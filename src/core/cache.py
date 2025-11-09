"""LRU cache for translation pipelines."""

from collections import OrderedDict
from typing import Any, Optional
import torch

from src.core.logging import logger

# Try to import Intel Extension for PyTorch (IPEX) if available
try:
    import intel_extension_for_pytorch as ipex
    HAS_IPEX = True
except ImportError:
    HAS_IPEX = False


class LRUPipelineCache(OrderedDict):
    """LRU cache with automatic GPU memory management on eviction."""

    def __init__(self, capacity: int):
        """Initialize cache with given capacity.

        Args:
            capacity: Maximum number of pipelines to cache
        """
        super().__init__()
        self.capacity = max(1, capacity)

    def get(self, key: str) -> Optional[Any]:
        """Get pipeline from cache and move to end (most recently used).

        Args:
            key: Cache key (e.g., "en->de")

        Returns:
            Cached pipeline or None if not found
        """
        if key in self:
            self.move_to_end(key)
            return super().__getitem__(key)
        return None

    def put(self, key: str, value: Any) -> None:
        """Put pipeline in cache, evicting oldest if at capacity.

        Args:
            key: Cache key (e.g., "en->de")
            value: Translation pipeline to cache
        """
        exists = key in self

        super().__setitem__(key, value)
        self.move_to_end(key)

        if not exists and len(self) > self.capacity:
            old_key, old_val = self.popitem(last=False)

            # Try to free GPU memory for the evicted pipeline
            try:
                if hasattr(old_val, "model"):
                    old_val.model.cpu()
                del old_val
            except Exception as e:
                logger.debug(f"Error during cache eviction cleanup: {e}")

            # Clear GPU cache for all supported device types
            self._clear_gpu_cache()

            logger.info(f"Evicted pipeline {old_key} from cache")

    def _clear_gpu_cache(self) -> None:
        """Clear GPU memory cache for NVIDIA CUDA, AMD ROCm, or Intel XPU."""
        # Clear CUDA cache (works for both NVIDIA and AMD ROCm)
        if torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
                logger.debug("Cleared CUDA/ROCm cache")
            except Exception as e:
                logger.debug(f"Error clearing CUDA cache: {e}")

        # Clear Intel XPU cache
        if HAS_IPEX and hasattr(torch, 'xpu') and torch.xpu.is_available():
            try:
                torch.xpu.empty_cache()
                logger.debug("Cleared Intel XPU cache")
            except Exception as e:
                logger.debug(f"Error clearing XPU cache: {e}")
