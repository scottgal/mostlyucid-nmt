"""Markdown sanitization utilities to prevent parser depth errors.

Addresses issues where translated markdown causes "depth limit exceeded" errors
in parsers like Markdig, particularly with:
- Unbalanced brackets [] and parentheses ()
- RTL languages (Arabic, Hebrew) flipping bracket direction
- Nested inline formatting that doesn't close properly
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass

from src.config import config


@dataclass
class SanitizationResult:
    """Result of markdown sanitization."""
    text: str
    was_sanitized: bool
    issues_found: List[str]
    depth_warning: bool


# Default maximum nesting depth (overridden by config.MARKDOWN_MAX_DEPTH)
_DEFAULT_MAX_NESTING_DEPTH = 10


def _get_max_depth() -> int:
    """Get configured maximum nesting depth."""
    return getattr(config, "MARKDOWN_MAX_DEPTH", _DEFAULT_MAX_NESTING_DEPTH)


# RTL languages that may have bracket issues
_RTL_LANGUAGES = {"ar", "he", "fa", "ur", "yi", "ps"}

# Bracket pairs to balance
_BRACKET_PAIRS = [
    ("[", "]"),
    ("(", ")"),
]

# Patterns that indicate problematic markdown nesting
_NESTED_LINK_PATTERN = re.compile(r'\[[^\]]*\[[^\]]*\]')  # [text[nested]]
_NESTED_PAREN_IN_LINK = re.compile(r'\]\([^)]*\([^)]*\)')  # ](url(nested))
_UNBALANCED_EMPHASIS = re.compile(r'(\*{1,3}|\_{1,3})(?:[^*_]*\1){3,}')  # ***a***b***c***


def _count_nesting_depth(text: str) -> int:
    """Count maximum bracket nesting depth in text.

    Args:
        text: Text to analyze

    Returns:
        Maximum nesting depth encountered
    """
    max_depth = 0
    current_depth = 0

    for ch in text:
        if ch in "[(":
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif ch in "])":
            current_depth = max(0, current_depth - 1)

    return max_depth


def _balance_brackets(text: str, open_char: str, close_char: str) -> Tuple[str, bool]:
    """Balance a specific bracket pair by removing unmatched brackets.

    Args:
        text: Text to process
        open_char: Opening bracket character
        close_char: Closing bracket character

    Returns:
        Tuple of (balanced_text, was_modified)
    """
    # Track positions of unmatched brackets
    open_stack: List[int] = []
    unmatched_close: List[int] = []

    for i, ch in enumerate(text):
        if ch == open_char:
            open_stack.append(i)
        elif ch == close_char:
            if open_stack:
                open_stack.pop()
            else:
                unmatched_close.append(i)

    # Collect all unmatched positions
    unmatched = set(open_stack) | set(unmatched_close)

    if not unmatched:
        return text, False

    # Build result without unmatched brackets
    result = []
    for i, ch in enumerate(text):
        if i not in unmatched:
            result.append(ch)

    return "".join(result), True


def _fix_rtl_brackets(text: str) -> Tuple[str, bool]:
    """Fix bracket direction issues common in RTL translation output.

    Some models flip brackets in RTL text: [text] becomes ]text[

    Args:
        text: Text to process

    Returns:
        Tuple of (fixed_text, was_modified)
    """
    # Detect reversed bracket patterns like ]text[ or )text(
    reversed_square = re.compile(r'\]([^\[\]]+)\[')
    reversed_paren = re.compile(r'\)([^()]+)\(')

    modified = False
    result = text

    # Fix reversed square brackets
    while True:
        match = reversed_square.search(result)
        if not match:
            break
        result = result[:match.start()] + "[" + match.group(1) + "]" + result[match.end():]
        modified = True

    # Fix reversed parentheses
    while True:
        match = reversed_paren.search(result)
        if not match:
            break
        result = result[:match.start()] + "(" + match.group(1) + ")" + result[match.end():]
        modified = True

    return result, modified


def _break_deep_nesting(text: str, max_depth: Optional[int] = None) -> Tuple[str, bool]:
    """Break deeply nested bracket structures to prevent parser depth issues.

    When nesting exceeds max_depth, inner brackets are converted to their
    text equivalents or removed.

    Args:
        text: Text to process
        max_depth: Maximum allowed nesting depth (defaults to config value)

    Returns:
        Tuple of (processed_text, was_modified)
    """
    if max_depth is None:
        max_depth = _get_max_depth()

    depth = _count_nesting_depth(text)
    if depth <= max_depth:
        return text, False

    # Build result, tracking depth and removing inner brackets
    result = []
    current_depth = 0
    modified = False

    for ch in text:
        if ch in "[(":
            current_depth += 1
            if current_depth > max_depth:
                # Skip this opening bracket
                modified = True
                continue
        elif ch in "])":
            if current_depth > max_depth:
                # Skip this closing bracket
                current_depth = max(0, current_depth - 1)
                modified = True
                continue
            current_depth = max(0, current_depth - 1)

        result.append(ch)

    return "".join(result), modified


def _fix_nested_emphasis(text: str) -> Tuple[str, bool]:
    """Fix deeply nested or unbalanced emphasis markers.

    Patterns like ***a***b***c*** can cause parser issues.

    Args:
        text: Text to process

    Returns:
        Tuple of (fixed_text, was_modified)
    """
    if not _UNBALANCED_EMPHASIS.search(text):
        return text, False

    # Count emphasis markers and balance them
    def balance_emphasis(marker: str, txt: str) -> str:
        count = txt.count(marker)
        if count % 2 == 0:
            return txt
        # Odd count - remove last occurrence
        idx = txt.rfind(marker)
        if idx >= 0:
            return txt[:idx] + txt[idx + len(marker):]
        return txt

    result = text
    for marker in ["***", "**", "*", "___", "__", "_"]:
        result = balance_emphasis(marker, result)

    return result, result != text


def _strip_complex_markdown(text: str) -> str:
    """Strip complex markdown formatting for safe mode.

    Removes links, images, and complex formatting while preserving text.

    Args:
        text: Text to process

    Returns:
        Simplified text with basic formatting only
    """
    result = text

    # Remove images: ![alt](url) -> alt
    result = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', result)

    # Convert links to text: [text](url) -> text
    result = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', result)

    # Remove reference-style links: [text][ref] -> text
    result = re.sub(r'\[([^\]]*)\]\[[^\]]*\]', r'\1', result)

    # Remove link definitions: [ref]: url
    result = re.sub(r'^\s*\[[^\]]+\]:\s*.*$', '', result, flags=re.MULTILINE)

    # Simplify emphasis to single level
    result = re.sub(r'\*{3,}([^*]+)\*{3,}', r'**\1**', result)
    result = re.sub(r'_{3,}([^_]+)_{3,}', r'__\1__', result)

    # Remove HTML tags
    result = re.sub(r'<[^>]+>', '', result)

    # Clean up multiple consecutive brackets
    result = re.sub(r'\[{2,}', '[', result)
    result = re.sub(r'\]{2,}', ']', result)
    result = re.sub(r'\({2,}', '(', result)
    result = re.sub(r'\){2,}', ')', result)

    return result


def sanitize_markdown(
    text: str,
    source_lang: Optional[str] = None,
    target_lang: Optional[str] = None,
    safe_mode: bool = False
) -> SanitizationResult:
    """Sanitize markdown to prevent parser depth errors.

    Args:
        text: Markdown text to sanitize
        source_lang: Source language code (for RTL detection)
        target_lang: Target language code (for RTL detection)
        safe_mode: If True, strip complex markdown entirely

    Returns:
        SanitizationResult with sanitized text and metadata
    """
    if not text:
        return SanitizationResult(text="", was_sanitized=False, issues_found=[], depth_warning=False)

    max_depth = _get_max_depth()
    issues: List[str] = []
    was_sanitized = False
    result = text

    # Check initial depth
    initial_depth = _count_nesting_depth(result)
    depth_warning = initial_depth > max_depth

    if depth_warning:
        issues.append(f"Initial nesting depth {initial_depth} exceeds limit {max_depth}")

    # Safe mode: strip complex formatting entirely
    if safe_mode:
        result = _strip_complex_markdown(result)
        issues.append("Safe mode: stripped complex markdown")
        was_sanitized = True
        return SanitizationResult(
            text=result,
            was_sanitized=was_sanitized,
            issues_found=issues,
            depth_warning=depth_warning
        )

    # Fix RTL bracket issues if target is RTL
    is_rtl = target_lang in _RTL_LANGUAGES if target_lang else False
    if is_rtl:
        result, modified = _fix_rtl_brackets(result)
        if modified:
            issues.append("Fixed RTL bracket direction")
            was_sanitized = True

    # Balance brackets
    for open_char, close_char in _BRACKET_PAIRS:
        result, modified = _balance_brackets(result, open_char, close_char)
        if modified:
            issues.append(f"Balanced {open_char}{close_char} brackets")
            was_sanitized = True

    # Break deep nesting
    result, modified = _break_deep_nesting(result)
    if modified:
        issues.append("Reduced excessive nesting depth")
        was_sanitized = True

    # Fix emphasis issues
    result, modified = _fix_nested_emphasis(result)
    if modified:
        issues.append("Fixed unbalanced emphasis markers")
        was_sanitized = True

    return SanitizationResult(
        text=result,
        was_sanitized=was_sanitized,
        issues_found=issues,
        depth_warning=depth_warning
    )


def validate_markdown_depth(text: str, max_depth: Optional[int] = None) -> Tuple[bool, int]:
    """Validate that markdown doesn't exceed nesting depth.

    Args:
        text: Markdown text to validate
        max_depth: Maximum allowed nesting depth (defaults to config value)

    Returns:
        Tuple of (is_valid, actual_depth)
    """
    if max_depth is None:
        max_depth = _get_max_depth()
    depth = _count_nesting_depth(text)
    return depth <= max_depth, depth


def should_use_safe_mode(source_lang: str, target_lang: str) -> bool:
    """Determine if safe mode should be used for a language pair.

    Some language pairs are known to produce problematic markdown output.

    Args:
        source_lang: Source language code
        target_lang: Target language code

    Returns:
        True if safe mode is recommended
    """
    if not config.MARKDOWN_SAFE_MODE_AUTO:
        return False

    # RTL targets often have bracket issues
    if target_lang in _RTL_LANGUAGES:
        return True

    # Add other problematic pairs as discovered
    problematic_pairs = config.MARKDOWN_PROBLEMATIC_PAIRS
    pair_key = f"{source_lang}->{target_lang}"

    return pair_key in problematic_pairs


def sanitize_translations(
    translations: List[str],
    source_lang: str,
    target_lang: str
) -> Tuple[List[str], bool, List[str]]:
    """Sanitize a list of translations.

    Args:
        translations: List of translated texts
        source_lang: Source language code
        target_lang: Target language code

    Returns:
        Tuple of (sanitized_texts, any_sanitized, all_issues)
    """
    if not config.MARKDOWN_SANITIZE:
        return translations, False, []

    # Determine if safe mode should be used
    safe_mode = config.MARKDOWN_SAFE_MODE or should_use_safe_mode(source_lang, target_lang)

    results: List[str] = []
    any_sanitized = False
    all_issues: List[str] = []

    for i, text in enumerate(translations):
        result = sanitize_markdown(
            text,
            source_lang=source_lang,
            target_lang=target_lang,
            safe_mode=safe_mode
        )
        results.append(result.text)

        if result.was_sanitized:
            any_sanitized = True
            for issue in result.issues_found:
                all_issues.append(f"[{i}] {issue}")

    return results, any_sanitized, all_issues
