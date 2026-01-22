"""Spotify Artist Service for fetching artist information and images."""

import logging
from typing import Any, Dict, List, Optional

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)


class SpotifyArtistInfo:
    """Artist information from Spotify."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self.id = data.get("id")
        self.name = data.get("name")
        self.genres = data.get("genres", [])
        self.popularity = data.get("popularity", 0)
        self.followers = data.get("followers", {}).get("total", 0)
        self.images = data.get("images", [])
        self.external_urls = data.get("external_urls", {})

    @property
    def image_url(self) -> Optional[str]:
        """Get the best quality image URL."""
        if not self.images:
            return None

        # Sort by size (width * height) and return the largest
        sorted_images = sorted(
            self.images,
            key=lambda img: (img.get("width", 0) * img.get("height", 0)),
            reverse=True,
        )
        return sorted_images[0].get("url")  # type: ignore[no-any-return]

    @property
    def medium_image_url(self) -> Optional[str]:
        """Get a medium-sized image URL (around 300px)."""
        if not self.images:
            return None

        # Find image closest to 300px width
        target_width = 300
        best_image = min(
            self.images, key=lambda img: abs(img.get("width", 0) - target_width)
        )
        return best_image.get("url")  # type: ignore[no-any-return]

    @property
    def small_image_url(self) -> Optional[str]:
        """Get a small image URL (around 160px)."""
        if not self.images:
            return None

        # Find image closest to 160px width
        target_width = 160
        best_image = min(
            self.images, key=lambda img: abs(img.get("width", 0) - target_width)
        )
        return best_image.get("url")  # type: ignore[no-any-return]

    @property
    def spotify_url(self) -> Optional[str]:
        """Get Spotify URL for the artist."""
        return self.external_urls.get("spotify")  # type: ignore[no-any-return]


class SpotifyArtistService:
    """Service for fetching artist information from Spotify."""

    def __init__(self) -> None:
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self._spotify: Optional[Any] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Spotify client with client credentials flow."""
        if not self.client_id or not self.client_secret:
            logger.warning("Spotify credentials not configured")
            return

        try:
            client_credentials_manager = SpotifyClientCredentials(
                client_id=self.client_id, client_secret=self.client_secret
            )
            self._spotify = spotipy.Spotify(
                client_credentials_manager=client_credentials_manager
            )
            logger.info("Spotify client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Spotify client: {e}")
            self._spotify = None

    def search_artist(self, artist_name: str) -> Optional[SpotifyArtistInfo]:
        """Search for an artist on Spotify and return their information."""
        if not self._spotify:
            logger.warning("Spotify client not available")
            return None

        try:
            # Search for the artist
            results = self._spotify.search(
                q=f"artist:{artist_name}", type="artist", limit=1
            )

            if not results["artists"]["items"]:
                logger.info(f"No Spotify results found for artist: {artist_name}")
                return None

            artist_data = results["artists"]["items"][0]
            return SpotifyArtistInfo(artist_data)

        except Exception as e:
            logger.error(f"Error searching for artist {artist_name} on Spotify: {e}")
            return None

    def search_artists_multiple(
        self, artist_name: str, limit: int = 5
    ) -> List[SpotifyArtistInfo]:
        """Search for artists on Spotify and return multiple results."""
        if not self._spotify:
            logger.warning("Spotify client not available")
            return []

        try:
            # Search for the artist
            results = self._spotify.search(
                q=f"artist:{artist_name}", type="artist", limit=limit
            )

            if not results["artists"]["items"]:
                logger.info(f"No Spotify results found for artist: {artist_name}")
                return []

            return [
                SpotifyArtistInfo(artist_data)
                for artist_data in results["artists"]["items"]
            ]

        except Exception as e:
            logger.error(f"Error searching for artist {artist_name} on Spotify: {e}")
            return []

    def get_artist_by_id(self, spotify_id: str) -> Optional[SpotifyArtistInfo]:
        """Get artist information by Spotify ID."""
        if not self._spotify:
            logger.warning("Spotify client not available")
            return None

        try:
            artist_data = self._spotify.artist(spotify_id)
            return SpotifyArtistInfo(artist_data)

        except Exception as e:
            logger.error(f"Error fetching artist {spotify_id} from Spotify: {e}")
            return None

    def get_artist_top_tracks(
        self, spotify_id: str, country: str = "US"
    ) -> List[Dict[str, Any]]:
        """Get artist's top tracks from Spotify."""
        if not self._spotify:
            logger.warning("Spotify client not available")
            return []

        try:
            results = self._spotify.artist_top_tracks(spotify_id, country=country)
            tracks: List[Dict[str, Any]] = results.get("tracks", [])
            return tracks

        except Exception as e:
            logger.error(f"Error fetching top tracks for artist {spotify_id}: {e}")
            return []

    def get_related_artists(self, spotify_id: str) -> List[SpotifyArtistInfo]:
        """Get related artists from Spotify."""
        if not self._spotify:
            logger.warning("Spotify client not available")
            return []

        try:
            results = self._spotify.artist_related_artists(spotify_id)
            related_artists = []

            for artist_data in results.get("artists", []):
                related_artists.append(SpotifyArtistInfo(artist_data))

            return related_artists

        except Exception as e:
            logger.error(f"Error fetching related artists for {spotify_id}: {e}")
            return []

    def is_available(self) -> bool:
        """Check if Spotify service is available."""
        return self._spotify is not None


# Global instance
spotify_artist_service = SpotifyArtistService()
