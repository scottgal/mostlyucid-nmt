# build_exe.ps1 - Build standalone executable for MostlyLucid-NMT (Windows)
#
# Usage:
#   .\build_exe.ps1           # Build with default settings
#   .\build_exe.ps1 -Clean    # Clean build (remove dist/build first)
#   .\build_exe.ps1 -NoUpx    # Skip UPX compression

param(
    [switch]$Clean,
    [switch]$NoUpx,
    [switch]$Debug
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MostlyLucid-NMT Executable Builder" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[1/5] Checking Python environment..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    exit 1
}
$pythonVersion = python --version
Write-Host "       Found: $pythonVersion" -ForegroundColor Green

# Check PyInstaller
Write-Host "[2/5] Checking PyInstaller..." -ForegroundColor Yellow
$pyinstaller = python -c "import PyInstaller; print(PyInstaller.__version__)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "       Installing PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install PyInstaller" -ForegroundColor Red
        exit 1
    }
}
$pyinstallerVersion = python -c "import PyInstaller; print(PyInstaller.__version__)"
Write-Host "       Found: PyInstaller $pyinstallerVersion" -ForegroundColor Green

# Check UPX (optional)
$upxAvailable = $false
if (-not $NoUpx) {
    Write-Host "[2.5/5] Checking UPX (optional compression)..." -ForegroundColor Yellow
    $upx = Get-Command upx -ErrorAction SilentlyContinue
    if ($upx) {
        $upxAvailable = $true
        Write-Host "       Found: UPX available" -ForegroundColor Green
    } else {
        Write-Host "       UPX not found (optional - exe will be larger)" -ForegroundColor DarkYellow
    }
}

# Clean if requested
if ($Clean) {
    Write-Host "[3/5] Cleaning previous builds..." -ForegroundColor Yellow
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    Write-Host "       Cleaned dist/ and build/" -ForegroundColor Green
} else {
    Write-Host "[3/5] Skipping clean (use -Clean to force)" -ForegroundColor DarkGray
}

# Build
Write-Host "[4/5] Building executable..." -ForegroundColor Yellow
Write-Host "       This may take several minutes..." -ForegroundColor DarkYellow

$buildArgs = @("mostlylucid_nmt.spec")
if ($Debug) {
    $buildArgs += "--log-level=DEBUG"
}
if ($NoUpx -or -not $upxAvailable) {
    $buildArgs += "--noupx"
}

$startTime = Get-Date
pyinstaller @buildArgs
$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Build failed" -ForegroundColor Red
    exit 1
}

# Verify output
Write-Host "[5/5] Verifying build..." -ForegroundColor Yellow
$exePath = "dist\mostlylucid-nmt.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "ERROR: Executable not found at $exePath" -ForegroundColor Red
    exit 1
}

$exeSize = (Get-Item $exePath).Length / 1MB
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "BUILD SUCCESSFUL" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output:   $exePath" -ForegroundColor White
Write-Host "Size:     $([math]::Round($exeSize, 1)) MB" -ForegroundColor White
Write-Host "Time:     $([math]::Round($duration, 1)) seconds" -ForegroundColor White
Write-Host ""
Write-Host "Usage:" -ForegroundColor Cyan
Write-Host "  .\dist\mostlylucid-nmt.exe              # Start server" -ForegroundColor White
Write-Host "  .\dist\mostlylucid-nmt.exe --help       # Show help" -ForegroundColor White
Write-Host "  .\dist\mostlylucid-nmt.exe --check      # Check if running" -ForegroundColor White
Write-Host "  .\dist\mostlylucid-nmt.exe --translate 'Hello' -s en -t de" -ForegroundColor White
Write-Host ""
