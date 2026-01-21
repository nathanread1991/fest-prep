"""
Image Matcher Service

Matches images to artists using AI-powered analysis and pattern matching.
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from bs4 import BeautifulSoup
import logging
import openai
import json

from festival_playlist_generator.services.brand_extractor import ImageInfo
from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)


class ImageMatcher:
    """Matches images to artists using AI and heuristics."""
    
    def __init__(self):
        """Initialize the ImageMatcher."""
        # Initialize OpenAI client if API key is available
        if settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
            self.ai_available = True
        else:
            self.ai_available = False
            logger.warning("OpenAI API key not configured. AI-powered image matching will be disabled.")
    
    def extract_lineup_images(self, html_content: str, base_url: str = "") -> List[ImageInfo]:
        """
        Extract all images from festival lineup section.
        
        Args:
            html_content: HTML content to analyze
            base_url: Base URL for resolving relative URLs
            
        Returns:
            List of ImageInfo objects from lineup section
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        images = []
        
        # Try to find lineup section
        lineup_section = self._find_lineup_section(soup)
        
        if lineup_section:
            logger.info("Found lineup section, extracting images from it")
            search_area = lineup_section
        else:
            logger.info("No specific lineup section found, searching entire page")
            search_area = soup
        
        # Find all img tags in the search area
        img_tags = search_area.find_all('img')
        
        for img in img_tags:
            # Get image URL
            url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if not url:
                continue
            
            # Resolve relative URLs
            if base_url and not url.startswith(('http://', 'https://', '//')):
                if url.startswith('/'):
                    # Absolute path
                    url = base_url.rstrip('/') + url
                else:
                    # Relative path
                    url = base_url.rstrip('/') + '/' + url
            
            # Get alt text
            alt_text = img.get('alt', '')
            
            # Get size attributes
            width = self._parse_dimension(img.get('width'))
            height = self._parse_dimension(img.get('height'))
            
            # Get surrounding context (parent elements)
            context = self._get_image_context(img)
            
            # Determine if it's logo-style
            is_logo_style = self._is_logo_style(url, alt_text, width, height)
            
            # Calculate position score (not as important for lineup images)
            position_score = 0.5
            
            image_info = ImageInfo(
                url=url,
                alt_text=alt_text,
                context=context,
                size=(width, height),
                is_logo_style=is_logo_style,
                position_score=position_score
            )
            
            images.append(image_info)
        
        logger.info(f"Extracted {len(images)} images from lineup section")
        return images
    
    def _find_lineup_section(self, soup: BeautifulSoup):
        """
        Find the lineup section in the HTML.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            BeautifulSoup element or None
        """
        # Try to find by common lineup section identifiers
        lineup_keywords = ['lineup', 'artists', 'performers', 'acts', 'bill']
        
        # Try by ID
        for keyword in lineup_keywords:
            section = soup.find(id=re.compile(keyword, re.IGNORECASE))
            if section:
                return section
        
        # Try by class
        for keyword in lineup_keywords:
            section = soup.find(class_=re.compile(keyword, re.IGNORECASE))
            if section:
                return section
        
        # Try by section/div with data attributes
        for keyword in lineup_keywords:
            section = soup.find(['section', 'div'], attrs={'data-section': re.compile(keyword, re.IGNORECASE)})
            if section:
                return section
        
        return None
    
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
        value = str(value).replace('px', '').strip()
        
        try:
            return int(value)
        except ValueError:
            return None
    
    def _get_image_context(self, img_tag) -> str:
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
                if parent.get('class'):
                    attrs.append(f"class={' '.join(parent.get('class'))}")
                if parent.get('id'):
                    attrs.append(f"id={parent.get('id')}")
                
                tag_str = parent.name
                if attrs:
                    tag_str += f"[{', '.join(attrs)}]"
                
                context_parts.append(tag_str)
                parent = parent.parent
            else:
                break
        
        return ' > '.join(reversed(context_parts))
    
    def _is_logo_style(self, url: str, alt_text: str, width: Optional[int], height: Optional[int]) -> bool:
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
        alt_lower = (alt_text or '').lower()
        
        # Check filename for logo keywords
        if any(keyword in url_lower for keyword in ['logo', 'brand', 'emblem', 'mark']):
            return True
        
        # Check alt text for logo keywords
        if any(keyword in alt_lower for keyword in ['logo', 'brand', 'emblem']):
            return True
        
        # Check for SVG (often used for logos)
        if url_lower.endswith('.svg'):
            return True
        
        # Check for PNG with transparency (common for logos)
        if url_lower.endswith('.png'):
            # Logos are often square or wide rectangles
            if width and height:
                aspect_ratio = width / height
                if 0.5 <= aspect_ratio <= 3.0:
                    return True
        
        return False
    
    def prioritize_logos(self, images: List[ImageInfo]) -> List[ImageInfo]:
        """
        Prioritize logo-style images over photos.
        
        Analyzes image characteristics like aspect ratio and transparency
        to identify logo-style images.
        
        Args:
            images: List of images to prioritize
            
        Returns:
            Sorted list with logo-style images first
        """
        # Separate logo-style and photo-style images
        logo_images = []
        photo_images = []
        
        for img in images:
            if img.is_logo_style:
                logo_images.append(img)
            else:
                photo_images.append(img)
        
        # Return logo images first, then photos
        return logo_images + photo_images
    
    async def match_images_to_artists(
        self,
        images: List[ImageInfo],
        artist_names: List[str]
    ) -> Dict[str, Tuple[str, float]]:
        """
        Use AI to match images to artist names.
        
        Args:
            images: List of images to match
            artist_names: List of artist names to match against
            
        Returns:
            Dictionary mapping artist names to (image_url, confidence_score)
        """
        if not self.ai_available:
            logger.warning("AI not available for image matching")
            return self._fallback_image_matching(images, artist_names)
        
        if not images or not artist_names:
            return {}
        
        try:
            # Limit to reasonable numbers for API
            images = images[:50]  # Max 50 images
            artist_names = artist_names[:100]  # Max 100 artists
            
            # Prepare image information for AI
            image_descriptions = []
            for i, img in enumerate(images):
                desc = {
                    'index': i,
                    'url': img.url,
                    'alt_text': img.alt_text or 'No alt text',
                    'context': img.context,
                    'is_logo_style': img.is_logo_style
                }
                image_descriptions.append(desc)
            
            # Create prompt for AI
            prompt = f"""You are analyzing a festival website to match artist images to artist names.

Artist Names:
{json.dumps(artist_names, indent=2)}

Images found on the page:
{json.dumps(image_descriptions, indent=2)}

Based on the image URLs, alt text, and context, match as many images as possible to the artist names.

Please respond with a JSON object where:
- Keys are artist names (exactly as provided)
- Values are objects with:
  - "image_index": the index of the matching image (0-{len(images)-1})
  - "confidence": your confidence level (0.0 to 1.0)

Only include matches where you have reasonable confidence (>0.3). If you can't match an artist, don't include them in the response."""

            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing website structure and matching images to artist names."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse response
            response_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
            
            result = json.loads(response_text)
            
            # Convert to our format
            matches = {}
            for artist_name, match_info in result.items():
                image_index = match_info.get('image_index', -1)
                confidence = match_info.get('confidence', 0.0)
                
                if image_index >= 0 and image_index < len(images) and confidence > 0.3:
                    matches[artist_name] = (images[image_index].url, confidence)
                    logger.info(f"Matched {artist_name} to image {image_index} with confidence {confidence}")
            
            logger.info(f"AI matched {len(matches)} artists to images")
            return matches
                
        except Exception as e:
            logger.error(f"Error in AI image matching: {e}", exc_info=True)
            return self._fallback_image_matching(images, artist_names)
    
    def _fallback_image_matching(
        self,
        images: List[ImageInfo],
        artist_names: List[str]
    ) -> Dict[str, Tuple[str, float]]:
        """
        Fallback pattern-based image matching.
        
        Uses heuristics to match images to artists:
        - Match alt text to artist names
        - Match URLs containing artist names
        - Match context containing artist names
        
        Args:
            images: List of images
            artist_names: List of artist names
            
        Returns:
            Dictionary mapping artist names to (image_url, confidence_score)
        """
        matches = {}
        
        for artist_name in artist_names:
            # Normalize artist name for matching
            artist_normalized = artist_name.lower().replace(' ', '').replace('-', '').replace('_', '')
            
            best_match = None
            best_score = 0.0
            
            for img in images:
                score = 0.0
                
                # Check alt text
                if img.alt_text:
                    alt_normalized = img.alt_text.lower().replace(' ', '').replace('-', '').replace('_', '')
                    if artist_normalized in alt_normalized:
                        score += 0.8
                    elif any(word in alt_normalized for word in artist_name.lower().split()):
                        score += 0.4
                
                # Check URL
                url_normalized = img.url.lower().replace(' ', '').replace('-', '').replace('_', '')
                if artist_normalized in url_normalized:
                    score += 0.6
                elif any(word in url_normalized for word in artist_name.lower().split()):
                    score += 0.3
                
                # Check context
                context_normalized = img.context.lower().replace(' ', '').replace('-', '').replace('_', '')
                if artist_normalized in context_normalized:
                    score += 0.4
                
                # Bonus for logo-style images
                if img.is_logo_style:
                    score += 0.2
                
                if score > best_score:
                    best_score = score
                    best_match = img.url
            
            # Only include matches with reasonable confidence
            if best_match and best_score > 0.3:
                matches[artist_name] = (best_match, best_score)
                logger.info(f"Fallback matched {artist_name} with score {best_score}")
        
        logger.info(f"Fallback matched {len(matches)} artists to images")
        return matches
    
    def apply_spotify_fallback(
        self,
        artist_matches: Dict[str, Tuple[str, float]],
        artist_spotify_images: Dict[str, str]
    ) -> Dict[str, Tuple[str, str]]:
        """
        Apply Spotify image fallback for artists without matched images.
        
        Args:
            artist_matches: Dictionary of artist_name -> (image_url, confidence)
            artist_spotify_images: Dictionary of artist_name -> spotify_image_url
            
        Returns:
            Dictionary of artist_name -> (image_url, source)
            where source is 'festival' or 'spotify'
        """
        result = {}
        
        # First, add all festival matches
        for artist_name, (image_url, confidence) in artist_matches.items():
            result[artist_name] = (image_url, 'festival')
        
        # Then, add Spotify fallbacks for missing artists
        for artist_name, spotify_url in artist_spotify_images.items():
            if artist_name not in result and spotify_url:
                result[artist_name] = (spotify_url, 'spotify')
                logger.info(f"Using Spotify fallback for {artist_name}")
        
        return result
