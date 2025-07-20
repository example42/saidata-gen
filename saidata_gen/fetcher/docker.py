"""
Docker Hub repository fetcher for saidata-gen.

This module provides functionality to fetch container metadata from Docker Hub.
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
class DockerRegistry:
    """
    Configuration for a Docker registry.
    """
    name: str  # e.g., "docker-hub"
    url: str  # e.g., "https://hub.docker.com/v2/"
    auth_url: Optional[str] = None  # URL for authentication, if needed


class DockerFetcher(HttpRepositoryFetcher):
    """
    Fetcher for Docker Hub and other Docker registries.
    
    This class fetches container metadata from Docker registries by querying
    their APIs.
    """
    
    def __init__(
        self,
        registries: Optional[List[DockerRegistry]] = None,
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Docker fetcher.
        
        Args:
            registries: List of Docker registries to fetch. If None, uses default registries.
            config: Configuration for the fetcher.
        """
        # Use Docker Hub as the default registry
        self.registries = registries or [
            DockerRegistry(
                name="docker-hub",
                url="https://hub.docker.com/v2/",
                auth_url="https://auth.docker.io/token"
            )
        ]
        
        # Initialize with the first registry
        super().__init__(
            base_url=self.registries[0].url,
            config=config,
            headers={"Accept": "application/json"}
        )
        
        # Initialize container cache
        self._container_cache: Dict[str, Dict[str, Dict[str, any]]] = {}
        
        # Authentication tokens
        self._auth_tokens: Dict[str, str] = {}
    
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        return "docker"
    
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from Docker registries.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        result = FetchResult(success=True)
        
        for registry in self.registries:
            try:
                # Update base URL
                self.base_url = registry.url
                
                # Fetch popular images as a sample
                images = self._fetch_popular_images(registry.name)
                if images:
                    self._container_cache[registry.name] = images
                    result.providers[registry.name] = True
                else:
                    result.success = False
                    result.providers[registry.name] = False
                    result.errors[registry.name] = "No images found"
            
            except Exception as e:
                logger.error(f"Failed to fetch repository data for {registry.name}: {e}")
                result.errors[registry.name] = str(e)
                result.providers[registry.name] = False
                result.success = False
        
        return result
    
    def get_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """
        Get information about a specific container image.
        
        Args:
            package_name: Name of the container image to get information for.
            
        Returns:
            PackageInfo if the image is found, None otherwise.
        """
        # Ensure we have fetched repository data
        if not self._container_cache:
            self.fetch_repository_data()
        
        # Look for the image in all registries
        for registry_name, images in self._container_cache.items():
            # Try exact match first
            if package_name in images:
                img_data = images[package_name]
                return self._create_package_info(package_name, img_data, registry_name)
            
            # Try case-insensitive match
            for img_name, img_data in images.items():
                if img_name.lower() == package_name.lower():
                    return self._create_package_info(img_name, img_data, registry_name)
        
        # If not found in cache, try to fetch directly
        for registry in self.registries:
            try:
                self.base_url = registry.url
                image_data = self._fetch_image_details(package_name, registry.name)
                if image_data:
                    return self._create_package_info(package_name, image_data, registry.name)
            except Exception as e:
                logger.warning(f"Failed to fetch image details for {package_name} from {registry.name}: {e}")
        
        return None
    
    def search_packages(self, query: str, max_results: int = 10) -> List[PackageInfo]:
        """
        Search for container images matching the query.
        
        Args:
            query: Search query.
            max_results: Maximum number of results to return.
            
        Returns:
            List of PackageInfo objects matching the query.
        """
        results = []
        
        # Search in all registries
        for registry in self.registries:
            try:
                self.base_url = registry.url
                search_results = self._search_images_in_registry(query, registry.name, max_results - len(results))
                
                for img_name, img_data in search_results.items():
                    # Create PackageInfo object
                    pkg_info = self._create_package_info(img_name, img_data, registry.name)
                    
                    # Add to results if not already present
                    if not any(r.name == img_name for r in results):
                        results.append(pkg_info)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        return results
            
            except Exception as e:
                logger.warning(f"Failed to search images in {registry.name}: {e}")
        
        return results
    
    def _create_package_info(self, image_name: str, image_data: Dict[str, any], registry_name: str) -> PackageInfo:
        """
        Create a PackageInfo object from image data.
        
        Args:
            image_name: Name of the image.
            image_data: Image data.
            registry_name: Name of the registry.
            
        Returns:
            PackageInfo object.
        """
        # Add registry information to details
        details = image_data.copy()
        details["registry"] = registry_name
        
        # Extract the tag (version)
        version = "latest"
        if "tag" in image_data:
            version = image_data["tag"]
        elif "tags" in image_data and image_data["tags"]:
            version = image_data["tags"][0]
        
        return PackageInfo(
            name=image_name,
            provider=self.get_repository_name(),
            version=version,
            description=image_data.get("description", ""),
            details=details
        )
    
    def _fetch_popular_images(self, registry_name: str) -> Dict[str, Dict[str, any]]:
        """
        Fetch popular images from a registry.
        
        Args:
            registry_name: Name of the registry.
            
        Returns:
            Dictionary mapping image names to their metadata.
        """
        if registry_name == "docker-hub":
            try:
                # Fetch popular images from Docker Hub
                response = self._fetch_json("repositories/explore/")
                
                images = {}
                for result in response.get("results", []):
                    repo_name = result.get("name")
                    if repo_name:
                        # For Docker Hub, the full name includes the namespace
                        namespace = result.get("namespace", "library")
                        full_name = f"{namespace}/{repo_name}" if namespace != "library" else repo_name
                        
                        images[full_name] = {
                            "name": repo_name,
                            "namespace": namespace,
                            "description": result.get("description", ""),
                            "star_count": result.get("star_count", 0),
                            "pull_count": result.get("pull_count", 0),
                            "is_official": result.get("is_official", False),
                            "is_automated": result.get("is_automated", False),
                            "tags": result.get("tags", []),
                            "registry": registry_name
                        }
                
                return images
            
            except Exception as e:
                logger.warning(f"Failed to fetch popular images from Docker Hub: {e}")
                return {}
        else:
            logger.warning(f"Fetching popular images from {registry_name} is not supported")
            return {}
    
    def _fetch_image_details(self, image_name: str, registry_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch detailed information about a container image.
        
        Args:
            image_name: Name of the image.
            registry_name: Name of the registry.
            
        Returns:
            Image metadata if found, None otherwise.
        """
        if registry_name == "docker-hub":
            try:
                # Split namespace and repository name
                if "/" in image_name:
                    namespace, repo_name = image_name.split("/", 1)
                else:
                    namespace, repo_name = "library", image_name
                
                # Fetch repository details
                response = self._fetch_json(f"repositories/{namespace}/{repo_name}")
                
                if "name" in response:
                    # Fetch tags
                    tags_response = self._fetch_json(f"repositories/{namespace}/{repo_name}/tags")
                    tags = [tag.get("name") for tag in tags_response.get("results", [])]
                    
                    return {
                        "name": response.get("name"),
                        "namespace": response.get("namespace", namespace),
                        "description": response.get("description", ""),
                        "star_count": response.get("star_count", 0),
                        "pull_count": response.get("pull_count", 0),
                        "is_official": response.get("is_official", False),
                        "is_automated": response.get("is_automated", False),
                        "tags": tags,
                        "registry": registry_name
                    }
            
            except Exception as e:
                logger.warning(f"Failed to fetch image details for {image_name} from Docker Hub: {e}")
                return None
        else:
            logger.warning(f"Fetching image details from {registry_name} is not supported")
            return None
    
    def _search_images_in_registry(self, query: str, registry_name: str, max_results: int = 10) -> Dict[str, Dict[str, any]]:
        """
        Search for images in a registry.
        
        Args:
            query: Search query.
            registry_name: Name of the registry.
            max_results: Maximum number of results to return.
            
        Returns:
            Dictionary mapping image names to their metadata.
        """
        if registry_name == "docker-hub":
            try:
                # Search for images on Docker Hub
                response = self._fetch_json(f"search/repositories/?query={query}&page_size={max_results}")
                
                images = {}
                for result in response.get("results", []):
                    repo_name = result.get("repo_name")
                    if repo_name:
                        images[repo_name] = {
                            "name": result.get("name", repo_name.split("/")[-1]),
                            "namespace": result.get("namespace", repo_name.split("/")[0] if "/" in repo_name else "library"),
                            "description": result.get("description", ""),
                            "star_count": result.get("star_count", 0),
                            "pull_count": result.get("pull_count", 0),
                            "is_official": result.get("is_official", False),
                            "is_automated": result.get("is_automated", False),
                            "registry": registry_name
                        }
                
                return images
            
            except Exception as e:
                logger.warning(f"Failed to search images in Docker Hub: {e}")
                return {}
        else:
            logger.warning(f"Searching images in {registry_name} is not supported")
            return {}