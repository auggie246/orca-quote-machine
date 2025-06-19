"""Unit tests for pricing service."""

from app.models.quote import MaterialType, SlicingResult
from app.services.pricing import PricingService


class TestPricingService:
    """Tests for the PricingService class."""

    def test_calculate_quote(self):
        """Test that calculate_quote returns correct structure and applies business logic."""
        service = PricingService()

        slicing_result = SlicingResult(
            print_time_minutes=120, filament_weight_grams=100.0
        )

        result = service.calculate_quote(slicing_result, MaterialType.PLA)

        # Test structure
        assert isinstance(result, dict)
        assert "total_cost" in result
        assert "material_cost" in result
        assert "time_cost" in result

        # Test business logic
        assert result["total_cost"] >= 5.0  # Minimum price
        assert result["total_cost"] > 0

    def test_format_cost_summary(self):
        """Test that format_cost_summary returns a string."""
        service = PricingService()

        cost_breakdown = {
            "filament_grams": 100.0,
            "filament_kg": 0.1,
            "price_per_kg": 25.0,
            "material_cost": 2.5,
            "print_time_hours": 2.5,
            "time_cost": 5.0,
            "subtotal": 8.25,
            "total_cost": 8.25,
            "markup_percentage": 10.0,
            "minimum_applied": False,
        }

        result = service.format_cost_summary(cost_breakdown)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Cost Breakdown:" in result
