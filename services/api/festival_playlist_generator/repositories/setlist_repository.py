"""Setlist repository for database operations."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from festival_playlist_generator.models.setlist import Setlist
from festival_playlist_generator.repositories.base_repository import BaseRepository


class SetlistRepository(BaseRepository[Setlist]):
    """Repository for Setlist database operations following enterprise patterns."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the setlist repository.

        Args:
            db: Async database session
        """
        super().__init__(db, Setlist)

    async def get_by_id(
        self, setlist_id: UUID, load_relationships: bool = False
    ) -> Optional[Setlist]:
        """
        Get setlist by ID.

        Args:
            setlist_id: Setlist UUID
            load_relationships: Whether to load artist relationship

        Returns:
            Setlist or None if not found
        """
        query = select(Setlist).where(Setlist.id == setlist_id)

        if load_relationships:
            query = query.options(selectinload(Setlist.artist))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_artist(
        self, artist_id: UUID, skip: int = 0, limit: int = 50
    ) -> List[Setlist]:
        """
        Get all setlists for a specific artist.

        Args:
            artist_id: Artist UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of artist's setlists ordered by date (most recent first)
        """
        result = await self.db.execute(
            select(Setlist)
            .where(Setlist.artist_id == artist_id)
            .order_by(Setlist.date.desc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all())

    async def get_recent_setlists(
        self, artist_id: UUID, limit: int = 10, from_date: Optional[datetime] = None
    ) -> List[Setlist]:
        """
        Get recent setlists for an artist.

        Args:
            artist_id: Artist UUID
            limit: Maximum number of setlists to return
            from_date: Only return setlists after this date

        Returns:
            List of recent setlists ordered by date (most recent first)
        """
        query = select(Setlist).where(Setlist.artist_id == artist_id)

        if from_date:
            query = query.where(Setlist.date >= from_date)

        query = query.order_by(Setlist.date.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_setlistfm_id(self, setlistfm_id: str) -> Optional[Setlist]:
        """
        Get setlist by Setlist.fm ID.

        Note: This assumes setlistfm_id is stored in a field.
        If not, this method may need adjustment based on your schema.

        Args:
            setlistfm_id: Setlist.fm ID

        Returns:
            Setlist or None if not found
        """
        # This is a placeholder - adjust based on your actual schema
        # If you don't have a setlistfm_id field, you might need to add it
        # or use a different identifier
        result = await self.db.execute(
            select(Setlist).where(Setlist.source == "setlist.fm")
            # Add additional filter if you have a setlistfm_id field
        )
        return result.scalar_one_or_none()

    async def get_by_venue(
        self, venue: str, skip: int = 0, limit: int = 50
    ) -> List[Setlist]:
        """
        Get setlists by venue.

        Args:
            venue: Venue name
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of setlists at the venue
        """
        result = await self.db.execute(
            select(Setlist)
            .where(func.lower(Setlist.venue).like(f"%{venue.lower()}%"))
            .order_by(Setlist.date.desc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all())

    async def get_by_tour(
        self, tour_name: str, skip: int = 0, limit: int = 50
    ) -> List[Setlist]:
        """
        Get setlists by tour name.

        Args:
            tour_name: Tour name
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of setlists from the tour
        """
        result = await self.db.execute(
            select(Setlist)
            .where(func.lower(Setlist.tour_name).like(f"%{tour_name.lower()}%"))
            .order_by(Setlist.date.desc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all())

    async def get_by_festival_name(
        self, festival_name: str, skip: int = 0, limit: int = 50
    ) -> List[Setlist]:
        """
        Get setlists by festival name.

        Args:
            festival_name: Festival name
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of setlists from the festival
        """
        result = await self.db.execute(
            select(Setlist)
            .where(func.lower(Setlist.festival_name).like(f"%{festival_name.lower()}%"))
            .order_by(Setlist.date.desc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all())

    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        artist_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Setlist]:
        """
        Get setlists within a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range
            artist_id: Optional artist filter
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of setlists in the date range
        """
        query = select(Setlist).where(
            Setlist.date >= start_date, Setlist.date <= end_date
        )

        if artist_id:
            query = query.where(Setlist.artist_id == artist_id)

        query = query.order_by(Setlist.date.desc()).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_by_artist(self, artist_id: UUID) -> int:
        """
        Get count of setlists for a specific artist.

        Args:
            artist_id: Artist UUID

        Returns:
            Number of artist's setlists
        """
        result = await self.db.execute(
            select(func.count(Setlist.id)).where(Setlist.artist_id == artist_id)
        )
        count = result.scalar()
        return count if count is not None else 0

    async def count_by_venue(self, venue: str) -> int:
        """
        Get count of setlists at a specific venue.

        Args:
            venue: Venue name

        Returns:
            Number of setlists at the venue
        """
        result = await self.db.execute(
            select(func.count(Setlist.id)).where(
                func.lower(Setlist.venue).like(f"%{venue.lower()}%")
            )
        )
        count = result.scalar()
        return count if count is not None else 0

    async def get_most_played_songs(
        self, artist_id: UUID, limit: int = 20
    ) -> List[tuple[str, int]]:
        """
        Get most played songs for an artist across all setlists.

        Args:
            artist_id: Artist UUID
            limit: Maximum number of songs to return

        Returns:
            List of tuples (song_name, play_count) ordered by play count
        """
        # This requires unnesting the songs array and counting occurrences
        # PostgreSQL specific query
        from sqlalchemy import text

        query = text(
            """
            SELECT song, COUNT(*) as play_count
            FROM setlists, unnest(songs) as song
            WHERE artist_id = :artist_id
            GROUP BY song
            ORDER BY play_count DESC
            LIMIT :limit
        """
        )

        result = await self.db.execute(query, {"artist_id": artist_id, "limit": limit})

        return [(row[0], row[1]) for row in result]
