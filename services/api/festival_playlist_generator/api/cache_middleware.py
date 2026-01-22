"""Cache middleware for API responses."""

import hashlib
import json
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from festival_playlist_generator.core.caching import (
    BrowserCacheOptimizer,
    HTTPCacheManager,
)


class APICacheMiddleware(BaseHTTPMiddleware):
    """Middleware to add appropriate cache headers to API responses."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.http_cache = HTTPCacheManager()
        self.browser_cache = BrowserCacheOptimizer()

    async def dispatch(
        self, request: Request, call_next: Callable[..., Any]
    ) -> Response:
        """Add cache headers to responses."""
        try:
            response: Response = await call_next(request)

            # Skip if response already has cache headers
            if "cache-control" in response.headers:
                return response

            path = request.url.path
            method = request.method

            # Only cache GET requests
            if method != "GET":
                response.headers["cache-control"] = (
                    "no-cache, no-store, must-revalidate"
                )
                return response

            # Static files - use browser cache optimizer
            if path.startswith("/static/"):
                try:
                    cache_headers = self.browser_cache.get_asset_cache_headers(path)
                    for key, value in cache_headers.items():
                        response.headers[key] = value
                except Exception:
                    # Fallback to basic cache headers
                    response.headers["cache-control"] = "public, max-age=3600"
                return response

            # API endpoints
            if path.startswith("/api/"):
                try:
                    cache_headers = self._get_api_cache_headers(path, response)
                    for key, value in cache_headers.items():
                        response.headers[key] = value
                except Exception:
                    # Fallback to basic cache headers
                    response.headers["cache-control"] = "public, max-age=600"
                return response

            # Web pages
            if response.headers.get("content-type", "").startswith("text/html"):
                try:
                    cache_headers = self.http_cache.get_cache_headers(
                        max_age=300, public=False, must_revalidate=True  # 5 minutes
                    )
                    for key, value in cache_headers.items():
                        response.headers[key] = value

                    # Add ETag for HTML responses
                    if hasattr(response, "body") and response.body:
                        body_data = response.body
                        body_bytes = (
                            bytes(body_data)
                            if isinstance(body_data, memoryview)
                            else body_data
                        )
                        etag = self.http_cache.generate_etag(body_bytes)
                        response.headers["etag"] = f'"{etag}"'
                except Exception:
                    # Fallback to basic cache headers
                    response.headers["cache-control"] = "private, max-age=300"

            return response

        except Exception as e:
            # If middleware fails, just return the original response
            fallback_response: Response = await call_next(request)
            return fallback_response

    def _get_api_cache_headers(self, path: str, response: Response) -> dict[str, str]:
        """Get cache headers for API endpoints."""
        # Health check endpoints - short cache
        if "/health" in path:
            return self.http_cache.get_cache_headers(
                max_age=60, public=True  # 1 minute
            )

        # Festival data - medium cache
        if "/festivals" in path:
            return self.http_cache.get_cache_headers(
                max_age=1800, public=True  # 30 minutes
            )

        # Artist/setlist data - longer cache (doesn't change often)
        if "/artists" in path or "/setlists" in path:
            return self.http_cache.get_cache_headers(
                max_age=3600, public=True  # 1 hour
            )

        # Playlist data - short cache (user-specific)
        if "/playlists" in path:
            return self.http_cache.get_cache_headers(
                max_age=300, public=False, must_revalidate=True  # 5 minutes
            )

        # User data - no cache
        if "/users" in path:
            return {"cache-control": "no-cache, no-store, must-revalidate"}

        # Auth endpoints - no cache (critical for login/logout state)
        if "/auth" in path:
            return {"cache-control": "no-cache, no-store, must-revalidate"}

        # Notifications - no cache
        if "/notifications" in path:
            return {"cache-control": "no-cache, no-store, must-revalidate"}

        # Default API cache
        return self.http_cache.get_cache_headers(
            max_age=600, public=True, must_revalidate=True  # 10 minutes
        )


class ConditionalCacheMiddleware(BaseHTTPMiddleware):
    """Middleware to handle conditional requests (ETag, If-None-Match)."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.http_cache = HTTPCacheManager()

    async def dispatch(
        self, request: Request, call_next: Callable[..., Any]
    ) -> Response:
        """Handle conditional requests."""
        try:
            response: Response = await call_next(request)

            # Only handle GET requests
            if request.method != "GET":
                return response

            # Check if response has ETag
            etag = response.headers.get("etag")
            if not etag:
                # Generate ETag if response has body
                try:
                    if hasattr(response, "body") and response.body:
                        body_data = response.body
                        body_bytes = (
                            bytes(body_data)
                            if isinstance(body_data, memoryview)
                            else body_data
                        )
                        etag = self.http_cache.generate_etag(body_bytes)
                        response.headers["etag"] = f'"{etag}"'
                except Exception:
                    # Skip ETag generation if it fails
                    pass

            # Check If-None-Match header
            if etag:
                try:
                    if_none_match = request.headers.get("if-none-match")
                    if if_none_match:
                        # Remove quotes from both ETags for comparison
                        request_etag = if_none_match.strip('"')
                        response_etag = etag.strip('"')

                        if request_etag == response_etag:
                            # Return 304 Not Modified
                            return Response(
                                status_code=304,
                                headers={
                                    "etag": etag,
                                    "cache-control": response.headers.get(
                                        "cache-control", ""
                                    ),
                                    "expires": response.headers.get("expires", ""),
                                },
                            )
                except Exception:
                    # If ETag comparison fails, just return the original response
                    pass

            return response

        except Exception:
            # If middleware fails, just return the original response
            fallback_response: Response = await call_next(request)
            return fallback_response
