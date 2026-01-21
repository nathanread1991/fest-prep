"""Setlist Pydantic schemas."""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional
from uuid import UUID


class SetlistBase(BaseModel):
    """Base Setlist schema with common fields."""
    venue: str = Field(..., min_length=1, max_length=255, description="Venue name")
    date: datetime = Field(..., description="Performance date")
    songs: List[str] = Field(default_factory=list, description="List of song titles (can be empty if tracklist not available)")
    tour_name: Optional[str] = Field(None, max_length=255, description="Tour name")
    festival_name: Optional[str] = Field(None, max_length=255, description="Festival name")
    source: str = Field(default="setlist.fm", max_length=50, description="Data source")


class SetlistCreate(SetlistBase):
    """Schema for creating a new setlist."""
    artist_id: UUID = Field(..., description="Artist UUID")


class SetlistUpdate(BaseModel):
    """Schema for updating a setlist."""
    venue: Optional[str] = Field(None, min_length=1, max_length=255)
    date: Optional[datetime] = None
    songs: Optional[List[str]] = None
    tour_name: Optional[str] = Field(None, max_length=255)
    festival_name: Optional[str] = Field(None, max_length=255)
    source: Optional[str] = Field(None, max_length=50)


class Setlist(SetlistBase):
    """Complete Setlist schema with all fields."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    artist_id: UUID
    artist_name: str = Field(..., description="Artist name for convenience")
    created_at: datetime
    updated_at: Optional[datetime] = None