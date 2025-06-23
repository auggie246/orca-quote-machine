"""Core test configuration and fixtures."""

import os
import tempfile
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

# Configure Celery for testing before importing the app
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"
os.environ["CELERY_TASK_EAGER_PROPAGATES"] = "True"
os.environ["PYTEST_CURRENT_TEST"] = "conftest.py"
os.environ["MAX_FILE_SIZE"] = "104857600"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest"

from app.core.config import get_settings
from app.main import app


@pytest.fixture(scope="session")
def celery_config() -> dict[str, Any]:
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
def test_settings() -> Any:
    """Override settings for testing."""
    settings = get_settings()
    # Create temporary upload directory
    temp_dir = tempfile.mkdtemp()
    settings.upload_dir = temp_dir
    settings.max_file_size = 10 * 1024 * 1024  # 10MB for tests
    settings.secret_key = "test-secret-key"

    yield settings

    # Cleanup the temporary directory
    import shutil
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def mock_orcaslicer_cli(mocker: MockerFixture) -> MagicMock:
    """Mock only the OrcaSlicer CLI subprocess call."""
    # Mock at the subprocess level, not the service level
    mock_subprocess = mocker.patch("asyncio.create_subprocess_exec")
    mock_process = mocker.AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = mocker.AsyncMock(return_value=(b"Success", b""))
    mock_subprocess.return_value = mock_process
    return mock_subprocess


@pytest.fixture
async def sample_slicing_result(create_test_gcode_dir):
    """Create a real SlicingResult for testing."""
    from _rust_core import parse_slicer_output

    # Create a test G-code directory with expected content
    temp_dir = create_test_gcode_dir(print_time="2h 0m", filament="50.0g")

    # Use the real Rust parser to create a SlicingResult
    slicing_result = await parse_slicer_output(temp_dir)

    # Clean up the temporary directory
    import shutil
    shutil.rmtree(temp_dir)

    return slicing_result


@pytest.fixture
def sample_cost_breakdown():
    """Create a real CostBreakdown for testing."""
    from _rust_core import calculate_quote_rust

    # Use real Rust function with test parameters
    # calculate_quote_rust(print_time_minutes, filament_weight_grams, material_type,
    #                      price_per_kg, additional_time_hours, price_multiplier, minimum_price)
    return calculate_quote_rust(120, 50.0, "PLA", 25.0, 0.5, 1.1, 5.0)


@pytest.fixture
def sample_model_info(temp_upload_file):
    """Create a real ModelInfo for testing."""
    from _rust_core import validate_3d_model

    # Use the real Rust validator with a temporary test file
    return validate_3d_model(temp_upload_file)


@pytest.fixture
def sample_cleanup_stats():
    """Create a real CleanupStats for testing."""
    from _rust_core import cleanup_old_files_rust

    # Create a temporary directory with old files
    temp_dir = tempfile.mkdtemp()

    # Create some test files
    for i in range(3):
        test_file = os.path.join(temp_dir, f"old_file_{i}.stl")
        with open(test_file, "w") as f:
            f.write("test content")
        # Make files old by setting their modification time to 48 hours ago
        old_time = os.path.getmtime(test_file) - (48 * 3600)
        os.utime(test_file, (old_time, old_time))

    # Run cleanup on the directory
    stats = cleanup_old_files_rust(temp_dir, 24)

    # Clean up the directory
    import shutil
    shutil.rmtree(temp_dir)

    return stats


@pytest.fixture
def mock_telegram_api(mocker: MockerFixture) -> MagicMock:
    """Mock only the Telegram HTTP API calls."""
    # Mock at the HTTP level, not the service level
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_response = mocker.AsyncMock()
    mock_response.status_code = 200
    mock_response.json = mocker.AsyncMock(return_value={"ok": True})
    mock_post.return_value = mock_response
    return mock_post


@pytest.fixture
def create_test_gcode_dir():
    """Create a temporary directory with test G-code file."""
    created_dirs = []

    def _create_gcode(print_time="2h 0m", filament="100.0g"):
        temp_dir = tempfile.mkdtemp()
        created_dirs.append(temp_dir)
        gcode_file = os.path.join(temp_dir, 'output.gcode')
        with open(gcode_file, 'w') as f:
            f.write(f'; estimated printing time: {print_time}\n')
            f.write(f'; filament used: {filament}\n')
            f.write('; layer_count: 150\n')
        return temp_dir

    yield _create_gcode

    # Cleanup all created directories
    import shutil
    for temp_dir in created_dirs:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@pytest.fixture
def sample_stl_content() -> bytes:
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
def sample_quote_data() -> dict[str, Any]:
    """Sample valid quote request data."""
    return {
        "name": "John Doe",
        "mobile": "+6591234567",
        "material": "PLA",
        "color": "Red",
    }


@pytest.fixture
def invalid_quote_data() -> dict[str, Any]:
    """Sample invalid quote request data for testing validation."""
    return {
        "name": "",  # Invalid: empty name
        "mobile": "invalid-phone",  # Invalid format
        "material": "INVALID_MATERIAL",  # Invalid material
        "color": "A" * 100,  # Invalid: too long
    }


@pytest.fixture
def temp_upload_file(sample_stl_content: bytes) -> Generator[str, None, None]:
    """Create a temporary file for upload testing."""
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        f.write(sample_stl_content)
        f.flush()
        yield f.name
    # Cleanup
    os.unlink(f.name)


@pytest.fixture(autouse=True)
def cleanup_uploads(test_settings):
    """Automatically cleanup upload directory after each test."""
    yield

    # Clean up any files left in the upload directory
    import shutil
    upload_dir = test_settings.upload_dir
    if os.path.exists(upload_dir):
        for filename in os.listdir(upload_dir):
            file_path = os.path.join(upload_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception:
                pass  # Ignore errors during cleanup
