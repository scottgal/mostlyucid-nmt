"""Device management and selection."""

from src.config import config
from src.core.logging import logger

# Torch is optional - only needed for transformers backend
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    TORCH_AVAILABLE = False


def _get_cuda_device_name(device_index: int) -> str:
    """Get CUDA device name if available."""
    if TORCH_AVAILABLE and torch.cuda.is_available():
        try:
            return torch.cuda.get_device_name(device_index)
        except Exception:
            pass
    # Try ctranslate2's detection
    try:
        import ctranslate2
        # CTranslate2 doesn't expose device names directly
        return f"CUDA Device {device_index}"
    except (ImportError, Exception):
        pass
    return f"CUDA Device {device_index}"


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
            # Check if CUDA is actually available
            cuda_available = False
            if TORCH_AVAILABLE:
                cuda_available = torch.cuda.is_available()
            else:
                try:
                    import ctranslate2
                    # get_supported_compute_types requires device argument in v4+
                    cuda_types = ctranslate2.get_supported_compute_types("cuda")
                    cuda_available = len(cuda_types) > 0
                except (ImportError, Exception):
                    pass

            if cuda_available:
                device_name = _get_cuda_device_name(self.device_index)
                logger.info(f"Using GPU: {device_name} (cuda:{self.device_index})")
            else:
                logger.warning("CUDA requested but not available, falling back to CPU")
                self.device_index = -1

        logger.info(f"Max inflight translations: {self.max_inflight}")

    @property
    def device_str(self) -> str:
        """Get device as string (e.g., 'cpu' or 'cuda:0')."""
        return "cpu" if self.device_index == -1 else f"cuda:{self.device_index}"

    @property
    def ct2_device(self) -> str:
        """Get device string for CTranslate2 ('cuda' or 'cpu')."""
        return "cuda" if self.device_index >= 0 else "cpu"

    def is_cuda(self) -> bool:
        """Check if using CUDA."""
        return self.device_index != -1


# Singleton device manager
device_manager = DeviceManager()
