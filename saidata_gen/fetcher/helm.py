"""
Helm repository fetcher for saidata-gen.

This module provides functionality to fetch Kubernetes Helm chart metadata from
Helm repositories.
"""

import logging
import os
import yaml
import tempfile
import tarfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageDetails, PackageInfo, RepositoryData
)
from saidata_gen.fetcher.base import HttpRepositoryFetcher


logger = logging.getLogger(__name__)


@dataclass
class HelmRepository:
    """
    Configuration for a Helm repository.
    """
    name: str  # e.g., "stable"
    url: str  # e.g., "https://charts.helm.sh/stable"


class HelmFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Helm chart repositories.
    
    This class fetches Helm chart metadata from Helm repositories by querying
    their index files and processing chart archives.
    """
    
    def __init__(
        self,
        repositories: Optional[List[HelmRepository]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Helm fetcher.
        
        Args:
            repositories: List of Helm repositories to fetch. If None, uses default repositories.
            config: Configuration for the fetcher.
        """
        # Use the standard Helm repositories as default
        self.repositories = repositories or [
            HelmRepository(
                name="stable",
                url="https://charts.helm.sh/stable"
            ),
            HelmRepository(
                name="bitnami",
                url="https://charts.bitnami.com/bitnami"
            )
        ]
        
        # Initialize with the first repository
        super().__init__(
            base_url=self.repositories[0].url,
            config=config
        )
        
        # Initialize chart cache
        self._chart_cache: Dict[str, Dict[str, Dict[str, any]]] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "helm"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Helm repositories.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for repo in self.repositories:
            try:
                # Update base URL
                self.base_url = repo.url
                
                # Fetch repository index
                charts = self._fetch_repository_index(repo.name)
                if charts:
                    self._chart_cache[repo.name] = charts
                    result.providers[repo.name] = True
                else:
                    result.success = False
                    result.providers[repo.name] = False
                    result.errors[repo.name] = "No charts found"
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {repo.name}: {e}")
                result.errors[repo.name] = str(e)
                result.providers[repo.name] = False
                result.success = False
        
        return result
    
    def get_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """
        Get information about a specific Helm chart.
        
        Args:
            package_name: Name of the chart to get information for.
            
        Returns:
            PackageInfo if the chart is found, None otherwise.
        """
        # Ensure we have fetched repository data
        if not self._chart_cache:
            self.fetch_repository_data()
        
        # Look for the chart in all repositories
        for repo_name, charts in self._chart_cache.items():
            # Try exact match first
            if package_name in charts:
                chart_data = charts[package_name]
                return self._create_package_info(package_name, chart_data, repo_name)
            
            # Try case-insensitive match
            for chart_name, chart_data in charts.items():
                if chart_name.lower() == package_name.lower():
                    return self._create_package_info(chart_name, chart_data, repo_name)
        
        return None
    
    def search_packages(self, query: str, max_results: int = 10) -> List[PackageInfo]:
        """
        Search for Helm charts matching the query.
        
        Args:
            query: Search query.
            max_results: Maximum number of results to return.
            
        Returns:
            List of PackageInfo objects matching the query.
        """
        # Ensure we have fetched repository data
        if not self._chart_cache:
            self.fetch_repository_data()
        
        results = []
        query_lower = query.lower()
        
        # Search in all repositories
        for repo_name, charts in self._chart_cache.items():
            for chart_name, chart_data in charts.items():
                # Check if the chart name or description contains the query
                if (query_lower in chart_name.lower() or
                    (chart_data.get("description") and query_lower in chart_data["description"].lower())):
                    
                    # Create PackageInfo object
                    pkg_info = self._create_package_info(chart_name, chart_data, repo_name)
                    
                    # Add to results if not already present
                    if not any(r.name == chart_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
        
        return results
    
    def _create_package_info(self, chart_name: str, chart_data: Dict[str, any], repo_name: str) -> PackageInfo:
        """
        Create a PackageInfo object from chart data.
        
        Args:
            chart_name: Name of the chart.
            chart_data: Chart data.
            repo_name: Name of the repository.
            
        Returns:
            PackageInfo object.
        """
        # Add repository information to details
        details = chart_data.copy()
        details["repository"] = repo_name
        
        return PackageInfo(
            name=chart_name,
            provider=self.get_repository_name(),
            version=chart_data.get("version"),
            description=chart_data.get("description"),
            details=details
        )
    
    def _fetch_repository_index(self, repo_name: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch the index file from a Helm repository.
        
        Args:
            repo_name: Name of the repository.
            
        Returns:
            Dictionary mapping chart names to their metadata.
        """
        try:
            # Fetch the index.yaml file
            response = self._fetch_text("index.yaml")
            
            # Parse the YAML
            index = yaml.safe_load(response)
            
            charts = {}
            for chart_name, chart_versions in index.get("entries", {}).items():
                if chart_versions:
                    # Get the latest version
                    latest_version = chart_versions[0]
                    
                    # Extract chart metadata
                    charts[chart_name] = {
                        "name": chart_name,
                        "version": latest_version.get("version"),
                        "description": latest_version.get("description"),
                        "app_version": latest_version.get("appVersion"),
                        "api_version": latest_version.get("apiVersion"),
                        "home": latest_version.get("home"),
                        "sources": latest_version.get("sources", []),
                        "keywords": latest_version.get("keywords", []),
                        "maintainers": latest_version.get("maintainers", []),
                        "icon": latest_version.get("icon"),
                        "urls": latest_version.get("urls", []),
                        "created": latest_version.get("created"),
                        "digest": latest_version.get("digest"),
                        "repository": repo_name
                    }
            
            return charts
        
        except Exception as e:
            logger.warning(f"Failed to fetch repository index for {repo_name}: {e}")
            return {}
    
    def _fetch_chart_details(self, chart_name: str, repo_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch detailed information about a Helm chart.
        
        Args:
            chart_name: Name of the chart.
            repo_name: Name of the repository.
            
        Returns:
            Chart metadata if found, None otherwise.
        """
        # Get the chart from the cache
        if repo_name in self._chart_cache and chart_name in self._chart_cache[repo_name]:
            chart_data = self._chart_cache[repo_name][chart_name]
            
            # If we already have detailed information, return it
            if "values" in chart_data:
                return chart_data
            
            try:
                # Get the chart URL
                chart_url = None
                if "urls" in chart_data and chart_data["urls"]:
                    chart_url = chart_data["urls"][0]
                
                if not chart_url:
                    return chart_data
                
                # Download the chart
                with tempfile.NamedTemporaryFile(suffix='.tgz', delete=False) as temp_file:
                    try:
                        # If the URL is relative, prepend the base URL
                        if not chart_url.startswith(('http://', 'https://')):
                            chart_url = f"{self.base_url}/{chart_url}"
                        
                        # Download the chart
                        self.base_url = ""  # Clear base URL for direct download
                        self._fetch_binary(chart_url, temp_file.name)
                        
                        # Extract values.yaml from the chart
                        with tarfile.open(temp_file.name, 'r:gz') as tar:
                            # Find the values.yaml file
                            values_file = None
                            for member in tar.getmembers():
                                if member.name.endswith('/values.yaml'):
                                    values_file = member
                                    break
                            
                            if values_file:
                                # Extract values.yaml
                                values_content = tar.extractfile(values_file).read().decode('utf-8')
                                
                                # Parse values.yaml
                                values = yaml.safe_load(values_content)
                                
                                # Add values to chart data
                                chart_data["values"] = values
                    
                    finally:
                        # Clean up the temporary file
                        if os.path.exists(temp_file.name):
                            os.unlink(temp_file.name)
                
                return chart_data
            
            except Exception as e:
                logger.warning(f"Failed to fetch chart details for {chart_name} from {repo_name}: {e}")
                return chart_data
        
        return None