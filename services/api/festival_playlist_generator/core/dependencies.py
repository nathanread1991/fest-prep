"""Dependency injection for services."""

from functools import lru_cache
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.core.service_orchestrator import ServiceOrchestrator
from festival_playlist_generator.services import (
    FestivalCollectorService,
    ArtistAnalyzerService,
    PlaylistGeneratorService,
    StreamingIntegrationService,
    RecommendationEngine,
    NotificationService
)


@lru_cache()
def get_festival_collector_service() -> FestivalCollectorService:
    """Get Festival Collector Service instance."""
    return FestivalCollectorService()


@lru_cache()
def get_artist_analyzer_service() -> ArtistAnalyzerService:
    """Get Artist Analyzer Service instance."""
    return ArtistAnalyzerService()


@lru_cache()
def get_playlist_generator_service() -> PlaylistGeneratorService:
    """Get Playlist Generator Service instance."""
    return PlaylistGeneratorService()


@lru_cache()
def get_streaming_integration_service() -> StreamingIntegrationService:
    """Get Streaming Integration Service instance."""
    # Default configuration for testing/development
    default_config = {
        "spotify": {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "redirect_uri": "http://localhost:8000/callback/spotify"
        },
        "youtube_music": {
            "oauth_file": "/tmp/test_oauth.json"
        },
        "apple_music": {
            "developer_token": "test_developer_token"
        }
    }
    return StreamingIntegrationService(default_config)


@lru_cache()
def get_recommendation_engine() -> RecommendationEngine:
    """Get Recommendation Engine instance."""
    return RecommendationEngine()


@lru_cache()
def get_notification_service() -> NotificationService:
    """Get Notification Service instance."""
    return NotificationService()


@lru_cache()
def get_service_orchestrator() -> ServiceOrchestrator:
    """Get Service Orchestrator instance."""
    return ServiceOrchestrator()


# Service dependencies for FastAPI
def get_orchestrator(
    orchestrator: ServiceOrchestrator = Depends(get_service_orchestrator)
) -> ServiceOrchestrator:
    """Get Service Orchestrator for FastAPI endpoints."""
    return orchestrator
def get_festival_collector(
    db: AsyncSession = Depends(get_db),
    service: FestivalCollectorService = Depends(get_festival_collector_service)
) -> FestivalCollectorService:
    """Get Festival Collector Service with database session."""
    service.db = db
    return service


def get_artist_analyzer(
    db: AsyncSession = Depends(get_db),
    service: ArtistAnalyzerService = Depends(get_artist_analyzer_service)
) -> ArtistAnalyzerService:
    """Get Artist Analyzer Service with database session."""
    service.db = db
    return service


def get_playlist_generator(
    db: AsyncSession = Depends(get_db),
    service: PlaylistGeneratorService = Depends(get_playlist_generator_service)
) -> PlaylistGeneratorService:
    """Get Playlist Generator Service with database session."""
    service.db = db
    return service


def get_streaming_integration(
    db: AsyncSession = Depends(get_db),
    service: StreamingIntegrationService = Depends(get_streaming_integration_service)
) -> StreamingIntegrationService:
    """Get Streaming Integration Service with database session."""
    service.db = db
    return service


def get_recommendation_service(
    db: AsyncSession = Depends(get_db),
    service: RecommendationEngine = Depends(get_recommendation_engine)
) -> RecommendationEngine:
    """Get Recommendation Engine with database session."""
    service.db = db
    return service


def get_notification_service_dep(
    db: AsyncSession = Depends(get_db),
    service: NotificationService = Depends(get_notification_service)
) -> NotificationService:
    """Get Notification Service with database session."""
    service.db = db
    return service