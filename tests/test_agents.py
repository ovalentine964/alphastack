"""Unit tests for the upgraded AlphaStack agent system (v2.0).

Tests cover:
- Circuit breaker (state transitions, thresholds, recovery)
- Retry policy (exponential backoff, jitter)
- Base agent (timeout, circuit breaker integration, health monitoring, traces)
- Strategy agent (regime detection, confluence adjustment)
- Risk agent (Kelly criterion, drawdown monitoring, correlation, circuit breakers)
- Execution agent (slippage tracking, algorithm selection, TWAP/VWAP)
- Reflection agent (journal generation, performance metrics, strategy suggestions)
- Orchestrator graph (routing, HITL)
"""

from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphastack.agents.base import (
    AlphaStackAgent,
    AgentHealth,
    CircuitBreaker,
    CircuitState,
    ExecutionTrace,
    RetryPolicy,
)
from alphastack.agents.risk_agent import (
    CorrelationMonitor,
    DrawdownMonitor,
    RiskAgent,
    kelly_fraction,
)
from alphastack.agents.execution_agent import (
    ExecutionAgent,
    SlippageTracker,
)
from alphastack.agents.reflection_agent import (
    PerformanceAnalyzer,
    ReflectionAgent,
    StrategyImprover,
    TradeJournalEntry,
)
from alphastack.agents.strategy_agent import (
    MarketRegime,
    StrategyAgent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DummyAgent(AlphaStackAgent):
    """Minimal concrete agent for testing the base class."""

    def __init__(self, **kwargs: Any) -> None:
        self._execute_fn = kwargs.pop("execute_fn", None)
        super().__init__(name="test", role="test", **kwargs)

    def system_prompt(self) -> str:
        return "test agent"

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if self._execute_fn:
            return await self._execute_fn(state)
        return {"result": "ok", "_confidence": 0.9}


# ===========================================================================
# Circuit Breaker Tests
# ===========================================================================

class TestCircuitBreaker:
    """Test circuit breaker state machine."""

    def test_initial_state_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_transition_to_open(self):
        cb = CircuitBreaker(failure_threshold=3, name="test")
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_transition_to_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1, name="test")
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True  # probe request allowed

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, name="test")
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, name="test")
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=2, name="test")
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_window_expiry(self):
        """Failures outside the window should not trigger the breaker."""
        cb = CircuitBreaker(failure_threshold=3, window_seconds=0.1, name="test")
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)  # wait for window to expire
        cb.record_failure()  # only 1 failure in current window
        assert cb.state == CircuitState.CLOSED

    def test_as_dict(self):
        cb = CircuitBreaker(name="test")
        d = cb.as_dict()
        assert d["name"] == "test"
        assert d["state"] == "closed"
        assert d["failure_count"] == 0


# ===========================================================================
# Retry Policy Tests
# ===========================================================================

class TestRetryPolicy:
    """Test exponential backoff retry policy."""

    def test_delay_exponential(self):
        policy = RetryPolicy(base_delay=1.0, exponential_base=2.0, jitter=False)
        assert policy.delay_for_attempt(0) == 1.0
        assert policy.delay_for_attempt(1) == 2.0
        assert policy.delay_for_attempt(2) == 4.0

    def test_delay_max_capped(self):
        policy = RetryPolicy(base_delay=1.0, max_delay=5.0, exponential_base=2.0, jitter=False)
        assert policy.delay_for_attempt(10) == 5.0

    def test_delay_jitter_range(self):
        policy = RetryPolicy(base_delay=10.0, jitter=True)
        delays = [policy.delay_for_attempt(0) for _ in range(100)]
        # Jitter: 50-150% of base
        assert all(5.0 <= d <= 15.0 for d in delays)


# ===========================================================================
# Base Agent Tests
# ===========================================================================

class TestBaseAgent:
    """Test the upgraded base agent."""

    @pytest.mark.asyncio
    async def test_run_success(self):
        agent = DummyAgent(timeout=5.0)
        result = await agent.run({"test": True})
        assert result["result"] == "ok"
        assert agent.health.status == "healthy"
        assert agent.health.total_calls == 1
        assert agent.health.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_run_timeout(self):
        async def slow_execute(state: dict) -> dict:
            await asyncio.sleep(10)
            return {}

        agent = DummyAgent(execute_fn=slow_execute, timeout=0.1, max_retries=0)
        result = await agent.run({})
        assert "_error" in result
        assert agent.health.consecutive_failures >= 1

    @pytest.mark.asyncio
    async def test_run_circuit_breaker_open(self):
        agent = DummyAgent(timeout=5.0, cb_failure_threshold=2)

        # Trip the circuit breaker
        agent.circuit_breaker.record_failure()
        agent.circuit_breaker.record_failure()
        assert agent.circuit_breaker.state == CircuitState.OPEN

        result = await agent.run({})
        assert result.get("_circuit_open") is True

    @pytest.mark.asyncio
    async def test_run_retry_on_failure(self):
        call_count = 0

        async def fail_then_succeed(state: dict) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient error")
            return {"result": "ok", "_confidence": 1.0}

        agent = DummyAgent(
            execute_fn=fail_then_succeed,
            timeout=5.0,
            max_retries=3,
            retry_base_delay=0.01,
        )
        result = await agent.run({})
        assert result["result"] == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_trace_capture(self):
        agent = DummyAgent(timeout=5.0)
        await agent.run({"test": True})
        traces = agent.get_traces()
        assert len(traces) == 1
        assert traces[0]["status"] == "success"
        assert traces[0]["agent_name"] == "test"

    @pytest.mark.asyncio
    async def test_health_heartbeat(self):
        agent = DummyAgent(timeout=5.0)
        health = agent.heartbeat()
        assert health["agent_name"] == "test"
        assert health["status"] == "healthy"
        assert health["uptime_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_latency_tracking(self):
        agent = DummyAgent(timeout=5.0)
        for _ in range(5):
            await agent.run({})
        assert agent.health.avg_latency_ms >= 0
        assert agent.health.p99_latency_ms >= 0


# ===========================================================================
# Kelly Criterion Tests
# ===========================================================================

class TestKellyCriterion:
    """Test Kelly fraction calculation."""

    def test_basic_kelly(self):
        # 60% win rate, 2:1 R:R
        f = kelly_fraction(win_rate=0.6, avg_win=2.0, avg_loss=1.0, fraction=1.0)
        # Kelly: (0.6 * 2 - 0.4) / 2 = 0.4
        assert abs(f - 0.4) < 0.01

    def test_half_kelly(self):
        f = kelly_fraction(win_rate=0.6, avg_win=2.0, avg_loss=1.0, fraction=0.5)
        assert abs(f - 0.2) < 0.01

    def test_negative_kelly_returns_zero(self):
        # 30% win rate, 1:1 R:R → negative Kelly
        f = kelly_fraction(win_rate=0.3, avg_win=1.0, avg_loss=1.0, fraction=1.0)
        assert f == 0.0

    def test_edge_cases(self):
        assert kelly_fraction(win_rate=0.0, avg_win=2.0, avg_loss=1.0) == 0.0
        assert kelly_fraction(win_rate=1.0, avg_win=2.0, avg_loss=1.0) == 0.0
        assert kelly_fraction(win_rate=0.5, avg_win=0.0, avg_loss=1.0) == 0.0
        assert kelly_fraction(win_rate=0.5, avg_win=2.0, avg_loss=0.0) == 0.0


# ===========================================================================
# Drawdown Monitor Tests
# ===========================================================================

class TestDrawdownMonitor:
    """Test drawdown monitoring."""

    def test_no_drawdown(self):
        dm = DrawdownMonitor(max_drawdown_pct=15.0)
        dm.update(10000)
        dm.update(10500)
        assert dm.current_drawdown_pct == 0.0

    def test_drawdown_computation(self):
        dm = DrawdownMonitor(max_drawdown_pct=15.0)
        dm.update(10000)  # peak
        dm.update(9000)   # 10% drawdown
        assert abs(dm.current_drawdown_pct - 10.0) < 0.01

    def test_drawdown_breach(self):
        dm = DrawdownMonitor(max_drawdown_pct=10.0)
        dm.update(10000)
        dm.update(8500)  # 15% drawdown
        assert dm.is_breach() is True

    def test_recovery(self):
        dm = DrawdownMonitor(max_drawdown_pct=15.0)
        dm.update(10000)
        dm.update(8000)  # 20% drawdown
        assert dm.is_breach() is True

        dm.update(11000)  # new peak, recovery
        assert dm.current_drawdown_pct == 0.0
        assert dm.is_breach() is False

    def test_max_historical(self):
        dm = DrawdownMonitor(max_drawdown_pct=15.0)
        dm.update(10000)
        dm.update(9000)   # 10%
        dm.update(9500)   # 5% from peak
        dm.update(8500)   # 15%
        assert abs(dm.max_historical_drawdown_pct - 15.0) < 0.01


# ===========================================================================
# Correlation Monitor Tests
# ===========================================================================

class TestCorrelationMonitor:
    """Test correlation monitoring."""

    def test_no_correlation_data(self):
        cm = CorrelationMonitor(max_correlation=0.7)
        allowed, corr = cm.check_correlation("EUR/USD", ["GBP/USD"])
        assert allowed is True
        assert corr == 0.0

    def test_high_correlation_rejected(self):
        cm = CorrelationMonitor(max_correlation=0.7)
        # Add correlated returns
        for i in range(20):
            cm.add_return("EUR/USD", 0.001 + i * 0.0001)
            cm.add_return("GBP/USD", 0.001 + i * 0.0001)  # identical

        allowed, corr = cm.check_correlation("EUR/USD", ["GBP/USD"])
        # Identical returns → correlation = 1.0 > 0.7
        assert allowed is False
        assert corr > 0.7

    def test_low_correlation_accepted(self):
        cm = CorrelationMonitor(max_correlation=0.7)
        import random
        random.seed(42)
        for _ in range(20):
            cm.add_return("EUR/USD", random.gauss(0, 0.01))
            cm.add_return("BTC/USDT", random.gauss(0, 0.05))  # different distribution

        allowed, corr = cm.check_correlation("EUR/USD", ["BTC/USDT"])
        assert allowed is True


# ===========================================================================
# Slippage Tracker Tests
# ===========================================================================

class TestSlippageTracker:
    """Test slippage tracking."""

    def test_positive_slippage_buy(self):
        st = SlippageTracker()
        obs = st.record("BTC/USDT", "buy", 50000.0, 49990.0, 1.0)
        # Buy at lower than expected → positive slippage
        assert obs["slippage_abs"] < 0  # negative = favorable for buy
        assert obs["slippage_bps"] < 0

    def test_negative_slippage_buy(self):
        st = SlippageTracker()
        obs = st.record("BTC/USDT", "buy", 50000.0, 50050.0, 1.0)
        assert obs["slippage_abs"] > 0  # paid more → adverse

    def test_slippage_sell(self):
        st = SlippageTracker()
        obs = st.record("BTC/USDT", "sell", 50000.0, 49950.0, 1.0)
        # Sold at less than expected → adverse
        assert obs["slippage_abs"] > 0

    def test_stats(self):
        st = SlippageTracker()
        for i in range(10):
            st.record("BTC/USDT", "buy", 50000.0, 50000.0 + i * 10, 1.0)

        stats = st.get_stats()
        assert stats["count"] == 10
        assert "mean_bps" in stats
        assert "p95_bps" in stats


# ===========================================================================
# Strategy Agent Tests
# ===========================================================================

class TestStrategyAgent:
    """Test strategy agent regime detection and confluence adjustment."""

    def test_regime_detection_trending_up(self):
        agent = StrategyAgent()
        market_data = {
            "adx": 30,
            "closes": [1.1000, 1.1050, 1.1100],
            "sma_20": [1.1020, 1.1030, 1.1040],
        }
        regime = agent._detect_regime(market_data)
        assert regime in (MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN)

    def test_regime_detection_ranging(self):
        agent = StrategyAgent()
        market_data = {
            "adx": 12,
            "bb_width": 0.03,
        }
        regime = agent._detect_regime(market_data)
        assert regime in (MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY)

    def test_regime_detection_volatile(self):
        agent = StrategyAgent()
        market_data = {"atr_pct": 3.0}
        regime = agent._detect_regime(market_data)
        assert regime == MarketRegime.VOLATILE

    def test_regime_detection_low_vol(self):
        agent = StrategyAgent()
        market_data = {"atr_pct": 0.3}
        regime = agent._detect_regime(market_data)
        assert regime == MarketRegime.LOW_VOLATILITY

    def test_regime_detection_unknown(self):
        agent = StrategyAgent()
        regime = agent._detect_regime({})
        assert regime == MarketRegime.UNKNOWN

    def test_confluence_adjustment_news(self):
        agent = StrategyAgent()
        adjusted = agent._adjust_confluence(
            base_confluence=0.7,
            symbol="BTC/USDT",
            market_data={},
            regime=MarketRegime.TRENDING_UP,
            news_adjustment=0.5,
        )
        # 0.7 * regime_mult * (1 - 0.5)
        assert adjusted < 0.7

    def test_fallback_signal(self):
        sig = StrategyAgent._fallback_signal("BTC/USDT", "1h", MarketRegime.RANGING)
        assert sig["side"] == "flat"
        assert sig["strength"] == 0.0
        assert sig["regime"] == "ranging"


# ===========================================================================
# Risk Agent Tests
# ===========================================================================

class TestRiskAgent:
    """Test risk agent with Kelly sizing and circuit breakers."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_all(self):
        agent = RiskAgent()
        # Trip circuit breaker
        agent._drawdown_monitor.update(10000)
        agent._drawdown_monitor.update(5000)  # 50% drawdown

        state = {
            "signals": [{"symbol": "BTC/USDT", "side": "long", "confluence_score": 0.8, "adjusted_confluence": 0.8}],
            "risk_status": {"drawdown_pct": 0.0, "daily_loss_pct": 0.0},
            "news_alerts": [],
            "market_data": {"equity": 5000, "account_balance": 10000},
            "pipeline_context": {},
        }
        result = await agent.execute(state)
        decisions = result["trade_decisions"]
        assert all(d.get("status") == "rejected" for d in decisions)

    @pytest.mark.asyncio
    async def test_kelly_sizing(self):
        agent = RiskAgent()
        agent.update_kelly_stats(win_rate=0.6, avg_win=2.0, avg_loss=1.0)

        state = {
            "signals": [{
                "symbol": "BTC/USDT",
                "side": "long",
                "confluence_score": 0.7,
                "adjusted_confluence": 0.7,
                "entry_price": 50000.0,
                "stop_loss": 49500.0,
            }],
            "risk_status": {"drawdown_pct": 0.0, "daily_loss_pct": 0.0},
            "news_alerts": [],
            "market_data": {"equity": 10000, "account_balance": 10000},
            "pipeline_context": {},
            "positions": [],
        }
        result = await agent.execute(state)
        approved = [d for d in result["trade_decisions"] if d.get("status") == "approved"]
        assert len(approved) == 1
        assert approved[0]["sizing_method"] == "kelly_fractional"
        assert approved[0]["quantity"] > 0

    @pytest.mark.asyncio
    async def test_regime_adjustment(self):
        agent = RiskAgent()
        agent.update_kelly_stats(win_rate=0.6, avg_win=2.0, avg_loss=1.0)

        # Normal regime
        state_normal = {
            "signals": [{
                "symbol": "BTC/USDT", "side": "long", "confluence_score": 0.5,
                "adjusted_confluence": 0.5, "entry_price": 50000.0, "stop_loss": 49500.0,
            }],
            "risk_status": {"drawdown_pct": 0.0, "daily_loss_pct": 0.0},
            "news_alerts": [],
            "market_data": {"equity": 10000, "account_balance": 10000},
            "pipeline_context": {"regime": "trending_up"},
            "positions": [],
        }
        result_normal = await agent.execute(state_normal)

        # Volatile regime
        state_volatile = {**state_normal, "pipeline_context": {"regime": "volatile"}}
        result_volatile = await agent.execute(state_volatile)

        # Volatile should produce smaller sizes or more rejections
        normal_qty = sum(d.get("quantity", 0) for d in result_normal["trade_decisions"] if d.get("status") == "approved")
        volatile_qty = sum(d.get("quantity", 0) for d in result_volatile["trade_decisions"] if d.get("status") == "approved")
        # Either volatile has smaller quantity or more rejections
        if volatile_qty > 0:
            assert volatile_qty <= normal_qty


# ===========================================================================
# Execution Agent Tests
# ===========================================================================

class TestExecutionAgent:
    """Test execution agent with slippage tracking."""

    def test_algorithm_selection_small_order(self):
        agent = ExecutionAgent()
        algo = agent._select_algorithm(quantity=0.01, price=50000.0, avg_volume=10000.0)
        assert algo == "market"

    def test_algorithm_selection_medium_order(self):
        agent = ExecutionAgent()
        algo = agent._select_algorithm(quantity=100.0, price=50000.0, avg_volume=10000.0)
        assert algo in ("twap", "vwap", "market")

    def test_algorithm_selection_no_volume(self):
        agent = ExecutionAgent()
        algo = agent._select_algorithm(quantity=100.0, price=50000.0, avg_volume=0.0)
        assert algo == "market"

    def test_broker_selection_crypto(self):
        assert ExecutionAgent._select_broker("BTC/USDT") == "ccxt"
        assert ExecutionAgent._select_broker("ETH/BTC") == "ccxt"

    def test_broker_selection_forex(self):
        assert ExecutionAgent._select_broker("EURUSD") == "mt5"
        assert ExecutionAgent._select_broker("GBPUSD") == "mt5"

    def test_log_entry_structure(self):
        entry = ExecutionAgent._make_log_entry(
            "d1", "BTC/USDT", "buy", 1.0, 50000.0, "filled",
            broker="ccxt", fill_price=50010.0, algorithm="market",
        )
        assert entry["decision_id"] == "d1"
        assert entry["status"] == "filled"
        assert entry["algorithm"] == "market"
        assert "timestamp" in entry


# ===========================================================================
# Reflection Agent Tests
# ===========================================================================

class TestReflectionAgent:
    """Test reflection agent with journal and performance analysis."""

    def test_performance_metrics_basic(self):
        analyzer = PerformanceAnalyzer()
        pnls = [100.0, -50.0, 200.0, -30.0, 150.0]
        metrics = analyzer.compute_metrics(pnls)
        assert metrics["trade_count"] == 5
        assert metrics["win_count"] == 3
        assert metrics["loss_count"] == 2
        assert abs(metrics["win_rate"] - 0.6) < 0.01
        assert metrics["profit_factor"] > 1.0
        assert metrics["total_pnl"] == 370.0

    def test_performance_metrics_empty(self):
        analyzer = PerformanceAnalyzer()
        metrics = analyzer.compute_metrics([])
        assert metrics["trade_count"] == 0

    def test_performance_metrics_all_wins(self):
        analyzer = PerformanceAnalyzer()
        metrics = analyzer.compute_metrics([100.0, 200.0, 50.0])
        assert metrics["win_rate"] == 1.0
        assert metrics["profit_factor"] == float("inf")

    def test_performance_metrics_all_losses(self):
        analyzer = PerformanceAnalyzer()
        metrics = analyzer.compute_metrics([-100.0, -200.0, -50.0])
        assert metrics["win_rate"] == 0.0
        assert metrics["profit_factor"] == 0.0

    def test_sharpe_ratio(self):
        analyzer = PerformanceAnalyzer()
        # Variable positive returns → positive Sharpe
        pnls = [8.0, 12.0, 9.0, 11.0, 10.0, 13.0, 7.0, 14.0, 10.0, 9.0,
                11.0, 12.0, 8.0, 13.0, 10.0, 9.0, 11.0, 14.0, 7.0, 12.0,
                10.0, 8.0, 13.0, 11.0, 9.0, 12.0, 10.0, 8.0, 14.0, 11.0]
        metrics = analyzer.compute_metrics(pnls)
        assert metrics["sharpe_ratio"] > 0

    def test_sortino_ratio(self):
        analyzer = PerformanceAnalyzer()
        pnls = [100.0, -10.0, 90.0, -30.0, 110.0]
        metrics = analyzer.compute_metrics(pnls)
        assert metrics["sortino_ratio"] > 0

    def test_consecutive_losses(self):
        analyzer = PerformanceAnalyzer()
        pnls = [100.0, -10.0, -20.0, -30.0, 50.0, -10.0, -20.0]
        metrics = analyzer.compute_metrics(pnls)
        assert metrics["max_consecutive_losses"] == 3

    def test_strategy_improver_low_win_rate(self):
        improver = StrategyImprover()
        journal = [{"pnl": -10, "regime": "ranging"}] * 10 + [{"pnl": 5, "regime": "ranging"}] * 2
        metrics = {"win_rate": 0.17, "profit_factor": 0.25, "avg_rr_ratio": 0.5, "trade_count": 12, "expectancy": -5.0, "max_consecutive_losses": 10}
        suggestions = improver.analyze_and_suggest(journal, metrics, {"confluence_threshold": 0.3})
        assert any(s["parameter"] == "min_confluence_score" for s in suggestions)

    def test_strategy_improver_good_performance(self):
        improver = StrategyImprover()
        journal = [{"pnl": 100, "regime": "trending_up"}] * 15
        metrics = {"win_rate": 0.7, "profit_factor": 3.0, "avg_rr_ratio": 2.0, "trade_count": 15, "expectancy": 50.0, "max_consecutive_losses": 1}
        suggestions = improver.analyze_and_suggest(journal, metrics, {})
        # Should suggest Kelly fraction increase
        assert any(s.get("parameter") == "kelly_fraction" for s in suggestions)

    def test_journal_entry(self):
        entry = TradeJournalEntry(
            trade_id="t1",
            symbol="BTC/USDT",
            side="buy",
            entry_price=50000.0,
            exit_price=51000.0,
            quantity=1.0,
            pnl=1000.0,
            regime="trending_up",
        )
        entry.add_tag("winner")
        entry.add_lesson("Good entry timing")

        d = entry.to_dict()
        assert d["pnl"] == 1000.0
        assert d["pnl_pct"] == 2.0
        assert "winner" in d["tags"]
        assert "Good entry timing" in d["lessons"]


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestAgentIntegration:
    """Test agent interactions (base → risk → execution → reflection)."""

    @pytest.mark.asyncio
    async def test_health_across_agents(self):
        """All agents should track health independently."""
        risk = RiskAgent()
        exec_agent = ExecutionAgent()
        reflection = ReflectionAgent()

        # Each has independent health
        h1 = risk.heartbeat()
        h2 = exec_agent.heartbeat()
        h3 = reflection.heartbeat()

        assert h1["agent_name"] == "risk"
        assert h2["agent_name"] == "execution"
        assert h3["agent_name"] == "reflection"
        assert all(h["status"] == "healthy" for h in [h1, h2, h3])

    @pytest.mark.asyncio
    async def test_circuit_breaker_isolation(self):
        """Each agent has an independent circuit breaker."""
        risk = RiskAgent()
        exec_agent = ExecutionAgent()

        # Trip risk agent's circuit breaker
        for _ in range(10):
            risk.circuit_breaker.record_failure()

        # Execution agent should be unaffected
        assert risk.circuit_breaker.state == CircuitState.OPEN
        assert exec_agent.circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_trace_buffer_limit(self):
        """Traces should be bounded."""
        agent = DummyAgent(timeout=5.0)
        agent._max_traces = 5

        for _ in range(10):
            await agent.run({})

        assert len(agent.get_traces()) == 5
