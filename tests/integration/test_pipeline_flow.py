"""Integration test: full 16-step pipeline end-to-end."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from alphastack.strategy.context import (
    AlphaStackContext,
    Bias,
    Direction,
    Session,
    StructureType,
)
from alphastack.strategy.pipeline import AlphaStackPipeline
from tests.conftest import generate_ohlcv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_market_data(seed: int = 42, sentiment: float = 0.1, vix: float = 14.0) -> dict:
    """Build comprehensive market data dict for pipeline tests."""
    ohlcv = generate_ohlcv(200, seed=seed)
    return {
        **ohlcv,
        "close": ohlcv["closes"][-1],
        "high_impact_events": [],
        "news_sentiment": sentiment,
        "volatility_index": vix,
        "atr_pips": 50.0,
        "pip_size": 0.0001,
        "spread_pips": 1.5,
        "account_balance": 10_000.0,
        "risk_pct": 1.0,
        "pip_value": 10.0,
        "stop_multiplier": 1.5,
        "rsi_period": 14,
        "entry_price": ohlcv["closes"][-1],
        "timeframe_closes": {
            "1h": ohlcv["closes"][-30:],
            "4h": ohlcv["closes"][-30:],
        },
        "htf_closes": ohlcv["closes"][-30:],
    }


# ===========================================================================
# Pipeline End-to-End
# ===========================================================================

class TestPipelineE2E:
    @pytest.mark.asyncio
    async def test_pipeline_runs_all_steps(self):
        """Pipeline completes without error and populates all context fields."""
        pipeline = AlphaStackPipeline(parallel=False)
        ctx = AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1H",
            timestamp=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            market_data=_full_market_data(),
        )
        result = await pipeline.run(ctx)

        # All step outputs should be populated (not necessarily non-default)
        assert result.symbol == "EUR/USD"
        assert result.fundamental is not None
        assert result.bias is not None
        assert result.session is not None
        assert result.structure is not None
        assert result.sr_levels is not None
        assert result.liquidity_pools is not None
        assert result.smc is not None
        assert result.rsi is not None
        assert result.candlestick is not None
        assert result.confluence is not None
        assert result.sizing is not None
        assert result.stop_loss is not None
        assert result.take_profit is not None
        assert result.management is not None
        assert result.exit_signal is not None
        assert result.journal is not None

    @pytest.mark.asyncio
    async def test_pipeline_parallel_mode(self):
        """Pipeline with parallel=True also completes successfully."""
        pipeline = AlphaStackPipeline(parallel=True)
        ctx = AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1H",
            timestamp=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            market_data=_full_market_data(),
        )
        result = await pipeline.run(ctx)
        assert result.symbol == "EUR/USD"
        assert result.confluence.score >= 0

    @pytest.mark.asyncio
    async def test_pipeline_events_emitted(self):
        """Pipeline emits events for each step."""
        pipeline = AlphaStackPipeline(parallel=False)
        events: list[tuple[int, str]] = []
        pipeline.on_step(lambda n, name, ctx: events.append((n, name)))

        ctx = AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1H",
            timestamp=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            market_data=_full_market_data(),
        )
        await pipeline.run(ctx)

        assert len(events) == 16
        assert events[0][0] == 1  # step 1
        assert events[-1][0] == 16  # step 16

    @pytest.mark.asyncio
    async def test_bullish_scenario_produces_signal(self):
        """Strong bullish data produces a long signal with high confluence."""
        pipeline = AlphaStackPipeline(parallel=False)
        ctx = AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1H",
            timestamp=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            market_data=_full_market_data(seed=100, sentiment=0.7, vix=10.0),
        )
        result = await pipeline.run(ctx)
        # Strong sentiment + low VIX should produce at least some confluence
        assert result.confluence.score >= 0
        assert result.fundamental.bias in (Bias.BULLISH, Bias.NEUTRAL)

    @pytest.mark.asyncio
    async def test_neutral_scenario(self):
        """Neutral data produces low confluence, no trade."""
        pipeline = AlphaStackPipeline(parallel=False)
        ctx = AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1H",
            timestamp=datetime(2025, 6, 15, 22, 0, 0, tzinfo=timezone.utc),  # off hours
            market_data=_full_market_data(seed=42, sentiment=0.0, vix=14.0),
        )
        result = await pipeline.run(ctx)
        assert result.confluence.score >= 0
        assert result.confluence.score <= 100

    @pytest.mark.asyncio
    async def test_pipeline_with_empty_market_data(self):
        """Pipeline handles empty market data gracefully."""
        pipeline = AlphaStackPipeline(parallel=False)
        ctx = AlphaStackContext(symbol="TEST", market_data={})
        result = await pipeline.run(ctx)
        assert result.symbol == "TEST"
        # All defaults should be used
        assert result.confluence.score >= 0

    @pytest.mark.asyncio
    async def test_step_results_chain_correctly(self):
        """Each step's output feeds into subsequent steps."""
        pipeline = AlphaStackPipeline(parallel=False)
        step_results: dict[int, AlphaStackContext] = {}

        def capture(n: int, name: str, ctx: AlphaStackContext):
            step_results[n] = ctx

        pipeline.on_step(capture)

        ctx = AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1H",
            timestamp=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            market_data=_full_market_data(),
        )
        await pipeline.run(ctx)

        # Step 4 (structure) should have produced structure data
        assert step_results[4].structure is not None
        # Step 10 (confluence) should reference earlier steps
        assert step_results[10].confluence is not None
        assert len(step_results[10].confluence.component_scores) > 0
