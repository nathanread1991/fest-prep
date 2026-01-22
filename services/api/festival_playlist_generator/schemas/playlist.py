"""Playlist Pydantic schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StreamingPlatform(str, Enum):
    """Supported streaming platforms."""

    SPOTIFY = "spotify"
    YOUTUBE_MUSIC = "youtube_music"
    APPLE_MUSIC = "apple_music"
    YOUTUBE = "youtube"


class PlaylistBase(BaseModel):
    """Base Playlist schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Playlist name")
    description: Optional[str] = Field(None, description="Playlist description")
    platform: Optional[StreamingPlatform] = Field(
        None, description="Streaming platform"
    )
    external_id: Optional[str] = Field(
        None, max_length=255, description="Platform-specific playlist ID"
    )


class PlaylistCreate(PlaylistBase):
    """Schema for creating a new playlist."""

    festival_id: Optional[UUID] = Field(None, description="Associated festival ID")
    artist_id: Optional[UUID] = Field(None, description="Associated artist ID")
    user_id: UUID = Field(..., description="Owner user ID")
    song_ids: List[UUID] = Field(default_factory=list, description="List of song IDs")


class PlaylistUpdate(BaseModel):
    """Schema for updating a playlist."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    platform: Optional[StreamingPlatform] = None
    external_id: Optional[str] = Field(None, max_length=255)
    song_ids: Optional[List[UUID]] = None


class Playlist(PlaylistBase):
    """Complete Playlist schema with all fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    festival_id: Optional[UUID]
    artist_id: Optional[UUID]
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to convert UUID and datetime to strings."""
        data = super().model_dump(**kwargs)
        # Convert UUIDs to strings
        if "id" in data and data["id"] is not None:
            data["id"] = str(data["id"])
        if "festival_id" in data and data["festival_id"] is not None:
            data["festival_id"] = str(data["festival_id"])
        if "artist_id" in data and data["artist_id"] is not None:
            data["artist_id"] = str(data["artist_id"])
        if "user_id" in data and data["user_id"] is not None:
            data["user_id"] = str(data["user_id"])
        # Convert datetimes to ISO format
        if "created_at" in data and data["created_at"] is not None:
            data["created_at"] = data["created_at"].isoformat()
        if "updated_at" in data and data["updated_at"] is not None:
            data["updated_at"] = data["updated_at"].isoformat()
        return data
