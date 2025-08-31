"""
Slackpkg repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from Slackware
package repositories.
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
class SlackpkgRepository:
    """
    Configuration for a Slackpkg repository.
    """
    name: str  # e.g., "slackware64-15.0"
    url: str  # e.g., "https://mirrors.slackware.com/slackware/slackware64-15.0"
    sections: List[str] = None  # e.g., ["a", "ap", "d", "l", "n", "x"]


class SlackpkgFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Slackware package repositories.
    
    This class fetches package metadata from Slackware package repositories
    by downloading and parsing PACKAGES.TXT files.
    """
    
    def __init__(
        self,
        repositories: Optional[List[SlackpkgRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Slackpkg fetcher.
        
        Args:
            repositories: List of Slackpkg repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Initialize with a dummy base_url, we'll use repository-specific URLs
        super().__init__(base_url="https://example.com", config=config)
        
        # Set up default repositories if none provided
        self.repositories = repositories or [
            SlackpkgRepository(
                name="slackware64-15.0",
                url="https://mirrors.slackware.com/slackware/slackware64-15.0",
                sections=["a", "ap", "d", "l", "n", "x"]
            )
        ]
        
        # Initialize package cache
        self._package_cache: Dict[str, Dict[str, Dict[str, any]]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "slackpkg"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Slackpkg repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for repo in self.repositories:
            repo_key = repo.name
            try:
                # Check if we have a valid cache
                cached_data = self._get_from_cache(repo_key)
                if cached_data:
                    self._package_cache[repo_key] = cached_data
                    result.cache_hits[repo_key] = True
                    continue
                
                # Fetch and parse PACKAGES.TXT files for each section
                packages_data = {}
                sections = repo.sections or ["a", "ap", "d", "l", "n", "x"]
                
                for section in sections:
                    try:
                        section_data = self._fetch_packages_file(repo, section)
                        packages_data.update(section_data)
                    except Exception as e:
                        logger.warning(f"Failed to fetch packages for section {section}: {e}")
                
                if packages_data:
                    self._package_cache[repo_key] = packages_data
                    self._save_to_cache(repo_key, packages_data)
                    result.providers[repo_key] = True
                else:
                    result.success = False
                    result.providers[repo_key] = False
                    result.errors[repo_key] = "No packages found"
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {repo_key}: {e}")
                result.errors[repo_key] = str(e)
                result.providers[repo_key] = False
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
            if package_name in packages:
                pkg_data = packages[package_name]
                return PackageInfo(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("version"),
                    description=pkg_data.get("description"),
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
        
        # Search in all repositories
        for repo_name, packages in self._package_cache.items():
            for pkg_name, pkg_data in packages.items():
                # Check if the package name or description contains the query
                if (query_lower in pkg_name.lower() or 
                    (pkg_data.get("description") and query_lower in pkg_data["description"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = PackageInfo(
                        name=pkg_name,
                        provider=self.get_repository_name(),
                        version=pkg_data.get("version"),
                        description=pkg_data.get("description"),
                        details=pkg_data
                    )
                    
                    # Add to results if not already present
                    if not any(r.name == pkg_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
        
        return results
    
    def get_package_details(self, package_name: str, repository: Optional[str] = None) -> Optional[PackageDetails]:
        """
        Get detailed information about a specific package.
        
        Args:
            package_name: Name of the package to get information for.
            repository: Optional repository to look in.
            
        Returns:
            PackageDetails if the package is found, None otherwise.
        """
        # Ensure we have fetched repository data
        if not self._package_cache:
            self.fetch_repository_data()
        
        # Look for the package in the specified repository or all repositories
        for repo_name, packages in self._package_cache.items():
            if repository and repo_name != repository:
                continue
                
            if package_name in packages:
                pkg_data = packages[package_name]
                
                # Parse dependencies (Slackware doesn't have formal dependency info)
                dependencies = []
                if "requires" in pkg_data:
                    for dep in pkg_data["requires"].split(","):
                        dep = dep.strip()
                        if dep:
                            dependencies.append(dep)
                
                return PackageDetails(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("version"),
                    description=pkg_data.get("description"),
                    license=None,  # Slackware doesn't provide license info in PACKAGES.TXT
                    homepage=None,  # Slackware doesn't provide homepage info in PACKAGES.TXT
                    dependencies=dependencies,
                    maintainer=None,  # Slackware doesn't provide maintainer info in PACKAGES.TXT
                    source_url=None,
                    download_url=pkg_data.get("location"),
                    checksum=None,
                    raw_data=pkg_data
                )
        
        return None
    
    def _fetch_packages_file(self, repo: SlackpkgRepository, section: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch and parse a PACKAGES.TXT file from a Slackpkg repository.
        
        Args:
            repo: Repository configuration.
            section: Repository section (e.g., "a", "ap", "d").
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        # Save the current base_url
        original_base_url = self.base_url
        
        try:
            # Set the base_url for this request
            self.base_url = repo.url
            
            # Fetch the PACKAGES.TXT file
            packages_path = f"slackware/{section}/PACKAGES.TXT"
            
            try:
                packages_text = self._fetch_text(packages_path)
                return self._parse_packages_file(packages_text, section)
            except Exception as e:
                logger.warning(f"Failed to fetch PACKAGES.TXT for section {section}, trying PACKAGES.TXT.gz: {e}")
                
                # Try gzipped version
                response = self._fetch_url(f"{packages_path}.gz")
                
                # Decompress the gzipped content
                with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
                    packages_text = f.read().decode("utf-8")
                
                return self._parse_packages_file(packages_text, section)
            
        except Exception as e:
            logger.warning(f"Failed to fetch packages for section {section}: {e}")
            return {}
        finally:
            # Restore the original base_url
            self.base_url = original_base_url
    
    def _parse_packages_file(self, packages_text: str, section: str) -> Dict[str, Dict[str, any]]:
        """
        Parse a PACKAGES.TXT file from a Slackpkg repository.
        
        Args:
            packages_text: Content of the PACKAGES.TXT file.
            section: Repository section (e.g., "a", "ap", "d").
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        current_package = None
        current_data = {}
        
        # Split the file into package entries (separated by blank lines)
        packages = packages_text.split("\n\n")
        
        for package_text in packages:
            if not package_text.strip():
                continue
            
            # Parse package entry
            lines = package_text.strip().split("\n")
            
            # First line contains the package filename
            if not lines:
                continue
                
            # Extract package name, version, and architecture from filename
            filename_match = re.match(r'PACKAGE NAME:\s+(.+)\.t[gx]z$', lines[0])
            if not filename_match:
                continue
                
            filename = filename_match.group(1)
            
            # Parse package name and version
            name_parts = filename.split("-")
            if len(name_parts) < 2:
                continue
                
            # Last part is the architecture
            arch = name_parts[-1]
            
            # Second to last part is the build number
            build = name_parts[-2]
            
            # Parts before that are version
            version_parts = []
            for i in range(len(name_parts) - 3, -1, -1):
                if re.match(r'^[0-9]', name_parts[i]):
                    version_parts.insert(0, name_parts[i])
                else:
                    break
            
            # Remaining parts are the package name
            name_end_index = len(name_parts) - len(version_parts) - 2
            pkg_name = "-".join(name_parts[:name_end_index + 1])
            version = "-".join(version_parts)
            
            # Create package data
            pkg_data = {
                "name": pkg_name,
                "version": version,
                "build": build,
                "arch": arch,
                "section": section,
                "filename": f"{filename}.tgz"
            }
            
            # Parse additional metadata
            for line in lines[1:]:
                if line.startswith("PACKAGE LOCATION: "):
                    pkg_data["location"] = line[18:].strip()
                elif line.startswith("PACKAGE SIZE (compressed): "):
                    pkg_data["size_compressed"] = line[27:].strip()
                elif line.startswith("PACKAGE SIZE (uncompressed): "):
                    pkg_data["size_uncompressed"] = line[29:].strip()
                elif line.startswith("PACKAGE REQUIRED: "):
                    pkg_data["requires"] = line[18:].strip()
                elif line.startswith("PACKAGE DESCRIPTION:"):
                    # Description can span multiple lines
                    description_lines = []
                    for desc_line in lines[lines.index(line) + 1:]:
                        if desc_line.startswith("PACKAGE "):
                            break
                        description_lines.append(desc_line.strip())
                    pkg_data["description"] = " ".join(description_lines)
            
            # Add package to result
            result[pkg_name] = pkg_data
        
        return result