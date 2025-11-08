"""Configuration management for the translator service."""

import os
import json
from typing import Optional, Dict, Any, List
import torch


class Config:
    """Centralized configuration from environment variables."""

    # Application
    VERSION = "1.0.0"
    TITLE = "Marian Translator API"

    # Supported language codes
    SUPPORTED_LANGS: List[str] = [
        "en", "es", "fr", "de", "it", "zh", "nl", "hi", "ar", "uk", "fi", "sv", "el",
    ]

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    REQUEST_LOG: bool = os.getenv("REQUEST_LOG", "0").lower() in ("1", "true", "yes")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "plain").lower()  # plain|json
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "0").lower() in ("1", "true", "yes")
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "/var/log/marian-translator/app.log")
    LOG_FILE_MAX_BYTES: int = int(os.getenv("LOG_FILE_MAX_BYTES", "10485760"))  # 10MB
    LOG_FILE_BACKUP_COUNT: int = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))
    LOG_INCLUDE_TEXT: bool = os.getenv("LOG_INCLUDE_TEXT", "0").lower() in ("1", "true", "yes")

    # Device selection
    USE_GPU: str = os.getenv("USE_GPU", "auto").lower()  # "true", "false", or "auto"
    DEVICE_ENV: str = os.getenv("DEVICE", "auto")  # e.g., "cuda", "cuda:0", "cpu"

    # Model configuration
    EASYNMT_MODEL: str = os.getenv("EASYNMT_MODEL", "opus-mt")
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

    # Cache
    MAX_CACHED_MODELS: int = int(os.getenv("MAX_CACHED_MODELS", "6"))

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
                # Map strings to torch dtype
                if isinstance(v, str):
                    vs = v.lower()
                    if vs in ("fp16", "float16", "torch.float16"):
                        out[k] = torch.float16
                    elif vs in ("bf16", "bfloat16", "torch.bfloat16"):
                        out[k] = torch.bfloat16
                    elif vs in ("fp32", "float32", "torch.float32"):
                        out[k] = torch.float32
                continue

            out[k] = v

        return out

    @classmethod
    def resolve_device_index(cls) -> int:
        """Resolve device index from configuration.

        Returns:
            -1 for CPU, 0+ for CUDA device index
        """
        dev = cls.DEVICE_ENV
        if dev and dev != "auto":
            if dev.startswith("cuda"):
                if not torch.cuda.is_available():
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
            return 0 if torch.cuda.is_available() else -1
        if cls.USE_GPU in ("0", "false", "no"):
            return -1
        # auto
        return 0 if torch.cuda.is_available() else -1

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
