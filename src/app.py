"""Main FastAPI application with dependency injection."""

import asyncio
import torch
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Query, Request
from typing import List
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.config import config
from src.core.logging import logger
from src.core.device import device_manager
from src.services.model_manager import model_manager
from src.services.translation_service import TranslationService
from src.models import TranslatePostBody, LanguageDetectionPostBody
from src.api.routes import observability, discovery, language
import os
import shutil


# Global executors and services
_backend_executor: ThreadPoolExecutor = None
_frontend_executor: ThreadPoolExecutor = None
_translation_service: TranslationService = None
_maintenance_task_handle: asyncio.Task = None


async def _maintenance_task():
    """Periodic CUDA cache clearing task."""
    if config.CUDA_CACHE_CLEAR_INTERVAL_SEC <= 0:
        return

    while True:
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                if config.REQUEST_LOG:
                    logger.info("maintenance: torch.cuda.empty_cache()")
        except Exception as e:
            logger.warning(f"maintenance error: {e}")

        await asyncio.sleep(config.CUDA_CACHE_CLEAR_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    global _backend_executor, _frontend_executor, _translation_service, _maintenance_task_handle

    # Startup
    logger.info("Starting up translation service...")

    try:
        # Initialize executors
        logger.info("Initializing executors...")
        _backend_executor = ThreadPoolExecutor(max_workers=max(1, config.MAX_WORKERS_BACKEND))
        _frontend_executor = ThreadPoolExecutor(max_workers=max(1, config.MAX_WORKERS_FRONTEND))
        logger.info(f"Executors initialized (backend={config.MAX_WORKERS_BACKEND}, frontend={config.MAX_WORKERS_FRONTEND})")

        # Initialize translation service
        logger.info("Initializing translation service...")
        _translation_service = TranslationService(_backend_executor)
        logger.info(f"Translation service initialized: {_translation_service}")

        # Log cache configuration
        logger.info(f"💾 Model cache configured: MAX_CACHED_MODELS={config.MAX_CACHED_MODELS}")
        logger.info(f"   Keeps up to {config.MAX_CACHED_MODELS} models loaded for instant switching (no reload wait)")
        logger.info(f"   Oldest models auto-evicted when cache full")

        # Preload models if requested
        if config.PRELOAD_MODELS:
            logger.info(f"Preloading models: {config.PRELOAD_MODELS}")
            model_manager.preload_models(config.PRELOAD_MODELS)
            # Show cache status after preload
            model_manager.cache.log_status()

        # Start maintenance task
        _maintenance_task_handle = asyncio.create_task(_maintenance_task())

        logger.info("Translation service ready")

    except Exception as e:
        logger.error(f"Failed to initialize translation service: {e}", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("Shutting down translation service...")

    # Stop background tasks
    try:
        if _maintenance_task_handle is not None:
            _maintenance_task_handle.cancel()
            try:
                await asyncio.wait_for(_maintenance_task_handle, timeout=1)
            except Exception:
                pass
    except Exception:
        pass

    # Shutdown executors
    try:
        _backend_executor.shutdown(wait=False, cancel_futures=True)
    except Exception as e:
        logger.warning(f"Error shutting down backend executor: {e}")

    try:
        _frontend_executor.shutdown(wait=False, cancel_futures=True)
    except Exception as e:
        logger.warning(f"Error shutting down frontend executor: {e}")

    # Clear CUDA cache
    if torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass

    logger.info("Translation service stopped")


# Create FastAPI app
app = FastAPI(
    title=config.TITLE,
    version=config.VERSION,
    lifespan=lifespan
)

# Mount static demo at /demo
app.mount("/demo", StaticFiles(directory="public", html=True), name="demo")

# Optional: redirect root to /demo
@app.get(
    "/",
    summary="Root Redirect",
    description="Redirects to the interactive demo UI"
)
async def root_redirect():
    """Redirect root to demo UI."""
    return RedirectResponse(url="/demo/")


# Dependency injection functions
def get_translation_service() -> TranslationService:
    """Get translation service instance."""
    return _translation_service


def get_frontend_executor() -> ThreadPoolExecutor:
    """Get frontend executor instance."""
    return _frontend_executor


# Include routers
app.include_router(observability.router, tags=["Observability"])
app.include_router(discovery.router, tags=["Discovery"])
app.include_router(language.router, tags=["Language"])

# EasyNMT compatibility namespace under /compat
from src.api.routes import compat as compat_handlers

@app.get(
    "/compat/translate",
    tags=["Compatibility"],
    summary="EasyNMT GET /translate (compat)",
)
async def compat_translate_get_endpoint(
    request: Request,
    target_lang: str = Query(...),
    text: List[str] = Query(default=[]),
    source_lang: str = Query(default=""),
    beam_size: int = Query(default=5),
    perform_sentence_splitting: bool = Query(default=True),
    translation_service: TranslationService = Depends(get_translation_service)
):
    return await compat_handlers.translate_get_compat(
        request, translation_service, target_lang, text, source_lang, beam_size, perform_sentence_splitting
    )


@app.post(
    "/compat/translate",
    tags=["Compatibility"],
    summary="EasyNMT POST /translate (compat)",
)
async def compat_translate_post_endpoint(
    request: Request,
    body: TranslatePostBody,
    translation_service: TranslationService = Depends(get_translation_service)
):
    return await compat_handlers.translate_post_compat(request, body, translation_service)


@app.get(
    "/translate",
    tags=["Translation"],
    summary="Translate",
    description=(
        "Translates the text to the given target language.\n"
        ":param text: Text that should be translated\n"
        ":param target_lang: Target language\n"
        ":param source_lang: Language of text. Optional, if empty: Automatic language detection\n"
        ":param beam_size: Beam size. Optional\n"
        ":param perform_sentence_splitting: Split longer documents into individual sentences for translation. Optional\n"
        ":return: Returns a json with the translated text"
    )
)
async def translate_get_endpoint(
    request: Request,
    target_lang: str = Query(...),
    text: List[str] = Query(default=[]),
    source_lang: str = Query(default=""),
    beam_size: int = Query(default=5),
    perform_sentence_splitting: bool = Query(default=True),
    translation_service: TranslationService = Depends(get_translation_service)
):
    """GET translation endpoint."""
    from src.api.routes.translation import translate_get
    return await translate_get(
        request, translation_service, target_lang, text, source_lang, beam_size, perform_sentence_splitting
    )


@app.post(
    "/translate",
    tags=["Translation"],
    summary="Translate Post",
    description="Post method for translation\n:return:"
)
async def translate_post_endpoint(
    request: Request,
    body: TranslatePostBody,
    translation_service: TranslationService = Depends(get_translation_service)
):
    """POST translation endpoint."""
    from src.api.routes.translation import translate_post
    return await translate_post(request, body, translation_service)


@app.get(
    "/language_detection",
    tags=["Language"],
    summary="Language Detection",
    description=(
        "Detects the language for the provided text\n"
        ":param text: A single text for which we want to know the language\n:return: The detected language"
    )
)
async def language_detection_get_endpoint(
    text: str = Query(...),
    frontend_executor: ThreadPoolExecutor = Depends(get_frontend_executor)
):
    """GET language detection endpoint."""
    from src.api.routes.language import language_detection_get
    return await language_detection_get(text, frontend_executor)


@app.post(
    "/language_detection",
    tags=["Language"],
    summary="Language Detection Post",
    description=(
        "Pass a json that has a 'text' key. The 'text' element can either be a string, a list of strings, or\n"
        "a dict.\n:return: Languages detected"
    )
)
async def language_detection_post_endpoint(
    body: LanguageDetectionPostBody,
    frontend_executor: ThreadPoolExecutor = Depends(get_frontend_executor)
):
    """POST language detection endpoint."""
    from src.api.routes.language import language_detection_post
    return await language_detection_post(body, frontend_executor)


# Global exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
