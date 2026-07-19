# AlphaStack Implementation Engineering Plan

**Date:** 2026-07-19  
**Author:** Engineering Agent  
**Inputs:** 9 AI weekly research files, ANALYSIS_ARCHITECTURE.md, full source tree audit  
**Purpose:** Concrete engineering plan — what to build, in what order, with actual code

---

## Table of Contents

1. [Critical Path — Build First](#1-critical-path--build-first)
2. [Model Selection Guide](#2-model-selection-guide)
3. [16-Step Strategy Pipeline Implementation Order](#3-16-step-strategy-pipeline-implementation-order)
4. [Code Architecture Patterns from Research](#4-code-architecture-patterns-from-research)
5. [Specific Code Changes Needed](#5-specific-code-changes-needed)
6. [Testing Strategy](#6-testing-strategy)
7. [4-Week Sprint Plan](#7-4-week-sprint-plan)

---

## 1. Critical Path — Build First

The architecture review scored implementation at **3.0/10** against an 8.4/10 design. The three systems that must work before anything else:

### 1.1 Data Pipeline (Priority: 🔴 CRITICAL)

**Why first:** No data → no signals → no trades → no system. Every other component is downstream.

**Current state:** `data/ingestion/market_data.py` has a solid `Tick`/`Candle`/`CandleAggregator` design but it's disconnected from the rest of the system. The `CCXTConnector` in `brokers/ccxt_connector.py` can fetch bars and ticks but isn't wired to the aggregator. The orchestrator receives `market_data` as a raw dict with no pipeline feeding it.

**What to build:**

```python
# src/alphastack/data/ingestion/live_feed.py — NEW FILE
"""Live market data feed that bridges broker connectors to the pipeline."""

from __future__ import annotations
import asyncio
from typing import Any
from alphastack.brokers.ccxt_connector import CCXTConnector
from alphastack.data.ingestion.market_data import (
    Candle, CandleAggregator, CandleTimeframe, Tick, BrokerSource,
)
from alphastack.core.events import EventBus, DataEvent
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


class LiveMarketFeed:
    """Connects CCXTConnector to CandleAggregator and publishes events."""

    def __init__(
        self,
        connector: CCXTConnector,
        event_bus: EventBus | None = None,
        timeframes: list[CandleTimeframe] | None = None,
    ) -> None:
        self.connector = connector
        self.bus = event_bus
        self.aggregator = CandleAggregator(
            timeframes or [CandleTimeframe.M5, CandleTimeframe.M15, CandleTimeframe.H1]
        )
        self._latest_candles: dict[str, dict[str, Any]] = {}
        self._latest_ticks: dict[str, Tick] = {}
        self._running = False

    async def start(self, symbols: list[str]) -> None:
        """Start streaming ticks from the connector."""
        self._running = True
        await self.connector.connect()
        await self.connector.start_ws_ticker(symbols)
        logger.info("live_feed.started", symbols=symbols)

    async def stop(self) -> None:
        self._running = False
        await self.connector.stop_ws()
        logger.info("live_feed.stopped")

    def get_market_data(self, symbol: str, bars_count: int = 200) -> dict[str, Any]:
        """Build market_data dict for the orchestrator from cached state."""
        tick = self._latest_ticks.get(symbol)
        candles = self._latest_candles.get(symbol, {})

        return {
            "symbol": symbol,
            "bid": float(tick.bid) if tick else 0.0,
            "ask": float(tick.ask) if tick else 0.0,
            "last": float(tick.last) if tick else 0.0,
            "spread_pips": float(tick.spread) if tick else 0.0,
            "volume": float(tick.volume) if tick else 0.0,
            "ohlcv": candles,  # {timeframe: [candles]}
            "timestamp": tick.timestamp.isoformat() if tick else "",
        }

    async def poll_tick(self, symbol: str) -> Tick:
        """Fetch a single tick (non-WebSocket fallback)."""
        broker_tick = await self.connector.get_tick(symbol)
        tick = Tick(
            symbol=symbol,
            broker=BrokerSource.CCXT,
            bid=str(broker_tick.bid),
            ask=str(broker_tick.ask),
            last=str(broker_tick.last),
            volume=str(broker_tick.volume),
            timestamp=broker_tick.timestamp,
        )
        self._latest_ticks[symbol] = tick
        closed = self.aggregator.process_tick(tick)
        for candle in closed:
            key = f"{candle.symbol}_{candle.timeframe.value}"
            self._latest_candles.setdefault(symbol, {})[key] = {
                "open": str(candle.open), "high": str(candle.high),
                "low": str(candle.low), "close": str(candle.close),
                "volume": str(candle.volume),
                "timestamp": candle.timestamp.isoformat(),
            }
            if self.bus:
                await self.bus.publish(DataEvent(
                    symbol=symbol, data_type="ohlcv",
                    interval=candle.timeframe.value,
                ))
        return tick
```

**Wiring into the orchestrator** (change in `agents/orchestrator/graph.py`):

```python
# In AlphaStackOrchestrator.__init__:
self.live_feed: LiveMarketFeed | None = None

def set_live_feed(self, feed: LiveMarketFeed) -> None:
    self.live_feed = feed

# In _strategy_node, before calling strategy_agent:
if self.live_feed:
    market_data = self.live_feed.get_market_data(state.get("current_symbol", "BTC/USDT"))
    s.market_data = market_data
```

**Historical data loader for backtesting:**

```python
# src/alphastack/data/ingestion/historical_loader.py — NEW FILE
"""Load historical OHLCV from CCXT for backtesting."""

async def load_historical(
    connector: CCXTConnector,
    symbol: str,
    timeframe: str,
    since: str,  # ISO date
    limit: int = 1000,
) -> list[dict]:
    """Fetch historical bars and return as list of dicts."""
    await connector.connect()
    bars = await connector.get_bars(symbol, timeframe, count=limit)
    return [
        {
            "timestamp": b.timestamp.isoformat(),
            "open": b.open, "high": b.high,
            "low": b.low, "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ]
```

### 1.2 Broker Connector Wiring (Priority: 🔴 CRITICAL)

**Current state:** `CCXTConnector` is fully implemented but the `ExecutionAgent` uses a generic `_submit_order` that tries duck-typing. The connector's `place_order()` expects a `BrokerOrder` Pydantic model, but the agent passes raw kwargs.

**What to fix in `agents/execution/agent.py`:**

```python
# Replace _submit_order with proper BrokerOrder construction:
from alphastack.brokers.models import BrokerOrder, OrderSide, OrderType

async def _submit_order(
    self,
    connector: Any,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    order_type: str,
) -> dict[str, Any]:
    """Submit via BrokerOrder model."""
    order = BrokerOrder(
        symbol=symbol,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        order_type=OrderType(order_type),
        quantity=quantity,
        price=price if order_type != "market" else 0.0,
    )
    result = await connector.place_order(order)
    return {
        "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
        "order_id": result.broker_order_id,
        "fill_price": result.avg_fill_price or price,
    }
```

**Registry wiring in `api/rest/app.py` lifespan:**

The current lifespan already registers CCXT. Add the live feed:

```python
# In lifespan(), after broker registration:
from alphastack.data.ingestion.live_feed import LiveMarketFeed
feed = LiveMarketFeed(connector, event_bus=bus)
# Store in app state for orchestrator access
app.state.live_feed = feed
```

### 1.3 Strategy Pipeline Data Flow (Priority: 🔴 CRITICAL)

**Current state:** `AlphaStackPipeline` exists with all 16 step classes, but steps are stubs — most return the context unchanged. The `StrategyAgent.execute()` calls `pipeline.run()` but the pipeline context (`AlphaStackContext`) expects real OHLCV data in `market_data` which never arrives properly.

**The data flow gap:**

```
CCXTConnector.get_bars() → [NOT WIRED] → AlphaStackContext.market_data → Pipeline steps
```

**Fix — bridge market_data dict to AlphaStackContext:**

```python
# In StrategyAgent.execute(), fix the context construction:
ctx = AlphaStackContext(
    symbol=symbol,
    timeframe=timeframe,
    market_data=market_data,  # This needs actual OHLCV arrays
)

# The pipeline steps read context.market_data.get("ohlcv") etc.
# Ensure market_data has the right shape:
# {
#   "ohlcv": {"1h": [[ts,o,h,l,c,v], ...]},  # arrays for TA-Lib
#   "bid": 65000.0,
#   "ask": 65001.0,
#   "last": 65000.5,
#   ...
# }
```

---

## 2. Model Selection Guide

Based on the voice/reasoning research and emerging systems research, here's the model assignment matrix for each agent role:

### 2.1 Cost-Optimized Configuration (Default)

| Agent Role | Model | Provider | Cost/MTok (input) | Why |
|---|---|---|---|---|
| **News Agent** | DeepSeek V4-Flash | DeepSeek API | $0.0028 (cached) | High-volume, repetitive prompts. Cache hits dominate. |
| **Strategy Agent** | DeepSeek V4-Pro | DeepSeek API | $0.003625 (cached) | Needs stronger reasoning for confluence analysis. |
| **Debate (Bull/Bear)** | DeepSeek V4-Flash | DeepSeek API | $0.0028 (cached) | Two calls per signal — cost-sensitive. |
| **Risk Agent** | Claude Sonnet 5 | Anthropic | $2.00 | Highest reliability needed. "Stays on plan, follows conventions." |
| **Execution Agent** | No LLM | — | $0 | Deterministic code — no LLM needed. |
| **Reflection Agent** | DeepSeek V4-Pro | DeepSeek API | $0.003625 (cached) | Complex reasoning for post-trade analysis. |

**Estimated daily cost (16 agents, ~1M tokens/day):** ~$2-5/day with aggressive caching.

### 2.2 High-Reliability Configuration (Live Trading)

| Agent Role | Model | Provider | Cost/MTok | Why |
|---|---|---|---|---|
| **News Agent** | Claude Sonnet 5 | Anthropic | $2.00 | News parsing accuracy critical. |
| **Strategy Agent** | GPT-5.6 Terra | OpenAI | ~$0.50 | Best reasoning for signal generation. |
| **Debate** | Claude Sonnet 5 | Anthropic | $2.00 | Debate quality directly affects trade quality. |
| **Risk Agent** | Claude Sonnet 5 | Anthropic | $2.00 | Non-negotiable reliability. |
| **Execution Agent** | No LLM | — | $0 | Deterministic. |
| **Reflection Agent** | GPT-5.6 Terra | OpenAI | ~$0.50 | Deep analysis of trade outcomes. |

### 2.3 Model Routing Implementation

```python
# src/alphastack/ai/model_router.py — NEW FILE
"""Route agent calls to the right model based on role and configuration."""

from __future__ import annotations
from dataclasses import dataclass
from alphastack.ai.model_client import AlphaModel

@dataclass
class ModelConfig:
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""

# Preset configurations
COST_OPTIMIZED = {
    "news":      ModelConfig("deepseek", "deepseek-v4-flash"),
    "strategy":  ModelConfig("deepseek", "deepseek-v4-pro"),
    "debate":    ModelConfig("deepseek", "deepseek-v4-flash"),
    "risk":      ModelConfig("anthropic", "claude-sonnet-5-20260630"),
    "execution": None,  # No LLM
    "reflection": ModelConfig("deepseek", "deepseek-v4-pro"),
}

HIGH_RELIABILITY = {
    "news":      ModelConfig("anthropic", "claude-sonnet-5-20260630"),
    "strategy":  ModelConfig("openai", "gpt-5.6-terra"),
    "debate":    ModelConfig("anthropic", "claude-sonnet-5-20260630"),
    "risk":      ModelConfig("anthropic", "claude-sonnet-5-20260630"),
    "execution": None,
    "reflection": ModelConfig("openai", "gpt-5.6-terra"),
}

class ModelRouter:
    """Provides AlphaModel instances per agent role."""

    def __init__(self, preset: str = "cost_optimized") -> None:
        configs = COST_OPTIMIZED if preset == "cost_optimized" else HIGH_RELIABILITY
        self._models: dict[str, AlphaModel | None] = {}
        for role, cfg in configs.items():
            if cfg is None:
                self._models[role] = None
            else:
                self._models[role] = AlphaModel(
                    provider=cfg.provider,
                    model=cfg.model,
                    api_key=cfg.api_key or None,
                    base_url=cfg.base_url or None,
                )

    def get(self, role: str) -> AlphaModel | None:
        return self._models.get(role)
```

### 2.4 IBM Research Insight: Cache Dynamics

From the IBM model routing research: "Cost ≠ sticker price. GPT-4.1 was nearly 2× more expensive than Claude Sonnet 4.6 in practice despite lower token pricing, due to caching dynamics."

**Action:** Track actual cost per agent call, not just token count:

```python
# Add to AlphaModel._request_with_retry:
import time
start = time.monotonic()
# ... after response:
self._metrics.record(
    provider=self._provider,
    model=self._model,
    input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
    output_tokens=data.get("usage", {}).get("completion_tokens", 0),
    cached_tokens=data.get("usage", {}).get("prompt_tokens_details", {}).get("cached_tokens", 0),
    latency_ms=int((time.monotonic() - start) * 1000),
)
```

---

## 3. 16-Step Strategy Pipeline Implementation Order

The pipeline in `strategy/pipeline.py` has all 16 steps registered but most are stubs. Here's the implementation priority:

### Phase 1: Price Action Foundation (Steps 3-5, 10)

These steps produce the core data that all other steps depend on.

**Step 3 — Session Analysis** (`s03_session.py`):
```python
async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
    from datetime import datetime, timezone
    hour = datetime.now(timezone.utc).hour

    if 12 <= hour < 16:
        session, vol = Session.LONDON, 0.9  # overlap
    elif 7 <= hour < 12:
        session, vol = Session.LONDON, 0.7
    elif 16 <= hour < 21:
        session, vol = Session.NEW_YORK, 0.6
    elif 0 <= hour < 7:
        session, vol = Session.ASIAN, 0.4
    else:
        session, vol = Session.OFF_HOURS, 0.2

    return context.update(session=SessionData(
        active=session, volatility=vol,
        typical_range_pips=self._typical_range(session, context.symbol),
    ))
```

**Step 4 — Market Structure** (`s04_structure.py`):
```python
async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
    closes = self._extract_closes(context.market_data)
    if len(closes) < 20:
        return context.update(structure=StructureData())

    # Swing detection: 5-bar lookback
    highs, lows = self._find_swings(closes, lookback=5)
    structure_type = self._classify_structure(highs, lows)
    direction = self._derive_direction(structure_type)

    return context.update(structure=StructureData(
        structure_type=structure_type,
        direction=direction,
        swing_highs=highs[-5:],
        swing_lows=lows[-5:],
    ))
```

**Step 5 — Support/Resistance** (`s05_support_resistance.py`):
```python
async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
    closes = self._extract_closes(context.market_data)
    if len(closes) < 50:
        return context.update(sr_levels=SRLevels())

    # Cluster swing points into S/R levels
    swing_prices = context.structure.swing_highs + context.structure.swing_lows
    levels = self._cluster_levels(swing_prices, tolerance_pct=0.5)

    support = [Level(price=l, strength=s, touches=t)
               for l, s, t in levels if l < closes[-1]]
    resistance = [Level(price=l, strength=s, touches=t)
                  for l, s, t in levels if l >= closes[-1]]

    return context.update(sr_levels=SRLevels(support=support, resistance=resistance))
```

**Step 10 — Confluence Engine** (`s10_confluence.py`):
```python
async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
    # Weight each component
    weights = {
        "bias": 0.15,
        "structure": 0.20,
        "sr_levels": 0.20,
        "liquidity": 0.10,
        "smc": 0.15,
        "rsi": 0.10,
        "candlestick": 0.10,
    }
    scores = {}
    # Bias alignment
    scores["bias"] = 1.0 if context.bias.bias == Bias.BULLISH else (
        0.0 if context.bias.bias == Bias.BEARISH else 0.5)
    # Structure alignment
    scores["structure"] = 1.0 if context.structure.direction == Direction.LONG else 0.0
    # S/R proximity
    last_close = self._last_close(context.market_data)
    scores["sr_levels"] = self._sr_proximity_score(last_close, context.sr_levels)
    # ... similarly for other components

    total = sum(scores[k] * weights[k] for k in weights)
    direction = Direction.LONG if total > 0.55 else (
        Direction.SHORT if total < 0.45 else Direction.NONE)

    return context.update(confluence=ConfluenceResult(
        score=total * 100,
        direction=direction,
        component_scores=scores,
    ))
```

### Phase 2: Indicator Confirmation (Steps 6-9)

**Step 6 — Liquidity Detection**: Scan for equal highs/lows, stop clusters above/below S/R.

**Step 7 — SMC (Smart Money Concepts)**: Detect order blocks, FVGs, breaker blocks from candle patterns.

**Step 8 — RSI Confirmation**: Compute RSI-14, detect overbought/oversold and divergences.

**Step 9 — Candlestick Confirmation**: Pattern recognition (engulfing, pin bars, dojis).

### Phase 3: Trade Management (Steps 11-16)

**Step 12 — Stop Loss** (runs before sizing): ATR-based or structure-based stop placement.

**Step 11 — Position Sizing**: Kelly criterion or fixed-fractional, using actual stop distance.

**Step 13 — Take Profit**: R:R-based TP levels (1:2, 1:3) at S/R zones.

**Step 14 — Trade Management**: Trailing stop rules, breakeven triggers.

**Step 15 — Exit Conditions**: Time-based, indicator-based, and P&L-based exit signals.

**Step 16 — Journal**: Log the full trade plan for reflection.

### Step 1 (Fundamental) and Step 2 (Bias) — Already Implemented

`s01_fundamental.py` and `s02_bias.py` have working code. They just need real data flowing in.

---

## 4. Code Architecture Patterns from Research

### 4.1 A2A Protocol for Agent Communication

From the multi-agent research: A2A crossed 150+ organizations, v1.0 stable. Each agent publishes an Agent Card describing capabilities.

**Don't replace LangGraph** — it's the right choice (validated by industry). But adopt A2A's Agent Card pattern for agent discovery:

```python
# src/alphastack/agents/agent_card.py — NEW FILE
"""Agent Card — A2A-inspired capability descriptor for each agent."""

from pydantic import BaseModel, Field

class AgentCard(BaseModel):
    """Describes an agent's capabilities for dynamic routing."""
    name: str
    role: str
    version: str = "1.0.0"
    capabilities: list[str] = Field(default_factory=list)
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    cost_per_call: float = 0.0  # estimated USD
    avg_latency_ms: int = 0
    reliability_score: float = 1.0  # 0-1, tracked over time

# Example usage in each agent:
class StrategyAgent(AlphaStackAgent):
    def agent_card(self) -> AgentCard:
        return AgentCard(
            name="strategy",
            role="analyst",
            capabilities=["signal_generation", "confluence_analysis", "technical_analysis"],
            input_schema={"market_data": "dict", "symbol": "str", "timeframe": "str"},
            output_schema={"signals": "list[Signal]", "pipeline_context": "dict"},
        )
```

### 4.2 Trace Mining Pipeline

From the loops research: "Agent improvement = data mining from traces. Traces are the currency of long-horizon agent improvement."

**Current state:** The reflection agent stores episodes in `EpisodicMemory` but doesn't mine patterns.

```python
# src/alphastack/agents/reflection/trace_miner.py — NEW FILE
"""Mine decision traces for improvement patterns."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from alphastack.agi.memory import EpisodicMemory, TradeEpisode

@dataclass
class TracePattern:
    """A pattern extracted from trade traces."""
    pattern_type: str  # "winning_setup", "losing_setup", "regime_shift"
    conditions: dict[str, Any]  # Market conditions when pattern occurs
    outcome: str  # "win" | "loss" | "breakeven"
    frequency: int = 0
    avg_pnl: float = 0.0
    confidence: float = 0.0

class TraceMiner:
    """Extract actionable patterns from trade history."""

    def __init__(self, memory: EpisodicMemory) -> None:
        self.memory = memory

    def mine_winning_patterns(self, min_trades: int = 10) -> list[TracePattern]:
        """Find common conditions in winning trades."""
        episodes = self.memory.get_all()
        wins = [e for e in episodes if e.outcome == "win"]
        losses = [e for e in episodes if e.outcome == "loss"]

        if len(wins) < min_trades:
            return []

        patterns = []
        # Cluster by indicator similarity
        for indicator_set in self._unique_indicator_combos(wins):
            matching_wins = [w for w in wins if self._matches_combo(w.indicators, indicator_set)]
            matching_losses = [l for l in losses if self._matches_combo(l.indicators, indicator_set)]

            win_rate = len(matching_wins) / max(len(matching_wins) + len(matching_losses), 1)
            if win_rate > 0.6 and len(matching_wins) >= 3:
                patterns.append(TracePattern(
                    pattern_type="winning_setup",
                    conditions=indicator_set,
                    outcome="win",
                    frequency=len(matching_wins),
                    avg_pnl=sum(w.pnl for w in matching_wins) / len(matching_wins),
                    confidence=win_rate,
                ))
        return sorted(patterns, key=lambda p: p.confidence * p.frequency, reverse=True)
```

### 4.3 Per-Node Timeouts (LangGraph)

From multi-agent research: LangGraph 1.0 added per-node timeouts — individual graph nodes can have configurable timeout guards.

```python
# In graph.py _build_graph(), wrap each node with timeout:
import asyncio

async def _with_timeout(coro, timeout_s: float, node_name: str):
    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except asyncio.TimeoutError:
        logger.error("node_timeout", node=node_name, timeout=timeout_s)
        return {"error": f"Node {node_name} timed out after {timeout_s}s"}

# Apply to node definitions:
NODE_TIMEOUTS = {
    "news": 30.0,       # Data fetching can be slow
    "strategy": 60.0,   # Complex reasoning
    "debate": 45.0,     # Two LLM calls
    "risk": 15.0,       # Mostly code-based
    "execution": 30.0,  # Broker API calls
    "reflection": 60.0, # Post-trade analysis
}
```

### 4.4 Context Engineering for Loops

From the loops research: "Context windows suffer from context rot — high-value instructions get buried under low-value execution data."

**Apply to the ReAct loop in `base.py`:**

```python
async def react_loop(self, query: str, max_steps: int = 5, context_budget: int = 4000) -> list[ReActStep]:
    """ReAct loop with context budget management."""
    steps = []
    total_tokens = 0

    for i in range(max_steps):
        # Compress earlier observations if approaching budget
        if total_tokens > context_budget * 0.8:
            compressed = self._compress_observations(steps[:-2])
            steps = steps[:1] + [compressed] + steps[-1:]

        step = await self._single_react_step(query, steps)
        steps.append(step)
        total_tokens += self._estimate_tokens(step)

        if step.action == "respond":
            break

    return steps
```

### 4.5 OWASP Agentic AI Governance Layer

From multi-agent research: Microsoft Agent Governance Toolkit — intercepts every agent action before execution at sub-millisecond latency.

**Apply as a policy layer between agents and execution:**

```python
# src/alphastack/security/agent_policy.py — NEW FILE
"""Policy engine — intercepts agent actions before execution."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass
class PolicyResult:
    allowed: bool
    reason: str
    modifications: dict[str, Any] | None = None

class AgentPolicyEngine:
    """Deterministic policy checks before any agent action executes."""

    def check_signal(self, signal: dict[str, Any], risk_status: dict) -> PolicyResult:
        """Check if a signal passes policy gates."""
        # Hard limits — never bypass
        if risk_status.get("circuit_breaker_active"):
            return PolicyResult(False, "Circuit breaker active — all signals blocked")

        strength = abs(signal.get("strength", 0))
        if strength > 1.0:
            return PolicyResult(False, f"Signal strength {strength} exceeds 1.0 — invalid")

        confluence = signal.get("confluence_score", 0)
        if confluence < 0.3:
            return PolicyResult(False, f"Confluence {confluence} below minimum 0.30")

        # News guard — reduce size on high-impact events
        news_adj = signal.get("news_risk_adjustment", 0)
        modifications = None
        if news_adj > 0.5:
            modifications = {"quantity_multiplier": 1.0 - news_adj}

        return PolicyResult(True, "Passed all policy checks", modifications)

    def check_execution(self, decision: dict[str, Any], portfolio: dict) -> PolicyResult:
        """Check if an execution passes policy gates."""
        max_position_pct = 0.02  # 2% of portfolio per trade
        portfolio_value = portfolio.get("equity", 0)
        trade_value = decision.get("quantity", 0) * decision.get("price", 0)

        if portfolio_value > 0 and trade_value / portfolio_value > max_position_pct:
            return PolicyResult(
                False,
                f"Position {trade_value/portfolio_value:.1%} exceeds {max_position_pct:.0%} limit",
            )
        return PolicyResult(True, "Execution approved")
```

### 4.6 CoALA Memory Architecture

From the loops research: Four memory types — Working (in-context), Episodic (past experiences), Semantic (facts/knowledge), Procedural (learned skills).

**Map to existing code:**

| CoALA Type | AlphaStack Current | What to Add |
|---|---|---|
| Working | `AgentMemory.observations` (base.py) | Already works — ephemeral per-session |
| Episodic | `EpisodicMemory` (agi/memory.py) | Add structured trade episodes with outcome tags |
| Semantic | **MISSING** | Market structure knowledge, correlation maps |
| Procedural | `SkillCreator` (reflection/post_trade.py) | Already partially implemented — skills from repeated wins |

**Add semantic memory:**

```python
# src/alphastack/agi/semantic_memory.py — NEW FILE
"""Semantic memory — persistent market knowledge."""

from __future__ import annotations
from pydantic import BaseModel, Field

class MarketKnowledge(BaseModel):
    """Facts about market structure and relationships."""
    pair_correlations: dict[str, float] = Field(default_factory=dict)
    session_volatility: dict[str, float] = Field(default_factory=dict)
    regime_history: list[dict] = Field(default_factory=list)
    support_resistance_cache: dict[str, list[float]] = Field(default_factory=dict)

    def update_correlation(self, pair_a: str, pair_b: str, correlation: float) -> None:
        key = f"{pair_a}:{pair_b}"
        self.pair_correlations[key] = correlation

    def get_regime(self, lookback_days: int = 30) -> str:
        if not self.regime_history:
            return "unknown"
        recent = self.regime_history[-lookback_days:]
        regimes = [r.get("regime", "unknown") for r in recent]
        return max(set(regimes), key=regimes.count)
```

---

## 5. Specific Code Changes Needed

### 5.1 Orchestrator Changes (`agents/orchestrator/graph.py`)

**Change 1: Add per-node timeouts**
```python
# Add to imports:
import asyncio

# Add timeout map:
NODE_TIMEOUTS = {"news": 30, "strategy": 60, "debate": 45, "risk": 15, "execution": 30, "reflection": 60}

# Wrap each node method:
async def _news_node(self, state):
    return await asyncio.wait_for(self._news_node_impl(state), timeout=NODE_TIMEOUTS["news"])
```

**Change 2: Add parallel signal debate**
Currently signals are debated sequentially. Use `asyncio.gather`:
```python
async def _debate_node(self, state):
    # ... existing setup ...
    results = await asyncio.gather(
        *(self._debate_single(signal, s) for signal in s.signals),
        return_exceptions=True,
    )
```

**Change 3: Wire live feed**
```python
def __init__(self, ...):
    # ... existing init ...
    self.live_feed: LiveMarketFeed | None = None
    self.policy_engine = AgentPolicyEngine()

def set_live_feed(self, feed: LiveMarketFeed) -> None:
    self.live_feed = feed
```

### 5.2 API Route Changes (`api/rest/routes/`)

**Fix 1: Replace in-memory stores with database**

`trades.py` uses `_TRADES: dict = {}`. Replace with PostgreSQL queries:

```python
# src/alphastack/api/rest/routes/trades.py
from alphastack.core.database import get_db_session
from alphastack.core.models import Trade

@router.get("/")
async def list_trades(
    limit: int = 50,
    offset: int = 0,
    session=Depends(get_db_session),
):
    trades = session.query(Trade).order_by(Trade.created_at.desc()).offset(offset).limit(limit).all()
    return [t.to_dict() for t in trades]
```

**Fix 2: Wire EventBus to WebSocket broadcasts**

```python
# In api/websocket/server.py, add event bus integration:
async def _on_trade_event(self, event: TradeEvent) -> None:
    """Broadcast trade events to subscribed WebSocket clients."""
    await self.broadcast("trades", event.model_dump())

# In app.py lifespan, after EventBus setup:
ws_server = get_websocket_server()
bus.subscribe(EventType.TRADE, ws_server._on_trade_event)
```

**Fix 3: Fix JWT secret persistence**

```python
# In security/auth.py (or api/rest/routes/auth.py):
# Replace: SECRET = secrets.token_urlsafe(64)
# With:
SECRET = os.environ.get("JWT_SECRET", "") or open("/run/secrets/jwt_secret").read().strip()
if not SECRET:
    raise RuntimeError("JWT_SECRET environment variable or secret file required")
```

### 5.3 Agent Base Changes (`agents/base.py`)

**Add execution timeout:**
```python
async def run(self, state: dict[str, Any]) -> dict[str, Any]:
    try:
        result = await asyncio.wait_for(
            self.execute(state),
            timeout=self._timeout_s,  # New: configurable per-agent
        )
    except asyncio.TimeoutError:
        logger.error("agent.timeout", agent=self.name, timeout=self._timeout_s)
        await self.publish_event(action="timeout", reasoning=f"{self.name} timed out")
        return {"error": f"{self.name} timed out", "_confidence": 0.0}
```

**Add circuit breaker at agent level:**
```python
class AgentCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 300.0):
        self._failures = 0
        self._threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._tripped_at: float = 0.0

    @property
    def is_open(self) -> bool:
        if self._failures >= self._threshold:
            if time.monotonic() - self._tripped_at > self._reset_timeout:
                self._failures = 0  # Half-open → try again
                return False
            return True
        return False

    def record_success(self):
        self._failures = 0

    def record_failure(self):
        self._failures += 1
        if self._failures >= self._threshold:
            self._tripped_at = time.monotonic()
```

### 5.4 Database Wiring (`core/database.py`)

**Add Alembic migrations:**

```bash
# Initialize Alembic
pip install alembic
alembic init alembic

# alembic/env.py — wire to AlphaStack models:
from alphastack.core.models import Base
target_metadata = Base.metadata

# First migration:
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

### 5.5 Risk Agent Enhancement

**Add LLM-powered risk reasoning (using Claude Sonnet 5):**

```python
# In RiskAgent.__init__:
self._model = ModelRouter(preset="cost_optimized").get("risk")

# In _evaluate_signal, for borderline cases:
if 0.3 <= confluence <= 0.5 and self._model:
    reasoning = await self._model.reasoning(
        f"Evaluate risk for: symbol={symbol}, confluence={confluence}, "
        f"drawdown={risk.drawdown_pct}%, positions={risk.open_positions}/{risk.max_positions}. "
        f"Should we approve, reject, or reduce size?"
    )
    # Parse model's recommendation
```

---

## 6. Testing Strategy

### 6.1 Unit Tests (existing tests in `tests/unit/`)

**What exists:** `test_pipeline.py`, `test_strategy_steps.py`, `test_risk.py`, `test_event_bus.py`, `test_broker_connectors.py`

**What to add:**

```python
# tests/unit/test_model_router.py
"""Test model routing per agent role."""
def test_cost_optimized_router():
    router = ModelRouter(preset="cost_optimized")
    assert router.get("news") is not None
    assert router.get("execution") is None  # No LLM
    assert "deepseek" in router.get("news").provider

# tests/unit/test_agent_policy.py
"""Test policy engine gates."""
def test_circuit_breaker_blocks_all():
    engine = AgentPolicyEngine()
    result = engine.check_signal(
        {"strength": 0.8, "confluence_score": 0.7},
        {"circuit_breaker_active": True},
    )
    assert result.allowed is False

def test_low_confluence_rejected():
    engine = AgentPolicyEngine()
    result = engine.check_signal(
        {"strength": 0.5, "confluence_score": 0.2},
        {"circuit_breaker_active": False},
    )
    assert result.allowed is False

# tests/unit/test_trace_miner.py
def test_mine_winning_patterns():
    memory = EpisodicMemory()
    # Add 15 winning trades with similar conditions
    for i in range(15):
        memory.store(TradeEpisode(
            symbol="BTC/USDT", direction="long", pnl=100.0,
            indicators={"rsi": 30 + i, "atr": 0.02},
            outcome="win",
        ))
    miner = TraceMiner(memory)
    patterns = miner.mine_winning_patterns(min_trades=10)
    assert len(patterns) > 0
    assert patterns[0].confidence > 0.6
```

### 6.2 Integration Tests (`tests/integration/`)

**What exists:** `test_pipeline_flow.py`, `test_trade_lifecycle.py`

**What to add:**

```python
# tests/integration/test_data_to_signal.py
"""Test full flow: market data → pipeline → signal generation."""
async def test_full_pipeline_with_real_data():
    """Feed real historical data through the pipeline."""
    # Load fixture data
    market_data = load_fixture("btcusdt_1h_100bars.json")

    ctx = AlphaStackContext(symbol="BTC/USDT", timeframe="1h", market_data=market_data)
    pipeline = AlphaStackPipeline(parallel=True)
    result = await pipeline.run(ctx)

    assert result.confluence.score >= 0
    assert result.confluence.direction in (Direction.LONG, Direction.SHORT, Direction.NONE)

# tests/integration/test_orchestrator_flow.py
async def test_orchestrator_end_to_end():
    """Test orchestrator with mocked broker."""
    bus = EventBus(redis_url="redis://localhost:6379/1")
    await bus.connect()

    orchestrator = AlphaStackOrchestrator(event_bus=bus, human_in_the_loop=False)

    # Mock market data
    market_data = {"last": 65000, "ohlcv": {"1h": generate_candles(100)}}
    state = await orchestrator.run(market_data=market_data, symbol="BTC/USDT")

    # Verify pipeline completed
    assert state.run_id
    assert state.current_node == "reflection" or state.error
```

### 6.3 Backtesting (`tests/backtest/`)

**What exists:** `backtester.py` with basic structure.

**Enhance:**

```python
# tests/backtest/backtester.py — enhance existing
class Backtester:
    """Run strategy pipeline against historical data."""

    async def run(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_balance: float = 10000.0,
    ) -> BacktestResult:
        # Load historical data
        bars = await load_historical(self.connector, symbol, timeframe, start_date)

        # Simulate pipeline execution per bar
        trades = []
        balance = initial_balance
        for i in range(50, len(bars)):  # Need 50 bars warmup
            window = bars[:i+1]
            market_data = {"ohlcv": {timeframe: window}, "last": bars[i]["close"]}

            ctx = AlphaStackContext(symbol=symbol, timeframe=timeframe, market_data=market_data)
            ctx = await self.pipeline.run(ctx)

            if ctx.confluence.score > 60:
                # Simulate trade
                entry = bars[i]["close"]
                sl = ctx.stop_loss.price or entry * 0.98
                tp = ctx.take_profit.levels[0] if ctx.take_profit.levels else entry * 1.04

                # Check if SL or TP hit in subsequent bars
                for j in range(i+1, min(i+50, len(bars))):
                    if bars[j]["low"] <= sl:
                        trades.append({"entry": entry, "exit": sl, "pnl": sl - entry, "result": "loss"})
                        break
                    if bars[j]["high"] >= tp:
                        trades.append({"entry": entry, "exit": tp, "pnl": tp - entry, "result": "win"})
                        break

        return BacktestResult(
            trades=trades,
            win_rate=sum(1 for t in trades if t["result"] == "win") / max(len(trades), 1),
            total_pnl=sum(t["pnl"] for t in trades),
            max_drawdown=self._calc_max_drawdown(trades, initial_balance),
        )
```

### 6.4 Test Fixtures

```python
# tests/conftest.py — add shared fixtures
import json
import pytest

@pytest.fixture
def sample_market_data():
    """Load sample OHLCV data for tests."""
    with open("tests/fixtures/btcusdt_1h_100bars.json") as f:
        return json.load(f)

@pytest.fixture
def sample_forex_data():
    """Load sample EUR/USD data for forex tests."""
    with open("tests/fixtures/eurusdt_1h_100bars.json") as f:
        return json.load(f)

@pytest.fixture
async def event_bus():
    """Provide a test EventBus connected to Redis test DB."""
    bus = EventBus(redis_url="redis://localhost:6379/15")  # Use DB 15 for tests
    await bus.connect()
    yield bus
    await bus.close()
```

---

## 7. 4-Week Sprint Plan

### Week 1: Data Pipeline + Broker Wiring

| Day | Task | Deliverable |
|---|---|---|
| **Mon** | Implement `LiveMarketFeed` class | `data/ingestion/live_feed.py` — connects CCXT to aggregator |
| **Tue** | Wire `LiveMarketFeed` into orchestrator | Orchestrator receives real market data |
| **Wed** | Fix `ExecutionAgent._submit_order` to use `BrokerOrder` | Orders flow through CCXT correctly |
| **Thu** | Implement historical data loader | `data/ingestion/historical_loader.py` for backtesting |
| **Fri** | Add Alembic migrations, wire API routes to PostgreSQL | `trades.py`, `signals.py` use DB not in-memory dicts |
| **Sat** | Integration test: data → pipeline → signal | `test_data_to_signal.py` passing |
| **Sun** | Buffer / code review / fix regressions | Clean codebase |

### Week 2: Strategy Pipeline Steps

| Day | Task | Deliverable |
|---|---|---|
| **Mon** | Implement Steps 3-4 (Session + Market Structure) | Working session detection and swing analysis |
| **Tue** | Implement Step 5 (Support/Resistance) | S/R level clustering from swing points |
| **Wed** | Implement Steps 6-7 (Liquidity + SMC) | Order block and FVG detection |
| **Thu** | Implement Steps 8-9 (RSI + Candlestick) | Indicator computation and pattern recognition |
| **Fri** | Implement Step 10 (Confluence Engine) | Weighted scoring from all components |
| **Sat** | Implement Steps 11-13 (Sizing + SL + TP) | Trade plan generation |
| **Sun** | Backtest: run pipeline on 3 months of BTC/USDT data | Win rate and P&L baseline |

### Week 3: Agent Intelligence + Model Routing

| Day | Task | Deliverable |
|---|---|---|
| **Mon** | Implement `ModelRouter` with DeepSeek V4-Flash/Pro | `ai/model_router.py` — per-role model assignment |
| **Tue** | Add LLM reasoning to Strategy Agent | Strategy agent uses V4-Pro for confluence analysis |
| **Wed** | Add LLM reasoning to Debate Engine | Bull/Bear arguments powered by V4-Flash |
| **Thu** | Add LLM reasoning to Risk Agent (borderline cases) | Risk agent uses Sonnet 5 for edge decisions |
| **Fri** | Implement `AgentPolicyEngine` | `security/agent_policy.py` — deterministic gates |
| **Sat** | Implement `TraceMiner` | `agents/reflection/trace_miner.py` — pattern extraction |
| **Sun** | End-to-end test with real API keys | Full pipeline with LLM reasoning on test data |

### Week 4: Hardening + Production Readiness

| Day | Task | Deliverable |
|---|---|---|
| **Mon** | Add per-node timeouts to orchestrator | No single agent can hang the pipeline |
| **Tue** | Add agent circuit breakers | Agents degrade gracefully on repeated failures |
| **Wed** | Fix JWT persistence + add bcrypt password hashing | Auth works across restarts |
| **Thu** | Wire EventBus → WebSocket broadcasts | Real-time data push to dashboard |
| **Fri** | Add Prometheus metrics to agents + pipeline | Observability for all agent calls |
| **Sat** | Run 1-week backtest on BTC/USDT + EUR/USD | Performance baseline established |
| **Sun** | Documentation update + IMPLEMENTATION_STATUS.md | Track what's built vs designed |

### Sprint Success Criteria

| Metric | Target | How to Measure |
|---|---|---|
| Data pipeline uptime | >99% over 7 days | Prometheus metrics |
| Signal generation | ≥1 signal/day on BTC/USDT | Pipeline output logs |
| End-to-end latency | <5s from data to signal | Timing middleware |
| LLM cost per signal | <$0.10 | Model router metrics |
| Backtest win rate | >45% (baseline) | Backtester output |
| Test coverage | >70% for core modules | pytest --cov |
| Zero hard crashes | 0 unhandled exceptions in 7 days | Error logging |

---

## Appendix: File Change Summary

### New Files to Create

| File | Purpose | Est. Lines |
|---|---|---|
| `data/ingestion/live_feed.py` | Bridge CCXT to aggregator + orchestrator | ~120 |
| `data/ingestion/historical_loader.py` | Load historical OHLCV for backtesting | ~60 |
| `ai/model_router.py` | Per-agent model assignment with presets | ~80 |
| `security/agent_policy.py` | Deterministic policy gates | ~100 |
| `agents/agent_card.py` | A2A-inspired capability descriptors | ~40 |
| `agents/reflection/trace_miner.py` | Pattern extraction from trade history | ~150 |
| `agi/semantic_memory.py` | Persistent market knowledge store | ~80 |

### Existing Files to Modify

| File | Changes |
|---|---|
| `agents/orchestrator/graph.py` | Add timeouts, live feed wiring, parallel debate |
| `agents/execution/agent.py` | Fix `_submit_order` to use `BrokerOrder` |
| `agents/base.py` | Add execution timeout, circuit breaker |
| `agents/strategy/agent.py` | Wire model router for LLM reasoning |
| `agents/risk/agent.py` | Add LLM reasoning for borderline decisions |
| `api/rest/routes/trades.py` | Replace in-memory dict with PostgreSQL |
| `api/rest/routes/signals.py` | Replace in-memory dict with PostgreSQL |
| `api/rest/routes/auth.py` | Fix JWT secret persistence |
| `api/rest/app.py` | Wire live feed, add WebSocket event bus bridge |
| `strategy/steps/s03_session.py` through `s16_journal.py` | Implement actual logic (14 files) |
| `core/database.py` | Add session factory, Alembic config |

---

*Document generated: 2026-07-19 16:21 CST*  
*Next review: End of Week 1 sprint*
