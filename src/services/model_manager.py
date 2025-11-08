"""Translation model loading and caching."""

from typing import Any
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

    def _model_name(self, src: str, tgt: str) -> str:
        """Get Hugging Face model name for language pair.

        Args:
            src: Source language code
            tgt: Target language code

        Returns:
            Model name (e.g., "Helsinki-NLP/opus-mt-en-de")
        """
        return f"Helsinki-NLP/opus-mt-{src}-{tgt}"

    def get_pipeline(self, src: str, tgt: str) -> Any:
        """Get or load translation pipeline for language pair.

        Args:
            src: Source language code
            tgt: Target language code

        Returns:
            Transformers pipeline for translation

        Raises:
            ModelLoadError: If model loading fails
        """
        if config.EASYNMT_MODEL and config.EASYNMT_MODEL != "opus-mt":
            raise ModelLoadError(
                config.EASYNMT_MODEL,
                ValueError(f"Unsupported EASYNMT_MODEL='{config.EASYNMT_MODEL}'. Only 'opus-mt' is supported.")
            )

        key = f"{src}->{tgt}"
        cached = self.cache.get(key)

        if cached is not None:
            if config.REQUEST_LOG:
                logger.debug(f"Pipeline cache hit: {key}")
            return cached

        model_name = self._model_name(src, tgt)
        if config.REQUEST_LOG:
            logger.info(f"Pipeline cache miss: {key}, loading model {model_name}")

        try:
            # Build pipeline with extra kwargs if any
            pl = pipeline(
                "translation",
                model=model_name,
                device=device_manager.device_index,
                **self.pipeline_kwargs
            )

            self.cache.put(key, pl)
            logger.info(f"Successfully loaded model: {model_name}")
            return pl

        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise ModelLoadError(model_name, e)

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

            if src not in config.SUPPORTED_LANGS or tgt not in config.SUPPORTED_LANGS or src == tgt:
                logger.warning(f"Unsupported language pair: {src}->{tgt}")
                continue

            try:
                self.get_pipeline(src, tgt)
                logger.info(f"Preloaded model: {src}->{tgt}")
            except Exception as e:
                logger.warning(f"Failed to preload {src}->{tgt}: {e}")


# Singleton instance
model_manager = ModelManager()
