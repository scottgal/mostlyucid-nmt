"""Emergency debug script - find out WHY translations return empty!"""

import os
import sys

# Force maximum logging
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["REQUEST_LOG"] = "1"
os.environ["MODEL_FAMILY"] = "opus-mt"

print("=" * 80)
print("EMERGENCY TRANSLATION DEBUGGER")
print("=" * 80)

# Test 1: Direct model loading
print("\n[TEST 1] Direct Model Loading")
print("-" * 80)
from src.services.model_manager import model_manager
from src.core.logging import logger

try:
    pipeline = model_manager.get_pipeline("en", "de")
    print(f"✓ Pipeline loaded: {type(pipeline)}")

    # Test translation
    result = pipeline(["Hello world"], max_length=512, num_beams=1, batch_size=1)
    print(f"✓ Direct result: {result}")
    translation = result[0].get('translation_text', 'NONE')
    print(f"✓ Translation: '{translation}'")
except Exception as e:
    print(f"✗ FAILED: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Translation Service
print("\n[TEST 2] Translation Service")
print("-" * 80)
from concurrent.futures import ThreadPoolExecutor
from src.services.translation_service import TranslationService

try:
    executor = ThreadPoolExecutor(max_workers=1)
    service = TranslationService(executor)
    print(f"✓ Service created: {service}")

    # Call translate_texts_aligned directly
    translations, pivot = service.translate_texts_aligned(
        ["Hello world"],
        "en",
        "de",
        1,  # beam size
        False  # sentence splitting
    )
    print(f"✓ Service result: {translations}")
    print(f"✓ Pivot used: {pivot}")
    print(f"✓ Translation: '{translations[0] if translations else 'EMPTY LIST'}'")
except Exception as e:
    print(f"✗ FAILED: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Full API stack (without HTTP)
print("\n[TEST 3] Full API Stack (Simulated)")
print("-" * 80)

try:
    import asyncio

    async def test_api():
        from src.services.translation_service import TranslationService
        from concurrent.futures import ThreadPoolExecutor

        executor = ThreadPoolExecutor(max_workers=1)
        service = TranslationService(executor)

        # This is what the API does
        texts = ["Hello world"]
        src = "en"
        tgt = "de"
        beam = 1
        sentence_split = False

        print(f"  Input: {texts}")
        print(f"  From: {src} To: {tgt}")
        print(f"  Beam: {beam}, Split: {sentence_split}")

        result = await service.translate_async(texts, src, tgt, beam, sentence_split, False)
        translations, pivot, metadata = result

        print(f"✓ API result: {translations}")
        print(f"✓ Translation: '{translations[0] if translations else 'EMPTY'}'")

        return translations[0] if translations else ""

    result = asyncio.run(test_api())
    print(f"\nFinal translation: '{result}'")

    if not result or result == "":
        print("\n" + "!" * 80)
        print("!!! EMPTY TRANSLATION DETECTED !!!")
        print("!!! Check the DEBUG logs above to see where it failed !!!")
        print("!" * 80)
    else:
        print("\n" + "=" * 80)
        print(f"SUCCESS! Got translation: '{result}'")
        print("=" * 80)

except Exception as e:
    print(f"✗ FAILED: {e}")
    import traceback
    traceback.print_exc()

# Show config
print("\n[CONFIG] Current Settings")
print("-" * 80)
from src.config import config
print(f"  INPUT_SANITIZE: {config.INPUT_SANITIZE}")
print(f"  INPUT_MIN_CHARS: {config.INPUT_MIN_CHARS}")
print(f"  INPUT_MIN_ALNUM_RATIO: {config.INPUT_MIN_ALNUM_RATIO}")
print(f"  SANITIZE_PLACEHOLDER: '{config.SANITIZE_PLACEHOLDER}'")
print(f"  SYMBOL_MASKING: {config.SYMBOL_MASKING}")
print(f"  MODEL_FAMILY: {config.MODEL_FAMILY}")
print(f"  LOG_LEVEL: {config.LOG_LEVEL}")
print(f"  REQUEST_LOG: {config.REQUEST_LOG}")

print("\n" + "=" * 80)
print("Debug complete. Check the output above for clues!")
print("=" * 80)
