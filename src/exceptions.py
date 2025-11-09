"""Custom exceptions for the translator service."""


class TranslatorException(Exception):
    """Base exception for translator errors."""
    pass


class QueueOverflowError(TranslatorException):
    """Raised when translation queue is full."""

    def __init__(self, waiters: int = 0):
        self.waiters = waiters
        super().__init__(f"Queue overflow with {waiters} waiters")


class ServiceBusyError(TranslatorException):
    """Raised when service is busy and queueing is disabled."""
    pass


class UnsupportedLanguagePairError(TranslatorException):
    """Raised when language pair is not supported."""

    def __init__(self, source_lang: str, target_lang: str):
        self.source_lang = source_lang
        self.target_lang = target_lang
        super().__init__(f"Unsupported language pair: {source_lang} -> {target_lang}")


class TranslationTimeoutError(TranslatorException):
    """Raised when translation times out."""
    pass


class ModelLoadError(TranslatorException):
    """Raised when model loading fails."""

    def __init__(self, model_name: str, original_error: Exception):
        self.model_name = model_name
        self.original_error = original_error
        super().__init__(f"Failed to load model {model_name}: {original_error}")


class OutOfMemoryError(TranslatorException):
    """Raised when system is critically low on memory (RAM or VRAM).

    This exception indicates that:
    - System RAM or GPU VRAM is at emergency levels (95%+)
    - All cached models have been evicted
    - Loading new models would likely cause OOM crash
    - Service needs time to recover or needs more resources
    """

    def __init__(self, ram_pct: float = 0.0, vram_pct: float = 0.0):
        self.ram_pct = ram_pct
        self.vram_pct = vram_pct

        if vram_pct > 0:
            msg = f"Out of memory: RAM at {ram_pct:.1f}%, VRAM at {vram_pct:.1f}%. All models evicted. Cannot load new models."
        else:
            msg = f"Out of memory: RAM at {ram_pct:.1f}%. All models evicted. Cannot load new models."

        super().__init__(msg)
