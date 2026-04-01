"""Redis connection and cache management.

Supports both local Redis and AWS ElastiCache for Redis.
In AWS, the REDIS_URL is injected by ECS from Secrets Manager.

ElastiCache specifics:
- SSL/TLS support (rediss:// scheme) when transit encryption is enabled
- Connection retry logic with exponential backoff for failover scenarios
- Tuned connection pooling for ElastiCache single-node (dev) or cluster
"""

import json
import logging
import ssl as ssl_module
from typing import TYPE_CHECKING, Any, Dict, Optional

import redis.asyncio as redis
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.retry import Retry

from festival_playlist_generator.core.aws_config import is_aws_environment
from festival_playlist_generator.core.config import settings

if TYPE_CHECKING:
    from redis.asyncio.connection import Connection

logger = logging.getLogger(__name__)

# Redis connection pool
redis_pool: Optional["redis.ConnectionPool[Connection]"] = None


def _build_pool_kwargs() -> Dict[str, Any]:
    """Build Redis connection pool kwargs based on environment.

    Returns:
        Dictionary of connection pool configuration.
    """
    kwargs: Dict[str, Any] = {
        "decode_responses": True,
    }

    if is_aws_environment():
        # ElastiCache connection pooling settings
        kwargs["max_connections"] = 20
        kwargs["socket_timeout"] = 5.0
        kwargs["socket_connect_timeout"] = 5.0
        kwargs["socket_keepalive"] = True

        # Retry configuration for ElastiCache failover/reconnection
        kwargs["retry"] = Retry(
            ExponentialBackoff(cap=10, base=0.5),
            retries=3,
        )
        kwargs["retry_on_error"] = [
            RedisConnectionError,
            ConnectionResetError,
            TimeoutError,
        ]

        # SSL for ElastiCache with transit encryption
        if settings.REDIS_URL.startswith("rediss://"):
            ssl_context = ssl_module.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl_module.CERT_NONE
            kwargs["ssl"] = True
            kwargs["ssl_ca_certs"] = None

        logger.info(
            "Redis pool configured for AWS ElastiCache "
            "(max_connections=20, retry=3, keepalive=True)"
        )
    else:
        # Local Docker development settings
        kwargs["max_connections"] = 50

    return kwargs


async def init_redis() -> None:
    """Initialize Redis connection pool."""
    global redis_pool
    try:
        pool_kwargs = _build_pool_kwargs()
        redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, **pool_kwargs)
        logger.info("Redis connection pool initialized")
    except Exception as e:
        logger.error(f"Error initializing Redis: {e}")
        logger.warning("Continuing without Redis - caching will be disabled")


async def get_redis() -> "redis.Redis[bytes]":
    """Get Redis connection."""
    if redis_pool is None:
        await init_redis()
    return redis.Redis(connection_pool=redis_pool)


class CacheManager:
    """Redis cache management utilities."""

    def __init__(self) -> None:
        self.redis_client: Optional["redis.Redis[bytes]"] = None

    async def get_client(self) -> "redis.Redis[bytes]":
        """Get Redis client."""
        if self.redis_client is None:
            self.redis_client = await get_redis()
        return self.redis_client

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            client = await self.get_client()
            value = await client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Set value in cache with expiration."""
        try:
            client = await self.get_client()
            serialized_value = json.dumps(value, default=str)
            await client.setex(key, expire, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            client = await self.get_client()
            await client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False


# Global cache manager instance
cache = CacheManager()
