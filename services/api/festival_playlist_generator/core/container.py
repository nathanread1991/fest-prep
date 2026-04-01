"""Dependency injection container for the application."""

from dependency_injector import containers, providers
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.core.database import AsyncSessionLocal, get_db

# Import repositories
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
from festival_playlist_generator.services.artist_service import ArtistService

# Import services
from festival_playlist_generator.services.cache_service import CacheService
from festival_playlist_generator.services.festival_service import FestivalService
from festival_playlist_generator.services.playlist_service import PlaylistService
from festival_playlist_generator.services.setlistfm_service import SetlistFmService
from festival_playlist_generator.services.spotify_service import SpotifyService
from festival_playlist_generator.services.user_service import UserService


class Container(containers.DeclarativeContainer):
    """Dependency injection container for all services and repositories."""

    # Configuration
    config = providers.Configuration()

    # Database session factory
    db_session_factory = providers.Singleton(lambda: AsyncSessionLocal)

    # Cache service (initialized without redis_client, will create its own pool lazily)
    cache_service = providers.Singleton(CacheService, redis_client=None)

    # Repositories
    artist_repository = providers.Factory(
        ArtistRepository, session=providers.Dependency()
    )

    festival_repository = providers.Factory(
        FestivalRepository, session=providers.Dependency()
    )

    playlist_repository = providers.Factory(
        PlaylistRepository, session=providers.Dependency()
    )

    setlist_repository = providers.Factory(
        SetlistRepository, session=providers.Dependency()
    )

    user_repository = providers.Factory(UserRepository, session=providers.Dependency())

    # Services
    artist_service = providers.Factory(
        ArtistService, artist_repository=artist_repository, cache_service=cache_service
    )

    festival_service = providers.Factory(
        FestivalService,
        festival_repository=festival_repository,
        artist_repository=artist_repository,
        cache_service=cache_service,
    )

    playlist_service = providers.Factory(
        PlaylistService,
        playlist_repository=playlist_repository,
        festival_repository=festival_repository,
        artist_repository=artist_repository,
        cache_service=cache_service,
    )

    user_service = providers.Factory(
        UserService, user_repository=user_repository, cache_service=cache_service
    )

    spotify_service = providers.Singleton(SpotifyService)

    setlistfm_service = providers.Singleton(SetlistFmService)


# Global container instance
container = Container()


# Dependency providers for FastAPI
def get_artist_service(db: AsyncSession = Depends(get_db)) -> ArtistService:
    """Get ArtistService instance with database session."""
    artist_repo = ArtistRepository(db)
    cache_service = container.cache_service()
    return ArtistService(artist_repository=artist_repo, cache_service=cache_service)


def get_festival_service(db: AsyncSession = Depends(get_db)) -> FestivalService:
    """Get FestivalService instance with database session."""
    festival_repo = FestivalRepository(db)
    artist_repo = ArtistRepository(db)
    cache_service = container.cache_service()
    return FestivalService(
        festival_repository=festival_repo,
        artist_repository=artist_repo,
        cache_service=cache_service,
    )


def get_playlist_service(db: AsyncSession = Depends(get_db)) -> PlaylistService:
    """Get PlaylistService instance with database session."""
    playlist_repo = PlaylistRepository(db)
    festival_repo = FestivalRepository(db)
    cache_service = container.cache_service()
    return PlaylistService(
        playlist_repository=playlist_repo,
        festival_repository=festival_repo,
        cache_service=cache_service,
    )


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """Get UserService instance with database session."""
    user_repo = UserRepository(db)
    cache_service = container.cache_service()
    return UserService(user_repository=user_repo, cache_service=cache_service)


def get_cache_service() -> CacheService:
    """Get CacheService singleton instance."""
    service: CacheService = container.cache_service()
    return service
