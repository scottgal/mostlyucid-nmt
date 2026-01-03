"""Main FastAPI application with dependency injection."""

# CRITICAL: Import torch first to avoid circular import issues in frozen executables
# This must happen before any other imports that might trigger torch loading
try:
    import torch
    import torch.nn
except ImportError:
    pass  # torch not required for all operations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

# Import CUDA helpers from cache module (torch is optional)
from src.core.cache import _cuda_available, _clear_cuda_cache

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
    """Periodic maintenance: CUDA cache clearing, idle model eviction, and chunk cache TTL sweep."""
    # Determine minimum interval from configured values
    cuda_interval = config.CUDA_CACHE_CLEAR_INTERVAL_SEC
    idle_interval = config.IDLE_CHECK_INTERVAL
    chunk_cache_interval = config.CHUNK_CACHE_CLEANUP_INTERVAL

    # Check if any maintenance is needed
    maintenance_needed = (
        cuda_interval > 0 or
        config.MODEL_IDLE_TIMEOUT > 0 or
        (config.CHUNK_CACHE_ENABLED and config.CHUNK_CACHE_MAX_AGE > 0)
    )

    if not maintenance_needed:
        logger.info("Maintenance task disabled (no periodic tasks configured)")
        return

    # Calculate intervals
    intervals = []
    if cuda_interval > 0:
        intervals.append(cuda_interval)
    if config.MODEL_IDLE_TIMEOUT > 0:
        intervals.append(idle_interval)
    if config.CHUNK_CACHE_ENABLED and config.CHUNK_CACHE_MAX_AGE > 0:
        intervals.append(chunk_cache_interval)

    interval = min(intervals) if intervals else 60

    logger.info(f"Maintenance task started (interval: {interval}s, CUDA clearing: {cuda_interval > 0}, idle eviction: {config.MODEL_IDLE_TIMEOUT}s, chunk cache TTL: {config.CHUNK_CACHE_MAX_AGE}s)")

    cuda_counter = 0
    idle_counter = 0
    chunk_cache_counter = 0

    while True:
        try:
            cuda_counter += interval
            idle_counter += interval
            chunk_cache_counter += interval

            # CUDA cache clearing
            if cuda_interval > 0 and cuda_counter >= cuda_interval:
                if _cuda_available():
                    _clear_cuda_cache()
                    if config.REQUEST_LOG:
                        logger.debug("maintenance: CUDA cache cleared")
                cuda_counter = 0

            # Idle model eviction
            if config.MODEL_IDLE_TIMEOUT > 0 and idle_counter >= idle_interval:
                try:
                    evicted = model_manager.cache.evict_idle_models(config.MODEL_IDLE_TIMEOUT)
                    if evicted and config.REQUEST_LOG:
                        logger.info(f"maintenance: evicted {len(evicted)} idle models")
                except Exception as e:
                    logger.warning(f"maintenance: idle eviction error: {e}")
                idle_counter = 0

            # Chunk cache TTL sweep
            if config.CHUNK_CACHE_ENABLED and config.CHUNK_CACHE_MAX_AGE > 0 and chunk_cache_counter >= chunk_cache_interval:
                try:
                    from src.core.chunk_cache import get_chunk_cache
                    chunk_cache = get_chunk_cache()
                    if chunk_cache:
                        evicted = chunk_cache.evict_expired()
                        if evicted and config.REQUEST_LOG:
                            logger.debug(f"maintenance: chunk cache TTL sweep evicted {evicted} entries")
                except Exception as e:
                    logger.warning(f"maintenance: chunk cache TTL sweep error: {e}")
                chunk_cache_counter = 0

        except Exception as e:
            logger.warning(f"maintenance error: {e}")

        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    global _backend_executor, _frontend_executor, _translation_service, _maintenance_task_handle

    # Startup
    logger.info("Starting up translation service...")

    try:
        # CRITICAL: Force-import torch and transformers BEFORE creating thread pools
        # In frozen executables, these imports must happen in the main thread first
        try:
            import torch
            import torch.nn
            from transformers import AutoTokenizer
            logger.info("[Lifespan] Pre-loaded torch and transformers for thread safety")
        except ImportError as e:
            logger.warning(f"[Lifespan] Could not pre-load torch/transformers: {e}")

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
        if config.MODEL_IDLE_TIMEOUT > 0:
            logger.info(f"⏰ Idle model eviction enabled: {config.MODEL_IDLE_TIMEOUT}s timeout (check every {config.IDLE_CHECK_INTERVAL}s)")
        else:
            logger.info(f"⏰ Idle model eviction disabled (MODEL_IDLE_TIMEOUT=0)")

        # Log chunk cache configuration
        if config.CHUNK_CACHE_ENABLED:
            logger.info(f"📦 Chunk cache enabled: capacity={config.CHUNK_CACHE_CAPACITY}, TTL={config.CHUNK_CACHE_MAX_AGE}s")
        else:
            logger.info(f"📦 Chunk cache disabled (CHUNK_CACHE_ENABLED=0)")

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
    if _cuda_available():
        try:
            _clear_cuda_cache()
        except Exception:
            pass

    logger.info("Translation service stopped")


# Create FastAPI app
app = FastAPI(
    title=config.TITLE,
    version=config.VERSION,
    lifespan=lifespan
)

# Mount static demo at /demo (only if public directory exists)
import os
if os.path.isdir("public"):
    app.mount("/demo", StaticFiles(directory="public", html=True), name="demo")

    # Redirect root to /demo when demo is available
    @app.get(
        "/",
        summary="Root Redirect",
        description="Redirects to the interactive demo UI"
    )
    async def root_redirect():
        """Redirect root to demo UI."""
        return RedirectResponse(url="/demo/")
else:
    # Standalone exe: redirect to API docs
    @app.get(
        "/",
        summary="Root Redirect",
        description="Redirects to API documentation"
    )
    async def root_redirect():
        """Redirect root to API docs."""
        return RedirectResponse(url="/docs")


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
