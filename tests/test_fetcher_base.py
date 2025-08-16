"""
Unit tests for the fetcher base classes.
"""

import os
import tempfile
import unittest
from unittest import mock

import requests

from saidata_gen.core.interfaces import FetcherConfig
from saidata_gen.fetcher.base import (
    GitRepositoryFetcher, HttpRepositoryFetcher, RepositoryFetcher
)


class MockResponse:
    """Mock response for requests."""
    
    def __init__(self, status_code=200, content=b"", text="", json_data=None):
        self.status_code = status_code
        self.content = content
        self.text = text
        self._json_data = json_data
    
    def json(self):
        """Return JSON data."""
        return self._json_data
    
    def raise_for_status(self):
        """Raise an exception if the status code is not 2xx."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP Error: {self.status_code}")


class TestRepositoryFetcher(unittest.TestCase):
    """Test the RepositoryFetcher class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a concrete implementation of the abstract class for testing
        class ConcreteRepositoryFetcher(RepositoryFetcher):
            def fetch_repository_data(self):
                return None
            
            def get_package_info(self, package_name):
                return None
            
            def search_packages(self, query, max_results=10):
                return []
            
            def get_repository_name(self):
                return "test-repo"
        
        self.fetcher = ConcreteRepositoryFetcher()
        
        # Create a temporary directory for cache
        self.temp_dir = tempfile.TemporaryDirectory()
        self.fetcher.cache_dir = self.temp_dir.name
    
    def tearDown(self):
        """Clean up the test environment."""
        self.temp_dir.cleanup()
    
    def test_initialization(self):
        """Test initialization with default values."""
        self.assertIsInstance(self.fetcher.config, FetcherConfig)
        self.assertIsInstance(self.fetcher.session, requests.Session)
    
    def test_get_cache_path(self):
        """Test getting the cache path."""
        key = "test-key"
        cache_path = self.fetcher._get_cache_path(key)
        self.assertTrue(cache_path.endswith(".json"))
        self.assertIn("test-repo", cache_path)
    
    def test_cache_operations(self):
        """Test cache operations."""
        key = "test-key"
        data = {"test": "data"}
        
        # Initially, the cache should be empty
        self.assertIsNone(self.fetcher._get_from_cache(key))
        
        # Save data to the cache
        self.fetcher._save_to_cache(key, data)
        
        # Now the cache should contain the data
        cached_data = self.fetcher._get_from_cache(key)
        self.assertEqual(cached_data, data)
    
    @mock.patch("requests.Session.get")
    def test_fetch_url(self, mock_get):
        """Test fetching a URL."""
        mock_get.return_value = MockResponse(
            status_code=200,
            text="test content"
        )
        
        response = self.fetcher._fetch_url("https://example.com")
        self.assertEqual(response.text, "test content")
        mock_get.assert_called_once()
    
    @mock.patch("requests.Session.get")
    def test_fetch_url_retry(self, mock_get):
        """Test retry logic when fetching a URL."""
        # First call fails, second succeeds
        mock_get.side_effect = [
            requests.exceptions.RequestException("Test error"),
            MockResponse(status_code=200, text="test content")
        ]
        
        response = self.fetcher._fetch_url("https://example.com")
        self.assertEqual(response.text, "test content")
        self.assertEqual(mock_get.call_count, 2)


class TestHttpRepositoryFetcher(unittest.TestCase):
    """Test the HttpRepositoryFetcher class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a concrete implementation of the abstract class for testing
        class ConcreteHttpFetcher(HttpRepositoryFetcher):
            def fetch_repository_data(self):
                return None
            
            def get_package_info(self, package_name):
                return None
            
            def search_packages(self, query, max_results=10):
                return []
            
            def get_repository_name(self):
                return "test-http-repo"
        
        self.fetcher = ConcreteHttpFetcher("https://example.com/api")
        
        # Create a temporary directory for cache
        self.temp_dir = tempfile.TemporaryDirectory()
        self.fetcher.cache_dir = self.temp_dir.name
    
    def tearDown(self):
        """Clean up the test environment."""
        self.temp_dir.cleanup()
    
    def test_initialization(self):
        """Test initialization with default values."""
        self.assertEqual(self.fetcher.base_url, "https://example.com/api")
        self.assertEqual(self.fetcher.headers, {})
    
    def test_get_url(self):
        """Test getting a full URL."""
        self.assertEqual(
            self.fetcher._get_url("test"),
            "https://example.com/api/test"
        )
        self.assertEqual(
            self.fetcher._get_url("/test"),
            "https://example.com/api/test"
        )
    
    @mock.patch("saidata_gen.fetcher.base.HttpRepositoryFetcher._fetch_url")
    def test_fetch_json(self, mock_fetch_url):
        """Test fetching JSON data."""
        mock_fetch_url.return_value = MockResponse(
            status_code=200,
            json_data={"test": "data"}
        )
        
        data = self.fetcher._fetch_json("test", use_cache=False)
        self.assertEqual(data, {"test": "data"})
        mock_fetch_url.assert_called_once()
    
    @mock.patch("saidata_gen.fetcher.base.HttpRepositoryFetcher._fetch_url")
    def test_fetch_text(self, mock_fetch_url):
        """Test fetching text data."""
        mock_fetch_url.return_value = MockResponse(
            status_code=200,
            text="test content"
        )
        
        text = self.fetcher._fetch_text("test", use_cache=False)
        self.assertEqual(text, "test content")
        mock_fetch_url.assert_called_once()
    
    @mock.patch("saidata_gen.fetcher.base.HttpRepositoryFetcher._fetch_url")
    def test_fetch_binary(self, mock_fetch_url):
        """Test fetching binary data."""
        mock_fetch_url.return_value = MockResponse(
            status_code=200,
            content=b"test content"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "test.bin")
            path = self.fetcher._fetch_binary("test", output_path, use_cache=False)
            self.assertEqual(path, output_path)
            
            # Check that the file was created with the correct content
            with open(output_path, "rb") as f:
                self.assertEqual(f.read(), b"test content")
        
        mock_fetch_url.assert_called_once()


class TestGitRepositoryFetcher(unittest.TestCase):
    """Test the GitRepositoryFetcher class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a concrete implementation of the abstract class for testing
        class ConcreteGitFetcher(GitRepositoryFetcher):
            def fetch_repository_data(self):
                return None
            
            def get_package_info(self, package_name):
                return None
            
            def search_packages(self, query, max_results=10):
                return []
            
            def get_repository_name(self):
                return "test-git-repo"
        
        self.fetcher = ConcreteGitFetcher("https://github.com/example/repo.git")
        
        # Create a temporary directory for cache
        self.temp_dir = tempfile.TemporaryDirectory()
        self.fetcher.cache_dir = self.temp_dir.name
        self.fetcher.repo_dir = os.path.join(self.temp_dir.name, "repo")
    
    def tearDown(self):
        """Clean up the test environment."""
        self.temp_dir.cleanup()
    
    def test_initialization(self):
        """Test initialization with default values."""
        self.assertEqual(self.fetcher.repository_url, "https://github.com/example/repo.git")
        self.assertEqual(self.fetcher.branch, "main")
    
    @mock.patch("subprocess.run")
    def test_clone_repository(self, mock_run):
        """Test cloning a repository."""
        mock_run.return_value.returncode = 0
        
        result = self.fetcher._clone_or_pull_repository()
        self.assertTrue(result)
        mock_run.assert_called_once()
        self.assertIn("git", mock_run.call_args[0][0])
        self.assertIn("clone", mock_run.call_args[0][0])
    
    @mock.patch("subprocess.run")
    def test_pull_repository(self, mock_run):
        """Test pulling a repository."""
        mock_run.return_value.returncode = 0
        
        # Create the repo directory to simulate an existing repo
        os.makedirs(self.fetcher.repo_dir, exist_ok=True)
        
        result = self.fetcher._clone_or_pull_repository()
        self.assertTrue(result)
        mock_run.assert_called_once()
        self.assertIn("git", mock_run.call_args[0][0])
        self.assertIn("pull", mock_run.call_args[0][0])
    
    def test_get_file_content(self):
        """Test getting file content."""
        # Create a test file
        os.makedirs(self.fetcher.repo_dir, exist_ok=True)
        test_file = os.path.join(self.fetcher.repo_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        
        content = self.fetcher._get_file_content("test.txt")
        self.assertEqual(content, "test content")
        
        # Test with a non-existent file
        content = self.fetcher._get_file_content("nonexistent.txt")
        self.assertIsNone(content)
    
    def test_list_files(self):
        """Test listing files."""
        # Create test files
        os.makedirs(os.path.join(self.fetcher.repo_dir, "dir"), exist_ok=True)
        with open(os.path.join(self.fetcher.repo_dir, "test1.txt"), "w") as f:
            f.write("test1")
        with open(os.path.join(self.fetcher.repo_dir, "test2.txt"), "w") as f:
            f.write("test2")
        with open(os.path.join(self.fetcher.repo_dir, "dir", "test3.txt"), "w") as f:
            f.write("test3")
        
        # List all files
        files = self.fetcher._list_files(pattern="**/*.txt")
        self.assertEqual(len(files), 3)
        self.assertIn("test1.txt", files)
        self.assertIn("test2.txt", files)
        self.assertIn(os.path.join("dir", "test3.txt"), files)
        
        # List files in a directory
        files = self.fetcher._list_files(directory="dir", pattern="*.txt")
        self.assertEqual(len(files), 1)
        self.assertIn(os.path.join("dir", "test3.txt"), files)


if __name__ == "__main__":
    unittest.main()