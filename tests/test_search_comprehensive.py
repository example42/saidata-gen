"""
Comprehensive unit tests for search components.
"""

import unittest
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from saidata_gen.search.engine import SoftwareSearchEngine
from saidata_gen.search.fuzzy import FuzzyMatcher
from saidata_gen.search.ranking import ResultRanker
from saidata_gen.search.comparison import PackageComparator
from saidata_gen.core.interfaces import SearchOptions, SoftwareMatch, SearchResult


class TestSoftwareSearchEngine(unittest.TestCase):
    """Test the SoftwareSearchEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_fetchers = {
            "apt": Mock(),
            "brew": Mock(),
            "npm": Mock()
        }
        
        self.search_engine = SoftwareSearchEngine(self.mock_fetchers)
    
    def test_initialization(self):
        """Test search engine initialization."""
        self.assertEqual(len(self.search_engine.fetchers), 3)
        self.assertIn("apt", self.search_engine.fetchers)
        self.assertIn("brew", self.search_engine.fetchers)
        self.assertIn("npm", self.search_engine.fetchers)
    
    def test_search_single_provider(self):
        """Test searching in a single provider."""
        # Mock search results
        self.mock_fetchers["apt"].search_packages.return_value = [
            {
                "name": "nginx",
                "version": "1.18.0",
                "description": "HTTP server and reverse proxy",
                "provider": "apt"
            }
        ]
        
        options = SearchOptions(providers=["apt"], max_results=10)
        result = self.search_engine.search("nginx", options)
        
        self.assertIsInstance(result, SearchResult)
        self.assertEqual(result.query, "nginx")
        self.assertEqual(len(result.matches), 1)
        self.assertEqual(result.matches[0].name, "nginx")
        self.assertEqual(result.matches[0].provider, "apt")
        
        self.mock_fetchers["apt"].search_packages.assert_called_once_with("nginx", 10)
    
    def test_search_multiple_providers(self):
        """Test searching across multiple providers."""
        # Mock search results from different providers
        self.mock_fetchers["apt"].search_packages.return_value = [
            {
                "name": "nginx",
                "version": "1.18.0",
                "description": "HTTP server and reverse proxy",
                "provider": "apt"
            }
        ]
        
        self.mock_fetchers["brew"].search_packages.return_value = [
            {
                "name": "nginx",
                "version": "1.25.3",
                "description": "HTTP(S) server and reverse proxy",
                "provider": "brew"
            }
        ]
        
        self.mock_fetchers["npm"].search_packages.return_value = []
        
        options = SearchOptions(providers=["apt", "brew", "npm"], max_results=20)
        result = self.search_engine.search("nginx", options)
        
        self.assertEqual(len(result.matches), 2)
        self.assertEqual(len(result.providers_searched), 3)
        
        # Verify all fetchers were called
        self.mock_fetchers["apt"].search_packages.assert_called_once()
        self.mock_fetchers["brew"].search_packages.assert_called_once()
        self.mock_fetchers["npm"].search_packages.assert_called_once()
    
    def test_search_with_fuzzy_matching(self):
        """Test search with fuzzy matching enabled."""
        # Mock fuzzy matcher
        with patch('saidata_gen.search.engine.FuzzyMatcher') as mock_fuzzy_class:
            mock_fuzzy = Mock()
            mock_fuzzy_class.return_value = mock_fuzzy
            
            # Mock fuzzy search results
            mock_fuzzy.find_matches.return_value = [
                {"name": "nginx", "score": 0.95},
                {"name": "nginx-full", "score": 0.85}
            ]
            
            self.mock_fetchers["apt"].search_packages.return_value = [
                {
                    "name": "nginx",
                    "version": "1.18.0",
                    "description": "HTTP server",
                    "provider": "apt"
                },
                {
                    "name": "nginx-full",
                    "version": "1.18.0",
                    "description": "Full nginx package",
                    "provider": "apt"
                }
            ]
            
            options = SearchOptions(
                providers=["apt"],
                fuzzy_matching=True,
                confidence_threshold=0.8
            )
            result = self.search_engine.search("nginx", options)
            
            self.assertEqual(len(result.matches), 2)
            # Results should be ordered by fuzzy score
            self.assertEqual(result.matches[0].name, "nginx")
            self.assertGreater(result.matches[0].confidence, result.matches[1].confidence)
    
    def test_search_with_ranking(self):
        """Test search with result ranking."""
        # Mock search results with different relevance
        self.mock_fetchers["apt"].search_packages.return_value = [
            {
                "name": "nginx",
                "version": "1.18.0",
                "description": "HTTP server and reverse proxy",
                "provider": "apt",
                "downloads": 1000000
            },
            {
                "name": "nginx-light",
                "version": "1.18.0",
                "description": "Lightweight nginx",
                "provider": "apt",
                "downloads": 100000
            }
        ]
        
        with patch('saidata_gen.search.engine.ResultRanker') as mock_ranker_class:
            mock_ranker = Mock()
            mock_ranker_class.return_value = mock_ranker
            
            # Mock ranking that prefers exact matches and popularity
            def mock_rank(matches, query):
                return sorted(matches, key=lambda x: (
                    1.0 if x.name == query else 0.5,
                    x.metadata.get("downloads", 0)
                ), reverse=True)
            
            mock_ranker.rank_results.side_effect = mock_rank
            
            options = SearchOptions(providers=["apt"])
            result = self.search_engine.search("nginx", options)
            
            self.assertEqual(len(result.matches), 2)
            self.assertEqual(result.matches[0].name, "nginx")  # Exact match first
            self.assertEqual(result.matches[1].name, "nginx-light")
    
    def test_search_no_results(self):
        """Test search with no results."""
        self.mock_fetchers["apt"].search_packages.return_value = []
        
        options = SearchOptions(providers=["apt"])
        result = self.search_engine.search("nonexistent-package", options)
        
        self.assertEqual(len(result.matches), 0)
        self.assertEqual(result.total_found, 0)
    
    def test_search_with_error_handling(self):
        """Test search with provider errors."""
        # Mock one provider failing
        self.mock_fetchers["apt"].search_packages.side_effect = Exception("Connection error")
        self.mock_fetchers["brew"].search_packages.return_value = [
            {
                "name": "nginx",
                "version": "1.25.3",
                "description": "HTTP server",
                "provider": "brew"
            }
        ]
        
        options = SearchOptions(providers=["apt", "brew"])
        result = self.search_engine.search("nginx", options)
        
        # Should still return results from working provider
        self.assertEqual(len(result.matches), 1)
        self.assertEqual(result.matches[0].provider, "brew")
        
        # Should include error information
        self.assertIn("errors", result.metadata)
        self.assertIn("apt", result.metadata["errors"])


class TestFuzzyMatcher(unittest.TestCase):
    """Test the FuzzyMatcher class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.fuzzy_matcher = FuzzyMatcher()
    
    def test_exact_match(self):
        """Test exact string matching."""
        candidates = ["nginx", "apache2", "mysql"]
        matches = self.fuzzy_matcher.find_matches("nginx", candidates)
        
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "nginx")
        self.assertEqual(matches[0]["score"], 1.0)
    
    def test_partial_match(self):
        """Test partial string matching."""
        candidates = ["nginx", "nginx-full", "nginx-light", "apache2"]
        matches = self.fuzzy_matcher.find_matches("nginx", candidates, threshold=0.5)
        
        # Should match all nginx variants
        nginx_matches = [m for m in matches if "nginx" in m["name"]]
        self.assertEqual(len(nginx_matches), 3)
        
        # Exact match should have highest score
        exact_match = next(m for m in matches if m["name"] == "nginx")
        self.assertEqual(exact_match["score"], 1.0)
    
    def test_typo_tolerance(self):
        """Test tolerance for typos."""
        candidates = ["nginx", "apache2", "mysql", "postgresql"]
        matches = self.fuzzy_matcher.find_matches("nginz", candidates, threshold=0.7)
        
        # Should still match nginx despite typo
        self.assertGreater(len(matches), 0)
        self.assertEqual(matches[0]["name"], "nginx")
        self.assertGreater(matches[0]["score"], 0.7)
    
    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        candidates = ["Nginx", "APACHE2", "mysql"]
        matches = self.fuzzy_matcher.find_matches("nginx", candidates)
        
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "Nginx")
        self.assertGreater(matches[0]["score"], 0.9)
    
    def test_threshold_filtering(self):
        """Test filtering by confidence threshold."""
        candidates = ["nginx", "nginx-full", "apache2", "completely-different"]
        matches = self.fuzzy_matcher.find_matches("nginx", candidates, threshold=0.8)
        
        # Should only include high-confidence matches
        for match in matches:
            self.assertGreaterEqual(match["score"], 0.8)
        
        # Should not include completely different package
        names = [m["name"] for m in matches]
        self.assertNotIn("completely-different", names)
    
    def test_similarity_algorithms(self):
        """Test different similarity algorithms."""
        candidates = ["nginx", "nginx-full"]
        
        # Test with different algorithms
        for algorithm in ["levenshtein", "jaro_winkler", "token_sort"]:
            matches = self.fuzzy_matcher.find_matches(
                "nginx", candidates, algorithm=algorithm
            )
            self.assertGreater(len(matches), 0)
            self.assertEqual(matches[0]["name"], "nginx")


class TestResultRanker(unittest.TestCase):
    """Test the ResultRanker class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.ranker = ResultRanker()
    
    def test_rank_by_relevance(self):
        """Test ranking by relevance to query."""
        matches = [
            SoftwareMatch(
                name="nginx-light",
                provider="apt",
                description="Lightweight nginx",
                confidence=0.8
            ),
            SoftwareMatch(
                name="nginx",
                provider="apt", 
                description="HTTP server and reverse proxy",
                confidence=0.9
            ),
            SoftwareMatch(
                name="nginx-full",
                provider="apt",
                description="Full nginx package",
                confidence=0.85
            )
        ]
        
        ranked = self.ranker.rank_results(matches, "nginx")
        
        # Exact match should be first
        self.assertEqual(ranked[0].name, "nginx")
        # Should be ordered by relevance/confidence
        for i in range(len(ranked) - 1):
            self.assertGreaterEqual(ranked[i].confidence, ranked[i + 1].confidence)
    
    def test_rank_by_popularity(self):
        """Test ranking by package popularity."""
        matches = [
            SoftwareMatch(
                name="nginx",
                provider="apt",
                confidence=0.9,
                metadata={"downloads": 100000, "stars": 1000}
            ),
            SoftwareMatch(
                name="nginx",
                provider="brew",
                confidence=0.9,
                metadata={"downloads": 500000, "stars": 5000}
            )
        ]
        
        ranked = self.ranker.rank_results(matches, "nginx", rank_by="popularity")
        
        # More popular package should be first
        self.assertEqual(ranked[0].provider, "brew")
        self.assertGreater(
            ranked[0].metadata["downloads"],
            ranked[1].metadata["downloads"]
        )
    
    def test_rank_by_recency(self):
        """Test ranking by package recency."""
        matches = [
            SoftwareMatch(
                name="nginx",
                provider="apt",
                version="1.18.0",
                confidence=0.9,
                metadata={"last_updated": "2021-01-01"}
            ),
            SoftwareMatch(
                name="nginx",
                provider="brew",
                version="1.25.3",
                confidence=0.9,
                metadata={"last_updated": "2023-12-01"}
            )
        ]
        
        ranked = self.ranker.rank_results(matches, "nginx", rank_by="recency")
        
        # More recent package should be first
        self.assertEqual(ranked[0].provider, "brew")
        self.assertEqual(ranked[0].version, "1.25.3")
    
    def test_rank_with_weights(self):
        """Test ranking with custom weights."""
        matches = [
            SoftwareMatch(
                name="nginx",
                provider="apt",
                confidence=1.0,  # Perfect match
                metadata={"downloads": 100000}
            ),
            SoftwareMatch(
                name="nginx-full",
                provider="apt",
                confidence=0.8,  # Good match
                metadata={"downloads": 1000000}  # Much more popular
            )
        ]
        
        # With high popularity weight, popular package should win
        ranked = self.ranker.rank_results(
            matches, "nginx",
            weights={"relevance": 0.3, "popularity": 0.7}
        )
        
        self.assertEqual(ranked[0].name, "nginx-full")
    
    def test_deduplication(self):
        """Test deduplication of similar results."""
        matches = [
            SoftwareMatch(name="nginx", provider="apt", version="1.18.0"),
            SoftwareMatch(name="nginx", provider="apt", version="1.18.0"),  # Duplicate
            SoftwareMatch(name="nginx", provider="brew", version="1.25.3")
        ]
        
        deduplicated = self.ranker.deduplicate_results(matches)
        
        self.assertEqual(len(deduplicated), 2)
        providers = [m.provider for m in deduplicated]
        self.assertIn("apt", providers)
        self.assertIn("brew", providers)


class TestPackageComparator(unittest.TestCase):
    """Test the PackageComparator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.comparator = PackageComparator()
    
    def test_compare_packages_same_software(self):
        """Test comparing packages for the same software."""
        packages = [
            {
                "name": "nginx",
                "provider": "apt",
                "version": "1.18.0",
                "description": "HTTP server and reverse proxy",
                "license": "BSD-2-Clause"
            },
            {
                "name": "nginx",
                "provider": "brew",
                "version": "1.25.3",
                "description": "HTTP(S) server and reverse proxy",
                "license": "BSD-2-Clause"
            }
        ]
        
        comparison = self.comparator.compare_packages(packages)
        
        self.assertEqual(comparison["software_name"], "nginx")
        self.assertEqual(len(comparison["providers"]), 2)
        self.assertIn("apt", comparison["providers"])
        self.assertIn("brew", comparison["providers"])
        
        # Should identify version differences
        self.assertIn("version", comparison["differences"])
        self.assertEqual(len(comparison["differences"]["version"]), 2)
    
    def test_identify_alternatives(self):
        """Test identifying alternative packages."""
        packages = [
            {
                "name": "nginx",
                "provider": "apt",
                "description": "HTTP server and reverse proxy",
                "category": "web-server"
            },
            {
                "name": "apache2",
                "provider": "apt",
                "description": "Apache HTTP Server",
                "category": "web-server"
            },
            {
                "name": "lighttpd",
                "provider": "apt",
                "description": "Lightweight HTTP server",
                "category": "web-server"
            }
        ]
        
        alternatives = self.comparator.find_alternatives(packages[0], packages[1:])
        
        self.assertGreater(len(alternatives), 0)
        # Should find apache2 and lighttpd as alternatives
        alt_names = [alt["name"] for alt in alternatives]
        self.assertIn("apache2", alt_names)
        self.assertIn("lighttpd", alt_names)
    
    def test_detect_duplicates(self):
        """Test detecting duplicate packages."""
        packages = [
            {"name": "nginx", "provider": "apt", "version": "1.18.0"},
            {"name": "nginx", "provider": "apt", "version": "1.18.0"},  # Exact duplicate
            {"name": "nginx", "provider": "brew", "version": "1.25.3"}  # Different provider
        ]
        
        duplicates = self.comparator.detect_duplicates(packages)
        
        self.assertEqual(len(duplicates), 1)  # One duplicate group
        self.assertEqual(len(duplicates[0]), 2)  # Two identical packages
    
    def test_version_comparison(self):
        """Test version comparison logic."""
        versions = ["1.18.0", "1.25.3", "1.20.1", "2.0.0"]
        
        sorted_versions = self.comparator.sort_versions(versions)
        
        # Should be sorted in ascending order
        self.assertEqual(sorted_versions[0], "1.18.0")
        self.assertEqual(sorted_versions[-1], "2.0.0")
    
    def test_feature_comparison(self):
        """Test comparing package features."""
        package1 = {
            "name": "nginx",
            "features": ["http", "https", "proxy", "load-balancing"],
            "modules": ["core", "ssl", "gzip"]
        }
        
        package2 = {
            "name": "nginx-full",
            "features": ["http", "https", "proxy", "load-balancing", "streaming"],
            "modules": ["core", "ssl", "gzip", "image-filter", "xslt"]
        }
        
        comparison = self.comparator.compare_features(package1, package2)
        
        self.assertIn("common_features", comparison)
        self.assertIn("unique_to_first", comparison)
        self.assertIn("unique_to_second", comparison)
        
        # Should identify streaming as unique to second package
        self.assertIn("streaming", comparison["unique_to_second"]["features"])


if __name__ == "__main__":
    unittest.main()