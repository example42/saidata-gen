#!/usr/bin/env python3
"""
Example demonstrating the caching and performance optimization features of saidata-gen.

This example shows how to use the intelligent caching system and performance monitoring
together to optimize data fetching and processing operations.
"""

import time
from typing import Dict, Any

from saidata_gen.core.cache import CacheManager, CacheConfig, cached
from saidata_gen.core.performance import (
    PerformanceOptimizer,
    PerformanceConfig,
    monitor_performance,
    rate_limited,
    concurrent_limited,
)


def main():
    """Demonstrate caching and performance optimization features."""
    
    print("🚀 Saidata-Gen Performance Optimization Example")
    print("=" * 50)
    
    # Configure performance optimization
    perf_config = PerformanceConfig(
        enable_metrics=True,
        enable_rate_limiting=True,
        enable_connection_pooling=True,
        rate_limit_requests_per_second=5.0,
        rate_limit_burst_size=3,
        max_total_connections=2
    )
    
    # Configure caching
    cache_config = CacheConfig(
        backend="memory",
        default_ttl=60,
        max_size=100
    )
    
    # Create optimizer and cache manager
    optimizer = PerformanceOptimizer(perf_config)
    cache_manager = CacheManager(cache_config)
    
    try:
        # Example 1: Cached expensive operation
        print("\n📊 Example 1: Cached Expensive Operation")
        print("-" * 40)
        
        @cached(cache_manager)
        @monitor_performance(optimizer.monitor, "expensive_calculation")
        def expensive_calculation(n: int) -> Dict[str, Any]:
            """Simulate an expensive calculation that benefits from caching."""
            print(f"  Computing expensive calculation for n={n}...")
            time.sleep(0.1)  # Simulate work
            
            result = sum(i * i for i in range(n))
            return {
                "input": n,
                "result": result,
                "computed_at": time.time()
            }
        
        # First call (cache miss)
        print("First call (cache miss):")
        start_time = time.time()
        result1 = expensive_calculation(1000)
        first_duration = time.time() - start_time
        print(f"  Result: {result1['result']}")
        print(f"  Duration: {first_duration:.3f}s")
        
        # Second call (cache hit)
        print("\nSecond call (cache hit):")
        start_time = time.time()
        result2 = expensive_calculation(1000)
        second_duration = time.time() - start_time
        print(f"  Result: {result2['result']}")
        print(f"  Duration: {second_duration:.3f}s")
        print(f"  Speedup: {first_duration / second_duration:.1f}x")
        
        # Example 2: Rate-limited operations
        print("\n🚦 Example 2: Rate-Limited Operations")
        print("-" * 40)
        
        @rate_limited(optimizer.rate_limiter, tokens=1, timeout=1.0)
        @monitor_performance(optimizer.monitor, "api_call")
        def simulate_api_call(endpoint: str) -> Dict[str, Any]:
            """Simulate a rate-limited API call."""
            print(f"  Making API call to {endpoint}")
            time.sleep(0.05)  # Simulate network delay
            return {
                "endpoint": endpoint,
                "status": "success",
                "timestamp": time.time()
            }
        
        print("Making multiple API calls (rate limited):")
        start_time = time.time()
        
        for i in range(5):
            try:
                result = simulate_api_call(f"/api/data/{i}")
                print(f"  ✅ Call {i+1}: {result['status']}")
            except TimeoutError:
                print(f"  ❌ Call {i+1}: Rate limited")
        
        total_time = time.time() - start_time
        print(f"Total time: {total_time:.2f}s")
        
        # Example 3: Concurrent operations with limits
        print("\n⚡ Example 3: Concurrent Operations")
        print("-" * 40)
        
        @concurrent_limited(optimizer.concurrency_controller)
        @monitor_performance(optimizer.monitor, "concurrent_task")
        def concurrent_task(task_id: int) -> Dict[str, Any]:
            """Simulate a concurrent task with concurrency limits."""
            print(f"  Starting task {task_id}")
            time.sleep(0.2)  # Simulate work
            print(f"  Completed task {task_id}")
            return {
                "task_id": task_id,
                "status": "completed",
                "duration": 0.2
            }
        
        print("Running concurrent tasks (limited concurrency):")
        
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(concurrent_task, i)
                for i in range(6)
            ]
            
            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        print(f"Completed {len(results)} tasks")
        
        # Example 4: Performance monitoring and reporting
        print("\n📈 Example 4: Performance Report")
        print("-" * 40)
        
        # Get comprehensive performance report
        report = optimizer.get_performance_report()
        
        print("Performance Summary:")
        print(f"  Active operations: {report['concurrency']['active_operations']}")
        print(f"  Available slots: {report['concurrency']['available_slots']}")
        
        if "metrics" in report:
            metrics = report["metrics"]
            print(f"  Total metrics collected: {metrics['total_metrics']}")
            
            # Show histogram statistics
            if "histogram_stats" in metrics:
                print("\n  Operation Statistics:")
                for name, stats in metrics["histogram_stats"].items():
                    if stats["count"] > 0:
                        print(f"    {name}:")
                        print(f"      Count: {stats['count']}")
                        print(f"      Mean: {stats['mean']:.4f}s")
                        print(f"      P95: {stats['p95']:.4f}s")
        
        # Cache statistics
        cache_stats = cache_manager.get_stats()
        print(f"\nCache Statistics:")
        print(f"  Hits: {cache_stats.hits}")
        print(f"  Misses: {cache_stats.misses}")
        print(f"  Hit rate: {cache_stats.hit_rate:.1%}")
        print(f"  Current size: {cache_stats.size}")
        
        # Example 5: Cache management
        print("\n🗄️  Example 5: Cache Management")
        print("-" * 40)
        
        # Add some test data to cache
        for i in range(5):
            cache_manager.put(f"test_key_{i}", f"test_value_{i}")
        
        print(f"Cache size after adding data: {cache_manager.get_stats().size}")
        
        # Invalidate pattern
        invalidated = cache_manager.invalidate_pattern("test_key_*")
        print(f"Invalidated {invalidated} entries matching pattern")
        print(f"Cache size after invalidation: {cache_manager.get_stats().size}")
        
        print("\n✅ Example completed successfully!")
        
    finally:
        # Cleanup
        optimizer.shutdown()
        cache_manager.shutdown()


if __name__ == "__main__":
    main()