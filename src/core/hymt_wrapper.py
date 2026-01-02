"""HY-MT (Hunyuan Translation) model wrapper.

Provides a pipeline-compatible interface for Tencent's HY-MT LLM-based translation model.
See: https://github.com/Tencent-Hunyuan/HY-MT
"""

from typing import Any, Dict, List, Optional
import torch

from src.config import config
from src.core.logging import logger


# Language code to full name mapping for HY-MT prompts
LANG_NAMES: Dict[str, str] = {
    "zh": "Chinese",
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ru": "Russian",
    "ar": "Arabic",
    "ko": "Korean",
    "de": "German",
    "it": "Italian",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "th": "Thai",
    "pl": "Polish",
    "nl": "Dutch",
    "cs": "Czech",
    "tr": "Turkish",
    "el": "Greek",
    "hu": "Hungarian",
    "ro": "Romanian",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "no": "Norwegian",
    "sk": "Slovak",
    "bg": "Bulgarian",
    "uk": "Ukrainian",
    "hr": "Croatian",
    "sr": "Serbian",
    "sl": "Slovenian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
    # Variants
    "zh-tw": "Traditional Chinese",
    "yue": "Cantonese",
}


class HYMTWrapper:
    """Wrapper for HY-MT models providing pipeline-compatible interface.

    HY-MT uses an LLM-style chat interface rather than direct translation pipelines.
    This wrapper handles prompt construction and response parsing to match the
    transformers pipeline interface.
    """

    def __init__(
        self,
        model_name: str = "tencent/HY-MT1.5-1.8B",
        device: str = "auto",
        device_index: int = 0,
        torch_dtype: Optional[torch.dtype] = None,
    ):
        """Initialize HY-MT wrapper.

        Args:
            model_name: HuggingFace model name (tencent/HY-MT1.5-1.8B or tencent/HY-MT1.5-7B)
            device: Device string ("auto", "cpu", "cuda")
            device_index: CUDA device index if using GPU
            torch_dtype: Optional torch dtype for model loading
        """
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_name = model_name
        self.device = device
        self.device_index = device_index

        logger.info(f"Loading HY-MT model: {model_name}")

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
        elif torch.cuda.is_available():
            # Default to bfloat16 on GPU for memory efficiency
            model_kwargs["torch_dtype"] = torch.bfloat16

        # Add cache directory if configured
        if config.MODEL_CACHE_DIR:
            model_kwargs["cache_dir"] = config.MODEL_CACHE_DIR

        self.model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)

        # Store generation parameters from config
        self.generation_config = {
            "top_k": config.HYMT_TOP_K,
            "top_p": config.HYMT_TOP_P,
            "temperature": config.HYMT_TEMPERATURE,
            "repetition_penalty": config.HYMT_REPETITION_PENALTY,
            "max_new_tokens": config.HYMT_MAX_NEW_TOKENS,
            "do_sample": True,
        }

        logger.info(f"HY-MT model loaded: {model_name} on {device_map}")

    def _get_lang_name(self, lang_code: str) -> str:
        """Get full language name from code.

        Args:
            lang_code: ISO language code (e.g., "en", "zh")

        Returns:
            Full language name for prompt
        """
        return LANG_NAMES.get(lang_code, lang_code.capitalize())

    def _build_prompt(self, text: str, tgt_lang: str) -> str:
        """Build translation prompt for HY-MT.

        Args:
            text: Text to translate
            tgt_lang: Target language code

        Returns:
            Formatted prompt string
        """
        lang_name = self._get_lang_name(tgt_lang)
        return f"Translate the following segment into {lang_name}, without additional explanation.\n\n{text}"

    def _extract_translation(self, generated_text: str, prompt: str) -> str:
        """Extract translation from generated response.

        Args:
            generated_text: Full generated text including prompt
            prompt: Original prompt to remove

        Returns:
            Extracted translation text
        """
        # Remove the prompt portion
        if generated_text.startswith(prompt):
            translation = generated_text[len(prompt):].strip()
        else:
            # Try to find assistant response marker
            translation = generated_text

        # Clean up any remaining chat markers
        for marker in ["<|assistant|>", "<|user|>", "<|end|>", "</s>", "<s>"]:
            translation = translation.replace(marker, "")

        return translation.strip()

    def __call__(
        self,
        texts: List[str],
        max_length: int = 512,
        num_beams: int = 1,
        **kwargs
    ) -> List[Dict[str, str]]:
        """Translate texts using HY-MT model.

        Provides pipeline-compatible interface returning list of dicts with
        "translation_text" keys.

        Args:
            texts: List of texts to translate
            max_length: Maximum output length (maps to max_new_tokens)
            num_beams: Number of beams (1 = greedy/sampling, >1 = beam search)
            **kwargs: Additional arguments (tgt_lang required)

        Returns:
            List of dicts with "translation_text" key
        """
        tgt_lang = kwargs.get("tgt_lang", "en")
        results = []

        for text in texts:
            # Build chat message
            prompt = self._build_prompt(text, tgt_lang)
            messages = [{"role": "user", "content": prompt}]

            # Apply chat template
            tokenized = self.tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt"
            )

            # Move to model device
            tokenized = tokenized.to(self.model.device)

            # Configure generation
            gen_kwargs = {
                **self.generation_config,
                "max_new_tokens": min(max_length, config.HYMT_MAX_NEW_TOKENS),
            }

            # Use beam search if requested
            if num_beams > 1:
                gen_kwargs["num_beams"] = num_beams
                gen_kwargs["do_sample"] = False
                # Remove sampling params when using beam search
                gen_kwargs.pop("top_k", None)
                gen_kwargs.pop("top_p", None)
                gen_kwargs.pop("temperature", None)

            # Generate
            with torch.no_grad():
                outputs = self.model.generate(tokenized, **gen_kwargs)

            # Decode and extract translation
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            translation = self._extract_translation(generated_text, prompt)

            results.append({"translation_text": translation})

        return results

    def to(self, device: str):
        """Move model to device (for compatibility).

        Args:
            device: Device string

        Returns:
            self
        """
        self.model.to(device)
        return self


def get_hymt_model_name() -> str:
    """Get HY-MT model name based on configuration.

    Returns:
        HuggingFace model identifier
    """
    size = config.HYMT_MODEL_SIZE.upper()
    if size == "7B":
        return "tencent/HY-MT1.5-7B"
    else:
        return "tencent/HY-MT1.5-1.8B"
