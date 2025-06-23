"""Quote-related data models."""

import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, computed_field, field_validator


class MaterialType(str, Enum):
    """Available material types."""

    PLA = "PLA"
    PETG = "PETG"
    ASA = "ASA"


class QuoteStatus(str, Enum):
    """Quote request status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class QuoteRequest(BaseModel):
    """Quote request from user."""

    name: str = Field(..., min_length=1, max_length=100)
    mobile: str = Field(..., min_length=8, max_length=20)
    material: MaterialType | None = None
    color: str | None = Field(None, max_length=50)
    filename: str = Field(..., min_length=1)

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls: type["QuoteRequest"], v: str) -> str:
        """Validate mobile number format."""
        # Remove spaces and common separators
        clean_mobile = re.sub(r"[\s\-\(\)\.]+", "", v)

        # Check if it's a valid phone number (basic validation)
        if not re.match(r"^\+?[\d]{8,15}$", clean_mobile):
            raise ValueError("Invalid mobile number format")

        return clean_mobile

    @field_validator("name")
    @classmethod
    def validate_name(cls: type["QuoteRequest"], v: str) -> str:
        """Validate name contains only allowed characters."""
        # Check if empty after stripping
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be empty")

        # Reject names with numbers or most special characters
        # Allow letters (including Unicode), spaces, hyphens, dots, apostrophes
        if re.search(r"[\d@#$%^&*()+=\[\]{}|\\:;\"<>?/~`]", stripped):
            raise ValueError("Name contains invalid characters")
        return stripped


class SlicingResult(BaseModel):
    """Results from OrcaSlicer."""

    print_time_minutes: int = Field(..., ge=0)
    filament_weight_grams: float = Field(..., ge=0)
    layer_count: int | None = None
    estimated_cost: float | None = None


class QuoteResponse(BaseModel):
    """Complete quote response."""

    request_id: str
    name: str
    mobile: str
    material: str | None
    color: str | None
    filename: str

    # Slicing results
    print_time_minutes: int
    filament_weight_grams: float

    # Pricing
    material_cost: float
    time_cost: float
    total_cost: float

    # Metadata
    status: QuoteStatus
    created_at: datetime
    processed_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def print_time_hours(self: "QuoteResponse") -> float:
        """Calculate hours from minutes."""
        return self.print_time_minutes / 60.0


class TelegramMessage(BaseModel):
    """Telegram message data."""

    quote_id: str
    customer_name: str
    customer_mobile: str
    material: str | None
    color: str | None
    filename: str
    print_time: str
    filament_weight: str
    total_cost: float

    def format_message(self: "TelegramMessage") -> str:
        """Format message for Telegram."""
        material_display = self.material or "PLA (default)"
        color_info = f" - {self.color}" if self.color else ""

        return f"""New Quote Request #{self.quote_id}

Customer: {self.customer_name}
WhatsApp: {self.customer_mobile}
File: {self.filename}
Material: {material_display}{color_info}

Print Time: {self.print_time}
Filament: {self.filament_weight}
Total Cost: S${self.total_cost:.2f}

Reply to this message to contact the customer directly."""
