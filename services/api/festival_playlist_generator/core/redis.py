"""Redis connection and cache management."""

import redis.asyncio as redis
from typing import Optional, Any
import json
import logging

from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)

# Redis connection pool
redis_pool = None


async def init_redis():
    """Initialize Redis connection pool."""
    global redis_pool
    try:
        redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
        logger.info("Redis connection pool initialized")
    except Exception as e:
        logger.error(f"Error initializing Redis: {e}")
        logger.warning("Continuing without Redis - caching will be disabled")


async def get_redis() -> redis.Redis:
    """Get Redis connection."""
    if redis_pool is None:
        await init_redis()
    return redis.Redis(connection_pool=redis_pool)


class CacheManager:
    """Redis cache management utilities."""
    
    def __init__(self):
        self.redis_client = None
    
    async def get_client(self) -> redis.Redis:
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