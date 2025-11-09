#!/usr/bin/env python3
"""
Preload a curated set of models into a fixed directory using Hugging Face snapshot_download,
fetching only the minimal files required at runtime (weights + tokenizer/config).

Usage:
  # Preload by language list (en<->XX):
  python preload_models.py --family opus-mt --langs "es,fr,de" --dest /app/models

  # Preload by explicit language PAIRS:
  python preload_models.py --family opus-mt --pairs "en->de,de->en,ja->de" --dest /app/models

Notes:
- Supports Opus‑MT. When using --langs, it preloads EN<->XX for each language.
- When using --pairs, it attempts to preload the exact direction XX->YY. If a direct
  pair does not exist for Opus‑MT and neither side is English, it will try a smart
  pivot preload via English by fetching XX->en and en->YY.
- Downloads only allow-listed files to keep layers small.
- If both safetensors and bin are present, safetensors will be preferred at runtime;
  we download both when provided since some repos vary.
"""
import argparse
import os
import sys
from typing import List, Tuple

try:
    from huggingface_hub import snapshot_download
except Exception as e:
    print("[preload] Missing dependency huggingface_hub; ensure transformers installs it.", file=sys.stderr)
    raise

ALLOWED_FILES = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "merges.txt",
    "vocab.json",
    "vocab.spm",
    "source.spm",
    "target.spm",
    "sentencepiece.*",
    "spiece.model",
    "*.model",
    "pytorch_model.bin",
    "model.safetensors",
    "*.safetensors",
]

LANG_MAP = {
    # identity mapping for common ISO codes; adjust if a repo uses different code
    "zh": "zh",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "nl": "nl",
    "hi": "hi",
    "ar": "ar",
    "uk": "uk",
    "fi": "fi",
    "sv": "sv",
    "el": "el",
}


def opus_mt_repo_pairs(lang_code: str) -> List[str]:
    """Return the two Helsinki-NLP/opus-mt repos for en<->lang_code.
    Example: lang_code='de' -> ['Helsinki-NLP/opus-mt-en-de', 'Helsinki-NLP/opus-mt-de-en']
    """
    lc = LANG_MAP.get(lang_code, lang_code)
    return [
        f"Helsinki-NLP/opus-mt-en-{lc}",
        f"Helsinki-NLP/opus-mt-{lc}-en",
    ]


def opus_mt_repo_for_pair(src: str, tgt: str) -> str:
    src = LANG_MAP.get(src, src)
    tgt = LANG_MAP.get(tgt, tgt)
    return f"Helsinki-NLP/opus-mt-{src}-{tgt}"


def parse_pair(pair: str) -> Tuple[str, str]:
    if "->" not in pair:
        raise ValueError(f"Invalid pair format '{pair}', expected 'xx->yy'")
    a, b = pair.split("->", 1)
    a = a.strip().lower()
    b = b.strip().lower()
    if not a or not b or a == b:
        raise ValueError(f"Invalid pair '{pair}'")
    return a, b


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--family", required=True, choices=["opus-mt"], help="Model family to preload")
    p.add_argument("--langs", required=False, default="", help="Comma-separated language codes (e.g., 'es,fr,de') for EN<->XX preloads")
    p.add_argument("--pairs", required=False, default="", help="Comma-separated language pairs (e.g., 'en->de,de->en,ja->de')")
    p.add_argument("--dest", required=True, help="Destination root directory to place models")
    return p.parse_args()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def download_repo(repo: str, dest_root: str) -> None:
    out_dir = os.path.join(dest_root, repo.replace("/", "--"))
    ensure_dir(out_dir)
    print(f"[preload] downloading {repo} -> {out_dir}")
    snapshot_download(
        repo_id=repo,
        local_dir=out_dir,
        local_dir_use_symlinks=False,
        allow_patterns=ALLOWED_FILES,
        ignore_patterns=["*.md", "*.txt", "*.jsonl", "*.png", "*.jpg", "*.jpeg", "*.gif", "tests*", "*train*", "*eval*", "*.h5"],
        resume_download=True,
    )


def main() -> None:
    args = parse_args()
    dest_root = os.path.abspath(args.dest)
    ensure_dir(dest_root)

    pairs_arg = (args.pairs or "").strip()
    langs_arg = (args.langs or "").strip()

    print(f"[preload] family={args.family} pairs={pairs_arg} langs={langs_arg} dest={dest_root}")

    repos: List[str] = []

    if args.family == "opus-mt":
        if pairs_arg:
            raw_pairs = [x.strip() for x in pairs_arg.split(",") if x.strip()]
            for p in raw_pairs:
                try:
                    src, tgt = parse_pair(p)
                except ValueError as ve:
                    print(f"[preload] skip invalid pair '{p}': {ve}", file=sys.stderr)
                    continue

                # Try direct pair first
                direct_repo = opus_mt_repo_for_pair(src, tgt)
                try:
                    download_repo(direct_repo, dest_root)
                except Exception as e:
                    # Fallback: if neither side is English, attempt pivot via English
                    if src != "en" and tgt != "en":
                        try:
                            download_repo(opus_mt_repo_for_pair(src, "en"), dest_root)
                            download_repo(opus_mt_repo_for_pair("en", tgt), dest_root)
                            print(f"[preload] used pivot via en for {src}->{tgt}")
                        except Exception as e2:
                            print(f"[preload] failed to preload {src}->{tgt} (direct and pivot failed): {e2}", file=sys.stderr)
                    else:
                        print(f"[preload] failed to preload {src}->{tgt}: {e}", file=sys.stderr)
        elif langs_arg:
            langs = [x.strip() for x in langs_arg.split(",") if x.strip()]
            for lc in langs:
                repos.extend(opus_mt_repo_pairs(lc))
        else:
            print("[preload] Nothing to do: neither --pairs nor --langs provided", file=sys.stderr)

    # De-duplicate repos (for langs mode)
    if repos:
        seen = set()
        repos = [r for r in repos if not (r in seen or seen.add(r))]
        for repo in repos:
            try:
                download_repo(repo, dest_root)
            except Exception as e:
                print(f"[preload] failed to download {repo}: {e}", file=sys.stderr)

    print("[preload] done")


if __name__ == "__main__":
    main()
