# Dockerfile - CPU production image with preloaded models
#
# FULL BUILD (preloads models - SLOW, ~5-10 minutes):
#   Linux/Mac: docker build -t scottgal/mostlylucid-nmt:latest --build-arg VERSION=$(date -u +"%Y%m%d.%H%M%S") .
#   Windows:   docker build -t scottgal/mostlylucid-nmt:latest .
#
# FAST DEVELOPMENT WORKFLOW:
#   Use Dockerfile.min instead! It skips model preloading:
#   docker build -f Dockerfile.min -t dev:latest .        # ~30 seconds
#
#   Linux/Mac: docker run -v ./src:/app/src -v ./model-cache:/models dev:latest
#   Windows:   docker run -v ${PWD}/src:/app/src -v ${PWD}/model-cache:/models dev:latest
#
# LAYER CACHING: This Dockerfile is optimized so code changes only rebuild the final layer:
#   1. Base image (cached unless Python version changes)
#   2. Python dependencies (cached unless requirements.txt changes)
#   3. Model downloads (SLOW - cached unless PRELOAD_LANGS/PRELOAD_PAIRS change)
#   4. Source code (rebuilds when .py files change - FAST!)
#
FROM python:3.12-slim

# Build arguments for versioning
ARG VERSION=dev
ARG BUILD_DATE
ARG VCS_REF

# OCI labels for metadata
LABEL org.opencontainers.image.title="mostlylucid-nmt" \
      org.opencontainers.image.description="FastAPI neural machine translation service - CPU with preloaded models" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/scottgal/mostlylucid-nmt" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.vendor="scottgal" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.documentation="https://github.com/scottgal/mostlylucid-nmt/blob/main/README.md" \
      variant="cpu-full"

# Prevent interactive prompts and reduce image size
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/models \
    HF_DATASETS_CACHE=/app/models \
    TORCH_HOME=/app/models \
    # Performance defaults optimized for CPU (fast as possible)
    WEB_CONCURRENCY=4 \
    MAX_WORKERS_BACKEND=4 \
    MAX_INFLIGHT_TRANSLATIONS=4 \
    EASYNMT_BATCH_SIZE=16 \
    MAX_CACHED_MODELS=5 \
    ENABLE_QUEUE=1 \
    MAX_QUEUE_SIZE=1000 \
    # Fast shutdown (5s graceful timeout instead of 20s)
    GRACEFUL_TIMEOUT=5

WORKDIR /app

# Ensure Python can import from /app (for "from src.app import app")
ENV PYTHONPATH=/app

# No extra system deps to keep image smaller (python:3.12-slim already includes what we need)

# Install Python dependencies (production only, no test tools)
COPY requirements-prod.txt ./
# --no-cache-dir: Reduces image size by not storing pip's download cache (~100MB saved)
# --no-compile: Skip .pyc compilation (faster builds, negligible runtime impact)
# Docker layer caching: When requirements changes, this layer rebuilds
RUN pip install --no-cache-dir --no-compile -r requirements-prod.txt

# Preload a minimal, curated set of Opus-MT models into /app/models to avoid runtime downloads
# Default build arg preloads EN<->(es,fr,de,it). Prefer specifying explicit pairs via PRELOAD_PAIRS.
# Override examples:
#   --build-arg PRELOAD_PAIRS="en->de,de->en,fr->en,en->it"
#   --build-arg PRELOAD_LANGS="es,fr,de"   # legacy: expands to EN<->XX for each
ARG PRELOAD_LANGS="es,fr,de,it"
ARG PRELOAD_PAIRS=""
RUN mkdir -p /app/models /app/tools
COPY tools/preload_models.py /app/tools/preload_models.py
RUN /bin/sh -c 'if [ -n "$PRELOAD_PAIRS" ]; then \
      python -u /app/tools/preload_models.py --family opus-mt --pairs "$PRELOAD_PAIRS" --dest /app/models; \
    else \
      python -u /app/tools/preload_models.py --family opus-mt --langs "$PRELOAD_LANGS" --dest /app/models; \
    fi'

# Copy source code
COPY src/ ./src/
COPY public/ ./public/
COPY app.py .

# Set default model cache directory to bundled models location
ENV MODEL_CACHE_DIR=/app/models

EXPOSE 8000

# Ensure fast, graceful shutdown: send SIGTERM and let Gunicorn handle it
STOPSIGNAL SIGTERM

# Use exec so Gunicorn becomes PID 1 and receives signals directly; add graceful timeout
CMD ["/bin/sh", "-lc", "exec gunicorn -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-1} -b 0.0.0.0:8000 --timeout ${TIMEOUT:-0} --graceful-timeout ${GRACEFUL_TIMEOUT:-30} --keep-alive ${KEEP_ALIVE:-5} app:app"]