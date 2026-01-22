"""Festival collection background tasks."""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Union

from celery import current_task

from festival_playlist_generator.core.celery_app import celery_app
from festival_playlist_generator.core.database import AsyncSessionLocal
from festival_playlist_generator.core.logging_config import get_logger
from festival_playlist_generator.core.service_orchestrator import ServiceOrchestrator
from festival_playlist_generator.schemas.festival import Festival
from festival_playlist_generator.services.festival_collector import (
    APISource,
    FestivalCollectorService,
    RawFestivalData,
    WebScrapingSource,
)

logger = get_logger("tasks.festival_collector")


class MockFestivalSource(WebScrapingSource):
    """Mock festival data source for testing and development."""

    def __init__(self) -> None:
        super().__init__("https://mock-festival-source.com", "mock_source")

    async def fetch_festivals(self) -> List[RawFestivalData]:
        """Fetch mock festival data."""
        # Generate some mock festival data for testing
        mock_festivals = [
            RawFestivalData(
                source="mock_source",
                name="Summer Music Festival 2024",
                dates=[
                    datetime(2024, 7, 15),
                    datetime(2024, 7, 16),
                    datetime(2024, 7, 17),
                ],
                location="Central Park, New York, NY",
                venue="Great Lawn",
                artists=["The Beatles", "Led Zeppelin", "Pink Floyd", "Queen"],
                genres=["Rock", "Classic Rock"],
                ticket_url="https://example.com/tickets/summer-music-2024",
            ),
            RawFestivalData(
                source="mock_source",
                name="Electronic Dance Festival",
                dates=[datetime(2024, 8, 20), datetime(2024, 8, 21)],
                location="Miami Beach, FL",
                venue="South Beach",
                artists=["Daft Punk", "Deadmau5", "Skrillex", "Calvin Harris"],
                genres=["Electronic", "EDM", "House"],
                ticket_url="https://example.com/tickets/edm-festival",
            ),
            RawFestivalData(
                source="mock_source",
                name="Jazz & Blues Weekend",
                dates=[datetime(2024, 9, 10), datetime(2024, 9, 11)],
                location="New Orleans, LA",
                venue="French Quarter",
                artists=["Miles Davis", "B.B. King", "John Coltrane", "Muddy Waters"],
                genres=["Jazz", "Blues"],
                ticket_url="https://example.com/tickets/jazz-blues",
            ),
        ]

        self.logger.info(f"Generated {len(mock_festivals)} mock festivals")
        return mock_festivals

    def validate_data(self, raw_data: Dict[str, Any]) -> bool:
        """Validate mock festival data."""
        return True  # Mock data is always valid


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)  # type: ignore[untyped-decorator]
def collect_daily_festivals(self: Any) -> Dict[str, Any]:
    """
    Collect festival data daily using the service orchestrator.

    This task:
    1. Initializes the service orchestrator
    2. Runs the daily maintenance workflow
    3. Returns comprehensive results

    Validates: Requirements 1.1
    """

    async def run_workflow() -> Dict[str, Any]:
        async with AsyncSessionLocal() as db:
            try:
                logger.info("Starting daily festival collection task via orchestrator")

                # Update task state
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "status": "Initializing service orchestrator",
                        "progress": 10,
                    },
                )

                # Initialize the service orchestrator
                orchestrator = ServiceOrchestrator(db)

                self.update_state(
                    state="PROGRESS",
                    meta={
                        "status": "Running daily maintenance workflow",
                        "progress": 30,
                    },
                )

                # Run the complete daily maintenance workflow
                result = await orchestrator.daily_maintenance_workflow()

                self.update_state(
                    state="PROGRESS",
                    meta={"status": "Processing workflow results", "progress": 80},
                )

                # Log results
                logger.info(f"Daily maintenance workflow completed: {result['status']}")

                if result["status"] == "completed":
                    self.update_state(
                        state="SUCCESS",
                        meta={
                            "status": "Daily maintenance completed",
                            "progress": 100,
                            "result": result,
                        },
                    )
                else:
                    self.update_state(
                        state="FAILURE",
                        meta={
                            "status": "Daily maintenance failed",
                            "error": result.get("error", "Unknown error"),
                        },
                    )

                return result

            except Exception as e:
                error_msg = f"Error in daily festival collection: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise

    try:
        # Run the async workflow
        import asyncio

        result = asyncio.run(run_workflow())
        return result

    except Exception as e:
        error_msg = f"Error in daily festival collection: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Update task state with error
        self.update_state(
            state="FAILURE",
            meta={"status": "Festival collection failed", "error": error_msg},
        )

        # Retry with exponential backoff
        try:
            retry_delay = min(300 * (2**self.request.retries), 3600)  # Max 1 hour
            logger.info(
                f"Retrying festival collection in {retry_delay} seconds (attempt {self.request.retries + 1}/{self.max_retries})"
            )
            self.retry(countdown=retry_delay, exc=e)
            # retry() raises an exception, so this line is never reached
            return {"status": "retrying"}  # For type checker
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for festival collection task")
            return {
                "status": "failed",
                "message": f"Festival collection failed after {self.max_retries} retries: {error_msg}",
                "error": error_msg,
                "failed_at": datetime.utcnow().isoformat(),
            }


@celery_app.task(bind=True, max_retries=2, default_retry_delay=600)  # type: ignore[untyped-decorator]
def collect_festivals_from_source(
    self: Any, source_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Collect festivals from a specific source.

    Args:
        source_config: Configuration for the data source
            {
                "type": "web_scraping" | "api",
                "url": "source_url",
                "api_key": "optional_api_key",
                "source_name": "source_identifier"
            }

    This task allows for parallel collection from multiple sources.
    """
    try:
        logger.info(
            f"Collecting festivals from source: {source_config.get('source_name', 'unknown')}"
        )

        # Create appropriate data source based on config
        source: Union[WebScrapingSource, APISource]
        if source_config["type"] == "web_scraping":
            source = WebScrapingSource(
                base_url=source_config["url"],
                source_name=source_config.get("source_name", "web_scraping"),
            )
        elif source_config["type"] == "api":
            source = APISource(
                api_url=source_config["url"],
                api_key=source_config.get("api_key"),
                source_name=source_config.get("source_name", "api"),
            )
        else:
            raise ValueError(f"Unknown source type: {source_config['type']}")

        # Collect festivals from this source
        import asyncio

        raw_festivals = asyncio.run(source.fetch_festivals())

        logger.info(
            f"Collected {len(raw_festivals)} festivals from {source.source_name}"
        )

        return {
            "status": "success",
            "source": source_config.get("source_name", "unknown"),
            "festivals_collected": len(raw_festivals),
            "completed_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        error_msg = f"Error collecting from source {source_config.get('source_name', 'unknown')}: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Retry with backoff
        try:
            retry_delay = 600 * (2**self.request.retries)  # 10 min, 20 min
            self.retry(countdown=retry_delay, exc=e)
            # retry() raises an exception, so this line is never reached
            return {"status": "retrying"}  # For type checker
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "source": source_config.get("source_name", "unknown"),
                "error": error_msg,
                "failed_at": datetime.utcnow().isoformat(),
            }


@celery_app.task(bind=True)  # type: ignore[untyped-decorator]
def cleanup_old_festivals(self: Any, days_old: int = 30) -> Dict[str, Any]:
    """
    Clean up old festival data that's no longer relevant.

    Args:
        days_old: Remove festivals older than this many days
    """
    try:
        logger.info(f"Cleaning up festivals older than {days_old} days")

        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        # This would connect to the database and remove old festivals
        # Implementation would depend on your database setup

        # Placeholder for actual cleanup logic
        cleaned_count = 0  # Would be actual count from database operation

        logger.info(f"Cleaned up {cleaned_count} old festivals")

        return {
            "status": "success",
            "message": f"Cleaned up {cleaned_count} festivals older than {days_old} days",
            "cutoff_date": cutoff_date.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        error_msg = f"Error during festival cleanup: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return {
            "status": "failed",
            "error": error_msg,
            "failed_at": datetime.utcnow().isoformat(),
        }
