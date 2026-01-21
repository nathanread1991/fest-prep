"""API middleware for rate limiting and authentication."""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time
import logging
import uuid

from festival_playlist_generator.api.rate_limiting import check_rate_limit, add_rate_limit_headers, default_rate_limiter
from festival_playlist_generator.api.auth import verify_api_key
from festival_playlist_generator.core.logging_config import set_request_id, clear_request_id

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to generate/extract request IDs and propagate them.
    
    This middleware:
    - Extracts X-Request-ID from incoming requests if present
    - Generates a new UUID if no request ID is provided
    - Stores request ID in context for logging
    - Adds X-Request-ID header to all responses
    """
    
    async def dispatch(self, request: Request, call_next):
        # Extract or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Store request ID in context for logging
        set_request_id(request_id)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
        finally:
            # Clear request ID from context
            clear_request_id()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to apply rate limiting to API endpoints."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Skip rate limiting for non-API endpoints
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        
        try:
            # Extract API key if present
            api_key = None
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                potential_key = auth_header[7:]  # Remove "Bearer " prefix
                if verify_api_key(potential_key):
                    api_key = potential_key
            
            # Check rate limit
            rate_info = await check_rate_limit(request, default_rate_limiter, api_key)
            
            # Process the request
            response = await call_next(request)
            
            # Add rate limiting headers to response
            await add_rate_limit_headers(response, rate_info)
            
            return response
            
        except Exception as e:
            if hasattr(e, 'status_code') and e.status_code == 429:
                # Rate limit exceeded
                return JSONResponse(
                    status_code=429,
                    content=e.detail,
                    headers=e.headers if hasattr(e, 'headers') else {}
                )
            else:
                logger.error(f"Rate limiting middleware error: {e}")
                # Continue with request if rate limiting fails
                return await call_next(request)


class APILoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log API requests and responses."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request (request ID will be automatically included from context)
        logger.info(
            f"API Request: {request.method} {request.url.path}",
            extra={"extra_fields": {"method": request.method, "path": request.url.path}}
        )
        
        # Process request
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        logger.info(
            f"API Response: {request.method} {request.url.path} "
            f"- Status: {response.status_code} - Time: {process_time:.3f}s",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": process_time
                }
            }
        )
        
        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response