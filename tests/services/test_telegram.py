"""Unit tests for Telegram service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.quote import TelegramMessage
from app.services.telegram import TelegramService


class TestTelegramService:
    """Tests for the TelegramService class."""

    def test_init_with_config(self) -> None:
        """Test TelegramService initialization with valid config."""
        with patch("app.services.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = "test-token"
            mock_settings.return_value.telegram_admin_chat_id = "123456789"

            service = TelegramService()

            assert service.bot_token == "test-token"
            assert service.admin_chat_id == "123456789"
            assert service.enabled is True

    def test_init_without_config(self) -> None:
        """Test TelegramService initialization without config."""
        with patch("app.services.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = None
            mock_settings.return_value.telegram_admin_chat_id = None

            service = TelegramService()

            assert service.bot_token is None
            assert service.admin_chat_id is None
            assert service.enabled is False

    @pytest.mark.asyncio
    @patch("app.services.telegram.Application")
    async def test_send_quote_notification_success(self, mock_application: MagicMock) -> None:
        """Test successful quote notification sending."""
        # Mock Telegram bot
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        mock_app_instance = MagicMock()
        mock_app_instance.bot = mock_bot
        mock_application.builder.return_value.token.return_value.build.return_value = mock_app_instance

        with patch("app.services.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = "test-token"
            mock_settings.return_value.telegram_admin_chat_id = "123456789"

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
                total_cost=30.25
            )

            result = await service.send_quote_notification(message)

            assert result is True
            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_quote_notification_disabled(self) -> None:
        """Test quote notification when service is disabled."""
        with patch("app.services.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = None
            mock_settings.return_value.telegram_admin_chat_id = None

            service = TelegramService()

            message = TelegramMessage(
                quote_id="test-123",
                customer_name="John Doe",
                customer_mobile="+6591234567",
                material="PLA",
                color=None,
                filename="test.stl",
                print_time="2h 30m",
                filament_weight="25.5g",
                total_cost=30.25
            )

            result = await service.send_quote_notification(message)

            assert result is False

    @pytest.mark.asyncio
    @patch("app.services.telegram.Application")
    async def test_send_quote_notification_failure(self, mock_application: MagicMock) -> None:
        """Test quote notification failure."""
        # Mock Telegram bot failure
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=Exception("Network error"))
        mock_app_instance = MagicMock()
        mock_app_instance.bot = mock_bot
        mock_application.builder.return_value.token.return_value.build.return_value = mock_app_instance

        with patch("app.services.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = "test-token"
            mock_settings.return_value.telegram_admin_chat_id = "123456789"

            service = TelegramService()

            message = TelegramMessage(
                quote_id="test-123",
                customer_name="John Doe",
                customer_mobile="+6591234567",
                material=None,
                color=None,
                filename="test.stl",
                print_time="1h 15m",
                filament_weight="20.0g",
                total_cost=22.50
            )

            result = await service.send_quote_notification(message)

            assert result is False

    @pytest.mark.asyncio
    @patch("app.services.telegram.Application")
    async def test_send_admin_notification_success(self, mock_application: MagicMock) -> None:
        """Test successful admin notification sending."""
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        mock_app_instance = MagicMock()
        mock_app_instance.bot = mock_bot
        mock_application.builder.return_value.token.return_value.build.return_value = mock_app_instance

        with patch("app.services.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = "test-token"
            mock_settings.return_value.telegram_admin_chat_id = "123456789"

            service = TelegramService()

            result = await service.send_admin_notification(
                "Processing Error",
                "Failed to process quote #test-123 for John Doe"
            )

            assert result is True
            mock_bot.send_message.assert_called_once()

            # Check that the message was formatted correctly
            call_args = mock_bot.send_message.call_args
            assert call_args[1]["chat_id"] == "123456789"
            assert "Processing Error" in call_args[1]["text"]
            assert "Failed to process quote" in call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_send_admin_notification_disabled(self) -> None:
        """Test admin notification when service is disabled."""
        with patch("app.services.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = None
            mock_settings.return_value.telegram_admin_chat_id = None

            service = TelegramService()

            result = await service.send_admin_notification(
                "Test Error",
                "Test message"
            )

            assert result is False

    def test_format_quote_notification_with_all_fields(self) -> None:
        """Test formatting quote notification with all fields."""
        service = TelegramService()

        message = TelegramMessage(
            quote_id="test-123",
            customer_name="John Doe",
            customer_mobile="+6591234567",
            material="PETG",
            color="Blue",
            filename="complex_model.stl",
            print_time="3h 45m",
            filament_weight="42.8g",
            total_cost=45.75
        )

        formatted = service._format_quote_notification(message)

        assert "New Quote Request #test-123" in formatted
        assert "Customer: John Doe" in formatted
        assert "WhatsApp: +6591234567" in formatted
        assert "File: complex_model.stl" in formatted
        assert "Material: PETG - Blue" in formatted
        assert "Print Time: 3h 45m" in formatted
        assert "Filament: 42.8g" in formatted
        assert "Total Cost: S$45.75" in formatted
        assert "Reply to this message" in formatted

    def test_format_quote_notification_minimal_fields(self) -> None:
        """Test formatting quote notification with minimal fields."""
        service = TelegramService()

        message = TelegramMessage(
            quote_id="test-456",
            customer_name="Jane Smith",
            customer_mobile="98765432",
            material=None,
            color=None,
            filename="simple.stl",
            print_time="1h 30m",
            filament_weight="18.2g",
            total_cost=20.00
        )

        formatted = service._format_quote_notification(message)

        assert "New Quote Request #test-456" in formatted
        assert "Customer: Jane Smith" in formatted
        assert "WhatsApp: 98765432" in formatted
        assert "File: simple.stl" in formatted
        assert "Material: PLA (default)" in formatted  # Default when None
        assert "Print Time: 1h 30m" in formatted
        assert "Filament: 18.2g" in formatted
        assert "Total Cost: S$20.00" in formatted

        # Should not contain color info when None
        assert " - " not in formatted.split("Material:")[1].split("\n")[0]

    def test_format_admin_notification(self) -> None:
        """Test formatting admin notification."""
        service = TelegramService()

        formatted = service._format_admin_notification(
            "Processing Error",
            "OrcaSlicer failed to slice model.stl for customer John Doe"
        )

        assert "🚨 Processing Error" in formatted
        assert "OrcaSlicer failed to slice" in formatted
        assert timestamp_pattern_present(formatted)  # Should include timestamp


def timestamp_pattern_present(text: str) -> bool:
    """Helper to check if timestamp pattern is present."""
    import re
    # Look for ISO format timestamp pattern
    pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
    return bool(re.search(pattern, text))
