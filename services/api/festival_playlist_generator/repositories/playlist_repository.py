"""Playlist repository for database operations."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from festival_playlist_generator.models.playlist import Playlist, StreamingPlatform
from festival_playlist_generator.repositories.base_repository import BaseRepository


class PlaylistRepository(BaseRepository[Playlist]):
    """Repository for Playlist database operations following enterprise patterns."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the playlist repository.

        Args:
            db: Async database session
        """
        super().__init__(db, Playlist)

    async def get_by_id(
        self, playlist_id: UUID, load_relationships: bool = False
    ) -> Optional[Playlist]:
        """
        Get playlist by ID.

        Args:
            playlist_id: Playlist UUID
            load_relationships: Whether to load festival, artist, user, and songs

        Returns:
            Playlist or None if not found
        """
        query = select(Playlist).where(Playlist.id == playlist_id)

        if load_relationships:
            query = query.options(
                selectinload(Playlist.festival),
                selectinload(Playlist.artist),
                selectinload(Playlist.user),
                selectinload(Playlist.songs),
            )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_user(
        self, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> List[Playlist]:
        """
        Get all playlists for a specific user.

        Eager-loads festival and artist to avoid N+1 queries.

        Args:
            user_id: User UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of user's playlists
        """
        result = await self.db.execute(
            select(Playlist)
            .options(
                selectinload(Playlist.festival),
                selectinload(Playlist.artist),
            )
            .where(Playlist.user_id == user_id)
            .order_by(Playlist.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all())

    async def get_by_festival(
        self, festival_id: UUID, skip: int = 0, limit: int = 50
    ) -> List[Playlist]:
        """
        Get all playlists for a specific festival.

        Eager-loads festival and artist to avoid N+1 queries.

        Args:
            festival_id: Festival UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of festival playlists
        """
        result = await self.db.execute(
            select(Playlist)
            .options(
                selectinload(Playlist.festival),
                selectinload(Playlist.artist),
            )
            .where(Playlist.festival_id == festival_id)
            .order_by(Playlist.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all())

    async def get_by_artist(
        self, artist_id: UUID, skip: int = 0, limit: int = 50
    ) -> List[Playlist]:
        """
        Get all playlists for a specific artist.

        Eager-loads festival and artist to avoid N+1 queries.

        Args:
            artist_id: Artist UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of artist playlists
        """
        result = await self.db.execute(
            select(Playlist)
            .options(
                selectinload(Playlist.festival),
                selectinload(Playlist.artist),
            )
            .where(Playlist.artist_id == artist_id)
            .order_by(Playlist.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all())

    async def get_by_spotify_id(self, spotify_id: str) -> Optional[Playlist]:
        """
        Get playlist by Spotify external ID.

        Args:
            spotify_id: Spotify playlist ID

        Returns:
            Playlist or None if not found
        """
        result = await self.db.execute(
            select(Playlist).where(
                Playlist.platform == StreamingPlatform.SPOTIFY,
                Playlist.external_id == spotify_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(
        self, platform: StreamingPlatform, external_id: str
    ) -> Optional[Playlist]:
        """
        Get playlist by platform and external ID.

        Args:
            platform: Streaming platform
            external_id: Platform-specific playlist ID

        Returns:
            Playlist or None if not found
        """
        result = await self.db.execute(
            select(Playlist).where(
                Playlist.platform == platform, Playlist.external_id == external_id
            )
        )
        return result.scalar_one_or_none()

    async def get_user_festival_playlist(
        self, user_id: UUID, festival_id: UUID
    ) -> Optional[Playlist]:
        """
        Get a user's playlist for a specific festival.

        Args:
            user_id: User UUID
            festival_id: Festival UUID

        Returns:
            Playlist or None if not found
        """
        result = await self.db.execute(
            select(Playlist)
            .where(Playlist.user_id == user_id, Playlist.festival_id == festival_id)
            .order_by(Playlist.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def count_by_user(self, user_id: UUID) -> int:
        """
        Get count of playlists for a specific user.

        Args:
            user_id: User UUID

        Returns:
            Number of user's playlists
        """
        result = await self.db.execute(
            select(func.count(Playlist.id)).where(Playlist.user_id == user_id)
        )
        count = result.scalar()
        return count if count is not None else 0

    async def count_by_festival(self, festival_id: UUID) -> int:
        """
        Get count of playlists for a specific festival.

        Args:
            festival_id: Festival UUID

        Returns:
            Number of festival playlists
        """
        result = await self.db.execute(
            select(func.count(Playlist.id)).where(Playlist.festival_id == festival_id)
        )
        count = result.scalar()
        return count if count is not None else 0

    async def count_by_platform(self, platform: StreamingPlatform) -> int:
        """
        Get count of playlists for a specific platform.

        Args:
            platform: Streaming platform

        Returns:
            Number of playlists on the platform
        """
        result = await self.db.execute(
            select(func.count(Playlist.id)).where(Playlist.platform == platform)
        )
        count = result.scalar()
        return count if count is not None else 0

    async def exists_by_external_id(
        self, platform: StreamingPlatform, external_id: str
    ) -> bool:
        """
        Check if playlist exists by platform and external ID.

        Args:
            platform: Streaming platform
            external_id: Platform-specific playlist ID

        Returns:
            True if playlist exists, False otherwise
        """
        result = await self.db.execute(
            select(func.count(Playlist.id)).where(
                Playlist.platform == platform, Playlist.external_id == external_id
            )
        )
        count = result.scalar()
        return count is not None and count > 0
