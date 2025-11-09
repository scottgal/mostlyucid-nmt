# Running on Raspberry Pi

This guide covers deploying mostlylucid-nmt on Raspberry Pi (ARM64 architecture).

## Requirements

### Hardware
- **Raspberry Pi 5 with 8GB RAM + NVMe SSD** (HIGHLY recommended)
  - NVMe SSD via HAT is **critical** for good performance (10x faster than SD card)
  - Active cooling required (CPU-intensive workload)
  - Official 27W power supply

- **Raspberry Pi 4 with 8GB RAM + SSD** (acceptable performance)
  - USB 3.0 SSD is **highly recommended** over SD card
  - Active cooling recommended

- **Raspberry Pi 3B+** (supported but slow)
  - Minimum 1GB RAM (very limited capacity)
  - Expect slower translations

### Software
- Raspberry Pi OS (64-bit) - **Bookworm or newer**
- Docker installed
- Docker Compose (optional but recommended)

## Quick Start

### 1. Install Docker (if not already installed)

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect
```

### 2. Pull Pre-built Image

```bash
# Pull multi-platform image - Docker automatically selects ARM64 on Raspberry Pi
docker pull scottgal/mostlylucid-nmt:latest
```

### 3. Run with Docker Compose (Recommended)

```bash
# Clone repository
git clone https://github.com/scottgal/mostlylucid-nmt.git
cd mostlylucid-nmt

# Create model cache directory
mkdir -p model-cache

# Start service
docker-compose -f docker-compose-arm64.yml up -d

# View logs
docker-compose -f docker-compose-arm64.yml logs -f
```

### 4. Or Run Directly

```bash
# Docker automatically selects the ARM64 version on Raspberry Pi
docker run -d \
  --name translation \
  --restart unless-stopped \
  -p 8000:8000 \
  -v $(pwd)/model-cache:/models \
  -e MODEL_CACHE_DIR=/models \
  -e MAX_CACHED_MODELS=2 \
  -e EASYNMT_BATCH_SIZE=4 \
  scottgal/mostlylucid-nmt:latest
```

## Building Locally on Raspberry Pi

If you want to build the image yourself:

```bash
# Clone repository
git clone https://github.com/scottgal/mostlylucid-nmt.git
cd mostlylucid-nmt

# Build ARM64 image (creates local tags)
chmod +x build-arm64.sh
./build-arm64.sh

# Run the locally built image
docker run -d \
  --name translation \
  -p 8000:8000 \
  -v $(pwd)/model-cache:/models \
  -e MODEL_CACHE_DIR=/models \
  mostlylucid-nmt:pi
```

**Note**: The build script creates multiple tags:
- `mostlylucid-nmt:pi` - Recommended for Raspberry Pi
- `mostlylucid-nmt:arm64` - Also works (same image)
- `mostlylucid-nmt:pi-YYYYMMDD.HHMMSS` - Versioned tag

## Performance Expectations

### Raspberry Pi 5 (8GB)
- **Translation speed**: ~5-10 words/second
- **First request**: 30-60 seconds (model download + load)
- **Subsequent requests**: 2-5 seconds (cached model)
- **Concurrent users**: 1-2 comfortably
- **Recommended**: en↔de, en↔fr, en↔es (common pairs)

### Raspberry Pi 4 (4GB)
- **Translation speed**: ~3-7 words/second
- **First request**: 45-90 seconds
- **Subsequent requests**: 3-8 seconds
- **Concurrent users**: 1
- **Recommended**: Keep MAX_CACHED_MODELS=1

### Raspberry Pi 4 (2GB)
- **Translation speed**: ~2-5 words/second
- **First request**: 60-120 seconds
- **Concurrent users**: 1
- **Recommended**: Opus-MT only, single model cache
- **Warning**: May struggle with large texts

## Optimizations for Pi

### 1. Reduce Memory Usage

```yaml
# In docker-compose-arm64.yml or as env vars
MAX_CACHED_MODELS: "1"           # Cache only 1 model
EASYNMT_BATCH_SIZE: "2"          # Smaller batches
MEMORY_CRITICAL_THRESHOLD: "80.0" # Aggressive eviction
```

### 2. Use Swap (if needed)

```bash
# Increase swap size for 2GB Pi models
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Set CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### 3. Use SSD Instead of SD Card

```bash
# Much faster model loading
# Boot from USB SSD for best performance
# See: https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#usb-boot
```

### 4. Preload Only Essential Models

```bash
# Preload just one language pair
docker run -d \
  -e PRELOAD_MODELS="en->de" \
  -e MAX_CACHED_MODELS=1 \
  ...
```

### 5. Enable Active Cooling

- Use a case with fan
- Or Raspberry Pi official cooler
- Prevents thermal throttling during heavy translation loads

## Memory Management

The ARM64 image has aggressive memory monitoring enabled by default:

```bash
# These are pre-configured for Pi
ENABLE_MEMORY_MONITOR=1
MEMORY_WARNING_THRESHOLD=75.0    # Warn at 75% RAM
MEMORY_CRITICAL_THRESHOLD=85.0   # Auto-evict at 85%
MEMORY_CHECK_INTERVAL=3          # Check every 3 operations
```

When RAM gets low, the service automatically:
1. Warns at 75% usage
2. Evicts oldest model at 85% usage
3. Evicts ALL models at 95% (emergency)

This prevents OOM crashes and keeps your Pi stable!

## Monitoring

### Check Service Status

```bash
# Health check
curl http://localhost:8000/healthz

# Cache status (includes RAM usage!)
curl http://localhost:8000/cache | jq

# System resources
docker stats translation
```

### View Logs

```bash
# With docker-compose
docker-compose -f docker-compose-arm64.yml logs -f

# Or directly
docker logs -f translation
```

### Monitor System

```bash
# CPU and memory
htop

# Temperature (important!)
vcgencmd measure_temp

# Throttling status
vcgencmd get_throttled
```

## Common Issues

### Issue: First translation takes forever

**Solution**: Models are being downloaded. Check logs:

```bash
docker logs -f translation
```

You'll see download progress. First model can take 2-5 minutes on Pi.

### Issue: Out of memory errors

**Solutions**:

```bash
# 1. Reduce cache size
docker run -e MAX_CACHED_MODELS=1 ...

# 2. Lower batch size
docker run -e EASYNMT_BATCH_SIZE=2 ...

# 3. Use only opus-mt (smaller models)
docker run -e MODEL_FAMILY=opus-mt ...

# 4. Increase swap space (see above)
```

### Issue: Service is slow/unresponsive

**Solutions**:

```bash
# Check CPU temperature
vcgencmd measure_temp

# If >70°C, add cooling or reduce load
# Check if throttled
vcgencmd get_throttled
# 0x0 = OK, anything else = throttled

# Reduce concurrent requests
docker run -e MAX_INFLIGHT_TRANSLATIONS=1 ...
```

### Issue: SD card running out of space

**Solutions**:

```bash
# 1. Clean up old Docker images
docker system prune -a

# 2. Move model cache to external drive
docker run -v /mnt/external/models:/models ...

# 3. Use minimal base image (already done in ARM64 build)
```

## Recommended Settings by Pi Model

### Raspberry Pi 5 (8GB)
```yaml
MAX_CACHED_MODELS: "3"
EASYNMT_BATCH_SIZE: "8"
MEMORY_CRITICAL_THRESHOLD: "85.0"
MAX_INFLIGHT_TRANSLATIONS: "2"
```

### Raspberry Pi 4 (8GB)
```yaml
MAX_CACHED_MODELS: "2"
EASYNMT_BATCH_SIZE: "6"
MEMORY_CRITICAL_THRESHOLD: "85.0"
MAX_INFLIGHT_TRANSLATIONS: "1"
```

### Raspberry Pi 4 (4GB)
```yaml
MAX_CACHED_MODELS: "1"
EASYNMT_BATCH_SIZE: "4"
MEMORY_CRITICAL_THRESHOLD: "80.0"
MAX_INFLIGHT_TRANSLATIONS: "1"
```

### Raspberry Pi 4 (2GB)
```yaml
MAX_CACHED_MODELS: "1"
EASYNMT_BATCH_SIZE: "2"
MEMORY_CRITICAL_THRESHOLD: "75.0"
MAX_INFLIGHT_TRANSLATIONS: "1"
MODEL_FAMILY: "opus-mt"  # Only opus-mt
```

## Production Tips

### 1. Use systemd for auto-restart

```bash
# Create systemd service
sudo nano /etc/systemd/system/translation.service
```

```ini
[Unit]
Description=Translation Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/pi/mostlylucid-nmt
ExecStart=/usr/bin/docker-compose -f docker-compose-arm64.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose-arm64.yml down
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable translation
sudo systemctl start translation
```

### 2. Set up log rotation

```bash
# Docker handles this, but ensure limits
docker run --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  ...
```

### 3. Use nginx reverse proxy

```bash
sudo apt-get install nginx

# Configure nginx for caching and rate limiting
sudo nano /etc/nginx/sites-available/translation
```

```nginx
server {
    listen 80;
    server_name translation.local;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # Rate limiting
        limit_req zone=translation burst=5;
    }
}
```

### 4. Monitor with Prometheus (optional)

The service exposes metrics at `/cache` - you can scrape these with Prometheus running on Pi.

## Accessing the Service

### Local Network
```bash
# From other devices on your network
http://<pi-ip-address>:8000/demo
```

### Find your Pi's IP
```bash
hostname -I
```

### Make it accessible
```bash
# Port forward on your router
# Or use ngrok/cloudflare tunnel for internet access
```

## Next Steps

- Visit http://localhost:8000/demo for interactive UI
- Check API docs at http://localhost:8000/docs
- Monitor cache/memory at http://localhost:8000/cache
- See main README.md for API usage examples

## Performance Optimizations

The ARM64 image includes comprehensive optimizations specifically for Raspberry Pi:

- **Memory-mapped model loading** - Models stay on SSD, paged into RAM on-demand (requires SSD!)
- **Aggressive memory monitoring** - Auto-evicts at 70% RAM (down from 85%)
- **CPU thread tuning** - Optimal thread counts for ARM Cortex CPUs
- **Streaming downloads** - Models download directly to SSD without RAM buffering
- **Garbage collection** - Aggressive cleanup after evictions

**For detailed explanation of all optimizations, see [RASPBERRY-PI-OPTIMIZATIONS.md](RASPBERRY-PI-OPTIMIZATIONS.md)**

### Quick Performance Tips

1. **Use SSD, not SD card** - 10x faster model loading and inference
2. **Keep 1 model cached** - `MAX_CACHED_MODELS=1` is optimal for 8GB RAM
3. **Use mBART50 for multiple languages** - Single 2GB model vs many Opus-MT models
4. **Monitor temperature** - `vcgencmd measure_temp` (keep <70°C)
5. **Check memory** - `curl http://localhost:8000/cache` (RAM should be <70%)

## Support

- **Performance issues**: See [RASPBERRY-PI-OPTIMIZATIONS.md](RASPBERRY-PI-OPTIMIZATIONS.md)
- **Hardware issues**: Check temperature, ensure SSD is used, verify active cooling
- **Translation issues**: See main README troubleshooting
- **Memory issues**: Lower thresholds, reduce cache size, use mBART50

Happy translating on your Raspberry Pi! 🥧🤖
