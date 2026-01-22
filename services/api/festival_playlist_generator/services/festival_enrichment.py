"""Festival Data Enrichment Service - Fetches festival data from multiple sources."""

import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import httpx

from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)


class FestivalEnrichmentService:
    """Service to enrich festival data from Clashfinder and other sources."""

    def __init__(self) -> None:
        self.clashfinder_username = settings.CLASHFINDER_USERNAME
        self.clashfinder_private_key = settings.CLASHFINDER_PRIVATE_KEY
        self.base_url = "https://clashfinder.com"

    def _generate_public_key(
        self, auth_param: str = "", auth_valid_until: str = ""
    ) -> str:
        """Generate SHA256 public key for Clashfinder API authentication."""
        hash_input = self.clashfinder_username + self.clashfinder_private_key

        if auth_param:
            hash_input += auth_param

        if auth_valid_until:
            hash_input += auth_valid_until

        public_key = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        return public_key

    async def fetch_from_clashfinder(
        self, clashfinder_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch festival data from Clashfinder API.

        Args:
            clashfinder_id: The Clashfinder event ID (e.g., 'coachella2024')

        Returns:
            Dictionary with enriched festival data or None if not found
        """
        if not self.clashfinder_username or not self.clashfinder_private_key:
            logger.warning("Clashfinder credentials not configured")
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Build the API endpoint URL
                api_url = f"{self.base_url}/data/event/{clashfinder_id}.json"

                # Build authentication parameters
                params = {
                    "authUsername": self.clashfinder_username,
                    "authPublicKey": self._generate_public_key(),
                }

                logger.info(f"Fetching Clashfinder data for ID: {clashfinder_id}")

                response = await client.get(api_url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_clashfinder_data(data, clashfinder_id)
                elif response.status_code == 404:
                    logger.warning(f"Clashfinder not found: {clashfinder_id}")
                    return {"error": "Festival not found on Clashfinder"}
                elif response.status_code == 401:
                    logger.error("Clashfinder API authentication failed")
                    return {"error": "Authentication failed"}
                else:
                    logger.error(f"Clashfinder API error: {response.status_code}")
                    return {"error": f"API error: {response.status_code}"}

        except httpx.TimeoutException:
            logger.error(f"Timeout fetching Clashfinder data for: {clashfinder_id}")
            return {"error": "Request timeout"}
        except Exception as e:
            logger.error(f"Error fetching Clashfinder data: {e}")
            return {"error": str(e)}

    def _parse_clashfinder_data(
        self, data: Dict[str, Any], clashfinder_id: str
    ) -> Dict[str, Any]:
        """Parse Clashfinder API response into a standardized format."""
        try:
            enriched_data: Dict[str, Any] = {
                "source": "clashfinder",
                "clashfinder_id": clashfinder_id,
            }

            # Extract festival name
            enriched_data["name"] = (
                data.get("name")
                or data.get("title")
                or data.get("festival_name")
                or data.get("event_name")
                or clashfinder_id.replace("-", " ").replace("_", " ").title()
            )

            # Extract location
            enriched_data["location"] = (
                data.get("location")
                or data.get("venue")
                or data.get("city")
                or data.get("place")
                or ""
            )

            # Extract venue
            enriched_data["venue"] = data.get("venue_name") or data.get("venue") or ""

            # Extract dates
            dates = self._extract_dates(data)
            enriched_data["dates"] = dates

            # Extract artists from lineup
            artists = self._extract_artists(data)
            enriched_data["artists"] = artists

            # Extract genres
            genres = data.get("genres") or data.get("genre") or []
            if isinstance(genres, str):
                genres = [genres]
            enriched_data["genres"] = genres

            # Extract ticket URL
            enriched_data["ticket_url"] = (
                data.get("ticket_url")
                or data.get("tickets")
                or data.get("url")
                or data.get("website")
                or ""
            )

            # Add metadata
            enriched_data["artist_count"] = len(artists)
            enriched_data["date_range"] = self._format_date_range(dates)

            logger.info(
                f"Successfully parsed Clashfinder data: {enriched_data['name']} with {len(artists)} artists"
            )

            return enriched_data

        except Exception as e:
            logger.error(f"Error parsing Clashfinder data: {e}")
            return {"error": f"Failed to parse data: {str(e)}"}

    def _extract_dates(self, data: Dict[str, Any]) -> List[str]:
        """Extract and parse dates from Clashfinder data."""
        dates = []

        # Try different possible date fields
        date_fields = ["start_date", "date", "event_date", "dates", "start", "begin"]

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
                if dates:
                    break

        # If no dates found, try to extract from event info
        if not dates and "info" in data:
            info_text = str(data["info"])
            date_patterns = [
                r"\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
                r"\d{1,2}/\d{1,2}/\d{4}",  # MM/DD/YYYY or DD/MM/YYYY
            ]
            for pattern in date_patterns:
                matches = re.findall(pattern, info_text)
                for match in matches:
                    parsed_date = self._parse_date(match)
                    if parsed_date:
                        dates.append(parsed_date)

        return sorted(set(dates))  # Remove duplicates and sort

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string and return in YYYY-MM-DD format."""
        if not date_str:
            return None

        date_str = date_str.strip()

        # Try different date formats
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
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return None

    def _extract_artists(self, data: Dict[str, Any]) -> List[str]:
        """Extract artist names from Clashfinder lineup data."""
        artists = []

        # Try different possible lineup structures
        lineup_fields = ["lineup", "artists", "performers", "acts", "bands"]

        for field in lineup_fields:
            if field in data:
                lineup_data = data[field]
                extracted = self._parse_lineup_data(lineup_data)
                if extracted:
                    artists.extend(extracted)
                    break

        # If no artists found, try to extract from stages or days
        if not artists:
            for key in ["stages", "days", "schedule"]:
                if key in data:
                    stages_data = data[key]
                    if isinstance(stages_data, dict):
                        for stage_name, stage_data in stages_data.items():
                            if isinstance(stage_data, list):
                                extracted = self._parse_lineup_data(stage_data)
                                artists.extend(extracted)
                            elif isinstance(stage_data, dict):
                                if "artists" in stage_data:
                                    extracted = self._parse_lineup_data(
                                        stage_data["artists"]
                                    )
                                    artists.extend(extracted)
                                elif "lineup" in stage_data:
                                    extracted = self._parse_lineup_data(
                                        stage_data["lineup"]
                                    )
                                    artists.extend(extracted)

        # Remove duplicates while preserving order
        unique_artists = []
        seen = set()
        for artist in artists:
            normalized = artist.lower().strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_artists.append(artist.strip())

        return unique_artists

    def _parse_lineup_data(self, lineup_data: Any) -> List[str]:
        """Parse lineup data structure to extract artist names."""
        artists = []

        if isinstance(lineup_data, list):
            for item in lineup_data:
                if isinstance(item, str):
                    artists.append(item)
                elif isinstance(item, dict):
                    # Try different possible name fields
                    name_fields = [
                        "name",
                        "artist",
                        "performer",
                        "act",
                        "title",
                        "band",
                    ]
                    for field in name_fields:
                        if field in item and item[field]:
                            artists.append(str(item[field]))
                            break
        elif isinstance(lineup_data, dict):
            # Handle case where lineup_data is a dict with artist info
            name_fields = ["name", "artist", "performer", "act", "title", "band"]
            for field in name_fields:
                if field in lineup_data and lineup_data[field]:
                    artists.append(str(lineup_data[field]))
                    break

        return artists

    def _format_date_range(self, dates: List[str]) -> str:
        """Format a list of dates into a readable range."""
        if not dates:
            return ""

        if len(dates) == 1:
            try:
                dt = datetime.strptime(dates[0], "%Y-%m-%d")
                return dt.strftime("%B %d, %Y")
            except:
                return dates[0]

        try:
            start_dt = datetime.strptime(dates[0], "%Y-%m-%d")
            end_dt = datetime.strptime(dates[-1], "%Y-%m-%d")

            if start_dt.year == end_dt.year:
                if start_dt.month == end_dt.month:
                    return f"{start_dt.strftime('%B %d')} - {end_dt.strftime('%d, %Y')}"
                else:
                    return (
                        f"{start_dt.strftime('%B %d')} - {end_dt.strftime('%B %d, %Y')}"
                    )
            else:
                return (
                    f"{start_dt.strftime('%B %d, %Y')} - {end_dt.strftime('%B %d, %Y')}"
                )
        except:
            return f"{dates[0]} - {dates[-1]}"


# Global instance
festival_enrichment_service = FestivalEnrichmentService()
