"""
APT/DEB repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from APT/DEB
repositories, including Debian and Ubuntu.
"""

import gzip
import io
import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import HttpRepositoryFetcher


logger = logging.getLogger(__name__)


@dataclass
class APTDistribution:
    """
    Configuration for an APT distribution.
    """
    name: str  # e.g., "debian", "ubuntu"
    version: str  # e.g., "bookworm", "jammy"
    url: str  # e.g., "https://deb.debian.org/debian/dists/bookworm"
    components: List[str] = None  # e.g., ["main", "contrib", "non-free"]
    architectures: List[str] = None  # e.g., ["amd64", "i386"]


class APTFetcher(HttpRepositoryFetcher):
    """
    Fetcher for APT/DEB repositories.
    
    This class fetches package metadata from APT/DEB repositories,
    including Debian and Ubuntu.
    """
    
    def __init__(
        self,
        distributions: Optional[List[APTDistribution]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the APT fetcher.
        
        Args:
            distributions: List of APT distributions to fetch. If None, uses default distributions.
            config: Configuration for the fetcher.
        """
        # Initialize with a dummy base_url, we'll use distribution-specific URLs
        super().__init__(base_url="https://example.com", config=config)
        
        # Set up default distributions if none provided
        self.distributions = distributions or [
            APTDistribution(
                name="debian",
                version="bookworm",
                url="https://deb.debian.org/debian/dists/bookworm",
                components=["main"],
                architectures=["amd64"]
            ),
            APTDistribution(
                name="debian",
                version="bullseye",
                url="https://deb.debian.org/debian/dists/bullseye",
                components=["main"],
                architectures=["amd64"]
            ),
            APTDistribution(
                name="ubuntu",
                version="jammy",
                url="http://archive.ubuntu.com/ubuntu/dists/jammy",
                components=["main"],
                architectures=["amd64"]
            ),
            APTDistribution(
                name="ubuntu",
                version="focal",
                url="http://archive.ubuntu.com/ubuntu/dists/focal",
                components=["main"],
                architectures=["amd64"]
            )
        ]
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, PackageInfo]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "apt"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from APT repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for dist in self.distributions:
            dist_key = f"{dist.name}_{dist.version}"
            try:
                # Fetch Release file to get component and architecture info if not specified
                if not dist.components or not dist.architectures:
                    release_data = self._fetch_release_file(dist.url)
                    if not dist.components:
                        dist.components = release_data.get("components", ["main"])
                    if not dist.architectures:
                        dist.architectures = release_data.get("architectures", ["amd64"])
                
                # Fetch Packages files for each component and architecture
                for component in dist.components:
                    for arch in dist.architectures:
                        packages_url = f"{component}/binary-{arch}/Packages.gz"
                        cache_key = f"{dist_key}_{component}_{arch}"
                        
                        # Check if we have a valid cache
                        cached_data = self._get_from_cache(cache_key)
                        if cached_data:
                            self._package_cache[cache_key] = cached_data
                            result.cache_hits[cache_key] = True
                            continue
                        
                        # Fetch and parse Packages.gz
                        try:
                            packages_data = self._fetch_packages_file(dist.url, packages_url)
                            self._package_cache[cache_key] = packages_data
                            self._save_to_cache(cache_key, packages_data)
                            result.providers[cache_key] = True
                        except Exception as e:
                            logger.error(f"Failed to fetch Packages file for {cache_key}: {e}")
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
                    version=pkg_data.get("Version"),
                    description=pkg_data.get("Description", "").split("\\n")[0] if pkg_data.get("Description") else None,
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
                    (pkg_data.get("Description") and query_lower in pkg_data["Description"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = PackageInfo(
                        name=pkg_name,
                        provider=self.get_repository_name(),
                        version=pkg_data.get("Version"),
                        description=pkg_data.get("Description", "").split("\\n")[0] if pkg_data.get("Description") else None,
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
            distribution: Optional distribution to look in (e.g., "debian_bookworm").
            
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
                
                # Parse dependencies
                dependencies = []
                if "Depends" in pkg_data:
                    # Split by comma, then extract package names (ignoring version constraints)
                    for dep in pkg_data["Depends"].split(","):
                        dep = dep.strip()
                        # Extract package name (everything before the first space or parenthesis)
                        match = re.match(r"([^\s\(]+)", dep)
                        if match:
                            dependencies.append(match.group(1))
                
                # Extract first line of description as summary
                description = pkg_data.get("Description", "")
                summary = description.split("\\n")[0] if description else None
                
                return PackageDetails(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("Version"),
                    description=summary,
                    license=pkg_data.get("License"),
                    homepage=pkg_data.get("Homepage"),
                    dependencies=dependencies,
                    maintainer=pkg_data.get("Maintainer"),
                    source_url=pkg_data.get("Source"),
                    download_url=None,  # APT doesn't provide direct download URLs
                    checksum=pkg_data.get("SHA256"),
                    raw_data=pkg_data
                )
        
        return None
    
    def _fetch_release_file(self, base_url: str) -> Dict[str, any]:
        """
        Fetch and parse the Release file from an APT repository.
        
        Args:
            base_url: Base URL of the repository.
            
        Returns:
            Dictionary with parsed Release file data.
        """
        # Save the current base_url
        original_base_url = self.base_url
        
        try:
            # Set the base_url for this request
            self.base_url = base_url
            
            # Fetch the Release file
            release_text = self._fetch_text("Release")
            
            # Parse the Release file (RFC822-style format)
            result = {}
            current_key = None
            current_value = []
            
            for line in release_text.splitlines():
                if not line.strip():
                    continue
                    
                if line.startswith(" "):
                    # Continuation of previous value
                    if current_key:
                        current_value.append(line.strip())
                else:
                    # New key-value pair
                    if current_key:
                        result[current_key] = " ".join(current_value)
                        current_value = []
                    
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        current_key = parts[0].strip()
                        current_value = [parts[1].strip()]
            
            # Add the last key-value pair
            if current_key:
                result[current_key] = " ".join(current_value)
            
            # Parse components and architectures
            if "Components" in result:
                result["components"] = result["Components"].split()
            if "Architectures" in result:
                result["architectures"] = result["Architectures"].split()
            
            return result
            
        finally:
            # Restore the original base_url
            self.base_url = original_base_url
    
    def _fetch_packages_file(self, base_url: str, packages_path: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch and parse a Packages.gz file from an APT repository.
        
        Args:
            base_url: Base URL of the repository.
            packages_path: Path to the Packages.gz file.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        # Save the current base_url
        original_base_url = self.base_url
        
        try:
            # Set the base_url for this request
            self.base_url = base_url
            
            # Fetch the Packages.gz file
            response = self._fetch_url(f"{base_url}/{packages_path}")
            
            # Decompress the gzipped content
            with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
                packages_text = f.read().decode("utf-8")
            
            # Parse the Packages file
            return self._parse_packages_file(packages_text)
            
        finally:
            # Restore the original base_url
            self.base_url = original_base_url
    
    def _parse_packages_file(self, packages_text: str) -> Dict[str, Dict[str, any]]:
        """
        Parse a Packages file from an APT repository.
        
        Args:
            packages_text: Content of the Packages file.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        current_package = None
        current_data = {}
        current_key = None
        current_value = []
        
        for line in packages_text.splitlines():
            if not line.strip():
                # Empty line indicates end of a package entry
                if current_key and current_package:
                    current_data[current_key] = "\\n".join(current_value)
                if current_package and current_data:
                    result[current_package] = current_data
                current_package = None
                current_data = {}
                current_key = None
                current_value = []
                continue
                
            if line.startswith(" "):
                # Continuation of previous value
                if current_key:
                    current_value.append(line.strip())
            else:
                # New key-value pair
                if current_key:
                    current_data[current_key] = "\\n".join(current_value)
                    current_value = []
                
                parts = line.split(":", 1)
                if len(parts) == 2:
                    current_key = parts[0].strip()
                    current_value = [parts[1].strip()]
                    
                    # If this is the Package field, set the current package
                    if current_key == "Package":
                        current_package = current_value[0]
        
        # Add the last package (handle case where file doesn't end with empty line)
        if current_key and current_package:
            current_data[current_key] = "\\n".join(current_value)
        if current_package and current_data:
            result[current_package] = current_data
        
        return result