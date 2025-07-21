"""
Software search and discovery functionality.

This module provides software search capabilities across multiple package repositories,
including fuzzy matching, result ranking, and deduplication.
"""

from .engine import SoftwareSearchEngine
from .ranking import SearchRanker
from .fuzzy import FuzzyMatcher
from .comparison import PackageComparator, PackageComparison, PackageGroup, SelectionCriteria

__all__ = [
    'SoftwareSearchEngine',
    'SearchRanker', 
    'FuzzyMatcher',
    'PackageComparator',
    'PackageComparison',
    'PackageGroup',
    'SelectionCriteria'
]