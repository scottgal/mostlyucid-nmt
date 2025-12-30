"""LFU cache for translated text chunks with LRU tiebreaker."""

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import time

from src.core.logging import logger


# Cache key type: (masked_text, src_lang, tgt_lang, model_family, beam_size)
CacheKey = Tuple[str, str, str, str, int]


@dataclass
class ChunkCacheEntry:
    """Entry in the chunk cache."""
    value: str              # Translated text
    frequency: int          # Access count
    created_at: float       # Unix timestamp
    last_accessed: float    # Unix timestamp
    size_bytes: int         # Approximate memory footprint


class LFUChunkCache:
    """LFU cache for translated text chunks with LRU tiebreaker.

    Features:
    - O(1) get/put operations using frequency buckets
    - LFU eviction with LRU tiebreaker for same frequency
    - TTL-based expiration for freshness
    - Batch lookup for efficient cache checking
    - Hit/miss counters for observability
    - Model family invalidation support

    Cache key format: (masked_chunk_text, src_lang, tgt_lang, model_family, beam_size)
    """

    def __init__(self, capacity: int, max_age_seconds: int = 0, max_key_length: int = 1000):
        """Initialize cache.

        Args:
            capacity: Maximum number of entries
            max_age_seconds: TTL for entries (0 = no expiration)
            max_key_length: Skip caching chunks longer than this
        """
        self.capacity = max(1, capacity)
        self.max_age_seconds = max_age_seconds
        self.max_key_length = max_key_length

        # Main storage: key -> ChunkCacheEntry
        self._cache: Dict[CacheKey, ChunkCacheEntry] = {}

        # Frequency buckets: frequency -> OrderedDict of keys (LRU order within frequency)
        # OrderedDict preserves insertion order, so oldest items are first
        self._freq_buckets: Dict[int, OrderedDict] = {}

        # Track minimum frequency for O(1) eviction
        self._min_frequency: int = 0

        # Metrics
        self._hit_count: int = 0
        self._miss_count: int = 0
        self._eviction_count: int = 0

        logger.info(f"LFU chunk cache initialized: capacity={capacity}, max_age={max_age_seconds}s, max_key_len={max_key_length}")

    def _make_key(self, masked_text: str, src: str, tgt: str, model_family: str, beam_size: int) -> CacheKey:
        """Create a cache key tuple."""
        return (masked_text, src, tgt, model_family, beam_size)

    def _is_expired(self, entry: ChunkCacheEntry) -> bool:
        """Check if entry has expired based on TTL."""
        if self.max_age_seconds <= 0:
            return False
        return (time.time() - entry.created_at) > self.max_age_seconds

    def _should_cache(self, key: CacheKey) -> bool:
        """Check if a key should be cached (not too long)."""
        masked_text = key[0]
        return len(masked_text) <= self.max_key_length

    def _remove_from_frequency_bucket(self, key: CacheKey, frequency: int) -> None:
        """Remove a key from its frequency bucket."""
        if frequency in self._freq_buckets:
            bucket = self._freq_buckets[frequency]
            if key in bucket:
                del bucket[key]
            # Clean up empty buckets
            if not bucket:
                del self._freq_buckets[frequency]

    def _add_to_frequency_bucket(self, key: CacheKey, frequency: int) -> None:
        """Add a key to a frequency bucket (at end for LRU ordering)."""
        if frequency not in self._freq_buckets:
            self._freq_buckets[frequency] = OrderedDict()
        self._freq_buckets[frequency][key] = True  # Value doesn't matter, just tracking keys

    def _update_min_frequency(self) -> None:
        """Update min_frequency after eviction or removal."""
        while self._min_frequency not in self._freq_buckets or not self._freq_buckets[self._min_frequency]:
            self._min_frequency += 1
            if self._min_frequency > 1000000:  # Safety limit
                self._min_frequency = 1
                break

    def _evict_one(self) -> Optional[CacheKey]:
        """Evict the least frequently used entry (LRU tiebreaker).

        Returns:
            The evicted key, or None if cache was empty
        """
        if not self._cache:
            return None

        # Find the lowest frequency bucket
        self._update_min_frequency()

        if self._min_frequency not in self._freq_buckets:
            return None

        bucket = self._freq_buckets[self._min_frequency]
        if not bucket:
            return None

        # Pop oldest (LRU) from lowest frequency bucket
        evicted_key, _ = bucket.popitem(last=False)

        # Clean up empty bucket
        if not bucket:
            del self._freq_buckets[self._min_frequency]

        # Remove from main cache
        if evicted_key in self._cache:
            del self._cache[evicted_key]

        self._eviction_count += 1

        # Log eviction (truncate text for readability)
        text_preview = evicted_key[0][:50] + "..." if len(evicted_key[0]) > 50 else evicted_key[0]
        logger.debug(f"LFU evicted: {evicted_key[1]}->{evicted_key[2]} (freq={self._min_frequency}): {text_preview}")

        return evicted_key

    def get(self, key: CacheKey) -> Optional[str]:
        """Get cached translation, incrementing frequency.

        Args:
            key: Cache key tuple

        Returns:
            Cached translation string, or None if not found/expired
        """
        if key not in self._cache:
            self._miss_count += 1
            return None

        entry = self._cache[key]

        # Check TTL
        if self._is_expired(entry):
            self._remove_from_frequency_bucket(key, entry.frequency)
            del self._cache[key]
            self._miss_count += 1
            return None

        # Cache hit - increment frequency
        old_frequency = entry.frequency
        entry.frequency += 1
        entry.last_accessed = time.time()

        # Move to new frequency bucket
        self._remove_from_frequency_bucket(key, old_frequency)
        self._add_to_frequency_bucket(key, entry.frequency)

        # Update min_frequency if needed
        if old_frequency == self._min_frequency and self._min_frequency not in self._freq_buckets:
            self._min_frequency = entry.frequency

        self._hit_count += 1
        return entry.value

    def put(self, key: CacheKey, value: str) -> bool:
        """Store translation in cache.

        If at capacity, evicts least frequently used entry.
        For ties in frequency, evicts least recently used.

        Args:
            key: Cache key tuple
            value: Translated text

        Returns:
            True if stored, False if skipped (too long)
        """
        # Skip if key is too long
        if not self._should_cache(key):
            return False

        now = time.time()
        size_bytes = len(key[0].encode('utf-8')) + len(value.encode('utf-8')) + 100  # Approximate

        # Update existing entry
        if key in self._cache:
            entry = self._cache[key]
            old_frequency = entry.frequency
            entry.value = value
            entry.frequency += 1
            entry.last_accessed = now
            entry.size_bytes = size_bytes

            # Move to new frequency bucket
            self._remove_from_frequency_bucket(key, old_frequency)
            self._add_to_frequency_bucket(key, entry.frequency)
            return True

        # Evict if at capacity
        while len(self._cache) >= self.capacity:
            self._evict_one()

        # Add new entry with frequency 1
        entry = ChunkCacheEntry(
            value=value,
            frequency=1,
            created_at=now,
            last_accessed=now,
            size_bytes=size_bytes
        )
        self._cache[key] = entry
        self._add_to_frequency_bucket(key, 1)

        # New entries have frequency 1, which is the new minimum
        self._min_frequency = 1

        return True

    def get_batch(self, keys: List[CacheKey]) -> Dict[int, str]:
        """Batch lookup for multiple keys.

        Args:
            keys: List of cache key tuples

        Returns:
            Dict mapping input index to cached translation.
            Indices not in result indicate cache misses.
        """
        results = {}
        for i, key in enumerate(keys):
            value = self.get(key)
            if value is not None:
                results[i] = value
        return results

    def evict_expired(self) -> int:
        """Remove entries older than max_age_seconds.

        Returns:
            Count of evicted entries
        """
        if self.max_age_seconds <= 0:
            return 0

        expired_keys = []
        for key, entry in self._cache.items():
            if self._is_expired(entry):
                expired_keys.append((key, entry.frequency))

        for key, frequency in expired_keys:
            self._remove_from_frequency_bucket(key, frequency)
            del self._cache[key]

        if expired_keys:
            logger.info(f"LFU TTL sweep: evicted {len(expired_keys)} expired chunks")

        return len(expired_keys)

    def invalidate_by_model(self, model_family: str) -> int:
        """Invalidate all entries for a specific model family.

        Args:
            model_family: Model family to invalidate (e.g., "opus-mt", "mbart50")

        Returns:
            Count of invalidated entries
        """
        keys_to_remove = []
        for key, entry in self._cache.items():
            if key[3] == model_family:  # key[3] is model_family
                keys_to_remove.append((key, entry.frequency))

        for key, frequency in keys_to_remove:
            self._remove_from_frequency_bucket(key, frequency)
            del self._cache[key]

        if keys_to_remove:
            logger.info(f"LFU invalidated {len(keys_to_remove)} chunks for model family: {model_family}")

        return len(keys_to_remove)

    def invalidate_by_lang_pair(self, src: str, tgt: str) -> int:
        """Invalidate all entries for a specific language pair.

        Args:
            src: Source language code
            tgt: Target language code

        Returns:
            Count of invalidated entries
        """
        keys_to_remove = []
        for key, entry in self._cache.items():
            if key[1] == src and key[2] == tgt:  # key[1] is src, key[2] is tgt
                keys_to_remove.append((key, entry.frequency))

        for key, frequency in keys_to_remove:
            self._remove_from_frequency_bucket(key, frequency)
            del self._cache[key]

        if keys_to_remove:
            logger.info(f"LFU invalidated {len(keys_to_remove)} chunks for lang pair: {src}->{tgt}")

        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cached entries."""
        count = len(self._cache)
        self._cache.clear()
        self._freq_buckets.clear()
        self._min_frequency = 0
        logger.info(f"LFU chunk cache cleared: {count} entries removed")

    def get_status(self) -> dict:
        """Return cache statistics for observability.

        Returns:
            Dictionary with cache metrics
        """
        total_requests = self._hit_count + self._miss_count
        hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0.0

        # Calculate average frequency
        total_frequency = sum(entry.frequency for entry in self._cache.values())
        avg_frequency = (total_frequency / len(self._cache)) if self._cache else 0.0

        # Calculate memory estimate
        total_size_bytes = sum(entry.size_bytes for entry in self._cache.values())
        memory_mb = total_size_bytes / (1024 * 1024)

        # Find oldest entry age
        oldest_age = None
        if self._cache:
            oldest_created = min(entry.created_at for entry in self._cache.values())
            oldest_age = time.time() - oldest_created

        # Frequency distribution (top 5 frequencies)
        freq_dist = {}
        for entry in self._cache.values():
            freq_dist[entry.frequency] = freq_dist.get(entry.frequency, 0) + 1
        top_freqs = sorted(freq_dist.items(), key=lambda x: -x[1])[:5]

        return {
            "enabled": True,
            "capacity": self.capacity,
            "size": len(self._cache),
            "utilization": f"{len(self._cache)}/{self.capacity} ({int(len(self._cache)/self.capacity*100) if self.capacity > 0 else 0}%)",
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": round(hit_rate, 2),
            "eviction_count": self._eviction_count,
            "avg_frequency": round(avg_frequency, 2),
            "memory_estimate_mb": round(memory_mb, 2),
            "oldest_entry_age_seconds": round(oldest_age, 1) if oldest_age else None,
            "max_age_seconds": self.max_age_seconds,
            "max_key_length": self.max_key_length,
            "frequency_distribution": dict(top_freqs)
        }


# Module-level singleton instance (lazy initialization)
_chunk_cache: Optional[LFUChunkCache] = None


def get_chunk_cache() -> Optional[LFUChunkCache]:
    """Get the singleton chunk cache instance.

    Returns:
        LFUChunkCache instance if enabled, None otherwise
    """
    global _chunk_cache

    from src.config import config

    if not config.CHUNK_CACHE_ENABLED:
        return None

    if _chunk_cache is None:
        _chunk_cache = LFUChunkCache(
            capacity=config.CHUNK_CACHE_CAPACITY,
            max_age_seconds=config.CHUNK_CACHE_MAX_AGE,
            max_key_length=config.CHUNK_CACHE_MAX_KEY_LENGTH
        )

    return _chunk_cache


def get_chunk_cache_status() -> dict:
    """Get chunk cache status for observability endpoint.

    Returns:
        Cache status dict, or disabled status if cache is off
    """
    from src.config import config

    if not config.CHUNK_CACHE_ENABLED:
        return {
            "enabled": False,
            "message": "Chunk cache is disabled (set CHUNK_CACHE_ENABLED=1 to enable)"
        }

    cache = get_chunk_cache()
    if cache is None:
        return {"enabled": False, "message": "Cache not initialized"}

    return cache.get_status()
