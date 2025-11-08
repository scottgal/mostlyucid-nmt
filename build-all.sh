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

# Docker repository
REPO="scottgal/mostlylucid-nmt"

# Build CPU full image (latest)
echo "Building ${REPO}:latest (CPU full)..."
docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t "${REPO}:latest" \
  -t "${REPO}:${VERSION}" \
  -f Dockerfile \
  .

# Build CPU minimal image
echo ""
echo "Building ${REPO}:min (CPU minimal)..."
docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t "${REPO}:min" \
  -t "${REPO}:min-${VERSION}" \
  -f Dockerfile.min \
  .

# Build GPU full image
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

# Build GPU minimal image
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
echo "Images built:"
echo "  ${REPO}:latest (and ${VERSION})"
echo "  ${REPO}:min (and min-${VERSION})"
echo "  ${REPO}:gpu (and gpu-${VERSION})"
echo "  ${REPO}:gpu-min (and gpu-min-${VERSION})"
echo ""
echo "To push to Docker Hub:"
echo "  docker push ${REPO}:latest"
echo "  docker push ${REPO}:${VERSION}"
echo "  docker push ${REPO}:min"
echo "  docker push ${REPO}:min-${VERSION}"
echo "  docker push ${REPO}:gpu"
echo "  docker push ${REPO}:gpu-${VERSION}"
echo "  docker push ${REPO}:gpu-min"
echo "  docker push ${REPO}:gpu-min-${VERSION}"
echo ""
echo "Or push all at once:"
echo "  docker push ${REPO} --all-tags"
