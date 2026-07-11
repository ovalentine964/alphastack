# Review 9: MT5 & Broker Integration Architecture — Correctness & Feasibility Assessment

**Reviewer:** Architecture Review Agent (MT5 Integration Focus)
**Date:** 2026-07-11
**Documents Reviewed:**
- `alphastack/architecture/architecture_broker.md` — Broker Abstraction Layer
- `architecture_crypto.md` — Crypto-Specific Trading Architecture
- `architecture_broker_routing.md` — Broker Routing Architecture

**Verdict: CONDITIONAL PASS — High-quality architecture with critical issues requiring resolution before implementation.**

---

## Executive Summary

The three architecture documents present a well-structured, modular broker abstraction layer that correctly identifies the key challenges of multi-broker, multi-asset trading. The design principles (plugin architecture, event-driven, stateless core, failover by default) are sound. However, there are **3 critical bugs**, **5 high-severity issues**, and **12 medium-severity issues** that must be addressed. The MT5-on-Linux strategy is the single largest feasibility risk.

| Severity | Count | Summary |
|----------|-------|---------|
| 🔴 Critical | 3 | MT5 pending order pricing bug, balance iterator bug, docker-compose platform directive |
| 🟠 High | 5 | MT5 on Linux fragility, CCXT streaming hardcoded, no post-trade reconciliation, symbol mapping gaps, no order size validation |
| 🟡 Medium | 12 | Filling mode assumptions, GIL contention, credential memory, event bus scalability, etc. |
| 🔵 Low | 8 | Style, documentation, minor improvements |

---

## 1. MT5 Python Library Integration — CORRECTNESS

### 1.1 Overall Assessment: **Mostly Correct, 1 Critical Bug**

The `MetaTrader5` Python package usage is largely accurate. The synchronous-to-async wrapping via `ThreadPoolExecutor` is the correct pattern. Key API calls (`mt5.initialize()`, `mt5.login()`, `mt5.order_send()`, `mt5.symbol_info_tick()`, `mt5.account_info()`, `mt5.positions_get()`, `mt5.terminal_info()`) are used correctly.

### 1.2 🔴 CRITICAL: Pending Order Pricing Bug

```python
# In MT5Connector._place_order_sync():
tick = mt5.symbol_info_tick(mt5_symbol)
price = order.price or (tick.ask if order.side == OrderSide.BUY else order.tick.bid)
```

**Problem:** For LIMIT and STOP orders, if `order.price` is set (which it should be), this code correctly uses it. But the fallback uses `tick.ask/tick.bid`, which is **market price** — defeating the purpose of a pending order. More critically, for STOP orders, the stop price must be at a specific distance from market price (broker-dependent). The code doesn't validate that the pending price is valid relative to current market price.

**Impact:** Pending orders could be submitted at market price (immediate execution) or rejected by the broker for invalid price levels.

**Fix:**
```python
if order.order_type == OrderType.MARKET:
    tick = mt5.symbol_info_tick(mt5_symbol)
    price = tick.ask if order.side == OrderSide.BUY else tick.bid
elif order.order_type in (OrderType.LIMIT, OrderType.STOP):
    if not order.price:
        raise BrokerError(self.broker_id, f"{order.order_type.value} order requires a price")
    price = order.price
    # Validate price vs market
    tick = mt5.symbol_info_tick(mt5_symbol)
    if order.order_type == OrderType.LIMIT:
        if order.side == OrderSide.BUY and price >= tick.ask:
            raise BrokerError(self.broker_id, "Buy limit must be below ask")
        elif order.side == OrderSide.SELL and price <= tick.bid:
            raise BrokerError(self.broker_id, "Sell limit must be above bid")
```

### 1.3 🟠 HIGH: No Order Size Validation

The MT5 connector doesn't validate order quantity against broker-specific constraints before submission:

```python
# Missing: volume validation
info = mt5.symbol_info(mt5_symbol)
if info is None:
    raise BrokerError(...)
if order.quantity < info.volume_min:
    raise BrokerError(...)
if order.quantity > info.volume_max:
    raise BrokerError(...)
if info.volume_step > 0 and order.quantity % info.volume_step != 0:
    raise BrokerError(...)
```

**Impact:** Broker will reject orders with invalid lot sizes. Some brokers silently round, leading to unexpected position sizes.

### 1.4 🟡 MEDIUM: Hard-Coded Filling Mode

```python
"type_filling": mt5.ORDER_FILLING_IOC,
```

**Problem:** Not all MT5 brokers support `ORDER_FILLING_IOC`. FXPesa and other brokers may require `ORDER_FILLING_RETURN` or `ORDER_FILLING_FOK`. The filling mode must be determined from `symbol_info().filling_mode` bitmask at runtime.

**Fix:**
```python
info = mt5.symbol_info(mt5_symbol)
if info.filling_mode & mt5.SYMBOL_FILLING_IOC:
    filling = mt5.ORDER_FILLING_IOC
elif info.filling_mode & mt5.SYMBOL_FILLING_FOK:
    filling = mt5.ORDER_FILLING_FOK
else:
    filling = mt5.ORDER_FILLING_RETURN
```

### 1.5 🟡 MEDIUM: Hard-Coded Deviation

```python
"deviation": 30,  # 3 pips max slippage
```

**Problem:** 30 points = 3 pips on 5-digit brokers, but this should be configurable per-symbol and per-strategy. For volatile pairs or news events, 3 pips may be too tight; for scalping, it may be too wide.

### 1.6 🟡 MEDIUM: No Magic Number Management

```python
"magic": 202607,
```

**Problem:** Hard-coded magic number prevents multiple Alpha Stack instances from coexisting on the same MT5 account. Should be derived from configuration or instance ID.

### 1.7 🟡 MEDIUM: Symbol Suffix Handling

MT5 brokers commonly append suffixes: `EURUSD.r`, `EURUSDm`, `EURUSD.pro`, `EURUSD+`. The static `SYMBOL_MAP` won't handle these. Need dynamic symbol discovery:

```python
def _discover_symbols(self):
    """Dynamically map normalized symbols to broker's native symbols."""
    all_symbols = mt5.symbols_get()
    for sym in all_symbols:
        # Strip common suffixes and match
        base = sym.name.rstrip('.rmpro+0123456789')
        if base in self.SYMBOL_MAP_REVERSE:
            self._dynamic_map[self.SYMBOL_MAP_REVERSE[base]] = sym.name
```

### 1.8 🟡 MEDIUM: Time-in-Force Assumptions

```python
"type_time": mt5.ORDER_TIME_GTC,
```

**Problem:** Some MT5 brokers don't support GTC for all order types. Forex brokers may enforce DAY orders. Need broker-specific TIF configuration.

---

## 2. Linux (Pop!_OS) Feasibility — HIGH RISK

### 2.1 The Core Problem

The `MetaTrader5` Python package is **Windows-only**. It depends on the MT5 terminal process (`terminal64.exe`) for all API communication. There is no native Linux MT5 terminal.

### 2.2 Deployment Options Assessment

| Option | Feasibility | Reliability | Latency | Complexity |
|--------|------------|-------------|---------|------------|
| **Wine/Bottles** | ⚠️ Fragile | ❌ Low | ⚠️ Medium | Medium |
| **Windows VM (VirtualBox/KVM)** | ✅ Works | ✅ High | ⚠️ Medium | High |
| **Remote Windows VPS** | ✅ Best | ✅ High | ⚠️ Network-dependent | Low |
| **Docker Windows container** | ❌ Requires Windows host | N/A | N/A | N/A |

### 2.3 🔴 CRITICAL: Docker Compose `platform` Directive

```yaml
mt5-bridge:
    build: ./mt5-bridge
    platform: windows  # ← INVALID
```

**Problem:** `platform` in docker-compose is for selecting the build platform (e.g., `linux/amd64`, `linux/arm64`), NOT for running Windows containers on Linux. You cannot run Windows containers on a Linux Docker host. This configuration will fail.

**Fix:** Remove the `platform: windows` directive. The MT5 bridge must run as a separate Windows process (VM or VPS), not as a Docker container on the Linux host. The architecture correctly identifies this with the `MT5_BRIDGE_URL: ws://mt5-bridge:8765` WebSocket bridge pattern, but the Docker configuration is misleading.

### 2.4 Recommended Architecture for Linux

```
┌─────────────────────────────────────────┐
│  Pop!_OS Host (Alpha Stack Core)        │
│                                         │
│  ┌───────────┐  ┌───────────┐          │
│  │ Core API  │  │ CCXT      │          │
│  │ (Python)  │  │ Connectors│          │
│  └─────┬─────┘  └───────────┘          │
│        │                                │
│  ┌─────▼─────────────────────┐         │
│  │  MT5 Bridge Client (WS)   │         │
│  │  Reconnects automatically │         │
│  └─────┬─────────────────────┘         │
└────────┼────────────────────────────────┘
         │ WebSocket (wss://)
         ▼
┌─────────────────────────────────────────┐
│  Windows VM / VPS                       │
│                                         │
│  ┌─────────────────────────────┐       │
│  │  MT5 Bridge Server (Python) │       │
│  │  + MetaTrader5 terminal     │       │
│  │  + MT5 Python package       │       │
│  └─────────────────────────────┘       │
└─────────────────────────────────────────┘
```

### 2.5 Wine/Bottles Risk Assessment

If pursuing Wine:
- MT5 terminal may run under Wine, but the Python package's COM/process communication is unreliable
- File paths (`C:\...`) must be mapped through Wine prefixes
- Network access may require Wine registry hacks
- Updates to MT5 terminal can break Wine compatibility at any time
- **Recommendation: Do NOT use Wine for production trading.** Use a Windows VM or VPS.

### 2.6 🟠 HIGH: MT5 Bridge Is Not Specified

The architecture references `MT5_BRIDGE_URL: ws://mt5-bridge:8765` but provides no specification for the bridge protocol. This is a non-trivial component that needs:

- Message format (JSON-RPC, custom binary, protobuf?)
- Authentication (how does the bridge authenticate to MT5?)
- Heartbeat and reconnection logic
- Error propagation (how do MT5 errors get back to the core?)
- Latency overhead measurement
- Fallback behavior when bridge is down

---

## 3. CCXT Integration — CORRECTNESS

### 3.1 Overall Assessment: **Correct with Notable Gaps**

The CCXT integration is well-structured. The async usage (`ccxt.async_support`), exchange initialization, and order placement patterns are correct.

### 3.2 🟠 HIGH: Streaming Hardcoded to Binance

```python
async def subscribe_ticker(self, symbol: str) -> AsyncIterator[UnifiedTicker]:
    import ccxt.pro as ccxtpro
    exchange_pro = ccxtpro.binance({  # ← HARDCODED
        "apiKey": self._credentials.api_key,
        "secret": self._credentials.api_secret,
    })
```

**Problem:** The streaming method creates a new `ccxtpro.binance` instance regardless of which exchange this connector represents. If the connector is for Bybit, it will still try to connect to Binance's WebSocket.

**Fix:**
```python
async def subscribe_ticker(self, symbol: str) -> AsyncIterator[UnifiedTicker]:
    import ccxt.pro as ccxtpro
    exchange_class = getattr(ccxtpro, self._credentials.endpoint, None)
    if exchange_class is None:
        raise BrokerError(self.broker_id, f"Streaming not supported for {self._credentials.endpoint}")
    
    exchange_pro = exchange_class({
        "apiKey": self._credentials.api_key,
        "secret": self._credentials.api_secret,
    })
    # ...
```

### 3.3 🟡 MEDIUM: Balance Iterator Bug

```python
async def get_balance(self) -> list[UnifiedBalance]:
    balance = await self._exchange.fetch_balance()
    result = []
    for currency, data in balance.items():
        if isinstance(data, dict) and data.get("total", 0) and data["total"] > 0:
            result.append(UnifiedBalance(
                currency=currency,
                # ...
            ))
```

**Problem:** `fetch_balance()` returns a dict where keys include `'info'`, `'free'`, `'used'`, `'total'` (metadata) alongside actual currency codes (`'BTC'`, `'ETH'`, `'USDT'`). The code will try to process metadata keys as currencies.

**Fix:**
```python
for currency, data in balance.items():
    if currency in ('info', 'free', 'used', 'total', 'timestamp', 'datetime', 'nonce'):
        continue
    if isinstance(data, dict) and data.get("total", 0) and data["total"] > 0:
        # ...
```

### 3.4 🟡 MEDIUM: Stop-Loss/Take-Profit Portability

```python
params = {}
if order.stop_loss:
    params["stopLoss"] = {"triggerPrice": order.stop_loss}
if order.take_profit:
    params["takeProfit"] = {"triggerPrice": order.take_profit}
```

**Problem:** The `stopLoss`/`takeProfit` param format is exchange-specific. Binance uses `stopPrice`, Bybit uses `stopLoss`/`takeProfit` with different structures, OKX uses `algoOrdParams`. CCXT's unified API doesn't fully normalize these.

**Fix:** Needs exchange-specific param formatting, ideally driven by a config or the CCXT exchange's `has` capabilities dict.

### 3.5 🟡 MEDIUM: Symbol Conversion is USDT-Only

```python
def _to_broker_symbol(self, normalized: str) -> str:
    mapping = self._credentials.additional.get("symbol_map", {})
    return mapping.get(normalized, normalized)
```

The fallback just passes through the normalized symbol, but normalized uses `/USD` while most exchanges use `/USDT`. Need automatic USD→USDT mapping for stablecoin-quote exchanges:

```python
def _to_broker_symbol(self, normalized: str) -> str:
    mapping = self._credentials.additional.get("symbol_map", {})
    if normalized in mapping:
        return mapping[normalized]
    # Auto-map USD to USDT for stablecoin-quote exchanges
    if "/USD" in normalized and self._credentials.additional.get("quote_currency") == "USDT":
        return normalized.replace("/USD", "/USDT")
    return normalized
```

### 3.6 🔵 LOW: Missing Exception Types

The CCXT connector catches `InsufficientFunds`, `InvalidOrder`, `NetworkError`, and `ExchangeNotAvailable`, but misses:
- `DDoSProtection` (rate limit exceeded)
- `RequestTimeout` (timeout, distinct from network error)
- `AuthenticationError` (expired API key)
- `ExchangeError` (catch-all for exchange-specific errors)

---

## 4. Smart Order Routing — FEASIBILITY

### 4.1 Overall Assessment: **Feasible but Needs Real-World Calibration**

The routing architecture is well-designed. The composite scoring formula, failover state machine, and arbitrage detection are all theoretically sound. However, several implementation details need attention.

### 4.2 🟡 MEDIUM: Scoring Latency

```python
async def _score_broker(self, broker_id: str, order: UnifiedOrder) -> float:
    connector = self._registry.get_connector(broker_id)
    ticker = await connector.get_ticker(order.symbol)  # ← LIVE API CALL
```

**Problem:** Every routing decision makes live API calls to all candidate brokers. For N brokers, this is N API calls per order. With rate limits and network latency, this adds 100-500ms to every order.

**The architecture_broker_routing.md correctly identifies the solution:** "Score aggregation & decay" with exponential smoothing and cached scores updated every 5 seconds. But the `architecture_broker.md` implementation doesn't implement this caching.

**Fix:** Implement a `ScoreCache` that updates scores periodically (every 5-10s) and serves cached scores for routing decisions.

### 4.3 🟡 MEDIUM: Liquidity and Fee Scores Are Placebos

```python
fee_score = 0.8  # Default; override from connector capabilities
liquidity_score = 0.7  # Default; would need orderbook depth analysis
```

**Problem:** Two of the five scoring factors are hard-coded constants, reducing the router's effectiveness to only spread, latency, and reliability.

### 4.4 🟡 MEDIUM: Arbitrage Execution Race Condition

The arbitrage detector identifies opportunities based on cached prices, but by the time both legs execute, prices may have moved. The `architecture_broker_routing.md` specifies timing constraints (`max_leg_skew_ms: 50`), but the `architecture_broker.md` implementation has no such guard.

**Risk:** Leg A fills at the arb price, but by the time Leg B submits, the price has moved, resulting in a net loss.

### 4.5 ✅ Strength: Failover Design

The failover state machine (CLOSED → OPEN → HALF_OPEN) is well-designed. The `FailoverManager` in `architecture_broker_routing.md` with degradation thresholds (2 failures = DEGRADED, 5 = OFFLINE) and recovery probes is production-grade.

### 4.6 ✅ Strength: Cost Model

The total cost model in `architecture_broker_routing.md` (fee + spread + impact + slippage + opportunity cost + financing) is comprehensive and correctly uses the square-root market impact model.

---

## 5. Broker-Specific Issues Not Addressed

### 5.1 MT5-Specific Gaps

| Issue | Severity | Description |
|-------|----------|-------------|
| **Symbol suffixes** | 🟡 | `EURUSD.r`, `EURUSDm` not handled |
| **Futures expiration** | 🟡 | MT5 futures symbols expire monthly (e.g., `US500U26`) |
| **Hedge vs Netting** | 🟡 | MT5 accounts can be hedge-mode or netting-mode; order logic differs |
| **Partial close** | 🟡 | MT5 allows partial position close; `place_order` doesn't model this |
| **Multi-account** | 🔵 | One MT5 terminal = one account; multi-account needs multiple terminals |
| **Weekend quotes** | 🔵 | MT5 may return stale Friday quotes on Saturday; no staleness check |

### 5.2 Crypto Exchange Gaps

| Issue | Severity | Description |
|-------|----------|-------------|
| **Binance filters** | 🟡 | `LOT_SIZE`, `PRICE_FILTER`, `MIN_NOTIONAL` not validated pre-submit |
| **Bybit account mode** | 🟡 | Must be in "Unified Trading Account" mode for the API to work as expected |
| **Exchange maintenance** | 🟡 | Binance/OKX do scheduled maintenance; no detection/prevention |
| **Testnet differences** | 🔵 | Testnet orderbooks are thin; testing may not reflect production behavior |
| **Withdrawal addresses** | 🔵 | Whitelisted withdrawal addresses required for some exchanges |

### 5.3 REST API (OANDA/IG) Gaps

| Issue | Severity | Description |
|-------|----------|-------------|
| **OANDA streaming** | 🟡 | OANDA uses HTTP streaming (chunked transfer), not WebSocket; needs different implementation |
| **IG session management** | 🟡 | IG requires CST + X-SECURITY-TOKEN headers that change per session |
| **Rate limit specifics** | 🟡 | OANDA: 120 req/min; IG: varies by endpoint; not modeled in RateLimitTracker |

### 5.4 IBKR Gaps

| Issue | Severity | Description |
|-------|----------|-------------|
| **TWS/Gateway dependency** | 🟡 | Requires running TWS or IB Gateway (Java app); not containerized |
| **Synchronous bridge** | 🟡 | `ib_insync` uses asyncio internally but the bridge to TWS is synchronous |
| **Contract resolution** | 🟡 | `_resolve_contract` is oversimplified; real IB contracts need conId, exchange, currency |
| **Order confirmation timing** | 🟡 | `await asyncio.sleep(0.5)` is a hack; should use `ib.orderStatusEvent` |

---

## 6. Integration Risks

### 6.1 Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **MT5 bridge failure** | High | Critical — all forex trading stops | Redundant bridge instances, auto-reconnect, alerting |
| **Symbol mapping mismatch** | Medium | Critical — orders on wrong pairs | Runtime validation, integration tests with real broker APIs |
| **CCXT API breaking change** | Medium | High — crypto trading disrupted | Pin CCXT version, test in sandbox before upgrading |
| **Rate limit exhaustion** | Medium | High — orders rejected | Proactive rate tracking, per-broker throttling |
| **Credential leak** | Low | Critical — account compromise | Memory zeroing, no logging of credentials, HSM integration |
| **GIL contention (MT5)** | Medium | Medium — order latency spikes | Limit concurrent MT5 calls, monitor thread pool queue depth |
| **WebSocket silent drop** | Medium | High — stale data, missed fills | Heartbeat monitoring, reconnection logic, staleness checks |
| **PostgreSQL deadlock** | Low | Medium — order processing stall | Proper transaction isolation, retry logic, connection pooling |
| **Clock skew** | Low | Medium — stale data detection fails | NTP sync, use broker timestamps not local time |
| **Multi-process event loss** | Medium | Medium — missed signals | Redis Streams implementation (currently just sketched) |

### 6.2 🔴 Most Critical Risk: MT5 on Linux

The entire forex trading capability depends on running MT5 on Linux, which is fundamentally unsupported. The architecture acknowledges this but the Docker Compose configuration is invalid. **Recommendation:**

1. **Immediate:** Remove `platform: windows` from docker-compose; document that MT5 bridge requires a separate Windows host
2. **Short-term:** Build a WebSocket bridge protocol spec (message format, auth, heartbeat, error propagation)
3. **Medium-term:** Test bridge with a Windows VPS (e.g., AWS Windows EC2, Azure Windows VM) and measure latency overhead
4. **Long-term:** Consider OANDA REST API as primary forex connector (native Linux support, no Windows dependency)

### 6.3 🔴 Most Critical Bug: Order Lifecycle Gap

There is **no post-trade reconciliation** anywhere in the architecture. After an order is placed:

1. The system records the fill in PostgreSQL ✅
2. But it never re-checks with the broker to verify the fill actually happened ❌
3. If the broker-side state changes (partial fill, cancel, expire), the system won't know ❌

**Impact:** Portfolio state drifts from reality. Risk calculations become wrong. P&L is incorrect.

**Fix:** Add a periodic reconciliation task:
```python
async def reconcile_orders(self):
    """Periodically verify system state matches broker state."""
    for broker_id, connector in self._registry.get_all_connectors():
        broker_orders = await connector.get_open_orders()
        system_orders = await self._db.get_open_orders_for_broker(broker_id)
        
        for sys_order in system_orders:
            broker_order = find_by_broker_id(broker_orders, sys_order.broker_order_id)
            if broker_order is None:
                # Order gone from broker — was it filled, cancelled, or expired?
                status = await connector.get_order_status(sys_order.broker_order_id)
                await self._db.update_order_status(sys_order.order_id, status)
```

---

## 7. Recommendations Summary

### Must-Fix Before Implementation (P0)

1. **Fix MT5 pending order pricing bug** — validate price for LIMIT/STOP orders, don't fall back to market price
2. **Fix Docker Compose MT5 bridge** — remove `platform: windows`, document Windows host requirement
3. **Fix CCXT balance iterator** — skip metadata keys
4. **Fix CCXT streaming** — don't hardcode to Binance
5. **Add post-trade reconciliation** — periodic broker state verification

### Must-Fix Before Production (P1)

6. **Add MT5 order size validation** — check min/max/step before submission
7. **Fix MT5 filling mode** — detect from `symbol_info()` bitmask
8. **Implement score caching** for the router — don't make live API calls per order
9. **Specify MT5 bridge protocol** — message format, auth, heartbeat, error handling
10. **Add CCXT exception handling** — `DDoSProtection`, `RequestTimeout`, `AuthenticationError`
11. **Add symbol suffix handling** for MT5 — dynamic symbol discovery
12. **Implement WebSocket heartbeat monitoring** — detect silent drops

### Should-Fix (P2)

13. Make MT5 deviation configurable per-symbol
14. Make MT5 magic number configurable
15. Implement real liquidity scoring (orderbook depth analysis)
16. Implement real fee scoring (per-broker fee schedules)
17. Add exchange-specific SL/TP param formatting for CCXT
18. Add Binance filter validation (LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL)
19. Add USD→USDT auto-mapping for CCXT
20. Implement Redis Streams for cross-process event bus
21. Add IBKR contract resolution (conId, exchange, currency)
22. Add hedge vs netting mode handling for MT5

### Nice-to-Have (P3)

23. Add MT5 futures expiration handling
24. Add multi-account MT5 support (multiple terminal instances)
25. Add exchange maintenance window detection
26. Add credential memory zeroing
27. Add NTP clock sync validation
28. Add PostgreSQL connection pooling and deadlock handling

---

## 8. Architecture Quality Assessment

| Aspect | Score | Notes |
|--------|-------|-------|
| **Abstraction design** | 9/10 | `BrokerConnector` ABC is clean, complete, and extensible |
| **Data model** | 8/10 | Unified data classes are well-typed; missing some fields (e.g., `broker_order_id` on `UnifiedOrder`) |
| **Error handling** | 7/10 | Error taxonomy is good; recovery matrix is helpful; but error propagation from broker-specific to unified is underspecified |
| **Security** | 7/10 | Credential vault is solid; missing memory zeroing, HSM option |
| **Scalability** | 6/10 | Single-process event bus, no connection pooling, no horizontal scaling path |
| **Testability** | 8/10 | Mock connector is excellent; test scenarios are comprehensive |
| **Documentation** | 9/10 | Thorough, well-structured, includes code examples |
| **Linux feasibility** | 4/10 | MT5 on Linux is the Achilles' heel; needs Windows host strategy |
| **Crypto coverage** | 8/10 | CCXT integration is solid; on-chain pipeline is comprehensive |
| **Routing sophistication** | 8/10 | Scoring, failover, arbitrage, cost model are all well-designed |

**Overall Architecture Score: 7.4/10** — Strong design, needs implementation hardening.

---

## 9. Conclusion

The Alpha Stack broker abstraction layer is a well-architected system that correctly identifies the key challenges of multi-broker trading. The `BrokerConnector` interface is clean and extensible. The CCXT integration for crypto is solid. The smart order routing design is sophisticated and feasible.

The primary risks are:
1. **MT5 on Linux** — requires a Windows host (VM or VPS) with a WebSocket bridge that needs to be fully specified
2. **Implementation bugs** — the pending order pricing bug and balance iterator bug will cause failures in production
3. **Missing reconciliation** — the system trusts its own state without verifying against broker reality

Addressing the P0 and P1 items above will bring this architecture to production-ready status. The design is sound; the execution needs refinement.

---

*Review completed: 2026-07-11*
*Reviewed documents: architecture_broker.md, architecture_crypto.md, architecture_broker_routing.md*
*Total issues found: 3 critical, 5 high, 12 medium, 8 low*
