"""Song database model."""

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from festival_playlist_generator.core.database import Base

# Association table for playlist-song many-to-many relationship with ordering
playlist_songs = Table(
    'playlist_songs',
    Base.metadata,
    Column('playlist_id', UUID(as_uuid=True), ForeignKey('playlists.id'), primary_key=True),
    Column('song_id', UUID(as_uuid=True), ForeignKey('songs.id'), primary_key=True),
    Column('order_index', Integer, nullable=False)
)


class Song(Base):
    """Song database model."""
    
    __tablename__ = "songs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False, index=True)
    artist = Column(String(255), nullable=False, index=True)
    original_artist = Column(String(255), nullable=True)  # For covers
    is_cover = Column(Boolean, default=False)
    normalized_title = Column(String(255), nullable=False, index=True)
    performance_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    playlists = relationship("Playlist", secondary=playlist_songs, back_populates="songs")
    user_preferences = relationship("UserSongPreference", back_populates="song")
    
    def __repr__(self):
        return f"<Song(title='{self.title}', artist='{self.artist}')>"