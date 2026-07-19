"""Circuit Breaker System — auto-halt trading when risk limits are breached.

Multiple independent breakers:
- Daily loss breaker
- Consecutive loss breaker
- Volatility breaker
- Black swan detector

When any breaker trips, all trading halts immediately.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Breaker types
# ---------------------------------------------------------------------------

class BreakerType(str, Enum):
    DAILY_LOSS = "daily_loss"
    CONSECUTIVE_LOSS = "consecutive_loss"
    VOLATILITY = "volatility"
    BLACK_SWAN = "black_swan"
    SPREAD_WIDENING = "spread_widening"
    MARGIN_LEVEL = "margin_level"
    MANUAL = "manual"


class TradingSession(str, Enum):
    """Forex trading sessions with distinct liquidity profiles."""
    ASIAN = "asian"               # 00:00–09:00 UTC
    LONDON = "london"             # 07:00–16:00 UTC
    LONDON_NY_OVERLAP = "overlap" # 12:00–16:00 UTC (peak liquidity)
    NEW_YORK = "new_york"         # 12:00–21:00 UTC
    LATE_NY = "late_ny"           # 20:00–22:00 UTC (thinning liquidity)
    OFF_HOURS = "off_hours"       # 22:00–00:00 UTC


class CircuitBreakerState(BaseModel):
    """Snapshot of circuit breaker status."""
    tripped: bool = False
    trip_reason: str = ""
    trip_type: BreakerType | None = None
    tripped_at: datetime | None = None
    daily_pnl: float = 0.0
    consecutive_losses: int = 0
    max_consecutive_losses: int = 0
    volatility_zscore: float = 0.0
    cooldown_remaining_seconds: float = 0.0
    current_session: str = ""
    spread_widening_active: bool = False
    asset_type: str = "crypto"


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Multi-trigger circuit breaker that halts trading when risk limits are hit.

    Progressive response for $7 micro-accounts:
    - 3 consecutive losses → reduce position size 50%
    - 5 consecutive losses → pause trading 1 hour
    - Daily loss limit hit → stop trading for the day
    - Emergency kill switch → immediate halt

    Each breaker type is independent — any single trip halts everything.
    Breakers can only be manually reset after a cooldown period.

    Forex-specific additions:
    - Spread widening breaker (halt if spread > 3x normal)
    - Session-aware thresholds (tighter limits in low-liquidity sessions)
    - 22:00 UTC daily reset (forex day end)
    - 2% daily loss limit for forex (vs 3% for crypto)
    """

    # Session-specific multipliers for circuit breaker thresholds.
    # Lower multiplier = tighter limits.
    SESSION_MULTIPLIERS: dict[TradingSession, float] = {
        TradingSession.ASIAN: 0.70,            # Tighter — lower liquidity
        TradingSession.LONDON: 1.0,            # Standard
        TradingSession.LONDON_NY_OVERLAP: 1.2, # Wider — peak liquidity
        TradingSession.NEW_YORK: 1.0,          # Standard
        TradingSession.LATE_NY: 0.80,          # Tighter — thinning liquidity
        TradingSession.OFF_HOURS: 0.60,        # Tightest
    }

    # Forex daily loss limit (tighter than crypto)
    FOREX_MAX_DAILY_LOSS_PCT: float = 2.0

    def __init__(
        self,
        max_daily_loss_pct: float = 5.0,
        max_consecutive_losses: int = 5,
        volatility_zscore_threshold: float = 3.0,
        black_swan_zscore_threshold: float = 5.0,
        cooldown_minutes: int = 60,
        account_balance: float = 7.0,
        asset_type: str = "crypto",
        max_spread_multiplier: float = 3.0,
    ) -> None:
        self._asset_type = asset_type
        # Apply tighter forex limit if asset is forex
        if asset_type == "forex":
            self._max_daily_loss_pct = min(
                max_daily_loss_pct, self.FOREX_MAX_DAILY_LOSS_PCT
            )
        else:
            self._max_daily_loss_pct = max_daily_loss_pct
        self._max_consecutive_losses = max_consecutive_losses
        self._vol_zscore_threshold = volatility_zscore_threshold
        self._black_swan_zscore = black_swan_zscore_threshold
        self._cooldown_minutes = cooldown_minutes
        self._balance = account_balance

        # Spread widening breaker
        self._max_spread_multiplier = max_spread_multiplier
        self._spread_history: dict[str, list[float]] = {}
        self._spread_widening_active = False

        # Session tracking
        self._current_session: TradingSession | None = None

        # State
        self._tripped = False
        self._trip_reason = ""
        self._trip_type: BreakerType | None = None
        self._tripped_at: datetime | None = None

        # Counters
        self._daily_pnl = 0.0
        self._consecutive_losses = 0
        self._max_consecutive_seen = 0
        self._volatility_zscore = 0.0

        # Rolling window for volatility
        self._recent_returns: list[float] = []
        self._max_window = 100

        # Daily reset tracking — forex resets at 22:00 UTC
        self._last_daily_reset_date = datetime.now(timezone.utc).date()

    # -- Properties ---------------------------------------------------------

    @property
    def is_tripped(self) -> bool:
        return self._tripped

    @property
    def trip_reason(self) -> str:
        return self._trip_reason

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses

    @property
    def state(self) -> CircuitBreakerState:
        cooldown = 0.0
        if self._tripped and self._tripped_at:
            elapsed = (datetime.now(timezone.utc) - self._tripped_at).total_seconds()
            cooldown = max(0, self._cooldown_minutes * 60 - elapsed)

        return CircuitBreakerState(
            tripped=self._tripped,
            trip_reason=self._trip_reason,
            trip_type=self._trip_type,
            tripped_at=self._tripped_at,
            daily_pnl=self._daily_pnl,
            consecutive_losses=self._consecutive_losses,
            max_consecutive_losses=self._max_consecutive_seen,
            volatility_zscore=self._volatility_zscore,
            cooldown_remaining_seconds=cooldown,
            current_session=self._current_session.value if self._current_session else "",
            spread_widening_active=self._spread_widening_active,
            asset_type=self._asset_type,
        )

    # -- Record events ------------------------------------------------------

    def record_loss(self, pnl: float) -> None:
        """Record a trade result and check all breakers.

        Progressive response:
        - Tracks consecutive losses for governor to act on
        - Trips breaker at max_consecutive_losses

        Args:
            pnl: Trade profit/loss (negative = loss).
        """
        self._daily_pnl += pnl

        # Track consecutive losses
        if pnl < 0:
            self._consecutive_losses += 1
            self._max_consecutive_seen = max(
                self._max_consecutive_seen, self._consecutive_losses
            )
        else:
            self._consecutive_losses = 0

        # Track volatility
        self._recent_returns.append(pnl)
        if len(self._recent_returns) > self._max_window:
            self._recent_returns = self._recent_returns[-self._max_window:]

        # Check all breakers
        self._check_daily_loss()
        self._check_consecutive_losses()
        self._check_volatility()
        self._check_black_swan()

    def record_return(self, return_pct: float) -> None:
        """Record a return percentage for volatility monitoring."""
        self._recent_returns.append(return_pct)
        if len(self._recent_returns) > self._max_window:
            self._recent_returns = self._recent_returns[-self._max_window:]
        self._check_volatility()
        self._check_black_swan()

    def check_spread(self, symbol: str, current_spread_pips: float) -> bool:
        """Check if current spread indicates abnormal widening.

        Records the spread and checks against 3x average threshold.
        Returns True if spread is normal, False if breaker tripped.
        """
        if symbol not in self._spread_history:
            self._spread_history[symbol] = []

        history = self._spread_history[symbol]
        history.append(current_spread_pips)
        if len(history) > 100:
            self._spread_history[symbol] = history[-100:]

        if len(history) < 5:
            return True  # Not enough data yet

        avg_spread = sum(history[-20:]) / min(len(history), 20)
        if avg_spread > 0 and current_spread_pips > avg_spread * self._max_spread_multiplier:
            self._spread_widening_active = True
            self._trip(
                BreakerType.SPREAD_WIDENING,
                f"Spread widening: {current_spread_pips:.1f} pips "
                f"> {self._max_spread_multiplier}x average {avg_spread:.1f} pips "
                f"on {symbol}",
            )
            return False

        self._spread_widening_active = False
        return True

    def set_session(self, session: TradingSession) -> None:
        """Update current trading session for session-aware thresholds."""
        if session != self._current_session:
            old = self._current_session
            self._current_session = session
            mult = self.SESSION_MULTIPLIERS.get(session, 1.0)
            log.info(
                "circuit_breaker_session_changed",
                old_session=old.value if old else "none",
                new_session=session.value,
                threshold_multiplier=mult,
            )

    @staticmethod
    def detect_session() -> TradingSession:
        """Detect current forex trading session from UTC time."""
        now = datetime.now(timezone.utc)
        hour = now.hour
        if 0 <= hour < 7:
            return TradingSession.ASIAN
        elif 7 <= hour < 12:
            return TradingSession.LONDON
        elif 12 <= hour < 16:
            return TradingSession.LONDON_NY_OVERLAP
        elif 16 <= hour < 20:
            return TradingSession.NEW_YORK
        elif 20 <= hour < 22:
            return TradingSession.LATE_NY
        else:
            return TradingSession.OFF_HOURS

    def get_effective_thresholds(self) -> dict[str, float]:
        """Return circuit breaker thresholds adjusted for the current session."""
        mult = 1.0
        if self._current_session:
            mult = self.SESSION_MULTIPLIERS.get(self._current_session, 1.0)
        return {
            "max_daily_loss_pct": self._max_daily_loss_pct,
            "max_consecutive_losses": self._max_consecutive_losses,
            "volatility_zscore_threshold": self._vol_zscore_threshold * mult,
            "black_swan_zscore": self._black_swan_zscore * mult,
            "session_multiplier": mult,
        }

    # -- Breaker checks -----------------------------------------------------

    def _check_daily_loss(self) -> None:
        """Check if daily loss limit is breached."""
        if self._balance <= 0:
            return
        loss_pct = abs(min(0, self._daily_pnl)) / self._balance * 100
        if loss_pct >= self._max_daily_loss_pct:
            asset_note = f" (forex limit: {self.FOREX_MAX_DAILY_LOSS_PCT}%)" if self._asset_type == "forex" else ""
            self._trip(
                BreakerType.DAILY_LOSS,
                f"Daily loss {loss_pct:.2f}% >= {self._max_daily_loss_pct}%{asset_note}",
            )

    def _check_consecutive_losses(self) -> None:
        """Check if consecutive loss limit is breached."""
        if self._consecutive_losses >= self._max_consecutive_losses:
            self._trip(
                BreakerType.CONSECUTIVE_LOSS,
                f"Consecutive losses {self._consecutive_losses} >= {self._max_consecutive_losses}",
            )

    def _check_volatility(self) -> None:
        """Check if recent volatility is abnormally high (z-score).

        Uses session-adjusted thresholds when a session is active.
        """
        if len(self._recent_returns) < 20:
            return  # Need enough data

        self._volatility_zscore = self._compute_zscore()
        threshold = self._vol_zscore_threshold
        # Adjust threshold for session liquidity
        if self._current_session:
            mult = self.SESSION_MULTIPLIERS.get(self._current_session, 1.0)
            threshold = threshold * mult

        if abs(self._volatility_zscore) >= threshold:
            session_note = f" (session: {self._current_session.value})" if self._current_session else ""
            self._trip(
                BreakerType.VOLATILITY,
                f"Volatility z-score {self._volatility_zscore:.2f} "
                f">= {threshold:.2f}{session_note}",
            )

    def _check_black_swan(self) -> None:
        """Detect potential black swan events (extreme z-score)."""
        if len(self._recent_returns) < 20:
            return
        if abs(self._volatility_zscore) >= self._black_swan_zscore:
            self._trip(
                BreakerType.BLACK_SWAN,
                f"Black swan detected: z-score {self._volatility_zscore:.2f}",
            )

    def _compute_zscore(self) -> float:
        """Compute z-score of the most recent return vs the rolling window."""
        if len(self._recent_returns) < 2:
            return 0.0
        data = self._recent_returns[:-1]  # exclude the latest from the baseline
        latest = self._recent_returns[-1]
        mean = sum(data) / len(data)
        variance = sum((x - mean) ** 2 for x in data) / len(data)
        std = variance ** 0.5
        if std < 1e-10:
            return 0.0
        return (latest - mean) / std

    # -- Trip / reset -------------------------------------------------------

    def _trip(self, breaker_type: BreakerType, reason: str) -> None:
        """Trip the circuit breaker."""
        if self._tripped:
            return  # Already tripped

        self._tripped = True
        self._trip_reason = reason
        self._trip_type = breaker_type
        self._tripped_at = datetime.now(timezone.utc)

        log.critical(
            "circuit_breaker_tripped",
            breaker_type=breaker_type.value,
            reason=reason,
            daily_pnl=self._daily_pnl,
            consecutive_losses=self._consecutive_losses,
            vol_zscore=self._volatility_zscore,
        )

    def reset(self) -> bool:
        """Attempt to reset the circuit breaker.

        Returns True if reset was successful, False if still in cooldown.
        """
        if not self._tripped:
            return True

        if self._tripped_at:
            elapsed = (datetime.now(timezone.utc) - self._tripped_at).total_seconds()
            if elapsed < self._cooldown_minutes * 60:
                remaining = self._cooldown_minutes * 60 - elapsed
                log.warning(
                    "circuit_breaker_cooldown",
                    remaining_seconds=round(remaining),
                )
                return False

        self._tripped = False
        self._trip_reason = ""
        self._trip_type = None
        self._tripped_at = None

        log.info("circuit_breaker_reset")
        return True

    def force_reset(self) -> None:
        """Force reset bypassing cooldown (admin override)."""
        self._tripped = False
        self._trip_reason = ""
        self._trip_type = None
        self._tripped_at = None
        log.warning("circuit_breaker_force_reset")

    def emergency_kill(self, reason: str = "Emergency kill switch activated") -> None:
        """Emergency kill switch — immediate halt, no cooldown required.

        Use when:
        - Market anomaly detected
        - Broker connection unstable
        - Manual intervention needed
        - Any "something is very wrong" scenario
        """
        self._trip(BreakerType.MANUAL, f"EMERGENCY: {reason}")
        log.critical("emergency_kill_switch_activated", reason=reason)

    @property
    def should_reduce_size(self) -> bool:
        """Check if position sizes should be reduced (progressive response).

        Returns True when consecutive losses >= 3 but < pause threshold.
        Governor uses this to apply 50% size reduction.
        """
        return 3 <= self._consecutive_losses < self._max_consecutive_losses

    @property
    def size_reduction_factor(self) -> float:
        """Return the size reduction factor based on consecutive losses.

        3 losses: 50% (0.5)
        4 losses: 25% (0.25)
        5+ losses: 0% (tripped)
        """
        if self._consecutive_losses < 3:
            return 1.0
        if self._consecutive_losses >= self._max_consecutive_losses:
            return 0.0
        # Each additional loss halves the size
        return 0.5 ** (self._consecutive_losses - 2)

    # -- Daily reset --------------------------------------------------------

    def reset_daily(self) -> None:
        """Reset daily counters (call at start of new trading day)."""
        self._daily_pnl = 0.0
        self._spread_widening_active = False
        # Don't reset consecutive losses — that tracks across days
        log.info("circuit_breaker_daily_reset")

    def maybe_auto_reset_daily(self) -> bool:
        """Auto-reset daily counters at 22:00 UTC (forex day end).

        For forex, the trading day ends at 5 PM EST (22:00 UTC),
        not midnight UTC. This method checks if we've crossed that
        boundary and resets if so.

        Returns True if a reset was performed.
        """
        now = datetime.now(timezone.utc)
        today = now.date()

        # Reset once per day when we're past 22:00 UTC
        if now.hour >= 22 and self._last_daily_reset_date < today:
            self.reset_daily()
            self._last_daily_reset_date = today
            log.info("circuit_breaker_forex_day_end_reset", utc_time=str(now.time()))
            return True
        return False

    # -- Status -------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return current breaker status."""
        return self.state.model_dump()
