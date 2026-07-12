"""Execution Agent — routes approved trade decisions to broker connectors.

This agent takes approved trade decisions from the risk agent and submits
them to the appropriate broker connector (MT5, CCXT, etc.). It manages
the full order lifecycle: submission, fill tracking, and error handling.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from alphastack.agents.base import AlphaStackAgent
from alphastack.core.events import EventBus, TradeEvent
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


class ExecutionAgent(AlphaStackAgent):
    """Routes approved trade decisions to broker connectors.

    Responsibilities:
    - Take approved decisions from the risk agent
    - Route orders to the correct broker connector
    - Track order lifecycle (new → filled / rejected / cancelled)
    - Publish trade events to the event bus
    - Handle partial fills and retries
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__(
            name="execution",
            role="executor",
            description="Routes approved trade decisions to broker connectors",
            event_bus=event_bus,
        )
        self._broker_registry: dict[str, Any] = {}

    def system_prompt(self) -> str:
        return (
            "You are the AlphaStack Execution Agent. Your job is to:\n"
            "1. Take approved trade decisions from the risk agent\n"
            "2. Route orders to the appropriate broker (MT5, CCXT/exchange)\n"
            "3. Manage order lifecycle: submit, track fills, handle rejections\n"
            "4. Publish trade events for the reflection agent\n"
            "5. Handle errors gracefully with retries where safe\n"
        )

    def register_broker(self, name: str, connector: Any) -> None:
        """Register a broker connector for order routing."""
        self._broker_registry[name] = connector
        logger.info("execution_agent.broker_registered", broker=name)

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute approved trade decisions."""
        trade_decisions = state.get("trade_decisions", [])
        execution_log = state.get("execution_log", [])

        # Filter to approved decisions only
        approved = [
            d for d in trade_decisions
            if (d.get("status") if isinstance(d, dict) else getattr(d, "status", "")) == "approved"
        ]

        logger.info("execution_agent.start", approved_count=len(approved))

        new_entries = []
        for decision in approved:
            entry = await self._execute_decision(decision)
            new_entries.append(entry)

        execution_log.extend(new_entries)

        # Summary
        filled = sum(1 for e in new_entries if e["status"] == "filled")
        failed = sum(1 for e in new_entries if e["status"] == "failed")
        logger.info("execution_agent.complete", filled=filled, failed=failed)

        return {
            "execution_log": execution_log,
            "pending_orders": [e for e in new_entries if e["status"] in ("pending", "partial")],
            "_confidence": filled / max(len(approved), 1),
        }

    async def _execute_decision(self, decision: Any) -> dict[str, Any]:
        """Execute a single trade decision."""
        # Extract fields from Pydantic model or dict
        if isinstance(decision, dict):
            d_id = decision.get("id", "")
            symbol = decision.get("symbol", "")
            action = decision.get("action", "hold")
            quantity = decision.get("quantity", 0.0)
            price = decision.get("price", 0.0)
            order_type = decision.get("order_type", "market")
            broker = decision.get("broker", "")
            signal = decision.get("signal")
        else:
            d_id = decision.id
            symbol = decision.symbol
            action = decision.action
            quantity = decision.quantity
            price = decision.price
            order_type = decision.order_type
            broker = decision.broker
            signal = decision.signal

        # Skip hold actions
        if action == "hold":
            return self._make_log_entry(
                d_id, symbol, action, quantity, price, "skipped",
                reason="hold action — no execution needed",
            )

        # Determine broker to use
        broker_name = broker or self._select_broker(symbol)
        connector = self._broker_registry.get(broker_name)

        if connector is None:
            logger.warning(
                "execution_agent.no_broker",
                symbol=symbol,
                requested_broker=broker_name,
            )
            # Log as pending — will retry when broker becomes available
            return self._make_log_entry(
                d_id, symbol, action, quantity, price, "pending",
                reason=f"No broker connector for '{broker_name}'",
                broker=broker_name,
            )

        # Submit order via broker connector
        try:
            result = await self._submit_order(
                connector=connector,
                symbol=symbol,
                side=action,
                quantity=quantity,
                price=price,
                order_type=order_type,
            )

            entry = self._make_log_entry(
                d_id, symbol, action, quantity, price,
                status=result.get("status", "filled"),
                broker=broker_name,
                broker_order_id=result.get("order_id"),
                fill_price=result.get("fill_price", price),
            )

            # Publish trade event
            await self._publish_trade_event(entry)

            return entry

        except Exception as exc:
            logger.error(
                "execution_agent.submit_failed",
                symbol=symbol,
                action=action,
                error=str(exc),
                exc_info=True,
            )
            return self._make_log_entry(
                d_id, symbol, action, quantity, price, "failed",
                reason=str(exc),
                broker=broker_name,
            )

    async def _submit_order(
        self,
        connector: Any,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_type: str,
    ) -> dict[str, Any]:
        """Submit an order through a broker connector.

        Tries common connector interfaces:
        1. ``connector.submit_order(...)``
        2. ``connector.create_order(...)``
        3. ``connector.place_order(...)``
        """
        # Try standardised interface first
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
                "fill_price": result.get("average", price),
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

    @staticmethod
    def _select_broker(symbol: str) -> str:
        """Select the best broker for a given symbol.

        Default heuristic:
        - Crypto pairs (contain '/' or 'USDT', 'BTC', 'ETH') → ccxt
        - Everything else → mt5
        """
        crypto_indicators = ["/", "USDT", "BTC", "ETH", "BNB", "SOL", "DOGE"]
        if any(ind in symbol.upper() for ind in crypto_indicators):
            return "ccxt"
        return "mt5"

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
    ) -> dict[str, Any]:
        """Create a standardised execution log entry."""
        return {
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
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _publish_trade_event(self, entry: dict[str, Any]) -> None:
        """Publish a TradeEvent to the event bus."""
        if self._event_bus is None:
            return
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
        try:
            await self._event_bus.publish(event)
        except Exception:
            logger.warning("execution_agent.event_publish_failed", exc_info=True)
