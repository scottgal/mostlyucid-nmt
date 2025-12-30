"""Tests for LFU chunk translation cache."""

import pytest
import time
from src.core.chunk_cache import LFUChunkCache


class TestLFUChunkCache:
    """Tests for LFU chunk cache functionality."""

    def test_cache_initialization(self):
        """Test cache initializes with correct capacity."""
        cache = LFUChunkCache(capacity=5)
        assert cache.capacity == 5
        assert len(cache._cache) == 0

    def test_cache_min_capacity(self):
        """Test cache enforces minimum capacity of 1."""
        cache = LFUChunkCache(capacity=0)
        assert cache.capacity == 1

    def test_cache_put_and_get(self):
        """Test basic put and get operations."""
        cache = LFUChunkCache(capacity=10)
        key = ("Hello world", "en", "de", "opus-mt", 5)

        cache.put(key, "Hallo Welt")
        result = cache.get(key)

        assert result == "Hallo Welt"

    def test_cache_get_nonexistent(self):
        """Test getting non-existent key returns None."""
        cache = LFUChunkCache(capacity=10)
        key = ("Hello world", "en", "de", "opus-mt", 5)

        assert cache.get(key) is None

    def test_lfu_eviction_basic(self):
        """Test that least frequently used item is evicted."""
        cache = LFUChunkCache(capacity=2)

        key1 = ("Hello", "en", "de", "opus-mt", 5)
        key2 = ("World", "en", "de", "opus-mt", 5)
        key3 = ("Test", "en", "de", "opus-mt", 5)

        cache.put(key1, "Hallo")
        cache.put(key2, "Welt")

        # Access key1 multiple times to increase its frequency
        cache.get(key1)
        cache.get(key1)

        # Add key3 - should evict key2 (lower frequency)
        cache.put(key3, "Test")

        assert cache.get(key1) == "Hallo"  # Still there (freq=4)
        assert cache.get(key2) is None  # Evicted (freq=1)
        assert cache.get(key3) == "Test"  # Just added

    def test_lfu_eviction_lru_tiebreaker(self):
        """Test that LRU is used when frequencies are equal."""
        cache = LFUChunkCache(capacity=2)

        key1 = ("Hello", "en", "de", "opus-mt", 5)
        key2 = ("World", "en", "de", "opus-mt", 5)
        key3 = ("Test", "en", "de", "opus-mt", 5)

        cache.put(key1, "Hallo")
        cache.put(key2, "Welt")

        # Both have frequency 1, key1 is older
        # Add key3 - should evict key1 (older with same frequency)
        cache.put(key3, "Test")

        assert cache.get(key1) is None  # Evicted (oldest with freq=1)
        assert cache.get(key2) == "Welt"  # Still there
        assert cache.get(key3) == "Test"  # Just added

    def test_frequency_increment_on_get(self):
        """Test that frequency increases on cache hits."""
        cache = LFUChunkCache(capacity=10)
        key = ("Hello", "en", "de", "opus-mt", 5)

        cache.put(key, "Hallo")
        assert cache._cache[key].frequency == 1

        cache.get(key)
        assert cache._cache[key].frequency == 2

        cache.get(key)
        assert cache._cache[key].frequency == 3

    def test_get_batch_all_hits(self):
        """Test batch lookup with all cache hits."""
        cache = LFUChunkCache(capacity=10)

        keys = [
            ("Hello", "en", "de", "opus-mt", 5),
            ("World", "en", "de", "opus-mt", 5),
            ("Test", "en", "de", "opus-mt", 5),
        ]

        cache.put(keys[0], "Hallo")
        cache.put(keys[1], "Welt")
        cache.put(keys[2], "Test")

        results = cache.get_batch(keys)

        assert len(results) == 3
        assert results[0] == "Hallo"
        assert results[1] == "Welt"
        assert results[2] == "Test"

    def test_get_batch_all_misses(self):
        """Test batch lookup with all cache misses."""
        cache = LFUChunkCache(capacity=10)

        keys = [
            ("Hello", "en", "de", "opus-mt", 5),
            ("World", "en", "de", "opus-mt", 5),
        ]

        results = cache.get_batch(keys)

        assert len(results) == 0

    def test_get_batch_mixed(self):
        """Test batch lookup with mix of hits and misses."""
        cache = LFUChunkCache(capacity=10)

        keys = [
            ("Hello", "en", "de", "opus-mt", 5),
            ("World", "en", "de", "opus-mt", 5),
            ("Test", "en", "de", "opus-mt", 5),
        ]

        cache.put(keys[0], "Hallo")
        cache.put(keys[2], "Test")

        results = cache.get_batch(keys)

        assert len(results) == 2
        assert results[0] == "Hallo"
        assert 1 not in results  # Miss
        assert results[2] == "Test"

    def test_ttl_expiration(self):
        """Test that old entries are expired correctly."""
        cache = LFUChunkCache(capacity=10, max_age_seconds=1)
        key = ("Hello", "en", "de", "opus-mt", 5)

        cache.put(key, "Hallo")
        assert cache.get(key) == "Hallo"

        # Wait for expiration
        time.sleep(1.1)

        assert cache.get(key) is None

    def test_evict_expired(self):
        """Test manual TTL sweep."""
        cache = LFUChunkCache(capacity=10, max_age_seconds=1)

        keys = [
            ("Hello", "en", "de", "opus-mt", 5),
            ("World", "en", "de", "opus-mt", 5),
        ]

        cache.put(keys[0], "Hallo")
        cache.put(keys[1], "Welt")

        # Wait for expiration
        time.sleep(1.1)

        evicted = cache.evict_expired()

        assert evicted == 2
        assert len(cache._cache) == 0

    def test_invalidate_by_model(self):
        """Test selective invalidation by model family."""
        cache = LFUChunkCache(capacity=10)

        key1 = ("Hello", "en", "de", "opus-mt", 5)
        key2 = ("World", "en", "de", "opus-mt", 5)
        key3 = ("Test", "en", "de", "mbart50", 5)

        cache.put(key1, "Hallo")
        cache.put(key2, "Welt")
        cache.put(key3, "Test")

        invalidated = cache.invalidate_by_model("opus-mt")

        assert invalidated == 2
        assert cache.get(key1) is None
        assert cache.get(key2) is None
        assert cache.get(key3) == "Test"

    def test_invalidate_by_lang_pair(self):
        """Test selective invalidation by language pair."""
        cache = LFUChunkCache(capacity=10)

        key1 = ("Hello", "en", "de", "opus-mt", 5)
        key2 = ("World", "en", "de", "opus-mt", 5)
        key3 = ("Test", "en", "fr", "opus-mt", 5)

        cache.put(key1, "Hallo")
        cache.put(key2, "Welt")
        cache.put(key3, "Test")

        invalidated = cache.invalidate_by_lang_pair("en", "de")

        assert invalidated == 2
        assert cache.get(key1) is None
        assert cache.get(key2) is None
        assert cache.get(key3) == "Test"

    def test_get_status(self):
        """Test status reporting."""
        cache = LFUChunkCache(capacity=10)

        key1 = ("Hello", "en", "de", "opus-mt", 5)
        key2 = ("World", "en", "de", "opus-mt", 5)

        cache.put(key1, "Hallo")
        cache.put(key2, "Welt")
        cache.get(key1)  # 1 hit

        status = cache.get_status()

        assert status["enabled"] is True
        assert status["capacity"] == 10
        assert status["size"] == 2
        assert status["hit_count"] == 1
        assert status["miss_count"] == 0
        assert status["eviction_count"] == 0

    def test_clear(self):
        """Test cache clearing."""
        cache = LFUChunkCache(capacity=10)

        key1 = ("Hello", "en", "de", "opus-mt", 5)
        key2 = ("World", "en", "de", "opus-mt", 5)

        cache.put(key1, "Hallo")
        cache.put(key2, "Welt")

        cache.clear()

        assert len(cache._cache) == 0
        assert cache.get(key1) is None
        assert cache.get(key2) is None

    def test_skip_long_chunks(self):
        """Test that very long chunks are not cached."""
        cache = LFUChunkCache(capacity=10, max_key_length=10)

        short_key = ("Hello", "en", "de", "opus-mt", 5)
        long_key = ("This is a very long text that exceeds the max key length", "en", "de", "opus-mt", 5)

        assert cache.put(short_key, "Hallo") is True
        assert cache.put(long_key, "Long translation") is False

        assert cache.get(short_key) == "Hallo"
        assert cache.get(long_key) is None

    def test_different_beam_sizes_separate_entries(self):
        """Test that different beam sizes create separate cache entries."""
        cache = LFUChunkCache(capacity=10)

        key_beam5 = ("Hello", "en", "de", "opus-mt", 5)
        key_beam3 = ("Hello", "en", "de", "opus-mt", 3)

        cache.put(key_beam5, "Hallo (beam 5)")
        cache.put(key_beam3, "Hallo (beam 3)")

        assert cache.get(key_beam5) == "Hallo (beam 5)"
        assert cache.get(key_beam3) == "Hallo (beam 3)"
        assert len(cache._cache) == 2

    def test_different_model_families_separate_entries(self):
        """Test that different model families create separate cache entries."""
        cache = LFUChunkCache(capacity=10)

        key_opus = ("Hello", "en", "de", "opus-mt", 5)
        key_mbart = ("Hello", "en", "de", "mbart50", 5)

        cache.put(key_opus, "Hallo (opus)")
        cache.put(key_mbart, "Hallo (mbart)")

        assert cache.get(key_opus) == "Hallo (opus)"
        assert cache.get(key_mbart) == "Hallo (mbart)"
        assert len(cache._cache) == 2

    def test_different_lang_pairs_separate_entries(self):
        """Test that different language pairs create separate cache entries."""
        cache = LFUChunkCache(capacity=10)

        key_de = ("Hello", "en", "de", "opus-mt", 5)
        key_fr = ("Hello", "en", "fr", "opus-mt", 5)

        cache.put(key_de, "Hallo")
        cache.put(key_fr, "Bonjour")

        assert cache.get(key_de) == "Hallo"
        assert cache.get(key_fr) == "Bonjour"
        assert len(cache._cache) == 2

    def test_hit_miss_counters(self):
        """Test that hit/miss counters are tracked correctly."""
        cache = LFUChunkCache(capacity=10)

        key1 = ("Hello", "en", "de", "opus-mt", 5)
        key2 = ("World", "en", "de", "opus-mt", 5)

        cache.put(key1, "Hallo")

        # 2 hits
        cache.get(key1)
        cache.get(key1)

        # 2 misses
        cache.get(key2)
        cache.get(key2)

        status = cache.get_status()
        assert status["hit_count"] == 2
        assert status["miss_count"] == 2
        assert status["hit_rate"] == 50.0

    def test_memory_estimate(self):
        """Test memory estimation in status."""
        cache = LFUChunkCache(capacity=10)

        # Add enough data to have measurable memory (small chunks round to 0)
        for i in range(100):
            key = (f"Hello world, this is test number {i} with some extra text", "en", "de", "opus-mt", 5)
            cache.put(key, f"Hallo Welt, das ist Test Nummer {i} mit etwas extra Text")

        status = cache.get_status()
        assert status["memory_estimate_mb"] >= 0  # At least non-negative
        assert "memory_estimate_mb" in status  # Field exists

    def test_frequency_distribution(self):
        """Test frequency distribution in status."""
        cache = LFUChunkCache(capacity=10)

        key1 = ("Hello", "en", "de", "opus-mt", 5)
        key2 = ("World", "en", "de", "opus-mt", 5)

        cache.put(key1, "Hallo")
        cache.put(key2, "Welt")

        # Access key1 twice more (total freq = 3)
        cache.get(key1)
        cache.get(key1)

        status = cache.get_status()
        assert 3 in status["frequency_distribution"]  # key1
        assert 1 in status["frequency_distribution"]  # key2
