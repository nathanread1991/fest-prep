"""Enhanced caching strategies for the Festival Playlist Generator."""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

from festival_playlist_generator.core.config import settings
from festival_playlist_generator.core.redis import get_redis

logger = logging.getLogger(__name__)


class CacheManager:
    """Centralized cache management with multiple strategies."""

    def __init__(self) -> None:
        self.default_ttl = 3600  # 1 hour
        self.cache_prefix = "fpg:"

    def _make_key(self, key: str, namespace: str = "default") -> str:
        """Create a namespaced cache key."""
        return f"{self.cache_prefix}{namespace}:{key}"

    def _serialize_value(self, value: Any) -> str:
        """Serialize a value for caching."""
        return json.dumps(value, default=str, separators=(",", ":"))

    def _deserialize_value(self, value: str) -> Any:
        """Deserialize a cached value."""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    async def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """Get a value from cache."""
        try:
            redis = await get_redis()
            cache_key = self._make_key(key, namespace)

            value = await redis.get(cache_key)
            if value:
                return self._deserialize_value(value)

            return None

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = "default",
    ) -> bool:
        """Set a value in cache."""
        try:
            redis = await get_redis()
            cache_key = self._make_key(key, namespace)
            serialized_value = self._serialize_value(value)

            if ttl is None:
                ttl = self.default_ttl

            await redis.setex(cache_key, ttl, serialized_value)
            return True

        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete a value from cache."""
        try:
            redis = await get_redis()
            cache_key = self._make_key(key, namespace)

            result = await redis.delete(cache_key)
            return bool(result > 0)

        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def exists(self, key: str, namespace: str = "default") -> bool:
        """Check if a key exists in cache."""
        try:
            redis = await get_redis()
            cache_key = self._make_key(key, namespace)

            result = await redis.exists(cache_key)
            return bool(result > 0)

        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str, namespace: str = "default") -> int:
        """Invalidate all keys matching a pattern."""
        try:
            redis = await get_redis()
            cache_pattern = self._make_key(pattern, namespace)

            keys = await redis.keys(cache_pattern)
            if keys:
                result = await redis.delete(*keys)
                return int(result)

            return 0

        except Exception as e:
            logger.error(f"Cache invalidate pattern error for {pattern}: {e}")
            return 0

    async def get_or_set(
        self,
        key: str,
        factory_func: Union[Callable[[], Any], Any],
        ttl: Optional[int] = None,
        namespace: str = "default",
    ) -> Any:
        """Get from cache or set using factory function."""
        value = await self.get(key, namespace)

        if value is not None:
            return value

        # Generate value using factory function
        if callable(factory_func):
            value = (
                await factory_func()
                if hasattr(factory_func, "__await__")
                else factory_func()
            )
        else:
            value = factory_func

        await self.set(key, value, ttl, namespace)
        return value


# Global cache manager instance
cache_manager = CacheManager()


def cache_key_from_args(*args: Any, **kwargs: Any) -> str:
    """Generate a cache key from function arguments."""
    key_parts = []

    # Add positional arguments
    for arg in args:
        if hasattr(arg, "id"):
            key_parts.append(str(arg.id))
        else:
            key_parts.append(str(arg))

    # Add keyword arguments
    for k, v in sorted(kwargs.items()):
        if hasattr(v, "id"):
            key_parts.append(f"{k}:{v.id}")
        else:
            key_parts.append(f"{k}:{v}")

    # Create hash of the key parts
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(
    ttl: int = 3600,
    namespace: str = "default",
    key_func: Optional[Callable[..., str]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for caching function results."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{cache_key_from_args(*args, **kwargs)}"

            # Try to get from cache
            cached_result = await cache_manager.get(cache_key, namespace)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                return cached_result

            # Execute function and cache result
            logger.debug(f"Cache miss for {func.__name__}: {cache_key}")
            result = (
                await func(*args, **kwargs)
                if hasattr(func, "__await__")
                else func(*args, **kwargs)
            )

            await cache_manager.set(cache_key, result, ttl, namespace)
            return result

        return wrapper

    return decorator


class HTTPCacheManager:
    """HTTP response caching with proper headers."""

    @staticmethod
    def get_cache_headers(
        max_age: int = 3600,
        public: bool = True,
        must_revalidate: bool = False,
        etag: Optional[str] = None,
    ) -> Dict[str, str]:
        """Generate HTTP cache headers."""
        headers = {}

        # Cache-Control header
        cache_control_parts = []

        if public:
            cache_control_parts.append("public")
        else:
            cache_control_parts.append("private")

        cache_control_parts.append(f"max-age={max_age}")

        if must_revalidate:
            cache_control_parts.append("must-revalidate")

        headers["Cache-Control"] = ", ".join(cache_control_parts)

        # Expires header (fallback for older browsers)
        expires_time = datetime.utcnow() + timedelta(seconds=max_age)
        headers["Expires"] = expires_time.strftime("%a, %d %b %Y %H:%M:%S GMT")

        # ETag header
        if etag:
            headers["ETag"] = f'"{etag}"'

        # Vary header for content negotiation
        headers["Vary"] = "Accept-Encoding, Accept"

        return headers

    @staticmethod
    def generate_etag(content: Union[str, bytes]) -> str:
        """Generate ETag for content."""
        if isinstance(content, str):
            content = content.encode("utf-8")

        return hashlib.md5(content).hexdigest()

    @staticmethod
    def is_not_modified(request_headers: Dict[str, str], etag: str) -> bool:
        """Check if content has not been modified."""
        if_none_match = request_headers.get("if-none-match")

        if if_none_match:
            # Remove quotes from ETag
            if_none_match = if_none_match.strip('"')
            return if_none_match == etag

        return False


class APIResponseCache:
    """Specialized caching for API responses."""

    def __init__(self) -> None:
        self.cache_manager = cache_manager

    async def cache_api_response(
        self,
        endpoint: str,
        params: Dict[str, Any],
        response_data: Any,
        ttl: int = 300,  # 5 minutes default for API responses
    ) -> bool:
        """Cache an API response."""
        cache_key = self._make_api_key(endpoint, params)

        cached_response = {"data": response_data, "timestamp": time.time(), "ttl": ttl}

        return await self.cache_manager.set(
            cache_key, cached_response, ttl, namespace="api"
        )

    async def get_cached_api_response(
        self, endpoint: str, params: Dict[str, Any]
    ) -> Optional[Any]:
        """Get cached API response."""
        cache_key = self._make_api_key(endpoint, params)

        cached_response = await self.cache_manager.get(cache_key, namespace="api")

        if cached_response:
            return cached_response.get("data")

        return None

    def _make_api_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Create cache key for API endpoint."""
        param_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        key_string = f"{endpoint}?{param_string}"
        return hashlib.md5(key_string.encode()).hexdigest()

    async def invalidate_endpoint(self, endpoint: str) -> int:
        """Invalidate all cached responses for an endpoint."""
        pattern = f"*{endpoint.replace('/', '_')}*"
        return await self.cache_manager.invalidate_pattern(pattern, namespace="api")


class BrowserCacheOptimizer:
    """Optimize browser caching for static assets."""

    @staticmethod
    def get_asset_cache_headers(file_path: str) -> Dict[str, str]:
        """Get cache headers for static assets."""
        file_extension = file_path.lower().split(".")[-1]

        # Long-term caching for versioned assets
        if any(char in file_path for char in [".min.", ".hash.", ".v"]):
            return HTTPCacheManager.get_cache_headers(
                max_age=31536000, public=True  # 1 year
            )

        # Medium-term caching for images
        elif file_extension in ["jpg", "jpeg", "png", "gif", "svg", "webp"]:
            return HTTPCacheManager.get_cache_headers(
                max_age=86400, public=True  # 1 day
            )

        # Short-term caching for CSS/JS
        elif file_extension in ["css", "js"]:
            return HTTPCacheManager.get_cache_headers(
                max_age=3600, public=True, must_revalidate=True  # 1 hour
            )

        # Very short caching for HTML
        elif file_extension in ["html", "htm"]:
            return HTTPCacheManager.get_cache_headers(
                max_age=300, public=False, must_revalidate=True  # 5 minutes
            )

        # Default caching
        else:
            return HTTPCacheManager.get_cache_headers(
                max_age=1800, public=True  # 30 minutes
            )


# Global instances
api_cache = APIResponseCache()
browser_cache_optimizer = BrowserCacheOptimizer()


# Specialized caching functions for common use cases
async def cache_festival_data(festival_id: str, data: Dict[str, Any]) -> bool:
    """Cache festival data with appropriate TTL."""
    return await cache_manager.set(
        f"festival:{festival_id}", data, ttl=7200, namespace="festivals"  # 2 hours
    )


async def get_cached_festival_data(festival_id: str) -> Optional[Dict[str, Any]]:
    """Get cached festival data."""
    return await cache_manager.get(f"festival:{festival_id}", namespace="festivals")


async def cache_playlist_data(playlist_id: str, data: Dict[str, Any]) -> bool:
    """Cache playlist data with appropriate TTL."""
    return await cache_manager.set(
        f"playlist:{playlist_id}", data, ttl=1800, namespace="playlists"  # 30 minutes
    )


async def get_cached_playlist_data(playlist_id: str) -> Optional[Dict[str, Any]]:
    """Get cached playlist data."""
    return await cache_manager.get(f"playlist:{playlist_id}", namespace="playlists")


async def cache_setlist_data(artist_id: str, data: List[Dict[str, Any]]) -> bool:
    """Cache setlist data with longer TTL (setlists don't change often)."""
    return await cache_manager.set(
        f"setlists:{artist_id}", data, ttl=86400, namespace="setlists"  # 24 hours
    )


async def get_cached_setlist_data(artist_id: str) -> Optional[List[Dict[str, Any]]]:
    """Get cached setlist data."""
    return await cache_manager.get(f"setlists:{artist_id}", namespace="setlists")


async def invalidate_user_cache(user_id: str) -> int:
    """Invalidate all cached data for a user."""
    return await cache_manager.invalidate_pattern(
        f"*user:{user_id}*", namespace="users"
    )


async def invalidate_festival_poster_cache(festival_id: str) -> bool:
    """Invalidate cached poster HTML for a festival."""
    return await cache_manager.delete(f"poster:{festival_id}", namespace="posters")
