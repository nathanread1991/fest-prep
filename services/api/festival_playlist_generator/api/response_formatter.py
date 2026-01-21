"""API response formatting and versioning utilities."""

from typing import Any, Dict, Optional, Union
from datetime import datetime, timezone
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class APIResponse(BaseModel):
    """Standard API response format."""
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime
    version: str
    
    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class APIError(BaseModel):
    """Standard API error format."""
    success: bool = False
    error: str
    message: Optional[str] = None
    timestamp: datetime
    version: str
    
    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class ResponseFormatter:
    """Handles API response formatting and versioning."""
    
    def __init__(self, version: str = "1.0"):
        self.version = version
    
    def success_response(
        self,
        data: Any = None,
        message: Optional[str] = None,
        status_code: int = status.HTTP_200_OK
    ) -> JSONResponse:
        """Create a successful API response."""
        response_data = {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": self.version
        }
        
        if data is not None:
            response_data["data"] = data
        if message:
            response_data["message"] = message
        
        return JSONResponse(
            content=response_data,
            status_code=status_code
        )
    
    def error_response(
        self,
        error: str,
        message: Optional[str] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST
    ) -> JSONResponse:
        """Create an error API response."""
        response_data = {
            "success": False,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": self.version
        }
        
        if message:
            response_data["message"] = message
        
        return JSONResponse(
            content=response_data,
            status_code=status_code
        )
    
    def created_response(
        self,
        data: Any,
        message: Optional[str] = None
    ) -> JSONResponse:
        """Create a 201 Created response."""
        return self.success_response(
            data=data,
            message=message,
            status_code=status.HTTP_201_CREATED
        )
    
    def no_content_response(
        self,
        message: Optional[str] = None
    ) -> JSONResponse:
        """Create a 204 No Content response."""
        return self.success_response(
            message=message,
            status_code=status.HTTP_204_NO_CONTENT
        )
    
    def not_found_response(
        self,
        resource: str,
        identifier: Union[str, int]
    ) -> JSONResponse:
        """Create a 404 Not Found response."""
        return self.error_response(
            error="Resource not found",
            message=f"{resource} with identifier '{identifier}' was not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    def validation_error_response(
        self,
        errors: Dict[str, Any]
    ) -> JSONResponse:
        """Create a 422 Validation Error response."""
        return self.error_response(
            error="Validation failed",
            message="Request data validation failed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    
    def internal_error_response(
        self,
        message: Optional[str] = None
    ) -> JSONResponse:
        """Create a 500 Internal Server Error response."""
        return self.error_response(
            error="Internal server error",
            message=message or "An unexpected error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class APIVersionManager:
    """Manages API versioning and compatibility."""
    
    SUPPORTED_VERSIONS = ["1.0", "1.1"]
    DEFAULT_VERSION = "1.0"
    LATEST_VERSION = "1.1"
    
    @classmethod
    def get_version_from_header(cls, version_header: Optional[str]) -> str:
        """Extract API version from header."""
        if not version_header:
            return cls.DEFAULT_VERSION
        
        # Support formats: "1.0", "v1.0", "application/vnd.api+json;version=1.0"
        if version_header.startswith("v"):
            version = version_header[1:]
        elif "version=" in version_header:
            version = version_header.split("version=")[1].split(";")[0]
        else:
            version = version_header
        
        return version if version in cls.SUPPORTED_VERSIONS else cls.DEFAULT_VERSION
    
    @classmethod
    def get_version_from_path(cls, path: str) -> str:
        """Extract API version from URL path."""
        if "/api/v1/" in path:
            return "1.0"
        elif "/api/v1.1/" in path:
            return "1.1"
        return cls.DEFAULT_VERSION
    
    @classmethod
    def is_version_supported(cls, version: str) -> bool:
        """Check if API version is supported."""
        return version in cls.SUPPORTED_VERSIONS
    
    @classmethod
    def get_formatter(cls, version: str) -> ResponseFormatter:
        """Get response formatter for specific version."""
        if not cls.is_version_supported(version):
            version = cls.DEFAULT_VERSION
        return ResponseFormatter(version=version)


def format_response_v1_0(data: Any, message: Optional[str] = None) -> Dict[str, Any]:
    """Format response for API version 1.0."""
    response = {
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0"
    }
    
    if data is not None:
        response["data"] = data
    if message:
        response["message"] = message
    
    return response


def format_response_v1_1(data: Any, message: Optional[str] = None) -> Dict[str, Any]:
    """Format response for API version 1.1 (enhanced with metadata)."""
    response = {
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.1",
        "meta": {
            "api_version": "1.1",
            "response_time": datetime.now(timezone.utc).isoformat()
        }
    }
    
    if data is not None:
        response["data"] = data
        # Add data metadata for v1.1
        if isinstance(data, list):
            response["meta"]["count"] = len(data)
        elif isinstance(data, dict) and "items" in data:
            response["meta"]["count"] = len(data["items"])
    
    if message:
        response["message"] = message
    
    return response


# Global formatter instances
default_formatter = ResponseFormatter("1.0")
latest_formatter = ResponseFormatter("1.1")