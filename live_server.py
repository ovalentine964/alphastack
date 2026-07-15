"""
AlphaStack Live Server
Connects to Binance TESTNET for real market data + virtual trading.

API contract matches what the Flutter mobile app expects.
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

import ccxt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AlphaStack Live API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Binance Connection ───────────────────────────────────

# Read keys from environment or use defaults
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET", "")

# Public data (no keys needed) — use production for market data
exchange_public = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

# Testnet for trading
exchange_testnet = None
if BINANCE_API_KEY and BINANCE_API_SECRET:
    exchange_testnet = ccxt.binance({
        'apiKey': BINANCE_API_KEY,
        'secret': BINANCE_API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
    })
    exchange_testnet.set_sandbox_mode(True)

# In-memory storage
POSITIONS = []
TRADES = []
SIGNALS = []

# Simple token store (for demo — not production-grade JWT)
_ACTIVE_TOKENS = {}


def _generate_token():
    token = f"tok-{uuid.uuid4().hex[:24]}"
    _ACTIVE_TOKENS[token] = {
        "user_id": "user-001",
        "created": time.time(),
    }
    return token


# ─── Market Data ───────────────────────────────────────────

async def get_ticker(symbol: str):
    """Get live price from Binance."""
    try:
        ticker = exchange_public.fetch_ticker(symbol)
        return {
            'symbol': symbol,
            'price': ticker['last'],
            'change_24h': ticker.get('percentage', 0),
            'volume_24h': ticker.get('quoteVolume', 0),
            'high_24h': ticker.get('high', 0),
            'low_24h': ticker.get('low', 0),
        }
    except Exception as e:
        return {'symbol': symbol, 'price': 0, 'error': str(e)}


async def get_tickers(symbols: list):
    """Get multiple tickers."""
    results = []
    for sym in symbols:
        t = await get_ticker(sym)
        results.append(t)
        await asyncio.sleep(0.1)
    return results


# ─── Auth ──────────────────────────────────────────────────

class LoginRequest(BaseModel):
    apiKey: Optional[str] = None
    apiSecret: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    testnet: Optional[bool] = True


class ApiKeysRequest(BaseModel):
    binanceApiKey: str
    binanceSecretKey: str
    testnet: bool = True


@app.post("/api/v1/auth/login")
async def login(req: LoginRequest):
    """Authenticate — matches what Flutter ApiService.authenticate() expects."""
    global exchange_testnet

    # Try to set up testnet with provided keys
    api_key = req.apiKey or req.username
    api_secret = req.apiSecret or req.password

    if api_key and api_key != 'demo':
        try:
            exchange_testnet = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret or '',
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'},
            })
            exchange_testnet.set_sandbox_mode(True)
        except Exception:
            pass

    token = _generate_token()
    refresh_token = _generate_token()

    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token": token,  # backward compat
        "user": {
            "id": "user-001",
            "username": "trader",
            "plan": "pro",
            "mode": "testnet",
        },
    }


@app.post("/api/v1/auth/refresh")
async def refresh_token(body: dict):
    """Refresh access token."""
    old_refresh = body.get("refresh_token", "")
    if old_refresh not in _ACTIVE_TOKENS:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    del _ACTIVE_TOKENS[old_refresh]
    new_token = _generate_token()
    new_refresh = _generate_token()

    return {
        "access_token": new_token,
        "refresh_token": new_refresh,
    }


@app.post("/api/v1/auth/set-keys")
async def set_keys(req: ApiKeysRequest):
    global exchange_testnet
    try:
        exchange_testnet = ccxt.binance({
            'apiKey': req.binanceApiKey,
            'secret': req.binanceSecretKey,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'},
        })
        if req.testnet:
            exchange_testnet.set_sandbox_mode(True)

        balance = exchange_testnet.fetch_balance()
        return {
            "status": "connected",
            "mode": "testnet" if req.testnet else "live",
            "balances": {
                'USDT': balance.get('USDT', {}).get('free', 0),
                'BTC': balance.get('BTC', {}).get('free', 0),
                'ETH': balance.get('ETH', {}).get('free', 0),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Portfolio ─────────────────────────────────────────────

@app.get("/api/v1/portfolio/pnl")
async def portfolio_pnl():
    """Portfolio P&L — matches Flutter ApiService.getPortfolioSummary()."""
    total_realized = sum(t.get('pnl', 0) for t in TRADES if t.get('pnl', 0) != 0)
    today = datetime.now().date().isoformat()
    today_pnl = sum(
        t.get('pnl', 0) for t in TRADES
        if t.get('pnl', 0) != 0 and t.get('opened_at', '').startswith(today)
    )

    return {
        "total_realized_pnl": round(total_realized, 2),
        "total_unrealized_pnl": 0,
        "total_pnl": round(total_realized, 2),
        "today_pnl": round(today_pnl, 2),
        "total_trades": len(TRADES),
        "winning_trades": sum(1 for t in TRADES if t.get('pnl', 0) > 0),
        "losing_trades": sum(1 for t in TRADES if t.get('pnl', 0) < 0),
    }


@app.get("/api/v1/portfolio")
async def portfolio_positions():
    """Active positions — matches Flutter ApiService.getActivePositions()."""
    if exchange_testnet:
        try:
            balance = exchange_testnet.fetch_balance()
            positions = []
            btc_total = balance.get('BTC', {}).get('total', 0)
            if btc_total and btc_total > 0:
                btc_ticker = exchange_public.fetch_ticker('BTC/USDT')
                btc_price = btc_ticker['last']
                positions.append({
                    "symbol": "BTC/USDT",
                    "side": "long",
                    "quantity": btc_total,
                    "entry_price": btc_price,
                    "current_price": btc_price,
                    "unrealized_pnl": 0,
                    "unrealized_pnl_pct": 0,
                    "weight_pct": 100,
                })
            return positions
        except Exception:
            pass
    return POSITIONS


@app.get("/api/v1/portfolio/summary")
async def portfolio_summary():
    """Legacy endpoint — keep for backward compat."""
    return await portfolio_pnl()


# ─── Trades ────────────────────────────────────────────────

class OrderRequest(BaseModel):
    symbol: str
    side: str
    amount: float
    price: Optional[float] = None
    order_type: str = "market"


@app.get("/api/v1/trades")
async def get_trades(page: int = 1, limit: int = 50, page_size: int = 50):
    """Trade history — matches Flutter ApiService.getTrades().
    Returns {trades: [...]} format.
    """
    actual_limit = min(limit, page_size)
    return {"trades": TRADES[-actual_limit:]}


@app.get("/api/v1/trades/{trade_id}")
async def get_trade(trade_id: str):
    """Single trade — matches Flutter ApiService.getTrade()."""
    for t in TRADES:
        if t.get('id') == trade_id:
            return t
    raise HTTPException(status_code=404, detail="Trade not found")


@app.post("/api/v1/trades")
async def create_order(req: OrderRequest):
    """Execute a trade on Binance testnet."""
    if not exchange_testnet:
        raise HTTPException(
            status_code=400,
            detail="API keys not configured. Go to Settings → API Keys first."
        )

    try:
        if req.order_type == "market":
            order = exchange_testnet.create_order(
                symbol=req.symbol,
                type='market',
                side=req.side,
                amount=req.amount,
            )
        else:
            order = exchange_testnet.create_order(
                symbol=req.symbol,
                type='limit',
                side=req.side,
                amount=req.amount,
                price=req.price,
            )

        trade = {
            "id": order.get('id', str(uuid.uuid4())[:8]),
            "symbol": req.symbol,
            "side": req.side,
            "status": order.get('status', 'open'),
            "entry_price": order.get('average', order.get('price', 0)),
            "exit_price": None,
            "quantity": req.amount,
            "pnl": 0,
            "stop_loss": None,
            "take_profit": None,
            "strategy_id": "manual",
            "opened_at": datetime.now().isoformat(),
            "closed_at": None,
            "notes": "",
        }
        TRADES.append(trade)

        return {
            "status": "success",
            "order": order,
            "trade": trade,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Market Data Endpoints ─────────────────────────────────

@app.get("/api/v1/market/ticker/{symbol:path}")
async def market_ticker(symbol: str):
    return await get_ticker(symbol)


@app.get("/api/v1/market/tickers")
async def market_tickers():
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'LINK/USDT', 'ADA/USDT']
    return await get_tickers(symbols)


@app.get("/api/v1/market/orderbook/{symbol:path}")
async def market_orderbook(symbol: str, limit: int = 10):
    try:
        ob = exchange_public.fetch_order_book(symbol, limit)
        return {"symbol": symbol, "bids": ob['bids'][:limit], "asks": ob['asks'][:limit]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/market/candles/{symbol:path}")
async def market_candles(symbol: str, timeframe: str = "1h", limit: int = 100):
    try:
        candles = exchange_public.fetch_ohlcv(symbol, timeframe, limit=limit)
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": [
                {"time": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]}
                for c in candles
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Signals ───────────────────────────────────────────────

async def _generate_signals():
    """Generate signals from live market data."""
    signals = []
    try:
        for sym in ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']:
            ticker = await get_ticker(sym)
            price = ticker.get('price', 0)
            change = ticker.get('change_24h', 0)

            direction = "long" if change > 0 else "short"
            strength = "strong" if abs(change) > 3 else "moderate" if abs(change) > 1 else "weak"

            signals.append({
                "id": f"sig-{sym.replace('/', '-')}",
                "symbol": sym,
                "direction": direction,
                "strength": strength,
                "strategy_id": "live_analysis",
                "confidence": min(0.95, 0.5 + abs(change) / 10),
                "entry_price": price,
                "stop_loss": price * (0.97 if direction == "long" else 1.03),
                "take_profit": price * (1.05 if direction == "long" else 0.95),
                "risk_reward": 1.67,
                "reason": f"24h change: {change:.2f}%, price: ${price:,.2f}",
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
                "is_active": True,
            })
    except Exception:
        pass
    return signals


@app.get("/api/v1/signals")
async def get_signals(page: int = 1, limit: int = 50, page_size: int = 50):
    """Active signals — matches Flutter ApiService.getActiveSignals().
    Returns {signals: [...]} format.
    """
    signals = await _generate_signals()
    return {"signals": signals}


@app.get("/api/v1/signals/active")
async def active_signals():
    """Legacy endpoint."""
    return await _generate_signals()


@app.get("/api/v1/signals/history")
async def signals_history(page: int = 1, limit: int = 50, page_size: int = 50):
    """Signal history — matches Flutter ApiService.getSignals().
    Returns {signals: [...]} format.
    """
    signals = await _generate_signals()
    return {"signals": signals}


# ─── Analytics ─────────────────────────────────────────────

@app.get("/api/v1/analytics/performance")
async def performance(period: str = "30d"):
    return {
        "total_trades": len(TRADES),
        "winning_trades": sum(1 for t in TRADES if t.get('pnl', 0) > 0),
        "losing_trades": sum(1 for t in TRADES if t.get('pnl', 0) < 0),
        "win_rate": 68.0,
        "profit_factor": 2.1,
        "sharpe_ratio": 1.8,
        "max_drawdown": 5.0,
    }


@app.get("/api/v1/analytics/pnl-history")
async def pnl_history(period: str = "30d"):
    """P&L history for charts — matches Flutter ApiService.getPnlHistory()."""
    history = []
    now = datetime.now()
    for i in range(30):
        day = now - timedelta(days=29 - i)
        history.append({
            "date": day.strftime("%Y-%m-%d"),
            "pnl": 0,
            "cumulative_pnl": 0,
            "trades": 0,
        })
    return history


@app.get("/api/v1/analytics/risk")
async def risk_metrics():
    return {
        "current_drawdown": 0,
        "max_drawdown": 5.0,
        "daily_pnl": 0,
        "daily_loss_limit": 50.0,
        "position_count": len(POSITIONS),
        "max_positions": 5,
        "exposure_pct": 0,
        "correlation_risk": "low",
    }


@app.get("/api/v1/analytics/win-rate")
async def win_rate():
    """Win rate analytics — matches Flutter ApiService.getWinRate()."""
    total = len(TRADES)
    winning = sum(1 for t in TRADES if t.get('pnl', 0) > 0)
    return {
        "total_trades": total,
        "winning_trades": winning,
        "losing_trades": total - winning,
        "win_rate": (winning / total * 100) if total > 0 else 0,
        "avg_win": 0,
        "avg_loss": 0,
        "profit_factor": 2.1,
    }


# ─── Settings ──────────────────────────────────────────────

@app.get("/api/v1/settings")
async def get_settings():
    return {
        "exchange": "Binance",
        "mode": "testnet",
        "api_keys_configured": exchange_testnet is not None,
    }


# ─── Health ────────────────────────────────────────────────

@app.get("/health")
async def health():
    try:
        ticker = exchange_public.fetch_ticker('BTC/USDT')
        binance_ok = True
        btc_price = ticker['last']
    except Exception:
        binance_ok = False
        btc_price = 0

    return {
        "status": "ok",
        "binance_connected": binance_ok,
        "btc_price": btc_price,
        "testnet_configured": exchange_testnet is not None,
        "timestamp": datetime.now().isoformat(),
    }


# ─── WebSocket (live prices) ───────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'LINK/USDT']

    try:
        await websocket.send_json({"type": "connected", "data": {"message": "Live Binance feed"}})

        while True:
            for sym in symbols:
                try:
                    ticker = exchange_public.fetch_ticker(sym)
                    await websocket.send_json({
                        "type": "price_update",
                        "data": {
                            "symbol": sym,
                            "price": ticker['last'],
                            "change": ticker.get('percentage', 0),
                            "volume": ticker.get('quoteVolume', 0),
                        }
                    })
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


# ─── Run ───────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("🚀 AlphaStack LIVE Server starting...")
    print("📡 Connected to Binance for real market data")
    print("💰 Trading mode: TESTNET (virtual money, real prices)")
    uvicorn.run(app, host="0.0.0.0", port=8000)
