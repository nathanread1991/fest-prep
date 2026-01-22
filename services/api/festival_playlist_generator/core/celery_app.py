"""Celery application configuration."""

import logging
from typing import Any

from celery import Celery
from celery.signals import worker_ready, worker_shutting_down

from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "festival_playlist_generator",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "festival_playlist_generator.tasks.festival_collector",
        "festival_playlist_generator.tasks.playlist_updater",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task execution
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    # Result backend
    result_expires=3600,  # 1 hour
    result_persistent=True,
    # Retry configuration
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    # Security
    worker_hijack_root_logger=False,
    worker_log_color=False,
)

# Periodic tasks configuration
celery_app.conf.beat_schedule = {
    "daily-festival-collection": {
        "task": "festival_playlist_generator.tasks.festival_collector.collect_daily_festivals",
        "schedule": 86400.0,  # Run daily (24 hours)
        "options": {
            "expires": 3600,  # Task expires after 1 hour if not executed
        },
    },
    "update-playlists": {
        "task": "festival_playlist_generator.tasks.playlist_updater.update_all_playlists",
        "schedule": 604800.0,  # Run weekly (7 days)
        "options": {
            "expires": 7200,  # Task expires after 2 hours if not executed
        },
    },
}


# Worker event handlers
@worker_ready.connect  # type: ignore[untyped-decorator]
def worker_ready_handler(sender: Any = None, **kwargs: Any) -> None:
    """Handle worker ready event."""
    logger.info(f"Celery worker {sender} is ready")


@worker_shutting_down.connect  # type: ignore[untyped-decorator]
def worker_shutting_down_handler(sender: Any = None, **kwargs: Any) -> None:
    """Handle worker shutdown event."""
    logger.info(f"Celery worker {sender} is shutting down")


# Task routing (for future scaling)
celery_app.conf.task_routes = {
    "festival_playlist_generator.tasks.festival_collector.*": {
        "queue": "data_collection"
    },
    "festival_playlist_generator.tasks.playlist_updater.*": {
        "queue": "playlist_updates"
    },
}
