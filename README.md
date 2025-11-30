# mostlylucid-nmt (EasyNMT-compatible API)

[![Docker Pulls](https://img.shields.io/docker/pulls/scottgal/mostlylucid-nmt)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)
[![latest](https://img.shields.io/docker/v/scottgal/mostlylucid-nmt/latest?label=latest)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)
[![cpu](https://img.shields.io/docker/v/scottgal/mostlylucid-nmt/cpu?label=cpu)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)
[![gpu](https://img.shields.io/docker/v/scottgal/mostlylucid-nmt/gpu?label=gpu)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)

**[Complete Guide & Tutorial](https://www.mostlylucid.net/blog/mostlylucid-nmt-complete-guide)** - Comprehensive walkthrough with examples

A production-ready FastAPI service providing an EasyNMT-compatible HTTP API for machine translation.

**Supported Model Families:**
- **Opus-MT** (Helsinki-NLP): 1200+ translation pairs for 150+ languages, best quality
- **mBART50** (Facebook): All-to-all translation for 50 languages, single model
- **M2M100** (Facebook): All-to-all translation for 100 languages, broadest coverage

**Key Features:**
- EasyNMT-compatible endpoints: `/translate` (GET/POST), `/lang_pairs`, `/language_detection`, `/model_name`
- Auto-chunking for texts of any size
- CPU and GPU support with on-demand model loading and LRU cache
- Volume-mapped model caching for persistence
- Backpressure and queuing with smart `Retry-After` estimation
- Intelligent memory management to prevent OOM crashes
- Automatic fallback across model families
- Pivot translation with intelligent path selection
- **Markdown sanitization** to prevent parser depth errors (v3.4+)
- Symbol masking to protect special characters during translation
- Swagger UI at `/docs` and ReDoc at `/redoc`

---

## Common Gotchas

**IMPORTANT - Read this first to avoid common mistakes:**

### 1. GPU Not Being Used
**Problem:** Container runs on CPU despite setting `USE_GPU=true`

**Solution:** You MUST use `--gpus all` flag:
```bash
# WRONG - ignores USE_GPU
docker run -p 8000:8000 -e USE_GPU=true scottgal/mostlylucid-nmt:gpu

# CORRECT - enables GPU access
docker run --gpus all -p 8000:8000 -e USE_GPU=true scottgal/mostlylucid-nmt:gpu
```

**Why:** Docker requires explicit GPU access via `--gpus` flag. The `USE_GPU` env var only tells the application to prefer GPU; without `--gpus all`, no GPU devices are visible to the container.

**Verify GPU is working:** Check startup logs for:
```
Using GPU: NVIDIA RTX A4000 (cuda:0)
```

### 2. Models Not Persisting Across Restarts
**Problem:** Container downloads models every time it restarts

**Solution:** You MUST map a volume AND set `MODEL_CACHE_DIR`:
```bash
# WRONG - models disappear on restart
docker run -p 8000:8000 scottgal/mostlylucid-nmt:cpu

# CORRECT - models persist
docker run -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_CACHE_DIR=/models \
  scottgal/mostlylucid-nmt:cpu
```

**Why:** Without a volume, models are stored inside the container and deleted when it stops. The minimal images (`:cpu` and `:gpu`) have no preloaded models by design.

### 3. Wrong Docker Tag
**Problem:** Using old tag names from v2.x

**Current tags (v3.4+):**
- `:latest` - CPU image (alias for `:cpu`)
- `:cpu` - CPU, no preloaded models
- `:gpu` - GPU with CUDA 12.6, no preloaded models
- `:cpu-3.4.0` - Pinned version (semantic versioning)
- `:gpu-3.4.0` - Pinned GPU version

**Old tags removed:**
- `:cpu-min`, `:gpu-min` - Replaced by `:cpu` and `:gpu`
- `:cpu-full`, `:gpu-full` - Dropped (too large, 4-7GB)

### 4. Cache Directory Confusion
**Problem:** Setting `HF_HOME` or `TORCH_HOME` instead of `MODEL_CACHE_DIR`

**Correct approach:**
```bash
# Use MODEL_CACHE_DIR (recommended)
-e MODEL_CACHE_DIR=/models
-v ./model-cache:/models

# Do NOT set these (they're automatically derived from MODEL_CACHE_DIR):
# -e HF_HOME=/models
# -e TORCH_HOME=/models
```

**Why:** The application manages cache paths internally. Setting `MODEL_CACHE_DIR` configures all caching locations correctly.

### 5. Forgetting Auto-Fallback is ON by Default
**Behavior:** Even if you set `MODEL_FAMILY=opus-mt`, the service will use mBART50/M2M100 for pairs not available in Opus-MT.

**This is intentional** - maximizes coverage while prioritizing quality.

**To disable:**
```bash
-e AUTO_MODEL_FALLBACK=0
```

**To change priority:**
```bash
-e MODEL_FALLBACK_ORDER="mbart50,m2m100,opus-mt"  # Try mBART50 first
```

### 6. Memory Issues on GPU
**Problem:** Out of memory crashes after several translations

**Solutions:**
- **Use FP16:** `-e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'`
- **Reduce cache:** `-e MAX_CACHED_MODELS=3` (default: 10)
- **Lower batch size:** `-e EASYNMT_BATCH_SIZE=32` (default: 64 for GPU)
- **Enable memory monitoring (default ON):** `-e ENABLE_MEMORY_MONITOR=1`

The service auto-evicts cached models when memory reaches 90% (configurable via `MEMORY_CRITICAL_THRESHOLD`).

### 7. Single Worker for GPU
**Problem:** Multiple Gunicorn workers cause CUDA errors

**Solution:** GPU images use `WEB_CONCURRENCY=1` by default. Do NOT change this for single-GPU setups:
```bash
# WRONG - causes CUDA conflicts
docker run --gpus all -e WEB_CONCURRENCY=4 scottgal/mostlylucid-nmt:gpu

# CORRECT - single worker per GPU
docker run --gpus all scottgal/mostlylucid-nmt:gpu
```

**Why:** Each worker would try to load models onto the same GPU, causing memory conflicts. Use `MAX_INFLIGHT_TRANSLATIONS` to control concurrency instead.

---

## Quick Start

### Using Pre-built Images (Recommended)

**CPU:**
```bash
# Basic run (downloads models on-demand)
docker run -p 8000:8000 scottgal/mostlylucid-nmt

# With persistent cache (recommended)
docker run -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_CACHE_DIR=/models \
  scottgal/mostlylucid-nmt:cpu
```

**GPU (requires NVIDIA Container Toolkit):**
```bash
# Basic run with GPU
docker run --gpus all -p 8000:8000 \
  -e USE_GPU=true \
  scottgal/mostlylucid-nmt:gpu

# Production config with cache and FP16
docker run --gpus all -p 8000:8000 \
  -v ./model-cache:/models \
  -e USE_GPU=true \
  -e MODEL_CACHE_DIR=/models \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  -e PRELOAD_MODELS="en->de,de->en" \
  scottgal/mostlylucid-nmt:gpu
```

**Access the API:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/healthz

---

## Model Families

Switch between model families using `MODEL_FAMILY` environment variable:

| Family | Languages | Pairs | Model Type | Quality | Size |
|--------|-----------|-------|------------|---------|------|
| **opus-mt** | 150+ | 1200+ | Separate per direction | Best | ~300MB each |
| **mbart50** | 50 | 2,450 | Single multilingual | Good | ~2.4GB |
| **m2m100** | 100 | 9,900 | Single multilingual | Good | ~2.2GB |

**Examples:**

```bash
# Opus-MT (default, best quality)
docker run -p 8000:8000 \
  -e MODEL_FAMILY=opus-mt \
  scottgal/mostlylucid-nmt:cpu

# mBART50 (50 languages, single model)
docker run -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_FAMILY=mbart50 \
  -e MODEL_CACHE_DIR=/models \
  scottgal/mostlylucid-nmt:cpu

# M2M100 (100 languages, broadest coverage)
docker run -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_FAMILY=m2m100 \
  -e MODEL_CACHE_DIR=/models \
  scottgal/mostlylucid-nmt:cpu
```

**Auto-fallback** (enabled by default):
- Request opus-mt for a pair that doesn't exist
- Automatically tries mbart50, then m2m100
- Maximizes coverage while prioritizing quality
- Configure with `MODEL_FALLBACK_ORDER="opus-mt,mbart50,m2m100"`

---

## API Endpoints

Full API documentation at `/docs` (Swagger UI).

### Translation

**POST /translate:**
```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{
    "text": ["Hello world", "This is a test"],
    "target_lang": "de",
    "source_lang": "en",
    "beam_size": 1
  }'
```

**Response:**
```json
{
  "target_lang": "de",
  "source_lang": "en",
  "translated": ["Hallo Welt", "Das ist ein Test"],
  "translation_time": 0.15
}
```

**Auto-chunking** (enabled by default):
- Texts of any size are automatically split into safe chunks
- Processed independently and reassembled
- Configure: `AUTO_CHUNK_ENABLED=1`, `AUTO_CHUNK_MAX_CHARS=5000`

**Translation metadata** (optional):
```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -H 'X-Enable-Metadata: 1' \
  -d '{"text": "Hello", "target_lang": "de", "source_lang": "en"}'
```

Returns model name, family, languages used, chunks processed, etc.

### Other Endpoints

- `GET /lang_pairs` - All supported language pairs
- `GET /get_languages` - All supported languages
- `POST /language_detection` - Detect language of input text
- `GET /model_name` - Model and device info
- `GET /discover/opus-mt` - Discover all Opus-MT pairs (cached 1 hour)
- `GET /discover/mbart50` - All mBART50 pairs
- `GET /discover/m2m100` - All M2M100 pairs
- `GET /discover/all` - All families in parallel
- `GET /healthz` - Health check
- `GET /readyz` - Readiness check
- `GET /cache` - Cache status and queue info

---

## Configuration

Key environment variables (defaults in parentheses):

### Device & Model
- `USE_GPU=true|false|auto` (`auto`) - Prefer GPU if available
- `DEVICE=auto|cpu|cuda|cuda:0` (`auto`) - Explicit device override
- `MODEL_FAMILY=opus-mt|mbart50|m2m100` (`opus-mt`) - Model family
- `AUTO_MODEL_FALLBACK=1|0` (`1`) - Auto-fallback to other families
- `MODEL_FALLBACK_ORDER="opus-mt,mbart50,m2m100"` - Fallback priority
- `MODEL_CACHE_DIR=/models` (unset) - Cache directory for volume mapping
- `MAX_CACHED_MODELS=10` (`10`) - LRU cache capacity

### Performance
- `EASYNMT_BATCH_SIZE=16` (`16` CPU, `64` GPU) - Batch size
- `EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'` (`{}`) - Model args (FP16 for GPU)
- `PRELOAD_MODELS="en->de,de->en"` - Preload at startup
- `WEB_CONCURRENCY=1` (unset, `1` for GPU) - Gunicorn workers
- `MAX_WORKERS_BACKEND=1` (`1`) - Translation thread pool
- `MAX_INFLIGHT_TRANSLATIONS=1` (auto: `1` GPU, `4` CPU) - Concurrent translations

### Memory Management
- `ENABLE_MEMORY_MONITOR=1` (`1`) - Auto-evict on high memory
- `MEMORY_CRITICAL_THRESHOLD=90.0` (`90.0`) - Auto-evict at 90% RAM
- `GPU_MEMORY_CRITICAL_THRESHOLD=90.0` (`90.0`) - Auto-evict at 90% VRAM

### Queueing & Timeouts
- `ENABLE_QUEUE=1` (`1`) - Enable request queueing
- `MAX_QUEUE_SIZE=1000` (`1000`) - Max waiting requests
- `TIMEOUT=120` (`120`) - Gunicorn worker timeout
- `GRACEFUL_TIMEOUT=20` (`20`) - Graceful shutdown timeout

### Logging
Default logging is minimal (errors, model loading, startup). Increase verbosity for debugging:

```bash
# Default: minimal logging
-e LOG_LEVEL=INFO

# Verbose: all translation details, masking, sanitization
-e LOG_LEVEL=DEBUG

# Enable file logging (rotates at 10MB, keeps 5 backups)
-e LOG_TO_FILE=1
-e LOG_FILE_PATH=/var/log/nmt/app.log

# JSON format for log aggregation (ELK, Datadog, etc.)
-e LOG_FORMAT=json

# Include translated text in logs (privacy risk - off by default)
-e LOG_INCLUDE_TEXT=1
```

**Log levels:** `DEBUG` < `INFO` < `WARNING` < `ERROR`

### Markdown Sanitization (v3.4+)
Prevents Markdig/parser "depth limit exceeded" errors from translated markdown. Only processes content detected as markdown (plain text passes through unchanged).

- `MARKDOWN_SANITIZE=1` (`1`) - Enable sanitization of translated markdown
- `MARKDOWN_SAFE_MODE=0` (`0`) - Force strip complex markdown (links, images)
- `MARKDOWN_SAFE_MODE_AUTO=1` (`1`) - Auto-enable safe mode for RTL targets (Arabic, Hebrew, etc.)
- `MARKDOWN_MAX_DEPTH=10` (`10`) - Maximum bracket nesting depth
- `MARKDOWN_PROBLEMATIC_PAIRS=""` - Force safe mode for specific pairs (e.g., `en->ar,en->he`)

**What it fixes:**
- Unbalanced brackets `[]` and parentheses `()`
- RTL bracket direction issues (common in Arabic/Hebrew translations)
- Deeply nested structures that exceed parser limits
- Unbalanced emphasis markers (`**`, `*`, `__`, `_`)

**Logs:** Sanitization events logged at `WARNING` level (visible by default)

For full configuration reference, see inline comments in source or `/model_name` endpoint output.

---

## Performance Tuning

**GPU Recommendations:**
```bash
docker run --gpus all -p 8000:8000 \
  -e USE_GPU=true \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  -e EASYNMT_BATCH_SIZE=64 \
  -e WEB_CONCURRENCY=1 \
  -e MAX_INFLIGHT_TRANSLATIONS=1 \
  -e MAX_CACHED_MODELS=10 \
  scottgal/mostlylucid-nmt:gpu
```

**CPU Recommendations:**
```bash
docker run -p 8000:8000 \
  -e EASYNMT_BATCH_SIZE=8 \
  -e WEB_CONCURRENCY=2 \
  -e MAX_WORKERS_BACKEND=4 \
  -e MAX_INFLIGHT_TRANSLATIONS=4 \
  scottgal/mostlylucid-nmt:cpu
```

**General tips:**
1. Use FP16 on GPU: `EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'`
2. Keep beam_size low (1-2) for throughput
3. Group inputs by language pair and send large batches
4. Preload hot pairs: `PRELOAD_MODELS="en->de,de->en"`
5. Use volume-mapped cache to avoid redownloading

---

## Building from Source

**Quick build all variants:**
```bash
# Windows PowerShell
.\build-all.ps1

# Linux/Mac
chmod +x build-all.sh
./build-all.sh
```

**Manual builds:**
```bash
# CPU
docker build -f Dockerfile.min -t scottgal/mostlylucid-nmt:cpu .

# GPU
docker build -f Dockerfile.gpu.min -t scottgal/mostlylucid-nmt:gpu .
```

**Versioning:**
- Named tags: `:latest`, `:cpu`, `:gpu`
- Version tags: `:cpu-3.4.0`, `:gpu-3.4.0` (semantic versioning)

For detailed build instructions and CI/CD integration, see [BUILD.md](BUILD.md).

---

## Troubleshooting

**429 Too Many Requests:**
- Queue exceeded `MAX_QUEUE_SIZE`
- Read `Retry-After` header and retry later
- Consider increasing `MAX_QUEUE_SIZE`

**503 Service Busy:**
- All translation slots occupied
- Enable queueing: `ENABLE_QUEUE=1`

**GPU not used (container shows CPU):**
- Ensure `--gpus all` flag is present
- Check: `docker run --gpus all --rm nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi`

**Models download every restart:**
- Map volume: `-v ./model-cache:/models`
- Set: `-e MODEL_CACHE_DIR=/models`

**Out of memory on GPU:**
- Use FP16: `-e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'`
- Reduce cache: `-e MAX_CACHED_MODELS=3`
- Lower batch size: `-e EASYNMT_BATCH_SIZE=32`

**Missing language pair:**
- Use `/discover/opus-mt` to check available pairs
- Enable auto-fallback (default ON): `AUTO_MODEL_FALLBACK=1`
- Try different model family: `MODEL_FAMILY=mbart50`
- Enable pivot: `PIVOT_FALLBACK=1` (default ON)

**Long texts fail:**
- Auto-chunking is enabled by default
- Adjust: `AUTO_CHUNK_MAX_CHARS=5000`
- Lower beam_size: `beam_size=1`

---

## License

MIT

---

## EasyNMT Compatibility

For strict EasyNMT response shapes, use `/compat` endpoints:

```bash
# GET (EasyNMT format)
curl "http://localhost:8000/compat/translate?target_lang=de&text=Hello&source_lang=en"
# => { "translations": ["Hallo"] }

# POST (EasyNMT format)
curl -X POST http://localhost:8000/compat/translate \
  -H 'Content-Type: application/json' \
  -d '{"text": ["Hello"], "target_lang": "de", "source_lang": "en"}'
# => { "target_lang": "de", "source_lang": "en", "translated": ["Hallo"], "translation_time": 0.1 }
```

Standard `/translate` endpoints include optional extras (pivot_path, metadata, etc.).
