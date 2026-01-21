"""Setlist Enrichment Service for automatic setlist data population."""

import logging
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.models.setlist import Setlist as SetlistModel
from festival_playlist_generator.services.artist_analyzer import ArtistAnalyzerService
from festival_playlist_generator.core.config import settings


logger = logging.getLogger(__name__)


class SetlistEnrichmentService:
    """Service for enriching artists with setlist data from Setlist.fm API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the setlist enrichment service.
        
        Args:
            api_key: Setlist.fm API key (defaults to settings.SETLIST_FM_API_KEY)
        """
        self.api_key = api_key or settings.SETLIST_FM_API_KEY
        self.logger = logging.getLogger(f"{__name__}.SetlistEnrichmentService")
        
        if not self.api_key:
            self.logger.warning("Setlist.fm API key not configured. Enrichment will be skipped.")
    
    async def enrich_artists(
        self, 
        artist_ids: List[str], 
        db: AsyncSession,
        limit: int = 10
    ) -> Dict[str, int]:
        """
        Enrich multiple artists with setlist data.
        
        Args:
            artist_ids: List of artist UUIDs to enrich
            db: Database session
            limit: Number of setlists to fetch per artist (default: 10)
            
        Returns:
            Dictionary with enrichment statistics:
            {
                "enriched": int,  # Artists successfully enriched
                "skipped": int,   # Artists already had setlists
                "failed": int,    # Artists that failed to enrich
                "total": int      # Total artists processed
            }
        """
        self.logger.info(f"Starting enrichment for {len(artist_ids)} artists")
        
        # Check if API key is configured
        if not self.api_key:
            self.logger.error("Setlist.fm API key not configured. Skipping enrichment.")
            return {
                "enriched": 0,
                "skipped": 0,
                "failed": len(artist_ids),
                "total": len(artist_ids)
            }
        
        stats = {
            "enriched": 0,
            "skipped": 0,
            "failed": 0,
            "total": len(artist_ids)
        }
        
        for artist_id in artist_ids:
            try:
                result = await self.enrich_artist_by_id(artist_id, db, limit)
                
                if result is None:
                    # Artist was skipped (already has setlists)
                    stats["skipped"] += 1
                elif result > 0:
                    # Artist was successfully enriched
                    stats["enriched"] += 1
                    self.logger.info(f"Enriched artist {artist_id} with {result} setlists")
                else:
                    # Enrichment failed (no setlists found or error)
                    stats["failed"] += 1
                    
            except Exception as e:
                self.logger.error(f"Error enriching artist {artist_id}: {e}")
                stats["failed"] += 1
        
        self.logger.info(
            f"Setlist enrichment complete: {stats['enriched']} enriched, "
            f"{stats['skipped']} skipped, {stats['failed']} failed"
        )
        
        return stats
    
    async def enrich_artist_by_id(
        self,
        artist_id: str,
        db: AsyncSession,
        limit: int = 10
    ) -> Optional[int]:
        """
        Enrich a single artist with setlist data.
        Falls back to Spotify top tracks if no setlist data is found.
        
        Args:
            artist_id: Artist UUID
            db: Database session
            limit: Number of setlists to fetch (default: 10)
            
        Returns:
            Number of setlists fetched, or None if artist was skipped (already has setlists)
        """
        try:
            # Get the artist from database
            result = await db.execute(
                select(ArtistModel).where(ArtistModel.id == artist_id)
            )
            artist = result.scalar_one_or_none()
            
            if not artist:
                self.logger.warning(f"Artist not found: {artist_id}")
                return 0
            
            # Check if artist already has setlists
            result = await db.execute(
                select(func.count(SetlistModel.id))
                .where(SetlistModel.artist_id == artist_id)
            )
            setlist_count = result.scalar()
            
            if setlist_count > 0:
                self.logger.info(
                    f"Artist {artist.name} already has {setlist_count} setlists, skipping"
                )
                return None
            
            # Fetch setlist data using ArtistAnalyzerService
            analyzer = ArtistAnalyzerService(setlist_fm_api_key=self.api_key)
            setlists = await analyzer.get_artist_setlists(artist.name, limit=limit)
            
            if not setlists:
                self.logger.warning(f"No setlist data found for artist {artist.name}, trying Spotify fallback")
                
                # Fallback to Spotify top tracks
                from festival_playlist_generator.services.spotify_artist_service import spotify_artist_service
                from datetime import datetime
                
                # Ensure artist has Spotify ID
                if not artist.spotify_id:
                    spotify_info = spotify_artist_service.search_artist(artist.name)
                    if spotify_info:
                        try:
                            artist.spotify_id = spotify_info.id
                            artist.spotify_image_url = spotify_info.medium_image_url
                            artist.spotify_popularity = spotify_info.popularity
                            artist.spotify_followers = spotify_info.followers
                            if spotify_info.genres and not artist.genres:
                                artist.genres = spotify_info.genres
                            await db.commit()
                        except Exception as e:
                            # Handle duplicate Spotify ID or other database errors
                            await db.rollback()
                            self.logger.warning(f"Could not update Spotify info for {artist.name}: {e}")
                            # Continue without Spotify info update
                
                # Get top tracks from Spotify
                if artist.spotify_id:
                    raw_tracks = spotify_artist_service.get_artist_top_tracks(artist.spotify_id)
                    
                    if raw_tracks:
                        # Create a synthetic setlist from Spotify top tracks
                        song_names = [track.get('name') for track in raw_tracks if track.get('name')]
                        
                        if song_names:
                            # Create a setlist entry with Spotify data
                            spotify_setlist = SetlistModel(
                                artist_id=artist.id,
                                venue="Spotify Top Tracks",
                                date=datetime.utcnow(),
                                songs=song_names,
                                tour_name=None,
                                festival_name=None,
                                source="spotify"
                            )
                            db.add(spotify_setlist)
                            await db.commit()
                            
                            self.logger.info(
                                f"Created Spotify fallback setlist for {artist.name} with {len(song_names)} tracks"
                            )
                            return 1  # Return 1 to indicate successful enrichment
                
                self.logger.warning(f"No data found for artist {artist.name} (neither setlists nor Spotify)")
                return 0
            
            self.logger.info(
                f"Successfully enriched artist {artist.name} with {len(setlists)} setlists"
            )
            return len(setlists)
            
        except Exception as e:
            self.logger.error(f"Error enriching artist {artist_id}: {e}")
            return 0


# Global service instance for import
setlist_enrichment_service = SetlistEnrichmentService()
