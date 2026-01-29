"""
Model catalog with metadata for speed, quality, and cost ratings.
Merges static catalog with live Ops-Center availability data.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ModelCatalog:
    """Manages model metadata and live availability."""

    def __init__(self, catalog_path: str = None):
        self._models: Dict[str, Dict[str, Any]] = {}
        catalog_path = catalog_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "model_catalog.json"
        )
        self._load(catalog_path)

    def _load(self, path: str):
        """Load model catalog from JSON."""
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    models = json.load(f)
                for m in models:
                    self._models[m["id"]] = m
                logger.info(f"Loaded {len(self._models)} models from catalog")
            except Exception as e:
                logger.error(f"Failed to load model catalog: {e}")

    def list_all(self) -> List[Dict[str, Any]]:
        """Return all models."""
        return list(self._models.values())

    def get(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get model by ID."""
        return self._models.get(model_id)

    def by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get models filtered by category (local, cloud-fast, cloud-quality)."""
        return [m for m in self._models.values() if m.get("category") == category]

    async def enrich_with_live_data(self, llm_client):
        """Fetch live models from Ops-Center and merge availability status."""
        try:
            live_models = await llm_client.get_available_models()
            if not live_models:
                return

            live_ids = set()
            for m in live_models:
                mid = m.get("id", "")
                if mid:
                    live_ids.add(mid)

            # Mark catalog models as available/unavailable
            for model_id, model in self._models.items():
                model["available"] = model_id in live_ids

            # Add Ops-Center models not in our catalog
            for live_model in live_models:
                mid = live_model.get("id", "")
                if mid and mid not in self._models:
                    provider = mid.split("/")[0] if "/" in mid else "unknown"
                    self._models[mid] = {
                        "id": mid,
                        "name": mid.split("/")[-1] if "/" in mid else mid,
                        "provider": provider,
                        "category": "cloud-quality",
                        "speed": 3,
                        "quality": 3,
                        "cost_per_million_tokens": 0,
                        "context_window": 0,
                        "supports_tools": False,
                        "supports_vision": False,
                        "recommended_for": [],
                        "description": f"Available via Ops-Center: {mid}",
                        "available": True,
                    }

            logger.info(f"Enriched catalog: {len(self._models)} models, {len(live_ids)} live")
        except Exception as e:
            logger.error(f"Failed to enrich model catalog: {e}")

    def count(self) -> int:
        """Total models in catalog."""
        return len(self._models)
