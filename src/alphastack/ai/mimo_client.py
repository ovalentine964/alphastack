"""Backward-compatible shim — MiMoClient is now an alias for AlphaModel.

All new code should import from ``alphastack.ai.model_client`` instead.

    from alphastack.ai.model_client import AlphaModel, ReasoningEngine

Legacy imports still work:

    from alphastack.ai.mimo_client import MiMoClient, ReasoningEngine
"""

from __future__ import annotations

from alphastack.ai.model_client import (
    AlphaModel,
    ReasoningEngine,
    detect_provider,
    resolve_config,
    PROVIDERS,
)

# Backward-compatible alias
MiMoClient = AlphaModel

__all__ = [
    "MiMoClient",
    "AlphaModel",
    "ReasoningEngine",
    "detect_provider",
    "resolve_config",
    "PROVIDERS",
]
