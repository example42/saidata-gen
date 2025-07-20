"""
Homebrew repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from Homebrew
repositories, including formulae and casks for both macOS and Linux.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urljoin

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import HttpRepositoryFetcher, REQUESTS_AVAILABLE


logger = logging.getLogger(__name__)


@dataclass
class BrewRepository:
    """
    Configuration for a Homebrew repository.
    """
    name: str  # e.g., "homebrew/core", "homebrew/cask"
    url: str  # e.g., "https://formulae.brew.sh/api/formula.json"
    type: str  # e.g., "formula", "cask"
    platform: str = "all"  # e.g., "macos", "linux", "all"


class BrewFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Homebrew repositories.
    
    This class fetches package metadata from Homebrew repositories,
    including formulae and casks for both macOS and Linux.
    """
    
    def __init__(
        self,
        repositories: Optional[List[BrewRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Homebrew fetcher.
        
        Args:
            repositories: List of Homebrew repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
            
        Raises:
            ImportError: If the requests library is not available.
        """
        # Check if requests is available
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "The 'requests' library is required for the BrewFetcher. "
                "Please install it using 'pip install requests'."
            )
        
        # Initialize with a dummy base_url, we'll use repository-specific URLs
        super().__init__(base_url="https://example.com", config=config)
        
        # Set up default repositories if none provided
        self.repositories = repositories or [
            BrewRepository(
                name="homebrew/core",
                url="https://formulae.brew.sh/api/formula.json",
                type="formula",
                platform="all"
            ),
            BrewRepository(
                name="homebrew/cask",
                url="https://formulae.brew.sh/api/cask.json",
                type="cask",
                platform="macos"
            ),
            BrewRepository(
                name="homebrew/core-linux",
                url="https://formulae.brew.sh/api/formula-linux.json",
                type="formula",
                platform="linux"
            )
        ]
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, Dict[str, any]]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "brew"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Homebrew repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for repo in self.repositories:
            repo_key = f"{repo.name}_{repo.type}"
            try:
                # Check if we have a valid cache
                cached_data = self._get_from_cache(repo_key)
                if cached_data:
                    self._package_cache[repo_key] = cached_data
                    result.cache_hits[repo_key] = True
                    continue
                
                # Fetch the repository data
                try:
                    # Save the current base_url
                    original_base_url = self.base_url
                    
                    try:
                        # Set the base_url for this request to the repository URL's base
                        self.base_url = "/".join(repo.url.split("/")[:-1])
                        
                        # Fetch the JSON data
                        response = self._fetch_url(repo.url)
                        data = response.json()
                        
                        # Process the data based on the repository type
                        packages_data = self._process_repository_data(data, repo.type)
                        
                        self._package_cache[repo_key] = packages_data
                        self._save_to_cache(repo_key, packages_data)
                        result.providers[repo_key] = True
                    finally:
                        # Restore the original base_url
                        self.base_url = original_base_url
                        
                except Exception as e:
                    logger.error(f"Failed to fetch repository data for {repo_key}: {e}")
                    result.errors[repo_key] = str(e)
                    result.providers[repo_key] = False
                    result.success = False
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {repo_key}: {e}")
                result.errors[repo_key] = str(e)
                result.providers[repo_key] = False
                result.success = False
        
        return result
    
    def get_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """
        Get information about a specific package.
        
        Args:
            package_name: Name of the package to get information for.
            
        Returns:
            PackageInfo if the package is found, None otherwise.
        """
        # Ensure we have fetched repository data
        if not self._package_cache:
            self.fetch_repository_data()
        
        # Look for the package in all repositories
        for repo_key, packages in self._package_cache.items():
            if package_name in packages:
                pkg_data = packages[package_name]
                return PackageInfo(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("version"),
                    description=pkg_data.get("desc"),
                    details=pkg_data
                )
        
        return None
    
    def search_packages(self, query: str, max_results: int = 10) -> List[PackageInfo]:
        """
        Search for packages matching the query.
        
        Args:
            query: Search query.
            max_results: Maximum number of results to return.
            
        Returns:
            List of PackageInfo objects matching the query.
        """
        # Ensure we have fetched repository data
        if not self._package_cache:
            self.fetch_repository_data()
        
        results = []
        query_lower = query.lower()
        
        # Search in all repositories
        for repo_key, packages in self._package_cache.items():
            for pkg_name, pkg_data in packages.items():
                # Check if the package name or description contains the query
                if (query_lower in pkg_name.lower() or 
                    (pkg_data.get("desc") and query_lower in pkg_data["desc"].lower()) or
                    (pkg_data.get("full_name") and query_lower in pkg_data["full_name"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = PackageInfo(
                        name=pkg_name,
                        provider=self.get_repository_name(),
                        version=pkg_data.get("version"),
                        description=pkg_data.get("desc"),
                        details=pkg_data
                    )
                    
                    # Add to results if not already present
                    if not any(r.name == pkg_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
        
        return results
    
    def get_package_details(self, package_name: str, repository: Optional[str] = None) -> Optional[PackageDetails]:
        """
        Get detailed information about a specific package.
        
        Args:
            package_name: Name of the package to get information for.
            repository: Optional repository to look in (e.g., "homebrew/core_formula").
            
        Returns:
            PackageDetails if the package is found, None otherwise.
        """
        # Ensure we have fetched repository data
        if not self._package_cache:
            self.fetch_repository_data()
        
        # Look for the package in the specified repository or all repositories
        for repo_key, packages in self._package_cache.items():
            if repository and repo_key != repository:
                continue
                
            if package_name in packages:
                pkg_data = packages[package_name]
                
                # Extract dependencies
                dependencies = []
                if "dependencies" in pkg_data:
                    dependencies.extend(pkg_data["dependencies"])
                if "build_dependencies" in pkg_data:
                    dependencies.extend(pkg_data["build_dependencies"])
                if "requirements" in pkg_data and isinstance(pkg_data["requirements"], list):
                    for req in pkg_data["requirements"]:
                        if isinstance(req, dict) and "name" in req:
                            dependencies.append(req["name"])
                
                # Get license information
                license_info = pkg_data.get("license")
                if isinstance(license_info, dict) and "spdx_id" in license_info:
                    license_text = license_info["spdx_id"]
                else:
                    license_text = str(license_info) if license_info else None
                
                # Get homepage
                homepage = pkg_data.get("homepage")
                
                # Get source URL
                source_url = None
                if "urls" in pkg_data and isinstance(pkg_data["urls"], dict):
                    source_url = pkg_data["urls"].get("stable")
                
                # Get download URL
                download_url = None
                if "bottle" in pkg_data and isinstance(pkg_data["bottle"], dict):
                    bottles = pkg_data["bottle"].get("stable", {}).get("files", {})
                    if bottles:
                        # Just get the first bottle URL
                        for platform, bottle in bottles.items():
                            if isinstance(bottle, dict) and "url" in bottle:
                                download_url = bottle["url"]
                                break
                
                return PackageDetails(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("version"),
                    description=pkg_data.get("desc"),
                    license=license_text,
                    homepage=homepage,
                    dependencies=dependencies,
                    maintainer=pkg_data.get("tap_git_head"),  # Not ideal, but Homebrew doesn't have explicit maintainer info
                    source_url=source_url,
                    download_url=download_url,
                    checksum=None,  # Homebrew API doesn't provide checksums directly
                    raw_data=pkg_data
                )
        
        return None
    
    def _process_repository_data(self, data: List[Dict[str, any]], repo_type: str) -> Dict[str, Dict[str, any]]:
        """
        Process repository data from Homebrew API.
        
        Args:
            data: Raw data from the Homebrew API.
            repo_type: Type of repository (formula or cask).
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        
        for item in data:
            # Get the package name
            name = item.get("name")
            if not name:
                continue
            
            # Add repository type to the data
            item["brew_type"] = repo_type
            
            # Add the package to the result
            result[name] = item
            
            # Also add by full_name if available and different from name
            full_name = item.get("full_name")
            if full_name and full_name != name and full_name not in result:
                # Create a copy with the same data but different name
                full_name_item = item.copy()
                full_name_item["name"] = full_name
                result[full_name] = full_name_item
        
        return result
    
    def fetch_formula_info(self, formula_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch detailed information about a specific formula.
        
        Args:
            formula_name: Name of the formula to get information for.
            
        Returns:
            Dictionary with formula information if found, None otherwise.
        """
        # Save the current base_url
        original_base_url = self.base_url
        
        try:
            # Set the base_url for this request
            self.base_url = "https://formulae.brew.sh/api"
            
            # Fetch the formula JSON data
            cache_key = f"formula_info:{formula_name}"
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                return cached_data
            
            try:
                response = self._fetch_url(f"{self.base_url}/formula/{formula_name}.json")
                data = response.json()
                self._save_to_cache(cache_key, data)
                return data
            except Exception as e:
                logger.error(f"Failed to fetch formula info for {formula_name}: {e}")
                return None
                
        finally:
            # Restore the original base_url
            self.base_url = original_base_url
    
    def fetch_cask_info(self, cask_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch detailed information about a specific cask.
        
        Args:
            cask_name: Name of the cask to get information for.
            
        Returns:
            Dictionary with cask information if found, None otherwise.
        """
        # Save the current base_url
        original_base_url = self.base_url
        
        try:
            # Set the base_url for this request
            self.base_url = "https://formulae.brew.sh/api"
            
            # Fetch the cask JSON data
            cache_key = f"cask_info:{cask_name}"
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                return cached_data
            
            try:
                response = self._fetch_url(f"{self.base_url}/cask/{cask_name}.json")
                data = response.json()
                self._save_to_cache(cache_key, data)
                return data
            except Exception as e:
                logger.error(f"Failed to fetch cask info for {cask_name}: {e}")
                return None
                
        finally:
            # Restore the original base_url
            self.base_url = original_base_url