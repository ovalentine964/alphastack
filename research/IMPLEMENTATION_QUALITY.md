# AlphaStack Implementation Quality Plan

> **Version:** 1.0 · **Date:** 2026-07-19 · **Author:** Quality & Testing Agent
> **Current State:** 0 tests, no CI/CD, no monitoring stack, architecture score 3.0/10
> **Target State:** Production-grade quality for a multi-agent trading system handling real capital
> **Research Basis:** Multi-agent systems, self-improving loops, emerging architectures, OWASP agentic AI security

---

## Table of Contents

1. [Testing Strategy](#1-testing-strategy)
2. [Agent Testing](#2-agent-testing)
3. [Trading System Testing](#3-trading-system-testing)
4. [Monitoring & Observability](#4-monitoring--observability)
5. [CI/CD Pipeline](#5-cicd-pipeline)
6. [Quality Gates](#6-quality-gates)
7. [Performance Benchmarks](#7-performance-benchmarks)

---

## 1. Testing Strategy

### 1.1 The Problem

AlphaStack has **zero tests** and a **3.0/10 architecture score**. Research shows:

- **54% of enterprises** have had confirmed agent security incidents (VentureBeat, Jul 2026)
- **Half of enterprises** shipped an agent that passed internal evals but failed in production
- **Intuit abandoned natural-language agent handoffs** because a 10-agent chain compounds errors by design — not occasionally, but by design
- OWASP identifies **memory poisoning, cascading failures, and goal hijacking** as top agentic AI risks

For a multi-agent trading system, bugs don't just crash software — they lose money. The testing strategy must be adversarial, exhaustive, and deterministic.

### 1.2 Test Pyramid

```
                    ┌───────────┐
                    │  E2E/Smoke │  ← Full trade lifecycle (5%)
                   ┌┴───────────┴┐
                   │ Integration  │ ← Agent chains, broker flows (15%)
                  ┌┴─────────────┴┐
                  │  Unit Tests    │ ← Individual functions (80%)
                 └────────────────┘

  CROSS-CUTTING: Agent evals · Backtesting · Security · Performance
```

**Coverage targets:** 90% line / 80% branch for unit tests. 100% coverage on Risk Governor — a bug there means lost money.

### 1.3 Test Directory Structure

```
tests/
├── conftest.py                          # Shared fixtures
├── unit/
│   ├── agents/
│   │   ├── test_news_agent.py
│   │   ├── test_strategy_agent.py
│   │   ├── test_risk_agent.py
│   │   ├── test_execution_agent.py
│   │   └── test_reflection_agent.py
│   ├── pipeline/
│   │   ├── test_orchestrator.py
│   │   ├── test_event_bus.py
│   │   └── test_state_machine.py
│   ├── risk/
│   │   ├── test_risk_governor.py         # 100% coverage — mandatory
│   │   ├── test_circuit_breakers.py
│   │   └── test_position_sizing.py
│   └── data/
│       ├── test_market_data.py
│       ├── test_gap_detector.py
│       └── test_sentiment.py
├── integration/
│   ├── test_agent_chain.py              # News → Strategy → Risk → Execution
│   ├── test_redis_streams.py
│   ├── test_broker_connector.py
│   └── test_database.py
├── agent_evals/
│   ├── test_news_eval.py
│   ├── test_strategy_eval.py
│   ├── test_risk_eval.py
│   └── eval_datasets/
│       ├── news_scenarios.json
│       ├── strategy_scenarios.json
│       └── risk_scenarios.json
├── backtest/
│   ├── test_module_equivalence.py
│   ├── test_fill_simulation.py
│   ├── test_walk_forward.py
│   └── fixtures/
│       ├── eurusd_2024_2025.parquet
│       └── trade_sequences/
├── performance/
│   ├── test_latency.py
│   ├── test_throughput.py
│   └── test_memory.py
└── security/
    ├── test_credential_isolation.py
    ├── test_agent_permissions.py
    └── test_memory_integrity.py
```

### 1.4 Unit Test Example: Risk Governor

The Risk Governor is the single most critical component. Every limit, every edge case, every boundary must be tested exhaustively.

```python
# tests/unit/risk/test_risk_governor.py
import pytest
from alpha.risk.governor import RiskGovernor
from alpha.risk.models import TradeProposal, AccountState

class TestRiskGovernor:
    """
    Risk Governor tests. These are CRITICAL — a bug here means lost money.
    Every limit, every edge case, every boundary must be tested.
    """

    @pytest.fixture
    def governor(self):
        return RiskGovernor()

    # ─── Per-Trade Risk Limit (2%) ────────────────────────────

    def test_rejects_trade_exceeding_2pct_risk(self, governor):
        account = AccountState(balance=1000, open_positions=[])
        proposal = TradeProposal(risk_amount=25)  # 2.5%
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Per-trade risk exceeded" in result.reason

    def test_accepts_trade_at_exactly_2pct_risk(self, governor):
        account = AccountState(balance=1000, open_positions=[])
        proposal = TradeProposal(risk_amount=20)  # exactly 2%
        result = governor.check(proposal, account)
        assert result.approved is True

    def test_risk_uses_balance_not_equity(self, governor):
        """Risk calculated against balance, not equity (prevents runaway on winning streaks)."""
        account = AccountState(balance=1000, equity=1500, open_positions=[])
        proposal = TradeProposal(risk_amount=25)  # 2.5% of balance
        result = governor.check(proposal, account)
        assert result.approved is False  # Rejected against balance

    # ─── Total Exposure Limit (6%) ────────────────────────────

    def test_rejects_when_total_exposure_exceeds_6pct(self, governor):
        positions = [TradeProposal(risk_amount=20) for _ in range(3)]  # 6% total
        account = AccountState(balance=1000, open_positions=positions)
        proposal = TradeProposal(risk_amount=5)  # Would push to 6.5%
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Total exposure exceeded" in result.reason

    # ─── Correlated Exposure Limit (3%) ───────────────────────

    def test_rejects_correlated_exposure_above_3pct(self, governor):
        """EUR/USD and GBP/USD are correlated (>0.7). Combined risk capped at 3%."""
        positions = [TradeProposal(symbol="EURUSD", risk_amount=20)]
        account = AccountState(balance=1000, open_positions=positions)
        proposal = TradeProposal(symbol="GBPUSD", risk_amount=15)  # Combined 3.5%
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Correlated exposure exceeded" in result.reason

    # ─── Daily Loss Circuit Breaker (4%) ──────────────────────

    def test_halts_trading_after_4pct_daily_loss(self, governor):
        account = AccountState(balance=1000, daily_pnl=-40)  # -4%
        proposal = TradeProposal(risk_amount=5)
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Daily loss circuit breaker" in result.reason

    def test_allows_trading_at_3_99pct_daily_loss(self, governor):
        account = AccountState(balance=1000, daily_pnl=-39.9)
        proposal = TradeProposal(risk_amount=5)
        result = governor.check(proposal, account)
        assert result.approved is True

    # ─── Max Concurrent Positions (5) ─────────────────────────

    def test_rejects_6th_position(self, governor):
        positions = [TradeProposal() for _ in range(5)]
        account = AccountState(balance=10000, open_positions=positions)
        proposal = TradeProposal(risk_amount=10)
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Max concurrent positions" in result.reason

    # ─── Margin Utilization (30%) ─────────────────────────────

    def test_rejects_when_margin_above_30pct(self, governor):
        account = AccountState(balance=1000, margin_utilization=0.31)
        proposal = TradeProposal(risk_amount=5)
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Margin utilization" in result.reason

    # ─── Edge Cases ───────────────────────────────────────────

    def test_zero_balance_rejects_all(self, governor):
        account = AccountState(balance=0, open_positions=[])
        proposal = TradeProposal(risk_amount=1)
        result = governor.check(proposal, account)
        assert result.approved is False

    def test_negative_pnl_does_not_inflate_risk_budget(self, governor):
        """Negative P&L should NOT increase available risk budget."""
        account = AccountState(balance=1000, daily_pnl=-100, open_positions=[])
        proposal = TradeProposal(risk_amount=20)  # 2% of balance
        result = governor.check(proposal, account)
        # Should still be checked against balance, not equity
        assert result.approved is True  # 2% of 1000 is fine

    def test_returns_adjusted_lot_size_when_slightly_over(self, governor):
        account = AccountState(balance=1000, open_positions=[])
        proposal = TradeProposal(risk_amount=25)  # 2.5%
        result = governor.check(proposal, account)
        assert result.approved is False
        assert result.adjusted_lot_size is not None
        assert result.adjusted_lot_size < proposal.lot_size
```

### 1.5 Unit Test Example: Agent Chain

```python
# tests/unit/pipeline/test_orchestrator.py
import pytest
from alpha.pipeline.orchestrator import PipelineOrchestrator
from alpha.pipeline.events import MarketEvent

class TestPipelineOrchestrator:

    @pytest.fixture
    def orchestrator(self, mock_agents, mock_event_bus):
        return PipelineOrchestrator(
            news_agent=mock_agents['news'],
            strategy_agent=mock_agents['strategy'],
            risk_agent=mock_agents['risk'],
            execution_agent=mock_agents['execution'],
            event_bus=mock_event_bus,
        )

    async def test_full_pipeline_produces_proposal(self, orchestrator):
        """Strong signals through all agents produce a trade proposal."""
        event = MarketEvent(pair="EURUSD", timeframe="H1", candle=VALID_CANDLE)
        result = await orchestrator.process(event)
        assert result.proposal is not None
        assert result.proposal.confluence_score >= 0.65

    async def test_pipeline_halts_on_avoid_all(self, orchestrator):
        """AVOID_ALL from news agent halts pipeline immediately."""
        orchestrator.news_agent.force_response = NewsResult(
            sentiment=-0.9, action="AVOID_ALL", reason="NFP imminent"
        )
        event = MarketEvent(pair="EURUSD", timeframe="H1", candle=VALID_CANDLE)
        result = await orchestrator.process(event)
        assert result.proposal is None
        assert result.halt_reason == "NEWS_AVOID_ALL"
        assert orchestrator.strategy_agent.call_count == 0  # Never called

    async def test_pipeline_degrades_on_agent_timeout(self, orchestrator):
        """Agent timeout should degrade gracefully, not crash."""
        orchestrator.strategy_agent.simulate_timeout = True
        event = MarketEvent(pair="EURUSD", timeframe="H1", candle=VALID_CANDLE)
        result = await orchestrator.process(event)
        assert result.proposal is None
        assert "timeout" in result.error.lower()
        assert result.partial_results is not None  # News agent result preserved

    async def test_pipeline_propagates_context_between_agents(self, orchestrator):
        """Each agent receives the accumulated context from prior agents."""
        event = MarketEvent(pair="EURUSD", timeframe="H1", candle=VALID_CANDLE)
        await orchestrator.process(event)

        # Strategy agent should have received news agent's output
        strategy_input = orchestrator.strategy_agent.last_input
        assert strategy_input.news_sentiment is not None
        assert strategy_input.bias is not None

        # Risk agent should have received strategy agent's output
        risk_input = orchestrator.risk_agent.last_input
        assert risk_input.direction is not None
        assert risk_input.confluence_score is not None

    async def test_pipeline_respects_per_agent_timeout(self, orchestrator):
        """Each agent has a configurable timeout. LangGraph per-node timeouts."""
        orchestrator.config = {
            'timeouts': {
                'news': 5.0,      # Data fetching can be slow
                'strategy': 10.0,  # Complex reasoning
                'risk': 2.0,       # Fast, deterministic
                'execution': 3.0,  # Time-critical
            }
        }
        # Verify timeout configuration is applied
        assert orchestrator.get_timeout('news') == 5.0
        assert orchestrator.get_timeout('risk') == 2.0
```

---

## 2. Agent Testing

### 2.1 Why Agent Testing Is Different

Traditional software testing assumes deterministic outputs. LLM-based agents are stochastic. Research from LangChain (Jul 2026) frames agent improvement as a **data mining problem** — traces are the currency of improvement. Intuit's lesson: natural-language agent handoffs compound errors by design.

**Three testing dimensions for agents:**

| Dimension | What It Tests | Method |
|-----------|--------------|--------|
| **Correctness** | Does the agent produce the right output? | Eval datasets with expected outputs |
| **Robustness** | Does the agent handle adversarial/malformed inputs? | Property-based testing, fuzzing |
| **Consistency** | Does the agent produce similar outputs for similar inputs? | Trace mining, regression detection |

### 2.2 Agent Evaluation Framework

```python
# tests/agent_evals/eval_runner.py
"""
Agent evaluation framework based on trace mining.
Research basis: "Improving Agents is a Data Mining Problem" (LangChain, Jul 2026)
"""
import json
import hashlib
from dataclasses import dataclass
from typing import Optional
from alpha.agents.base import BaseAgent

@dataclass
class EvalCase:
    id: str
    input_data: dict
    expected_output: dict
    tags: list[str]           # e.g., ["bullish", "london_session", "high_volatility"]
    difficulty: str            # "easy", "medium", "hard"
    source: str               # "manual", "trace_mining", "regression"

@dataclass
class EvalResult:
    case_id: str
    passed: bool
    actual_output: dict
    score: float              # 0.0 - 1.0 similarity
    latency_ms: float
    token_count: int
    trace_id: str             # For trace mining pipeline

class AgentEvalRunner:
    """
    Run eval suites against agents, capture traces for mining.
    """

    def __init__(self, agent: BaseAgent, eval_dataset: list[EvalCase]):
        self.agent = agent
        self.dataset = eval_dataset
        self.results: list[EvalResult] = []

    async def run_suite(self, threshold: float = 0.8) -> dict:
        """Run full eval suite, return pass/fail summary."""
        passed, failed = 0, 0

        for case in self.dataset:
            result = await self._run_case(case)
            self.results.append(result)

            if result.score >= threshold:
                passed += 1
            else:
                failed += 1

        return {
            "total": len(self.dataset),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(self.dataset),
            "avg_latency_ms": sum(r.latency_ms for r in self.results) / len(self.results),
            "avg_tokens": sum(r.token_count for r in self.results) / len(self.results),
        }

    async def _run_case(self, case: EvalCase) -> EvalResult:
        """Run a single eval case, capture full trace."""
        import time

        start = time.perf_counter_ns()
        trace = await self.agent.run_with_trace(case.input_data)
        latency_ms = (time.perf_counter_ns() - start) / 1_000_000

        # Compute similarity score
        score = self._compute_similarity(trace.output, case.expected_output)

        # Generate trace ID for mining pipeline
        trace_id = hashlib.sha256(
            json.dumps(trace.to_dict(), sort_keys=True).encode()
        ).hexdigest()[:16]

        return EvalResult(
            case_id=case.id,
            passed=score >= 0.8,
            actual_output=trace.output,
            score=score,
            latency_ms=latency_ms,
            token_count=trace.total_tokens,
            trace_id=trace_id,
        )

    def _compute_similarity(self, actual: dict, expected: dict) -> float:
        """
        Compute output similarity. Different strategies per field:
        - Numeric fields: tolerance-based (e.g., confluence_score ±0.05)
        - Categorical fields: exact match (e.g., direction = "BULLISH")
        - Text fields: embedding similarity (e.g., reasoning)
        """
        score = 0.0
        total = 0

        for key, expected_val in expected.items():
            actual_val = actual.get(key)
            if actual_val is None:
                continue

            total += 1
            if isinstance(expected_val, (int, float)):
                # Numeric: within 5% tolerance
                if abs(actual_val - expected_val) / max(abs(expected_val), 1e-9) < 0.05:
                    score += 1
            elif isinstance(expected_val, str):
                # Categorical: exact match
                if actual_val == expected_val:
                    score += 1
            elif isinstance(expected_val, bool):
                if actual_val == expected_val:
                    score += 1

        return score / total if total > 0 else 0.0

    def get_regression_candidates(self) -> list[EvalCase]:
        """Extract cases from failed runs for regression dataset."""
        return [
            EvalCase(
                id=f"regression_{r.case_id}",
                input_data=self._get_case(r.case_id).input_data,
                expected_output=r.actual_output,  # Use actual as new expected
                tags=["regression"],
                difficulty="medium",
                source="regression",
            )
            for r in self.results
            if not r.passed
        ]
```

### 2.3 Agent Eval Datasets

```json
// tests/agent_evals/eval_datasets/news_scenarios.json
[
  {
    "id": "news_001",
    "input_data": {
      "headline": "Fed signals 50bp rate cut in September, markets rally",
      "source": "reuters",
      "timestamp": "2026-07-19T13:30:00Z",
      "pair": "EURUSD"
    },
    "expected_output": {
      "sentiment": "BULLISH",
      "impact_score": 0.85,
      "action": "TRADE",
      "bias": "BULLISH",
      "confidence": 0.80
    },
    "tags": ["fed", "rate_decision", "high_impact", "bullish"],
    "difficulty": "easy",
    "source": "manual"
  },
  {
    "id": "news_002",
    "input_data": {
      "headline": "NFP due in 30 minutes, open EURUSD long position",
      "source": "forex_factory",
      "timestamp": "2026-07-19T12:30:00Z",
      "pair": "EURUSD",
      "open_positions": [{"symbol": "EURUSD", "direction": "BULLISH", "pnl": 15}]
    },
    "expected_output": {
      "sentiment": "NEUTRAL",
      "impact_score": 0.95,
      "action": "AVOID_ALL",
      "reason": "High-impact news event imminent with open position",
      "pre_news_action": "TIGHTEN_STOPS"
    },
    "tags": ["nfp", "pre_news", "position_management", "risk"],
    "difficulty": "medium",
    "source": "trace_mining"
  },
  {
    "id": "news_003",
    "input_data": {
      "headline": "ECB Lagarde: Inflation remains sticky, no rate cut discussed",
      "source": "ecb",
      "timestamp": "2026-07-19T08:00:00Z",
      "pair": "EURUSD"
    },
    "expected_output": {
      "sentiment": "HAWKISH",
      "impact_score": 0.70,
      "action": "TRADE",
      "bias": "BULLISH",
      "confidence": 0.65
    },
    "tags": ["ecb", "hawkish", "medium_impact"],
    "difficulty": "medium",
    "source": "manual"
  }
]
```

```json
// tests/agent_evals/eval_datasets/risk_scenarios.json
[
  {
    "id": "risk_001",
    "input_data": {
      "proposal": {"pair": "EURUSD", "direction": "BULLISH", "lot_size": 0.10, "risk_amount": 25},
      "account": {"balance": 1000, "equity": 1000, "open_positions": [], "daily_pnl": 0}
    },
    "expected_output": {
      "approved": false,
      "reason_contains": "Per-trade risk exceeded",
      "adjusted_lot_size": true
    },
    "tags": ["per_trade_limit", "rejection"],
    "difficulty": "easy",
    "source": "manual"
  },
  {
    "id": "risk_002",
    "input_data": {
      "proposal": {"pair": "EURUSD", "direction": "BULLISH", "lot_size": 0.05, "risk_amount": 15},
      "account": {
        "balance": 1000, "equity": 1000,
        "open_positions": [
          {"symbol": "GBPUSD", "direction": "BULLISH", "risk_amount": 20}
        ],
        "daily_pnl": 0
      }
    },
    "expected_output": {
      "approved": false,
      "reason_contains": "Correlated exposure exceeded"
    },
    "tags": ["correlation", "eurusd_gbpusd", "rejection"],
    "difficulty": "medium",
    "source": "manual"
  }
]
```

### 2.4 Trace Mining Pipeline

Research insight: *"Traces are the currency of long-horizon agent improvement."* (LangChain, Jul 2026)

```python
# alpha/quality/trace_miner.py
"""
Trace mining pipeline for agent improvement.
Captures decision traces, mines patterns from winning vs losing trades.
"""
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from alpha.storage.redis import RedisClient
from alpha.storage.postgres import PostgresClient

@dataclass
class AgentTrace:
    trace_id: str
    agent_name: str
    timestamp: datetime
    input_data: dict
    output_data: dict
    reasoning_chain: list[dict]    # Step-by-step reasoning
    tool_calls: list[dict]         # Tools invoked
    token_count: int
    latency_ms: float
    trade_outcome: str | None      # "win", "loss", "breakeven", None
    r_multiple: float | None       # Trade R-multiple

class TraceMiner:
    """
    Capture and mine agent decision traces for improvement.
    """

    def __init__(self, redis: RedisClient, postgres: PostgresClient):
        self.redis = redis
        self.postgres = postgres

    async def capture_trace(self, trace: AgentTrace):
        """Store trace in both Redis (hot) and Postgres (cold)."""
        # Hot store: recent traces for real-time analysis
        await self.redis.xadd(
            f"traces:{trace.agent_name}",
            {"trace": json.dumps(asdict(trace), default=str)},
            maxlen=10000,
        )
        # Cold store: all traces for historical mining
        await self.postgres.insert("agent_traces", asdict(trace))

    async def mine_patterns(self, agent_name: str, min_traces: int = 100) -> dict:
        """
        Mine patterns from traces to identify improvement opportunities.
        Returns: patterns found, suggested eval cases, parameter adjustments.
        """
        traces = await self.postgres.query(
            "SELECT * FROM agent_traces WHERE agent_name = %s ORDER BY timestamp DESC LIMIT %s",
            (agent_name, min_traces)
        )

        winning_traces = [t for t in traces if t.get('r_multiple') and t['r_multiple'] > 0]
        losing_traces = [t for t in traces if t.get('r_multiple') and t['r_multiple'] < 0]

        patterns = {
            "winning_patterns": self._extract_patterns(winning_traces),
            "losing_patterns": self._extract_patterns(losing_traces),
            "common_failures": self._identify_failures(traces),
            "suggested_evals": self._generate_eval_cases(losing_traces),
        }

        return patterns

    def _extract_patterns(self, traces: list[dict]) -> list[dict]:
        """Extract common patterns from a set of traces."""
        # Group by reasoning chain similarity
        # Identify recurring tool call sequences
        # Find common input characteristics
        patterns = []
        # ... pattern extraction logic
        return patterns

    def _identify_failures(self, traces: list[dict]) -> list[dict]:
        """Identify recurring failure modes."""
        failures = []
        for trace in traces:
            if trace.get('trade_outcome') == 'loss':
                failures.append({
                    "trace_id": trace['trace_id'],
                    "failure_type": self._classify_failure(trace),
                    "reasoning_at_failure": self._extract_failure_reasoning(trace),
                })
        return failures

    def _generate_eval_cases(self, losing_traces: list[dict]) -> list[dict]:
        """Generate eval cases from losing traces for regression testing."""
        eval_cases = []
        for trace in losing_traces[:50]:  # Top 50 losing traces
            eval_cases.append({
                "id": f"mined_{trace['trace_id']}",
                "input_data": trace['input_data'],
                "expected_output": self._derive_expected(trace),
                "tags": ["trace_mined", "regression"],
                "source": "trace_mining",
            })
        return eval_cases
```

### 2.5 Agent Regression Testing

```python
# tests/agent_evals/test_regression.py
"""
Regression tests for agents. Run after any agent config change.
Cases sourced from trace mining pipeline.
"""
import pytest
from tests.agent_evals.eval_runner import AgentEvalRunner, EvalCase
from tests.agent_evals.fixtures import load_regression_dataset

class TestAgentRegression:

    @pytest.fixture
    def regression_cases(self):
        """Load regression cases from trace mining pipeline."""
        return load_regression_dataset()

    async def test_news_agent_no_regression(self, news_agent, regression_cases):
        """News agent must not regress on previously-correct cases."""
        cases = [c for c in regression_cases if "news" in c.tags]
        runner = AgentEvalRunner(news_agent, cases)
        results = await runner.run_suite(threshold=0.9)

        assert results['pass_rate'] >= 0.95, \
            f"News agent regression: {results['failed']} cases failed"

    async def test_strategy_agent_no_regression(self, strategy_agent, regression_cases):
        """Strategy agent must not regress on previously-correct cases."""
        cases = [c for c in regression_cases if "strategy" in c.tags]
        runner = AgentEvalRunner(strategy_agent, cases)
        results = await runner.run_suite(threshold=0.85)

        assert results['pass_rate'] >= 0.95

    async def test_risk_agent_no_regression(self, risk_agent, regression_cases):
        """Risk agent must never regress — this is the safety net."""
        cases = [c for c in regression_cases if "risk" in c.tags]
        runner = AgentEvalRunner(risk_agent, cases)
        results = await runner.run_suite(threshold=0.95)

        assert results['pass_rate'] >= 1.0, \
            f"Risk agent regression: ZERO tolerance for failures"
```

---

## 3. Trading System Testing

### 3.1 Backtesting Framework

**Core principle:** The backtesting engine reuses identical code paths as live trading. If you can't test it with historical data, you can't trust it with real money.

```python
# alpha/backtest/engine.py
"""
Backtesting engine. Same pipeline code, different data source.
"""
from alpha.pipeline.orchestrator import PipelineOrchestrator
from alpha.backtest.replay_bus import ReplayEventBus
from alpha.backtest.fill_simulator import FillSimulator

class BacktestEngine:
    """
    Runs AlphaStack pipeline against historical data.
    Uses identical code paths as live trading.
    """

    def __init__(self, config: dict):
        self.orchestrator = PipelineOrchestrator(
            mode='backtest',
            event_bus=ReplayEventBus(),
            broker=FillSimulator(
                slippage_model=config.get('slippage_model', 'proportional'),
                spread_model=config.get('spread_model', 'session_based'),
            ),
        )
        self.results = BacktestResults()

    async def run(self, data: pd.DataFrame, start_date: str = None, end_date: str = None) -> 'BacktestResults':
        """Run backtest on historical data."""
        filtered = data
        if start_date:
            filtered = filtered[filtered['time'] >= start_date]
        if end_date:
            filtered = filtered[filtered['time'] <= end_date]

        for _, row in filtered.iterrows():
            event = self._row_to_event(row)
            result = await self.orchestrator.process(event)
            self.results.record(result)

        return self.results

class FillSimulator:
    """
    Simulates broker fills with realistic slippage and spread.
    """

    def __init__(self, slippage_model: str = 'proportional', spread_model: str = 'session_based'):
        self.slippage_model = slippage_model
        self.spread_model = spread_model

    def get_spread(self, pair: str, session: str) -> float:
        """Session-aware spread model."""
        base_spreads = {
            "EURUSD": 0.00012,
            "GBPUSD": 0.00018,
            "USDJPY": 0.015,
        }
        session_multipliers = {
            "ASIAN": 1.5,
            "LONDON": 1.0,
            "NEW_YORK": 1.0,
            "LDN_NY_OVERLAP": 0.8,
            "OFF_HOURS": 2.0,
        }
        base = base_spreads.get(pair, 0.00020)
        multiplier = session_multipliers.get(session, 1.0)
        return base * multiplier

    def simulate_fill(self, order, market_event) -> 'FillResult':
        """Simulate order fill with slippage."""
        spread = self.get_spread(order.pair, market_event.session)
        slippage = self._calculate_slippage(order, market_event)

        if order.order_type == "MARKET":
            fill_price = market_event.ask + slippage if order.direction == "BULLISH" \
                else market_event.bid - slippage
            return FillResult(status="FILLED", price=fill_price, slippage=slippage)
        elif order.order_type == "LIMIT":
            if self._price_reached_limit(order, market_event):
                return FillResult(status="FILLED", price=order.entry_price, slippage=0)
            return FillResult(status="NOT_FILLED")
```

### 3.2 Backtesting Validation Tests

```python
# tests/backtest/test_module_equivalence.py
"""
Verify backtesting engine produces identical outputs as live engine.
"""
import pytest

class TestModuleEquivalence:

    async def test_step_outputs_match_live(self, sample_data):
        """Each pipeline step produces identical output in backtest vs live."""
        live = PipelineOrchestrator(mode='live')
        backtest = PipelineOrchestrator(mode='backtest')

        for i in range(len(sample_data)):
            event = build_event(sample_data.iloc[i])
            live_result = await live.process(event)
            backtest_result = await backtest.process(event)

            for step in live_result.step_results:
                assert live_result.step_results[step].direction == \
                       backtest_result.step_results[step].direction, \
                    f"Step {step} direction mismatch at bar {i}"
                assert abs(live_result.step_results[step].confidence -
                           backtest_result.step_results[step].confidence) < 1e-9

    async def test_fill_simulation_slippage_accuracy(self):
        """Simulated slippage matches historical slippage within ±0.5 pips."""
        actual_slippage = load_historical_slippage("fxpesa_eurusd_2025.csv")
        sim = FillSimulator()
        simulated = [sim.simulate_fill(build_order(), build_tick(s)).slippage
                     for s in actual_slippage]

        assert abs(np.mean(actual_slippage) - np.mean(simulated)) < 0.00005

    async def test_walk_forward_oos_not_overfit(self):
        """Out-of-sample Sharpe must be ≥50% of in-sample Sharpe."""
        optimizer = WalkForwardOptimizer(n_splits=5)
        result = await optimizer.optimize(DATA, DEFAULT_PARAMS)

        assert result.degradation_ratio >= 0.5, \
            f"OOS degradation too high: {result.degradation_ratio:.2f} — likely overfit"

    async def test_monte_carlo_ruin_probability(self):
        """Monte Carlo simulation: ruin probability <5%."""
        trades = load_backtest_trades()
        mc = MonteCarloSimulator(initial_balance=1000)
        result = mc.simulate(trades, n_simulations=10000)

        assert result.ruin_probability < 0.05
        assert result.percentile_5 > 0
        assert result.median_max_drawdown < 0.30
```

### 3.3 Paper Trading

Paper trading is the final integration test before real capital. It uses live market data with simulated execution.

```python
# alpha/trading/paper.py
"""
Paper trading mode: live data, simulated execution.
Purpose: Validate the full system under real market conditions without risk.
"""
from alpha.pipeline.orchestrator import PipelineOrchestrator
from alpha.backtest.fill_simulator import FillSimulator
from alpha.monitoring.metrics import MetricsCollector

class PaperTradingEngine:
    """
    Runs AlphaStack on live market data with simulated fills.
    Tracks performance metrics for comparison against backtest expectations.
    """

    def __init__(self, config: dict):
        self.orchestrator = PipelineOrchestrator(
            mode='paper',
            event_bus=LiveEventBus(config['data_feeds']),
            broker=FillSimulator(slippage_model='proportional'),
        )
        self.metrics = MetricsCollector(prefix='paper')
        self.trade_log = []

    async def start(self):
        """Start paper trading. Runs indefinitely until stopped."""
        await self.orchestrator.start()

        async for event in self.orchestrator.events():
            result = await self.orchestrator.process(event)

            if result.proposal:
                self.metrics.increment('paper.signals_generated')
                self.metrics.record_confluence(result.proposal.confluence_score)

            if result.fill:
                self.trade_log.append(result.fill)
                self.metrics.increment('paper.trades_executed')
                self.metrics.record_latency('paper.execution', result.fill.latency_ms)

    def get_performance_summary(self) -> dict:
        """Compare paper trading results against backtest expectations."""
        return {
            "total_trades": len(self.trade_log),
            "win_rate": self._calculate_win_rate(),
            "profit_factor": self._calculate_profit_factor(),
            "max_drawdown": self._calculate_max_drawdown(),
            "sharpe_ratio": self._calculate_sharpe(),
            "avg_slippage_pips": self._calculate_avg_slippage(),
            # Compare against backtest
            "backtest_win_rate_deviation": abs(self._calculate_win_rate() - self.expected_win_rate),
            "backtest_sharpe_deviation": abs(self._calculate_sharpe() - self.expected_sharpe),
        }
```

### 3.4 Shadow Mode

Shadow mode runs live and paper trading in parallel, comparing decisions in real-time.

```python
# alpha/trading/shadow.py
"""
Shadow mode: live and paper run in parallel.
Any divergence triggers an alert.
"""
class ShadowModeComparator:
    """
    Compare live vs paper decisions in real-time.
    Divergence = potential bug in either path.
    """

    def __init__(self):
        self.divergences = []

    async def compare(self, live_result, paper_result):
        """Compare live and paper results, alert on divergence."""
        if live_result.proposal and paper_result.proposal:
            # Both generated proposals — check alignment
            if live_result.proposal.direction != paper_result.proposal.direction:
                self.divergences.append({
                    "type": "DIRECTION_DIVERGENCE",
                    "live": live_result.proposal.direction,
                    "paper": paper_result.proposal.direction,
                    "timestamp": datetime.utcnow(),
                })
                await self.alert("DIRECTION_DIVERGENCE", self.divergences[-1])

            score_diff = abs(live_result.proposal.confluence_score -
                            paper_result.proposal.confluence_score)
            if score_diff > 0.1:
                self.divergences.append({
                    "type": "SCORE_DIVERGENCE",
                    "live_score": live_result.proposal.confluence_score,
                    "paper_score": paper_result.proposal.confluence_score,
                    "diff": score_diff,
                })

        elif bool(live_result.proposal) != bool(paper_result.proposal):
            # One generated a proposal, the other didn't
            self.divergences.append({
                "type": "ASYMMETRIC_SIGNAL",
                "live_has_proposal": live_result.proposal is not None,
                "paper_has_proposal": paper_result.proposal is not None,
            })
            await self.alert("ASYMMETRIC_SIGNAL", self.divergences[-1])

    async def alert(self, alert_type: str, details: dict):
        """Send alert on divergence."""
        # Alert via monitoring stack
        pass
```

---

## 4. Monitoring & Observability

### 4.1 Why Monitoring Matters

Research shows enterprises are **"buying infrastructure faster than they can measure what it costs"** (VentureBeat, Jul 2026). GPUs sit at 50% utilization. Fewer than half rigorously track actual compute costs. For a trading system, unmonitored costs and latencies directly impact profitability.

### 4.2 Prometheus Metrics Definitions

```yaml
# infra/monitoring/metrics_definitions.yml
# Prometheus metric definitions for AlphaStack

# ─── Trading Metrics ───────────────────────────────────────────
trading_signals_total:
  type: counter
  help: "Total trading signals generated"
  labels: [pair, direction, timeframe, agent]

trading_signals_confluence_score:
  type: histogram
  help: "Distribution of confluence scores"
  buckets: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0]
  labels: [pair]

trading_orders_total:
  type: counter
  help: "Total orders placed"
  labels: [pair, direction, broker, status]

trading_orders_filled_total:
  type: counter
  help: "Total orders filled"
  labels: [pair, direction, broker]

trading_orders_rejected_total:
  type: counter
  help: "Total orders rejected by risk governor"
  labels: [pair, reason]

trading_pnl_daily:
  type: gauge
  help: "Daily P&L in account currency"
  labels: [account]

trading_drawdown_current:
  type: gauge
  help: "Current drawdown percentage"
  labels: [account]

trading_open_positions:
  type: gauge
  help: "Number of open positions"
  labels: [account]

trading_risk_exposure:
  type: gauge
  help: "Current total risk exposure as percentage of balance"
  labels: [account]

# ─── Agent Metrics ─────────────────────────────────────────────
agent_latency_seconds:
  type: histogram
  help: "Agent processing latency"
  buckets: [0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
  labels: [agent_name, loop_type]

agent_tokens_consumed:
  type: counter
  help: "Total tokens consumed by agent"
  labels: [agent_name, model]

agent_errors_total:
  type: counter
  help: "Total agent errors"
  labels: [agent_name, error_type]

agent_timeout_total:
  type: counter
  help: "Total agent timeouts"
  labels: [agent_name]

agent_eval_pass_rate:
  type: gauge
  help: "Agent eval pass rate (rolling 24h)"
  labels: [agent_name]

# ─── Pipeline Metrics ─────────────────────────────────────────
pipeline_processing_seconds:
  type: histogram
  help: "End-to-end pipeline processing time"
  buckets: [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
  labels: [pair, timeframe]

pipeline_step_seconds:
  type: histogram
  help: "Individual step processing time"
  buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
  labels: [step_name]

pipeline_halts_total:
  type: counter
  help: "Pipeline halts (AVOID_ALL, choppy market, etc.)"
  labels: [halt_reason, step]

# ─── Infrastructure Metrics ───────────────────────────────────
event_bus_messages_published:
  type: counter
  help: "Messages published to event bus"
  labels: [stream]

event_bus_messages_consumed:
  type: counter
  help: "Messages consumed from event bus"
  labels: [stream, consumer_group]

event_bus_consumer_lag:
  type: gauge
  help: "Consumer group lag (messages behind)"
  labels: [stream, consumer_group]

redis_memory_bytes:
  type: gauge
  help: "Redis memory usage"

database_query_seconds:
  type: histogram
  help: "Database query latency"
  buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
  labels: [query_type]

# ─── Cost Metrics ─────────────────────────────────────────────
llm_cost_usd:
  type: counter
  help: "LLM API cost in USD"
  labels: [model, agent_name]

llm_cache_hit_rate:
  type: gauge
  help: "LLM context cache hit rate"
  labels: [model]

data_feed_cost_usd:
  type: counter
  help: "Data feed cost in USD"
  labels: [provider]

broker_cost_usd:
  type: counter
  help: "Broker fees in USD"
  labels: [broker, fee_type]
```

### 4.3 Prometheus Metric Implementation

```python
# alpha/monitoring/metrics.py
"""
Prometheus metrics for AlphaStack.
"""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

# ─── Trading Metrics ───────────────────────────────────────────
SIGNALS_TOTAL = Counter(
    'alphastack_signals_total',
    'Total trading signals generated',
    ['pair', 'direction', 'timeframe']
)

CONFLUENCE_SCORE = Histogram(
    'alphastack_confluence_score',
    'Distribution of confluence scores',
    ['pair'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0]
)

ORDERS_TOTAL = Counter(
    'alphastack_orders_total',
    'Total orders placed',
    ['pair', 'direction', 'broker', 'status']
)

ORDERS_REJECTED = Counter(
    'alphastack_orders_rejected_total',
    'Total orders rejected by risk governor',
    ['pair', 'reason']
)

PNL_DAILY = Gauge(
    'alphastack_pnl_daily',
    'Daily P&L in account currency',
    ['account']
)

DRAWDOWN_CURRENT = Gauge(
    'alphastack_drawdown_current',
    'Current drawdown percentage',
    ['account']
)

OPEN_POSITIONS = Gauge(
    'alphastack_open_positions',
    'Number of open positions',
    ['account']
)

RISK_EXPOSURE = Gauge(
    'alphastack_risk_exposure',
    'Current total risk exposure as % of balance',
    ['account']
)

# ─── Agent Metrics ─────────────────────────────────────────────
AGENT_LATENCY = Histogram(
    'alphastack_agent_latency_seconds',
    'Agent processing latency',
    ['agent_name', 'loop_type'],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
)

AGENT_TOKENS = Counter(
    'alphastack_agent_tokens_consumed',
    'Total tokens consumed by agent',
    ['agent_name', 'model']
)

AGENT_ERRORS = Counter(
    'alphastack_agent_errors_total',
    'Total agent errors',
    ['agent_name', 'error_type']
)

AGENT_TIMEOUTS = Counter(
    'alphastack_agent_timeout_total',
    'Total agent timeouts',
    ['agent_name']
)

AGENT_EVAL_PASS_RATE = Gauge(
    'alphastack_agent_eval_pass_rate',
    'Agent eval pass rate (rolling 24h)',
    ['agent_name']
)

# ─── Pipeline Metrics ─────────────────────────────────────────
PIPELINE_LATENCY = Histogram(
    'alphastack_pipeline_processing_seconds',
    'End-to-end pipeline processing time',
    ['pair', 'timeframe'],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
)

PIPELINE_STEP_LATENCY = Histogram(
    'alphastack_pipeline_step_seconds',
    'Individual step processing time',
    ['step_name'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

PIPELINE_HALTS = Counter(
    'alphastack_pipeline_halts_total',
    'Pipeline halts',
    ['halt_reason', 'step']
)

# ─── Cost Metrics ─────────────────────────────────────────────
LLM_COST = Counter(
    'alphastack_llm_cost_usd',
    'LLM API cost in USD',
    ['model', 'agent_name']
)

LLM_CACHE_HIT_RATE = Gauge(
    'alphastack_llm_cache_hit_rate',
    'LLM context cache hit rate',
    ['model']
)

# Usage in agent code:
# with AGENT_LATENCY.labels(agent_name='news', loop_type='react').time():
#     result = await news_agent.process(event)
# AGENT_TOKENS.labels(agent_name='news', model='gpt-4.1').inc(response.usage.total_tokens)
# LLM_COST.labels(model='gpt-4.1', agent_name='news').inc(response.cost_usd)
```

### 4.4 Grafana Dashboard Queries

```yaml
# infra/monitoring/grafana/dashboards/alphastack_overview.json
# Grafana dashboard: AlphaStack Trading Overview

panels:
  # ─── Panel 1: Signal Generation Rate ────────────────────────
  - title: "Signals per Hour"
    type: timeseries
    targets:
      - expr: "rate(alphastack_signals_total[1h])"
        legendFormat: "{{pair}} {{direction}}"

  # ─── Panel 2: Confluence Score Distribution ─────────────────
  - title: "Confluence Score Distribution (24h)"
    type: heatmap
    targets:
      - expr: "alphastack_confluence_score_bucket"
        legendFormat: "{{le}}"

  # ─── Panel 3: Order Fill Rate ───────────────────────────────
  - title: "Order Fill Rate"
    type: stat
    targets:
      - expr: "sum(rate(alphastack_orders_filled_total[1h])) / sum(rate(alphastack_orders_total[1h])) * 100"
        legendFormat: "Fill Rate %"

  # ─── Panel 4: Risk Rejection Reasons ───────────────────────
  - title: "Risk Rejections by Reason"
    type: piechart
    targets:
      - expr: "sum by (reason) (increase(alphastack_orders_rejected_total[24h]))"
        legendFormat: "{{reason}}"

  # ─── Panel 5: Daily P&L ────────────────────────────────────
  - title: "Daily P&L"
    type: timeseries
    targets:
      - expr: "alphastack_pnl_daily"
        legendFormat: "{{account}}"
    fieldConfig:
      thresholds:
        steps:
          - color: red, value: -100
          - color: yellow, value: 0
          - color: green, value: 100

  # ─── Panel 6: Current Drawdown ─────────────────────────────
  - title: "Current Drawdown %"
    type: gauge
    targets:
      - expr: "alphastack_drawdown_current"
        legendFormat: "{{account}}"
    fieldConfig:
      thresholds:
        steps:
          - color: green, value: 0
          - color: yellow, value: 5
          - color: red, value: 10
      max: 20

  # ─── Panel 7: Agent Latency (P50/P95/P99) ──────────────────
  - title: "Agent Latency by Agent"
    type: timeseries
    targets:
      - expr: "histogram_quantile(0.50, rate(alphastack_agent_latency_seconds_bucket[5m]))"
        legendFormat: "P50 {{agent_name}}"
      - expr: "histogram_quantile(0.95, rate(alphastack_agent_latency_seconds_bucket[5m]))"
        legendFormat: "P95 {{agent_name}}"
      - expr: "histogram_quantile(0.99, rate(alphastack_agent_latency_seconds_bucket[5m]))"
        legendFormat: "P99 {{agent_name}}"

  # ─── Panel 8: Pipeline Latency ─────────────────────────────
  - title: "Pipeline End-to-End Latency"
    type: timeseries
    targets:
      - expr: "histogram_quantile(0.95, rate(alphastack_pipeline_processing_seconds_bucket[5m]))"
        legendFormat: "P95 {{pair}}"
      - expr: "histogram_quantile(0.50, rate(alphastack_pipeline_processing_seconds_bucket[5m]))"
        legendFormat: "P50 {{pair}}"

  # ─── Panel 9: Agent Errors & Timeouts ──────────────────────
  - title: "Agent Errors"
    type: timeseries
    targets:
      - expr: "rate(alphastack_agent_errors_total[5m])"
        legendFormat: "Errors: {{agent_name}} {{error_type}}"
      - expr: "rate(alphastack_agent_timeout_total[5m])"
        legendFormat: "Timeouts: {{agent_name}}"

  # ─── Panel 10: LLM Cost Tracking ───────────────────────────
  - title: "LLM Cost (USD/hour)"
    type: timeseries
    targets:
      - expr: "rate(alphastack_llm_cost_usd[1h])"
        legendFormat: "{{model}} {{agent_name}}"

  # ─── Panel 11: Event Bus Lag ───────────────────────────────
  - title: "Event Bus Consumer Lag"
    type: timeseries
    targets:
      - expr: "alphastack_event_bus_consumer_lag"
        legendFormat: "{{stream}} {{consumer_group}}"
    alert:
      condition: "> 1000"
      message: "Event bus lag exceeds 1000 messages"

  # ─── Panel 12: Agent Eval Pass Rate ────────────────────────
  - title: "Agent Eval Pass Rate (24h rolling)"
    type: stat
    targets:
      - expr: "alphastack_agent_eval_pass_rate"
        legendFormat: "{{agent_name}}"
    fieldConfig:
      thresholds:
        steps:
          - color: red, value: 0
          - color: yellow, value: 0.90
          - color: green, value: 0.95
```

### 4.5 Alerting Rules

```yaml
# infra/monitoring/prometheus/alerts.yml
groups:
  - name: alphastack_trading
    rules:
      # ─── Critical: Trading halted ──────────────────────────
      - alert: TradingHalted
        expr: increase(alphastack_pipeline_halts_total{halt_reason=~".*circuit_breaker.*"}[5m]) > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Trading circuit breaker triggered"
          description: "Pipeline halted due to {{ $labels.halt_reason }}"

      # ─── Critical: Daily loss approaching limit ────────────
      - alert: DailyLossWarning
        expr: alphastack_pnl_daily < -30
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Daily P&L at {{ $value }} — approaching 4% circuit breaker"

      - alert: DailyLossCritical
        expr: alphastack_pnl_daily < -40
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Daily loss circuit breaker triggered: {{ $value }}"

      # ─── Critical: Drawdown limit ──────────────────────────
      - alert: DrawdownWarning
        expr: alphastack_drawdown_current > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Drawdown at {{ $value }}%"

      - alert: DrawdownCritical
        expr: alphastack_drawdown_current > 15
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "CRITICAL: Drawdown at {{ $value }}% — consider manual intervention"

      # ─── High: Agent timeout ───────────────────────────────
      - alert: AgentTimeoutHigh
        expr: rate(alphastack_agent_timeout_total[15m]) > 5
        for: 5m
        labels:
          severity: high
        annotations:
          summary: "{{ $labels.agent_name }} experiencing high timeout rate"

      # ─── High: Agent error rate ────────────────────────────
      - alert: AgentErrorRateHigh
        expr: rate(alphastack_agent_errors_total[15m]) > 10
        for: 5m
        labels:
          severity: high
        annotations:
          summary: "{{ $labels.agent_name }} error rate elevated"

      # ─── Warning: Pipeline latency ─────────────────────────
      - alert: PipelineLatencyHigh
        expr: histogram_quantile(0.95, rate(alphastack_pipeline_processing_seconds_bucket[5m])) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Pipeline P95 latency at {{ $value }}s — exceeds 2s target"

      # ─── Warning: Event bus lag ────────────────────────────
      - alert: EventBusLagHigh
        expr: alphastack_event_bus_consumer_lag > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Event bus lag at {{ $value }} messages for {{ $labels.consumer_group }}"

      # ─── Warning: LLM cost spike ──────────────────────────
      - alert: LLMCostSpike
        expr: rate(alphastack_llm_cost_usd[1h]) > 5
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "LLM cost rate at ${{ $value }}/hour — investigate"

      # ─── Info: Agent eval regression ───────────────────────
      - alert: AgentEvalRegression
        expr: alphastack_agent_eval_pass_rate < 0.90
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.agent_name }} eval pass rate dropped to {{ $value }}"

  - name: alphastack_infrastructure
    rules:
      - alert: RedisDown
        expr: up{job="redis"} == 0
        for: 1m
        labels:
          severity: critical

      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical

      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes / 1024 / 1024 > 512
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Memory usage at {{ $value }}MB — possible leak"
```

---

## 5. CI/CD Pipeline

### 5.1 GitHub Actions Workflow

```yaml
# .github/workflows/alphastack-ci.yml
name: AlphaStack CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'    # Nightly E2E
    - cron: '0 3 * * 1'    # Weekly performance (Monday 3am UTC)

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  PYTHON_VERSION: '3.12'
  NODE_VERSION: '22'

jobs:
  # ═══════════════════════════════════════════════════════════
  # STAGE 1: Static Analysis (<30s)
  # ═══════════════════════════════════════════════════════════
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Python lint (Ruff)
        uses: astral-sh/ruff-action@v1
        with:
          args: check

      - name: Python type check (mypy)
        run: |
          pip install mypy
          mypy src/ --ignore-missing-imports --strict

      - name: TypeScript lint (ESLint)
        run: |
          cd apps/dashboard
          npm ci
          npx eslint src/

  # ═══════════════════════════════════════════════════════════
  # STAGE 2: Unit Tests (<60s)
  # ═══════════════════════════════════════════════════════════
  unit-tests:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: pip install -e ".[test]"

      - name: Unit tests
        run: |
          pytest tests/unit/ -v \
            --cov=src/ \
            --cov-report=xml \
            --cov-fail-under=90 \
            -m "not integration and not e2e and not slow" \
            --timeout=60

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml

  # ═══════════════════════════════════════════════════════════
  # STAGE 3: Agent Evals (<2min)
  # ═══════════════════════════════════════════════════════════
  agent-evals:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: pip install -e ".[test,agents]"

      - name: Run agent evals
        run: |
          pytest tests/agent_evals/ -v \
            --timeout=120 \
            -m "not regression"

      - name: Check eval pass rates
        run: |
          python scripts/check_eval_pass_rates.py --min-rate 0.85

  # ═══════════════════════════════════════════════════════════
  # STAGE 4: Security Scans (<5min)
  # ═══════════════════════════════════════════════════════════
  security:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4

      - name: Python SAST (Bandit)
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json --severity-level medium

      - name: Dependency audit (pip-audit)
        run: |
          pip install pip-audit
          pip-audit --strict

      - name: Secrets detection (TruffleHog)
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          extra_args: --only-verified

      - name: Container scan (Trivy)
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'alphastack:ci'
          format: 'table'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

  # ═══════════════════════════════════════════════════════════
  # STAGE 5: Build (<5min)
  # ═══════════════════════════════════════════════════════════
  build:
    runs-on: ubuntu-latest
    needs: [unit-tests, security]
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker images
        run: |
          docker compose -f infra/compose/docker-compose.ci.yml build

      - name: Build dashboard
        run: |
          cd apps/dashboard
          npm ci
          npm run build

  # ═══════════════════════════════════════════════════════════
  # STAGE 6: Integration Tests (<10min) — PR and main only
  # ═══════════════════════════════════════════════════════════
  integration-tests:
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name == 'pull_request' || github.ref == 'refs/heads/main'
    services:
      redis:
        image: redis:7-alpine
        ports: ['6379:6379']
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 3
      timescaledb:
        image: timescale/timescaledb:latest-pg16
        env:
          POSTGRES_DB: test_trading
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
        options: >-
          --health-cmd "pg_isready -U test"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 3
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: pip install -e ".[test]"

      - name: Integration tests
        run: |
          pytest tests/integration/ -v --timeout=300
        env:
          REDIS_URL: redis://localhost:6379
          DATABASE_URL: postgresql://test:test@localhost:5432/test_trading

  # ═══════════════════════════════════════════════════════════
  # STAGE 7: Backtest Validation (<15min) — PR only
  # ═══════════════════════════════════════════════════════════
  backtest-validation:
    runs-on: ubuntu-latest
    needs: integration-tests
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: pip install -e ".[test,backtest]"

      - name: Module equivalence tests
        run: pytest tests/backtest/test_module_equivalence.py -v --timeout=300

      - name: Walk-forward validation
        run: pytest tests/backtest/test_walk_forward.py -v --timeout=600

      - name: Monte Carlo validation
        run: pytest tests/backtest/test_monte_carlo.py -v --timeout=300

  # ═══════════════════════════════════════════════════════════
  # STAGE 8: E2E Tests (<15min) — Nightly and pre-release
  # ═══════════════════════════════════════════════════════════
  e2e-tests:
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name == 'schedule' || github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Start full stack
        run: docker compose -f infra/compose/docker-compose.test.yml up -d

      - name: Wait for services
        run: |
          for i in $(seq 1 30); do
            curl -sf http://localhost:8000/health && break
            sleep 2
          done

      - name: E2E trade lifecycle tests
        run: pytest tests/e2e/ -v --timeout=900

      - name: Collect logs on failure
        if: failure()
        run: docker compose -f infra/compose/docker-compose.test.yml logs > e2e-logs.txt

      - name: Upload logs
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: e2e-logs
          path: e2e-logs.txt

      - name: Tear down
        if: always()
        run: docker compose -f infra/compose/docker-compose.test.yml down -v

  # ═══════════════════════════════════════════════════════════
  # STAGE 9: Performance Tests — Weekly
  # ═══════════════════════════════════════════════════════════
  performance-tests:
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name == 'schedule'
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: pip install -e ".[test,perf]"

      - name: Latency benchmarks
        run: pytest tests/performance/test_latency.py -v --timeout=600

      - name: Throughput benchmarks
        run: pytest tests/performance/test_throughput.py -v --timeout=600

      - name: Memory leak detection
        run: pytest tests/performance/test_memory.py -v --timeout=600

      - name: Upload benchmark results
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: benchmark-results/

  # ═══════════════════════════════════════════════════════════
  # STAGE 10: Deploy — Staging
  # ═══════════════════════════════════════════════════════════
  deploy-staging:
    runs-on: ubuntu-latest
    needs: [integration-tests, backtest-validation]
    if: github.ref == 'refs/heads/main'
    environment: staging
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to staging
        run: ./scripts/deploy.sh staging
        env:
          DEPLOY_KEY: ${{ secrets.STAGING_DEPLOY_KEY }}

      - name: Smoke test
        run: |
          for i in $(seq 1 10); do
            STATUS=$(curl -sf http://staging.alphastack.io/health | jq -r '.status')
            [ "$STATUS" = "healthy" ] && exit 0
            sleep 5
          done
          exit 1

  # ═══════════════════════════════════════════════════════════
  # STAGE 11: Deploy — Production
  # ═══════════════════════════════════════════════════════════
  deploy-production:
    runs-on: ubuntu-latest
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to production (blue-green)
        run: ./scripts/deploy.sh production
        env:
          DEPLOY_KEY: ${{ secrets.PRODUCTION_DEPLOY_KEY }}

      - name: Health check
        run: |
          for i in $(seq 1 10); do
            STATUS=$(curl -sf https://api.alphastack.io/health | jq -r '.status')
            [ "$STATUS" = "healthy" ] && exit 0
            sleep 5
          done
          exit 1

      - name: Rollback on failure
        if: failure()
        run: ./scripts/rollback.sh production
```

### 5.2 Pytest Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
timeout = 300

markers = [
    "unit: Unit tests (fast, no external dependencies)",
    "integration: Integration tests (requires Docker services)",
    "e2e: End-to-end tests (full system)",
    "backtest: Backtest validation tests",
    "performance: Performance benchmarks",
    "security: Security-focused tests",
    "agent_eval: Agent evaluation tests",
    "regression: Agent regression tests (from trace mining)",
    "slow: Tests that take >30 seconds",
    "flaky: Known flaky tests (allowed to fail)",
]

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/fixtures/*"]

[tool.coverage.report]
fail_under = 90
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
]
```

---

## 6. Quality Gates

### 6.1 Gate Definitions

Quality gates are hard requirements that must pass before code progresses to the next stage.

| Gate | Stage | Criteria | Failure Action |
|------|-------|----------|----------------|
| **G1: Lint** | Every commit | Zero lint errors, zero type errors | Block commit |
| **G2: Unit** | Every PR | ≥90% coverage, 0 failures | Block merge |
| **G3: Agent Evals** | Every PR | ≥85% pass rate per agent | Block merge |
| **G4: Security** | Every PR | Zero critical/high CVEs, zero secrets | Block merge |
| **G5: Integration** | PR to main | 0 failures, all critical paths covered | Block merge |
| **G6: Backtest** | PR to main | OOS Sharpe ≥50% of IS, Monte Carlo ruin <5% | Block merge |
| **G7: E2E** | Nightly + pre-release | All scenarios pass | Block release |
| **G8: Performance** | Weekly + pre-release | P95 latency within targets, no regressions >10% | Block release |
| **G9: Shadow Mode** | Pre-production | Zero divergences for 24h minimum | Block production |
| **G10: Paper Trading** | Pre-production | Win rate within 10% of backtest, 7+ days | Block production |

### 6.2 Gate Implementation

```python
# scripts/quality_gates.py
"""
Quality gate checks. Run in CI/CD pipeline.
Exit code 0 = gate passed, exit code 1 = gate failed.
"""
import json
import sys
from pathlib import Path

def check_coverage(report_path: str, min_coverage: float = 90.0) -> bool:
    """G2: Check unit test coverage meets minimum."""
    with open(report_path) as f:
        report = json.load(f)

    total_coverage = report['totals']['percent_covered']
    if total_coverage < min_coverage:
        print(f"FAIL: Coverage {total_coverage:.1f}% < {min_coverage}%")
        return False

    # Check critical modules have 100% coverage
    critical_modules = ['risk/governor', 'risk/circuit_breakers']
    for module in critical_modules:
        for file_path, data in report['files'].items():
            if module in file_path:
                file_coverage = data['summary']['percent_covered']
                if file_coverage < 100:
                    print(f"FAIL: Critical module {module} at {file_coverage:.1f}% (need 100%)")
                    return False

    print(f"PASS: Coverage {total_coverage:.1f}%")
    return True

def check_eval_pass_rates(results_dir: str, min_rate: float = 0.85) -> bool:
    """G3: Check agent eval pass rates."""
    all_pass = True
    for result_file in Path(results_dir).glob("*.json"):
        with open(result_file) as f:
            results = json.load(f)

        agent_name = result_file.stem
        pass_rate = results['pass_rate']

        if pass_rate < min_rate:
            print(f"FAIL: {agent_name} eval pass rate {pass_rate:.1%} < {min_rate:.0%}")
            all_pass = False
        else:
            print(f"PASS: {agent_name} eval pass rate {pass_rate:.1%}")

    return all_pass

def check_backtest_validation(results_path: str) -> bool:
    """G6: Check backtest validation results."""
    with open(results_path) as f:
        results = json.load(f)

    checks = [
        ("OOS degradation", results['degradation_ratio'] >= 0.5, f"{results['degradation_ratio']:.2f}"),
        ("Monte Carlo ruin", results['ruin_probability'] < 0.05, f"{results['ruin_probability']:.3f}"),
        ("Parameter stability", results['param_cv'] < 0.5, f"{results['param_cv']:.2f}"),
    ]

    all_pass = True
    for name, passed, value in checks:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {name} = {value}")
        if not passed:
            all_pass = False

    return all_pass

def check_performance_regression(current_path: str, baseline_path: str, max_regression: float = 0.10) -> bool:
    """G8: Check for performance regressions."""
    with open(current_path) as f:
        current = json.load(f)
    with open(baseline_path) as f:
        baseline = json.load(f)

    all_pass = True
    for metric, current_value in current.items():
        baseline_value = baseline.get(metric)
        if baseline_value is None:
            continue

        regression = (current_value - baseline_value) / baseline_value
        if regression > max_regression:
            print(f"FAIL: {metric} regressed {regression:.1%} (current: {current_value}, baseline: {baseline_value})")
            all_pass = False
        else:
            print(f"PASS: {metric} within {max_regression:.0%} of baseline")

    return all_pass

if __name__ == "__main__":
    gate = sys.argv[1]
    args = sys.argv[2:]

    gates = {
        'coverage': check_coverage,
        'evals': check_eval_pass_rates,
        'backtest': check_backtest_validation,
        'performance': check_performance_regression,
    }

    if gate not in gates:
        print(f"Unknown gate: {gate}. Available: {list(gates.keys())}")
        sys.exit(2)

    passed = gates[gate](*args)
    sys.exit(0 if passed else 1)
```

### 6.3 Deployment Phase Requirements

```
PHASE 1: Development (current → 2 weeks)
├── G1: Lint         ✅ Must pass
├── G2: Unit tests   ✅ Must pass (target: 80% coverage initially)
├── G4: Security     ✅ Must pass
└── Goal: Get to 0 tests → basic test coverage

PHASE 2: Stabilization (weeks 3-6)
├── G1-G4            ✅ All must pass
├── G5: Integration  ✅ Must pass
├── G3: Agent Evals  ✅ Must pass (target: 80% pass rate)
├── G6: Backtest     ✅ Must pass
└── Goal: Full test coverage, CI/CD operational

PHASE 3: Paper Trading (weeks 7-10)
├── G1-G6            ✅ All must pass
├── G7: E2E          ✅ Must pass
├── G8: Performance  ✅ Must pass
├── G9: Shadow Mode  ✅ 24h zero divergences
├── G10: Paper Trade ✅ 7+ days, win rate within 10% of backtest
└── Goal: Validate system under real market conditions

PHASE 4: Live Trading (week 11+)
├── G1-G10           ✅ ALL must pass
├── Manual approval  ✅ Required for first live trade
├── Monitoring       ✅ All dashboards green, alerts configured
└── Goal: Graduated capital deployment (start small)
```

---

## 7. Performance Benchmarks

### 7.1 Latency Targets

| Component | Metric | Target | Critical Threshold |
|-----------|--------|--------|--------------------|
| **Signal-to-Execution** | End-to-end latency | <500ms (P95) | >2s = investigation |
| **Pipeline Processing** | Per-candle processing | <200ms (P95) | >500ms = investigation |
| **Risk Governor** | Single check | <10ms (P99) | >50ms = critical |
| **Order Placement (MT5)** | Broker round-trip | <200ms (P95) | >1s = investigation |
| **Order Placement (CCXT)** | Exchange round-trip | <500ms (P95) | >2s = investigation |
| **Agent Processing** | Per-agent inference | <1s (P95) | >5s = timeout |
| **ML Model Inference** | ONNX Runtime | <100ms (P95) | >500ms = critical |
| **API Response** | HTTP latency | <100ms (P95) | >500ms = investigation |
| **Event Bus** | Message delivery | <5ms (P95) | >50ms = investigation |
| **Database Query (hot)** | Redis cache hit | <10ms (P95) | >50ms = investigation |
| **Database Query (cold)** | TimescaleDB | <100ms (P95) | >500ms = investigation |

### 7.2 Throughput Requirements

| Component | Metric | Target | Measurement |
|-----------|--------|--------|-------------|
| **Event Bus** | Messages/second | >10,000 | Load test with 50K messages |
| **Pipeline** | Concurrent instruments | 10+ | Parallel processing test |
| **WebSocket** | Fan-out clients | 1,000 | Broadcast latency <50ms |
| **API** | Requests/second | 500 | Load test |
| **Sustained Load** | 1-hour continuous | No degradation | Memory, latency, error rate stable |

### 7.3 Cost Limits

| Resource | Metric | Limit | Alert Threshold |
|----------|--------|-------|-----------------|
| **LLM API** | Cost per signal | <$0.05 | >$0.10 |
| **LLM API** | Cost per hour (normal) | <$2.00 | >$5.00 |
| **LLM API** | Cost per hour (active) | <$5.00 | >$10.00 |
| **Data Feeds** | Monthly cost | <$500 | >$400 |
| **Infrastructure** | Monthly cost | <$200 | >$150 |
| **Total Monthly** | All costs | <$1,000 | >$800 |

### 7.4 Performance Test Implementation

```python
# tests/performance/test_latency.py
"""
Performance benchmarks for AlphaStack.
Run weekly and before any release.
"""
import pytest
import time
import statistics
import psutil
import os

class TestLatencyBenchmarks:

    async def test_pipeline_latency_p95_under_200ms(self, pipeline, sample_data):
        """Pipeline processes a single candle in <200ms at P95."""
        latencies = []

        for i in range(100):
            event = build_event(sample_data.iloc[i])
            start = time.perf_counter_ns()
            await pipeline.process(event)
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            latencies.append(elapsed_ms)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[94]
        p99 = sorted(latencies)[98]

        assert p50 < 100, f"P50 {p50:.1f}ms > 100ms"
        assert p95 < 200, f"P95 {p95:.1f}ms > 200ms"
        assert p99 < 500, f"P99 {p99:.1f}ms > 500ms"

    async def test_risk_governor_p99_under_10ms(self, governor):
        """Risk check completes in <10ms at P99."""
        proposal = build_proposal()
        account = build_account()

        latencies = []
        for _ in range(1000):
            start = time.perf_counter_ns()
            governor.check(proposal, account)
            latencies.append((time.perf_counter_ns() - start) / 1_000_000)

        p99 = sorted(latencies)[989]
        assert p99 < 10, f"P99 {p99:.2f}ms > 10ms"

    async def test_event_bus_throughput_above_10k(self, event_bus):
        """Event bus handles >10,000 messages/second."""
        count = 50000
        payload = {"bid": 1.0850, "ask": 1.0852}

        start = time.perf_counter()
        for i in range(count):
            await event_bus.publish("perf.test", {**payload, "seq": i})
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        assert throughput > 10000, f"Throughput {throughput:.0f} < 10K"

    async def test_concurrent_instruments_no_degradation(self, pipeline):
        """10 concurrent instruments don't degrade each other."""
        instruments = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
                       "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "XAUUSD"]

        async def process_one(symbol):
            lats = []
            for _ in range(50):
                event = build_event(pair=symbol)
                start = time.perf_counter_ns()
                await pipeline.process(event)
                lats.append((time.perf_counter_ns() - start) / 1_000_000)
            return statistics.median(lats)

        results = await asyncio.gather(*[process_one(s) for s in instruments])
        median = statistics.median(results)

        for symbol, latency in zip(instruments, results):
            assert latency < median * 2, \
                f"{symbol} latency {latency:.1f}ms > 2x median {median:.1f}ms"

class TestMemoryUsage:

    async def test_no_memory_leak_under_sustained_load(self, pipeline):
        """1000 iterations doesn't leak memory (>100MB growth = leak)."""
        process = psutil.Process(os.getpid())
        initial = process.memory_info().rss / 1024 / 1024

        for _ in range(1000):
            await pipeline.process(build_event())

        import gc; gc.collect()
        final = process.memory_info().rss / 1024 / 1024
        growth = final - initial

        assert growth < 100, f"Memory grew {growth:.1f}MB — possible leak"

    async def test_memory_under_512mb(self, pipeline):
        """Engine memory stays under 512MB during operation."""
        process = psutil.Process(os.getpid())

        for _ in range(500):
            await pipeline.process(build_event())

        memory_mb = process.memory_info().rss / 1024 / 1024
        assert memory_mb < 512, f"Memory {memory_mb:.0f}MB > 512MB"
```

---

## Appendix A: Monitoring Stack Setup

### Docker Compose for Monitoring

```yaml
# infra/compose/docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ../monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - ../monitoring/alerts.yml:/etc/prometheus/alerts.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=90d'

  grafana:
    image: grafana/grafana:latest
    volumes:
      - ../monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ../monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: 'false'

  alertmanager:
    image: prom/alertmanager:latest
    volumes:
      - ../monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml
    ports:
      - "9093:9093"

  node-exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"

  redis-exporter:
    image: oliver006/redis_exporter:latest
    ports:
      - "9121:9121"
    environment:
      REDIS_ADDR: redis://redis:6379

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    ports:
      - "9187:9187"
    environment:
      DATA_SOURCE_NAME: "postgresql://postgres:password@timescaledb:5432/alphastack?sslmode=disable"

volumes:
  prometheus_data:
  grafana_data:
```

### Prometheus Configuration

```yaml
# infra/monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  - job_name: 'alphastack-engine'
    static_configs:
      - targets: ['trading-engine:8000']
    metrics_path: '/metrics'

  - job_name: 'alphastack-api'
    static_configs:
      - targets: ['api:8001']
    metrics_path: '/metrics'

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

---

## Appendix B: Implementation Roadmap

```
WEEK 1-2: Foundation
├── Set up pytest infrastructure (conftest, fixtures, markers)
├── Write Risk Governor tests (100% coverage — highest priority)
├── Write basic unit tests for each agent
├── Set up GitHub Actions (lint + unit test stages)
└── Configure pre-commit hooks (Ruff, mypy)

WEEK 3-4: Agent Testing
├── Build agent eval framework
├── Create eval datasets (news, strategy, risk scenarios)
├── Implement trace capture infrastructure
├── Write integration tests (agent chain, event bus)
└── Add agent eval stage to CI/CD

WEEK 5-6: Trading Validation
├── Build backtest validation framework
├── Write module equivalence tests
├── Implement fill simulator with realistic slippage
├── Write walk-forward and Monte Carlo validation
└── Add backtest validation stage to CI/CD

WEEK 7-8: Monitoring
├── Deploy Prometheus + Grafana + Alertmanager
├── Implement all metric definitions in code
├── Build Grafana dashboards (trading overview, agent health, costs)
├── Configure alerting rules
└── Add performance test stage to CI/CD

WEEK 9-10: Paper Trading
├── Deploy paper trading engine
├── Run shadow mode (live vs paper comparison)
├── Collect 7+ days of paper trading data
├── Compare against backtest expectations
└── Fix any divergences

WEEK 11+: Production Readiness
├── All quality gates passing
├── Monitoring dashboards green
├── Paper trading within 10% of backtest
├── Manual approval for first live trade
└── Graduated capital deployment
```

---

## Appendix C: Key Research Findings Applied

| Research Finding | Source | Application in This Plan |
|-----------------|--------|--------------------------|
| 54% enterprises had agent security incidents | VentureBeat Jul 2026 | Security scans at every stage, credential isolation tests |
| Intuit abandoned NL agent handoffs (error compounding) | VentureBeat Jul 2026 | Structured agent chain tests, no NL handoffs between agents |
| Agent improvement = data mining from traces | LangChain Jul 2026 | Trace mining pipeline, regression tests from mined traces |
| Harness tuning > model upgrades | LangChain+NVIDIA Jul 2026 | Agent eval framework tests harness quality, not model quality |
| Per-node timeouts prevent pipeline stalls | LangGraph 1.0 | Timeout configuration per agent, timeout tests |
| Memory poisoning is top OWASP risk | OWASP Jun 2026 | Memory integrity tests, append-only audit trail |
| Cascading failures in multi-agent chains | OWASP Jun 2026 | Pipeline halt tests, circuit breakers, graceful degradation |
| Half of agents pass evals but fail in production | VentureBeat Jul 2026 | Paper trading + shadow mode as mandatory pre-production gates |
| Cost ≠ sticker price (cache dynamics) | IBM Research Jul 2026 | Actual cost tracking per signal, not just token pricing |
| Code-orchestrated subagents > model-orchestrated | LangChain RLMs Jul 2026 | Pipeline orchestrator uses programmatic dispatch, not NL |

---

*This plan transforms AlphaStack from 0 tests to production-grade quality. Every line of code that touches real money will be tested, monitored, and gated.*

*Generated: 2026-07-19 16:21 CST*
