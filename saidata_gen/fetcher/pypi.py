"""
PyPI repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from the Python
Package Index (PyPI).
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import HttpRepositoryFetcher


logger = logging.getLogger(__name__)


@dataclass
class PyPIRepository:
    """
    Configuration for a PyPI repository.
    """
    name: str  # e.g., "pypi"
    url: str  # e.g., "https://pypi.org/pypi/"


class PyPIFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Python Package Index (PyPI).
    
    This class fetches package metadata from PyPI by querying the JSON API.
    """
    
    def __init__(
        self,
        repositories: Optional[List[PyPIRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the PyPI fetcher.
        
        Args:
            repositories: List of PyPI repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Use the official PyPI as default
        self.repositories = repositories or [
            PyPIRepository(
                name="pypi",
                url="https://pypi.org/pypi/"
            )
        ]
        
        # Initialize with the first repository
        super().__init__(
            base_url=self.repositories[0].url,
            config=config,
            headers={"Accept": "application/json"}
        )
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, Dict[str, any]]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "pypi"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from PyPI repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for repo in self.repositories:
            try:
                # Update base URL
                self.base_url = repo.url
                
                # Fetch popular packages as a sample
                packages = self._fetch_popular_packages(repo.name)
                if packages:
                    self._package_cache[repo.name] = packages
                    result.providers[repo.name] = True
                else:
                    result.success = False
                    result.providers[repo.name] = False
                    result.errors[repo.name] = "No packages found"
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {repo.name}: {e}")
                result.errors[repo.name] = str(e)
                result.providers[repo.name] = False
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
        for repo_name, packages in self._package_cache.items():
            # Try exact match first
            if package_name in packages:
                pkg_data = packages[package_name]
                return self._create_package_info(package_name, pkg_data, repo_name)
            
            # Try case-insensitive match
            for pkg_name, pkg_data in packages.items():
                if pkg_name.lower() == package_name.lower():
                    return self._create_package_info(pkg_name, pkg_data, repo_name)
        
        # If not found in cache, try to fetch directly
        for repo in self.repositories:
            try:
                self.base_url = repo.url
                package_data = self._fetch_package_details(package_name, repo.name)
                if package_data:
                    return self._create_package_info(package_name, package_data, repo.name)
            except Exception as e:
                logger.warning(f"Failed to fetch package details for {package_name} from {repo.name}: {e}")
        
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
        results = []
        
        # Search in all repositories
        for repo in self.repositories:
            try:
                self.base_url = repo.url
                search_results = self._search_packages_in_repo(query, repo.name, max_results - len(results))
                
                for pkg_name, pkg_data in search_results.items():
                    # Create PackageInfo object
                    pkg_info = self._create_package_info(pkg_name, pkg_data, repo_name=repo.name)
                    
                    # Add to results if not already present
                    if not any(r.name == pkg_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
            
            except Exception as e:
                logger.warning(f"Failed to search packages in {repo.name}: {e}")
        
        return results
    
    def _create_package_info(self, package_name: str, package_data: Dict[str, any], repo_name: str) -> PackageInfo:
        """
        Create a PackageInfo object from package data.
        
        Args:
            package_name: Name of the package.
            package_data: Package data.
            repo_name: Name of the repository.
            
        Returns:
            PackageInfo object.
        """
        # Add repository information to details
        details = package_data.copy()
        details["repository"] = repo_name
        
        # Extract version
        version = "latest"
        if "version" in package_data:
            version = package_data["version"]
        elif "info" in package_data and "version" in package_data["info"]:
            version = package_data["info"]["version"]
        
        # Extract description
        description = ""
        if "summary" in package_data:
            description = package_data["summary"]
        elif "info" in package_data and "summary" in package_data["info"]:
            description = package_data["info"]["summary"]
        
        return PackageInfo(
            name=package_name,
            provider=self.get_repository_name(),
            version=version,
            description=description,
            details=details
        )
    
    def _fetch_popular_packages(self, repo_name: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch popular packages from a repository.
        
        Args:
            repo_name: Name of the repository.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        # For PyPI, we'll use a list of popular packages
        popular_packages = [
            "numpy", "pandas", "matplotlib", "requests", "django",
            "flask", "tensorflow", "pytorch", "scikit-learn", "scipy",
            "pillow", "beautifulsoup4", "pytest", "sqlalchemy", "fastapi"
        ]
        
        packages = {}
        for pkg_name in popular_packages:
            try:
                package_data = self._fetch_package_details(pkg_name, repo_name)
                if package_data:
                    packages[pkg_name] = package_data
            except Exception as e:
                logger.warning(f"Failed to fetch package details for {pkg_name} from {repo_name}: {e}")
        
        return packages
    
    def _fetch_package_details(self, package_name: str, repo_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch detailed information about a package.
        
        Args:
            package_name: Name of the package.
            repo_name: Name of the repository.
            
        Returns:
            Package metadata if found, None otherwise.
        """
        try:
            # Fetch package details from PyPI JSON API
            response = self._fetch_json(f"{package_name}/json")
            
            if "info" in response:
                info = response["info"]
                releases = response.get("releases", {})
                
                # Get the latest version
                latest_version = info.get("version")
                
                # Extract package metadata
                return {
                    "name": info.get("name"),
                    "version": latest_version,
                    "summary": info.get("summary"),
                    "description": info.get("description"),
                    "author": info.get("author"),
                    "author_email": info.get("author_email"),
                    "maintainer": info.get("maintainer"),
                    "maintainer_email": info.get("maintainer_email"),
                    "license": info.get("license"),
                    "project_url": info.get("project_url"),
                    "homepage": info.get("home_page"),
                    "documentation_url": info.get("docs_url"),
                    "download_url": info.get("download_url"),
                    "keywords": info.get("keywords", "").split(),
                    "classifiers": info.get("classifiers", []),
                    "requires_python": info.get("requires_python"),
                    "requires_dist": info.get("requires_dist", []),
                    "repository": repo_name
                }
        
        except Exception as e:
            logger.warning(f"Failed to fetch package details for {package_name} from {repo_name}: {e}")
            return None
    
    def _search_packages_in_repo(self, query: str, repo_name: str, max_results: int = 10) -> Dict[str, Dict[str, any]]:
        """
        Search for packages in a repository.
        
        Args:
            query: Search query.
            repo_name: Name of the repository.
            max_results: Maximum number of results to return.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        if repo_name == "pypi":
            try:
                # PyPI doesn't have a direct search API in the same format
                # We'll use the PyPI JSON API to search for packages
                # This is a simplified approach - in a real implementation, we might use the PyPI XML-RPC API
                # or the Warehouse API for more comprehensive search
                
                # For now, we'll try to fetch the package directly
                package_data = self._fetch_package_details(query, repo_name)
                if package_data:
                    return {query: package_data}
                
                # If that fails, we'll try some variations
                variations = [
                    query.lower(),
                    query.replace("-", "_"),
                    query.replace("_", "-"),
                    query.replace(" ", "-"),
                    query.replace(" ", "_")
                ]
                
                results = {}
                for variation in variations:
                    if len(results) >= max_results:
                        break
                    
                    if variation != query:
                        try:
                            package_data = self._fetch_package_details(variation, repo_name)
                            if package_data:
                                results[variation] = package_data
                        except Exception:
                            pass
                
                return results
            
            except Exception as e:
                logger.warning(f"Failed to search packages in {repo_name}: {e}")
                return {}
        else:
            logger.warning(f"Searching packages in {repo_name} is not supported")
            return {}