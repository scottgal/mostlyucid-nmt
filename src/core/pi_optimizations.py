"""Raspberry Pi specific optimizations for model loading and inference.

This module provides memory and performance optimizations specifically designed
for resource-constrained ARM64 devices like Raspberry Pi.

Key optimizations:
1. Streaming model downloads to SSD (avoid loading into RAM)
2. Memory-mapped model loading (mmap - don't load entire model into RAM)
3. Model quantization (int8 for smaller memory footprint)
4. Aggressive garbage collection
5. CPU-specific PyTorch optimizations
"""

import os
import torch
import gc
from typing import Any, Dict, Optional
from src.core.logging import logger


class PiOptimizer:
    """Optimizations for Raspberry Pi deployment."""

    def __init__(self):
        """Initialize Pi-specific optimizations."""
        self.is_pi = self._detect_pi()
        if self.is_pi:
            logger.info("[PiOptimizer] Raspberry Pi detected - enabling optimizations")
            self._configure_pytorch_for_pi()
        else:
            logger.info("[PiOptimizer] Not running on Raspberry Pi - optimizations disabled")

    def _detect_pi(self) -> bool:
        """Detect if running on Raspberry Pi.

        Returns:
            True if running on Raspberry Pi
        """
        # Check for ARM64 architecture
        import platform
        if platform.machine() not in ("aarch64", "arm64"):
            return False

        # Check for Raspberry Pi specific markers
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
                return "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo
        except:
            # If we can't read cpuinfo, assume Pi based on architecture
            return True

    def _configure_pytorch_for_pi(self):
        """Configure PyTorch for optimal Pi performance.

        Sets thread counts, memory allocators, and other CPU-specific settings.
        """
        # Limit CPU threads to avoid thrashing
        # Pi 5 has 4 cores, use 2-3 threads for inference
        num_threads = min(3, os.cpu_count() or 2)
        torch.set_num_threads(num_threads)
        torch.set_num_interop_threads(1)  # Single thread for inter-op

        logger.info(f"[PiOptimizer] Set PyTorch threads: {num_threads} (intra), 1 (inter)")

        # Enable memory-efficient attention if available (PyTorch 2.0+)
        try:
            torch.backends.opt_einsum.enabled = True
            logger.info("[PiOptimizer] Enabled optimized einsum")
        except:
            pass

        # Disable TensorFloat32 (not applicable to CPU but doesn't hurt)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False

    def get_model_loading_kwargs(self) -> Dict[str, Any]:
        """Get optimized kwargs for model loading on Pi.

        Returns:
            Dictionary of kwargs to pass to transformers model loading
        """
        if not self.is_pi:
            return {}

        kwargs = {
            # Use memory-mapped loading - doesn't load entire model into RAM
            # Model stays on disk and is paged in as needed
            "low_cpu_mem_usage": True,

            # Load in bfloat16 if supported, otherwise float32
            # Note: Most ARM CPUs don't have native bf16 support, but it still saves memory
            # during loading and PyTorch will upcast to fp32 for computation
            "torch_dtype": torch.bfloat16,

            # Disable safetensors fast init (uses less memory during load)
            "use_safetensors": True,
        }

        logger.info(f"[PiOptimizer] Model loading kwargs: {kwargs}")
        return kwargs

    def get_pipeline_kwargs(self) -> Dict[str, Any]:
        """Get optimized kwargs for pipeline creation on Pi.

        Returns:
            Dictionary of kwargs to pass to transformers pipeline()
        """
        if not self.is_pi:
            return {}

        kwargs = {
            # Use smaller batch size for inference
            # This is overridden by EASYNMT_BATCH_SIZE but provides a sensible default
            "batch_size": 1,

            # Disable unnecessary features
            "framework": "pt",  # Explicitly use PyTorch
        }

        return kwargs

    def optimize_after_model_load(self, model: Any):
        """Apply post-load optimizations to a model.

        Args:
            model: The loaded transformers model
        """
        if not self.is_pi:
            return

        logger.info("[PiOptimizer] Applying post-load optimizations")

        # Move model to eval mode (disables dropout, etc.)
        if hasattr(model, 'eval'):
            model.eval()

        # Disable gradient computation globally
        if hasattr(model, 'requires_grad_'):
            model.requires_grad_(False)

        # Run garbage collection to free any temporary memory from loading
        gc.collect()

        logger.info("[PiOptimizer] Post-load optimizations complete")

    def quantize_model(self, model: Any, quantization_type: str = "dynamic") -> Any:
        """Quantize model to int8 for smaller memory footprint.

        WARNING: Quantization reduces quality slightly but saves 75% memory.
        Only use if running out of RAM.

        Args:
            model: The model to quantize
            quantization_type: "dynamic" (default) or "static"

        Returns:
            Quantized model
        """
        if not self.is_pi:
            return model

        try:
            logger.info(f"[PiOptimizer] Quantizing model to int8 ({quantization_type})")

            if quantization_type == "dynamic":
                # Dynamic quantization - good for LSTMs and Transformers
                quantized = torch.quantization.quantize_dynamic(
                    model,
                    {torch.nn.Linear},  # Quantize linear layers
                    dtype=torch.qint8
                )
                logger.info("[PiOptimizer] Dynamic quantization complete")
                return quantized
            else:
                logger.warning(f"[PiOptimizer] Quantization type '{quantization_type}' not implemented")
                return model

        except Exception as e:
            logger.error(f"[PiOptimizer] Quantization failed: {e}")
            return model

    def aggressive_cleanup(self):
        """Perform aggressive memory cleanup.

        Call this after model loading or eviction to free memory.
        """
        if not self.is_pi:
            return

        gc.collect()

        # Try to release fragmented memory back to OS
        try:
            import ctypes
            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
            logger.debug("[PiOptimizer] malloc_trim() called")
        except:
            pass

    def get_optimal_batch_size(self, available_ram_gb: float) -> int:
        """Calculate optimal batch size based on available RAM.

        Args:
            available_ram_gb: Available system RAM in GB

        Returns:
            Recommended batch size
        """
        if not self.is_pi:
            return 16  # Default for non-Pi systems

        # Conservative batch sizes for Pi
        if available_ram_gb < 2:
            return 1
        elif available_ram_gb < 4:
            return 2
        elif available_ram_gb < 6:
            return 4
        else:
            return 8

    def enable_model_caching_to_disk(self, cache_dir: str):
        """Configure HuggingFace to stream downloads directly to disk.

        This prevents loading large model files into RAM during download.

        Args:
            cache_dir: Directory to cache models (should be on SSD for Pi)
        """
        if not self.is_pi:
            return

        # HuggingFace already streams to disk by default, but we can ensure
        # the cache directory is on fast storage (SSD)
        os.makedirs(cache_dir, exist_ok=True)

        # Set environment variable for HuggingFace cache
        os.environ["HF_HOME"] = cache_dir
        os.environ["TRANSFORMERS_CACHE"] = cache_dir
        logger.info(f"[PiOptimizer] HuggingFace cache configured: {cache_dir}")

        # Disable HuggingFace telemetry to save bandwidth and CPU
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["DISABLE_TELEMETRY"] = "1"


# Global singleton
pi_optimizer = PiOptimizer()
