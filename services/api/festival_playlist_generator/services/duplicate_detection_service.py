"""Duplicate Detection Service - Find potential duplicate artists."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from festival_playlist_generator.models.artist import Artist
from festival_playlist_generator.services.name_normalization_service import (
    name_normalization_service,
)


@dataclass
class ArtistStats:
    """Statistics about an artist for duplicate detection."""

    id: str
    name: str
    normalized_name: str
    festival_count: int
    setlist_count: int
    has_spotify: bool
    spotify_id: Optional[str]

    @property
    def total_data_score(self) -> int:
        """Calculate a score representing how much data this artist has."""
        score = 0
        score += self.festival_count * 10  # Festivals are most important
        score += self.setlist_count * 2  # Setlists are valuable
        score += 50 if self.has_spotify else 0  # Spotify data is important
        return score


@dataclass
class DuplicateGroup:
    """A group of artists that are potential duplicates."""

    normalized_name: str
    artists: List[ArtistStats]

    @property
    def primary_artist(self) -> ArtistStats:
        """Get the artist with the most data (best candidate to keep)."""
        return max(self.artists, key=lambda a: a.total_data_score)

    @property
    def secondary_artists(self) -> List[ArtistStats]:
        """Get all artists except the primary (candidates for merging)."""
        primary = self.primary_artist
        return [a for a in self.artists if a.id != primary.id]


class DuplicateDetectionService:
    """Service for detecting potential duplicate artists."""

    def __init__(self, db: Session):
        """
        Initialize the duplicate detection service.

        Args:
            db: Database session
        """
        self.db = db

    def find_all_duplicates(self) -> List[DuplicateGroup]:
        """
        Find all groups of potential duplicate artists.

        Uses case-insensitive name matching to find artists with the same
        normalized name.

        Returns:
            List of duplicate groups, each containing 2+ artists

        Example:
            >>> groups = service.find_all_duplicates()
            >>> for group in groups:
            ...     print(f"{group.normalized_name}: {len(group.artists)} duplicates")
        """
        # Get all artists with their stats
        artists = self.db.query(Artist).all()

        # Group by normalized name
        groups_dict: Dict[str, List[ArtistStats]] = {}

        for artist in artists:
            normalized = name_normalization_service.normalize_for_comparison(
                artist.name
            )

            # Load stats for this artist
            stats = self._load_artist_stats(artist)

            if normalized not in groups_dict:
                groups_dict[normalized] = []
            groups_dict[normalized].append(stats)

        # Filter to only groups with 2+ artists (actual duplicates)
        duplicate_groups = [
            DuplicateGroup(normalized_name=name, artists=artists)
            for name, artists in groups_dict.items()
            if len(artists) >= 2
        ]

        # Sort by number of duplicates (most duplicates first)
        duplicate_groups.sort(key=lambda g: len(g.artists), reverse=True)

        return duplicate_groups

    def find_duplicates_for_artist(self, artist_id: str) -> Optional[DuplicateGroup]:
        """
        Find potential duplicates for a specific artist.

        Args:
            artist_id: ID of the artist to check

        Returns:
            DuplicateGroup if duplicates found, None otherwise

        Example:
            >>> group = service.find_duplicates_for_artist(artist_id)
            >>> if group:
            ...     print(f"Found {len(group.artists)} duplicates")
        """
        # Get the artist
        artist = self.db.query(Artist).filter(Artist.id == artist_id).first()
        if not artist:
            return None

        # Get normalized name
        normalized = name_normalization_service.normalize_for_comparison(artist.name)

        # Find all artists with same normalized name
        all_artists = self.db.query(Artist).all()
        duplicates = []

        for other in all_artists:
            other_normalized = name_normalization_service.normalize_for_comparison(
                other.name
            )
            if other_normalized == normalized:
                stats = self._load_artist_stats(other)
                duplicates.append(stats)

        # Return group if we found duplicates (2+ artists)
        if len(duplicates) >= 2:
            return DuplicateGroup(normalized_name=normalized, artists=duplicates)

        return None

    def is_exact_match(self, name1: str, name2: str) -> bool:
        """
        Check if two names are exact matches (case-insensitive).

        Args:
            name1: First artist name
            name2: Second artist name

        Returns:
            True if names match (case-insensitive)

        Example:
            >>> service.is_exact_match("AC/DC", "ac/dc")
            True
            >>> service.is_exact_match("Metallica", "Megadeth")
            False
        """
        norm1 = name_normalization_service.normalize_for_comparison(name1)
        norm2 = name_normalization_service.normalize_for_comparison(name2)
        return norm1 == norm2

    def calculate_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity score between two artist names.

        Uses simple string similarity for now. Could be enhanced with
        fuzzy matching algorithms like Levenshtein distance.

        Args:
            name1: First artist name
            name2: Second artist name

        Returns:
            Similarity score from 0.0 (no match) to 1.0 (exact match)

        Example:
            >>> service.calculate_similarity("Metallica", "Metallica")
            1.0
            >>> service.calculate_similarity("Metallica", "METALLICA")
            1.0
            >>> service.calculate_similarity("Metallica", "Megadeth")
            0.0
        """
        # Normalize both names
        norm1 = name_normalization_service.normalize_for_comparison(name1)
        norm2 = name_normalization_service.normalize_for_comparison(name2)

        # Exact match
        if norm1 == norm2:
            return 1.0

        # For now, return 0.0 for non-exact matches
        # TODO: Implement fuzzy matching (Levenshtein, Jaro-Winkler, etc)
        return 0.0

    def _load_artist_stats(self, artist: Artist) -> ArtistStats:
        """
        Load statistics for an artist.

        Args:
            artist: Artist model instance

        Returns:
            ArtistStats with counts and flags
        """
        # Count festivals
        festival_count = len(artist.festivals) if artist.festivals else 0

        # Count setlists
        setlist_count = len(artist.setlists) if artist.setlists else 0

        # Check Spotify data
        has_spotify = bool(artist.spotify_id)

        return ArtistStats(
            id=str(artist.id),  # Convert UUID to string for consistency
            name=artist.name,
            normalized_name=name_normalization_service.normalize_for_comparison(
                artist.name
            ),
            festival_count=festival_count,
            setlist_count=setlist_count,
            has_spotify=has_spotify,
            spotify_id=artist.spotify_id,
        )


# Factory function for creating service instances
def create_duplicate_detection_service(db: Session) -> DuplicateDetectionService:
    """
    Create a duplicate detection service instance.

    Args:
        db: Database session

    Returns:
        DuplicateDetectionService instance
    """
    return DuplicateDetectionService(db)
