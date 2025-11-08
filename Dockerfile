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
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for performance (optional) and SSL
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY public/ ./public/
COPY app.py .

EXPOSE 8000

# Ensure fast, graceful shutdown: send SIGTERM and let Gunicorn handle it
STOPSIGNAL SIGTERM

# Use exec so Gunicorn becomes PID 1 and receives signals directly; add graceful timeout
CMD ["/bin/sh", "-lc", "exec gunicorn -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-1} -b 0.0.0.0:8000 --timeout ${TIMEOUT:-60} --graceful-timeout ${GRACEFUL_TIMEOUT:-20} --keep-alive ${KEEP_ALIVE:-5} app:app"]