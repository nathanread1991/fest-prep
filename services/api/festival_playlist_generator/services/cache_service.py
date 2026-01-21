"""Cache service for Redis operations with connection pooling and JSON serialization."""

import json
import logging
from typing import Any, List, Optional

import redis.asyncio as redis

from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Service for Redis cache operations.

    Provides methods for get, set, delete, delete_pattern, and exists operations
    with TTL support and JSON serialization. Includes connection pooling for
    optimal performance.

    Requirements: US-4.2
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize cache service.

        Args:
            redis_client: Optional Redis client. If not provided, creates one from settings.
        """
        self._redis_client = redis_client
        self._pool = None

    async def _get_client(self) -> redis.Redis:
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
        try:
            client = await self._get_client()
            value = await client.get(key)

            if value is None:
                return None

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
        try:
            client = await self._get_client()

            # Serialize value to JSON
            serialized = json.dumps(value, default=str)

            # Set with expiration
            await client.setex(key, ttl, serialized)
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
        try:
            client = await self._get_client()
            result = await client.delete(key)
            return result > 0
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
            logger.info(f"Deleted {result} keys matching pattern: {pattern}")
            return result
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
            return result > 0
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

            results = []
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
            return result
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
            return result
        except Exception as e:
            logger.error(f"Error setting expiration for cache key {key}: {e}")
            return False

    async def close(self):
        """Close Redis connection pool."""
        if self._pool is not None:
            await self._pool.disconnect()
            logger.info("Redis connection pool closed")
