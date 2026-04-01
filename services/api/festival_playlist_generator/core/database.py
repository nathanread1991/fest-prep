"""Database configuration and connection management.

Supports both local Docker (PostgreSQL) and AWS (Aurora Serverless v2)
deployments. In AWS, the DATABASE_URL is injected by ECS from Secrets Manager.

Aurora Serverless v2 specifics:
- Connection pooling tuned for serverless scaling (0.5-4 ACU)
- SSL/TLS enabled via connect_args when in AWS
- Pool pre-ping to handle Aurora auto-pause wake-up
- Reduced pool size to avoid exhausting serverless connections

Slow query logging:
- Queries exceeding SLOW_QUERY_THRESHOLD_MS (default 100ms) are logged
- Logs include duration, truncated SQL statement, and parameters
- Structured JSON fields for CloudWatch Logs Insights integration
"""

import logging
import ssl as ssl_module
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional, Sequence, Tuple

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from festival_playlist_generator.core.aws_config import is_aws_environment
from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)

# Slow query threshold in milliseconds
SLOW_QUERY_THRESHOLD_MS: float = 100.0


def _build_engine_kwargs() -> Tuple[str, Dict[str, Any]]:
    """Build SQLAlchemy engine URL and keyword arguments based on environment.

    Returns:
        Tuple of (database_url, engine_kwargs).
    """
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    kwargs: Dict[str, Any] = {
        "echo": settings.DEBUG,
        "future": True,
        "pool_pre_ping": True,
    }

    if is_aws_environment():
        # Aurora Serverless v2 connection pooling settings:
        # - Smaller pool for serverless (ACU-based connection limits)
        # - Longer recycle to handle auto-pause wake-up latency
        # - Pre-ping catches stale connections after auto-pause
        kwargs.update(
            {
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 900,
            }
        )

        # Enable SSL/TLS for RDS connections
        ssl_context = ssl_module.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl_module.CERT_NONE
        kwargs["connect_args"] = {"ssl": ssl_context}

        logger.info(
            "Database engine configured for AWS Aurora Serverless v2 "
            "(SSL enabled, pool_size=5, max_overflow=10)"
        )
    else:
        # Local Docker development settings
        kwargs.update(
            {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 1800,
            }
        )

    return db_url, kwargs


# Build engine configuration
_db_url, _engine_kwargs = _build_engine_kwargs()

# Create async engine
engine = create_async_engine(_db_url, **_engine_kwargs)


# ---------------------------------------------------------------------------
# Slow query performance logging via SQLAlchemy engine events
# ---------------------------------------------------------------------------


def _before_cursor_execute(
    conn: Connection,
    cursor: Any,
    statement: str,
    parameters: Optional[Sequence[Any]],
    context: Any,
    executemany: bool,
) -> None:
    """Record query start time before execution."""
    conn.info["query_start_time"] = time.monotonic()


def _after_cursor_execute(
    conn: Connection,
    cursor: Any,
    statement: str,
    parameters: Optional[Sequence[Any]],
    context: Any,
    executemany: bool,
) -> None:
    """Log slow queries that exceed the threshold."""
    start_time: Optional[float] = conn.info.get("query_start_time")
    if start_time is None:
        return

    duration_ms = (time.monotonic() - start_time) * 1000.0

    if duration_ms >= SLOW_QUERY_THRESHOLD_MS:
        # Truncate long SQL statements for readability
        truncated_sql = statement[:500] + "..." if len(statement) > 500 else statement
        logger.warning(
            "Slow database query detected",
            extra={
                "extra_fields": {
                    "slow_query": True,
                    "duration_ms": round(duration_ms, 2),
                    "query": truncated_sql,
                    "threshold_ms": SLOW_QUERY_THRESHOLD_MS,
                }
            },
        )


def _register_slow_query_listeners(sync_engine: Engine) -> None:
    """Attach before/after cursor-execute listeners to the sync engine."""
    event.listen(sync_engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(sync_engine, "after_cursor_execute", _after_cursor_execute)


# Register listeners on the underlying synchronous engine used by asyncpg
_register_slow_query_listeners(engine.sync_engine)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base class for all database models."""


async def init_db() -> None:
    """Initialize database tables."""
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they are registered
            pass

            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        logger.warning(
            "Continuing without database initialization - some features may not work"
        )
        # Don't raise the exception, just log it


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def transaction_context(
    session: AsyncSession | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database transactions.

    Provides automatic transaction management with:
    - Automatic commit on success
    - Automatic rollback on exceptions
    - Transaction logging

    Usage:
        async with transaction_context() as session:
            # Perform database operations
            await session.execute(...)
            # Transaction is automatically committed

    Args:
        session: Optional existing session to use. If None, creates a new session.

    Yields:
        AsyncSession: Database session with active transaction

    Raises:
        Exception: Re-raises any exception after rollback
    """
    # Create new session if not provided
    if session is None:
        async with AsyncSessionLocal() as new_session:
            async with transaction_context(new_session) as txn_session:
                yield txn_session
        return

    # Use provided session
    logger.debug("Starting database transaction")

    try:
        # Begin transaction (if not already in one)
        if not session.in_transaction():
            await session.begin()

        yield session

        # Commit transaction on success
        await session.commit()
        logger.debug("Database transaction committed successfully")

    except Exception as e:
        # Rollback transaction on error
        await session.rollback()
        logger.error(
            f"Database transaction rolled back due to error: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__}},
            exc_info=True,
        )
        raise

    finally:
        # Ensure session is closed if we created it
        if session.is_active:
            await session.close()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session for use outside of FastAPI dependency injection.

    This is useful for background tasks, scripts, or other contexts where
    FastAPI's dependency injection is not available.

    Usage:
        async with get_db_session() as session:
            # Use session
            result = await session.execute(...)

    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
