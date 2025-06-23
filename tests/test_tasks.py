"""Unit tests for Celery tasks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orca_quote_machine.models.quote import MaterialType
from orca_quote_machine.tasks import (
    cleanup_old_files,
    process_quote_request,
    run_processing_pipeline,
    send_failure_notification,
)


class TestTasks:
    """Tests for Celery task functions."""

    @patch("orca_quote_machine.tasks.asyncio.run")
    @patch("orca_quote_machine.tasks.validate_3d_model", None)
    @patch("orca_quote_machine.tasks.os.path.exists", return_value=False)
    def test_process_quote_request(
        self, mock_exists: MagicMock, mock_asyncio_run: MagicMock
    ) -> None:
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
    @patch("orca_quote_machine.tasks.OrcaSlicerService")
    @patch("orca_quote_machine.tasks.PricingService")
    @patch("orca_quote_machine.tasks.TelegramService")
    async def test_run_processing_pipeline(
        self, mock_telegram: MagicMock, mock_pricing: MagicMock, mock_slicer: MagicMock
    ) -> None:
        """Test run_processing_pipeline function."""
        import os
        import tempfile

        from orca_quote_machine._rust_core import SlicingResult, parse_slicer_output

        # Create a real SlicingResult using Rust parser
        async def create_real_slicing_result() -> SlicingResult:
            with tempfile.TemporaryDirectory() as temp_dir:
                gcode_file = os.path.join(temp_dir, 'test.gcode')
                with open(gcode_file, 'w') as f:  # noqa: ASYNC230  # Test file creation
                    f.write('; estimated printing time: 2h 0m\n; filament used: 25.5g\n')
                return await parse_slicer_output(temp_dir)

        real_slicing_result = await create_real_slicing_result()

        # Setup mocks with real objects
        mock_slicer_instance = mock_slicer.return_value
        mock_slicer_instance.slice_model = AsyncMock(return_value=real_slicing_result)

        # Use real pricing service to create real CostBreakdown
        from orca_quote_machine.services.pricing import PricingService
        real_pricing_service = PricingService()
        real_cost_breakdown = real_pricing_service.calculate_quote(real_slicing_result, MaterialType.PLA)

        mock_pricing_instance = mock_pricing.return_value
        mock_pricing_instance.calculate_quote.return_value = real_cost_breakdown

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
    @patch("orca_quote_machine.tasks.TelegramService")
    async def test_send_failure_notification(self, mock_telegram: MagicMock) -> None:
        """Test send_failure_notification function."""
        mock_telegram_instance = mock_telegram.return_value
        mock_telegram_instance.send_error_notification = AsyncMock()

        result = await send_failure_notification("Test error", "test-123")

        # Function returns None
        assert result is None

    @patch("orca_quote_machine.tasks.cleanup_old_files_rust")
    def test_cleanup_old_files(self, mock_cleanup_rust: MagicMock) -> None:
        """Test cleanup_old_files function."""
        # Mock the Rust cleanup function to return stats
        mock_stats = MagicMock()
        mock_stats.files_cleaned = 5
        mock_stats.bytes_freed = 12345
        mock_cleanup_rust.return_value = mock_stats

        result = cleanup_old_files(max_age_hours=24)

        assert isinstance(result, dict)
        assert "success" in result
        assert result["files_cleaned"] == 5
        assert result["bytes_freed"] == 12345
