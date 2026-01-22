"""Cache warming service to pre-populate nginx image cache."""

import asyncio
import logging
from typing import Any, Dict, List

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.models.artist import Artist
from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.services.image_url_helper import convert_to_proxy_url

logger = logging.getLogger(__name__)


class CacheWarmer:
    """Service to warm up the nginx image cache by pre-fetching images."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(10.0, connect=5.0)
        self.max_concurrent = 20  # Can handle many more with no rate limiting
        self.batch_delay = 0  # No delay needed without rate limiting
        # Use internal Docker network address with internal endpoint (no rate limiting)
        self.internal_proxy_url = "http://nginx:8080"
        self.internal_endpoint = "/images/internal-proxy"  # No rate limiting

    async def warm_cache(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Warm the cache by fetching all artist and festival images.

        Args:
            db: Database session

        Returns:
            Dictionary with warming statistics
        """
        logger.info("Starting cache warming...")

        stats = {
            "total_images": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
        }

        # Collect all image URLs
        image_urls = await self._collect_image_urls(db)
        stats["total_images"] = len(image_urls)

        if not image_urls:
            logger.info("No images to warm")
            return stats

        logger.info(f"Warming cache with {len(image_urls)} images...")

        # Warm cache without rate limiting (using internal endpoint)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Process in batches for better control and logging
            batch_count = (
                len(image_urls) + self.max_concurrent - 1
            ) // self.max_concurrent
            for i in range(0, len(image_urls), self.max_concurrent):
                batch_num = (i // self.max_concurrent) + 1
                batch = image_urls[i : i + self.max_concurrent]

                logger.info(
                    f"Processing batch {batch_num}/{batch_count} "
                    f"({len(batch)} images)..."
                )

                tasks = [self._fetch_image(client, url, stats) for url in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(
            f"Cache warming complete: {stats['successful']} successful, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )

        return stats

    async def _collect_image_urls(self, db: AsyncSession) -> List[str]:
        """Collect all image URLs from database."""
        urls = []

        # Get all artist images
        result = await db.execute(select(Artist))
        artists = result.scalars().all()

        for artist in artists:
            if artist.spotify_image_url:
                proxy_url = convert_to_proxy_url(artist.spotify_image_url)
                if proxy_url:
                    # Convert to internal endpoint (no rate limiting)
                    internal_url = proxy_url.replace(
                        "http://localhost/images/proxy",
                        f"{self.internal_proxy_url}{self.internal_endpoint}",
                    )
                    if internal_url not in urls:
                        urls.append(internal_url)

            if artist.logo_url:
                proxy_url = convert_to_proxy_url(artist.logo_url)
                if proxy_url:
                    # Convert to internal endpoint (no rate limiting)
                    internal_url = proxy_url.replace(
                        "http://localhost/images/proxy",
                        f"{self.internal_proxy_url}{self.internal_endpoint}",
                    )
                    if internal_url not in urls:
                        urls.append(internal_url)

        # Get all festival images
        result = await db.execute(select(Festival))
        festivals = result.scalars().all()

        for festival in festivals:
            if festival.logo_url:
                proxy_url = convert_to_proxy_url(festival.logo_url)
                if proxy_url:
                    # Convert to internal endpoint (no rate limiting)
                    internal_url = proxy_url.replace(
                        "http://localhost/images/proxy",
                        f"{self.internal_proxy_url}{self.internal_endpoint}",
                    )
                    if internal_url not in urls:
                        urls.append(internal_url)

        return urls

    async def _fetch_image(
        self, client: httpx.AsyncClient, url: str, stats: Dict[str, Any]
    ) -> None:
        """Fetch a single image to warm the cache."""
        try:
            # Only fetch if it's a proxy URL
            if "/images/proxy" not in url:
                stats["skipped"] += 1
                return

            # Make HEAD request to warm cache without downloading full image
            response = await client.head(url, follow_redirects=True)

            if response.status_code == 200:
                stats["successful"] += 1
                cache_status = response.headers.get("X-Cache-Status", "UNKNOWN")
                logger.debug(f"Warmed: {url} (Cache: {cache_status})")
            else:
                stats["failed"] += 1
                error_msg = f"Failed to warm {url}: HTTP {response.status_code}"
                logger.warning(error_msg)
                stats["errors"].append(error_msg)

        except httpx.TimeoutException:
            stats["failed"] += 1
            error_msg = f"Timeout warming {url}"
            logger.warning(error_msg)
            stats["errors"].append(error_msg)

        except Exception as e:
            stats["failed"] += 1
            error_msg = f"Error warming {url}: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)

    async def warm_specific_images(self, image_urls: List[str]) -> Dict[str, Any]:
        """
        Warm cache for specific image URLs.

        Args:
            image_urls: List of image URLs to warm

        Returns:
            Dictionary with warming statistics
        """
        stats = {
            "total_images": len(image_urls),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
        }

        if not image_urls:
            return stats

        logger.info(f"Warming cache with {len(image_urls)} specific images...")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [self._fetch_image(client, url, stats) for url in image_urls]
            await asyncio.gather(*tasks, return_exceptions=True)

        return stats


# Global cache warmer instance
cache_warmer = CacheWarmer()
