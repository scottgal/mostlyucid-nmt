# API Validation Script
# Runs automated tests against a live running instance
# PowerShell script for Windows

param(
    [string]$BaseURL = "http://localhost:8000",
    [switch]$SmokeOnly,
    [switch]$Verbose
)

Write-Host "=== API VALIDATION ===" -ForegroundColor Cyan
Write-Host "Testing API at: $BaseURL" -ForegroundColor Yellow
Write-Host ""

# Check if API is reachable
Write-Host "Checking API availability..." -ForegroundColor Gray
try {
    $response = Invoke-WebRequest -Uri "$BaseURL/healthz" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ API is reachable" -ForegroundColor Green
    }
    else {
        Write-Host "✗ API returned status $($response.StatusCode)" -ForegroundColor Red
        Write-Host ""
        Write-Host "Make sure the API is running:" -ForegroundColor Yellow
        Write-Host "  docker run -p 8000:8000 dev:latest"
        exit 1
    }
}
catch {
    Write-Host "✗ API not reachable at $BaseURL" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure the API is running:" -ForegroundColor Yellow
    Write-Host "  docker run -p 8000:8000 dev:latest"
    Write-Host ""
    Write-Host "Or specify a different URL:" -ForegroundColor Yellow
    Write-Host "  .\validate-api.ps1 -BaseURL http://localhost:8001"
    exit 1
}

Write-Host ""

# Set environment variable for tests
$env:BASE_URL = $BaseURL

# Build pytest command
$pytestArgs = @("tests/test_api_live.py")

if ($Verbose) {
    $pytestArgs += "-v"
}
else {
    $pytestArgs += "-v"
}

if ($SmokeOnly) {
    Write-Host "Running smoke tests only (health checks + basic translation)..." -ForegroundColor Yellow
    $pytestArgs += "-m"
    $pytestArgs += "smoke"
}
else {
    Write-Host "Running full validation suite..." -ForegroundColor Yellow
    $pytestArgs += "-m"
    $pytestArgs += "not slow"
}

Write-Host ""

# Run tests
python -m pytest @pytestArgs

$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "✓ All validation tests passed!" -ForegroundColor Green
}
else {
    Write-Host "✗ Some tests failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "OPTIONS:" -ForegroundColor Yellow
Write-Host "  .\validate-api.ps1                                # Full validation"
Write-Host "  .\validate-api.ps1 -SmokeOnly                     # Quick smoke test"
Write-Host "  .\validate-api.ps1 -BaseURL http://localhost:8001 # Custom URL"
Write-Host "  .\validate-api.ps1 -Verbose                       # Verbose output"

exit $exitCode
