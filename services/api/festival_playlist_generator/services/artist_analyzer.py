"""Artist Analyzer Service for retrieving and analyzing artist setlist data."""

import asyncio
import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, cast

import httpx
from sqlalchemy.orm import Session

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.models.setlist import Setlist as SetlistModel
from festival_playlist_generator.models.song import Song as SongModel
from festival_playlist_generator.schemas.setlist import Setlist, SetlistCreate
from festival_playlist_generator.schemas.song import Song, SongCreate

logger = logging.getLogger(__name__)


@dataclass
class SetlistData:
    """Raw setlist data from external sources."""

    artist_name: str
    venue: str
    date: datetime
    songs: List[str]
    tour_name: Optional[str] = None
    festival_name: Optional[str] = None
    source: str = "setlist.fm"


class SetlistFmClient:
    """Client for interacting with the Setlist.fm API."""

    BASE_URL = "https://api.setlist.fm/rest/1.0"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key
        self.logger = logging.getLogger(f"{__name__}.SetlistFmClient")
        self.session: Optional[httpx.AsyncClient] = None

        # Rate limiting: Setlist.fm allows 2 requests per second
        self._last_request_time = 0.0
        self._min_request_interval = 0.5  # 500ms between requests

    async def __aenter__(self) -> "SetlistFmClient":
        """Async context manager entry."""
        self.session = httpx.AsyncClient(
            headers={
                "Accept": "application/json",
                "x-api-key": self.api_key or "",
                "User-Agent": "FestivalPlaylistGenerator/1.0",
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self.session:
            await self.session.aclose()

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)

        self._last_request_time = asyncio.get_event_loop().time()

    async def search_artist(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Search for an artist by name using intelligent matching."""
        await self._rate_limit()

        try:
            if self.session is None:
                raise RuntimeError("Session not initialized. Use async context manager.")

            params: Dict[str, Any] = {"artistName": artist_name, "p": 1}  # First page only

            response = await self.session.get(
                f"{self.BASE_URL}/search/artists", params=params
            )

            if response.status_code == 200:
                data = response.json()
                artists = data.get("artist", [])

                if artists:
                    # Look for exact matches first
                    exact_matches = [
                        a
                        for a in artists
                        if a.get("name", "").lower() == artist_name.lower()
                    ]

                    if exact_matches:
                        # Use sophisticated scoring algorithm to find the best match
                        best_match = await self._score_and_select_artist(
                            exact_matches, artist_name
                        )
                        if best_match:
                            return best_match
                        else:
                            # Fallback to first exact match
                            self.logger.info(
                                f"Using first exact match for '{artist_name}': {exact_matches[0].get('name')}"
                            )
                            return cast(Dict[str, Any], exact_matches[0])
                    else:
                        # No exact match, use scoring on all results
                        best_match = await self._score_and_select_artist(
                            artists, artist_name
                        )
                        if best_match:
                            return best_match
                        else:
                            # Final fallback to first result
                            self.logger.info(
                                f"No exact match for '{artist_name}', using first result: {artists[0].get('name')}"
                            )
                            return cast(Dict[str, Any], artists[0])
                else:
                    self.logger.warning(f"No artists found for: {artist_name}")
                    return None

            elif response.status_code == 404:
                self.logger.info(f"Artist not found: {artist_name}")
                return None

            else:
                self.logger.error(
                    f"API error searching for artist {artist_name}: {response.status_code}"
                )
                return None

        except Exception as e:
            self.logger.error(f"Error searching for artist {artist_name}: {e}")
            return None

    async def _score_and_select_artist(
        self, artists: List[Dict[str, Any]], search_name: str
    ) -> Optional[Dict[str, Any]]:
        """Score artists based on multiple factors and select the best match."""
        scored_artists: List[Tuple[Dict[str, Any], float]] = []

        for artist in artists:
            score = await self._calculate_artist_score(artist, search_name)
            if score > 0:  # Only consider artists with positive scores
                scored_artists.append((artist, score))

        if not scored_artists:
            return None

        # Sort by score (highest first)
        scored_artists.sort(key=lambda x: x[1], reverse=True)
        best_artist, best_score = scored_artists[0]

        self.logger.info(
            f"Selected artist '{best_artist.get('name')}' with score {best_score:.2f} for search '{search_name}'"
        )

        # Log all candidates for debugging
        for artist, score in scored_artists[:3]:  # Top 3
            self.logger.debug(f"  Candidate: {artist.get('name')} (score: {score:.2f})")

        return best_artist

    async def _calculate_artist_score(self, artist: Dict[str, Any], search_name: str) -> float:
        """Calculate a likelihood score for an artist match."""
        score = 0.0
        artist_name = artist.get("name", "")
        mbid = artist.get("mbid")

        # Factor 1: Name similarity (base score)
        if artist_name.lower() == search_name.lower():
            score += 10.0  # Exact match bonus
        elif search_name.lower() in artist_name.lower():
            score += 5.0  # Partial match
        else:
            score += 1.0  # Fallback for fuzzy matches

        if not mbid:
            return score * 0.1  # Heavily penalize artists without MBID

        try:
            if self.session is None:
                raise RuntimeError("Session not initialized. Use async context manager.")

            # Factor 2: Setlist activity (most important for active bands)
            await self._rate_limit()
            params_setlist: Dict[str, Any] = {"p": 1}
            setlist_response = await self.session.get(
                f"{self.BASE_URL}/artist/{mbid}/setlists", params=params_setlist
            )

            if setlist_response.status_code == 200:
                setlist_data = setlist_response.json()
                setlists = setlist_data.get("setlist", [])

                # Count only past setlists with songs
                valid_setlists = 0
                total_songs = 0
                most_recent_year = 0
                current_year = 2026  # Update this as needed

                for setlist in setlists[:15]:  # Check more setlists to find valid ones
                    # Parse and validate the date
                    event_date = setlist.get("eventDate", "")
                    if not event_date:
                        continue  # Skip setlists without dates

                    try:
                        # Parse date format: dd-mm-yyyy
                        day, month, year = event_date.split("-")
                        year = int(year)

                        # Skip future gigs
                        if year > current_year:
                            continue

                        # For current year, we'd need more detailed date checking
                        # For now, we'll be conservative and skip 2026 dates
                        if year == current_year:
                            continue

                    except (ValueError, IndexError):
                        continue  # Skip setlists with invalid date formats

                    # Check if setlist has songs
                    sets = setlist.get("sets", {}).get("set", [])
                    setlist_songs = 0

                    for set_data in sets:
                        if isinstance(set_data, dict):
                            songs = set_data.get("song", [])
                            setlist_songs += len(songs) if songs else 0

                    # Only count setlists with actual songs
                    if setlist_songs > 0:
                        valid_setlists += 1
                        total_songs += setlist_songs
                        most_recent_year = max(most_recent_year, year)

                # Score based on valid setlist activity
                if valid_setlists > 0:
                    score += valid_setlists * 3.0  # 3 points per valid setlist
                    score += min(
                        total_songs / 10, 8.0
                    )  # Up to 8 points for song variety

                    # Factor 3: Recency bonus (active bands get higher scores)
                    years_since_last_show = current_year - most_recent_year
                    if years_since_last_show <= 1:
                        score += 8.0  # Very recent activity (2025)
                    elif years_since_last_show <= 3:
                        score += 5.0  # Recent activity (2023-2024)
                    elif years_since_last_show <= 5:
                        score += 3.0  # Somewhat recent (2021-2022)
                    elif years_since_last_show <= 10:
                        score += 1.0  # Still relevant (2016-2020)
                    # No bonus for older activity

                    # Factor 4: Consistency bonus (bands with many valid setlists are likely more notable)
                    if valid_setlists >= 8:
                        score += 5.0  # Very active
                    elif valid_setlists >= 5:
                        score += 3.0  # Active
                    elif valid_setlists >= 3:
                        score += 2.0  # Moderately active
                    elif valid_setlists >= 1:
                        score += 1.0  # Some activity

                    # Factor 5: Average songs per setlist (quality indicator)
                    avg_songs = total_songs / valid_setlists
                    if avg_songs >= 15:
                        score += 3.0  # Full setlists
                    elif avg_songs >= 10:
                        score += 2.0  # Decent setlists
                    elif avg_songs >= 5:
                        score += 1.0  # Short but valid setlists

                else:
                    # Heavily penalize artists with no valid setlists (past gigs with songs)
                    score *= 0.05  # Very low score for artists with no real performance history

            else:
                # Penalize artists we can't get setlist data for
                score *= 0.3

        except Exception as e:
            self.logger.debug(f"Error scoring artist {artist_name} ({mbid}): {e}")
            # Don't penalize for API errors, but don't give bonus either
            pass

        return score

    async def get_artist_setlists(
        self, artist_mbid: str, limit: int = 10
    ) -> List[SetlistData]:
        """Get recent setlists for an artist by MusicBrainz ID."""
        await self._rate_limit()

        try:
            if self.session is None:
                raise RuntimeError("Session not initialized. Use async context manager.")

            params_get: Dict[str, Any] = {"p": 1}  # Page number

            response = await self.session.get(
                f"{self.BASE_URL}/artist/{artist_mbid}/setlists", params=params_get
            )

            if response.status_code == 200:
                data = response.json()
                setlists_data = data.get("setlist", [])

                parsed_setlists = []
                for setlist_data in setlists_data[:limit]:
                    parsed = self._parse_setlist_data(setlist_data)
                    if parsed:
                        parsed_setlists.append(parsed)

                self.logger.info(
                    f"Retrieved {len(parsed_setlists)} setlists for artist {artist_mbid}"
                )
                return parsed_setlists

            elif response.status_code == 404:
                self.logger.info(f"No setlists found for artist: {artist_mbid}")
                return []

            else:
                self.logger.error(
                    f"API error getting setlists for {artist_mbid}: {response.status_code}"
                )
                return []

        except Exception as e:
            self.logger.error(f"Error getting setlists for artist {artist_mbid}: {e}")
            return []

    def _parse_setlist_data(self, setlist_data: Dict[str, Any]) -> Optional[SetlistData]:
        """Parse raw setlist data from API response."""
        try:
            # Extract basic info
            artist_name = setlist_data.get("artist", {}).get("name", "")
            venue_data = setlist_data.get("venue", {})
            venue_name = venue_data.get("name", "")
            city_data = venue_data.get("city", {})
            city_name = city_data.get("name", "")
            country_name = city_data.get("country", {}).get("name", "")

            venue = f"{venue_name}, {city_name}, {country_name}".strip(", ")

            # Parse date
            date_str = setlist_data.get("eventDate", "")
            if not date_str:
                self.logger.warning("Setlist missing date, skipping")
                return None

            try:
                # Date format: "dd-mm-yyyy"
                date = datetime.strptime(date_str, "%d-%m-%Y")
            except ValueError:
                self.logger.warning(f"Invalid date format: {date_str}")
                return None

            # Extract songs from sets
            songs = []
            sets_data = setlist_data.get("sets", {}).get("set", [])

            for set_data in sets_data:
                if isinstance(set_data, dict):
                    song_list = set_data.get("song", [])
                    for song_data in song_list:
                        if isinstance(song_data, dict):
                            song_name = song_data.get("name", "").strip()
                            if song_name:
                                songs.append(song_name)

            # Extract tour info
            tour_name = (
                setlist_data.get("tour", {}).get("name")
                if setlist_data.get("tour")
                else None
            )

            # Check if it's a festival
            festival_name = None
            if (
                venue_data.get("name")
                and "festival" in venue_data.get("name", "").lower()
            ):
                festival_name = venue_data.get("name")

            return SetlistData(
                artist_name=artist_name,
                venue=venue,
                date=date,
                songs=songs,
                tour_name=tour_name,
                festival_name=festival_name,
                source="setlist.fm",
            )

        except Exception as e:
            self.logger.error(f"Error parsing setlist data: {e}")
            return None


class SongNormalizer:
    """Handles song title normalization and cover song identification."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"{__name__}.SongNormalizer")

        # Common cover song indicators
        self.cover_indicators = [
            r"\(.*cover.*\)",
            r"\[.*cover.*\]",
            r"\(originally by.*\)",
            r"\[originally by.*\]",
            r"\(.*version\)",
            r"\[.*version\]",
        ]

    def normalize_song_title(self, title: str) -> str:
        """Normalize a song title for deduplication."""
        if not title:
            return ""

        # Start with the original title
        normalized = title.strip()

        # Early return for empty or whitespace-only strings
        if not normalized:
            return ""

        # Handle Unicode normalization
        normalized = unicodedata.normalize("NFKD", normalized)

        # Remove diacritics and accents
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

        # Convert to lowercase
        normalized = normalized.lower()

        # Remove common suffixes that don't affect song identity BEFORE removing punctuation
        # This ensures "(Live)" is properly detected and removed
        suffixes_to_remove = [
            r"\s*\(live\)\s*$",
            r"\s*\[live\]\s*$",
            r"\s*\(acoustic\)\s*$",
            r"\s*\[acoustic\]\s*$",
            r"\s*\(demo\)\s*$",
            r"\s*\[demo\]\s*$",
            r"\s*\(instrumental\)\s*$",
            r"\s*\[instrumental\]\s*$",
        ]

        for suffix_pattern in suffixes_to_remove:
            normalized = re.sub(suffix_pattern, "", normalized, flags=re.IGNORECASE)

        # Remove common punctuation and special characters
        # Keep alphanumeric, spaces, hyphens, and apostrophes
        normalized = re.sub(r"[^\w\s\-\']", " ", normalized)

        # Handle common variations
        normalized = re.sub(r"\bfeat\.?\s+", "featuring ", normalized)
        normalized = re.sub(r"\bft\.?\s+", "featuring ", normalized)
        normalized = re.sub(r"\b&\b", "and", normalized)

        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()

        # Final check - return empty string if normalization resulted in empty or whitespace-only string
        if not normalized or not normalized.strip():
            return ""

        return normalized

    def identify_cover_song(
        self, song_title: str, performing_artist: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Identify if a song is a cover and extract the original artist if possible.

        Returns:
            Tuple of (is_cover, original_artist)
        """
        if not song_title:
            return False, None

        # Check for explicit cover indicators
        for pattern in self.cover_indicators:
            match = re.search(pattern, song_title, re.IGNORECASE)
            if match:
                # Try to extract original artist from the match
                cover_text = match.group(0)
                original_artist = self._extract_original_artist(cover_text)
                return True, original_artist

        # Additional heuristics for cover detection
        # Check for common cover song patterns
        cover_patterns = [
            r"\(.*by\s+([^)]+)\)",
            r"\[.*by\s+([^\]]+)\]",
            r"originally\s+by\s+([^,\(\[\n]+)",
            r"cover\s+of\s+([^,\(\[\n]+)",
        ]

        for pattern in cover_patterns:
            match = re.search(pattern, song_title, re.IGNORECASE)
            if match:
                original_artist = match.group(1).strip()
                return True, original_artist

        return False, None

    def _extract_original_artist(self, cover_text: str) -> Optional[str]:
        """Extract original artist name from cover indicator text."""
        # Remove parentheses and brackets
        text = re.sub(r"[\(\)\[\]]", "", cover_text)

        # Look for "by" patterns
        by_patterns = [
            r"by\s+([^,\n]+)",
            r"originally\s+by\s+([^,\n]+)",
            r"cover\s+of\s+([^,\n]+)",
        ]

        for pattern in by_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                artist = match.group(1).strip()
                # Clean up common suffixes
                artist = re.sub(r"\s*(version|cover)$", "", artist, flags=re.IGNORECASE)
                return artist.strip()

        return None


class SongDeduplicator:
    """Handles song deduplication logic."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"{__name__}.SongDeduplicator")
        self.normalizer = SongNormalizer()

    def deduplicate_songs(
        self, songs: List[str], artist_name: str
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate a list of songs and identify covers.

        Returns:
            List of dictionaries with song info including cover detection
        """
        if not songs:
            return []

        # Process each song
        processed_songs = []
        for song in songs:
            if not song or not song.strip():
                continue

            normalized_title = self.normalizer.normalize_song_title(song)

            # Skip songs that normalize to empty strings
            if not normalized_title:
                self.logger.debug(f"Skipping song with empty normalized title: {song}")
                continue

            is_cover, original_artist = self.normalizer.identify_cover_song(
                song, artist_name
            )

            processed_songs.append(
                {
                    "original_title": song.strip(),
                    "normalized_title": normalized_title,
                    "is_cover": is_cover,
                    "original_artist": original_artist,
                    "performing_artist": artist_name,
                }
            )

        # Deduplicate based on normalized titles
        seen_normalized = {}
        deduplicated = []

        for song_info in processed_songs:
            normalized = song_info["normalized_title"]

            if normalized in seen_normalized:
                # Song already seen, skip duplicate
                self.logger.debug(
                    f"Skipping duplicate song: {song_info['original_title']}"
                )
                continue

            seen_normalized[normalized] = True
            deduplicated.append(song_info)

        self.logger.info(
            f"Deduplicated {len(songs)} songs to {len(deduplicated)} unique songs"
        )
        return deduplicated


class SongFrequencyAnalyzer:
    """Analyzes song performance frequency and creates rankings."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"{__name__}.SongFrequencyAnalyzer")

    def analyze_song_frequency(
        self, setlists: List[SetlistData]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze song frequency across multiple setlists.

        Returns:
            Dictionary mapping normalized song titles to frequency data
        """
        if not setlists:
            return {}

        song_frequency = {}
        normalizer = SongNormalizer()

        # Count song occurrences across all setlists
        for setlist in setlists:
            processed_songs = (
                set()
            )  # Track songs in this setlist to avoid double-counting

            for song in setlist.songs:
                if not song or not song.strip():
                    continue

                normalized_title = normalizer.normalize_song_title(song)

                # Skip songs that normalize to empty strings
                if not normalized_title:
                    self.logger.debug(
                        f"Skipping song with empty normalized title: {song}"
                    )
                    continue

                # Skip if we've already processed this song in this setlist
                if normalized_title in processed_songs:
                    continue

                processed_songs.add(normalized_title)

                # Initialize or update frequency data
                if normalized_title not in song_frequency:
                    is_cover, original_artist = normalizer.identify_cover_song(
                        song, setlist.artist_name
                    )

                    song_frequency[normalized_title] = {
                        "original_title": song.strip(),
                        "normalized_title": normalized_title,
                        "frequency": 0,
                        "is_cover": is_cover,
                        "original_artist": original_artist,
                        "performing_artist": setlist.artist_name,
                        "first_seen": setlist.date,
                        "last_seen": setlist.date,
                        "venues": [],
                    }

                # Update frequency and metadata
                song_data: Dict[str, Any] = song_frequency[normalized_title]
                song_data["frequency"] = song_data["frequency"] + 1
                song_data["last_seen"] = max(
                    song_data["last_seen"], setlist.date
                )
                song_data["first_seen"] = min(
                    song_data["first_seen"], setlist.date
                )

                venues_list: List[str] = song_data["venues"]
                if setlist.venue not in venues_list:
                    venues_list.append(setlist.venue)

        self.logger.info(
            f"Analyzed frequency for {len(song_frequency)} unique songs across {len(setlists)} setlists"
        )
        return song_frequency

    def rank_songs_by_frequency(
        self, song_frequency: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rank songs by performance frequency.

        Returns:
            List of song data dictionaries sorted by frequency (descending)
        """
        if not song_frequency:
            return []

        # Sort by frequency (descending), then by last seen date (descending)
        ranked_songs = sorted(
            song_frequency.values(),
            key=lambda x: (x["frequency"], x["last_seen"]),
            reverse=True,
        )

        # Add rank information
        for i, song_data in enumerate(ranked_songs, 1):
            song_data["rank"] = i

        self.logger.info(f"Ranked {len(ranked_songs)} songs by frequency")
        return ranked_songs


class ArtistAnalyzerService:
    """Main service for analyzing artist setlist data."""

    def __init__(self, setlist_fm_api_key: Optional[str] = None) -> None:
        self.logger = logging.getLogger(f"{__name__}.ArtistAnalyzerService")
        self.setlist_fm_api_key = setlist_fm_api_key
        self.deduplicator = SongDeduplicator()
        self.frequency_analyzer = SongFrequencyAnalyzer()
        self.db: Optional[Any] = None  # Set by dependency injection

    async def get_artist_setlists(
        self, artist_name: str, limit: int = 10
    ) -> List[Setlist]:
        """
        Get recent setlists for an artist.

        Args:
            artist_name: Name of the artist
            limit: Maximum number of setlists to retrieve

        Returns:
            List of Setlist objects
        """
        self.logger.info(f"Getting setlists for artist: {artist_name} (limit: {limit})")

        try:
            async with SetlistFmClient(self.setlist_fm_api_key) as client:
                # First, search for the artist to get their MusicBrainz ID
                artist_data = await client.search_artist(artist_name)

                if not artist_data:
                    self.logger.warning(f"Artist not found: {artist_name}")
                    return []

                artist_mbid = artist_data.get("mbid")
                if not artist_mbid:
                    self.logger.warning(
                        f"No MusicBrainz ID found for artist: {artist_name}"
                    )
                    return []

                # Get setlists for the artist
                setlist_data = await client.get_artist_setlists(artist_mbid, limit)

                if not setlist_data:
                    self.logger.info(f"No setlists found for artist: {artist_name}")
                    return []

                # Convert to Pydantic models and store in database
                setlists = []
                for data in setlist_data:
                    setlist = await self._store_setlist(data)
                    if setlist:
                        setlists.append(setlist)

                self.logger.info(
                    f"Retrieved and stored {len(setlists)} setlists for {artist_name}"
                )
                return setlists

        except Exception as e:
            self.logger.error(f"Error getting setlists for {artist_name}: {e}")
            return []

    async def analyze_song_frequency(self, setlists: List[Setlist]) -> Dict[str, int]:
        """
        Analyze song frequency from setlists.

        Args:
            setlists: List of Setlist objects

        Returns:
            Dictionary mapping song titles to frequency counts
        """
        if not setlists:
            return {}

        # Convert Setlist objects to SetlistData for analysis
        setlist_data = []
        for setlist in setlists:
            data = SetlistData(
                artist_name=setlist.artist_name,
                venue=setlist.venue,
                date=setlist.date,
                songs=setlist.songs,
                tour_name=setlist.tour_name,
                festival_name=setlist.festival_name,
                source=setlist.source,
            )
            setlist_data.append(data)

        # Analyze frequency
        frequency_data = self.frequency_analyzer.analyze_song_frequency(setlist_data)

        # Return simple frequency mapping
        return {
            data["original_title"]: data["frequency"]
            for data in frequency_data.values()
        }

    async def normalize_song_titles(self, songs: List[str]) -> List[str]:
        """
        Normalize song titles for deduplication.

        Args:
            songs: List of song titles

        Returns:
            List of normalized song titles
        """
        normalizer = SongNormalizer()
        return [normalizer.normalize_song_title(song) for song in songs]

    async def identify_cover_songs(
        self, songs: List[str], artist: str
    ) -> Dict[str, str]:
        """
        Identify cover songs and their original artists.

        Args:
            songs: List of song titles
            artist: Performing artist name

        Returns:
            Dictionary mapping song titles to original artists (for covers only)
        """
        normalizer = SongNormalizer()
        covers = {}

        for song in songs:
            is_cover, original_artist = normalizer.identify_cover_song(song, artist)
            if is_cover and original_artist:
                covers[song] = original_artist

        return covers

    async def _store_setlist(self, setlist_data: SetlistData) -> Optional[Setlist]:
        """Store setlist data in the database."""
        try:
            from sqlalchemy import select

            from festival_playlist_generator.core.database import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                # First, find or create the artist
                result = await db.execute(
                    select(ArtistModel).where(
                        ArtistModel.name == setlist_data.artist_name
                    )
                )
                artist = result.scalar_one_or_none()

                if not artist:
                    artist = ArtistModel(name=setlist_data.artist_name)
                    db.add(artist)
                    await db.flush()  # Get the ID

                # Check if setlist already exists
                result_setlist = await db.execute(
                    select(SetlistModel).where(
                        SetlistModel.artist_id == artist.id,
                        SetlistModel.venue == setlist_data.venue,
                        SetlistModel.date == setlist_data.date,
                    )
                )
                existing_setlist = result_setlist.scalar_one_or_none()

                if existing_setlist:
                    # Update existing setlist
                    existing_setlist.songs = setlist_data.songs
                    existing_setlist.tour_name = setlist_data.tour_name
                    existing_setlist.festival_name = setlist_data.festival_name
                    existing_setlist.source = setlist_data.source
                    existing_setlist.updated_at = datetime.utcnow()

                    setlist_model = existing_setlist
                else:
                    # Create new setlist
                    setlist_model = SetlistModel(
                        artist_id=artist.id,
                        venue=setlist_data.venue,
                        date=setlist_data.date,
                        songs=setlist_data.songs,
                        tour_name=setlist_data.tour_name,
                        festival_name=setlist_data.festival_name,
                        source=setlist_data.source,
                    )
                    db.add(setlist_model)

                await db.commit()

                # Convert to Pydantic model
                setlist = Setlist(
                    id=setlist_model.id,
                    artist_id=setlist_model.artist_id,
                    artist_name=artist.name,
                    venue=setlist_model.venue,
                    date=setlist_model.date,
                    songs=setlist_model.songs,
                    tour_name=setlist_model.tour_name,
                    festival_name=setlist_model.festival_name,
                    source=setlist_model.source,
                    created_at=setlist_model.created_at,
                    updated_at=setlist_model.updated_at,
                )

                return setlist

        except Exception as e:
            self.logger.error(f"Error storing setlist: {e}")
            return None
