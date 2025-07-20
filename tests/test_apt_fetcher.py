"""
Unit tests for the APT fetcher.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from saidata_gen.core.interfaces import FetcherConfig
from saidata_gen.fetcher import APTFetcher, APTDistribution


class TestAPTFetcher(unittest.TestCase):
    """
    Test cases for the APT fetcher.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a test config with a temporary cache directory
        self.config = FetcherConfig(
            cache_dir=os.path.join(os.path.dirname(__file__), "test_cache"),
            cache_ttl=60
        )
        
        # Create a test distribution
        self.test_dist = APTDistribution(
            name="test",
            version="test",
            url="https://example.com/test",
            components=["main"],
            architectures=["amd64"]
        )
        
        # Create the fetcher with the test distribution
        self.fetcher = APTFetcher(
            distributions=[self.test_dist],
            config=self.config
        )
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up the test cache directory
        if os.path.exists(self.config.cache_dir):
            for file in os.listdir(self.config.cache_dir):
                file_path = os.path.join(self.config.cache_dir, file)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            
            # Remove any subdirectories
            for subdir in os.listdir(self.config.cache_dir):
                subdir_path = os.path.join(self.config.cache_dir, subdir)
                if os.path.isdir(subdir_path):
                    for file in os.listdir(subdir_path):
                        file_path = os.path.join(subdir_path, file)
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    os.rmdir(subdir_path)
            
            os.rmdir(self.config.cache_dir)
    
    def test_get_repository_name(self):
        """Test getting the repository name."""
        self.assertEqual(self.fetcher.get_repository_name(), "apt")
    
    @patch("saidata_gen.fetcher.apt.APTFetcher._fetch_packages_file")
    def test_fetch_repository_data(self, mock_fetch_packages):
        """Test fetching repository data."""
        # Mock the _fetch_packages_file method
        mock_fetch_packages.return_value = {
            "test-package": {
                "Package": "test-package",
                "Version": "1.0.0",
                "Description": "Test package description\\nMultiline description"
            }
        }
        
        # Fetch repository data
        result = self.fetcher.fetch_repository_data()
        
        # Check that the fetch was successful
        self.assertTrue(result.success)
        
        # Check that the mock was called with the correct arguments
        mock_fetch_packages.assert_called_once_with(
            self.test_dist.url,
            "main/binary-amd64/Packages.gz"
        )
    
    @patch("saidata_gen.fetcher.apt.APTFetcher._fetch_packages_file")
    def test_get_package_info(self, mock_fetch_packages):
        """Test getting package information."""
        # Mock the _fetch_packages_file method
        mock_fetch_packages.return_value = {
            "test-package": {
                "Package": "test-package",
                "Version": "1.0.0",
                "Description": "Test package description\\nMultiline description"
            }
        }
        
        # Fetch repository data to populate the cache
        self.fetcher.fetch_repository_data()
        
        # Get package info
        pkg_info = self.fetcher.get_package_info("test-package")
        
        # Check that the package info is correct
        self.assertIsNotNone(pkg_info)
        self.assertEqual(pkg_info.name, "test-package")
        self.assertEqual(pkg_info.provider, "apt")
        self.assertEqual(pkg_info.version, "1.0.0")
        self.assertEqual(pkg_info.description, "Test package description")
    
    @patch("saidata_gen.fetcher.apt.APTFetcher._fetch_packages_file")
    def test_search_packages(self, mock_fetch_packages):
        """Test searching for packages."""
        # Mock the _fetch_packages_file method
        mock_fetch_packages.return_value = {
            "test-package": {
                "Package": "test-package",
                "Version": "1.0.0",
                "Description": "Test package description\\nMultiline description"
            },
            "another-package": {
                "Package": "another-package",
                "Version": "2.0.0",
                "Description": "Another test package\\nWith test in the description"
            }
        }
        
        # Fetch repository data to populate the cache
        self.fetcher.fetch_repository_data()
        
        # Search for packages
        results = self.fetcher.search_packages("test")
        
        # Check that both packages are found
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "test-package")
        self.assertEqual(results[1].name, "another-package")
    
    @patch("saidata_gen.fetcher.apt.APTFetcher._fetch_packages_file")
    def test_get_package_details(self, mock_fetch_packages):
        """Test getting detailed package information."""
        # Mock the _fetch_packages_file method
        mock_fetch_packages.return_value = {
            "test-package": {
                "Package": "test-package",
                "Version": "1.0.0",
                "Description": "Test package description\\nMultiline description",
                "Depends": "lib1 (>= 1.0), lib2",
                "Maintainer": "Test Maintainer <test@example.com>",
                "Homepage": "https://example.com/test-package",
                "License": "MIT",
                "SHA256": "abcdef1234567890"
            }
        }
        
        # Fetch repository data to populate the cache
        self.fetcher.fetch_repository_data()
        
        # Get package details
        details = self.fetcher.get_package_details("test-package")
        
        # Check that the package details are correct
        self.assertIsNotNone(details)
        self.assertEqual(details.name, "test-package")
        self.assertEqual(details.provider, "apt")
        self.assertEqual(details.version, "1.0.0")
        self.assertEqual(details.description, "Test package description")
        self.assertEqual(details.license, "MIT")
        self.assertEqual(details.homepage, "https://example.com/test-package")
        self.assertEqual(details.maintainer, "Test Maintainer <test@example.com>")
        self.assertEqual(details.checksum, "abcdef1234567890")
        
        # Check that dependencies are parsed correctly
        self.assertEqual(len(details.dependencies), 2)
        self.assertEqual(details.dependencies[0], "lib1")
        self.assertEqual(details.dependencies[1], "lib2")
    
    def test_parse_packages_file(self):
        """Test parsing a Packages file."""
        # Sample Packages file content
        packages_text = """Package: test-package
Version: 1.0.0
Description: Test package description
 This is a multiline description
 with multiple lines

Package: another-package
Version: 2.0.0
Description: Another test package
 This is another multiline description
"""
        
        # Parse the Packages file
        result = self.fetcher._parse_packages_file(packages_text)
        
        # Check that the packages are parsed correctly
        self.assertEqual(len(result), 2)
        self.assertEqual(result["test-package"]["Package"], "test-package")
        self.assertEqual(result["test-package"]["Version"], "1.0.0")
        self.assertEqual(result["test-package"]["Description"], "Test package description\\nThis is a multiline description\\nwith multiple lines")
        self.assertEqual(result["another-package"]["Package"], "another-package")
        self.assertEqual(result["another-package"]["Version"], "2.0.0")
        self.assertEqual(result["another-package"]["Description"], "Another test package\\nThis is another multiline description")


if __name__ == "__main__":
    unittest.main()