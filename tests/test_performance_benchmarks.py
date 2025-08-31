"""
Performance and load testing for batch operations.

This module provides performance benchmarks and load tests for the saidata-gen system,
focusing on batch processing, concurrent operations, and scalability.
"""

import pytest
import time
import threading
import concurrent.futures
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Any
import statistics
import gc

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from saidata_gen.core.models import EnhancedSaidataMetadata
from saidata_gen.core.interfaces import PackageConfig
from saidata_gen.validation.schema import SchemaValidator
from saidata_gen.validation.quality import QualityAssessment
from saidata_gen.core.cache import CacheManager, MemoryCacheStorage
from saidata_gen.core.performance import PerformanceMonitor


@pytest.mark.slow
@pytest.mark.integration
class TestPerformanceBenchmarks:
    """Performance benchmarks for core operations."""
    
    @pytest.fixture
    def performance_workspace(self):
        """Create workspace for performance testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            
            # Create schema file
            schema_content = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "version": {"type": "string", "enum": ["0.1"]},
                    "description": {"type": "string"},
                    "packages": {"type": "object"}
                },
                "required": ["version"]
            }
            
            schema_file = workspace / "schema.json"
            with open(schema_file, "w") as f:
                import json
                json.dump(schema_content, f)
            
            yield {
                "workspace": workspace,
                "schema_file": schema_file
            }
    
    def generate_test_metadata(self, count: int) -> List[Dict[str, Any]]:
        """Generate test metadata for performance testing."""
        metadata_list = []
        
        for i in range(count):
            metadata = {
                "version": "0.1",
                "description": f"Test software package {i}",
                "language": "python" if i % 2 == 0 else "javascript",
                "license": "MIT" if i % 3 == 0 else "Apache-2.0",
                "platforms": ["linux", "macos"] if i % 2 == 0 else ["linux", "windows"],
                "packages": {
                    "apt": {"name": f"test-pkg-{i}", "version": f"1.{i}.0"},
                    "npm": {"name": f"test-pkg-{i}", "version": f"1.{i}.0"} if i % 2 == 0 else None
                },
                "urls": {
                    "website": f"https://example-{i}.com",
                    "documentation": f"https://docs.example-{i}.com"
                },
                "category": {
                    "default": "Development" if i % 2 == 0 else "Utilities",
                    "tags": [f"tag-{i}", f"category-{i % 5}"]
                }
            }
            
            # Remove None values
            if metadata["packages"]["npm"] is None:
                del metadata["packages"]["npm"]
            
            metadata_list.append(metadata)
        
        return metadata_list
    
    def test_metadata_creation_performance(self):
        """Test performance of metadata creation."""
        test_sizes = [10, 50, 100, 500]
        results = {}
        
        for size in test_sizes:
            metadata_list = self.generate_test_metadata(size)
            
            start_time = time.time()
            created_metadata = []
            
            for metadata_dict in metadata_list:
                metadata = EnhancedSaidataMetadata.from_dict(metadata_dict)
                created_metadata.append(metadata)
            
            end_time = time.time()
            duration = end_time - start_time
            
            results[size] = {
                "duration": duration,
                "items_per_second": size / duration if duration > 0 else float('inf'),
                "avg_time_per_item": duration / size if size > 0 else 0
            }
        
        # Verify performance scales reasonably
        for size, result in results.items():
            print(f"Size {size}: {result['items_per_second']:.2f} items/sec, "
                  f"{result['avg_time_per_item']*1000:.2f}ms per item")
            
            # Should be able to create at least 10 items per second
            assert result["items_per_second"] >= 10, f"Performance too slow for size {size}"
    
    def test_yaml_serialization_performance(self):
        """Test performance of YAML serialization."""
        test_sizes = [10, 50, 100, 200]
        results = {}
        
        for size in test_sizes:
            metadata_list = self.generate_test_metadata(size)
            enhanced_metadata = [
                EnhancedSaidataMetadata.from_dict(data) for data in metadata_list
            ]
            
            # Test serialization performance
            start_time = time.time()
            yaml_strings = []
            
            for metadata in enhanced_metadata:
                yaml_str = metadata.to_yaml()
                yaml_strings.append(yaml_str)
            
            end_time = time.time()
            serialization_duration = end_time - start_time
            
            # Test deserialization performance
            start_time = time.time()
            deserialized_metadata = []
            
            for yaml_str in yaml_strings:
                metadata = EnhancedSaidataMetadata.from_yaml(yaml_str)
                deserialized_metadata.append(metadata)
            
            end_time = time.time()
            deserialization_duration = end_time - start_time
            
            results[size] = {
                "serialization_duration": serialization_duration,
                "deserialization_duration": deserialization_duration,
                "serialization_rate": size / serialization_duration if serialization_duration > 0 else float('inf'),
                "deserialization_rate": size / deserialization_duration if deserialization_duration > 0 else float('inf')
            }
        
        # Verify performance
        for size, result in results.items():
            print(f"Size {size}: Serialization {result['serialization_rate']:.2f} items/sec, "
                  f"Deserialization {result['deserialization_rate']:.2f} items/sec")
            
            # Should be able to serialize/deserialize at least 5 items per second
            assert result["serialization_rate"] >= 5, f"Serialization too slow for size {size}"
            assert result["deserialization_rate"] >= 5, f"Deserialization too slow for size {size}"
    
    def test_validation_performance(self, performance_workspace):
        """Test performance of validation operations."""
        validator = SchemaValidator(str(performance_workspace["schema_file"]))
        test_sizes = [10, 50, 100, 200]
        results = {}
        
        for size in test_sizes:
            metadata_list = self.generate_test_metadata(size)
            
            # Test data validation performance
            start_time = time.time()
            validation_results = []
            
            for metadata_dict in metadata_list:
                result = validator.validate_data(metadata_dict)
                validation_results.append(result)
            
            end_time = time.time()
            duration = end_time - start_time
            
            results[size] = {
                "duration": duration,
                "validations_per_second": size / duration if duration > 0 else float('inf'),
                "valid_count": sum(1 for r in validation_results if r.valid),
                "invalid_count": sum(1 for r in validation_results if not r.valid)
            }
        
        # Verify performance
        for size, result in results.items():
            print(f"Size {size}: {result['validations_per_second']:.2f} validations/sec, "
                  f"{result['valid_count']} valid, {result['invalid_count']} invalid")
            
            # Should be able to validate at least 20 items per second
            assert result["validations_per_second"] >= 20, f"Validation too slow for size {size}"
    
    def test_quality_assessment_performance(self):
        """Test performance of quality assessment."""
        quality_assessor = QualityAssessment()
        test_sizes = [10, 25, 50, 100]
        results = {}
        
        for size in test_sizes:
            metadata_list = self.generate_test_metadata(size)
            
            start_time = time.time()
            assessments = []
            
            for metadata_dict in metadata_list:
                assessment = quality_assessor.assess_metadata_quality(metadata_dict)
                assessments.append(assessment)
            
            end_time = time.time()
            duration = end_time - start_time
            
            avg_score = statistics.mean(a["overall_score"] for a in assessments)
            
            results[size] = {
                "duration": duration,
                "assessments_per_second": size / duration if duration > 0 else float('inf'),
                "average_score": avg_score
            }
        
        # Verify performance
        for size, result in results.items():
            print(f"Size {size}: {result['assessments_per_second']:.2f} assessments/sec, "
                  f"avg score {result['average_score']:.2f}")
            
            # Should be able to assess at least 5 items per second
            assert result["assessments_per_second"] >= 5, f"Quality assessment too slow for size {size}"


@pytest.mark.slow
@pytest.mark.integration
class TestConcurrencyAndScalability:
    """Test concurrent operations and scalability."""
    
    def test_concurrent_metadata_creation(self):
        """Test concurrent metadata creation."""
        def create_metadata_batch(batch_id: int, batch_size: int) -> List[EnhancedSaidataMetadata]:
            """Create a batch of metadata concurrently."""
            metadata_list = []
            
            for i in range(batch_size):
                metadata_dict = {
                    "version": "0.1",
                    "description": f"Concurrent test package {batch_id}-{i}",
                    "packages": {"apt": {"name": f"test-pkg-{batch_id}-{i}", "version": "1.0.0"}}
                }
                
                metadata = EnhancedSaidataMetadata.from_dict(metadata_dict)
                metadata_list.append(metadata)
            
            return metadata_list
        
        # Test with different numbers of concurrent workers
        worker_counts = [1, 2, 4, 8]
        batch_size = 25
        results = {}
        
        for worker_count in worker_counts:
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = []
                
                for batch_id in range(worker_count):
                    future = executor.submit(create_metadata_batch, batch_id, batch_size)
                    futures.append(future)
                
                # Wait for all batches to complete
                all_metadata = []
                for future in concurrent.futures.as_completed(futures):
                    batch_metadata = future.result()
                    all_metadata.extend(batch_metadata)
            
            end_time = time.time()
            duration = end_time - start_time
            total_items = worker_count * batch_size
            
            results[worker_count] = {
                "duration": duration,
                "total_items": total_items,
                "items_per_second": total_items / duration if duration > 0 else float('inf'),
                "metadata_count": len(all_metadata)
            }
        
        # Verify results
        for worker_count, result in results.items():
            print(f"Workers {worker_count}: {result['items_per_second']:.2f} items/sec, "
                  f"{result['total_items']} total items")
            
            assert result["metadata_count"] == result["total_items"]
            assert result["items_per_second"] > 0
        
        # Performance should improve with more workers (up to a point)
        single_worker_rate = results[1]["items_per_second"]
        multi_worker_rate = results[4]["items_per_second"]
        
        # Multi-worker should be at least as fast as single worker
        assert multi_worker_rate >= single_worker_rate * 0.8, "Concurrency should not significantly hurt performance"
    
    def test_concurrent_validation(self):
        """Test concurrent validation operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create schema
            schema_content = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "version": {"type": "string", "enum": ["0.1"]},
                    "description": {"type": "string"}
                },
                "required": ["version"]
            }
            
            schema_file = Path(temp_dir) / "schema.json"
            with open(schema_file, "w") as f:
                import json
                json.dump(schema_content, f)
            
            validator = SchemaValidator(str(schema_file))
            
            def validate_batch(batch_id: int, batch_size: int) -> List[bool]:
                """Validate a batch of data concurrently."""
                results = []
                
                for i in range(batch_size):
                    # Mix of valid and invalid data
                    if i % 4 == 0:
                        # Invalid - missing version
                        data = {"description": f"Test {batch_id}-{i}"}
                    else:
                        # Valid
                        data = {"version": "0.1", "description": f"Test {batch_id}-{i}"}
                    
                    result = validator.validate_data(data)
                    results.append(result.valid)
                
                return results
            
            # Test concurrent validation
            worker_count = 4
            batch_size = 50
            
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = []
                
                for batch_id in range(worker_count):
                    future = executor.submit(validate_batch, batch_id, batch_size)
                    futures.append(future)
                
                # Collect results
                all_results = []
                for future in concurrent.futures.as_completed(futures):
                    batch_results = future.result()
                    all_results.extend(batch_results)
            
            end_time = time.time()
            duration = end_time - start_time
            total_validations = worker_count * batch_size
            
            # Verify results
            valid_count = sum(all_results)
            invalid_count = len(all_results) - valid_count
            
            print(f"Concurrent validation: {total_validations / duration:.2f} validations/sec, "
                  f"{valid_count} valid, {invalid_count} invalid")
            
            assert len(all_results) == total_validations
            assert valid_count > 0  # Should have some valid results
            assert invalid_count > 0  # Should have some invalid results (every 4th item)
            
            # Should be reasonably fast
            assert total_validations / duration >= 50, "Concurrent validation too slow"
    
    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_memory_usage_under_load(self):
        """Test memory usage under load."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create a large number of metadata objects
        metadata_objects = []
        batch_size = 100
        
        for batch in range(5):  # 5 batches of 100 = 500 total
            batch_metadata = []
            
            for i in range(batch_size):
                metadata_dict = {
                    "version": "0.1",
                    "description": f"Memory test package {batch}-{i}",
                    "language": "python",
                    "license": "MIT",
                    "platforms": ["linux", "macos", "windows"],
                    "packages": {
                        "apt": {"name": f"test-pkg-{batch}-{i}", "version": f"1.{i}.0"},
                        "brew": {"name": f"test-pkg-{batch}-{i}", "version": f"1.{i}.0"},
                        "npm": {"name": f"test-pkg-{batch}-{i}", "version": f"1.{i}.0"}
                    },
                    "urls": {
                        "website": f"https://example-{batch}-{i}.com",
                        "documentation": f"https://docs.example-{batch}-{i}.com",
                        "source": f"https://github.com/example/pkg-{batch}-{i}"
                    },
                    "category": {
                        "default": "Development",
                        "sub": "Tools",
                        "tags": [f"tag-{i}", f"batch-{batch}", "testing"]
                    }
                }
                
                metadata = EnhancedSaidataMetadata.from_dict(metadata_dict)
                batch_metadata.append(metadata)
            
            metadata_objects.extend(batch_metadata)
            
            # Check memory usage after each batch
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            print(f"Batch {batch + 1}: {len(metadata_objects)} objects, "
                  f"{current_memory:.1f}MB total, {memory_increase:.1f}MB increase")
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - initial_memory
        
        # Memory usage should be reasonable
        # Allow up to 100MB increase for 500 objects (rough estimate)
        assert total_memory_increase < 100, f"Memory usage too high: {total_memory_increase:.1f}MB"
        
        # Clean up and check memory is released
        del metadata_objects
        gc.collect()
        
        # Give some time for cleanup
        time.sleep(0.1)
        
        cleanup_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_after_cleanup = cleanup_memory - initial_memory
        
        print(f"After cleanup: {cleanup_memory:.1f}MB total, {memory_after_cleanup:.1f}MB increase")
        
        # Memory should be mostly released (allow some overhead)
        assert memory_after_cleanup < total_memory_increase * 0.5, "Memory not properly released"


@pytest.mark.slow
@pytest.mark.integration
class TestCachePerformance:
    """Test cache performance under various conditions."""
    
    def test_cache_performance_under_load(self):
        """Test cache performance under high load."""
        cache_manager = CacheManager(MemoryCacheStorage())
        
        # Test data
        test_data = {
            "software": "nginx",
            "version": "1.18.0",
            "description": "HTTP server and reverse proxy",
            "packages": {"apt": {"name": "nginx", "version": "1.18.0"}}
        }
        
        # Test cache write performance
        write_count = 1000
        start_time = time.time()
        
        for i in range(write_count):
            cache_key = f"test_key_{i}"
            cache_manager.put(cache_key, {**test_data, "id": i})
        
        write_duration = time.time() - start_time
        write_rate = write_count / write_duration
        
        print(f"Cache write performance: {write_rate:.2f} writes/sec")
        
        # Test cache read performance
        start_time = time.time()
        hit_count = 0
        
        for i in range(write_count):
            cache_key = f"test_key_{i}"
            cached_data = cache_manager.get(cache_key)
            if cached_data is not None:
                hit_count += 1
        
        read_duration = time.time() - start_time
        read_rate = write_count / read_duration
        
        print(f"Cache read performance: {read_rate:.2f} reads/sec, {hit_count} hits")
        
        # Verify performance
        assert write_rate >= 1000, f"Cache write too slow: {write_rate:.2f} writes/sec"
        assert read_rate >= 5000, f"Cache read too slow: {read_rate:.2f} reads/sec"
        assert hit_count == write_count, f"Cache hit rate too low: {hit_count}/{write_count}"
    
    def test_concurrent_cache_access(self):
        """Test concurrent cache access."""
        cache_manager = CacheManager(MemoryCacheStorage())
        
        def cache_worker(worker_id: int, operation_count: int) -> Dict[str, int]:
            """Worker function for concurrent cache operations."""
            stats = {"writes": 0, "reads": 0, "hits": 0, "misses": 0}
            
            for i in range(operation_count):
                cache_key = f"worker_{worker_id}_key_{i}"
                
                # Write operation
                test_data = {"worker": worker_id, "item": i, "data": f"test_data_{i}"}
                cache_manager.put(cache_key, test_data)
                stats["writes"] += 1
                
                # Read operation
                cached_data = cache_manager.get(cache_key)
                stats["reads"] += 1
                
                if cached_data is not None:
                    stats["hits"] += 1
                else:
                    stats["misses"] += 1
                
                # Also try to read from other workers' keys
                other_worker_key = f"worker_{(worker_id + 1) % 4}_key_{i}"
                other_data = cache_manager.get(other_worker_key)
                stats["reads"] += 1
                
                if other_data is not None:
                    stats["hits"] += 1
                else:
                    stats["misses"] += 1
            
            return stats
        
        # Run concurrent workers
        worker_count = 4
        operations_per_worker = 100
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = []
            
            for worker_id in range(worker_count):
                future = executor.submit(cache_worker, worker_id, operations_per_worker)
                futures.append(future)
            
            # Collect results
            all_stats = []
            for future in concurrent.futures.as_completed(futures):
                worker_stats = future.result()
                all_stats.append(worker_stats)
        
        duration = time.time() - start_time
        
        # Aggregate statistics
        total_writes = sum(stats["writes"] for stats in all_stats)
        total_reads = sum(stats["reads"] for stats in all_stats)
        total_hits = sum(stats["hits"] for stats in all_stats)
        total_misses = sum(stats["misses"] for stats in all_stats)
        
        write_rate = total_writes / duration
        read_rate = total_reads / duration
        hit_rate = total_hits / total_reads if total_reads > 0 else 0
        
        print(f"Concurrent cache performance: {write_rate:.2f} writes/sec, "
              f"{read_rate:.2f} reads/sec, {hit_rate:.2%} hit rate")
        
        # Verify performance and correctness
        assert total_writes == worker_count * operations_per_worker
        assert total_reads == worker_count * operations_per_worker * 2  # Each worker does 2 reads per iteration
        assert total_hits + total_misses == total_reads
        assert write_rate >= 500, f"Concurrent write performance too slow: {write_rate:.2f}"
        assert read_rate >= 1000, f"Concurrent read performance too slow: {read_rate:.2f}"
        assert hit_rate >= 0.4, f"Hit rate too low: {hit_rate:.2%}"  # Should hit at least 40% due to own writes


@pytest.mark.slow
@pytest.mark.integration
class TestPerformanceMonitoring:
    """Test performance monitoring capabilities."""
    
    def test_performance_monitor_overhead(self):
        """Test that performance monitoring has minimal overhead."""
        monitor = PerformanceMonitor()
        
        # Test without monitoring
        start_time = time.time()
        
        for i in range(1000):
            # Simulate some work
            result = sum(range(100))
        
        unmonitored_duration = time.time() - start_time
        
        # Test with monitoring
        start_time = time.time()
        
        for i in range(1000):
            with monitor.time_operation("test_operation"):
                # Same work as above
                result = sum(range(100))
        
        monitored_duration = time.time() - start_time
        
        # Calculate overhead
        overhead = monitored_duration - unmonitored_duration
        overhead_percentage = (overhead / unmonitored_duration) * 100
        
        print(f"Performance monitoring overhead: {overhead:.4f}s ({overhead_percentage:.1f}%)")
        
        # Overhead should be minimal (less than 50%)
        assert overhead_percentage < 50, f"Performance monitoring overhead too high: {overhead_percentage:.1f}%"
        
        # Verify metrics were collected
        metrics = monitor.get_metrics()
        assert "test_operation" in metrics
        assert metrics["test_operation"]["count"] == 1000
    
    def test_memory_monitoring_accuracy(self):
        """Test accuracy of memory monitoring."""
        monitor = PerformanceMonitor()
        
        # Get initial memory
        initial_memory = monitor.get_memory_info()
        
        # Allocate some memory
        large_data = []
        for i in range(100):
            # Create relatively large objects
            data = {
                "id": i,
                "data": "x" * 1000,  # 1KB string
                "metadata": {
                    "version": "0.1",
                    "description": f"Test data item {i}",
                    "tags": [f"tag-{j}" for j in range(10)]
                }
            }
            large_data.append(data)
        
        # Get memory after allocation
        after_allocation_memory = monitor.get_memory_info()
        
        # Clean up
        del large_data
        import gc
        gc.collect()
        
        # Get memory after cleanup
        after_cleanup_memory = monitor.get_memory_info()
        
        # Verify memory monitoring detected changes
        memory_increase = after_allocation_memory["current_memory_mb"] - initial_memory["current_memory_mb"]
        memory_decrease = after_allocation_memory["current_memory_mb"] - after_cleanup_memory["current_memory_mb"]
        
        print(f"Memory monitoring: +{memory_increase:.1f}MB allocation, -{memory_decrease:.1f}MB cleanup")
        
        # Should detect memory allocation (at least some increase)
        assert memory_increase > 0, "Memory monitoring should detect allocation"
        
        # Should detect memory cleanup (at least partial decrease)
        assert memory_decrease >= 0, "Memory monitoring should detect cleanup"