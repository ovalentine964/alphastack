"""Tail Risk Management — CVaR, stress testing, and scenario replay.

Protects against extreme market moves that standard VaR models miss.
Survives first, profits second — the tail is where accounts blow up.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Historical crisis scenarios
# ---------------------------------------------------------------------------

class CrisisScenario(str, Enum):
    """Pre-defined historical crisis scenarios for replay testing."""
    GFC_2008 = "gfc_2008"           # Global Financial Crisis
    FLASH_CRASH_2010 = "flash_2010" # May 6 2010 Flash Crash
    CHF_UNPEG_2015 = "chf_2015"     # SNB removes EUR/CHF floor
    BREXIT_2016 = "brexit_2016"     # Brexit referendum
    COVID_2020 = "covid_2020"       # March 2020 pandemic crash
    LUNA_2022 = "luna_2022"         # Terra/LUNA collapse
    SVB_2023 = "svb_2023"           # Silicon Valley Bank failure


# Typical drawdowns per scenario by asset class (% moves)
CRISIS_SHOCKS: dict[CrisisScenario, dict[str, float]] = {
    CrisisScenario.GFC_2008: {
        "equity": -0.55,      # S&P 500 peak-to-trough
        "fx_major": -0.15,
        "fx_em": -0.30,
        "crypto": -0.80,
        "gold": 0.25,         # Flight to safety
        "bonds": 0.10,
    },
    CrisisScenario.FLASH_CRASH_2010: {
        "equity": -0.09,      # Intraday then recovery
        "fx_major": -0.03,
        "crypto": -0.05,
        "gold": 0.02,
    },
    CrisisScenario.CHF_UNPEG_2015: {
        "fx_major": -0.30,    # EUR/CHF collapsed ~30%
        "equity": -0.03,
        "crypto": -0.10,
    },
    CrisisScenario.BREXIT_2016: {
        "fx_major": -0.12,    # GBP flash crash
        "equity": -0.08,
        "crypto": -0.05,
        "gold": 0.08,
    },
    CrisisScenario.COVID_2020: {
        "equity": -0.34,      # S&P 500 ~34% drawdown
        "fx_major": -0.08,
        "fx_em": -0.25,
        "crypto": -0.50,
        "gold": -0.12,        # Liquidation phase
        "bonds": -0.05,
    },
    CrisisScenario.LUNA_2022: {
        "crypto": -0.99,      # LUNA/Terra → 0
        "crypto_alt": -0.80,
        "crypto_btc": -0.30,
        "equity": -0.05,
    },
    CrisisScenario.SVB_2023: {
        "equity": -0.08,
        "equity_bank": -0.25,
        "bonds": 0.05,
        "crypto": 0.10,       # BTC rallied on bank fears
        "gold": 0.08,
    },
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TailRiskLimit(BaseModel):
    """Configurable tail risk limits."""
    max_cvar_95: float = 5.0       # Max CVaR at 95% confidence (% of portfolio)
    max_cvar_99: float = 10.0      # Max CVaR at 99% confidence
    max_stress_loss: float = 25.0  # Max acceptable loss in worst stress scenario
    max_portfolio_leverage: float = 3.0
    alert_threshold_pct: float = 80.0  # Alert when using 80% of limit


class CVaRResult(BaseModel):
    """Conditional Value at Risk calculation result."""
    confidence: float = 0.95
    var: float = 0.0           # Value at Risk (% of portfolio)
    cvar: float = 0.0          # Conditional VaR (expected shortfall)
    observations: int = 0
    method: str = "historical"  # historical | parametric | cornish_fisher
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StressTestResult(BaseModel):
    """Result of a single stress test scenario."""
    scenario: str
    description: str = ""
    portfolio_loss_pct: float = 0.0
    position_losses: dict[str, float] = Field(default_factory=dict)
    breaches_limit: bool = False
    recovery_estimate_days: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReverseStressResult(BaseModel):
    """Result of a reverse stress test — what would it take to blow up?"""
    target_loss_pct: float = 0.0
    required_market_move: float = 0.0
    scenario_description: str = ""
    probability_estimate: str = "unknown"  # low | medium | high | extreme
    affected_positions: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TailRiskAlert(BaseModel):
    """Alert when tail risk limits are approached or breached."""
    alert_type: str  # cvar_warning | cvar_breach | stress_breach | reverse_stress_warning
    severity: str    # info | warning | critical
    message: str
    current_value: float = 0.0
    limit_value: float = 0.0
    utilization_pct: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Tail Risk Manager
# ---------------------------------------------------------------------------

class TailRiskManager:
    """Manages tail risk through CVaR monitoring, stress testing, and
    historical scenario replay.

    This is the last line of defense — it asks "what if everything goes
    wrong at once?" and enforces limits on the answer.
    """

    def __init__(
        self,
        limits: TailRiskLimit | None = None,
        portfolio_value: float = 1000.0,
    ) -> None:
        self._limits = limits or TailRiskLimit()
        self._portfolio_value = portfolio_value
        self._returns: list[float] = []
        self._max_history = 1000
        self._alerts: list[TailRiskAlert] = []

    # -- Properties ---------------------------------------------------------

    @property
    def limits(self) -> TailRiskLimit:
        return self._limits

    @property
    def alerts(self) -> list[TailRiskAlert]:
        return list(self._alerts)

    def update_portfolio_value(self, value: float) -> None:
        """Update the current portfolio value."""
        self._portfolio_value = value

    # -- CVaR Calculation ---------------------------------------------------

    def add_return(self, return_pct: float) -> None:
        """Add a return observation for CVaR calculation."""
        self._returns.append(return_pct)
        if len(self._returns) > self._max_history:
            self._returns = self._returns[-self._max_history:]

    def add_returns(self, returns: list[float]) -> None:
        """Bulk-add return observations."""
        self._returns.extend(returns)
        if len(self._returns) > self._max_history:
            self._returns = self._returns[-self._max_history:]

    def calculate_cvar(
        self,
        confidence: float = 0.95,
        method: str = "historical",
    ) -> CVaRResult:
        """Calculate Conditional Value at Risk (Expected Shortfall).

        Args:
            confidence: Confidence level (0.90, 0.95, 0.99).
            method: Calculation method — "historical", "parametric", or
                    "cornish_fisher".

        Returns:
            CVaRResult with VaR and CVaR values as percentages.
        """
        if len(self._returns) < 20:
            log.warning("cvar_insufficient_data", observations=len(self._returns))
            return CVaRResult(
                confidence=confidence, observations=len(self._returns), method=method
            )

        if method == "parametric":
            return self._cvar_parametric(confidence)
        elif method == "cornish_fisher":
            return self._cvar_cornish_fisher(confidence)
        else:
            return self._cvar_historical(confidence)

    def _cvar_historical(self, confidence: float) -> CVaRResult:
        """Historical simulation CVaR."""
        sorted_returns = sorted(self._returns)
        n = len(sorted_returns)
        var_index = max(0, int(n * (1 - confidence)) - 1)

        var = abs(sorted_returns[var_index])
        # CVaR = average of all returns below VaR threshold
        tail = sorted_returns[: var_index + 1]
        cvar = abs(sum(tail) / len(tail)) if tail else var

        return CVaRResult(
            confidence=confidence,
            var=var,
            cvar=cvar,
            observations=n,
            method="historical",
        )

    def _cvar_parametric(self, confidence: float) -> CVaRResult:
        """Parametric (normal distribution) CVaR."""
        n = len(self._returns)
        mean = sum(self._returns) / n
        variance = sum((r - mean) ** 2 for r in self._returns) / n
        std = math.sqrt(variance)

        # Z-scores for common confidence levels
        z_scores = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}
        z = z_scores.get(confidence, 1.645)

        var = abs(mean - z * std)
        # For normal distribution, CVaR = mean + std * phi(z) / (1-confidence)
        # where phi is the standard normal PDF at the z-quantile
        phi_z = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
        cvar = abs(mean - std * phi_z / (1 - confidence))

        return CVaRResult(
            confidence=confidence,
            var=var,
            cvar=cvar,
            observations=n,
            method="parametric",
        )

    def _cvar_cornish_fisher(self, confidence: float) -> CVaRResult:
        """Cornish-Fisher expansion CVaR — adjusts for skew and kurtosis."""
        n = len(self._returns)
        mean = sum(self._returns) / n
        m2 = sum((r - mean) ** 2 for r in self._returns) / n
        m3 = sum((r - mean) ** 3 for r in self._returns) / n
        m4 = sum((r - mean) ** 4 for r in self._returns) / n

        std = math.sqrt(m2)
        if std < 1e-10:
            return CVaRResult(confidence=confidence, observations=n, method="cornish_fisher")

        skew = m3 / (std ** 3)
        kurt = (m4 / (std ** 4)) - 3  # excess kurtosis

        z_scores = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}
        z = z_scores.get(confidence, 1.645)

        # Cornish-Fisher adjustment
        z_cf = (
            z
            + (z ** 2 - 1) * skew / 6
            + (z ** 3 - 3 * z) * kurt / 24
            - (2 * z ** 3 - 5 * z) * (skew ** 2) / 36
        )

        var = abs(mean - z_cf * std)
        # Use adjusted z for CVaR approximation
        phi_z = math.exp(-0.5 * z_cf * z_cf) / math.sqrt(2 * math.pi)
        cvar = abs(mean - std * phi_z / (1 - confidence))

        return CVaRResult(
            confidence=confidence,
            var=var,
            cvar=cvar,
            observations=n,
            method="cornish_fisher",
        )

    # -- Stress Testing -----------------------------------------------------

    def run_stress_test(
        self,
        scenario: CrisisScenario,
        positions: dict[str, dict[str, Any]] | None = None,
    ) -> StressTestResult:
        """Run a historical stress scenario against current portfolio.

        Args:
            scenario: Which historical crisis to replay.
            positions: Optional dict of {symbol: {size, price, asset_class}}.
                       If None, uses a notional portfolio.

        Returns:
            StressTestResult with projected losses.
        """
        shocks = CRISIS_SHOCKS.get(scenario, {})
        if not shocks:
            return StressTestResult(
                scenario=scenario.value,
                description=f"No shock data for {scenario.value}",
            )

        description = self._scenario_description(scenario)
        position_losses: dict[str, float] = {}
        total_loss = 0.0

        if positions:
            for symbol, pos in positions.items():
                asset_class = pos.get("asset_class", "equity")
                shock = shocks.get(asset_class, shocks.get("equity", -0.20))
                size = pos.get("size", 0)
                price = pos.get("price", 0)
                notional = size * price
                loss = notional * shock
                position_losses[symbol] = round(loss, 2)
                total_loss += loss
        else:
            # Notional portfolio: assume 100% equity exposure
            shock = shocks.get("equity", -0.20)
            total_loss = self._portfolio_value * shock
            position_losses["_notional_equity"] = round(total_loss, 2)

        loss_pct = (total_loss / self._portfolio_value * 100) if self._portfolio_value > 0 else 0
        breaches = abs(loss_pct) > self._limits.max_stress_loss

        result = StressTestResult(
            scenario=scenario.value,
            description=description,
            portfolio_loss_pct=round(loss_pct, 2),
            position_losses=position_losses,
            breaches_limit=breaches,
            recovery_estimate_days=self._estimate_recovery(abs(loss_pct)),
        )

        if breaches:
            alert = TailRiskAlert(
                alert_type="stress_breach",
                severity="critical",
                message=(
                    f"Stress scenario '{scenario.value}' projects {loss_pct:.1f}% loss "
                    f"(limit: {self._limits.max_stress_loss}%)"
                ),
                current_value=abs(loss_pct),
                limit_value=self._limits.max_stress_loss,
                utilization_pct=abs(loss_pct) / self._limits.max_stress_loss * 100,
            )
            self._alerts.append(alert)
            log.critical("stress_test_breach", scenario=scenario.value, loss_pct=loss_pct)

        return result

    def run_all_scenarios(
        self,
        positions: dict[str, dict[str, Any]] | None = None,
    ) -> list[StressTestResult]:
        """Run all predefined crisis scenarios and return results."""
        results = []
        for scenario in CrisisScenario:
            result = self.run_stress_test(scenario, positions)
            results.append(result)
        return results

    # -- Reverse Stress Testing ---------------------------------------------

    def reverse_stress_test(
        self,
        target_loss_pct: float = 50.0,
        asset_class: str = "equity",
    ) -> ReverseStressResult:
        """Determine what market move would cause a target loss.

        Asks: "What would it take to lose X% of the portfolio?"

        Args:
            target_loss_pct: Target loss as percentage of portfolio.
            asset_class: Which asset class to stress.

        Returns:
            ReverseStressResult describing the required market move.
        """
        if self._portfolio_value <= 0:
            return ReverseStressResult(
                target_loss_pct=target_loss_pct,
                scenario_description="No portfolio value to stress",
            )

        # Required move to hit target loss
        required_move = -target_loss_pct / 100

        # Estimate probability based on historical precedents
        prob = self._estimate_probability(abs(required_move), asset_class)

        # Find which scenarios come close
        affected = []
        for scenario, shocks in CRISIS_SHOCKS.items():
            shock = shocks.get(asset_class, 0)
            if abs(shock) >= abs(required_move) * 0.5:
                affected.append(scenario.value)

        return ReverseStressResult(
            target_loss_pct=target_loss_pct,
            required_market_move=round(required_move * 100, 1),
            scenario_description=(
                f"A {abs(required_move) * 100:.1f}% decline in {asset_class} "
                f"would cause a {target_loss_pct:.0f}% portfolio loss"
            ),
            probability_estimate=prob,
            affected_positions=affected,
        )

    def check_tail_risk_limits(self) -> list[TailRiskAlert]:
        """Check current CVaR and stress metrics against limits.

        Returns a list of alerts for any breaches or warnings.
        """
        new_alerts: list[TailRiskAlert] = []

        # Check CVaR at 95%
        cvar_95 = self.calculate_cvar(confidence=0.95)
        if cvar_95.observations >= 20:
            util_95 = cvar_95.cvar / self._limits.max_cvar_95 * 100
            if util_95 >= 100:
                alert = TailRiskAlert(
                    alert_type="cvar_breach",
                    severity="critical",
                    message=f"CVaR(95%) = {cvar_95.cvar:.2f}% exceeds limit {self._limits.max_cvar_95}%",
                    current_value=cvar_95.cvar,
                    limit_value=self._limits.max_cvar_95,
                    utilization_pct=util_95,
                )
                new_alerts.append(alert)
            elif util_95 >= self._limits.alert_threshold_pct:
                alert = TailRiskAlert(
                    alert_type="cvar_warning",
                    severity="warning",
                    message=f"CVaR(95%) = {cvar_95.cvar:.2f}% approaching limit {self._limits.max_cvar_95}%",
                    current_value=cvar_95.cvar,
                    limit_value=self._limits.max_cvar_95,
                    utilization_pct=util_95,
                )
                new_alerts.append(alert)

        # Check CVaR at 99%
        cvar_99 = self.calculate_cvar(confidence=0.99)
        if cvar_99.observations >= 20:
            util_99 = cvar_99.cvar / self._limits.max_cvar_99 * 100
            if util_99 >= 100:
                alert = TailRiskAlert(
                    alert_type="cvar_breach",
                    severity="critical",
                    message=f"CVaR(99%) = {cvar_99.cvar:.2f}% exceeds limit {self._limits.max_cvar_99}%",
                    current_value=cvar_99.cvar,
                    limit_value=self._limits.max_cvar_99,
                    utilization_pct=util_99,
                )
                new_alerts.append(alert)
            elif util_99 >= self._limits.alert_threshold_pct:
                alert = TailRiskAlert(
                    alert_type="cvar_warning",
                    severity="warning",
                    message=f"CVaR(99%) = {cvar_99.cvar:.2f}% approaching limit {self._limits.max_cvar_99}%",
                    current_value=cvar_99.cvar,
                    limit_value=self._limits.max_cvar_99,
                    utilization_pct=util_99,
                )
                new_alerts.append(alert)

        self._alerts.extend(new_alerts)

        for a in new_alerts:
            if a.severity == "critical":
                log.critical("tail_risk_alert", alert_type=a.alert_type, message=a.message)
            else:
                log.warning("tail_risk_alert", alert_type=a.alert_type, message=a.message)

        return new_alerts

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _scenario_description(scenario: CrisisScenario) -> str:
        """Human-readable description of a crisis scenario."""
        descriptions = {
            CrisisScenario.GFC_2008: (
                "2008 Global Financial Crisis: Lehman Brothers collapse, "
                "subprime mortgage contagion, S&P 500 fell ~55%"
            ),
            CrisisScenario.FLASH_CRASH_2010: (
                "May 6 2010 Flash Crash: Dow dropped 1000 points in minutes, "
                "high-frequency trading amplification"
            ),
            CrisisScenario.CHF_UNPEG_2015: (
                "Jan 15 2015 SNB EUR/CHF floor removal: Swiss franc appreciated "
                "~30% in minutes, multiple FX brokers insolvent"
            ),
            CrisisScenario.BREXIT_2016: (
                "Jun 23 2016 Brexit referendum: GBP/USD fell ~12%, global "
                "equity sell-off, flight to safe havens"
            ),
            CrisisScenario.COVID_2020: (
                "Mar 2020 COVID-19 pandemic: fastest 30% decline in history, "
                "oil went negative, unprecedented volatility"
            ),
            CrisisScenario.LUNA_2022: (
                "May 2022 Terra/LUNA collapse: algorithmic stablecoin death "
                "spiral, $40B+ wiped out, crypto contagion"
            ),
            CrisisScenario.SVB_2023: (
                "Mar 2023 Silicon Valley Bank failure: bank run contagion, "
                "USDC depeg, regional banking crisis"
            ),
        }
        return descriptions.get(scenario, f"Historical scenario: {scenario.value}")

    @staticmethod
    def _estimate_recovery(drawdown_pct: float) -> int:
        """Estimate recovery time in days based on drawdown magnitude."""
        # Rough historical recovery periods
        if drawdown_pct < 5:
            return 7
        elif drawdown_pct < 10:
            return 30
        elif drawdown_pct < 20:
            return 90
        elif drawdown_pct < 30:
            return 180
        elif drawdown_pct < 50:
            return 365
        else:
            return 730  # 2+ years for catastrophic losses

    @staticmethod
    def _estimate_probability(magnitude: float, asset_class: str) -> str:
        """Estimate probability of a given market move magnitude."""
        # Based on historical frequency of moves
        if asset_class == "crypto":
            thresholds = {"low": 0.70, "medium": 0.50, "high": 0.30}
        elif asset_class == "fx_major":
            thresholds = {"low": 0.30, "medium": 0.15, "high": 0.08}
        else:
            thresholds = {"low": 0.50, "medium": 0.30, "high": 0.15}

        if magnitude >= thresholds["high"]:
            return "extreme"
        elif magnitude >= thresholds["medium"]:
            return "high"
        elif magnitude >= thresholds["low"]:
            return "medium"
        return "low"

    # -- Status -------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return tail risk manager status."""
        cvar_95 = self.calculate_cvar(confidence=0.95)
        cvar_99 = self.calculate_cvar(confidence=0.99)

        return {
            "portfolio_value": self._portfolio_value,
            "observations": len(self._returns),
            "cvar_95": cvar_95.model_dump(),
            "cvar_99": cvar_99.model_dump(),
            "limits": self._limits.model_dump(),
            "active_alerts": len([a for a in self._alerts if a.severity == "critical"]),
            "total_alerts": len(self._alerts),
        }

    def clear_alerts(self) -> None:
        """Clear all stored alerts."""
        self._alerts.clear()
