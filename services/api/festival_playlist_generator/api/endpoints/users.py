"""User management API endpoints."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.core.container import get_user_service
from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.schemas.playlist import Playlist as PlaylistSchema
from festival_playlist_generator.schemas.song import Song as SongSchema
from festival_playlist_generator.schemas.user import User as UserSchema
from festival_playlist_generator.schemas.user import UserCreate
from festival_playlist_generator.schemas.user import (
    UserSongPreference as UserSongPreferenceSchema,
)
from festival_playlist_generator.schemas.user import UserUpdate
from festival_playlist_generator.services.auth import auth_service
from festival_playlist_generator.services.song_filtering import song_filtering_service
from festival_playlist_generator.services.user_preferences import (
    user_preference_service,
)
from festival_playlist_generator.services.user_service import UserService

router = APIRouter()


async def get_current_user(
    session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
    user_service: UserService = Depends(get_user_service),
) -> UserSchema:
    """Get current authenticated user."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    user = await auth_service.get_current_user(db, session_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )

    return user


@router.post("/register", response_model=UserSchema)
async def register_user(
    user_data: UserCreate,
    password: str,
    db: AsyncSession = Depends(get_db),
    user_service: UserService = Depends(get_user_service),
) -> UserSchema:
    """Register a new user."""
    return await auth_service.register_user(db, user_data, password)


@router.post("/login")
async def login_user(
    email: str,
    password: str,
    db: AsyncSession = Depends(get_db),
    user_service: UserService = Depends(get_user_service),
) -> Dict[str, Any]:
    """Login user and create session."""
    user = await auth_service.authenticate_user(db, email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    session_id = await auth_service.create_session(user.id)

    return {"message": "Login successful", "user": user, "session_id": session_id}


@router.post("/logout")
async def logout_user(session_id: Optional[str] = Cookie(None)) -> Dict[str, str]:
    """Logout user and delete session."""
    if session_id:
        await auth_service.delete_session(session_id)

    return {"message": "Logout successful"}


@router.get("/me", response_model=UserSchema)
async def get_current_user_info(
    current_user: UserSchema = Depends(get_current_user),
) -> UserSchema:
    """Get current user information."""
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_current_user(
    user_update: UserUpdate,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    user_service: UserService = Depends(get_user_service),
) -> UserSchema:
    """Update current user information."""
    # Get user from service
    db_user = await user_service.get_user_by_id(current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
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
    db: AsyncSession = Depends(get_db),
) -> UserSongPreferenceSchema:
    """Mark a song as known or unknown."""
    return await user_preference_service.mark_song_preference(
        db, current_user.id, song_id, is_known
    )


@router.get("/me/song-preferences", response_model=List[UserSongPreferenceSchema])
async def get_song_preferences(
    known_only: Optional[bool] = None,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserSongPreferenceSchema]:
    """Get user's song preferences."""
    return await user_preference_service.get_user_song_preferences(
        db, current_user.id, known_only
    )


@router.get("/me/known-songs", response_model=List[UUID])
async def get_known_songs(
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UUID]:
    """Get list of songs marked as known."""
    return await user_preference_service.get_known_songs(db, current_user.id)


@router.get("/me/unknown-songs", response_model=List[UUID])
async def get_unknown_songs(
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UUID]:
    """Get list of songs marked as unknown."""
    return await user_preference_service.get_unknown_songs(db, current_user.id)


@router.post("/me/song-preferences/bulk", response_model=List[UserSongPreferenceSchema])
async def bulk_mark_songs(
    song_preferences: Dict[UUID, bool],
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserSongPreferenceSchema]:
    """Bulk update song preferences."""
    return await user_preference_service.bulk_mark_songs(
        db, current_user.id, song_preferences
    )


@router.delete("/me/song-preferences/{song_id}")
async def delete_song_preference(
    song_id: UUID,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    """Delete a song preference."""
    success = await user_preference_service.delete_song_preference(
        db, current_user.id, song_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Song preference not found"
        )

    return {"message": "Song preference deleted"}


# Song filtering endpoints
@router.post("/me/playlists/{playlist_id}/filter", response_model=PlaylistSchema)
async def filter_playlist(
    playlist_id: UUID,
    show_known: bool = Query(True, description="Show songs marked as known"),
    show_unknown: bool = Query(True, description="Show songs marked as unknown"),
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaylistSchema:
    """Filter playlist based on user song preferences."""
    # This would typically fetch the playlist from database
    # For now, we'll return an error since playlist fetching isn't implemented yet
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Playlist filtering will be implemented "
            "when playlist endpoints are available"
        ),
    )


@router.post("/me/songs/filter", response_model=List[SongSchema])
async def filter_songs(
    songs: List[SongSchema],
    show_known: bool = Query(True, description="Show songs marked as known"),
    show_unknown: bool = Query(True, description="Show songs marked as unknown"),
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SongSchema]:
    """Filter a list of songs based on user preferences."""
    return await song_filtering_service.filter_songs_by_preferences(
        db, songs, current_user.id, show_known, show_unknown
    )


@router.post("/me/songs/filter/known", response_model=List[SongSchema])
async def get_known_songs_from_list(
    songs: List[SongSchema],
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SongSchema]:
    """Get only known songs from a list."""
    return await song_filtering_service.get_known_songs_from_list(
        db, songs, current_user.id
    )


@router.post("/me/songs/filter/unknown", response_model=List[SongSchema])
async def get_unknown_songs_from_list(
    songs: List[SongSchema],
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SongSchema]:
    """Get only unknown songs from a list."""
    return await song_filtering_service.get_unknown_songs_from_list(
        db, songs, current_user.id
    )


@router.post("/me/songs/summary")
async def get_song_preference_summary(
    songs: List[SongSchema],
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get summary of song preferences for a list of songs."""
    return await song_filtering_service.get_song_preference_summary(
        db, songs, current_user.id
    )


@router.get("/me/filter-toggle")
async def get_filter_toggle_options() -> Dict[str, List[Dict[str, Any]]]:
    """Get available filter toggle options."""
    return {
        "options": [
            {"show_known": True, "show_unknown": True, "description": "Show all songs"},
            {
                "show_known": True,
                "show_unknown": False,
                "description": "Show only known songs",
            },
            {
                "show_known": False,
                "show_unknown": True,
                "description": "Show only unknown songs",
            },
            {
                "show_known": False,
                "show_unknown": False,
                "description": "Hide all songs",
            },
        ]
    }


@router.post("/me/filter-toggle")
async def toggle_filter_settings(
    show_known: bool, show_unknown: bool
) -> Dict[str, Any]:
    """Toggle filter settings and get description."""
    return song_filtering_service.create_filter_toggle_response(
        show_known, show_unknown
    )


# API Key management endpoints
@router.post("/me/api-keys", response_model=Dict[str, Any])
async def create_api_key_endpoint(
    name: str = "Default", current_user: UserSchema = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new API key for the current user."""
    # TODO: Implement API key creation functionality
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="API key management not yet implemented",
    )


@router.get("/me/api-keys", response_model=List[Dict[str, Any]])
async def list_api_keys(
    current_user: UserSchema = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List API keys for the current user."""
    # TODO: Implement API key listing functionality
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="API key management not yet implemented",
    )


@router.delete("/me/api-keys/{key_name}")
async def revoke_api_key(
    key_name: str, current_user: UserSchema = Depends(get_current_user)
) -> Dict[str, str]:
    """Revoke an API key."""
    # TODO: Implement API key revocation functionality
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="API key management not yet implemented",
    )
