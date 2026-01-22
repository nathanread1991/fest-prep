"""Spotify service with circuit breaker pattern for API resilience."""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, cast

import httpx

from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker implementation for external API calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing recovery, allow limited requests

    Requirements: US-7.6
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise Exception("Circuit breaker is OPEN - service unavailable")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            if isinstance(e, self.expected_exception):
                self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return False

        return (
            datetime.now() - self.last_failure_time
        ).total_seconds() >= self.recovery_timeout

    def _on_success(self) -> None:
        """Handle successful request."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker recovered - entering CLOSED state")

    def _on_failure(self) -> None:
        """Handle failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )


class SpotifyService:
    """
    Service for Spotify API integration with circuit breaker.

    Provides methods for:
    - Artist search
    - Playlist creation
    - Adding tracks to playlists
    - Token refresh

    Includes comprehensive error handling and circuit breaker pattern.

    Requirements: US-7.6
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ) -> None:
        """
        Initialize Spotify service.

        Args:
            client_id: Spotify client ID (defaults to settings)
            client_secret: Spotify client secret (defaults to settings)
            redirect_uri: OAuth redirect URI (defaults to settings)
        """
        self.client_id = client_id or getattr(settings, "SPOTIFY_CLIENT_ID", None)
        self.client_secret = client_secret or getattr(
            settings, "SPOTIFY_CLIENT_SECRET", None
        )
        self.redirect_uri = redirect_uri or getattr(
            settings, "SPOTIFY_REDIRECT_URI", None
        )

        # Circuit breaker for API calls
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5, recovery_timeout=60, expected_exception=httpx.HTTPError
        )

        # HTTP client with timeout
        self.client = httpx.AsyncClient(timeout=10.0)

        self.base_url = "https://api.spotify.com/v1"
        self.auth_url = "https://accounts.spotify.com/api/token"

    async def search_artist(
        self, artist_name: str, access_token: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for an artist on Spotify with circuit breaker.

        Args:
            artist_name: Name of artist to search
            access_token: User's Spotify access token
            limit: Maximum number of results

        Returns:
            List of artist data dictionaries
        """

        async def _search() -> List[Dict[str, Any]]:
            headers = {"Authorization": f"Bearer {access_token}"}
            params: Dict[str, str | int] = {"q": artist_name, "type": "artist", "limit": str(limit)}

            response = await self.client.get(
                f"{self.base_url}/search", headers=headers, params=params
            )
            response.raise_for_status()

            data = cast(Dict[str, Any], response.json())
            return cast(List[Dict[str, Any]], data.get("artists", {}).get("items", []))

        try:
            result: List[Dict[str, Any]] = await self.circuit_breaker.call(_search)
            return result
        except Exception as e:
            logger.error(f"Failed to search artist '{artist_name}': {e}")
            return []

    async def create_playlist(
        self, name: str, description: str, access_token: str, public: bool = False
    ) -> str:
        """
        Create a playlist on Spotify with circuit breaker.

        Args:
            name: Playlist name
            description: Playlist description
            access_token: User's Spotify access token
            public: Whether playlist should be public

        Returns:
            Spotify playlist ID

        Raises:
            Exception: If creation fails
        """

        async def _create() -> str:
            # First get user ID
            user_id = await self._get_current_user_id(access_token)

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            payload = {"name": name, "description": description, "public": public}

            response = await self.client.post(
                f"{self.base_url}/users/{user_id}/playlists",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            data = response.json()
            playlist_id: str = data["id"]
            return playlist_id

        result: str = await self.circuit_breaker.call(_create)
        return result

    async def add_tracks_to_playlist(
        self, playlist_id: str, track_uris: List[str], access_token: str
    ) -> bool:
        """
        Add tracks to a Spotify playlist with circuit breaker.

        Spotify allows max 100 tracks per request, so this method
        batches requests if needed.

        Args:
            playlist_id: Spotify playlist ID
            track_uris: List of Spotify track URIs (e.g., "spotify:track:...")
            access_token: User's Spotify access token

        Returns:
            True if successful
        """

        async def _add_batch(batch: List[str]) -> bool:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            payload = {"uris": batch}

            response = await self.client.post(
                f"{self.base_url}/playlists/{playlist_id}/tracks",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return True

        try:
            # Batch requests (max 100 tracks per request)
            for i in range(0, len(track_uris), 100):
                batch = track_uris[i : i + 100]
                await self.circuit_breaker.call(_add_batch, batch)

            return True
        except Exception as e:
            logger.error(f"Failed to add tracks to playlist {playlist_id}: {e}")
            return False

    async def refresh_access_token(
        self, refresh_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Refresh Spotify access token.

        Args:
            refresh_token: User's refresh token

        Returns:
            Dictionary with access_token, expires_in, etc., or None on failure
        """

        async def _refresh() -> Dict[str, Any]:
            import base64

            # Encode client credentials
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            data = {"grant_type": "refresh_token", "refresh_token": refresh_token}

            response = await self.client.post(self.auth_url, headers=headers, data=data)
            response.raise_for_status()

            return cast(Dict[str, Any], response.json())

        try:
            result: Dict[str, Any] = await self.circuit_breaker.call(_refresh)
            return result
        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            return None

    async def get_track(
        self, track_id: str, access_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get track details from Spotify.

        Args:
            track_id: Spotify track ID
            access_token: User's Spotify access token

        Returns:
            Track data dictionary or None on failure
        """

        async def _get() -> Dict[str, Any]:
            headers = {"Authorization": f"Bearer {access_token}"}

            response = await self.client.get(
                f"{self.base_url}/tracks/{track_id}", headers=headers
            )
            response.raise_for_status()

            return cast(Dict[str, Any], response.json())

        try:
            result: Dict[str, Any] = await self.circuit_breaker.call(_get)
            return result
        except Exception as e:
            logger.error(f"Failed to get track {track_id}: {e}")
            return None

    async def search_track(
        self, track_name: str, artist_name: str, access_token: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for a track on Spotify.

        Args:
            track_name: Name of track to search
            artist_name: Name of artist
            access_token: User's Spotify access token
            limit: Maximum number of results

        Returns:
            List of track data dictionaries
        """

        async def _search() -> List[Dict[str, Any]]:
            headers = {"Authorization": f"Bearer {access_token}"}
            params: Dict[str, str | int] = {
                "q": f"track:{track_name} artist:{artist_name}",
                "type": "track",
                "limit": str(limit),
            }

            response = await self.client.get(
                f"{self.base_url}/search", headers=headers, params=params
            )
            response.raise_for_status()

            data = cast(Dict[str, Any], response.json())
            return cast(List[Dict[str, Any]], data.get("tracks", {}).get("items", []))

        try:
            result: List[Dict[str, Any]] = await self.circuit_breaker.call(_search)
            return result
        except Exception as e:
            logger.error(
                f"Failed to search track '{track_name}' by '{artist_name}': {e}"
            )
            return []

    async def _get_current_user_id(self, access_token: str) -> str:
        """
        Get current user's Spotify ID.

        Args:
            access_token: User's Spotify access token

        Returns:
            User's Spotify ID
        """
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await self.client.get(f"{self.base_url}/me", headers=headers)
        response.raise_for_status()

        data = response.json()
        user_id: str = data["id"]
        return user_id

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
