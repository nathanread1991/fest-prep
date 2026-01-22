"""Festival Web Scraper - Uses AI to extract festival data from websites."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class FestivalScraper:
    """Uses AI to intelligently scrape festival data from any website."""

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
        }
        # Import settings here to avoid circular imports
        from festival_playlist_generator.core.config import settings

        self.openai_api_key = settings.OPENAI_API_KEY
        self.anthropic_api_key = settings.ANTHROPIC_API_KEY

        # Initialize BrandExtractor for visual branding extraction
        try:
            from festival_playlist_generator.services.brand_extractor import (
                BrandExtractor,
            )

            self.brand_extractor: Optional[BrandExtractor] = BrandExtractor()
            logger.info("BrandExtractor initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize BrandExtractor: {e}")
            self.brand_extractor = None

        # Initialize ImageMatcher for artist image matching
        try:
            from festival_playlist_generator.services.image_matcher import ImageMatcher

            self.image_matcher: Optional[ImageMatcher] = ImageMatcher()
            logger.info("ImageMatcher initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize ImageMatcher: {e}")
            self.image_matcher = None

    async def search_and_scrape_festival(
        self, festival_name: str, year: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for a festival by name and use AI to extract its data.

        Args:
            festival_name: Name of the festival (e.g., "Download Festival")
            year: Optional year (e.g., "2024")

        Returns:
            Festival data including artists, dates, location, etc.
        """
        logger.info(f"Searching for festival: {festival_name} {year or ''}")

        # Step 1: Find the festival's official website
        official_url = await self._find_festival_website(festival_name, year)

        if not official_url:
            logger.warning(f"Could not find official website for {festival_name}")
            return None

        logger.info(f"Found festival website: {official_url}")

        # Step 2: Use AI to extract festival data from the website
        festival_data = await self._ai_extract_festival_data(
            official_url, festival_name, year
        )

        return festival_data

    async def scrape_url_with_ai(
        self, url: str, festival_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Use AI to extract festival data from a specific URL.

        Args:
            url: The festival website URL
            festival_name: Name of the festival

        Returns:
            Festival data including artists, dates, location, etc.
        """
        return await self._ai_extract_festival_data(url, festival_name, None)

    async def _ai_extract_festival_data(
        self, url: str, festival_name: str, year: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Use AI (OpenAI or Anthropic) to extract festival data from a website."""
        try:
            # Fetch the website content
            async with httpx.AsyncClient(
                headers=self.headers, timeout=30.0, follow_redirects=True
            ) as client:
                response = await client.get(url)

                if response.status_code != 200:
                    logger.error(f"Failed to fetch {url}: {response.status_code}")
                    return None

                # Store the raw HTML for branding extraction
                raw_html = response.text

                # Parse HTML to clean it up but keep structure
                soup = BeautifulSoup(raw_html, "html.parser")

                # Try to extract artists directly from HTML first (more reliable for
                # large lineups)
                artists = self._extract_artists_from_html(soup)
                logger.info(f"Directly extracted {len(artists)} artists from HTML")

                # Remove script, style, and other non-content elements
                for element in soup(["script", "style", "noscript", "iframe"]):
                    element.decompose()

                # Get the cleaned HTML (keeping structure for AI to understand)
                html_content = str(soup)

                # Limit content length (AI models have token limits)
                # Keep it reasonable to avoid token limit errors
                max_chars = 30000
                if len(html_content) > max_chars:
                    # Try to find the container with the most artist/content information
                    # Look for common patterns in festival lineup pages
                    content_candidates = [
                        soup.find(
                            "div",
                            class_=lambda x: x
                            and (
                                "lineup" in str(x).lower()
                                or "artist" in str(x).lower()
                                or "posts-container" in str(x).lower()
                            ),
                        ),
                        soup.find(
                            "section",
                            class_=lambda x: x
                            and (
                                "lineup" in str(x).lower() or "artist" in str(x).lower()
                            ),
                        ),
                        soup.find("main"),
                        soup.find("article"),
                        soup.find("body"),
                    ]

                    # Use the first valid candidate
                    main_content = None
                    for candidate in content_candidates:
                        if candidate:
                            main_content = candidate
                            break

                    if main_content:
                        html_content = str(main_content)

                    # If still too long, truncate
                    if len(html_content) > max_chars:
                        html_content = (
                            html_content[:max_chars] + "\n... (content truncated)"
                        )

                logger.info(
                    f"Extracted {len(html_content)} characters of HTML from {url}"
                )

                # Use AI to extract festival metadata (dates, location, etc.)
                # But use our directly extracted artists if we found them
                if self.anthropic_api_key:
                    ai_data = await self._extract_with_anthropic(
                        html_content, festival_name, year, url
                    )
                elif self.openai_api_key:
                    ai_data = await self._extract_with_openai(
                        html_content, festival_name, year, url
                    )
                else:
                    logger.error(
                        "No AI API key configured (OPENAI_API_KEY or ANTHROPIC_API_KEY)"
                    )
                    ai_data = None

                # If we extracted artists directly and AI extraction worked, merge them
                if ai_data and artists:
                    # Use directly extracted artists if we found more than AI did
                    if len(artists) > len(ai_data.get("artists", [])):
                        logger.info(
                            f"Using directly extracted artists ({len(artists)}) "
                            f"instead of AI extracted "
                            f"({len(ai_data.get('artists', []))})"
                        )
                        ai_data["artists"] = artists
                elif artists:
                    # AI failed but we have artists - return basic data
                    logger.info("AI extraction failed, using directly extracted data")
                    ai_data = {
                        "name": festival_name,
                        "location": "",
                        "venue": "",
                        "dates": [],
                        "artists": artists,
                        "genres": [],
                        "source_url": url,
                    }

                # Extract visual branding (non-blocking)
                if ai_data and self.brand_extractor:
                    try:
                        logger.info(
                            "Extracting visual branding from festival website..."
                        )
                        branding = await self.brand_extractor.extract_festival_branding(
                            raw_html, url, festival_name
                        )

                        # Add branding data to festival data
                        ai_data["logo_url"] = branding.logo_url
                        ai_data["primary_color"] = branding.primary_color
                        ai_data["secondary_color"] = branding.secondary_color
                        ai_data["accent_colors"] = branding.accent_colors
                        ai_data["branding_extracted_at"] = datetime.utcnow().isoformat()

                        logger.info(
                            f"Branding extracted: logo={bool(branding.logo_url)}, "
                            f"colors={bool(branding.primary_color)}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Branding extraction failed (non-blocking): {e}"
                        )
                        # Continue without branding - this is non-blocking

                # Extract artist images (non-blocking)
                if ai_data and self.image_matcher and ai_data.get("artists"):
                    try:
                        logger.info("Matching artist images from festival website...")

                        # Extract lineup images
                        lineup_images = self.image_matcher.extract_lineup_images(
                            raw_html, url
                        )
                        logger.info(f"Found {len(lineup_images)} lineup images")

                        # Prioritize logo-style images
                        prioritized_images = self.image_matcher.prioritize_logos(
                            lineup_images
                        )

                        # Match images to artists using AI
                        artist_matches = (
                            await self.image_matcher.match_images_to_artists(
                                prioritized_images, ai_data["artists"]
                            )
                        )

                        logger.info(f"Matched {len(artist_matches)} artists to images")

                        # Store artist image data in a format that can be used
                        # later. We'll store it as a dict mapping artist name to
                        # (image_url, source)
                        ai_data["artist_images"] = {}
                        for artist_name, (
                            image_url,
                            confidence,
                        ) in artist_matches.items():
                            ai_data["artist_images"][artist_name] = {
                                "logo_url": image_url,
                                "logo_source": "festival",
                                "confidence": confidence,
                            }

                    except Exception as e:
                        logger.warning(
                            f"Artist image matching failed (non-blocking): {e}"
                        )
                        # Continue without artist images - this is non-blocking

                return ai_data

        except Exception as e:
            logger.error(f"Error in AI extraction: {e}")
            return None

    def _extract_artists_from_html(self, soup: BeautifulSoup) -> List[str]:
        """
        Directly extract artist names from HTML using common patterns.
        This is more reliable than AI for large lineups.
        """
        artists = []

        # Common patterns for artist names in festival websites
        patterns = [
            # Pattern 1: h3 with class containing "title" or "artist"
            (
                "h3",
                {
                    "class": lambda x: x
                    and any(
                        keyword in str(x).lower()
                        for keyword in ["title", "artist", "performer"]
                    )
                },
            ),
            # Pattern 2: h2 with class containing "title" or "artist"
            (
                "h2",
                {
                    "class": lambda x: x
                    and any(
                        keyword in str(x).lower()
                        for keyword in ["title", "artist", "performer"]
                    )
                },
            ),
            # Pattern 3: div with class containing "artist-name"
            (
                "div",
                {
                    "class": lambda x: x
                    and "artist" in str(x).lower()
                    and "name" in str(x).lower()
                },
            ),
            # Pattern 4: a tags with href containing "/artist/" or "/band/"
            (
                "a",
                {
                    "href": lambda x: x
                    and ("/artist/" in str(x).lower() or "/band/" in str(x).lower())
                },
            ),
        ]

        for tag, attrs in patterns:
            elements = soup.find_all(tag, attrs)  # type: ignore[arg-type]
            for elem in elements:
                # Get text content
                text = elem.get_text(strip=True)

                # Filter out non-artist entries
                if text and len(text) > 1 and len(text) < 100:
                    # Reasonable artist name length
                    # Skip common non-artist text
                    skip_words = [
                        "contact",
                        "faq",
                        "ticket",
                        "venue",
                        "info",
                        "sign up",
                        "news",
                        "home",
                        "about",
                    ]
                    if not any(skip in text.lower() for skip in skip_words):
                        if text not in artists:  # Avoid duplicates
                            artists.append(text)

            # If we found artists with this pattern, use them
            if artists:
                logger.info(
                    f"Found {len(artists)} artists using pattern: {tag} {attrs}"
                )
                break

        return artists

    async def _extract_with_anthropic(
        self, html_content: str, festival_name: str, year: Optional[str], url: str
    ) -> Optional[Dict[str, Any]]:
        """Use Anthropic Claude to extract festival data."""
        try:
            prompt = f"""You are analyzing HTML from a festival website to extract structured data.

Festival: {festival_name} {year or ''}
URL: {url}

Your task is to intelligently parse the HTML and extract:
1. Festival name
2. Location (city, country)
3. Venue name
4. Dates (in YYYY-MM-DD format)
5. List of ALL artists/performers you can find in the HTML (look for artist names in divs, links, lists, etc.)  # noqa: E501
6. Genres

HTML Content:
{html_content}

IMPORTANT: Look carefully through the HTML structure for artist names. They might be in:  # noqa: E501
- <div class="artist-title">Artist Name</div>
- <a href="/artist/...">Artist Name</a>
- <h2>, <h3>, or other heading tags
- List items (<li>)
- Any element with "artist", "performer", "act", or "band" in the class name  # noqa: E501

Extract as many artist names as you can find. Be thorough.

Respond ONLY with valid JSON in this exact format:
{{
    "name": "Festival Name",
    "location": "City, Country",
    "venue": "Venue Name",
    "dates": ["2024-06-14", "2024-06-15"],
    "artists": ["Artist 1", "Artist 2", "Artist 3", ...],
    "genres": ["Rock", "Metal"]
}}

If you cannot find certain information, use empty strings or empty arrays. Do not include any explanation, only the JSON."""  # noqa: E501

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 2000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"Anthropic API error: {response.status_code} - {response.text}"
                    )
                    return None

                result = response.json()
                content = result["content"][0]["text"]

                # Parse JSON response
                # Remove markdown code blocks if present
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                festival_data_raw = json.loads(content)
                festival_data: Dict[str, Any] = dict(festival_data_raw)
                festival_data["source_url"] = url

                logger.info(
                    f"AI extracted {len(festival_data.get('artists', []))} artists"
                )
                return festival_data

        except Exception as e:
            logger.error(f"Anthropic extraction error: {e}")
            return None

    async def _extract_with_openai(
        self, html_content: str, festival_name: str, year: Optional[str], url: str
    ) -> Optional[Dict[str, Any]]:
        """Use OpenAI GPT to extract festival data."""
        try:
            prompt = f"""You are analyzing HTML from a festival website to extract structured data.

Festival: {festival_name} {year or ''}
URL: {url}

Your task is to intelligently parse the HTML and extract:
1. Festival name
2. Location (city, country)
3. Venue name
4. Dates (in YYYY-MM-DD format)
5. List of ALL artists/performers you can find in the HTML (look for artist names in divs, links, lists, etc.)  # noqa: E501
6. Genres

HTML Content:
{html_content}

IMPORTANT: Look carefully through the HTML structure for artist names. They might be in:  # noqa: E501
- <div class="artist-title">Artist Name</div>
- <a href="/artist/...">Artist Name</a>
- <h2>, <h3>, or other heading tags
- List items (<li>)
- Any element with "artist", "performer", "act", or "band" in the class name  # noqa: E501

Extract as many artist names as you can find. Be thorough.

Respond ONLY with valid JSON in this exact format:
{{
    "name": "Festival Name",
    "location": "City, Country",
    "venue": "Venue Name",
    "dates": ["2024-06-14", "2024-06-15"],
    "artists": ["Artist 1", "Artist 2", "Artist 3", ...],
    "genres": ["Rock", "Metal"]
}}

If you cannot find certain information, use empty strings or empty arrays. Do not include any explanation, only the JSON."""  # noqa: E501

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are an expert at parsing HTML and "
                                    "extracting structured data. You understand "
                                    "HTML structure and can identify relevant "
                                    "information even in complex layouts. Always "
                                    "respond with valid JSON only."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"OpenAI API error: {response.status_code} - {response.text}"
                    )
                    return None

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # Parse JSON response
                # Remove markdown code blocks if present
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                festival_data_raw = json.loads(content)
                festival_data: Dict[str, Any] = dict(festival_data_raw)
                festival_data["source_url"] = url

                logger.info(
                    f"AI extracted {len(festival_data.get('artists', []))} artists"
                )
                return festival_data

        except Exception as e:
            logger.error(f"OpenAI extraction error: {e}")
            return None

    async def _find_festival_website(
        self, festival_name: str, year: Optional[str] = None
    ) -> Optional[str]:
        """Use Google search scraping to find the festival's official website."""
        # Try Google search scraping first
        google_result = await self._google_search_scrape(festival_name, year)
        if google_result:
            return google_result

        # Fallback to DuckDuckGo
        logger.info("Google scraping failed, trying DuckDuckGo...")
        return await self._duckduckgo_search(festival_name, year)

    async def _google_search_scrape(
        self, festival_name: str, year: Optional[str] = None
    ) -> Optional[str]:
        """Scrape Google search results directly."""
        try:
            search_query = (
                f"{festival_name} {year or ''} festival official website lineup"
            )
            url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"

            async with httpx.AsyncClient(
                headers=self.headers, timeout=10.0, follow_redirects=True
            ) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Google search results are in <a> tags with specific patterns
                    # Look for result links (not ads, not Google's own links)
                    links = soup.find_all("a", href=True)

                    for link in links:
                        href_value = link.get("href", "")
                        href = str(href_value) if href_value else ""

                        # Google wraps URLs in /url?q= format
                        if "/url?q=" in href:
                            # Extract the actual URL
                            actual_url = href.split("/url?q=")[1].split("&")[0]

                            # Decode URL encoding
                            from urllib.parse import unquote

                            actual_url = unquote(actual_url)

                            # Skip Google's own links and common non-festival sites
                            skip_domains = [
                                "google.com",
                                "youtube.com",
                                "facebook.com",
                                "twitter.com",
                                "instagram.com",
                                "wikipedia.org",
                            ]
                            if any(
                                domain in actual_url.lower() for domain in skip_domains
                            ):
                                continue

                            # Prefer official-looking domains
                            festival_slug = festival_name.lower().replace(" ", "")
                            if (
                                festival_slug in actual_url.lower()
                                or "festival" in actual_url.lower()
                            ):
                                logger.info(f"Google found: {actual_url}")
                                return actual_url

                    # If no perfect match, return first non-Google result
                    for link in links:
                        href_value = link.get("href", "")
                        href = str(href_value) if href_value else ""
                        if "/url?q=" in href:
                            actual_url = href.split("/url?q=")[1].split("&")[0]
                            from urllib.parse import unquote

                            actual_url = unquote(actual_url)

                            skip_domains = [
                                "google.com",
                                "youtube.com",
                                "facebook.com",
                                "twitter.com",
                                "instagram.com",
                            ]
                            if not any(
                                domain in actual_url.lower() for domain in skip_domains
                            ):
                                logger.info(f"Google found (fallback): {actual_url}")
                                return actual_url

        except Exception as e:
            logger.error(f"Google search scraping error: {e}")

        return None

    async def _duckduckgo_search(
        self, festival_name: str, year: Optional[str] = None
    ) -> Optional[str]:
        """Fallback search using DuckDuckGo HTML scraping."""
        try:
            search_query = f"{festival_name} {year or ''} festival lineup"
            url = (
                f"https://html.duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
            )

            async with httpx.AsyncClient(
                headers=self.headers, timeout=10.0, follow_redirects=True
            ) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    results = soup.find_all("a", class_="result__a")

                    for result in results[:5]:
                        link_value = result.get("href", "")
                        link = str(link_value) if link_value else ""
                        if link:
                            # DuckDuckGo wraps URLs - extract the actual URL
                            if "uddg=" in link:
                                from urllib.parse import unquote

                                # Extract the actual URL from the DuckDuckGo redirect
                                actual_url = link.split("uddg=")[1].split("&")[0]
                                actual_url = unquote(actual_url)

                                # Ensure it has a protocol
                                if not actual_url.startswith("http"):
                                    actual_url = (
                                        "https:" + actual_url
                                        if actual_url.startswith("//")
                                        else "https://" + actual_url
                                    )

                                logger.info(f"DuckDuckGo found: {actual_url}")
                                return actual_url
                            elif link.startswith("http"):
                                logger.info(f"DuckDuckGo found: {link}")
                                return link

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")

        # Try direct URL construction as last resort
        logger.info("Trying direct URL construction...")
        festival_slug = festival_name.lower().replace(" ", "")
        possible_urls = [
            f"https://www.{festival_slug}.com",
            f"https://www.{festival_slug}festival.com",
            f"https://{festival_slug}.co.uk",
        ]

        for url in possible_urls:
            try:
                async with httpx.AsyncClient(
                    headers=self.headers, timeout=5.0, follow_redirects=True
                ) as client:
                    response = await client.head(url)
                    if response.status_code == 200:
                        logger.info(f"Direct URL found: {url}")
                        return url
            except Exception:
                continue

        return None


# Global instance
festival_scraper = FestivalScraper()
