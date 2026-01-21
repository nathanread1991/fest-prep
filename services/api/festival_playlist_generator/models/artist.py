"""Artist database model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from festival_playlist_generator.core.database import Base
from festival_playlist_generator.models.festival import festival_artists


class Artist(Base):
    """Artist database model."""

    __tablename__ = "artists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    musicbrainz_id = Column(String(36), nullable=True, unique=True)
    spotify_id = Column(String(50), nullable=True, unique=True)
    spotify_image_url = Column(String(500), nullable=True)
    spotify_popularity = Column(Float, nullable=True)
    spotify_followers = Column(Float, nullable=True)
    genres = Column(ARRAY(String), nullable=True)
    popularity_score = Column(Float, nullable=True)

    # Visual branding fields
    logo_url = Column(Text, nullable=True)
    logo_source = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    festivals = relationship(
        "Festival", secondary=festival_artists, back_populates="artists"
    )
    setlists = relationship("Setlist", back_populates="artist")
    playlists = relationship("Playlist", back_populates="artist")

    def __repr__(self):
        return f"<Artist(name='{self.name}')>"
