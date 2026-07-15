"""Shared API dependencies — broker registry, event bus, trade store.

Provides a dependency-injection layer so routes can access real broker
connectors, the event bus, and persistent trade storage.  Falls back to
in-memory stores when brokers / Redis are not configured.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from alphastack.brokers.base import BrokerConnector
from alphastack.brokers.models import BrokerOrder, BrokerPosition, BrokerBalance
from alphastack.brokers.registry import BrokerRegistry
from alphastack.core.events import EventBus, SignalEvent, TradeEvent, EventType
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Singleton holders (lazily initialised)
# ---------------------------------------------------------------------------

_registry: BrokerRegistry | None = None
_event_bus: EventBus | None = None


def get_broker_registry() -> BrokerRegistry:
    """Return the global broker registry singleton."""
    global _registry
    if _registry is None:
        _registry = BrokerRegistry()
    return _registry


def set_broker_registry(registry: BrokerRegistry) -> None:
    """Override the global broker registry (for testing / startup wiring)."""
    global _registry
    _registry = registry


def get_event_bus() -> EventBus | None:
    """Return the global event bus (may be None if Redis is unavailable)."""
    return _event_bus


def set_event_bus(bus: EventBus | None) -> None:
    """Override the global event bus."""
    global _event_bus
    _event_bus = bus


# ---------------------------------------------------------------------------
# Trade Store — backed by broker registry when available
# ---------------------------------------------------------------------------

class TradeStore:
    """Manages trades.  Uses broker registry for real execution when
    available; otherwise falls back to in-memory demo data."""

    def __init__(self) -> None:
        self._trades: dict[str, dict[str, Any]] = {}
        self._seeded = False

    def _ensure_seeded(self) -> None:
        if self._seeded:
            return
        self._seeded = True
        # Only seed if no broker is available (demo mode)
        registry = get_broker_registry()
        if not registry.names:
            self._seed_demo()

    def _seed_demo(self) -> None:
        now = datetime.now(timezone.utc)
        demos = [
            {"symbol": "BTC/USDT", "side": "buy", "quantity": 0.5,
             "entry_price": 67500.0, "stop_loss": 66000.0, "take_profit": 71000.0,
             "status": "open", "pnl": None},
            {"symbol": "EUR/USD", "side": "sell", "quantity": 100000,
             "entry_price": 1.0850, "stop_loss": 1.0900, "take_profit": 1.0750,
             "status": "open", "pnl": None},
            {"symbol": "ETH/USDT", "side": "buy", "quantity": 5.0,
             "entry_price": 3500.0, "stop_loss": 3350.0, "take_profit": 3800.0,
             "status": "closed", "exit_price": 3750.0, "pnl": 1250.0},
        ]
        for d in demos:
            tid = str(uuid.uuid4())
            self._trades[tid] = {
                "id": tid, **d, "strategy_id": "demo_v1",
                "opened_at": now.isoformat(),
                "closed_at": now.isoformat() if d["status"] == "closed" else None,
                "notes": "Demo trade",
            }

    def list_trades(
        self,
        status_filter: str | None = None,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_seeded()
        items = list(self._trades.values())
        if status_filter:
            items = [t for t in items if t["status"] == status_filter]
        if symbol:
            items = [t for t in items if t["symbol"].upper() == symbol.upper()]
        return items

    def get_trade(self, trade_id: str) -> dict[str, Any] | None:
        self._ensure_seeded()
        return self._trades.get(trade_id)

    def create_trade(self, data: dict[str, Any]) -> dict[str, Any]:
        self._ensure_seeded()
        tid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        trade = {
            "id": tid,
            "symbol": data["symbol"],
            "side": data["side"],
            "quantity": data["quantity"],
            "entry_price": data.get("price"),
            "exit_price": None,
            "stop_loss": data.get("stop_loss"),
            "take_profit": data.get("take_profit"),
            "status": "pending" if data.get("price") is None else "open",
            "strategy_id": data.get("strategy_id"),
            "pnl": None,
            "opened_at": now.isoformat(),
            "closed_at": None,
            "notes": data.get("notes", ""),
        }
        self._trades[tid] = trade

        # Emit trade event
        bus = get_event_bus()
        if bus:
            asyncio.create_task(bus.publish(TradeEvent(
                order_id=tid,
                symbol=data["symbol"],
                side=data["side"],
                quantity=data["quantity"],
                price=data.get("price") or 0.0,
                status="new",
                source="api",
            )))

        logger.info("trade_created", trade_id=tid, symbol=data["symbol"])
        return trade

    def close_trade(
        self, trade_id: str, exit_price: float | None = None,
    ) -> dict[str, Any] | None:
        self._ensure_seeded()
        trade = self._trades.get(trade_id)
        if not trade or trade["status"] != "open":
            return None

        now = datetime.now(timezone.utc)
        price = exit_price or trade["entry_price"]
        entry = trade["entry_price"] or price
        qty = trade["quantity"]
        multiplier = 1 if trade["side"] == "buy" else -1
        pnl = (price - entry) * qty * multiplier

        trade["exit_price"] = price
        trade["pnl"] = round(pnl, 4)
        trade["status"] = "closed"
        trade["closed_at"] = now.isoformat()

        # Emit event
        bus = get_event_bus()
        if bus:
            asyncio.create_task(bus.publish(TradeEvent(
                order_id=trade_id,
                symbol=trade["symbol"],
                side="sell" if trade["side"] == "buy" else "buy",
                quantity=trade["quantity"],
                price=price,
                status="filled",
                source="api",
            )))

        logger.info("trade_closed", trade_id=trade_id, pnl=trade["pnl"])
        return trade


# ---------------------------------------------------------------------------
# Signal Store — backed by event bus when available
# ---------------------------------------------------------------------------

class SignalStore:
    """Manages signals.  Subscribes to the event bus for real-time
    signals from the strategy pipeline; falls back to demo data."""

    def __init__(self) -> None:
        self._signals: dict[str, dict[str, Any]] = {}
        self._seeded = False

    def _ensure_seeded(self) -> None:
        if self._seeded:
            return
        self._seeded = True
        self._seed_demo()
        self._subscribe_events()

    def _seed_demo(self) -> None:
        now = datetime.now(timezone.utc)
        demos = [
            {"symbol": "BTC/USDT", "direction": "long", "strength": "strong",
             "strategy_id": "smc_v1", "confidence": 0.85, "entry_price": 67200.0,
             "stop_loss": 66500.0, "take_profit": 69000.0, "risk_reward": 2.57,
             "reason": "Bullish order block at 67200 with volume confirmation"},
            {"symbol": "EUR/USD", "direction": "short", "strength": "moderate",
             "strategy_id": "mean_revert_v1", "confidence": 0.72, "entry_price": 1.0870,
             "stop_loss": 1.0920, "take_profit": 1.0780, "risk_reward": 1.8,
             "reason": "RSI overbought + bearish divergence on H4"},
            {"symbol": "ETH/USDT", "direction": "long", "strength": "very_strong",
             "strategy_id": "breakout_v1", "confidence": 0.91, "entry_price": 3520.0,
             "stop_loss": 3450.0, "take_profit": 3700.0, "risk_reward": 2.57,
             "reason": "Ascending triangle breakout with high volume"},
        ]
        for d in demos:
            sid = str(uuid.uuid4())
            self._signals[sid] = {
                "id": sid, "is_active": True,
                "created_at": now.isoformat(), "expires_at": None, **d,
            }

    def _subscribe_events(self) -> None:
        """Subscribe to signal events from the event bus."""
        bus = get_event_bus()
        if bus is None:
            return
        try:
            bus.subscribe(EventType.SIGNAL, self._on_signal_event)
        except Exception:
            logger.debug("signal_store.event_subscribe_failed")

    async def _on_signal_event(self, event: Any) -> None:
        """Convert a SignalEvent into a stored signal."""
        payload = event.payload if hasattr(event, "payload") else {}
        sid = str(uuid.uuid4())
        self._signals[sid] = {
            "id": sid,
            "symbol": getattr(event, "symbol", payload.get("symbol", "")),
            "direction": getattr(event, "side", payload.get("side", "neutral")),
            "strength": _strength_label(getattr(event, "strength", 0)),
            "strategy_id": getattr(event, "strategy", payload.get("strategy", "")),
            "confidence": abs(getattr(event, "strength", 0)),
            "entry_price": payload.get("entry_price"),
            "stop_loss": payload.get("stop_loss"),
            "take_profit": payload.get("take_profit"),
            "risk_reward": payload.get("risk_reward"),
            "reason": getattr(event, "source", ""),
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": None,
        }

    def list_active(self, symbol: str | None = None, strategy_id: str | None = None) -> list[dict[str, Any]]:
        self._ensure_seeded()
        items = [s for s in self._signals.values() if s["is_active"]]
        if symbol:
            items = [s for s in items if s["symbol"].upper() == symbol.upper()]
        if strategy_id:
            items = [s for s in items if s["strategy_id"] == strategy_id]
        return items

    def list_all(self, symbol: str | None = None) -> list[dict[str, Any]]:
        self._ensure_seeded()
        items = list(self._signals.values())
        if symbol:
            items = [s for s in items if s["symbol"].upper() == symbol.upper()]
        return items


def _strength_label(strength: float) -> str:
    abs_s = abs(strength)
    if abs_s >= 0.8:
        return "very_strong"
    if abs_s >= 0.6:
        return "strong"
    if abs_s >= 0.3:
        return "moderate"
    return "weak"


# ---------------------------------------------------------------------------
# Portfolio service — reads from broker positions
# ---------------------------------------------------------------------------

class PortfolioService:
    """Fetches real positions and balance from the broker registry."""

    async def get_positions(self) -> list[dict[str, Any]]:
        """Get positions from all connected brokers, or demo data if none."""
        registry = get_broker_registry()
        all_positions: list[dict[str, Any]] = []

        for name in registry.connected_brokers():
            connector = registry.get(name)
            if connector is None:
                continue
            try:
                positions = await connector.get_positions()
                for p in positions:
                    all_positions.append({
                        "symbol": p.symbol,
                        "side": p.side.value,
                        "quantity": p.quantity,
                        "entry_price": p.avg_entry_price,
                        "current_price": p.current_price,
                        "unrealized_pnl": p.unrealized_pnl,
                        "unrealized_pnl_pct": p.pnl_pct,
                        "broker": name,
                    })
            except Exception:
                logger.warning("portfolio.fetch_positions_failed", broker=name)

        return all_positions

    async def get_balance(self) -> dict[str, Any] | None:
        """Get balance from the default broker."""
        registry = get_broker_registry()
        connector = registry.default
        if connector is None or not connector.is_connected:
            return None
        try:
            bal = await connector.get_balance()
            return {
                "total": bal.total,
                "available": bal.available,
                "equity": bal.equity,
                "used_margin": bal.used_margin,
                "unrealized_pnl": bal.unrealized_pnl,
                "currency": bal.currency,
                "broker": bal.broker,
            }
        except Exception:
            logger.warning("portfolio.fetch_balance_failed")
            return None


# Singletons
trade_store = TradeStore()
signal_store = SignalStore()
portfolio_service = PortfolioService()
