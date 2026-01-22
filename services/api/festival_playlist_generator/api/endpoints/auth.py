"""Authentication API endpoints."""

from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.schemas.user import User as UserSchema
from festival_playlist_generator.services.oauth_service import oauth_service

router = APIRouter()


@router.get("/me", response_model=UserSchema)
async def get_current_user_api(
    request: Request, db: AsyncSession = Depends(get_db)
) -> UserSchema:
    """Get current authenticated user information."""
    session_id = request.cookies.get("session_id")

    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await oauth_service.get_current_user(db, session_id)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    return user


@router.get("/providers")
async def get_oauth_providers() -> Dict[str, List[str]]:
    """Get list of available OAuth providers."""
    return {"providers": oauth_service.get_available_providers()}


@router.get("/session")
async def get_session_info(request: Request) -> Dict[str, Any]:
    """Get current session information."""
    session_id = request.cookies.get("session_id")

    if not session_id:
        return {"authenticated": False, "session": None}

    session_data = await oauth_service.get_session(session_id)

    if not session_data:
        return {"authenticated": False, "session": None}

    return {
        "authenticated": True,
        "session": {
            "created_at": session_data["created_at"],
            "expires_at": session_data["expires_at"],
        },
    }
