"""Translation service with robust error handling and processing pipeline."""

from typing import List, Optional, Tuple, Dict, Any
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
    ) -> Tuple[str, bool]:
        """Translate a single text item.

        Args:
            txt: Text to translate
            src: Source language
            tgt: Target language
            eff_beam: Beam size
            perform_sentence_splitting: Whether to split sentences
            translator_direct: Pre-loaded translator or None

        Returns:
            Tuple of (translated text or placeholder if failed, pivot_used flag)
        """
        if config.INPUT_SANITIZE and is_noise(txt):
            return (config.SANITIZE_PLACEHOLDER, False)

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
                return (combined, False)
            else:
                res = translator([txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                base = res[0].get("translation_text", config.SANITIZE_PLACEHOLDER)
                base = remove_repeating_new_symbols(txt, base)
                return (base, False)

        except Exception as direct_err:
            # Attempt pivot fallback if enabled
            if not config.PIVOT_FALLBACK or config.PIVOT_LANG in (src, tgt):
                if config.REQUEST_LOG:
                    logger.warning(f"Direct translate failed (no pivot): {direct_err}")
                return (config.SANITIZE_PLACEHOLDER, False)

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
                    return (combined, True)
                else:
                    mid = trans_src_pivot([txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                    mid_txt = mid[0].get("translation_text", "")

                    fin = trans_pivot_tgt([mid_txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                    base = fin[0].get("translation_text", config.SANITIZE_PLACEHOLDER)
                    base = remove_repeating_new_symbols(txt, base)
                    return (base, True)

            except Exception as pivot_err:
                if config.REQUEST_LOG:
                    logger.warning(f"Pivot translate failed: {pivot_err}")
                return (config.SANITIZE_PLACEHOLDER, False)

    def translate_texts_aligned(
        self,
        input_texts: List[str],
        src: str,
        tgt: str,
        eff_beam: int,
        perform_sentence_splitting: bool
    ) -> Tuple[List[str], bool]:
        """Translate list of texts while preserving alignment.

        Args:
            input_texts: List of texts to translate
            src: Source language
            tgt: Target language
            eff_beam: Beam size
            perform_sentence_splitting: Whether to split sentences

        Returns:
            Tuple of (list of translations (same length as input), pivot_used flag)
        """
        outputs: List[str] = []
        pivot_used = False

        # Try to load direct translator once
        translator_direct = None
        try:
            translator_direct = model_manager.get_pipeline(src, tgt)
        except Exception as e:
            # We will use pivot per-item if available
            if config.REQUEST_LOG:
                logger.warning(f"Loading direct pipeline failed; will pivot per item if possible: {e}")
            pivot_used = True  # Direct pipeline not available

        for t in input_texts:
            try:
                txt = t if isinstance(t, str) else ""
                translated, item_pivot_used = self._translate_text_single(
                    txt, src, tgt, eff_beam, perform_sentence_splitting,
                    translator_direct=translator_direct
                )
                if item_pivot_used:
                    pivot_used = True
                outputs.append(translated if isinstance(translated, str) else config.SANITIZE_PLACEHOLDER)
            except Exception as e:
                if config.REQUEST_LOG:
                    logger.warning(f"Per-item translation failed, inserting placeholder: {e}")
                outputs.append(config.SANITIZE_PLACEHOLDER)

        return (outputs, pivot_used)

    def _auto_chunk_texts(self, texts: List[str]) -> Tuple[List[str], List[Tuple[int, int]]]:
        """Auto-chunk texts that exceed max chunk size.

        Args:
            texts: List of input texts

        Returns:
            Tuple of (chunked_texts, chunk_map) where chunk_map contains (original_index, num_chunks)
        """
        if not config.AUTO_CHUNK_ENABLED:
            return (texts, [(i, 1) for i in range(len(texts))])

        max_chars = config.AUTO_CHUNK_MAX_CHARS
        chunked_texts: List[str] = []
        chunk_map: List[Tuple[int, int]] = []

        for i, text in enumerate(texts):
            if len(text) <= max_chars:
                chunked_texts.append(text)
                chunk_map.append((i, 1))
            else:
                # Split large text into chunks
                num_chunks = (len(text) + max_chars - 1) // max_chars
                for chunk_idx in range(num_chunks):
                    start = chunk_idx * max_chars
                    end = min(start + max_chars, len(text))
                    chunk = text[start:end]
                    chunked_texts.append(chunk)

                chunk_map.append((i, num_chunks))

        return (chunked_texts, chunk_map)

    def _reassemble_chunks(self, translations: List[str], chunk_map: List[Tuple[int, int]]) -> List[str]:
        """Reassemble chunked translations back to original structure.

        Args:
            translations: List of translated chunks
            chunk_map: Mapping of (original_index, num_chunks)

        Returns:
            List of reassembled translations matching original input length
        """
        result: List[str] = []
        trans_idx = 0

        for orig_idx, num_chunks in chunk_map:
            if num_chunks == 1:
                result.append(translations[trans_idx])
                trans_idx += 1
            else:
                # Combine multiple chunks
                combined = config.JOIN_SENTENCES_WITH.join(translations[trans_idx:trans_idx + num_chunks])
                result.append(combined)
                trans_idx += num_chunks

        return result

    async def translate_async(
        self,
        texts: List[str],
        src: str,
        tgt: str,
        beam_size: int,
        perform_sentence_splitting: bool,
        include_metadata: bool = False
    ) -> Tuple[List[str], bool, Optional[Dict[str, Any]]]:
        """Asynchronously translate texts using thread pool.

        Args:
            texts: List of texts to translate
            src: Source language
            tgt: Target language
            beam_size: Beam size
            perform_sentence_splitting: Whether to split sentences
            include_metadata: Whether to include metadata in response

        Returns:
            Tuple of (list of translations, pivot_used flag, optional metadata dict)
        """
        loop = asyncio.get_event_loop()

        # Auto-chunk if needed
        chunked_texts, chunk_map = self._auto_chunk_texts(texts)
        auto_chunked = any(num_chunks > 1 for _, num_chunks in chunk_map)
        total_chunks = sum(num_chunks for _, num_chunks in chunk_map)

        # Translate chunked texts
        translations, pivot_used = await loop.run_in_executor(
            self.executor,
            self.translate_texts_aligned,
            chunked_texts,
            src,
            tgt,
            beam_size,
            perform_sentence_splitting
        )

        # Reassemble chunks
        final_translations = self._reassemble_chunks(translations, chunk_map)

        # Build metadata if requested
        metadata = None
        if include_metadata:
            # Get model info
            try:
                model_name, src_lang, tgt_lang = model_manager._get_model_name_and_langs(src, tgt)
            except Exception:
                model_name = f"unknown-{src}-{tgt}"
                src_lang, tgt_lang = src, tgt

            languages_used = [src_lang, tgt_lang]
            if pivot_used and config.PIVOT_LANG not in [src, tgt]:
                pivot_model = config.PIVOT_LANG
                if config.MODEL_FAMILY == "mbart50":
                    pivot_model = f"{config.PIVOT_LANG}_XX"
                languages_used = [src_lang, pivot_model, tgt_lang]

            metadata = {
                "model_name": model_name,
                "model_family": config.MODEL_FAMILY,
                "languages_used": languages_used,
                "chunks_processed": total_chunks,
                "chunk_size": config.AUTO_CHUNK_MAX_CHARS,
                "auto_chunked": auto_chunked
            }

        return (final_translations, pivot_used, metadata)


# We'll instantiate this in the main app with the executor
