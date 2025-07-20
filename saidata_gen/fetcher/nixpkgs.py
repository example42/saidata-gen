"""
Nixpkgs repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from Nixpkgs
collection by cloning the repository and parsing package definitions.
"""

import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import GitRepositoryFetcher


logger = logging.getLogger(__name__)


@dataclass
class NixpkgsRepository:
    """
    Configuration for a Nixpkgs repository.
    """
    name: str  # e.g., "nixpkgs"
    url: str  # e.g., "https://github.com/NixOS/nixpkgs.git"
    branch: str = "master"  # Default branch


class NixpkgsFetcher(GitRepositoryFetcher):
    """
    Fetcher for Nixpkgs collection.
    
    This class fetches package metadata from Nixpkgs collection by cloning
    the repository and parsing package definitions.
    """
    
    def __init__(
        self,
        repositories: Optional[List[NixpkgsRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Nixpkgs fetcher.
        
        Args:
            repositories: List of Nixpkgs repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Set up default repositories if none provided
        self.repositories = repositories or [
            NixpkgsRepository(
                name="nixpkgs",
                url="https://github.com/NixOS/nixpkgs.git"
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
        return "nixpkgs"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Nixpkgs repositories.
        
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
                packages_data = self._parse_nixpkgs_repository()
                if packages_data:
                    self._package_cache[repo_key] = packages_data
                    self._save_to_cache(repo_key, packages_data)
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
            
            # Try with attribute path
            for attr_path, pkg_data in packages.items():
                if attr_path.endswith(f".{package_name}") or attr_path == package_name:
                    return self._create_package_info(package_name, pkg_data)
        
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
            for attr_path, pkg_data in packages.items():
                # Extract package name from attribute path
                pkg_name = attr_path.split(".")[-1]
                
                # Check if the package name or description contains the query
                if (query_lower in pkg_name.lower() or 
                    (pkg_data.get("description") and query_lower in pkg_data["description"].lower())):
                    
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
            version=package_data.get("version"),
            description=package_data.get("description"),
            details=package_data
        )
    
    def _parse_nixpkgs_repository(self) -> Dict[str, Dict[str, any]]:
        """
        Parse a Nixpkgs repository.
        
        Returns:
            Dictionary mapping package attribute paths to their metadata.
        """
        packages = {}
        
        try:
            # Check if nix is available
            if not self._is_nix_available():
                logger.warning("nix command not available, using fallback parsing method")
                return self._parse_nixpkgs_repository_fallback()
            
            # Use nix-env to list all packages in the repository
            with tempfile.NamedTemporaryFile(suffix='.nix') as temp_file:
                # Create a temporary Nix expression that imports the repository
                temp_file.write(f'import {self.repo_dir} {{}}'.encode('utf-8'))
                temp_file.flush()
                
                # Run nix-env to list all packages
                cmd_result = subprocess.run(
                    ["nix-env", "-f", temp_file.name, "-qa", "--json"],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Parse the JSON output
                nix_packages = json.loads(cmd_result.stdout)
                
                for attr_path, pkg_data in nix_packages.items():
                    # Extract package name
                    name = pkg_data.get("name")
                    if name:
                        # Remove version from name
                        name_parts = name.split("-")
                        version = None
                        
                        # Find the first part that looks like a version
                        for i, part in enumerate(name_parts):
                            if re.match(r'^[0-9]', part):
                                version = "-".join(name_parts[i:])
                                name = "-".join(name_parts[:i])
                                break
                        
                        # If no version found, use the original version
                        if not version:
                            version = pkg_data.get("version")
                        
                        packages[attr_path] = {
                            "name": name,
                            "version": version,
                            "description": pkg_data.get("meta", {}).get("description"),
                            "license": pkg_data.get("meta", {}).get("license"),
                            "homepage": pkg_data.get("meta", {}).get("homepage"),
                            "position": pkg_data.get("meta", {}).get("position"),
                            "attr_path": attr_path
                        }
        
        except Exception as e:
            logger.warning(f"Failed to parse Nixpkgs repository using nix-env: {e}")
            # Fallback to parsing the repository manually
            return self._parse_nixpkgs_repository_fallback()
        
        return packages
    
    def _parse_nixpkgs_repository_fallback(self) -> Dict[str, Dict[str, any]]:
        """
        Parse a Nixpkgs repository using a fallback method.
        
        This method parses the repository by scanning for default.nix files
        and extracting basic metadata from them.
        
        Returns:
            Dictionary mapping package attribute paths to their metadata.
        """
        packages = {}
        
        try:
            # Find all default.nix files in the pkgs directory
            pkgs_dir = os.path.join(self.repo_dir, "pkgs")
            if not os.path.exists(pkgs_dir):
                logger.warning(f"pkgs directory not found in {self.repo_dir}")
                return packages
            
            # Walk through the pkgs directory
            for root, dirs, files in os.walk(pkgs_dir):
                if "default.nix" in files:
                    # Extract relative path from pkgs directory
                    rel_path = os.path.relpath(root, pkgs_dir)
                    if rel_path == ".":
                        continue
                    
                    # Convert path to attribute path
                    attr_path = rel_path.replace(os.path.sep, ".")
                    
                    # Extract package name from attribute path
                    pkg_name = attr_path.split(".")[-1]
                    
                    # Read the default.nix file
                    default_nix_path = os.path.join(root, "default.nix")
                    with open(default_nix_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Extract basic metadata
                    pkg_data = {
                        "name": pkg_name,
                        "attr_path": attr_path
                    }
                    
                    # Extract version
                    version_match = re.search(r'version\s*=\s*"([^"]*)"', content)
                    if version_match:
                        pkg_data["version"] = version_match.group(1)
                    
                    # Extract description
                    desc_match = re.search(r'description\s*=\s*"([^"]*)"', content)
                    if desc_match:
                        pkg_data["description"] = desc_match.group(1)
                    
                    # Extract homepage
                    homepage_match = re.search(r'homepage\s*=\s*"([^"]*)"', content)
                    if homepage_match:
                        pkg_data["homepage"] = homepage_match.group(1)
                    
                    # Extract license
                    license_match = re.search(r'license\s*=\s*([^;]*);', content)
                    if license_match:
                        pkg_data["license"] = license_match.group(1).strip()
                    
                    # Add package to result
                    packages[attr_path] = pkg_data
        
        except Exception as e:
            logger.warning(f"Failed to parse Nixpkgs repository using fallback method: {e}")
        
        return packages
    
    def _is_nix_available(self) -> bool:
        """
        Check if the nix command is available.
        
        Returns:
            True if nix is available, False otherwise.
        """
        try:
            subprocess.run(["nix", "--version"], check=True, capture_output=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False