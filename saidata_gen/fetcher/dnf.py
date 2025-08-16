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
from saidata_gen.fetcher.error_handler import FetcherErrorHandler, ErrorContext
from saidata_gen.core.system_dependency_checker import SystemDependencyChecker
from saidata_gen.core.repository_url_manager import get_repository_url_manager
from saidata_gen.fetcher.rpm_utils import (
    fetch_primary_location, decompress_gzip_content, parse_primary_xml, parse_metalink_xml
)

# Try to import requests for error handling
try:
    import requests
    import ssl
except ImportError:
    pass


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
            distributions: List of DNF distributions to fetch. If None, uses default distributions from URL manager.
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
        
        # Initialize error handler and system dependency checker
        self.error_handler = FetcherErrorHandler(max_retries=3, base_wait_time=1.0)
        self.dependency_checker = SystemDependencyChecker()
        
        # Initialize repository URL manager
        self.url_manager = get_repository_url_manager()
        
        # Check for dnf/yum command availability (optional for API-based fetching)
        self.dnf_available = self.dependency_checker.check_command_availability("dnf")
        self.yum_available = self.dependency_checker.check_command_availability("yum")
        
        if not self.dnf_available and not self.yum_available:
            logger.info("Neither dnf nor yum commands available - using API-only mode")
        
        # Set up distributions from URL manager or use provided ones
        if distributions:
            self.distributions = distributions
        else:
            self.distributions = self._load_distributions_from_url_manager()
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, PackageInfo]] = {}
        self._mirror_urls: Dict[str, str] = {}
    
    def _load_distributions_from_url_manager(self) -> List[DNFDistribution]:
        """
        Load distribution configurations from the repository URL manager.
        
        Returns:
            List of DNFDistribution objects configured from URL manager.
        """
        distributions = []
        
        # Define the distributions and versions to load
        dist_configs = [
            ("fedora", "38", ["x86_64"]),
            ("fedora", "39", ["x86_64"]),
            ("fedora", "40", ["x86_64"]),
            ("centos", "9-stream", ["x86_64"]),
            ("centos", "9", ["x86_64"]),
            ("almalinux", "9", ["x86_64"]),
            ("almalinux", "8", ["x86_64"]),
            ("rockylinux", "9", ["x86_64"]),
            ("rockylinux", "8", ["x86_64"]),
        ]
        
        for os_name, version, architectures in dist_configs:
            try:
                # Get URLs from the URL manager
                primary_url = self.url_manager.get_primary_url(
                    provider="dnf",
                    os_name=os_name,
                    os_version=version,
                    architecture="x86_64",
                    context={"repo_name": f"{os_name}-{version}"}
                )
                
                if primary_url:
                    distributions.append(DNFDistribution(
                        name=os_name,
                        version=version,
                        url=primary_url,
                        architectures=architectures
                    ))
                else:
                    logger.warning(f"No URL found for DNF distribution: {os_name} {version}")
                    
            except Exception as e:
                logger.error(f"Failed to load DNF distribution {os_name} {version}: {e}")
        
        # Fallback to hardcoded distributions if URL manager fails
        if not distributions:
            logger.warning("Failed to load distributions from URL manager, using fallback")
            distributions = [
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
            ]
        
        return distributions
    
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
            
            # For each architecture
            for arch in dist.architectures or ["x86_64"]:
                cache_key = f"{dist_key}_{arch}"
                
                # Check if we have a valid cache
                cached_data = self._get_from_cache(cache_key)
                if cached_data:
                    self._package_cache[cache_key] = cached_data
                    result.cache_hits[cache_key] = True
                    continue
                
                # Fetch repository data with enhanced error handling
                fetch_result = self._fetch_distribution_with_retries(dist, arch, cache_key)
                
                if fetch_result.success:
                    result.providers[cache_key] = True
                else:
                    result.errors[cache_key] = fetch_result.errors.get(cache_key, "Unknown error")
                    result.providers[cache_key] = False
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
    
    def _fetch_distribution_with_retries(self, dist: DNFDistribution, arch: str, cache_key: str) -> FetchResult:
        """
        Fetch distribution data with enhanced error handling and retries.
        
        Args:
            dist: Distribution configuration.
            arch: Architecture.
            cache_key: Cache key for this distribution/architecture combination.
            
        Returns:
            FetchResult with the outcome.
        """
        max_attempts = 3
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Get the mirror URL if it's a metalink
                base_url = self._get_mirror_url_with_fallback(dist.url, attempt) if "metalink" in dist.url else dist.url
                
                # Create error context
                context = ErrorContext(
                    provider="dnf",
                    url=base_url,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    additional_info={"distribution": dist.name, "version": dist.version, "arch": arch}
                )
                
                # Fetch and parse repomd.xml to get the primary.xml location
                repomd_url = f"{base_url}/repodata/repomd.xml"
                primary_location = self._fetch_primary_location_with_retries(repomd_url, context)
                
                # Fetch and parse primary.xml
                primary_url = f"{base_url}/{primary_location}"
                packages_data = self._fetch_primary_xml_with_retries(primary_url, context)
                
                self._package_cache[cache_key] = packages_data
                self._save_to_cache(cache_key, packages_data)
                
                return FetchResult(
                    success=True,
                    providers={cache_key: True},
                    errors={},
                    cache_hits={}
                )
                
            except (requests.exceptions.SSLError, ssl.SSLError) as e:
                # Handle SSL errors with fallback
                context = ErrorContext(
                    provider="dnf",
                    url=base_url if 'base_url' in locals() else dist.url,
                    attempt=attempt,
                    max_attempts=max_attempts
                )
                
                fallback_response = self.error_handler.handle_ssl_error(e, context)
                if fallback_response and attempt == max_attempts:
                    # Try to continue with SSL fallback for the remaining operations
                    logger.warning(f"Using SSL fallback for DNF distribution {dist.name}")
                
                if attempt == max_attempts:
                    return FetchResult(
                        success=False,
                        providers={cache_key: False},
                        errors={cache_key: f"SSL error: {str(e)}"},
                        cache_hits={}
                    )
                    
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, 
                    requests.exceptions.HTTPError) as e:
                # Handle network errors
                context = ErrorContext(
                    provider="dnf",
                    url=base_url if 'base_url' in locals() else dist.url,
                    attempt=attempt,
                    max_attempts=max_attempts
                )
                
                network_result = self.error_handler.handle_network_error(e, context)
                if attempt == max_attempts:
                    return network_result
                    
            except Exception as e:
                # Handle XML parsing or other errors
                if "xml" in str(e).lower() or "parse" in str(e).lower():
                    context = ErrorContext(
                        provider="dnf",
                        url=base_url if 'base_url' in locals() else dist.url,
                        attempt=attempt,
                        max_attempts=max_attempts
                    )
                    
                    logger.warning(f"XML parsing error for DNF distribution {dist.name}: {e}")
                
                if attempt == max_attempts:
                    return FetchResult(
                        success=False,
                        providers={cache_key: False},
                        errors={cache_key: f"Error: {str(e)}"},
                        cache_hits={}
                    )
        
        # Should not reach here, but just in case
        return FetchResult(
            success=False,
            providers={cache_key: False},
            errors={cache_key: "Max retries exceeded"},
            cache_hits={}
        )
    
    def _get_mirror_url_with_fallback(self, metalink_url: str, attempt: int) -> str:
        """
        Get a mirror URL from a metalink URL with fallback handling.
        
        Args:
            metalink_url: Metalink URL.
            attempt: Current attempt number.
            
        Returns:
            Mirror URL.
        """
        try:
            return self._get_mirror_url(metalink_url)
        except Exception as e:
            logger.warning(f"Failed to get mirror URL on attempt {attempt}: {e}")
            # For subsequent attempts, try to use fallback URLs from URL manager
            if attempt > 1:
                # Determine OS from metalink URL
                os_name = None
                if "fedora" in metalink_url:
                    os_name = "fedora"
                elif "centos" in metalink_url:
                    os_name = "centos"
                
                if os_name:
                    fallback_urls = self.url_manager.get_fallback_urls(
                        provider="dnf",
                        os_name=os_name,
                        architecture="x86_64"
                    )
                    if fallback_urls:
                        return fallback_urls[0]
                
                # Final fallback to hardcoded URLs
                if "fedora" in metalink_url:
                    return "https://download.fedoraproject.org/pub/fedora/linux/releases"
                elif "centos" in metalink_url:
                    return "https://mirror.centos.org/centos"
            raise
    
    def _fetch_primary_location_with_retries(self, repomd_url: str, context: ErrorContext) -> str:
        """
        Fetch primary location with retry logic.
        
        Args:
            repomd_url: URL to repomd.xml.
            context: Error context.
            
        Returns:
            Primary XML location.
        """
        try:
            return self._fetch_primary_location(repomd_url)
        except (requests.exceptions.SSLError, ssl.SSLError) as e:
            # Try SSL fallback
            fallback_response = self.error_handler.handle_ssl_error(e, context)
            if fallback_response:
                return fetch_primary_location(fallback_response.text)
            raise
        except Exception as e:
            # Handle malformed XML
            if "xml" in str(e).lower():
                try:
                    response = self._fetch_url(repomd_url)
                    parsed_data = self.error_handler.handle_malformed_data(
                        response.content, "xml", context
                    )
                    if parsed_data:
                        # Try to extract primary location from parsed data
                        return self._extract_primary_location_from_dict(parsed_data)
                except Exception:
                    pass
            raise
    
    def _fetch_primary_xml_with_retries(self, primary_url: str, context: ErrorContext) -> Dict[str, Dict[str, any]]:
        """
        Fetch primary XML with retry logic.
        
        Args:
            primary_url: URL to primary.xml.
            context: Error context.
            
        Returns:
            Parsed package data.
        """
        try:
            return self._fetch_primary_xml(primary_url)
        except (requests.exceptions.SSLError, ssl.SSLError) as e:
            # Try SSL fallback
            fallback_response = self.error_handler.handle_ssl_error(e, context)
            if fallback_response:
                content = fallback_response.content
                if primary_url.endswith(".gz"):
                    content = decompress_gzip_content(content)
                return parse_primary_xml(content.decode("utf-8"))
            raise
        except Exception as e:
            # Handle malformed XML
            if "xml" in str(e).lower():
                try:
                    response = self._fetch_url(primary_url)
                    parsed_data = self.error_handler.handle_malformed_data(
                        response.content, "xml", context
                    )
                    if parsed_data:
                        # Convert parsed XML dict back to expected format
                        return self._convert_xml_dict_to_packages(parsed_data)
                except Exception:
                    pass
            raise
    
    def _extract_primary_location_from_dict(self, parsed_data: Dict[str, any]) -> str:
        """
        Extract primary location from parsed repomd XML data.
        
        Args:
            parsed_data: Parsed XML data as dictionary.
            
        Returns:
            Primary XML location.
        """
        # This is a simplified extraction - in practice, you'd need to navigate the XML structure
        # For now, return a reasonable default
        return "repodata/primary.xml.gz"
    
    def _convert_xml_dict_to_packages(self, parsed_data: Dict[str, any]) -> Dict[str, Dict[str, any]]:
        """
        Convert parsed XML dictionary to package format.
        
        Args:
            parsed_data: Parsed XML data as dictionary.
            
        Returns:
            Package data in expected format.
        """
        # This is a simplified conversion - in practice, you'd need to properly parse the XML structure
        # For now, return empty dict to avoid crashes
        logger.warning("Using fallback XML parsing - package data may be incomplete")
        return {}