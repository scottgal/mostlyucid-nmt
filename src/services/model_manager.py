"""Translation model loading and caching."""

from typing import Any, Optional
from transformers import pipeline

from src.config import config
from src.core.cache import LRUPipelineCache
from src.core.device import device_manager
from src.core.logging import logger
from src.exceptions import ModelLoadError


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
            return src in config.MBART50_LANGS and tgt in config.MBART50_LANGS and src != tgt
        elif family == "m2m100":
            return src in config.M2M100_LANGS and tgt in config.M2M100_LANGS and src != tgt
        elif family == "opus-mt":
            # For Opus-MT, we'd ideally check if the model exists on HuggingFace
            # For now, we assume it's available (will fail at load time if not)
            return src in config.SUPPORTED_LANGS and tgt in config.SUPPORTED_LANGS and src != tgt
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

    def get_pipeline(self, src: str, tgt: str) -> Any:
        """Get or load translation pipeline for language pair with automatic fallback.

        Args:
            src: Source language code
            tgt: Target language code

        Returns:
            Transformers pipeline for translation

        Raises:
            ModelLoadError: If model loading fails for all families
        """
        key = f"{src}->{tgt}"
        cached = self.cache.get(key)

        if cached is not None:
            if config.REQUEST_LOG:
                logger.debug(f"Pipeline cache hit: {key}")
            return cached

        # Determine which model family to use
        families_to_try = []

        if config.AUTO_MODEL_FALLBACK:
            # Parse fallback order
            fallback_families = [f.strip() for f in config.MODEL_FALLBACK_ORDER.split(",") if f.strip()]
            # Filter to only supported families for this pair
            for family in fallback_families:
                if self._is_pair_supported(src, tgt, family):
                    families_to_try.append(family)

            if not families_to_try:
                # No family supports this pair
                raise ModelLoadError(
                    f"{src}->{tgt}",
                    ValueError(f"Language pair {src}->{tgt} not supported by any model family")
                )
        else:
            # No fallback, use configured family only
            families_to_try = [config.MODEL_FAMILY]

        # Try each family in order
        last_error = None
        for family in families_to_try:
            try:
                model_name, src_lang, tgt_lang, family_used = self._get_model_name_and_langs(src, tgt, family)

                if family != config.MODEL_FAMILY:
                    logger.info(f"Using fallback model family '{family}' for {src}->{tgt} (primary '{config.MODEL_FAMILY}' not available)")

                if config.REQUEST_LOG:
                    logger.info(f"Pipeline cache miss: {key}, loading model {model_name} (family: {family})")

                # Build pipeline kwargs
                pipeline_kwargs = {
                    "model": model_name,
                    "device": device_manager.device_index,
                    **self.pipeline_kwargs
                }

                # For mBART50 and M2M100, we need to specify src_lang and tgt_lang
                if family in ("mbart50", "m2m100"):
                    pipeline_kwargs["src_lang"] = src_lang
                    pipeline_kwargs["tgt_lang"] = tgt_lang

                pl = pipeline("translation", **pipeline_kwargs)

                self.cache.put(key, pl)
                logger.info(f"Successfully loaded model: {model_name} ({src}->{tgt}) using family '{family}'")
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
