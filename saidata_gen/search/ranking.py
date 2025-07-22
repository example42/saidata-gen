"""
Search result ranking and deduplication algorithms.

This module provides algorithms for ranking search results and removing duplicates
based on various criteria.
"""

import logging
from typing import Dict, List, Set, Tuple
from collections import defaultdict

from saidata_gen.core.interfaces import SoftwareMatch


logger = logging.getLogger(__name__)


class SearchRanker:
    """
    Search result ranking and deduplication system.
    
    Provides algorithms for ranking search results based on relevance,
    popularity, and other factors, as well as deduplication logic.
    """
    
    def __init__(self):
        """Initialize the search ranker."""
        # Provider popularity weights (higher = more popular/trusted)
        self.provider_weights = {
            'apt': 0.9,
            'dnf': 0.9,
            'yum': 0.85,
            'zypper': 0.8,
            'brew': 0.85,
            'winget': 0.8,
            'scoop': 0.75,
            'choco': 0.7,
            'npm': 0.8,
            'pypi': 0.8,
            'cargo': 0.75,
            'docker': 0.85,
            'snap': 0.7,
            'flatpak': 0.7,
            'pacman': 0.8,
            'apk': 0.75,
            'portage': 0.7,
            'nix': 0.7,
            'guix': 0.65,
        }
    
    def calculate_relevance_score(self, match: SoftwareMatch, query: str) -> float:
        """
        Calculate relevance score for a search match.
        
        Args:
            match: Software match to score
            query: Original search query
            
        Returns:
            Relevance score between 0.0 and 1.0
        """
        score = 0.0
        query_lower = query.lower().strip()
        name_lower = match.name.lower().strip()
        
        # Base similarity score (from fuzzy matching)
        score += match.score * 0.4
        
        # Exact name match bonus
        if query_lower == name_lower:
            score += 0.3
        
        # Prefix match bonus
        if name_lower.startswith(query_lower):
            score += 0.2
        
        # Provider popularity weight
        provider_weight = self.provider_weights.get(match.provider.lower(), 0.5)
        score += provider_weight * 0.1
        
        # Description relevance (if available)
        if match.description:
            desc_lower = match.description.lower()
            if query_lower in desc_lower:
                score += 0.1
        
        # Ensure score doesn't exceed 1.0
        return min(score, 1.0)
    
    def rank_results(self, matches: List[SoftwareMatch], query: str) -> List[SoftwareMatch]:
        """
        Rank search results by relevance.
        
        Args:
            matches: List of software matches to rank
            query: Original search query
            
        Returns:
            Ranked list of software matches
        """
        # Calculate relevance scores
        scored_matches = []
        for match in matches:
            relevance_score = self.calculate_relevance_score(match, query)
            # Update the match score with the calculated relevance
            match.score = relevance_score
            scored_matches.append(match)
        
        # Sort by score descending, then by name for stable sorting
        scored_matches.sort(key=lambda x: (-x.score, x.name.lower()))
        
        return scored_matches
    
    def deduplicate_results(self, matches: List[SoftwareMatch]) -> List[SoftwareMatch]:
        """
        Remove duplicate results from search matches.
        
        Deduplication is based on package name similarity and keeps the
        highest-scored match for each unique package.
        
        Args:
            matches: List of software matches to deduplicate
            
        Returns:
            Deduplicated list of software matches
        """
        if not matches:
            return []
        
        # Group matches by normalized name
        name_groups = defaultdict(list)
        
        for match in matches:
            # Normalize the name for grouping
            normalized_name = self._normalize_package_name(match.name)
            name_groups[normalized_name].append(match)
        
        deduplicated = []
        
        for normalized_name, group_matches in name_groups.items():
            if len(group_matches) == 1:
                # Single match, keep it
                deduplicated.append(group_matches[0])
            else:
                # Multiple matches, apply deduplication logic
                best_match = self._select_best_match(group_matches)
                deduplicated.append(best_match)
        
        return deduplicated
    
    def _normalize_package_name(self, name: str) -> str:
        """
        Normalize package name for deduplication.
        
        Args:
            name: Package name to normalize
            
        Returns:
            Normalized package name
        """
        # Convert to lowercase and remove common prefixes/suffixes
        normalized = name.lower().strip()
        
        # Remove common prefixes
        prefixes_to_remove = ['lib', 'python-', 'python3-', 'node-', 'ruby-']
        for prefix in prefixes_to_remove:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        
        # Remove common suffixes
        suffixes_to_remove = ['-dev', '-devel', '-doc', '-docs', '-common', '-utils', '-tools']
        for suffix in suffixes_to_remove:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
                break
        
        # Replace separators with hyphens for consistency
        import re
        normalized = re.sub(r'[-_\.]+', '-', normalized)
        
        return normalized.strip('-')
    
    def _select_best_match(self, matches: List[SoftwareMatch]) -> SoftwareMatch:
        """
        Select the best match from a group of similar matches.
        
        Args:
            matches: List of similar matches
            
        Returns:
            Best match from the group
        """
        if len(matches) == 1:
            return matches[0]
        
        # Sort by multiple criteria
        def sort_key(match):
            return (
                -match.score,  # Higher score first
                -self.provider_weights.get(match.provider.lower(), 0.5),  # More trusted provider first
                len(match.name),  # Shorter name first (usually more canonical)
                match.name.lower()  # Alphabetical for stable sorting
            )
        
        sorted_matches = sorted(matches, key=sort_key)
        return sorted_matches[0]
    
    def filter_by_confidence(self, matches: List[SoftwareMatch], min_confidence: float = 0.3) -> List[SoftwareMatch]:
        """
        Filter matches by minimum confidence score.
        
        Args:
            matches: List of software matches to filter
            min_confidence: Minimum confidence score (0.0 to 1.0)
            
        Returns:
            Filtered list of software matches
        """
        return [match for match in matches if match.score >= min_confidence]
    
    def group_by_provider(self, matches: List[SoftwareMatch]) -> Dict[str, List[SoftwareMatch]]:
        """
        Group matches by provider.
        
        Args:
            matches: List of software matches to group
            
        Returns:
            Dictionary mapping provider names to lists of matches
        """
        groups = defaultdict(list)
        for match in matches:
            groups[match.provider].append(match)
        
        return dict(groups)
    
    def get_top_matches(self, matches: List[SoftwareMatch], limit: int = 10) -> List[SoftwareMatch]:
        """
        Get top N matches from a list.
        
        Args:
            matches: List of software matches
            limit: Maximum number of matches to return
            
        Returns:
            Top N matches
        """
        return matches[:limit]
    
    def calculate_diversity_score(self, matches: List[SoftwareMatch]) -> float:
        """
        Calculate diversity score for a set of matches.
        
        Higher diversity means matches come from different providers
        and have different characteristics.
        
        Args:
            matches: List of software matches
            
        Returns:
            Diversity score between 0.0 and 1.0
        """
        if not matches:
            return 0.0
        
        # Count unique providers
        providers = set(match.provider for match in matches)
        provider_diversity = len(providers) / len(matches)
        
        # Count unique normalized names
        names = set(self._normalize_package_name(match.name) for match in matches)
        name_diversity = len(names) / len(matches)
        
        # Average the diversity metrics
        return (provider_diversity + name_diversity) / 2


# Alias for backward compatibility
ResultRanker = SearchRanker