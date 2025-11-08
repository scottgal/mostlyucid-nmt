"""Translation endpoints."""

import time
import uuid
import asyncio
from typing import List, Union, Optional, TYPE_CHECKING

from fastapi import Request, HTTPException

from src.config import config
from src.models import TranslatePostBody, TranslateResponse, TranslatePostResponse
from src.core.logging import logger
from src.services.language_detection import language_detector
from src.services.queue_manager import acquire_translate_slot, queue_manager
from src.exceptions import QueueOverflowError, ServiceBusyError, UnsupportedLanguagePairError
from src.utils.text_processing import is_noise

if TYPE_CHECKING:
    from src.services.translation_service import TranslationService


def _normalize_texts(text: Union[str, List[str]]) -> List[str]:
    """Convert text input to list of strings.

    Args:
        text: String or list of strings

    Returns:
        List of strings
    """
    if isinstance(text, list):
        return [t if isinstance(t, str) else "" for t in text]
    elif isinstance(text, str):
        return [text]
    else:
        return []


def _validate_language_pair(src: str, tgt: str) -> None:
    """Validate language pair is supported.

    Args:
        src: Source language code
        tgt: Target language code

    Raises:
        UnsupportedLanguagePairError: If pair is invalid
    """
    supported_langs = config.get_supported_langs()
    if src not in supported_langs or tgt not in supported_langs or src == tgt:
        raise UnsupportedLanguagePairError(src, tgt)


def _get_effective_beam_size(beam_size: int) -> int:
    """Get effective beam size after applying constraints.

    Args:
        beam_size: Requested beam size

    Returns:
        Clamped beam size
    """
    eff_beam = max(1, beam_size)
    if config.EASYNMT_MAX_BEAM_SIZE_INT is not None:
        eff_beam = min(eff_beam, max(1, config.EASYNMT_MAX_BEAM_SIZE_INT))
    return eff_beam


async def translate_get(
    request: Request,
    translation_service: "TranslationService",
    target_lang: str,
    text: List[str],
    source_lang: str,
    beam_size: int,
    perform_sentence_splitting: bool,
):
    """GET endpoint for translation."""
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    base_texts = _normalize_texts(text)

    if perform_sentence_splitting is None:
        perform_sentence_splitting = config.PERFORM_SENTENCE_SPLITTING_DEFAULT

    if config.REQUEST_LOG:
        logger.info(
            f"{req_id} translate_get received target={target_lang} src={source_lang} items={len(base_texts)}"
        )

    if not base_texts:
        return TranslateResponse(translations=[])

    # Detect language if needed using first non-noise string
    first_non_noise = next(
        (t for t in base_texts if t and (not config.INPUT_SANITIZE or not is_noise(t))),
        ""
    )
    src = source_lang or language_detector.detect_language(first_non_noise)

    try:
        _validate_language_pair(src, target_lang)
    except UnsupportedLanguagePairError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "Unsupported language pair", "src": e.source_lang, "tgt": e.target_lang}
        )

    eff_beam = _get_effective_beam_size(beam_size)

    start_t = time.perf_counter()
    texts = []

    try:
        async with await acquire_translate_slot():
            if config.TRANSLATE_TIMEOUT_SEC > 0:
                texts = await asyncio.wait_for(
                    translation_service.translate_async(base_texts, src, target_lang, eff_beam, perform_sentence_splitting),
                    timeout=config.TRANSLATE_TIMEOUT_SEC
                )
            else:
                texts = await translation_service.translate_async(
                    base_texts, src, target_lang, eff_beam, perform_sentence_splitting
                )

    except QueueOverflowError as e:
        retry_after = queue_manager.estimate_retry_after(e.waiters)
        if config.REQUEST_LOG:
            logger.warning(f"translate_get overload: 429, retry_after={retry_after}s, waiters={e.waiters}")
        raise HTTPException(
            status_code=429,
            detail={"message": "Too many requests; queue full", "retry_after_sec": retry_after},
            headers={"Retry-After": str(retry_after)}
        )

    except ServiceBusyError:
        retry_after = queue_manager.estimate_retry_after()
        if config.REQUEST_LOG:
            logger.warning(f"translate_get busy: 503, retry_after={retry_after}s")
        raise HTTPException(
            status_code=503,
            detail={"message": "Server busy", "retry_after_sec": retry_after},
            headers={"Retry-After": str(retry_after)}
        )

    finally:
        if texts:
            dt = max(0.0, time.perf_counter() - start_t)
            await queue_manager.record_duration(dt)

    if config.REQUEST_LOG:
        logger.info(f"{req_id} translate_get done items={len(texts)}")

    return TranslateResponse(translations=texts)


async def translate_post(
    request: Request,
    body: TranslatePostBody,
    translation_service: "TranslationService"
):
    """POST endpoint for translation."""
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    base_texts = _normalize_texts(body.text)

    perform_sentence_splitting = (
        body.perform_sentence_splitting
        if body.perform_sentence_splitting is not None
        else config.PERFORM_SENTENCE_SPLITTING_DEFAULT
    )

    if config.REQUEST_LOG:
        logger.info(
            f"{req_id} translate_post received target={body.target_lang} src={body.source_lang} items={len(base_texts)}"
        )

    if not base_texts:
        # Align POST response to schema expectations even on empty input
        return TranslatePostResponse(
            target_lang=body.target_lang,
            source_lang=body.source_lang or "",
            translated=[],
            translation_time=0.0
        )

    src = body.source_lang or language_detector.detect_language(
        next((t for t in base_texts if t and (not config.INPUT_SANITIZE or not is_noise(t))), "")
    )

    try:
        _validate_language_pair(src, body.target_lang)
    except UnsupportedLanguagePairError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "Unsupported language pair", "src": e.source_lang, "tgt": e.target_lang}
        )

    eff_beam = _get_effective_beam_size(body.beam_size)

    start_t = time.perf_counter()
    texts = []

    try:
        async with await acquire_translate_slot():
            if config.TRANSLATE_TIMEOUT_SEC > 0:
                texts = await asyncio.wait_for(
                    translation_service.translate_async(base_texts, src, body.target_lang, eff_beam, perform_sentence_splitting),
                    timeout=config.TRANSLATE_TIMEOUT_SEC
                )
            else:
                texts = await translation_service.translate_async(
                    base_texts, src, body.target_lang, eff_beam, perform_sentence_splitting
                )

    except QueueOverflowError as e:
        retry_after = queue_manager.estimate_retry_after(e.waiters)
        if config.REQUEST_LOG:
            logger.warning(f"translate_post overload: 429, retry_after={retry_after}s, waiters={e.waiters}")
        raise HTTPException(
            status_code=429,
            detail={"message": "Too many requests; queue full", "retry_after_sec": retry_after},
            headers={"Retry-After": str(retry_after)}
        )

    except ServiceBusyError:
        retry_after = queue_manager.estimate_retry_after()
        if config.REQUEST_LOG:
            logger.warning(f"translate_post busy: 503, retry_after={retry_after}s")
        raise HTTPException(
            status_code=503,
            detail={"message": "Server busy", "retry_after_sec": retry_after},
            headers={"Retry-After": str(retry_after)}
        )

    finally:
        if texts:
            dt = max(0.0, time.perf_counter() - start_t)
            await queue_manager.record_duration(dt)

    # Build response matching C# client's expected schema
    duration_sec = max(0.0, time.perf_counter() - start_t)

    if config.REQUEST_LOG:
        logger.info(f"{req_id} translate_post done items={len(texts)} dt={duration_sec:.3f}s")

    return TranslatePostResponse(
        target_lang=body.target_lang,
        source_lang=src,
        translated=texts,
        translation_time=float(duration_sec)
    )
