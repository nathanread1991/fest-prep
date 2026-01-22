"""Setlist API endpoints."""

import os
from datetime import datetime
from typing import Any, Callable, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from festival_playlist_generator.api.response_formatter import APIVersionManager
from festival_playlist_generator.api.versioning import (
    get_request_version,
    version_compatible_response,
)
from festival_playlist_generator.core.config import settings
from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.models.setlist import Setlist as SetlistModel
from festival_playlist_generator.schemas.setlist import (
    Setlist,
    SetlistCreate,
    SetlistUpdate,
)
from festival_playlist_generator.services.artist_analyzer import ArtistAnalyzerService

router = APIRouter()


@router.get("/artist/{artist_id}")
async def get_artist_setlists(
    request: Request,
    artist_id: UUID,
    skip: int = Query(0, ge=0, description="Number of setlists to skip"),
    limit: int = Query(10, ge=1, le=50, description="Number of setlists to return"),
    fetch_external: bool = Query(
        False, description="Fetch from external API if no local data"
    ),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Get setlists for a specific artist."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Check if artist exists
    result = await db.execute(select(ArtistModel).filter(ArtistModel.id == artist_id))
    artist = result.scalar_one_or_none()

    if not artist:
        return formatter.not_found_response("Artist", artist_id)

    # Get setlists from database
    query = (
        select(SetlistModel)
        .filter(SetlistModel.artist_id == artist_id)
        .order_by(SetlistModel.date.desc())
    )
    query = query.offset(skip).limit(limit)
    result_setlists = await db.execute(query)
    setlists_list = result_setlists.scalars().all()

    # If no setlists found and external fetch is requested, try to fetch from external API
    if not setlists_list and fetch_external:
        try:
            setlist_fm_api_key = settings.SETLIST_FM_API_KEY
            if setlist_fm_api_key:
                analyzer = ArtistAnalyzerService(setlist_fm_api_key)
                external_setlists = await analyzer.get_artist_setlists(
                    artist.name, limit
                )

                # Refresh the query to get newly stored setlists
                result_setlists = await db.execute(query)
                setlists_list = result_setlists.scalars().all()
        except Exception as e:
            # Log error but don't fail the request
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Error fetching external setlists for artist {artist.name}: {e}"
            )

    # Convert to response format
    setlist_data = []
    for setlist_item in setlists_list:
        setlist_data.append(
            {
                "id": str(setlist_item.id),
                "artist_id": str(setlist_item.artist_id),
                "artist_name": artist.name,
                "venue": setlist_item.venue,
                "date": setlist_item.date.isoformat(),
                "songs": setlist_item.songs,
                "tour_name": setlist_item.tour_name,
                "festival_name": setlist_item.festival_name,
                "source": setlist_item.source,
                "created_at": setlist_item.created_at.isoformat(),
                "updated_at": (
                    setlist_item.updated_at.isoformat() if setlist_item.updated_at else None
                ),
            }
        )

    return formatter.success_response(
        data=setlist_data,
        message=f"Found {len(setlist_data)} setlists for artist '{artist.name}'",
    )


@router.get("/artist/{artist_id}/recent")
async def get_recent_artist_setlists(
    request: Request,
    artist_id: UUID,
    limit: int = Query(
        5, ge=1, le=20, description="Number of recent setlists to return"
    ),
    fetch_external: bool = Query(
        True, description="Fetch from external API if no local data"
    ),
) -> JSONResponse:
    """Get recent setlists for an artist (optimized for UI display)."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    try:
        # Try to get database session
        from festival_playlist_generator.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            # Check if artist exists
            result = await db.execute(
                select(ArtistModel).filter(ArtistModel.id == artist_id)
            )
            artist = result.scalar_one_or_none()

            if not artist:
                return formatter.not_found_response("Artist", artist_id)

            # Get recent setlists from database
            query = (
                select(SetlistModel)
                .filter(SetlistModel.artist_id == artist_id)
                .order_by(SetlistModel.date.desc())
                .limit(limit)
            )
            result_recent = await db.execute(query)
            setlists_recent = result_recent.scalars().all()

            # If no setlists found and external fetch is requested, try to fetch from external API
            if not setlists_recent and fetch_external:
                try:
                    setlist_fm_api_key = settings.SETLIST_FM_API_KEY
                    if setlist_fm_api_key:
                        analyzer = ArtistAnalyzerService(setlist_fm_api_key)
                        external_setlists = await analyzer.get_artist_setlists(
                            artist.name, limit
                        )

                        # Refresh the query to get newly stored setlists
                        result_recent = await db.execute(query)
                        setlists_recent = result_recent.scalars().all()
                except Exception as e:
                    # Log error but don't fail the request
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"Error fetching external setlists for artist {artist.name}: {e}"
                    )

            # Convert to simplified response format for UI
            setlist_data = []
            for setlist_item in setlists_recent:
                setlist_data.append(
                    {
                        "id": str(setlist_item.id),
                        "venue": setlist_item.venue,
                        "date": setlist_item.date.strftime("%Y-%m-%d"),
                        "song_count": len(setlist_item.songs),
                        "songs": setlist_item.songs[
                            :10
                        ],  # Limit to first 10 songs for preview
                        "tour_name": setlist_item.tour_name,
                        "festival_name": setlist_item.festival_name,
                        "source": setlist_item.source,
                    }
                )

            return formatter.success_response(
                data=setlist_data,
                message=f"Found {len(setlist_data)} recent setlists for artist '{artist.name}'",
            )

    except Exception as e:
        # If database is not available, return mock data for demonstration
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Database unavailable, returning mock setlist data: {e}")

        # Mock setlist data for demonstration
        mock_setlists = [
            {
                "id": "mock-setlist-1",
                "venue": "Madison Square Garden, New York, NY",
                "date": "2024-03-15",
                "song_count": 18,
                "songs": [
                    "Opening Song",
                    "Hit Single #1",
                    "Fan Favorite",
                    "New Track",
                    "Classic Hit",
                    "Acoustic Version",
                    "Crowd Pleaser",
                    "Deep Cut",
                    "Radio Hit",
                    "Encore Opener",
                ],
                "tour_name": "World Tour 2024",
                "festival_name": None,
                "source": "setlist.fm",
            },
            {
                "id": "mock-setlist-2",
                "venue": "Red Rocks Amphitheatre, Morrison, CO",
                "date": "2024-03-10",
                "song_count": 16,
                "songs": [
                    "Show Opener",
                    "Popular Track",
                    "Album Highlight",
                    "Surprise Cover",
                    "Emotional Ballad",
                    "High Energy Song",
                    "Instrumental",
                    "Sing-Along",
                    "Dance Track",
                    "Final Song",
                ],
                "tour_name": "World Tour 2024",
                "festival_name": None,
                "source": "setlist.fm",
            },
        ]

        return formatter.success_response(
            data=mock_setlists,
            message=f"Found {len(mock_setlists)} recent setlists (demo data - database unavailable)",
        )


@router.get("/{setlist_id}")
async def get_setlist(
    request: Request, setlist_id: UUID, db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    """Get a specific setlist by ID."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Get setlist with artist information
    query = (
        select(SetlistModel)
        .options(selectinload(SetlistModel.artist))
        .filter(SetlistModel.id == setlist_id)
    )
    result = await db.execute(query)
    setlist = result.scalar_one_or_none()

    if not setlist:
        return formatter.not_found_response("Setlist", setlist_id)

    setlist_data = {
        "id": str(setlist.id),
        "artist_id": str(setlist.artist_id),
        "artist_name": setlist.artist.name,
        "venue": setlist.venue,
        "date": setlist.date.isoformat(),
        "songs": setlist.songs,
        "tour_name": setlist.tour_name,
        "festival_name": setlist.festival_name,
        "source": setlist.source,
        "created_at": setlist.created_at.isoformat(),
        "updated_at": setlist.updated_at.isoformat() if setlist.updated_at else None,
    }

    return formatter.success_response(
        data=setlist_data, message="Setlist retrieved successfully"
    )


@router.post("/refresh/{artist_id}")
async def refresh_artist_setlists(
    request: Request,
    artist_id: UUID,
    limit: int = Query(10, ge=1, le=50, description="Number of setlists to fetch"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Refresh setlists for an artist from external API."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Check if artist exists
    result = await db.execute(select(ArtistModel).filter(ArtistModel.id == artist_id))
    artist = result.scalar_one_or_none()

    if not artist:
        return formatter.not_found_response("Artist", artist_id)

    # Check if API key is configured
    setlist_fm_api_key = settings.SETLIST_FM_API_KEY
    if not setlist_fm_api_key:
        return formatter.error_response(
            error="API key not configured",
            message="Setlist.fm API key is not configured. Please add SETLIST_FM_API_KEY to your environment variables.",
            status_code=503,
        )

    try:
        # Fetch setlists from external API
        analyzer = ArtistAnalyzerService(setlist_fm_api_key)
        external_setlists = await analyzer.get_artist_setlists(artist.name, limit)

        return formatter.success_response(
            data={"fetched_count": len(external_setlists)},
            message=f"Successfully refreshed {len(external_setlists)} setlists for artist '{artist.name}'",
        )

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error refreshing setlists for artist {artist.name}: {e}")

        return formatter.error_response(
            error="External API error",
            message=f"Failed to refresh setlists from external API: {str(e)}",
            status_code=503,
        )


@router.get("/")
async def list_setlists(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of setlists to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of setlists to return"),
    artist_name: Optional[str] = Query(None, description="Filter by artist name"),
    venue: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """List all setlists with optional filtering."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    query = select(SetlistModel).options(selectinload(SetlistModel.artist))

    # Apply filters
    if artist_name:
        query = query.join(SetlistModel.artist).filter(
            ArtistModel.name.ilike(f"%{artist_name}%")
        )

    if venue:
        query = query.filter(SetlistModel.venue.ilike(f"%{venue}%"))

    # Apply ordering and pagination
    query = query.order_by(SetlistModel.date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    setlists = result.scalars().all()

    # Convert to response format
    setlist_data = []
    for setlist in setlists:
        setlist_data.append(
            {
                "id": str(setlist.id),
                "artist_id": str(setlist.artist_id),
                "artist_name": setlist.artist.name,
                "venue": setlist.venue,
                "date": setlist.date.strftime("%Y-%m-%d"),
                "song_count": len(setlist.songs),
                "tour_name": setlist.tour_name,
                "festival_name": setlist.festival_name,
                "source": setlist.source,
            }
        )

    return formatter.success_response(
        data=setlist_data, message=f"Found {len(setlist_data)} setlists"
    )
