"""Festival Pydantic schemas."""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FestivalBase(BaseModel):
    """Base Festival schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Festival name")
    dates: List[datetime] = Field(..., min_length=1, description="Festival dates")
    location: str = Field(
        ..., min_length=1, max_length=255, description="Festival location"
    )
    venue: Optional[str] = Field(None, max_length=255, description="Festival venue")
    genres: List[str] = Field(default_factory=list, description="Festival genres")
    ticket_url: Optional[str] = Field(None, description="Ticket purchase URL")

    # Visual branding fields
    logo_url: Optional[str] = Field(None, description="Festival logo URL")
    primary_color: Optional[str] = Field(
        None, max_length=7, description="Primary color (hex format)"
    )
    secondary_color: Optional[str] = Field(
        None, max_length=7, description="Secondary color (hex format)"
    )
    accent_colors: Optional[List[str]] = Field(
        None, description="Accent colors (hex format)"
    )
    branding_extracted_at: Optional[datetime] = Field(
        None, description="When branding was extracted"
    )


class FestivalCreate(FestivalBase):
    """Schema for creating a new festival."""

    artists: List[str] = Field(
        default_factory=list, description="Artist names in lineup"
    )
    artist_images: Optional[Dict[str, Any]] = Field(
        None, description="Artist image data from scraping"
    )


class FestivalUpdate(BaseModel):
    """Schema for updating a festival."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    dates: Optional[List[datetime]] = Field(None, min_length=1)
    location: Optional[str] = Field(None, min_length=1, max_length=255)
    venue: Optional[str] = Field(None, max_length=255)
    genres: Optional[List[str]] = None
    ticket_url: Optional[str] = None
    artists: Optional[List[str]] = None

    # Visual branding fields
    logo_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, max_length=7)
    secondary_color: Optional[str] = Field(None, max_length=7)
    accent_colors: Optional[List[str]] = None
    branding_extracted_at: Optional[datetime] = None


class Festival(FestivalBase):
    """Complete Festival schema with all fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artists: List[str] = Field(
        default_factory=list, description="Artist names in lineup"
    )
    created_at: datetime
    updated_at: datetime

    # Override branding fields to ensure they're included in response
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_colors: Optional[List[str]] = None
    branding_extracted_at: Optional[datetime] = None
