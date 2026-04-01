"""FastAPI middleware for AWS X-Ray request tracing.

Creates a top-level segment for each incoming HTTP request, recording
method, URL, status code, and any exceptions. When X-Ray is disabled
the middleware passes requests through with no overhead.

Requirements: US-5.5
"""

import logging
import time
from typing import Awaitable, Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from festival_playlist_generator.core.xray import _get_recorder, is_xray_enabled

logger = logging.getLogger(__name__)

# Paths that should not be traced to reduce noise
_SKIP_PATHS = frozenset({"/health", "/docs", "/redoc", "/openapi.json"})


class XRayMiddleware(BaseHTTPMiddleware):
    """Wrap each HTTP request in an X-Ray segment.

    The segment captures:
    - HTTP method and URL
    - Response status code
    - Request duration
    - Any unhandled exceptions
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not is_xray_enabled():
            return await call_next(request)

        path = request.url.path
        if path in _SKIP_PATHS:
            return await call_next(request)

        recorder = _get_recorder()
        if recorder is None:
            return await call_next(request)

        segment_name = f"{request.method} {path}"
        segment = None

        try:
            segment = recorder.begin_segment(segment_name)
        except Exception:
            logger.debug("Could not begin X-Ray segment for %s", path)
            return await call_next(request)

        start = time.monotonic()
        response: Optional[Response] = None

        try:
            # Add HTTP request metadata
            if segment is not None:
                segment.put_http_meta("url", str(request.url))
                segment.put_http_meta("method", request.method)
                client_ip = _get_client_ip(request)
                if client_ip:
                    segment.put_http_meta("client_ip", client_ip)

            response = await call_next(request)

            # Record response metadata
            if segment is not None and response is not None:
                segment.put_http_meta("status", response.status_code)
                if response.status_code >= 500:
                    segment.add_fault_flag()
                elif response.status_code == 429:
                    segment.add_throttle_flag()
                elif response.status_code >= 400:
                    segment.add_error_flag()

            return response  # type: ignore[return-value]

        except Exception as exc:
            if segment is not None:
                segment.add_exception(exc, exc.__traceback__)
                segment.add_fault_flag()
            raise
        finally:
            latency = time.monotonic() - start
            if segment is not None:
                segment.put_annotation("latency_ms", round(latency * 1000))
                segment.put_annotation(
                    "environment",
                    _safe_env(),
                )
            try:
                if recorder is not None:
                    recorder.end_segment()
            except Exception:
                logger.debug("Could not end X-Ray segment for %s", path)


def _get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _safe_env() -> str:
    """Return the environment name without importing at module level."""
    try:
        from festival_playlist_generator.core.config import settings

        return settings.ENVIRONMENT
    except Exception:
        return "unknown"
