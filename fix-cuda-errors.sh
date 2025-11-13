#!/bin/bash
# fix-cuda-errors.sh - Resolve CUDA device-side assertion errors
# Run this script with: chmod +x fix-cuda-errors.sh && ./fix-cuda-errors.sh

set -e

echo "=== MostlyLucid NMT CUDA Error Fix ==="
echo ""

# Step 1: Stop all containers
echo "[1/6] Stopping all Docker containers..."
docker stop $(docker ps -aq) 2>/dev/null || true
echo "      ✓ Done."

# Step 2: Clear GPU memory
echo "[2/6] Clearing GPU memory..."
sudo nvidia-smi --gpu-reset 2>/dev/null || {
    echo "      ⚠ Warning: GPU reset failed (may require sudo)"
    echo "      Continuing anyway..."
}
echo "      ✓ Done."

# Step 3: Prune Docker build cache
echo "[3/6] Pruning Docker build cache..."
docker builder prune -af
echo "      ✓ Done."

# Step 4: Remove old images
echo "[4/6] Removing old mostlylucid-nmt images..."
docker images | grep mostlylucid-nmt | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true
echo "      ✓ Done."

# Step 5: Rebuild with updated Dockerfile
echo "[5/6] Rebuilding Docker image with CUDA debugging enabled..."
docker build -f Dockerfile.gpu -t mostlylucid-nmt:gpu \
    --build-arg PRELOAD_PAIRS="en->de,de->en" \
    --progress=plain \
    .

echo "      ✓ Done."

# Step 6: Test with CUDA debugging
echo "[6/6] Testing with CUDA_LAUNCH_BLOCKING=1 for detailed errors..."
echo ""
echo "      Starting container with debugging enabled..."
echo "      Container logs will appear below."
echo "      Press Ctrl+C to stop when you see errors or success."
echo ""

docker run --rm --gpus all \
    -e USE_GPU=true \
    -e CUDA_LAUNCH_BLOCKING=1 \
    -e TORCH_USE_CUDA_DSA=1 \
    -e MODEL_FAMILY=opus-mt \
    -e PRELOAD_MODELS="en->de" \
    -e LOG_LEVEL=DEBUG \
    -p 8000:8000 \
    mostlylucid-nmt:gpu

echo ""
echo "=== Fix Complete ==="
echo ""
echo "If you still see CUDA errors, try:"
echo "  1. Run on CPU: docker run -e USE_GPU=false -p 8000:8000 mostlylucid-nmt:gpu"
echo "  2. Update NVIDIA drivers: https://www.nvidia.com/Download/index.aspx"
echo "  3. Check Docker GPU support: docker run --rm --gpus all nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi"
