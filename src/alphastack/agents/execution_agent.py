"""Execution Agent — real implementation with TWAP/VWAP and slippage tracking.

Production features:
- Broker routing via BrokerConnector abstraction
- TWAP (Time-Weighted Average Price) execution algorithm
- VWAP (Volume-Weighted Average Price) execution algorithm
- Slippage tracking and reporting
- Order lifecycle management (submit → fill → track)
- Partial fill handling
"""

from __future__ import annotations

import asyncio
import statistics
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from alphastack.agents.base import AlphaStackAgent
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Execution Algorithm
# ---------------------------------------------------------------------------

ExecutionAlgorithm = Literal["market", "twap", "vwap"]


# ---------------------------------------------------------------------------
# Slippage Tracker
# ---------------------------------------------------------------------------

class SlippageTracker:
    """Tracks execution slippage across all orders."""

    def __init__(self) -> None:
        self._observations: list[dict[str, Any]] = []

    def record(
        self,
        symbol: str,
        side: str,
        expected_price: float,
        fill_price: float,
        quantity: float,
    ) -> dict[str, Any]:
        """Record a fill and compute slippage.

        Returns slippage info dict.
        """
        if expected_price <= 0:
            slippage_abs = 0.0
            slippage_pct = 0.0
            slippage_bps = 0.0
        else:
            if side == "buy":
                slippage_abs = fill_price - expected_price
            else:
                slippage_abs = expected_price - fill_price
            slippage_pct = (slippage_abs / expected_price) * 100
            slippage_bps = slippage_pct * 100

        obs = {
            "symbol": symbol,
            "side": side,
            "expected_price": expected_price,
            "fill_price": fill_price,
            "quantity": quantity,
            "slippage_abs": round(slippage_abs, 8),
            "slippage_pct": round(slippage_pct, 6),
            "slippage_bps": round(slippage_bps, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._observations.append(obs)

        # Keep rolling window
        if len(self._observations) > 500:
            self._observations = self._observations[-500:]

        return obs

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate slippage statistics."""
        if not self._observations:
            return {"count": 0}

        slippages = [o["slippage_bps"] for o in self._observations]
        abs_slippages = [abs(s) for s in slippages]

        return {
            "count": len(slippages),
            "mean_bps": round(statistics.mean(slippages), 2),
            "median_bps": round(statistics.median(slippages), 2),
            "std_bps": round(statistics.stdev(slippages), 2) if len(slippages) > 1 else 0.0,
            "p95_bps": round(sorted(abs_slippages)[int(len(abs_slippages) * 0.95)], 2)
            if len(abs_slippages) >= 20
            else round(max(abs_slippages), 2),
            "max_adverse_bps": round(max(abs_slippages), 2) if abs_slippages else 0.0,
            "positive_slippage_pct": round(
                sum(1 for s in slippages if s > 0) / len(slippages) * 100, 1
            ),
        }

    def get_recent(self, n: int = 20) -> list[dict[str, Any]]:
        """Return the N most recent slippage observations."""
        return self._observations[-n:]


# ---------------------------------------------------------------------------
# TWAP Algorithm
# ---------------------------------------------------------------------------

async def execute_twap(
    connector: Any,
    symbol: str,
    side: str,
    total_quantity: float,
    num_slices: int = 5,
    interval_seconds: float = 10.0,
    price: float | None = None,
) -> list[dict[str, Any]]:
    """Execute a TWAP (Time-Weighted Average Price) order.

    Splits the order into `num_slices` equal parts and executes
    each at a fixed time interval.

    Parameters
    ----------
    connector : BrokerConnector
        Broker connector to use.
    symbol : str
        Trading symbol.
    side : str
        "buy" or "sell".
    total_quantity : float
        Total quantity to execute.
    num_slices : int
        Number of sub-orders.
    interval_seconds : float
        Time between sub-orders.
    price : float | None
        Limit price (None for market orders).

    Returns
    -------
    list[dict]
        List of fill results for each slice.
    """
    slice_qty = total_quantity / num_slices
    fills: list[dict[str, Any]] = []

    for i in range(num_slices):
        if i > 0:
            await asyncio.sleep(interval_seconds)

        try:
            result = await _submit_single_order(
                connector=connector,
                symbol=symbol,
                side=side,
                quantity=slice_qty,
                price=price,
                order_type="limit" if price else "market",
            )
            result["slice_index"] = i
            result["algorithm"] = "twap"
            fills.append(result)

            logger.info(
                "execution.twap_slice",
                symbol=symbol,
                slice=i + 1,
                total=num_slices,
                fill_price=result.get("fill_price", 0),
                status=result.get("status", "unknown"),
            )

        except Exception as exc:
            logger.error(
                "execution.twap_slice_failed",
                symbol=symbol,
                slice=i + 1,
                error=str(exc),
            )
            fills.append({
                "slice_index": i,
                "algorithm": "twap",
                "status": "failed",
                "error": str(exc),
            })

    return fills


# ---------------------------------------------------------------------------
# VWAP Algorithm
# ---------------------------------------------------------------------------

async def execute_vwap(
    connector: Any,
    symbol: str,
    side: str,
    total_quantity: float,
    volume_profile: list[float] | None = None,
    num_slices: int = 5,
    interval_seconds: float = 10.0,
    price: float | None = None,
) -> list[dict[str, Any]]:
    """Execute a VWAP (Volume-Weighted Average Price) order.

    Distributes quantity proportional to expected volume at each time slice.
    Falls back to equal distribution if no volume profile is provided.

    Parameters
    ----------
    connector : BrokerConnector
        Broker connector.
    symbol : str
        Trading symbol.
    side : str
        "buy" or "sell".
    total_quantity : float
        Total quantity.
    volume_profile : list[float] | None
        Expected relative volume at each slice. If None, equal distribution.
    num_slices : int
        Number of sub-orders.
    interval_seconds : float
        Time between sub-orders.
    price : float | None
        Limit price.

    Returns
    -------
    list[dict]
        List of fill results for each slice.
    """
    # Compute volume-weighted quantities
    if volume_profile and len(volume_profile) == num_slices:
        total_vol = sum(volume_profile)
        quantities = [(v / total_vol) * total_quantity for v in volume_profile]
    else:
        # Equal distribution fallback
        quantities = [total_quantity / num_slices] * num_slices

    fills: list[dict[str, Any]] = []

    for i in range(num_slices):
        if i > 0:
            await asyncio.sleep(interval_seconds)

        slice_qty = quantities[i]
        if slice_qty <= 0:
            continue

        try:
            result = await _submit_single_order(
                connector=connector,
                symbol=symbol,
                side=side,
                quantity=slice_qty,
                price=price,
                order_type="limit" if price else "market",
            )
            result["slice_index"] = i
            result["algorithm"] = "vwap"
            result["volume_weight"] = (
                volume_profile[i] / sum(volume_profile) if volume_profile else 1.0 / num_slices
            )
            fills.append(result)

            logger.info(
                "execution.vwap_slice",
                symbol=symbol,
                slice=i + 1,
                total=num_slices,
                quantity=round(slice_qty, 6),
                fill_price=result.get("fill_price", 0),
            )

        except Exception as exc:
            logger.error(
                "execution.vwap_slice_failed",
                symbol=symbol,
                slice=i + 1,
                error=str(exc),
            )
            fills.append({
                "slice_index": i,
                "algorithm": "vwap",
                "status": "failed",
                "error": str(exc),
            })

    return fills


# ---------------------------------------------------------------------------
# Single order submission helper
# ---------------------------------------------------------------------------

async def _submit_single_order(
    connector: Any,
    symbol: str,
    side: str,
    quantity: float,
    price: float | None = None,
    order_type: str = "market",
) -> dict[str, Any]:
    """Submit a single order through a broker connector."""
    # Try standardised interface
    if hasattr(connector, "submit_order"):
        return await connector.submit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

    # CCXT-style interface
    if hasattr(connector, "create_order"):
        result = await connector.create_order(
            symbol=symbol,
            type=order_type,
            side=side,
            amount=quantity,
            price=price if order_type != "market" else None,
        )
        return {
            "status": "filled",
            "order_id": result.get("id", ""),
            "fill_price": result.get("average", price or 0),
            "filled_quantity": result.get("filled", quantity),
        }

    # Fallback
    if hasattr(connector, "place_order"):
        return await connector.place_order(
            symbol=symbol, side=side, quantity=quantity,
            price=price, order_type=order_type,
        )

    raise NotImplementedError(
        f"Broker connector {type(connector).__name__} has no recognised order interface"
    )


# ---------------------------------------------------------------------------
# Execution Agent
# ---------------------------------------------------------------------------

class ExecutionAgent(AlphaStackAgent):
    """Routes approved trade decisions to broker connectors.

    Upgraded v2.0 features:
    - TWAP/VWAP execution algorithms for large orders
    - Slippage tracking and reporting
    - Order lifecycle management
    - Smart algorithm selection based on order size
    """

    # Order size thresholds for algorithm selection (as fraction of avg volume)
    _TWAP_THRESHOLD: float = 0.01   # 1% of avg volume → use TWAP
    _VWAP_THRESHOLD: float = 0.05   # 5% of avg volume → use VWAP

    def __init__(self, event_bus: Any | None = None) -> None:
        super().__init__(
            name="execution",
            role="executor",
            description="Routes approved decisions with TWAP/VWAP and slippage tracking",
            event_bus=event_bus,
            timeout=60.0,  # TWAP can take a while
            max_retries=2,
            cb_failure_threshold=5,
        )
        self._broker_registry: dict[str, Any] = {}
        self._slippage_tracker = SlippageTracker()

    def system_prompt(self) -> str:
        return (
            "You are the AlphaStack Execution Agent. Your job is to:\n"
            "1. Take approved trade decisions from the risk agent\n"
            "2. Select optimal execution algorithm (market, TWAP, VWAP)\n"
            "3. Route orders to the appropriate broker\n"
            "4. Track slippage vs expected price\n"
            "5. Manage order lifecycle: submit, track fills, handle rejections\n"
        )

    def register_broker(self, name: str, connector: Any) -> None:
        """Register a broker connector for order routing."""
        self._broker_registry[name] = connector
        logger.info("execution_agent.broker_registered", broker=name)

    # ------------------------------------------------------------------
    # Algorithm selection
    # ------------------------------------------------------------------

    def _select_algorithm(
        self,
        quantity: float,
        price: float,
        avg_volume: float = 0.0,
    ) -> str:
        """Select execution algorithm based on order size relative to volume.

        - Small orders (< 1% of avg volume) → market
        - Medium orders (1-5%) → TWAP
        - Large orders (> 5%) → VWAP
        """
        if avg_volume <= 0 or price <= 0:
            return "market"  # insufficient data → simple market order

        order_value = quantity * price
        volume_ratio = order_value / (avg_volume * price) if avg_volume * price > 0 else 0

        if volume_ratio >= self._VWAP_THRESHOLD:
            return "vwap"
        elif volume_ratio >= self._TWAP_THRESHOLD:
            return "twap"
        return "market"

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute approved trade decisions."""
        trade_decisions = state.get("trade_decisions", [])
        execution_log = state.get("execution_log", [])
        market_data = state.get("market_data", {})

        # Filter to approved decisions
        approved = [
            d for d in trade_decisions
            if (d.get("status") if isinstance(d, dict) else getattr(d, "status", "")) == "approved"
        ]

        logger.info("execution_agent.start", approved_count=len(approved))

        new_entries: list[dict[str, Any]] = []

        for decision in approved:
            entry = await self._execute_decision(decision, market_data)
            new_entries.append(entry)

        execution_log.extend(new_entries)

        # Compute slippage stats
        slippage_stats = self._slippage_tracker.get_stats()

        filled = sum(1 for e in new_entries if e.get("status") == "filled")
        failed = sum(1 for e in new_entries if e.get("status") == "failed")
        partial = sum(1 for e in new_entries if e.get("status") == "partial")

        logger.info(
            "execution_agent.complete",
            filled=filled,
            failed=failed,
            partial=partial,
            slippage_stats=slippage_stats,
        )

        return {
            "execution_log": execution_log,
            "pending_orders": [e for e in new_entries if e.get("status") in ("pending", "partial")],
            "slippage_stats": slippage_stats,
            "_confidence": filled / max(len(approved), 1),
        }

    # ------------------------------------------------------------------
    # Decision execution
    # ------------------------------------------------------------------

    async def _execute_decision(
        self,
        decision: Any,
        market_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single trade decision."""
        # Extract fields
        if isinstance(decision, dict):
            d_id = decision.get("id", "")
            symbol = decision.get("symbol", "")
            action = decision.get("action", "hold")
            quantity = decision.get("quantity", 0.0)
            price = decision.get("price", 0.0)
            order_type = decision.get("order_type", "market")
            broker = decision.get("broker", "")
            signal = decision.get("signal", {})
        else:
            d_id = decision.id
            symbol = decision.symbol
            action = decision.action
            quantity = decision.quantity
            price = decision.price
            order_type = decision.order_type
            broker = decision.broker
            signal = decision.signal if hasattr(decision, "signal") else {}

        # Skip hold actions
        if action == "hold":
            return self._make_log_entry(
                d_id, symbol, action, quantity, price, "skipped",
                reason="hold action — no execution needed",
            )

        # Select broker
        broker_name = broker or self._select_broker(symbol)
        connector = self._broker_registry.get(broker_name)

        if connector is None:
            logger.warning("execution_agent.no_broker", symbol=symbol, broker=broker_name)
            return self._make_log_entry(
                d_id, symbol, action, quantity, price, "pending",
                reason=f"No broker connector for '{broker_name}'",
                broker=broker_name,
            )

        # Select execution algorithm
        avg_volume = market_data.get("avg_volume", 0.0)
        algo = self._select_algorithm(quantity, price, avg_volume)

        try:
            if algo == "twap" and quantity > 0:
                fills = await execute_twap(
                    connector=connector,
                    symbol=symbol,
                    side=action,
                    total_quantity=quantity,
                    num_slices=5,
                    interval_seconds=10.0,
                    price=price if order_type == "limit" else None,
                )
                return self._aggregate_fills(d_id, symbol, action, quantity, price, fills, broker_name, "twap")

            elif algo == "vwap" and quantity > 0:
                volume_profile = market_data.get("volume_profile", None)
                fills = await execute_vwap(
                    connector=connector,
                    symbol=symbol,
                    side=action,
                    total_quantity=quantity,
                    volume_profile=volume_profile,
                    num_slices=5,
                    interval_seconds=10.0,
                    price=price if order_type == "limit" else None,
                )
                return self._aggregate_fills(d_id, symbol, action, quantity, price, fills, broker_name, "vwap")

            else:
                # Simple market/limit order
                result = await _submit_single_order(
                    connector=connector,
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    price=price if order_type != "market" else None,
                    order_type=order_type,
                )

                fill_price = result.get("fill_price", price)
                slippage = self._slippage_tracker.record(
                    symbol=symbol,
                    side=action,
                    expected_price=price,
                    fill_price=fill_price,
                    quantity=quantity,
                )

                entry = self._make_log_entry(
                    d_id, symbol, action, quantity, price,
                    status=result.get("status", "filled"),
                    broker=broker_name,
                    broker_order_id=result.get("order_id", ""),
                    fill_price=fill_price,
                    algorithm="market",
                    slippage=slippage,
                )

                await self._publish_trade_event(entry)
                return entry

        except Exception as exc:
            logger.error(
                "execution_agent.submit_failed",
                symbol=symbol,
                action=action,
                algorithm=algo,
                error=str(exc),
                exc_info=True,
            )
            return self._make_log_entry(
                d_id, symbol, action, quantity, price, "failed",
                reason=str(exc),
                broker=broker_name,
                algorithm=algo,
            )

    # ------------------------------------------------------------------
    # Fill aggregation (for TWAP/VWAP)
    # ------------------------------------------------------------------

    def _aggregate_fills(
        self,
        decision_id: str,
        symbol: str,
        side: str,
        total_qty: float,
        expected_price: float,
        fills: list[dict[str, Any]],
        broker: str,
        algorithm: str,
    ) -> dict[str, Any]:
        """Aggregate multiple slice fills into a single execution log entry."""
        successful_fills = [f for f in fills if f.get("status") == "filled"]
        failed_fills = [f for f in fills if f.get("status") == "failed"]

        if not successful_fills:
            return self._make_log_entry(
                decision_id, symbol, side, total_qty, expected_price, "failed",
                reason=f"All {algorithm.upper()} slices failed",
                broker=broker,
                algorithm=algorithm,
            )

        # Volume-weighted average fill price
        total_filled_qty = sum(f.get("filled_quantity", f.get("quantity", 0)) for f in successful_fills)
        if total_filled_qty > 0:
            vwap_fill = sum(
                f.get("fill_price", 0) * f.get("filled_quantity", f.get("quantity", 0))
                for f in successful_fills
            ) / total_filled_qty
        else:
            vwap_fill = expected_price

        # Slippage on VWAP fill
        slippage = self._slippage_tracker.record(
            symbol=symbol,
            side=side,
            expected_price=expected_price,
            fill_price=vwap_fill,
            quantity=total_filled_qty,
        )

        status = "filled" if not failed_fills else "partial"

        entry = self._make_log_entry(
            decision_id, symbol, side, total_qty, expected_price,
            status=status,
            broker=broker,
            fill_price=vwap_fill,
            algorithm=algorithm,
            slippage=slippage,
            slices_total=len(fills),
            slices_filled=len(successful_fills),
            slices_failed=len(failed_fills),
        )

        # Also log individual slice slippages
        for f in successful_fills:
            self._slippage_tracker.record(
                symbol=symbol,
                side=side,
                expected_price=expected_price,
                fill_price=f.get("fill_price", expected_price),
                quantity=f.get("filled_quantity", f.get("quantity", 0)),
            )

        return entry

    # ------------------------------------------------------------------
    # Broker selection
    # ------------------------------------------------------------------

    @staticmethod
    def _select_broker(symbol: str) -> str:
        """Select the best broker for a given symbol."""
        crypto_indicators = ["/", "USDT", "BTC", "ETH", "BNB", "SOL", "DOGE"]
        if any(ind in symbol.upper() for ind in crypto_indicators):
            return "ccxt"
        return "mt5"

    # ------------------------------------------------------------------
    # Log entry helper
    # ------------------------------------------------------------------

    @staticmethod
    def _make_log_entry(
        decision_id: str,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        status: str,
        reason: str = "",
        broker: str = "",
        broker_order_id: str = "",
        fill_price: float = 0.0,
        algorithm: str = "market",
        slippage: dict[str, Any] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """Create a standardised execution log entry."""
        entry: dict[str, Any] = {
            "id": uuid.uuid4().hex[:12],
            "decision_id": decision_id,
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "price": price,
            "fill_price": fill_price or price,
            "status": status,
            "reason": reason,
            "broker": broker,
            "broker_order_id": broker_order_id,
            "algorithm": algorithm,
            "slippage": slippage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        entry.update(extra)
        return entry

    # ------------------------------------------------------------------
    # Event publishing
    # ------------------------------------------------------------------

    async def _publish_trade_event(self, entry: dict[str, Any]) -> None:
        """Publish a TradeEvent to the event bus."""
        if self._event_bus is None:
            return
        try:
            from alphastack.core.events import TradeEvent
            event = TradeEvent(
                source=self.agent_id,
                order_id=entry.get("broker_order_id", ""),
                symbol=entry["symbol"],
                side=entry["action"],
                quantity=entry["quantity"],
                price=entry.get("fill_price", entry["price"]),
                order_type="market",
                status=entry["status"],
            )
            await self._event_bus.publish(event)
        except Exception:
            logger.warning("execution_agent.event_publish_failed", exc_info=True)
