"""CTranslate2 translator wrapper with pipeline-compatible interface."""

from typing import Any, Dict, List, Optional
import ctranslate2
from transformers import AutoTokenizer

from src.config import config
from src.core.logging import logger


class CT2TranslatorWrapper:
    """Wrapper around ctranslate2.Translator that mimics transformers pipeline interface.

    This allows drop-in replacement of transformers.pipeline() with CTranslate2
    while maintaining the same API for the translation service.
    """

    def __init__(
        self,
        model_path: str,
        tokenizer_name: str,
        src_lang: str,
        tgt_lang: str,
        device: str = "cpu",
        device_index: int = 0,
        family: str = "opus-mt",
    ):
        """Initialize CT2 translator wrapper.

        Args:
            model_path: Path to converted CTranslate2 model directory
            tokenizer_name: HuggingFace model name for tokenizer
            src_lang: Source language code
            tgt_lang: Target language code
            device: Device type ("cpu" or "cuda")
            device_index: GPU device index (if device is "cuda")
            family: Model family (opus-mt, mbart50, m2m100)
        """
        self.model_path = model_path
        self.tokenizer_name = tokenizer_name
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.device = device
        self.device_index = device_index
        self.family = family

        # Initialize CTranslate2 translator
        logger.info(f"Loading CT2 translator from {model_path} on {device}")

        compute_type = config.CT2_COMPUTE_TYPE
        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "default"

        self.translator = ctranslate2.Translator(
            model_path,
            device=device,
            device_index=[device_index] if device == "cuda" else None,
            inter_threads=config.CT2_INTER_THREADS,
            intra_threads=config.CT2_INTRA_THREADS,
            compute_type=compute_type,
        )

        # Initialize tokenizer
        logger.info(f"Loading tokenizer from {tokenizer_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)

        # Configure tokenizer for multilingual models
        self._configure_multilingual()

        logger.info(f"CT2 translator ready: {src_lang}->{tgt_lang} ({family})")

    def _configure_multilingual(self):
        """Configure tokenizer for multilingual models."""
        if self.family == "mbart50":
            # mBART50 uses lang_code with _XX suffix
            src_code = f"{self.src_lang}_XX"
            if hasattr(self.tokenizer, 'src_lang'):
                self.tokenizer.src_lang = src_code
        elif self.family == "m2m100":
            # M2M100 uses plain lang codes
            if hasattr(self.tokenizer, 'src_lang'):
                self.tokenizer.src_lang = self.src_lang

    def _get_target_prefix(self) -> Optional[List[str]]:
        """Get target language prefix tokens for multilingual models."""
        if self.family == "mbart50":
            # mBART50: target starts with target language token
            tgt_code = f"{self.tgt_lang}_XX"
            if hasattr(self.tokenizer, 'lang_code_to_id'):
                lang_token = self.tokenizer.convert_ids_to_tokens(
                    self.tokenizer.lang_code_to_id.get(tgt_code, 0)
                )
                return [[lang_token]]
            return None

        elif self.family == "m2m100":
            # M2M100: target starts with target language token
            if hasattr(self.tokenizer, 'lang_code_to_id'):
                lang_id = self.tokenizer.lang_code_to_id.get(self.tgt_lang)
                if lang_id is not None:
                    lang_token = self.tokenizer.convert_ids_to_tokens(lang_id)
                    return [[lang_token]]
            return None

        return None

    def __call__(
        self,
        texts: List[str],
        max_length: int = 512,
        num_beams: int = 5,
        batch_size: int = 16,
        **kwargs: Any,
    ) -> List[Dict[str, str]]:
        """Translate texts, returning results in pipeline-compatible format.

        Args:
            texts: List of texts to translate
            max_length: Maximum output length
            num_beams: Beam size for decoding
            batch_size: Batch size (not directly used by CT2, but kept for API compat)
            **kwargs: Additional arguments (ignored for compatibility)

        Returns:
            List of dicts with "translation_text" key, matching pipeline output format
        """
        if not texts:
            return []

        # Tokenize inputs
        tokenized_inputs = []
        for text in texts:
            # Encode and convert to tokens
            input_ids = self.tokenizer.encode(text, add_special_tokens=True)
            tokens = self.tokenizer.convert_ids_to_tokens(input_ids)
            tokenized_inputs.append(tokens)

        # Get target prefix for multilingual models
        target_prefix = self._get_target_prefix()
        if target_prefix:
            # Expand to match batch size
            target_prefix = target_prefix * len(tokenized_inputs)

        # Translate
        try:
            results = self.translator.translate_batch(
                tokenized_inputs,
                target_prefix=target_prefix,
                beam_size=num_beams,
                max_decoding_length=max_length,
                return_scores=False,
            )
        except Exception as e:
            logger.error(f"CT2 translation error: {e}")
            # Return empty translations on error
            return [{"translation_text": ""} for _ in texts]

        # Decode results
        output = []
        for result in results:
            if result.hypotheses:
                # Get top hypothesis
                tokens = result.hypotheses[0]

                # Remove target prefix if present
                if target_prefix and tokens:
                    prefix_len = len(target_prefix[0]) if target_prefix else 0
                    if prefix_len > 0 and len(tokens) > prefix_len:
                        tokens = tokens[prefix_len:]

                # Convert tokens to IDs and decode
                try:
                    token_ids = self.tokenizer.convert_tokens_to_ids(tokens)
                    text = self.tokenizer.decode(token_ids, skip_special_tokens=True)
                except Exception as e:
                    logger.warning(f"Decoding error: {e}")
                    text = ""

                output.append({"translation_text": text.strip()})
            else:
                output.append({"translation_text": ""})

        return output

    @property
    def model(self) -> ctranslate2.Translator:
        """Provide model attribute for cache eviction compatibility.

        The cache expects a .model attribute for cleanup operations.
        """
        return self.translator

    def unload(self):
        """Unload model from memory."""
        if hasattr(self.translator, 'unload'):
            self.translator.unload()
            logger.debug(f"Unloaded CT2 translator: {self.src_lang}->{self.tgt_lang}")

    def to(self, device: str):
        """Move model to device (compatibility method).

        Note: CT2 doesn't support dynamic device moves like PyTorch.
        This is a no-op for API compatibility.
        """
        logger.debug(f"CT2 to({device}) called - no-op for CTranslate2")
        return self

    def cpu(self):
        """Move to CPU (compatibility method).

        For CT2, we just unload to free memory.
        """
        self.unload()
        return self

    def __repr__(self) -> str:
        return f"CT2TranslatorWrapper({self.src_lang}->{self.tgt_lang}, family={self.family}, device={self.device})"
