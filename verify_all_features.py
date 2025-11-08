#!/usr/bin/env python3
"""
Comprehensive Feature Verification Script for mostlylucid-nmt

This script tests ALL features of the translation service:
- Health and readiness endpoints
- Translation (GET and POST)
- Language detection
- Language pairs listing
- Model discovery (all families)
- Cache status
- Error handling
- Batch translation
- Sentence splitting
- Symbol masking

Usage:
    python verify_all_features.py [--host localhost] [--port 8000]

To build as standalone exe:
    pip install pyinstaller
    pyinstaller --onefile verify_all_features.py
"""

import argparse
import sys
import time
import requests
from typing import Dict, List, Tuple
from dataclasses import dataclass
import platform

# Simple ASCII icons for Windows compatibility
ICONS = {
    'search': '[TEST]',
    'check': '[PASS]',
    'cross': '[FAIL]',
    'boom': '[ERROR]',
    'party': '[SUCCESS]',
    'warning': '[WARN]',
}

# Use emojis on non-Windows platforms
if platform.system() != 'Windows':
    ICONS = {
        'search': '🔍',
        'check': '✅',
        'cross': '❌',
        'boom': '💥',
        'party': '🎉',
        'warning': '⚠️',
    }


@dataclass
class TestResult:
    """Result of a test."""
    name: str
    passed: bool
    message: str
    response_time: float = 0.0


class FeatureVerifier:
    """Verifies all features of the translation service."""

    def __init__(self, host: str = "localhost", port: int = 8000):
        self.base_url = f"http://{host}:{port}"
        self.results: List[TestResult] = []
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "mostlylucid-nmt-verifier/1.0"})

    def test(self, name: str, func):
        """Run a test and record the result."""
        print(f"\n{ICONS['search']} Testing: {name}...")
        start = time.time()
        try:
            func()
            elapsed = time.time() - start
            print(f"   {ICONS['check']} PASSED ({elapsed:.2f}s)")
            self.results.append(TestResult(name, True, "Success", elapsed))
        except AssertionError as e:
            elapsed = time.time() - start
            print(f"   {ICONS['cross']} FAILED: {e}")
            self.results.append(TestResult(name, False, str(e), elapsed))
        except Exception as e:
            elapsed = time.time() - start
            print(f"   {ICONS['boom']} ERROR: {e}")
            self.results.append(TestResult(name, False, f"Exception: {e}", elapsed))

    def test_health_endpoint(self):
        """Test /healthz endpoint."""
        resp = self.session.get(f"{self.base_url}/healthz", timeout=5)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["status"] == "ok", f"Expected status=ok, got {data.get('status')}"

    def test_readiness_endpoint(self):
        """Test /readyz endpoint."""
        resp = self.session.get(f"{self.base_url}/readyz", timeout=5)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "device" in data, "Missing device info"

    def test_model_name_endpoint(self):
        """Test /model_name endpoint."""
        resp = self.session.get(f"{self.base_url}/model_name", timeout=5)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "model_name" in data, "Missing model_name"

    def test_cache_status_endpoint(self):
        """Test /cache endpoint."""
        resp = self.session.get(f"{self.base_url}/cache", timeout=5)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "max_size" in data, "Missing cache max_size"
        assert "current_size" in data, "Missing cache current_size"

    def test_lang_pairs_endpoint(self):
        """Test /lang_pairs endpoint."""
        resp = self.session.get(f"{self.base_url}/lang_pairs", timeout=5)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list), "Expected list of language pairs"
        assert len(data) > 0, "No language pairs returned"

    def test_get_languages_endpoint(self):
        """Test /get_languages endpoint."""
        resp = self.session.get(f"{self.base_url}/get_languages", timeout=5)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list), "Expected list of languages"
        assert len(data) > 0, "No languages returned"

    def test_translate_get_single(self):
        """Test GET /translate with single text."""
        resp = self.session.get(
            f"{self.base_url}/translate",
            params={"target_lang": "de", "text": "Hello world"},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "translations" in data, "Missing translations"
        assert len(data["translations"]) > 0, "No translations returned"

    def test_translate_get_multiple(self):
        """Test GET /translate with multiple texts."""
        resp = self.session.get(
            f"{self.base_url}/translate",
            params={"target_lang": "de", "text": ["Hello", "World", "Test"]},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert len(data["translations"]) == 3, f"Expected 3 translations, got {len(data['translations'])}"

    def test_translate_get_empty_list(self):
        """Test GET /translate with no text (empty list default)."""
        resp = self.session.get(
            f"{self.base_url}/translate",
            params={"target_lang": "de"},
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["translations"] == [], "Expected empty translations list"

    def test_translate_post_single(self):
        """Test POST /translate with single text."""
        resp = self.session.post(
            f"{self.base_url}/translate",
            json={"text": ["Hello world"], "target_lang": "de"},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "translated" in data, "Missing translated field"
        assert len(data["translated"]) == 1, "Expected 1 translation"

    def test_translate_post_batch(self):
        """Test POST /translate with batch of texts."""
        texts = ["Hello", "Good morning", "How are you?", "Thank you", "Goodbye"]
        resp = self.session.post(
            f"{self.base_url}/translate",
            json={"text": texts, "target_lang": "fr"},
            timeout=60
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert len(data["translated"]) == len(texts), \
            f"Expected {len(texts)} translations, got {len(data['translated'])}"

    def test_translate_with_source_lang(self):
        """Test translation with explicit source language."""
        resp = self.session.post(
            f"{self.base_url}/translate",
            json={"text": ["Hello"], "source_lang": "en", "target_lang": "es"},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_translate_with_beam_size(self):
        """Test translation with custom beam size."""
        resp = self.session.post(
            f"{self.base_url}/translate",
            json={"text": ["Hello"], "target_lang": "de", "beam_size": 3},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_translate_with_sentence_splitting_off(self):
        """Test translation with sentence splitting disabled."""
        long_text = "This is a long text. It has multiple sentences. We want to test translation."
        resp = self.session.post(
            f"{self.base_url}/translate",
            json={"text": [long_text], "target_lang": "de", "perform_sentence_splitting": False},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_language_detection_string(self):
        """Test language detection with string input."""
        resp = self.session.post(
            f"{self.base_url}/language_detection",
            json={"text": "Hello world"},
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "en" in data["language"].lower(), f"Expected 'en', got {data['language']}"

    def test_language_detection_list(self):
        """Test language detection with list input."""
        resp = self.session.post(
            f"{self.base_url}/language_detection",
            json={"text": ["Hello", "Bonjour", "Hola"]},
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert isinstance(data["language"], list), "Expected list of languages"

    def test_language_detection_dict(self):
        """Test language detection with dict input."""
        resp = self.session.post(
            f"{self.base_url}/language_detection",
            json={"text": {"text1": "Hello", "text2": "Bonjour"}},
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert isinstance(data["language"], dict), "Expected dict of languages"

    def test_discover_all(self):
        """Test /discover/all endpoint."""
        resp = self.session.get(f"{self.base_url}/discover/all", timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "opus_mt" in data, "Missing opus_mt in discovery"

    def test_discover_opus_mt(self):
        """Test /discover/opus-mt endpoint."""
        resp = self.session.get(f"{self.base_url}/discover/opus-mt", timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "available_pairs" in data, "Missing available_pairs"
        assert len(data["available_pairs"]) > 0, "No opus-mt pairs found"

    def test_discover_mbart50(self):
        """Test /discover/mbart50 endpoint."""
        resp = self.session.get(f"{self.base_url}/discover/mbart50", timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "supported_languages" in data, "Missing supported_languages"

    def test_discover_m2m100(self):
        """Test /discover/m2m100 endpoint."""
        resp = self.session.get(f"{self.base_url}/discover/m2m100", timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "supported_languages" in data, "Missing supported_languages"

    def test_error_handling_invalid_lang(self):
        """Test error handling for invalid language."""
        resp = self.session.post(
            f"{self.base_url}/translate",
            json={"text": ["Hello"], "target_lang": "invalid_lang"},
            timeout=10
        )
        assert resp.status_code == 400, f"Expected 400 for invalid lang, got {resp.status_code}"

    def test_special_characters_translation(self):
        """Test translation with special characters and emojis."""
        text_with_specials = "Hello 😊! How are you? #awesome 🎉"
        resp = self.session.post(
            f"{self.base_url}/translate",
            json={"text": [text_with_specials], "target_lang": "de"},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        # Should preserve emojis
        translated = data["translated"][0]
        assert "😊" in translated or "🎉" in translated, "Emojis should be preserved"

    def run_all_tests(self):
        """Run all verification tests."""
        print("=" * 60)
        print("MOSTLYLUCID-NMT FEATURE VERIFICATION")
        print(f"Testing: {self.base_url}")
        print("=" * 60)

        # Core health checks
        self.test("Health Endpoint", self.test_health_endpoint)
        self.test("Readiness Endpoint", self.test_readiness_endpoint)
        self.test("Model Name Endpoint", self.test_model_name_endpoint)
        self.test("Cache Status Endpoint", self.test_cache_status_endpoint)

        # Language endpoints
        self.test("Language Pairs Listing", self.test_lang_pairs_endpoint)
        self.test("Get Languages", self.test_get_languages_endpoint)

        # Translation - GET
        self.test("Translate GET (Single)", self.test_translate_get_single)
        self.test("Translate GET (Multiple)", self.test_translate_get_multiple)
        self.test("Translate GET (Empty List)", self.test_translate_get_empty_list)

        # Translation - POST
        self.test("Translate POST (Single)", self.test_translate_post_single)
        self.test("Translate POST (Batch)", self.test_translate_post_batch)
        self.test("Translate with Source Lang", self.test_translate_with_source_lang)
        self.test("Translate with Beam Size", self.test_translate_with_beam_size)
        self.test("Translate with Sentence Splitting Off", self.test_translate_with_sentence_splitting_off)

        # Language Detection
        self.test("Language Detection (String)", self.test_language_detection_string)
        self.test("Language Detection (List)", self.test_language_detection_list)
        self.test("Language Detection (Dict)", self.test_language_detection_dict)

        # Model Discovery
        self.test("Discover All Models", self.test_discover_all)
        self.test("Discover Opus-MT", self.test_discover_opus_mt)
        self.test("Discover mBART50", self.test_discover_mbart50)
        self.test("Discover M2M100", self.test_discover_m2m100)

        # Error Handling
        self.test("Error Handling (Invalid Lang)", self.test_error_handling_invalid_lang)

        # Special Features
        self.test("Special Characters & Emojis", self.test_special_characters_translation)

        # Print summary
        self.print_summary()

        return all(r.passed for r in self.results)

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)

        print(f"\n{ICONS['check']} Passed: {passed}/{total}")
        print(f"{ICONS['cross']} Failed: {failed}/{total}")

        if failed > 0:
            print("\nFailed Tests:")
            for result in self.results:
                if not result.passed:
                    print(f"  {ICONS['cross']} {result.name}: {result.message}")

        total_time = sum(r.response_time for r in self.results)
        print(f"\nTotal Time: {total_time:.2f}s")

        if passed == total:
            print(f"\n{ICONS['party']} ALL FEATURES VERIFIED SUCCESSFULLY!")
        else:
            print(f"\n{ICONS['warning']} {failed} test(s) failed")


def main():
    parser = argparse.ArgumentParser(
        description="Verify all features of mostlylucid-nmt translation service"
    )
    parser.add_argument("--host", default="localhost", help="API host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="API port (default: 8000)")
    parser.add_argument("--url", help="Full base URL (overrides host/port)")

    args = parser.parse_args()

    if args.url:
        # Extract host and port from URL if provided
        from urllib.parse import urlparse
        parsed = urlparse(args.url)
        host = parsed.hostname or args.host
        port = parsed.port or args.port
    else:
        host = args.host
        port = args.port

    verifier = FeatureVerifier(host=host, port=port)

    try:
        success = verifier.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n\n{ICONS['warning']} Verification interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n{ICONS['boom']} Fatal error: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()
