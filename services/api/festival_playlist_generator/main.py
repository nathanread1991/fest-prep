"""Main FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, Dict, Union, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from festival_playlist_generator.api.auth import api_auth_router
from festival_playlist_generator.api.cache_middleware import (
    APICacheMiddleware,
    ConditionalCacheMiddleware,
)
from festival_playlist_generator.api.compression import (
    CompressionMiddleware,
    StaticFileCompressionMiddleware,
)
from festival_playlist_generator.api.exception_handlers import (
    CircuitBreakerOpenError,
    circuit_breaker_handler,
    general_exception_handler,
    http_exception_handler,
    integrity_error_handler,
    pydantic_validation_exception_handler,
    sqlalchemy_error_handler,
    validation_exception_handler,
)
from festival_playlist_generator.api.metrics_middleware import MetricsMiddleware
from festival_playlist_generator.api.middleware import (
    APILoggingMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
)
from festival_playlist_generator.api.routes import api_router
from festival_playlist_generator.api.versioning import APIVersioningMiddleware
from festival_playlist_generator.api.xray_middleware import XRayMiddleware
from festival_playlist_generator.core.config import settings
from festival_playlist_generator.core.database import init_db
from festival_playlist_generator.core.logging_config import get_logger, setup_logging
from festival_playlist_generator.core.metrics import metrics_client
from festival_playlist_generator.core.redis import init_redis
from festival_playlist_generator.core.xray import configure_xray
from festival_playlist_generator.core.xray_sampling import apply_sampling_rules
from festival_playlist_generator.web.admin import admin_router
from festival_playlist_generator.web.auth_routes import auth_router
from festival_playlist_generator.web.routes import web_router

# Configure logging
setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    logger.info("Starting Festival Playlist Generator...")

    # Validate AWS environment variables if running in ECS
    from festival_playlist_generator.core.aws_config import validate_aws_environment

    try:
        validate_aws_environment()
    except Exception as e:
        logger.error(f"AWS environment validation failed: {e}")

    await init_db()
    await init_redis()
    await metrics_client.start()
    configure_xray()
    apply_sampling_rules()

    # Register database query metrics on the engine
    from festival_playlist_generator.core.database import engine as db_engine
    from festival_playlist_generator.core.db_metrics import register_db_metrics

    register_db_metrics(db_engine)

    # Optionally warm image cache on startup
    if settings.IMAGE_CACHE_ENABLED and getattr(
        settings, "WARM_CACHE_ON_STARTUP", False
    ):
        logger.info("Warming image cache on startup...")
        try:
            from festival_playlist_generator.core.database import AsyncSessionLocal
            from festival_playlist_generator.services.cache_warmer import cache_warmer

            async with AsyncSessionLocal() as db:
                stats = await cache_warmer.warm_cache(db)
                logger.info(
                    f"Cache warming complete: {stats['successful']} successful, "
                    f"{stats['failed']} failed, {stats['skipped']} skipped"
                )
        except Exception as e:
            logger.error(f"Error warming cache on startup: {e}")

    yield
    # Shutdown
    logger.info("Shutting down Festival Playlist Generator...")
    await metrics_client.stop()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Festival Playlist Generator",
        description=(
            "A system for creating playlists based on festival lineups "
            "and artist setlists"
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add custom middleware (order matters - last added is executed first)
    app.add_middleware(APILoggingMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(XRayMiddleware)  # X-Ray tracing (outermost)
    app.add_middleware(RequestIDMiddleware)  # Add request ID middleware
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(APIVersioningMiddleware)
    app.add_middleware(CompressionMiddleware)
    app.add_middleware(StaticFileCompressionMiddleware)
    app.add_middleware(APICacheMiddleware)
    app.add_middleware(ConditionalCacheMiddleware)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files
    from pathlib import Path

    # Get the directory where this file is located
    base_dir = Path(__file__).parent
    static_dir = base_dir / "web" / "static"

    app.mount(
        "/static",
        StaticFiles(directory=str(static_dir)),
        name="static",
    )

    # Include web routes (before API routes to handle root path)
    app.include_router(web_router)

    # Include auth routes
    app.include_router(auth_router)

    # Include API auth routes
    app.include_router(api_auth_router)

    # Include admin routes
    app.include_router(admin_router, prefix="/admin")

    # Include API routes
    app.include_router(api_router, prefix="/api/v1")

    # Include v1.1 routes for enhanced API
    app.include_router(api_router, prefix="/api/v1.1")

    # Add exception handlers
    # Cast handlers to the correct type for FastAPI
    ExceptionHandler = Callable[
        [Request, Exception], Union[Response, Awaitable[Response]]
    ]

    app.add_exception_handler(
        HTTPException, cast(ExceptionHandler, http_exception_handler)
    )
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, validation_exception_handler)
    )
    app.add_exception_handler(
        IntegrityError, cast(ExceptionHandler, integrity_error_handler)
    )
    app.add_exception_handler(
        SQLAlchemyError, cast(ExceptionHandler, sqlalchemy_error_handler)
    )
    app.add_exception_handler(
        CircuitBreakerOpenError, cast(ExceptionHandler, circuit_breaker_handler)
    )
    app.add_exception_handler(
        ValidationError, cast(ExceptionHandler, pydantic_validation_exception_handler)
    )
    app.add_exception_handler(
        Exception, cast(ExceptionHandler, general_exception_handler)
    )

    @app.get("/api")
    async def api_root(request: Request) -> Dict[str, Any]:
        from festival_playlist_generator.api.versioning import (
            get_request_version,
            version_compatible_response,
        )

        get_request_version(request)
        return version_compatible_response(
            request,
            {"message": "Festival Playlist Generator API", "version": "0.1.0"},
            "Welcome to the Festival Playlist Generator API",
        )

    @app.get("/health")
    @app.options("/health")
    async def health_check(request: Request) -> Dict[str, Any]:
        from festival_playlist_generator.api.versioning import (
            version_compatible_response,
        )

        return version_compatible_response(
            request, {"status": "healthy"}, "Service is running normally"
        )

    return app


app = create_app()

if __name__ == "__main__":
    from pathlib import Path

    import uvicorn

    # Determine SSL configuration
    use_https = settings.USE_HTTPS
    ssl_cert_path = settings.SSL_CERT_PATH
    ssl_key_path = settings.SSL_KEY_PATH

    # Auto-detect SSL certificates if USE_HTTPS not explicitly set
    if not use_https and settings.SSL_AUTO_GENERATE:
        cert_file = Path(ssl_cert_path)
        key_file = Path(ssl_key_path)
        if cert_file.exists() and key_file.exists():
            use_https = True
            logger.info("SSL certificates detected - enabling HTTPS")

    # Configure uvicorn
    uvicorn_config: Dict[str, Any] = {
        "app": "festival_playlist_generator.main:app",
        "host": "0.0.0.0",  # nosec B104
        "port": 8000,
        "reload": True,
    }

    # Add SSL configuration if enabled
    if use_https:
        cert_file = Path(ssl_cert_path)
        key_file = Path(ssl_key_path)

        if cert_file.exists() and key_file.exists():
            uvicorn_config["ssl_certfile"] = str(cert_file)
            uvicorn_config["ssl_keyfile"] = str(key_file)
            logger.info(f"🔒 HTTPS enabled with certificate: {ssl_cert_path}")
            logger.info("🌐 Server will be available at: https://localhost:8000")
        else:
            logger.warning("⚠️  SSL enabled but certificates not found:")
            logger.warning(f"   Certificate: {ssl_cert_path}")
            logger.warning(f"   Key: {ssl_key_path}")
            logger.warning("   Run: ./scripts/setup-ssl.sh")
            logger.info("🌐 Falling back to HTTP: http://localhost:8000")
    else:
        logger.info("🌐 Server will be available at: http://localhost:8000")

    uvicorn.run(**uvicorn_config)
