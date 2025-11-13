#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script to demonstrate symbol masking with markdown content."""

import sys
import io

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.utils.symbol_masking import mask_symbols, unmask_symbols

# Test with markdown examples
test_cases = [
    # Basic markdown formatting
    "**This is bold text** and *this is italic*.",

    # Code blocks with backticks
    "Use the `mask_symbols()` function to protect special characters.",

    # Links
    "[Click here](https://example.com) to visit the site.",

    # URLs with parameters
    "API endpoint: https://api.example.com/v1/translate?src=en&tgt=de",

    # Code with symbols
    "Example code: `if (x > 10 && y < 20) { return true; }`",

    # Mixed content with numbers and symbols
    "Price: $99.99 (save 25%!) - Limited time offer!!!",

    # Emoji and special characters
    "Hello 👋 Welcome to the site! 🎉 Let's get started... 🚀",

    # Complex markdown with multiple elements
    """## Installation

To install the package, run:

```bash
pip install -r requirements.txt
```

Then configure with `MODEL_FAMILY=opus-mt`.""",

    # Inline HTML
    "<strong>Bold</strong> and <em>italic</em> text with <code>code</code>.",
]

print("=" * 80)
print("SYMBOL MASKING TEST - Markdown Content")
print("=" * 80)
print()

for i, text in enumerate(test_cases, 1):
    print(f"Test Case {i}:")
    print(f"Original:  {text[:100]}{'...' if len(text) > 100 else ''}")
    print()

    # Mask symbols
    masked_text, originals = mask_symbols(text)
    print(f"Masked:    {masked_text[:100]}{'...' if len(masked_text) > 100 else ''}")
    print(f"Protected: {len(originals)} symbol sequences")
    if originals:
        print(f"Sequences: {originals[:5]}{'...' if len(originals) > 5 else ''}")
    print()

    # Unmask symbols
    restored_text = unmask_symbols(masked_text, originals)
    print(f"Restored:  {restored_text[:100]}{'...' if len(restored_text) > 100 else ''}")

    # Verify roundtrip
    if restored_text == text:
        print("✓ Roundtrip successful - original text preserved!")
    else:
        print("✗ Roundtrip failed - text differs!")
        print(f"  Expected: {text}")
        print(f"  Got:      {restored_text}")

    print("-" * 80)
    print()

print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print()
print("What this demonstrates:")
print("- Symbols, punctuation, and special characters are masked before translation")
print("- Masked tokens (⟪MSK0⟫, ⟪MSK1⟫, etc.) replace the original symbols")
print("- After translation, the original symbols are restored")
print("- This protects markdown syntax, URLs, code, and other special content")
print()
print("Note: Full markdown awareness (code blocks, links) requires additional work")
print("Current masking protects individual symbols but doesn't understand structure")
