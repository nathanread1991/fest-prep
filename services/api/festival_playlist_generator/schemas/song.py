"""Song Pydantic schemas."""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SongBase(BaseModel):
    """Base Song schema with common fields."""

    title: str = Field(..., min_length=1, max_length=255, description="Song title")
    artist: str = Field(..., min_length=1, max_length=255, description="Artist name")
    original_artist: Optional[str] = Field(
        None, max_length=255, description="Original artist for covers"
    )
    is_cover: bool = Field(default=False, description="Whether this is a cover song")
    performance_count: int = Field(
        default=0, ge=0, description="Number of times performed"
    )

    @field_validator("title", "artist", "original_artist")
    @classmethod
    def normalize_strings(cls, v: Optional[str]) -> Optional[str]:
        """Normalize string fields by stripping whitespace."""
        if v is None:
            return v
        return v.strip()

    def get_normalized_title(self) -> str:
        """Generate normalized title for deduplication."""
        if not self.title:
            return ""

        # Convert to lowercase and remove special characters
        normalized = re.sub(r"[^\w\s]", "", self.title.lower())
        # Replace multiple spaces with single space and strip
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized


class SongCreate(SongBase):
    """Schema for creating a new song."""


class SongUpdate(BaseModel):
    """Schema for updating a song."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    artist: Optional[str] = Field(None, min_length=1, max_length=255)
    original_artist: Optional[str] = Field(None, max_length=255)
    is_cover: Optional[bool] = None
    performance_count: Optional[int] = Field(None, ge=0)


class Song(SongBase):
    """Complete Song schema with all fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    normalized_title: str = Field(..., description="Normalized title for deduplication")
    created_at: datetime
