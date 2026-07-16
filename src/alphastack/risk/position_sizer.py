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

class AssetType(str, Enum):
    CRYPTO = "crypto"
    FOREX = "forex"


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
    # Forex-specific
    asset_type: AssetType = AssetType.CRYPTO
    contract_size: float = 100_000.0  # units per standard lot (forex)
    lot_step: float = 0.01           # minimum lot increment
    leverage: float = 30.0           # broker-provided leverage
    swap_rate_daily: float = 0.0     # daily swap cost per lot


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
    # Forex-specific results
    lots: float = 0.0                # size in lots (forex) or 0 for crypto
    margin_required: float = 0.0     # margin needed for this position
    notional_value: float = 0.0      # notional value of the position
    effective_leverage: float = 0.0  # resulting leverage if this trade executes


# ---------------------------------------------------------------------------
# Position Sizer
# ---------------------------------------------------------------------------

class PositionSizer:
    """Risk-based position sizing engine.

    Supports multiple sizing methods and is spread-cost aware,
    which is critical for small accounts where a few pips of spread
    can represent a significant portion of the risk budget.
    """

    # Our hard leverage cap — tighter than broker's 50x
    OUR_MAX_LEVERAGE: float = 20.0

    def __init__(
        self,
        account_balance: float = 1000.0,
        max_position_pct: float = 5.0,
        default_risk_pct: float = 1.0,
        max_risk_pct: float = 2.0,
        max_leverage: float = 20.0,
    ) -> None:
        self._balance = account_balance
        self._max_position_pct = max_position_pct
        self._default_risk_pct = default_risk_pct
        self._max_risk_pct = max_risk_pct
        self._max_leverage = min(max_leverage, self.OUR_MAX_LEVERAGE)

    def update_balance(self, new_balance: float) -> None:
        """Update account balance reference."""
        self._balance = new_balance

    def size_position(self, request: SizingRequest) -> SizingResult:
        """Calculate the maximum safe position size.

        Runs all sizing methods and returns the most conservative result.
        Routes to forex lot-based or crypto quantity-based sizing.
        """
        if request.asset_type == AssetType.FOREX:
            return self._size_forex(request)
        return self._size_crypto(request)

    def _size_crypto(self, request: SizingRequest) -> SizingResult:
        """Crypto position sizing (original logic)."""
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

    def _size_forex(self, request: SizingRequest) -> SizingResult:
        """Forex lot-based position sizing.

        Calculates size in lots, enforces leverage caps, checks margin.
        """
        adjustments: list[str] = []
        balance = request.account_balance or self._balance

        # Progressive de-escalation
        effective_risk_pct = self._de_escalate_risk(
            self._default_risk_pct,
            request.daily_drawdown_pct,
        )
        if effective_risk_pct < self._default_risk_pct:
            adjustments.append(
                f"Risk reduced to {effective_risk_pct:.2f}% "
                f"(drawdown {request.daily_drawdown_pct:.1f}%)"
            )

        risk_amount = balance * (effective_risk_pct / 100)

        # SL distance in pips
        sl_distance_price = abs(request.entry_price - request.stop_loss)
        if sl_distance_price < 1e-10 or request.pip_value < 1e-10:
            return SizingResult(
                max_size=0, min_size=request.min_size,
                risk_amount=0, risk_pct=0,
                method_used=request.method,
                adjustments=["Invalid SL distance or pip value"],
            )

        sl_distance_pips = sl_distance_price / request.pip_value

        # Pip value per lot = pip_value * contract_size
        pip_value_per_lot = request.pip_value * request.contract_size

        # Size in lots
        lots = risk_amount / (sl_distance_pips * pip_value_per_lot)

        # Align to lot step
        if request.lot_step > 0:
            lots = math.floor(lots / request.lot_step) * request.lot_step

        # Spread cost adjustment for forex
        spread_cost_per_lot = request.spread_pips * pip_value_per_lot
        total_spread_cost = spread_cost_per_lot * lots
        spread_risk_ratio = total_spread_cost / max(risk_amount, 1e-10)
        if spread_risk_ratio > 0.30:
            # Reduce lots so spread is max 30% of risk budget
            target_lots = (risk_amount * 0.30) / max(spread_cost_per_lot, 1e-10)
            if request.lot_step > 0:
                target_lots = math.floor(target_lots / request.lot_step) * request.lot_step
            lots = min(lots, target_lots)
            adjustments.append(
                f"Lots reduced for spread cost: {request.spread_pips:.1f} pips"
            )

        # Leverage enforcement (our cap, not broker's)
        effective_leverage = self._compute_forex_leverage(
            lots, request.contract_size, request.entry_price, balance
        )
        if effective_leverage > self._max_leverage:
            max_lots_by_leverage = (
                self._max_leverage * balance
                / (request.contract_size * request.entry_price)
            )
            if request.lot_step > 0:
                max_lots_by_leverage = math.floor(
                    max_lots_by_leverage / request.lot_step
                ) * request.lot_step
            lots = min(lots, max_lots_by_leverage)
            adjustments.append(
                f"Capped at {self._max_leverage}x leverage (our limit)"
            )

        # Margin check — never use more than 80% of available margin
        margin_required = self._compute_forex_margin(
            lots, request.contract_size, request.entry_price, request.leverage
        )
        max_margin = balance * 0.80
        if margin_required > max_margin:
            max_lots_by_margin = (
                max_margin * request.leverage
                / (request.contract_size * request.entry_price)
            )
            if request.lot_step > 0:
                max_lots_by_margin = math.floor(
                    max_lots_by_margin / request.lot_step
                ) * request.lot_step
            lots = min(lots, max_lots_by_margin)
            margin_required = self._compute_forex_margin(
                lots, request.contract_size, request.entry_price, request.leverage
            )
            adjustments.append("Capped at 80% margin utilization")

        # Effective risk check
        risk_amount_actual = sl_distance_pips * pip_value_per_lot * lots
        effective_risk = ((risk_amount_actual + total_spread_cost) / balance * 100) if balance > 0 else 0
        if effective_risk > self._max_risk_pct:
            target_lots = (
                (balance * self._max_risk_pct / 100 - total_spread_cost)
                / max(sl_distance_pips * pip_value_per_lot, 1e-10)
            )
            if request.lot_step > 0:
                target_lots = math.floor(target_lots / request.lot_step) * request.lot_step
            lots = max(0, min(lots, target_lots))
            adjustments.append(f"Capped at {self._max_risk_pct}% effective risk")

        # Enforce minimum lot size
        lots = max(lots, 0.0)
        if lots > 0 and lots < request.min_size:
            lots = request.min_size

        # Final calculations
        notional = lots * request.contract_size * request.entry_price
        final_margin = self._compute_forex_margin(
            lots, request.contract_size, request.entry_price, request.leverage
        )
        final_leverage = self._compute_forex_leverage(
            lots, request.contract_size, request.entry_price, balance
        )
        final_risk = sl_distance_pips * pip_value_per_lot * lots

        result = SizingResult(
            max_size=lots,
            min_size=request.min_size,
            risk_amount=final_risk,
            risk_pct=(final_risk / balance * 100) if balance > 0 else 0,
            method_used=request.method,
            spread_cost=spread_cost_per_lot * lots,
            effective_risk_pct=effective_risk,
            adjustments=adjustments,
            lots=lots,
            margin_required=final_margin,
            notional_value=notional,
            effective_leverage=final_leverage,
        )

        log.debug(
            "forex_position_sized",
            symbol=request.symbol,
            lots=lots,
            risk_pct=result.risk_pct,
            margin_required=final_margin,
            leverage=f"{final_leverage:.2f}x",
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

    # -- Forex helpers ------------------------------------------------------

    @staticmethod
    def calculate_lot_size(
        balance: float,
        risk_pct: float,
        stop_loss_pips: float,
        pip_value: float,
        contract_size: float = 100_000.0,
        lot_step: float = 0.01,
    ) -> float:
        """Calculate lot size for a forex position.

        Args:
            balance: Account balance.
            risk_pct: Risk per trade as percentage (e.g. 1.0 = 1%).
            stop_loss_pips: Stop loss distance in pips.
            pip_value: Value of 1 pip in quote currency (e.g. 0.0001 for EUR/USD).
            contract_size: Units per standard lot (default 100,000).
            lot_step: Minimum lot increment (default 0.01).

        Returns:
            Lot size aligned to lot_step.
        """
        if stop_loss_pips <= 0 or pip_value <= 0 or balance <= 0:
            return 0.0
        risk_amount = balance * (risk_pct / 100)
        pip_value_per_lot = pip_value * contract_size
        lots = risk_amount / (stop_loss_pips * pip_value_per_lot)
        if lot_step > 0:
            lots = math.floor(lots / lot_step) * lot_step
        return max(lots, 0.0)

    @staticmethod
    def check_margin(
        lots: float,
        contract_size: float,
        price: float,
        leverage: float,
        free_margin: float,
    ) -> tuple[bool, float]:
        """Check if sufficient margin exists for a forex position.

        Args:
            lots: Position size in lots.
            contract_size: Units per lot.
            price: Current price.
            leverage: Account leverage.
            free_margin: Available margin.

        Returns:
            (ok, required_margin) — ok=True if margin is sufficient.
        """
        notional = lots * contract_size * price
        required = notional / max(leverage, 1.0)
        return free_margin >= required, required

    @staticmethod
    def _compute_forex_margin(
        lots: float, contract_size: float, price: float, leverage: float
    ) -> float:
        """Compute margin required for a forex position."""
        return lots * contract_size * price / max(leverage, 1.0)

    @staticmethod
    def _compute_forex_leverage(
        lots: float, contract_size: float, price: float, balance: float
    ) -> float:
        """Compute effective leverage for a forex position."""
        if balance <= 0:
            return 0.0
        notional = lots * contract_size * price
        return notional / balance

    # -- Helpers ------------------------------------------------------------

    def _compute_risk_amount(
        self,
        request: SizingRequest,
        size: float,
    ) -> float:
        """Compute the monetary risk for a given position size."""
        sl_distance = abs(request.entry_price - request.stop_loss)
        return sl_distance * size
