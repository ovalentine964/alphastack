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


class TestAlphaStackContext:
    """Tests for the strategy context model."""

    def test_context_creation(self) -> None:
        ctx = AlphaStackContext(
            symbol="EUR/USD",
            timeframe="1h",
            current_price=1.1050,
            timestamp=datetime.now(timezone.utc),
        )
        assert ctx.symbol == "EUR/USD"
        assert ctx.timeframe == "1h"
        assert ctx.current_price == 1.1050

    def test_context_defaults(self) -> None:
        ctx = AlphaStackContext()
        assert ctx.symbol == ""
        assert ctx.bias == Bias.NEUTRAL
        assert ctx.direction == Direction.NONE

    def test_context_is_pydantic_model(self) -> None:
        ctx = AlphaStackContext(symbol="GBP/USD")
        data = ctx.model_dump()
        assert "symbol" in data
        assert data["symbol"] == "GBP/USD"
