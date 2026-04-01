"""Database query metrics via SQLAlchemy engine events.

Hooks into SQLAlchemy's ``before_cursor_execute`` / ``after_cursor_execute``
events to track query count and latency, then publishes to CloudWatch.

Requirements: US-5.2
"""

import logging
import time
from typing import Any, Optional, Sequence, Tuple

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from festival_playlist_generator.core.metrics import metrics_client

logger = logging.getLogger(__name__)

# Key used to stash the start time on the connection info dict
_START_KEY = "_query_start_time"


def _before_cursor_execute(
    conn: Connection,
    cursor: Any,
    statement: str,
    parameters: Optional[Sequence[Any] | dict[str, Any]],
    context: Any,
    executemany: bool,
) -> None:
    """Record query start time."""
    conn.info[_START_KEY] = time.monotonic()


def _after_cursor_execute(
    conn: Connection,
    cursor: Any,
    statement: str,
    parameters: Optional[Sequence[Any] | dict[str, Any]],
    context: Any,
    executemany: bool,
) -> None:
    """Publish query count and latency metrics."""
    start: Optional[float] = conn.info.pop(_START_KEY, None)
    if start is None:
        return

    latency_ms = (time.monotonic() - start) * 1000.0

    # Determine a short operation label from the SQL statement
    operation = _extract_operation(statement)
    dims = {"Operation": operation}

    # Use the event loop–safe fire-and-forget helper.
    # SQLAlchemy sync events run inside run_in_executor, so we schedule
    # the coroutine on the running loop without awaiting it here.
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_publish_db_metrics(latency_ms, dims))
    except RuntimeError:
        # No running loop (e.g. during tests) – just log
        logger.debug(f"DB metric (no loop): {operation} {latency_ms:.1f}ms")


async def _publish_db_metrics(latency_ms: float, dims: dict[str, str]) -> None:
    """Publish database metrics to the metrics client."""
    await metrics_client.put_metric("DBQueryCount", 1.0, "Count", dims)
    await metrics_client.put_metric("DBQueryLatency", latency_ms, "Milliseconds", dims)


def _extract_operation(statement: str) -> str:
    """Return the SQL operation verb (SELECT, INSERT, etc.)."""
    stripped = statement.strip().upper()
    for op in ("SELECT", "INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT", "ROLLBACK"):
        if stripped.startswith(op):
            return op
    return "OTHER"


def register_db_metrics(async_engine: AsyncEngine) -> None:
    """Attach query-metric event listeners to the given async engine.

    Call this once during application startup after the engine is created.

    Args:
        async_engine: The SQLAlchemy async engine to instrument.
    """
    sync_engine: Engine = async_engine.sync_engine
    event.listen(sync_engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(sync_engine, "after_cursor_execute", _after_cursor_execute)
    logger.info("Database query metrics listeners registered")
