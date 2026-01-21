"""Centralized logging configuration for the application."""

import json
import logging
import logging.config
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from festival_playlist_generator.core.config import settings

# Context variable for request ID
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging.

    Outputs logs in JSON format with required fields:
    - timestamp: ISO 8601 formatted timestamp
    - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - message: Log message
    - request_id: Request ID from context (if available)
    - service_name: Name of the service
    - logger: Logger name
    - module: Module name
    - function: Function name
    - line: Line number
    - exception: Exception details with stack trace (if present)
    """

    def __init__(self, service_name: str = "festival-playlist-generator"):
        """Initialize JSON formatter.

        Args:
            service_name: Name of the service for identification
        """
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON formatted log string
        """
        # Build base log entry
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "service_name": self.service_name,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request ID from context if available
        request_id = request_id_var.get()
        if request_id:
            log_entry["request_id"] = request_id

        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "stacktrace": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry)


def setup_logging() -> None:
    """Configure application-wide logging."""

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Determine environment
    environment = getattr(settings, "ENVIRONMENT", "development")
    is_production = environment == "production"

    # Configure log level based on environment
    if is_production:
        default_level = "INFO"
        console_level = "WARNING"
    elif settings.DEBUG:
        default_level = "DEBUG"
        console_level = "DEBUG"
    else:
        default_level = "INFO"
        console_level = "INFO"

    # Logging configuration
    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "()": JSONFormatter,
                "service_name": "festival-playlist-generator",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": console_level,
                "formatter": "json" if is_production else "default",
                "stream": sys.stdout,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": default_level,
                "formatter": "json",
                "filename": log_dir / "app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json",
                "filename": log_dir / "error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
            },
        },
        "loggers": {
            "festival_playlist_generator": {
                "level": default_level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": ["file"],
                "propagate": False,
            },
            "celery": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["console", "file"],
        },
    }

    # Apply configuration
    logging.config.dictConfig(logging_config)

    # Set up specific loggers for different components
    setup_component_loggers()


def setup_component_loggers() -> None:
    """Set up loggers for specific application components."""

    # Determine environment
    environment = getattr(settings, "ENVIRONMENT", "development")
    is_production = environment == "production"

    # Set log level based on environment
    if is_production:
        component_level = logging.INFO
    elif settings.DEBUG:
        component_level = logging.DEBUG
    else:
        component_level = logging.INFO

    # Service loggers
    service_logger = logging.getLogger("festival_playlist_generator.services")
    service_logger.setLevel(component_level)

    # API loggers
    api_logger = logging.getLogger("festival_playlist_generator.api")
    api_logger.setLevel(component_level)

    # Database loggers
    db_logger = logging.getLogger("festival_playlist_generator.database")
    db_logger.setLevel(logging.INFO)

    # External API loggers
    external_logger = logging.getLogger("festival_playlist_generator.external")
    external_logger.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific component."""
    return logging.getLogger(f"festival_playlist_generator.{name}")


def set_request_id(request_id: str) -> None:
    """Set the request ID in context for logging.

    Args:
        request_id: Unique request identifier
    """
    request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context.

    Returns:
        Request ID if set, None otherwise
    """
    return request_id_var.get()


def clear_request_id() -> None:
    """Clear the request ID from context."""
    request_id_var.set(None)


# Context manager for request logging
class RequestLoggingContext:
    """Context manager for request-specific logging."""

    def __init__(self, request_id: str, endpoint: str, user_id: str = None):
        self.request_id = request_id
        self.endpoint = endpoint
        self.user_id = user_id
        self.logger = get_logger("api.requests")

    def __enter__(self):
        self.logger.info(
            f"Request started - ID: {self.request_id}, Endpoint: {self.endpoint}, User: {self.user_id}"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(
                f"Request failed - ID: {self.request_id}, Error: {exc_type.__name__}: {exc_val}"
            )
        else:
            self.logger.info(f"Request completed - ID: {self.request_id}")


# Service operation logging decorator
def log_service_operation(operation_name: str):
    """Decorator to log service operations."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger("services")
            logger.info(f"Starting {operation_name}")
            try:
                result = func(*args, **kwargs)
                logger.info(f"Completed {operation_name}")
                return result
            except Exception as e:
                logger.error(f"Failed {operation_name}: {e}")
                raise

        return wrapper

    return decorator
