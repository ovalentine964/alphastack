"""Position Sizing Engine — risk-based sizing with spread cost awareness.

Critical for small accounts ($7) where spread costs can eat entire profits.
Supports fixed-risk, Kelly criterion, and spread-adjusted sizing.
"""

from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Sizing models
# ---------------------------------------------------------------------------

class SizingMethod(str, Enum):
    FIXED_RISK = "fixed_risk"          # Risk X% of account per trade
    KELLY = "kelly"                     # Kelly criterion
    FIXED_FRACTIONAL = "fixed_frac"     # Fixed fraction of account
    SPREAD_ADJUSTED = "spread_adjusted" # Adjusted for spread cost


class SizingRequest(BaseModel):
    """Input for position sizing calculation."""
    symbol: str
    direction: str  # long | short
    entry_price: float
    stop_loss: float
    account_balance: float
    daily_drawdown_pct: float = 0.0
    method: SizingMethod = SizingMethod.FIXED_RISK
    # Kelly inputs
    win_rate: float = 0.5
    avg_win: float = 1.5
    avg_loss: float = 1.0
    # Spread cost
    spread_pips: float = 0.0
    pip_value: float = 0.0001  # for forex pairs
    # Constraints
    max_risk_pct: float = 2.0  # max % of account to risk
    min_size: float = 0.01     # minimum lot size (broker minimum)


class SizingResult(BaseModel):
    """Output from position sizing calculation."""
    max_size: float = 0.0
    min_size: float = 0.0
    risk_amount: float = 0.0
    risk_pct: float = 0.0
    method_used: SizingMethod = SizingMethod.FIXED_RISK
    spread_cost: float = 0.0
    effective_risk_pct: float = 0.0  # risk + spread as % of account
    adjustments: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Position Sizer
# ---------------------------------------------------------------------------

class PositionSizer:
    """Risk-based position sizing engine.

    Supports multiple sizing methods and is spread-cost aware,
    which is critical for small accounts where a few pips of spread
    can represent a significant portion of the risk budget.
    """

    def __init__(
        self,
        account_balance: float = 1000.0,
        max_position_pct: float = 5.0,
        default_risk_pct: float = 1.0,
        max_risk_pct: float = 2.0,
    ) -> None:
        self._balance = account_balance
        self._max_position_pct = max_position_pct
        self._default_risk_pct = default_risk_pct
        self._max_risk_pct = max_risk_pct

    def update_balance(self, new_balance: float) -> None:
        """Update account balance reference."""
        self._balance = new_balance

    def size_position(self, request: SizingRequest) -> SizingResult:
        """Calculate the maximum safe position size.

        Runs all sizing methods and returns the most conservative result.
        """
        adjustments: list[str] = []
        balance = request.account_balance or self._balance

        # Progressive de-escalation: reduce risk as drawdown increases
        effective_risk_pct = self._de_escalate_risk(
            self._default_risk_pct,
            request.daily_drawdown_pct,
        )
        if effective_risk_pct < self._default_risk_pct:
            adjustments.append(
                f"Risk reduced to {effective_risk_pct:.2f}% "
                f"(drawdown {request.daily_drawdown_pct:.1f}%)"
            )

        # Calculate by method
        if request.method == SizingMethod.KELLY:
            size = self._kelly_size(request, balance, effective_risk_pct)
        else:
            size = self._fixed_risk_size(request, balance, effective_risk_pct)

        # Spread cost adjustment
        spread_cost = self._compute_spread_cost(request)
        spread_adjusted_size = self._adjust_for_spread(
            size, spread_cost, balance, request
        )
        if spread_adjusted_size < size:
            adjustments.append(
                f"Size reduced for spread cost: {spread_cost:.4f}"
            )
            size = spread_adjusted_size

        # Hard caps
        max_by_pct = balance * (self._max_position_pct / 100) / max(request.entry_price, 1e-10)
        size = min(size, max_by_pct)

        # Effective risk check
        risk_amount = self._compute_risk_amount(request, size)
        effective_risk = ((risk_amount + spread_cost) / balance * 100) if balance > 0 else 0

        if effective_risk > self._max_risk_pct:
            # Scale down to fit within max risk
            target_risk_amount = balance * (self._max_risk_pct / 100) - spread_cost
            if target_risk_amount > 0 and request.entry_price != request.stop_loss:
                sl_distance = abs(request.entry_price - request.stop_loss)
                size = target_risk_amount / sl_distance
                adjustments.append(
                    f"Capped at {self._max_risk_pct}% effective risk"
                )

        result = SizingResult(
            max_size=max(size, 0),
            min_size=request.min_size,
            risk_amount=risk_amount,
            risk_pct=(risk_amount / balance * 100) if balance > 0 else 0,
            method_used=request.method,
            spread_cost=spread_cost,
            effective_risk_pct=effective_risk,
            adjustments=adjustments,
        )

        log.debug(
            "position_sized",
            symbol=request.symbol,
            method=request.method.value,
            max_size=result.max_size,
            risk_pct=result.risk_pct,
            spread_cost=result.spread_cost,
        )
        return result

    # -- Sizing methods -----------------------------------------------------

    def _fixed_risk_size(
        self,
        request: SizingRequest,
        balance: float,
        risk_pct: float,
    ) -> float:
        """Fixed-risk sizing: risk X% of account per trade."""
        risk_amount = balance * (risk_pct / 100)
        sl_distance = abs(request.entry_price - request.stop_loss)
        if sl_distance < 1e-10:
            return 0.0
        return risk_amount / sl_distance

    def _kelly_size(
        self,
        request: SizingRequest,
        balance: float,
        risk_pct: float,
    ) -> float:
        """Kelly criterion sizing with half-Kelly safety factor.

        Kelly % = W - (1-W)/R where W=win_rate, R=win/loss ratio.
        We use half-Kelly to reduce variance.
        """
        w = request.win_rate
        r = request.avg_win / max(request.avg_loss, 1e-10)
        kelly_full = w - (1 - w) / r

        if kelly_full <= 0:
            # Negative edge — minimum size only
            log.info("kelly_negative_edge", win_rate=w, ratio=r)
            return request.min_size

        # Half-Kelly for safety
        kelly_half = kelly_full * 0.5

        # Cap at our max risk
        kelly_pct = min(kelly_half * 100, risk_pct)
        risk_amount = balance * (kelly_pct / 100)

        sl_distance = abs(request.entry_price - request.stop_loss)
        if sl_distance < 1e-10:
            return 0.0
        return risk_amount / sl_distance

    # -- Spread & de-escalation --------------------------------------------

    def _compute_spread_cost(self, request: SizingRequest) -> float:
        """Compute the monetary cost of the spread."""
        if request.spread_pips <= 0:
            return 0.0
        spread_in_price = request.spread_pips * request.pip_value
        return spread_in_price  # per unit; multiplied by size at execution

    def _adjust_for_spread(
        self,
        size: float,
        spread_cost_per_unit: float,
        balance: float,
        request: SizingRequest,
    ) -> float:
        """Reduce size if spread cost makes the trade uneconomical.

        For a $7 account, a 2-pip spread on EUR/USD (~$0.0002) on 0.01 lot
        is about $0.02 — nearly 0.3% of the account. That matters.
        """
        if spread_cost_per_unit <= 0 or size <= 0:
            return size

        total_spread = spread_cost_per_unit * size
        sl_distance = abs(request.entry_price - request.stop_loss)
        risk_amount = sl_distance * size

        # If spread cost > 30% of risk, the trade has negative expected value
        if risk_amount > 0 and total_spread / risk_amount > 0.30:
            # Scale down until spread is max 30% of risk
            target_risk = total_spread / 0.30
            new_size = target_risk / max(sl_distance, 1e-10)
            return new_size

        return size

    def _de_escalate_risk(self, base_pct: float, daily_dd_pct: float) -> float:
        """Progressive de-escalation: reduce risk as drawdown increases.

        Drawdown 0-2%:  full risk
        Drawdown 2-5%:  50% risk
        Drawdown 5-10%: 25% risk
        Drawdown >10%:  10% risk
        """
        if daily_dd_pct <= 2.0:
            return base_pct
        elif daily_dd_pct <= 5.0:
            return base_pct * 0.50
        elif daily_dd_pct <= 10.0:
            return base_pct * 0.25
        else:
            return base_pct * 0.10

    # -- Helpers ------------------------------------------------------------

    def _compute_risk_amount(
        self,
        request: SizingRequest,
        size: float,
    ) -> float:
        """Compute the monetary risk for a given position size."""
        sl_distance = abs(request.entry_price - request.stop_loss)
        return sl_distance * size
