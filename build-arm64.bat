@echo off
REM Build script for ARM64/Raspberry Pi (Windows)
REM Uses buildx for cross-compilation

setlocal

REM Generate version timestamp using PowerShell
for /f "delims=" %%i in ('powershell -Command "(Get-Date).ToUniversalTime().ToString('yyyyMMdd.HHmmss')"') do set VERSION=%%i

set IMAGE_NAME=mostlylucid-nmt
set DOCKER_HUB_REPO=scottgal/mostlylucid-nmt
set PLATFORM=linux/arm64

echo ==========================================
echo Building ARM64 image for Raspberry Pi
echo Version: %VERSION%
echo Platform: %PLATFORM%
echo ==========================================
echo.

REM Check if Docker is available
docker version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running or not installed
    exit /b 1
)

REM Cross-compile using buildx (required on Windows)
echo Cross-compiling for ARM64 using buildx...
echo.

REM Create builder if it doesn't exist, or use existing
docker buildx create --name arm-builder --use 2>nul
if errorlevel 1 (
    echo Using existing buildx builder...
    docker buildx use arm-builder
)

REM Build for ARM64
docker buildx build ^
    --platform %PLATFORM% ^
    -f Dockerfile.arm64 ^
    -t %IMAGE_NAME%:pi ^
    -t %IMAGE_NAME%:arm64 ^
    -t %IMAGE_NAME%:pi-%VERSION% ^
    --build-arg VERSION=%VERSION% ^
    --load ^
    .

if errorlevel 1 (
    echo.
    echo ==========================================
    echo Build FAILED!
    echo ==========================================
    exit /b 1
)

echo.
echo ==========================================
echo Build complete!
echo Images created:
echo   %IMAGE_NAME%:pi
echo   %IMAGE_NAME%:arm64
echo   %IMAGE_NAME%:pi-%VERSION%
echo ==========================================
echo.
echo To run locally on Raspberry Pi:
echo   docker run -p 8000:8000 ^
echo     -v ./model-cache:/models ^
echo     -e MODEL_CACHE_DIR=/models ^
echo     %IMAGE_NAME%:pi
echo.
echo Or use docker-compose-arm64.yml:
echo   docker-compose -f docker-compose-arm64.yml up
echo.
echo To push to Docker Hub:
echo   docker tag %IMAGE_NAME%:pi %DOCKER_HUB_REPO%:pi
echo   docker tag %IMAGE_NAME%:pi %DOCKER_HUB_REPO%:arm64
echo   docker tag %IMAGE_NAME%:pi-%VERSION% %DOCKER_HUB_REPO%:pi-%VERSION%
echo   docker push %DOCKER_HUB_REPO%:pi
echo   docker push %DOCKER_HUB_REPO%:arm64
echo   docker push %DOCKER_HUB_REPO%:pi-%VERSION%
echo.

endlocal
