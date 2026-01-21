"""Playlist Generator Service for creating ranked playlists based on setlist analysis."""

import logging
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime
from uuid import UUID, uuid4

from festival_playlist_generator.schemas.playlist import PlaylistCreate, Playlist
from festival_playlist_generator.schemas.song import SongCreate, Song
from festival_playlist_generator.models.playlist import Playlist as PlaylistModel
from festival_playlist_generator.models.song import Song as SongModel
from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.models.festival import Festival as FestivalModel
from festival_playlist_generator.models.user import User as UserModel
from festival_playlist_generator.services.artist_analyzer import ArtistAnalyzerService
from festival_playlist_generator.core.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

logger = logging.getLogger(__name__)


class PlaylistGeneratorService:
    """Main service for generating playlists based on setlist analysis."""
    
    def __init__(self, setlist_fm_api_key: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.PlaylistGeneratorService")
        self.artist_analyzer = ArtistAnalyzerService(setlist_fm_api_key)
    
    async def generate_artist_playlist(self, artist_id: UUID, user_id: UUID, limit: int = 10) -> Optional[Playlist]:
        """
        Generate a playlist for a single artist based on their recent setlists.
        
        Args:
            artist_id: UUID of the artist
            user_id: UUID of the user creating the playlist
            limit: Maximum number of setlists to analyze
            
        Returns:
            Generated Playlist object or None if failed
        """
        self.logger.info(f"Generating playlist for artist {artist_id}, user {user_id}")
        
        try:
            db = next(get_db())
            
            # Get artist information
            artist = db.query(ArtistModel).filter(ArtistModel.id == artist_id).first()
            if not artist:
                self.logger.error(f"Artist not found: {artist_id}")
                db.close()
                return None
            
            # Get user information
            user = db.query(UserModel).filter(UserModel.id == user_id).first()
            if not user:
                self.logger.error(f"User not found: {user_id}")
                db.close()
                return None
            
            # Get recent setlists for the artist
            setlists = await self.artist_analyzer.get_artist_setlists(artist.name, limit)
            
            if not setlists:
                self.logger.warning(f"No setlists found for artist: {artist.name}")
                db.close()
                return None
            
            # Analyze song frequency
            song_frequency = await self.artist_analyzer.analyze_song_frequency(setlists)
            
            if not song_frequency:
                self.logger.warning(f"No songs found in setlists for artist: {artist.name}")
                db.close()
                return None
            
            # Rank songs by frequency
            ranked_songs = self.rank_songs_by_frequency(song_frequency)
            
            # Create or find songs in database
            song_objects = await self._create_or_find_songs(ranked_songs, artist.name, db)
            
            # Create playlist
            playlist_name = f"{artist.name} - Live Setlist Playlist"
            playlist_description = f"Playlist based on {artist.name}'s most frequently played songs from their last {len(setlists)} concerts"
            
            playlist_create = PlaylistCreate(
                name=playlist_name,
                description=playlist_description,
                artist_id=artist_id,
                user_id=user_id,
                song_ids=[song.id for song in song_objects]
            )
            
            playlist = await self._create_playlist(playlist_create, song_objects, db)
            
            db.close()
            
            self.logger.info(f"Successfully generated playlist for artist {artist.name} with {len(song_objects)} songs")
            return playlist
            
        except Exception as e:
            self.logger.error(f"Error generating artist playlist: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
            return None
    
    async def generate_festival_playlist(self, festival_id: UUID, user_id: UUID, limit: int = 10) -> Optional[Playlist]:
        """
        Generate a comprehensive playlist for a festival based on all artists' setlists.
        
        Args:
            festival_id: UUID of the festival
            user_id: UUID of the user creating the playlist
            limit: Maximum number of setlists per artist to analyze
            
        Returns:
            Generated Playlist object or None if failed
        """
        self.logger.info(f"Generating festival playlist for festival {festival_id}, user {user_id}")
        
        try:
            db = next(get_db())
            
            # Get festival information
            festival = db.query(FestivalModel).filter(FestivalModel.id == festival_id).first()
            if not festival:
                self.logger.error(f"Festival not found: {festival_id}")
                db.close()
                return None
            
            # Get user information
            user = db.query(UserModel).filter(UserModel.id == user_id).first()
            if not user:
                self.logger.error(f"User not found: {user_id}")
                db.close()
                return None
            
            # Get all artists for the festival
            artists = festival.artists
            if not artists:
                self.logger.warning(f"No artists found for festival: {festival.name}")
                db.close()
                return None
            
            # Collect setlists for all artists
            all_song_frequency = {}
            artist_song_mapping = {}  # Track which artist performs each song
            processed_artists = 0
            
            for artist in artists:
                try:
                    # Get setlists for this artist
                    setlists = await self.artist_analyzer.get_artist_setlists(artist.name, limit)
                    
                    if not setlists:
                        self.logger.debug(f"No setlists found for artist: {artist.name}")
                        continue
                    
                    # Analyze song frequency for this artist
                    artist_song_frequency = await self.artist_analyzer.analyze_song_frequency(setlists)
                    
                    if not artist_song_frequency:
                        self.logger.debug(f"No songs found for artist: {artist.name}")
                        continue
                    
                    # Merge with overall frequency data
                    for song_title, frequency in artist_song_frequency.items():
                        # Normalize song title for cross-artist deduplication
                        normalized_titles = await self.artist_analyzer.normalize_song_titles([song_title])
                        normalized_title = normalized_titles[0] if normalized_titles else song_title.lower().strip()
                        
                        if normalized_title in all_song_frequency:
                            # Song already exists, add to frequency
                            all_song_frequency[normalized_title]['frequency'] += frequency
                            # Track multiple artists performing the same song
                            if artist.name not in all_song_frequency[normalized_title]['artists']:
                                all_song_frequency[normalized_title]['artists'].append(artist.name)
                        else:
                            # New song
                            all_song_frequency[normalized_title] = {
                                'original_title': song_title,
                                'frequency': frequency,
                                'artists': [artist.name],
                                'primary_artist': artist.name  # First artist we found performing this song
                            }
                        
                        # Track artist-song mapping for attribution
                        if normalized_title not in artist_song_mapping:
                            artist_song_mapping[normalized_title] = []
                        if artist.name not in artist_song_mapping[normalized_title]:
                            artist_song_mapping[normalized_title].append(artist.name)
                    
                    processed_artists += 1
                    self.logger.debug(f"Processed setlists for artist: {artist.name}")
                    
                except Exception as e:
                    self.logger.warning(f"Error processing artist {artist.name}: {e}")
                    continue
            
            if not all_song_frequency:
                self.logger.warning(f"No songs found for any artists in festival: {festival.name}")
                db.close()
                return None
            
            # Rank songs by total frequency across all artists
            ranked_songs = self.rank_songs_by_frequency(
                {data['original_title']: data['frequency'] for data in all_song_frequency.values()}
            )
            
            # Create or find songs in database with proper artist attribution
            song_objects = await self._create_or_find_festival_songs(
                ranked_songs, all_song_frequency, artist_song_mapping, db
            )
            
            # Create playlist
            playlist_name = f"{festival.name} - Festival Playlist"
            playlist_description = (
                f"Comprehensive playlist for {festival.name} featuring the most frequently "
                f"played songs from {processed_artists} festival artists"
            )
            
            playlist_create = PlaylistCreate(
                name=playlist_name,
                description=playlist_description,
                festival_id=festival_id,
                user_id=user_id,
                song_ids=[song.id for song in song_objects]
            )
            
            playlist = await self._create_playlist(playlist_create, song_objects, db)
            
            db.close()
            
            self.logger.info(
                f"Successfully generated festival playlist for {festival.name} with "
                f"{len(song_objects)} songs from {processed_artists} artists"
            )
            return playlist
            
        except Exception as e:
            self.logger.error(f"Error generating festival playlist: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
            return None
    
    def rank_songs_by_frequency(self, songs: Dict[str, int]) -> List[Tuple[str, int]]:
        """
        Rank songs by performance frequency.
        
        Args:
            songs: Dictionary mapping song titles to frequency counts
            
        Returns:
            List of (song_title, frequency) tuples sorted by frequency (descending)
        """
        if not songs:
            return []
        
        # Sort by frequency (descending), then by song title (ascending) for consistent ordering
        ranked = sorted(
            songs.items(),
            key=lambda x: (-x[1], x[0])  # Negative frequency for descending, title for tie-breaking
        )
        
        self.logger.debug(f"Ranked {len(ranked)} songs by frequency")
        return ranked
    
    async def check_existing_playlist(self, festival_id: Optional[UUID] = None, 
                                    artist_id: Optional[UUID] = None, 
                                    user_id: Optional[UUID] = None) -> Optional[Playlist]:
        """
        Check if a playlist already exists for the given parameters.
        
        Args:
            festival_id: Festival ID (optional)
            artist_id: Artist ID (optional)
            user_id: User ID (optional)
            
        Returns:
            Existing Playlist object or None if not found
        """
        try:
            db = next(get_db())
            
            query = db.query(PlaylistModel)
            
            # Build query conditions
            conditions = []
            if festival_id:
                conditions.append(PlaylistModel.festival_id == festival_id)
            if artist_id:
                conditions.append(PlaylistModel.artist_id == artist_id)
            if user_id:
                conditions.append(PlaylistModel.user_id == user_id)
            
            if not conditions:
                db.close()
                return None
            
            # Apply all conditions
            for condition in conditions:
                query = query.filter(condition)
            
            playlist_model = query.first()
            
            if playlist_model:
                # Convert to Pydantic model
                playlist = Playlist(
                    id=playlist_model.id,
                    name=playlist_model.name,
                    description=playlist_model.description,
                    festival_id=playlist_model.festival_id,
                    artist_id=playlist_model.artist_id,
                    user_id=playlist_model.user_id,
                    platform=playlist_model.platform,
                    external_id=playlist_model.external_id,
                    created_at=playlist_model.created_at,
                    updated_at=playlist_model.updated_at
                )
                
                db.close()
                return playlist
            
            db.close()
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking existing playlist: {e}")
            if 'db' in locals():
                db.close()
            return None
    
    async def update_playlist(self, playlist_id: UUID, new_songs: List[Song], 
                            preserve_user_preferences: bool = True) -> Optional[Playlist]:
        """
        Update an existing playlist with new songs while preserving user customizations.
        
        Args:
            playlist_id: UUID of the playlist to update
            new_songs: List of new Song objects
            preserve_user_preferences: Whether to preserve user song preferences
            
        Returns:
            Updated Playlist object or None if failed
        """
        self.logger.info(f"Updating playlist {playlist_id} with {len(new_songs)} songs")
        
        try:
            db = next(get_db())
            
            # Get existing playlist
            playlist_model = db.query(PlaylistModel).filter(PlaylistModel.id == playlist_id).first()
            if not playlist_model:
                self.logger.error(f"Playlist not found: {playlist_id}")
                db.close()
                return None
            
            # Get current songs if preserving preferences
            current_song_ids = set()
            if preserve_user_preferences:
                current_song_ids = {song.id for song in playlist_model.songs}
            
            # Get new song IDs
            new_song_ids = {song.id for song in new_songs}
            
            # Combine songs (preserve existing + add new)
            if preserve_user_preferences:
                # Keep existing songs and add new ones
                combined_song_ids = current_song_ids.union(new_song_ids)
            else:
                # Replace with new songs
                combined_song_ids = new_song_ids
            
            # Update playlist songs
            playlist_model.songs.clear()
            for song_id in combined_song_ids:
                song = db.query(SongModel).filter(SongModel.id == song_id).first()
                if song:
                    playlist_model.songs.append(song)
            
            # Update timestamp
            playlist_model.updated_at = datetime.utcnow()
            
            db.commit()
            
            # Convert to Pydantic model
            playlist = Playlist(
                id=playlist_model.id,
                name=playlist_model.name,
                description=playlist_model.description,
                festival_id=playlist_model.festival_id,
                artist_id=playlist_model.artist_id,
                user_id=playlist_model.user_id,
                platform=playlist_model.platform,
                external_id=playlist_model.external_id,
                created_at=playlist_model.created_at,
                updated_at=playlist_model.updated_at
            )
            
            db.close()
            
            self.logger.info(f"Successfully updated playlist {playlist_id}")
            return playlist
            
        except Exception as e:
            self.logger.error(f"Error updating playlist: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
            return None
    
    async def apply_user_preferences(self, playlist: Playlist, user_id: UUID) -> Playlist:
        """
        Apply user preferences to customize a playlist.
        
        Args:
            playlist: Playlist object to customize
            user_id: UUID of the user
            
        Returns:
            Customized Playlist object
        """
        # This is a placeholder for future user preference functionality
        # For now, just return the playlist as-is
        self.logger.debug(f"Applying user preferences for user {user_id} to playlist {playlist.id}")
        return playlist
    
    async def _create_or_find_songs(self, ranked_songs: List[Tuple[str, int]], 
                                  artist_name: str, db: Session) -> List[Song]:
        """Create or find songs in the database for a single artist."""
        song_objects = []
        
        for song_title, frequency in ranked_songs:
            # Check if song already exists
            normalized_titles = await self.artist_analyzer.normalize_song_titles([song_title])
            normalized_title = normalized_titles[0] if normalized_titles else song_title.lower().strip()
            
            existing_song = db.query(SongModel).filter(
                and_(
                    SongModel.normalized_title == normalized_title,
                    SongModel.artist == artist_name
                )
            ).first()
            
            if existing_song:
                # Update performance count
                existing_song.performance_count = max(existing_song.performance_count, frequency)
                song_objects.append(Song(
                    id=existing_song.id,
                    title=existing_song.title,
                    artist=existing_song.artist,
                    original_artist=existing_song.original_artist,
                    is_cover=existing_song.is_cover,
                    normalized_title=existing_song.normalized_title,
                    performance_count=existing_song.performance_count,
                    created_at=existing_song.created_at
                ))
            else:
                # Create new song
                # Check if it's a cover song
                covers = await self.artist_analyzer.identify_cover_songs([song_title], artist_name)
                is_cover = song_title in covers
                original_artist = covers.get(song_title) if is_cover else None
                
                song_model = SongModel(
                    title=song_title,
                    artist=artist_name,
                    original_artist=original_artist,
                    is_cover=is_cover,
                    normalized_title=normalized_title,
                    performance_count=frequency
                )
                db.add(song_model)
                db.flush()  # Get the ID
                
                song_objects.append(Song(
                    id=song_model.id,
                    title=song_model.title,
                    artist=song_model.artist,
                    original_artist=song_model.original_artist,
                    is_cover=song_model.is_cover,
                    normalized_title=song_model.normalized_title,
                    performance_count=song_model.performance_count,
                    created_at=song_model.created_at
                ))
        
        return song_objects
    
    async def _create_or_find_festival_songs(self, ranked_songs: List[Tuple[str, int]], 
                                           all_song_frequency: Dict[str, Dict], 
                                           artist_song_mapping: Dict[str, List[str]], 
                                           db: Session) -> List[Song]:
        """Create or find songs in the database for a festival with proper artist attribution."""
        song_objects = []
        
        for song_title, frequency in ranked_songs:
            # Get normalized title and artist info
            normalized_titles = await self.artist_analyzer.normalize_song_titles([song_title])
            normalized_title = normalized_titles[0] if normalized_titles else song_title.lower().strip()
            
            # Find the song data in our frequency mapping
            song_data = None
            for norm_title, data in all_song_frequency.items():
                if data['original_title'] == song_title:
                    song_data = data
                    break
            
            if not song_data:
                self.logger.warning(f"Could not find song data for: {song_title}")
                continue
            
            primary_artist = song_data['primary_artist']
            
            # Check if song already exists for the primary artist
            existing_song = db.query(SongModel).filter(
                and_(
                    SongModel.normalized_title == normalized_title,
                    SongModel.artist == primary_artist
                )
            ).first()
            
            if existing_song:
                # Update performance count
                existing_song.performance_count = max(existing_song.performance_count, frequency)
                song_objects.append(Song(
                    id=existing_song.id,
                    title=existing_song.title,
                    artist=existing_song.artist,
                    original_artist=existing_song.original_artist,
                    is_cover=existing_song.is_cover,
                    normalized_title=existing_song.normalized_title,
                    performance_count=existing_song.performance_count,
                    created_at=existing_song.created_at
                ))
            else:
                # Create new song with primary artist attribution
                # Check if it's a cover song
                covers = await self.artist_analyzer.identify_cover_songs([song_title], primary_artist)
                is_cover = song_title in covers
                original_artist = covers.get(song_title) if is_cover else None
                
                song_model = SongModel(
                    title=song_title,
                    artist=primary_artist,
                    original_artist=original_artist,
                    is_cover=is_cover,
                    normalized_title=normalized_title,
                    performance_count=frequency
                )
                db.add(song_model)
                db.flush()  # Get the ID
                
                song_objects.append(Song(
                    id=song_model.id,
                    title=song_model.title,
                    artist=song_model.artist,
                    original_artist=song_model.original_artist,
                    is_cover=song_model.is_cover,
                    normalized_title=song_model.normalized_title,
                    performance_count=song_model.performance_count,
                    created_at=song_model.created_at
                ))
        
        return song_objects
    
    async def _create_playlist(self, playlist_create: PlaylistCreate, 
                             song_objects: List[Song], db: Session) -> Playlist:
        """Create a new playlist in the database."""
        # Create playlist model
        playlist_model = PlaylistModel(
            name=playlist_create.name,
            description=playlist_create.description,
            festival_id=playlist_create.festival_id,
            artist_id=playlist_create.artist_id,
            user_id=playlist_create.user_id,
            platform=playlist_create.platform,
            external_id=playlist_create.external_id
        )
        db.add(playlist_model)
        db.flush()  # Get the ID
        
        # Add songs to playlist
        for song in song_objects:
            song_model = db.query(SongModel).filter(SongModel.id == song.id).first()
            if song_model:
                playlist_model.songs.append(song_model)
        
        db.commit()
        
        # Convert to Pydantic model
        playlist = Playlist(
            id=playlist_model.id,
            name=playlist_model.name,
            description=playlist_model.description,
            festival_id=playlist_model.festival_id,
            artist_id=playlist_model.artist_id,
            user_id=playlist_model.user_id,
            platform=playlist_model.platform,
            external_id=playlist_model.external_id,
            created_at=playlist_model.created_at,
            updated_at=playlist_model.updated_at
        )
        
        return playlist