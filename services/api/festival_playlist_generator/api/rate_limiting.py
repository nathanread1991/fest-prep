"""Rate limiting middleware using Redis."""

import logging
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

from festival_playlist_generator.core.redis import get_redis

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-based rate limiter using sliding window algorithm."""

    def __init__(
        self, requests_per_minute: int = 60, requests_per_hour: int = 1000
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

    async def is_allowed(self, identifier: str) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed for the given identifier.
        Returns (is_allowed, rate_limit_info)
        """
        try:
            redis_client = await get_redis()
            current_time = int(time.time())

            # Keys for minute and hour windows
            minute_key = f"rate_limit:minute:{identifier}:{current_time // 60}"
            hour_key = f"rate_limit:hour:{identifier}:{current_time // 3600}"

            # Get current counts
            minute_count = await redis_client.get(minute_key) or 0
            hour_count = await redis_client.get(hour_key) or 0

            minute_count = int(minute_count)
            hour_count = int(hour_count)

            # Check limits
            if minute_count >= self.requests_per_minute:
                return False, {
                    "limit_type": "minute",
                    "limit": self.requests_per_minute,
                    "current": minute_count,
                    "reset_time": (current_time // 60 + 1) * 60,
                }

            if hour_count >= self.requests_per_hour:
                return False, {
                    "limit_type": "hour",
                    "limit": self.requests_per_hour,
                    "current": hour_count,
                    "reset_time": (current_time // 3600 + 1) * 3600,
                }

            # Increment counters
            pipe = redis_client.pipeline()
            pipe.incr(minute_key)
            pipe.expire(minute_key, 60)  # Expire after 1 minute
            pipe.incr(hour_key)
            pipe.expire(hour_key, 3600)  # Expire after 1 hour
            await pipe.execute()

            return True, {
                "minute_limit": self.requests_per_minute,
                "minute_remaining": self.requests_per_minute - minute_count - 1,
                "hour_limit": self.requests_per_hour,
                "hour_remaining": self.requests_per_hour - hour_count - 1,
            }

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # If Redis is down, allow the request but log the error
            return True, {"error": "Rate limiting unavailable"}


# Global rate limiter instances
default_rate_limiter = RateLimiter(requests_per_minute=60, requests_per_hour=1000)
strict_rate_limiter = RateLimiter(requests_per_minute=30, requests_per_hour=500)


def get_client_identifier(request: Request, api_key: Optional[str] = None) -> str:
    """Get unique identifier for rate limiting."""
    if api_key:
        return f"api_key:{api_key}"

    # Use IP address as fallback
    client_ip = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("X-Forwarded-For")

    if forwarded_for:
        # Use the first IP in the chain
        client_ip = forwarded_for.split(",")[0].strip()

    return f"ip:{client_ip}"


async def check_rate_limit(
    request: Request,
    rate_limiter: RateLimiter = default_rate_limiter,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Check rate limit and raise HTTPException if exceeded."""
    identifier = get_client_identifier(request, api_key)

    is_allowed, rate_info = await rate_limiter.is_allowed(identifier)

    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit_type": rate_info["limit_type"],
                "limit": rate_info["limit"],
                "current": rate_info["current"],
                "reset_time": rate_info["reset_time"],
            },
            headers={
                "Retry-After": str(rate_info["reset_time"] - int(time.time())),
                "X-RateLimit-Limit": str(rate_info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(rate_info["reset_time"]),
            },
        )

    return rate_info


async def add_rate_limit_headers(response: Any, rate_info: Dict[str, Any]) -> None:
    """Add rate limiting headers to response."""
    if "minute_remaining" in rate_info:
        response.headers["X-RateLimit-Limit-Minute"] = str(rate_info["minute_limit"])
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            rate_info["minute_remaining"]
        )

    if "hour_remaining" in rate_info:
        response.headers["X-RateLimit-Limit-Hour"] = str(rate_info["hour_limit"])
        response.headers["X-RateLimit-Remaining-Hour"] = str(
            rate_info["hour_remaining"]
        )
