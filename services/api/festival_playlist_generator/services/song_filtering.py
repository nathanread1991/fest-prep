"""Song filtering service for user preferences."""

import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.schemas.playlist import Playlist as PlaylistSchema
from festival_playlist_generator.schemas.song import Song as SongSchema
from festival_playlist_generator.services.user_preferences import (
    user_preference_service,
)

logger = logging.getLogger(__name__)


class SongFilteringService:
    """Service for filtering songs based on user preferences."""

    def __init__(self) -> None:
        self.user_preference_service = user_preference_service

    async def filter_playlist_by_preferences(
        self,
        db: AsyncSession,
        playlist: PlaylistSchema,
        user_id: UUID,
        show_known: bool = True,
        show_unknown: bool = True,
    ) -> PlaylistSchema:
        """Filter playlist songs based on user preferences.

        Note: This method returns the playlist as-is since PlaylistSchema
        doesn't contain songs. Use filter_songs_by_preferences for song filtering.
        """
        # PlaylistSchema doesn't have a songs field, so just return the playlist
        return playlist

    async def filter_songs_by_preferences(
        self,
        db: AsyncSession,
        songs: List[SongSchema],
        user_id: UUID,
        show_known: bool = True,
        show_unknown: bool = True,
    ) -> List[SongSchema]:
        """Filter a list of songs based on user preferences."""
        if not show_known and not show_unknown:
            return []

        # Get user preferences
        user_preferences = await self.user_preference_service.get_user_song_preferences(
            db, user_id
        )

        # Create preference lookup
        preference_lookup = {pref.song_id: pref.is_known for pref in user_preferences}

        # Filter songs
        filtered_songs = []
        for song in songs:
            is_known = preference_lookup.get(song.id)

            # If no preference exists, treat as unknown
            if is_known is None:
                if show_unknown:
                    filtered_songs.append(song)
            elif is_known and show_known:
                filtered_songs.append(song)
            elif not is_known and show_unknown:
                filtered_songs.append(song)

        logger.info(f"Filtered songs: {len(songs)} -> {len(filtered_songs)} songs")
        return filtered_songs

    async def get_known_songs_from_list(
        self, db: AsyncSession, songs: List[SongSchema], user_id: UUID
    ) -> List[SongSchema]:
        """Get only known songs from a list."""
        return await self.filter_songs_by_preferences(
            db, songs, user_id, show_known=True, show_unknown=False
        )

    async def get_unknown_songs_from_list(
        self, db: AsyncSession, songs: List[SongSchema], user_id: UUID
    ) -> List[SongSchema]:
        """Get only unknown songs from a list."""
        return await self.filter_songs_by_preferences(
            db, songs, user_id, show_known=False, show_unknown=True
        )

    async def get_song_preference_summary(
        self, db: AsyncSession, songs: List[SongSchema], user_id: UUID
    ) -> Dict[str, Any]:
        """Get summary of song preferences for a list of songs."""
        # Get user preferences
        user_preferences = await self.user_preference_service.get_user_song_preferences(
            db, user_id
        )

        # Create preference lookup
        preference_lookup = {pref.song_id: pref.is_known for pref in user_preferences}

        # Count preferences
        known_count = 0
        unknown_count = 0
        no_preference_count = 0

        for song in songs:
            is_known = preference_lookup.get(song.id)
            if is_known is None:
                no_preference_count += 1
            elif is_known:
                known_count += 1
            else:
                unknown_count += 1

        return {
            "total_songs": len(songs),
            "known_songs": known_count,
            "unknown_songs": unknown_count,
            "no_preference": no_preference_count,
            "known_percentage": (known_count / len(songs) * 100) if songs else 0,
            "unknown_percentage": (unknown_count / len(songs) * 100) if songs else 0,
        }

    def create_filter_toggle_response(
        self, current_show_known: bool, current_show_unknown: bool
    ) -> Dict[str, Any]:
        """Create response for filter toggle functionality."""
        return {
            "show_known": current_show_known,
            "show_unknown": current_show_unknown,
            "filter_description": self._get_filter_description(
                current_show_known, current_show_unknown
            ),
        }

    def _get_filter_description(self, show_known: bool, show_unknown: bool) -> str:
        """Get human-readable description of current filter state."""
        if show_known and show_unknown:
            return "Showing all songs"
        elif show_known and not show_unknown:
            return "Showing only known songs"
        elif not show_known and show_unknown:
            return "Showing only unknown songs"
        else:
            return "Hiding all songs"


# Global song filtering service instance
song_filtering_service = SongFilteringService()
