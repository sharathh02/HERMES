"""
Hermes In-Memory Cache Client
Provides key-value caching with TTL expiration, evictions, and statistics tracking.
"""

import time
from typing import Any, Dict, Optional


class CacheEntry:
    """Represents a single cached item with expiration timestamp."""

    def __init__(self, value: Any, ttl: Optional[float] = None):
        self.value = value
        self.expires_at = time.time() + ttl if ttl is not None else None

    def is_expired(self) -> bool:
        """Returns True if this entry has surpassed its time-to-live."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class MemoryCache:
    """Simple, thread-safe in-memory cache supporting TTL and hit/miss statistics."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._store: Dict[str, CacheEntry] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve value by key. Evicts entry if expired.

        Args:
            key: Cache lookup key.
            default: Fallback value if missing or expired.

        Returns:
            Cached value or default.
        """
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return default

        if entry.is_expired():
            del self._store[key]
            self.misses += 1
            return default

        self.hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """
        Store a value in cache with optional TTL in seconds.

        Args:
            key: Storage key.
            value: Any Python object to cache.
            ttl: Lifetime in seconds.

        Returns:
            True if stored successfully.
        """
        if len(self._store) >= self.max_size and key not in self._store:
            # Evict oldest entry
            oldest_key = next(iter(self._store))
            del self._store[oldest_key]

        self._store[key] = CacheEntry(value, ttl)
        return True

    def delete(self, key: str) -> bool:
        """
        Remove key from cache if present.

        Returns:
            True if key was removed, False if not found.
        """
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """Remove all entries from the cache."""
        self._store.clear()

    def stats(self) -> Dict[str, Any]:
        """
        Returns cache utilization and hit ratio.
        """
        total = self.hits + self.misses
        hit_ratio = (self.hits / total) if total > 0 else 0.0
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": round(hit_ratio, 3),
        }
