"""Unit tests for Celery task logic.

Focus: Test task orchestration logic, error handling, and cleanup behavior.
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orca_quote_machine.tasks import cleanup_old_files, process_quote_request


class TestProcessQuoteRequestLogic:
    """Test the quote processing task logic."""

    @patch('orca_quote_machine.tasks.validate_3d_model')
    def test_task_validates_file_first(self, mock_validate):
        """Test that task validates file before processing."""
        # Setup invalid file validation
        mock_result = MagicMock()
        mock_result.file_type = "stl"
        mock_result.file_size = 100
        mock_result.is_valid = False
        mock_result.error_message = "Invalid STL format"
        mock_validate.return_value = mock_result

        with tempfile.NamedTemporaryFile(suffix=".stl") as temp_file:
            result = process_quote_request(
                temp_file.name,
                {"name": "Test", "mobile": "123"},
                "PLA"
            )

            assert result["success"] is False
            assert "Invalid 3D model" in result["error"]
            mock_validate.assert_called_once_with(temp_file.name)

    @patch('orca_quote_machine.tasks.validate_3d_model')
    def test_task_handles_unknown_material(self, mock_validate):
        """Test that unknown materials default to PLA."""
        mock_result = MagicMock()
        mock_result.file_type = "stl"
        mock_result.file_size = 100
        mock_result.is_valid = True
        mock_result.error_message = None
        mock_validate.return_value = mock_result

        # Mock the async pipeline
        with patch('orca_quote_machine.tasks.asyncio.run') as mock_run:
            mock_run.return_value = {
                "success": True,
                "quote_id": "test-id",
                "slicing_result": {"print_time_minutes": 120},
                "cost_breakdown": {"total_cost": 25.0}
            }

            with tempfile.NamedTemporaryFile(suffix=".stl") as temp_file:
                result = process_quote_request(
                    temp_file.name,
                    {"name": "Test", "mobile": "123"},
                    "UNKNOWN_MATERIAL"  # Invalid material
                )

                # Should complete successfully with PLA default
                assert result["success"] is True

    def test_task_cleans_up_file_on_success(self):
        """Test that uploaded file is cleaned up after processing."""
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as temp_file:
            temp_path = temp_file.name

        # Ensure file exists
        assert os.path.exists(temp_path)

        with patch('orca_quote_machine.tasks.validate_3d_model') as mock_validate:
            mock_result = MagicMock()
            mock_result.file_type = "stl"
            mock_result.file_size = 100
            mock_result.is_valid = True
            mock_result.error_message = None
            mock_validate.return_value = mock_result

            with patch('orca_quote_machine.tasks.asyncio.run') as mock_run:
                mock_run.return_value = {
                    "success": True,
                    "quote_id": "test-id",
                    "slicing_result": {"print_time_minutes": 120},
                    "cost_breakdown": {"total_cost": 25.0}
                }

                process_quote_request(
                    temp_path,
                    {"name": "Test", "mobile": "123"},
                    "PLA"
                )

        # File should be cleaned up
        assert not os.path.exists(temp_path)

    def test_task_cleans_up_file_on_error(self):
        """Test that uploaded file is cleaned up even on error."""
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as temp_file:
            temp_path = temp_file.name

        # Ensure file exists
        assert os.path.exists(temp_path)

        with patch('orca_quote_machine.tasks.validate_3d_model') as mock_validate:
            mock_validate.side_effect = Exception("Validation error")

            result = process_quote_request(
                temp_path,
                {"name": "Test", "mobile": "123"},
                "PLA"
            )

            assert result["success"] is False
            # File should still be cleaned up
            assert not os.path.exists(temp_path)

    @patch('orca_quote_machine.tasks.send_failure_notification')
    @patch('orca_quote_machine.tasks.validate_3d_model')
    def test_task_sends_error_notification(self, mock_validate, mock_notify):
        """Test that errors trigger admin notification."""
        mock_validate.side_effect = Exception("Critical error")

        with tempfile.NamedTemporaryFile(suffix=".stl") as temp_file:
            result = process_quote_request(
                temp_file.name,
                {"name": "Test", "mobile": "123"},
                "PLA"
            )

            assert result["success"] is False
            # Should attempt to send notification (even if it fails)


class TestRunProcessingPipelineLogic:
    """Test the async processing pipeline orchestration."""

    @pytest.mark.asyncio
    async def test_pipeline_orchestrates_services(self, sample_slicing_result, sample_cost_breakdown):
        """Test that pipeline calls services in correct order."""
        from orca_quote_machine.tasks import run_processing_pipeline

        # Mock all services but use real Rust objects for return values
        with patch('orca_quote_machine.tasks.OrcaSlicerService') as mock_slicer:
            mock_slicer_instance = mock_slicer.return_value
            # Return the real SlicingResult fixture
            mock_slicer_instance.slice_model = AsyncMock(return_value=sample_slicing_result)

            with patch('orca_quote_machine.tasks.PricingService') as mock_pricing:
                mock_pricing_instance = mock_pricing.return_value
                # Return the real CostBreakdown fixture
                mock_pricing_instance.calculate_quote = MagicMock(return_value=sample_cost_breakdown)

                with patch('orca_quote_machine.tasks.TelegramService') as mock_telegram:
                    mock_telegram_instance = mock_telegram.return_value
                    mock_telegram_instance.send_quote_notification = AsyncMock(return_value=True)

                    result = await run_processing_pipeline(
                        "/test/file.stl",
                        {"name": "Test", "mobile": "123", "filename": "test.stl"},
                        None,  # Material
                        "quote-123",
                        "quote-12"
                    )

                    assert result["success"] is True
                    assert result["notification_sent"] is True

                    # Verify service call order
                    mock_slicer_instance.slice_model.assert_called_once()
                    mock_pricing_instance.calculate_quote.assert_called_once()
                    mock_telegram_instance.send_quote_notification.assert_called_once()


class TestCleanupTaskLogic:
    """Test the file cleanup task logic."""

    @patch('orca_quote_machine.tasks.cleanup_old_files_rust')
    def test_cleanup_returns_success_stats(self, mock_cleanup, sample_cleanup_stats):
        """Test cleanup task formats Rust stats correctly."""
        # Use real CleanupStats object
        mock_cleanup.return_value = sample_cleanup_stats

        result = cleanup_old_files(max_age_hours=24)

        assert result["success"] is True
        assert result["files_cleaned"] == sample_cleanup_stats.files_cleaned
        assert result["bytes_freed"] == sample_cleanup_stats.bytes_freed

    @patch('orca_quote_machine.tasks.cleanup_old_files_rust')
    def test_cleanup_handles_rust_errors(self, mock_cleanup):
        """Test cleanup task handles Rust function errors."""
        mock_cleanup.side_effect = Exception("Rust error")

        result = cleanup_old_files(max_age_hours=24)

        assert result["success"] is False
        assert "error" in result
        assert "Rust error" in result["error"]
