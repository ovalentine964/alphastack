"""
MT5 Bridge API — REST wrapper around MetaTrader 5 Python library.

Runs inside Docker with Wine + MT5.  Exposes endpoints that AlphaStack's
MT5BridgeConnector calls to trade forex via any MT5 broker (FXPesa, FBS,
ICMarkets, etc.).

Endpoints
---------
GET  /health               — MT5 connection status + uptime
GET  /metrics              — Prometheus metrics (text/openmetrics)
POST /connect              — Login to MT5 terminal
POST /disconnect           — Logout / shutdown terminal
GET  /account              — Account info (balance, equity, margin)
GET  /positions            — Open positions (unified BrokerPosition format)
GET  /tick/{symbol}        — Live price tick
GET  /bars/{symbol}        — OHLCV candles (?timeframe=H1&count=200)
GET  /symbols              — Available symbols on the server
POST /order                — Place order (market / limit / stop)
POST /order/close          — Close a position by ticket
POST /order/modify         — Modify SL/TP of an open position
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("mt5-bridge")

# ---------------------------------------------------------------------------
# Prometheus metrics (lightweight — no external dependency)
# ---------------------------------------------------------------------------
_METRICS: dict[str, float] = {
    "orders_total": 0,
    "orders_filled": 0,
    "orders_rejected": 0,
    "signals_received": 0,
    "ticks_served": 0,
    "bars_served": 0,
    "uptime_start": time.time(),
    "connected": 0,
}

# Histogram-style buckets for order latency (seconds)
_LATENCY_BUCKETS = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
_LATENCY_HIST: dict[float, int] = {b: 0 for b in _LATENCY_BUCKETS}
_LATENCY_INF = 0


def _record_latency(seconds: float) -> None:
    global _LATENCY_INF
    for b in _LATENCY_BUCKETS:
        if seconds <= b:
            _LATENCY_HIST[b] += 1
    _LATENCY_INF += 1


def _render_metrics() -> str:
    """Render Prometheus text exposition format."""
    lines: list[str] = []
    lines.append("# HELP mt5_bridge_uptime_seconds Seconds since bridge start")
    lines.append("# TYPE mt5_bridge_uptime_seconds gauge")
    lines.append(f"mt5_bridge_uptime_seconds {time.time() - _METRICS['uptime_start']:.1f}")

    lines.append("# HELP mt5_bridge_connected Whether MT5 is connected (1=yes)")
    lines.append("# TYPE mt5_bridge_connected gauge")
    lines.append(f"mt5_bridge_connected {int(_METRICS['connected'])}")

    for name in ("orders_total", "orders_filled", "orders_rejected",
                 "signals_received", "ticks_served", "bars_served"):
        lines.append(f"# HELP mt5_bridge_{name} Counter")
        lines.append(f"# TYPE mt5_bridge_{name} counter")
        lines.append(f"mt5_bridge_{name} {int(_METRICS[name])}")

    lines.append("# HELP mt5_bridge_order_latency_seconds Order execution latency")
    lines.append("# TYPE mt5_bridge_order_latency_seconds histogram")
    cumulative = 0
    for b in _LATENCY_BUCKETS:
        cumulative += _LATENCY_HIST[b]
        lines.append(f'mt5_bridge_order_latency_seconds_bucket{{le="{b}"}} {cumulative}')
    lines.append(f'mt5_bridge_order_latency_seconds_bucket{{le="+Inf"}} {_LATENCY_INF}')
    lines.append(f"mt5_bridge_order_latency_seconds_count {_LATENCY_INF}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# MT5 lazy import (only works under Wine)
# ---------------------------------------------------------------------------
_mt5: Any = None
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mt5")
_connected = False
_login_info: dict[str, Any] = {}


def _get_mt5() -> Any:
    global _mt5
    if _mt5 is None:
        import MetaTrader5 as mt5
        _mt5 = mt5
    return _mt5


async def _run(fn: Any, *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))


# ---------------------------------------------------------------------------
# Pydantic models — aligned with alphastack.brokers.models
# ---------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    login: int
    password: str
    server: str
    path: str | None = None  # Path to terminal64.exe (auto-detect if empty)


class OrderRequest(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    order_type: str = "market"  # "market", "limit", "stop"
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    magic: int = 20260713
    comment: str = ""
    # New fields — confluence / risk pipeline integration
    confluence_score: float | None = None
    risk_pct: float | None = None
    regime: str | None = None
    strategy_id: str | None = None
    signal_id: str | None = None


class CloseRequest(BaseModel):
    ticket: int
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float


class ModifyRequest(BaseModel):
    ticket: int
    symbol: str
    stop_loss: float | None = None
    take_profit: float | None = None


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("mt5-bridge starting")
    yield
    mt5 = _get_mt5()
    try:
        mt5.shutdown()
    except Exception:
        pass
    logger.info("mt5-bridge stopped")


app = FastAPI(
    title="AlphaStack MT5 Bridge API",
    version="1.1.0",
    description="REST bridge between AlphaStack and MetaTrader 5 (Wine/Docker)",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health & Metrics
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, Any]:
    mt5 = _get_mt5()
    try:
        info = mt5.terminal_info()
        mt5_ok = info is not None
    except Exception:
        mt5_ok = False

    return {
        "status": "ok" if mt5_ok and _connected else "disconnected",
        "mt5_connected": _connected,
        "mt5_terminal_ok": mt5_ok,
        "login": _login_info.get("login"),
        "server": _login_info.get("server"),
        "uptime_s": round(time.time() - _METRICS["uptime_start"], 1),
        "orders_filled": int(_METRICS["orders_filled"]),
        "orders_rejected": int(_METRICS["orders_rejected"]),
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=_render_metrics(), media_type="text/plain; version=0.0.4")


# ---------------------------------------------------------------------------
# Connect / Disconnect
# ---------------------------------------------------------------------------

@app.post("/connect")
async def connect(req: ConnectRequest) -> dict[str, Any]:
    global _connected, _login_info
    mt5 = _get_mt5()

    init_kwargs: dict[str, Any] = {"timeout": 60000}
    if req.path:
        init_kwargs["path"] = req.path

    ok = await _run(mt5.initialize, **init_kwargs)
    if not ok:
        err = await _run(mt5.last_error)
        raise HTTPException(500, f"MT5 initialize failed: {err}")

    authorized = await _run(mt5.login, req.login, req.password, req.server)
    if not authorized:
        err = await _run(mt5.last_error)
        raise HTTPException(401, f"MT5 login failed: {err}")

    _connected = True
    _login_info = {"login": req.login, "server": req.server}
    _METRICS["connected"] = 1
    logger.info("mt5_connected login=%d server=%s", req.login, req.server)
    return {"status": "connected", "login": req.login, "server": req.server}


@app.post("/disconnect")
async def disconnect() -> dict[str, str]:
    global _connected, _login_info
    mt5 = _get_mt5()
    mt5.shutdown()
    _connected = False
    _login_info = {}
    _METRICS["connected"] = 0
    logger.info("mt5_disconnected")
    return {"status": "disconnected"}


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

@app.get("/account")
async def account() -> dict[str, Any]:
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()
    info = await _run(mt5.account_info)
    if info is None:
        raise HTTPException(500, "Failed to get account info")
    d = info._asdict() if hasattr(info, "_asdict") else dict(info)
    return {
        "login": d.get("login"),
        "currency": d.get("currency", "USD"),
        "balance": d.get("balance", 0),
        "equity": d.get("equity", 0),
        "margin": d.get("margin", 0),
        "free_margin": d.get("margin_free", 0),
        "margin_level": d.get("margin_level", 0),
        "profit": d.get("profit", 0),
        "server": d.get("server", ""),
        "company": d.get("company", ""),
    }


# ---------------------------------------------------------------------------
# Positions — returns in BrokerPosition-compatible format
# ---------------------------------------------------------------------------

@app.get("/positions")
async def positions() -> list[dict[str, Any]]:
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()
    pos = await _run(mt5.positions_get)
    if not pos:
        return []
    result: list[dict[str, Any]] = []
    for p in pos:
        d = p._asdict() if hasattr(p, "_asdict") else dict(p)
        result.append({
            "ticket": d.get("ticket"),
            "symbol": d.get("symbol"),
            "side": "buy" if d.get("type") == 0 else "sell",
            "volume": d.get("volume"),
            "price_open": d.get("price_open"),
            "price_current": d.get("price_current"),
            "sl": d.get("sl"),
            "tp": d.get("tp"),
            "profit": d.get("profit"),
            "swap": d.get("swap"),
            "margin": d.get("margin", 0),
            "magic": d.get("magic"),
            "comment": d.get("comment", ""),
            "time": d.get("time", 0),
        })
    return result


# ---------------------------------------------------------------------------
# Tick
# ---------------------------------------------------------------------------

@app.get("/tick/{symbol}")
async def tick(symbol: str) -> dict[str, Any]:
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()
    t = await _run(mt5.symbol_info_tick, symbol)
    if t is None:
        raise HTTPException(404, f"No tick data for {symbol}")
    d = t._asdict() if hasattr(t, "_asdict") else dict(t)
    _METRICS["ticks_served"] += 1
    bid = d.get("bid", 0)
    ask = d.get("ask", 0)
    return {
        "symbol": symbol,
        "bid": bid,
        "ask": ask,
        "last": d.get("last", 0) or (bid + ask) / 2 if bid and ask else 0,
        "spread": d.get("spread", 0),
        "time": d.get("time", 0),
    }


# ---------------------------------------------------------------------------
# Bars
# ---------------------------------------------------------------------------

@app.get("/bars/{symbol}")
async def bars(symbol: str, timeframe: str = "H1", count: int = 200) -> list[dict[str, Any]]:
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()

    tf_map: dict[str, int] = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30,
        "H1": 16385, "H4": 16388, "D1": 16408, "W1": 32769, "MN1": 49153,
    }
    mt5_tf = tf_map.get(timeframe.upper(), 16385)

    rates = await _run(mt5.copy_rates_from_pos, symbol, mt5_tf, 0, count)
    if rates is None or len(rates) == 0:
        return []

    _METRICS["bars_served"] += 1
    return [
        {
            "time": int(r["time"]),
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "volume": r["tick_volume"],
            "spread": r["spread"],
        }
        for r in rates
    ]


# ---------------------------------------------------------------------------
# Symbols
# ---------------------------------------------------------------------------

@app.get("/symbols")
async def symbols() -> list[dict[str, str]]:
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()
    all_symbols = await _run(mt5.symbols_get)
    if not all_symbols:
        return []
    return [{"name": s.name, "path": s.path} for s in all_symbols[:200]]


# ---------------------------------------------------------------------------
# Place Order
# ---------------------------------------------------------------------------

@app.post("/order")
async def place_order(req: OrderRequest) -> dict[str, Any]:
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()

    t0 = time.monotonic()
    _METRICS["orders_total"] += 1

    side_map = {"buy": 0, "sell": 1}
    order_type = side_map.get(req.side.lower())
    if order_type is None:
        raise HTTPException(400, f"Invalid side: {req.side}")

    # Build comment with confluence metadata
    comment = req.comment or "AlphaStack"
    if req.confluence_score is not None:
        comment = f"AS:{req.strategy_id or 's'}:{req.confluence_score:.0f}"
    if req.signal_id:
        comment = f"{comment}|{req.signal_id[:16]}"

    if req.order_type == "market":
        action = 1  # TRADE_ACTION_DEAL
        tick = await _run(mt5.symbol_info_tick, req.symbol)
        if tick is None:
            _METRICS["orders_rejected"] += 1
            raise HTTPException(404, f"No tick for {req.symbol}")
        price = tick.ask if req.side == "buy" else tick.bid
        order_type_val = order_type
    else:
        type_map = {"limit": 2, "stop": 4}
        action = 0  # TRADE_ACTION_PENDING
        price = req.price or 0
        order_type_val = type_map.get(req.order_type, 0) + order_type

    request: dict[str, Any] = {
        "action": action,
        "symbol": req.symbol,
        "volume": req.quantity,
        "type": order_type_val,
        "price": price,
        "deviation": 10,
        "magic": req.magic,
        "comment": comment,
        "type_filling": 2,  # ORDER_FILLING_IOC
    }

    if req.stop_loss:
        request["sl"] = req.stop_loss
    if req.take_profit:
        request["tp"] = req.take_profit

    result = await _run(mt5.order_send, request)
    if result is None:
        err = await _run(mt5.last_error)
        _METRICS["orders_rejected"] += 1
        raise HTTPException(500, f"Order failed: {err}")

    d = result._asdict() if hasattr(result, "_asdict") else dict(result)
    retcode = d.get("retcode", 0)
    latency = time.monotonic() - t0
    _record_latency(latency)

    if retcode == 10009:  # DONE
        _METRICS["orders_filled"] += 1
        logger.info(
            "order_filled symbol=%s side=%s vol=%.2f price=%.5f ticket=%d latency=%.3fs",
            req.symbol, req.side, req.quantity, d.get("price", 0), d.get("order", 0), latency,
        )
        return {
            "status": "filled",
            "ticket": d.get("order"),
            "price": d.get("price", 0),
            "volume": d.get("volume", 0),
            "retcode": retcode,
            "latency_s": round(latency, 4),
        }
    else:
        _METRICS["orders_rejected"] += 1
        logger.warning("order_rejected symbol=%s retcode=%d comment=%s", req.symbol, retcode, d.get("comment", ""))
        raise HTTPException(400, f"Order rejected: retcode={retcode}, comment={d.get('comment', '')}")


# ---------------------------------------------------------------------------
# Close Position
# ---------------------------------------------------------------------------

@app.post("/order/close")
async def close_position(req: CloseRequest) -> dict[str, Any]:
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()

    t0 = time.monotonic()

    close_type = 1 if req.side == "buy" else 0  # Reverse side
    tick = await _run(mt5.symbol_info_tick, req.symbol)
    if tick is None:
        raise HTTPException(404, f"No tick for {req.symbol}")

    price = tick.bid if req.side == "buy" else tick.ask

    request: dict[str, Any] = {
        "action": 1,  # TRADE_ACTION_DEAL
        "symbol": req.symbol,
        "volume": req.quantity,
        "type": close_type,
        "position": req.ticket,
        "price": price,
        "deviation": 10,
        "magic": 20260713,
        "comment": "AS:close",
        "type_filling": 2,
    }

    result = await _run(mt5.order_send, request)
    if result is None:
        err = await _run(mt5.last_error)
        raise HTTPException(500, f"Close failed: {err}")

    d = result._asdict() if hasattr(result, "_asdict") else dict(result)
    latency = time.monotonic() - t0
    _record_latency(latency)

    if d.get("retcode") == 10009:
        logger.info("position_closed ticket=%d profit=%.2f latency=%.3fs", req.ticket, d.get("profit", 0), latency)
        return {"status": "closed", "ticket": req.ticket, "profit": d.get("profit", 0)}
    else:
        raise HTTPException(400, f"Close rejected: retcode={d.get('retcode')}")


# ---------------------------------------------------------------------------
# Modify Position (new — needed for trailing stop / breakeven from Python side)
# ---------------------------------------------------------------------------

@app.post("/order/modify")
async def modify_position(req: ModifyRequest) -> dict[str, Any]:
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()

    # Select position by ticket
    positions = await _run(mt5.positions_get)
    pos = None
    if positions:
        for p in positions:
            if p.ticket == req.ticket:
                pos = p
                break

    if pos is None:
        raise HTTPException(404, f"Position {req.ticket} not found")

    request: dict[str, Any] = {
        "action": 3,  # TRADE_ACTION_SLTP
        "symbol": req.symbol,
        "position": req.ticket,
        "sl": req.stop_loss if req.stop_loss is not None else pos.sl,
        "tp": req.take_profit if req.take_profit is not None else pos.tp,
    }

    result = await _run(mt5.order_send, request)
    if result is None:
        err = await _run(mt5.last_error)
        raise HTTPException(500, f"Modify failed: {err}")

    d = result._asdict() if hasattr(result, "_asdict") else dict(result)
    if d.get("retcode") == 10009:
        logger.info("position_modified ticket=%d sl=%.5f tp=%.5f", req.ticket, request["sl"], request["tp"])
        return {"status": "modified", "ticket": req.ticket, "sl": request["sl"], "tp": request["tp"]}
    else:
        raise HTTPException(400, f"Modify rejected: retcode={d.get('retcode')}")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("API_PORT", os.environ.get("PORT", "8080")))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
