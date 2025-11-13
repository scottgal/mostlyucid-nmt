"""LRU cache for translation pipelines with intelligent memory monitoring."""

from collections import OrderedDict
from typing import Any, Optional, Tuple, List
import time
import torch

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from src.core.logging import logger


class LRUPipelineCache(OrderedDict):
    """LRU cache with automatic GPU memory management and intelligent RAM monitoring.

    Features:
    - Automatic eviction when cache reaches capacity
    - Memory monitoring with configurable thresholds
    - Auto-eviction when system RAM or GPU VRAM gets critically low
    - Time-based eviction for idle models (configurable)
    - Warning logs when memory usage is high
    - GPU memory cleanup on eviction
    """

    def __init__(self, capacity: int):
        """Initialize cache with given capacity.

        Args:
            capacity: Maximum number of pipelines to cache
        """
        super().__init__()
        self.capacity = max(1, capacity)
        self.operation_count = 0  # Track operations for periodic memory checks
        self.last_access_times: dict[str, float] = {}  # Track last access time for each model

        if not PSUTIL_AVAILABLE:
            logger.warning("psutil not available - memory monitoring disabled. Install psutil for intelligent memory management.")

        # Log initial memory state
        if PSUTIL_AVAILABLE:
            self._log_initial_memory_state()

    def _log_initial_memory_state(self) -> None:
        """Log initial system memory state at cache initialization."""
        ram_pct, ram_used_gb, ram_total_gb = self._get_system_memory_usage()
        logger.info(f"💾 System RAM: {ram_used_gb:.1f}GB / {ram_total_gb:.1f}GB ({ram_pct:.1f}%)")

        if torch.cuda.is_available():
            gpu_pct, gpu_used_gb, gpu_total_gb = self._get_gpu_memory_usage()
            logger.info(f"🎮 GPU VRAM: {gpu_used_gb:.1f}GB / {gpu_total_gb:.1f}GB ({gpu_pct:.1f}%)")

    def _get_system_memory_usage(self) -> Tuple[float, float, float]:
        """Get current system memory usage.

        Returns:
            Tuple of (percentage, used_gb, total_gb)
        """
        if not PSUTIL_AVAILABLE:
            return (0.0, 0.0, 0.0)

        mem = psutil.virtual_memory()
        percentage = mem.percent
        used_gb = mem.used / (1024**3)
        total_gb = mem.total / (1024**3)
        return (percentage, used_gb, total_gb)

    def _get_gpu_memory_usage(self) -> Tuple[float, float, float]:
        """Get current GPU memory usage.

        Returns:
            Tuple of (percentage, used_gb, total_gb)
        """
        if not torch.cuda.is_available():
            return (0.0, 0.0, 0.0)

        try:
            # Get memory info for device 0 (primary GPU)
            mem_allocated = torch.cuda.memory_allocated(0)
            mem_reserved = torch.cuda.memory_reserved(0)

            # Use nvidia-smi via pynvml if available, otherwise estimate
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_gb = info.total / (1024**3)
                used_gb = info.used / (1024**3)
                percentage = (info.used / info.total) * 100
                pynvml.nvmlShutdown()
                return (percentage, used_gb, total_gb)
            except (ImportError, Exception):
                # Fallback: estimate from PyTorch
                # Note: PyTorch only tracks its own allocations, not total GPU usage
                total_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                used_gb = mem_reserved / (1024**3)
                percentage = (mem_reserved / torch.cuda.get_device_properties(0).total_memory) * 100
                return (percentage, used_gb, total_gb)
        except Exception as e:
            logger.debug(f"Error getting GPU memory: {e}")
            return (0.0, 0.0, 0.0)

    def _check_memory_and_evict_if_needed(self) -> None:
        """Check memory usage and auto-evict if critically low.

        This is called periodically (based on MEMORY_CHECK_INTERVAL) to avoid
        checking on every cache operation.
        """
        from src.config import config

        if not config.ENABLE_MEMORY_MONITOR or not PSUTIL_AVAILABLE:
            return

        # Only check every N operations to avoid overhead
        self.operation_count += 1
        if self.operation_count % config.MEMORY_CHECK_INTERVAL != 0:
            return

        # Check system RAM
        ram_pct, ram_used_gb, ram_total_gb = self._get_system_memory_usage()

        # EMERGENCY: If RAM is extremely high (95%+), evict ALL models
        if ram_pct >= 95.0:
            if len(self) > 0:
                logger.error(f"🆘 EMERGENCY RAM: {ram_pct:.1f}% ({ram_used_gb:.1f}GB/{ram_total_gb:.1f}GB) - Evicting ALL cached models!")
                self._evict_all_models(reason="emergency RAM pressure")
            else:
                logger.error(f"🆘 EMERGENCY RAM: {ram_pct:.1f}% ({ram_used_gb:.1f}GB/{ram_total_gb:.1f}GB) - Cache already empty! System critically low on memory!")
            return  # Skip further checks after emergency eviction

        if ram_pct >= config.MEMORY_CRITICAL_THRESHOLD:
            # CRITICAL: Auto-evict to free memory
            if len(self) > 0:
                logger.warning(f"🚨 CRITICAL RAM: {ram_pct:.1f}% ({ram_used_gb:.1f}GB/{ram_total_gb:.1f}GB) - Auto-evicting oldest cached model!")
                self._evict_oldest_model()
            else:
                logger.warning(f"🚨 CRITICAL RAM: {ram_pct:.1f}% ({ram_used_gb:.1f}GB/{ram_total_gb:.1f}GB) - Cache already empty!")

        elif ram_pct >= config.MEMORY_WARNING_THRESHOLD:
            # WARNING: Log but don't evict yet
            logger.warning(f"⚠️  High RAM usage: {ram_pct:.1f}% ({ram_used_gb:.1f}GB/{ram_total_gb:.1f}GB) - Consider reducing MAX_CACHED_MODELS if this persists")

        # Check GPU VRAM if available
        if torch.cuda.is_available():
            gpu_pct, gpu_used_gb, gpu_total_gb = self._get_gpu_memory_usage()

            # EMERGENCY: If VRAM is extremely high (95%+), evict ALL models
            if gpu_pct >= 95.0:
                if len(self) > 0:
                    logger.error(f"🆘 EMERGENCY VRAM: {gpu_pct:.1f}% ({gpu_used_gb:.1f}GB/{gpu_total_gb:.1f}GB) - Evicting ALL cached models!")
                    self._evict_all_models(reason="emergency VRAM pressure")
                else:
                    logger.error(f"🆘 EMERGENCY VRAM: {gpu_pct:.1f}% ({gpu_used_gb:.1f}GB/{gpu_total_gb:.1f}GB) - Cache already empty! GPU critically low on memory!")
                return  # Skip further checks after emergency eviction

            if gpu_pct >= config.GPU_MEMORY_CRITICAL_THRESHOLD:
                # CRITICAL: Auto-evict to free VRAM
                if len(self) > 0:
                    logger.warning(f"🚨 CRITICAL VRAM: {gpu_pct:.1f}% ({gpu_used_gb:.1f}GB/{gpu_total_gb:.1f}GB) - Auto-evicting oldest cached model!")
                    self._evict_oldest_model()
                else:
                    logger.warning(f"🚨 CRITICAL VRAM: {gpu_pct:.1f}% ({gpu_used_gb:.1f}GB/{gpu_total_gb:.1f}GB) - Cache already empty!")

            elif gpu_pct >= config.GPU_MEMORY_WARNING_THRESHOLD:
                # WARNING: Log but don't evict yet
                logger.warning(f"⚠️  High VRAM usage: {gpu_pct:.1f}% ({gpu_used_gb:.1f}GB/{gpu_total_gb:.1f}GB) - Watch for OOM errors")

    def _evict_oldest_model(self) -> None:
        """Evict the oldest (least recently used) model from cache.

        This is called when memory is critically low.
        """
        if len(self) == 0:
            return

        old_key, old_val = self.popitem(last=False)
        # Clean up access time tracking
        self.last_access_times.pop(old_key, None)
        logger.info(f"🧹 Auto-evicted oldest model: {old_key} (memory management)")

        # Clean up GPU memory
        try:
            if hasattr(old_val, "model"):
                old_val.model.cpu()
                logger.debug(f"Moved evicted model {old_key} to CPU")
            del old_val
        except Exception as e:
            logger.debug(f"Error during eviction cleanup: {e}")

        if torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
                logger.debug("Cleared CUDA cache after auto-eviction")
            except Exception as e:
                logger.debug(f"Error clearing CUDA cache: {e}")

        # Pi-specific: aggressive memory cleanup
        try:
            from src.core.pi_optimizations import pi_optimizer
            pi_optimizer.aggressive_cleanup()
        except:
            pass

        # Log memory after eviction
        ram_pct, ram_used_gb, ram_total_gb = self._get_system_memory_usage()
        logger.info(f"💾 RAM after eviction: {ram_pct:.1f}% ({ram_used_gb:.1f}GB/{ram_total_gb:.1f}GB)")

        if torch.cuda.is_available():
            gpu_pct, gpu_used_gb, gpu_total_gb = self._get_gpu_memory_usage()
            logger.info(f"🎮 VRAM after eviction: {gpu_pct:.1f}% ({gpu_used_gb:.1f}GB/{gpu_total_gb:.1f}GB)")

    def _evict_all_models(self, reason: str = "emergency memory pressure") -> None:
        """Emergency eviction: Remove ALL cached models.

        This is called when memory is so critically low (95%+) that even a single
        model load might fail. Clears the entire cache to free maximum memory.

        Args:
            reason: Reason for emergency eviction (for logging)
        """
        if len(self) == 0:
            return

        count = len(self)
        logger.error(f"🆘 EMERGENCY EVICTION: Removing {count} cached models ({reason})")

        # Evict all models
        while len(self) > 0:
            try:
                old_key, old_val = self.popitem(last=False)
                # Clean up access time tracking
                self.last_access_times.pop(old_key, None)
                logger.info(f"   Evicting: {old_key}")

                # Clean up
                try:
                    if hasattr(old_val, "model"):
                        old_val.model.cpu()
                    del old_val
                except Exception as e:
                    logger.debug(f"Error cleaning up {old_key}: {e}")

            except Exception as e:
                logger.error(f"Error during emergency eviction: {e}")
                break

        # Clear any remaining access times (safety measure)
        self.last_access_times.clear()

        # Aggressive CUDA cleanup
        if torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
                torch.cuda.synchronize()  # Wait for all operations to complete
                logger.info("Cleared and synchronized CUDA cache")
            except Exception as e:
                logger.debug(f"Error clearing CUDA cache: {e}")

        # Log final memory state
        ram_pct, ram_used_gb, ram_total_gb = self._get_system_memory_usage()
        logger.info(f"💾 RAM after emergency eviction: {ram_pct:.1f}% ({ram_used_gb:.1f}GB/{ram_total_gb:.1f}GB)")

        if torch.cuda.is_available():
            gpu_pct, gpu_used_gb, gpu_total_gb = self._get_gpu_memory_usage()
            logger.info(f"🎮 VRAM after emergency eviction: {gpu_pct:.1f}% ({gpu_used_gb:.1f}GB/{gpu_total_gb:.1f}GB)")

        logger.error(f"🆘 Emergency eviction complete. Evicted {count} models. Cache now empty.")

    def is_memory_critical(self) -> bool:
        """Check if system memory is at emergency levels (95%+).

        Returns:
            True if memory is critically low and cache should reject new models
        """
        if not PSUTIL_AVAILABLE:
            return False

        ram_pct, _, _ = self._get_system_memory_usage()
        if ram_pct >= 95.0:
            return True

        if torch.cuda.is_available():
            gpu_pct, _, _ = self._get_gpu_memory_usage()
            if gpu_pct >= 95.0:
                return True

        return False

    def evict_idle_models(self, timeout_seconds: int) -> List[str]:
        """Evict models that haven't been accessed for the specified timeout.

        This method checks all cached models and evicts any that haven't been
        accessed within the timeout period. Used for time-based cache eviction.

        Args:
            timeout_seconds: Evict models idle for longer than this (in seconds)

        Returns:
            List of evicted model keys
        """
        if timeout_seconds <= 0:
            return []  # Feature disabled

        current_time = time.time()
        evicted_keys: List[str] = []

        # Find models that have been idle too long
        idle_models = []
        for key in list(self.keys()):
            last_access = self.last_access_times.get(key, 0)
            idle_duration = current_time - last_access

            if idle_duration > timeout_seconds:
                idle_models.append((key, idle_duration))

        if not idle_models:
            return []

        # Evict idle models
        logger.info(f"⏰ Found {len(idle_models)} idle models (timeout: {timeout_seconds}s)")

        for key, idle_duration in idle_models:
            try:
                if key in self:
                    val = self.pop(key)
                    self.last_access_times.pop(key, None)
                    evicted_keys.append(key)

                    idle_mins = int(idle_duration / 60)
                    logger.info(f"⏰ Evicted idle model: {key} (idle for {idle_mins}m {int(idle_duration % 60)}s)")

                    # Clean up GPU memory
                    try:
                        if hasattr(val, "model"):
                            val.model.cpu()
                            logger.debug(f"Moved evicted model {key} to CPU")
                        del val
                    except Exception as e:
                        logger.debug(f"Error during idle eviction cleanup: {e}")

            except Exception as e:
                logger.error(f"Error evicting idle model {key}: {e}")

        # Clear CUDA cache after evictions
        if evicted_keys and torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
                logger.debug(f"Cleared CUDA cache after idle evictions")
            except Exception as e:
                logger.debug(f"Error clearing CUDA cache: {e}")

        if evicted_keys:
            logger.info(f"⏰ Idle eviction complete: {len(evicted_keys)} models evicted ({len(self)}/{self.capacity} remaining)")

        return evicted_keys

    def get(self, key: str) -> Optional[Any]:
        """Get pipeline from cache and move to end (most recently used).

        Args:
            key: Cache key (e.g., "en->de")

        Returns:
            Cached pipeline or None if not found
        """
        # Periodic memory check
        self._check_memory_and_evict_if_needed()

        if key in self:
            self.move_to_end(key)
            self.last_access_times[key] = time.time()  # Update last access time
            logger.info(f"✓ Cache HIT: Reusing loaded model for {key} ({len(self)}/{self.capacity} models in cache)")
            return super().__getitem__(key)
        logger.info(f"✗ Cache MISS: Need to load model for {key} ({len(self)}/{self.capacity} models in cache)")
        return None

    def put(self, key: str, value: Any) -> None:
        """Put pipeline in cache, evicting oldest if at capacity.

        Also checks memory usage and may auto-evict if memory is critically low.

        Args:
            key: Cache key (e.g., "en->de")
            value: Translation pipeline to cache
        """
        # Periodic memory check before adding
        self._check_memory_and_evict_if_needed()

        exists = key in self

        super().__setitem__(key, value)
        self.move_to_end(key)
        self.last_access_times[key] = time.time()  # Update last access time

        if exists:
            logger.debug(f"Updated existing cache entry: {key}")
        else:
            logger.info(f"💾 Cached model: {key} ({len(self)}/{self.capacity} models in cache)")

        if not exists and len(self) > self.capacity:
            old_key, old_val = self.popitem(last=False)
            # Clean up access time tracking
            self.last_access_times.pop(old_key, None)

            logger.warning(f"⚠️  Cache FULL! Evicting oldest model: {old_key} (to make room for {key})")

            # Try to free GPU memory for the evicted pipeline
            try:
                if hasattr(old_val, "model"):
                    old_val.model.cpu()
                    logger.info(f"Moved evicted model {old_key} to CPU to free GPU memory")
                del old_val
            except Exception as e:
                logger.debug(f"Error during cache eviction cleanup: {e}")

            if torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                    logger.debug(f"Cleared CUDA cache after eviction")
                except Exception as e:
                    logger.debug(f"Error clearing CUDA cache: {e}")

    def get_status(self) -> dict:
        """Get current cache status including memory usage.

        Returns:
            Dictionary with cache statistics and memory info
        """
        status = {
            "capacity": self.capacity,
            "size": len(self),
            "keys": list(self.keys()),
            "utilization": f"{len(self)}/{self.capacity} ({int(len(self)/self.capacity*100)}%)" if self.capacity > 0 else "0/0 (0%)"
        }

        # Add memory information if available
        if PSUTIL_AVAILABLE:
            ram_pct, ram_used_gb, ram_total_gb = self._get_system_memory_usage()
            status["system_memory"] = {
                "percentage": round(ram_pct, 1),
                "used_gb": round(ram_used_gb, 1),
                "total_gb": round(ram_total_gb, 1),
                "status": "critical" if ram_pct >= 90 else "warning" if ram_pct >= 80 else "ok"
            }

            if torch.cuda.is_available():
                gpu_pct, gpu_used_gb, gpu_total_gb = self._get_gpu_memory_usage()
                status["gpu_memory"] = {
                    "percentage": round(gpu_pct, 1),
                    "used_gb": round(gpu_used_gb, 1),
                    "total_gb": round(gpu_total_gb, 1),
                    "status": "critical" if gpu_pct >= 90 else "warning" if gpu_pct >= 80 else "ok"
                }

        return status

    def log_status(self) -> None:
        """Log current cache status including memory."""
        status = self.get_status()
        logger.info(f"📊 Cache Status: {status['utilization']} - Models: {', '.join(status['keys']) if status['keys'] else 'none'}")

        # Log memory info if available
        if "system_memory" in status:
            mem = status["system_memory"]
            logger.info(f"💾 System RAM: {mem['used_gb']}GB / {mem['total_gb']}GB ({mem['percentage']}%) - Status: {mem['status']}")

        if "gpu_memory" in status:
            mem = status["gpu_memory"]
            logger.info(f"🎮 GPU VRAM: {mem['used_gb']}GB / {mem['total_gb']}GB ({mem['percentage']}%) - Status: {mem['status']}")
