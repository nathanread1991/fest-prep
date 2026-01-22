"""User database model."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from festival_playlist_generator.core.database import Base


class User(Base):
    """User database model."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    oauth_provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )
    oauth_provider_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_picture_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    marketing_opt_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    connected_platforms: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    festival_history: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID), nullable=True
    )
    known_songs: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    playlists = relationship("Playlist", back_populates="user")
    song_preferences = relationship("UserSongPreference", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(email='{self.email}')>"


class UserSongPreference(Base):
    """User song preference tracking."""

    __tablename__ = "user_song_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    song_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("songs.id"), nullable=False, index=True
    )
    is_known: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="song_preferences")
    song = relationship("Song", back_populates="user_preferences")

    def __repr__(self) -> str:
        return (
            f"<UserSongPreference(user_id='{self.user_id}', "
            f"song_id='{self.song_id}', is_known={self.is_known})>"
        )
