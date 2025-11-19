# BOM Fix Summary - Docker Import Error Resolution

## Problem
Docker images from Docker Hub (`scottgal/mostlylucid-nmt:*`) were failing at startup with:
```
ModuleNotFoundError: No module named 'src.app'
```

## Root Cause
**UTF-8 BOM (Byte Order Mark)** characters in Python source files were interfering with Python's import system when running under Gunicorn inside Docker containers.

## Files That Had BOMs (Now Fixed)
1. `src/api/routes/compat.py` ⚠️ **Critical - imported during app startup**
2. `tests/test_preload_models.py`
3. `README.md`
4. `.gitignore`
5. `.idea/.gitignore`

## What Was Done

### 1. Removed All BOMs
- Created `tools/remove-bom.ps1` (Windows/PowerShell version)
- Created `tools/remove-bom.sh` (Linux/Mac/CI version)
- Removed BOMs from all affected files

### 2. Updated CI/CD Pipeline
- Modified `.github/workflows/docker.yml` to run BOM removal before every build
- This ensures ALL future Docker Hub images are BOM-free

### 3. Git Commits
```bash
ee04f1e - Fix Docker import errors by removing UTF-8 BOM from all files
8c7c566 - Add BOM removal to GitHub Actions CI/CD workflow
```

## How to Push Fixed Images to Docker Hub

### Option 1: Create a Version Tag (Recommended)
This triggers the GitHub Actions workflow to build and push to Docker Hub:

```bash
# Push your commits
git push origin main

# Create and push a version tag
git tag v1.0.1
git push origin v1.0.1
```

This will automatically build and push:
- `scottgal/mostlylucid-nmt:latest`
- `scottgal/mostlylucid-nmt:cpu`
- `scottgal/mostlylucid-nmt:cpu-min`
- `scottgal/mostlylucid-nmt:gpu`
- `scottgal/mostlylucid-nmt:gpu-min`
- Plus versioned tags like `:cpu-20251119.120000`

### Option 2: Manual Local Build and Push
If you want to build and push manually:

```powershell
# Windows PowerShell
.\build-all.ps1 -Push
```

This requires Docker Hub login:
```bash
docker login
```

## Verification

### Test Locally
```bash
# Build fresh image
docker build -f Dockerfile.min -t test:latest .

# Test it starts correctly
docker run --rm test:latest python -c "from src.app import app; print('SUCCESS')"

# Test with Gunicorn
docker run --rm -p 8000:8000 test:latest
```

### Test from Docker Hub (After Push)
```bash
# Pull latest
docker pull scottgal/mostlylucid-nmt:gpu

# Run it
docker run --rm --gpus all -p 8000:8000 scottgal/mostlylucid-nmt:gpu
```

Should start without errors and show:
```
[INFO] Using CPU/GPU for translation
[INFO] Max inflight translations: 1
```

## Prevention

### For Developers
Run BOM check before committing:

**Windows:**
```powershell
.\tools\remove-bom.ps1
```

**Linux/Mac:**
```bash
./tools/remove-bom.sh
```

### Automatic in CI/CD
The GitHub Actions workflow now automatically removes BOMs before every Docker build.

## Why This Happened

Windows text editors (like Notepad, some IDEs) sometimes save files with UTF-8 BOM. While Python can handle BOMs in source files when run directly, they cause issues when:
1. Files are imported as modules
2. Running under Gunicorn/WSGI servers
3. Building Docker images on different platforms

## Current Status

✅ All BOM instances removed from repository
✅ CI/CD pipeline updated to prevent future BOMs
✅ Tools created for manual BOM checking
✅ Ready to push fixed images to Docker Hub

## Next Steps

1. **Push commits to GitHub:**
   ```bash
   git push origin main
   ```

2. **Create version tag to trigger Docker Hub push:**
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```

3. **Monitor GitHub Actions:**
   - Go to https://github.com/scottgal/mostlylucid-nmt/actions
   - Watch the "Build and Push Docker Images" workflow
   - Verify all 4 variants build and push successfully

4. **Test from Docker Hub:**
   ```bash
   docker pull scottgal/mostlylucid-nmt:gpu
   docker run --rm --gpus all -p 8000:8000 scottgal/mostlylucid-nmt:gpu
   ```

## Timeline

- **Before:** Docker Hub images failing with `ModuleNotFoundError`
- **Now:** Fixed in repository, need to push new version tag
- **After v1.0.1 tag:** Docker Hub will have working images

---

Generated: 2025-11-19
Issue: BOM-induced Docker import failures
Status: **Fixed, awaiting deployment**
