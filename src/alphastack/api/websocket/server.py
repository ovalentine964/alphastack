"""WebSocket Server – real-time streaming of prices, trades, signals."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Channel types
# ---------------------------------------------------------------------------

class Channel(str, Enum):
    PRICES = "prices"
    TRADES = "trades"
    SIGNALS = "signals"
    SYSTEM = "system"


# ---------------------------------------------------------------------------
# Client subscription manager
# ---------------------------------------------------------------------------

@dataclass
class Client:
    """A connected WebSocket client."""

    client_id: str
    ws: WebSocket
    subscriptions: set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)

    async def send_json(self, data: dict[str, Any]) -> None:
        try:
            await self.ws.send_json(data)
        except Exception:
            logger.debug("ws_send_failed", client_id=self.client_id)


class ConnectionManager:
    """Manages WebSocket connections and channel subscriptions."""

    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}
        self._channels: dict[str, set[str]] = defaultdict(set)  # channel → {client_ids}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> Client:
        await ws.accept()
        client_id = str(uuid.uuid4())
        client = Client(client_id=client_id, ws=ws)
        async with self._lock:
            self._clients[client_id] = client
        logger.info("ws_client_connected", client_id=client_id)
        return client

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            client = self._clients.pop(client_id, None)
            if client:
                for ch in client.subscriptions:
                    self._channels[ch].discard(client_id)
        logger.info("ws_client_disconnected", client_id=client_id)

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            client = self._clients.get(client_id)
            if client:
                client.subscriptions.add(channel)
                self._channels[channel].add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            client = self._clients.get(client_id)
            if client:
                client.subscriptions.discard(channel)
                self._channels[channel].discard(client_id)

    async def broadcast(self, channel: str, message: dict[str, Any]) -> int:
        """Broadcast a message to all subscribers of a channel. Returns count sent."""
        sent = 0
        client_ids = list(self._channels.get(channel, set()))
        for cid in client_ids:
            client = self._clients.get(cid)
            if client:
                await client.send_json({"channel": channel, "data": message, "ts": time.time()})
                sent += 1
        return sent

    async def send_to(self, client_id: str, message: dict[str, Any]) -> None:
        client = self._clients.get(client_id)
        if client:
            await client.send_json(message)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def channel_info(self) -> dict[str, int]:
        return {ch: len(cids) for ch, cids in self._channels.items()}


# Global connection manager
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

async def _handle_subscribe(client: Client, data: dict[str, Any]) -> None:
    channels = data.get("channels", [])
    for ch in channels:
        if isinstance(ch, str):
            await manager.subscribe(client.client_id, ch)
    await client.send_json({"type": "subscribed", "channels": channels})


async def _handle_unsubscribe(client: Client, data: dict[str, Any]) -> None:
    channels = data.get("channels", [])
    for ch in channels:
        if isinstance(ch, str):
            await manager.unsubscribe(client.client_id, ch)
    await client.send_json({"type": "unsubscribed", "channels": channels})


async def _handle_ping(client: Client, data: dict[str, Any]) -> None:
    client.last_ping = time.time()
    await client.send_json({"type": "pong", "ts": time.time()})


_HANDLERS: dict[str, Callable] = {
    "subscribe": _handle_subscribe,
    "unsubscribe": _handle_unsubscribe,
    "ping": _handle_ping,
}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Main WebSocket endpoint.

    Protocol (JSON messages):

    Client → Server:
        {"type": "subscribe", "channels": ["prices", "trades", "signals"]}
        {"type": "unsubscribe", "channels": ["prices"]}
        {"type": "ping"}

    Server → Client:
        {"channel": "prices", "data": {...}, "ts": 1234567890.0}
        {"type": "subscribed", "channels": [...]}
        {"type": "pong", "ts": ...}
    """
    client = await manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await client.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "")
            handler = _HANDLERS.get(msg_type)
            if handler:
                await handler(client, msg)
            else:
                await client.send_json({"type": "error", "detail": f"Unknown message type: {msg_type}"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws_error", client_id=client.client_id)
    finally:
        await manager.disconnect(client.client_id)


# ---------------------------------------------------------------------------
# Broadcast helpers (called by data pipeline / trading engine)
# ---------------------------------------------------------------------------

async def broadcast_price(symbol: str, price: float, bid: float, ask: float) -> int:
    """Broadcast a price update to all price subscribers."""
    return await manager.broadcast(Channel.PRICES.value, {
        "symbol": symbol,
        "price": price,
        "bid": bid,
        "ask": ask,
    })


async def broadcast_trade(trade_data: dict[str, Any]) -> int:
    """Broadcast a trade update."""
    return await manager.broadcast(Channel.TRADES.value, trade_data)


async def broadcast_signal(signal_data: dict[str, Any]) -> int:
    """Broadcast a new signal."""
    return await manager.broadcast(Channel.SIGNALS.value, signal_data)


async def broadcast_system(message: str, level: str = "info") -> int:
    """Broadcast a system message."""
    return await manager.broadcast(Channel.SYSTEM.value, {
        "message": message,
        "level": level,
    })
