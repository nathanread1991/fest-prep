"""Celery monitoring utilities."""

import logging
from typing import Dict, List, Optional

from celery import Celery
from celery.events.state import State

from festival_playlist_generator.core.celery_app import celery_app

logger = logging.getLogger(__name__)


class TaskMonitor:
    """Monitor Celery tasks and workers."""

    def __init__(self, app: Celery):
        self.app = app
        self.state = State()

    def get_active_tasks(self) -> Dict:
        """Get currently active tasks."""
        try:
            inspect = self.app.control.inspect()
            active_tasks = inspect.active()
            return active_tasks or {}
        except Exception as e:
            logger.error(f"Error getting active tasks: {e}")
            return {}

    def get_scheduled_tasks(self) -> Dict:
        """Get scheduled tasks."""
        try:
            inspect = self.app.control.inspect()
            scheduled_tasks = inspect.scheduled()
            return scheduled_tasks or {}
        except Exception as e:
            logger.error(f"Error getting scheduled tasks: {e}")
            return {}

    def get_worker_stats(self) -> Dict:
        """Get worker statistics."""
        try:
            inspect = self.app.control.inspect()
            stats = inspect.stats()
            return stats or {}
        except Exception as e:
            logger.error(f"Error getting worker stats: {e}")
            return {}

    def get_registered_tasks(self) -> Dict:
        """Get registered tasks on workers."""
        try:
            inspect = self.app.control.inspect()
            registered = inspect.registered()
            return registered or {}
        except Exception as e:
            logger.error(f"Error getting registered tasks: {e}")
            return {}

    def ping_workers(self) -> Dict:
        """Ping all workers to check if they're alive."""
        try:
            inspect = self.app.control.inspect()
            pong = inspect.ping()
            return pong or {}
        except Exception as e:
            logger.error(f"Error pinging workers: {e}")
            return {}

    def get_queue_lengths(self) -> Dict:
        """Get queue lengths (requires Redis broker)."""
        try:
            # This is a simplified version - in production you might want
            # to connect directly to Redis to get accurate queue lengths
            inspect = self.app.control.inspect()
            reserved = inspect.reserved()
            return reserved or {}
        except Exception as e:
            logger.error(f"Error getting queue lengths: {e}")
            return {}

    def revoke_task(self, task_id: str, terminate: bool = False) -> bool:
        """Revoke a task by ID."""
        try:
            self.app.control.revoke(task_id, terminate=terminate)
            logger.info(f"Task {task_id} revoked (terminate={terminate})")
            return True
        except Exception as e:
            logger.error(f"Error revoking task {task_id}: {e}")
            return False

    def get_task_info(self, task_id: str) -> Optional[Dict]:
        """Get information about a specific task."""
        try:
            result = self.app.AsyncResult(task_id)
            return {
                "id": task_id,
                "status": result.status,
                "result": result.result,
                "traceback": result.traceback,
                "date_done": result.date_done,
            }
        except Exception as e:
            logger.error(f"Error getting task info for {task_id}: {e}")
            return None

    def health_check(self) -> Dict:
        """Perform a comprehensive health check."""
        health = {
            "workers": {},
            "queues": {},
            "broker": "unknown",
            "overall_status": "healthy",
        }

        try:
            # Check workers
            workers = self.ping_workers()
            health["workers"] = {
                "count": len(workers),
                "online": list(workers.keys()),
                "status": "healthy" if workers else "no_workers",
            }

            # Check broker connection
            try:
                self.app.broker_connection().ensure_connection(max_retries=1)
                health["broker"] = "connected"
            except Exception:
                health["broker"] = "disconnected"
                health["overall_status"] = "unhealthy"

            # Check if we have workers
            if not workers:
                health["overall_status"] = "degraded"

        except Exception as e:
            logger.error(f"Error during health check: {e}")
            health["overall_status"] = "error"
            health["error"] = str(e)

        return health


def monitor_cli():
    """CLI entry point for monitoring."""
    import argparse
    import json
    import time

    parser = argparse.ArgumentParser(description="Monitor Celery tasks")
    parser.add_argument(
        "--command",
        choices=["status", "health", "tasks", "workers"],
        default="status",
        help="Monitoring command",
    )
    parser.add_argument(
        "--watch", action="store_true", help="Watch mode (refresh every 5 seconds)"
    )

    args = parser.parse_args()

    monitor = TaskMonitor(celery_app)

    def print_status():
        if args.command == "health":
            health = monitor.health_check()
            print(json.dumps(health, indent=2, default=str))
        elif args.command == "tasks":
            active = monitor.get_active_tasks()
            scheduled = monitor.get_scheduled_tasks()
            print("Active tasks:")
            print(json.dumps(active, indent=2, default=str))
            print("\nScheduled tasks:")
            print(json.dumps(scheduled, indent=2, default=str))
        elif args.command == "workers":
            stats = monitor.get_worker_stats()
            print(json.dumps(stats, indent=2, default=str))
        else:  # status
            health = monitor.health_check()
            active = monitor.get_active_tasks()
            print(f"Overall Status: {health['overall_status']}")
            print(f"Workers Online: {len(health['workers']['online'])}")
            print(f"Broker Status: {health['broker']}")
            print(f"Active Tasks: {sum(len(tasks) for tasks in active.values())}")

    if args.watch:
        try:
            while True:
                print("\033[2J\033[H")  # Clear screen
                print_status()
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
    else:
        print_status()


if __name__ == "__main__":
    monitor_cli()
