"""Playlist generation API endpoints that integrate all services."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.api.response_formatter import APIVersionManager
from festival_playlist_generator.api.versioning import (
    get_request_version,
    version_compatible_response,
)
from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.core.dependencies import (
    get_artist_analyzer,
    get_festival_collector,
    get_playlist_generator,
    get_recommendation_service,
    get_streaming_integration,
)
from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.models.festival import Festival as FestivalModel
from festival_playlist_generator.models.user import User as UserModel
from festival_playlist_generator.schemas.playlist import PlaylistCreate
from festival_playlist_generator.services import (
    ArtistAnalyzerService,
    FestivalCollectorService,
    PlaylistGeneratorService,
    RecommendationEngine,
    StreamingIntegrationService,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate/festival/{festival_id}")
async def generate_festival_playlist(
    request: Request,
    festival_id: UUID,
    user_id: UUID,
    platform: Optional[str] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    festival_collector: FestivalCollectorService = Depends(get_festival_collector),
    artist_analyzer: ArtistAnalyzerService = Depends(get_artist_analyzer),
    playlist_generator: PlaylistGeneratorService = Depends(get_playlist_generator),
    streaming_service: StreamingIntegrationService = Depends(get_streaming_integration),
):
    """Generate a comprehensive playlist for a festival using all services."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    try:
        # Verify festival exists
        result = await db.execute(
            select(FestivalModel).filter(FestivalModel.id == festival_id)
        )
        festival = result.scalar_one_or_none()
        if not festival:
            return formatter.not_found_response("Festival", festival_id)

        # Verify user exists
        result = await db.execute(select(UserModel).filter(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return formatter.not_found_response("User", user_id)

        logger.info(
            f"Generating festival playlist for {festival.name} (user: {user_id})"
        )

        # Step 1: Collect/refresh festival data if needed
        await festival_collector.refresh_festival_data(festival_id)

        # Step 2: Analyze all artists in the festival
        artist_setlist_data = {}
        for artist in festival.artists:
            try:
                setlists = await artist_analyzer.get_artist_setlists(
                    artist.name, limit=10
                )
                if setlists:
                    song_frequency = await artist_analyzer.analyze_song_frequency(
                        setlists
                    )
                    artist_setlist_data[artist.name] = song_frequency
                    logger.info(f"Analyzed {len(setlists)} setlists for {artist.name}")
            except Exception as e:
                logger.warning(f"Failed to analyze artist {artist.name}: {e}")
                continue

        if not artist_setlist_data:
            return formatter.error_response(
                error="No setlist data available",
                message="Could not retrieve setlist data for any festival artists",
                status_code=404,
            )

        # Step 3: Generate the playlist using the playlist generator service
        playlist = await playlist_generator.generate_festival_playlist(
            festival_id=festival_id,
            artist_setlist_data=artist_setlist_data,
            user_id=user_id,
        )

        # Step 4: If platform specified, create playlist on streaming service
        external_playlist_id = None
        if platform and playlist.songs:
            try:
                # This would require user authentication with the streaming service
                # For now, we'll just log the intent
                logger.info(
                    f"Would create playlist on {platform} with {len(playlist.songs)} songs"
                )
                # external_playlist_id = await streaming_service.create_playlist(
                #     playlist, platform, user_auth_token
                # )
            except Exception as e:
                logger.warning(f"Failed to create playlist on {platform}: {e}")

        # Step 5: Return the generated playlist
        response_data = {
            "id": playlist.id,
            "name": playlist.name,
            "description": playlist.description,
            "festival_id": str(festival_id),
            "user_id": str(user_id),
            "platform": platform,
            "external_id": external_playlist_id,
            "song_count": len(playlist.songs),
            "artists_analyzed": len(artist_setlist_data),
            "created_at": playlist.created_at.isoformat(),
            "songs": [
                {
                    "id": song.id,
                    "title": song.title,
                    "artist": song.artist,
                    "performance_count": song.performance_count,
                    "is_cover": song.is_cover,
                }
                for song in playlist.songs[:50]  # Limit response size
            ],
        }

        return formatter.success_response(
            data=response_data,
            message=f"Festival playlist generated successfully with {len(playlist.songs)} songs",
        )

    except Exception as e:
        logger.error(f"Error generating festival playlist: {e}")
        return formatter.error_response(
            error="Playlist generation failed", message=str(e), status_code=500
        )


@router.post("/generate/artist/{artist_id}")
async def generate_artist_playlist(
    request: Request,
    artist_id: UUID,
    user_id: UUID,
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    artist_analyzer: ArtistAnalyzerService = Depends(get_artist_analyzer),
    playlist_generator: PlaylistGeneratorService = Depends(get_playlist_generator),
    streaming_service: StreamingIntegrationService = Depends(get_streaming_integration),
):
    """Generate a playlist for a single artist using integrated services."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    try:
        # Verify artist exists
        result = await db.execute(
            select(ArtistModel).filter(ArtistModel.id == artist_id)
        )
        artist = result.scalar_one_or_none()
        if not artist:
            return formatter.not_found_response("Artist", artist_id)

        # Verify user exists
        result = await db.execute(select(UserModel).filter(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return formatter.not_found_response("User", user_id)

        logger.info(f"Generating artist playlist for {artist.name} (user: {user_id})")

        # Step 1: Analyze artist setlists
        setlists = await artist_analyzer.get_artist_setlists(artist.name, limit=10)
        if not setlists:
            return formatter.error_response(
                error="No setlist data available",
                message=f"Could not retrieve setlist data for {artist.name}",
                status_code=404,
            )

        # Step 2: Generate the playlist
        playlist = await playlist_generator.generate_artist_playlist(
            artist_id=artist_id, user_id=user_id
        )

        # Step 3: If platform specified, create playlist on streaming service
        external_playlist_id = None
        if platform and playlist.songs:
            try:
                logger.info(
                    f"Would create playlist on {platform} with {len(playlist.songs)} songs"
                )
                # external_playlist_id = await streaming_service.create_playlist(
                #     playlist, platform, user_auth_token
                # )
            except Exception as e:
                logger.warning(f"Failed to create playlist on {platform}: {e}")

        # Step 4: Return the generated playlist
        response_data = {
            "id": playlist.id,
            "name": playlist.name,
            "description": playlist.description,
            "artist_id": str(artist_id),
            "user_id": str(user_id),
            "platform": platform,
            "external_id": external_playlist_id,
            "song_count": len(playlist.songs),
            "setlists_analyzed": len(setlists),
            "created_at": playlist.created_at.isoformat(),
            "songs": [
                {
                    "id": song.id,
                    "title": song.title,
                    "artist": song.artist,
                    "performance_count": song.performance_count,
                    "is_cover": song.is_cover,
                }
                for song in playlist.songs
            ],
        }

        return formatter.success_response(
            data=response_data,
            message=f"Artist playlist generated successfully with {len(playlist.songs)} songs",
        )

    except Exception as e:
        logger.error(f"Error generating artist playlist: {e}")
        return formatter.error_response(
            error="Playlist generation failed", message=str(e), status_code=500
        )


@router.get("/recommendations/festivals/{user_id}")
async def get_festival_recommendations(
    request: Request,
    user_id: UUID,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    recommendation_engine: RecommendationEngine = Depends(get_recommendation_service),
):
    """Get personalized festival recommendations for a user."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    try:
        # Verify user exists
        result = await db.execute(select(UserModel).filter(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return formatter.not_found_response("User", user_id)

        # Get recommendations
        recommendations = await recommendation_engine.recommend_festivals(user_id)

        # Limit results
        limited_recommendations = recommendations[:limit]

        response_data = [
            {
                "festival_id": rec.festival_id,
                "festival_name": rec.festival_name,
                "similarity_score": rec.similarity_score,
                "matching_artists": rec.matching_artists,
                "recommendation_reason": rec.reason,
            }
            for rec in limited_recommendations
        ]

        return formatter.success_response(
            data=response_data,
            message=f"Found {len(limited_recommendations)} festival recommendations",
        )

    except Exception as e:
        logger.error(f"Error getting festival recommendations: {e}")
        return formatter.error_response(
            error="Recommendation failed", message=str(e), status_code=500
        )


@router.post("/collect/festivals")
async def trigger_festival_collection(
    request: Request,
    background_tasks: BackgroundTasks,
    festival_collector: FestivalCollectorService = Depends(get_festival_collector),
):
    """Trigger manual festival data collection."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    try:
        # Add background task for festival collection
        background_tasks.add_task(festival_collector.collect_daily_festivals)

        return formatter.success_response(
            data={"status": "started"},
            message="Festival collection task started in background",
        )

    except Exception as e:
        logger.error(f"Error starting festival collection: {e}")
        return formatter.error_response(
            error="Collection failed", message=str(e), status_code=500
        )
