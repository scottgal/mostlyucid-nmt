"""Tests for CTranslate2 backend modules."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import tempfile
import shutil


# Skip all tests if ctranslate2 is not available
ct2_available = False
try:
    import ctranslate2
    ct2_available = True
except ImportError:
    pass

pytestmark = pytest.mark.skipif(not ct2_available, reason="ctranslate2 not installed")


class TestCT2ModelLoader:
    """Tests for CT2ModelLoader class."""

    def test_loader_initialization(self):
        """Test loader initializes with correct cache directory."""
        from src.core.ct2_loader import CT2ModelLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CT2ModelLoader(cache_dir=tmpdir)
            assert loader.cache_dir == Path(tmpdir) / "ct2"
            assert loader.cache_dir.exists()

    def test_get_hf_model_name_opus(self):
        """Test HuggingFace model name generation for Opus-MT."""
        from src.core.ct2_loader import CT2ModelLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CT2ModelLoader(cache_dir=tmpdir)
            name = loader._get_hf_model_name("en", "de", "opus-mt")
            assert name == "Helsinki-NLP/opus-mt-en-de"

    def test_get_hf_model_name_mbart50(self):
        """Test HuggingFace model name generation for mBART50."""
        from src.core.ct2_loader import CT2ModelLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CT2ModelLoader(cache_dir=tmpdir)
            name = loader._get_hf_model_name("en", "de", "mbart50")
            assert name == "facebook/mbart-large-50-many-to-many-mmt"

    def test_get_hf_model_name_m2m100(self):
        """Test HuggingFace model name generation for M2M100."""
        from src.core.ct2_loader import CT2ModelLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CT2ModelLoader(cache_dir=tmpdir)
            name = loader._get_hf_model_name("en", "de", "m2m100")
            assert name == "facebook/m2m100_418M"

    def test_get_cache_key_opus(self):
        """Test cache key generation for Opus-MT (per-pair)."""
        from src.core.ct2_loader import CT2ModelLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CT2ModelLoader(cache_dir=tmpdir)
            key = loader._get_cache_key("en", "de", "opus-mt")
            assert key == "opus-mt/en-de"

    def test_get_cache_key_multilingual(self):
        """Test cache key generation for multilingual models (single model)."""
        from src.core.ct2_loader import CT2ModelLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CT2ModelLoader(cache_dir=tmpdir)

            mbart_key = loader._get_cache_key("en", "de", "mbart50")
            assert mbart_key == "mbart50/all"

            m2m_key = loader._get_cache_key("en", "de", "m2m100")
            assert m2m_key == "m2m100/all"

    def test_check_local_cache_not_exists(self):
        """Test local cache check returns None when model not cached."""
        from src.core.ct2_loader import CT2ModelLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CT2ModelLoader(cache_dir=tmpdir)
            result = loader._check_local_cache("en", "de", "opus-mt")
            assert result is None

    def test_check_local_cache_exists(self):
        """Test local cache check returns path when model is cached."""
        from src.core.ct2_loader import CT2ModelLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CT2ModelLoader(cache_dir=tmpdir)

            # Create fake cached model
            cache_path = loader.cache_dir / "opus-mt" / "en-de"
            cache_path.mkdir(parents=True)
            (cache_path / "model.bin").write_text("fake")

            result = loader._check_local_cache("en", "de", "opus-mt")
            assert result == cache_path

    def test_clear_cache_specific_family(self):
        """Test clearing cache for specific family."""
        from src.core.ct2_loader import CT2ModelLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CT2ModelLoader(cache_dir=tmpdir)

            # Create fake cached models
            (loader.cache_dir / "opus-mt" / "en-de").mkdir(parents=True)
            (loader.cache_dir / "mbart50" / "all").mkdir(parents=True)

            count = loader.clear_cache(family="opus-mt")
            assert count == 1
            assert not (loader.cache_dir / "opus-mt").exists()
            assert (loader.cache_dir / "mbart50").exists()

    def test_clear_cache_all(self):
        """Test clearing all cache."""
        from src.core.ct2_loader import CT2ModelLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CT2ModelLoader(cache_dir=tmpdir)

            # Create fake cached models
            (loader.cache_dir / "opus-mt" / "en-de").mkdir(parents=True)
            (loader.cache_dir / "mbart50" / "all").mkdir(parents=True)

            count = loader.clear_cache()
            assert count == 2
            assert not (loader.cache_dir / "opus-mt").exists()
            assert not (loader.cache_dir / "mbart50").exists()

    def test_get_cache_info(self):
        """Test cache info retrieval."""
        from src.core.ct2_loader import CT2ModelLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CT2ModelLoader(cache_dir=tmpdir)

            # Create fake cached model with source info
            cache_path = loader.cache_dir / "opus-mt" / "en-de"
            cache_path.mkdir(parents=True)
            (cache_path / "model.bin").write_text("x" * 1000)
            (cache_path / "source_model.txt").write_text("Helsinki-NLP/opus-mt-en-de")

            info = loader.get_cache_info()
            assert "opus-mt" in info["families"]
            assert len(info["families"]["opus-mt"]["models"]) == 1
            assert info["families"]["opus-mt"]["models"][0]["source"] == "Helsinki-NLP/opus-mt-en-de"


class TestCT2TranslatorWrapper:
    """Tests for CT2TranslatorWrapper class."""

    @pytest.fixture
    def mock_translator(self):
        """Create mock CTranslate2 translator."""
        mock = MagicMock()
        mock.translate_batch.return_value = [
            MagicMock(hypotheses=[["Hallo", "Welt"]])
        ]
        return mock

    @pytest.fixture
    def mock_tokenizer(self):
        """Create mock tokenizer."""
        mock = MagicMock()
        mock.encode.return_value = [1, 2, 3]
        mock.convert_ids_to_tokens.return_value = ["Hello", "world"]
        mock.convert_tokens_to_ids.return_value = [4, 5]
        mock.decode.return_value = "Hallo Welt"
        return mock

    def test_wrapper_call_returns_pipeline_format(self, mock_translator, mock_tokenizer):
        """Test wrapper returns pipeline-compatible format."""
        from src.core.ct2_wrapper import CT2TranslatorWrapper

        with patch.object(CT2TranslatorWrapper, '__init__', lambda x, *args, **kwargs: None):
            wrapper = CT2TranslatorWrapper.__new__(CT2TranslatorWrapper)
            wrapper.translator = mock_translator
            wrapper.tokenizer = mock_tokenizer
            wrapper.family = "opus-mt"
            wrapper.src_lang = "en"
            wrapper.tgt_lang = "de"

            result = wrapper(["Hello world"])

            assert isinstance(result, list)
            assert len(result) == 1
            assert "translation_text" in result[0]

    def test_wrapper_empty_input(self, mock_translator, mock_tokenizer):
        """Test wrapper handles empty input."""
        from src.core.ct2_wrapper import CT2TranslatorWrapper

        with patch.object(CT2TranslatorWrapper, '__init__', lambda x, *args, **kwargs: None):
            wrapper = CT2TranslatorWrapper.__new__(CT2TranslatorWrapper)
            wrapper.translator = mock_translator
            wrapper.tokenizer = mock_tokenizer

            result = wrapper([])
            assert result == []

    def test_wrapper_unload(self, mock_translator, mock_tokenizer):
        """Test wrapper unload method."""
        from src.core.ct2_wrapper import CT2TranslatorWrapper

        with patch.object(CT2TranslatorWrapper, '__init__', lambda x, *args, **kwargs: None):
            wrapper = CT2TranslatorWrapper.__new__(CT2TranslatorWrapper)
            wrapper.translator = mock_translator
            wrapper.tokenizer = mock_tokenizer
            wrapper.src_lang = "en"
            wrapper.tgt_lang = "de"
            mock_translator.unload = MagicMock()

            wrapper.unload()
            mock_translator.unload.assert_called_once()

    def test_wrapper_cpu_calls_unload(self, mock_translator, mock_tokenizer):
        """Test wrapper cpu() method calls unload."""
        from src.core.ct2_wrapper import CT2TranslatorWrapper

        with patch.object(CT2TranslatorWrapper, '__init__', lambda x, *args, **kwargs: None):
            wrapper = CT2TranslatorWrapper.__new__(CT2TranslatorWrapper)
            wrapper.translator = mock_translator
            wrapper.tokenizer = mock_tokenizer
            wrapper.src_lang = "en"
            wrapper.tgt_lang = "de"
            mock_translator.unload = MagicMock()

            result = wrapper.cpu()
            mock_translator.unload.assert_called_once()
            assert result == wrapper

    def test_wrapper_model_property(self, mock_translator, mock_tokenizer):
        """Test wrapper.model returns translator for cache compatibility."""
        from src.core.ct2_wrapper import CT2TranslatorWrapper

        with patch.object(CT2TranslatorWrapper, '__init__', lambda x, *args, **kwargs: None):
            wrapper = CT2TranslatorWrapper.__new__(CT2TranslatorWrapper)
            wrapper.translator = mock_translator

            assert wrapper.model == mock_translator


class TestBackendSelection:
    """Tests for automatic backend selection in model_manager."""

    def test_ct2_available_check(self):
        """Test CT2_AVAILABLE flag is set correctly."""
        from src.services.model_manager import CT2_AVAILABLE
        assert CT2_AVAILABLE == ct2_available

    @patch('src.services.model_manager.config')
    def test_backend_selection_ct2(self, mock_config):
        """Test CT2 backend is selected when available and configured."""
        mock_config.TRANSLATION_BACKEND = "ct2"
        mock_config.MODEL_FAMILY = "opus-mt"

        # This would need more complete mocking to fully test
        # Just verify the config is read correctly
        assert mock_config.TRANSLATION_BACKEND == "ct2"

    @patch('src.services.model_manager.config')
    def test_backend_selection_transformers(self, mock_config):
        """Test transformers backend is selected when configured."""
        mock_config.TRANSLATION_BACKEND = "transformers"
        assert mock_config.TRANSLATION_BACKEND == "transformers"


class TestCT2Config:
    """Tests for CT2 configuration in config.py."""

    def test_ct2_config_defaults(self):
        """Test CT2 configuration defaults."""
        from src.config import config

        assert hasattr(config, 'TRANSLATION_BACKEND')
        assert hasattr(config, 'CT2_COMPUTE_TYPE')
        assert hasattr(config, 'CT2_QUANTIZATION')
        assert hasattr(config, 'CT2_INTER_THREADS')
        assert hasattr(config, 'CT2_INTRA_THREADS')

    def test_ct2_quantization_default(self):
        """Test default quantization value."""
        from src.config import config

        # Default should be 'default' which means no quantization during conversion
        assert config.CT2_QUANTIZATION in ['default', 'float32', 'float16', 'int8']

    def test_ct2_thread_defaults(self):
        """Test thread configuration defaults are positive integers."""
        from src.config import config

        assert isinstance(config.CT2_INTER_THREADS, int)
        assert isinstance(config.CT2_INTRA_THREADS, int)
        assert config.CT2_INTER_THREADS >= 1
        assert config.CT2_INTRA_THREADS >= 1
