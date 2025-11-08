"""Language detection and metadata endpoints."""

import asyncio
from typing import Optional, Union, List, Dict
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter

from src.config import config
from src.models import (
    LanguagePairsResponse,
    LanguagesResponse,
    LanguageDetectionResponse,
    LanguageDetectionPostBody
)
from src.services.language_detection import language_detector


router = APIRouter()


@router.get(
    "/lang_pairs",
    response_model=LanguagePairsResponse,
    summary="Lang Pairs",
    description="Returns the language pairs from the model\n:return:"
)
async def lang_pairs():
    """Get all supported language pairs."""
    supported_langs = config.get_supported_langs()
    pairs = []
    for src in supported_langs:
        for tgt in supported_langs:
            if src != tgt:
                pairs.append([src, tgt])
    return LanguagePairsResponse(language_pairs=pairs)


@router.get(
    "/get_languages",
    response_model=LanguagesResponse,
    summary="Get Languages",
    description=(
        "Returns the languages the model supports\n"
        ":param source_lang: Optional. Only return languages with this language as source\n"
        ":param target_lang: Optional. Only return languages with this language as target\n:return:"
    )
)
async def get_languages(
    source_lang: Optional[str] = None,
    target_lang: Optional[str] = None
):
    """Get supported languages with optional filtering."""
    supported_langs = config.get_supported_langs()
    if source_lang and source_lang in supported_langs:
        # Return targets for this source
        languages = [l for l in supported_langs if l != source_lang]
    elif target_lang and target_lang in supported_langs:
        # Return sources for this target
        languages = [l for l in supported_langs if l != target_lang]
    else:
        languages = supported_langs

    return LanguagesResponse(languages=languages)


async def language_detection_get(
    text: str,
    frontend_executor: ThreadPoolExecutor
):
    """GET endpoint for language detection."""
    loop = asyncio.get_event_loop()
    lang = await loop.run_in_executor(
        frontend_executor,
        language_detector.detect_language,
        text
    )
    return LanguageDetectionResponse(language=lang)


async def language_detection_post(
    body: LanguageDetectionPostBody,
    frontend_executor: ThreadPoolExecutor
):
    """POST endpoint for language detection (batch)."""
    payload = body.text
    loop = asyncio.get_event_loop()

    def _work():
        if isinstance(payload, str):
            return {"language": language_detector.detect_language(payload)}
        if isinstance(payload, list):
            return {"languages": language_detector.detect_languages_batch(payload)}
        if isinstance(payload, dict):
            return language_detector.detect_languages_dict(payload)
        return {"error": "Invalid payload"}

    return await loop.run_in_executor(frontend_executor, _work)
