# 🏛️ Decision Council Review Board — Final Production Audit

**Date:** 2026-07-16
**Auditor:** Decision Council Review Board (Automated)
**Scope:** 8 implementations — final gate before production deployment
**Methodology:** Line-by-line code review against correctness, security, performance, integration, safety, and quality criteria

---

## Executive Summary

| # | Implementation | Verdict | Critical Issues |
|---|----------------|---------|-----------------|
| 1 | Pre-Trade Reflection | ⚠️ CONDITIONAL | 1 critical (stop_loss corruption) |
| 2 | Multi-Agent Debate | ⚠️ CONDITIONAL | 1 critical (mutates shared state) |
| 3 | Bounded Memory | ⚠️ CONDITIONAL | 1 high (unbounded eviction log) |
| 4 | Self-Reflection & Correction | ⚠️ CONDITIONAL | 1 critical (unbounded parameter drift) |
| 5 | Telegram Bot | ⚠️ CONDITIONAL | 1 critical (no auth on commands) |
| 6 | Model-Agnostic AI Client | ⚠️ CONDITIONAL | 1 critical (permanent AI blackout) |
| 7 | Loop Engine | ❌ REJECTED | 2 critical (broken drawdown, fail-open debate) |
| 8 | Orchestrator | ❌ REJECTED | 2 critical (human-review bypass, signal attribute bug) |

**Bottom line:** Zero implementations approved unconditionally. Two are **REJECTED** and must be fixed before production. The remaining six are **CONDITIONAL** — approved pending specific fixes. The most dangerous patterns are: (1) stop-loss corruption in pre-trade reflection, (2) permanent AI blackout in the model client, (3) broken drawdown tracking in the loop engine, and (4) default-approve behavior in human review.

---

## 1. Pre-Trade Reflection (`agents/reflection/pre_trade.py`)

### Verdict: ⚠️ CONDITIONAL

### CORRECTNESS — ⚠️
- **[CRITICAL] Stop-loss corruption in `_apply_modifications`:** The method multiplies the absolute `stop_loss` price by `sl_factor` (0.8). For BTC at 50,000 with stop_loss at 49,000, this produces `49000 * 0.8 = 39,200` — an absurd stop 10,800 points away. The code should compute the distance `|entry - sl|`, reduce that by 20%, then apply to the entry price.
  ```python
  # BUG: object.__setattr__(signal, "stop_loss", round(new_sl, 6))
  # where new_sl = sl * sl_factor  ← multiplies ABSOLUTE PRICE
  # FIX: new_sl = entry - (entry - sl) * sl_factor
  ```
- ✅ Aggregate verdict logic is correct (any REJECT → overall REJECT)
- ✅ Edge case: empty signals returns APPROVE with 1.0 confidence
- ✅ `getattr` with defaults handles missing attributes gracefully
- ⚠️ Confidence aggregation uses arithmetic mean — may not reflect the "weakest link" nature of sequential gates

### SECURITY — ✅
- No API keys, no external calls, no user input injection vectors

### PERFORMANCE — ✅
- Pure computation, no blocking calls
- Each signal evaluated independently — O(n) per cycle

### INTEGRATION — ✅
- Properly extends `AlphaStackAgent`
- Returns dict compatible with orchestrator state
- Clean import chain

### SAFETY — ⚠️
- **[HIGH]** If stop_loss corruption goes undetected, the risk agent receives a wildly incorrect stop. This could result in either (a) position with no effective stop or (b) immediate stop-out on entry. **Must fix before production.**
- ✅ Regime fit check prevents counter-trend trades
- ✅ Conflict detection limits overtrading

### QUALITY — ✅
- Good docstrings and type hints
- Proper logging at decision points
- Constants extracted to module level

### Required Fix
1. Fix `_apply_modifications` to compute stop distance, not multiply absolute price

---

## 2. Multi-Agent Debate (`agents/debate/`)

### Verdict: ⚠️ CONDITIONAL

### CORRECTNESS — ⚠️
- **[CRITICAL] `debate_engine.py` mutates original chain objects:** Lines in `debate()`:
  ```python
  blended_bull_chain = bull_chain  # ← same object reference!
  blended_bull_chain.overall_confidence = round(...)  # ← mutates original
  ```
  The transcript records the original chain, but its `overall_confidence` has been overwritten with the blended value. This corrupts audit data and makes debugging impossible. Fix: create a copy or store the original confidence before blending.
- ✅ Bull/Bear agents produce logically consistent chains
- ✅ Risk arbiter's confidence-weighted voting is well-structured
- ✅ 3-round debate with rebuttals is sound design
- ⚠️ `DEBATE_BUDGET_S = 2.0` is only logged, never enforced — debates can take arbitrarily long

### SECURITY — ✅
- No external calls, no API keys, no injection vectors

### PERFORMANCE — ⚠️
- **[HIGH] Synchronous blocking:** The `debate()` method is synchronous but called from async contexts in both the orchestrator and loop engine. With 4 chain evaluations per signal and 3+ signals per cycle, this blocks the event loop for potentially 500ms+.
- ⚠️ Shared `ChainOfThoughtEngine` between bull and bear agents accumulates all chains in `self._chains` — unbounded memory growth over time

### INTEGRATION — ✅
- Clean interfaces with orchestrator and loop engine
- `DebateResult.to_dict()` matches expected format

### SAFETY — ⚠️
- **[HIGH] Fail-open on debate errors:** Both the loop engine (`except Exception: return True`) and the orchestrator treat debate failures as approval. A crash in the debate engine means signals bypass the debate safety gate entirely. This should fail-closed (reject on error).
- ✅ Risk arbiter defaults to REJECT on ambiguity — correct safety posture
- ✅ Risk context penalties reduce bull confidence under drawdown

### QUALITY — ✅
- Excellent docstrings and design documentation
- Clean separation of concerns (bull, bear, arbiter, engine)
- Full audit transcript preserved

### Required Fixes
1. Fix chain mutation in `debate_engine.py` — copy before blending
2. Make debate fail-closed (reject on error) in loop engine and orchestrator
3. Consider wrapping synchronous `debate()` in `asyncio.to_thread()` for async contexts

---

## 3. Bounded Memory (`agi/memory.py`)

### Verdict: ⚠️ CONDITIONAL

### CORRECTNESS — ✅
- ✅ Impact-based eviction correctly selects lowest-impact entries
- ✅ Recency half-life exponential decay is mathematically correct (`e^(-0.693 * age / half_life)`)
- ✅ Similarity scoring with weighted components (symbol, direction, indicators, context)
- ✅ Periodic cleanup prunes bottom 10th percentile
- ✅ Zero-division protection throughout (`max(..., 1e-10)`)
- ⚠️ `BoundedMemory` and `EpisodicMemory` are separate, non-integrated classes — `EpisodicMemory` has no hard cap on total episodes (only consolidation threshold)

### SECURITY — ✅
- No external calls, no user input processing

### PERFORMANCE — ⚠️
- `find_similar()` iterates all episodes O(n) on every call — acceptable at 500 max, but `PrioritizedRetrieval.query()` also does O(n) with no index
- `similarity_score()` iterates common indicator keys — bounded by indicator count

### INTEGRATION — ⚠️
- Orchestrator uses `EpisodicMemory`, loop engine uses `EpisodicMemory`, but `BoundedMemory` appears unused in the hot path
- This means the hard caps (500 trades, 50 patterns) may not be enforced in production

### SAFETY — ⚠️
- **[HIGH] `_eviction_log` grows unboundedly:** Every eviction appends to `self._eviction_log` with no cap. Over months of operation, this will consume increasing memory. Only `self._insights` is capped at `_max_trades`.
- Impact scores drive eviction priority — if scores are computed incorrectly, valuable episodes could be evicted

### QUALITY — ✅
- Well-structured dataclasses with proper defaults
- Good separation of concerns (TradeEpisode, LearnedPattern, EvictionInsight)
- Comprehensive stats() method

### Required Fix
1. Cap `_eviction_log` (e.g., keep last 1000 entries)
2. Clarify production usage: will `BoundedMemory` actually replace `EpisodicMemory` in the hot path?

---

## 4. Self-Reflection & Correction (`agents/reflection/post_trade.py`)

### Verdict: ⚠️ CONDITIONAL

### CORRECTNESS — ⚠️
- **[CRITICAL] Unbounded parameter drift in CorrectionEngine:** Corrections auto-apply deltas to parameters without bounds. Example: after 10 signal-driven losses, `min_confluence_score` accumulates `+0.05 * 10 = +0.50`, potentially reaching 1.0 (impossible to trigger). After 5 signal-driven wins, it decreases by `0.02 * 5 = 0.10`. No min/max clamping exists.
  ```python
  # In generate(): new_value = current + template["delta"]
  # No clamping to valid ranges!
  ```
- ✅ Diagnosis logic covers all four categories (signal, execution, timing, risk)
- ✅ SkillCreator correctly promotes after 5+ similar wins and demotes below 40% win rate
- ⚠️ Category extraction from inference step searches in reverse — if multiple inference steps exist, it may find the wrong one

### SECURITY — ✅
- No external calls, no user input injection

### PERFORMANCE — ✅
- Synchronous but lightweight — called after trade execution, not in hot path
- SkillCreator's `find_similar()` is O(n) but bounded by memory cap

### INTEGRATION — ⚠️
- Orchestrator's `_reflection_node` has an inline `from alphastack.agi.memory import TradeEpisode` — works but suggests incomplete refactoring
- CorrectionEngine's `apply_corrections` modifies pipeline_context — no validation that new values are in valid ranges

### SAFETY — ❌
- **[CRITICAL] Auto-applied corrections without safety bounds:** If corrections push `position_size_pct` negative or `min_confluence_score` above 1.0, the trading system could malfunction. All correction deltas MUST be clamped to valid parameter ranges.
- **[HIGH] No correction reversal mechanism:** A correction applied after a loss persists even if subsequent trades prove it wrong. The system has no way to undo harmful corrections.
- SkillCreator's action template hardcodes `position_size_pct: 0.02` and `stop_loss_atr_mult: 2.0` — these should be configurable

### QUALITY — ✅
- Clean dataclass models (Correction, TradeSkill)
- Good logging throughout
- Proper use of type hints

### Required Fixes
1. **MUST:** Add parameter bounds clamping in `CorrectionEngine.generate()` and `apply_corrections()`
2. **MUST:** Add correction reversal/decay mechanism
3. Consider making skill action templates configurable

---

## 5. Telegram Bot (`integrations/telegram_bot.py`)

### Verdict: ⚠️ CONDITIONAL

### CORRECTNESS — ✅
- ✅ All commands handle missing data gracefully ("⚠️ not available")
- ✅ Notification queue is bounded (500 messages)
- ✅ Markdown fallback on send failure prevents message loss
- ✅ Proper async lifecycle (start/stop)

### SECURITY — ❌
- **[CRITICAL] No authentication or authorization:** Any Telegram user who discovers the bot can interact with it. The `/portfolio`, `/trades`, `/signals`, and `/explain` commands expose sensitive financial data. There is no `chat_id` validation on incoming messages — only outgoing messages use the configured `chat_id`.
  ```python
  # _cmd_portfolio, _cmd_trades, etc. respond to ANY user
  # FIX: Check update.message.chat_id == self.config.chat_id
  ```
- ⚠️ No rate limiting on incoming commands — vulnerable to spam/DoS
- ⚠️ `_cmd_fallback` echoes user input back — potential for abuse if Markdown injection is possible (low risk with Telegram's parser)

### PERFORMANCE — ⚠️
- **[HIGH] `_cmd_market` makes 5 sequential blocking exchange API calls:** Each `fetch_ticker()` is synchronous and could take 1-5 seconds. Total: 5-25 seconds of blocked event loop.
  ```python
  # FIX: Use asyncio.gather() or run in executor
  ```
- `_cmd_status` has the same issue with a single `fetch_ticker()` call
- ✅ Flush loop is properly rate-limited (0.1s between messages, 2s between batches)

### INTEGRATION — ⚠️
- Global singleton pattern (`_bot_instance`) makes testing difficult
- Tightly coupled to TradeStore, SignalStore, PortfolioService interfaces

### SAFETY — ⚠️
- No validation that bot commands are coming from the authorized chat
- `_cmd_fallback` echoes arbitrary user text (low risk)

### QUALITY — ✅
- Good error handling with fallbacks
- Comprehensive command set
- Module-level notification helpers are convenient

### Required Fixes
1. **MUST:** Add `chat_id` validation on all incoming commands
2. **MUST:** Wrap exchange calls in `asyncio.to_thread()` or use async exchange client
3. Add per-user rate limiting

---

## 6. Model-Agnostic AI Client (`ai/model_client.py`)

### Verdict: ⚠️ CONDITIONAL

### CORRECTNESS — ⚠️
- **[CRITICAL] Permanent AI blackout after transient failure:** When `_request_with_retry` fails after all retries, it sets `self._available = False`. The `is_available()` method checks `if self._available is not None` and returns the cached value. Once set to `False`, the system permanently falls back to keyword-based heuristics — even if the provider recovers minutes later. This is a serious reliability issue for a trading system.
  ```python
  # In _request_with_retry:
  self._available = False  # ← set once, never reset
  # In is_available():
  if self._available is not None:
      return self._available  # ← cached forever
  ```
- ✅ Provider auto-detection is clean and extensible
- ✅ Anthropic-specific request format handling is correct
- ⚠️ `is_available()` checks `/models` endpoint — a 401 (invalid key) returns `True` because `status_code < 500`

### SECURITY — ✅
- API keys read from environment variables only
- Keys passed via headers, not logged
- Anthropic uses `x-api-key` header (correct)

### PERFORMANCE — ✅
- Rate limiter (token bucket, 10 rps) is well-implemented
- Cache (5 min TTL, 500 entry cap) prevents redundant calls
- Retry with exponential backoff handles transient failures

### INTEGRATION — ✅
- Clean `AlphaModel` → `ReasoningEngine` layering
- `.mimo` backward-compat alias is thoughtful
- Fallback heuristics provide graceful degradation

### SAFETY — ⚠️
- **[HIGH] Fallback heuristics are dangerously simplistic:** Keyword matching ("bull", "buy", "long") determines trade direction. This is worse than random — it has systematic bias. A better fallback would be to reject all signals when AI is unavailable, forcing human review.
- **[HIGH] No recovery mechanism for `_available` flag:** If the AI provider has a 30-second outage during startup, the entire trading session runs without AI. Need a periodic health check or TTL on the `_available` flag.

### QUALITY — ✅
- Excellent documentation and provider registry
- Clean separation of concerns
- Good logging at decision points

### Required Fixes
1. **MUST:** Add TTL or periodic retry for `_available` flag (e.g., reset every 5 minutes)
2. **MUST:** Fix `is_available()` to reject 401/403 responses
3. Consider replacing keyword fallback with "reject all signals" when AI is unavailable

---

## 7. Loop Engine (`engine/loop.py`)

### Verdict: ❌ REJECTED

### CORRECTNESS — ❌
- **[CRITICAL] Broken drawdown calculation:**
  ```python
  # Current (WRONG):
  if self.state.total_pnl < 0:
      self.state.current_drawdown = abs(self.state.total_pnl)
  else:
      self.state.current_drawdown = max(0.0, self.state.current_drawdown - pnl)
  ```
  This tracks cumulative loss, NOT drawdown from peak equity. Example: profit +$1000, then lose $200 → drawdown shows 0 (because total_pnl is +$800). Real drawdown is 20% from peak. The `_pre_trade_reflect` check `current_drawdown > 15.0` will never trigger during normal losing streaks within profitable sessions.
  ```python
  # FIX: Track peak_equity separately
  # peak_equity = max(peak_equity, total_pnl)
  # current_drawdown = (peak_equity - total_pnl) / peak_equity * 100
  ```
- **[CRITICAL] Win streak tracking is incorrect:**
  ```python
  if pnl > 0:
      self.state.win_streak = max(0, self.state.win_streak) + 1
  elif pnl < 0:
      self.state.win_streak = min(0, self.state.win_streak) - 1
  ```
  After W-L-W-L: streaks would be 1, -1, 1, -1. This never accumulates. A true losing streak of 3 would show -1, -1, -1 (not -3). The `max(0, ...)` and `min(0, ...)` resets kill accumulation.
- ✅ Cooldown logic is correct (skip N cycles after loss)
- ✅ Symbol loop with per-symbol error handling is good
- ⚠️ Hardcoded `quantity=0.001` ignores signal strength, account size, and risk parameters

### SECURITY — ✅
- No external API keys or injection vectors

### PERFORMANCE — ⚠️
- Per-symbol pipeline/debate/reflect calls are sequential — 3 symbols × ~3s each = ~9s per cycle
- `_debate_signal` calls synchronous `debate()` from async context — blocks event loop

### INTEGRATION — ⚠️
- Depends on external callables (`build_market_data`, `run_pipeline`, `run_orchestrator`) — interface contract not enforced
- `EpisodicMemory` used directly, not `BoundedMemory` — no hard caps on memory growth

### SAFETY — ❌
- **[CRITICAL] Debate fails open:**
  ```python
  except Exception:
      logger.warning("loop.debate_error", exc_info=True)
      return True  # Allow through on debate failure
  ```
  If the debate engine crashes, ALL signals pass through to execution. This defeats the entire purpose of the debate safety gate. **Must fail closed.**
- **[HIGH] `_pre_trade_reflect` checks `recent_losses` but doesn't filter by symbol correctly:** It checks `memory_context["recent_trades"]` which comes from `_read_memory()` that queries ALL episodes, not per-symbol. A loss on ETH/USDT could block a BTC/USDT trade.
- **[HIGH] 15% drawdown threshold never triggers** due to broken drawdown calculation
- ✅ `max_concurrent_trades` limit is enforced

### QUALITY — ✅
- Excellent docstrings and design documentation
- Clean state management with `LoopState` dataclass
- Good logging throughout

### Required Fixes (MUST FIX BEFORE PRODUCTION)
1. **MUST:** Fix drawdown calculation to track peak-to-trough properly
2. **MUST:** Fix win streak tracking (remove `max(0, ...)` / `min(0, ...)` resets)
3. **MUST:** Make debate fail-closed (reject on error)
4. **MUST:** Fix symbol-specific loss filtering in `_pre_trade_reflect`
5. Consider dynamic position sizing instead of hardcoded 0.001
6. Wrap synchronous debate calls in `asyncio.to_thread()`

---

## 8. Orchestrator (`agents/orchestrator/graph.py`)

### Verdict: ❌ REJECTED

### CORRECTNESS — ❌
- **[CRITICAL] Human review node defaults to APPROVE on non-string input:**
  ```python
  if isinstance(human_response, str):
      # ... process feedback
  else:
      s.human_feedback = "approved"  # ← DEFAULT APPROVE!
  ```
  If `interrupt()` returns `None`, a dict, or any non-string type, the trade is automatically approved. This bypasses the entire human-in-the-loop safety mechanism. In a trading system, this is catastrophic — a UI bug or framework change could silently approve all trades.
- **[CRITICAL] Signal attribute access bug in `_enrich_trade`:**
  ```python
  for sig in state.signals:
      sig_sym = sig.get("symbol", "") if isinstance(sig, dict) else getattr(sig, "symbol", "")
  ```
  `state.signals` is `list[Signal]` (Pydantic models). `getattr(sig, "symbol", "")` returns the value, but later:
  ```python
  signal = sig if isinstance(sig, dict) else {
      "type": getattr(sig, "type", ""),  # ← Signal model has no 'type' field!
      "confidence": getattr(sig, "confidence", 0.5),  # ← Signal has no 'confidence' field!
  ```
  The `Signal` model has `symbol`, `side`, `strength`, `confluence_score`, `strategy` — NOT `type` or `confidence`. This means `_enrich_trade` always returns an empty signal dict, and the reflection engine operates without signal context.
- **[HIGH] Debate verdict counting mismatch:**
  ```python
  approved = sum(1 for r in debate_results if r["verdict"] == "execute")
  ```
  But `DebateResult.to_dict()` returns `self.verdict.value` which is `"execute"`, `"reject"`, or `"modify"`. The log says `approved` but counts `"execute"` — semantically confusing but technically correct. However, the variable names mislead anyone reading the logs.
- ✅ Graph structure (news → strategy → debate → risk → human_review → execution → reflection) is well-designed
- ✅ Conditional routing after debate and risk is correct

### SECURITY — ⚠️
- **[HIGH] Human review accepts any string as approval:** `("approve", "yes", "ok", "go", "proceed")` — very broad. A typo like "I don't approve" would match nothing and reject, but "ok let's go" would match "ok" and approve.

### PERFORMANCE — ⚠️
- **[HIGH] Double serialization per node:** Every node call does `_state_from_dict(state)` → process → `_state_to_dict(s)`. With 7 nodes, that's 14 full Pydantic serialize/deserialize cycles per run. For a state with lists of signals, decisions, and execution logs, this is significant overhead.
- Synchronous `debate_engine.debate()` called from async `_debate_node` — blocks event loop

### INTEGRATION — ⚠️
- Inline import in `_reflection_node`: `from alphastack.agi.memory import TradeEpisode` — works but fragile
- `skill_creator._skills` accessed directly (private attribute) — should expose via public API

### SAFETY — ❌
- **[CRITICAL] Human-in-the-loop bypass:** Default-approve on non-string response means the human review checkpoint provides zero safety guarantee. The `interrupt()` mechanism from LangGraph could return unexpected types during framework upgrades.
- **[HIGH] No timeout on human review:** If `interrupt()` blocks indefinitely (human never responds), the entire pipeline hangs. There's no timeout or fallback to rejection.
- ✅ Circuit breaker check in `_route_after_risk` is correct
- ✅ Risk agent rejection properly prevents execution

### QUALITY — ⚠️
- Good docstrings and architecture documentation
- Clean graph construction
- The `_enrich_trade` method needs a complete rewrite to handle Signal model correctly

### Required Fixes (MUST FIX BEFORE PRODUCTION)
1. **MUST:** Default to REJECT (not APPROVE) on non-string human review response
2. **MUST:** Fix `_enrich_trade` to correctly access Signal model fields
3. **MUST:** Add timeout to `interrupt()` with reject-on-timeout fallback
4. Consider reducing serialization overhead (use dict throughout or Pydantic throughout)
5. Fix debate verdict counting variable names for clarity

---

## Cross-Cutting Concerns

### 1. Fail-Open vs Fail-Closed Pattern
The most dangerous pattern across the codebase is **fail-open on error**. Both the loop engine and orchestrator treat errors in the debate engine as approval. In a trading system, every error path should default to REJECT, not EXECUTE. This is a fundamental safety principle violation.

**Affected files:** `engine/loop.py`, `agents/orchestrator/graph.py`, `agents/debate/debate_engine.py`

### 2. Permanent State Corruption
Multiple implementations set flags or values that are never reset:
- `AlphaModel._available = False` → permanent AI blackout
- `ChainOfThoughtEngine._chains` → unbounded memory growth
- `CorrectionEngine._corrections` → unbounded list
- `BoundedMemory._eviction_log` → unbounded list

### 3. Synchronous Calls in Async Context
The debate engine is synchronous but called from async orchestrator and loop nodes. This blocks the event loop and degrades system responsiveness. All synchronous debate calls should be wrapped in `asyncio.to_thread()`.

### 4. Missing Integration Tests
No integration tests exist that verify the full pipeline: signal → debate → reflection → execution → memory → correction. Individual unit tests exist, but the critical path is untested end-to-end.

### 5. No Persistent State Recovery
The loop engine's `LoopState` is in-memory only. A restart loses drawdown tracking, win streaks, and cooldown state. For a production trading system, this state must survive restarts.

---

## Summary of Required Fixes

### ❌ REJECTED — Must Fix Before Production

**Loop Engine (`engine/loop.py`):**
1. Fix drawdown calculation (track peak-to-trough, not cumulative loss)
2. Fix win streak tracking (remove `max(0,...)` / `min(0,...)` resets)
3. Make debate fail-closed on error
4. Fix symbol-specific loss filtering

**Orchestrator (`agents/orchestrator/graph.py`):**
1. Default to REJECT on non-string human review response
2. Fix `_enrich_trade` Signal model field access
3. Add timeout to human review interrupt

### ⚠️ CONDITIONAL — Fix Before Go-Live

| File | Fix |
|------|-----|
| `pre_trade.py` | Fix `_apply_modifications` stop_loss calculation |
| `debate_engine.py` | Fix chain mutation (copy before blending) |
| `memory.py` | Cap `_eviction_log` list |
| `post_trade.py` | Add parameter bounds clamping to CorrectionEngine |
| `telegram_bot.py` | Add chat_id validation on incoming commands |
| `model_client.py` | Add TTL/retry for `_available` flag |

---

## Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Stop-loss corruption (pre_trade) | HIGH | CRITICAL | Fix multiplier → distance calc |
| Permanent AI blackout (model_client) | MEDIUM | CRITICAL | Add TTL to _available flag |
| Human review bypass (orchestrator) | MEDIUM | CRITICAL | Default to REJECT |
| Broken drawdown (loop) | HIGH | CRITICAL | Fix peak-to-trough tracking |
| Debate fail-open (loop + orchestrator) | MEDIUM | HIGH | Fail-closed on error |
| Unbounded parameter drift (post_trade) | HIGH | HIGH | Add bounds clamping |
| No auth on Telegram (telegram_bot) | HIGH | MEDIUM | Add chat_id validation |
| Memory leaks (multiple) | LOW | MEDIUM | Cap all growing lists |

---

## Final Recommendation

**DO NOT DEPLOY TO PRODUCTION** until the 4 critical REJECTED fixes are implemented and verified. The combination of broken drawdown tracking, fail-open debate errors, default-approve human review, and stop-loss corruption creates a system that could:

1. Place trades with no effective stop-loss
2. Bypass all safety gates on error
3. Never trigger circuit breakers during drawdown
4. Silently approve trades without human oversight

These are not edge cases — they are the normal failure modes of the current code. Production deployment with real money requires all critical fixes to be implemented, tested, and verified.

**Signed:** Decision Council Review Board
**Date:** 2026-07-16
