"""AI reasoning layer — model-agnostic integration for AlphaStack.

Primary interface (new code):

    from alphastack.ai import AlphaModel, ReasoningEngine

Legacy interface (still works):

    from alphastack.ai import MiMoClient, ReasoningEngine
"""

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
    "AlphaModel",
    "MiMoClient",
    "ReasoningEngine",
    "detect_provider",
    "resolve_config",
    "PROVIDERS",
]
