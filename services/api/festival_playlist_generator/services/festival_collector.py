"""Festival Collector Service for gathering and processing festival data."""

import hashlib
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import and_
from sqlalchemy.orm import Session

from festival_playlist_generator.core.config import settings
from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.models.festival import Festival as FestivalModel
from festival_playlist_generator.schemas.festival import Festival, FestivalCreate

logger = logging.getLogger(__name__)


@dataclass
class RawFestivalData:
    """Raw festival data from external sources."""

    source: str
    name: str
    dates: List[datetime]
    location: str
    venue: Optional[str] = None
    artists: Optional[List[str]] = None
    genres: Optional[List[str]] = None
    ticket_url: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class FestivalDataSource(ABC):
    """Abstract base class for festival data sources."""

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        self.logger = logging.getLogger(f"{__name__}.{source_name}")

    @abstractmethod
    async def fetch_festivals(self) -> List[RawFestivalData]:
        """Fetch festival data from the source."""
        pass

    @abstractmethod
    def validate_data(self, raw_data: Dict[str, Any]) -> bool:
        """Validate raw festival data."""
        pass

    def normalize_artist_name(self, artist_name: str) -> str:
        """Normalize artist names for consistency."""
        if not artist_name:
            return ""

        # Remove extra whitespace and convert to title case
        normalized = re.sub(r"\s+", " ", artist_name.strip())

        # Handle common variations
        normalized = re.sub(r"\bfeat\.\s*", "feat. ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bft\.\s*", "feat. ", normalized, flags=re.IGNORECASE)

        return normalized

    def normalize_location(self, location: str) -> str:
        """Normalize location strings."""
        if not location:
            return ""

        # Remove extra whitespace and standardize format
        normalized = re.sub(r"\s+", " ", location.strip())

        # Standardize common abbreviations
        normalized = re.sub(r"\bSt\.\s*", "Street ", normalized)
        normalized = re.sub(r"\bAve\.\s*", "Avenue ", normalized)
        normalized = re.sub(r"\bDr\.\s*", "Drive ", normalized)

        return normalized


class ClashfinderAPIClient:
    """Client for interacting with the Clashfinder API with proper authentication."""

    def __init__(self, username: str, private_key: str) -> None:
        self.username = username
        self.private_key = private_key
        self.base_url = "https://clashfinder.com"
        self.logger = logging.getLogger(f"{__name__}.ClashfinderAPIClient")
        self.session: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "ClashfinderAPIClient":
        """Async context manager entry."""
        self.session = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self.session:
            await self.session.aclose()

    def _generate_public_key(
        self, auth_param: str = "", auth_valid_until: str = ""
    ) -> str:
        """Generate SHA256 public key for Clashfinder API authentication."""
        import hashlib

        # Build the hash input string according to Clashfinder spec
        hash_input = self.username + self.private_key

        if auth_param:
            hash_input += auth_param

        if auth_valid_until:
            hash_input += auth_valid_until

        # Generate SHA256 hash
        public_key = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        self.logger.debug(f"Generated public key for user: {self.username}")
        return public_key

    def _build_auth_params(
        self,
        additional_params: Optional[Dict[str, str]] = None,
        auth_param: str = "",
        auth_valid_until: str = "",
    ) -> Dict[str, str]:
        """Build authentication parameters for API requests."""
        params = {
            "authUsername": self.username,
            "authPublicKey": self._generate_public_key(auth_param, auth_valid_until),
        }

        if auth_param:
            params["authParam"] = auth_param

        if auth_valid_until:
            params["authValidUntil"] = auth_valid_until

        if additional_params:
            params.update(additional_params)

        return params

    async def fetch_clashfinder_data(
        self, clashfinder_id: str, format_type: str = "json"
    ) -> Optional[Dict[str, Any]]:
        """Fetch data for a specific clashfinder using the correct endpoint format."""
        if not self.username or not self.private_key:
            self.logger.warning("Clashfinder credentials not provided")
            return None

        try:
            # Build the API endpoint URL using the correct format
            api_url = f"{self.base_url}/data/event/{clashfinder_id}.{format_type}"

            # Build authentication parameters
            params = self._build_auth_params()

            self.logger.debug(f"Fetching Clashfinder data for ID: {clashfinder_id}")
            self.logger.debug(f"API URL: {api_url}")

            if self.session is None:
                raise RuntimeError(
                    "Session not initialized. Use async context manager."
                )

            response = await self.session.get(api_url, params=params)

            if response.status_code == 200:
                if format_type.lower() == "json":
                    return response.json()  # type: ignore[no-any-return]
                else:
                    return {"raw_data": response.text}
            elif response.status_code == 401:
                self.logger.error(
                    "Clashfinder API authentication failed - check username and private key"
                )
                return None
            elif response.status_code == 403:
                self.logger.error(
                    "Clashfinder API access forbidden - check permissions"
                )
                return None
            elif response.status_code == 404:
                self.logger.warning(f"Clashfinder not found: {clashfinder_id}")
                return None
            elif response.status_code == 429:
                self.logger.warning("Clashfinder API rate limit exceeded")
                return None
            else:
                self.logger.error(
                    f"Clashfinder API error: {response.status_code} - {response.text}"
                )
                return None

        except httpx.TimeoutException:
            self.logger.error(
                f"Timeout fetching Clashfinder data for: {clashfinder_id}"
            )
            return None
        except Exception as e:
            self.logger.error(f"Error fetching Clashfinder data: {e}")
            return None

    async def search_clashfinders(self, search_term: str = "") -> List[Dict[str, Any]]:
        """Search for clashfinders. Note: This may require a different endpoint."""
        # Note: The actual Clashfinder API may not have a search endpoint
        # This is a placeholder for potential future functionality
        # For now, we'll need to work with known clashfinder IDs

        self.logger.warning(
            "Clashfinder search functionality not yet implemented - API may not support search"
        )
        return []

    def normalize_artist_name_for_setlistfm(self, artist_name: str) -> str:
        """Normalize artist names for compatibility with Setlist.fm."""
        if not artist_name:
            return ""

        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", artist_name.strip())

        # Handle common variations that might cause issues with Setlist.fm
        # Remove featuring/feat variations that might not match
        normalized = re.sub(
            r"\s+(?:feat\.|featuring|ft\.|with)\s+.*$",
            "",
            normalized,
            flags=re.IGNORECASE,
        )

        # Remove common suffixes that might not be in Setlist.fm
        suffixes_to_remove = [
            r"\s+\(live\)$",
            r"\s+\(acoustic\)$",
            r"\s+\(dj set\)$",
            r"\s+dj set$",
            r"\s+live$",
        ]

        for suffix in suffixes_to_remove:
            normalized = re.sub(suffix, "", normalized, flags=re.IGNORECASE)

        # Handle special characters that might cause issues
        # Replace common Unicode characters with ASCII equivalents
        char_replacements = {
            "é": "e",
            "è": "e",
            "ê": "e",
            "ë": "e",
            "á": "a",
            "à": "a",
            "â": "a",
            "ä": "a",
            "ã": "a",
            "í": "i",
            "ì": "i",
            "î": "i",
            "ï": "i",
            "ó": "o",
            "ò": "o",
            "ô": "o",
            "ö": "o",
            "õ": "o",
            "ú": "u",
            "ù": "u",
            "û": "u",
            "ü": "u",
            "ñ": "n",
            "ç": "c",
        }

        for unicode_char, ascii_char in char_replacements.items():
            normalized = normalized.replace(unicode_char, ascii_char)
            normalized = normalized.replace(unicode_char.upper(), ascii_char.upper())

        # Remove or replace special punctuation
        normalized = re.sub(r"[" "`]", "'", normalized)  # Normalize apostrophes
        normalized = re.sub(r'["""]', '"', normalized)  # Normalize quotes

        return normalized.strip()


class ClashfinderSource(FestivalDataSource):
    """Clashfinder API festival data source with proper authentication."""

    def __init__(
        self, username: str, private_key: str, source_name: str = "clashfinder"
    ) -> None:
        super().__init__(source_name)
        self.username = username
        self.private_key = private_key
        self.client: Optional[ClashfinderAPIClient] = None

        # Known clashfinder IDs for major festivals (these would need to be updated regularly)
        # Starting with the test endpoint and some common festival patterns
        self.known_festival_ids = [
            "test",  # Test endpoint provided by Clashfinder
            # Common festival ID patterns - these would need to be discovered/maintained
            "coachella2024",
            "coachella2025",
            "glastonbury2024",
            "glastonbury2025",
            "lollapalooza2024",
            "lollapalooza2025",
            "bonnaroo2024",
            "bonnaroo2025",
            "outsidelands2024",
            "outsidelands2025",
            "aclfest2024",
            "aclfest2025",
            "sxsw2024",
            "sxsw2025",
            "edc2024",
            "edc2025",
            "ultra2024",
            "ultra2025",
        ]

    async def fetch_festivals(self) -> List[RawFestivalData]:
        """Fetch festivals from Clashfinder API."""
        if not self.username or not self.private_key:
            self.logger.warning("Clashfinder credentials not provided, skipping")
            return []

        self.logger.info("Fetching festivals from Clashfinder API")
        festivals = []

        try:
            async with ClashfinderAPIClient(self.username, self.private_key) as client:
                self.client = client

                # Fetch data for known festival IDs
                for festival_id in self.known_festival_ids:
                    try:
                        festival_data = await client.fetch_clashfinder_data(festival_id)
                        if festival_data:
                            parsed_festival = await self._parse_clashfinder_data(
                                festival_data, client
                            )
                            if parsed_festival:
                                festivals.append(parsed_festival)
                    except Exception as e:
                        self.logger.error(
                            f"Error processing festival ID '{festival_id}': {e}"
                        )
                        continue

        except Exception as e:
            self.logger.error(f"Error fetching from Clashfinder API: {e}")

        self.logger.info(f"Fetched {len(festivals)} festivals from Clashfinder")
        return festivals

    async def _parse_clashfinder_data(
        self, data: Dict[str, Any], client: ClashfinderAPIClient
    ) -> Optional[RawFestivalData]:
        """Parse Clashfinder API response into RawFestivalData."""
        try:
            # Extract basic festival information
            # Note: The actual structure depends on Clashfinder's JSON format
            name = data.get("name") or data.get("title") or data.get("festival_name")
            if not name:
                # Try to extract from other fields
                name = data.get("event_name") or "Unknown Festival"

            # Extract dates
            dates = []
            date_fields = ["start_date", "date", "event_date", "dates"]

            for field in date_fields:
                if field in data:
                    date_value = data[field]
                    if isinstance(date_value, list):
                        for date_str in date_value:
                            parsed_date = self._parse_date(str(date_str))
                            if parsed_date:
                                dates.append(parsed_date)
                    else:
                        parsed_date = self._parse_date(str(date_value))
                        if parsed_date:
                            dates.append(parsed_date)
                    break

            if not dates:
                self.logger.warning(f"No valid dates found for festival: {name}")
                # Use current year as fallback
                from datetime import datetime

                dates = [datetime.now()]

            # Extract location
            location = (
                data.get("location")
                or data.get("venue")
                or data.get("city")
                or data.get("place")
                or "Unknown Location"
            )

            # Extract venue
            venue = data.get("venue_name") or data.get("venue")

            # Extract artists from lineup
            artists = []

            # Try different possible lineup structures
            lineup_fields = ["lineup", "artists", "performers", "acts"]
            for field in lineup_fields:
                if field in data:
                    lineup_data = data[field]
                    artists = self._extract_artists_from_lineup(lineup_data, client)
                    if artists:
                        break

            # If no artists found, try to extract from stages or days
            if not artists:
                stages_data = data.get("stages") or data.get("days") or {}
                if isinstance(stages_data, dict):
                    for stage_name, stage_data in stages_data.items():
                        if isinstance(stage_data, list):
                            stage_artists = self._extract_artists_from_lineup(
                                stage_data, client
                            )
                            artists.extend(stage_artists)
                        elif isinstance(stage_data, dict) and "artists" in stage_data:
                            stage_artists = self._extract_artists_from_lineup(
                                stage_data["artists"], client
                            )
                            artists.extend(stage_artists)

            # Remove duplicates while preserving order
            unique_artists = []
            seen = set()
            for artist in artists:
                if artist.lower() not in seen:
                    seen.add(artist.lower())
                    unique_artists.append(artist)

            # Extract genres
            genres = data.get("genres") or data.get("genre") or []
            if isinstance(genres, str):
                genres = [genres]

            # Extract ticket URL
            ticket_url = (
                data.get("ticket_url")
                or data.get("tickets")
                or data.get("url")
                or data.get("website")
            )

            return RawFestivalData(
                source=self.source_name,
                name=name,
                dates=dates,
                location=location,
                venue=venue,
                artists=unique_artists,
                genres=genres,
                ticket_url=ticket_url,
                raw_data=data,
            )

        except Exception as e:
            self.logger.error(f"Error parsing Clashfinder data: {e}")
            return None

    def _extract_artists_from_lineup(
        self, lineup_data: Any, client: ClashfinderAPIClient
    ) -> List[str]:
        """Extract and normalize artist names from lineup data."""
        artists = []

        if isinstance(lineup_data, list):
            for item in lineup_data:
                if isinstance(item, str):
                    normalized_artist = client.normalize_artist_name_for_setlistfm(item)
                    if normalized_artist:
                        artists.append(normalized_artist)
                elif isinstance(item, dict):
                    # Try different possible name fields
                    name_fields = ["name", "artist", "performer", "act", "title"]
                    for field in name_fields:
                        if field in item:
                            artist_name = item[field]
                            if artist_name:
                                normalized_artist = (
                                    client.normalize_artist_name_for_setlistfm(
                                        str(artist_name)
                                    )
                                )
                                if normalized_artist:
                                    artists.append(normalized_artist)
                                break
        elif isinstance(lineup_data, dict):
            # Handle case where lineup_data is a dict with artist info
            name_fields = ["name", "artist", "performer", "act", "title"]
            for field in name_fields:
                if field in lineup_data:
                    artist_name = lineup_data[field]
                    if artist_name:
                        normalized_artist = client.normalize_artist_name_for_setlistfm(
                            str(artist_name)
                        )
                        if normalized_artist:
                            artists.append(normalized_artist)
                        break

        return artists

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string from Clashfinder API."""
        if not date_str:
            return None

        # Clean the date string
        date_str = date_str.strip()

        # Try different date formats that Clashfinder might use
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%Y%m%d",
            "%d %B %Y",
            "%B %d, %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Try parsing with dateutil if available
        try:
            from dateutil import parser

            return parser.parse(date_str)
        except:
            pass

        self.logger.debug(f"Could not parse Clashfinder date: {date_str}")
        return None

    def validate_data(self, raw_data: Dict[str, Any]) -> bool:
        """Validate Clashfinder festival data."""
        required_fields = ["name", "dates", "location"]
        return all(field in raw_data and raw_data[field] for field in required_fields)


class WebScrapingSource(FestivalDataSource):
    """Web scraping festival data source."""

    def __init__(self, base_url: str, source_name: str = "web_scraping") -> None:
        super().__init__(source_name)
        self.base_url = base_url

    async def fetch_festivals(self) -> List[RawFestivalData]:
        """Fetch festivals via web scraping."""
        self.logger.info(f"Fetching festivals from {self.base_url}")

        try:
            import re
            from datetime import datetime, timedelta

            import httpx

            festivals = []

            # Example implementation for common festival listing sites
            if "songkick.com" in self.base_url.lower():
                festivals.extend(await self._scrape_songkick())
            elif "bandsintown.com" in self.base_url.lower():
                festivals.extend(await self._scrape_bandsintown())
            elif "festicket.com" in self.base_url.lower():
                festivals.extend(await self._scrape_festicket())
            else:
                # Generic scraping approach
                festivals.extend(await self._scrape_generic())

            self.logger.info(f"Scraped {len(festivals)} festivals from {self.base_url}")
            return festivals

        except Exception as e:
            self.logger.error(f"Error scraping festivals from {self.base_url}: {e}")
            return []

    async def _scrape_songkick(self) -> List[RawFestivalData]:
        """Scrape festivals from Songkick."""
        festivals = []
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, timeout=30.0)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Look for festival events
                    events = soup.find_all("div", class_="event-listings-element")

                    for event in events:
                        try:
                            # Extract festival name
                            name_elem = event.find("strong") or event.find("h3")
                            if not name_elem:
                                continue
                            name = name_elem.get_text(strip=True)

                            # Skip if not a festival
                            if not any(
                                keyword in name.lower()
                                for keyword in ["festival", "fest", "music"]
                            ):
                                continue

                            # Extract location
                            location_elem = event.find("span", class_="location")
                            location = (
                                location_elem.get_text(strip=True)
                                if location_elem
                                else ""
                            )

                            # Extract date
                            date_elem = event.find("time") or event.find(
                                "span", class_="date"
                            )
                            if date_elem:
                                date_str_raw = date_elem.get(
                                    "datetime"
                                ) or date_elem.get_text(strip=True)
                                # Ensure we have a string
                                date_str = str(date_str_raw) if date_str_raw else ""
                                try:
                                    date = datetime.fromisoformat(
                                        date_str.replace("Z", "+00:00")
                                    )
                                except:
                                    # Try parsing common date formats
                                    parsed_date = self._parse_date_string(date_str)
                                    if parsed_date is None:
                                        continue
                                    date = parsed_date
                            else:
                                continue

                            # Extract artists (if available)
                            artists = []
                            artist_elems = event.find_all(
                                "a", href=re.compile(r"/artists/")
                            )
                            for artist_elem in artist_elems:
                                artist_name = artist_elem.get_text(strip=True)
                                if artist_name:
                                    artists.append(artist_name)

                            if name and location and date is not None:
                                festivals.append(
                                    RawFestivalData(
                                        source=self.source_name,
                                        name=name,
                                        dates=[date],
                                        location=location,
                                        artists=artists,
                                    )
                                )
                        except Exception as e:
                            self.logger.debug(f"Error parsing event: {e}")
                            continue
        except Exception as e:
            self.logger.error(f"Error scraping Songkick: {e}")

        return festivals

    async def _scrape_bandsintown(self) -> List[RawFestivalData]:
        """Scrape festivals from Bandsintown."""
        festivals = []
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, timeout=30.0)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Look for event cards
                    events = soup.find_all("div", class_="eventCard") or soup.find_all(
                        "article", class_="event"
                    )

                    for event in events:
                        try:
                            # Extract festival name
                            name_elem = (
                                event.find("h2")
                                or event.find("h3")
                                or event.find("a", class_="event-name")
                            )
                            if not name_elem:
                                continue
                            name = name_elem.get_text(strip=True)

                            # Skip if not a festival
                            if not any(
                                keyword in name.lower()
                                for keyword in ["festival", "fest", "music"]
                            ):
                                continue

                            # Extract location
                            location_elem = event.find(
                                "span", class_="venue-name"
                            ) or event.find("div", class_="location")
                            location = (
                                location_elem.get_text(strip=True)
                                if location_elem
                                else ""
                            )

                            # Extract date
                            date_elem = event.find("time") or event.find(
                                "span", class_="date"
                            )
                            if date_elem:
                                date_str_raw = date_elem.get(
                                    "datetime"
                                ) or date_elem.get_text(strip=True)
                                date_str = str(date_str_raw) if date_str_raw else ""
                                date = self._parse_date_string(date_str)
                            else:
                                continue

                            if name and location and date:
                                festivals.append(
                                    RawFestivalData(
                                        source=self.source_name,
                                        name=name,
                                        dates=[date],
                                        location=location,
                                        artists=[],
                                    )
                                )
                        except Exception as e:
                            self.logger.debug(f"Error parsing event: {e}")
                            continue
        except Exception as e:
            self.logger.error(f"Error scraping Bandsintown: {e}")

        return festivals

    async def _scrape_festicket(self) -> List[RawFestivalData]:
        """Scrape festivals from Festicket."""
        festivals = []
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, timeout=30.0)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Look for festival cards
                    events = soup.find_all(
                        "div", class_="festival-card"
                    ) or soup.find_all("article", class_="festival")

                    for event in events:
                        try:
                            # Extract festival name
                            name_elem = (
                                event.find("h2")
                                or event.find("h3")
                                or event.find("a", class_="festival-name")
                            )
                            if not name_elem:
                                continue
                            name = name_elem.get_text(strip=True)

                            # Extract location
                            location_elem = event.find(
                                "span", class_="location"
                            ) or event.find("div", class_="venue")
                            location = (
                                location_elem.get_text(strip=True)
                                if location_elem
                                else ""
                            )

                            # Extract date
                            date_elem = event.find("time") or event.find(
                                "span", class_="date"
                            )
                            if date_elem:
                                date_str_raw = date_elem.get(
                                    "datetime"
                                ) or date_elem.get_text(strip=True)
                                date_str = str(date_str_raw) if date_str_raw else ""
                                date = self._parse_date_string(date_str)
                            else:
                                continue

                            # Extract artists from lineup
                            artists = []
                            lineup_elem = event.find(
                                "div", class_="lineup"
                            ) or event.find("ul", class_="artists")
                            if lineup_elem:
                                artist_elems = lineup_elem.find_all(
                                    "a"
                                ) or lineup_elem.find_all("li")
                                for artist_elem in artist_elems:
                                    artist_name = artist_elem.get_text(strip=True)
                                    if artist_name and len(artist_name) > 1:
                                        artists.append(artist_name)

                            if name and location and date:
                                festivals.append(
                                    RawFestivalData(
                                        source=self.source_name,
                                        name=name,
                                        dates=[date],
                                        location=location,
                                        artists=artists,
                                    )
                                )
                        except Exception as e:
                            self.logger.debug(f"Error parsing event: {e}")
                            continue
        except Exception as e:
            self.logger.error(f"Error scraping Festicket: {e}")

        return festivals

    async def _scrape_generic(self) -> List[RawFestivalData]:
        """Generic scraping approach for unknown sites."""
        festivals = []
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, timeout=30.0)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Look for common festival-related elements
                    potential_events: List[Any] = []

                    # Try different selectors
                    selectors = [
                        'div[class*="event"]',
                        'div[class*="festival"]',
                        'article[class*="event"]',
                        'article[class*="festival"]',
                        ".event-card",
                        ".festival-card",
                        ".event-item",
                        ".festival-item",
                    ]

                    for selector in selectors:
                        elements = soup.select(selector)
                        potential_events.extend(elements)

                    for event in potential_events:
                        try:
                            # Extract text content
                            text = event.get_text(strip=True)

                            # Skip if doesn't contain festival keywords
                            if not any(
                                keyword in text.lower()
                                for keyword in ["festival", "fest", "music"]
                            ):
                                continue

                            # Try to extract name (usually in headings or strong tags)
                            name_elem = event.find(
                                ["h1", "h2", "h3", "h4", "strong", "b"]
                            )
                            if not name_elem:
                                continue
                            name = name_elem.get_text(strip=True)

                            # Try to extract location
                            location = ""
                            location_patterns = [
                                r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2,})",  # City, State/Country
                                r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # Just city
                            ]
                            for pattern in location_patterns:
                                match = re.search(pattern, text)
                                if match:
                                    location = match.group(1)
                                    break

                            # Try to extract date
                            date = None
                            date_elem = event.find("time")
                            if date_elem:
                                date_str = date_elem.get(
                                    "datetime"
                                ) or date_elem.get_text(strip=True)
                                date = self._parse_date_string(date_str)
                            else:
                                # Look for date patterns in text
                                date_patterns = [
                                    r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
                                    r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
                                    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})",
                                ]
                                for pattern in date_patterns:
                                    match = re.search(pattern, text, re.IGNORECASE)
                                    if match:
                                        date = self._parse_date_string(match.group(1))
                                        break

                            if name and date:
                                festivals.append(
                                    RawFestivalData(
                                        source=self.source_name,
                                        name=name,
                                        dates=[date],
                                        location=location or "Unknown Location",
                                        artists=[],
                                    )
                                )
                        except Exception as e:
                            self.logger.debug(f"Error parsing generic event: {e}")
                            continue
        except Exception as e:
            self.logger.error(f"Error in generic scraping: {e}")

        return festivals

    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse various date string formats."""
        if not date_str:
            return None

        # Clean the date string
        date_str = date_str.strip()

        # Try different date formats
        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Try parsing with dateutil if available
        try:
            from dateutil import parser

            return parser.parse(date_str)
        except:
            pass

        self.logger.debug(f"Could not parse date: {date_str}")
        return None

    def validate_data(self, raw_data: Dict[str, Any]) -> bool:
        """Validate scraped festival data."""
        required_fields = ["name", "dates", "location"]
        return all(field in raw_data and raw_data[field] for field in required_fields)


class APISource(FestivalDataSource):
    """API-based festival data source."""

    def __init__(
        self, api_url: str, api_key: Optional[str] = None, source_name: str = "api"
    ) -> None:
        super().__init__(source_name)
        self.api_url = api_url
        self.api_key = api_key

    async def fetch_festivals(self) -> List[RawFestivalData]:
        """Fetch festivals from API."""
        self.logger.info(f"Fetching festivals from API: {self.api_url}")

        try:
            from datetime import datetime

            import httpx

            festivals = []

            # Handle different API types
            if "musicbrainz" in self.api_url.lower():
                festivals.extend(await self._fetch_from_musicbrainz())
            elif "last.fm" in self.api_url.lower():
                festivals.extend(await self._fetch_from_lastfm())
            elif "spotify" in self.api_url.lower():
                festivals.extend(await self._fetch_from_spotify())
            else:
                # Generic API approach
                festivals.extend(await self._fetch_generic_api())

            self.logger.info(f"Fetched {len(festivals)} festivals from API")
            return festivals

        except Exception as e:
            self.logger.error(f"Error fetching festivals from API {self.api_url}: {e}")
            return []

    async def _fetch_from_musicbrainz(self) -> List[RawFestivalData]:
        """Fetch festival data from MusicBrainz API."""
        festivals = []
        try:
            async with httpx.AsyncClient() as client:
                # Search for events with festival in the name
                params: Dict[str, str | int] = {
                    "query": "type:festival",
                    "limit": 50,
                    "fmt": "json",
                }

                response = await client.get(
                    f"{self.api_url}/ws/2/event",
                    params=params,
                    headers={"User-Agent": "FestivalPlaylistGenerator/1.0"},
                )

                if response.status_code == 200:
                    data = response.json()
                    events = data.get("events", [])

                    for event in events:
                        try:
                            name = event.get("name", "")
                            if not name:
                                continue

                            # Extract dates
                            dates = []
                            life_span = event.get("life-span", {})
                            if life_span.get("begin"):
                                try:
                                    begin_date = datetime.fromisoformat(
                                        life_span["begin"]
                                    )
                                    dates.append(begin_date)
                                except:
                                    pass

                            # Extract location
                            location = ""
                            relations = event.get("relations", [])
                            for relation in relations:
                                if relation.get("type") == "held at":
                                    place = relation.get("place", {})
                                    if place.get("name"):
                                        location = place["name"]
                                        area = place.get("area", {})
                                        if area.get("name"):
                                            location += f", {area['name']}"
                                    break

                            if dates and location:
                                festivals.append(
                                    RawFestivalData(
                                        source=self.source_name,
                                        name=name,
                                        dates=dates,
                                        location=location,
                                        artists=[],
                                    )
                                )
                        except Exception as e:
                            self.logger.debug(f"Error parsing MusicBrainz event: {e}")
                            continue
        except Exception as e:
            self.logger.error(f"Error fetching from MusicBrainz: {e}")

        return festivals

    async def _fetch_from_lastfm(self) -> List[RawFestivalData]:
        """Fetch festival data from Last.fm API."""
        festivals: List[RawFestivalData] = []
        try:
            if not self.api_key:
                self.logger.warning("Last.fm API key not provided")
                return festivals

            async with httpx.AsyncClient() as client:
                # Search for festival events
                params: Dict[str, str | int] = {
                    "method": "geo.getevents",
                    "api_key": self.api_key,
                    "format": "json",
                    "limit": 50,
                }

                response = await client.get(self.api_url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    events = data.get("events", {}).get("event", [])

                    if isinstance(events, dict):
                        events = [events]

                    for event in events:
                        try:
                            title = event.get("title", "")
                            if not any(
                                keyword in title.lower()
                                for keyword in ["festival", "fest"]
                            ):
                                continue

                            # Extract date
                            start_date = event.get("startDate")
                            if start_date:
                                try:
                                    date = datetime.strptime(
                                        start_date, "%a, %d %b %Y %H:%M:%S"
                                    )
                                except:
                                    continue
                            else:
                                continue

                            # Extract location
                            venue = event.get("venue", {})
                            location = venue.get("name", "")
                            if venue.get("location", {}).get("city"):
                                city = venue["location"]["city"]
                                country = venue["location"].get("country", "")
                                location = f"{location}, {city}, {country}".strip(", ")

                            # Extract artists
                            artists = []
                            artist_data = event.get("artists", {}).get("artist", [])
                            if isinstance(artist_data, dict):
                                artist_data = [artist_data]

                            for artist in artist_data:
                                if isinstance(artist, str):
                                    artists.append(artist)
                                elif isinstance(artist, dict):
                                    artists.append(artist.get("name", ""))

                            if title and location and date:
                                festivals.append(
                                    RawFestivalData(
                                        source=self.source_name,
                                        name=title,
                                        dates=[date],
                                        location=location,
                                        artists=artists,
                                    )
                                )
                        except Exception as e:
                            self.logger.debug(f"Error parsing Last.fm event: {e}")
                            continue
        except Exception as e:
            self.logger.error(f"Error fetching from Last.fm: {e}")

        return festivals

    async def _fetch_from_spotify(self) -> List[RawFestivalData]:
        """Fetch festival data from Spotify API (limited festival info available)."""
        festivals: List[RawFestivalData] = []
        try:
            if not self.api_key:
                self.logger.warning("Spotify API credentials not provided")
                return festivals

            # Spotify doesn't have direct festival endpoints, but we can search for festival playlists
            # This is a limited approach but can provide some festival information
            async with httpx.AsyncClient() as client:
                # Get access token first
                auth_response = await client.post(
                    "https://accounts.spotify.com/api/token",
                    data={"grant_type": "client_credentials"},
                    headers={"Authorization": f"Basic {self.api_key}"},
                )

                if auth_response.status_code == 200:
                    token_data = auth_response.json()
                    access_token = token_data["access_token"]

                    # Search for festival playlists
                    search_params: Dict[str, str | int] = {
                        "q": "festival 2024 2025",
                        "type": "playlist",
                        "limit": 50,
                    }

                    search_response = await client.get(
                        "https://api.spotify.com/v1/search",
                        params=search_params,
                        headers={"Authorization": f"Bearer {access_token}"},
                    )

                    if search_response.status_code == 200:
                        search_data = search_response.json()
                        playlists = search_data.get("playlists", {}).get("items", [])

                        for playlist in playlists:
                            try:
                                name = playlist.get("name", "")
                                description = playlist.get("description", "")

                                # Extract festival info from playlist name/description
                                if any(
                                    keyword in name.lower()
                                    for keyword in ["festival", "fest"]
                                ):
                                    # This is a very basic extraction - would need more sophisticated parsing
                                    location = "Unknown Location"  # Spotify doesn't provide location info
                                    date = (
                                        datetime.now()
                                    )  # Would need to parse from name/description

                                    festivals.append(
                                        RawFestivalData(
                                            source=self.source_name,
                                            name=name,
                                            dates=[date],
                                            location=location,
                                            artists=[],
                                        )
                                    )
                            except Exception as e:
                                self.logger.debug(
                                    f"Error parsing Spotify playlist: {e}"
                                )
                                continue
        except Exception as e:
            self.logger.error(f"Error fetching from Spotify: {e}")

        return festivals

    async def _fetch_generic_api(self) -> List[RawFestivalData]:
        """Generic API fetching approach."""
        festivals = []
        try:
            async with httpx.AsyncClient() as client:
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                response = await client.get(self.api_url, headers=headers, timeout=30.0)

                if response.status_code == 200:
                    data = response.json()

                    # Try to find events/festivals in the response
                    events = []
                    if isinstance(data, list):
                        events = data
                    elif isinstance(data, dict):
                        # Try common keys
                        for key in ["events", "festivals", "data", "results", "items"]:
                            if key in data:
                                events = data[key]
                                break

                    for event in events:
                        try:
                            if not isinstance(event, dict):
                                continue

                            # Extract name
                            name = (
                                event.get("name")
                                or event.get("title")
                                or event.get("event_name")
                            )
                            if not name:
                                continue

                            # Extract date
                            date_str = (
                                event.get("date")
                                or event.get("start_date")
                                or event.get("event_date")
                            )
                            if date_str:
                                try:
                                    if isinstance(date_str, str):
                                        date = datetime.fromisoformat(
                                            date_str.replace("Z", "+00:00")
                                        )
                                    else:
                                        date = datetime.now()
                                except:
                                    date = datetime.now()
                            else:
                                continue

                            # Extract location
                            location = (
                                event.get("location")
                                or event.get("venue")
                                or event.get("city")
                                or "Unknown Location"
                            )

                            # Extract artists
                            artists = []
                            artist_data = (
                                event.get("artists")
                                or event.get("lineup")
                                or event.get("performers")
                                or []
                            )
                            if isinstance(artist_data, list):
                                for artist in artist_data:
                                    if isinstance(artist, str):
                                        artists.append(artist)
                                    elif isinstance(artist, dict):
                                        artist_name = artist.get("name") or artist.get(
                                            "artist_name"
                                        )
                                        if artist_name:
                                            artists.append(artist_name)

                            festivals.append(
                                RawFestivalData(
                                    source=self.source_name,
                                    name=name,
                                    dates=[date],
                                    location=location,
                                    artists=artists,
                                )
                            )
                        except Exception as e:
                            self.logger.debug(f"Error parsing generic API event: {e}")
                            continue
        except Exception as e:
            self.logger.error(f"Error in generic API fetching: {e}")

        return festivals

    def validate_data(self, raw_data: Dict[str, Any]) -> bool:
        """Validate API festival data."""
        required_fields = ["name", "dates", "location"]
        return all(field in raw_data and raw_data[field] for field in required_fields)


class FestivalParser:
    """Parses and validates raw festival data."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"{__name__}.FestivalParser")

    def parse_festival_data(
        self, raw_data: RawFestivalData
    ) -> Optional[FestivalCreate]:
        """Parse raw festival data into a validated FestivalCreate object."""
        try:
            # Validate required fields
            if not self._validate_required_fields(raw_data):
                self.logger.warning(
                    f"Missing required fields in festival data: {raw_data.name}"
                )
                return None

            # Parse and validate dates
            parsed_dates = self._parse_dates(raw_data.dates)
            if not parsed_dates:
                self.logger.warning(f"Invalid dates for festival: {raw_data.name}")
                return None

            # Create FestivalCreate object
            festival_data = FestivalCreate(
                name=self._clean_name(raw_data.name),
                dates=parsed_dates,
                location=self._clean_location(raw_data.location),
                venue=self._clean_venue(raw_data.venue),
                artists=self._clean_artists(raw_data.artists or []),
                genres=self._clean_genres(raw_data.genres or []),
                ticket_url=self._clean_url(raw_data.ticket_url),
                logo_url=None,
                primary_color=None,
                secondary_color=None,
                accent_colors=None,
                branding_extracted_at=None,
                artist_images=None,
            )

            return festival_data

        except Exception as e:
            self.logger.error(f"Error parsing festival data for {raw_data.name}: {e}")
            return None

    def _validate_required_fields(self, raw_data: RawFestivalData) -> bool:
        """Validate that required fields are present and non-empty."""
        if not raw_data.name or not raw_data.name.strip():
            return False
        if not raw_data.dates or len(raw_data.dates) == 0:
            return False
        if not raw_data.location or not raw_data.location.strip():
            return False
        return True

    def _parse_dates(self, dates: List[Any]) -> List[datetime]:
        """Parse and validate festival dates."""
        if not dates:
            return []

        valid_dates = []
        for date in dates:
            if isinstance(date, datetime):
                valid_dates.append(date)
            else:
                self.logger.warning(f"Invalid date format: {date}")

        # Sort dates chronologically
        return sorted(valid_dates)

    def _clean_name(self, name: str) -> str:
        """Clean and normalize festival name."""
        if not name:
            return ""

        # Remove extra whitespace and normalize
        cleaned = re.sub(r"\s+", " ", name.strip())

        # Remove common suffixes that might cause duplicates
        cleaned = re.sub(
            r"\s+(Festival|Fest|Music Festival)$", "", cleaned, flags=re.IGNORECASE
        )

        return cleaned

    def _clean_location(self, location: str) -> str:
        """Clean and normalize location."""
        if not location:
            return ""

        return re.sub(r"\s+", " ", location.strip())

    def _clean_venue(self, venue: Optional[str]) -> Optional[str]:
        """Clean venue name."""
        if not venue:
            return None

        cleaned = re.sub(r"\s+", " ", venue.strip())
        return cleaned if cleaned else None

    def _clean_artists(self, artists: List[str]) -> List[str]:
        """Clean and normalize artist names."""
        cleaned_artists = []
        for artist in artists:
            if artist and artist.strip():
                # Normalize artist name
                normalized = re.sub(r"\s+", " ", artist.strip())
                cleaned_artists.append(normalized)

        # Remove duplicates while preserving order
        seen = set()
        unique_artists = []
        for artist in cleaned_artists:
            if artist.lower() not in seen:
                seen.add(artist.lower())
                unique_artists.append(artist)

        return unique_artists

    def _clean_genres(self, genres: List[str]) -> List[str]:
        """Clean and normalize genre names."""
        cleaned_genres = []
        for genre in genres:
            if genre and genre.strip():
                # Normalize genre name
                normalized = re.sub(r"\s+", " ", genre.strip().title())
                cleaned_genres.append(normalized)

        # Remove duplicates
        return list(set(cleaned_genres))

    def _clean_url(self, url: Optional[str]) -> Optional[str]:
        """Clean and validate URL."""
        if not url:
            return None

        url = url.strip()
        if not url:
            return None

        # Basic URL validation
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url

        return url


class FestivalDeduplicator:
    """Handles festival deduplication logic."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"{__name__}.FestivalDeduplicator")

    def deduplicate_festivals(
        self, festivals: List[FestivalCreate]
    ) -> List[FestivalCreate]:
        """Deduplicate a list of festivals."""
        if not festivals:
            return []

        # Group festivals by similarity
        festival_groups = self._group_similar_festivals(festivals)

        # Merge each group into a single festival
        deduplicated = []
        for group in festival_groups:
            merged_festival = self._merge_festival_group(group)
            if merged_festival:
                deduplicated.append(merged_festival)

        self.logger.info(
            f"Deduplicated {len(festivals)} festivals to {len(deduplicated)}"
        )
        return deduplicated

    def _group_similar_festivals(
        self, festivals: List[FestivalCreate]
    ) -> List[List[FestivalCreate]]:
        """Group similar festivals together."""
        groups = []
        processed = set()

        for i, festival in enumerate(festivals):
            if i in processed:
                continue

            # Start a new group with this festival
            group = [festival]
            processed.add(i)

            # Find similar festivals
            for j, other_festival in enumerate(festivals[i + 1 :], i + 1):
                if j in processed:
                    continue

                if self._are_festivals_similar(festival, other_festival):
                    group.append(other_festival)
                    processed.add(j)

            groups.append(group)

        return groups

    def _are_festivals_similar(
        self, festival1: FestivalCreate, festival2: FestivalCreate
    ) -> bool:
        """Check if two festivals are similar enough to be considered duplicates."""
        # Check name similarity
        name_similarity = self._calculate_name_similarity(
            festival1.name, festival2.name
        )
        if name_similarity < 0.8:  # Names must be at least 80% similar
            return False

        # Check location similarity
        location_similarity = self._calculate_location_similarity(
            festival1.location, festival2.location
        )
        if location_similarity < 0.9:  # Locations must be at least 90% similar
            return False

        # Check date overlap
        if not self._have_overlapping_dates(festival1.dates, festival2.dates):
            return False

        return True

    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between festival names."""
        if not name1 or not name2:
            return 0.0

        # Normalize names for comparison
        norm1 = self._normalize_for_comparison(name1)
        norm2 = self._normalize_for_comparison(name2)

        if norm1 == norm2:
            return 1.0

        # Simple Jaccard similarity on words
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def _calculate_location_similarity(self, loc1: str, loc2: str) -> float:
        """Calculate similarity between locations."""
        if not loc1 or not loc2:
            return 0.0

        norm1 = self._normalize_for_comparison(loc1)
        norm2 = self._normalize_for_comparison(loc2)

        if norm1 == norm2:
            return 1.0

        # Check if one location contains the other
        if norm1 in norm2 or norm2 in norm1:
            return 0.9

        # Simple word-based similarity
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def _have_overlapping_dates(
        self, dates1: List[datetime], dates2: List[datetime]
    ) -> bool:
        """Check if two date ranges overlap."""
        if not dates1 or not dates2:
            return False

        # Convert to date ranges
        start1, end1 = min(dates1), max(dates1)
        start2, end2 = min(dates2), max(dates2)

        # Check for overlap (allowing for some tolerance)
        tolerance_days = 7  # 7 days tolerance

        return (
            abs((start1 - start2).days) <= tolerance_days
            or abs((end1 - end2).days) <= tolerance_days
            or (start1 <= end2 and end1 >= start2)
        )

    def _normalize_for_comparison(self, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""

        import unicodedata

        # First normalize Unicode characters (NFKD = compatibility decomposed form)
        # This handles more character variations than NFD
        normalized = unicodedata.normalize("NFKD", text)

        # Handle specific Unicode character mappings that NFKD doesn't catch
        char_mappings = {
            "µ": "u",  # Latin micro sign -> u
            "Μ": "u",  # Greek capital mu -> u (changed from M to u)
            "μ": "u",  # Greek small mu -> u
            "ß": "ss",  # German eszett -> ss
            "æ": "ae",  # Latin ae -> ae
            "Æ": "ae",  # Latin capital ae -> ae
            "œ": "oe",  # Latin oe -> oe
            "Œ": "oe",  # Latin capital oe -> oe
            "ø": "o",  # Latin o with stroke -> o
            "Ø": "o",  # Latin capital o with stroke -> o
            "ð": "d",  # Latin eth -> d
            "Ð": "d",  # Latin capital eth -> d
            "þ": "th",  # Latin thorn -> th
            "Þ": "th",  # Latin capital thorn -> th
        }

        for unicode_char, replacement in char_mappings.items():
            normalized = normalized.replace(unicode_char, replacement)

        # Remove diacritics and accents
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

        # Convert to lowercase and remove special characters
        normalized = re.sub(r"[^\w\s]", "", normalized.lower())

        # Remove common words that don't help with matching
        stop_words = {"the", "and", "or", "at", "in", "on", "festival", "fest", "music"}
        words = [word for word in normalized.split() if word not in stop_words]

        return " ".join(words)

    def _merge_festival_group(
        self, festivals: List[FestivalCreate]
    ) -> Optional[FestivalCreate]:
        """Merge a group of similar festivals into one."""
        if not festivals:
            return None

        if len(festivals) == 1:
            return festivals[0]

        # Use the first festival as base and merge others into it
        base_festival = festivals[0]

        # Merge dates (combine and deduplicate)
        all_dates = []
        for festival in festivals:
            all_dates.extend(festival.dates)
        unique_dates = sorted(list(set(all_dates)))

        # Merge artists (combine and deduplicate)
        all_artists = []
        for festival in festivals:
            all_artists.extend(festival.artists)
        unique_artists = self._deduplicate_list(all_artists)

        # Merge genres
        all_genres = []
        for festival in festivals:
            all_genres.extend(festival.genres)
        unique_genres = self._deduplicate_list(all_genres)

        # Choose best name (longest non-empty name)
        best_name = max(
            [f.name for f in festivals if f.name], key=len, default=base_festival.name
        )

        # Choose best location (most detailed)
        best_location = max(
            [f.location for f in festivals if f.location],
            key=len,
            default=base_festival.location,
        )

        # Choose best venue (first non-empty)
        best_venue = next((f.venue for f in festivals if f.venue), None)

        # Choose best ticket URL (first non-empty)
        best_ticket_url = next((f.ticket_url for f in festivals if f.ticket_url), None)

        return FestivalCreate(
            name=best_name,
            dates=unique_dates,
            location=best_location,
            venue=best_venue,
            artists=unique_artists,
            genres=unique_genres,
            ticket_url=best_ticket_url,
            logo_url=None,
            primary_color=None,
            secondary_color=None,
            accent_colors=None,
            branding_extracted_at=None,
            artist_images=None,
        )

    def _deduplicate_list(self, items: List[str]) -> List[str]:
        """Deduplicate a list while preserving order."""
        seen = set()
        result = []
        for item in items:
            if item and item.strip() and item.lower() not in seen:
                seen.add(item.lower())
                result.append(item)
        return result


class FestivalCollectorService:
    """Main service for collecting and processing festival data."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"{__name__}.FestivalCollectorService")
        self.parser = FestivalParser()
        self.deduplicator = FestivalDeduplicator()
        self.data_sources: List[FestivalDataSource] = []
        self.db: Optional[Any] = None  # Set by dependency injection
        self._initialize_data_sources()

    def _initialize_data_sources(self) -> None:
        """Initialize data sources with Clashfinder as primary and web scraping as fallback."""
        # Add Clashfinder API as primary source
        if settings.CLASHFINDER_USERNAME and settings.CLASHFINDER_PRIVATE_KEY:
            clashfinder_source = ClashfinderSource(
                settings.CLASHFINDER_USERNAME, settings.CLASHFINDER_PRIVATE_KEY
            )
            self.add_data_source(clashfinder_source)
            self.logger.info("Initialized Clashfinder API as primary data source")
        else:
            self.logger.warning(
                "Clashfinder credentials not found, skipping Clashfinder integration"
            )

        # Add web scraping sources as fallback
        fallback_sources = [
            "https://www.songkick.com/search?type=upcoming&query=festival",
            "https://www.bandsintown.com/events/search?query=festival",
            "https://www.festicket.com/festivals/",
        ]

        for url in fallback_sources:
            try:
                web_source = WebScrapingSource(
                    url, f"web_scraping_{url.split('//')[1].split('.')[1]}"
                )
                self.add_data_source(web_source)
            except Exception as e:
                self.logger.debug(
                    f"Could not initialize web scraping source for {url}: {e}"
                )

        self.logger.info(f"Initialized {len(self.data_sources)} data sources total")

    def add_data_source(self, source: FestivalDataSource) -> None:
        """Add a festival data source."""
        self.data_sources.append(source)
        self.logger.info(f"Added data source: {source.source_name}")

    async def collect_daily_festivals(self) -> List[Festival]:
        """Collect festival data from all sources with Clashfinder as primary."""
        self.logger.info("Starting daily festival collection")

        all_raw_data = []
        clashfinder_success = False

        # Try Clashfinder first (primary source)
        for source in self.data_sources:
            if isinstance(source, ClashfinderSource):
                try:
                    self.logger.info(
                        "Attempting to collect from Clashfinder API (primary source)"
                    )
                    raw_festivals = await source.fetch_festivals()
                    if raw_festivals:
                        all_raw_data.extend(raw_festivals)
                        clashfinder_success = True
                        self.logger.info(
                            f"Successfully collected {len(raw_festivals)} festivals from Clashfinder"
                        )
                    else:
                        self.logger.warning("Clashfinder API returned no festivals")
                except Exception as e:
                    self.logger.error(f"Error collecting from Clashfinder API: {e}")
                break

        # If Clashfinder failed or returned insufficient data, use fallback sources
        if (
            not clashfinder_success or len(all_raw_data) < 5
        ):  # Threshold for "insufficient data"
            self.logger.info("Using fallback web scraping sources")
            for source in self.data_sources:
                if not isinstance(source, ClashfinderSource):
                    try:
                        raw_festivals = await source.fetch_festivals()
                        all_raw_data.extend(raw_festivals)
                        self.logger.info(
                            f"Collected {len(raw_festivals)} festivals from {source.source_name}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Error collecting from {source.source_name}: {e}"
                        )
                        continue

        if not all_raw_data:
            self.logger.warning("No festival data collected from any source")
            return []

        # Parse raw data
        parsed_festivals = []
        for raw_data in all_raw_data:
            parsed = self.parser.parse_festival_data(raw_data)
            if parsed:
                parsed_festivals.append(parsed)

        self.logger.info(
            f"Parsed {len(parsed_festivals)} valid festivals from {len(all_raw_data)} raw entries"
        )

        # Deduplicate festivals
        deduplicated_festivals = self.deduplicator.deduplicate_festivals(
            parsed_festivals
        )

        # Store in database
        stored_festivals = await self._store_festivals(deduplicated_festivals)

        self.logger.info(f"Successfully processed {len(stored_festivals)} festivals")
        return stored_festivals

    async def _store_festivals(self, festivals: List[FestivalCreate]) -> List[Festival]:
        """Store festivals in the database."""
        stored_festivals = []

        from sqlalchemy import select

        from festival_playlist_generator.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            try:
                for festival_data in festivals:
                    try:
                        # Check if festival already exists
                        existing = await self._find_existing_festival(db, festival_data)

                        if existing:
                            # Update existing festival
                            updated = await self._update_festival(
                                db, existing, festival_data
                            )
                            if updated:
                                stored_festivals.append(updated)
                        else:
                            # Create new festival
                            created = await self._create_festival(db, festival_data)
                            if created:
                                stored_festivals.append(created)

                    except Exception as e:
                        self.logger.error(
                            f"Error storing festival {festival_data.name}: {e}"
                        )
                        continue

                await db.commit()

            except Exception as e:
                self.logger.error(f"Database error during festival storage: {e}")
                await db.rollback()
                raise

        return stored_festivals

    async def _find_existing_festival(
        self, db: Any, festival_data: FestivalCreate
    ) -> Optional[FestivalModel]:
        """Find existing festival in database."""
        from sqlalchemy import and_, select

        # Look for festivals with similar name and location
        result = await db.execute(
            select(FestivalModel).where(
                and_(
                    FestivalModel.name.ilike(f"%{festival_data.name}%"),
                    FestivalModel.location.ilike(f"%{festival_data.location}%"),
                )
            )
        )

        return result.scalar_one_or_none()  # type: ignore[no-any-return]

    async def _create_festival(
        self, db: Any, festival_data: FestivalCreate
    ) -> Optional[Festival]:
        """Create a new festival in the database."""
        from sqlalchemy import select

        try:
            # Create festival model
            festival_model = FestivalModel(
                name=festival_data.name,
                dates=festival_data.dates,
                location=festival_data.location,
                venue=festival_data.venue,
                genres=festival_data.genres,
                ticket_url=festival_data.ticket_url,
                # Visual branding fields
                logo_url=festival_data.logo_url,
                primary_color=festival_data.primary_color,
                secondary_color=festival_data.secondary_color,
                accent_colors=festival_data.accent_colors,
                branding_extracted_at=festival_data.branding_extracted_at,
            )

            db.add(festival_model)
            await db.flush()  # Get the ID

            # Handle artists (create if they don't exist)
            artist_images = festival_data.artist_images or {}

            for artist_name in festival_data.artists:
                result = await db.execute(
                    select(ArtistModel).where(ArtistModel.name == artist_name)
                )
                artist = result.scalar_one_or_none()

                if not artist:
                    artist = ArtistModel(name=artist_name)
                    db.add(artist)
                    await db.flush()

                # Update artist logo if we have image data for this artist
                if artist_name in artist_images:
                    image_data = artist_images[artist_name]
                    artist.logo_url = image_data.get("logo_url")
                    artist.logo_source = image_data.get("logo_source", "festival")
                    self.logger.info(
                        f"Set logo for artist {artist_name}: {artist.logo_url}"
                    )

                festival_model.artists.append(artist)

            # Convert to Pydantic model
            festival_schema = Festival(
                id=festival_model.id,
                name=festival_model.name,
                dates=festival_model.dates,
                location=festival_model.location,
                venue=festival_model.venue,
                genres=festival_model.genres or [],
                ticket_url=festival_model.ticket_url,
                artists=[artist.name for artist in festival_model.artists],
                created_at=festival_model.created_at,
                updated_at=festival_model.updated_at,
                # Visual branding fields
                logo_url=festival_model.logo_url,
                primary_color=festival_model.primary_color,
                secondary_color=festival_model.secondary_color,
                accent_colors=festival_model.accent_colors,
                branding_extracted_at=festival_model.branding_extracted_at,
            )

            return festival_schema

        except Exception as e:
            self.logger.error(f"Error creating festival {festival_data.name}: {e}")
            return None

    async def _update_festival(
        self, db: Any, existing: FestivalModel, festival_data: FestivalCreate
    ) -> Optional[Festival]:
        """Update an existing festival with new data."""
        from sqlalchemy import select

        try:
            # Update basic fields
            existing.name = festival_data.name
            existing.dates = festival_data.dates
            existing.location = festival_data.location
            existing.venue = festival_data.venue
            existing.genres = festival_data.genres
            existing.ticket_url = festival_data.ticket_url
            existing.updated_at = datetime.utcnow()

            # Update visual branding fields (only if provided)
            if festival_data.logo_url is not None:
                existing.logo_url = festival_data.logo_url
            if festival_data.primary_color is not None:
                existing.primary_color = festival_data.primary_color
            if festival_data.secondary_color is not None:
                existing.secondary_color = festival_data.secondary_color
            if festival_data.accent_colors is not None:
                existing.accent_colors = festival_data.accent_colors
            if festival_data.branding_extracted_at is not None:
                existing.branding_extracted_at = festival_data.branding_extracted_at

            # Update artists
            existing.artists.clear()
            artist_images = festival_data.artist_images or {}

            for artist_name in festival_data.artists:
                result = await db.execute(
                    select(ArtistModel).where(ArtistModel.name == artist_name)
                )
                artist = result.scalar_one_or_none()

                if not artist:
                    artist = ArtistModel(name=artist_name)
                    db.add(artist)
                    await db.flush()

                # Update artist logo if we have image data for this artist
                if artist_name in artist_images:
                    image_data = artist_images[artist_name]
                    artist.logo_url = image_data.get("logo_url")
                    artist.logo_source = image_data.get("logo_source", "festival")
                    self.logger.info(
                        f"Updated logo for artist {artist_name}: {artist.logo_url}"
                    )

                existing.artists.append(artist)

            # Convert to Pydantic model
            festival_schema = Festival(
                id=existing.id,
                name=existing.name,
                dates=existing.dates,
                location=existing.location,
                venue=existing.venue,
                genres=existing.genres or [],
                ticket_url=existing.ticket_url,
                artists=[artist.name for artist in existing.artists],
                created_at=existing.created_at,
                updated_at=existing.updated_at,
                # Visual branding fields
                logo_url=existing.logo_url,
                primary_color=existing.primary_color,
                secondary_color=existing.secondary_color,
                accent_colors=existing.accent_colors,
                branding_extracted_at=existing.branding_extracted_at,
            )

            return festival_schema

        except Exception as e:
            self.logger.error(f"Error updating festival {existing.name}: {e}")
            return None

    def generate_festival_id(self, festival_data: FestivalCreate) -> str:
        """Generate a unique identifier for a festival."""
        # Create a hash based on name, location, and first date
        content = f"{festival_data.name}|{festival_data.location}"
        if festival_data.dates:
            content += f"|{festival_data.dates[0].strftime('%Y-%m-%d')}"

        return hashlib.md5(content.encode()).hexdigest()
