"""Song database model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from festival_playlist_generator.core.database import Base

# Association table for playlist-song many-to-many relationship with ordering
playlist_songs = Table(
    "playlist_songs",
    Base.metadata,
    Column(
        "playlist_id", UUID(as_uuid=True), ForeignKey("playlists.id"), primary_key=True
    ),
    Column("song_id", UUID(as_uuid=True), ForeignKey("songs.id"), primary_key=True),
    Column("order_index", Integer, nullable=False),
)


class Song(Base):
    """Song database model."""

    __tablename__ = "songs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_artist: Mapped[str | None] = mapped_column(String(255), nullable=True)  # For covers
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False)
    normalized_title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    performance_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    playlists = relationship(
        "Playlist", secondary=playlist_songs, back_populates="songs"
    )
    user_preferences = relationship("UserSongPreference", back_populates="song")

    def __repr__(self) -> str:
        return f"<Song(title='{self.title}', artist='{self.artist}')>"
