"""Integration tests for the complete quote workflow using real Rust functions."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _rust_core import (
    CostBreakdown,
    ModelInfo,
    SlicingResult,
    calculate_quote_rust,
    parse_slicer_output,
    validate_3d_model,
)

from app.models.quote import MaterialType
from app.services.pricing import PricingService
from app.services.slicer import OrcaSlicerService
from app.tasks import process_quote_request


class TestQuoteWorkflow:
    """Test the complete quote processing workflow with real Rust integration."""

    @pytest.fixture
    def valid_stl_path(self):
        """Path to a valid STL file fixture."""
        return str(Path(__file__).parent.parent / "fixtures" / "valid.stl")

    @pytest.fixture
    def invalid_stl_path(self):
        """Path to an invalid STL file fixture."""
        return str(Path(__file__).parent.parent / "fixtures" / "invalid.stl")

    @pytest.fixture
    def sample_gcode_dir(self):
        """Create a temporary directory with sample G-code output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            gcode_path = Path(temp_dir) / "output.gcode"
            gcode_path.write_text(
                "; estimated printing time: 2h 30m\n"
                "; filament used: 125.5g\n"
                "; layer_count: 150\n"
                "G92 E0\n"
            )
            yield temp_dir

    def test_rust_validate_valid_stl(self, valid_stl_path):
        """Test that Rust validation correctly identifies a valid STL file."""
        # Use real Rust function
        result = validate_3d_model(valid_stl_path)

        assert isinstance(result, ModelInfo)
        assert result.is_valid is True
        assert result.file_type == "stl"
        assert result.file_size > 0
        assert result.error_message is None

    def test_rust_validate_invalid_stl(self, invalid_stl_path):
        """Test that Rust validation correctly rejects an invalid STL file."""
        # Use real Rust function
        result = validate_3d_model(invalid_stl_path)

        assert isinstance(result, ModelInfo)
        assert result.is_valid is False
        assert result.file_type == "stl"
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_rust_parse_slicer_output(self, sample_gcode_dir):
        """Test that Rust G-code parser extracts correct information."""
        # Use real Rust async function
        result = await parse_slicer_output(sample_gcode_dir)

        assert isinstance(result, SlicingResult)
        assert result.print_time_minutes == 150  # 2h 30m
        assert result.filament_weight_grams == 125.5
        assert result.layer_count == 150

    def test_rust_calculate_quote(self):
        """Test that Rust pricing calculation works correctly."""
        # Use real Rust function
        result = calculate_quote_rust(
            print_time_minutes=120,
            filament_weight_grams=50.0,
            material_type="PLA",
            price_per_kg=25.0,
            additional_time_hours=0.5,
            price_multiplier=1.1,
            minimum_price=5.0
        )

        assert isinstance(result, CostBreakdown)
        assert result.material_type == "PLA"
        assert result.filament_grams == 50.0
        assert result.total_cost >= 5.0  # Minimum price
        assert result.print_time_minutes == 120

    @pytest.mark.asyncio
    async def test_slicer_service_with_mocked_cli(self, valid_stl_path, sample_gcode_dir):
        """Test OrcaSlicerService with mocked CLI but real Rust parsing."""
        service = OrcaSlicerService()

        # Mock the subprocess call to OrcaSlicer
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Configure mock process
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Success", b""))
            mock_subprocess.return_value = mock_process

            # Mock tempfile to use our sample gcode directory
            with patch('tempfile.TemporaryDirectory') as mock_tempdir:
                mock_tempdir.return_value.__enter__.return_value = Path(sample_gcode_dir).parent

                # Run the service - it will use real Rust parsing
                result = await service.slice_model(valid_stl_path, MaterialType.PLA)

                assert isinstance(result, SlicingResult)
                assert result.print_time_minutes == 150
                assert result.filament_weight_grams == 125.5

    def test_pricing_service_with_real_rust(self):
        """Test PricingService using real Rust calculations."""
        service = PricingService()

        # Create a real SlicingResult (as would come from parse_slicer_output)
        class MockSlicingResult:
            print_time_minutes = 120
            filament_weight_grams = 50.0

        slicing_result = MockSlicingResult()

        # This will call the real Rust calculate_quote_rust function
        result = service.calculate_quote(slicing_result, MaterialType.PLA)

        assert isinstance(result, CostBreakdown)
        assert result.total_cost >= 5.0
        assert result.material_type == "PLA"

    @pytest.mark.asyncio
    async def test_complete_quote_workflow(self, valid_stl_path):
        """Test the complete quote processing workflow with real Rust and mocked external services."""
        quote_data = {
            "name": "Test User",
            "mobile": "+1234567890",
            "material": "PLA",
            "color": "Red",
            "filename": "test.stl"
        }

        # Mock Celery task
        with patch('app.tasks.process_quote_request.delay') as mock_delay:
            mock_delay.return_value = MagicMock(id="test-task-id")

            # In a real scenario, we'd test the actual task execution
            # For now, test the task function directly
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                # Mock OrcaSlicer CLI
                mock_process = AsyncMock()
                mock_process.returncode = 0
                mock_process.communicate = AsyncMock(return_value=(b"Success", b""))
                mock_subprocess.return_value = mock_process

                # Mock Telegram notification
                with patch('app.services.telegram.TelegramService.send_quote_notification') as mock_telegram:
                    mock_telegram.return_value = asyncio.create_task(asyncio.coroutine(lambda: True)())

                    # Create temp gcode output
                    with tempfile.TemporaryDirectory() as temp_dir:
                        gcode_path = Path(temp_dir) / "output" / "output.gcode"
                        gcode_path.parent.mkdir()
                        gcode_path.write_text(
                            "; estimated printing time: 2h 0m\n"
                            "; filament used: 100.0g\n"
                        )

                        # Mock tempfile to use our directory
                        with patch('tempfile.TemporaryDirectory') as mock_tempdir:
                            mock_tempdir.return_value.__enter__.return_value = temp_dir

                            # Execute the task
                            result = process_quote_request(
                                file_path=valid_stl_path,
                                quote_data=quote_data,
                                material="PLA"
                            )

                            assert result["success"] is True
                            assert result["slicing_result"]["print_time_minutes"] == 120
                            assert result["slicing_result"]["filament_weight_grams"] == 100.0
                            assert result["cost_breakdown"]["total_cost"] >= 5.0
