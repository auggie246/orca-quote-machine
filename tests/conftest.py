"""Core test configuration and fixtures."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# Configure Celery for testing before importing the app
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"
os.environ["CELERY_TASK_EAGER_PROPAGATES"] = "True"

from app.main import app
from app.core.config import get_settings


@pytest.fixture(scope="session")
def celery_config():
    """Configure Celery for testing."""
    return {
        "broker_url": "memory://",
        "result_backend": "rpc://",
        "task_always_eager": True,
        "task_eager_propagates": True,
    }


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Provides a TestClient for making requests to the FastAPI app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_settings():
    """Override settings for testing."""
    settings = get_settings()
    # Create temporary upload directory
    temp_dir = tempfile.mkdtemp()
    settings.upload_dir = temp_dir
    settings.max_file_size = 10 * 1024 * 1024  # 10MB for tests
    settings.secret_key = "test-secret-key"
    return settings


@pytest.fixture
def mock_orcaslicer_service(mocker):
    """Mock the OrcaSlicerService to prevent actual CLI calls."""
    mock_service = mocker.patch("app.services.slicer.OrcaSlicerService")
    mock_instance = mock_service.return_value
    
    # Default successful return value
    mock_instance.slice_model.return_value = {
        "print_time_minutes": 120,  # 2 hours
        "filament_weight_grams": 25.5,
        "layer_count": 200
    }
    return mock_instance


@pytest.fixture
def mock_pricing_service(mocker):
    """Mock the PricingService."""
    mock_service = mocker.patch("app.services.pricing.PricingService")
    mock_instance = mock_service.return_value
    
    # Default pricing calculation
    mock_instance.calculate_quote.return_value = {
        "material_cost": 12.50,
        "time_cost": 15.00,
        "total_cost": 30.25
    }
    return mock_instance


@pytest.fixture
def mock_telegram_service(mocker):
    """Mock the TelegramService."""
    mock_service = mocker.patch("app.services.telegram.TelegramService")
    mock_instance = mock_service.return_value
    
    # Mock successful message sending
    mock_instance.send_quote_notification.return_value = True
    return mock_instance


@pytest.fixture
def mock_rust_validation(mocker):
    """Mock the Rust validation functions."""
    mock_validate = mocker.patch("app.tasks.validate_3d_model")
    mock_validate.return_value = True  # Valid file by default
    return mock_validate


@pytest.fixture
def sample_stl_content():
    """Sample STL file content for testing."""
    return b"""solid test_model
facet normal 0.0 0.0 1.0
  outer loop
    vertex 0.0 0.0 0.0
    vertex 1.0 0.0 0.0
    vertex 0.0 1.0 0.0
  endloop
endfacet
endsolid test_model"""


@pytest.fixture
def sample_quote_data():
    """Sample valid quote request data."""
    return {
        "name": "John Doe",
        "mobile": "+6591234567",
        "material": "PLA",
        "color": "Red"
    }


@pytest.fixture
def invalid_quote_data():
    """Sample invalid quote request data for testing validation."""
    return {
        "name": "",  # Invalid: empty name
        "mobile": "invalid-phone",  # Invalid format
        "material": "INVALID_MATERIAL",  # Invalid material
        "color": "A" * 100  # Invalid: too long
    }


@pytest.fixture
def temp_upload_file(sample_stl_content):
    """Create a temporary file for upload testing."""
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        f.write(sample_stl_content)
        f.flush()
        yield f.name
    # Cleanup
    os.unlink(f.name)


@pytest.fixture(autouse=True)
def cleanup_uploads():
    """Automatically cleanup upload directory after each test."""
    yield
    # Cleanup logic can be added here if needed
    pass