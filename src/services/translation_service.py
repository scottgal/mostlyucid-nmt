"""Translation service with robust error handling and processing pipeline."""

from typing import List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from src.config import config
from src.core.logging import logger
from src.services.model_manager import model_manager
from src.utils.text_processing import (
    is_noise,
    split_sentences,
    chunk_sentences,
    remove_repeating_new_symbols
)
from src.utils.symbol_masking import mask_symbols, unmask_symbols


class TranslationService:
    """Service for translating text with full processing pipeline."""

    def __init__(self, executor: ThreadPoolExecutor):
        """Initialize translation service.

        Args:
            executor: ThreadPoolExecutor for CPU-bound work
        """
        self.executor = executor

    def _translate_with_translator(
        self,
        translator: any,
        chunks: List[str],
        eff_beam: int
    ) -> List[str]:
        """Translate chunks using translator pipeline.

        Args:
            translator: Transformers pipeline
            chunks: List of text chunks to translate
            eff_beam: Effective beam size

        Returns:
            List of translated chunks
        """
        if not chunks:
            return []

        gen_max_len = 512
        if config.EASYNMT_MAX_TEXT_LEN_INT is not None:
            gen_max_len = min(gen_max_len, max(1, config.EASYNMT_MAX_TEXT_LEN_INT))

        out_chunks: List[str] = []
        bs = max(1, config.EASYNMT_BATCH_SIZE)

        for i in range(0, len(chunks), bs):
            batch = chunks[i:i + bs]
            res = translator(batch, max_length=gen_max_len, num_beams=eff_beam, batch_size=len(batch))
            out_chunks.extend([r.get("translation_text", "") for r in res])

        return out_chunks

    def _translate_text_single(
        self,
        txt: str,
        src: str,
        tgt: str,
        eff_beam: int,
        perform_sentence_splitting: bool,
        translator_direct: Optional[any] = None
    ) -> str:
        """Translate a single text item.

        Args:
            txt: Text to translate
            src: Source language
            tgt: Target language
            eff_beam: Beam size
            perform_sentence_splitting: Whether to split sentences
            translator_direct: Pre-loaded translator or None

        Returns:
            Translated text or placeholder if failed
        """
        if config.INPUT_SANITIZE and is_noise(txt):
            return config.SANITIZE_PLACEHOLDER

        gen_max_len = 512
        if config.EASYNMT_MAX_TEXT_LEN_INT is not None:
            gen_max_len = min(gen_max_len, max(1, config.EASYNMT_MAX_TEXT_LEN_INT))

        try:
            translator = translator_direct or model_manager.get_pipeline(src, tgt)

            if perform_sentence_splitting:
                sents = split_sentences(txt)
                chunks = chunk_sentences(sents, config.MAX_CHUNK_CHARS)
                out = self._translate_with_translator(translator, chunks, eff_beam)
                combined = config.JOIN_SENTENCES_WITH.join(out)
                combined = remove_repeating_new_symbols(txt, combined)
                return combined
            else:
                res = translator([txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                base = res[0].get("translation_text", config.SANITIZE_PLACEHOLDER)
                base = remove_repeating_new_symbols(txt, base)
                return base

        except Exception as direct_err:
            # Attempt pivot fallback if enabled
            if not config.PIVOT_FALLBACK or config.PIVOT_LANG in (src, tgt):
                if config.REQUEST_LOG:
                    logger.warning(f"Direct translate failed (no pivot): {direct_err}")
                return config.SANITIZE_PLACEHOLDER

            try:
                trans_src_pivot = model_manager.get_pipeline(src, config.PIVOT_LANG)
                trans_pivot_tgt = model_manager.get_pipeline(config.PIVOT_LANG, tgt)

                if perform_sentence_splitting:
                    sents = split_sentences(txt)
                    chunks = chunk_sentences(sents, config.MAX_CHUNK_CHARS)

                    # First hop: src -> pivot
                    mid = self._translate_with_translator(trans_src_pivot, chunks, eff_beam)

                    # Second hop: pivot -> tgt
                    final = self._translate_with_translator(trans_pivot_tgt, mid, eff_beam)

                    combined = config.JOIN_SENTENCES_WITH.join(final)
                    combined = remove_repeating_new_symbols(txt, combined)
                    return combined
                else:
                    mid = trans_src_pivot([txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                    mid_txt = mid[0].get("translation_text", "")

                    fin = trans_pivot_tgt([mid_txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                    base = fin[0].get("translation_text", config.SANITIZE_PLACEHOLDER)
                    base = remove_repeating_new_symbols(txt, base)
                    return base

            except Exception as pivot_err:
                if config.REQUEST_LOG:
                    logger.warning(f"Pivot translate failed: {pivot_err}")
                return config.SANITIZE_PLACEHOLDER

    def translate_texts_aligned(
        self,
        input_texts: List[str],
        src: str,
        tgt: str,
        eff_beam: int,
        perform_sentence_splitting: bool
    ) -> List[str]:
        """Translate list of texts while preserving alignment.

        Args:
            input_texts: List of texts to translate
            src: Source language
            tgt: Target language
            eff_beam: Beam size
            perform_sentence_splitting: Whether to split sentences

        Returns:
            List of translations (same length as input)
        """
        outputs: List[str] = []

        # Try to load direct translator once
        translator_direct = None
        try:
            translator_direct = model_manager.get_pipeline(src, tgt)
        except Exception as e:
            # We will use pivot per-item if available
            if config.REQUEST_LOG:
                logger.warning(f"Loading direct pipeline failed; will pivot per item if possible: {e}")

        for t in input_texts:
            try:
                txt = t if isinstance(t, str) else ""
                translated = self._translate_text_single(
                    txt, src, tgt, eff_beam, perform_sentence_splitting,
                    translator_direct=translator_direct
                )
                outputs.append(translated if isinstance(translated, str) else config.SANITIZE_PLACEHOLDER)
            except Exception as e:
                if config.REQUEST_LOG:
                    logger.warning(f"Per-item translation failed, inserting placeholder: {e}")
                outputs.append(config.SANITIZE_PLACEHOLDER)

        return outputs

    async def translate_async(
        self,
        texts: List[str],
        src: str,
        tgt: str,
        beam_size: int,
        perform_sentence_splitting: bool
    ) -> List[str]:
        """Asynchronously translate texts using thread pool.

        Args:
            texts: List of texts to translate
            src: Source language
            tgt: Target language
            beam_size: Beam size
            perform_sentence_splitting: Whether to split sentences

        Returns:
            List of translations
        """
        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(
            self.executor,
            self.translate_texts_aligned,
            texts,
            src,
            tgt,
            beam_size,
            perform_sentence_splitting
        )


# We'll instantiate this in the main app with the executor
