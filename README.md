# mostlylucid-nmt (EasyNMT-compatible API)

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
- **Auto-chunking**: Automatically handles texts of any size - no client-side splitting needed!
- **Translation metadata**: Optional detailed info about model, languages, chunking, and timing
- Swagger UI available at `/docs` (also at `/` via redirect) and ReDoc at `/redoc`
- CPU and GPU support (CUDA), with on-demand model loading and LRU in-memory cache
- Minimal Docker images with volume-mapped model caching
- Backpressure and queuing on by default; smart `Retry-After` on overload
- Robust input handling, sentence splitting, and optional pivot translation
- Structured logging with optional file rotation for long-running stability


## 🚀 Latest Updates - v3.1

### Major Reliability & User Experience Enhancements

Version 3.1 focuses on **bulletproof reliability** and **transparency** - making the service "always recover gracefully" with clear visibility into what's happening.

#### 1. Smart Model Caching with Visibility 💾
**Keep multiple models loaded for instant switching!**

- **Increased default cache**: Now keeps up to **10 models** loaded in memory (GPU/CPU) for instant switching without reload wait
- **Enhanced visibility**: Clear logging with emoji indicators showing cache hits (✓), misses (✗), and evictions (⚠️)
- **Smart eviction**: Automatically frees GPU memory when cache is full
- **Zero reload time**: Switch between language pairs instantly when models are cached

```bash
# Configure cache size (default: 10 models)
MAX_CACHED_MODELS=10
```

**Example logs:**
```
💾 Model cache configured: MAX_CACHED_MODELS=10
   Keeps up to 10 models loaded for instant switching (no reload wait)
   Oldest models auto-evicted when cache full
✓ Cache HIT: Reusing loaded model for en->de (5/10 models in cache)
✗ Cache MISS: Need to load model for fr->de (5/10 models in cache)
💾 Cached model: fr->de (6/10 models in cache)
⚠️  Cache FULL! Evicting oldest model: en->es (to make room for de->fr)
```

#### 2. Enhanced Download Progress with Size Information 🚀
**Know exactly what's downloading and how long it'll take!**

Before v3.1, long model downloads (3+ minutes) looked like the service had hung. Now you get:

- **Pre-download size estimation**: Queries HuggingFace API to show total download size BEFORE starting
- **Beautiful download banners**: Shows model name, family, direction, device, total size, and file count
- **Completion confirmation**: Clear banner when download finishes
- **Device visibility**: Always shows whether using CPU or GPU

**Example output:**
```
====================================================================================================
  🚀 DOWNLOADING MODEL
  Model: Helsinki-NLP/opus-mt-en-bn
  Family: opus-mt
  Direction: en → bn
  Device: GPU (cuda:0)
  Total Size: 298.5 MB
  Files: 8 main files
====================================================================================================
Fetching 8 files: 100%|████████████████████████████████████| 8/8 [03:12<00:00, 24.1s/it]
====================================================================================================
  ✅ DOWNLOAD COMPLETE
  Model: Helsinki-NLP/opus-mt-en-bn (en → bn)
====================================================================================================
```

#### 3. Data-Driven Intelligent Pivot Selection 🎯
**No more blind pivot attempts that fail!**

Previously, pivot translation would try arbitrary intermediary languages (e.g., en→es→bn) even when the second leg (es→bn) didn't exist, wasting time and causing errors.

**Now uses mathematical set intersection:**
- Finds all languages reachable FROM source (src→X exists)
- Finds all languages that can reach target (X→tgt exists)
- Computes intersection: languages where BOTH legs exist
- Selects best pivot from valid candidates using priority order

**Example:** For English→Bengali:
```
Before (v3.0):
  Trying pivot: en → es → bn
  Loading Helsinki-NLP/opus-mt-es-bn... FAILED (model doesn't exist)
  Trying pivot: en → fr → bn
  Loading Helsinki-NLP/opus-mt-fr-bn... FAILED (model doesn't exist)

After (v3.1):
  Checking which languages work for BOTH en→X AND X→bn...
  Found valid pivots: {hi, mr, ta, te} (Indian languages with both legs)
  Selected pivot: hi (highest priority Indian language)
  Loading Helsinki-NLP/opus-mt-en-hi... SUCCESS
  Loading Helsinki-NLP/opus-mt-hi-bn... SUCCESS
  Translation via en → hi → bn completed!
```

**Configuration:**
```bash
PIVOT_FALLBACK=1               # Enable intelligent pivot (default: ON)
PIVOT_LANG=en                  # Preferred pivot language
MODEL_FALLBACK_ORDER="opus-mt,mbart50,m2m100"  # Priority order
```

#### 4. Fixed Automatic Fallback - No More Double-Tries! 🔧
**Critical fix: Stop retrying the same model twice**

Previously, when requesting a specific model family (e.g., opus-mt) for a pair that didn't exist, the service would:
1. Try the requested family
2. Retry the SAME family again (wasting time)
3. Never try fallback families even with AUTO_MODEL_FALLBACK enabled

**Now fixed:**
- Always adds fallback families when `AUTO_MODEL_FALLBACK=1` (even if preferred family "should" work)
- Each family is tried only ONCE
- Automatic fallback works reliably

**Example:** Request opus-mt for English→Bengali (doesn't exist in Opus-MT):
```
Before (v3.0):
  Trying families for en->bn: ['opus-mt']
  Loading Helsinki-NLP/opus-mt-en-bn... FAILED
  Loading Helsinki-NLP/opus-mt-en-bn... FAILED (trying again!)
  Translation failed

After (v3.1):
  Trying families for en->bn: ['opus-mt', 'mbart50', 'm2m100']
  Loading Helsinki-NLP/opus-mt-en-bn... FAILED
  Using fallback model family 'mbart50' for en->bn
  Loading facebook/mbart-large-50-many-to-many-mmt... SUCCESS
  Translation completed with mbart50!
```

**Configuration:**
```bash
AUTO_MODEL_FALLBACK=1                          # Enable auto-fallback (default: ON)
MODEL_FALLBACK_ORDER="opus-mt,mbart50,m2m100"  # Try opus-mt first, then mbart50, then m2m100
```

#### 5. GPU Device Clarity 🖥️
**Always know which device is being used!**

Added extensive device logging throughout the model loading pipeline to eliminate confusion:

- Device shown in download banners
- Device confirmed after model loads
- Device included in success messages
- Clear distinction between CPU, GPU (cuda:0), etc.

**Example logs:**
```
[ModelManager] Loading opus-mt model on GPU (cuda:0)
[ModelManager] Model loaded on device: cuda:0
Successfully loaded model: Helsinki-NLP/opus-mt-en-de (en->de) using family 'opus-mt' on GPU (cuda:0)
```

**For ALL model families** (Opus-MT, mBART50, M2M100) - GPU is used when enabled!

#### 6. Pivot Model Caching ♻️
**Both legs of pivot translation are cached!**

When using pivot translation (e.g., en→hi→bn), both intermediate models are cached separately:
- First leg (en→hi) cached for reuse
- Second leg (hi→bn) cached for reuse
- Future translations can reuse either leg independently

**Example:** After translating en→bn via hi pivot:
```
✓ Cache HIT: Reusing loaded model for en->hi (7/10 models in cache)
✓ Cache HIT: Reusing loaded model for hi->bn (7/10 models in cache)
```

Next translation using en→hi (different target) reuses the first leg instantly!

#### 7. Per-Request Model Selection 🎛️
**Client can specify model family per request!**

The demo UI and API support per-request model family selection:

```bash
# Request specific model family via query parameter or POST body
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{
    "text": ["Hello world"],
    "target_lang": "de",
    "source_lang": "en",
    "model_family": "mbart50"
  }'
```

**Benefits:**
- Test different model families without restarting service
- Use best model family for each language pair
- Compare translation quality across families
- Demo UI dropdown switches model family per translation

---

### Summary: v3.1 = Reliability + Transparency

**Out-of-the-box reliability:**
- ✅ No more double-tries or wasted model loads
- ✅ Intelligent pivot selection that only tries valid paths
- ✅ Automatic fallback across model families
- ✅ Graceful recovery from all failure modes

**Clear visibility:**
- ✅ Download progress with sizes and device info
- ✅ Cache status with emoji indicators
- ✅ Device placement always logged
- ✅ Pivot selection reasoning visible in logs

**Configuration:**
```bash
# Recommended v3.1 settings for maximum reliability
AUTO_MODEL_FALLBACK=1                          # ON by default
PIVOT_FALLBACK=1                               # ON by default
MAX_CACHED_MODELS=10                           # Increased from 6
MODEL_FALLBACK_ORDER="opus-mt,mbart50,m2m100"  # Quality-first fallback
```

---

## 🚀 Latest Updates - v3.0

### 1. EasyNMT Compatibility Namespace (/compat)
- New, dedicated endpoints that strictly match EasyNMT response shapes while keeping the enhanced primary API unchanged.
  - `GET /compat/translate` → `{ "translations": [...] }`
  - `POST /compat/translate` → `{ "target_lang", "source_lang", "detected_langs" (when auto), "translated", "translation_time" }`
- Existing `/translate` endpoints continue to support optional extras like `pivot_path` and `metadata`.

### 2. Preloaded Models in Prepack Images (cpu, gpu)
- CPU `:cpu` and GPU `:gpu` images now include a minimal, curated set of Opus‑MT models preloaded into the image to avoid first-request latency.
- Default preload set: `es, fr, de, it` as en<->XX (8 model repos total). Stored under `/app/models`.
- You can change the preloaded set at build time using `--build-arg PRELOAD_LANGS="es,fr,de,it"`.
  - Default is controlled by the Docker build arg `ARG PRELOAD_LANGS="es,fr,de,it"` (preloads EN<->ES/FR/DE/IT → 8 repos).
  - To customize at build time:
    ```bash
    # CPU prepack, preload EN<->(es,fr,de)
    docker build -t scottgal/mostlylucid-nmt:cpu \
      --build-arg PRELOAD_LANGS="es,fr,de" .

    # GPU prepack, preload EN<->(es,fr,de,it,nl)
    docker build -f Dockerfile.gpu -t scottgal/mostlylucid-nmt:gpu \
      --build-arg PRELOAD_LANGS="es,fr,de,it,nl" .
    ```
  - You can also specify explicit PAIRS to preload at build time (preferred for Opus‑MT since models are per-direction). The build uses pairs first when provided:
    ```bash
    # CPU prepack: preload exact pairs (and auto-pivot via English if a direct pair does not exist)
    docker build -t scottgal/mostlylucid-nmt:cpu \
      --build-arg PRELOAD_PAIRS="en->de,de->en,fr->en,en->it,ja->de" .

    # GPU prepack with pairs
    docker build -f Dockerfile.gpu -t scottgal/mostlylucid-nmt:gpu \
      --build-arg PRELOAD_PAIRS="en->de,en->fr,fr->en" .
    ```
    - Smart pivot: For Opus‑MT, if a non-English direct pair is missing (e.g., `ja->de`), the preloader will fetch `ja->en` and `en->de` as a fallback.
  - Minimal variants (`:cpu-min`, `:gpu-min`) preload nothing by design; they download on-demand unless you map a cache.

### 3. Cache Overlay Support (Prepack Images)
- You can map an external cache directory and it will work on top of the preloaded models.
  - Example:
    ```bash
    docker run -p 8000:8000 \
      -v ./model-cache:/models \
      -e MODEL_CACHE_DIR=/models \
      scottgal/mostlylucid-nmt:cpu
    ```
  - Behavior: preloaded models are used directly from `/app/models`; any new downloads are stored in `/models` (your mapped cache), so they persist between runs.

### 4. Minimal Images: Cache Mapping is Optional
- Minimal images (`:cpu-min`, `:gpu-min`) do not include preloaded models. Mapping a cache directory is recommended but optional:
  - Without mapping a cache, the image will download models on-demand on each run (no persistence).
  - With `-v ./model-cache:/models -e MODEL_CACHE_DIR=/models`, models persist between runs.

### 5. GPU Docker Fix
- Fixed `python: not found` during build preload step in `Dockerfile.gpu` by switching to `python3`.

---

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

### 7. Auto-Chunking - NEW!
**Throw text of ANY size at the API!**

- Automatically splits large texts into safe chunks
- Processes each chunk independently
- Reassembles results seamlessly
- **No client-side chunking needed!**

```bash
# Translate a 50,000 character document - automatically chunked!
AUTO_CHUNK_ENABLED=1           # Default: ON
AUTO_CHUNK_MAX_CHARS=5000      # Chars per chunk (default: 5000)
```

**How it works:** Input text > 5000 chars → auto-split → translate → reassemble → return as single translation!

### 8. Translation Metadata - NEW!
**Get detailed information about each translation:**

```bash
# Enable via header (per-request)
curl -H 'X-Enable-Metadata: 1' http://localhost:8000/translate ...

# Or globally
ENABLE_METADATA=1              # Include metadata in responses
METADATA_VIA_HEADERS=1         # Also add to HTTP headers
```

**Metadata includes:**
- Model name and family used
- Languages involved (including pivot if used)
- Number of chunks processed
- Whether auto-chunking was applied
- Chunk size configuration

**Perfect for:** monitoring, debugging, analytics, and understanding how your translations are processed!

### 9. Updated Base Images - SECURITY!
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

### Quick API Testing

Three test scripts are provided to verify all v3.1 features:

**Python script (comprehensive, color output):**
```bash
# Install requests if needed
pip install requests

# Run comprehensive test suite
python test_api_comprehensive.py
```

**Bash script (Linux/Mac):**
```bash
chmod +x test_api_quick.sh
./test_api_quick.sh
```

**Windows batch file:**
```cmd
test_api_quick.bat
```

These scripts test:
- ✅ Basic translation pairs (opus-mt)
- ✅ Automatic fallback scenarios (mbart50/m2m100)
- ✅ Explicit model family selection
- ✅ Pivot translation with intelligent selection
- ✅ Cache behavior across requests
- ✅ Batch translation
- ✅ Multiple model switching

**Check server logs during tests to see:**
- Download progress banners with sizes
- Cache HIT/MISS indicators (✓/✗/💾/⚠️)
- Model family fallback decisions
- Intelligent pivot selection reasoning
- GPU/CPU device placement

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

#### Auto-Chunking (NEW!)
**Automatically handles texts of any size!** No need to pre-chunk your input.

When enabled (default), the service automatically splits large texts into safe chunks, processes them, and reassembles the results.

**Configuration:**
```bash
AUTO_CHUNK_ENABLED=1           # Enable auto-chunking (default: ON)
AUTO_CHUNK_MAX_CHARS=5000      # Max chars per chunk (default: 5000)
```

**How it works:**
1. Input text > `AUTO_CHUNK_MAX_CHARS` → automatically split into chunks
2. Each chunk is translated independently
3. Results are reassembled and returned as a single translation
4. Works transparently - no client-side changes needed!

**Example:**
```bash
# Translate a 50,000 character document - no problem!
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Your very long text here... (50,000 chars)",
    "target_lang": "de",
    "source_lang": "en"
  }'
# Automatically chunked into 10 pieces, translated, and reassembled!
```

#### Translation Metadata (NEW!)
**Get detailed information about each translation!**

Enable metadata to receive additional information about model used, languages, chunking, and more.

**Enable via header (per-request):**
```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -H 'X-Enable-Metadata: 1' \
  -d '{"text": "Hello world", "target_lang": "de", "source_lang": "en"}'
```

**Or globally via config:**
```bash
ENABLE_METADATA=1              # Always include metadata (default: OFF)
METADATA_VIA_HEADERS=1         # Also add metadata to response headers (default: OFF)
```

**Response with metadata:**
```json
{
  "target_lang": "de",
  "source_lang": "en",
  "translated": ["Hallo Welt"],
  "translation_time": 0.15,
  "pivot_path": null,
  "metadata": {
    "model_name": "Helsinki-NLP/opus-mt-en-de",
    "model_family": "opus-mt",
    "languages_used": ["en", "de"],
    "chunks_processed": 1,
    "chunk_size": 5000,
    "auto_chunked": false
  }
}
```

**Metadata fields:**
- `model_name`: Actual model used for translation
- `model_family`: opus-mt, mbart50, or m2m100
- `languages_used`: All languages involved (includes pivot if used)
- `chunks_processed`: Number of chunks processed
- `chunk_size`: Max characters per chunk
- `auto_chunked`: Whether auto-chunking was applied

**Metadata in headers** (when `METADATA_VIA_HEADERS=1`):
```
X-Model-Name: Helsinki-NLP/opus-mt-en-de
X-Model-Family: opus-mt
X-Languages-Used: en,de
X-Chunks-Processed: 1
X-Auto-Chunked: false
```

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
```
{
  "model_family": "opus-mt",
  "language_pairs": [["en", "de"], ["de", "en"], ...],
  "pair_count": 1234
}
```

#### `/discover/mbart50`
Returns all available mBART50 language pairs (all-to-all for 50 languages).

Response:
```
{
  "model_family": "mbart50",
  "language_pairs": [["en", "de"], ["de", "en"], ...],
  "pair_count": 2450
}
```

#### `/discover/m2m100`
Returns all available M2M100 language pairs (all-to-all for 100 languages).

Response:
```
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
```
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
- `MAX_CACHED_MODELS` = int (`10`) — LRU capacity of in-memory pipelines. **v3.1: Increased from 6 to 10** for better instant switching between language pairs. Eviction frees VRAM when on GPU. Set higher to keep more models loaded, or lower if running out of memory.

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

### Auto-Chunking (NEW!)
- `AUTO_CHUNK_ENABLED` = `1|0` (`1`) — automatically split large texts into safe chunks before translation. Handles texts of any size!
- `AUTO_CHUNK_MAX_CHARS` = int (`5000`) — maximum characters per chunk. Texts exceeding this are automatically split, translated, and reassembled.

**Why auto-chunking?** Throws any text at the API without worrying about size limits. The service handles chunking automatically and reassembles results seamlessly.

### Translation Metadata (NEW!)
- `ENABLE_METADATA` = `1|0` (`0`) — include metadata in translation responses (model, languages, chunking info, etc.).
- `METADATA_VIA_HEADERS` = `1|0` (`0`) — also include metadata in response headers (X-Model-Name, X-Languages-Used, etc.).

**Metadata can also be enabled per-request** by adding the `X-Enable-Metadata: 1` header to your request.

**Metadata includes:** model name, model family, languages used (including pivot), chunks processed, chunk size, and whether auto-chunking was applied.

### Pivot Fallback
- `PIVOT_FALLBACK` = `1|0` (`1`) — enable two-hop translation via pivot if direct model fails.
- `PIVOT_LANG` = string (`en`) — pivot language.

### Logging
- `LOG_LEVEL` = `DEBUG|INFO|WARN|ERROR` (`INFO`)
- `REQUEST_LOG` = `1|0` (`0`) — per-request logs.
- `LOG_TO_FILE` = `1|0` (`0`) — enable rotating file logs.
- `LOG_FILE_PATH` = path (`/var/log/mostlylucid-nmt/app.log`)
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
  - Enable file logs with rotation (`LOG_TO_FILE=1`). Mount a volume at `/var/log/mostlylucid-nmt` if you need persistence.
- `sacremoses` warning:
  - The image includes `sacremoses`; the app also suppresses the warning. If you build custom images, ensure `sacremoses` is installed.


## License
MIT or as specified by your repository. Replace this section with your actual license terms.


---

### Compatibility namespace (/compat)

For clients that require strict EasyNMT response shapes, a dedicated compatibility namespace is available. These endpoints return exactly the EasyNMT field names without MostlyLucid-NMT extras.

Examples:

- GET (EasyNMT style)
```bash
curl "http://localhost:8000/compat/translate?target_lang=de&text=Hello%20world&source_lang=en"
# => { "translations": ["Hallo Welt"] }
```

- POST (EasyNMT style)
```bash
curl -X POST http://localhost:8000/compat/translate \
  -H 'Content-Type: application/json' \
  -d '{
    "text": ["Hello world"],
    "target_lang": "de",
    "source_lang": "en",
    "beam_size": 5,
    "perform_sentence_splitting": true
  }'
# => {
#   "target_lang": "de",
#   "source_lang": "en",
#   "translated": ["Hallo Welt"],
#   "translation_time": 0.12
# }
```

Notes:
- The existing endpoints under `/translate` remain as the primary, enhanced API (with optional fields like `pivot_path`, `metadata`, etc.).
- The `/compat` endpoints are provided for legacy clients and strict EasyNMT schema requirements.
