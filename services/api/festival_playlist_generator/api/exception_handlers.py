"""Global exception handlers for API responses."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from festival_playlist_generator.api.response_formatter import APIVersionManager
from festival_playlist_generator.api.versioning import get_request_version
from festival_playlist_generator.core.logging_config import get_request_id

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standardized error response format.

    Provides consistent error responses across the API with:
    - error: Error type/code
    - message: Human-readable error message
    - details: Additional error details (optional)
    - request_id: Request ID for tracking
    - timestamp: ISO 8601 timestamp
    """

    @staticmethod
    def format_error(
        error: str,
        message: str,
        status_code: int,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format error response.

        Args:
            error: Error type/code
            message: Human-readable error message
            status_code: HTTP status code
            details: Additional error details

        Returns:
            Formatted error response dictionary
        """
        response = {
            "error": error,
            "message": message,
            "status_code": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Add request ID if available
        request_id = get_request_id()
        if request_id:
            response["request_id"] = request_id

        # Add details if provided
        if details:
            response["details"] = details

        return response


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, service_name: str, message: Optional[str] = None) -> None:
        self.service_name = service_name
        self.message = message or f"Circuit breaker is OPEN for {service_name}"
        super().__init__(self.message)


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """Handle HTTP exceptions with proper API response format."""
    # Log the exception with request context
    logger.warning(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        extra={
            "extra_fields": {
                "status_code": exc.status_code,
                "path": str(request.url.path),
                "method": request.method,
            }
        },
    )

    # For admin routes with 401 errors, preserve WWW-Authenticate header for
    # browser auth
    if (
        exc.status_code == 401
        and str(request.url.path).startswith("/admin")
        and exc.headers
        and "WWW-Authenticate" in exc.headers
    ):

        # Return a response with WWW-Authenticate header to trigger browser auth dialog
        return JSONResponse(
            status_code=401, content={"detail": exc.detail}, headers=exc.headers
        )

    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    return formatter.error_response(
        error=exc.detail,
        message=f"HTTP {exc.status_code} error occurred",
        status_code=exc.status_code,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> Response:
    """Handle request validation errors."""
    # Log validation error with request context
    logger.warning(
        f"Validation error: {len(exc.errors())} errors",
        extra={
            "extra_fields": {
                "path": str(request.url.path),
                "method": request.method,
                "error_count": len(exc.errors()),
            }
        },
    )

    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Format validation errors
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")

    return formatter.error_response(
        error="Validation failed",
        message="; ".join(errors),
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> Response:
    """Handle database integrity errors."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Log error with full context
    logger.error(
        f"Database integrity error: {exc}",
        extra={
            "extra_fields": {"path": str(request.url.path), "method": request.method}
        },
        exc_info=True,
    )

    # Check for common integrity violations
    error_msg = str(exc.orig)
    if "UNIQUE constraint failed" in error_msg or "duplicate key" in error_msg:
        return formatter.error_response(
            error="Duplicate resource",
            message="A resource with these details already exists",
            status_code=status.HTTP_409_CONFLICT,
        )
    elif "FOREIGN KEY constraint failed" in error_msg:
        return formatter.error_response(
            error="Invalid reference",
            message="Referenced resource does not exist",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    else:
        return formatter.error_response(
            error="Database error",
            message="A database constraint was violated",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> Response:
    """Handle general SQLAlchemy errors."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Log error with full context
    logger.error(
        f"Database error: {exc}",
        extra={
            "extra_fields": {
                "path": str(request.url.path),
                "method": request.method,
                "error_type": type(exc).__name__,
            }
        },
        exc_info=True,
    )

    return formatter.error_response(
        error="Database error",
        message="A database error occurred. Please try again later.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def circuit_breaker_handler(
    request: Request, exc: CircuitBreakerOpenError
) -> Response:
    """Handle circuit breaker open errors."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Log circuit breaker event
    logger.warning(
        f"Circuit breaker open for {exc.service_name}",
        extra={
            "extra_fields": {
                "path": str(request.url.path),
                "method": request.method,
                "service_name": exc.service_name,
            }
        },
    )

    return formatter.error_response(
        error="Service unavailable",
        message=(
            f"The {exc.service_name} service is temporarily unavailable. "
            f"Please try again later."
        ),
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


async def general_exception_handler(request: Request, exc: Exception) -> Response:
    """Handle unexpected exceptions."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Log error with full context and stack trace
    logger.error(
        f"Unexpected error: {exc}",
        extra={
            "extra_fields": {
                "path": str(request.url.path),
                "method": request.method,
                "error_type": type(exc).__name__,
            }
        },
        exc_info=True,
    )

    return formatter.internal_error_response(
        message="An unexpected error occurred. Please try again later."
    )


async def pydantic_validation_exception_handler(
    request: Request, exc: ValidationError
) -> Response:
    """Handle Pydantic validation errors."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    # Log validation error
    logger.warning(
        f"Pydantic validation error: {len(exc.errors())} errors",
        extra={
            "extra_fields": {
                "path": str(request.url.path),
                "method": request.method,
                "error_count": len(exc.errors()),
            }
        },
    )

    # Format validation errors
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")

    return formatter.error_response(
        error="Data validation failed",
        message="; ".join(errors),
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )
