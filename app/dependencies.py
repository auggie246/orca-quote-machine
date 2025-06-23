"""FastAPI dependency injection providers."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.pricing import PricingService
from app.services.slicer import OrcaSlicerService
from app.services.telegram import TelegramService


def get_slicer_service(
    settings: Annotated[Settings, Depends(get_settings)]
) -> OrcaSlicerService:
    """Get OrcaSlicerService instance."""
    return OrcaSlicerService(settings=settings)


def get_pricing_service(
    settings: Annotated[Settings, Depends(get_settings)]
) -> PricingService:
    """Get PricingService instance."""
    return PricingService(settings=settings)


def get_telegram_service(
    settings: Annotated[Settings, Depends(get_settings)]
) -> TelegramService:
    """Get TelegramService instance."""
    return TelegramService(settings=settings)
