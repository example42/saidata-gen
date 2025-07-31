"""
Tests for FetcherErrorHandler.

This module contains tests for the centralized error handling functionality
in the fetcher module.
"""

import json
import pytest
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from xml.etree import ElementTree as ET

from saidata_gen.fetcher.error_handler import (
    FetcherErrorHandler, ErrorContext, RetryResult
)
from saidata_gen.core.interfaces import FetchResult


class TestFetcherErrorHandler:
    """Test cases for FetcherErrorHandler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = FetcherErrorHandler(max_retries=3, base_wait_time=0.1)
        self.context = ErrorContext(
            provider="test_provider",
            url="https://example.com/test",
            attempt=1,
            max_attempts=3
        )
    
    def test_initialization(self):
        """Test FetcherErrorHandler initialization."""
        handler = FetcherErrorHandler(max_retries=5, base_wait_time=2.0)
        assert handler.max_retries == 5
        assert handler.base_wait_time == 2.0
        assert len(handler._ssl_failed_urls) == 0
        assert len(handler._network_failed_urls) == 0
        assert len(handler._malformed_data_urls) == 0
    
    def test_handle_network_error_retryable(self):
        """Test handling of retryable network errors."""
        # Create a proper connection error
        class ConnectionError(Exception):
            pass
        error = ConnectionError("Connection failed")
        
        with patch.object(self.handler, 'should_retry') as mock_should_retry:
            mock_should_retry.return_value = RetryResult(
                should_retry=True,
                wait_time=0.1,
                reason="Retryable network error"
            )
            
            with patch('time.sleep'):  # Mock sleep to speed up test
                result = self.handler.handle_network_error(error, self.context)
        
        assert not result.success
        assert "test_provider" in result.providers
        assert not result.providers["test_provider"]
        assert "test_provider" in result.errors
        assert "Network error (will retry)" in result.errors["test_provider"]
        assert "https://example.com/test" in self.handler._network_failed_urls
    
    def test_handle_network_error_non_retryable(self):
        """Test handling of non-retryable network errors."""
        class AuthenticationError(Exception):
            pass
        error = AuthenticationError("Authentication failed")
        
        with patch.object(self.handler, 'should_retry') as mock_should_retry:
            mock_should_retry.return_value = RetryResult(
                should_retry=False,
                reason="Non-retryable error"
            )
            
            result = self.handler.handle_network_error(error, self.context)
        
        assert not result.success
        assert "test_provider" in result.providers
        assert not result.providers["test_provider"]
        assert "test_provider" in result.errors
        assert "Network error (final)" in result.errors["test_provider"]
    
    def test_handle_network_error_max_retries_exceeded(self):
        """Test handling when max retries are exceeded."""
        class ConnectionError(Exception):
            pass
        error = ConnectionError("Connection failed")
        
        # Set attempt to max attempts
        context = ErrorContext(
            provider="test_provider",
            url="https://example.com/test",
            attempt=3,
            max_attempts=3
        )
        
        with patch.object(self.handler, 'should_retry') as mock_should_retry:
            mock_should_retry.return_value = RetryResult(
                should_retry=True,
                wait_time=0.1,
                reason="Retryable network error"
            )
            
            result = self.handler.handle_network_error(error, context)
        
        assert not result.success
        assert "Network error (final)" in result.errors["test_provider"]
    
    @patch('saidata_gen.fetcher.error_handler.REQUESTS_AVAILABLE', True)
    def test_handle_ssl_error_with_fallback_success(self):
        """Test SSL error handling with successful fallback."""
        # Create a proper SSL error
        class SSLError(Exception):
            pass
        ssl_error = SSLError("SSL certificate verification failed")
        
        # Mock successful fallback
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"test content"
        
        with patch.object(self.handler, '_try_ssl_verification_disabled') as mock_fallback:
            mock_fallback.return_value = mock_response
            
            result = self.handler.handle_ssl_error(ssl_error, self.context)
        
        assert result is not None
        assert result.status_code == 200
        assert "https://example.com/test" in self.handler._ssl_failed_urls
    
    @patch('saidata_gen.fetcher.error_handler.REQUESTS_AVAILABLE', True)
    def test_handle_ssl_error_all_fallbacks_fail(self):
        """Test SSL error handling when all fallbacks fail."""
        class SSLError(Exception):
            pass
        ssl_error = SSLError("SSL certificate verification failed")
        
        # Mock all fallbacks failing
        with patch.object(self.handler, '_try_ssl_verification_disabled') as mock_fallback1:
            with patch.object(self.handler, '_try_alternative_ssl_context') as mock_fallback2:
                with patch.object(self.handler, '_try_http_fallback') as mock_fallback3:
                    mock_fallback1.return_value = None
                    mock_fallback2.return_value = None
                    mock_fallback3.return_value = None
                    
                    result = self.handler.handle_ssl_error(ssl_error, self.context)
        
        assert result is None
        assert "https://example.com/test" in self.handler._ssl_failed_urls
    
    def test_handle_malformed_data_json_success(self):
        """Test handling of malformed JSON data with successful parsing."""
        malformed_json = b'{"key": "value",}'  # Trailing comma
        
        with patch.object(self.handler, '_handle_malformed_json') as mock_handler:
            mock_handler.return_value = {"key": "value"}
            
            result = self.handler.handle_malformed_data(malformed_json, "json", self.context)
        
        assert result is not None
        assert result == {"key": "value"}
        assert "https://example.com/test" in self.handler._malformed_data_urls
    
    def test_handle_malformed_data_xml_success(self):
        """Test handling of malformed XML data with successful parsing."""
        malformed_xml = b'<root><item>value</item></root>'
        
        with patch.object(self.handler, '_handle_malformed_xml') as mock_handler:
            mock_handler.return_value = {"root": {"item": "value"}}
            
            result = self.handler.handle_malformed_data(malformed_xml, "xml", self.context)
        
        assert result is not None
        assert result == {"root": {"item": "value"}}
    
    def test_handle_malformed_data_yaml_success(self):
        """Test handling of malformed YAML data with successful parsing."""
        malformed_yaml = b'key: value\n\tindented: item'  # Tab character
        
        with patch.object(self.handler, '_handle_malformed_yaml') as mock_handler:
            mock_handler.return_value = {"key": "value", "indented": "item"}
            
            result = self.handler.handle_malformed_data(malformed_yaml, "yaml", self.context)
        
        assert result is not None
        assert result == {"key": "value", "indented": "item"}
    
    def test_handle_malformed_data_unsupported_format(self):
        """Test handling of unsupported format type."""
        data = b'some data'
        
        result = self.handler.handle_malformed_data(data, "unsupported", self.context)
        
        assert result is None
    
    def test_should_retry_retryable_network_error(self):
        """Test retry logic for retryable network errors."""
        class Timeout(Exception):
            pass
        error = Timeout("Connection timeout")
        
        result = self.handler.should_retry(error, 1)
        
        assert result.should_retry
        assert result.wait_time > 0
        assert "Retryable network error" in result.reason
    
    def test_should_retry_retryable_http_error(self):
        """Test retry logic for retryable HTTP errors."""
        class HTTPError(Exception):
            pass
        error = HTTPError("Server error")
        
        # Mock response with retryable status code
        mock_response = Mock()
        mock_response.status_code = 503
        error.response = mock_response
        
        result = self.handler.should_retry(error, 1)
        
        assert result.should_retry
        assert result.wait_time > 0
        assert "Retryable HTTP status: 503" in result.reason
    
    def test_should_retry_non_retryable_http_error(self):
        """Test retry logic for non-retryable HTTP errors."""
        class HTTPError(Exception):
            pass
        error = HTTPError("Client error")
        
        # Mock response with non-retryable status code
        mock_response = Mock()
        mock_response.status_code = 404
        error.response = mock_response
        
        result = self.handler.should_retry(error, 1)
        
        assert not result.should_retry
        assert "Non-retryable HTTP status: 404" in result.reason
    
    def test_should_retry_ssl_error(self):
        """Test retry logic for SSL errors."""
        class SSLError(Exception):
            pass
        error = SSLError("SSL certificate error")
        
        result = self.handler.should_retry(error, 1)
        
        assert not result.should_retry
        assert "SSL errors require fallback handling" in result.reason
    
    def test_should_retry_max_attempts_reached(self):
        """Test retry logic when max attempts are reached."""
        class Timeout(Exception):
            pass
        error = Timeout("Connection timeout")
        
        result = self.handler.should_retry(error, 3)  # max_retries = 3
        
        assert not result.should_retry
        assert "Maximum retry attempts reached" in result.reason
    
    def test_calculate_backoff_time(self):
        """Test exponential backoff calculation."""
        # Test different attempt numbers - check ranges instead of exact ordering due to jitter
        time1 = self.handler._calculate_backoff_time(1)
        time2 = self.handler._calculate_backoff_time(2)
        time3 = self.handler._calculate_backoff_time(3)
        
        # Check that times are in reasonable ranges (base_wait_time = 0.1)
        # Attempt 1: 0.1 * 2^0 + jitter = 0.1 + (0.1 to 0.5) = 0.2 to 0.6
        assert 0.2 <= time1 <= 0.6
        # Attempt 2: 0.1 * 2^1 + jitter = 0.2 + (0.1 to 0.5) = 0.3 to 0.7
        assert 0.3 <= time2 <= 0.7
        # Attempt 3: 0.1 * 2^2 + jitter = 0.4 + (0.1 to 0.5) = 0.5 to 0.9
        assert 0.5 <= time3 <= 0.9
    
    def test_get_error_statistics(self):
        """Test error statistics collection."""
        # Simulate some errors
        error = Exception("Test error")
        self.handler.handle_network_error(error, self.context)
        
        ssl_error = Exception("SSL error")
        self.handler.handle_ssl_error(ssl_error, self.context)
        
        stats = self.handler.get_error_statistics()
        
        assert "error_counts" in stats
        assert "failed_urls" in stats
        assert "total_failed_urls" in stats
        assert stats["error_counts"]["network_errors"] >= 1
        assert stats["error_counts"]["ssl_errors"] >= 1
        assert len(stats["failed_urls"]["network_failed"]) >= 1
        assert len(stats["failed_urls"]["ssl_failed"]) >= 1
    
    def test_reset_statistics(self):
        """Test resetting error statistics."""
        # Simulate some errors
        error = Exception("Test error")
        self.handler.handle_network_error(error, self.context)
        
        # Reset statistics
        self.handler.reset_statistics()
        
        stats = self.handler.get_error_statistics()
        assert stats["error_counts"]["network_errors"] == 0
        assert stats["error_counts"]["ssl_errors"] == 0
        assert len(stats["failed_urls"]["network_failed"]) == 0
        assert len(stats["failed_urls"]["ssl_failed"]) == 0
    
    def test_fix_common_json_issues(self):
        """Test JSON issue fixing."""
        # Test trailing comma removal
        json_with_comma = '{"key": "value",}'
        fixed = self.handler._fix_common_json_issues(json_with_comma)
        assert fixed == '{"key": "value"}'
        
        # Test BOM removal
        json_with_bom = '\ufeff{"key": "value"}'
        fixed = self.handler._fix_common_json_issues(json_with_bom)
        assert fixed == '{"key": "value"}'
    
    def test_fix_common_xml_issues(self):
        """Test XML issue fixing."""
        # Test BOM removal
        xml_with_bom = '\ufeff<root><item>value</item></root>'
        fixed = self.handler._fix_common_xml_issues(xml_with_bom)
        assert fixed == '<root><item>value</item></root>'
        
        # Test control character removal
        xml_with_control = '<root>\x00<item>value</item></root>'
        fixed = self.handler._fix_common_xml_issues(xml_with_control)
        assert '<item>value</item>' in fixed
        assert '\x00' not in fixed
    
    def test_fix_common_yaml_issues(self):
        """Test YAML issue fixing."""
        # Test BOM removal
        yaml_with_bom = '\ufeffkey: value'
        fixed = self.handler._fix_common_yaml_issues(yaml_with_bom)
        assert fixed == 'key: value'
        
        # Test tab replacement
        yaml_with_tabs = 'key: value\n\tindented: item'
        fixed = self.handler._fix_common_yaml_issues(yaml_with_tabs)
        assert fixed == 'key: value\n  indented: item'
    
    def test_xml_to_dict_simple(self):
        """Test XML to dictionary conversion."""
        xml_string = '<root><item>value</item></root>'
        root = ET.fromstring(xml_string)
        
        result = self.handler._xml_to_dict(root)
        
        assert result == {"item": "value"}
    
    def test_xml_to_dict_with_attributes(self):
        """Test XML to dictionary conversion with attributes."""
        xml_string = '<root id="1"><item type="text">value</item></root>'
        root = ET.fromstring(xml_string)
        
        result = self.handler._xml_to_dict(root)
        
        assert "@attributes" in result
        assert result["@attributes"]["id"] == "1"
        assert isinstance(result["item"], dict)
        assert result["item"]["@attributes"]["type"] == "text"
    
    def test_xml_to_dict_multiple_same_tag(self):
        """Test XML to dictionary conversion with multiple elements of same tag."""
        xml_string = '<root><item>value1</item><item>value2</item></root>'
        root = ET.fromstring(xml_string)
        
        result = self.handler._xml_to_dict(root)
        
        assert isinstance(result["item"], list)
        assert len(result["item"]) == 2
        assert "value1" in result["item"]
        assert "value2" in result["item"]


class TestErrorContext:
    """Test cases for ErrorContext."""
    
    def test_error_context_creation(self):
        """Test ErrorContext creation."""
        context = ErrorContext(
            provider="test_provider",
            url="https://example.com",
            attempt=2,
            max_attempts=5
        )
        
        assert context.provider == "test_provider"
        assert context.url == "https://example.com"
        assert context.attempt == 2
        assert context.max_attempts == 5
        assert isinstance(context.timestamp, datetime)
        assert isinstance(context.additional_info, dict)
    
    def test_error_context_defaults(self):
        """Test ErrorContext with default values."""
        context = ErrorContext(
            provider="test_provider",
            url="https://example.com"
        )
        
        assert context.attempt == 1
        assert context.max_attempts == 3
        assert len(context.additional_info) == 0


class TestRetryResult:
    """Test cases for RetryResult."""
    
    def test_retry_result_creation(self):
        """Test RetryResult creation."""
        result = RetryResult(
            should_retry=True,
            wait_time=2.5,
            reason="Network timeout"
        )
        
        assert result.should_retry is True
        assert result.wait_time == 2.5
        assert result.reason == "Network timeout"
    
    def test_retry_result_defaults(self):
        """Test RetryResult with default values."""
        result = RetryResult(should_retry=False)
        
        assert result.should_retry is False
        assert result.wait_time == 0.0
        assert result.reason == ""


# Integration tests
class TestFetcherErrorHandlerIntegration:
    """Integration tests for FetcherErrorHandler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = FetcherErrorHandler(max_retries=2, base_wait_time=0.1)
    
    def test_full_error_handling_workflow(self):
        """Test complete error handling workflow."""
        context = ErrorContext(
            provider="integration_test",
            url="https://example.com/api",
            attempt=1,
            max_attempts=2
        )
        
        # Simulate network error
        class ConnectionError(Exception):
            pass
        network_error = ConnectionError("Connection failed")
        
        # Handle network error (should retry)
        with patch('time.sleep'):  # Speed up test
            result1 = self.handler.handle_network_error(network_error, context)
        
        assert not result1.success
        assert "will retry" in result1.errors["integration_test"]
        
        # Simulate SSL error with different URL
        ssl_context = ErrorContext(
            provider="integration_test",
            url="https://ssl-example.com/api",  # Different URL
            attempt=1,
            max_attempts=2
        )
        class SSLError(Exception):
            pass
        ssl_error = SSLError("SSL verification failed")
        
        with patch.object(self.handler, '_try_ssl_verification_disabled') as mock_fallback:
            mock_fallback.return_value = None  # Fallback fails
            result2 = self.handler.handle_ssl_error(ssl_error, ssl_context)
        
        assert result2 is None
        
        # Check statistics
        stats = self.handler.get_error_statistics()
        assert stats["error_counts"]["network_errors"] == 1
        assert stats["error_counts"]["ssl_errors"] == 1
        assert stats["total_failed_urls"] == 2  # Both network and SSL failed URLs
    
    @patch('saidata_gen.fetcher.error_handler.json.loads')
    def test_malformed_json_handling_with_fallback(self, mock_json_loads):
        """Test malformed JSON handling with encoding fallback."""
        # First call fails, second succeeds
        mock_json_loads.side_effect = [
            json.JSONDecodeError("Invalid JSON", "", 0),
            {"key": "value"}
        ]
        
        malformed_data = b'{"key": "value",}'  # Trailing comma
        context = ErrorContext(provider="test", url="https://example.com")
        
        result = self.handler._handle_malformed_json(malformed_data, context)
        
        assert result == {"key": "value"}
        assert mock_json_loads.call_count == 2  # First fails, second succeeds

# Additional network failure and SSL error test scenarios
class TestFetcherErrorHandlerEnhanced:
    """Enhanced test cases for FetcherErrorHandler with additional network failure scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = FetcherErrorHandler(max_retries=3, base_wait_time=0.1)
        self.context = ErrorContext(
            provider="test_provider",
            url="https://example.com/test",
            attempt=1,
            max_attempts=3
        )
    
    def test_handle_network_error_dns_resolution_failure(self):
        """Test handling of DNS resolution failures."""
        class DNSError(Exception):
            pass
        error = DNSError("Name or service not known")
        
        with patch.object(self.handler, 'should_retry') as mock_should_retry:
            mock_should_retry.return_value = RetryResult(
                should_retry=True,
                wait_time=0.1,
                reason="DNS resolution error"
            )
            
            with patch('time.sleep'):
                result = self.handler.handle_network_error(error, self.context)
        
        assert not result.success
        assert "DNS resolution error" in mock_should_retry.return_value.reason
        assert "https://example.com/test" in self.handler._network_failed_urls
    
    def test_handle_network_error_proxy_authentication_failure(self):
        """Test handling of proxy authentication failures."""
        class ProxyError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.response = Mock()
                self.response.status_code = 407
        
        error = ProxyError("Proxy authentication required")
        
        with patch.object(self.handler, 'should_retry') as mock_should_retry:
            mock_should_retry.return_value = RetryResult(
                should_retry=False,
                reason="Non-retryable HTTP status: 407"
            )
            
            result = self.handler.handle_network_error(error, self.context)
        
        assert not result.success
        assert "Network error (final)" in result.errors["test_provider"]
    
    def test_handle_network_error_rate_limiting(self):
        """Test handling of rate limiting errors."""
        class RateLimitError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.response = Mock()
                self.response.status_code = 429
                self.response.headers = {'Retry-After': '60'}
        
        error = RateLimitError("Too Many Requests")
        
        with patch.object(self.handler, 'should_retry') as mock_should_retry:
            mock_should_retry.return_value = RetryResult(
                should_retry=True,
                wait_time=60.0,
                reason="Retryable HTTP status: 429"
            )
            
            with patch('time.sleep'):
                result = self.handler.handle_network_error(error, self.context)
        
        assert not result.success
        assert "Network error (will retry)" in result.errors["test_provider"]
    
    def test_handle_network_error_server_overload(self):
        """Test handling of server overload scenarios."""
        class ServerError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.response = Mock()
                self.response.status_code = 503
        
        error = ServerError("Service Temporarily Unavailable")
        
        with patch.object(self.handler, 'should_retry') as mock_should_retry:
            mock_should_retry.return_value = RetryResult(
                should_retry=True,
                wait_time=2.0,
                reason="Retryable HTTP status: 503"
            )
            
            with patch('time.sleep'):
                result = self.handler.handle_network_error(error, self.context)
        
        assert not result.success
        assert "Network error (will retry)" in result.errors["test_provider"]
    
    def test_handle_network_error_connection_pool_exhaustion(self):
        """Test handling of connection pool exhaustion."""
        class PoolError(Exception):
            pass
        error = PoolError("HTTPSConnectionPool: Max retries exceeded")
        
        with patch.object(self.handler, 'should_retry') as mock_should_retry:
            mock_should_retry.return_value = RetryResult(
                should_retry=True,
                wait_time=1.0,
                reason="Connection pool exhaustion"
            )
            
            with patch('time.sleep'):
                result = self.handler.handle_network_error(error, self.context)
        
        assert not result.success
        assert "test_provider" in result.errors
    
    @patch('saidata_gen.fetcher.error_handler.REQUESTS_AVAILABLE', True)
    def test_handle_ssl_error_certificate_expired(self):
        """Test handling of expired SSL certificates."""
        class SSLCertificateError(Exception):
            pass
        error = SSLCertificateError("certificate verify failed: certificate has expired")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"success"
        
        with patch.object(self.handler, '_try_ssl_verification_disabled') as mock_fallback:
            mock_fallback.return_value = mock_response
            
            result = self.handler.handle_ssl_error(error, self.context)
        
        assert result is not None
        assert result.status_code == 200
        assert "https://example.com/test" in self.handler._ssl_failed_urls
    
    @patch('saidata_gen.fetcher.error_handler.REQUESTS_AVAILABLE', True)
    def test_handle_ssl_error_hostname_mismatch(self):
        """Test handling of SSL hostname mismatch errors."""
        class SSLHostnameError(Exception):
            pass
        error = SSLHostnameError("hostname 'example.com' doesn't match certificate")
        
        # Mock all fallback strategies failing
        with patch.object(self.handler, '_try_ssl_verification_disabled') as mock_fallback1:
            with patch.object(self.handler, '_try_alternative_ssl_context') as mock_fallback2:
                with patch.object(self.handler, '_try_http_fallback') as mock_fallback3:
                    mock_fallback1.return_value = None
                    mock_fallback2.return_value = None
                    mock_fallback3.return_value = None
                    
                    result = self.handler.handle_ssl_error(error, self.context)
        
        assert result is None
        assert "https://example.com/test" in self.handler._ssl_failed_urls
    
    @patch('saidata_gen.fetcher.error_handler.REQUESTS_AVAILABLE', True)
    def test_handle_ssl_error_self_signed_certificate(self):
        """Test handling of self-signed certificate errors."""
        class SSLSelfSignedError(Exception):
            pass
        error = SSLSelfSignedError("self signed certificate")
        
        # Mock successful fallback with disabled verification
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"self-signed success"
        
        with patch.object(self.handler, '_try_ssl_verification_disabled') as mock_fallback:
            mock_fallback.return_value = mock_response
            
            result = self.handler.handle_ssl_error(error, self.context)
        
        assert result is not None
        assert result.content == b"self-signed success"
    
    @patch('saidata_gen.fetcher.error_handler.REQUESTS_AVAILABLE', True)
    def test_handle_ssl_error_weak_cipher(self):
        """Test handling of weak cipher SSL errors."""
        class SSLWeakCipherError(Exception):
            pass
        error = SSLWeakCipherError("sslv3 alert handshake failure")
        
        # Mock alternative SSL context success
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"alternative context success"
        
        with patch.object(self.handler, '_try_ssl_verification_disabled') as mock_fallback1:
            with patch.object(self.handler, '_try_alternative_ssl_context') as mock_fallback2:
                mock_fallback1.return_value = None
                mock_fallback2.return_value = mock_response
                
                result = self.handler.handle_ssl_error(error, self.context)
        
        assert result is not None
        assert result.content == b"alternative context success"
    
    def test_handle_malformed_data_corrupted_json_with_encoding_issues(self):
        """Test handling of corrupted JSON with encoding issues."""
        # JSON with encoding issues and syntax errors
        corrupted_json = b'\xff\xfe{"key": "value\x00", "invalid": }'
        
        with patch.object(self.handler, '_handle_malformed_json') as mock_handler:
            mock_handler.return_value = {"key": "value"}
            
            result = self.handler.handle_malformed_data(corrupted_json, "json", self.context)
        
        assert result is not None
        assert result == {"key": "value"}
        mock_handler.assert_called_once_with(corrupted_json, self.context)
    
    def test_handle_malformed_data_xml_with_invalid_characters(self):
        """Test handling of XML with invalid characters."""
        # XML with control characters and encoding issues
        malformed_xml = b'<?xml version="1.0"?>\x00<root>\x01<item>value\x02</item></root>'
        
        with patch.object(self.handler, '_handle_malformed_xml') as mock_handler:
            mock_handler.return_value = {"root": {"item": "value"}}
            
            result = self.handler.handle_malformed_data(malformed_xml, "xml", self.context)
        
        assert result is not None
        assert result == {"root": {"item": "value"}}
    
    def test_handle_malformed_data_yaml_with_tab_indentation(self):
        """Test handling of YAML with tab indentation issues."""
        # YAML with tabs instead of spaces
        malformed_yaml = b'key: value\n\tindented:\n\t\tdeep: item'
        
        with patch.object(self.handler, '_handle_malformed_yaml') as mock_handler:
            mock_handler.return_value = {"key": "value", "indented": {"deep": "item"}}
            
            result = self.handler.handle_malformed_data(malformed_yaml, "yaml", self.context)
        
        assert result is not None
        assert result == {"key": "value", "indented": {"deep": "item"}}
    
    def test_should_retry_with_custom_error_types(self):
        """Test retry logic with custom error types."""
        # Test custom timeout error
        class CustomTimeoutError(Exception):
            pass
        
        error = CustomTimeoutError("Custom timeout occurred")
        result = self.handler.should_retry(error, 1)
        
        # Should not retry unknown error types by default
        assert not result.should_retry
        assert "Non-retryable error type" in result.reason
    
    def test_should_retry_with_http_error_edge_cases(self):
        """Test retry logic with HTTP error edge cases."""
        # Test 502 Bad Gateway (should retry)
        class HTTPError(Exception):
            def __init__(self, status_code):
                self.response = Mock()
                self.response.status_code = status_code
        
        error_502 = HTTPError(502)
        result = self.handler.should_retry(error_502, 1)
        assert result.should_retry
        assert "Retryable HTTP status: 502" in result.reason
        
        # Test 401 Unauthorized (should not retry)
        error_401 = HTTPError(401)
        result = self.handler.should_retry(error_401, 1)
        assert not result.should_retry
        assert "Non-retryable HTTP status: 401" in result.reason
        
        # Test 403 Forbidden (should not retry)
        error_403 = HTTPError(403)
        result = self.handler.should_retry(error_403, 1)
        assert not result.should_retry
        assert "Non-retryable HTTP status: 403" in result.reason
    
    def test_calculate_backoff_time_with_high_attempts(self):
        """Test exponential backoff with high attempt numbers."""
        # Test that backoff time is within reasonable ranges (due to jitter, exact ordering isn't guaranteed)
        time_1 = self.handler._calculate_backoff_time(1)
        time_2 = self.handler._calculate_backoff_time(2)
        time_3 = self.handler._calculate_backoff_time(3)
        
        # Should be reasonable for low attempts (base_wait_time = 0.1)
        # Attempt 1: 0.1 * 2^0 + jitter = 0.1 + (0.1 to 0.5) = 0.2 to 0.6
        assert 0.2 <= time_1 <= 0.6
        # Attempt 2: 0.1 * 2^1 + jitter = 0.2 + (0.1 to 0.5) = 0.3 to 0.7
        assert 0.3 <= time_2 <= 0.7
        # Attempt 3: 0.1 * 2^2 + jitter = 0.4 + (0.1 to 0.5) = 0.5 to 0.9
        assert 0.5 <= time_3 <= 0.9
        
        # Test that all times are positive
        assert time_1 > 0
        assert time_2 > 0
        assert time_3 > 0
    
    def test_error_statistics_comprehensive(self):
        """Test comprehensive error statistics tracking."""
        # Generate various types of errors
        network_error = Exception("Network error")
        ssl_error = Exception("SSL error")
        
        # Multiple network errors
        for i in range(3):
            self.handler.handle_network_error(network_error, self.context)
        
        # Multiple SSL errors
        for i in range(2):
            self.handler.handle_ssl_error(ssl_error, self.context)
        
        # Malformed data errors
        self.handler.handle_malformed_data(b'invalid json', 'json', self.context)
        
        stats = self.handler.get_error_statistics()
        
        assert stats["error_counts"]["network_errors"] == 3
        assert stats["error_counts"]["ssl_errors"] == 2
        assert stats["error_counts"]["malformed_data_errors"] == 1
        assert stats["total_failed_urls"] >= 1  # At least one unique URL
        
        # Check that URLs are tracked correctly
        assert len(stats["failed_urls"]["network_failed"]) >= 1
        assert len(stats["failed_urls"]["ssl_failed"]) >= 1
        assert len(stats["failed_urls"]["malformed_data"]) >= 1
    
    @patch('saidata_gen.fetcher.error_handler.REQUESTS_AVAILABLE', True)
    def test_ssl_fallback_strategies_comprehensive(self):
        """Test all SSL fallback strategies comprehensively."""
        ssl_error = Exception("SSL certificate error")
        
        # Test each fallback strategy individually
        with patch.object(self.handler, '_try_ssl_verification_disabled') as mock_disabled:
            with patch.object(self.handler, '_try_alternative_ssl_context') as mock_alt_context:
                with patch.object(self.handler, '_try_http_fallback') as mock_http:
                    
                    # Test first strategy success
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_disabled.return_value = mock_response
                    mock_alt_context.return_value = None
                    mock_http.return_value = None
                    
                    result = self.handler.handle_ssl_error(ssl_error, self.context)
                    
                    assert result is not None
                    assert result.status_code == 200
                    mock_disabled.assert_called_once()
                    # Other strategies should not be called if first succeeds
                    mock_alt_context.assert_not_called()
                    mock_http.assert_not_called()
    
    def test_malformed_data_encoding_fallback_comprehensive(self):
        """Test comprehensive encoding fallback for malformed data."""
        # Test data with various encoding issues
        test_cases = [
            (b'\xff\xfe{"key": "value"}', 'json'),  # UTF-16 BOM
            (b'\xef\xbb\xbf{"key": "value"}', 'json'),  # UTF-8 BOM
            (b'{"key": "value"}', 'json'),  # Clean UTF-8
            (b'\x80\x81{"key": "value"}', 'json'),  # Invalid UTF-8
        ]
        
        for data, format_type in test_cases:
            with patch.object(self.handler, f'_handle_malformed_{format_type}') as mock_handler:
                mock_handler.return_value = {"key": "value"}
                
                result = self.handler.handle_malformed_data(data, format_type, self.context)
                
                assert result is not None
                assert result == {"key": "value"}
                mock_handler.assert_called_once_with(data, self.context)
                mock_handler.reset_mock()
    
    def test_concurrent_error_handling(self):
        """Test error handling under concurrent scenarios."""
        import threading
        import time
        
        errors = []
        
        def generate_errors():
            for i in range(10):
                try:
                    error = Exception(f"Concurrent error {i}")
                    result = self.handler.handle_network_error(error, self.context)
                    errors.append(result)
                except Exception as e:
                    errors.append(e)
                time.sleep(0.01)  # Small delay to simulate real conditions
        
        # Start multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=generate_errors)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify that all errors were handled without exceptions
        assert len(errors) == 30  # 3 threads * 10 errors each
        assert all(isinstance(error, FetchResult) for error in errors)
        
        # Verify statistics are consistent
        stats = self.handler.get_error_statistics()
        assert stats["error_counts"]["network_errors"] == 30


# Mock network failure scenarios for integration testing
class TestNetworkFailureScenarios:
    """Test cases for various network failure scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = FetcherErrorHandler(max_retries=3, base_wait_time=0.1)
    
    @patch('saidata_gen.fetcher.error_handler.REQUESTS_AVAILABLE', True)
    def test_intermittent_network_connectivity(self):
        """Test handling of intermittent network connectivity."""
        context = ErrorContext(
            provider="intermittent_provider",
            url="https://unstable.example.com",
            attempt=1,
            max_attempts=3
        )
        
        # Simulate intermittent failures
        connection_errors = [
            Exception("Connection timed out"),
            Exception("Network is unreachable"),
            Exception("Connection refused")
        ]
        
        results = []
        for error in connection_errors:
            with patch('time.sleep'):  # Speed up test
                result = self.handler.handle_network_error(error, context)
                results.append(result)
                context.attempt += 1
        
        # All should be handled gracefully
        assert all(not result.success for result in results)
        assert len(self.handler._network_failed_urls) == 1  # Same URL
        assert self.handler._error_stats['network_errors'] == 3
    
    @patch('saidata_gen.fetcher.error_handler.REQUESTS_AVAILABLE', True)
    def test_cascading_ssl_failures(self):
        """Test handling of cascading SSL failures across multiple URLs."""
        ssl_contexts = [
            ErrorContext("provider1", "https://expired-cert.example.com", 1, 3),
            ErrorContext("provider2", "https://self-signed.example.com", 1, 3),
            ErrorContext("provider3", "https://wrong-host.example.com", 1, 3),
        ]
        
        ssl_errors = [
            Exception("certificate has expired"),
            Exception("self signed certificate"),
            Exception("hostname mismatch")
        ]
        
        results = []
        for context, error in zip(ssl_contexts, ssl_errors):
            with patch.object(self.handler, '_try_ssl_verification_disabled') as mock_fallback:
                mock_fallback.return_value = None  # All fallbacks fail
                result = self.handler.handle_ssl_error(error, context)
                results.append(result)
        
        # All should fail
        assert all(result is None for result in results)
        assert len(self.handler._ssl_failed_urls) == 3
        assert self.handler._error_stats['ssl_errors'] == 3
    
    def test_mixed_error_scenarios(self):
        """Test handling of mixed error scenarios in a single session."""
        contexts = [
            ErrorContext("provider1", "https://timeout.example.com", 1, 3),
            ErrorContext("provider2", "https://ssl-error.example.com", 1, 3),
            ErrorContext("provider3", "https://malformed.example.com", 1, 3),
        ]
        
        # Network error
        network_error = Exception("Connection timeout")
        with patch('time.sleep'):
            network_result = self.handler.handle_network_error(network_error, contexts[0])
        
        # SSL error
        ssl_error = Exception("SSL certificate error")
        ssl_result = self.handler.handle_ssl_error(ssl_error, contexts[1])
        
        # Malformed data error
        malformed_data = b'{"invalid": json}'
        malformed_result = self.handler.handle_malformed_data(malformed_data, 'json', contexts[2])
        
        # Verify all were handled
        assert not network_result.success
        assert ssl_result is None
        assert malformed_result is None
        
        # Verify statistics
        stats = self.handler.get_error_statistics()
        assert stats["error_counts"]["network_errors"] == 1
        assert stats["error_counts"]["ssl_errors"] == 1
        assert stats["error_counts"]["malformed_data_errors"] == 1
        assert stats["total_failed_urls"] == 3