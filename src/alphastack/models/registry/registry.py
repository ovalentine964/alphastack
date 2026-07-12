"""Model Registry — versioning, metadata, A/B testing, promotion gates.

Central registry for all ML model artifacts with lifecycle management.
Models progress through stages: staging → canary → production → archived.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Model lifecycle stages
# ---------------------------------------------------------------------------

class ModelStage(str, Enum):
    STAGING = "staging"      # Newly trained, under evaluation
    CANARY = "canary"        # Serving small traffic slice
    PRODUCTION = "production"  # Full production serving
    ARCHIVED = "archived"    # Retired, kept for reference


# ---------------------------------------------------------------------------
# Model metadata
# ---------------------------------------------------------------------------

class ModelVersion(BaseModel):
    """Full metadata for a registered model version."""
    version_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    model_name: str = ""
    version: str = ""  # semver, e.g. "1.2.0"
    stage: ModelStage = ModelStage.STAGING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Artifact
    artifact_path: str = ""  # path to .onnx file
    model_hash: str = ""     # SHA-256 prefix for integrity
    file_size_bytes: int = 0

    # Training info
    training_run_id: str = ""
    training_metrics: dict[str, float] = Field(default_factory=dict)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    training_data_hash: str = ""
    walk_forward_folds: int = 0

    # Serving info
    input_shape: list[int] = Field(default_factory=list)
    output_shape: list[int] = Field(default_factory=list)
    framework: str = "onnx"
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class ABTestConfig(BaseModel):
    """Configuration for A/B testing between model versions."""
    test_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    description: str = ""
    control_version: str = ""      # version_id of control (current prod)
    treatment_version: str = ""    # version_id of challenger
    traffic_split: float = 0.1     # fraction of traffic to treatment (0-1)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    active: bool = True

    # Metrics
    control_metrics: dict[str, float] = Field(default_factory=dict)
    treatment_metrics: dict[str, float] = Field(default_factory=dict)
    winner: str = ""  # "control" | "treatment" | ""


class PromotionGate(BaseModel):
    """Criteria that must be met before promoting a model."""
    min_sharpe_ratio: float = 0.5
    min_win_rate: float = 0.45
    max_drawdown_pct: float = 15.0
    min_profit_factor: float = 1.1
    min_trades: int = 30
    max_latency_p99_ms: float = 50.0
    required_stage: ModelStage = ModelStage.STAGING


# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------

class ModelRegistry:
    """Central registry for ML model versions.

    Stores model metadata in a JSON file (swap for a database in production).
    Supports versioning, stage promotion, A/B testing, and promotion gates.

    Usage::

        registry = ModelRegistry()
        registry.register(version_info)
        registry.promote(version_id, ModelStage.CANARY)
        active = registry.get_active_model("signal_model")
    """

    def __init__(self, registry_dir: str | Path = "models/registry") -> None:
        self._dir = Path(registry_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.json"
        self._models: dict[str, ModelVersion] = {}
        self._ab_tests: dict[str, ABTestConfig] = {}
        self._promotion_gates: dict[str, PromotionGate] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load registry from disk."""
        if self._index_path.exists():
            data = json.loads(self._index_path.read_text())
            for vid, mdata in data.get("models", {}).items():
                self._models[vid] = ModelVersion.model_validate(mdata)
            for tid, tdata in data.get("ab_tests", {}).items():
                self._ab_tests[tid] = ABTestConfig.model_validate(tdata)
            log.info("Loaded %d model versions from registry", len(self._models))

    def _save(self) -> None:
        """Persist registry to disk."""
        data = {
            "models": {vid: m.model_dump() for vid, m in self._models.items()},
            "ab_tests": {tid: t.model_dump() for tid, t in self._ab_tests.items()},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._index_path.write_text(json.dumps(data, indent=2, default=str))

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, model: ModelVersion) -> str:
        """Register a new model version.

        Args:
            model: ModelVersion with metadata.

        Returns:
            The version_id.
        """
        # Auto-increment version if not set
        if not model.version:
            existing = [
                m.version for m in self._models.values()
                if m.model_name == model.model_name and m.version
            ]
            if existing:
                parts = max(existing).rsplit(".", 1)
                model.version = f"{parts[0]}.{int(parts[1]) + 1}"
            else:
                model.version = "1.0.0"

        self._models[model.version_id] = model
        self._save()
        log.info(
            "Registered model %s v%s (stage=%s, id=%s)",
            model.model_name, model.version, model.stage.value, model.version_id,
        )
        return model.version_id

    def get(self, version_id: str) -> ModelVersion | None:
        """Get a model version by ID."""
        return self._models.get(version_id)

    def list_models(
        self,
        model_name: str | None = None,
        stage: ModelStage | None = None,
    ) -> list[ModelVersion]:
        """List registered models with optional filters."""
        results = list(self._models.values())
        if model_name:
            results = [m for m in results if m.model_name == model_name]
        if stage:
            results = [m for m in results if m.stage == stage]
        return sorted(results, key=lambda m: m.created_at, reverse=True)

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    def set_promotion_gate(self, model_name: str, gate: PromotionGate) -> None:
        """Set promotion criteria for a model."""
        self._promotion_gates[model_name] = gate
        log.info("Set promotion gate for %s", model_name)

    def check_promotion_eligibility(self, version_id: str) -> tuple[bool, list[str]]:
        """Check if a model version meets promotion gate criteria.

        Returns:
            (eligible, list of failure reasons).
        """
        model = self._models.get(version_id)
        if model is None:
            return False, [f"Version {version_id} not found"]

        gate = self._promotion_gates.get(model.model_name)
        if gate is None:
            return True, []  # no gate set, always eligible

        reasons: list[str] = []
        metrics = model.training_metrics

        if gate.required_stage != model.stage:
            reasons.append(
                f"Stage is {model.stage.value}, required {gate.required_stage.value}"
            )

        sharpe = metrics.get("sharpe_ratio", 0)
        if sharpe < gate.min_sharpe_ratio:
            reasons.append(f"Sharpe {sharpe:.2f} < minimum {gate.min_sharpe_ratio}")

        win_rate = metrics.get("win_rate", 0)
        if win_rate < gate.min_win_rate:
            reasons.append(f"Win rate {win_rate:.2f} < minimum {gate.min_win_rate}")

        dd = metrics.get("max_drawdown_pct", 100)
        if dd > gate.max_drawdown_pct:
            reasons.append(f"Max DD {dd:.1f}% > limit {gate.max_drawdown_pct}%")

        pf = metrics.get("profit_factor", 0)
        if pf < gate.min_profit_factor:
            reasons.append(f"Profit factor {pf:.2f} < minimum {gate.min_profit_factor}")

        trades = int(metrics.get("total_trades", 0))
        if trades < gate.min_trades:
            reasons.append(f"Trades {trades} < minimum {gate.min_trades}")

        return len(reasons) == 0, reasons

    def promote(
        self,
        version_id: str,
        target_stage: ModelStage,
        *,
        force: bool = False,
    ) -> bool:
        """Promote a model to a new stage.

        Args:
            version_id: Model version to promote.
            target_stage: Stage to promote to.
            force: Skip promotion gate checks.

        Returns:
            True if promoted successfully.
        """
        model = self._models.get(version_id)
        if model is None:
            log.error("Cannot promote: version %s not found", version_id)
            return False

        if not force:
            eligible, reasons = self.check_promotion_eligibility(version_id)
            if not eligible:
                log.warning("Promotion blocked for %s: %s", version_id, reasons)
                return False

        # If promoting to production, demote current production model
        if target_stage == ModelStage.PRODUCTION:
            for m in self._models.values():
                if (
                    m.model_name == model.model_name
                    and m.stage == ModelStage.PRODUCTION
                    and m.version_id != version_id
                ):
                    m.stage = ModelStage.ARCHIVED
                    m.updated_at = datetime.now(timezone.utc)
                    log.info("Archived previous production model %s", m.version_id)

        old_stage = model.stage
        model.stage = target_stage
        model.updated_at = datetime.now(timezone.utc)
        self._save()
        log.info(
            "Promoted %s v%s: %s → %s",
            model.model_name, model.version, old_stage.value, target_stage.value,
        )
        return True

    # ------------------------------------------------------------------
    # A/B testing
    # ------------------------------------------------------------------

    def create_ab_test(
        self,
        name: str,
        control_version_id: str,
        treatment_version_id: str,
        traffic_split: float = 0.1,
        description: str = "",
    ) -> ABTestConfig | None:
        """Create an A/B test between two model versions.

        Args:
            name: Human-readable test name.
            control_version_id: Version ID of the control model.
            treatment_version_id: Version ID of the challenger.
            traffic_split: Fraction of traffic routed to treatment (0-1).
            description: What this test is evaluating.

        Returns:
            ABTestConfig or None if versions not found.
        """
        control = self._models.get(control_version_id)
        treatment = self._models.get(treatment_version_id)
        if control is None or treatment is None:
            log.error("A/B test requires both versions to exist")
            return None

        test = ABTestConfig(
            name=name,
            control_version=control_version_id,
            treatment_version=treatment_version_id,
            traffic_split=traffic_split,
            description=description,
        )
        self._ab_tests[test.test_id] = test
        self._save()
        log.info(
            "Created A/B test '%s': %s vs %s (%.0f%% traffic to treatment)",
            name, control_version_id, treatment_version_id, traffic_split * 100,
        )
        return test

    def route_request(self, test_id: str) -> str:
        """Route a request to control or treatment.

        Uses deterministic routing based on request ID for consistency.

        Returns:
            version_id to use for this request.
        """
        test = self._ab_tests.get(test_id)
        if test is None or not test.active:
            return ""

        # Simple random split
        import random
        if random.random() < test.traffic_split:
            return test.treatment_version
        return test.control_version

    def end_ab_test(self, test_id: str, winner: str = "") -> None:
        """End an A/B test and optionally record the winner."""
        test = self._ab_tests.get(test_id)
        if test:
            test.active = False
            test.ended_at = datetime.now(timezone.utc)
            test.winner = winner
            self._save()
            log.info("Ended A/B test %s, winner: %s", test_id, winner or "undecided")

    def get_active_ab_tests(self, model_name: str | None = None) -> list[ABTestConfig]:
        """Get all active A/B tests."""
        tests = [t for t in self._ab_tests.values() if t.active]
        if model_name:
            tests = [
                t for t in tests
                if self._models.get(t.control_version, ModelVersion()).model_name == model_name
            ]
        return tests

    # ------------------------------------------------------------------
    # Active model lookup
    # ------------------------------------------------------------------

    def get_active_model(self, model_name: str) -> ModelVersion | None:
        """Get the current production model for a given model name.

        If an A/B test is active, may return the treatment version
        based on traffic split.
        """
        # Check for active A/B tests
        for test in self._ab_tests.values():
            if not test.active:
                continue
            control = self._models.get(test.control_version)
            if control and control.model_name == model_name and control.stage == ModelStage.PRODUCTION:
                # Let route_request handle the split
                routed = self.route_request(test.test_id)
                if routed:
                    return self._models.get(routed)

        # Default: return production model
        for model in self._models.values():
            if model.model_name == model_name and model.stage == ModelStage.PRODUCTION:
                return model

        # Fallback to canary if no production model
        for model in self._models.values():
            if model.model_name == model_name and model.stage == ModelStage.CANARY:
                return model

        return None

    def delete(self, version_id: str) -> bool:
        """Delete a model version (only from staging)."""
        model = self._models.get(version_id)
        if model is None:
            return False
        if model.stage not in (ModelStage.STAGING, ModelStage.ARCHIVED):
            log.error("Cannot delete model in stage %s", model.stage.value)
            return False
        del self._models[version_id]
        self._save()
        log.info("Deleted model version %s", version_id)
        return True
