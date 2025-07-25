"""
Base classes and interfaces for repository fetchers.

This module provides the abstract base classes and interfaces for implementing
repository fetchers for different package managers.
"""

import abc
import hashlib
import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Try to import requests, but don't fail if it's not available
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    # Create dummy classes for type checking
    class HTTPAdapter:
        pass
    class Retry:
        pass
    class requests:
        class Session:
            def __init__(self):
                pass
        class Response:
            def __init__(self):
                self.content = b""
                self.text = ""
                self.status_code = 200
            def json(self):
                return {}
            def raise_for_status(self):
                pass
        class exceptions:
            class RequestException(Exception):
                pass

# Try to import tenacity, but don't fail if it's not available
try:
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    # Create dummy functions for type checking
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def retry_if_exception_type(*args, **kwargs):
        return None
    def stop_after_attempt(*args, **kwargs):
        return None
    def wait_exponential(*args, **kwargs):
        return None

from saidata_gen.core.interfaces import (
    FetchResult, FetcherConfig, PackageInfo, RepositoryData
)


logger = logging.getLogger(__name__)


class RepositoryFetcher(abc.ABC):
    """
    Abstract base class for repository fetchers.
    
    This class defines the interface for fetching package metadata from
    different package repositories.
    """
    
    def __init__(self, config: Optional[FetcherConfig] = None):
        """
        Initialize the repository fetcher.
        
        Args:
            config: Configuration for the fetcher. If None, uses default configuration.
        """
        self.config = config or FetcherConfig()
        self.cache_dir = os.path.expanduser(self.config.cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Create a session with retry logic
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """
        Create a requests session with retry logic.
        
        Returns:
            A configured requests session.
        """
        session = requests.Session()
        
        # Configure retry strategy - don't retry on SSL errors
        retry_strategy = Retry(
            total=self.config.retry_count,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            # Don't retry on SSL errors
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set reasonable timeout
        session.timeout = 30
        
        return session
    
    @abc.abstractmethod
    def fetch_repository_data(self) -> FetchResult:
        """
        Fetch repository data from the package repository.
        
        Returns:
            FetchResult with the result of the fetch operation.
        """
        pass
    
    @abc.abstractmethod
    def get_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """
        Get information about a specific package.
        
        Args:
            package_name: Name of the package to get information for.
            
        Returns:
            PackageInfo if the package is found, None otherwise.
        """
        pass
    
    @abc.abstractmethod
    def search_packages(self, query: str, max_results: int = 10) -> List[PackageInfo]:
        """
        Search for packages matching the query.
        
        Args:
            query: Search query.
            max_results: Maximum number of results to return.
            
        Returns:
            List of PackageInfo objects matching the query.
        """
        pass
    
    @abc.abstractmethod
    def get_repository_name(self) -> str:
        """
        Get the name of the repository.
        
        Returns:
            Name of the repository.
        """
        pass
    
    def _get_cache_path(self, key: str) -> str:
        """
        Get the cache path for a given key.
        
        Args:
            key: Cache key.
            
        Returns:
            Path to the cache file.
        """
        # Create a hash of the key to use as the filename
        key_hash = hashlib.md5(key.encode()).hexdigest()
        repo_name = self.get_repository_name()
        cache_dir = os.path.join(self.cache_dir, repo_name)
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, f"{key_hash}.json")
    
    def _is_cache_valid(self, cache_path: str) -> bool:
        """
        Check if the cache is valid.
        
        Args:
            cache_path: Path to the cache file.
            
        Returns:
            True if the cache is valid, False otherwise.
        """
        if not os.path.exists(cache_path):
            return False
        
        # Check if the cache has expired
        cache_time = os.path.getmtime(cache_path)
        current_time = time.time()
        return (current_time - cache_time) < self.config.cache_ttl
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get data from the cache.
        
        Args:
            key: Cache key.
            
        Returns:
            Cached data if available and valid, None otherwise.
        """
        cache_path = self._get_cache_path(key)
        
        if not self._is_cache_valid(cache_path):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read cache for {key}: {e}")
            return None
    
    def _save_to_cache(self, key: str, data: Dict[str, Any]) -> None:
        """
        Save data to the cache.
        
        Args:
            key: Cache key.
            data: Data to cache.
        """
        cache_path = self._get_cache_path(key)
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write cache for {key}: {e}")
    
    @retry(
        retry=retry_if_exception_type((requests.exceptions.RequestException, IOError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _fetch_url(self, url: str, headers: Optional[Dict[str, str]] = None) -> requests.Response:
        """
        Fetch data from a URL with retry logic.
        
        Args:
            url: URL to fetch.
            headers: Optional headers to include in the request.
            
        Returns:
            Response object.
            
        Raises:
            requests.exceptions.RequestException: If the request fails after retries.
        """
        headers = headers or {}
        response = self.session.get(
            url,
            headers=headers,
            timeout=self.config.request_timeout
        )
        response.raise_for_status()
        return response


class HttpRepositoryFetcher(RepositoryFetcher):
    """
    Base class for repository fetchers that use HTTP.
    
    This class provides common functionality for fetchers that retrieve
    data from HTTP endpoints.
    """
    
    def __init__(
        self,
        base_url: str,
        config: Optional[FetcherConfig] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the HTTP repository fetcher.
        
        Args:
            base_url: Base URL for the repository.
            config: Configuration for the fetcher.
            headers: Optional headers to include in all requests.
        """
        super().__init__(config)
        self.base_url = base_url.rstrip('/')
        self.headers = headers or {}
    
    def _get_url(self, path: str) -> str:
        """
        Get the full URL for a path.
        
        Args:
            path: Path to append to the base URL.
            
        Returns:
            Full URL.
        """
        path = path.lstrip('/')
        return f"{self.base_url}/{path}"
    
    def _fetch_json(self, path: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Fetch JSON data from a URL.
        
        Args:
            path: Path to append to the base URL.
            use_cache: Whether to use the cache.
            
        Returns:
            Parsed JSON data.
            
        Raises:
            requests.exceptions.RequestException: If the request fails.
            ValueError: If the response is not valid JSON.
        """
        url = self._get_url(path)
        cache_key = f"json:{url}"
        
        if use_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                return cached_data
        
        response = self._fetch_url(url, headers=self.headers)
        data = response.json()
        
        if use_cache:
            self._save_to_cache(cache_key, data)
        
        return data
    
    def _fetch_text(self, path: str, use_cache: bool = True) -> str:
        """
        Fetch text data from a URL.
        
        Args:
            path: Path to append to the base URL.
            use_cache: Whether to use the cache.
            
        Returns:
            Text data.
            
        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        url = self._get_url(path)
        cache_key = f"text:{url}"
        
        if use_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None and "text" in cached_data:
                return cached_data["text"]
        
        response = self._fetch_url(url, headers=self.headers)
        text = response.text
        
        if use_cache:
            self._save_to_cache(cache_key, {"text": text})
        
        return text
    
    def _fetch_binary(self, path: str, output_path: str, use_cache: bool = True) -> str:
        """
        Fetch binary data from a URL and save it to a file.
        
        Args:
            path: Path to append to the base URL.
            output_path: Path to save the binary data to.
            use_cache: Whether to use the cache.
            
        Returns:
            Path to the saved file.
            
        Raises:
            requests.exceptions.RequestException: If the request fails.
            IOError: If the file cannot be written.
        """
        url = self._get_url(path)
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # If the file already exists and cache is enabled, return the path
        if use_cache and os.path.exists(output_path):
            if self._is_cache_valid(output_path):
                return output_path
        
        # Fetch the data
        response = self._fetch_url(url, headers=self.headers)
        
        # Save the data to the file
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        return output_path


class GitRepositoryFetcher(RepositoryFetcher):
    """
    Base class for repository fetchers that use Git.
    
    This class provides common functionality for fetchers that retrieve
    data from Git repositories.
    """
    
    def __init__(
        self,
        repository_url: str,
        branch: str = "main",
        config: Optional[FetcherConfig] = None
    ):
        """
        Initialize the Git repository fetcher.
        
        Args:
            repository_url: URL of the Git repository.
            branch: Branch to clone.
            config: Configuration for the fetcher.
        """
        super().__init__(config)
        self.repository_url = repository_url
        self.branch = branch
        self.repo_dir = os.path.join(
            self.cache_dir,
            self.get_repository_name(),
            hashlib.md5(repository_url.encode()).hexdigest()
        )
    
    def _clone_or_pull_repository(self) -> bool:
        """
        Clone the repository if it doesn't exist, or pull if it does.
        
        Returns:
            True if successful, False otherwise.
        """
        import subprocess
        
        try:
            if not os.path.exists(self.repo_dir):
                # Clone the repository
                os.makedirs(os.path.dirname(self.repo_dir), exist_ok=True)
                subprocess.run(
                    ["git", "clone", "--depth", "1", "-b", self.branch, self.repository_url, self.repo_dir],
                    check=True,
                    capture_output=True
                )
                return True
            else:
                # Pull the latest changes
                subprocess.run(
                    ["git", "-C", self.repo_dir, "pull", "origin", self.branch],
                    check=True,
                    capture_output=True
                )
                return True
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to clone or pull repository: {e}")
            return False
    
    def _get_file_content(self, file_path: str) -> Optional[str]:
        """
        Get the content of a file from the repository.
        
        Args:
            file_path: Path to the file relative to the repository root.
            
        Returns:
            Content of the file if it exists, None otherwise.
        """
        full_path = os.path.join(self.repo_dir, file_path)
        
        if not os.path.exists(full_path):
            return None
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            return None
    
    def _list_files(self, directory: str = "", pattern: str = "*") -> List[str]:
        """
        List files in a directory in the repository.
        
        Args:
            directory: Directory to list files in, relative to the repository root.
            pattern: Glob pattern to match files against.
            
        Returns:
            List of file paths relative to the repository root.
        """
        import glob
        
        full_dir = os.path.join(self.repo_dir, directory)
        
        if not os.path.exists(full_dir):
            return []
        
        # Get all files matching the pattern
        files = glob.glob(os.path.join(full_dir, pattern), recursive=True)
        
        # Convert to paths relative to the repository root
        return [os.path.relpath(f, self.repo_dir) for f in files]