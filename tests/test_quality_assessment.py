"""
Unit tests for quality assessment and verification system.

Tests confidence scoring, cross-reference validation, and quality reporting
functionality for saidata metadata generation.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from saidata_gen.core.interfaces import PackageInfo, SaidataMetadata, URLConfig, CategoryConfig
from saidata_gen.validation.quality import (
    QualityAssessment, QualityReport, FieldQuality, SourceAttribution,
    CrossReferenceResult
)


class TestQualityAssessment:
    """Test cases for QualityAssessment class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.quality_assessment = QualityAssessment()
        
        # Sample source data
        self.sample_source_data = {
            'apt': [
                PackageInfo(
                    name='nginx',
                    provider='apt',
                    version='1.18.0',
                    description='High-performance HTTP server and reverse proxy'
                )
            ],
            'brew': [
                PackageInfo(
                    name='nginx',
                    provider='brew',
                    version='1.19.0',
                    description='HTTP server and reverse proxy'
                )
            ],
            'docker': [
                PackageInfo(
                    name='nginx',
                    provider='docker',
                    version='1.19.1',
                    description='Official nginx Docker image'
                )
            ]
        }
        
        # Sample metadata
        self.sample_metadata = SaidataMetadata(
            version="0.1",
            description="High-performance HTTP server and reverse proxy",
            license="BSD-2-Clause",
            platforms=["linux", "windows", "macos"],
            urls=URLConfig(
                website="https://nginx.org",
                source="https://github.com/nginx/nginx",
                documentation="https://nginx.org/en/docs/"
            ),
            category=CategoryConfig(default="web", tags=["server", "proxy"]),
            packages={
                'apt': {'name': 'nginx'},
                'brew': {'name': 'nginx'},
                'docker': {'name': 'nginx'}
            }
        )
    
    def test_assess_metadata_quality_basic(self):
        """Test basic metadata quality assessment."""
        report = self.quality_assessment.assess_metadata_quality(
            self.sample_metadata,
            self.sample_source_data,
            "nginx"
        )
        
        assert isinstance(report, QualityReport)
        assert report.software_name == "nginx"
        assert 0.0 <= report.overall_quality_score <= 1.0
        assert 0.0 <= report.overall_confidence_score <= 1.0
        assert isinstance(report.field_qualities, dict)
        assert isinstance(report.cross_reference_results, dict)
        assert isinstance(report.source_reliability, dict)
        assert isinstance(report.recommendations, list)
    
    def test_calculate_field_confidence_single_source(self):
        """Test confidence calculation with single source."""
        sources = [
            SourceAttribution(
                provider='apt',
                field_name='description',
                value='Test description',
                confidence=0.9
            )
        ]
        
        confidence = self.quality_assessment.calculate_field_confidence(
            'description',
            'Test description',
            sources
        )
        
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # Should have reasonable confidence
    
    def test_calculate_field_confidence_multiple_sources_agreement(self):
        """Test confidence calculation with multiple agreeing sources."""
        sources = [
            SourceAttribution(
                provider='apt',
                field_name='description',
                value='Test description',
                confidence=0.9
            ),
            SourceAttribution(
                provider='brew',
                field_name='description',
                value='Test description',
                confidence=0.8
            )
        ]
        
        confidence = self.quality_assessment.calculate_field_confidence(
            'description',
            'Test description',
            sources
        )
        
        assert 0.0 <= confidence <= 1.0
        # Should have higher confidence due to agreement
        single_source_confidence = self.quality_assessment.calculate_field_confidence(
            'description',
            'Test description',
            sources[:1]
        )
        assert confidence >= single_source_confidence
    
    def test_calculate_field_confidence_multiple_sources_disagreement(self):
        """Test confidence calculation with disagreeing sources."""
        sources = [
            SourceAttribution(
                provider='apt',
                field_name='description',
                value='Test description',
                confidence=0.9
            ),
            SourceAttribution(
                provider='brew',
                field_name='description',
                value='Different description',
                confidence=0.8
            )
        ]
        
        confidence = self.quality_assessment.calculate_field_confidence(
            'description',
            'Test description',
            sources
        )
        
        assert 0.0 <= confidence <= 1.0
        # Should have lower confidence due to disagreement
        assert confidence < 0.9
    
    def test_assess_description_quality_good(self):
        """Test description quality assessment with good description."""
        description = "A high-performance HTTP server and reverse proxy server."
        
        quality = self.quality_assessment._assess_description_quality(
            description,
            self.sample_source_data
        )
        
        assert isinstance(quality, FieldQuality)
        assert quality.field_name == 'description'
        assert quality.value == description
        assert 0.0 <= quality.confidence_score <= 1.0
        assert 0.0 <= quality.quality_score <= 1.0
        assert isinstance(quality.sources, list)
        assert isinstance(quality.issues, list)
        assert isinstance(quality.recommendations, list)
    
    def test_assess_description_quality_poor(self):
        """Test description quality assessment with poor description."""
        description = "nginx"  # Very short description
        
        quality = self.quality_assessment._assess_description_quality(
            description,
            self.sample_source_data
        )
        
        assert isinstance(quality, FieldQuality)
        assert quality.quality_score < 0.7  # Should be low quality
        assert len(quality.issues) > 0  # Should have issues
        assert any("short" in issue.lower() for issue in quality.issues)
    
    def test_assess_license_quality_standard(self):
        """Test license quality assessment with standard license."""
        license_value = "MIT"
        
        quality = self.quality_assessment._assess_license_quality(
            license_value,
            self.sample_source_data
        )
        
        assert isinstance(quality, FieldQuality)
        assert quality.field_name == 'license'
        assert quality.value == license_value
        assert quality.quality_score > 0.7  # Should be high quality for standard license
    
    def test_assess_license_quality_non_standard(self):
        """Test license quality assessment with non-standard license."""
        license_value = "Custom License"
        
        quality = self.quality_assessment._assess_license_quality(
            license_value,
            self.sample_source_data
        )
        
        assert isinstance(quality, FieldQuality)
        assert quality.quality_score < 0.8  # Should be lower quality
        assert len(quality.issues) > 0  # Should have issues
    
    def test_assess_platforms_quality_complete(self):
        """Test platforms quality assessment with complete platform list."""
        platforms = ["linux", "windows", "macos"]
        
        quality = self.quality_assessment._assess_platforms_quality(
            platforms,
            self.sample_source_data
        )
        
        assert isinstance(quality, FieldQuality)
        assert quality.field_name == 'platforms'
        assert quality.value == platforms
        assert quality.quality_score > 0.7  # Should be good quality
    
    def test_assess_platforms_quality_empty(self):
        """Test platforms quality assessment with empty platform list."""
        platforms = []
        
        quality = self.quality_assessment._assess_platforms_quality(
            platforms,
            self.sample_source_data
        )
        
        assert isinstance(quality, FieldQuality)
        assert quality.quality_score < 0.5  # Should be low quality
        assert len(quality.issues) > 0  # Should have issues
        assert any("no platforms" in issue.lower() for issue in quality.issues)
    
    def test_assess_urls_quality_complete(self):
        """Test URLs quality assessment with complete URLs."""
        urls = URLConfig(
            website="https://nginx.org",
            source="https://github.com/nginx/nginx",
            documentation="https://nginx.org/en/docs/"
        )
        
        quality = self.quality_assessment._assess_urls_quality(
            urls,
            self.sample_source_data
        )
        
        assert isinstance(quality, FieldQuality)
        assert quality.field_name == 'urls'
        assert quality.quality_score > 0.7  # Should be good quality
    
    def test_assess_urls_quality_invalid(self):
        """Test URLs quality assessment with invalid URLs."""
        urls = URLConfig(
            website="not-a-url",
            source="also-not-a-url"
        )
        
        quality = self.quality_assessment._assess_urls_quality(
            urls,
            self.sample_source_data
        )
        
        assert isinstance(quality, FieldQuality)
        assert quality.quality_score < 0.5  # Should be low quality
        assert len(quality.issues) > 0  # Should have issues
    
    def test_cross_reference_package_names_agreement(self):
        """Test cross-reference validation with agreeing package names."""
        result = self.quality_assessment._cross_reference_package_names(
            self.sample_source_data
        )
        
        assert isinstance(result, CrossReferenceResult)
        assert result.field_name == 'package_names'
        assert result.consensus_value == 'nginx'
        assert result.consensus_confidence > 0.8  # All sources agree
        assert len(result.conflicts) == 0  # No conflicts
        assert result.agreement_score == 1.0  # Perfect agreement
    
    def test_cross_reference_package_names_conflict(self):
        """Test cross-reference validation with conflicting package names."""
        conflicting_data = {
            'apt': [PackageInfo(name='nginx', provider='apt')],
            'brew': [PackageInfo(name='nginx-full', provider='brew')]
        }
        
        result = self.quality_assessment._cross_reference_package_names(
            conflicting_data
        )
        
        assert isinstance(result, CrossReferenceResult)
        assert len(result.conflicts) > 0  # Should have conflicts
        assert result.agreement_score < 1.0  # Not perfect agreement
    
    def test_cross_reference_descriptions(self):
        """Test cross-reference validation for descriptions."""
        result = self.quality_assessment._cross_reference_descriptions(
            self.sample_source_data
        )
        
        assert isinstance(result, CrossReferenceResult)
        assert result.field_name == 'descriptions'
        assert result.consensus_value is not None
        assert 0.0 <= result.consensus_confidence <= 1.0
        assert 0.0 <= result.agreement_score <= 1.0
    
    def test_cross_reference_versions(self):
        """Test cross-reference validation for versions."""
        result = self.quality_assessment._cross_reference_versions(
            self.sample_source_data
        )
        
        assert isinstance(result, CrossReferenceResult)
        assert result.field_name == 'versions'
        assert result.consensus_value is not None
        assert 0.0 <= result.consensus_confidence <= 1.0
    
    def test_calculate_source_reliability(self):
        """Test source reliability calculation."""
        reliability = self.quality_assessment._calculate_source_reliability(
            self.sample_source_data
        )
        
        assert isinstance(reliability, dict)
        assert all(provider in reliability for provider in self.sample_source_data.keys())
        assert all(0.0 <= score <= 1.0 for score in reliability.values())
        
        # APT should have high reliability
        assert reliability['apt'] > 0.8
    
    def test_calculate_data_freshness(self):
        """Test data freshness calculation."""
        freshness = self.quality_assessment._calculate_data_freshness(
            self.sample_source_data
        )
        
        assert isinstance(freshness, dict)
        assert all(provider in freshness for provider in self.sample_source_data.keys())
        assert all(0.0 <= score <= 1.0 for score in freshness.values())
    
    def test_identify_consistency_issues(self):
        """Test consistency issue identification."""
        # Create cross-reference results with conflicts
        cross_ref_results = {
            'package_names': CrossReferenceResult(
                field_name='package_names',
                values={'apt': 'nginx', 'brew': 'nginx-full'},
                consensus_value='nginx',
                consensus_confidence=0.5,
                conflicts=[('apt', 'brew', 'nginx', 'nginx-full')],
                agreement_score=0.5
            )
        }
        
        issues = self.quality_assessment._identify_consistency_issues(
            cross_ref_results
        )
        
        assert isinstance(issues, list)
        assert len(issues) > 0
        assert any("conflict" in issue.lower() for issue in issues)
    
    def test_generate_recommendations(self):
        """Test recommendation generation."""
        field_qualities = {
            'description': FieldQuality(
                field_name='description',
                value='Short desc',
                confidence_score=0.5,
                quality_score=0.4,
                recommendations=['Expand description']
            )
        }
        
        cross_ref_results = {}
        consistency_issues = ['Some consistency issue']
        
        recommendations = self.quality_assessment._generate_recommendations(
            field_qualities,
            cross_ref_results,
            consistency_issues
        )
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert any("description" in rec.lower() for rec in recommendations)
    
    def test_validate_license_format_standard(self):
        """Test license format validation with standard licenses."""
        assert self.quality_assessment._validate_license_format('MIT') == 1.0
        assert self.quality_assessment._validate_license_format('Apache-2.0') == 1.0
        assert self.quality_assessment._validate_license_format('GPL-3.0') == 1.0
    
    def test_validate_license_format_pattern(self):
        """Test license format validation with pattern matching."""
        score = self.quality_assessment._validate_license_format('MIT License')
        assert 0.7 <= score <= 0.9  # Should match pattern but not exact
    
    def test_validate_license_format_unknown(self):
        """Test license format validation with unknown license."""
        score = self.quality_assessment._validate_license_format('Unknown License')
        assert score < 0.5  # Should be low score
    
    def test_text_similarity(self):
        """Test text similarity calculation."""
        text1 = "High-performance HTTP server"
        text2 = "HTTP server with high performance"
        text3 = "Database management system"
        
        # Similar texts should have reasonable similarity
        similarity1 = self.quality_assessment._text_similarity(text1, text2)
        assert similarity1 > 0.4
        
        # Different texts should have low similarity
        similarity2 = self.quality_assessment._text_similarity(text1, text3)
        assert similarity2 < 0.3
        
        # Identical texts should have perfect similarity
        similarity3 = self.quality_assessment._text_similarity(text1, text1)
        assert similarity3 == 1.0
    
    def test_normalize_license(self):
        """Test license normalization."""
        assert self.quality_assessment._normalize_license('MIT License') == 'MIT'
        assert self.quality_assessment._normalize_license('Apache License 2.0') == 'Apache-2.0'
        assert self.quality_assessment._normalize_license('GPL v3') == 'GPL-3.0'
        assert self.quality_assessment._normalize_license('BSD License') == 'BSD'
        assert self.quality_assessment._normalize_license('Custom License') == 'Custom License'
    
    def test_infer_platforms_from_provider(self):
        """Test platform inference from provider."""
        assert 'linux' in self.quality_assessment._infer_platforms_from_provider('apt')
        assert 'windows' in self.quality_assessment._infer_platforms_from_provider('winget')
        assert 'macos' in self.quality_assessment._infer_platforms_from_provider('brew')
        assert self.quality_assessment._infer_platforms_from_provider('unknown') == []
    
    def test_version_sort_key(self):
        """Test version sorting key generation."""
        key1 = self.quality_assessment._version_sort_key('1.2.3')
        key2 = self.quality_assessment._version_sort_key('1.2.10')
        key3 = self.quality_assessment._version_sort_key('2.0.0')
        
        assert key1 == (1, 2, 3)
        assert key2 == (1, 2, 10)
        assert key3 == (2, 0, 0)
        
        # Test ordering
        assert key1 < key2 < key3
    
    def test_versions_compatible(self):
        """Test version compatibility checking."""
        assert self.quality_assessment._versions_compatible('1.2.3', '1.3.0')  # Same major
        assert not self.quality_assessment._versions_compatible('1.2.3', '2.0.0')  # Different major
        assert self.quality_assessment._versions_compatible('invalid', 'also-invalid')  # Invalid versions
    
    def test_find_latest_version(self):
        """Test finding latest version from list."""
        versions = ['1.2.3', '1.10.0', '2.0.0', '1.2.10']
        latest = self.quality_assessment._find_latest_version(versions)
        assert latest == '2.0.0'
        
        # Test empty list
        assert self.quality_assessment._find_latest_version([]) == ""
    
    def test_assess_metadata_quality_empty_metadata(self):
        """Test quality assessment with minimal metadata."""
        minimal_metadata = SaidataMetadata(version="0.1")
        
        report = self.quality_assessment.assess_metadata_quality(
            minimal_metadata,
            {},
            "test-software"
        )
        
        assert isinstance(report, QualityReport)
        assert report.overall_quality_score <= 0.5  # Should be low quality
        assert len(report.recommendations) > 0  # Should have recommendations
    
    def test_assess_metadata_quality_high_quality(self):
        """Test quality assessment with high-quality metadata."""
        report = self.quality_assessment.assess_metadata_quality(
            self.sample_metadata,
            self.sample_source_data,
            "nginx"
        )
        
        assert isinstance(report, QualityReport)
        assert report.overall_quality_score > 0.6  # Should be reasonable quality
        assert report.overall_confidence_score > 0.4  # Should have reasonable confidence
    
    def test_field_quality_dataclass(self):
        """Test FieldQuality dataclass functionality."""
        quality = FieldQuality(
            field_name='test',
            value='test_value',
            confidence_score=0.8,
            quality_score=0.9
        )
        
        assert quality.field_name == 'test'
        assert quality.value == 'test_value'
        assert quality.confidence_score == 0.8
        assert quality.quality_score == 0.9
        assert isinstance(quality.sources, list)
        assert isinstance(quality.issues, list)
        assert isinstance(quality.recommendations, list)
    
    def test_source_attribution_dataclass(self):
        """Test SourceAttribution dataclass functionality."""
        attribution = SourceAttribution(
            provider='apt',
            field_name='description',
            value='Test description',
            confidence=0.9
        )
        
        assert attribution.provider == 'apt'
        assert attribution.field_name == 'description'
        assert attribution.value == 'Test description'
        assert attribution.confidence == 0.9
        assert attribution.timestamp is None
        assert attribution.source_url is None
    
    def test_cross_reference_result_dataclass(self):
        """Test CrossReferenceResult dataclass functionality."""
        result = CrossReferenceResult(
            field_name='test_field',
            values={'provider1': 'value1', 'provider2': 'value2'},
            consensus_value='value1',
            consensus_confidence=0.8,
            conflicts=[],
            agreement_score=1.0
        )
        
        assert result.field_name == 'test_field'
        assert result.values == {'provider1': 'value1', 'provider2': 'value2'}
        assert result.consensus_value == 'value1'
        assert result.consensus_confidence == 0.8
        assert result.conflicts == []
        assert result.agreement_score == 1.0
    
    def test_quality_report_dataclass(self):
        """Test QualityReport dataclass functionality."""
        report = QualityReport(
            software_name='test-software',
            overall_quality_score=0.8,
            overall_confidence_score=0.7
        )
        
        assert report.software_name == 'test-software'
        assert report.overall_quality_score == 0.8
        assert report.overall_confidence_score == 0.7
        assert isinstance(report.field_qualities, dict)
        assert isinstance(report.cross_reference_results, dict)
        assert isinstance(report.source_reliability, dict)
        assert isinstance(report.recommendations, list)
        assert isinstance(report.generation_timestamp, datetime)


class TestQualityAssessmentIntegration:
    """Integration tests for quality assessment system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.quality_assessment = QualityAssessment()
    
    def test_end_to_end_quality_assessment(self):
        """Test complete end-to-end quality assessment workflow."""
        # Create comprehensive test data
        source_data = {
            'apt': [
                PackageInfo(
                    name='nginx',
                    provider='apt',
                    version='1.18.0',
                    description='High-performance HTTP server and reverse proxy'
                )
            ],
            'brew': [
                PackageInfo(
                    name='nginx',
                    provider='brew',
                    version='1.19.0',
                    description='HTTP server and reverse proxy'
                )
            ]
        }
        
        metadata = SaidataMetadata(
            version="0.1",
            description="High-performance HTTP server and reverse proxy",
            license="BSD-2-Clause",
            platforms=["linux", "macos"],
            urls=URLConfig(website="https://nginx.org"),
            category=CategoryConfig(default="web"),
            packages={'apt': {'name': 'nginx'}, 'brew': {'name': 'nginx'}}
        )
        
        # Perform quality assessment
        report = self.quality_assessment.assess_metadata_quality(
            metadata,
            source_data,
            "nginx"
        )
        
        # Verify comprehensive report
        assert isinstance(report, QualityReport)
        assert report.software_name == "nginx"
        assert 0.0 <= report.overall_quality_score <= 1.0
        assert 0.0 <= report.overall_confidence_score <= 1.0
        
        # Verify field qualities
        assert 'description' in report.field_qualities
        assert 'license' in report.field_qualities
        assert 'platforms' in report.field_qualities
        assert 'urls' in report.field_qualities
        assert 'category' in report.field_qualities
        assert 'packages' in report.field_qualities
        
        # Verify cross-reference results
        assert 'package_names' in report.cross_reference_results
        assert 'descriptions' in report.cross_reference_results
        assert 'versions' in report.cross_reference_results
        
        # Verify source reliability
        assert 'apt' in report.source_reliability
        assert 'brew' in report.source_reliability
        
        # Verify recommendations exist
        assert isinstance(report.recommendations, list)
        
        # Verify timestamp
        assert isinstance(report.generation_timestamp, datetime)
    
    def test_quality_assessment_with_conflicts(self):
        """Test quality assessment with conflicting source data."""
        source_data = {
            'apt': [
                PackageInfo(
                    name='nginx',
                    provider='apt',
                    version='1.18.0',
                    description='HTTP server'
                )
            ],
            'brew': [
                PackageInfo(
                    name='nginx-full',  # Different name
                    provider='brew',
                    version='2.0.0',    # Very different version
                    description='Web server software'  # Different description
                )
            ]
        }
        
        metadata = SaidataMetadata(
            version="0.1",
            description="HTTP server",
            packages={'apt': {'name': 'nginx'}, 'brew': {'name': 'nginx-full'}}
        )
        
        report = self.quality_assessment.assess_metadata_quality(
            metadata,
            source_data,
            "nginx"
        )
        
        # Should detect conflicts
        assert len(report.consistency_issues) > 0
        assert any("conflict" in issue.lower() for issue in report.consistency_issues)
        
        # Cross-reference should show conflicts
        package_names_result = report.cross_reference_results.get('package_names')
        if isinstance(package_names_result, CrossReferenceResult):
            assert len(package_names_result.conflicts) > 0
            assert package_names_result.agreement_score < 1.0
    
    def test_quality_assessment_performance(self):
        """Test quality assessment performance with larger dataset."""
        # Create larger source data
        providers = ['apt', 'brew', 'npm', 'pypi', 'docker']
        source_data = {}
        
        for provider in providers:
            source_data[provider] = [
                PackageInfo(
                    name=f'test-package-{provider}',
                    provider=provider,
                    version='1.0.0',
                    description=f'Test package from {provider}'
                )
            ]
        
        metadata = SaidataMetadata(
            version="0.1",
            description="Test package",
            packages={provider: {'name': f'test-package-{provider}'} for provider in providers}
        )
        
        # Should complete in reasonable time
        import time
        start_time = time.time()
        
        report = self.quality_assessment.assess_metadata_quality(
            metadata,
            source_data,
            "test-package"
        )
        
        end_time = time.time()
        
        # Should complete within 5 seconds (generous for CI)
        assert end_time - start_time < 5.0
        
        # Should still produce valid report
        assert isinstance(report, QualityReport)
        assert len(report.field_qualities) > 0
        assert len(report.source_reliability) == len(providers)


if __name__ == '__main__':
    pytest.main([__file__])