"""Authentication middleware for protected routes."""

import logging
from typing import Awaitable, Callable, Optional

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.schemas.user import User as UserSchema
from festival_playlist_generator.services.oauth_service import oauth_service

logger = logging.getLogger(__name__)


class AuthenticationMiddleware:
    """Middleware to handle authentication for protected routes."""

    def __init__(self) -> None:
        self.protected_routes = {
            "/playlists",
            "/auth/profile",
            "/auth/settings",
            "/auth/privacy-preferences",
            "/auth/export-data",
            "/auth/delete-account",
        }

        self.api_protected_routes = {"/api/playlists", "/api/user", "/api/auth/me"}

    async def __call__(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request through authentication middleware."""
        path = request.url.path

        # Skip authentication for non-protected routes
        if not self._is_protected_route(path):
            return await call_next(request)

        # Get current user
        user = await self._get_current_user(request)

        # Handle unauthenticated requests
        if not user:
            return self._handle_unauthenticated_request(request, path)

        # Add user to request state for use in route handlers
        request.state.current_user = user

        return await call_next(request)

    def _is_protected_route(self, path: str) -> bool:
        """Check if route requires authentication."""
        # Check exact matches
        if path in self.protected_routes or path in self.api_protected_routes:
            return True

        # Check prefix matches for dynamic routes
        protected_prefixes = ["/playlists/", "/api/playlists/", "/api/user/", "/auth/"]

        return any(path.startswith(prefix) for prefix in protected_prefixes)

    async def _get_current_user(self, request: Request) -> Optional[UserSchema]:
        """Get current authenticated user from session."""
        try:
            session_id = request.cookies.get("session_id")
            if not session_id:
                return None

            # Get database session
            db_gen = get_db()
            db = await db_gen.__anext__()

            try:
                user = await oauth_service.get_current_user(db, session_id)
                return user
            finally:
                await db_gen.aclose()

        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            return None

    def _handle_unauthenticated_request(self, request: Request, path: str) -> Response:
        """Handle requests to protected routes without authentication."""
        # For API routes, return JSON error
        if path.startswith("/api/"):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
            )

        # For web routes, redirect to login with return URL
        return_url = str(request.url)
        login_url = f"/auth/login?return_url={return_url}"

        return RedirectResponse(url=login_url, status_code=302)


# Global middleware instance
auth_middleware = AuthenticationMiddleware()


# Dependency for route handlers that require authentication
async def require_authentication(request: Request) -> UserSchema:
    """Dependency that requires user to be authenticated."""
    user: Optional[UserSchema] = getattr(request.state, "current_user", None)

    if not user:
        # This should not happen if middleware is working correctly
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    return user


# Dependency for optional authentication
async def optional_authentication(request: Request) -> Optional[UserSchema]:
    """Dependency that provides user if authenticated, None otherwise."""
    return getattr(request.state, "current_user", None)
