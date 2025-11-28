"""Symbol masking utilities for preserving special characters during translation."""

import re
import unicodedata
from typing import List, Tuple

from src.config import config


# Mask token format
_MASK_PREFIX = "⟪MSK"
_MASK_SUFFIX = "⟫"

# Emoji unicode ranges
_EMOJI_RANGES = [
    (0x1F300, 0x1FAFF),  # Misc Symbols and Pictographs to Symbols and Pictographs Extended-A
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport and Map Symbols
    (0x2600, 0x26FF),    # Misc symbols
    (0x2700, 0x27BF),    # Dingbats
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
]


def is_emoji_char(ch: str) -> bool:
    """Check if character is an emoji.

    Args:
        ch: Character to check

    Returns:
        True if character is an emoji
    """
    if not ch:
        return False

    cp = ord(ch)
    for a, b in _EMOJI_RANGES:
        if a <= cp <= b:
            return True

    # Many emoji are category So (Symbol, other)
    cat = unicodedata.category(ch)
    return cat == "So"


def is_maskable_char(ch: str) -> bool:
    """Check if character should be masked before translation.

    Args:
        ch: Character to check

    Returns:
        True if character should be masked
    """
    if config.MASK_DIGITS and ch.isdigit():
        return True

    cat = unicodedata.category(ch)

    # P* = punctuation, S* = symbols
    if config.MASK_PUNCT and (cat.startswith("P") or cat.startswith("S")):
        return True

    if config.MASK_EMOJI and is_emoji_char(ch):
        return True

    return False


def mask_symbols(text: str) -> Tuple[str, List[str]]:
    """Replace contiguous runs of maskable chars with sentinel tokens.

    Args:
        text: Input text to mask

    Returns:
        Tuple of (masked_text, list_of_original_segments)
    """
    if not config.SYMBOL_MASKING or not text:
        return text, []

    originals: List[str] = []
    out_chars: List[str] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if is_maskable_char(ch):
            j = i + 1
            # Group contiguous maskable chars
            while j < n and is_maskable_char(text[j]):
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


def unmask_symbols(text: str, originals: List[str]) -> str:
    """Replace mask tokens with original symbol sequences.

    Handles variations introduced by translation models:
    - Added quotes: "MSK1", 'MSK1', «MSK1»
    - Spaces: MSK 1, MSK  1
    - Case changes: msk1, Msk1
    - Missing brackets: MSK1 instead of ⟪MSK1⟫

    Args:
        text: Masked text with tokens
        originals: List of original symbol sequences

    Returns:
        Text with symbols restored
    """
    if not config.SYMBOL_MASKING or not originals or not text:
        return text

    out = text

    for idx, orig in enumerate(originals):
        # Try exact match first (fastest path)
        token = f"{_MASK_PREFIX}{idx}{_MASK_SUFFIX}"
        pos = out.find(token)
        if pos != -1:
            out = out[:pos] + orig + out[pos + len(token):]
            continue

        # Try quoted/bracketed version first (includes internal whitespace)
        # Matches: "MSK 0", 'MSK0', «MSK 0», [MSK0], (MSK 0), etc.
        quoted_pattern = (
            r'["\'"«»⟪\[\(]'  # Required opening quote/bracket
            rf'\s*[Mm][Ss][Kk]\s*{idx}\s*'  # MSK + index with optional internal spaces
            r'["\'"»⟫\]\)]'  # Required closing quote/bracket
        )
        match = re.search(quoted_pattern, out)
        if match:
            out = out[:match.start()] + orig + out[match.end():]
            continue

        # Try bare version (no quotes, only internal space between MSK and number)
        # Matches: MSK0, MSK 0, msk0, Msk 0, etc.
        bare_pattern = rf'[Mm][Ss][Kk]\s*{idx}(?![0-9])'  # Negative lookahead to avoid MSK12 matching MSK1
        match = re.search(bare_pattern, out)
        if match:
            out = out[:match.start()] + orig + out[match.end():]

    return out
