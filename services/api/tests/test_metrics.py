"""Tests for CloudWatch metrics client, middleware, and service integration.

Requirements: US-5.2, US-5.8
"""

import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from festival_playlist_generator.core.metrics import (
    MetricDatum,
    MetricsClient,
    elapsed_ms,
    metrics_client,
)


# ---------------------------------------------------------------------------
# MetricDatum
# ---------------------------------------------------------------------------


class TestMetricDatum:
    """Tests for the MetricDatum data class."""

    def test_default_values(self) -> None:
        datum = MetricDatum(name="TestMetric", value=1.0)
        assert datum.name == "TestMetric"
        assert datum.value == 1.0
        assert datum.unit == "None"
        assert datum.dimensions == {}
        assert datum.timestamp is not None

    def test_custom_dimensions(self) -> None:
        dims = {"Endpoint": "/api/v1/artists", "Method": "GET"}
        datum = MetricDatum(
            name="RequestCount", value=1.0, unit="Count", dimensions=dims
        )
        assert datum.dimensions == dims
        assert datum.unit == "Count"

    def test_to_cloudwatch_format(self) -> None:
        dims = {"Env": "test"}
        datum = MetricDatum(
            name="Latency", value=42.5, unit="Milliseconds", dimensions=dims
        )
        cw = datum.to_cloudwatch_format()
        assert cw["MetricName"] == "Latency"
        assert cw["Value"] == 42.5
        assert cw["Unit"] == "Milliseconds"
        assert len(cw["Dimensions"]) == 1
        assert cw["Dimensions"][0] == {"Name": "Env", "Value": "test"}

    def test_to_cloudwatch_format_no_dimensions(self) -> None:
        datum = MetricDatum(name="Simple", value=1.0)
        cw = datum.to_cloudwatch_format()
        assert "Dimensions" not in cw or cw.get("Dimensions") == []


# ---------------------------------------------------------------------------
# MetricsClient – disabled mode (local development)
# ---------------------------------------------------------------------------


class TestMetricsClientDisabled:
    """Tests for MetricsClient when metrics are disabled (local mode)."""

    @pytest.fixture()
    def client(self) -> MetricsClient:
        return MetricsClient(namespace="TestNS", enabled=False)

    @pytest.mark.asyncio
    async def test_put_metric_logs_only(self, client: MetricsClient) -> None:
        """When disabled, put_metric should not buffer anything."""
        await client.put_metric("Test", 1.0, "Count")
        # Buffer should remain empty
        assert len(client._buffer) == 0

    @pytest.mark.asyncio
    async def test_put_metrics_batch_logs_only(
        self, client: MetricsClient
    ) -> None:
        data = [MetricDatum(name="A", value=1.0), MetricDatum(name="B", value=2.0)]
        await client.put_metrics_batch(data)
        assert len(client._buffer) == 0

    @pytest.mark.asyncio
    async def test_flush_noop_when_disabled(self, client: MetricsClient) -> None:
        await client.flush()  # Should not raise


# ---------------------------------------------------------------------------
# MetricsClient – enabled mode
# ---------------------------------------------------------------------------


class TestMetricsClientEnabled:
    """Tests for MetricsClient when metrics are enabled."""

    @pytest.fixture()
    def client(self) -> MetricsClient:
        return MetricsClient(namespace="TestNS", enabled=True)

    @pytest.mark.asyncio
    async def test_put_metric_buffers(self, client: MetricsClient) -> None:
        await client.put_metric("RequestCount", 1.0, "Count", {"Endpoint": "/test"})
        assert len(client._buffer) == 1
        assert client._buffer[0].name == "RequestCount"

    @pytest.mark.asyncio
    async def test_default_dimensions_merged(self, client: MetricsClient) -> None:
        await client.put_metric("Test", 1.0, "Count", {"Custom": "dim"})
        dims = client._buffer[0].dimensions
        assert "Environment" in dims
        assert "Service" in dims
        assert dims["Custom"] == "dim"

    @pytest.mark.asyncio
    async def test_put_metrics_batch_buffers(self, client: MetricsClient) -> None:
        data = [MetricDatum(name="A", value=1.0), MetricDatum(name="B", value=2.0)]
        await client.put_metrics_batch(data)
        assert len(client._buffer) == 2

    @pytest.mark.asyncio
    async def test_flush_clears_buffer(self, client: MetricsClient) -> None:
        """Flush should clear the buffer and call CloudWatch."""
        await client.put_metric("Test", 1.0, "Count")
        assert len(client._buffer) == 1

        mock_cw = MagicMock()
        mock_cw.put_metric_data = MagicMock()
        client._client = mock_cw

        await client.flush()
        assert len(client._buffer) == 0
        mock_cw.put_metric_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_empty_buffer_noop(self, client: MetricsClient) -> None:
        mock_cw = MagicMock()
        client._client = mock_cw
        await client.flush()
        mock_cw.put_metric_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_handles_cloudwatch_error(
        self, client: MetricsClient
    ) -> None:
        """Flush should not raise even if CloudWatch call fails."""
        await client.put_metric("Test", 1.0, "Count")

        mock_cw = MagicMock()
        mock_cw.put_metric_data = MagicMock(side_effect=Exception("AWS error"))
        client._client = mock_cw

        # Should not raise
        await client.flush()
        assert len(client._buffer) == 0

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, client: MetricsClient) -> None:
        mock_cw = MagicMock()
        mock_cw.put_metric_data = MagicMock()
        client._client = mock_cw
        client._flush_interval = 0.1  # Fast for testing

        await client.start()
        assert client._flush_task is not None

        await client.stop()
        assert client._flush_task is None


# ---------------------------------------------------------------------------
# elapsed_ms helper
# ---------------------------------------------------------------------------


class TestElapsedMs:
    def test_elapsed_ms(self) -> None:
        import time

        start = time.monotonic()
        time.sleep(0.01)
        ms = elapsed_ms(start)
        assert ms >= 5  # At least ~10ms but allow some slack


# ---------------------------------------------------------------------------
# MetricsMiddleware
# ---------------------------------------------------------------------------


class TestMetricsMiddleware:
    """Tests for the request metrics middleware."""

    @pytest.mark.asyncio
    async def test_normalise_path_uuid(self) -> None:
        from festival_playlist_generator.api.metrics_middleware import _normalise_path

        path = "/api/v1/artists/550e8400-e29b-41d4-a716-446655440000"
        assert _normalise_path(path) == "/api/v1/artists/{id}"

    @pytest.mark.asyncio
    async def test_normalise_path_numeric(self) -> None:
        from festival_playlist_generator.api.metrics_middleware import _normalise_path

        assert _normalise_path("/api/v1/festivals/123") == "/api/v1/festivals/{id}"

    @pytest.mark.asyncio
    async def test_normalise_path_nested(self) -> None:
        from festival_playlist_generator.api.metrics_middleware import _normalise_path

        path = "/api/v1/festivals/550e8400-e29b-41d4-a716-446655440000/artists"
        assert _normalise_path(path) == "/api/v1/festivals/{id}/artists"

    @pytest.mark.asyncio
    async def test_normalise_path_no_ids(self) -> None:
        from festival_playlist_generator.api.metrics_middleware import _normalise_path

        assert _normalise_path("/api/v1/artists") == "/api/v1/artists"

    @pytest.mark.asyncio
    async def test_looks_like_id(self) -> None:
        from festival_playlist_generator.api.metrics_middleware import _looks_like_id

        assert _looks_like_id("123") is True
        assert _looks_like_id("550e8400-e29b-41d4-a716-446655440000") is True
        assert _looks_like_id("artists") is False
        assert _looks_like_id("") is False


# ---------------------------------------------------------------------------
# Database metrics
# ---------------------------------------------------------------------------


class TestDbMetrics:
    """Tests for database query metrics helpers."""

    def test_extract_operation(self) -> None:
        from festival_playlist_generator.core.db_metrics import _extract_operation

        assert _extract_operation("SELECT * FROM artists") == "SELECT"
        assert _extract_operation("INSERT INTO artists") == "INSERT"
        assert _extract_operation("UPDATE artists SET") == "UPDATE"
        assert _extract_operation("DELETE FROM artists") == "DELETE"
        assert _extract_operation("BEGIN") == "BEGIN"
        assert _extract_operation("COMMIT") == "COMMIT"
        assert _extract_operation("  select * from x") == "SELECT"
        assert _extract_operation("EXPLAIN ANALYZE") == "OTHER"


# ---------------------------------------------------------------------------
# Cache metrics integration
# ---------------------------------------------------------------------------


class TestCacheMetrics:
    """Tests that CacheService publishes cache hit/miss metrics."""

    @pytest.mark.asyncio
    async def test_cache_get_miss_publishes_metric(self) -> None:
        from festival_playlist_generator.services.cache_service import CacheService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        service = CacheService(redis_client=mock_redis)

        with patch(
            "festival_playlist_generator.services.cache_service.metrics_client"
        ) as mock_metrics:
            mock_metrics.put_metric = AsyncMock()
            result = await service.get("nonexistent")

            assert result is None
            # Should have published CacheMiss and CacheLatency
            calls = mock_metrics.put_metric.call_args_list
            metric_names = [c[0][0] for c in calls]
            assert "CacheMiss" in metric_names
            assert "CacheLatency" in metric_names

    @pytest.mark.asyncio
    async def test_cache_get_hit_publishes_metric(self) -> None:
        import json

        from festival_playlist_generator.services.cache_service import CacheService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps({"key": "value"}))

        service = CacheService(redis_client=mock_redis)

        with patch(
            "festival_playlist_generator.services.cache_service.metrics_client"
        ) as mock_metrics:
            mock_metrics.put_metric = AsyncMock()
            result = await service.get("existing")

            assert result == {"key": "value"}
            calls = mock_metrics.put_metric.call_args_list
            metric_names = [c[0][0] for c in calls]
            assert "CacheHit" in metric_names
            assert "CacheLatency" in metric_names

    @pytest.mark.asyncio
    async def test_cache_set_publishes_latency(self) -> None:
        from festival_playlist_generator.services.cache_service import CacheService

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        service = CacheService(redis_client=mock_redis)

        with patch(
            "festival_playlist_generator.services.cache_service.metrics_client"
        ) as mock_metrics:
            mock_metrics.put_metric = AsyncMock()
            result = await service.set("key", "value", ttl=60)

            assert result is True
            calls = mock_metrics.put_metric.call_args_list
            metric_names = [c[0][0] for c in calls]
            assert "CacheLatency" in metric_names

    @pytest.mark.asyncio
    async def test_cache_delete_publishes_latency(self) -> None:
        from festival_playlist_generator.services.cache_service import CacheService

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)

        service = CacheService(redis_client=mock_redis)

        with patch(
            "festival_playlist_generator.services.cache_service.metrics_client"
        ) as mock_metrics:
            mock_metrics.put_metric = AsyncMock()
            result = await service.delete("key")

            assert result is True
            calls = mock_metrics.put_metric.call_args_list
            metric_names = [c[0][0] for c in calls]
            assert "CacheLatency" in metric_names
