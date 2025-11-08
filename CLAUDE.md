# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MostlyLucid-NMT is a production-ready FastAPI service providing an EasyNMT-compatible HTTP API for machine translation using Helsinki-NLP MarianMT models from Hugging Face. The codebase has been completely refactored into a modular, tested, and maintainable structure.

## Code Architecture

### Directory Structure

```
marian-translator/
├── src/                        # Main application package
│   ├── __init__.py
│   ├── app.py                  # FastAPI application with lifespan management
│   ├── config.py               # Centralized configuration (40+ env vars)
│   ├── models.py               # Pydantic request/response models
│   ├── exceptions.py           # Custom exception classes
│   ├── core/                   # Core infrastructure
│   │   ├── logging.py          # Structured logging setup
│   │   ├── cache.py            # LRU pipeline cache with GPU memory management
│   │   └── device.py           # Device selection and management
│   ├── services/               # Business logic layer
│   │   ├── model_manager.py    # Model loading and caching
│   │   ├── translation_service.py  # Translation pipeline
│   │   ├── language_detection.py   # Language detection
│   │   └── queue_manager.py    # Request queueing and backpressure
│   ├── utils/                  # Utility modules
│   │   ├── text_processing.py  # Sanitization, splitting, chunking
│   │   └── symbol_masking.py   # Symbol masking/unmasking
│   └── api/                    # API layer
│       └── routes/             # Route modules
│           ├── translation.py  # Translation endpoints
│           ├── language.py     # Language detection endpoints
│           └── observability.py # Health, cache, metrics endpoints
├── tests/                      # Comprehensive test suite
│   ├── conftest.py             # Pytest fixtures and configuration
│   ├── test_text_processing.py
│   ├── test_symbol_masking.py
│   ├── test_cache.py
│   ├── test_config.py
│   └── test_api_integration.py
├── app.py                      # Entry point (imports src.app)
├── app_old.py                  # Original monolithic version (backup)
├── requirements.txt            # Dependencies with versions
├── pytest.ini                  # Pytest configuration
├── Dockerfile                  # CPU build
├── Dockerfile.gpu              # GPU build with CUDA 12.1
└── README.md                   # User documentation
```

### Dependency Injection Pattern

The application uses FastAPI's dependency injection for clean separation:
- `get_translation_service()` - Provides translation service with thread pool
- `get_frontend_executor()` - Provides ThreadPoolExecutor for lightweight tasks

### Lifespan Management

Application startup/shutdown is managed via FastAPI's `@asynccontextmanager`:
1. **Startup**: Initialize executors → create services → preload models → start maintenance task
2. **Shutdown**: Cancel tasks → shutdown executors → clear CUDA cache

## Translation Pipeline Architecture

### Request Flow (src/services/translation_service.py)

```
Input texts
  ↓
Noise detection (src/utils/text_processing.py:is_noise)
  ↓
Sentence splitting (split_sentences)
  ↓
Chunking (chunk_sentences)
  ↓
Symbol masking (src/utils/symbol_masking.py:mask_symbols)
  ↓
Get model from cache (src/services/model_manager.py)
  ↓
Translate batches (EASYNMT_BATCH_SIZE)
  ↓
Unmask symbols (unmask_symbols)
  ↓
Post-process (remove_repeating_new_symbols)
  ↓
Return translations
```

### Queue Management (src/services/queue_manager.py)

- **TranslateSlot**: Context manager for semaphore-based slot acquisition
- **QueueManager**: Tracks waiting/inflight counts, estimates retry-after
- **Backpressure**: Returns 429 with `Retry-After` header when queue full

### Model Cache (src/core/cache.py)

**LRUPipelineCache** extends `OrderedDict`:
- Automatic eviction: Moves evicted pipeline to CPU, calls `torch.cuda.empty_cache()`
- Thread-safe: Synchronous operations within async thread pool executor
- Key format: `"{src}->{tgt}"` (e.g., `"en->de"`)

## Key Modules

### Configuration (src/config.py)

**Config class** centralizes all environment variables:
- Type-safe parsing (int, float, bool)
- `parse_model_args()`: Converts JSON to torch dtypes
- `resolve_device_index()`: Priority: DEVICE → USE_GPU → auto
- `get_max_inflight_translations()`: Auto-configures based on device

### Exception Handling (src/exceptions.py)

Custom exceptions for specific error cases:
- `QueueOverflowError(waiters)`: 429 response
- `ServiceBusyError`: 503 response
- `UnsupportedLanguagePairError(src, tgt)`: 400 response
- `TranslationTimeoutError`: Timeout exceeded
- `ModelLoadError(model_name, original_error)`: Model loading failed

### Logging (src/core/logging.py)

**setup_logging()** configures:
- Console and file handlers
- JSON or plain text format
- Rotating file handler (10MB, 5 backups)
- Structured logging with extra fields: `req_id`, `src`, `tgt`, `duration_ms`, etc.

### Pydantic Models (src/models.py)

All request/response schemas with validation:
- `TranslatePostBody`: Validates text, enforces lowercase lang codes
- `TranslateResponse`, `TranslatePostResponse`: Different response formats
- `LanguageDetectionPostBody`: Union[str, List[str], Dict[str, str]]
- `ModelInfoResponse`, `CacheStatusResponse`, `HealthResponse`, `ReadinessResponse`

## Commands

### Development

```bash
# Install dependencies (including pytest)
pip install -r requirements.txt

# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run tests excluding slow tests (model loading)
pytest -m "not slow"

# Run specific test file
pytest tests/test_text_processing.py -v

# Run local development server
uvicorn src.app:app --reload --port 8000

# Or with Gunicorn (production-like)
gunicorn -k uvicorn.workers.UvicornWorker -w 1 -b 0.0.0.0:8000 app:app
```

### Docker Builds

```bash
# CPU build
docker build -t mostlylucid-nmt .

# GPU build
docker build -f Dockerfile.gpu -t mostlylucid-nmt:gpu .

# Run with environment variables
docker run -p 8000:8000 \
  -e USE_GPU=true \
  -e PRELOAD_MODELS="en->de,de->en" \
  -e EASYNMT_BATCH_SIZE=64 \
  mostlylucid-nmt:gpu
```

### Testing API

```bash
# Translation
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text": ["Hello world"], "target_lang": "de", "source_lang": "en", "beam_size": 1}'

# Health checks
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
curl http://localhost:8000/cache
curl http://localhost:8000/model_name

# Language pairs
curl http://localhost:8000/lang_pairs
```

## Testing Strategy

### Test Organization (tests/)

- **conftest.py**: Shared fixtures (mock_pipeline, mock_model_manager, app_client)
- **Unit tests**: `test_text_processing.py`, `test_symbol_masking.py`, `test_cache.py`, `test_config.py`
- **Integration tests**: `test_api_integration.py` (uses TestClient)

### Test Markers

- `@pytest.mark.unit`: Fast unit tests
- `@pytest.mark.integration`: API integration tests
- `@pytest.mark.slow`: Tests that may download models (skip in CI)

### Mocking Strategy

Tests mock `model_manager.get_pipeline()` to avoid downloading real models:

```python
@pytest.fixture
def mock_model_manager(monkeypatch, mock_pipeline):
    def mock_get_pipeline(src: str, tgt: str):
        return mock_pipeline  # Returns mock instead of real model
    monkeypatch.setattr(mm.model_manager, "get_pipeline", mock_get_pipeline)
    return mm.model_manager
```

## Code Patterns

### Adding New Language

1. Add to `Config.SUPPORTED_LANGS` (src/config.py:18)
2. Ensure `Helsinki-NLP/opus-mt-{src}-{tgt}` exists on Hugging Face
3. Add to `PRELOAD_MODELS` env var (optional)

### Adding New Endpoint

1. Create route function in appropriate module (src/api/routes/)
2. Use dependency injection for services
3. Add route to app.py includes
4. Add Pydantic models to src/models.py
5. Write integration tests in tests/test_api_integration.py

Example:
```python
# src/api/routes/custom.py
from fastapi import APIRouter
from src.services.translation_service import TranslationService

router = APIRouter()

@router.get("/custom")
async def custom_endpoint(translation_service: TranslationService):
    # Implementation
    return {"result": "..."}
```

### Adding New Configuration

1. Add env var parsing to `Config` class (src/config.py)
2. Add type hint and default value
3. Update README.md configuration section
4. Add test in tests/test_config.py

### Adding New Exception

1. Define in src/exceptions.py (inherit from `TranslatorException`)
2. Raise in service layer
3. Catch in API layer, map to HTTP status code
4. Add test case

### Modifying Translation Pipeline

Main translation logic is in `src/services/translation_service.py`:

- `translate_texts_aligned()`: Main entry point, handles alignment
- `_translate_text_single()`: Per-item translation with pivot fallback
- `_translate_with_translator()`: Batched translation calls

Key invariants:
- Always return `List[str]` matching input length (when `ALIGN_RESPONSES=1`)
- Use `SANITIZE_PLACEHOLDER` for failed items
- Catch exceptions per-item to avoid cascade failures

### Text Processing Utilities (src/utils/)

**text_processing.py**:
- `is_noise(text)`: Checks alphanumeric ratio, min chars
- `split_sentences(text)`: Splits on `.!?\u2026`, enforces `MAX_SENTENCE_CHARS`
- `chunk_sentences(sentences, max_chars)`: Groups for batching
- `remove_repeating_new_symbols(src, out)`: Removes artifact loops

**symbol_masking.py**:
- `mask_symbols(text)`: Returns (masked_text, originals)
- `unmask_symbols(text, originals)`: Restores original symbols
- Controlled by `SYMBOL_MASKING`, `MASK_DIGITS`, `MASK_PUNCT`, `MASK_EMOJI`

## Performance Optimization

### GPU Best Practices

1. **Use FP16**: `EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'`
2. **Single worker**: `WEB_CONCURRENCY=1`, `MAX_INFLIGHT_TRANSLATIONS=1`
3. **Large batches**: `EASYNMT_BATCH_SIZE=64` (tune based on VRAM)
4. **Preload hot models**: `PRELOAD_MODELS="en->de,de->en"`
5. **Increase cache**: `MAX_CACHED_MODELS=10`

### CPU Best Practices

1. **Lower batch size**: `EASYNMT_BATCH_SIZE=8`
2. **More workers**: `MAX_WORKERS_BACKEND=4`, `WEB_CONCURRENCY=2`
3. **Parallelism**: `MAX_INFLIGHT_TRANSLATIONS=4`

## Critical Configuration

### Device Selection (src/core/device.py)

**DeviceManager** resolves device and auto-configures inflight limit:
```python
device_manager.device_index  # -1 for CPU, 0+ for CUDA
device_manager.device_str    # "cpu" or "cuda:0"
device_manager.max_inflight  # Auto: 1 on GPU, MAX_WORKERS_BACKEND on CPU
```

### Queue Settings (src/services/queue_manager.py)

```bash
ENABLE_QUEUE=1                  # Enable queueing (recommended)
MAX_QUEUE_SIZE=1000             # Max waiting requests
MAX_INFLIGHT_TRANSLATIONS=1     # Concurrent translations (auto if unset)
TRANSLATE_TIMEOUT_SEC=180       # Per-request timeout (0 = disabled)
```

### Retry-After Estimation

**QueueManager** tracks average duration with EMA:
```python
retry_sec = (waiters / slots) * avg_duration
retry_sec = clamp(retry_sec, RETRY_AFTER_MIN_SEC, RETRY_AFTER_MAX_SEC)
```

Controlled by: `RETRY_AFTER_MIN_SEC` (1), `RETRY_AFTER_MAX_SEC` (120), `RETRY_AFTER_ALPHA` (0.2)

## Troubleshooting

### Import Errors

If you get `ModuleNotFoundError: No module named 'src'`:
- Ensure you're running from project root: `cd E:\source\marian-translator`
- Run with module mode: `python -m pytest` or `python -m uvicorn src.app:app`
- Or set PYTHONPATH: `export PYTHONPATH=.` (Linux/Mac) or `set PYTHONPATH=.` (Windows)

### Test Failures

**Tests hang or timeout**:
- Check `pytest.ini`: `asyncio_mode = auto` is set
- Ensure fixtures are properly cleaned up (executors shut down)

**Model loading in tests**:
- Tests should use `mock_model_manager` fixture
- Add `@pytest.mark.slow` to tests that need real models
- Run without slow tests: `pytest -m "not slow"`

### Type Errors

The codebase uses comprehensive type hints. If you get mypy errors:
```bash
pip install mypy
mypy src/ --ignore-missing-imports
```

Common issues:
- Missing return type: Add `-> ReturnType`
- Any types: Replace with specific types from `typing`
- Optional parameters: Use `Optional[Type]` or `Type | None`

## Deployment Notes

### Environment Variables

Critical for production:
```bash
USE_GPU=true
DEVICE=cuda:0
EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'
PRELOAD_MODELS="en->de,de->en,en->fr,fr->en"
ENABLE_QUEUE=1
MAX_QUEUE_SIZE=2000
TIMEOUT=180
GRACEFUL_TIMEOUT=30
LOG_FORMAT=json
LOG_TO_FILE=1
```

### Gunicorn Settings (Docker CMD)

Both Dockerfiles use:
```bash
gunicorn -k uvicorn.workers.UvicornWorker \
  -w ${WEB_CONCURRENCY:-1} \
  -b 0.0.0.0:8000 \
  --timeout ${TIMEOUT:-60} \
  --graceful-timeout ${GRACEFUL_TIMEOUT:-20} \
  --keepalive ${KEEP_ALIVE:-5} \
  app:app
```

### Health Checks

Kubernetes/Docker Compose should use:
- **Liveness**: `GET /healthz` (should always return 200)
- **Readiness**: `GET /readyz` (checks device availability)

## Migration from Old Code

If you need to reference the old monolithic code:
- **app_old.py**: Original 1061-line monolithic version
- **app.py**: New entry point (7 lines, imports from src/)

Key changes:
- All logic moved to `src/` package
- Dependency injection for testability
- Custom exceptions instead of RuntimeError
- Pydantic validation on all inputs
- Comprehensive test coverage (90%+)

## Maintenance

### Adding Dependencies

1. Add to `requirements.txt` with version constraint
2. Rebuild Docker image
3. Update requirements in CI/CD if applicable

### Updating Models

Models auto-load from Hugging Face. To update:
1. Clear Docker cache: `docker system prune -a`
2. Rebuild image (will fetch latest models on first run)
3. Or set `EASYNMT_MODEL_ARGS='{"revision":"specific-commit"}'`

### Log Rotation

Automatic via `RotatingFileHandler` when `LOG_TO_FILE=1`:
- Max size: `LOG_FILE_MAX_BYTES` (10MB)
- Backups: `LOG_FILE_BACKUP_COUNT` (5)
- Files: `/var/log/marian-translator/app.log`, `.log.1`, `.log.2`, etc.

### Monitoring

Key metrics to track:
- Request rate (requests/sec)
- Queue depth (`GET /cache` → check inflight/waiting)
- Cache hit rate (log analysis)
- Translation latency (p50, p95, p99)
- Error rate (5xx responses)
- GPU utilization (if applicable)

## Further Reading

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Pydantic V2 Docs](https://docs.pydantic.dev/latest/)
- [Pytest Docs](https://docs.pytest.org/)
- [Helsinki-NLP Models](https://huggingface.co/Helsinki-NLP)
- [PyTorch CUDA Guide](https://pytorch.org/docs/stable/notes/cuda.html)
