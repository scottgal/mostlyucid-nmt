# Build all Docker image variants with proper versioning
# PowerShell script for Windows

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

# Docker repository
$REPO = "scottgal/mostlylucid-nmt"

# Build CPU full image (latest)
Write-Host "Building ${REPO}:latest (CPU full)..." -ForegroundColor Yellow
docker build `
  --build-arg VERSION="$VERSION" `
  --build-arg BUILD_DATE="$BUILD_DATE" `
  --build-arg VCS_REF="$VCS_REF" `
  -t "${REPO}:latest" `
  -t "${REPO}:${VERSION}" `
  -f Dockerfile `
  .

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Build CPU minimal image
Write-Host ""
Write-Host "Building ${REPO}:min (CPU minimal)..." -ForegroundColor Yellow
docker build `
  --build-arg VERSION="$VERSION" `
  --build-arg BUILD_DATE="$BUILD_DATE" `
  --build-arg VCS_REF="$VCS_REF" `
  -t "${REPO}:min" `
  -t "${REPO}:min-${VERSION}" `
  -f Dockerfile.min `
  .

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Build GPU full image
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

# Build GPU minimal image
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
Write-Host "Images built:"
Write-Host "  ${REPO}:latest (and ${VERSION})"
Write-Host "  ${REPO}:min (and min-${VERSION})"
Write-Host "  ${REPO}:gpu (and gpu-${VERSION})"
Write-Host "  ${REPO}:gpu-min (and gpu-min-${VERSION})"
Write-Host ""
Write-Host "To push to Docker Hub:" -ForegroundColor Cyan
Write-Host "  docker push ${REPO}:latest"
Write-Host "  docker push ${REPO}:${VERSION}"
Write-Host "  docker push ${REPO}:min"
Write-Host "  docker push ${REPO}:min-${VERSION}"
Write-Host "  docker push ${REPO}:gpu"
Write-Host "  docker push ${REPO}:gpu-${VERSION}"
Write-Host "  docker push ${REPO}:gpu-min"
Write-Host "  docker push ${REPO}:gpu-min-${VERSION}"
Write-Host ""
Write-Host "Or push all at once:" -ForegroundColor Cyan
Write-Host "  docker push ${REPO} --all-tags"
