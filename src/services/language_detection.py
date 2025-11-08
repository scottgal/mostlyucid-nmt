"""Language detection service."""

from typing import Dict, List, Union
from langdetect import detect

from src.config import config
from src.utils.text_processing import is_noise
from src.core.logging import logger


class LanguageDetectionService:
    """Service for detecting language of text."""

    def detect_language(self, text: str) -> str:
        """Detect language of a single text.

        Args:
            text: Input text

        Returns:
            Language code or UNDETERMINED_LANG_CODE if noise
        """
        try:
            if config.INPUT_SANITIZE and is_noise(text):
                return config.UNDETERMINED_LANG_CODE

            lang = detect(text)
            if config.REQUEST_LOG:
                logger.debug(f"Detected language: {lang} for text (len={len(text)})")
            return lang

        except Exception as e:
            logger.warning(f"Language detection failed: {e}, defaulting to 'en'")
            return "en"  # Default fallback

    def detect_languages_batch(self, texts: List[str]) -> List[str]:
        """Detect languages for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of language codes
        """
        return [self.detect_language(text) for text in texts]

    def detect_languages_dict(self, texts: Dict[str, str]) -> Dict[str, str]:
        """Detect languages for dictionary of texts.

        Args:
            texts: Dictionary mapping keys to text values

        Returns:
            Dictionary mapping same keys to language codes
        """
        return {key: self.detect_language(val) for key, val in texts.items()}


# Singleton instance
language_detector = LanguageDetectionService()
