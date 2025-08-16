"""
Intelligent caching system for saidata-gen.

This module provides a comprehensive caching system with configurable TTL,
multiple storage backends, and intelligent cache management.
"""

import hashlib
import json
import logging
import os
import pickle
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum

logger = logging.getLogger(__name__)


class CacheBackend(Enum):
    """Supported cache storage backends."""
    FILESYSTEM = "filesystem"
    SQLITE = "sqlite"
    MEMORY = "memory"


@dataclass
class CacheConfig:
    """Configuration for the cache system."""
    backend: CacheBackend = CacheBackend.FILESYSTEM
    cache_dir: str = "~/.saidata-gen/cache"
    default_ttl: int = 3600  # 1 hour
    max_size: int = 1000  # Maximum number of entries
    cleanup_interval: int = 300  # 5 minutes
    compression: bool = True
    enable_stats: bool = True


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    data: Any
    created_at: float
    ttl: int
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.created_at > self.ttl
    
    def touch(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = time.time()


class CacheStorage(ABC):
    """Abstract base class for cache storage backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cache entry by key."""
        pass
    
    @abstractmethod
    def put(self, entry: CacheEntry) -> None:
        """Store a cache entry."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a cache entry by key."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""
        pass
    
    @abstractmethod
    def keys(self) -> List[str]:
        """Get all cache keys."""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get the number of cache entries."""
        pass


class MemoryCacheStorage(CacheStorage):
    """In-memory cache storage backend."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cache entry by key."""
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired:
                entry.touch()
                return entry
            elif entry:
                # Remove expired entry
                del self._cache[key]
            return None
    
    def put(self, entry: CacheEntry) -> None:
        """Store a cache entry."""
        with self._lock:
            self._cache[entry.key] = entry
            self._enforce_size_limit()
    
    def delete(self, key: str) -> bool:
        """Delete a cache entry by key."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
    
    def keys(self) -> List[str]:
        """Get all cache keys."""
        with self._lock:
            return list(self._cache.keys())
    
    def size(self) -> int:
        """Get the number of cache entries."""
        with self._lock:
            return len(self._cache)
    
    def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self._cache.items():
                if (current_time - entry.created_at) > entry.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
            
            return len(expired_keys)
    
    def _enforce_size_limit(self) -> None:
        """Enforce maximum cache size by evicting LRU entries."""
        if len(self._cache) <= self.config.max_size:
            return
        
        # Sort by last accessed time (LRU)
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        # Remove oldest entries
        entries_to_remove = len(self._cache) - self.config.max_size
        for key, _ in sorted_entries[:entries_to_remove]:
            del self._cache[key]


class FilesystemCacheStorage(CacheStorage):
    """Filesystem-based cache storage backend."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache_dir = Path(os.path.expanduser(config.cache_dir))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
    
    def _get_cache_path(self, key: str) -> Path:
        """Get the filesystem path for a cache key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def _serialize_entry(self, entry: CacheEntry) -> bytes:
        """Serialize a cache entry to bytes."""
        if self.config.compression:
            import gzip
            return gzip.compress(pickle.dumps(entry))
        return pickle.dumps(entry)
    
    def _deserialize_entry(self, data: bytes) -> CacheEntry:
        """Deserialize a cache entry from bytes."""
        if self.config.compression:
            import gzip
            return pickle.loads(gzip.decompress(data))
        return pickle.loads(data)
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cache entry by key."""
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            with self._lock:
                with open(cache_path, 'rb') as f:
                    entry = self._deserialize_entry(f.read())
                
                if entry.is_expired:
                    cache_path.unlink(missing_ok=True)
                    return None
                
                entry.touch()
                # Update the file with new access stats
                with open(cache_path, 'wb') as f:
                    f.write(self._serialize_entry(entry))
                
                return entry
        except Exception as e:
            logger.warning(f"Failed to read cache entry {key}: {e}")
            cache_path.unlink(missing_ok=True)
            return None
    
    def put(self, entry: CacheEntry) -> None:
        """Store a cache entry."""
        cache_path = self._get_cache_path(entry.key)
        
        try:
            with self._lock:
                with open(cache_path, 'wb') as f:
                    f.write(self._serialize_entry(entry))
        except Exception as e:
            logger.warning(f"Failed to write cache entry {entry.key}: {e}")
    
    def delete(self, key: str) -> bool:
        """Delete a cache entry by key."""
        cache_path = self._get_cache_path(key)
        
        try:
            with self._lock:
                if cache_path.exists():
                    cache_path.unlink()
                    return True
                return False
        except Exception as e:
            logger.warning(f"Failed to delete cache entry {key}: {e}")
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        try:
            with self._lock:
                for cache_file in self.cache_dir.glob("*.cache"):
                    cache_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to clear cache: {e}")
    
    def keys(self) -> List[str]:
        """Get all cache keys."""
        keys = []
        try:
            with self._lock:
                for cache_file in self.cache_dir.glob("*.cache"):
                    try:
                        with open(cache_file, 'rb') as f:
                            entry = self._deserialize_entry(f.read())
                            if not entry.is_expired:
                                keys.append(entry.key)
                            else:
                                cache_file.unlink(missing_ok=True)
                    except Exception:
                        cache_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to list cache keys: {e}")
        
        return keys
    
    def size(self) -> int:
        """Get the number of cache entries."""
        return len(self.keys())
    
    def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        current_time = time.time()
        cleaned = 0
        
        try:
            with self._lock:
                for cache_file in self.cache_dir.glob("*.cache"):
                    try:
                        with open(cache_file, 'rb') as f:
                            entry = self._deserialize_entry(f.read())
                            if (current_time - entry.created_at) > entry.ttl:
                                cache_file.unlink()
                                cleaned += 1
                    except Exception:
                        cache_file.unlink(missing_ok=True)
                        cleaned += 1
        except Exception as e:
            logger.warning(f"Failed to cleanup expired entries: {e}")
        
        return cleaned


class SQLiteCacheStorage(CacheStorage):
    """SQLite-based cache storage backend."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache_dir = Path(os.path.expanduser(config.cache_dir))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "cache.db"
        self._lock = threading.RLock()
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        key TEXT PRIMARY KEY,
                        data BLOB,
                        created_at REAL,
                        ttl INTEGER,
                        access_count INTEGER,
                        last_accessed REAL,
                        size INTEGER
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at ON cache_entries(created_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_last_accessed ON cache_entries(last_accessed)
                """)
                conn.commit()
            finally:
                conn.close()
    
    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data to bytes."""
        if self.config.compression:
            import gzip
            return gzip.compress(pickle.dumps(data))
        return pickle.dumps(data)
    
    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize data from bytes."""
        if self.config.compression:
            import gzip
            return pickle.loads(gzip.decompress(data))
        return pickle.loads(data)
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cache entry by key."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    "SELECT * FROM cache_entries WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                entry = CacheEntry(
                    key=row[0],
                    data=self._deserialize_data(row[1]),
                    created_at=row[2],
                    ttl=row[3],
                    access_count=row[4],
                    last_accessed=row[5],
                    size=row[6]
                )
                
                if entry.is_expired:
                    conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    conn.commit()
                    return None
                
                # Update access stats
                entry.touch()
                conn.execute(
                    "UPDATE cache_entries SET access_count = ?, last_accessed = ? WHERE key = ?",
                    (entry.access_count, entry.last_accessed, key)
                )
                conn.commit()
                
                return entry
            finally:
                conn.close()
    
    def put(self, entry: CacheEntry) -> None:
        """Store a cache entry."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                serialized_data = self._serialize_data(entry.data)
                entry.size = len(serialized_data)
                
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries 
                    (key, data, created_at, ttl, access_count, last_accessed, size)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.key,
                        serialized_data,
                        entry.created_at,
                        entry.ttl,
                        entry.access_count,
                        entry.last_accessed,
                        entry.size
                    )
                )
                conn.commit()
                self._enforce_size_limit(conn)
            finally:
                conn.close()
    
    def delete(self, key: str) -> bool:
        """Delete a cache entry by key."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("DELETE FROM cache_entries")
                conn.commit()
            finally:
                conn.close()
    
    def keys(self) -> List[str]:
        """Get all cache keys."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                # Clean up expired entries first
                current_time = time.time()
                conn.execute(
                    "DELETE FROM cache_entries WHERE (? - created_at) > ttl",
                    (current_time,)
                )
                conn.commit()
                
                cursor = conn.execute("SELECT key FROM cache_entries")
                return [row[0] for row in cursor.fetchall()]
            finally:
                conn.close()
    
    def size(self) -> int:
        """Get the number of cache entries."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM cache_entries")
                return cursor.fetchone()[0]
            finally:
                conn.close()
    
    def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                current_time = time.time()
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM cache_entries WHERE (? - created_at) > ttl",
                    (current_time,)
                )
                expired_count = cursor.fetchone()[0]
                
                conn.execute(
                    "DELETE FROM cache_entries WHERE (? - created_at) > ttl",
                    (current_time,)
                )
                conn.commit()
                
                return expired_count
            finally:
                conn.close()
    
    def _enforce_size_limit(self, conn: sqlite3.Connection) -> None:
        """Enforce maximum cache size by evicting LRU entries."""
        cursor = conn.execute("SELECT COUNT(*) FROM cache_entries")
        current_size = cursor.fetchone()[0]
        
        if current_size <= self.config.max_size:
            return
        
        # Remove oldest entries by last accessed time
        entries_to_remove = current_size - self.config.max_size
        conn.execute(
            """
            DELETE FROM cache_entries WHERE key IN (
                SELECT key FROM cache_entries 
                ORDER BY last_accessed ASC 
                LIMIT ?
            )
            """,
            (entries_to_remove,)
        )
        conn.commit()


class CacheManager:
    """
    Intelligent cache manager with configurable TTL and storage backends.
    
    Provides multi-level caching for repository data, API responses, and generated metadata
    with cache invalidation and cleanup mechanisms.
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize the cache manager.
        
        Args:
            config: Cache configuration. If None, uses default configuration.
        """
        self.config = config or CacheConfig()
        self.stats = CacheStats()
        self._storage = self._create_storage()
        self._cleanup_thread = None
        self._shutdown = False
        
        # Optional performance monitor integration
        self._performance_monitor = None
        
        if self.config.cleanup_interval > 0:
            self._start_cleanup_thread()
    
    def _create_storage(self) -> CacheStorage:
        """Create the appropriate storage backend."""
        if self.config.backend == CacheBackend.MEMORY:
            return MemoryCacheStorage(self.config)
        elif self.config.backend == CacheBackend.SQLITE:
            return SQLiteCacheStorage(self.config)
        else:  # FILESYSTEM
            return FilesystemCacheStorage(self.config)
    
    def _start_cleanup_thread(self) -> None:
        """Start the background cleanup thread."""
        import threading
        
        def cleanup_worker():
            while not self._shutdown:
                try:
                    self.cleanup_expired()
                    time.sleep(self.config.cleanup_interval)
                except Exception as e:
                    logger.warning(f"Cache cleanup error: {e}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get data from the cache.
        
        Args:
            key: Cache key.
            
        Returns:
            Cached data if available and valid, None otherwise.
        """
        entry = self._storage.get(key)
        
        if entry:
            if self.config.enable_stats:
                self.stats.hits += 1
            # Report cache hit to performance monitor if available
            if self._performance_monitor:
                self._performance_monitor.increment_counter("cache_hits", 1.0, {"cache_key": key})
            return entry.data
        else:
            if self.config.enable_stats:
                self.stats.misses += 1
            # Report cache miss to performance monitor if available
            if self._performance_monitor:
                self._performance_monitor.increment_counter("cache_misses", 1.0, {"cache_key": key})
            return None
    
    def put(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """
        Store data in the cache.
        
        Args:
            key: Cache key.
            data: Data to cache.
            ttl: Time to live in seconds. If None, uses default TTL.
        """
        ttl = ttl or self.config.default_ttl
        
        entry = CacheEntry(
            key=key,
            data=data,
            created_at=time.time(),
            ttl=ttl
        )
        
        self._storage.put(entry)
        
        if self.config.enable_stats:
            self.stats.size = self._storage.size()
    
    def delete(self, key: str) -> bool:
        """
        Delete a cache entry.
        
        Args:
            key: Cache key.
            
        Returns:
            True if the entry was deleted, False if it didn't exist.
        """
        result = self._storage.delete(key)
        
        if self.config.enable_stats:
            self.stats.size = self._storage.size()
        
        return result
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._storage.clear()
        
        if self.config.enable_stats:
            self.stats = CacheStats()
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match against cache keys (supports * wildcards).
            
        Returns:
            Number of entries invalidated.
        """
        import fnmatch
        
        keys = self._storage.keys()
        invalidated = 0
        
        for key in keys:
            if fnmatch.fnmatch(key, pattern):
                if self._storage.delete(key):
                    invalidated += 1
        
        if self.config.enable_stats:
            self.stats.size = self._storage.size()
            self.stats.evictions += invalidated
        
        return invalidated
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired cache entries.
        
        Returns:
            Number of entries cleaned up.
        """
        if hasattr(self._storage, 'cleanup_expired'):
            # Storage backend supports direct cleanup
            return self._storage.cleanup_expired()
        
        # Fallback: manual cleanup
        keys = self._storage.keys()
        cleaned = 0
        current_time = time.time()
        
        for key in keys:
            if hasattr(self._storage, '_cache'):  # Memory storage
                entry = self._storage._cache.get(key)
                if entry and (current_time - entry.created_at) > entry.ttl:
                    if self._storage.delete(key):
                        cleaned += 1
            else:
                # For other storage types, check if entry exists after get()
                original_size = self._storage.size()
                self._storage.get(key)  # This will remove expired entries
                new_size = self._storage.size()
                if new_size < original_size:
                    cleaned += (original_size - new_size)
        
        if self.config.enable_stats:
            self.stats.size = self._storage.size()
            self.stats.evictions += cleaned
        
        return cleaned
    
    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.
        
        Returns:
            Current cache statistics.
        """
        if self.config.enable_stats:
            self.stats.size = self._storage.size()
        
        return self.stats
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get detailed cache information.
        
        Returns:
            Dictionary with cache information.
        """
        stats = self.get_stats()
        
        return {
            "backend": self.config.backend.value,
            "cache_dir": self.config.cache_dir,
            "default_ttl": self.config.default_ttl,
            "max_size": self.config.max_size,
            "compression": self.config.compression,
            "stats": {
                "hits": stats.hits,
                "misses": stats.misses,
                "hit_rate": stats.hit_rate,
                "evictions": stats.evictions,
                "size": stats.size,
            }
        }
    
    def shutdown(self) -> None:
        """Shutdown the cache manager and cleanup resources."""
        self._shutdown = True
        
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5.0)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()
    
    def set_performance_monitor(self, monitor) -> None:
        """
        Set performance monitor for cache metrics integration.
        
        Args:
            monitor: Performance monitor instance.
        """
        self._performance_monitor = monitor


# Convenience functions for common cache operations
def create_cache_manager(
    backend: Union[str, CacheBackend] = CacheBackend.FILESYSTEM,
    cache_dir: str = "~/.saidata-gen/cache",
    default_ttl: int = 3600,
    **kwargs
) -> CacheManager:
    """
    Create a cache manager with common configuration.
    
    Args:
        backend: Cache backend to use.
        cache_dir: Directory for cache storage.
        default_ttl: Default time to live in seconds.
        **kwargs: Additional configuration options.
        
    Returns:
        Configured cache manager.
    """
    if isinstance(backend, str):
        backend = CacheBackend(backend)
    
    config = CacheConfig(
        backend=backend,
        cache_dir=cache_dir,
        default_ttl=default_ttl,
        **kwargs
    )
    
    return CacheManager(config)


# Cache decorators for easy integration
def cached(
    cache_manager: CacheManager,
    key_func: Optional[callable] = None,
    ttl: Optional[int] = None
):
    """
    Decorator to cache function results.
    
    Args:
        cache_manager: Cache manager to use.
        key_func: Function to generate cache key from arguments.
        ttl: Time to live for cached results.
        
    Returns:
        Decorated function.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)
            
            # Try to get from cache
            result = cache_manager.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.put(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator