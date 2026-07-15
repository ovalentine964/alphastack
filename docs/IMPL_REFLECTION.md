# Implementation Report: Pre-Trade Signal Reflection

**Status:** ✅ Complete  
**Priority:** #1 (Decision Council)  
**Date:** 2026-07-16

## What Was Built

A pre-trade signal quality gate that runs **between the Strategy and Risk agents** in the LangGraph orchestrator. Before any signal reaches the risk engine, it passes through chain-of-thought reasoning to determine if it's worth taking.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/alphastack/agents/reflection/pre_trade.py` | **Created** | `PreTradeReflection` class (~190 lines) |
| `src/alphastack/agents/orchestrator/state.py` | **Modified** | Added `pre_trade_reflection: dict` field |
| `src/alphastack/agents/orchestrator/graph.py` | **Modified** | Inserted `pre_reflect` node + routing |
| `src/alphastack/agents/reflection/__init__.py` | **Modified** | Export `PreTradeReflection` |

## Architecture

### New Graph Flow

```
START → news → strategy → pre_reflect → risk → execution → reflection → END
                                │
                                ├── REJECT → END (skip risk entirely)
                                ├── MODIFY → risk (adjusted signals)
                                └── APPROVE → risk (unchanged)
```

### PreTradeReflection Class

**Extends:** `AlphaStackAgent` (same base as all other agents)  
**Uses:** `ChainOfThoughtEngine` from `alphastack.agi.reasoning`

#### Evaluation Pipeline (per signal)

1. **Observe** — log signal properties (side, strength, confluence)
2. **Confidence check** — reject if `strength < 0.45`
3. **Confluence check** — reject if `confluence_score < 0.30`
4. **Regime alignment** — score how well signal side fits market regime
5. **Conflict check** — reject if > 2 conflicting recent trades on same symbol
6. **Verdict:**
   - All pass + good regime fit → **APPROVE**
   - All pass + mediocre regime fit → **MODIFY** (reduce size, tighten SL)
   - Any threshold failure → **REJECT**

#### Verdicts

| Verdict | Effect |
|---------|--------|
| `APPROVE` | Signal passes unchanged to risk agent |
| `REJECT` | Signal dropped; graph routes to END |
| `MODIFY` | Signal parameters adjusted (position size factor, stop loss tightening) |

### State Addition

```python
# In AlphaStackState:
pre_trade_reflection: dict[str, Any] = Field(default_factory=dict)
# Keys: verdict, reasoning, confidence, signal_verdicts
```

### Graph Integration

- New node: `pre_reflect` registered between `strategy` and `risk`
- New routing: `_route_after_pre_reflect()` — returns `"continue"` or `"end"`
- Existing flow untouched: risk → execution → reflection still works as before
- 6 total nodes (was 5): news, strategy, **pre_reflect**, risk, execution, reflection

## Design Decisions

1. **Simple thresholds over LLM calls** — Uses deterministic checks (strength, confluence, regime, conflicts) wrapped in `ReasoningChain` for explainability. No external LLM call needed for this gate, keeping latency low.

2. **Reuse `ChainOfThoughtEngine`** — Each signal gets a full reasoning chain with observation → evidence → inference → conclusion steps. The chain is serialized into the verdict dict for debugging/auditing.

3. **Aggregate verdict** — If multiple signals exist: any REJECT → overall REJECT; any MODIFY (without reject) → overall MODIFY. This is conservative by design.

4. **MODIFY adjusts conservatively** — Only reduces position size (by regime fit score) and tightens stop loss by 20%. Never increases risk.

5. **Non-breaking** — The existing 5-agent flow works unchanged. The pre-trade reflection is additive; if no signals exist, it auto-approves.

## Configuration Constants

```python
MIN_CONFIDENCE = 0.45      # minimum signal strength
MIN_CONFLUENCE = 0.30      # minimum confluence score
MAX_RECENT_CONFLICTS = 2   # max conflicting recent trades
```

These could be moved to a config file in a future iteration.

## Testing Notes

- All 4 modified/created files pass Python syntax validation
- `PreTradeReflection` follows the same `AlphaStackAgent` interface as all other agents
- The graph compiles with the new node (LangGraph `StateGraph.add_node` + edges)
