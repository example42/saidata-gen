"""
NuGet repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from NuGet
package repositories.
"""

import logging
import os
import xml.etree.ElementTree as ET
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import HttpRepositoryFetcher


logger = logging.getLogger(__name__)


@dataclass
class NuGetFeed:
    """
    Configuration for a NuGet feed.
    """
    name: str  # e.g., "nuget.org"
    url: str  # e.g., "https://api.nuget.org/v3/index.json"


class NuGetFetcher(HttpRepositoryFetcher):
    """
    Fetcher for NuGet package repositories.
    
    This class fetches package metadata from NuGet feeds by querying
    the NuGet API and processing package metadata.
    """
    
    def __init__(
        self,
        feeds: Optional[List[NuGetFeed]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the NuGet fetcher.
        
        Args:
            feeds: List of NuGet feeds to fetch. If None, uses default feeds.
            config: Configuration for the fetcher.
        """
        # Use the official NuGet feed as default
        self.feeds = feeds or [
            NuGetFeed(
                name="nuget.org",
                url="https://api.nuget.org/v3/index.json"
            )
        ]
        
        # Initialize with the first feed
        super().__init__(
            base_url=self.feeds[0].url,
            config=config,
            headers={"Accept": "application/json"}
        )
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, Dict[str, any]]] = {}
        
        # Cache for service endpoints
        self._service_endpoints: Dict[str, Dict[str, str]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "nuget"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from NuGet feeds.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for feed in self.feeds:
            try:
                # Update base URL
                self.base_url = feed.url
                
                # Get service endpoints
                endpoints = self._get_service_endpoints(feed.url)
                if not endpoints:
                    result.success = False
                    result.providers[feed.name] = False
                    result.errors[feed.name] = "Failed to get service endpoints"
                    continue
                
                # Cache the endpoints
                self._service_endpoints[feed.name] = endpoints
                
                # Fetch popular packages as a sample
                packages = self._fetch_popular_packages(feed.name)
                if packages:
                    self._package_cache[feed.name] = packages
                    result.providers[feed.name] = True
                else:
                    result.success = False
                    result.providers[feed.name] = False
                    result.errors[feed.name] = "No packages found"
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {feed.name}: {e}")
                result.errors[feed.name] = str(e)
                result.providers[feed.name] = False
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
        # Look for the package in all feeds
        for feed_name, packages in self._package_cache.items():
            # Try exact match first
            if package_name in packages:
                pkg_data = packages[package_name]
                return self._create_package_info(package_name, pkg_data, feed_name)
            
            # Try case-insensitive match
            for pkg_name, pkg_data in packages.items():
                if pkg_name.lower() == package_name.lower():
                    return self._create_package_info(pkg_name, pkg_data, feed_name)
        
        # If not found in cache, try to fetch directly
        for feed in self.feeds:
            try:
                # Get service endpoints if not already cached
                if feed.name not in self._service_endpoints:
                    self._service_endpoints[feed.name] = self._get_service_endpoints(feed.url)
                
                # Get package details
                package_data = self._fetch_package_details(package_name, feed.name)
                if package_data:
                    return self._create_package_info(package_name, package_data, feed.name)
            except Exception as e:
                logger.warning(f"Failed to fetch package details for {package_name} from {feed.name}: {e}")
        
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
        
        # Search in all feeds
        for feed in self.feeds:
            try:
                # Get service endpoints if not already cached
                if feed.name not in self._service_endpoints:
                    self._service_endpoints[feed.name] = self._get_service_endpoints(feed.url)
                
                # Search for packages
                search_results = self._search_packages_in_feed(query, feed.name, max_results - len(results))
                
                for pkg_name, pkg_data in search_results.items():
                    # Create PackageInfo object
                    pkg_info = self._create_package_info(pkg_name, pkg_data, feed.name)
                    
                    # Add to results if not already present
                    if not any(r.name == pkg_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
            
            except Exception as e:
                logger.warning(f"Failed to search packages in {feed.name}: {e}")
        
        return results
    
    def _create_package_info(self, package_name: str, package_data: Dict[str, any], feed_name: str) -> PackageInfo:
        """
        Create a PackageInfo object from package data.
        
        Args:
            package_name: Name of the package.
            package_data: Package data.
            feed_name: Name of the feed.
            
        Returns:
            PackageInfo object.
        """
        # Add feed information to details
        details = package_data.copy()
        details["feed"] = feed_name
        
        return PackageInfo(
            name=package_name,
            provider=self.get_repository_name(),
            version=package_data.get("version"),
            description=package_data.get("description"),
            details=details
        )
    
    def _get_service_endpoints(self, feed_url: str) -> Dict[str, str]:
        """
        Get service endpoints from a NuGet feed.
        
        Args:
            feed_url: URL of the feed.
            
        Returns:
            Dictionary mapping service types to their endpoints.
        """
        # Set base URL to the feed URL
        self.base_url = feed_url
        
        try:
            # Fetch the service index
            response = self._fetch_json("", use_cache=True)
            
            endpoints = {}
            for resource in response.get("resources", []):
                resource_type = resource.get("@type", "")
                resource_url = resource.get("@id", "")
                
                if resource_type and resource_url:
                    # Some resources have multiple types separated by semicolons
                    for type_value in resource_type.split(";"):
                        type_value = type_value.strip()
                        if type_value:
                            endpoints[type_value] = resource_url
            
            return endpoints
        
        except Exception as e:
            logger.warning(f"Failed to get service endpoints from {feed_url}: {e}")
            return {}
    
    def _fetch_popular_packages(self, feed_name: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch popular packages from a feed.
        
        Args:
            feed_name: Name of the feed.
            
        Returns:
            Dictionary mapping package IDs to their metadata.
        """
        # Get the search endpoint
        search_endpoint = self._service_endpoints.get(feed_name, {}).get(
            "SearchQueryService/3.5.0",
            self._service_endpoints.get(feed_name, {}).get(
                "SearchQueryService",
                ""
            )
        )
        
        if not search_endpoint:
            logger.warning(f"Search endpoint not found for {feed_name}")
            return {}
        
        try:
            # Set base URL to the search endpoint
            self.base_url = search_endpoint
            
            # Fetch popular packages
            response = self._fetch_json("?q=&prerelease=false&semVerLevel=2.0.0&take=100")
            
            packages = {}
            for pkg in response.get("data", []):
                pkg_id = pkg.get("id")
                if pkg_id:
                    packages[pkg_id] = {
                        "id": pkg_id,
                        "version": pkg.get("version"),
                        "description": pkg.get("description"),
                        "authors": pkg.get("authors"),
                        "total_downloads": pkg.get("totalDownloads"),
                        "verified": pkg.get("verified", False),
                        "tags": pkg.get("tags", "").split(),
                        "project_url": pkg.get("projectUrl"),
                        "license_url": pkg.get("licenseUrl"),
                        "icon_url": pkg.get("iconUrl"),
                        "feed": feed_name
                    }
            
            return packages
        
        except Exception as e:
            logger.warning(f"Failed to fetch popular packages from {feed_name}: {e}")
            return {}
    
    def _fetch_package_details(self, package_name: str, feed_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch detailed information about a package.
        
        Args:
            package_name: Name of the package.
            feed_name: Name of the feed.
            
        Returns:
            Package metadata if found, None otherwise.
        """
        # Get the registration endpoint
        registration_endpoint = self._service_endpoints.get(feed_name, {}).get(
            "RegistrationsBaseUrl/3.6.0",
            self._service_endpoints.get(feed_name, {}).get(
                "RegistrationsBaseUrl",
                ""
            )
        )
        
        if not registration_endpoint:
            logger.warning(f"Registration endpoint not found for {feed_name}")
            return None
        
        try:
            # Set base URL to the registration endpoint
            self.base_url = registration_endpoint
            
            # Fetch package details
            url = f"{package_name.lower()}/index.json"
            response = self._fetch_json(url)
            
            # Extract the latest version
            items = response.get("items", [])
            if not items:
                return None
            
            # Get the latest version
            latest_item = items[-1]
            latest_version = None
            latest_version_data = None
            
            for item in latest_item.get("items", []):
                catalog_entry = item.get("catalogEntry", {})
                version = catalog_entry.get("version")
                
                # Skip prerelease versions
                if version and "-" not in version:
                    if latest_version is None or version > latest_version:
                        latest_version = version
                        latest_version_data = catalog_entry
            
            if latest_version_data:
                return {
                    "id": latest_version_data.get("id"),
                    "version": latest_version_data.get("version"),
                    "description": latest_version_data.get("description"),
                    "authors": latest_version_data.get("authors"),
                    "tags": latest_version_data.get("tags", "").split(),
                    "project_url": latest_version_data.get("projectUrl"),
                    "license_url": latest_version_data.get("licenseUrl"),
                    "icon_url": latest_version_data.get("iconUrl"),
                    "dependencies": latest_version_data.get("dependencyGroups", []),
                    "feed": feed_name
                }
        
        except Exception as e:
            logger.warning(f"Failed to fetch package details for {package_name} from {feed_name}: {e}")
            return None
    
    def _search_packages_in_feed(self, query: str, feed_name: str, max_results: int = 10) -> Dict[str, Dict[str, any]]:
        """
        Search for packages in a feed.
        
        Args:
            query: Search query.
            feed_name: Name of the feed.
            max_results: Maximum number of results to return.
            
        Returns:
            Dictionary mapping package IDs to their metadata.
        """
        # Get the search endpoint
        search_endpoint = self._service_endpoints.get(feed_name, {}).get(
            "SearchQueryService/3.5.0",
            self._service_endpoints.get(feed_name, {}).get(
                "SearchQueryService",
                ""
            )
        )
        
        if not search_endpoint:
            logger.warning(f"Search endpoint not found for {feed_name}")
            return {}
        
        try:
            # Set base URL to the search endpoint
            self.base_url = search_endpoint
            
            # Search for packages
            url = f"?q={query}&prerelease=false&semVerLevel=2.0.0&take={max_results}"
            response = self._fetch_json(url)
            
            packages = {}
            for pkg in response.get("data", []):
                pkg_id = pkg.get("id")
                if pkg_id:
                    packages[pkg_id] = {
                        "id": pkg_id,
                        "version": pkg.get("version"),
                        "description": pkg.get("description"),
                        "authors": pkg.get("authors"),
                        "total_downloads": pkg.get("totalDownloads"),
                        "verified": pkg.get("verified", False),
                        "tags": pkg.get("tags", "").split() if pkg.get("tags") else [],
                        "project_url": pkg.get("projectUrl"),
                        "license_url": pkg.get("licenseUrl"),
                        "icon_url": pkg.get("iconUrl"),
                        "feed": feed_name
                    }
            
            return packages
        
        except Exception as e:
            logger.warning(f"Failed to search packages in {feed_name}: {e}")
            return {}