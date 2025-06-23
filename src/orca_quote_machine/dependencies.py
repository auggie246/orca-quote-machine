"""FastAPI dependency injection providers."""

from typing import Annotated

from fastapi import Depends

from orca_quote_machine.core.config import Settings, get_settings
from orca_quote_machine.services.pricing import PricingService
from orca_quote_machine.services.slicer import OrcaSlicerService
from orca_quote_machine.services.telegram import TelegramService


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
