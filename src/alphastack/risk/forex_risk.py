"""Forex-Specific Risk Management — margin, swaps, sessions, gaps, spreads.

Consolidates all forex-unique risk concerns that don't exist in crypto:

- MarginMonitor: track margin level, alert at 150%, stop-out at 100%
- SwapTracker: track daily swap costs, alert on triple-Wednesday
- SessionGuard: restrict trading during low-liquidity hours
- WeekendGapProtection: auto-close positions before market close Friday
- SpreadMonitor: track and alert on abnormal spreads

These are the safety systems that keep a leveraged forex account alive.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Our safety limits (tighter than broker defaults)
OUR_MAX_LEVERAGE: float = 20.0          # Broker may offer 50x, we cap at 20x
MARGIN_ALERT_PCT: float = 150.0         # Alert when margin level drops to 150%
MARGIN_STOP_OUT_PCT: float = 100.0      # Force close at 100% margin level
MAX_MARGIN_UTILIZATION_PCT: float = 60.0 # Never use more than 60% of margin

# Weekend schedule (UTC)
MARKET_CLOSE_HOUR_UTC: int = 22         # Friday 22:00 UTC
MARKET_OPEN_HOUR_UTC: int = 22          # Sunday 22:00 UTC
WEEKEND_CLOSE_WARN_HOURS: int = 2       # Warn 2h before market close

# Swap triple day
TRIPLE_SWAP_WEEKDAY: int = 2            # Wednesday = 2 (Monday=0)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class MarginAlert(BaseModel):
    """Alert for margin level concerns."""
    alert_type: str  # margin_warning | margin_critical | stop_out_imminent
    severity: str    # info | warning | critical
    message: str
    margin_level_pct: float = 0.0
    used_margin: float = 0.0
    equity: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SwapAlert(BaseModel):
    """Alert for swap cost concerns."""
    alert_type: str  # triple_swap_warning | swap_budget_exceeded | swap_accumulation
    severity: str
    message: str
    daily_cost: float = 0.0
    total_accumulated: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionStatus(BaseModel):
    """Current session trading status."""
    session: str
    is_active: bool
    can_trade: bool
    liquidity_level: str  # high | medium | low | closed
    reason: str = ""


class GapWarning(BaseModel):
    """Warning about weekend gap risk."""
    symbol: str
    direction: str
    current_sl_pips: float
    recommended_action: str  # close | reduce | hold
    risk_message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SpreadAlert(BaseModel):
    """Alert for abnormal spread conditions."""
    symbol: str
    current_spread_pips: float
    average_spread_pips: float
    multiplier: float
    severity: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Margin Monitor
# ---------------------------------------------------------------------------

class MarginMonitor:
    """Track margin level and prevent margin calls.

    Margin level = (equity / used_margin) × 100%.
    - Alert at 150% (getting dangerous)
    - Stop-out at 100% (broker force-closes positions)
    - Our limit: never exceed 60% margin utilization

    Unlike crypto spot (where max loss = deposited amount),
    forex leverage means a 1% adverse move at 50x = 50% account loss.
    """

    def __init__(
        self,
        alert_level_pct: float = MARGIN_ALERT_PCT,
        stop_out_pct: float = MARGIN_STOP_OUT_PCT,
        max_utilization_pct: float = MAX_MARGIN_UTILIZATION_PCT,
        max_leverage: float = OUR_MAX_LEVERAGE,
    ) -> None:
        self._alert_level = alert_level_pct
        self._stop_out = stop_out_pct
        self._max_utilization = max_utilization_pct
        self._max_leverage = max_leverage
        self._alerts: list[MarginAlert] = []
        self._equity: float = 0.0
        self._used_margin: float = 0.0
        self._free_margin: float = 0.0

    # -- Properties ---------------------------------------------------------

    @property
    def margin_level_pct(self) -> float:
        """Current margin level as percentage."""
        if self._used_margin <= 0:
            return float("inf")
        return (self._equity / self._used_margin) * 100

    @property
    def margin_utilization_pct(self) -> float:
        """Percentage of available margin in use."""
        total = self._equity + self._free_margin
        if total <= 0:
            return 0.0
        return (self._used_margin / total) * 100

    @property
    def effective_leverage(self) -> float:
        """Current effective leverage across all positions."""
        if self._equity <= 0:
            return 0.0
        # Notional is inferred: used_margin * broker_leverage ≈ notional
        # We track effective leverage via equity
        return self._used_margin / self._equity if self._equity > 0 else 0.0

    # -- State updates ------------------------------------------------------

    def update(
        self,
        equity: float,
        used_margin: float,
        free_margin: float,
    ) -> list[MarginAlert]:
        """Update margin state and return any new alerts.

        Args:
            equity: Account equity (balance + unrealized P&L).
            used_margin: Margin currently in use by open positions.
            free_margin: Available margin for new positions.

        Returns:
            List of new margin alerts (if any).
        """
        self._equity = equity
        self._used_margin = used_margin
        self._free_margin = free_margin

        return self._check_alerts()

    # -- Pre-trade checks ---------------------------------------------------

    def check_new_position(
        self,
        margin_required: float,
        total_notional_after: float,
    ) -> tuple[bool, str]:
        """Check if a new position is safe to open.

        Args:
            margin_required: Margin needed for the new position.
            total_notional_after: Total notional if this position opens.

        Returns:
            (ok, reason) — ok=True if safe to proceed.
        """
        # Check margin utilization
        projected_used = self._used_margin + margin_required
        total_margin = self._equity + self._free_margin
        if total_margin > 0:
            projected_util = (projected_used / total_margin) * 100
            if projected_util > self._max_utilization:
                return False, (
                    f"Margin utilization would be {projected_util:.1f}% "
                    f"(limit: {self._max_utilization}%)"
                )

        # Check leverage cap
        if self._equity > 0:
            projected_leverage = total_notional_after / self._equity
            if projected_leverage > self._max_leverage:
                return False, (
                    f"Effective leverage would be {projected_leverage:.1f}x "
                    f"(our limit: {self._max_leverage}x, broker may allow more)"
                )

        # Check margin level after trade
        projected_equity = self._equity  # equity doesn't change on open
        projected_margin_level = (
            (projected_equity / projected_used) * 100
            if projected_used > 0 else float("inf")
        )
        if projected_margin_level < self._alert_level:
            return False, (
                f"Margin level would drop to {projected_margin_level:.1f}% "
                f"(alert threshold: {self._alert_level}%)"
            )

        return True, ""

    def check_leverage(
        self,
        total_notional: float,
        equity: float | None = None,
    ) -> tuple[bool, str]:
        """Check if effective leverage exceeds our cap.

        Args:
            total_notional: Total notional value of all positions.
            equity: Account equity (uses tracked value if None).

        Returns:
            (ok, reason) — ok=True if within limits.
        """
        eq = equity if equity is not None else self._equity
        if eq <= 0:
            return False, "Zero equity — cannot determine leverage"
        leverage = total_notional / eq
        if leverage > self._max_leverage:
            return False, (
                f"Effective leverage {leverage:.1f}x > our limit {self._max_leverage}x "
                f"(broker may offer higher — we are stricter)"
            )
        return True, ""

    # -- Internal -----------------------------------------------------------

    def _check_alerts(self) -> list[MarginAlert]:
        """Check current state against thresholds and emit alerts."""
        new_alerts: list[MarginAlert] = []
        level = self.margin_level_pct

        if level < self._stop_out:
            alert = MarginAlert(
                alert_type="stop_out_imminent",
                severity="critical",
                message=(
                    f"MARGIN LEVEL {level:.1f}% — STOP-OUT IMMINENT "
                    f"(threshold: {self._stop_out}%). "
                    f"Broker will force-close positions."
                ),
                margin_level_pct=level,
                used_margin=self._used_margin,
                equity=self._equity,
            )
            new_alerts.append(alert)
            log.critical("margin_stop_out_imminent", margin_level=level)

        elif level < self._alert_level:
            alert = MarginAlert(
                alert_type="margin_warning",
                severity="warning",
                message=(
                    f"Margin level {level:.1f}% approaching danger zone "
                    f"(alert at {self._alert_level}%, stop-out at {self._stop_out}%)"
                ),
                margin_level_pct=level,
                used_margin=self._used_margin,
                equity=self._equity,
            )
            new_alerts.append(alert)
            log.warning("margin_level_warning", margin_level=level)

        self._alerts.extend(new_alerts)
        return new_alerts

    def status(self) -> dict[str, Any]:
        """Return current margin status."""
        return {
            "equity": self._equity,
            "used_margin": self._used_margin,
            "free_margin": self._free_margin,
            "margin_level_pct": round(self.margin_level_pct, 2) if self.margin_level_pct != float("inf") else "N/A",
            "margin_utilization_pct": round(self.margin_utilization_pct, 2),
            "max_leverage": self._max_leverage,
            "alert_threshold": self._alert_level,
            "stop_out_threshold": self._stop_out,
            "alerts": len(self._alerts),
        }


# ---------------------------------------------------------------------------
# Swap Tracker
# ---------------------------------------------------------------------------

class SwapTracker:
    """Track daily swap/rollover costs on open positions.

    Swap fees accrue when positions are held past 5 PM EST (22:00 UTC).
    Wednesday is triple-swap day (charges for Wednesday, Saturday, Sunday).

    Swap costs are often overlooked — they can silently turn winning trades
    into losers over time.
    """

    def __init__(
        self,
        max_daily_swap_pct: float = 0.5,
        max_accumulated_swap_pct: float = 5.0,
        account_balance: float = 1000.0,
    ) -> None:
        self._max_daily_pct = max_daily_swap_pct
        self._max_accumulated_pct = max_accumulated_swap_pct
        self._balance = account_balance
        self._daily_swap: float = 0.0
        self._accumulated_swap: float = 0.0
        self._position_swaps: dict[str, float] = {}  # symbol -> accumulated cost
        self._alerts: list[SwapAlert] = []

    # -- Properties ---------------------------------------------------------

    @property
    def daily_swap_cost(self) -> float:
        return self._daily_swap

    @property
    def accumulated_swap_cost(self) -> float:
        return self._accumulated_swap

    @property
    def is_triple_swap_day(self) -> bool:
        """Check if today is Wednesday (triple swap day)."""
        return datetime.now(timezone.utc).weekday() == TRIPLE_SWAP_WEEKDAY

    # -- Tracking -----------------------------------------------------------

    def record_swap(
        self,
        symbol: str,
        swap_amount: float,
        direction: str = "",
    ) -> list[SwapAlert]:
        """Record a swap charge/credit for a position.

        Args:
            symbol: Instrument symbol.
            swap_amount: Swap cost (positive = cost, negative = credit).
            direction: Position direction (long/short).

        Returns:
            List of new swap alerts (if any).
        """
        multiplier = 3.0 if self.is_triple_swap_day else 1.0
        actual_cost = swap_amount * multiplier

        self._daily_swap += actual_cost
        self._accumulated_swap += actual_cost
        self._position_swaps[symbol] = self._position_swaps.get(symbol, 0.0) + actual_cost

        log.debug(
            "swap_recorded",
            symbol=symbol,
            direction=direction,
            swap_amount=actual_cost,
            triple_swap=multiplier > 1,
            daily_total=self._daily_swap,
            accumulated=self._accumulated_swap,
        )

        return self._check_alerts()

    def project_daily_swap(
        self,
        symbol: str,
        direction: str,
        lots: float,
        swap_long: float,
        swap_short: float,
        contract_size: float = 100_000.0,
    ) -> float:
        """Project daily swap cost for a position.

        Args:
            symbol: Instrument symbol.
            direction: "long" or "short".
            lots: Position size in lots.
            swap_long: Swap rate for long positions (per lot per day).
            swap_short: Swap rate for short positions (per lot per day).
            contract_size: Units per lot.

        Returns:
            Projected daily swap cost in account currency.
        """
        rate = swap_long if direction == "long" else swap_short
        base_cost = rate * lots
        # Triple swap on Wednesday
        if self.is_triple_swap_day:
            base_cost *= 3.0
        return base_cost

    def check_swap_budget(
        self,
        total_daily_swap: float | None = None,
        balance: float | None = None,
    ) -> tuple[bool, str]:
        """Check if swap costs are within budget.

        Args:
            total_daily_swap: Override daily swap (uses tracked value if None).
            balance: Override balance (uses tracked value if None).

        Returns:
            (ok, reason) — ok=True if within budget.
        """
        daily = total_daily_swap if total_daily_swap is not None else self._daily_swap
        bal = balance if balance is not None else self._balance

        if bal <= 0:
            return False, "Zero balance"

        daily_pct = (abs(daily) / bal) * 100
        if daily_pct > self._max_daily_pct:
            return False, (
                f"Daily swap cost {daily_pct:.2f}% exceeds {self._max_daily_pct}% budget"
            )

        accum_pct = (abs(self._accumulated_swap) / bal) * 100
        if accum_pct > self._max_accumulated_pct:
            return False, (
                f"Accumulated swap cost {accum_pct:.2f}% exceeds "
                f"{self._max_accumulated_pct}% limit"
            )

        return True, ""

    def reset_daily(self) -> None:
        """Reset daily swap counters (call at forex day end 22:00 UTC)."""
        self._daily_swap = 0.0
        log.info("swap_daily_reset", accumulated=self._accumulated_swap)

    # -- Internal -----------------------------------------------------------

    def _check_alerts(self) -> list[SwapAlert]:
        """Check swap costs against thresholds."""
        new_alerts: list[SwapAlert] = []

        # Triple swap warning (every Wednesday)
        if self.is_triple_swap_day and self._daily_swap > 0:
            alert = SwapAlert(
                alert_type="triple_swap_warning",
                severity="warning",
                message=(
                    f"TRIPLE SWAP WEDNESDAY — today's swap charges are 3x normal. "
                    f"Daily cost so far: {self._daily_swap:.2f}"
                ),
                daily_cost=self._daily_swap,
                total_accumulated=self._accumulated_swap,
            )
            new_alerts.append(alert)

        # Budget check
        ok, reason = self.check_swap_budget()
        if not ok:
            alert = SwapAlert(
                alert_type="swap_budget_exceeded",
                severity="critical",
                message=reason,
                daily_cost=self._daily_swap,
                total_accumulated=self._accumulated_swap,
            )
            new_alerts.append(alert)
            log.warning("swap_budget_exceeded", reason=reason)

        self._alerts.extend(new_alerts)
        return new_alerts

    def status(self) -> dict[str, Any]:
        """Return current swap tracking status."""
        return {
            "daily_swap_cost": round(self._daily_swap, 4),
            "accumulated_swap_cost": round(self._accumulated_swap, 4),
            "is_triple_swap_day": self.is_triple_swap_day,
            "per_position": {k: round(v, 4) for k, v in self._position_swaps.items()},
            "max_daily_pct": self._max_daily_pct,
            "max_accumulated_pct": self._max_accumulated_pct,
            "alerts": len(self._alerts),
        }


# ---------------------------------------------------------------------------
# Session Guard
# ---------------------------------------------------------------------------

class SessionGuard:
    """Restrict or warn on trading during low-liquidity forex sessions.

    Forex sessions have vastly different liquidity profiles:
    - Asian: thinner liquidity, wider spreads on non-JPY pairs
    - London: peak liquidity for EUR/GBP pairs
    - London-NY overlap: highest overall liquidity
    - Late NY: rapidly thinning liquidity, wider spreads
    - Off-hours (22:00-00:00): minimal liquidity, gap risk
    """

    class Session(str, Enum):
        ASIAN = "asian"
        LONDON = "london"
        LONDON_NY_OVERLAP = "overlap"
        NEW_YORK = "new_york"
        LATE_NY = "late_ny"
        OFF_HOURS = "off_hours"
        WEEKEND = "weekend"

    # Which sessions allow trading
    SESSION_POLICIES: dict[str, dict[str, Any]] = {
        "asian":    {"can_trade": True,  "liquidity": "low",    "max_positions": 3},
        "london":   {"can_trade": True,  "liquidity": "high",   "max_positions": 6},
        "overlap":  {"can_trade": True,  "liquidity": "high",   "max_positions": 6},
        "new_york": {"can_trade": True,  "liquidity": "high",   "max_positions": 6},
        "late_ny":  {"can_trade": True,  "liquidity": "medium", "max_positions": 4},
        "off_hours": {"can_trade": False, "liquidity": "low",   "max_positions": 0},
        "weekend":  {"can_trade": False, "liquidity": "closed", "max_positions": 0},
    }

    def __init__(self, allow_off_hours: bool = False) -> None:
        self._allow_off_hours = allow_off_hours

    @staticmethod
    def detect_session() -> Session:
        """Detect current forex trading session from UTC time.

        Returns:
            Current trading session.
        """
        now = datetime.now(timezone.utc)

        # Weekend check
        if now.weekday() == 5:  # Saturday
            return SessionGuard.Session.WEEKEND
        if now.weekday() == 6 and now.hour < MARKET_OPEN_HOUR_UTC:  # Sunday before open
            return SessionGuard.Session.WEEKEND
        if now.weekday() == 4 and now.hour >= MARKET_CLOSE_HOUR_UTC:  # Friday after close
            return SessionGuard.Session.WEEKEND

        hour = now.hour
        if 0 <= hour < 7:
            return SessionGuard.Session.ASIAN
        elif 7 <= hour < 12:
            return SessionGuard.Session.LONDON
        elif 12 <= hour < 16:
            return SessionGuard.Session.LONDON_NY_OVERLAP
        elif 16 <= hour < 20:
            return SessionGuard.Session.NEW_YORK
        elif 20 <= hour < 22:
            return SessionGuard.Session.LATE_NY
        else:
            return SessionGuard.Session.OFF_HOURS

    def can_trade_now(self) -> tuple[bool, str]:
        """Check if trading is allowed in the current session.

        Returns:
            (ok, reason) — ok=True if trading is permitted.
        """
        session = self.detect_session()
        policy = self.SESSION_POLICIES.get(session.value, {})

        if session == self.Session.WEEKEND:
            return False, "Market is closed (weekend)"

        if session == self.Session.OFF_HOURS:
            if self._allow_off_hours:
                return True, "Off-hours trading permitted (override active)"
            return False, (
                "Off-hours trading disabled — low liquidity, high gap risk. "
                "Market reopens at 22:00 UTC."
            )

        if not policy.get("can_trade", False):
            return False, f"Trading not permitted during {session.value} session"

        return True, ""

    def get_session_info(self) -> SessionStatus:
        """Get detailed current session status."""
        session = self.detect_session()
        policy = self.SESSION_POLICIES.get(session.value, {})
        can_trade, reason = self.can_trade_now()

        return SessionStatus(
            session=session.value,
            is_active=session not in (self.Session.WEEKEND, self.Session.OFF_HOURS),
            can_trade=can_trade,
            liquidity_level=policy.get("liquidity", "unknown"),
            reason=reason,
        )

    def get_max_positions(self) -> int:
        """Get maximum positions allowed for the current session."""
        session = self.detect_session()
        policy = self.SESSION_POLICIES.get(session.value, {})
        return policy.get("max_positions", 0)

    def status(self) -> dict[str, Any]:
        """Return session guard status."""
        info = self.get_session_info()
        return {
            "session": info.session,
            "is_active": info.is_active,
            "can_trade": info.can_trade,
            "liquidity_level": info.liquidity_level,
            "max_positions": self.get_max_positions(),
            "allow_off_hours_override": self._allow_off_hours,
            "reason": info.reason,
        }


# ---------------------------------------------------------------------------
# Weekend Gap Protection
# ---------------------------------------------------------------------------

class WeekendGapProtection:
    """Auto-close or warn about positions before forex market closes Friday.

    Weekend gaps can be 50-200+ pips on major pairs. A stop loss at 1.0850
    might fill at 1.0780 on Monday open — 70 pips of slippage the system
    never anticipated.

    Strategy: recommend closing positions with SL tighter than the typical
    weekend gap size before market close.
    """

    # Typical max weekend gap in pips by pair category
    TYPICAL_GAP_PIPS: dict[str, float] = {
        "major": 50.0,      # EUR/USD, GBP/USD, USD/JPY
        "minor": 80.0,      # EUR/GBP, AUD/NZD
        "exotic": 150.0,    # USD/TRY, EUR/PLN
        "default": 70.0,
    }

    def __init__(
        self,
        warn_hours_before_close: int = WEEKEND_CLOSE_WARN_HOURS,
        auto_close_gap_threshold: float = 50.0,
    ) -> None:
        self._warn_hours = warn_hours_before_close
        self._auto_close_threshold = auto_close_gap_threshold
        self._warnings: list[GapWarning] = []

    @property
    def is_pre_close_window(self) -> bool:
        """Check if we're in the warning window before market close."""
        now = datetime.now(timezone.utc)
        if now.weekday() != 4:  # Not Friday
            return False
        close_time = now.replace(
            hour=MARKET_CLOSE_HOUR_UTC, minute=0, second=0, microsecond=0
        )
        warn_time = close_time - timedelta(hours=self._warn_hours)
        return warn_time <= now < close_time

    @property
    def is_market_closed(self) -> bool:
        """Check if forex market is currently closed."""
        now = datetime.now(timezone.utc)
        # Saturday
        if now.weekday() == 5:
            return True
        # Sunday before 22:00 UTC
        if now.weekday() == 6 and now.hour < MARKET_OPEN_HOUR_UTC:
            return True
        # Friday after 22:00 UTC
        if now.weekday() == 4 and now.hour >= MARKET_CLOSE_HOUR_UTC:
            return True
        return False

    def check_position(
        self,
        symbol: str,
        direction: str,
        stop_loss_pips: float,
        pair_category: str = "default",
    ) -> GapWarning | None:
        """Check if a position should be closed before the weekend.

        Args:
            symbol: Instrument symbol.
            direction: Position direction.
            stop_loss_pips: Current stop loss distance in pips.
            pair_category: "major", "minor", "exotic", or "default".

        Returns:
            GapWarning if action is recommended, None otherwise.
        """
        if not self.is_pre_close_window:
            return None

        typical_gap = self.TYPICAL_GAP_PIPS.get(
            pair_category, self.TYPICAL_GAP_PIPS["default"]
        )

        if stop_loss_pips < typical_gap:
            # SL is tighter than typical weekend gap — high risk
            if stop_loss_pips < self._auto_close_threshold:
                action = "close"
                msg = (
                    f"WEEKEND GAP RISK: {symbol} SL is {stop_loss_pips:.0f} pips, "
                    f"typical weekend gap is {typical_gap:.0f} pips. "
                    f"RECOMMEND CLOSING before Friday market close."
                )
            else:
                action = "reduce"
                msg = (
                    f"Weekend gap risk: {symbol} SL is {stop_loss_pips:.0f} pips, "
                    f"typical gap is {typical_gap:.0f} pips. "
                    f"Consider reducing size or widening SL."
                )

            warning = GapWarning(
                symbol=symbol,
                direction=direction,
                current_sl_pips=stop_loss_pips,
                recommended_action=action,
                risk_message=msg,
            )
            self._warnings.append(warning)
            log.warning("weekend_gap_risk", symbol=symbol, sl_pips=stop_loss_pips)
            return warning

        return None

    def get_all_warnings(self) -> list[GapWarning]:
        """Get all active gap warnings."""
        return list(self._warnings)

    def clear_warnings(self) -> None:
        """Clear all warnings (e.g., after positions are managed)."""
        self._warnings.clear()

    def status(self) -> dict[str, Any]:
        """Return weekend gap protection status."""
        now = datetime.now(timezone.utc)
        return {
            "is_pre_close_window": self.is_pre_close_window,
            "is_market_closed": self.is_market_closed,
            "warn_hours_before": self._warn_hours,
            "auto_close_threshold_pips": self._auto_close_threshold,
            "active_warnings": len(self._warnings),
            "current_utc": now.isoformat(),
            "day_of_week": now.strftime("%A"),
        }


# ---------------------------------------------------------------------------
# Spread Monitor
# ---------------------------------------------------------------------------

class SpreadMonitor:
    """Track and alert on abnormal forex spreads.

    Forex spreads are the primary transaction cost. During news events,
    spreads can widen 5-10x, making normally profitable strategies
    unviable. This monitor:
    - Tracks rolling average spread per symbol
    - Alerts when current spread exceeds 3x average
    - Maintains per-symbol spread history for analysis
    """

    def __init__(
        self,
        max_spread_multiplier: float = 3.0,
        history_size: int = 200,
        min_samples_for_avg: int = 10,
    ) -> None:
        self._max_multiplier = max_spread_multiplier
        self._history_size = history_size
        self._min_samples = min_samples_for_avg
        self._spread_history: dict[str, list[float]] = {}
        self._alerts: list[SpreadAlert] = []
        self._last_spread: dict[str, float] = {}

    def record_spread(
        self,
        symbol: str,
        spread_pips: float,
    ) -> SpreadAlert | None:
        """Record a spread observation and check for anomalies.

        Args:
            symbol: Instrument symbol.
            spread_pips: Current spread in pips.

        Returns:
            SpreadAlert if spread is abnormal, None otherwise.
        """
        self._last_spread[symbol] = spread_pips

        if symbol not in self._spread_history:
            self._spread_history[symbol] = []

        history = self._spread_history[symbol]
        history.append(spread_pips)
        if len(history) > self._history_size:
            self._spread_history[symbol] = history[-self._history_size:]

        return self._check_anomaly(symbol, spread_pips)

    def get_average_spread(self, symbol: str, window: int = 20) -> float:
        """Get the rolling average spread for a symbol.

        Args:
            symbol: Instrument symbol.
            window: Number of recent observations to average.

        Returns:
            Average spread in pips, or 0 if insufficient data.
        """
        history = self._spread_history.get(symbol, [])
        if not history:
            return 0.0
        recent = history[-window:]
        return sum(recent) / len(recent)

    def is_spread_acceptable(
        self,
        symbol: str,
        current_spread_pips: float,
        max_pips: float = 0.0,
    ) -> tuple[bool, str]:
        """Check if a spread is acceptable for trading.

        Args:
            symbol: Instrument symbol.
            current_spread_pips: Current spread in pips.
            max_pips: Absolute max spread in pips (0 = use dynamic check only).

        Returns:
            (ok, reason) — ok=True if spread is acceptable.
        """
        # Absolute check
        if max_pips > 0 and current_spread_pips > max_pips:
            return False, (
                f"Spread {current_spread_pips:.1f} pips > absolute limit "
                f"{max_pips:.1f} pips"
            )

        # Dynamic check (vs average)
        avg = self.get_average_spread(symbol)
        if avg > 0 and current_spread_pips > avg * self._max_multiplier:
            return False, (
                f"Spread {current_spread_pips:.1f} pips is "
                f"{current_spread_pips / avg:.1f}x average {avg:.1f} pips "
                f"(limit: {self._max_multiplier}x)"
            )

        return True, ""

    def _check_anomaly(self, symbol: str, spread_pips: float) -> SpreadAlert | None:
        """Check if a spread observation is anomalous."""
        history = self._spread_history.get(symbol, [])
        if len(history) < self._min_samples:
            return None

        avg = sum(history[-20:]) / min(len(history), 20)
        if avg <= 0:
            return None

        multiplier = spread_pips / avg
        if multiplier >= self._max_multiplier:
            severity = "critical" if multiplier >= self._max_multiplier * 2 else "warning"
            alert = SpreadAlert(
                symbol=symbol,
                current_spread_pips=spread_pips,
                average_spread_pips=round(avg, 2),
                multiplier=round(multiplier, 2),
                severity=severity,
                message=(
                    f"Abnormal spread on {symbol}: {spread_pips:.1f} pips "
                    f"({multiplier:.1f}x average {avg:.1f} pips)"
                ),
            )
            self._alerts.append(alert)
            log.warning(
                "spread_anomaly",
                symbol=symbol,
                spread=spread_pips,
                average=avg,
                multiplier=multiplier,
            )
            return alert

        return None

    def status(self) -> dict[str, Any]:
        """Return spread monitor status."""
        per_symbol = {}
        for symbol, history in self._spread_history.items():
            if history:
                per_symbol[symbol] = {
                    "latest": round(history[-1], 2),
                    "average_20": round(sum(history[-20:]) / min(len(history), 20), 2),
                    "min": round(min(history), 2),
                    "max": round(max(history), 2),
                    "samples": len(history),
                }

        return {
            "tracked_symbols": len(self._spread_history),
            "max_multiplier": self._max_multiplier,
            "total_alerts": len(self._alerts),
            "per_symbol": per_symbol,
        }


# ---------------------------------------------------------------------------
# Forex Risk Manager (aggregates all forex risk components)
# ---------------------------------------------------------------------------

class ForexRiskManager:
    """Unified forex risk manager — single entry point for all forex risk checks.

    Aggregates:
    - MarginMonitor
    - SwapTracker
    - SessionGuard
    - WeekendGapProtection
    - SpreadMonitor

    Used by the Risk Governor to gate forex trades.
    """

    def __init__(
        self,
        account_balance: float = 1000.0,
        allow_off_hours: bool = False,
        max_leverage: float = OUR_MAX_LEVERAGE,
    ) -> None:
        self._balance = account_balance
        self.margin = MarginMonitor(max_leverage=max_leverage)
        self.swap = SwapTracker(account_balance=account_balance)
        self.session = SessionGuard(allow_off_hours=allow_off_hours)
        self.gap = WeekendGapProtection()
        self.spread = SpreadMonitor()

    def update_balance(self, new_balance: float) -> None:
        """Update account balance across all sub-systems."""
        self._balance = new_balance
        self.swap._balance = new_balance

    def check_trade(
        self,
        symbol: str,
        direction: str,
        lots: float,
        entry_price: float,
        stop_loss_pips: float,
        spread_pips: float,
        contract_size: float = 100_000.0,
        leverage: float = 30.0,
        pair_category: str = "default",
    ) -> tuple[bool, list[str]]:
        """Run all forex risk checks for a proposed trade.

        Args:
            symbol: Instrument symbol.
            direction: "long" or "short".
            lots: Position size in lots.
            entry_price: Entry price.
            stop_loss_pips: Stop loss distance in pips.
            spread_pips: Current spread in pips.
            contract_size: Units per lot.
            leverage: Account leverage.
            pair_category: "major", "minor", "exotic", or "default".

        Returns:
            (ok, warnings) — ok=True if all checks pass.
        """
        warnings: list[str] = []

        # 1. Session check
        session_ok, session_reason = self.session.can_trade_now()
        if not session_ok:
            return False, [session_reason]

        # 2. Spread check
        spread_ok, spread_reason = self.spread.is_spread_acceptable(symbol, spread_pips)
        if not spread_ok:
            return False, [spread_reason]

        # 3. Margin check
        notional = lots * contract_size * entry_price
        margin_required = notional / max(leverage, 1.0)
        margin_ok, margin_reason = self.margin.check_new_position(
            margin_required, notional
        )
        if not margin_ok:
            return False, [margin_reason]

        # 4. Weekend gap check (warning, not blocking)
        gap_warning = self.gap.check_position(
            symbol, direction, stop_loss_pips, pair_category
        )
        if gap_warning:
            warnings.append(gap_warning.risk_message)

        # 5. Swap projection
        projected_daily_swap = self.swap.project_daily_swap(
            symbol, direction, lots, 0, 0  # rates passed from caller
        )
        if projected_daily_swap > 0:
            swap_pct = (projected_daily_swap / self._balance * 100) if self._balance > 0 else 0
            if swap_pct > 0.1:
                warnings.append(
                    f"Projected daily swap: ${projected_daily_swap:.2f} "
                    f"({swap_pct:.2f}% of account)"
                )

        # 6. Triple swap warning
        if self.swap.is_triple_swap_day:
            warnings.append(
                "TRIPLE SWAP WEDNESDAY — swap charges are 3x today"
            )

        return True, warnings

    def status(self) -> dict[str, Any]:
        """Return full forex risk status."""
        return {
            "balance": self._balance,
            "margin": self.margin.status(),
            "swap": self.swap.status(),
            "session": self.session.status(),
            "weekend_gap": self.gap.status(),
            "spread": self.spread.status(),
        }
