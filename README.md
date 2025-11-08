# Marian Translator (EasyNMT-compatible API)

A FastAPI service that provides an EasyNMT-like HTTP API for machine translation using Helsinki-NLP MarianMT models from Hugging Face.

- Compatible endpoints with EasyNMT: `/translate` (GET/POST), `/lang_pairs`, `/get_languages`, `/language_detection` (GET/POST), `/model_name`
- Swagger UI available at `/docs` (also at `/` via redirect) and ReDoc at `/redoc`
- CPU and GPU support (CUDA), with on-demand model loading and LRU in-memory cache
- Backpressure and queuing on by default; smart `Retry-After` on overload
- Robust input handling, sentence splitting, and optional pivot translation
- Structured logging with optional file rotation for long-running stability


## Table of Contents
- [Quick Start](#quick-start)
  - [CPU](#cpu)
  - [GPU](#gpu)
- [API](#api)
  - [`/translate` GET](#translate-get)
  - [`/translate` POST](#translate-post)
  - [`/lang_pairs`](#lang_pairs)
  - [`/get_languages`](#get_languages)
  - [`/language_detection` GET/POST](#language_detection)
  - [`/model_name`](#model_name)
  - [Health/Observability](#healthobservability)
- [Configuration (Environment Variables)](#configuration-environment-variables)
  - [Device Selection](#device-selection)
  - [Model & Cache](#model--cache)
  - [Preloading](#preloading)
  - [EasyNMT Options](#easynmt-options)
  - [Queueing / Backpressure / Timeouts](#queueing--backpressure--timeouts)
  - [Retry-After Estimation](#retry-after-estimation)
  - [Input Sanitization](#input-sanitization)
  - [Response Alignment & Sentence Splitting](#response-alignment--sentence-splitting)
  - [Pivot Fallback](#pivot-fallback)
  - [Logging](#logging)
  - [Maintenance](#maintenance)
- [Performance Tuning](#performance-tuning)
- [Client Tips](#client-tips)
- [Graceful Shutdown](#graceful-shutdown)
- [Troubleshooting](#troubleshooting)
- [License](#license)


## Quick Start

### CPU
Build and run the CPU image:

```bash
# Build
docker build -t mostlylucid-nmt .

# Run (example prod-ish defaults)
docker run -p 8000:8000 \
  -e ENABLE_QUEUE=1 -e MAX_QUEUE_SIZE=500 \
  -e EASYNMT_BATCH_SIZE=16 \
  -e TIMEOUT=180 \
  mostlylucid-nmt
```

Open the docs at: http://localhost:8000/


### GPU
Requires NVIDIA Container Toolkit.

```bash
# Build
docker build -f Dockerfile.gpu -t mostlylucid-nmt:gpu .

# Run (typical high-throughput, safe defaults)
docker run --gpus all -p 8000:8000 \
  -e USE_GPU=true -e DEVICE=cuda:0 \
  -e PRELOAD_MODELS="en->de,de->en" \
  -e EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}' \
  -e ENABLE_QUEUE=1 -e MAX_QUEUE_SIZE=1000 \
  -e WEB_CONCURRENCY=1 -e TIMEOUT=180 \
  mostlylucid-nmt:gpu
```

Open the docs at: http://localhost:8000/


## API
The API matches EasyNMT routes and shapes where applicable. Swagger UI is available at `/docs`.

### `/translate` GET
Translates texts passed as repeated `text=` query params.

Query params:
- `target_lang` (string, required)
- `text` (string[], optional; repeat param multiple times)
- `source_lang` (string, optional; empty for auto-detect)
- `beam_size` (int, optional; default `5`, clamped by `EASYNMT_MAX_BEAM_SIZE` if set)
- `perform_sentence_splitting` (bool, optional; default true)

Response (default mode):
```json
{ "translations": ["..."] }
```

### `/translate` POST
Body:
```json
{
  "text": ["Hello world", "This is a test"],
  "target_lang": "de",
  "source_lang": "en",
  "beam_size": 1,
  "perform_sentence_splitting": true
}
```

Note: `text` can also be a single string.

Response: same as GET.

Notes:
- On success, `translations` length always equals the number of input items, with non-null strings (placeholder on per-item failure).
- On overload, server returns 429/503 with `Retry-After` header and JSON `{ "retry_after_sec": N }`.

### `/lang_pairs`
Returns all supported source/target pairs built from the `SUPPORTED_LANGS` set.

```json
{ "language_pairs": [["en", "de"], ["de", "en"]] }
```

### `/get_languages`
Optionally filter by `source_lang` or `target_lang`.

```json
{ "languages": ["en", "de"] }
```

### `/language_detection`
- GET: `?text=...` → `{ "language": "en" }`
- POST: body `{"text": "..." | ["..."] | {"id":"text", ...}}`
  - Returns `{ "language": ... }`, `{ "languages": [...] }`, or a map of detections.

### `/model_name`
Returns model/device info and key runtime configuration snapshot.

```json
{
  "model_name": "Helsinki-NLP/opus-mt (dynamic)",
  "device": "cpu|cuda:N",
  "easynmt_model": "opus-mt",
  "batch_size": 16,
  "max_text_len": null,
  "max_beam_size": null,
  "workers": {"backend": 1, "frontend": 2},
  "align_responses": true,
  "pivot_fallback": true,
  "logging": {
    "log_level": "INFO",
    "log_to_file": false,
    "log_file_path": null,
    "log_format": "plain",
    "request_log": false,
    "log_include_text": false
  }
}
```

### Health/Observability
- `GET /healthz` → `{ "status": "ok" }`
- `GET /readyz` → readiness with device and queue settings
- `GET /cache` → LRU cache status (capacity/size/keys/device) and queue configuration


## Configuration (Environment Variables)
Defaults are shown in parentheses.

### Device Selection
- `USE_GPU` = `true|false|auto` (`auto`) — prefer GPU if available.
- `DEVICE` = `auto|cpu|cuda|cuda:0` (`auto`) — explicit device overrides `USE_GPU`.

### Model & Cache
- `EASYNMT_MODEL` = `opus-mt` (`opus-mt`) — model family selector (only opus-mt supported).
- `EASYNMT_MODEL_ARGS` = JSON string (`{}`) — forwarded to `transformers.pipeline` (allowed keys: `revision`, `trust_remote_code`, `cache_dir`, `use_fast`, `torch_dtype` where `"fp16"|"bf16"|"fp32"`).
- `MAX_CACHED_MODELS` = int (`6`) — LRU capacity of in-memory pipelines. Eviction frees VRAM when on GPU.

### Preloading
- `PRELOAD_MODELS` = `"en->de,de->en,fr->en"` — preloads pipelines at startup; invalid or missing repos are ignored.

### EasyNMT Options
- `MAX_WORKERS_BACKEND` = int (`1`) — translation thread pool workers.
- `MAX_WORKERS_FRONTEND` = int (`2`) — language detection/meta workers.
- `EASYNMT_MAX_TEXT_LEN` = int (unset) — max text length per item; also caps generation `max_length`.
- `EASYNMT_MAX_BEAM_SIZE` = int (unset) — upper bound for requested `beam_size`.
- `EASYNMT_BATCH_SIZE` = int (`16`) — batch size for pipeline calls.
- `EASYNMT_RESPONSE_MODE` = `strings|objects` (`strings`) — shape of `translations`.

### Queueing / Backpressure / Timeouts
- `ENABLE_QUEUE` = `1|0` (`1`) — enable request queueing/backpressure.
- `MAX_INFLIGHT_TRANSLATIONS` = int (auto) — concurrent translations; default `1` on GPU, else `MAX_WORKERS_BACKEND` on CPU.
- `MAX_QUEUE_SIZE` = int (`1000`) — max enqueued requests; overflow returns 429 with `Retry-After`.
- `TRANSLATE_TIMEOUT_SEC` = int (`0`) — per-request translation timeout (0 disables).
- Gunicorn: `TIMEOUT` = int (`120`) — worker timeout for requests; set via Docker `CMD`.
- Gunicorn workers: `WEB_CONCURRENCY` (unset) — use `1` on single GPU to avoid VRAM contention.

### Retry-After Estimation
- `RETRY_AFTER_MIN_SEC` = float (`1`) — lower bound for estimate.
- `RETRY_AFTER_MAX_SEC` = int (`120`) — upper bound for estimate.
- `RETRY_AFTER_ALPHA` = float (`0.2`) — EMA smoothing factor for average translate duration.

### Input Sanitization
- `INPUT_SANITIZE` = `1|0` (`1`) — enables filtering of noise (emoji-only, control chars, punctuation-only, etc.).
- `INPUT_MIN_ALNUM_RATIO` = float (`0.2`) — minimal alphanumeric ratio among non-space chars.
- `INPUT_MIN_CHARS` = int (`1`) — minimal length after stripping control chars.
- `UNDETERMINED_LANG_CODE` = string (`und`) — returned by detection when input is noise.

### Response Alignment & Sentence Splitting
- `ALIGN_RESPONSES` = `1|0` (`1`) — return aligned `translations` array of the same length; per-item failures use placeholder.
- `SANITIZE_PLACEHOLDER` = string (`""`) — placeholder for skipped/failed items.
- `PERFORM_SENTENCE_SPLITTING_DEFAULT` = `1|0` (`1`) — default behavior if request does not specify.
- `MAX_SENTENCE_CHARS` = int (`500`) — max chars per sentence before further splitting.
- `MAX_CHUNK_CHARS` = int (`900`) — re-chunk sentences to this size for translation.
- `JOIN_SENTENCES_WITH` = string (`" "`) — glue used when recombining translated chunks.

### Pivot Fallback
- `PIVOT_FALLBACK` = `1|0` (`1`) — enable two-hop translation via pivot if direct model fails.
- `PIVOT_LANG` = string (`en`) — pivot language.

### Logging
- `LOG_LEVEL` = `DEBUG|INFO|WARN|ERROR` (`INFO`)
- `REQUEST_LOG` = `1|0` (`0`) — per-request logs.
- `LOG_TO_FILE` = `1|0` (`0`) — enable rotating file logs.
- `LOG_FILE_PATH` = path (`/var/log/marian-translator/app.log`)
- `LOG_FILE_MAX_BYTES` = int (`10485760`) — 10MB.
- `LOG_FILE_BACKUP_COUNT` = int (`5`)
- `LOG_FORMAT` = `plain|json` (`plain`)
- `LOG_INCLUDE_TEXT` = `1|0` (`0`) — include raw texts in logs (off by default for privacy).

### Maintenance
- `CUDA_CACHE_CLEAR_INTERVAL_SEC` = int (`0`) — periodically call `torch.cuda.empty_cache()`; `0` disables.


## Performance Tuning
Order of impact:
1. Enable GPU, use half precision if supported:
   - `USE_GPU=true`, `DEVICE=cuda:0`, `EASYNMT_MODEL_ARGS='{"torch_dtype":"fp16"}'`
2. Batch size (`EASYNMT_BATCH_SIZE`): start 32–64 on GPU; 8–16 on CPU, tune carefully.
3. Keep `beam_size` low (1–2) for throughput.
4. Group inputs by language pair and send large arrays via POST.
5. Preload hot pairs via `PRELOAD_MODELS` to avoid first-request latency.
6. Keep `WEB_CONCURRENCY=1` and `MAX_INFLIGHT_TRANSLATIONS=1` on single GPU; scale horizontally for more throughput.
7. Use backpressure defaults (`ENABLE_QUEUE=1`, large `MAX_QUEUE_SIZE`).


## Client Tips
- Use a single long-lived HTTP client with keep-alive. Respect 429/503 `Retry-After` and retry with jitter backoff.
- Only parse `translations` on HTTP 200. Expect `translations.Length == input.Length` and no null elements.
- Prefer POST with a large `text` array per language pair.

Example `curl` (POST):
```bash
curl -s -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{
        "text": ["Hello world", "This is fast"],
        "target_lang": "de",
        "source_lang": "en",
        "beam_size": 1,
        "perform_sentence_splitting": true
      }'
```

Other useful endpoints:
```bash
curl -s http://localhost:8000/model_name | jq
curl -s http://localhost:8000/cache | jq
curl -s http://localhost:8000/readyz | jq
curl -s http://localhost:8000/lang_pairs | jq
```


## Graceful Shutdown
Fast, graceful termination is enabled by default in both CPU and GPU images.

What happens on shutdown:
- Docker sends SIGTERM to PID 1 (Gunicorn) thanks to `STOPSIGNAL SIGTERM`.
- Gunicorn stops accepting new connections, waits up to `GRACEFUL_TIMEOUT` seconds for in‑flight requests to finish, then forcefully kills workers if they don’t exit.
- The FastAPI app’s shutdown hook cancels background maintenance and shuts down internal thread pools. On GPU, CUDA cache is cleared.

Key runtime knobs (env vars):
- `GRACEFUL_TIMEOUT` (default `20`): Gunicorn graceful period in seconds before sending SIGKILL to workers.
- `TIMEOUT` (default `60`): Max time a worker can spend handling a single request.
- `KEEP_ALIVE` (default `5`): HTTP keep‑alive timeout for idle connections.
- `WEB_CONCURRENCY` (unset by default): Number of Gunicorn workers. Use `1` for single‑GPU deployments.

Quick test locally:
```bash
# Start the service
docker run --rm --name mt -p 8000:8000 mostlylucid-nmt

# In another shell, start a long request (simulate with a large text or big batch)
# Then ask Docker to stop the container and observe logs for a quick, clean exit.
docker stop mt
```

Notes:
- If clients hold long‑lived idle HTTP connections, the short `KEEP_ALIVE` helps close them quickly on shutdown.
- For extremely long translations, consider lowering `TIMEOUT` and/or guiding clients to send smaller batches and respect `Retry-After`.

## Troubleshooting
- 429 Too Many Requests:
  - The queue exceeded `MAX_QUEUE_SIZE`. Read `Retry-After` header or JSON `retry_after_sec` and retry later. Consider increasing `MAX_QUEUE_SIZE`.
- 503 Busy:
  - Queueing disabled or all slots occupied. Respect `Retry-After`; consider enabling queueing (`ENABLE_QUEUE=1`).
- Missing language pair:
  - The service dynamically loads `Helsinki-NLP/opus-mt-{src}-{tgt}`. If it doesn’t exist, direct translation fails; pivot fallback (`PIVOT_FALLBACK=1`) may help.
- Long texts fail:
  - Sentence splitting and chunking are enabled by default; adjust `MAX_SENTENCE_CHARS` / `MAX_CHUNK_CHARS` or lower `beam_size`.
- Logs and persistence:
  - Enable file logs with rotation (`LOG_TO_FILE=1`). Mount a volume at `/var/log/marian-translator` if you need persistence.
- `sacremoses` warning:
  - The image includes `sacremoses`; the app also suppresses the warning. If you build custom images, ensure `sacremoses` is installed.


## License
MIT or as specified by your repository. Replace this section with your actual license terms.
