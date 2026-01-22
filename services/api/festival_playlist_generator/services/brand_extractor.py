"""
Brand Extractor Service

Extracts visual branding (logos, colors, images) from festival websites.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import openai
from bs4 import BeautifulSoup

from festival_playlist_generator.core.config import settings
from festival_playlist_generator.services.color_analyzer import (
    ColorAnalyzer,
    ColorScheme,
)

logger = logging.getLogger(__name__)


@dataclass
class ImageInfo:
    """Information about an image found in HTML."""

    url: str
    alt_text: Optional[str]
    context: str  # Surrounding HTML context
    size: Tuple[Optional[int], Optional[int]]  # (width, height)
    is_logo_style: bool
    position_score: float  # Higher score = more prominent position


@dataclass
class FestivalBranding:
    """Complete branding information for a festival."""

    logo_url: Optional[str]
    primary_color: Optional[str]  # Hex format
    secondary_color: Optional[str]
    accent_colors: List[str]
    confidence_score: float


class BrandExtractor:
    """Extracts visual branding from festival websites."""

    def __init__(self) -> None:
        """Initialize the BrandExtractor."""
        self.color_analyzer = ColorAnalyzer()

        # Initialize OpenAI client if API key is available
        if settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
            self.ai_available = True
        else:
            self.ai_available = False
            logger.warning(
                "OpenAI API key not configured. AI-powered logo identification will be disabled."
            )

    def extract_all_images(
        self, html_content: str, base_url: str = ""
    ) -> List[ImageInfo]:
        """
        Find all images in HTML and extract metadata.

        Args:
            html_content: HTML content to analyze
            base_url: Base URL for resolving relative URLs

        Returns:
            List of ImageInfo objects
        """
        soup = BeautifulSoup(html_content, "html.parser")
        images = []

        # Find all img tags
        img_tags = soup.find_all("img")

        for img in img_tags:
            # Get image URL
            url_raw = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if not url_raw:
                continue
            
            # Convert to string (handle AttributeValueList)
            url = str(url_raw) if url_raw else ""
            if not url:
                continue

            # Resolve relative URLs
            if base_url and not url.startswith(("http://", "https://", "//")):
                if url.startswith("/"):
                    # Absolute path
                    url = base_url.rstrip("/") + url
                else:
                    # Relative path
                    url = base_url.rstrip("/") + "/" + url

            # Get alt text
            alt_text_raw = img.get("alt", "")
            alt_text = str(alt_text_raw) if alt_text_raw else ""

            # Get size attributes
            width_raw = img.get("width")
            height_raw = img.get("height")
            width = self._parse_dimension(str(width_raw) if width_raw else None)
            height = self._parse_dimension(str(height_raw) if height_raw else None)

            # Get surrounding context (parent elements)
            context = self._get_image_context(img)

            # Calculate position score (higher = more prominent)
            position_score = self._calculate_position_score(img, context)

            # Determine if it's logo-style
            is_logo_style = self._is_logo_style(url, alt_text, width, height)

            image_info = ImageInfo(
                url=url,
                alt_text=alt_text if alt_text else None,
                context=context,
                size=(width, height),
                is_logo_style=is_logo_style,
                position_score=position_score,
            )

            images.append(image_info)

        return images

    def filter_logo_candidates(self, images: List[ImageInfo]) -> List[ImageInfo]:
        """
        Filter images to find likely logo candidates.

        Filters by:
        - Size (logos are typically medium-large, not tiny icons or huge banners)
        - Position (logos are typically in header/top of page)
        - Style (logo-style images preferred)

        Args:
            images: List of all images

        Returns:
            Filtered list of logo candidates, sorted by likelihood
        """
        candidates = []

        for img in images:
            # Skip very small images (likely icons)
            width, height = img.size
            if width and height:
                if width < 50 or height < 50:
                    continue
                # Skip very large images (likely banners or photos)
                if width > 1000 or height > 1000:
                    continue

            # Prefer images with high position scores
            if img.position_score < 0.3:
                continue

            candidates.append(img)

        # Sort by position score (descending) and logo style
        candidates.sort(key=lambda x: (x.is_logo_style, x.position_score), reverse=True)

        return candidates

    def _parse_dimension(self, value: Optional[str]) -> Optional[int]:
        """
        Parse a dimension value (width or height).

        Args:
            value: Dimension value as string (e.g., "200", "200px")

        Returns:
            Integer dimension or None
        """
        if not value:
            return None

        # Remove 'px' suffix if present
        value = str(value).replace("px", "").strip()

        try:
            return int(value)
        except ValueError:
            return None

    def _get_image_context(self, img_tag: Any) -> str:
        """
        Get the surrounding HTML context for an image.

        Args:
            img_tag: BeautifulSoup img tag

        Returns:
            String representation of parent elements
        """
        context_parts = []

        # Get parent tags up to 3 levels
        parent = img_tag.parent
        for _ in range(3):
            if parent and parent.name:
                # Get tag name and relevant attributes
                attrs = []
                if parent.get("class"):
                    attrs.append(f"class={' '.join(parent.get('class'))}")
                if parent.get("id"):
                    attrs.append(f"id={parent.get('id')}")

                tag_str = parent.name
                if attrs:
                    tag_str += f"[{', '.join(attrs)}]"

                context_parts.append(tag_str)
                parent = parent.parent
            else:
                break

        return " > ".join(reversed(context_parts))

    def _calculate_position_score(self, img_tag: Any, context: str) -> float:
        """
        Calculate a position score for an image (0.0 to 1.0).

        Higher scores indicate more prominent positions (header, top of page).

        Args:
            img_tag: BeautifulSoup img tag
            context: Context string from _get_image_context

        Returns:
            Position score (0.0 to 1.0)
        """
        score = 0.5  # Base score

        context_lower = context.lower()

        # Check for header/banner context
        if any(
            keyword in context_lower
            for keyword in ["header", "banner", "logo", "brand", "nav"]
        ):
            score += 0.3

        # Check for footer (negative score)
        if "footer" in context_lower:
            score -= 0.3

        # Check for sidebar (slight negative)
        if "sidebar" in context_lower or "aside" in context_lower:
            score -= 0.1

        # Check alt text
        alt_text = (img_tag.get("alt") or "").lower()
        if any(keyword in alt_text for keyword in ["logo", "brand", "festival"]):
            score += 0.2

        # Clamp to 0.0-1.0
        return max(0.0, min(1.0, score))

    def _is_logo_style(
        self, url: str, alt_text: str, width: Optional[int], height: Optional[int]
    ) -> bool:
        """
        Determine if an image is likely a logo based on characteristics.

        Args:
            url: Image URL
            alt_text: Alt text
            width: Image width
            height: Image height

        Returns:
            True if likely a logo
        """
        url_lower = url.lower()
        alt_lower = (alt_text or "").lower()

        # Check filename for logo keywords
        if any(keyword in url_lower for keyword in ["logo", "brand", "emblem", "mark"]):
            return True

        # Check alt text for logo keywords
        if any(keyword in alt_lower for keyword in ["logo", "brand", "emblem"]):
            return True

        # Check for SVG (often used for logos)
        if url_lower.endswith(".svg"):
            return True

        # Check for PNG with transparency (common for logos)
        if url_lower.endswith(".png"):
            # Logos are often square or wide rectangles
            if width and height:
                aspect_ratio = width / height
                if 0.5 <= aspect_ratio <= 3.0:
                    return True

        return False

    async def extract_logo_with_ai(
        self, festival_name: str, images: List[ImageInfo]
    ) -> Tuple[Optional[str], float]:
        """
        Use AI to identify the festival logo from a list of images.

        Args:
            festival_name: Name of the festival
            images: List of candidate images

        Returns:
            Tuple of (logo_url, confidence_score)
        """
        if not self.ai_available:
            logger.warning("AI not available for logo identification")
            return None, 0.0

        if not images:
            return None, 0.0

        try:
            # Prepare image information for AI
            image_descriptions = []
            for i, img in enumerate(images[:10]):  # Limit to top 10 candidates
                desc = {
                    "index": i,
                    "url": img.url,
                    "alt_text": img.alt_text or "No alt text",
                    "context": img.context,
                    "is_logo_style": img.is_logo_style,
                    "position_score": img.position_score,
                }
                image_descriptions.append(desc)

            # Create prompt for AI
            prompt = f"""You are analyzing a festival website to identify the main festival logo.

Festival Name: {festival_name}

Here are the candidate images found on the page:

{json.dumps(image_descriptions, indent=2)}

Based on the image URLs, alt text, context, and position scores, which image is most likely the main festival logo?

Please respond with a JSON object containing:
- "index": the index of the most likely logo image (0-{len(image_descriptions)-1})
- "confidence": your confidence level (0.0 to 1.0)
- "reasoning": brief explanation of your choice

If none of the images appear to be a festival logo, set index to -1 and confidence to 0.0."""

            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing website structure and identifying brand logos.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            # Parse response
            response_text = response.choices[0].message.content.strip()

            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)

            result = json.loads(response_text)

            index = result.get("index", -1)
            confidence = result.get("confidence", 0.0)
            reasoning = result.get("reasoning", "")

            logger.info(
                f"AI logo identification: index={index}, confidence={confidence}, reasoning={reasoning}"
            )

            if index >= 0 and index < len(images):
                return images[index].url, confidence
            else:
                return None, 0.0

        except Exception as e:
            logger.error(f"Error in AI logo identification: {e}", exc_info=True)
            return None, 0.0

    async def extract_festival_branding(
        self, html_content: str, url: str, festival_name: str = ""
    ) -> FestivalBranding:
        """
        Extract complete visual branding from festival website.

        This is the main entry point that orchestrates logo and color extraction.

        Args:
            html_content: HTML content of the festival website
            url: Base URL of the festival website
            festival_name: Name of the festival (for AI context)

        Returns:
            FestivalBranding object with logo and colors
        """
        try:
            # Extract all images
            all_images = self.extract_all_images(html_content, url)
            logger.info(f"Found {len(all_images)} total images")

            # Filter to logo candidates
            logo_candidates = self.filter_logo_candidates(all_images)
            logger.info(f"Filtered to {len(logo_candidates)} logo candidates")

            # Try AI-powered logo identification first
            logo_url = None
            confidence = 0.0

            if self.ai_available and logo_candidates:
                logo_url, confidence = await self.extract_logo_with_ai(
                    festival_name, logo_candidates
                )
                logger.info(
                    f"AI logo identification: url={logo_url}, confidence={confidence}"
                )

            # If AI didn't find a logo with high confidence, use fallback
            if not logo_url or confidence < 0.5:
                fallback_logo = self._fallback_logo_extraction(logo_candidates)
                if fallback_logo:
                    logo_url = fallback_logo
                    logger.info(f"Using fallback logo: {logo_url}")

            # Extract colors using ColorAnalyzer
            colors = self.color_analyzer.extract_from_css(html_content)
            logger.info(f"Extracted {len(colors)} colors from CSS")

            # Rank colors to create scheme
            color_scheme = self.color_analyzer.rank_colors(colors)

            # Create branding object
            branding = FestivalBranding(
                logo_url=logo_url,
                primary_color=color_scheme.primary,
                secondary_color=color_scheme.secondary,
                accent_colors=color_scheme.accents,
                confidence_score=confidence,
            )

            logger.info(
                f"Extracted branding: logo={bool(logo_url)}, colors={bool(color_scheme.primary)}"
            )

            return branding

        except Exception as e:
            logger.error(f"Error extracting festival branding: {e}", exc_info=True)
            # Return default branding on error
            return FestivalBranding(
                logo_url=None,
                primary_color="#667EEA",
                secondary_color="#764BA2",
                accent_colors=["#FFFFFF"],
                confidence_score=0.0,
            )

    def _fallback_logo_extraction(
        self, logo_candidates: List[ImageInfo]
    ) -> Optional[str]:
        """
        Fallback pattern-based logo extraction.

        Uses heuristics to identify the most likely logo:
        - Images with "logo" in filename or alt text
        - Images in header/banner sections
        - Images with high position scores

        Args:
            logo_candidates: List of filtered logo candidates

        Returns:
            Logo URL or None
        """
        if not logo_candidates:
            return None

        # Score each candidate
        scored_candidates = []

        for img in logo_candidates:
            score = 0.0

            # Check URL for logo keywords
            url_lower = img.url.lower()
            if "logo" in url_lower:
                score += 3.0
            if "brand" in url_lower:
                score += 2.0
            if "emblem" in url_lower or "mark" in url_lower:
                score += 2.0

            # Check alt text for logo keywords
            alt_lower = (img.alt_text or "").lower()
            if "logo" in alt_lower:
                score += 3.0
            if "brand" in alt_lower:
                score += 2.0
            if "festival" in alt_lower:
                score += 1.0

            # Check context for header/banner
            context_lower = img.context.lower()
            if "header" in context_lower:
                score += 2.0
            if "banner" in context_lower:
                score += 1.5
            if "logo" in context_lower:
                score += 2.0
            if "nav" in context_lower:
                score += 1.0

            # Add position score
            score += img.position_score * 2.0

            # Bonus for logo-style images
            if img.is_logo_style:
                score += 1.5

            # Bonus for SVG (common for logos)
            if img.url.lower().endswith(".svg"):
                score += 1.0

            scored_candidates.append((img, score))

        # Sort by score (descending)
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Log top candidates
        logger.info("Top logo candidates by fallback scoring:")
        for i, (img, score) in enumerate(scored_candidates[:3]):
            logger.info(
                f"  {i+1}. Score={score:.2f}, URL={img.url}, Alt={img.alt_text}"
            )

        # Return the highest scoring candidate
        if scored_candidates and scored_candidates[0][1] > 0:
            return scored_candidates[0][0].url

        return None
