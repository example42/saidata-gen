"""
Multi-source data aggregation system for saidata-gen.

This module provides sophisticated data aggregation logic that combines information
from multiple repositories with confidence scoring and conflict resolution strategies.
"""

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from saidata_gen.core.interfaces import PackageInfo


logger = logging.getLogger(__name__)


class ConflictResolutionStrategy(Enum):
    """Strategies for resolving conflicts between data sources."""
    
    HIGHEST_CONFIDENCE = "highest_confidence"
    MAJORITY_VOTE = "majority_vote"
    MOST_RECENT = "most_recent"
    LONGEST_VALUE = "longest_value"
    PROVIDER_PRIORITY = "provider_priority"
    MERGE_LISTS = "merge_lists"
    MERGE_DICTS = "merge_dicts"


@dataclass
class SourceInfo:
    """Information about a data source."""
    
    provider: str
    timestamp: Optional[float] = None
    priority: int = 0  # Higher values = higher priority
    reliability_score: float = 1.0  # 0.0 to 1.0


@dataclass
class DataPoint:
    """A data point from a source with metadata."""
    
    value: Any
    source: SourceInfo
    confidence: float = 1.0  # 0.0 to 1.0
    field_path: str = ""


@dataclass
class AggregationResult:
    """Result of data aggregation for a field."""
    
    value: Any
    confidence: float
    sources: List[SourceInfo] = field(default_factory=list)
    conflicts: List[DataPoint] = field(default_factory=list)
    resolution_strategy: Optional[ConflictResolutionStrategy] = None


class DataAggregator:
    """
    Sophisticated data aggregation system that combines information from multiple sources.
    
    This class provides methods for aggregating data from multiple package repositories,
    calculating confidence scores, and resolving conflicts between sources.
    """
    
    def __init__(
        self,
        provider_priorities: Optional[Dict[str, int]] = None,
        provider_reliability: Optional[Dict[str, float]] = None,
        default_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.HIGHEST_CONFIDENCE
    ):
        """
        Initialize the data aggregator.
        
        Args:
            provider_priorities: Dictionary mapping provider names to priority scores.
            provider_reliability: Dictionary mapping provider names to reliability scores.
            default_strategy: Default conflict resolution strategy.
        """
        self.provider_priorities = provider_priorities or self._get_default_priorities()
        self.provider_reliability = provider_reliability or self._get_default_reliability()
        self.default_strategy = default_strategy
        
        # Field-specific strategies
        self.field_strategies = {
            "description": ConflictResolutionStrategy.LONGEST_VALUE,
            "license": ConflictResolutionStrategy.MAJORITY_VOTE,
            "platforms": ConflictResolutionStrategy.MERGE_LISTS,
            "urls": ConflictResolutionStrategy.MERGE_DICTS,
            "version": ConflictResolutionStrategy.MOST_RECENT,
            "name": ConflictResolutionStrategy.PROVIDER_PRIORITY,
        }
    
    def _get_default_priorities(self) -> Dict[str, int]:
        """Get default provider priorities."""
        return {
            # Official package managers (highest priority)
            "apt": 10,
            "dnf": 10,
            "yum": 10,
            "zypper": 10,
            "pacman": 10,
            "apk": 10,
            "pkg": 10,
            
            # Language-specific package managers
            "pypi": 9,
            "npm": 9,
            "cargo": 9,
            "gem": 9,
            "composer": 9,
            "maven": 9,
            "nuget": 9,
            
            # Third-party package managers
            "brew": 8,
            "scoop": 8,
            "choco": 8,
            "winget": 8,
            
            # Container registries
            "docker": 7,
            "helm": 7,
            
            # Universal package managers
            "snap": 6,
            "flatpak": 6,
            
            # Specialized package managers
            "nix": 5,
            "guix": 5,
            "spack": 5,
            
            # Default priority for unknown providers
            "default": 1,
        }
    
    def _get_default_reliability(self) -> Dict[str, float]:
        """Get default provider reliability scores."""
        return {
            # Official package managers (highest reliability)
            "apt": 0.95,
            "dnf": 0.95,
            "yum": 0.95,
            "zypper": 0.95,
            "pacman": 0.95,
            "apk": 0.95,
            "pkg": 0.95,
            
            # Language-specific package managers
            "pypi": 0.90,
            "npm": 0.90,
            "cargo": 0.90,
            "gem": 0.90,
            "composer": 0.90,
            "maven": 0.90,
            "nuget": 0.90,
            
            # Third-party package managers
            "brew": 0.85,
            "scoop": 0.80,
            "choco": 0.80,
            "winget": 0.85,
            
            # Container registries
            "docker": 0.85,
            "helm": 0.85,
            
            # Universal package managers
            "snap": 0.80,
            "flatpak": 0.80,
            
            # Specialized package managers
            "nix": 0.85,
            "guix": 0.85,
            "spack": 0.85,
            
            # Default reliability for unknown providers
            "default": 0.70,
        }
    
    def aggregate_package_data(
        self,
        software_name: str,
        sources: List[PackageInfo]
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Aggregate package data from multiple sources.
        
        Args:
            software_name: Name of the software package.
            sources: List of package information from different sources.
            
        Returns:
            Tuple of (aggregated_data, confidence_scores).
        """
        if not sources:
            return {}, {}
        
        # Convert sources to data points
        data_points = self._convert_sources_to_data_points(sources)
        
        # Group data points by field
        field_groups = self._group_data_points_by_field(data_points)
        
        # Aggregate each field
        aggregated_data = {}
        confidence_scores = {}
        
        for field_path, points in field_groups.items():
            result = self._aggregate_field(field_path, points)
            
            # Set the value in the aggregated data
            self._set_nested_value(aggregated_data, field_path, result.value)
            confidence_scores[field_path] = result.confidence
        
        # Add package configurations for each provider
        packages = {}
        for source in sources:
            packages[source.provider] = {
                "name": source.name,
                "version": source.version or "latest"
            }
        
        aggregated_data["packages"] = packages
        
        # Calculate overall confidence
        if confidence_scores:
            confidence_scores["overall"] = sum(confidence_scores.values()) / len(confidence_scores)
        else:
            confidence_scores["overall"] = 0.5
        
        return aggregated_data, confidence_scores
    
    def _convert_sources_to_data_points(self, sources: List[PackageInfo]) -> List[DataPoint]:
        """Convert package sources to data points."""
        data_points = []
        
        for source in sources:
            source_info = SourceInfo(
                provider=source.provider,
                priority=self.provider_priorities.get(source.provider, self.provider_priorities["default"]),
                reliability_score=self.provider_reliability.get(source.provider, self.provider_reliability["default"])
            )
            
            # Add description
            if source.description:
                data_points.append(DataPoint(
                    value=source.description,
                    source=source_info,
                    confidence=self._calculate_field_confidence("description", source.description, source_info),
                    field_path="description"
                ))
            
            # Add license
            if "license" in source.details and source.details["license"]:
                data_points.append(DataPoint(
                    value=source.details["license"],
                    source=source_info,
                    confidence=self._calculate_field_confidence("license", source.details["license"], source_info),
                    field_path="license"
                ))
            
            # Add URLs
            url_fields = {
                "homepage": "urls.website",
                "source_url": "urls.source",
                "download_url": "urls.download",
                "license_url": "urls.license"
            }
            
            for detail_key, field_path in url_fields.items():
                if detail_key in source.details and source.details[detail_key]:
                    data_points.append(DataPoint(
                        value=source.details[detail_key],
                        source=source_info,
                        confidence=self._calculate_field_confidence(field_path, source.details[detail_key], source_info),
                        field_path=field_path
                    ))
            
            # Add platforms
            if "platforms" in source.details and source.details["platforms"]:
                data_points.append(DataPoint(
                    value=source.details["platforms"],
                    source=source_info,
                    confidence=self._calculate_field_confidence("platforms", source.details["platforms"], source_info),
                    field_path="platforms"
                ))
        
        return data_points
    
    def _calculate_field_confidence(self, field_path: str, value: Any, source: SourceInfo) -> float:
        """Calculate confidence for a field value."""
        base_confidence = source.reliability_score
        
        # Adjust confidence based on field type and value characteristics
        if field_path == "description":
            # Longer descriptions are generally more informative
            if isinstance(value, str):
                length_factor = min(len(value) / 100.0, 1.0)  # Cap at 100 characters
                base_confidence *= (0.5 + 0.5 * length_factor)
        
        elif field_path == "license":
            # Well-known licenses get higher confidence
            well_known_licenses = {
                "MIT", "Apache-2.0", "GPL-3.0", "BSD-3-Clause", "BSD-2-Clause",
                "ISC", "MPL-2.0", "LGPL-3.0", "GPL-2.0", "Apache License 2.0"
            }
            if isinstance(value, str) and value in well_known_licenses:
                base_confidence *= 1.1
        
        elif field_path.startswith("urls."):
            # URLs with HTTPS get higher confidence
            if isinstance(value, str) and value.startswith("https://"):
                base_confidence *= 1.05
        
        elif field_path == "platforms":
            # More platforms generally indicate better coverage
            if isinstance(value, list):
                platform_factor = min(len(value) / 5.0, 1.0)  # Cap at 5 platforms
                base_confidence *= (0.7 + 0.3 * platform_factor)
        
        return min(base_confidence, 1.0)
    
    def _group_data_points_by_field(self, data_points: List[DataPoint]) -> Dict[str, List[DataPoint]]:
        """Group data points by field path."""
        groups = defaultdict(list)
        for point in data_points:
            groups[point.field_path].append(point)
        return dict(groups)
    
    def _aggregate_field(self, field_path: str, data_points: List[DataPoint]) -> AggregationResult:
        """Aggregate data points for a single field."""
        if not data_points:
            return AggregationResult(value=None, confidence=0.0)
        
        if len(data_points) == 1:
            point = data_points[0]
            return AggregationResult(
                value=point.value,
                confidence=point.confidence,
                sources=[point.source]
            )
        
        # Determine resolution strategy
        strategy = self.field_strategies.get(field_path, self.default_strategy)
        
        # Apply resolution strategy
        if strategy == ConflictResolutionStrategy.HIGHEST_CONFIDENCE:
            return self._resolve_by_highest_confidence(data_points)
        elif strategy == ConflictResolutionStrategy.MAJORITY_VOTE:
            return self._resolve_by_majority_vote(data_points)
        elif strategy == ConflictResolutionStrategy.MOST_RECENT:
            return self._resolve_by_most_recent(data_points)
        elif strategy == ConflictResolutionStrategy.LONGEST_VALUE:
            return self._resolve_by_longest_value(data_points)
        elif strategy == ConflictResolutionStrategy.PROVIDER_PRIORITY:
            return self._resolve_by_provider_priority(data_points)
        elif strategy == ConflictResolutionStrategy.MERGE_LISTS:
            return self._resolve_by_merging_lists(data_points)
        elif strategy == ConflictResolutionStrategy.MERGE_DICTS:
            return self._resolve_by_merging_dicts(data_points)
        else:
            return self._resolve_by_highest_confidence(data_points)
    
    def _resolve_by_highest_confidence(self, data_points: List[DataPoint]) -> AggregationResult:
        """Resolve conflicts by selecting the value with highest confidence."""
        best_point = max(data_points, key=lambda p: p.confidence)
        conflicts = [p for p in data_points if p != best_point]
        
        return AggregationResult(
            value=best_point.value,
            confidence=best_point.confidence,
            sources=[best_point.source],
            conflicts=conflicts,
            resolution_strategy=ConflictResolutionStrategy.HIGHEST_CONFIDENCE
        )
    
    def _resolve_by_majority_vote(self, data_points: List[DataPoint]) -> AggregationResult:
        """Resolve conflicts by majority vote."""
        value_counts = Counter(str(p.value) for p in data_points)
        most_common_value_str, count = value_counts.most_common(1)[0]
        
        # Find the actual value (not string representation)
        majority_points = [p for p in data_points if str(p.value) == most_common_value_str]
        best_point = max(majority_points, key=lambda p: p.confidence)
        
        # Calculate confidence based on majority and individual confidences
        majority_ratio = count / len(data_points)
        avg_confidence = sum(p.confidence for p in majority_points) / len(majority_points)
        final_confidence = majority_ratio * avg_confidence
        
        conflicts = [p for p in data_points if str(p.value) != most_common_value_str]
        
        return AggregationResult(
            value=best_point.value,
            confidence=final_confidence,
            sources=[p.source for p in majority_points],
            conflicts=conflicts,
            resolution_strategy=ConflictResolutionStrategy.MAJORITY_VOTE
        )
    
    def _resolve_by_most_recent(self, data_points: List[DataPoint]) -> AggregationResult:
        """Resolve conflicts by selecting the most recent value."""
        # Filter points with timestamps
        timestamped_points = [p for p in data_points if p.source.timestamp is not None]
        
        if timestamped_points:
            best_point = max(timestamped_points, key=lambda p: p.source.timestamp)
            conflicts = [p for p in data_points if p != best_point]
        else:
            # Fallback to highest confidence if no timestamps
            return self._resolve_by_highest_confidence(data_points)
        
        return AggregationResult(
            value=best_point.value,
            confidence=best_point.confidence,
            sources=[best_point.source],
            conflicts=conflicts,
            resolution_strategy=ConflictResolutionStrategy.MOST_RECENT
        )
    
    def _resolve_by_longest_value(self, data_points: List[DataPoint]) -> AggregationResult:
        """Resolve conflicts by selecting the longest string value."""
        string_points = [p for p in data_points if isinstance(p.value, str)]
        
        if string_points:
            best_point = max(string_points, key=lambda p: len(p.value))
            conflicts = [p for p in data_points if p != best_point]
        else:
            # Fallback to highest confidence if no string values
            return self._resolve_by_highest_confidence(data_points)
        
        return AggregationResult(
            value=best_point.value,
            confidence=best_point.confidence,
            sources=[best_point.source],
            conflicts=conflicts,
            resolution_strategy=ConflictResolutionStrategy.LONGEST_VALUE
        )
    
    def _resolve_by_provider_priority(self, data_points: List[DataPoint]) -> AggregationResult:
        """Resolve conflicts by provider priority."""
        best_point = max(data_points, key=lambda p: p.source.priority)
        conflicts = [p for p in data_points if p != best_point]
        
        return AggregationResult(
            value=best_point.value,
            confidence=best_point.confidence,
            sources=[best_point.source],
            conflicts=conflicts,
            resolution_strategy=ConflictResolutionStrategy.PROVIDER_PRIORITY
        )
    
    def _resolve_by_merging_lists(self, data_points: List[DataPoint]) -> AggregationResult:
        """Resolve conflicts by merging list values."""
        merged_list = []
        all_sources = []
        total_confidence = 0.0
        
        for point in data_points:
            if isinstance(point.value, list):
                for item in point.value:
                    if item not in merged_list:
                        merged_list.append(item)
                all_sources.append(point.source)
                total_confidence += point.confidence
        
        avg_confidence = total_confidence / len(data_points) if data_points else 0.0
        
        return AggregationResult(
            value=merged_list,
            confidence=avg_confidence,
            sources=all_sources,
            conflicts=[],  # No conflicts when merging
            resolution_strategy=ConflictResolutionStrategy.MERGE_LISTS
        )
    
    def _resolve_by_merging_dicts(self, data_points: List[DataPoint]) -> AggregationResult:
        """Resolve conflicts by merging dictionary values."""
        merged_dict = {}
        all_sources = []
        total_confidence = 0.0
        
        for point in data_points:
            if isinstance(point.value, dict):
                for key, value in point.value.items():
                    if key not in merged_dict and value:  # Only add non-empty values
                        merged_dict[key] = value
                all_sources.append(point.source)
                total_confidence += point.confidence
        
        avg_confidence = total_confidence / len(data_points) if data_points else 0.0
        
        return AggregationResult(
            value=merged_dict,
            confidence=avg_confidence,
            sources=all_sources,
            conflicts=[],  # No conflicts when merging
            resolution_strategy=ConflictResolutionStrategy.MERGE_DICTS
        )
    
    def _set_nested_value(self, data: Dict[str, Any], field_path: str, value: Any) -> None:
        """Set a nested value in a dictionary using dot notation."""
        keys = field_path.split('.')
        current = data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def get_conflict_report(
        self,
        software_name: str,
        sources: List[PackageInfo]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate a conflict report showing disagreements between sources.
        
        Args:
            software_name: Name of the software package.
            sources: List of package information from different sources.
            
        Returns:
            Dictionary mapping field paths to lists of conflicting values.
        """
        data_points = self._convert_sources_to_data_points(sources)
        field_groups = self._group_data_points_by_field(data_points)
        
        conflicts = {}
        
        for field_path, points in field_groups.items():
            if len(points) > 1:
                # Check if there are actual conflicts (different values)
                unique_values = set(str(p.value) for p in points)
                if len(unique_values) > 1:
                    conflicts[field_path] = [
                        {
                            "value": point.value,
                            "provider": point.source.provider,
                            "confidence": point.confidence,
                            "priority": point.source.priority
                        }
                        for point in points
                    ]
        
        return conflicts