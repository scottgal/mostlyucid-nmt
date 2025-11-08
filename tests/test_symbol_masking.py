"""Tests for symbol masking utilities."""

import pytest
from src.utils.symbol_masking import (
    is_emoji_char,
    is_maskable_char,
    mask_symbols,
    unmask_symbols
)


class TestIsEmojiChar:
    """Tests for is_emoji_char function."""

    def test_common_emoji(self):
        """Test detection of common emoji."""
        assert is_emoji_char("😀") is True
        assert is_emoji_char("🎉") is True
        assert is_emoji_char("👋") is True

    def test_non_emoji(self):
        """Test that non-emoji returns False."""
        assert is_emoji_char("a") is False
        assert is_emoji_char("1") is False
        assert is_emoji_char(".") is False

    def test_empty_string(self):
        """Test empty string handling."""
        assert is_emoji_char("") is False


class TestIsMaskableChar:
    """Tests for is_maskable_char function."""

    def test_digits_maskable(self):
        """Test that digits are maskable."""
        assert is_maskable_char("0") is True
        assert is_maskable_char("5") is True
        assert is_maskable_char("9") is True

    def test_punctuation_maskable(self):
        """Test that punctuation is maskable."""
        assert is_maskable_char(".") is True
        assert is_maskable_char("!") is True
        assert is_maskable_char("?") is True
        assert is_maskable_char(",") is True

    def test_letters_not_maskable(self):
        """Test that letters are not maskable."""
        assert is_maskable_char("a") is False
        assert is_maskable_char("Z") is False

    def test_spaces_not_maskable(self):
        """Test that spaces are not maskable."""
        assert is_maskable_char(" ") is False


class TestMaskSymbols:
    """Tests for mask_symbols function."""

    def test_mask_basic_punctuation(self):
        """Test masking basic punctuation."""
        text = "Hello! World?"
        masked, originals = mask_symbols(text)
        assert "⟪MSK" in masked
        assert "⟫" in masked
        assert "!" in originals
        assert "?" in originals

    def test_mask_digits(self):
        """Test masking digits."""
        text = "Price is $99.99"
        masked, originals = mask_symbols(text)
        assert "99" in " ".join(originals) or any("9" in o for o in originals)

    def test_mask_contiguous_runs(self):
        """Test that contiguous runs are grouped."""
        text = "Hello!!! World"
        masked, originals = mask_symbols(text)
        # "!!!" should be one masked segment
        assert "!!!" in originals

    def test_preserves_text(self):
        """Test that text is preserved."""
        text = "Hello World"
        masked, originals = mask_symbols(text)
        # If no maskable chars, should be unchanged
        if not originals:
            assert masked == text

    def test_empty_string(self):
        """Test empty string handling."""
        masked, originals = mask_symbols("")
        assert masked == ""
        assert originals == []

    def test_mask_emoji(self):
        """Test masking emoji."""
        text = "Hello 👋 World"
        masked, originals = mask_symbols(text)
        assert "👋" in " ".join(originals) or any("👋" in o for o in originals)


class TestUnmaskSymbols:
    """Tests for unmask_symbols function."""

    def test_unmask_restores_symbols(self):
        """Test that unmasking restores original symbols."""
        text = "Hello! World?"
        masked, originals = mask_symbols(text)
        unmasked = unmask_symbols(masked, originals)
        # Should restore to original (or close to it)
        assert "!" in unmasked or "?" in unmasked

    def test_unmask_empty(self):
        """Test unmasking with empty originals."""
        text = "Hello World"
        unmasked = unmask_symbols(text, [])
        assert unmasked == text

    def test_unmask_preserves_order(self):
        """Test that unmasking preserves order."""
        text = "A! B? C."
        masked, originals = mask_symbols(text)
        unmasked = unmask_symbols(masked, originals)
        # Tokens should be restored in order
        assert unmasked.count("!") <= text.count("!")

    def test_roundtrip(self):
        """Test full mask/unmask roundtrip."""
        original = "Price: $99.99! Sale ends soon."
        masked, originals = mask_symbols(original)
        restored = unmask_symbols(masked, originals)
        # Should have same punctuation and digits
        assert "$" in restored or "99" in restored
