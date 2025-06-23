"""Telegram bot service for admin notifications."""

import httpx
from telegram import Bot
from telegram.error import TelegramError

from orca_quote_machine.core.config import Settings, get_settings
from orca_quote_machine.models.quote import TelegramMessage


class TelegramService:
    """Service for sending notifications via Telegram bot."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.bot: Bot | None = None

        if self.settings.telegram_bot_token:
            self.bot = Bot(token=self.settings.telegram_bot_token)

    async def send_quote_notification(self, message: TelegramMessage) -> bool:
        """
        Send quote notification to admin via Telegram.

        Args:
            message: Telegram message data

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.bot or not self.settings.telegram_admin_chat_id:
            print("Telegram bot not configured - notification not sent")
            return False

        try:
            formatted_message = message.format_message()

            await self.bot.send_message(
                chat_id=self.settings.telegram_admin_chat_id,
                text=formatted_message,
                parse_mode="HTML",
            )

            print(f"Quote notification sent for {message.quote_id}")
            return True

        except TelegramError as e:
            print(f"Failed to send Telegram notification: {e}")
            return False
        except httpx.HTTPError as e:
            print(f"HTTP error while sending Telegram notification: {e}")
            return False
        except (ConnectionError, TimeoutError) as e:
            print(f"Network error while sending Telegram notification: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error sending Telegram notification: {type(e).__name__}: {e}")
            return False

    async def send_error_notification(self, error_message: str, quote_id: str) -> bool:
        """Send error notification to admin."""
        if not self.bot or not self.settings.telegram_admin_chat_id:
            return False

        try:
            message = f"Quote Processing Error #{quote_id}\n\n{error_message}"

            await self.bot.send_message(
                chat_id=self.settings.telegram_admin_chat_id, text=message
            )

            return True

        except httpx.HTTPError as e:
            print(f"HTTP error while sending error notification: {e}")
            return False
        except (ConnectionError, TimeoutError) as e:
            print(f"Network error while sending error notification: {e}")
            return False
        except Exception as e:
            print(f"Failed to send error notification: {type(e).__name__}: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test Telegram bot connection."""
        if not self.bot:
            return False

        try:
            bot_info = await self.bot.get_me()
            print(f"Telegram bot connected: @{bot_info.username}")
            return True
        except httpx.HTTPError as e:
            print(f"HTTP error while testing Telegram connection: {e}")
            return False
        except (ConnectionError, TimeoutError) as e:
            print(f"Network error while testing Telegram connection: {e}")
            return False
        except Exception as e:
            print(f"Telegram bot connection failed: {type(e).__name__}: {e}")
            return False
