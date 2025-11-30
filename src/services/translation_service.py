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
from src.utils.markdown_sanitizer import sanitize_translations


class TranslationService:
    """Service for translating text with full processing pipeline."""

    def __init__(self, executor: ThreadPoolExecutor):
        """Initialize translation service.

        Args:
            executor: ThreadPoolExecutor for CPU-bound work
        """
        self.executor = executor

    def _get_available_targets_from_source(self, src: str) -> set:
        """Get all languages that can be translated TO from source.

        Args:
            src: Source language code

        Returns:
            Set of target language codes where src→tgt is supported
        """
        from src.services.model_manager import model_manager
        targets = set()

        # Check all model families
        for family in ["opus-mt", "mbart50", "m2m100"]:
            if family == "mbart50":
                langs = set(config.MBART50_LANGS)
            elif family == "m2m100":
                langs = set(config.M2M100_LANGS)
            else:  # opus-mt
                langs = set(config.SUPPORTED_LANGS)

            # For each potential target, check if pair is supported
            for tgt in langs:
                if tgt != src and model_manager._is_pair_supported(src, tgt, family):
                    targets.add(tgt)

        return targets

    def _get_available_sources_to_target(self, tgt: str) -> set:
        """Get all languages that can be translated FROM to reach target.

        Args:
            tgt: Target language code

        Returns:
            Set of source language codes where src→tgt is supported
        """
        from src.services.model_manager import model_manager
        sources = set()

        # Check all model families
        for family in ["opus-mt", "mbart50", "m2m100"]:
            if family == "mbart50":
                langs = set(config.MBART50_LANGS)
            elif family == "m2m100":
                langs = set(config.M2M100_LANGS)
            else:  # opus-mt
                langs = set(config.SUPPORTED_LANGS)

            # For each potential source, check if pair is supported
            for src in langs:
                if src != tgt and model_manager._is_pair_supported(src, tgt, family):
                    sources.add(src)

        return sources

    def _select_pivot_language(self, src: str, tgt: str) -> Optional[str]:
        """Intelligently select a pivot language using data-driven approach.

        Args:
            src: Source language code
            tgt: Target language code

        Returns:
            Pivot language code, or None if no suitable pivot available

        Strategy:
            1. Find all languages X where src→X exists
            2. Find all languages Y where Y→tgt exists
            3. Find intersection (languages that work for BOTH legs)
            4. Pick best from intersection (prefer default pivot lang, then by priority)
        """
        # Get all possible pivot languages (intersection of available routes)
        logger.debug(f"[Pivot] Finding common intermediary languages for {src}→{tgt}")

        # Languages reachable FROM source
        from_source = self._get_available_targets_from_source(src)
        logger.debug(f"[Pivot] Languages reachable from {src}: {len(from_source)} languages")

        # Languages that can reach target
        to_target = self._get_available_sources_to_target(tgt)
        logger.debug(f"[Pivot] Languages that can reach {tgt}: {len(to_target)} languages")

        # Find common intermediaries (both legs exist)
        common_pivots = from_source & to_target

        # Remove source and target from candidates
        common_pivots.discard(src)
        common_pivots.discard(tgt)

        if not common_pivots:
            logger.warning(f"[Pivot] No common intermediary language found for {src}→{tgt}")
            logger.debug(f"[Pivot] from_source={sorted(list(from_source)[:10])}, to_target={sorted(list(to_target)[:10])}")
            return None

        logger.info(f"[Pivot] Found {len(common_pivots)} possible pivot languages: {sorted(list(common_pivots)[:10])}")

        # Priority order for selecting from common pivots
        priority_order = [
            config.PIVOT_LANG,  # Default (usually "en")
            "es", "fr", "de", "zh", "ru",  # Major languages
            "it", "pt", "nl", "pl", "ja",  # Secondary major languages
        ]

        # First, try pivots in priority order
        for candidate in priority_order:
            if candidate in common_pivots:
                logger.info(f"[Pivot] Selected pivot: {src} → {candidate} → {tgt} (priority match)")
                return candidate

        # If no priority match, pick any common pivot (alphabetically first for consistency)
        pivot = sorted(common_pivots)[0]
        logger.info(f"[Pivot] Selected pivot: {src} → {pivot} → {tgt} (from {len(common_pivots)} available)")
        return pivot

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

        # Apply symbol masking to protect special characters
        masked_chunks: List[str] = []
        mask_data: List[List[str]] = []

        for chunk in chunks:
            masked_text, originals = mask_symbols(chunk)
            masked_chunks.append(masked_text)
            mask_data.append(originals)

        logger.debug(f"[Masking] Masked {len(chunks)} chunks, found {sum(len(m) for m in mask_data)} symbol sequences")

        out_chunks: List[str] = []
        bs = max(1, config.EASYNMT_BATCH_SIZE)

        for i in range(0, len(masked_chunks), bs):
            batch = masked_chunks[i:i + bs]
            res = translator(batch, max_length=gen_max_len, num_beams=eff_beam, batch_size=len(batch))
            out_chunks.extend([r.get("translation_text", "") for r in res])

        # Unmask symbols in translated output
        final_chunks: List[str] = []
        for translated, originals in zip(out_chunks, mask_data):
            unmasked = unmask_symbols(translated, originals)
            final_chunks.append(unmasked)

        logger.debug(f"[Unmasking] Restored symbols in {len(final_chunks)} chunks")

        return final_chunks

    def _translate_text_single(
        self,
        txt: str,
        src: str,
        tgt: str,
        eff_beam: int,
        perform_sentence_splitting: bool,
        translator_direct: Optional[any] = None,
        preferred_family: Optional[str] = None
    ) -> Tuple[str, bool, Optional[str]]:
        """Translate a single text item.

        Args:
            txt: Text to translate
            src: Source language
            tgt: Target language
            eff_beam: Beam size
            perform_sentence_splitting: Whether to split sentences
            translator_direct: Pre-loaded translator or None

        Returns:
            Tuple of (translated text or placeholder if failed, pivot_used flag, optional error message)
        """
        logger.debug(f"[Translate] Input text (len={len(txt)}): {txt[:100]}...")

        if config.INPUT_SANITIZE and is_noise(txt):
            logger.info(f"[Translate] Text detected as noise, skipping translation")
            return (config.SANITIZE_PLACEHOLDER, False, None)

        gen_max_len = 512
        if config.EASYNMT_MAX_TEXT_LEN_INT is not None:
            gen_max_len = min(gen_max_len, max(1, config.EASYNMT_MAX_TEXT_LEN_INT))

        try:
            translator = translator_direct or model_manager.get_pipeline(src, tgt, preferred_family)
            logger.debug(f"[Translate] Got pipeline for {src}->{tgt} (family: {preferred_family or 'default'})")

            if perform_sentence_splitting:
                sents = split_sentences(txt)
                logger.debug(f"[Translate] Split into {len(sents)} sentences")
                chunks = chunk_sentences(sents, config.MAX_CHUNK_CHARS)
                logger.debug(f"[Translate] Created {len(chunks)} chunks")
                out = self._translate_with_translator(translator, chunks, eff_beam)
                logger.debug(f"[Translate] Translation output: {out[:2] if len(out) > 2 else out}")
                combined = config.JOIN_SENTENCES_WITH.join(out)
                combined = remove_repeating_new_symbols(txt, combined)
                logger.info(f"[Translate] Success with sentence splitting: {combined[:50]}...")
                return (combined, False, None)
            else:
                logger.debug(f"[Translate] Translating without sentence splitting")
                # Apply symbol masking
                masked_txt, originals = mask_symbols(txt)
                logger.debug(f"[Masking] Masked text, found {len(originals)} symbol sequences")

                res = translator([masked_txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                logger.debug(f"[Translate] Raw result: {res}")
                base = res[0].get("translation_text", config.SANITIZE_PLACEHOLDER)
                logger.debug(f"[Translate] Extracted translation_text: '{base}'")

                # Unmask symbols
                base = unmask_symbols(base, originals)
                logger.debug(f"[Unmasking] Restored symbols")

                base = remove_repeating_new_symbols(txt, base)
                logger.info(f"[Translate] Success: '{base}'")
                return (base, False, None)

        except Exception as direct_err:
            # Attempt pivot fallback if enabled
            logger.error(f"[Translate] Direct translation failed: {type(direct_err).__name__}: {direct_err}")
            if not config.PIVOT_FALLBACK:
                error_msg = f"Translation failed for {src}→{tgt}: {str(direct_err)}. Pivot fallback disabled."
                logger.warning(f"[Translate] Pivot fallback disabled, returning placeholder")
                return (config.SANITIZE_PLACEHOLDER, False, error_msg)

            # Intelligently select pivot language (avoid using source or target as pivot)
            pivot_lang = self._select_pivot_language(src, tgt)
            if not pivot_lang:
                error_msg = f"Translation failed for {src}→{tgt}: No suitable pivot language available"
                logger.warning(f"[Translate] No suitable pivot language found, returning placeholder")
                return (config.SANITIZE_PLACEHOLDER, False, error_msg)

            try:
                # For pivot, allow AUTO_MODEL_FALLBACK to try any family (don't restrict to preferred)
                # This lets mbart50/m2m100 be used for pivot even if opus-mt was originally requested
                logger.info(f"[Pivot] Attempting pivot translation: {src} → {pivot_lang} → {tgt}")
                logger.info(f"[Pivot] Loading first leg: {src} → {pivot_lang}")
                trans_src_pivot = model_manager.get_pipeline(src, pivot_lang, preferred_family=None)
                logger.info(f"[Pivot] First leg loaded, now loading second leg: {pivot_lang} → {tgt}")
                trans_pivot_tgt = model_manager.get_pipeline(pivot_lang, tgt, preferred_family=None)
                logger.info(f"[Pivot] Both legs loaded and cached. Ready to translate.")

                if perform_sentence_splitting:
                    sents = split_sentences(txt)
                    chunks = chunk_sentences(sents, config.MAX_CHUNK_CHARS)

                    # First hop: src -> pivot
                    mid = self._translate_with_translator(trans_src_pivot, chunks, eff_beam)

                    # Second hop: pivot -> tgt
                    final = self._translate_with_translator(trans_pivot_tgt, mid, eff_beam)

                    combined = config.JOIN_SENTENCES_WITH.join(final)
                    combined = remove_repeating_new_symbols(txt, combined)
                    return (combined, True, None)
                else:
                    # Apply symbol masking for pivot translation
                    masked_txt, originals = mask_symbols(txt)

                    mid = trans_src_pivot([masked_txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                    mid_txt = mid[0].get("translation_text", "")

                    fin = trans_pivot_tgt([mid_txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                    base = fin[0].get("translation_text", config.SANITIZE_PLACEHOLDER)

                    # Unmask symbols
                    base = unmask_symbols(base, originals)

                    base = remove_repeating_new_symbols(txt, base)
                    return (base, True, None)

            except Exception as pivot_err:
                logger.warning(f"[Pivot] Pivot translation failed: {type(pivot_err).__name__}: {pivot_err}")

                # Last resort: try direct translation with unitary models (mbart50/m2m100)
                # These multilingual models might support the pair directly even if opus-mt doesn't
                logger.info(f"[Fallback] Attempting direct translation with unitary models: {src} → {tgt}")
                for fallback_family in ["mbart50", "m2m100"]:
                    try:
                        translator_fallback = model_manager.get_pipeline(src, tgt, preferred_family=fallback_family)
                        logger.info(f"[Fallback] Loaded {fallback_family} model for direct {src}→{tgt}")

                        if perform_sentence_splitting:
                            sents = split_sentences(txt)
                            chunks = chunk_sentences(sents, config.MAX_CHUNK_CHARS)
                            translated_chunks = self._translate_with_translator(translator_fallback, chunks, eff_beam)
                            combined = config.JOIN_SENTENCES_WITH.join(translated_chunks)
                            combined = remove_repeating_new_symbols(txt, combined)
                            logger.info(f"[Fallback] Success with {fallback_family}: '{combined[:100]}'")
                            return (combined, False, None)  # Not a pivot, direct translation
                        else:
                            # Apply symbol masking for fallback translation
                            masked_txt, originals = mask_symbols(txt)

                            res = translator_fallback([masked_txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                            base = res[0].get("translation_text", config.SANITIZE_PLACEHOLDER)

                            # Unmask symbols
                            base = unmask_symbols(base, originals)

                            base = remove_repeating_new_symbols(txt, base)
                            logger.info(f"[Fallback] Success with {fallback_family}: '{base[:100]}'")
                            return (base, False, None)  # Not a pivot, direct translation
                    except Exception as fallback_err:
                        logger.debug(f"[Fallback] {fallback_family} failed for {src}→{tgt}: {fallback_err}")
                        continue

                # All fallback attempts failed
                error_msg = f"Unsupported language pair {src}→{tgt}. No model available (tried opus-mt, pivot via {pivot_lang}, mbart50, m2m100)"
                logger.error(f"[Fallback] All translation attempts failed for {src}→{tgt}")
                return (config.SANITIZE_PLACEHOLDER, False, error_msg)

    def translate_texts_aligned(
        self,
        input_texts: List[str],
        src: str,
        tgt: str,
        eff_beam: int,
        perform_sentence_splitting: bool,
        preferred_family: Optional[str] = None
    ) -> Tuple[List[str], bool, Optional[str]]:
        """Translate list of texts while preserving alignment.

        Args:
            input_texts: List of texts to translate
            src: Source language
            tgt: Target language
            eff_beam: Beam size
            perform_sentence_splitting: Whether to split sentences
            preferred_family: Preferred model family (opus-mt, mbart50, m2m100)

        Returns:
            Tuple of (list of translations (same length as input), pivot_used flag, first error if any)
        """
        outputs: List[str] = []
        pivot_used = False
        first_error: Optional[str] = None

        # Try to load direct translator once
        translator_direct = None
        fallback_to_pivot = False
        try:
            translator_direct = model_manager.get_pipeline(src, tgt, preferred_family)
            logger.info(f"Loaded direct translator for {src}→{tgt}, will use for all texts")
        except Exception as e:
            # Direct load failed - don't retry with same preferred_family, let pivot/fallback handle it
            logger.warning(f"Direct pipeline load failed for {src}→{tgt}, will use pivot/fallback per item: {e}")
            pivot_used = True  # Direct pipeline not available
            fallback_to_pivot = True

        for t in input_texts:
            try:
                txt = t if isinstance(t, str) else ""
                # If direct load failed, pass None for preferred_family to avoid retrying same family
                translated, item_pivot_used, error = self._translate_text_single(
                    txt, src, tgt, eff_beam, perform_sentence_splitting,
                    translator_direct=translator_direct,
                    preferred_family=None if fallback_to_pivot else preferred_family
                )
                if item_pivot_used:
                    pivot_used = True
                if error and not first_error:
                    first_error = error
                outputs.append(translated if isinstance(translated, str) else config.SANITIZE_PLACEHOLDER)
            except Exception as e:
                if config.REQUEST_LOG:
                    logger.warning(f"Per-item translation failed, inserting placeholder: {e}")
                if not first_error:
                    first_error = f"Translation error: {str(e)}"
                outputs.append(config.SANITIZE_PLACEHOLDER)

        # Apply markdown sanitization to prevent parser depth errors
        sanitized_outputs, any_sanitized, sanitize_issues = sanitize_translations(outputs, src, tgt)
        if any_sanitized:
            # Log at WARNING since sanitization indicates translation produced malformed markdown
            logger.warning(f"[Markdown] Sanitized {len(sanitize_issues)} issues for {src}->{tgt}: {sanitize_issues[:3]}")

        return (sanitized_outputs, pivot_used, first_error)

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
        include_metadata: bool = False,
        preferred_family: Optional[str] = None
    ) -> Tuple[List[str], bool, Optional[Dict[str, Any]], Optional[str]]:
        """Asynchronously translate texts using thread pool.

        Args:
            texts: List of texts to translate
            src: Source language
            tgt: Target language
            beam_size: Beam size
            perform_sentence_splitting: Whether to split sentences
            include_metadata: Whether to include metadata in response
            preferred_family: Preferred model family (opus-mt, mbart50, m2m100)

        Returns:
            Tuple of (list of translations, pivot_used flag, optional metadata dict, optional error message)
        """
        loop = asyncio.get_event_loop()

        # Auto-chunk if needed
        chunked_texts, chunk_map = self._auto_chunk_texts(texts)
        auto_chunked = any(num_chunks > 1 for _, num_chunks in chunk_map)
        total_chunks = sum(num_chunks for _, num_chunks in chunk_map)

        # Translate chunked texts
        translations, pivot_used, error = await loop.run_in_executor(
            self.executor,
            self.translate_texts_aligned,
            chunked_texts,
            src,
            tgt,
            beam_size,
            perform_sentence_splitting,
            preferred_family
        )

        # Reassemble chunks
        final_translations = self._reassemble_chunks(translations, chunk_map)

        # Build metadata if requested
        metadata = None
        if include_metadata or error:
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

        return (final_translations, pivot_used, metadata, error)


# We'll instantiate this in the main app with the executor
