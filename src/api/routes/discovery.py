"""Model discovery endpoints."""

from typing import Dict, List
from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.config import config
from src.services.model_discovery import model_discovery_service


router = APIRouter()


class ModelDiscoveryResponse(BaseModel):
    """Response model for model discovery."""
    model_family: str
    language_pairs: List[List[str]]
    pair_count: int


class AllModelsDiscoveryResponse(BaseModel):
    """Response model for all model families."""
    models: Dict[str, Dict]


@router.get(
    "/discover/opus-mt",
    response_model=ModelDiscoveryResponse,
    summary="Discover Opus-MT Pairs",
    description="Discovers all available Opus-MT language pairs from Hugging Face. Results are cached for 1 hour."
)
async def discover_opus_mt(
    force_refresh: bool = Query(
        default=False,
        description="Force refresh from Hugging Face API, bypassing cache"
    )
):
    """Discover all available Opus-MT translation pairs."""
    pairs = await model_discovery_service.discover_opus_mt_pairs(force_refresh=force_refresh)
    return ModelDiscoveryResponse(
        model_family="opus-mt",
        language_pairs=pairs,
        pair_count=len(pairs)
    )


@router.get(
    "/discover/mbart50",
    response_model=ModelDiscoveryResponse,
    summary="Discover mBART50 Pairs",
    description="Returns all available mBART50 language pairs (all-to-all for 50 languages)."
)
async def discover_mbart50():
    """Get all available mBART50 translation pairs."""
    pairs = await model_discovery_service.discover_mbart50_pairs()
    return ModelDiscoveryResponse(
        model_family="mbart50",
        language_pairs=pairs,
        pair_count=len(pairs)
    )


@router.get(
    "/discover/m2m100",
    response_model=ModelDiscoveryResponse,
    summary="Discover M2M100 Pairs",
    description="Returns all available M2M100 language pairs (all-to-all for 100 languages)."
)
async def discover_m2m100():
    """Get all available M2M100 translation pairs."""
    pairs = await model_discovery_service.discover_m2m100_pairs()
    return ModelDiscoveryResponse(
        model_family="m2m100",
        language_pairs=pairs,
        pair_count=len(pairs)
    )


@router.get(
    "/discover/all",
    response_model=AllModelsDiscoveryResponse,
    summary="Discover All Models",
    description="Discovers all available language pairs for all model families."
)
async def discover_all(
    force_refresh: bool = Query(
        default=False,
        description="Force refresh Opus-MT from Hugging Face API, bypassing cache"
    )
):
    """Discover all available translation pairs for all model families."""
    all_pairs = await model_discovery_service.discover_all_pairs(force_refresh=force_refresh)

    # Format response
    models = {}
    for family, pairs in all_pairs.items():
        models[family] = {
            "language_pairs": pairs,
            "pair_count": len(pairs)
        }

    return AllModelsDiscoveryResponse(models=models)


@router.post(
    "/discover/clear-cache",
    summary="Clear Discovery Cache",
    description="Clears the model discovery cache. Next discovery request will fetch fresh data."
)
async def clear_discovery_cache():
    """Clear the model discovery cache."""
    model_discovery_service.clear_cache()
    return {"status": "ok", "message": "Discovery cache cleared"}
