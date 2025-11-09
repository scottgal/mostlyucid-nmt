# k6 Load Testing Guide

## Installation

### Windows (using Chocolatey):
```powershell
choco install k6
```

### Windows (using Winget):
```powershell
winget install k6 --source winget
```

### Windows (manual download):
1. Download from: https://dl.k6.io/msi/k6-latest-amd64.msi
2. Run the installer
3. Open a new terminal

### Verify installation:
```bash
k6 version
```

## Running the Load Test

### Prerequisites:
1. **Start the translation server**:
   ```bash
   uvicorn src.app:app --host 0.0.0.0 --port 8000
   ```

2. **Verify it's running**:
   ```bash
   curl http://localhost:8000/healthz
   ```
   Should return: `{"status":"ok"}`

### Run the test:

**From project root**:
```bash
# Quick smoke test (1 user, 30 seconds)
k6 run --vus 1 --duration 30s tests/k6-load-test.js

# Moderate load test (10 users, 2 minutes)
k6 run --vus 10 --duration 2m tests/k6-load-test.js

# Use custom stages (defined in script)
k6 run tests/k6-load-test.js

# Test against different host
k6 run -e BASE_URL=http://192.168.1.100:8000 tests/k6-load-test.js
```

**From tests directory**:
```bash
cd tests
k6 run --vus 1 --duration 30s k6-load-test.js
```

## Common Issues

### Issue 1: "k6: command not found"
**Solution**: k6 is not installed or not in PATH
- Reinstall k6
- Close and reopen terminal
- Check: `k6 version`

### Issue 2: "API not available at http://localhost:8000"
**Solution**: Translation server is not running
- Start server: `uvicorn src.app:app --port 8000`
- Check: `curl http://localhost:8000/healthz`

### Issue 3: Parse errors in JavaScript
**Solution**: Make sure you're using the fixed version
- The script should import: `import { textSummary } from 'k6/summary';`
- Update k6 to latest: `choco upgrade k6` or download new version

### Issue 4: High error rates during test
**Solution**: Server may be overloaded or models not cached
- Preload models first (make a few manual requests)
- Reduce VUs: `--vus 1` or `--vus 2`
- Check server logs for errors

### Issue 5: Tests timeout
**Solution**: Translations may be slow (model downloads, CPU mode, etc.)
- First run downloads models (will be slow)
- Subsequent runs use cached models (faster)
- Increase timeout in script if needed

## Understanding Results

### Key Metrics:

```
checks.........................: 100.00% ✓ 450      ✗ 0
http_req_duration..............: avg=1.2s   p95=2.3s
http_req_failed................: 0.00%   ✓ 0        ✗ 450
http_reqs......................: 450     15/s
translation_errors.............: 0.00%
translated_chars...............: 25000   (total characters)
vus............................: 10      (concurrent users)
```

**Good indicators**:
- ✅ `checks: 100%` - All validations passed
- ✅ `http_req_failed: 0%` - No HTTP errors
- ✅ `translation_errors: 0%` - No empty translations
- ✅ `http_req_duration p95 < 5s` - Fast responses

**Warning signs**:
- ⚠️ `checks < 95%` - Some requests failing validation
- ⚠️ `http_req_failed > 5%` - Many HTTP errors (429, 503, 500)
- ⚠️ `translation_errors > 5%` - Empty translations
- ⚠️ `http_req_duration p95 > 10s` - Very slow responses

## Example Output

```
     ✓ status is 200
     ✓ has translated field
     ✓ translation not empty
     ✓ response time < 10s

     checks.........................: 100.00% ✓ 245      ✗ 0
     data_received..................: 127 kB  4.2 kB/s
     data_sent......................: 64 kB   2.1 kB/s
     http_req_blocked...............: avg=1.23ms  min=0s     med=0s      max=15.2ms
     http_req_connecting............: avg=412µs   min=0s     med=0s      max=5.1ms
     http_req_duration..............: avg=1.85s   min=245ms  med=1.6s    max=4.2s
       { expected_response:true }...: avg=1.85s   min=245ms  med=1.6s    max=4.2s
     http_req_failed................: 0.00%   ✓ 0        ✗ 245
     http_req_receiving.............: avg=124µs   min=0s     med=0s      max=1.2ms
     http_req_sending...............: avg=89µs    min=0s     med=0s      max=892µs
     http_req_tls_handshaking.......: avg=0s      min=0s     med=0s      max=0s
     http_req_waiting...............: avg=1.85s   min=245ms  med=1.6s    max=4.2s
     http_reqs......................: 245     8.16/s
     iteration_duration.............: avg=3.07s   min=2.28s  med=2.89s   max=5.43s
     iterations.....................: 245     8.16/s
     pivot_translations.............: 12      0.4/s
     translated_chars...............: 18543   618.1/s
     translation_duration_ms........: avg=1847    min=245    med=1598    max=4201
     translation_errors.............: 0.00%   ✓ 0        ✗ 245
     vus............................: 10      min=5      max=10
     vus_max........................: 10      min=10     max=10
```

## Tips

1. **Start small**: Begin with 1 VU for 30s to validate everything works
2. **Preload models**: Make a few requests manually before load testing
3. **Watch logs**: Keep server logs visible: `uvicorn src.app:app --log-level info`
4. **GPU vs CPU**: GPU can handle more load, CPU will be slower
5. **Realistic load**: Real users don't send requests every second - that's why we have `sleep()`
6. **Thresholds**: Adjust thresholds in the script based on your requirements

## Troubleshooting Command

If k6 fails to parse the script, try:
```bash
# Validate the script without running
k6 inspect tests/k6-load-test.js

# Run with verbose output
k6 run -v tests/k6-load-test.js

# Check specific line
k6 run --no-summary tests/k6-load-test.js
```
