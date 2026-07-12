"""Quantum readiness assessment for AlphaStack.

Evaluates the current state of quantum computing, assesses impact on
trading algorithms, and defines a migration path from classical to quantum.

Based on research: 2026 hardware landscape (Google Willow 105 qubits,
IBM Condor 1,121+ qubits, D-Wave 5,000+ qubits).
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class QuantumStage(enum.Enum):
    """Maturity stages for quantum adoption."""

    CLASSICAL = "classical"  # Pure classical, no quantum awareness
    AWARE = "aware"  # Architecture ready, monitoring quantum landscape
    HYBRID = "hybrid"  # Using hybrid quantum-classical for specific sub-problems
    QUANTUM_NATIVE = "quantum_native"  # Full quantum advantage for production workloads


class QuantumProvider(enum.Enum):
    """Available quantum computing providers."""

    D_WAVE = "d_wave"  # Quantum annealing, 5,000+ qubits
    IBM_QUANTUM = "ibm_quantum"  # Condor 1,121+ qubits, Qiskit
    GOOGLE_WILLOW = "google_willow"  # 105 qubits, 13,000x speedup demo
    IONQ = "ionq"  # Trapped ion, 36 algorithmic qubits
    QUANTINUUM = "quantinuum"  # 56 qubits, highest fidelity
    AWS_BRAKET = "aws_braket"  # Multi-provider cloud access


@dataclass
class QuantumCapability:
    """Assessment of a quantum capability area."""

    name: str
    classical_performance: float  # 0-1 score for classical approach
    quantum_potential: float  # 0-1 score for quantum advantage potential
    timeline_years: float  # Estimated years until quantum advantage
    readiness_score: float = 0.0  # Computed: potential / (1 + timeline)
    risk_if_ignored: str = ""
    recommended_action: str = ""

    def __post_init__(self) -> None:
        self.readiness_score = self.quantum_potential / (1 + self.timeline_years)
        if not self.risk_if_ignored:
            self.risk_if_ignored = self._assess_risk()
        if not self.recommended_action:
            self.recommended_action = self._recommend_action()

    def _assess_risk(self) -> str:
        if self.readiness_score > 0.5:
            return "HIGH — Competitors may gain quantum advantage soon"
        if self.readiness_score > 0.2:
            return "MEDIUM — Quantum advantage emerging, monitor closely"
        return "LOW — Classical methods adequate for 5+ years"

    def _recommend_action(self) -> str:
        if self.timeline_years <= 1:
            return "Begin hybrid integration immediately"
        if self.timeline_years <= 3:
            return "Architecture preparation and pilot projects"
        if self.timeline_years <= 5:
            return "Monitor landscape, ensure cryptographic migration"
        return "Continue with classical, periodic review"


@dataclass
class HardwareStatus:
    """Current quantum hardware snapshot."""

    provider: QuantumProvider
    qubits: int
    connectivity: str  # "full", "nearest-neighbor", "pegasus"
    fidelity: float  # Gate fidelity, 0-1
    cloud_accessible: bool
    finance_focus: bool
    notes: str = ""


@dataclass
class QuantumReadinessReport:
    """Complete quantum readiness assessment."""

    assessed_at: str = ""
    current_stage: QuantumStage = QuantumStage.CLASSICAL
    target_stage: QuantumStage = QuantumStage.HYBRID
    capabilities: list[QuantumCapability] = field(default_factory=list)
    hardware: list[HardwareStatus] = field(default_factory=list)
    overall_score: float = 0.0
    migration_steps: list[str] = field(default_factory=list)
    immediate_actions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.assessed_at:
            self.assessed_at = datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# Quantum Readiness Assessor
# ---------------------------------------------------------------------------


class QuantumReadinessAssessor:
    """Assesses AlphaStack's quantum readiness across all dimensions.

    Evaluates:
    - Portfolio optimization (combinatorial explosion → quantum annealing)
    - Options pricing (Monte Carlo → quantum amplitude estimation)
    - Random number generation (PRNG → quantum true randomness)
    - Cryptographic security (RSA/ECDSA → post-quantum)
    - Market microstructure simulation
    """

    def __init__(self) -> None:
        self._capabilities = self._build_default_capabilities()
        self._hardware = self._build_hardware_snapshot()

    def assess(self) -> QuantumReadinessReport:
        """Run full quantum readiness assessment."""
        report = QuantumReadinessReport(
            current_stage=self._determine_stage(),
            target_stage=QuantumStage.HYBRID,
            capabilities=self._capabilities,
            hardware=self._hardware,
            overall_score=self._compute_overall_score(),
            migration_steps=self._build_migration_plan(),
            immediate_actions=self._identify_immediate_actions(),
        )
        logger.info(
            "Quantum readiness assessed: stage=%s, score=%.2f",
            report.current_stage.value,
            report.overall_score,
        )
        return report

    def get_quantum_advantage_timeline(self) -> dict[str, float]:
        """Return estimated years-to-quantum-advantage by problem domain."""
        return {cap.name: cap.timeline_years for cap in self._capabilities}

    def should_use_hybrid(self, problem_type: str) -> bool:
        """Determine if a problem should use hybrid quantum-classical approach.

        Parameters
        ----------
        problem_type : str
            One of: "portfolio_optimization", "option_pricing", "rng",
            "encryption", "simulation"
        """
        for cap in self._capabilities:
            if cap.name == problem_type:
                return cap.timeline_years <= 2 and cap.quantum_potential > 0.5
        return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _determine_stage(self) -> QuantumStage:
        """Determine current quantum adoption stage."""
        # AlphaStack is currently classical with quantum-aware architecture
        return QuantumStage.AWARE

    def _compute_overall_score(self) -> float:
        """Weighted average of capability readiness scores."""
        if not self._capabilities:
            return 0.0
        scores = [c.readiness_score for c in self._capabilities]
        return sum(scores) / len(scores)

    def _build_default_capabilities(self) -> list[QuantumCapability]:
        """Build the default capability assessment based on 2026 research."""
        return [
            QuantumCapability(
                name="portfolio_optimization",
                classical_performance=0.6,
                quantum_potential=0.85,
                timeline_years=1.5,
                risk_if_ignored="Competitors using hybrid QC for constrained portfolios may find better optima",
                recommended_action="Begin hybrid quantum-classical pilot with D-Wave Leap (free tier available)",
            ),
            QuantumCapability(
                name="option_pricing",
                classical_performance=0.7,
                quantum_potential=0.9,
                timeline_years=5.0,
                risk_if_ignored="Institutional players will price exotic derivatives faster with quantum Monte Carlo",
                recommended_action="Monitor IBM Quantinuum progress; ensure pricing engine is quantum-ready",
            ),
            QuantumCapability(
                name="rng",
                classical_performance=0.4,
                quantum_potential=0.95,
                timeline_years=0.5,
                risk_if_ignored="PRNG predictability undermines Monte Carlo simulation integrity",
                recommended_action="Evaluate QRNG hardware (Quantis, ID Quantique) for Monte Carlo seeding",
            ),
            QuantumCapability(
                name="encryption",
                classical_performance=0.8,
                quantum_potential=0.99,
                timeline_years=3.0,
                risk_if_ignored="Q-Day: quantum computers break RSA/ECDSA, exposing all encrypted trading data",
                recommended_action="Begin CRYSTALS-Kyber/Dilithium migration for API auth and wallet security NOW",
            ),
            QuantumCapability(
                name="simulation",
                classical_performance=0.5,
                quantum_potential=0.8,
                timeline_years=7.0,
                risk_if_ignored="Complex market microstructure models remain intractable classically",
                recommended_action="No action needed; classical agent-based models sufficient until 2033+",
            ),
            QuantumCapability(
                name="machine_learning",
                classical_performance=0.85,
                quantum_potential=0.5,
                timeline_years=8.0,
                risk_if_ignored="Quantum ML may find patterns classical ML misses in high-dimensional data",
                recommended_action="No action — dequantization research shows classical parity for most tasks",
            ),
        ]

    def _build_hardware_snapshot(self) -> list[HardwareStatus]:
        """Snapshot of 2026 quantum hardware landscape."""
        return [
            HardwareStatus(
                provider=QuantumProvider.GOOGLE_WILLOW,
                qubits=105,
                connectivity="nearest-neighbor",
                fidelity=0.995,
                cloud_accessible=False,
                finance_focus=False,
                notes="13,000x speedup vs classical supercomputer (Oct 2025 demo)",
            ),
            HardwareStatus(
                provider=QuantumProvider.IBM_QUANTUM,
                qubits=1121,
                connectivity="heavy-hex",
                fidelity=0.99,
                cloud_accessible=True,
                finance_focus=True,
                notes="Condor processor; Qiskit Finance module; quantum finance roadmap",
            ),
            HardwareStatus(
                provider=QuantumProvider.D_WAVE,
                qubits=5000,
                connectivity="pegasus",
                fidelity=0.95,
                cloud_accessible=True,
                finance_focus=True,
                notes="Advantage processor; hybrid quantum-classical portfolio optimization; AWS Braket access",
            ),
            HardwareStatus(
                provider=QuantumProvider.IONQ,
                qubits=36,
                connectivity="full",
                fidelity=0.996,
                cloud_accessible=True,
                finance_focus=False,
                notes="36 algorithmic qubits (trapped ion); AWS/Azure cloud access",
            ),
            HardwareStatus(
                provider=QuantumProvider.QUANTINUUM,
                qubits=56,
                connectivity="full",
                fidelity=0.998,
                cloud_accessible=True,
                finance_focus=True,
                notes="Highest fidelity; financial modeling partnerships",
            ),
        ]

    def _build_migration_plan(self) -> list[str]:
        """Build phased migration plan from classical to quantum."""
        return [
            "Phase 0 (NOW): Architecture audit — ensure all optimization problems "
            "are formulated as QUBO or Ising models for future quantum mapping",
            "Phase 1 (0-6 months): Evaluate D-Wave Leap free tier for portfolio "
            "selection with cardinality constraints; benchmark vs classical heuristics",
            "Phase 2 (6-12 months): Integrate QRNG for Monte Carlo seeding; "
            "begin CRYSTALS-Kyber migration for API authentication",
            "Phase 3 (12-24 months): Hybrid quantum-classical portfolio optimizer "
            "in production for constrained optimization sub-problems",
            "Phase 4 (24-36 months): Full post-quantum cryptography migration; "
            "deprecate RSA/ECDSA for all trading infrastructure",
            "Phase 5 (36-60 months): Quantum Monte Carlo for options pricing "
            "when error-corrected hardware becomes available",
        ]

    def _identify_immediate_actions(self) -> list[str]:
        """Identify actions that should be taken immediately."""
        actions = []
        for cap in self._capabilities:
            if cap.timeline_years <= 1:
                actions.append(f"[{cap.name}] {cap.recommended_action}")
        # Always include crypto migration as immediate
        if not any("encryption" in a.lower() or "crypto" in a.lower() for a in actions):
            actions.append("[encryption] Begin CRYSTALS-Kyber/Dilithium evaluation for post-quantum migration")
        return actions
