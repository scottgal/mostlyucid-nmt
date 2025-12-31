"""Translation endpoints."""

import time
import uuid
import asyncio
from typing import List, Union, Optional, TYPE_CHECKING

from fastapi import Request, HTTPException

from src.config import config
from src.models import TranslatePostBody, TranslateResponse, TranslatePostResponse, TranslationMetadata
from src.core.logging import logger
from src.services.language_detection import language_detector
from src.services.queue_manager import acquire_translate_slot, queue_manager
from src.exceptions import QueueOverflowError, ServiceBusyError, TextTooLongError
from src.utils.text_processing import is_noise


def _is_pi_mode() -> bool:
    """Check if we're running in Pi mode (explicitly set or auto-detected).

    Returns:
        True if running in Pi mode
    """
    if config.PI_MODE:
        return True

    try:
        from src.core.pi_optimizations import pi_optimizer
        if pi_optimizer.is_pi:
            return True
    except ImportError:
        pass

    return False


def _get_max_input_length() -> int:
    """Get maximum input text length based on environment.

    Returns:
        Maximum allowed text length in characters
    """
    if _is_pi_mode():
        return config.PI_MAX_INPUT_TEXT_LENGTH

    return config.MAX_INPUT_TEXT_LENGTH


def _get_translate_timeout() -> int:
    """Get effective translation timeout in seconds.

    Uses PI_TRANSLATE_TIMEOUT_SEC on Pi if TRANSLATE_TIMEOUT_SEC is 0.

    Returns:
        Timeout in seconds, or 0 to disable
    """
    # If user explicitly set a timeout, use it
    if config.TRANSLATE_TIMEOUT_SEC > 0:
        return config.TRANSLATE_TIMEOUT_SEC

    # On Pi, use Pi-specific timeout
    if _is_pi_mode():
        return config.PI_TRANSLATE_TIMEOUT_SEC

    return 0  # No timeout by default


def _validate_text_lengths(texts: List[str]) -> None:
    """Validate that all texts are within allowed length limits.

    Args:
        texts: List of texts to validate

    Raises:
        TextTooLongError: If any text exceeds the maximum length
    """
    max_length = _get_max_input_length()
    if max_length <= 0:
        return  # Validation disabled

    for i, text in enumerate(texts):
        if text and len(text) > max_length:
            raise TextTooLongError(len(text), max_length, i)

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

    # Validate text lengths before processing
    try:
        _validate_text_lengths(base_texts)
    except TextTooLongError as e:
        if config.REQUEST_LOG:
            logger.warning(f"{req_id} text too long: {e}")
        raise HTTPException(
            status_code=413,
            detail={
                "message": f"Text too long: {e.text_length} chars exceeds limit of {e.max_length}",
                "text_length": e.text_length,
                "max_length": e.max_length,
                "item_index": e.item_index
            }
        )

    # Detect language if needed using first non-noise string
    first_non_noise = next(
        (t for t in base_texts if t and (not config.INPUT_SANITIZE or not is_noise(t))),
        ""
    )
    src = source_lang or language_detector.detect_language(first_non_noise)
    eff_beam = _get_effective_beam_size(beam_size)

    # Check if metadata is requested via header or global config
    enable_metadata_header = request.headers.get("X-Enable-Metadata", "").lower() in ("1", "true", "yes")
    include_metadata = enable_metadata_header or config.ENABLE_METADATA

    start_t = time.perf_counter()
    texts = []
    pivot_used = False
    metadata_dict = None
    error = None

    try:
        async with await acquire_translate_slot():
            timeout_sec = _get_translate_timeout()
            if timeout_sec > 0:
                texts, pivot_used, metadata_dict, error = await asyncio.wait_for(
                    translation_service.translate_async(base_texts, src, target_lang, eff_beam, perform_sentence_splitting, include_metadata),
                    timeout=timeout_sec
                )
            else:
                texts, pivot_used, metadata_dict, error = await translation_service.translate_async(
                    base_texts, src, target_lang, eff_beam, perform_sentence_splitting, include_metadata
                )

    except asyncio.TimeoutError:
        logger.warning(f"{req_id} translation timed out after {_get_translate_timeout()}s")
        raise HTTPException(
            status_code=504,
            detail={"message": f"Translation timed out after {_get_translate_timeout()} seconds"}
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

    pivot_path = None
    if pivot_used:
        pivot_path = f"{src}->{config.PIVOT_LANG}->{target_lang}"

    response = TranslateResponse(translations=texts, pivot_path=pivot_path, error=error)

    # Optionally add metadata to response headers
    if config.METADATA_VIA_HEADERS and metadata_dict:
        from fastapi import Response
        import json

        response_dict = response.model_dump(exclude_none=True)
        json_response = Response(
            content=json.dumps(response_dict),
            media_type="application/json",
            headers={
                "X-Model-Name": metadata_dict.get("model_name", ""),
                "X-Model-Family": metadata_dict.get("model_family", ""),
                "X-Languages-Used": ",".join(metadata_dict.get("languages_used", [])),
                "X-Chunks-Processed": str(metadata_dict.get("chunks_processed", 0)),
                "X-Auto-Chunked": str(metadata_dict.get("auto_chunked", False)).lower()
            }
        )
        return json_response

    return response


async def translate_post(
    request: Request,
    body: TranslatePostBody,
    translation_service: "TranslationService"
):
    """POST endpoint for translation."""
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    base_texts = _normalize_texts(body.text)

    # Check if metadata is requested via header or global config
    enable_metadata_header = request.headers.get("X-Enable-Metadata", "").lower() in ("1", "true", "yes")
    include_metadata = enable_metadata_header or config.ENABLE_METADATA

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

    # Validate text lengths before processing
    try:
        _validate_text_lengths(base_texts)
    except TextTooLongError as e:
        if config.REQUEST_LOG:
            logger.warning(f"{req_id} text too long: {e}")
        raise HTTPException(
            status_code=413,
            detail={
                "message": f"Text too long: {e.text_length} chars exceeds limit of {e.max_length}",
                "text_length": e.text_length,
                "max_length": e.max_length,
                "item_index": e.item_index
            }
        )

    # Track if source language was auto-detected for detected_langs field
    was_auto_detected = not body.source_lang
    src = body.source_lang or language_detector.detect_language(
        next((t for t in base_texts if t and (not config.INPUT_SANITIZE or not is_noise(t))), "")
    )
    eff_beam = _get_effective_beam_size(body.beam_size)

    start_t = time.perf_counter()
    texts = []
    pivot_used = False
    metadata_dict = None
    error = None

    try:
        async with await acquire_translate_slot():
            timeout_sec = _get_translate_timeout()
            if timeout_sec > 0:
                texts, pivot_used, metadata_dict, error = await asyncio.wait_for(
                    translation_service.translate_async(base_texts, src, body.target_lang, eff_beam, perform_sentence_splitting, include_metadata, body.model_family),
                    timeout=timeout_sec
                )
            else:
                texts, pivot_used, metadata_dict, error = await translation_service.translate_async(
                    base_texts, src, body.target_lang, eff_beam, perform_sentence_splitting, include_metadata, body.model_family
                )

    except asyncio.TimeoutError:
        logger.warning(f"{req_id} translation timed out after {_get_translate_timeout()}s")
        raise HTTPException(
            status_code=504,
            detail={"message": f"Translation timed out after {_get_translate_timeout()} seconds"}
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

    pivot_path = None
    # Only show pivot path if it makes sense (pivot lang isn't source or target)
    if pivot_used and config.PIVOT_LANG not in (src, body.target_lang):
        pivot_path = f"{src}->{config.PIVOT_LANG}->{body.target_lang}"

    # Build metadata object if requested
    metadata_obj = None
    if include_metadata and metadata_dict:
        metadata_obj = TranslationMetadata(**metadata_dict)

    # Include detected_langs for EasyNMT compatibility when source was auto-detected
    detected_langs = [src] if was_auto_detected else None

    response = TranslatePostResponse(
        target_lang=body.target_lang,
        source_lang=src,
        detected_langs=detected_langs,
        translated=texts,
        translation_time=float(duration_sec),
        pivot_path=pivot_path,
        metadata=metadata_obj,
        error=error
    )

    # Optionally add metadata to response headers
    if config.METADATA_VIA_HEADERS and metadata_dict:
        # Custom response with headers (FastAPI will handle this)
        from fastapi import Response
        import json

        response_dict = response.model_dump(exclude_none=True)
        json_response = Response(
            content=json.dumps(response_dict),
            media_type="application/json",
            headers={
                "X-Model-Name": metadata_dict.get("model_name", ""),
                "X-Model-Family": metadata_dict.get("model_family", ""),
                "X-Languages-Used": ",".join(metadata_dict.get("languages_used", [])),
                "X-Chunks-Processed": str(metadata_dict.get("chunks_processed", 0)),
                "X-Auto-Chunked": str(metadata_dict.get("auto_chunked", False)).lower()
            }
        )
        return json_response

    return response
