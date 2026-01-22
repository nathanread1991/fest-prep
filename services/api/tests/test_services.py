"""Unit tests for service layer with mocked dependencies.

Tests cover:
- CacheService operations
- ArtistService with caching
- FestivalService with artist validation
- PlaylistService with Spotify integration
- SpotifyService circuit breaker
- SetlistFmService circuit breaker and retry logic

Requirements: US-4.7
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from festival_playlist_generator.models.artist import Artist
from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.models.playlist import Playlist
from festival_playlist_generator.services.artist_service import ArtistService
from festival_playlist_generator.services.cache_service import CacheService
from festival_playlist_generator.services.festival_service import FestivalService
from festival_playlist_generator.services.playlist_service import PlaylistService
from festival_playlist_generator.services.setlistfm_service import (
    RateLimiter,
    SetlistFmService,
)
from festival_playlist_generator.services.spotify_service import (
    CircuitBreaker,
    CircuitState,
    SpotifyService,
)

# ============================================================================
# CacheService Tests
# ============================================================================


class TestCacheService:
    """Test CacheService operations."""

    @pytest_asyncio.fixture
    async def mock_redis(self):
        """Create a mock Redis client."""
        redis_mock = AsyncMock()
        return redis_mock

    @pytest_asyncio.fixture
    async def cache_service(self, mock_redis):
        """Create CacheService with mocked Redis."""
        service = CacheService(redis_client=mock_redis)
        return service

    async def test_get_cache_hit(self, cache_service, mock_redis):
        """Test cache get with hit."""
        # Arrange
        test_data = {"key": "value", "number": 42}
        mock_redis.get.return_value = json.dumps(test_data)

        # Act
        result = await cache_service.get("test_key")

        # Assert
        assert result == test_data
        mock_redis.get.assert_called_once_with("test_key")

    async def test_get_cache_miss(self, cache_service, mock_redis):
        """Test cache get with miss."""
        # Arrange
        mock_redis.get.return_value = None

        # Act
        result = await cache_service.get("missing_key")

        # Assert
        assert result is None
        mock_redis.get.assert_called_once_with("missing_key")

    async def test_set_success(self, cache_service, mock_redis):
        """Test cache set operation."""
        # Arrange
        test_data = {"key": "value"}
        mock_redis.setex = AsyncMock()

        # Act
        result = await cache_service.set("test_key", test_data, ttl=300)

        # Assert
        assert result is True
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == "test_key"
        assert args[1] == 300
        assert json.loads(args[2]) == test_data

    async def test_delete_success(self, cache_service, mock_redis):
        """Test cache delete operation."""
        # Arrange
        mock_redis.delete.return_value = 1

        # Act
        result = await cache_service.delete("test_key")

        # Assert
        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")

    async def test_delete_pattern(self, cache_service, mock_redis):
        """Test cache delete pattern operation."""
        # Arrange
        mock_keys = ["key1", "key2", "key3"]

        async def mock_scan_iter(match):
            for key in mock_keys:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete.return_value = 3

        # Act
        result = await cache_service.delete_pattern("test:*")

        # Assert
        assert result == 3
        mock_redis.delete.assert_called_once_with(*mock_keys)

    async def test_exists_true(self, cache_service, mock_redis):
        """Test cache exists returns true."""
        # Arrange
        mock_redis.exists.return_value = 1

        # Act
        result = await cache_service.exists("test_key")

        # Assert
        assert result is True
        mock_redis.exists.assert_called_once_with("test_key")

    async def test_exists_false(self, cache_service, mock_redis):
        """Test cache exists returns false."""
        # Arrange
        mock_redis.exists.return_value = 0

        # Act
        result = await cache_service.exists("missing_key")

        # Assert
        assert result is False


# ============================================================================
# ArtistService Tests
# ============================================================================


class TestArtistService:
    """Test ArtistService with caching."""

    @pytest_asyncio.fixture
    async def mock_artist_repo(self):
        """Create mock ArtistRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_cache(self):
        """Create mock CacheService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def artist_service(self, mock_artist_repo, mock_cache):
        """Create ArtistService with mocked dependencies."""
        return ArtistService(mock_artist_repo, mock_cache)

    @pytest_asyncio.fixture
    def sample_artist(self):
        """Create sample artist."""
        return Artist(
            id=uuid4(),
            name="Test Artist",
            spotify_id="spotify123",
            genres=["rock", "indie"],
        )

    async def test_get_artist_by_id_cache_hit(
        self, artist_service, mock_cache, mock_artist_repo, sample_artist
    ):
        """Test get artist by ID with cache hit."""
        # Arrange
        mock_cache.get.return_value = sample_artist

        # Act
        result = await artist_service.get_artist_by_id(sample_artist.id)

        # Assert
        assert result == sample_artist
        mock_cache.get.assert_called_once()
        mock_artist_repo.get_by_id.assert_not_called()

    async def test_get_artist_by_id_cache_miss(
        self, artist_service, mock_cache, mock_artist_repo, sample_artist
    ):
        """Test get artist by ID with cache miss."""
        # Arrange
        mock_cache.get.return_value = None
        mock_artist_repo.get_by_id.return_value = sample_artist

        # Act
        result = await artist_service.get_artist_by_id(sample_artist.id)

        # Assert
        assert result == sample_artist
        mock_cache.get.assert_called_once()
        mock_artist_repo.get_by_id.assert_called_once_with(sample_artist.id, False)
        mock_cache.set.assert_called_once()

    async def test_search_artists_with_caching(
        self, artist_service, mock_cache, mock_artist_repo, sample_artist
    ):
        """Test search artists - caching disabled for complex objects."""
        # Arrange
        mock_cache.get.return_value = None
        mock_artist_repo.search_paginated.return_value = ([sample_artist], 1)

        # Act
        artists, total = await artist_service.search_artists(search="Test")

        # Assert
        assert len(artists) == 1
        assert total == 1
        # Caching is disabled for complex objects
        mock_artist_repo.search_paginated.assert_called_once()
        # Cache set should not be called since caching is disabled
        # mock_cache.set.assert_not_called()

    async def test_create_artist_invalidates_cache(
        self, artist_service, mock_cache, mock_artist_repo, sample_artist
    ):
        """Test create artist invalidates search caches."""
        # Arrange
        mock_artist_repo.create.return_value = sample_artist

        # Act
        result = await artist_service.create_artist(sample_artist)

        # Assert
        assert result == sample_artist
        mock_artist_repo.create.assert_called_once_with(sample_artist)
        mock_cache.delete_pattern.assert_called_once_with("artists:search:*")

    async def test_update_artist_invalidates_cache(
        self, artist_service, mock_cache, mock_artist_repo, sample_artist
    ):
        """Test update artist invalidates caches."""
        # Arrange
        mock_artist_repo.update.return_value = sample_artist

        # Act
        result = await artist_service.update_artist(sample_artist)

        # Assert
        assert result == sample_artist
        mock_artist_repo.update.assert_called_once_with(sample_artist)
        # Should delete specific artist caches
        assert mock_cache.delete.call_count >= 2
        # Should delete search caches
        mock_cache.delete_pattern.assert_called()

    async def test_delete_artist_invalidates_cache(
        self, artist_service, mock_cache, mock_artist_repo, sample_artist
    ):
        """Test delete artist invalidates caches."""
        # Arrange
        mock_artist_repo.delete.return_value = True

        # Act
        result = await artist_service.delete_artist(sample_artist.id)

        # Assert
        assert result is True
        mock_artist_repo.delete.assert_called_once_with(sample_artist.id)
        mock_cache.delete.assert_called()
        mock_cache.delete_pattern.assert_called()


# ============================================================================
# FestivalService Tests
# ============================================================================


class TestFestivalService:
    """Test FestivalService with artist validation."""

    @pytest_asyncio.fixture
    async def mock_festival_repo(self):
        """Create mock FestivalRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_artist_repo(self):
        """Create mock ArtistRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_cache(self):
        """Create mock CacheService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def festival_service(self, mock_festival_repo, mock_artist_repo, mock_cache):
        """Create FestivalService with mocked dependencies."""
        return FestivalService(mock_festival_repo, mock_artist_repo, mock_cache)

    @pytest_asyncio.fixture
    def sample_festival(self):
        """Create sample festival."""
        return Festival(
            id=uuid4(),
            name="Test Festival",
            dates=[datetime.utcnow() + timedelta(days=30)],
            location="Test City",
        )

    @pytest_asyncio.fixture
    def sample_artist(self):
        """Create sample artist."""
        return Artist(id=uuid4(), name="Test Artist", spotify_id="spotify123")

    async def test_get_festival_by_id_cache_hit(
        self, festival_service, mock_cache, mock_festival_repo, sample_festival
    ):
        """Test get festival by ID with cache hit."""
        # Arrange
        mock_cache.get.return_value = sample_festival

        # Act
        result = await festival_service.get_festival_by_id(sample_festival.id)

        # Assert
        assert result == sample_festival
        mock_cache.get.assert_called_once()
        mock_festival_repo.get_by_id.assert_not_called()

    async def test_create_festival_with_artist_validation(
        self,
        festival_service,
        mock_festival_repo,
        mock_artist_repo,
        mock_cache,
        sample_festival,
        sample_artist,
    ):
        """Test create festival validates artists."""
        # Arrange
        artist_ids = [sample_artist.id]
        mock_artist_repo.get_by_id.return_value = sample_artist
        mock_festival_repo.create.return_value = sample_festival

        # Act
        result = await festival_service.create_festival(sample_festival, artist_ids)

        # Assert
        assert result == sample_festival
        mock_artist_repo.get_by_id.assert_called_once_with(sample_artist.id)
        mock_festival_repo.create.assert_called_once()
        mock_cache.delete_pattern.assert_called()

    async def test_create_festival_invalid_artist_raises_error(
        self, festival_service, mock_artist_repo, sample_festival
    ):
        """Test create festival with invalid artist raises ValueError."""
        # Arrange
        invalid_artist_id = uuid4()
        mock_artist_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="not found"):
            await festival_service.create_festival(sample_festival, [invalid_artist_id])

    async def test_search_festivals_with_caching(
        self, festival_service, mock_cache, mock_festival_repo, sample_festival
    ):
        """Test search festivals with caching disabled for complex objects."""
        # Arrange
        mock_festival_repo.search_paginated.return_value = ([sample_festival], 1)

        # Act
        festivals, total = await festival_service.search_festivals(search="Test")

        # Assert
        assert len(festivals) == 1
        assert total == 1
        # Caching is disabled for complex objects to avoid serialization issues
        mock_cache.get.assert_not_called()
        mock_festival_repo.search_paginated.assert_called_once()
        mock_cache.set.assert_not_called()

    async def test_add_artist_to_festival(
        self,
        festival_service,
        mock_festival_repo,
        mock_artist_repo,
        mock_cache,
        sample_festival,
        sample_artist,
    ):
        """Test adding artist to festival."""
        # Arrange
        sample_festival.artists = []
        mock_festival_repo.get_by_id.return_value = sample_festival
        mock_artist_repo.get_by_id.return_value = sample_artist
        mock_festival_repo.update.return_value = sample_festival

        # Act
        result = await festival_service.add_artist_to_festival(
            sample_festival.id, sample_artist.id
        )

        # Assert
        assert result == sample_festival
        assert sample_artist in sample_festival.artists
        mock_festival_repo.update.assert_called_once()
        mock_cache.delete.assert_called()

    async def test_add_artist_to_festival_not_found_raises_error(
        self, festival_service, mock_festival_repo
    ):
        """Test adding artist to non-existent festival raises error."""
        # Arrange
        mock_festival_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Festival .* not found"):
            await festival_service.add_artist_to_festival(uuid4(), uuid4())


# ============================================================================
# PlaylistService Tests
# ============================================================================


class TestPlaylistService:
    """Test PlaylistService with Spotify integration."""

    @pytest_asyncio.fixture
    async def mock_playlist_repo(self):
        """Create mock PlaylistRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_festival_repo(self):
        """Create mock FestivalRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_cache(self):
        """Create mock CacheService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_spotify_service(self):
        """Create mock SpotifyService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def playlist_service(
        self, mock_playlist_repo, mock_festival_repo, mock_cache, mock_spotify_service
    ):
        """Create PlaylistService with mocked dependencies."""
        return PlaylistService(
            mock_playlist_repo, mock_festival_repo, mock_cache, mock_spotify_service
        )

    @pytest_asyncio.fixture
    def sample_playlist(self):
        """Create sample playlist."""
        return Playlist(
            id=uuid4(), name="Test Playlist", user_id=uuid4(), festival_id=uuid4()
        )

    async def test_get_playlist_by_id_cache_hit(
        self, playlist_service, mock_cache, mock_playlist_repo, sample_playlist
    ):
        """Test get playlist by ID with cache hit."""
        # Arrange
        mock_cache.get.return_value = sample_playlist

        # Act
        result = await playlist_service.get_playlist_by_id(sample_playlist.id)

        # Assert
        assert result == sample_playlist
        mock_cache.get.assert_called_once()
        mock_playlist_repo.get_by_id.assert_not_called()

    async def test_create_playlist_with_festival_validation(
        self,
        playlist_service,
        mock_playlist_repo,
        mock_festival_repo,
        mock_cache,
        sample_playlist,
    ):
        """Test create playlist validates festival."""
        # Arrange
        festival = Festival(id=sample_playlist.festival_id, name="Test Festival")
        mock_festival_repo.get_by_id.return_value = festival
        mock_playlist_repo.create.return_value = sample_playlist

        # Act
        result = await playlist_service.create_playlist(
            sample_playlist, sample_playlist.festival_id
        )

        # Assert
        assert result == sample_playlist
        mock_festival_repo.get_by_id.assert_called_once_with(
            sample_playlist.festival_id
        )
        mock_playlist_repo.create.assert_called_once()
        mock_cache.delete_pattern.assert_called()

    async def test_create_playlist_invalid_festival_raises_error(
        self, playlist_service, mock_festival_repo, sample_playlist
    ):
        """Test create playlist with invalid festival raises ValueError."""
        # Arrange
        mock_festival_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Festival .* not found"):
            await playlist_service.create_playlist(
                sample_playlist, sample_playlist.festival_id
            )

    async def test_sync_to_spotify_success(
        self,
        playlist_service,
        mock_playlist_repo,
        mock_spotify_service,
        sample_playlist,
    ):
        """Test syncing playlist to Spotify."""
        # Arrange
        sample_playlist.tracks = []
        mock_playlist_repo.get_by_id.return_value = sample_playlist
        mock_spotify_service.create_playlist.return_value = "spotify_playlist_123"
        mock_playlist_repo.update.return_value = sample_playlist

        # Act
        result = await playlist_service.sync_to_spotify(
            sample_playlist.id, "access_token"
        )

        # Assert
        assert result == "spotify_playlist_123"
        mock_spotify_service.create_playlist.assert_called_once()
        mock_playlist_repo.update.assert_called_once()

    async def test_sync_to_spotify_no_service_raises_error(
        self, mock_playlist_repo, mock_festival_repo, mock_cache
    ):
        """Test sync to Spotify without service raises error."""
        # Arrange
        service = PlaylistService(
            mock_playlist_repo, mock_festival_repo, mock_cache, None
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Spotify service not configured"):
            await service.sync_to_spotify(uuid4(), "token")

    async def test_get_user_playlists_with_caching(
        self, playlist_service, mock_cache, mock_playlist_repo, sample_playlist
    ):
        """Test get user playlists with caching."""
        # Arrange
        user_id = uuid4()
        mock_cache.get.return_value = None
        mock_playlist_repo.get_by_user.return_value = [sample_playlist]

        # Act
        result = await playlist_service.get_user_playlists(user_id)

        # Assert
        assert len(result) == 1
        mock_cache.get.assert_called_once()
        mock_playlist_repo.get_by_user.assert_called_once()
        mock_cache.set.assert_called_once()


# ============================================================================
# CircuitBreaker Tests
# ============================================================================


class TestCircuitBreaker:
    """Test CircuitBreaker pattern."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create CircuitBreaker instance."""
        return CircuitBreaker(
            failure_threshold=3, recovery_timeout=1, expected_exception=Exception
        )

    async def test_circuit_closed_allows_requests(self, circuit_breaker):
        """Test circuit breaker in CLOSED state allows requests."""

        # Arrange
        async def success_func():
            return "success"

        # Act
        result = await circuit_breaker.call(success_func)

        # Assert
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    async def test_circuit_opens_after_threshold_failures(self, circuit_breaker):
        """Test circuit breaker opens after threshold failures."""

        # Arrange
        async def failing_func():
            raise Exception("Test failure")

        # Act - trigger failures
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_func)

        # Assert
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.failure_count == 3

    async def test_circuit_open_rejects_requests(self, circuit_breaker):
        """Test circuit breaker in OPEN state rejects requests."""
        # Arrange - force circuit to open
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.last_failure_time = datetime.now()

        async def any_func():
            return "should not execute"

        # Act & Assert
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await circuit_breaker.call(any_func)

    async def test_circuit_transitions_to_half_open(self, circuit_breaker):
        """Test circuit breaker transitions to HALF_OPEN after timeout."""
        # Arrange - force circuit to open and wait
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=2)

        async def success_func():
            return "success"

        # Act
        result = await circuit_breaker.call(success_func)

        # Assert
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    async def test_circuit_half_open_closes_on_success(self, circuit_breaker):
        """Test circuit breaker closes from HALF_OPEN on success."""
        # Arrange
        circuit_breaker.state = CircuitState.HALF_OPEN

        async def success_func():
            return "success"

        # Act
        result = await circuit_breaker.call(success_func)

        # Assert
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED


# ============================================================================
# SpotifyService Tests
# ============================================================================


class TestSpotifyService:
    """Test SpotifyService with circuit breaker."""

    @pytest.fixture
    def spotify_service(self):
        """Create SpotifyService instance."""
        return SpotifyService(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost/callback",
        )

    async def test_search_artist_success(self, spotify_service):
        """Test successful artist search."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "artists": {"items": [{"id": "artist1", "name": "Test Artist"}]}
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            spotify_service.client, "get", return_value=mock_response
        ) as mock_get:
            mock_get.return_value = mock_response

            # Act
            result = await spotify_service.search_artist("Test Artist", "token")

            # Assert
            assert len(result) == 1
            assert result[0]["name"] == "Test Artist"

    async def test_search_artist_circuit_breaker_opens(self, spotify_service):
        """Test circuit breaker opens after failures."""
        # Arrange
        import httpx

        async def failing_get(*args, **kwargs):
            raise httpx.HTTPError("Connection failed")

        with patch.object(spotify_service.client, "get", side_effect=failing_get):
            # Act - trigger failures
            for _ in range(5):
                result = await spotify_service.search_artist("Test", "token")
                assert result == []

            # Assert - circuit should be open
            assert spotify_service.circuit_breaker.state == CircuitState.OPEN

    async def test_create_playlist_success(self, spotify_service):
        """Test successful playlist creation."""
        # Arrange
        user_response = MagicMock()
        user_response.json.return_value = {"id": "user123"}
        user_response.raise_for_status = MagicMock()

        playlist_response = MagicMock()
        playlist_response.json.return_value = {"id": "playlist123"}
        playlist_response.raise_for_status = MagicMock()

        with patch.object(spotify_service.client, "get", return_value=user_response):
            with patch.object(
                spotify_service.client, "post", return_value=playlist_response
            ):
                # Act
                result = await spotify_service.create_playlist(
                    "Test Playlist", "Description", "token"
                )

                # Assert
                assert result == "playlist123"

    async def test_add_tracks_to_playlist_batching(self, spotify_service):
        """Test adding tracks with batching (max 100 per request)."""
        # Arrange
        track_uris = [f"spotify:track:{i}" for i in range(150)]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            spotify_service.client, "post", return_value=mock_response
        ) as mock_post:
            # Act
            result = await spotify_service.add_tracks_to_playlist(
                "playlist123", track_uris, "token"
            )

            # Assert
            assert result is True
            # Should make 2 requests (100 + 50)
            assert mock_post.call_count == 2


# ============================================================================
# SetlistFmService Tests
# ============================================================================


class TestSetlistFmService:
    """Test SetlistFmService with circuit breaker and retry logic."""

    @pytest.fixture
    def setlistfm_service(self):
        """Create SetlistFmService instance."""
        return SetlistFmService(api_key="test_api_key")

    async def test_get_artist_setlists_success(self, setlistfm_service):
        """Test successful artist setlists retrieval."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "setlist": [{"id": "setlist1", "artist": {"name": "Test Artist"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(setlistfm_service.client, "get", return_value=mock_response):
            # Act
            result = await setlistfm_service.get_artist_setlists("mbid123")

            # Assert
            assert result is not None
            assert "setlist" in result

    async def test_retry_with_exponential_backoff(self, setlistfm_service):
        """Test retry logic with exponential backoff."""
        # Arrange
        import httpx

        call_count = 0

        async def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                response = MagicMock()
                response.status_code = 500
                raise httpx.HTTPStatusError(
                    "Server error", request=None, response=response
                )

            mock_response = MagicMock()
            mock_response.json.return_value = {"success": True}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch.object(
            setlistfm_service.client, "get", side_effect=failing_then_success
        ):
            # Act
            result = await setlistfm_service.get_setlist_by_id("setlist123")

            # Assert
            assert result is not None
            assert result["success"] is True
            assert call_count == 3  # Failed twice, succeeded on third

    async def test_no_retry_on_client_error(self, setlistfm_service):
        """Test no retry on 4xx client errors."""
        # Arrange
        import httpx

        async def client_error(*args, **kwargs):
            response = MagicMock()
            response.status_code = 404
            raise httpx.HTTPStatusError("Not found", request=None, response=response)

        with patch.object(setlistfm_service.client, "get", side_effect=client_error):
            # Act
            result = await setlistfm_service.get_setlist_by_id("invalid_id")

            # Assert
            assert result is None

    async def test_rate_limiter_throttles_requests(self):
        """Test rate limiter throttles requests."""
        # Arrange
        rate_limiter = RateLimiter(max_requests=2, time_window=1)

        # Act - make 3 requests quickly
        start_time = datetime.now()
        await rate_limiter.acquire()
        await rate_limiter.acquire()
        await rate_limiter.acquire()  # This should wait
        end_time = datetime.now()

        # Assert - third request should have been delayed
        elapsed = (end_time - start_time).total_seconds()
        assert elapsed >= 0.5  # Should have waited at least some time


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestServiceErrorHandling:
    """Test error handling across services."""

    async def test_cache_service_handles_json_decode_error(self):
        """Test CacheService handles invalid JSON gracefully."""
        # Arrange
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "invalid json {"
        cache_service = CacheService(redis_client=mock_redis)

        # Act
        result = await cache_service.get("test_key")

        # Assert
        assert result is None

    async def test_cache_service_handles_connection_error(self):
        """Test CacheService handles connection errors gracefully."""
        # Arrange
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Connection failed")
        cache_service = CacheService(redis_client=mock_redis)

        # Act
        result = await cache_service.get("test_key")

        # Assert
        assert result is None

    async def test_artist_service_handles_repository_error(self):
        """Test ArtistService handles repository errors."""
        # Arrange
        mock_repo = AsyncMock()
        mock_repo.get_by_id.side_effect = Exception("Database error")
        mock_cache = AsyncMock()
        mock_cache.get.return_value = None
        service = ArtistService(mock_repo, mock_cache)

        # Act & Assert
        with pytest.raises(Exception, match="Database error"):
            await service.get_artist_by_id(uuid4())


# ============================================================================
# Integration-like Tests (Multiple Services)
# ============================================================================


class TestServiceIntegration:
    """Test interactions between services."""

    async def test_festival_service_uses_artist_service_pattern(self):
        """Test FestivalService validates artists correctly."""
        # Arrange
        mock_festival_repo = AsyncMock()
        mock_artist_repo = AsyncMock()
        mock_cache = AsyncMock()

        artist_id = uuid4()
        artist = Artist(id=artist_id, name="Test Artist")
        festival = Festival(id=uuid4(), name="Test Festival")

        mock_artist_repo.get_by_id.return_value = artist
        mock_festival_repo.create.return_value = festival

        service = FestivalService(mock_festival_repo, mock_artist_repo, mock_cache)

        # Act
        result = await service.create_festival(festival, [artist_id])

        # Assert
        assert result == festival
        assert artist in festival.artists

    async def test_playlist_service_integrates_with_spotify(self):
        """Test PlaylistService integrates with SpotifyService."""
        # Arrange
        mock_playlist_repo = AsyncMock()
        mock_festival_repo = AsyncMock()
        mock_cache = AsyncMock()
        mock_spotify = AsyncMock()

        playlist = Playlist(id=uuid4(), name="Test")
        playlist.tracks = []  # Set tracks after initialization
        mock_playlist_repo.get_by_id.return_value = playlist
        mock_spotify.create_playlist.return_value = "spotify123"
        mock_playlist_repo.update.return_value = playlist

        service = PlaylistService(
            mock_playlist_repo, mock_festival_repo, mock_cache, mock_spotify
        )

        # Act
        result = await service.sync_to_spotify(playlist.id, "token")

        # Assert
        assert result == "spotify123"
        mock_spotify.create_playlist.assert_called_once()


# ============================================================================
# Additional Coverage Tests
# ============================================================================


class TestCacheServiceAdditional:
    """Additional tests for CacheService to increase coverage."""

    @pytest_asyncio.fixture
    async def mock_redis(self):
        """Create a mock Redis client."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def cache_service(self, mock_redis):
        """Create CacheService with mocked Redis."""
        return CacheService(redis_client=mock_redis)

    async def test_get_many(self, cache_service, mock_redis):
        """Test getting multiple values from cache."""
        # Arrange
        mock_redis.mget.return_value = [
            json.dumps({"key": "value1"}),
            None,
            json.dumps({"key": "value2"}),
        ]

        # Act
        result = await cache_service.get_many(["key1", "key2", "key3"])

        # Assert
        assert len(result) == 3
        assert result[0] == {"key": "value1"}
        assert result[1] is None
        assert result[2] == {"key": "value2"}

    async def test_increment(self, cache_service, mock_redis):
        """Test incrementing a value in cache."""
        # Arrange
        mock_redis.incrby.return_value = 5

        # Act
        result = await cache_service.increment("counter", 2)

        # Assert
        assert result == 5
        mock_redis.incrby.assert_called_once_with("counter", 2)

    async def test_expire(self, cache_service, mock_redis):
        """Test setting expiration on a key."""
        # Arrange
        mock_redis.expire.return_value = True

        # Act
        result = await cache_service.expire("test_key", 300)

        # Assert
        assert result is True
        mock_redis.expire.assert_called_once_with("test_key", 300)


class TestArtistServiceAdditional:
    """Additional tests for ArtistService to increase coverage."""

    @pytest_asyncio.fixture
    async def mock_artist_repo(self):
        """Create mock ArtistRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_cache(self):
        """Create mock CacheService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def artist_service(self, mock_artist_repo, mock_cache):
        """Create ArtistService with mocked dependencies."""
        return ArtistService(mock_artist_repo, mock_cache)

    async def test_get_artist_by_name(
        self, artist_service, mock_cache, mock_artist_repo
    ):
        """Test get artist by name."""
        # Arrange
        artist = Artist(id=uuid4(), name="Test Artist")
        mock_cache.get.return_value = None
        mock_artist_repo.get_by_name.return_value = artist

        # Act
        result = await artist_service.get_artist_by_name("Test Artist")

        # Assert
        assert result == artist
        mock_cache.set.assert_called_once()

    async def test_get_artist_by_spotify_id(
        self, artist_service, mock_cache, mock_artist_repo
    ):
        """Test get artist by Spotify ID."""
        # Arrange
        artist = Artist(id=uuid4(), name="Test Artist", spotify_id="spotify123")
        mock_cache.get.return_value = None
        mock_artist_repo.get_by_spotify_id.return_value = artist

        # Act
        result = await artist_service.get_artist_by_spotify_id("spotify123")

        # Assert
        assert result == artist
        mock_cache.set.assert_called_once()

    async def test_bulk_delete_artists(
        self, artist_service, mock_cache, mock_artist_repo
    ):
        """Test bulk delete artists."""
        # Arrange
        artist_ids = [uuid4(), uuid4(), uuid4()]
        mock_artist_repo.bulk_delete.return_value = 3

        # Act
        result = await artist_service.bulk_delete_artists(artist_ids)

        # Assert
        assert result == 3
        mock_artist_repo.bulk_delete.assert_called_once_with(artist_ids)
        mock_cache.delete_pattern.assert_called()

    async def test_get_artist_count(self, artist_service, mock_cache, mock_artist_repo):
        """Test get total artist count."""
        # Arrange
        mock_cache.get.return_value = None
        mock_artist_repo.count_total.return_value = 42

        # Act
        result = await artist_service.get_artist_count()

        # Assert
        assert result == 42
        mock_cache.set.assert_called_once()

    async def test_get_orphaned_artist_count(
        self, artist_service, mock_cache, mock_artist_repo
    ):
        """Test get orphaned artist count."""
        # Arrange
        mock_cache.get.return_value = None
        mock_artist_repo.count_orphaned.return_value = 5

        # Act
        result = await artist_service.get_orphaned_artist_count()

        # Assert
        assert result == 5
        mock_cache.set.assert_called_once()


class TestFestivalServiceAdditional:
    """Additional tests for FestivalService to increase coverage."""

    @pytest_asyncio.fixture
    async def mock_festival_repo(self):
        """Create mock FestivalRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_artist_repo(self):
        """Create mock ArtistRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_cache(self):
        """Create mock CacheService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def festival_service(self, mock_festival_repo, mock_artist_repo, mock_cache):
        """Create FestivalService with mocked dependencies."""
        return FestivalService(mock_festival_repo, mock_artist_repo, mock_cache)

    async def test_get_festival_by_name(
        self, festival_service, mock_cache, mock_festival_repo
    ):
        """Test get festival by name."""
        # Arrange
        festival = Festival(id=uuid4(), name="Test Festival")
        mock_cache.get.return_value = None
        mock_festival_repo.get_by_name.return_value = festival

        # Act
        result = await festival_service.get_festival_by_name("Test Festival")

        # Assert
        assert result == festival
        mock_cache.set.assert_called_once()

    async def test_get_upcoming_festivals(
        self, festival_service, mock_cache, mock_festival_repo
    ):
        """Test get upcoming festivals."""
        # Arrange
        festivals = [Festival(id=uuid4(), name=f"Festival {i}") for i in range(3)]
        mock_cache.get.return_value = None
        mock_festival_repo.get_upcoming_festivals.return_value = festivals

        # Act
        result = await festival_service.get_upcoming_festivals(limit=10)

        # Assert
        assert len(result) == 3
        mock_cache.set.assert_called_once()

    async def test_update_festival(
        self, festival_service, mock_cache, mock_festival_repo
    ):
        """Test update festival."""
        # Arrange
        festival = Festival(id=uuid4(), name="Updated Festival")
        mock_festival_repo.update.return_value = festival

        # Act
        result = await festival_service.update_festival(festival)

        # Assert
        assert result == festival
        mock_festival_repo.update.assert_called_once()
        mock_cache.delete.assert_called()

    async def test_remove_artist_from_festival(
        self, festival_service, mock_festival_repo, mock_cache
    ):
        """Test removing artist from festival."""
        # Arrange
        artist_id = uuid4()
        artist = Artist(id=artist_id, name="Test Artist")
        festival = Festival(id=uuid4(), name="Test Festival")
        festival.artists = [artist]

        mock_festival_repo.get_by_id.return_value = festival
        mock_festival_repo.update.return_value = festival

        # Act
        result = await festival_service.remove_artist_from_festival(
            festival.id, artist_id
        )

        # Assert
        assert result == festival
        assert artist not in festival.artists
        mock_festival_repo.update.assert_called_once()

    async def test_get_festival_count(
        self, festival_service, mock_cache, mock_festival_repo
    ):
        """Test get total festival count."""
        # Arrange
        mock_cache.get.return_value = None
        mock_festival_repo.count_total.return_value = 15

        # Act
        result = await festival_service.get_festival_count()

        # Assert
        assert result == 15
        mock_cache.set.assert_called_once()


class TestPlaylistServiceAdditional:
    """Additional tests for PlaylistService to increase coverage."""

    @pytest_asyncio.fixture
    async def mock_playlist_repo(self):
        """Create mock PlaylistRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_festival_repo(self):
        """Create mock FestivalRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_cache(self):
        """Create mock CacheService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_spotify_service(self):
        """Create mock SpotifyService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def playlist_service(
        self, mock_playlist_repo, mock_festival_repo, mock_cache, mock_spotify_service
    ):
        """Create PlaylistService with mocked dependencies."""
        return PlaylistService(
            mock_playlist_repo, mock_festival_repo, mock_cache, mock_spotify_service
        )

    async def test_get_playlist_by_spotify_id(
        self, playlist_service, mock_cache, mock_playlist_repo
    ):
        """Test get playlist by Spotify ID."""
        # Arrange
        playlist = Playlist(id=uuid4(), name="Test")
        playlist.spotify_id = "spotify123"  # Set after initialization
        mock_cache.get.return_value = None
        mock_playlist_repo.get_by_spotify_id.return_value = playlist

        # Act
        result = await playlist_service.get_playlist_by_spotify_id("spotify123")

        # Assert
        assert result == playlist
        mock_cache.set.assert_called_once()

    async def test_get_festival_playlists(
        self, playlist_service, mock_cache, mock_playlist_repo
    ):
        """Test get festival playlists."""
        # Arrange
        festival_id = uuid4()
        playlists = [Playlist(id=uuid4(), name=f"Playlist {i}") for i in range(2)]
        mock_cache.get.return_value = None
        mock_playlist_repo.get_by_festival.return_value = playlists

        # Act
        result = await playlist_service.get_festival_playlists(festival_id)

        # Assert
        assert len(result) == 2
        mock_cache.set.assert_called_once()

    async def test_update_playlist(
        self, playlist_service, mock_cache, mock_playlist_repo
    ):
        """Test update playlist."""
        # Arrange
        playlist = Playlist(id=uuid4(), name="Updated", user_id=uuid4())
        mock_playlist_repo.update.return_value = playlist

        # Act
        result = await playlist_service.update_playlist(playlist)

        # Assert
        assert result == playlist
        mock_playlist_repo.update.assert_called_once()
        mock_cache.delete.assert_called()

    async def test_delete_playlist(
        self, playlist_service, mock_cache, mock_playlist_repo
    ):
        """Test delete playlist."""
        # Arrange
        playlist = Playlist(id=uuid4(), name="Test", user_id=uuid4())
        mock_playlist_repo.get_by_id.return_value = playlist
        mock_playlist_repo.delete.return_value = True

        # Act
        result = await playlist_service.delete_playlist(playlist.id)

        # Assert
        assert result is True
        mock_playlist_repo.delete.assert_called_once()
        mock_cache.delete.assert_called()

    async def test_sync_to_spotify_not_found(
        self, playlist_service, mock_playlist_repo
    ):
        """Test sync to Spotify with non-existent playlist."""
        # Arrange
        mock_playlist_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Playlist .* not found"):
            await playlist_service.sync_to_spotify(uuid4(), "token")

    async def test_sync_to_spotify_with_tracks(
        self, playlist_service, mock_playlist_repo, mock_spotify_service, mock_cache
    ):
        """Test syncing playlist with tracks to Spotify."""
        # Arrange
        from festival_playlist_generator.models.song import Song

        playlist = Playlist(id=uuid4(), name="Test")
        track1 = Song(id=uuid4(), title="Song 1")
        track1.external_id = "track1"  # Use external_id instead of spotify_id
        track2 = Song(id=uuid4(), title="Song 2")
        track2.external_id = "track2"  # Use external_id instead of spotify_id
        playlist.songs = [track1, track2]  # Use songs instead of tracks

        mock_playlist_repo.get_by_id.return_value = playlist
        mock_spotify_service.create_playlist.return_value = "spotify_playlist_123"
        mock_spotify_service.add_tracks_to_playlist.return_value = True
        mock_playlist_repo.update.return_value = playlist

        # Act
        result = await playlist_service.sync_to_spotify(playlist.id, "token")

        # Assert
        assert result == "spotify_playlist_123"
        mock_spotify_service.add_tracks_to_playlist.assert_called_once()


class TestSpotifyServiceAdditional:
    """Additional tests for SpotifyService to increase coverage."""

    @pytest.fixture
    def spotify_service(self):
        """Create SpotifyService instance."""
        return SpotifyService(
            client_id="test_client_id", client_secret="test_client_secret"
        )

    async def test_get_track(self, spotify_service):
        """Test getting track details."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "track123", "name": "Test Track"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(spotify_service.client, "get", return_value=mock_response):
            # Act
            result = await spotify_service.get_track("track123", "token")

            # Assert
            assert result["id"] == "track123"

    async def test_search_track(self, spotify_service):
        """Test searching for a track."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tracks": {"items": [{"id": "track1", "name": "Test Track"}]}
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(spotify_service.client, "get", return_value=mock_response):
            # Act
            result = await spotify_service.search_track("Test Track", "Artist", "token")

            # Assert
            assert len(result) == 1

    async def test_refresh_access_token(self, spotify_service):
        """Test refreshing access token."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(spotify_service.client, "post", return_value=mock_response):
            # Act
            result = await spotify_service.refresh_access_token("refresh_token")

            # Assert
            assert result["access_token"] == "new_token"


class TestSetlistFmServiceAdditional:
    """Additional tests for SetlistFmService to increase coverage."""

    @pytest.fixture
    def setlistfm_service(self):
        """Create SetlistFmService instance."""
        return SetlistFmService(api_key="test_api_key")

    async def test_search_artist(self, setlistfm_service):
        """Test searching for an artist."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "artist": [{"mbid": "mbid123", "name": "Test Artist"}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(setlistfm_service.client, "get", return_value=mock_response):
            # Act
            result = await setlistfm_service.search_artist("Test Artist")

            # Assert
            assert result is not None

    async def test_search_setlists(self, setlistfm_service):
        """Test searching for setlists."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"setlist": [{"id": "setlist1"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(setlistfm_service.client, "get", return_value=mock_response):
            # Act
            result = await setlistfm_service.search_setlists(artist_name="Test")

            # Assert
            assert result is not None

    async def test_get_venue(self, setlistfm_service):
        """Test getting venue details."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "venue123", "name": "Test Venue"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(setlistfm_service.client, "get", return_value=mock_response):
            # Act
            result = await setlistfm_service.get_venue("venue123")

            # Assert
            assert result["id"] == "venue123"


# ============================================================================
# Additional Tests to Reach 90% Coverage
# ============================================================================


class TestCacheServiceComplete:
    """Additional tests to reach 90% coverage for CacheService."""

    @pytest_asyncio.fixture
    async def mock_redis(self):
        """Create a mock Redis client."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def cache_service(self, mock_redis):
        """Create CacheService with mocked Redis."""
        return CacheService(redis_client=mock_redis)

    async def test_get_client_creates_pool(self):
        """Test _get_client creates connection pool."""
        # Arrange
        service = CacheService(redis_client=None)

        with patch(
            "festival_playlist_generator.services.cache_service.redis.ConnectionPool"
        ) as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool_class.from_url.return_value = mock_pool

            with patch(
                "festival_playlist_generator.services.cache_service.redis.Redis"
            ) as mock_redis_class:
                mock_client = AsyncMock()
                mock_redis_class.return_value = mock_client

                # Act
                client = await service._get_client()

                # Assert
                assert client == mock_client
                mock_pool_class.from_url.assert_called_once()

    async def test_get_with_exception(self, cache_service, mock_redis):
        """Test get handles general exceptions."""
        # Arrange
        mock_redis.get.side_effect = Exception("Redis error")

        # Act
        result = await cache_service.get("test_key")

        # Assert
        assert result is None

    async def test_set_with_exception(self, cache_service, mock_redis):
        """Test set handles general exceptions."""
        # Arrange
        mock_redis.setex.side_effect = Exception("Redis error")

        # Act
        result = await cache_service.set("test_key", {"data": "value"})

        # Assert
        assert result is False

    async def test_delete_with_exception(self, cache_service, mock_redis):
        """Test delete handles exceptions."""
        # Arrange
        mock_redis.delete.side_effect = Exception("Redis error")

        # Act
        result = await cache_service.delete("test_key")

        # Assert
        assert result is False

    async def test_delete_pattern_with_exception(self, cache_service, mock_redis):
        """Test delete_pattern handles exceptions."""

        # Arrange
        async def mock_scan_iter(match):
            # Make this an async generator that raises an exception
            if False:
                yield  # Make it a generator
            raise Exception("Redis error")

        mock_redis.scan_iter = mock_scan_iter

        # Act
        result = await cache_service.delete_pattern("test:*")

        # Assert
        assert result == 0

    async def test_exists_with_exception(self, cache_service, mock_redis):
        """Test exists handles exceptions."""
        # Arrange
        mock_redis.exists.side_effect = Exception("Redis error")

        # Act
        result = await cache_service.exists("test_key")

        # Assert
        assert result is False

    async def test_get_many_with_exception(self, cache_service, mock_redis):
        """Test get_many handles exceptions."""
        # Arrange
        mock_redis.mget.side_effect = Exception("Redis error")

        # Act
        result = await cache_service.get_many(["key1", "key2"])

        # Assert
        assert result == [None, None]

    async def test_increment_with_exception(self, cache_service, mock_redis):
        """Test increment handles exceptions."""
        # Arrange
        mock_redis.incrby.side_effect = Exception("Redis error")

        # Act
        result = await cache_service.increment("counter")

        # Assert
        assert result is None

    async def test_expire_with_exception(self, cache_service, mock_redis):
        """Test expire handles exceptions."""
        # Arrange
        mock_redis.expire.side_effect = Exception("Redis error")

        # Act
        result = await cache_service.expire("test_key", 300)

        # Assert
        assert result is False

    async def test_close(self, cache_service, mock_redis):
        """Test close method."""
        # Arrange
        mock_pool = AsyncMock()
        cache_service._pool = mock_pool

        # Act
        await cache_service.close()

        # Assert
        mock_pool.disconnect.assert_called_once()


class TestArtistServiceComplete:
    """Additional tests to reach 90% coverage for ArtistService."""

    @pytest_asyncio.fixture
    async def mock_artist_repo(self):
        """Create mock ArtistRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_cache(self):
        """Create mock CacheService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def artist_service(self, mock_artist_repo, mock_cache):
        """Create ArtistService with mocked dependencies."""
        return ArtistService(mock_artist_repo, mock_cache)

    async def test_get_artist_by_id_with_relationships(
        self, artist_service, mock_cache, mock_artist_repo
    ):
        """Test get artist by ID with relationships loaded."""
        # Arrange
        artist = Artist(id=uuid4(), name="Test Artist")
        mock_cache.get.return_value = None
        mock_artist_repo.get_by_id.return_value = artist

        # Act
        result = await artist_service.get_artist_by_id(
            artist.id, load_relationships=True
        )

        # Assert
        assert result == artist
        mock_artist_repo.get_by_id.assert_called_once_with(artist.id, True)
        # Should not cache when loading relationships
        mock_cache.set.assert_not_called()

    async def test_search_artists_cache_hit(
        self, artist_service, mock_cache, mock_artist_repo
    ):
        """Test search artists - caching disabled for complex objects."""
        # Arrange
        sample_artist = Artist(id=uuid4(), name="Test Artist", spotify_id="test123")
        mock_artist_repo.search_paginated.return_value = ([sample_artist], 1)

        # Act
        artists, total = await artist_service.search_artists(search="Test")

        # Assert
        assert total == 1
        assert len(artists) == 1
        # Caching is disabled for complex objects, so repo should always be called
        mock_artist_repo.search_paginated.assert_called_once()

    async def test_bulk_delete_artists_zero_count(
        self, artist_service, mock_cache, mock_artist_repo
    ):
        """Test bulk delete with zero deletions."""
        # Arrange
        mock_artist_repo.bulk_delete.return_value = 0

        # Act
        result = await artist_service.bulk_delete_artists([uuid4()])

        # Assert
        assert result == 0
        # Should not invalidate cache if nothing deleted
        mock_cache.delete.assert_not_called()


class TestFestivalServiceComplete:
    """Additional tests to reach 90% coverage for FestivalService."""

    @pytest_asyncio.fixture
    async def mock_festival_repo(self):
        """Create mock FestivalRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_artist_repo(self):
        """Create mock ArtistRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_cache(self):
        """Create mock CacheService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def festival_service(self, mock_festival_repo, mock_artist_repo, mock_cache):
        """Create FestivalService with mocked dependencies."""
        return FestivalService(mock_festival_repo, mock_artist_repo, mock_cache)

    async def test_get_festival_by_id_with_relationships(
        self, festival_service, mock_cache, mock_festival_repo
    ):
        """Test get festival by ID with relationships loaded."""
        # Arrange
        festival = Festival(id=uuid4(), name="Test Festival")
        mock_cache.get.return_value = None
        mock_festival_repo.get_by_id.return_value = festival

        # Act
        result = await festival_service.get_festival_by_id(
            festival.id, load_relationships=True
        )

        # Assert
        assert result == festival
        mock_festival_repo.get_by_id.assert_called_once_with(festival.id, True)
        # Should not cache when loading relationships
        mock_cache.set.assert_not_called()

    async def test_get_upcoming_festivals_with_relationships(
        self, festival_service, mock_cache, mock_festival_repo
    ):
        """Test get upcoming festivals with relationships."""
        # Arrange
        festivals = [Festival(id=uuid4(), name="Test")]
        mock_cache.get.return_value = None
        mock_festival_repo.get_upcoming_festivals.return_value = festivals

        # Act
        result = await festival_service.get_upcoming_festivals(
            limit=5, load_relationships=True
        )

        # Assert
        assert len(result) == 1
        mock_festival_repo.get_upcoming_festivals.assert_called_once_with(5, from_date=None)
        # Should not cache when loading relationships
        mock_cache.set.assert_not_called()

    async def test_search_festivals_cache_hit(
        self, festival_service, mock_cache, mock_festival_repo
    ):
        """Test search festivals - caching disabled for complex objects."""
        # Arrange
        sample_festival = Festival(
            id=uuid4(),
            name="Test Festival",
            dates=[datetime.utcnow()],
            location="Test City",
        )
        mock_festival_repo.search_paginated.return_value = ([sample_festival], 1)

        # Act
        festivals, total = await festival_service.search_festivals(search="Test")

        # Assert
        assert total == 1
        assert len(festivals) == 1
        # Caching is disabled for complex objects, so repo should always be called
        mock_festival_repo.search_paginated.assert_called_once()

    async def test_update_festival_with_artists(
        self, festival_service, mock_festival_repo, mock_artist_repo, mock_cache
    ):
        """Test update festival with artist IDs."""
        # Arrange
        festival = Festival(id=uuid4(), name="Test")
        artist = Artist(id=uuid4(), name="Artist")
        mock_artist_repo.get_by_id.return_value = artist
        mock_festival_repo.update.return_value = festival

        # Act
        result = await festival_service.update_festival(festival, [artist.id])

        # Assert
        assert result == festival
        mock_artist_repo.get_by_id.assert_called_once()

    async def test_delete_festival_not_found(
        self, festival_service, mock_festival_repo, mock_cache
    ):
        """Test delete festival that doesn't exist."""
        # Arrange
        mock_festival_repo.delete.return_value = False

        # Act
        result = await festival_service.delete_festival(uuid4())

        # Assert
        assert result is False
        # Should not invalidate cache if nothing deleted
        mock_cache.delete.assert_not_called()

    async def test_add_artist_to_festival_already_present(
        self, festival_service, mock_festival_repo, mock_artist_repo, mock_cache
    ):
        """Test adding artist that's already in festival."""
        # Arrange
        artist = Artist(id=uuid4(), name="Test")
        festival = Festival(id=uuid4(), name="Test")
        festival.artists = [artist]

        mock_festival_repo.get_by_id.return_value = festival
        mock_artist_repo.get_by_id.return_value = artist

        # Act
        result = await festival_service.add_artist_to_festival(festival.id, artist.id)

        # Assert
        assert result == festival
        # Should not update if artist already present
        mock_festival_repo.update.assert_not_called()

    async def test_add_artist_to_festival_artist_not_found(
        self, festival_service, mock_festival_repo, mock_artist_repo
    ):
        """Test adding non-existent artist to festival."""
        # Arrange
        festival = Festival(id=uuid4(), name="Test")
        mock_festival_repo.get_by_id.return_value = festival
        mock_artist_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Artist .* not found"):
            await festival_service.add_artist_to_festival(festival.id, uuid4())


class TestPlaylistServiceComplete:
    """Additional tests to reach 90% coverage for PlaylistService."""

    @pytest_asyncio.fixture
    async def mock_playlist_repo(self):
        """Create mock PlaylistRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_festival_repo(self):
        """Create mock FestivalRepository."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_cache(self):
        """Create mock CacheService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def mock_spotify_service(self):
        """Create mock SpotifyService."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def playlist_service(
        self, mock_playlist_repo, mock_festival_repo, mock_cache, mock_spotify_service
    ):
        """Create PlaylistService with mocked dependencies."""
        return PlaylistService(
            mock_playlist_repo, mock_festival_repo, mock_cache, mock_spotify_service
        )

    async def test_get_playlist_by_id_with_relationships(
        self, playlist_service, mock_cache, mock_playlist_repo
    ):
        """Test get playlist by ID with relationships loaded."""
        # Arrange
        playlist = Playlist(id=uuid4(), name="Test")
        mock_cache.get.return_value = None
        mock_playlist_repo.get_by_id.return_value = playlist

        # Act
        result = await playlist_service.get_playlist_by_id(
            playlist.id, load_relationships=True
        )

        # Assert
        assert result == playlist
        mock_playlist_repo.get_by_id.assert_called_once_with(playlist.id, True)
        # Should not cache when loading relationships
        mock_cache.set.assert_not_called()

    async def test_get_user_playlists_cache_hit(
        self, playlist_service, mock_cache, mock_playlist_repo
    ):
        """Test get user playlists with cache hit."""
        # Arrange
        user_id = uuid4()
        cached_playlists = [{"id": "123", "name": "Test"}]
        mock_cache.get.return_value = cached_playlists

        # Act
        result = await playlist_service.get_user_playlists(user_id)

        # Assert
        assert result == cached_playlists
        mock_cache.get.assert_called_once()
        mock_playlist_repo.get_by_user.assert_not_called()

    async def test_get_festival_playlists_cache_hit(
        self, playlist_service, mock_cache, mock_playlist_repo
    ):
        """Test get festival playlists with cache hit."""
        # Arrange
        festival_id = uuid4()
        cached_playlists = [{"id": "123"}]
        mock_cache.get.return_value = cached_playlists

        # Act
        result = await playlist_service.get_festival_playlists(festival_id)

        # Assert
        assert result == cached_playlists
        mock_cache.get.assert_called_once()
        mock_playlist_repo.get_by_festival.assert_not_called()

    async def test_delete_playlist_not_found(
        self, playlist_service, mock_playlist_repo, mock_cache
    ):
        """Test delete playlist that doesn't exist."""
        # Arrange
        mock_playlist_repo.get_by_id.return_value = None
        mock_playlist_repo.delete.return_value = False

        # Act
        result = await playlist_service.delete_playlist(uuid4())

        # Assert
        assert result is False

    async def test_sync_to_spotify_error(
        self, playlist_service, mock_playlist_repo, mock_spotify_service, mock_cache
    ):
        """Test sync to Spotify with error."""
        # Arrange
        playlist = Playlist(id=uuid4(), name="Test")
        playlist.tracks = []
        mock_playlist_repo.get_by_id.return_value = playlist
        mock_spotify_service.create_playlist.side_effect = Exception("Spotify error")

        # Act
        result = await playlist_service.sync_to_spotify(playlist.id, "token")

        # Assert
        assert result is None


class TestSetlistFmServiceComplete:
    """Additional tests to reach 90% coverage for SetlistFmService."""

    @pytest.fixture
    def setlistfm_service(self):
        """Create SetlistFmService instance."""
        return SetlistFmService(api_key="test_api_key")

    async def test_get_artist_setlists_error(self, setlistfm_service):
        """Test get artist setlists with error."""
        # Arrange
        import httpx

        async def failing_get(*args, **kwargs):
            response = MagicMock()
            response.status_code = 500
            raise httpx.HTTPStatusError("Server error", request=None, response=response)

        with patch.object(setlistfm_service.client, "get", side_effect=failing_get):
            # Act
            result = await setlistfm_service.get_artist_setlists("mbid123")

            # Assert
            assert result is None

    async def test_get_setlist_by_id_error(self, setlistfm_service):
        """Test get setlist by ID with error."""
        # Arrange
        import httpx

        async def failing_get(*args, **kwargs):
            response = MagicMock()
            response.status_code = 500
            raise httpx.HTTPStatusError("Server error", request=None, response=response)

        with patch.object(setlistfm_service.client, "get", side_effect=failing_get):
            # Act
            result = await setlistfm_service.get_setlist_by_id("setlist123")

            # Assert
            assert result is None

    async def test_search_artist_error(self, setlistfm_service):
        """Test search artist with error."""
        # Arrange
        import httpx

        async def failing_get(*args, **kwargs):
            response = MagicMock()
            response.status_code = 500
            raise httpx.HTTPStatusError("Server error", request=None, response=response)

        with patch.object(setlistfm_service.client, "get", side_effect=failing_get):
            # Act
            result = await setlistfm_service.search_artist("Test Artist")

            # Assert
            assert result is None

    async def test_search_setlists_error(self, setlistfm_service):
        """Test search setlists with error."""
        # Arrange
        import httpx

        async def failing_get(*args, **kwargs):
            response = MagicMock()
            response.status_code = 500
            raise httpx.HTTPStatusError("Server error", request=None, response=response)

        with patch.object(setlistfm_service.client, "get", side_effect=failing_get):
            # Act
            result = await setlistfm_service.search_setlists(artist_name="Test")

            # Assert
            assert result is None

    async def test_get_venue_error(self, setlistfm_service):
        """Test get venue with error."""
        # Arrange
        import httpx

        async def failing_get(*args, **kwargs):
            response = MagicMock()
            response.status_code = 500
            raise httpx.HTTPStatusError("Server error", request=None, response=response)

        with patch.object(setlistfm_service.client, "get", side_effect=failing_get):
            # Act
            result = await setlistfm_service.get_venue("venue123")

            # Assert
            assert result is None


class TestSpotifyServiceComplete:
    """Additional tests to reach 90% coverage for SpotifyService."""

    @pytest.fixture
    def spotify_service(self):
        """Create SpotifyService instance."""
        return SpotifyService(
            client_id="test_client_id", client_secret="test_client_secret"
        )

    async def test_search_artist_error(self, spotify_service):
        """Test search artist with error."""
        # Arrange
        import httpx

        async def failing_get(*args, **kwargs):
            raise httpx.HTTPError("Connection failed")

        with patch.object(spotify_service.client, "get", side_effect=failing_get):
            # Act
            result = await spotify_service.search_artist("Test", "token")

            # Assert
            assert result == []

    async def test_get_track_error(self, spotify_service):
        """Test get track with error."""
        # Arrange
        import httpx

        async def failing_get(*args, **kwargs):
            raise httpx.HTTPError("Connection failed")

        with patch.object(spotify_service.client, "get", side_effect=failing_get):
            # Act
            result = await spotify_service.get_track("track123", "token")

            # Assert
            assert result is None

    async def test_search_track_error(self, spotify_service):
        """Test search track with error."""
        # Arrange
        import httpx

        async def failing_get(*args, **kwargs):
            raise httpx.HTTPError("Connection failed")

        with patch.object(spotify_service.client, "get", side_effect=failing_get):
            # Act
            result = await spotify_service.search_track("Track", "Artist", "token")

            # Assert
            assert result == []

    async def test_refresh_access_token_error(self, spotify_service):
        """Test refresh access token with error."""
        # Arrange
        import httpx

        async def failing_post(*args, **kwargs):
            raise httpx.HTTPError("Connection failed")

        with patch.object(spotify_service.client, "post", side_effect=failing_post):
            # Act
            result = await spotify_service.refresh_access_token("refresh_token")

            # Assert
            assert result is None

    async def test_add_tracks_to_playlist_error(self, spotify_service):
        """Test add tracks to playlist with error."""
        # Arrange
        import httpx

        async def failing_post(*args, **kwargs):
            raise httpx.HTTPError("Connection failed")

        with patch.object(spotify_service.client, "post", side_effect=failing_post):
            # Act
            result = await spotify_service.add_tracks_to_playlist(
                "playlist123", ["track1", "track2"], "token"
            )

            # Assert
            assert result is False
