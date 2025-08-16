"""
Quality assessment and verification module for saidata-gen.

This module provides comprehensive quality scoring, confidence assessment,
and cross-reference validation for generated metadata across multiple data sources.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

from saidata_gen.core.interfaces import (
    PackageInfo, PackageDetails, SaidataMetadata, ValidationLevel
)


@dataclass
class SourceAttribution:
    """
    Attribution information for a data field.
    """
    provider: str
    field_name: str
    value: Any
    confidence: float
    timestamp: Optional[datetime] = None
    source_url: Optional[str] = None
    verification_method: Optional[str] = None


@dataclass
class FieldQuality:
    """
    Quality assessment for a specific field.
    """
    field_name: str
    value: Any
    confidence_score: float
    quality_score: float
    sources: List[SourceAttribution] = field(default_factory=list)
    consistency_score: float = 0.0
    completeness_score: float = 0.0
    accuracy_indicators: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class QualityReport:
    """
    Comprehensive quality report for metadata.
    """
    software_name: str
    overall_quality_score: float
    overall_confidence_score: float
    field_qualities: Dict[str, FieldQuality] = field(default_factory=dict)
    cross_reference_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    source_reliability: Dict[str, float] = field(default_factory=dict)
    data_freshness: Dict[str, float] = field(default_factory=dict)
    consistency_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    generation_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CrossReferenceResult:
    """
    Result of cross-reference validation.
    """
    field_name: str
    values: Dict[str, Any]  # provider -> value
    consensus_value: Any
    consensus_confidence: float
    conflicts: List[Tuple[str, str, Any, Any]]  # provider1, provider2, value1, value2
    agreement_score: float


class QualityAssessment:
    """
    Comprehensive quality assessment system for saidata metadata.
    
    Provides confidence scoring, cross-reference validation, and quality reporting
    with source attribution for generated metadata.
    """
    
    def __init__(self):
        """Initialize the quality assessment system."""
        # Provider reliability weights based on data quality and freshness
        self.provider_weights = {
            'apt': 0.9,
            'dnf': 0.9,
            'brew': 0.85,
            'winget': 0.8,
            'scoop': 0.75,
            'npm': 0.85,
            'pypi': 0.9,
            'cargo': 0.85,
            'docker': 0.8,
            'snap': 0.75,
            'flatpak': 0.8,
            'default': 0.7
        }
        
        # Field importance weights for overall quality calculation
        self.field_weights = {
            'name': 1.0,
            'description': 0.8,
            'version': 0.7,
            'license': 0.6,
            'homepage': 0.6,
            'source_url': 0.5,
            'platforms': 0.5,
            'category': 0.4,
            'dependencies': 0.3
        }
        
        # Quality thresholds
        self.quality_thresholds = {
            'excellent': 0.9,
            'good': 0.75,
            'fair': 0.6,
            'poor': 0.4
        }
        
        # Common patterns for validation
        self.url_pattern = re.compile(
            r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$'
        )
        self.version_pattern = re.compile(r'^(\d+)\.(\d+)(?:\.(\d+))?(?:[-.]?([a-zA-Z0-9]+))?$')
        self.license_patterns = {
            'MIT': re.compile(r'MIT|mit', re.IGNORECASE),
            'Apache-2.0': re.compile(r'Apache.*2\.0|apache.*2\.0', re.IGNORECASE),
            'GPL-3.0': re.compile(r'GPL.*3\.0|gpl.*3\.0|GNU.*General.*Public.*License.*3', re.IGNORECASE),
            'BSD': re.compile(r'BSD|bsd', re.IGNORECASE)
        }
    
    def assess_metadata_quality(
        self,
        metadata: SaidataMetadata,
        source_data: Dict[str, List[PackageInfo]],
        software_name: str
    ) -> QualityReport:
        """
        Perform comprehensive quality assessment of generated metadata.
        
        Args:
            metadata: Generated saidata metadata
            source_data: Raw data from multiple sources
            software_name: Name of the software being assessed
            
        Returns:
            Comprehensive quality report
        """
        report = QualityReport(
            software_name=software_name,
            overall_quality_score=0.0,
            overall_confidence_score=0.0
        )
        
        # Assess individual fields
        field_qualities = {}
        
        # Assess basic metadata fields
        if metadata.description:
            field_qualities['description'] = self._assess_description_quality(
                metadata.description, source_data
            )
        
        if metadata.license:
            field_qualities['license'] = self._assess_license_quality(
                metadata.license, source_data
            )
        
        if metadata.platforms:
            field_qualities['platforms'] = self._assess_platforms_quality(
                metadata.platforms, source_data
            )
        
        if metadata.urls:
            field_qualities['urls'] = self._assess_urls_quality(
                metadata.urls, source_data
            )
        
        if metadata.category:
            field_qualities['category'] = self._assess_category_quality(
                metadata.category, source_data
            )
        
        if metadata.packages:
            field_qualities['packages'] = self._assess_packages_quality(
                metadata.packages, source_data
            )
        
        # Perform cross-reference validation
        cross_reference_results = self._perform_cross_reference_validation(source_data)
        
        # Calculate source reliability scores
        source_reliability = self._calculate_source_reliability(source_data)
        
        # Calculate data freshness scores
        data_freshness = self._calculate_data_freshness(source_data)
        
        # Identify consistency issues
        consistency_issues = self._identify_consistency_issues(cross_reference_results)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            field_qualities, cross_reference_results, consistency_issues
        )
        
        # Calculate overall scores
        overall_quality_score = self._calculate_overall_quality_score(field_qualities)
        overall_confidence_score = self._calculate_overall_confidence_score(field_qualities)
        
        # Populate report
        report.overall_quality_score = overall_quality_score
        report.overall_confidence_score = overall_confidence_score
        report.field_qualities = field_qualities
        report.cross_reference_results = cross_reference_results
        report.source_reliability = source_reliability
        report.data_freshness = data_freshness
        report.consistency_issues = consistency_issues
        report.recommendations = recommendations
        
        return report
    
    def calculate_field_confidence(
        self,
        field_name: str,
        value: Any,
        sources: List[SourceAttribution]
    ) -> float:
        """
        Calculate confidence score for a specific field based on multiple sources.
        
        Args:
            field_name: Name of the field
            value: Field value
            sources: List of source attributions
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not sources:
            return 0.0
        
        # Base confidence from source reliability
        source_confidence = sum(
            self.provider_weights.get(source.provider, 0.5) * source.confidence
            for source in sources
        ) / len(sources)
        
        # Agreement bonus - higher confidence if multiple sources agree
        agreement_bonus = 0.0
        if len(sources) > 1:
            agreement_count = sum(1 for source in sources if source.value == value)
            agreement_ratio = agreement_count / len(sources)
            agreement_bonus = agreement_ratio * 0.2
        
        # Field-specific validation
        validation_bonus = self._validate_field_format(field_name, value)
        
        # Combine scores
        confidence = min(1.0, source_confidence + agreement_bonus + validation_bonus)
        
        return confidence
    
    def _assess_description_quality(
        self,
        description: str,
        source_data: Dict[str, List[PackageInfo]]
    ) -> FieldQuality:
        """Assess quality of description field."""
        sources = []
        for provider, packages in source_data.items():
            for package in packages:
                if package.description:
                    sources.append(SourceAttribution(
                        provider=provider,
                        field_name='description',
                        value=package.description,
                        confidence=self.provider_weights.get(provider, 0.5)
                    ))
        
        # Quality indicators
        length_score = min(1.0, len(description) / 100)  # Prefer longer descriptions
        uniqueness_score = self._calculate_text_uniqueness(description, sources)
        clarity_score = self._assess_text_clarity(description)
        
        quality_score = (length_score + uniqueness_score + clarity_score) / 3
        confidence_score = self.calculate_field_confidence('description', description, sources)
        
        issues = []
        recommendations = []
        
        if len(description) < 20:
            issues.append("Description is very short")
            recommendations.append("Consider expanding the description with more details")
        
        if not description[0].isupper():
            issues.append("Description should start with a capital letter")
            recommendations.append("Capitalize the first letter of the description")
        
        return FieldQuality(
            field_name='description',
            value=description,
            confidence_score=confidence_score,
            quality_score=quality_score,
            sources=sources,
            accuracy_indicators={
                'length_score': length_score,
                'uniqueness_score': uniqueness_score,
                'clarity_score': clarity_score
            },
            issues=issues,
            recommendations=recommendations
        )
    
    def _assess_license_quality(
        self,
        license_value: str,
        source_data: Dict[str, List[PackageInfo]]
    ) -> FieldQuality:
        """Assess quality of license field."""
        sources = []
        for provider, packages in source_data.items():
            for package in packages:
                if hasattr(package, 'license') and package.license:
                    sources.append(SourceAttribution(
                        provider=provider,
                        field_name='license',
                        value=package.license,
                        confidence=self.provider_weights.get(provider, 0.5)
                    ))
        
        # Quality indicators
        format_score = self._validate_license_format(license_value)
        consistency_score = self._calculate_license_consistency(license_value, sources)
        
        quality_score = (format_score + consistency_score) / 2
        confidence_score = self.calculate_field_confidence('license', license_value, sources)
        
        issues = []
        recommendations = []
        
        if format_score < 0.8:
            issues.append("License format may not be standard SPDX identifier")
            recommendations.append("Use standard SPDX license identifier")
        
        return FieldQuality(
            field_name='license',
            value=license_value,
            confidence_score=confidence_score,
            quality_score=quality_score,
            sources=sources,
            accuracy_indicators={
                'format_score': format_score,
                'consistency_score': consistency_score
            },
            issues=issues,
            recommendations=recommendations
        )
    
    def _assess_platforms_quality(
        self,
        platforms: List[str],
        source_data: Dict[str, List[PackageInfo]]
    ) -> FieldQuality:
        """Assess quality of platforms field."""
        sources = []
        for provider, packages in source_data.items():
            # Infer platforms from provider
            provider_platforms = self._infer_platforms_from_provider(provider)
            if provider_platforms:
                sources.append(SourceAttribution(
                    provider=provider,
                    field_name='platforms',
                    value=provider_platforms,
                    confidence=self.provider_weights.get(provider, 0.5)
                ))
        
        # Quality indicators
        completeness_score = self._assess_platform_completeness(platforms)
        accuracy_score = self._validate_platform_names(platforms)
        
        quality_score = (completeness_score + accuracy_score) / 2
        confidence_score = self.calculate_field_confidence('platforms', platforms, sources)
        
        issues = []
        recommendations = []
        
        if not platforms:
            issues.append("No platforms specified")
            recommendations.append("Add supported platforms")
        
        for platform in platforms:
            if platform.lower() not in ['linux', 'windows', 'macos', 'darwin', 'freebsd']:
                issues.append(f"Platform '{platform}' may not be standard")
                recommendations.append(f"Verify platform name '{platform}' is correct")
        
        return FieldQuality(
            field_name='platforms',
            value=platforms,
            confidence_score=confidence_score,
            quality_score=quality_score,
            sources=sources,
            accuracy_indicators={
                'completeness_score': completeness_score,
                'accuracy_score': accuracy_score
            },
            issues=issues,
            recommendations=recommendations
        )
    
    def _assess_urls_quality(
        self,
        urls: Any,
        source_data: Dict[str, List[PackageInfo]]
    ) -> FieldQuality:
        """Assess quality of URLs field."""
        sources = []
        for provider, packages in source_data.items():
            for package in packages:
                if hasattr(package, 'homepage') and package.homepage:
                    sources.append(SourceAttribution(
                        provider=provider,
                        field_name='urls.website',
                        value=package.homepage,
                        confidence=self.provider_weights.get(provider, 0.5)
                    ))
        
        # Quality indicators
        url_dict = urls.__dict__ if hasattr(urls, '__dict__') else urls
        validity_score = self._validate_urls(url_dict)
        completeness_score = self._assess_url_completeness(url_dict)
        
        quality_score = (validity_score + completeness_score) / 2
        confidence_score = self.calculate_field_confidence('urls', url_dict, sources)
        
        issues = []
        recommendations = []
        
        if not url_dict.get('website'):
            issues.append("Website URL is missing")
            recommendations.append("Add website URL for better documentation")
        
        for url_type, url_value in url_dict.items():
            if url_value and not self.url_pattern.match(str(url_value)):
                issues.append(f"Invalid URL format for {url_type}")
                recommendations.append(f"Fix URL format for {url_type}")
        
        return FieldQuality(
            field_name='urls',
            value=url_dict,
            confidence_score=confidence_score,
            quality_score=quality_score,
            sources=sources,
            accuracy_indicators={
                'validity_score': validity_score,
                'completeness_score': completeness_score
            },
            issues=issues,
            recommendations=recommendations
        )
    
    def _assess_category_quality(
        self,
        category: Any,
        source_data: Dict[str, List[PackageInfo]]
    ) -> FieldQuality:
        """Assess quality of category field."""
        sources = []
        # Categories are typically inferred, so confidence is lower
        for provider in source_data.keys():
            sources.append(SourceAttribution(
                provider=provider,
                field_name='category',
                value='inferred',
                confidence=0.6
            ))
        
        category_dict = category.__dict__ if hasattr(category, '__dict__') else category
        
        # Quality indicators
        completeness_score = 1.0 if category_dict.get('default') else 0.5
        accuracy_score = self._validate_category_names(category_dict)
        
        quality_score = (completeness_score + accuracy_score) / 2
        confidence_score = 0.6  # Categories are typically inferred
        
        issues = []
        recommendations = []
        
        if not category_dict.get('default'):
            issues.append("Default category is missing")
            recommendations.append("Add default category")
        
        return FieldQuality(
            field_name='category',
            value=category_dict,
            confidence_score=confidence_score,
            quality_score=quality_score,
            sources=sources,
            accuracy_indicators={
                'completeness_score': completeness_score,
                'accuracy_score': accuracy_score
            },
            issues=issues,
            recommendations=recommendations
        )
    
    def _assess_packages_quality(
        self,
        packages: Dict[str, Any],
        source_data: Dict[str, List[PackageInfo]]
    ) -> FieldQuality:
        """Assess quality of packages field."""
        sources = []
        for provider, package_list in source_data.items():
            for package in package_list:
                sources.append(SourceAttribution(
                    provider=provider,
                    field_name='packages',
                    value=package.name,
                    confidence=self.provider_weights.get(provider, 0.5)
                ))
        
        # Quality indicators
        completeness_score = self._assess_package_completeness(packages)
        accuracy_score = self._validate_package_names(packages, source_data)
        
        quality_score = (completeness_score + accuracy_score) / 2
        confidence_score = self.calculate_field_confidence('packages', packages, sources)
        
        issues = []
        recommendations = []
        
        if not packages:
            issues.append("No packages defined")
            recommendations.append("Add package definitions")
        
        for pkg_key, pkg_config in packages.items():
            if isinstance(pkg_config, dict) and not pkg_config.get('name'):
                issues.append(f"Package '{pkg_key}' has no name specified")
                recommendations.append(f"Add name for package '{pkg_key}'")
        
        return FieldQuality(
            field_name='packages',
            value=packages,
            confidence_score=confidence_score,
            quality_score=quality_score,
            sources=sources,
            accuracy_indicators={
                'completeness_score': completeness_score,
                'accuracy_score': accuracy_score
            },
            issues=issues,
            recommendations=recommendations
        )
    
    def _perform_cross_reference_validation(
        self,
        source_data: Dict[str, List[PackageInfo]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Perform cross-reference validation across multiple data sources.
        """
        results = {}
        
        # Cross-reference package names
        results['package_names'] = self._cross_reference_package_names(source_data)
        
        # Cross-reference descriptions
        results['descriptions'] = self._cross_reference_descriptions(source_data)
        
        # Cross-reference versions
        results['versions'] = self._cross_reference_versions(source_data)
        
        # Cross-reference licenses
        results['licenses'] = self._cross_reference_licenses(source_data)
        
        return results
    
    def _cross_reference_package_names(
        self,
        source_data: Dict[str, List[PackageInfo]]
    ) -> CrossReferenceResult:
        """Cross-reference package names across sources."""
        values = {}
        for provider, packages in source_data.items():
            if packages:
                values[provider] = packages[0].name
        
        # Find consensus
        name_counts = {}
        for name in values.values():
            name_counts[name] = name_counts.get(name, 0) + 1
        
        consensus_value = max(name_counts.keys(), key=name_counts.get) if name_counts else None
        consensus_confidence = name_counts.get(consensus_value, 0) / len(values) if values else 0
        
        # Find conflicts
        conflicts = []
        for p1, v1 in values.items():
            for p2, v2 in values.items():
                if p1 < p2 and v1 != v2:
                    conflicts.append((p1, p2, v1, v2))
        
        agreement_score = 1.0 - (len(conflicts) / max(1, len(values) * (len(values) - 1) / 2))
        
        return CrossReferenceResult(
            field_name='package_names',
            values=values,
            consensus_value=consensus_value,
            consensus_confidence=consensus_confidence,
            conflicts=conflicts,
            agreement_score=agreement_score
        )
    
    def _cross_reference_descriptions(
        self,
        source_data: Dict[str, List[PackageInfo]]
    ) -> CrossReferenceResult:
        """Cross-reference descriptions across sources."""
        values = {}
        for provider, packages in source_data.items():
            for package in packages:
                if package.description:
                    values[provider] = package.description
                    break
        
        # Find most common description (by similarity)
        consensus_value = self._find_consensus_text(list(values.values())) if values else None
        consensus_confidence = 0.7 if consensus_value else 0.0
        
        # Find conflicts (descriptions that are very different)
        conflicts = []
        for p1, v1 in values.items():
            for p2, v2 in values.items():
                if p1 < p2 and self._text_similarity(v1, v2) < 0.5:
                    conflicts.append((p1, p2, v1, v2))
        
        agreement_score = 1.0 - (len(conflicts) / max(1, len(values) * (len(values) - 1) / 2))
        
        return CrossReferenceResult(
            field_name='descriptions',
            values=values,
            consensus_value=consensus_value,
            consensus_confidence=consensus_confidence,
            conflicts=conflicts,
            agreement_score=agreement_score
        )
    
    def _cross_reference_versions(
        self,
        source_data: Dict[str, List[PackageInfo]]
    ) -> CrossReferenceResult:
        """Cross-reference versions across sources."""
        values = {}
        for provider, packages in source_data.items():
            for package in packages:
                if package.version:
                    values[provider] = package.version
                    break
        
        # Find most recent version
        consensus_value = self._find_latest_version(list(values.values())) if values else None
        consensus_confidence = 0.8 if consensus_value else 0.0
        
        # Find conflicts (very different versions)
        conflicts = []
        for p1, v1 in values.items():
            for p2, v2 in values.items():
                if p1 < p2 and not self._versions_compatible(v1, v2):
                    conflicts.append((p1, p2, v1, v2))
        
        agreement_score = 1.0 - (len(conflicts) / max(1, len(values) * (len(values) - 1) / 2))
        
        return CrossReferenceResult(
            field_name='versions',
            values=values,
            consensus_value=consensus_value,
            consensus_confidence=consensus_confidence,
            conflicts=conflicts,
            agreement_score=agreement_score
        )
    
    def _cross_reference_licenses(
        self,
        source_data: Dict[str, List[PackageInfo]]
    ) -> CrossReferenceResult:
        """Cross-reference licenses across sources."""
        values = {}
        for provider, packages in source_data.items():
            for package in packages:
                if hasattr(package, 'license') and package.license:
                    values[provider] = package.license
                    break
        
        # Normalize licenses and find consensus
        normalized_values = {p: self._normalize_license(v) for p, v in values.items()}
        license_counts = {}
        for license_name in normalized_values.values():
            license_counts[license_name] = license_counts.get(license_name, 0) + 1
        
        consensus_value = max(license_counts.keys(), key=license_counts.get) if license_counts else None
        consensus_confidence = license_counts.get(consensus_value, 0) / len(values) if values else 0
        
        # Find conflicts
        conflicts = []
        for p1, v1 in normalized_values.items():
            for p2, v2 in normalized_values.items():
                if p1 < p2 and v1 != v2:
                    conflicts.append((p1, p2, values[p1], values[p2]))
        
        agreement_score = 1.0 - (len(conflicts) / max(1, len(values) * (len(values) - 1) / 2))
        
        return CrossReferenceResult(
            field_name='licenses',
            values=values,
            consensus_value=consensus_value,
            consensus_confidence=consensus_confidence,
            conflicts=conflicts,
            agreement_score=agreement_score
        )
    
    def _calculate_source_reliability(
        self,
        source_data: Dict[str, List[PackageInfo]]
    ) -> Dict[str, float]:
        """Calculate reliability scores for each data source."""
        reliability = {}
        
        for provider, packages in source_data.items():
            base_weight = self.provider_weights.get(provider, 0.5)
            
            # Adjust based on data completeness
            completeness_bonus = 0.0
            if packages:
                total_fields = 0
                filled_fields = 0
                
                for package in packages:
                    fields = ['name', 'version', 'description']
                    total_fields += len(fields)
                    
                    for field in fields:
                        if hasattr(package, field) and getattr(package, field):
                            filled_fields += 1
                
                if total_fields > 0:
                    completeness_bonus = (filled_fields / total_fields) * 0.2
            
            reliability[provider] = min(1.0, base_weight + completeness_bonus)
        
        return reliability
    
    def _calculate_data_freshness(
        self,
        source_data: Dict[str, List[PackageInfo]]
    ) -> Dict[str, float]:
        """Calculate data freshness scores for each source."""
        freshness = {}
        
        for provider, packages in source_data.items():
            # For now, assume all data is reasonably fresh
            # In a real implementation, this would check timestamps
            freshness[provider] = 0.8
        
        return freshness
    
    def _identify_consistency_issues(
        self,
        cross_reference_results: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """Identify consistency issues from cross-reference results."""
        issues = []
        
        for field_name, result in cross_reference_results.items():
            if isinstance(result, CrossReferenceResult):
                if result.conflicts:
                    issues.append(
                        f"Conflicting {field_name} found across sources: "
                        f"{len(result.conflicts)} conflicts detected"
                    )
                
                if result.agreement_score < 0.7:
                    issues.append(
                        f"Low agreement score ({result.agreement_score:.2f}) for {field_name}"
                    )
        
        return issues
    
    def _generate_recommendations(
        self,
        field_qualities: Dict[str, FieldQuality],
        cross_reference_results: Dict[str, Dict[str, Any]],
        consistency_issues: List[str]
    ) -> List[str]:
        """Generate recommendations for improving metadata quality."""
        recommendations = []
        
        # Field-specific recommendations
        for field_name, quality in field_qualities.items():
            if quality.confidence_score < 0.7:
                recommendations.append(
                    f"Consider verifying {field_name} from additional sources "
                    f"(current confidence: {quality.confidence_score:.2f})"
                )
            
            if quality.quality_score < 0.6:
                recommendations.append(
                    f"Improve {field_name} quality "
                    f"(current quality: {quality.quality_score:.2f})"
                )
            
            recommendations.extend(quality.recommendations)
        
        # Cross-reference recommendations
        for field_name, result in cross_reference_results.items():
            if isinstance(result, CrossReferenceResult) and result.conflicts:
                recommendations.append(
                    f"Resolve conflicts in {field_name} by manually reviewing source data"
                )
        
        # General recommendations
        if consistency_issues:
            recommendations.append(
                "Review data sources for consistency issues and consider "
                "prioritizing more reliable sources"
            )
        
        return list(set(recommendations))  # Remove duplicates
    
    def _calculate_overall_quality_score(
        self,
        field_qualities: Dict[str, FieldQuality]
    ) -> float:
        """Calculate overall quality score from field qualities."""
        if not field_qualities:
            return 0.0
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for field_name, quality in field_qualities.items():
            weight = self.field_weights.get(field_name, 0.5)
            weighted_sum += quality.quality_score * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _calculate_overall_confidence_score(
        self,
        field_qualities: Dict[str, FieldQuality]
    ) -> float:
        """Calculate overall confidence score from field qualities."""
        if not field_qualities:
            return 0.0
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for field_name, quality in field_qualities.items():
            weight = self.field_weights.get(field_name, 0.5)
            weighted_sum += quality.confidence_score * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    # Helper methods for validation and scoring
    
    def _validate_field_format(self, field_name: str, value: Any) -> float:
        """Validate field format and return bonus score."""
        if field_name == 'license':
            return self._validate_license_format(value)
        elif field_name == 'version':
            return 1.0 if self.version_pattern.match(str(value)) else 0.0
        elif 'url' in field_name.lower():
            return 1.0 if self.url_pattern.match(str(value)) else 0.0
        return 0.0
    
    def _validate_license_format(self, license_value: str) -> float:
        """Validate license format."""
        # Check against common SPDX identifiers
        spdx_licenses = {
            'MIT', 'Apache-2.0', 'GPL-3.0', 'GPL-2.0', 'BSD-3-Clause',
            'BSD-2-Clause', 'ISC', 'MPL-2.0', 'LGPL-3.0', 'LGPL-2.1'
        }
        
        if license_value in spdx_licenses:
            return 1.0
        
        # Check against patterns
        for pattern in self.license_patterns.values():
            if pattern.search(license_value):
                return 0.8
        
        return 0.3
    
    def _calculate_text_uniqueness(self, text: str, sources: List[SourceAttribution]) -> float:
        """Calculate uniqueness score for text."""
        if not sources:
            return 0.5
        
        # Simple uniqueness based on text length and word count
        words = set(text.lower().split())
        unique_words = len(words)
        
        # Compare with other sources
        similarity_scores = []
        for source in sources:
            if isinstance(source.value, str):
                similarity = self._text_similarity(text, source.value)
                similarity_scores.append(similarity)
        
        avg_similarity = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0
        uniqueness = 1.0 - avg_similarity
        
        return max(0.0, min(1.0, uniqueness))
    
    def _assess_text_clarity(self, text: str) -> float:
        """Assess text clarity."""
        # Simple heuristics for text clarity
        score = 0.5
        
        # Length bonus
        if 20 <= len(text) <= 200:
            score += 0.2
        
        # Sentence structure
        if '.' in text:
            score += 0.1
        
        # No excessive punctuation
        punct_ratio = sum(1 for c in text if c in '!@#$%^&*()') / len(text)
        if punct_ratio < 0.1:
            score += 0.2
        
        return min(1.0, score)
    
    def _calculate_license_consistency(self, license_value: str, sources: List[SourceAttribution]) -> float:
        """Calculate license consistency across sources."""
        if not sources:
            return 0.5
        
        normalized_license = self._normalize_license(license_value)
        matching_sources = 0
        
        for source in sources:
            if isinstance(source.value, str):
                normalized_source = self._normalize_license(source.value)
                if normalized_source == normalized_license:
                    matching_sources += 1
        
        return matching_sources / len(sources)
    
    def _normalize_license(self, license_str: str) -> str:
        """Normalize license string for comparison."""
        license_lower = license_str.lower()
        
        # Map common variations to standard names
        if 'mit' in license_lower:
            return 'MIT'
        elif 'apache' in license_lower and '2' in license_lower:
            return 'Apache-2.0'
        elif 'gpl' in license_lower and '3' in license_lower:
            return 'GPL-3.0'
        elif 'bsd' in license_lower:
            return 'BSD'
        
        return license_str
    
    def _infer_platforms_from_provider(self, provider: str) -> List[str]:
        """Infer supported platforms from provider."""
        platform_map = {
            'apt': ['linux'],
            'dnf': ['linux'],
            'yum': ['linux'],
            'zypper': ['linux'],
            'pacman': ['linux'],
            'brew': ['macos', 'linux'],
            'winget': ['windows'],
            'scoop': ['windows'],
            'choco': ['windows'],
            'npm': ['linux', 'windows', 'macos'],
            'pypi': ['linux', 'windows', 'macos'],
            'cargo': ['linux', 'windows', 'macos']
        }
        
        return platform_map.get(provider, [])
    
    def _assess_platform_completeness(self, platforms: List[str]) -> float:
        """Assess completeness of platform list."""
        if not platforms:
            return 0.0
        
        # Common platforms
        common_platforms = {'linux', 'windows', 'macos'}
        platform_set = {p.lower() for p in platforms}
        
        coverage = len(platform_set.intersection(common_platforms)) / len(common_platforms)
        return coverage
    
    def _validate_platform_names(self, platforms: List[str]) -> float:
        """Validate platform names."""
        if not platforms:
            return 0.0
        
        valid_platforms = {
            'linux', 'windows', 'macos', 'darwin', 'freebsd', 'openbsd',
            'netbsd', 'solaris', 'aix', 'android', 'ios'
        }
        
        valid_count = sum(1 for p in platforms if p.lower() in valid_platforms)
        return valid_count / len(platforms)
    
    def _validate_urls(self, url_dict: Dict[str, Any]) -> float:
        """Validate URLs in URL dictionary."""
        if not url_dict:
            return 0.0
        
        valid_count = 0
        total_count = 0
        
        for url_value in url_dict.values():
            if url_value:
                total_count += 1
                if self.url_pattern.match(str(url_value)):
                    valid_count += 1
        
        return valid_count / total_count if total_count > 0 else 1.0
    
    def _assess_url_completeness(self, url_dict: Dict[str, Any]) -> float:
        """Assess completeness of URL dictionary."""
        important_urls = ['website', 'source', 'documentation']
        present_count = sum(1 for url_type in important_urls if url_dict.get(url_type))
        
        return present_count / len(important_urls)
    
    def _validate_category_names(self, category_dict: Dict[str, Any]) -> float:
        """Validate category names."""
        common_categories = {
            'development', 'productivity', 'system', 'network', 'security',
            'multimedia', 'graphics', 'office', 'education', 'games',
            'science', 'database', 'web', 'communication', 'utilities'
        }
        
        default_category = category_dict.get('default')
        if not default_category:
            return 0.5
        
        return 1.0 if default_category.lower() in common_categories else 0.5
    
    def _assess_package_completeness(self, packages: Dict[str, Any]) -> float:
        """Assess completeness of package definitions."""
        if not packages:
            return 0.0
        
        complete_packages = 0
        for pkg_config in packages.values():
            if isinstance(pkg_config, dict) and pkg_config.get('name'):
                complete_packages += 1
        
        return complete_packages / len(packages)
    
    def _validate_package_names(self, packages: Dict[str, Any], source_data: Dict[str, List[PackageInfo]]) -> float:
        """Validate package names against source data."""
        if not packages or not source_data:
            return 0.5
        
        # Collect all known package names from sources
        known_names = set()
        for package_list in source_data.values():
            for package in package_list:
                known_names.add(package.name)
        
        valid_count = 0
        total_count = 0
        
        for pkg_config in packages.values():
            if isinstance(pkg_config, dict) and pkg_config.get('name'):
                total_count += 1
                if pkg_config['name'] in known_names:
                    valid_count += 1
        
        return valid_count / total_count if total_count > 0 else 0.5
    
    def _find_consensus_text(self, texts: List[str]) -> str:
        """Find consensus text from a list of texts."""
        if not texts:
            return ""
        
        if len(texts) == 1:
            return texts[0]
        
        # Find the text with highest average similarity to others
        best_text = texts[0]
        best_score = 0.0
        
        for text in texts:
            similarity_sum = sum(self._text_similarity(text, other) for other in texts if other != text)
            avg_similarity = similarity_sum / (len(texts) - 1)
            
            if avg_similarity > best_score:
                best_score = avg_similarity
                best_text = text
        
        return best_text
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts."""
        if not text1 or not text2:
            return 0.0
        
        # Simple word-based similarity using Jaccard coefficient
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        jaccard = len(intersection) / len(union) if union else 0.0
        
        # Also consider word order similarity for better results
        words1_list = text1.lower().split()
        words2_list = text2.lower().split()
        
        # Calculate positional similarity
        position_score = 0.0
        if words1_list and words2_list:
            common_words = intersection
            if common_words:
                position_matches = 0
                total_positions = 0
                
                for word in common_words:
                    if word in words1_list and word in words2_list:
                        pos1 = words1_list.index(word) / len(words1_list)
                        pos2 = words2_list.index(word) / len(words2_list)
                        position_matches += 1 - abs(pos1 - pos2)
                        total_positions += 1
                
                if total_positions > 0:
                    position_score = position_matches / total_positions
        
        # Combine Jaccard and position scores
        return (jaccard * 0.7) + (position_score * 0.3)
    
    def _find_latest_version(self, versions: List[str]) -> str:
        """Find the latest version from a list of versions."""
        if not versions:
            return ""
        
        # Simple version comparison (would need more sophisticated logic for real use)
        return max(versions, key=lambda v: self._version_sort_key(v))
    
    def _version_sort_key(self, version: str) -> Tuple[int, ...]:
        """Create sort key for version string."""
        try:
            # Extract numeric parts
            parts = re.findall(r'\d+', version)
            return tuple(int(part) for part in parts)
        except:
            return (0,)
    
    def _versions_compatible(self, version1: str, version2: str) -> bool:
        """Check if two versions are compatible (similar major version)."""
        try:
            v1_parts = self._version_sort_key(version1)
            v2_parts = self._version_sort_key(version2)
            
            # Consider compatible if major version is the same
            return v1_parts[0] == v2_parts[0] if v1_parts and v2_parts else True
        except:
            return True