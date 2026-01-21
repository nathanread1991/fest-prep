"""Cache middleware for API responses."""

from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import hashlib
import json

from festival_playlist_generator.core.caching import HTTPCacheManager, BrowserCacheOptimizer


class APICacheMiddleware(BaseHTTPMiddleware):
    """Middleware to add appropriate cache headers to API responses."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.http_cache = HTTPCacheManager()
        self.browser_cache = BrowserCacheOptimizer()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add cache headers to responses."""
        try:
            response = await call_next(request)
            
            # Skip if response already has cache headers
            if "cache-control" in response.headers:
                return response
            
            path = request.url.path
            method = request.method
            
            # Only cache GET requests
            if method != "GET":
                response.headers["cache-control"] = "no-cache, no-store, must-revalidate"
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
                        max_age=300,  # 5 minutes
                        public=False,
                        must_revalidate=True
                    )
                    for key, value in cache_headers.items():
                        response.headers[key] = value
                    
                    # Add ETag for HTML responses
                    if hasattr(response, "body") and response.body:
                        etag = self.http_cache.generate_etag(response.body)
                        response.headers["etag"] = f'"{etag}"'
                except Exception:
                    # Fallback to basic cache headers
                    response.headers["cache-control"] = "private, max-age=300"
            
            return response
            
        except Exception as e:
            # If middleware fails, just return the original response
            return await call_next(request)
    
    def _get_api_cache_headers(self, path: str, response: Response) -> dict:
        """Get cache headers for API endpoints."""
        # Health check endpoints - short cache
        if "/health" in path:
            return self.http_cache.get_cache_headers(
                max_age=60,  # 1 minute
                public=True
            )
        
        # Festival data - medium cache
        if "/festivals" in path:
            return self.http_cache.get_cache_headers(
                max_age=1800,  # 30 minutes
                public=True
            )
        
        # Artist/setlist data - longer cache (doesn't change often)
        if "/artists" in path or "/setlists" in path:
            return self.http_cache.get_cache_headers(
                max_age=3600,  # 1 hour
                public=True
            )
        
        # Playlist data - short cache (user-specific)
        if "/playlists" in path:
            return self.http_cache.get_cache_headers(
                max_age=300,  # 5 minutes
                public=False,
                must_revalidate=True
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
            max_age=600,  # 10 minutes
            public=True,
            must_revalidate=True
        )


class ConditionalCacheMiddleware(BaseHTTPMiddleware):
    """Middleware to handle conditional requests (ETag, If-None-Match)."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.http_cache = HTTPCacheManager()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle conditional requests."""
        try:
            response = await call_next(request)
            
            # Only handle GET requests
            if request.method != "GET":
                return response
            
            # Check if response has ETag
            etag = response.headers.get("etag")
            if not etag:
                # Generate ETag if response has body
                try:
                    if hasattr(response, "body") and response.body:
                        etag = self.http_cache.generate_etag(response.body)
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
                                    "cache-control": response.headers.get("cache-control", ""),
                                    "expires": response.headers.get("expires", "")
                                }
                            )
                except Exception:
                    # If ETag comparison fails, just return the original response
                    pass
            
            return response
            
        except Exception:
            # If middleware fails, just return the original response
            return await call_next(request)