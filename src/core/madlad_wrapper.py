"""MADLAD-400 translation model wrapper.

Provides a pipeline-compatible interface for Google's MADLAD-400 multilingual translation model.
MADLAD-400 supports 400+ languages using T5-based architecture with <2xx> language prefixes.

See: https://huggingface.co/google/madlad400-3b-mt
"""

from typing import Any, Dict, List, Optional
import torch

from src.config import config
from src.core.logging import logger


class MADLADWrapper:
    """Wrapper for MADLAD-400 models providing pipeline-compatible interface.

    MADLAD uses T5 architecture with language code prefixes like <2de> for German.
    This wrapper handles the prefix injection and provides a standard translation interface.
    """

    def __init__(
        self,
        model_name: str = "google/madlad400-3b-mt",
        device: str = "auto",
        device_index: int = 0,
        torch_dtype: Optional[torch.dtype] = None,
    ):
        """Initialize MADLAD wrapper.

        Args:
            model_name: HuggingFace model name (google/madlad400-3b-mt, etc.)
            device: Device string ("auto", "cpu", "cuda")
            device_index: CUDA device index if using GPU
            torch_dtype: Optional torch dtype for model loading
        """
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.model_name = model_name
        self.device = device
        self.device_index = device_index

        logger.info(f"Loading MADLAD model: {model_name}")

        # Determine device map
        if device == "auto":
            device_map = "auto"
        elif device == "cpu":
            device_map = "cpu"
        else:
            device_map = f"cuda:{device_index}"

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        # Load model with appropriate dtype
        model_kwargs: Dict[str, Any] = {"device_map": device_map}

        if torch_dtype:
            model_kwargs["torch_dtype"] = torch_dtype
        elif torch.cuda.is_available() and device != "cpu":
            # Default to bfloat16 on GPU for memory efficiency
            model_kwargs["torch_dtype"] = torch.bfloat16

        # Add cache directory if configured
        if config.MODEL_CACHE_DIR:
            model_kwargs["cache_dir"] = config.MODEL_CACHE_DIR

        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name, **model_kwargs)

        logger.info(f"MADLAD model loaded: {model_name} on {device_map}")

    def _format_input(self, text: str, tgt_lang: str) -> str:
        """Format input with MADLAD language prefix.

        Args:
            text: Text to translate
            tgt_lang: Target language code (e.g., "de", "fr")

        Returns:
            Formatted input string with <2xx> prefix
        """
        # MADLAD uses <2xx> format for target language
        return f"<2{tgt_lang}> {text}"

    def __call__(
        self,
        texts: List[str],
        max_length: int = 256,
        num_beams: int = 4,
        **kwargs
    ) -> List[Dict[str, str]]:
        """Translate texts using MADLAD model.

        Provides pipeline-compatible interface returning list of dicts with
        "translation_text" keys.

        Args:
            texts: List of texts to translate
            max_length: Maximum output length
            num_beams: Number of beams for beam search
            **kwargs: Additional arguments (tgt_lang required)

        Returns:
            List of dicts with "translation_text" key
        """
        tgt_lang = kwargs.get("tgt_lang", "en")

        # Format inputs with language prefix
        formatted_texts = [self._format_input(text, tgt_lang) for text in texts]

        # Tokenize
        inputs = self.tokenizer(
            formatted_texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,  # Input max length
        )

        # Move to model device
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        # Generate
        max_len = min(max_length, config.MADLAD_MAX_LENGTH)
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_length=max_len,
                num_beams=num_beams,
                early_stopping=True,
            )

        # Decode
        translations = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)

        return [{"translation_text": t} for t in translations]

    def to(self, device: str):
        """Move model to device (for compatibility).

        Args:
            device: Device string

        Returns:
            self
        """
        self.model.to(device)
        return self


def get_madlad_model_name() -> str:
    """Get MADLAD model name based on configuration.

    Returns:
        HuggingFace model identifier
    """
    size = config.MADLAD_MODEL_SIZE.lower()
    if size == "10b":
        return "google/madlad400-10b-mt"
    elif size == "7b":
        return "google/madlad400-7b-mt"
    else:  # Default to 3b
        return "google/madlad400-3b-mt"
