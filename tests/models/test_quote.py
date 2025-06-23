"""Unit tests for Pydantic quote models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from orca_quote_machine.models.quote import (
    MaterialType,
    QuoteRequest,
    QuoteResponse,
    QuoteStatus,
    SlicingResult,
    TelegramMessage,
)


class TestMaterialType:
    """Tests for MaterialType enum."""

    def test_material_type_values(self):
        """Test that MaterialType has expected values."""
        assert MaterialType.PLA == "PLA"
        assert MaterialType.PETG == "PETG"
        assert MaterialType.ASA == "ASA"

        # Test that all values are strings
        for material in MaterialType:
            assert isinstance(material.value, str)


class TestQuoteStatus:
    """Tests for QuoteStatus enum."""

    def test_quote_status_values(self):
        """Test that QuoteStatus has expected values."""
        assert QuoteStatus.PENDING == "pending"
        assert QuoteStatus.PROCESSING == "processing"
        assert QuoteStatus.COMPLETED == "completed"
        assert QuoteStatus.FAILED == "failed"


class TestQuoteRequest:
    """Tests for QuoteRequest model validation."""

    def test_valid_quote_request(self):
        """Test creating a valid quote request."""
        data = {
            "name": "John Doe",
            "mobile": "+6591234567",
            "material": MaterialType.PLA,
            "color": "Red",
            "filename": "test.stl",
        }

        quote = QuoteRequest(**data)

        assert quote.name == "John Doe"
        assert quote.mobile == "+6591234567"
        assert quote.material == MaterialType.PLA
        assert quote.color == "Red"
        assert quote.filename == "test.stl"

    def test_quote_request_optional_fields(self):
        """Test quote request with optional fields."""
        data = {"name": "Jane Doe", "mobile": "91234567", "filename": "model.stl"}

        quote = QuoteRequest(**data)

        assert quote.name == "Jane Doe"
        assert quote.mobile == "91234567"
        assert quote.material is None
        assert quote.color is None
        assert quote.filename == "model.stl"

    def test_name_validation_valid(self):
        """Test valid name validation."""
        valid_names = [
            "John Doe",
            "Mary-Jane",
            "O'Connor",
            "Jean-Luc",
            "Dr. Smith",
            "李明",
        ]

        for name in valid_names:
            data = {"name": name, "mobile": "+6591234567", "filename": "test.stl"}
            quote = QuoteRequest(**data)
            assert quote.name == name.strip()

    def test_name_validation_invalid(self):
        """Test invalid name validation."""
        invalid_names = [
            "",  # Empty
            "   ",  # Only whitespace
            "A" * 101,  # Too long
            "John123",  # Contains numbers
            "John@Doe",  # Contains special chars
        ]

        for name in invalid_names:
            data = {"name": name, "mobile": "+6591234567", "filename": "test.stl"}
            with pytest.raises(ValidationError):
                QuoteRequest(**data)

    def test_mobile_validation_valid(self):
        """Test valid mobile number validation."""
        valid_mobiles = [
            "+6591234567",
            "91234567",
            "+1-555-123-4567",
            "+44 20 7946 0958",
            "(555) 123-4567",
            "555.123.4567",
        ]

        for mobile in valid_mobiles:
            data = {"name": "John Doe", "mobile": mobile, "filename": "test.stl"}
            quote = QuoteRequest(**data)
            # Check that formatting is cleaned up
            cleaned_mobile = (
                quote.mobile.replace("+", "").replace("-", "").replace(" ", "")
            )
            cleaned_mobile = (
                cleaned_mobile.replace("(", "").replace(")", "").replace(".", "")
            )
            assert cleaned_mobile.isdigit()

    def test_mobile_validation_invalid(self):
        """Test invalid mobile number validation."""
        invalid_mobiles = [
            "",  # Empty
            "123",  # Too short
            "abcdefghij",  # Not numeric
            "++6591234567",  # Multiple plus signs
            "1234567890123456",  # Too long
        ]

        for mobile in invalid_mobiles:
            data = {"name": "John Doe", "mobile": mobile, "filename": "test.stl"}
            with pytest.raises(ValidationError):
                QuoteRequest(**data)

    def test_filename_validation(self):
        """Test filename validation."""
        data = {
            "name": "John Doe",
            "mobile": "+6591234567",
            "filename": "",  # Empty filename
        }

        with pytest.raises(ValidationError):
            QuoteRequest(**data)


class TestSlicingResult:
    """Tests for SlicingResult model."""

    def test_valid_slicing_result(self):
        """Test creating a valid slicing result."""
        data = {
            "print_time_minutes": 120,
            "filament_weight_grams": 25.5,
            "layer_count": 200,
            "estimated_cost": 30.25,
        }

        result = SlicingResult(**data)

        assert result.print_time_minutes == 120
        assert result.filament_weight_grams == 25.5
        assert result.layer_count == 200
        assert result.estimated_cost == 30.25

    def test_slicing_result_optional_fields(self):
        """Test slicing result with only required fields."""
        data = {"print_time_minutes": 60, "filament_weight_grams": 15.0}

        result = SlicingResult(**data)

        assert result.print_time_minutes == 60
        assert result.filament_weight_grams == 15.0
        assert result.layer_count is None
        assert result.estimated_cost is None

    def test_slicing_result_negative_values(self):
        """Test that negative values are rejected."""
        with pytest.raises(ValidationError):
            SlicingResult(print_time_minutes=-1, filament_weight_grams=20.0)

        with pytest.raises(ValidationError):
            SlicingResult(print_time_minutes=60, filament_weight_grams=-5.0)


class TestQuoteResponse:
    """Tests for QuoteResponse model."""

    def test_valid_quote_response(self):
        """Test creating a valid quote response."""
        now = datetime.now()
        data = {
            "request_id": "test-123",
            "name": "John Doe",
            "mobile": "+6591234567",
            "material": "PLA",
            "color": "Red",
            "filename": "test.stl",
            "print_time_hours": 2.0,
            "print_time_minutes": 120,
            "filament_weight_grams": 25.5,
            "material_cost": 12.75,
            "time_cost": 15.00,
            "total_cost": 30.53,
            "status": QuoteStatus.COMPLETED,
            "created_at": now,
            "processed_at": now,
        }

        response = QuoteResponse(**data)

        assert response.request_id == "test-123"
        assert response.name == "John Doe"
        assert response.total_cost == 30.53
        assert response.status == QuoteStatus.COMPLETED

    def test_print_time_hours_calculation(self):
        """Test that print_time_hours is calculated from minutes."""
        data = {
            "request_id": "test-123",
            "name": "John Doe",
            "mobile": "+6591234567",
            "material": "PLA",
            "color": None,
            "filename": "test.stl",
            "print_time_minutes": 150,  # 2.5 hours
            "filament_weight_grams": 25.5,
            "material_cost": 12.75,
            "time_cost": 15.00,
            "total_cost": 30.53,
            "status": QuoteStatus.COMPLETED,
            "created_at": datetime.now(),
        }

        response = QuoteResponse(**data)

        # Should calculate hours from minutes
        assert response.print_time_hours == 2.5


class TestTelegramMessage:
    """Tests for TelegramMessage model."""

    def test_valid_telegram_message(self):
        """Test creating a valid telegram message."""
        data = {
            "quote_id": "test-123",
            "customer_name": "John Doe",
            "customer_mobile": "+6591234567",
            "material": "PLA",
            "color": "Red",
            "filename": "test.stl",
            "print_time": "2h 30m",
            "filament_weight": "25.5g",
            "total_cost": 30.25,
        }

        message = TelegramMessage(**data)

        assert message.quote_id == "test-123"
        assert message.customer_name == "John Doe"
        assert message.total_cost == 30.25

    def test_format_message_with_material_and_color(self):
        """Test message formatting with material and color."""
        data = {
            "quote_id": "test-123",
            "customer_name": "John Doe",
            "customer_mobile": "+6591234567",
            "material": "PLA",
            "color": "Red",
            "filename": "test.stl",
            "print_time": "2h 30m",
            "filament_weight": "25.5g",
            "total_cost": 30.25,
        }

        message = TelegramMessage(**data)
        formatted = message.format_message()

        assert "New Quote Request #test-123" in formatted
        assert "Customer: John Doe" in formatted
        assert "WhatsApp: +6591234567" in formatted
        assert "File: test.stl" in formatted
        assert "Material: PLA - Red" in formatted
        assert "Print Time: 2h 30m" in formatted
        assert "Filament: 25.5g" in formatted
        assert "Total Cost: S$30.25" in formatted
        assert "Reply to this message" in formatted

    def test_format_message_without_material_and_color(self):
        """Test message formatting without optional fields."""
        data = {
            "quote_id": "test-456",
            "customer_name": "Jane Doe",
            "customer_mobile": "+6598765432",
            "material": None,
            "color": None,
            "filename": "model.stl",
            "print_time": "1h 15m",
            "filament_weight": "18.2g",
            "total_cost": 22.50,
        }

        message = TelegramMessage(**data)
        formatted = message.format_message()

        assert "New Quote Request #test-456" in formatted
        assert "Material: PLA (default)" in formatted
        # Should not contain color info when color is None
        assert " - " not in formatted.split("Material:")[1].split("\n")[0]
