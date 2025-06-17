"""Quote-related data models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, validator
import re


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
    material: Optional[MaterialType] = None
    color: Optional[str] = Field(None, max_length=50)
    filename: str = Field(..., min_length=1)
    
    @validator("mobile")
    def validate_mobile(cls, v):
        """Validate mobile number format."""
        # Remove spaces and common separators
        clean_mobile = re.sub(r'[\s\-\(\)]+', '', v)
        
        # Check if it's a valid phone number (basic validation)
        if not re.match(r'^\+?[\d]{8,15}$', clean_mobile):
            raise ValueError("Invalid mobile number format")
        
        return clean_mobile
    
    @validator("name")
    def validate_name(cls, v):
        """Validate name contains only allowed characters."""
        if not re.match(r'^[a-zA-Z\s\-\.]+$', v.strip()):
            raise ValueError("Name contains invalid characters")
        return v.strip()


class SlicingResult(BaseModel):
    """Results from OrcaSlicer."""
    
    print_time_minutes: int = Field(..., ge=0)
    filament_weight_grams: float = Field(..., ge=0)
    layer_count: Optional[int] = None
    estimated_cost: Optional[float] = None


class QuoteResponse(BaseModel):
    """Complete quote response."""
    
    request_id: str
    name: str
    mobile: str
    material: Optional[str]
    color: Optional[str]
    filename: str
    
    # Slicing results
    print_time_hours: float
    print_time_minutes: int
    filament_weight_grams: float
    
    # Pricing
    material_cost: float
    time_cost: float
    total_cost: float
    
    # Metadata
    status: QuoteStatus
    created_at: datetime
    processed_at: Optional[datetime] = None
    
    @validator("print_time_hours", pre=True)
    def calculate_hours(cls, v, values):
        """Calculate hours from minutes if not provided."""
        if 'print_time_minutes' in values:
            return values['print_time_minutes'] / 60.0
        return v


class TelegramMessage(BaseModel):
    """Telegram message data."""
    
    quote_id: str
    customer_name: str
    customer_mobile: str
    material: Optional[str]
    color: Optional[str]
    filename: str
    print_time: str
    filament_weight: str
    total_cost: float
    
    def format_message(self) -> str:
        """Format message for Telegram."""
        material_info = f" ({self.material})" if self.material else ""
        color_info = f" - {self.color}" if self.color else ""
        
        return f"""New Quote Request #{self.quote_id}
        
Customer: {self.customer_name}
WhatsApp: {self.customer_mobile}
File: {self.filename}
Material: {self.material or 'PLA (default)'}{color_info}

Print Time: {self.print_time}
Filament: {self.filament_weight}
Total Cost: S${self.total_cost:.2f}

Reply to this message to contact the customer directly."""