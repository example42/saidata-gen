"""
DNF/RPM repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from DNF/RPM
repositories, including Fedora, CentOS, AlmaLinux, Rocky Linux, and RHEL.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import HttpRepositoryFetcher, REQUESTS_AVAILABLE
from saidata_gen.fetcher.rpm_utils import (
    fetch_primary_location, decompress_gzip_content, parse_primary_xml, parse_metalink_xml
)


logger = logging.getLogger(__name__)


@dataclass
class DNFDistribution:
    """
    Configuration for a DNF distribution.
    """
    name: str  # e.g., "fedora", "centos", "rhel"
    version: str  # e.g., "38", "9-stream", "9"
    url: str  # e.g., "https://mirrors.fedoraproject.org/metalink?repo=fedora-38&arch=x86_64"
    architectures: List[str] = None  # e.g., ["x86_64", "aarch64"]


class DNFFetcher(HttpRepositoryFetcher):
    """
    Fetcher for DNF/RPM repositories.
    
    This class fetches package metadata from DNF/RPM repositories,
    including Fedora, CentOS, and RHEL.
    """
    
    def __init__(
        self,
        distributions: Optional[List[DNFDistribution]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the DNF fetcher.
        
        Args:
            distributions: List of DNF distributions to fetch. If None, uses default distributions.
            config: Configuration for the fetcher.
            
        Raises:
            ImportError: If the requests library is not available.
        """
        # Check if requests is available
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "The 'requests' library is required for the DNFFetcher. "
                "Please install it using 'pip install requests'."
            )
        # Initialize with a dummy base_url, we'll use distribution-specific URLs
        super().__init__(base_url="https://example.com", config=config)
        
        # Set up default distributions if none provided
        self.distributions = distributions or [
            DNFDistribution(
                name="fedora",
                version="38",
                url="https://mirrors.fedoraproject.org/metalink?repo=fedora-38&arch=x86_64",
                architectures=["x86_64"]
            ),
            DNFDistribution(
                name="fedora",
                version="39",
                url="https://mirrors.fedoraproject.org/metalink?repo=fedora-39&arch=x86_64",
                architectures=["x86_64"]
            ),
            DNFDistribution(
                name="fedora",
                version="40",
                url="https://mirrors.fedoraproject.org/metalink?repo=fedora-40&arch=x86_64",
                architectures=["x86_64"]
            ),
            DNFDistribution(
                name="centos",
                version="9-stream",
                url="https://mirrors.centos.org/metalink?repo=centos-baseos-9-stream&arch=x86_64",
                architectures=["x86_64"]
            ),
            DNFDistribution(
                name="centos",
                version="9",
                url="https://mirrors.centos.org/metalink?repo=centos-baseos-9&arch=x86_64",
                architectures=["x86_64"]
            ),
            DNFDistribution(
                name="almalinux",
                version="9",
                url="https://repo.almalinux.org/almalinux/9/BaseOS/x86_64/os/",
                architectures=["x86_64"]
            ),
            DNFDistribution(
                name="almalinux",
                version="8",
                url="https://repo.almalinux.org/almalinux/8/BaseOS/x86_64/os/",
                architectures=["x86_64"]
            ),
            DNFDistribution(
                name="rockylinux",
                version="9",
                url="https://download.rockylinux.org/pub/rocky/9/BaseOS/x86_64/os/",
                architectures=["x86_64"]
            ),
            DNFDistribution(
                name="rockylinux",
                version="8",
                url="https://download.rockylinux.org/pub/rocky/8/BaseOS/x86_64/os/",
                architectures=["x86_64"]
            ),
            # RHEL repositories removed due to authentication requirements and SSL issues
            # Users can add their own RHEL repositories with proper authentication
        ]
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, PackageInfo]] = {}
        self._mirror_urls: Dict[str, str] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "dnf"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from DNF repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for dist in self.distributions:
            dist_key = f"{dist.name}_{dist.version}"
            try:
                # For each architecture
                for arch in dist.architectures or ["x86_64"]:
                    cache_key = f"{dist_key}_{arch}"
                    
                    # Check if we have a valid cache
                    cached_data = self._get_from_cache(cache_key)
                    if cached_data:
                        self._package_cache[cache_key] = cached_data
                        result.cache_hits[cache_key] = True
                        continue
                    
                    # Get the mirror URL if it's a metalink
                    base_url = self._get_mirror_url(dist.url) if "metalink" in dist.url else dist.url
                    
                    # Fetch and parse repomd.xml to get the primary.xml location
                    try:
                        repomd_url = f"{base_url}/repodata/repomd.xml"
                        primary_location = self._fetch_primary_location(repomd_url)
                        
                        # Fetch and parse primary.xml
                        primary_url = f"{base_url}/{primary_location}"
                        packages_data = self._fetch_primary_xml(primary_url)
                        
                        self._package_cache[cache_key] = packages_data
                        self._save_to_cache(cache_key, packages_data)
                        result.providers[cache_key] = True
                    except Exception as e:
                        logger.error(f"Failed to fetch repository data for {cache_key}: {e}")
                        result.errors[cache_key] = str(e)
                        result.providers[cache_key] = False
                        result.success = False
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {dist_key}: {e}")
                result.errors[dist_key] = str(e)
                result.providers[dist_key] = False
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
        
        # Look for the package in all distributions
        for cache_key, packages in self._package_cache.items():
            if package_name in packages:
                pkg_data = packages[package_name]
                return PackageInfo(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("version"),
                    description=pkg_data.get("summary"),
                    details=pkg_data
                )
        
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
        
        # Search in all distributions
        for cache_key, packages in self._package_cache.items():
            for pkg_name, pkg_data in packages.items():
                # Check if the package name or description contains the query
                if (query_lower in pkg_name.lower() or 
                    (pkg_data.get("summary") and query_lower in pkg_data["summary"].lower()) or
                    (pkg_data.get("description") and query_lower in pkg_data["description"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = PackageInfo(
                        name=pkg_name,
                        provider=self.get_repository_name(),
                        version=pkg_data.get("version"),
                        description=pkg_data.get("summary"),
                        details=pkg_data
                    )
                    
                    # Add to results if not already present
                    if not any(r.name == pkg_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
        
        return results
    
    def get_package_details(self, package_name: str, distribution: Optional[str] = None) -> Optional[PackageDetails]:
        """
        Get detailed information about a specific package.
        
        Args:
            package_name: Name of the package to get information for.
            distribution: Optional distribution to look in (e.g., "fedora_38").
            
        Returns:
            PackageDetails if the package is found, None otherwise.
        """
        # Ensure we have fetched repository data
        if not self._package_cache:
            self.fetch_repository_data()
        
        # Look for the package in the specified distribution or all distributions
        for cache_key, packages in self._package_cache.items():
            if distribution and not cache_key.startswith(distribution):
                continue
                
            if package_name in packages:
                pkg_data = packages[package_name]
                
                # Extract dependencies
                dependencies = pkg_data.get("requires", [])
                
                return PackageDetails(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("version"),
                    description=pkg_data.get("summary"),
                    license=pkg_data.get("license"),
                    homepage=pkg_data.get("url"),
                    dependencies=dependencies,
                    maintainer=None,  # RPM doesn't typically include maintainer info in the metadata
                    source_url=pkg_data.get("source_rpm"),
                    download_url=None,  # DNF doesn't provide direct download URLs
                    checksum=pkg_data.get("checksum"),
                    raw_data=pkg_data
                )
        
        return None
    
    def _get_mirror_url(self, metalink_url: str) -> str:
        """
        Get a mirror URL from a metalink URL.
        
        Args:
            metalink_url: Metalink URL.
            
        Returns:
            Mirror URL.
            
        Raises:
            ValueError: If no mirrors are found.
        """
        # Check if we already have a mirror URL for this metalink
        if metalink_url in self._mirror_urls:
            return self._mirror_urls[metalink_url]
        
        # Save the current base_url
        original_base_url = self.base_url
        
        try:
            # Fetch the metalink XML
            response = self._fetch_url(metalink_url)
            metalink_xml = response.text
            
            # Parse the XML to find mirror URLs
            mirrors = parse_metalink_xml(metalink_xml)
            
            # Use the first mirror
            mirror_url = mirrors[0]
            
            # Cache the mirror URL
            self._mirror_urls[metalink_url] = mirror_url
            
            return mirror_url
            
        finally:
            # Restore the original base_url
            self.base_url = original_base_url
    
    def _fetch_primary_location(self, repomd_url: str) -> str:
        """
        Fetch and parse the repomd.xml file to get the primary.xml location.
        
        Args:
            repomd_url: URL to the repomd.xml file.
            
        Returns:
            Location of the primary.xml file.
            
        Raises:
            ValueError: If the primary.xml location is not found.
        """
        # Save the current base_url
        original_base_url = self.base_url
        
        try:
            # Fetch the repomd.xml file
            response = self._fetch_url(repomd_url)
            repomd_xml = response.text
            
            # Use the common utility to parse the XML
            return fetch_primary_location(repomd_xml)
            
        finally:
            # Restore the original base_url
            self.base_url = original_base_url
    
    def _fetch_primary_xml(self, primary_url: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch and parse the primary.xml file.
        
        Args:
            primary_url: URL to the primary.xml file.
            
        Returns:
            Dictionary mapping package names to their metadata.
            
        Raises:
            ValueError: If the primary.xml file cannot be parsed.
        """
        # Save the current base_url
        original_base_url = self.base_url
        
        try:
            # Fetch the primary.xml file
            response = self._fetch_url(primary_url)
            
            # Check if the file is gzipped
            content = response.content
            if primary_url.endswith(".gz"):
                content = decompress_gzip_content(content)
            
            # Parse the XML using the common utility
            return parse_primary_xml(content.decode("utf-8"))
            
        finally:
            # Restore the original base_url
            self.base_url = original_base_url