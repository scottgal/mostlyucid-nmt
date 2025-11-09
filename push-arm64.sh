#!/bin/bash
# Build and push ARM64 image to Docker Hub
# This script builds for ARM64 and immediately pushes to registry

set -e

# Check if logged into Docker Hub
echo "Checking Docker Hub authentication..."
if ! docker info &>/dev/null; then
    echo "ERROR: Docker is not running"
    exit 1
fi

# Generate version timestamp
VERSION=$(date -u +"%Y%m%d.%H%M%S")
IMAGE_NAME="mostlylucid-nmt"
DOCKER_HUB_REPO="scottgal/mostlylucid-nmt"
PLATFORM="linux/arm64"

echo "=========================================="
echo "Building and Pushing ARM64 to Docker Hub"
echo "Version: $VERSION"
echo "Platform: $PLATFORM"
echo "Repository: $DOCKER_HUB_REPO"
echo "=========================================="
echo ""

# Ensure buildx builder exists
echo "Setting up buildx builder..."
docker buildx create --name arm-builder --use 2>/dev/null || docker buildx use arm-builder
docker buildx inspect --bootstrap
echo ""

# Build and push ARM64 image
echo "=========================================="
echo "Building and pushing ARM64 image..."
echo "This will take several minutes..."
echo "=========================================="
echo ""

docker buildx build \
    --platform ${PLATFORM} \
    -f Dockerfile.arm64 \
    -t ${DOCKER_HUB_REPO}:pi \
    -t ${DOCKER_HUB_REPO}:arm64 \
    -t ${DOCKER_HUB_REPO}:pi-${VERSION} \
    --build-arg VERSION=${VERSION} \
    --push \
    .

if [ $? -ne 0 ]; then
    echo ""
    echo "=========================================="
    echo "Build and push FAILED!"
    echo "=========================================="
    echo ""
    echo "Common issues:"
    echo "1. Not logged into Docker Hub - run: docker login"
    echo "2. No internet connection"
    echo "3. Docker daemon not running"
    echo ""
    exit 1
fi

echo ""
echo "=========================================="
echo "Build and push complete!"
echo "=========================================="
echo ""
echo "Images pushed to Docker Hub:"
echo "  ${DOCKER_HUB_REPO}:pi"
echo "  ${DOCKER_HUB_REPO}:arm64"
echo "  ${DOCKER_HUB_REPO}:pi-${VERSION}"
echo ""
echo "Verify with:"
echo "  docker buildx imagetools inspect ${DOCKER_HUB_REPO}:pi"
echo ""
echo "Test on Raspberry Pi:"
echo "  docker pull ${DOCKER_HUB_REPO}:pi"
echo "  docker run -p 8000:8000 -v ./model-cache:/models ${DOCKER_HUB_REPO}:pi"
echo ""
