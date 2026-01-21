"""Main API router configuration."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

# Import route modules
from festival_playlist_generator.api.endpoints import users, festivals, artists, playlists, recommendations, notifications, playlist_generation, workflows, setlists, auth, data_export
from festival_playlist_generator.api.versioning import get_request_version, version_compatible_response

api_router = APIRouter()

# Basic health check endpoint
@api_router.get("/health")
@api_router.options("/health")
async def api_health(request: Request):
    """API health check endpoint with proper response formatting."""
    return JSONResponse(
        content=version_compatible_response(
            request,
            {"status": "healthy", "service": "Festival Playlist Generator API"},
            "API is healthy and running"
        ),
        status_code=200
    )

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(data_export.router, prefix="/user", tags=["data-export"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(festivals.router, prefix="/festivals", tags=["festivals"])
api_router.include_router(artists.router, prefix="/artists", tags=["artists"])
api_router.include_router(setlists.router, prefix="/setlists", tags=["setlists"])
api_router.include_router(playlists.router, prefix="/playlists", tags=["playlists"])
api_router.include_router(playlist_generation.router, prefix="/playlists", tags=["playlist-generation"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])