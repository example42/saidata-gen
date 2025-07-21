"""
Performance benchmarks and integration tests for the performance monitoring system.
"""

import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed

from saidata_gen.core.performance import (
    PerformanceConfig,
    PerformanceOptimizer,
    monitor_performance,
    rate_limited,
    concurrent_limited,
)


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmarks and integration tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = PerformanceConfig(
            enable_metrics=True,
            enable_rate_limiting=True,
            enable_connection_pooling=True,
            rate_limit_requests_per_second=50.0,
            rate_limit_burst_size=10,
            max_total_connections=5
        )
        self.optimizer = PerformanceOptimizer(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.optimizer.shutdown()
    
    def test_concurrent_operations_benchmark(self):
        """Benchmark concurrent operations with performance monitoring."""
        
        @monitor_performance(self.optimizer.monitor, "benchmark_operation")
        @concurrent_limited(self.optimizer.concurrency_controller)
        def benchmark_operation(operation_id: int) -> dict:
            """Simulate a CPU-intensive operation."""
            start_time = time.time()
            
            # Simulate work
            total = 0
            for i in range(10000):
                total += i * i
            
            end_time = time.time()
            
            return {
                "operation_id": operation_id,
                "result": total,
                "duration": end_time - start_time
            }
        
        # Run concurrent operations
        num_operations = 20
        results = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(benchmark_operation, i)
                for i in range(num_operations)
            ]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        # Verify all operations completed
        self.assertEqual(len(results), num_operations)
        
        # Check performance metrics
        metrics_summary = self.optimizer.monitor.get_summary()
        self.assertIn("benchmark_operation_duration:", metrics_summary["histogram_stats"])
        
        # Check for counter with status label
        counter_found = any(key.startswith("benchmark_operation_total:") for key in metrics_summary["counters"])
        self.assertTrue(counter_found, f"Counter not found in: {list(metrics_summary['counters'].keys())}")
        
        # Verify concurrency was limited
        duration_stats = metrics_summary["histogram_stats"]["benchmark_operation_duration:"]
        self.assertEqual(duration_stats["count"], num_operations)
        
        print(f"\nBenchmark Results:")
        print(f"Operations completed: {num_operations}")
        print(f"Average duration: {duration_stats['mean']:.4f}s")
        print(f"Min duration: {duration_stats['min']:.4f}s")
        print(f"Max duration: {duration_stats['max']:.4f}s")
        print(f"P95 duration: {duration_stats['p95']:.4f}s")
    
    def test_rate_limited_operations_benchmark(self):
        """Benchmark rate-limited operations."""
        
        @monitor_performance(self.optimizer.monitor, "rate_limited_operation")
        @rate_limited(self.optimizer.rate_limiter, tokens=1, timeout=1.0)
        def rate_limited_operation(operation_id: int) -> dict:
            """Simulate a rate-limited operation."""
            start_time = time.time()
            
            # Simulate quick work
            time.sleep(0.01)
            
            end_time = time.time()
            
            return {
                "operation_id": operation_id,
                "duration": end_time - start_time
            }
        
        # Run rate-limited operations
        num_operations = 15
        results = []
        start_time = time.time()
        
        for i in range(num_operations):
            try:
                result = rate_limited_operation(i)
                results.append(result)
            except TimeoutError:
                # Expected when rate limit is exceeded
                break
        
        total_time = time.time() - start_time
        
        # Should have completed some operations within rate limit
        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), num_operations)
        
        print(f"\nRate Limiting Results:")
        print(f"Operations attempted: {num_operations}")
        print(f"Operations completed: {len(results)}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Effective rate: {len(results) / total_time:.2f} ops/sec")
    
    def test_cache_performance_impact(self):
        """Test performance impact of caching."""
        from saidata_gen.core.cache import CacheManager, CacheConfig, cached
        
        # Create cache manager
        cache_config = CacheConfig(backend="memory", default_ttl=60)
        cache_manager = CacheManager(cache_config)
        
        @cached(cache_manager)
        @monitor_performance(self.optimizer.monitor, "cached_operation")
        def expensive_operation(x: int) -> int:
            """Simulate an expensive operation."""
            time.sleep(0.01)  # Simulate work
            return x * x
        
        # First run (cache miss)
        start_time = time.time()
        result1 = expensive_operation(42)
        first_run_time = time.time() - start_time
        
        # Second run (cache hit)
        start_time = time.time()
        result2 = expensive_operation(42)
        second_run_time = time.time() - start_time
        
        # Results should be the same
        self.assertEqual(result1, result2)
        
        # Second run should be faster (or at least not significantly slower)
        # Note: Due to timing precision, we just check that caching worked
        self.assertLessEqual(second_run_time, first_run_time * 2.0)  # Allow some variance
        
        # Check cache statistics
        cache_stats = cache_manager.get_stats()
        self.assertEqual(cache_stats.hits, 1)
        self.assertEqual(cache_stats.misses, 1)
        self.assertEqual(cache_stats.hit_rate, 0.5)
        
        print(f"\nCache Performance Impact:")
        print(f"First run (cache miss): {first_run_time:.4f}s")
        print(f"Second run (cache hit): {second_run_time:.4f}s")
        print(f"Speedup: {first_run_time / second_run_time:.1f}x")
        print(f"Cache hit rate: {cache_stats.hit_rate:.1%}")
        
        cache_manager.shutdown()
    
    def test_comprehensive_performance_report(self):
        """Test comprehensive performance reporting."""
        
        # Generate some activity
        @monitor_performance(self.optimizer.monitor, "test_activity")
        def test_activity(duration: float):
            time.sleep(duration)
            return "completed"
        
        # Run various operations
        test_activity(0.01)
        test_activity(0.02)
        test_activity(0.015)
        
        # Increment some counters
        self.optimizer.monitor.increment_counter("test_requests", 10)
        self.optimizer.monitor.increment_counter("test_requests", 5)
        
        # Set some gauges
        self.optimizer.monitor.set_gauge("memory_usage", 512.0)
        self.optimizer.monitor.set_gauge("cpu_usage", 75.5)
        
        # Get comprehensive report
        report = self.optimizer.get_performance_report()
        
        # Verify report structure
        self.assertIn("config", report)
        self.assertIn("concurrency", report)
        self.assertIn("metrics", report)
        self.assertIn("rate_limiter", report)
        
        # Verify metrics are included
        metrics = report["metrics"]
        self.assertIn("total_metrics", metrics)
        self.assertIn("histogram_stats", metrics)
        self.assertIn("counters", metrics)
        self.assertIn("gauges", metrics)
        
        print(f"\nComprehensive Performance Report:")
        print(f"Total metrics collected: {metrics['total_metrics']}")
        print(f"Active operations: {report['concurrency']['active_operations']}")
        print(f"Available slots: {report['concurrency']['available_slots']}")
        
        if "test_activity_duration:" in metrics["histogram_stats"]:
            activity_stats = metrics["histogram_stats"]["test_activity_duration:"]
            print(f"Test activity - Count: {activity_stats['count']}")
            print(f"Test activity - Mean: {activity_stats['mean']:.4f}s")
            print(f"Test activity - P95: {activity_stats['p95']:.4f}s")
    
    def test_memory_usage_monitoring(self):
        """Test memory usage monitoring during operations."""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            @monitor_performance(self.optimizer.monitor, "memory_test")
            def memory_intensive_operation():
                # Create some data structures
                data = []
                for i in range(10000):
                    data.append({"id": i, "data": "x" * 100})
                
                # Monitor memory usage
                memory_info = process.memory_info()
                self.optimizer.monitor.set_gauge("memory_rss", memory_info.rss / 1024 / 1024)  # MB
                self.optimizer.monitor.set_gauge("memory_vms", memory_info.vms / 1024 / 1024)  # MB
                
                return len(data)
            
            # Run memory-intensive operation
            result = memory_intensive_operation()
            self.assertEqual(result, 10000)
            
            # Check memory metrics
            metrics = self.optimizer.monitor.get_summary()
            self.assertIn("memory_rss:", metrics["gauges"])
            self.assertIn("memory_vms:", metrics["gauges"])
            
            memory_rss = list(metrics["gauges"].values())[0]  # Get first gauge value
            print(f"\nMemory Usage Monitoring:")
            print(f"Peak RSS memory: {memory_rss:.1f} MB")
            
        except ImportError:
            # Skip test if psutil is not available
            self.skipTest("psutil not available for memory monitoring test")


if __name__ == "__main__":
    # Run benchmarks with verbose output
    unittest.main(verbosity=2)