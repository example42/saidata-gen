"""
Flatpak repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from Flatpak repositories.
"""

import logging
import os
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import HttpRepositoryFetcher
from saidata_gen.fetcher.error_handler import FetcherErrorHandler, ErrorContext
from saidata_gen.core.system_dependency_checker import SystemDependencyChecker

# Try to import requests for error handling
try:
    import requests
    import ssl
except ImportError:
    pass


logger = logging.getLogger(__name__)


@dataclass
class FlatpakRepository:
    """
    Configuration for a Flatpak repository.
    """
    name: str  # e.g., "flathub"
    url: str  # e.g., "https://flathub.org/api/v1/"


class FlatpakFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Flatpak repositories.
    
    This class fetches package metadata from Flatpak repositories by querying
    their APIs.
    """
    
    def __init__(
        self,
        repositories: Optional[List[FlatpakRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Flatpak fetcher.
        
        Args:
            repositories: List of Flatpak repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Use Flathub as the default repository
        self.repositories = repositories or [
            FlatpakRepository(
                name="flathub",
                url="https://flathub.org/api/v1/"
            )
        ]
        
        # Initialize with the first repository
        super().__init__(
            base_url=self.repositories[0].url,
            config=config,
            headers={"Accept": "application/json"}
        )
        
        # Initialize error handler and system dependency checker
        self.error_handler = FetcherErrorHandler(max_retries=3, base_wait_time=1.0)
        self.dependency_checker = SystemDependencyChecker()
        
        # Check for flatpak command availability (optional for API-based fetching)
        self.flatpak_available = self.dependency_checker.check_command_availability("flatpak")
        if not self.flatpak_available:
            self.dependency_checker.log_missing_dependency("flatpak", "flatpak")
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, Dict[str, any]]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "flatpak"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Flatpak repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for repo in self.repositories:
            try:
                # Update base URL
                self.base_url = repo.url
                
                # Fetch applications
                apps = self._fetch_applications(repo.name)
                if apps:
                    self._package_cache[repo.name] = apps
                    result.providers[repo.name] = True
                else:
                    result.success = False
                    result.providers[repo.name] = False
                    result.errors[repo.name] = "No applications found"
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {repo.name}: {e}")
                result.errors[repo.name] = str(e)
                result.providers[repo.name] = False
                result.success = False
        
        return result
    
    def get_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """
        Get information about a specific Flatpak application.
        
        Args:
            package_name: Name of the application to get information for.
            
        Returns:
            PackageInfo if the application is found, None otherwise.
        """
        # Ensure we have fetched repository data
        if not self._package_cache:
            self.fetch_repository_data()
        
        # Look for the application in all repositories
        for repo_name, apps in self._package_cache.items():
            # Try exact match first
            if package_name in apps:
                app_data = apps[package_name]
                return self._create_package_info(package_name, app_data, repo_name)
            
            # Try case-insensitive match
            for app_id, app_data in apps.items():
                if app_id.lower() == package_name.lower():
                    return self._create_package_info(app_id, app_data, repo_name)
        
        # If not found in cache, try to fetch directly
        for repo in self.repositories:
            try:
                self.base_url = repo.url
                app_data = self._fetch_application_details(package_name, repo.name)
                if app_data:
                    return self._create_package_info(package_name, app_data, repo.name)
            except Exception as e:
                logger.warning(f"Failed to fetch application details for {package_name} from {repo.name}: {e}")
        
        return None
    
    def search_packages(self, query: str, max_results: int = 10) -> List[PackageInfo]:
        """
        Search for Flatpak applications matching the query.
        
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
        for repo_name, apps in self._package_cache.items():
            for app_id, app_data in apps.items():
                # Check if the application ID, name, or summary contains the query
                if (query_lower in app_id.lower() or
                    (app_data.get("name") and query_lower in app_data["name"].lower()) or
                    (app_data.get("summary") and query_lower in app_data["summary"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = self._create_package_info(app_id, app_data, repo_name)
                    
                    # Add to results if not already present
                    if not any(r.name == app_id for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
        
        return results
    
    def _create_package_info(self, app_id: str, app_data: Dict[str, any], repo_name: str) -> PackageInfo:
        """
        Create a PackageInfo object from application data.
        
        Args:
            app_id: ID of the application.
            app_data: Application data.
            repo_name: Name of the repository.
            
        Returns:
            PackageInfo object.
        """
        # Add repository information to details
        details = app_data.copy()
        details["repository"] = repo_name
        
        return PackageInfo(
            name=app_id,
            provider=self.get_repository_name(),
            version=app_data.get("version"),
            description=app_data.get("summary", ""),
            details=details
        )
    
    def _fetch_applications(self, repo_name: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch applications from a repository.
        
        Args:
            repo_name: Name of the repository.
            
        Returns:
            Dictionary mapping application IDs to their metadata.
        """
        if repo_name == "flathub":
            try:
                # Fetch applications from Flathub
                response = self._fetch_json("apps")
                
                apps = {}
                for app in response:
                    app_id = app.get("flatpakAppId")
                    if app_id:
                        apps[app_id] = {
                            "id": app_id,
                            "name": app.get("name"),
                            "summary": app.get("summary"),
                            "description": app.get("description"),
                            "version": app.get("currentReleaseVersion"),
                            "developer_name": app.get("developerName"),
                            "project_license": app.get("projectLicense"),
                            "icon_url": app.get("iconDesktopUrl"),
                            "download_size": app.get("downloadSize"),
                            "installed_size": app.get("installedSize"),
                            "categories": app.get("categories", []),
                            "repository": repo_name
                        }
                
                return apps
            
            except Exception as e:
                logger.warning(f"Failed to fetch applications from Flathub: {e}")
                return {}
        else:
            logger.warning(f"Fetching applications from {repo_name} is not supported")
            return {}
    
    def _fetch_application_details(self, app_id: str, repo_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch detailed information about a Flatpak application.
        
        Args:
            app_id: ID of the application.
            repo_name: Name of the repository.
            
        Returns:
            Application metadata if found, None otherwise.
        """
        if repo_name == "flathub":
            try:
                # Fetch application details from Flathub
                response = self._fetch_json(f"apps/{app_id}")
                
                if "flatpakAppId" in response:
                    return {
                        "id": response.get("flatpakAppId"),
                        "name": response.get("name"),
                        "summary": response.get("summary"),
                        "description": response.get("description"),
                        "version": response.get("currentReleaseVersion"),
                        "developer_name": response.get("developerName"),
                        "project_license": response.get("projectLicense"),
                        "icon_url": response.get("iconDesktopUrl"),
                        "download_size": response.get("downloadSize"),
                        "installed_size": response.get("installedSize"),
                        "categories": response.get("categories", []),
                        "repository": repo_name
                    }
            
            except Exception as e:
                logger.warning(f"Failed to fetch application details for {app_id} from Flathub: {e}")
                return None
        else:
            logger.warning(f"Fetching application details from {repo_name} is not supported")
            return None