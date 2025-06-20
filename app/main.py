"""FastAPI application for OrcaSlicer quotation machine."""

import contextlib
import os
import re
import uuid
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from app.core.config import get_settings
from app.models.quote import MaterialType, QuoteRequest
from app.services.slicer import OrcaSlicerService
from app.tasks import celery_app, process_quote_request

settings = get_settings()

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Generate 3D printing quotations using OrcaSlicer",
    version="0.1.0",
    debug=settings.debug,
)

# Mount static files and templates
# Skip static mounting during testing to avoid RuntimeError
if not os.getenv("PYTEST_CURRENT_TEST"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Ensure upload directory exists
Path(settings.upload_dir).mkdir(exist_ok=True)


def secure_filename(filename: str) -> str:
    """Sanitizes a filename to prevent path traversal attacks."""
    if not filename:
        return ""

    # Keep only alphanumeric, dots, dashes, and underscores
    filename = re.sub(r"[^a-zA-Z0-9._-]", "", filename)

    # Prevent path traversal by removing leading dots or slashes
    filename = filename.lstrip("./\\")

    # Ensure we don't have an empty filename
    if not filename:
        return "unnamed_file"

    return filename


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> Response:
    """Home page with quote request form."""
    # Get available materials from slicer service (includes custom materials)
    try:
        slicer_service = OrcaSlicerService()
        available_materials = slicer_service.get_available_materials()
    except Exception:
        # Fallback to enum values if slicer service fails
        available_materials = [material.value for material in MaterialType]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "materials": available_materials,
            "max_file_size_mb": settings.max_file_size // (1024 * 1024),
            "allowed_extensions": ", ".join(settings.allowed_extensions),
        },
    )


@app.post("/quote")
async def create_quote(
    name: str = Form(..., min_length=1, max_length=100),
    mobile: str = Form(..., min_length=8, max_length=20),
    material: str | None = Form(None),
    color: str | None = Form(None, max_length=50),
    model_file: UploadFile = File(...),
) -> JSONResponse:
    """
    Create a new quote request.

    Accepts form data and uploads the 3D model file.
    Starts background processing and returns immediately.
    """

    # Validate file
    if not model_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided"
        )

    file_ext = Path(model_file.filename).suffix.lower()
    if file_ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed. Supported: {', '.join(settings.allowed_extensions)}",
        )

    # Validate material against available materials (including custom ones)
    if material:
        try:
            slicer_service = OrcaSlicerService()
            available_materials = slicer_service.get_available_materials()
            if material.upper() not in available_materials:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid material. Supported: {', '.join(available_materials)}",
                )
        except Exception:
            # Fallback to enum validation if slicer service fails
            if material.upper() not in [m.value for m in MaterialType]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid material. Supported: {', '.join([m.value for m in MaterialType])}",
                ) from None

    # Sanitize filename to prevent path traversal
    safe_filename = secure_filename(model_file.filename)
    if not safe_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename"
        )

    try:
        # Validate quote request data
        quote_request = QuoteRequest(
            name=name,
            mobile=mobile,
            material=MaterialType(material.upper()) if material else None,
            color=color,
            filename=safe_filename,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    # Save uploaded file with size validation during write
    file_id = str(uuid.uuid4())
    file_path = Path(settings.upload_dir) / f"{file_id}_{safe_filename}"

    written_bytes = 0
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await model_file.read(8192):  # Read in 8KB chunks
                written_bytes += len(chunk)
                if written_bytes > settings.max_file_size:
                    # Clean up partial file
                    await f.close()
                    if file_path.exists():
                        os.remove(file_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Maximum size: {settings.max_file_size // (1024 * 1024)}MB",
                    )
                await f.write(chunk)
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        # Clean up file if it exists
        if file_path.exists():
            with contextlib.suppress(Exception):
                os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}",
        ) from e

    # Start background processing
    try:
        task = process_quote_request.delay(
            file_path=str(file_path),
            quote_data=quote_request.model_dump(),
            material=material,
        )

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "message": "Quote request received and is being processed",
                "task_id": task.id,
                "customer_name": quote_request.name,
                "filename": quote_request.filename,
                "material": material or "PLA (default)",
                "estimated_processing_time": "2-5 minutes",
            },
        )

    except Exception as e:
        # Cleanup file if task creation fails
        with contextlib.suppress(Exception):
            os.remove(file_path)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start processing: {str(e)}",
        ) from e


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "app_name": settings.app_name, "version": "0.1.0"}


@app.get("/status/{task_id}")
async def get_task_status(task_id: str) -> dict[str, Any]:
    """Get the status of a background task."""
    task_result = celery_app.AsyncResult(task_id)

    if task_result.state == "PENDING":
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Task is being processed...",
        }
    elif task_result.state == "SUCCESS":
        result = task_result.result
        return {"task_id": task_id, "status": "completed", "result": result}
    elif task_result.state == "FAILURE":
        return {"task_id": task_id, "status": "failed", "error": str(task_result.info)}
    else:
        return {
            "task_id": task_id,
            "status": task_result.state,
            "message": "Task state: " + task_result.state,
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host=settings.host, port=settings.port, reload=settings.debug
    )
