"""Artist service for business logic with caching."""

import logging
from typing import List, Optional, Tuple
from uuid import UUID

from festival_playlist_generator.models.artist import Artist
from festival_playlist_generator.repositories.artist_repository import ArtistRepository
from festival_playlist_generator.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class ArtistService:
    """
    Service layer for artist business logic.

    Handles artist operations with caching strategy:
    - get_artist_by_id: 1 hour TTL
    - search_artists: 5 minute TTL
    - Cache invalidation on create/update/delete

    Requirements: US-4.2, US-4.6
    """

    def __init__(
        self, artist_repository: ArtistRepository, cache_service: CacheService
    ):
        """
        Initialize artist service.

        Args:
            artist_repository: Repository for artist data access
            cache_service: Service for caching operations
        """
        self.artist_repo = artist_repository
        self.cache = cache_service

    async def get_artist_by_id(
        self, artist_id: UUID, load_relationships: bool = False
    ) -> Optional[Artist]:
        """
        Get artist by ID with caching (1 hour TTL).

        Args:
            artist_id: Artist UUID
            load_relationships: Whether to load festivals and setlists

        Returns:
            Artist or None if not found
        """
        # Generate cache key
        cache_key = f"artist:{artist_id}:relationships:{load_relationships}"

        # Check cache first
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for artist {artist_id}")
            # Note: Cached data is dict, would need to reconstruct Artist model
            # For now, skip cache for complex objects with relationships
            if not load_relationships:
                return cached

        # Fetch from database
        artist = await self.artist_repo.get_by_id(artist_id, load_relationships)

        # Cache result (1 hour TTL)
        if artist and not load_relationships:
            # Only cache simple artist data without relationships
            await self.cache.set(cache_key, artist, ttl=3600)
            logger.debug(f"Cached artist {artist_id}")

        return artist

    async def get_artist_by_name(self, name: str) -> Optional[Artist]:
        """
        Get artist by exact name match.

        Args:
            name: Artist name

        Returns:
            Artist or None if not found
        """
        # Check cache
        cache_key = f"artist:name:{name}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for artist name {name}")
            return cached

        # Fetch from database
        artist = await self.artist_repo.get_by_name(name)

        # Cache result (1 hour TTL)
        if artist:
            await self.cache.set(cache_key, artist, ttl=3600)

        return artist

    async def get_artist_by_spotify_id(self, spotify_id: str) -> Optional[Artist]:
        """
        Get artist by Spotify ID.

        Args:
            spotify_id: Spotify artist ID

        Returns:
            Artist or None if not found
        """
        # Check cache
        cache_key = f"artist:spotify:{spotify_id}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for Spotify ID {spotify_id}")
            return cached

        # Fetch from database
        artist = await self.artist_repo.get_by_spotify_id(spotify_id)

        # Cache result (1 hour TTL)
        if artist:
            await self.cache.set(cache_key, artist, ttl=3600)

        return artist

    async def search_artists(
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
        Search artists with caching (5 minute TTL).

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
        # Generate cache key from search parameters
        cache_key = (
            f"artists:search:{search}:{filter_orphaned}:{filter_with_festivals}:"
            f"{page}:{per_page}:{order_by}:{order_desc}"
        )

        # Check cache first
        # Note: Caching disabled for complex objects to avoid serialization issues
        # cached = await self.cache.get(cache_key)
        # if cached is not None:
        #     logger.debug(f"Cache hit for artist search")
        #     return cached.get("artists", []), cached.get("total", 0)

        # Fetch from database
        artists, total = await self.artist_repo.search_paginated(
            search=search,
            filter_orphaned=filter_orphaned,
            filter_with_festivals=filter_with_festivals,
            page=page,
            per_page=per_page,
            order_by=order_by,
            order_desc=order_desc,
        )

        # Cache result (5 minute TTL)
        # Note: Caching disabled for complex objects to avoid serialization issues
        # cache_data = {"artists": artists, "total": total}
        # await self.cache.set(cache_key, cache_data, ttl=300)
        # logger.debug(f"Cached artist search results")

        return artists, total

    async def create_artist(self, artist: Artist) -> Artist:
        """
        Create a new artist.

        Args:
            artist: Artist instance to create

        Returns:
            Created artist with generated ID
        """
        # Create in database
        created_artist = await self.artist_repo.create(artist)

        # Invalidate search caches
        await self._invalidate_search_caches()

        logger.info(f"Created artist {created_artist.id}: {created_artist.name}")
        return created_artist

    async def update_artist(self, artist: Artist) -> Artist:
        """
        Update an existing artist.

        Args:
            artist: Artist instance to update

        Returns:
            Updated artist
        """
        # Update in database
        updated_artist = await self.artist_repo.update(artist)

        # Invalidate caches for this artist
        await self._invalidate_artist_caches(artist.id)

        # Invalidate search caches
        await self._invalidate_search_caches()

        logger.info(f"Updated artist {artist.id}: {artist.name}")
        return updated_artist

    async def delete_artist(self, artist_id: UUID) -> bool:
        """
        Delete an artist.

        Args:
            artist_id: Artist UUID to delete

        Returns:
            True if deleted, False if not found
        """
        # Delete from database
        deleted = await self.artist_repo.delete(artist_id)

        if deleted:
            # Invalidate caches for this artist
            await self._invalidate_artist_caches(artist_id)

            # Invalidate search caches
            await self._invalidate_search_caches()

            logger.info(f"Deleted artist {artist_id}")

        return deleted

    async def bulk_delete_artists(self, artist_ids: List[UUID]) -> int:
        """
        Delete multiple artists.

        Args:
            artist_ids: List of artist UUIDs to delete

        Returns:
            Number of artists deleted
        """
        # Delete from database
        count = await self.artist_repo.bulk_delete(artist_ids)

        if count > 0:
            # Invalidate caches for all deleted artists
            for artist_id in artist_ids:
                await self._invalidate_artist_caches(artist_id)

            # Invalidate search caches
            await self._invalidate_search_caches()

            logger.info(f"Bulk deleted {count} artists")

        return count

    async def get_artist_count(self) -> int:
        """
        Get total count of all artists.

        Returns:
            Total number of artists
        """
        # Check cache
        cache_key = "artists:count:total"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Fetch from database
        count = await self.artist_repo.count_total()

        # Cache result (5 minute TTL)
        await self.cache.set(cache_key, count, ttl=300)

        return count

    async def get_orphaned_artist_count(self) -> int:
        """
        Get count of orphaned artists.

        Returns:
            Number of orphaned artists
        """
        # Check cache
        cache_key = "artists:count:orphaned"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Fetch from database
        count = await self.artist_repo.count_orphaned()

        # Cache result (5 minute TTL)
        await self.cache.set(cache_key, count, ttl=300)

        return count

    async def _invalidate_artist_caches(self, artist_id: UUID):
        """
        Invalidate all caches related to a specific artist.

        Args:
            artist_id: Artist UUID
        """
        # Delete specific artist caches
        await self.cache.delete(f"artist:{artist_id}:relationships:True")
        await self.cache.delete(f"artist:{artist_id}:relationships:False")

        logger.debug(f"Invalidated caches for artist {artist_id}")

    async def _invalidate_search_caches(self):
        """Invalidate all artist search and count caches."""
        # Delete all search result caches
        await self.cache.delete_pattern("artists:search:*")

        # Delete count caches
        await self.cache.delete("artists:count:total")
        await self.cache.delete("artists:count:orphaned")

        logger.debug("Invalidated artist search caches")
