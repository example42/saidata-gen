"""
Performance and load tests for the refactored system.

This module contains performance tests for template processing with large provider lists,
load tests for AI enhancement with concurrent requests, memory usage tests for batch
processing operations, and caching effectiveness tests.
"""

import asyncio
import concurrent.futures
import gc
import tempfile
import threading
import time
import unittest
import yaml
from pathlib import Path
from unittest.mock import Mock, patch
from typing import List, Dict, Any

# Optional dependencies for performance testing
try:
    import memory_profiler
    HAS_MEMORY_PROFILER = True
except ImportError:
    HAS_MEMORY_PROFILER = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from saidata_gen.generator.templates import TemplateEngine
from saidata_gen.generator.core import MetadataGenerator
from saidata_gen.ai.enhancer import AIMetadataEnhancer, AIEnhancementResult
from saidata_gen.core.interfaces import PackageInfo
from saidata_gen.core.cache import CacheManager, CacheConfig, CacheBackend


class TestPerformanceAndLoad(unittest.TestCase):
    """Performance and load tests for the refactored system."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for templates
        self.temp_dir = tempfile.TemporaryDirectory()
        self.templates_dir = Path(self.temp_dir.name)
        
        # List of providers for testing (define before creating templates)
        self.all_providers = [
            "apt", "brew", "winget", "choco", "scoop", "yum", "dnf", "zypper",
            "pacman", "apk", "snap", "flatpak", "npm", "pypi", "cargo", "gem",
            "composer", "nuget", "maven", "gradle", "go", "docker", "helm",
            "nix", "nixpkgs", "guix", "spack", "portage", "emerge", "xbps",
            "slackpkg", "opkg", "pkg"
        ]
        
        # Software names for testing
        self.test_software_names = [
            "nginx", "apache", "mysql", "postgresql", "redis", "mongodb",
            "elasticsearch", "docker", "kubernetes", "jenkins", "gitlab",
            "prometheus", "grafana", "consul", "vault", "terraform",
            "ansible", "puppet", "chef", "saltstack", "zabbix", "nagios",
            "splunk", "logstash", "kibana", "fluentd", "traefik", "haproxy",
            "memcached", "rabbitmq", "kafka", "zookeeper", "etcd"
        ]
        
        # Create comprehensive test templates
        self._create_performance_test_templates()
        
        # Initialize components
        self.template_engine = TemplateEngine(str(self.templates_dir))
        self.metadata_generator = MetadataGenerator(template_engine=self.template_engine)
        
        # Mock AI enhancer for performance tests
        self.mock_ai_enhancer = Mock(spec=AIMetadataEnhancer)
        self.mock_ai_enhancer.is_available.return_value = True
        self.mock_ai_enhancer.enhance_metadata.return_value = AIEnhancementResult(
            enhanced_metadata={"description": "AI-generated description"},
            confidence_scores={"description": 0.9},
            sources_used=["openai-gpt-3.5-turbo"],
            processing_time=0.5,
            success=True
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def _create_performance_test_templates(self):
        """Create templates optimized for performance testing."""
        # Create providers directory
        providers_dir = self.templates_dir / "providers"
        providers_dir.mkdir(exist_ok=True)
        
        # Create comprehensive default template
        default_template = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "$software_name",
                    "version": "latest",
                    "install_options": []
                }
            },
            "services": {
                "default": {
                    "name": "$software_name",
                    "enabled": False,
                    "status": "stopped"
                }
            },
            "directories": {
                "config": {
                    "path": "/etc/$software_name",
                    "owner": "root",
                    "group": "root",
                    "mode": "0755"
                },
                "data": {
                    "path": "/var/lib/$software_name",
                    "owner": "$software_name",
                    "group": "$software_name",
                    "mode": "0750"
                }
            },
            "urls": {
                "website": None,
                "source": None,
                "documentation": None
            },
            "category": {
                "default": None,
                "sub": None,
                "tags": []
            },
            "platforms": ["linux"],
            "ports": [],
            "processes": []
        }
        
        with open(self.templates_dir / "defaults.yaml", "w") as f:
            yaml.dump(default_template, f)
        
        # Create provider templates for all providers
        for provider in self.all_providers:
            provider_template = {
                "version": "0.1",
                "services": {
                    "default": {
                        "enabled": True  # Simple override
                    }
                },
                "urls": {
                    f"{provider}_search": f"https://{provider}.example.com/search?q=$software_name"
                }
            }
            
            # Add provider-specific overrides
            if provider in ["winget", "choco", "scoop"]:
                provider_template["platforms"] = ["windows"]
                provider_template["directories"] = {
                    "config": {
                        "path": f"C:\\ProgramData\\$software_name",
                        "owner": "Administrator"
                    }
                }
            elif provider == "brew":
                provider_template["platforms"] = ["macos", "linux"]
                provider_template["directories"] = {
                    "config": {
                        "path": "/usr/local/etc/$software_name",
                        "owner": "$(whoami)"
                    }
                }
            elif provider in ["npm", "pypi", "cargo", "gem", "composer"]:
                provider_template["platforms"] = ["linux", "macos", "windows"]
                provider_template["directories"] = {
                    "config": {
                        "path": "~/.config/$software_name",
                        "owner": "$(whoami)"
                    }
                }
            
            with open(providers_dir / f"{provider}.yaml", "w") as f:
                yaml.dump(provider_template, f)
    
    def test_template_processing_performance_large_provider_list(self):
        """Test template processing performance with large provider lists."""
        print(f"\\nTesting template processing with {len(self.all_providers)} providers...")
        
        # Measure template loading time
        start_time = time.time()
        template_engine = TemplateEngine(str(self.templates_dir))
        loading_time = time.time() - start_time
        
        print(f"Template loading time: {loading_time:.3f}s")
        self.assertLess(loading_time, 2.0, "Template loading took too long")
        
        # Measure provider override generation for all providers
        software_name = "nginx"
        override_times = []
        
        for provider in self.all_providers:
            start_time = time.time()
            overrides = template_engine.apply_provider_overrides_only(
                software_name=software_name,
                provider=provider
            )
            override_time = time.time() - start_time
            override_times.append(override_time)
            
            # Verify override was generated
            self.assertIsInstance(overrides, dict)
            self.assertEqual(overrides["version"], "0.1")
        
        # Calculate statistics
        total_time = sum(override_times)
        avg_time = total_time / len(override_times)
        max_time = max(override_times)
        
        print(f"Provider override generation:")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Average time per provider: {avg_time:.4f}s")
        print(f"  Maximum time per provider: {max_time:.4f}s")
        
        # Performance assertions
        self.assertLess(total_time, 5.0, "Total override generation took too long")
        self.assertLess(avg_time, 0.1, "Average override generation took too long")
        self.assertLess(max_time, 0.5, "Maximum override generation took too long")
    
    def test_metadata_generation_performance_batch_processing(self):
        """Test metadata generation performance with batch processing."""
        print(f"\\nTesting batch metadata generation for {len(self.test_software_names)} software packages...")
        
        # Create package sources for all test software
        all_sources = []
        for software_name in self.test_software_names:
            sources = [
                PackageInfo(
                    name=software_name,
                    version="1.0.0",
                    provider="apt",
                    description=f"{software_name} package"
                ),
                PackageInfo(
                    name=software_name,
                    version="1.0.0",
                    provider="brew",
                    description=f"{software_name} package"
                )
            ]
            all_sources.append((software_name, sources))
        
        # Measure batch generation time
        start_time = time.time()
        results = []
        
        for software_name, sources in all_sources:
            result = self.metadata_generator.generate_from_sources(
                software_name=software_name,
                sources=sources,
                providers=["apt", "brew", "npm", "docker"]  # Subset for performance
            )
            results.append(result)
        
        batch_time = time.time() - start_time
        
        # Calculate statistics
        avg_time_per_package = batch_time / len(self.test_software_names)
        
        print(f"Batch metadata generation:")
        print(f"  Total time: {batch_time:.3f}s")
        print(f"  Average time per package: {avg_time_per_package:.4f}s")
        print(f"  Packages per second: {len(self.test_software_names) / batch_time:.2f}")
        
        # Verify all results
        self.assertEqual(len(results), len(self.test_software_names))
        for result in results:
            self.assertIsNotNone(result.metadata)
        
        # Performance assertions
        self.assertLess(batch_time, 30.0, "Batch generation took too long")
        self.assertLess(avg_time_per_package, 1.0, "Average generation time per package too long")
    
    @patch('saidata_gen.generator.core.AIMetadataEnhancer')
    def test_ai_enhancement_concurrent_requests(self, mock_ai_class):
        """Test AI enhancement with multiple concurrent requests."""
        print("\\nTesting AI enhancement with concurrent requests...")
        
        # Setup mock AI enhancer
        mock_ai_class.return_value = self.mock_ai_enhancer
        
        # Add artificial delay to simulate AI processing
        def mock_enhance_with_delay(*args, **kwargs):
            time.sleep(0.1)  # Simulate AI processing time
            return self.mock_ai_enhancer.enhance_metadata.return_value
        
        self.mock_ai_enhancer.enhance_metadata.side_effect = mock_enhance_with_delay
        
        # Create test data
        test_packages = self.test_software_names[:10]  # Use subset for concurrent test
        
        def enhance_single_package(software_name):
            """Enhance a single package."""
            sources = [
                PackageInfo(
                    name=software_name,
                    version="1.0.0",
                    provider="apt",
                    description=f"{software_name} package"
                )
            ]
            
            return self.metadata_generator.generate_with_ai_enhancement(
                software_name=software_name,
                sources=sources,
                providers=["apt"],
                ai_provider="openai"
            )
        
        # Test sequential processing
        start_time = time.time()
        sequential_results = []
        for package in test_packages:
            result = enhance_single_package(package)
            sequential_results.append(result)
        sequential_time = time.time() - start_time
        
        # Reset mock call count
        self.mock_ai_enhancer.enhance_metadata.reset_mock()
        self.mock_ai_enhancer.enhance_metadata.side_effect = mock_enhance_with_delay
        
        # Test concurrent processing
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            concurrent_results = list(executor.map(enhance_single_package, test_packages))
        concurrent_time = time.time() - start_time
        
        # Calculate performance improvement
        speedup = sequential_time / concurrent_time if concurrent_time > 0 else 0
        
        print(f"AI enhancement performance:")
        print(f"  Sequential time: {sequential_time:.3f}s")
        print(f"  Concurrent time: {concurrent_time:.3f}s")
        print(f"  Speedup: {speedup:.2f}x")
        
        # Verify results
        self.assertEqual(len(sequential_results), len(test_packages))
        self.assertEqual(len(concurrent_results), len(test_packages))
        
        # Performance assertions
        self.assertGreater(speedup, 2.0, "Concurrent processing should provide significant speedup")
        self.assertLess(concurrent_time, sequential_time * 0.7, "Concurrent processing should be faster")
    
    def test_memory_usage_batch_processing(self):
        """Test memory usage during batch processing operations."""
        if not HAS_PSUTIL:
            self.skipTest("psutil not available for memory testing")
            
        print("\\nTesting memory usage during batch processing...")
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"Initial memory usage: {initial_memory:.2f} MB")
        
        # Process large batch of packages
        large_batch = self.test_software_names * 3  # Triple the test set
        memory_measurements = []
        
        for i, software_name in enumerate(large_batch):
            sources = [
                PackageInfo(
                    name=software_name,
                    version="1.0.0",
                    provider="apt",
                    description=f"{software_name} package"
                )
            ]
            
            # Generate metadata
            result = self.metadata_generator.generate_from_sources(
                software_name=software_name,
                sources=sources,
                providers=["apt", "brew"]
            )
            
            # Measure memory every 10 packages
            if i % 10 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_measurements.append(current_memory)
                
                if i > 0:  # Skip first measurement
                    memory_increase = current_memory - initial_memory
                    print(f"  After {i+1} packages: {current_memory:.2f} MB (+{memory_increase:.2f} MB)")
        
        # Final memory measurement
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - initial_memory
        
        print(f"Final memory usage: {final_memory:.2f} MB")
        print(f"Total memory increase: {total_memory_increase:.2f} MB")
        print(f"Memory per package: {total_memory_increase / len(large_batch):.3f} MB")
        
        # Force garbage collection and measure again
        gc.collect()
        after_gc_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_freed = final_memory - after_gc_memory
        
        print(f"Memory after GC: {after_gc_memory:.2f} MB (freed {memory_freed:.2f} MB)")
        
        # Memory usage assertions
        self.assertLess(total_memory_increase, 500, "Memory usage increased too much")
        self.assertLess(total_memory_increase / len(large_batch), 2.0, "Memory per package too high")
    
    def test_caching_effectiveness_and_performance(self):
        """Test caching effectiveness and performance improvements."""
        print("\\nTesting caching effectiveness and performance...")
        
        # Create template engine with cache
        cache_config = CacheConfig(
            backend=CacheBackend.MEMORY,
            default_ttl=3600,
            max_size=1000
        )
        cache_manager = CacheManager(cache_config)
        cached_template_engine = TemplateEngine(str(self.templates_dir), cache_manager=cache_manager)
        
        # Test provider support caching
        test_software = "nginx"
        test_providers = self.all_providers[:20]  # Use subset for caching test
        
        # First pass - populate cache
        start_time = time.time()
        first_pass_results = []
        for provider in test_providers:
            is_supported = cached_template_engine.is_provider_supported(test_software, provider)
            first_pass_results.append(is_supported)
        first_pass_time = time.time() - start_time
        
        # Second pass - should hit cache
        start_time = time.time()
        second_pass_results = []
        for provider in test_providers:
            is_supported = cached_template_engine.is_provider_supported(test_software, provider)
            second_pass_results.append(is_supported)
        second_pass_time = time.time() - start_time
        
        # Calculate cache performance
        cache_speedup = first_pass_time / second_pass_time if second_pass_time > 0 else 0
        
        print(f"Provider support caching:")
        print(f"  First pass (cache miss): {first_pass_time:.4f}s")
        print(f"  Second pass (cache hit): {second_pass_time:.4f}s")
        print(f"  Cache speedup: {cache_speedup:.2f}x")
        
        # Verify results are consistent
        self.assertEqual(first_pass_results, second_pass_results)
        
        # Get cache statistics
        cache_stats = cached_template_engine.get_provider_support_cache_stats()
        print(f"  Cache stats: {cache_stats}")
        
        # Performance assertions
        self.assertGreater(cache_speedup, 2.0, "Cache should provide significant speedup")
        self.assertLess(second_pass_time, first_pass_time * 0.5, "Cached operations should be much faster")
        
        # Test cache invalidation
        cleared_entries = cached_template_engine.clear_provider_support_cache(test_software)
        print(f"  Cleared {cleared_entries} cache entries")
        
        # Third pass after cache clear - should be slow again
        start_time = time.time()
        third_pass_results = []
        for provider in test_providers:
            is_supported = cached_template_engine.is_provider_supported(test_software, provider)
            third_pass_results.append(is_supported)
        third_pass_time = time.time() - start_time
        
        print(f"  Third pass (after clear): {third_pass_time:.4f}s")
        
        # Should be similar to first pass time
        self.assertAlmostEqual(third_pass_time, first_pass_time, delta=first_pass_time * 0.5)
    
    def test_template_processing_scalability(self):
        """Test template processing scalability with increasing load."""
        print("\\nTesting template processing scalability...")
        
        # Test with increasing numbers of providers
        provider_counts = [5, 10, 20, len(self.all_providers)]
        scalability_results = []
        
        for count in provider_counts:
            providers_subset = self.all_providers[:count]
            
            # Measure processing time
            start_time = time.time()
            
            for software_name in self.test_software_names[:10]:  # Use subset of software
                for provider in providers_subset:
                    overrides = self.template_engine.apply_provider_overrides_only(
                        software_name=software_name,
                        provider=provider
                    )
                    self.assertIsInstance(overrides, dict)
            
            processing_time = time.time() - start_time
            operations = 10 * count  # 10 software * count providers
            ops_per_second = operations / processing_time
            
            scalability_results.append({
                'provider_count': count,
                'processing_time': processing_time,
                'operations': operations,
                'ops_per_second': ops_per_second
            })
            
            print(f"  {count} providers: {processing_time:.3f}s, {ops_per_second:.1f} ops/sec")
        
        # Analyze scalability
        # Check if performance degrades linearly or worse
        for i in range(1, len(scalability_results)):
            prev_result = scalability_results[i-1]
            curr_result = scalability_results[i]
            
            provider_ratio = curr_result['provider_count'] / prev_result['provider_count']
            time_ratio = curr_result['processing_time'] / prev_result['processing_time']
            
            # Time should scale roughly linearly with provider count
            self.assertLess(time_ratio, provider_ratio * 1.5, 
                          f"Performance degraded too much from {prev_result['provider_count']} to {curr_result['provider_count']} providers")
    
    def test_concurrent_template_access(self):
        """Test concurrent access to template engine."""
        print("\\nTesting concurrent template access...")
        
        # Number of concurrent threads
        num_threads = 10
        operations_per_thread = 50
        
        results = []
        errors = []
        
        def worker_thread(thread_id):
            """Worker thread function."""
            thread_results = []
            try:
                for i in range(operations_per_thread):
                    software_name = self.test_software_names[i % len(self.test_software_names)]
                    provider = self.all_providers[i % len(self.all_providers)]
                    
                    # Test provider support check
                    is_supported = self.template_engine.is_provider_supported(software_name, provider)
                    
                    # Test override generation
                    overrides = self.template_engine.apply_provider_overrides_only(
                        software_name=software_name,
                        provider=provider
                    )
                    
                    thread_results.append({
                        'software_name': software_name,
                        'provider': provider,
                        'is_supported': is_supported,
                        'overrides_valid': isinstance(overrides, dict) and 'version' in overrides
                    })
                
                results.extend(thread_results)
                
            except Exception as e:
                errors.append(f"Thread {thread_id}: {str(e)}")
        
        # Start concurrent threads
        threads = []
        start_time = time.time()
        
        for i in range(num_threads):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        concurrent_time = time.time() - start_time
        
        # Analyze results
        total_operations = num_threads * operations_per_thread
        ops_per_second = total_operations / concurrent_time
        
        print(f"Concurrent access test:")
        print(f"  Threads: {num_threads}")
        print(f"  Operations per thread: {operations_per_thread}")
        print(f"  Total operations: {total_operations}")
        print(f"  Total time: {concurrent_time:.3f}s")
        print(f"  Operations per second: {ops_per_second:.1f}")
        print(f"  Errors: {len(errors)}")
        
        # Verify no errors occurred
        if errors:
            print("Errors encountered:")
            for error in errors[:5]:  # Show first 5 errors
                print(f"  {error}")
        
        self.assertEqual(len(errors), 0, "Concurrent access should not produce errors")
        self.assertEqual(len(results), total_operations, "All operations should complete")
        
        # Verify all results are valid
        for result in results:
            self.assertIsInstance(result['is_supported'], bool)
            self.assertTrue(result['overrides_valid'])
        
        # Performance assertion
        self.assertGreater(ops_per_second, 100, "Concurrent operations should maintain good throughput")
    
    def test_memory_leak_detection(self):
        """Test for memory leaks during repeated operations."""
        if not HAS_PSUTIL:
            self.skipTest("psutil not available for memory leak testing")
            
        print("\\nTesting for memory leaks...")
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform many repeated operations
        iterations = 1000
        memory_samples = []
        
        for i in range(iterations):
            # Perform various operations
            software_name = self.test_software_names[i % len(self.test_software_names)]
            provider = self.all_providers[i % len(self.all_providers)]
            
            # Template operations
            is_supported = self.template_engine.is_provider_supported(software_name, provider)
            overrides = self.template_engine.apply_provider_overrides_only(software_name, provider)
            
            # Metadata generation
            sources = [PackageInfo(name=software_name, version="1.0.0", provider=provider)]
            result = self.metadata_generator.generate_from_sources(
                software_name=software_name,
                sources=sources,
                providers=[provider]
            )
            
            # Sample memory every 100 iterations
            if i % 100 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_samples.append(current_memory)
                
                if i > 0:
                    memory_increase = current_memory - initial_memory
                    print(f"  After {i+1} iterations: {current_memory:.2f} MB (+{memory_increase:.2f} MB)")
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_increase = final_memory - initial_memory
        
        print(f"Memory leak test results:")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Total increase: {total_increase:.2f} MB")
        print(f"  Increase per iteration: {total_increase / iterations:.4f} MB")
        
        # Force garbage collection
        gc.collect()
        after_gc_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_freed = final_memory - after_gc_memory
        
        print(f"  Memory after GC: {after_gc_memory:.2f} MB (freed {memory_freed:.2f} MB)")
        
        # Memory leak assertions
        # Allow some memory growth but not excessive
        self.assertLess(total_increase, 100, "Memory increase suggests possible memory leak")
        self.assertLess(total_increase / iterations, 0.1, "Memory increase per iteration too high")
        
        # Check that memory growth is not linear (which would indicate a leak)
        if len(memory_samples) >= 3:
            # Calculate memory growth rate
            early_samples = memory_samples[:3]
            late_samples = memory_samples[-3:]
            
            early_avg = sum(early_samples) / len(early_samples)
            late_avg = sum(late_samples) / len(late_samples)
            
            growth_rate = (late_avg - early_avg) / (len(memory_samples) - 3) * 100
            print(f"  Memory growth rate: {growth_rate:.4f} MB per 100 iterations")
            
            # Growth rate should be minimal
            self.assertLess(abs(growth_rate), 1.0, "Memory growth rate suggests memory leak")


if __name__ == "__main__":
    # Run with verbose output to see performance metrics
    unittest.main(verbosity=2)