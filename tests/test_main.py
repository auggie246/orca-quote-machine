"""Integration tests for FastAPI endpoints."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pytest_mock import MockerFixture


class TestHomeEndpoint:
    """Tests for the home page endpoint."""

    def test_home_page_returns_html(self, client: TestClient) -> None:
        """Test that the home page returns HTML with the form."""
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        # Check that form elements are present
        assert "form" in response.text.lower()
        assert "file" in response.text.lower()


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """Test that health check returns proper status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app_name" in data
        assert "version" in data


class TestQuoteEndpoint:
    """Tests for the quote processing endpoint."""

    def test_create_quote_success(
        self,
        client: TestClient,
        sample_stl_content: bytes,
        sample_quote_data: dict,
        mock_orcaslicer_service: MagicMock,
        mock_pricing_service: MagicMock,
        mock_telegram_service: MagicMock,
    ) -> None:
        """Test successful quote creation with valid data."""
        files = {
            "model_file": ("test.stl", sample_stl_content, "application/octet-stream")
        }

        response = client.post("/quote", files=files, data=sample_quote_data)

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert "message" in data
        assert data["customer_name"] == sample_quote_data["name"]
        assert data["filename"] == "test.stl"
        assert "estimated_processing_time" in data

    def test_create_quote_no_file(
        self, client: TestClient, sample_quote_data: dict
    ) -> None:
        """Test quote creation fails when no file is provided."""
        response = client.post("/quote", data=sample_quote_data)

        assert response.status_code == 422  # Validation error

    def test_create_quote_invalid_file_extension(
        self, client: TestClient, sample_quote_data: dict
    ) -> None:
        """Test quote creation fails with invalid file extension."""
        files = {"model_file": ("test.txt", b"not a 3d model", "text/plain")}

        response = client.post("/quote", files=files, data=sample_quote_data)

        assert response.status_code == 400
        assert "File type .txt not allowed" in response.json()["detail"]

    def test_create_quote_invalid_material(
        self, client: TestClient, sample_stl_content: bytes
    ) -> None:
        """Test quote creation fails with invalid material."""
        files = {
            "model_file": ("test.stl", sample_stl_content, "application/octet-stream")
        }
        data = {
            "name": "John Doe",
            "mobile": "+6591234567",
            "material": "INVALID_MATERIAL",
            "color": "Red",
        }

        response = client.post("/quote", files=files, data=data)

        assert response.status_code == 400
        assert "Invalid material" in response.json()["detail"]

    def test_create_quote_invalid_name(
        self, client: TestClient, sample_stl_content: bytes
    ) -> None:
        """Test quote creation fails with invalid name."""
        files = {
            "model_file": ("test.stl", sample_stl_content, "application/octet-stream")
        }
        data = {"name": "", "mobile": "+6591234567", "material": "PLA"}  # Empty name

        response = client.post("/quote", files=files, data=data)

        assert response.status_code == 422  # Validation error

    def test_create_quote_invalid_mobile(
        self, client: TestClient, sample_stl_content: bytes
    ) -> None:
        """Test quote creation fails with invalid mobile number."""
        files = {
            "model_file": ("test.stl", sample_stl_content, "application/octet-stream")
        }
        data = {"name": "John Doe", "mobile": "invalid-phone", "material": "PLA"}

        response = client.post("/quote", files=files, data=data)

        assert response.status_code == 400
        assert "Invalid mobile number format" in response.json()["detail"]

    def test_create_quote_no_filename(
        self, client: TestClient, sample_stl_content: bytes, sample_quote_data: dict
    ) -> None:
        """Test quote creation fails when file has no filename."""
        files = {"model_file": ("", sample_stl_content, "application/octet-stream")}

        response = client.post("/quote", files=files, data=sample_quote_data)

        assert response.status_code == 422
        assert "detail" in response.json()

    def test_create_quote_large_file(
        self, client: TestClient, sample_quote_data: dict
    ) -> None:
        """Test quote creation fails with oversized file."""
        # Create a large file (larger than 100MB default limit)
        large_content = b"x" * (101 * 1024 * 1024)  # 101MB
        files = {"model_file": ("large.stl", large_content, "application/octet-stream")}

        response = client.post("/quote", files=files, data=sample_quote_data)

        assert response.status_code == 413  # Request entity too large
        assert "File too large" in response.json()["detail"]


class TestTaskStatusEndpoint:
    """Tests for the task status endpoint."""

    def test_get_task_status_pending(
        self, client: TestClient, mocker: MockerFixture
    ) -> None:
        """Test getting status of a pending task."""
        # Mock celery result
        mock_result = mocker.patch("app.main.celery_app.AsyncResult")
        mock_result.return_value.state = "PENDING"

        response = client.get("/status/test-task-id")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "processing"

    def test_get_task_status_success(
        self, client: TestClient, mocker: MockerFixture
    ) -> None:
        """Test getting status of a successful task."""
        mock_result = mocker.patch("app.main.celery_app.AsyncResult")
        mock_result.return_value.state = "SUCCESS"
        mock_result.return_value.result = {"total_cost": 25.50}

        response = client.get("/status/test-task-id")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "completed"
        assert "result" in data

    def test_get_task_status_failure(
        self, client: TestClient, mocker: MockerFixture
    ) -> None:
        """Test getting status of a failed task."""
        mock_result = mocker.patch("app.main.celery_app.AsyncResult")
        mock_result.return_value.state = "FAILURE"
        mock_result.return_value.info = "Slicing failed"

        response = client.get("/status/test-task-id")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "failed"
        assert "error" in data
