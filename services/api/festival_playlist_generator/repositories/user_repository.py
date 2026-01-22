"""User repository for database operations."""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from festival_playlist_generator.models.user import User
from festival_playlist_generator.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User database operations following enterprise patterns."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the user repository.

        Args:
            db: Async database session
        """
        super().__init__(db, User)

    async def get_by_id(
        self, user_id: UUID, load_relationships: bool = False
    ) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User UUID
            load_relationships: Whether to load playlists and song preferences

        Returns:
            User or None if not found
        """
        query = select(User).where(User.id == user_id)

        if load_relationships:
            query = query.options(
                selectinload(User.playlists), selectinload(User.song_preferences)
            )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: User email

        Returns:
            User or None if not found
        """
        result = await self.db.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Get user by display name (username).

        Args:
            username: User display name

        Returns:
            User or None if not found
        """
        result = await self.db.execute(
            select(User).where(func.lower(User.display_name) == username.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_oauth_provider(
        self, provider: str, provider_id: str
    ) -> Optional[User]:
        """
        Get user by OAuth provider and provider ID.

        Args:
            provider: OAuth provider name (e.g., 'spotify', 'google')
            provider_id: Provider-specific user ID

        Returns:
            User or None if not found
        """
        result = await self.db.execute(
            select(User).where(
                User.oauth_provider == provider, User.oauth_provider_id == provider_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_spotify_id(self, spotify_id: str) -> Optional[User]:
        """
        Get user by Spotify ID.

        Args:
            spotify_id: Spotify user ID

        Returns:
            User or None if not found
        """
        return await self.get_by_oauth_provider("spotify", spotify_id)

    async def exists_by_email(self, email: str) -> bool:
        """
        Check if user exists by email.

        Args:
            email: User email

        Returns:
            True if user exists, False otherwise
        """
        result = await self.db.execute(
            select(func.count(User.id)).where(func.lower(User.email) == email.lower())
        )
        count = result.scalar()
        return count is not None and count > 0

    async def exists_by_oauth_provider(self, provider: str, provider_id: str) -> bool:
        """
        Check if user exists by OAuth provider.

        Args:
            provider: OAuth provider name
            provider_id: Provider-specific user ID

        Returns:
            True if user exists, False otherwise
        """
        result = await self.db.execute(
            select(func.count(User.id)).where(
                User.oauth_provider == provider, User.oauth_provider_id == provider_id
            )
        )
        count = result.scalar()
        return count is not None and count > 0

    async def update_last_login(self, user_id: UUID) -> bool:
        """
        Update user's last login timestamp.

        Args:
            user_id: User UUID

        Returns:
            True if updated, False if user not found
        """
        result = await self.db.execute(
            update(User).where(User.id == user_id).values(last_login=datetime.utcnow())
        )
        rowcount = cast(Any, result).rowcount
        return rowcount is not None and rowcount > 0

    async def update_preferences(
        self, user_id: UUID, preferences: Dict[str, Any]
    ) -> bool:
        """
        Update user preferences.

        Args:
            user_id: User UUID
            preferences: User preferences dictionary

        Returns:
            True if updated, False if user not found
        """
        result = await self.db.execute(
            update(User).where(User.id == user_id).values(preferences=preferences)
        )
        rowcount = cast(Any, result).rowcount
        return rowcount is not None and rowcount > 0

    async def add_connected_platform(self, user_id: UUID, platform: str) -> bool:
        """
        Add a connected platform to user's account.

        Args:
            user_id: User UUID
            platform: Platform name (e.g., 'spotify', 'youtube')

        Returns:
            True if updated, False if user not found
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False

        if user.connected_platforms is None:
            user.connected_platforms = []

        if platform not in user.connected_platforms:
            user.connected_platforms.append(platform)
            await self.db.flush()

        return True

    async def remove_connected_platform(self, user_id: UUID, platform: str) -> bool:
        """
        Remove a connected platform from user's account.

        Args:
            user_id: User UUID
            platform: Platform name

        Returns:
            True if updated, False if user not found or platform not connected
        """
        user = await self.get_by_id(user_id)
        if not user or not user.connected_platforms:
            return False

        if platform in user.connected_platforms:
            user.connected_platforms.remove(platform)
            await self.db.flush()
            return True

        return False

    async def add_festival_to_history(self, user_id: UUID, festival_id: UUID) -> bool:
        """
        Add a festival to user's history.

        Args:
            user_id: User UUID
            festival_id: Festival UUID

        Returns:
            True if updated, False if user not found
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False

        if user.festival_history is None:
            user.festival_history = []

        if festival_id not in user.festival_history:
            user.festival_history.append(festival_id)
            await self.db.flush()

        return True

    async def get_users_with_marketing_opt_in(
        self, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """
        Get users who opted in to marketing communications.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of users with marketing opt-in
        """
        result = await self.db.execute(
            select(User)
            .where(User.marketing_opt_in == True)
            .order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all())

    async def count_by_oauth_provider(self, provider: str) -> int:
        """
        Get count of users by OAuth provider.

        Args:
            provider: OAuth provider name

        Returns:
            Number of users using the provider
        """
        result = await self.db.execute(
            select(func.count(User.id)).where(User.oauth_provider == provider)
        )
        count = result.scalar()
        return count if count is not None else 0

    async def count_with_marketing_opt_in(self) -> int:
        """
        Get count of users with marketing opt-in.

        Returns:
            Number of users with marketing opt-in
        """
        result = await self.db.execute(
            select(func.count(User.id)).where(User.marketing_opt_in == True)
        )
        count = result.scalar()
        return count if count is not None else 0

    async def get_recently_active(self, days: int = 30, limit: int = 100) -> List[User]:
        """
        Get recently active users.

        Args:
            days: Number of days to look back
            limit: Maximum number of users to return

        Returns:
            List of recently active users
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(User)
            .where(User.last_login >= cutoff_date)
            .order_by(User.last_login.desc())
            .limit(limit)
        )

        return list(result.scalars().all())


# Import timedelta for recently_active method
from datetime import timedelta
