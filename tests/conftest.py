"""Pytest configuration and fixtures."""

import pytest
import os
from unittest.mock import Mock, MagicMock
from concurrent.futures import ThreadPoolExecutor

# Set test environment variables before importing app code
os.environ["LOG_LEVEL"] = "ERROR"  # Suppress logs during tests
os.environ["USE_GPU"] = "false"  # Force CPU for tests
os.environ["ENABLE_QUEUE"] = "1"
os.environ["MAX_CACHED_MODELS"] = "2"  # Small cache for tests


@pytest.fixture
def mock_pipeline():
    """Mock transformers pipeline."""
    pipeline = MagicMock()
    pipeline.return_value = [{"translation_text": "Hallo Welt"}]
    return pipeline


@pytest.fixture
def mock_model_manager(monkeypatch, mock_pipeline):
    """Mock model manager to avoid loading real models."""
    from src.services import model_manager as mm

    original_get = mm.model_manager.get_pipeline

    def mock_get_pipeline(src: str, tgt: str):
        """Return mock pipeline without loading models."""
        return mock_pipeline

    monkeypatch.setattr(mm.model_manager, "get_pipeline", mock_get_pipeline)
    return mm.model_manager


@pytest.fixture
def backend_executor():
    """Create backend thread pool executor."""
    executor = ThreadPoolExecutor(max_workers=1)
    yield executor
    executor.shutdown(wait=False)


@pytest.fixture
def frontend_executor():
    """Create frontend thread pool executor."""
    executor = ThreadPoolExecutor(max_workers=1)
    yield executor
    executor.shutdown(wait=False)


@pytest.fixture
def translation_service(backend_executor):
    """Create translation service instance."""
    from src.services.translation_service import TranslationService
    return TranslationService(backend_executor)


@pytest.fixture
def app_client(mock_model_manager):
    """Create test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from src.app import app

    with TestClient(app) as client:
        yield client
