# Dockerfile
# Build: docker build -t mostlylucid-nmt .
FROM python:3.11-slim

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
COPY app.py .

EXPOSE 8000

# Ensure fast, graceful shutdown: send SIGTERM and let Gunicorn handle it
STOPSIGNAL SIGTERM

# Use exec so Gunicorn becomes PID 1 and receives signals directly; add graceful timeout
CMD ["/bin/sh", "-lc", "exec gunicorn -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-1} -b 0.0.0.0:8000 --timeout ${TIMEOUT:-60} --graceful-timeout ${GRACEFUL_TIMEOUT:-20} --keepalive ${KEEP_ALIVE:-5} app:app"]