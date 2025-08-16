"""
Chocolatey repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from the Chocolatey
package manager repository.
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
class ChocoRepository:
    """
    Configuration for a Chocolatey repository.
    """
    name: str  # e.g., "community"
    url: str  # e.g., "https://community.chocolatey.org/api/v2/"


class ChocoFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Chocolatey package manager repositories.
    
    This class fetches package metadata from Chocolatey repositories by querying
    the OData API and processing NuSpec XML files.
    """
    
    def __init__(
        self,
        repositories: Optional[List[ChocoRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Chocolatey fetcher.
        
        Args:
            repositories: List of Chocolatey repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Use the community repository as default
        self.repositories = repositories or [
            ChocoRepository(
                name="community",
                url="https://community.chocolatey.org/api/v2/"
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
        
        # Check for choco command availability (optional for API-based fetching)
        self.choco_available = self.dependency_checker.check_command_availability("choco")
        if not self.choco_available:
            self.dependency_checker.log_missing_dependency("choco", "choco")
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, Dict[str, any]]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "choco"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Chocolatey repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for repo in self.repositories:
            try:
                # Update base URL
                self.base_url = repo.url
                
                # Fetch package list
                packages = self._fetch_package_list(repo.name)
                if packages:
                    self._package_cache[repo.name] = packages
                    result.providers[repo.name] = True
                else:
                    result.success = False
                    result.providers[repo.name] = False
                    result.errors[repo.name] = "No packages found"
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {repo.name}: {e}")
                result.errors[repo.name] = str(e)
                result.providers[repo.name] = False
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
                return self._create_package_info(package_name, pkg_data, repo_name)
            
            # Try case-insensitive match
            for pkg_name, pkg_data in packages.items():
                if pkg_name.lower() == package_name.lower():
                    return self._create_package_info(pkg_name, pkg_data, repo_name)
        
        # If not found in cache, try to fetch directly
        for repo in self.repositories:
            try:
                self.base_url = repo.url
                package_data = self._fetch_package_details(package_name)
                if package_data:
                    return self._create_package_info(package_name, package_data, repo.name)
            except Exception as e:
                logger.warning(f"Failed to fetch package details for {package_name} from {repo.name}: {e}")
        
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
        
        # Search in all repositories
        for repo in self.repositories:
            try:
                self.base_url = repo.url
                search_results = self._search_packages_in_repo(query, max_results - len(results))
                
                for pkg_name, pkg_data in search_results.items():
                    # Create PackageInfo object
                    pkg_info = self._create_package_info(pkg_name, pkg_data, repo.name)
                    
                    # Add to results if not already present
                    if not any(r.name == pkg_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
            
            except Exception as e:
                logger.warning(f"Failed to search packages in {repo.name}: {e}")
        
        return results
    
    def _create_package_info(self, package_name: str, package_data: Dict[str, any], repo_name: str) -> PackageInfo:
        """
        Create a PackageInfo object from package data.
        
        Args:
            package_name: Name of the package.
            package_data: Package data.
            repo_name: Name of the repository.
            
        Returns:
            PackageInfo object.
        """
        # Add repository information to details
        details = package_data.copy()
        details["repository"] = repo_name
        
        return PackageInfo(
            name=package_name,
            provider=self.get_repository_name(),
            version=package_data.get("version"),
            description=package_data.get("description"),
            details=details
        )
    
    def _fetch_package_list(self, repo_name: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch the list of packages from a repository.
        
        Args:
            repo_name: Name of the repository.
            
        Returns:
            Dictionary mapping package IDs to their metadata.
        """
        # Use OData API to get package list
        # The API returns 100 packages per page by default
        packages = {}
        skip = 0
        page_size = 100
        
        while True:
            try:
                # Fetch a page of packages
                url = f"Packages()?$skip={skip}&$top={page_size}&$format=json"
                response = self._fetch_json(url)
                
                # Extract package data
                page_packages = response.get("d", {}).get("results", [])
                if not page_packages:
                    break
                
                # Process packages
                for pkg in page_packages:
                    pkg_id = pkg.get("Id")
                    if pkg_id:
                        # Extract basic metadata
                        packages[pkg_id] = {
                            "id": pkg_id,
                            "version": pkg.get("Version"),
                            "title": pkg.get("Title"),
                            "description": pkg.get("Description"),
                            "authors": pkg.get("Authors"),
                            "published": pkg.get("Published"),
                            "download_count": pkg.get("DownloadCount"),
                            "gallery_details_url": pkg.get("GalleryDetailsUrl"),
                            "project_url": pkg.get("ProjectUrl"),
                            "license_url": pkg.get("LicenseUrl"),
                            "icon_url": pkg.get("IconUrl"),
                            "tags": pkg.get("Tags", "").split(),
                            "repository": repo_name
                        }
                
                # Move to the next page
                skip += page_size
                
                # If we got fewer packages than the page size, we're done
                if len(page_packages) < page_size:
                    break
            
            except Exception as e:
                logger.warning(f"Failed to fetch package list page at skip={skip}: {e}")
                break
        
        return packages
    
    def _fetch_package_details(self, package_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch detailed information about a package.
        
        Args:
            package_name: Name of the package.
            
        Returns:
            Package metadata if found, None otherwise.
        """
        try:
            # Try to get package metadata from the API
            url = f"Packages(Id='{package_name}',Version='latest')?$format=json"
            response = self._fetch_json(url)
            
            if "d" in response:
                pkg = response["d"]
                
                # Extract basic metadata
                package_data = {
                    "id": pkg.get("Id"),
                    "version": pkg.get("Version"),
                    "title": pkg.get("Title"),
                    "description": pkg.get("Description"),
                    "authors": pkg.get("Authors"),
                    "published": pkg.get("Published"),
                    "download_count": pkg.get("DownloadCount"),
                    "gallery_details_url": pkg.get("GalleryDetailsUrl"),
                    "project_url": pkg.get("ProjectUrl"),
                    "license_url": pkg.get("LicenseUrl"),
                    "icon_url": pkg.get("IconUrl"),
                    "tags": pkg.get("Tags", "").split()
                }
                
                # Try to get more detailed information from the NuSpec file
                try:
                    nuspec_data = self._fetch_nuspec(package_name, pkg.get("Version"))
                    if nuspec_data:
                        package_data.update(nuspec_data)
                except Exception as e:
                    logger.warning(f"Failed to fetch NuSpec for {package_name}: {e}")
                
                return package_data
        
        except Exception as e:
            logger.warning(f"Failed to fetch package details for {package_name}: {e}")
        
        return None
    
    def _search_packages_in_repo(self, query: str, max_results: int = 10) -> Dict[str, Dict[str, any]]:
        """
        Search for packages in a repository.
        
        Args:
            query: Search query.
            max_results: Maximum number of results to return.
            
        Returns:
            Dictionary mapping package IDs to their metadata.
        """
        try:
            # Use OData API to search for packages
            url = f"Packages()?$filter=substringof('{query}',Id) or substringof('{query}',Title) or substringof('{query}',Description)&$top={max_results}&$format=json"
            response = self._fetch_json(url)
            
            results = {}
            
            # Extract package data
            packages = response.get("d", {}).get("results", [])
            for pkg in packages:
                pkg_id = pkg.get("Id")
                if pkg_id:
                    # Extract basic metadata
                    results[pkg_id] = {
                        "id": pkg_id,
                        "version": pkg.get("Version"),
                        "title": pkg.get("Title"),
                        "description": pkg.get("Description"),
                        "authors": pkg.get("Authors"),
                        "published": pkg.get("Published"),
                        "download_count": pkg.get("DownloadCount"),
                        "gallery_details_url": pkg.get("GalleryDetailsUrl"),
                        "project_url": pkg.get("ProjectUrl"),
                        "license_url": pkg.get("LicenseUrl"),
                        "icon_url": pkg.get("IconUrl"),
                        "tags": pkg.get("Tags", "").split()
                    }
            
            return results
        
        except Exception as e:
            logger.warning(f"Failed to search packages: {e}")
            return {}
    
    def _fetch_nuspec(self, package_name: str, version: str) -> Optional[Dict[str, any]]:
        """
        Fetch and parse the NuSpec file for a package.
        
        Args:
            package_name: Name of the package.
            version: Version of the package.
            
        Returns:
            Dictionary with NuSpec metadata if successful, None otherwise.
        """
        try:
            # Download the NuGet package
            url = f"package/{package_name}/{version}"
            with tempfile.NamedTemporaryFile(suffix='.nupkg', delete=False) as temp_file:
                try:
                    # Download the package
                    self._fetch_binary(url, temp_file.name)
                    
                    # Extract the NuSpec file from the package
                    with zipfile.ZipFile(temp_file.name, 'r') as zip_ref:
                        nuspec_files = [f for f in zip_ref.namelist() if f.endswith('.nuspec')]
                        if not nuspec_files:
                            return None
                        
                        # Parse the NuSpec file
                        with zip_ref.open(nuspec_files[0]) as nuspec_file:
                            return self._parse_nuspec(nuspec_file.read())
                
                finally:
                    # Clean up the temporary file
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
        
        except Exception as e:
            logger.warning(f"Failed to fetch NuSpec for {package_name} {version}: {e}")
            return None
    
    def _parse_nuspec(self, nuspec_content: bytes) -> Dict[str, any]:
        """
        Parse a NuSpec XML file.
        
        Args:
            nuspec_content: Content of the NuSpec file.
            
        Returns:
            Dictionary with NuSpec metadata.
        """
        try:
            # Parse the XML
            root = ET.fromstring(nuspec_content)
            
            # Find the metadata element
            metadata = root.find(".//{http://schemas.microsoft.com/packaging/2010/07/nuspec.xsd}metadata")
            if metadata is None:
                metadata = root.find(".//metadata")
            
            if metadata is None:
                return {}
            
            # Extract metadata
            result = {}
            
            for child in metadata:
                tag = child.tag
                if tag.startswith("{"):
                    # Remove namespace
                    tag = tag.split("}")[-1]
                
                # Handle special cases
                if tag == "dependencies":
                    result["dependencies"] = []
                    for dep in child.findall(".//{http://schemas.microsoft.com/packaging/2010/07/nuspec.xsd}dependency") or child.findall(".//dependency"):
                        dep_id = dep.get("id")
                        dep_version = dep.get("version")
                        if dep_id:
                            result["dependencies"].append({
                                "id": dep_id,
                                "version": dep_version
                            })
                elif tag == "tags":
                    result["tags"] = child.text.split() if child.text else []
                else:
                    result[tag.lower()] = child.text
            
            return result
        
        except Exception as e:
            logger.warning(f"Failed to parse NuSpec: {e}")
            return {}