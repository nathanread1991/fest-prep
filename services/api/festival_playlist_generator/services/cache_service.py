"""Cache service for Redis operations with connection pooling and JSON serialization."""

import json
import logging
import time
from typing import TYPE_CHECKING, Any, List, Optional

import redis.asyncio as redis

from festival_playlist_generator.core.config import settings
from festival_playlist_generator.core.metrics import metrics_client

if TYPE_CHECKING:
    from redis.asyncio.connection import Connection

logger = logging.getLogger(__name__)


class CacheService:
    """
    Service for Redis cache operations.

    Provides methods for get, set, delete, delete_pattern, and exists operations
    with TTL support and JSON serialization. Includes connection pooling for
    optimal performance.

    Requirements: US-4.2
    """

    def __init__(self, redis_client: Optional["redis.Redis[bytes]"] = None) -> None:
        """
        Initialize cache service.

        Args:
            redis_client: Optional Redis client. If not provided,
                creates one from settings.
        """
        self._redis_client = redis_client
        self._pool: Optional["redis.ConnectionPool[Connection]"] = None

    async def _get_client(self) -> "redis.Redis[bytes]":
        """Get or create Redis client with connection pooling."""
        if self._redis_client is not None:
            return self._redis_client
        if self._pool is None:
            try:
                self._pool = redis.ConnectionPool.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    max_connections=10,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                )
                logger.info("Redis connection pool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Redis connection pool: {e}")
                raise

        return redis.Redis(connection_pool=self._pool)

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Deserialized value or None if not found
        """
        start = time.monotonic()
        try:
            client = await self._get_client()
            value = await client.get(key)
            latency_ms = (time.monotonic() - start) * 1000.0

            if value is None:
                await metrics_client.put_metric(
                    "CacheMiss", 1.0, "Count", {"Operation": "get"}
                )
                await metrics_client.put_metric(
                    "CacheLatency",
                    latency_ms,
                    "Milliseconds",
                    {"Operation": "get"},
                )
                return None

            await metrics_client.put_metric(
                "CacheHit", 1.0, "Count", {"Operation": "get"}
            )
            await metrics_client.put_metric(
                "CacheLatency",
                latency_ms,
                "Milliseconds",
                {"Operation": "get"},
            )

            # Deserialize JSON
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to deserialize cache value for key {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (default: 1 hour)

        Returns:
            True if successful, False otherwise
        """
        start = time.monotonic()
        try:
            client = await self._get_client()

            # Serialize value to JSON
            serialized = json.dumps(value, default=str)

            # Set with expiration
            await client.setex(key, ttl, serialized)

            latency_ms = (time.monotonic() - start) * 1000.0
            await metrics_client.put_metric(
                "CacheLatency",
                latency_ms,
                "Milliseconds",
                {"Operation": "set"},
            )
            return True
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize value for key {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False otherwise
        """
        start = time.monotonic()
        try:
            client = await self._get_client()
            result = await client.delete(key)

            latency_ms = (time.monotonic() - start) * 1000.0
            await metrics_client.put_metric(
                "CacheLatency",
                latency_ms,
                "Milliseconds",
                {"Operation": "delete"},
            )
            return bool(result > 0)
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Pattern to match (e.g., "user:*", "festival:*")

        Returns:
            Number of keys deleted
        """
        try:
            client = await self._get_client()

            # Find all keys matching pattern
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)

            if not keys:
                return 0

            # Delete all matching keys
            result = await client.delete(*keys)
            result_int = int(result) if result is not None else 0
            logger.info(f"Deleted {result_int} keys matching pattern: {pattern}")
            return result_int
        except Exception as e:
            logger.error(f"Error deleting keys with pattern {pattern}: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists, False otherwise
        """
        try:
            client = await self._get_client()
            result = await client.exists(key)
            return bool(result > 0)
        except Exception as e:
            logger.error(f"Error checking existence of cache key {key}: {e}")
            return False

    async def get_many(self, keys: List[str]) -> List[Optional[Any]]:
        """
        Get multiple values from cache.

        Args:
            keys: List of cache keys

        Returns:
            List of deserialized values (None for missing keys)
        """
        try:
            client = await self._get_client()
            values = await client.mget(keys)

            results: List[Any] = []
            for value in values:
                if value is None:
                    results.append(None)
                else:
                    try:
                        results.append(json.loads(value))
                    except json.JSONDecodeError:
                        results.append(None)

            return results
        except Exception as e:
            logger.error(f"Error getting multiple cache keys: {e}")
            return [None] * len(keys)

    async def set_many(self, items: dict[str, Any], ttl: int = 3600) -> bool:
        """
        Set multiple values in cache with TTL.

        Args:
            items: Dictionary of key-value pairs
            ttl: Time to live in seconds (default: 1 hour)

        Returns:
            True if all successful, False otherwise
        """
        try:
            client = await self._get_client()

            # Use pipeline for atomic operations
            async with client.pipeline() as pipe:
                for key, value in items.items():
                    serialized = json.dumps(value, default=str)
                    pipe.setex(key, ttl, serialized)

                await pipe.execute()

            return True
        except Exception as e:
            logger.error(f"Error setting multiple cache keys: {e}")
            return False

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a numeric value in cache.

        Args:
            key: Cache key
            amount: Amount to increment by (default: 1)

        Returns:
            New value after increment, or None on error
        """
        try:
            client = await self._get_client()
            result = await client.incrby(key, amount)
            return int(result) if result is not None else None
        except Exception as e:
            logger.error(f"Error incrementing cache key {key}: {e}")
            return None

    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time for a key.

        Args:
            key: Cache key
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            client = await self._get_client()
            result = await client.expire(key, ttl)
            return bool(result)
        except Exception as e:
            logger.error(f"Error setting expiration for cache key {key}: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self._pool is not None:
            await self._pool.disconnect()
            logger.info("Redis connection pool closed")

    async def get_stats(self) -> dict[str, object]:
        """Collect cache statistics from Redis.

        Returns a dictionary with key counts per prefix, total keys,
        and memory usage when available.

        Returns:
            Dictionary with cache statistics.
        """
        stats: dict[str, object] = {
            "total_keys": 0,
            "key_counts": {},
            "memory_usage_bytes": None,
        }
        try:
            client = await self._get_client()

            # Count keys per well-known prefix
            prefixes = [
                "artist:",
                "artists:",
                "festival:",
                "festivals:",
                "playlist:",
                "playlists:",
                "setlist:",
                "setlists:",
            ]
            key_counts: dict[str, int] = {}
            total = 0
            for prefix in prefixes:
                count = 0
                async for _ in client.scan_iter(match=f"{prefix}*"):
                    count += 1
                key_counts[prefix.rstrip(":")] = count
                total += count

            stats["key_counts"] = key_counts
            stats["total_keys"] = total

            # Try to get memory info
            try:
                info = await client.info("memory")
                if isinstance(info, dict):
                    stats["memory_usage_bytes"] = info.get("used_memory", None)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error collecting cache stats: {e}")

        return stats
