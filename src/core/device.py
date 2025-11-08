"""Device management and selection."""

import torch
from src.config import config
from src.core.logging import logger


class DeviceManager:
    """Manages device selection and configuration."""

    def __init__(self):
        """Initialize device manager."""
        self.device_index = config.resolve_device_index()
        self.max_inflight = config.get_max_inflight_translations(self.device_index)

        # Log device information
        if self.device_index == -1:
            logger.info("Using CPU for translation")
        else:
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(self.device_index)
                logger.info(f"Using GPU: {device_name} (cuda:{self.device_index})")
            else:
                logger.warning("CUDA requested but not available, falling back to CPU")
                self.device_index = -1

        logger.info(f"Max inflight translations: {self.max_inflight}")

    @property
    def device_str(self) -> str:
        """Get device as string (e.g., 'cpu' or 'cuda:0')."""
        return "cpu" if self.device_index == -1 else f"cuda:{self.device_index}"

    def is_cuda(self) -> bool:
        """Check if using CUDA."""
        return self.device_index != -1


# Singleton device manager
device_manager = DeviceManager()
