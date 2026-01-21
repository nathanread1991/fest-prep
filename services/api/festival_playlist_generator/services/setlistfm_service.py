"""Setlist.fm service with circuit breaker and rate limiting awareness."""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import httpx

from festival_playlist_generator.core.config import settings
from festival_playlist_generator.services.spotify_service import CircuitBreaker

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter for API calls.
    
    Setlist.fm has rate limits, so we need to be aware and throttle requests.
    """
    
    def __init__(self, max_requests: int = 10, time_window: int = 1):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: List[datetime] = []
    
    async def acquire(self):
        """Wait if necessary to respect rate limit."""
        now = datetime.now()
        
        # Remove old requests outside time window
        cutoff = now - timedelta(seconds=self.time_window)
        self.requests = [req_time for req_time in self.requests if req_time > cutoff]
        
        # If at limit, wait until oldest request expires
        if len(self.requests) >= self.max_requests:
            oldest = self.requests[0]
            wait_time = (oldest + timedelta(seconds=self.time_window) - now).total_seconds()
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                # Recursively try again
                return await self.acquire()
        
        # Record this request
        self.requests.append(now)


class SetlistFmService:
    """
    Service for Setlist.fm API integration with circuit breaker and rate limiting.
    
    Provides methods for:
    - Getting artist setlists
    - Getting setlist by ID
    - Retry logic with exponential backoff
    - Rate limiting awareness
    
    Requirements: US-7.6
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Setlist.fm service.
        
        Args:
            api_key: Setlist.fm API key (defaults to settings)
        """
        self.api_key = api_key or getattr(settings, 'SETLISTFM_API_KEY', None)
        
        # Circuit breaker for API calls
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=httpx.HTTPError
        )
        
        # Rate limiter (Setlist.fm allows ~2 requests per second)
        self.rate_limiter = RateLimiter(max_requests=10, time_window=5)
        
        # HTTP client with timeout
        self.client = httpx.AsyncClient(timeout=15.0)
        
        self.base_url = "https://api.setlist.fm/rest/1.0"
    
    async def get_artist_setlists(
        self,
        artist_mbid: str,
        page: int = 1,
        limit: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Get setlists for an artist with circuit breaker and rate limiting.
        
        Args:
            artist_mbid: MusicBrainz artist ID
            page: Page number (1-indexed)
            limit: Results per page
            
        Returns:
            Dictionary with setlists data or None on failure
        """
        async def _get():
            # Respect rate limit
            await self.rate_limiter.acquire()
            
            headers = {
                "x-api-key": self.api_key,
                "Accept": "application/json"
            }
            params = {
                "p": page,
                "artistMbid": artist_mbid
            }
            
            response = await self.client.get(
                f"{self.base_url}/artist/{artist_mbid}/setlists",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        
        try:
            return await self._retry_with_backoff(_get)
        except Exception as e:
            logger.error(f"Failed to get setlists for artist {artist_mbid}: {e}")
            return None
    
    async def get_setlist_by_id(self, setlist_id: str) -> Optional[Dict[str, Any]]:
        """
        Get setlist by ID with circuit breaker and rate limiting.
        
        Args:
            setlist_id: Setlist.fm setlist ID
            
        Returns:
            Setlist data dictionary or None on failure
        """
        async def _get():
            # Respect rate limit
            await self.rate_limiter.acquire()
            
            headers = {
                "x-api-key": self.api_key,
                "Accept": "application/json"
            }
            
            response = await self.client.get(
                f"{self.base_url}/setlist/{setlist_id}",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        
        try:
            return await self._retry_with_backoff(_get)
        except Exception as e:
            logger.error(f"Failed to get setlist {setlist_id}: {e}")
            return None
    
    async def search_artist(
        self,
        artist_name: str,
        page: int = 1,
        limit: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Search for an artist on Setlist.fm.
        
        Args:
            artist_name: Name of artist to search
            page: Page number (1-indexed)
            limit: Results per page
            
        Returns:
            Dictionary with artist search results or None on failure
        """
        async def _search():
            # Respect rate limit
            await self.rate_limiter.acquire()
            
            headers = {
                "x-api-key": self.api_key,
                "Accept": "application/json"
            }
            params = {
                "artistName": artist_name,
                "p": page,
                "sort": "relevance"
            }
            
            response = await self.client.get(
                f"{self.base_url}/search/artists",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        
        try:
            return await self._retry_with_backoff(_search)
        except Exception as e:
            logger.error(f"Failed to search artist '{artist_name}': {e}")
            return None
    
    async def search_setlists(
        self,
        artist_name: Optional[str] = None,
        venue_name: Optional[str] = None,
        city_name: Optional[str] = None,
        year: Optional[int] = None,
        page: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Search for setlists with various filters.
        
        Args:
            artist_name: Filter by artist name
            venue_name: Filter by venue name
            city_name: Filter by city name
            year: Filter by year
            page: Page number (1-indexed)
            
        Returns:
            Dictionary with setlist search results or None on failure
        """
        async def _search():
            # Respect rate limit
            await self.rate_limiter.acquire()
            
            headers = {
                "x-api-key": self.api_key,
                "Accept": "application/json"
            }
            params = {"p": page}
            
            if artist_name:
                params["artistName"] = artist_name
            if venue_name:
                params["venueName"] = venue_name
            if city_name:
                params["cityName"] = city_name
            if year:
                params["year"] = year
            
            response = await self.client.get(
                f"{self.base_url}/search/setlists",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        
        try:
            return await self._retry_with_backoff(_search)
        except Exception as e:
            logger.error(f"Failed to search setlists: {e}")
            return None
    
    async def get_venue(self, venue_id: str) -> Optional[Dict[str, Any]]:
        """
        Get venue details by ID.
        
        Args:
            venue_id: Setlist.fm venue ID
            
        Returns:
            Venue data dictionary or None on failure
        """
        async def _get():
            # Respect rate limit
            await self.rate_limiter.acquire()
            
            headers = {
                "x-api-key": self.api_key,
                "Accept": "application/json"
            }
            
            response = await self.client.get(
                f"{self.base_url}/venue/{venue_id}",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        
        try:
            return await self._retry_with_backoff(_get)
        except Exception as e:
            logger.error(f"Failed to get venue {venue_id}: {e}")
            return None
    
    async def _retry_with_backoff(
        self,
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0
    ):
        """
        Retry function with exponential backoff.
        
        Args:
            func: Async function to retry
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            backoff_factor: Multiplier for delay on each retry
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries fail
        """
        delay = initial_delay
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                # Use circuit breaker for the actual call
                return await self.circuit_breaker.call(func)
            except httpx.HTTPStatusError as e:
                last_exception = e
                
                # Don't retry on client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    logger.error(f"Client error {e.response.status_code}, not retrying")
                    raise
                
                # Retry on server errors (5xx) or network errors
                if attempt < max_retries:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
                else:
                    logger.error(f"All retry attempts failed: {e}")
                    raise
            except Exception as e:
                last_exception = e
                
                # Retry on any other exception
                if attempt < max_retries:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
                else:
                    logger.error(f"All retry attempts failed: {e}")
                    raise
        
        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
