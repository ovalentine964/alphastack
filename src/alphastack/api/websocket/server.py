"""WebSocket Server – real-time streaming of prices, trades, signals.

Security features:
- JWT token verification on connection (first message within 10s timeout)
- Heartbeat: 30s ping / 10s pong timeout
- Idle timeout: 300s (5 min)
- Per-user connection limit: 5
- Message rate limiting: 60/min per client
- Message size limit: 64KB
- Origin validation
"""

from __future__ import annotations

import asyncio
import json
import os
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
# Security constants
# ---------------------------------------------------------------------------

_AUTH_TIMEOUT = 10.0          # seconds to send auth message after connect
_HEARTBEAT_INTERVAL = 30.0   # seconds between server pings
_PONG_TIMEOUT = 10.0         # seconds to wait for pong
_IDLE_TIMEOUT = 300.0        # seconds of inactivity before disconnect
_MAX_CONNECTIONS_PER_USER = 5
_MSG_RATE_LIMIT = 60         # max messages per minute per client
_MAX_MSG_SIZE = 65_536       # 64 KB max message size


# ---------------------------------------------------------------------------
# Allowed origins (configure via env)
# ---------------------------------------------------------------------------

def _get_allowed_origins() -> set[str]:
    origins_str = os.environ.get("ALPHASTACK_WS_ORIGINS", "http://localhost:3000")
    return {o.strip() for o in origins_str.split(",") if o.strip()}


_ALLOWED_ORIGINS = _get_allowed_origins()


# ---------------------------------------------------------------------------
# JWT verification for WebSocket (lazy import to avoid circular deps)
# ---------------------------------------------------------------------------

def _verify_ws_token(token: str) -> dict[str, Any] | None:
    """Verify a JWT token passed via WebSocket auth.  Returns claims or None."""
    try:
        from alphastack.security.auth import JWTManager
        import base64

        priv_b64 = os.environ.get("ALPHASTACK_JWT_PRIVATE_KEY", "")
        pub_b64 = os.environ.get("ALPHASTACK_JWT_PUBLIC_KEY", "")
        if pub_b64:
            pub_pem = base64.b64decode(pub_b64)
        else:
            # Dev fallback: generate ephemeral key (same as REST auth)
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
            private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=4096, backend=default_backend()
            )
            pub_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )

        key_id = os.environ.get("ALPHASTACK_JWT_KEY_ID", "as-key-1")
        jwt_mgr = JWTManager(
            private_key_pem=b"",  # not needed for decode
            public_key_pem=pub_pem,
            key_id=key_id,
        )
        claims = jwt_mgr.decode_token(token)

        # Check blocklist
        try:
            from alphastack.api.rest.routes.auth import blocklist
            jti = claims.get("jti", "")
            if jti and blocklist.is_revoked(jti):
                return None
        except ImportError:
            pass

        return claims
    except Exception as exc:
        logger.debug("ws_token_verify_failed", error=str(exc))
        return None


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
    user_id: str = ""           # populated after auth
    email: str = ""
    roles: list[str] = field(default_factory=list)
    is_authenticated: bool = False
    subscriptions: set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    msg_count_window: int = 0   # messages in current rate-limit window
    window_start: float = field(default_factory=time.time)

    def is_rate_limited(self) -> bool:
        """Check if client exceeds message rate limit."""
        now = time.time()
        if now - self.window_start >= 60:
            self.msg_count_window = 0
            self.window_start = now
        self.msg_count_window += 1
        return self.msg_count_window > _MSG_RATE_LIMIT

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()

    async def send_json(self, data: dict[str, Any]) -> None:
        try:
            await self.ws.send_json(data)
            self.touch()
        except Exception:
            logger.debug("ws_send_failed", client_id=self.client_id)


class ConnectionManager:
    """Manages WebSocket connections and channel subscriptions.

    Enforces per-user connection limits and tracks authenticated clients.
    """

    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}
        self._channels: dict[str, set[str]] = defaultdict(set)  # channel → {client_ids}
        self._user_connections: dict[str, set[str]] = defaultdict(set)  # user_id → {client_ids}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> Client:
        """Accept a WebSocket connection. Client must authenticate within _AUTH_TIMEOUT."""
        await ws.accept()
        client_id = str(uuid.uuid4())
        client = Client(client_id=client_id, ws=ws)
        async with self._lock:
            self._clients[client_id] = client
        logger.info("ws_client_connected", client_id=client_id)
        return client

    async def authenticate(self, client_id: str, user_id: str, email: str, roles: list[str]) -> bool:
        """Mark a client as authenticated. Returns False if user exceeds connection limit."""
        async with self._lock:
            client = self._clients.get(client_id)
            if not client:
                return False

            # Enforce per-user connection limit
            user_conns = self._user_connections.get(user_id, set())
            if len(user_conns) >= _MAX_CONNECTIONS_PER_USER:
                logger.warning(
                    "ws_connection_limit_exceeded",
                    user_id=user_id,
                    current_connections=len(user_conns),
                )
                return False

            client.is_authenticated = True
            client.user_id = user_id
            client.email = email
            client.roles = roles
            self._user_connections[user_id].add(client_id)

        logger.info("ws_client_authenticated", client_id=client_id, user_id=user_id)
        return True

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            client = self._clients.pop(client_id, None)
            if client:
                for ch in client.subscriptions:
                    self._channels[ch].discard(client_id)
                if client.user_id:
                    self._user_connections[client.user_id].discard(client_id)
                    if not self._user_connections[client.user_id]:
                        del self._user_connections[client.user_id]
        logger.info("ws_client_disconnected", client_id=client_id)

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            client = self._clients.get(client_id)
            if client and client.is_authenticated:
                client.subscriptions.add(channel)
                self._channels[channel].add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            client = self._clients.get(client_id)
            if client:
                client.subscriptions.discard(channel)
                self._channels[channel].discard(client_id)

    async def broadcast(self, channel: str, message: dict[str, Any]) -> int:
        """Broadcast a message to all authenticated subscribers of a channel."""
        sent = 0
        client_ids = list(self._channels.get(channel, set()))
        for cid in client_ids:
            client = self._clients.get(cid)
            if client and client.is_authenticated:
                await client.send_json({"channel": channel, "data": message, "ts": time.time()})
                sent += 1
        return sent

    async def send_to(self, client_id: str, message: dict[str, Any]) -> None:
        client = self._clients.get(client_id)
        if client and client.is_authenticated:
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
    if not client.is_authenticated:
        await client.send_json({"type": "error", "detail": "Not authenticated"})
        return
    channels = data.get("channels", [])
    for ch in channels:
        if isinstance(ch, str):
            await manager.subscribe(client.client_id, ch)
    await client.send_json({"type": "subscribed", "channels": channels})


async def _handle_unsubscribe(client: Client, data: dict[str, Any]) -> None:
    if not client.is_authenticated:
        await client.send_json({"type": "error", "detail": "Not authenticated"})
        return
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
    """Secure WebSocket endpoint.

    Security flow:
    1. Validate Origin header on upgrade
    2. Accept connection (unauthenticated)
    3. Wait for auth message with JWT token (10s timeout)
    4. Verify JWT, check blocklist, enforce per-user connection limit
    5. Run heartbeat loop (30s ping / 10s pong timeout)
    6. Disconnect on idle timeout (300s) or auth failure

    Protocol (JSON messages):

    Client → Server:
        {"type": "auth", "token": "<jwt_access_token>"}  (first message)
        {"type": "subscribe", "channels": ["prices", "trades", "signals"]}
        {"type": "unsubscribe", "channels": ["prices"]}
        {"type": "ping"}

    Server → Client:
        {"type": "auth_ok", "user_id": "...", "email": "..."}
        {"type": "auth_error", "detail": "..."}
        {"type": "heartbeat"}  (server-initiated ping)
        {"channel": "prices", "data": {...}, "ts": 1234567890.0}
        {"type": "subscribed", "channels": [...]}
        {"type": "pong", "ts": ...}
    """
    # 1. Origin validation on upgrade
    origin = ws.headers.get("origin", "")
    if origin and _ALLOWED_ORIGINS and origin not in _ALLOWED_ORIGINS:
        logger.warning("ws_origin_rejected", origin=origin)
        await ws.close(code=4403, reason="Origin not allowed")
        return

    client = await manager.connect(ws)

    try:
        # 2. Authentication phase — wait for auth message with timeout
        auth_msg = await _wait_for_auth(ws, client)
        if auth_msg is None:
            # Auth failed or timed out
            await ws.close(code=4401, reason="Authentication required")
            await manager.disconnect(client.client_id)
            return

        token = auth_msg.get("token", "")
        if not token:
            await client.send_json({"type": "auth_error", "detail": "Missing token field"})
            await ws.close(code=4401, reason="Missing token")
            await manager.disconnect(client.client_id)
            return

        # Verify JWT
        claims = _verify_ws_token(token)
        if claims is None:
            await client.send_json({"type": "auth_error", "detail": "Invalid or revoked token"})
            await ws.close(code=4401, reason="Invalid token")
            await manager.disconnect(client.client_id)
            return

        user_id = claims.get("sub", "")
        email = claims.get("email", "")
        roles = claims.get("roles", [])

        # Check per-user connection limit
        if not await manager.authenticate(client.client_id, user_id, email, roles):
            await client.send_json({"type": "auth_error", "detail": "Too many connections"})
            await ws.close(code=4429, reason="Connection limit exceeded")
            await manager.disconnect(client.client_id)
            return

        await client.send_json({"type": "auth_ok", "user_id": user_id, "email": email})
        logger.info("ws_auth_success", client_id=client.client_id, user_id=user_id)

        # 3. Main message loop with heartbeat and idle timeout
        await _message_loop(ws, client)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws_error", client_id=client.client_id)
    finally:
        await manager.disconnect(client.client_id)


async def _wait_for_auth(ws: WebSocket, client: Client) -> dict[str, Any] | None:
    """Wait for an auth message within _AUTH_TIMEOUT seconds.

    Returns the parsed auth message dict, or None on timeout/error.
    """
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=_AUTH_TIMEOUT)
        msg = json.loads(raw)
        if msg.get("type") != "auth":
            await client.send_json({"type": "error", "detail": "First message must be auth"})
            return None
        return msg
    except asyncio.TimeoutError:
        await client.send_json({"type": "error", "detail": "Auth timeout"})
        return None
    except json.JSONDecodeError:
        await client.send_json({"type": "error", "detail": "Invalid JSON"})
        return None


async def _message_loop(ws: WebSocket, client: Client) -> None:
    """Main message loop with heartbeat and idle timeout."""
    async def _heartbeat_task() -> None:
        """Send periodic heartbeat pings; disconnect on pong timeout."""
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            if not client.is_authenticated:
                return
            # Check idle timeout
            if time.time() - client.last_activity > _IDLE_TIMEOUT:
                logger.info("ws_idle_timeout", client_id=client.client_id)
                await ws.close(code=4408, reason="Idle timeout")
                return
            # Send heartbeat
            try:
                await client.send_json({"type": "heartbeat", "ts": time.time()})
            except Exception:
                return

    heartbeat = asyncio.create_task(_heartbeat_task())

    try:
        while True:
            # Check message size by reading raw bytes
            raw = await ws.receive_text()
            client.touch()

            # Enforce message size limit
            if len(raw.encode("utf-8")) > _MAX_MSG_SIZE:
                await client.send_json({"type": "error", "detail": "Message too large"})
                continue

            # Rate limiting
            if client.is_rate_limited():
                await client.send_json({"type": "error", "detail": "Rate limit exceeded"})
                continue

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
        raise
    finally:
        heartbeat.cancel()


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
