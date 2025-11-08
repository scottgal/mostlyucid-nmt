# Marian Translator (EasyNMT-compatible API)

[![Docker Pulls](https://img.shields.io/docker/pulls/scottgal/mostlylucid-nmt)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)
[![cpu](https://img.shields.io/docker/v/scottgal/mostlylucid-nmt/cpu?label=cpu)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)
[![cpu-min](https://img.shields.io/docker/v/scottgal/mostlylucid-nmt/cpu-min?label=cpu-min)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)
[![gpu](https://img.shields.io/docker/v/scottgal/mostlylucid-nmt/gpu?label=gpu)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)
[![gpu-min](https://img.shields.io/docker/v/scottgal/mostlylucid-nmt/gpu-min?label=gpu-min)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)

📖 **[Complete Guide & Tutorial](https://www.mostlylucid.net/blog/mostlylucid-nmt-complete-guide)** - Comprehensive walkthrough with examples and best practices

A FastAPI service that provides an EasyNMT-like HTTP API for machine translation supporting multiple model families:
- **Opus-MT** (Helsinki-NLP): 1200+ translation pairs for 150+ languages
- **mBART50** (Facebook): All-to-all translation for 50 languages
- **M2M100** (Facebook): All-to-all translation for 100 languages

Features:
- Compatible endpoints with EasyNMT: `/translate` (GET/POST), `/lang_pairs`, `/get_languages`, `/language_detection` (GET/POST), `/model_name`
- New discovery endpoints to find available models dynamically
- Swagger UI available at `/docs` (also at `/` via redirect) and ReDoc at `/redoc`
- CPU and GPU support (CUDA), with on-demand model loading and LRU in-memory cache
- Minimal Docker images with volume-mapped model caching
- Backpressure and queuing on by default; smart `Retry-After` on overload
- Robust input handling, sentence splitting, and optional pivot translation
- Structured logging with optional file rotation for long-running stability


## 🚀 Latest Updates - v2.0

### 1. Multiple Model Families - BIGGEST UPDATE!
**Switch between three powerful translation model families:**

| Family | Languages | Pairs | Model Type | Quality | Use Case |
|--------|-----------|-------|------------|---------|----------|
| **Opus-MT** | 150+ | 1200+ | Separate per direction | ⭐⭐⭐⭐⭐ Best | High-quality production |
| **mBART50** | 50 | 2,450 | Single multilingual | ⭐⭐⭐⭐ Good | Space-constrained, many pairs |
| **M2M100** | 100 | 9,900 | Single multilingual | ⭐⭐⭐⭐ Good | Maximum language coverage |

**Switch via environment variable:**
```bash
MODEL_FAMILY=opus-mt   # Default, best quality
MODEL_FAMILY=mbart50   # 50 languages, single model
MODEL_FAMILY=m2m100    # 100 languages, broadest coverage
```

### 2. Automatic Model Family Fallback - NEW!
**Intelligently selects the best available model for any translation:**

- Primary family tries first (e.g., Opus-MT for quality)
- Automatically falls back to mBART50 or M2M100 if pair not available
- **Maximum coverage without sacrificing quality!**
- Configurable priority order

```bash
# Enable auto-fallback (default: ON)
AUTO_MODEL_FALLBACK=1
MODEL_FALLBACK_ORDER="opus-mt,mbart50,m2m100"
```

**Example:** Request Ukrainian→French:
1. Try Opus-MT (not available)
2. Auto-fallback to mBART50 ✓ (succeeds!)
3. Translation completes with best available model

### 3. Model Discovery Endpoints - NEW!
**Dynamically discover available models from Hugging Face:**

- `GET /discover/opus-mt` - All 1200+ Opus-MT pairs (cached 1 hour)
- `GET /discover/mbart50` - All 2,450 mBART50 pairs
- `GET /discover/m2m100` - All 9,900 M2M100 pairs
- `GET /discover/all` - All families in parallel
- `POST /discover/clear-cache` - Clear discovery cache

### 4. Minimal Docker Images - NEW!
**Smaller images with volume-mapped model caching:**

| Tag | Full Image Name | Size | Description | Use Case |
|-----|-----------------|------|-------------|----------|
| `cpu` (or `latest`) | `scottgal/mostlylucid-nmt:cpu` | ~2.5GB | CPU with source code | Production CPU deployments |
| `cpu-min` | `scottgal/mostlylucid-nmt:cpu-min` | ~1.5GB | CPU minimal, no preloaded models | Volume-mapped cache, flexible |
| `gpu` | `scottgal/mostlylucid-nmt:gpu` | ~5GB | GPU with CUDA 12.6 + source | Production GPU deployments |
| `gpu-min` | `scottgal/mostlylucid-nmt:gpu-min` | ~4GB | GPU minimal, no preloaded models | GPU with volume-mapped cache |

**Benefits:**
- ✅ Smaller image sizes
- ✅ Models persist across container restarts (volume mapping)
- ✅ Switch model families without rebuilding
- ✅ Shared cache between containers

### 5. All Images in One Repository!
**Single Docker Hub repository with multiple tags:**

```bash
# All from: scottgal/mostlylucid-nmt
docker pull scottgal/mostlylucid-nmt:cpu       # CPU full (also available as :latest)
docker pull scottgal/mostlylucid-nmt:cpu-min   # CPU minimal
docker pull scottgal/mostlylucid-nmt:gpu       # GPU full
docker pull scottgal/mostlylucid-nmt:gpu-min   # GPU minimal
```

### 6. Volume-Mapped Model Cache - NEW!
**Persistent model storage across containers:**

```bash
# Linux/Mac
docker run -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_CACHE_DIR=/models \
  scottgal/mostlylucid-nmt:cpu-min

# Windows PowerShell
docker run -p 8000:8000 `
  -v ${HOME}/model-cache:/models `
  -e MODEL_CACHE_DIR=/models `
  scottgal/mostlylucid-nmt:cpu-min

# Windows CMD
docker run -p 8000:8000 ^
  -v %USERPROFILE%/model-cache:/models ^
  -e MODEL_CACHE_DIR=/models ^
  scottgal/mostlylucid-nmt:cpu-min
```

### 7. Updated Base Images - SECURITY!
**Latest and most secure base images:**

- **Python 3.13-slim** for CPU images (latest stable Python)
- **CUDA 12.6** with Ubuntu 24.04 for GPU images
- **PyTorch with CUDA 12.4** support (compatible with CUDA 12.6 runtime)
- Addresses all known vulnerabilities in previous Python 3.11 and CUDA 12.1 images

---

## Table of Contents
- [Quick Start](#quick-start)
  - [Using Pre-built Images (Docker Hub)](#using-pre-built-images-docker-hub)
  - [CPU (Build from Source)](#cpu-build-from-source)
  - [GPU (Build from Source)](#gpu-build-from-source)
  - [Minimal Images (with volume-mapped cache)](#minimal-images-with-volume-mapped-cache)
- [API](#api)
  - [`/translate` GET](#translate-get)
  - [`/translate` POST](#translate-post)
  - [`/lang_pairs`](#lang_pairs)
  - [`/get_languages`](#get_languages)
  - [`/language_detection` GET/POST](#language_detection)
  - [`/model_name`](#model_name)
  - [Model Discovery](#model-discovery)
  - [Health/Observability](#healthobservability)
- [Building from Source](#building-from-source)
  - [Quick Build](#quick-build)
  - [Versioning Strategy](#versioning-strategy)
  - [Publishing](#publishing)
- [Configuration (Environment Variables)](#configuration-environment-variables)
  - [Device Selection](#device-selection)
  - [Model & Cache](#model--cache)
  - [Preloading](#preloading)
  - [EasyNMT Options](#easynmt-options)
  - [Queueing / Backpressure / Timeouts](#queueing--backpressure--timeouts)
  - [Retry-After Estimation](#retry-after-estimation)
  - [Input Sanitization](#input-sanitization)
  - [Response Alignment & Sentence Splitting](#response-alignment--sentence-splitting)
  - [Pivot Fallback](#pivot-fallback)
  - [Logging](#logging)
  - [Maintenance](#maintenance)
- [Performance Tuning](#performance-tuning)
- [Client Tips](#client-tips)
- [Graceful Shutdown](#graceful-shutdown)
- [Troubleshooting](#troubleshooting)
- [License](#license)


## Quick Start

### Using Pre-built Images (Docker Hub)

The easiest way to get started is using pre-built images from Docker Hub.

#### CPU (Docker Hub)
```bash
# Pull and run
docker run -p 8000:8000 \
  -e MODEL_FAMILY=opus-mt \
  -e ENABLE_QUEUE=1 \
  scottgal/mostlylucid-nmt

# Or use mBART50 with volume-mapped cache
docker run -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_FAMILY=mbart50 \
  -e MODEL_CACHE_DIR=/models \
  scottgal/mostlylucid-nmt:cpu-min
```

#### GPU (Docker Hub)
Requires NVIDIA Container Toolkit.

```bash
# Pull and run with Opus-MT
docker run --gpus all -p 8000:8000 \
  -e USE_GPU=true \
  -e PRELOAD_MODELS="en->de,de->en" \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  scottgal/mostlylucid-nmt:gpu

# Or use M2M100 with volume-mapped cache
docker run --gpus all -p 8000:8000 \
  -v ./model-cache:/models \
  -e USE_GPU=true \
  -e MODEL_FAMILY=m2m100 \
  -e MODEL_CACHE_DIR=/models \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  scottgal/mostlylucid-nmt:gpu-min
```

Open the docs at: http://localhost:8000/

---

### CPU (Build from Source)
Build and run the CPU image:

```bash
# Build
docker build -t mostlylucid-nmt .

# Run (example prod-ish defaults)
docker run -p 8000:8000 \
  -e ENABLE_QUEUE=1 -e MAX_QUEUE_SIZE=500 \
  -e EASYNMT_BATCH_SIZE=16 \
  -e TIMEOUT=180 \
  mostlylucid-nmt
```

Open the docs at: http://localhost:8000/


### GPU (Build from Source)
Requires NVIDIA Container Toolkit.

```bash
# Build
docker build -f Dockerfile.gpu -t mostlylucid-nmt:gpu .

# Run (typical high-throughput, safe defaults)
docker run --gpus all -p 8000:8000 \
  -e USE_GPU=true -e DEVICE=cuda:0 \
  -e PRELOAD_MODELS="en->de,de->en" \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  -e ENABLE_QUEUE=1 -e MAX_QUEUE_SIZE=1000 \
  -e WEB_CONCURRENCY=1 -e TIMEOUT=180 \
  mostlylucid-nmt:gpu
```

Open the docs at: http://localhost:8000/


### Minimal Images (with volume-mapped cache)

Minimal images don't preload any models but download them on-demand and cache to a volume-mapped directory. This keeps container size small and allows model persistence across container restarts.

#### CPU Minimal
```bash
# Build
docker build -f Dockerfile.min -t scottgal/mostlylucid-nmt:cpu-min .

# Run with volume mapping for model cache
docker run -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_FAMILY=opus-mt \
  -e MODEL_CACHE_DIR=/models \
  scottgal/mostlylucid-nmt:cpu-min
```

#### GPU Minimal
```bash
# Build
docker build -f Dockerfile.gpu.min -t mostlylucid-nmt:gpu-min .

# Run with volume mapping and GPU
docker run --gpus all -p 8000:8000 \
  -v ./model-cache:/models \
  -e USE_GPU=true \
  -e MODEL_FAMILY=mbart50 \
  -e MODEL_CACHE_DIR=/models \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  scottgal/mostlylucid-nmt:gpu-min
```

Benefits:
- **Smaller images**: No preloaded models embedded in image
- **Flexible model selection**: Switch model families without rebuilding
- **Persistent cache**: Models persist across container restarts
- **On-demand loading**: Models download automatically when first requested

---

### Model Family Examples

#### Opus-MT (1200+ pairs, best quality)
```bash
# CPU with pre-built image
docker run -p 8000:8000 \
  -e MODEL_FAMILY=opus-mt \
  scottgal/mostlylucid-nmt

# GPU with pre-built image
docker run --gpus all -p 8000:8000 \
  -e USE_GPU=true \
  -e MODEL_FAMILY=opus-mt \
  -e PRELOAD_MODELS="en->de,de->en,fr->en" \
  scottgal/mostlylucid-nmt:gpu
```

#### mBART50 (50 languages, single model)
```bash
# Minimal image with volume cache (recommended)
docker run -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_FAMILY=mbart50 \
  -e MODEL_CACHE_DIR=/models \
  scottgal/mostlylucid-nmt:cpu-min

# GPU with FP16
docker run --gpus all -p 8000:8000 \
  -v ./model-cache:/models \
  -e USE_GPU=true \
  -e MODEL_FAMILY=mbart50 \
  -e MODEL_CACHE_DIR=/models \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  scottgal/mostlylucid-nmt:gpu-min
```

#### M2M100 (100 languages, broadest coverage)
```bash
# Minimal image with volume cache (recommended)
docker run -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_FAMILY=m2m100 \
  -e MODEL_CACHE_DIR=/models \
  scottgal/mostlylucid-nmt:cpu-min

# GPU with FP16
docker run --gpus all -p 8000:8000 \
  -v ./model-cache:/models \
  -e USE_GPU=true \
  -e MODEL_FAMILY=m2m100 \
  -e MODEL_CACHE_DIR=/models \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  scottgal/mostlylucid-nmt:gpu-min
```

**Tip:** Use minimal images (`-min` tag) with volume-mapped cache for mBART50/M2M100 since they're single large models. This avoids embedding them in the image and allows sharing across containers.


## API
The API matches EasyNMT routes and shapes where applicable. Swagger UI is available at `/docs`.

### `/translate` GET
Translates texts passed as repeated `text=` query params.

Query params:
- `target_lang` (string, required)
- `text` (string[], optional; repeat param multiple times)
- `source_lang` (string, optional; empty for auto-detect)
- `beam_size` (int, optional; default `5`, clamped by `EASYNMT_MAX_BEAM_SIZE` if set)
- `perform_sentence_splitting` (bool, optional; default true)

Response (default mode):
```json
{ "translations": ["..."] }
```

### `/translate` POST
Body:
```json
{
  "text": ["Hello world", "This is a test"],
  "target_lang": "de",
  "source_lang": "en",
  "beam_size": 1,
  "perform_sentence_splitting": true
}
```

Note: `text` can also be a single string.

Response: same as GET.

Notes:
- On success, `translations` length always equals the number of input items, with non-null strings (placeholder on per-item failure).
- On overload, server returns 429/503 with `Retry-After` header and JSON `{ "retry_after_sec": N }`.

### `/lang_pairs`
Returns all supported source/target pairs built from the `SUPPORTED_LANGS` set.

```json
{ "language_pairs": [["en", "de"], ["de", "en"]] }
```

### `/get_languages`
Optionally filter by `source_lang` or `target_lang`.

```json
{ "languages": ["en", "de"] }
```

### `/language_detection`
- GET: `?text=...` → `{ "language": "en" }`
- POST: body `{"text": "..." | ["..."] | {"id":"text", ...}}`
  - Returns `{ "language": ... }`, `{ "languages": [...] }`, or a map of detections.

### `/model_name`
Returns model/device info and key runtime configuration snapshot.

```json
{
  "model_name": "Helsinki-NLP/opus-mt (dynamic)",
  "device": "cpu|cuda:N",
  "easynmt_model": "opus-mt",
  "batch_size": 16,
  "max_text_len": null,
  "max_beam_size": null,
  "workers": {"backend": 1, "frontend": 2},
  "align_responses": true,
  "pivot_fallback": true,
  "logging": {
    "log_level": "INFO",
    "log_to_file": false,
    "log_file_path": null,
    "log_format": "plain",
    "request_log": false,
    "log_include_text": false
  }
}
```

### Model Discovery

Endpoints to discover available translation models dynamically.

#### `/discover/opus-mt`
Discovers all available Opus-MT language pairs from Hugging Face. Results are cached for 1 hour.

Query params:
- `force_refresh` (bool, optional): Bypass cache and fetch fresh data

Response:
```json
{
  "model_family": "opus-mt",
  "language_pairs": [["en", "de"], ["de", "en"], ...],
  "pair_count": 1234
}
```

#### `/discover/mbart50`
Returns all available mBART50 language pairs (all-to-all for 50 languages).

Response:
```json
{
  "model_family": "mbart50",
  "language_pairs": [["en", "de"], ["de", "en"], ...],
  "pair_count": 2450
}
```

#### `/discover/m2m100`
Returns all available M2M100 language pairs (all-to-all for 100 languages).

Response:
```json
{
  "model_family": "m2m100",
  "language_pairs": [["en", "de"], ["de", "en"], ...],
  "pair_count": 9900
}
```

#### `/discover/all`
Discovers all available language pairs for all model families.

Query params:
- `force_refresh` (bool, optional): Force refresh Opus-MT from HuggingFace

Response:
```json
{
  "models": {
    "opus-mt": {"language_pairs": [...], "pair_count": 1234},
    "mbart50": {"language_pairs": [...], "pair_count": 2450},
    "m2m100": {"language_pairs": [...], "pair_count": 9900}
  }
}
```

#### `POST /discover/clear-cache`
Clears the model discovery cache.

Response:
```json
{"status": "ok", "message": "Discovery cache cleared"}
```

### Health/Observability
- `GET /healthz` → `{ "status": "ok" }`
- `GET /readyz` → readiness with device and queue settings
- `GET /cache` → LRU cache status (capacity/size/keys/device) and queue configuration


## Building from Source

All 4 Docker image variants include proper versioning and OCI labels for tracking.

### Quick Build

**Windows PowerShell:**
```powershell
.\build-all.ps1
```

**Linux/Mac:**
```bash
chmod +x build-all.sh
./build-all.sh
```

This builds all 4 variants with automatic datetime versioning (format: `YYYYMMDD.HHMMSS`).

### Versioning Strategy

Each build creates **two tags** per variant:
- **Named tag**: `latest`, `min`, `gpu`, `gpu-min` (always latest)
- **Version tag**: Immutable snapshot (e.g., `20250108.143022` or `min-20250108.143022`)

Example:
```bash
# Always get latest CPU full image
docker pull scottgal/mostlylucid-nmt:cpu
# Or use the :latest alias
docker pull scottgal/mostlylucid-nmt:latest

# Pin to specific version
docker pull scottgal/mostlylucid-nmt:cpu-20250108.143022
```

### Publishing

After building, push to Docker Hub:
```bash
docker push scottgal/mostlylucid-nmt --all-tags
```

For detailed build instructions, versioning strategy, and CI/CD integration, see **[BUILD.md](BUILD.md)**.


## Configuration (Environment Variables)
Defaults are shown in parentheses.

### Device Selection
- `USE_GPU` = `true|false|auto` (`auto`) — prefer GPU if available.
- `DEVICE` = `auto|cpu|cuda|cuda:0` (`auto`) — explicit device overrides `USE_GPU`.

### Model & Cache
- `MODEL_FAMILY` = `opus-mt|mbart50|m2m100` (`opus-mt`) — selects which model family to use for translation.
  - `opus-mt`: Helsinki-NLP MarianMT models (1200+ pairs, separate model per direction)
  - `mbart50`: Facebook mBART-50 (50 languages, all-to-all, single multilingual model)
  - `m2m100`: Facebook M2M-100 (100 languages, all-to-all, single multilingual model)
- `AUTO_MODEL_FALLBACK` = `1|0` (`1`) — automatically try other model families if pair not available in primary family. Maximizes coverage while prioritizing quality.
- `MODEL_FALLBACK_ORDER` = string (`opus-mt,mbart50,m2m100`) — comma-separated priority order for auto-fallback. First available family wins.
- `MODEL_CACHE_DIR` = path (unset) — directory to cache downloaded models (useful with Docker volumes).
- `EASYNMT_MODEL` = `opus-mt` (`opus-mt`) — legacy compatibility, prefer `MODEL_FAMILY`.
- `EASYNMT_MODEL_ARGS` = JSON string (`{}`) — forwarded to `transformers.pipeline` (allowed keys: `revision`, `trust_remote_code`, `cache_dir`, `use_fast`, `torch_dtype` where `"fp16"|"bf16"|"fp32"`). If `MODEL_CACHE_DIR` is set, `cache_dir` is automatically added.
- `MAX_CACHED_MODELS` = int (`6`) — LRU capacity of in-memory pipelines. Eviction frees VRAM when on GPU.

**Auto-fallback example:** If `MODEL_FAMILY=opus-mt` but you request Ukrainian→French (not available in Opus-MT), the system automatically tries mBART50 or M2M100 based on `MODEL_FALLBACK_ORDER`. This ensures maximum language pair coverage while prioritizing quality.

### Preloading
- `PRELOAD_MODELS` = `"en->de,de->en,fr->en"` — preloads pipelines at startup; invalid or missing repos are ignored.

### EasyNMT Options
- `MAX_WORKERS_BACKEND` = int (`1`) — translation thread pool workers.
- `MAX_WORKERS_FRONTEND` = int (`2`) — language detection/meta workers.
- `EASYNMT_MAX_TEXT_LEN` = int (unset) — max text length per item; also caps generation `max_length`.
- `EASYNMT_MAX_BEAM_SIZE` = int (unset) — upper bound for requested `beam_size`.
- `EASYNMT_BATCH_SIZE` = int (`16`) — batch size for pipeline calls.
- `EASYNMT_RESPONSE_MODE` = `strings|objects` (`strings`) — shape of `translations`.

### Queueing / Backpressure / Timeouts
- `ENABLE_QUEUE` = `1|0` (`1`) — enable request queueing/backpressure.
- `MAX_INFLIGHT_TRANSLATIONS` = int (auto) — concurrent translations; default `1` on GPU, else `MAX_WORKERS_BACKEND` on CPU.
- `MAX_QUEUE_SIZE` = int (`1000`) — max enqueued requests; overflow returns 429 with `Retry-After`.
- `TRANSLATE_TIMEOUT_SEC` = int (`0`) — per-request translation timeout (0 disables).
- Gunicorn: `TIMEOUT` = int (`120`) — worker timeout for requests; set via Docker `CMD`.
- Gunicorn workers: `WEB_CONCURRENCY` (unset) — use `1` on single GPU to avoid VRAM contention.

### Retry-After Estimation
- `RETRY_AFTER_MIN_SEC` = float (`1`) — lower bound for estimate.
- `RETRY_AFTER_MAX_SEC` = int (`120`) — upper bound for estimate.
- `RETRY_AFTER_ALPHA` = float (`0.2`) — EMA smoothing factor for average translate duration.

### Input Sanitization
- `INPUT_SANITIZE` = `1|0` (`1`) — enables filtering of noise (emoji-only, control chars, punctuation-only, etc.).
- `INPUT_MIN_ALNUM_RATIO` = float (`0.2`) — minimal alphanumeric ratio among non-space chars.
- `INPUT_MIN_CHARS` = int (`1`) — minimal length after stripping control chars.
- `UNDETERMINED_LANG_CODE` = string (`und`) — returned by detection when input is noise.

### Response Alignment & Sentence Splitting
- `ALIGN_RESPONSES` = `1|0` (`1`) — return aligned `translations` array of the same length; per-item failures use placeholder.
- `SANITIZE_PLACEHOLDER` = string (`""`) — placeholder for skipped/failed items.
- `PERFORM_SENTENCE_SPLITTING_DEFAULT` = `1|0` (`1`) — default behavior if request does not specify.
- `MAX_SENTENCE_CHARS` = int (`500`) — max chars per sentence before further splitting.
- `MAX_CHUNK_CHARS` = int (`900`) — re-chunk sentences to this size for translation.
- `JOIN_SENTENCES_WITH` = string (`" "`) — glue used when recombining translated chunks.

### Pivot Fallback
- `PIVOT_FALLBACK` = `1|0` (`1`) — enable two-hop translation via pivot if direct model fails.
- `PIVOT_LANG` = string (`en`) — pivot language.

### Logging
- `LOG_LEVEL` = `DEBUG|INFO|WARN|ERROR` (`INFO`)
- `REQUEST_LOG` = `1|0` (`0`) — per-request logs.
- `LOG_TO_FILE` = `1|0` (`0`) — enable rotating file logs.
- `LOG_FILE_PATH` = path (`/var/log/marian-translator/app.log`)
- `LOG_FILE_MAX_BYTES` = int (`10485760`) — 10MB.
- `LOG_FILE_BACKUP_COUNT` = int (`5`)
- `LOG_FORMAT` = `plain|json` (`plain`)
- `LOG_INCLUDE_TEXT` = `1|0` (`0`) — include raw texts in logs (off by default for privacy).

### Maintenance
- `CUDA_CACHE_CLEAR_INTERVAL_SEC` = int (`0`) — periodically call `torch.cuda.empty_cache()`; `0` disables.


## Performance Tuning
Order of impact:
1. Enable GPU, use half precision if supported:
   - `USE_GPU=true`, `DEVICE=cuda:0`, `EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'`
2. Batch size (`EASYNMT_BATCH_SIZE`): start 32–64 on GPU; 8–16 on CPU, tune carefully.
3. Keep `beam_size` low (1–2) for throughput.
4. Group inputs by language pair and send large arrays via POST.
5. Preload hot pairs via `PRELOAD_MODELS` to avoid first-request latency.
6. Keep `WEB_CONCURRENCY=1` and `MAX_INFLIGHT_TRANSLATIONS=1` on single GPU; scale horizontally for more throughput.
7. Use backpressure defaults (`ENABLE_QUEUE=1`, large `MAX_QUEUE_SIZE`).


## Client Tips
- Use a single long-lived HTTP client with keep-alive. Respect 429/503 `Retry-After` and retry with jitter backoff.
- Only parse `translations` on HTTP 200. Expect `translations.Length == input.Length` and no null elements.
- Prefer POST with a large `text` array per language pair.

Example `curl` (POST):
```bash
curl -s -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{
        "text": ["Hello world", "This is fast"],
        "target_lang": "de",
        "source_lang": "en",
        "beam_size": 1,
        "perform_sentence_splitting": true
      }'
```

Other useful endpoints:
```bash
curl -s http://localhost:8000/model_name | jq
curl -s http://localhost:8000/cache | jq
curl -s http://localhost:8000/readyz | jq
curl -s http://localhost:8000/lang_pairs | jq
```


## Graceful Shutdown
Fast, graceful termination is enabled by default in both CPU and GPU images.

What happens on shutdown:
- Docker sends SIGTERM to PID 1 (Gunicorn) thanks to `STOPSIGNAL SIGTERM`.
- Gunicorn stops accepting new connections, waits up to `GRACEFUL_TIMEOUT` seconds for in‑flight requests to finish, then forcefully kills workers if they don’t exit.
- The FastAPI app’s shutdown hook cancels background maintenance and shuts down internal thread pools. On GPU, CUDA cache is cleared.

Key runtime knobs (env vars):
- `GRACEFUL_TIMEOUT` (default `20`): Gunicorn graceful period in seconds before sending SIGKILL to workers.
- `TIMEOUT` (default `60`): Max time a worker can spend handling a single request.
- `KEEP_ALIVE` (default `5`): HTTP keep‑alive timeout for idle connections.
- `WEB_CONCURRENCY` (unset by default): Number of Gunicorn workers. Use `1` for single‑GPU deployments.

Quick test locally:
```bash
# Start the service
docker run --rm --name mt -p 8000:8000 mostlylucid-nmt

# In another shell, start a long request (simulate with a large text or big batch)
# Then ask Docker to stop the container and observe logs for a quick, clean exit.
docker stop mt
```

Notes:
- If clients hold long‑lived idle HTTP connections, the short `KEEP_ALIVE` helps close them quickly on shutdown.
- For extremely long translations, consider lowering `TIMEOUT` and/or guiding clients to send smaller batches and respect `Retry-After`.

## Troubleshooting
- 429 Too Many Requests:
  - The queue exceeded `MAX_QUEUE_SIZE`. Read `Retry-After` header or JSON `retry_after_sec` and retry later. Consider increasing `MAX_QUEUE_SIZE`.
- 503 Busy:
  - Queueing disabled or all slots occupied. Respect `Retry-After`; consider enabling queueing (`ENABLE_QUEUE=1`).
- Missing language pair:
  - **Opus-MT**: The service dynamically loads `Helsinki-NLP/opus-mt-{src}-{tgt}`. Use `/discover/opus-mt` to see all available pairs. If a direct pair doesn't exist, pivot fallback (`PIVOT_FALLBACK=1`) may help.
  - **mBART50/M2M100**: These support all-to-all translation for their language sets. Check supported languages via `/get_languages`.
- Model family selection:
  - Use `MODEL_FAMILY` env var to switch between `opus-mt`, `mbart50`, or `m2m100`. Each has different language support and model sizes.
  - Discovery endpoints (`/discover/*`) help identify which pairs are available for each family.
- Long texts fail:
  - Sentence splitting and chunking are enabled by default; adjust `MAX_SENTENCE_CHARS` / `MAX_CHUNK_CHARS` or lower `beam_size`.
- Model caching with Docker volumes:
  - Set `MODEL_CACHE_DIR=/models` and mount a volume: `-v ./model-cache:/models`
  - Models persist across container restarts and are shared if multiple containers use the same volume.
- Logs and persistence:
  - Enable file logs with rotation (`LOG_TO_FILE=1`). Mount a volume at `/var/log/marian-translator` if you need persistence.
- `sacremoses` warning:
  - The image includes `sacremoses`; the app also suppresses the warning. If you build custom images, ensure `sacremoses` is installed.


## License
MIT or as specified by your repository. Replace this section with your actual license terms.
