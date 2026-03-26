"""Festival repository for database operations."""

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.repositories.base_repository import BaseRepository


class FestivalRepository(BaseRepository[Festival]):
    """Repository for Festival database operations following enterprise patterns."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the festival repository.

        Args:
            db: Async database session
        """
        super().__init__(db, Festival)

    async def get_by_id(
        self, festival_id: UUID, load_relationships: bool = False
    ) -> Optional[Festival]:
        """
        Get festival by ID.

        Args:
            festival_id: Festival UUID
            load_relationships: Whether to load artists and playlists

        Returns:
            Festival or None if not found
        """
        query = select(Festival).where(Festival.id == festival_id)

        if load_relationships:
            query = query.options(
                selectinload(Festival.artists), selectinload(Festival.playlists)
            )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Festival]:
        """
        Get festival by exact name match.

        Args:
            name: Festival name

        Returns:
            Festival or None if not found
        """
        result = await self.db.execute(select(Festival).where(Festival.name == name))
        return result.scalar_one_or_none()

    async def get_upcoming_festivals(
        self, limit: int = 10, from_date: Optional[datetime] = None
    ) -> List[Festival]:
        """
        Get upcoming festivals ordered by start date.

        Args:
            limit: Maximum number of festivals to return
            from_date: Only return festivals after this date (defaults to now)

        Returns:
            List of upcoming festivals
        """
        if from_date is None:
            from_date = datetime.utcnow()

        # Query festivals where any date in the dates array is >= from_date
        # Note: This uses PostgreSQL array operations
        result = await self.db.execute(
            select(Festival)
            .where(func.array_length(Festival.dates, 1) > 0)
            .order_by(Festival.dates[1].asc())  # Order by first date
            .limit(limit)
        )

        # Filter in Python to ensure at least one date is in the future
        festivals = result.scalars().all()
        upcoming = [f for f in festivals if any(date >= from_date for date in f.dates)]

        return upcoming[:limit]

    async def search_festivals(
        self, query: str, skip: int = 0, limit: int = 20
    ) -> List[Festival]:
        """
        Full-text search for festivals by name, location, or venue.

        Args:
            query: Search term
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching festivals
        """
        search_term = f"%{query.lower()}%"

        result = await self.db.execute(
            select(Festival)
            .where(
                or_(
                    func.lower(Festival.name).like(search_term),
                    func.lower(Festival.location).like(search_term),
                    func.lower(Festival.venue).like(search_term),
                )
            )
            .order_by(Festival.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all())

    async def search_paginated(
        self,
        search: Optional[str] = None,
        location: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 20,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> Tuple[List[Festival], int]:
        """
        Search festivals with pagination and filters.

        Args:
            search: Search term for name/venue
            location: Filter by location
            from_date: Filter festivals starting after this date
            to_date: Filter festivals starting before this date
            page: Page number (1-indexed)
            per_page: Results per page
            order_by: Column to order by
            order_desc: Order descending if True

        Returns:
            Tuple of (festivals list, total count)
        """
        # Build base query
        base_query = select(Festival)

        # Apply search filter
        if search:
            search_term = f"%{search.lower()}%"
            base_query = base_query.where(
                or_(
                    func.lower(Festival.name).like(search_term),
                    func.lower(Festival.venue).like(search_term),
                )
            )

        # Apply location filter
        if location:
            base_query = base_query.where(
                func.lower(Festival.location).like(f"%{location.lower()}%")
            )

        # Apply date filters
        if from_date:
            # Filter festivals that have at least one date >= from_date
            base_query = base_query.where(func.array_length(Festival.dates, 1) > 0)

        if to_date:
            # Filter festivals that have at least one date <= to_date
            base_query = base_query.where(func.array_length(Festival.dates, 1) > 0)

        # Get total count (with filters applied)
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar()

        # Apply ordering
        order_column = getattr(Festival, order_by, Festival.created_at)
        if order_desc:
            base_query = base_query.order_by(order_column.desc())
        else:
            base_query = base_query.order_by(order_column.asc())

        # Apply pagination
        offset = (page - 1) * per_page
        base_query = base_query.limit(per_page).offset(offset)

        # Execute query
        result = await self.db.execute(base_query)
        festivals = list(result.scalars().all())

        total_count_int = total_count if total_count is not None else 0

        return festivals, total_count_int

    async def get_by_location(self, location: str, limit: int = 10) -> List[Festival]:
        """
        Get festivals by location.

        Args:
            location: Location to search for
            limit: Maximum number of festivals to return

        Returns:
            List of festivals in the specified location
        """
        result = await self.db.execute(
            select(Festival)
            .where(func.lower(Festival.location).like(f"%{location.lower()}%"))
            .order_by(Festival.created_at.desc())
            .limit(limit)
        )

        return list(result.scalars().all())

    async def exists_by_name(self, name: str) -> bool:
        """
        Check if festival exists by name.

        Args:
            name: Festival name

        Returns:
            True if festival exists, False otherwise
        """
        result = await self.db.execute(
            select(func.count(Festival.id)).where(Festival.name == name)
        )
        count = result.scalar()
        return count is not None and count > 0

    async def count_by_location(self, location: str) -> int:
        """
        Get count of festivals in a specific location.

        Args:
            location: Location to count festivals for

        Returns:
            Number of festivals in the location
        """
        result = await self.db.execute(
            select(func.count(Festival.id)).where(
                func.lower(Festival.location).like(f"%{location.lower()}%")
            )
        )
        count = result.scalar()
        return count if count is not None else 0

    async def count_total(self) -> int:
        """
        Get total count of all festivals.

        Returns:
            Total number of festivals
        """
        result = await self.db.execute(select(func.count(Festival.id)))
        count = result.scalar()
        return count if count is not None else 0
