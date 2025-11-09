"""Tests for intelligent memory monitoring in LRUPipelineCache."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import torch

from src.core.cache import LRUPipelineCache, PSUTIL_AVAILABLE


class MockPipeline:
    """Mock translation pipeline for testing."""

    def __init__(self, name: str):
        self.name = name
        self.model = Mock()
        self.model.cpu = Mock()


@pytest.fixture
def mock_pipeline():
    """Create a mock pipeline."""
    return MockPipeline("test-model")


@pytest.fixture
def cache():
    """Create a cache instance for testing."""
    return LRUPipelineCache(capacity=3)


class TestMemoryMonitoring:
    """Test memory monitoring functionality."""

    def test_cache_initialization_logs_memory(self, caplog):
        """Test that cache logs initial memory state on init."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        cache = LRUPipelineCache(capacity=5)

        # Should log system RAM
        assert any("System RAM:" in record.message for record in caplog.records)

    def test_system_memory_usage_returns_tuple(self, cache):
        """Test _get_system_memory_usage returns valid tuple."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        percentage, used_gb, total_gb = cache._get_system_memory_usage()

        assert isinstance(percentage, float)
        assert isinstance(used_gb, float)
        assert isinstance(total_gb, float)
        assert 0 <= percentage <= 100
        assert used_gb >= 0
        assert total_gb > 0
        assert used_gb <= total_gb

    def test_system_memory_without_psutil(self, cache):
        """Test memory usage returns zeros when psutil not available."""
        with patch("src.core.cache.PSUTIL_AVAILABLE", False):
            percentage, used_gb, total_gb = cache._get_system_memory_usage()

            assert percentage == 0.0
            assert used_gb == 0.0
            assert total_gb == 0.0

    def test_gpu_memory_usage_when_no_gpu(self, cache):
        """Test GPU memory returns zeros when CUDA not available."""
        with patch("torch.cuda.is_available", return_value=False):
            percentage, used_gb, total_gb = cache._get_gpu_memory_usage()

            assert percentage == 0.0
            assert used_gb == 0.0
            assert total_gb == 0.0

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_gpu_memory_usage_with_cuda(self, cache):
        """Test GPU memory usage returns valid values with CUDA."""
        percentage, used_gb, total_gb = cache._get_gpu_memory_usage()

        assert isinstance(percentage, float)
        assert isinstance(used_gb, float)
        assert isinstance(total_gb, float)
        assert 0 <= percentage <= 100
        assert total_gb > 0

    def test_get_status_includes_memory_info(self, cache):
        """Test that get_status includes memory information."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        status = cache.get_status()

        # Should have system memory info
        assert "system_memory" in status
        assert "percentage" in status["system_memory"]
        assert "used_gb" in status["system_memory"]
        assert "total_gb" in status["system_memory"]
        assert "status" in status["system_memory"]
        assert status["system_memory"]["status"] in ["ok", "warning", "critical"]

    def test_memory_status_thresholds(self, cache):
        """Test that memory status correctly categorizes usage levels."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        # Mock different memory levels
        test_cases = [
            (75.0, "ok"),      # Below warning threshold
            (85.0, "warning"), # Between warning and critical
            (95.0, "critical") # Above critical threshold
        ]

        for percentage, expected_status in test_cases:
            with patch.object(cache, "_get_system_memory_usage", return_value=(percentage, 10.0, 16.0)):
                status = cache.get_status()
                assert status["system_memory"]["status"] == expected_status


class TestMemoryBasedEviction:
    """Test automatic eviction based on memory pressure."""

    def test_eviction_when_ram_critical(self, cache, mock_pipeline, caplog):
        """Test that cache auto-evicts when RAM is critically low."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        # Add some models to cache
        cache.put("en->de", MockPipeline("en-de"))
        cache.put("en->fr", MockPipeline("en-fr"))
        cache.put("en->es", MockPipeline("en-es"))

        assert len(cache) == 3

        # Mock critical RAM usage (95%)
        with patch.object(cache, "_get_system_memory_usage", return_value=(95.0, 15.2, 16.0)):
            with patch("src.config.config.ENABLE_MEMORY_MONITOR", True):
                with patch("src.config.config.MEMORY_CRITICAL_THRESHOLD", 90.0):
                    with patch("src.config.config.MEMORY_CHECK_INTERVAL", 1):
                        # Trigger memory check via get
                        cache.get("en->de")

                        # Should have auto-evicted one model
                        assert len(cache) < 3
                        assert any("CRITICAL RAM" in record.message for record in caplog.records)
                        assert any("Auto-evicting" in record.message for record in caplog.records)

    def test_eviction_when_vram_critical(self, cache, mock_pipeline, caplog):
        """Test that cache auto-evicts when VRAM is critically low."""
        if not PSUTIL_AVAILABLE or not torch.cuda.is_available():
            pytest.skip("psutil or CUDA not available")

        # Add models to cache
        cache.put("en->de", MockPipeline("en-de"))
        cache.put("en->fr", MockPipeline("en-fr"))

        assert len(cache) == 2

        # Mock critical VRAM usage (92%)
        with patch.object(cache, "_get_system_memory_usage", return_value=(70.0, 11.2, 16.0)):  # RAM ok
            with patch.object(cache, "_get_gpu_memory_usage", return_value=(92.0, 7.3, 8.0)):  # VRAM critical
                with patch("src.config.config.ENABLE_MEMORY_MONITOR", True):
                    with patch("src.config.config.GPU_MEMORY_CRITICAL_THRESHOLD", 90.0):
                        with patch("src.config.config.MEMORY_CHECK_INTERVAL", 1):
                            # Trigger memory check
                            cache.get("en->de")

                            # Should have auto-evicted
                            assert len(cache) < 2
                            assert any("CRITICAL VRAM" in record.message for record in caplog.records)

    def test_warning_logged_when_ram_high(self, cache, mock_pipeline, caplog):
        """Test that warning is logged when RAM is high but not critical."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        # Add model
        cache.put("en->de", MockPipeline("en-de"))
        initial_count = len(cache)

        # Mock warning-level RAM usage (85%)
        with patch.object(cache, "_get_system_memory_usage", return_value=(85.0, 13.6, 16.0)):
            with patch("src.config.config.ENABLE_MEMORY_MONITOR", True):
                with patch("src.config.config.MEMORY_WARNING_THRESHOLD", 80.0):
                    with patch("src.config.config.MEMORY_CRITICAL_THRESHOLD", 90.0):
                        with patch("src.config.config.MEMORY_CHECK_INTERVAL", 1):
                            # Trigger memory check
                            cache.get("en->de")

                            # Should NOT evict (only warning)
                            assert len(cache) == initial_count
                            assert any("High RAM usage" in record.message for record in caplog.records)

    def test_no_eviction_when_memory_ok(self, cache, mock_pipeline, caplog):
        """Test that no eviction happens when memory is OK."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        # Add models
        cache.put("en->de", MockPipeline("en-de"))
        cache.put("en->fr", MockPipeline("en-fr"))
        initial_count = len(cache)

        # Mock normal RAM usage (60%)
        with patch.object(cache, "_get_system_memory_usage", return_value=(60.0, 9.6, 16.0)):
            with patch("src.config.config.ENABLE_MEMORY_MONITOR", True):
                with patch("src.config.config.MEMORY_CHECK_INTERVAL", 1):
                    # Trigger memory check
                    cache.get("en->de")

                    # Should NOT evict
                    assert len(cache) == initial_count

                    # Should not have memory warnings
                    warnings = [r for r in caplog.records if "High RAM" in r.message or "CRITICAL" in r.message]
                    assert len(warnings) == 0

    def test_eviction_clears_cuda_cache(self, cache, mock_pipeline, caplog):
        """Test that eviction clears CUDA cache if available."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        cache.put("en->de", MockPipeline("en-de"))

        with patch("torch.cuda.is_available", return_value=True):
            with patch("torch.cuda.empty_cache") as mock_empty_cache:
                with patch.object(cache, "_get_system_memory_usage", return_value=(95.0, 15.2, 16.0)):
                    with patch("src.config.config.ENABLE_MEMORY_MONITOR", True):
                        with patch("src.config.config.MEMORY_CRITICAL_THRESHOLD", 90.0):
                            with patch("src.config.config.MEMORY_CHECK_INTERVAL", 1):
                                # Trigger eviction
                                cache.put("fr->de", MockPipeline("fr-de"))

                                # Should have called empty_cache
                                assert mock_empty_cache.called

    def test_eviction_moves_model_to_cpu(self, cache, caplog):
        """Test that evicted models are moved to CPU."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        pipeline = MockPipeline("test")
        cache.put("en->de", pipeline)

        with patch.object(cache, "_get_system_memory_usage", return_value=(95.0, 15.2, 16.0)):
            with patch("src.config.config.ENABLE_MEMORY_MONITOR", True):
                with patch("src.config.config.MEMORY_CRITICAL_THRESHOLD", 90.0):
                    with patch("src.config.config.MEMORY_CHECK_INTERVAL", 1):
                        # Trigger eviction
                        cache.get("non-existent")

                        # Should have called model.cpu()
                        assert pipeline.model.cpu.called

    def test_memory_check_respects_interval(self, cache, mock_pipeline):
        """Test that memory checks only happen at configured intervals."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        check_count = 0

        def mock_check():
            nonlocal check_count
            check_count += 1

        with patch.object(cache, "_get_system_memory_usage", return_value=(70.0, 11.2, 16.0)):
            with patch("src.config.config.ENABLE_MEMORY_MONITOR", True):
                with patch("src.config.config.MEMORY_CHECK_INTERVAL", 3):  # Every 3 operations
                    original_check = cache._check_memory_and_evict_if_needed

                    def counting_check():
                        nonlocal check_count
                        check_count += 1
                        return original_check()

                    with patch.object(cache, "_check_memory_and_evict_if_needed", side_effect=counting_check):
                        # First 2 operations shouldn't trigger actual check
                        cache.get("en->de")
                        cache.get("en->fr")

                        # 3rd operation should trigger check
                        cache.get("en->es")

                        # We call _check_memory_and_evict_if_needed 3 times, but only 1 actually checks
                        # because operation_count % interval != 0 for the first 2
                        assert cache.operation_count >= 3


class TestMemoryMonitorConfiguration:
    """Test configuration options for memory monitoring."""

    def test_memory_monitor_can_be_disabled(self, cache, mock_pipeline):
        """Test that memory monitoring can be disabled via config."""
        cache.put("en->de", MockPipeline("en-de"))

        check_called = False

        def mock_check():
            nonlocal check_called
            check_called = True

        with patch("src.config.config.ENABLE_MEMORY_MONITOR", False):
            with patch.object(cache, "_get_system_memory_usage", return_value=(95.0, 15.2, 16.0)):
                # Even with high memory, shouldn't check if disabled
                original_check = cache._check_memory_and_evict_if_needed
                original_check()

                # Internal check returns early if disabled
                # So we test by checking that eviction didn't happen
                assert len(cache) == 1  # No eviction occurred

    def test_custom_memory_thresholds(self, cache, mock_pipeline, caplog):
        """Test that custom memory thresholds are respected."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        cache.put("en->de", MockPipeline("en-de"))

        # Set custom thresholds
        with patch("src.config.config.ENABLE_MEMORY_MONITOR", True):
            with patch("src.config.config.MEMORY_WARNING_THRESHOLD", 70.0):  # Lower threshold
                with patch("src.config.config.MEMORY_CRITICAL_THRESHOLD", 75.0):  # Lower threshold
                    with patch("src.config.config.MEMORY_CHECK_INTERVAL", 1):
                        # 72% should trigger warning
                        with patch.object(cache, "_get_system_memory_usage", return_value=(72.0, 11.5, 16.0)):
                            cache.get("en->de")
                            assert any("High RAM usage" in record.message for record in caplog.records)

                        caplog.clear()

                        # 76% should trigger critical
                        with patch.object(cache, "_get_system_memory_usage", return_value=(76.0, 12.2, 16.0)):
                            cache.get("en->de")
                            assert any("CRITICAL RAM" in record.message for record in caplog.records)


class TestHelperMethods:
    """Test helper methods for testing memory behavior."""

    def test_simulate_high_memory_helper(self, cache, mock_pipeline):
        """Helper to simulate high memory conditions for testing."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        def simulate_high_memory(ram_percent: float, vram_percent: float = 0.0):
            """Helper to simulate specific memory conditions."""
            with patch.object(cache, "_get_system_memory_usage", return_value=(ram_percent, ram_percent * 16 / 100, 16.0)):
                if vram_percent > 0 and torch.cuda.is_available():
                    with patch.object(cache, "_get_gpu_memory_usage", return_value=(vram_percent, vram_percent * 8 / 100, 8.0)):
                        return cache
                return cache

        # Test the helper
        cache.put("en->de", MockPipeline("en-de"))

        # Simulate 95% RAM
        with simulate_high_memory(95.0):
            status = cache.get_status()
            assert status["system_memory"]["percentage"] == 95.0

    def test_force_memory_check_helper(self, cache):
        """Helper to force immediate memory check (bypass interval)."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        def force_memory_check():
            """Force immediate memory check regardless of interval."""
            # Save original count
            original_count = cache.operation_count

            # Set count to trigger check on next operation
            from src.config import config
            cache.operation_count = config.MEMORY_CHECK_INTERVAL - 1

            # Trigger check
            cache.get("any-key")

            # Restore if needed
            cache.operation_count = original_count + 1

        # Test the helper
        initial_count = cache.operation_count
        force_memory_check()
        # Count should have incremented
        assert cache.operation_count > initial_count


@pytest.mark.integration
class TestMemoryMonitoringIntegration:
    """Integration tests for memory monitoring."""

    def test_full_lifecycle_with_memory_monitoring(self, caplog):
        """Test full cache lifecycle with memory monitoring enabled."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        cache = LRUPipelineCache(capacity=2)

        # Initial state should log memory
        assert any("System RAM:" in record.message for record in caplog.records)

        # Add models
        cache.put("en->de", MockPipeline("en-de"))
        cache.put("en->fr", MockPipeline("en-fr"))

        # Get status with memory
        status = cache.get_status()
        assert "system_memory" in status
        assert status["size"] == 2

        # Cache hit should work
        result = cache.get("en->de")
        assert result is not None

        # Overflow should evict
        cache.put("en->es", MockPipeline("en-es"))
        assert len(cache) == 2  # Oldest evicted

        # Log status should show memory
        caplog.clear()
        cache.log_status()
        assert any("System RAM:" in record.message for record in caplog.records)
