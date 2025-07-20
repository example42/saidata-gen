"""
Portage repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from Gentoo
Portage repositories.
"""

import logging
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import GitRepositoryFetcher


logger = logging.getLogger(__name__)


@dataclass
class PortageRepository:
    """
    Configuration for a Portage repository.
    """
    name: str  # e.g., "gentoo"
    url: str  # e.g., "https://github.com/gentoo/gentoo.git"
    branch: str = "master"  # Default branch


class PortageFetcher(GitRepositoryFetcher):
    """
    Fetcher for Gentoo Portage repositories.
    
    This class fetches package metadata from Gentoo Portage repositories
    by cloning the repository and parsing ebuild files.
    """
    
    def __init__(
        self,
        repositories: Optional[List[PortageRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Portage fetcher.
        
        Args:
            repositories: List of Portage repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Set up default repositories if none provided
        self.repositories = repositories or [
            PortageRepository(
                name="gentoo",
                url="https://github.com/gentoo/gentoo.git"
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
        self._category_cache: Dict[str, List[str]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "portage"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Portage repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for repo in self.repositories:
            repo_key = repo.name
            try:
                # Check if we have a valid cache
                cached_data = self._get_from_cache(repo_key)
                cached_categories = self._get_from_cache(f"{repo_key}_categories")
                
                if cached_data and cached_categories:
                    self._package_cache[repo_key] = cached_data
                    self._category_cache[repo_key] = cached_categories
                    result.cache_hits[repo_key] = True
                    continue
                
                # Update repository URL and branch
                self.repository_url = repo.url
                self.branch = repo.branch
                
                # Clone or pull the repository
                if not self._clone_or_pull_repository():
                    result.success = False
                    result.providers[repo_key] = False
                    result.errors[repo_key] = "Failed to clone or pull repository"
                    continue
                
                # Parse the repository
                packages_data, categories = self._parse_portage_repository()
                if packages_data:
                    self._package_cache[repo_key] = packages_data
                    self._category_cache[repo_key] = categories
                    self._save_to_cache(repo_key, packages_data)
                    self._save_to_cache(f"{repo_key}_categories", categories)
                    result.providers[repo_key] = True
                else:
                    result.success = False
                    result.providers[repo_key] = False
                    result.errors[repo_key] = "No packages found"
            
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
            # Try exact match first
            if package_name in packages:
                pkg_data = packages[package_name]
                return self._create_package_info(package_name, pkg_data)
            
            # Try with category prefix
            for full_name, pkg_data in packages.items():
                if full_name.endswith(f"/{package_name}"):
                    return self._create_package_info(full_name, pkg_data)
        
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
                    (pkg_data.get("DESCRIPTION") and query_lower in pkg_data["DESCRIPTION"].lower())):
                    
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
            version=package_data.get("PV"),
            description=package_data.get("DESCRIPTION"),
            details=package_data
        )
    
    def _parse_portage_repository(self) -> Tuple[Dict[str, Dict[str, any]], List[str]]:
        """
        Parse a Portage repository.
        
        Returns:
            Tuple containing:
            - Dictionary mapping package names to their metadata.
            - List of categories.
        """
        packages = {}
        categories = []
        
        try:
            # Get all directories in the repository root (categories)
            for item in os.listdir(self.repo_dir):
                category_path = os.path.join(self.repo_dir, item)
                
                # Skip non-directories and special directories
                if not os.path.isdir(category_path) or item.startswith(".") or item in ["eclass", "profiles", "metadata"]:
                    continue
                
                categories.append(item)
                
                # Get all directories in the category (packages)
                for pkg in os.listdir(category_path):
                    pkg_path = os.path.join(category_path, pkg)
                    
                    # Skip non-directories and special files
                    if not os.path.isdir(pkg_path) or pkg.startswith("."):
                        continue
                    
                    # Get all ebuild files in the package directory
                    ebuilds = []
                    for file in os.listdir(pkg_path):
                        if file.endswith(".ebuild"):
                            ebuilds.append(file)
                    
                    if not ebuilds:
                        continue
                    
                    # Sort ebuilds by version (latest first)
                    ebuilds.sort(reverse=True)
                    
                    # Parse the latest ebuild
                    latest_ebuild = ebuilds[0]
                    ebuild_path = os.path.join(pkg_path, latest_ebuild)
                    
                    # Extract package metadata
                    pkg_data = self._parse_ebuild(ebuild_path)
                    
                    # Add package to result
                    full_name = f"{item}/{pkg}"
                    packages[full_name] = pkg_data
                    
                    # Also add metadata file if it exists
                    metadata_path = os.path.join(pkg_path, "metadata.xml")
                    if os.path.exists(metadata_path):
                        pkg_data["metadata_xml"] = self._get_file_content(os.path.relpath(metadata_path, self.repo_dir))
        
        except Exception as e:
            logger.error(f"Failed to parse Portage repository: {e}")
        
        return packages, categories
    
    def _parse_ebuild(self, ebuild_path: str) -> Dict[str, any]:
        """
        Parse an ebuild file.
        
        Args:
            ebuild_path: Path to the ebuild file.
            
        Returns:
            Dictionary with package metadata.
        """
        result = {}
        
        try:
            # Read the ebuild file
            with open(ebuild_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract package version from filename
            filename = os.path.basename(ebuild_path)
            pkg_name = os.path.splitext(filename)[0]
            version_match = re.search(r'-([0-9][0-9a-z_.-]*)$', pkg_name)
            if version_match:
                result["PV"] = version_match.group(1)
            
            # Extract common metadata fields
            for field in ["DESCRIPTION", "HOMEPAGE", "LICENSE", "KEYWORDS", "SLOT", "IUSE", "DEPEND", "RDEPEND"]:
                pattern = rf'{field}="([^"]*)"'
                match = re.search(pattern, content)
                if match:
                    result[field] = match.group(1)
                else:
                    # Try alternative syntax with single quotes
                    pattern = rf"{field}='([^']*)'"
                    match = re.search(pattern, content)
                    if match:
                        result[field] = match.group(1)
            
            # Extract dependencies
            if "DEPEND" in result:
                result["dependencies"] = self._parse_dependencies(result["DEPEND"])
            
            if "RDEPEND" in result:
                result["runtime_dependencies"] = self._parse_dependencies(result["RDEPEND"])
        
        except Exception as e:
            logger.warning(f"Failed to parse ebuild {ebuild_path}: {e}")
        
        return result
    
    def _parse_dependencies(self, depend_str: str) -> List[str]:
        """
        Parse a dependency string.
        
        Args:
            depend_str: Dependency string.
            
        Returns:
            List of dependencies.
        """
        dependencies = []
        
        # Split by whitespace and handle basic dependency syntax
        for dep in depend_str.split():
            # Skip operators and parentheses
            if dep in ["||", "(", ")", "?", "!"]:
                continue
            
            # Extract package name (remove version constraints and USE flags)
            match = re.search(r'([a-z0-9_-]+/[a-z0-9_-]+)', dep)
            if match:
                dependencies.append(match.group(1))
        
        return dependencies