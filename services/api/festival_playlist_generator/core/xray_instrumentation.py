"""X-Ray instrumentation for database, Redis, and external API calls.

Provides functions to add X-Ray subsegments around key I/O operations
so that traces show time spent in each dependency. When X-Ray is
disabled all helpers are no-ops.

Requirements: US-5.5
"""

import logging
from typing import Any, Optional

from festival_playlist_generator.core.xray import (
    _get_recorder,
    is_xray_enabled,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Database instrumentation
# ------------------------------------------------------------------


def instrument_db_query(
    operation: str,
    statement: str,
) -> Optional[Any]:
    """Begin an X-Ray subsegment for a database query.

    Returns the subsegment (or None) so the caller can close it
    via ``end_db_query``.

    Args:
        operation: SQL operation verb (SELECT, INSERT, etc.).
        statement: The SQL statement (first 200 chars stored).

    Returns:
        The subsegment object, or None when tracing is off.
    """
    if not is_xray_enabled():
        return None

    recorder = _get_recorder()
    if recorder is None:
        return None

    try:
        subsegment = recorder.begin_subsegment(f"db.{operation.lower()}", "remote")
        if subsegment is not None:
            subsegment.put_metadata("sql", statement[:200], "database")
            subsegment.put_annotation("db_operation", operation)
        return subsegment
    except Exception:
        logger.debug("Could not begin DB X-Ray subsegment")
        return None


def end_db_query(
    subsegment: Optional[Any],
    error: Optional[Exception] = None,
) -> None:
    """End a database query subsegment.

    Args:
        subsegment: The subsegment returned by ``instrument_db_query``.
        error: Optional exception if the query failed.
    """
    if subsegment is None or not is_xray_enabled():
        return

    recorder = _get_recorder()
    if recorder is None:
        return

    try:
        if error is not None:
            subsegment.add_exception(error, error.__traceback__)
        recorder.end_subsegment()
    except Exception:
        logger.debug("Could not end DB X-Ray subsegment")


# ------------------------------------------------------------------
# Redis instrumentation
# ------------------------------------------------------------------


def trace_redis_operation(
    operation: str,
    key: str = "",
) -> Optional[Any]:
    """Begin an X-Ray subsegment for a Redis operation.

    Args:
        operation: Redis command (GET, SET, DEL, etc.).
        key: The cache key (first 100 chars stored).

    Returns:
        The subsegment object, or None when tracing is off.
    """
    if not is_xray_enabled():
        return None

    recorder = _get_recorder()
    if recorder is None:
        return None

    try:
        subsegment = recorder.begin_subsegment(f"redis.{operation.lower()}", "remote")
        if subsegment is not None:
            subsegment.put_annotation("redis_operation", operation)
            if key:
                subsegment.put_metadata("key", key[:100], "redis")
        return subsegment
    except Exception:
        logger.debug("Could not begin Redis X-Ray subsegment")
        return None


def end_redis_operation(
    subsegment: Optional[Any],
    error: Optional[Exception] = None,
    hit: Optional[bool] = None,
) -> None:
    """End a Redis operation subsegment.

    Args:
        subsegment: The subsegment from ``trace_redis_operation``.
        error: Optional exception if the operation failed.
        hit: Optional cache hit/miss indicator for GET operations.
    """
    if subsegment is None or not is_xray_enabled():
        return

    recorder = _get_recorder()
    if recorder is None:
        return

    try:
        if hit is not None:
            subsegment.put_annotation("cache_hit", hit)
        if error is not None:
            subsegment.add_exception(error, error.__traceback__)
        recorder.end_subsegment()
    except Exception:
        logger.debug("Could not end Redis X-Ray subsegment")


# ------------------------------------------------------------------
# External API instrumentation
# ------------------------------------------------------------------


def trace_external_api_call(
    service_name: str,
    operation: str,
    url: str = "",
) -> Optional[Any]:
    """Begin an X-Ray subsegment for an external API call.

    Args:
        service_name: Name of the external service (e.g. "spotify").
        operation: API operation (e.g. "search_artist").
        url: The request URL (first 200 chars stored).

    Returns:
        The subsegment object, or None when tracing is off.
    """
    if not is_xray_enabled():
        return None

    recorder = _get_recorder()
    if recorder is None:
        return None

    try:
        subsegment = recorder.begin_subsegment(f"{service_name}.{operation}", "remote")
        if subsegment is not None:
            subsegment.put_annotation("service", service_name)
            subsegment.put_annotation("operation", operation)
            if url:
                subsegment.put_http_meta("url", url[:200])
        return subsegment
    except Exception:
        logger.debug("Could not begin external API X-Ray subsegment")
        return None


def end_external_api_call(
    subsegment: Optional[Any],
    status_code: Optional[int] = None,
    error: Optional[Exception] = None,
) -> None:
    """End an external API call subsegment.

    Args:
        subsegment: The subsegment from ``trace_external_api_call``.
        status_code: HTTP response status code.
        error: Optional exception if the call failed.
    """
    if subsegment is None or not is_xray_enabled():
        return

    recorder = _get_recorder()
    if recorder is None:
        return

    try:
        if status_code is not None:
            subsegment.put_http_meta("status", status_code)
            if status_code >= 500:
                subsegment.add_fault_flag()
            elif status_code == 429:
                subsegment.add_throttle_flag()
            elif status_code >= 400:
                subsegment.add_error_flag()
        if error is not None:
            subsegment.add_exception(error, error.__traceback__)
            subsegment.add_fault_flag()
        recorder.end_subsegment()
    except Exception:
        logger.debug("Could not end external API X-Ray subsegment")


# ------------------------------------------------------------------
# Business logic instrumentation
# ------------------------------------------------------------------


def trace_business_operation(
    name: str,
    metadata: Optional[dict[str, object]] = None,
) -> Optional[Any]:
    """Begin an X-Ray subsegment for a business logic operation.

    Args:
        name: Operation name (e.g. "create_playlist").
        metadata: Optional metadata dict.

    Returns:
        The subsegment object, or None when tracing is off.
    """
    if not is_xray_enabled():
        return None

    recorder = _get_recorder()
    if recorder is None:
        return None

    try:
        subsegment = recorder.begin_subsegment(name, "local")
        if subsegment is not None and metadata:
            for key, value in metadata.items():
                subsegment.put_metadata(key, value)
        return subsegment
    except Exception:
        logger.debug("Could not begin business X-Ray subsegment %s", name)
        return None


def end_business_operation(
    subsegment: Optional[Any],
    error: Optional[Exception] = None,
) -> None:
    """End a business logic subsegment.

    Args:
        subsegment: The subsegment from ``trace_business_operation``.
        error: Optional exception if the operation failed.
    """
    if subsegment is None or not is_xray_enabled():
        return

    recorder = _get_recorder()
    if recorder is None:
        return

    try:
        if error is not None:
            subsegment.add_exception(error, error.__traceback__)
        recorder.end_subsegment()
    except Exception:
        logger.debug("Could not end business X-Ray subsegment")
