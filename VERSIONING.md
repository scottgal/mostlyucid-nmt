# Docker Image Versioning Guide

## Overview

All 4 Docker image variants (`latest`, `min`, `gpu`, `gpu-min`) now include proper versioning with OCI labels and datetime-based version tags.

## Version Format

**Format**: `YYYYMMDD.HHMMSS` (UTC)

**Example**: `20250108.143022` = January 8, 2025 at 14:30:22 UTC

## Tag Strategy

Each build creates **two tags per variant**:

### Named Tags (Mutable)
These always point to the most recent build:
- `scottgal/mostlylucid-nmt:cpu` (also aliased as `:latest`)
- `scottgal/mostlylucid-nmt:cpu-min`
- `scottgal/mostlylucid-nmt:gpu`
- `scottgal/mostlylucid-nmt:gpu-min`

### Version Tags (Immutable)
These are permanent snapshots:
- `scottgal/mostlylucid-nmt:cpu-20250108.143022`
- `scottgal/mostlylucid-nmt:cpu-min-20250108.143022`
- `scottgal/mostlylucid-nmt:gpu-20250108.143022`
- `scottgal/mostlylucid-nmt:gpu-min-20250108.143022`

## OCI Labels

Every image includes these labels:

```json
{
  "org.opencontainers.image.title": "mostlylucid-nmt",
  "org.opencontainers.image.description": "FastAPI neural machine translation service - [variant]",
  "org.opencontainers.image.version": "20250108.143022",
  "org.opencontainers.image.created": "2025-01-08T14:30:22Z",
  "org.opencontainers.image.source": "https://github.com/scottgal/mostlylucid-nmt",
  "org.opencontainers.image.revision": "abc1234",
  "org.opencontainers.image.vendor": "scottgal",
  "org.opencontainers.image.licenses": "MIT",
  "org.opencontainers.image.documentation": "https://github.com/scottgal/mostlylucid-nmt/blob/main/README.md",
  "variant": "cpu-full|cpu-min|gpu-full|gpu-min"
}
```

## Inspecting Versions

### Check Image Version
```bash
docker inspect scottgal/mostlylucid-nmt:cpu | jq '.[0].Config.Labels."org.opencontainers.image.version"'
```

### Check All Labels
```bash
docker inspect scottgal/mostlylucid-nmt:cpu | jq '.[0].Config.Labels'
```

### List All Available Tags
```bash
docker search scottgal/mostlylucid-nmt --limit 25
```

Or visit: https://hub.docker.com/r/scottgal/mostlylucid-nmt/tags

## Usage Examples

### Development (Always Latest)
```bash
docker pull scottgal/mostlylucid-nmt:cpu
docker run -p 8000:8000 scottgal/mostlylucid-nmt:cpu
```

### Production (Pinned Version)
```bash
# Pin to specific tested version
docker pull scottgal/mostlylucid-nmt:cpu-20250108.143022
docker run -p 8000:8000 scottgal/mostlylucid-nmt:cpu-20250108.143022
```

### Docker Compose (Pinned)
```yaml
version: '3.8'
services:
  translator:
    image: scottgal/mostlylucid-nmt:20250108.143022
    ports:
      - "8000:8000"
    environment:
      - USE_GPU=false
```

### Kubernetes (Pinned)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mostlylucid-nmt
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: translator
        image: scottgal/mostlylucid-nmt:cpu-20250108.143022
        imagePullPolicy: IfNotPresent
```

## Building with Versions

### Automated Build Scripts

**Windows:**
```powershell
.\build-all.ps1
```

**Linux/Mac:**
```bash
./build-all.sh
```

These scripts automatically:
1. Generate version string from current datetime
2. Get git commit hash
3. Build all 4 variants
4. Tag with both named and version tags

### Manual Build

```bash
# Set version variables
VERSION=$(date -u +"%Y%m%d.%H%M%S")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VCS_REF=$(git rev-parse --short HEAD)

# Build with version
docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t scottgal/mostlylucid-nmt:cpu \
  -t scottgal/mostlylucid-nmt:latest \
  -t scottgal/mostlylucid-nmt:cpu-${VERSION} \
  .
```

## Publishing

### Login
```bash
docker login
```

### Push Named Tags (Updates Latest)
```bash
docker push scottgal/mostlylucid-nmt:cpu
docker push scottgal/mostlylucid-nmt:latest
docker push scottgal/mostlylucid-nmt:cpu-min
docker push scottgal/mostlylucid-nmt:gpu
docker push scottgal/mostlylucid-nmt:gpu-min
```

### Push Version Tags (Permanent Snapshots)
```bash
docker push scottgal/mostlylucid-nmt:cpu-20250108.143022
docker push scottgal/mostlylucid-nmt:cpu-min-20250108.143022
docker push scottgal/mostlylucid-nmt:gpu-20250108.143022
docker push scottgal/mostlylucid-nmt:gpu-min-20250108.143022
```

### Push All Tags
```bash
docker push scottgal/mostlylucid-nmt --all-tags
```

## Version Lifecycle

### Development Workflow
1. Make code changes
2. Run `build-all.ps1` (creates new version)
3. Test locally with version tag
4. Push both named and version tags
5. Named tags (`latest`) now point to new version
6. Old version tags remain available

### Production Workflow
1. Pull specific version: `docker pull scottgal/mostlylucid-nmt:20250108.143022`
2. Test thoroughly
3. Deploy to production using version tag
4. Update infrastructure code to reference new version
5. Rollback is simple: redeploy old version tag

## Best Practices

### ✅ DO
- **Pin versions in production** for reproducibility
- **Use named tags in development** to always get latest
- **Keep version tags immutable** - never overwrite
- **Document which versions are deployed** in each environment
- **Test version tags locally** before pushing to Docker Hub

### ❌ DON'T
- **Don't use `latest` in production** - it's not reproducible
- **Don't overwrite version tags** - breaks reproducibility
- **Don't skip versioning** - always use build scripts
- **Don't forget to push version tags** - they're the permanent record

## Troubleshooting

### Version Not Showing on Docker Hub
Wait a few minutes for Docker Hub to update. Clear browser cache or use CLI:
```bash
docker pull scottgal/mostlylucid-nmt:20250108.143022
```

### Wrong Version in Labels
Ensure you passed `--build-arg VERSION=...` during build. Rebuild if necessary.

### Can't Find Old Version
Check Docker Hub tags page: https://hub.docker.com/r/scottgal/mostlylucid-nmt/tags

If deleted, it's gone forever (this is why we don't overwrite).

## See Also

- [BUILD.md](BUILD.md) - Detailed build instructions
- [README.md](README.md) - Full documentation
- [DOCKER_HUB.md](DOCKER_HUB.md) - Docker Hub overview
