"""Playlist database model."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from festival_playlist_generator.core.database import Base
from festival_playlist_generator.models.song import playlist_songs


class StreamingPlatform(enum.Enum):
    """Supported streaming platforms."""

    SPOTIFY = "spotify"
    YOUTUBE_MUSIC = "youtube_music"
    APPLE_MUSIC = "apple_music"
    YOUTUBE = "youtube"


class Playlist(Base):
    """Playlist database model."""

    __tablename__ = "playlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    festival_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("festivals.id"), nullable=True
    )
    artist_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artists.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    platform: Mapped[StreamingPlatform | None] = mapped_column(
        Enum(StreamingPlatform), nullable=True
    )
    external_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Platform-specific playlist ID
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    festival = relationship("Festival", back_populates="playlists")
    artist = relationship("Artist", back_populates="playlists")
    user = relationship("User", back_populates="playlists")
    songs = relationship("Song", secondary=playlist_songs, back_populates="playlists")

    def __repr__(self) -> str:
        return f"<Playlist(name='{self.name}', user_id='{self.user_id}')>"
