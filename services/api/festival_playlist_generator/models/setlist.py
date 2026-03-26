"""Setlist database model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from festival_playlist_generator.core.database import Base


class Setlist(Base):
    """Setlist database model."""

    __tablename__ = "setlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artists.id"), nullable=False, index=True
    )
    venue: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    songs: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    tour_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    festival_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="setlist.fm"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    artist = relationship("Artist", back_populates="setlists")

    def __repr__(self) -> str:
        artist_name = self.artist.name if self.artist else "Unknown"
        return (
            f"<Setlist(artist='{artist_name}', "
            f"venue='{self.venue}', date='{self.date}')>"
        )
