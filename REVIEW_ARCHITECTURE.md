# AlphaStack Architecture Review

**Reviewer:** AI Architecture Review Agent  
**Date:** 2026-07-17  
**Scope:** Full codebase — `src/alphastack/`, deployment, AI integration, risk management  
**Lines of code reviewed:** ~21,400 (Python source)

---

## Table of Contents

1. [Architecture Assessment](#a-architecture-assessment)
2. [Code Quality Issues](#b-code-quality-issues)
3. [AI Integration Quality](#c-ai-integration-quality)
4. [Deployment Issues (Fly.io)](#d-deployment-issues)
5. [Missing/Incomplete Features](#e-missingincomplete-features)
6. [Priority Fix List](#f-priority-fix-list)

---

## A. Architecture Assessment

### A1. Multi-Agent Design (Grade: B+)

The LangGraph-based orchestrator (`src/alphastack/agents/orchestrator/graph.py`) implements a well-structured 5-agent pipeline:

```
News → Strategy → Debate → Risk → Execution → Reflection
```

**What's good:**
- Clean separation of concerns: each agent has a single responsibility
- The state machine pattern (LangGraph `StateGraph`) is appropriate for this domain
- Conditional edges properly handle REJECT/MODIFY/EXECUTE flows
- Human-in-the-loop checkpoint is properly implemented with fail-closed behavior
- The debate engine (bull/bear/risk-arbiter) is a genuinely novel pattern for signal validation
- Post-trade reflection with `CorrectionEngine` and `SkillCreator` closes the learning loop

**What's concerning:**
- **The LangGraph graph is bypassed in production.** In `live_server.py` lines ~350-410, `_run_orchestrator()` manually calls each agent's `.run()` method sequentially instead of using `self._graph.ainvoke()`. The comment says "to avoid LangGraph state serialization issues with nested Pydantic models." This means the entire LangGraph infrastructure (conditional routing, checkpointing, interrupt) is dead code in production.
- **The debate engine uses heuristic reasoning, not AI.** The `DebateEngine` uses `ChainOfThoughtEngine` (a deterministic rule-based system), not the `AlphaModel` LLM client. The bull/bear agents produce arguments from simple indicator checks, not LLM reasoning. This is fine for latency but undermines the "AI-powered" claim.
- **Agent memory is session-scoped.** `AgentMemory` in `base.py` is an in-memory list that resets every process restart. There's no persistence layer for agent working memory.

### A2. Strategy Pipeline (Grade: A-)

The 16-step pipeline (`src/alphastack/strategy/pipeline.py`) is the strongest architectural component:

**What's excellent:**
- Immutable `AlphaStackContext` (frozen Pydantic model) — each step returns a new copy. This is the correct functional pattern for a pipeline.
- Steps 5-9 are parallelizable via `asyncio.gather` (S/R, liquidity, SMC, RSI, candlestick)
- Step ordering is sensible: StopLoss (12) runs before PositionSizing (11) so sizing uses actual stop price
- The confluence engine (`s10_confluence.py`) uses weighted voting with independent direction signals from each component — this is institutional-quality design
- Regime-adaptive weights via `config/strategy_params.yaml`
- RSI divergence detection in `s08_rsi.py` is properly implemented with Wilder smoothing

**What needs work:**
- **Step 1 (Fundamental) is a stub.** It reads `news_sentiment` and `volatility_index` from market data, but `_build_market_data()` in `live_server.py` hardcodes both to 0.0. The fundamental step does nothing in production.
- **No backtesting integration.** The pipeline has no mechanism to run against historical data. The `BacktestEngine` in `rust_bridge.py` is a stub class with no methods.
- **Parallel execution has a bug.** In `_run_parallel_group()`, each step receives the *same* base context. If two parallel steps try to write the same field, the last merge wins. This is documented but not guarded against.

### A3. Comparison to Institutional Systems

| Feature | AlphaStack | Institutional (e.g., Citadel, Two Sigma) |
|---------|-----------|------------------------------------------|
| Multi-agent orchestration | ✅ LangGraph | ✅ Custom microservices |
| Strategy pipeline | ✅ 16 steps | ✅ 50-200+ factors |
| Real-time data | ⚠️ REST polling | ✅ WebSocket feeds, co-located |
| Execution | ⚠️ REST API orders | ✅ Smart order routing, DMA |
| Risk management | ✅ Comprehensive | ✅ Real-time intraday |
| Backtesting | ❌ Stub | ✅ Tick-level, years of history |
| ML/RL models | ❌ Placeholder | ✅ Ensemble, deep RL |
| Latency | ⚠️ ~100ms+ | ✅ <1ms (HFT) to ~10ms |
| Data persistence | ❌ In-memory | ✅ TimescaleDB, KDB+ |

AlphaStack is a well-architected **prototype** that demonstrates institutional patterns but lacks the data infrastructure, execution layer, and ML models needed for real institutional use.

---

## B. Code Quality Issues

### B1. Critical Bugs

**BUG-1: Monkey-patch in `live_server.py` (line ~35-40)**
```python
try:
    import alphastack.strategy.steps.s10_confluence as _s10
    if not hasattr(_s10, '_WEIGHTS'):
        _s10._WEIGHTS = _s10._DEFAULT_WEIGHTS
except Exception as _mp_err:
    logging.getLogger("alphastack.live").warning(...)
```
The `s10_confluence.py` module references `_WEIGHTS` (line ~160: `w = _WEIGHTS.get(component, 0.0)`) but only defines `_DEFAULT_WEIGHTS`. The monkey-patch patches this at runtime, but if the import order changes or the module is reloaded, it breaks. The fix should be in `s10_confluence.py` itself: `_WEIGHTS = _DEFAULT_WEIGHTS` at module level.

**BUG-2: `_TOKEN_BLOCKLIST` uses `set.pop()` which is non-deterministic**
In `live_server.py` lines ~475-480:
```python
if len(_TOKEN_BLOCKLIST) >= _TOKEN_BLOCKLIST_MAX:
    _TOKEN_BLOCKLIST.pop()  # removes ARBITRARY element
_TOKEN_BLOCKLIST.add(jti)
```
`set.pop()` removes an arbitrary element, not the oldest. This means a recently revoked token could be popped while an old one stays. Should use an `OrderedDict` or `deque` with FIFO eviction.

**BUG-3: `_sanitize_str()` strips non-ASCII from API keys/secrets**
In `live_server.py` lines ~107-112:
```python
BINANCE_API_KEY = _sanitize_str(os.environ.get("BINANCE_API_KEY", ""))
BINANCE_API_SECRET = _sanitize_str(os.environ.get("BINANCE_API_SECRET", ""))
```
If an API key legitimately contains non-ASCII characters (unlikely but possible), this silently corrupts it. The function should validate and raise, not silently strip.

**BUG-4: `signal` variable shadowing in `_run_orchestrator()`**
In `live_server.py` line ~382, `signal` is used as a loop variable:
```python
for signal in state.get('signals', []):
```
But `signal` is also a Python keyword (from the `signal` module). While this works, it shadows the built-in and can cause confusion.

**BUG-5: Race condition in `InMemoryEventBus`**
The `InMemoryEventBus` in `live_server.py` has no locking on `_handlers` or `_events`. If `publish()` and `subscribe()` are called concurrently from different coroutines, the handler list could be modified during iteration. Should use `asyncio.Lock`.

### B2. Dead Code

1. **LangGraph graph compilation** — `_build_graph()` in `orchestrator/graph.py` builds a full StateGraph with conditional edges, but `_run_orchestrator()` in `live_server.py` bypasses it entirely by calling agents directly.

2. **`stream()` method** on `AlphaStackOrchestrator` — never called anywhere in the codebase.

3. **`BrokerRegistry.from_env()`** — auto-detection classmethod that reads from `get_settings()`, but `live_server.py` creates brokers manually.

4. **`SignalStore._subscribe_events()`** — subscribes to the `EventBus` for signals, but the `InMemoryEventBus` in production doesn't fire events through the `SignalStore` path.

5. **Multiple `api/rest/routes/` files** — `analytics.py`, `auth.py`, `portfolio.py`, `settings.py`, `signals.py`, `system.py`, `trades.py` exist but are never imported by `live_server.py`, which implements all routes inline.

6. **`src/alphastack/api/rest/app.py`** — standalone FastAPI app definition, never used (live_server.py creates its own).

7. **`src/alphastack/api/websocket/server.py`** — standalone WebSocket server, never used.

8. **All `src/alphastack/loops/` files** — `deliberation_loop.py`, `hitl_loop.py`, `learning_loop.py`, `react_loop.py`, `reflection_loop.py` — none are imported or used anywhere.

### B3. Hardcoded Values

| Location | Value | Issue |
|----------|-------|-------|
| `live_server.py:380` | `account_balance: 10_000.0` | Hardcoded in `_build_market_data()` — should come from broker |
| `live_server.py:381` | `risk_pct: 1.0` | Hardcoded — should come from settings |
| `live_server.py:470` | `_JWT_SECRET = sha256(b"alphastack-dev-secret-v1")` | Dev fallback JWT secret — dangerous if env var missing |
| `engine/loop.py:65` | `INITIAL_CAPITAL: float = 10000.0` | Fixed initial capital for drawdown normalization |
| `engine/loop.py:520` | `account_balance = 10_000.0` | In `_calculate_forex_quantity()` — should come from broker |
| `agi/planning.py` | All scenario probabilities = 0.33/0.33/0.34 | Equal probability for bull/bear/sideways — no actual market analysis |
| `live_server.py:130` | `_FOREX_PAIRS` set | Hardcoded — should be configurable |

### B4. Missing Error Handling

1. **`_fetch_ohlcv()`** — silently returns empty list on failure. Pipeline continues with empty data, producing garbage signals.

2. **`_build_market_data()`** — if `closes` is empty, `current_price = 0.0`. All downstream steps (RSI, ATR, S/R) will produce nonsensical results with zero prices.

3. **`WebSocket endpoint`** — bare `except Exception: pass` in the price feed loop (line ~780). Any error (including disconnection) is silently swallowed.

4. **`_run_pipeline_signal()`** — catches all exceptions and returns empty dict. This means pipeline failures are invisible — no retry, no alert.

5. **`OandaConnector.connect()`** — if the initial auth request fails, `_connected` is set to False but `_session` is not closed, leaking the aiohttp session.

---

## C. AI Integration Quality

### C1. `model_client.py` Design (Grade: A-)

This is one of the best-designed modules in the codebase:

**Strengths:**
- **Provider-agnostic design** — supports MiMo, NVIDIA, OpenAI, Anthropic, Fable, Google, Local via a clean `resolve_config()` chain
- **Auto-detection** — `detect_provider()` matches URL patterns to provider keys
- **Backward compatibility** — legacy `MIMO_*` env vars still work
- **Tri-state availability** — `_available: bool | None` with periodic reset (5 min cooldown)
- **Rate limiting** — async token-bucket limiter at 10 RPS
- **Response caching** — 5-minute TTL with SHA-256 cache keys
- **Exponential backoff** — 3 retries with 1s/2s/4s delays
- **Anthropic-specific path** — separate `_request_anthropic()` for the different API format
- **Heuristic fallback** — keyword-based fallback when AI is unavailable

**Weaknesses:**
- **The fallback is too simplistic.** Keyword matching ("bull", "bear", "risk") will produce the same response regardless of actual market conditions. This is the source of the "fallback" responses the user sees.
- **No streaming support.** All responses are buffered to completion. For long reasoning chains, this adds latency.
- **Cache doesn't differentiate by model.** If you switch providers, cached responses from the old provider are served.
- **`is_available()` checks `/models` endpoint** — not all providers expose this. Should fall back to a lightweight chat completion test.

### C2. Prompt Quality

The prompts in `ReasoningEngine` are functional but generic:

- **`reasoning()`**: "You are a quantitative trading reasoning engine..." — adequate but could be more specific about the trading context
- **`bull_argue()`/`bear_argue()`**: Good structure — provides signal, indicators, and counter-arguments
- **`pre_trade_reflect()`**: Asks for APPROVE/REJECT/MODIFY verdict — good structured output format
- **`consolidate_memory()`**: Asks for patterns, lessons, parameter adjustments — appropriate for the task

**Missing:** No structured output enforcement (JSON mode), no few-shot examples, no chain-of-thought prompting. Compare to 2025-2026 best practices where structured output and tool use are standard.

### C3. Fallback Chain Robustness

The fallback chain is: `AlphaModel._chat()` → cache check → availability check → API call (3 retries) → `_fallback()` heuristic.

**The problem:** When the API key isn't reaching the app (see Section D), `_available` is set to `False` after the first failed `/models` check, and stays False for 5 minutes. During that window, ALL requests get the heuristic fallback. The 5-minute cooldown (`_AVAILABLE_RESET_S = 300`) means the system spends most of its time in fallback mode if the key issue isn't resolved.

**Fix:** The availability check should verify the actual API key, not just test the `/models` endpoint. If `self._api_key` is empty, return fallback immediately without trying the endpoint.

---

## D. Deployment Issues (Fly.io)

### D1. Root Cause: API Key Not Reaching the App

The user reports the AI model keeps returning "fallback" responses. Here's the chain of failure:

**Step 1: `fly.toml` only sets `PORT=8000`**
```toml
[env]
  PORT = "8000"
```
No `AI_API_KEY`, `AI_PROVIDER`, `AI_BASE_URL`, or `AI_MODEL` are set in `fly.toml`.

**Step 2: Fly.io secrets are separate from env vars**
Fly.io secrets (set via `fly secrets set AI_API_KEY=...`) ARE injected as environment variables at runtime. But they're NOT visible in `fly.toml` or during build time.

**Step 3: `Dockerfile` runs `test_startup.py` at build time**
```dockerfile
RUN python3 test_startup.py
```
If `test_startup.py` tries to initialize the AI client, it will fail because secrets aren't available at build time. However, the test likely passes because it only checks imports.

**Step 4: `start.py` prints env var status but doesn't fail**
```python
print(f"AI_PROVIDER: {os.environ.get('AI_PROVIDER', 'not set')}")
```
This shows whether the env var is set at runtime. If it prints "not set", the secret wasn't configured.

**Step 5: `AlphaModel.__init__()` defaults to MiMo**
```python
# resolve_config() defaults:
resolved_provider = "mimo"  # if no provider specified
resolved_url = "https://token-plan-sgp.xiaomimimo.com/v1"  # default
resolved_model = "mimo-v2.5-pro"  # default
```
Without `AI_API_KEY`, the client defaults to MiMo with an empty API key. The first `/models` check fails with 401, `_available` is set to False, and all subsequent calls return `[fallback]` responses.

### D2. Specific Deployment Issues

1. **No secrets configured.** The `fly.toml` has no secrets. You need:
   ```bash
   fly secrets set AI_API_KEY="your-key-here"
   fly secrets set AI_PROVIDER="mimo"  # or openai, anthropic, etc.
   fly secrets set AI_BASE_URL="https://token-plan-sgp.xiaomimimo.com/v1"
   fly secrets set AI_MODEL="mimo-v2.5-pro"
   ```

2. **512MB RAM is tight.** The `shared-cpu-1x` VM with 512MB is insufficient for:
   - FastAPI + uvicorn (~100MB)
   - ccxt initialization (~50MB)
   - LangGraph + LangChain (~150MB)
   - python-telegram-bot (~30MB)
   - Remaining for request handling (~180MB)
   
   This can cause OOM kills under load.

3. **`min_machines_running = 0`** — the app scales to zero. First request after idle has cold start latency (10-30s for imports + ccxt initialization).

4. **`auto_stop_machines = true`** — combined with scale-to-zero, the trading loop will be killed when idle. This defeats the purpose of a continuous trading loop.

5. **No persistent storage.** All state (trades, signals, episodic memory) is in-memory. Every restart loses everything.

6. **`Procfile` exists but isn't used by Fly.io.** Fly.io uses the Dockerfile's CMD, not Procfile.

### D3. `start.py` vs `live_server.py` Confusion

The Dockerfile CMD is `python start.py`, which imports `live_server` and runs uvicorn. But `live_server.py` has its own `if __name__ == "__main__"` block that also runs uvicorn. This double-entry-point is confusing and could lead to issues if someone runs `python live_server.py` directly (different behavior than `python start.py`).

---

## E. Missing/Incomplete Features

### E1. Stubbed Modules (Not Implemented)

| Module | Status | What's Missing |
|--------|--------|----------------|
| `quantum/algorithms.py` | Simulator only | No actual quantum backend connection. Classical Monte Carlo only. |
| `quantum/readiness.py` | Assessment only | No actual quantum-resistant crypto |
| `security/quantum_ready.py` | **All methods return placeholders** | `encrypt_hybrid()` returns input unchanged. `sign_hybrid()` returns placeholder strings. `verify_hybrid()` returns `True` always. |
| `security/encryption.py` | Functional | Works but falls back to hardcoded dev master key |
| `security/audit.py` | Stub | `pass` body |
| `security/credentials.py` | Stub | `pass` body |
| `models/serving/loader.py` | Placeholder | `MiMoAdapter.predict()` returns `np.tanh(momentum * 10)` — a toy heuristic |
| `models/training/trainer.py` | Minimal | Placeholder timestamps, no actual training loop |
| `core/rust_bridge.py` | Fallback only | Rust extension not built. All Python fallbacks. |
| `data/ingestion/alternative_data.py` | Placeholder data | All feeds return hardcoded mock data |
| `data/storage/timescale.py` | Stub | `pass` body |
| `data/ingestion/market_data.py` | Stub | `pass` body |
| `brokers/ccxt_connector.py` | Stub | `pass` body |
| `brokers/oanda_connector.py` | Stub | `pass` body (the real one is inline in live_server.py) |
| `loops/*.py` | Unused | 5 loop modules, none imported or used |

### E2. README vs Reality

| README Claim | Reality |
|-------------|---------|
| "Deep learning, reinforcement learning" | No ML models. `MiMoAdapter` returns `tanh(momentum)`. |
| "Ensemble ML, LSTM, transformers" | None exist. |
| "TWAP/VWAP algorithms" | Not implemented. |
| "Smart order routing" | Basic broker selection by symbol type. |
| "Kafka · Redis · TimescaleDB · ClickHouse" | All in-memory. Redis EventBus exists but unused in production. |
| "Desktop (Tauri)" | No desktop app code found. |
| "Web (Next.js)" | `apps/` directory exists but not reviewed. |
| "Mobile (React Native)" | APK found but no source code in this repo. |
| "MT5 Integration" | `mt5_connector.py` is a stub. |
| "MEXC · FXPesa · IBKR" | Not implemented. Only Binance (ccxt) and OANDA (inline). |
| "Rust core" | Python fallbacks only. Rust source not found. |

### E3. Missing Infrastructure

1. **No database.** `DatabaseSettings` in config.py exists but no actual database connection or ORM models. All data is in-memory dicts.
2. **No Redis.** `RedisSettings` exists but the production `InMemoryEventBus` replaces it.
3. **No tests in CI.** The `tests/` directory exists but no CI configuration was found in `.github/`.
4. **No logging to persistent storage.** Logs go to stdout only.
5. **No metrics collection.** Prometheus `/metrics` endpoint exists but no actual metric counters are registered.

---

## F. Priority Fix List

### P0 — Critical (Fix Immediately)

**1. Fix the s10_confluence monkey-patch bug**
- **File:** `src/alphastack/strategy/steps/s10_confluence.py`
- **Fix:** Add `_WEIGHTS = _DEFAULT_WEIGHTS` after the `_DEFAULT_WEIGHTS` definition (around line 20)
- **Remove:** The monkey-patch block in `live_server.py` (lines ~35-40)
- **Impact:** Without this fix, the confluence engine crashes if the monkey-patch fails

**2. Configure AI secrets on Fly.io**
- **Action:** Run:
  ```bash
  fly secrets set AI_API_KEY="your-actual-key"
  fly secrets set AI_PROVIDER="mimo"  # or your provider
  fly secrets set AI_BASE_URL="https://token-plan-sgp.xiaomimimo.com/v1"
  fly secrets set AI_MODEL="mimo-v2.5-pro"
  ```
- **Impact:** Eliminates all "[fallback]" responses

**3. Fix `_TOKEN_BLOCKLIST` FIFO eviction**
- **File:** `live_server.py`
- **Fix:** Replace `set` with `collections.OrderedDict`:
  ```python
  from collections import OrderedDict
  _TOKEN_BLOCKLIST: OrderedDict[str, None] = OrderedDict()
  # In revoke:
  if len(_TOKEN_BLOCKLIST) >= _TOKEN_BLOCKLIST_MAX:
      _TOKEN_BLOCKLIST.popitem(last=False)  # FIFO
  _TOKEN_BLOCKLIST[jti] = None
  ```
- **Impact:** Security — revoked tokens could be un-revoked

**4. Add input validation for empty market data**
- **File:** `live_server.py`, function `_run_pipeline_signal()`
- **Fix:** After `_build_market_data()`, check that `closes` is non-empty before proceeding
- **Impact:** Prevents garbage signals from zero-price data

### P1 — High (Fix This Week)

**5. Wire the LangGraph orchestrator or remove it**
- Either fix the Pydantic serialization issue and use `self._graph.ainvoke()`, or remove the LangGraph dependency entirely and keep the manual agent sequencing. Current state: 500+ lines of dead graph code.

**6. Increase Fly.io VM size**
- **File:** `fly.toml`
- **Fix:** Change to `shared-cpu-2x` with `1024mb` memory minimum
- **Impact:** Prevents OOM kills under concurrent requests

**7. Fix `_build_market_data()` to fail gracefully**
- **File:** `live_server.py`
- **Fix:** If `closes` is empty, raise a clear error instead of returning zero-filled data
- **Impact:** Prevents downstream pipeline steps from producing nonsense

**8. Wire `RiskSettings.max_leverage` to the actual risk governor**
- **File:** `src/alphastack/core/config.py` — `max_leverage: float = Field(default=2.0)`
- **Issue:** This default of 2.0x is extremely conservative. The `PositionSizer` uses its own `OUR_MAX_LEVERAGE = 20.0`. These should be unified.

**9. Remove dead code**
- Delete: `api/rest/routes/` (7 files), `api/rest/app.py`, `api/websocket/server.py`, `loops/` (5 files)
- Or: Wire them properly and remove the inline routes from `live_server.py`

### P2 — Medium (Fix This Month)

**10. Implement persistent storage**
- Add SQLite (for simplicity) or PostgreSQL for trades, signals, and episodic memory
- Current in-memory storage loses all data on restart

**11. Implement real news data integration**
- The news agent only checks `market_data.get("news", [])` which is always empty
- Wire to a real news API (Finnhub, Alpha Vantage, or NewsAPI)

**12. Implement actual ML models**
- Replace `MiMoAdapter._local_predict()` (the `tanh(momentum)` toy) with a real model
- At minimum: train a simple gradient-boosted model on historical data

**13. Add proper WebSocket market data feeds**
- Current implementation polls REST APIs in a loop with `asyncio.sleep(0.5)`
- Should use exchange WebSocket streams for real-time data

**14. Implement the `SecurityValidator` and `ComplianceEngine`**
- `security/audit.py`, `security/credentials.py` are empty stubs
- At minimum: implement audit logging for all trades

### P3 — Low (Backlog)

**15. Implement backtesting**
- The `BacktestEngine` stub should be wired to the pipeline
- Essential for validating strategy changes before live deployment

**16. Build the Rust extension**
- `rust_bridge.py` has good Python fallbacks, but the Rust path would improve latency
- Priority: `Indicators` (RSI, MACD) and `TickProcessor`

**17. Implement the learning loops**
- `loops/deliberation_loop.py`, `learning_loop.py`, etc. are unused
- These could provide continuous self-improvement if wired properly

**18. Add monitoring and alerting**
- Prometheus metrics are exported but not collected
- Add alerting for: circuit breaker trips, execution failures, AI fallback rate

---

## Summary

AlphaStack is a **well-architected prototype** with institutional-quality design patterns (multi-agent orchestration, immutable pipeline context, circuit breakers, position sizing). The code quality is generally high — clean abstractions, proper error handling patterns, and good separation of concerns.

However, it's a **prototype pretending to be production**. The gap between what's advertised (deep learning, quantum computing, multi-broker routing) and what's implemented (in-memory stores, heuristic AI fallback, single exchange) is enormous. The immediate priorities are:

1. **Fix the deployment** — get the AI API key working on Fly.io
2. **Fix the bugs** — confluence monkey-patch, token blocklist, empty market data
3. **Remove dead code** — 500+ lines of unused routes, loops, and stubs
4. **Add persistence** — in-memory storage is unacceptable for a trading system

The architecture is sound. The implementation needs 2-3 focused weeks to go from prototype to reliable demo.
