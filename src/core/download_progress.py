"""Beautiful progress bars for model downloads."""

import os
import sys
from typing import Optional, Dict
from tqdm import tqdm
from huggingface_hub import HfFileSystem

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
