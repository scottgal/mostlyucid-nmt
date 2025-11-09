# Quick build script for LOCAL DEVELOPMENT AND TESTING
# Builds only the minimal variants (NO model downloads - fast!)
# PowerShell script for Windows

param(
    [switch]$GPU,
    [switch]$Both
)

Write-Host "=== RAPID LOCAL BUILD ===" -ForegroundColor Cyan
Write-Host ""

if ($Both) {
    Write-Host "Building BOTH CPU and GPU minimal variants..." -ForegroundColor Yellow
    Write-Host ""

    Write-Host "[1/2] Building CPU minimal (dev:cpu)..." -ForegroundColor Green
    docker build -f Dockerfile.min -t dev:cpu -t dev:latest .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed!" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host ""
    Write-Host "[2/2] Building GPU minimal (dev:gpu)..." -ForegroundColor Green
    docker build -f Dockerfile.gpu.min -t dev:gpu .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed!" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host ""
    Write-Host "Both builds completed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Run CPU: docker run -p 8000:8000 -v `${PWD}/src:/app/src -v `${PWD}/model-cache:/models dev:cpu"
    Write-Host "Run GPU: docker run --gpus all -p 8000:8000 -v `${PWD}/src:/app/src -v `${PWD}/model-cache:/models dev:gpu"
}
elseif ($GPU) {
    Write-Host "Building GPU minimal variant (dev:gpu)..." -ForegroundColor Yellow
    Write-Host ""

    docker build -f Dockerfile.gpu.min -t dev:gpu .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed!" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host ""
    Write-Host "Build completed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Run: docker run --gpus all -p 8000:8000 -v `${PWD}/src:/app/src -v `${PWD}/model-cache:/models dev:gpu"
    Write-Host ""
    Write-Host "Hot reload: docker run --gpus all -p 8000:8000 -v `${PWD}/src:/app/src dev:gpu uvicorn src.app:app --reload"
}
else {
    Write-Host "Building CPU minimal variant (dev:latest)..." -ForegroundColor Yellow
    Write-Host ""

    docker build -f Dockerfile.min -t dev:latest .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed!" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host ""
    Write-Host "Build completed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Run: docker run -p 8000:8000 -v `${PWD}/src:/app/src -v `${PWD}/model-cache:/models dev:latest"
    Write-Host ""
    Write-Host "Hot reload: docker run -p 8000:8000 -v `${PWD}/src:/app/src dev:latest uvicorn src.app:app --reload"
}

Write-Host ""
Write-Host "Build time: ~30 seconds (no model downloads)" -ForegroundColor Cyan
Write-Host "Rebuild after code change: ~3 seconds (layer caching)" -ForegroundColor Cyan
Write-Host ""
Write-Host "OPTIONS:" -ForegroundColor Yellow
Write-Host "  .\build-dev.ps1        # Build CPU minimal"
Write-Host "  .\build-dev.ps1 -GPU   # Build GPU minimal"
Write-Host "  .\build-dev.ps1 -Both  # Build both"
