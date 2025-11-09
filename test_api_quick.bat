@echo off
REM Quick API test script for mostlylucid-nmt v3.1 (Windows)
REM Tests various translation pairs including fallback scenarios

setlocal enabledelayedexpansion

set BASE_URL=%1
if "%BASE_URL%"=="" set BASE_URL=http://localhost:8000

echo ========================================================================
echo   mostlylucid-nmt v3.1 - Quick API Test (Windows)
echo ========================================================================
echo.
echo Testing API at: %BASE_URL%
echo.

REM Check if curl is available
where curl >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: curl is not available. Please install curl or use Windows 10/11 which includes it.
    exit /b 1
)

REM Check health
echo Checking service health...
curl -s "%BASE_URL%/healthz" | findstr "ok" >nul
if %ERRORLEVEL% equ 0 (
    echo [OK] Service is healthy
) else (
    echo [ERROR] Service is not responding
    exit /b 1
)
echo.

echo ========================================================================
echo TEST SET 1: Basic Translation Pairs (Opus-MT)
echo ========================================================================
echo.

echo Testing: en -^> de
curl -s -X POST "%BASE_URL%/translate" -H "Content-Type: application/json" -d "{\"text\": [\"Hello world\"], \"source_lang\": \"en\", \"target_lang\": \"de\", \"beam_size\": 1}"
echo.
echo.

echo Testing: de -^> en
curl -s -X POST "%BASE_URL%/translate" -H "Content-Type: application/json" -d "{\"text\": [\"Guten Tag\"], \"source_lang\": \"de\", \"target_lang\": \"en\", \"beam_size\": 1}"
echo.
echo.

echo Testing: fr -^> en
curl -s -X POST "%BASE_URL%/translate" -H "Content-Type: application/json" -d "{\"text\": [\"Bonjour le monde\"], \"source_lang\": \"fr\", \"target_lang\": \"en\", \"beam_size\": 1}"
echo.
echo.

echo Testing: es -^> en
curl -s -X POST "%BASE_URL%/translate" -H "Content-Type: application/json" -d "{\"text\": [\"Hola mundo\"], \"source_lang\": \"es\", \"target_lang\": \"en\", \"beam_size\": 1}"
echo.
echo.

echo ========================================================================
echo TEST SET 2: Automatic Fallback (requires mBART50/M2M100)
echo ========================================================================
echo.

echo Testing: en -^> bn (Bengali - should fallback)
curl -s -X POST "%BASE_URL%/translate" -H "Content-Type: application/json" -H "X-Enable-Metadata: 1" -d "{\"text\": [\"Hello\"], \"source_lang\": \"en\", \"target_lang\": \"bn\", \"beam_size\": 1}"
echo.
echo.

echo Testing: en -^> ur (Urdu - should fallback)
curl -s -X POST "%BASE_URL%/translate" -H "Content-Type: application/json" -H "X-Enable-Metadata: 1" -d "{\"text\": [\"Hello\"], \"source_lang\": \"en\", \"target_lang\": \"ur\", \"beam_size\": 1}"
echo.
echo.

echo ========================================================================
echo TEST SET 3: Explicit Model Family Selection
echo ========================================================================
echo.

echo Testing: en -^> de with opus-mt
curl -s -X POST "%BASE_URL%/translate" -H "Content-Type: application/json" -H "X-Enable-Metadata: 1" -d "{\"text\": [\"Hello world\"], \"source_lang\": \"en\", \"target_lang\": \"de\", \"beam_size\": 1, \"model_family\": \"opus-mt\"}"
echo.
echo.

echo Testing: en -^> de with mbart50
curl -s -X POST "%BASE_URL%/translate" -H "Content-Type: application/json" -H "X-Enable-Metadata: 1" -d "{\"text\": [\"Hello world\"], \"source_lang\": \"en\", \"target_lang\": \"de\", \"beam_size\": 1, \"model_family\": \"mbart50\"}"
echo.
echo.

echo Testing: en -^> de with m2m100
curl -s -X POST "%BASE_URL%/translate" -H "Content-Type: application/json" -H "X-Enable-Metadata: 1" -d "{\"text\": [\"Hello world\"], \"source_lang\": \"en\", \"target_lang\": \"de\", \"beam_size\": 1, \"model_family\": \"m2m100\"}"
echo.
echo.

echo ========================================================================
echo TEST SET 4: Batch Translation
echo ========================================================================
echo.

echo Testing batch: en -^> de (4 texts)
curl -s -X POST "%BASE_URL%/translate" -H "Content-Type: application/json" -d "{\"text\": [\"Hello world\", \"How are you?\", \"This is a test\", \"Machine translation is amazing\"], \"source_lang\": \"en\", \"target_lang\": \"de\", \"beam_size\": 1}"
echo.
echo.

echo ========================================================================
echo CACHE STATUS
echo ========================================================================
echo.

curl -s "%BASE_URL%/cache"
echo.
echo.

echo ========================================================================
echo Test suite complete!
echo ========================================================================
echo.
echo Check server logs to see:
echo   - Download progress banners with sizes and device info
echo   - Cache HIT/MISS indicators
echo   - Model family fallback decisions
echo   - Intelligent pivot selection logic
echo.

endlocal
