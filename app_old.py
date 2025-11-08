from typing import Dict, List, Any, Optional, Tuple, Union

import os
import json
import asyncio
import logging
import uuid
import time
import math
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
import re
import warnings
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from transformers import pipeline
from langdetect import detect
import torch

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
REQUEST_LOG = os.getenv("REQUEST_LOG", "0").lower() in ("1", "true", "yes")
LOG_FORMAT = os.getenv("LOG_FORMAT", "plain").lower()  # plain|json
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "0").lower() in ("1", "true", "yes")
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "/var/log/marian-translator/app.log")
LOG_FILE_MAX_BYTES = int(os.getenv("LOG_FILE_MAX_BYTES", "10485760"))  # 10MB
LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))
LOG_INCLUDE_TEXT = os.getenv("LOG_INCLUDE_TEXT", "0").lower() in ("1", "true", "yes")

# Set up base logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        # Include selected extras if present
        for k in ("req_id", "endpoint", "src", "tgt", "items", "beam", "duration_ms", "queue_wait_ms", "retry_after_sec"):
            if hasattr(record, k):
                base[k] = getattr(record, k)
        return json.dumps(base, ensure_ascii=False)

# Optional file logging with rotation
if LOG_TO_FILE:
    try:
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=LOG_FILE_MAX_BYTES, backupCount=LOG_FILE_BACKUP_COUNT)
        file_fmt = JsonFormatter() if LOG_FORMAT == "json" else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        file_handler.setFormatter(file_fmt)
        file_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        logging.getLogger().addHandler(file_handler)
    except Exception as _e:
        logger.warning(f"failed to set up file logging: {_e}")

# If JSON format requested, set all existing handlers to JSON formatter
if LOG_FORMAT == "json":
    jf = JsonFormatter()
    for h in logging.getLogger().handlers:
        try:
            h.setFormatter(jf)
        except Exception:
            pass

# Silence specific UserWarning about sacremoses if it still appears
warnings.filterwarnings("ignore", message=".*sacremoses.*", category=UserWarning)

app = FastAPI(title="FastAPI", version="0.1.0")

# Supported language codes. We support bidirectional translation with MarianMT where available.
SUPPORTED_LANGS: List[str] = [
    "en", "es", "fr", "de", "it", "zh", "nl", "hi", "ar", "uk", "fi", "sv", "el",
]

# Cache with LRU eviction for translation pipelines
class LRUPipelineCache(OrderedDict):
    def __init__(self, capacity: int):
        super().__init__()
        self.capacity = max(1, capacity)

    def get(self, key: str):
        if key in self:
            self.move_to_end(key)
            return super().__getitem__(key)
        return None

    def put(self, key: str, value: Any):
        exists = key in self
        super().__setitem__(key, value)
        self.move_to_end(key)
        if not exists and len(self) > self.capacity:
            old_key, old_val = self.popitem(last=False)
            # Try to free GPU memory for the evicted pipeline
            try:
                if hasattr(old_val, "model"):
                    old_val.model.cpu()
                del old_val
            except Exception:
                pass
            if torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass

# Build possible model names for src->tgt using Helsinki-NLP Marian models.
# We will try to use "Helsinki-NLP/opus-mt-{src}-{tgt}".
MAX_CACHED_MODELS = int(os.getenv("MAX_CACHED_MODELS", "6"))
PIPELINE_CACHE: LRUPipelineCache = LRUPipelineCache(MAX_CACHED_MODELS)

# Device selection
USE_GPU = os.getenv("USE_GPU", "auto").lower()  # "true", "false", or "auto"
DEVICE_ENV = os.getenv("DEVICE", "auto")  # e.g., "cuda", "cuda:0", "cpu"

# EasyNMT-like environment configuration
MAX_WORKERS_BACKEND = int(os.getenv("MAX_WORKERS_BACKEND", "1"))
MAX_WORKERS_FRONTEND = int(os.getenv("MAX_WORKERS_FRONTEND", "2"))
EASYNMT_MODEL = os.getenv("EASYNMT_MODEL", "opus-mt")
EASYNMT_MODEL_ARGS_RAW = os.getenv("EASYNMT_MODEL_ARGS", "{}")
EASYNMT_MAX_TEXT_LEN = os.getenv("EASYNMT_MAX_TEXT_LEN")
EASYNMT_MAX_TEXT_LEN_INT: Optional[int] = int(EASYNMT_MAX_TEXT_LEN) if (EASYNMT_MAX_TEXT_LEN and EASYNMT_MAX_TEXT_LEN.isdigit()) else None
EASYNMT_MAX_BEAM_SIZE = os.getenv("EASYNMT_MAX_BEAM_SIZE")
EASYNMT_MAX_BEAM_SIZE_INT: Optional[int] = int(EASYNMT_MAX_BEAM_SIZE) if (EASYNMT_MAX_BEAM_SIZE and EASYNMT_MAX_BEAM_SIZE.isdigit()) else None
EASYNMT_BATCH_SIZE = int(os.getenv("EASYNMT_BATCH_SIZE", "16"))
EASYNMT_RESPONSE_MODE = os.getenv("EASYNMT_RESPONSE_MODE", "strings").lower()  # "strings" or "objects"

# Input sanitization controls
INPUT_SANITIZE = os.getenv("INPUT_SANITIZE", "1").lower() in ("1", "true", "yes")
INPUT_SKIP_MODE = os.getenv("INPUT_SKIP_MODE", "skip").lower()  # currently only 'skip' is implemented
INPUT_MIN_ALNUM_RATIO = float(os.getenv("INPUT_MIN_ALNUM_RATIO", "0.2"))
INPUT_MIN_CHARS = int(os.getenv("INPUT_MIN_CHARS", "1"))
UNDETERMINED_LANG_CODE = os.getenv("UNDETERMINED_LANG_CODE", "und")

# Response alignment and sentence splitting controls
ALIGN_RESPONSES = os.getenv("ALIGN_RESPONSES", "1").lower() in ("1", "true", "yes")
SANITIZE_PLACEHOLDER = os.getenv("SANITIZE_PLACEHOLDER", "")  # used when ALIGN_RESPONSES=1 and an item is skipped/noise
PERFORM_SENTENCE_SPLITTING_DEFAULT = os.getenv("PERFORM_SENTENCE_SPLITTING_DEFAULT", "1").lower() in ("1", "true", "yes")
MAX_SENTENCE_CHARS = int(os.getenv("MAX_SENTENCE_CHARS", "500"))
MAX_CHUNK_CHARS = int(os.getenv("MAX_CHUNK_CHARS", "900"))
JOIN_SENTENCES_WITH = os.getenv("JOIN_SENTENCES_WITH", " ")

# Symbol masking configuration (mask punctuation, symbols, numbers, emoji before translation, then reinsert)
SYMBOL_MASKING = os.getenv("SYMBOL_MASKING", "1").lower() in ("1", "true", "yes")
MASK_DIGITS = os.getenv("MASK_DIGITS", "1").lower() in ("1", "true", "yes")
MASK_PUNCT = os.getenv("MASK_PUNCT", "1").lower() in ("1", "true", "yes")
MASK_EMOJI = os.getenv("MASK_EMOJI", "1").lower() in ("1", "true", "yes")

# Pivot fallback configuration
PIVOT_FALLBACK = os.getenv("PIVOT_FALLBACK", "1").lower() in ("1", "true", "yes")
PIVOT_LANG = os.getenv("PIVOT_LANG", "en")

# Parse allowed pipeline args from EASYNMT_MODEL_ARGS
_ALLOWED_PIPELINE_KWARGS = {"revision", "trust_remote_code", "cache_dir", "use_fast", "torch_dtype"}

def _parse_model_args() -> Dict[str, Any]:
    try:
        data = json.loads(EASYNMT_MODEL_ARGS_RAW or "{}")
        if not isinstance(data, dict):
            return {}
    except Exception:
        return {}
    out: Dict[str, Any] = {}
    for k, v in data.items():
        if k not in _ALLOWED_PIPELINE_KWARGS:
            continue
        if k == "torch_dtype":
            # map strings to torch dtype
            if isinstance(v, str):
                vs = v.lower()
                if vs in ("fp16", "float16", "torch.float16"):
                    out[k] = torch.float16
                elif vs in ("bf16", "bfloat16", "torch.bfloat16"):
                    out[k] = torch.bfloat16
                elif vs in ("fp32", "float32", "torch.float32"):
                    out[k] = torch.float32
                else:
                    continue
            continue
        out[k] = v
    return out

PIPELINE_EXTRA_KWARGS = _parse_model_args()

# Executors for backend (translation) and frontend (detection / meta)
_backend_executor = ThreadPoolExecutor(max_workers=max(1, MAX_WORKERS_BACKEND))
_frontend_executor = ThreadPoolExecutor(max_workers=max(1, MAX_WORKERS_FRONTEND))

# Load management / queuing
ENABLE_QUEUE = os.getenv("ENABLE_QUEUE", "1").lower() in ("1", "true", "yes")
MAX_INFLIGHT_TRANSLATIONS_RAW = os.getenv("MAX_INFLIGHT_TRANSLATIONS")  # if unset, we decide after device resolution
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "1000"))
TRANSLATE_TIMEOUT_SEC = int(os.getenv("TRANSLATE_TIMEOUT_SEC", "0"))  # 0 = no extra timeout

_translate_semaphore: Optional[asyncio.Semaphore] = None
_waiting_count_lock = asyncio.Lock()
_waiting_count = 0

# Overload signaling / Retry-After estimation
RETRY_AFTER_MAX_SEC = int(os.getenv("RETRY_AFTER_MAX_SEC", "120"))
RETRY_AFTER_MIN_SEC = float(os.getenv("RETRY_AFTER_MIN_SEC", "1"))
RETRY_AFTER_ALPHA = float(os.getenv("RETRY_AFTER_ALPHA", "0.2"))  # EMA smoothing factor

_avg_translate_duration_sec: float = 0.0
_avg_duration_lock = asyncio.Lock()

_inflight_count = 0
_inflight_lock = asyncio.Lock()

class _TranslateSlot:
    def __init__(self):
        self.acquired = False

    async def __aenter__(self):
        global _waiting_count, _inflight_count
        if ENABLE_QUEUE:
            async with _waiting_count_lock:
                _waiting_count += 1
                wc = _waiting_count
            # If queue too long and no slots free, reject
            if _translate_semaphore.locked() and wc > MAX_QUEUE_SIZE:
                async with _waiting_count_lock:
                    _waiting_count -= 1
                # include waiters hint in error string
                raise RuntimeError(f"queue_overflow:{wc}")
            await _translate_semaphore.acquire()
            async with _waiting_count_lock:
                _waiting_count -= 1
            self.acquired = True
            async with _inflight_lock:
                _inflight_count += 1
            return self
        else:
            # No queueing: try immediate acquire
            if _translate_semaphore.locked():
                raise RuntimeError("busy")
            await _translate_semaphore.acquire()
            self.acquired = True
            async with _inflight_lock:
                _inflight_count += 1
            return self

    async def __aexit__(self, exc_type, exc, tb):
        global _inflight_count
        if self.acquired:
            _translate_semaphore.release()
            async with _inflight_lock:
                _inflight_count = max(0, _inflight_count - 1)
            self.acquired = False

async def acquire_translate_slot():
    return _TranslateSlot()

async def _record_duration(dt: float):
    global _avg_translate_duration_sec
    try:
        async with _avg_duration_lock:
            if _avg_translate_duration_sec <= 0:
                _avg_translate_duration_sec = dt
            else:
                _avg_translate_duration_sec = (1.0 - RETRY_AFTER_ALPHA) * _avg_translate_duration_sec + RETRY_AFTER_ALPHA * dt
    except Exception:
        pass

def _estimate_retry_after(waiters: Optional[int] = None) -> int:
    # Base estimate per job
    base = _avg_translate_duration_sec if _avg_translate_duration_sec > 0 else RETRY_AFTER_MIN_SEC
    base = max(base, RETRY_AFTER_MIN_SEC)
    cap = max(1, MAX_INFLIGHT_TRANSLATIONS)
    if waiters is None:
        # If we only know it's busy, assume at least one batch ahead
        est = base
    else:
        # Roughly how many batches ahead of us
        est = (waiters / cap) * base
    # clamp
    est = min(max(est, RETRY_AFTER_MIN_SEC), float(RETRY_AFTER_MAX_SEC))
    return max(1, math.ceil(est))


def _resolve_device_index() -> int:
    # Priority: explicit DEVICE env, else USE_GPU/auto
    dev = DEVICE_ENV
    if dev and dev != "auto":
        if dev.startswith("cuda"):
            if not torch.cuda.is_available():
                return -1
            if ":" in dev:
                _, idx = dev.split(":", 1)
                try:
                    return int(idx)
                except ValueError:
                    return 0
            return 0
        return -1  # cpu

    # Fallback by USE_GPU
    if USE_GPU in ("1", "true", "yes"):  # force GPU if available
        return 0 if torch.cuda.is_available() else -1
    if USE_GPU in ("0", "false", "no"):
        return -1
    # auto
    return 0 if torch.cuda.is_available() else -1

DEVICE_INDEX = _resolve_device_index()

# Determine default max inflight based on device if not explicitly set
if MAX_INFLIGHT_TRANSLATIONS_RAW is None or MAX_INFLIGHT_TRANSLATIONS_RAW == "":
    if DEVICE_INDEX == -1:
        # CPU: allow limited parallelism, bounded by backend workers
        MAX_INFLIGHT_TRANSLATIONS = max(1, MAX_WORKERS_BACKEND)
    else:
        # GPU: default to 1 to avoid VRAM oversubscription; batching provides parallelism
        MAX_INFLIGHT_TRANSLATIONS = 1
else:
    try:
        MAX_INFLIGHT_TRANSLATIONS = max(1, int(MAX_INFLIGHT_TRANSLATIONS_RAW))
    except Exception:
        MAX_INFLIGHT_TRANSLATIONS = 1 if DEVICE_INDEX != -1 else max(1, MAX_WORKERS_BACKEND)

# Initialize semaphore with the effective inflight limit
_translate_semaphore = asyncio.Semaphore(value=MAX_INFLIGHT_TRANSLATIONS)


class TranslatePostBody(BaseModel):
    text: Union[str, List[str]]
    target_lang: str
    source_lang: str = ""  # empty means auto-detect
    beam_size: int = 5
    perform_sentence_splitting: bool = True


def _model_name(src: str, tgt: str) -> str:
    return f"Helsinki-NLP/opus-mt-{src}-{tgt}"


def _get_pipeline(src: str, tgt: str):
    if EASYNMT_MODEL and EASYNMT_MODEL != "opus-mt":
        raise RuntimeError(f"Unsupported EASYNMT_MODEL='{EASYNMT_MODEL}'. Only 'opus-mt' is supported.")
    key = f"{src}->{tgt}"
    cached = PIPELINE_CACHE.get(key)
    if cached is not None:
        if REQUEST_LOG:
            logger.info(f"pipeline_cache hit {key}")
        return cached
    model = _model_name(src, tgt)
    if REQUEST_LOG:
        logger.info(f"pipeline_cache miss {key}, loading model {model}")
    # Build pipeline with extra kwargs if any
    pl = pipeline("translation", model=model, device=DEVICE_INDEX, **PIPELINE_EXTRA_KWARGS)
    PIPELINE_CACHE.put(key, pl)
    return pl


def _translate_texts_aligned(input_texts: List[str], src: str, tgt: str, eff_beam: int, perform_sentence_splitting: bool) -> List[str]:
    """Translate a list of texts while preserving alignment. If direct translation pipeline fails
    and pivot fallback is enabled, attempt src->pivot->tgt.
    """
    gen_max_len = 512
    if EASYNMT_MAX_TEXT_LEN_INT is not None:
        gen_max_len = min(gen_max_len, max(1, EASYNMT_MAX_TEXT_LEN_INT))

    def _translate_with_translator(translator, chunks: List[str]) -> List[str]:
        if not chunks:
            return []
        out_chunks: List[str] = []
        bs = max(1, EASYNMT_BATCH_SIZE)
        for i in range(0, len(chunks), bs):
            batch = chunks[i:i+bs]
            res = translator(batch, max_length=gen_max_len, num_beams=eff_beam, batch_size=len(batch))
            out_chunks.extend([r.get("translation_text", "") for r in res])
        return out_chunks

    def _translate_text_single(txt: str, translator_direct=None) -> str:
        # Returns a translation string for one input text, using direct or pivot if needed
        if INPUT_SANITIZE and _is_noise(txt):
            return SANITIZE_PLACEHOLDER
        try:
            translator = translator_direct or _get_pipeline(src, tgt)
            if perform_sentence_splitting:
                sents = _split_sentences(txt)
                chunks = _chunk_sentences(sents, MAX_CHUNK_CHARS)
                out = _translate_with_translator(translator, chunks)
                combined = JOIN_SENTENCES_WITH.join(out)
                combined = _remove_repeating_new_symbols(txt, combined)
                return combined
            else:
                res = translator([txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                base = res[0].get("translation_text", SANITIZE_PLACEHOLDER)
                base = _remove_repeating_new_symbols(txt, base)
                return base
        except Exception as direct_err:
            # Attempt pivot fallback if enabled
            if not PIVOT_FALLBACK or PIVOT_LANG in (src, tgt):
                if REQUEST_LOG:
                    logger.warning(f"direct translate failed (no pivot): {direct_err}")
                return SANITIZE_PLACEHOLDER
            try:
                trans_src_pivot = _get_pipeline(src, PIVOT_LANG)
                trans_pivot_tgt = _get_pipeline(PIVOT_LANG, tgt)
                if perform_sentence_splitting:
                    sents = _split_sentences(txt)
                    chunks = _chunk_sentences(sents, MAX_CHUNK_CHARS)
                    # First hop
                    mid = _translate_with_translator(trans_src_pivot, chunks)
                    # Second hop
                    final = _translate_with_translator(trans_pivot_tgt, mid)
                    combined = JOIN_SENTENCES_WITH.join(final)
                    combined = _remove_repeating_new_symbols(txt, combined)
                    return combined
                else:
                    mid = trans_src_pivot([txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                    mid_txt = mid[0].get("translation_text", "")
                    fin = trans_pivot_tgt([mid_txt], max_length=gen_max_len, num_beams=eff_beam, batch_size=1)
                    base = fin[0].get("translation_text", SANITIZE_PLACEHOLDER)
                    base = _remove_repeating_new_symbols(txt, base)
                    return base
            except Exception as pivot_err:
                if REQUEST_LOG:
                    logger.warning(f"pivot translate failed: {pivot_err}")
                return SANITIZE_PLACEHOLDER

    outputs: List[str] = []
    translator_direct = None
    try:
        translator_direct = _get_pipeline(src, tgt)
    except Exception as e:
        # We will use pivot per-item if available
        if REQUEST_LOG:
            logger.warning(f"loading direct pipeline failed; will pivot per item if possible: {e}")
        translator_direct = None

    for t in input_texts:
        try:
            txt = t if isinstance(t, str) else ""
            translated = _translate_text_single(txt, translator_direct=translator_direct)
            outputs.append(translated if isinstance(translated, str) else SANITIZE_PLACEHOLDER)
        except Exception as e:
            if REQUEST_LOG:
                logger.warning(f"per-item translation failed, inserting placeholder: {e}")
            outputs.append(SANITIZE_PLACEHOLDER)
    return outputs


def _strip_control_chars(s: str) -> str:
    # Remove ASCII control chars except common whitespace
    return "".join(ch for ch in s if ch == "\t" or ch == "\n" or ch == "\r" or ord(ch) >= 32)


def _is_noise(text: str) -> bool:
    if text is None:
        return True
    s = _strip_control_chars(str(text)).strip()
    if len(s) < INPUT_MIN_CHARS:
        return True
    # Count non-space characters
    no_space = [ch for ch in s if not ch.isspace()]
    if not no_space:
        return True
    alnum = sum(1 for ch in no_space if ch.isalnum())
    if alnum == 0:
        # Pure symbols/emoji/punct
        return True
    ratio = alnum / max(1, len(no_space))
    return ratio < INPUT_MIN_ALNUM_RATIO


def _sanitize_list(items: List[str]) -> Tuple[List[str], int]:
    if not INPUT_SANITIZE:
        return items, 0
    kept: List[str] = []
    skipped = 0
    for t in items:
        if isinstance(t, str):
            if _is_noise(t):
                skipped += 1
                continue
            kept.append(t)
    return kept, skipped

# Post-translation symbol loop filter
# Remove runs of the same symbol (punctuation/symbol/emoji) that appear in the translation
# if that symbol did not appear in the source text at all. Designed to curb "loops" like "!!!!" or "🤣🤣🤣"
# inadvertently produced by some models.
import unicodedata as _unicodedata_sym

def _is_symbol_char(ch: str) -> bool:
    if not ch or ch.isspace() or ch.isalnum():
        return False
    cat = _unicodedata_sym.category(ch)
    return cat.startswith("P") or cat.startswith("S") or _is_emoji_char(ch)

def _collect_symbol_set(text: str) -> set:
    if not text:
        return set()
    return {ch for ch in text if _is_symbol_char(ch)}

def _remove_repeating_new_symbols(src: str, out: str) -> str:
    if not out:
        return out
    allowed = _collect_symbol_set(src)
    n = len(out)
    i = 0
    buf: List[str] = []
    while i < n:
        ch = out[i]
        # detect run of same char
        j = i + 1
        while j < n and out[j] == ch:
            j += 1
        run_len = j - i
        if run_len >= 2 and _is_symbol_char(ch) and ch not in allowed:
            # drop the whole run
            pass
        else:
            buf.append(out[i:j])
        i = j
    cleaned = "".join(buf)
    # collapse excessive whitespace that might result
    cleaned = re.sub(r"\s{3,}", "  ", cleaned)
    return cleaned

# Sentence splitting and chunking helpers
_SENT_BOUNDARY_RE = re.compile(r"([.!?\u2026]+)(\s+)")
_WORD_SPLIT_RE = re.compile(r"(,|;|:|\s+)")

# Symbol masking helpers
import unicodedata

_MASK_PREFIX = "⟪MSK"
_MASK_SUFFIX = "⟫"

_DEF_EMOJI_RANGES = [
    (0x1F300, 0x1FAFF),  # Misc Symbols and Pictographs to Symbols and Pictographs Extended-A
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport and Map Symbols
    (0x2600, 0x26FF),    # Misc symbols
    (0x2700, 0x27BF),    # Dingbats
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
]

def _is_emoji_char(ch: str) -> bool:
    if not ch:
        return False
    cp = ord(ch)
    for a, b in _DEF_EMOJI_RANGES:
        if a <= cp <= b:
            return True
    # Many emoji are category So (Symbol, other)
    cat = unicodedata.category(ch)
    return cat == "So"

def _is_maskable_char(ch: str) -> bool:
    if MASK_DIGITS and ch.isdigit():
        return True
    cat = unicodedata.category(ch)
    # P* = punctuation, S* = symbols
    if MASK_PUNCT and (cat.startswith("P") or cat.startswith("S")):
        # avoid masking normal currency/plus-minus if desired? keep default mask
        return True
    if MASK_EMOJI and _is_emoji_char(ch):
        return True
    return False

def _mask_symbols(text: str) -> Tuple[str, List[str]]:
    """Replace contiguous runs of maskable chars with sentinel tokens. Return masked_text and list of originals."""
    if not SYMBOL_MASKING or not text:
        return text, []
    originals: List[str] = []
    out_chars: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if _is_maskable_char(ch):
            j = i + 1
            # group contiguous maskable chars
            while j < n and _is_maskable_char(text[j]):
                j += 1
            seg = text[i:j]
            idx = len(originals)
            originals.append(seg)
            out_chars.append(f"{_MASK_PREFIX}{idx}{_MASK_SUFFIX}")
            i = j
        else:
            out_chars.append(ch)
            i += 1
    return "".join(out_chars), originals

def _unmask_symbols(text: str, originals: List[str]) -> str:
    if not SYMBOL_MASKING or not originals or not text:
        return text
    out = text
    for idx, orig in enumerate(originals):
        token = f"{_MASK_PREFIX}{idx}{_MASK_SUFFIX}"
        # replace only the first occurrence each time to maintain order
        pos = out.find(token)
        if pos == -1:
            continue
        out = out[:pos] + orig + out[pos + len(token):]
    return out

def _split_sentences(text: str) -> List[str]:
    # Simple heuristic splitter: split on . ! ? … followed by whitespace
    if not text:
        return []
    cleaned = _strip_control_chars(text).strip()
    if not cleaned:
        return []
    parts: List[str] = []
    last = 0
    for m in _SENT_BOUNDARY_RE.finditer(cleaned):
        end = m.end()
        parts.append(cleaned[last:end].strip())
        last = end
    if last < len(cleaned):
        parts.append(cleaned[last:].strip())
    # If no boundaries found, return the whole text
    if not parts:
        parts = [cleaned]
    # Enforce MAX_SENTENCE_CHARS by further splitting on word boundaries
    enforced: List[str] = []
    for p in parts:
        if len(p) <= MAX_SENTENCE_CHARS:
            enforced.append(p)
            continue
        # split on spaces/punctuation to keep under limit
        buffer = []
        cur_len = 0
        tokens = _WORD_SPLIT_RE.split(p)
        for tok in tokens:
            if not tok:
                continue
            if cur_len + len(tok) > MAX_SENTENCE_CHARS and buffer:
                enforced.append("".join(buffer).strip())
                buffer = [tok]
                cur_len = len(tok)
            else:
                buffer.append(tok)
                cur_len += len(tok)
        if buffer:
            enforced.append("".join(buffer).strip())
    # Drop empties
    return [e for e in enforced if e]

def _chunk_sentences(sentences: List[str], max_chars: int) -> List[str]:
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0
    for s in sentences:
        add_len = len(s) if not cur else len(JOIN_SENTENCES_WITH) + len(s)
        if cur and (cur_len + add_len) > max_chars:
            chunks.append(JOIN_SENTENCES_WITH.join(cur))
            cur = [s]
            cur_len = len(s)
        else:
            cur.append(s)
            cur_len += add_len if cur_len > 0 else len(s)
    if cur:
        chunks.append(JOIN_SENTENCES_WITH.join(cur))
    return chunks


def _detect_lang(text: str) -> str:
    try:
        if INPUT_SANITIZE and _is_noise(text):
            return UNDETERMINED_LANG_CODE
        lang = detect(text)
    except Exception:
        lang = "en"  # default fallback
    return lang


def _normalize_texts(text: Union[str, List[str]]) -> List[str]:
    # Convert to list of strings without dropping to preserve alignment behavior upstream
    if isinstance(text, list):
        base = [t if isinstance(t, str) else "" for t in text]
    elif isinstance(text, str):
        base = [text]
    else:
        base = []
    # Do not sanitize here; endpoints will handle alignment-aware sanitization per item
    return base


@app.get("/translate", summary="Translate", description=(
    "Translates the text to the given target language.\n"
    ":param text: Text that should be translated\n"
    ":param target_lang: Target language\n"
    ":param source_lang: Language of text. Optional, if empty: Automatic language detection\n"
    ":param beam_size: Beam size. Optional\n"
    ":param perform_sentence_splitting: Split longer documents into individual sentences for translation. Optional\n"
    ":return:  Returns a json with the translated text"
))
async def translate_get(
    request: Request,
    target_lang: str = Query(..., alias="target_lang"),
    text: Optional[List[str]] = Query(default=None, alias="text"),
    source_lang: str = Query(default="", alias="source_lang"),
    beam_size: int = Query(default=5, alias="beam_size"),
    perform_sentence_splitting: bool = Query(default=True, alias="perform_sentence_splitting"),
):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    base_texts = _normalize_texts(text or [])
    if perform_sentence_splitting is None:
        perform_sentence_splitting = PERFORM_SENTENCE_SPLITTING_DEFAULT
    if REQUEST_LOG:
        logger.info(f"{req_id} translate_get received target={target_lang} src={source_lang} items={len(base_texts)}")
    if not base_texts:
        return {"translations": []}

    # Detect language if needed using first non-noise string
    first_non_noise = next((t for t in base_texts if t and (not INPUT_SANITIZE or not _is_noise(t))), "")
    src = source_lang or _detect_lang(first_non_noise)
    if src not in SUPPORTED_LANGS or target_lang not in SUPPORTED_LANGS or src == target_lang:
        raise HTTPException(status_code=400, detail={"error": "Unsupported language pair", "src": src, "tgt": target_lang})

    eff_beam = max(1, beam_size)
    if EASYNMT_MAX_BEAM_SIZE_INT is not None:
        eff_beam = min(eff_beam, max(1, EASYNMT_MAX_BEAM_SIZE_INT))

    loop = asyncio.get_event_loop()

    def _do_translate_aligned():
        return _translate_texts_aligned(base_texts, src, target_lang, eff_beam, perform_sentence_splitting)

    start_t = time.perf_counter()
    try:
        async with await acquire_translate_slot():
            if TRANSLATE_TIMEOUT_SEC > 0:
                texts = await asyncio.wait_for(loop.run_in_executor(_backend_executor, _do_translate_aligned), timeout=TRANSLATE_TIMEOUT_SEC)
            else:
                texts = await loop.run_in_executor(_backend_executor, _do_translate_aligned)
    except RuntimeError as e:
        reason = str(e)
        if reason.startswith("queue_overflow"):
            # parse waiters if available for better estimate
            try:
                _, waiters_s = reason.split(":", 1)
                waiters = int(waiters_s)
            except Exception:
                waiters = None
            retry_after = _estimate_retry_after(waiters)
            if REQUEST_LOG:
                logger.warning(f"translate_get overload: 429, retry_after={retry_after}s, waiters={waiters}")
            raise HTTPException(status_code=429, detail={"message": "Too many requests; queue full", "retry_after_sec": retry_after}, headers={"Retry-After": str(retry_after)})
        if reason == "busy":
            retry_after = _estimate_retry_after()
            if REQUEST_LOG:
                logger.warning(f"translate_get busy: 503, retry_after={retry_after}s")
            raise HTTPException(status_code=503, detail={"message": "Server busy", "retry_after_sec": retry_after}, headers={"Retry-After": str(retry_after)})
        raise
    finally:
        if 'texts' in locals():
            dt = max(0.0, time.perf_counter() - start_t)
            await _record_duration(dt)

    if EASYNMT_RESPONSE_MODE == "strings":
        payload = {"translations": texts}
    else:
        payload = {"translations": [{"text": t} for t in texts]}
    if REQUEST_LOG:
        logger.info(f"{req_id} translate_get done items={len(texts)}")
    return payload


@app.post("/translate", summary="Translate Post", description="Post method for translation\n:return:")
async def translate_post(request: Request, body: TranslatePostBody):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    base_texts = _normalize_texts(body.text)
    perform_sentence_splitting = body.perform_sentence_splitting if body.perform_sentence_splitting is not None else PERFORM_SENTENCE_SPLITTING_DEFAULT
    if REQUEST_LOG:
        logger.info(f"{req_id} translate_post received target={body.target_lang} src={body.source_lang} items={len(base_texts)}")
    if not base_texts:
        # Align POST response to C# schema expectations even on empty input
        src = body.source_lang or ""
        tgt = body.target_lang
        return {
            "target_lang": tgt,
            "source_lang": src,
            "translated": [],
            "translation_time": 0.0,
        }

    src = body.source_lang or _detect_lang(next((t for t in base_texts if t and (not INPUT_SANITIZE or not _is_noise(t))), ""))
    tgt = body.target_lang
    if src not in SUPPORTED_LANGS or tgt not in SUPPORTED_LANGS or src == tgt:
        raise HTTPException(status_code=400, detail={"error": "Unsupported language pair", "src": src, "tgt": tgt})

    eff_beam = max(1, body.beam_size)
    if EASYNMT_MAX_BEAM_SIZE_INT is not None:
        eff_beam = min(eff_beam, max(1, EASYNMT_MAX_BEAM_SIZE_INT))

    loop = asyncio.get_event_loop()

    def _do_translate_aligned():
        return _translate_texts_aligned(base_texts, src, tgt, eff_beam, perform_sentence_splitting)

    start_t = time.perf_counter()
    try:
        async with await acquire_translate_slot():
            if TRANSLATE_TIMEOUT_SEC > 0:
                texts = await asyncio.wait_for(loop.run_in_executor(_backend_executor, _do_translate_aligned), timeout=TRANSLATE_TIMEOUT_SEC)
            else:
                texts = await loop.run_in_executor(_backend_executor, _do_translate_aligned)
    except RuntimeError as e:
        reason = str(e)
        if reason.startswith("queue_overflow"):
            # parse waiters if available for better estimate
            try:
                _, waiters_s = reason.split(":", 1)
                waiters = int(waiters_s)
            except Exception:
                waiters = None
            retry_after = _estimate_retry_after(waiters)
            if REQUEST_LOG:
                logger.warning(f"translate_post overload: 429, retry_after={retry_after}s, waiters={waiters}")
            raise HTTPException(status_code=429, detail={"message": "Too many requests; queue full", "retry_after_sec": retry_after}, headers={"Retry-After": str(retry_after)})
        if reason == "busy":
            retry_after = _estimate_retry_after()
            if REQUEST_LOG:
                logger.warning(f"translate_post busy: 503, retry_after={retry_after}s")
            raise HTTPException(status_code=503, detail={"message": "Server busy", "retry_after_sec": retry_after}, headers={"Retry-After": str(retry_after)})
        raise
    finally:
        if 'texts' in locals():
            dt = max(0.0, time.perf_counter() - start_t)
            await _record_duration(dt)

    # Build response matching C# client's expected schema
    duration_sec = max(0.0, time.perf_counter() - start_t)
    payload = {
        "target_lang": tgt,
        "source_lang": src,
        "translated": texts,
        "translation_time": float(duration_sec),
    }
    if REQUEST_LOG:
        logger.info(f"{req_id} translate_post done items={len(texts)} dt={duration_sec:.3f}s")
    return payload


@app.get("/lang_pairs", summary="Lang Pairs", description="Returns the language pairs from the model\n:return:")
async def lang_pairs():
    pairs: List[Tuple[str, str]] = []
    for src in SUPPORTED_LANGS:
        for tgt in SUPPORTED_LANGS:
            if src != tgt:
                pairs.append((src, tgt))
    return {"language_pairs": pairs}


@app.get(
    "/get_languages",
    summary="Get Languages",
    description=(
        "Returns the languages the model supports\n:param source_lang: Optional. Only return languages with this language as source\n"
        ":param target_lang: Optional. Only return languages with this language as target\n:return:"
    ),
)
async def get_languages(source_lang: Optional[str] = None, target_lang: Optional[str] = None):
    if source_lang and source_lang in SUPPORTED_LANGS:
        # return targets for this source
        return {"languages": [l for l in SUPPORTED_LANGS if l != source_lang]}
    if target_lang and target_lang in SUPPORTED_LANGS:
        # return sources for this target
        return {"languages": [l for l in SUPPORTED_LANGS if l != target_lang]}
    return {"languages": SUPPORTED_LANGS}


@app.get(
    "/language_detection",
    summary="Language Detection",
    description=(
        "Detects the language for the provided text\n:param text: A single text for which we want to know the language\n:return: The detected language"
    ),
)
async def language_detection_get(text: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_frontend_executor, lambda: {"language": _detect_lang(text)})


class LanguageDetectionPostBody(BaseModel):
    text: Union[str, List[str], Dict[str, str]]


@app.post(
    "/language_detection",
    summary="Language Detection Post",
    description=(
        "Pass a json that has a 'text' key. The 'text' element can either be a string, a list of strings, or\n"
        "a dict.\n:return: Languages detected"
    ),
)
async def language_detection_post(body: LanguageDetectionPostBody):
    payload = body.text
    loop = asyncio.get_event_loop()

    def _work():
        if isinstance(payload, str):
            return {"language": _detect_lang(payload)}
        if isinstance(payload, list):
            return {"languages": [_detect_lang(t) for t in payload]}
        if isinstance(payload, dict):
            return {key: _detect_lang(val) for key, val in payload.items()}
        return {"error": "Invalid payload"}

    return await loop.run_in_executor(_frontend_executor, _work)


@app.get("/model_name", summary="Model Name", description="Returns the name of the loaded model\n:return: EasyNMT model name")
async def model_name():
    device_str = "cpu" if DEVICE_INDEX == -1 else f"cuda:{DEVICE_INDEX}"
    return {
        "model_name": "Helsinki-NLP/opus-mt (dynamic)",
        "device": device_str,
        "easynmt_model": EASYNMT_MODEL,
        "batch_size": EASYNMT_BATCH_SIZE,
        "max_text_len": EASYNMT_MAX_TEXT_LEN_INT,
        "max_beam_size": EASYNMT_MAX_BEAM_SIZE_INT,
        "workers": {
            "backend": MAX_WORKERS_BACKEND,
            "frontend": MAX_WORKERS_FRONTEND,
        },
        "input_sanitize": INPUT_SANITIZE,
        "input_sanitize_min_alnum_ratio": INPUT_MIN_ALNUM_RATIO,
        "input_sanitize_min_chars": INPUT_MIN_CHARS,
        "undetermined_lang_code": UNDETERMINED_LANG_CODE,
        "align_responses": ALIGN_RESPONSES,
        "sanitize_placeholder": SANITIZE_PLACEHOLDER,
        "sentence_splitting_default": PERFORM_SENTENCE_SPLITTING_DEFAULT,
        "max_sentence_chars": MAX_SENTENCE_CHARS,
        "max_chunk_chars": MAX_CHUNK_CHARS,
        "join_sentences_with": JOIN_SENTENCES_WITH,
        "pivot_fallback": PIVOT_FALLBACK,
        "pivot_lang": PIVOT_LANG,
        "logging": {
            "log_level": LOG_LEVEL,
            "log_to_file": LOG_TO_FILE,
            "log_file_path": LOG_FILE_PATH if LOG_TO_FILE else None,
            "log_format": LOG_FORMAT,
            "request_log": REQUEST_LOG,
            "log_include_text": LOG_INCLUDE_TEXT,
        },
    }


@app.get("/cache", summary="Cache status", description="Returns the currently cached translation pipelines")
async def cache_status():
    return {
        "capacity": PIPELINE_CACHE.capacity if hasattr(PIPELINE_CACHE, "capacity") else None,
        "size": len(PIPELINE_CACHE),
        "keys": list(PIPELINE_CACHE.keys()),
        "device": ("cpu" if DEVICE_INDEX == -1 else f"cuda:{DEVICE_INDEX}"),
        "inflight": MAX_INFLIGHT_TRANSLATIONS,
        "queue_enabled": ENABLE_QUEUE,
    }


CUDA_CACHE_CLEAR_INTERVAL_SEC = int(os.getenv("CUDA_CACHE_CLEAR_INTERVAL_SEC", "0"))  # 0 disables

async def _maintenance_task():
    if CUDA_CACHE_CLEAR_INTERVAL_SEC <= 0:
        return
    while True:
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                if REQUEST_LOG:
                    logger.info("maintenance: torch.cuda.empty_cache()")
        except Exception as e:
            logger.warning(f"maintenance error: {e}")
        await asyncio.sleep(CUDA_CACHE_CLEAR_INTERVAL_SEC)


# Track background maintenance task so we can cancel it on shutdown
_maintenance_task_handle: Optional[asyncio.Task] = None


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    device_ok = (DEVICE_INDEX == -1) or torch.cuda.is_available()
    return {
        "status": "ready" if device_ok else "degraded",
        "device": ("cpu" if DEVICE_INDEX == -1 else f"cuda:{DEVICE_INDEX}"),
        "queue_enabled": ENABLE_QUEUE,
        "max_inflight": MAX_INFLIGHT_TRANSLATIONS,
    }


@app.on_event("startup")
async def _startup():
    # preload models if requested
    preload = os.getenv("PRELOAD_MODELS", "").strip()
    if preload:
        pairs = [p.strip() for p in preload.split(";") if p.strip()]
        if len(pairs) == 1 and "," in pairs[0]:
            pairs = [p.strip() for p in pairs[0].split(",") if p.strip()]
        for p in pairs:
            if "->" not in p:
                continue
            src, tgt = p.split("->", 1)
            src = src.strip()
            tgt = tgt.strip()
            if not src or not tgt:
                continue
            if src not in SUPPORTED_LANGS or tgt not in SUPPORTED_LANGS or src == tgt:
                continue
            try:
                _ = _get_pipeline(src, tgt)
            except Exception:
                # ignore failures during preload
                pass
    # start maintenance task
    global _maintenance_task_handle
    _maintenance_task_handle = asyncio.create_task(_maintenance_task())


@app.on_event("shutdown")
async def _shutdown():
    # Stop background tasks first to speed up shutdown
    try:
        if _maintenance_task_handle is not None:
            _maintenance_task_handle.cancel()
            try:
                await asyncio.wait_for(_maintenance_task_handle, timeout=2)
            except Exception:
                pass
    except Exception:
        pass
    try:
        _backend_executor.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
    try:
        _frontend_executor.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
    if torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass


@app.get("/", include_in_schema=False)
async def root():
    # Redirect default index to the interactive API docs (Swagger UI), like EasyNMT
    return RedirectResponse(url="/docs")
