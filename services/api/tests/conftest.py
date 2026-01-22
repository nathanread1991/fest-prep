"""Pytest configuration and fixtures for repository tests."""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from festival_playlist_generator.core.database import Base
from festival_playlist_generator.models.artist import Artist
from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.models.playlist import Playlist, StreamingPlatform
from festival_playlist_generator.models.setlist import Setlist
from festival_playlist_generator.models.user import User
from festival_playlist_generator.repositories.artist_repository import ArtistRepository
from festival_playlist_generator.repositories.festival_repository import (
    FestivalRepository,
)
from festival_playlist_generator.repositories.playlist_repository import (
    PlaylistRepository,
)
from festival_playlist_generator.repositories.setlist_repository import (
    SetlistRepository,
)
from festival_playlist_generator.repositories.user_repository import UserRepository

# Import testcontainers
try:
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    PostgresContainer = None
    RedisContainer = None


@pytest.fixture(scope="session")
def postgres_container():
    """Create a PostgreSQL container for testing (session-scoped, reused)."""
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip(
            "testcontainers not installed. Install with: "
            "pip install testcontainers[postgresql]"
        )

    container = PostgresContainer("postgres:15-alpine")
    container.start()

    yield container

    container.stop()


@pytest.fixture(scope="session")
def redis_container():
    """Create a Redis container for testing (session-scoped, reused)."""
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip(
            "testcontainers not installed. Install with: "
            "pip install testcontainers[redis]"
        )

    container = RedisContainer("redis:7-alpine")
    container.start()

    yield container

    container.stop()


@pytest.fixture(scope="session")
def database_url(postgres_container):
    """Get the database URL from the container."""
    connection_url = postgres_container.get_connection_url()

    # Replace psycopg2 driver with asyncpg
    if "postgresql://" in connection_url:
        connection_url = connection_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
    elif "postgresql+psycopg2://" in connection_url:
        connection_url = connection_url.replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )

    return connection_url


@pytest.fixture(scope="session")
def redis_url(redis_container):
    """Get the Redis URL from the container."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


@pytest_asyncio.fixture(scope="function")
async def async_engine(database_url):
    """Create a PostgreSQL async engine using testcontainer."""
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)

    # Create all tables once
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine):
    """Create an async database session for testing."""
    async_session_maker = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def artist_repository(async_session):
    """Create an ArtistRepository instance."""
    return ArtistRepository(async_session)


@pytest_asyncio.fixture(scope="function")
async def festival_repository(async_session):
    """Create a FestivalRepository instance."""
    return FestivalRepository(async_session)


@pytest_asyncio.fixture(scope="function")
async def playlist_repository(async_session):
    """Create a PlaylistRepository instance."""
    return PlaylistRepository(async_session)


@pytest_asyncio.fixture(scope="function")
async def setlist_repository(async_session):
    """Create a SetlistRepository instance."""
    return SetlistRepository(async_session)


@pytest_asyncio.fixture(scope="function")
async def user_repository(async_session):
    """Create a UserRepository instance."""
    return UserRepository(async_session)


@pytest_asyncio.fixture(scope="function")
async def sample_artist(async_session):
    """Create a sample artist for testing."""
    artist = Artist(
        name="Test Artist",
        spotify_id="test_spotify_id",
        spotify_image_url="https://example.com/image.jpg",
        spotify_popularity=75.5,
        spotify_followers=10000.0,
        genres=["rock", "indie"],
        popularity_score=0.80,
    )
    async_session.add(artist)
    await async_session.flush()
    await async_session.refresh(artist)
    return artist


@pytest_asyncio.fixture(scope="function")
async def sample_festival(async_session):
    """Create a sample festival for testing."""
    festival = Festival(
        name="Test Festival",
        dates=[datetime.utcnow() + timedelta(days=30)],
        location="Test City",
        venue="Test Venue",
        genres=["rock", "pop"],
        ticket_url="https://example.com/tickets",
    )
    async_session.add(festival)
    await async_session.flush()
    await async_session.refresh(festival)
    return festival


@pytest_asyncio.fixture(scope="function")
async def sample_user(async_session):
    """Create a sample user for testing."""
    user = User(
        email="test@example.com",
        oauth_provider="spotify",
        oauth_provider_id="test_oauth_id",
        display_name="Test User",
        marketing_opt_in=True,
    )
    async_session.add(user)
    await async_session.flush()
    await async_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def sample_playlist(async_session, sample_user, sample_festival):
    """Create a sample playlist for testing."""
    playlist = Playlist(
        name="Test Playlist",
        description="A test playlist",
        festival_id=sample_festival.id,
        user_id=sample_user.id,
        platform=StreamingPlatform.SPOTIFY,
        external_id="test_external_id",
    )
    async_session.add(playlist)
    await async_session.flush()
    await async_session.refresh(playlist)
    return playlist


@pytest_asyncio.fixture(scope="function")
async def sample_setlist(async_session, sample_artist):
    """Create a sample setlist for testing."""
    setlist = Setlist(
        artist_id=sample_artist.id,
        venue="Test Venue",
        date=datetime.utcnow(),
        songs=["Song 1", "Song 2", "Song 3"],
        tour_name="Test Tour",
        festival_name="Test Festival",
        source="setlist.fm",
    )
    async_session.add(setlist)
    await async_session.flush()
    await async_session.refresh(setlist)
    return setlist
