"""Application configuration settings."""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator
import os


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
    allowed_extensions: List[str] = [".stl", ".obj", ".step", ".stp"]
    
    # OrcaSlicer settings
    orcaslicer_cli_path: str = "/var/lib/flatpak/exports/bin/io.github.softfever.OrcaSlicer"
    slicer_timeout: int = 300  # 5 minutes
    slicer_profiles_dir: str = "config/slicer_profiles"
    
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
    telegram_bot_token: Optional[str] = None
    telegram_admin_chat_id: Optional[str] = None
    
    # Security
    secret_key: str  # Must be set via environment variable
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @validator("upload_dir")
    def create_upload_dir(cls, v):
        """Ensure upload directory exists."""
        os.makedirs(v, exist_ok=True)
        return v
    
    @validator("allowed_extensions")
    def normalize_extensions(cls, v):
        """Normalize file extensions to lowercase with dots."""
        return [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in v]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()