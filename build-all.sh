#!/bin/bash
# Build all Docker image variants with proper versioning
set -e

# Generate version string (datetime to the second)
VERSION=$(date -u +"%Y%m%d.%H%M%S")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo "Building all variants with version: ${VERSION}"
echo "VCS ref: ${VCS_REF}"
echo "Build date: ${BUILD_DATE}"
echo ""

# Docker repository - ONE repository with multiple tags
REPO="scottgal/mostlylucid-nmt"

# Build CPU full image (cpu and latest tags)
echo "Building ${REPO}:cpu (CPU full)..."
docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t "${REPO}:cpu" \
  -t "${REPO}:latest" \
  -t "${REPO}:cpu-${VERSION}" \
  -f Dockerfile \
  .

# Build CPU minimal image (cpu-min tag)
echo ""
echo "Building ${REPO}:cpu-min (CPU minimal)..."
docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t "${REPO}:cpu-min" \
  -t "${REPO}:cpu-min-${VERSION}" \
  -f Dockerfile.min \
  .

# Build GPU full image (gpu tag)
echo ""
echo "Building ${REPO}:gpu (GPU full)..."
docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t "${REPO}:gpu" \
  -t "${REPO}:gpu-${VERSION}" \
  -f Dockerfile.gpu \
  .

# Build GPU minimal image (gpu-min tag)
echo ""
echo "Building ${REPO}:gpu-min (GPU minimal)..."
docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t "${REPO}:gpu-min" \
  -t "${REPO}:gpu-min-${VERSION}" \
  -f Dockerfile.gpu.min \
  .

echo ""
echo "✓ All builds completed successfully!"
echo ""
echo "Images built (all in ONE repository with different tags):"
echo "  ${REPO}:cpu (also tagged as :latest and :cpu-${VERSION})"
echo "  ${REPO}:cpu-min (also tagged as :cpu-min-${VERSION})"
echo "  ${REPO}:gpu (also tagged as :gpu-${VERSION})"
echo "  ${REPO}:gpu-min (also tagged as :gpu-min-${VERSION})"
echo ""
echo "To push to Docker Hub:"
echo "  docker push ${REPO}:cpu"
echo "  docker push ${REPO}:latest"
echo "  docker push ${REPO}:cpu-${VERSION}"
echo "  docker push ${REPO}:cpu-min"
echo "  docker push ${REPO}:cpu-min-${VERSION}"
echo "  docker push ${REPO}:gpu"
echo "  docker push ${REPO}:gpu-${VERSION}"
echo "  docker push ${REPO}:gpu-min"
echo "  docker push ${REPO}:gpu-min-${VERSION}"
echo ""
echo "Or push all tags at once:"
echo "  docker push ${REPO} --all-tags"
