"""Artist repository for database operations."""

from typing import Any, List, Optional, Tuple, cast
from uuid import UUID

from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from festival_playlist_generator.models.artist import Artist
from festival_playlist_generator.models.festival import festival_artists
from festival_playlist_generator.models.setlist import Setlist


class ArtistRepository:
    """Repository for Artist database operations following enterprise patterns."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(
        self, artist_id: UUID, load_relationships: bool = False
    ) -> Optional[Artist]:
        """
        Get artist by ID.

        Args:
            artist_id: Artist UUID
            load_relationships: Whether to load festivals and setlists

        Returns:
            Artist or None if not found
        """
        query = select(Artist).where(Artist.id == artist_id)

        if load_relationships:
            query = query.options(
                selectinload(Artist.festivals), selectinload(Artist.setlists)
            )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Artist]:
        """Get artist by exact name match."""
        result = await self.db.execute(select(Artist).where(Artist.name == name))
        return result.scalar_one_or_none()

    async def get_by_spotify_id(self, spotify_id: str) -> Optional[Artist]:
        """Get artist by Spotify ID."""
        result = await self.db.execute(
            select(Artist).where(Artist.spotify_id == spotify_id)
        )
        return result.scalar_one_or_none()

    async def search_paginated(
        self,
        search: Optional[str] = None,
        filter_orphaned: bool = False,
        filter_with_festivals: bool = False,
        page: int = 1,
        per_page: int = 100,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> Tuple[List[Artist], int]:
        """
        Search artists with pagination and filters.

        Args:
            search: Search term for name/genres
            filter_orphaned: Only show orphaned artists
            filter_with_festivals: Only show artists with festivals
            page: Page number (1-indexed)
            per_page: Results per page
            order_by: Column to order by
            order_desc: Order descending if True

        Returns:
            Tuple of (artists list, total count)
        """
        # Build subquery for setlist count (for orphaned detection)
        setlist_count_subquery = (
            select(func.count(Setlist.id))
            .where(Setlist.artist_id == Artist.id)
            .correlate(Artist)
            .scalar_subquery()
        )

        # Build base query with is_orphaned calculation
        base_query = select(
            Artist,
            case(
                ((Artist.spotify_id.is_(None)) & (setlist_count_subquery == 0), True),
                else_=False,
            ).label("is_orphaned"),
        )

        # Apply search filter
        if search:
            search_term = f"%{search.lower()}%"
            base_query = base_query.where(
                or_(
                    func.lower(Artist.name).like(search_term),
                    func.lower(func.array_to_string(Artist.genres, ",")).like(
                        search_term
                    ),
                )
            )

        # Apply orphaned filter
        if filter_orphaned:
            base_query = base_query.where(
                (Artist.spotify_id.is_(None)) & (setlist_count_subquery == 0)
            )

        # Apply with festivals filter
        if filter_with_festivals:
            base_query = base_query.where(
                Artist.id.in_(select(festival_artists.c.artist_id).distinct())
            )

        # Get total count (with filters applied)
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar()
        total_count_int = total_count if total_count is not None else 0

        # Apply ordering
        order_column = getattr(Artist, order_by, Artist.created_at)
        if order_desc:
            base_query = base_query.order_by(order_column.desc())
        else:
            base_query = base_query.order_by(order_column.asc())

        # Apply pagination
        offset = (page - 1) * per_page
        base_query = base_query.limit(per_page).offset(offset)

        # Execute query
        result = await self.db.execute(base_query)

        # Extract artists and add is_orphaned flag
        artists: List[Any] = []
        for row in result:
            artist = row[0]
            artist.is_orphaned = row[1]
            artists.append(artist)

        return artists, total_count_int

    async def create(self, artist: Artist) -> Artist:
        """Create a new artist."""
        self.db.add(artist)
        await self.db.flush()
        await self.db.refresh(artist)
        return artist

    async def update(self, artist: Artist) -> Artist:
        """Update an existing artist."""
        await self.db.flush()
        await self.db.refresh(artist)
        return artist

    async def delete(self, artist_id: UUID) -> bool:
        """
        Delete an artist.

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute(delete(Artist).where(Artist.id == artist_id))
        rowcount = cast(Any, result).rowcount
        return rowcount is not None and rowcount > 0

    async def bulk_delete(self, artist_ids: List[UUID]) -> int:
        """
        Delete multiple artists.

        Returns:
            Number of artists deleted
        """
        result = await self.db.execute(delete(Artist).where(Artist.id.in_(artist_ids)))
        rowcount = cast(Any, result).rowcount
        return rowcount if rowcount is not None else 0

    async def exists_by_name(self, name: str) -> bool:
        """Check if artist exists by name."""
        result = await self.db.execute(
            select(func.count(Artist.id)).where(Artist.name == name)
        )
        count = result.scalar()
        return count is not None and count > 0

    async def exists_by_spotify_id(self, spotify_id: str) -> bool:
        """Check if artist exists by Spotify ID."""
        result = await self.db.execute(
            select(func.count(Artist.id)).where(Artist.spotify_id == spotify_id)
        )
        count = result.scalar()
        return count is not None and count > 0

    async def get_all_ids(self) -> List[UUID]:
        """Get all artist IDs (for bulk operations)."""
        result = await self.db.execute(select(Artist.id))
        return [row[0] for row in result]

    async def count_total(self) -> int:
        """Get total count of all artists."""
        result = await self.db.execute(select(func.count(Artist.id)))
        count = result.scalar()
        return count if count is not None else 0

    async def count_orphaned(self) -> int:
        """Get count of orphaned artists."""
        setlist_count_subquery = (
            select(func.count(Setlist.id))
            .where(Setlist.artist_id == Artist.id)
            .correlate(Artist)
            .scalar_subquery()
        )

        result = await self.db.execute(
            select(func.count(Artist.id)).where(
                (Artist.spotify_id.is_(None)) & (setlist_count_subquery == 0)
            )
        )
        count = result.scalar()
        return count if count is not None else 0
