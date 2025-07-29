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
    import ssl
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
            class SSLError(Exception):
                pass
            class ConnectionError(Exception):
                pass
            class Timeout(Exception):
                pass
    class ssl:
        class SSLError(Exception):
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
        
        # Track SSL issues for fallback handling
        self._ssl_failed_urls = set()
        self._fallback_urls = {}
    
    def register_fallback_urls(self, primary_url: str, fallback_urls: List[str]) -> None:
        """
        Register fallback URLs for a primary URL.
        
        Args:
            primary_url: The primary URL.
            fallback_urls: List of fallback URLs to try if the primary fails.
        """
        self._fallback_urls[primary_url] = fallback_urls
        logger.debug(f"Registered {len(fallback_urls)} fallback URLs for {primary_url}")
    
    def get_fallback_urls(self, primary_url: str) -> List[str]:
        """
        Get fallback URLs for a primary URL.
        
        Args:
            primary_url: The primary URL.
            
        Returns:
            List of fallback URLs, or empty list if none registered.
        """
        return self._fallback_urls.get(primary_url, [])
    
    def _create_session(self) -> requests.Session:
        """
        Create a requests session with enhanced retry logic and SSL handling.
        
        Returns:
            A configured requests session.
        """
        session = requests.Session()
        
        # Configure retry strategy - don't retry on SSL errors initially
        retry_strategy = Retry(
            total=self.config.retry_count,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            # Don't retry on SSL errors in the adapter - we'll handle them manually
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set reasonable timeout
        session.timeout = 30
        
        return session
    
    def _create_session_with_ssl_fallback(self, verify_ssl: bool = True) -> requests.Session:
        """
        Create a requests session with SSL fallback handling.
        
        Args:
            verify_ssl: Whether to verify SSL certificates.
            
        Returns:
            A configured requests session.
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.retry_count,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Configure SSL verification
        session.verify = verify_ssl
        if not verify_ssl:
            # Disable SSL warnings when verification is disabled
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except ImportError:
                pass
        
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
    
    def _fetch_url(self, url: str, headers: Optional[Dict[str, str]] = None, 
                   fallback_urls: Optional[List[str]] = None) -> requests.Response:
        """
        Fetch data from a URL with enhanced retry logic and SSL fallback handling.
        
        Args:
            url: URL to fetch.
            headers: Optional headers to include in the request.
            fallback_urls: Optional list of fallback URLs to try if the primary URL fails.
            
        Returns:
            Response object.
            
        Raises:
            requests.exceptions.RequestException: If the request fails after retries.
        """
        headers = headers or {}
        fallback_urls = fallback_urls or []
        
        # Try the primary URL first
        urls_to_try = [url] + fallback_urls
        
        for attempt, current_url in enumerate(urls_to_try):
            try:
                return self._fetch_url_with_retries(current_url, headers, attempt + 1)
            except (requests.exceptions.SSLError, ssl.SSLError) as e:
                logger.warning(f"SSL error for {current_url}: {e}")
                self._ssl_failed_urls.add(current_url)
                
                # Try with SSL verification disabled as fallback
                try:
                    return self._fetch_url_with_ssl_fallback(current_url, headers)
                except Exception as ssl_fallback_error:
                    logger.warning(f"SSL fallback also failed for {current_url}: {ssl_fallback_error}")
                    if attempt == len(urls_to_try) - 1:  # Last URL
                        raise e
                    continue
                    
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                logger.warning(f"Network error for {current_url}: {e}")
                if attempt == len(urls_to_try) - 1:  # Last URL
                    raise e
                continue
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error for {current_url}: {e}")
                if attempt == len(urls_to_try) - 1:  # Last URL
                    raise e
                continue
        
        # This should not be reached, but just in case
        raise requests.exceptions.RequestException(f"All URLs failed: {urls_to_try}")
    
    @retry(
        retry=retry_if_exception_type((
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError
        )),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _fetch_url_with_retries(self, url: str, headers: Dict[str, str], 
                               attempt: int = 1) -> requests.Response:
        """
        Fetch data from a URL with exponential backoff retry logic.
        
        Args:
            url: URL to fetch.
            headers: Headers to include in the request.
            attempt: Current attempt number (for progressive timeout).
            
        Returns:
            Response object.
            
        Raises:
            requests.exceptions.RequestException: If the request fails after retries.
        """
        # Progressive timeout - increase timeout with each attempt
        timeout = self.config.request_timeout + (attempt - 1) * 10
        
        response = self.session.get(
            url,
            headers=headers,
            timeout=timeout
        )
        response.raise_for_status()
        return response
    
    def _fetch_url_with_ssl_fallback(self, url: str, headers: Dict[str, str]) -> requests.Response:
        """
        Fetch data from a URL with SSL verification disabled as fallback.
        
        Args:
            url: URL to fetch.
            headers: Headers to include in the request.
            
        Returns:
            Response object.
            
        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        logger.warning(f"Attempting SSL fallback for {url} (SSL verification disabled)")
        
        # Create a session with SSL verification disabled
        fallback_session = self._create_session_with_ssl_fallback(verify_ssl=False)
        
        try:
            response = fallback_session.get(
                url,
                headers=headers,
                timeout=self.config.request_timeout
            )
            response.raise_for_status()
            logger.info(f"SSL fallback successful for {url}")
            return response
        finally:
            fallback_session.close()


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
        headers: Optional[Dict[str, str]] = None,
        fallback_base_urls: Optional[List[str]] = None
    ):
        """
        Initialize the HTTP repository fetcher.
        
        Args:
            base_url: Base URL for the repository.
            config: Configuration for the fetcher.
            headers: Optional headers to include in all requests.
            fallback_base_urls: Optional list of fallback base URLs.
        """
        super().__init__(config)
        self.base_url = base_url.rstrip('/')
        self.headers = headers or {}
        self.fallback_base_urls = [url.rstrip('/') for url in (fallback_base_urls or [])]
    
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
    
    def _fetch_json(self, path: str, use_cache: bool = True, 
                    fallback_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Fetch JSON data from a URL with fallback support.
        
        Args:
            path: Path to append to the base URL.
            use_cache: Whether to use the cache.
            fallback_urls: Optional list of fallback URLs to try.
            
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
        
        # Combine provided fallback URLs with base URL fallbacks
        all_fallback_urls = fallback_urls or []
        if self.fallback_base_urls:
            for fallback_base in self.fallback_base_urls:
                fallback_url = f"{fallback_base}/{path.lstrip('/')}"
                all_fallback_urls.append(fallback_url)
        
        response = self._fetch_url(url, headers=self.headers, fallback_urls=all_fallback_urls)
        
        try:
            data = response.json()
        except ValueError as e:
            logger.error(f"Failed to parse JSON from {url}: {e}")
            # Try to provide more context about the response
            logger.debug(f"Response content (first 500 chars): {response.text[:500]}")
            raise
        
        if use_cache:
            self._save_to_cache(cache_key, data)
        
        return data
    
    def _fetch_text(self, path: str, use_cache: bool = True, 
                    fallback_urls: Optional[List[str]] = None) -> str:
        """
        Fetch text data from a URL with fallback support.
        
        Args:
            path: Path to append to the base URL.
            use_cache: Whether to use the cache.
            fallback_urls: Optional list of fallback URLs to try.
            
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
        
        # Combine provided fallback URLs with base URL fallbacks
        all_fallback_urls = fallback_urls or []
        if self.fallback_base_urls:
            for fallback_base in self.fallback_base_urls:
                fallback_url = f"{fallback_base}/{path.lstrip('/')}"
                all_fallback_urls.append(fallback_url)
        
        response = self._fetch_url(url, headers=self.headers, fallback_urls=all_fallback_urls)
        text = response.text
        
        if use_cache:
            self._save_to_cache(cache_key, {"text": text})
        
        return text
    
    def _fetch_binary(self, path: str, output_path: str, use_cache: bool = True, 
                      fallback_urls: Optional[List[str]] = None) -> str:
        """
        Fetch binary data from a URL and save it to a file with fallback support.
        
        Args:
            path: Path to append to the base URL.
            output_path: Path to save the binary data to.
            use_cache: Whether to use the cache.
            fallback_urls: Optional list of fallback URLs to try.
            
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
        
        # Combine provided fallback URLs with base URL fallbacks
        all_fallback_urls = fallback_urls or []
        if self.fallback_base_urls:
            for fallback_base in self.fallback_base_urls:
                fallback_url = f"{fallback_base}/{path.lstrip('/')}"
                all_fallback_urls.append(fallback_url)
        
        # Fetch the data
        response = self._fetch_url(url, headers=self.headers, fallback_urls=all_fallback_urls)
        
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