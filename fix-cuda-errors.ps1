# fix-cuda-errors.ps1 - Resolve CUDA device-side assertion errors
# Run this script in PowerShell as Administrator

Write-Host "=== MostlyLucid NMT CUDA Error Fix ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop all containers
Write-Host "[1/6] Stopping all Docker containers..." -ForegroundColor Yellow
docker stop $(docker ps -aq) 2>$null
Write-Host "      Done." -ForegroundColor Green

# Step 2: Clear GPU memory
Write-Host "[2/6] Clearing GPU memory..." -ForegroundColor Yellow
nvidia-smi --gpu-reset 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      Warning: GPU reset failed (may require admin privileges)" -ForegroundColor Red
    Write-Host "      Continuing anyway..." -ForegroundColor Yellow
} else {
    Write-Host "      Done." -ForegroundColor Green
}

# Step 3: Prune Docker build cache
Write-Host "[3/6] Pruning Docker build cache..." -ForegroundColor Yellow
docker builder prune -af
Write-Host "      Done." -ForegroundColor Green

# Step 4: Remove old images
Write-Host "[4/6] Removing old mostlylucid-nmt images..." -ForegroundColor Yellow
docker images | Select-String "mostlylucid-nmt" | ForEach-Object {
    $imageId = ($_ -split '\s+')[2]
    docker rmi -f $imageId 2>$null
}
Write-Host "      Done." -ForegroundColor Green

# Step 5: Rebuild with updated Dockerfile
Write-Host "[5/6] Rebuilding Docker image with CUDA debugging enabled..." -ForegroundColor Yellow
docker build -f Dockerfile.gpu -t mostlylucid-nmt:gpu `
    --build-arg PRELOAD_PAIRS="en->de,de->en" `
    --progress=plain `
    .

if ($LASTEXITCODE -ne 0) {
    Write-Host "      Build failed! Check output above." -ForegroundColor Red
    exit 1
}
Write-Host "      Done." -ForegroundColor Green

# Step 6: Test with CUDA debugging
Write-Host "[6/6] Testing with CUDA_LAUNCH_BLOCKING=1 for detailed errors..." -ForegroundColor Yellow
Write-Host ""
Write-Host "      Starting container with debugging enabled..." -ForegroundColor Cyan
Write-Host "      Container logs will appear below." -ForegroundColor Cyan
Write-Host "      Press Ctrl+C to stop when you see errors or success." -ForegroundColor Cyan
Write-Host ""

docker run --rm --gpus all `
    -e USE_GPU=true `
    -e CUDA_LAUNCH_BLOCKING=1 `
    -e TORCH_USE_CUDA_DSA=1 `
    -e MODEL_FAMILY=opus-mt `
    -e PRELOAD_MODELS="en->de" `
    -e LOG_LEVEL=DEBUG `
    -p 8000:8000 `
    mostlylucid-nmt:gpu

Write-Host ""
Write-Host "=== Fix Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "If you still see CUDA errors, try:" -ForegroundColor Yellow
Write-Host "  1. Run on CPU: docker run -e USE_GPU=false -p 8000:8000 mostlylucid-nmt:gpu" -ForegroundColor White
Write-Host "  2. Update NVIDIA drivers: https://www.nvidia.com/Download/index.aspx" -ForegroundColor White
Write-Host "  3. Check Docker GPU support: docker run --rm --gpus all nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi" -ForegroundColor White
