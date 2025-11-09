"""Beautiful progress bars for model downloads."""

import os
import sys
from typing import Optional, Dict, List, Tuple
from tqdm import tqdm
from huggingface_hub import HfApi, hf_hub_download

from src.core.logging import logger


class DownloadProgressBar:
    """Custom progress bar for HuggingFace downloads with rich formatting."""

    def __init__(self):
        """Initialize progress tracking."""
        self.progress_bars: Dict[str, tqdm] = {}
        self.enabled = sys.stdout.isatty() or os.getenv("FORCE_PROGRESS_BAR", "0") == "1"

    def __call__(self,
                 filename: str,
                 downloaded: int,
                 total: Optional[int] = None):
        """Callback for download progress.

        Args:
            filename: Name of file being downloaded
            downloaded: Bytes downloaded so far
            total: Total bytes to download (None if unknown)
        """
        if not self.enabled:
            return

        # Create or update progress bar
        if filename not in self.progress_bars:
            # Create new progress bar
            self.progress_bars[filename] = tqdm(
                total=total if total else 0,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc=f"⬇ {filename}",
                ncols=100,
                bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
                leave=True,
                file=sys.stdout
            )

        pbar = self.progress_bars[filename]

        # Update total if it changed (first callback with size info)
        if total and pbar.total != total:
            pbar.total = total
            pbar.refresh()

        # Update progress
        if downloaded > pbar.n:
            pbar.update(downloaded - pbar.n)

    def close(self, filename: str):
        """Close progress bar for a file.

        Args:
            filename: Name of file
        """
        if filename in self.progress_bars:
            self.progress_bars[filename].close()
            del self.progress_bars[filename]

    def close_all(self):
        """Close all active progress bars."""
        for pbar in self.progress_bars.values():
            pbar.close()
        self.progress_bars.clear()


# Global progress tracker
_download_progress = DownloadProgressBar()


def get_download_progress() -> DownloadProgressBar:
    """Get global download progress tracker.

    Returns:
        Global DownloadProgressBar instance
    """
    return _download_progress


def get_model_download_size(model_name: str) -> Tuple[int, List[str]]:
    """Get total download size and list of files for a model.

    Args:
        model_name: HuggingFace model name (e.g., "Helsinki-NLP/opus-mt-en-de")

    Returns:
        Tuple of (total_bytes, list of main file names)
    """
    try:
        api = HfApi()
        # Get model files info
        files = api.list_repo_files(model_name, repo_type="model")

        # Filter to main model files (exclude .git, .md, etc.)
        main_extensions = ['.bin', '.safetensors', '.json', '.txt', '.model', '.spm', '.vocab']
        main_files = [f for f in files if any(f.endswith(ext) for ext in main_extensions)]

        # Get file sizes
        model_info = api.model_info(model_name, files_metadata=True)
        total_size = 0
        file_names = []

        if hasattr(model_info, 'siblings') and model_info.siblings:
            for file_info in model_info.siblings:
                if file_info.rfilename in main_files:
                    if hasattr(file_info, 'size') and file_info.size:
                        total_size += file_info.size
                    file_names.append(file_info.rfilename)

        return (total_size, file_names[:10])  # Limit to first 10 files for display
    except Exception as e:
        logger.debug(f"Could not fetch model size for {model_name}: {e}")
        return (0, [])


def format_bytes(bytes_val: int) -> str:
    """Format bytes as human-readable string.

    Args:
        bytes_val: Number of bytes

    Returns:
        Formatted string (e.g., "1.2 GB", "500 MB")
    """
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024**2:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024**3:
        return f"{bytes_val / (1024**2):.1f} MB"
    else:
        return f"{bytes_val / (1024**3):.2f} GB"


def show_download_banner(model_name: str, src: str = "", tgt: str = "", family: str = "", device: str = ""):
    """Show an informative banner before downloading a model.

    Args:
        model_name: HuggingFace model name
        src: Source language (optional)
        tgt: Target language (optional)
        family: Model family (optional)
        device: Device name (e.g., "GPU (cuda:0)" or "CPU") (optional)
    """
    if not (sys.stdout.isatty() or os.getenv("FORCE_PROGRESS_BAR", "0") == "1"):
        return

    # Get model size
    total_bytes, files = get_model_download_size(model_name)

    print("\n" + "="*100)
    print(f"  🚀 DOWNLOADING MODEL")
    print(f"  Model: {model_name}")
    if family:
        print(f"  Family: {family}")
    if src and tgt:
        print(f"  Direction: {src} → {tgt}")
    if device:
        print(f"  Device: {device}")
    if total_bytes > 0:
        print(f"  Total Size: {format_bytes(total_bytes)}")
        if files:
            print(f"  Files: {len(files)} main files")
    else:
        print(f"  Size: (fetching...)")
    print("="*100)
    print()

    # Log detailed info
    if total_bytes > 0:
        logger.info(f"Downloading {model_name}: {format_bytes(total_bytes)} across {len(files)} files")
    else:
        logger.info(f"Downloading {model_name}: size unknown, fetching from HuggingFace Hub")


def show_download_complete(model_name: str, src: str = "", tgt: str = ""):
    """Show completion banner after model download.

    Args:
        model_name: HuggingFace model name
        src: Source language (optional)
        tgt: Target language (optional)
    """
    if not (sys.stdout.isatty() or os.getenv("FORCE_PROGRESS_BAR", "0") == "1"):
        return

    print()
    print("="*100)
    print(f"  ✅ MODEL READY")
    print(f"  Model: {model_name}")
    if src and tgt:
        print(f"  Translation: {src} → {tgt} is now available")
    print("="*100)
    print()


def setup_hf_progress():
    """Configure HuggingFace Hub to show download progress bars."""
    # Set environment variable to enable HF progress bars
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"  # Disable hf_transfer for compatibility

    # Note: Transformers library automatically shows tqdm progress bars
    # when downloading files. We just need to ensure tqdm is available
    # and not suppress it.

    # Ensure we don't disable tqdm in transformers
    if "HF_HUB_DISABLE_PROGRESS_BARS" in os.environ:
        del os.environ["HF_HUB_DISABLE_PROGRESS_BARS"]

    # Ensure we don't disable tqdm in general
    if "TQDM_DISABLE" in os.environ:
        del os.environ["TQDM_DISABLE"]

    logger.debug("Download progress bars enabled")
