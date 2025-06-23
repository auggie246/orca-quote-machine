"""Application configuration settings."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SlicerProfileSettings(BaseModel):
    """Configuration for default slicer profiles."""

    base_dir: Path = Path("config/slicer_profiles")

    # Default machine and process profiles
    machine: str = "RatRig V-Core 3 400 0.5 nozzle.json"
    process: str = "0.2mm RatRig 0.5mm nozzle.json"

    # Per-material filament profiles for official materials
    # These act as overrides for the default file-based convention
    filament_pla: str = "ALT TABL MATTE PLA PEI.json"
    filament_petg: str = "Alt Tab PETG.json"
    filament_asa: str = "fusrock ASA.json"

    @model_validator(mode="after")
    def validate_profiles_exist(self) -> "SlicerProfileSettings":
        """Validate that all configured profile files exist.

        Skip validation in test environments or when SKIP_PROFILE_VALIDATION is set.
        """
        # Skip validation in test environments
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SKIP_PROFILE_VALIDATION"):
            return self

        profiles_to_check = [
            ("machine", self.machine),
            ("process", self.process),
            ("filament", self.filament_pla),
            ("filament", self.filament_petg),
            ("filament", self.filament_asa),
        ]
        for profile_type, filename in profiles_to_check:
            profile_path = self.base_dir / profile_type / filename
            if not profile_path.exists():
                raise ValueError(
                    f"{profile_type.capitalize()} profile not found at: {profile_path}"
                )
        return self


class Settings(BaseSettings):
    """Application settings."""

    # App settings
    app_name: str = "OrcaSlicer Quotation Machine"
    debug: bool = False

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000

    # File upload settings
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    upload_dir: str = "uploads"
    allowed_extensions: list[str] = [".stl", ".obj", ".step", ".stp"]

    # OrcaSlicer settings
    orcaslicer_cli_path: str = (
        "/var/lib/flatpak/exports/bin/io.github.softfever.OrcaSlicer"
    )
    slicer_timeout: int = 300  # 5 minutes
    slicer_profiles: SlicerProfileSettings | None = None

    # Pricing settings
    default_price_per_kg: float = 25.0  # S$25/kg for PLA
    price_multiplier: float = 1.1  # 10% markup
    minimum_price: float = 5.0  # S$5 minimum
    additional_time_hours: float = 0.5  # Add 30 minutes to print time

    # Material pricing (per kg)
    material_prices: dict = {
        "PLA": 25.0,
        "PETG": 30.0,
        "ASA": 35.0,
    }

    # Redis/Celery settings
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Telegram bot settings
    telegram_bot_token: str | None = None
    telegram_admin_chat_id: str | None = None

    # Security
    secret_key: str  # Must be set via environment variable

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    @model_validator(mode="after")
    def initialize_slicer_profiles(self) -> "Settings":
        """Initialize slicer profiles if not already set."""
        if self.slicer_profiles is None:
            self.slicer_profiles = SlicerProfileSettings()
        return self

    @field_validator("upload_dir")
    @classmethod
    def validate_upload_dir(cls: type["Settings"], dir_path: str) -> str:
        """Validate the upload directory path.

        Note: Directory creation is handled during application startup,
        not during configuration validation.
        """
        return dir_path

    @field_validator("allowed_extensions")
    @classmethod
    def normalize_extensions(cls: type["Settings"], extensions: list[str]) -> list[str]:
        """Normalize file extensions to lowercase with dots."""
        return [
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in extensions
        ]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
