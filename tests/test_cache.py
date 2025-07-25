"""
Unit tests for the caching system.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from saidata_gen.core.cache import (
    CacheBackend,
    CacheConfig,
    CacheEntry,
    CacheManager,
    CacheStats,
    FilesystemCacheStorage,
    MemoryCacheStorage,
    SQLiteCacheStorage,
    cached,
    create_cache_manager,
)


class TestCacheEntry(unittest.TestCase):
    """Test CacheEntry functionality."""
    
    def test_cache_entry_creation(self):
        """Test cache entry creation."""
        entry = CacheEntry(
            key="test_key",
            data={"test": "data"},
            created_at=time.time(),
            ttl=3600
        )
        
        self.assertEqual(entry.key, "test_key")
        self.assertEqual(entry.data, {"test": "data"})
        self.assertEqual(entry.ttl, 3600)
        self.assertEqual(entry.access_count, 0)
        self.assertFalse(entry.is_expired)
    
    def test_cache_entry_expiration(self):
        """Test cache entry expiration."""
        # Create expired entry
        entry = CacheEntry(
            key="test_key",
            data={"test": "data"},
            created_at=time.time() - 7200,  # 2 hours ago
            ttl=3600  # 1 hour TTL
        )
        
        self.assertTrue(entry.is_expired)
    
    def test_cache_entry_touch(self):
        """Test cache entry touch functionality."""
        entry = CacheEntry(
            key="test_key",
            data={"test": "data"},
            created_at=time.time(),
            ttl=3600
        )
        
        initial_access_count = entry.access_count
        initial_last_accessed = entry.last_accessed
        
        time.sleep(0.01)  # Small delay
        entry.touch()
        
        self.assertEqual(entry.access_count, initial_access_count + 1)
        self.assertGreater(entry.last_accessed, initial_last_accessed)


class TestMemoryCacheStorage(unittest.TestCase):
    """Test MemoryCacheStorage functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = CacheConfig(backend=CacheBackend.MEMORY, max_size=10)
        self.storage = MemoryCacheStorage(self.config)
    
    def test_put_and_get(self):
        """Test storing and retrieving cache entries."""
        entry = CacheEntry(
            key="test_key",
            data={"test": "data"},
            created_at=time.time(),
            ttl=3600
        )
        
        self.storage.put(entry)
        retrieved = self.storage.get("test_key")
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.key, "test_key")
        self.assertEqual(retrieved.data, {"test": "data"})
        self.assertEqual(retrieved.access_count, 1)  # Should be touched
    
    def test_get_nonexistent(self):
        """Test retrieving non-existent cache entry."""
        result = self.storage.get("nonexistent_key")
        self.assertIsNone(result)
    
    def test_get_expired(self):
        """Test retrieving expired cache entry."""
        entry = CacheEntry(
            key="expired_key",
            data={"test": "data"},
            created_at=time.time() - 7200,  # 2 hours ago
            ttl=3600  # 1 hour TTL
        )
        
        self.storage.put(entry)
        result = self.storage.get("expired_key")
        
        self.assertIsNone(result)
        self.assertEqual(self.storage.size(), 0)  # Should be removed
    
    def test_delete(self):
        """Test deleting cache entries."""
        entry = CacheEntry(
            key="test_key",
            data={"test": "data"},
            created_at=time.time(),
            ttl=3600
        )
        
        self.storage.put(entry)
        self.assertEqual(self.storage.size(), 1)
        
        result = self.storage.delete("test_key")
        self.assertTrue(result)
        self.assertEqual(self.storage.size(), 0)
        
        # Try to delete again
        result = self.storage.delete("test_key")
        self.assertFalse(result)
    
    def test_clear(self):
        """Test clearing all cache entries."""
        for i in range(5):
            entry = CacheEntry(
                key=f"key_{i}",
                data={"test": f"data_{i}"},
                created_at=time.time(),
                ttl=3600
            )
            self.storage.put(entry)
        
        self.assertEqual(self.storage.size(), 5)
        
        self.storage.clear()
        self.assertEqual(self.storage.size(), 0)
    
    def test_keys(self):
        """Test getting all cache keys."""
        keys = ["key_1", "key_2", "key_3"]
        
        for key in keys:
            entry = CacheEntry(
                key=key,
                data={"test": "data"},
                created_at=time.time(),
                ttl=3600
            )
            self.storage.put(entry)
        
        retrieved_keys = self.storage.keys()
        self.assertEqual(set(retrieved_keys), set(keys))
    
    def test_size_limit_enforcement(self):
        """Test that size limits are enforced."""
        # Add more entries than the limit
        for i in range(15):
            entry = CacheEntry(
                key=f"key_{i}",
                data={"test": f"data_{i}"},
                created_at=time.time(),
                ttl=3600
            )
            # Add small delay to ensure different access times
            if i > 0:
                time.sleep(0.001)
            self.storage.put(entry)
        
        # Should not exceed max_size
        self.assertLessEqual(self.storage.size(), self.config.max_size)


class TestFilesystemCacheStorage(unittest.TestCase):
    """Test FilesystemCacheStorage functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = CacheConfig(
            backend=CacheBackend.FILESYSTEM,
            cache_dir=self.temp_dir,
            compression=False  # Disable compression for easier testing
        )
        self.storage = FilesystemCacheStorage(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_put_and_get(self):
        """Test storing and retrieving cache entries."""
        entry = CacheEntry(
            key="test_key",
            data={"test": "data"},
            created_at=time.time(),
            ttl=3600
        )
        
        self.storage.put(entry)
        retrieved = self.storage.get("test_key")
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.key, "test_key")
        self.assertEqual(retrieved.data, {"test": "data"})
    
    def test_get_nonexistent(self):
        """Test retrieving non-existent cache entry."""
        result = self.storage.get("nonexistent_key")
        self.assertIsNone(result)
    
    def test_get_expired(self):
        """Test retrieving expired cache entry."""
        entry = CacheEntry(
            key="expired_key",
            data={"test": "data"},
            created_at=time.time() - 7200,  # 2 hours ago
            ttl=3600  # 1 hour TTL
        )
        
        self.storage.put(entry)
        result = self.storage.get("expired_key")
        
        self.assertIsNone(result)
        # File should be removed
        cache_path = self.storage._get_cache_path("expired_key")
        self.assertFalse(cache_path.exists())
    
    def test_delete(self):
        """Test deleting cache entries."""
        entry = CacheEntry(
            key="test_key",
            data={"test": "data"},
            created_at=time.time(),
            ttl=3600
        )
        
        self.storage.put(entry)
        cache_path = self.storage._get_cache_path("test_key")
        self.assertTrue(cache_path.exists())
        
        result = self.storage.delete("test_key")
        self.assertTrue(result)
        self.assertFalse(cache_path.exists())
        
        # Try to delete again
        result = self.storage.delete("test_key")
        self.assertFalse(result)
    
    def test_clear(self):
        """Test clearing all cache entries."""
        for i in range(5):
            entry = CacheEntry(
                key=f"key_{i}",
                data={"test": f"data_{i}"},
                created_at=time.time(),
                ttl=3600
            )
            self.storage.put(entry)
        
        # Verify files exist
        cache_files = list(Path(self.temp_dir).glob("*.cache"))
        self.assertEqual(len(cache_files), 5)
        
        self.storage.clear()
        
        # Verify files are removed
        cache_files = list(Path(self.temp_dir).glob("*.cache"))
        self.assertEqual(len(cache_files), 0)
    
    def test_compression(self):
        """Test compression functionality."""
        config = CacheConfig(
            backend=CacheBackend.FILESYSTEM,
            cache_dir=self.temp_dir,
            compression=True
        )
        storage = FilesystemCacheStorage(config)
        
        entry = CacheEntry(
            key="test_key",
            data={"test": "data" * 1000},  # Larger data for compression
            created_at=time.time(),
            ttl=3600
        )
        
        storage.put(entry)
        retrieved = storage.get("test_key")
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.data, entry.data)


class TestSQLiteCacheStorage(unittest.TestCase):
    """Test SQLiteCacheStorage functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = CacheConfig(
            backend=CacheBackend.SQLITE,
            cache_dir=self.temp_dir,
            max_size=10,
            compression=False
        )
        self.storage = SQLiteCacheStorage(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_put_and_get(self):
        """Test storing and retrieving cache entries."""
        entry = CacheEntry(
            key="test_key",
            data={"test": "data"},
            created_at=time.time(),
            ttl=3600
        )
        
        self.storage.put(entry)
        retrieved = self.storage.get("test_key")
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.key, "test_key")
        self.assertEqual(retrieved.data, {"test": "data"})
    
    def test_get_nonexistent(self):
        """Test retrieving non-existent cache entry."""
        result = self.storage.get("nonexistent_key")
        self.assertIsNone(result)
    
    def test_get_expired(self):
        """Test retrieving expired cache entry."""
        entry = CacheEntry(
            key="expired_key",
            data={"test": "data"},
            created_at=time.time() - 7200,  # 2 hours ago
            ttl=3600  # 1 hour TTL
        )
        
        self.storage.put(entry)
        result = self.storage.get("expired_key")
        
        self.assertIsNone(result)
        self.assertEqual(self.storage.size(), 0)  # Should be removed
    
    def test_delete(self):
        """Test deleting cache entries."""
        entry = CacheEntry(
            key="test_key",
            data={"test": "data"},
            created_at=time.time(),
            ttl=3600
        )
        
        self.storage.put(entry)
        self.assertEqual(self.storage.size(), 1)
        
        result = self.storage.delete("test_key")
        self.assertTrue(result)
        self.assertEqual(self.storage.size(), 0)
        
        # Try to delete again
        result = self.storage.delete("test_key")
        self.assertFalse(result)
    
    def test_clear(self):
        """Test clearing all cache entries."""
        for i in range(5):
            entry = CacheEntry(
                key=f"key_{i}",
                data={"test": f"data_{i}"},
                created_at=time.time(),
                ttl=3600
            )
            self.storage.put(entry)
        
        self.assertEqual(self.storage.size(), 5)
        
        self.storage.clear()
        self.assertEqual(self.storage.size(), 0)
    
    def test_size_limit_enforcement(self):
        """Test that size limits are enforced."""
        # Add more entries than the limit
        for i in range(15):
            entry = CacheEntry(
                key=f"key_{i}",
                data={"test": f"data_{i}"},
                created_at=time.time(),
                ttl=3600
            )
            # Add small delay to ensure different access times
            if i > 0:
                time.sleep(0.001)
            self.storage.put(entry)
        
        # Should not exceed max_size
        self.assertLessEqual(self.storage.size(), self.config.max_size)


class TestCacheManager(unittest.TestCase):
    """Test CacheManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = CacheConfig(
            backend=CacheBackend.MEMORY,
            cache_dir=self.temp_dir,
            cleanup_interval=0,  # Disable automatic cleanup for testing
            enable_stats=True
        )
        self.cache_manager = CacheManager(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.cache_manager.shutdown()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_put_and_get(self):
        """Test storing and retrieving data."""
        data = {"test": "data"}
        self.cache_manager.put("test_key", data)
        
        retrieved = self.cache_manager.get("test_key")
        self.assertEqual(retrieved, data)
    
    def test_get_nonexistent(self):
        """Test retrieving non-existent data."""
        result = self.cache_manager.get("nonexistent_key")
        self.assertIsNone(result)
    
    def test_delete(self):
        """Test deleting cache entries."""
        self.cache_manager.put("test_key", {"test": "data"})
        
        result = self.cache_manager.delete("test_key")
        self.assertTrue(result)
        
        retrieved = self.cache_manager.get("test_key")
        self.assertIsNone(retrieved)
    
    def test_clear(self):
        """Test clearing all cache entries."""
        for i in range(5):
            self.cache_manager.put(f"key_{i}", {"test": f"data_{i}"})
        
        self.cache_manager.clear()
        
        for i in range(5):
            result = self.cache_manager.get(f"key_{i}")
            self.assertIsNone(result)
    
    def test_invalidate_pattern(self):
        """Test pattern-based cache invalidation."""
        # Add various keys
        self.cache_manager.put("user:123", {"name": "John"})
        self.cache_manager.put("user:456", {"name": "Jane"})
        self.cache_manager.put("product:789", {"name": "Widget"})
        
        # Invalidate user keys
        invalidated = self.cache_manager.invalidate_pattern("user:*")
        self.assertEqual(invalidated, 2)
        
        # Check that user keys are gone but product key remains
        self.assertIsNone(self.cache_manager.get("user:123"))
        self.assertIsNone(self.cache_manager.get("user:456"))
        self.assertIsNotNone(self.cache_manager.get("product:789"))
    
    def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        # Add expired entry
        self.cache_manager.put("expired_key", {"test": "data"}, ttl=1)
        time.sleep(1.1)  # Wait for expiration
        
        # Add non-expired entry
        self.cache_manager.put("valid_key", {"test": "data"}, ttl=3600)
        
        cleaned = self.cache_manager.cleanup_expired()
        self.assertEqual(cleaned, 1)
        
        # Check that expired entry is gone but valid entry remains
        self.assertIsNone(self.cache_manager.get("expired_key"))
        self.assertIsNotNone(self.cache_manager.get("valid_key"))
    
    def test_stats(self):
        """Test cache statistics."""
        # Generate some hits and misses
        self.cache_manager.put("test_key", {"test": "data"})
        
        # Hit
        self.cache_manager.get("test_key")
        
        # Miss
        self.cache_manager.get("nonexistent_key")
        
        stats = self.cache_manager.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)
        self.assertEqual(stats.hit_rate, 0.5)
    
    def test_get_info(self):
        """Test getting cache information."""
        info = self.cache_manager.get_info()
        
        self.assertIn("backend", info)
        self.assertIn("cache_dir", info)
        self.assertIn("stats", info)
        self.assertEqual(info["backend"], "memory")
    
    def test_context_manager(self):
        """Test using cache manager as context manager."""
        with CacheManager(self.config) as cache:
            cache.put("test_key", {"test": "data"})
            result = cache.get("test_key")
            self.assertEqual(result, {"test": "data"})


class TestCacheDecorator(unittest.TestCase):
    """Test cache decorator functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = CacheConfig(backend=CacheBackend.MEMORY)
        self.cache_manager = CacheManager(self.config)
        self.call_count = 0
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.cache_manager.shutdown()
    
    def test_cached_decorator(self):
        """Test the cached decorator."""
        @cached(self.cache_manager)
        def expensive_function(x, y):
            self.call_count += 1
            return x + y
        
        # First call should execute the function
        result1 = expensive_function(1, 2)
        self.assertEqual(result1, 3)
        self.assertEqual(self.call_count, 1)
        
        # Second call should use cache
        result2 = expensive_function(1, 2)
        self.assertEqual(result2, 3)
        self.assertEqual(self.call_count, 1)  # Should not increment
        
        # Different arguments should execute the function again
        result3 = expensive_function(2, 3)
        self.assertEqual(result3, 5)
        self.assertEqual(self.call_count, 2)
    
    def test_cached_decorator_with_custom_key(self):
        """Test the cached decorator with custom key function."""
        def key_func(x, y):
            return f"custom:{x}:{y}"
        
        @cached(self.cache_manager, key_func=key_func)
        def expensive_function(x, y):
            self.call_count += 1
            return x * y
        
        # First call
        result1 = expensive_function(2, 3)
        self.assertEqual(result1, 6)
        self.assertEqual(self.call_count, 1)
        
        # Check that custom key is used
        cached_result = self.cache_manager.get("custom:2:3")
        self.assertEqual(cached_result, 6)
        
        # Second call should use cache
        result2 = expensive_function(2, 3)
        self.assertEqual(result2, 6)
        self.assertEqual(self.call_count, 1)


class TestCacheUtilities(unittest.TestCase):
    """Test cache utility functions."""
    
    def test_create_cache_manager(self):
        """Test create_cache_manager utility function."""
        cache_manager = create_cache_manager(
            backend="memory",
            default_ttl=1800,
            max_size=500
        )
        
        self.assertEqual(cache_manager.config.backend, CacheBackend.MEMORY)
        self.assertEqual(cache_manager.config.default_ttl, 1800)
        self.assertEqual(cache_manager.config.max_size, 500)
        
        cache_manager.shutdown()
    
    def test_create_cache_manager_with_enum(self):
        """Test create_cache_manager with enum backend."""
        cache_manager = create_cache_manager(
            backend=CacheBackend.FILESYSTEM,
            compression=True
        )
        
        self.assertEqual(cache_manager.config.backend, CacheBackend.FILESYSTEM)
        self.assertTrue(cache_manager.config.compression)
        
        cache_manager.shutdown()


if __name__ == "__main__":
    unittest.main()