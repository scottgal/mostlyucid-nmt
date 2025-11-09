# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2025-11-09

### Added
- EasyNMT compatibility namespace under `/compat` providing strict EasyNMT response shapes while keeping the enhanced primary API intact.
  - `GET /compat/translate` → `{ "translations": [...] }`
  - `POST /compat/translate` → `{ "target_lang", "source_lang", "detected_langs" (when auto), "translated", "translation_time" }`
- Prepack images (CPU `:cpu`, GPU `:gpu`) now ship with a minimal set of preloaded Opus‑MT models to remove first‑request latency:
  - Default preload languages: `es, fr, de, it` as en<->XX (8 repos total)
  - You can now also specify explicit language PAIRS at build time via `ARG PRELOAD_PAIRS` (preferred for Opus‑MT). The preloader will fetch direct pairs when available and will smart‑pivot via English (download `src->en` and `en->tgt`) when a non‑English direct pair is missing.
  - Location inside the image: `/app/models/Helsinki-NLP/opus-mt-*-*` (stored as `Helsinki-NLP--opus-mt-*-*`)
- Cache overlay behavior: you can map an external cache directory on prepack images and it works on top of the preloaded set.
  - Set `-v ./model-cache:/models -e MODEL_CACHE_DIR=/models`
  - The service prefers preloaded snapshots when present and stores any new downloads into the mapped cache.
- Release notes and documentation updated across README, DOCKER_HUB, and EasyNMT guide.
- Minimal images (`:cpu-min`, `:gpu-min`) preload nothing by design; mapping a cache is optional (without it, models are re‑downloaded each run).

### Fixed
- GPU Docker build failure at model preload step (`python: not found`). Switched to `python3` in `Dockerfile.gpu` for the preload script.

### Notes
- Version bumped to `3.0.0`.
- No breaking changes to the primary API; legacy clients can use `/compat`.

## [Unreleased]

### Security
- **BREAKING**: Updated base images to address vulnerabilities
  - CPU images: `python:3.11-slim` → `python:3.12-slim` (3.13 has FastAPI compatibility issues)
  - GPU images: `nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04` → `nvidia/cuda:12.6.2-cudnn-runtime-ubuntu24.04`
  - PyTorch CUDA support: `cu121` → `cu124` (compatible with CUDA 12.6 runtime)
  - Ubuntu: 22.04 → 24.04 for GPU images

### Fixed
- Added `--break-system-packages` flag to pip installs in GPU Dockerfiles for Ubuntu 24.04 compatibility (PEP 668)
- Fixed OCI image titles: All Dockerfiles now use same `org.opencontainers.image.title="mostlylucid-nmt"` to ensure all images go to ONE Docker Hub repository with different tags (previously used hyphened names that could cause confusion)
- **CRITICAL**: Fixed GitHub Actions CI/CD workflow to push all variants to ONE repository (`scottgal/mostlylucid-nmt`) with different tags (`:cpu`, `:cpu-min`, `:gpu`, `:gpu-min`) instead of creating separate repositories with hyphens (`mostlylucid-nmt-gpu`)
- **CRITICAL**: Fixed gunicorn startup error - changed `--keepalive` to `--keep-alive` in all Dockerfiles (containers were failing to start with "unrecognized arguments: --keepalive")
- **CRITICAL**: Fixed FastAPI/Pydantic compatibility issue - removed unused `translation` and `language` module imports from app.py (line 17) that were causing decorator registration to fail with "Invalid args for response field" error. The app.py file defines its own wrapper endpoints with proper dependency injection (lines 144-223), so these router imports were unnecessary and causing FastAPI 0.121.0 to fail validation on route parameters without Depends().

### Changed
- **Tag structure updated**: All images now use clearer tag names
  - `cpu` (alias: `latest`) instead of just `latest`
  - `cpu-min` instead of `min`
  - Version tags now include variant prefix (e.g., `cpu-20250108.143022`)
- Updated all OCI labels to reflect CUDA 12.6 in GPU images
- Updated all documentation references from CUDA 12.1 to CUDA 12.6
- PyTorch installation now uses CUDA 12.4 wheels (cu124 index)
- All badges updated to show 4 variants: cpu, cpu-min, gpu, gpu-min
- GitHub Actions now automatically syncs DOCKER_HUB.md to Docker Hub repository page

### Added
- **Comprehensive test suite** to prevent regression:
  - `test_app_startup.py`: Tests FastAPI app initialization, route registration, OpenAPI schema generation
  - `test_route_parameters.py`: Validates query parameter types, catches Optional[List[...]] issues
  - `test_docker_config.py`: Validates Dockerfile syntax, gunicorn arguments, OCI labels

## [2.0.0] - 2025-01-08

### Added
- **Multi-model family support**: Opus-MT (1200+ pairs), mBART50 (50 languages), M2M100 (100 languages)
- **Auto-fallback mechanism**: Automatically tries alternate model families for maximum coverage
- **Model discovery endpoints**: `/discover/opus-mt`, `/discover/mbart50`, `/discover/m2m100`, `/discover/all`
- **Minimal Docker images**: CPU-min and GPU-min variants without preloaded models
- **Volume-mapped model caching**: Persistent model storage across container restarts
- **Datetime versioning**: All images now tagged with build datetime (YYYYMMDD.HHMMSS)
- **OCI labels**: Full metadata including version, build date, git commit, and variant
- **Build scripts**: `build-all.ps1` (Windows) and `build-all.sh` (Linux/Mac)
- **Documentation**: BUILD.md, VERSIONING.md, DOCKER_HUB.md

### Changed
- Restructured Docker image variants into single repository with 4 tags
- All images now include proper versioning with both named and version tags
- Updated README with comprehensive "What's New" section
- Updated blog article with v2.0 features

### Configuration
- Added `MODEL_FAMILY` environment variable (opus-mt, mbart50, m2m100)
- Added `AUTO_MODEL_FALLBACK` (default: enabled)
- Added `MODEL_FALLBACK_ORDER` (default: "opus-mt,mbart50,m2m100")
- Added `MODEL_CACHE_DIR` for volume-mapped cache

## [1.0.0] - Initial Release

### Features
- FastAPI-based translation service
- EasyNMT-compatible API endpoints
- Opus-MT (Helsinki-NLP) model support
- CPU and GPU support with CUDA 12.1
- LRU model caching with automatic eviction
- Request queueing and backpressure handling
- Health, readiness, and cache status endpoints
- Structured logging with JSON output
- Graceful shutdown handling
- Symbol masking and input sanitization
- Pivot translation fallback
- Docker images for CPU and GPU

### API Endpoints
- `POST /translate` - Translate text (batch supported)
- `GET /translate` - Query parameter translation
- `GET /lang_pairs` - List supported language pairs
- `GET /get_languages` - Get supported languages
- `POST /language_detection` - Detect language
- `GET /model_name` - Get model information
- `GET /healthz` - Health check
- `GET /readyz` - Readiness check
- `GET /cache` - Cache status

### Configuration
- Device selection (USE_GPU, DEVICE)
- Model preloading (PRELOAD_MODELS)
- Queue configuration (MAX_QUEUE_SIZE, MAX_INFLIGHT_TRANSLATIONS)
- Timeout settings (TRANSLATE_TIMEOUT_SEC)
- Logging options (LOG_LEVEL, LOG_FORMAT, LOG_TO_FILE)
- Input sanitization controls
- Response alignment options
