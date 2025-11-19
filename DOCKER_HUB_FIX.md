# Docker Hub Fix - Complete Summary

**Date:** 2025-11-19
**Tag:** v3.2.6
**Status:** Building in GitHub Actions

## Issues Fixed

### 1. ✅ BOM (Byte Order Mark) Causing Import Errors
**Problem:** UTF-8 BOM in Python files caused `ModuleNotFoundError: No module named 'src.app'`

**Files Fixed:**
- `src/api/routes/compat.py` ⚠️ Critical
- `tests/test_preload_models.py`
- `README.md`
- `.gitignore`
- `.idea/.gitignore`

**Prevention:** Added BOM removal step to GitHub Actions workflow

### 2. ✅ Stale `:latest` Tag
**Problem:** `:latest` tag was from 2025-11-08 (11 days old)

**Root Cause:** Workflow only updated `:latest` on main branch pushes, not version tags

**Fix:** Changed workflow to update `:latest` on every version tag push

### 3. ✅ Poor Version Management
**Problem:** Only timestamp-based versions (20251119.045845), no semantic versioning

**Fix:** Workflow now extracts semantic version from git tags:
- Tag `v3.2.6` → Docker tags `:cpu-3.2.6`, `:gpu-3.2.6`, etc.

## New Docker Hub Tagging Strategy

### After v3.2.6 Build Completes:

| Tag | Points To | Updated On | Description |
|-----|-----------|------------|-------------|
| `:latest` | CPU | Every tag push | **ALWAYS** the latest CPU image |
| `:cpu` | CPU | Every tag push | Latest CPU (on-demand model loading) |
| `:cpu-3.2.6` | CPU | Version tags | Semantic versioned CPU |
| `:gpu` | GPU | Every tag push | Latest GPU (on-demand model loading) |
| `:gpu-3.2.6` | GPU | Version tags | Semantic versioned GPU |

**Note:** All images use minimal base with on-demand model loading. No more bundled variants!

### For Users:

**Just want it to work (CPU)?**
```bash
docker pull scottgal/mostlylucid-nmt:latest
```

**Want specific variant?**
```bash
docker pull scottgal/mostlylucid-nmt:cpu      # CPU (on-demand models)
docker pull scottgal/mostlylucid-nmt:gpu      # GPU (on-demand models)
```

**Want pinned version?**
```bash
docker pull scottgal/mostlylucid-nmt:cpu-3.2.6
docker pull scottgal/mostlylucid-nmt:gpu-3.2.6
```

## Current Build Status

**GitHub Actions:** https://github.com/scottgal/mostlylucid-nmt/actions

The workflow is building 4 variants in parallel:
1. CPU full (with preloaded models) - amd64 + arm64
2. CPU minimal (no models) - amd64 + arm64
3. GPU full (with preloaded models) - amd64 only
4. GPU minimal (no models) - amd64 only

**Expected completion:** ~15-20 minutes from tag push (2025-11-19 12:14 UTC)

## Verification Commands

### After Build Completes:

```bash
# 1. Verify :latest points to CPU and is fresh
docker pull scottgal/mostlylucid-nmt:latest
docker inspect scottgal/mostlylucid-nmt:latest | grep Created

# 2. Verify it runs without import errors
docker run --rm scottgal/mostlylucid-nmt:latest python -c "from src.app import app; print('SUCCESS')"

# 3. Test GPU variant
docker pull scottgal/mostlylucid-nmt:gpu
docker run --rm --gpus all -p 8000:8000 scottgal/mostlylucid-nmt:gpu

# 4. Check versioned tags exist
docker pull scottgal/mostlylucid-nmt:cpu-3.2.6
docker pull scottgal/mostlylucid-nmt:gpu-3.2.6
```

## Git Commits

```
ee04f1e - Fix Docker import errors by removing UTF-8 BOM from all files
8c7c566 - Add BOM removal to GitHub Actions CI/CD workflow
e1d5e5f - Add comprehensive BOM fix summary and deployment instructions
d855aae - Fix Docker Hub tagging: ensure :latest always points to CPU
v3.2.6  - Release tag (triggers build with all fixes)
```

## What Changed in CI/CD Workflow

### Before:
```yaml
# :latest only updated on main branch pushes
type=raw,value=latest,enable=${{ matrix.is_latest && github.ref == 'refs/heads/main' }}

# Only timestamp versions
VERSION=$(date -u +"%Y%m%d.%H%M%S")
```

### After:
```yaml
# :latest updates on version tag pushes
type=raw,value=latest,enable=${{ matrix.is_latest && startsWith(github.ref, 'refs/tags/v') }}

# Semantic versioning from git tags
if [[ "${{ github.ref }}" =~ refs/tags/v([0-9]+\.[0-9]+\.[0-9]+) ]]; then
  VERSION="${BASH_REMATCH[1]}"  # e.g., "3.2.6"
else
  VERSION=$(date -u +"%Y%m%d.%H%M%S")  # fallback
fi
```

### BOM Protection:
```yaml
- name: Remove BOM from all files
  run: |
    chmod +x tools/remove-bom.sh
    ./tools/remove-bom.sh || echo "No BOMs found or already removed"
```

## Future Release Process

### To Release a New Version:

1. **Make your changes and commit:**
   ```bash
   git add .
   git commit -m "Your changes"
   git push origin main
   ```

2. **Create and push a version tag:**
   ```bash
   git tag v3.2.7
   git push origin v3.2.7
   ```

3. **Monitor the build:**
   - Go to https://github.com/scottgal/mostlylucid-nmt/actions
   - Wait for all 4 variants to build (~15-20 min)

4. **Verify on Docker Hub:**
   ```bash
   docker pull scottgal/mostlylucid-nmt:latest
   docker pull scottgal/mostlylucid-nmt:cpu-3.2.7
   ```

### The workflow will automatically:
- ✅ Remove any BOM characters
- ✅ Build all 4 variants (CPU, CPU-min, GPU, GPU-min)
- ✅ Tag with semantic version (3.2.7)
- ✅ Update `:latest` to point to CPU
- ✅ Update all variant tags (:cpu, :gpu, etc.)
- ✅ Push to both Docker Hub and GitHub Container Registry

## Technical Details

### Why This Happened:

1. **BOM Issue:** Windows editors (VSCode, Notepad) sometimes save files with UTF-8 BOM
2. **Stale :latest:** Workflow logic error - checked for main branch instead of version tags
3. **No Semantic Versioning:** Original workflow only used timestamps

### How It's Fixed:

1. **BOM:** Automated removal in CI + tools for local checking
2. **:latest:** Fixed workflow condition to trigger on version tags
3. **Versioning:** Extract version from git tag using regex

---

**Status:** All fixes committed and pushed. Tag v3.2.6 building now.

**Next Steps:** Wait for GitHub Actions to complete, then verify Docker Hub images.
