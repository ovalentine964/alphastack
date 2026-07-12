"""Drawdown Manager — daily, weekly, and total drawdown limits.

Tracks drawdown from peak equity and triggers progressive de-escalation.
Hard limits — when breached, trading halts until reset.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Drawdown state
# ---------------------------------------------------------------------------

class DrawdownState(BaseModel):
    """Current drawdown tracking state."""
    starting_balance: float = 0.0
    peak_balance: float = 0.0
    current_balance: float = 0.0
    daily_starting_balance: float = 0.0
    weekly_starting_balance: float = 0.0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    total_drawdown: float = 0.0  # absolute
    daily_pct: float = 0.0
    weekly_pct: float = 0.0
    total_pct: float = 0.0
    max_daily_pct: float = 0.0  # historical max
    max_total_pct: float = 0.0  # historical max
    last_reset: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Drawdown Manager
# ---------------------------------------------------------------------------

class DrawdownManager:
    """Tracks and enforces drawdown limits at daily, weekly, and total levels.

    Features:
    - Progressive de-escalation as drawdown increases
    - Hard circuit-breaker limits
    - Daily/weekly auto-reset
    """

    def __init__(
        self,
        account_balance: float = 1000.0,
        max_daily_pct: float = 3.0,
        max_weekly_pct: float = 7.0,
        max_total_pct: float = 15.0,
    ) -> None:
        self._max_daily_pct = max_daily_pct
        self._max_weekly_pct = max_weekly_pct
        self._max_total_pct = max_total_pct

        now = datetime.now(timezone.utc)
        self._state = DrawdownState(
            starting_balance=account_balance,
            peak_balance=account_balance,
            current_balance=account_balance,
            daily_starting_balance=account_balance,
            weekly_starting_balance=account_balance,
            last_reset=now,
        )

    # -- Properties ---------------------------------------------------------

    @property
    def state(self) -> DrawdownState:
        return self._state

    @property
    def max_daily_pct(self) -> float:
        return self._max_daily_pct

    @property
    def max_total_pct(self) -> float:
        return self._max_total_pct

    # -- Core tracking ------------------------------------------------------

    def update_balance(self, new_balance: float) -> None:
        """Update current balance and recalculate drawdown metrics."""
        s = self._state
        s.current_balance = new_balance

        # Update peak
        if new_balance > s.peak_balance:
            s.peak_balance = new_balance

        # P&L tracking
        s.daily_pnl = new_balance - s.daily_starting_balance
        s.weekly_pnl = new_balance - s.weekly_starting_balance

        # Drawdown from peak
        s.total_drawdown = s.peak_balance - new_balance

        # Percentages
        if s.peak_balance > 0:
            s.total_pct = (s.total_drawdown / s.peak_balance) * 100
        if s.daily_starting_balance > 0:
            s.daily_pct = max(0, (-s.daily_pnl / s.daily_starting_balance) * 100)
        if s.weekly_starting_balance > 0:
            s.weekly_pct = max(0, (-s.weekly_pnl / s.weekly_starting_balance) * 100)

        # Track historical maxes
        s.max_daily_pct = max(s.max_daily_pct, s.daily_pct)
        s.max_total_pct = max(s.max_total_pct, s.total_pct)

    def record_pnl(self, pnl: float) -> None:
        """Record a trade P&L and update balance."""
        self.update_balance(self._state.current_balance + pnl)

    # -- Limit checks -------------------------------------------------------

    def is_breach(self) -> bool:
        """Check if any drawdown limit is breached."""
        s = self._state
        return (
            s.daily_pct >= self._max_daily_pct
            or s.weekly_pct >= self._max_weekly_pct
            or s.total_pct >= self._max_total_pct
        )

    def breach_details(self) -> list[str]:
        """Return list of breached limits."""
        reasons: list[str] = []
        s = self._state
        if s.daily_pct >= self._max_daily_pct:
            reasons.append(
                f"Daily drawdown {s.daily_pct:.2f}% >= {self._max_daily_pct}%"
            )
        if s.weekly_pct >= self._max_weekly_pct:
            reasons.append(
                f"Weekly drawdown {s.weekly_pct:.2f}% >= {self._max_weekly_pct}%"
            )
        if s.total_pct >= self._max_total_pct:
            reasons.append(
                f"Total drawdown {s.total_pct:.2f}% >= {self._max_total_pct}%"
            )
        return reasons

    # -- Progressive de-escalation ------------------------------------------

    def risk_multiplier(self) -> float:
        """Return a risk multiplier based on current drawdown level.

        1.0 = full risk allowed
        0.0 = no risk (limit breached)
        """
        s = self._state
        # Use the worst of daily or total drawdown
        max_pct = max(s.daily_pct / self._max_daily_pct, s.total_pct / self._max_total_pct)

        if max_pct >= 1.0:
            return 0.0  # halt
        elif max_pct >= 0.8:
            return 0.1  # 10% of normal risk
        elif max_pct >= 0.6:
            return 0.25
        elif max_pct >= 0.4:
            return 0.50
        elif max_pct >= 0.2:
            return 0.75
        else:
            return 1.0

    # -- Reset ---------------------------------------------------------------

    def reset_daily(self) -> None:
        """Reset daily drawdown tracking (call at start of new trading day)."""
        s = self._state
        s.daily_starting_balance = s.current_balance
        s.daily_pnl = 0.0
        s.daily_pct = 0.0
        s.last_reset = datetime.now(timezone.utc)
        log.info("drawdown_daily_reset", balance=s.current_balance)

    def reset_weekly(self) -> None:
        """Reset weekly drawdown tracking (call at start of new trading week)."""
        s = self._state
        s.weekly_starting_balance = s.current_balance
        s.weekly_pnl = 0.0
        s.weekly_pct = 0.0
        log.info("drawdown_weekly_reset", balance=s.current_balance)

    def full_reset(self) -> None:
        """Full reset — use when restarting with fresh capital."""
        balance = self._state.current_balance
        now = datetime.now(timezone.utc)
        self._state = DrawdownState(
            starting_balance=balance,
            peak_balance=balance,
            current_balance=balance,
            daily_starting_balance=balance,
            weekly_starting_balance=balance,
            last_reset=now,
        )
        log.info("drawdown_full_reset", balance=balance)

    # -- Status -------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return current drawdown status as dict."""
        s = self._state
        return {
            "current_balance": s.current_balance,
            "peak_balance": s.peak_balance,
            "daily_pnl": s.daily_pnl,
            "daily_pct": round(s.daily_pct, 2),
            "weekly_pnl": s.weekly_pnl,
            "weekly_pct": round(s.weekly_pct, 2),
            "total_drawdown": s.total_drawdown,
            "total_pct": round(s.total_pct, 2),
            "max_daily_pct": round(s.max_daily_pct, 2),
            "max_total_pct": round(s.max_total_pct, 2),
            "risk_multiplier": self.risk_multiplier(),
            "is_breach": self.is_breach(),
        }
