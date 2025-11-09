#!/usr/bin/env python3
"""
Comprehensive API test for mostlylucid-nmt v3.1

Tests:
1. Basic translation pairs (opus-mt)
2. Fallback scenarios (pairs not in opus-mt)
3. Each model family explicitly
4. Pivot translation scenarios
5. Cache behavior across requests
"""

import requests
import json
import time
from typing import Dict, Any, List, Tuple

BASE_URL = "http://localhost:8000"

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text: str):
    """Print a section header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")

def print_test(test_name: str):
    """Print a test name"""
    print(f"{Colors.OKBLUE}[TEST] {test_name}{Colors.ENDC}")

def print_success(message: str):
    """Print success message"""
    print(f"{Colors.OKGREEN}[OK] {message}{Colors.ENDC}")

def print_warning(message: str):
    """Print warning message"""
    print(f"{Colors.WARNING}[WARN] {message}{Colors.ENDC}")

def print_fail(message: str):
    """Print failure message"""
    print(f"{Colors.FAIL}[FAIL] {message}{Colors.ENDC}")

def print_info(message: str):
    """Print info message"""
    print(f"{Colors.OKCYAN}[INFO] {message}{Colors.ENDC}")

def safe_print_translation(translation: str):
    """Safely print translation handling Unicode"""
    try:
        print_success(f"Translation: '{translation}'")
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Fallback for non-ASCII output on Windows
        ascii_safe = translation.encode('ascii', 'ignore').decode('ascii')
        if ascii_safe:
            print_success(f"Translation: '{ascii_safe}' [some chars removed for display]")
        else:
            print_success(f"Translation received (non-ASCII, {len(translation)} chars)")

def translate(
    text: str,
    source_lang: str,
    target_lang: str,
    model_family: str = None,
    beam_size: int = 1
) -> Tuple[bool, Dict[str, Any]]:
    """
    Make a translation request

    Returns:
        (success: bool, response: dict)
    """
    payload = {
        "text": [text],
        "source_lang": source_lang,
        "target_lang": target_lang,
        "beam_size": beam_size,
        "perform_sentence_splitting": False
    }

    if model_family:
        payload["model_family"] = model_family

    try:
        response = requests.post(
            f"{BASE_URL}/translate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {
                "error": f"HTTP {response.status_code}",
                "detail": response.text
            }
    except Exception as e:
        return False, {"error": str(e)}

def get_cache_status() -> Dict[str, Any]:
    """Get cache status"""
    try:
        response = requests.get(f"{BASE_URL}/cache", timeout=10)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception:
        return {}

def test_basic_pairs():
    """Test basic translation pairs that work with opus-mt"""
    print_header("TEST SET 1: Basic Translation Pairs (Opus-MT)")

    test_cases = [
        ("Hello world", "en", "de", "Hallo Welt"),
        ("Guten Tag", "de", "en", "Good day"),
        ("Bonjour", "fr", "en", "Hello"),
        ("Hello", "en", "fr", "Bonjour"),
        ("Hola mundo", "es", "en", "Hello world"),
        ("Ciao", "it", "en", "Hello"),
    ]

    for text, src, tgt, expected_contains in test_cases:
        print_test(f"{src} -> {tgt}: '{text}'")
        success, response = translate(text, src, tgt)

        if success:
            translation = response.get("translated", [""])[0]
            safe_print_translation(translation)
            if expected_contains.lower() in translation.lower():
                print_success(f"Contains expected text: '{expected_contains}'")
            else:
                print_warning(f"Expected to contain: '{expected_contains}'")
        else:
            print_fail(f"Translation failed: {response.get('error', 'Unknown error')}")

        time.sleep(0.5)

def test_fallback_pairs():
    """Test pairs that require fallback to mbart50/m2m100"""
    print_header("TEST SET 2: Automatic Fallback Pairs (Opus-MT -> mBART50/M2M100)")

    # Pairs that don't exist in opus-mt but should work with fallback
    test_cases = [
        ("Hello", "en", "bn", "Bengali"),  # Bengali - should fallback
        ("Hello", "en", "ur", "Urdu"),   # Urdu - should fallback
        ("Hello", "en", "ta", "Tamil"),  # Tamil - might use pivot or fallback
    ]

    for text, src, tgt, expected_script in test_cases:
        print_test(f"{src} -> {tgt}: '{text}' (expects fallback)")
        success, response = translate(text, src, tgt)

        if success:
            translation = response.get("translated", [""])[0]
            safe_print_translation(translation)

            # Check if response includes metadata showing fallback
            metadata = response.get("metadata", {})
            if metadata:
                model_family = metadata.get("model_family", "unknown")
                model_name = metadata.get("model_name", "unknown")
                print_info(f"Model family used: {model_family}")
                print_info(f"Model: {model_name}")

            pivot_path = response.get("pivot_path")
            if pivot_path:
                print_info(f"Pivot used: {pivot_path}")
        else:
            print_fail(f"Translation failed: {response.get('error', 'Unknown error')}")

        time.sleep(0.5)

def test_explicit_model_families():
    """Test each model family explicitly"""
    print_header("TEST SET 3: Explicit Model Family Selection")

    test_text = "Hello world"
    src = "en"
    tgt = "de"

    families = ["opus-mt", "mbart50", "m2m100"]

    for family in families:
        print_test(f"Using {family} for {src} -> {tgt}")
        success, response = translate(test_text, src, tgt, model_family=family)

        if success:
            translation = response.get("translated", [""])[0]
            safe_print_translation(translation)

            metadata = response.get("metadata", {})
            if metadata:
                actual_family = metadata.get("model_family", "unknown")
                model_name = metadata.get("model_name", "unknown")

                if actual_family == family:
                    print_success(f"Correct family used: {actual_family}")
                else:
                    print_warning(f"Expected {family}, got {actual_family}")

                print_info(f"Model: {model_name}")
        else:
            print_fail(f"Translation failed: {response.get('error', 'Unknown error')}")

        time.sleep(0.5)

def test_pivot_translation():
    """Test pivot translation scenarios"""
    print_header("TEST SET 4: Pivot Translation (Intelligent Pivot Selection)")

    # Pairs likely to use pivot (not direct opus-mt models)
    test_cases = [
        ("Hello", "en", "bn", "English -> Bengali (likely pivot)"),
        ("Hola", "es", "ja", "Spanish -> Japanese (likely pivot)"),
    ]

    for text, src, tgt, description in test_cases:
        print_test(f"{description}: '{text}'")
        success, response = translate(text, src, tgt)

        if success:
            translation = response.get("translated", [""])[0]
            safe_print_translation(translation)

            pivot_path = response.get("pivot_path")
            if pivot_path:
                print_info(f"Pivot path: {pivot_path}")
                print_success("Intelligent pivot selection worked!")
            else:
                print_info("Direct translation (no pivot needed)")
        else:
            print_fail(f"Translation failed: {response.get('error', 'Unknown error')}")

        time.sleep(0.5)

def test_cache_behavior():
    """Test cache behavior across multiple requests"""
    print_header("TEST SET 5: Cache Behavior (Instant Model Switching)")

    # Make the same request twice to test cache hit
    print_test("First request: en -> de (cache MISS expected)")
    success1, response1 = translate("Hello", "en", "de")
    if success1:
        safe_print_translation(response1.get('translated', [''])[0])

    time.sleep(0.5)

    print_test("Second request: en -> de (cache HIT expected)")
    success2, response2 = translate("World", "en", "de")
    if success2:
        safe_print_translation(response2.get('translated', [''])[0])
        print_info("Model should be loaded from cache (check server logs)")

    time.sleep(0.5)

    print_test("Different pair: fr -> en (cache MISS expected)")
    success3, response3 = translate("Bonjour", "fr", "en")
    if success3:
        safe_print_translation(response3.get('translated', [''])[0])

    time.sleep(0.5)

    # Check cache status
    cache_status = get_cache_status()
    if cache_status:
        print_info(f"Cache capacity: {cache_status.get('max_cached_models', 'unknown')}")
        cached_models = cache_status.get('cached_models', [])
        print_info(f"Currently cached: {len(cached_models)} models")
        if cached_models:
            print_info("Cached model keys:")
            for model in cached_models:
                print(f"  • {model}")

def test_multi_model_switching():
    """Test switching between multiple model families rapidly"""
    print_header("TEST SET 6: Rapid Model Family Switching")

    test_text = "Hello"
    pairs_and_families = [
        ("en", "de", "opus-mt"),
        ("en", "de", "mbart50"),
        ("en", "de", "m2m100"),
        ("en", "fr", "opus-mt"),
        ("en", "fr", "mbart50"),
        ("fr", "es", "opus-mt"),
        ("de", "fr", "mbart50"),
    ]

    for src, tgt, family in pairs_and_families:
        print_test(f"{src} -> {tgt} using {family}")
        success, response = translate(test_text, src, tgt, model_family=family)

        if success:
            translation = response.get("translated", [""])[0]
            try:
                print_success(f"Translation: '{translation}' [{family}]")
            except (UnicodeEncodeError, UnicodeDecodeError):
                print_success(f"Translation received [{family}]")
        else:
            print_fail(f"Failed: {response.get('error', 'Unknown error')}")

        time.sleep(0.3)

    # Final cache status
    cache_status = get_cache_status()
    if cache_status:
        cached_models = cache_status.get('cached_models', [])
        print_info(f"\nFinal cache status: {len(cached_models)} models cached")
        print_info("This demonstrates the LRU cache keeping multiple models loaded!")

def test_batch_translation():
    """Test batch translation with multiple texts"""
    print_header("TEST SET 7: Batch Translation")

    texts = [
        "Hello world",
        "How are you?",
        "This is a test",
        "Machine translation is amazing"
    ]

    print_test(f"Batch translating {len(texts)} texts: en -> de")

    payload = {
        "text": texts,
        "source_lang": "en",
        "target_lang": "de",
        "beam_size": 1,
        "perform_sentence_splitting": False
    }

    try:
        response = requests.post(
            f"{BASE_URL}/translate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            translations = result.get("translated", [])

            print_success(f"Received {len(translations)} translations")
            for i, (orig, trans) in enumerate(zip(texts, translations), 1):
                print(f"  {i}. '{orig}' -> '{trans}'")
        else:
            print_fail(f"Batch translation failed: HTTP {response.status_code}")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

def main():
    """Run all tests"""
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("="*80)
    print("  mostlylucid-nmt v3.1 Comprehensive API Test Suite")
    print("="*80)
    print(f"{Colors.ENDC}\n")

    print_info(f"Testing API at: {BASE_URL}")
    print_info("Ensure the service is running before starting tests\n")

    # Check if service is available
    try:
        response = requests.get(f"{BASE_URL}/healthz", timeout=5)
        if response.status_code == 200:
            print_success("Service is healthy and ready!\n")
        else:
            print_warning("Service responded but may not be healthy\n")
    except Exception as e:
        print_fail(f"Cannot connect to service: {e}")
        print_fail("Please start the service first: docker run -p 8000:8000 ...\n")
        return

    # Run all test sets
    try:
        test_basic_pairs()
        test_fallback_pairs()
        test_explicit_model_families()
        test_pivot_translation()
        test_cache_behavior()
        test_multi_model_switching()
        test_batch_translation()

        print_header("TEST SUITE COMPLETE")
        print_success("All test sets executed successfully!")
        print_info("Check server logs to see:")
        print_info("  - Download progress banners with sizes")
        print_info("  - Cache HIT/MISS indicators")
        print_info("  - Model family fallback decisions")
        print_info("  - Intelligent pivot selection")
        print_info("  - Device placement (CPU/GPU)")

    except KeyboardInterrupt:
        print_warning("\n\nTests interrupted by user")
    except Exception as e:
        print_fail(f"\n\nTest suite failed with error: {e}")

if __name__ == "__main__":
    main()
