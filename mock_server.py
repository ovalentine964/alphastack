"""
AlphaStack Mock API Server
Lightweight server for testing the mobile app.
No heavy dependencies - just FastAPI + uvicorn.
"""

import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="AlphaStack Mock API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Mock Data ─────────────────────────────────────────────

MOCK_USER = {
    "id": "user-001",
    "username": "trader",
    "email": "trader@alphastack.io",
    "plan": "pro",
    "created_at": "2026-01-01T00:00:00Z"
}

MOCK_PORTFOLIO = {
    "total_value": 1250.75,
    "available_balance": 450.25,
    "unrealized_pnl": 35.50,
    "realized_pnl": 120.00,
    "total_pnl": 155.50,
    "pnl_percent": 14.2,
    "positions_count": 3,
    "win_rate": 68.5,
    "sharpe_ratio": 1.85,
    "max_drawdown": 8.2
}

MOCK_POSITIONS = [
    {
        "symbol": "BTC/USDT",
        "side": "long",
        "quantity": 0.0015,
        "entry_price": 67250.00,
        "current_price": 67800.00,
        "unrealized_pnl": 0.825,
        "unrealized_pnl_pct": 0.82,
        "weight_pct": 45.2
    },
    {
        "symbol": "ETH/USDT",
        "side": "long",
        "quantity": 0.1,
        "entry_price": 3450.00,
        "current_price": 3520.00,
        "unrealized_pnl": 7.00,
        "unrealized_pnl_pct": 2.03,
        "weight_pct": 30.1
    },
    {
        "symbol": "SOL/USDT",
        "side": "short",
        "quantity": 2.0,
        "entry_price": 180.00,
        "current_price": 175.50,
        "unrealized_pnl": 9.00,
        "unrealized_pnl_pct": 2.50,
        "weight_pct": 24.7
    }
]

MOCK_TRADES = [
    {
        "id": "t-001",
        "symbol": "BTC/USDT",
        "side": "long",
        "status": "closed",
        "entry_price": 65200.00,
        "exit_price": 67800.00,
        "quantity": 0.002,
        "pnl": 5.20,
        "stop_loss": 64000.00,
        "take_profit": 70000.00,
        "strategy_id": "trend_following",
        "opened_at": (datetime.now() - timedelta(days=2)).isoformat(),
        "closed_at": (datetime.now() - timedelta(days=1)).isoformat(),
        "notes": "Strong uptrend continuation"
    },
    {
        "id": "t-002",
        "symbol": "ETH/USDT",
        "side": "long",
        "status": "closed",
        "entry_price": 3450.00,
        "exit_price": 3380.00,
        "quantity": 0.05,
        "pnl": -3.50,
        "stop_loss": 3300.00,
        "take_profit": 3600.00,
        "strategy_id": "breakout",
        "opened_at": (datetime.now() - timedelta(days=3)).isoformat(),
        "closed_at": (datetime.now() - timedelta(days=2)).isoformat(),
        "notes": "False breakout, stopped out"
    },
    {
        "id": "t-003",
        "symbol": "SOL/USDT",
        "side": "short",
        "status": "open",
        "entry_price": 180.00,
        "exit_price": None,
        "quantity": 2.0,
        "pnl": 9.00,
        "stop_loss": 190.00,
        "take_profit": 165.00,
        "strategy_id": "mean_reversion",
        "opened_at": (datetime.now() - timedelta(hours=6)).isoformat(),
        "closed_at": None,
        "notes": "Overbought on RSI"
    }
]

MOCK_SIGNALS = [
    {
        "id": "sig-001",
        "symbol": "BTC/USDT",
        "direction": "long",
        "strength": "strong",
        "strategy_id": "trend_following",
        "confidence": 0.82,
        "entry_price": 67500.00,
        "stop_loss": 66000.00,
        "take_profit": 72000.00,
        "risk_reward": 2.67,
        "reason": "EMA crossover, bullish structure, high volume",
        "created_at": (datetime.now() - timedelta(minutes=15)).isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=2)).isoformat(),
        "is_active": True
    },
    {
        "id": "sig-002",
        "symbol": "ETH/USDT",
        "direction": "buy",
        "strength": "moderate",
        "strategy_id": "support_bounce",
        "confidence": 0.65,
        "entry_price": 3500.00,
        "stop_loss": 3400.00,
        "take_profit": 3700.00,
        "risk_reward": 2.0,
        "reason": "Support bounce at 3500, RSI oversold",
        "created_at": (datetime.now() - timedelta(minutes=30)).isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        "is_active": True
    },
    {
        "id": "sig-003",
        "symbol": "LINK/USDT",
        "direction": "long",
        "strength": "very_strong",
        "strategy_id": "breakout",
        "confidence": 0.91,
        "entry_price": 14.50,
        "stop_loss": 13.80,
        "take_profit": 16.50,
        "risk_reward": 2.86,
        "reason": "Bullish breakout, volume surge, whale accumulation",
        "created_at": (datetime.now() - timedelta(minutes=5)).isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=3)).isoformat(),
        "is_active": True
    }
]

MOCK_ANALYTICS = {
    "total_trades": 47,
    "winning_trades": 32,
    "losing_trades": 15,
    "win_rate": 68.1,
    "profit_factor": 2.15,
    "sharpe_ratio": 1.85,
    "max_drawdown": 8.2,
    "avg_win": 12.50,
    "avg_loss": -5.80,
    "best_trade": 45.00,
    "worst_trade": -18.50,
    "pnl_history": [
        {"date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"),
         "value": round(random.uniform(-20, 50), 2)}
        for i in range(30, 0, -1)
    ]
}

MOCK_RISK = {
    "current_drawdown": 2.1,
    "max_drawdown": 8.2,
    "daily_pnl": 15.50,
    "daily_loss_limit": 50.0,
    "position_count": 3,
    "max_positions": 5,
    "exposure_pct": 72.5,
    "correlation_risk": "low",
    "circuit_breaker_status": "inactive"
}


# ─── Auth ──────────────────────────────────────────────────

class LoginRequest(BaseModel):
    apiKey: Optional[str] = None
    apiSecret: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

@app.post("/api/v1/auth/login")
async def login(req: LoginRequest):
    # Accept any credentials for demo
    return {
        "token": "mock-jwt-token-abc123",
        "user": MOCK_USER,
        "message": "Connected successfully"
    }

@app.get("/api/v1/auth/me")
async def get_me():
    return MOCK_USER


# ─── Portfolio ─────────────────────────────────────────────

@app.get("/api/v1/portfolio/summary")
async def portfolio_summary():
    return MOCK_PORTFOLIO

@app.get("/api/v1/portfolio/positions")
async def portfolio_positions():
    return MOCK_POSITIONS


# ─── Trades ────────────────────────────────────────────────

@app.get("/api/v1/trades")
async def get_trades(page: int = 1, limit: int = 50):
    return MOCK_TRADES

@app.get("/api/v1/trades/{trade_id}")
async def get_trade(trade_id: str):
    for t in MOCK_TRADES:
        if t["id"] == trade_id:
            return t
    raise HTTPException(status_code=404, detail="Trade not found")


# ─── Signals ───────────────────────────────────────────────

@app.get("/api/v1/signals/active")
async def active_signals():
    return [s for s in MOCK_SIGNALS if s["is_active"]]

@app.get("/api/v1/signals")
async def get_signals(page: int = 1, limit: int = 50):
    return MOCK_SIGNALS


# ─── Analytics ─────────────────────────────────────────────

@app.get("/api/v1/analytics/performance")
async def performance(period: str = "30d"):
    return MOCK_ANALYTICS

@app.get("/api/v1/analytics/pnl-history")
async def pnl_history(period: str = "30d"):
    return MOCK_ANALYTICS["pnl_history"]

@app.get("/api/v1/analytics/risk")
async def risk_metrics():
    return MOCK_RISK


# ─── Settings ──────────────────────────────────────────────

@app.get("/api/v1/settings")
async def get_settings():
    return {
        "exchange": "Binance",
        "mode": "testnet",
        "risk_level": "moderate",
        "max_positions": 5,
        "default_timeframe": "4H",
        "notifications": True
    }


# ─── Health ────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/v1/health")
async def api_health():
    return {"status": "ok", "version": "1.0.0", "mode": "mock"}


# ─── WebSocket ─────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "data": {"message": "Connected to AlphaStack"}
        })

        # Start price feed task
        async def send_price_updates():
            while True:
                btc_price = 67000 + random.uniform(-500, 500)
                eth_price = 3500 + random.uniform(-50, 50)
                sol_price = 175 + random.uniform(-5, 5)

                await websocket.send_json({
                    "type": "price_update",
                    "data": {
                        "BTC/USDT": round(btc_price, 2),
                        "ETH/USDT": round(eth_price, 2),
                        "SOL/USDT": round(sol_price, 2),
                        "LINK/USDT": round(14.50 + random.uniform(-0.5, 0.5), 4)
                    }
                })
                await asyncio.sleep(2)

        price_task = asyncio.create_task(send_price_updates())

        # Listen for messages
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "subscribe":
                channels = msg.get("channels", [])
                await websocket.send_json({
                    "type": "subscribed",
                    "data": {"channels": channels}
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        price_task.cancel()


# ─── Run ───────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("🚀 AlphaStack Mock API starting on http://0.0.0.0:8000")
    print("📱 Use this URL in your app: http://47.236.53.59:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
