"""
XBPS repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from Void Linux
XBPS repositories.
"""

import gzip
import io
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import HttpRepositoryFetcher


logger = logging.getLogger(__name__)


@dataclass
class XbpsRepository:
    """
    Configuration for an XBPS repository.
    """
    name: str  # e.g., "current", "nonfree"
    url: str  # e.g., "https://alpha.de.repo.voidlinux.org/current"
    architecture: str = "x86_64"  # Default architecture


class XbpsFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Void Linux XBPS repositories.
    
    This class fetches package metadata from Void Linux XBPS repositories
    by downloading and parsing repository index files.
    """
    
    def __init__(
        self,
        repositories: Optional[List[XbpsRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the XBPS fetcher.
        
        Args:
            repositories: List of XBPS repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Initialize with a dummy base_url, we'll use repository-specific URLs
        super().__init__(base_url="https://example.com", config=config)
        
        # Set up default repositories if none provided
        self.repositories = repositories or [
            XbpsRepository(
                name="current",
                url="https://alpha.de.repo.voidlinux.org/current"
            ),
            XbpsRepository(
                name="nonfree",
                url="https://alpha.de.repo.voidlinux.org/current/nonfree"
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
        return "xbps"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from XBPS repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for repo in self.repositories:
            repo_key = f"{repo.name}_{repo.architecture}"
            try:
                # Check if we have a valid cache
                cached_data = self._get_from_cache(repo_key)
                if cached_data:
                    self._package_cache[repo_key] = cached_data
                    result.cache_hits[repo_key] = True
                    continue
                
                # Fetch and parse repository index
                packages_data = self._fetch_repository_index(repo)
                if packages_data:
                    self._package_cache[repo_key] = packages_data
                    self._save_to_cache(repo_key, packages_data)
                    result.providers[repo_key] = True
                else:
                    result.success = False
                    result.providers[repo_key] = False
                    result.errors[repo_key] = "Failed to fetch repository index"
            
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
                    description=pkg_data.get("short_desc"),
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
                    (pkg_data.get("short_desc") and query_lower in pkg_data["short_desc"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = PackageInfo(
                        name=pkg_name,
                        provider=self.get_repository_name(),
                        version=pkg_data.get("version"),
                        description=pkg_data.get("short_desc"),
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
            repository: Optional repository to look in.
            
        Returns:
            PackageDetails if the package is found, None otherwise.
        """
        # Ensure we have fetched repository data
        if not self._package_cache:
            self.fetch_repository_data()
        
        # Look for the package in the specified repository or all repositories
        for repo_key, packages in self._package_cache.items():
            if repository and not repo_key.startswith(repository):
                continue
                
            if package_name in packages:
                pkg_data = packages[package_name]
                
                # Parse dependencies
                dependencies = []
                if "run_depends" in pkg_data:
                    for dep in pkg_data["run_depends"]:
                        # Extract package name (remove version constraints)
                        dep_name = re.sub(r'[<>=].*', '', dep)
                        if dep_name:
                            dependencies.append(dep_name)
                
                return PackageDetails(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("version"),
                    description=pkg_data.get("short_desc"),
                    license=pkg_data.get("license"),
                    homepage=pkg_data.get("homepage"),
                    dependencies=dependencies,
                    maintainer=pkg_data.get("maintainer"),
                    source_url=pkg_data.get("homepage"),
                    download_url=None,
                    checksum=pkg_data.get("sha256"),
                    raw_data=pkg_data
                )
        
        return None
    
    def _fetch_repository_index(self, repo: XbpsRepository) -> Dict[str, Dict[str, any]]:
        """
        Fetch and parse an XBPS repository index.
        
        Args:
            repo: Repository configuration.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        # Save the current base_url
        original_base_url = self.base_url
        
        try:
            # Set the base_url for this request
            self.base_url = repo.url
            
            # Fetch the index file
            index_path = f"{repo.architecture}/index.plist"
            
            try:
                # Try to fetch the binary plist file
                response = self._fetch_url(index_path)
                
                # Parse the binary plist file
                import plistlib
                index_data = plistlib.loads(response.content)
                
                # Convert to dictionary
                return self._parse_xbps_index(index_data)
                
            except Exception as e:
                logger.warning(f"Failed to fetch or parse index.plist, trying index-meta: {e}")
                
                # Try to fetch the index-meta file (JSON format)
                index_meta_path = f"{repo.architecture}/index-meta"
                response = self._fetch_url(index_meta_path)
                
                # Parse the JSON data
                index_data = json.loads(response.text)
                
                # Convert to dictionary
                return self._parse_xbps_meta_index(index_data)
            
        except Exception as e:
            logger.warning(f"Failed to fetch repository index for {repo.name}: {e}")
            return {}
        finally:
            # Restore the original base_url
            self.base_url = original_base_url
    
    def _parse_xbps_index(self, index_data: Dict[str, any]) -> Dict[str, Dict[str, any]]:
        """
        Parse an XBPS repository index in plist format.
        
        Args:
            index_data: Index data from plist file.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        
        # Extract package data
        for pkg_data in index_data.get("packages", []):
            pkg_name = pkg_data.get("pkgname")
            if pkg_name:
                result[pkg_name] = pkg_data
        
        return result
    
    def _parse_xbps_meta_index(self, index_data: Dict[str, any]) -> Dict[str, Dict[str, any]]:
        """
        Parse an XBPS repository index in JSON format.
        
        Args:
            index_data: Index data from JSON file.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        
        # Extract package data
        for pkg_name, pkg_data in index_data.items():
            # Skip non-package entries
            if not isinstance(pkg_data, dict):
                continue
                
            # Add package to result
            result[pkg_name] = pkg_data
        
        return result