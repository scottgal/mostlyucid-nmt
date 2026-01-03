# mostlylucid-nmt (EasyNMT-compatible API)

[![Docker Pulls](https://img.shields.io/docker/pulls/scottgal/mostlylucid-nmt)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)
[![latest](https://img.shields.io/docker/v/scottgal/mostlylucid-nmt/latest?label=latest)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)
[![cpu](https://img.shields.io/docker/v/scottgal/mostlylucid-nmt/cpu?label=cpu)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)
[![gpu](https://img.shields.io/docker/v/scottgal/mostlylucid-nmt/gpu?label=gpu)](https://hub.docker.com/r/scottgal/mostlylucid-nmt)

A drop-in EasyNMT replacement that runs locally, survives long-running workloads, and won't OOM your server when someone pastes a book into it.

> **Not a hosted SaaS, not a black box API.** This project optimises for predictability, bounded memory, and failure modes you can reason about.

**Why this exists (the practical bits):**
- **On-demand model loading + LRU eviction** to avoid OOM and keep long-running services stable
- **Backpressure + request queueing** with smart `Retry-After` so clients can behave nicely under load
- **Markdown-safe translation pipeline** (sanitization + symbol masking) to prevent parser depth/bracket failures

**EasyNMT-compatible endpoints:** `/translate` (GET/POST), `/lang_pairs`, `/language_detection`, `/model_name`
Swagger: `/docs` · ReDoc: `/redoc` · **[Complete Guide](https://www.mostlylucid.net/blog/mostlylucid-nmt-complete-guide)**

---

## Quick Start

> **Just want a single binary?** Skip Docker — see [Standalone Executable](#standalone-executable) below.

### CPU (persistent cache) — most users start here
```bash
docker run -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_CACHE_DIR=/models \
  scottgal/mostlylucid-nmt:cpu
```

### GPU (persistent cache + FP16)
```bash
docker run --gpus all -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_CACHE_DIR=/models \
  -e USE_GPU=true \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  scottgal/mostlylucid-nmt:gpu
```

### Highest Quality (LLM-based, GPU required, significantly slower)

> **Reality check:** 7B models require 16GB+ VRAM and are 50-100x slower than opus-mt. They are not a free upgrade.

```bash
# HY-MT: Best quality for major languages (en, zh, de, fr, es, ja, ko, etc.)
docker run --gpus all -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_CACHE_DIR=/models \
  -e USE_GPU=true \
  -e MODEL_FAMILY=hymt \
  -e HYMT_MODEL_SIZE=7B \
  scottgal/mostlylucid-nmt:gpu

# MADLAD: 400+ languages including rare/low-resource
docker run --gpus all -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_CACHE_DIR=/models \
  -e USE_GPU=true \
  -e MODEL_FAMILY=madlad \
  -e MADLAD_MODEL_SIZE=7b \
  scottgal/mostlylucid-nmt:gpu
```

> **Important (GPU):** `USE_GPU=true` does nothing unless you run with `--gpus all`.
> **Important (cache):** Without `-v ./model-cache:/models` + `MODEL_CACHE_DIR=/models`, models re-download on every restart.

### Try the API
```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text":["Hello world"],"source_lang":"en","target_lang":"de","beam_size":1}'
```

---

## Model Families

**Quick chooser:**

| If you want…                  | Use               |
|-------------------------------|-------------------|
| Fast, cheap, production       | opus-mt (default) |
| One model, many languages     | m2m100            |
| Best quality major languages  | hymt              |
| Rare / low-resource languages | madlad            |

Set via `MODEL_FAMILY` environment variable or per-request with `"model_family": "..."`:

**Fast (CPU-friendly, recommended):**
- **opus-mt** (default): Best quality/speed, 1200+ directional pairs
- **mbart50**: Single model, 50 languages
- **m2m100**: Single model, 100 languages

**High quality (GPU recommended):**
- **hymt**: LLM-based (Tencent Hunyuan), best quality for major language pairs
- **madlad**: T5-based (Google), 400+ languages including low-resource

```bash
# Per-request override
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text":["Hello"],"source_lang":"en","target_lang":"zh","model_family":"hymt"}'
```

**Auto-fallback** (enabled by default): If a pair isn't available in your chosen family, it tries the fallback order automatically.

---

## Backends

- **CTranslate2**: Smaller footprint, faster CPU inference (standalone exe + CPU images)
- **Transformers/PyTorch**: Best CUDA support (GPU images)

Auto-selected based on what's installed. You normally don't need to configure this.

---

## Reference

<details>
<summary><strong>CLI Commands & Options</strong></summary>

| Command | Description | Example |
|---------|-------------|---------|
| `translate` | Translate text directly | `translate "Hello" --to de` |
| `server` | Start HTTP API server | `server --port 8000` |
| `mcp` | MCP server for LLM integration | `mcp` |
| `languages` | List supported languages | `languages --json` |
| `status` | Check server health & cache | `status` |
| `info` | Show configuration | `info` |

```bash
# Global options
--version, -v         Show version
--json, -j            JSON output format
--host                Server host (default: 127.0.0.1)
--port, -p            Server port (default: 8000)

# translate options
--to, -t              Target language (required)
--source, -s          Source language (default: en, or auto-detect)
--model, -m           Model family: opus-mt, mbart50, m2m100

# server options
--workers, -w         Number of workers (default: 1)
--reload              Auto-reload for development
--background, -b      Run as daemon
```

**Smart Server Detection:** If server is running, CLI uses HTTP API (fast). Otherwise loads model directly (slower first time).

</details>

<details>
<summary><strong>MCP Integration (Claude Code / LLMs)</strong></summary>

```json
// ~/.claude/settings.json
{
  "mcpServers": {
    "translate": {
      "command": "mostlylucid-nmt",
      "args": ["mcp"]
    }
  }
}
```

Available tools: `translate`, `detect_language`, `list_languages`

</details>

<details>
<summary><strong>Model Family Details & Performance</strong></summary>

### Fast Models (CPU-friendly)

| Family | Languages | Pairs | Model Type | Size | Speed |
|--------|-----------|-------|------------|------|-------|
| **opus-mt** | 150+ | 1200+ | Separate per direction | ~300MB each | Fast |
| **mbart50** | 50 | 2,450 | Single multilingual | ~2.4GB | Fast |
| **m2m100** | 100 | 9,900 | Single multilingual | ~2.2GB | Fast |

### High-Quality Models (GPU recommended)

| Family | Languages | Model Type | Size | Speed | Notes |
|--------|-----------|------------|------|-------|-------|
| **hymt** | 34 | LLM (1.8B/7B) | 3.5-14GB | Slow | Best quality for major pairs |
| **madlad** | 400+ | T5 (3B/7B/10B) | 6-20GB | Slow | Best for rare languages |

### Performance Benchmark

Translating ~385 chars (README excerpt) English→German:

| Model | Time | Speed | Relative |
|-------|------|-------|----------|
| **opus-mt** | 0.93s | 412 chars/sec | 1.0x baseline |
| **m2m100** | 5.02s | 76 chars/sec | 5.4x slower |
| **hymt** | 44.35s | 9 chars/sec | 48x slower |
| **madlad** | 105.53s | 4 chars/sec | 114x slower |

*Tested on AMD Ryzen 9 9950X / NVIDIA RTX A4000 16GB, CPU inference. GPU is significantly faster for hymt/madlad.*

### Configuration

**HY-MT:**
```bash
HYMT_MODEL_SIZE=1.8B      # 1.8B (default) or 7B
HYMT_TOP_K=20             # Top-k sampling
HYMT_TOP_P=0.6            # Nucleus sampling
HYMT_TEMPERATURE=0.7      # Generation temperature
```

**MADLAD:**
```bash
MADLAD_MODEL_SIZE=3b      # 3b (default), 7b, or 10b
MADLAD_MAX_LENGTH=256     # Max output length
```

</details>

<details>
<summary><strong>API Endpoints</strong></summary>

Full API documentation at `/docs` (Swagger UI).

**POST /translate:**
```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text": ["Hello world"], "target_lang": "de", "source_lang": "en", "beam_size": 1}'
```

**Other endpoints:**
- `GET /lang_pairs` - All supported language pairs
- `POST /language_detection` - Detect language of input text
- `GET /healthz` - Health check
- `GET /readyz` - Readiness check
- `GET /cache` - Model cache status
- `GET /discover/opus-mt|mbart50|m2m100|all` - Available pairs

</details>

<details>
<summary><strong>Configuration Reference</strong></summary>

### Device & Model
```bash
USE_GPU=auto                # true|false|auto
DEVICE=auto                 # cpu|cuda|cuda:0
MODEL_FAMILY=opus-mt        # opus-mt|mbart50|m2m100|hymt|madlad
AUTO_MODEL_FALLBACK=1       # Try other families if pair unavailable
MODEL_CACHE_DIR=/models     # Cache directory for volume mapping
MAX_CACHED_MODELS=10        # LRU cache capacity
```

### Performance
```bash
EASYNMT_BATCH_SIZE=16       # 16 CPU, 64 GPU
EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'  # FP16 for GPU
PRELOAD_MODELS="en->de,de->en"
MAX_INFLIGHT_TRANSLATIONS=1  # auto: 1 GPU, 4 CPU
```

### Memory Management
```bash
ENABLE_MEMORY_MONITOR=1     # Auto-evict on high memory
MEMORY_CRITICAL_THRESHOLD=90.0
GPU_MEMORY_CRITICAL_THRESHOLD=90.0
```

### Chunk Cache (LFU)
```bash
CHUNK_CACHE_ENABLED=1
CHUNK_CACHE_CAPACITY=10000  # ~25MB at capacity
CHUNK_CACHE_MAX_AGE=3600    # TTL in seconds
```

### Queueing & Timeouts
```bash
ENABLE_QUEUE=1
MAX_QUEUE_SIZE=1000
TIMEOUT=120
```

### Logging
```bash
LOG_LEVEL=INFO        # DEBUG for verbose
LOG_TO_FILE=1         # Enable file logging
LOG_FORMAT=json       # For log aggregation
```

### Markdown Sanitization
Prevents parser depth errors in translated markdown:
```bash
MARKDOWN_SANITIZE=1
MARKDOWN_SAFE_MODE_AUTO=1  # Auto-enable for RTL targets
```

</details>

<details>
<summary><strong>Troubleshooting</strong></summary>

| Issue | Solution |
|-------|----------|
| **GPU not used** | Add `--gpus all` flag to docker run |
| **Models re-download** | Add `-v ./model-cache:/models -e MODEL_CACHE_DIR=/models` |
| **Out of memory** | Use FP16: `-e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'` |
| **429 errors** | Increase `MAX_QUEUE_SIZE` or check `Retry-After` header |
| **Missing pair** | Enable auto-fallback (default ON) or try different model family |

</details>

<details>
<summary><strong>Building from Source</strong></summary>

**Standalone executable:**
```bash
pip install pyinstaller
pyinstaller mostlylucid_nmt.spec --clean
```

**Docker:**
```bash
docker build -f Dockerfile.min -t mostlylucid-nmt:cpu .
docker build -f Dockerfile.gpu.min -t mostlylucid-nmt:gpu .
```

See [BUILD.md](BUILD.md) for full instructions.

</details>

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
