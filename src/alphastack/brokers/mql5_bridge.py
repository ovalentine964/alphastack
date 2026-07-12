"""MQL5 Bridge for AlphaStack.

ZeroMQ-based bridge between Python trading engine and MT5 Expert Advisor.
Handles signal sending, trade status receiving, and heartbeat management.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class MT5Action(Enum):
    """MT5 trade actions."""
    BUY = "buy"
    SELL = "sell"
    BUY_LIMIT = "buy_limit"
    SELL_LIMIT = "sell_limit"
    BUY_STOP = "buy_stop"
    SELL_STOP = "sell_stop"
    CLOSE = "close"
    MODIFY = "modify"
    CLOSE_ALL = "close_all"


@dataclass
class MT5Signal:
    """Signal to send to MT5 EA."""
    action: MT5Action
    symbol: str
    lots: float = 0.01
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    magic: int = 20260713
    comment: str = "AlphaStack"
    ticket: int = 0  # For modify/close

    def to_json(self) -> str:
        """Convert signal to JSON for MT5."""
        return json.dumps({
            "action": self.action.value,
            "symbol": self.symbol,
            "lots": self.lots,
            "price": self.price,
            "sl": self.sl,
            "tp": self.tp,
            "magic": self.magic,
            "comment": self.comment,
            "ticket": self.ticket,
        })


@dataclass
class MT5TradeStatus:
    """Trade status received from MT5."""
    ticket: int
    symbol: str
    action: str
    lots: float
    open_price: float
    current_price: float
    sl: float
    tp: float
    profit: float
    swap: float
    commission: float
    magic: int
    comment: str
    timestamp: float


@dataclass
class MT5AccountInfo:
    """Account info received from MT5."""
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    leverage: int
    currency: str


@dataclass
class MQL5BridgeConfig:
    """Configuration for MQL5 Bridge."""
    zmq_address: str = "tcp://*:5555"
    heartbeat_interval: float = 5.0
    heartbeat_timeout: float = 15.0
    reconnect_interval: float = 3.0
    max_retries: int = 10
    magic_number: int = 20260713


class MQL5Bridge:
    """ZeroMQ bridge between Python and MT5 Expert Advisor.

    Usage:
        bridge = MQL5Bridge(config)
        await bridge.start()

        # Send a signal
        signal = MT5Signal(action=MT5Action.BUY, symbol="EURUSD", lots=0.01, sl=1.085, tp=1.095)
        await bridge.send_signal(signal)

        # Get account info
        account = await bridge.get_account_info()

        # Get open positions
        positions = await bridge.get_positions()
    """

    def __init__(self, config: Optional[MQL5BridgeConfig] = None):
        self.config = config or MQL5BridgeConfig()
        self._running = False
        self._connected = False
        self._last_heartbeat: float = 0
        self._socket = None
        self._positions: dict[int, MT5TradeStatus] = {}
        self._account_info: Optional[MT5AccountInfo] = None
        self._signal_callbacks: list[Callable] = []
        self._trade_callbacks: list[Callable] = []
        logger.info(f"MQL5Bridge initialized on {self.config.zmq_address}")

    async def start(self) -> None:
        """Start the ZeroMQ server."""
        try:
            import zmq
            import zmq.asyncio

            self._context = zmq.asyncio.Context()
            self._socket = self._context.socket(zmq.PAIR)
            self._socket.bind(self.config.zmq_address)
            self._running = True
            logger.info(f"MQL5 Bridge started on {self.config.zmq_address}")

            # Start background tasks
            asyncio.create_task(self._receive_loop())
            asyncio.create_task(self._heartbeat_loop())

        except ImportError:
            logger.warning("pyzmq not installed. MQL5 bridge disabled. Install with: pip install pyzmq")
            self._running = False

    async def stop(self) -> None:
        """Stop the bridge."""
        self._running = False
        self._connected = False
        if self._socket:
            self._socket.close()
        if hasattr(self, '_context'):
            self._context.term()
        logger.info("MQL5 Bridge stopped")

    @property
    def is_connected(self) -> bool:
        """Check if EA is connected."""
        return self._connected

    async def send_signal(self, signal: MT5Signal) -> bool:
        """Send a trade signal to MT5 EA."""
        if not self._running or not self._socket:
            logger.warning("Bridge not running")
            return False

        try:
            message = signal.to_json()
            await self._socket.send_string(message)
            logger.info(f"Signal sent: {signal.action.value} {signal.symbol} {signal.lots}")
            return True
        except Exception as e:
            logger.error(f"Failed to send signal: {e}")
            return False

    async def get_account_info(self) -> Optional[MT5AccountInfo]:
        """Get MT5 account info."""
        if not self._connected:
            return None
        # Request account info
        await self._socket.send_string(json.dumps({"action": "get_account"}))
        # Wait for response (handled in receive loop)
        return self._account_info

    async def get_positions(self) -> dict[int, MT5TradeStatus]:
        """Get open positions from MT5."""
        if not self._connected:
            return {}
        await self._socket.send_string(json.dumps({"action": "get_positions"}))
        return self._positions.copy()

    async def close_position(self, ticket: int) -> bool:
        """Close a specific position."""
        signal = MT5Signal(
            action=MT5Action.CLOSE,
            symbol="",
            ticket=ticket,
        )
        return await self.send_signal(signal)

    async def close_all_positions(self) -> bool:
        """Emergency close all positions."""
        signal = MT5Signal(
            action=MT5Action.CLOSE_ALL,
            symbol="",
        )
        return await self.send_signal(signal)

    async def modify_position(self, ticket: int, sl: float, tp: float) -> bool:
        """Modify SL/TP of a position."""
        signal = MT5Signal(
            action=MT5Action.MODIFY,
            symbol="",
            sl=sl,
            tp=tp,
            ticket=ticket,
        )
        return await self.send_signal(signal)

    def on_trade_update(self, callback: Callable) -> None:
        """Register callback for trade updates."""
        self._trade_callbacks.append(callback)

    def on_signal(self, callback: Callable) -> None:
        """Register callback for signals from EA."""
        self._signal_callbacks.append(callback)

    async def _receive_loop(self) -> None:
        """Background loop to receive messages from EA."""
        while self._running:
            try:
                if self._socket:
                    message = await self._socket.recv_string()
                    data = json.loads(message)
                    await self._handle_message(data)
            except Exception as e:
                if self._running:
                    logger.error(f"Receive error: {e}")
                await asyncio.sleep(0.1)

    async def _handle_message(self, data: dict) -> None:
        """Handle incoming message from EA."""
        msg_type = data.get("type", "")

        if msg_type == "heartbeat":
            self._connected = True
            self._last_heartbeat = time.time()

        elif msg_type == "account_info":
            self._account_info = MT5AccountInfo(**data)

        elif msg_type == "position":
            ticket = data.get("ticket", 0)
            self._positions[ticket] = MT5TradeStatus(**data)
            for cb in self._trade_callbacks:
                await cb(self._positions[ticket])

        elif msg_type == "positions":
            self._positions.clear()
            for pos_data in data.get("positions", []):
                ticket = pos_data.get("ticket", 0)
                self._positions[ticket] = MT5TradeStatus(**pos_data)

        elif msg_type == "trade_result":
            logger.info(f"Trade result: {data}")

        for cb in self._signal_callbacks:
            await cb(data)

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat to EA and check connection."""
        while self._running:
            try:
                if self._socket:
                    await self._socket.send_string(json.dumps({"type": "heartbeat"}))

                # Check if EA is still connected
                if self._connected and time.time() - self._last_heartbeat > self.config.heartbeat_timeout:
                    self._connected = False
                    logger.warning("MT5 EA disconnected (heartbeat timeout)")

                await asyncio.sleep(self.config.heartbeat_interval)

            except Exception as e:
                if self._running:
                    logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self.config.reconnect_interval)

    def get_status(self) -> dict:
        """Get bridge status."""
        return {
            "running": self._running,
            "connected": self._connected,
            "positions": len(self._positions),
            "account_info": self._account_info is not None,
            "zmq_address": self.config.zmq_address,
            "last_heartbeat": self._last_heartbeat,
        }


# Convenience function
def create_bridge(address: str = "tcp://*:5555") -> MQL5Bridge:
    """Create a configured MQL5 bridge."""
    config = MQL5BridgeConfig(zmq_address=address)
    return MQL5Bridge(config)
