#!/bin/bash
# Build all Docker image variants with proper versioning and multi-platform support
set -e

# Generate version string (datetime to the second)
VERSION=$(date -u +"%Y%m%d.%H%M%S")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Parse arguments
PUSH=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            PUSH=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--push]"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Multi-platform build for mostlylucid-nmt"
echo "Version: ${VERSION}"
echo "VCS ref: ${VCS_REF}"
echo "Build date: ${BUILD_DATE}"
echo "Push to Docker Hub: ${PUSH}"
echo "=========================================="
echo ""

# Docker repository - ONE repository with multiple tags
REPO="scottgal/mostlylucid-nmt"

# Ensure buildx is available and create/use builder
echo "Setting up Docker buildx..."
docker buildx create --name multiarch-builder --use 2>/dev/null || docker buildx use multiarch-builder
docker buildx inspect --bootstrap
echo ""

# Build CPU full image (multi-platform: AMD64 + ARM64)
echo "=========================================="
echo "Building CPU full (multi-platform)"
echo "Platforms: linux/amd64, linux/arm64"
echo "=========================================="

if [ "$PUSH" = true ]; then
    docker buildx build \
      --platform linux/amd64,linux/arm64 \
      --build-arg VERSION="${VERSION}" \
      --build-arg BUILD_DATE="${BUILD_DATE}" \
      --build-arg VCS_REF="${VCS_REF}" \
      -t "${REPO}:cpu" \
      -t "${REPO}:latest" \
      -t "${REPO}:cpu-${VERSION}" \
      -f Dockerfile \
      --push \
      .
    echo "Pushed ${REPO}:cpu (AMD64 + ARM64)"
    echo "Pushed ${REPO}:latest (AMD64 + ARM64)"
    echo "Pushed ${REPO}:cpu-${VERSION} (AMD64 + ARM64)"
else
    docker buildx build \
      --build-arg VERSION="${VERSION}" \
      --build-arg BUILD_DATE="${BUILD_DATE}" \
      --build-arg VCS_REF="${VCS_REF}" \
      -t "${REPO}:cpu" \
      -t "${REPO}:latest" \
      -t "${REPO}:cpu-${VERSION}" \
      -f Dockerfile \
      --load \
      .
    echo "Built ${REPO}:cpu (local platform only)"
    echo "Built ${REPO}:latest (local platform only)"
    echo "Built ${REPO}:cpu-${VERSION} (local platform only)"
fi

# Build CPU minimal image (multi-platform: AMD64 + ARM64)
echo ""
echo "=========================================="
echo "Building CPU minimal (multi-platform)"
echo "Platforms: linux/amd64, linux/arm64"
echo "=========================================="

if [ "$PUSH" = true ]; then
    docker buildx build \
      --platform linux/amd64,linux/arm64 \
      --build-arg VERSION="${VERSION}" \
      --build-arg BUILD_DATE="${BUILD_DATE}" \
      --build-arg VCS_REF="${VCS_REF}" \
      -t "${REPO}:cpu-min" \
      -t "${REPO}:cpu-min-${VERSION}" \
      -f Dockerfile.min \
      --push \
      .
    echo "Pushed ${REPO}:cpu-min (AMD64 + ARM64)"
    echo "Pushed ${REPO}:cpu-min-${VERSION} (AMD64 + ARM64)"
else
    docker buildx build \
      --build-arg VERSION="${VERSION}" \
      --build-arg BUILD_DATE="${BUILD_DATE}" \
      --build-arg VCS_REF="${VCS_REF}" \
      -t "${REPO}:cpu-min" \
      -t "${REPO}:cpu-min-${VERSION}" \
      -f Dockerfile.min \
      --load \
      .
    echo "Built ${REPO}:cpu-min (local platform only)"
    echo "Built ${REPO}:cpu-min-${VERSION} (local platform only)"
fi

# Build GPU full image (AMD64 only with CUDA)
echo ""
echo "=========================================="
echo "Building GPU full (AMD64 only)"
echo "Platform: linux/amd64 with CUDA"
echo "=========================================="

if [ "$PUSH" = true ]; then
    docker buildx build \
      --platform linux/amd64 \
      --build-arg VERSION="${VERSION}" \
      --build-arg BUILD_DATE="${BUILD_DATE}" \
      --build-arg VCS_REF="${VCS_REF}" \
      -t "${REPO}:gpu" \
      -t "${REPO}:gpu-${VERSION}" \
      -f Dockerfile.gpu \
      --push \
      .
    echo "Pushed ${REPO}:gpu (AMD64 with CUDA)"
    echo "Pushed ${REPO}:gpu-${VERSION} (AMD64 with CUDA)"
else
    docker buildx build \
      --platform linux/amd64 \
      --build-arg VERSION="${VERSION}" \
      --build-arg BUILD_DATE="${BUILD_DATE}" \
      --build-arg VCS_REF="${VCS_REF}" \
      -t "${REPO}:gpu" \
      -t "${REPO}:gpu-${VERSION}" \
      -f Dockerfile.gpu \
      --load \
      .
    echo "Built ${REPO}:gpu (AMD64 with CUDA)"
    echo "Built ${REPO}:gpu-${VERSION} (AMD64 with CUDA)"
fi

# Build GPU minimal image (AMD64 only with CUDA)
echo ""
echo "=========================================="
echo "Building GPU minimal (AMD64 only)"
echo "Platform: linux/amd64 with CUDA"
echo "=========================================="

if [ "$PUSH" = true ]; then
    docker buildx build \
      --platform linux/amd64 \
      --build-arg VERSION="${VERSION}" \
      --build-arg BUILD_DATE="${BUILD_DATE}" \
      --build-arg VCS_REF="${VCS_REF}" \
      -t "${REPO}:gpu-min" \
      -t "${REPO}:gpu-min-${VERSION}" \
      -f Dockerfile.gpu.min \
      --push \
      .
    echo "Pushed ${REPO}:gpu-min (AMD64 with CUDA)"
    echo "Pushed ${REPO}:gpu-min-${VERSION} (AMD64 with CUDA)"
else
    docker buildx build \
      --platform linux/amd64 \
      --build-arg VERSION="${VERSION}" \
      --build-arg BUILD_DATE="${BUILD_DATE}" \
      --build-arg VCS_REF="${VCS_REF}" \
      -t "${REPO}:gpu-min" \
      -t "${REPO}:gpu-min-${VERSION}" \
      -f Dockerfile.gpu.min \
      --load \
      .
    echo "Built ${REPO}:gpu-min (AMD64 with CUDA)"
    echo "Built ${REPO}:gpu-min-${VERSION} (AMD64 with CUDA)"
fi

echo ""
echo "=========================================="
echo "All builds completed successfully!"
echo "=========================================="
echo ""

if [ "$PUSH" = true ]; then
    echo "Images pushed to Docker Hub:"
    echo ""
    echo "CPU (multi-platform - auto-detects AMD64 or ARM64):"
    echo "  ${REPO}:latest"
    echo "  ${REPO}:cpu"
    echo "  ${REPO}:cpu-${VERSION}"
    echo "  ${REPO}:cpu-min"
    echo "  ${REPO}:cpu-min-${VERSION}"
    echo ""
    echo "GPU (AMD64 only with CUDA):"
    echo "  ${REPO}:gpu"
    echo "  ${REPO}:gpu-${VERSION}"
    echo "  ${REPO}:gpu-min"
    echo "  ${REPO}:gpu-min-${VERSION}"
    echo ""
    echo "Users can now pull and Docker will auto-select the right architecture:"
    echo "  docker pull ${REPO}:latest    # Gets AMD64 on PC, ARM64 on Raspberry Pi"
    echo "  docker pull ${REPO}:gpu        # Gets AMD64 with CUDA"
else
    echo "Images built locally (not pushed to Docker Hub):"
    echo ""
    echo "CPU images (local platform only):"
    echo "  ${REPO}:latest"
    echo "  ${REPO}:cpu"
    echo "  ${REPO}:cpu-${VERSION}"
    echo "  ${REPO}:cpu-min"
    echo "  ${REPO}:cpu-min-${VERSION}"
    echo ""
    echo "GPU images (local platform only):"
    echo "  ${REPO}:gpu"
    echo "  ${REPO}:gpu-${VERSION}"
    echo "  ${REPO}:gpu-min"
    echo "  ${REPO}:gpu-min-${VERSION}"
    echo ""
    echo "To build AND push multi-platform images to Docker Hub:"
    echo "  ./build-all.sh --push"
fi

echo ""
echo "Usage examples:"
echo "  # CPU on any platform (auto-detects architecture)"
echo "  docker run -p 8000:8000 ${REPO}:latest"
echo ""
echo "  # GPU on x86_64 with NVIDIA GPU"
echo "  docker run --gpus all -p 8000:8000 ${REPO}:gpu"
echo ""
