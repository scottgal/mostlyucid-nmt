#!/usr/bin/env python3
"""Download and convert translation models to CTranslate2 format.

This script downloads HuggingFace models and converts them to CTranslate2 format
for faster inference and smaller package size.

Usage:
    # Convert all Opus-MT models (WARNING: 1200+ models, ~400GB, takes days)
    python tools/download_and_convert_models.py --output D:/translatemodels --family opus-mt

    # Convert specific language pairs
    python tools/download_and_convert_models.py --output D:/translatemodels --pairs en-de,de-en,en-fr,fr-en

    # Convert common European languages only
    python tools/download_and_convert_models.py --output D:/translatemodels --langs en,de,fr,es,it,pt,nl

    # Convert mBART50 and M2M100 (single models, ~5GB total)
    python tools/download_and_convert_models.py --output D:/translatemodels --family mbart50,m2m100

    # Resume interrupted download
    python tools/download_and_convert_models.py --output D:/translatemodels --resume

    # Dry run - show what would be downloaded
    python tools/download_and_convert_models.py --output D:/translatemodels --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from huggingface_hub import HfApi, list_models


# Common language codes
COMMON_LANGS = {
    "en", "de", "fr", "es", "it", "pt", "nl", "pl", "ru", "zh",
    "ja", "ko", "ar", "hi", "tr", "vi", "th", "id", "sv", "da",
    "no", "fi", "cs", "el", "he", "hu", "ro", "uk", "bg", "hr",
}

# mBART50 supported languages
MBART50_LANGS = {
    "ar", "cs", "de", "en", "es", "et", "fi", "fr", "gu", "hi",
    "it", "ja", "kk", "ko", "lt", "lv", "my", "ne", "nl", "ro",
    "ru", "si", "tr", "uk", "vi", "zh", "af", "az", "bn", "fa",
    "he", "hr", "id", "ka", "km", "mk", "ml", "mn", "mr", "pl",
    "ps", "pt", "sv", "sw", "ta", "te", "th", "tl", "ur", "xh",
}

# M2M100 supported languages (subset - full list is 100 languages)
M2M100_LANGS = {
    "af", "am", "ar", "ast", "az", "ba", "be", "bg", "bn", "br",
    "bs", "ca", "ceb", "cs", "cy", "da", "de", "el", "en", "es",
    "et", "fa", "ff", "fi", "fr", "fy", "ga", "gd", "gl", "gu",
    "ha", "he", "hi", "hr", "ht", "hu", "hy", "id", "ig", "ilo",
    "is", "it", "ja", "jv", "ka", "kk", "km", "kn", "ko", "lb",
    "lg", "ln", "lo", "lt", "lv", "mg", "mk", "ml", "mn", "mr",
    "ms", "my", "ne", "nl", "no", "ns", "oc", "or", "pa", "pl",
    "ps", "pt", "ro", "ru", "sd", "si", "sk", "sl", "so", "sq",
    "sr", "ss", "su", "sv", "sw", "ta", "th", "tl", "tn", "tr",
    "uk", "ur", "uz", "vi", "wo", "xh", "yi", "yo", "zh", "zu",
}


def get_progress_file(output_dir: Path) -> Path:
    """Get path to progress tracking file."""
    return output_dir / "conversion_progress.json"


def load_progress(output_dir: Path) -> dict:
    """Load conversion progress from file."""
    progress_file = get_progress_file(output_dir)
    if progress_file.exists():
        with open(progress_file, "r") as f:
            return json.load(f)
    return {"completed": [], "failed": [], "skipped": []}


def save_progress(output_dir: Path, progress: dict):
    """Save conversion progress to file."""
    progress_file = get_progress_file(output_dir)
    with open(progress_file, "w") as f:
        json.dump(progress, f, indent=2)


def discover_opus_mt_models(
    filter_langs: Optional[Set[str]] = None,
    filter_pairs: Optional[Set[str]] = None,
) -> List[Tuple[str, str, str]]:
    """Discover available Opus-MT models on HuggingFace.

    Returns:
        List of (src, tgt, model_name) tuples
    """
    print("Discovering Opus-MT models on HuggingFace...")
    api = HfApi()

    models = []
    try:
        # Search for Helsinki-NLP opus-mt models
        for model in list_models(author="Helsinki-NLP", search="opus-mt"):
            model_id = model.id
            if not model_id.startswith("Helsinki-NLP/opus-mt-"):
                continue

            # Parse language pair from model name
            # Format: Helsinki-NLP/opus-mt-{src}-{tgt}
            suffix = model_id.replace("Helsinki-NLP/opus-mt-", "")

            # Handle multi-language models (e.g., opus-mt-en-ROMANCE)
            if "-" not in suffix:
                continue

            parts = suffix.split("-")
            if len(parts) == 2:
                src, tgt = parts
            elif len(parts) > 2:
                # Could be something like en-de-fr (multi-target) - skip for now
                src = parts[0]
                tgt = "-".join(parts[1:])
            else:
                continue

            # Apply filters
            if filter_pairs:
                pair_key = f"{src}-{tgt}"
                if pair_key not in filter_pairs:
                    continue

            if filter_langs:
                # Check if either language matches filter
                src_match = src in filter_langs or any(l in src for l in filter_langs)
                tgt_match = tgt in filter_langs or any(l in tgt for l in filter_langs)
                if not (src_match and tgt_match):
                    continue

            models.append((src, tgt, model_id))

    except Exception as e:
        print(f"Error discovering models: {e}")
        return []

    print(f"Found {len(models)} Opus-MT models")
    return sorted(models)


def convert_model(
    model_name: str,
    output_dir: Path,
    quantization: str = "float32",
    force: bool = False,
) -> Tuple[bool, str]:
    """Convert a HuggingFace model to CTranslate2 format.

    Returns:
        Tuple of (success, error_message)
    """
    # Build output path
    if model_name.startswith("Helsinki-NLP/opus-mt-"):
        pair = model_name.replace("Helsinki-NLP/opus-mt-", "")
        ct2_output = output_dir / "opus-mt" / pair
    elif model_name == "facebook/mbart-large-50-many-to-many-mmt":
        ct2_output = output_dir / "mbart50" / "all"
    elif model_name == "facebook/m2m100_418M":
        ct2_output = output_dir / "m2m100" / "all"
    else:
        ct2_output = output_dir / "other" / model_name.replace("/", "_")

    # Check if already converted
    if not force and ct2_output.exists() and (ct2_output / "model.bin").exists():
        return True, "already converted"

    # Create output directory
    ct2_output.mkdir(parents=True, exist_ok=True)

    # Build conversion command
    cmd = [
        "ct2-transformers-converter",
        "--model", model_name,
        "--output_dir", str(ct2_output),
        "--force",
    ]

    # Add quantization if not default
    if quantization and quantization.lower() != "default":
        cmd.extend(["--quantization", quantization])

    # Add low_cpu_mem_usage for large models
    if "mbart" in model_name.lower() or "m2m100" in model_name.lower():
        cmd.append("--low_cpu_mem_usage")

    # Run conversion
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
        )

        if result.returncode != 0:
            # Clean up failed conversion
            if ct2_output.exists():
                import shutil
                shutil.rmtree(ct2_output, ignore_errors=True)
            return False, result.stderr[:500]

        # Write source model info
        (ct2_output / "source_model.txt").write_text(model_name)

        return True, ""

    except subprocess.TimeoutExpired:
        return False, "timeout (30 minutes exceeded)"
    except Exception as e:
        return False, str(e)


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


def estimate_remaining(completed: int, total: int, elapsed: float) -> str:
    """Estimate remaining time."""
    if completed == 0:
        return "unknown"
    rate = elapsed / completed
    remaining = (total - completed) * rate
    return format_duration(remaining)


def main():
    parser = argparse.ArgumentParser(
        description="Download and convert translation models to CTranslate2 format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        required=True,
        help="Output directory for converted models (e.g., D:/translatemodels)",
    )
    parser.add_argument(
        "--family",
        type=str,
        default="opus-mt",
        help="Model family to convert: opus-mt, mbart50, m2m100, or comma-separated list (default: opus-mt)",
    )
    parser.add_argument(
        "--pairs",
        type=str,
        help="Specific language pairs to convert (comma-separated, e.g., en-de,de-en,en-fr)",
    )
    parser.add_argument(
        "--langs",
        type=str,
        help="Filter to pairs involving these languages (comma-separated, e.g., en,de,fr)",
    )
    parser.add_argument(
        "--common-only",
        action="store_true",
        help="Only convert pairs between common languages (30 most common)",
    )
    parser.add_argument(
        "--quantization", "-q",
        type=str,
        default="float32",
        choices=["float32", "float16", "int8", "int8_float16"],
        help="Quantization type (default: float32)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous progress",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-conversion of already converted models",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be converted without actually doing it",
    )
    parser.add_argument(
        "--max-models",
        type=int,
        help="Maximum number of models to convert (useful for testing)",
    )

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse filters
    filter_pairs = None
    if args.pairs:
        filter_pairs = set(args.pairs.split(","))

    filter_langs = None
    if args.langs:
        filter_langs = set(args.langs.split(","))
    elif args.common_only:
        filter_langs = COMMON_LANGS

    # Collect models to convert
    models_to_convert = []
    families = [f.strip() for f in args.family.split(",")]

    for family in families:
        if family == "opus-mt":
            opus_models = discover_opus_mt_models(filter_langs, filter_pairs)
            for src, tgt, model_name in opus_models:
                models_to_convert.append((family, src, tgt, model_name))

        elif family == "mbart50":
            models_to_convert.append(("mbart50", "multi", "multi", "facebook/mbart-large-50-many-to-many-mmt"))

        elif family == "m2m100":
            models_to_convert.append(("m2m100", "multi", "multi", "facebook/m2m100_418M"))

        else:
            print(f"Unknown family: {family}")

    # Apply max limit
    if args.max_models:
        models_to_convert = models_to_convert[:args.max_models]

    total = len(models_to_convert)
    print(f"\nTotal models to convert: {total}")

    if args.dry_run:
        print("\nDry run - models that would be converted:")
        for family, src, tgt, model_name in models_to_convert[:50]:
            print(f"  {model_name}")
        if total > 50:
            print(f"  ... and {total - 50} more")
        return

    # Load progress
    progress = load_progress(output_dir) if args.resume else {"completed": [], "failed": [], "skipped": []}
    completed_set = set(progress["completed"])

    # Filter out already completed
    if args.resume and not args.force:
        models_to_convert = [
            m for m in models_to_convert
            if m[3] not in completed_set
        ]
        print(f"Resuming: {len(completed_set)} already completed, {len(models_to_convert)} remaining")

    if not models_to_convert:
        print("No models to convert!")
        return

    # Convert models
    start_time = time.time()
    converted = 0
    failed = 0
    skipped = 0

    print(f"\nStarting conversion at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output directory: {output_dir}")
    print(f"Quantization: {args.quantization}")
    print("-" * 60)

    for i, (family, src, tgt, model_name) in enumerate(models_to_convert, 1):
        elapsed = time.time() - start_time
        eta = estimate_remaining(converted + failed + skipped, len(models_to_convert), elapsed)

        print(f"\n[{i}/{len(models_to_convert)}] {model_name}")
        print(f"  Progress: {converted} converted, {failed} failed, {skipped} skipped")
        print(f"  Elapsed: {format_duration(elapsed)}, ETA: {eta}")

        success, error = convert_model(
            model_name,
            output_dir,
            quantization=args.quantization,
            force=args.force,
        )

        if success:
            if error == "already converted":
                print(f"  -> Skipped (already converted)")
                skipped += 1
                progress["skipped"].append(model_name)
            else:
                print(f"  -> Success!")
                converted += 1
                progress["completed"].append(model_name)
        else:
            print(f"  -> FAILED: {error}")
            failed += 1
            progress["failed"].append({"model": model_name, "error": error})

        # Save progress after each model
        save_progress(output_dir, progress)

    # Final summary
    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("CONVERSION COMPLETE")
    print("=" * 60)
    print(f"Total time: {format_duration(total_time)}")
    print(f"Converted: {converted}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")
    print(f"Output directory: {output_dir}")

    if failed > 0:
        print(f"\nFailed models saved to: {get_progress_file(output_dir)}")


if __name__ == "__main__":
    main()
