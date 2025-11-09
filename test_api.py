"""Test the API endpoint with detailed logging."""

import os
import sys

# Enable detailed logging
os.environ["REQUEST_LOG"] = "1"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["MODEL_FAMILY"] = "opus-mt"

from fastapi.testclient import TestClient
from src.app import app

client = TestClient(app)

def test_translation_api():
    """Test the POST /translate endpoint."""
    print("=" * 60)
    print("Testing POST /translate API")
    print("=" * 60)

    payload = {
        "text": ["Hello world"],
        "target_lang": "de",
        "source_lang": "en",
        "beam_size": 1
    }

    print(f"\nRequest payload: {payload}")

    response = client.post("/translate", json=payload)

    print(f"\nResponse status: {response.status_code}")
    print(f"Response body: {response.json()}")

    if response.status_code == 200:
        data = response.json()
        translated = data.get("translated", [])
        if translated and translated[0]:
            print(f"\n[OK] Translation successful: '{translated[0]}'")
            return True
        else:
            print(f"\n[ERROR] Empty translation returned!")
            return False
    else:
        print(f"\n[ERROR] API returned error status {response.status_code}")
        return False

if __name__ == "__main__":
    try:
        success = test_translation_api()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
