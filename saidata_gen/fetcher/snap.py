"""
Snap repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from the Snap Store.
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
class SnapStore:
    """
    Configuration for a Snap Store.
    """
    name: str  # e.g., "snapcraft"
    url: str  # e.g., "https://api.snapcraft.io/api/v1/"


class SnapFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Snap Store.
    
    This class fetches package metadata from the Snap Store by querying
    the Snapcraft API.
    """
    
    def __init__(
        self,
        stores: Optional[List[SnapStore]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Snap fetcher.
        
        Args:
            stores: List of Snap stores to fetch. If None, uses default stores.
            config: Configuration for the fetcher.
        """
        # Use the official Snap Store as default
        self.stores = stores or [
            SnapStore(
                name="snapcraft",
                url="https://api.snapcraft.io/api/v1/"
            )
        ]
        
        # Initialize with the first store
        super().__init__(
            base_url=self.stores[0].url,
            config=config,
            headers={
                "Accept": "application/json",
                "X-Ubuntu-Series": "16",  # Default series
                "X-Ubuntu-Architecture": "amd64"  # Default architecture
            }
        )
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, Dict[str, any]]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "snap"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Snap stores.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for store in self.stores:
            try:
                # Update base URL
                self.base_url = store.url
                
                # Fetch featured snaps as a sample
                snaps = self._fetch_featured_snaps(store.name)
                if snaps:
                    self._package_cache[store.name] = snaps
                    result.providers[store.name] = True
                else:
                    result.success = False
                    result.providers[store.name] = False
                    result.errors[store.name] = "No snaps found"
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {store.name}: {e}")
                result.errors[store.name] = str(e)
                result.providers[store.name] = False
                result.success = False
        
        return result
    
    def get_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """
        Get information about a specific snap.
        
        Args:
            package_name: Name of the snap to get information for.
            
        Returns:
            PackageInfo if the snap is found, None otherwise.
        """
        # Ensure we have fetched repository data
        if not self._package_cache:
            self.fetch_repository_data()
        
        # Look for the snap in all stores
        for store_name, snaps in self._package_cache.items():
            # Try exact match first
            if package_name in snaps:
                snap_data = snaps[package_name]
                return self._create_package_info(package_name, snap_data, store_name)
            
            # Try case-insensitive match
            for snap_name, snap_data in snaps.items():
                if snap_name.lower() == package_name.lower():
                    return self._create_package_info(snap_name, snap_data, store_name)
        
        # If not found in cache, try to fetch directly
        for store in self.stores:
            try:
                self.base_url = store.url
                snap_data = self._fetch_snap_details(package_name, store.name)
                if snap_data:
                    return self._create_package_info(package_name, snap_data, store.name)
            except Exception as e:
                logger.warning(f"Failed to fetch snap details for {package_name} from {store.name}: {e}")
        
        return None
    
    def search_packages(self, query: str, max_results: int = 10) -> List[PackageInfo]:
        """
        Search for snaps matching the query.
        
        Args:
            query: Search query.
            max_results: Maximum number of results to return.
            
        Returns:
            List of PackageInfo objects matching the query.
        """
        results = []
        
        # Search in all stores
        for store in self.stores:
            try:
                self.base_url = store.url
                search_results = self._search_snaps_in_store(query, store.name, max_results - len(results))
                
                for snap_name, snap_data in search_results.items():
                    # Create PackageInfo object
                    pkg_info = self._create_package_info(snap_name, snap_data, store.name)
                    
                    # Add to results if not already present
                    if not any(r.name == snap_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
            
            except Exception as e:
                logger.warning(f"Failed to search snaps in {store.name}: {e}")
        
        return results
    
    def _create_package_info(self, snap_name: str, snap_data: Dict[str, any], store_name: str) -> PackageInfo:
        """
        Create a PackageInfo object from snap data.
        
        Args:
            snap_name: Name of the snap.
            snap_data: Snap data.
            store_name: Name of the store.
            
        Returns:
            PackageInfo object.
        """
        # Add store information to details
        details = snap_data.copy()
        details["store"] = store_name
        
        # Extract version
        version = "latest"
        if "version" in snap_data:
            version = snap_data["version"]
        
        return PackageInfo(
            name=snap_name,
            provider=self.get_repository_name(),
            version=version,
            description=snap_data.get("summary", ""),
            details=details
        )
    
    def _fetch_featured_snaps(self, store_name: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch featured snaps from a store.
        
        Args:
            store_name: Name of the store.
            
        Returns:
            Dictionary mapping snap names to their metadata.
        """
        try:
            # Fetch featured snaps
            response = self._fetch_json("snaps/search?section=featured")
            
            snaps = {}
            for snap in response.get("_embedded", {}).get("clickindex:package", []):
                snap_name = snap.get("package_name")
                if snap_name:
                    snaps[snap_name] = {
                        "name": snap_name,
                        "title": snap.get("title"),
                        "summary": snap.get("summary"),
                        "description": snap.get("description"),
                        "version": snap.get("version"),
                        "developer_name": snap.get("developer_name"),
                        "developer_id": snap.get("developer_id"),
                        "publisher": snap.get("publisher"),
                        "icon_url": snap.get("icon_url"),
                        "download_url": snap.get("download_url"),
                        "confinement": snap.get("confinement"),
                        "license": snap.get("license"),
                        "categories": snap.get("categories", []),
                        "store": store_name
                    }
            
            return snaps
        
        except Exception as e:
            logger.warning(f"Failed to fetch featured snaps from {store_name}: {e}")
            return {}
    
    def _fetch_snap_details(self, snap_name: str, store_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch detailed information about a snap.
        
        Args:
            snap_name: Name of the snap.
            store_name: Name of the store.
            
        Returns:
            Snap metadata if found, None otherwise.
        """
        try:
            # Fetch snap details
            response = self._fetch_json(f"snaps/details/{snap_name}")
            
            if "package_name" in response:
                return {
                    "name": response.get("package_name"),
                    "title": response.get("title"),
                    "summary": response.get("summary"),
                    "description": response.get("description"),
                    "version": response.get("version"),
                    "developer_name": response.get("developer_name"),
                    "developer_id": response.get("developer_id"),
                    "publisher": response.get("publisher"),
                    "icon_url": response.get("icon_url"),
                    "download_url": response.get("download_url"),
                    "confinement": response.get("confinement"),
                    "license": response.get("license"),
                    "categories": response.get("categories", []),
                    "store": store_name
                }
        
        except Exception as e:
            logger.warning(f"Failed to fetch snap details for {snap_name} from {store_name}: {e}")
            return None
    
    def _search_snaps_in_store(self, query: str, store_name: str, max_results: int = 10) -> Dict[str, Dict[str, any]]:
        """
        Search for snaps in a store.
        
        Args:
            query: Search query.
            store_name: Name of the store.
            max_results: Maximum number of results to return.
            
        Returns:
            Dictionary mapping snap names to their metadata.
        """
        try:
            # Search for snaps
            response = self._fetch_json(f"snaps/search?q={query}&size={max_results}")
            
            snaps = {}
            for snap in response.get("_embedded", {}).get("clickindex:package", []):
                snap_name = snap.get("package_name")
                if snap_name:
                    snaps[snap_name] = {
                        "name": snap_name,
                        "title": snap.get("title"),
                        "summary": snap.get("summary"),
                        "description": snap.get("description"),
                        "version": snap.get("version"),
                        "developer_name": snap.get("developer_name"),
                        "developer_id": snap.get("developer_id"),
                        "publisher": snap.get("publisher"),
                        "icon_url": snap.get("icon_url"),
                        "download_url": snap.get("download_url"),
                        "confinement": snap.get("confinement"),
                        "license": snap.get("license"),
                        "categories": snap.get("categories", []),
                        "store": store_name
                    }
            
            return snaps
        
        except Exception as e:
            logger.warning(f"Failed to search snaps in {store_name}: {e}")
            return {}