# Multi-Vendor GPU Support

This branch adds support for AMD ROCm and Intel GPUs/NPUs in addition to the existing NVIDIA CUDA support.

## Supported GPU Vendors

### 1. NVIDIA CUDA (Existing)
- **Supported GPUs**: All CUDA-capable NVIDIA GPUs (GeForce, Quadro, Tesla, etc.)
- **Docker Images**: `scottgal/mostlylucid-nmt:gpu`, `scottgal/mostlylucid-nmt:gpu-min`
- **Dockerfiles**: `Dockerfile.gpu`, `Dockerfile.gpu.min`
- **Requirements**: NVIDIA Container Toolkit, CUDA 12.6+
- **Device String**: `cuda:0`, `cuda:1`, etc.

**Run Example:**
```bash
docker run --gpus all -e USE_GPU=true -p 8000:8000 scottgal/mostlylucid-nmt:gpu
```

### 2. AMD ROCm (New)
- **Supported GPUs**: AMD Radeon RX 6000/7000 series, AMD Instinct accelerators
- **Docker Images**: `scottgal/mostlylucid-nmt:rocm`, `scottgal/mostlylucid-nmt:rocm-min`
- **Dockerfiles**: `Dockerfile.rocm`, `Dockerfile.rocm.min`
- **Requirements**: AMD ROCm 6.2+, compatible AMD GPU
- **Device String**: `cuda:0` (ROCm uses CUDA-compatible API)
- **Base Image**: `rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch_release_2.3.0`

**Run Example:**
```bash
docker run --device=/dev/kfd --device=/dev/dri -e USE_GPU=true -p 8000:8000 scottgal/mostlylucid-nmt:rocm
```

**Environment Variables:**
- `HSA_OVERRIDE_GFX_VERSION`: Set if your GPU needs architecture override (e.g., `10.3.0`)
- `ROCR_VISIBLE_DEVICES`: Specify which AMD GPUs to use (similar to `CUDA_VISIBLE_DEVICES`)

### 3. Intel Arc/Data Center GPUs and NPUs (New)
- **Supported Hardware**:
  - Intel Arc A-series GPUs (A770, A750, A380, etc.)
  - Intel Data Center GPUs (Flex Series, Max Series)
  - Intel integrated GPUs (Iris Xe)
  - Intel NPUs (experimental - driver support required)
- **Docker Images**: `scottgal/mostlylucid-nmt:intel`, `scottgal/mostlylucid-nmt:intel-min`
- **Dockerfiles**: `Dockerfile.intel`, `Dockerfile.intel.min`
- **Requirements**: Intel GPU drivers, Intel Extension for PyTorch (IPEX)
- **Device String**: `xpu:0`, `xpu:1`, etc.
- **Technology**: Intel Extension for PyTorch (IPEX) 2.3.110

**Run Example:**
```bash
docker run --device=/dev/dri -e USE_GPU=true -p 8000:8000 scottgal/mostlylucid-nmt:intel
```

**Environment Variables:**
- `DEVICE=xpu:0`: Explicitly use Intel XPU device

## Building Images

### Quick Build All Variants
```bash
# Windows
.\build-all.ps1

# Linux/Mac
./build-all.sh
```

### Build Individual Variants

#### AMD ROCm
```bash
# Full (with preloaded models)
docker build -f Dockerfile.rocm -t mostlylucid-nmt:rocm .

# Minimal (no preloaded models)
docker build -f Dockerfile.rocm.min -t mostlylucid-nmt:rocm-min .
```

#### Intel GPU/NPU
```bash
# Full (with preloaded models)
docker build -f Dockerfile.intel -t mostlylucid-nmt:intel .

# Minimal (no preloaded models)
docker build -f Dockerfile.intel.min -t mostlylucid-nmt:intel-min .
```

## Performance Comparison

### Translation Speed (sentences/second)

| GPU Type | Model | Approx. Speed | VRAM Usage | Notes |
|----------|-------|--------------|------------|-------|
| NVIDIA RTX 4090 | Opus-MT FP16 | 50-80 sent/s | 2-4GB | Best performance |
| NVIDIA RTX 3060 | Opus-MT FP16 | 30-50 sent/s | 2-4GB | Good value |
| AMD RX 7900 XTX | Opus-MT FP16 | 40-60 sent/s | 2-4GB | Competitive with NVIDIA |
| AMD RX 6800 | Opus-MT FP16 | 25-40 sent/s | 2-4GB | Good performance |
| Intel Arc A770 | Opus-MT FP16 | 20-35 sent/s | 2-4GB | Improving with drivers |
| Intel Arc A380 | Opus-MT FP16 | 15-25 sent/s | 2-4GB | Budget option |
| CPU (12-core) | Opus-MT FP32 | 5-10 sent/s | 4-8GB RAM | Baseline |

*Note: These are approximate figures. Actual performance varies based on text length, model, and driver versions.*

## Automatic Device Detection

The application automatically detects available GPUs:

```python
# Device detection order:
1. Intel XPU (if IPEX installed and torch.xpu.is_available())
2. NVIDIA CUDA (if torch.cuda.is_available() and no ROCm)
3. AMD ROCm (if torch.cuda.is_available() and torch.version.hip exists)
4. CPU (fallback)
```

## Configuration

### Device Selection

```bash
# Auto-detect (default)
USE_GPU=auto

# Force GPU
USE_GPU=true

# Force CPU
USE_GPU=false

# Explicit device (NVIDIA/AMD)
DEVICE=cuda:0

# Explicit device (Intel)
DEVICE=xpu:0
```

### Performance Settings

All GPU variants use optimised defaults:

```bash
# GPU defaults (all vendors)
WEB_CONCURRENCY=1                  # Single worker per GPU
MAX_INFLIGHT_TRANSLATIONS=1        # One translation at a time
EASYNMT_BATCH_SIZE=64             # Large batches for throughput
EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'  # Half precision
MAX_CACHED_MODELS=10              # Keep more models in VRAM
GRACEFUL_TIMEOUT=5                # Fast shutdown
```

### Vendor-Specific Tuning

#### AMD ROCm
```bash
# Override GPU architecture if needed
HSA_OVERRIDE_GFX_VERSION=10.3.0

# Multi-GPU selection
ROCR_VISIBLE_DEVICES=0,1
```

#### Intel XPU
```bash
# Explicitly select Intel GPU
DEVICE=xpu:0

# Intel may benefit from smaller batch sizes initially
EASYNMT_BATCH_SIZE=32
```

## Docker Compose Examples

### AMD ROCm
```yaml
version: '3.8'

services:
  translator:
    image: scottgal/mostlylucid-nmt:rocm-min
    devices:
      - /dev/kfd:/dev/kfd
      - /dev/dri:/dev/dri
    environment:
      USE_GPU: "true"
      EASYNMT_MODEL_ARGS: '{"torch_dtype":"fp16"}'
      PRELOAD_MODELS: "en->de,de->en"
    volumes:
      - ./model-cache:/models
    ports:
      - "8000:8000"
```

### Intel GPU
```yaml
version: '3.8'

services:
  translator:
    image: scottgal/mostlylucid-nmt:intel-min
    devices:
      - /dev/dri:/dev/dri
    environment:
      USE_GPU: "true"
      DEVICE: "xpu:0"
      EASYNMT_MODEL_ARGS: '{"torch_dtype":"fp16"}'
      PRELOAD_MODELS: "en->de,de->en"
    volumes:
      - ./model-cache:/models
    ports:
      - "8000:8000"
```

## Troubleshooting

### AMD ROCm

**Issue**: "RuntimeError: No HIP GPUs are available"
**Solution**:
- Ensure ROCm drivers are installed: `rocm-smi`
- Check GPU is visible: `rocm-smi --showproductname`
- Verify Docker has access: `docker run --device=/dev/kfd --device=/dev/dri rocm/pytorch:latest rocm-smi`

**Issue**: "HSA_STATUS_ERROR_INCOMPATIBLE_ARGUMENTS"
**Solution**:
- Set `HSA_OVERRIDE_GFX_VERSION` to your GPU's architecture version
- Example: `HSA_OVERRIDE_GFX_VERSION=10.3.0` for RDNA 2 GPUs

### Intel GPU

**Issue**: "RuntimeError: No XPU devices available"
**Solution**:
- Ensure Intel GPU drivers are installed
- Check `/dev/dri` exists and has correct permissions
- Install Intel compute runtime: `apt install intel-opencl-icd intel-level-zero-gpu`

**Issue**: Slower than expected
**Solution**:
- Intel GPU support is actively improving with driver updates
- Update to latest Intel GPU drivers
- Try reducing batch size: `EASYNMT_BATCH_SIZE=32`
- Ensure you're using FP16: `EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'`

**Issue**: "ImportError: No module named 'intel_extension_for_pytorch'"
**Solution**:
- This shouldn't happen in Docker images (IPEX is pre-installed)
- If running locally, install: `pip install intel-extension-for-pytorch`

## NPU Support (Experimental)

### Intel NPU Overview

Intel NPUs (Neural Processing Units) are dedicated AI accelerators available in recent Intel processors:
- **Intel Core Ultra (Meteor Lake)**: 14th gen mobile processors with NPU 3720
- **Intel Core Ultra Series 2 (Lunar Lake)**: Newer mobile processors with NPU 4 (up to 48 TOPS)
- **Future Intel CPUs**: Arrow Lake and beyond

NPUs provide power-efficient AI acceleration but have different characteristics from GPUs:
- **Lower power consumption**: Ideal for laptops and mobile devices
- **Lower performance**: ~10-48 TOPS vs ~200+ TFLOPS for GPUs
- **Limited operation support**: Not all PyTorch operations work on NPU
- **Best for inference**: Optimised for running pre-trained models, not training

### Checking NPU Availability

**Windows:**
```powershell
# Check Device Manager
# Look for "Neural Processors" under "System devices"

# Or use PowerShell
Get-PnpDevice | Where-Object {$_.FriendlyName -like "*NPU*"}
```

**Linux:**
```bash
# Check for NPU device
ls -la /dev/accel*

# Check Intel compute runtime
clinfo | grep -i npu

# Verify NPU is recognized
lspci | grep -i "AI\|NPU"
```

### NPU Driver Installation

**Windows:**
```powershell
# Install Intel NPU Driver
# Download from Intel's website or use Windows Update
# Driver version 31.0.100.5590 or newer

# Verify installation
devcon status "*NPU*"
```

**Linux (Ubuntu 22.04+):**
```bash
# Add Intel package repository
wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | sudo gpg --dearmor --output /usr/share/keyrings/intel-graphics.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy client" | sudo tee /etc/apt/sources.list.d/intel-gpu-jammy.list

# Install NPU drivers and runtime
sudo apt update
sudo apt install -y \
    intel-level-zero-npu \
    intel-driver-compiler-npu \
    level-zero

# Verify installation
ls -la /dev/accel*
```

### Running with NPU (Docker)

Intel NPU requires passing the NPU device to Docker:

```bash
# Run with NPU device
docker run \
  --device=/dev/accel/accel0 \
  -e USE_GPU=true \
  -e DEVICE=xpu:0 \
  -p 8000:8000 \
  scottgal/mostlylucid-nmt:intel-min
```

**Note**: Current Intel Extension for PyTorch (IPEX) treats NPU as an XPU device. The application will attempt to use it automatically if detected.

### NPU-Specific Configuration

```bash
# Enable NPU explicitly (when both iGPU and NPU available)
DEVICE=xpu:0  # May select NPU if it's the first XPU device

# Reduce batch size for NPU (lower memory than GPU)
EASYNMT_BATCH_SIZE=16

# FP16 may not be supported on all NPU operations
EASYNMT_MODEL_ARGS='{"torch_dtype":"fp32"}'

# Smaller model cache for NPU
MAX_CACHED_MODELS=3
```

### NPU Limitations

Current limitations of NPU support:
1. **Limited PyTorch operation support**: Not all transformer operations work on NPU
2. **FP16 support varies**: Some NPU models require FP32
3. **Slower than dedicated GPUs**: NPUs are power-efficient but not as fast as discrete GPUs
4. **Fallback behavior**: Most models will use iGPU or CPU if NPU cannot handle all operations
5. **Driver maturity**: NPU drivers and IPEX support are actively evolving

### NPU vs iGPU vs dGPU

| Feature | NPU | Intel iGPU (Iris Xe) | Intel dGPU (Arc) |
|---------|-----|----------------------|------------------|
| Power Consumption | 5-15W | 15-30W | 50-200W |
| Performance | 10-48 TOPS | ~2-5 TFLOPS | ~10-30 TFLOPS |
| Best For | Lightweight inference | Balanced workloads | Heavy inference |
| Availability | Laptops (Core Ultra) | Most Intel CPUs | Add-in cards |
| Translation Speed | 10-20 sent/s | 15-30 sent/s | 20-40 sent/s |

**Recommendation**: For translation workloads:
- **NPU**: Good for low-power devices, simple models
- **iGPU**: Better balanced performance/power
- **dGPU (Arc)**: Best performance for dedicated translation server

### Testing NPU

```bash
# Build Intel image
docker build -f Dockerfile.intel.min -t nmt-intel .

# Run with NPU device
docker run \
  --device=/dev/accel/accel0 \
  -e USE_GPU=true \
  -e EASYNMT_BATCH_SIZE=16 \
  -p 8000:8000 \
  nmt-intel

# Check which device is being used
curl http://localhost:8000/readyz | jq

# Expected output includes device info:
# {
#   "status": "ready",
#   "device": "xpu:0",  # NPU if detected first
#   "device_type": "xpu"
# }

# Test translation
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text": ["Hello NPU world"], "target_lang": "de"}'
```

### Troubleshooting NPU

**Issue**: NPU not detected
```bash
# Check NPU device exists
ls -la /dev/accel*

# Check permissions
sudo chmod 666 /dev/accel/accel0

# Verify Intel compute runtime
clinfo | grep -i npu
```

**Issue**: "Operation not supported on NPU"
```bash
# Fallback to CPU/iGPU will happen automatically
# Check logs:
docker logs <container-id>

# Look for messages like:
# "WARNING: NPU operation not supported, using fallback"
```

**Issue**: Slower than expected
```bash
# NPUs are slower than GPUs for transformers
# Try smaller models or reduce batch size
EASYNMT_BATCH_SIZE=8
MAX_CACHED_MODELS=2
```

### NPU Development Status

Intel NPU support in PyTorch is evolving:
- **Current (2025)**: Basic inference support via IPEX
- **Near future**: Better operation coverage, FP16 support
- **Long term**: Native PyTorch NPU backend, improved performance

For production use, Intel Arc GPUs (dGPU) or iGPU provide more stable performance currently. NPU is best for:
- Power-constrained devices (laptops)
- Simple models
- Experimental deployments

Monitor Intel's IPEX releases for NPU improvements: https://github.com/intel/intel-extension-for-pytorch

## Code Changes

The following files were modified to support multi-vendor GPUs:

1. **src/core/device.py**: Multi-vendor GPU detection
   - Detects NVIDIA CUDA, AMD ROCm, Intel XPU
   - Returns appropriate device strings (`cuda:0`, `xpu:0`)
   - Logs vendor-specific GPU information

2. **src/core/cache.py**: GPU memory management
   - Clears CUDA cache for NVIDIA/AMD
   - Clears XPU cache for Intel GPUs
   - Automatic memory cleanup on model eviction

3. **Dockerfiles**: New images for ROCm and Intel
   - `Dockerfile.rocm` / `Dockerfile.rocm.min`
   - `Dockerfile.intel` / `Dockerfile.intel.min`
   - Vendor-specific base images and dependencies

## Testing

### Test AMD ROCm
```bash
# Build
docker build -f Dockerfile.rocm.min -t test-rocm .

# Run with AMD GPU
docker run --device=/dev/kfd --device=/dev/dri -p 8000:8000 test-rocm

# Test translation
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text": ["Hello world"], "target_lang": "de"}'

# Check device info
curl http://localhost:8000/readyz
```

### Test Intel GPU
```bash
# Build
docker build -f Dockerfile.intel.min -t test-intel .

# Run with Intel GPU
docker run --device=/dev/dri -p 8000:8000 test-intel

# Test translation
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text": ["Hello world"], "target_lang": "de"}'

# Check device info
curl http://localhost:8000/readyz
```

## Roadmap

- [ ] Add Apple Metal (MPS) support for Mac
- [ ] Optimize Intel NPU support when PyTorch backend is stable
- [ ] Add Qualcomm Hexagon NPU support
- [ ] Benchmark all GPU vendors with standardised test suite
- [ ] Add GPU vendor comparison to documentation

## References

- [AMD ROCm Documentation](https://rocm.docs.amd.com/)
- [Intel Extension for PyTorch](https://intel.github.io/intel-extension-for-pytorch/)
- [PyTorch Device Management](https://pytorch.org/docs/stable/notes/cuda.html)
