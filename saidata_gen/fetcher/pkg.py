"""
FreeBSD pkg repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from FreeBSD
pkg repositories.
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
class PkgRepository:
    """
    Configuration for a FreeBSD pkg repository.
    """
    name: str  # e.g., "FreeBSD"
    url: str  # e.g., "https://pkg.freebsd.org/FreeBSD:13:amd64/latest"
    architecture: str = "amd64"  # Default architecture
    version: str = "13"  # FreeBSD version


class PkgFetcher(HttpRepositoryFetcher):
    """
    Fetcher for FreeBSD pkg repositories.
    
    This class fetches package metadata from FreeBSD pkg repositories
    by downloading and parsing packagesite.txz files.
    """
    
    def __init__(
        self,
        repositories: Optional[List[PkgRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the pkg fetcher.
        
        Args:
            repositories: List of pkg repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Initialize with a dummy base_url, we'll use repository-specific URLs
        super().__init__(base_url="https://example.com", config=config)
        
        # Set up default repositories if none provided
        self.repositories = repositories or [
            PkgRepository(
                name="FreeBSD",
                url="https://pkg.freebsd.org/FreeBSD:13:amd64/latest"
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
        return "pkg"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from pkg repositories.
        
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
                
                # Fetch and parse packagesite
                packages_data = self._fetch_packagesite(repo)
                if packages_data:
                    self._package_cache[repo_key] = packages_data
                    self._save_to_cache(repo_key, packages_data)
                    result.providers[repo_key] = True
                else:
                    result.success = False
                    result.providers[repo_key] = False
                    result.errors[repo_key] = "Failed to fetch packagesite"
            
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
                    description=pkg_data.get("comment"),
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
                    (pkg_data.get("comment") and query_lower in pkg_data["comment"].lower()) or
                    (pkg_data.get("desc") and query_lower in pkg_data["desc"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = PackageInfo(
                        name=pkg_name,
                        provider=self.get_repository_name(),
                        version=pkg_data.get("version"),
                        description=pkg_data.get("comment"),
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
                if "deps" in pkg_data:
                    for dep_name in pkg_data["deps"]:
                        dependencies.append(dep_name)
                
                return PackageDetails(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("version"),
                    description=pkg_data.get("comment"),
                    license=pkg_data.get("license"),
                    homepage=pkg_data.get("www"),
                    dependencies=dependencies,
                    maintainer=pkg_data.get("maintainer"),
                    source_url=pkg_data.get("www"),
                    download_url=None,
                    checksum=pkg_data.get("sum"),
                    raw_data=pkg_data
                )
        
        return None
    
    def _fetch_packagesite(self, repo: PkgRepository) -> Dict[str, Dict[str, any]]:
        """
        Fetch and parse a packagesite file from a pkg repository.
        
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
            
            # Create a temporary directory for the packagesite
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download the packagesite.txz file
                packagesite_path = os.path.join(temp_dir, "packagesite.txz")
                
                try:
                    self._fetch_binary("packagesite.txz", packagesite_path)
                except Exception as e:
                    logger.warning(f"Failed to fetch packagesite.txz: {e}")
                    return {}
                
                # Extract the packagesite.txz file
                import tarfile
                try:
                    with tarfile.open(packagesite_path, 'r:xz') as tar:
                        tar.extractall(path=temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to extract packagesite.txz: {e}")
                    return {}
                
                # Parse the packagesite.yaml file
                packagesite_yaml_path = os.path.join(temp_dir, "packagesite.yaml")
                if not os.path.exists(packagesite_yaml_path):
                    logger.warning(f"packagesite.yaml not found in {packagesite_path}")
                    return {}
                
                return self._parse_packagesite_yaml(packagesite_yaml_path)
            
        except Exception as e:
            logger.warning(f"Failed to fetch packagesite for {repo.name}: {e}")
            return {}
        finally:
            # Restore the original base_url
            self.base_url = original_base_url
    
    def _parse_packagesite_yaml(self, packagesite_path: str) -> Dict[str, Dict[str, any]]:
        """
        Parse a packagesite.yaml file from a pkg repository.
        
        Args:
            packagesite_path: Path to the packagesite.yaml file.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        
        try:
            # Read the packagesite.yaml file
            with open(packagesite_path, 'r', encoding='utf-8') as f:
                # The file contains one JSON object per line
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Parse the JSON object
                    pkg_data = json.loads(line)
                    
                    # Extract package name
                    pkg_name = pkg_data.get("name")
                    if pkg_name:
                        result[pkg_name] = pkg_data
        
        except Exception as e:
            logger.warning(f"Failed to parse packagesite.yaml: {e}")
        
        return result