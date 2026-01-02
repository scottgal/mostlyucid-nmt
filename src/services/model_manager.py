"""Translation model loading and caching."""

from typing import Any, Optional
import os
import sys

from src.config import config
from src.core.cache import LRUPipelineCache
from src.core.device import device_manager
from src.core.logging import logger
from src.core.download_progress import setup_hf_progress, show_download_banner, show_download_complete
from src.core.pi_optimizations import pi_optimizer
from src.exceptions import ModelLoadError

# HY-MT wrapper - lazy import to avoid loading unless needed
_hymt_wrapper_class = None
_hymt_import_attempted = False

# MADLAD wrapper - lazy import to avoid loading unless needed
_madlad_wrapper_class = None
_madlad_import_attempted = False


def _get_madlad_wrapper():
    """Lazily import and return the MADLADWrapper class.

    Returns:
        MADLADWrapper class or None if not available
    """
    global _madlad_wrapper_class, _madlad_import_attempted

    if _madlad_import_attempted:
        return _madlad_wrapper_class

    _madlad_import_attempted = True

    try:
        from src.core.madlad_wrapper import MADLADWrapper
        _madlad_wrapper_class = MADLADWrapper
        logger.info("MADLAD-400 wrapper available")
    except ImportError as e:
        logger.warning(f"MADLAD-400 wrapper not available: {e}")

    return _madlad_wrapper_class


def _get_hymt_wrapper():
    """Lazily import and return the HYMTWrapper class.

    Returns:
        HYMTWrapper class or None if not available
    """
    global _hymt_wrapper_class, _hymt_import_attempted

    if _hymt_import_attempted:
        return _hymt_wrapper_class

    _hymt_import_attempted = True

    try:
        from src.core.hymt_wrapper import HYMTWrapper
        _hymt_wrapper_class = HYMTWrapper
        logger.info("HY-MT wrapper available")
    except ImportError as e:
        logger.warning(f"HY-MT wrapper not available: {e}")

    return _hymt_wrapper_class


# Import backend-specific modules
# CT2 backend - only if ctranslate2 is installed
CT2_AVAILABLE = False
if config.TRANSLATION_BACKEND == "ct2":
    try:
        from src.core.ct2_loader import get_ct2_loader
        from src.core.ct2_wrapper import CT2TranslatorWrapper
        CT2_AVAILABLE = True
    except ImportError as e:
        logger.warning(f"CTranslate2 backend requested but not available: {e}")
        CT2_AVAILABLE = False

# Transformers pipeline - LAZY import for PyInstaller compatibility
# In frozen executables, importing transformers at module level causes circular import errors
# We defer the import to first actual use when torch is guaranteed to be fully initialized
_transformers_pipeline = None
_transformers_import_attempted = False
_transformers_import_error = None

def _get_transformers_pipeline():
    """Lazily import and return the transformers pipeline function.

    This defers the import until first actual use, ensuring torch is fully
    initialized before transformers tries to use torch.nn.
    """
    global _transformers_pipeline, _transformers_import_attempted, _transformers_import_error

    if _transformers_import_attempted:
        return _transformers_pipeline

    _transformers_import_attempted = True

    try:
        # Import torch first to ensure it's fully initialized
        import torch
        import torch.nn

        # Now import transformers
        from transformers import pipeline as tf_pipeline
        _transformers_pipeline = tf_pipeline
        logger.info("Translation backend: PyTorch/Transformers (lazy loaded)")
    except ImportError as e:
        _transformers_import_error = e
        logger.warning(f"Transformers backend not available: {e}")

    return _transformers_pipeline

# Log backend availability at startup (CT2 only, transformers is lazy)
if CT2_AVAILABLE:
    logger.info("Translation backend: CTranslate2")

# Enable beautiful download progress bars
setup_hf_progress()

# Configure Pi-specific model caching if on Raspberry Pi
if config.MODEL_CACHE_DIR:
    pi_optimizer.enable_model_caching_to_disk(config.MODEL_CACHE_DIR)


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
            family: Model family name (opus-mt, mbart50, m2m100, hymt)

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
        elif family == "hymt":
            result = src in config.HYMT_LANGS and tgt in config.HYMT_LANGS and src != tgt
            logger.info(f"[_is_pair_supported] hymt: src({src}) in langs={src in config.HYMT_LANGS}, tgt({tgt}) in langs={tgt in config.HYMT_LANGS}, src!=tgt={src != tgt} => {result}")
            return result
        elif family == "madlad":
            result = src in config.MADLAD_LANGS and tgt in config.MADLAD_LANGS and src != tgt
            logger.info(f"[_is_pair_supported] madlad: src({src}) in langs={src in config.MADLAD_LANGS}, tgt({tgt}) in langs={tgt in config.MADLAD_LANGS}, src!=tgt={src != tgt} => {result}")
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
        elif family == "hymt":
            # HY-MT uses LLM-based translation (Tencent Hunyuan)
            from src.core.hymt_wrapper import get_hymt_model_name
            return (get_hymt_model_name(), src, tgt, "hymt")
        elif family == "madlad":
            # MADLAD-400 uses T5-based translation with <2xx> prefixes
            from src.core.madlad_wrapper import get_madlad_model_name
            return (get_madlad_model_name(), src, tgt, "madlad")
        elif family == "opus-mt":
            # Opus-MT uses separate models for each language pair
            return (f"Helsinki-NLP/opus-mt-{src}-{tgt}", src, tgt, "opus-mt")
        else:
            raise ModelLoadError(
                family,
                ValueError(f"Unsupported MODEL_FAMILY='{family}'. Supported: opus-mt, mbart50, m2m100, hymt, madlad")
            )

    def get_pipeline(self, src: str, tgt: str, preferred_family: Optional[str] = None) -> Any:
        """Get or load translation pipeline for language pair with automatic fallback.

        Args:
            src: Source language code
            tgt: Target language code
            preferred_family: Preferred model family (opus-mt, mbart50, m2m100).
                            Uses config.MODEL_FAMILY if None.

        Returns:
            Translator (CT2TranslatorWrapper or transformers pipeline)

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
        families_to_try = self._get_families_to_try(src, tgt, preferred_family)

        if not families_to_try:
            # No family supports this pair
            logger.error(f"No families support {src}->{tgt}. Checked: opus-mt={self._is_pair_supported(src, tgt, 'opus-mt')}, mbart50={self._is_pair_supported(src, tgt, 'mbart50')}, m2m100={self._is_pair_supported(src, tgt, 'm2m100')}, hymt={self._is_pair_supported(src, tgt, 'hymt')}, madlad={self._is_pair_supported(src, tgt, 'madlad')}")
            raise ModelLoadError(
                f"{src}->{tgt}",
                ValueError(f"Language pair {src}->{tgt} not supported by any model family")
            )

        # Try each family in order
        logger.info(f"Trying families for {src}->{tgt}: {families_to_try} (backend: {config.TRANSLATION_BACKEND})")
        last_error = None

        for family in families_to_try:
            try:
                # HY-MT uses its own LLM-based loader
                if family == "hymt":
                    pl = self._load_hymt_model(src, tgt, key)
                # MADLAD uses its own T5-based loader
                elif family == "madlad":
                    pl = self._load_madlad_model(src, tgt, key)
                # Use CT2 backend if available (not for hymt/madlad)
                elif CT2_AVAILABLE and config.TRANSLATION_BACKEND == "ct2":
                    pl = self._load_ct2_translator(src, tgt, family, key)
                elif _get_transformers_pipeline() is not None:
                    pl = self._load_transformers_pipeline(src, tgt, family, key)
                else:
                    raise ModelLoadError(
                        f"{src}->{tgt}",
                        ImportError("No translation backend available. Install ctranslate2 or transformers.")
                    )

                return pl

            except Exception as e:
                last_error = e
                logger.warning(f"Failed to load model family '{family}' for {src}->{tgt}: {e}")
                continue

        # All families failed
        logger.error(f"Failed to load model for {src}->{tgt} from any family")
        raise ModelLoadError(f"{src}->{tgt}", last_error or Exception("No families to try"))

    def _get_families_to_try(self, src: str, tgt: str, preferred_family: Optional[str]) -> list:
        """Determine which model families to try for a language pair."""
        families_to_try = []

        logger.info(f"[ModelManager] AUTO_MODEL_FALLBACK={config.AUTO_MODEL_FALLBACK}, preferred_family={preferred_family}")

        if preferred_family:
            # User requested specific family - try it first
            logger.info(f"[ModelManager] User requested family: {preferred_family}")
            families_to_try.append(preferred_family)

            # If AUTO_MODEL_FALLBACK enabled, add fallback families too
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
            for family in fallback_families:
                supported = self._is_pair_supported(src, tgt, family)
                logger.info(f"[ModelManager] _is_pair_supported({src}, {tgt}, {family}) = {supported}")
                if supported:
                    families_to_try.append(family)
        else:
            # No fallback, use configured family only
            logger.info(f"[ModelManager] AUTO_MODEL_FALLBACK disabled, using only {config.MODEL_FAMILY}")
            families_to_try = [config.MODEL_FAMILY]

        return families_to_try

    def _load_ct2_translator(self, src: str, tgt: str, family: str, cache_key: str) -> Any:
        """Load a CTranslate2 translator for a language pair.

        Args:
            src: Source language code
            tgt: Target language code
            family: Model family (opus-mt, mbart50, m2m100)
            cache_key: Cache key for storing the translator

        Returns:
            CT2TranslatorWrapper instance
        """
        model_name, src_lang, tgt_lang, family_used = self._get_model_name_and_langs(src, tgt, family)

        if family != config.MODEL_FAMILY:
            logger.info(f"Using fallback model family '{family}' for {src}->{tgt}")

        # Determine device
        device = "cuda" if device_manager.device_index >= 0 else "cpu"
        device_name = "CPU" if device == "cpu" else f"GPU (cuda:{device_manager.device_index})"

        logger.info(f"Loading CT2 model: {model_name} ({src}->{tgt}) on {device_name}")
        show_download_banner(model_name, src=src, tgt=tgt, family=family, device=device_name)

        # Get CT2 model path (handles download/conversion)
        ct2_loader = get_ct2_loader()
        model_path, tokenizer_name = ct2_loader.get_model_path(src, tgt, family)

        # Create CT2 wrapper
        pl = CT2TranslatorWrapper(
            model_path=str(model_path),
            tokenizer_name=tokenizer_name,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            device=device,
            device_index=device_manager.device_index if device_manager.device_index >= 0 else 0,
            family=family_used,
        )

        # Cache the translator
        actual_key = f"{src}->{tgt}:{family}"
        self.cache.put(actual_key, pl)

        if actual_key != cache_key:
            self.cache.put(cache_key, pl)
            logger.debug(f"[ModelManager] Cached model under both {actual_key} and {cache_key}")

        show_download_complete(model_name, src=src, tgt=tgt)
        logger.info(f"Successfully loaded CT2 model: {model_name} ({src}->{tgt}) using family '{family}' on {device_name}")

        return pl

    def _load_transformers_pipeline(self, src: str, tgt: str, family: str, cache_key: str) -> Any:
        """Load a transformers pipeline for a language pair (legacy backend).

        Args:
            src: Source language code
            tgt: Target language code
            family: Model family (opus-mt, mbart50, m2m100)
            cache_key: Cache key for storing the pipeline

        Returns:
            Transformers pipeline instance
        """
        model_name, src_lang, tgt_lang, family_used = self._get_model_name_and_langs(src, tgt, family)

        if family != config.MODEL_FAMILY:
            logger.info(f"Using fallback model family '{family}' for {src}->{tgt}")

        device_name = "CPU" if device_manager.device_index == -1 else f"GPU (cuda:{device_manager.device_index})"
        logger.info(f"Loading transformers model: {model_name} ({src}->{tgt}) on {device_name}")

        show_download_banner(model_name, src=src, tgt=tgt, family=family, device=device_name)

        if config.REQUEST_LOG:
            logger.debug(f"Pipeline cache miss: {cache_key}, loading model {model_name} (family: {family})")

        # Build pipeline kwargs
        filtered_kwargs = {k: v for k, v in self.pipeline_kwargs.items() if k != "cache_dir"}

        # Get Pi-specific optimizations
        pi_kwargs = pi_optimizer.get_pipeline_kwargs()
        model_kwargs = pi_optimizer.get_model_loading_kwargs()

        pipeline_kwargs = {
            "model": model_name,
            "device": device_manager.device_index,
            "model_kwargs": model_kwargs,
            **filtered_kwargs,
            **pi_kwargs,
        }

        # Check for preloaded models
        try:
            preloaded_root = os.getenv("PRELOADED_MODELS_DIR", "/app/models")
            if family == "opus-mt":
                preloaded_path = os.path.join(preloaded_root, model_name.replace("/", "--"))
                if os.path.isdir(preloaded_path):
                    pipeline_kwargs["model"] = preloaded_path
                    if config.REQUEST_LOG:
                        logger.info(f"Using preloaded model from disk: {preloaded_path}")
        except Exception:
            pass

        # For multilingual models, add language params
        if family in ("mbart50", "m2m100"):
            pipeline_kwargs["src_lang"] = src_lang
            pipeline_kwargs["tgt_lang"] = tgt_lang

        pipeline_func = _get_transformers_pipeline()
        pl = pipeline_func("translation", **pipeline_kwargs)

        # Apply Pi-specific post-load optimizations
        if hasattr(pl, 'model'):
            pi_optimizer.optimize_after_model_load(pl.model)

        # Cache the pipeline
        actual_key = f"{src}->{tgt}:{family}"
        self.cache.put(actual_key, pl)

        if actual_key != cache_key:
            self.cache.put(cache_key, pl)
            logger.debug(f"[ModelManager] Cached model under both {actual_key} and {cache_key}")

        # Confirm device placement
        model_device = getattr(pl.model, 'device', None)
        if model_device:
            logger.info(f"[ModelManager] Model loaded on device: {model_device}")
        else:
            logger.info(f"[ModelManager] Model loaded (device: {device_name})")

        show_download_complete(model_name, src=src, tgt=tgt)
        logger.info(f"Successfully loaded transformers model: {model_name} ({src}->{tgt}) using family '{family}' on {device_name}")

        return pl

    def _load_hymt_model(self, src: str, tgt: str, cache_key: str) -> Any:
        """Load HY-MT (Hunyuan Translation) model for a language pair.

        HY-MT is an LLM-based translation model from Tencent that uses
        chat-style prompts rather than traditional translation pipelines.

        Args:
            src: Source language code
            tgt: Target language code
            cache_key: Cache key for storing the model

        Returns:
            HYMTWrapper instance (pipeline-compatible)
        """
        import torch

        model_name, src_lang, tgt_lang, family_used = self._get_model_name_and_langs(src, tgt, "hymt")

        device_name = "CPU" if device_manager.device_index == -1 else f"GPU (cuda:{device_manager.device_index})"
        logger.info(f"Loading HY-MT model: {model_name} ({src}->{tgt}) on {device_name}")

        show_download_banner(model_name, src=src, tgt=tgt, family="hymt", device=device_name)

        # Get HY-MT wrapper class
        HYMTWrapper = _get_hymt_wrapper()
        if HYMTWrapper is None:
            raise ModelLoadError(
                model_name,
                ImportError("HY-MT wrapper not available. Check transformers installation.")
            )

        # Determine device and dtype
        if device_manager.device_index >= 0:
            device = "cuda"
            torch_dtype = torch.bfloat16  # Use bfloat16 on GPU for efficiency
        else:
            device = "cpu"
            torch_dtype = torch.float32  # Full precision on CPU

        # Check for user-specified dtype
        if "torch_dtype" in self.pipeline_kwargs:
            torch_dtype = self.pipeline_kwargs["torch_dtype"]

        # Create HY-MT wrapper
        wrapper = HYMTWrapper(
            model_name=model_name,
            device=device,
            device_index=device_manager.device_index if device_manager.device_index >= 0 else 0,
            torch_dtype=torch_dtype,
        )

        # Store target language in wrapper for translation calls
        # The wrapper needs this since HY-MT uses prompts, not src/tgt params
        wrapper._default_tgt_lang = tgt_lang

        # Wrap the wrapper to automatically pass tgt_lang
        class HYMTTranslatorProxy:
            """Proxy that auto-injects tgt_lang for pipeline compatibility."""

            def __init__(self, hymt_wrapper, tgt_lang: str):
                self._wrapper = hymt_wrapper
                self._tgt_lang = tgt_lang
                # Copy model attribute for device checking
                self.model = hymt_wrapper.model

            def __call__(self, texts, **kwargs):
                # Always inject tgt_lang if not provided
                if "tgt_lang" not in kwargs:
                    kwargs["tgt_lang"] = self._tgt_lang
                return self._wrapper(texts, **kwargs)

        proxy = HYMTTranslatorProxy(wrapper, tgt_lang)

        # Cache the proxy
        actual_key = f"{src}->{tgt}:hymt"
        self.cache.put(actual_key, proxy)

        if actual_key != cache_key:
            self.cache.put(cache_key, proxy)
            logger.debug(f"[ModelManager] Cached HY-MT model under both {actual_key} and {cache_key}")

        show_download_complete(model_name, src=src, tgt=tgt)
        logger.info(f"Successfully loaded HY-MT model: {model_name} ({src}->{tgt}) on {device_name}")

        return proxy

    def _load_madlad_model(self, src: str, tgt: str, cache_key: str) -> Any:
        """Load MADLAD-400 model for a language pair.

        MADLAD-400 is a T5-based multilingual translation model supporting 400+ languages.
        It uses language prefixes like <2de> for target language specification.

        Args:
            src: Source language code
            tgt: Target language code
            cache_key: Cache key for storing the model

        Returns:
            MADLADWrapper instance (pipeline-compatible)
        """
        import torch

        model_name, src_lang, tgt_lang, family_used = self._get_model_name_and_langs(src, tgt, "madlad")

        device_name = "CPU" if device_manager.device_index == -1 else f"GPU (cuda:{device_manager.device_index})"
        logger.info(f"Loading MADLAD model: {model_name} ({src}->{tgt}) on {device_name}")

        show_download_banner(model_name, src=src, tgt=tgt, family="madlad", device=device_name)

        # Get MADLAD wrapper class
        MADLADWrapper = _get_madlad_wrapper()
        if MADLADWrapper is None:
            raise ModelLoadError(
                model_name,
                ImportError("MADLAD-400 wrapper not available. Check transformers installation.")
            )

        # Determine device and dtype
        if device_manager.device_index >= 0:
            device = "cuda"
            torch_dtype = torch.bfloat16  # Use bfloat16 on GPU for efficiency
        else:
            device = "cpu"
            torch_dtype = torch.float32  # Full precision on CPU

        # Check for user-specified dtype
        if "torch_dtype" in self.pipeline_kwargs:
            torch_dtype = self.pipeline_kwargs["torch_dtype"]

        # Create MADLAD wrapper
        wrapper = MADLADWrapper(
            model_name=model_name,
            device=device,
            device_index=device_manager.device_index if device_manager.device_index >= 0 else 0,
            torch_dtype=torch_dtype,
        )

        # Wrap the wrapper to automatically pass tgt_lang
        class MADLADTranslatorProxy:
            """Proxy that auto-injects tgt_lang for pipeline compatibility."""

            def __init__(self, madlad_wrapper, tgt_lang: str):
                self._wrapper = madlad_wrapper
                self._tgt_lang = tgt_lang
                # Copy model attribute for device checking
                self.model = madlad_wrapper.model

            def __call__(self, texts, **kwargs):
                # Always inject tgt_lang if not provided
                if "tgt_lang" not in kwargs:
                    kwargs["tgt_lang"] = self._tgt_lang
                return self._wrapper(texts, **kwargs)

        proxy = MADLADTranslatorProxy(wrapper, tgt_lang)

        # Cache the proxy
        actual_key = f"{src}->{tgt}:madlad"
        self.cache.put(actual_key, proxy)

        if actual_key != cache_key:
            self.cache.put(cache_key, proxy)
            logger.debug(f"[ModelManager] Cached MADLAD model under both {actual_key} and {cache_key}")

        show_download_complete(model_name, src=src, tgt=tgt)
        logger.info(f"Successfully loaded MADLAD model: {model_name} ({src}->{tgt}) on {device_name}")

        return proxy

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
