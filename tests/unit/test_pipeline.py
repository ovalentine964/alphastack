"""Unit tests for the strategy pipeline."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from alphastack.strategy.context import AlphaStackContext, Bias, Direction, Session
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
