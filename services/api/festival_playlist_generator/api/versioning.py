"""API versioning middleware and utilities."""

from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from festival_playlist_generator.api.response_formatter import APIVersionManager


class APIVersioningMiddleware(BaseHTTPMiddleware):
    """Middleware to handle API versioning."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add version information."""
        # Extract version from header or path
        version_header = request.headers.get("API-Version") or request.headers.get("Accept-Version")
        path_version = APIVersionManager.get_version_from_path(str(request.url.path))
        
        # Determine version (path takes precedence over header)
        if path_version != APIVersionManager.DEFAULT_VERSION:
            version = path_version
        else:
            version = APIVersionManager.get_version_from_header(version_header)
        
        # Check if version is supported
        if not APIVersionManager.is_version_supported(version):
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Unsupported API version",
                    "message": f"API version '{version}' is not supported. Supported versions: {APIVersionManager.SUPPORTED_VERSIONS}",
                    "supported_versions": APIVersionManager.SUPPORTED_VERSIONS,
                    "latest_version": APIVersionManager.LATEST_VERSION
                },
                status_code=400
            )
        
        # Add version to request state
        request.state.api_version = version
        
        # Process request
        response = await call_next(request)
        
        # Add version headers to response
        response.headers["API-Version"] = version
        response.headers["API-Supported-Versions"] = ",".join(APIVersionManager.SUPPORTED_VERSIONS)
        response.headers["API-Latest-Version"] = APIVersionManager.LATEST_VERSION
        
        return response


def get_request_version(request: Request) -> str:
    """Get API version from request state."""
    return getattr(request.state, "api_version", APIVersionManager.DEFAULT_VERSION)


def version_compatible_response(request: Request, data: any, message: str = None) -> dict:
    """Create version-compatible response based on request version."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)
    
    if version == "1.1":
        from festival_playlist_generator.api.response_formatter import format_response_v1_1
        return format_response_v1_1(data, message)
    else:
        from festival_playlist_generator.api.response_formatter import format_response_v1_0
        return format_response_v1_0(data, message)