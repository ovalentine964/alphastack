"""Strategy parameter loader — reads config/strategy_params.yaml.

Provides a singleton StrategyConfig that all pipeline steps can import.
Parameters are loaded once at import time and can be overridden per-regime.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _find_config_path() -> Path:
    """Locate strategy_params.yaml relative to the project root."""
    # Walk up from this file to find the config directory
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / "strategy_params.yaml"
        if candidate.exists():
            return candidate
    # Fallback: environment variable
    env_path = os.environ.get("ALPHASTACK_STRATEGY_PARAMS")
    if env_path:
        return Path(env_path)
    raise FileNotFoundError(
        "Cannot find config/strategy_params.yaml. "
        "Set ALPHASTACK_STRATEGY_PARAMS env var or place the file in the config/ directory."
    )


class StrategyConfig:
    """Loads and provides access to strategy parameters.

    Usage::

        from alphastack.strategy.config import strategy_params

        lookback = strategy_params.get("structure.swing_lookback", 5)
        weights = strategy_params.get("confluence.weights", {})
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _find_config_path()
        self._data: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        """(Re)load parameters from YAML."""
        with open(self._path) as f:
            self._data = yaml.safe_load(f) or {}

    @property
    def raw(self) -> dict[str, Any]:
        return self._data

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Retrieve a value using dotted notation: ``'structure.swing_lookback'``."""
        keys = dotted_key.split(".")
        node: Any = self._data
        for k in keys:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                return default
        return node

    def get_regime_override(
        self,
        dotted_key: str,
        regime: str,
        default: Any = None,
    ) -> Any:
        """Get a parameter, applying regime-specific override if present.

        For example, ``get_regime_override("rsi.overbought", "trending")``
        checks ``rsi.regimes.trending.overbought`` first, then falls back to
        ``rsi.overbought``.
        """
        # Try regime-specific path first: section.regimes.<regime>.<key>
        parts = dotted_key.split(".")
        if len(parts) == 2:
            section, key = parts
            regime_val = self.get(f"{section}.regimes.{regime}.{key}")
            if regime_val is not None:
                return regime_val
        return self.get(dotted_key, default)

    def weights_for_regime(self, regime: str | None = None) -> dict[str, float]:
        """Return confluence weights, optionally overridden for a regime."""
        base = self.get("confluence.weights", {})
        if regime:
            overrides = self.get(f"confluence.regimes.{regime}", {})
            if overrides:
                merged = dict(base)
                merged.update(overrides)
                return merged
        return base


# Module-level singleton
strategy_params = StrategyConfig()
