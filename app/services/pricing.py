"""Pricing calculation service."""

from typing import Any

from app.core.config import get_settings
from app.models.quote import MaterialType, SlicingResult


class PricingService:
    """Service for calculating print costs."""

    def __init__(self: "PricingService") -> None:
        self.settings = get_settings()

    def calculate_quote(
        self: "PricingService", slicing_result: SlicingResult, material: MaterialType | None = None
    ) -> dict[str, Any]:
        """
        Calculate pricing for a 3D print job.

        Formula: (filament_kg * price_per_kg) * (print_time + 0.5h) * 1.1
        Minimum price: $5

        Args:
            slicing_result: Results from slicing operation
            material: Material type used

        Returns:
            Dictionary with cost breakdown
        """
        material = material or MaterialType.PLA

        # Get material price per kg
        price_per_kg = self.settings.material_prices.get(
            material.value, self.settings.default_price_per_kg
        )

        # Convert grams to kg
        filament_kg = slicing_result.filament_weight_grams / 1000.0

        # Convert minutes to hours and add additional time
        print_time_hours = (
            slicing_result.print_time_minutes / 60.0
        ) + self.settings.additional_time_hours

        # Calculate base costs
        material_cost = filament_kg * price_per_kg
        time_cost = (
            print_time_hours * price_per_kg
        )  # Using material price as hourly rate

        # Calculate total with multiplier
        subtotal = (material_cost + time_cost) * self.settings.price_multiplier

        # Apply minimum price
        total_cost = max(subtotal, self.settings.minimum_price)

        return {
            "material_type": material.value,
            "filament_kg": filament_kg,
            "filament_grams": slicing_result.filament_weight_grams,
            "print_time_hours": print_time_hours,
            "print_time_minutes": slicing_result.print_time_minutes,
            "price_per_kg": price_per_kg,
            "material_cost": material_cost,
            "time_cost": time_cost,
            "subtotal": subtotal,
            "total_cost": total_cost,
            "minimum_applied": total_cost == self.settings.minimum_price,
            "markup_percentage": (self.settings.price_multiplier - 1) * 100,
        }

    def format_cost_summary(self: "PricingService", cost_breakdown: dict) -> str:
        """Format cost breakdown for display."""
        material_line = (
            f"Material: {cost_breakdown['filament_grams']:.1f}g "
            f"({cost_breakdown['filament_kg']:.3f}kg) × "
            f"S${cost_breakdown['price_per_kg']:.2f}/kg = "
            f"S${cost_breakdown['material_cost']:.2f}"
        )
        time_line = (
            f"Time: {cost_breakdown['print_time_hours']:.1f}h × "
            f"S${cost_breakdown['price_per_kg']:.2f}/h = "
            f"S${cost_breakdown['time_cost']:.2f}"
        )
        return f"""Cost Breakdown:
{material_line}
{time_line}
Subtotal: S${cost_breakdown["subtotal"]:.2f} (includes {cost_breakdown["markup_percentage"]:.0f}% markup)
Total: S${cost_breakdown["total_cost"]:.2f}{"*" if cost_breakdown["minimum_applied"] else ""}
{"* Minimum price applied" if cost_breakdown["minimum_applied"] else ""}"""
