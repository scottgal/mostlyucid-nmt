"""CTranslate2 translator wrapper with pipeline-compatible interface."""

from typing import Any, Dict, List, Optional
import ctranslate2

from src.config import config
from src.core.logging import logger

# Lazy import for AutoTokenizer to avoid torch circular import in frozen executables
_AutoTokenizer = None

def _get_auto_tokenizer():
    """Lazily import AutoTokenizer to defer torch loading."""
    global _AutoTokenizer
    if _AutoTokenizer is None:
        from transformers import AutoTokenizer
        _AutoTokenizer = AutoTokenizer
    return _AutoTokenizer


# mBART50 language code mapping (2-letter -> mBART format)
# mBART uses specific codes like de_DE, not de_XX for most languages
MBART50_LANG_CODES = {
    "ar": "ar_AR", "cs": "cs_CZ", "de": "de_DE", "en": "en_XX", "es": "es_XX",
    "et": "et_EE", "fi": "fi_FI", "fr": "fr_XX", "gu": "gu_IN", "hi": "hi_IN",
    "it": "it_IT", "ja": "ja_XX", "kk": "kk_KZ", "ko": "ko_KR", "lt": "lt_LT",
    "lv": "lv_LV", "my": "my_MM", "ne": "ne_NP", "nl": "nl_XX", "ro": "ro_RO",
    "ru": "ru_RU", "si": "si_LK", "tr": "tr_TR", "vi": "vi_VN", "zh": "zh_CN",
    "af": "af_ZA", "az": "az_AZ", "bn": "bn_IN", "fa": "fa_IR", "he": "he_IL",
    "hr": "hr_HR", "id": "id_ID", "ka": "ka_GE", "km": "km_KH", "mk": "mk_MK",
    "ml": "ml_IN", "mn": "mn_MN", "mr": "mr_IN", "pl": "pl_PL", "ps": "ps_AF",
    "pt": "pt_XX", "sv": "sv_SE", "sw": "sw_KE", "ta": "ta_IN", "te": "te_IN",
    "th": "th_TH", "tl": "tl_XX", "uk": "uk_UA", "ur": "ur_PK", "xh": "xh_ZA",
    "gl": "gl_ES", "sl": "sl_SI",
}


def _normalize_lang_code(lang: str) -> str:
    """Normalize language code to 2-letter format.

    mBART50 codes come in as 'de_XX' from model_manager but we need 'de'
    to look them up in MBART50_LANG_CODES dictionary.
    """
    if "_" in lang:
        return lang.split("_")[0]
    return lang


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

        # Build kwargs - only include device_index for CUDA devices
        translator_kwargs: Dict[str, Any] = {
            "device": device,
            "inter_threads": config.CT2_INTER_THREADS,
            "intra_threads": config.CT2_INTRA_THREADS,
            "compute_type": compute_type,
        }

        # Only pass device_index for CUDA devices
        if device == "cuda":
            translator_kwargs["device_index"] = device_index

        self.translator = ctranslate2.Translator(model_path, **translator_kwargs)

        # Initialize tokenizer (lazy import to avoid torch circular import)
        logger.info(f"Loading tokenizer from {tokenizer_name}")
        AutoTokenizer = _get_auto_tokenizer()
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)

        # Configure tokenizer for multilingual models
        self._configure_multilingual()

        logger.info(f"CT2 translator ready: {src_lang}->{tgt_lang} ({family})")

    def _configure_multilingual(self):
        """Configure tokenizer for multilingual models."""
        if self.family == "mbart50":
            # mBART50 uses specific language codes (e.g., de_DE, not de_XX)
            # Normalize input (may come as "de_XX" from model_manager)
            src_normalized = _normalize_lang_code(self.src_lang)
            src_code = MBART50_LANG_CODES.get(src_normalized, f"{src_normalized}_XX")
            if hasattr(self.tokenizer, 'src_lang'):
                self.tokenizer.src_lang = src_code
                logger.info(f"mBART50 source language set to: {src_code}")
        elif self.family == "m2m100":
            # M2M100 uses plain lang codes
            src_normalized = _normalize_lang_code(self.src_lang)
            if hasattr(self.tokenizer, 'src_lang'):
                self.tokenizer.src_lang = src_normalized

    def _get_target_prefix(self) -> Optional[List[List[str]]]:
        """Get target language prefix tokens for multilingual models.

        Returns:
            List of token lists (one per input), or None for non-multilingual models
        """
        if self.family == "mbart50":
            # mBART50: target starts with target language token (e.g., de_DE, not de_XX)
            # Normalize input (may come as "es_XX" from model_manager)
            tgt_normalized = _normalize_lang_code(self.tgt_lang)
            tgt_code = MBART50_LANG_CODES.get(tgt_normalized, f"{tgt_normalized}_XX")
            if hasattr(self.tokenizer, 'lang_code_to_id'):
                lang_id = self.tokenizer.lang_code_to_id.get(tgt_code)
                if lang_id is not None:
                    lang_token = self.tokenizer.convert_ids_to_tokens(lang_id)
                    logger.info(f"mBART50 target prefix: {tgt_code} -> {lang_token}")
                    return [[lang_token]]
                else:
                    logger.warning(f"mBART50 language code {tgt_code} not found in tokenizer")
            return None

        elif self.family == "m2m100":
            # M2M100: target starts with target language token
            # Normalize input (may come as "es_XX" from model_manager)
            tgt_normalized = _normalize_lang_code(self.tgt_lang)
            if hasattr(self.tokenizer, 'lang_code_to_id'):
                lang_id = self.tokenizer.lang_code_to_id.get(tgt_normalized)
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
        no_repeat_ngram_size: int = 3,
        repetition_penalty: float = 1.2,
        **kwargs: Any,
    ) -> List[Dict[str, str]]:
        """Translate texts, returning results in pipeline-compatible format.

        Args:
            texts: List of texts to translate
            max_length: Maximum output length
            num_beams: Beam size for decoding
            batch_size: Batch size (not directly used by CT2, but kept for API compat)
            no_repeat_ngram_size: Prevent repeating n-grams of this size (default: 3)
            repetition_penalty: Penalty for repeated tokens, >1.0 penalizes (default: 1.2)
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

        # Translate with repetition prevention
        try:
            results = self.translator.translate_batch(
                tokenized_inputs,
                target_prefix=target_prefix,
                beam_size=num_beams,
                max_decoding_length=max_length,
                no_repeat_ngram_size=no_repeat_ngram_size,
                repetition_penalty=repetition_penalty,
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
