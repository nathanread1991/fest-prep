"""Setlist database model."""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from datetime import datetime
import uuid

from festival_playlist_generator.core.database import Base


class Setlist(Base):
    """Setlist database model."""
    
    __tablename__ = "setlists"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artists.id"), nullable=False, index=True)
    venue = Column(String(255), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    songs = Column(ARRAY(String), nullable=False)
    tour_name = Column(String(255), nullable=True)
    festival_name = Column(String(255), nullable=True)
    source = Column(String(50), nullable=False, default="setlist.fm")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    artist = relationship("Artist", back_populates="setlists")
    
    def __repr__(self):
        return f"<Setlist(artist='{self.artist.name if self.artist else 'Unknown'}', venue='{self.venue}', date='{self.date}')>"