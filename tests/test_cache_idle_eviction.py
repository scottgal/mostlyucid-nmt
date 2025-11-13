"""Tests for time-based (idle) cache eviction."""

import time
import pytest
from unittest.mock import Mock
from src.core.cache import LRUPipelineCache


@pytest.mark.unit
def test_idle_eviction_disabled():
    """Test that idle eviction does nothing when timeout is 0."""
    cache = LRUPipelineCache(capacity=3)

    # Add some items
    cache.put("en->de", Mock())
    cache.put("en->fr", Mock())

    # Try to evict with timeout=0 (disabled)
    evicted = cache.evict_idle_models(timeout_seconds=0)

    assert evicted == []
    assert len(cache) == 2


@pytest.mark.unit
def test_idle_eviction_no_idle_models():
    """Test that recently accessed models are not evicted."""
    cache = LRUPipelineCache(capacity=3)

    # Add some items
    cache.put("en->de", Mock())
    cache.put("en->fr", Mock())

    # Try to evict with very short timeout, but models are fresh
    evicted = cache.evict_idle_models(timeout_seconds=10)

    assert evicted == []
    assert len(cache) == 2


@pytest.mark.unit
def test_idle_eviction_removes_old_models():
    """Test that idle models are evicted after timeout."""
    cache = LRUPipelineCache(capacity=3)

    # Add items and manually set old access times
    mock1 = Mock()
    mock2 = Mock()
    mock3 = Mock()

    cache.put("en->de", mock1)
    cache.put("en->fr", mock2)
    cache.put("en->es", mock3)

    # Manually set access times to simulate old models
    current_time = time.time()
    cache.last_access_times["en->de"] = current_time - 120  # 2 minutes ago
    cache.last_access_times["en->fr"] = current_time - 30   # 30 seconds ago (fresh)
    cache.last_access_times["en->es"] = current_time - 90   # 90 seconds ago

    # Evict models idle for more than 60 seconds
    evicted = cache.evict_idle_models(timeout_seconds=60)

    # Should evict en->de and en->es (both over 60s old)
    assert len(evicted) == 2
    assert "en->de" in evicted
    assert "en->es" in evicted

    # Only en->fr should remain
    assert len(cache) == 1
    assert "en->fr" in cache
    assert "en->de" not in cache
    assert "en->es" not in cache


@pytest.mark.unit
def test_idle_eviction_cleans_up_access_times():
    """Test that access time tracking is cleaned up after eviction."""
    cache = LRUPipelineCache(capacity=3)

    mock1 = Mock()
    cache.put("en->de", mock1)

    # Set old access time
    cache.last_access_times["en->de"] = time.time() - 120

    # Evict
    evicted = cache.evict_idle_models(timeout_seconds=60)

    assert "en->de" in evicted
    assert "en->de" not in cache.last_access_times


@pytest.mark.unit
def test_idle_eviction_updates_on_get():
    """Test that accessing a model updates its last access time."""
    cache = LRUPipelineCache(capacity=3)

    mock1 = Mock()
    cache.put("en->de", mock1)

    # Set old access time
    old_time = time.time() - 120
    cache.last_access_times["en->de"] = old_time

    # Access the model
    result = cache.get("en->de")
    assert result is not None

    # Access time should be updated (newer than old_time)
    assert cache.last_access_times["en->de"] > old_time

    # Model should not be evicted now
    evicted = cache.evict_idle_models(timeout_seconds=60)
    assert "en->de" not in evicted


@pytest.mark.unit
def test_idle_eviction_with_lru_eviction():
    """Test that idle and LRU eviction work together."""
    cache = LRUPipelineCache(capacity=2)

    mock1 = Mock()
    mock2 = Mock()
    mock3 = Mock()

    # Add two models
    cache.put("en->de", mock1)
    cache.put("en->fr", mock2)

    # Make en->de old
    cache.last_access_times["en->de"] = time.time() - 120

    # Evict idle models (should remove en->de)
    evicted = cache.evict_idle_models(timeout_seconds=60)
    assert "en->de" in evicted
    assert len(cache) == 1

    # Now add two more models (should trigger LRU eviction)
    cache.put("en->es", mock1)
    cache.put("de->en", mock3)

    # Cache should have en->es and de->en (en->fr evicted by LRU)
    assert len(cache) == 2
    assert "en->es" in cache
    assert "de->en" in cache
    assert "en->fr" not in cache


@pytest.mark.unit
def test_idle_eviction_empty_cache():
    """Test that evicting from empty cache doesn't error."""
    cache = LRUPipelineCache(capacity=3)

    evicted = cache.evict_idle_models(timeout_seconds=60)

    assert evicted == []
    assert len(cache) == 0
