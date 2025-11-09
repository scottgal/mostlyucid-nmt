# Build all Docker image variants with proper versioning and multi-platform support
# PowerShell script for Windows
#
# Usage:
#   .\build-all.ps1           # Build locally (single platform)
#   .\build-all.ps1 -Push     # Build and push multi-platform images to Docker Hub
#
# RAPID LOCAL TESTING:
#   For fastest iteration, build ONLY the minimal variants (skip model downloads):
#
#   Just CPU minimal (30 seconds):
#     docker build -f Dockerfile.min -t dev:latest .
#
#   Just GPU minimal (30 seconds):
#     docker build -f Dockerfile.gpu.min -t dev:gpu .

param(
    [switch]$Push = $false
)

# Generate version string (datetime to the second)
$now = (Get-Date).ToUniversalTime()
$VERSION = $now.ToString("yyyyMMdd.HHmmss")
$BUILD_DATE = $now.ToString("yyyy-MM-ddTHH:mm:ssZ")
try {
    $VCS_REF = (git rev-parse --short HEAD 2>$null)
    if (-not $VCS_REF) { $VCS_REF = "unknown" }
} catch {
    $VCS_REF = "unknown"
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Multi-platform build for mostlylucid-nmt" -ForegroundColor Cyan
Write-Host "Version: $VERSION" -ForegroundColor Cyan
Write-Host "VCS ref: $VCS_REF" -ForegroundColor Cyan
Write-Host "Build date: $BUILD_DATE" -ForegroundColor Cyan
Write-Host "Push to Docker Hub: $Push" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Docker repository - ONE repository with multiple tags
$REPO = "scottgal/mostlylucid-nmt"

# Ensure buildx is available and create/use builder
Write-Host "Setting up Docker buildx..." -ForegroundColor Yellow
docker buildx create --name multiarch-builder --use 2>$null
if ($LASTEXITCODE -ne 0) {
    docker buildx use multiarch-builder
}
docker buildx inspect --bootstrap
Write-Host ""

# Build CPU full image (multi-platform: AMD64 + ARM64)
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Building CPU full (multi-platform)" -ForegroundColor Yellow
Write-Host "Platforms: linux/amd64, linux/arm64" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow

if ($Push) {
    docker buildx build `
      --platform linux/amd64,linux/arm64 `
      --build-arg VERSION="$VERSION" `
      --build-arg BUILD_DATE="$BUILD_DATE" `
      --build-arg VCS_REF="$VCS_REF" `
      -t "${REPO}:cpu" `
      -t "${REPO}:latest" `
      -t "${REPO}:cpu-${VERSION}" `
      -f Dockerfile `
      --push `
      .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Pushed ${REPO}:cpu (AMD64 + ARM64)" -ForegroundColor Green
    Write-Host "Pushed ${REPO}:latest (AMD64 + ARM64)" -ForegroundColor Green
    Write-Host "Pushed ${REPO}:cpu-${VERSION} (AMD64 + ARM64)" -ForegroundColor Green
} else {
    docker buildx build `
      --build-arg VERSION="$VERSION" `
      --build-arg BUILD_DATE="$BUILD_DATE" `
      --build-arg VCS_REF="$VCS_REF" `
      -t "${REPO}:cpu" `
      -t "${REPO}:latest" `
      -t "${REPO}:cpu-${VERSION}" `
      -f Dockerfile `
      --load `
      .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Built ${REPO}:cpu (local platform only)" -ForegroundColor Green
    Write-Host "Built ${REPO}:latest (local platform only)" -ForegroundColor Green
    Write-Host "Built ${REPO}:cpu-${VERSION} (local platform only)" -ForegroundColor Green
}

# Build CPU minimal image (multi-platform: AMD64 + ARM64)
Write-Host ""
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Building CPU minimal (multi-platform)" -ForegroundColor Yellow
Write-Host "Platforms: linux/amd64, linux/arm64" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow

if ($Push) {
    docker buildx build `
      --platform linux/amd64,linux/arm64 `
      --build-arg VERSION="$VERSION" `
      --build-arg BUILD_DATE="$BUILD_DATE" `
      --build-arg VCS_REF="$VCS_REF" `
      -t "${REPO}:cpu-min" `
      -t "${REPO}:cpu-min-${VERSION}" `
      -f Dockerfile.min `
      --push `
      .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Pushed ${REPO}:cpu-min (AMD64 + ARM64)" -ForegroundColor Green
    Write-Host "Pushed ${REPO}:cpu-min-${VERSION} (AMD64 + ARM64)" -ForegroundColor Green
} else {
    docker buildx build `
      --build-arg VERSION="$VERSION" `
      --build-arg BUILD_DATE="$BUILD_DATE" `
      --build-arg VCS_REF="$VCS_REF" `
      -t "${REPO}:cpu-min" `
      -t "${REPO}:cpu-min-${VERSION}" `
      -f Dockerfile.min `
      --load `
      .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Built ${REPO}:cpu-min (local platform only)" -ForegroundColor Green
    Write-Host "Built ${REPO}:cpu-min-${VERSION} (local platform only)" -ForegroundColor Green
}

# Build GPU full image (AMD64 only with CUDA)
Write-Host ""
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Building GPU full (AMD64 only)" -ForegroundColor Yellow
Write-Host "Platform: linux/amd64 with CUDA" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow

if ($Push) {
    docker buildx build `
      --platform linux/amd64 `
      --build-arg VERSION="$VERSION" `
      --build-arg BUILD_DATE="$BUILD_DATE" `
      --build-arg VCS_REF="$VCS_REF" `
      -t "${REPO}:gpu" `
      -t "${REPO}:gpu-${VERSION}" `
      -f Dockerfile.gpu `
      --push `
      .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Pushed ${REPO}:gpu (AMD64 with CUDA)" -ForegroundColor Green
    Write-Host "Pushed ${REPO}:gpu-${VERSION} (AMD64 with CUDA)" -ForegroundColor Green
} else {
    docker buildx build `
      --platform linux/amd64 `
      --build-arg VERSION="$VERSION" `
      --build-arg BUILD_DATE="$BUILD_DATE" `
      --build-arg VCS_REF="$VCS_REF" `
      -t "${REPO}:gpu" `
      -t "${REPO}:gpu-${VERSION}" `
      -f Dockerfile.gpu `
      --load `
      .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Built ${REPO}:gpu (AMD64 with CUDA)" -ForegroundColor Green
    Write-Host "Built ${REPO}:gpu-${VERSION} (AMD64 with CUDA)" -ForegroundColor Green
}

# Build GPU minimal image (AMD64 only with CUDA)
Write-Host ""
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Building GPU minimal (AMD64 only)" -ForegroundColor Yellow
Write-Host "Platform: linux/amd64 with CUDA" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow

if ($Push) {
    docker buildx build `
      --platform linux/amd64 `
      --build-arg VERSION="$VERSION" `
      --build-arg BUILD_DATE="$BUILD_DATE" `
      --build-arg VCS_REF="$VCS_REF" `
      -t "${REPO}:gpu-min" `
      -t "${REPO}:gpu-min-${VERSION}" `
      -f Dockerfile.gpu.min `
      --push `
      .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Pushed ${REPO}:gpu-min (AMD64 with CUDA)" -ForegroundColor Green
    Write-Host "Pushed ${REPO}:gpu-min-${VERSION} (AMD64 with CUDA)" -ForegroundColor Green
} else {
    docker buildx build `
      --platform linux/amd64 `
      --build-arg VERSION="$VERSION" `
      --build-arg BUILD_DATE="$BUILD_DATE" `
      --build-arg VCS_REF="$VCS_REF" `
      -t "${REPO}:gpu-min" `
      -t "${REPO}:gpu-min-${VERSION}" `
      -f Dockerfile.gpu.min `
      --load `
      .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Built ${REPO}:gpu-min (AMD64 with CUDA)" -ForegroundColor Green
    Write-Host "Built ${REPO}:gpu-min-${VERSION} (AMD64 with CUDA)" -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "All builds completed successfully!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

if ($Push) {
    Write-Host "Images pushed to Docker Hub:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "CPU (multi-platform - auto-detects AMD64 or ARM64):"
    Write-Host "  ${REPO}:latest"
    Write-Host "  ${REPO}:cpu"
    Write-Host "  ${REPO}:cpu-${VERSION}"
    Write-Host "  ${REPO}:cpu-min"
    Write-Host "  ${REPO}:cpu-min-${VERSION}"
    Write-Host ""
    Write-Host "GPU (AMD64 only with CUDA):"
    Write-Host "  ${REPO}:gpu"
    Write-Host "  ${REPO}:gpu-${VERSION}"
    Write-Host "  ${REPO}:gpu-min"
    Write-Host "  ${REPO}:gpu-min-${VERSION}"
    Write-Host ""
    Write-Host "Users can now pull and Docker will auto-select the right architecture:" -ForegroundColor Cyan
    Write-Host "  docker pull ${REPO}:latest    # Gets AMD64 on PC, ARM64 on Raspberry Pi"
    Write-Host "  docker pull ${REPO}:gpu        # Gets AMD64 with CUDA"
} else {
    Write-Host "Images built locally (not pushed to Docker Hub):" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "CPU images (local platform only):"
    Write-Host "  ${REPO}:latest"
    Write-Host "  ${REPO}:cpu"
    Write-Host "  ${REPO}:cpu-${VERSION}"
    Write-Host "  ${REPO}:cpu-min"
    Write-Host "  ${REPO}:cpu-min-${VERSION}"
    Write-Host ""
    Write-Host "GPU images (local platform only):"
    Write-Host "  ${REPO}:gpu"
    Write-Host "  ${REPO}:gpu-${VERSION}"
    Write-Host "  ${REPO}:gpu-min"
    Write-Host "  ${REPO}:gpu-min-${VERSION}"
    Write-Host ""
    Write-Host "To build AND push multi-platform images to Docker Hub:" -ForegroundColor Cyan
    Write-Host "  .\build-all.ps1 -Push"
}

Write-Host ""
Write-Host "Usage examples:" -ForegroundColor Cyan
Write-Host "  # CPU on any platform (auto-detects architecture)"
Write-Host "  docker run -p 8000:8000 ${REPO}:latest"
Write-Host ""
Write-Host "  # GPU on x86_64 with NVIDIA GPU"
Write-Host "  docker run --gpus all -p 8000:8000 ${REPO}:gpu"
Write-Host ""
