"""Text processing utilities: sanitization, splitting, chunking."""

import re
from typing import List, Tuple

from src.config import config


def strip_control_chars(s: str) -> str:
    """Remove ASCII control chars except common whitespace.

    Args:
        s: Input string

    Returns:
        String with control characters removed
    """
    return "".join(ch for ch in s if ch == "\t" or ch == "\n" or ch == "\r" or ord(ch) >= 32)


def is_noise(text: str) -> bool:
    """Check if text is considered noise (too short, no alphanum content, etc.).

    Args:
        text: Input text to check

    Returns:
        True if text is noise and should be skipped
    """
    if text is None:
        return True

    s = strip_control_chars(str(text)).strip()
    if len(s) < config.INPUT_MIN_CHARS:
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
    return ratio < config.INPUT_MIN_ALNUM_RATIO


def sanitize_list(items: List[str]) -> Tuple[List[str], int]:
    """Filter noise from list of strings.

    Args:
        items: List of strings to filter

    Returns:
        Tuple of (filtered_list, skipped_count)
    """
    if not config.INPUT_SANITIZE:
        return items, 0

    kept: List[str] = []
    skipped = 0

    for t in items:
        if isinstance(t, str):
            if is_noise(t):
                skipped += 1
                continue
            kept.append(t)

    return kept, skipped


# Regex patterns for sentence splitting
_SENT_BOUNDARY_RE = re.compile(r"([.!?\u2026]+)(\s+)")
_WORD_SPLIT_RE = re.compile(r"(,|;|:|\s+)")


def split_sentences(text: str) -> List[str]:
    """Split text into sentences using heuristic boundaries.

    Args:
        text: Input text to split

    Returns:
        List of sentence strings
    """
    if not text:
        return []

    cleaned = strip_control_chars(text).strip()
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
        if len(p) <= config.MAX_SENTENCE_CHARS:
            enforced.append(p)
            continue

        # Split on spaces/punctuation to keep under limit
        buffer = []
        cur_len = 0
        tokens = _WORD_SPLIT_RE.split(p)

        for tok in tokens:
            if not tok:
                continue

            if cur_len + len(tok) > config.MAX_SENTENCE_CHARS and buffer:
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


def chunk_sentences(sentences: List[str], max_chars: int) -> List[str]:
    """Group sentences into chunks under max_chars limit.

    Args:
        sentences: List of sentences to chunk
        max_chars: Maximum characters per chunk

    Returns:
        List of chunked strings
    """
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0

    for s in sentences:
        add_len = len(s) if not cur else len(config.JOIN_SENTENCES_WITH) + len(s)

        if cur and (cur_len + add_len) > max_chars:
            chunks.append(config.JOIN_SENTENCES_WITH.join(cur))
            cur = [s]
            cur_len = len(s)
        else:
            cur.append(s)
            cur_len += add_len if cur_len > 0 else len(s)

    if cur:
        chunks.append(config.JOIN_SENTENCES_WITH.join(cur))

    return chunks


def remove_repeating_new_symbols(src: str, out: str) -> str:
    """Remove runs of symbols that appear in output but not in source.

    This prevents translation artifacts like "!!!!" or "🤣🤣🤣" from models.

    Args:
        src: Original source text
        out: Translated output text

    Returns:
        Cleaned output text
    """
    import unicodedata

    def is_symbol_char(ch: str) -> bool:
        """Check if character is a symbol/punctuation."""
        if not ch or ch.isspace() or ch.isalnum():
            return False
        cat = unicodedata.category(ch)
        return cat.startswith("P") or cat.startswith("S")

    def collect_symbol_set(text: str) -> set:
        """Get set of all symbols in text."""
        if not text:
            return set()
        return {ch for ch in text if is_symbol_char(ch)}

    if not out:
        return out

    allowed = collect_symbol_set(src)
    n = len(out)
    i = 0
    buf: List[str] = []

    while i < n:
        ch = out[i]
        # Detect run of same char
        j = i + 1
        while j < n and out[j] == ch:
            j += 1

        run_len = j - i

        if run_len >= 2 and is_symbol_char(ch) and ch not in allowed:
            # Drop the whole run
            pass
        else:
            buf.append(out[i:j])

        i = j

    cleaned = "".join(buf)
    # Collapse excessive whitespace that might result
    cleaned = re.sub(r"\s{3,}", "  ", cleaned)

    return cleaned


def remove_word_repetitions(src: str, out: str, max_allowed_repeats: int = 3) -> str:
    """Remove excessive word/phrase repetitions that don't exist in source.

    Detects patterns like "Mòr, Mòr, Mòr, Mòr, Mòr" and truncates them
    to a reasonable count based on what's in the source text.

    Args:
        src: Original source text
        out: Translated output text
        max_allowed_repeats: Maximum repeats allowed even if source has more (default: 3)

    Returns:
        Cleaned output text with excessive repetitions removed
    """
    if not out or len(out) < 10:
        return out

    # Count word repetitions in source (normalized)
    def normalize_word(w: str) -> str:
        return w.lower().strip(".,;:!?\"'()[]{}") if w else ""

    def count_consecutive_repeats(text: str, pattern: str) -> int:
        """Count max consecutive occurrences of a pattern."""
        import re
        # Escape special regex chars in pattern
        escaped = re.escape(pattern)
        # Match pattern followed by optional punctuation/space, repeated
        matches = re.findall(rf'({escaped}[\s,;]*)+', text, re.IGNORECASE)
        if not matches:
            return 0
        max_count = 0
        for m in matches:
            count = len(re.findall(escaped, m, re.IGNORECASE))
            max_count = max(max_count, count)
        return max_count

    # Find repeated word sequences in output
    words = out.split()
    if len(words) < 4:
        return out

    # Look for runs of the same word
    result_words = []
    i = 0
    while i < len(words):
        word = words[i]
        norm_word = normalize_word(word)

        if not norm_word:
            result_words.append(word)
            i += 1
            continue

        # Count consecutive occurrences of this word
        j = i + 1
        while j < len(words) and normalize_word(words[j]) == norm_word:
            j += 1

        run_length = j - i

        if run_length > max_allowed_repeats:
            # Check how many times this word repeats in source
            src_repeats = count_consecutive_repeats(src, norm_word)
            allowed = max(max_allowed_repeats, min(src_repeats, max_allowed_repeats * 2))

            # Keep only allowed number
            for k in range(min(run_length, allowed)):
                result_words.append(words[i + k])
        else:
            # Keep all
            for k in range(run_length):
                result_words.append(words[i + k])

        i = j

    cleaned = " ".join(result_words)

    # Also detect phrase repetitions like "Mòr, Mòr, Mòr"
    # Pattern: word followed by comma/space, repeated 4+ times
    phrase_pattern = re.compile(r'\b(\w+)(?:[,\s]+\1){3,}\b', re.IGNORECASE)

    def limit_phrase_repeats(match):
        word = match.group(1)
        src_count = count_consecutive_repeats(src, word)
        allowed = max(2, min(src_count, max_allowed_repeats))
        return ", ".join([word] * allowed)

    cleaned = phrase_pattern.sub(limit_phrase_repeats, cleaned)

    return cleaned
