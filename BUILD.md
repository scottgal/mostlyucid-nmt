# Building and Publishing Docker Images

This guide explains how to build and publish all 4 Docker image variants with proper versioning.

## Image Variants

All variants are published to the same repository: `scottgal/mostlylucid-nmt`

**Multi-Platform Images** (AMD64 + ARM64):
| Tag | Dockerfile | Platforms | Description | Approx Size |
|-----|------------|-----------|-------------|------------|
| `latest` / `cpu` | `Dockerfile` | AMD64, ARM64 | CPU with preloaded models | 8-10GB (AMD64), 7-9GB (ARM64) |
| `cpu-min` | `Dockerfile.min` | AMD64, ARM64 | CPU minimal, no preloaded models | 3-4GB (AMD64), 2-3GB (ARM64) |

**Single-Platform Images** (AMD64 only with CUDA):
| Tag | Dockerfile | Platform | Description | Approx Size |
|-----|------------|----------|-------------|------------|
| `gpu` | `Dockerfile.gpu` | AMD64 | GPU with CUDA 12.1 and preloaded models | 12-15GB |
| `gpu-min` | `Dockerfile.gpu.min` | AMD64 | GPU minimal, no preloaded models | 6-8GB |

**Architecture Auto-Detection**: When you `docker pull scottgal/mostlylucid-nmt:latest`, Docker automatically selects:
- **AMD64** version on x86_64 PCs
- **ARM64** version on Raspberry Pi and Apple Silicon Macs

**Why larger than EasyNMT (2-3GB)?**
- **PyTorch 2.x vs 1.8**: Modern PyTorch is 5x larger (750MB vs 150MB for CPU, 5GB vs 1GB for GPU)
- **CUDA 12.x runtime**: Newer CUDA toolkits are significantly larger
- **Python 3.12 vs 3.8**: Modern Python includes more stdlib modules
- **Better model support**: Transformers 4.x supports many more model architectures

**Use `:min` variants** to avoid preloading models and reduce size by 60%

## Fast Development Builds

### TL;DR - Fastest Iteration Methods

**For rapid code-only changes (just updating .py files):**

**Linux/Mac (Bash):**
```bash
# Option 1: Use minimal build (skips model downloads) - ~30 seconds
docker build -f Dockerfile.min -t mostlylucid-dev:latest .

# Option 2: Volume mount for ZERO rebuild - INSTANT
# Models download on first use, then cached in ./model-cache
docker run -p 8000:8000 \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/app.py:/app/app.py \
  -v $(pwd)/model-cache:/models \
  scottgal/mostlylucid-nmt:cpu-min
```

**Windows (PowerShell):**
```powershell
# Option 1: Use minimal build (skips model downloads) - ~30 seconds
docker build -f Dockerfile.min -t mostlylucid-dev:latest .

# Option 2: Volume mount for ZERO rebuild - INSTANT
# Models download on first use, then cached in .\model-cache
docker run -p 8000:8000 `
  -v ${PWD}/src:/app/src `
  -v ${PWD}/app.py:/app/app.py `
  -v ${PWD}/model-cache:/models `
  scottgal/mostlylucid-nmt:cpu-min
```

### Understanding Docker Layer Caching

Docker builds images in layers. Each `RUN`, `COPY`, `ADD` command creates a new layer. When you rebuild:
- **Cached layers**: Steps that haven't changed are reused (fast!)
- **Rebuilt layers**: Steps after the first change are rebuilt (slow)

**Current Dockerfile structure** (optimized for caching):
```dockerfile
# Layer 1: Base image (rarely changes)
FROM python:3.12-slim

# Layer 2: System dependencies (rarely changes)
# ... system packages ...

# Layer 3: Python dependencies (changes occasionally)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Note: --no-cache-dir reduces image size by not storing pip's download cache
# Docker layer caching still works! This entire layer is reused if requirements.txt hasn't changed

# Layer 4: Model downloads (SLOW - only in full images)
# This is why Dockerfile.min is faster!

# Layer 5: Source code (changes frequently)
COPY src/ ./src/
COPY app.py .
```

**Impact**: When you change Python code (`.py` files), only Layer 5 rebuilds!

#### Two Types of Caching (Don't Confuse Them!)

1. **Docker Layer Caching** (Makes rebuilds fast)
   - Docker caches entire layers
   - When `requirements.txt` doesn't change, Docker reuses the cached pip install layer
   - **This is why rebuilds are fast!**

2. **pip's Internal Cache** (--no-cache-dir disables this)
   - pip normally caches downloaded packages in `~/.cache/pip`
   - In Docker, this cache would be stored in the image (wasting space)
   - `--no-cache-dir` prevents this, making images smaller
   - **Does NOT affect Docker layer caching or build speed!**

**Example:**
```bash
# First build: Downloads everything, creates layer (slow)
docker build -f Dockerfile.min -t dev .  # ~30 seconds

# Change a .py file, rebuild
docker build -f Dockerfile.min -t dev .  # ~3 seconds
# Docker reuses the pip install layer (didn't download anything!)
# Only copies new source code
```

### Development Workflow Options

#### Option 1: Minimal Image (Fastest Build - ~30s)

Use `Dockerfile.min` or `Dockerfile.gpu.min` - they skip model preloading.

**Linux/Mac:**
```bash
# CPU version
docker build -f Dockerfile.min -t mostlylucid-dev .

# GPU version
docker build -f Dockerfile.gpu.min -t mostlylucid-dev-gpu .

# Run with model cache volume
docker run -p 8000:8000 \
  -v ./model-cache:/models \
  -e PRELOAD_MODELS="en->de,de->en" \
  mostlylucid-dev
```

**Windows:**
```powershell
# CPU version
docker build -f Dockerfile.min -t mostlylucid-dev .

# GPU version
docker build -f Dockerfile.gpu.min -t mostlylucid-dev-gpu .

# Run with model cache volume
docker run -p 8000:8000 `
  -v ${PWD}\model-cache:/models `
  -e PRELOAD_MODELS="en->de,de->en" `
  mostlylucid-dev
```

**When to use**: When you need a clean build but don't want to wait for model downloads.

**Build time**:
- First build: ~30 seconds (dependencies only)
- Rebuild after code change: ~3 seconds (just copies source files)

#### Option 2: Volume Mounts (ZERO Rebuild - Instant!)

Mount your source code directly into a running container. Code changes reflect immediately!

**Linux/Mac:**
```bash
# Start container with source code mounted
docker run -p 8000:8000 \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/app.py:/app/app.py \
  -v $(pwd)/public:/app/public \
  -v $(pwd)/model-cache:/models \
  -e LOG_LEVEL=DEBUG \
  scottgal/mostlylucid-nmt:cpu-min
```

**Windows:**
```powershell
# Start container with source code mounted
docker run -p 8000:8000 `
  -v ${PWD}/src:/app/src `
  -v ${PWD}/app.py:/app/app.py `
  -v ${PWD}/public:/app/public `
  -v ${PWD}/model-cache:/models `
  -e LOG_LEVEL=DEBUG `
  scottgal/mostlylucid-nmt:cpu-min
```

**When to use**: Active development - edit code in your IDE, restart container to see changes.

**Advantages**:
- ZERO build time
- Use your local editor
- Model cache persists between restarts
- Logs show immediately

**Restart to reload code (same on all platforms)**:
```bash
# Find container ID
docker ps

# Restart container (2-3 seconds)
docker restart <container-id>
```

#### Option 3: Hot Reload with Uvicorn (Development Server)

Run the app directly with auto-reload:

**Linux/Mac:**
```bash
# Run development server with auto-reload
docker run -p 8000:8000 \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/app.py:/app/app.py \
  -v $(pwd)/model-cache:/models \
  -e LOG_LEVEL=DEBUG \
  scottgal/mostlylucid-nmt:cpu-min \
  uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

**Windows:**
```powershell
# Run development server with auto-reload
docker run -p 8000:8000 `
  -v ${PWD}/src:/app/src `
  -v ${PWD}/app.py:/app/app.py `
  -v ${PWD}/model-cache:/models `
  -e LOG_LEVEL=DEBUG `
  scottgal/mostlylucid-nmt:cpu-min `
  uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

**When to use**: Active development - code changes apply automatically without restart!

**Note**: Use `--reload` only in development, never in production.

### Comparison Table

| Method | First Time | After Code Change | Models | Best For |
|--------|-----------|-------------------|--------|----------|
| **Full build** (Dockerfile) | ~5-10 min | ~5-10 min | Preloaded | Production |
| **Minimal build** (Dockerfile.min) | ~30 sec | ~3 sec | Downloaded on use | Clean dev builds |
| **Volume mount** | 0 sec | 0 sec (restart 2s) | Downloaded on use | Active development |
| **Hot reload** | 0 sec | 0 sec (instant) | Downloaded on use | Rapid iteration |

### Tips for Fastest Development

1. **Use `.min` Dockerfiles for development**

   **Linux/Mac:**
   ```bash
   docker build -f Dockerfile.min -t dev:latest .
   ```

   **Windows:**
   ```powershell
   docker build -f Dockerfile.min -t dev:latest .
   ```

2. **Create a model cache volume once, reuse forever**

   **Linux/Mac:**
   ```bash
   # First time: models download to ./model-cache
   docker run -v $(pwd)/model-cache:/models dev:latest

   # Subsequent runs: instant model loading
   docker run -v $(pwd)/model-cache:/models dev:latest
   ```

   **Windows:**
   ```powershell
   # First time: models download to .\model-cache
   docker run -v ${PWD}/model-cache:/models dev:latest

   # Subsequent runs: instant model loading
   docker run -v ${PWD}/model-cache:/models dev:latest
   ```

3. **Use Docker Compose for easy dev setup**
   ```yaml
   # docker-compose.dev.yml
   services:
     app:
       image: scottgal/mostlylucid-nmt:cpu-min
       ports:
         - "8000:8000"
       volumes:
         - ./src:/app/src
         - ./app.py:/app/app.py
         - ./model-cache:/models
       environment:
         - LOG_LEVEL=DEBUG
         - PRELOAD_MODELS=en->de,de->en
       command: uvicorn src.app:app --host 0.0.0.0 --reload
   ```

   ```bash
   docker-compose -f docker-compose.dev.yml up
   ```

4. **When dependencies change (requirements.txt)**
   ```bash
   # Must rebuild to install new dependencies
   docker build -f Dockerfile.min -t dev:latest .
   ```

5. **Layer caching works best with clean Git state**
   ```bash
   # .dockerignore prevents cache invalidation from temp files
   __pycache__/
   *.pyc
   .pytest_cache/
   .coverage
   htmlcov/
   ```

### Production vs Development Builds

**Development (fast iteration)**:

Linux/Mac:
```bash
docker build -f Dockerfile.min -t dev:latest .
docker run -v ./src:/app/src -v ./model-cache:/models dev:latest
```

Windows:
```powershell
docker build -f Dockerfile.min -t dev:latest .
docker run -v ${PWD}/src:/app/src -v ${PWD}/model-cache:/models dev:latest
```

**Production (preloaded models)**:

Same on all platforms:
```bash
docker build --build-arg PRELOAD_PAIRS="en->de,de->en,fr->en,en->es" -t prod:latest .
docker run -p 8000:8000 prod:latest
```

---

## API Validation

After building and running your Docker image, validate that the API works correctly.

### Automated Validation Tests

**Quick validation (smoke tests only - ~10 seconds):**

Windows:
```powershell
# Start the API first
docker run -p 8000:8000 dev:latest

# In another terminal, run smoke tests
.\validate-api.ps1 -SmokeOnly
```

Linux/Mac:
```bash
# Start the API first
docker run -p 8000:8000 dev:latest

# In another terminal, run smoke tests
chmod +x validate-api.sh
./validate-api.sh --smoke-only
```

**Full validation suite (~30 seconds):**

Windows:
```powershell
.\validate-api.ps1
```

Linux/Mac:
```bash
./validate-api.sh
```

**Test against different URL:**

Windows:
```powershell
.\validate-api.ps1 -BaseURL http://localhost:8001
```

Linux/Mac:
```bash
./validate-api.sh --base-url http://localhost:8001
```

### What Gets Tested

The automated validation tests check:
- Health & observability endpoints (healthz, readyz, cache, model info)
- Basic translation (GET and POST)
- Multiple text translation
- Language detection (GET and POST, string/list/dict)
- Language pairs and discovery
- Advanced features (auto-detect, beam size, empty lists)
- Error handling (missing params, invalid values)
- Documentation endpoints (OpenAPI, Swagger)
- EasyNMT compatibility endpoints

**Total: 30+ test cases**

### Manual Testing with .http File

For interactive testing, use `api-tests.http` with VS Code REST Client:

1. Install "REST Client" extension in VS Code
2. Open `api-tests.http`
3. Click "Send Request" above any request
4. View response in side panel

**85+ test cases available** covering all endpoints and edge cases.

---

## Automated Build (Recommended)

The `build-all` scripts now support **multi-platform builds** using Docker buildx. They automatically build for both AMD64 and ARM64 (Raspberry Pi, Apple Silicon) where applicable.

### Local Build (Single Platform)

**Windows (PowerShell)**:
```powershell
.\build-all.ps1
```

**Linux/Mac (Bash)**:
```bash
chmod +x build-all.sh
./build-all.sh
```

Builds locally for your current platform only (fast, uses `--load`).

### Multi-Platform Build and Push

**Windows (PowerShell)**:
```powershell
.\build-all.ps1 -Push
```

**Linux/Mac (Bash)**:
```bash
./build-all.sh --push
```

Builds for **both AMD64 and ARM64** (CPU variants only) and pushes to Docker Hub with manifest lists. GPU variants remain AMD64-only (CUDA requirement).

**What the scripts do**:
1. Generate version string: `YYYYMMDD.HHMMSS`
2. Get git commit hash for VCS_REF label
3. Set up Docker buildx for multi-platform builds
4. Build CPU variants for AMD64 + ARM64 (multi-platform manifest)
5. Build GPU variants for AMD64 only (CUDA)
6. Tag with both named tags (`:latest`, `:cpu`, `:gpu`, etc.) and version tags (`:cpu-20250108.143022`)
7. Push to Docker Hub (when `--push` flag used)

## Manual Build

### Set Version Variables

**Windows PowerShell:**
```powershell
$VERSION = (Get-Date).ToUniversalTime().ToString("yyyyMMdd.HHmmss")
$BUILD_DATE = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$VCS_REF = (git rev-parse --short HEAD)
```

**Linux/Mac Bash:**
```bash
VERSION=$(date -u +"%Y%m%d.%H%M%S")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VCS_REF=$(git rev-parse --short HEAD)
```

### Build Individual Variants

**CPU Full (cpu and latest):**
```bash
docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t scottgal/mostlylucid-nmt:cpu \
  -t scottgal/mostlylucid-nmt:latest \
  -t scottgal/mostlylucid-nmt:cpu-${VERSION} \
  -f Dockerfile \
  .
```

**CPU Minimal (cpu-min):**
```bash
docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t scottgal/mostlylucid-nmt:cpu-min \
  -t scottgal/mostlylucid-nmt:cpu-min-${VERSION} \
  -f Dockerfile.min \
  .
```

**GPU Full (gpu):**
```bash
docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t scottgal/mostlylucid-nmt:gpu \
  -t scottgal/mostlylucid-nmt:gpu-${VERSION} \
  -f Dockerfile.gpu \
  .
```

**GPU Minimal (gpu-min):**
```bash
docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t scottgal/mostlylucid-nmt:gpu-min \
  -t scottgal/mostlylucid-nmt:gpu-min-${VERSION} \
  -f Dockerfile.gpu.min \
  .
```

## Publishing to Docker Hub

### Prerequisites

1. Login to Docker Hub:
```bash
docker login
```

2. Ensure you have push access to the `scottgal/mostlylucid-nmt` repository

### Push Individual Tags

```bash
# Push CPU variants
docker push scottgal/mostlylucid-nmt:cpu
docker push scottgal/mostlylucid-nmt:latest
docker push scottgal/mostlylucid-nmt:cpu-${VERSION}
docker push scottgal/mostlylucid-nmt:cpu-min
docker push scottgal/mostlylucid-nmt:cpu-min-${VERSION}

# Push GPU variants
docker push scottgal/mostlylucid-nmt:gpu
docker push scottgal/mostlylucid-nmt:gpu-${VERSION}
docker push scottgal/mostlylucid-nmt:gpu-min
docker push scottgal/mostlylucid-nmt:gpu-min-${VERSION}
```

### Push All Tags at Once

```bash
docker push scottgal/mostlylucid-nmt --all-tags
```

## Versioning Strategy

### Tag Format

Each build creates **two tags** per variant:

1. **Named tag**: `cpu` (alias: `latest`), `cpu-min`, `gpu`, `gpu-min` (always points to most recent build)
2. **Version tag**: `YYYYMMDD.HHMMSS` format (immutable snapshot)

Example:
- `scottgal/mostlylucid-nmt:cpu` (or `:latest`) → Most recent CPU full build
- `scottgal/mostlylucid-nmt:cpu-20250108.143022` → Specific build from Jan 8, 2025 at 14:30:22 UTC
- `scottgal/mostlylucid-nmt:cpu-min-20250108.143022` → Specific minimal build

### OCI Labels

Each image includes standard OCI labels:
- `org.opencontainers.image.version`: Build version (YYYYMMDD.HHMMSS)
- `org.opencontainers.image.created`: ISO 8601 timestamp
- `org.opencontainers.image.revision`: Git commit hash
- `org.opencontainers.image.source`: GitHub repository URL
- `variant`: cpu-full, cpu-min, gpu-full, or gpu-min

### Inspecting Image Metadata

View labels for an image:
```bash
docker inspect scottgal/mostlylucid-nmt:cpu | jq '.[0].Config.Labels'
```

## Verification

After building, verify the images:

```bash
# List all built images
docker images scottgal/mostlylucid-nmt

# Test an image
docker run --rm -p 8000:8000 scottgal/mostlylucid-nmt:cpu

# Check version endpoint
curl http://localhost:8000/model_name
```

## CI/CD Integration

### GitHub Actions Workflow

This repository includes a complete GitHub Actions workflow at `.github/workflows/docker.yml` that:
- Builds all 4 variants (cpu, cpu-min, gpu, gpu-min)
- Pushes to **ONE repository** (`scottgal/mostlylucid-nmt`) with different tags
- Creates version tags with datetime stamps
- Publishes to both Docker Hub and GitHub Container Registry

**Key features:**
- Matrix build strategy for parallel builds
- Automatic versioning with `YYYYMMDD.HHMMSS` format
- OCI labels with version, build date, and git commit
- Proper tag structure: `:cpu`, `:cpu-min`, `:gpu`, `:gpu-min`, `:latest`
- Version tags: `:cpu-20250108.143022`, `:gpu-20250108.143022`, etc.
- **Auto-sync Docker Hub README**: DOCKER_HUB.md automatically pushed to Docker Hub repository page

**Triggered on:**
- Push to `main` or `master` branch
- Version tags (`v*.*.*`)
- Pull requests (build only, no push)

See the workflow file for complete implementation details.

## Multi-Architecture Builds

**TL;DR**: Use `./build-all.sh --push` or `.\build-all.ps1 -Push` to build and push multi-platform images automatically.

The build scripts handle multi-architecture builds using Docker buildx:

### Automatic (Recommended)

**Linux/Mac**:
```bash
./build-all.sh --push
```

**Windows**:
```powershell
.\build-all.ps1 -Push
```

This creates multi-platform manifest lists for CPU variants that work on both AMD64 (x86_64) and ARM64 (Raspberry Pi, Apple Silicon).

### Manual Multi-Platform Build

If you need to build manually:

```bash
# Create and use buildx builder (one-time setup)
docker buildx create --name multiarch-builder --use
docker buildx inspect --bootstrap

# Build CPU variants for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t scottgal/mostlylucid-nmt:latest \
  -t scottgal/mostlylucid-nmt:cpu \
  -t scottgal/mostlylucid-nmt:cpu-${VERSION} \
  -f Dockerfile \
  --push \
  .

# Build GPU variant (AMD64 only - CUDA requirement)
docker buildx build \
  --platform linux/amd64 \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t scottgal/mostlylucid-nmt:gpu \
  -t scottgal/mostlylucid-nmt:gpu-${VERSION} \
  -f Dockerfile.gpu \
  --push \
  .
```

**Note**: Multi-platform builds with buildx require `--push` to a registry. You cannot use `--load` with multiple platforms.

## Troubleshooting

### Build fails with "No space left on device"

Clean up old images:
```bash
docker system prune -a
```

### Version already exists on Docker Hub

If you need to overwrite a version tag (not recommended for production):
```bash
docker push scottgal/mostlylucid-nmt:${VERSION} --force
```

### Images are too large (12GB for CPU, 17GB for GPU)

**Root causes:**
1. **PyTorch 2.x**: Modern PyTorch with CUDA 12.x is 5GB (vs 1GB for old PyTorch 1.8)
2. **Preloaded models**: Full variants preload 4-8 translation models (adds 4-6GB)
3. **Test dependencies**: pytest, pytest-cov add unnecessary weight

**Solutions (in order of impact):**

1. **Use `:min` variants** (60% smaller - most effective):
```bash
# 3-4GB instead of 10GB
docker pull scottgal/mostlylucid-nmt:cpu-min

# 6-8GB instead of 17GB
docker pull scottgal/mostlylucid-nmt:gpu-min
```

2. **Volume-map model cache** (no preloaded models baked into image):
```bash
# Models download once to ./models, persist across container rebuilds
docker run -v ./models:/models scottgal/mostlylucid-nmt:cpu-min
```

3. **Already implemented** (production builds now use `requirements-prod.txt`):
- Removed pytest, pytest-cov, pytest-asyncio, pytest-mock (~200MB saved)
- Using --no-cache-dir (100MB saved)

**Trade-off**: `:min` variants download models on first use (1-5 min per model), but overall much smaller footprint

### Image labels not showing on Docker Hub

Wait a few minutes after pushing - Docker Hub may cache the manifest. Clear your browser cache or use Docker CLI to inspect.

### Container shutdown shows "Worker was sent SIGKILL! Perhaps out of memory?"

**This is NORMAL and NOT an out-of-memory error.** This message appears when:

1. You stop the container (Ctrl+C or `docker stop`)
2. Gunicorn sends SIGTERM to workers
3. Workers have `GRACEFUL_TIMEOUT` seconds (default: 5) to finish in-flight requests
4. If workers don't exit within the timeout, Gunicorn sends SIGKILL to force shutdown
5. The "Perhaps out of memory?" message is misleading - it's just Gunicorn's default message for SIGKILL

**The container stops in ~5 seconds by design.** To make shutdown even faster:
```bash
# Reduce graceful timeout to 2 seconds
docker run -e GRACEFUL_TIMEOUT=2 scottgal/mostlylucid-nmt:gpu

# Or instant shutdown (not recommended for production)
docker run -e GRACEFUL_TIMEOUT=0 scottgal/mostlylucid-nmt:gpu
```

**Actual OOM errors** look different and show kernel messages like:
```
Out of memory: Killed process 1234 (gunicorn) total-vm:8GB
kernel: [12345.678] oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null)
```

## Best Practices

1. **Always use build scripts** for consistency
2. **Never overwrite version tags** - they should be immutable
3. **Test locally** before pushing to Docker Hub
4. **Document releases** - create GitHub releases for major versions
5. **Keep named tags updated** - `:latest`, `:cpu`, `:cpu-min`, `:gpu`, `:gpu-min` should always point to most recent stable build

---

# Performance Tuning and Deployment

## Default Performance Settings

All Docker images are configured with **"fast as possible" defaults** optimized for their respective hardware:

### GPU Containers (`:gpu`, `:gpu-min`)
- `WEB_CONCURRENCY=1` - Single Gunicorn worker (GPUs don't benefit from multiple workers)
- `MAX_INFLIGHT_TRANSLATIONS=1` - One translation at a time per GPU (matches 1 GPU = 1 slot)
- `EASYNMT_BATCH_SIZE=64` - Large batches maximize GPU throughput
- `EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'` - FP16 for 2x speed and 50% memory savings
- `MAX_CACHED_MODELS=10` - Cache multiple models in VRAM
- `ENABLE_QUEUE=1`, `MAX_QUEUE_SIZE=2000` - Queue requests to avoid 429 errors

**Multi-GPU Setup:**
Set `MAX_INFLIGHT_TRANSLATIONS` to the number of GPUs (e.g., 2 GPUs = 2 inflight)

### CPU Containers (`:latest`, `:min`)
- `WEB_CONCURRENCY=4` - Multiple workers to use all CPU cores
- `MAX_WORKERS_BACKEND=4` - Thread pool for parallel backend operations
- `MAX_INFLIGHT_TRANSLATIONS=4` - Higher concurrency for CPU parallelism
- `EASYNMT_BATCH_SIZE=16` - Smaller batches (CPUs handle smaller batches better)
- `MAX_CACHED_MODELS=5` - Less cache (CPU memory is shared with other processes)
- `ENABLE_QUEUE=1`, `MAX_QUEUE_SIZE=1000` - Queueing enabled

## Tuning for Different Scenarios

### Scenario 1: Maximum Throughput (Default)

**Goal**: Highest translations/second for batch processing

**GPU Settings (already default)**:
```bash
WEB_CONCURRENCY=1
MAX_INFLIGHT_TRANSLATIONS=1
EASYNMT_BATCH_SIZE=64  # Or higher (128, 256) if VRAM allows
EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'
```

**CPU Settings (already default)**:
```bash
WEB_CONCURRENCY=4  # Match CPU core count
MAX_WORKERS_BACKEND=4
MAX_INFLIGHT_TRANSLATIONS=4
EASYNMT_BATCH_SIZE=16
```

### Scenario 2: Low Latency (Interactive Applications)

**Goal**: Minimize response time for single requests

**Trade-off**: Lower overall throughput to reduce per-request latency

**GPU Settings**:
```bash
WEB_CONCURRENCY=1
MAX_INFLIGHT_TRANSLATIONS=1
EASYNMT_BATCH_SIZE=1  # Process immediately, don't wait for batching
EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'
MAX_CACHED_MODELS=3   # Preload most common models only
PRELOAD_MODELS="en->de,de->en,en->fr"  # Critical pairs
```

**CPU Settings**:
```bash
WEB_CONCURRENCY=2  # Fewer workers = less context switching
MAX_WORKERS_BACKEND=2
MAX_INFLIGHT_TRANSLATIONS=2
EASYNMT_BATCH_SIZE=1  # Single-item batches
```

### Scenario 3: High Concurrency, Lower Throughput

**Goal**: Handle many simultaneous users with acceptable (not optimal) speed per request

**Trade-off**: Increase `MAX_INFLIGHT_TRANSLATIONS` to allow more concurrent requests, but each request will be slower due to GPU/CPU contention

**GPU Settings**:
```bash
WEB_CONCURRENCY=1
MAX_INFLIGHT_TRANSLATIONS=4  # Allow 4 concurrent translations (they'll compete for GPU)
EASYNMT_BATCH_SIZE=32        # Smaller batches to reduce per-request latency
EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'
MAX_QUEUE_SIZE=5000          # Larger queue for bursts
```

**Why this reduces throughput**: Multiple translations compete for the GPU, causing context switching overhead and memory fragmentation. Each individual request will be slower, but more requests can run simultaneously.

**CPU Settings**:
```bash
WEB_CONCURRENCY=8            # More workers
MAX_WORKERS_BACKEND=8
MAX_INFLIGHT_TRANSLATIONS=8  # High concurrency
EASYNMT_BATCH_SIZE=8         # Smaller batches
```

### Scenario 4: Memory-Constrained GPU

**Goal**: Avoid OOM errors on smaller GPUs (e.g., <12GB VRAM)

**GPU Settings**:
```bash
WEB_CONCURRENCY=1
MAX_INFLIGHT_TRANSLATIONS=1
EASYNMT_BATCH_SIZE=16       # Smaller batches
EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'
MAX_CACHED_MODELS=3         # Fewer cached models
MODEL_FAMILY=mbart50        # Or m2m100 (single model vs many Opus-MT models)
```

## Docker Compose Example

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  translator-gpu:
    image: scottgal/mostlylucid-nmt:gpu
    ports:
      - "8000:8000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      # Defaults are optimized for max throughput (see above)
      # Override for specific scenarios:

      # For low latency:
      # EASYNMT_BATCH_SIZE: 1
      # MAX_CACHED_MODELS: 3
      # PRELOAD_MODELS: "en->de,de->en"

      # For high concurrency:
      # MAX_INFLIGHT_TRANSLATIONS: 4
      # EASYNMT_BATCH_SIZE: 32
      # MAX_QUEUE_SIZE: 5000

      # Model selection
      MODEL_FAMILY: opus-mt  # or mbart50, m2m100

    volumes:
      # Optional: persist model cache
      - ./model-cache:/app/models

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  translator-cpu:
    image: scottgal/mostlylucid-nmt:latest
    ports:
      - "8001:8000"
    environment:
      # CPU defaults are already optimized (WEB_CONCURRENCY=4, etc.)
      MODEL_FAMILY: opus-mt
    volumes:
      - ./model-cache-cpu:/app/models
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Run**:
```bash
docker-compose up -d
docker-compose logs -f
```

## Kubernetes Deployment

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mostlylucid-nmt-gpu
spec:
  replicas: 2  # Scale based on GPU availability
  selector:
    matchLabels:
      app: mostlylucid-nmt
      variant: gpu
  template:
    metadata:
      labels:
        app: mostlylucid-nmt
        variant: gpu
    spec:
      containers:
      - name: translator
        image: scottgal/mostlylucid-nmt:gpu
        ports:
        - containerPort: 8000
        env:
        - name: MODEL_FAMILY
          value: "opus-mt"
        # Defaults are optimal for GPU throughput
        # Override if needed:
        # - name: MAX_INFLIGHT_TRANSLATIONS
        #   value: "2"  # If using multi-GPU nodes
        # - name: EASYNMT_BATCH_SIZE
        #   value: "32"  # For high concurrency scenario
        resources:
          requests:
            memory: "8Gi"
            cpu: "4"
            nvidia.com/gpu: 1
          limits:
            memory: "16Gi"
            cpu: "8"
            nvidia.com/gpu: 1
        volumeMounts:
        - name: model-cache
          mountPath: /app/models
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /readyz
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: model-cache
        persistentVolumeClaim:
          claimName: model-cache-pvc
      nodeSelector:
        accelerator: nvidia-tesla-t4  # Or your GPU type

---
apiVersion: v1
kind: Service
metadata:
  name: mostlylucid-nmt-gpu
spec:
  selector:
    app: mostlylucid-nmt
    variant: gpu
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: model-cache-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
```

**Deploy**:
```bash
kubectl apply -f k8s-deployment.yaml
kubectl get pods -w
kubectl logs -f deployment/mostlylucid-nmt-gpu
```

## Azure Container Instances (ACI)

**CPU Instance**:
```bash
az container create \
  --resource-group myResourceGroup \
  --name mostlylucid-nmt \
  --image scottgal/mostlylucid-nmt:latest \
  --cpu 4 \
  --memory 8 \
  --ports 8000 \
  --environment-variables \
    MODEL_FAMILY=opus-mt \
    WEB_CONCURRENCY=4 \
  --dns-name-label mostlylucid-nmt
```

**GPU Instance (requires GPU-enabled regions)**:
```bash
az container create \
  --resource-group myResourceGroup \
  --name mostlylucid-nmt-gpu \
  --image scottgal/mostlylucid-nmt:gpu \
  --cpu 4 \
  --memory 16 \
  --gpu-count 1 \
  --gpu-sku V100 \
  --ports 8000 \
  --environment-variables \
    MODEL_FAMILY=mbart50 \
    EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  --dns-name-label mostlylucid-nmt-gpu
```

## Load Testing

Use the included k6 load test to find your optimal configuration:

```bash
# Install k6: https://k6.io/docs/get-started/installation/

# Smoke test (quick validation)
k6 run --vus 1 --duration 30s tests/k6-load-test.js

# Load test (find throughput limits)
k6 run --vus 10 --duration 2m tests/k6-load-test.js

# Stress test (push beyond limits)
k6 run --vus 50 --duration 5m tests/k6-load-test.js

# Custom BASE_URL
BASE_URL=http://my-server:8000 k6 run tests/k6-load-test.js
```

**Interpret Results**:
- `http_req_duration` p95 < 2s: Good latency for interactive use
- `http_req_duration` p95 < 10s: Acceptable for batch processing
- `http_req_failed` < 5%: Healthy error rate
- `http_reqs` (requests/sec): Your throughput capacity

**Tuning Based on Results**:
- **High p95 latency**: Reduce `EASYNMT_BATCH_SIZE` or `MAX_INFLIGHT_TRANSLATIONS`
- **Low throughput**: Increase `EASYNMT_BATCH_SIZE` (GPU) or `WEB_CONCURRENCY` (CPU)
- **Many 429 errors**: Increase `MAX_QUEUE_SIZE`
- **Many 503 errors**: Increase `MAX_INFLIGHT_TRANSLATIONS` or scale horizontally

## Monitoring Recommendations

**Essential Metrics**:
1. Request rate (req/s): Track via load balancer or APM
2. Response latency (p50, p95, p99): From load balancer or k6
3. Queue depth: `GET /cache` returns inflight/waiting counts
4. Error rate: 4xx, 5xx responses
5. GPU utilization: `nvidia-smi` or `dcgm-exporter` (K8s)
6. Memory usage: Container memory metrics

**Example Prometheus Query**:
```promql
# Request rate
rate(http_requests_total[5m])

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m])
```

## Common Configuration Patterns

### Pattern 1: Multi-GPU Node
```bash
# Node with 4 GPUs
MAX_INFLIGHT_TRANSLATIONS=4
EASYNMT_BATCH_SIZE=64
# Kubernetes: request 4 GPUs, set affinity to keep all on same node
```

### Pattern 2: Hybrid CPU/GPU Setup
```yaml
# docker-compose.yml
services:
  gpu-fast:
    image: scottgal/mostlylucid-nmt:gpu
    # Handle hot language pairs (en<->de, en<->fr)

  cpu-fallback:
    image: scottgal/mostlylucid-nmt:latest
    # Handle overflow and rare pairs
```

### Pattern 3: Model-Specific Instances
```yaml
# Opus-MT for quality
services:
  opus-mt:
    image: scottgal/mostlylucid-nmt:gpu
    environment:
      MODEL_FAMILY: opus-mt

# mBART50 for speed and 50 languages
services:
  mbart50:
    image: scottgal/mostlylucid-nmt:gpu
    environment:
      MODEL_FAMILY: mbart50
      MAX_CACHED_MODELS: 1  # Only one model needed
```

## Environment Variable Reference

See [README.md](README.md#configuration) for the complete list of 40+ configuration options.

**Key Performance Variables**:
- `WEB_CONCURRENCY`: Gunicorn workers (default: 1 GPU, 4 CPU)
- `MAX_INFLIGHT_TRANSLATIONS`: Concurrent translations (default: 1 GPU, 4 CPU)
- `EASYNMT_BATCH_SIZE`: Batch size for translation (default: 64 GPU, 16 CPU)
- `EASYNMT_MODEL_ARGS`: JSON dict for model init (default: `{"torch_dtype":"fp16"}` GPU, `{}` CPU)
- `MAX_CACHED_MODELS`: LRU cache size (default: 10 GPU, 5 CPU)
- `MAX_QUEUE_SIZE`: Max queued requests (default: 2000 GPU, 1000 CPU)
- `ENABLE_QUEUE`: Enable queueing (default: 1)
- `TRANSLATE_TIMEOUT_SEC`: Per-request timeout (default: 180)
- `MODEL_FAMILY`: Model family (`opus-mt`, `mbart50`, `m2m100`)
