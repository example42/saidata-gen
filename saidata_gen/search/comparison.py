"""
Package comparison and selection system for identifying alternatives and duplicates.

This module provides functionality to compare packages across different providers,
identify alternatives and duplicates, and help users select the best package option.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import PackageDetails, SoftwareMatch
from saidata_gen.fetcher.base import RepositoryFetcher
from saidata_gen.search.fuzzy import FuzzyMatcher


logger = logging.getLogger(__name__)


@dataclass
class PackageComparison:
    """
    Comparison result between packages.
    """
    primary_package: SoftwareMatch
    alternative_packages: List[SoftwareMatch] = field(default_factory=list)
    similarity_scores: Dict[str, float] = field(default_factory=dict)
    common_features: List[str] = field(default_factory=list)
    differences: Dict[str, Dict[str, any]] = field(default_factory=dict)
    recommendation_score: float = 0.0
    recommendation_reason: str = ""


@dataclass
class PackageGroup:
    """
    Group of related packages (alternatives/duplicates).
    """
    canonical_name: str
    packages: List[SoftwareMatch] = field(default_factory=list)
    group_type: str = "alternative"  # "alternative", "duplicate", "related"
    confidence: float = 0.0
    description: str = ""


@dataclass
class SelectionCriteria:
    """
    Criteria for package selection.
    """
    prefer_official: bool = True
    prefer_latest_version: bool = True
    prefer_popular_providers: List[str] = field(default_factory=lambda: ["apt", "brew", "winget", "npm", "pypi"])
    minimum_description_length: int = 20
    require_version: bool = False
    exclude_providers: List[str] = field(default_factory=list)
    include_providers: List[str] = field(default_factory=list)


class PackageComparator:
    """
    Compares packages to identify alternatives, duplicates, and provide selection recommendations.
    """
    
    def __init__(self, fetchers: Dict[str, RepositoryFetcher]):
        """
        Initialize the package comparator.
        
        Args:
            fetchers: Dictionary of provider name to fetcher instances
        """
        self.fetchers = fetchers
        self.fuzzy_matcher = FuzzyMatcher(min_similarity=0.6)
        
        # Provider popularity ranking (higher is better)
        self.provider_popularity = {
            "apt": 10,
            "brew": 9,
            "winget": 8,
            "npm": 7,
            "pypi": 7,
            "cargo": 6,
            "dnf": 8,
            "yum": 7,
            "zypper": 7,
            "pacman": 6,
            "docker": 5,
            "snap": 4,
            "flatpak": 4,
            "scoop": 3,
            "choco": 3,
        }
    
    def compare_packages(
        self,
        packages: List[SoftwareMatch],
        criteria: Optional[SelectionCriteria] = None
    ) -> List[PackageComparison]:
        """
        Compare a list of packages and identify relationships.
        
        Args:
            packages: List of software matches to compare
            criteria: Selection criteria for comparison
            
        Returns:
            List of package comparisons
        """
        if not packages:
            return []
        
        criteria = criteria or SelectionCriteria()
        
        # Group packages by similarity
        groups = self._group_similar_packages(packages)
        
        # Create comparisons for each group
        comparisons = []
        for group in groups:
            if len(group.packages) > 1:
                comparison = self._create_package_comparison(group, criteria)
                comparisons.append(comparison)
        
        return comparisons
    
    def identify_duplicates(
        self,
        packages: List[SoftwareMatch],
        similarity_threshold: float = 0.9
    ) -> List[PackageGroup]:
        """
        Identify duplicate packages (same software, different providers).
        
        Args:
            packages: List of software matches
            similarity_threshold: Minimum similarity to consider duplicates
            
        Returns:
            List of package groups containing duplicates
        """
        duplicates = []
        processed = set()
        
        for i, package in enumerate(packages):
            if i in processed:
                continue
            
            # Find similar packages
            similar_packages = [package]
            for j, other_package in enumerate(packages[i+1:], i+1):
                if j in processed:
                    continue
                
                similarity = self._calculate_package_similarity(package, other_package)
                if similarity >= similarity_threshold:
                    similar_packages.append(other_package)
                    processed.add(j)
            
            if len(similar_packages) > 1:
                group = PackageGroup(
                    canonical_name=self._get_canonical_name(similar_packages),
                    packages=similar_packages,
                    group_type="duplicate",
                    confidence=min(similarity_threshold, 1.0),
                    description=f"Duplicate packages for {similar_packages[0].name}"
                )
                duplicates.append(group)
            
            processed.add(i)
        
        return duplicates
    
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
        alternatives = []
        
        for candidate in candidate_packages:
            if candidate.provider == target_package.provider and candidate.name == target_package.name:
                continue  # Skip the same package
            
            similarity = self._calculate_package_similarity(target_package, candidate)
            if similarity >= similarity_threshold:
                candidate.score = similarity
                alternatives.append(candidate)
        
        # Sort by similarity score
        alternatives.sort(key=lambda x: x.score, reverse=True)
        
        return alternatives
    
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
        if not packages:
            return None
        
        criteria = criteria or SelectionCriteria()
        
        # Filter packages based on criteria
        filtered_packages = self._filter_packages(packages, criteria)
        
        if not filtered_packages:
            return None
        
        # Score packages
        scored_packages = []
        for package in filtered_packages:
            score = self._calculate_selection_score(package, criteria)
            scored_packages.append((package, score))
        
        # Sort by score and return the best
        scored_packages.sort(key=lambda x: x[1], reverse=True)
        
        return scored_packages[0][0]
    
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
        fetcher = self.fetchers.get(package.provider)
        if not fetcher:
            logger.warning(f"No fetcher available for provider: {package.provider}")
            return None
        
        try:
            # Try to get package info first
            package_info = fetcher.get_package_info(package.name)
            if not package_info:
                return None
            
            # Convert PackageInfo to PackageDetails
            details = PackageDetails(
                name=package_info.name,
                provider=package_info.provider,
                version=package_info.version,
                description=package_info.description,
                raw_data=package_info.details
            )
            
            # Extract additional details from raw_data if available
            raw_data = package_info.details
            if isinstance(raw_data, dict):
                details.license = raw_data.get("license")
                details.homepage = raw_data.get("homepage") or raw_data.get("website")
                details.dependencies = raw_data.get("dependencies", [])
                details.maintainer = raw_data.get("maintainer")
                details.source_url = raw_data.get("source_url")
                details.download_url = raw_data.get("download_url")
                details.checksum = raw_data.get("checksum")
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting detailed info for {package.name} from {package.provider}: {e}")
            return None
    
    def _group_similar_packages(self, packages: List[SoftwareMatch]) -> List[PackageGroup]:
        """
        Group packages by similarity.
        
        Args:
            packages: List of packages to group
            
        Returns:
            List of package groups
        """
        groups = []
        processed = set()
        
        for i, package in enumerate(packages):
            if i in processed:
                continue
            
            # Start a new group with this package
            group_packages = [package]
            
            # Find similar packages
            for j, other_package in enumerate(packages[i+1:], i+1):
                if j in processed:
                    continue
                
                similarity = self._calculate_package_similarity(package, other_package)
                if similarity >= 0.6:  # Threshold for grouping
                    group_packages.append(other_package)
                    processed.add(j)
            
            # Create group
            group = PackageGroup(
                canonical_name=self._get_canonical_name(group_packages),
                packages=group_packages,
                group_type="related" if len(group_packages) > 1 else "single",
                confidence=0.8,
                description=f"Related packages for {package.name}"
            )
            groups.append(group)
            processed.add(i)
        
        return groups
    
    def _create_package_comparison(
        self,
        group: PackageGroup,
        criteria: SelectionCriteria
    ) -> PackageComparison:
        """
        Create a detailed comparison for a package group.
        
        Args:
            group: Package group to compare
            criteria: Selection criteria
            
        Returns:
            Package comparison result
        """
        if not group.packages:
            raise ValueError("Package group is empty")
        
        # Select primary package (best according to criteria)
        primary = self.select_best_package(group.packages, criteria)
        if not primary:
            primary = group.packages[0]
        
        # Get alternatives (other packages in the group)
        alternatives = [pkg for pkg in group.packages if pkg != primary]
        
        # Calculate similarity scores
        similarity_scores = {}
        for alt in alternatives:
            similarity_scores[f"{alt.provider}:{alt.name}"] = self._calculate_package_similarity(primary, alt)
        
        # Find common features and differences
        common_features, differences = self._analyze_package_features(group.packages)
        
        # Calculate recommendation score and reason
        rec_score, rec_reason = self._calculate_recommendation(primary, alternatives, criteria)
        
        return PackageComparison(
            primary_package=primary,
            alternative_packages=alternatives,
            similarity_scores=similarity_scores,
            common_features=common_features,
            differences=differences,
            recommendation_score=rec_score,
            recommendation_reason=rec_reason
        )
    
    def _calculate_package_similarity(
        self,
        package1: SoftwareMatch,
        package2: SoftwareMatch
    ) -> float:
        """
        Calculate similarity between two packages.
        
        Args:
            package1: First package
            package2: Second package
            
        Returns:
            Similarity score between 0 and 1
        """
        # Name similarity (most important)
        name_similarity = self.fuzzy_matcher.calculate_similarity(package1.name, package2.name)
        
        # Description similarity
        desc_similarity = 0.0
        if package1.description and package2.description:
            desc_similarity = self.fuzzy_matcher.calculate_similarity(
                package1.description, package2.description
            )
        
        # Provider similarity (same provider = higher similarity)
        provider_similarity = 1.0 if package1.provider == package2.provider else 0.3
        
        # Weighted average
        similarity = (
            name_similarity * 0.6 +
            desc_similarity * 0.3 +
            provider_similarity * 0.1
        )
        
        return min(similarity, 1.0)
    
    def _get_canonical_name(self, packages: List[SoftwareMatch]) -> str:
        """
        Get the canonical name for a group of packages.
        
        Args:
            packages: List of packages
            
        Returns:
            Canonical name
        """
        if not packages:
            return "unknown"
        
        # Use the name from the most popular provider
        best_package = max(
            packages,
            key=lambda p: self.provider_popularity.get(p.provider, 0)
        )
        
        return best_package.name
    
    def _filter_packages(
        self,
        packages: List[SoftwareMatch],
        criteria: SelectionCriteria
    ) -> List[SoftwareMatch]:
        """
        Filter packages based on selection criteria.
        
        Args:
            packages: List of packages to filter
            criteria: Selection criteria
            
        Returns:
            Filtered list of packages
        """
        filtered = []
        
        for package in packages:
            # Check provider inclusion/exclusion
            if criteria.exclude_providers and package.provider in criteria.exclude_providers:
                continue
            
            if criteria.include_providers and package.provider not in criteria.include_providers:
                continue
            
            # Check version requirement
            if criteria.require_version and not package.version:
                continue
            
            # Check description length
            if (package.description and 
                len(package.description) < criteria.minimum_description_length):
                continue
            
            filtered.append(package)
        
        return filtered
    
    def _calculate_selection_score(
        self,
        package: SoftwareMatch,
        criteria: SelectionCriteria
    ) -> float:
        """
        Calculate selection score for a package.
        
        Args:
            package: Package to score
            criteria: Selection criteria
            
        Returns:
            Selection score
        """
        score = 0.0
        
        # Provider popularity
        provider_score = self.provider_popularity.get(package.provider, 1) / 10.0
        score += provider_score * 0.3
        
        # Description quality
        if package.description:
            desc_score = min(len(package.description) / 100.0, 1.0)
            score += desc_score * 0.2
        
        # Version availability
        if package.version:
            score += 0.2
        
        # Base search score
        score += package.score * 0.3
        
        return min(score, 1.0)
    
    def _analyze_package_features(
        self,
        packages: List[SoftwareMatch]
    ) -> Tuple[List[str], Dict[str, Dict[str, any]]]:
        """
        Analyze common features and differences between packages.
        
        Args:
            packages: List of packages to analyze
            
        Returns:
            Tuple of (common_features, differences)
        """
        common_features = []
        differences = {}
        
        if len(packages) < 2:
            return common_features, differences
        
        # Analyze names
        names = [pkg.name for pkg in packages]
        if len(set(names)) == 1:
            common_features.append("Same name")
        else:
            differences["names"] = {pkg.provider: pkg.name for pkg in packages}
        
        # Analyze versions
        versions = [pkg.version for pkg in packages if pkg.version]
        if len(set(versions)) == 1 and versions:
            common_features.append(f"Same version: {versions[0]}")
        elif len(versions) > 1:
            differences["versions"] = {pkg.provider: pkg.version for pkg in packages if pkg.version}
        
        # Analyze descriptions
        descriptions = [pkg.description for pkg in packages if pkg.description]
        if descriptions:
            # Check if descriptions are similar
            similarities = []
            for i in range(len(descriptions)):
                for j in range(i+1, len(descriptions)):
                    sim = self.fuzzy_matcher.calculate_similarity(descriptions[i], descriptions[j])
                    similarities.append(sim)
            
            if similarities and sum(similarities) / len(similarities) > 0.8:
                common_features.append("Similar descriptions")
            else:
                differences["descriptions"] = {
                    pkg.provider: pkg.description for pkg in packages if pkg.description
                }
        
        # Analyze providers
        providers = [pkg.provider for pkg in packages]
        differences["providers"] = sorted(list(set(providers)))
        
        return common_features, differences
    
    def _calculate_recommendation(
        self,
        primary: SoftwareMatch,
        alternatives: List[SoftwareMatch],
        criteria: SelectionCriteria
    ) -> Tuple[float, str]:
        """
        Calculate recommendation score and reason.
        
        Args:
            primary: Primary package
            alternatives: Alternative packages
            criteria: Selection criteria
            
        Returns:
            Tuple of (score, reason)
        """
        score = 0.8  # Base score for having a recommendation
        reasons = []
        
        # Provider preference
        if primary.provider in criteria.prefer_popular_providers:
            score += 0.1
            reasons.append(f"Popular provider ({primary.provider})")
        
        # Version availability
        if primary.version:
            score += 0.05
            reasons.append("Version available")
        
        # Description quality
        if primary.description and len(primary.description) >= criteria.minimum_description_length:
            score += 0.05
            reasons.append("Good description")
        
        # Comparison with alternatives
        if alternatives:
            primary_popularity = self.provider_popularity.get(primary.provider, 1)
            alt_popularities = [self.provider_popularity.get(alt.provider, 1) for alt in alternatives]
            
            if primary_popularity >= max(alt_popularities):
                reasons.append("Most popular provider among alternatives")
        
        reason = "; ".join(reasons) if reasons else "Default selection"
        
        return min(score, 1.0), reason