"""Tests for configuration management."""

import pytest
import os
import json
import torch
from src.config import Config


class TestConfig:
    """Tests for Config class."""

    def test_supported_langs(self):
        """Test that supported languages are defined."""
        assert len(Config.SUPPORTED_LANGS) > 0
        assert "en" in Config.SUPPORTED_LANGS
        assert "de" in Config.SUPPORTED_LANGS

    def test_parse_model_args_empty(self):
        """Test parsing empty model args."""
        Config.EASYNMT_MODEL_ARGS_RAW = "{}"
        args = Config.parse_model_args()
        assert args == {}

    def test_parse_model_args_fp16(self):
        """Test parsing FP16 torch dtype."""
        Config.EASYNMT_MODEL_ARGS_RAW = '{"torch_dtype": "fp16"}'
        args = Config.parse_model_args()
        assert "torch_dtype" in args
        assert args["torch_dtype"] == torch.float16

    def test_parse_model_args_bf16(self):
        """Test parsing BF16 torch dtype."""
        Config.EASYNMT_MODEL_ARGS_RAW = '{"torch_dtype": "bf16"}'
        args = Config.parse_model_args()
        assert args["torch_dtype"] == torch.bfloat16

    def test_parse_model_args_fp32(self):
        """Test parsing FP32 torch dtype."""
        Config.EASYNMT_MODEL_ARGS_RAW = '{"torch_dtype": "fp32"}'
        args = Config.parse_model_args()
        assert args["torch_dtype"] == torch.float32

    def test_parse_model_args_allowed_keys(self):
        """Test that only allowed keys are parsed."""
        Config.EASYNMT_MODEL_ARGS_RAW = '{"revision": "main", "invalid_key": "value"}'
        args = Config.parse_model_args()
        assert "revision" in args
        assert "invalid_key" not in args

    def test_parse_model_args_invalid_json(self):
        """Test parsing invalid JSON returns empty dict."""
        Config.EASYNMT_MODEL_ARGS_RAW = "invalid json"
        args = Config.parse_model_args()
        assert args == {}

    def test_resolve_device_index_cpu(self):
        """Test resolving CPU device."""
        Config.DEVICE_ENV = "cpu"
        index = Config.resolve_device_index()
        assert index == -1

    def test_resolve_device_index_auto_no_cuda(self, monkeypatch):
        """Test resolving auto device when CUDA not available."""
        Config.DEVICE_ENV = "auto"
        monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
        index = Config.resolve_device_index()
        assert index == -1

    def test_get_max_inflight_cpu(self):
        """Test max inflight for CPU."""
        Config.MAX_WORKERS_BACKEND = 4
        Config.MAX_INFLIGHT_TRANSLATIONS_RAW = None
        inflight = Config.get_max_inflight_translations(device_index=-1)
        assert inflight == 4  # Should match workers

    def test_get_max_inflight_gpu(self):
        """Test max inflight for GPU."""
        Config.MAX_INFLIGHT_TRANSLATIONS_RAW = None
        inflight = Config.get_max_inflight_translations(device_index=0)
        assert inflight == 1  # Should default to 1 for GPU

    def test_get_max_inflight_explicit(self):
        """Test explicit max inflight setting."""
        Config.MAX_INFLIGHT_TRANSLATIONS_RAW = "10"
        inflight = Config.get_max_inflight_translations(device_index=0)
        assert inflight == 10
