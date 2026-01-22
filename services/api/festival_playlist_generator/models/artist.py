"""Artist database model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from festival_playlist_generator.core.database import Base
from festival_playlist_generator.models.festival import festival_artists


class Artist(Base):
    """Artist database model."""

    __tablename__ = "artists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    musicbrainz_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, unique=True
    )
    spotify_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, unique=True
    )
    spotify_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    spotify_popularity: Mapped[float | None] = mapped_column(Float, nullable=True)
    spotify_followers: Mapped[float | None] = mapped_column(Float, nullable=True)
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    popularity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Visual branding fields
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    festivals = relationship(
        "Festival", secondary=festival_artists, back_populates="artists"
    )
    setlists = relationship("Setlist", back_populates="artist")
    playlists = relationship("Playlist", back_populates="artist")

    def __repr__(self) -> str:
        return f"<Artist(name='{self.name}')>"
