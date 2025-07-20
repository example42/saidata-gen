"""
Unit tests for the DNF fetcher.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from saidata_gen.core.interfaces import FetcherConfig
from saidata_gen.fetcher import DNFFetcher, DNFDistribution


class TestDNFFetcher(unittest.TestCase):
    """
    Test cases for the DNF fetcher.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a test config with a temporary cache directory
        self.config = FetcherConfig(
            cache_dir=os.path.join(os.path.dirname(__file__), "test_cache"),
            cache_ttl=60
        )
        
        # Create a test distribution
        self.test_dist = DNFDistribution(
            name="test",
            version="test",
            url="https://example.com/test",
            architectures=["x86_64"]
        )
        
        # Create the fetcher with the test distribution
        self.fetcher = DNFFetcher(
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
        self.assertEqual(self.fetcher.get_repository_name(), "dnf")
    
    @patch("saidata_gen.fetcher.dnf.DNFFetcher._fetch_primary_location")
    @patch("saidata_gen.fetcher.dnf.DNFFetcher._fetch_primary_xml")
    def test_fetch_repository_data(self, mock_fetch_primary_xml, mock_fetch_primary_location):
        """Test fetching repository data."""
        # Mock the _fetch_primary_location method
        mock_fetch_primary_location.return_value = "repodata/primary.xml.gz"
        
        # Mock the _fetch_primary_xml method
        mock_fetch_primary_xml.return_value = {
            "test-package": {
                "name": "test-package",
                "version": "1.0.0-1",
                "summary": "Test package summary",
                "description": "Test package description"
            }
        }
        
        # Fetch repository data
        result = self.fetcher.fetch_repository_data()
        
        # Check that the fetch was successful
        self.assertTrue(result.success)
        
        # Check that the mocks were called with the correct arguments
        mock_fetch_primary_location.assert_called_once_with("https://example.com/test/repodata/repomd.xml")
        mock_fetch_primary_xml.assert_called_once_with("https://example.com/test/repodata/primary.xml.gz")
    
    @patch("saidata_gen.fetcher.dnf.DNFFetcher._fetch_primary_location")
    @patch("saidata_gen.fetcher.dnf.DNFFetcher._fetch_primary_xml")
    def test_get_package_info(self, mock_fetch_primary_xml, mock_fetch_primary_location):
        """Test getting package information."""
        # Mock the _fetch_primary_location method
        mock_fetch_primary_location.return_value = "repodata/primary.xml.gz"
        
        # Mock the _fetch_primary_xml method
        mock_fetch_primary_xml.return_value = {
            "test-package": {
                "name": "test-package",
                "version": "1.0.0-1",
                "summary": "Test package summary",
                "description": "Test package description"
            }
        }
        
        # Fetch repository data to populate the cache
        self.fetcher.fetch_repository_data()
        
        # Get package info
        pkg_info = self.fetcher.get_package_info("test-package")
        
        # Check that the package info is correct
        self.assertIsNotNone(pkg_info)
        self.assertEqual(pkg_info.name, "test-package")
        self.assertEqual(pkg_info.provider, "dnf")
        self.assertEqual(pkg_info.version, "1.0.0-1")
        self.assertEqual(pkg_info.description, "Test package summary")
    
    @patch("saidata_gen.fetcher.dnf.DNFFetcher._fetch_primary_location")
    @patch("saidata_gen.fetcher.dnf.DNFFetcher._fetch_primary_xml")
    def test_search_packages(self, mock_fetch_primary_xml, mock_fetch_primary_location):
        """Test searching for packages."""
        # Mock the _fetch_primary_location method
        mock_fetch_primary_location.return_value = "repodata/primary.xml.gz"
        
        # Mock the _fetch_primary_xml method
        mock_fetch_primary_xml.return_value = {
            "test-package": {
                "name": "test-package",
                "version": "1.0.0-1",
                "summary": "Test package summary",
                "description": "Test package description"
            },
            "another-package": {
                "name": "another-package",
                "version": "2.0.0-1",
                "summary": "Another test package",
                "description": "Another package with test in the description"
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
    
    @patch("saidata_gen.fetcher.dnf.DNFFetcher._fetch_primary_location")
    @patch("saidata_gen.fetcher.dnf.DNFFetcher._fetch_primary_xml")
    def test_get_package_details(self, mock_fetch_primary_xml, mock_fetch_primary_location):
        """Test getting detailed package information."""
        # Mock the _fetch_primary_location method
        mock_fetch_primary_location.return_value = "repodata/primary.xml.gz"
        
        # Mock the _fetch_primary_xml method
        mock_fetch_primary_xml.return_value = {
            "test-package": {
                "name": "test-package",
                "version": "1.0.0-1",
                "summary": "Test package summary",
                "description": "Test package description",
                "url": "https://example.com/test-package",
                "license": "MIT",
                "source_rpm": "test-package-1.0.0-1.src.rpm",
                "requires": ["lib1", "lib2"],
                "checksum": "abcdef1234567890",
                "checksum_type": "sha256"
            }
        }
        
        # Fetch repository data to populate the cache
        self.fetcher.fetch_repository_data()
        
        # Get package details
        details = self.fetcher.get_package_details("test-package")
        
        # Check that the package details are correct
        self.assertIsNotNone(details)
        self.assertEqual(details.name, "test-package")
        self.assertEqual(details.provider, "dnf")
        self.assertEqual(details.version, "1.0.0-1")
        self.assertEqual(details.description, "Test package summary")
        self.assertEqual(details.license, "MIT")
        self.assertEqual(details.homepage, "https://example.com/test-package")
        self.assertEqual(details.source_url, "test-package-1.0.0-1.src.rpm")
        self.assertEqual(details.checksum, "abcdef1234567890")
        
        # Check that dependencies are parsed correctly
        self.assertEqual(len(details.dependencies), 2)
        self.assertEqual(details.dependencies[0], "lib1")
        self.assertEqual(details.dependencies[1], "lib2")
    
    def test_parse_primary_xml(self):
        """Test parsing a primary.xml file."""
        # Sample primary.xml content
        primary_xml = """<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="2">
  <package type="rpm">
    <name>test-package</name>
    <arch>x86_64</arch>
    <version epoch="0" ver="1.0.0" rel="1"/>
    <checksum type="sha256" pkgid="YES">abcdef1234567890</checksum>
    <summary>Test package summary</summary>
    <description>Test package description</description>
    <url>https://example.com/test-package</url>
    <format>
      <rpm:license>MIT</rpm:license>
      <rpm:sourcerpm>test-package-1.0.0-1.src.rpm</rpm:sourcerpm>
      <rpm:requires>
        <rpm:entry name="lib1"/>
        <rpm:entry name="lib2"/>
        <rpm:entry name="rpmlib(CompressedFileNames)" flags="LE" epoch="0" ver="3.0.4" rel="1"/>
      </rpm:requires>
    </format>
  </package>
  <package type="rpm">
    <name>another-package</name>
    <arch>x86_64</arch>
    <version epoch="1" ver="2.0.0" rel="1"/>
    <checksum type="sha256" pkgid="YES">0987654321fedcba</checksum>
    <summary>Another test package</summary>
    <description>Another package with test in the description</description>
    <url>https://example.com/another-package</url>
    <format>
      <rpm:license>GPL-2.0</rpm:license>
      <rpm:sourcerpm>another-package-2.0.0-1.src.rpm</rpm:sourcerpm>
      <rpm:requires>
        <rpm:entry name="lib3"/>
        <rpm:entry name="/bin/sh"/>
      </rpm:requires>
    </format>
  </package>
</metadata>
"""
        
        # Parse the primary.xml file
        result = self.fetcher._parse_primary_xml(primary_xml)
        
        # Check that the packages are parsed correctly
        self.assertEqual(len(result), 2)
        
        # Check first package
        self.assertEqual(result["test-package"]["name"], "test-package")
        self.assertEqual(result["test-package"]["version"], "1.0.0-1")
        self.assertEqual(result["test-package"]["summary"], "Test package summary")
        self.assertEqual(result["test-package"]["description"], "Test package description")
        self.assertEqual(result["test-package"]["url"], "https://example.com/test-package")
        self.assertEqual(result["test-package"]["license"], "MIT")
        self.assertEqual(result["test-package"]["source_rpm"], "test-package-1.0.0-1.src.rpm")
        self.assertEqual(result["test-package"]["checksum"], "abcdef1234567890")
        self.assertEqual(result["test-package"]["checksum_type"], "sha256")
        
        # Check dependencies
        self.assertEqual(len(result["test-package"]["requires"]), 2)
        self.assertEqual(result["test-package"]["requires"][0], "lib1")
        self.assertEqual(result["test-package"]["requires"][1], "lib2")
        
        # Check second package
        self.assertEqual(result["another-package"]["name"], "another-package")
        self.assertEqual(result["another-package"]["version"], "1:2.0.0-1")  # Note the epoch
        self.assertEqual(result["another-package"]["summary"], "Another test package")
        self.assertEqual(result["another-package"]["description"], "Another package with test in the description")
        
        # Check dependencies (should only include lib3, not /bin/sh)
        self.assertEqual(len(result["another-package"]["requires"]), 1)
        self.assertEqual(result["another-package"]["requires"][0], "lib3")


if __name__ == "__main__":
    unittest.main()