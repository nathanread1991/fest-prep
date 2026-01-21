"""Streaming Integration Service for managing authentication and playlist creation across platforms."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
import spotipy
from pydantic import BaseModel
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic

from ..schemas.playlist import StreamingPlatform
from ..schemas.song import Song

logger = logging.getLogger(__name__)


class AuthToken(BaseModel):
    """Authentication token for streaming platforms."""

    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    platform: StreamingPlatform
    user_id: str


class Track(BaseModel):
    """Track representation from streaming platforms."""

    id: str
    title: str
    artist: str
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    is_live: bool = False
    is_cover: bool = False
    platform: StreamingPlatform
    external_url: Optional[str] = None


class StreamingPlatformClient(ABC):
    """Abstract base class for streaming platform clients."""

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> AuthToken:
        """Authenticate with the streaming platform."""
        pass

    @abstractmethod
    async def refresh_token(self, auth_token: AuthToken) -> AuthToken:
        """Refresh an expired authentication token."""
        pass

    @abstractmethod
    async def search_song(
        self, song: str, artist: str, auth_token: AuthToken
    ) -> List[Track]:
        """Search for a song on the platform."""
        pass

    @abstractmethod
    async def create_playlist(
        self, name: str, description: str, auth_token: AuthToken
    ) -> str:
        """Create a new playlist on the platform."""
        pass

    @abstractmethod
    async def add_tracks_to_playlist(
        self, playlist_id: str, track_ids: List[str], auth_token: AuthToken
    ) -> bool:
        """Add tracks to an existing playlist."""
        pass


class SpotifyClient(StreamingPlatformClient):
    """Spotify streaming platform client."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    async def authenticate(self, credentials: Dict[str, Any]) -> AuthToken:
        """Authenticate with Spotify using OAuth2."""
        try:
            auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope="playlist-modify-public playlist-modify-private",
            )

            # Handle different credential types
            if "authorization_code" in credentials:
                token_info = auth_manager.get_access_token(
                    credentials["authorization_code"]
                )
            elif "refresh_token" in credentials:
                token_info = auth_manager.refresh_access_token(
                    credentials["refresh_token"]
                )
            else:
                raise ValueError("Invalid credentials provided")

            expires_at = datetime.now() + timedelta(seconds=token_info["expires_in"])

            # Get user info to extract user ID
            sp = spotipy.Spotify(auth=token_info["access_token"])
            user_info = sp.current_user()

            return AuthToken(
                access_token=token_info["access_token"],
                refresh_token=token_info.get("refresh_token"),
                expires_at=expires_at,
                platform=StreamingPlatform.SPOTIFY,
                user_id=user_info["id"],
            )
        except Exception as e:
            logger.error(f"Spotify authentication failed: {e}")
            raise

    async def refresh_token(self, auth_token: AuthToken) -> AuthToken:
        """Refresh Spotify access token."""
        if not auth_token.refresh_token:
            raise ValueError("No refresh token available")

        return await self.authenticate({"refresh_token": auth_token.refresh_token})

    async def search_song(
        self, song: str, artist: str, auth_token: AuthToken
    ) -> List[Track]:
        """Search for a song on Spotify."""
        try:
            sp = spotipy.Spotify(auth=auth_token.access_token)
            query = f"track:{song} artist:{artist}"
            results = sp.search(q=query, type="track", limit=10)

            tracks = []
            for item in results["tracks"]["items"]:
                # Determine if it's a live version
                is_live = any(
                    keyword in item["name"].lower()
                    for keyword in ["live", "concert", "tour"]
                )

                track = Track(
                    id=item["id"],
                    title=item["name"],
                    artist=", ".join([artist["name"] for artist in item["artists"]]),
                    album=item["album"]["name"],
                    duration_ms=item["duration_ms"],
                    is_live=is_live,
                    platform=StreamingPlatform.SPOTIFY,
                    external_url=item["external_urls"]["spotify"],
                )
                tracks.append(track)

            return tracks
        except Exception as e:
            logger.error(f"Spotify search failed for {song} by {artist}: {e}")
            return []

    async def create_playlist(
        self, name: str, description: str, auth_token: AuthToken
    ) -> str:
        """Create a new playlist on Spotify."""
        try:
            sp = spotipy.Spotify(auth=auth_token.access_token)
            playlist = sp.user_playlist_create(
                user=auth_token.user_id,
                name=name,
                description=description,
                public=False,
            )
            return playlist["id"]
        except Exception as e:
            logger.error(f"Failed to create Spotify playlist: {e}")
            raise

    async def add_tracks_to_playlist(
        self, playlist_id: str, track_ids: List[str], auth_token: AuthToken
    ) -> bool:
        """Add tracks to a Spotify playlist."""
        try:
            sp = spotipy.Spotify(auth=auth_token.access_token)
            # Spotify allows max 100 tracks per request
            for i in range(0, len(track_ids), 100):
                batch = track_ids[i : i + 100]
                sp.playlist_add_items(playlist_id, batch)
            return True
        except Exception as e:
            logger.error(f"Failed to add tracks to Spotify playlist: {e}")
            return False


class YouTubeMusicClient(StreamingPlatformClient):
    """YouTube Music streaming platform client."""

    def __init__(self):
        self.ytmusic = None

    async def authenticate(self, credentials: Dict[str, Any]) -> AuthToken:
        """Authenticate with YouTube Music."""
        try:
            # YouTube Music uses OAuth2 headers file
            if "oauth_file" in credentials:
                self.ytmusic = YTMusic(credentials["oauth_file"])
            else:
                raise ValueError("OAuth file required for YouTube Music authentication")

            # YouTube Music doesn't provide user ID directly, use a placeholder
            return AuthToken(
                access_token="ytmusic_authenticated",
                platform=StreamingPlatform.YOUTUBE_MUSIC,
                user_id="ytmusic_user",
            )
        except Exception as e:
            logger.error(f"YouTube Music authentication failed: {e}")
            raise

    async def refresh_token(self, auth_token: AuthToken) -> AuthToken:
        """YouTube Music tokens are handled internally by ytmusicapi."""
        return auth_token

    async def search_song(
        self, song: str, artist: str, auth_token: AuthToken
    ) -> List[Track]:
        """Search for a song on YouTube Music."""
        try:
            if not self.ytmusic:
                raise ValueError("YouTube Music client not authenticated")

            query = f"{song} {artist}"
            results = self.ytmusic.search(query, filter="songs", limit=10)

            tracks = []
            for item in results:
                # Determine if it's a live version
                is_live = any(
                    keyword in item["title"].lower()
                    for keyword in ["live", "concert", "tour"]
                )

                track = Track(
                    id=item["videoId"],
                    title=item["title"],
                    artist=", ".join(
                        [artist["name"] for artist in item.get("artists", [])]
                    ),
                    album=(
                        item.get("album", {}).get("name") if item.get("album") else None
                    ),
                    duration_ms=(
                        item.get("duration_seconds", 0) * 1000
                        if item.get("duration_seconds")
                        else None
                    ),
                    is_live=is_live,
                    platform=StreamingPlatform.YOUTUBE_MUSIC,
                )
                tracks.append(track)

            return tracks
        except Exception as e:
            logger.error(f"YouTube Music search failed for {song} by {artist}: {e}")
            return []

    async def create_playlist(
        self, name: str, description: str, auth_token: AuthToken
    ) -> str:
        """Create a new playlist on YouTube Music."""
        try:
            if not self.ytmusic:
                raise ValueError("YouTube Music client not authenticated")

            playlist_id = self.ytmusic.create_playlist(name, description)
            return playlist_id
        except Exception as e:
            logger.error(f"Failed to create YouTube Music playlist: {e}")
            raise

    async def add_tracks_to_playlist(
        self, playlist_id: str, track_ids: List[str], auth_token: AuthToken
    ) -> bool:
        """Add tracks to a YouTube Music playlist."""
        try:
            if not self.ytmusic:
                raise ValueError("YouTube Music client not authenticated")

            self.ytmusic.add_playlist_items(playlist_id, track_ids)
            return True
        except Exception as e:
            logger.error(f"Failed to add tracks to YouTube Music playlist: {e}")
            return False


class AppleMusicClient(StreamingPlatformClient):
    """Apple Music streaming platform client (placeholder implementation)."""

    def __init__(self, developer_token: str):
        self.developer_token = developer_token

    async def authenticate(self, credentials: Dict[str, Any]) -> AuthToken:
        """Authenticate with Apple Music."""
        # Apple Music uses JWT developer tokens
        return AuthToken(
            access_token=self.developer_token,
            platform=StreamingPlatform.APPLE_MUSIC,
            user_id="apple_music_user",
        )

    async def refresh_token(self, auth_token: AuthToken) -> AuthToken:
        """Apple Music uses long-lived developer tokens."""
        return auth_token

    async def search_song(
        self, song: str, artist: str, auth_token: AuthToken
    ) -> List[Track]:
        """Search for a song on Apple Music."""
        # Placeholder implementation - would use Apple Music API
        logger.warning("Apple Music search not fully implemented")
        return []

    async def create_playlist(
        self, name: str, description: str, auth_token: AuthToken
    ) -> str:
        """Create a new playlist on Apple Music."""
        # Placeholder implementation - would use Apple Music API
        logger.warning("Apple Music playlist creation not fully implemented")
        raise NotImplementedError("Apple Music playlist creation not implemented")

    async def add_tracks_to_playlist(
        self, playlist_id: str, track_ids: List[str], auth_token: AuthToken
    ) -> bool:
        """Add tracks to an Apple Music playlist."""
        # Placeholder implementation - would use Apple Music API
        logger.warning("Apple Music playlist modification not fully implemented")
        return False


class StreamingIntegrationService:
    """Main service for streaming platform integration."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.clients: Dict[StreamingPlatform, StreamingPlatformClient] = {}
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize streaming platform clients."""
        # Initialize Spotify client
        if "spotify" in self.config:
            spotify_config = self.config["spotify"]
            self.clients[StreamingPlatform.SPOTIFY] = SpotifyClient(
                client_id=spotify_config["client_id"],
                client_secret=spotify_config["client_secret"],
                redirect_uri=spotify_config["redirect_uri"],
            )

        # Initialize YouTube Music client
        if "youtube_music" in self.config:
            self.clients[StreamingPlatform.YOUTUBE_MUSIC] = YouTubeMusicClient()

        # Initialize Apple Music client
        if "apple_music" in self.config:
            apple_config = self.config["apple_music"]
            self.clients[StreamingPlatform.APPLE_MUSIC] = AppleMusicClient(
                developer_token=apple_config["developer_token"]
            )

    async def authenticate_user(
        self, platform: StreamingPlatform, credentials: Dict[str, Any]
    ) -> AuthToken:
        """Authenticate user with a streaming platform."""
        if platform not in self.clients:
            raise ValueError(f"Platform {platform} not supported or configured")

        client = self.clients[platform]
        return await client.authenticate(credentials)

    async def refresh_authentication(self, auth_token: AuthToken) -> AuthToken:
        """Refresh an authentication token."""
        if auth_token.platform not in self.clients:
            raise ValueError(f"Platform {auth_token.platform} not supported")

        client = self.clients[auth_token.platform]
        return await client.refresh_token(auth_token)

    async def search_song(
        self, song: str, artist: str, platform: StreamingPlatform, auth_token: AuthToken
    ) -> List[Track]:
        """Search for a song on a streaming platform."""
        if platform not in self.clients:
            raise ValueError(f"Platform {platform} not supported")

        client = self.clients[platform]
        return await client.search_song(song, artist, auth_token)

    async def prioritize_studio_versions(self, tracks: List[Track]) -> List[Track]:
        """Prioritize studio versions over live versions."""

        # Sort tracks: studio versions first, then by relevance
        def sort_key(track: Track) -> Tuple[int, str]:
            # Studio versions get priority (0), live versions get lower priority (1)
            live_priority = 0 if not track.is_live else 1
            return (live_priority, track.title.lower())

        return sorted(tracks, key=sort_key)

    async def find_cover_song_fallback(
        self,
        song: str,
        original_artist: str,
        cover_artist: str,
        platform: StreamingPlatform,
        auth_token: AuthToken,
    ) -> Optional[Track]:
        """Find original version when cover is not available."""
        # First try to find the cover version
        try:
            cover_tracks = await self.search_song(
                song, cover_artist, platform, auth_token
            )
            if cover_tracks:
                prioritized = await self.prioritize_studio_versions(cover_tracks)
                if prioritized:
                    return prioritized[0]
        except Exception as e:
            logger.warning(
                f"Cover song search failed for {song} by {cover_artist}: {e}"
            )

        # If cover not found or search failed, try original artist
        try:
            original_tracks = await self.search_song(
                song, original_artist, platform, auth_token
            )
            if original_tracks:
                prioritized = await self.prioritize_studio_versions(original_tracks)
                if prioritized:
                    return prioritized[0]
        except Exception as e:
            logger.warning(
                f"Original song search failed for {song} by {original_artist}: {e}"
            )

        return None

    async def create_playlist(
        self,
        name: str,
        description: str,
        songs: List[Song],
        platform: StreamingPlatform,
        auth_token: AuthToken,
    ) -> Tuple[str, List[str]]:
        """Create a playlist on a streaming platform."""
        if platform not in self.clients:
            raise ValueError(f"Platform {platform} not supported")

        client = self.clients[platform]

        # Create the playlist
        playlist_id = await client.create_playlist(name, description, auth_token)

        # Search for and add songs
        found_tracks = []
        for song in songs:
            tracks = await self.search_song(
                song.title, song.artist, platform, auth_token
            )
            if tracks:
                # Prioritize studio versions
                prioritized = await self.prioritize_studio_versions(tracks)
                if prioritized:
                    found_tracks.append(prioritized[0].id)
            else:
                logger.warning(f"Song not found: {song.title} by {song.artist}")

        # Add tracks to playlist
        if found_tracks:
            success = await client.add_tracks_to_playlist(
                playlist_id, found_tracks, auth_token
            )
            if not success:
                logger.error(f"Failed to add some tracks to playlist {playlist_id}")

        return playlist_id, found_tracks

    def generate_playlist_name(
        self,
        festival_name: Optional[str] = None,
        artist_name: Optional[str] = None,
        date: Optional[datetime] = None,
    ) -> str:
        """Generate descriptive playlist names."""
        if festival_name and date:
            return f"{festival_name} {date.year} - Festival Playlist"
        elif festival_name:
            return f"{festival_name} - Festival Playlist"
        elif artist_name and date:
            return f"{artist_name} - Setlist Playlist ({date.strftime('%B %Y')})"
        elif artist_name:
            return f"{artist_name} - Setlist Playlist"
        else:
            return f"Generated Playlist - {datetime.now().strftime('%B %Y')}"
