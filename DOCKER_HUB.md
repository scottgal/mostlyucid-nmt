# mostlylucid-nmt Docker Images

Production-ready FastAPI service for neural machine translation with multiple model family support.

## Quick Links
- [GitHub Repository](https://github.com/scottgal/mostlylucid-nmt)
- [Full Documentation](https://github.com/scottgal/mostlylucid-nmt/blob/main/README.md)
- [Docker Hub](https://hub.docker.com/r/scottgal/mostlylucid-nmt)

## Available Tags

All variants are available in this single repository as different tags:

| Tag | Full Image Name | Size | Description | Use Case |
|-----|-----------------|------|-------------|----------|
| `latest` | `scottgal/mostlylucid-nmt:latest` | ~2.5GB | CPU with source code | Production CPU deployments |
| `min` | `scottgal/mostlylucid-nmt:min` | ~1.5GB | CPU minimal, no preloaded models | Volume-mapped cache, flexible |
| `gpu` | `scottgal/mostlylucid-nmt:gpu` | ~5GB | GPU with CUDA 12.1 + source | Production GPU deployments |
| `gpu-min` | `scottgal/mostlylucid-nmt:gpu-min` | ~4GB | GPU minimal, no preloaded models | GPU with volume-mapped cache |

**Note:** All images are built from the same source code, just with different configurations and base images.

### Pulling Images

```bash
# Pull specific tag
docker pull scottgal/mostlylucid-nmt:latest
docker pull scottgal/mostlylucid-nmt:min
docker pull scottgal/mostlylucid-nmt:gpu
docker pull scottgal/mostlylucid-nmt:gpu-min

# Or just run (auto-pulls if not present)
docker run scottgal/mostlylucid-nmt:gpu
```

## Supported Model Families

- **Opus-MT** (Helsinki-NLP): 1200+ translation pairs, best quality
- **mBART50** (Facebook): 50 languages, all-to-all, single model
- **M2M100** (Facebook): 100 languages, all-to-all, single model

Switch between them using `MODEL_FAMILY` environment variable.

## Quick Start

### `latest` - CPU Production Image

Best for: Production CPU deployments with preloaded models

```bash
docker run -d -p 8000:8000 scottgal/mostlylucid-nmt
```

### `min` - CPU Minimal Image

Best for: Volume-mapped cache, switching model families without rebuilding

```bash
docker run -d -p 8000:8000 \
  -v ./model-cache:/models \
  -e MODEL_CACHE_DIR=/models \
  -e MODEL_FAMILY=opus-mt \
  scottgal/mostlylucid-nmt:min
```

### `gpu` - GPU Production Image

Best for: Production GPU deployments with FP16, 10x faster

```bash
docker run -d --gpus all -p 8000:8000 \
  -e USE_GPU=true \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  scottgal/mostlylucid-nmt:gpu
```

### `gpu-min` - GPU Minimal Image

Best for: GPU with volume-mapped cache for large multilingual models

```bash
docker run -d --gpus all -p 8000:8000 \
  -v ./model-cache:/models \
  -e USE_GPU=true \
  -e MODEL_FAMILY=mbart50 \
  -e MODEL_CACHE_DIR=/models \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  scottgal/mostlylucid-nmt:gpu-min
```

## Features

- ✅ **Multi-model family support** - Opus-MT, mBART50, M2M100
- ✅ **Auto-fallback** - Automatically tries other model families for maximum coverage
- ✅ **Production-ready** - Queueing, backpressure, graceful shutdown
- ✅ **GPU accelerated** - CUDA 12.1, FP16/BF16 support
- ✅ **EasyNMT compatible** - Drop-in replacement
- ✅ **Model discovery** - Dynamically query available models
- ✅ **Persistent cache** - Volume-mapped model storage

## Key Configuration

```bash
# Model family selection
MODEL_FAMILY=opus-mt  # or mbart50, m2m100

# Auto-fallback (enabled by default)
AUTO_MODEL_FALLBACK=1
MODEL_FALLBACK_ORDER="opus-mt,mbart50,m2m100"

# Volume-mapped cache
MODEL_CACHE_DIR=/models

# GPU optimization
USE_GPU=true
EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'

# Preload models (optional)
PRELOAD_MODELS="en->de,de->en,fr->en"
```

## API Endpoints

- `POST /translate` - Translate text (batch supported)
- `GET /lang_pairs` - List supported language pairs
- `GET /discover/opus-mt` - Discover available Opus-MT models
- `GET /discover/mbart50` - List mBART50 language pairs
- `GET /discover/m2m100` - List M2M100 language pairs
- `GET /healthz` - Health check
- `GET /readyz` - Readiness check
- `GET /cache` - Cache status

## Example Request

```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{
    "text": ["Hello world", "Machine translation is amazing"],
    "target_lang": "de",
    "source_lang": "en",
    "beam_size": 1
  }'
```

## Performance Tips

**GPU:**
- Use FP16: `EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'`
- Increase batch size: `EASYNMT_BATCH_SIZE=64`
- Single worker: `WEB_CONCURRENCY=1`
- Preload hot models: `PRELOAD_MODELS="en->de,de->en"`

**CPU:**
- Lower batch size: `EASYNMT_BATCH_SIZE=8`
- More workers: `MAX_WORKERS_BACKEND=4`

## Documentation

Full documentation: https://github.com/scottgal/mostlylucid-nmt/blob/main/README.md

## License

MIT License - Free for personal and commercial use
