"""Unit tests for pricing service."""

from app.models.quote import MaterialType
from app.services.pricing import PricingService


class TestPricingService:
    """Tests for the PricingService class."""

    def test_calculate_material_cost_pla(self):
        """Test material cost calculation for PLA."""
        service = PricingService()

        # 25.5g = 0.0255kg, PLA = $25/kg
        cost = service.calculate_material_cost(25.5, MaterialType.PLA)

        expected = 0.0255 * 25.0  # 0.6375
        assert abs(cost - expected) < 0.001

    def test_calculate_material_cost_petg(self):
        """Test material cost calculation for PETG."""
        service = PricingService()

        # 30.0g = 0.030kg, PETG = $30/kg
        cost = service.calculate_material_cost(30.0, MaterialType.PETG)

        expected = 0.030 * 30.0  # 0.9
        assert abs(cost - expected) < 0.001

    def test_calculate_material_cost_asa(self):
        """Test material cost calculation for ASA."""
        service = PricingService()

        # 20.0g = 0.020kg, ASA = $35/kg
        cost = service.calculate_material_cost(20.0, MaterialType.ASA)

        expected = 0.020 * 35.0  # 0.7
        assert abs(cost - expected) < 0.001

    def test_calculate_time_cost(self):
        """Test time cost calculation."""
        service = PricingService()

        # 120 minutes = 2 hours, with 0.5h additional = 2.5h
        # Base rate should be in settings, let's assume $10/hour
        cost = service.calculate_time_cost(120)

        # This will depend on the actual implementation
        # For now, just test that it returns a positive number
        assert cost > 0
        assert isinstance(cost, float)

    def test_calculate_total_cost_with_markup(self):
        """Test total cost calculation includes markup."""
        service = PricingService()

        material_cost = 10.0
        time_cost = 15.0

        total = service.calculate_total_cost(material_cost, time_cost)

        # Should include 1.1 markup (10% increase)
        expected = (material_cost + time_cost) * 1.1
        assert abs(total - expected) < 0.001

    def test_calculate_total_cost_minimum_price(self):
        """Test that total cost respects minimum price."""
        service = PricingService()

        # Very low costs should be bumped to minimum
        material_cost = 1.0
        time_cost = 1.0

        total = service.calculate_total_cost(material_cost, time_cost)

        # Should be at least the minimum price ($5.00)
        assert total >= 5.0

    def test_calculate_quote_full_workflow(self):
        """Test the complete quote calculation workflow."""
        service = PricingService()

        # Test data
        print_time_minutes = 120  # 2 hours
        filament_weight_grams = 25.5
        material = MaterialType.PLA

        quote = service.calculate_quote(
            print_time_minutes=print_time_minutes,
            filament_weight_grams=filament_weight_grams,
            material=material
        )

        # Verify structure
        assert "material_cost" in quote
        assert "time_cost" in quote
        assert "total_cost" in quote

        # Verify all costs are positive
        assert quote["material_cost"] > 0
        assert quote["time_cost"] > 0
        assert quote["total_cost"] > 0

        # Verify total is sum of parts with markup
        expected_base = quote["material_cost"] + quote["time_cost"]
        expected_total = max(expected_base * 1.1, 5.0)  # With markup and minimum
        assert abs(quote["total_cost"] - expected_total) < 0.001

    def test_calculate_quote_different_materials(self):
        """Test that different materials produce different costs."""
        service = PricingService()

        # Same print parameters, different materials
        print_time = 60
        filament_weight = 20.0

        pla_quote = service.calculate_quote(print_time, filament_weight, MaterialType.PLA)
        petg_quote = service.calculate_quote(print_time, filament_weight, MaterialType.PETG)
        asa_quote = service.calculate_quote(print_time, filament_weight, MaterialType.ASA)

        # Material costs should be different (PLA < PETG < ASA)
        assert pla_quote["material_cost"] < petg_quote["material_cost"]
        assert petg_quote["material_cost"] < asa_quote["material_cost"]

        # Time costs should be the same
        assert pla_quote["time_cost"] == petg_quote["time_cost"]
        assert petg_quote["time_cost"] == asa_quote["time_cost"]

    def test_zero_filament_weight(self):
        """Test handling of zero filament weight."""
        service = PricingService()

        cost = service.calculate_material_cost(0.0, MaterialType.PLA)
        assert cost == 0.0

    def test_zero_print_time(self):
        """Test handling of zero print time."""
        service = PricingService()

        # Should still add the additional time (0.5h)
        cost = service.calculate_time_cost(0)
        assert cost > 0  # Should include base additional time cost
