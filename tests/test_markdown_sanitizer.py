"""Tests for markdown sanitization utilities."""

import pytest
from src.utils.markdown_sanitizer import (
    sanitize_markdown,
    validate_markdown_depth,
    sanitize_translations,
    should_use_safe_mode,
    is_markdown,
    detect_markdown,
    SanitizationResult,
    MarkdownDetectionResult,
    _count_nesting_depth,
    _balance_brackets,
    _fix_rtl_brackets,
    _break_deep_nesting,
    _fix_nested_emphasis,
    _strip_complex_markdown,
)


class TestMarkdownDetection:
    """Tests for markdown content detection."""

    def test_plain_text_not_markdown(self):
        """Plain text should not be detected as markdown."""
        assert not is_markdown("Hello world")
        assert not is_markdown("This is just plain text.")
        assert not is_markdown("No formatting here at all")

    def test_links_detected(self):
        """Markdown links should be detected."""
        assert is_markdown("[link](https://example.com)")
        assert is_markdown("Check out [this site](http://test.com)")
        assert is_markdown("Multiple [one](a) and [two](b)")

    def test_images_detected(self):
        """Markdown images should be detected."""
        assert is_markdown("![alt text](image.jpg)")
        assert is_markdown("![](image.png)")

    def test_headers_detected(self):
        """Markdown headers should be detected."""
        assert is_markdown("# Header")
        assert is_markdown("## Subheader")
        assert is_markdown("### Level 3")
        assert is_markdown("Text\n# Header\nMore text")

    def test_code_blocks_detected(self):
        """Code blocks should be detected."""
        assert is_markdown("```python\ncode\n```")
        assert is_markdown("Use `inline code` here")

    def test_bold_detected(self):
        """Bold formatting should be detected."""
        assert is_markdown("This is **bold** text")
        assert is_markdown("This is __also bold__")

    def test_italic_detected(self):
        """Italic formatting should be detected."""
        assert is_markdown("This is *italic* text")

    def test_lists_detected(self):
        """Lists should be detected."""
        assert is_markdown("- Item one\n- Item two")
        assert is_markdown("* Bullet point")
        assert is_markdown("1. First item\n2. Second item")

    def test_blockquotes_detected(self):
        """Blockquotes should be detected."""
        assert is_markdown("> This is a quote")

    def test_tables_detected(self):
        """Tables should be detected."""
        assert is_markdown("| Col1 | Col2 |")
        assert is_markdown("|---|---|")

    def test_reference_links_detected(self):
        """Reference-style links should be detected."""
        assert is_markdown("[text][ref]")
        assert is_markdown("[ref]: https://example.com")

    def test_empty_not_markdown(self):
        """Empty strings should not be markdown."""
        assert not is_markdown("")
        assert not is_markdown("a")

    def test_confidence_scores(self):
        """Test confidence scoring."""
        # High confidence for definitive patterns
        result = detect_markdown("[link](url)")
        assert result.confidence >= 0.9
        assert "link" in result.patterns_found

        # Multiple patterns boost confidence
        result = detect_markdown("# Header\n[link](url)\n**bold**")
        assert result.confidence >= 0.9
        assert len(result.patterns_found) >= 3

        # Plain text has zero confidence
        result = detect_markdown("Just plain text")
        assert result.confidence == 0.0
        assert not result.is_markdown

    def test_mixed_content(self):
        """Text with markdown embedded in plain text."""
        assert is_markdown("Please visit [our site](https://example.com) for more info.")
        assert is_markdown("Use the `config.yaml` file to configure settings.")


class TestCountNestingDepth:
    """Tests for nesting depth counting."""

    def test_empty_string(self):
        assert _count_nesting_depth("") == 0

    def test_no_brackets(self):
        assert _count_nesting_depth("Hello world") == 0

    def test_single_level(self):
        assert _count_nesting_depth("[text]") == 1
        assert _count_nesting_depth("(text)") == 1

    def test_nested_brackets(self):
        assert _count_nesting_depth("[[nested]]") == 2
        assert _count_nesting_depth("[outer[inner]]") == 2

    def test_deeply_nested(self):
        text = "[[[[[[[[[[deep]]]]]]]]]]"  # 10 levels
        assert _count_nesting_depth(text) == 10

    def test_mixed_brackets(self):
        assert _count_nesting_depth("[text](url)") == 1
        assert _count_nesting_depth("[text](url[nested])") == 2

    def test_problematic_link_nesting(self):
        # Pattern that can occur in bad translations
        text = "[link](url[nested](more))"
        assert _count_nesting_depth(text) >= 2


class TestBalanceBrackets:
    """Tests for bracket balancing."""

    def test_balanced_already(self):
        text, modified = _balance_brackets("[balanced]", "[", "]")
        assert text == "[balanced]"
        assert not modified

    def test_unmatched_opening(self):
        text, modified = _balance_brackets("[unmatched", "[", "]")
        assert text == "unmatched"
        assert modified

    def test_unmatched_closing(self):
        text, modified = _balance_brackets("unmatched]", "[", "]")
        assert text == "unmatched"
        assert modified

    def test_multiple_unmatched(self):
        text, modified = _balance_brackets("[[text]", "[", "]")
        assert text == "[text]"
        assert modified

    def test_parentheses(self):
        text, modified = _balance_brackets("((nested)", "(", ")")
        assert text == "(nested)"
        assert modified

    def test_complex_unbalanced(self):
        text, modified = _balance_brackets("[a](b[c)", "[", "]")
        assert "[" not in text or text.count("[") == text.count("]")
        assert modified


class TestFixRtlBrackets:
    """Tests for RTL bracket fixing."""

    def test_no_rtl_issues(self):
        text, modified = _fix_rtl_brackets("[normal](url)")
        assert text == "[normal](url)"
        assert not modified

    def test_reversed_square_brackets(self):
        text, modified = _fix_rtl_brackets("]reversed[")
        assert text == "[reversed]"
        assert modified

    def test_reversed_parentheses(self):
        text, modified = _fix_rtl_brackets(")reversed(")
        assert text == "(reversed)"
        assert modified

    def test_mixed_rtl_issues(self):
        text, modified = _fix_rtl_brackets("]text[ and )more(")
        assert "[text]" in text
        assert "(more)" in text
        assert modified


class TestBreakDeepNesting:
    """Tests for breaking deep nesting."""

    def test_shallow_nesting_unchanged(self):
        text, modified = _break_deep_nesting("[[nested]]", max_depth=5)
        assert text == "[[nested]]"
        assert not modified

    def test_deep_nesting_reduced(self):
        # Create deeply nested structure
        text = "[" * 15 + "deep" + "]" * 15
        result, modified = _break_deep_nesting(text, max_depth=5)
        assert modified
        assert _count_nesting_depth(result) <= 5

    def test_preserves_text_content(self):
        text = "[[[content]]]"
        result, modified = _break_deep_nesting(text, max_depth=2)
        assert "content" in result


class TestFixNestedEmphasis:
    """Tests for emphasis fixing."""

    def test_balanced_emphasis_unchanged(self):
        text, modified = _fix_nested_emphasis("**bold** and *italic*")
        assert text == "**bold** and *italic*"
        assert not modified

    def test_unbalanced_emphasis(self):
        text, modified = _fix_nested_emphasis("***odd***emphasis***")
        # Should have balanced count of markers
        assert modified or text.count("*") % 2 == 0

    def test_deeply_nested_emphasis(self):
        text, modified = _fix_nested_emphasis("***a***b***c***d***")
        # Should detect the problematic pattern
        assert modified or "***" not in text


class TestStripComplexMarkdown:
    """Tests for safe mode stripping."""

    def test_removes_links(self):
        text = "Check [this link](https://example.com) here"
        result = _strip_complex_markdown(text)
        assert "https://example.com" not in result
        assert "this link" in result

    def test_removes_images(self):
        text = "See ![alt text](image.jpg)"
        result = _strip_complex_markdown(text)
        assert "image.jpg" not in result
        assert "alt text" in result

    def test_removes_html(self):
        text = "Some <span class='test'>HTML</span> content"
        result = _strip_complex_markdown(text)
        assert "<span" not in result
        assert "HTML" in result

    def test_simplifies_emphasis(self):
        text = "***very bold***"
        result = _strip_complex_markdown(text)
        # Should simplify to double or single emphasis
        assert "***" not in result


class TestSanitizeMarkdown:
    """Tests for the main sanitize_markdown function."""

    def test_clean_markdown_unchanged(self):
        text = "Simple [link](url) text"
        result = sanitize_markdown(text)
        assert result.text == text
        assert not result.was_sanitized
        assert not result.depth_warning

    def test_unbalanced_brackets_fixed(self):
        text = "Unbalanced [bracket"
        result = sanitize_markdown(text)
        assert result.was_sanitized
        assert "[" not in result.text or result.text.count("[") == result.text.count("]")

    def test_deep_nesting_fixed(self):
        deep = "[[[[[[[[[[[[very deep]]]]]]]]]]]]"
        result = sanitize_markdown(deep)
        assert result.was_sanitized
        assert result.depth_warning
        assert _count_nesting_depth(result.text) <= 10

    def test_safe_mode_strips_complex(self):
        text = "Complex [link](url) with ![image](img.jpg)"
        result = sanitize_markdown(text, safe_mode=True)
        assert result.was_sanitized
        assert "url" not in result.text
        assert "img.jpg" not in result.text
        assert "link" in result.text
        assert "image" in result.text

    def test_rtl_target_triggers_rtl_fix(self):
        text = "]reversed["
        result = sanitize_markdown(text, target_lang="ar")
        assert result.was_sanitized
        assert "[reversed]" in result.text

    def test_issues_tracked(self):
        text = "[[[[deep]]]] and unbalanced["
        result = sanitize_markdown(text)
        assert len(result.issues_found) > 0


class TestValidateMarkdownDepth:
    """Tests for markdown depth validation."""

    def test_valid_depth(self):
        is_valid, depth = validate_markdown_depth("[link](url)")
        assert is_valid
        assert depth == 1

    def test_invalid_depth(self):
        deep = "[" * 20 + "text" + "]" * 20
        is_valid, depth = validate_markdown_depth(deep, max_depth=10)
        assert not is_valid
        assert depth == 20


class TestShouldUseSafeMode:
    """Tests for safe mode detection."""

    def test_rtl_targets_suggest_safe_mode(self):
        # RTL languages should suggest safe mode when auto is enabled
        from src.config import config
        original = config.MARKDOWN_SAFE_MODE_AUTO
        try:
            config.MARKDOWN_SAFE_MODE_AUTO = True
            assert should_use_safe_mode("en", "ar")
            assert should_use_safe_mode("en", "he")
            assert should_use_safe_mode("en", "fa")
        finally:
            config.MARKDOWN_SAFE_MODE_AUTO = original

    def test_non_rtl_no_safe_mode(self):
        from src.config import config
        original = config.MARKDOWN_SAFE_MODE_AUTO
        try:
            config.MARKDOWN_SAFE_MODE_AUTO = True
            assert not should_use_safe_mode("en", "de")
            assert not should_use_safe_mode("en", "fr")
        finally:
            config.MARKDOWN_SAFE_MODE_AUTO = original


class TestSanitizeTranslations:
    """Tests for batch translation sanitization."""

    def test_list_sanitization(self):
        """Test sanitization of markdown content in list."""
        texts = [
            "Clean [link](url) text",  # Valid markdown, no issues
            "Unbalanced [link](url[nested)",  # Markdown with unbalanced brackets
            "[[[[deep]]]](url)"  # Deeply nested markdown
        ]
        results, any_sanitized, issues = sanitize_translations(texts, "en", "fr")
        assert len(results) == len(texts)
        assert any_sanitized

    def test_plain_text_skipped(self):
        """Non-markdown content should be passed through unchanged."""
        texts = [
            "Plain text without any markdown",
            "Just regular sentences here.",
            "No links, no formatting."
        ]
        results, any_sanitized, issues = sanitize_translations(texts, "en", "fr")
        assert results == texts  # Unchanged
        assert not any_sanitized  # Nothing sanitized

    def test_disabled_returns_unchanged(self):
        from src.config import config
        original = config.MARKDOWN_SANITIZE
        try:
            config.MARKDOWN_SANITIZE = False
            texts = ["Unbalanced [bracket"]
            results, any_sanitized, issues = sanitize_translations(texts, "en", "fr")
            assert results == texts
            assert not any_sanitized
        finally:
            config.MARKDOWN_SANITIZE = original


class TestRealWorldPatterns:
    """Tests based on real-world problematic patterns."""

    def test_multiple_links_in_paragraph(self):
        """Test pattern from the alt-text blog post."""
        text = """Check [nuget package](https://www.nuget.org/packages/Mostlylucid.LlmAltText)
and [here](https://github.com/scottgal/mostlylucid.nugetpackages/tree/main/Mostlylucid.AltText.Demo)
for a demo site."""
        result = sanitize_markdown(text)
        # Should be valid already
        assert _count_nesting_depth(result.text) <= 10

    def test_badge_links(self):
        """Test NuGet badge pattern."""
        text = """[![NuGet](https://img.shields.io/nuget/v/mostlylucid.llmaltText.svg)](https://www.nuget.org/packages/mostlylucid.llmalttext)"""
        result = sanitize_markdown(text)
        assert _count_nesting_depth(result.text) <= 10

    def test_code_blocks_preserved(self):
        """Code blocks should pass through."""
        text = """```csharp
var text = "brackets [in] code";
```"""
        result = sanitize_markdown(text)
        # Code blocks aren't real markdown nesting
        assert result.text == text or "brackets [in] code" in result.text

    def test_table_syntax(self):
        """Tables with pipes shouldn't cause issues."""
        text = """| Type | Description |
|------|-------------|
| Photo | Real images |"""
        result = sanitize_markdown(text)
        assert _count_nesting_depth(result.text) <= 10

    def test_mermaid_diagram(self):
        """Mermaid diagrams have their own syntax."""
        text = """```mermaid
flowchart TB
    subgraph Input[Image Sources]
        A[File Path]
    end
```"""
        result = sanitize_markdown(text)
        # Should handle without breaking
        assert "File Path" in result.text or "flowchart" in result.text

    def test_simulated_arabic_translation_issue(self):
        """Simulate what might happen with Arabic translation."""
        # Arabic translations might reverse or double brackets
        text = "[نص](رابط[متداخل](أكثر))"  # Nested link pattern in Arabic
        result = sanitize_markdown(text, target_lang="ar")
        assert _count_nesting_depth(result.text) <= 10

    def test_french_translation_pattern(self):
        """French might add spaces around brackets."""
        text = "[ lien ] ( url ) avec [ plus ]"
        result = sanitize_markdown(text, target_lang="fr")
        assert _count_nesting_depth(result.text) <= 10


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_input(self):
        result = sanitize_markdown("")
        assert result.text == ""
        assert not result.was_sanitized

    def test_none_like_empty(self):
        result = sanitize_markdown("")
        assert result.text == ""

    def test_only_brackets(self):
        result = sanitize_markdown("[[[]]]]")
        # Should either balance or strip
        assert result.text.count("[") == result.text.count("]")

    def test_unicode_content_preserved(self):
        text = "[中文链接](url) and [العربية](url2)"
        result = sanitize_markdown(text)
        assert "中文链接" in result.text
        assert "العربية" in result.text

    def test_very_long_text(self):
        """Performance test with long text."""
        text = "[link](url) " * 1000
        result = sanitize_markdown(text)
        assert len(result.text) > 0  # Should complete without error
