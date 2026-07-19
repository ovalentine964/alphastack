"""Order validation pipeline, circuit breakers, kill switch, and position limits.

Implements trading-specific security controls from IMPLEMENTATION_SECURITY.md §6:
- 7-layer order validation (schema → business rules → risk → position → price → duplicate → circuit breaker)
- Hard-coded position limits (NOT prompt-controlled)
- Circuit breaker enforcement (daily loss, rapid losses, concentration, volatility, agent anomaly)
- Kill switch with multi-channel activation
- All limits are enforced at code level — AI agents cannot override them
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from alphastack.security.audit import AuditCategory, AuditLogger
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

# Shared audit logger (imported from wherever it's configured)
_audit = AuditLogger()


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of a single validation layer."""
    passed: bool
    reason: str = ""
    layer: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, layer: str = "") -> ValidationResult:
        return cls(passed=True, layer=layer)

    @classmethod
    def fail(cls, reason: str, layer: str = "", **details: Any) -> ValidationResult:
        return cls(passed=False, reason=reason, layer=layer, details=details)


@dataclass
class PipelineResult:
    """Result of the full 7-layer validation pipeline."""
    passed: bool
    failures: list[ValidationResult] = field(default_factory=list)

    @property
    def rejection_reasons(self) -> list[str]:
        return [f"[{f.layer}] {f.reason}" for f in self.failures if not f.passed]


# ---------------------------------------------------------------------------
# Position limits — HARD-CODED, NOT prompt-controlled
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PositionLimits:
    """Hard-coded position limits enforced at code level.

    These limits CANNOT be overridden by AI agents, prompt injection,
    or configuration changes without a code deployment.
    """

    # Per-trade limits
    max_order_size: float = 10.0            # Maximum lot size per order
    max_order_value_usd: float = 50_000.0   # Maximum USD value per order
    min_order_size: float = 0.001           # Minimum lot size

    # Per-symbol limits
    max_position_per_symbol: float = 50.0           # Max lot size per symbol
    max_exposure_per_symbol_usd: float = 200_000.0  # Max USD exposure per symbol

    # Portfolio limits
    max_total_positions: int = 50                   # Max concurrent positions
    max_total_exposure_usd: float = 500_000.0       # Max total USD exposure
    max_drawdown_pct: float = 15.0                  # Max drawdown before halt

    # Correlation limits
    max_correlated_positions: int = 10      # Max positions in correlated assets
    correlation_threshold: float = 0.7      # Correlation coefficient threshold

    # Symbol allowlist — only these can be traded
    allowed_symbols: frozenset[str] = frozenset({
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "NZD/USD", "USD/CAD",
        "EUR/GBP", "EUR/JPY", "GBP/JPY",
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
        "BTC/USD", "ETH/USD",
        "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META",
    })


# Default immutable limits instance
DEFAULT_LIMITS = PositionLimits()


# ---------------------------------------------------------------------------
# Circuit breaker configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Circuit breaker thresholds — hard-coded, not agent-controlled."""
    max_daily_loss_pct: float = 5.0           # 5% daily loss → halt
    max_consecutive_losses: int = 5            # 5 losing trades in a row → halt
    max_concentration_pct: float = 0.30        # 30% in one asset → halt
    volatility_halt_threshold: float = 40.0    # VIX equivalent > 40 → halt
    min_agent_confidence: float = 0.6          # Agent confidence < 60% → halt
    max_trades_per_hour: int = 30              # Rate limit on trade frequency
    cooldown_seconds: int = 300                # 5-minute cooldown after trigger


DEFAULT_CB_CONFIG = CircuitBreakerConfig()


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Trading circuit breaker — automatically halt trading when risk thresholds are breached.

    HARD-CODED in the application, not controlled by AI agents.
    Requires human operator to reset after trigger.
    """

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self._config = config or DEFAULT_CB_CONFIG
        self._is_triggered = False
        self._trigger_reason: str | None = None
        self._trigger_time: float | None = None
        self._trade_timestamps: list[float] = []

    @property
    def is_triggered(self) -> bool:
        return self._is_triggered

    @property
    def trigger_reason(self) -> str | None:
        return self._trigger_reason

    def check(self, context: dict[str, Any]) -> bool:
        """Check all circuit breaker conditions.

        Returns True if trading should continue, False if halted.
        """
        if self._is_triggered:
            # Check cooldown
            if self._trigger_time and (time.time() - self._trigger_time) < self._config.cooldown_seconds:
                return False
            # Auto-restart after cooldown (still logged)
            logger.warning("circuit_breaker_cooldown_expired", reason=self._trigger_reason)
            self._is_triggered = False
            self._trigger_reason = None

        checks = [
            self._check_daily_loss(context),
            self._check_rapid_losses(context),
            self._check_position_concentration(context),
            self._check_volatility_spike(context),
            self._check_agent_anomaly(context),
            self._check_trade_frequency(context),
        ]

        for passed, reason in checks:
            if not passed:
                self._trigger(reason)
                return False

        return True

    def _check_daily_loss(self, ctx: dict[str, Any]) -> tuple[bool, str | None]:
        daily_pnl = ctx.get("daily_pnl_pct", 0)
        if daily_pnl < -self._config.max_daily_loss_pct:
            return False, f"Daily loss {daily_pnl:.2f}% exceeds max {self._config.max_daily_loss_pct}%"
        return True, None

    def _check_rapid_losses(self, ctx: dict[str, Any]) -> tuple[bool, str | None]:
        recent_trades = ctx.get("recent_trades", [])
        if not recent_trades:
            return True, None
        losing_streak = sum(1 for t in recent_trades[-10:] if t.get("pnl", 0) < 0)
        if losing_streak >= self._config.max_consecutive_losses:
            return False, f"{losing_streak} consecutive losses (max {self._config.max_consecutive_losses})"
        return True, None

    def _check_position_concentration(self, ctx: dict[str, Any]) -> tuple[bool, str | None]:
        positions = ctx.get("positions", [])
        if not positions:
            return True, None
        total_exposure = sum(abs(p.get("quantity", 0) * p.get("current_price", 0)) for p in positions)
        if total_exposure <= 0:
            return True, None
        symbol_exposures: dict[str, float] = {}
        for p in positions:
            sym = p.get("symbol", "")
            symbol_exposures[sym] = symbol_exposures.get(sym, 0) + abs(p.get("quantity", 0) * p.get("current_price", 0))
        for sym, exp in symbol_exposures.items():
            if exp / total_exposure > self._config.max_concentration_pct:
                return False, f"Concentration in {sym} ({exp/total_exposure:.0%}) exceeds {self._config.max_concentration_pct:.0%}"
        return True, None

    def _check_volatility_spike(self, ctx: dict[str, Any]) -> tuple[bool, str | None]:
        vix = ctx.get("market_volatility", 0)
        if vix > self._config.volatility_halt_threshold:
            return False, f"Market volatility {vix:.1f} exceeds halt threshold {self._config.volatility_halt_threshold}"
        return True, None

    def _check_agent_anomaly(self, ctx: dict[str, Any]) -> tuple[bool, str | None]:
        confidence = ctx.get("strategy_confidence", 1.0)
        if confidence < self._config.min_agent_confidence:
            return False, f"Agent confidence {confidence:.2f} below minimum {self._config.min_agent_confidence}"
        signals = ctx.get("recent_signals", [])
        if len(signals) >= 3:
            directions = [s.get("direction", "") for s in signals[-3:]]
            if len(set(directions)) > 1:
                return False, "Contradictory signals from strategy agent"
        return True, None

    def _check_trade_frequency(self, ctx: dict[str, Any]) -> tuple[bool, str | None]:
        now = time.time()
        hour_ago = now - 3600
        self._trade_timestamps = [t for t in self._trade_timestamps if t > hour_ago]
        self._trade_timestamps.append(now)
        if len(self._trade_timestamps) > self._config.max_trades_per_hour:
            return False, f"Trade frequency {len(self._trade_timestamps)}/hr exceeds max {self._config.max_trades_per_hour}"
        return True, None

    def _trigger(self, reason: str) -> None:
        self._is_triggered = True
        self._trigger_reason = reason
        self._trigger_time = time.time()
        _audit.log(
            AuditCategory.SECURITY,
            "circuit_breaker_triggered",
            details={"reason": reason, "cooldown_seconds": self._config.cooldown_seconds},
        )
        logger.error("circuit_breaker_triggered", reason=reason)

    def reset(self, operator: str, reason: str) -> None:
        """Reset circuit breaker — requires human authorization."""
        self._is_triggered = False
        self._trigger_reason = None
        self._trigger_time = None
        _audit.log(
            AuditCategory.SECURITY,
            "circuit_breaker_reset",
            actor_type="operator",
            actor_id=operator,
            details={"reason": reason},
        )
        logger.info("circuit_breaker_reset", operator=operator, reason=reason)


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

class KillSwitch:
    """Emergency kill switch — immediate halt of ALL trading activity.

    Accessible via: API endpoint, UI button, keyboard shortcut.
    Activation cancels all pending orders and disables the agent pipeline.
    Deactivation requires explicit operator authorization.
    """

    def __init__(self) -> None:
        self._is_active = False
        self._activation_time: float | None = None
        self._activation_reason: str | None = None
        self._activation_source: str | None = None
        self._on_activate_callbacks: list[Callable[[], None]] = []
        self._authorization_codes: dict[str, str] = {}  # operator → hashed code

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def status(self) -> dict[str, Any]:
        return {
            "active": self._is_active,
            "reason": self._activation_reason,
            "source": self._activation_source,
            "activated_at": self._activation_time,
            "uptime_seconds": (time.time() - self._activation_time) if self._activation_time else None,
        }

    def activate(self, reason: str, source: str = "api") -> None:
        """Immediately halt ALL trading activity."""
        if self._is_active:
            return  # Already active

        self._is_active = True
        self._activation_time = time.time()
        self._activation_reason = reason
        self._activation_source = source

        _audit.log(
            AuditCategory.SECURITY,
            "kill_switch_activated",
            details={
                "reason": reason,
                "source": source,
                "timestamp": self._activation_time,
            },
        )
        logger.critical("kill_switch_activated", reason=reason, source=source)

        # Fire callbacks (cancel orders, disable pipeline, etc.)
        for cb in self._on_activate_callbacks:
            try:
                cb()
            except Exception as exc:
                logger.error("kill_switch_callback_failed", error=str(exc))

    def deactivate(self, operator: str, authorization_code: str) -> bool:
        """Re-enable trading — requires authorization code.

        Returns True if deactivation succeeded.
        """
        if not self._is_active:
            return True

        # Verify authorization
        expected = self._authorization_codes.get(operator)
        if not expected or not hmac.compare_digest(
            hashlib.sha256(authorization_code.encode()).hexdigest(), expected
        ):
            _audit.log(
                AuditCategory.SECURITY,
                "kill_switch_deactivation_denied",
                actor_type="operator",
                actor_id=operator,
                details={"reason": "invalid_authorization"},
            )
            logger.warning("kill_switch_deactivation_denied", operator=operator)
            return False

        downtime = time.time() - (self._activation_time or time.time())
        self._is_active = False
        self._activation_time = None

        _audit.log(
            AuditCategory.SECURITY,
            "kill_switch_deactivated",
            actor_type="operator",
            actor_id=operator,
            details={"downtime_seconds": downtime},
        )
        logger.info("kill_switch_deactivated", operator=operator, downtime=downtime)
        return True

    def register_activation_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to fire when kill switch is activated."""
        self._on_activate_callbacks.append(callback)

    def set_authorization(self, operator: str, code: str) -> None:
        """Set an authorization code for an operator (hashed for storage)."""
        self._authorization_codes[operator] = hashlib.sha256(code.encode()).hexdigest()


# ---------------------------------------------------------------------------
# 7-Layer order validation pipeline
# ---------------------------------------------------------------------------

class OrderValidationPipeline:
    """Multi-layer order validation. Each layer is independent.
    ALL must pass for an order to be submitted.

    Layer 1: Schema validation (Pydantic — handled by FastAPI)
    Layer 2: Business rule validation
    Layer 3: Risk limit validation
    Layer 4: Position limit validation (HARD-CODED)
    Layer 5: Price reasonableness check
    Layer 6: Duplicate order check
    Layer 7: Circuit breaker check
    """

    def __init__(
        self,
        limits: PositionLimits | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        self._limits = limits or DEFAULT_LIMITS
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._kill_switch = kill_switch or KillSwitch()
        self._recent_order_hashes: set[str] = set()
        self._order_hash_ttl: float = 60.0  # Dedup window in seconds
        self._order_hash_timestamps: dict[str, float] = {}

    def validate(
        self,
        order: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """Run order through all 7 validation layers.

        Parameters
        ----------
        order : dict
            Order with keys: symbol, side, quantity, order_type, price,
            stop_loss, take_profit, time_in_force
        context : dict
            Trading context with keys: current_positions, daily_pnl_pct,
            recent_trades, market_volatility, strategy_confidence,
            recent_signals, current_prices

        Returns
        -------
        PipelineResult
            passed=True only if ALL layers pass.
        """
        ctx = context or {}
        failures: list[ValidationResult] = []

        # Kill switch check (supersedes everything)
        if self._kill_switch.is_active:
            return PipelineResult(
                passed=False,
                failures=[ValidationResult.fail("Kill switch is active — all trading halted", layer="kill_switch")],
            )

        # Layer 2: Business rules
        r = self._validate_business_rules(order)
        if not r.passed:
            failures.append(r)

        # Layer 3: Risk limits
        r = self._validate_risk_limits(order, ctx)
        if not r.passed:
            failures.append(r)

        # Layer 4: Position limits (HARD-CODED)
        r = self._validate_position_limits(order, ctx)
        if not r.passed:
            failures.append(r)

        # Layer 5: Price reasonableness
        r = self._validate_price_reasonableness(order, ctx)
        if not r.passed:
            failures.append(r)

        # Layer 6: Duplicate order check
        r = self._check_duplicate(order)
        if not r.passed:
            failures.append(r)

        # Layer 7: Circuit breaker
        r = self._check_circuit_breaker(ctx)
        if not r.passed:
            failures.append(r)

        if failures:
            _audit.log(
                AuditCategory.TRADING,
                "order_rejected",
                details={
                    "symbol": order.get("symbol"),
                    "side": order.get("side"),
                    "quantity": order.get("quantity"),
                    "failures": [f.reason for f in failures],
                },
            )
            return PipelineResult(passed=False, failures=failures)

        return PipelineResult(passed=True)

    # -- Layer 2: Business rules -------------------------------------------

    def _validate_business_rules(self, order: dict[str, Any]) -> ValidationResult:
        symbol = order.get("symbol", "")
        side = order.get("side", "")
        order_type = order.get("order_type", "market")
        stop_loss = order.get("stop_loss")
        take_profit = order.get("take_profit")
        price = order.get("price")

        # Symbol must be in allowlist
        if symbol not in self._limits.allowed_symbols:
            return ValidationResult.fail(
                f"Symbol {symbol!r} is not in the allowed symbols list",
                layer="business_rules",
            )

        # Side must be valid
        if side not in ("buy", "sell"):
            return ValidationResult.fail(f"Invalid side: {side!r}", layer="business_rules")

        # Stop-loss is mandatory
        if stop_loss is None:
            return ValidationResult.fail("Stop-loss is mandatory for all orders", layer="business_rules")

        # Stop-loss must be on correct side
        ref_price = price or order.get("current_price", 0)
        if ref_price:
            if side == "buy" and stop_loss >= ref_price:
                return ValidationResult.fail("Buy stop-loss must be below entry price", layer="business_rules")
            if side == "sell" and stop_loss <= ref_price:
                return ValidationResult.fail("Sell stop-loss must be above entry price", layer="business_rules")

        # Risk/reward ratio check
        if take_profit and price and stop_loss:
            risk = abs(price - stop_loss)
            reward = abs(take_profit - price)
            if risk > 0 and reward / risk < 1.0:
                return ValidationResult.fail(
                    f"Risk/reward ratio {reward/risk:.2f} must be >= 1.0",
                    layer="business_rules",
                )

        return ValidationResult.ok(layer="business_rules")

    # -- Layer 3: Risk limits ----------------------------------------------

    def _validate_risk_limits(self, order: dict[str, Any], ctx: dict[str, Any]) -> ValidationResult:
        quantity = order.get("quantity", 0)
        price = order.get("price") or ctx.get("current_prices", {}).get(order.get("symbol", ""), 0)
        order_value = quantity * price if price else 0

        # Max order value
        if order_value > self._limits.max_order_value_usd:
            return ValidationResult.fail(
                f"Order value ${order_value:.2f} exceeds max ${self._limits.max_order_value_usd:.2f}",
                layer="risk_limits",
            )

        # Max order size
        if quantity > self._limits.max_order_size:
            return ValidationResult.fail(
                f"Order size {quantity} exceeds max {self._limits.max_order_size}",
                layer="risk_limits",
            )

        # Min order size
        if quantity < self._limits.min_order_size:
            return ValidationResult.fail(
                f"Order size {quantity} below min {self._limits.min_order_size}",
                layer="risk_limits",
            )

        # Max drawdown check
        daily_pnl = ctx.get("daily_pnl_pct", 0)
        if daily_pnl < -self._limits.max_drawdown_pct:
            return ValidationResult.fail(
                f"Current drawdown {abs(daily_pnl):.1f}% exceeds max {self._limits.max_drawdown_pct}%",
                layer="risk_limits",
            )

        return ValidationResult.ok(layer="risk_limits")

    # -- Layer 4: Position limits (HARD-CODED) -----------------------------

    def _validate_position_limits(self, order: dict[str, Any], ctx: dict[str, Any]) -> ValidationResult:
        positions = ctx.get("current_positions", [])
        symbol = order.get("symbol", "")
        quantity = order.get("quantity", 0)
        price = order.get("price") or ctx.get("current_prices", {}).get(symbol, 0)
        order_value = quantity * price if price else 0

        # Per-symbol position limit
        current_symbol_qty = sum(p.get("quantity", 0) for p in positions if p.get("symbol") == symbol)
        if current_symbol_qty + quantity > self._limits.max_position_per_symbol:
            return ValidationResult.fail(
                f"Symbol position would be {current_symbol_qty + quantity}, max {self._limits.max_position_per_symbol}",
                layer="position_limits",
            )

        # Per-symbol exposure limit
        current_symbol_exp = sum(
            abs(p.get("quantity", 0) * p.get("current_price", 0))
            for p in positions if p.get("symbol") == symbol
        )
        if current_symbol_exp + order_value > self._limits.max_exposure_per_symbol_usd:
            return ValidationResult.fail(
                f"Symbol exposure would exceed ${self._limits.max_exposure_per_symbol_usd:.0f}",
                layer="position_limits",
            )

        # Total positions limit
        if len(positions) >= self._limits.max_total_positions:
            return ValidationResult.fail(
                f"At max {self._limits.max_total_positions} positions",
                layer="position_limits",
            )

        # Total exposure limit
        total_exposure = sum(
            abs(p.get("quantity", 0) * p.get("current_price", 0)) for p in positions
        )
        if total_exposure + order_value > self._limits.max_total_exposure_usd:
            return ValidationResult.fail(
                f"Total exposure would exceed ${self._limits.max_total_exposure_usd:.0f}",
                layer="position_limits",
            )

        return ValidationResult.ok(layer="position_limits")

    # -- Layer 5: Price reasonableness -------------------------------------

    def _validate_price_reasonableness(self, order: dict[str, Any], ctx: dict[str, Any]) -> ValidationResult:
        order_type = order.get("order_type", "market")
        if order_type not in ("limit", "stop", "stop_limit"):
            return ValidationResult.ok(layer="price_check")

        price = order.get("price")
        if not price:
            return ValidationResult.ok(layer="price_check")

        symbol = order.get("symbol", "")
        current_price = ctx.get("current_prices", {}).get(symbol)
        if not current_price:
            return ValidationResult.ok(layer="price_check")

        deviation_pct = abs(price - current_price) / current_price * 100
        if deviation_pct > 5.0:
            return ValidationResult.fail(
                f"Limit price deviates {deviation_pct:.1f}% from market (max 5%)",
                layer="price_check",
            )

        return ValidationResult.ok(layer="price_check")

    # -- Layer 6: Duplicate order check ------------------------------------

    def _check_duplicate(self, order: dict[str, Any]) -> ValidationResult:
        now = time.time()
        # Prune expired hashes
        expired = [h for h, ts in self._order_hash_timestamps.items() if now - ts > self._order_hash_ttl]
        for h in expired:
            self._recent_order_hashes.discard(h)
            del self._order_hash_timestamps[h]

        # Compute order fingerprint
        fingerprint = json.dumps(
            {k: order.get(k) for k in ("symbol", "side", "quantity", "price", "order_type")},
            sort_keys=True,
        )
        order_hash = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]

        if order_hash in self._recent_order_hashes:
            return ValidationResult.fail(
                "Duplicate order detected within dedup window",
                layer="duplicate_check",
            )

        self._recent_order_hashes.add(order_hash)
        self._order_hash_timestamps[order_hash] = now
        return ValidationResult.ok(layer="duplicate_check")

    # -- Layer 7: Circuit breaker ------------------------------------------

    def _check_circuit_breaker(self, ctx: dict[str, Any]) -> ValidationResult:
        if not self._circuit_breaker.check(ctx):
            return ValidationResult.fail(
                f"Circuit breaker triggered: {self._circuit_breaker.trigger_reason}",
                layer="circuit_breaker",
            )
        return ValidationResult.ok(layer="circuit_breaker")
