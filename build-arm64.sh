#!/bin/bash
# Build script for ARM64/Raspberry Pi
# Run this ON a Raspberry Pi or use buildx for cross-compilation

set -e

VERSION=$(date +%Y%m%d.%H%M%S)
IMAGE_NAME="mostlylucid-nmt"
DOCKER_HUB_REPO="scottgal/mostlylucid-nmt"
PLATFORM="linux/arm64"

echo "=========================================="
echo "Building ARM64 image for Raspberry Pi"
echo "Version: $VERSION"
echo "Platform: $PLATFORM"
echo "=========================================="

# Option 1: Build natively on Raspberry Pi
if [ "$(uname -m)" = "aarch64" ]; then
    echo "Building natively on ARM64..."
    docker build \
        -f Dockerfile.arm64 \
        -t ${IMAGE_NAME}:pi \
        -t ${IMAGE_NAME}:arm64 \
        -t ${IMAGE_NAME}:pi-${VERSION} \
        --build-arg VERSION=${VERSION} \
        .
else
    # Option 2: Cross-compile using buildx (requires Docker Desktop or buildx)
    echo "Cross-compiling for ARM64 using buildx..."

    # Create builder if it doesn't exist
    docker buildx create --name arm-builder --use 2>/dev/null || docker buildx use arm-builder

    # Build for ARM64
    docker buildx build \
        --platform ${PLATFORM} \
        -f Dockerfile.arm64 \
        -t ${IMAGE_NAME}:pi \
        -t ${IMAGE_NAME}:arm64 \
        -t ${IMAGE_NAME}:pi-${VERSION} \
        --build-arg VERSION=${VERSION} \
        --load \
        .
fi

echo ""
echo "=========================================="
echo "Build complete!"
echo "Images created:"
echo "  ${IMAGE_NAME}:pi"
echo "  ${IMAGE_NAME}:arm64"
echo "  ${IMAGE_NAME}:pi-${VERSION}"
echo "=========================================="
echo ""
echo "To run locally on Raspberry Pi:"
echo "  docker run -p 8000:8000 \\"
echo "    -v ./model-cache:/models \\"
echo "    -e MODEL_CACHE_DIR=/models \\"
echo "    ${IMAGE_NAME}:pi"
echo ""
echo "Or use docker-compose-arm64.yml:"
echo "  docker-compose -f docker-compose-arm64.yml up"
echo ""
echo "To push to Docker Hub:"
echo "  docker tag ${IMAGE_NAME}:pi ${DOCKER_HUB_REPO}:pi"
echo "  docker tag ${IMAGE_NAME}:pi ${DOCKER_HUB_REPO}:arm64"
echo "  docker tag ${IMAGE_NAME}:pi-${VERSION} ${DOCKER_HUB_REPO}:pi-${VERSION}"
echo "  docker push ${DOCKER_HUB_REPO}:pi"
echo "  docker push ${DOCKER_HUB_REPO}:arm64"
echo "  docker push ${DOCKER_HUB_REPO}:pi-${VERSION}"
echo ""
