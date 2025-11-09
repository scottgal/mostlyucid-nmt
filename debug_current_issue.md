# Debug Current Issue

Please share:

1. **What you tested:**
   - URL/curl command you used
   - Expected result
   - Actual result

2. **Current error logs:**
   ```bash
   docker logs $(docker ps -q) --tail 50
   ```

3. **What's "closer":**
   - What works now that didn't before?
   - What still doesn't work?

4. **Did you rebuild?**
   - Yes/No
   - When?
   - Which Dockerfile? (Dockerfile.gpu or Dockerfile?)

---

## Quick Checks:

### Check if new code is running:
```bash
# Should show protobuf in the list
docker exec $(docker ps -q) pip list | grep protobuf
```

### Check if translations work:
```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text": ["Hello world"], "target_lang": "de", "source_lang": "en"}'
```

### Check cache keys:
```bash
curl http://localhost:8000/cache
```

---

## Common Issues After Rebuild:

### Issue 1: Still showing old error
**Cause**: Container wasn't rebuilt or wrong container is running
**Fix**: `docker ps` - check IMAGE column, should show recent build time

### Issue 2: Model family not changing
**Cause**: Browser cache, old JavaScript
**Fix**: Hard refresh (Ctrl+F5) or clear browser cache

### Issue 3: Still getting empty translations
**Cause**: Old container still running
**Fix**: `docker stop $(docker ps -q)` then restart

### Issue 4: protobuf still missing
**Cause**: Build cache using old requirements.txt
**Fix**: `docker build --no-cache -f Dockerfile.gpu -t mostlylucid-nmt:gpu .`

---

Please share the specific error you're seeing!
