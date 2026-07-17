"""
MT5 Bridge API — REST wrapper around MetaTrader 5 Python library.

Runs inside Docker with Wine + MT5. Exposes endpoints that AlphaStack
can call to trade forex via FXPesa, FBS, or any MT5 broker.

Endpoints:
  GET  /health           — MT5 connection status
  POST /connect          — Login to MT5
  POST /disconnect       — Logout
  GET  /account          — Account info (balance, equity, margin)
  GET  /positions        — Open positions
  GET  /tick/{symbol}    — Live price tick
  GET  /bars/{symbol}    — OHLCV candles (?timeframe=H1&count=200)
  POST /order            — Place order
  POST /order/close      — Close position
  GET  /symbols          — Available symbols
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mt5-bridge")

# Lazy import MetaTrader5 (only works under Wine)
_mt5: Any = None
_executor = ThreadPoolExecutor(max_workers=4)
_connected = False
_login_info: dict[str, Any] = {}


def _get_mt5():
    global _mt5
    if _mt5 is None:
        import MetaTrader5 as mt5
        _mt5 = mt5
    return _mt5


async def _run(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))


# ─── Models ─────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    login: int
    password: str
    server: str
    path: str | None = None  # Path to terminal64.exe


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


class CloseRequest(BaseModel):
    ticket: int
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float


# ─── App ────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("mt5-bridge starting")
    yield
    mt5 = _get_mt5()
    try:
        mt5.shutdown()
    except:
        pass
    logger.info("mt5-bridge stopped")


app = FastAPI(title="MT5 Bridge API", version="0.1.0", lifespan=lifespan)


# ─── Health ─────────────────────────────────────────────────

@app.get("/health")
async def health():
    mt5 = _get_mt5()
    try:
        info = mt5.terminal_info()
        connected = info is not None
    except:
        connected = False
    return {
        "status": "ok" if connected else "disconnected",
        "mt5_connected": _connected,
        "login": _login_info.get("login"),
        "server": _login_info.get("server"),
        "uptime": time.time(),
    }


# ─── Connect ────────────────────────────────────────────────

@app.post("/connect")
async def connect(req: ConnectRequest):
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
    logger.info(f"MT5 connected: login={req.login} server={req.server}")
    return {"status": "connected", "login": req.login, "server": req.server}


@app.post("/disconnect")
async def disconnect():
    global _connected, _login_info
    mt5 = _get_mt5()
    mt5.shutdown()
    _connected = False
    _login_info = {}
    return {"status": "disconnected"}


# ─── Account ────────────────────────────────────────────────

@app.get("/account")
async def account():
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


# ─── Positions ──────────────────────────────────────────────

@app.get("/positions")
async def positions():
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()
    pos = await _run(mt5.positions_get)
    if not pos:
        return []
    result = []
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
            "magic": d.get("magic"),
            "comment": d.get("comment", ""),
        })
    return result


# ─── Tick ────────────────────────────────────────────────────

@app.get("/tick/{symbol}")
async def tick(symbol: str):
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()
    t = await _run(mt5.symbol_info_tick, symbol)
    if t is None:
        raise HTTPException(404, f"No tick data for {symbol}")
    d = t._asdict() if hasattr(t, "_asdict") else dict(t)
    return {
        "symbol": symbol,
        "bid": d.get("bid", 0),
        "ask": d.get("ask", 0),
        "last": d.get("last", 0) or (d.get("bid", 0) + d.get("ask", 0)) / 2,
        "spread": d.get("spread", 0),
        "time": d.get("time", 0),
    }


# ─── Bars ────────────────────────────────────────────────────

@app.get("/bars/{symbol}")
async def bars(symbol: str, timeframe: str = "H1", count: int = 200):
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()

    tf_map = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 16385, "H4": 16388, "D1": 16408}
    mt5_tf = tf_map.get(timeframe.upper(), 16385)

    rates = await _run(mt5.copy_rates_from_pos, symbol, mt5_tf, 0, count)
    if rates is None or len(rates) == 0:
        return []

    return [
        {
            "time": r["time"],
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "volume": r["tick_volume"],
            "spread": r["spread"],
        }
        for r in rates
    ]


# ─── Symbols ────────────────────────────────────────────────

@app.get("/symbols")
async def symbols():
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()
    all_symbols = await _run(mt5.symbols_get)
    if not all_symbols:
        return []
    return [{"name": s.name, "path": s.path} for s in all_symbols[:100]]


# ─── Place Order ────────────────────────────────────────────

@app.post("/order")
async def place_order(req: OrderRequest):
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()

    side_map = {"buy": 0, "sell": 1}
    type_map = {"market": None, "limit": 2, "stop": 4}
    order_type = side_map.get(req.side.lower())
    if order_type is None:
        raise HTTPException(400, f"Invalid side: {req.side}")

    if req.order_type == "market":
        action = 1  # TRADE_ACTION_DEAL
        tick = await _run(mt5.symbol_info_tick, req.symbol)
        if tick is None:
            raise HTTPException(404, f"No tick for {req.symbol}")
        price = tick.ask if req.side == "buy" else tick.bid
        order_type_val = order_type
    else:
        action = 0  # TRADE_ACTION_PENDING
        price = req.price or 0
        order_type_val = type_map.get(req.order_type, 0) + order_type

    request = {
        "action": action,
        "symbol": req.symbol,
        "volume": req.quantity,
        "type": order_type_val,
        "price": price,
        "deviation": 10,
        "magic": req.magic,
        "comment": req.comment or "AlphaStack",
        "type_filling": 2,  # ORDER_FILLING_IOC
    }

    if req.stop_loss:
        request["sl"] = req.stop_loss
    if req.take_profit:
        request["tp"] = req.take_profit

    result = await _run(mt5.order_send, request)
    if result is None:
        err = await _run(mt5.last_error)
        raise HTTPException(500, f"Order failed: {err}")

    d = result._asdict() if hasattr(result, "_asdict") else dict(result)
    retcode = d.get("retcode", 0)

    if retcode == 10009:  # DONE
        return {
            "status": "filled",
            "order_id": d.get("order"),
            "price": d.get("price", 0),
            "volume": d.get("volume", 0),
            "retcode": retcode,
        }
    else:
        raise HTTPException(400, f"Order rejected: retcode={retcode}, comment={d.get('comment', '')}")


# ─── Close Position ─────────────────────────────────────────

@app.post("/order/close")
async def close_position(req: CloseRequest):
    if not _connected:
        raise HTTPException(400, "Not connected to MT5")
    mt5 = _get_mt5()

    close_type = 1 if req.side == "buy" else 0  # Reverse side
    tick = await _run(mt5.symbol_info_tick, req.symbol)
    if tick is None:
        raise HTTPException(404, f"No tick for {req.symbol}")

    price = tick.bid if req.side == "buy" else tick.ask

    request = {
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
    if d.get("retcode") == 10009:
        return {"status": "closed", "ticket": req.ticket, "profit": d.get("profit", 0)}
    else:
        raise HTTPException(400, f"Close rejected: retcode={d.get('retcode')}")


# ─── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
