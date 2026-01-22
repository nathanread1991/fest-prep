"""Playlist API endpoints."""

import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

import spotipy
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from spotipy.oauth2 import SpotifyOAuth
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from festival_playlist_generator.api.response_formatter import APIVersionManager
from festival_playlist_generator.api.versioning import (
    get_request_version,
    version_compatible_response,
)
from festival_playlist_generator.core.config import settings
from festival_playlist_generator.core.container import get_playlist_service
from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.core.redis import cache
from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.models.festival import Festival as FestivalModel
from festival_playlist_generator.models.playlist import Playlist as PlaylistModel
from festival_playlist_generator.models.song import Song as SongModel
from festival_playlist_generator.models.user import User as UserModel
from festival_playlist_generator.schemas.playlist import (
    Playlist,
    PlaylistCreate,
    PlaylistUpdate,
)
from festival_playlist_generator.schemas.playlist import (
    StreamingPlatform as SchemaStreamingPlatform,
)
from festival_playlist_generator.services.playlist_service import PlaylistService

router = APIRouter()
logger = logging.getLogger(__name__)


def convert_platform(model_platform: Any) -> Optional[SchemaStreamingPlatform]:
    """Convert model StreamingPlatform to schema StreamingPlatform."""
    if model_platform is None:
        return None
    return SchemaStreamingPlatform(model_platform.value)


class SongItem(BaseModel):
    """Song item for playlist creation."""

    title: str
    artist: str


class CreatePlaylistRequest(BaseModel):
    """Request model for creating a playlist on streaming platform."""

    artist_name: str
    songs: List[SongItem]
    platform: str = "spotify"


async def get_current_user_from_session(
    session_id: Optional[str] = Cookie(None), db: AsyncSession = Depends(get_db)
) -> Optional[UserModel]:
    """Get current user from session cookie."""
    if not session_id:
        return None

    try:
        # Get user ID from Redis session
        user_id_str = await cache.get(f"session:{session_id}")
        if not user_id_str:
            return None

        # Get user from database
        result = await db.execute(
            select(UserModel).filter(UserModel.id == UUID(user_id_str))
        )
        user = result.scalar_one_or_none()
        return user
    except Exception as e:
        logger.error(f"Error getting user from session: {e}")
        return None


@router.post("/create")
async def create_playlist_on_platform(
    request: Request,
    playlist_request: CreatePlaylistRequest,
    session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Create a playlist on a streaming platform (currently Spotify only)."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Check if user is authenticated
    user = await get_current_user_from_session(session_id, db)
    if not user:
        return formatter.error_response(
            error="Authentication required",
            message="You must be signed in to create playlists",
            status_code=401,
        )

    # Currently only Spotify is supported
    if playlist_request.platform != "spotify":
        return formatter.error_response(
            error="Platform not supported",
            message=f"Platform '{playlist_request.platform}' is not yet supported. Currently only Spotify is available.",
            status_code=400,
        )

    # Check if user has Spotify OAuth token
    spotify_token_key = f"spotify_token:{user.id}"
    spotify_token_data = await cache.get(spotify_token_key)

    if not spotify_token_data:
        return formatter.error_response(
            error="Spotify not connected",
            message="Please connect your Spotify account to create playlists",
            status_code=401,
        )

    try:
        import json

        token_info = json.loads(spotify_token_data)

        # Create Spotify client with user's access token
        sp = spotipy.Spotify(auth=token_info.get("access_token"))

        # Get user's Spotify ID
        spotify_user = sp.current_user()
        spotify_user_id = spotify_user["id"]

        # Create playlist name
        playlist_name = f"{playlist_request.artist_name} - Festival Prep"
        playlist_description = f"Playlist generated for {playlist_request.artist_name} based on recent setlists"

        # Create the playlist
        spotify_playlist = sp.user_playlist_create(
            user=spotify_user_id,
            name=playlist_name,
            public=True,
            description=playlist_description,
        )

        playlist_id = spotify_playlist["id"]
        playlist_url = spotify_playlist["external_urls"]["spotify"]

        # Search for tracks and add them to the playlist
        track_uris = []
        tracks_found = 0
        tracks_not_found = []

        for song in playlist_request.songs:
            try:
                # Search for the track
                query = f"track:{song.title} artist:{song.artist}"
                results = sp.search(q=query, type="track", limit=1)

                if results["tracks"]["items"]:
                    track = results["tracks"]["items"][0]
                    track_uris.append(track["uri"])
                    tracks_found += 1
                else:
                    tracks_not_found.append(f"{song.title} by {song.artist}")
                    logger.warning(
                        f"Track not found on Spotify: {song.title} by {song.artist}"
                    )
            except Exception as e:
                logger.error(f"Error searching for track {song.title}: {e}")
                tracks_not_found.append(f"{song.title} by {song.artist}")

        # Add tracks to playlist in batches of 100 (Spotify API limit)
        if track_uris:
            for i in range(0, len(track_uris), 100):
                batch = track_uris[i : i + 100]
                sp.playlist_add_items(playlist_id, batch)

        # Return success response
        return formatter.success_response(
            data={
                "playlist_id": playlist_id,
                "playlist_url": playlist_url,
                "playlist_name": playlist_name,
                "tracks_added": tracks_found,
                "tracks_requested": len(playlist_request.songs),
                "tracks_not_found": tracks_not_found if tracks_not_found else None,
            },
            message=f"Playlist created successfully! Added {tracks_found} of {len(playlist_request.songs)} songs.",
        )

    except spotipy.exceptions.SpotifyException as e:
        logger.error(f"Spotify API error: {e}")
        return formatter.error_response(
            error="Spotify API error",
            message=f"Failed to create playlist on Spotify: {str(e)}",
            status_code=503,
        )
    except Exception as e:
        logger.error(f"Error creating playlist: {e}")
        return formatter.error_response(
            error="Playlist creation failed",
            message=f"An error occurred while creating the playlist: {str(e)}",
            status_code=500,
        )


@router.post("/", status_code=201)
async def create_playlist(
    request: Request, playlist: PlaylistCreate, db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    """Create a new playlist."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Verify user exists
    result = await db.execute(
        select(UserModel).filter(UserModel.id == playlist.user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return formatter.not_found_response("User", playlist.user_id)

    # Verify festival exists if provided
    if playlist.festival_id:
        result = await db.execute(
            select(FestivalModel).filter(FestivalModel.id == playlist.festival_id)
        )
        festival = result.scalar_one_or_none()
        if not festival:
            return formatter.not_found_response("Festival", playlist.festival_id)

    # Verify artist exists if provided
    if playlist.artist_id:
        result = await db.execute(
            select(ArtistModel).filter(ArtistModel.id == playlist.artist_id)
        )
        artist = result.scalar_one_or_none()
        if not artist:
            return formatter.not_found_response("Artist", playlist.artist_id)

    # Create playlist
    db_playlist = PlaylistModel(
        name=playlist.name,
        description=playlist.description,
        festival_id=playlist.festival_id,
        artist_id=playlist.artist_id,
        user_id=playlist.user_id,
        platform=playlist.platform,
        external_id=playlist.external_id,
    )

    # Add songs if provided
    if playlist.song_ids:
        result = await db.execute(
            select(SongModel).filter(SongModel.id.in_(playlist.song_ids))
        )
        songs = result.scalars().all()
        if len(songs) != len(playlist.song_ids):
            return formatter.error_response(
                error="Songs not found",
                message="One or more songs not found",
                status_code=404,
            )
        db_playlist.songs.extend(songs)

    db.add(db_playlist)
    await db.commit()
    await db.refresh(db_playlist)

    playlist_data = Playlist(
        id=db_playlist.id,
        name=db_playlist.name,
        description=db_playlist.description,
        festival_id=db_playlist.festival_id,
        artist_id=db_playlist.artist_id,
        user_id=db_playlist.user_id,
        platform=convert_platform(db_playlist.platform),
        external_id=db_playlist.external_id,
        created_at=db_playlist.created_at,
        updated_at=db_playlist.updated_at,
    )

    return formatter.created_response(
        data=playlist_data.model_dump(), message="Playlist created successfully"
    )


@router.get("/")
async def list_playlists(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of playlists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of playlists to return"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    festival_id: Optional[UUID] = Query(None, description="Filter by festival ID"),
    artist_id: Optional[UUID] = Query(None, description="Filter by artist ID"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """List playlists with optional filtering."""
    from sqlalchemy import select

    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Build query using select()
    stmt = select(PlaylistModel)

    # Apply filters
    if user_id:
        stmt = stmt.where(PlaylistModel.user_id == user_id)

    if festival_id:
        stmt = stmt.where(PlaylistModel.festival_id == festival_id)

    if artist_id:
        stmt = stmt.where(PlaylistModel.artist_id == artist_id)

    if platform:
        stmt = stmt.where(PlaylistModel.platform == platform)

    # Apply pagination
    stmt = stmt.offset(skip).limit(limit)

    # Execute query
    result = await db.execute(stmt)
    playlists = result.scalars().all()

    playlist_data = [
        Playlist(
            id=playlist.id,
            name=playlist.name,
            description=playlist.description,
            festival_id=playlist.festival_id,
            artist_id=playlist.artist_id,
            user_id=playlist.user_id,
            platform=convert_platform(playlist.platform),
            external_id=playlist.external_id,
            created_at=playlist.created_at,
            updated_at=playlist.updated_at,
        ).model_dump()
        for playlist in playlists
    ]

    # For v1.1, include pagination metadata
    response_data: Dict[str, Any]
    if version == "1.1":
        # Get total count with same filters but without pagination
        count_stmt = select(func.count(PlaylistModel.id))
        if user_id:
            count_stmt = count_stmt.where(PlaylistModel.user_id == user_id)
        if festival_id:
            count_stmt = count_stmt.where(PlaylistModel.festival_id == festival_id)
        if artist_id:
            count_stmt = count_stmt.where(PlaylistModel.artist_id == artist_id)
        if platform:
            count_stmt = count_stmt.where(PlaylistModel.platform == platform)

        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar() or 0

        response_data = {
            "items": playlist_data,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total_count,
                "has_more": skip + limit < total_count,
            },
        }
    else:
        response_data = {"items": playlist_data}

    return JSONResponse(
        content=version_compatible_response(
            request, response_data, "Playlists retrieved successfully"
        ),
        status_code=200,
    )


@router.get("/{playlist_id}")
async def get_playlist(
    request: Request,
    playlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    playlist_service: PlaylistService = Depends(get_playlist_service),
) -> JSONResponse:
    """Get a specific playlist by ID."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Get playlist via service
    playlist = await playlist_service.get_playlist_by_id(
        playlist_id, load_relationships=False
    )

    if not playlist:
        return formatter.not_found_response("Playlist", playlist_id)

    playlist_data = Playlist(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        festival_id=playlist.festival_id,
        artist_id=playlist.artist_id,
        user_id=playlist.user_id,
        platform=convert_platform(playlist.platform),
        external_id=playlist.external_id,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
    )

    return formatter.success_response(
        data=playlist_data.model_dump(), message="Playlist retrieved successfully"
    )


@router.put("/{playlist_id}", response_model=Playlist)
async def update_playlist(
    playlist_id: UUID,
    playlist_update: PlaylistUpdate,
    db: AsyncSession = Depends(get_db),
) -> Playlist:
    """Update a playlist."""
    result = await db.execute(
        select(PlaylistModel).filter(PlaylistModel.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Update fields if provided
    update_data = playlist_update.model_dump(exclude_unset=True)

    # Handle songs separately
    if "song_ids" in update_data:
        song_ids = update_data.pop("song_ids")
        playlist.songs.clear()

        if song_ids:
            result = await db.execute(
                select(SongModel).filter(SongModel.id.in_(song_ids))
            )
            songs = result.scalars().all()
            if len(songs) != len(song_ids):
                raise HTTPException(
                    status_code=404, detail="One or more songs not found"
                )
            playlist.songs.extend(songs)

    # Update other fields
    for field, value in update_data.items():
        setattr(playlist, field, value)

    await db.commit()
    await db.refresh(playlist)

    return Playlist(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        festival_id=playlist.festival_id,
        artist_id=playlist.artist_id,
        user_id=playlist.user_id,
        platform=convert_platform(playlist.platform),
        external_id=playlist.external_id,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
    )


@router.delete("/{playlist_id}", status_code=204)
async def delete_playlist(
    playlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    playlist_service: PlaylistService = Depends(get_playlist_service),
) -> None:
    """Delete a playlist."""
    # Delete via service
    deleted = await playlist_service.delete_playlist(playlist_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Playlist not found")


@router.get("/{playlist_id}/songs", response_model=List[Dict[str, Any]])
async def get_playlist_songs(
    playlist_id: UUID, db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get songs in a playlist."""
    result = await db.execute(
        select(PlaylistModel).filter(PlaylistModel.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    return [
        {
            "id": song.id,
            "title": song.title,
            "artist": song.artist,
            "original_artist": song.original_artist,
            "is_cover": song.is_cover,
            "performance_count": song.performance_count,
        }
        for song in playlist.songs
    ]


@router.post("/{playlist_id}/songs/{song_id}", status_code=201)
async def add_song_to_playlist(
    playlist_id: UUID, song_id: UUID, db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Add a song to a playlist."""
    result = await db.execute(
        select(PlaylistModel).filter(PlaylistModel.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    result = await db.execute(select(SongModel).filter(SongModel.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    if song in playlist.songs:
        raise HTTPException(status_code=400, detail="Song already in playlist")

    playlist.songs.append(song)
    await db.commit()

    return {"message": "Song added to playlist"}


@router.delete("/{playlist_id}/songs/{song_id}", status_code=204)
async def remove_song_from_playlist(
    playlist_id: UUID, song_id: UUID, db: AsyncSession = Depends(get_db)
) -> None:
    """Remove a song from a playlist."""
    result = await db.execute(
        select(PlaylistModel).filter(PlaylistModel.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    result = await db.execute(select(SongModel).filter(SongModel.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    if song not in playlist.songs:
        raise HTTPException(status_code=404, detail="Song not in playlist")

    playlist.songs.remove(song)
    await db.commit()


@router.get("/user/{user_id}", response_model=List[Playlist])
async def get_user_playlists(
    user_id: UUID,
    skip: int = Query(0, ge=0, description="Number of playlists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of playlists to return"),
    db: AsyncSession = Depends(get_db),
    playlist_service: PlaylistService = Depends(get_playlist_service),
) -> List[Playlist]:
    """Get all playlists for a specific user."""
    # Verify user exists (using direct DB query for now, will use UserService in task 5.5)
    result = await db.execute(select(UserModel).filter(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get playlists via service
    playlists = await playlist_service.get_user_playlists(user_id, skip, limit)

    return [
        Playlist(
            id=playlist.id,
            name=playlist.name,
            description=playlist.description,
            festival_id=playlist.festival_id,
            artist_id=playlist.artist_id,
            user_id=playlist.user_id,
            platform=convert_platform(playlist.platform),
            external_id=playlist.external_id,
            created_at=playlist.created_at,
            updated_at=playlist.updated_at,
        )
        for playlist in playlists
    ]
