"""
Unit tests for the Winget fetcher.
"""

import os
import pytest
import tempfile
import yaml
from unittest.mock import patch, MagicMock

from saidata_gen.core.interfaces import FetcherConfig
from saidata_gen.fetcher.winget import WingetFetcher, WingetRepository


class TestWingetFetcher:
    """Test the Winget fetcher."""

    @pytest.fixture
    def mock_repo_dir(self):
        """Create a temporary directory for the mock repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create manifests directory structure
            manifests_dir = os.path.join(temp_dir, "manifests")
            os.makedirs(manifests_dir, exist_ok=True)
            
            # Create sample manifest directories and files
            # Microsoft/VisualStudioCode/1.60.0/
            vscode_dir = os.path.join(manifests_dir, "m", "Microsoft", "VisualStudioCode", "1.60.0")
            os.makedirs(vscode_dir, exist_ok=True)
            with open(os.path.join(vscode_dir, "Microsoft.VisualStudioCode.yaml"), "w") as f:
                yaml.dump({
                    "PackageIdentifier": "Microsoft.VisualStudioCode",
                    "PackageVersion": "1.60.0",
                    "PackageName": "Visual Studio Code",
                    "Publisher": "Microsoft",
                    "License": "MIT",
                    "Description": "Code editing. Redefined.",
                    "Homepage": "https://code.visualstudio.com",
                }, f)
            
            # Mozilla/Firefox/90.0/
            firefox_dir = os.path.join(manifests_dir, "m", "Mozilla", "Firefox", "90.0")
            os.makedirs(firefox_dir, exist_ok=True)
            with open(os.path.join(firefox_dir, "Mozilla.Firefox.yaml"), "w") as f:
                yaml.dump({
                    "PackageIdentifier": "Mozilla.Firefox",
                    "PackageVersion": "90.0",
                    "PackageName": "Firefox",
                    "Publisher": "Mozilla",
                    "License": "MPL-2.0",
                    "Description": "Mozilla Firefox is free and open source software.",
                    "Homepage": "https://www.mozilla.org/firefox/",
                }, f)
            
            yield temp_dir

    @pytest.fixture
    def fetcher(self):
        """Create a Winget fetcher with a mock configuration."""
        config = FetcherConfig(
            cache_dir=tempfile.mkdtemp(),
            cache_ttl=3600,
            concurrent_requests=5,
            request_timeout=30,
            retry_count=3
        )
        return WingetFetcher(config=config)

    def test_get_repository_name(self, fetcher):
        """Test getting the repository name."""
        assert fetcher.get_repository_name() == "winget"

    @patch("saidata_gen.fetcher.base.GitRepositoryFetcher._clone_or_pull_repository")
    def test_fetch_repository_data(self, mock_clone, fetcher, mock_repo_dir):
        """Test fetching repository data."""
        # Mock the clone_or_pull_repository method to return True
        mock_clone.return_value = True
        
        # Mock the repo_dir to use our temporary directory
        fetcher.repo_dir = mock_repo_dir
        
        # Fetch repository data
        result = fetcher.fetch_repository_data()
        
        # Verify the result
        assert result.success is True
        assert "winget-pkgs" in result.providers
        assert result.providers["winget-pkgs"] is True
        
        # Verify that the package cache contains the expected packages
        assert "Microsoft.VisualStudioCode" in fetcher._package_cache["winget-pkgs"]
        assert "Mozilla.Firefox" in fetcher._package_cache["winget-pkgs"]

    @patch("saidata_gen.fetcher.base.GitRepositoryFetcher._clone_or_pull_repository")
    def test_get_package_info(self, mock_clone, fetcher, mock_repo_dir):
        """Test getting package information."""
        # Mock the clone_or_pull_repository method to return True
        mock_clone.return_value = True
        
        # Mock the repo_dir to use our temporary directory
        fetcher.repo_dir = mock_repo_dir
        
        # Fetch repository data first
        fetcher.fetch_repository_data()
        
        # Get package info
        vscode_info = fetcher.get_package_info("Microsoft.VisualStudioCode")
        
        # Verify the package info
        assert vscode_info is not None
        assert vscode_info.name == "Microsoft.VisualStudioCode"
        assert vscode_info.provider == "winget"
        assert vscode_info.version == "1.60.0"  # Now using PackageVersion instead of Version
        assert vscode_info.description == "Code editing. Redefined."
        assert vscode_info.details["Publisher"] == "Microsoft"
        assert vscode_info.details["License"] == "MIT"
        assert vscode_info.details["Homepage"] == "https://code.visualstudio.com"

    @patch("saidata_gen.fetcher.base.GitRepositoryFetcher._clone_or_pull_repository")
    def test_search_packages(self, mock_clone, fetcher, mock_repo_dir):
        """Test searching for packages."""
        # Mock the clone_or_pull_repository method to return True
        mock_clone.return_value = True
        
        # Mock the repo_dir to use our temporary directory
        fetcher.repo_dir = mock_repo_dir
        
        # Fetch repository data first
        fetcher.fetch_repository_data()
        
        # Search for packages
        results = fetcher.search_packages("firefox")
        
        # Verify the search results
        assert len(results) == 1
        assert results[0].name == "Mozilla.Firefox"
        assert results[0].provider == "winget"
        assert results[0].version == "90.0"
        assert results[0].description == "Mozilla Firefox is free and open source software."
        
        # Search for packages with a more general query
        results = fetcher.search_packages("mozilla")
        
        # Verify the search results
        assert len(results) == 1
        assert results[0].name == "Mozilla.Firefox"
        
        # Search for packages with a query that should match multiple packages
        results = fetcher.search_packages("microsoft")
        
        # Verify the search results
        assert len(results) == 1
        assert results[0].name == "Microsoft.VisualStudioCode"

    @patch("saidata_gen.fetcher.base.GitRepositoryFetcher._clone_or_pull_repository")
    def test_clone_failure(self, mock_clone, fetcher):
        """Test handling of clone failure."""
        # Mock the clone_or_pull_repository method to return False
        mock_clone.return_value = False
        
        # Fetch repository data
        result = fetcher.fetch_repository_data()
        
        # Verify the result
        assert result.success is False
        assert "winget-pkgs" in result.providers
        assert result.providers["winget-pkgs"] is False
        assert "winget-pkgs" in result.errors
        assert result.errors["winget-pkgs"] == "Failed to clone or pull repository"