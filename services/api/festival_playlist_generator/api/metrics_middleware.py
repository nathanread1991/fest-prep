"""Middleware for publishing API request metrics to CloudWatch.

Tracks per-request:
- RequestCount (by endpoint and method)
- RequestLatency in milliseconds (by endpoint)
- ErrorCount (by endpoint and status code)

Requirements: US-5.2, US-5.8
"""

import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from festival_playlist_generator.core.metrics import metrics_client


def _normalise_path(path: str) -> str:
    """Collapse path-parameter segments so metrics aren't high-cardinality.

    Examples:
        /api/v1/artists/550e8400-... -> /api/v1/artists/{id}
        /api/v1/festivals/123/artists -> /api/v1/festivals/{id}/artists
    """
    parts = path.strip("/").split("/")
    normalised = []
    for part in parts:
        # Treat UUIDs and numeric IDs as path parameters
        if _looks_like_id(part):
            normalised.append("{id}")
        else:
            normalised.append(part)
    return "/" + "/".join(normalised)


def _looks_like_id(segment: str) -> bool:
    """Return True if *segment* looks like a UUID or numeric ID."""
    if not segment:
        return False
    # Numeric ID
    if segment.isdigit():
        return True
    # UUID (with or without dashes)
    stripped = segment.replace("-", "")
    if len(stripped) == 32:
        try:
            int(stripped, 16)
            return True
        except ValueError:
            pass
    return False


class MetricsMiddleware(BaseHTTPMiddleware):
    """Publish request count, latency, and error metrics to CloudWatch."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Skip metrics for health/docs endpoints
        if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        path = _normalise_path(request.url.path)
        method = request.method
        start = time.monotonic()

        response = await call_next(request)

        latency_ms = (time.monotonic() - start) * 1000.0
        status = response.status_code

        # Fire-and-forget metric publishing (non-blocking)
        dims = {"Endpoint": path, "Method": method}

        await metrics_client.put_metric(
            "RequestCount", 1.0, "Count", dims
        )
        await metrics_client.put_metric(
            "RequestLatency", latency_ms, "Milliseconds", dims
        )

        if status >= 400:
            error_dims = {**dims, "StatusCode": str(status)}
            await metrics_client.put_metric(
                "ErrorCount", 1.0, "Count", error_dims
            )

        return response
