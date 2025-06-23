"""Celery tasks for background processing."""

import asyncio
import contextlib
import os
import uuid
from datetime import datetime
from typing import Any

from celery import Celery, Task
from celery.utils.log import get_task_logger

# Import Rust functions
from orca_quote_machine._rust_core import cleanup_old_files_rust, validate_3d_model
from orca_quote_machine.core.config import get_settings
from orca_quote_machine.models.quote import MaterialType, TelegramMessage
from orca_quote_machine.services.pricing import PricingService
from orca_quote_machine.services.slicer import OrcaSlicerService
from orca_quote_machine.services.telegram import TelegramService

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
        # Validate file using Rust
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
        except OSError as e:
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
    # Get fresh settings for services
    settings = get_settings()

    # Run slicing
    slicer_service = OrcaSlicerService(settings=settings)
    slicing_result = await slicer_service.slice_model(file_path, material_enum)
    logger.info(
        f"Slicing completed: {slicing_result.print_time_minutes}min, {slicing_result.filament_weight_grams}g"
    )

    # Calculate pricing
    pricing_service = PricingService(settings=settings)
    cost_breakdown = pricing_service.calculate_quote(slicing_result, material_enum)
    logger.info(f"Pricing calculated: S${cost_breakdown.total_cost:.2f}")

    # Send Telegram notification
    telegram_service = TelegramService(settings=settings)
    telegram_message = TelegramMessage(
        quote_id=short_quote_id,
        customer_name=quote_data["name"],
        customer_mobile=quote_data["mobile"],
        material=material_enum.value if material_enum else None,
        color=quote_data.get("color"),
        filename=quote_data["filename"],
        print_time=f"{slicing_result.print_time_minutes // 60}h {slicing_result.print_time_minutes % 60}m",
        filament_weight=f"{slicing_result.filament_weight_grams:.1f}g",
        total_cost=cost_breakdown.total_cost,
    )

    notification_sent = await telegram_service.send_quote_notification(telegram_message)

    return {
        "success": True,
        "quote_id": quote_id,
        "slicing_result": {
            "print_time_minutes": slicing_result.print_time_minutes,
            "filament_weight_grams": slicing_result.filament_weight_grams,
        },
        "cost_breakdown": {
            "material_type": cost_breakdown.material_type,
            "total_cost": cost_breakdown.total_cost,
            "filament_kg": cost_breakdown.filament_kg,
            "print_time_hours": cost_breakdown.print_time_hours,
            "minimum_applied": cost_breakdown.minimum_applied,
        },
        "notification_sent": notification_sent,
        "processed_at": datetime.utcnow().isoformat(),
    }


async def send_failure_notification(error_msg: str, quote_id: str) -> None:
    """Send error notification to admin."""
    settings = get_settings()
    telegram_service = TelegramService(settings=settings)
    await telegram_service.send_error_notification(error_msg, quote_id)


@celery_app.task
def cleanup_old_files(max_age_hours: int = 24) -> dict[str, Any]:
    """
    Cleanup old uploaded files using high-performance Rust implementation.

    Args:
        max_age_hours: Maximum age of files to keep

    Returns:
        Cleanup statistics
    """
    try:
        stats = cleanup_old_files_rust(settings.upload_dir, max_age_hours)
        logger.info(
            f"Cleaned up {stats.files_cleaned} old files, freeing {stats.bytes_freed} bytes."
        )

        return {
            "success": True,
            "files_cleaned": stats.files_cleaned,
            "bytes_freed": stats.bytes_freed,
        }

    except Exception as e:
        logger.error(f"File cleanup failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }
