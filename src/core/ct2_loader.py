"""CTranslate2 model loading, conversion, and caching."""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple
from huggingface_hub import HfApi, hf_hub_download, snapshot_download

from src.config import config
from src.core.logging import logger


# Pre-converted CT2 model patterns on HuggingFace
# These are downloaded directly without needing conversion (instant!)
#
# Coverage:
#   - Opus-MT: 2,177 models from gaudi/ (covers virtually all pairs)
#   - M2M100: Full model from michaelfeil/
#   - mBART50: No pre-converted available (converts on first use, ~5-10 min)
#
CT2_PRECONVERTED = {
    "opus-mt": {
        "pattern": "gaudi/opus-mt-{src}-{tgt}-ctranslate2",
        "check_exists": True,  # Verify pair exists (most do, 2177 available)
    },
    "mbart50": {
        "repo": None,  # No known pre-converted - converts on first use (~5-10 min)
    },
    "m2m100": {
        "repo": "michaelfeil/ct2fast-m2m100_418M",
        "check_exists": False,  # Single repo for all 100 languages
    },
}


class CT2ModelLoader:
    """Handles CTranslate2 model discovery, conversion, and caching.

    Strategy:
    1. Check local disk cache first
    2. Check for pre-converted CT2 model on HuggingFace
    3. Download HF model and convert to CT2
    4. Save to disk cache for future use
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize CT2 model loader.

        Args:
            cache_dir: Base cache directory. Defaults to ~/.cache/mostlylucid-nmt
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir) / "ct2"
        else:
            self.cache_dir = Path.home() / ".cache" / "mostlylucid-nmt" / "ct2"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hf_api = HfApi()
        self._preconverted_cache: dict[str, bool] = {}  # Cache HF existence checks

        logger.info(f"CT2ModelLoader initialized with cache: {self.cache_dir}")

    def get_model_path(self, src: str, tgt: str, family: str) -> Tuple[Path, str]:
        """Get path to CT2 model, downloading/converting if needed.

        Args:
            src: Source language code
            tgt: Target language code
            family: Model family (opus-mt, mbart50, m2m100)

        Returns:
            Tuple of (model_path, tokenizer_name) where tokenizer_name is the
            HuggingFace model ID for loading the tokenizer
        """
        # Get the original HF model name (for tokenizer)
        hf_model_name = self._get_hf_model_name(src, tgt, family)

        # 1. Check local cache
        local_path = self._check_local_cache(src, tgt, family)
        if local_path:
            logger.info(f"CT2 model found in local cache: {local_path}")
            return local_path, hf_model_name

        # 2. Check for pre-converted on HuggingFace
        preconverted_repo = self._check_preconverted_hf(src, tgt, family)
        if preconverted_repo:
            logger.info(f"Downloading pre-converted CT2 model: {preconverted_repo}")
            local_path = self._download_preconverted(preconverted_repo, src, tgt, family)
            return local_path, hf_model_name

        # 3. Convert from HuggingFace model
        logger.info(f"Converting {hf_model_name} to CTranslate2 format...")
        local_path = self._convert_to_ct2(hf_model_name, src, tgt, family)
        return local_path, hf_model_name

    def _get_hf_model_name(self, src: str, tgt: str, family: str) -> str:
        """Get HuggingFace model name for a language pair."""
        if family == "opus-mt":
            return f"Helsinki-NLP/opus-mt-{src}-{tgt}"
        elif family == "mbart50":
            return "facebook/mbart-large-50-many-to-many-mmt"
        elif family == "m2m100":
            return "facebook/m2m100_418M"
        else:
            raise ValueError(f"Unknown model family: {family}")

    def _get_cache_key(self, src: str, tgt: str, family: str) -> str:
        """Get cache key for a model."""
        if family in ("mbart50", "m2m100"):
            # Multilingual models - single cache entry
            return f"{family}/all"
        else:
            # Per-pair models
            return f"{family}/{src}-{tgt}"

    def _check_local_cache(self, src: str, tgt: str, family: str) -> Optional[Path]:
        """Check if model exists in local CT2 cache."""
        cache_key = self._get_cache_key(src, tgt, family)
        model_path = self.cache_dir / cache_key

        # Check for CT2 model marker files
        if model_path.exists() and (model_path / "model.bin").exists():
            return model_path

        return None

    def _check_preconverted_hf(self, src: str, tgt: str, family: str) -> Optional[str]:
        """Check for pre-converted CT2 model on HuggingFace.

        Returns:
            Repository ID if pre-converted model exists, None otherwise
        """
        family_config = CT2_PRECONVERTED.get(family, {})

        # Check for single repo (m2m100)
        if "repo" in family_config and family_config["repo"]:
            return family_config["repo"]

        # Check for pattern-based repos (opus-mt)
        if "pattern" in family_config:
            pattern = family_config["pattern"]
            repo_id = pattern.format(src=src, tgt=tgt)

            # Check cache first
            if repo_id in self._preconverted_cache:
                return repo_id if self._preconverted_cache[repo_id] else None

            # Verify repo exists on HuggingFace
            if family_config.get("check_exists", True):
                try:
                    self.hf_api.repo_info(repo_id, repo_type="model")
                    self._preconverted_cache[repo_id] = True
                    return repo_id
                except Exception:
                    self._preconverted_cache[repo_id] = False
                    return None
            else:
                return repo_id

        return None

    def _download_preconverted(self, repo_id: str, src: str, tgt: str, family: str) -> Path:
        """Download pre-converted CT2 model from HuggingFace."""
        cache_key = self._get_cache_key(src, tgt, family)
        local_path = self.cache_dir / cache_key
        local_path.mkdir(parents=True, exist_ok=True)

        try:
            # Download entire repo
            downloaded_path = snapshot_download(
                repo_id=repo_id,
                local_dir=str(local_path),
                local_dir_use_symlinks=False,
            )

            # Write source info
            (local_path / "source_model.txt").write_text(repo_id)

            logger.info(f"Downloaded pre-converted model to: {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"Failed to download {repo_id}: {e}")
            # Clean up partial download
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)
            raise

    def _convert_to_ct2(self, hf_model_name: str, src: str, tgt: str, family: str) -> Path:
        """Convert HuggingFace model to CTranslate2 format.

        Uses ct2-transformers-converter CLI tool.
        """
        cache_key = self._get_cache_key(src, tgt, family)
        local_path = self.cache_dir / cache_key

        # Skip if already converted (race condition protection)
        if local_path.exists() and (local_path / "model.bin").exists():
            return local_path

        local_path.mkdir(parents=True, exist_ok=True)

        # Build conversion command
        cmd = [
            "ct2-transformers-converter",
            "--model", hf_model_name,
            "--output_dir", str(local_path),
            "--force",
        ]

        # Only add quantization if not 'default' (CT2 uses float32 by default)
        if config.CT2_QUANTIZATION and config.CT2_QUANTIZATION.lower() != "default":
            cmd.extend(["--quantization", config.CT2_QUANTIZATION])

        # Add low_cpu_mem_usage for large models
        if family in ("mbart50", "m2m100"):
            cmd.append("--low_cpu_mem_usage")

        logger.info(f"Converting model: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=1800,  # 30 minute timeout for large models
            )

            # Write source info
            (local_path / "source_model.txt").write_text(hf_model_name)

            logger.info(f"Model converted successfully: {local_path}")
            if result.stdout:
                logger.debug(f"Converter output: {result.stdout}")

            return local_path

        except subprocess.CalledProcessError as e:
            logger.error(f"Conversion failed: {e.stderr}")
            # Clean up failed conversion
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)
            raise RuntimeError(f"Failed to convert {hf_model_name}: {e.stderr}")

        except subprocess.TimeoutExpired:
            logger.error(f"Conversion timed out for {hf_model_name}")
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)
            raise RuntimeError(f"Conversion timed out for {hf_model_name}")

    def clear_cache(self, family: Optional[str] = None) -> int:
        """Clear cached CT2 models.

        Args:
            family: Specific family to clear, or None for all

        Returns:
            Number of models cleared
        """
        count = 0

        if family:
            family_path = self.cache_dir / family
            if family_path.exists():
                shutil.rmtree(family_path)
                count = 1
        else:
            for family_path in self.cache_dir.iterdir():
                if family_path.is_dir():
                    shutil.rmtree(family_path)
                    count += 1

        logger.info(f"Cleared {count} cached CT2 model(s)")
        return count

    def get_cache_info(self) -> dict:
        """Get information about cached models."""
        info = {
            "cache_dir": str(self.cache_dir),
            "families": {},
            "total_size_mb": 0,
        }

        for family_path in self.cache_dir.iterdir():
            if not family_path.is_dir():
                continue

            family_name = family_path.name
            models = []
            family_size = 0

            for model_path in family_path.iterdir():
                if not model_path.is_dir():
                    continue

                # Calculate size
                size = sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file())
                family_size += size

                # Get source model info
                source_file = model_path / "source_model.txt"
                source = source_file.read_text().strip() if source_file.exists() else "unknown"

                models.append({
                    "name": model_path.name,
                    "source": source,
                    "size_mb": round(size / 1024 / 1024, 2),
                })

            info["families"][family_name] = {
                "models": models,
                "total_size_mb": round(family_size / 1024 / 1024, 2),
            }
            info["total_size_mb"] += family_size / 1024 / 1024

        info["total_size_mb"] = round(info["total_size_mb"], 2)
        return info


# Singleton instance (lazy-initialized)
_ct2_loader: Optional[CT2ModelLoader] = None


def get_ct2_loader() -> CT2ModelLoader:
    """Get the singleton CT2ModelLoader instance."""
    global _ct2_loader
    if _ct2_loader is None:
        _ct2_loader = CT2ModelLoader(config.MODEL_CACHE_DIR)
    return _ct2_loader
