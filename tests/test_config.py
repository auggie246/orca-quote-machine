"""Tests for configuration settings."""

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


class TestSettings:
    """Tests for the Settings configuration class."""

    def test_default_settings(self):
        """Test default settings values."""
        # Set required environment variable
        os.environ["SECRET_KEY"] = "test-secret-key"

        try:
            settings = Settings()

            # Test default values
            assert settings.app_name == "OrcaSlicer Quotation Machine"
            assert settings.debug is False
            assert settings.host == "0.0.0.0"
            assert settings.port == 8000
            assert settings.max_file_size == 100 * 1024 * 1024  # 100MB
            assert settings.upload_dir == "uploads"
            assert ".stl" in settings.allowed_extensions
            assert ".obj" in settings.allowed_extensions

        finally:
            del os.environ["SECRET_KEY"]

    def test_secret_key_required(self):
        """Test that SECRET_KEY is required."""
        # Ensure SECRET_KEY is not set
        if "SECRET_KEY" in os.environ:
            del os.environ["SECRET_KEY"]
        
        # Clear any cached settings
        get_settings.cache_clear()

        with pytest.raises(ValidationError):
            Settings(_env_file=None)  # Don't load .env file

    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        env_vars = {
            "SECRET_KEY": "test-secret-key",
            "APP_NAME": "Custom App Name",
            "DEBUG": "true",
            "HOST": "127.0.0.1",
            "PORT": "9000",
            "MAX_FILE_SIZE": "50000000",  # 50MB
            "UPLOAD_DIR": "custom_uploads"
        }

        # Set environment variables
        for key, value in env_vars.items():
            os.environ[key] = value

        try:
            settings = Settings()

            assert settings.app_name == "Custom App Name"
            assert settings.debug is True
            assert settings.host == "127.0.0.1"
            assert settings.port == 9000
            assert settings.max_file_size == 50000000
            assert settings.upload_dir == "custom_uploads"

        finally:
            # Clean up environment variables
            for key in env_vars:
                if key in os.environ:
                    del os.environ[key]

    def test_allowed_extensions_normalization(self):
        """Test that file extensions are normalized."""
        os.environ["SECRET_KEY"] = "test-secret-key"
        os.environ["ALLOWED_EXTENSIONS"] = '["STL", "obj", ".step", "STP"]'

        try:
            settings = Settings()

            # All extensions should be lowercase with dots
            expected = [".stl", ".obj", ".step", ".stp"]
            assert settings.allowed_extensions == expected

        finally:
            del os.environ["SECRET_KEY"]
            del os.environ["ALLOWED_EXTENSIONS"]

    def test_upload_dir_validation(self):
        """Test that upload directory path is validated."""
        with tempfile.TemporaryDirectory() as temp_dir:
            upload_path = Path(temp_dir) / "test_uploads"

            os.environ["SECRET_KEY"] = "test-secret-key"
            os.environ["UPLOAD_DIR"] = str(upload_path)

            try:
                settings = Settings()

                # Directory path should be set correctly
                assert settings.upload_dir == str(upload_path)

            finally:
                del os.environ["SECRET_KEY"]
                del os.environ["UPLOAD_DIR"]

    def test_material_prices_from_env(self):
        """Test material prices loaded from environment/config."""
        os.environ["SECRET_KEY"] = "test-secret-key"

        try:
            settings = Settings()

            # Check that material prices are loaded correctly from .env
            assert settings.material_prices["PLA"] == 20.0
            assert settings.material_prices["PETG"] == 20.0
            assert settings.material_prices["ASA"] == 30.0

        finally:
            del os.environ["SECRET_KEY"]

    def test_pricing_settings(self):
        """Test pricing-related settings."""
        os.environ["SECRET_KEY"] = "test-secret-key"

        try:
            settings = Settings()

            assert settings.default_price_per_kg == 25.0
            assert settings.price_multiplier == 1.1
            assert settings.minimum_price == 5.0
            assert settings.additional_time_hours == 0.5

        finally:
            del os.environ["SECRET_KEY"]

    def test_redis_celery_settings(self):
        """Test Redis and Celery settings."""
        os.environ["SECRET_KEY"] = "test-secret-key"

        try:
            settings = Settings()

            assert settings.redis_url == "redis://localhost:6379/0"
            assert settings.celery_broker_url == "redis://localhost:6379/0"
            assert settings.celery_result_backend == "redis://localhost:6379/0"

        finally:
            del os.environ["SECRET_KEY"]

    def test_telegram_settings_from_env(self):
        """Test that Telegram settings are loaded from environment."""
        os.environ["SECRET_KEY"] = "test-secret-key"

        try:
            settings = Settings()

            # Should load values from .env file
            assert settings.telegram_bot_token == "8075425172:AAGGcWdEjGccBGBbqiFNtu_qMN8fqBV_u9A"
            assert settings.telegram_admin_chat_id == "134137944"

        finally:
            del os.environ["SECRET_KEY"]

    def test_telegram_settings_configured(self):
        """Test Telegram settings when configured."""
        env_vars = {
            "SECRET_KEY": "test-secret-key",
            "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234567890",
            "TELEGRAM_ADMIN_CHAT_ID": "987654321"
        }

        for key, value in env_vars.items():
            os.environ[key] = value

        try:
            settings = Settings()

            assert settings.telegram_bot_token == "123456:ABC-DEF1234567890"
            assert settings.telegram_admin_chat_id == "987654321"

        finally:
            for key in env_vars:
                if key in os.environ:
                    del os.environ[key]

    def test_orcaslicer_settings(self):
        """Test OrcaSlicer-related settings."""
        os.environ["SECRET_KEY"] = "test-secret-key"

        try:
            settings = Settings()

            assert settings.orcaslicer_cli_path == "/var/lib/flatpak/exports/bin/io.github.softfever.OrcaSlicer"
            assert settings.slicer_timeout == 300  # 5 minutes
            assert str(settings.slicer_profiles.base_dir) == "config/slicer_profiles"

        finally:
            del os.environ["SECRET_KEY"]

    def test_case_insensitive_env_vars(self):
        """Test that environment variables are case insensitive."""
        env_vars = {
            "secret_key": "test-secret-key",  # lowercase
            "app_name": "Test App",
            "debug": "true"
        }

        for key, value in env_vars.items():
            os.environ[key] = value

        try:
            settings = Settings()

            assert settings.secret_key == "test-secret-key"
            assert settings.app_name == "Test App"
            assert settings.debug is True

        finally:
            for key in env_vars:
                if key in os.environ:
                    del os.environ[key]


class TestGetSettings:
    """Tests for the get_settings function."""

    def test_get_settings_caching(self):
        """Test that get_settings returns cached instance."""
        os.environ["SECRET_KEY"] = "test-secret-key"

        try:
            settings1 = get_settings()
            settings2 = get_settings()

            # Should be the same instance due to caching
            assert settings1 is settings2

        finally:
            del os.environ["SECRET_KEY"]

    def test_get_settings_returns_settings_instance(self):
        """Test that get_settings returns Settings instance."""
        os.environ["SECRET_KEY"] = "test-secret-key"

        try:
            settings = get_settings()

            assert isinstance(settings, Settings)
            assert hasattr(settings, "app_name")
            assert hasattr(settings, "secret_key")

        finally:
            del os.environ["SECRET_KEY"]
