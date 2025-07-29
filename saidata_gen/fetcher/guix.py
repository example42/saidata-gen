"""
Guix repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from GNU Guix
by executing guix commands and parsing their output.
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


class GuixFetcher(RepositoryFetcher):
    """
    Fetcher for GNU Guix packages.
    
    This class fetches package metadata from GNU Guix by executing guix commands
    and parsing their output. This fetcher requires the guix command to be
    available on the system.
    """
    
    def __init__(self, config: Optional[FetcherConfig] = None):
        """
        Initialize the Guix fetcher.
        
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
        
        # Check for guix command availability (required for this fetcher)
        self.guix_available = self.dependency_checker.check_command_availability("guix")
        if not self.guix_available:
            self.dependency_checker.log_missing_dependency("guix", "guix")
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, any]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "guix"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Guix.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        try:
            # Check if we have a valid cache
            cached_data = self._get_from_cache("guix_packages")
            
            if cached_data:
                self._package_cache = cached_data
                result.cache_hits["guix"] = True
                return result
            
            # Check if guix is available
            if not self._is_guix_available():
                result.success = False
                result.providers["guix"] = False
                result.errors["guix"] = "guix command not available"
                return result
            
            # Fetch packages
            packages_data = self._fetch_packages()
            if packages_data:
                self._package_cache = packages_data
                self._save_to_cache("guix_packages", packages_data)
                result.providers["guix"] = True
            else:
                result.success = False
                result.providers["guix"] = False
                result.errors["guix"] = "No packages found"
        
        except Exception as e:
            logger.error(f"Failed to fetch repository data from Guix: {e}")
            result.errors["guix"] = str(e)
            result.providers["guix"] = False
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
        
        # If not found, try to get info directly from guix
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
        
        # If we don't have enough results, try searching with guix
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
    
    def _is_guix_available(self) -> bool:
        """
        Check if the guix command is available.
        
        Returns:
            True if guix is available, False otherwise.
        """
        try:
            subprocess.run(["guix", "--version"], check=True, capture_output=True)
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
            # Run guix package --list-available in JSON format
            cmd_result = subprocess.run(
                ["guix", "package", "--list-available", "--format=json"],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Parse the JSON output
            packages = json.loads(cmd_result.stdout)
            
            for pkg in packages:
                name = pkg.get("name")
                if name:
                    result[name] = {
                        "version": pkg.get("version"),
                        "description": pkg.get("description"),
                        "synopsis": pkg.get("synopsis"),
                        "license": pkg.get("license"),
                        "homepage": pkg.get("home-page"),
                        "location": pkg.get("location")
                    }
        
        except Exception as e:
            logger.warning(f"Failed to fetch packages: {e}")
            
            # Try alternative approach with guix package -A
            try:
                cmd_result = subprocess.run(
                    ["guix", "package", "-A"],
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
                    pkg_match = re.match(r'([a-z0-9_-]+)\s+([0-9][0-9a-z_.-]*)', line)
                    if pkg_match:
                        # Save previous package
                        if current_package and current_data:
                            result[current_package] = current_data
                        
                        # Start new package
                        current_package = pkg_match.group(1)
                        current_data = {"version": pkg_match.group(2)}
                        
                        # Extract description (rest of the line)
                        desc_start = line.find(current_data["version"]) + len(current_data["version"])
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
            # Run guix show in JSON format
            cmd_result = subprocess.run(
                ["guix", "show", "--format=json", package_name],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Parse the JSON output
            pkg_data = json.loads(cmd_result.stdout)
            
            # Extract relevant fields
            return {
                "version": pkg_data.get("version"),
                "description": pkg_data.get("description"),
                "synopsis": pkg_data.get("synopsis"),
                "license": pkg_data.get("license"),
                "homepage": pkg_data.get("home-page"),
                "location": pkg_data.get("location"),
                "dependencies": pkg_data.get("dependencies", []),
                "inputs": pkg_data.get("inputs", [])
            }
            
        except Exception as e:
            logger.warning(f"Failed to fetch package info for {package_name}: {e}")
            
            # Try alternative approach with guix show
            try:
                cmd_result = subprocess.run(
                    ["guix", "show", package_name],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Parse the output
                pkg_data = {}
                
                for line in cmd_result.stdout.splitlines():
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    # Extract version
                    version_match = re.match(r'version: ([0-9][0-9a-z_.-]*)', line)
                    if version_match:
                        pkg_data["version"] = version_match.group(1)
                        continue
                    
                    # Extract description
                    if line.startswith("description:"):
                        pkg_data["description"] = line[12:].strip()
                        continue
                    
                    # Extract license
                    license_match = re.match(r'license: (.+)', line)
                    if license_match:
                        pkg_data["license"] = license_match.group(1)
                        continue
                    
                    # Extract homepage
                    homepage_match = re.match(r'home page: (.+)', line)
                    if homepage_match:
                        pkg_data["homepage"] = homepage_match.group(1)
                        continue
                
                return pkg_data
                
            except Exception as e2:
                logger.warning(f"Failed to fetch package info with alternative approach: {e2}")
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
            # Run guix search in JSON format
            cmd_result = subprocess.run(
                ["guix", "search", "--format=json", query],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Parse the JSON output
            packages = json.loads(cmd_result.stdout)
            
            count = 0
            for pkg in packages:
                name = pkg.get("name")
                if name:
                    result[name] = {
                        "version": pkg.get("version"),
                        "description": pkg.get("description"),
                        "synopsis": pkg.get("synopsis"),
                        "license": pkg.get("license"),
                        "homepage": pkg.get("home-page"),
                        "location": pkg.get("location")
                    }
                    
                    count += 1
                    if count >= max_results:
                        break
        
        except Exception as e:
            logger.warning(f"Failed to search packages for {query}: {e}")
            
            # Try alternative approach with guix search
            try:
                cmd_result = subprocess.run(
                    ["guix", "search", query],
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
                    pkg_match = re.match(r'([a-z0-9_-]+)\s+([0-9][0-9a-z_.-]*)', line)
                    if pkg_match:
                        # Save previous package
                        if current_package and current_data:
                            result[current_package] = current_data
                            count += 1
                            
                            if count >= max_results:
                                break
                        
                        # Start new package
                        current_package = pkg_match.group(1)
                        current_data = {"version": pkg_match.group(2)}
                        
                        # Extract description (rest of the line)
                        desc_start = line.find(current_data["version"]) + len(current_data["version"])
                        if desc_start < len(line):
                            current_data["description"] = line[desc_start:].strip()
                        
                        continue
                
                # Save the last package
                if current_package and current_data and count < max_results:
                    result[current_package] = current_data
            
            except Exception as e2:
                logger.warning(f"Failed to search packages with alternative approach: {e2}")
        
        return result