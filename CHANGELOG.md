# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- **BREAKING**: Updated base images to address vulnerabilities
  - CPU images: `python:3.11-slim` → `python:3.13-slim`
  - GPU images: `nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04` → `nvidia/cuda:12.6.2-cudnn-runtime-ubuntu24.04`
  - PyTorch CUDA support: `cu121` → `cu124` (compatible with CUDA 12.6 runtime)
  - Ubuntu: 22.04 → 24.04 for GPU images

### Changed
- Updated all OCI labels to reflect CUDA 12.6 in GPU images
- Updated all documentation references from CUDA 12.1 to CUDA 12.6
- PyTorch installation now uses CUDA 12.4 wheels (cu124 index)

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
