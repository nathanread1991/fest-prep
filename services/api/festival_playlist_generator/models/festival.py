"""Festival database model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from festival_playlist_generator.core.database import Base

# Association table for festival-artist many-to-many relationship
festival_artists = Table(
    "festival_artists",
    Base.metadata,
    Column(
        "festival_id", UUID(as_uuid=True), ForeignKey("festivals.id"), primary_key=True
    ),
    Column("artist_id", UUID(as_uuid=True), ForeignKey("artists.id"), primary_key=True),
)


class Festival(Base):
    """Festival database model."""

    __tablename__ = "festivals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    dates: Mapped[list[datetime]] = mapped_column(ARRAY(DateTime), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    ticket_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Visual branding fields
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    text_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    accent_colors: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    branding_extracted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    artists = relationship(
        "Artist", secondary=festival_artists, back_populates="festivals"
    )
    playlists = relationship("Playlist", back_populates="festival")

    @property
    def start_date(self) -> datetime | None:
        """Get the start date of the festival."""
        return min(self.dates) if self.dates else None

    @property
    def end_date(self) -> datetime | None:
        """Get the end date of the festival."""
        return max(self.dates) if self.dates else None

    @property
    def description(self) -> str:
        """Get a description of the festival."""
        return f"A {len(self.genres) if self.genres else 'multi-genre'} music festival in {self.location}"

    def __repr__(self) -> str:
        return f"<Festival(name='{self.name}', location='{self.location}')>"
