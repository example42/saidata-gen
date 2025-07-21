"""
Software search engine for querying multiple repositories simultaneously.

This module provides the main search engine that coordinates searches across
multiple package repositories and provides unified results.
"""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetcherConfig, PackageDetails, PackageInfo, SoftwareMatch
)
from saidata_gen.fetcher.factory import fetcher_factory
from saidata_gen.fetcher.base import RepositoryFetcher
from saidata_gen.search.fuzzy import FuzzyMatcher
from saidata_gen.search.ranking import SearchRanker
from saidata_gen.search.comparison import PackageComparator, PackageComparison, PackageGroup, SelectionCriteria


logger = logging.getLogger(__name__)


class SoftwareSearchEngine:
    """
    Software search engine that queries multiple repositories simultaneously.
    
    Provides unified search capabilities across different package managers
    with fuzzy matching, ranking, and deduplication.
    """
    
    def __init__(
        self,
        config: Optional[FetcherConfig] = None,
        providers: Optional[List[str]] = None,
        max_workers: int = 5
    ):
        """
        Initialize the software search engine.
        
        Args:
            config: Configuration for fetchers
            providers: List of provider names to search. If None, uses all available providers.
            max_workers: Maximum number of concurrent workers for parallel searches
        """
        self.config = config or FetcherConfig()
        self.max_workers = max_workers
        
        # Initialize search components
        self.fuzzy_matcher = FuzzyMatcher(min_similarity=0.3)
        self.ranker = SearchRanker()
        
        # Initialize fetchers
        self.fetchers: Dict[str, RepositoryFetcher] = {}
        self._initialize_fetchers(providers)
        
        # Initialize comparator after fetchers are ready
        self.comparator = PackageComparator(self.fetchers)
        
        # Cache for package lists (to avoid repeated fetching)
        self._package_cache: Dict[str, List[str]] = {}
        self._cache_lock = threading.Lock()
    
    def _initialize_fetchers(self, providers: Optional[List[str]] = None) -> None:
        """
        Initialize repository fetchers.
        
        Args:
            providers: List of provider names to initialize. If None, uses all available.
        """
        available_providers = fetcher_factory.get_available_fetchers()
        
        if providers is None:
            providers_to_init = available_providers
        else:
            # Filter to only available providers
            providers_to_init = [p for p in providers if p in available_providers]
            
            # Log warnings for unavailable providers
            unavailable = set(providers) - set(available_providers)
            if unavailable:
                logger.warning(f"Unavailable providers requested: {unavailable}")
        
        # Initialize fetchers
        for provider in providers_to_init:
            try:
                fetcher = fetcher_factory.create_fetcher(provider, self.config)
                if fetcher:
                    self.fetchers[provider] = fetcher
                    logger.debug(f"Initialized fetcher for provider: {provider}")
                else:
                    logger.warning(f"Failed to create fetcher for provider: {provider}")
            except Exception as e:
                logger.error(f"Error initializing fetcher for {provider}: {e}")
    
    def search(
        self,
        query: str,
        max_results: int = 20,
        providers: Optional[List[str]] = None,
        include_fuzzy: bool = True,
        min_confidence: float = 0.3
    ) -> List[SoftwareMatch]:
        """
        Search for software packages across multiple repositories.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            providers: List of specific providers to search. If None, searches all configured providers.
            include_fuzzy: Whether to include fuzzy matching results
            min_confidence: Minimum confidence score for results
            
        Returns:
            List of ranked and deduplicated software matches
        """
        if not query or not query.strip():
            return []
        
        query = query.strip()
        logger.info(f"Searching for '{query}' across {len(self.fetchers)} providers")
        
        # Determine which providers to search
        search_providers = self._get_search_providers(providers)
        
        if not search_providers:
            logger.warning("No providers available for search")
            return []
        
        # Perform parallel searches
        all_matches = self._parallel_search(query, search_providers, include_fuzzy)
        
        # Filter by confidence
        filtered_matches = self.ranker.filter_by_confidence(all_matches, min_confidence)
        
        # Deduplicate results
        deduplicated_matches = self.ranker.deduplicate_results(filtered_matches)
        
        # Rank results
        ranked_matches = self.ranker.rank_results(deduplicated_matches, query)
        
        # Limit results
        final_matches = self.ranker.get_top_matches(ranked_matches, max_results)
        
        logger.info(f"Found {len(final_matches)} matches for '{query}'")
        return final_matches
    
    def _get_search_providers(self, providers: Optional[List[str]]) -> List[str]:
        """
        Get the list of providers to search.
        
        Args:
            providers: Requested providers, or None for all
            
        Returns:
            List of provider names to search
        """
        if providers is None:
            return list(self.fetchers.keys())
        
        # Filter to only available providers
        available = [p for p in providers if p in self.fetchers]
        
        # Log warnings for unavailable providers
        unavailable = set(providers) - set(available)
        if unavailable:
            logger.warning(f"Requested providers not available: {unavailable}")
        
        return available
    
    def _parallel_search(
        self,
        query: str,
        providers: List[str],
        include_fuzzy: bool
    ) -> List[SoftwareMatch]:
        """
        Perform parallel searches across multiple providers.
        
        Args:
            query: Search query
            providers: List of provider names to search
            include_fuzzy: Whether to include fuzzy matching
            
        Returns:
            Combined list of matches from all providers
        """
        all_matches = []
        
        # Use ThreadPoolExecutor for parallel searches
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(providers))) as executor:
            # Submit search tasks
            future_to_provider = {
                executor.submit(self._search_provider, query, provider, include_fuzzy): provider
                for provider in providers
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    matches = future.result(timeout=30)  # 30 second timeout per provider
                    all_matches.extend(matches)
                    logger.debug(f"Provider {provider} returned {len(matches)} matches")
                except Exception as e:
                    logger.error(f"Search failed for provider {provider}: {e}")
        
        return all_matches
    
    def _search_provider(
        self,
        query: str,
        provider: str,
        include_fuzzy: bool
    ) -> List[SoftwareMatch]:
        """
        Search a single provider for packages.
        
        Args:
            query: Search query
            provider: Provider name
            include_fuzzy: Whether to include fuzzy matching
            
        Returns:
            List of matches from the provider
        """
        fetcher = self.fetchers.get(provider)
        if not fetcher:
            return []
        
        try:
            # First try direct search from the fetcher
            package_infos = fetcher.search_packages(query, max_results=50)
            
            # Convert PackageInfo to SoftwareMatch
            matches = []
            for pkg_info in package_infos:
                match = SoftwareMatch(
                    name=pkg_info.name,
                    provider=pkg_info.provider,
                    version=pkg_info.version,
                    description=pkg_info.description,
                    score=1.0,  # Will be recalculated by ranker
                    details=pkg_info.details
                )
                matches.append(match)
            
            # If fuzzy matching is enabled and we have few results, try fuzzy search
            if include_fuzzy and len(matches) < 10:
                fuzzy_matches = self._fuzzy_search_provider(query, provider)
                matches.extend(fuzzy_matches)
            
            return matches
            
        except Exception as e:
            logger.error(f"Error searching provider {provider}: {e}")
            return []
    
    def _fuzzy_search_provider(self, query: str, provider: str) -> List[SoftwareMatch]:
        """
        Perform fuzzy search on a provider's package list.
        
        Args:
            query: Search query
            provider: Provider name
            
        Returns:
            List of fuzzy matches
        """
        try:
            # Get cached package list or fetch it
            package_names = self._get_package_list(provider)
            
            if not package_names:
                return []
            
            # Find fuzzy matches
            fuzzy_matches = self.fuzzy_matcher.find_matches(query, package_names)
            
            # Convert to SoftwareMatch objects
            matches = []
            for name, score in fuzzy_matches[:20]:  # Limit fuzzy results
                # Try to get detailed info for the package
                try:
                    pkg_info = self.fetchers[provider].get_package_info(name)
                    if pkg_info:
                        match = SoftwareMatch(
                            name=pkg_info.name,
                            provider=pkg_info.provider,
                            version=pkg_info.version,
                            description=pkg_info.description,
                            score=score,
                            details=pkg_info.details
                        )
                    else:
                        # Create basic match if detailed info not available
                        match = SoftwareMatch(
                            name=name,
                            provider=provider,
                            score=score
                        )
                    matches.append(match)
                except Exception as e:
                    logger.debug(f"Could not get details for {name} from {provider}: {e}")
                    # Create basic match
                    match = SoftwareMatch(
                        name=name,
                        provider=provider,
                        score=score
                    )
                    matches.append(match)
            
            return matches
            
        except Exception as e:
            logger.error(f"Error in fuzzy search for provider {provider}: {e}")
            return []
    
    def _get_package_list(self, provider: str) -> List[str]:
        """
        Get the list of package names for a provider (with caching).
        
        Args:
            provider: Provider name
            
        Returns:
            List of package names
        """
        with self._cache_lock:
            if provider in self._package_cache:
                return self._package_cache[provider]
        
        try:
            # Try to get package list from fetcher
            fetcher = self.fetchers.get(provider)
            if not fetcher:
                return []
            
            # This is a simplified approach - in practice, fetchers might need
            # to implement a get_all_package_names method or similar
            # For now, we'll return an empty list and rely on direct search
            package_names = []
            
            # Cache the result
            with self._cache_lock:
                self._package_cache[provider] = package_names
            
            return package_names
            
        except Exception as e:
            logger.error(f"Error getting package list for provider {provider}: {e}")
            return []
    
    def suggest(self, query: str, max_suggestions: int = 5) -> List[str]:
        """
        Generate search suggestions based on a partial query.
        
        Args:
            query: Partial search query
            max_suggestions: Maximum number of suggestions to return
            
        Returns:
            List of suggested search terms
        """
        if not query or len(query.strip()) < 2:
            return []
        
        query = query.strip()
        all_suggestions = set()
        
        # Get suggestions from each provider
        for provider in self.fetchers.keys():
            try:
                package_names = self._get_package_list(provider)
                if package_names:
                    suggestions = self.fuzzy_matcher.generate_suggestions(
                        query, package_names, max_suggestions * 2
                    )
                    all_suggestions.update(suggestions)
            except Exception as e:
                logger.debug(f"Error getting suggestions from provider {provider}: {e}")
        
        # Convert to list and limit
        suggestion_list = list(all_suggestions)
        
        # Sort by similarity to query
        scored_suggestions = [
            (suggestion, self.fuzzy_matcher.calculate_similarity(query, suggestion))
            for suggestion in suggestion_list
        ]
        scored_suggestions.sort(key=lambda x: x[1], reverse=True)
        
        return [suggestion for suggestion, _ in scored_suggestions[:max_suggestions]]
    
    def get_package_details(self, package_name: str, provider: str) -> Optional[SoftwareMatch]:
        """
        Get detailed information about a specific package.
        
        Args:
            package_name: Name of the package
            provider: Provider name
            
        Returns:
            Detailed software match or None if not found
        """
        fetcher = self.fetchers.get(provider)
        if not fetcher:
            return None
        
        try:
            pkg_info = fetcher.get_package_info(package_name)
            if pkg_info:
                return SoftwareMatch(
                    name=pkg_info.name,
                    provider=pkg_info.provider,
                    version=pkg_info.version,
                    description=pkg_info.description,
                    score=1.0,
                    details=pkg_info.details
                )
        except Exception as e:
            logger.error(f"Error getting package details for {package_name} from {provider}: {e}")
        
        return None
    
    def get_available_providers(self) -> List[str]:
        """
        Get list of available providers.
        
        Returns:
            List of provider names
        """
        return list(self.fetchers.keys())
    
    def clear_cache(self) -> None:
        """Clear the package name cache."""
        with self._cache_lock:
            self._package_cache.clear()
        logger.info("Package cache cleared")
    
    def compare_packages(
        self,
        packages: List[SoftwareMatch],
        criteria: Optional[SelectionCriteria] = None
    ) -> List[PackageComparison]:
        """
        Compare packages to identify alternatives and duplicates.
        
        Args:
            packages: List of software matches to compare
            criteria: Selection criteria for comparison
            
        Returns:
            List of package comparisons
        """
        return self.comparator.compare_packages(packages, criteria)
    
    def identify_duplicates(
        self,
        packages: List[SoftwareMatch],
        similarity_threshold: float = 0.9
    ) -> List[PackageGroup]:
        """
        Identify duplicate packages across providers.
        
        Args:
            packages: List of software matches
            similarity_threshold: Minimum similarity to consider duplicates
            
        Returns:
            List of package groups containing duplicates
        """
        return self.comparator.identify_duplicates(packages, similarity_threshold)
    
    def find_alternatives(
        self,
        target_package: SoftwareMatch,
        candidate_packages: List[SoftwareMatch],
        similarity_threshold: float = 0.5
    ) -> List[SoftwareMatch]:
        """
        Find alternative packages for a target package.
        
        Args:
            target_package: Package to find alternatives for
            candidate_packages: List of candidate packages
            similarity_threshold: Minimum similarity to consider alternatives
            
        Returns:
            List of alternative packages sorted by relevance
        """
        return self.comparator.find_alternatives(target_package, candidate_packages, similarity_threshold)
    
    def select_best_package(
        self,
        packages: List[SoftwareMatch],
        criteria: Optional[SelectionCriteria] = None
    ) -> Optional[SoftwareMatch]:
        """
        Select the best package from a list based on criteria.
        
        Args:
            packages: List of packages to choose from
            criteria: Selection criteria
            
        Returns:
            Best package or None if no suitable package found
        """
        return self.comparator.select_best_package(packages, criteria)
    
    def get_detailed_package_info(
        self,
        package: SoftwareMatch
    ) -> Optional[PackageDetails]:
        """
        Get detailed information about a package from its provider.
        
        Args:
            package: Software match to get details for
            
        Returns:
            Detailed package information or None if not available
        """
        return self.comparator.get_detailed_package_info(package)