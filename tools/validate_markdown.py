#!/usr/bin/env python3
"""Markdown validation and sanitization tool.

Usage:
    # Validate a single string
    python tools/validate_markdown.py "Some [markdown](url) text"

    # Validate a file
    python tools/validate_markdown.py -f input.md

    # Sanitize and output result
    python tools/validate_markdown.py --sanitize "Some [[nested](url)](more)"

    # Test with safe mode
    python tools/validate_markdown.py --safe-mode "Complex **[markdown](url)**"

    # Validate against Markdig (requires .NET)
    python tools/validate_markdown.py --markdig "Some markdown"
"""

import argparse
import sys
import subprocess
import tempfile
import os

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.markdown_sanitizer import (
    sanitize_markdown,
    validate_markdown_depth,
    SanitizationResult,
    _count_nesting_depth,
)


def validate_with_markdig(text: str) -> tuple[bool, str]:
    """Validate markdown using Markdig .NET library.

    Requires dotnet SDK and Markdig package.

    Args:
        text: Markdown text to validate

    Returns:
        Tuple of (success, error_message)
    """
    # Create a minimal C# program to validate with Markdig
    cs_code = '''
using System;
using Markdig;

class Program {
    static int Main(string[] args) {
        try {
            string input = Console.In.ReadToEnd();
            var pipeline = new MarkdownPipelineBuilder()
                .UseAdvancedExtensions()
                .Build();
            var result = Markdown.ToHtml(input, pipeline);
            Console.WriteLine("OK");
            return 0;
        } catch (Exception ex) {
            Console.Error.WriteLine(ex.Message);
            return 1;
        }
    }
}
'''

    try:
        # Create temp directory for the project
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write project file
            csproj_path = os.path.join(tmpdir, "validate.csproj")
            with open(csproj_path, "w") as f:
                f.write('''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>disable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Markdig" Version="0.37.0" />
  </ItemGroup>
</Project>
''')

            # Write C# code
            cs_path = os.path.join(tmpdir, "Program.cs")
            with open(cs_path, "w") as f:
                f.write(cs_code)

            # Build and run
            build_result = subprocess.run(
                ["dotnet", "build", "-c", "Release", "-o", os.path.join(tmpdir, "out")],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=60
            )

            if build_result.returncode != 0:
                return False, f"Build failed: {build_result.stderr}"

            # Run the validator
            run_result = subprocess.run(
                ["dotnet", os.path.join(tmpdir, "out", "validate.dll")],
                input=text,
                capture_output=True,
                text=True,
                timeout=30
            )

            if run_result.returncode == 0:
                return True, "Markdig validation passed"
            else:
                return False, run_result.stderr.strip()

    except FileNotFoundError:
        return False, "dotnet SDK not found. Install .NET SDK to use Markdig validation."
    except subprocess.TimeoutExpired:
        return False, "Markdig validation timed out"
    except Exception as e:
        return False, f"Markdig validation error: {e}"


def print_result(result: SanitizationResult, verbose: bool = False) -> None:
    """Print sanitization result."""
    if result.was_sanitized:
        print(f"[SANITIZED] Issues found: {len(result.issues_found)}")
        if verbose:
            for issue in result.issues_found:
                print(f"  - {issue}")
    else:
        print("[OK] No sanitization needed")

    if result.depth_warning:
        print("[WARNING] Depth exceeded threshold")


def main():
    parser = argparse.ArgumentParser(
        description="Validate and sanitize markdown to prevent parser depth errors"
    )
    parser.add_argument(
        "text",
        nargs="?",
        help="Markdown text to validate (or use -f for file)"
    )
    parser.add_argument(
        "-f", "--file",
        help="Read markdown from file"
    )
    parser.add_argument(
        "--sanitize",
        action="store_true",
        help="Sanitize the markdown and output the result"
    )
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Use safe mode (strip complex markdown)"
    )
    parser.add_argument(
        "--markdig",
        action="store_true",
        help="Validate using Markdig .NET library"
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Maximum allowed nesting depth (default: 10)"
    )
    parser.add_argument(
        "--source-lang",
        default="en",
        help="Source language code (default: en)"
    )
    parser.add_argument(
        "--target-lang",
        default="en",
        help="Target language code (default: en)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only output sanitized text (no status messages)"
    )

    args = parser.parse_args()

    # Get input text
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
    elif args.text:
        text = args.text
    else:
        # Read from stdin
        text = sys.stdin.read()

    if not text:
        print("Error: No input text provided", file=sys.stderr)
        sys.exit(1)

    # Check depth
    depth = _count_nesting_depth(text)
    is_valid, actual_depth = validate_markdown_depth(text, args.max_depth)

    if not args.quiet:
        print(f"Nesting depth: {actual_depth} (max: {args.max_depth})")
        if not is_valid:
            print(f"[WARNING] Depth {actual_depth} exceeds limit {args.max_depth}")

    # Sanitize if requested or if depth exceeded
    if args.sanitize or not is_valid:
        result = sanitize_markdown(
            text,
            source_lang=args.source_lang,
            target_lang=args.target_lang,
            safe_mode=args.safe_mode
        )

        if not args.quiet:
            print_result(result, args.verbose)
            print("\n--- Sanitized output ---")

        print(result.text)

        # Verify result
        new_depth = _count_nesting_depth(result.text)
        if not args.quiet and new_depth != actual_depth:
            print(f"\n--- Depth reduced: {actual_depth} -> {new_depth} ---")
    else:
        if not args.quiet:
            print("[OK] Markdown depth within limits")
        if args.verbose:
            print(text)

    # Markdig validation if requested
    if args.markdig:
        if not args.quiet:
            print("\n--- Markdig validation ---")

        final_text = result.text if (args.sanitize or not is_valid) else text
        success, message = validate_with_markdig(final_text)

        if success:
            if not args.quiet:
                print(f"[OK] {message}")
            sys.exit(0)
        else:
            print(f"[FAIL] {message}", file=sys.stderr)
            sys.exit(1)

    # Exit with error if depth exceeded and not sanitizing
    if not is_valid and not args.sanitize:
        sys.exit(1)


if __name__ == "__main__":
    main()
