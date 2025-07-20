"""
NPM repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from the NPM
registry.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import HttpRepositoryFetcher


logger = logging.getLogger(__name__)


@dataclass
class NPMRegistry:
    """
    Configuration for an NPM registry.
    """
    name: str  # e.g., "npmjs"
    url: str  # e.g., "https://registry.npmjs.org/"


class NPMFetcher(HttpRepositoryFetcher):
    """
    Fetcher for NPM registry.
    
    This class fetches package metadata from NPM registries by querying
    their APIs.
    """
    
    def __init__(
        self,
        registries: Optional[List[NPMRegistry]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the NPM fetcher.
        
        Args:
            registries: List of NPM registries to fetch. If None, uses default registries.
            config: Configuration for the fetcher.
        """
        # Use the official NPM registry as default
        self.registries = registries or [
            NPMRegistry(
                name="npmjs",
                url="https://registry.npmjs.org/"
            )
        ]
        
        # Initialize with the first registry
        super().__init__(
            base_url=self.registries[0].url,
            config=config,
            headers={"Accept": "application/json"}
        )
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, Dict[str, any]]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "npm"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from NPM registries.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for registry in self.registries:
            try:
                # Update base URL
                self.base_url = registry.url
                
                # Fetch popular packages as a sample
                packages = self._fetch_popular_packages(registry.name)
                if packages:
                    self._package_cache[registry.name] = packages
                    result.providers[registry.name] = True
                else:
                    result.success = False
                    result.providers[registry.name] = False
                    result.errors[registry.name] = "No packages found"
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {registry.name}: {e}")
                result.errors[registry.name] = str(e)
                result.providers[registry.name] = False
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
        
        # Look for the package in all registries
        for registry_name, packages in self._package_cache.items():
            # Try exact match first
            if package_name in packages:
                pkg_data = packages[package_name]
                return self._create_package_info(package_name, pkg_data, registry_name)
            
            # Try case-insensitive match
            for pkg_name, pkg_data in packages.items():
                if pkg_name.lower() == package_name.lower():
                    return self._create_package_info(pkg_name, pkg_data, registry_name)
        
        # If not found in cache, try to fetch directly
        for registry in self.registries:
            try:
                self.base_url = registry.url
                package_data = self._fetch_package_details(package_name, registry.name)
                if package_data:
                    return self._create_package_info(package_name, package_data, registry.name)
            except Exception as e:
                logger.warning(f"Failed to fetch package details for {package_name} from {registry.name}: {e}")
        
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
        results = []
        
        # Search in all registries
        for registry in self.registries:
            try:
                self.base_url = registry.url
                search_results = self._search_packages_in_registry(query, registry.name, max_results - len(results))
                
                for pkg_name, pkg_data in search_results.items():
                    # Create PackageInfo object
                    pkg_info = self._create_package_info(pkg_name, pkg_data, registry.name)
                    
                    # Add to results if not already present
                    if not any(r.name == pkg_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
            
            except Exception as e:
                logger.warning(f"Failed to search packages in {registry.name}: {e}")
        
        return results
    
    def _create_package_info(self, package_name: str, package_data: Dict[str, any], registry_name: str) -> PackageInfo:
        """
        Create a PackageInfo object from package data.
        
        Args:
            package_name: Name of the package.
            package_data: Package data.
            registry_name: Name of the registry.
            
        Returns:
            PackageInfo object.
        """
        # Add registry information to details
        details = package_data.copy()
        details["registry"] = registry_name
        
        # Extract version
        version = "latest"
        if "version" in package_data:
            version = package_data["version"]
        elif "dist-tags" in package_data and "latest" in package_data["dist-tags"]:
            version = package_data["dist-tags"]["latest"]
        
        # Extract description
        description = ""
        if "description" in package_data:
            description = package_data["description"]
        
        return PackageInfo(
            name=package_name,
            provider=self.get_repository_name(),
            version=version,
            description=description,
            details=details
        )
    
    def _fetch_popular_packages(self, registry_name: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch popular packages from a registry.
        
        Args:
            registry_name: Name of the registry.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        # For NPM, we'll use a list of popular packages
        popular_packages = [
            "react", "express", "lodash", "axios", "moment",
            "vue", "angular", "jquery", "typescript", "next",
            "webpack", "babel", "eslint", "jest", "mocha"
        ]
        
        packages = {}
        for pkg_name in popular_packages:
            try:
                package_data = self._fetch_package_details(pkg_name, registry_name)
                if package_data:
                    packages[pkg_name] = package_data
            except Exception as e:
                logger.warning(f"Failed to fetch package details for {pkg_name} from {registry_name}: {e}")
        
        return packages
    
    def _fetch_package_details(self, package_name: str, registry_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch detailed information about a package.
        
        Args:
            package_name: Name of the package.
            registry_name: Name of the registry.
            
        Returns:
            Package metadata if found, None otherwise.
        """
        try:
            # Fetch package details from NPM registry
            response = self._fetch_json(package_name)
            
            if "name" in response:
                # Extract the latest version
                latest_version = response.get("dist-tags", {}).get("latest")
                
                # Get the latest version data
                version_data = {}
                if latest_version and latest_version in response.get("versions", {}):
                    version_data = response["versions"][latest_version]
                
                # Combine metadata
                return {
                    "name": response.get("name"),
                    "version": latest_version,
                    "description": response.get("description") or version_data.get("description", ""),
                    "author": response.get("author") or version_data.get("author", {}),
                    "maintainers": response.get("maintainers", []),
                    "license": response.get("license") or version_data.get("license", ""),
                    "homepage": response.get("homepage") or version_data.get("homepage", ""),
                    "repository": response.get("repository") or version_data.get("repository", {}),
                    "bugs": response.get("bugs") or version_data.get("bugs", {}),
                    "keywords": response.get("keywords", []) or version_data.get("keywords", []),
                    "dependencies": version_data.get("dependencies", {}),
                    "devDependencies": version_data.get("devDependencies", {}),
                    "peerDependencies": version_data.get("peerDependencies", {}),
                    "dist": version_data.get("dist", {}),
                    "dist-tags": response.get("dist-tags", {}),
                    "time": response.get("time", {}),
                    "registry": registry_name
                }
        
        except Exception as e:
            logger.warning(f"Failed to fetch package details for {package_name} from {registry_name}: {e}")
            return None
    
    def _search_packages_in_registry(self, query: str, registry_name: str, max_results: int = 10) -> Dict[str, Dict[str, any]]:
        """
        Search for packages in a registry.
        
        Args:
            query: Search query.
            registry_name: Name of the registry.
            max_results: Maximum number of results to return.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        if registry_name == "npmjs":
            try:
                # Use the NPM search API
                # Note: The official NPM registry has a different endpoint for search
                original_base_url = self.base_url
                self.base_url = "https://registry.npmjs.org/-/v1/"
                
                response = self._fetch_json(f"search?text={query}&size={max_results}")
                
                # Restore the original base URL
                self.base_url = original_base_url
                
                packages = {}
                for obj in response.get("objects", []):
                    package = obj.get("package", {})
                    pkg_name = package.get("name")
                    if pkg_name:
                        packages[pkg_name] = {
                            "name": pkg_name,
                            "version": package.get("version"),
                            "description": package.get("description", ""),
                            "keywords": package.get("keywords", []),
                            "publisher": package.get("publisher", {}),
                            "maintainers": package.get("maintainers", []),
                            "links": package.get("links", {}),
                            "score": obj.get("score", {}),
                            "searchScore": obj.get("searchScore"),
                            "registry": registry_name
                        }
                
                return packages
            
            except Exception as e:
                logger.warning(f"Failed to search packages in {registry_name}: {e}")
                return {}
        else:
            logger.warning(f"Searching packages in {registry_name} is not supported")
            return {}