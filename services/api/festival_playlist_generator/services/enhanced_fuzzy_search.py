"""Enhanced Fuzzy Artist Search with Levenshtein distance and phonetic matching."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.services.name_normalization_service import (
    normalize_artist_name,
)

logger = logging.getLogger(__name__)


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance between two strings.
    This measures the minimum number of single-character edits needed.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def similarity_ratio(s1: str, s2: str) -> float:
    """
    Calculate similarity ratio between two strings (0.0 to 1.0).
    Based on Levenshtein distance.
    """
    distance = levenshtein_distance(s1.lower(), s2.lower())
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return 1.0 - (distance / max_len)


def soundex(name: str) -> str:
    """
    Generate Soundex code for phonetic matching.
    Soundex codes sound-alike names to the same code.
    """
    # Remove non-alphabetic characters and convert to uppercase
    name = re.sub(r"[^A-Za-z]", "", name).upper()

    if not name:
        return "0000"

    # Soundex mapping
    soundex_mapping = {
        "B": "1",
        "F": "1",
        "P": "1",
        "V": "1",
        "C": "2",
        "G": "2",
        "J": "2",
        "K": "2",
        "Q": "2",
        "S": "2",
        "X": "2",
        "Z": "2",
        "D": "3",
        "T": "3",
        "L": "4",
        "M": "5",
        "N": "5",
        "R": "6",
    }

    # Keep first letter
    code = name[0]

    # Process remaining letters
    for char in name[1:]:
        if char in soundex_mapping:
            digit = soundex_mapping[char]
            # Don't add consecutive duplicates
            if code[-1] != digit:
                code += digit
        # Ignore vowels and H, W, Y

    # Pad with zeros or truncate to 4 characters
    code = (code + "000")[:4]

    return code


def metaphone(name: str) -> str:
    """
    Simplified Metaphone algorithm for phonetic matching.
    More accurate than Soundex for English names.
    """
    name = re.sub(r"[^A-Za-z]", "", name).upper()

    if not name:
        return ""

    # Simplified metaphone rules
    result = []
    i = 0

    while i < len(name):
        char = name[i]

        # Skip vowels except at start
        if char in "AEIOU":
            if i == 0:
                result.append(char)
            i += 1
            continue

        # Handle consonants
        if char == "B":
            result.append("B")
        elif char == "C":
            if i + 1 < len(name) and name[i + 1] == "H":
                result.append("X")
                i += 1
            elif i + 1 < len(name) and name[i + 1] in "EIY":
                result.append("S")
            else:
                result.append("K")
        elif char == "D":
            result.append("T")
        elif char == "F":
            result.append("F")
        elif char == "G":
            if i + 1 < len(name) and name[i + 1] in "EIY":
                result.append("J")
            else:
                result.append("K")
        elif char == "H":
            # H is silent after vowel
            if i > 0 and name[i - 1] not in "AEIOU":
                result.append("H")
        elif char == "J":
            result.append("J")
        elif char == "K":
            result.append("K")
        elif char == "L":
            result.append("L")
        elif char == "M":
            result.append("M")
        elif char == "N":
            result.append("N")
        elif char == "P":
            if i + 1 < len(name) and name[i + 1] == "H":
                result.append("F")
                i += 1
            else:
                result.append("P")
        elif char == "Q":
            result.append("K")
        elif char == "R":
            result.append("R")
        elif char == "S":
            if i + 1 < len(name) and name[i + 1] == "H":
                result.append("X")
                i += 1
            else:
                result.append("S")
        elif char == "T":
            if i + 1 < len(name) and name[i + 1] == "H":
                result.append("0")
                i += 1
            else:
                result.append("T")
        elif char == "V":
            result.append("F")
        elif char == "W":
            result.append("W")
        elif char == "X":
            result.append("KS")
        elif char == "Y":
            result.append("Y")
        elif char == "Z":
            result.append("S")

        i += 1

    return "".join(result)[:8]  # Limit length


class EnhancedFuzzySearch:
    """
    Enhanced fuzzy search with multiple matching strategies:
    1. Exact match
    2. Normalized match
    3. Levenshtein distance (typo tolerance)
    4. Phonetic matching (Soundex + Metaphone)
    5. Token-based matching
    6. Character n-gram matching
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self, query: str, limit: int = 10, min_score: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search for artists using enhanced fuzzy matching.

        Args:
            query: Search query
            limit: Maximum number of results
            min_score: Minimum match score (0-100)

        Returns:
            List of artist dictionaries with match scores
        """
        if not query or not query.strip():
            return []

        query = query.strip()

        # Get all artists (we'll score them all)
        result = await self.db.execute(
            select(ArtistModel).options(
                selectinload(ArtistModel.festivals), selectinload(ArtistModel.setlists)
            )
        )
        all_artists = result.scalars().all()

        # Score each artist
        scored_artists = []
        for artist in all_artists:
            score, match_type = self._calculate_match_score(query, artist.name)

            if score >= min_score:
                scored_artists.append(
                    {"artist": artist, "score": score, "match_type": match_type}
                )

        # Sort by score (highest first) and limit
        scored_artists.sort(key=lambda x: x["score"], reverse=True)
        scored_artists = scored_artists[:limit]

        # Format results
        formatted_results = []
        for item in scored_artists:
            artist = item["artist"]
            formatted_results.append(
                {
                    "id": str(artist.id),
                    "name": artist.name,
                    "festival_count": len(artist.festivals) if artist.festivals else 0,
                    "setlist_count": len(artist.setlists) if artist.setlists else 0,
                    "has_spotify": bool(artist.spotify_id),
                    "genres": artist.genres if artist.genres else [],
                    "match_score": item["score"],
                    "match_type": item["match_type"],
                }
            )

        return formatted_results

    def _calculate_match_score(self, query: str, artist_name: str) -> Tuple[int, str]:
        """
        Calculate comprehensive match score using multiple strategies.
        Returns (score, match_type).
        """
        query_lower = query.lower()
        name_lower = artist_name.lower()

        # Strategy 1: Exact match (100 points)
        if query_lower == name_lower:
            return (100, "exact")

        # Strategy 2: Normalized match (95 points)
        query_norm = normalize_artist_name(query)
        name_norm = normalize_artist_name(artist_name)
        if query_norm == name_norm:
            return (95, "normalized")

        # Strategy 3: Contains match (85-90 points)
        if query_lower in name_lower:
            ratio = len(query) / len(artist_name)
            score = int(85 + (ratio * 5))
            return (score, "contains")
        if name_lower in query_lower:
            ratio = len(artist_name) / len(query)
            score = int(85 + (ratio * 5))
            return (score, "contains")

        # Strategy 4: Levenshtein similarity (60-85 points)
        lev_ratio = similarity_ratio(query_lower, name_lower)
        if lev_ratio >= 0.6:  # At least 60% similar
            score = int(60 + (lev_ratio - 0.6) * 62.5)  # Scale 0.6-1.0 to 60-85
            return (score, "levenshtein")

        # Strategy 5: Phonetic matching (55-75 points)
        query_soundex = soundex(query)
        name_soundex = soundex(artist_name)
        query_metaphone = metaphone(query)
        name_metaphone = metaphone(artist_name)

        if query_soundex == name_soundex and query_soundex != "0000":
            # Soundex match - calculate additional similarity
            lev_ratio = similarity_ratio(query_lower, name_lower)
            score = int(55 + (lev_ratio * 20))
            return (score, "phonetic_soundex")

        if query_metaphone == name_metaphone and query_metaphone != "":
            # Metaphone match
            lev_ratio = similarity_ratio(query_lower, name_lower)
            score = int(60 + (lev_ratio * 15))
            return (score, "phonetic_metaphone")

        # Strategy 6: Token-based matching (50-70 points)
        query_tokens = self._tokenize(query)
        name_tokens = self._tokenize(artist_name)

        if query_tokens and name_tokens:
            token_score = self._calculate_token_score(query_tokens, name_tokens)
            if token_score >= 50:
                return (token_score, "token")

        # Strategy 7: Character n-gram matching (45-65 points)
        ngram_score = self._calculate_ngram_score(query_lower, name_lower)
        if ngram_score >= 45:
            return (ngram_score, "ngram")

        # No good match
        return (0, "none")

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into normalized words."""
        text = text.lower()
        text = text.replace("&", "and")
        text = re.sub(r"[^\w\s]", "", text)
        words = text.split()
        stop_words = {"the", "and", "a", "an", "of", "in", "on", "at", "to", "for"}
        words = [w for w in words if w not in stop_words]
        return words

    def _calculate_token_score(
        self, query_tokens: List[str], artist_tokens: List[str]
    ) -> int:
        """Calculate match score based on token overlap with fuzzy matching."""
        if not query_tokens:
            return 0

        matched_tokens = 0
        partial_matches = 0

        for q_token in query_tokens:
            best_match = 0

            for a_token in artist_tokens:
                # Exact match
                if q_token == a_token:
                    best_match = 1.0
                    break

                # Substring match
                if q_token in a_token or a_token in q_token:
                    best_match = max(best_match, 0.7)

                # Levenshtein similarity
                sim = similarity_ratio(q_token, a_token)
                if sim > best_match:
                    best_match = sim

            if best_match >= 0.8:
                matched_tokens += 1
            elif best_match >= 0.5:
                partial_matches += 1

        # Calculate score
        exact_match_score = (matched_tokens / len(query_tokens)) * 70
        partial_match_score = (partial_matches / len(query_tokens)) * 30

        return int(exact_match_score + partial_match_score)

    def _calculate_ngram_score(self, s1: str, s2: str, n: int = 2) -> int:
        """
        Calculate similarity based on character n-grams.
        Useful for catching transpositions and character-level errors.
        """

        def get_ngrams(s: str, n: int) -> set:
            return set(s[i : i + n] for i in range(len(s) - n + 1))

        ngrams1 = get_ngrams(s1, n)
        ngrams2 = get_ngrams(s2, n)

        if not ngrams1 or not ngrams2:
            return 0

        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)

        if union == 0:
            return 0

        jaccard = intersection / union
        return int(45 + (jaccard * 20))  # Scale to 45-65


async def enhanced_fuzzy_search(
    db: AsyncSession, query: str, limit: int = 10, min_score: int = 50
) -> List[Dict[str, Any]]:
    """
    Convenience function for enhanced fuzzy search.

    Args:
        db: Database session
        query: Search query
        limit: Maximum number of results
        min_score: Minimum match score (0-100)

    Returns:
        List of artist dictionaries with match scores
    """
    search_service = EnhancedFuzzySearch(db)
    return await search_service.search(query, limit=limit, min_score=min_score)
