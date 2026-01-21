"""Recommendation engine service for personalized festival and artist recommendations."""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.models.artist import Artist
from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.models.playlist import Playlist
from festival_playlist_generator.models.song import Song
from festival_playlist_generator.models.user import User, UserSongPreference


@dataclass
class UserProfile:
    """User music taste profile."""

    user_id: str
    preferred_genres: Dict[str, float]  # genre -> preference score
    preferred_artists: Dict[str, float]  # artist_id -> preference score
    known_songs_count: int
    total_songs_count: int
    discovery_rate: float  # percentage of unknown songs
    created_at: datetime


@dataclass
class FestivalRecommendation:
    """Festival recommendation with similarity score."""

    festival_id: str
    festival_name: str
    similarity_score: float
    matching_artists: List[str]
    recommended_artists: List[str]
    dates: List[datetime]
    location: str


@dataclass
class ArtistRecommendation:
    """Artist recommendation with similarity score."""

    artist_id: str
    artist_name: str
    similarity_score: float
    genres: List[str]
    popularity_score: Optional[float]


class RecommendationEngine:
    """Service for generating personalized recommendations."""

    def __init__(self, db: Session):
        self.db = db

    async def analyze_user_preferences(self, user_id: str) -> UserProfile:
        """
        Analyze user's music preferences from their playlist and song preference history.

        Args:
            user_id: User identifier

        Returns:
            UserProfile with analyzed preferences
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Get user's song preferences
        song_preferences = (
            self.db.query(UserSongPreference)
            .filter(UserSongPreference.user_id == user_id)
            .all()
        )

        # Get user's playlists and associated songs
        user_playlists = (
            self.db.query(Playlist).filter(Playlist.user_id == user_id).all()
        )

        # Analyze genre preferences from playlists and known songs
        genre_counter: Dict[str, float] = defaultdict(float)
        artist_counter: Dict[str, float] = defaultdict(float)
        known_songs_count = 0
        total_songs_count = 0

        # Process song preferences
        for pref in song_preferences:
            total_songs_count += 1
            if pref.is_known:
                known_songs_count += 1

                # Get song details for genre and artist analysis
                song = self.db.query(Song).filter(Song.id == pref.song_id).first()
                if song:
                    # Get artist details
                    artist = (
                        self.db.query(Artist).filter(Artist.name == song.artist).first()
                    )
                    if artist:
                        artist_counter[artist.id] += 1
                        # Add genres from artist
                        for genre in artist.genres or []:
                            genre_counter[genre] += 1

        # Process playlists for additional preference signals
        for playlist in user_playlists:
            # Get songs from playlist
            playlist_songs = self.db.query(Song).join(playlist.songs).all()

            for song in playlist_songs:
                artist = (
                    self.db.query(Artist).filter(Artist.name == song.artist).first()
                )
                if artist:
                    artist_counter[artist.id] += 0.5  # Lower weight for playlist songs
                    for genre in artist.genres or []:
                        genre_counter[genre] += 0.5

        # Calculate preference scores (normalize to 0-1 range)
        max_genre_count = max(genre_counter.values()) if genre_counter else 1
        max_artist_count = max(artist_counter.values()) if artist_counter else 1

        preferred_genres = {
            genre: count / max_genre_count for genre, count in genre_counter.items()
        }

        preferred_artists = {
            artist_id: count / max_artist_count
            for artist_id, count in artist_counter.items()
        }

        # Calculate discovery rate
        discovery_rate = (
            (total_songs_count - known_songs_count) / total_songs_count
            if total_songs_count > 0
            else 1.0
        )

        return UserProfile(
            user_id=user_id,
            preferred_genres=preferred_genres,
            preferred_artists=preferred_artists,
            known_songs_count=known_songs_count,
            total_songs_count=total_songs_count,
            discovery_rate=discovery_rate,
            created_at=datetime.utcnow(),
        )

    async def recommend_festivals(
        self, user_id: str, limit: int = 10
    ) -> List[FestivalRecommendation]:
        """
        Recommend festivals based on user preferences.

        Args:
            user_id: User identifier
            limit: Maximum number of recommendations

        Returns:
            List of festival recommendations sorted by similarity score
        """
        user_profile = await self.analyze_user_preferences(user_id)

        # Get upcoming festivals (within next year)
        cutoff_date = datetime.utcnow() + timedelta(days=365)
        festivals = (
            self.db.query(Festival)
            .filter(
                Festival.dates.any(lambda d: d > datetime.utcnow() and d < cutoff_date)
            )
            .all()
        )

        recommendations = []

        for festival in festivals:
            similarity_score = await self._calculate_festival_similarity(
                festival, user_profile
            )

            if similarity_score > 0.1:  # Only recommend festivals with some similarity
                matching_artists, recommended_artists = (
                    await self._analyze_festival_artists(festival, user_profile)
                )

                recommendations.append(
                    FestivalRecommendation(
                        festival_id=str(festival.id),
                        festival_name=festival.name,
                        similarity_score=similarity_score,
                        matching_artists=matching_artists,
                        recommended_artists=recommended_artists,
                        dates=festival.dates,
                        location=festival.location,
                    )
                )

        # Sort by similarity score and return top recommendations
        recommendations.sort(key=lambda x: x.similarity_score, reverse=True)
        return recommendations[:limit]

    async def recommend_artists(
        self, festival_id: str, user_id: str, limit: int = 10
    ) -> List[ArtistRecommendation]:
        """
        Recommend artists from a festival lineup based on user preferences.

        Args:
            festival_id: Festival identifier
            user_id: User identifier
            limit: Maximum number of recommendations

        Returns:
            List of artist recommendations sorted by similarity score
        """
        user_profile = await self.analyze_user_preferences(user_id)

        festival = self.db.query(Festival).filter(Festival.id == festival_id).first()
        if not festival:
            raise ValueError(f"Festival {festival_id} not found")

        recommendations = []

        # Get artists from festival lineup
        festival_artists = (
            self.db.query(Artist).filter(Artist.name.in_(festival.artists)).all()
        )

        for artist in festival_artists:
            # Skip artists user already knows well
            if str(artist.id) in user_profile.preferred_artists:
                continue

            similarity_score = await self._calculate_artist_similarity(
                artist, user_profile
            )

            if similarity_score > 0.1:  # Only recommend artists with some similarity
                recommendations.append(
                    ArtistRecommendation(
                        artist_id=str(artist.id),
                        artist_name=artist.name,
                        similarity_score=similarity_score,
                        genres=artist.genres or [],
                        popularity_score=artist.popularity_score,
                    )
                )

        # Sort by similarity score and return top recommendations
        recommendations.sort(key=lambda x: x.similarity_score, reverse=True)
        return recommendations[:limit]

    async def calculate_similarity_scores(
        self, profile: UserProfile, items: List
    ) -> Dict[str, float]:
        """
        Calculate similarity scores between user profile and a list of items.

        Args:
            profile: User preference profile
            items: List of items to score (festivals or artists)

        Returns:
            Dictionary mapping item IDs to similarity scores
        """
        scores = {}

        for item in items:
            if hasattr(item, "genres") and item.genres:
                # Calculate genre similarity
                genre_similarity = self._calculate_genre_similarity(
                    item.genres, profile.preferred_genres
                )
                scores[str(item.id)] = genre_similarity
            else:
                scores[str(item.id)] = 0.0

        return scores

    async def _calculate_festival_similarity(
        self, festival: Festival, user_profile: UserProfile
    ) -> float:
        """Calculate similarity score between festival and user profile."""
        if not festival.artists:
            return 0.0

        # Get artists from festival
        festival_artists = (
            self.db.query(Artist).filter(Artist.name.in_(festival.artists)).all()
        )

        if not festival_artists:
            return 0.0

        # Calculate genre overlap
        festival_genres = []
        for artist in festival_artists:
            if artist.genres:
                festival_genres.extend(artist.genres)

        genre_similarity = self._calculate_genre_similarity(
            festival_genres, user_profile.preferred_genres
        )

        # Calculate artist overlap
        artist_similarity = 0.0
        for artist in festival_artists:
            if str(artist.id) in user_profile.preferred_artists:
                artist_similarity += user_profile.preferred_artists[str(artist.id)]

        artist_similarity = min(artist_similarity / len(festival_artists), 1.0)

        # Combine scores (weighted average)
        return 0.7 * genre_similarity + 0.3 * artist_similarity

    async def _calculate_artist_similarity(
        self, artist: Artist, user_profile: UserProfile
    ) -> float:
        """Calculate similarity score between artist and user profile."""
        if not artist.genres:
            return 0.0

        return self._calculate_genre_similarity(
            artist.genres, user_profile.preferred_genres
        )

    def _calculate_genre_similarity(
        self, item_genres: List[str], user_genres: Dict[str, float]
    ) -> float:
        """Calculate cosine similarity between item genres and user genre preferences."""
        if not item_genres or not user_genres:
            return 0.0

        # Create genre vectors
        all_genres = set(item_genres) | set(user_genres.keys())

        item_vector = [1.0 if genre in item_genres else 0.0 for genre in all_genres]
        user_vector = [user_genres.get(genre, 0.0) for genre in all_genres]

        # Calculate cosine similarity
        dot_product = sum(a * b for a, b in zip(item_vector, user_vector))
        item_magnitude = math.sqrt(sum(a * a for a in item_vector))
        user_magnitude = math.sqrt(sum(b * b for b in user_vector))

        if item_magnitude == 0 or user_magnitude == 0:
            return 0.0

        return dot_product / (item_magnitude * user_magnitude)

    async def _analyze_festival_artists(
        self, festival: Festival, user_profile: UserProfile
    ) -> Tuple[List[str], List[str]]:
        """Analyze festival artists to identify matching and recommended artists."""
        if not festival.artists:
            return [], []

        festival_artists = (
            self.db.query(Artist).filter(Artist.name.in_(festival.artists)).all()
        )

        matching_artists = []
        recommended_artists = []

        for artist in festival_artists:
            if str(artist.id) in user_profile.preferred_artists:
                matching_artists.append(artist.name)
            else:
                similarity = await self._calculate_artist_similarity(
                    artist, user_profile
                )
                if similarity > 0.3:  # Threshold for recommendations
                    recommended_artists.append(artist.name)

        return matching_artists, recommended_artists[:5]  # Limit recommended artists
