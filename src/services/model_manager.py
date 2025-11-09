"""Translation model loading and caching."""

from typing import Any, Optional
from transformers import pipeline
import os
import sys

from src.config import config
from src.core.cache import LRUPipelineCache
from src.core.device import device_manager
from src.core.logging import logger
from src.core.download_progress import setup_hf_progress, show_download_banner, show_download_complete
from src.exceptions import ModelLoadError

# Enable beautiful download progress bars
setup_hf_progress()


class ModelManager:
    """Manages loading and caching of translation models."""

    def __init__(self):
        """Initialize model manager with LRU cache."""
        self.cache = LRUPipelineCache(config.MAX_CACHED_MODELS)
        self.pipeline_kwargs = config.parse_model_args()

    def _is_pair_supported(self, src: str, tgt: str, family: str) -> bool:
        """Check if a language pair is supported by a model family.

        Args:
            src: Source language code
            tgt: Target language code
            family: Model family name (opus-mt, mbart50, m2m100)

        Returns:
            True if the pair is supported
        """
        if family == "mbart50":
            result = src in config.MBART50_LANGS and tgt in config.MBART50_LANGS and src != tgt
            logger.info(f"[_is_pair_supported] mbart50: src({src}) in langs={src in config.MBART50_LANGS}, tgt({tgt}) in langs={tgt in config.MBART50_LANGS}, src!=tgt={src != tgt} => {result}")
            return result
        elif family == "m2m100":
            result = src in config.M2M100_LANGS and tgt in config.M2M100_LANGS and src != tgt
            logger.info(f"[_is_pair_supported] m2m100: src({src}) in langs={src in config.M2M100_LANGS}, tgt({tgt}) in langs={tgt in config.M2M100_LANGS}, src!=tgt={src != tgt} => {result}")
            return result
        elif family == "opus-mt":
            # For Opus-MT, we'd ideally check if the model exists on HuggingFace
            # For now, we assume it's available (will fail at load time if not)
            result = src in config.SUPPORTED_LANGS and tgt in config.SUPPORTED_LANGS and src != tgt
            logger.info(f"[_is_pair_supported] opus-mt: src({src}) in langs={src in config.SUPPORTED_LANGS}, tgt({tgt}) in langs={tgt in config.SUPPORTED_LANGS}, src!=tgt={src != tgt} => {result}")
            return result
        logger.info(f"[_is_pair_supported] unknown family: {family} => False")
        return False

    def _get_model_name_and_langs(self, src: str, tgt: str, family: Optional[str] = None) -> tuple[str, str, str, str]:
        """Get Hugging Face model name and language codes for a model family.

        Args:
            src: Source language code
            tgt: Target language code
            family: Model family to use (defaults to config.MODEL_FAMILY)

        Returns:
            Tuple of (model_name, src_lang_code, tgt_lang_code, family_used)

        Raises:
            ModelLoadError: If model family is unsupported
        """
        if family is None:
            family = config.MODEL_FAMILY

        if family == "mbart50":
            # mBART50 uses a single multilingual model
            # Language codes need _XX suffix for mBART50
            return ("facebook/mbart-large-50-many-to-many-mmt", f"{src}_XX", f"{tgt}_XX", "mbart50")
        elif family == "m2m100":
            # M2M_100 uses a single multilingual model (we'll use the 418M version by default)
            return ("facebook/m2m100_418M", src, tgt, "m2m100")
        elif family == "opus-mt":
            # Opus-MT uses separate models for each language pair
            return (f"Helsinki-NLP/opus-mt-{src}-{tgt}", src, tgt, "opus-mt")
        else:
            raise ModelLoadError(
                family,
                ValueError(f"Unsupported MODEL_FAMILY='{family}'. Supported: opus-mt, mbart50, m2m100")
            )

    def get_pipeline(self, src: str, tgt: str, preferred_family: Optional[str] = None) -> Any:
        """Get or load translation pipeline for language pair with automatic fallback.

        Args:
            src: Source language code
            tgt: Target language code
            preferred_family: Preferred model family (opus-mt, mbart50, m2m100).
                            Uses config.MODEL_FAMILY if None.

        Returns:
            Transformers pipeline for translation

        Raises:
            ModelLoadError: If model loading fails for all families
        """
        # Use preferred family in cache key if specified
        family_key = preferred_family or config.MODEL_FAMILY
        key = f"{src}->{tgt}:{family_key}"
        cached = self.cache.get(key)

        if cached is not None:
            if config.REQUEST_LOG:
                logger.debug(f"Pipeline cache hit: {key}")
            return cached

        # Determine which model family to use
        families_to_try = []

        logger.info(f"[ModelManager] AUTO_MODEL_FALLBACK={config.AUTO_MODEL_FALLBACK}, preferred_family={preferred_family}")

        if preferred_family:
            # User requested specific family - try it first
            logger.info(f"[ModelManager] User requested family: {preferred_family}")
            families_to_try.append(preferred_family)  # Always try preferred first

            # If AUTO_MODEL_FALLBACK enabled, add fallback families too
            # This allows falling back even if preferred family "should" support the pair
            # but the actual model doesn't exist (e.g., Helsinki-NLP/opus-mt-en-bn)
            if config.AUTO_MODEL_FALLBACK:
                logger.info(f"[ModelManager] AUTO_MODEL_FALLBACK enabled, adding fallback families after {preferred_family}")
                fallback_families = [f.strip() for f in config.MODEL_FALLBACK_ORDER.split(",") if f.strip()]
                for family in fallback_families:
                    if family != preferred_family and family not in families_to_try:
                        if self._is_pair_supported(src, tgt, family):
                            families_to_try.append(family)
        elif config.AUTO_MODEL_FALLBACK:
            # Parse fallback order
            logger.info(f"[ModelManager] No preferred family, using AUTO_MODEL_FALLBACK")
            fallback_families = [f.strip() for f in config.MODEL_FALLBACK_ORDER.split(",") if f.strip()]
            logger.info(f"[ModelManager] Fallback order: {fallback_families}")
            # Filter to only supported families for this pair
            for family in fallback_families:
                supported = self._is_pair_supported(src, tgt, family)
                logger.info(f"[ModelManager] _is_pair_supported({src}, {tgt}, {family}) = {supported}")
                if supported:
                    families_to_try.append(family)
        else:
            # No fallback, use configured family only
            logger.info(f"[ModelManager] AUTO_MODEL_FALLBACK disabled, using only {config.MODEL_FAMILY}")
            families_to_try = [config.MODEL_FAMILY]

        if not families_to_try:
            # No family supports this pair
            logger.error(f"No families support {src}->{tgt}. Checked: opus-mt={self._is_pair_supported(src, tgt, 'opus-mt')}, mbart50={self._is_pair_supported(src, tgt, 'mbart50')}, m2m100={self._is_pair_supported(src, tgt, 'm2m100')}")
            raise ModelLoadError(
                f"{src}->{tgt}",
                ValueError(f"Language pair {src}->{tgt} not supported by any model family")
            )

        # Try each family in order
        logger.info(f"Trying families for {src}->{tgt}: {families_to_try}")
        last_error = None
        for family in families_to_try:
            try:
                model_name, src_lang, tgt_lang, family_used = self._get_model_name_and_langs(src, tgt, family)

                if family != config.MODEL_FAMILY:
                    logger.info(f"Using fallback model family '{family}' for {src}->{tgt} (primary '{config.MODEL_FAMILY}' not available)")

                # Show nice loading message with download size
                logger.info(f"Loading translation model: {model_name} ({src}->{tgt})")

                # Determine device name for logging
                device_name = "CPU" if device_manager.device_index == -1 else f"GPU (cuda:{device_manager.device_index})"
                logger.info(f"[ModelManager] Loading {family} model on {device_name}")

                # Show download banner with size information
                show_download_banner(model_name, src=src, tgt=tgt, family=family, device=device_name)

                if config.REQUEST_LOG:
                    logger.debug(f"Pipeline cache miss: {key}, loading model {model_name} (family: {family})")

                # Build pipeline kwargs
                # Note: cache_dir is NOT valid for pipeline(), only for model loading
                # Remove cache_dir from pipeline kwargs (transformers uses default HF cache)
                filtered_kwargs = {k: v for k, v in self.pipeline_kwargs.items() if k != "cache_dir"}

                pipeline_kwargs = {
                    "model": model_name,
                    "device": device_manager.device_index,
                    **filtered_kwargs
                }

                # If running a prepacked image with preloaded models, prefer the on-disk snapshot
                # even when an external MODEL_CACHE_DIR is configured. This allows overlay behavior:
                # preloaded models are used, while new downloads go to the external cache.
                try:
                    preloaded_root = os.getenv("PRELOADED_MODELS_DIR", "/app/models")
                    if family == "opus-mt":
                        preloaded_path = os.path.join(preloaded_root, model_name.replace("/", "--"))
                        if os.path.isdir(preloaded_path):
                            pipeline_kwargs["model"] = preloaded_path
                            if config.REQUEST_LOG:
                                logger.info(f"Using preloaded model from disk: {preloaded_path}")
                except Exception:
                    # Non-fatal; fall back to standard hub resolution
                    pass

                # For mBART50 and M2M100, we need to specify src_lang and tgt_lang
                if family in ("mbart50", "m2m100"):
                    pipeline_kwargs["src_lang"] = src_lang
                    pipeline_kwargs["tgt_lang"] = tgt_lang

                pl = pipeline("translation", **pipeline_kwargs)

                # Store in cache with ACTUAL family used, not requested family
                # This ensures multilingual models can be reused across different requests
                actual_key = f"{src}->{tgt}:{family}"
                self.cache.put(actual_key, pl)

                # Also store under requested family key if different (for cache hits next time)
                if actual_key != key:
                    self.cache.put(key, pl)
                    logger.debug(f"[ModelManager] Cached model under both {actual_key} and {key}")

                # Confirm device placement
                model_device = getattr(pl.model, 'device', None)
                if model_device:
                    logger.info(f"[ModelManager] Model loaded on device: {model_device}")
                else:
                    logger.info(f"[ModelManager] Model loaded (device: {device_name})")

                # Show completion banner
                show_download_complete(model_name, src=src, tgt=tgt)

                logger.info(f"Successfully loaded model: {model_name} ({src}->{tgt}) using family '{family}' on {device_name}")
                return pl

            except Exception as e:
                last_error = e
                logger.warning(f"Failed to load model family '{family}' for {src}->{tgt}: {e}")
                continue

        # All families failed
        logger.error(f"Failed to load model for {src}->{tgt} from any family")
        raise ModelLoadError(f"{src}->{tgt}", last_error or Exception("No families to try"))

    def preload_models(self, pairs: str) -> None:
        """Preload translation models at startup.

        Args:
            pairs: Comma or semicolon separated language pairs (e.g., "en->de,de->en")
        """
        if not pairs:
            return

        # Parse pairs
        pair_list = [p.strip() for p in pairs.split(";") if p.strip()]
        if len(pair_list) == 1 and "," in pair_list[0]:
            pair_list = [p.strip() for p in pair_list[0].split(",") if p.strip()]

        supported_langs = config.get_supported_langs()

        for pair in pair_list:
            if "->" not in pair:
                logger.warning(f"Invalid preload pair format: {pair}")
                continue

            src, tgt = pair.split("->", 1)
            src = src.strip()
            tgt = tgt.strip()

            if not src or not tgt:
                logger.warning(f"Empty language code in pair: {pair}")
                continue

            if src not in supported_langs or tgt not in supported_langs or src == tgt:
                logger.warning(f"Unsupported language pair for {config.MODEL_FAMILY}: {src}->{tgt}")
                continue

            try:
                self.get_pipeline(src, tgt)
                logger.info(f"Preloaded model: {src}->{tgt}")
            except Exception as e:
                logger.warning(f"Failed to preload {src}->{tgt}: {e}")


# Singleton instance
model_manager = ModelManager()
