"""Unit tests for Celery tasks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.quote import MaterialType, SlicingResult
from app.tasks import (cleanup_old_files, process_quote_request,
                       run_processing_pipeline, send_failure_notification)


class TestTasks:
    """Tests for Celery task functions."""

    @patch("app.tasks.asyncio.run")
    @patch("app.tasks.validate_3d_model", None)
    @patch("app.tasks.os.path.exists", return_value=False)
    def test_process_quote_request(self, mock_exists, mock_asyncio_run):
        """Test process_quote_request task function."""
        mock_asyncio_run.return_value = {"success": True, "total_cost": 25.50}

        quote_data = {
            "name": "John Doe",
            "mobile": "+6591234567",
            "filename": "test.stl",
        }

        result = process_quote_request("/path/to/file.stl", quote_data, "PLA")

        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    @patch("app.tasks.OrcaSlicerService")
    @patch("app.tasks.PricingService")
    @patch("app.tasks.TelegramService")
    async def test_run_processing_pipeline(
        self, mock_telegram, mock_pricing, mock_slicer
    ):
        """Test run_processing_pipeline function."""
        # Setup mocks
        mock_slicer_instance = mock_slicer.return_value
        mock_slicer_instance.slice_model = AsyncMock(
            return_value=SlicingResult(
                print_time_minutes=120, filament_weight_grams=25.5
            )
        )

        mock_pricing_instance = mock_pricing.return_value
        mock_pricing_instance.calculate_quote.return_value = {"total_cost": 30.50}

        mock_telegram_instance = mock_telegram.return_value
        mock_telegram_instance.send_quote_notification = AsyncMock(return_value=True)

        quote_data = {
            "name": "John Doe",
            "mobile": "+6591234567",
            "filename": "test.stl",
        }

        result = await run_processing_pipeline(
            "/path/to/test.stl", quote_data, MaterialType.PLA, "test-uuid", "test-123"
        )

        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    @patch("app.tasks.TelegramService")
    async def test_send_failure_notification(self, mock_telegram):
        """Test send_failure_notification function."""
        mock_telegram_instance = mock_telegram.return_value
        mock_telegram_instance.send_error_notification = AsyncMock()

        result = await send_failure_notification("Test error", "test-123")

        # Function returns None
        assert result is None

    @patch("app.tasks.Path")
    def test_cleanup_old_files(self, mock_path):
        """Test cleanup_old_files function."""
        result = cleanup_old_files(max_age_hours=24)

        assert isinstance(result, dict)
        assert "success" in result
