"""Playlist update background tasks."""

from celery import current_task
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID

from festival_playlist_generator.core.celery_app import celery_app
from festival_playlist_generator.services.playlist_generator import PlaylistGeneratorService
from festival_playlist_generator.services.artist_analyzer import ArtistAnalyzerService
from festival_playlist_generator.models.playlist import Playlist as PlaylistModel
from festival_playlist_generator.models.user import UserSongPreference
from festival_playlist_generator.models.song import Song as SongModel
from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.models.festival import Festival as FestivalModel
from festival_playlist_generator.core.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=1800)  # 30 minutes
def update_all_playlists(self, days_since_update: int = 7):
    """
    Update all playlists with new setlist data while preserving user customizations.
    
    Args:
        days_since_update: Only update playlists older than this many days
    
    This task:
    1. Finds playlists that need updating (older than specified days)
    2. Fetches new setlist data for artists in those playlists
    3. Updates playlist content with new songs
    4. Preserves user customizations (known/unknown song preferences)
    5. Handles errors gracefully with retry logic
    
    Validates: Requirements 6.3, 6.4
    """
    try:
        logger.info(f"Starting playlist update task for playlists older than {days_since_update} days")
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Finding playlists to update', 'progress': 10}
        )
        
        # Initialize services
        playlist_generator = PlaylistGeneratorService()
        artist_analyzer = ArtistAnalyzerService()
        
        # Get database session
        db = next(get_db())
        
        try:
            # Find playlists that need updating
            cutoff_date = datetime.utcnow() - timedelta(days=days_since_update)
            playlists_to_update = db.query(PlaylistModel).filter(
                or_(
                    PlaylistModel.updated_at < cutoff_date,
                    PlaylistModel.updated_at.is_(None)  # Handle playlists never updated
                )
            ).all()
            
            if not playlists_to_update:
                logger.info("No playlists found that need updating")
                db.close()
                return {
                    "status": "success",
                    "message": "No playlists needed updating",
                    "playlists_checked": 0,
                    "playlists_updated": 0,
                    "completed_at": datetime.utcnow().isoformat()
                }
            
            logger.info(f"Found {len(playlists_to_update)} playlists to update")
            
            self.update_state(
                state='PROGRESS',
                meta={
                    'status': f'Updating {len(playlists_to_update)} playlists',
                    'progress': 20,
                    'playlists_found': len(playlists_to_update)
                }
            )
            
            # Track update results
            updated_count = 0
            failed_count = 0
            skipped_count = 0
            update_results = []
            
            for i, playlist in enumerate(playlists_to_update):
                try:
                    # Update progress
                    progress = 20 + (i / len(playlists_to_update)) * 70  # 20-90%
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'status': f'Updating playlist: {playlist.name}',
                            'progress': int(progress),
                            'current_playlist': playlist.name,
                            'updated_count': updated_count,
                            'failed_count': failed_count
                        }
                    )
                    
                    # Update individual playlist
                    result = asyncio.run(update_single_playlist(
                        playlist.id, playlist_generator, artist_analyzer, db
                    ))
                    
                    if result['status'] == 'success':
                        updated_count += 1
                        logger.info(f"Successfully updated playlist: {playlist.name}")
                    elif result['status'] == 'skipped':
                        skipped_count += 1
                        logger.info(f"Skipped playlist: {playlist.name} - {result['reason']}")
                    else:
                        failed_count += 1
                        logger.warning(f"Failed to update playlist: {playlist.name} - {result['error']}")
                    
                    update_results.append({
                        'playlist_id': str(playlist.id),
                        'playlist_name': playlist.name,
                        'status': result['status'],
                        'message': result.get('message', result.get('error', result.get('reason', ''))),
                        'songs_added': result.get('songs_added', 0),
                        'songs_total': result.get('songs_total', 0)
                    })
                    
                except Exception as e:
                    failed_count += 1
                    error_msg = f"Error updating playlist {playlist.name}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    
                    update_results.append({
                        'playlist_id': str(playlist.id),
                        'playlist_name': playlist.name,
                        'status': 'failed',
                        'message': error_msg,
                        'songs_added': 0,
                        'songs_total': 0
                    })
            
            # Final results
            total_processed = updated_count + failed_count + skipped_count
            
            self.update_state(
                state='SUCCESS',
                meta={
                    'status': 'Playlist updates completed',
                    'progress': 100,
                    'updated_count': updated_count,
                    'failed_count': failed_count,
                    'skipped_count': skipped_count
                }
            )
            
            result = {
                "status": "success",
                "message": f"Playlist update completed. Updated: {updated_count}, Failed: {failed_count}, Skipped: {skipped_count}",
                "playlists_checked": len(playlists_to_update),
                "playlists_updated": updated_count,
                "playlists_failed": failed_count,
                "playlists_skipped": skipped_count,
                "update_results": update_results[:20],  # Limit to first 20 for brevity
                "completed_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Playlist update task completed. Updated: {updated_count}, Failed: {failed_count}, Skipped: {skipped_count}")
            
            db.close()
            return result
            
        except Exception as e:
            db.rollback()
            db.close()
            raise
            
    except Exception as e:
        error_msg = f"Error in playlist update task: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Update task state with error
        self.update_state(
            state='FAILURE',
            meta={'status': 'Playlist update failed', 'error': error_msg}
        )
        
        # Retry with exponential backoff
        try:
            # Calculate retry delay with exponential backoff
            retry_delay = min(1800 * (2 ** self.request.retries), 7200)  # Max 2 hours
            
            logger.info(f"Retrying playlist update in {retry_delay} seconds (attempt {self.request.retries + 1}/{self.max_retries})")
            
            self.retry(countdown=retry_delay, exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for playlist update task")
            return {
                "status": "failed",
                "message": f"Playlist update failed after {self.max_retries} retries: {error_msg}",
                "error": error_msg,
                "failed_at": datetime.utcnow().isoformat()
            }


@celery_app.task(bind=True, max_retries=2, default_retry_delay=600)
def update_single_playlist_task(self, playlist_id: str):
    """
    Update a single playlist with new setlist data.
    
    Args:
        playlist_id: UUID string of the playlist to update
    
    This task can be called individually to update specific playlists.
    """
    try:
        logger.info(f"Starting update for playlist {playlist_id}")
        
        # Initialize services
        playlist_generator = PlaylistGeneratorService()
        artist_analyzer = ArtistAnalyzerService()
        
        # Get database session
        db = next(get_db())
        
        try:
            # Update the playlist
            result = asyncio.run(update_single_playlist(
                UUID(playlist_id), playlist_generator, artist_analyzer, db
            ))
            
            db.close()
            
            logger.info(f"Single playlist update completed for {playlist_id}: {result['status']}")
            return result
            
        except Exception as e:
            db.rollback()
            db.close()
            raise
            
    except Exception as e:
        error_msg = f"Error updating single playlist {playlist_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Retry with backoff
        try:
            retry_delay = 600 * (2 ** self.request.retries)  # 10 min, 20 min
            self.retry(countdown=retry_delay, exc=e)
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "playlist_id": playlist_id,
                "error": error_msg,
                "failed_at": datetime.utcnow().isoformat()
            }


async def update_single_playlist(playlist_id: UUID, playlist_generator: PlaylistGeneratorService,
                               artist_analyzer: ArtistAnalyzerService, db: Session) -> Dict[str, Any]:
    """
    Update a single playlist with new setlist data while preserving user customizations.
    
    Args:
        playlist_id: UUID of the playlist to update
        playlist_generator: Playlist generator service instance
        artist_analyzer: Artist analyzer service instance
        db: Database session
        
    Returns:
        Dictionary with update results
    """
    try:
        # Get playlist
        playlist = db.query(PlaylistModel).filter(PlaylistModel.id == playlist_id).first()
        if not playlist:
            return {
                "status": "failed",
                "error": f"Playlist not found: {playlist_id}"
            }
        
        logger.debug(f"Updating playlist: {playlist.name}")
        
        # Get user song preferences for this playlist
        user_preferences = {}
        if playlist.user_id:
            preferences = db.query(UserSongPreference).filter(
                UserSongPreference.user_id == playlist.user_id
            ).all()
            user_preferences = {pref.song_id: pref.is_known for pref in preferences}
        
        # Store current songs for comparison
        current_songs = {song.id: song for song in playlist.songs}
        current_song_count = len(current_songs)
        
        # Generate new playlist content based on type
        new_songs = []
        
        if playlist.festival_id:
            # Festival playlist - regenerate with latest setlist data
            logger.debug(f"Updating festival playlist for festival {playlist.festival_id}")
            
            # Get festival
            festival = db.query(FestivalModel).filter(FestivalModel.id == playlist.festival_id).first()
            if not festival:
                return {
                    "status": "failed",
                    "error": f"Festival not found: {playlist.festival_id}"
                }
            
            # Check if festival is still upcoming or recent (within 30 days)
            if festival.dates:
                latest_date = max(festival.dates)
                days_since_festival = (datetime.utcnow() - latest_date).days
                
                if days_since_festival > 30:
                    return {
                        "status": "skipped",
                        "reason": f"Festival is too old ({days_since_festival} days ago), skipping update"
                    }
            
            # Generate new festival playlist
            new_playlist = await playlist_generator.generate_festival_playlist(
                playlist.festival_id, playlist.user_id, limit=10
            )
            
            if new_playlist and hasattr(new_playlist, 'songs'):
                # Get song objects from the new playlist
                new_song_ids = getattr(new_playlist, 'song_ids', [])
                if new_song_ids:
                    new_songs = db.query(SongModel).filter(SongModel.id.in_(new_song_ids)).all()
            
        elif playlist.artist_id:
            # Artist playlist - regenerate with latest setlist data
            logger.debug(f"Updating artist playlist for artist {playlist.artist_id}")
            
            # Generate new artist playlist
            new_playlist = await playlist_generator.generate_artist_playlist(
                playlist.artist_id, playlist.user_id, limit=10
            )
            
            if new_playlist and hasattr(new_playlist, 'songs'):
                # Get song objects from the new playlist
                new_song_ids = getattr(new_playlist, 'song_ids', [])
                if new_song_ids:
                    new_songs = db.query(SongModel).filter(SongModel.id.in_(new_song_ids)).all()
        
        else:
            return {
                "status": "skipped",
                "reason": "Playlist has no associated festival or artist"
            }
        
        if not new_songs:
            return {
                "status": "skipped",
                "reason": "No new songs found to update playlist"
            }
        
        # Preserve user customizations by combining current and new songs
        # Keep songs that user has marked as known, add new songs
        preserved_songs = []
        new_song_additions = []
        
        # Keep existing songs that user has interacted with (marked as known)
        for song_id, song in current_songs.items():
            if song_id in user_preferences and user_preferences[song_id]:
                # User marked this song as known, preserve it
                preserved_songs.append(song)
        
        # Add new songs that aren't already in the playlist
        new_song_ids = {song.id for song in new_songs}
        current_song_ids = set(current_songs.keys())
        
        for song in new_songs:
            if song.id not in current_song_ids:
                new_song_additions.append(song)
        
        # Combine preserved and new songs
        updated_songs = preserved_songs + new_song_additions
        
        # Update playlist songs
        playlist.songs.clear()
        for song in updated_songs:
            playlist.songs.append(song)
        
        # Update timestamp
        playlist.updated_at = datetime.utcnow()
        
        # Commit changes
        db.commit()
        
        songs_added = len(new_song_additions)
        songs_preserved = len(preserved_songs)
        songs_total = len(updated_songs)
        
        logger.debug(
            f"Updated playlist {playlist.name}: "
            f"Added {songs_added} new songs, preserved {songs_preserved} user songs, "
            f"total {songs_total} songs"
        )
        
        return {
            "status": "success",
            "message": f"Updated playlist with {songs_added} new songs",
            "songs_added": songs_added,
            "songs_preserved": songs_preserved,
            "songs_total": songs_total,
            "previous_song_count": current_song_count
        }
        
    except Exception as e:
        logger.error(f"Error updating playlist {playlist_id}: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e)
        }


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def update_playlists_for_festival(self, festival_id: str):
    """
    Update all playlists associated with a specific festival.
    
    Args:
        festival_id: UUID string of the festival
    
    This task is useful when a festival lineup changes or new setlist data becomes available.
    """
    try:
        logger.info(f"Starting playlist updates for festival {festival_id}")
        
        # Initialize services
        playlist_generator = PlaylistGeneratorService()
        artist_analyzer = ArtistAnalyzerService()
        
        # Get database session
        db = next(get_db())
        
        try:
            # Find all playlists for this festival
            playlists = db.query(PlaylistModel).filter(
                PlaylistModel.festival_id == UUID(festival_id)
            ).all()
            
            if not playlists:
                db.close()
                return {
                    "status": "success",
                    "message": f"No playlists found for festival {festival_id}",
                    "playlists_updated": 0
                }
            
            logger.info(f"Found {len(playlists)} playlists to update for festival {festival_id}")
            
            # Update each playlist
            updated_count = 0
            failed_count = 0
            results = []
            
            for playlist in playlists:
                try:
                    result = asyncio.run(update_single_playlist(
                        playlist.id, playlist_generator, artist_analyzer, db
                    ))
                    
                    if result['status'] == 'success':
                        updated_count += 1
                    else:
                        failed_count += 1
                    
                    results.append({
                        'playlist_id': str(playlist.id),
                        'playlist_name': playlist.name,
                        'status': result['status'],
                        'message': result.get('message', result.get('error', ''))
                    })
                    
                except Exception as e:
                    failed_count += 1
                    error_msg = f"Error updating playlist {playlist.name}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    
                    results.append({
                        'playlist_id': str(playlist.id),
                        'playlist_name': playlist.name,
                        'status': 'failed',
                        'message': error_msg
                    })
            
            db.close()
            
            result = {
                "status": "success",
                "message": f"Festival playlist update completed. Updated: {updated_count}, Failed: {failed_count}",
                "festival_id": festival_id,
                "playlists_updated": updated_count,
                "playlists_failed": failed_count,
                "results": results,
                "completed_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Festival playlist update completed for {festival_id}: {updated_count} updated, {failed_count} failed")
            return result
            
        except Exception as e:
            db.rollback()
            db.close()
            raise
            
    except Exception as e:
        error_msg = f"Error updating playlists for festival {festival_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Retry with backoff
        try:
            retry_delay = 300 * (2 ** self.request.retries)  # 5 min, 10 min
            self.retry(countdown=retry_delay, exc=e)
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "festival_id": festival_id,
                "error": error_msg,
                "failed_at": datetime.utcnow().isoformat()
            }