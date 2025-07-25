"""
Unit tests for the performance monitoring and optimization system.
"""

import time
import unittest
from unittest.mock import Mock, patch
import threading

from saidata_gen.core.performance import (
    ConcurrencyController,
    ConnectionPool,
    MetricType,
    PerformanceConfig,
    PerformanceMetric,
    PerformanceMonitor,
    PerformanceOptimizer,
    RateLimiter,
    TimerResult,
    concurrent_limited,
    monitor_performance,
    rate_limited,
)


class TestPerformanceMetric(unittest.TestCase):
    """Test PerformanceMetric functionality."""
    
    def test_metric_creation(self):
        """Test performance metric creation."""
        metric = PerformanceMetric(
            name="test_metric",
            metric_type=MetricType.COUNTER,
            value=42.0,
            timestamp=time.time(),
            labels={"service": "test"}
        )
        
        self.assertEqual(metric.name, "test_metric")
        self.assertEqual(metric.metric_type, MetricType.COUNTER)
        self.assertEqual(metric.value, 42.0)
        self.assertEqual(metric.labels, {"service": "test"})
    
    def test_metric_to_dict(self):
        """Test metric serialization to dictionary."""
        metric = PerformanceMetric(
            name="test_metric",
            metric_type=MetricType.GAUGE,
            value=100.0,
            timestamp=1234567890.0,
            labels={"env": "test"}
        )
        
        result = metric.to_dict()
        
        expected = {
            "name": "test_metric",
            "type": "gauge",
            "value": 100.0,
            "timestamp": 1234567890.0,
            "labels": {"env": "test"}
        }
        
        self.assertEqual(result, expected)


class TestPerformanceMonitor(unittest.TestCase):
    """Test PerformanceMonitor functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = PerformanceConfig(enable_metrics=True, metrics_retention_seconds=60)
        self.monitor = PerformanceMonitor(self.config)
    
    def test_increment_counter(self):
        """Test counter increment functionality."""
        self.monitor.increment_counter("test_counter", 5.0, {"service": "test"})
        self.monitor.increment_counter("test_counter", 3.0, {"service": "test"})
        
        metrics = self.monitor.get_metrics("test_counter")
        self.assertEqual(len(metrics), 2)
        self.assertEqual(metrics[0].value, 5.0)
        self.assertEqual(metrics[1].value, 8.0)  # Cumulative
    
    def test_set_gauge(self):
        """Test gauge setting functionality."""
        self.monitor.set_gauge("test_gauge", 42.0, {"service": "test"})
        self.monitor.set_gauge("test_gauge", 84.0, {"service": "test"})
        
        metrics = self.monitor.get_metrics("test_gauge")
        self.assertEqual(len(metrics), 2)
        self.assertEqual(metrics[0].value, 42.0)
        self.assertEqual(metrics[1].value, 84.0)
    
    def test_record_histogram(self):
        """Test histogram recording functionality."""
        values = [1.0, 2.5, 3.2, 1.8, 4.1]
        
        for value in values:
            self.monitor.record_histogram("test_histogram", value, {"service": "test"})
        
        metrics = self.monitor.get_metrics("test_histogram")
        self.assertEqual(len(metrics), 5)
        
        recorded_values = [m.value for m in metrics]
        self.assertEqual(recorded_values, values)
    
    def test_timer_context_manager(self):
        """Test timer context manager functionality."""
        with self.monitor.timer("test_operation", {"service": "test"}) as timer_result:
            time.sleep(0.01)  # Small delay
        
        self.assertIsInstance(timer_result, TimerResult)
        self.assertGreater(timer_result.duration, 0.0)
        self.assertTrue(timer_result.success)
        self.assertIsNone(timer_result.error)
        
        # Check that metrics were recorded
        duration_metrics = self.monitor.get_metrics("test_operation_duration")
        total_metrics = self.monitor.get_metrics("test_operation_total")
        
        self.assertEqual(len(duration_metrics), 1)
        self.assertEqual(len(total_metrics), 1)
        self.assertEqual(total_metrics[0].labels["status"], "success")
    
    def test_timer_with_exception(self):
        """Test timer context manager with exception."""
        with self.assertRaises(ValueError):
            with self.monitor.timer("test_operation", {"service": "test"}) as timer_result:
                raise ValueError("Test error")
        
        self.assertFalse(timer_result.success)
        self.assertEqual(timer_result.error, "Test error")
        
        # Check that error metrics were recorded
        total_metrics = self.monitor.get_metrics("test_operation_total")
        self.assertEqual(len(total_metrics), 1)
        self.assertEqual(total_metrics[0].labels["status"], "error")
    
    def test_get_summary(self):
        """Test performance summary generation."""
        # Add various metrics
        self.monitor.increment_counter("requests", 10.0)
        self.monitor.set_gauge("memory_usage", 512.0)
        self.monitor.record_histogram("response_time", 0.1)
        self.monitor.record_histogram("response_time", 0.2)
        self.monitor.record_histogram("response_time", 0.15)
        
        summary = self.monitor.get_summary()
        
        self.assertIn("total_metrics", summary)
        self.assertIn("metric_names", summary)
        self.assertIn("counters", summary)
        self.assertIn("gauges", summary)
        self.assertIn("histogram_stats", summary)
        
        # Check histogram statistics
        response_time_key = "response_time:"
        self.assertIn(response_time_key, summary["histogram_stats"])
        
        stats = summary["histogram_stats"][response_time_key]
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["min"], 0.1)
        self.assertEqual(stats["max"], 0.2)
        self.assertAlmostEqual(stats["mean"], 0.15, places=2)
    
    def test_reset_metrics(self):
        """Test metrics reset functionality."""
        self.monitor.increment_counter("test_counter", 5.0)
        self.monitor.set_gauge("test_gauge", 42.0)
        
        # Verify metrics exist
        self.assertTrue(len(self.monitor.get_metrics()) > 0)
        
        # Reset and verify empty
        self.monitor.reset_metrics()
        self.assertEqual(len(self.monitor.get_metrics()), 0)
    
    def test_disabled_metrics(self):
        """Test behavior when metrics are disabled."""
        config = PerformanceConfig(enable_metrics=False)
        monitor = PerformanceMonitor(config)
        
        monitor.increment_counter("test_counter", 5.0)
        monitor.set_gauge("test_gauge", 42.0)
        monitor.record_histogram("test_histogram", 1.0)
        
        # Should have no metrics
        self.assertEqual(len(monitor.get_metrics()), 0)


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter functionality."""
    
    def test_rate_limiter_creation(self):
        """Test rate limiter creation."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=20)
        
        self.assertEqual(limiter.requests_per_second, 10.0)
        self.assertEqual(limiter.burst_size, 20)
        self.assertEqual(limiter.tokens, 20)
    
    def test_acquire_tokens(self):
        """Test token acquisition."""
        limiter = RateLimiter(requests_per_second=1.0, burst_size=3)  # Lower rate for testing
        
        # Should be able to acquire up to burst size immediately
        for _ in range(3):
            self.assertTrue(limiter.acquire(1, timeout=0.1))
        
        # Next acquisition should fail with short timeout
        self.assertFalse(limiter.acquire(1, timeout=0.01))
    
    def test_token_replenishment(self):
        """Test token replenishment over time."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=5)
        
        # Exhaust tokens
        for _ in range(5):
            self.assertTrue(limiter.acquire(1, timeout=0.1))
        
        # Wait for token replenishment
        time.sleep(0.2)  # Should add ~2 tokens
        
        # Should be able to acquire again
        self.assertTrue(limiter.acquire(1, timeout=0.1))
    
    def test_rate_limiter_context_manager(self):
        """Test rate limiter context manager."""
        limiter = RateLimiter(requests_per_second=1.0, burst_size=3)  # Lower rate for testing
        
        # Should work within burst limit
        with limiter.limit(1, timeout=0.1):
            pass
        
        # Exhaust remaining tokens
        for _ in range(2):
            with limiter.limit(1, timeout=0.1):
                pass
        
        # Should raise timeout error
        with self.assertRaises(TimeoutError):
            with limiter.limit(1, timeout=0.01):
                pass


class TestConcurrencyController(unittest.TestCase):
    """Test ConcurrencyController functionality."""
    
    def test_concurrency_controller_creation(self):
        """Test concurrency controller creation."""
        controller = ConcurrencyController(max_concurrent=5)
        
        self.assertEqual(controller.max_concurrent, 5)
        self.assertEqual(controller.get_active_count(), 0)
        self.assertEqual(controller.get_available_slots(), 5)
    
    def test_acquire_release(self):
        """Test acquiring and releasing concurrency slots."""
        controller = ConcurrencyController(max_concurrent=2)
        
        # Acquire first slot
        with controller.acquire():
            self.assertEqual(controller.get_active_count(), 1)
            self.assertEqual(controller.get_available_slots(), 1)
            
            # Acquire second slot
            with controller.acquire():
                self.assertEqual(controller.get_active_count(), 2)
                self.assertEqual(controller.get_available_slots(), 0)
        
        # Both slots should be released
        self.assertEqual(controller.get_active_count(), 0)
        self.assertEqual(controller.get_available_slots(), 2)
    
    def test_concurrent_access(self):
        """Test concurrent access to controller."""
        controller = ConcurrencyController(max_concurrent=2)
        results = []
        
        def worker(worker_id):
            with controller.acquire():
                results.append(f"start_{worker_id}")
                time.sleep(0.1)
                results.append(f"end_{worker_id}")
        
        # Start 3 threads (more than max_concurrent)
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have 6 results (3 starts, 3 ends)
        self.assertEqual(len(results), 6)
        
        # Count concurrent operations at any point
        concurrent_count = 0
        max_concurrent = 0
        
        for result in results:
            if result.startswith("start_"):
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            elif result.startswith("end_"):
                concurrent_count -= 1
        
        # Should not exceed max_concurrent
        self.assertLessEqual(max_concurrent, 2)


class TestConnectionPool(unittest.TestCase):
    """Test ConnectionPool functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = PerformanceConfig(
            enable_connection_pooling=True,
            max_connections_per_host=5,
            max_total_connections=20
        )
        self.monitor = PerformanceMonitor(self.config)
        self.pool = ConnectionPool(self.config, self.monitor)
    
    @patch('saidata_gen.core.performance.REQUESTS_AVAILABLE', True)
    @patch('requests.Session')
    def test_session_creation(self, mock_session_class):
        """Test HTTP session creation with connection pooling."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Create a fresh pool to avoid interference from setUp
        config = PerformanceConfig(enable_connection_pooling=True)
        pool = ConnectionPool(config)
        pool._create_session()
        
        # Verify session was created and configured
        mock_session_class.assert_called()
        self.assertGreaterEqual(mock_session.mount.call_count, 2)  # http and https
    
    def test_disabled_connection_pooling(self):
        """Test behavior when connection pooling is disabled."""
        config = PerformanceConfig(enable_connection_pooling=False)
        pool = ConnectionPool(config)
        
        self.assertIsNone(pool._session)
    
    def test_close_pool(self):
        """Test closing the connection pool."""
        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            pool = ConnectionPool(self.config)
            pool._create_session()
            pool.close()
            
            mock_session.close.assert_called_once()
            self.assertIsNone(pool._session)


class TestPerformanceOptimizer(unittest.TestCase):
    """Test PerformanceOptimizer functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = PerformanceConfig(
            enable_metrics=True,
            enable_rate_limiting=True,
            enable_connection_pooling=True,
            rate_limit_requests_per_second=10.0,
            rate_limit_burst_size=5,
            max_total_connections=10
        )
        self.optimizer = PerformanceOptimizer(self.config)
    
    def test_optimizer_creation(self):
        """Test performance optimizer creation."""
        self.assertIsNotNone(self.optimizer.monitor)
        self.assertIsNotNone(self.optimizer.connection_pool)
        self.assertIsNotNone(self.optimizer.rate_limiter)
        self.assertIsNotNone(self.optimizer.concurrency_controller)
    
    def test_optimized_request_context(self):
        """Test optimized request context manager."""
        with self.optimizer.optimized_request(tokens=1, timeout=1.0) as pool:
            self.assertIs(pool, self.optimizer.connection_pool)
    
    def test_performance_report(self):
        """Test performance report generation."""
        report = self.optimizer.get_performance_report()
        
        self.assertIn("config", report)
        self.assertIn("concurrency", report)
        self.assertIn("metrics", report)
        self.assertIn("rate_limiter", report)
        
        # Check config section
        config_section = report["config"]
        self.assertTrue(config_section["enable_metrics"])
        self.assertEqual(config_section["max_total_connections"], 10)
        
        # Check concurrency section
        concurrency_section = report["concurrency"]
        self.assertEqual(concurrency_section["active_operations"], 0)
        self.assertEqual(concurrency_section["max_concurrent"], 10)
    
    def test_shutdown(self):
        """Test optimizer shutdown."""
        # Should not raise any exceptions
        self.optimizer.shutdown()


class TestPerformanceDecorators(unittest.TestCase):
    """Test performance monitoring decorators."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = PerformanceConfig(enable_metrics=True)
        self.monitor = PerformanceMonitor(self.config)
        self.rate_limiter = RateLimiter(requests_per_second=10.0, burst_size=5)
        self.concurrency_controller = ConcurrencyController(max_concurrent=2)
    
    def test_monitor_performance_decorator(self):
        """Test performance monitoring decorator."""
        @monitor_performance(self.monitor, "test_function", {"service": "test"})
        def test_function(x, y):
            time.sleep(0.01)
            return x + y
        
        result = test_function(1, 2)
        self.assertEqual(result, 3)
        
        # Check that metrics were recorded
        duration_metrics = self.monitor.get_metrics("test_function_duration")
        total_metrics = self.monitor.get_metrics("test_function_total")
        
        self.assertEqual(len(duration_metrics), 1)
        self.assertEqual(len(total_metrics), 1)
        self.assertEqual(total_metrics[0].labels["status"], "success")
    
    def test_rate_limited_decorator(self):
        """Test rate limiting decorator."""
        # Use a more restrictive rate limiter for testing
        rate_limiter = RateLimiter(requests_per_second=1.0, burst_size=3)
        call_count = 0
        
        @rate_limited(rate_limiter, tokens=1, timeout=0.1)
        def test_function():
            nonlocal call_count
            call_count += 1
            return call_count
        
        # Should work within burst limit
        for i in range(3):
            result = test_function()
            self.assertEqual(result, i + 1)
        
        # Should raise timeout error when rate limited
        with self.assertRaises(TimeoutError):
            test_function()
    
    def test_concurrent_limited_decorator(self):
        """Test concurrency limiting decorator."""
        active_calls = 0
        max_concurrent = 0
        
        @concurrent_limited(self.concurrency_controller)
        def test_function():
            nonlocal active_calls, max_concurrent
            active_calls += 1
            max_concurrent = max(max_concurrent, active_calls)
            time.sleep(0.1)
            active_calls -= 1
            return active_calls
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=test_function)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should not exceed max_concurrent
        self.assertLessEqual(max_concurrent, 2)
        self.assertEqual(active_calls, 0)  # All should be finished


class TestTimerResult(unittest.TestCase):
    """Test TimerResult functionality."""
    
    def test_timer_result_creation(self):
        """Test timer result creation."""
        result = TimerResult(
            duration=1.5,
            start_time=1000.0,
            end_time=1001.5,
            success=True
        )
        
        self.assertEqual(result.duration, 1.5)
        self.assertEqual(result.start_time, 1000.0)
        self.assertEqual(result.end_time, 1001.5)
        self.assertTrue(result.success)
        self.assertIsNone(result.error)
    
    def test_timer_result_with_error(self):
        """Test timer result with error."""
        result = TimerResult(
            duration=0.5,
            start_time=1000.0,
            end_time=1000.5,
            success=False,
            error="Test error"
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Test error")


if __name__ == "__main__":
    unittest.main()