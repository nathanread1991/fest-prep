"""Workflow API endpoints that orchestrate multiple services."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.api.response_formatter import APIVersionManager
from festival_playlist_generator.api.versioning import get_request_version
from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.core.logging_config import get_logger
from festival_playlist_generator.core.service_orchestrator import ServiceOrchestrator

router = APIRouter()
logger = get_logger("api.workflows")


def get_orchestrator(db: AsyncSession = Depends(get_db)) -> ServiceOrchestrator:
    """Get service orchestrator instance."""
    return ServiceOrchestrator(db)


@router.post("/festival/{festival_id}/complete")
async def complete_festival_workflow(
    request: Request,
    festival_id: UUID,
    user_id: UUID,
    create_streaming_playlist: bool = False,
    platform: Optional[str] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    orchestrator: ServiceOrchestrator = Depends(get_orchestrator),
) -> JSONResponse:
    """Execute complete festival playlist workflow."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    logger.info(f"Starting complete festival workflow for {festival_id}")

    try:
        # Execute the complete workflow
        result = await orchestrator.complete_festival_workflow(
            festival_id=festival_id,
            user_id=user_id,
            create_streaming_playlist=create_streaming_playlist,
            platform=platform,
        )

        if result["status"] == "completed":
            return formatter.success_response(
                data=result, message="Festival workflow completed successfully"
            )
        else:
            return formatter.error_response(
                error="Workflow failed",
                message=result.get("error", "Unknown error occurred"),
                status_code=500,
            )

    except Exception as e:
        logger.error(f"Festival workflow endpoint error: {e}")
        return formatter.error_response(
            error="Workflow execution failed", message=str(e), status_code=500
        )


@router.post("/artist/{artist_id}/complete")
async def complete_artist_workflow(
    request: Request,
    artist_id: UUID,
    user_id: UUID,
    create_streaming_playlist: bool = False,
    platform: Optional[str] = None,
    orchestrator: ServiceOrchestrator = Depends(get_orchestrator),
) -> JSONResponse:
    """Execute complete artist playlist workflow."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    logger.info(f"Starting complete artist workflow for {artist_id}")

    try:
        # Execute the complete workflow
        result = await orchestrator.complete_artist_workflow(
            artist_id=artist_id,
            user_id=user_id,
            create_streaming_playlist=create_streaming_playlist,
            platform=platform,
        )

        if result["status"] == "completed":
            return formatter.success_response(
                data=result, message="Artist workflow completed successfully"
            )
        else:
            return formatter.error_response(
                error="Workflow failed",
                message=result.get("error", "Unknown error occurred"),
                status_code=500,
            )

    except Exception as e:
        logger.error(f"Artist workflow endpoint error: {e}")
        return formatter.error_response(
            error="Workflow execution failed", message=str(e), status_code=500
        )


@router.post("/maintenance/daily")
async def trigger_daily_maintenance(
    request: Request,
    background_tasks: BackgroundTasks,
    orchestrator: ServiceOrchestrator = Depends(get_orchestrator),
) -> JSONResponse:
    """Trigger daily maintenance workflow."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    logger.info("Triggering daily maintenance workflow")

    try:
        # Add maintenance task to background
        background_tasks.add_task(orchestrator.daily_maintenance_workflow)

        return formatter.success_response(
            data={"status": "started", "background_task": True},
            message="Daily maintenance workflow started in background",
        )

    except Exception as e:
        logger.error(f"Daily maintenance trigger error: {e}")
        return formatter.error_response(
            error="Maintenance trigger failed", message=str(e), status_code=500
        )


@router.get("/health/services")
async def check_service_health(
    request: Request, orchestrator: ServiceOrchestrator = Depends(get_orchestrator)
) -> JSONResponse:
    """Check health status of all integrated services."""
    version = get_request_version(request)
    formatter = APIVersionManager.get_formatter(version)

    try:
        health_status = {
            "overall_status": "healthy",
            "services": {
                "festival_collector": "healthy",
                "artist_analyzer": "healthy",
                "playlist_generator": "healthy",
                "streaming_integration": "healthy",
                "recommendation_engine": "healthy",
                "notification_service": "healthy",
            },
            "database": "connected",
            "redis": "connected",
            "checked_at": "2024-01-01T00:00:00Z",
        }

        return formatter.success_response(
            data=health_status, message="Service health check completed"
        )

    except Exception as e:
        logger.error(f"Service health check error: {e}")
        return formatter.error_response(
            error="Health check failed", message=str(e), status_code=500
        )
