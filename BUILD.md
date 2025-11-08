# Building and Publishing Docker Images

This guide explains how to build and publish all 4 Docker image variants with proper versioning.

## Image Variants

All variants are published to the same repository: `scottgal/mostlylucid-nmt`

| Tag | Dockerfile | Description | Size |
|-----|------------|-------------|------|
| `latest` | `Dockerfile` | CPU with preloaded models | ~2.5GB |
| `min` | `Dockerfile.min` | CPU minimal, no preloaded models | ~1.5GB |
| `gpu` | `Dockerfile.gpu` | GPU with CUDA 12.1 and preloaded models | ~5GB |
| `gpu-min` | `Dockerfile.gpu.min` | GPU minimal, no preloaded models | ~4GB |

## Automated Build (Recommended)

### Windows (PowerShell)

```powershell
.\build-all.ps1
```

### Linux/Mac (Bash)

```bash
chmod +x build-all.sh
./build-all.sh
```

These scripts will:
1. Generate a version string based on current datetime (YYYYMMDD.HHMMSS)
2. Get the current git commit hash
3. Build all 4 variants with proper labels
4. Tag each variant with both the named tag (latest, min, gpu, gpu-min) AND the version tag

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

For automated builds in CI/CD pipelines:

**GitHub Actions Example:**
```yaml
- name: Build and Push Docker Images
  run: |
    VERSION=$(date -u +"%Y%m%d.%H%M%S")
    BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    VCS_REF=${{ github.sha }}

    docker build \
      --build-arg VERSION="${VERSION}" \
      --build-arg BUILD_DATE="${BUILD_DATE}" \
      --build-arg VCS_REF="${VCS_REF}" \
      -t scottgal/mostlylucid-nmt:cpu \
      -t scottgal/mostlylucid-nmt:latest \
      -t scottgal/mostlylucid-nmt:cpu-${VERSION} \
      .

    docker push scottgal/mostlylucid-nmt --all-tags
```

## Multi-Architecture Builds

To build for multiple architectures (amd64, arm64):

```bash
# Create and use buildx builder
docker buildx create --use

# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t scottgal/mostlylucid-nmt:cpu \
  -t scottgal/mostlylucid-nmt:latest \
  -t scottgal/mostlylucid-nmt:cpu-${VERSION} \
  --push \
  .
```

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

### Image labels not showing on Docker Hub

Wait a few minutes after pushing - Docker Hub may cache the manifest. Clear your browser cache or use Docker CLI to inspect.

## Best Practices

1. **Always use build scripts** for consistency
2. **Never overwrite version tags** - they should be immutable
3. **Test locally** before pushing to Docker Hub
4. **Document releases** - create GitHub releases for major versions
5. **Keep named tags updated** - `latest`, `min`, `gpu`, `gpu-min` should always point to most recent stable build
