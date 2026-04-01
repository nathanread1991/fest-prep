"""AWS X-Ray tracing configuration and instrumentation.

Provides X-Ray recorder setup, FastAPI middleware, and helpers for
creating subsegments around database, Redis, and external API calls.

In non-AWS environments (local/Docker), tracing is disabled and all
instrumentation functions become no-ops.

Requirements: US-5.5
"""

import functools
import logging
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional, TypeVar, cast

from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Module-level flag – set once during configure()
_xray_enabled: bool = False
_recorder: Optional[Any] = None


def _get_recorder() -> Optional[Any]:
    """Return the configured X-Ray recorder, or None if disabled."""
    return _recorder


def configure_xray() -> None:
    """Initialise the X-Ray recorder and set the module-level flag.

    Call this once during application startup. When running outside AWS
    or when XRAY_ENABLED is False the recorder is not created and all
    instrumentation becomes a no-op.
    """
    global _xray_enabled, _recorder

    if not settings.XRAY_ENABLED:
        logger.info("X-Ray tracing disabled (XRAY_ENABLED=False)")
        return

    try:
        from aws_xray_sdk.core import (  # type: ignore[import-untyped]
            xray_recorder,
        )

        xray_recorder.configure(
            service=settings.XRAY_SERVICE_NAME,
            daemon_address=settings.XRAY_DAEMON_ADDRESS,
            context_missing="LOG_ERROR",
            sampling=True,
        )
        _recorder = xray_recorder
        _xray_enabled = True
        logger.info(
            "X-Ray tracing configured "
            f"(service={settings.XRAY_SERVICE_NAME}, "
            f"daemon={settings.XRAY_DAEMON_ADDRESS})"
        )
    except ImportError:
        logger.warning("aws-xray-sdk not installed; X-Ray tracing disabled")
    except Exception:
        logger.exception("Failed to configure X-Ray recorder")


def is_xray_enabled() -> bool:
    """Return True if X-Ray tracing is active."""
    return _xray_enabled


# ------------------------------------------------------------------
# Subsegment helpers
# ------------------------------------------------------------------


@contextmanager
def xray_subsegment(
    name: str,
    namespace: str = "local",
    metadata: Optional[dict[str, object]] = None,
) -> Generator[Optional[Any], None, None]:
    """Context manager that wraps a block in an X-Ray subsegment.

    When tracing is disabled the block executes without overhead.

    Args:
        name: Subsegment name (e.g. ``"db.query"``).
        namespace: ``"aws"`` | ``"remote"`` | ``"local"``.
        metadata: Optional dict attached to the subsegment.

    Yields:
        The subsegment object, or ``None`` when tracing is off.
    """
    if not _xray_enabled or _recorder is None:
        yield None
        return

    try:
        subsegment = _recorder.begin_subsegment(name, namespace)
    except Exception:
        logger.debug("Could not begin X-Ray subsegment %s", name)
        yield None
        return

    try:
        if metadata and subsegment is not None:
            for key, value in metadata.items():
                subsegment.put_metadata(key, value)
        yield subsegment
    except Exception as exc:
        if subsegment is not None:
            subsegment.add_exception(exc, exc.__traceback__)
        raise
    finally:
        try:
            _recorder.end_subsegment()
        except Exception:
            logger.debug("Could not end X-Ray subsegment %s", name)


def trace_function(
    name: Optional[str] = None,
    namespace: str = "local",
) -> Callable[[F], F]:
    """Decorator that wraps a sync function in an X-Ray subsegment.

    Args:
        name: Subsegment name; defaults to the function's qualified name.
        namespace: ``"aws"`` | ``"remote"`` | ``"local"``.
    """

    def decorator(func: F) -> F:
        seg_name = name or func.__qualname__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with xray_subsegment(seg_name, namespace):
                return func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def trace_async_function(
    name: Optional[str] = None,
    namespace: str = "local",
) -> Callable[[F], F]:
    """Decorator that wraps an async function in an X-Ray subsegment.

    Args:
        name: Subsegment name; defaults to the function's qualified name.
        namespace: ``"aws"`` | ``"remote"`` | ``"local"``.
    """

    def decorator(func: F) -> F:
        seg_name = name or func.__qualname__

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            with xray_subsegment(seg_name, namespace):
                return await func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator
