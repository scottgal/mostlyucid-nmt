"""Request queue and backpressure management."""

import asyncio
import math
import time
from typing import Optional

from src.config import config
from src.core.device import device_manager
from src.core.logging import logger
from src.exceptions import QueueOverflowError, ServiceBusyError


class QueueManager:
    """Manages request queueing and backpressure."""

    def __init__(self):
        """Initialize queue manager with semaphore."""
        self.max_inflight = device_manager.max_inflight
        self.semaphore = asyncio.Semaphore(value=self.max_inflight)

        self.waiting_count = 0
        self.waiting_lock = asyncio.Lock()

        self.inflight_count = 0
        self.inflight_lock = asyncio.Lock()

        # EMA tracking for retry-after estimation
        self.avg_translate_duration_sec = 0.0
        self.avg_duration_lock = asyncio.Lock()

    async def record_duration(self, duration_sec: float) -> None:
        """Record translation duration for retry-after estimation.

        Args:
            duration_sec: Translation duration in seconds
        """
        try:
            async with self.avg_duration_lock:
                if self.avg_translate_duration_sec <= 0:
                    self.avg_translate_duration_sec = duration_sec
                else:
                    alpha = config.RETRY_AFTER_ALPHA
                    self.avg_translate_duration_sec = (
                        (1.0 - alpha) * self.avg_translate_duration_sec +
                        alpha * duration_sec
                    )
        except Exception as e:
            logger.debug(f"Error recording duration: {e}")

    def estimate_retry_after(self, waiters: Optional[int] = None) -> int:
        """Estimate retry-after time in seconds.

        Args:
            waiters: Number of waiting requests (None if unknown)

        Returns:
            Retry-after time in seconds
        """
        # Base estimate per job
        base = (
            self.avg_translate_duration_sec
            if self.avg_translate_duration_sec > 0
            else config.RETRY_AFTER_MIN_SEC
        )
        base = max(base, config.RETRY_AFTER_MIN_SEC)

        cap = max(1, self.max_inflight)

        if waiters is None:
            # If we only know it's busy, assume at least one batch ahead
            est = base
        else:
            # Roughly how many batches ahead of us
            est = (waiters / cap) * base

        # Clamp to configured bounds
        est = min(max(est, config.RETRY_AFTER_MIN_SEC), float(config.RETRY_AFTER_MAX_SEC))
        return max(1, math.ceil(est))

    async def get_waiting_count(self) -> int:
        """Get current waiting count."""
        async with self.waiting_lock:
            return self.waiting_count

    async def get_inflight_count(self) -> int:
        """Get current inflight count."""
        async with self.inflight_lock:
            return self.inflight_count


class TranslateSlot:
    """Context manager for acquiring translation slots."""

    def __init__(self, queue_manager: QueueManager):
        """Initialize slot manager.

        Args:
            queue_manager: QueueManager instance
        """
        self.queue_manager = queue_manager
        self.acquired = False

    async def __aenter__(self):
        """Acquire translation slot."""
        if config.ENABLE_QUEUE:
            # Queueing enabled: increment waiting count
            async with self.queue_manager.waiting_lock:
                self.queue_manager.waiting_count += 1
                wc = self.queue_manager.waiting_count

            # If queue too long and no slots free, reject
            if self.queue_manager.semaphore.locked() and wc > config.MAX_QUEUE_SIZE:
                async with self.queue_manager.waiting_lock:
                    self.queue_manager.waiting_count -= 1
                raise QueueOverflowError(waiters=wc)

            # Acquire semaphore (may wait)
            await self.queue_manager.semaphore.acquire()

            async with self.queue_manager.waiting_lock:
                self.queue_manager.waiting_count -= 1

            self.acquired = True

            async with self.queue_manager.inflight_lock:
                self.queue_manager.inflight_count += 1

            return self

        else:
            # No queueing: try immediate acquire
            if self.queue_manager.semaphore.locked():
                raise ServiceBusyError()

            await self.queue_manager.semaphore.acquire()
            self.acquired = True

            async with self.queue_manager.inflight_lock:
                self.queue_manager.inflight_count += 1

            return self

    async def __aexit__(self, exc_type, exc, tb):
        """Release translation slot."""
        if self.acquired:
            self.queue_manager.semaphore.release()

            async with self.queue_manager.inflight_lock:
                self.queue_manager.inflight_count = max(0, self.queue_manager.inflight_count - 1)

            self.acquired = False


# Singleton instance
queue_manager = QueueManager()


async def acquire_translate_slot() -> TranslateSlot:
    """Acquire a translation slot (context manager).

    Returns:
        TranslateSlot context manager

    Raises:
        QueueOverflowError: If queue is full
        ServiceBusyError: If service is busy and queueing disabled
    """
    return TranslateSlot(queue_manager)
