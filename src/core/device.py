"""Device management and selection."""

import os
import torch
from src.config import config
from src.core.logging import logger

# Try to import Intel Extension for PyTorch (IPEX) if available
try:
    import intel_extension_for_pytorch as ipex
    HAS_IPEX = True
except ImportError:
    HAS_IPEX = False


class DeviceManager:
    """Manages device selection and configuration for NVIDIA, AMD, and Intel GPUs."""

    def __init__(self):
        """Initialize device manager with multi-vendor GPU support."""
        self.device_index = config.resolve_device_index()
        self.max_inflight = config.get_max_inflight_translations(self.device_index)
        self.device_type = self._detect_device_type()

        # Log device information
        if self.device_index == -1:
            logger.info("Using CPU for translation")
        else:
            self._log_gpu_info()

        logger.info(f"Max inflight translations: {self.max_inflight}")

    def _detect_device_type(self) -> str:
        """Detect GPU vendor/type: 'cuda' (NVIDIA/AMD ROCm), 'xpu' (Intel), or 'cpu'."""
        if self.device_index == -1:
            return "cpu"

        # Check for Intel XPU (Intel Arc, Data Center GPUs, NPUs)
        if HAS_IPEX and hasattr(torch, 'xpu') and torch.xpu.is_available():
            return "xpu"

        # Check for CUDA (NVIDIA or AMD ROCm - both use CUDA API)
        if torch.cuda.is_available():
            # Detect if this is ROCm (AMD) or CUDA (NVIDIA)
            if hasattr(torch.version, 'hip') and torch.version.hip is not None:
                return "rocm"
            return "cuda"

        # GPU requested but not available
        logger.warning("GPU requested but no compatible device found, falling back to CPU")
        self.device_index = -1
        return "cpu"

    def _log_gpu_info(self):
        """Log GPU information based on detected device type."""
        if self.device_type == "xpu":
            # Intel XPU device
            if HAS_IPEX:
                try:
                    device_name = torch.xpu.get_device_name(self.device_index)
                    logger.info(f"Using Intel GPU: {device_name} (xpu:{self.device_index})")
                except Exception as e:
                    logger.info(f"Using Intel XPU device: xpu:{self.device_index}")
        elif self.device_type == "rocm":
            # AMD ROCm device
            device_name = torch.cuda.get_device_name(self.device_index)
            logger.info(f"Using AMD GPU (ROCm): {device_name} (cuda:{self.device_index})")
        elif self.device_type == "cuda":
            # NVIDIA CUDA device
            device_name = torch.cuda.get_device_name(self.device_index)
            logger.info(f"Using NVIDIA GPU: {device_name} (cuda:{self.device_index})")

    @property
    def device_str(self) -> str:
        """Get device as string (e.g., 'cpu', 'cuda:0', 'xpu:0')."""
        if self.device_index == -1:
            return "cpu"
        elif self.device_type == "xpu":
            return f"xpu:{self.device_index}"
        else:
            # Both NVIDIA CUDA and AMD ROCm use 'cuda:N' device string
            return f"cuda:{self.device_index}"

    def is_gpu(self) -> bool:
        """Check if using any GPU (NVIDIA, AMD, or Intel)."""
        return self.device_index != -1

    def is_cuda(self) -> bool:
        """Check if using CUDA (NVIDIA or AMD ROCm)."""
        return self.device_index != -1 and self.device_type in ("cuda", "rocm")

    def is_xpu(self) -> bool:
        """Check if using Intel XPU."""
        return self.device_index != -1 and self.device_type == "xpu"


# Singleton device manager
device_manager = DeviceManager()
