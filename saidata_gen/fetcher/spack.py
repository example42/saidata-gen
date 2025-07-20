"""
Spack repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from Spack
package manager for HPC software.
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
class SpackRepository:
    """
    Configuration for a Spack repository.
    """
    name: str  # e.g., "spack"
    url: str  # e.g., "https://github.com/spack/spack.git"
    branch: str = "develop"  # Default branch


class SpackFetcher(GitRepositoryFetcher):
    """
    Fetcher for Spack package manager.
    
    This class fetches package metadata from Spack package manager by cloning
    the repository and parsing package definitions.
    """
    
    def __init__(
        self,
        repositories: Optional[List[SpackRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Spack fetcher.
        
        Args:
            repositories: List of Spack repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Set up default repositories if none provided
        self.repositories = repositories or [
            SpackRepository(
                name="spack",
                url="https://github.com/spack/spack.git"
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
        return "spack"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Spack repositories.
        
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
                packages_data = self._parse_spack_repository()
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
            if package_name in packages:
                pkg_data = packages[package_name]
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
            for pkg_name, pkg_data in packages.items():
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
            version=package_data.get("latest_version"),
            description=package_data.get("description"),
            details=package_data
        )
    
    def _parse_spack_repository(self) -> Dict[str, Dict[str, any]]:
        """
        Parse a Spack repository.
        
        Returns:
            Dictionary mapping package names to their metadata.
        """
        packages = {}
        
        try:
            # Check if spack is available
            if self._is_spack_available():
                # Try to use spack command to list packages
                return self._parse_spack_repository_with_command()
            else:
                logger.warning("spack command not available, using fallback parsing method")
                return self._parse_spack_repository_fallback()
        
        except Exception as e:
            logger.warning(f"Failed to parse Spack repository: {e}")
            # Fallback to parsing the repository manually
            return self._parse_spack_repository_fallback()
    
    def _parse_spack_repository_with_command(self) -> Dict[str, Dict[str, any]]:
        """
        Parse a Spack repository using the spack command.
        
        Returns:
            Dictionary mapping package names to their metadata.
        """
        packages = {}
        
        try:
            # Set up environment to use the cloned spack repository
            env = os.environ.copy()
            env["PATH"] = f"{os.path.join(self.repo_dir, 'bin')}:{env['PATH']}"
            
            # Run spack list --format=json to get all packages
            cmd_result = subprocess.run(
                ["spack", "list", "--format=json"],
                check=True,
                capture_output=True,
                text=True,
                env=env
            )
            
            # Parse the JSON output
            pkg_list = json.loads(cmd_result.stdout)
            
            # Get details for each package
            for pkg_name in pkg_list:
                try:
                    # Run spack info --json to get package details
                    info_result = subprocess.run(
                        ["spack", "info", "--json", pkg_name],
                        check=True,
                        capture_output=True,
                        text=True,
                        env=env
                    )
                    
                    # Parse the JSON output
                    pkg_info = json.loads(info_result.stdout)
                    
                    if pkg_name in pkg_info:
                        pkg_data = pkg_info[pkg_name]
                        
                        # Extract versions
                        versions = pkg_data.get("versions", [])
                        latest_version = versions[0] if versions else None
                        
                        packages[pkg_name] = {
                            "description": pkg_data.get("description"),
                            "homepage": pkg_data.get("homepage"),
                            "versions": versions,
                            "latest_version": latest_version,
                            "variants": pkg_data.get("variants", {}),
                            "dependencies": pkg_data.get("dependencies", [])
                        }
                except Exception as e:
                    logger.warning(f"Failed to get info for package {pkg_name}: {e}")
        
        except Exception as e:
            logger.warning(f"Failed to parse Spack repository using spack command: {e}")
            # Fallback to parsing the repository manually
            return self._parse_spack_repository_fallback()
        
        return packages
    
    def _parse_spack_repository_fallback(self) -> Dict[str, Dict[str, any]]:
        """
        Parse a Spack repository using a fallback method.
        
        This method parses the repository by scanning for package.py files
        and extracting basic metadata from them.
        
        Returns:
            Dictionary mapping package names to their metadata.
        """
        packages = {}
        
        try:
            # Find all package.py files in the var/spack/repos/builtin/packages directory
            packages_dir = os.path.join(self.repo_dir, "var", "spack", "repos", "builtin", "packages")
            if not os.path.exists(packages_dir):
                logger.warning(f"packages directory not found in {self.repo_dir}")
                return packages
            
            # Walk through the packages directory
            for pkg_dir in os.listdir(packages_dir):
                pkg_path = os.path.join(packages_dir, pkg_dir)
                
                # Skip non-directories
                if not os.path.isdir(pkg_path):
                    continue
                
                # Check for package.py file
                package_py_path = os.path.join(pkg_path, "package.py")
                if not os.path.exists(package_py_path):
                    continue
                
                # Read the package.py file
                with open(package_py_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract basic metadata
                pkg_data = {
                    "name": pkg_dir
                }
                
                # Extract description
                desc_match = re.search(r'description\s*=\s*[\'"]([^\'"]*)[\'"]', content)
                if desc_match:
                    pkg_data["description"] = desc_match.group(1)
                
                # Extract homepage
                homepage_match = re.search(r'homepage\s*=\s*[\'"]([^\'"]*)[\'"]', content)
                if homepage_match:
                    pkg_data["homepage"] = homepage_match.group(1)
                
                # Extract versions
                versions = []
                for version_match in re.finditer(r'version\([\'"]([^\'"]*)[\'"]', content):
                    versions.append(version_match.group(1))
                
                pkg_data["versions"] = versions
                pkg_data["latest_version"] = versions[0] if versions else None
                
                # Add package to result
                packages[pkg_dir] = pkg_data
        
        except Exception as e:
            logger.warning(f"Failed to parse Spack repository using fallback method: {e}")
        
        return packages
    
    def _is_spack_available(self) -> bool:
        """
        Check if the spack command is available.
        
        Returns:
            True if spack is available, False otherwise.
        """
        try:
            # Set up environment to use the cloned spack repository
            env = os.environ.copy()
            env["PATH"] = f"{os.path.join(self.repo_dir, 'bin')}:{env['PATH']}"
            
            subprocess.run(["spack", "--version"], check=True, capture_output=True, env=env)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False