"""CloudWatch metrics client for publishing application metrics.

Provides a MetricsClient that buffers metric data points and publishes
them to CloudWatch in batches. In non-AWS environments (local/Docker),
metrics are logged instead of published.

Requirements: US-5.2
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from festival_playlist_generator.core.aws_config import is_aws_environment
from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)


class MetricDatum:
    """A single metric data point for CloudWatch."""

    __slots__ = ("name", "value", "unit", "dimensions", "timestamp")

    def __init__(
        self,
        name: str,
        value: float,
        unit: str = "None",
        dimensions: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        self.name = name
        self.value = value
        self.unit = unit
        self.dimensions = dimensions or {}
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def to_cloudwatch_format(self) -> Dict[str, Any]:
        """Convert to CloudWatch PutMetricData format."""
        datum: Dict[str, Any] = {
            "MetricName": self.name,
            "Value": self.value,
            "Unit": self.unit,
            "Timestamp": self.timestamp,
        }
        if self.dimensions:
            datum["Dimensions"] = [
                {"Name": k, "Value": v} for k, v in self.dimensions.items()
            ]
        return datum


class MetricsClient:
    """CloudWatch metrics client with buffering and batch publishing.

    Buffers metric data points and publishes them in batches to reduce
    API calls. Falls back to logging in non-AWS environments.

    Usage:
        metrics = MetricsClient()
        await metrics.put_metric("RequestCount", 1.0, "Count",
                                 {"Endpoint": "/api/v1/artists"})
        # Or batch:
        await metrics.put_metrics_batch([datum1, datum2])

    Requirements: US-5.2
    """

    # CloudWatch allows max 1000 metric data points per PutMetricData call
    _MAX_BATCH_SIZE = 1000

    def __init__(
        self,
        namespace: Optional[str] = None,
        enabled: Optional[bool] = None,
        flush_interval: Optional[int] = None,
    ) -> None:
        self._namespace = namespace or settings.METRICS_NAMESPACE
        self._enabled = enabled if enabled is not None else settings.METRICS_ENABLED
        self._flush_interval = flush_interval or settings.METRICS_FLUSH_INTERVAL
        self._buffer: List[MetricDatum] = []
        self._lock = asyncio.Lock()
        self._client: Any = None
        self._flush_task: Optional[asyncio.Task[None]] = None
        self._default_dimensions: Dict[str, str] = {
            "Environment": settings.ENVIRONMENT,
            "Service": "festival-api",
        }

    def _get_client(self) -> Any:
        """Lazily create boto3 CloudWatch client."""
        if self._client is None:
            try:
                import boto3  # type: ignore[import-untyped]

                self._client = boto3.client(
                    "cloudwatch", region_name=settings.AWS_REGION
                )
            except ImportError:
                logger.warning(
                    "boto3 not installed; CloudWatch metrics disabled"
                )
                self._enabled = False
        return self._client

    async def start(self) -> None:
        """Start the background flush task."""
        if self._enabled and self._flush_task is None:
            self._flush_task = asyncio.create_task(self._periodic_flush())
            logger.info(
                "CloudWatch metrics client started "
                f"(namespace={self._namespace}, "
                f"flush_interval={self._flush_interval}s)"
            )

    async def stop(self) -> None:
        """Flush remaining metrics and stop the background task."""
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        # Final flush
        await self.flush()
        logger.info("CloudWatch metrics client stopped")

    async def put_metric(
        self,
        name: str,
        value: float,
        unit: str = "None",
        dimensions: Optional[Dict[str, str]] = None,
    ) -> None:
        """Buffer a single metric data point.

        Args:
            name: Metric name (e.g. "RequestCount").
            value: Metric value.
            unit: CloudWatch unit (Count, Milliseconds, etc.).
            dimensions: Additional dimensions beyond defaults.
        """
        merged_dims = {**self._default_dimensions}
        if dimensions:
            merged_dims.update(dimensions)

        datum = MetricDatum(
            name=name, value=value, unit=unit, dimensions=merged_dims
        )

        if not self._enabled:
            logger.debug(
                f"Metric (local): {name}={value} {unit} dims={merged_dims}"
            )
            return

        async with self._lock:
            self._buffer.append(datum)

    async def put_metrics_batch(self, data: Sequence[MetricDatum]) -> None:
        """Buffer multiple metric data points at once.

        Args:
            data: Sequence of MetricDatum objects.
        """
        if not self._enabled:
            for d in data:
                logger.debug(
                    f"Metric (local): {d.name}={d.value} "
                    f"{d.unit} dims={d.dimensions}"
                )
            return

        async with self._lock:
            self._buffer.extend(data)

    async def flush(self) -> None:
        """Publish all buffered metrics to CloudWatch."""
        async with self._lock:
            if not self._buffer:
                return
            to_flush = list(self._buffer)
            self._buffer.clear()

        if not self._enabled:
            return

        client = self._get_client()
        if client is None:
            return

        # Send in batches of _MAX_BATCH_SIZE
        for i in range(0, len(to_flush), self._MAX_BATCH_SIZE):
            batch = to_flush[i : i + self._MAX_BATCH_SIZE]
            metric_data = [d.to_cloudwatch_format() for d in batch]
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda md=metric_data: client.put_metric_data(  # type: ignore[misc]
                        Namespace=self._namespace, MetricData=md
                    ),
                )
                logger.debug(
                    f"Published {len(batch)} metrics to CloudWatch"
                )
            except Exception:
                logger.exception(
                    f"Failed to publish {len(batch)} metrics to CloudWatch"
                )

    async def _periodic_flush(self) -> None:
        """Background task that flushes metrics at regular intervals."""
        while True:
            await asyncio.sleep(self._flush_interval)
            try:
                await self.flush()
            except Exception:
                logger.exception("Error in periodic metrics flush")


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def _timer() -> float:
    """Return a monotonic timestamp for latency measurement."""
    return time.monotonic()


def elapsed_ms(start: float) -> float:
    """Return elapsed milliseconds since *start* (from ``_timer()``)."""
    return (time.monotonic() - start) * 1000.0


# Module-level singleton – initialised once, shared across the app.
metrics_client = MetricsClient()
