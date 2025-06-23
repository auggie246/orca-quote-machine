"""Unit tests for telegram service."""

import pytest

from app.models.quote import TelegramMessage
from app.services.telegram import TelegramService


class TestTelegramService:
    """Tests for the TelegramService class."""

    def test_init(self):
        """Test TelegramService initialization."""
        service = TelegramService()

        # Should initialize without error
        assert hasattr(service, "settings")
        assert hasattr(service, "bot")

    @pytest.mark.asyncio
    async def test_send_quote_notification(self):
        """Test send_quote_notification returns boolean."""
        service = TelegramService()

        message = TelegramMessage(
            quote_id="test-123",
            customer_name="John Doe",
            customer_mobile="+6591234567",
            material="PLA",
            color="Red",
            filename="test.stl",
            print_time="2h 30m",
            filament_weight="25.5g",
            total_cost=30.25,
        )

        result = await service.send_quote_notification(message)

        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_send_error_notification(self):
        """Test send_error_notification returns boolean."""
        service = TelegramService()

        result = await service.send_error_notification("Test error", "test-123")

        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_test_connection(self):
        """Test test_connection returns boolean."""
        service = TelegramService()

        result = await service.test_connection()

        assert isinstance(result, bool)
