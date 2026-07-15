"""Model Loader — orchestrates registry ↔ inference engine wiring.

Provides a high-level interface for loading, versioning, and serving
ML models.  Integrates ModelRegistry (versioning) with InferenceEngine
(ONNX serving) and adds model caching and hot-reload support.

MiMo Integration:
    The loader supports registering Xiaomi MiMo models alongside
    traditional ONNX models.  MiMo models can be served via the
    same InferenceEngine interface by wrapping their inference in
    a compatible adapter.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np

from alphastack.models.registry.registry import ModelRegistry, ModelStage, ModelVersion
from alphastack.models.serving.inference import InferenceEngine, Prediction
from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Model adapter protocol (for MiMo and other non-ONNX models)
# ---------------------------------------------------------------------------

@runtime_checkable
class ModelAdapter(Protocol):
    """Protocol for custom model adapters (e.g., MiMo, PyTorch direct)."""

    async def predict(self, features: np.ndarray) -> np.ndarray:
        """Run inference and return predictions."""
        ...

    @property
    def input_shape(self) -> tuple[int, ...]:
        """Expected input shape (without batch dim)."""
        ...

    @property
    def output_shape(self) -> tuple[int, ...]:
        """Output shape (without batch dim)."""
        ...


class MiMoAdapter:
    """Adapter for Xiaomi MiMo model integration.

    Wraps MiMo API calls into the ModelAdapter protocol.
    Configure with API endpoint and credentials.

    Usage::

        adapter = MiMoAdapter(
            endpoint="https://api.mimo.xiaomi.com/v1/predict",
            api_key="...",
            model_id="mimo-signal-v1",
        )
        loader.register_adapter("mimo_signal", adapter)
        pred = await loader.predict("mimo_signal", features)
    """

    def __init__(
        self,
        endpoint: str = "",
        api_key: str = "",
        model_id: str = "",
        timeout: float = 5.0,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model_id = model_id
        self.timeout = timeout
        self._predict_count = 0

    async def predict(self, features: np.ndarray) -> np.ndarray:
        """Run inference via MiMo API.

        Currently returns a placeholder.  Wire to actual MiMo endpoint
        when API credentials are configured.
        """
        self._predict_count += 1

        if not self.endpoint:
            # Local fallback: simple heuristic
            return self._local_predict(features)

        # TODO: Wire to actual MiMo API
        # import httpx
        # async with httpx.AsyncClient(timeout=self.timeout) as client:
        #     resp = await client.post(
        #         self.endpoint,
        #         json={"features": features.tolist(), "model_id": self.model_id},
        #         headers={"Authorization": f"Bearer {self.api_key}"},
        #     )
        #     resp.raise_for_status()
        #     return np.array(resp.json()["predictions"])
        return self._local_predict(features)

    def _local_predict(self, features: np.ndarray) -> np.ndarray:
        """Local heuristic prediction (placeholder for MiMo)."""
        # Simple momentum-based signal
        if features.ndim == 1:
            features = features.reshape(1, -1)
        # Use last feature as momentum proxy
        momentum = features[:, -1] if features.shape[1] > 0 else np.zeros(features.shape[0])
        signal = np.tanh(momentum * 10)  # squash to [-1, 1]
        return signal.reshape(-1, 1)

    @property
    def input_shape(self) -> tuple[int, ...]:
        return (0,)  # dynamic

    @property
    def output_shape(self) -> tuple[int, ...]:
        return (1,)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "predict_count": self._predict_count,
            "endpoint": self.endpoint or "(local fallback)",
            "model_id": self.model_id,
        }


# ---------------------------------------------------------------------------
# Serving Manager
# ---------------------------------------------------------------------------

class ModelServingManager:
    """High-level model serving orchestrator.

    Combines ModelRegistry (versioning/promotion) with InferenceEngine
    (ONNX serving) and custom adapters (MiMo, etc.).

    Features:
    - Auto-loads production models from registry on startup
    - Hot-reload when models are promoted to production
    - Per-model latency tracking
    - A/B test routing through registry
    - Custom adapter support for non-ONNX models

    Usage::

        manager = ModelServingManager(registry_dir="models/registry")
        await manager.initialize()

        # Predict using the active production model
        pred = await manager.predict("signal_model", features)

        # Or use A/B test routing
        pred = await manager.predict_ab("signal_model", request_id="abc123", features=features)
    """

    def __init__(
        self,
        registry_dir: str | Path = "models/registry",
        inference_engine: InferenceEngine | None = None,
    ) -> None:
        self.registry = ModelRegistry(registry_dir=registry_dir)
        self.engine = inference_engine or InferenceEngine()
        self._adapters: dict[str, ModelAdapter] = {}
        self._model_cache: dict[str, dict[str, Any]] = {}  # model_name → cache metadata

    async def initialize(self) -> None:
        """Load all production and canary models from registry."""
        for model in self.registry.list_models():
            if model.stage in (ModelStage.PRODUCTION, ModelStage.CANARY):
                await self._load_model(model)
        log.info(
            "Serving manager initialized: %d models loaded",
            len(self.engine.loaded_models),
        )

    async def _load_model(self, version: ModelVersion) -> None:
        """Load a model version into the inference engine."""
        if not version.artifact_path:
            log.warning("No artifact path for %s v%s", version.model_name, version.version)
            return

        path = Path(version.artifact_path)
        if not path.exists():
            log.warning("Artifact not found: %s", path)
            return

        model_id = f"{version.model_name}:{version.version}"
        try:
            self.engine.load_model(model_id, str(path))
            self._model_cache[version.model_name] = {
                "active_version": version.version,
                "active_model_id": model_id,
                "stage": version.stage.value,
                "loaded_at": datetime.now(timezone.utc).isoformat(),
            }
            log.info("Loaded %s v%s (%s)", version.model_name, version.version, version.stage.value)
        except Exception:
            log.exception("Failed to load %s", model_id)

    # -- Adapter registration (for MiMo, etc.) -----------------------------

    def register_adapter(self, name: str, adapter: ModelAdapter) -> None:
        """Register a custom model adapter."""
        self._adapters[name] = adapter
        log.info("Registered adapter: %s", name)

    # -- Prediction ---------------------------------------------------------

    async def predict(
        self,
        model_name: str,
        features: np.ndarray,
        *,
        timeout_ms: float = 100.0,
    ) -> Prediction:
        """Predict using the active model for *model_name*.

        Checks adapters first, then ONNX engine.
        """
        # Check adapters
        if model_name in self._adapters:
            adapter = self._adapters[model_name]
            t0 = time.perf_counter()
            values = await adapter.predict(features)
            latency_ms = (time.perf_counter() - t0) * 1000
            return Prediction(
                values=values,
                latency_ms=round(latency_ms, 3),
                model_version=model_name,
            )

        # Check ONNX engine
        cache = self._model_cache.get(model_name)
        if cache:
            model_id = cache["active_model_id"]
            return await self.engine.predict(model_id, features, timeout_ms=timeout_ms)

        raise KeyError(
            f"Model '{model_name}' not found. "
            f"Available ONNX: {self.engine.loaded_models}, "
            f"Adapters: {list(self._adapters.keys())}"
        )

    async def predict_ab(
        self,
        model_name: str,
        request_id: str,
        features: np.ndarray,
    ) -> Prediction:
        """Predict with A/B test routing.

        If an active A/B test exists for *model_name*, routes to control
        or treatment based on traffic split.
        """
        # Check for active A/B tests
        ab_tests = self.registry.get_active_ab_tests(model_name)
        if ab_tests:
            test = ab_tests[0]
            routed_id = self.registry.route_request(test.test_id)
            if routed_id:
                version = self.registry.get(routed_id)
                if version:
                    model_id = f"{version.model_name}:{version.version}"
                    if model_id in [m for m in self.engine.loaded_models]:
                        return await self.engine.predict(model_id, features)

        # Fallback to normal predict
        return await self.predict(model_name, features)

    # -- Hot reload ---------------------------------------------------------

    async def reload_model(self, model_name: str) -> bool:
        """Reload the active model for *model_name* from registry."""
        version = self.registry.get_active_model(model_name)
        if version is None:
            log.warning("No active model for %s", model_name)
            return False

        # Unload old
        cache = self._model_cache.get(model_name)
        if cache:
            self.engine.unload_model(cache["active_model_id"])

        await self._load_model(version)
        return True

    # -- Stats --------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get serving stats for all models."""
        stats: dict[str, Any] = {
            "onnx_models": self.engine.get_all_stats(),
            "adapters": {
                name: getattr(adapter, "stats", {"type": type(adapter).__name__})
                for name, adapter in self._adapters.items()
            },
            "cache": dict(self._model_cache),
        }
        return stats
