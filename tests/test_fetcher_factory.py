"""
Unit tests for the fetcher factory.
"""

import unittest

from saidata_gen.core.interfaces import FetcherConfig
from saidata_gen.fetcher.base import RepositoryFetcher
from saidata_gen.fetcher.factory import FetcherFactory


class TestFetcherFactory(unittest.TestCase):
    """Test the FetcherFactory class."""
    
    def setUp(self):
        """Set up the test environment."""
        self.factory = FetcherFactory()
        
        # Create a concrete implementation of the abstract class for testing
        class TestFetcher(RepositoryFetcher):
            def __init__(self, config=None, test_arg=None):
                super().__init__(config)
                self.test_arg = test_arg
            
            def fetch_repository_data(self):
                return None
            
            def get_package_info(self, package_name):
                return None
            
            def search_packages(self, query, max_results=10):
                return []
            
            def get_repository_name(self):
                return "test-repo"
        
        self.TestFetcher = TestFetcher
    
    def test_register_fetcher(self):
        """Test registering a fetcher."""
        self.factory.register_fetcher("test", self.TestFetcher)
        self.assertIn("test", self.factory.get_available_fetchers())
        self.assertTrue(self.factory.is_fetcher_available("test"))
    
    def test_create_fetcher(self):
        """Test creating a fetcher."""
        self.factory.register_fetcher("test", self.TestFetcher)
        
        # Create with default config
        fetcher = self.factory.create_fetcher("test")
        self.assertIsInstance(fetcher, self.TestFetcher)
        self.assertIsInstance(fetcher.config, FetcherConfig)
        self.assertIsNone(fetcher.test_arg)
        
        # Create with custom config and args
        config = FetcherConfig(cache_ttl=3600)
        fetcher = self.factory.create_fetcher("test", config=config, test_arg="value")
        self.assertIsInstance(fetcher, self.TestFetcher)
        self.assertEqual(fetcher.config.cache_ttl, 3600)
        self.assertEqual(fetcher.test_arg, "value")
    
    def test_create_unregistered_fetcher(self):
        """Test creating an unregistered fetcher."""
        fetcher = self.factory.create_fetcher("nonexistent")
        self.assertIsNone(fetcher)
    
    def test_get_available_fetchers(self):
        """Test getting available fetchers."""
        self.assertEqual(self.factory.get_available_fetchers(), [])
        
        self.factory.register_fetcher("test1", self.TestFetcher)
        self.factory.register_fetcher("test2", self.TestFetcher)
        
        available_fetchers = self.factory.get_available_fetchers()
        self.assertEqual(len(available_fetchers), 2)
        self.assertIn("test1", available_fetchers)
        self.assertIn("test2", available_fetchers)
    
    def test_is_fetcher_available(self):
        """Test checking if a fetcher is available."""
        self.assertFalse(self.factory.is_fetcher_available("test"))
        
        self.factory.register_fetcher("test", self.TestFetcher)
        self.assertTrue(self.factory.is_fetcher_available("test"))


if __name__ == "__main__":
    unittest.main()