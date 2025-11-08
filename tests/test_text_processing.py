"""Tests for text processing utilities."""

import pytest
from src.utils.text_processing import (
    strip_control_chars,
    is_noise,
    sanitize_list,
    split_sentences,
    chunk_sentences,
    remove_repeating_new_symbols
)


class TestStripControlChars:
    """Tests for strip_control_chars function."""

    def test_strip_control_chars_basic(self):
        """Test stripping basic control characters."""
        assert strip_control_chars("hello\x00world") == "helloworld"
        assert strip_control_chars("test\x01\x02\x03") == "test"

    def test_keep_whitespace(self):
        """Test that common whitespace is preserved."""
        assert strip_control_chars("hello\tworld") == "hello\tworld"
        assert strip_control_chars("hello\nworld") == "hello\nworld"
        assert strip_control_chars("hello\rworld") == "hello\rworld"

    def test_empty_string(self):
        """Test empty string handling."""
        assert strip_control_chars("") == ""


class TestIsNoise:
    """Tests for is_noise function."""

    def test_none_is_noise(self):
        """Test that None is considered noise."""
        assert is_noise(None) is True

    def test_empty_string_is_noise(self):
        """Test that empty string is noise."""
        assert is_noise("") is True
        assert is_noise("   ") is True

    def test_pure_symbols_is_noise(self):
        """Test that pure symbols are noise."""
        assert is_noise("!!!") is True
        assert is_noise("???") is True
        assert is_noise("...") is True

    def test_pure_emoji_is_noise(self):
        """Test that pure emoji is noise."""
        assert is_noise("😀😂🎉") is True

    def test_valid_text_not_noise(self):
        """Test that valid text is not noise."""
        assert is_noise("Hello world") is False
        assert is_noise("Test 123") is False

    def test_mixed_content_not_noise(self):
        """Test that mixed content passes threshold."""
        assert is_noise("Hello!!!") is False
        assert is_noise("Test 😀") is False


class TestSanitizeList:
    """Tests for sanitize_list function."""

    def test_sanitize_empty_list(self):
        """Test sanitizing empty list."""
        result, skipped = sanitize_list([])
        assert result == []
        assert skipped == 0

    def test_sanitize_removes_noise(self):
        """Test that noise items are removed."""
        items = ["Hello", "!!!", "World", "😀😀😀"]
        result, skipped = sanitize_list(items)
        assert "Hello" in result
        assert "World" in result
        assert "!!!" not in result
        assert skipped == 2

    def test_sanitize_preserves_valid(self):
        """Test that valid items are preserved."""
        items = ["Hello world", "Test 123", "Valid text"]
        result, skipped = sanitize_list(items)
        assert len(result) == 3
        assert skipped == 0


class TestSplitSentences:
    """Tests for split_sentences function."""

    def test_split_basic_sentences(self):
        """Test splitting basic sentences."""
        text = "Hello world. This is a test. Final sentence."
        sentences = split_sentences(text)
        assert len(sentences) == 3
        assert "Hello world." in sentences[0]

    def test_split_exclamation(self):
        """Test splitting on exclamation marks."""
        text = "Wow! This is great! Amazing!"
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_split_question(self):
        """Test splitting on question marks."""
        text = "Is this a test? Yes it is. Really?"
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_split_ellipsis(self):
        """Test splitting on ellipsis."""
        text = "This is… interesting. Very… unusual."
        sentences = split_sentences(text)
        assert len(sentences) >= 2

    def test_empty_text(self):
        """Test empty text handling."""
        assert split_sentences("") == []
        assert split_sentences("   ") == []

    def test_long_sentence_splitting(self):
        """Test that long sentences are split at word boundaries."""
        # Create a sentence longer than MAX_SENTENCE_CHARS (500)
        long_text = " ".join(["word"] * 200)  # ~1000 chars
        sentences = split_sentences(long_text)
        # Should be split into multiple parts
        assert len(sentences) > 1


class TestChunkSentences:
    """Tests for chunk_sentences function."""

    def test_chunk_small_sentences(self):
        """Test chunking small sentences."""
        sentences = ["Hello.", "World.", "Test."]
        chunks = chunk_sentences(sentences, max_chars=100)
        # Should combine into one chunk
        assert len(chunks) == 1
        assert "Hello. World. Test." in chunks[0]

    def test_chunk_respects_max_chars(self):
        """Test that chunks respect max_chars limit."""
        sentences = ["A" * 100, "B" * 100, "C" * 100]
        chunks = chunk_sentences(sentences, max_chars=150)
        # Each sentence should be in its own chunk
        assert len(chunks) == 3

    def test_chunk_empty_list(self):
        """Test chunking empty list."""
        chunks = chunk_sentences([], max_chars=100)
        assert chunks == []


class TestRemoveRepeatingNewSymbols:
    """Tests for remove_repeating_new_symbols function."""

    def test_removes_new_repeating_symbols(self):
        """Test removing repeated symbols not in source."""
        src = "Hello world"
        out = "Hallo Welt!!!!!!!"
        cleaned = remove_repeating_new_symbols(src, out)
        # Should remove the repeated !!!!!!
        assert cleaned == "Hallo Welt"

    def test_preserves_original_symbols(self):
        """Test preserving symbols that exist in source."""
        src = "Hello world!!!"
        out = "Hallo Welt!!!"
        cleaned = remove_repeating_new_symbols(src, out)
        # Should keep !!! because it's in source
        assert "!!!" in cleaned

    def test_single_symbols_preserved(self):
        """Test that single symbols are always preserved."""
        src = "Hello world"
        out = "Hallo Welt!"
        cleaned = remove_repeating_new_symbols(src, out)
        # Single ! should be preserved
        assert cleaned == "Hallo Welt!"

    def test_empty_strings(self):
        """Test empty string handling."""
        assert remove_repeating_new_symbols("", "") == ""
        assert remove_repeating_new_symbols("test", "") == ""

    def test_collapses_excessive_whitespace(self):
        """Test that excessive whitespace is collapsed."""
        src = "Hello world"
        out = "Hallo     Welt"
        cleaned = remove_repeating_new_symbols(src, out)
        # Should collapse to double space max
        assert "     " not in cleaned
