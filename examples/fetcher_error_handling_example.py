#!/usr/bin/env python3
"""
Example demonstrating the FetcherErrorHandler usage.

This example shows how to use the FetcherErrorHandler class for centralized
error handling in repository fetchers.
"""

import json
import logging
from saidata_gen.fetcher.error_handler import FetcherErrorHandler, ErrorContext

# Set up logging to see the error handling in action
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def main():
    """Demonstrate FetcherErrorHandler usage."""
    print("FetcherErrorHandler Example")
    print("=" * 40)
    
    # Create an error handler
    handler = FetcherErrorHandler(max_retries=3, base_wait_time=1.0)
    
    # Example 1: Network error handling
    print("\n1. Network Error Handling:")
    context = ErrorContext(
        provider="example_provider",
        url="https://example.com/api/packages",
        attempt=1,
        max_attempts=3
    )
    
    # Simulate a connection error
    class ConnectionError(Exception):
        pass
    
    network_error = ConnectionError("Connection timed out")
    result = handler.handle_network_error(network_error, context)
    
    print(f"   Success: {result.success}")
    print(f"   Provider status: {result.providers}")
    print(f"   Errors: {result.errors}")
    
    # Example 2: Retry logic
    print("\n2. Retry Logic:")
    class TimeoutError(Exception):
        pass
    
    timeout_error = TimeoutError("Request timeout")
    retry_result = handler.should_retry(timeout_error, 1)
    
    print(f"   Should retry: {retry_result.should_retry}")
    print(f"   Wait time: {retry_result.wait_time:.2f}s")
    print(f"   Reason: {retry_result.reason}")
    
    # Example 3: Malformed data handling
    print("\n3. Malformed Data Handling:")
    malformed_json = b'{"packages": ["nginx", "apache",]}'  # Trailing comma
    
    context2 = ErrorContext(
        provider="json_provider",
        url="https://example.com/packages.json"
    )
    
    parsed_data = handler.handle_malformed_data(malformed_json, "json", context2)
    
    if parsed_data:
        print(f"   Successfully parsed: {parsed_data}")
    else:
        print("   Failed to parse malformed JSON")
    
    # Example 4: Error statistics
    print("\n4. Error Statistics:")
    stats = handler.get_error_statistics()
    
    print(f"   Network errors: {stats['error_counts']['network_errors']}")
    print(f"   SSL errors: {stats['error_counts']['ssl_errors']}")
    print(f"   Malformed data errors: {stats['error_counts']['malformed_data_errors']}")
    print(f"   Total failed URLs: {stats['total_failed_urls']}")
    
    # Example 5: HTTP error with status code
    print("\n5. HTTP Error with Status Code:")
    class HTTPError(Exception):
        def __init__(self, message, status_code):
            super().__init__(message)
            self.response = type('Response', (), {'status_code': status_code})()
    
    # Retryable HTTP error (503 Service Unavailable)
    http_error_503 = HTTPError("Service temporarily unavailable", 503)
    retry_result_503 = handler.should_retry(http_error_503, 1)
    
    print(f"   HTTP 503 - Should retry: {retry_result_503.should_retry}")
    print(f"   HTTP 503 - Reason: {retry_result_503.reason}")
    
    # Non-retryable HTTP error (404 Not Found)
    http_error_404 = HTTPError("Not found", 404)
    retry_result_404 = handler.should_retry(http_error_404, 1)
    
    print(f"   HTTP 404 - Should retry: {retry_result_404.should_retry}")
    print(f"   HTTP 404 - Reason: {retry_result_404.reason}")
    
    print("\n" + "=" * 40)
    print("Example completed successfully!")

if __name__ == "__main__":
    main()