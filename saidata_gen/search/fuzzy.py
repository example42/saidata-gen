"""
Fuzzy matching algorithms for software search.

This module provides fuzzy matching capabilities for partial name searches
and suggestion algorithms.
"""

import re
from typing import List, Tuple, Set
from difflib import SequenceMatcher


class FuzzyMatcher:
    """
    Fuzzy matching algorithms for software search.
    
    Provides various fuzzy matching algorithms to find similar package names
    and generate suggestions for partial searches.
    """
    
    def __init__(self, min_similarity: float = 0.3):
        """
        Initialize the fuzzy matcher.
        
        Args:
            min_similarity: Minimum similarity score to consider a match (0.0 to 1.0)
        """
        self.min_similarity = min_similarity
    
    def calculate_similarity(self, query: str, target: str) -> float:
        """
        Calculate similarity between query and target strings.
        
        Uses a combination of different similarity metrics:
        - Sequence matching (difflib)
        - Substring matching
        - Word matching
        - Prefix matching
        
        Args:
            query: Search query string
            target: Target string to compare against
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not query or not target:
            return 0.0
        
        query_lower = query.lower().strip()
        target_lower = target.lower().strip()
        
        # Exact match gets highest score
        if query_lower == target_lower:
            return 1.0
        
        # Calculate different similarity metrics
        scores = []
        
        # 1. Sequence similarity using difflib
        seq_similarity = SequenceMatcher(None, query_lower, target_lower).ratio()
        scores.append(seq_similarity * 0.4)  # 40% weight
        
        # 2. Substring matching
        if query_lower in target_lower:
            substring_score = len(query_lower) / len(target_lower)
            scores.append(substring_score * 0.3)  # 30% weight
        
        # 3. Word matching (for multi-word queries/targets)
        query_words = set(query_lower.split())
        target_words = set(target_lower.split())
        
        if query_words and target_words:
            word_intersection = len(query_words.intersection(target_words))
            word_union = len(query_words.union(target_words))
            word_similarity = word_intersection / word_union if word_union > 0 else 0
            scores.append(word_similarity * 0.2)  # 20% weight
        
        # 4. Prefix matching
        common_prefix_len = 0
        for i, (q_char, t_char) in enumerate(zip(query_lower, target_lower)):
            if q_char == t_char:
                common_prefix_len = i + 1
            else:
                break
        
        if common_prefix_len > 0:
            prefix_score = common_prefix_len / max(len(query_lower), len(target_lower))
            scores.append(prefix_score * 0.1)  # 10% weight
        
        return sum(scores)
    
    def find_matches(self, query: str, candidates: List[str]) -> List[Tuple[str, float]]:
        """
        Find fuzzy matches for a query in a list of candidates.
        
        Args:
            query: Search query
            candidates: List of candidate strings to search in
            
        Returns:
            List of tuples (candidate, similarity_score) sorted by score descending
        """
        matches = []
        
        for candidate in candidates:
            similarity = self.calculate_similarity(query, candidate)
            if similarity >= self.min_similarity:
                matches.append((candidate, similarity))
        
        # Sort by similarity score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
    
    def generate_suggestions(self, query: str, candidates: List[str], max_suggestions: int = 5) -> List[str]:
        """
        Generate suggestions for a query based on fuzzy matching.
        
        Args:
            query: Search query
            candidates: List of candidate strings to generate suggestions from
            max_suggestions: Maximum number of suggestions to return
            
        Returns:
            List of suggested strings
        """
        matches = self.find_matches(query, candidates)
        return [match[0] for match in matches[:max_suggestions]]
    
    def is_partial_match(self, query: str, target: str) -> bool:
        """
        Check if query is a partial match of target.
        
        Args:
            query: Search query
            target: Target string
            
        Returns:
            True if query partially matches target
        """
        query_lower = query.lower().strip()
        target_lower = target.lower().strip()
        
        # Check for substring match
        if query_lower in target_lower:
            return True
        
        # Check for word-based partial match
        query_words = query_lower.split()
        target_words = target_lower.split()
        
        # If any query word is a prefix of any target word
        for q_word in query_words:
            for t_word in target_words:
                if t_word.startswith(q_word) and len(q_word) >= 2:
                    return True
        
        return False
    
    def extract_keywords(self, text: str) -> Set[str]:
        """
        Extract keywords from text for better matching.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            Set of keywords
        """
        if not text:
            return set()
        
        # Convert to lowercase and split on common separators
        text_lower = text.lower()
        
        # Split on various separators
        words = re.split(r'[-_\s\.]+', text_lower)
        
        # Filter out short words and common stop words
        stop_words = {'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'the'}
        keywords = {word.strip() for word in words if len(word.strip()) >= 2 and word.strip() not in stop_words}
        
        return keywords
    
    def keyword_similarity(self, query: str, target: str) -> float:
        """
        Calculate similarity based on keyword matching.
        
        Args:
            query: Search query
            target: Target string
            
        Returns:
            Keyword-based similarity score between 0.0 and 1.0
        """
        query_keywords = self.extract_keywords(query)
        target_keywords = self.extract_keywords(target)
        
        if not query_keywords or not target_keywords:
            return 0.0
        
        intersection = len(query_keywords.intersection(target_keywords))
        union = len(query_keywords.union(target_keywords))
        
        return intersection / union if union > 0 else 0.0