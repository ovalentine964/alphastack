# AlphaStack Swarm Design — Dual-Swarm Arbitrated Architecture

> **Author:** Swarm Architecture Agent  
> **Date:** 2026-07-16  
> **Status:** Design Complete — Ready for Implementation  
> **Depends on:** SWARM_ARCHITECTURE.md, graph.py, reasoning.py, memory.py

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Agent Specialization](#3-agent-specialization)
4. [Debate Protocol](#4-debate-protocol)
5. [Arbitrator Design](#5-arbitrator-design)
6. [Evolution Mechanism](#6-evolution-mechanism)
7. [State Extensions](#7-state-extensions)
8. [LangGraph Integration](#8-langgraph-integration)
9. [Implementation Plan](#9-implementation-plan)
10. [File Manifest](#10-file-manifest)

---

## 1. Executive Summary

The current AlphaStack orchestrator runs a **linear 5-agent pipeline**: news → strategy → risk → execution → reflection. This produces a single opinion per trading cycle. Real hedge funds run **competing research teams** whose disagreements surface better decisions.

This design replaces the monolithic strategy/risk agents with **two specialized swarms** coordinated by an **Arbitrator** that uses MiMo chain-of-thought reasoning for tie-breaking. After each trade, an **Evolution Engine** updates swarm parameters based on outcomes, closing the learning loop.

**Key design principles:**
- **Disagreement is signal, not noise** — when swarms disagree, the Arbitrator digs deeper
- **Confidence-weighted voting** — agents don't get equal votes; confidence scales influence
- **Evolution over time** — swarm parameters adapt based on real P&L outcomes
- **Backward compatible** — wraps around existing agents, doesn't break the pipeline

---

## 2. Architecture Overview

### 2.1 High-Level Flow

```
                         ┌──────────────────────┐
                         │      ORCHESTRATOR     │
                         │   (LangGraph Graph)   │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │     NEWS AGENT       │  ← unchanged
                         │  (detect events)     │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼                               ▼
          ┌─────────────────┐             ┌─────────────────┐
          │    SWARM A      │             │    SWARM B      │
          │   "OpenClaw"    │   ◄─DEBATE─►│    "Hermes"     │
          │  (Aggressive)   │             │  (Defensive)    │
          │                 │             │                 │
          │ ┌─────────────┐ │             │ ┌─────────────┐ │
          │ │  Momentum   │ │             │ │   Macro     │ │
          │ │  Scout      │ │             │ │   Analyst   │ │
          │ ├─────────────┤ │             │ ├─────────────┤ │
          │ │  Pattern    │ │             │ │ Volatility  │ │
          │ │  Hunter     │ │             │ │   Guard     │ │
          │ ├─────────────┤ │             │ ├─────────────┤ │
          │ │  Sentiment  │ │             │ │Correlation  │ │
          │ │  Reader     │ │             │ │  Checker    │ │
          │ ├─────────────┤ │             │ ├─────────────┤ │
          │ │ Liquidity   │ │             │ │ Drawdown    │ │
          │ │  Mapper     │ │             │ │  Monitor    │ │
          │ └─────────────┘ │             │ └─────────────┘ │
          └────────┬────────┘             └────────┬────────┘
                   │                               │
                   │  Swarm A Proposal             │  Swarm B Verdict
                   │  (signal + confidence)        │  (risk score + constraints)
                   │                               │
                   └───────────┬───────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │     ARBITRATOR      │
                    │  (MiMo CoT Engine)  │
                    │                     │
                    │ confidence-weighted  │
                    │ debate resolution   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │     EXECUTION       │  ← unchanged
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  EVOLUTION ENGINE   │  ← enhanced reflection
                    │                     │
                    │ • Update Swarm A    │
                    │   signal weights    │
                    │ • Update Swarm B    │
                    │   risk thresholds   │
                    │ • Store in Episodic │
                    │   Memory            │
                    └─────────────────────┘
```

### 2.2 What Changes vs. Current

| Component | Current | New |
|-----------|---------|-----|
| Strategy agent | Single monolithic agent | Decomposed into Swarm A (4 agents) |
| Risk agent | Single monolithic agent | Decomposed into Swarm B (4 agents) |
| Consensus | Risk agent approves/rejects | Arbitrator mediates debate |
| Learning | Reflection agent | Evolution Engine (enhanced reflection + weight updates) |
| Reasoning | Basic chain-of-thought | MiMo CoT with debate transcripts |
| State | AlphaStackState | Extended with swarm proposals, debate logs, evolution history |

---

## 3. Agent Specialization

### 3.1 Swarm A — "OpenClaw" (Aggressive Alpha Hunter)

Each agent runs independently and produces a **SwarmSignal** with confidence.

#### 3.1.1 Momentum Scout

**Purpose:** Identify trending assets with strong directional momentum.

**Inputs:** OHLCV data, volume profiles, multi-timeframe analysis

**Analysis:**
- Compute rate-of-change (ROC) across 3 timeframes (5m, 1h, 4h)
- Identify momentum divergences (price up but momentum fading)
- Score trend strength via ADX + directional movement index (DMI)
- Detect breakouts from consolidation ranges

**Output:**
```python
SwarmSignal(
    agent="momentum_scout",
    signal="BUY",           # BUY / SELL / HOLD
    confidence=0.82,         # 0.0 – 1.0
    reasoning="BTC 4h ROC = +8.2%, ADX = 34 (strong trend), DMI+ > DMI- confirming uptrend",
    timeframe_weight={"5m": 0.2, "1h": 0.3, "4h": 0.5},
    suggested_position_pct=1.0,  # fraction of max position
)
```

#### 3.1.2 Pattern Hunter

**Purpose:** Recognize chart patterns and compute measured-move targets.

**Inputs:** OHLCV data (candlestick patterns), support/resistance levels

**Analysis:**
- Detect candlestick patterns: engulfing, morning/evening star, hammer, doji
- Identify chart patterns: head & shoulders, flags, wedges, triangles
- Compute measured-move targets from pattern geometry
- Score pattern reliability based on historical completion rates

**Output:**
```python
SwarmSignal(
    agent="pattern_hunter",
    signal="BUY",
    confidence=0.71,
    reasoning="Bull flag on 1h chart, measured move target = $67,200. Pattern completion rate: 72%",
    pattern_type="bull_flag",
    target_price=67200.0,
    suggested_position_pct=0.8,
)
```

#### 3.1.3 Sentiment Reader

**Purpose:** Analyze news, social media, and on-chain data for directional bias.

**Inputs:** News alerts (from NewsAgent), social media feeds, on-chain metrics

**Analysis:**
- NLP sentiment scoring on headlines (positive/negative/neutral, -1 to +1)
- Social media volume spike detection (unusual Twitter/Reddit activity)
- On-chain: exchange inflow/outflow, whale wallet movements, funding rates
- Fear & Greed index integration

**Output:**
```python
SwarmSignal(
    agent="sentiment_reader",
    signal="BUY",
    confidence=0.68,
    reasoning="Headline sentiment = +0.42 (bullish), funding rate = 0.01% (neutral), exchange outflows increasing",
    sentiment_score=0.42,
    on_chain_bias="accumulation",
    suggested_position_pct=0.6,
)
```

#### 3.1.4 Liquidity Mapper

**Purpose:** Find institutional order flow and whale activity.

**Inputs:** Order book depth, trade flow (tape reading), CME futures data

**Analysis:**
- Detect large block trades (>1 std dev from mean trade size)
- Order book imbalance: bid/ask ratio at ±2% from mid
- CME futures open interest and commitment of traders (COT) data
- Identify liquidity zones (where large orders cluster)

**Output:**
```python
SwarmSignal(
    agent="liquidity_mapper",
    signal="BUY",
    confidence=0.77,
    reasoning="Order book bid/ask ratio = 1.8 (heavy bid side), $45M block buy detected at $64,800",
    order_book_imbalance=1.8,
    whale_activity="buying",
    suggested_position_pct=0.9,
)
```

### 3.2 Swarm B — "Hermes" (Defensive Risk Guardian)

Each agent runs independently and produces a **RiskAssessment** with constraints.

#### 3.2.1 Macro Analyst

**Purpose:** Check macro environment before any trade.

**Inputs:** BTC dominance, DXY (dollar index), US 10Y yield, global M2 money supply, VIX

**Analysis:**
- BTC dominance trend (rising = risk-off within crypto, altcoins bleed)
- DXY correlation: strong dollar = headwind for BTC
- Rate environment: rising rates = tighter liquidity
- Macro event calendar: FOMC, CPI, NFP within 48h = caution
- Global liquidity cycle position (expansion vs contraction)

**Output:**
```python
RiskAssessment(
    agent="macro_analyst",
    verdict="CONDITIONAL_APPROVE",  # APPROVE / CONDITIONAL_APPROVE / REJECT
    risk_score=0.35,                 # 0.0 = safe, 1.0 = maximum risk
    reasoning="DXY weakening (-0.8%), BTC dominance flat. FOMC in 36h — reduce position size by 30%",
    constraints=[
        RiskConstraint(type="position_size", value=0.7, reason="FOMC proximity"),
        RiskConstraint(type="stop_loss", value=0.02, reason="Volatility expansion expected"),
    ],
    macro_regime="risk_on",          # risk_on / risk_off / transition
)
```

#### 3.2.2 Volatility Guard

**Purpose:** Monitor volatility and adjust position sizing accordingly.

**Inputs:** ATR (14-period), realized volatility, implied volatility (if available), Bollinger Band width

**Analysis:**
- Compute ATR-based position sizing (risk 1% of portfolio per ATR)
- Detect volatility regime: low/normal/elevated/extreme
- Compare current vol to 30-day average (vol expansion/contraction)
- Adjust stop distance based on current ATR

**Output:**
```python
RiskAssessment(
    agent="volatility_guard",
    verdict="APPROVE",
    risk_score=0.25,
    reasoning="ATR(14) = $1,200 (1.8% of price), vol regime = normal. Stop at 2x ATR = $2,400 below entry",
    volatility_regime="normal",
    atr_value=1200.0,
    suggested_stop_distance=2400.0,
    constraints=[],
)
```

#### 3.2.3 Correlation Checker

**Purpose:** Ensure portfolio isn't overexposed to correlated assets.

**Inputs:** Current open positions, correlation matrix, sector exposure

**Analysis:**
- Compute rolling 30-day correlation between proposed asset and existing positions
- Flag if adding position would increase portfolio beta beyond threshold
- Check sector concentration (e.g., already long ETH + SOL, adding AVAX = too much L1 exposure)
- Diversification score

**Output:**
```python
RiskAssessment(
    agent="correlation_checker",
    verdict="APPROVE",
    risk_score=0.15,
    reasoning="BTC correlation with existing ETH position = 0.87, but ETH position is small (5% of portfolio). Diversification OK.",
    portfolio_correlation=0.87,
    sector_exposure={"L1": 0.15, "DeFi": 0.05},
    constraints=[],
)
```

#### 3.2.4 Drawdown Monitor

**Purpose:** Track max drawdown and enforce circuit breakers.

**Inputs:** Portfolio equity curve, daily P&L, drawdown history

**Analysis:**
- Compute current drawdown from equity peak
- Track consecutive losing days
- Enforce circuit breakers: daily loss > 3%, weekly loss > 7%, total DD > 15%
- Recovery factor analysis (how long does it take to recover from drawdowns?)

**Output:**
```python
RiskAssessment(
    agent="drawdown_monitor",
    verdict="APPROVE",
    risk_score=0.20,
    reasoning="Current drawdown = 1.2% from peak. Daily loss = 0.4%. All circuit breakers clear.",
    current_drawdown_pct=1.2,
    daily_loss_pct=0.4,
    circuit_breaker_active=False,
    constraints=[],
)
```

### 3.3 Aggregation

Each swarm has an **Aggregator** that collects all agent outputs:

**Swarm A Aggregator** computes a weighted composite signal:
```
composite_confidence = Σ(agent_confidence × agent_weight × agent_position_suggestion) / Σ(agent_weight)
```
Default weights (evolvable):
- Momentum Scout: 0.30
- Pattern Hunter: 0.25
- Sentiment Reader: 0.20
- Liquidity Mapper: 0.25

**Swarm B Aggregator** computes a weighted risk score:
```
composite_risk = Σ(agent_risk_score × agent_weight) / Σ(agent_weight)
verdict = REJECT if any agent vetoes, else APPROVE if composite_risk < threshold, else CONDITIONAL_APPROVE
```
Default weights (evolvable):
- Macro Analyst: 0.30
- Volatility Guard: 0.25
- Correlation Checker: 0.20
- Drawdown Monitor: 0.25

---

## 4. Debate Protocol

The debate is a structured, multi-round negotiation between Swarm A and Swarm B, mediated by the Arbitrator. It produces a **traceable decision record**.

### 4.1 Protocol Phases

```
Phase 1: PROPOSAL      → Swarm A presents signal + confidence
Phase 2: SCRUTINY      → Swarm B evaluates risk, raises objections
Phase 3: REBUTTAL      → Swarm A responds to objections (optional)
Phase 4: ARBITRATION   → Arbitrator resolves with MiMo reasoning
Phase 5: DECISION      → Final trade decision with full rationale
```

### 4.2 Debate Message Format

```python
@dataclass
class DebateMessage:
    round: int                    # debate round (1, 2, 3...)
    phase: str                    # "proposal" | "scrutiny" | "rebuttal" | "arbitration"
    sender: str                   # "swarm_a" | "swarm_b" | "arbitrator"
    content: str                  # human-readable argument
    signal: str | None            # "BUY" | "SELL" | "HOLD" | None
    confidence: float             # 0.0 – 1.0
    constraints: list[dict]       # proposed constraints/conditions
    evidence: list[str]           # supporting evidence references
    timestamp: datetime
```

### 4.3 Debate Example — Full Transcript

```
═══════════════════════════════════════════════════════════
DEBATE #2026-07-16-BTC-001          Symbol: BTC/USDT
═══════════════════════════════════════════════════════════

── PHASE 1: PROPOSAL ─────────────────────────────────────

SWARM A (OpenClaw) — Round 1:
┌─────────────────────────────────────────────────────────┐
│ Signal:     BUY BTC at $65,000                          │
│ Confidence: 85%                                         │
│ Position:   100% of max allocation                      │
│                                                         │
│ Evidence:                                                │
│  • Momentum Scout (82%): 4h ROC +8.2%, ADX=34           │
│  • Pattern Hunter (71%): Bull flag, target $67,200       │
│  • Sentiment Reader (68%): Headlines +0.42, outflows ↑  │
│  • Liquidity Mapper (77%): Bid/ask 1.8, $45M whale buy  │
│                                                         │
│ Composite Confidence: 85%                               │
│ Suggested Stop Loss: $63,200 (-2.8%)                    │
│ Suggested Take Profit: $67,200 (+3.4%)                  │
└─────────────────────────────────────────────────────────┘

── PHASE 2: SCRUTINY ─────────────────────────────────────

SWARM B (Hermes) — Round 1:
┌─────────────────────────────────────────────────────────┐
│ Verdict:    CONDITIONAL_APPROVE                         │
│ Risk Score: 42/100                                      │
│                                                         │
│ Objections:                                              │
│  1. Macro Analyst: FOMC in 36h — reduce position 30%    │
│  2. Volatility Guard: ATR elevated — widen stop to 3.5% │
│  3. Drawdown Monitor: Approve, DD only 1.2%             │
│  4. Correlation Checker: Approve, no concentration risk  │
│                                                         │
│ Constraints:                                             │
│  • Max position: 70% (FOMC proximity)                   │
│  • Stop loss: $62,725 (-3.5%)                           │
│  • No leverage                                           │
└─────────────────────────────────────────────────────────┘

── PHASE 3: REBUTTAL ─────────────────────────────────────

SWARM A (OpenClaw) — Round 2:
┌─────────────────────────────────────────────────────────┐
│ Response to objections:                                  │
│                                                         │
│  • Accept FOMC concern — will reduce to 70% position    │
│  • Dispute volatility concern — ATR is 1.8%, not        │
│    elevated. $63,200 stop is 2x ATR, adequate.         │
│  • Counter: Tight stop means smaller loss if wrong,     │
│    but maintaining wider stop risks missing the move.   │
│                                                         │
│ Revised Proposal:                                        │
│  • Position: 70% (accepted)                             │
│  • Stop: $63,200 (maintained, 2x ATR)                  │
│  • Take Profit: $67,200 (maintained)                    │
│  • Confidence: 82% (slightly reduced for FOMC risk)     │
└─────────────────────────────────────────────────────────┘

── PHASE 4: ARBITRATION ──────────────────────────────────

ARBITRATOR — MiMo Chain-of-Thought:
┌─────────────────────────────────────────────────────────┐
│ Step 1 (Observation):                                    │
│   Swarm A confidence: 82%, composite signal: BUY        │
│   Swarm B risk score: 42/100, verdict: CONDITIONAL      │
│   Key tension: stop loss placement (2.8% vs 3.5%)       │
│                                                         │
│ Step 2 (Hypothesis):                                     │
│   Both swarms agree on direction (BUY). Disagreement    │
│   is on position sizing and stop placement. This is a   │
│   negotiation, not a conflict.                          │
│                                                         │
│ Step 3 (Evidence Weighing):                              │
│   • Historical data: BTC ATR(14) = $1,200 = 1.8%       │
│     2x ATR = $2,400 = 3.7% → closer to Swarm B's       │
│     3.5% recommendation                                 │
│   • FOMC historically causes ±3% BTC moves in 24h       │
│   • Whale buying is strong signal but doesn't negate    │
│     macro risk                                          │
│   • Past similar debates (episodic memory): when both    │
│     swarms agreed on direction but differed on sizing,  │
│     the tighter stop was hit 40% of the time vs 15%     │
│     for the wider stop.                                 │
│                                                         │
│ Step 4 (Inference):                                      │
│   Accept Swarm B's wider stop (3.5%) given FOMC         │
│   proximity and historical ATR data. Compromise on      │
│   position at 70%. Accept Swarm A's TP target.          │
│                                                         │
│ Step 5 (Conclusion):                                     │
│   Final decision: BUY BTC at $65,000                    │
│   Position: 70% of max allocation                       │
│   Stop Loss: $62,725 (-3.5%)                            │
│   Take Profit: $67,200 (+3.4%)                          │
│   R:R Ratio: 1:0.97 → acceptable given high confidence  │
│   Confidence: 78%                                       │
└─────────────────────────────────────────────────────────┘

── PHASE 5: DECISION ─────────────────────────────────────

FINAL DECISION:
  Action:     BUY BTC/USDT
  Entry:      $65,000 (market)
  Position:   70% of max allocation
  Stop Loss:  $62,725 (-3.5%)
  Take Profit: $67,200 (+3.4%)
  R:R:        1:0.97
  Confidence: 78%
  Dissent:    None (consensus reached)

═══════════════════════════════════════════════════════════
```

### 4.4 Debate Rules

| Rule | Description |
|------|-------------|
| **Max rounds** | 3 rounds maximum (proposal → scrutiny → rebuttal → arbitration) |
| **Timeout** | Each swarm has 30 seconds per round |
| **Veto power** | Swarm B can veto if any agent flags `risk_score > 0.90` (circuit breaker) |
| **Confidence floor** | If composite confidence < 40% after debate, no trade |
| **Escalation** | If swarms can't converge in 3 rounds, Arbitrator decides unilaterally |
| **Transcript** | Every debate is logged in full for audit and evolution |

---

## 5. Arbitrator Design

### 5.1 Core Architecture

The Arbitrator is **not** a separate LLM call — it's a deterministic reasoning engine built on the existing `ChainOfThoughtEngine` from `reasoning.py`, extended with debate-specific steps.

```python
class Arbitrator:
    """Resolves disagreements between Swarm A and Swarm B.
    
    Uses confidence-weighted voting + MiMo chain-of-thought reasoning
    for tie-breaking. Produces a traceable decision record.
    """
    
    def __init__(
        self,
        reasoning_engine: ChainOfThoughtEngine,
        episodic_memory: EpisodicMemory,
        swarm_a_weights: dict[str, float] | None = None,
        swarm_b_weights: dict[str, float] | None = None,
    ):
        self.reasoning = reasoning_engine
        self.memory = episodic_memory
        self.swarm_a_weights = swarm_a_weights or SWARM_A_DEFAULT_WEIGHTS
        self.swarm_b_weights = swarm_b_weights or SWARM_B_DEFAULT_WEIGHTS
```

### 5.2 Decision Algorithm

```python
async def arbitrate(
    self,
    swarm_a_proposal: SwarmProposal,
    swarm_b_assessment: SwarmAssessment,
    market_context: dict[str, Any],
) -> ArbitrationResult:
    """Main arbitration entry point.
    
    Decision tree:
    1. If both swarms agree → fast path (no debate needed)
    2. If Swarm B hard vetoes → reject (safety override)
    3. If soft disagreement → confidence-weighted vote + CoT reasoning
    """
    
    # ── Step 1: Check for consensus ──
    if swarm_a_proposal.signal == "HOLD" and swarm_b_assessment.verdict == "APPROVE":
        return ArbitrationResult(action="HOLD", reason="No signal from Swarm A")
    
    if swarm_a_proposal.signal in ("BUY", "SELL") and swarm_b_assessment.verdict == "APPROVE":
        # Both agree — fast path
        return self._fast_path(swarm_a_proposal, swarm_b_assessment)
    
    # ── Step 2: Check for hard veto ──
    if swarm_b_assessment.has_hard_veto():
        return ArbitrationResult(
            action="REJECT",
            reason=f"Safety veto: {swarm_b_assessment.veto_reason}",
            confidence=0.95,
        )
    
    # ── Step 3: Soft disagreement → full arbitration ──
    return await self._full_arbitration(
        swarm_a_proposal, swarm_b_assessment, market_context,
    )
```

### 5.3 Confidence-Weighted Voting

When swarms disagree, votes are weighted by confidence × agent weight:

```python
def _confidence_weighted_vote(
    self,
    swarm_a: SwarmProposal,
    swarm_b: SwarmAssessment,
) -> tuple[str, float]:
    """Compute confidence-weighted vote.
    
    Returns (direction, net_confidence).
    Positive net_confidence = BUY, negative = SELL.
    """
    # Swarm A vote: signal direction × composite confidence
    a_direction = {"BUY": 1.0, "SELL": -1.0, "HOLD": 0.0}[swarm_a.signal]
    a_vote = a_direction * swarm_a.composite_confidence  # e.g., 1.0 * 0.85 = 0.85
    
    # Swarm B vote: risk-adjusted confidence
    # APPROVE = full support, CONDITIONAL = partial, REJECT = opposition
    b_multiplier = {
        "APPROVE": 0.5,            # supports but doesn't drive direction
        "CONDITIONAL_APPROVE": 0.0, # neutral — wants constraints
        "REJECT": -1.0,            # opposes the trade
    }[swarm_b.verdict]
    b_vote = b_multiplier * (1.0 - swarm_b.risk_score)  # higher risk = stronger opposition
    
    net = a_vote + b_vote
    
    if net > 0.1:
        direction = "BUY"
    elif net < -0.1:
        direction = "SELL"
    else:
        direction = "HOLD"
    
    return direction, round(abs(net), 4)
```

**Decision matrix:**

| Swarm A Signal | Swarm A Conf | Swarm B Verdict | Swarm B Risk | Net Vote | Decision |
|---------------|-------------|----------------|-------------|---------|----------|
| BUY | 0.85 | APPROVE | 0.20 | +0.91 | BUY |
| BUY | 0.85 | CONDITIONAL | 0.42 | +0.85 | BUY (with constraints) |
| BUY | 0.85 | REJECT | 0.75 | +0.60 | BUY (debate needed) |
| BUY | 0.60 | REJECT | 0.75 | +0.35 | BUY (weak, debate needed) |
| BUY | 0.40 | REJECT | 0.80 | +0.20 | HOLD (too close) |
| BUY | 0.30 | REJECT | 0.85 | +0.15 | HOLD (too close) |
| BUY | 0.20 | REJECT | 0.90 | +0.10 | REJECT |
| HOLD | any | APPROVE | any | ~0 | HOLD |

### 5.4 MiMo Chain-of-Thought for Tie-Breaking

When the confidence-weighted vote is ambiguous (net vote between -0.3 and +0.3), the Arbitrator invokes MiMo reasoning:

```python
async def _full_arbitration(
    self,
    swarm_a: SwarmProposal,
    swarm_b: SwarmAssessment,
    market_context: dict[str, Any],
) -> ArbitrationResult:
    """Full arbitration with MiMo chain-of-thought."""
    
    chain = self.reasoning.start_chain(
        topic=f"Arbitration: {swarm_a.signal} {market_context.get('symbol', '?')}"
    )
    
    # Step 1: Observe both positions
    chain.add_step(
        ReasoningStepType.OBSERVATION,
        f"Swarm A: {swarm_a.signal} (confidence={swarm_a.composite_confidence:.0%}), "
        f"Swarm B: {swarm_b.verdict} (risk={swarm_b.risk_score:.0%})",
        confidence=0.95,
    )
    
    # Step 2: Identify the core disagreement
    disagreements = self._identify_disagreements(swarm_a, swarm_b)
    chain.add_step(
        ReasoningStepType.OBSERVATION,
        f"Core disagreements: {disagreements}",
        confidence=0.90,
    )
    
    # Step 3: Consult episodic memory for similar past debates
    similar_cases = self._find_similar_debates(swarm_a, market_context)
    if similar_cases:
        chain.add_step(
            ReasoningStepType.EVIDENCE,
            f"Found {len(similar_cases)} similar past cases. "
            f"Outcome distribution: {self._case_outcome_summary(similar_cases)}",
            confidence=0.75,
            evidence_refs=[c["episode_id"] for c in similar_cases],
        )
    
    # Step 4: Weigh technical vs macro evidence
    technical_strength = swarm_a.composite_confidence
    macro_risk = swarm_b.risk_score
    
    if technical_strength > macro_risk + 0.2:
        hypothesis = "Technical signals outweigh macro risk — lean toward trade"
        hyp_conf = min(technical_strength, 0.85)
    elif macro_risk > technical_strength + 0.2:
        hypothesis = "Macro risk outweighs technical signals — lean toward caution"
        hyp_conf = min(1.0 - macro_risk + 0.3, 0.85)
    else:
        hypothesis = "Technical and macro signals are balanced — need tie-breaker"
        hyp_conf = 0.5
    
    chain.add_step(ReasoningStepType.HYPOTHESIS, hypothesis, confidence=hyp_conf)
    
    # Step 5: Apply constraints from both swarms
    constraints = self._merge_constraints(swarm_a, swarm_b)
    chain.add_step(
        ReasoningStepType.INFERENCE,
        f"Merged constraints: {constraints}. R:R after constraints = {self._compute_rr(constraints)}",
        confidence=0.80,
    )
    
    # Step 6: Final decision
    if technical_strength > macro_risk:
        direction = swarm_a.signal
        position_pct = min(
            swarm_a.suggested_position_pct,
            1.0 - swarm_b.risk_score * 0.5,  # reduce position by risk
        )
    else:
        direction = "HOLD"
        position_pct = 0.0
    
    chain.finalize(
        conclusion=f"Decision: {direction} at {position_pct:.0%} position. {hypothesis}"
    )
    
    return ArbitrationResult(
        action=direction,
        position_pct=round(position_pct, 2),
        constraints=constraints,
        confidence=chain.overall_confidence,
        reasoning_chain=chain,
        debate_transcript=self._build_transcript(swarm_a, swarm_b, chain),
    )
```

### 5.5 Constraint Merging

When both swarms propose constraints, the Arbitrator merges them conservatively:

```python
def _merge_constraints(
    self,
    swarm_a: SwarmProposal,
    swarm_b: SwarmAssessment,
) -> MergedConstraints:
    """Merge constraints from both swarms. Conservative wins."""
    
    # Position size: take the smaller
    a_pos = swarm_a.suggested_position_pct
    b_pos = swarm_b.max_position_pct  # from constraints
    final_pos = min(a_pos, b_pos) if b_pos else a_pos
    
    # Stop loss: take the wider (more protective) stop
    a_stop = swarm_a.stop_loss_pct  # e.g., -2.8%
    b_stop = swarm_b.min_stop_loss_pct  # e.g., -3.5%
    final_stop = min(a_stop, b_stop)  # more negative = wider stop
    
    # Take profit: take the more conservative target
    a_tp = swarm_a.take_profit_pct
    b_tp = swarm_b.max_tp_pct if swarm_b.max_tp_pct else a_tp
    final_tp = min(a_tp, b_tp)
    
    return MergedConstraints(
        position_pct=final_pos,
        stop_loss_pct=final_stop,
        take_profit_pct=final_tp,
        leverage=1.0,  # default: no leverage unless both agree
        time_limit_hours=swarm_b.time_limit_hours or None,
    )
```

---

## 6. Evolution Mechanism

### 6.1 Overview

After each trade cycle, the Evolution Engine reviews outcomes and updates swarm parameters. This is the **self-improvement loop**.

```
Trade Executed → Price Moves → Outcome Known
                                      │
                                      ▼
                            ┌─────────────────┐
                            │ EVOLUTION ENGINE │
                            │                 │
                            │ 1. Evaluate     │
                            │    each agent's  │
                            │    prediction    │
                            │                 │
                            │ 2. Update Swarm │
                            │    A weights     │
                            │                 │
                            │ 3. Update Swarm │
                            │    B thresholds  │
                            │                 │
                            │ 4. Store in     │
                            │    Episodic     │
                            │    Memory       │
                            └─────────────────┘
```

### 6.2 Agent Performance Tracking

Each agent's predictions are tracked over time:

```python
@dataclass
class AgentTrackRecord:
    """Tracks an individual agent's prediction accuracy over time."""
    agent_name: str
    swarm: str  # "A" or "B"
    
    # Rolling metrics
    total_predictions: int = 0
    correct_direction: int = 0       # predicted direction matched outcome
    confidence_calibration: float = 0.0  # how well confidence matches accuracy
    
    # Per-signal-type accuracy
    buy_accuracy: float = 0.0        # % of BUY signals that were profitable
    sell_accuracy: float = 0.0       # % of SELL signals that were profitable
    hold_accuracy: float = 0.0       # % of HOLD that was correct (avoided loss)
    
    # Recent window (last N trades)
    recent_accuracy: float = 0.0     # last 20 trades
    recent_confidence: float = 0.0   # average confidence of last 20
    
    # Weight history
    current_weight: float = 0.25     # current voting weight
    weight_history: list[tuple[datetime, float]] = field(default_factory=list)
```

### 6.3 Swarm A Weight Updates

After each trade, update agent weights based on who was right:

```python
class SwarmAEvolution:
    """Evolution engine for Swarm A (aggressive) agents."""
    
    def __init__(
        self,
        episodic_memory: EpisodicMemory,
        learning_rate: float = 0.05,
        min_weight: float = 0.10,
        max_weight: float = 0.45,
        lookback_window: int = 20,
    ):
        self.memory = episodic_memory
        self.lr = learning_rate
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.lookback = lookback_window
        self.track_records: dict[str, AgentTrackRecord] = {}
    
    def update_weights(
        self,
        trade_outcome: TradeOutcome,
        agent_signals: dict[str, SwarmSignal],  # agent_name → signal
    ) -> dict[str, float]:
        """Update weights based on trade outcome.
        
        Algorithm:
        1. For each agent, check if their signal direction matched outcome
        2. Agents that were correct get weight increased
        3. Agents that were wrong get weight decreased
        4. Confidence calibration: if agent said 90% confident and was wrong,
           penalize more than if they said 55% confident and were wrong
        5. Normalize weights to sum to 1.0
        """
        profitable = trade_outcome.pnl > 0
        
        adjustments: dict[str, float] = {}
        
        for agent_name, signal in agent_signals.items():
            track = self.track_records.setdefault(
                agent_name,
                AgentTrackRecord(agent_name=agent_name, swarm="A"),
            )
            
            # Was the agent's direction correct?
            direction_correct = (
                (signal.signal == "BUY" and profitable) or
                (signal.signal == "SELL" and not profitable) or
                (signal.signal == "HOLD")
            )
            
            if direction_correct:
                # Reward: increase weight proportional to confidence
                adjustment = self.lr * signal.confidence
            else:
                # Penalize: decrease weight proportional to overconfidence
                # If agent was 90% confident and wrong, bigger penalty
                overconfidence = signal.confidence - 0.5  # how much above neutral
                adjustment = -self.lr * max(overconfidence, 0.1)
            
            adjustments[agent_name] = adjustment
            
            # Update track record
            track.total_predictions += 1
            if direction_correct:
                track.correct_direction += 1
        
        # Apply adjustments and normalize
        current_weights = {r.agent_name: r.current_weight for r in self.track_records.values()}
        
        for agent_name, adj in adjustments.items():
            new_weight = current_weights.get(agent_name, 0.25) + adj
            new_weight = max(self.min_weight, min(self.max_weight, new_weight))
            current_weights[agent_name] = new_weight
        
        # Normalize to sum to 1.0
        total = sum(current_weights.values())
        normalized = {k: round(v / total, 4) for k, v in current_weights.items()}
        
        # Update track records
        for agent_name, weight in normalized.items():
            track = self.track_records[agent_name]
            track.current_weight = weight
            track.weight_history.append((datetime.utcnow(), weight))
        
        return normalized
```

**Weight update examples:**

| Scenario | Agent | Old Weight | Signal | Confidence | Outcome | Adjustment | New Weight |
|----------|-------|-----------|--------|-----------|---------|-----------|-----------|
| Correct high-confidence | Momentum Scout | 0.30 | BUY | 0.85 | Profitable | +0.0425 | 0.34 |
| Wrong high-confidence | Pattern Hunter | 0.25 | BUY | 0.80 | Loss | -0.015 | 0.21 |
| Correct low-confidence | Sentiment Reader | 0.20 | BUY | 0.55 | Profitable | +0.0275 | 0.23 |
| Wrong low-confidence | Liquidity Mapper | 0.25 | BUY | 0.60 | Loss | -0.005 | 0.22 |

### 6.4 Swarm B Threshold Updates

Swarm B evolves its risk thresholds — was it too conservative (missing good trades) or too aggressive (allowing bad trades)?

```python
class SwarmBEvolution:
    """Evolution engine for Swarm B (defensive) agents."""
    
    def __init__(
        self,
        episodic_memory: EpisodicMemory,
        learning_rate: float = 0.03,
    ):
        self.memory = episodic_memory
        self.lr = learning_rate
        self.threshold_history: dict[str, list[tuple[datetime, float]]] = {}
    
    def update_thresholds(
        self,
        trade_outcome: TradeOutcome,
        swarm_b_assessment: SwarmAssessment,
        arbitrated_action: str,
    ) -> dict[str, float]:
        """Update risk thresholds based on trade outcome.
        
        Key question: Was Swarm B's caution justified?
        
        Cases:
        1. Trade was profitable + Swarm B wanted to reject → too conservative
           → loosen thresholds (lower risk scores for similar conditions)
        2. Trade was a loss + Swarm B wanted to reject → correctly cautious
           → maintain or tighten thresholds
        3. Trade was profitable + Swarm B approved → correctly calibrated
           → no change
        4. Trade was a loss + Swarm B approved → too aggressive
           → tighten thresholds
        """
        profitable = trade_outcome.pnl > 0
        swarm_b_rejected = swarm_b_assessment.verdict == "REJECT"
        trade_executed = arbitrated_action in ("BUY", "SELL")
        
        adjustments: dict[str, float] = {}
        
        for agent_name, assessment in swarm_b_assessment.agent_assessments.items():
            if profitable and swarm_b_rejected and trade_executed:
                # Case 1: Too conservative — loosen
                adjustments[agent_name] = self.lr  # positive = loosen
            elif not profitable and not swarm_b_rejected:
                # Case 4: Too aggressive — tighten
                adjustments[agent_name] = -self.lr  # negative = tighten
            else:
                # Cases 2 & 3: Well calibrated — no change
                adjustments[agent_name] = 0.0
        
        return adjustments
```

### 6.5 Evolution Storage

All evolution data is stored in the AGI Episodic Memory:

```python
@dataclass
class EvolutionRecord:
    """Record of a parameter evolution event."""
    record_id: str
    timestamp: datetime
    trade_episode_id: str          # link to TradeEpisode
    
    # What changed
    swarm: str                     # "A" or "B"
    agent_name: str
    parameter: str                 # "weight" or "threshold"
    old_value: float
    new_value: float
    reason: str
    
    # Context
    trade_outcome: str             # "win" | "loss"
    pnl: float
    confidence_at_decision: float
```

The Evolution Engine stores these alongside TradeEpisodes in EpisodicMemory, enabling queries like:
- "What happened the last 5 times Momentum Scout was wrong?"
- "Has Drawdown Monitor been too conservative in trending markets?"
- "Which agent's weights have changed the most in the last 30 days?"

### 6.6 Evolution Schedule

| Trigger | Action |
|---------|--------|
| After each trade execution | Update agent track records |
| After trade outcome known (price hit TP/SL) | Update weights and thresholds |
| Every 20 trades | Compute calibration metrics, flag miscalibrated agents |
| Weekly | Full evolution report, normalize weights if any drifted too far |
| Monthly | Review evolution history, reset weights if system has drifted |

---

## 7. State Extensions

### 7.1 New State Models

```python
# ── Swarm Signal ──────────────────────────────────────────

class SwarmSignal(BaseModel):
    """Output from an individual swarm agent."""
    agent_name: str
    swarm: Literal["A", "B"]
    signal: Literal["BUY", "SELL", "HOLD"]
    confidence: float = 0.0
    reasoning: str = ""
    suggested_position_pct: float = 1.0
    suggested_stop_loss_pct: float | None = None
    suggested_take_profit_pct: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SwarmProposal(BaseModel):
    """Aggregated proposal from Swarm A."""
    signal: Literal["BUY", "SELL", "HOLD"]
    composite_confidence: float = 0.0
    suggested_position_pct: float = 1.0
    stop_loss_pct: float = -0.028
    take_profit_pct: float = 0.034
    agent_signals: list[SwarmSignal] = Field(default_factory=list)
    reasoning: str = ""


class RiskAssessment(BaseModel):
    """Output from an individual Swarm B agent."""
    agent_name: str
    verdict: Literal["APPROVE", "CONDITIONAL_APPROVE", "REJECT"]
    risk_score: float = 0.0  # 0.0 = safe, 1.0 = max risk
    reasoning: str = ""
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SwarmAssessment(BaseModel):
    """Aggregated assessment from Swarm B."""
    verdict: Literal["APPROVE", "CONDITIONAL_APPROVE", "REJECT"]
    composite_risk_score: float = 0.0
    agent_assessments: dict[str, RiskAssessment] = Field(default_factory=dict)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    veto_reason: str = ""


# ── Debate ────────────────────────────────────────────────

class DebateMessage(BaseModel):
    """A single message in the swarm debate."""
    round: int
    phase: Literal["proposal", "scrutiny", "rebuttal", "arbitration"]
    sender: Literal["swarm_a", "swarm_b", "arbitrator"]
    content: str
    signal: str | None = None
    confidence: float = 0.0
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DebateTranscript(BaseModel):
    """Full record of a swarm debate."""
    debate_id: str = ""
    symbol: str = ""
    started_at: datetime = Field(default_factory=datetime.utcnow)
    messages: list[DebateMessage] = Field(default_factory=list)
    rounds: int = 0
    outcome: str = ""  # "consensus", "arbitration", "veto", "timeout"


# ── Arbitration ───────────────────────────────────────────

class MergedConstraints(BaseModel):
    """Constraints merged from both swarms."""
    position_pct: float = 1.0
    stop_loss_pct: float = -0.028
    take_profit_pct: float = 0.034
    leverage: float = 1.0
    time_limit_hours: int | None = None


class ArbitrationResult(BaseModel):
    """Final output of the Arbitrator."""
    action: Literal["BUY", "SELL", "HOLD", "REJECT"]
    position_pct: float = 0.0
    constraints: MergedConstraints = Field(default_factory=MergedConstraints)
    confidence: float = 0.0
    reasoning_chain_id: str = ""
    debate_transcript: DebateTranscript = Field(default_factory=DebateTranscript)
    reasoning_summary: str = ""


# ── Evolution ─────────────────────────────────────────────

class TradeOutcome(BaseModel):
    """Outcome of an executed trade for evolution purposes."""
    trade_id: str
    symbol: str
    action: str
    entry_price: float
    exit_price: float | None = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    outcome: Literal["win", "loss", "breakeven", "open"] = "open"
    duration_hours: float = 0.0
    swarm_a_confidence: float = 0.0
    swarm_b_risk_score: float = 0.0


class EvolutionUpdate(BaseModel):
    """A parameter update from the Evolution Engine."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trade_episode_id: str
    swarm: Literal["A", "B"]
    agent_name: str
    parameter: str
    old_value: float
    new_value: float
    reason: str
```

### 7.2 Extended AlphaStackState

New fields added to `AlphaStackState`:

```python
class AlphaStackState(BaseModel):
    # ... existing fields ...
    
    # ── Swarm A (OpenClaw) ────────────────────────────────
    swarm_a_proposal: SwarmProposal | None = None
    swarm_a_signals: list[SwarmSignal] = Field(default_factory=list)
    swarm_a_weights: dict[str, float] = Field(default_factory=lambda: {
        "momentum_scout": 0.30,
        "pattern_hunter": 0.25,
        "sentiment_reader": 0.20,
        "liquidity_mapper": 0.25,
    })
    
    # ── Swarm B (Hermes) ──────────────────────────────────
    swarm_b_assessment: SwarmAssessment | None = None
    swarm_b_signals: list[RiskAssessment] = Field(default_factory=list)
    swarm_b_weights: dict[str, float] = Field(default_factory=lambda: {
        "macro_analyst": 0.30,
        "volatility_guard": 0.25,
        "correlation_checker": 0.20,
        "drawdown_monitor": 0.25,
    })
    
    # ── Debate ────────────────────────────────────────────
    debate_transcript: DebateTranscript | None = None
    
    # ── Arbitration ───────────────────────────────────────
    arbitration_result: ArbitrationResult | None = None
    
    # ── Evolution ─────────────────────────────────────────
    evolution_updates: list[EvolutionUpdate] = Field(default_factory=list)
    trade_outcome: TradeOutcome | None = None
```

---

## 8. LangGraph Integration

### 8.1 New Graph Structure

The orchestrator graph is extended with swarm nodes:

```
START
  │
  ▼
news ─────────────────── (unchanged)
  │
  ├─── parallel ────────────────────────────┐
  │                                          │
  ▼                                          ▼
swarm_a                                    swarm_b
(swarm_a_momentum ──► swarm_a_pattern ──►  (swarm_b_macro ──► swarm_b_volatility ──►
 swarm_a_sentiment ─► swarm_a_liquidity    swarm_b_correlation ─► swarm_b_drawdown ──►
 ──► swarm_a_aggregate)                     ──► swarm_b_aggregate)
  │                                          │
  └───────────────┬──────────────────────────┘
                  │
                  ▼
              debate
         (if disagreement)
                  │
                  ▼
            arbitrator
                  │
                  ├── approved ──► human_review ──► execution
                  │                                    │
                  └── rejected ──► END            reflection
                                                    │
                                                evolution
                                                    │
                                                    END
```

### 8.2 Implementation in graph.py

```python
# New nodes to add to the orchestrator

class AlphaStackOrchestrator:
    def __init__(self, ...):
        # ... existing agents ...
        
        # New: Swarm A agents
        self.momentum_scout = MomentumScoutAgent(event_bus=event_bus)
        self.pattern_hunter = PatternHunterAgent(event_bus=event_bus)
        self.sentiment_reader = SentimentReaderAgent(event_bus=event_bus)
        self.liquidity_mapper = LiquidityMapperAgent(event_bus=event_bus)
        self.swarm_a_aggregator = SwarmAAggregator(event_bus=event_bus)
        
        # New: Swarm B agents
        self.macro_analyst = MacroAnalystAgent(event_bus=event_bus)
        self.volatility_guard = VolatilityGuardAgent(event_bus=event_bus)
        self.correlation_checker = CorrelationCheckerAgent(event_bus=event_bus)
        self.drawdown_monitor = DrawdownMonitorAgent(event_bus=event_bus)
        self.swarm_b_aggregator = SwarmBAggregator(event_bus=event_bus)
        
        # New: Arbitrator and Evolution
        self.arbitrator = Arbitrator(reasoning_engine, episodic_memory)
        self.evolution_engine = EvolutionEngine(episodic_memory)
    
    def _build_graph(self) -> Any:
        graph = StateGraph(AlphaStackState)
        
        # Existing nodes
        graph.add_node("news", self._news_node)
        graph.add_node("execution", self._execution_node)
        graph.add_node("reflection", self._reflection_node)
        graph.add_node("human_review", self._human_review_node)
        
        # New: Swarm A nodes
        graph.add_node("swarm_a_momentum", self._swarm_a_momentum_node)
        graph.add_node("swarm_a_pattern", self._swarm_a_pattern_node)
        graph.add_node("swarm_a_sentiment", self._swarm_a_sentiment_node)
        graph.add_node("swarm_a_liquidity", self._swarm_a_liquidity_node)
        graph.add_node("swarm_a_aggregate", self._swarm_a_aggregate_node)
        
        # New: Swarm B nodes
        graph.add_node("swarm_b_macro", self._swarm_b_macro_node)
        graph.add_node("swarm_b_volatility", self._swarm_b_volatility_node)
        graph.add_node("swarm_b_correlation", self._swarm_b_correlation_node)
        graph.add_node("swarm_b_drawdown", self._swarm_b_drawdown_node)
        graph.add_node("swarm_b_aggregate", self._swarm_b_aggregate_node)
        
        # New: Debate and Arbitration
        graph.add_node("debate", self._debate_node)
        graph.add_node("arbitrator", self._arbitrator_node)
        graph.add_node("evolution", self._evolution_node)
        
        # ── Edges ──
        graph.set_entry_point("news")
        graph.add_edge("news", "swarm_a_momentum")
        graph.add_edge("news", "swarm_b_macro")  # parallel entry
        
        # Swarm A internal flow (sequential — each builds on prior)
        graph.add_edge("swarm_a_momentum", "swarm_a_pattern")
        graph.add_edge("swarm_a_pattern", "swarm_a_sentiment")
        graph.add_edge("swarm_a_sentiment", "swarm_a_liquidity")
        graph.add_edge("swarm_a_liquidity", "swarm_a_aggregate")
        
        # Swarm B internal flow
        graph.add_edge("swarm_b_macro", "swarm_b_volatility")
        graph.add_edge("swarm_b_volatility", "swarm_b_correlation")
        graph.add_edge("swarm_b_correlation", "swarm_b_drawdown")
        graph.add_edge("swarm_b_drawdown", "swarm_b_aggregate")
        
        # Both aggregators → debate
        graph.add_edge("swarm_a_aggregate", "debate")
        graph.add_edge("swarm_b_aggregate", "debate")
        
        # Debate → arbitrator
        graph.add_edge("debate", "arbitrator")
        
        # Arbitrator → conditional
        graph.add_conditional_edges(
            "arbitrator",
            self._route_after_arbitration,
            {
                "execute": "human_review" if self.human_in_the_loop else "execution",
                "reject": END,
            },
        )
        
        # Human review → execution
        graph.add_conditional_edges(
            "human_review",
            self._route_after_human,
            {"execute": "execution", "reject": END},
        )
        
        # Execution → reflection → evolution → end
        graph.add_edge("execution", "reflection")
        graph.add_edge("reflection", "evolution")
        graph.add_edge("evolution", END)
        
        # ... compile ...
```

### 8.3 Parallel Execution

Swarm A and Swarm B can run in parallel using LangGraph's fan-out pattern. The `debate` node waits for both to complete (LangGraph handles this automatically when a node has multiple incoming edges — it waits for all predecessors).

```python
# Both swarms receive the same news output and run concurrently
graph.add_edge("news", "swarm_a_momentum")  # fan-out branch 1
graph.add_edge("news", "swarm_b_macro")     # fan-out branch 2

# Both aggregate nodes feed into debate (fan-in)
graph.add_edge("swarm_a_aggregate", "debate")
graph.add_edge("swarm_b_aggregate", "debate")
```

---

## 9. Implementation Plan

### Phase 1: Foundation (Week 1)

**Goal:** Create the data models and base agent classes for swarm agents.

| Step | File | Action |
|------|------|--------|
| 1.1 | `src/alphastack/agents/swarm/models.py` | Create all new Pydantic models (SwarmSignal, SwarmProposal, RiskAssessment, SwarmAssessment, DebateMessage, DebateTranscript, ArbitrationResult, MergedConstraints, TradeOutcome, EvolutionUpdate) |
| 1.2 | `src/alphastack/agents/swarm/base.py` | Create `SwarmAgent` base class extending `AlphaStackAgent` with swarm-specific methods (produce_signal, get_weight) |
| 1.3 | `src/alphastack/agents/orchestrator/state.py` | Extend `AlphaStackState` with new swarm fields |

### Phase 2: Swarm A Agents (Week 1-2)

**Goal:** Implement all four Swarm A agents.

| Step | File | Action |
|------|------|--------|
| 2.1 | `src/alphastack/agents/swarm/a/__init__.py` | Package init |
| 2.2 | `src/alphastack/agents/swarm/a/momentum.py` | `MomentumScoutAgent` — ROC, ADX, DMI analysis |
| 2.3 | `src/alphastack/agents/swarm/a/pattern.py` | `PatternHunterAgent` — candlestick and chart pattern detection |
| 2.4 | `src/alphastack/agents/swarm/a/sentiment.py` | `SentimentReaderAgent` — NLP sentiment, on-chain, social |
| 2.5 | `src/alphastack/agents/swarm/a/liquidity.py` | `LiquidityMapperAgent` — order book, block trades, COT |
| 2.6 | `src/alphastack/agents/swarm/a/aggregator.py` | `SwarmAAggregator` — weighted composite signal |

### Phase 3: Swarm B Agents (Week 2)

**Goal:** Implement all four Swarm B agents.

| Step | File | Action |
|------|------|--------|
| 3.1 | `src/alphastack/agents/swarm/b/__init__.py` | Package init |
| 3.2 | `src/alphastack/agents/swarm/b/macro.py` | `MacroAnalystAgent` — BTC dominance, DXY, rates |
| 3.3 | `src/alphastack/agents/swarm/b/volatility.py` | `VolatilityGuardAgent` — ATR, vol regime, position sizing |
| 3.4 | `src/alphastack/agents/swarm/b/correlation.py` | `CorrelationCheckerAgent` — portfolio correlation, sector exposure |
| 3.5 | `src/alphastack/agents/swarm/b/drawdown.py` | `DrawdownMonitorAgent` — DD tracking, circuit breakers |
| 3.6 | `src/alphastack/agents/swarm/b/aggregator.py` | `SwarmBAggregator` — weighted risk composite |

### Phase 4: Debate & Arbitration (Week 2-3)

**Goal:** Implement the debate protocol and arbitrator.

| Step | File | Action |
|------|------|--------|
| 4.1 | `src/alphastack/agents/swarm/debate.py` | `DebateEngine` — orchestrates multi-round debate protocol |
| 4.2 | `src/alphastack/agents/swarm/arbitrator.py` | `Arbitrator` — confidence-weighted voting + MiMo CoT tie-breaking |
| 4.3 | `src/alphastack/agi/reasoning.py` | Extend `ChainOfThoughtEngine` with debate-specific reasoning methods |

### Phase 5: Evolution Engine (Week 3)

**Goal:** Implement the self-improvement loop.

| Step | File | Action |
|------|------|--------|
| 5.1 | `src/alphastack/agents/swarm/evolution.py` | `EvolutionEngine` — weight updates, threshold updates, calibration |
| 5.2 | `src/alphastack/agi/memory.py` | Extend `EpisodicMemory` with evolution record storage and queries |
| 5.3 | `src/alphastack/agents/swarm/tracker.py` | `AgentTrackRecord` — rolling accuracy and calibration tracking |

### Phase 6: Graph Integration (Week 3-4)

**Goal:** Wire everything into the LangGraph orchestrator.

| Step | File | Action |
|------|------|--------|
| 6.1 | `src/alphastack/agents/orchestrator/graph.py` | Add swarm nodes, debate node, arbitrator node, evolution node. Replace strategy/risk nodes with swarm parallel fan-out/fan-in. |
| 6.2 | `src/alphastack/agents/orchestrator/graph.py` | Add `_route_after_arbitration` conditional edge |
| 6.3 | `src/alphastack/agents/orchestrator/graph.py` | Update `run()` and `stream()` for new graph structure |

### Phase 7: Backward Compatibility (Week 4)

**Goal:** Ensure old pipeline still works as fallback.

| Step | File | Action |
|------|------|--------|
| 7.1 | `src/alphastack/agents/orchestrator/graph.py` | Add `swarm_mode` flag — `True` uses new dual-swarm, `False` uses legacy linear pipeline |
| 7.2 | `src/alphastack/agents/orchestrator/graph.py` | Both modes share the same `run()` API |

### Phase 8: Testing & Tuning (Week 4+)

| Step | Action |
|------|--------|
| 8.1 | Unit tests for each swarm agent |
| 8.2 | Integration tests for debate protocol |
| 8.3 | Backtest: run swarm on historical data, compare vs linear pipeline |
| 8.4 | Tune default weights using backtest results |
| 8.5 | Paper trading validation |

---

## 10. File Manifest

### New Files

```
src/alphastack/agents/swarm/
├── __init__.py
├── models.py              # All Pydantic models (SwarmSignal, DebateMessage, etc.)
├── base.py                # SwarmAgent base class
├── debate.py              # DebateEngine
├── arbitrator.py          # Arbitrator (confidence-weighted voting + MiMo CoT)
├── evolution.py           # EvolutionEngine
├── tracker.py             # AgentTrackRecord tracking
├── a/                     # Swarm A (OpenClaw)
│   ├── __init__.py
│   ├── momentum.py        # MomentumScoutAgent
│   ├── pattern.py         # PatternHunterAgent
│   ├── sentiment.py       # SentimentReaderAgent
│   ├── liquidity.py       # LiquidityMapperAgent
│   └── aggregator.py      # SwarmAAggregator
└── b/                     # Swarm B (Hermes)
    ├── __init__.py
    ├── macro.py           # MacroAnalystAgent
    ├── volatility.py      # VolatilityGuardAgent
    ├── correlation.py     # CorrelationCheckerAgent
    ├── drawdown.py        # DrawdownMonitorAgent
    └── aggregator.py      # SwarmBAggregator
```

### Modified Files

```
src/alphastack/agents/orchestrator/
├── graph.py               # Add swarm nodes, debate, arbitrator, evolution nodes
└── state.py               # Extend AlphaStackState with swarm fields

src/alphastack/agi/
├── reasoning.py           # Extend ChainOfThoughtEngine with debate reasoning
└── memory.py              # Extend EpisodicMemory with evolution records
```

### Documentation

```
docs/
├── SWARM_ARCHITECTURE.md  # Existing (high-level overview)
└── SWARM_DESIGN.md        # This file (detailed design)
```

---

## Appendix A: Configuration Defaults

```python
# Swarm A default weights (evolvable)
SWARM_A_DEFAULT_WEIGHTS = {
    "momentum_scout": 0.30,
    "pattern_hunter": 0.25,
    "sentiment_reader": 0.20,
    "liquidity_mapper": 0.25,
}

# Swarm B default weights (evolvable)
SWARM_B_DEFAULT_WEIGHTS = {
    "macro_analyst": 0.30,
    "volatility_guard": 0.25,
    "correlation_checker": 0.20,
    "drawdown_monitor": 0.25,
}

# Arbitrator thresholds
ARBITRATION_THRESHOLDS = {
    "consensus_fast_path": True,      # skip debate if both agree
    "hard_veto_risk_score": 0.90,     # Swarm B can hard-veto above this
    "confidence_floor": 0.40,         # minimum confidence to trade
    "debate_max_rounds": 3,
    "debate_timeout_seconds": 30,
    "ambiguous_vote_range": (-0.3, 0.3),  # trigger CoT reasoning
}

# Evolution parameters
EVOLUTION_PARAMS = {
    "learning_rate_swarm_a": 0.05,
    "learning_rate_swarm_b": 0.03,
    "min_agent_weight": 0.10,
    "max_agent_weight": 0.45,
    "lookback_window": 20,
    "calibration_check_interval": 20,  # trades
    "weight_normalization_interval": "weekly",
}
```

---

## Appendix B: Decision Flow Summary

```
Market Data In
     │
     ▼
 News Agent (detect events)
     │
     ├──► Swarm A: 4 agents run → composite signal + confidence
     │
     ├──► Swarm B: 4 agents run → composite risk + constraints
     │
     ▼
 Both Aggregators produce proposals
     │
     ▼
 DEBATE ENGINE
     │
     ├── Both agree? ──► Fast path ──► Execute
     │
     ├── Swarm B hard veto (risk > 0.90)? ──► Reject
     │
     └── Disagreement? ──► Multi-round debate
                              │
                              ▼
                        ARBITRATOR
                              │
                              ├─ Confidence-weighted vote
                              │
                              ├─ If ambiguous ──► MiMo CoT reasoning
                              │
                              ├─ Consult episodic memory (similar past cases)
                              │
                              └─ Merge constraints (conservative wins)
                                    │
                                    ▼
                              Final Decision
                                    │
                              ┌─────┴─────┐
                              ▼           ▼
                          Execute      Reject
                              │
                              ▼
                          Reflection
                              │
                              ▼
                          EVOLUTION ENGINE
                              │
                              ├─ Update Swarm A weights
                              ├─ Update Swarm B thresholds
                              └─ Store in Episodic Memory
                                    │
                                    ▼
                              Better decisions next time 🔄
```
