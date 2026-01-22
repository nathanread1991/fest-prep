"""
Color Analyzer Service

Extracts and analyzes color schemes from HTML/CSS content.
"""

import colorsys
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class ColorScheme:
    """Represents a color scheme with primary, secondary, and accent colors."""

    primary: str
    secondary: str
    accents: List[str]


class ColorAnalyzer:
    """Analyzes and extracts color schemes from websites."""

    # Named CSS colors to hex mapping (subset of most common colors)
    NAMED_COLORS = {
        "black": "#000000",
        "white": "#ffffff",
        "red": "#ff0000",
        "green": "#008000",
        "blue": "#0000ff",
        "yellow": "#ffff00",
        "cyan": "#00ffff",
        "magenta": "#ff00ff",
        "silver": "#c0c0c0",
        "gray": "#808080",
        "grey": "#808080",
        "maroon": "#800000",
        "olive": "#808000",
        "lime": "#00ff00",
        "aqua": "#00ffff",
        "teal": "#008080",
        "navy": "#000080",
        "fuchsia": "#ff00ff",
        "purple": "#800080",
        "orange": "#ffa500",
        "pink": "#ffc0cb",
        "brown": "#a52a2a",
        "gold": "#ffd700",
        "indigo": "#4b0082",
        "violet": "#ee82ee",
    }

    def __init__(self) -> None:
        """Initialize the ColorAnalyzer."""
        pass

    def extract_from_css(self, html_content: str) -> List[str]:
        """
        Extract colors from CSS in HTML content.

        Extracts colors from:
        - Inline styles
        - <style> tags
        - CSS properties (background-color, color, border-color, etc.)

        Args:
            html_content: HTML content to analyze

        Returns:
            List of colors in hex format
        """
        colors = []

        # Extract from inline styles
        inline_style_pattern = r'style=["\']([^"\']*)["\']'
        inline_matches = re.findall(inline_style_pattern, html_content, re.IGNORECASE)
        for style in inline_matches:
            colors.extend(self._extract_colors_from_css_text(style))

        # Extract from <style> tags
        style_tag_pattern = r"<style[^>]*>(.*?)</style>"
        style_matches = re.findall(
            style_tag_pattern, html_content, re.IGNORECASE | re.DOTALL
        )
        for style_content in style_matches:
            colors.extend(self._extract_colors_from_css_text(style_content))

        # Convert all to hex format
        hex_colors = []
        for color in colors:
            hex_color = self._to_hex(color)
            if hex_color:
                hex_colors.append(hex_color)

        return hex_colors

    def _extract_colors_from_css_text(self, css_text: str) -> List[str]:
        """
        Extract color values from CSS text.

        Args:
            css_text: CSS text content

        Returns:
            List of color values (various formats)
        """
        colors = []

        # Match hex colors (#RGB or #RRGGBB) - keep the # symbol
        hex_pattern = r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b"
        hex_matches = re.findall(hex_pattern, css_text)
        for match in hex_matches:
            colors.append(f"#{match}")

        # Match rgb/rgba colors
        rgb_pattern = (
            r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*[\d.]+)?\s*\)"
        )
        rgb_matches = re.findall(rgb_pattern, css_text)
        for match in rgb_matches:
            colors.append(f"rgb({match[0]},{match[1]},{match[2]})")

        # Match named colors
        for name in self.NAMED_COLORS.keys():
            # Use word boundaries to avoid partial matches
            if re.search(r"\b" + name + r"\b", css_text, re.IGNORECASE):
                colors.append(name.lower())

        return colors

    def _to_hex(self, color: str) -> Optional[str]:
        """
        Convert a color value to hex format.

        Args:
            color: Color in various formats (hex, rgb, named)

        Returns:
            Color in hex format (#RRGGBB) or None if invalid
        """
        color = color.strip().lower()

        # Already hex format
        if color.startswith("#"):
            # Expand 3-digit hex to 6-digit
            if len(color) == 4:  # #RGB
                r_hex, g_hex, b_hex = color[1], color[2], color[3]
                return f"#{r_hex}{r_hex}{g_hex}{g_hex}{b_hex}{b_hex}"
            elif len(color) == 7:  # #RRGGBB
                return color.upper()
            else:
                return None

        # Named color
        if color in self.NAMED_COLORS:
            return self.NAMED_COLORS[color].upper()

        # RGB format
        if color.startswith("rgb"):
            rgb_match = re.match(r"rgba?\s*\((\d+),(\d+),(\d+)", color)
            if rgb_match:
                r: int = int(rgb_match.group(1))
                g: int = int(rgb_match.group(2))
                b: int = int(rgb_match.group(3))
                # Clamp values to 0-255
                r = max(0, min(255, r))
                g = max(0, min(255, g))
                b = max(0, min(255, b))
                return f"#{r:02X}{g:02X}{b:02X}"

        return None

    def rank_colors(self, colors: List[str]) -> ColorScheme:
        """
        Rank colors by frequency and prominence to create a color scheme.

        Args:
            colors: List of colors in hex format

        Returns:
            ColorScheme with primary, secondary, and accent colors
        """
        if not colors:
            # Return default scheme if no colors found
            return ColorScheme(
                primary="#667EEA", secondary="#764BA2", accents=["#FFFFFF"]
            )

        # Filter out very common colors (black, white, grays)
        filtered_colors = self._filter_common_colors(colors)

        # If all colors were filtered, use the original list
        if not filtered_colors:
            filtered_colors = colors

        # Count color frequency
        color_counts = Counter(filtered_colors)

        # Get most common colors
        most_common = color_counts.most_common(5)

        # Extract colors
        primary = most_common[0][0] if len(most_common) > 0 else "#667EEA"
        secondary = (
            most_common[1][0]
            if len(most_common) > 1
            else self._generate_complementary(primary)
        )

        # Get accent colors (up to 3)
        accents = [color for color, _ in most_common[2:5]]
        if not accents:
            accents = ["#FFFFFF"]

        # Ensure contrast for accessibility
        if not self.ensure_contrast(primary, "#FFFFFF"):
            # If primary doesn't have good contrast with white, try to adjust
            primary = self._adjust_for_contrast(primary)

        return ColorScheme(primary=primary, secondary=secondary, accents=accents)

    def _filter_common_colors(self, colors: List[str]) -> List[str]:
        """
        Filter out very common colors like black, white, and grays.

        Args:
            colors: List of colors in hex format

        Returns:
            Filtered list of colors
        """
        filtered = []
        for color in colors:
            # Skip black, white, and grays
            if color.upper() in ["#000000", "#FFFFFF"]:
                continue

            # Check if it's a gray (R=G=B)
            if len(color) == 7:
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                if r == g == b:
                    continue

            filtered.append(color)

        return filtered

    def ensure_contrast(self, bg_color: str, text_color: str) -> bool:
        """
        Ensure sufficient contrast between background and text colors.

        Uses WCAG 2.0 guidelines (4.5:1 for normal text).

        Args:
            bg_color: Background color in hex format
            text_color: Text color in hex format

        Returns:
            True if contrast is sufficient, False otherwise
        """
        contrast_ratio = self._calculate_contrast_ratio(bg_color, text_color)
        return contrast_ratio >= 4.5

    def _calculate_contrast_ratio(self, color1: str, color2: str) -> float:
        """
        Calculate contrast ratio between two colors.

        Args:
            color1: First color in hex format
            color2: Second color in hex format

        Returns:
            Contrast ratio (1.0 to 21.0)
        """
        lum1 = self._get_relative_luminance(color1)
        lum2 = self._get_relative_luminance(color2)

        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)

        return (lighter + 0.05) / (darker + 0.05)

    def _get_relative_luminance(self, color: str) -> float:
        """
        Calculate relative luminance of a color.

        Args:
            color: Color in hex format

        Returns:
            Relative luminance (0.0 to 1.0)
        """
        # Convert hex to RGB
        r = int(color[1:3], 16) / 255.0
        g = int(color[3:5], 16) / 255.0
        b = int(color[5:7], 16) / 255.0

        # Apply gamma correction
        def gamma_correct(c: float) -> float:
            if c <= 0.03928:
                result: float = c / 12.92
                return result
            else:
                result_exp: float = ((c + 0.055) / 1.055) ** 2.4
                return result_exp

        r_corrected: float = gamma_correct(r)
        g_corrected: float = gamma_correct(g)
        b_corrected: float = gamma_correct(b)

        # Calculate luminance
        luminance: float = 0.2126 * r_corrected + 0.7152 * g_corrected + 0.0722 * b_corrected
        return luminance

    def _adjust_for_contrast(self, color: str) -> str:
        """
        Adjust a color to ensure better contrast with white text.

        Args:
            color: Color in hex format

        Returns:
            Adjusted color in hex format
        """
        # Convert to HSL
        r = int(color[1:3], 16) / 255.0
        g = int(color[3:5], 16) / 255.0
        b = int(color[5:7], 16) / 255.0

        h, l, s = colorsys.rgb_to_hls(r, g, b)

        # Darken the color if it's too light
        if l > 0.5:
            l = 0.4

        # Convert back to RGB
        r, g, b = colorsys.hls_to_rgb(h, l, s)

        return f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"

    def _generate_complementary(self, color: str) -> str:
        """
        Generate a complementary color using color theory.

        Args:
            color: Color in hex format

        Returns:
            Complementary color in hex format
        """
        # Convert to HSL
        r = int(color[1:3], 16) / 255.0
        g = int(color[3:5], 16) / 255.0
        b = int(color[5:7], 16) / 255.0

        h, l, s = colorsys.rgb_to_hls(r, g, b)

        # Rotate hue by 180 degrees for complementary color
        h = (h + 0.5) % 1.0

        # Convert back to RGB
        r, g, b = colorsys.hls_to_rgb(h, l, s)

        return f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"
