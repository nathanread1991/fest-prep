"""Base repository with generic CRUD operations."""

from abc import ABC
from typing import Any, Callable, Generic, List, Optional, Type, TypeVar, cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Type variable for the model class
T = TypeVar("T", bound=DeclarativeBase)


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository with common CRUD operations.

    This class provides generic database operations that can be inherited
    by specific repository implementations. It follows the Repository pattern
    to abstract database access and provide a clean interface for data operations.

    Type Parameters:
        T: The SQLAlchemy model class this repository manages

    Example:
        class FestivalRepository(BaseRepository[Festival]):
            def __init__(self, db: AsyncSession) -> None:
                super().__init__(db, Festival)
    """

    def __init__(self, db: AsyncSession, model_class: Type[T]) -> None:
        """
        Initialize the repository.

        Args:
            db: Async database session
            model_class: The SQLAlchemy model class to manage
        """
        self.db = db
        self.model_class = model_class

    async def get_by_id(self, id: UUID) -> Optional[T]:
        """
        Get entity by ID.

        Args:
            id: Entity UUID

        Returns:
            Entity instance or None if not found
        """
        result = await self.db.execute(
            select(self.model_class).where(getattr(self.model_class, 'id') == id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> List[T]:
        """
        Get all entities with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Column name to order by
            order_desc: Order descending if True, ascending if False

        Returns:
            List of entity instances
        """
        order_column: Any = getattr(self.model_class, order_by, getattr(self.model_class, 'created_at'))

        query = select(self.model_class)

        if order_desc:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, entity: T) -> T:
        """
        Create a new entity.

        Args:
            entity: Entity instance to create

        Returns:
            Created entity with generated ID and timestamps
        """
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def update(self, entity: T) -> T:
        """
        Update an existing entity.

        Note: The entity should already be attached to the session
        and have its attributes modified before calling this method.

        Args:
            entity: Entity instance to update

        Returns:
            Updated entity with refreshed state
        """
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def delete(self, id: UUID) -> bool:
        """
        Delete an entity by ID.

        Args:
            id: Entity UUID to delete

        Returns:
            True if entity was deleted, False if not found
        """
        result = await self.db.execute(
            delete(self.model_class).where(getattr(self.model_class, 'id') == id)
        )
        # Cast to access rowcount attribute
        rowcount = cast(Any, result).rowcount
        return rowcount is not None and rowcount > 0

    async def bulk_delete(self, ids: List[UUID]) -> int:
        """
        Delete multiple entities by IDs.

        Args:
            ids: List of entity UUIDs to delete

        Returns:
            Number of entities deleted
        """
        result = await self.db.execute(
            delete(self.model_class).where(getattr(self.model_class, 'id').in_(ids))
        )
        # Cast to access rowcount attribute
        rowcount = cast(Any, result).rowcount
        return rowcount if rowcount is not None else 0

    async def exists(self, id: UUID) -> bool:
        """
        Check if an entity exists by ID.

        Args:
            id: Entity UUID to check

        Returns:
            True if entity exists, False otherwise
        """
        result = await self.db.execute(
            select(func.count(getattr(self.model_class, 'id'))).where(getattr(self.model_class, 'id') == id)
        )
        count = result.scalar()
        return count is not None and count > 0

    async def count(self) -> int:
        """
        Get total count of all entities.

        Returns:
            Total number of entities
        """
        result = await self.db.execute(select(func.count(getattr(self.model_class, 'id'))))
        count = result.scalar()
        return count if count is not None else 0

    async def get_all_ids(self) -> List[UUID]:
        """
        Get all entity IDs (useful for bulk operations).

        Returns:
            List of all entity UUIDs
        """
        result = await self.db.execute(select(getattr(self.model_class, 'id')))
        return [row[0] for row in result]
