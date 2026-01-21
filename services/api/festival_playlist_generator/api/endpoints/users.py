"""User management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict
from uuid import UUID

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.core.container import get_user_service
from festival_playlist_generator.schemas.user import (
    UserCreate, User as UserSchema, UserUpdate,
    UserSongPreference as UserSongPreferenceSchema
)
from festival_playlist_generator.schemas.song import Song as SongSchema
from festival_playlist_generator.schemas.playlist import Playlist as PlaylistSchema
from festival_playlist_generator.services.auth import auth_service
from festival_playlist_generator.services.user_preferences import user_preference_service
from festival_playlist_generator.services.song_filtering import song_filtering_service
from festival_playlist_generator.services.user_service import UserService
from festival_playlist_generator.models.user import User
from festival_playlist_generator.api.response_formatter import APIVersionManager
from festival_playlist_generator.api.versioning import get_request_version, version_compatible_response

router = APIRouter()


async def get_current_user(
    session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
) -> UserSchema:
    """Get current authenticated user."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    user = await auth_service.get_current_user(db, session_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )
    
    return user


@router.post("/register", response_model=UserSchema)
async def register_user(
    user_data: UserCreate,
    password: str,
    db: AsyncSession = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """Register a new user."""
    return await auth_service.register_user(db, user_data, password)


@router.post("/login")
async def login_user(
    email: str,
    password: str,
    db: AsyncSession = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """Login user and create session."""
    user = await auth_service.authenticate_user(db, email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    session_id = await auth_service.create_session(user.id)
    
    return {
        "message": "Login successful",
        "user": user,
        "session_id": session_id
    }


@router.post("/logout")
async def logout_user(
    session_id: Optional[str] = Cookie(None)
):
    """Logout user and delete session."""
    if session_id:
        await auth_service.delete_session(session_id)
    
    return {"message": "Logout successful"}


@router.get("/me", response_model=UserSchema)
async def get_current_user_info(
    current_user: UserSchema = Depends(get_current_user)
):
    """Get current user information."""
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_current_user(
    user_update: UserUpdate,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """Update current user information."""
    # Get user from service
    db_user = await user_service.get_user_by_id(current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    if user_update.email is not None:
        db_user.email = user_update.email
    if user_update.preferences is not None:
        db_user.preferences = user_update.preferences
    if user_update.connected_platforms is not None:
        db_user.connected_platforms = user_update.connected_platforms
    
    # Update via service
    updated_user = await user_service.update_user(db_user)
    
    return UserSchema.model_validate(updated_user)


# Song preference endpoints
@router.post("/me/song-preferences/{song_id}", response_model=UserSongPreferenceSchema)
async def mark_song_preference(
    song_id: UUID,
    is_known: bool,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a song as known or unknown."""
    return await user_preference_service.mark_song_preference(
        db, current_user.id, song_id, is_known
    )


@router.get("/me/song-preferences", response_model=List[UserSongPreferenceSchema])
async def get_song_preferences(
    known_only: Optional[bool] = None,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's song preferences."""
    return await user_preference_service.get_user_song_preferences(
        db, current_user.id, known_only
    )


@router.get("/me/known-songs", response_model=List[UUID])
async def get_known_songs(
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of songs marked as known."""
    return await user_preference_service.get_known_songs(db, current_user.id)


@router.get("/me/unknown-songs", response_model=List[UUID])
async def get_unknown_songs(
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of songs marked as unknown."""
    return await user_preference_service.get_unknown_songs(db, current_user.id)


@router.post("/me/song-preferences/bulk", response_model=List[UserSongPreferenceSchema])
async def bulk_mark_songs(
    song_preferences: Dict[UUID, bool],
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Bulk update song preferences."""
    return await user_preference_service.bulk_mark_songs(
        db, current_user.id, song_preferences
    )


@router.delete("/me/song-preferences/{song_id}")
async def delete_song_preference(
    song_id: UUID,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a song preference."""
    success = await user_preference_service.delete_song_preference(
        db, current_user.id, song_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Song preference not found"
        )
    
    return {"message": "Song preference deleted"}


# Song filtering endpoints
@router.post("/me/playlists/{playlist_id}/filter", response_model=PlaylistSchema)
async def filter_playlist(
    playlist_id: UUID,
    show_known: bool = Query(True, description="Show songs marked as known"),
    show_unknown: bool = Query(True, description="Show songs marked as unknown"),
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Filter playlist based on user song preferences."""
    # This would typically fetch the playlist from database
    # For now, we'll return an error since playlist fetching isn't implemented yet
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Playlist filtering will be implemented when playlist endpoints are available"
    )


@router.post("/me/songs/filter", response_model=List[SongSchema])
async def filter_songs(
    songs: List[SongSchema],
    show_known: bool = Query(True, description="Show songs marked as known"),
    show_unknown: bool = Query(True, description="Show songs marked as unknown"),
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Filter a list of songs based on user preferences."""
    return await song_filtering_service.filter_songs_by_preferences(
        db, songs, current_user.id, show_known, show_unknown
    )


@router.post("/me/songs/filter/known", response_model=List[SongSchema])
async def get_known_songs_from_list(
    songs: List[SongSchema],
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get only known songs from a list."""
    return await song_filtering_service.get_known_songs_from_list(
        db, songs, current_user.id
    )


@router.post("/me/songs/filter/unknown", response_model=List[SongSchema])
async def get_unknown_songs_from_list(
    songs: List[SongSchema],
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get only unknown songs from a list."""
    return await song_filtering_service.get_unknown_songs_from_list(
        db, songs, current_user.id
    )


@router.post("/me/songs/summary")
async def get_song_preference_summary(
    songs: List[SongSchema],
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get summary of song preferences for a list of songs."""
    return await song_filtering_service.get_song_preference_summary(
        db, songs, current_user.id
    )


@router.get("/me/filter-toggle")
async def get_filter_toggle_options():
    """Get available filter toggle options."""
    return {
        "options": [
            {
                "show_known": True,
                "show_unknown": True,
                "description": "Show all songs"
            },
            {
                "show_known": True,
                "show_unknown": False,
                "description": "Show only known songs"
            },
            {
                "show_known": False,
                "show_unknown": True,
                "description": "Show only unknown songs"
            },
            {
                "show_known": False,
                "show_unknown": False,
                "description": "Hide all songs"
            }
        ]
    }


@router.post("/me/filter-toggle")
async def toggle_filter_settings(
    show_known: bool,
    show_unknown: bool
):
    """Toggle filter settings and get description."""
    return song_filtering_service.create_filter_toggle_response(
        show_known, show_unknown
    )


# API Key management endpoints
@router.post("/me/api-keys", response_model=dict)
async def create_api_key(
    name: str = "Default",
    current_user: UserSchema = Depends(get_current_user)
):
    """Create a new API key for the current user."""
    from festival_playlist_generator.api.auth import create_api_key
    
    api_key = create_api_key(str(current_user.id), name)
    
    return {
        "api_key": api_key,
        "name": name,
        "message": "API key created successfully. Store this key securely - it won't be shown again."
    }


@router.get("/me/api-keys", response_model=List[dict])
async def list_api_keys(
    current_user: UserSchema = Depends(get_current_user)
):
    """List API keys for the current user."""
    from festival_playlist_generator.api.auth import api_keys
    
    user_keys = []
    for hashed_key, key_info in api_keys.items():
        if key_info.user_id == str(current_user.id) and key_info.is_active:
            user_keys.append({
                "name": key_info.name,
                "created_at": key_info.created_at,
                "last_used": key_info.last_used,
                "key_preview": f"fpg_...{hashed_key[-8:]}"  # Show last 8 chars of hash
            })
    
    return user_keys


@router.delete("/me/api-keys/{key_name}")
async def revoke_api_key(
    key_name: str,
    current_user: UserSchema = Depends(get_current_user)
):
    """Revoke an API key."""
    from festival_playlist_generator.api.auth import api_keys
    
    # Find and deactivate the key
    for hashed_key, key_info in api_keys.items():
        if (key_info.user_id == str(current_user.id) and 
            key_info.name == key_name and 
            key_info.is_active):
            key_info.is_active = False
            return {"message": f"API key '{key_name}' has been revoked"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="API key not found"
    )