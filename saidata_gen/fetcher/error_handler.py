"""
Centralized error handling for repository fetchers.

This module provides the FetcherErrorHandler class for handling various types
of errors that can occur during repository fetching operations.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from xml.etree import ElementTree as ET

# Try to import requests, but don't fail if it's not available
try:
    import requests
    import ssl
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    # Create dummy classes for type checking
    class requests:
        class Response:
            def __init__(self):
                self.content = b""
                self.text = ""
                self.status_code = 200
            def json(self):
                return {}
        class exceptions:
            class RequestException(Exception):
                pass
            class SSLError(Exception):
                pass
            class ConnectionError(Exception):
                pass
            class Timeout(Exception):
                pass
            class HTTPError(Exception):
                pass
    class ssl:
        class SSLError(Exception):
            pass

# Try to import yaml, but don't fail if it's not available
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from saidata_gen.core.exceptions import FetchError
from saidata_gen.core.interfaces import FetchResult


logger = logging.getLogger(__name__)


@dataclass
class ErrorContext:
    """Context information for error handling."""
    provider: str
    url: str
    attempt: int = 1
    max_attempts: int = 3
    timestamp: datetime = field(default_factory=datetime.now)
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetryResult:
    """Result of retry decision."""
    should_retry: bool
    wait_time: float = 0.0
    reason: str = ""


class FetcherErrorHandler:
    """
    Centralized error handler for repository fetchers.
    
    This class provides methods to handle various types of errors that can occur
    during repository fetching operations, including network errors, SSL errors,
    and malformed data errors.
    """
    
    def __init__(self, max_retries: int = 3, base_wait_time: float = 1.0):
        """
        Initialize the error handler.
        
        Args:
            max_retries: Maximum number of retry attempts.
            base_wait_time: Base wait time for exponential backoff.
        """
        self.max_retries = max_retries
        self.base_wait_time = base_wait_time
        self._ssl_failed_urls = set()
        self._network_failed_urls = set()
        self._malformed_data_urls = set()
        
        # Track error statistics
        self._error_stats = {
            'network_errors': 0,
            'ssl_errors': 0,
            'malformed_data_errors': 0,
            'total_retries': 0
        }
    
    def handle_network_error(self, error: Exception, context: ErrorContext) -> FetchResult:
        """
        Handle network-related errors (HTTP errors, connection errors, timeouts).
        
        Args:
            error: The network error that occurred.
            context: Context information about the error.
            
        Returns:
            FetchResult indicating the outcome of error handling.
        """
        self._error_stats['network_errors'] += 1
        self._network_failed_urls.add(context.url)
        
        error_type = type(error).__name__
        error_message = str(error)
        
        logger.warning(
            f"Network error for {context.provider} at {context.url} "
            f"(attempt {context.attempt}/{context.max_attempts}): "
            f"{error_type}: {error_message}"
        )
        
        # Determine if this is a retryable error
        retry_result = self.should_retry(error, context.attempt)
        
        if retry_result.should_retry and context.attempt < context.max_attempts:
            logger.info(
                f"Will retry {context.provider} request in {retry_result.wait_time:.1f}s: "
                f"{retry_result.reason}"
            )
            self._error_stats['total_retries'] += 1
            
            # Sleep before retry
            if retry_result.wait_time > 0:
                time.sleep(retry_result.wait_time)
            
            return FetchResult(
                success=False,
                providers={context.provider: False},
                errors={context.provider: f"Network error (will retry): {error_message}"},
                cache_hits={context.provider: False}
            )
        else:
            logger.error(
                f"Network error for {context.provider} - max retries exceeded or non-retryable: "
                f"{error_type}: {error_message}"
            )
            
            return FetchResult(
                success=False,
                providers={context.provider: False},
                errors={context.provider: f"Network error (final): {error_message}"},
                cache_hits={context.provider: False}
            )
    
    def handle_ssl_error(self, error: Union[requests.exceptions.SSLError, ssl.SSLError], 
                        context: ErrorContext) -> Optional[requests.Response]:
        """
        Handle SSL certificate validation errors with fallback mechanisms.
        
        Args:
            error: The SSL error that occurred.
            context: Context information about the error.
            
        Returns:
            Response object if fallback succeeds, None otherwise.
        """
        self._error_stats['ssl_errors'] += 1
        self._ssl_failed_urls.add(context.url)
        
        error_message = str(error)
        
        logger.warning(
            f"SSL error for {context.provider} at {context.url}: {error_message}"
        )
        
        # Try SSL fallback strategies
        fallback_strategies = [
            self._try_ssl_verification_disabled,
            self._try_alternative_ssl_context,
            self._try_http_fallback
        ]
        
        for strategy in fallback_strategies:
            try:
                strategy_name = getattr(strategy, '__name__', str(strategy))
                logger.info(f"Trying SSL fallback strategy: {strategy_name}")
                response = strategy(context)
                if response is not None:
                    logger.info(f"SSL fallback successful for {context.provider}")
                    return response
            except Exception as fallback_error:
                strategy_name = getattr(strategy, '__name__', str(strategy))
                logger.debug(f"SSL fallback strategy {strategy_name} failed: {fallback_error}")
                continue
        
        logger.error(f"All SSL fallback strategies failed for {context.provider}")
        return None
    
    def handle_malformed_data(self, data: bytes, format_type: str, 
                            context: ErrorContext) -> Optional[Dict[str, Any]]:
        """
        Handle malformed or corrupted data with parsing fallbacks.
        
        Args:
            data: The raw data that failed to parse.
            format_type: Expected format type ('json', 'xml', 'yaml').
            context: Context information about the error.
            
        Returns:
            Parsed data if fallback succeeds, None otherwise.
        """
        self._error_stats['malformed_data_errors'] += 1
        self._malformed_data_urls.add(context.url)
        
        logger.warning(
            f"Malformed {format_type} data for {context.provider} at {context.url}"
        )
        
        # Try different parsing strategies based on format type
        if format_type.lower() == 'json':
            return self._handle_malformed_json(data, context)
        elif format_type.lower() == 'xml':
            return self._handle_malformed_xml(data, context)
        elif format_type.lower() == 'yaml':
            return self._handle_malformed_yaml(data, context)
        else:
            logger.error(f"Unsupported format type for malformed data handling: {format_type}")
            return None
    
    def should_retry(self, error: Exception, attempt: int) -> RetryResult:
        """
        Determine if an error should be retried with intelligent retry logic.
        
        Args:
            error: The error that occurred.
            attempt: Current attempt number.
            
        Returns:
            RetryResult indicating whether to retry and wait time.
        """
        if attempt >= self.max_retries:
            return RetryResult(
                should_retry=False,
                reason="Maximum retry attempts reached"
            )
        
        error_type = type(error).__name__
        
        # Network errors that are typically retryable
        retryable_network_errors = [
            'ConnectionError',
            'Timeout',
            'HTTPError'
        ]
        
        # HTTP status codes that are retryable
        retryable_status_codes = [429, 500, 502, 503, 504]
        
        # Check if it's an HTTP error with retryable status code first
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            status_code = error.response.status_code
            if status_code in retryable_status_codes:
                wait_time = self._calculate_backoff_time(attempt)
                return RetryResult(
                    should_retry=True,
                    wait_time=wait_time,
                    reason=f"Retryable HTTP status: {status_code}"
                )
            else:
                return RetryResult(
                    should_retry=False,
                    reason=f"Non-retryable HTTP status: {status_code}"
                )
        
        # Check if it's a retryable network error
        if error_type in retryable_network_errors:
            wait_time = self._calculate_backoff_time(attempt)
            return RetryResult(
                should_retry=True,
                wait_time=wait_time,
                reason=f"Retryable network error: {error_type}"
            )
        
        # SSL errors are generally not retryable through normal retry logic
        # (they should be handled through SSL fallback mechanisms)
        if 'SSL' in error_type:
            return RetryResult(
                should_retry=False,
                reason="SSL errors require fallback handling, not retry"
            )
        
        # Default: don't retry unknown errors
        return RetryResult(
            should_retry=False,
            reason=f"Non-retryable error type: {error_type}"
        )
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error handling statistics.
        
        Returns:
            Dictionary containing error statistics.
        """
        return {
            'error_counts': self._error_stats.copy(),
            'failed_urls': {
                'ssl_failed': list(self._ssl_failed_urls),
                'network_failed': list(self._network_failed_urls),
                'malformed_data': list(self._malformed_data_urls)
            },
            'total_failed_urls': len(self._ssl_failed_urls | self._network_failed_urls | self._malformed_data_urls)
        }
    
    def reset_statistics(self) -> None:
        """Reset error handling statistics."""
        self._error_stats = {
            'network_errors': 0,
            'ssl_errors': 0,
            'malformed_data_errors': 0,
            'total_retries': 0
        }
        self._ssl_failed_urls.clear()
        self._network_failed_urls.clear()
        self._malformed_data_urls.clear()
    
    def _calculate_backoff_time(self, attempt: int) -> float:
        """
        Calculate exponential backoff time with jitter.
        
        Args:
            attempt: Current attempt number.
            
        Returns:
            Wait time in seconds.
        """
        import random
        
        # Exponential backoff: base_wait_time * (2 ^ (attempt - 1))
        backoff_time = self.base_wait_time * (2 ** (attempt - 1))
        
        # Add jitter to avoid thundering herd
        jitter = random.uniform(0.1, 0.5)
        
        return backoff_time + jitter
    
    def _try_ssl_verification_disabled(self, context: ErrorContext) -> Optional[requests.Response]:
        """
        Try to fetch with SSL verification disabled.
        
        Args:
            context: Error context.
            
        Returns:
            Response if successful, None otherwise.
        """
        if not REQUESTS_AVAILABLE:
            return None
        
        logger.warning(f"Attempting SSL verification bypass for {context.url}")
        
        try:
            # Disable SSL warnings
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except ImportError:
            pass
        
        try:
            response = requests.get(context.url, verify=False, timeout=30)
            response.raise_for_status()
            return response
        except Exception as e:
            logger.debug(f"SSL verification bypass failed: {e}")
            return None
    
    def _try_alternative_ssl_context(self, context: ErrorContext) -> Optional[requests.Response]:
        """
        Try to fetch with alternative SSL context.
        
        Args:
            context: Error context.
            
        Returns:
            Response if successful, None otherwise.
        """
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            import ssl
            import requests.adapters
            
            # Create a custom SSL context with more lenient settings
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Create a custom adapter with the SSL context
            class SSLAdapter(requests.adapters.HTTPAdapter):
                def init_poolmanager(self, *args, **kwargs):
                    kwargs['ssl_context'] = ssl_context
                    return super().init_poolmanager(*args, **kwargs)
            
            session = requests.Session()
            session.mount('https://', SSLAdapter())
            
            response = session.get(context.url, timeout=30)
            response.raise_for_status()
            return response
            
        except Exception as e:
            logger.debug(f"Alternative SSL context failed: {e}")
            return None
    
    def _try_http_fallback(self, context: ErrorContext) -> Optional[requests.Response]:
        """
        Try to fetch using HTTP instead of HTTPS.
        
        Args:
            context: Error context.
            
        Returns:
            Response if successful, None otherwise.
        """
        if not REQUESTS_AVAILABLE:
            return None
        
        if not context.url.startswith('https://'):
            return None
        
        http_url = context.url.replace('https://', 'http://', 1)
        logger.warning(f"Attempting HTTP fallback: {http_url}")
        
        try:
            response = requests.get(http_url, timeout=30)
            response.raise_for_status()
            return response
        except Exception as e:
            logger.debug(f"HTTP fallback failed: {e}")
            return None
    
    def _handle_malformed_json(self, data: bytes, context: ErrorContext) -> Optional[Dict[str, Any]]:
        """
        Handle malformed JSON data with various parsing strategies.
        
        Args:
            data: Raw data bytes.
            context: Error context.
            
        Returns:
            Parsed data if successful, None otherwise.
        """
        # Try different encoding strategies
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                text = data.decode(encoding)
                
                # Try to parse as-is
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
                
                # Try to fix common JSON issues
                fixed_text = self._fix_common_json_issues(text)
                if fixed_text != text:
                    try:
                        return json.loads(fixed_text)
                    except json.JSONDecodeError:
                        pass
                
            except UnicodeDecodeError:
                continue
        
        logger.error(f"Failed to parse JSON data from {context.url} with all strategies")
        return None
    
    def _handle_malformed_xml(self, data: bytes, context: ErrorContext) -> Optional[Dict[str, Any]]:
        """
        Handle malformed XML data with various parsing strategies.
        
        Args:
            data: Raw data bytes.
            context: Error context.
            
        Returns:
            Parsed data if successful, None otherwise.
        """
        # Try different encoding strategies
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                text = data.decode(encoding)
                
                # Try to parse as-is
                try:
                    root = ET.fromstring(text)
                    return self._xml_to_dict(root)
                except ET.ParseError:
                    pass
                
                # Try to fix common XML issues
                fixed_text = self._fix_common_xml_issues(text)
                if fixed_text != text:
                    try:
                        root = ET.fromstring(fixed_text)
                        return self._xml_to_dict(root)
                    except ET.ParseError:
                        pass
                
            except UnicodeDecodeError:
                continue
        
        logger.error(f"Failed to parse XML data from {context.url} with all strategies")
        return None
    
    def _handle_malformed_yaml(self, data: bytes, context: ErrorContext) -> Optional[Dict[str, Any]]:
        """
        Handle malformed YAML data with various parsing strategies.
        
        Args:
            data: Raw data bytes.
            context: Error context.
            
        Returns:
            Parsed data if successful, None otherwise.
        """
        if not YAML_AVAILABLE:
            logger.warning("YAML library not available for malformed data handling")
            return None
        
        # Try different encoding strategies
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                text = data.decode(encoding)
                
                # Try to parse as-is
                try:
                    return yaml.safe_load(text)
                except yaml.YAMLError:
                    pass
                
                # Try to fix common YAML issues
                fixed_text = self._fix_common_yaml_issues(text)
                if fixed_text != text:
                    try:
                        return yaml.safe_load(fixed_text)
                    except yaml.YAMLError:
                        pass
                
            except UnicodeDecodeError:
                continue
        
        logger.error(f"Failed to parse YAML data from {context.url} with all strategies")
        return None
    
    def _fix_common_json_issues(self, text: str) -> str:
        """
        Fix common JSON formatting issues.
        
        Args:
            text: JSON text to fix.
            
        Returns:
            Fixed JSON text.
        """
        # Remove BOM if present
        if text.startswith('\ufeff'):
            text = text[1:]
        
        # Remove trailing commas before closing brackets/braces
        import re
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        
        # Fix single quotes to double quotes (basic case)
        text = re.sub(r"'([^']*)':", r'"\1":', text)
        
        return text
    
    def _fix_common_xml_issues(self, text: str) -> str:
        """
        Fix common XML formatting issues.
        
        Args:
            text: XML text to fix.
            
        Returns:
            Fixed XML text.
        """
        # Remove BOM if present
        if text.startswith('\ufeff'):
            text = text[1:]
        
        # Fix unclosed tags (basic case)
        import re
        
        # This is a very basic fix - in practice, XML repair is complex
        # For now, just remove any obvious control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        return text
    
    def _fix_common_yaml_issues(self, text: str) -> str:
        """
        Fix common YAML formatting issues.
        
        Args:
            text: YAML text to fix.
            
        Returns:
            Fixed YAML text.
        """
        # Remove BOM if present
        if text.startswith('\ufeff'):
            text = text[1:]
        
        # Fix tab characters (YAML doesn't allow tabs for indentation)
        text = text.replace('\t', '  ')
        
        return text
    
    def _xml_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """
        Convert XML element to dictionary.
        
        Args:
            element: XML element to convert.
            
        Returns:
            Dictionary representation of the XML element.
        """
        result = {}
        
        # Add attributes
        if element.attrib:
            result['@attributes'] = element.attrib
        
        # Add text content
        if element.text and element.text.strip():
            if len(element) == 0 and not element.attrib:  # No child elements and no attributes
                return element.text.strip()
            else:
                result['#text'] = element.text.strip()
        
        # Add child elements
        for child in element:
            child_data = self._xml_to_dict(child)
            if child.tag in result:
                # Convert to list if multiple elements with same tag
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        return result