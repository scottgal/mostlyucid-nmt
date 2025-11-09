"""LRU cache for translation pipelines."""

from collections import OrderedDict
from typing import Any, Optional
import torch

from src.core.logging import logger


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
            logger.info(f"✓ Cache HIT: Reusing loaded model for {key} ({len(self)}/{self.capacity} models in cache)")
            return super().__getitem__(key)
        logger.info(f"✗ Cache MISS: Need to load model for {key} ({len(self)}/{self.capacity} models in cache)")
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

        if exists:
            logger.debug(f"Updated existing cache entry: {key}")
        else:
            logger.info(f"💾 Cached model: {key} ({len(self)}/{self.capacity} models in cache)")

        if not exists and len(self) > self.capacity:
            old_key, old_val = self.popitem(last=False)

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
        """Get current cache status.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "capacity": self.capacity,
            "size": len(self),
            "keys": list(self.keys()),
            "utilization": f"{len(self)}/{self.capacity} ({int(len(self)/self.capacity*100)}%)" if self.capacity > 0 else "0/0 (0%)"
        }

    def log_status(self) -> None:
        """Log current cache status."""
        status = self.get_status()
        logger.info(f"📊 Cache Status: {status['utilization']} - Models: {', '.join(status['keys']) if status['keys'] else 'none'}")
