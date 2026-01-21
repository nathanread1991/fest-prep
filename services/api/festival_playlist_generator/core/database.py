"""Database configuration and connection management."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG,
    future=True
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def init_db():
    """Initialize database tables."""
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they are registered
            from festival_playlist_generator.models import (
                festival, artist, setlist, song, playlist, user
            )
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        logger.warning("Continuing without database initialization - some features may not work")
        # Don't raise the exception, just log it


async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def transaction_context(session: AsyncSession = None) -> AsyncGenerator[AsyncSession, None]:
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
            exc_info=True
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
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()