"""Pydantic models for request/response validation."""

from typing import Union, List, Dict
from pydantic import BaseModel, Field, validator


class TranslatePostBody(BaseModel):
    """Request body for POST /translate endpoint."""

    text: Union[str, List[str]] = Field(..., description="Text(s) to translate")
    target_lang: str = Field(..., description="Target language code")
    source_lang: str = Field(default="", description="Source language code (empty for auto-detect)")
    beam_size: int = Field(default=5, ge=1, description="Beam size for translation")
    perform_sentence_splitting: bool = Field(default=True, description="Whether to split sentences")

    @validator("text")
    def validate_text(cls, v):
        """Ensure text is not empty."""
        if isinstance(v, str):
            if not v.strip():
                raise ValueError("Text cannot be empty")
        elif isinstance(v, list):
            if not v:
                raise ValueError("Text list cannot be empty")
        return v

    @validator("target_lang", "source_lang")
    def validate_lang_code(cls, v):
        """Ensure language codes are lowercase."""
        return v.lower().strip() if v else ""


class TranslateResponse(BaseModel):
    """Response for GET /translate endpoint."""

    translations: List[str] = Field(..., description="Translated texts")


class TranslatePostResponse(BaseModel):
    """Response for POST /translate endpoint."""

    target_lang: str = Field(..., description="Target language code")
    source_lang: str = Field(..., description="Detected or provided source language code")
    translated: List[str] = Field(..., description="Translated texts")
    translation_time: float = Field(..., description="Translation duration in seconds")


class LanguageDetectionPostBody(BaseModel):
    """Request body for POST /language_detection endpoint."""

    text: Union[str, List[str], Dict[str, str]] = Field(..., description="Text(s) for language detection")


class LanguagePairsResponse(BaseModel):
    """Response for /lang_pairs endpoint."""

    language_pairs: List[List[str]] = Field(..., description="List of [source, target] language pairs")


class LanguagesResponse(BaseModel):
    """Response for /get_languages endpoint."""

    languages: List[str] = Field(..., description="List of language codes")


class LanguageDetectionResponse(BaseModel):
    """Response for GET /language_detection endpoint."""

    language: str = Field(..., description="Detected language code")


class ModelInfoResponse(BaseModel):
    """Response for /model_name endpoint."""

    model_name: str
    device: str
    easynmt_model: str
    batch_size: int
    max_text_len: Union[int, None]
    max_beam_size: Union[int, None]
    workers: Dict[str, int]
    input_sanitize: bool
    input_sanitize_min_alnum_ratio: float
    input_sanitize_min_chars: int
    undetermined_lang_code: str
    align_responses: bool
    sanitize_placeholder: str
    sentence_splitting_default: bool
    max_sentence_chars: int
    max_chunk_chars: int
    join_sentences_with: str
    pivot_fallback: bool
    pivot_lang: str
    logging: Dict[str, Union[str, bool, None]]


class CacheStatusResponse(BaseModel):
    """Response for /cache endpoint."""

    capacity: Union[int, None]
    size: int
    keys: List[str]
    device: str
    inflight: int
    queue_enabled: bool


class HealthResponse(BaseModel):
    """Response for /healthz endpoint."""

    status: str


class ReadinessResponse(BaseModel):
    """Response for /readyz endpoint."""

    status: str
    device: str
    queue_enabled: bool
    max_inflight: int
