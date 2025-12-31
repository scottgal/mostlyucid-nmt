"""Configuration management for the translator service."""

import os
import json
from typing import Optional, Dict, Any, List

# Torch is optional - only needed for transformers backend
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    TORCH_AVAILABLE = False


class Config:
    """Centralized configuration from environment variables."""

    # Application
    VERSION = "3.5.0"
    TITLE = "mostlylucid-nmt"

    # Supported language codes (Opus-MT)
    # This is a comprehensive list of major languages. For the complete list,
    # use the /discover/opus-mt endpoint which queries Hugging Face dynamically.
    SUPPORTED_LANGS: List[str] = [
        # Germanic languages
        "en", "de", "nl", "sv", "da", "no", "is", "af",
        # Romance languages
        "es", "fr", "it", "pt", "ro", "ca", "gl",
        # Slavic languages
        "ru", "pl", "uk", "cs", "sk", "bg", "hr", "sr", "sl", "mk", "be",
        # Other European
        "el", "fi", "hu", "et", "lv", "lt", "ga", "cy", "eu", "sq", "mt",
        # Asian languages
        "zh", "ja", "ko", "ar", "he", "fa", "hi", "ur", "bn", "ta", "te", "th",
        "vi", "id", "ms", "tr", "az", "ka", "hy", "kk", "uz",
        # African languages
        "sw", "am", "so", "yo", "ha", "ig",
        # Other
        "eo", "la",
    ]

    # mBART50 language codes (50 languages)
    MBART50_LANGS: List[str] = [
        "ar", "cs", "de", "en", "es", "et", "fi", "fr", "gu", "hi",
        "it", "ja", "kk", "ko", "lt", "lv", "my", "ne", "nl", "ro",
        "ru", "si", "tr", "vi", "zh", "af", "az", "bn", "fa", "he",
        "hr", "id", "ka", "km", "mk", "ml", "mn", "mr", "pl", "ps",
        "pt", "sv", "sw", "ta", "te", "th", "tl", "uk", "ur", "xh",
    ]

    # M2M100 language codes (100 languages)
    M2M100_LANGS: List[str] = [
        "af", "am", "ar", "ast", "az", "ba", "be", "bg", "bn", "br",
        "bs", "ca", "ceb", "cs", "cy", "da", "de", "el", "en", "es",
        "et", "fa", "ff", "fi", "fr", "fy", "ga", "gd", "gl", "gu",
        "ha", "he", "hi", "hr", "ht", "hu", "hy", "id", "ig", "ilo",
        "is", "it", "ja", "jv", "ka", "kk", "km", "kn", "ko", "lb",
        "lg", "ln", "lo", "lt", "lv", "mg", "mk", "ml", "mn", "mr",
        "ms", "my", "ne", "nl", "no", "ns", "oc", "or", "pa", "pl",
        "ps", "pt", "ro", "ru", "sd", "si", "sk", "sl", "so", "sq",
        "sr", "ss", "su", "sv", "sw", "ta", "te", "th", "tl", "tn",
        "tr", "uk", "ur", "uz", "vi", "wo", "xh", "yi", "yo", "zh",
    ]

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()  # Changed default from DEBUG to INFO
    REQUEST_LOG: bool = os.getenv("REQUEST_LOG", "1").lower() in ("1", "true", "yes")  # Changed default to enabled
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "plain").lower()  # plain|json
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "0").lower() in ("1", "true", "yes")
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "/var/log/mostlylucid-nmt/app.log")
    LOG_FILE_MAX_BYTES: int = int(os.getenv("LOG_FILE_MAX_BYTES", "10485760"))  # 10MB
    LOG_FILE_BACKUP_COUNT: int = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))
    LOG_INCLUDE_TEXT: bool = os.getenv("LOG_INCLUDE_TEXT", "0").lower() in ("1", "true", "yes")

    # Device selection
    USE_GPU: str = os.getenv("USE_GPU", "auto").lower()  # "true", "false", or "auto"
    DEVICE_ENV: str = os.getenv("DEVICE", "auto")  # e.g., "cuda", "cuda:0", "cpu"

    # Model configuration
    EASYNMT_MODEL: str = os.getenv("EASYNMT_MODEL", "opus-mt")
    MODEL_FAMILY: str = os.getenv("MODEL_FAMILY", "opus-mt").lower()  # opus-mt, mbart50, m2m100
    EASYNMT_MODEL_ARGS_RAW: str = os.getenv("EASYNMT_MODEL_ARGS", "{}")
    EASYNMT_MAX_TEXT_LEN: Optional[str] = os.getenv("EASYNMT_MAX_TEXT_LEN")
    EASYNMT_MAX_TEXT_LEN_INT: Optional[int] = (
        int(EASYNMT_MAX_TEXT_LEN) if (EASYNMT_MAX_TEXT_LEN and EASYNMT_MAX_TEXT_LEN.isdigit()) else None
    )
    EASYNMT_MAX_BEAM_SIZE: Optional[str] = os.getenv("EASYNMT_MAX_BEAM_SIZE")
    EASYNMT_MAX_BEAM_SIZE_INT: Optional[int] = (
        int(EASYNMT_MAX_BEAM_SIZE) if (EASYNMT_MAX_BEAM_SIZE and EASYNMT_MAX_BEAM_SIZE.isdigit()) else None
    )
    EASYNMT_BATCH_SIZE: int = int(os.getenv("EASYNMT_BATCH_SIZE", "16"))
    EASYNMT_RESPONSE_MODE: str = os.getenv("EASYNMT_RESPONSE_MODE", "strings").lower()  # "strings" or "objects"

    # Cache - Keep multiple models loaded in memory (GPU/CPU) for instant switching
    # Each cached model takes ~300MB-2GB of RAM/VRAM depending on model family
    # Increase this to keep more models loaded (no reload wait time)
    # Decrease if running out of memory
    MAX_CACHED_MODELS: int = int(os.getenv("MAX_CACHED_MODELS", "10"))

    # Worker pools
    MAX_WORKERS_BACKEND: int = int(os.getenv("MAX_WORKERS_BACKEND", "1"))
    MAX_WORKERS_FRONTEND: int = int(os.getenv("MAX_WORKERS_FRONTEND", "2"))

    # Input sanitization
    INPUT_SANITIZE: bool = os.getenv("INPUT_SANITIZE", "1").lower() in ("1", "true", "yes")
    INPUT_MIN_ALNUM_RATIO: float = float(os.getenv("INPUT_MIN_ALNUM_RATIO", "0.2"))
    INPUT_MIN_CHARS: int = int(os.getenv("INPUT_MIN_CHARS", "1"))
    UNDETERMINED_LANG_CODE: str = os.getenv("UNDETERMINED_LANG_CODE", "und")

    # Response alignment and sentence splitting
    ALIGN_RESPONSES: bool = os.getenv("ALIGN_RESPONSES", "1").lower() in ("1", "true", "yes")
    SANITIZE_PLACEHOLDER: str = os.getenv("SANITIZE_PLACEHOLDER", "")
    PERFORM_SENTENCE_SPLITTING_DEFAULT: bool = (
        os.getenv("PERFORM_SENTENCE_SPLITTING_DEFAULT", "1").lower() in ("1", "true", "yes")
    )
    MAX_SENTENCE_CHARS: int = int(os.getenv("MAX_SENTENCE_CHARS", "500"))
    MAX_CHUNK_CHARS: int = int(os.getenv("MAX_CHUNK_CHARS", "900"))
    JOIN_SENTENCES_WITH: str = os.getenv("JOIN_SENTENCES_WITH", " ")

    # Symbol masking
    SYMBOL_MASKING: bool = os.getenv("SYMBOL_MASKING", "1").lower() in ("1", "true", "yes")
    MASK_DIGITS: bool = os.getenv("MASK_DIGITS", "1").lower() in ("1", "true", "yes")
    MASK_PUNCT: bool = os.getenv("MASK_PUNCT", "1").lower() in ("1", "true", "yes")
    MASK_EMOJI: bool = os.getenv("MASK_EMOJI", "1").lower() in ("1", "true", "yes")

    # Pivot fallback
    PIVOT_FALLBACK: bool = os.getenv("PIVOT_FALLBACK", "1").lower() in ("1", "true", "yes")
    PIVOT_LANG: str = os.getenv("PIVOT_LANG", "en")

    # Queueing and backpressure
    ENABLE_QUEUE: bool = os.getenv("ENABLE_QUEUE", "1").lower() in ("1", "true", "yes")
    MAX_INFLIGHT_TRANSLATIONS_RAW: Optional[str] = os.getenv("MAX_INFLIGHT_TRANSLATIONS")
    MAX_QUEUE_SIZE: int = int(os.getenv("MAX_QUEUE_SIZE", "1000"))
    TRANSLATE_TIMEOUT_SEC: int = int(os.getenv("TRANSLATE_TIMEOUT_SEC", "0"))  # 0 = no extra timeout

    # Retry-After estimation
    RETRY_AFTER_MAX_SEC: int = int(os.getenv("RETRY_AFTER_MAX_SEC", "120"))
    RETRY_AFTER_MIN_SEC: float = float(os.getenv("RETRY_AFTER_MIN_SEC", "1"))
    RETRY_AFTER_ALPHA: float = float(os.getenv("RETRY_AFTER_ALPHA", "0.2"))  # EMA smoothing factor

    # Maintenance
    CUDA_CACHE_CLEAR_INTERVAL_SEC: int = int(os.getenv("CUDA_CACHE_CLEAR_INTERVAL_SEC", "0"))  # 0 disables

    # Preloading
    PRELOAD_MODELS: str = os.getenv("PRELOAD_MODELS", "").strip()

    # Model cache directory (for volume mapping in Docker)
    MODEL_CACHE_DIR: Optional[str] = os.getenv("MODEL_CACHE_DIR", None)

    # Auto-fallback to other model families if pair not available
    AUTO_MODEL_FALLBACK: bool = os.getenv("AUTO_MODEL_FALLBACK", "1").lower() in ("1", "true", "yes")

    # Priority order for model family fallback (comma-separated)
    # Default: opus-mt first (best quality), then mbart50, then m2m100 (broadest coverage)
    MODEL_FALLBACK_ORDER: str = os.getenv("MODEL_FALLBACK_ORDER", "opus-mt,mbart50,m2m100")

    # Auto-chunking for large inputs
    AUTO_CHUNK_ENABLED: bool = os.getenv("AUTO_CHUNK_ENABLED", "1").lower() in ("1", "true", "yes")
    AUTO_CHUNK_MAX_CHARS: int = int(os.getenv("AUTO_CHUNK_MAX_CHARS", "5000"))  # Safe default per chunk

    # Maximum input text length (per item) - prevents memory exhaustion on long texts
    # Set to 0 to disable limit
    MAX_INPUT_TEXT_LENGTH: int = int(os.getenv("MAX_INPUT_TEXT_LENGTH", "50000"))  # ~12.5k words

    # Lower limit for resource-constrained devices (Pi, low-memory systems)
    # Applied when running on detected Raspberry Pi or when PI_MODE is enabled
    PI_MAX_INPUT_TEXT_LENGTH: int = int(os.getenv("PI_MAX_INPUT_TEXT_LENGTH", "10000"))  # ~2.5k words
    PI_MODE: bool = os.getenv("PI_MODE", "0").lower() in ("1", "true", "yes")

    # Per-chunk translation timeout in seconds (0 = disabled)
    # Prevents individual chunks from hanging forever
    CHUNK_TRANSLATE_TIMEOUT_SEC: int = int(os.getenv("CHUNK_TRANSLATE_TIMEOUT_SEC", "30"))

    # Pi-specific translation timeout (applied automatically if Pi mode is detected)
    # Default 60s is reasonable for Pi's slower CPU
    PI_TRANSLATE_TIMEOUT_SEC: int = int(os.getenv("PI_TRANSLATE_TIMEOUT_SEC", "60"))

    # Metadata tracking (model, languages, timing, chunks, etc.)
    ENABLE_METADATA: bool = os.getenv("ENABLE_METADATA", "0").lower() in ("1", "true", "yes")
    METADATA_VIA_HEADERS: bool = os.getenv("METADATA_VIA_HEADERS", "0").lower() in ("1", "true", "yes")

    # Intelligent memory management
    ENABLE_MEMORY_MONITOR: bool = os.getenv("ENABLE_MEMORY_MONITOR", "1").lower() in ("1", "true", "yes")
    MEMORY_WARNING_THRESHOLD: float = float(os.getenv("MEMORY_WARNING_THRESHOLD", "80.0"))  # Warn at 80% RAM usage
    MEMORY_CRITICAL_THRESHOLD: float = float(os.getenv("MEMORY_CRITICAL_THRESHOLD", "90.0"))  # Auto-evict at 90% RAM usage
    GPU_MEMORY_WARNING_THRESHOLD: float = float(os.getenv("GPU_MEMORY_WARNING_THRESHOLD", "80.0"))  # Warn at 80% VRAM
    GPU_MEMORY_CRITICAL_THRESHOLD: float = float(os.getenv("GPU_MEMORY_CRITICAL_THRESHOLD", "90.0"))  # Auto-evict at 90% VRAM
    MEMORY_CHECK_INTERVAL: int = int(os.getenv("MEMORY_CHECK_INTERVAL", "5"))  # Check memory every N cache operations

    # Time-based model eviction (idle timeout)
    MODEL_IDLE_TIMEOUT: int = int(os.getenv("MODEL_IDLE_TIMEOUT", "0"))  # Seconds before evicting idle models (0 = disabled)
    IDLE_CHECK_INTERVAL: int = int(os.getenv("IDLE_CHECK_INTERVAL", "60"))  # How often to check for idle models (seconds)

    # Markdown sanitization (prevents parser depth errors)
    MARKDOWN_SANITIZE: bool = os.getenv("MARKDOWN_SANITIZE", "1").lower() in ("1", "true", "yes")
    MARKDOWN_SAFE_MODE: bool = os.getenv("MARKDOWN_SAFE_MODE", "0").lower() in ("1", "true", "yes")  # Force strip complex markdown
    MARKDOWN_SAFE_MODE_AUTO: bool = os.getenv("MARKDOWN_SAFE_MODE_AUTO", "1").lower() in ("1", "true", "yes")  # Auto-enable for problematic pairs
    MARKDOWN_MAX_DEPTH: int = int(os.getenv("MARKDOWN_MAX_DEPTH", "10"))  # Max bracket nesting depth
    MARKDOWN_PROBLEMATIC_PAIRS: List[str] = [
        p.strip() for p in os.getenv("MARKDOWN_PROBLEMATIC_PAIRS", "").split(",") if p.strip()
    ]  # e.g., "en->ar,en->he"

    # Chunk translation cache (LFU) - caches translated chunks to avoid repeated model inference
    CHUNK_CACHE_ENABLED: bool = os.getenv("CHUNK_CACHE_ENABLED", "1").lower() in ("1", "true", "yes")
    CHUNK_CACHE_CAPACITY: int = int(os.getenv("CHUNK_CACHE_CAPACITY", "10000"))  # Max entries (~25MB at capacity)
    CHUNK_CACHE_MAX_AGE: int = int(os.getenv("CHUNK_CACHE_MAX_AGE", "3600"))  # TTL in seconds (0 = no expiration)
    CHUNK_CACHE_MAX_KEY_LENGTH: int = int(os.getenv("CHUNK_CACHE_MAX_KEY_LENGTH", "1000"))  # Skip caching chunks longer than this
    CHUNK_CACHE_CLEANUP_INTERVAL: int = int(os.getenv("CHUNK_CACHE_CLEANUP_INTERVAL", "300"))  # Seconds between TTL sweeps

    # CTranslate2 configuration
    # Backend selection: "ct2" (CTranslate2, recommended) or "transformers" (PyTorch, legacy)
    TRANSLATION_BACKEND: str = os.getenv("TRANSLATION_BACKEND", "ct2").lower()

    # CT2 quantization: "default", "float16", "int8", "int8_float16"
    CT2_QUANTIZATION: str = os.getenv("CT2_QUANTIZATION", "default")

    # CT2 compute type: "auto", "float32", "float16", "int8", "int8_float16"
    CT2_COMPUTE_TYPE: str = os.getenv("CT2_COMPUTE_TYPE", "auto")

    # CT2 threading (for CPU inference)
    CT2_INTER_THREADS: int = int(os.getenv("CT2_INTER_THREADS", "1"))  # Number of parallel translations
    CT2_INTRA_THREADS: int = int(os.getenv("CT2_INTRA_THREADS", "4"))  # Threads per translation

    # Prefer pre-converted CT2 models from HuggingFace when available
    CT2_PREFER_PRECONVERTED: bool = os.getenv("CT2_PREFER_PRECONVERTED", "1").lower() in ("1", "true", "yes")

    @classmethod
    def get_supported_langs(cls) -> List[str]:
        """Get supported language codes for current model family.

        Returns:
            List of supported language codes
        """
        if cls.MODEL_FAMILY == "mbart50":
            return cls.MBART50_LANGS
        elif cls.MODEL_FAMILY == "m2m100":
            return cls.M2M100_LANGS
        else:  # opus-mt
            return cls.SUPPORTED_LANGS

    @classmethod
    def parse_model_args(cls) -> Dict[str, Any]:
        """Parse EASYNMT_MODEL_ARGS JSON string into allowed pipeline kwargs."""
        allowed_keys = {"revision", "trust_remote_code", "cache_dir", "use_fast", "torch_dtype"}

        try:
            data = json.loads(cls.EASYNMT_MODEL_ARGS_RAW or "{}")
            if not isinstance(data, dict):
                return {}
        except json.JSONDecodeError:
            return {}

        out: Dict[str, Any] = {}
        for k, v in data.items():
            if k not in allowed_keys:
                continue

            if k == "torch_dtype":
                # Map strings to torch dtype (only if torch is available)
                if isinstance(v, str) and TORCH_AVAILABLE:
                    vs = v.lower()
                    if vs in ("fp16", "float16", "torch.float16"):
                        out[k] = torch.float16
                    elif vs in ("bf16", "bfloat16", "torch.bfloat16"):
                        out[k] = torch.bfloat16
                    elif vs in ("fp32", "float32", "torch.float32"):
                        out[k] = torch.float32
                continue

            out[k] = v

        # Add cache_dir if MODEL_CACHE_DIR is set (unless already specified)
        if cls.MODEL_CACHE_DIR and "cache_dir" not in out:
            out["cache_dir"] = cls.MODEL_CACHE_DIR

        return out

    @classmethod
    def resolve_device_index(cls) -> int:
        """Resolve device index from configuration.

        Returns:
            -1 for CPU, 0+ for CUDA device index
        """
        # Check CUDA availability (works with torch or ctranslate2)
        cuda_available = False
        if TORCH_AVAILABLE:
            cuda_available = torch.cuda.is_available()
        else:
            # Try ctranslate2's CUDA detection
            try:
                import ctranslate2
                # get_supported_compute_types requires device argument in v4+
                cuda_types = ctranslate2.get_supported_compute_types("cuda")
                cuda_available = len(cuda_types) > 0
            except (ImportError, Exception):
                cuda_available = False

        dev = cls.DEVICE_ENV
        if dev and dev != "auto":
            if dev.startswith("cuda"):
                if not cuda_available:
                    return -1
                if ":" in dev:
                    _, idx = dev.split(":", 1)
                    try:
                        return int(idx)
                    except ValueError:
                        return 0
                return 0
            return -1  # cpu

        # Fallback by USE_GPU
        if cls.USE_GPU in ("1", "true", "yes"):  # force GPU if available
            return 0 if cuda_available else -1
        if cls.USE_GPU in ("0", "false", "no"):
            return -1
        # auto
        return 0 if cuda_available else -1

    @classmethod
    def get_max_inflight_translations(cls, device_index: int) -> int:
        """Determine max inflight translations based on device.

        Args:
            device_index: -1 for CPU, 0+ for CUDA

        Returns:
            Maximum concurrent translation requests
        """
        if cls.MAX_INFLIGHT_TRANSLATIONS_RAW:
            try:
                return max(1, int(cls.MAX_INFLIGHT_TRANSLATIONS_RAW))
            except ValueError:
                pass

        # Auto-configure based on device
        if device_index == -1:
            # CPU: allow limited parallelism, bounded by backend workers
            return max(1, cls.MAX_WORKERS_BACKEND)
        else:
            # GPU: default to 1 to avoid VRAM oversubscription
            return 1


# Singleton config instance
config = Config()
