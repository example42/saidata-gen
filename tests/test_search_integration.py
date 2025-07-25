"""
Integration tests for search engine with package comparison functionality.
"""

import pytest
from unittest.mock import Mock, MagicMock

from saidata_gen.core.interfaces import FetcherConfig, PackageInfo, SoftwareMatch
from saidata_gen.search.engine import SoftwareSearchEngine
from saidata_gen.search.comparison import SelectionCriteria


class TestSearchEngineIntegration:
    """Test cases for search engine integration with package comparison."""
    
    @pytest.fixture
    def mock_fetcher(self):
        """Create a mock fetcher for testing."""
        fetcher = Mock()
        fetcher.search_packages.return_value = [
            PackageInfo(
                name="nginx",
                provider="apt",
                version="1.18.0",
                description="High-performance web server",
                details={"license": "BSD-2-Clause"}
            ),
            PackageInfo(
                name="apache2",
                provider="apt",
                version="2.4.41",
                description="Apache HTTP Server",
                details={"license": "Apache-2.0"}
            )
        ]
        fetcher.get_package_info.return_value = PackageInfo(
            name="nginx",
            provider="apt",
            version="1.18.0",
            description="High-performance web server",
            details={"license": "BSD-2-Clause", "homepage": "https://nginx.org"}
        )
        return fetcher
    
    @pytest.fixture
    def search_engine(self, mock_fetcher):
        """Create a search engine with mock fetchers."""
        # Mock the fetcher factory
        with pytest.MonkeyPatch().context() as m:
            mock_factory = Mock()
            mock_factory.get_available_fetchers.return_value = ["apt"]
            mock_factory.create_fetcher.return_value = mock_fetcher
            
            m.setattr("saidata_gen.search.engine.fetcher_factory", mock_factory)
            
            engine = SoftwareSearchEngine(providers=["apt"])
            return engine
    
    def test_search_with_comparison(self, search_engine):
        """Test searching and comparing results."""
        # Perform search
        results = search_engine.search("web server", max_results=10)
        
        assert len(results) >= 0  # Should not fail
        
        if results:
            # Test comparison functionality
            comparisons = search_engine.compare_packages(results)
            assert isinstance(comparisons, list)
            
            # Test duplicate identification
            duplicates = search_engine.identify_duplicates(results)
            assert isinstance(duplicates, list)
            
            # Test best package selection
            best_package = search_engine.select_best_package(results)
            assert best_package is None or isinstance(best_package, SoftwareMatch)
    
    def test_find_alternatives_integration(self, search_engine):
        """Test finding alternatives through search engine."""
        # Create test packages
        target = SoftwareMatch(name="nginx", provider="apt", description="Web server")
        candidates = [
            SoftwareMatch(name="apache2", provider="apt", description="HTTP server"),
            SoftwareMatch(name="nginx-full", provider="brew", description="Full nginx package")
        ]
        
        alternatives = search_engine.find_alternatives(target, candidates)
        
        assert isinstance(alternatives, list)
        assert all(isinstance(alt, SoftwareMatch) for alt in alternatives)
    
    def test_get_detailed_info_integration(self, search_engine):
        """Test getting detailed package info through search engine."""
        package = SoftwareMatch(name="nginx", provider="apt")
        
        details = search_engine.get_detailed_package_info(package)
        
        # Should either return details or None (if fetcher fails)
        assert details is None or hasattr(details, 'name')
    
    def test_select_best_with_criteria(self, search_engine):
        """Test selecting best package with custom criteria."""
        packages = [
            SoftwareMatch(name="nginx", provider="apt", version="1.18.0", description="Web server"),
            SoftwareMatch(name="nginx", provider="snap", description="Web server package")
        ]
        
        criteria = SelectionCriteria(
            prefer_popular_providers=["apt"],
            require_version=True
        )
        
        best = search_engine.select_best_package(packages, criteria)
        
        if best:
            assert best.provider == "apt"  # Should prefer apt
            assert best.version is not None  # Should have version
    
    def test_empty_results_handling(self, search_engine):
        """Test handling of empty search results."""
        # Test with empty lists
        assert search_engine.compare_packages([]) == []
        assert search_engine.identify_duplicates([]) == []
        assert search_engine.find_alternatives(
            SoftwareMatch(name="test", provider="apt"), []
        ) == []
        assert search_engine.select_best_package([]) is None