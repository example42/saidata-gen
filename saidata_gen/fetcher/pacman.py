"""
Pacman repository fetcher for saidata-gen.

This module provides functionality to fetch package metadata from Arch Linux
Pacman repositories.
"""

import logging
import os
import re
import tarfile
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import HttpRepositoryFetcher


logger = logging.getLogger(__name__)


@dataclass
class PacmanRepository:
    """
    Configuration for a Pacman repository.
    """
    name: str  # e.g., "core", "extra", "community"
    url: str  # e.g., "https://mirrors.kernel.org/archlinux/core/os/x86_64"
    architecture: str = "x86_64"  # Default architecture


class PacmanFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Arch Linux Pacman repositories.
    
    This class fetches package metadata from Arch Linux Pacman repositories
    by downloading and parsing repository databases.
    """
    
    def __init__(
        self,
        repositories: Optional[List[PacmanRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Pacman fetcher.
        
        Args:
            repositories: List of Pacman repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Initialize with a dummy base_url, we'll use repository-specific URLs
        super().__init__(base_url="https://example.com", config=config)
        
        # Set up default repositories if none provided
        self.repositories = repositories or [
            PacmanRepository(
                name="core",
                url="https://mirrors.kernel.org/archlinux/core/os/x86_64"
            ),
            PacmanRepository(
                name="extra",
                url="https://mirrors.kernel.org/archlinux/extra/os/x86_64"
            ),
            PacmanRepository(
                name="community",
                url="https://mirrors.kernel.org/archlinux/community/os/x86_64"
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
        return "pacman"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Pacman repositories.
        
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
                
                # Fetch and parse repository database
                packages_data = self._fetch_repository_database(repo)
                if packages_data:
                    self._package_cache[repo_key] = packages_data
                    self._save_to_cache(repo_key, packages_data)
                    result.providers[repo_key] = True
                else:
                    result.success = False
                    result.providers[repo_key] = False
                    result.errors[repo_key] = "Failed to fetch repository database"
            
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
                    version=pkg_data.get("VERSION"),
                    description=pkg_data.get("DESC"),
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
                    (pkg_data.get("DESC") and query_lower in pkg_data["DESC"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = PackageInfo(
                        name=pkg_name,
                        provider=self.get_repository_name(),
                        version=pkg_data.get("VERSION"),
                        description=pkg_data.get("DESC"),
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
                
                # Parse dependencies
                dependencies = []
                if "DEPENDS" in pkg_data:
                    # Split dependencies and extract package names
                    for dep in pkg_data["DEPENDS"].split():
                        # Remove version constraints
                        dep_name = re.sub(r'[<>=].*', '', dep)
                        if dep_name:
                            dependencies.append(dep_name)
                
                return PackageDetails(
                    name=package_name,
                    provider=self.get_repository_name(),
                    version=pkg_data.get("VERSION"),
                    description=pkg_data.get("DESC"),
                    license=pkg_data.get("LICENSE"),
                    homepage=pkg_data.get("URL"),
                    dependencies=dependencies,
                    maintainer=pkg_data.get("PACKAGER"),
                    source_url=pkg_data.get("URL"),
                    download_url=None,
                    checksum=pkg_data.get("MD5SUM"),
                    raw_data=pkg_data
                )
        
        return None
    
    def _fetch_repository_database(self, repo: PacmanRepository) -> Dict[str, Dict[str, any]]:
        """
        Fetch and parse a Pacman repository database.
        
        Args:
            repo: Repository configuration.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        # Save the current base_url
        original_base_url = self.base_url
        
        try:
            # Set the base_url for this request
            self.base_url = repo.url
            
            # Create a temporary directory for the database
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download the database file
                db_file = f"{repo.name}.db.tar.gz"
                db_path = os.path.join(temp_dir, db_file)
                
                try:
                    self._fetch_binary(db_file, db_path)
                except Exception as e:
                    logger.warning(f"Failed to fetch {db_file}, trying {repo.name}.db: {e}")
                    # Some mirrors use .db instead of .db.tar.gz
                    db_file = f"{repo.name}.db"
                    db_path = os.path.join(temp_dir, db_file)
                    self._fetch_binary(db_file, db_path)
                
                # Parse the database
                return self._parse_pacman_database(db_path)
                
        finally:
            # Restore the original base_url
            self.base_url = original_base_url
    
    def _parse_pacman_database(self, db_path: str) -> Dict[str, Dict[str, any]]:
        """
        Parse a Pacman repository database.
        
        Args:
            db_path: Path to the database file.
            
        Returns:
            Dictionary mapping package names to their metadata.
        """
        result = {}
        
        try:
            with tarfile.open(db_path, 'r:gz') as tar:
                # Group files by directory (package)
                packages = {}
                for member in tar.getmembers():
                    if member.isdir():
                        continue
                    
                    # Extract package name and file name
                    parts = member.name.split('/')
                    if len(parts) < 2:
                        continue
                    
                    pkg_dir = parts[0]
                    file_name = parts[-1]
                    
                    # Initialize package entry if needed
                    if pkg_dir not in packages:
                        packages[pkg_dir] = {}
                    
                    # Extract file content
                    if member.isfile():
                        try:
                            content = tar.extractfile(member).read().decode('utf-8')
                            packages[pkg_dir][file_name] = content
                        except Exception as e:
                            logger.warning(f"Failed to extract {member.name}: {e}")
                
                # Process each package
                for pkg_dir, files in packages.items():
                    # Extract package name from directory (remove version)
                    pkg_name_match = re.match(r'(.+)-[^-]+-\d+', pkg_dir)
                    if pkg_name_match:
                        pkg_name = pkg_name_match.group(1)
                    else:
                        pkg_name = pkg_dir
                    
                    # Create package metadata
                    pkg_data = {}
                    
                    # Process each file
                    for file_name, content in files.items():
                        if file_name == 'desc':
                            # Parse desc file
                            current_key = None
                            for line in content.splitlines():
                                line = line.strip()
                                if not line:
                                    continue
                                
                                if line.startswith('%') and line.endswith('%'):
                                    # New key
                                    current_key = line[1:-1]
                                    pkg_data[current_key] = ""
                                elif current_key:
                                    # Append to current key
                                    if pkg_data[current_key]:
                                        pkg_data[current_key] += " " + line
                                    else:
                                        pkg_data[current_key] = line
                        
                        elif file_name == 'depends':
                            # Parse depends file
                            current_key = None
                            for line in content.splitlines():
                                line = line.strip()
                                if not line:
                                    continue
                                
                                if line.startswith('%') and line.endswith('%'):
                                    # New key
                                    current_key = line[1:-1]
                                    if current_key not in pkg_data:
                                        pkg_data[current_key] = []
                                elif current_key:
                                    # Add to current key list
                                    pkg_data[current_key].append(line)
                            
                            # Convert lists to strings
                            for key in ['DEPENDS', 'CONFLICTS', 'PROVIDES', 'REPLACES']:
                                if key in pkg_data and isinstance(pkg_data[key], list):
                                    pkg_data[key] = ' '.join(pkg_data[key])
                    
                    # Add package to result
                    result[pkg_name] = pkg_data
        
        except Exception as e:
            logger.error(f"Failed to parse Pacman database: {e}")
        
        return result