"""
OPKG repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from embedded Linux
OPKG repositories.
"""

import gzip
import io
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
class OpkgRepository:
    """
    Configuration for an OPKG repository.
    """
    name: str  # e.g., "openwrt", "openwrt-packages"
    url: str  # e.g., "https://downloads.openwrt.org/releases/22.03.3/packages/x86_64/base"
    architecture: str = "x86_64"  # Default architecture


class OpkgFetcher(HttpRepositoryFetcher):
    """
    Fetcher for embedded Linux OPKG repositories.
    
    This class fetches package metadata from OPKG repositories by downloading
    and parsing Packages.gz files.
    """
    
    def __init__(
        self,
        repositories: Optional[List[OpkgRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the OPKG fetcher.
        
        Args:
            repositories: List of OPKG repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Initialize with a dummy base_url, we'll use repository-specific URLs
        super().__init__(base_url="https://example.com", config=config)
        
        # Set up default repositories if none provided
        self.repositories = repositories or [
            OpkgRepository(
                name="openwrt-base",
                url="https://downloads.openwrt.org/releases/22.03.3/packages/x86_64/base"
            ),
            OpkgRepository(
                name="openwrt-packages",
                url="https://downloads.openwrt.org/releases/22.03.3/packages/x86_64/packages"
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
        return "opkg"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from OPKG repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for repo in self.repositories:
            repo_key = repo.name
            try:
                # Check if we have a valid cache
                cached_data = self._get_from_cache(repo_key)
                if cached_data:
                    self._package_cache[repo_key] = cached_data
                    result.cache_hits[repo_key] = True
                    continue
                
                # Fetch and parse Packages.gz
                packages_data = self._fetch_packages_file(repo)
                if packages_data:
                    self._package_cache[repo_key] = packages_data
                    self._save_to_cache(repo_key, packages_data)
                    result.providers[repo_key] = True
                else:
                    result.success = False
                    result.providers[repo_key] = False
                    result.errors[repo_key] = "Failed to fetch Packages.gz"
            
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
        for repo_name, packages in self._package_cache.items():
            if package_name in packages:
                pkg_data = packages[package_name]
                return PackageInfo(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("Version"),
                    description=pkg_data.get("Description"),
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
        for repo_name, packages in self._package_cache.items():
            for pkg_name, pkg_data in packages.items():
                # Check if the package name or description contains the query
                if (query_lower in pkg_name.lower() or 
                    (pkg_data.get("Description") and query_lower in pkg_data["Description"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = PackageInfo(
                        name=pkg_name,
                        provider=self.get_repository_name(),
                        version=pkg_data.get("Version"),
                        description=pkg_data.get("Description"),
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
        for repo_name, packages in self._package_cache.items():
            if repository and repo_name != repository:
                continue
                
            if package_name in packages:
                pkg_data = packages[package_name]
                
                # Parse dependencies
                dependencies = []
                if "Depends" in pkg_data:
                    # Split by comma, then extract package names (ignoring version constraints)
                    for dep in pkg_data["Depends"].split(","):
                        dep = dep.strip()
                        # Extract package name (everything before the first space or parenthesis)
                        match = re.match(r"([^\s\(]+)", dep)
                        if match:
                            dependencies.append(match.group(1))
                
                return PackageDetails(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("Version"),
                    description=pkg_data.get("Description"),
                    license=pkg_data.get("License"),
                    homepage=pkg_data.get("Homepage"),
                    dependencies=dependencies,
                    maintainer=pkg_data.get("Maintainer"),
                    source_url=pkg_data.get("Source"),
                    download_url=pkg_data.get("Filename"),
                    checksum=pkg_data.get("MD5Sum"),
                    raw_data=pkg_data
                )
        
        return None
    
    def _fetch_packages_file(self, repo: OpkgRepository) -> Dict[str, Dict[str, any]]:
        """
        Fetch and parse a Packages.gz file from an OPKG repository.
        
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
            
            # Fetch the Packages.gz file
            response = self._fetch_url("Packages.gz")
            
            # Decompress the gzipped content
            with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
                packages_text = f.read().decode("utf-8")
            
            # Parse the Packages file
            return self._parse_packages_file(packages_text)
            
        except Exception as e:
            logger.warning(f"Failed to fetch Packages.gz, trying uncompressed Packages: {e}")
            
            try:
                # Try uncompressed Packages file
                packages_text = self._fetch_text("Packages")
                return self._parse_packages_file(packages_text)
            except Exception as e2:
                logger.warning(f"Failed to fetch uncompressed Packages: {e2}")
                return {}
        finally:
            # Restore the original base_url
            self.base_url = original_base_url
    
    def _parse_packages_file(self, packages_text: str) -> Dict[str, Dict[str, any]]:
        """
        Parse a Packages file from an OPKG repository.
        
        Args:
            packages_text: Content of the Packages file.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        current_package = None
        current_data = {}
        
        for line in packages_text.splitlines():
            if not line.strip():
                # Empty line indicates end of a package entry
                if current_package and current_data:
                    result[current_package] = current_data
                current_package = None
                current_data = {}
                continue
                
            if line.startswith(" "):
                # Continuation of previous value
                continue
                
            # New key-value pair
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                
                current_data[key] = value
                
                # If this is the Package field, set the current package
                if key == "Package":
                    current_package = value
        
        # Add the last package (handle case where file doesn't end with empty line)
        if current_package and current_data:
            result[current_package] = current_data
        
        return result