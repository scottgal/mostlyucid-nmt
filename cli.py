#!/usr/bin/env python3
"""MostlyLucid-NMT Command Line Interface.

This is the main entry point for the standalone executable.
Provides server mode, batch translation, and cache management.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Fix Windows console UTF-8 encoding
if sys.platform == "win32":
    # Enable UTF-8 mode for Windows console
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def print_banner():
    """Print startup banner."""
    print("""
================================================================================
  MostlyLucid-NMT - Machine Translation Service
================================================================================

  Supports 150+ languages via multiple model families:
    - Opus-MT:  2,177 language pairs (instant download, pre-converted)
    - M2M100:   100 languages, any-to-any translation
    - mBART50:  50 languages, any-to-any translation

  Backend: CTranslate2 (fast, lightweight inference)
""")


def print_quick_start():
    """Print quick start guide."""
    print("""
QUICK START
-----------

  1. Start the server:
     mostlylucid-nmt serve

  2. Translate via API:
     curl -X POST http://localhost:8000/translate \\
       -H "Content-Type: application/json" \\
       -d '{"text": ["Hello world"], "target_lang": "de", "source_lang": "en"}'

  3. Or translate from command line:
     mostlylucid-nmt translate "Hello world" --to de

  4. Open the web demo:
     http://localhost:8000/demo/


FIRST-TIME USE
--------------

  Models are downloaded automatically on first use:
    - Opus-MT & M2M100: Pre-converted models, instant download (~300MB each)
    - mBART50: Requires conversion on first use (~5-10 min, then cached)

  Models are cached in: ~/.cache/mostlylucid-nmt/ct2/


COMMON COMMANDS
---------------

  mostlylucid-nmt serve              Start HTTP server on port 8000
  mostlylucid-nmt serve -p 9000      Start on custom port
  mostlylucid-nmt translate "text"   Translate text from CLI
  mostlylucid-nmt cache              Show cached models
  mostlylucid-nmt langs              List supported languages
  mostlylucid-nmt --help             Show all options


ENVIRONMENT VARIABLES
---------------------

  PORT=8000                 HTTP server port
  HOST=0.0.0.0             Bind address
  MODEL_FAMILY=opus-mt     Default model family (opus-mt, mbart50, m2m100)
  PRELOAD_MODELS=en->de    Preload specific language pairs at startup
  MODEL_CACHE_DIR=./cache  Custom cache directory

""")


def cmd_serve(args):
    """Start the HTTP server."""
    import uvicorn

    # Set environment from args
    os.environ.setdefault("HOST", args.host)
    os.environ.setdefault("PORT", str(args.port))

    if args.preload:
        os.environ["PRELOAD_MODELS"] = args.preload

    if args.family:
        os.environ["MODEL_FAMILY"] = args.family

    if args.cache_dir:
        os.environ["MODEL_CACHE_DIR"] = args.cache_dir

    print(f"Starting MostlyLucid-NMT server on http://{args.host}:{args.port}")
    print(f"  Model family: {os.environ.get('MODEL_FAMILY', 'opus-mt')}")
    print(f"  Demo UI: http://{args.host}:{args.port}/demo/")
    print(f"  API docs: http://{args.host}:{args.port}/docs")
    print()

    # Import and run
    from src.app import app
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


def cmd_translate(args):
    """Translate text from command line."""
    # Set backend
    os.environ.setdefault("TRANSLATION_BACKEND", "ct2")
    os.environ.setdefault("LOG_LEVEL", "WARNING")

    if args.family:
        os.environ["MODEL_FAMILY"] = args.family

    # Import after env setup
    from src.core.ct2_loader import get_ct2_loader
    from src.core.ct2_wrapper import CT2TranslatorWrapper

    src_lang = args.source or "en"
    tgt_lang = args.target
    family = args.family or os.environ.get("MODEL_FAMILY", "opus-mt")

    if not args.quiet:
        print(f"Translating {src_lang} -> {tgt_lang} ({family})...", file=sys.stderr)

    # Get model
    loader = get_ct2_loader()
    model_path, tokenizer_name = loader.get_model_path(src_lang, tgt_lang, family)

    # Create translator
    wrapper = CT2TranslatorWrapper(
        model_path=str(model_path),
        tokenizer_name=tokenizer_name,
        src_lang=src_lang,
        tgt_lang=tgt_lang,
        device="cpu",
        device_index=0,
        family=family
    )

    # Handle input
    if args.text:
        texts = [args.text]
    elif args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            texts = [line.strip() for line in f if line.strip()]
    else:
        # Read from stdin
        if not args.quiet:
            print("Enter text (Ctrl+D/Ctrl+Z to finish):", file=sys.stderr)
        texts = [line.strip() for line in sys.stdin if line.strip()]

    if not texts:
        print("No text to translate", file=sys.stderr)
        return

    # Translate with progress for large batches
    start = time.perf_counter()
    if len(texts) > 10 and not args.quiet:
        # Batch with progress
        batch_size = 16
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            results.extend(wrapper(batch))
            pct = min(100, (i + len(batch)) * 100 // len(texts))
            print(f"\rProgress: {pct}% ({i + len(batch)}/{len(texts)})", end="", file=sys.stderr)
        print(file=sys.stderr)
    else:
        results = wrapper(texts)

    elapsed = time.perf_counter() - start

    # Output
    output_lines = [r['translation_text'] for r in results]

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            if args.json:
                json.dump(output_lines, f, ensure_ascii=False, indent=2)
            else:
                for line in output_lines:
                    f.write(line + '\n')
        if not args.quiet:
            print(f"Saved to {args.output} ({len(texts)} texts, {elapsed:.2f}s)", file=sys.stderr)
    elif args.json:
        print(json.dumps(output_lines, ensure_ascii=False, indent=2))
    else:
        for line in output_lines:
            print(line)

    if not args.quiet and len(texts) > 1:
        rate = len(texts) / elapsed
        print(f"Translated {len(texts)} texts in {elapsed:.2f}s ({rate:.1f} texts/sec)", file=sys.stderr)


def cmd_detect(args):
    """Detect language of text."""
    os.environ.setdefault("LOG_LEVEL", "WARNING")

    from src.services.language_detection import language_detector

    # Handle input
    if args.text:
        texts = [args.text]
    elif args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            texts = [line.strip() for line in f if line.strip()]
    else:
        print("Enter text (Ctrl+D/Ctrl+Z to finish):", file=sys.stderr)
        texts = [line.strip() for line in sys.stdin if line.strip()]

    if not texts:
        print("No text to detect", file=sys.stderr)
        return

    # Detect languages
    results = []
    for text in texts:
        lang = language_detector.detect_language(text)
        results.append({"text": text[:50] + "..." if len(text) > 50 else text, "language": lang})

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"{r['language']}: {r['text']}")


def cmd_download(args):
    """Download models ahead of time."""
    os.environ.setdefault("LOG_LEVEL", "INFO")

    from src.core.ct2_loader import get_ct2_loader

    loader = get_ct2_loader()
    pairs = args.pairs.split(",")

    print(f"Downloading {len(pairs)} language pair(s)...")
    print()

    for pair in pairs:
        pair = pair.strip()
        if "->" in pair:
            src, tgt = pair.split("->")
        elif "-" in pair:
            src, tgt = pair.split("-", 1)
        else:
            print(f"Invalid pair format: {pair} (use 'en->de' or 'en-de')")
            continue

        src = src.strip()
        tgt = tgt.strip()
        family = args.family or "opus-mt"

        print(f"Downloading {src} -> {tgt} ({family})...")
        try:
            model_path, _ = loader.get_model_path(src, tgt, family)
            print(f"  Cached at: {model_path}")
        except Exception as e:
            print(f"  Failed: {e}")

    print()
    print("Download complete. Use 'cache' command to see cached models.")


def cmd_benchmark(args):
    """Run performance benchmark."""
    os.environ.setdefault("TRANSLATION_BACKEND", "ct2")
    os.environ.setdefault("LOG_LEVEL", "WARNING")

    from src.core.ct2_loader import get_ct2_loader
    from src.core.ct2_wrapper import CT2TranslatorWrapper

    print("MostlyLucid-NMT Performance Benchmark")
    print("=" * 50)
    print()

    # Load model
    print("Loading model (en->de, opus-mt)...")
    loader = get_ct2_loader()
    model_path, tokenizer_name = loader.get_model_path("en", "de", "opus-mt")

    wrapper = CT2TranslatorWrapper(
        model_path=str(model_path),
        tokenizer_name=tokenizer_name,
        src_lang="en",
        tgt_lang="de",
        device="cpu",
        device_index=0,
        family="opus-mt"
    )

    # Warmup
    wrapper(["Hello"])
    print("Model loaded and warmed up.")
    print()

    # Benchmark
    test_text = "Hello world, how are you today?"
    iterations = args.iterations

    print(f"Running {iterations} iterations...")
    print()

    # Single sentence
    start = time.perf_counter()
    for _ in range(iterations):
        wrapper([test_text])
    elapsed = time.perf_counter() - start
    single_rate = iterations / elapsed
    print(f"Single sentence: {elapsed:.2f}s total, {elapsed/iterations*1000:.1f}ms/sentence, {single_rate:.1f} sentences/sec")

    # Batch of 10
    batch = [test_text] * 10
    start = time.perf_counter()
    for _ in range(iterations):
        wrapper(batch)
    elapsed = time.perf_counter() - start
    batch_rate = (iterations * 10) / elapsed
    print(f"Batch of 10:     {elapsed:.2f}s total, {elapsed/iterations*1000:.1f}ms/batch, {batch_rate:.1f} sentences/sec")

    # Batch of 50
    batch = [test_text] * 50
    start = time.perf_counter()
    for _ in range(max(1, iterations // 4)):
        wrapper(batch)
    elapsed = time.perf_counter() - start
    iters = max(1, iterations // 4)
    batch50_rate = (iters * 50) / elapsed
    print(f"Batch of 50:     {elapsed:.2f}s total, {elapsed/iters*1000:.1f}ms/batch, {batch50_rate:.1f} sentences/sec")

    print()
    print(f"Peak throughput: {max(single_rate, batch_rate, batch50_rate):.1f} sentences/sec")


def cmd_cache(args):
    """Show or manage cached models."""
    os.environ.setdefault("LOG_LEVEL", "WARNING")

    from src.core.ct2_loader import get_ct2_loader

    loader = get_ct2_loader()

    if args.clear:
        family = args.clear if args.clear != "all" else None
        count = loader.clear_cache(family)
        print(f"Cleared {count} cached model(s)")
        return

    info = loader.get_cache_info()

    print(f"CT2 Model Cache: {info['cache_dir']}")
    print(f"Total size: {info['total_size_mb']:.1f} MB")
    print()

    if not info['families']:
        print("  (no cached models)")
        print()
        print("Models are downloaded on first translation request.")
        return

    for family_name, family_info in info['families'].items():
        print(f"  {family_name}/ ({family_info['total_size_mb']:.1f} MB)")
        for model in family_info['models']:
            print(f"    - {model['name']} ({model['size_mb']:.1f} MB)")
            print(f"        Source: {model['source']}")


def cmd_langs(args):
    """List supported languages."""
    os.environ.setdefault("LOG_LEVEL", "WARNING")

    from src.config import config

    family = args.family or config.MODEL_FAMILY

    print(f"Supported languages for {family}:")
    print()

    if family == "opus-mt":
        print("  Opus-MT supports 150+ languages with 2,177 pre-converted pairs.")
        print("  Common pairs include: en, de, fr, es, it, pt, nl, pl, ru, zh, ja, ko, ar")
        print()
        print("  Check specific pair availability:")
        print("    curl http://localhost:8000/discover/opus-mt")

    elif family == "mbart50":
        langs = sorted(config.MBART50_LANGS)
        print(f"  {len(langs)} languages supported:")
        print(f"  {', '.join(langs)}")

    elif family == "m2m100":
        langs = sorted(config.M2M100_LANGS)
        print(f"  {len(langs)} languages supported:")
        print(f"  {', '.join(langs)}")

    print()


def cmd_info(args):
    """Show system information."""
    os.environ.setdefault("LOG_LEVEL", "WARNING")

    print("System Information")
    print("=" * 40)

    # Python version
    print(f"Python: {sys.version}")

    # Check CT2
    try:
        import ctranslate2
        print(f"CTranslate2: {ctranslate2.__version__}")

        # Check CUDA
        cuda_devices = ctranslate2.get_cuda_device_count()
        print(f"CUDA devices: {cuda_devices}")
    except ImportError:
        print("CTranslate2: Not installed")

    # Check PyTorch (optional)
    try:
        import torch
        print(f"PyTorch: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA device: {torch.cuda.get_device_name(0)}")
    except ImportError:
        print("PyTorch: Not installed (optional for CT2 backend)")

    # Check transformers
    try:
        import transformers
        print(f"Transformers: {transformers.__version__}")
    except ImportError:
        print("Transformers: Not installed")

    # Cache location
    from pathlib import Path
    cache_dir = os.environ.get("MODEL_CACHE_DIR") or Path.home() / ".cache" / "mostlylucid-nmt"
    print(f"Cache dir: {cache_dir}")

    print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="mostlylucid-nmt",
        description="MostlyLucid-NMT - Fast Machine Translation Service",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--version", action="version", version="MostlyLucid-NMT 3.2.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start HTTP server")
    serve_parser.add_argument("-p", "--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    serve_parser.add_argument("-H", "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    serve_parser.add_argument("--preload", help="Preload models (e.g., 'en->de,de->en')")
    serve_parser.add_argument("--family", choices=["opus-mt", "mbart50", "m2m100"], help="Default model family")
    serve_parser.add_argument("--cache-dir", help="Model cache directory")

    # translate command
    translate_parser = subparsers.add_parser("translate", help="Translate text")
    translate_parser.add_argument("text", nargs="?", help="Text to translate (or use --file or stdin)")
    translate_parser.add_argument("-t", "--target", "--to", required=True, help="Target language code")
    translate_parser.add_argument("-s", "--source", "--from", help="Source language code (default: en)")
    translate_parser.add_argument("-f", "--file", help="Read text from file (one per line)")
    translate_parser.add_argument("-o", "--output", help="Write output to file")
    translate_parser.add_argument("--family", choices=["opus-mt", "mbart50", "m2m100"], help="Model family")
    translate_parser.add_argument("--json", action="store_true", help="Output as JSON")
    translate_parser.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")

    # detect command
    detect_parser = subparsers.add_parser("detect", help="Detect language of text")
    detect_parser.add_argument("text", nargs="?", help="Text to detect (or use --file or stdin)")
    detect_parser.add_argument("-f", "--file", help="Read text from file (one per line)")
    detect_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # download command
    download_parser = subparsers.add_parser("download", help="Download models ahead of time")
    download_parser.add_argument("pairs", help="Language pairs to download (e.g., 'en->de,de->en,en->fr')")
    download_parser.add_argument("--family", choices=["opus-mt", "mbart50", "m2m100"], help="Model family")

    # benchmark command
    benchmark_parser = subparsers.add_parser("benchmark", help="Run performance benchmark")
    benchmark_parser.add_argument("-n", "--iterations", type=int, default=20, help="Number of iterations (default: 20)")

    # cache command
    cache_parser = subparsers.add_parser("cache", help="Show/manage cached models")
    cache_parser.add_argument("--clear", nargs="?", const="all", help="Clear cache (optionally specify family)")

    # langs command
    langs_parser = subparsers.add_parser("langs", help="List supported languages")
    langs_parser.add_argument("--family", choices=["opus-mt", "mbart50", "m2m100"], help="Model family")

    # info command
    subparsers.add_parser("info", help="Show system information")

    args = parser.parse_args()

    # No command - show help
    if not args.command:
        print_banner()
        print_quick_start()
        return

    # Dispatch to command handlers
    if args.command == "serve":
        cmd_serve(args)
    elif args.command == "translate":
        cmd_translate(args)
    elif args.command == "detect":
        cmd_detect(args)
    elif args.command == "download":
        cmd_download(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "cache":
        cmd_cache(args)
    elif args.command == "langs":
        cmd_langs(args)
    elif args.command == "info":
        cmd_info(args)


if __name__ == "__main__":
    main()
