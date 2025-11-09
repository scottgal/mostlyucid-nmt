"""Test the beautiful download progress bars."""

import os
import sys
import shutil

# Force progress bars even if not on TTY
os.environ["FORCE_PROGRESS_BAR"] = "1"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["MODEL_FAMILY"] = "opus-mt"

# Clear cache to force download
cache_path = os.path.expanduser("~/.cache/huggingface/hub/models--Helsinki-NLP--opus-mt-en-fr")
if os.path.exists(cache_path):
    print(f"Clearing cache: {cache_path}")
    try:
        shutil.rmtree(cache_path)
        print("Cache cleared!\n")
    except Exception as e:
        print(f"Could not clear cache (may already be empty): {e}\n")

from src.services.model_manager import model_manager
from src.core.logging import logger

def test_download():
    """Test downloading a model with progress bars."""
    print("=" * 80)
    print("  Testing Beautiful Download Progress Bars")
    print("  This will download Helsinki-NLP/opus-mt-en-fr (~300 MB)")
    print("=" * 80)
    print()

    try:
        # Load a model (this will download if not cached)
        print("Starting model download...\n")
        pipeline = model_manager.get_pipeline("en", "fr")

        print("\nTesting translation with loaded model...")
        test_text = ["Hello world", "How are you?", "This is a test"]
        results = pipeline(test_text, max_length=512, num_beams=1, batch_size=len(test_text))

        print("\nTranslation Results:")
        print("-" * 80)
        for src, result in zip(test_text, results):
            translation = result.get('translation_text', '')
            print(f"  EN: {src}")
            print(f"  FR: {translation}")
            print()

        print("=" * 80)
        print("  ✓ Download and translation test completed successfully!")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n[ERROR] Test failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_download()
    sys.exit(0 if success else 1)
