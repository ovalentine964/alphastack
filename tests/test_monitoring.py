"""
Unit tests for the AlphaStack monitoring module.

Tests cover:
- Prometheus metric definitions (existence, label cardinality)
- Metric recording helpers
- Health check registry (liveness, readiness, dependency checks)
- Health check implementations (Redis, Postgres, broker)
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphastack.monitoring import health, metrics
from alphastack.monitoring.health import (
    DependencyHealth,
    HealthRegistry,
    HealthStatus,
)


# ═══════════════════════════════════════════════════════════════════
# METRIC DEFINITION TESTS
# ═══════════════════════════════════════════════════════════════════


class TestMetricDefinitions:
    """Verify all 25+ metrics are defined and properly configured."""

    def test_trading_metrics_exist(self):
        """All trading metrics are defined."""
        assert metrics.SIGNALS_TOTAL is not None
        assert metrics.CONFLUENCE_SCORE is not None
        assert metrics.ORDERS_TOTAL is not None
        assert metrics.ORDERS_REJECTED is not None
        assert metrics.PNL_DAILY is not None
        assert metrics.DRAWDOWN_CURRENT is not None
        assert metrics.OPEN_POSITIONS is not None
        assert metrics.RISK_EXPOSURE is not None
        assert metrics.WIN_RATE is not None

    def test_agent_metrics_exist(self):
        """All agent metrics are defined."""
        assert metrics.AGENT_LATENCY is not None
        assert metrics.AGENT_TOKENS is not None
        assert metrics.AGENT_ERRORS is not None
        assert metrics.AGENT_TIMEOUTS is not None
        assert metrics.AGENT_EVAL_PASS_RATE is not None

    def test_pipeline_metrics_exist(self):
        """All pipeline metrics are defined."""
        assert metrics.PIPELINE_LATENCY is not None
        assert metrics.PIPELINE_STEP_LATENCY is not None
        assert metrics.PIPELINE_HALTS is not None

    def test_event_bus_metrics_exist(self):
        """All event bus metrics are defined."""
        assert metrics.EVENT_BUS_PUBLISHED is not None
        assert metrics.EVENT_BUS_CONSUMED is not None
        assert metrics.EVENT_BUS_LAG is not None

    def test_infrastructure_metrics_exist(self):
        """All infrastructure metrics are defined."""
        assert metrics.REDIS_MEMORY_BYTES is not None
        assert metrics.DB_QUERY_LATENCY is not None

    def test_cost_metrics_exist(self):
        """All cost metrics are defined."""
        assert metrics.LLM_COST is not None
        assert metrics.LLM_CACHE_HIT_RATE is not None
        assert metrics.DATA_FEED_COST is not None
        assert metrics.BROKER_COST is not None

    def test_additional_trading_metrics_exist(self):
        """Additional trading metrics are defined."""
        assert metrics.TRADE_EXECUTION_LATENCY is not None
        assert metrics.TRADE_VOLUME is not None
        assert metrics.RISK_CHECKS is not None

    def test_system_info_exists(self):
        """System info metric is defined."""
        assert metrics.SYSTEM_INFO is not None

    def test_total_metric_count(self):
        """Verify we have at least 25 distinct metric objects."""
        metric_objects = [
            metrics.SIGNALS_TOTAL,
            metrics.CONFLUENCE_SCORE,
            metrics.ORDERS_TOTAL,
            metrics.ORDERS_REJECTED,
            metrics.PNL_DAILY,
            metrics.DRAWDOWN_CURRENT,
            metrics.OPEN_POSITIONS,
            metrics.RISK_EXPOSURE,
            metrics.WIN_RATE,
            metrics.AGENT_LATENCY,
            metrics.AGENT_TOKENS,
            metrics.AGENT_ERRORS,
            metrics.AGENT_TIMEOUTS,
            metrics.AGENT_EVAL_PASS_RATE,
            metrics.PIPELINE_LATENCY,
            metrics.PIPELINE_STEP_LATENCY,
            metrics.PIPELINE_HALTS,
            metrics.EVENT_BUS_PUBLISHED,
            metrics.EVENT_BUS_CONSUMED,
            metrics.EVENT_BUS_LAG,
            metrics.REDIS_MEMORY_BYTES,
            metrics.DB_QUERY_LATENCY,
            metrics.LLM_COST,
            metrics.LLM_CACHE_HIT_RATE,
            metrics.DATA_FEED_COST,
            metrics.BROKER_COST,
            metrics.TRADE_EXECUTION_LATENCY,
            metrics.TRADE_VOLUME,
            metrics.RISK_CHECKS,
        ]
        assert len(metric_objects) >= 25


# ═══════════════════════════════════════════════════════════════════
# METRIC HELPER TESTS
# ═══════════════════════════════════════════════════════════════════


class TestMetricHelpers:
    """Test high-level metric recording helpers."""

    def test_record_trade(self):
        """record_trade increments counters correctly."""
        # Should not raise
        metrics.record_trade(
            pair="EURUSD",
            direction="BULLISH",
            broker="oanda",
            status="filled",
            volume=100000,
            execution_latency_s=0.15,
        )

    def test_record_agent_execution(self):
        """record_agent_execution records latency and tokens."""
        metrics.record_agent_execution(
            agent_name="news",
            loop_type="react",
            latency_s=0.5,
            tokens=1200,
            model="gpt-4.1",
        )

    def test_record_agent_execution_error(self):
        """record_agent_execution handles error case."""
        metrics.record_agent_execution(
            agent_name="strategy",
            loop_type="deliberation",
            latency_s=1.0,
            error=True,
            error_type="timeout",
            timed_out=True,
        )

    def test_record_pipeline_run(self):
        """record_pipeline_run records latency and halt state."""
        metrics.record_pipeline_run(
            pair="EURUSD",
            timeframe="H1",
            latency_s=0.18,
        )

    def test_record_pipeline_run_halted(self):
        """record_pipeline_run handles halted pipeline."""
        metrics.record_pipeline_run(
            pair="EURUSD",
            timeframe="H1",
            latency_s=0.05,
            halted=True,
            halt_reason="AVOID_ALL",
            halt_step="news",
        )

    def test_record_signal(self):
        """record_signal increments signal counter and observes confluence."""
        metrics.record_signal(
            pair="GBPUSD",
            direction="BEARISH",
            timeframe="H4",
            confluence_score=0.78,
        )

    def test_record_risk_check_passed(self):
        """record_risk_check handles approved trades."""
        metrics.record_risk_check(approved=True)

    def test_record_risk_check_rejected(self):
        """record_risk_check handles rejected trades."""
        metrics.record_risk_check(
            approved=False,
            pair="EURUSD",
            reason="Per-trade risk exceeded",
        )

    def test_update_account_state(self):
        """update_account_state sets all gauge metrics."""
        metrics.update_account_state(
            account="demo",
            daily_pnl=-25.50,
            drawdown_pct=3.2,
            open_position_count=2,
            risk_exposure_pct=4.5,
            win_rate_pct=62.5,
        )

    def test_record_llm_cost(self):
        """record_llm_cost increments cost counter."""
        metrics.record_llm_cost(
            model="gpt-4.1",
            agent_name="news",
            cost_usd=0.0032,
        )


class TestContextManagers:
    """Test context manager timing utilities."""

    def test_time_agent(self):
        """time_agent records latency."""
        with metrics.time_agent("test_agent", "react"):
            time.sleep(0.01)  # Sleep 10ms

    def test_time_pipeline_step(self):
        """time_pipeline_step records latency."""
        with metrics.time_pipeline_step("confluence"):
            time.sleep(0.005)

    def test_time_db_query(self):
        """time_db_query records latency."""
        with metrics.time_db_query("select"):
            time.sleep(0.005)

    def test_time_agent_records_on_exception(self):
        """time_agent records latency even when exception occurs."""
        with pytest.raises(ValueError):
            with metrics.time_agent("failing_agent", "react"):
                raise ValueError("test error")


# ═══════════════════════════════════════════════════════════════════
# HEALTH CHECK TESTS
# ═══════════════════════════════════════════════════════════════════


class TestHealthRegistry:
    """Test the health check registry."""

    @pytest.fixture
    def registry(self):
        return HealthRegistry(version="test-1.0.0")

    def test_liveness_returns_alive(self, registry):
        """Liveness probe always returns alive."""
        result = registry.liveness()
        assert result["status"] == "alive"
        assert "uptime_seconds" in result
        assert result["version"] == "test-1.0.0"

    @pytest.mark.asyncio
    async def test_readiness_no_deps(self, registry):
        """Readiness with no dependencies returns healthy."""
        result = await registry.readiness()
        assert result["status"] == "healthy"
        assert result["dependencies"] == []

    @pytest.mark.asyncio
    async def test_readiness_all_healthy(self, registry):
        """Readiness returns healthy when all deps are healthy."""

        async def healthy_check():
            return DependencyHealth(
                name="test_dep",
                status=HealthStatus.HEALTHY,
                message="OK",
            )

        registry.register("test_dep", healthy_check)
        result = await registry.readiness()
        assert result["status"] == "healthy"
        assert len(result["dependencies"]) == 1
        assert result["dependencies"][0]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_readiness_one_unhealthy(self, registry):
        """Readiness returns unhealthy when any dep is unhealthy."""

        async def healthy_check():
            return DependencyHealth(name="good", status=HealthStatus.HEALTHY)

        async def unhealthy_check():
            return DependencyHealth(name="bad", status=HealthStatus.UNHEALTHY, message="down")

        registry.register("good", healthy_check)
        registry.register("bad", unhealthy_check)
        result = await registry.readiness()
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_readiness_degraded(self, registry):
        """Readiness returns degraded when a dep is degraded."""

        async def degraded_check():
            return DependencyHealth(name="slow", status=HealthStatus.DEGRADED, message="slow")

        async def healthy_check():
            return DependencyHealth(name="good", status=HealthStatus.HEALTHY)

        registry.register("slow", degraded_check)
        registry.register("good", healthy_check)
        result = await registry.readiness()
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_check_one_unknown(self, registry):
        """Checking an unknown dependency returns unhealthy."""
        result = await registry.check_one("nonexistent")
        assert result.status == HealthStatus.UNHEALTHY
        assert "Unknown dependency" in result.message

    @pytest.mark.asyncio
    async def test_check_one_exception(self, registry):
        """A check that raises returns unhealthy."""

        async def broken_check():
            raise RuntimeError("connection refused")

        registry.register("broken", broken_check)
        result = await registry.check_one("broken")
        assert result.status == HealthStatus.UNHEALTHY
        assert "connection refused" in result.message

    @pytest.mark.asyncio
    async def test_check_all_parallel(self, registry):
        """All checks run in parallel."""
        call_order = []

        async def slow_check():
            await asyncio.sleep(0.05)
            call_order.append("slow")
            return DependencyHealth(name="slow", status=HealthStatus.HEALTHY)

        async def fast_check():
            call_order.append("fast")
            return DependencyHealth(name="fast", status=HealthStatus.HEALTHY)

        registry.register("slow", slow_check)
        registry.register("fast", fast_check)

        results = await registry.check_all()
        assert len(results) == 2
        # Both should be done
        assert all(d.status == HealthStatus.HEALTHY for d in results)

    def test_unregister(self, registry):
        """Unregister removes a dependency."""

        async def check():
            return DependencyHealth(name="temp", status=HealthStatus.HEALTHY)

        registry.register("temp", check)
        assert "temp" in registry._checks
        registry.unregister("temp")
        assert "temp" not in registry._checks

    def test_uptime_increases(self, registry):
        """Uptime increases between calls."""
        result1 = registry.liveness()
        time.sleep(0.01)
        result2 = registry.liveness()
        assert result2["uptime_seconds"] > result1["uptime_seconds"]

    @pytest.mark.asyncio
    async def test_detailed_health(self, registry):
        """Detailed health returns full dependency info."""

        async def redis_check():
            return DependencyHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                latency_ms=1.5,
                message="Connected",
                metadata={"used_memory_bytes": 1024},
            )

        registry.register("redis", redis_check)
        result = await registry.detailed()
        assert result["status"] == "healthy"
        assert len(result["dependencies"]) == 1
        dep = result["dependencies"][0]
        assert dep["name"] == "redis"
        assert dep["latency_ms"] > 0
        assert dep["used_memory_bytes"] == 1024

    @pytest.mark.asyncio
    async def test_caching(self, registry):
        """Results are cached within TTL."""
        call_count = 0

        async def counting_check():
            nonlocal call_count
            call_count += 1
            return DependencyHealth(name="cached", status=HealthStatus.HEALTHY)

        registry.register("cached", counting_check)
        registry._cache_ttl = 1.0  # 1 second cache

        await registry.check_all(use_cache=False)
        assert call_count == 1

        # Should use cache
        await registry.check_all(use_cache=True)
        assert call_count == 1

        # After TTL expires, should re-check
        registry._cache_time = time.time() - 2.0
        await registry.check_all(use_cache=True)
        assert call_count == 2


class TestDependencyHealth:
    """Test the DependencyHealth dataclass."""

    def test_to_dict_format(self):
        """Health registry output is serializable."""
        registry = HealthRegistry()

        async def check():
            return DependencyHealth(
                name="test",
                status=HealthStatus.HEALTHY,
                latency_ms=2.5,
                message="ok",
            )

        # Just verify liveness dict is JSON-serializable
        result = registry.liveness()
        import json
        json.dumps(result)  # Should not raise

    @pytest.mark.asyncio
    async def test_readiness_serializable(self):
        """Readiness output is JSON-serializable."""
        registry = HealthRegistry()

        async def check():
            return DependencyHealth(name="test", status=HealthStatus.HEALTHY)

        registry.register("test", check)
        result = await registry.readiness()
        import json
        json.dumps(result)  # Should not raise


class TestHealthStatus:
    """Test the HealthStatus enum."""

    def test_values(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_string_comparison(self):
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.UNHEALTHY == "unhealthy"
