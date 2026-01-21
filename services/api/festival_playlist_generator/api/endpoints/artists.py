"""Artist API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.core.container import get_artist_service
from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.schemas.artist import Artist, ArtistCreate, ArtistUpdate
from festival_playlist_generator.api.response_formatter import APIVersionManager
from festival_playlist_generator.api.versioning import get_request_version
from festival_playlist_generator.services.artist_service import ArtistService

router = APIRouter()


@router.post("/", status_code=201)
async def create_artist(
    request: Request,
    artist: ArtistCreate,
    db: AsyncSession = Depends(get_db),
    artist_service: ArtistService = Depends(get_artist_service)
):
    """Create a new artist."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)
    
    # Check if artist already exists
    existing_artist = await artist_service.get_artist_by_name(artist.name)
    
    if existing_artist:
        return formatter.error_response(
            error="Artist already exists",
            message=f"Artist '{artist.name}' already exists in the database",
            status_code=400
        )
    
    # Create artist model
    db_artist = ArtistModel(
        name=artist.name,
        musicbrainz_id=artist.musicbrainz_id,
        genres=artist.genres,
        popularity_score=artist.popularity_score
    )
    
    # Create via service
    created_artist = await artist_service.create_artist(db_artist)
    
    # Convert to response schema
    artist_data = Artist(
        id=created_artist.id,
        name=created_artist.name,
        musicbrainz_id=created_artist.musicbrainz_id,
        genres=created_artist.genres or [],
        popularity_score=created_artist.popularity_score,
        created_at=created_artist.created_at
    )
    
    return formatter.created_response(
        data=artist_data.model_dump(),
        message="Artist created successfully"
    )


@router.get("/")
async def list_artists(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of artists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of artists to return"),
    genre: Optional[str] = Query(None, description="Filter by genre"),
    festival: Optional[str] = Query(None, description="Filter by festival name"),
    db: AsyncSession = Depends(get_db),
    artist_service: ArtistService = Depends(get_artist_service)
):
    """List artists with optional filtering."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)
    
    # Calculate page from skip/limit
    page = (skip // limit) + 1
    per_page = limit
    
    # Build search query if festival filter is provided
    search = festival if festival else None
    
    # Get artists via service
    artists, total_count = await artist_service.search_artists(
        search=search,
        page=page,
        per_page=per_page,
        order_by="created_at",
        order_desc=True
    )
    
    # Filter by genre if provided (service doesn't support genre filter yet)
    if genre:
        artists = [a for a in artists if genre in (a.genres or [])]
        total_count = len(artists)
    
    # Convert to response format
    artist_data = [
        Artist(
            id=artist.id,
            name=artist.name,
            musicbrainz_id=artist.musicbrainz_id,
            genres=artist.genres or [],
            popularity_score=artist.popularity_score,
            created_at=artist.created_at
        ).model_dump()
        for artist in artists
    ]
    
    # For v1.1, include pagination metadata
    if version == "1.1":
        response_data = {
            "items": artist_data,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total_count,
                "has_more": skip + limit < total_count
            }
        }
    else:
        response_data = artist_data
    
    return formatter.success_response(
        data=response_data,
        message="Artists retrieved successfully"
    )


@router.get("/{artist_id}")
async def get_artist(
    request: Request,
    artist_id: UUID,
    db: AsyncSession = Depends(get_db),
    artist_service: ArtistService = Depends(get_artist_service)
):
    """Get a specific artist by ID."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)
    
    # Get artist via service
    artist = await artist_service.get_artist_by_id(artist_id, load_relationships=False)
    
    if not artist:
        return formatter.not_found_response("Artist", artist_id)
    
    artist_data = Artist(
        id=artist.id,
        name=artist.name,
        musicbrainz_id=artist.musicbrainz_id,
        genres=artist.genres or [],
        popularity_score=artist.popularity_score,
        created_at=artist.created_at
    )
    
    return formatter.success_response(
        data=artist_data.model_dump(),
        message="Artist retrieved successfully"
    )


@router.put("/{artist_id}")
async def update_artist(
    request: Request,
    artist_id: UUID,
    artist_update: ArtistUpdate,
    db: AsyncSession = Depends(get_db),
    artist_service: ArtistService = Depends(get_artist_service)
):
    """Update an artist."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)
    
    # Get existing artist
    artist = await artist_service.get_artist_by_id(artist_id, load_relationships=False)
    
    if not artist:
        return formatter.not_found_response("Artist", artist_id)
    
    # Update fields if provided
    update_data = artist_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(artist, field, value)
    
    # Update via service
    updated_artist = await artist_service.update_artist(artist)
    
    artist_data = Artist(
        id=updated_artist.id,
        name=updated_artist.name,
        musicbrainz_id=updated_artist.musicbrainz_id,
        genres=updated_artist.genres or [],
        popularity_score=updated_artist.popularity_score,
        created_at=updated_artist.created_at
    )
    
    return formatter.success_response(
        data=artist_data.model_dump(),
        message="Artist updated successfully"
    )


@router.delete("/{artist_id}")
async def delete_artist(
    request: Request,
    artist_id: UUID,
    db: AsyncSession = Depends(get_db),
    artist_service: ArtistService = Depends(get_artist_service)
):
    """Delete an artist."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)
    
    # Delete via service
    deleted = await artist_service.delete_artist(artist_id)
    
    if not deleted:
        return formatter.not_found_response("Artist", artist_id)
    
    return formatter.no_content_response("Artist deleted successfully")


@router.get("/search/")
async def search_artists(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    skip: int = Query(0, ge=0, description="Number of artists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of artists to return"),
    db: AsyncSession = Depends(get_db),
    artist_service: ArtistService = Depends(get_artist_service)
):
    """Search artists by name or genre."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)
    
    # Calculate page from skip/limit
    page = (skip // limit) + 1
    per_page = limit
    
    # Search via service
    artists, total_count = await artist_service.search_artists(
        search=q,
        page=page,
        per_page=per_page,
        order_by="created_at",
        order_desc=True
    )
    
    artist_data = [
        Artist(
            id=artist.id,
            name=artist.name,
            musicbrainz_id=artist.musicbrainz_id,
            genres=artist.genres or [],
            popularity_score=artist.popularity_score,
            created_at=artist.created_at
        ).model_dump()
        for artist in artists
    ]
    
    # For v1.1, include search metadata
    if version == "1.1":
        response_data = {
            "items": artist_data,
            "search": {
                "query": q,
                "skip": skip,
                "limit": limit,
                "total": total_count,
                "has_more": skip + limit < total_count
            }
        }
    else:
        response_data = artist_data
    
    return formatter.success_response(
        data=response_data,
        message=f"Found {len(artist_data)} artists matching '{q}'"
    )


@router.get("/{artist_id}/festivals")
async def get_artist_festivals(
    request: Request,
    artist_id: UUID,
    db: AsyncSession = Depends(get_db),
    artist_service: ArtistService = Depends(get_artist_service)
):
    """Get festivals where an artist is performing."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)
    
    # Get artist with relationships loaded
    artist = await artist_service.get_artist_by_id(artist_id, load_relationships=True)
    
    if not artist:
        return formatter.not_found_response("Artist", artist_id)
    
    festival_data = [
        {
            "id": str(festival.id),
            "name": festival.name,
            "dates": [date.isoformat() for date in festival.dates] if festival.dates else [],
            "location": festival.location,
            "venue": festival.venue
        }
        for festival in artist.festivals
    ]
    
    return formatter.success_response(
        data=festival_data,
        message=f"Found {len(festival_data)} festivals for artist '{artist.name}'"
    )
