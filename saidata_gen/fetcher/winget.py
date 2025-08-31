"""
Winget repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from the Windows
Package Manager (winget) repository.
"""

import logging
import os
import yaml
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import GitRepositoryFetcher


logger = logging.getLogger(__name__)


@dataclass
class WingetRepository:
    """
    Configuration for a Winget repository.
    """
    name: str  # e.g., "winget-pkgs"
    url: str  # e.g., "https://github.com/microsoft/winget-pkgs.git"
    branch: str = "master"  # Default branch


class WingetFetcher(GitRepositoryFetcher):
    """
    Fetcher for Windows Package Manager (winget) repositories.
    
    This class fetches package metadata from winget repositories by cloning
    and processing the YAML manifests.
    """
    
    def __init__(
        self,
        repositories: Optional[List[WingetRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Winget fetcher.
        
        Args:
            repositories: List of Winget repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Use the main winget-pkgs repository as default
        self.repositories = repositories or [
            WingetRepository(
                name="winget-pkgs",
                url="https://github.com/microsoft/winget-pkgs.git",
                branch="master"
            )
        ]
        
        # Initialize with the first repository
        super().__init__(
            repository_url=self.repositories[0].url,
            branch=self.repositories[0].branch,
            config=config
        )
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, Dict[str, any]]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "winget"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Winget repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for repo in self.repositories:
            try:
                # Update repository URL and branch
                self.repository_url = repo.url
                self.branch = repo.branch
                
                # Clone or pull the repository
                if not self._clone_or_pull_repository():
                    result.success = False
                    result.providers[repo.name] = False
                    result.errors[repo.name] = "Failed to clone or pull repository"
                    continue
                
                # Process manifests
                manifests = self._process_manifests()
                if manifests:
                    self._package_cache[repo.name] = manifests
                    result.providers[repo.name] = True
                else:
                    result.success = False
                    result.providers[repo.name] = False
                    result.errors[repo.name] = "No manifests found"
            
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
                return self._create_package_info(package_name, pkg_data)
            
            # Try case-insensitive match
            for pkg_name, pkg_data in packages.items():
                if pkg_name.lower() == package_name.lower():
                    return self._create_package_info(pkg_name, pkg_data)
        
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
                # Check if the package name, publisher, or description contains the query
                if (query_lower in pkg_name.lower() or
                    (pkg_data.get("Publisher") and query_lower in pkg_data["Publisher"].lower()) or
                    (pkg_data.get("Description") and query_lower in pkg_data["Description"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = self._create_package_info(pkg_name, pkg_data)
                    
                    # Add to results if not already present
                    if not any(r.name == pkg_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
        
        return results
    
    def _create_package_info(self, package_name: str, package_data: Dict[str, any]) -> PackageInfo:
        """
        Create a PackageInfo object from package data.
        
        Args:
            package_name: Name of the package.
            package_data: Package data.
            
        Returns:
            PackageInfo object.
        """
        return PackageInfo(
            name=package_name,
            provider=self.get_repository_name(),
            version=package_data.get("PackageVersion"),
            description=package_data.get("Description"),
            details=package_data
        )
    
    def _process_manifests(self) -> Dict[str, Dict[str, any]]:
        """
        Process Winget manifests from the repository.
        
        Returns:
            Dictionary mapping package IDs to their metadata.
        """
        manifests_dir = os.path.join(self.repo_dir, "manifests")
        if not os.path.exists(manifests_dir):
            logger.warning(f"Manifests directory not found: {manifests_dir}")
            return {}
        
        result = {}
        
        # Walk through the manifests directory
        for root, dirs, files in os.walk(manifests_dir):
            for file in files:
                if file.endswith(".yaml") or file.endswith(".yml"):
                    try:
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            manifest = yaml.safe_load(f)
                        
                        # Extract package ID and metadata
                        if manifest and isinstance(manifest, dict):
                            # Winget manifests typically have PackageIdentifier
                            package_id = manifest.get("PackageIdentifier")
                            if not package_id:
                                # Try to extract from path
                                path_parts = os.path.relpath(file_path, manifests_dir).split(os.path.sep)
                                if len(path_parts) >= 3:
                                    # Format is typically manifests/p/Publisher/PackageName/Version/...
                                    publisher = path_parts[1]
                                    package_name = path_parts[2]
                                    package_id = f"{publisher}.{package_name}"
                            
                            if package_id:
                                # Merge with existing data if present
                                if package_id in result:
                                    result[package_id].update(manifest)
                                else:
                                    result[package_id] = manifest
                    
                    except Exception as e:
                        logger.warning(f"Failed to process manifest {file}: {e}")
        
        return result