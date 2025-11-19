""EasyNMT compatibility handlers used by /compat endpoints.

These functions mirror EasyNMT's behavior and response shapes exactly,
without the extra fields added by MostlyLucid-NMT.
"""
from typing import List, Union, TYPE_CHECKING
import time
import uuid
import asyncio

from fastapi import Query, Request, HTTPException

from src.config import config
from src.core.logging import logger
from src.models import TranslatePostBody
from src.services.language_detection import language_detector
from src.services.queue_manager import acquire_translate_slot, queue_manager
from src.exceptions import QueueOverflowError, ServiceBusyError
from src.utils.text_processing import is_noise

if TYPE_CHECKING:
    from src.services.translation_service import TranslationService


def _normalize_texts(text: Union[str, List[str]]) -> List[str]:
    if isinstance(text, list):
        return [t if isinstance(t, str) else "" for t in text]
    elif isinstance(text, str):
        return [text]
    return []


def _get_effective_beam_size(beam_size: int) -> int:
    eff_beam = max(1, beam_size)
    if config.EASYNMT_MAX_BEAM_SIZE_INT is not None:
        eff_beam = min(eff_beam, max(1, config.EASYNMT_MAX_BEAM_SIZE_INT))
    return eff_beam


async def translate_get_compat(
    request: Request,
    translation_service: "TranslationService",
    target_lang: str,
    text: List[str],
    source_lang: str,
    beam_size: int,
    perform_sentence_splitting: bool,
):
    """EasyNMT-compatible GET returning only {"translations": [...]}"""
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    base_texts = _normalize_texts(text)

    if perform_sentence_splitting is None:
        perform_sentence_splitting = config.PERFORM_SENTENCE_SPLITTING_DEFAULT

    if not base_texts:
        return {"translations": []}

    first_non_noise = next((t for t in base_texts if t and (not config.INPUT_SANITIZE or not is_noise(t))), "")
    src = source_lang or language_detector.detect_language(first_non_noise)
    eff_beam = _get_effective_beam_size(beam_size)

    start_t = time.perf_counter()
    texts: List[str] = []

    try:
        async with await acquire_translate_slot():
            if config.TRANSLATE_TIMEOUT_SEC > 0:
                texts, _pivot_used, _metadata = await asyncio.wait_for(
                    translation_service.translate_async(
                        base_texts, src, target_lang, eff_beam, perform_sentence_splitting, include_metadata=False
                    ),
                    timeout=config.TRANSLATE_TIMEOUT_SEC,
                )
            else:
                texts, _pivot_used, _metadata = await translation_service.translate_async(
                    base_texts, src, target_lang, eff_beam, perform_sentence_splitting, include_metadata=False
                )
    except QueueOverflowError as e:
        retry_after = queue_manager.estimate_retry_after(e.waiters)
        raise HTTPException(status_code=429, detail={"message": "Too many requests; queue full", "retry_after_sec": retry_after}, headers={"Retry-After": str(retry_after)})
    except ServiceBusyError:
        retry_after = queue_manager.estimate_retry_after()
        raise HTTPException(status_code=503, detail={"message": "Server busy", "retry_after_sec": retry_after}, headers={"Retry-After": str(retry_after)})
    finally:
        if texts:
            dt = max(0.0, time.perf_counter() - start_t)
            await queue_manager.record_duration(dt)

    if config.REQUEST_LOG:
        logger.info(f"{req_id} compat.translate_get done items={len(texts)}")

    return {"translations": texts}


async def translate_post_compat(
    request: Request,
    body: TranslatePostBody,
    translation_service: "TranslationService",
):
    """EasyNMT-compatible POST returning only EasyNMT fields."""
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    base_texts = _normalize_texts(body.text)

    perform_sentence_splitting = (
        body.perform_sentence_splitting
        if body.perform_sentence_splitting is not None
        else config.PERFORM_SENTENCE_SPLITTING_DEFAULT
    )

    if not base_texts:
        return {
            "target_lang": body.target_lang,
            "source_lang": body.source_lang or "",
            "translated": [],
            "translation_time": 0.0,
        }

    was_auto_detected = not body.source_lang
    src = body.source_lang or language_detector.detect_language(
        next((t for t in base_texts if t and (not config.INPUT_SANITIZE or not is_noise(t))), "")
    )
    eff_beam = _get_effective_beam_size(body.beam_size)

    start_t = time.perf_counter()
    texts: List[str] = []

    try:
        async with await acquire_translate_slot():
            if config.TRANSLATE_TIMEOUT_SEC > 0:
                texts, _pivot_used, _metadata = await asyncio.wait_for(
                    translation_service.translate_async(
                        base_texts, src, body.target_lang, eff_beam, perform_sentence_splitting, include_metadata=False
                    ),
                    timeout=config.TRANSLATE_TIMEOUT_SEC,
                )
            else:
                texts, _pivot_used, _metadata = await translation_service.translate_async(
                    base_texts, src, body.target_lang, eff_beam, perform_sentence_splitting, include_metadata=False
                )
    except QueueOverflowError as e:
        retry_after = queue_manager.estimate_retry_after(e.waiters)
        raise HTTPException(status_code=429, detail={"message": "Too many requests; queue full", "retry_after_sec": retry_after}, headers={"Retry-After": str(retry_after)})
    except ServiceBusyError:
        retry_after = queue_manager.estimate_retry_after()
        raise HTTPException(status_code=503, detail={"message": "Server busy", "retry_after_sec": retry_after}, headers={"Retry-After": str(retry_after)})
    finally:
        if texts:
            dt = max(0.0, time.perf_counter() - start_t)
            await queue_manager.record_duration(dt)

    duration_sec = max(0.0, time.perf_counter() - start_t)

    if config.REQUEST_LOG:
        logger.info(f"{req_id} compat.translate_post done items={len(texts)} dt={duration_sec:.3f}s")

    resp = {
        "target_lang": body.target_lang,
        "source_lang": src,
        "translated": texts,
        "translation_time": float(duration_sec),
    }
    if was_auto_detected:
        resp["detected_langs"] = [src]
    return resp
