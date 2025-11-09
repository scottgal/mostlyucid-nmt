# Model Family Selection Feature

## Date: 2025-11-09

## Overview

Users can now select which model family (opus-mt, mbart50, m2m100) to use **per request** via the API and demo UI. Previously, the model family was set globally via `MODEL_FAMILY` environment variable and couldn't be changed without restarting the server.

---

## API Changes

### New Request Parameter: `model_family`

Added optional `model_family` parameter to translation requests:

```json
{
  "text": ["Hello world"],
  "target_lang": "de",
  "source_lang": "en",
  "beam_size": 5,
  "perform_sentence_splitting": true,
  "model_family": "mbart50"  // NEW! Optional
}
```

**Valid values**:
- `"opus-mt"` - Helsinki-NLP models (1200+ language pairs)
- `"mbart50"` - Facebook mBART50 (50 languages, single model)
- `"m2m100"` - Facebook M2M100 (100 languages, single model)
- `null` or omitted - Uses server's default (`MODEL_FAMILY` env var)

---

## Backend Changes

### 1. Updated Request Model

**File**: `src/models.py`

```python
class TranslatePostBody(BaseModel):
    text: Union[str, List[str]]
    target_lang: str
    source_lang: str = ""
    beam_size: int = 5
    perform_sentence_splitting: bool = True
    model_family: Optional[str] = None  # NEW!
```

---

### 2. Model Manager Updates

**File**: `src/services/model_manager.py`

**Updated method signature**:
```python
def get_pipeline(self, src: str, tgt: str, preferred_family: Optional[str] = None) -> Any:
```

**Behavior**:
1. If `preferred_family` is specified:
   - Try that family first
   - Fall back to other families if enabled (`AUTO_MODEL_FALLBACK=1`)

2. If `preferred_family` is `None`:
   - Use `MODEL_FAMILY` env var (existing behavior)

**Cache key includes family**:
```python
# Before: key = "en->de"
# After:  key = "en->de:opus-mt"
```

This allows caching different model families for the same language pair.

---

### 3. Translation Service Updates

**File**: `src/services/translation_service.py`

All translation methods now accept and pass `preferred_family`:
- `_translate_text_single()` - Added `preferred_family` parameter
- `translate_texts_aligned()` - Added `preferred_family` parameter
- `translate_async()` - Added `preferred_family` parameter

---

### 4. API Route Updates

**File**: `src/api/routes/translation.py`

The POST /translate endpoint now passes `body.model_family` to translation service:

```python
texts, pivot_used, metadata_dict = await translation_service.translate_async(
    base_texts, src, body.target_lang, eff_beam,
    perform_sentence_splitting, include_metadata,
    body.model_family  # NEW!
)
```

---

## Frontend Changes

### Demo UI Updates

**File**: `public/index.html`

The model family dropdown now actually works!

**Before** (broken):
```javascript
const body = { text: [chunks[i]], target_lang: tgt, ... };
// model_family was NEVER sent! ❌
```

**After** (fixed):
```javascript
const modelFamily = els.modelFamily.value;
const body = {
  text: [chunks[i]],
  target_lang: tgt,
  model_family: modelFamily  // ✅ Now sent!
};
```

**Updated help text**:
> "You can select which model family to use for translation above. The server will use your selection or fall back to alternatives if the selected family doesn't support the language pair."

---

## Usage Examples

### API Request with Model Family

```bash
# Use mBART50 for translation
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{
    "text": ["Hello world"],
    "target_lang": "de",
    "source_lang": "en",
    "model_family": "mbart50"
  }'
```

### API Request without Model Family

```bash
# Use server default (MODEL_FAMILY env var)
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{
    "text": ["Hello world"],
    "target_lang": "de",
    "source_lang": "en"
  }'
```

---

## Demo UI Usage

1. **Open demo**: Navigate to `http://localhost:8000/demo/`
2. **Select model family**: Use dropdown at top (Opus‑MT, mBART50, or M2M100)
3. **Enter text** and select languages
4. **Click "Translate"** - The selected model family will be used!

---

## Model Family Characteristics

| Family | Languages | Model Count | Size | Best For |
|--------|-----------|-------------|------|----------|
| **opus-mt** | 150+ | 1200+ pairs (separate models) | ~300 MB per pair | High quality, specific pairs |
| **mbart50** | 50 | 1 model (all pairs) | ~2.3 GB | Medium quality, all-to-all |
| **m2m100** | 100 | 1 model (all pairs) | ~1.6 GB | Broad coverage, all-to-all |

---

## Fallback Behavior

If the selected model family doesn't support a language pair:

1. **With `AUTO_MODEL_FALLBACK=1`** (default):
   - Try other families in order: `MODEL_FALLBACK_ORDER`
   - Example: Request mbart50 for en→bn, but mBART50 missing protobuf → Falls back to m2m100

2. **With `AUTO_MODEL_FALLBACK=0`**:
   - Return error if selected family can't handle the pair
   - Strict mode - only use what was requested

---

## Performance Implications

### Cache Considerations

Models are cached with family in the key:
```
Cache keys:
- "en->de:opus-mt"   ← Opus-MT model for en→de
- "en->de:mbart50"   ← mBART50 model for en→de
- "en->de:m2m100"    ← M2M100 model for en→de
```

**Same language pair, different families = separate cache entries**

This means:
- ✅ You can switch between families without evicting other models
- ⚠️ Uses more memory if you use multiple families for same pair
- ⚠️ Each family needs to be loaded on first use

### Memory Usage

Example with `MAX_CACHED_MODELS=6`:
- 2 opus-mt pairs: 600 MB
- 1 mbart50 (all 50 langs): 2.3 GB
- 1 m2m100 (all 100 langs): 1.6 GB
- **Total**: ~4.5 GB

Consider increasing `MAX_CACHED_MODELS` if using multiple families.

---

## Testing

### Test Different Families

```bash
# Test Opus-MT
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text": ["Hello"], "target_lang": "de", "source_lang": "en", "model_family": "opus-mt"}'

# Test mBART50
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text": ["Hello"], "target_lang": "de", "source_lang": "en", "model_family": "mbart50"}'

# Test M2M100
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text": ["Hello"], "target_lang": "de", "source_lang": "en", "model_family": "m2m100"}'
```

### Check Cache

```bash
curl http://localhost:8000/cache
```

You should see entries like:
```json
{
  "keys": [
    "en->de:opus-mt",
    "en->de:mbart50",
    "en->de:m2m100"
  ]
}
```

---

## Backward Compatibility

✅ **Fully backward compatible!**

- Existing requests without `model_family` work exactly as before
- Default behavior unchanged (uses `MODEL_FAMILY` env var)
- New parameter is optional
- No breaking changes to API contracts

---

## Configuration

Relevant environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_FAMILY` | `opus-mt` | Default family when not specified in request |
| `AUTO_MODEL_FALLBACK` | `1` | Enable automatic fallback to other families |
| `MODEL_FALLBACK_ORDER` | `opus-mt,mbart50,m2m100` | Fallback priority order |
| `MAX_CACHED_MODELS` | `6` | Max models in cache (consider increasing) |

---

## Benefits

1. **Flexibility**: Users can choose best model for their use case
2. **Quality vs Coverage**: Balance between high-quality opus-mt and broad-coverage m2m100
3. **A/B Testing**: Compare translations from different models
4. **Language Support**: Access more language pairs via mbart50/m2m100 when opus-mt unavailable
5. **No Restart Needed**: Change model family per request without server restart

---

## Limitations

1. **Cache Memory**: Using multiple families for same pair increases memory usage
2. **First Request Slow**: Each new family must be downloaded on first use
3. **Model Quality Varies**: Not all families perform equally well for all pairs

---

## Future Enhancements

Potential improvements:
- Return which model family was actually used in response metadata
- Add model family to response headers
- Cache warming: preload multiple families for common pairs
- Quality scoring: automatically select best family for each pair

---

## Summary

Users can now control model family selection via:
- **API**: Set `model_family` in request body
- **Demo UI**: Select from dropdown before translating
- **Default**: Omit parameter to use server's `MODEL_FAMILY` setting

This gives users full control over which translation models power their requests! 🎉
