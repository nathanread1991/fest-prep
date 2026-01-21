"""Playlist database model."""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

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
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    festival_id = Column(UUID(as_uuid=True), ForeignKey("festivals.id"), nullable=True)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artists.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform = Column(Enum(StreamingPlatform), nullable=True)
    external_id = Column(String(255), nullable=True)  # Platform-specific playlist ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    festival = relationship("Festival", back_populates="playlists")
    artist = relationship("Artist", back_populates="playlists")
    user = relationship("User", back_populates="playlists")
    songs = relationship("Song", secondary=playlist_songs, back_populates="playlists")
    
    def __repr__(self):
        return f"<Playlist(name='{self.name}', user_id='{self.user_id}')>"