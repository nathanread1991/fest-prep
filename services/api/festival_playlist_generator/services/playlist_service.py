"""Playlist service for business logic with Spotify integration and circuit breaker."""

import logging
from typing import List, Optional
from uuid import UUID

from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.models.playlist import Playlist
from festival_playlist_generator.repositories.festival_repository import (
    FestivalRepository,
)
from festival_playlist_generator.repositories.playlist_repository import (
    PlaylistRepository,
)
from festival_playlist_generator.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class PlaylistService:
    """
    Service layer for playlist business logic.

    Handles playlist operations with:
    - Caching strategy
    - Festival validation
    - Spotify API integration with circuit breaker (via SpotifyService)
    - Retry logic with exponential backoff

    Requirements: US-4.2, US-4.6, US-7.6
    """

    def __init__(
        self,
        playlist_repository: PlaylistRepository,
        festival_repository: FestivalRepository,
        cache_service: CacheService,
        spotify_service: Optional["SpotifyService"] = None,
    ):
        """
        Initialize playlist service.

        Args:
            playlist_repository: Repository for playlist data access
            festival_repository: Repository for festival data access
            cache_service: Service for caching operations
            spotify_service: Optional Spotify service for API integration
        """
        self.playlist_repo = playlist_repository
        self.festival_repo = festival_repository
        self.cache = cache_service
        self.spotify_service = spotify_service

    async def get_playlist_by_id(
        self, playlist_id: UUID, load_relationships: bool = False
    ) -> Optional[Playlist]:
        """
        Get playlist by ID with caching.

        Args:
            playlist_id: Playlist UUID
            load_relationships: Whether to load festival and tracks

        Returns:
            Playlist or None if not found
        """
        # Generate cache key
        cache_key = f"playlist:{playlist_id}:relationships:{load_relationships}"

        # Check cache first
        cached = await self.cache.get(cache_key)
        if cached is not None and not load_relationships:
            logger.debug(f"Cache hit for playlist {playlist_id}")
            return cached

        # Fetch from database
        playlist = await self.playlist_repo.get_by_id(playlist_id, load_relationships)

        # Cache result (1 hour TTL) - only simple data without relationships
        if playlist and not load_relationships:
            await self.cache.set(cache_key, playlist, ttl=3600)
            logger.debug(f"Cached playlist {playlist_id}")

        return playlist

    async def get_playlist_by_spotify_id(self, spotify_id: str) -> Optional[Playlist]:
        """
        Get playlist by Spotify ID.

        Args:
            spotify_id: Spotify playlist ID

        Returns:
            Playlist or None if not found
        """
        # Check cache
        cache_key = f"playlist:spotify:{spotify_id}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for Spotify playlist {spotify_id}")
            return cached

        # Fetch from database
        playlist = await self.playlist_repo.get_by_spotify_id(spotify_id)

        # Cache result (1 hour TTL)
        if playlist:
            await self.cache.set(cache_key, playlist, ttl=3600)

        return playlist

    async def get_user_playlists(
        self, user_id: UUID, skip: int = 0, limit: int = 20
    ) -> List[Playlist]:
        """
        Get all playlists for a user.

        Args:
            user_id: User UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of playlists
        """
        # Check cache
        cache_key = f"playlists:user:{user_id}:{skip}:{limit}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for user {user_id} playlists")
            return cached

        # Fetch from database
        playlists = await self.playlist_repo.get_by_user(user_id, skip, limit)

        # Cache result (5 minute TTL)
        await self.cache.set(cache_key, playlists, ttl=300)

        return playlists

    async def get_festival_playlists(
        self, festival_id: UUID, skip: int = 0, limit: int = 20
    ) -> List[Playlist]:
        """
        Get all playlists for a festival.

        Args:
            festival_id: Festival UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of playlists
        """
        # Check cache
        cache_key = f"playlists:festival:{festival_id}:{skip}:{limit}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for festival {festival_id} playlists")
            return cached

        # Fetch from database
        playlists = await self.playlist_repo.get_by_festival(festival_id, skip, limit)

        # Cache result (5 minute TTL)
        await self.cache.set(cache_key, playlists, ttl=300)

        return playlists

    async def create_playlist(
        self, playlist: Playlist, festival_id: Optional[UUID] = None
    ) -> Playlist:
        """
        Create a new playlist with festival validation.

        Args:
            playlist: Playlist instance to create
            festival_id: Optional festival UUID to associate

        Returns:
            Created playlist with generated ID

        Raises:
            ValueError: If festival ID is invalid
        """
        # Validate festival if provided
        if festival_id:
            festival = await self.festival_repo.get_by_id(festival_id)
            if not festival:
                raise ValueError(f"Festival {festival_id} not found")
            playlist.festival_id = festival_id

        # Create in database
        created_playlist = await self.playlist_repo.create(playlist)

        # Invalidate user and festival playlist caches
        if playlist.user_id:
            await self.cache.delete_pattern(f"playlists:user:{playlist.user_id}:*")
        if festival_id:
            await self.cache.delete_pattern(f"playlists:festival:{festival_id}:*")

        logger.info(f"Created playlist {created_playlist.id}: {created_playlist.name}")
        return created_playlist

    async def update_playlist(self, playlist: Playlist) -> Playlist:
        """
        Update an existing playlist.

        Args:
            playlist: Playlist instance to update

        Returns:
            Updated playlist
        """
        # Update in database
        updated_playlist = await self.playlist_repo.update(playlist)

        # Invalidate caches for this playlist
        await self._invalidate_playlist_caches(playlist.id)

        # Invalidate user and festival playlist caches
        if playlist.user_id:
            await self.cache.delete_pattern(f"playlists:user:{playlist.user_id}:*")
        if playlist.festival_id:
            await self.cache.delete_pattern(
                f"playlists:festival:{playlist.festival_id}:*"
            )

        logger.info(f"Updated playlist {playlist.id}: {playlist.name}")
        return updated_playlist

    async def delete_playlist(self, playlist_id: UUID) -> bool:
        """
        Delete a playlist.

        Args:
            playlist_id: Playlist UUID to delete

        Returns:
            True if deleted, False if not found
        """
        # Get playlist to know user_id and festival_id for cache invalidation
        playlist = await self.playlist_repo.get_by_id(playlist_id)

        # Delete from database
        deleted = await self.playlist_repo.delete(playlist_id)

        if deleted and playlist:
            # Invalidate caches for this playlist
            await self._invalidate_playlist_caches(playlist_id)

            # Invalidate user and festival playlist caches
            if playlist.user_id:
                await self.cache.delete_pattern(f"playlists:user:{playlist.user_id}:*")
            if playlist.festival_id:
                await self.cache.delete_pattern(
                    f"playlists:festival:{playlist.festival_id}:*"
                )

            logger.info(f"Deleted playlist {playlist_id}")

        return deleted

    async def sync_to_spotify(
        self, playlist_id: UUID, user_access_token: str
    ) -> Optional[str]:
        """
        Sync playlist to Spotify with circuit breaker and retry logic.

        Args:
            playlist_id: Playlist UUID to sync
            user_access_token: User's Spotify access token

        Returns:
            Spotify playlist ID if successful, None otherwise

        Raises:
            ValueError: If playlist not found or Spotify service not configured
        """
        if not self.spotify_service:
            raise ValueError("Spotify service not configured")

        # Get playlist with tracks
        playlist = await self.playlist_repo.get_by_id(
            playlist_id, load_relationships=True
        )
        if not playlist:
            raise ValueError(f"Playlist {playlist_id} not found")

        try:
            # Create playlist on Spotify via SpotifyService (with circuit breaker)
            spotify_playlist_id = await self.spotify_service.create_playlist(
                name=playlist.name,
                description=playlist.description or "",
                access_token=user_access_token,
            )

            # Add tracks to Spotify playlist
            if playlist.tracks:
                track_uris = [
                    f"spotify:track:{track.spotify_id}"
                    for track in playlist.tracks
                    if track.spotify_id
                ]
                if track_uris:
                    await self.spotify_service.add_tracks_to_playlist(
                        playlist_id=spotify_playlist_id,
                        track_uris=track_uris,
                        access_token=user_access_token,
                    )

            # Update playlist with Spotify ID
            playlist.spotify_id = spotify_playlist_id
            await self.playlist_repo.update(playlist)

            # Invalidate caches
            await self._invalidate_playlist_caches(playlist_id)

            logger.info(
                f"Synced playlist {playlist_id} to Spotify: {spotify_playlist_id}"
            )
            return spotify_playlist_id

        except Exception as e:
            logger.error(f"Failed to sync playlist {playlist_id} to Spotify: {e}")
            return None

    async def _invalidate_playlist_caches(self, playlist_id: UUID):
        """
        Invalidate all caches related to a specific playlist.

        Args:
            playlist_id: Playlist UUID
        """
        # Delete specific playlist caches
        await self.cache.delete(f"playlist:{playlist_id}:relationships:True")
        await self.cache.delete(f"playlist:{playlist_id}:relationships:False")

        logger.debug(f"Invalidated caches for playlist {playlist_id}")
