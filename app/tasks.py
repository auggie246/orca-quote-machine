"""Celery tasks for background processing."""

import asyncio
import contextlib
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from celery import Celery, Task
from celery.utils.log import get_task_logger

from app.core.config import get_settings
from app.models.quote import MaterialType, TelegramMessage
from app.services.pricing import PricingService
from app.services.slicer import OrcaSlicerService
from app.services.telegram import TelegramService

# Import Rust validation functions
try:
    from _rust_core import validate_3d_model
except ImportError:
    print(
        "Warning: Rust validation module not available. Install with 'maturin develop'"
    )
    validate_3d_model = None

settings = get_settings()
logger = get_task_logger(__name__)

# Initialize Celery with test-aware configuration
if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("CELERY_TASK_ALWAYS_EAGER"):
    # Use in-memory broker for testing
    celery_app = Celery(
        "orca_quote_machine",
        broker="memory://",
        backend="rpc://",
    )
else:
    # Use Redis for production
    celery_app = Celery(
        "orca_quote_machine",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )

# Configure Celery settings
celery_config = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
}

# Add eager mode for testing
if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("CELERY_TASK_ALWAYS_EAGER"):
    celery_config.update(
        {
            "task_always_eager": True,
            "task_eager_propagates": True,
        }
    )

celery_app.conf.update(**celery_config)


@celery_app.task(bind=True)
def process_quote_request(
    self: Task, file_path: str, quote_data: dict, material: str | None = None
) -> dict:
    """
    Process a quote request in the background.

    Args:
        file_path: Path to uploaded 3D model file
        quote_data: Quote request data
        material: Material type (PLA, PETG, ASA)

    Returns:
        Dictionary with processing results
    """
    quote_id = str(uuid.uuid4())
    short_quote_id = quote_id[:8]

    logger.info(f"Processing quote {short_quote_id} for file {file_path}")

    try:
        # Validate file using Rust if available
        if validate_3d_model:
            validation_result = validate_3d_model(file_path)
            if not validation_result.is_valid:
                raise Exception(f"Invalid 3D model: {validation_result.error_message}")
            logger.info(f"File validation passed: {validation_result.file_type}")

        # Parse material
        material_enum = None
        if material:
            try:
                material_enum = MaterialType(material.upper())
            except ValueError:
                logger.warning(f"Unknown material {material}, defaulting to PLA")
                material_enum = MaterialType.PLA

        # Run async processing pipeline
        result = asyncio.run(
            run_processing_pipeline(
                file_path, quote_data, material_enum, quote_id, short_quote_id
            )
        )
        return result

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Quote processing failed for {short_quote_id}: {error_msg}")

        # Send error notification
        with contextlib.suppress(Exception):
            asyncio.run(send_failure_notification(error_msg, short_quote_id))

        return {
            "success": False,
            "quote_id": quote_id,
            "error": error_msg,
            "processed_at": datetime.utcnow().isoformat(),
        }

    finally:
        # Cleanup uploaded file
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup file {file_path}: {e}")


async def run_processing_pipeline(
    file_path: str,
    quote_data: dict,
    material_enum: MaterialType | None,
    quote_id: str,
    short_quote_id: str,
) -> dict[str, Any]:
    """
    Helper async function to orchestrate async calls in the processing pipeline.
    """
    # Run slicing
    slicer_service = OrcaSlicerService()
    slicing_result = await slicer_service.slice_model(file_path, material_enum)
    logger.info(
        f"Slicing completed: {slicing_result.print_time_minutes}min, {slicing_result.filament_weight_grams}g"
    )

    # Calculate pricing
    pricing_service = PricingService()
    cost_breakdown = pricing_service.calculate_quote(slicing_result, material_enum)
    logger.info(f"Pricing calculated: S${cost_breakdown['total_cost']:.2f}")

    # Send Telegram notification
    telegram_service = TelegramService()
    telegram_message = TelegramMessage(
        quote_id=short_quote_id,
        customer_name=quote_data["name"],
        customer_mobile=quote_data["mobile"],
        material=material_enum.value if material_enum else None,
        color=quote_data.get("color"),
        filename=quote_data["filename"],
        print_time=f"{slicing_result.print_time_minutes // 60}h {slicing_result.print_time_minutes % 60}m",
        filament_weight=f"{slicing_result.filament_weight_grams:.1f}g",
        total_cost=cost_breakdown["total_cost"],
    )

    notification_sent = await telegram_service.send_quote_notification(telegram_message)

    return {
        "success": True,
        "quote_id": quote_id,
        "slicing_result": {
            "print_time_minutes": slicing_result.print_time_minutes,
            "filament_weight_grams": slicing_result.filament_weight_grams,
        },
        "cost_breakdown": cost_breakdown,
        "notification_sent": notification_sent,
        "processed_at": datetime.utcnow().isoformat(),
    }


async def send_failure_notification(error_msg: str, quote_id: str) -> None:
    """Send error notification to admin."""
    telegram_service = TelegramService()
    await telegram_service.send_error_notification(error_msg, quote_id)


@celery_app.task
def cleanup_old_files(max_age_hours: int = 24) -> dict[str, Any]:
    """
    Cleanup old uploaded files.

    Args:
        max_age_hours: Maximum age of files to keep

    Returns:
        Cleanup statistics
    """
    from datetime import timedelta

    upload_dir = Path(settings.upload_dir)
    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

    cleaned_count = 0
    total_size = 0

    try:
        for file_path in upload_dir.glob("*"):
            if file_path.is_file():
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time < cutoff_time:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    cleaned_count += 1
                    total_size += file_size
                    logger.info(f"Cleaned up old file: {file_path}")

        return {
            "success": True,
            "files_cleaned": cleaned_count,
            "bytes_freed": total_size,
            "cutoff_time": cutoff_time.isoformat(),
        }

    except Exception as e:
        logger.error(f"File cleanup failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }
