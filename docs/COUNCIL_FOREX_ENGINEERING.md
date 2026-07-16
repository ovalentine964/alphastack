# FOREX Engineering Feasibility Assessment

**Author:** Engineering Specialist (Subagent)  
**Date:** 2026-07-16  
**Status:** Council Document — For Review

---

## Executive Verdict

**The existing FOREX architecture is ~70% viable but has critical blocking issues.** The research report is sound in its recommendations, but the existing code needs targeted fixes before it can work. The OANDA-first approach is correct. MT5 is feasible but requires external infrastructure. The MQL5 bridge is architecturally right but incomplete — it's missing the EA source code, which is the entire MT5-side of the bridge.

**Bottom line:** We can ship a working OANDA connector in 2–3 days with zero external dependencies. MT5 requires a Windows VPS and ~2 weeks. The research report's timeline is realistic.

---

## 1. MT5Connector: Can It Work As-Is?

### Status: ~80% complete, has 3 blocking bugs

**What works:**
- ✅ Async thread-pool pattern (`ThreadPoolExecutor`) — correct, MT5 Python lib is synchronous
- ✅ Order type mapping (buy/sell → limit/stop/stop-limit) — complete
- ✅ Account info, positions, bars, ticks — all implemented
- ✅ Config integration (`MT5Settings` in `config.py`) — done
- ✅ Lazy import of `MetaTrader5` — won't crash on Linux without it installed
- ✅ Connection state machine — follows `BrokerConnector` ABC correctly

**Blocking bugs:**

| # | Bug | Severity | Fix |
|---|-----|----------|-----|
| 1 | **Spread conversion is hardcoded** `1e-5` | HIGH | `_bar_from_tick()` and `get_bars()` both use `spread * 1e-5`. This assumes 5-digit pairs. JPY pairs use 3 digits (pip = 0.01, point = 0.001). Metals like XAU/USD use 2 digits. Will produce wrong spread values for ~40% of instruments. |
| 2 | **No `swap` field on `BrokerPosition`** | MEDIUM | MT5 positions have `.swap` (accumulated rollover). The existing `get_positions()` doesn't extract it. `BrokerPosition` model has no `swap` field. Overnight forex positions silently lose swap tracking. |
| 3 | **Missing `deviation` (slippage) parameter** | MEDIUM | `place_order()` doesn't set `deviation` in the order request. MT5 will use terminal default (often 0 = no slippage tolerance), causing frequent rejections in volatile markets. |

**Non-blocking gaps (nice-to-have):**
- No `get_symbol_info()` helper for pip size, contract size, lot limits
- No historical deal/order retrieval (`history_deals_get`)
- No leverage query helper
- `_bar_from_tick` doesn't populate `last` correctly when `tick.last` is 0 (common for forex — only bid/ask)

**Verdict:** Needs ~2 hours of targeted fixes. Not a rewrite.

---

## 2. MQL5 Bridge: Is the ZeroMQ Approach Correct?

### Status: ~60% complete — architecture is right, critical piece missing

**What works:**
- ✅ ZeroMQ PAIR socket pattern — correct for 1:1 EA ↔ Python communication
- ✅ Heartbeat management with timeout detection
- ✅ Signal/action enum covers all trade types
- ✅ Position and account info dataclasses defined
- ✅ Message serialization (JSON over ZMQ)
- ✅ Callback registration for trade updates

**What's critically missing:**

| # | Gap | Impact |
|---|-----|--------|
| 1 | **No MQL5 Expert Advisor source code** | **BLOCKER.** The bridge is Python-only. The EA that runs inside MT5 and speaks ZMQ doesn't exist. This is literally half the bridge. Without it, the bridge does nothing. |
| 2 | **No reconnection logic** | If the EA disconnects, `_receive_loop` just logs errors and sleeps 0.1s forever. No exponential backoff, no socket recreation. |
| 3 | **No message sequence numbers** | ZMQ PAIR doesn't guarantee ordering after reconnection. Missing sequence numbers means we can't detect message loss or reorder. |
| 4 | **No malformed JSON handling** | `_handle_message` does `json.loads(message)` with no try/except around individual field parsing. One bad field crashes the handler. |
| 5 | **Position sync is pull-only** | `get_positions()` sends a request and returns `self._positions.copy()` immediately — before the EA responds. Race condition. Needs a request/response pattern with correlation IDs. |
| 6 | **`get_account_info()` same race condition** | Returns `_account_info` immediately after sending request, before EA response arrives. |

**Architectural assessment:**

The ZMQ PAIR pattern is the right choice for this use case. Alternatives considered:
- **REQ/REP:** Too rigid — Python must wait for response before sending next message
- **PUB/SUB:** Wrong — we need bidirectional command/response
- **PAIR:** ✅ Correct — both sides can send/receive freely

However, the bridge needs a **request/response correlation layer** on top of PAIR:
```
Python sends: {"id": "req_001", "action": "get_positions"}
EA responds:  {"id": "req_001", "type": "positions", "positions": [...]}
```

**The EA itself** needs to:
1. Connect to the PAIR socket from MT5 side
2. Monitor `OnTick()` for price pushes
3. Execute trade signals from Python
4. Push position/account updates
5. Respond to heartbeat pings

This is ~200–300 lines of MQL5 code. Not trivial but well-documented.

**Verdict:** Bridge needs the EA written + reconnection/sequencing fixes. ~3–5 days of work.

---

## 3. Package Dependencies to Add

### Currently in `requirements.txt`:
```
ccxt, fastapi, uvicorn, pydantic, pydantic-settings, langchain-core, langgraph,
python-telegram-bot, PyJWT, prometheus-client, argon2-cffi, pyotp, httpx,
redis, gunicorn, structlog, cryptography
```

### Must add:

| Package | Purpose | Priority | Size |
|---------|---------|----------|------|
| `aiohttp` | HTTP client for OANDA REST API | 🔴 Required | Already transitive dep of many packages |
| `pyzmq` | ZeroMQ bindings for MQL5 Bridge | 🔴 Required (MT5 only) | ~2MB |
| `MetaTrader5` | MT5 Python API | 🟡 Optional (Windows only) | ~5MB |
| `oandapyV20` | OANDA v20 Python client | 🟢 Optional (we can use raw HTTP) | ~50KB |

### Recommended additions:

| Package | Purpose | Priority |
|---------|---------|----------|
| `websockets` | OANDA streaming prices (alternative to `aiohttp` chunked) | 🟡 Medium |
| `ib_insync` | Interactive Brokers (future) | 🟢 Low (Phase 4) |

### What we DON'T need:
- ~~`oandapyV20`~~ — The research report suggests it, but `aiohttp` + raw REST is cleaner and avoids a dependency with questionable maintenance. The OANDA v20 API is simple REST.
- ~~`fxcmpy`~~ — Not recommended as first integration
- ~~`quickfix`~~ — LMAX FIX protocol is too complex for MVP

### `requirements.txt` additions:
```
aiohttp>=3.9.0
pyzmq>=25.0.0
```

That's it for MVP. Two packages.

---

## 4. Code vs. External Dependencies: What's Writeable Now

### ✅ Can build NOW (no external dependencies):

| Component | Files | Effort | Notes |
|-----------|-------|--------|-------|
| **`forex_utils.py`** | New file | 1 day | Pip calc, lot sizes, symbol metadata — pure Python, no deps |
| **`SymbolNormalizer`** | New file or in `forex_utils.py` | 0.5 day | Symbol format conversion — pure Python |
| **`OandaConnector`** | New file | 2 days | REST API via `aiohttp` — no OANDA account needed for code |
| **Broker model updates** | Edit `models.py` | 0.5 day | Add `swap`, `spread_at_entry`, `margin_required` fields |
| **Config updates** | Edit `config.py` | 0.5 day | Add `OandaSettings` class |
| **MT5Connector fixes** | Edit existing | 2 hours | Fix spread, add deviation, add swap extraction |
| **MQL5 Bridge fixes** | Edit existing | 1 day | Reconnection, sequencing, error handling |
| **Unit tests** | New files | 1 day | Mock-based tests for all connectors |
| **Symbol normalizer tests** | New files | 0.5 day | Test all broker format conversions |

### ⚠️ Needs external setup:

| Component | Dependency | Setup Effort | Cost |
|-----------|-----------|-------------|------|
| **OANDA demo account** | OANDA website signup | 30 min | Free |
| **OANDA integration tests** | Demo account + API key | 1 hour | Free |
| **MT5 demo account** | Broker signup + MT5 install | 1 hour | Free |
| **MT5 Windows VPS** | AWS/Azure/Vultr Windows instance | 2 hours | $10–30/mo |
| **MQL5 EA testing** | MT5 terminal + Strategy Tester | 1 day | Free (demo) |
| **OANDA streaming prices** | Demo account | 1 hour | Free |

### ❌ Cannot build without external resources:

| Component | Why |
|-----------|-----|
| MQL5 Expert Advisor | Needs MQL5 IDE (MetaEditor) — Windows only |
| Live order execution testing | Needs funded or demo broker account |
| Spread/slippage validation | Needs real market data |
| Swap rate verification | Needs live positions held overnight |

---

## 5. Minimum Viable Forex Integration (MVP)

### Scope: "AlphaStack can trade one forex pair via OANDA demo account"

```
MVP = OandaConnector + forex_utils + SymbolNormalizer + model updates
```

### What MVP includes:

1. **`forex_utils.py`** — Core forex calculations
   - `ForexSymbol` dataclass with pip size, contract size, lot limits
   - Pip value calculation (quote-currency pairs)
   - Lot size validation (min/max/step)
   - Predefined symbol specs for 15 major/minor pairs + metals

2. **`SymbolNormalizer`** — Canonical symbol handling
   - `EUR/USD` ↔ `EURUSD` (MT5) ↔ `EUR_USD` (OANDA) ↔ `EUR.USD` (IBKR)
   - Validation that symbol exists in known set

3. **`OandaConnector`** — Full OANDA v20 REST integration
   - `connect()` / `disconnect()` with API key auth
   - `place_order()` — market + limit orders with SL/TP
   - `cancel_order()` / `modify_order()`
   - `get_positions()` — open positions
   - `get_balance()` — account summary
   - `get_tick()` — latest bid/ask
   - `get_bars()` — historical OHLCV

4. **Model updates** to `brokers/models.py`:
   - `swap: float` on `BrokerPosition`
   - `spread_at_entry: float` on `BrokerOrder`
   - `lot_size: float` on `BrokerOrder` (optional)

5. **Config update** to `config.py`:
   - `OandaSettings` with `account_id`, `access_token`, `environment`

6. **Tests**:
   - Unit tests with mocked OANDA responses
   - `forex_utils` calculation tests
   - `SymbolNormalizer` round-trip tests

### What MVP excludes:
- ❌ MT5 integration (Phase 2)
- ❌ MQL5 Bridge (Phase 2)
- ❌ Cross-broker risk management (Phase 3)
- ❌ SmartRouter forex routing (Phase 3)
- ❌ Streaming prices (can poll initially)
- ❌ IBKR (Phase 4)

### MVP delivery: 3–4 days

---

## 6. Testing Without a Live Broker

### What's testable NOW (no broker needed):

| Test Type | Coverage | How |
|-----------|----------|-----|
| **Unit tests for `forex_utils`** | Pip calculation, lot validation, symbol metadata | Pure Python, pytest |
| **Unit tests for `SymbolNormalizer`** | All format conversions | Pure Python, pytest |
| **OANDA connector with mocks** | All API calls, error handling, response parsing | Mock `aiohttp` responses with realistic OANDA JSON |
| **MT5 connector with mocks** | Order mapping, tick conversion, bar parsing | Mock `MetaTrader5` module |
| **MQL5 bridge with mocks** | Signal serialization, message handling, heartbeat | Mock ZMQ socket |
| **Integration: connector ↔ registry** | Registration, routing, state management | Mock connectors, real registry |
| **Integration: connector ↔ event bus** | Event emission on trade/position changes | Mock connector, real EventBus |
| **Model serialization** | `BrokerOrder`/`BrokerPosition` round-trip | Pydantic model tests |

### What needs a demo account:

| Test Type | Coverage | Broker |
|-----------|----------|--------|
| **OANDA connectivity** | Auth, rate limits, error codes | OANDA demo (free) |
| **OANDA order lifecycle** | Place → fill → cancel flow | OANDA demo |
| **OANDA market data** | Tick + bar accuracy | OANDA demo |
| **MT5 connectivity** | Init, login, symbol discovery | MT5 demo broker |
| **MT5 order execution** | Market/limit/stop orders | MT5 demo |
| **Bridge end-to-end** | Python → ZMQ → EA → MT5 → response | MT5 demo + Windows VPS |

### What needs live market conditions:

| Test Type | When |
|-----------|------|
| Spread behavior during news | NFP, CPI releases |
| Slippage under volatility | High-impact events |
| Swap calculation accuracy | Hold positions overnight |
| Margin call behavior | Deliberately over-leverage demo |
| Weekend gap handling | Hold over weekend |

### Recommended testing strategy:

```
Phase 1 (NOW):     Unit tests with mocks → 80% code coverage
Phase 2 (Day 3):   OANDA demo integration tests → validate API contract
Phase 3 (Week 2):  MT5 demo tests on Windows VPS → validate execution
Phase 4 (Week 4):  Paper trading with real market conditions → validate edge cases
```

---

## 7. Specific Code Issues Found

### MT5Connector bugs (exact locations):

**Bug 1 — Hardcoded spread conversion** in `_bar_from_tick()`:
```python
# BROKEN: assumes 5-digit pairs
spread=getattr(tick, "spread", 0.0) * 1e-5,

# FIX: use symbol_info.point dynamically
# Requires passing symbol_info or caching point sizes
```

Same bug in `get_bars()`:
```python
# BROKEN:
spread=r["spread"] * 1e-5,

# FIX: cache symbol point sizes at connect time
```

**Bug 2 — No deviation in `place_order()`**:
```python
# MISSING from req dict:
"deviation": 10,  # Max slippage in points — critical for forex
```

**Bug 3 — `_bar_from_tick` doesn't use `last` properly**:
```python
# Current: last=getattr(tick, "last", 0.0)
# Forex ticks often have last=0.0 (no "last" trade, only bid/ask)
# Should fall back to mid:
last = getattr(tick, "last", 0.0) or ((tick.bid + tick.ask) / 2)
```

### MQL5Bridge issues (exact locations):

**Issue 1 — Race condition in `get_positions()`** (line ~160):
```python
async def get_positions(self) -> dict[int, MT5TradeStatus]:
    await self._socket.send_string(...)  # Send request
    return self._positions.copy()         # Return BEFORE response arrives!
```

**Fix:** Add correlation ID and asyncio.Event:
```python
async def get_positions(self) -> dict[int, MT5TradeStatus]:
    req_id = str(uuid.uuid4())
    self._pending[req_id] = asyncio.Event()
    await self._socket.send_string(json.dumps({"action": "get_positions", "id": req_id}))
    await asyncio.wait_for(self._pending[req_id].wait(), timeout=5.0)
    return self._positions.copy()
```

**Issue 2 — No reconnection** in `_receive_loop()`:
```python
# Current: just logs error and sleeps 0.1s forever
# Fix: detect socket failure, recreate socket, re-bind
```

### OANDA connector (from research report):

The code example in the research report is a good starting point but has issues:
- Uses `aiohttp.ClientSession` without context manager — session leak on error
- No rate limiting (OANDA: 120 req/s is generous but should still limit)
- No pagination for large position/history queries
- Streaming price endpoint uses chunked HTTP, not WebSocket — needs different handling

---

## 8. Risk Assessment

### Technical risks:

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| MT5 Python lib fails under Wine | Medium | High | Use Windows VPS instead (recommended) |
| OANDA rate limits hit during backtesting | Low | Medium | Add rate limiter (like `_RateLimiter` in CCXT) |
| Symbol normalization errors | Low | Critical | Comprehensive test suite + validation at order time |
| ZMQ message loss | Low | High | Add sequence numbers + ACK pattern |
| EA crashes silently | Medium | High | Heartbeat timeout + auto-reconnect + alerts |

### Operational risks:

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| OANDA demo account expires | Low | Low | Re-register, data is ephemeral anyway |
| Windows VPS cost escalation | Low | Low | $10–30/mo is negligible for trading |
| Broker API changes | Low | Medium | Pin API versions, monitor changelogs |

---

## 9. Recommendations to Council

### Immediate actions (this sprint):

1. **Fix MT5Connector bugs** — 2 hours, no dependencies, unblocks future work
2. **Create `forex_utils.py`** — pure Python, no external deps, foundation for everything
3. **Create `SymbolNormalizer`** — prevents symbol format bugs across all future connectors
4. **Add `aiohttp` and `pyzmq` to `requirements.txt`** — minimal additions
5. **Update `BrokerPosition` and `BrokerOrder` models** — add swap/spread fields

### This week:

6. **Build `OandaConnector`** — can be fully coded, tested with mocks, ready for demo account
7. **Write unit tests** — mock-based, no broker needed

### Next week:

8. **Sign up for OANDA demo account** — free, 30 minutes
9. **Integration test OANDA** — validate against real API
10. **Write MQL5 Expert Advisor** — requires MetaEditor (Windows)

### Phase 2 (weeks 3–4):

11. **Deploy MT5 on Windows VPS**
12. **Refine MQL5 Bridge** — reconnection, sequencing
13. **End-to-end MT5 testing**

### Architecture decision needed from council:

**OANDA uses netting (one position per symbol), not hedging.** This means:
- If you buy 0.1 lots EUR/USD, then sell 0.05 lots, you have 0.05 lots long (not two positions)
- This differs from MT5 which supports hedging (both positions exist)
- The `BrokerPosition` model needs to handle both paradigms
- Recommendation: Add `position_mode: Literal["netting", "hedging"]` to connector config

---

## Appendix: File Inventory

### Files to CREATE:

| File | Purpose | Lines (est) |
|------|---------|-------------|
| `src/alphastack/brokers/forex_utils.py` | Pip calc, lot sizes, symbol metadata | ~200 |
| `src/alphastack/brokers/symbol_normalizer.py` | Canonical ↔ broker symbol conversion | ~80 |
| `src/alphastack/brokers/oanda_connector.py` | OANDA v20 REST connector | ~350 |
| `tests/brokers/test_forex_utils.py` | Unit tests | ~150 |
| `tests/brokers/test_symbol_normalizer.py` | Unit tests | ~80 |
| `tests/brokers/test_oanda_connector.py` | Mock-based tests | ~200 |
| `tests/brokers/test_mt5_connector.py` | Mock-based tests | ~150 |
| `mql5/AlphaStackBridge.mq5` | Expert Advisor source | ~300 |

### Files to EDIT:

| File | Changes |
|------|---------|
| `src/alphastack/brokers/models.py` | Add `swap`, `spread_at_entry` fields |
| `src/alphastack/brokers/mt5_connector.py` | Fix spread, add deviation, add swap |
| `src/alphastack/brokers/mql5_bridge.py` | Reconnection, sequencing, error handling |
| `src/alphastack/core/config.py` | Add `OandaSettings` |
| `requirements.txt` | Add `aiohttp`, `pyzmq` |

---

*End of engineering assessment.*
