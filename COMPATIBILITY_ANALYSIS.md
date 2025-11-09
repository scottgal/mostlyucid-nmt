# EasyNMT API Compatibility Analysis

## Comparison: EasyNMT vs MostlyLucid-NMT

### 1. GET /translate
**EasyNMT Expected:**
```json
{
  "translations": ["translated text"]
}
```
**Current MostlyLucid-NMT:**
```json
{
  "translations": ["translated text"],
  "pivot_path": null  // Optional, added feature
}
```
**Status:** ✅ **Compatible** - Extra optional fields should not break clients

---

### 2. POST /translate
**EasyNMT Expected:**
```json
{
  "target_lang": "en",
  "source_lang": "de",
  "detected_langs": ["de"],  // Present when source_lang is auto-detected
  "translated": ["Hello world"],
  "translation_time": 77.64
}
```
**Current MostlyLucid-NMT:**
```json
{
  "target_lang": "en",
  "source_lang": "de",
  "translated": ["Hello world"],
  "translation_time": 77.64,
  "pivot_path": null,  // Optional, added feature
  "metadata": null     // Optional, added feature
}
```
**Status:** ⚠️ **MISSING FIELD** - `detected_langs` field is missing
**Action Required:** Add `detected_langs` to TranslatePostResponse

---

### 3. GET /lang_pairs
**EasyNMT Expected:**
```json
{
  "language_pairs": [["en", "de"], ["de", "en"], ...]
}
```
**Current MostlyLucid-NMT:**
```json
{
  "language_pairs": [["en", "de"], ["de", "en"], ...]
}
```
**Status:** ✅ **Compatible**

---

### 4. GET /get_languages
**EasyNMT Expected:**
```json
{
  "languages": ["en", "de", "fr", ...]
}
```
**Current MostlyLucid-NMT:**
```json
{
  "languages": ["en", "de", "fr", ...]
}
```
**Status:** ✅ **Compatible**

---

### 5. GET /language_detection
**EasyNMT Expected:**
```json
{
  "language": "en"
}
```
**Current MostlyLucid-NMT:**
```json
{
  "language": "en"
}
```
**Status:** ✅ **Compatible**

---

### 6. POST /language_detection
**EasyNMT Expected:**
- String input: `{"language": "en"}`
- List input: `{"languages": ["en", "de"]}`
- Dict input: `{"key1": "en", "key2": "de"}`

**Current MostlyLucid-NMT:**
Same structure (returns appropriate format based on input)

**Status:** ✅ **Compatible**

---

### 7. GET /model_name
**EasyNMT Expected:**
```json
{
  "model_name": "opus-mt-en-de"
}
```
OR just the string directly.

**Current MostlyLucid-NMT:**
```json
{
  "model_name": "Helsinki-NLP/opus-mt (dynamic)",
  "device": "cuda:0",
  "easynmt_model": "...",
  "batch_size": 64,
  "max_text_len": null,
  "max_beam_size": null,
  "workers": {...},
  "input_sanitize": true,
  ...  // Many additional fields
}
```
**Status:** ❌ **INCOMPATIBLE** - Returns complex object instead of simple response
**Action Required:** Consider creating compatibility wrapper or simplifying response

---

## Required Changes for Full Compatibility

### 1. Add `detected_langs` to POST /translate Response
- Modify `TranslatePostResponse` model
- Track detected languages in translation service
- Return array of detected languages when source_lang was auto-detected

### 2. Consider /model_name compatibility
**Option A:** Simplify response to match EasyNMT (breaking change for current users)
**Option B:** Add alias endpoint `/model_name_simple` for EasyNMT compatibility
**Option C:** Keep current behavior if clients can ignore extra fields

### 3. Test with actual EasyNMT clients
- Python client
- Node.js client (node-easynmt)
- Direct HTTP requests

---

## Recommendations

1. **High Priority:** Add `detected_langs` field to POST /translate response
2. **Medium Priority:** Review /model_name response format
3. **Low Priority:** Ensure all error responses match EasyNMT format
