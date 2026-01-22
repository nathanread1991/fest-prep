"""Artist Pydantic schemas."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ArtistBase(BaseModel):
    """Base Artist schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Artist name")
    musicbrainz_id: Optional[str] = Field(
        None, max_length=36, description="MusicBrainz identifier"
    )
    genres: List[str] = Field(default_factory=list, description="Artist genres")
    popularity_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Popularity score (0-1)"
    )


class ArtistCreate(ArtistBase):
    """Schema for creating a new artist."""


class ArtistUpdate(BaseModel):
    """Schema for updating an artist."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    musicbrainz_id: Optional[str] = Field(None, max_length=36)
    genres: Optional[List[str]] = None
    popularity_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class Artist(ArtistBase):
    """Complete Artist schema with all fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to convert UUID and datetime to strings."""
        data = super().model_dump(**kwargs)
        if "id" in data:
            data["id"] = str(data["id"])
        if "created_at" in data:
            data["created_at"] = data["created_at"].isoformat()
        return data
