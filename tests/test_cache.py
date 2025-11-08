"""Tests for LRU pipeline cache."""

import pytest
from unittest.mock import Mock, MagicMock
from src.core.cache import LRUPipelineCache


class TestLRUPipelineCache:
    """Tests for LRU cache functionality."""

    def test_cache_initialization(self):
        """Test cache initializes with correct capacity."""
        cache = LRUPipelineCache(capacity=5)
        assert cache.capacity == 5
        assert len(cache) == 0

    def test_cache_min_capacity(self):
        """Test cache enforces minimum capacity of 1."""
        cache = LRUPipelineCache(capacity=0)
        assert cache.capacity == 1

    def test_cache_put_and_get(self):
        """Test basic put and get operations."""
        cache = LRUPipelineCache(capacity=3)
        mock_pipeline = Mock()

        cache.put("en->de", mock_pipeline)
        retrieved = cache.get("en->de")

        assert retrieved is mock_pipeline

    def test_cache_get_nonexistent(self):
        """Test getting non-existent key returns None."""
        cache = LRUPipelineCache(capacity=3)
        assert cache.get("en->de") is None

    def test_cache_eviction(self):
        """Test that cache evicts oldest item when at capacity."""
        cache = LRUPipelineCache(capacity=2)

        pipeline1 = Mock()
        pipeline2 = Mock()
        pipeline3 = Mock()

        pipeline1.model = Mock()
        pipeline1.model.cpu = Mock()

        cache.put("en->de", pipeline1)
        cache.put("de->en", pipeline2)
        cache.put("fr->en", pipeline3)  # Should evict en->de

        assert cache.get("en->de") is None  # Evicted
        assert cache.get("de->en") is pipeline2
        assert cache.get("fr->en") is pipeline3

    def test_cache_lru_ordering(self):
        """Test that cache maintains LRU ordering."""
        cache = LRUPipelineCache(capacity=2)

        pipeline1 = Mock()
        pipeline2 = Mock()
        pipeline3 = Mock()

        pipeline1.model = Mock()
        pipeline1.model.cpu = Mock()

        cache.put("en->de", pipeline1)
        cache.put("de->en", pipeline2)

        # Access en->de to make it recently used
        cache.get("en->de")

        # Add new item - should evict de->en (least recently used)
        cache.put("fr->en", pipeline3)

        assert cache.get("en->de") is pipeline1  # Still there
        assert cache.get("de->en") is None  # Evicted
        assert cache.get("fr->en") is pipeline3

    def test_cache_update_existing(self):
        """Test updating existing key."""
        cache = LRUPipelineCache(capacity=3)

        pipeline1 = Mock()
        pipeline2 = Mock()

        cache.put("en->de", pipeline1)
        cache.put("en->de", pipeline2)  # Update

        assert cache.get("en->de") is pipeline2
        assert len(cache) == 1  # Still only one item
