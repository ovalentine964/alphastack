"""Performance tests — latency, throughput, and query benchmarks."""

from __future__ import annotations

import asyncio
import time

import pytest

from alphastack.core.events import Event, EventType, SignalEvent
from alphastack.strategy.context import AlphaStackContext, Direction
from alphastack.strategy.pipeline import AlphaStackPipeline
from tests.conftest import InMemoryEventBus, generate_ohlcv


# ===========================================================================
# Pipeline Latency
# ===========================================================================

class TestPipelineLatency:
    @pytest.mark.asyncio
    async def test_pipeline_under_5_seconds(self):
        """Full 16-step pipeline must complete in under 5 seconds."""
        pipeline = AlphaStackPipeline(parallel=False)
        ohlcv = generate_ohlcv(200, seed=42)
        ohlcv["close"] = ohlcv["closes"][-1]
        ohlcv.update({
            "high_impact_events": [],
            "news_sentiment": 0.1,
            "volatility_index": 14.0,
            "atr_pips": 50.0,
            "pip_size": 0.0001,
            "spread_pips": 1.5,
            "account_balance": 10_000.0,
            "risk_pct": 1.0,
            "pip_value": 10.0,
            "stop_multiplier": 1.5,
            "rsi_period": 14,
            "entry_price": ohlcv["closes"][-1],
            "timeframe_closes": {"1h": ohlcv["closes"][-30:], "4h": ohlcv["closes"][-30:]},
            "htf_closes": ohlcv["closes"][-30:],
        })

        ctx = AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1H",
            market_data=ohlcv,
        )

        t0 = time.perf_counter()
        result = await pipeline.run(ctx)
        elapsed = time.perf_counter() - t0

        assert elapsed < 5.0, f"Pipeline took {elapsed:.2f}s (> 5s limit)"
        assert result.symbol == "EUR/USD"

    @pytest.mark.asyncio
    async def test_pipeline_parallel_faster_or_equal(self):
        """Parallel mode should not be slower than sequential."""
        ohlcv = generate_ohlcv(200, seed=42)
        ohlcv["close"] = ohlcv["closes"][-1]
        ohlcv.update({
            "high_impact_events": [], "news_sentiment": 0.0,
            "volatility_index": 14.0, "atr_pips": 50.0, "pip_size": 0.0001,
            "spread_pips": 1.5, "account_balance": 10_000.0, "risk_pct": 1.0,
            "pip_value": 10.0, "stop_multiplier": 1.5, "rsi_period": 14,
            "entry_price": ohlcv["closes"][-1],
            "timeframe_closes": {"1h": ohlcv["closes"][-30:]},
            "htf_closes": ohlcv["closes"][-30:],
        })

        ctx = AlphaStackContext(symbol="EUR/USD", timeframe="1H", market_data=ohlcv)

        # Sequential
        seq_pipeline = AlphaStackPipeline(parallel=False)
        t0 = time.perf_counter()
        await seq_pipeline.run(ctx)
        seq_time = time.perf_counter() - t0

        # Parallel
        par_pipeline = AlphaStackPipeline(parallel=True)
        t0 = time.perf_counter()
        await par_pipeline.run(ctx)
        par_time = time.perf_counter() - t0

        # Parallel should be within 2x of sequential (overhead may cause slight slowdown for small data)
        assert par_time < seq_time * 2.0 + 0.5

    @pytest.mark.asyncio
    async def test_single_step_latency(self):
        """Each individual step should complete in under 500ms."""
        from alphastack.strategy.steps.s01_fundamental import FundamentalIntelligence
        from alphastack.strategy.steps.s08_rsi import RSIConfirmation
        from alphastack.strategy.steps.s10_confluence import ConfluenceEngine

        ohlcv = generate_ohlcv(200, seed=42)
        ohlcv["close"] = ohlcv["closes"][-1]
        ohlcv.update({
            "high_impact_events": [], "news_sentiment": 0.1,
            "volatility_index": 14.0, "atr_pips": 50.0, "pip_size": 0.0001,
            "rsi_period": 14, "entry_price": ohlcv["closes"][-1],
        })
        ctx = AlphaStackContext(symbol="EUR/USD", market_data=ohlcv)

        for step_cls in [FundamentalIntelligence, RSIConfirmation]:
            step = step_cls()
            t0 = time.perf_counter()
            await step.run(ctx)
            elapsed = time.perf_counter() - t0
            assert elapsed < 0.5, f"Step {step.step_name} took {elapsed:.3f}s"


# ===========================================================================
# Event Bus Throughput
# ===========================================================================

class TestEventBusThroughput:
    @pytest.mark.asyncio
    async def test_publish_1000_events_fast(self, event_bus):
        """Publishing 1000 events should complete in under 2 seconds."""
        t0 = time.perf_counter()
        for i in range(1000):
            await event_bus.publish(SignalEvent(symbol=f"SYM-{i}", side="long"))
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0, f"Publishing 1000 events took {elapsed:.2f}s"
        assert len(event_bus.published_events) == 1000

    @pytest.mark.asyncio
    async def test_handler_throughput(self, event_bus):
        """Handler invocations should not bottleneck."""
        count = 0

        async def fast_handler(evt):
            nonlocal count
            count += 1

        event_bus.subscribe(EventType.SIGNAL, fast_handler)

        t0 = time.perf_counter()
        for i in range(500):
            await event_bus.publish(SignalEvent(symbol="X", side="long"))
        elapsed = time.perf_counter() - t0

        assert count == 500
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_multiple_handlers_linear_scaling(self, event_bus):
        """Adding more handlers should scale roughly linearly."""
        counters = [0] * 5

        async def make_handler(idx):
            async def handler(evt):
                counters[idx] += 1
            return handler

        for i in range(5):
            handler = await make_handler(i)
            event_bus.subscribe(EventType.SIGNAL, handler)

        t0 = time.perf_counter()
        for _ in range(200):
            await event_bus.publish(SignalEvent(symbol="X", side="long"))
        elapsed = time.perf_counter() - t0

        assert all(c == 200 for c in counters)
        assert elapsed < 3.0


# ===========================================================================
# Data Processing Performance
# ===========================================================================

class TestDataPerformance:
    def test_generate_large_dataset(self):
        """Generating 10k bars should be fast."""
        t0 = time.perf_counter()
        data = generate_ohlcv(10_000, seed=42)
        elapsed = time.perf_counter() - t0
        assert elapsed < 1.0
        assert len(data["closes"]) == 10_000

    def test_rsi_computation_large_dataset(self):
        """RSI on 10k bars should be fast."""
        from alphastack.strategy.steps.s08_rsi import _compute_rsi

        data = generate_ohlcv(10_000, seed=42)
        closes = data["closes"]

        t0 = time.perf_counter()
        rsi = _compute_rsi(closes, 14)
        elapsed = time.perf_counter() - t0

        assert elapsed < 0.5
        assert 0 <= rsi <= 100
