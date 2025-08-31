#!/usr/bin/env python3
"""
Performance Optimization Example
Demonstrates various performance optimization techniques for the saidata generator
"""

import time
import asyncio
import aiohttp
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import yaml
import argparse
from dataclasses import dataclass
from contextlib import asynccontextmanager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics for operations"""
    operation: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error: Optional[str] = None
    
    @property
    def duration_ms(self) -> float:
        return self.duration * 1000

class PerformanceOptimizer:
    """Demonstrates various performance optimization techniques"""
    
    def __init__(self, max_workers: int = 4, cache_dir: str = "./perf-cache"):
        self.max_workers = max_workers
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metrics: List[PerformanceMetrics] = []
        self.cache: Dict[str, Any] = {}
    
    def measure_performance(self, operation: str):
        """Decorator to measure operation performance"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error = None
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error = str(e)
                    raise
                finally:
                    end_time = time.time()
                    duration = end_time - start_time
                    
                    metric = PerformanceMetrics(
                        operation=operation,
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        success=success,
                        error=error
                    )
                    self.metrics.append(metric)
                    
                    logger.info(f"{operation} completed in {duration:.3f}s (success: {success})")
            
            return wrapper
        return decorator
    
    @measure_performance("sequential_processing")
    def process_sequential(self, software_list: List[str]) -> List[Dict[str, Any]]:
        """Process software list sequentially (baseline)"""
        results = []
        
        for software in software_list:
            result = self._simulate_metadata_generation(software)
            results.append(result)
        
        return results
    
    @measure_performance("parallel_processing")
    def process_parallel(self, software_list: List[str]) -> List[Dict[str, Any]]:
        """Process software list in parallel using ThreadPoolExecutor"""
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_software = {
                executor.submit(self._simulate_metadata_generation, software): software
                for software in software_list
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_software):
                software = future_to_software[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing {software}: {e}")
                    results.append({"software": software, "error": str(e)})
        
        return results
    
    @measure_performance("async_processing")
    async def process_async(self, software_list: List[str]) -> List[Dict[str, Any]]:
        """Process software list asynchronously"""
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def process_with_semaphore(software: str):
            async with semaphore:
                return await self._simulate_async_metadata_generation(software)
        
        tasks = [process_with_semaphore(software) for software in software_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "software": software_list[i],
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    @measure_performance("cached_processing")
    def process_with_cache(self, software_list: List[str]) -> List[Dict[str, Any]]:
        """Process software list with caching"""
        results = []
        cache_hits = 0
        cache_misses = 0
        
        for software in software_list:
            # Check cache first
            cache_key = f"metadata_{software}"
            
            if cache_key in self.cache:
                result = self.cache[cache_key]
                cache_hits += 1
                logger.debug(f"Cache hit for {software}")
            else:
                result = self._simulate_metadata_generation(software)
                self.cache[cache_key] = result
                cache_misses += 1
                logger.debug(f"Cache miss for {software}")
            
            results.append(result)
        
        logger.info(f"Cache performance: {cache_hits} hits, {cache_misses} misses")
        return results
    
    @measure_performance("batch_processing")
    def process_in_batches(self, software_list: List[str], batch_size: int = 5) -> List[Dict[str, Any]]:
        """Process software list in batches"""
        results = []
        
        for i in range(0, len(software_list), batch_size):
            batch = software_list[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} items")
            
            # Process batch in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(batch), self.max_workers)) as executor:
                batch_results = list(executor.map(self._simulate_metadata_generation, batch))
                results.extend(batch_results)
            
            # Small delay between batches to avoid overwhelming services
            time.sleep(0.1)
        
        return results
    
    def _simulate_metadata_generation(self, software: str) -> Dict[str, Any]:
        """Simulate metadata generation with realistic timing"""
        # Simulate network request and processing time
        processing_time = 0.1 + (hash(software) % 100) / 1000  # 0.1-0.2 seconds
        time.sleep(processing_time)
        
        return {
            "software": software,
            "description": f"Description for {software}",
            "category": "Software",
            "providers": ["apt", "brew"],
            "processing_time": processing_time,
            "timestamp": time.time()
        }
    
    async def _simulate_async_metadata_generation(self, software: str) -> Dict[str, Any]:
        """Simulate async metadata generation"""
        processing_time = 0.1 + (hash(software) % 100) / 1000
        await asyncio.sleep(processing_time)
        
        return {
            "software": software,
            "description": f"Description for {software}",
            "category": "Software",
            "providers": ["apt", "brew"],
            "processing_time": processing_time,
            "timestamp": time.time()
        }
    
    @measure_performance("http_requests_sequential")
    def make_http_requests_sequential(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Make HTTP requests sequentially"""
        import requests
        
        results = []
        for url in urls:
            try:
                response = requests.get(url, timeout=5)
                results.append({
                    "url": url,
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds(),
                    "success": True
                })
            except Exception as e:
                results.append({
                    "url": url,
                    "error": str(e),
                    "success": False
                })
        
        return results
    
    @measure_performance("http_requests_async")
    async def make_http_requests_async(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Make HTTP requests asynchronously"""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            tasks = [self._fetch_url(session, url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "url": urls[i],
                        "error": str(result),
                        "success": False
                    })
                else:
                    processed_results.append(result)
            
            return processed_results
    
    async def _fetch_url(self, session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
        """Fetch a single URL"""
        start_time = time.time()
        try:
            async with session.get(url) as response:
                await response.text()  # Read response body
                return {
                    "url": url,
                    "status_code": response.status,
                    "response_time": time.time() - start_time,
                    "success": True
                }
        except Exception as e:
            return {
                "url": url,
                "error": str(e),
                "success": False
            }
    
    def optimize_memory_usage(self, large_dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Demonstrate memory optimization techniques"""
        
        @self.measure_performance("memory_optimization")
        def process_with_generator():
            # Use generator to process data in chunks
            def data_generator(data, chunk_size=100):
                for i in range(0, len(data), chunk_size):
                    yield data[i:i + chunk_size]
            
            processed_count = 0
            for chunk in data_generator(large_dataset):
                # Process chunk
                for item in chunk:
                    # Simulate processing
                    processed_count += 1
                
                # Clear processed data from memory
                del chunk
            
            return {"processed_items": processed_count}
        
        return process_with_generator()
    
    def benchmark_different_approaches(self, software_list: List[str]) -> Dict[str, Any]:
        """Benchmark different processing approaches"""
        logger.info("Starting performance benchmark...")
        
        # Clear previous metrics
        self.metrics = []
        
        # Test sequential processing
        logger.info("Testing sequential processing...")
        sequential_results = self.process_sequential(software_list.copy())
        
        # Test parallel processing
        logger.info("Testing parallel processing...")
        parallel_results = self.process_parallel(software_list.copy())
        
        # Test async processing
        logger.info("Testing async processing...")
        async_results = asyncio.run(self.process_async(software_list.copy()))
        
        # Test cached processing (run twice to see cache effect)
        logger.info("Testing cached processing (first run)...")
        cached_results_1 = self.process_with_cache(software_list.copy())
        
        logger.info("Testing cached processing (second run)...")
        cached_results_2 = self.process_with_cache(software_list.copy())
        
        # Test batch processing
        logger.info("Testing batch processing...")
        batch_results = self.process_in_batches(software_list.copy(), batch_size=3)
        
        # Compile benchmark results
        benchmark_results = {
            "test_parameters": {
                "software_count": len(software_list),
                "max_workers": self.max_workers,
                "software_list": software_list
            },
            "results": {},
            "performance_metrics": []
        }
        
        # Process metrics
        for metric in self.metrics:
            benchmark_results["performance_metrics"].append({
                "operation": metric.operation,
                "duration_seconds": metric.duration,
                "duration_ms": metric.duration_ms,
                "success": metric.success,
                "error": metric.error
            })
            
            if metric.operation not in benchmark_results["results"]:
                benchmark_results["results"][metric.operation] = []
            
            benchmark_results["results"][metric.operation].append(metric.duration)
        
        # Calculate averages
        for operation, durations in benchmark_results["results"].items():
            avg_duration = sum(durations) / len(durations)
            benchmark_results["results"][operation] = {
                "average_duration": avg_duration,
                "total_runs": len(durations),
                "all_durations": durations
            }
        
        return benchmark_results
    
    def generate_performance_report(self, benchmark_results: Dict[str, Any], output_file: Path):
        """Generate a comprehensive performance report"""
        
        report = {
            "performance_benchmark_report": {
                "timestamp": time.time(),
                "test_configuration": benchmark_results["test_parameters"],
                "results_summary": {},
                "detailed_metrics": benchmark_results["performance_metrics"],
                "recommendations": []
            }
        }
        
        # Calculate summary statistics
        results = benchmark_results["results"]
        fastest_operation = min(results.keys(), key=lambda k: results[k]["average_duration"])
        slowest_operation = max(results.keys(), key=lambda k: results[k]["average_duration"])
        
        report["performance_benchmark_report"]["results_summary"] = {
            "fastest_approach": {
                "operation": fastest_operation,
                "average_duration": results[fastest_operation]["average_duration"]
            },
            "slowest_approach": {
                "operation": slowest_operation,
                "average_duration": results[slowest_operation]["average_duration"]
            },
            "performance_comparison": {}
        }
        
        # Compare all approaches to sequential baseline
        if "sequential_processing" in results:
            baseline_duration = results["sequential_processing"]["average_duration"]
            
            for operation, data in results.items():
                if operation != "sequential_processing":
                    speedup = baseline_duration / data["average_duration"]
                    report["performance_benchmark_report"]["results_summary"]["performance_comparison"][operation] = {
                        "speedup_factor": speedup,
                        "percentage_improvement": (speedup - 1) * 100
                    }
        
        # Generate recommendations
        recommendations = []
        
        if "parallel_processing" in results and "sequential_processing" in results:
            parallel_speedup = results["sequential_processing"]["average_duration"] / results["parallel_processing"]["average_duration"]
            if parallel_speedup > 1.5:
                recommendations.append(f"Parallel processing shows {parallel_speedup:.1f}x speedup - recommended for batch operations")
        
        if "cached_processing" in results:
            cache_runs = [m for m in benchmark_results["performance_metrics"] if m["operation"] == "cached_processing"]
            if len(cache_runs) >= 2:
                first_run = cache_runs[0]["duration_seconds"]
                second_run = cache_runs[1]["duration_seconds"]
                if second_run < first_run * 0.5:
                    recommendations.append("Caching provides significant performance improvement - enable for production")
        
        if "async_processing" in results:
            async_duration = results["async_processing"]["average_duration"]
            if fastest_operation == "async_processing":
                recommendations.append("Async processing is fastest - recommended for I/O intensive operations")
        
        report["performance_benchmark_report"]["recommendations"] = recommendations
        
        # Save report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Performance report saved to {output_file}")
        
        # Print summary
        print("\n" + "="*60)
        print("PERFORMANCE BENCHMARK SUMMARY")
        print("="*60)
        print(f"Test Items: {benchmark_results['test_parameters']['software_count']}")
        print(f"Max Workers: {benchmark_results['test_parameters']['max_workers']}")
        print()
        
        print("Results (average duration):")
        for operation, data in sorted(results.items(), key=lambda x: x[1]["average_duration"]):
            print(f"  {operation:25} {data['average_duration']:.3f}s")
        
        print()
        print("Recommendations:")
        for rec in recommendations:
            print(f"  • {rec}")
        
        print("="*60)

def main():
    parser = argparse.ArgumentParser(description="Performance optimization examples and benchmarks")
    parser.add_argument("--software-list", nargs="+", 
                       default=["nginx", "apache2", "mysql", "postgresql", "redis", "docker", "git", "vim"],
                       help="List of software to test with")
    parser.add_argument("--max-workers", type=int, default=4, help="Maximum number of worker threads")
    parser.add_argument("--output-dir", default="./performance-output", help="Output directory")
    parser.add_argument("--test-http", action="store_true", help="Include HTTP request tests")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    optimizer = PerformanceOptimizer(max_workers=args.max_workers)
    
    # Run benchmark
    benchmark_results = optimizer.benchmark_different_approaches(args.software_list)
    
    # Generate report
    report_file = output_dir / "performance_benchmark.json"
    optimizer.generate_performance_report(benchmark_results, report_file)
    
    # Test HTTP requests if requested
    if args.test_http:
        test_urls = [
            "https://httpbin.org/delay/1",
            "https://httpbin.org/delay/2",
            "https://httpbin.org/status/200",
            "https://httpbin.org/json"
        ]
        
        logger.info("Testing HTTP request performance...")
        
        # Sequential HTTP requests
        sequential_http = optimizer.make_http_requests_sequential(test_urls)
        
        # Async HTTP requests
        async_http = asyncio.run(optimizer.make_http_requests_async(test_urls))
        
        # Save HTTP test results
        http_results = {
            "sequential_http": sequential_http,
            "async_http": async_http,
            "performance_metrics": [
                {
                    "operation": m.operation,
                    "duration": m.duration,
                    "success": m.success
                }
                for m in optimizer.metrics
                if "http_requests" in m.operation
            ]
        }
        
        http_report_file = output_dir / "http_performance.json"
        with open(http_report_file, 'w') as f:
            json.dump(http_results, f, indent=2)
        
        logger.info(f"HTTP performance results saved to {http_report_file}")
    
    print(f"\nAll performance test results saved to: {output_dir}")

if __name__ == "__main__":
    main()