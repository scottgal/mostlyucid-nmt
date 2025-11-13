# Time-Based Model Eviction (Idle Timeout)

## Overview

The translation service now supports automatic eviction of cached models that haven't been used for a configurable period. This feature helps optimize memory usage by automatically unloading models that are no longer actively needed.

## How It Works

### Access Tracking

Every cached model has its access time tracked:
- **Last Access Time**: Updated whenever a model is loaded (`put`) or used (`get`)
- **Idle Duration**: Current time minus last access time
- **Timeout Threshold**: Configurable via `MODEL_IDLE_TIMEOUT`

### Background Task

A maintenance task runs periodically to check for idle models:
- Checks every `IDLE_CHECK_INTERVAL` seconds (default: 60)
- Evicts models where `idle_duration > MODEL_IDLE_TIMEOUT`
- Cleans up GPU memory after evictions
- Logs eviction activities

### Integration with Existing Eviction

The idle timeout eviction works alongside existing eviction mechanisms:
1. **LRU Eviction**: When cache reaches `MAX_CACHED_MODELS` capacity
2. **Memory Pressure Eviction**: When RAM/VRAM exceeds critical thresholds
3. **Idle Timeout Eviction**: When models haven't been used for `MODEL_IDLE_TIMEOUT` seconds

All three mechanisms coexist and operate independently.

## Configuration

### Environment Variables

```bash
# Time-based eviction settings
MODEL_IDLE_TIMEOUT=3600      # Evict models idle for 1 hour (0 = disabled)
IDLE_CHECK_INTERVAL=60       # Check for idle models every 60 seconds

# Existing cache settings (still apply)
MAX_CACHED_MODELS=10         # Maximum models in cache (LRU eviction)
ENABLE_MEMORY_MONITOR=1      # Memory-based eviction
MEMORY_CRITICAL_THRESHOLD=90 # Auto-evict at 90% RAM
```

### Configuration Details

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MODEL_IDLE_TIMEOUT` | int | 0 (disabled) | Seconds before evicting idle models. Set to 0 to disable. |
| `IDLE_CHECK_INTERVAL` | int | 60 | How often to check for idle models (seconds). Only active if `MODEL_IDLE_TIMEOUT > 0`. |

## Usage Examples

### Example 1: Evict Models After 30 Minutes

```bash
docker run --gpus all \
  -e USE_GPU=true \
  -e MODEL_IDLE_TIMEOUT=1800 \
  -e IDLE_CHECK_INTERVAL=300 \
  -p 8000:8000 \
  mostlylucid-nmt:gpu
```

- Models idle for 30+ minutes will be evicted
- Check runs every 5 minutes
- Useful for services with sporadic usage patterns

### Example 2: Aggressive Eviction (5 Minutes)

```bash
docker run --gpus all \
  -e USE_GPU=true \
  -e MODEL_IDLE_TIMEOUT=300 \
  -e IDLE_CHECK_INTERVAL=60 \
  -p 8000:8000 \
  mostlylucid-nmt:gpu
```

- Models idle for 5+ minutes will be evicted
- Check runs every minute
- Useful for memory-constrained environments

### Example 3: Disabled (Default Behavior)

```bash
docker run --gpus all \
  -e USE_GPU=true \
  -e MODEL_IDLE_TIMEOUT=0 \
  -p 8000:8000 \
  mostlylucid-nmt:gpu
```

- Idle eviction disabled
- Models only evicted by LRU or memory pressure
- Useful when models are frequently reused

## Logs and Monitoring

### Startup Logs

When idle eviction is enabled:
```
⏰ Idle model eviction enabled: 3600s timeout (check every 60s)
Maintenance task started (interval: 60s, CUDA clearing: False, idle eviction: 3600s)
```

When disabled:
```
⏰ Idle model eviction disabled (MODEL_IDLE_TIMEOUT=0)
```

### Runtime Logs

When idle models are evicted:
```
⏰ Found 2 idle models (timeout: 3600s)
⏰ Evicted idle model: en->fr (idle for 62m 15s)
⏰ Evicted idle model: de->en (idle for 75m 42s)
⏰ Idle eviction complete: 2 models evicted (3/10 remaining)
```

### Monitoring via `/cache` Endpoint

```bash
curl http://localhost:8000/cache
```

Response includes current cache state:
```json
{
  "capacity": 10,
  "size": 3,
  "keys": ["en->de", "en->es", "fr->en"],
  "utilization": "3/10 (30%)",
  "system_memory": {
    "percentage": 65.2,
    "used_gb": 10.4,
    "total_gb": 16.0,
    "status": "ok"
  }
}
```

## Use Cases

### 1. Multi-Language API with Sporadic Usage

**Scenario**: Service supporting 50+ language pairs, but only 5-10 actively used at any time

**Configuration**:
```bash
MAX_CACHED_MODELS=15
MODEL_IDLE_TIMEOUT=1800  # 30 minutes
IDLE_CHECK_INTERVAL=300   # 5 minutes
```

**Benefit**: Keeps frequently used models hot, evicts rarely used ones

### 2. Development/Testing Environment

**Scenario**: Developer testing multiple translation pairs, switching frequently

**Configuration**:
```bash
MAX_CACHED_MODELS=5
MODEL_IDLE_TIMEOUT=600   # 10 minutes
IDLE_CHECK_INTERVAL=120  # 2 minutes
```

**Benefit**: Balances quick model switching with memory conservation

### 3. Production Service with Predictable Patterns

**Scenario**: Service handling EN↔DE and EN↔FR primarily, occasional other pairs

**Configuration**:
```bash
MAX_CACHED_MODELS=10
MODEL_IDLE_TIMEOUT=7200  # 2 hours
IDLE_CHECK_INTERVAL=600   # 10 minutes
PRELOAD_MODELS="en->de,de->en,en->fr,fr->en"
```

**Benefit**: Core models stay loaded, occasional pairs evicted after 2 hours

### 4. Memory-Constrained Environment

**Scenario**: Running on a system with limited RAM/VRAM

**Configuration**:
```bash
MAX_CACHED_MODELS=3
MODEL_IDLE_TIMEOUT=300   # 5 minutes
IDLE_CHECK_INTERVAL=60   # 1 minute
MEMORY_CRITICAL_THRESHOLD=85  # Aggressive memory management
```

**Benefit**: Maximizes available memory, evicts idle models quickly

## Performance Considerations

### Memory Savings

- **Opus-MT models**: ~300MB-1GB each
- **mBART50**: ~2.3GB (single model for all pairs)
- **M2M100**: ~2.5GB (single model for all pairs)

Example: With 10 idle Opus-MT models evicted:
- **Memory freed**: 3-10GB RAM/VRAM
- **Reload time**: 10-30s per model when needed again

### Trade-offs

| Shorter Timeout (e.g., 5 minutes) | Longer Timeout (e.g., 2 hours) |
|-------------------------------------|----------------------------------|
| ✅ Maximizes memory availability | ✅ Minimizes model reload overhead |
| ✅ Good for sporadic usage | ✅ Good for bursty traffic patterns |
| ❌ More frequent model reloads | ❌ Higher memory usage |
| ❌ Increased latency on cold requests | ❌ Risk of OOM on memory-constrained systems |

### Check Interval Impact

- **Lower interval** (e.g., 30s): More responsive, slightly higher CPU usage
- **Higher interval** (e.g., 300s): More efficient, models may stay longer than timeout

Recommended: `IDLE_CHECK_INTERVAL = MODEL_IDLE_TIMEOUT / 6` (check ~6 times during timeout period)

## Technical Details

### Implementation

The feature is implemented in:
- **`src/core/cache.py`**: `LRUPipelineCache.evict_idle_models()`
- **`src/app.py`**: `_maintenance_task()` background task
- **`src/config.py`**: Configuration variables

### Access Time Tracking

```python
# Tracked in LRUPipelineCache
self.last_access_times: dict[str, float] = {}

# Updated on get()
self.last_access_times[key] = time.time()

# Updated on put()
self.last_access_times[key] = time.time()

# Cleaned up on eviction
self.last_access_times.pop(key, None)
```

### Eviction Logic

```python
def evict_idle_models(self, timeout_seconds: int) -> List[str]:
    current_time = time.time()
    evicted_keys = []

    for key in list(self.keys()):
        last_access = self.last_access_times.get(key, 0)
        idle_duration = current_time - last_access

        if idle_duration > timeout_seconds:
            # Evict model and clean up GPU memory
            val = self.pop(key)
            self.last_access_times.pop(key, None)
            evicted_keys.append(key)

            if hasattr(val, "model"):
                val.model.cpu()
            del val

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return evicted_keys
```

## Testing

Run the test suite:
```bash
pytest tests/test_cache_idle_eviction.py -v
```

Test coverage includes:
- ✅ Disabled timeout (0) does nothing
- ✅ Recently accessed models not evicted
- ✅ Old models evicted correctly
- ✅ Access time tracking cleaned up
- ✅ Getting a model updates its access time
- ✅ Idle and LRU eviction work together
- ✅ Empty cache doesn't error

## Troubleshooting

### Models Not Being Evicted

**Symptom**: Models stay in cache longer than `MODEL_IDLE_TIMEOUT`

**Possible Causes**:
1. `MODEL_IDLE_TIMEOUT=0` (feature disabled)
2. Models are being accessed more frequently than expected
3. `IDLE_CHECK_INTERVAL` is too large

**Solution**:
```bash
# Check configuration
docker exec <container> env | grep -E '(MODEL_IDLE_TIMEOUT|IDLE_CHECK_INTERVAL)'

# Check logs
docker logs <container> | grep -E '(idle|Idle)'
```

### Excessive Model Reloads

**Symptom**: High latency, frequent model loading logs

**Possible Causes**:
1. `MODEL_IDLE_TIMEOUT` too short for usage pattern
2. `IDLE_CHECK_INTERVAL` too frequent

**Solution**:
```bash
# Increase timeout
-e MODEL_IDLE_TIMEOUT=3600  # 1 hour instead of 5 minutes

# Reduce check frequency
-e IDLE_CHECK_INTERVAL=300   # 5 minutes instead of 1 minute
```

### Memory Still Too High

**Symptom**: High memory usage despite idle eviction

**Possible Causes**:
1. `MAX_CACHED_MODELS` too high
2. Models are frequently accessed (not idle)
3. Memory leak elsewhere

**Solution**:
```bash
# Reduce max cache size
-e MAX_CACHED_MODELS=5

# More aggressive memory monitoring
-e MEMORY_CRITICAL_THRESHOLD=80

# More aggressive idle timeout
-e MODEL_IDLE_TIMEOUT=300  # 5 minutes
```

## FAQ

**Q: Does this replace LRU eviction?**
A: No, both work together. LRU evicts when cache is full, idle timeout evicts based on time.

**Q: What happens if a model is evicted while in use?**
A: Models are only evicted by the background task between requests. Active translations are never interrupted.

**Q: Can I disable idle eviction?**
A: Yes, set `MODEL_IDLE_TIMEOUT=0` (default).

**Q: Does this work on CPU?**
A: Yes, it works on both CPU and GPU.

**Q: How does this affect preloaded models?**
A: Preloaded models are subject to idle eviction like any other model.

**Q: Can I manually trigger eviction?**
A: Not via API, but the maintenance task runs automatically based on `IDLE_CHECK_INTERVAL`.

## Best Practices

1. **Start Conservative**: Begin with longer timeouts (1-2 hours) and adjust based on monitoring
2. **Match Usage Patterns**: Use shorter timeouts for sporadic usage, longer for steady traffic
3. **Monitor Logs**: Watch for eviction patterns and adjust accordingly
4. **Balance with LRU**: Set `MAX_CACHED_MODELS` to handle burst traffic, use idle timeout for cleanup
5. **Test in Development**: Experiment with aggressive timeouts in dev to understand reload overhead
6. **Combine with Memory Monitoring**: Use both idle timeout and memory-based eviction for robustness

## Related Configuration

- `MAX_CACHED_MODELS`: LRU cache capacity
- `ENABLE_MEMORY_MONITOR`: Enable/disable memory-based eviction
- `MEMORY_CRITICAL_THRESHOLD`: Auto-evict when RAM exceeds this %
- `GPU_MEMORY_CRITICAL_THRESHOLD`: Auto-evict when VRAM exceeds this %
- `CUDA_CACHE_CLEAR_INTERVAL_SEC`: Periodic CUDA cache clearing

## See Also

- Main README: [README.md](README.md)
- Configuration Guide: [CLAUDE.md](CLAUDE.md)
- Cache Implementation: [src/core/cache.py](src/core/cache.py)
- Test Suite: [tests/test_cache_idle_eviction.py](tests/test_cache_idle_eviction.py)
