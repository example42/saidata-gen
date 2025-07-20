"""
APK repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from Alpine Linux
APK repositories.
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
class ApkRepository:
    """
    Configuration for an APK repository.
    """
    name: str  # e.g., "main", "community"
    url: str  # e.g., "https://dl-cdn.alpinelinux.org/alpine/v3.16/main"
    architecture: str = "x86_64"  # Default architecture
    version: str = "v3.16"  # Alpine version


class ApkFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Alpine Linux APK repositories.
    
    This class fetches package metadata from Alpine Linux APK repositories
    by downloading and parsing APKINDEX files.
    """
    
    def __init__(
        self,
        repositories: Optional[List[ApkRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the APK fetcher.
        
        Args:
            repositories: List of APK repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Initialize with a dummy base_url, we'll use repository-specific URLs
        super().__init__(base_url="https://example.com", config=config)
        
        # Set up default repositories if none provided
        self.repositories = repositories or [
            ApkRepository(
                name="main",
                url="https://dl-cdn.alpinelinux.org/alpine/v3.16/main"
            ),
            ApkRepository(
                name="community",
                url="https://dl-cdn.alpinelinux.org/alpine/v3.16/community"
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
        return "apk"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from APK repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for repo in self.repositories:
            repo_key = f"{repo.name}_{repo.version}_{repo.architecture}"
            try:
                # Check if we have a valid cache
                cached_data = self._get_from_cache(repo_key)
                if cached_data:
                    self._package_cache[repo_key] = cached_data
                    result.cache_hits[repo_key] = True
                    continue
                
                # Fetch and parse APKINDEX
                packages_data = self._fetch_apkindex(repo)
                if packages_data:
                    self._package_cache[repo_key] = packages_data
                    self._save_to_cache(repo_key, packages_data)
                    result.providers[repo_key] = True
                else:
                    result.success = False
                    result.providers[repo_key] = False
                    result.errors[repo_key] = "Failed to fetch APKINDEX"
            
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
                    version=pkg_data.get("V"),
                    description=pkg_data.get("T"),
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
                    (pkg_data.get("T") and query_lower in pkg_data["T"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = PackageInfo(
                        name=pkg_name,
                        provider=self.get_repository_name(),
                        version=pkg_data.get("V"),
                        description=pkg_data.get("T"),
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
                if "D" in pkg_data:
                    # Split dependencies and extract package names
                    for dep in pkg_data["D"].split():
                        # Remove version constraints
                        dep_name = re.sub(r'[<>=].*', '', dep)
                        if dep_name and dep_name != "so:":
                            dependencies.append(dep_name)
                
                return PackageDetails(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("V"),
                    description=pkg_data.get("T"),
                    license=pkg_data.get("L"),
                    homepage=pkg_data.get("U"),
                    dependencies=dependencies,
                    maintainer=pkg_data.get("m"),
                    source_url=pkg_data.get("U"),
                    download_url=None,
                    checksum=pkg_data.get("C"),
                    raw_data=pkg_data
                )
        
        return None
    
    def _fetch_apkindex(self, repo: ApkRepository) -> Dict[str, Dict[str, any]]:
        """
        Fetch and parse an APKINDEX file from an APK repository.
        
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
            
            # Fetch the APKINDEX.tar.gz file
            apkindex_path = f"{repo.architecture}/APKINDEX.tar.gz"
            response = self._fetch_url(f"{repo.url}/{apkindex_path}")
            
            # Extract the APKINDEX file from the tar.gz archive
            import tarfile
            import io
            
            with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
                for member in tar.getmembers():
                    if member.name == "APKINDEX":
                        apkindex_content = tar.extractfile(member).read().decode("utf-8")
                        return self._parse_apkindex(apkindex_content)
            
            logger.warning(f"APKINDEX file not found in {apkindex_path}")
            return {}
            
        except Exception as e:
            logger.warning(f"Failed to fetch APKINDEX for {repo.name}: {e}")
            return {}
        finally:
            # Restore the original base_url
            self.base_url = original_base_url
    
    def _parse_apkindex(self, apkindex_content: str) -> Dict[str, Dict[str, any]]:
        """
        Parse an APKINDEX file from an APK repository.
        
        Args:
            apkindex_content: Content of the APKINDEX file.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        current_package = None
        current_data = {}
        
        for line in apkindex_content.splitlines():
            if not line:
                # Empty line indicates end of a package entry
                if current_package and current_data:
                    result[current_package] = current_data
                current_package = None
                current_data = {}
                continue
            
            # Each line is a key-value pair
            if ":" in line:
                key, value = line.split(":", 1)
                current_data[key] = value.strip()
                
                # If this is the package name field, set the current package
                if key == "P":
                    current_package = value.strip()
        
        # Add the last package (handle case where file doesn't end with empty line)
        if current_package and current_data:
            result[current_package] = current_data
        
        return result