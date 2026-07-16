"""Unit tests for the strategy pipeline."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from alphastack.strategy.context import (
    AlphaStackContext,
    Bias,
    Direction,
    FundamentalData,
    MarketBias,
    Session,
    SessionData,
)
from alphastack.strategy.pipeline import AlphaStackPipeline
from alphastack.strategy.steps.base import AlphaStackStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class StubStep(AlphaStackStep):
    """A no-op step that records calls."""

    call_count = 0

    def __init__(self, step_number: int = 1, step_name: str = "stub") -> None:
        super().__init__()
        self.step_number = step_number
        self.step_name = step_name

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        StubStep.call_count += 1
        return context


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAlphaStackPipeline:
    """Tests for the 16-step pipeline orchestrator."""

    def test_pipeline_has_all_steps(self) -> None:
        pipeline = AlphaStackPipeline()
        assert len(pipeline._steps) == 16

    def test_pipeline_steps_are_ordered(self) -> None:
        pipeline = AlphaStackPipeline()
        for i, step in enumerate(pipeline._steps, start=1):
            assert step.step_number == i, f"Step {i} has wrong number: {step.step_number}"

    @pytest.mark.asyncio
    async def test_pipeline_runs_sequential(self, sample_context: AlphaStackContext) -> None:
        """Pipeline should execute all steps and return a context."""
        pipeline = AlphaStackPipeline(parallel=False)

        # Patch all steps to be stubs
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")

        StubStep.call_count = 0
        result = await pipeline.run(sample_context)
        assert StubStep.call_count == 16
        assert result is not None
        assert isinstance(result, AlphaStackContext)

    @pytest.mark.asyncio
    async def test_pipeline_emits_events(self, sample_context: AlphaStackContext) -> None:
        """Pipeline should call registered listeners after each step."""
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")

        events: list[tuple[int, str, AlphaStackContext]] = []
        pipeline.on_step(lambda sn, name, ctx: events.append((sn, name, ctx)))

        await pipeline.run(sample_context)
        assert len(events) == 16
        assert events[0][0] == 1  # first step number
        assert events[-1][0] == 16  # last step number

    @pytest.mark.asyncio
    async def test_pipeline_parallel_mode(self, sample_context: AlphaStackContext) -> None:
        """Parallel mode should still produce correct output."""
        pipeline = AlphaStackPipeline(parallel=True)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")

        result = await pipeline.run(sample_context)
        assert result is not None

    @pytest.mark.asyncio
    async def test_pipeline_step_failure_propagates(self, sample_context: AlphaStackContext) -> None:
        """A failing step should propagate the error."""
        pipeline = AlphaStackPipeline(parallel=False)

        class FailingStep(AlphaStackStep):
            step_number = 1
            step_name = "failing"

            async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
                raise ValueError("Step failed deliberately")

        pipeline._steps[0] = FailingStep()
        with pytest.raises(ValueError, match="deliberately"):
            await pipeline.run(sample_context)

    @pytest.mark.asyncio
    async def test_pipeline_returns_frozen_context(self, sample_context: AlphaStackContext) -> None:
        """Pipeline output must be a frozen (immutable) context."""
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")

        result = await pipeline.run(sample_context)
        assert result.model_config.get("frozen") is True

    @pytest.mark.asyncio
    async def test_pipeline_preserves_symbol(self, sample_context: AlphaStackContext) -> None:
        """Pipeline must carry the symbol through all steps."""
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")

        result = await pipeline.run(sample_context)
        assert result.symbol == sample_context.symbol

    @pytest.mark.asyncio
    async def test_pipeline_listener_error_does_not_break_run(
        self, sample_context: AlphaStackContext,
    ) -> None:
        """A misbehaving listener should not crash the pipeline."""
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")

        def bad_listener(sn: int, name: str, ctx: AlphaStackContext) -> None:
            raise RuntimeError("listener error")

        pipeline.on_step(bad_listener)
        result = await pipeline.run(sample_context)
        assert result is not None


class TestAlphaStackContext:
    """Tests for the strategy context model."""

    def test_context_creation(self) -> None:
        ctx = AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1h",
            timestamp=datetime.now(timezone.utc),
            market_data={"close": 1.1050},
        )
        assert ctx.symbol == "EUR/USD"
        assert ctx.timeframe == "1h"
        assert ctx.market_data["close"] == 1.1050

    def test_context_defaults(self) -> None:
        ctx = AlphaStackContext()
        assert ctx.symbol == ""
        assert ctx.bias.bias == Bias.NEUTRAL
        assert ctx.structure.direction == Direction.NONE

    def test_context_is_pydantic_model(self) -> None:
        ctx = AlphaStackContext(symbol="GBP/USD")
        data = ctx.model_dump()
        assert "symbol" in data
        assert data["symbol"] == "GBP/USD"

    def test_context_update_returns_new_instance(self) -> None:
        ctx = AlphaStackContext(symbol="EUR/USD")
        updated = ctx.update(symbol="GBP/USD")
        assert updated.symbol == "GBP/USD"
        assert ctx.symbol == "EUR/USD"  # original unchanged
        assert updated is not ctx

    def test_context_frozen(self) -> None:
        ctx = AlphaStackContext(symbol="EUR/USD")
        with pytest.raises(Exception):
            ctx.symbol = "GBP/USD"  # type: ignore[misc]

    def test_context_market_data_defaults_empty(self) -> None:
        ctx = AlphaStackContext()
        assert ctx.market_data == {}

    def test_context_sub_models_initialized(self) -> None:
        ctx = AlphaStackContext()
        # All sub-models should be initialized with defaults
        assert ctx.fundamental is not None
        assert ctx.bias is not None
        assert ctx.session is not None
        assert ctx.structure is not None
        assert ctx.sr_levels is not None
        assert ctx.smc is not None
        assert ctx.rsi is not None
        assert ctx.candlestick is not None
        assert ctx.confluence is not None
        assert ctx.sizing is not None
        assert ctx.stop_loss is not None
        assert ctx.take_profit is not None
        assert ctx.management is not None
        assert ctx.exit_signal is not None
        assert ctx.journal is not None

    def test_context_serialization_roundtrip(self) -> None:
        ctx = AlphaStackContext(
            symbol="BTC/USDT",
            timeframe="4H",
            market_data={"close": 67500.0},
        )
        data = ctx.model_dump()
        restored = AlphaStackContext.model_validate(data)
        assert restored.symbol == ctx.symbol
        assert restored.market_data["close"] == 67500.0


class TestPipelineStepBase:
    """Tests for the AlphaStackStep base class."""

    @pytest.mark.asyncio
    async def test_step_run_calls_execute(self) -> None:
        """run() should delegate to execute()."""

        class RecordingStep(AlphaStackStep):
            step_number = 1
            step_name = "recording"
            called = False

            async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
                RecordingStep.called = True
                return context

        step = RecordingStep()
        ctx = AlphaStackContext(symbol="EUR/USD")
        result = await step.run(ctx)
        assert RecordingStep.called is True
        assert result is not None

    @pytest.mark.asyncio
    async def test_step_run_propagates_exception(self) -> None:
        class BadStep(AlphaStackStep):
            step_number = 99
            step_name = "bad"

            async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
                raise RuntimeError("oops")

        step = BadStep()
        with pytest.raises(RuntimeError, match="oops"):
            await step.run(AlphaStackContext())


# ===========================================================================
# FOREX Pipeline Tests
# ===========================================================================

class TestForexPipeline:
    """Tests for pipeline behavior with forex-specific market data."""

    @pytest.fixture
    def eurusd_context(self) -> AlphaStackContext:
        """EUR/USD context with forex-specific market data fields."""
        from tests.conftest import generate_ohlcv
        ohlcv = generate_ohlcv(200, start_price=1.1000, volatility=0.0005, seed=77)
        return AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1H",
            timestamp=datetime(2025, 6, 16, 13, 0, 0, tzinfo=timezone.utc),  # London-NY overlap
            market_data={
                **ohlcv,
                "close": ohlcv["closes"][-1],
                "high_impact_events": [],
                "news_sentiment": 0.2,
                "volatility_index": 12.0,
                "atr_pips": 45.0,
                "pip_size": 0.0001,
                "spread_pips": 1.2,
                "account_balance": 10_000.0,
                "risk_pct": 1.0,
                "pip_value": 10.0,
                "stop_multiplier": 1.5,
                "rsi_period": 14,
                # Forex-specific fields
                "swap_long": -0.50,         # $/day per lot
                "swap_short": 0.30,
                "margin_required": 1_100.0,
                "leverage": 100,
                "pair_type": "major",
                "session": "london_ny_overlap",
                "contract_size": 100_000,
            },
        )

    @pytest.fixture
    def usdjpy_context(self) -> AlphaStackContext:
        """USD/JPY context with JPY-pair specifics."""
        from tests.conftest import generate_ohlcv
        ohlcv = generate_ohlcv(200, start_price=150.00, volatility=0.10, seed=88)
        return AlphaStackContext(
            symbol="USD/JPY",
            timeframe="1H",
            timestamp=datetime(2025, 6, 16, 3, 0, 0, tzinfo=timezone.utc),  # Tokyo session
            market_data={
                **ohlcv,
                "close": ohlcv["closes"][-1],
                "high_impact_events": [],
                "news_sentiment": 0.0,
                "volatility_index": 10.0,
                "atr_pips": 30.0,
                "pip_size": 0.01,               # JPY pairs use 0.01
                "spread_pips": 1.5,
                "account_balance": 5_000.0,
                "risk_pct": 2.0,
                "pip_value": 6.67,              # ~$6.67 per pip per lot
                "stop_multiplier": 1.5,
                "rsi_period": 14,
                "swap_long": 0.80,
                "swap_short": -1.20,
                "margin_required": 1_500.0,
                "leverage": 100,
                "pair_type": "major",
                "session": "tokyo",
                "contract_size": 100_000,
            },
        )

    @pytest.fixture
    def gbpjpy_context(self) -> AlphaStackContext:
        """GBP/JPY — volatile cross pair."""
        from tests.conftest import generate_ohlcv
        ohlcv = generate_ohlcv(200, start_price=190.00, volatility=0.15, seed=99)
        return AlphaStackContext(
            symbol="GBP/JPY",
            timeframe="4H",
            timestamp=datetime(2025, 6, 16, 14, 0, 0, tzinfo=timezone.utc),
            market_data={
                **ohlcv,
                "close": ohlcv["closes"][-1],
                "high_impact_events": [],
                "news_sentiment": -0.1,
                "volatility_index": 18.0,
                "atr_pips": 60.0,
                "pip_size": 0.01,
                "spread_pips": 3.0,
                "account_balance": 25_000.0,
                "risk_pct": 0.5,
                "pip_value": 6.67,
                "stop_multiplier": 2.0,
                "rsi_period": 14,
                "swap_long": -0.90,
                "swap_short": 0.40,
                "margin_required": 2_500.0,
                "leverage": 50,
                "pair_type": "minor",
                "session": "london",
                "contract_size": 100_000,
            },
        )

    @pytest.mark.asyncio
    async def test_pipeline_runs_with_eurusd_data(self, eurusd_context: AlphaStackContext) -> None:
        """Pipeline should complete with EUR/USD forex data (using stubs)."""
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")
        result = await pipeline.run(eurusd_context)
        assert result is not None
        assert result.symbol == "EUR/USD"
        assert result.market_data["pip_size"] == pytest.approx(0.0001)
        assert result.market_data["spread_pips"] == pytest.approx(1.2)

    @pytest.mark.asyncio
    async def test_pipeline_runs_with_usdjpy_data(self, usdjpy_context: AlphaStackContext) -> None:
        """Pipeline should complete with USD/JPY data (different pip size)."""
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")
        result = await pipeline.run(usdjpy_context)
        assert result is not None
        assert result.symbol == "USD/JPY"
        assert result.market_data["pip_size"] == pytest.approx(0.01)

    @pytest.mark.asyncio
    async def test_pipeline_runs_with_cross_pair(self, gbpjpy_context: AlphaStackContext) -> None:
        """Pipeline should handle volatile cross pairs like GBP/JPY."""
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")
        result = await pipeline.run(gbpjpy_context)
        assert result is not None
        assert result.symbol == "GBP/JPY"

    @pytest.mark.asyncio
    async def test_pipeline_preserves_forex_market_data(self, eurusd_context: AlphaStackContext) -> None:
        """Forex-specific market data should survive the full pipeline."""
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")
        result = await pipeline.run(eurusd_context)
        md = result.market_data
        # Original forex fields preserved
        assert md.get("pip_size") == pytest.approx(0.0001)
        assert md.get("contract_size") == 100_000
        assert md.get("leverage") == 100
        assert md.get("pair_type") == "major"

    @pytest.mark.asyncio
    async def test_pipeline_parallel_with_forex_data(self, eurusd_context: AlphaStackContext) -> None:
        """Parallel mode should work with forex data (steps 5-9)."""
        pipeline = AlphaStackPipeline(parallel=True)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")
        result = await pipeline.run(eurusd_context)
        assert result is not None
        assert result.symbol == "EUR/USD"

    @pytest.mark.asyncio
    async def test_pipeline_signal_generation_eurusd(self, eurusd_context: AlphaStackContext) -> None:
        """Pipeline should produce a valid context for signal generation."""
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")
        result = await pipeline.run(eurusd_context)
        # Context should have all sub-models populated
        assert result.bias is not None
        assert result.structure is not None
        assert result.confluence is not None
        assert result.stop_loss is not None
        assert result.take_profit is not None
        assert result.sizing is not None

    @pytest.mark.asyncio
    async def test_pipeline_with_bullish_forex_context(self) -> None:
        """Pipeline with strong bullish forex signals should preserve bias."""
        from tests.conftest import generate_ohlcv
        ohlcv = generate_ohlcv(200, start_price=1.1000, volatility=0.0005, seed=42)
        ctx = AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1H",
            timestamp=datetime(2025, 6, 16, 13, 0, 0, tzinfo=timezone.utc),
            market_data={
                **ohlcv,
                "close": ohlcv["closes"][-1],
                "high_impact_events": [],
                "news_sentiment": 0.5,
                "volatility_index": 12.0,
                "atr_pips": 40.0,
                "pip_size": 0.0001,
                "spread_pips": 1.0,
                "account_balance": 10_000.0,
                "risk_pct": 1.0,
                "pip_value": 10.0,
                "stop_multiplier": 1.5,
                "rsi_period": 14,
            },
            fundamental=FundamentalData(bias=Bias.BULLISH, news_sentiment=0.5, macro_regime="risk_on"),
            bias=MarketBias(bias=Bias.BULLISH, trend_strength=0.75, htf_bias=Bias.BULLISH),
            session=SessionData(active=Session.LONDON, volatility=1.0, typical_range_pips=50.0),
        )
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")
        result = await pipeline.run(ctx)
        assert result is not None
        # Bullish context should preserve bias through pipeline
        assert result.fundamental.bias == Bias.BULLISH
        assert result.bias.bias == Bias.BULLISH

    @pytest.mark.asyncio
    async def test_pipeline_step_events_for_forex(self, eurusd_context: AlphaStackContext) -> None:
        """All 16 steps should emit events when processing forex data."""
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")
        events: list[tuple[int, str]] = []
        pipeline.on_step(lambda sn, name, ctx: events.append((sn, name)))
        await pipeline.run(eurusd_context)
        assert len(events) == 16
        # Check step names are present
        step_names = [name for _, name in events]
        assert len(step_names) == 16

    @pytest.mark.asyncio
    async def test_pipeline_forex_with_no_market_data(self) -> None:
        """Pipeline should handle forex context with minimal market data."""
        ctx = AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1H",
            timestamp=datetime(2025, 6, 16, 12, 0, 0, tzinfo=timezone.utc),
            market_data={"pip_size": 0.0001},
        )
        pipeline = AlphaStackPipeline(parallel=False)
        for i in range(len(pipeline._steps)):
            pipeline._steps[i] = StubStep(step_number=i + 1, step_name=f"stub_{i+1}")
        # Should not crash even with minimal data
        result = await pipeline.run(ctx)
        assert result is not None
        assert result.symbol == "EUR/USD"
