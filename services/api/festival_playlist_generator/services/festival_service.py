"""Festival service for business logic with caching and artist validation."""

import logging
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime

from festival_playlist_generator.repositories.festival_repository import FestivalRepository
from festival_playlist_generator.repositories.artist_repository import ArtistRepository
from festival_playlist_generator.services.cache_service import CacheService
from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.models.artist import Artist

logger = logging.getLogger(__name__)


class FestivalService:
    """
    Service layer for festival business logic.
    
    Handles festival operations with:
    - Caching strategy (1 hour TTL for get, 5 min for search)
    - Artist validation on create
    - Cache invalidation on create/update/delete
    
    Requirements: US-4.2, US-4.6
    """
    
    def __init__(
        self,
        festival_repository: FestivalRepository,
        artist_repository: ArtistRepository,
        cache_service: CacheService
    ):
        """
        Initialize festival service.
        
        Args:
            festival_repository: Repository for festival data access
            artist_repository: Repository for artist data access
            cache_service: Service for caching operations
        """
        self.festival_repo = festival_repository
        self.artist_repo = artist_repository
        self.cache = cache_service
    
    async def get_festival_by_id(
        self,
        festival_id: UUID,
        load_relationships: bool = False
    ) -> Optional[Festival]:
        """
        Get festival by ID with caching (1 hour TTL).
        
        Args:
            festival_id: Festival UUID
            load_relationships: Whether to load artists and playlists
            
        Returns:
            Festival or None if not found
        """
        # Generate cache key
        cache_key = f"festival:{festival_id}:relationships:{load_relationships}"
        
        # Check cache first
        cached = await self.cache.get(cache_key)
        if cached is not None and not load_relationships:
            logger.debug(f"Cache hit for festival {festival_id}")
            return cached
        
        # Fetch from database
        festival = await self.festival_repo.get_by_id(festival_id, load_relationships)
        
        # Cache result (1 hour TTL) - only simple data without relationships
        if festival and not load_relationships:
            await self.cache.set(cache_key, festival, ttl=3600)
            logger.debug(f"Cached festival {festival_id}")
        
        return festival
    
    async def get_festival_by_name(self, name: str) -> Optional[Festival]:
        """
        Get festival by exact name match.
        
        Args:
            name: Festival name
            
        Returns:
            Festival or None if not found
        """
        # Check cache
        cache_key = f"festival:name:{name}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for festival name {name}")
            return cached
        
        # Fetch from database
        festival = await self.festival_repo.get_by_name(name)
        
        # Cache result (1 hour TTL)
        if festival:
            await self.cache.set(cache_key, festival, ttl=3600)
        
        return festival
    
    async def get_upcoming_festivals(
        self,
        limit: int = 10,
        load_relationships: bool = False
    ) -> List[Festival]:
        """
        Get upcoming festivals ordered by date.
        
        Args:
            limit: Maximum number of festivals to return
            load_relationships: Whether to load artists and playlists
            
        Returns:
            List of upcoming festivals
        """
        # Check cache
        cache_key = f"festivals:upcoming:{limit}:relationships:{load_relationships}"
        cached = await self.cache.get(cache_key)
        if cached is not None and not load_relationships:
            logger.debug("Cache hit for upcoming festivals")
            return cached
        
        # Fetch from database
        festivals = await self.festival_repo.get_upcoming_festivals(limit, load_relationships)
        
        # Cache result (5 minute TTL) - shorter TTL for time-sensitive data
        if not load_relationships:
            await self.cache.set(cache_key, festivals, ttl=300)
        
        return festivals
    
    async def search_festivals(
        self,
        search: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 20,
        order_by: str = "date",
        order_desc: bool = False
    ) -> Tuple[List[Festival], int]:
        """
        Search festivals with caching (5 minute TTL).
        
        Args:
            search: Search term for name/location
            start_date: Filter by start date
            end_date: Filter by end date
            page: Page number (1-indexed)
            per_page: Results per page
            order_by: Column to order by
            order_desc: Order descending if True
            
        Returns:
            Tuple of (festivals list, total count)
        """
        # Generate cache key from search parameters
        cache_key = (
            f"festivals:search:{search}:{start_date}:{end_date}:"
            f"{page}:{per_page}:{order_by}:{order_desc}"
        )
        
        # Check cache first
        # Note: Caching disabled for complex objects to avoid serialization issues
        # cached = await self.cache.get(cache_key)
        # if cached is not None:
        #     logger.debug("Cache hit for festival search")
        #     return cached.get("festivals", []), cached.get("total", 0)
        
        # Fetch from database
        festivals, total = await self.festival_repo.search_paginated(
            search=search,
            from_date=start_date,
            to_date=end_date,
            page=page,
            per_page=per_page,
            order_by=order_by,
            order_desc=order_desc
        )
        
        # Cache result (5 minute TTL)
        # Note: Caching disabled for complex objects to avoid serialization issues
        # cache_data = {"festivals": festivals, "total": total}
        # await self.cache.set(cache_key, cache_data, ttl=300)
        # logger.debug("Cached festival search results")
        
        return festivals, total
    
    async def create_festival(
        self,
        festival: Festival,
        artist_ids: Optional[List[UUID]] = None
    ) -> Festival:
        """
        Create a new festival with artist validation.
        
        Args:
            festival: Festival instance to create
            artist_ids: Optional list of artist UUIDs to associate
            
        Returns:
            Created festival with generated ID
            
        Raises:
            ValueError: If any artist IDs are invalid
        """
        # Validate artists if provided
        if artist_ids:
            artists = await self._validate_artists(artist_ids)
            festival.artists = artists
        
        # Create in database
        created_festival = await self.festival_repo.create(festival)
        
        # Invalidate search caches
        await self._invalidate_search_caches()
        
        logger.info(f"Created festival {created_festival.id}: {created_festival.name}")
        return created_festival
    
    async def update_festival(
        self,
        festival: Festival,
        artist_ids: Optional[List[UUID]] = None
    ) -> Festival:
        """
        Update an existing festival.
        
        Args:
            festival: Festival instance to update
            artist_ids: Optional list of artist UUIDs to associate
            
        Returns:
            Updated festival
            
        Raises:
            ValueError: If any artist IDs are invalid
        """
        # Validate and update artists if provided
        if artist_ids is not None:
            artists = await self._validate_artists(artist_ids)
            festival.artists = artists
        
        # Update in database
        updated_festival = await self.festival_repo.update(festival)
        
        # Invalidate caches for this festival
        await self._invalidate_festival_caches(festival.id)
        
        # Invalidate search caches
        await self._invalidate_search_caches()
        
        logger.info(f"Updated festival {festival.id}: {festival.name}")
        return updated_festival
    
    async def delete_festival(self, festival_id: UUID) -> bool:
        """
        Delete a festival.
        
        Args:
            festival_id: Festival UUID to delete
            
        Returns:
            True if deleted, False if not found
        """
        # Delete from database
        deleted = await self.festival_repo.delete(festival_id)
        
        if deleted:
            # Invalidate caches for this festival
            await self._invalidate_festival_caches(festival_id)
            
            # Invalidate search caches
            await self._invalidate_search_caches()
            
            logger.info(f"Deleted festival {festival_id}")
        
        return deleted
    
    async def add_artist_to_festival(
        self,
        festival_id: UUID,
        artist_id: UUID
    ) -> Festival:
        """
        Add an artist to a festival.
        
        Args:
            festival_id: Festival UUID
            artist_id: Artist UUID to add
            
        Returns:
            Updated festival
            
        Raises:
            ValueError: If festival or artist not found
        """
        # Get festival
        festival = await self.festival_repo.get_by_id(festival_id, load_relationships=True)
        if not festival:
            raise ValueError(f"Festival {festival_id} not found")
        
        # Validate artist
        artist = await self.artist_repo.get_by_id(artist_id)
        if not artist:
            raise ValueError(f"Artist {artist_id} not found")
        
        # Add artist if not already present
        if artist not in festival.artists:
            festival.artists.append(artist)
            updated_festival = await self.festival_repo.update(festival)
            
            # Invalidate caches
            await self._invalidate_festival_caches(festival_id)
            await self._invalidate_search_caches()
            
            logger.info(f"Added artist {artist_id} to festival {festival_id}")
            return updated_festival
        
        return festival
    
    async def remove_artist_from_festival(
        self,
        festival_id: UUID,
        artist_id: UUID
    ) -> Festival:
        """
        Remove an artist from a festival.
        
        Args:
            festival_id: Festival UUID
            artist_id: Artist UUID to remove
            
        Returns:
            Updated festival
            
        Raises:
            ValueError: If festival not found
        """
        # Get festival
        festival = await self.festival_repo.get_by_id(festival_id, load_relationships=True)
        if not festival:
            raise ValueError(f"Festival {festival_id} not found")
        
        # Remove artist if present
        festival.artists = [a for a in festival.artists if a.id != artist_id]
        updated_festival = await self.festival_repo.update(festival)
        
        # Invalidate caches
        await self._invalidate_festival_caches(festival_id)
        await self._invalidate_search_caches()
        
        logger.info(f"Removed artist {artist_id} from festival {festival_id}")
        return updated_festival
    
    async def get_festival_count(self) -> int:
        """
        Get total count of all festivals.
        
        Returns:
            Total number of festivals
        """
        # Check cache
        cache_key = "festivals:count:total"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        # Fetch from database
        count = await self.festival_repo.count_total()
        
        # Cache result (5 minute TTL)
        await self.cache.set(cache_key, count, ttl=300)
        
        return count
    
    async def _validate_artists(self, artist_ids: List[UUID]) -> List[Artist]:
        """
        Validate that all artist IDs exist.
        
        Args:
            artist_ids: List of artist UUIDs to validate
            
        Returns:
            List of Artist instances
            
        Raises:
            ValueError: If any artist ID is invalid
        """
        artists = []
        for artist_id in artist_ids:
            artist = await self.artist_repo.get_by_id(artist_id)
            if not artist:
                raise ValueError(f"Artist {artist_id} not found")
            artists.append(artist)
        
        return artists
    
    async def _invalidate_festival_caches(self, festival_id: UUID):
        """
        Invalidate all caches related to a specific festival.
        
        Args:
            festival_id: Festival UUID
        """
        # Delete specific festival caches
        await self.cache.delete(f"festival:{festival_id}:relationships:True")
        await self.cache.delete(f"festival:{festival_id}:relationships:False")
        
        logger.debug(f"Invalidated caches for festival {festival_id}")
    
    async def _invalidate_search_caches(self):
        """Invalidate all festival search and count caches."""
        # Delete all search result caches
        await self.cache.delete_pattern("festivals:search:*")
        await self.cache.delete_pattern("festivals:upcoming:*")
        
        # Delete count caches
        await self.cache.delete("festivals:count:total")
        
        logger.debug("Invalidated festival search caches")
