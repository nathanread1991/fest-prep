"""Smart Artist Search Service - Fuzzy matching with multiple strategies."""

import logging
import re
from typing import Any, Dict, List, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.services.name_normalization_service import (
    NameNormalizationService,
)

logger = logging.getLogger(__name__)


class SmartArtistSearch:
    """
    Smart artist search using multiple strategies:
    1. Exact match (case-insensitive)
    2. Normalized name match (removes "The", "&", punctuation, etc.)
    3. Contains match (partial string matching)
    4. Token-based fuzzy match (word-by-word comparison)
    5. Spotify search fallback (if available)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self, query: str, limit: int = 10, include_spotify_fallback: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for artists using multiple strategies.

        Args:
            query: Search query
            limit: Maximum number of results
            include_spotify_fallback: Whether to search Spotify if no local results

        Returns:
            List of artist dictionaries with match scores
        """
        if not query or not query.strip():
            return []

        query = query.strip()
        results = {}  # artist_id -> {artist_data, score, match_type}

        # Strategy 1: Exact match (case-insensitive)
        exact_matches = await self._exact_match(query)
        for artist in exact_matches:
            results[str(artist.id)] = {
                "artist": artist,
                "score": 100,
                "match_type": "exact",
            }

        # Strategy 2: Normalized name match
        normalized_matches = await self._normalized_match(query)
        for artist in normalized_matches:
            artist_id = str(artist.id)
            if artist_id not in results:
                results[artist_id] = {
                    "artist": artist,
                    "score": 90,
                    "match_type": "normalized",
                }

        # Strategy 3: Contains match (partial string)
        contains_matches = await self._contains_match(query)
        for artist in contains_matches:
            artist_id = str(artist.id)
            if artist_id not in results:
                # Calculate score based on how much of the query matches
                score = self._calculate_contains_score(query, artist.name)
                results[artist_id] = {
                    "artist": artist,
                    "score": score,
                    "match_type": "contains",
                }

        # Strategy 4: Token-based fuzzy match
        token_matches = await self._token_match(query)
        for artist, score in token_matches:
            artist_id = str(artist.id)
            if artist_id not in results:
                results[artist_id] = {
                    "artist": artist,
                    "score": score,
                    "match_type": "token",
                }

        # Sort by score (highest first) and limit
        sorted_results = sorted(
            results.values(), key=lambda x: cast(float, x["score"]), reverse=True
        )[:limit]

        # Format results
        formatted_results = []
        for result in sorted_results:
            artist = cast(ArtistModel, result["artist"])
            formatted_results.append(
                {
                    "id": str(artist.id),
                    "name": artist.name,
                    "festival_count": len(artist.festivals) if artist.festivals else 0,
                    "setlist_count": len(artist.setlists) if artist.setlists else 0,
                    "has_spotify": bool(artist.spotify_id),
                    "genres": artist.genres if artist.genres else [],
                    "match_score": result["score"],
                    "match_type": result["match_type"],
                }
            )

        # If no results and Spotify fallback is enabled, suggest Spotify search
        if not formatted_results and include_spotify_fallback:
            logger.info(
                f"No local matches for '{query}', Spotify fallback could be used"
            )

        return formatted_results

    async def _exact_match(self, query: str) -> List[ArtistModel]:
        """Exact case-insensitive match."""
        result = await self.db.execute(
            select(ArtistModel)
            .options(
                selectinload(ArtistModel.festivals), selectinload(ArtistModel.setlists)
            )
            .filter(func.lower(ArtistModel.name) == query.lower())
        )
        return list(result.scalars().all())

    async def _normalized_match(self, query: str) -> List[ArtistModel]:
        """Match using normalized names (removes 'The', '&', punctuation, etc.)."""
        normalizer = NameNormalizationService()
        normalized_query = normalizer.normalize(query)

        # Get all artists and filter in Python (since we can't easily normalize in SQL)
        result = await self.db.execute(
            select(ArtistModel).options(
                selectinload(ArtistModel.festivals), selectinload(ArtistModel.setlists)
            )
        )
        all_artists = result.scalars().all()

        matches = []
        for artist in all_artists:
            if normalizer.normalize(artist.name) == normalized_query:
                matches.append(artist)

        return matches

    async def _contains_match(self, query: str) -> List[ArtistModel]:
        """Partial string matching (case-insensitive)."""
        # Use ILIKE for case-insensitive contains
        search_pattern = f"%{query}%"

        result = await self.db.execute(
            select(ArtistModel)
            .options(
                selectinload(ArtistModel.festivals), selectinload(ArtistModel.setlists)
            )
            .filter(ArtistModel.name.ilike(search_pattern))
        )
        return list(result.scalars().all())

    async def _token_match(self, query: str) -> List[tuple[ArtistModel, int]]:
        """
        Token-based fuzzy matching.
        Splits query into words and finds artists that contain those words.

        Example:
        Query: "Rubbersnake Charmers"
        Matches: "Mario Lalli & The Rubber Snake Charmers"
                 (contains "Rubber", "Snake", "Charmers")
        """
        # Tokenize query (split on whitespace and remove common words)
        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        # Get all artists
        result = await self.db.execute(
            select(ArtistModel).options(
                selectinload(ArtistModel.festivals), selectinload(ArtistModel.setlists)
            )
        )
        all_artists = result.scalars().all()

        matches = []
        for artist in all_artists:
            artist_tokens = self._tokenize(artist.name)
            score = self._calculate_token_score(query_tokens, artist_tokens)

            # Only include if at least 50% of query tokens match
            if score >= 50:
                matches.append((artist, score))

        return matches

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into normalized words.
        Removes common words like 'the', 'and', '&'.
        """
        # Convert to lowercase
        text = text.lower()

        # Replace '&' with 'and'
        text = text.replace("&", "and")

        # Remove punctuation except spaces
        text = re.sub(r"[^\w\s]", "", text)

        # Split into words
        words = text.split()

        # Remove common stop words
        stop_words = {"the", "and", "a", "an", "of", "in", "on", "at", "to", "for"}
        words = [w for w in words if w not in stop_words]

        return words

    def _calculate_token_score(
        self, query_tokens: List[str], artist_tokens: List[str]
    ) -> int:
        """
        Calculate match score based on token overlap.

        Returns score from 0-100 based on:
        - How many query tokens are found in artist tokens
        - Bonus for exact token matches
        - Bonus for substring matches
        """
        if not query_tokens:
            return 0

        matched_tokens = 0
        partial_matches = 0

        for q_token in query_tokens:
            # Check for exact match
            if q_token in artist_tokens:
                matched_tokens += 1
            else:
                # Check for partial match (substring)
                for a_token in artist_tokens:
                    if q_token in a_token or a_token in q_token:
                        partial_matches += 1
                        break

        # Calculate score
        exact_match_score = (matched_tokens / len(query_tokens)) * 80
        partial_match_score = (partial_matches / len(query_tokens)) * 20

        return int(exact_match_score + partial_match_score)

    def _calculate_contains_score(self, query: str, artist_name: str) -> int:
        """
        Calculate score for contains match based on:
        - Length of match relative to artist name
        - Position of match (earlier is better)
        """
        query_lower = query.lower()
        name_lower = artist_name.lower()

        if query_lower == name_lower:
            return 100

        if query_lower in name_lower:
            # Score based on how much of the name is the query
            match_ratio = len(query) / len(artist_name)
            position_score = 100 - (
                name_lower.index(query_lower) / len(name_lower) * 20
            )
            return int(match_ratio * 60 + position_score * 0.4)

        return 50  # Default for contains matches


async def smart_search_artists(
    db: AsyncSession, query: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Convenience function for smart artist search.

    Args:
        db: Database session
        query: Search query
        limit: Maximum number of results

    Returns:
        List of artist dictionaries with match scores
    """
    search_service = SmartArtistSearch(db)
    return await search_service.search(query, limit=limit)
