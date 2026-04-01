"""Tests for cache optimization: CacheTTL config, CachePrefix, and cache stats.

Requirements: US-7.4
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest_asyncio

from festival_playlist_generator.core.cache_config import CachePrefix, CacheTTL
from festival_playlist_generator.models.artist import Artist
from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.models.playlist import Playlist
from festival_playlist_generator.services.artist_service import ArtistService
from festival_playlist_generator.services.cache_service import CacheService
from festival_playlist_generator.services.festival_service import FestivalService
from festival_playlist_generator.services.playlist_service import PlaylistService

# ============================================================================
# CacheTTL Configuration Tests
# ============================================================================


class TestCacheTTL:
    """Verify centralized TTL values are sensible."""

    def test_artist_ttls_are_longer_than_search(self) -> None:
        """Artist individual lookups should have longer TTL than search."""
        assert CacheTTL.ARTIST_BY_ID > CacheTTL.ARTIST_SEARCH
        assert CacheTTL.ARTIST_BY_NAME > CacheTTL.ARTIST_SEARCH

    def test_festival_ttls_are_moderate(self) -> None:
        """Festival individual lookups should be 30 min."""
        assert CacheTTL.FESTIVAL_BY_ID == 1800
        assert CacheTTL.FESTIVAL_BY_NAME == 1800

    def test_playlist_ttls_are_shorter(self) -> None:
        """Playlist TTLs should be shorter than artist/festival."""
        assert CacheTTL.PLAYLIST_BY_ID < CacheTTL.ARTIST_BY_ID
        assert CacheTTL.PLAYLIST_BY_ID < CacheTTL.FESTIVAL_BY_ID

    def test_setlist_ttl_is_longest(self) -> None:
        """Setlist data is very static, should have 24h TTL."""
        assert CacheTTL.SETLIST_DATA == 86400
        assert CacheTTL.SETLIST_DATA > CacheTTL.ARTIST_BY_ID

    def test_all_ttls_are_positive(self) -> None:
        """All TTL values must be positive integers."""
        for attr in dir(CacheTTL):
            if attr.isupper() and not attr.startswith("_"):
                value = getattr(CacheTTL, attr)
                assert isinstance(value, int)
                assert value > 0, f"CacheTTL.{attr} must be positive"


class TestCachePrefix:
    """Verify cache key prefix constants."""

    def test_prefixes_end_with_colon(self) -> None:
        """All prefixes should end with colon for clean key construction."""
        for attr in dir(CachePrefix):
            if attr.isupper() and not attr.startswith("_"):
                value = getattr(CachePrefix, attr)
                assert isinstance(value, str)
                assert value.endswith(":"), f"CachePrefix.{attr} must end with ':'"

    def test_singular_and_plural_prefixes_exist(self) -> None:
        """Both singular and plural prefixes should exist for each domain."""
        assert CachePrefix.ARTIST == "artist:"
        assert CachePrefix.ARTISTS == "artists:"
        assert CachePrefix.FESTIVAL == "festival:"
        assert CachePrefix.FESTIVALS == "festivals:"
        assert CachePrefix.PLAYLIST == "playlist:"
        assert CachePrefix.PLAYLISTS == "playlists:"


# ============================================================================
# CacheService.get_stats Tests
# ============================================================================


class TestCacheServiceStats:
    """Test CacheService.get_stats method."""

    @pytest_asyncio.fixture
    async def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def cache_service(self, mock_redis: AsyncMock) -> CacheService:
        """Create CacheService with mocked Redis."""
        return CacheService(redis_client=mock_redis)

    async def test_get_stats_returns_key_counts(
        self, cache_service: CacheService, mock_redis: AsyncMock
    ) -> None:
        """get_stats should return key counts per prefix."""

        async def mock_scan_iter(match: str = "") -> AsyncMock:
            # Return some keys for artist prefix, none for others
            if match == "artist:*":
                keys = ["artist:1", "artist:2"]
            elif match == "festivals:*":
                keys = ["festivals:upcoming:10"]
            else:
                keys = []
            for key in keys:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.info = AsyncMock(return_value={"used_memory": 1024})

        stats = await cache_service.get_stats()

        assert stats["total_keys"] == 3
        key_counts = stats["key_counts"]
        assert key_counts["artist"] == 2
        assert key_counts["festivals"] == 1
        assert stats["memory_usage_bytes"] == 1024

    async def test_get_stats_handles_empty_cache(
        self, cache_service: CacheService, mock_redis: AsyncMock
    ) -> None:
        """get_stats should handle an empty cache gracefully."""

        async def mock_scan_iter(match: str = "") -> AsyncMock:
            return
            yield  # type: ignore[misc]  # noqa: B027 - async generator

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.info = AsyncMock(return_value={"used_memory": 0})

        stats = await cache_service.get_stats()

        assert stats["total_keys"] == 0

    async def test_get_stats_handles_redis_error(
        self, cache_service: CacheService, mock_redis: AsyncMock
    ) -> None:
        """get_stats should return defaults on Redis error."""
        mock_redis.scan_iter = AsyncMock(side_effect=Exception("Connection refused"))

        stats = await cache_service.get_stats()

        assert stats["total_keys"] == 0
        assert stats["key_counts"] == {}


# ============================================================================
# Service TTL Integration Tests
# ============================================================================


class TestArtistServiceTTLs:
    """Verify ArtistService uses centralized TTL values."""

    @pytest_asyncio.fixture
    async def mock_cache(self) -> AsyncMock:
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest_asyncio.fixture
    async def service(
        self, mock_repo: AsyncMock, mock_cache: AsyncMock
    ) -> ArtistService:
        return ArtistService(mock_repo, mock_cache)

    async def test_get_artist_by_id_uses_correct_ttl(
        self,
        service: ArtistService,
        mock_cache: AsyncMock,
        mock_repo: AsyncMock,
    ) -> None:
        """get_artist_by_id should cache with ARTIST_BY_ID TTL."""
        artist = Artist(id=uuid4(), name="Test")
        mock_cache.get.return_value = None
        mock_repo.get_by_id.return_value = artist

        await service.get_artist_by_id(artist.id)

        mock_cache.set.assert_called_once()
        call_kwargs = mock_cache.set.call_args
        assert call_kwargs[1]["ttl"] == CacheTTL.ARTIST_BY_ID

    async def test_get_artist_by_name_uses_correct_ttl(
        self,
        service: ArtistService,
        mock_cache: AsyncMock,
        mock_repo: AsyncMock,
    ) -> None:
        """get_artist_by_name should cache with ARTIST_BY_NAME TTL."""
        artist = Artist(id=uuid4(), name="Test")
        mock_cache.get.return_value = None
        mock_repo.get_by_name.return_value = artist

        await service.get_artist_by_name("Test")

        mock_cache.set.assert_called_once()
        call_kwargs = mock_cache.set.call_args
        assert call_kwargs[1]["ttl"] == CacheTTL.ARTIST_BY_NAME

    async def test_get_artist_count_uses_correct_ttl(
        self,
        service: ArtistService,
        mock_cache: AsyncMock,
        mock_repo: AsyncMock,
    ) -> None:
        """get_artist_count should cache with ARTIST_COUNT TTL."""
        mock_cache.get.return_value = None
        mock_repo.count_total.return_value = 42

        await service.get_artist_count()

        mock_cache.set.assert_called_once()
        call_kwargs = mock_cache.set.call_args
        assert call_kwargs[1]["ttl"] == CacheTTL.ARTIST_COUNT


class TestFestivalServiceTTLs:
    """Verify FestivalService uses centralized TTL values."""

    @pytest_asyncio.fixture
    async def mock_cache(self) -> AsyncMock:
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_festival_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_artist_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest_asyncio.fixture
    async def service(
        self,
        mock_festival_repo: AsyncMock,
        mock_artist_repo: AsyncMock,
        mock_cache: AsyncMock,
    ) -> FestivalService:
        return FestivalService(mock_festival_repo, mock_artist_repo, mock_cache)

    async def test_get_festival_by_id_uses_correct_ttl(
        self,
        service: FestivalService,
        mock_cache: AsyncMock,
        mock_festival_repo: AsyncMock,
    ) -> None:
        """get_festival_by_id should cache with FESTIVAL_BY_ID TTL (30 min)."""
        festival = Festival(id=uuid4(), name="Fest")
        mock_cache.get.return_value = None
        mock_festival_repo.get_by_id.return_value = festival

        await service.get_festival_by_id(festival.id)

        mock_cache.set.assert_called_once()
        call_kwargs = mock_cache.set.call_args
        assert call_kwargs[1]["ttl"] == CacheTTL.FESTIVAL_BY_ID

    async def test_get_upcoming_festivals_uses_correct_ttl(
        self,
        service: FestivalService,
        mock_cache: AsyncMock,
        mock_festival_repo: AsyncMock,
    ) -> None:
        """get_upcoming_festivals should cache with FESTIVAL_UPCOMING TTL."""
        mock_cache.get.return_value = None
        mock_festival_repo.get_upcoming_festivals.return_value = []

        await service.get_upcoming_festivals()

        mock_cache.set.assert_called_once()
        call_kwargs = mock_cache.set.call_args
        assert call_kwargs[1]["ttl"] == CacheTTL.FESTIVAL_UPCOMING


class TestPlaylistServiceTTLs:
    """Verify PlaylistService uses centralized TTL values."""

    @pytest_asyncio.fixture
    async def mock_cache(self) -> AsyncMock:
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_playlist_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_festival_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest_asyncio.fixture
    async def service(
        self,
        mock_playlist_repo: AsyncMock,
        mock_festival_repo: AsyncMock,
        mock_cache: AsyncMock,
    ) -> PlaylistService:
        return PlaylistService(mock_playlist_repo, mock_festival_repo, mock_cache)

    async def test_get_playlist_by_id_uses_correct_ttl(
        self,
        service: PlaylistService,
        mock_cache: AsyncMock,
        mock_playlist_repo: AsyncMock,
    ) -> None:
        """get_playlist_by_id should cache with PLAYLIST_BY_ID TTL (15 min)."""
        playlist = Playlist(id=uuid4(), name="PL")
        mock_cache.get.return_value = None
        mock_playlist_repo.get_by_id.return_value = playlist

        await service.get_playlist_by_id(playlist.id)

        mock_cache.set.assert_called_once()
        call_kwargs = mock_cache.set.call_args
        assert call_kwargs[1]["ttl"] == CacheTTL.PLAYLIST_BY_ID

    async def test_get_user_playlists_uses_correct_ttl(
        self,
        service: PlaylistService,
        mock_cache: AsyncMock,
        mock_playlist_repo: AsyncMock,
    ) -> None:
        """get_user_playlists should cache with PLAYLIST_USER TTL."""
        mock_cache.get.return_value = None
        mock_playlist_repo.get_by_user.return_value = []

        await service.get_user_playlists(uuid4())

        mock_cache.set.assert_called_once()
        call_kwargs = mock_cache.set.call_args
        assert call_kwargs[1]["ttl"] == CacheTTL.PLAYLIST_USER
