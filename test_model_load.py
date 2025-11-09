"""Diagnostic script to test model loading."""

import os
import sys

# Set minimal config
os.environ["REQUEST_LOG"] = "1"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["MODEL_FAMILY"] = "opus-mt"

from src.services.model_manager import model_manager
from src.core.logging import logger

def test_model_load():
    """Test loading a simple translation model."""
    print("=" * 60)
    print("Testing Model Loading for en->de")
    print("=" * 60)

    try:
        print("\n1. Attempting to load translation pipeline...")
        pipeline = model_manager.get_pipeline("en", "de")
        print("[OK] Pipeline loaded successfully!")

        print("\n2. Testing translation...")
        test_text = ["Hello world"]
        result = pipeline(test_text, max_length=512, num_beams=1, batch_size=1)
        print(f"   Input: {test_text[0]}")
        print(f"   Output: {result[0].get('translation_text', 'NO TRANSLATION')}")
        print(f"   Full result: {result}")

        if result[0].get('translation_text'):
            print("\n[OK] Translation SUCCESSFUL!")
        else:
            print("\n[ERROR] Translation returned empty result")
            return False

    except Exception as e:
        print(f"\n[ERROR] Exception occurred:")
        print(f"   Type: {type(e).__name__}")
        print(f"   Message: {str(e)}")

        # Print full traceback
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()

        return False

    return True

if __name__ == "__main__":
    success = test_model_load()
    sys.exit(0 if success else 1)
