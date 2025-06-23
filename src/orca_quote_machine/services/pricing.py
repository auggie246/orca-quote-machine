"""Pricing calculation service."""

from orca_quote_machine._rust_core import (
    CostBreakdown,
    SlicingResult,
    calculate_quote_rust,
)
from orca_quote_machine.core.config import Settings, get_settings
from orca_quote_machine.models.quote import MaterialType


class PricingService:
    """Service for calculating print costs."""

    def __init__(self: "PricingService", settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def calculate_quote(
        self: "PricingService",
        slicing_result: SlicingResult,
        material: MaterialType | None = None,
    ) -> CostBreakdown:
        """
        Calculate pricing for a 3D print job using high-performance Rust implementation.

        Formula: (filament_kg * price_per_kg) * (print_time + 0.5h) * 1.1
        Minimum price: $5

        Args:
            slicing_result: Results from slicing operation
            material: Material type used

        Returns:
            CostBreakdown object with pricing details
        """
        material = material or MaterialType.PLA

        # Get material price per kg
        price_per_kg = self.settings.material_prices.get(
            material.value, self.settings.default_price_per_kg
        )

        # Use Rust implementation for enhanced performance
        return calculate_quote_rust(
            slicing_result.print_time_minutes,
            slicing_result.filament_weight_grams,
            material.value,
            price_per_kg,
            self.settings.additional_time_hours,
            self.settings.price_multiplier,
            self.settings.minimum_price,
        )

    def format_cost_summary(
        self: "PricingService", cost_breakdown: CostBreakdown
    ) -> str:
        """Format cost breakdown for display."""
        material_line = (
            f"Material: {cost_breakdown.filament_grams:.1f}g "
            f"({cost_breakdown.filament_kg:.3f}kg) × "
            f"S${cost_breakdown.price_per_kg:.2f}/kg = "
            f"S${cost_breakdown.material_cost:.2f}"
        )
        time_line = (
            f"Time: {cost_breakdown.print_time_hours:.1f}h × "
            f"S${cost_breakdown.price_per_kg:.2f}/h = "
            f"S${cost_breakdown.time_cost:.2f}"
        )
        return f"""Cost Breakdown:
{material_line}
{time_line}
Subtotal: S${cost_breakdown.subtotal:.2f} (includes {cost_breakdown.markup_percentage:.0f}% markup)
Total: S${cost_breakdown.total_cost:.2f}{"*" if cost_breakdown.minimum_applied else ""}
{"* Minimum price applied" if cost_breakdown.minimum_applied else ""}"""
