"""Model discovery service for finding available translation models."""

import asyncio
import time
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
import httpx

from src.config import config
from src.core.logging import logger


class ModelDiscoveryService:
    """Service for discovering available translation models from Hugging Face."""

    def __init__(self):
        """Initialize model discovery service."""
        # Cache structure: {model_family: {language_pairs: [...], last_updated: timestamp}}
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl_seconds = 3600  # Cache for 1 hour
        self._hf_api_base = "https://huggingface.co/api/models"

    async def discover_opus_mt_pairs(self, force_refresh: bool = False) -> List[List[str]]:
        """Discover all available Opus-MT language pairs from Hugging Face.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of language pairs [[src1, tgt1], [src2, tgt2], ...]
        """
        cache_key = "opus-mt"

        # Check cache
        if not force_refresh and cache_key in self._cache:
            cached = self._cache[cache_key]
            age = time.time() - cached.get("last_updated", 0)
            if age < self._cache_ttl_seconds:
                logger.debug(f"Returning cached Opus-MT pairs (age: {age:.0f}s)")
                return cached["language_pairs"]

        logger.info("Fetching available Opus-MT models from Hugging Face...")
        pairs = await self._fetch_opus_mt_models()

        # Update cache
        self._cache[cache_key] = {
            "language_pairs": pairs,
            "last_updated": time.time()
        }

        logger.info(f"Discovered {len(pairs)} Opus-MT language pairs")
        return pairs

    async def _fetch_opus_mt_models(self) -> List[List[str]]:
        """Fetch all Opus-MT models from Hugging Face API.

        Returns:
            List of language pairs
        """
        pairs = set()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Query HuggingFace API for Helsinki-NLP models
                # We'll paginate through results
                url = f"{self._hf_api_base}"
                params = {
                    "author": "Helsinki-NLP",
                    "search": "opus-mt",
                    "limit": 1000,  # Max allowed per page
                    "full": "false"
                }

                response = await client.get(url, params=params)
                response.raise_for_status()
                models = response.json()

                # Parse model names to extract language pairs
                for model in models:
                    model_id = model.get("modelId", "")
                    if not model_id.startswith("Helsinki-NLP/opus-mt-"):
                        continue

                    # Extract language pair from model name
                    # Format: Helsinki-NLP/opus-mt-{src}-{tgt}
                    pair_part = model_id.replace("Helsinki-NLP/opus-mt-", "")

                    # Handle multi-language codes (e.g., opus-mt-en-de, opus-mt-en-ROMANCE)
                    # For now, we'll only include simple pairs
                    parts = pair_part.split("-")
                    if len(parts) == 2:
                        src, tgt = parts
                        # Skip group codes (all uppercase like ROMANCE, CELTIC, etc.)
                        if not src.isupper() and not tgt.isupper():
                            pairs.add((src, tgt))

        except Exception as e:
            logger.error(f"Failed to fetch Opus-MT models from HuggingFace: {e}")
            # Return empty list on error
            return []

        # Convert set to sorted list
        return sorted([[src, tgt] for src, tgt in pairs])

    async def discover_mbart50_pairs(self) -> List[List[str]]:
        """Get all available mBART50 language pairs.

        Returns:
            List of language pairs
        """
        # mBART50 is a single multilingual model supporting all-to-all translation
        # We can return the cartesian product of supported languages
        pairs = []
        for src in config.MBART50_LANGS:
            for tgt in config.MBART50_LANGS:
                if src != tgt:
                    pairs.append([src, tgt])
        return pairs

    async def discover_m2m100_pairs(self) -> List[List[str]]:
        """Get all available M2M100 language pairs.

        Returns:
            List of language pairs
        """
        # M2M100 is a single multilingual model supporting all-to-all translation
        pairs = []
        for src in config.M2M100_LANGS:
            for tgt in config.M2M100_LANGS:
                if src != tgt:
                    pairs.append([src, tgt])
        return pairs

    async def discover_all_pairs(self, force_refresh: bool = False) -> Dict[str, List[List[str]]]:
        """Discover all available language pairs for all model families.

        Args:
            force_refresh: If True, bypass cache for Opus-MT

        Returns:
            Dictionary with model family as key and list of pairs as value
        """
        # Fetch all in parallel
        opus_mt_task = asyncio.create_task(self.discover_opus_mt_pairs(force_refresh))
        mbart50_task = asyncio.create_task(self.discover_mbart50_pairs())
        m2m100_task = asyncio.create_task(self.discover_m2m100_pairs())

        opus_mt_pairs, mbart50_pairs, m2m100_pairs = await asyncio.gather(
            opus_mt_task, mbart50_task, m2m100_task
        )

        return {
            "opus-mt": opus_mt_pairs,
            "mbart50": mbart50_pairs,
            "m2m100": m2m100_pairs
        }

    def clear_cache(self) -> None:
        """Clear the discovery cache."""
        self._cache.clear()
        logger.info("Model discovery cache cleared")


# Singleton instance
model_discovery_service = ModelDiscoveryService()
