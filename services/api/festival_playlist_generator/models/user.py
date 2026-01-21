"""User database model."""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSON, ARRAY
from datetime import datetime
import uuid

from festival_playlist_generator.core.database import Base


class User(Base):
    """User database model."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    oauth_provider = Column(String(50), nullable=True, index=True)
    oauth_provider_id = Column(String(255), nullable=True, index=True)
    display_name = Column(String(255), nullable=True)
    profile_picture_url = Column(Text, nullable=True)
    marketing_opt_in = Column(Boolean, nullable=False, default=False)
    preferences = Column(JSON, nullable=True)
    connected_platforms = Column(ARRAY(String), nullable=True)
    festival_history = Column(ARRAY(UUID), nullable=True)
    known_songs = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    playlists = relationship("Playlist", back_populates="user")
    song_preferences = relationship("UserSongPreference", back_populates="user")
    
    def __repr__(self):
        return f"<User(email='{self.email}')>"


class UserSongPreference(Base):
    """User song preference tracking."""
    
    __tablename__ = "user_song_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    song_id = Column(UUID(as_uuid=True), ForeignKey("songs.id"), nullable=False, index=True)
    is_known = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="song_preferences")
    song = relationship("Song", back_populates="user_preferences")
    
    def __repr__(self):
        return f"<UserSongPreference(user_id='{self.user_id}', song_id='{self.song_id}', is_known={self.is_known})>"