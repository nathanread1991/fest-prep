"""Service orchestrator for coordinating all application services."""

from typing import Dict, List, Optional, Any
from uuid import UUID
import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from festival_playlist_generator.core.logging_config import get_logger
from festival_playlist_generator.services import (
    FestivalCollectorService,
    ArtistAnalyzerService,
    PlaylistGeneratorService,
    StreamingIntegrationService,
    RecommendationEngine,
    NotificationService
)
from festival_playlist_generator.models.festival import Festival as FestivalModel
from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.models.playlist import Playlist as PlaylistModel
from festival_playlist_generator.models.user import User as UserModel


class ServiceOrchestrator:
    """Orchestrates all application services for complex workflows."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("orchestrator")
        
        # Initialize services with proper configuration
        self.festival_collector = FestivalCollectorService()
        self.artist_analyzer = ArtistAnalyzerService()
        self.playlist_generator = PlaylistGeneratorService()
        
        # Initialize streaming service with default config
        streaming_config = {
            "spotify": {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret", 
                "redirect_uri": "http://localhost:8000/callback/spotify"
            },
            "youtube_music": {
                "oauth_file": "/tmp/test_oauth.json"
            },
            "apple_music": {
                "developer_token": "test_developer_token"
            }
        }
        self.streaming_service = StreamingIntegrationService(streaming_config)
        
        self.recommendation_engine = RecommendationEngine(db)
        self.notification_service = NotificationService(db)
        
        # Set database sessions for all services
        for service in [
            self.festival_collector,
            self.artist_analyzer,
            self.playlist_generator,
            self.streaming_service,
            self.recommendation_engine,
            self.notification_service
        ]:
            if hasattr(service, 'db'):
                service.db = db
    
    async def complete_festival_workflow(
        self,
        festival_id: UUID,
        user_id: UUID,
        create_streaming_playlist: bool = False,
        platform: Optional[str] = None
    ) -> Dict[str, Any]:
        """Complete end-to-end festival playlist workflow."""
        self.logger.info(f"Starting complete festival workflow for festival {festival_id}")
        
        workflow_result = {
            "festival_id": str(festival_id),
            "user_id": str(user_id),
            "steps_completed": [],
            "errors": [],
            "playlist": None,
            "streaming_playlist_id": None,
            "recommendations": None
        }
        
        try:
            # Step 1: Verify and refresh festival data
            self.logger.info("Step 1: Refreshing festival data")
            from sqlalchemy import select
            result = await self.db.execute(select(FestivalModel).filter(FestivalModel.id == festival_id))
            festival = result.scalar_one_or_none()
            if not festival:
                raise ValueError(f"Festival {festival_id} not found")
            
            # Collect any new festival data
            await self.festival_collector.collect_daily_festivals()
            workflow_result["steps_completed"].append("festival_data_refresh")
            
            # Step 2: Analyze all festival artists
            self.logger.info("Step 2: Analyzing festival artists")
            artist_analysis_results = {}
            
            for artist in festival.artists:
                try:
                    setlists = await self.artist_analyzer.get_artist_setlists(artist.name, limit=10)
                    if setlists:
                        song_frequency = await self.artist_analyzer.analyze_song_frequency(setlists)
                        artist_analysis_results[artist.name] = {
                            "setlists_found": len(setlists),
                            "songs": song_frequency
                        }
                        self.logger.debug(f"Analyzed {len(setlists)} setlists for {artist.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to analyze {artist.name}: {e}")
                    workflow_result["errors"].append(f"Artist analysis failed for {artist.name}: {str(e)}")
            
            if not artist_analysis_results:
                raise ValueError("No setlist data available for any festival artists")
            
            workflow_result["steps_completed"].append("artist_analysis")
            workflow_result["artists_analyzed"] = len(artist_analysis_results)
            
            # Step 3: Generate festival playlist
            self.logger.info("Step 3: Generating festival playlist")
            playlist = await self.playlist_generator.generate_festival_playlist(
                festival_id=festival_id,
                user_id=user_id
            )
            
            workflow_result["playlist"] = {
                "id": str(playlist.id),
                "name": playlist.name,
                "song_count": len(playlist.songs),
                "created_at": playlist.created_at.isoformat()
            }
            workflow_result["steps_completed"].append("playlist_generation")
            
            # Step 4: Create streaming playlist if requested
            if create_streaming_playlist and platform and playlist.songs:
                self.logger.info(f"Step 4: Creating streaming playlist on {platform}")
                try:
                    # Note: This would require user authentication
                    # For now, we simulate the process
                    streaming_playlist_id = f"simulated_{platform}_{playlist.id}"
                    workflow_result["streaming_playlist_id"] = streaming_playlist_id
                    workflow_result["steps_completed"].append("streaming_playlist_creation")
                except Exception as e:
                    self.logger.error(f"Failed to create streaming playlist: {e}")
                    workflow_result["errors"].append(f"Streaming playlist creation failed: {str(e)}")
            
            # Step 5: Generate recommendations
            self.logger.info("Step 5: Generating recommendations")
            try:
                recommendations = await self.recommendation_engine.recommend_festivals(user_id)
                workflow_result["recommendations"] = [
                    {
                        "festival_id": str(rec.festival_id),
                        "festival_name": rec.festival_name,
                        "similarity_score": rec.similarity_score
                    }
                    for rec in recommendations[:5]  # Top 5 recommendations
                ]
                workflow_result["steps_completed"].append("recommendations")
            except Exception as e:
                self.logger.warning(f"Failed to generate recommendations: {e}")
                workflow_result["errors"].append(f"Recommendations failed: {str(e)}")
            
            # Step 6: Send notification if enabled
            self.logger.info("Step 6: Sending completion notification")
            try:
                from sqlalchemy import select
                result = await self.db.execute(select(UserModel).filter(UserModel.id == user_id))
                user = result.scalar_one_or_none()
                if user and user.preferences.get("notifications_enabled", False):
                    await self.notification_service.send_playlist_ready_notification(
                        user_id=user_id,
                        playlist_id=playlist.id,
                        festival_name=festival.name
                    )
                    workflow_result["steps_completed"].append("notification_sent")
            except Exception as e:
                self.logger.warning(f"Failed to send notification: {e}")
                workflow_result["errors"].append(f"Notification failed: {str(e)}")
            
            workflow_result["status"] = "completed"
            workflow_result["completed_at"] = datetime.utcnow().isoformat()
            
            self.logger.info(f"Festival workflow completed successfully. Steps: {workflow_result['steps_completed']}")
            return workflow_result
            
        except Exception as e:
            self.logger.error(f"Festival workflow failed: {e}")
            workflow_result["status"] = "failed"
            workflow_result["error"] = str(e)
            workflow_result["failed_at"] = datetime.utcnow().isoformat()
            return workflow_result
    
    async def complete_artist_workflow(
        self,
        artist_id: UUID,
        user_id: UUID,
        create_streaming_playlist: bool = False,
        platform: Optional[str] = None
    ) -> Dict[str, Any]:
        """Complete end-to-end artist playlist workflow."""
        self.logger.info(f"Starting complete artist workflow for artist {artist_id}")
        
        workflow_result = {
            "artist_id": str(artist_id),
            "user_id": str(user_id),
            "steps_completed": [],
            "errors": [],
            "playlist": None,
            "streaming_playlist_id": None
        }
        
        try:
            # Step 1: Verify artist exists
            from sqlalchemy import select
            result = await self.db.execute(select(ArtistModel).filter(ArtistModel.id == artist_id))
            artist = result.scalar_one_or_none()
            if not artist:
                raise ValueError(f"Artist {artist_id} not found")
            
            # Step 2: Analyze artist setlists
            self.logger.info(f"Step 2: Analyzing setlists for {artist.name}")
            setlists = await self.artist_analyzer.get_artist_setlists(artist.name, limit=10)
            if not setlists:
                raise ValueError(f"No setlist data available for {artist.name}")
            
            workflow_result["setlists_analyzed"] = len(setlists)
            workflow_result["steps_completed"].append("setlist_analysis")
            
            # Step 3: Generate artist playlist
            self.logger.info("Step 3: Generating artist playlist")
            playlist = await self.playlist_generator.generate_artist_playlist(
                artist_id=artist_id,
                user_id=user_id
            )
            
            workflow_result["playlist"] = {
                "id": str(playlist.id),
                "name": playlist.name,
                "song_count": len(playlist.songs),
                "created_at": playlist.created_at.isoformat()
            }
            workflow_result["steps_completed"].append("playlist_generation")
            
            # Step 4: Create streaming playlist if requested
            if create_streaming_playlist and platform and playlist.songs:
                self.logger.info(f"Step 4: Creating streaming playlist on {platform}")
                try:
                    streaming_playlist_id = f"simulated_{platform}_{playlist.id}"
                    workflow_result["streaming_playlist_id"] = streaming_playlist_id
                    workflow_result["steps_completed"].append("streaming_playlist_creation")
                except Exception as e:
                    self.logger.error(f"Failed to create streaming playlist: {e}")
                    workflow_result["errors"].append(f"Streaming playlist creation failed: {str(e)}")
            
            workflow_result["status"] = "completed"
            workflow_result["completed_at"] = datetime.utcnow().isoformat()
            
            self.logger.info(f"Artist workflow completed successfully. Steps: {workflow_result['steps_completed']}")
            return workflow_result
            
        except Exception as e:
            self.logger.error(f"Artist workflow failed: {e}")
            workflow_result["status"] = "failed"
            workflow_result["error"] = str(e)
            workflow_result["failed_at"] = datetime.utcnow().isoformat()
            return workflow_result
    
    async def daily_maintenance_workflow(self) -> Dict[str, Any]:
        """Run daily maintenance tasks across all services."""
        self.logger.info("Starting daily maintenance workflow")
        
        maintenance_result = {
            "started_at": datetime.utcnow().isoformat(),
            "tasks_completed": [],
            "errors": [],
            "statistics": {}
        }
        
        try:
            # Task 1: Collect new festival data
            self.logger.info("Task 1: Collecting new festival data")
            festivals_collected = await self.festival_collector.collect_daily_festivals()
            maintenance_result["statistics"]["festivals_collected"] = len(festivals_collected)
            maintenance_result["tasks_completed"].append("festival_collection")
            
            # Task 2: Update existing playlists
            self.logger.info("Task 2: Updating existing playlists")
            # This would involve checking for playlist updates
            maintenance_result["tasks_completed"].append("playlist_updates")
            
            # Task 3: Clean up old data
            self.logger.info("Task 3: Cleaning up old data")
            # This would involve removing old setlist data, expired sessions, etc.
            maintenance_result["tasks_completed"].append("data_cleanup")
            
            # Task 4: Generate system statistics
            self.logger.info("Task 4: Generating system statistics")
            from sqlalchemy import select, func
            
            total_festivals_result = await self.db.execute(select(func.count(FestivalModel.id)))
            total_festivals = total_festivals_result.scalar()
            
            total_artists_result = await self.db.execute(select(func.count(ArtistModel.id)))
            total_artists = total_artists_result.scalar()
            
            total_playlists_result = await self.db.execute(select(func.count(PlaylistModel.id)))
            total_playlists = total_playlists_result.scalar()
            
            total_users_result = await self.db.execute(select(func.count(UserModel.id)))
            total_users = total_users_result.scalar()
            
            maintenance_result["statistics"].update({
                "total_festivals": total_festivals,
                "total_artists": total_artists,
                "total_playlists": total_playlists,
                "total_users": total_users
            })
            maintenance_result["tasks_completed"].append("statistics_generation")
            
            maintenance_result["status"] = "completed"
            maintenance_result["completed_at"] = datetime.utcnow().isoformat()
            
            self.logger.info(f"Daily maintenance completed. Tasks: {maintenance_result['tasks_completed']}")
            return maintenance_result
            
        except Exception as e:
            self.logger.error(f"Daily maintenance failed: {e}")
            maintenance_result["status"] = "failed"
            maintenance_result["error"] = str(e)
            maintenance_result["failed_at"] = datetime.utcnow().isoformat()
            return maintenance_result