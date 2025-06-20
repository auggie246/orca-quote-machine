"""Unit tests for pricing service."""

import asyncio
import os
import tempfile

from _rust_core import CostBreakdown, SlicingResult, parse_slicer_output

from app.models.quote import MaterialType
from app.services.pricing import PricingService


class TestPricingService:
    """Tests for the PricingService class."""

    def test_calculate_quote(self):
        """Test that calculate_quote returns correct structure and applies business logic."""
        service = PricingService()

        # Create a real slicing result using the Rust parser
        async def create_slicing_result() -> SlicingResult:
            with tempfile.TemporaryDirectory() as temp_dir:
                gcode_file = os.path.join(temp_dir, 'test.gcode')
                with open(gcode_file, 'w') as f:  # noqa: ASYNC230  # Test file creation
                    f.write('; estimated printing time: 2h 0m\n; filament used: 100.0g\n')

                return await parse_slicer_output(temp_dir)

        slicing_result = asyncio.run(create_slicing_result())
        result = service.calculate_quote(slicing_result, MaterialType.PLA)

        # Test structure
        assert isinstance(result, CostBreakdown)
        assert hasattr(result, 'total_cost')
        assert hasattr(result, 'material_cost')
        assert hasattr(result, 'time_cost')

        # Test business logic
        assert result.total_cost >= 5.0  # Minimum price
        assert result.total_cost > 0

    def test_format_cost_summary(self):
        """Test that format_cost_summary returns a string."""
        service = PricingService()

        # Create a real CostBreakdown using the actual pricing logic
        async def create_slicing_result() -> SlicingResult:
            with tempfile.TemporaryDirectory() as temp_dir:
                gcode_file = os.path.join(temp_dir, 'test.gcode')
                with open(gcode_file, 'w') as f:  # noqa: ASYNC230  # Test file creation
                    f.write('; estimated printing time: 2h 0m\n; filament used: 100.0g\n')

                return await parse_slicer_output(temp_dir)

        slicing_result = asyncio.run(create_slicing_result())
        cost_breakdown = service.calculate_quote(slicing_result, MaterialType.PLA)

        result = service.format_cost_summary(cost_breakdown)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Cost Breakdown:" in result
