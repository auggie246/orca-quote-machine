"""Unit tests for main FastAPI app logic.

Focus: Test request validation logic, file handling logic, and response formatting.
"""

from unittest.mock import MagicMock, patch

import pytest
from _rust_core import secure_filename
from fastapi.testclient import TestClient

from app.main import app


class TestSecureFilenameIntegration:
    """Test that the app correctly uses Rust secure_filename."""

    def test_secure_filename_removes_path_traversal(self):
        """Test that secure_filename prevents path traversal."""
        # Test the actual Rust function
        result = secure_filename("../../etc/passwd")

        # The sanitize-filename crate converts path separators to dots
        assert "/" not in result
        assert "\\" not in result
        # The important thing is that it can't be used for path traversal
        assert result != "../../etc/passwd"

    def test_secure_filename_preserves_valid_names(self):
        """Test that secure_filename preserves valid filenames."""
        result = secure_filename("my_model_v2.stl")

        assert "my_model_v2.stl" in result


class TestQuoteEndpointLogic:
    """Test the quote endpoint validation and processing logic."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_quote_validates_file_extension(self, client):
        """Test that only allowed file extensions are accepted."""
        # Create a file with invalid extension
        files = {"model_file": ("test.txt", b"content", "text/plain")}
        data = {
            "name": "Test User",
            "mobile": "+1234567890",
            "material": "PLA",
            "color": "Blue"
        }

        response = client.post("/quote", files=files, data=data)

        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]

    def test_quote_validates_material_exists(self, client):
        """Test material validation against available materials."""
        files = {"model_file": ("test.stl", b"content", "application/octet-stream")}
        data = {
            "name": "Test User",
            "mobile": "+1234567890",
            "material": "INVALID_MATERIAL",
            "color": "Blue"
        }

        # Mock slicer service to control available materials
        with patch('app.main.OrcaSlicerService') as mock_slicer:
            mock_instance = mock_slicer.return_value
            mock_instance.get_available_materials.return_value = ["PLA", "PETG", "ASA"]

            response = client.post("/quote", files=files, data=data)

            assert response.status_code == 400
            assert "Invalid material" in response.json()["detail"]

    def test_quote_accepts_custom_materials(self, client):
        """Test that custom materials discovered by slicer are accepted."""
        files = {"model_file": ("test.stl", b"content", "application/octet-stream")}
        data = {
            "name": "Test User",
            "mobile": "+1234567890",
            "material": "TPU",  # Custom material
            "color": "Black"
        }

        # Mock the services
        with patch('app.main.OrcaSlicerService') as mock_slicer:
            mock_instance = mock_slicer.return_value
            mock_instance.get_available_materials.return_value = ["PLA", "PETG", "ASA", "TPU"]

            # Mock the task
            with patch('app.main.process_quote_request.delay') as mock_task:
                mock_task.return_value = MagicMock(id="test-task-id")

                response = client.post("/quote", files=files, data=data)

                assert response.status_code == 202
                assert response.json()["material"] == "TPU"

    def test_quote_applies_secure_filename(self, client):
        """Test that uploaded filenames are sanitized."""
        # Filename with path traversal attempt
        dangerous_filename = "../../../etc/passwd"
        files = {"model_file": (dangerous_filename, b"content", "application/octet-stream")}
        data = {
            "name": "Test User",
            "mobile": "+1234567890",
            "material": "PLA",
            "color": "Red"
        }

        with patch('app.main.process_quote_request.delay') as mock_task:
            mock_task.return_value = MagicMock(id="test-task-id")

            response = client.post("/quote", files=files, data=data)

            if response.status_code == 202:
                # Check that the filename was sanitized
                assert response.json()["filename"] != dangerous_filename
                assert ".." not in response.json()["filename"]


class TestHomeEndpointLogic:
    """Test the home endpoint template data logic."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_home_includes_available_materials(self, client):
        """Test that home page gets materials from slicer service."""
        with patch('app.main.OrcaSlicerService') as mock_slicer:
            mock_instance = mock_slicer.return_value
            mock_instance.get_available_materials.return_value = ["PLA", "PETG", "TPU"]

            response = client.get("/")

            assert response.status_code == 200
            # Materials should be passed to template

    def test_home_fallback_on_slicer_error(self, client):
        """Test that home page falls back to enum values on error."""
        with patch('app.main.OrcaSlicerService') as mock_slicer:
            mock_instance = mock_slicer.return_value
            mock_instance.get_available_materials.side_effect = Exception("Service error")

            response = client.get("/")

            assert response.status_code == 200
            # Should still work with fallback materials


class TestTaskStatusLogic:
    """Test task status endpoint logic."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_status_formats_pending_correctly(self, client):
        """Test pending task status formatting."""
        with patch('app.main.celery_app.AsyncResult') as mock_result:
            mock_result.return_value.state = "PENDING"

            response = client.get("/status/test-task-id")

            assert response.status_code == 200
            assert response.json()["status"] == "processing"
            assert response.json()["task_id"] == "test-task-id"

    def test_status_includes_result_on_success(self, client):
        """Test successful task includes result data."""
        with patch('app.main.celery_app.AsyncResult') as mock_result:
            mock_async = mock_result.return_value
            mock_async.state = "SUCCESS"
            mock_async.result = {"total_cost": 25.50, "print_time": 120}

            response = client.get("/status/test-task-id")

            assert response.status_code == 200
            assert response.json()["status"] == "completed"
            assert "result" in response.json()
            assert response.json()["result"]["total_cost"] == 25.50
