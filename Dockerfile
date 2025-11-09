# Dockerfile - CPU production image with preloaded models
# Build: docker build -t scottgal/mostlylucid-nmt:latest --build-arg VERSION=$(date -u +"%Y%m%d.%H%M%S") .
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
    TRANSFORMERS_CACHE=/app/models \
    HF_DATASETS_CACHE=/app/models \
    TORCH_HOME=/app/models

WORKDIR /app

# No extra system deps to keep image smaller (python:3.12-slim already includes what we need)

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --no-compile -r requirements.txt

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
CMD ["/bin/sh", "-lc", "exec gunicorn -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-1} -b 0.0.0.0:8000 --timeout ${TIMEOUT:-60} --graceful-timeout ${GRACEFUL_TIMEOUT:-20} --keep-alive ${KEEP_ALIVE:-5} app:app"]