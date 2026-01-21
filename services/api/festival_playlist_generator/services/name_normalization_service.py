"""Name Normalization Service - Consistent artist name formatting and comparison."""

import re
from typing import Set


class NameNormalizationService:
    """Service for normalizing artist names to consistent format."""
    
    # Words that should stay all caps
    ALL_CAPS_WORDS: Set[str] = {
        'AC/DC', 'ACDC', 'USA', 'UK', 'DJ', 'MC', 'DMX', 'NWA', 'REM',
        'INXS', 'MGMT', 'AWOLNATION', 'MØ', 'BØRNS', 'CHVRCHES',
        'MSTRKRFT', 'STRFKR', 'SBTRKT', 'MNEK', 'HONNE', 'LANY'
    }
    
    # Articles and prepositions that should be lowercase (except at start)
    LOWERCASE_WORDS: Set[str] = {
        'of', 'the', 'and', 'a', 'an', 'in', 'on', 'at', 'to', 'for',
        'with', 'from', 'by', 'as', 'or', 'but', 'nor'
    }
    
    def normalize(self, name: str) -> str:
        """
        Normalize artist name to consistent format.
        
        Rules:
        - Trim whitespace
        - Collapse multiple spaces
        - Apply title case with exceptions
        - Preserve intentional all-caps words (AC/DC, USA, etc)
        - Lowercase articles and prepositions (except at start)
        
        Args:
            name: Artist name to normalize
            
        Returns:
            Normalized artist name
            
        Examples:
            >>> normalize("corrosion of conformity")
            "Corrosion of Conformity"
            >>> normalize("AC/DC")
            "AC/DC"
            >>> normalize("  the  beatles  ")
            "The Beatles"
        """
        if not name:
            return ""
        
        # Trim and collapse multiple spaces
        name = ' '.join(name.split())
        
        # Split into words, preserving special characters
        words = name.split()
        normalized_words = []
        
        for i, word in enumerate(words):
            # Check if word should stay all caps
            if word.upper() in self.ALL_CAPS_WORDS:
                normalized_words.append(word.upper())
            # Check if word should be lowercase (not at start)
            elif i > 0 and word.lower() in self.LOWERCASE_WORDS:
                normalized_words.append(word.lower())
            else:
                # Apply title case
                normalized_words.append(self._to_title_case(word))
        
        return ' '.join(normalized_words)
    
    def normalize_for_comparison(self, name: str) -> str:
        """
        Normalize name for case-insensitive comparison.
        
        This is used for duplicate detection and validation.
        Uses casefold() instead of lower() to handle Unicode edge cases
        like German ß correctly.
        
        Args:
            name: Artist name to normalize
            
        Returns:
            Casefolded, trimmed name for comparison
            
        Examples:
            >>> normalize_for_comparison("Corrosion Of Conformity")
            "corrosion of conformity"
            >>> normalize_for_comparison("  AC/DC  ")
            "ac/dc"
            >>> normalize_for_comparison("ß")
            "ss"
        """
        if not name:
            return ""
        
        # Trim, collapse spaces, and casefold (better than lower for Unicode)
        return ' '.join(name.split()).casefold()
    
    def is_all_caps_word(self, word: str) -> bool:
        """
        Check if word should stay all caps.
        
        Args:
            word: Word to check
            
        Returns:
            True if word should stay all caps
            
        Examples:
            >>> is_all_caps_word("AC/DC")
            True
            >>> is_all_caps_word("USA")
            True
            >>> is_all_caps_word("Beatles")
            False
        """
        return word.upper() in self.ALL_CAPS_WORDS
    
    def _to_title_case(self, word: str) -> str:
        """
        Convert word to title case, handling special characters.
        
        Handles words with apostrophes, hyphens, and other punctuation.
        
        Args:
            word: Word to convert
            
        Returns:
            Title-cased word
            
        Examples:
            >>> _to_title_case("o'brien")
            "O'Brien"
            >>> _to_title_case("hip-hop")
            "Hip-Hop"
            >>> _to_title_case("(the)")
            "(The)"
        """
        if not word:
            return ""
        
        # Handle words with apostrophes (O'Brien, D'Angelo)
        if "'" in word:
            parts = word.split("'")
            return "'".join(part.capitalize() for part in parts)
        
        # Handle words with hyphens (Hip-Hop, Post-Punk)
        if "-" in word:
            parts = word.split("-")
            return "-".join(part.capitalize() for part in parts)
        
        # Handle words with parentheses or brackets
        if word.startswith(('(', '[', '{')) and len(word) > 1:
            return word[0] + word[1:].capitalize()
        
        # Default: capitalize first letter
        return word.capitalize()


# Global instance
name_normalization_service = NameNormalizationService()
