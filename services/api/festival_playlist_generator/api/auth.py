"""API authentication endpoints."""

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import os

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.services.oauth_service import oauth_service

logger = logging.getLogger(__name__)


def verify_api_key(api_key: str) -> bool:
    """Verify if the provided API key is valid."""
    # For now, check against environment variable
    # In production, this should check against a database of valid API keys
    valid_api_key = os.getenv("API_KEY")
    return valid_api_key and api_key == valid_api_key

# Create API router
api_auth_router = APIRouter(prefix="/api/auth", tags=["api-authentication"])


@api_auth_router.get("/me")
async def get_current_user_api(request: Request, db: AsyncSession = Depends(get_db)):
    """API endpoint to get current authenticated user."""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = await oauth_service.get_current_user(db, session_id)
    
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "profile_picture_url": user.profile_picture_url,
        "oauth_provider": user.oauth_provider,
        "marketing_opt_in": user.marketing_opt_in,
        "preferences": user.preferences,
        "connected_platforms": user.connected_platforms,
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat()
    }


@api_auth_router.get("/status")
async def get_auth_status(request: Request, db: AsyncSession = Depends(get_db)):
    """Check authentication status without returning user data."""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        return {"authenticated": False}
    
    user = await oauth_service.get_current_user(db, session_id)
    
    return {
        "authenticated": user is not None,
        "user_id": str(user.id) if user else None
    }