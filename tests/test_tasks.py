"""Tests for Celery background tasks."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from app.tasks import process_quote_request, run_processing_pipeline, send_failure_notification
from app.models.quote import MaterialType, SlicingResult


class TestProcessQuoteRequest:
    """Tests for the main quote processing task."""
    
    @patch("app.tasks.run_processing_pipeline")
    def test_process_quote_request_success(self, mock_pipeline):
        """Test successful quote processing."""
        # Mock the async pipeline
        mock_pipeline.return_value = {
            "request_id": "test-123",
            "total_cost": 25.50,
            "status": "completed"
        }
        
        quote_data = {
            "name": "John Doe",
            "mobile": "+6591234567",
            "material": "PLA",
            "filename": "test.stl"
        }
        
        result = process_quote_request.apply(
            args=["/path/to/file.stl", quote_data, "PLA"]
        )
        
        assert result.successful()
        assert result.result["status"] == "completed"
        assert result.result["total_cost"] == 25.50
    
    @patch("app.tasks.run_processing_pipeline")
    @patch("app.tasks.send_failure_notification")
    def test_process_quote_request_failure(self, mock_send_failure, mock_pipeline):
        """Test quote processing with failure."""
        # Mock pipeline failure
        mock_pipeline.side_effect = Exception("Slicing failed")
        
        quote_data = {
            "name": "John Doe",
            "mobile": "+6591234567", 
            "material": "PLA",
            "filename": "test.stl"
        }
        
        result = process_quote_request.apply(
            args=["/path/to/file.stl", quote_data, "PLA"]
        )
        
        assert result.failed()
        mock_send_failure.assert_called_once()
    
    @patch("app.tasks.validate_3d_model")
    @patch("app.tasks.run_processing_pipeline")
    def test_process_quote_request_invalid_file(self, mock_pipeline, mock_validate):
        """Test processing with invalid 3D model file."""
        # Mock Rust validation failure
        mock_validate.return_value = False
        
        quote_data = {
            "name": "John Doe",
            "mobile": "+6591234567",
            "material": "PLA", 
            "filename": "test.stl"
        }
        
        result = process_quote_request.apply(
            args=["/path/to/file.stl", quote_data, "PLA"]
        )
        
        assert result.failed()
        # Pipeline should not be called for invalid files
        mock_pipeline.assert_not_called()
    
    @patch("app.tasks.validate_3d_model", None)  # Simulate missing Rust module
    @patch("app.tasks.run_processing_pipeline")
    def test_process_quote_request_no_rust_validation(self, mock_pipeline):
        """Test processing when Rust validation is not available."""
        mock_pipeline.return_value = {"status": "completed"}
        
        quote_data = {
            "name": "John Doe",
            "mobile": "+6591234567",
            "material": "PLA",
            "filename": "test.stl"
        }
        
        result = process_quote_request.apply(
            args=["/path/to/file.stl", quote_data, "PLA"]
        )
        
        # Should succeed even without Rust validation
        assert result.successful()
        mock_pipeline.assert_called_once()


class TestRunProcessingPipeline:
    """Tests for the processing pipeline function."""
    
    @pytest.mark.asyncio
    @patch("app.tasks.OrcaSlicerService")
    @patch("app.tasks.PricingService") 
    @patch("app.tasks.TelegramService")
    async def test_run_processing_pipeline_success(
        self, 
        mock_telegram_service,
        mock_pricing_service, 
        mock_slicer_service
    ):
        """Test successful processing pipeline execution."""
        # Setup mocks
        mock_slicer = mock_slicer_service.return_value
        mock_slicer.slice_model = AsyncMock(return_value=SlicingResult(
            print_time_minutes=120,
            filament_weight_grams=25.5
        ))
        
        mock_pricing = mock_pricing_service.return_value
        mock_pricing.calculate_quote.return_value = {
            "material_cost": 12.75,
            "time_cost": 15.00,
            "total_cost": 30.53
        }
        
        mock_telegram = mock_telegram_service.return_value
        mock_telegram.send_quote_notification = AsyncMock(return_value=True)
        
        quote_data = {
            "name": "John Doe",
            "mobile": "+6591234567",
            "material": "PLA",
            "filename": "test.stl"
        }
        
        result = await run_processing_pipeline(
            "/path/to/test.stl",
            "test-request-id", 
            quote_data,
            MaterialType.PLA
        )
        
        # Verify result structure
        assert result["request_id"] == "test-request-id"
        assert result["status"] == "completed"
        assert result["total_cost"] == 30.53
        assert "slicing_result" in result
        assert "pricing_result" in result
        
        # Verify service calls
        mock_slicer.slice_model.assert_called_once_with("/path/to/test.stl", MaterialType.PLA)
        mock_pricing.calculate_quote.assert_called_once()
        mock_telegram.send_quote_notification.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("app.tasks.OrcaSlicerService")
    async def test_run_processing_pipeline_slicer_failure(self, mock_slicer_service):
        """Test pipeline failure during slicing."""
        mock_slicer = mock_slicer_service.return_value
        mock_slicer.slice_model = AsyncMock(side_effect=Exception("Slicing failed"))
        
        quote_data = {
            "name": "John Doe",
            "mobile": "+6591234567",
            "material": "PLA",
            "filename": "test.stl"
        }
        
        with pytest.raises(Exception, match="Slicing failed"):
            await run_processing_pipeline(
                "/path/to/test.stl",
                "test-request-id",
                quote_data,
                MaterialType.PLA
            )
    
    @pytest.mark.asyncio
    @patch("app.tasks.OrcaSlicerService")
    @patch("app.tasks.PricingService")
    async def test_run_processing_pipeline_pricing_failure(
        self,
        mock_pricing_service,
        mock_slicer_service
    ):
        """Test pipeline failure during pricing."""
        # Slicer succeeds
        mock_slicer = mock_slicer_service.return_value
        mock_slicer.slice_model = AsyncMock(return_value=SlicingResult(
            print_time_minutes=120,
            filament_weight_grams=25.5
        ))
        
        # Pricing fails
        mock_pricing = mock_pricing_service.return_value
        mock_pricing.calculate_quote.side_effect = Exception("Pricing failed")
        
        quote_data = {
            "name": "John Doe",
            "mobile": "+6591234567", 
            "material": "PLA",
            "filename": "test.stl"
        }
        
        with pytest.raises(Exception, match="Pricing failed"):
            await run_processing_pipeline(
                "/path/to/test.stl",
                "test-request-id",
                quote_data, 
                MaterialType.PLA
            )
    
    @pytest.mark.asyncio
    @patch("app.tasks.OrcaSlicerService")
    @patch("app.tasks.PricingService")
    @patch("app.tasks.TelegramService")
    async def test_run_processing_pipeline_telegram_failure(
        self,
        mock_telegram_service,
        mock_pricing_service,
        mock_slicer_service
    ):
        """Test pipeline with Telegram notification failure."""
        # Slicer and pricing succeed
        mock_slicer = mock_slicer_service.return_value
        mock_slicer.slice_model = AsyncMock(return_value=SlicingResult(
            print_time_minutes=120,
            filament_weight_grams=25.5
        ))
        
        mock_pricing = mock_pricing_service.return_value
        mock_pricing.calculate_quote.return_value = {
            "material_cost": 12.75,
            "time_cost": 15.00,
            "total_cost": 30.53
        }
        
        # Telegram fails
        mock_telegram = mock_telegram_service.return_value
        mock_telegram.send_quote_notification = AsyncMock(side_effect=Exception("Telegram failed"))
        
        quote_data = {
            "name": "John Doe",
            "mobile": "+6591234567",
            "material": "PLA", 
            "filename": "test.stl"
        }
        
        # Should still complete successfully even if Telegram fails
        result = await run_processing_pipeline(
            "/path/to/test.stl",
            "test-request-id",
            quote_data,
            MaterialType.PLA
        )
        
        assert result["status"] == "completed"
        assert result["total_cost"] == 30.53
        # Should indicate notification failure
        assert "notification_sent" in result
        assert result["notification_sent"] is False


class TestSendFailureNotification:
    """Tests for failure notification function."""
    
    @patch("app.tasks.TelegramService")
    def test_send_failure_notification_success(self, mock_telegram_service):
        """Test successful failure notification."""
        mock_telegram = mock_telegram_service.return_value
        mock_telegram.send_admin_notification.return_value = True
        
        result = send_failure_notification(
            "test-request-id",
            "John Doe",
            "test.stl",
            "Slicing failed"
        )
        
        assert result is True
        mock_telegram.send_admin_notification.assert_called_once()
    
    @patch("app.tasks.TelegramService")
    def test_send_failure_notification_telegram_failure(self, mock_telegram_service):
        """Test failure notification when Telegram fails."""
        mock_telegram = mock_telegram_service.return_value
        mock_telegram.send_admin_notification.side_effect = Exception("Telegram error")
        
        # Should not raise exception, just return False
        result = send_failure_notification(
            "test-request-id",
            "John Doe", 
            "test.stl",
            "Slicing failed"
        )
        
        assert result is False
    
    @patch("app.tasks.TelegramService", None)  # Simulate missing Telegram service
    def test_send_failure_notification_no_telegram(self):
        """Test failure notification when Telegram service unavailable."""
        result = send_failure_notification(
            "test-request-id",
            "John Doe",
            "test.stl", 
            "Slicing failed"
        )
        
        assert result is False