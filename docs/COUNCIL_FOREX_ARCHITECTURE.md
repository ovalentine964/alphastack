# COUNCIL: Forex Architecture Alignment Report

**Reviewer:** Architecture Specialist  
**Date:** 2026-07-16  
**Scope:** FOREX_MT5_INTEGRATION.md vs. actual AlphaStack codebase  
**Files reviewed:** 11 source files + integration report

---

## Executive Summary

The FOREX integration report is **well-researched and architecturally sound** in its broker-layer analysis. It accurately characterizes the `BrokerConnector` ABC, registry, and smart router. However, it **underestimates the blast radius** beyond the broker layer — the live server, trading loop, and market data pipeline are deeply crypto-hardcoded and will require significant refactoring not covered in the report.

**Compatibility Score: 6/10**  
The broker layer is ready (8/10), but the integration surface beyond brokers pulls the score down.

---

## 1. What the Report Got RIGHT

### 1.1 Broker Architecture Assessment — ✅ Accurate

| Report Claim | Reality | Verdict |
|---|---|---|
| `BrokerConnector` ABC has unified async interface | `base.py` implements full ABC: `connect()`, `disconnect()`, `place_order()`, `cancel_order()`, `modify_order()`, `get_positions()`, `get_balance()`, `get_tick()`, `get_bars()` — all async | ✅ Correct |
| `BrokerRegistry` supports register/route/failover | `registry.py` has `register()`, `route_order()`, `route_order_with_failover()`, `connect_all()`, `disconnect_all()` | ✅ Correct |
| `SmartRouter` has cost/fill/latency/reliability scoring | `smart_router.py` implements `BrokerScore` with exactly those 4 dimensions, weighted by `RoutingCriteria` | ✅ Correct |
| `OrderManager` handles lifecycle tracking | `order_manager.py` tracks `PENDING → OPEN → PARTIALLY_FILLED → FILLED / CANCELLED / REJECTED / EXPIRED` with persistence hooks | ✅ Correct |
| Models are broker-agnostic | `models.py` has `BrokerOrder`, `BrokerPosition`, `BrokerBalance`, `BrokerTick`, `BrokerBar` — all clean Pydantic models | ✅ Correct |

### 1.2 MT5 Connector Assessment — ✅ Mostly Accurate

| Report Claim | Reality | Verdict |
|---|---|---|
| ~80% complete, async thread-pool pattern | `MT5Connector` uses `ThreadPoolExecutor` with `run_in_executor()` — correct pattern for sync MT5 lib | ✅ Correct |
| Order type mapping present | `_ORDER_TYPE_MAP` and `_ORDER_TYPE_MAP_SELL` cover MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP | ✅ Correct |
| Hardcoded `1e-5` spread conversion | `_bar_from_tick()` line: `spread=getattr(tick, "spread", 0.0) * 1e-5` and `get_bars()` line: `spread=r["spread"] * 1e-5` | ✅ Correct — should be dynamic |
| No swap tracking | `BrokerPosition` model has no `swap` field; `MT5Connector.get_positions()` doesn't extract `p.swap` | ✅ Correct |
| Missing symbol info helpers | No `get_symbol_info()` method in `MT5Connector` | ✅ Correct |
| Missing leverage helper | No `get_account_leverage()` method | ✅ Correct |
| Missing historical deal retrieval | No `history_deals_get()` wrapper | ✅ Correct |

### 1.3 MQL5 Bridge Assessment — ✅ Accurate

| Report Claim | Reality | Verdict |
|---|---|---|
| ~60% complete, ZeroMQ PAIR socket | `MQL5Bridge` uses `zmq.PAIR` with `bind()` — correct pattern | ✅ Correct |
| Heartbeat management implemented | `_heartbeat_loop()` sends heartbeat and checks timeout | ✅ Correct |
| No malformed JSON error handling | `_receive_loop()` catches generic `Exception`, no JSON schema validation | ✅ Correct |
| Missing reconnection logic | No reconnect on socket disconnect — `_connected` just flips to `False` | ✅ Correct |
| No message sequence numbers | Messages are plain JSON with no `seq` field | ✅ Correct |
| Missing MQL5 EA source code | No `.mq5` file anywhere in the repo — bridge is Python-side only | ✅ Correct |

### 1.4 OANDA Connector Design — ✅ Well-Aligned

The proposed `OandaConnector` correctly extends `BrokerConnector` and maps to its ABC methods. The REST API structure (aiohttp, account-scoped endpoints) is straightforward and compatible.

### 1.5 Symbol Normalizer Concept — ✅ Sound

The canonical `EUR/USD` format with per-broker converters is the right approach. Current code uses different formats (MT5: `EURUSD`, CCXT: `EUR/USD`) — normalizer is needed.

---

## 2. What the Report Got WRONG or MISSED

### 2.1 CRITICAL: Live Server Is Crypto-Hardcoded — ❌ Not Mentioned

**This is the biggest gap in the report.** `live_server.py` is the production entry point and it's deeply hardcoded for Binance/crypto:

```python
# live_server.py — hardcoded crypto everywhere

# Global exchange singleton — Binance only
exchange_public = None  # ccxt.binance()
exchange_testnet = None  # ccxt.binance() with sandbox

# Market data — Binance-only functions
async def _fetch_ohlcv(symbol, timeframe="1h", limit=200):
    ex = _get_exchange()  # Always Binance
    return await asyncio.to_thread(ex.fetch_ohlcv, ...)

async def _build_market_data(symbol: str) -> dict[str, Any]:
    # pip_size hardcoded to 1.0 (crypto assumption)
    pip_size = 1.0
    # ...
    return {"pip_size": pip_size, "pip_value": 1.0, ...}

# Signal generation — hardcoded crypto symbols
async def _generate_signals() -> list[dict[str, Any]]:
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']  # Hardcoded!

# WebSocket — hardcoded crypto symbols
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'LINK/USDT']  # Hardcoded!

# Portfolio — uses Binance for live prices
@app.get("/api/v1/portfolio")
async def portfolio_positions():
    ticker = await asyncio.to_thread(_get_exchange().fetch_ticker, t["symbol"])  # Binance

# Trading — direct Binance testnet execution
@app.post("/api/v1/trades")
async def create_trade(body: TradeCreate):
    if exchange_testnet and body.price is None:
        order = await asyncio.to_thread(exchange_testnet.create_order, ...)  # Binance testnet
```

**Impact:** Even if all broker-layer code is perfect, the live server cannot route to forex brokers without refactoring `_build_market_data()`, `_generate_signals()`, the portfolio endpoint, and the trade execution path.

**Report's blind spot:** The report focuses exclusively on the `brokers/` package and doesn't analyze how `live_server.py` would need to change.

### 2.2 CRITICAL: Trading Loop Has Crypto Assumptions — ⚠️ Understated

`loop.py` issues not addressed in the report:

| Issue | Location | Impact |
|---|---|---|
| Hardcoded crypto symbols | `LoopConfig.symbols` defaults to `["BTC/USDT", "ETH/USDT", "SOL/USDT"]` | Needs forex pairs added |
| Hardcoded quantity `0.001` | `_execute_trade()`: `"quantity": 0.001` | **Breaks forex** — 0.001 BTC is ~$65; 0.001 lot EUR/USD is $10 notional. Need lot-based sizing |
| No pip calculation | Entire loop file | Forex risk depends on pip value, not just price × quantity |
| No lot sizing | No lot calculation anywhere | Forex uses standard/mini/micro lots |
| No session awareness | Loop runs 24/7 | Forex markets close Friday–Sunday; signals during closed hours are useless |
| Drawdown in absolute $ | `INITIAL_CAPITAL = 10000.0` | Works cross-asset, but needs currency normalization for multi-broker |

**Report mentions:** The report proposes `forex_utils.py` with pip/lot helpers, but doesn't explain how the trading loop would *consume* these utilities.

### 2.3 HIGH: BrokerPosition Missing Swap Field — ⚠️ Mentioned But Understated

The report mentions adding `swap` to positions, but doesn't flag that `BrokerPosition.notional_value` is calculated as:

```python
@property
def notional_value(self) -> float:
    return abs(self.quantity * self.current_price)
```

This works for crypto (quantity = BTC amount, price = USDT) but **breaks for forex**:
- Forex `quantity` is in lots (e.g., 1.0)
- Notional = lots × contract_size × price (e.g., 1.0 × 100,000 × 1.0850 = $108,500)
- Without `contract_size`, notional is wrong by 100,000×!

This cascades into `SmartRouter` cost scoring (spread comparison), risk management, and position aggregation.

### 2.4 HIGH: Market Data Pipeline Is Binance-Only — ⚠️ Not Addressed

The report's `_build_market_data()` function (Section 8.1) shows a clean `OandaConnector` but doesn't address:

1. `_build_market_data()` in `live_server.py` calls Binance directly via `_fetch_ohlcv()`
2. The 16-step pipeline (`AlphaStackPipeline`) receives `market_data` dict — its internal steps may assume crypto-specific structures
3. ATR calculation, spread calculation, and pip value are all crypto-hardcoded in the current `_build_market_data()`

**The report needs a `MarketDataRouter`** that delegates to the correct connector based on symbol type.

### 2.5 MEDIUM: SmartRouter Spread Scoring Doesn't Account for Pip Differences — ⚠️

`smart_router.py` scores brokers by spread:

```python
max_spread = max(t.spread for t in tick_data.values()) or 1.0
score.cost_score = 1.0 - (tick.spread / max_spread) if max_spread > 0 else 1.0
```

If comparing crypto spread (e.g., BTC: $0.50) with forex spread (e.g., EUR/USD: 0.00015), the raw values are incomparable. The router needs **spread normalization** (e.g., spread in pips or basis points) before scoring.

### 2.6 MEDIUM: Orchestrator State Doesn't Carry Broker Context — ⚠️

`graph.py` orchestrator passes `AlphaStackState` through nodes. The execution agent (`ExecutionAgent`) presumably routes to brokers, but:

1. No broker preference in signals (e.g., "route EUR/USD to OANDA")
2. No lot sizing in trade decisions
3. Risk agent doesn't account for leverage differences across brokers

### 2.7 MEDIUM: No Currency Conversion Layer — ❌ Not Mentioned

When trading crypto (USD-denominated) and forex (multi-currency) simultaneously:
- P&L from EUR/USD is in USD
- P&L from GBP/JPY needs JPY→USD conversion
- Cross-broker equity calculation needs live FX rates

The report mentions `CrossBrokerRiskManager` but doesn't implement the conversion layer.

### 2.8 LOW: OrderManager Doesn't Handle Forex-Specific Order Fields — ⚠️

`order_manager.py` `update_status()` handles `filled_quantity`, `avg_fill_price`, `commission`, `slippage` — but not:
- `swap` (accumulated swap on position)
- `spread_at_entry` (for cost tracking)
- `margin_required` (for risk management)

These are mentioned in the report's model additions but not in the order manager lifecycle.

### 2.9 LOW: No Forex Calendar Integration — ⚠️ Acknowledged

The report mentions forex calendar integration as a Phase 4 item. The orchestrator's `NewsAgent` would need forex-specific event detection (NFP, FOMC, ECB rate decisions) — currently it's crypto-focused.

---

## 3. Compatibility Matrix

| Component | Compatibility | Changes Needed | Effort |
|---|---|---|---|
| `BrokerConnector` ABC | ✅ 9/10 | None — ABC is clean | None |
| `BrokerRegistry` | ✅ 9/10 | None — works with any connector | None |
| `SmartRouter` | ⚠️ 6/10 | Spread normalization for cross-asset scoring | 1-2 days |
| `OrderManager` | ⚠️ 7/10 | Add forex-specific field handling | 0.5 day |
| `BrokerOrder` model | ⚠️ 7/10 | Add `lot_size`, `pip_value`, `spread_at_entry`, `margin_required` | 0.5 day |
| `BrokerPosition` model | ⚠️ 5/10 | Add `swap`, `contract_size`; fix `notional_value` | 1 day |
| `BrokerBalance` model | ✅ 8/10 | Minor — works as-is | None |
| `BrokerTick` model | ✅ 9/10 | None | None |
| `BrokerBar` model | ✅ 9/10 | None | None |
| `MT5Connector` | ⚠️ 7/10 | Dynamic spread, swap tracking, symbol info, leverage | 2-3 days |
| `MQL5Bridge` | ⚠️ 5/10 | Reconnection, error handling, seq numbers, EA source | 3-5 days |
| `CCXTConnector` | ✅ 9/10 | None — already broker-agnostic | None |
| `TradingLoop` | ❌ 4/10 | Lot sizing, pip calc, session awareness, forex symbols | 3-5 days |
| `live_server.py` | ❌ 3/10 | Market data routing, symbol config, remove Binance hardcoding | 3-5 days |
| Orchestrator (`graph.py`) | ⚠️ 6/10 | Broker-aware routing, lot sizing in risk | 2-3 days |
| `_build_market_data()` | ❌ 2/10 | Complete rewrite needed — currently Binance-only | 2-3 days |

---

## 4. Recommended Implementation Order

The report's Phase 1–4 ordering is reasonable for the broker layer, but misses the integration work. Here's a corrected order:

### Phase 0: Data Model Foundation (2 days)
**Must come first — everything else depends on this.**

1. Update `models.py`:
   - `BrokerPosition`: add `swap: float = 0.0`, `contract_size: float = 1.0`
   - `BrokerPosition.notional_value`: use `quantity * contract_size * current_price`
   - `BrokerOrder`: add `lot_size: float | None`, `pip_value: float | None`, `spread_at_entry: float | None`, `margin_required: float | None`
   - `BrokerBalance`: add `leverage: float = 1.0` (already has `margin_level`)
2. Create `forex_utils.py` (pip calculation, lot sizing, symbol metadata) — per report Section 6.4
3. Create `SymbolNormalizer` — per report Section 6.3
4. Unit tests for all forex utilities

### Phase 1: Market Data Abstraction (3 days)
**Critical missing piece — not in the report.**

1. Create `MarketDataRouter` that delegates to the correct connector:
   - If symbol is forex → use OANDA/MT5 connector for OHLCV
   - If symbol is crypto → use CCXT connector for OHLCV
2. Refactor `_build_market_data()` in `live_server.py` to use `MarketDataRouter`
3. Update `_generate_signals()` to use configurable symbol list (not hardcoded)
4. Update WebSocket endpoint to support forex symbols

### Phase 2: OANDA Connector (3 days)
**Per report Phase 1 — correct priority.**

1. Implement `OandaConnector` (report Section 8.1 is a good starting point)
2. Register in `BrokerRegistry` alongside CCXT
3. Integration tests with OANDA demo account
4. Update `live_server.py` to support OANDA market data

### Phase 3: MT5 Connector Refinement (1 week)
**Per report Phase 2 — correct ordering.**

1. Fix `_bar_from_tick()` spread conversion (dynamic, not `1e-5`)
2. Add `get_symbol_info()` method
3. Add swap tracking to positions
4. Add leverage helper
5. Add historical deal retrieval
6. MQL5 Bridge improvements (reconnection, error handling, seq numbers)
7. Write MQL5 EA source code (`.mq5` file)

### Phase 4: Trading Loop Forex Support (3 days)
**Missing from report — essential for production.**

1. Update `LoopConfig` to support forex symbol configuration
2. Add lot sizing logic to `_execute_trade()`:
   - Calculate position size based on risk %, stop loss distance, and pip value
   - Use `forex_utils.py` for pip/lot calculations
3. Add session awareness (skip forex during market close)
4. Add pip-based risk calculations to debate and reflection

### Phase 5: Cross-Broker Risk & Smart Routing (1 week)
**Per report Phase 3 — correct, but add spread normalization.**

1. Normalize spread scoring in `SmartRouter` (pips for forex, absolute for crypto)
2. Implement `CrossBrokerRiskManager` with currency conversion
3. Add broker-aware routing to orchestrator
4. Update risk agent for leverage-aware calculations

### Phase 6: Advanced (Ongoing)
**Per report Phase 4 — reasonable.**

1. IBKR connector if multi-asset expansion needed
2. Forex calendar integration with `NewsAgent`
3. Swap-aware position management
4. Cross-broker arbitrage detection

---

## 5. Risk Assessment (Updated from Report)

### Risks the Report Underestimates

| Risk | Report Rating | Actual Rating | Reason |
|---|---|---|---|
| Symbol format mismatches | High | **Critical** | Cascades through market data, pipeline, signals, execution — not just broker layer |
| Live server refactoring | Not mentioned | **Critical** | 800+ lines of crypto-hardcoded code |
| Trading loop forex support | Not mentioned | **High** | Hardcoded quantities, symbols, no pip/lot logic |
| Cross-asset spread comparison | Not mentioned | **High** | SmartRouter will make wrong routing decisions |

### Risks the Report Overestimates

| Risk | Report Rating | Actual Rating | Reason |
|---|---|---|---|
| MT5 under Wine instability | Medium | **Low** | Report correctly recommends Windows VPS — Wine is not the production path |
| Thread pool exhaustion | Medium | **Low** | Existing code already uses `ThreadPoolExecutor` with `max_workers=4` |

---

## 6. Specific Code-Level Recommendations

### 6.1 Fix `notional_value` in `models.py`

```python
# CURRENT (broken for forex):
@property
def notional_value(self) -> float:
    return abs(self.quantity * self.current_price)

# PROPOSED:
@property
def notional_value(self) -> float:
    return abs(self.quantity * self.contract_size * self.current_price)
```

### 6.2 Fix `_bar_from_tick()` in `mt5_connector.py`

```python
# CURRENT (hardcoded):
spread=getattr(tick, "spread", 0.0) * 1e-5

# PROPOSED (dynamic):
def _bar_from_tick(tick: Any, symbol_info: Any = None) -> BrokerTick:
    spread_raw = getattr(tick, "spread", 0)
    if symbol_info:
        spread = spread_raw * symbol_info.point
    else:
        spread = spread_raw * 1e-5  # Fallback
    # ...
```

### 6.3 Add `_build_market_data()` abstraction in `live_server.py`

```python
# CURRENT (Binance-only):
async def _build_market_data(symbol: str) -> dict[str, Any]:
    candles_1h = await _fetch_ohlcv(symbol, "1h", 200)  # Always Binance

# PROPOSED (broker-aware):
async def _build_market_data(symbol: str, broker: str = "auto") -> dict[str, Any]:
    connector = _resolve_market_data_broker(symbol, broker)
    candles_1h = await connector.get_bars(symbol, "H1", 200)
    # ...
```

### 6.4 Add lot sizing to `_execute_trade()` in `loop.py`

```python
# CURRENT (crypto-hardcoded):
trade = self._trade_store.create_trade({
    "quantity": 0.001,  # Hardcoded!
    # ...
})

# PROPOSED (forex-aware):
from alphastack.brokers.forex_utils import FOREX_SYMBOLS, calculate_lot_size

if symbol in FOREX_SYMBOLS:
    lot_size = calculate_lot_size(
        account_balance=balance,
        risk_pct=0.01,
        stop_loss_pips=stop_pips,
        symbol=FOREX_SYMBOLS[symbol],
    )
else:
    lot_size = 0.001  # Crypto fallback
```

---

## 7. Verdict

The FOREX integration report is a **solid research document** that correctly identifies the broker-layer architecture as well-designed for multi-broker expansion. Its phased implementation plan for OANDA → MT5 → Multi-broker risk is sound.

However, the report has a **significant blind spot**: it doesn't analyze the integration surface beyond the `brokers/` package. The live server, trading loop, market data pipeline, and orchestrator all contain crypto-specific assumptions that will break or produce incorrect results with forex brokers.

**The report should be updated with:**
1. A Phase 0 for data model and market data abstraction
2. Analysis of `live_server.py` hardcoding
3. Trading loop forex adaptation plan
4. SmartRouter spread normalization
5. Currency conversion layer for cross-broker P&L

**Final compatibility score: 6/10**  
Broker layer: 8/10 | Integration layer: 3/10 | Overall: 6/10

The broker registry pattern is the right foundation. The gap is everything that sits *above* it.
