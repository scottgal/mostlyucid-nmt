@echo off
REM Build and push ARM64 image to Docker Hub
REM This script builds for ARM64 and immediately pushes to registry

setlocal

REM Check if logged into Docker Hub
echo Checking Docker Hub authentication...
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running
    exit /b 1
)

REM Generate version timestamp using PowerShell
for /f "delims=" %%i in ('powershell -Command "(Get-Date).ToUniversalTime().ToString('yyyyMMdd.HHmmss')"') do set VERSION=%%i

set IMAGE_NAME=mostlylucid-nmt
set DOCKER_HUB_REPO=scottgal/mostlylucid-nmt
set PLATFORM=linux/arm64

echo ==========================================
echo Building and Pushing ARM64 to Docker Hub
echo Version: %VERSION%
echo Platform: %PLATFORM%
echo Repository: %DOCKER_HUB_REPO%
echo ==========================================
echo.

REM Ensure buildx builder exists
echo Setting up buildx builder...
docker buildx create --name arm-builder --use 2>nul
if errorlevel 1 (
    echo Using existing buildx builder...
    docker buildx use arm-builder
)
docker buildx inspect --bootstrap
echo.

REM Build and push ARM64 image
echo ==========================================
echo Building and pushing ARM64 image...
echo This will take several minutes...
echo ==========================================
echo.

docker buildx build ^
    --platform %PLATFORM% ^
    -f Dockerfile.arm64 ^
    -t %DOCKER_HUB_REPO%:pi ^
    -t %DOCKER_HUB_REPO%:arm64 ^
    -t %DOCKER_HUB_REPO%:pi-%VERSION% ^
    --build-arg VERSION=%VERSION% ^
    --push ^
    .

if errorlevel 1 (
    echo.
    echo ==========================================
    echo Build and push FAILED!
    echo ==========================================
    echo.
    echo Common issues:
    echo 1. Not logged into Docker Hub - run: docker login
    echo 2. No internet connection
    echo 3. Docker daemon not running
    echo.
    exit /b 1
)

echo.
echo ==========================================
echo Build and push complete!
echo ==========================================
echo.
echo Images pushed to Docker Hub:
echo   %DOCKER_HUB_REPO%:pi
echo   %DOCKER_HUB_REPO%:arm64
echo   %DOCKER_HUB_REPO%:pi-%VERSION%
echo.
echo Verify with:
echo   docker buildx imagetools inspect %DOCKER_HUB_REPO%:pi
echo.
echo Test on Raspberry Pi:
echo   docker pull %DOCKER_HUB_REPO%:pi
echo   docker run -p 8000:8000 -v ./model-cache:/models %DOCKER_HUB_REPO%:pi
echo.

endlocal
