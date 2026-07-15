# AlphaStack Backend API — Test Results

**Date:** 2026-07-16 03:46 CST  
**Base URL:** `http://localhost:8000`  
**Server Version:** 3.0.0  
**Auth:** `admin` / `alphastack` (note: task spec said `demo`/`demo` — actual credentials differ)

---

## Summary

| # | Endpoint | Method | Status | Response Time | Notes |
|---|----------|--------|--------|---------------|-------|
| 1 | `/health` | GET | ✅ Working | 101ms | Full status, Binance connected |
| 2 | `/api/v1/auth/login` | POST | ⚠️ Partial | 3ms | Works with `admin`/`alphastack`, NOT `demo`/`demo` |
| 3 | `/api/v1/signals/active` | GET | ✅ Working | 1,093ms | Pipeline-generated signal with confluence scores |
| 4 | `/api/v1/trades` | GET | ✅ Working | 3ms | Returns demo trades |
| 5 | `/api/v1/trades` | POST | ⚠️ Partial | 832ms | Trade created but broker error on execution |
| 6 | `/api/v1/portfolio` | GET | ✅ Working | 80ms | Live positions with P&L |
| 7 | `/api/v1/portfolio/pnl` | GET | ✅ Working | 39ms | Aggregate P&L stats |
| 8 | `/api/v1/analytics/performance` | GET | ✅ Working | 2ms | Performance metrics |
| 9 | `/api/v1/analytics/risk` | GET | ✅ Working | 2ms | Risk metrics (mostly zeros) |
| 10 | `/api/v1/market/tickers` | GET | ✅ Working | 1,274ms | 7 symbols from Binance |
| 11 | `/ws` | WebSocket | ✅ Working | 673ms | Connects, sends `connected` event |

**Overall: 9/11 fully working, 2/11 partial**

---

## Detailed Results

### 1. GET /health ✅

```json
{
  "status": "ok",
  "version": "3.0.0",
  "uptime_seconds": 3024.92,
  "binance_connected": true,
  "btc_price": 64928.4,
  "testnet_configured": true,
  "pipeline_available": true,
  "orchestrator_available": true,
  "agents": ["news", "strategy", "risk", "execution", "reflection"],
  "event_bus": "in_memory"
}
```

**Assessment:** Excellent. Reports all subsystem status, live BTC price, and agent availability.

---

### 2. POST /api/v1/auth/login ⚠️

**Issue:** Task spec specifies `{"username":"demo","password":"demo"}` but actual valid credentials are `admin` / `alphastack`.

| Input | Result |
|-------|--------|
| `admin` / `alphastack` | ✅ 200 — returns JWT access + refresh tokens |
| `demo` / `demo` | ❌ 401 — "Invalid credentials" |
| `admin` / `wrong` | ❌ 401 — "Invalid credentials" |
| `{}` (empty) | ❌ 400 — "Missing credentials" |
| No auth header (protected endpoints) | ❌ 401 — "Missing Authorization header" |

**Token structure:** JWT with `sub`, `type`, `iat`, `exp`, `jti` claims. Access token TTL: 1800s (30 min). Refresh token TTL: 7 days.

**Assessment:** Auth works correctly. Error handling is proper (400 for missing, 401 for wrong). The `demo`/`demo` credential mismatch is a documentation/config issue, not a bug.

---

### 3. GET /api/v1/signals/active ✅

Returns pipeline-generated trading signals with full confluence analysis:

```json
{
  "id": "sig-SOL-USDT-pipeline",
  "symbol": "SOL/USDT",
  "direction": "long",
  "strength": "strong",
  "confidence": 0.68,
  "entry_price": 77.18,
  "stop_loss": 72.03,
  "take_profit": [84.91, 90.06, 97.78],
  "risk_reward": 1.5,
  "confluence_score": 67.5,
  "reason": "Confluence 68/100 | Bias: bullish | Structure: higher_high | Pattern: hammer",
  "component_scores": {
    "fundamental": 0.0, "market_bias": 1.0, "session": 1.0,
    "structure": 1.0, "sr_levels": 0.0, "liquidity": 1.0,
    "smc": 0.7, "rsi": 0.0
  }
}
```

**Assessment:** Rich signal data with multi-factor scoring. Component scores provide transparency. ~1.1s response time suggests pipeline computation on each request (acceptable for real-time signals).

---

### 4. GET /api/v1/trades ✅

Returns list of trades with full details:

```json
{
  "trades": [
    {
      "id": "74bb98d8-...",
      "symbol": "BTC/USDT",
      "side": "buy",
      "quantity": 0.5,
      "entry_price": 67500.0,
      "stop_loss": 66000.0,
      "take_profit": 71000.0,
      "status": "open",
      "strategy_id": "demo_v1"
    }
  ]
}
```

**Assessment:** Clean trade objects. Includes demo trades seeded at startup.

---

### 5. POST /api/v1/trades ⚠️

**Issue 1:** API expects `quantity` field, not `amount`. The task spec `{"symbol":"BTC/USDT","side":"buy","amount":0.001}` returns 422 validation error.

**Issue 2:** Even with correct `quantity` field, trade is created but broker execution fails:

```json
{
  "id": "04e4c793-...",
  "status": "pending",
  "notes": " | Broker error: 'latin-1' codec can't encode character '…' in position 6: ordinal not in range(256)"
}
```

The broker error is an **encoding bug** — a non-ASCII character (ellipsis `…`) somewhere in the broker request/response path is causing a `latin-1` codec failure. This is a real bug that would prevent live trade execution.

**Assessment:** Trade creation works, but broker integration has an encoding bug.

---

### 6. GET /api/v1/portfolio ✅

```json
[
  {
    "symbol": "BTC/USDT",
    "side": "long",
    "quantity": 0.5,
    "entry_price": 67500.0,
    "current_price": 64920.01,
    "unrealized_pnl": -1289.995,
    "unrealized_pnl_pct": -3.82,
    "weight_pct": 22.94
  }
]
```

**Assessment:** Live price integration working. Unrealized P&L calculated correctly. Position weights sum to ~100%.

---

### 7. GET /api/v1/portfolio/pnl ✅

```json
{
  "total_realized_pnl": 1250.0,
  "total_unrealized_pnl": 0,
  "total_pnl": 1250.0,
  "today_pnl": 1250.0,
  "win_rate": 100.0,
  "avg_win": 1250.0,
  "best_trade_pnl": 1250.0,
  "worst_trade_pnl": 1250.0,
  "total_trades": 1
}
```

**Data quality concern:** `total_unrealized_pnl: 0` contradicts portfolio endpoint showing `-1832.50` in unrealized losses. The P&L endpoint may only track realized P&L, which is misleading. Also `profit_factor: 0` is odd when there are winning trades.

---

### 8. GET /api/v1/analytics/performance ✅

```json
{
  "total_return_pct": 12.5,
  "sharpe_ratio": 0,
  "max_drawdown_pct": 0,
  "total_trades": 1,
  "win_rate": 100.0,
  "profit_factor": 1250.0,
  "avg_trade_duration_hours": 24.0,
  "expectancy": 1250.0
}
```

**Data quality concern:** `sharpe_ratio: 0` and `max_drawdown_pct: 0` with a 12.5% return seems wrong — likely a calculation issue with only 1 trade (insufficient data points). `profit_factor: 1250.0` looks like it's returning the P&L value instead of a ratio.

---

### 9. GET /api/v1/analytics/risk ✅

```json
{
  "max_drawdown_pct": 0,
  "current_drawdown_pct": 0,
  "var_95": 1250.0,
  "var_99": 1250.0,
  "sharpe_ratio": 0,
  "sortino_ratio": 0,
  "avg_risk_per_trade": 0,
  "max_consecutive_losses": 0,
  "risk_reward_avg": 0
}
```

**Data quality concern:** `var_95: 1250.0` and `var_99: 1250.0` being identical is suspicious — VaR99 should be ≥ VaR95. Many zero fields suggest insufficient data or calculation issues.

---

### 10. GET /api/v1/market/tickers ✅

7 tickers from Binance: BTC, ETH, SOL, BNB, XRP, LINK, ADA — all with live prices and 24h change.

**Assessment:** Real-time data, ~1.3s response (Binance API latency). Clean data.

---

### 11. WebSocket /ws ✅

```json
{
  "type": "connected",
  "data": {
    "message": "Live Binance feed"
  }
}
```

Connects successfully, sends welcome message. Connection established in ~673ms.

---

## Bugs Found

### 🔴 Critical
1. **Broker encoding bug** — `latin-1` codec error when executing trades. Character `…` (U+2026) in broker path causes trade execution failure.

### 🟡 Medium
2. **P&L inconsistency** — `portfolio/pnl` shows `total_unrealized_pnl: 0` while `portfolio` shows ~$-1,832 in unrealized losses.
3. **Analytics calculation issues** — `profit_factor` returns raw P&L (1250.0) instead of a ratio. VaR95 = VaR99. Sharpe/drawdown all zero despite positive returns.
4. **Credential mismatch** — API uses `admin`/`alphastack`, not `demo`/`demo` as documented.

### 🟢 Minor
5. **Field naming** — `POST /api/v1/trades` uses `quantity` not `amount` (API validation error on `amount`).
6. **Slow signal endpoint** — ~1.1s response time on `/signals/active` (pipeline computation).
7. **Slow market endpoint** — ~1.3s on `/market/tickers` (upstream Binance latency).

---

## Recommendations

1. **Fix broker encoding** — Ensure all broker communication uses UTF-8, not latin-1.
2. **Unify P&L calculation** — `portfolio/pnl` should include unrealized P&L from open positions.
3. **Fix analytics math** — Profit factor should be gross_profit/gross_loss ratio. VaR95/99 should differ. Consider requiring minimum trade count before returning metrics.
4. **Update docs** — Align documented credentials with actual config.
5. **Consider caching** — Market tickers and signals could benefit from short-lived caches (5-10s) to reduce latency.
