"""Tests for auto-chunking functionality."""

import pytest
import os


@pytest.mark.unit
class TestAutoChunking:
    """Tests for automatic text chunking."""

    def test_auto_chunk_texts_disabled(self, translation_service, monkeypatch):
        """Test that chunking is skipped when disabled."""
        from src import config as cfg

        monkeypatch.setattr(cfg.config, "AUTO_CHUNK_ENABLED", False)

        texts = ["a" * 10000]  # Large text
        chunked, chunk_map = translation_service._auto_chunk_texts(texts)

        assert len(chunked) == 1
        assert chunk_map == [(0, 1)]
        assert chunked[0] == texts[0]

    def test_auto_chunk_texts_small_input(self, translation_service, monkeypatch):
        """Test that small texts are not chunked."""
        from src import config as cfg

        monkeypatch.setattr(cfg.config, "AUTO_CHUNK_ENABLED", True)
        monkeypatch.setattr(cfg.config, "AUTO_CHUNK_MAX_CHARS", 5000)

        texts = ["Hello world", "This is a test"]
        chunked, chunk_map = translation_service._auto_chunk_texts(texts)

        assert len(chunked) == 2
        assert chunk_map == [(0, 1), (1, 1)]
        assert chunked == texts

    def test_auto_chunk_texts_large_input(self, translation_service, monkeypatch):
        """Test that large texts are chunked correctly."""
        from src import config as cfg

        monkeypatch.setattr(cfg.config, "AUTO_CHUNK_ENABLED", True)
        monkeypatch.setattr(cfg.config, "AUTO_CHUNK_MAX_CHARS", 100)

        # Create text that needs 3 chunks
        large_text = "a" * 250
        texts = [large_text]
        chunked, chunk_map = translation_service._auto_chunk_texts(texts)

        # Should be split into 3 chunks (100 + 100 + 50)
        assert len(chunked) == 3
        assert chunk_map == [(0, 3)]
        assert chunked[0] == "a" * 100
        assert chunked[1] == "a" * 100
        assert chunked[2] == "a" * 50

    def test_auto_chunk_texts_mixed(self, translation_service, monkeypatch):
        """Test chunking with mix of small and large texts."""
        from src import config as cfg

        monkeypatch.setattr(cfg.config, "AUTO_CHUNK_ENABLED", True)
        monkeypatch.setattr(cfg.config, "AUTO_CHUNK_MAX_CHARS", 100)

        texts = ["small", "a" * 250, "medium"]
        chunked, chunk_map = translation_service._auto_chunk_texts(texts)

        # small (1 chunk), large (3 chunks), medium (1 chunk) = 5 total
        assert len(chunked) == 5
        assert chunk_map == [(0, 1), (1, 3), (2, 1)]

    def test_reassemble_chunks_single(self, translation_service):
        """Test reassembling single-chunk translations."""
        translations = ["Hello", "World"]
        chunk_map = [(0, 1), (1, 1)]

        result = translation_service._reassemble_chunks(translations, chunk_map)

        assert result == ["Hello", "World"]

    def test_reassemble_chunks_multi(self, translation_service, monkeypatch):
        """Test reassembling multi-chunk translations."""
        from src import config as cfg

        monkeypatch.setattr(cfg.config, "JOIN_SENTENCES_WITH", " ")

        # Simulate 1 single chunk, 1 text with 3 chunks, 1 single chunk
        translations = ["Part1", "Part2a", "Part2b", "Part2c", "Part3"]
        chunk_map = [(0, 1), (1, 3), (2, 1)]

        result = translation_service._reassemble_chunks(translations, chunk_map)

        assert len(result) == 3
        assert result[0] == "Part1"
        assert result[1] == "Part2a Part2b Part2c"
        assert result[2] == "Part3"


@pytest.mark.integration
class TestAutoChunkingAPI:
    """Integration tests for auto-chunking via API."""

    def test_translate_post_with_large_text(self, app_client, monkeypatch):
        """Test POST /translate with large text that triggers chunking."""
        from src import config as cfg

        # Enable chunking with small chunk size
        monkeypatch.setattr(cfg.config, "AUTO_CHUNK_ENABLED", True)
        monkeypatch.setattr(cfg.config, "AUTO_CHUNK_MAX_CHARS", 50)

        large_text = "This is a test sentence. " * 10  # ~250 chars
        response = app_client.post(
            "/translate",
            json={
                "text": large_text,
                "target_lang": "de",
                "source_lang": "en",
                "beam_size": 1
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "translated" in data
        assert isinstance(data["translated"], list)
        assert len(data["translated"]) == 1

    def test_translate_post_with_metadata(self, app_client, monkeypatch):
        """Test POST /translate with metadata enabled."""
        from src import config as cfg

        monkeypatch.setattr(cfg.config, "AUTO_CHUNK_ENABLED", True)
        monkeypatch.setattr(cfg.config, "AUTO_CHUNK_MAX_CHARS", 50)
        monkeypatch.setattr(cfg.config, "ENABLE_METADATA", False)  # Off by default

        response = app_client.post(
            "/translate",
            json={
                "text": "Hello world",
                "target_lang": "de",
                "source_lang": "en"
            },
            headers={"X-Enable-Metadata": "1"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "metadata" in data
        assert data["metadata"] is not None
        assert "model_name" in data["metadata"]
        assert "model_family" in data["metadata"]
        assert "chunks_processed" in data["metadata"]
        assert "auto_chunked" in data["metadata"]

    def test_translate_post_without_metadata(self, app_client):
        """Test POST /translate without metadata."""
        response = app_client.post(
            "/translate",
            json={
                "text": "Hello world",
                "target_lang": "de",
                "source_lang": "en"
            }
        )

        assert response.status_code == 200
        data = response.json()
        # Metadata should be None or not present when not requested
        assert data.get("metadata") is None
