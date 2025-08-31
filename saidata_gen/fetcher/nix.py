"""
Nix repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from Nix
by executing nix commands and parsing their output.
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
from saidata_gen.fetcher.base import RepositoryFetcher


logger = logging.getLogger(__name__)


class NixFetcher(RepositoryFetcher):
    """
    Fetcher for Nix packages.
    
    This class fetches package metadata from Nix by executing nix commands
    and parsing their output. This fetcher requires the nix command to be
    available on the system.
    """
    
    def __init__(self, config: Optional[FetcherConfig] = None):
        """
        Initialize the Nix fetcher.
        
        Args:
            config: Configuration for the fetcher.
        """
        super().__init__(config)
        
        # Import error handler and system dependency checker
        from saidata_gen.fetcher.error_handler import FetcherErrorHandler, ErrorContext
        from saidata_gen.core.system_dependency_checker import SystemDependencyChecker
        
        # Initialize error handler and system dependency checker
        self.error_handler = FetcherErrorHandler(max_retries=3, base_wait_time=1.0)
        self.dependency_checker = SystemDependencyChecker()
        
        # Check for nix command availability (required for this fetcher)
        self.nix_available = self.dependency_checker.check_command_availability("nix")
        if not self.nix_available:
            self.dependency_checker.log_missing_dependency("nix", "nix")
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, any]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "nix"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Nix.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        try:
            # Check if we have a valid cache
            cached_data = self._get_from_cache("nix_packages")
            
            if cached_data:
                self._package_cache = cached_data
                result.cache_hits["nix"] = True
                return result
            
            # Check if nix is available
            if not self._is_nix_available():
                result.success = False
                result.providers["nix"] = False
                result.errors["nix"] = "nix command not available"
                return result
            
            # Fetch packages
            packages_data = self._fetch_packages()
            if packages_data:
                self._package_cache = packages_data
                self._save_to_cache("nix_packages", packages_data)
                result.providers["nix"] = True
            else:
                result.success = False
                result.providers["nix"] = False
                result.errors["nix"] = "No packages found"
        
        except Exception as e:
            logger.error(f"Failed to fetch repository data from Nix: {e}")
            result.errors["nix"] = str(e)
            result.providers["nix"] = False
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
        
        # Try exact match first
        if package_name in self._package_cache:
            pkg_data = self._package_cache[package_name]
            return self._create_package_info(package_name, pkg_data)
        
        # If not found, try to get info directly from nix
        try:
            pkg_data = self._fetch_package_info(package_name)
            if pkg_data:
                return self._create_package_info(package_name, pkg_data)
        except Exception as e:
            logger.warning(f"Failed to fetch package info for {package_name}: {e}")
        
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
        
        # Search in cached packages
        for pkg_name, pkg_data in self._package_cache.items():
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
        
        # If we don't have enough results, try searching with nix
        if len(results) < max_results:
            try:
                search_results = self._search_packages(query, max_results - len(results))
                for pkg_name, pkg_data in search_results.items():
                    # Create PackageInfo object
                    pkg_info = self._create_package_info(pkg_name, pkg_data)
                    
                    # Add to results if not already present
                    if not any(r.name == pkg_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        break
            except Exception as e:
                logger.warning(f"Failed to search packages for {query}: {e}")
        
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
    
    def _fetch_packages(self) -> Dict[str, Dict[str, any]]:
        """
        Fetch the list of available packages.
        
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        
        try:
            # Run nix-env -qa --json to get all packages in JSON format
            cmd_result = subprocess.run(
                ["nix-env", "-qa", "--json"],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Parse the JSON output
            packages = json.loads(cmd_result.stdout)
            
            for attr_path, pkg_data in packages.items():
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
                    
                    # If no version found, use the original name
                    if not version:
                        version = pkg_data.get("version")
                    
                    result[name] = {
                        "version": version,
                        "description": pkg_data.get("meta", {}).get("description"),
                        "license": pkg_data.get("meta", {}).get("license"),
                        "homepage": pkg_data.get("meta", {}).get("homepage"),
                        "position": pkg_data.get("meta", {}).get("position"),
                        "attr_path": attr_path
                    }
        
        except Exception as e:
            logger.warning(f"Failed to fetch packages: {e}")
            
            # Try alternative approach with nix search
            try:
                cmd_result = subprocess.run(
                    ["nix", "search", "nixpkgs", "."],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Parse the output
                current_package = None
                current_data = {}
                
                for line in cmd_result.stdout.splitlines():
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    # Check for package header
                    pkg_match = re.match(r'(\S+)\s+\(([^)]+)\)', line)
                    if pkg_match:
                        # Save previous package
                        if current_package and current_data:
                            result[current_package] = current_data
                        
                        # Start new package
                        attr_path = pkg_match.group(1)
                        name = attr_path.split(".")[-1]
                        version = pkg_match.group(2)
                        
                        current_package = name
                        current_data = {"version": version, "attr_path": attr_path}
                        
                        # Extract description (rest of the line)
                        desc_start = line.find(")") + 1
                        if desc_start < len(line):
                            current_data["description"] = line[desc_start:].strip()
                        
                        continue
                
                # Save the last package
                if current_package and current_data:
                    result[current_package] = current_data
            
            except Exception as e2:
                logger.warning(f"Failed to fetch packages with alternative approach: {e2}")
        
        return result
    
    def _fetch_package_info(self, package_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch information about a specific package.
        
        Args:
            package_name: Name of the package to get information for.
            
        Returns:
            Dictionary with package metadata if found, None otherwise.
        """
        try:
            # Try to find the attribute path for the package
            attr_path = None
            
            # Check if we have the attribute path in the cache
            for name, data in self._package_cache.items():
                if name == package_name:
                    attr_path = data.get("attr_path")
                    break
            
            if not attr_path:
                # Try to find the attribute path using nix search
                cmd_result = subprocess.run(
                    ["nix", "search", "nixpkgs", f"^{package_name}$"],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Parse the output to find the attribute path
                for line in cmd_result.stdout.splitlines():
                    pkg_match = re.match(r'(\S+)\s+\(([^)]+)\)', line)
                    if pkg_match:
                        attr_path = pkg_match.group(1)
                        break
            
            if not attr_path:
                return None
            
            # Run nix-env -qa --json -A to get package info
            cmd_result = subprocess.run(
                ["nix-env", "-qa", "--json", "-A", attr_path],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Parse the JSON output
            packages = json.loads(cmd_result.stdout)
            
            if attr_path in packages:
                pkg_data = packages[attr_path]
                
                # Extract package name and version
                name = pkg_data.get("name")
                version = None
                
                if name:
                    # Remove version from name
                    name_parts = name.split("-")
                    
                    # Find the first part that looks like a version
                    for i, part in enumerate(name_parts):
                        if re.match(r'^[0-9]', part):
                            version = "-".join(name_parts[i:])
                            name = "-".join(name_parts[:i])
                            break
                
                # If no version found, use the original version
                if not version:
                    version = pkg_data.get("version")
                
                return {
                    "version": version,
                    "description": pkg_data.get("meta", {}).get("description"),
                    "license": pkg_data.get("meta", {}).get("license"),
                    "homepage": pkg_data.get("meta", {}).get("homepage"),
                    "position": pkg_data.get("meta", {}).get("position"),
                    "attr_path": attr_path
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to fetch package info for {package_name}: {e}")
            return None
    
    def _search_packages(self, query: str, max_results: int = 10) -> Dict[str, Dict[str, any]]:
        """
        Search for packages matching the query.
        
        Args:
            query: Search query.
            max_results: Maximum number of results to return.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        
        try:
            # Run nix search to search for packages
            cmd_result = subprocess.run(
                ["nix", "search", "nixpkgs", query],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Parse the output
            current_package = None
            current_data = {}
            count = 0
            
            for line in cmd_result.stdout.splitlines():
                line = line.strip()
                
                if not line:
                    continue
                
                # Check for package header
                pkg_match = re.match(r'(\S+)\s+\(([^)]+)\)', line)
                if pkg_match:
                    # Save previous package
                    if current_package and current_data:
                        result[current_package] = current_data
                        count += 1
                        
                        if count >= max_results:
                            break
                    
                    # Start new package
                    attr_path = pkg_match.group(1)
                    name = attr_path.split(".")[-1]
                    version = pkg_match.group(2)
                    
                    current_package = name
                    current_data = {"version": version, "attr_path": attr_path}
                    
                    # Extract description (rest of the line)
                    desc_start = line.find(")") + 1
                    if desc_start < len(line):
                        current_data["description"] = line[desc_start:].strip()
                    
                    continue
            
            # Save the last package
            if current_package and current_data and count < max_results:
                result[current_package] = current_data
        
        except Exception as e:
            logger.warning(f"Failed to search packages for {query}: {e}")
        
        return result