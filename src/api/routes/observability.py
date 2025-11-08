"""Health, readiness, and observability endpoints."""

import torch
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from src.config import config
from src.core.device import device_manager
from src.services.model_manager import model_manager
from src.services.queue_manager import queue_manager
from src.models import (
    HealthResponse,
    ReadinessResponse,
    CacheStatusResponse,
    ModelInfoResponse
)


router = APIRouter()


@router.get("/", include_in_schema=False)
async def root():
    """Redirect root to API docs."""
    return RedirectResponse(url="/docs")


@router.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns health status"
)
async def healthz():
    """Health check endpoint."""
    return HealthResponse(status="ok")


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    summary="Readiness Check",
    description="Returns readiness status with device and queue info"
)
async def readyz():
    """Readiness check endpoint."""
    device_ok = (device_manager.device_index == -1) or torch.cuda.is_available()

    return ReadinessResponse(
        status="ready" if device_ok else "degraded",
        device=device_manager.device_str,
        queue_enabled=config.ENABLE_QUEUE,
        max_inflight=queue_manager.max_inflight
    )


@router.get(
    "/cache",
    response_model=CacheStatusResponse,
    summary="Cache Status",
    description="Returns the currently cached translation pipelines and queue info"
)
async def cache_status():
    """Cache status endpoint."""
    return CacheStatusResponse(
        capacity=model_manager.cache.capacity,
        size=len(model_manager.cache),
        keys=list(model_manager.cache.keys()),
        device=device_manager.device_str,
        inflight=queue_manager.max_inflight,
        queue_enabled=config.ENABLE_QUEUE
    )


@router.get(
    "/model_name",
    response_model=ModelInfoResponse,
    summary="Model Name",
    description="Returns the name of the loaded model and configuration snapshot"
)
async def model_name():
    """Model info endpoint."""
    return ModelInfoResponse(
        model_name="Helsinki-NLP/opus-mt (dynamic)",
        device=device_manager.device_str,
        easynmt_model=config.EASYNMT_MODEL,
        batch_size=config.EASYNMT_BATCH_SIZE,
        max_text_len=config.EASYNMT_MAX_TEXT_LEN_INT,
        max_beam_size=config.EASYNMT_MAX_BEAM_SIZE_INT,
        workers={
            "backend": config.MAX_WORKERS_BACKEND,
            "frontend": config.MAX_WORKERS_FRONTEND,
        },
        input_sanitize=config.INPUT_SANITIZE,
        input_sanitize_min_alnum_ratio=config.INPUT_MIN_ALNUM_RATIO,
        input_sanitize_min_chars=config.INPUT_MIN_CHARS,
        undetermined_lang_code=config.UNDETERMINED_LANG_CODE,
        align_responses=config.ALIGN_RESPONSES,
        sanitize_placeholder=config.SANITIZE_PLACEHOLDER,
        sentence_splitting_default=config.PERFORM_SENTENCE_SPLITTING_DEFAULT,
        max_sentence_chars=config.MAX_SENTENCE_CHARS,
        max_chunk_chars=config.MAX_CHUNK_CHARS,
        join_sentences_with=config.JOIN_SENTENCES_WITH,
        pivot_fallback=config.PIVOT_FALLBACK,
        pivot_lang=config.PIVOT_LANG,
        logging={
            "log_level": config.LOG_LEVEL,
            "log_to_file": config.LOG_TO_FILE,
            "log_file_path": config.LOG_FILE_PATH if config.LOG_TO_FILE else None,
            "log_format": config.LOG_FORMAT,
            "request_log": config.REQUEST_LOG,
            "log_include_text": config.LOG_INCLUDE_TEXT,
        }
    )
