"""
Unit tests for package comparison and selection system.
"""

import pytest
from unittest.mock import Mock, MagicMock

from saidata_gen.core.interfaces import PackageDetails, PackageInfo, SoftwareMatch
from saidata_gen.search.comparison import (
    PackageComparator, PackageComparison, PackageGroup, SelectionCriteria
)


class TestPackageComparator:
    """Test cases for PackageComparator."""
    
    @pytest.fixture
    def mock_fetchers(self):
        """Create mock fetchers for testing."""
        apt_fetcher = Mock()
        brew_fetcher = Mock()
        npm_fetcher = Mock()
        
        return {
            "apt": apt_fetcher,
            "brew": brew_fetcher,
            "npm": npm_fetcher
        }
    
    @pytest.fixture
    def comparator(self, mock_fetchers):
        """Create a PackageComparator instance for testing."""
        return PackageComparator(mock_fetchers)
    
    @pytest.fixture
    def sample_packages(self):
        """Create sample packages for testing."""
        return [
            SoftwareMatch(
                name="nginx",
                provider="apt",
                version="1.18.0",
                description="High-performance web server and reverse proxy",
                score=0.9
            ),
            SoftwareMatch(
                name="nginx",
                provider="brew",
                version="1.21.0",
                description="HTTP and reverse proxy server",
                score=0.8
            ),
            SoftwareMatch(
                name="apache2",
                provider="apt",
                version="2.4.41",
                description="Apache HTTP Server",
                score=0.7
            ),
            SoftwareMatch(
                name="httpd",
                provider="brew",
                version="2.4.54",
                description="Apache HTTP Server",
                score=0.6
            )
        ]
    
    def test_compare_packages_empty_list(self, comparator):
        """Test comparing empty package list."""
        result = comparator.compare_packages([])
        assert result == []
    
    def test_compare_packages_single_package(self, comparator, sample_packages):
        """Test comparing single package."""
        result = comparator.compare_packages([sample_packages[0]])
        assert len(result) == 0  # No comparisons for single package
    
    def test_compare_packages_multiple(self, comparator, sample_packages):
        """Test comparing multiple packages."""
        result = comparator.compare_packages(sample_packages)
        
        assert len(result) >= 1
        assert all(isinstance(comp, PackageComparison) for comp in result)
        
        # Check that each comparison has a primary package and alternatives
        for comp in result:
            assert comp.primary_package is not None
            assert isinstance(comp.alternative_packages, list)
            assert isinstance(comp.similarity_scores, dict)
            assert isinstance(comp.common_features, list)
            assert isinstance(comp.differences, dict)
            assert 0 <= comp.recommendation_score <= 1
            assert isinstance(comp.recommendation_reason, str)
    
    def test_identify_duplicates_exact_match(self, comparator):
        """Test identifying exact duplicate packages."""
        packages = [
            SoftwareMatch(name="nginx", provider="apt", description="Web server"),
            SoftwareMatch(name="nginx", provider="brew", description="Web server"),
            SoftwareMatch(name="apache", provider="apt", description="HTTP server")
        ]
        
        duplicates = comparator.identify_duplicates(packages, similarity_threshold=0.8)
        
        assert len(duplicates) == 1
        assert duplicates[0].group_type == "duplicate"
        assert len(duplicates[0].packages) == 2
        assert duplicates[0].canonical_name == "nginx"
    
    def test_identify_duplicates_no_duplicates(self, comparator):
        """Test identifying duplicates when none exist."""
        packages = [
            SoftwareMatch(name="nginx", provider="apt", description="Web server"),
            SoftwareMatch(name="apache", provider="apt", description="HTTP server"),
            SoftwareMatch(name="mysql", provider="apt", description="Database server")
        ]
        
        duplicates = comparator.identify_duplicates(packages, similarity_threshold=0.9)
        
        assert len(duplicates) == 0
    
    def test_find_alternatives(self, comparator):
        """Test finding alternative packages."""
        target = SoftwareMatch(name="nginx", provider="apt", description="Web server")
        candidates = [
            SoftwareMatch(name="apache2", provider="apt", description="Web server HTTP"),
            SoftwareMatch(name="nginx-full", provider="brew", description="Web server nginx"),
            SoftwareMatch(name="mysql", provider="apt", description="Database server")
        ]
        
        alternatives = comparator.find_alternatives(target, candidates, similarity_threshold=0.2)
        
        # Should find web servers as alternatives, but not database server
        assert len(alternatives) >= 1  # Should find at least nginx-full
        assert all(alt.score >= 0.2 for alt in alternatives)
        if len(alternatives) > 1:
            assert alternatives[0].score >= alternatives[-1].score  # Should be sorted by score
    
    def test_select_best_package_empty_list(self, comparator):
        """Test selecting best package from empty list."""
        result = comparator.select_best_package([])
        assert result is None
    
    def test_select_best_package_single(self, comparator, sample_packages):
        """Test selecting best package from single package."""
        result = comparator.select_best_package([sample_packages[0]])
        assert result == sample_packages[0]
    
    def test_select_best_package_multiple(self, comparator, sample_packages):
        """Test selecting best package from multiple packages."""
        result = comparator.select_best_package(sample_packages)
        
        assert result is not None
        assert result in sample_packages
        # Should prefer popular providers (apt, brew over others)
        assert result.provider in ["apt", "brew"]
    
    def test_select_best_package_with_criteria(self, comparator, sample_packages):
        """Test selecting best package with specific criteria."""
        criteria = SelectionCriteria(
            prefer_popular_providers=["brew"],
            require_version=True,
            minimum_description_length=10
        )
        
        result = comparator.select_best_package(sample_packages, criteria)
        
        assert result is not None
        assert result.version is not None
        assert len(result.description or "") >= 10
    
    def test_get_detailed_package_info_success(self, comparator, mock_fetchers):
        """Test getting detailed package info successfully."""
        package = SoftwareMatch(name="nginx", provider="apt")
        
        # Mock the fetcher response
        mock_package_info = PackageInfo(
            name="nginx",
            provider="apt",
            version="1.18.0",
            description="Web server",
            details={
                "license": "BSD-2-Clause",
                "homepage": "https://nginx.org",
                "dependencies": ["libc6", "libssl1.1"],
                "maintainer": "Debian Nginx Maintainers"
            }
        )
        mock_fetchers["apt"].get_package_info.return_value = mock_package_info
        
        result = comparator.get_detailed_package_info(package)
        
        assert result is not None
        assert isinstance(result, PackageDetails)
        assert result.name == "nginx"
        assert result.provider == "apt"
        assert result.version == "1.18.0"
        assert result.license == "BSD-2-Clause"
        assert result.homepage == "https://nginx.org"
        assert result.dependencies == ["libc6", "libssl1.1"]
        assert result.maintainer == "Debian Nginx Maintainers"
    
    def test_get_detailed_package_info_not_found(self, comparator, mock_fetchers):
        """Test getting detailed package info when package not found."""
        package = SoftwareMatch(name="nonexistent", provider="apt")
        
        mock_fetchers["apt"].get_package_info.return_value = None
        
        result = comparator.get_detailed_package_info(package)
        
        assert result is None
    
    def test_get_detailed_package_info_no_fetcher(self, comparator):
        """Test getting detailed package info when fetcher not available."""
        package = SoftwareMatch(name="nginx", provider="unknown")
        
        result = comparator.get_detailed_package_info(package)
        
        assert result is None
    
    def test_calculate_package_similarity_identical(self, comparator):
        """Test calculating similarity for identical packages."""
        package1 = SoftwareMatch(name="nginx", provider="apt", description="Web server")
        package2 = SoftwareMatch(name="nginx", provider="apt", description="Web server")
        
        similarity = comparator._calculate_package_similarity(package1, package2)
        
        assert similarity > 0.9  # Should be very high for identical packages
    
    def test_calculate_package_similarity_different(self, comparator):
        """Test calculating similarity for different packages."""
        package1 = SoftwareMatch(name="nginx", provider="apt", description="Web server")
        package2 = SoftwareMatch(name="mysql", provider="apt", description="Database server")
        
        similarity = comparator._calculate_package_similarity(package1, package2)
        
        assert similarity < 0.5  # Should be low for different packages
    
    def test_calculate_package_similarity_similar_names(self, comparator):
        """Test calculating similarity for packages with similar names."""
        package1 = SoftwareMatch(name="nginx", provider="apt", description="Web server")
        package2 = SoftwareMatch(name="nginx-full", provider="apt", description="Full nginx package")
        
        similarity = comparator._calculate_package_similarity(package1, package2)
        
        assert 0.3 < similarity < 0.9  # Should be moderate for similar names
    
    def test_filter_packages_exclude_providers(self, comparator, sample_packages):
        """Test filtering packages by excluding providers."""
        criteria = SelectionCriteria(exclude_providers=["brew"])
        
        filtered = comparator._filter_packages(sample_packages, criteria)
        
        assert all(pkg.provider != "brew" for pkg in filtered)
        assert len(filtered) < len(sample_packages)
    
    def test_filter_packages_include_providers(self, comparator, sample_packages):
        """Test filtering packages by including only specific providers."""
        criteria = SelectionCriteria(include_providers=["apt"])
        
        filtered = comparator._filter_packages(sample_packages, criteria)
        
        assert all(pkg.provider == "apt" for pkg in filtered)
    
    def test_filter_packages_require_version(self, comparator, sample_packages):
        """Test filtering packages that require version."""
        criteria = SelectionCriteria(require_version=True)
        
        filtered = comparator._filter_packages(sample_packages, criteria)
        
        assert all(pkg.version is not None for pkg in filtered)
    
    def test_filter_packages_minimum_description_length(self, comparator, sample_packages):
        """Test filtering packages by minimum description length."""
        criteria = SelectionCriteria(minimum_description_length=30)
        
        filtered = comparator._filter_packages(sample_packages, criteria)
        
        assert all(
            pkg.description is None or len(pkg.description) >= 30
            for pkg in filtered
        )
    
    def test_calculate_selection_score(self, comparator):
        """Test calculating selection score for packages."""
        package = SoftwareMatch(
            name="nginx",
            provider="apt",  # Popular provider
            version="1.18.0",
            description="High-performance web server and reverse proxy server",
            score=0.8
        )
        criteria = SelectionCriteria()
        
        score = comparator._calculate_selection_score(package, criteria)
        
        assert 0 <= score <= 1
        assert score > 0.5  # Should be high for good package
    
    def test_get_canonical_name(self, comparator):
        """Test getting canonical name for package group."""
        packages = [
            SoftwareMatch(name="nginx", provider="apt"),
            SoftwareMatch(name="nginx", provider="brew"),
            SoftwareMatch(name="nginx-full", provider="snap")
        ]
        
        canonical = comparator._get_canonical_name(packages)
        
        assert canonical == "nginx"  # Should prefer name from popular provider
    
    def test_analyze_package_features(self, comparator):
        """Test analyzing package features."""
        packages = [
            SoftwareMatch(name="nginx", provider="apt", version="1.18.0", description="Web server"),
            SoftwareMatch(name="nginx", provider="brew", version="1.21.0", description="HTTP server")
        ]
        
        common_features, differences = comparator._analyze_package_features(packages)
        
        assert "Same name" in common_features
        assert "versions" in differences
        assert "providers" in differences
        assert set(differences["providers"]) == {"apt", "brew"}
    
    def test_calculate_recommendation(self, comparator):
        """Test calculating recommendation score and reason."""
        primary = SoftwareMatch(name="nginx", provider="apt", version="1.18.0", 
                               description="High-performance web server")
        alternatives = [
            SoftwareMatch(name="nginx", provider="snap", description="Web server")
        ]
        criteria = SelectionCriteria()
        
        score, reason = comparator._calculate_recommendation(primary, alternatives, criteria)
        
        assert 0 <= score <= 1
        assert isinstance(reason, str)
        assert len(reason) > 0


class TestSelectionCriteria:
    """Test cases for SelectionCriteria."""
    
    def test_default_criteria(self):
        """Test default selection criteria."""
        criteria = SelectionCriteria()
        
        assert criteria.prefer_official is True
        assert criteria.prefer_latest_version is True
        assert "apt" in criteria.prefer_popular_providers
        assert "brew" in criteria.prefer_popular_providers
        assert criteria.minimum_description_length == 20
        assert criteria.require_version is False
        assert criteria.exclude_providers == []
        assert criteria.include_providers == []
    
    def test_custom_criteria(self):
        """Test custom selection criteria."""
        criteria = SelectionCriteria(
            prefer_official=False,
            prefer_latest_version=False,
            prefer_popular_providers=["npm"],
            minimum_description_length=50,
            require_version=True,
            exclude_providers=["snap"],
            include_providers=["apt", "brew"]
        )
        
        assert criteria.prefer_official is False
        assert criteria.prefer_latest_version is False
        assert criteria.prefer_popular_providers == ["npm"]
        assert criteria.minimum_description_length == 50
        assert criteria.require_version is True
        assert criteria.exclude_providers == ["snap"]
        assert criteria.include_providers == ["apt", "brew"]


class TestPackageComparison:
    """Test cases for PackageComparison dataclass."""
    
    def test_package_comparison_creation(self):
        """Test creating PackageComparison instance."""
        primary = SoftwareMatch(name="nginx", provider="apt")
        alternatives = [SoftwareMatch(name="nginx", provider="brew")]
        
        comparison = PackageComparison(
            primary_package=primary,
            alternative_packages=alternatives,
            similarity_scores={"brew:nginx": 0.9},
            common_features=["Same name"],
            differences={"providers": ["apt", "brew"]},
            recommendation_score=0.8,
            recommendation_reason="Popular provider"
        )
        
        assert comparison.primary_package == primary
        assert comparison.alternative_packages == alternatives
        assert comparison.similarity_scores == {"brew:nginx": 0.9}
        assert comparison.common_features == ["Same name"]
        assert comparison.differences == {"providers": ["apt", "brew"]}
        assert comparison.recommendation_score == 0.8
        assert comparison.recommendation_reason == "Popular provider"


class TestPackageGroup:
    """Test cases for PackageGroup dataclass."""
    
    def test_package_group_creation(self):
        """Test creating PackageGroup instance."""
        packages = [
            SoftwareMatch(name="nginx", provider="apt"),
            SoftwareMatch(name="nginx", provider="brew")
        ]
        
        group = PackageGroup(
            canonical_name="nginx",
            packages=packages,
            group_type="duplicate",
            confidence=0.9,
            description="Duplicate nginx packages"
        )
        
        assert group.canonical_name == "nginx"
        assert group.packages == packages
        assert group.group_type == "duplicate"
        assert group.confidence == 0.9
        assert group.description == "Duplicate nginx packages"
    
    def test_package_group_defaults(self):
        """Test PackageGroup with default values."""
        group = PackageGroup(canonical_name="test")
        
        assert group.canonical_name == "test"
        assert group.packages == []
        assert group.group_type == "alternative"
        assert group.confidence == 0.0
        assert group.description == ""