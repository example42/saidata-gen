"""
Cargo repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from the Rust
crates.io registry.
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
class CargoRegistry:
    """
    Configuration for a Cargo registry.
    """
    name: str  # e.g., "crates-io"
    url: str  # e.g., "https://crates.io/api/v1/"


class CargoFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Cargo (Rust) package registry.
    
    This class fetches package metadata from crates.io and other Cargo registries
    by querying their APIs.
    """
    
    def __init__(
        self,
        registries: Optional[List[CargoRegistry]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Cargo fetcher.
        
        Args:
            registries: List of Cargo registries to fetch. If None, uses default registries.
            config: Configuration for the fetcher.
        """
        # Use crates.io as the default registry
        self.registries = registries or [
            CargoRegistry(
                name="crates-io",
                url="https://crates.io/api/v1/"
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
        return "cargo"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Cargo registries.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for registry in self.registries:
            try:
                # Update base URL
                self.base_url = registry.url
                
                # Fetch popular crates as a sample
                crates = self._fetch_popular_crates(registry.name)
                if crates:
                    self._package_cache[registry.name] = crates
                    result.providers[registry.name] = True
                else:
                    result.success = False
                    result.providers[registry.name] = False
                    result.errors[registry.name] = "No crates found"
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {registry.name}: {e}")
                result.errors[registry.name] = str(e)
                result.providers[registry.name] = False
                result.success = False
        
        return result
    
    def get_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """
        Get information about a specific crate.
        
        Args:
            package_name: Name of the crate to get information for.
            
        Returns:
            PackageInfo if the crate is found, None otherwise.
        """
        # Ensure we have fetched repository data
        if not self._package_cache:
            self.fetch_repository_data()
        
        # Look for the crate in all registries
        for registry_name, crates in self._package_cache.items():
            # Try exact match first
            if package_name in crates:
                crate_data = crates[package_name]
                return self._create_package_info(package_name, crate_data, registry_name)
            
            # Try case-insensitive match
            for crate_name, crate_data in crates.items():
                if crate_name.lower() == package_name.lower():
                    return self._create_package_info(crate_name, crate_data, registry_name)
        
        # If not found in cache, try to fetch directly
        for registry in self.registries:
            try:
                self.base_url = registry.url
                crate_data = self._fetch_crate_details(package_name, registry.name)
                if crate_data:
                    return self._create_package_info(package_name, crate_data, registry.name)
            except Exception as e:
                logger.warning(f"Failed to fetch crate details for {package_name} from {registry.name}: {e}")
        
        return None
    
    def search_packages(self, query: str, max_results: int = 10) -> List[PackageInfo]:
        """
        Search for crates matching the query.
        
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
                search_results = self._search_crates_in_registry(query, registry.name, max_results - len(results))
                
                for crate_name, crate_data in search_results.items():
                    # Create PackageInfo object
                    pkg_info = self._create_package_info(crate_name, crate_data, registry.name)
                    
                    # Add to results if not already present
                    if not any(r.name == crate_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
            
            except Exception as e:
                logger.warning(f"Failed to search crates in {registry.name}: {e}")
        
        return results
    
    def _create_package_info(self, crate_name: str, crate_data: Dict[str, any], registry_name: str) -> PackageInfo:
        """
        Create a PackageInfo object from crate data.
        
        Args:
            crate_name: Name of the crate.
            crate_data: Crate data.
            registry_name: Name of the registry.
            
        Returns:
            PackageInfo object.
        """
        # Add registry information to details
        details = crate_data.copy()
        details["registry"] = registry_name
        
        # Extract version
        version = "latest"
        if "max_version" in crate_data:
            version = crate_data["max_version"]
        elif "version" in crate_data:
            version = crate_data["version"]
        elif "crate" in crate_data and "max_version" in crate_data["crate"]:
            version = crate_data["crate"]["max_version"]
        
        # Extract description
        description = ""
        if "description" in crate_data:
            description = crate_data["description"]
        elif "crate" in crate_data and "description" in crate_data["crate"]:
            description = crate_data["crate"]["description"]
        
        return PackageInfo(
            name=crate_name,
            provider=self.get_repository_name(),
            version=version,
            description=description,
            details=details
        )
    
    def _fetch_popular_crates(self, registry_name: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch popular crates from a registry.
        
        Args:
            registry_name: Name of the registry.
            
        Returns:
            Dictionary mapping crate names to their metadata.
        """
        if registry_name == "crates-io":
            try:
                # Fetch popular crates from crates.io
                response = self._fetch_json("crates?page=1&per_page=15&sort=downloads")
                
                crates = {}
                for crate in response.get("crates", []):
                    crate_name = crate.get("name")
                    if crate_name:
                        crates[crate_name] = {
                            "name": crate_name,
                            "id": crate.get("id"),
                            "description": crate.get("description"),
                            "max_version": crate.get("max_version"),
                            "newest_version": crate.get("newest_version"),
                            "downloads": crate.get("downloads"),
                            "recent_downloads": crate.get("recent_downloads"),
                            "categories": crate.get("categories", []),
                            "keywords": crate.get("keywords", []),
                            "created_at": crate.get("created_at"),
                            "updated_at": crate.get("updated_at"),
                            "homepage": crate.get("homepage"),
                            "documentation": crate.get("documentation"),
                            "repository": crate.get("repository"),
                            "license": crate.get("license"),
                            "registry": registry_name
                        }
                
                return crates
            
            except Exception as e:
                logger.warning(f"Failed to fetch popular crates from {registry_name}: {e}")
                return {}
        else:
            logger.warning(f"Fetching popular crates from {registry_name} is not supported")
            return {}
    
    def _fetch_crate_details(self, crate_name: str, registry_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch detailed information about a crate.
        
        Args:
            crate_name: Name of the crate.
            registry_name: Name of the registry.
            
        Returns:
            Crate metadata if found, None otherwise.
        """
        if registry_name == "crates-io":
            try:
                # Fetch crate details from crates.io
                response = self._fetch_json(f"crates/{crate_name}")
                
                if "crate" in response:
                    crate = response["crate"]
                    versions = response.get("versions", [])
                    
                    # Get the latest version
                    latest_version = None
                    if versions:
                        latest_version = versions[0]
                    
                    # Combine metadata
                    return {
                        "name": crate.get("name"),
                        "id": crate.get("id"),
                        "description": crate.get("description"),
                        "max_version": crate.get("max_version"),
                        "newest_version": crate.get("newest_version"),
                        "downloads": crate.get("downloads"),
                        "recent_downloads": crate.get("recent_downloads"),
                        "categories": crate.get("categories", []),
                        "keywords": crate.get("keywords", []),
                        "created_at": crate.get("created_at"),
                        "updated_at": crate.get("updated_at"),
                        "homepage": crate.get("homepage"),
                        "documentation": crate.get("documentation"),
                        "repository": crate.get("repository"),
                        "license": crate.get("license"),
                        "versions": versions,
                        "latest_version": latest_version,
                        "registry": registry_name
                    }
            
            except Exception as e:
                logger.warning(f"Failed to fetch crate details for {crate_name} from {registry_name}: {e}")
                return None
        else:
            logger.warning(f"Fetching crate details from {registry_name} is not supported")
            return None
    
    def _search_crates_in_registry(self, query: str, registry_name: str, max_results: int = 10) -> Dict[str, Dict[str, any]]:
        """
        Search for crates in a registry.
        
        Args:
            query: Search query.
            registry_name: Name of the registry.
            max_results: Maximum number of results to return.
            
        Returns:
            Dictionary mapping crate names to their metadata.
        """
        if registry_name == "crates-io":
            try:
                # Search for crates on crates.io
                response = self._fetch_json(f"crates?q={query}&page=1&per_page={max_results}")
                
                crates = {}
                for crate in response.get("crates", []):
                    crate_name = crate.get("name")
                    if crate_name:
                        crates[crate_name] = {
                            "name": crate_name,
                            "id": crate.get("id"),
                            "description": crate.get("description"),
                            "max_version": crate.get("max_version"),
                            "newest_version": crate.get("newest_version"),
                            "downloads": crate.get("downloads"),
                            "recent_downloads": crate.get("recent_downloads"),
                            "categories": crate.get("categories", []),
                            "keywords": crate.get("keywords", []),
                            "created_at": crate.get("created_at"),
                            "updated_at": crate.get("updated_at"),
                            "homepage": crate.get("homepage"),
                            "documentation": crate.get("documentation"),
                            "repository": crate.get("repository"),
                            "license": crate.get("license"),
                            "registry": registry_name
                        }
                
                return crates
            
            except Exception as e:
                logger.warning(f"Failed to search crates in {registry_name}: {e}")
                return {}
        else:
            logger.warning(f"Searching crates in {registry_name} is not supported")
            return {}