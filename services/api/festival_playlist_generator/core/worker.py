"""Celery worker management utilities."""

import logging
import signal
import sys
from typing import Any, Callable, Optional

from celery import Celery

from festival_playlist_generator.core.celery_app import celery_app

logger = logging.getLogger(__name__)


class WorkerManager:
    """Manages Celery worker lifecycle."""

    def __init__(self, app: Celery) -> None:
        self.app = app
        self.worker: Optional[Any] = None

    def start_worker(
        self,
        loglevel: str = "INFO",
        concurrency: Optional[int] = None,
        queues: Optional[list[str]] = None,
    ) -> None:
        """Start a Celery worker with specified configuration."""
        try:
            # Default queues
            if queues is None:
                queues = ["data_collection", "playlist_updates", "celery"]

            # Worker arguments
            worker_args = [
                "--loglevel",
                loglevel,
                "--queues",
                ",".join(queues),
            ]

            if concurrency:
                worker_args.extend(["--concurrency", str(concurrency)])

            logger.info(f"Starting Celery worker with args: {worker_args}")

            # Start worker
            self.app.worker_main(worker_args)

        except KeyboardInterrupt:
            logger.info("Worker interrupted by user")
            self.stop_worker()
        except Exception as e:
            logger.error(f"Error starting worker: {e}")
            raise

    def stop_worker(self) -> None:
        """Stop the Celery worker gracefully."""
        if self.worker:
            logger.info("Stopping Celery worker...")
            self.worker.stop()
            self.worker = None

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: Any) -> None:
            logger.info(f"Received signal {signum}, shutting down worker...")
            self.stop_worker()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


def start_worker_cli() -> None:
    """CLI entry point for starting a worker."""
    import argparse

    parser = argparse.ArgumentParser(description="Start Celery worker")
    parser.add_argument("--loglevel", default="INFO", help="Log level")
    parser.add_argument("--concurrency", type=int, help="Number of worker processes")
    parser.add_argument("--queues", nargs="+", help="Queues to consume from")

    args = parser.parse_args()

    manager = WorkerManager(celery_app)
    manager.setup_signal_handlers()
    manager.start_worker(
        loglevel=args.loglevel, concurrency=args.concurrency, queues=args.queues
    )


if __name__ == "__main__":
    start_worker_cli()
