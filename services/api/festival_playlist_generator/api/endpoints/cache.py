"""Cache statistics and management endpoints.

Requirements: US-7.4
"""

from typing import Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from festival_playlist_generator.core.cache_config import CacheTTL
from festival_playlist_generator.core.container import get_cache_service
from festival_playlist_generator.services.cache_service import CacheService

router = APIRouter()


@router.get("/stats")
async def get_cache_stats(
    cache_service: CacheService = Depends(get_cache_service),
) -> JSONResponse:
    """Return cache statistics including key counts and memory usage."""
    stats = await cache_service.get_stats()
    return JSONResponse(content={"status": "ok", "cache": stats})


@router.get("/config")
async def get_cache_config() -> JSONResponse:
    """Return the current cache TTL configuration."""
    ttl_config: Dict[str, int] = {
        "artist_by_id": CacheTTL.ARTIST_BY_ID,
        "artist_by_name": CacheTTL.ARTIST_BY_NAME,
        "artist_by_spotify_id": CacheTTL.ARTIST_BY_SPOTIFY_ID,
        "artist_search": CacheTTL.ARTIST_SEARCH,
        "artist_count": CacheTTL.ARTIST_COUNT,
        "festival_by_id": CacheTTL.FESTIVAL_BY_ID,
        "festival_by_name": CacheTTL.FESTIVAL_BY_NAME,
        "festival_upcoming": CacheTTL.FESTIVAL_UPCOMING,
        "festival_search": CacheTTL.FESTIVAL_SEARCH,
        "festival_count": CacheTTL.FESTIVAL_COUNT,
        "playlist_by_id": CacheTTL.PLAYLIST_BY_ID,
        "playlist_by_spotify_id": CacheTTL.PLAYLIST_BY_SPOTIFY_ID,
        "playlist_user": CacheTTL.PLAYLIST_USER,
        "playlist_festival": CacheTTL.PLAYLIST_FESTIVAL,
        "setlist_data": CacheTTL.SETLIST_DATA,
        "default": CacheTTL.DEFAULT,
    }
    return JSONResponse(content={"status": "ok", "ttl_seconds": ttl_config})
