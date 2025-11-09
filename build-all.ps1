# Build all Docker image variants with proper versioning
# PowerShell script for Windows
#
# RAPID LOCAL TESTING:
#   For fastest iteration, build ONLY the minimal variants (skip model downloads):
#
#   Just CPU minimal (30 seconds):
#     docker build -f Dockerfile.min -t dev:latest .
#
#   Just GPU minimal (30 seconds):
#     docker build -f Dockerfile.gpu.min -t dev:gpu .
#
#   Build only minimal variants from this script:
#     Comment out the "full" builds below (CPU full and GPU full sections)
#
# FULL BUILD (production):
#   Run this script as-is to build all 4 variants (~20-30 minutes total)
#

# Generate version string (datetime to the second)
$VERSION = (Get-Date).ToUniversalTime().ToString("yyyyMMdd.HHmmss")
$BUILD_DATE = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
try {
    $VCS_REF = (git rev-parse --short HEAD 2>$null)
} catch {
    $VCS_REF = "unknown"
}

Write-Host "Building all variants with version: $VERSION" -ForegroundColor Cyan
Write-Host "VCS ref: $VCS_REF" -ForegroundColor Cyan
Write-Host "Build date: $BUILD_DATE" -ForegroundColor Cyan
Write-Host ""

# Docker repository - ONE repository with multiple tags
$REPO = "scottgal/mostlylucid-nmt"

# Build CPU full image (cpu and latest tags)
Write-Host "Building ${REPO}:cpu (CPU full)..." -ForegroundColor Yellow
docker build `
  --build-arg VERSION="$VERSION" `
  --build-arg BUILD_DATE="$BUILD_DATE" `
  --build-arg VCS_REF="$VCS_REF" `
  -t "${REPO}:cpu" `
  -t "${REPO}:latest" `
  -t "${REPO}:cpu-${VERSION}" `
  -f Dockerfile `
  .

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Build CPU minimal image (cpu-min tag)
Write-Host ""
Write-Host "Building ${REPO}:cpu-min (CPU minimal)..." -ForegroundColor Yellow
docker build `
  --build-arg VERSION="$VERSION" `
  --build-arg BUILD_DATE="$BUILD_DATE" `
  --build-arg VCS_REF="$VCS_REF" `
  -t "${REPO}:cpu-min" `
  -t "${REPO}:cpu-min-${VERSION}" `
  -f Dockerfile.min `
  .

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Build GPU full image (gpu tag)
Write-Host ""
Write-Host "Building ${REPO}:gpu (GPU full)..." -ForegroundColor Yellow
docker build `
  --build-arg VERSION="$VERSION" `
  --build-arg BUILD_DATE="$BUILD_DATE" `
  --build-arg VCS_REF="$VCS_REF" `
  -t "${REPO}:gpu" `
  -t "${REPO}:gpu-${VERSION}" `
  -f Dockerfile.gpu `
  .

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Build GPU minimal image (gpu-min tag)
Write-Host ""
Write-Host "Building ${REPO}:gpu-min (GPU minimal)..." -ForegroundColor Yellow
docker build `
  --build-arg VERSION="$VERSION" `
  --build-arg BUILD_DATE="$BUILD_DATE" `
  --build-arg VCS_REF="$VCS_REF" `
  -t "${REPO}:gpu-min" `
  -t "${REPO}:gpu-min-${VERSION}" `
  -f Dockerfile.gpu.min `
  .

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "✓ All builds completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Images built (all in ONE repository with different tags):"
Write-Host "  ${REPO}:cpu (also tagged as :latest and :cpu-${VERSION})"
Write-Host "  ${REPO}:cpu-min (also tagged as :cpu-min-${VERSION})"
Write-Host "  ${REPO}:gpu (also tagged as :gpu-${VERSION})"
Write-Host "  ${REPO}:gpu-min (also tagged as :gpu-min-${VERSION})"
Write-Host ""
Write-Host "To push to Docker Hub:" -ForegroundColor Cyan
Write-Host "  docker push ${REPO}:cpu"
Write-Host "  docker push ${REPO}:latest"
Write-Host "  docker push ${REPO}:cpu-${VERSION}"
Write-Host "  docker push ${REPO}:cpu-min"
Write-Host "  docker push ${REPO}:cpu-min-${VERSION}"
Write-Host "  docker push ${REPO}:gpu"
Write-Host "  docker push ${REPO}:gpu-${VERSION}"
Write-Host "  docker push ${REPO}:gpu-min"
Write-Host "  docker push ${REPO}:gpu-min-${VERSION}"
Write-Host ""
Write-Host "Or push all tags at once:" -ForegroundColor Cyan
Write-Host "  docker push ${REPO} --all-tags"
