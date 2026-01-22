"""Compression middleware for FastAPI application."""

import gzip
from typing import Any, Callable, Optional, Set

import brotli
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class CompressionMiddleware(BaseHTTPMiddleware):
    """Middleware to compress responses using gzip or brotli."""

    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        compressible_types: Optional[Set[str]] = None,
    ) -> None:
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compressible_types = compressible_types or {
            "text/html",
            "text/css",
            "text/javascript",
            "application/javascript",
            "application/json",
            "application/xml",
            "text/xml",
            "text/plain",
            "application/rss+xml",
            "application/atom+xml",
            "image/svg+xml",
        }

    async def dispatch(
        self, request: Request, call_next: Callable[..., Any]
    ) -> Response:
        """Process request and compress response if appropriate."""
        response: Response = await call_next(request)

        # Skip compression for certain conditions
        if (
            response.status_code < 200
            or response.status_code >= 300
            or "content-encoding" in response.headers
            or "content-range" in response.headers
        ):
            return response

        # Get accept-encoding header
        accept_encoding = request.headers.get("accept-encoding", "").lower()

        # Check if client supports compression
        supports_brotli = "br" in accept_encoding
        supports_gzip = "gzip" in accept_encoding

        if not (supports_brotli or supports_gzip):
            return response

        # Get content type
        content_type = response.headers.get("content-type", "").split(";")[0].lower()

        # Check if content type is compressible
        if content_type not in self.compressible_types:
            return response

        # Get response body - handle different response types
        try:
            if isinstance(response, StreamingResponse):
                # Handle streaming responses
                body_parts: list[bytes] = []
                async for chunk in response.body_iterator:
                    if isinstance(chunk, bytes):
                        body_parts.append(chunk)
                    elif isinstance(chunk, (str, memoryview)):
                        body_parts.append(
                            bytes(chunk)
                            if isinstance(chunk, memoryview)
                            else chunk.encode()
                        )
                body = b"".join(body_parts)
            elif hasattr(response, "body") and response.body:
                body_raw = response.body
                body = bytes(body_raw) if isinstance(body_raw, memoryview) else body_raw
            else:
                # Skip compression if we can't get the body
                return response
        except Exception:
            # If we can't get the body, return original response
            return response

        # Check minimum size
        if len(body) < self.minimum_size:
            return response

        # Compress the body
        try:
            if supports_brotli:
                compressed_body = brotli.compress(body, quality=4)
                encoding = "br"
            else:
                compressed_body = gzip.compress(body, compresslevel=6)
                encoding = "gzip"
        except Exception:
            # If compression fails, return original response
            return response

        # Only use compression if it actually reduces size
        if len(compressed_body) >= len(body):
            return response

        # Create new response with compressed body
        new_response = Response(
            content=compressed_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

        # Update headers
        new_response.headers["content-encoding"] = encoding
        new_response.headers["content-length"] = str(len(compressed_body))
        new_response.headers["vary"] = "Accept-Encoding"

        # Add cache headers for compressed content
        if not new_response.headers.get("cache-control"):
            new_response.headers["cache-control"] = "public, max-age=3600"

        return new_response


class StaticFileCompressionMiddleware(BaseHTTPMiddleware):
    """Middleware to add cache headers for static files."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[..., Any]
    ) -> Response:
        """Add cache headers for static files."""
        response: Response = await call_next(request)

        # Add cache headers for static files
        if request.url.path.startswith("/static/"):
            # Get file extension
            path = request.url.path.lower()

            if any(
                path.endswith(ext)
                for ext in [
                    ".css",
                    ".js",
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".svg",
                    ".ico",
                    ".woff",
                    ".woff2",
                    ".ttf",
                    ".eot",
                ]
            ):
                # Cache static assets for 1 year
                response.headers["cache-control"] = (
                    "public, max-age=31536000, immutable"
                )
                response.headers["expires"] = "Thu, 31 Dec 2025 23:59:59 GMT"
            elif any(path.endswith(ext) for ext in [".html", ".json", ".xml"]):
                # Cache HTML/JSON/XML for 1 hour
                response.headers["cache-control"] = "public, max-age=3600"

            # Add ETag for better caching
            if (
                "etag" not in response.headers
                and hasattr(response, "body")
                and response.body
            ):
                import hashlib

                etag = hashlib.md5(response.body).hexdigest()
                response.headers["etag"] = f'"{etag}"'

        return response
