"""Festival database model."""

from sqlalchemy import Column, String, DateTime, Text, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from datetime import datetime
import uuid

from festival_playlist_generator.core.database import Base

# Association table for festival-artist many-to-many relationship
festival_artists = Table(
    'festival_artists',
    Base.metadata,
    Column('festival_id', UUID(as_uuid=True), ForeignKey('festivals.id'), primary_key=True),
    Column('artist_id', UUID(as_uuid=True), ForeignKey('artists.id'), primary_key=True)
)


class Festival(Base):
    """Festival database model."""
    
    __tablename__ = "festivals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    dates = Column(ARRAY(DateTime), nullable=False, index=True)
    location = Column(String(255), nullable=False, index=True)
    venue = Column(String(255), nullable=True)
    genres = Column(ARRAY(String), nullable=True)
    ticket_url = Column(Text, nullable=True)
    
    # Visual branding fields
    logo_url = Column(Text, nullable=True)
    primary_color = Column(String(7), nullable=True)
    secondary_color = Column(String(7), nullable=True)
    text_color = Column(String(7), nullable=True)
    accent_colors = Column(ARRAY(String), nullable=True)
    branding_extracted_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    artists = relationship("Artist", secondary=festival_artists, back_populates="festivals")
    playlists = relationship("Playlist", back_populates="festival")
    
    @property
    def start_date(self):
        """Get the start date of the festival."""
        return min(self.dates) if self.dates else None
    
    @property
    def end_date(self):
        """Get the end date of the festival."""
        return max(self.dates) if self.dates else None
    
    @property
    def description(self):
        """Get a description of the festival."""
        return f"A {len(self.genres) if self.genres else 'multi-genre'} music festival in {self.location}"
    
    def __repr__(self):
        return f"<Festival(name='{self.name}', location='{self.location}')>"