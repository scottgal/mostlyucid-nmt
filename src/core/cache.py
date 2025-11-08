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

            if torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                except Exception as e:
                    logger.debug(f"Error clearing CUDA cache: {e}")

            logger.info(f"Evicted pipeline {old_key} from cache")
