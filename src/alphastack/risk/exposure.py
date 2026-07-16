"""Exposure Manager — total, per-pair, per-session, and leverage limits.

Tracks all open positions and enforces hard limits on:
- Total portfolio exposure
- Per-pair concentration
- Per-session risk budget
- Leverage caps
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Exposure tracking
# ---------------------------------------------------------------------------

class PositionExposure(BaseModel):
    """Tracked position for exposure calculations."""
    symbol: str
    direction: str  # long | short
    size: float  # lots (forex) or quantity (crypto)
    entry_price: float
    broker: str = ""              # which broker: binance, oanda, mt5, etc.
    asset_type: str = "crypto"    # "crypto" or "forex"
    contract_size: float = 1.0    # units per lot (100_000 for forex, 1 for crypto)
    margin_used: float = 0.0      # margin consumed by this position
    session: str = ""
    strategy_id: str = ""
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExposureSnapshot(BaseModel):
    """Point-in-time exposure summary."""
    total_positions: int = 0
    total_exposure_value: float = 0.0
    total_notional: float = 0.0
    effective_leverage: float = 0.0
    per_pair_exposure: dict[str, float] = Field(default_factory=dict)
    per_session_exposure: dict[str, float] = Field(default_factory=dict)
    per_direction_exposure: dict[str, float] = Field(default_factory=dict)
    # Cross-broker aggregation
    per_broker_exposure: dict[str, float] = Field(default_factory=dict)
    total_notional_usd: float = 0.0
    total_margin_used: float = 0.0
    per_asset_type_exposure: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Exposure Manager
# ---------------------------------------------------------------------------

class ExposureManager:
    """Tracks and enforces exposure limits across the portfolio.

    Hard limits:
    - Max open positions
    - Max per-pair exposure (% of account)
    - Max per-session exposure
    - Max leverage
    - Max cross-broker total exposure (USD-normalized)
    """

    def __init__(
        self,
        max_open_positions: int = 10,
        max_per_pair_pct: float = 20.0,
        max_per_session_pct: float = 40.0,
        max_leverage: float = 2.0,
        max_total_exposure_usd: float = 0.0,
    ) -> None:
        self._max_positions = max_open_positions
        self._max_per_pair_pct = max_per_pair_pct
        self._max_per_session_pct = max_per_session_pct
        self._max_leverage = max_leverage
        self._max_total_exposure_usd = max_total_exposure_usd
        self._positions: list[PositionExposure] = []

    # -- Position management ------------------------------------------------

    def add_position(self, position: PositionExposure) -> None:
        """Register an open position."""
        self._positions.append(position)
        log.debug(
            "exposure_position_added",
            symbol=position.symbol,
            direction=position.direction,
            size=position.size,
            total=len(self._positions),
        )

    def remove_position(self, symbol: str, strategy_id: str = "") -> None:
        """Remove a closed position."""
        before = len(self._positions)
        if strategy_id:
            self._positions = [
                p for p in self._positions
                if not (p.symbol == symbol and p.strategy_id == strategy_id)
            ]
        else:
            # Remove the first matching symbol
            for i, p in enumerate(self._positions):
                if p.symbol == symbol:
                    self._positions.pop(i)
                    break
        if len(self._positions) < before:
            log.debug("exposure_position_removed", symbol=symbol, total=len(self._positions))

    def clear(self) -> None:
        """Remove all tracked positions."""
        self._positions.clear()

    # -- Exposure checks ----------------------------------------------------

    def check_add_position(
        self,
        symbol: str,
        direction: str,
        size: float,
        price: float,
        balance: float,
        session: str = "",
        broker: str = "",
        asset_type: str = "crypto",
        contract_size: float = 1.0,
    ) -> tuple[bool, str]:
        """Check if a new position can be added within exposure limits.

        For forex, notional = size (lots) × contract_size × price.
        For crypto, notional = size (quantity) × price.

        Returns:
            (ok, reason) — ok=True if allowed.
        """
        # Compute correct notional value
        notional = self._compute_notional(size, price, contract_size)

        # Check max open positions
        if len(self._positions) >= self._max_positions:
            return False, (
                f"Max open positions reached: "
                f"{len(self._positions)} >= {self._max_positions}"
            )

        # Check per-pair exposure
        pair_exposure = self._pair_exposure(symbol) + notional
        pair_pct = (pair_exposure / balance * 100) if balance > 0 else 0
        if pair_pct > self._max_per_pair_pct:
            return False, (
                f"Per-pair exposure for {symbol}: "
                f"{pair_pct:.1f}% > {self._max_per_pair_pct}%"
            )

        # Check per-session exposure
        if session:
            session_exposure = self._session_exposure(session) + notional
            session_pct = (session_exposure / balance * 100) if balance > 0 else 0
            if session_pct > self._max_per_session_pct:
                return False, (
                    f"Session '{session}' exposure: "
                    f"{session_pct:.1f}% > {self._max_per_session_pct}%"
                )

        # Check leverage
        new_total = self._total_notional() + notional
        leverage = (new_total / balance) if balance > 0 else 0
        if leverage > self._max_leverage:
            return False, (
                f"Effective leverage {leverage:.2f}x > {self._max_leverage}x"
            )

        # Check cross-broker total exposure (USD-normalized)
        if self._max_total_exposure_usd > 0:
            total_usd = self._total_notional_usd() + notional
            if total_usd > self._max_total_exposure_usd:
                return False, (
                    f"Total cross-broker exposure ${total_usd:,.0f} "
                    f"> limit ${self._max_total_exposure_usd:,.0f}"
                )

        return True, ""

    # -- Exposure calculations ----------------------------------------------

    @staticmethod
    def _compute_notional(
        size: float, price: float, contract_size: float = 1.0
    ) -> float:
        """Compute notional value, accounting for forex lot sizing.

        For crypto: notional = quantity × price
        For forex:  notional = lots × contract_size × price
        """
        return size * contract_size * price

    def _pair_exposure(self, symbol: str) -> float:
        """Total notional exposure for a specific pair."""
        return sum(
            self._compute_notional(p.size, p.entry_price, p.contract_size)
            for p in self._positions if p.symbol == symbol
        )

    def _session_exposure(self, session: str) -> float:
        """Total notional exposure for a specific session."""
        return sum(
            self._compute_notional(p.size, p.entry_price, p.contract_size)
            for p in self._positions if p.session == session
        )

    def _total_notional(self) -> float:
        """Total notional value of all open positions."""
        return sum(
            self._compute_notional(p.size, p.entry_price, p.contract_size)
            for p in self._positions
        )

    def _broker_exposure(self, broker: str) -> float:
        """Total notional exposure for a specific broker."""
        return sum(
            self._compute_notional(p.size, p.entry_price, p.contract_size)
            for p in self._positions if p.broker == broker
        )

    def _total_notional_usd(self) -> float:
        """Total USD-normalized notional across all brokers.

        For crypto positions with USDT quote, notional is already in USD.
        For forex positions, notional is in quote currency — needs conversion.
        This method returns the raw total; callers should provide USD rates.
        """
        return self._total_notional()

    def get_snapshot(self, balance: float = 0.0) -> ExposureSnapshot:
        """Get current exposure snapshot with cross-broker aggregation."""
        per_pair: dict[str, float] = {}
        per_session: dict[str, float] = {}
        per_direction: dict[str, float] = {}
        per_broker: dict[str, float] = {}
        per_asset_type: dict[str, float] = {}
        total_margin = 0.0

        for p in self._positions:
            notional = self._compute_notional(p.size, p.entry_price, p.contract_size)
            per_pair[p.symbol] = per_pair.get(p.symbol, 0) + notional
            if p.session:
                per_session[p.session] = per_session.get(p.session, 0) + notional
            per_direction[p.direction] = per_direction.get(p.direction, 0) + notional
            if p.broker:
                per_broker[p.broker] = per_broker.get(p.broker, 0) + notional
            per_asset_type[p.asset_type] = per_asset_type.get(p.asset_type, 0) + notional
            total_margin += p.margin_used

        total_notional = sum(per_pair.values())
        leverage = (total_notional / balance) if balance > 0 else 0

        return ExposureSnapshot(
            total_positions=len(self._positions),
            total_exposure_value=total_notional,
            total_notional=total_notional,
            effective_leverage=leverage,
            per_pair_exposure=per_pair,
            per_session_exposure=per_session,
            per_direction_exposure=per_direction,
            per_broker_exposure=per_broker,
            total_notional_usd=total_notional,
            total_margin_used=total_margin,
            per_asset_type_exposure=per_asset_type,
        )

    # -- Status -------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return exposure manager status with cross-broker breakdown."""
        snapshot = self.get_snapshot()
        return {
            "total_positions": snapshot.total_positions,
            "total_notional": round(snapshot.total_notional, 2),
            "total_notional_usd": round(snapshot.total_notional_usd, 2),
            "total_margin_used": round(snapshot.total_margin_used, 2),
            "effective_leverage": round(snapshot.effective_leverage, 2),
            "per_pair_exposure": {
                k: round(v, 2) for k, v in snapshot.per_pair_exposure.items()
            },
            "per_session_exposure": {
                k: round(v, 2) for k, v in snapshot.per_session_exposure.items()
            },
            "per_direction_exposure": {
                k: round(v, 2) for k, v in snapshot.per_direction_exposure.items()
            },
            "per_broker_exposure": {
                k: round(v, 2) for k, v in snapshot.per_broker_exposure.items()
            },
            "per_asset_type_exposure": {
                k: round(v, 2) for k, v in snapshot.per_asset_type_exposure.items()
            },
            "limits": {
                "max_positions": self._max_positions,
                "max_per_pair_pct": self._max_per_pair_pct,
                "max_per_session_pct": self._max_per_session_pct,
                "max_leverage": self._max_leverage,
                "max_total_exposure_usd": self._max_total_exposure_usd,
            },
        }
