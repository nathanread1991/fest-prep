"""User song preference tracking service."""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.core.redis import cache
from festival_playlist_generator.models.song import Song
from festival_playlist_generator.models.user import User, UserSongPreference
from festival_playlist_generator.schemas.user import (
    UserSongPreference as UserSongPreferenceSchema,
)
from festival_playlist_generator.schemas.user import (
    UserSongPreferenceCreate,
)

logger = logging.getLogger(__name__)


class UserPreferenceService:
    """Service for managing user song preferences."""

    def __init__(self) -> None:
        self.cache = cache

    async def mark_song_preference(
        self, db: AsyncSession, user_id: UUID, song_id: UUID, is_known: bool
    ) -> UserSongPreferenceSchema:
        """Mark a song as known or unknown for a user."""
        # Check if user exists
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Check if song exists
        song = db.get(Song, song_id)
        if not song:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Song not found"
            )

        # Check if preference already exists
        result = await db.execute(
            select(UserSongPreference).where(
                and_(
                    UserSongPreference.user_id == user_id,
                    UserSongPreference.song_id == song_id,
                )
            )
        )
        existing_preference = result.scalar_one_or_none()

        if existing_preference:
            # Update existing preference
            existing_preference.is_known = is_known
            await db.commit()
            await db.refresh(existing_preference)
            preference = existing_preference
        else:
            # Create new preference
            preference_data = UserSongPreferenceCreate(
                user_id=user_id, song_id=song_id, is_known=is_known
            )
            db_preference = UserSongPreference(**preference_data.model_dump())
            db.add(db_preference)
            await db.commit()
            await db.refresh(db_preference)
            preference = db_preference

        # Update cache
        cache_key = f"user_preferences:{user_id}"
        await self._invalidate_user_preferences_cache(cache_key)

        logger.info(
            f"Song preference updated: user={user_id}, song={song_id}, known={is_known}"
        )
        return UserSongPreferenceSchema.model_validate(preference)

    async def get_user_song_preferences(
        self, db: AsyncSession, user_id: UUID, known_only: Optional[bool] = None
    ) -> List[UserSongPreferenceSchema]:
        """Get all song preferences for a user."""
        # Try cache first
        cache_key = f"user_preferences:{user_id}"
        cached_preferences = await self.cache.get(cache_key)

        if cached_preferences:
            preferences = [
                UserSongPreferenceSchema(**pref) for pref in cached_preferences
            ]
        else:
            # Get from database
            query = select(UserSongPreference).where(
                UserSongPreference.user_id == user_id
            )
            result = await db.execute(query)
            db_preferences = result.scalars().all()
            preferences = [
                UserSongPreferenceSchema.model_validate(pref) for pref in db_preferences
            ]

            # Cache the results
            await self.cache.set(
                cache_key,
                [pref.model_dump() for pref in preferences],
                expire=3600,  # 1 hour
            )

        # Filter by known status if specified
        if known_only is not None:
            preferences = [pref for pref in preferences if pref.is_known == known_only]

        return preferences

    async def get_known_songs(self, db: AsyncSession, user_id: UUID) -> List[UUID]:
        """Get list of song IDs that user has marked as known."""
        preferences = await self.get_user_song_preferences(db, user_id, known_only=True)
        return [pref.song_id for pref in preferences]

    async def get_unknown_songs(self, db: AsyncSession, user_id: UUID) -> List[UUID]:
        """Get list of song IDs that user has marked as unknown."""
        preferences = await self.get_user_song_preferences(
            db, user_id, known_only=False
        )
        return [pref.song_id for pref in preferences]

    async def is_song_known(
        self, db: AsyncSession, user_id: UUID, song_id: UUID
    ) -> Optional[bool]:
        """Check if a specific song is marked as known by user."""
        result = await db.execute(
            select(UserSongPreference).where(
                and_(
                    UserSongPreference.user_id == user_id,
                    UserSongPreference.song_id == song_id,
                )
            )
        )
        preference = result.scalar_one_or_none()

        return preference.is_known if preference else None

    async def bulk_mark_songs(
        self, db: AsyncSession, user_id: UUID, song_preferences: Dict[UUID, bool]
    ) -> List[UserSongPreferenceSchema]:
        """Bulk update song preferences for a user."""
        results = []

        for song_id, is_known in song_preferences.items():
            try:
                preference = await self.mark_song_preference(
                    db, user_id, song_id, is_known
                )
                results.append(preference)
            except HTTPException as e:
                logger.warning(
                    f"Failed to update preference for song {song_id}: {e.detail}"
                )
                continue

        return results

    async def delete_song_preference(
        self, db: AsyncSession, user_id: UUID, song_id: UUID
    ) -> bool:
        """Delete a song preference."""
        result = await db.execute(
            select(UserSongPreference).where(
                and_(
                    UserSongPreference.user_id == user_id,
                    UserSongPreference.song_id == song_id,
                )
            )
        )
        preference = result.scalar_one_or_none()

        if not preference:
            return False

        await db.delete(preference)
        await db.commit()

        # Invalidate cache
        cache_key = f"user_preferences:{user_id}"
        await self._invalidate_user_preferences_cache(cache_key)

        logger.info(f"Song preference deleted: user={user_id}, song={song_id}")
        return True

    async def _invalidate_user_preferences_cache(self, cache_key: str) -> None:
        """Invalidate user preferences cache."""
        await self.cache.delete(cache_key)


# Global user preference service instance
user_preference_service = UserPreferenceService()
