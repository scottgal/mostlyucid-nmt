"""
Live API validation tests.

These tests run against a LIVE running instance of the API.
Unlike the other tests, these don't use mocks - they test real behavior.

Usage:
    # Start the server first:
    docker run -p 8000:8000 dev:latest

    # Then run these tests:
    pytest tests/test_api_live.py -v

    # Or with custom base URL:
    BASE_URL=http://localhost:8001 pytest tests/test_api_live.py -v

    # Quick smoke test (just health checks):
    pytest tests/test_api_live.py -v -m smoke

    # Full validation:
    pytest tests/test_api_live.py -v -m "not slow"
"""

import os
import pytest
import httpx
from typing import Dict, Any

# Base URL for API (override with BASE_URL environment variable)
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def api_url():
    """Base URL for the API."""
    return BASE_URL


@pytest.fixture(scope="module")
def check_api_available(api_url):
    """Check if API is available before running tests."""
    try:
        response = httpx.get(f"{api_url}/healthz", timeout=5)
        if response.status_code != 200:
            pytest.skip(f"API not available at {api_url}")
    except httpx.RequestError:
        pytest.skip(f"API not reachable at {api_url}. Start the server first.")


@pytest.mark.smoke
class TestHealthEndpoints:
    """Test health and observability endpoints."""

    def test_healthz(self, api_url, check_api_available):
        """Test health check endpoint."""
        response = httpx.get(f"{api_url}/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_readyz(self, api_url, check_api_available):
        """Test readiness check endpoint."""
        response = httpx.get(f"{api_url}/readyz")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "device" in data

    def test_cache_status(self, api_url, check_api_available):
        """Test cache status endpoint."""
        response = httpx.get(f"{api_url}/cache")
        assert response.status_code == 200
        data = response.json()
        assert "size" in data
        assert "keys" in data

    def test_model_info(self, api_url, check_api_available):
        """Test model information endpoint."""
        response = httpx.get(f"{api_url}/model_name")
        assert response.status_code == 200
        data = response.json()
        assert "model_name" in data
        assert "device" in data


@pytest.mark.smoke
class TestBasicTranslation:
    """Test basic translation functionality."""

    def test_translate_get_simple(self, api_url, check_api_available):
        """Test simple GET translation."""
        response = httpx.get(
            f"{api_url}/translate",
            params={
                "text": "Hello world",
                "target_lang": "de",
                "source_lang": "en"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "translations" in data
        assert len(data["translations"]) > 0
        assert isinstance(data["translations"][0], str)

    def test_translate_post_simple(self, api_url, check_api_available):
        """Test simple POST translation."""
        response = httpx.post(
            f"{api_url}/translate",
            json={
                "text": ["Hello world"],
                "target_lang": "de",
                "source_lang": "en"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "translated" in data
        assert len(data["translated"]) == 1
        assert data["target_lang"] == "de"
        assert data["source_lang"] == "en"

    def test_translate_multiple_texts(self, api_url, check_api_available):
        """Test translating multiple texts."""
        response = httpx.post(
            f"{api_url}/translate",
            json={
                "text": ["Hello", "Goodbye", "Thank you"],
                "target_lang": "fr",
                "source_lang": "en"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["translated"]) == 3


class TestLanguageDetection:
    """Test language detection endpoints."""

    def test_language_detection_get(self, api_url, check_api_available):
        """Test GET language detection."""
        response = httpx.get(
            f"{api_url}/language_detection",
            params={"text": "Hello world"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "language" in data

    def test_language_detection_post_string(self, api_url, check_api_available):
        """Test POST language detection with string."""
        response = httpx.post(
            f"{api_url}/language_detection",
            json={"text": "Bonjour le monde"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "language" in data or "detected_langs" in data

    def test_language_detection_post_list(self, api_url, check_api_available):
        """Test POST language detection with list."""
        response = httpx.post(
            f"{api_url}/language_detection",
            json={"text": ["Hello", "Hola", "Bonjour"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "detected_langs" in data or "language" in data


class TestLanguagePairs:
    """Test language pair endpoints."""

    def test_lang_pairs(self, api_url, check_api_available):
        """Test language pairs endpoint."""
        response = httpx.get(f"{api_url}/lang_pairs")
        assert response.status_code == 200
        data = response.json()
        assert "language_pairs" in data
        assert len(data["language_pairs"]) > 0

    def test_get_languages(self, api_url, check_api_available):
        """Test get languages endpoint."""
        response = httpx.get(f"{api_url}/get_languages")
        assert response.status_code == 200
        data = response.json()
        assert "languages" in data
        assert len(data["languages"]) > 0


class TestDiscoveryEndpoints:
    """Test model discovery endpoints."""

    @pytest.mark.slow
    def test_discover_opus_mt(self, api_url, check_api_available):
        """Test Opus-MT discovery."""
        response = httpx.get(f"{api_url}/discover/opus-mt", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert "pairs" in data
        assert len(data["pairs"]) > 0

    def test_discover_mbart50(self, api_url, check_api_available):
        """Test mBART50 discovery."""
        response = httpx.get(f"{api_url}/discover/mbart50")
        assert response.status_code == 200
        data = response.json()
        assert "pairs" in data

    def test_discover_m2m100(self, api_url, check_api_available):
        """Test M2M100 discovery."""
        response = httpx.get(f"{api_url}/discover/m2m100")
        assert response.status_code == 200
        data = response.json()
        assert "pairs" in data


class TestAdvancedTranslation:
    """Test advanced translation features."""

    def test_translate_with_beam_size(self, api_url, check_api_available):
        """Test translation with custom beam size."""
        response = httpx.post(
            f"{api_url}/translate",
            json={
                "text": ["The quick brown fox"],
                "target_lang": "de",
                "source_lang": "en",
                "beam_size": 3
            }
        )
        assert response.status_code == 200

    def test_translate_auto_detect(self, api_url, check_api_available):
        """Test translation with auto language detection."""
        response = httpx.post(
            f"{api_url}/translate",
            json={
                "text": ["Bonjour"],
                "target_lang": "en"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "source_lang" in data

    def test_translate_empty_list(self, api_url, check_api_available):
        """Test translation with empty list."""
        response = httpx.post(
            f"{api_url}/translate",
            json={
                "text": [],
                "target_lang": "de",
                "source_lang": "en"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["translated"] == []


class TestErrorHandling:
    """Test error handling."""

    def test_missing_target_lang(self, api_url, check_api_available):
        """Test missing required parameter."""
        response = httpx.post(
            f"{api_url}/translate",
            json={"text": ["Hello"]}
        )
        assert response.status_code == 422  # Validation error

    def test_invalid_beam_size(self, api_url, check_api_available):
        """Test invalid beam size."""
        response = httpx.post(
            f"{api_url}/translate",
            json={
                "text": ["Hello"],
                "target_lang": "de",
                "source_lang": "en",
                "beam_size": 0
            }
        )
        assert response.status_code == 422  # Validation error


class TestDocumentation:
    """Test documentation endpoints."""

    def test_openapi_schema(self, api_url, check_api_available):
        """Test OpenAPI schema endpoint."""
        response = httpx.get(f"{api_url}/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_endpoint(self, api_url, check_api_available):
        """Test Swagger UI endpoint."""
        response = httpx.get(f"{api_url}/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestEasyNMTCompatibility:
    """Test EasyNMT compatibility endpoints."""

    def test_easynmt_translate_get(self, api_url, check_api_available):
        """Test EasyNMT GET translation."""
        response = httpx.get(
            f"{api_url}/easynmt/translate",
            params={
                "text": "Hello",
                "target_lang": "de",
                "source_lang": "en"
            }
        )
        # Should work with either 200 (implemented) or 404 (not implemented)
        assert response.status_code in [200, 404]

    def test_easynmt_available_languages(self, api_url, check_api_available):
        """Test EasyNMT available languages."""
        response = httpx.get(f"{api_url}/easynmt/available_languages")
        # Should work with either 200 (implemented) or 404 (not implemented)
        assert response.status_code in [200, 404]


@pytest.mark.slow
class TestModelDownloads:
    """Test automatic model downloads for unseen language pairs."""

    def test_download_new_model_pair(self, api_url, check_api_available):
        """Test that a new model pair is automatically downloaded on demand."""
        # Use a less common pair that might not be preloaded
        response = httpx.post(
            f"{api_url}/translate",
            json={
                "text": ["Hello"],
                "target_lang": "fi",  # Finnish
                "source_lang": "en",
                "beam_size": 1
            },
            timeout=120  # Allow time for model download
        )
        assert response.status_code == 200
        data = response.json()
        assert "translated" in data
        assert len(data["translated"]) == 1
        assert data["translated"][0] != ""  # Should have actual translation


@pytest.mark.slow
class TestPivotTranslations:
    """Test pivot translation fallback mechanism."""

    def test_pivot_translation_unsupported_pair(self, api_url, check_api_available):
        """Test that pivot translation works for unsupported language pairs."""
        # Test a pair that likely doesn't have a direct model (e.g., Finnish to Japanese)
        response = httpx.post(
            f"{api_url}/translate",
            json={
                "text": ["Hei maailma"],  # "Hello world" in Finnish
                "target_lang": "ja",  # Japanese
                "source_lang": "fi",  # Finnish
                "beam_size": 1
            },
            timeout=180  # Allow time for pivot translation (2 models)
        )
        assert response.status_code == 200
        data = response.json()
        assert "translated" in data
        assert len(data["translated"]) == 1

        # Check if pivot was used
        if "pivot_path" in data and data["pivot_path"]:
            # Pivot should be through English: fi->en->ja
            assert "en" in data["pivot_path"]
            assert data["pivot_path"].count("->") == 2  # Two translation steps

    def test_pivot_path_in_response(self, api_url, check_api_available):
        """Test that pivot_path is included when pivot is used."""
        response = httpx.post(
            f"{api_url}/translate",
            json={
                "text": ["Hola mundo"],  # Spanish
                "target_lang": "zh",  # Chinese
                "source_lang": "es",
                "beam_size": 1
            },
            timeout=180
        )
        assert response.status_code == 200
        data = response.json()

        # If pivot was used, pivot_path should be present
        if "pivot_path" in data and data["pivot_path"]:
            # Should show the translation path
            assert "->" in data["pivot_path"]
            assert data["pivot_path"].startswith("es")
            assert data["pivot_path"].endswith("zh")


if __name__ == "__main__":
    print(f"Testing API at: {BASE_URL}")
    print("\nRun with: pytest tests/test_api_live.py -v")
    print("Or for smoke tests only: pytest tests/test_api_live.py -v -m smoke")
