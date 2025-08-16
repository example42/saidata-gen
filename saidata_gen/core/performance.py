"""
Performance monitoring and optimization for saidata-gen.

This module provides performance metrics collection, connection pooling,
concurrency controls, and rate limiting functionality.
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum
import functools

# Try to import requests for connection pooling
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from urllib3.poolmanager import PoolManager
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    # Create dummy classes for type checking
    class HTTPAdapter:
        pass
    class Retry:
        pass
    class PoolManager:
        pass

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of performance metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class PerformanceMetric:
    """Performance metric data."""
    name: str
    metric_type: MetricType
    value: Union[int, float]
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary."""
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "value": self.value,
            "timestamp": self.timestamp,
            "labels": self.labels
        }


@dataclass
class TimerResult:
    """Result of a timer measurement."""
    duration: float
    start_time: float
    end_time: float
    success: bool = True
    error: Optional[str] = None


@dataclass
class PerformanceConfig:
    """Configuration for performance monitoring."""
    enable_metrics: bool = True
    metrics_retention_seconds: int = 3600  # 1 hour
    histogram_buckets: List[float] = field(default_factory=lambda: [
        0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
    ])
    max_connections_per_host: int = 10
    max_total_connections: int = 100
    connection_timeout: float = 30.0
    read_timeout: float = 30.0
    max_retries: int = 3
    backoff_factor: float = 0.3
    rate_limit_requests_per_second: float = 10.0
    rate_limit_burst_size: int = 20
    enable_connection_pooling: bool = True
    enable_rate_limiting: bool = True


class PerformanceMonitor:
    """
    Performance monitoring system for collecting and reporting metrics.
    """
    
    def __init__(self, config: Optional[PerformanceConfig] = None):
        """
        Initialize the performance monitor.
        
        Args:
            config: Performance configuration. If None, uses default configuration.
        """
        self.config = config or PerformanceConfig()
        self._metrics: Dict[str, List[PerformanceMetric]] = defaultdict(list)
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.RLock()
        
        # Start cleanup thread
        if self.config.enable_metrics:
            self._start_cleanup_thread()
    
    def _start_cleanup_thread(self) -> None:
        """Start background thread to clean up old metrics."""
        def cleanup_worker():
            while True:
                try:
                    self._cleanup_old_metrics()
                    time.sleep(60)  # Cleanup every minute
                except Exception as e:
                    logger.warning(f"Metrics cleanup error: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def _cleanup_old_metrics(self) -> None:
        """Remove old metrics beyond retention period."""
        if not self.config.enable_metrics:
            return
        
        cutoff_time = time.time() - self.config.metrics_retention_seconds
        
        with self._lock:
            for metric_name in list(self._metrics.keys()):
                self._metrics[metric_name] = [
                    metric for metric in self._metrics[metric_name]
                    if metric.timestamp > cutoff_time
                ]
                
                # Remove empty metric lists
                if not self._metrics[metric_name]:
                    del self._metrics[metric_name]
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name.
            value: Value to increment by.
            labels: Optional labels for the metric.
        """
        if not self.config.enable_metrics:
            return
        
        labels = labels or {}
        key = f"{name}:{':'.join(f'{k}={v}' for k, v in sorted(labels.items()))}"
        
        with self._lock:
            self._counters[key] += value
            
            metric = PerformanceMetric(
                name=name,
                metric_type=MetricType.COUNTER,
                value=self._counters[key],
                timestamp=time.time(),
                labels=labels
            )
            
            self._metrics[name].append(metric)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Set a gauge metric value.
        
        Args:
            name: Metric name.
            value: Gauge value.
            labels: Optional labels for the metric.
        """
        if not self.config.enable_metrics:
            return
        
        labels = labels or {}
        key = f"{name}:{':'.join(f'{k}={v}' for k, v in sorted(labels.items()))}"
        
        with self._lock:
            self._gauges[key] = value
            
            metric = PerformanceMetric(
                name=name,
                metric_type=MetricType.GAUGE,
                value=value,
                timestamp=time.time(),
                labels=labels
            )
            
            self._metrics[name].append(metric)
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Record a histogram metric value.
        
        Args:
            name: Metric name.
            value: Value to record.
            labels: Optional labels for the metric.
        """
        if not self.config.enable_metrics:
            return
        
        labels = labels or {}
        key = f"{name}:{':'.join(f'{k}={v}' for k, v in sorted(labels.items()))}"
        
        with self._lock:
            self._histograms[key].append(value)
            
            metric = PerformanceMetric(
                name=name,
                metric_type=MetricType.HISTOGRAM,
                value=value,
                timestamp=time.time(),
                labels=labels
            )
            
            self._metrics[name].append(metric)
    
    @contextmanager
    def timer(self, name: str, labels: Optional[Dict[str, str]] = None):
        """
        Context manager for timing operations.
        
        Args:
            name: Timer name.
            labels: Optional labels for the metric.
            
        Yields:
            TimerResult object that will be populated with timing data.
        """
        start_time = time.time()
        result = TimerResult(
            duration=0.0,
            start_time=start_time,
            end_time=0.0
        )
        
        try:
            yield result
            result.success = True
        except Exception as e:
            result.success = False
            result.error = str(e)
            raise
        finally:
            end_time = time.time()
            result.end_time = end_time
            result.duration = end_time - start_time
            
            if self.config.enable_metrics:
                # Record as histogram
                self.record_histogram(f"{name}_duration", result.duration, labels)
                
                # Record success/failure counter
                status_labels = (labels or {}).copy()
                status_labels["status"] = "success" if result.success else "error"
                self.increment_counter(f"{name}_total", 1.0, status_labels)
    
    def get_metrics(self, name: Optional[str] = None) -> List[PerformanceMetric]:
        """
        Get collected metrics.
        
        Args:
            name: Optional metric name to filter by.
            
        Returns:
            List of performance metrics.
        """
        with self._lock:
            if name:
                return self._metrics.get(name, []).copy()
            
            all_metrics = []
            for metrics_list in self._metrics.values():
                all_metrics.extend(metrics_list)
            
            return sorted(all_metrics, key=lambda m: m.timestamp)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get performance summary statistics.
        
        Returns:
            Dictionary with performance summary.
        """
        with self._lock:
            summary = {
                "total_metrics": sum(len(metrics) for metrics in self._metrics.values()),
                "metric_names": list(self._metrics.keys()),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histogram_stats": {}
            }
            
            # Calculate histogram statistics
            for key, values in self._histograms.items():
                if values:
                    summary["histogram_stats"][key] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "mean": sum(values) / len(values),
                        "p50": self._percentile(values, 0.5),
                        "p95": self._percentile(values, 0.95),
                        "p99": self._percentile(values, 0.99)
                    }
            
            return summary
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def reset_metrics(self) -> None:
        """Reset all collected metrics."""
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


class RateLimiter:
    """
    Token bucket rate limiter for controlling request rates.
    """
    
    def __init__(self, requests_per_second: float, burst_size: int):
        """
        Initialize the rate limiter.
        
        Args:
            requests_per_second: Maximum requests per second.
            burst_size: Maximum burst size (token bucket capacity).
        """
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_update = time.time()
        self._lock = threading.Lock()
    
    def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Acquire tokens from the rate limiter.
        
        Args:
            tokens: Number of tokens to acquire.
            timeout: Maximum time to wait for tokens.
            
        Returns:
            True if tokens were acquired, False if timeout occurred.
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                now = time.time()
                
                # Add tokens based on elapsed time
                elapsed = now - self.last_update
                self.tokens = min(
                    self.burst_size,
                    self.tokens + elapsed * self.requests_per_second
                )
                self.last_update = now
                
                # Check if we have enough tokens
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
            
            # Check timeout
            if timeout is not None and (time.time() - start_time) >= timeout:
                return False
            
            # Wait a bit before trying again
            time.sleep(0.01)
    
    @contextmanager
    def limit(self, tokens: int = 1, timeout: Optional[float] = None):
        """
        Context manager for rate limiting.
        
        Args:
            tokens: Number of tokens to acquire.
            timeout: Maximum time to wait for tokens.
            
        Raises:
            TimeoutError: If tokens cannot be acquired within timeout.
        """
        if not self.acquire(tokens, timeout):
            raise TimeoutError("Rate limit exceeded")
        
        yield


class ConnectionPool:
    """
    HTTP connection pool with retry logic and performance monitoring.
    """
    
    def __init__(self, config: PerformanceConfig, monitor: Optional[PerformanceMonitor] = None):
        """
        Initialize the connection pool.
        
        Args:
            config: Performance configuration.
            monitor: Optional performance monitor.
        """
        self.config = config
        self.monitor = monitor
        self._session = None
        self._lock = threading.Lock()
        
        if REQUESTS_AVAILABLE and config.enable_connection_pooling:
            self._create_session()
    
    def _create_session(self) -> None:
        """Create HTTP session with connection pooling and retry logic."""
        self._session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD", "POST", "PUT", "DELETE"]
        )
        
        # Configure connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.config.max_total_connections,
            pool_maxsize=self.config.max_connections_per_host
        )
        
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        
        # Set timeouts
        self._session.timeout = (self.config.connection_timeout, self.config.read_timeout)
    
    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with connection pooling and monitoring.
        
        Args:
            method: HTTP method.
            url: Request URL.
            **kwargs: Additional request arguments.
            
        Returns:
            Response object.
        """
        if not REQUESTS_AVAILABLE or not self.config.enable_connection_pooling:
            # Fallback to basic requests
            return requests.request(method, url, **kwargs)
        
        with self._lock:
            if self._session is None:
                self._create_session()
        
        # Monitor request performance
        labels = {"method": method.upper(), "host": url.split("/")[2] if "//" in url else "unknown"}
        
        if self.monitor:
            with self.monitor.timer("http_request", labels):
                response = self._session.request(method, url, **kwargs)
                
                # Record response status
                status_labels = labels.copy()
                status_labels["status_code"] = str(response.status_code)
                self.monitor.increment_counter("http_requests_total", 1.0, status_labels)
                
                return response
        else:
            return self._session.request(method, url, **kwargs)
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """Make GET request."""
        return self.request("GET", url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """Make POST request."""
        return self.request("POST", url, **kwargs)
    
    def put(self, url: str, **kwargs) -> requests.Response:
        """Make PUT request."""
        return self.request("PUT", url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> requests.Response:
        """Make DELETE request."""
        return self.request("DELETE", url, **kwargs)
    
    def close(self) -> None:
        """Close the connection pool."""
        with self._lock:
            if self._session:
                self._session.close()
                self._session = None


class ConcurrencyController:
    """
    Controls concurrent operations with semaphores and thread pools.
    """
    
    def __init__(self, max_concurrent: int = 10):
        """
        Initialize the concurrency controller.
        
        Args:
            max_concurrent: Maximum number of concurrent operations.
        """
        self.max_concurrent = max_concurrent
        self._semaphore = threading.Semaphore(max_concurrent)
        self._active_operations = 0
        self._lock = threading.Lock()
    
    @contextmanager
    def acquire(self):
        """
        Context manager for acquiring concurrency slot.
        
        Raises:
            RuntimeError: If unable to acquire slot.
        """
        acquired = self._semaphore.acquire(blocking=True)
        if not acquired:
            raise RuntimeError("Unable to acquire concurrency slot")
        
        try:
            with self._lock:
                self._active_operations += 1
            yield
        finally:
            with self._lock:
                self._active_operations -= 1
            self._semaphore.release()
    
    def get_active_count(self) -> int:
        """Get number of active operations."""
        with self._lock:
            return self._active_operations
    
    def get_available_slots(self) -> int:
        """Get number of available concurrency slots."""
        return self.max_concurrent - self.get_active_count()


class PerformanceOptimizer:
    """
    Main performance optimization system that combines all components.
    """
    
    def __init__(self, config: Optional[PerformanceConfig] = None):
        """
        Initialize the performance optimizer.
        
        Args:
            config: Performance configuration. If None, uses default configuration.
        """
        self.config = config or PerformanceConfig()
        self.monitor = PerformanceMonitor(self.config) if self.config.enable_metrics else None
        self.connection_pool = ConnectionPool(self.config, self.monitor)
        self.rate_limiter = RateLimiter(
            self.config.rate_limit_requests_per_second,
            self.config.rate_limit_burst_size
        ) if self.config.enable_rate_limiting else None
        self.concurrency_controller = ConcurrencyController(self.config.max_total_connections)
    
    @contextmanager
    def optimized_request(self, tokens: int = 1, timeout: Optional[float] = None):
        """
        Context manager for optimized HTTP requests with rate limiting and concurrency control.
        
        Args:
            tokens: Number of rate limit tokens to acquire.
            timeout: Timeout for rate limiting.
        """
        # Apply rate limiting
        if self.rate_limiter:
            with self.rate_limiter.limit(tokens, timeout):
                # Apply concurrency control
                with self.concurrency_controller.acquire():
                    yield self.connection_pool
        else:
            # Apply concurrency control only
            with self.concurrency_controller.acquire():
                yield self.connection_pool
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Get comprehensive performance report.
        
        Returns:
            Dictionary with performance metrics and statistics.
        """
        report = {
            "config": {
                "enable_metrics": self.config.enable_metrics,
                "max_connections_per_host": self.config.max_connections_per_host,
                "max_total_connections": self.config.max_total_connections,
                "rate_limit_rps": self.config.rate_limit_requests_per_second,
                "rate_limit_burst": self.config.rate_limit_burst_size,
            },
            "concurrency": {
                "active_operations": self.concurrency_controller.get_active_count(),
                "available_slots": self.concurrency_controller.get_available_slots(),
                "max_concurrent": self.concurrency_controller.max_concurrent,
            }
        }
        
        if self.monitor:
            report["metrics"] = self.monitor.get_summary()
        
        if self.rate_limiter:
            report["rate_limiter"] = {
                "requests_per_second": self.rate_limiter.requests_per_second,
                "burst_size": self.rate_limiter.burst_size,
                "current_tokens": self.rate_limiter.tokens,
            }
        
        return report
    
    def shutdown(self) -> None:
        """Shutdown the performance optimizer and cleanup resources."""
        self.connection_pool.close()


# Decorators for easy performance monitoring
def monitor_performance(
    monitor: PerformanceMonitor,
    metric_name: Optional[str] = None,
    labels: Optional[Dict[str, str]] = None
):
    """
    Decorator to monitor function performance.
    
    Args:
        monitor: Performance monitor instance.
        metric_name: Optional metric name. If None, uses function name.
        labels: Optional labels for the metric.
    """
    def decorator(func: Callable) -> Callable:
        name = metric_name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with monitor.timer(name, labels):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def rate_limited(
    rate_limiter: RateLimiter,
    tokens: int = 1,
    timeout: Optional[float] = None
):
    """
    Decorator to apply rate limiting to functions.
    
    Args:
        rate_limiter: Rate limiter instance.
        tokens: Number of tokens to acquire.
        timeout: Timeout for acquiring tokens.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with rate_limiter.limit(tokens, timeout):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def concurrent_limited(concurrency_controller: ConcurrencyController):
    """
    Decorator to apply concurrency limiting to functions.
    
    Args:
        concurrency_controller: Concurrency controller instance.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with concurrency_controller.acquire():
                return func(*args, **kwargs)
        
        return wrapper
    return decorator