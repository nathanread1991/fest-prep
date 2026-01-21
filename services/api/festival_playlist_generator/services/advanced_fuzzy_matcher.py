"""
Advanced Fuzzy Matching for Artist Names

Combines multiple strategies:
1. Traditional string similarity (Levenshtein, Jaro-Winkler)
2. Phonetic matching (Soundex, Metaphone)
3. Token-based fuzzy matching
4. OpenAI embeddings for semantic similarity
5. Hybrid scoring system

Target: 95%+ accuracy on misspelled/variant artist names
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import re
import logging
from functools import lru_cache
import asyncio

from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# STRING SIMILARITY ALGORITHMS
# ============================================================================

def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein (edit) distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def jaro_winkler_similarity(s1: str, s2: str) -> float:
    """
    Calculate Jaro-Winkler similarity (0.0 to 1.0).
    Better than Levenshtein for short strings and typos.
    """
    s1, s2 = s1.lower(), s2.lower()
    
    if s1 == s2:
        return 1.0
    
    len1, len2 = len(s1), len(s2)
    
    if len1 == 0 or len2 == 0:
        return 0.0
    
    # Maximum allowed distance
    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 1:
        match_distance = 1
    
    s1_matches = [False] * len1
    s2_matches = [False] * len2
    
    matches = 0
    transpositions = 0
    
    # Find matches
    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = s2_matches[j] = True
            matches += 1
            break
    
    if matches == 0:
        return 0.0
    
    # Count transpositions
    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1
    
    # Jaro similarity
    jaro = (matches / len1 + matches / len2 + 
            (matches - transpositions / 2) / matches) / 3
    
    # Jaro-Winkler modification (boost for common prefix)
    prefix = 0
    for i in range(min(len1, len2)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break
    prefix = min(4, prefix)  # Max prefix length of 4
    
    return jaro + (prefix * 0.1 * (1 - jaro))


# ============================================================================
# PHONETIC ALGORITHMS
# ============================================================================

@lru_cache(maxsize=1000)
def double_metaphone(name: str) -> Tuple[str, str]:
    """
    Double Metaphone algorithm - returns primary and secondary phonetic codes.
    More accurate than Soundex for English names.
    """
    # Simplified implementation - in production, use a library like 'metaphone'
    name = re.sub(r'[^A-Za-z]', '', name).upper()
    
    if not name:
        return ("", "")
    
    primary = []
    secondary = []
    current = 0
    length = len(name)
    last = length - 1
    
    # Helper function
    def get_at(index):
        if 0 <= index < length:
            return name[index]
        return ''
    
    # Simplified rules (full implementation would be much longer)
    while current < length:
        char = name[current]
        
        if char in 'AEIOU':
            if current == 0:
                primary.append('A')
                secondary.append('A')
            current += 1
            
        elif char == 'B':
            primary.append('P')
            secondary.append('P')
            current += 2 if get_at(current + 1) == 'B' else 1
            
        elif char == 'C':
            # CH
            if get_at(current + 1) == 'H':
                primary.append('X')
                secondary.append('X')
                current += 2
            # CE, CI, CY
            elif get_at(current + 1) in 'EIY':
                primary.append('S')
                secondary.append('S')
                current += 1
            else:
                primary.append('K')
                secondary.append('K')
                current += 1
                
        elif char == 'D':
            # DGE, DGI, DGY
            if get_at(current + 1) == 'G' and get_at(current + 2) in 'EIY':
                primary.append('J')
                secondary.append('J')
                current += 3
            else:
                primary.append('T')
                secondary.append('T')
                current += 1
                
        elif char == 'F':
            primary.append('F')
            secondary.append('F')
            current += 2 if get_at(current + 1) == 'F' else 1
            
        elif char == 'G':
            # GH
            if get_at(current + 1) == 'H':
                if current > 0:
                    primary.append('K')
                    secondary.append('K')
                current += 2
            # GN
            elif get_at(current + 1) == 'N':
                current += 2
            # GE, GI, GY
            elif get_at(current + 1) in 'EIY':
                primary.append('J')
                secondary.append('J')
                current += 1
            else:
                primary.append('K')
                secondary.append('K')
                current += 1
                
        elif char == 'H':
            # Keep H if between vowels
            if current > 0 and get_at(current - 1) in 'AEIOU' and get_at(current + 1) in 'AEIOU':
                primary.append('H')
                secondary.append('H')
            current += 1
            
        elif char == 'J':
            primary.append('J')
            secondary.append('J')
            current += 1
            
        elif char == 'K':
            primary.append('K')
            secondary.append('K')
            current += 2 if get_at(current + 1) == 'K' else 1
            
        elif char == 'L':
            primary.append('L')
            secondary.append('L')
            current += 2 if get_at(current + 1) == 'L' else 1
            
        elif char == 'M':
            primary.append('M')
            secondary.append('M')
            current += 2 if get_at(current + 1) == 'M' else 1
            
        elif char == 'N':
            primary.append('N')
            secondary.append('N')
            current += 2 if get_at(current + 1) == 'N' else 1
            
        elif char == 'P':
            # PH
            if get_at(current + 1) == 'H':
                primary.append('F')
                secondary.append('F')
                current += 2
            else:
                primary.append('P')
                secondary.append('P')
                current += 2 if get_at(current + 1) == 'P' else 1
                
        elif char == 'Q':
            primary.append('K')
            secondary.append('K')
            current += 2 if get_at(current + 1) == 'Q' else 1
            
        elif char == 'R':
            primary.append('R')
            secondary.append('R')
            current += 2 if get_at(current + 1) == 'R' else 1
            
        elif char == 'S':
            # SH
            if get_at(current + 1) == 'H':
                primary.append('X')
                secondary.append('X')
                current += 2
            else:
                primary.append('S')
                secondary.append('S')
                current += 2 if get_at(current + 1) == 'S' else 1
                
        elif char == 'T':
            # TH
            if get_at(current + 1) == 'H':
                primary.append('0')
                secondary.append('0')
                current += 2
            # TIO, TIA
            elif get_at(current + 1) == 'I' and get_at(current + 2) in 'AO':
                primary.append('X')
                secondary.append('X')
                current += 3
            else:
                primary.append('T')
                secondary.append('T')
                current += 2 if get_at(current + 1) == 'T' else 1
                
        elif char == 'V':
            primary.append('F')
            secondary.append('F')
            current += 1
            
        elif char == 'W':
            # WH
            if current == 0 and get_at(current + 1) == 'H':
                primary.append('W')
                secondary.append('W')
                current += 2
            # Vowel before W
            elif current > 0 and get_at(current - 1) in 'AEIOU':
                primary.append('W')
                secondary.append('W')
                current += 1
            else:
                current += 1
                
        elif char == 'X':
            primary.append('KS')
            secondary.append('KS')
            current += 1
            
        elif char == 'Y':
            if get_at(current + 1) in 'AEIOU':
                primary.append('Y')
                secondary.append('Y')
            current += 1
            
        elif char == 'Z':
            primary.append('S')
            secondary.append('S')
            current += 2 if get_at(current + 1) == 'Z' else 1
            
        else:
            current += 1
    
    return (''.join(primary)[:8], ''.join(secondary)[:8])


# ============================================================================
# TOKEN-BASED MATCHING
# ============================================================================

def normalize_for_matching(text: str) -> str:
    """Normalize text for matching."""
    text = text.lower()
    text = text.replace('&', 'and')
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def tokenize(text: str) -> List[str]:
    """Tokenize text into words, removing stop words."""
    text = normalize_for_matching(text)
    words = text.split()
    stop_words = {'the', 'and', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with'}
    return [w for w in words if w not in stop_words and len(w) > 1]


def token_set_ratio(s1: str, s2: str) -> float:
    """
    Calculate token set ratio (handles word order differences).
    Similar to fuzzywuzzy's token_set_ratio.
    """
    tokens1 = set(tokenize(s1))
    tokens2 = set(tokenize(s2))
    
    if not tokens1 or not tokens2:
        return 0.0
    
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)


def token_sort_ratio(s1: str, s2: str) -> float:
    """
    Calculate token sort ratio (handles word order differences).
    Similar to fuzzywuzzy's token_sort_ratio.
    """
    tokens1 = sorted(tokenize(s1))
    tokens2 = sorted(tokenize(s2))
    
    sorted1 = ' '.join(tokens1)
    sorted2 = ' '.join(tokens2)
    
    return jaro_winkler_similarity(sorted1, sorted2)


# ============================================================================
# OPENAI SEMANTIC MATCHING
# ============================================================================

class OpenAISemanticMatcher:
    """Use OpenAI embeddings for semantic similarity matching."""
    
    def __init__(self):
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client if API key is available."""
        if settings.OPENAI_API_KEY:
            try:
                import openai
                self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI client initialized for semantic matching")
            except ImportError:
                logger.warning("openai package not installed, semantic matching disabled")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
    
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding vector for text."""
        if not self.client:
            return None
        
        try:
            response = await self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return None
    
    async def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2:
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    async def semantic_similarity(self, s1: str, s2: str) -> float:
        """Calculate semantic similarity between two strings."""
        try:
            emb1, emb2 = await asyncio.gather(
                self.get_embedding(s1),
                self.get_embedding(s2)
            )
            
            if emb1 and emb2:
                return await self.cosine_similarity(emb1, emb2)
        except Exception as e:
            logger.error(f"Error calculating semantic similarity: {e}")
        
        return 0.0


# ============================================================================
# MAIN FUZZY MATCHER
# ============================================================================

class AdvancedFuzzyMatcher:
    """
    Advanced fuzzy matcher combining multiple strategies.
    Target: 95%+ accuracy on misspelled/variant artist names.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.semantic_matcher = OpenAISemanticMatcher()
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        min_score: int = 50,
        use_semantic: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for artists using advanced fuzzy matching.
        
        Args:
            query: Search query
            limit: Maximum number of results
            min_score: Minimum match score (0-100)
            use_semantic: Whether to use OpenAI semantic matching
            
        Returns:
            List of artist dictionaries with match scores
        """
        if not query or not query.strip():
            return []
        
        query = query.strip()
        
        # Get all artists
        result = await self.db.execute(
            select(ArtistModel)
            .options(
                selectinload(ArtistModel.festivals),
                selectinload(ArtistModel.setlists)
            )
        )
        all_artists = result.scalars().all()
        
        # Get semantic embedding for query if enabled
        query_embedding = None
        if use_semantic and self.semantic_matcher.client:
            query_embedding = await self.semantic_matcher.get_embedding(query)
        
        # Score each artist
        scored_artists = []
        for artist in all_artists:
            score, match_type, details = await self._calculate_comprehensive_score(
                query, artist.name, query_embedding
            )
            
            if score >= min_score:
                scored_artists.append({
                    'artist': artist,
                    'score': score,
                    'match_type': match_type,
                    'details': details
                })
        
        # Sort by score and limit
        scored_artists.sort(key=lambda x: x['score'], reverse=True)
        scored_artists = scored_artists[:limit]
        
        # Format results
        formatted_results = []
        for item in scored_artists:
            artist = item['artist']
            formatted_results.append({
                'id': str(artist.id),
                'name': artist.name,
                'festival_count': len(artist.festivals) if artist.festivals else 0,
                'setlist_count': len(artist.setlists) if artist.setlists else 0,
                'has_spotify': bool(artist.spotify_id),
                'genres': artist.genres if artist.genres else [],
                'match_score': item['score'],
                'match_type': item['match_type'],
                'match_details': item['details']
            })
        
        return formatted_results
    
    async def _calculate_comprehensive_score(
        self,
        query: str,
        artist_name: str,
        query_embedding: Optional[List[float]] = None
    ) -> Tuple[int, str, Dict[str, float]]:
        """
        Calculate comprehensive match score using all strategies.
        Returns (score, match_type, details_dict).
        
        Optimized for production use - prioritizes simple typos and prefix matches.
        """
        query_lower = query.lower()
        name_lower = artist_name.lower()
        
        scores = {}
        
        # 1. Exact match (100 points)
        if query_lower == name_lower:
            return (100, 'exact', {'exact': 100})
        
        # 2. Normalized exact match (98 points)
        query_norm = normalize_for_matching(query)
        name_norm = normalize_for_matching(artist_name)
        if query_norm == name_norm:
            return (98, 'normalized_exact', {'normalized': 98})
        
        # 3. Prefix match (85-95 points) - NEW: Spotify-style prefix matching
        if name_lower.startswith(query_lower):
            # Strong match if query is significant portion of name
            ratio = len(query) / len(artist_name)
            scores['prefix'] = 85 + (ratio * 10)
        elif query_lower.startswith(name_lower):
            # Query contains full artist name
            ratio = len(artist_name) / len(query)
            scores['prefix_reverse'] = 80 + (ratio * 10)
        
        # 4. Contains match (65-85 points) - Adjusted down slightly
        if query_lower in name_lower or name_lower in query_lower:
            ratio = min(len(query), len(artist_name)) / max(len(query), len(artist_name))
            scores['contains'] = 65 + (ratio * 20)
        
        # 5. Levenshtein similarity (0-90 points) - BOOSTED for simple typos
        lev_dist = levenshtein_distance(query_lower, name_lower)
        max_len = max(len(query), len(artist_name))
        if max_len > 0:
            lev_ratio = 1 - (lev_dist / max_len)
            # Boost score for single character differences
            if lev_dist == 1:
                scores['levenshtein'] = 95  # Single typo = very high score
            elif lev_dist == 2:
                scores['levenshtein'] = 85  # Two typos = high score
            else:
                scores['levenshtein'] = lev_ratio * 90
        
        # 6. Jaro-Winkler similarity (0-90 points)
        jw_sim = jaro_winkler_similarity(query_lower, name_lower)
        scores['jaro_winkler'] = jw_sim * 90
        
        # 7. Character n-gram similarity (0-85 points) - NEW: Better for typos
        ngram_sim = self._ngram_similarity(query_lower, name_lower, n=2)
        scores['ngram'] = ngram_sim * 85
        
        # 8. Phonetic matching (0-80 points)
        query_phonetic = double_metaphone(query)
        name_phonetic = double_metaphone(artist_name)
        
        if query_phonetic[0] and name_phonetic[0]:
            if query_phonetic[0] == name_phonetic[0]:
                scores['phonetic_primary'] = 80
            elif query_phonetic[1] and name_phonetic[1] and query_phonetic[1] == name_phonetic[1]:
                scores['phonetic_secondary'] = 75
            elif query_phonetic[0] == name_phonetic[1] or query_phonetic[1] == name_phonetic[0]:
                scores['phonetic_cross'] = 70
        
        # 9. Token set ratio (0-85 points)
        token_set = token_set_ratio(query, artist_name)
        scores['token_set'] = token_set * 85
        
        # 10. Token sort ratio (0-85 points)
        token_sort = token_sort_ratio(query, artist_name)
        scores['token_sort'] = token_sort * 85
        
        # 11. Semantic similarity via OpenAI (0-95 points)
        if query_embedding and self.semantic_matcher.client:
            try:
                artist_embedding = await self.semantic_matcher.get_embedding(artist_name)
                if artist_embedding:
                    semantic_sim = await self.semantic_matcher.cosine_similarity(
                        query_embedding, artist_embedding
                    )
                    scores['semantic'] = semantic_sim * 95
            except Exception as e:
                logger.debug(f"Semantic matching failed: {e}")
        
        # Calculate weighted final score
        if not scores:
            return (0, 'none', {})
        
        # Weight the scores - UPDATED: Prioritize simple typos and prefix matches
        weights = {
            'prefix': 1.5,              # NEW: Strong boost for prefix matches
            'prefix_reverse': 1.4,      # NEW: Boost for reverse prefix
            'levenshtein': 1.5,         # BOOSTED: Prioritize edit distance (typos)
            'ngram': 1.4,               # NEW: Character-level similarity
            'jaro_winkler': 1.3,
            'contains': 1.2,
            'phonetic_primary': 1.4,
            'phonetic_secondary': 1.2,
            'phonetic_cross': 1.0,
            'token_set': 1.3,
            'token_sort': 1.2,
            'semantic': 1.5
        }
        
        weighted_scores = {k: v * weights.get(k, 1.0) for k, v in scores.items()}
        
        # Take the best score
        best_match = max(weighted_scores.items(), key=lambda x: x[1])
        final_score = min(100, int(best_match[1]))
        
        return (final_score, best_match[0], scores)
    
    def _ngram_similarity(self, s1: str, s2: str, n: int = 2) -> float:
        """
        Calculate character n-gram similarity.
        Better for catching single character typos.
        """
        if not s1 or not s2:
            return 0.0
        
        # Generate n-grams
        def get_ngrams(s, n):
            s = ' ' + s + ' '  # Add padding
            return set(s[i:i+n] for i in range(len(s) - n + 1))
        
        ngrams1 = get_ngrams(s1, n)
        ngrams2 = get_ngrams(s2, n)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = ngrams1 & ngrams2
        union = ngrams1 | ngrams2
        
        return len(intersection) / len(union) if union else 0.0


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

async def advanced_fuzzy_search(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    min_score: int = 50,
    use_semantic: bool = True
) -> List[Dict[str, Any]]:
    """
    Convenience function for advanced fuzzy search.
    
    Args:
        db: Database session
        query: Search query
        limit: Maximum number of results
        min_score: Minimum match score (0-100)
        use_semantic: Whether to use OpenAI semantic matching
        
    Returns:
        List of artist dictionaries with match scores
    """
    matcher = AdvancedFuzzyMatcher(db)
    return await matcher.search(query, limit=limit, min_score=min_score, use_semantic=use_semantic)
