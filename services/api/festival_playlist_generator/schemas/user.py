"""User Pydantic schemas."""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Base User schema with common fields."""

    email: EmailStr = Field(..., description="User email address")
    preferences: Dict[str, Any] = Field(
        default_factory=dict, description="User preferences"
    )
    connected_platforms: List[str] = Field(
        default_factory=list, description="Connected streaming platforms"
    )

    @field_validator("connected_platforms")
    @classmethod
    def validate_platforms(cls, v: List[str]) -> List[str]:
        """Validate connected platforms are supported."""
        valid_platforms = {"spotify", "youtube_music", "apple_music", "youtube"}
        for platform in v:
            if platform not in valid_platforms:
                raise ValueError(f"Unsupported platform: {platform}")
        return v


class UserCreate(UserBase):
    """Schema for creating a new user."""

    oauth_provider: Optional[str] = Field(
        None, description="OAuth provider (e.g., spotify)"
    )
    oauth_provider_id: Optional[str] = Field(None, description="OAuth provider user ID")
    display_name: Optional[str] = Field(None, description="User display name")


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: Optional[EmailStr] = None
    preferences: Optional[Dict[str, Any]] = None
    connected_platforms: Optional[List[str]] = None

    @field_validator("connected_platforms")
    @classmethod
    def validate_platforms(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate connected platforms are supported."""
        if v is None:
            return v
        valid_platforms = {"spotify", "youtube_music", "apple_music", "youtube"}
        for platform in v:
            if platform not in valid_platforms:
                raise ValueError(f"Unsupported platform: {platform}")
        return v


class User(UserBase):
    """Complete User schema with all fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    oauth_provider: Optional[str] = Field(
        None, description="OAuth provider (google, apple, youtube, spotify, x)"
    )
    oauth_provider_id: Optional[str] = Field(
        None, description="Provider-specific user ID"
    )
    display_name: Optional[str] = Field(None, description="User display name")
    profile_picture_url: Optional[str] = Field(None, description="Profile picture URL")
    marketing_opt_in: bool = Field(False, description="Marketing communications opt-in")
    known_songs: Optional[List[str]] = Field(
        default=None, description="Songs marked as known"
    )
    festival_history: Optional[List[UUID]] = Field(
        default=None, description="Festival attendance history"
    )
    created_at: datetime
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")


class UserSongPreferenceBase(BaseModel):
    """Base UserSongPreference schema."""

    is_known: bool = Field(..., description="Whether user knows this song")


class UserSongPreferenceCreate(UserSongPreferenceBase):
    """Schema for creating a user song preference."""

    user_id: UUID = Field(..., description="User ID")
    song_id: UUID = Field(..., description="Song ID")


class UserSongPreferenceUpdate(BaseModel):
    """Schema for updating a user song preference."""

    is_known: Optional[bool] = None


class UserSongPreference(UserSongPreferenceBase):
    """Complete UserSongPreference schema with all fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    song_id: UUID
    created_at: datetime
