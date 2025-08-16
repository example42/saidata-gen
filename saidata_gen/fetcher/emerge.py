"""
Emerge repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from Gentoo's
emerge tool by parsing the output of emerge commands.
"""

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
from saidata_gen.fetcher.error_handler import FetcherErrorHandler, ErrorContext
from saidata_gen.core.system_dependency_checker import SystemDependencyChecker


logger = logging.getLogger(__name__)


class EmergeFetcher(RepositoryFetcher):
    """
    Fetcher for Gentoo's emerge tool.
    
    This class fetches package metadata from Gentoo's emerge tool by executing
    emerge commands and parsing their output. This fetcher requires the emerge
    command to be available on the system.
    """
    
    def __init__(self, config: Optional[FetcherConfig] = None):
        """
        Initialize the Emerge fetcher.
        
        Args:
            config: Configuration for the fetcher.
        """
        super().__init__(config)
        
        # Initialize error handler and system dependency checker
        self.error_handler = FetcherErrorHandler(max_retries=3, base_wait_time=1.0)
        self.dependency_checker = SystemDependencyChecker()
        
        # Check for emerge command availability (required for this fetcher)
        self.emerge_available = self.dependency_checker.check_command_availability("emerge")
        if not self.emerge_available:
            self.dependency_checker.log_missing_dependency("emerge", "emerge")
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, any]] = {}
        self._category_cache: List[str] = []
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "emerge"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from emerge.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        # Check if we have a valid cache
        cached_data = self._get_from_cache("emerge_packages")
        cached_categories = self._get_from_cache("emerge_categories")
        
        if cached_data and cached_categories:
            self._package_cache = cached_data
            self._category_cache = cached_categories
            result.cache_hits["emerge"] = True
            return result
        
        # Check if emerge is available with graceful degradation
        if not self.emerge_available:
            return FetchResult(
                success=False,
                providers={"emerge": False},
                errors={"emerge": "emerge command not available - skipping Gentoo package fetching"},
                cache_hits={}
            )
        
        # Fetch repository data with enhanced error handling
        return self._fetch_emerge_data_with_retries()
    
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
        
        # Try with category prefix
        for full_name, pkg_data in self._package_cache.items():
            if full_name.endswith(f"/{package_name}"):
                return self._create_package_info(full_name, pkg_data)
        
        # If not found, try to get info directly from emerge
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
        
        # If we don't have enough results, try searching with emerge
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
    
    def _is_emerge_available(self) -> bool:
        """
        Check if the emerge command is available.
        
        Returns:
            True if emerge is available, False otherwise.
        """
        try:
            subprocess.run(["emerge", "--version"], check=True, capture_output=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _fetch_categories(self) -> List[str]:
        """
        Fetch the list of package categories.
        
        Returns:
            List of package categories.
        """
        try:
            # Run emerge --info to get the portage directory
            result = subprocess.run(
                ["emerge", "--info"],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Extract PORTDIR from the output
            portdir_match = re.search(r'PORTDIR="([^"]+)"', result.stdout)
            if not portdir_match:
                logger.warning("Failed to find PORTDIR in emerge --info output")
                return []
            
            portdir = portdir_match.group(1)
            
            # List directories in PORTDIR
            categories = []
            for item in os.listdir(portdir):
                category_path = os.path.join(portdir, item)
                
                # Skip non-directories and special directories
                if not os.path.isdir(category_path) or item.startswith(".") or item in ["eclass", "profiles", "metadata"]:
                    continue
                
                categories.append(item)
            
            return categories
            
        except Exception as e:
            logger.warning(f"Failed to fetch categories: {e}")
            return []
    
    def _fetch_category_packages(self, category: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch packages for a specific category.
        
        Args:
            category: Package category.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        
        try:
            # Run emerge --search to get packages in the category
            cmd_result = subprocess.run(
                ["emerge", "--search", f"^{category}/"],
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
                pkg_match = re.match(r'\*\s+([a-z0-9_-]+/[a-z0-9_-]+)', line)
                if pkg_match:
                    # Save previous package
                    if current_package and current_data:
                        result[current_package] = current_data
                    
                    # Start new package
                    current_package = pkg_match.group(1)
                    current_data = {}
                    continue
                
                # Check for version
                version_match = re.match(r'Latest version available: ([0-9][0-9a-z_.-]*)', line)
                if version_match:
                    current_data["version"] = version_match.group(1)
                    continue
                
                # Check for description
                desc_match = re.match(r'Description:\s+(.+)', line)
                if desc_match:
                    current_data["description"] = desc_match.group(1)
                    continue
                
                # Check for homepage
                homepage_match = re.match(r'Homepage:\s+(.+)', line)
                if homepage_match:
                    current_data["homepage"] = homepage_match.group(1)
                    continue
                
                # Check for license
                license_match = re.match(r'License:\s+(.+)', line)
                if license_match:
                    current_data["license"] = license_match.group(1)
                    continue
            
            # Save the last package
            if current_package and current_data:
                result[current_package] = current_data
        
        except Exception as e:
            logger.warning(f"Failed to fetch packages for category {category}: {e}")
        
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
            # Run emerge --pretend --verbose to get package info
            cmd_result = subprocess.run(
                ["emerge", "--pretend", "--verbose", package_name],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Parse the output
            pkg_data = {}
            
            # Extract package name and version
            pkg_match = re.search(r'\[ebuild[^\]]*\]\s+([a-z0-9_-]+/[a-z0-9_-]+-[0-9][0-9a-z_.-]*)', cmd_result.stdout)
            if pkg_match:
                full_name = pkg_match.group(1)
                
                # Extract version
                version_match = re.search(r'-([0-9][0-9a-z_.-]*)$', full_name)
                if version_match:
                    pkg_data["version"] = version_match.group(1)
            
            # Extract USE flags
            use_match = re.search(r'USE="([^"]*)"', cmd_result.stdout)
            if use_match:
                pkg_data["use_flags"] = use_match.group(1)
            
            # Run emerge --info to get more details
            cmd_result = subprocess.run(
                ["emerge", "--info", package_name],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Extract description
            desc_match = re.search(r'DESCRIPTION="([^"]*)"', cmd_result.stdout)
            if desc_match:
                pkg_data["description"] = desc_match.group(1)
            
            # Extract homepage
            homepage_match = re.search(r'HOMEPAGE="([^"]*)"', cmd_result.stdout)
            if homepage_match:
                pkg_data["homepage"] = homepage_match.group(1)
            
            # Extract license
            license_match = re.search(r'LICENSE="([^"]*)"', cmd_result.stdout)
            if license_match:
                pkg_data["license"] = license_match.group(1)
            
            return pkg_data
            
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
            # Run emerge --search to search for packages
            cmd_result = subprocess.run(
                ["emerge", "--search", query],
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
                pkg_match = re.match(r'\*\s+([a-z0-9_-]+/[a-z0-9_-]+)', line)
                if pkg_match:
                    # Save previous package
                    if current_package and current_data:
                        result[current_package] = current_data
                        count += 1
                        
                        if count >= max_results:
                            break
                    
                    # Start new package
                    current_package = pkg_match.group(1)
                    current_data = {}
                    continue
                
                # Check for version
                version_match = re.match(r'Latest version available: ([0-9][0-9a-z_.-]*)', line)
                if version_match:
                    current_data["version"] = version_match.group(1)
                    continue
                
                # Check for description
                desc_match = re.match(r'Description:\s+(.+)', line)
                if desc_match:
                    current_data["description"] = desc_match.group(1)
                    continue
                
                # Check for homepage
                homepage_match = re.match(r'Homepage:\s+(.+)', line)
                if homepage_match:
                    current_data["homepage"] = homepage_match.group(1)
                    continue
                
                # Check for license
                license_match = re.match(r'License:\s+(.+)', line)
                if license_match:
                    current_data["license"] = license_match.group(1)
                    continue
            
            # Save the last package
            if current_package and current_data and count < max_results:
                result[current_package] = current_data
        
        except Exception as e:
            logger.warning(f"Failed to search packages for {query}: {e}")
        
        return result
    
    def _fetch_emerge_data_with_retries(self) -> FetchResult:
        """
        Fetch emerge data with enhanced error handling and retries.
        
        Returns:
            FetchResult with the outcome.
        """
        max_attempts = 2  # Reduce attempts for command-line operations
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Create error context
                context = ErrorContext(
                    provider="emerge",
                    url="local_emerge_command",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    additional_info={"operation": "fetch_categories"}
                )
                
                # Fetch categories with system dependency checking
                categories = self._fetch_categories_with_dependency_check()
                if not categories:
                    if attempt == max_attempts:
                        return FetchResult(
                            success=False,
                            providers={"emerge": False},
                            errors={"emerge": "Failed to fetch categories"},
                            cache_hits={}
                        )
                    continue
                
                self._category_cache = categories
                
                # Fetch packages for each category with graceful degradation
                packages_data = {}
                failed_categories = []
                
                for category in categories:
                    try:
                        category_packages = self._fetch_category_packages_with_retries(category)
                        packages_data.update(category_packages)
                    except Exception as e:
                        failed_categories.append(category)
                        logger.warning(f"Failed to fetch packages for category {category}: {e}")
                
                if packages_data:
                    self._package_cache = packages_data
                    self._save_to_cache("emerge_packages", packages_data)
                    self._save_to_cache("emerge_categories", categories)
                    
                    # Log graceful degradation if some categories failed
                    if failed_categories:
                        logger.info(f"Successfully fetched emerge data with {len(failed_categories)} failed categories")
                    
                    return FetchResult(
                        success=True,
                        providers={"emerge": True},
                        errors={},
                        cache_hits={}
                    )
                else:
                    if attempt == max_attempts:
                        return FetchResult(
                            success=False,
                            providers={"emerge": False},
                            errors={"emerge": "No packages found"},
                            cache_hits={}
                        )
                        
            except Exception as e:
                logger.warning(f"Emerge fetch attempt {attempt} failed: {e}")
                if attempt == max_attempts:
                    return FetchResult(
                        success=False,
                        providers={"emerge": False},
                        errors={"emerge": f"Error: {str(e)}"},
                        cache_hits={}
                    )
        
        # Should not reach here, but just in case
        return FetchResult(
            success=False,
            providers={"emerge": False},
            errors={"emerge": "Max retries exceeded"},
            cache_hits={}
        )
    
    def _fetch_categories_with_dependency_check(self) -> List[str]:
        """
        Fetch categories with system dependency checking.
        
        Returns:
            List of categories.
        """
        # Validate emerge command is available
        if not self.dependency_checker.validate_provider_dependencies("emerge", ["emerge"]):
            return []
        
        try:
            return self._fetch_categories()
        except subprocess.SubprocessError as e:
            logger.warning(f"Emerge command failed: {e}")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch emerge categories: {e}")
            return []
    
    def _fetch_category_packages_with_retries(self, category: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch category packages with retry logic.
        
        Args:
            category: Package category.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        max_attempts = 2
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Execute emerge command safely
                result = self.dependency_checker.execute_command_safely(
                    ["emerge", "--search", f"^{category}/"],
                    "emerge",
                    timeout=60  # Longer timeout for emerge operations
                )
                
                if result is None:
                    if attempt == max_attempts:
                        logger.warning(f"Failed to execute emerge command for category {category}")
                        return {}
                    continue
                
                if result.returncode != 0:
                    logger.warning(f"Emerge search returned non-zero exit code for {category}: {result.returncode}")
                    if attempt == max_attempts:
                        return {}
                    continue
                
                # Parse the output
                return self._parse_emerge_search_output(result.stdout, category)
                
            except Exception as e:
                logger.warning(f"Failed to fetch packages for category {category} on attempt {attempt}: {e}")
                if attempt == max_attempts:
                    return {}
        
        return {}
    
    def _parse_emerge_search_output(self, output: str, category: str) -> Dict[str, Dict[str, any]]:
        """
        Parse emerge search output with error handling.
        
        Args:
            output: Command output.
            category: Package category.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        current_package = None
        current_data = {}
        
        try:
            for line in output.splitlines():
                line = line.strip()
                
                if not line:
                    continue
                
                # Check for package header
                pkg_match = re.match(r'\*\s+([a-z0-9_-]+/[a-z0-9_-]+)', line)
                if pkg_match:
                    # Save previous package
                    if current_package and current_data:
                        result[current_package] = current_data
                    
                    # Start new package
                    current_package = pkg_match.group(1)
                    current_data = {}
                    continue
                
                # Parse package information with error handling
                self._parse_package_line(line, current_data)
            
            # Save the last package
            if current_package and current_data:
                result[current_package] = current_data
                
        except Exception as e:
            logger.warning(f"Failed to parse emerge output for category {category}: {e}")
        
        return result
    
    def _parse_package_line(self, line: str, current_data: Dict[str, any]) -> None:
        """
        Parse a single line of emerge output.
        
        Args:
            line: Line to parse.
            current_data: Current package data dictionary to update.
        """
        try:
            # Check for version
            version_match = re.match(r'Latest version available: ([0-9][0-9a-z_.-]*)', line)
            if version_match:
                current_data["version"] = version_match.group(1)
                return
            
            # Check for description
            desc_match = re.match(r'Description:\s+(.+)', line)
            if desc_match:
                current_data["description"] = desc_match.group(1)
                return
            
            # Check for homepage
            homepage_match = re.match(r'Homepage:\s+(.+)', line)
            if homepage_match:
                current_data["homepage"] = homepage_match.group(1)
                return
            
            # Check for license
            license_match = re.match(r'License:\s+(.+)', line)
            if license_match:
                current_data["license"] = license_match.group(1)
                return
                
        except Exception as e:
            logger.debug(f"Failed to parse emerge line '{line}': {e}")