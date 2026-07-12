"""Main pipeline orchestrator — runs the 16-step AlphaStack pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from alphastack.strategy.context import AlphaStackContext
from alphastack.strategy.steps.base import AlphaStackStep
from alphastack.strategy.steps.s01_fundamental import FundamentalIntelligence
from alphastack.strategy.steps.s02_bias import MarketBiasStep
from alphastack.strategy.steps.s03_session import SessionAnalysis
from alphastack.strategy.steps.s04_structure import MarketStructure
from alphastack.strategy.steps.s05_support_resistance import SupportResistance
from alphastack.strategy.steps.s06_liquidity import LiquidityDetection
from alphastack.strategy.steps.s07_smc import SmartMoneyConcepts
from alphastack.strategy.steps.s08_rsi import RSIConfirmation
from alphastack.strategy.steps.s09_candlestick import CandlestickConfirmation
from alphastack.strategy.steps.s10_confluence import ConfluenceEngine
from alphastack.strategy.steps.s11_sizing import PositionSizingStep
from alphastack.strategy.steps.s12_stop_loss import StopLossStep
from alphastack.strategy.steps.s13_take_profit import TakeProfitStep
from alphastack.strategy.steps.s14_management import TradeManagementStep
from alphastack.strategy.steps.s15_exit import ExitConditions
from alphastack.strategy.steps.s16_journal import TradeJournal

logger = logging.getLogger("alphastack.pipeline")

# Type alias for event callbacks
PipelineEvent = Callable[[int, str, AlphaStackContext], None]


class AlphaStackPipeline:
    """Runs the 16-step AlphaStack strategy pipeline sequentially.

    Steps 5–9 (S/R, liquidity, SMC, RSI, candlestick) are **parallelisable**
    because they only read from earlier outputs and write independent fields.
    Pass ``parallel=True`` to the constructor to enable this.

    Events
    ------
    Register callbacks via :meth:`on_step` to receive ``(step_number,
    step_name, context)`` after each step completes.
    """

    def __init__(self, *, parallel: bool = False) -> None:
        self.parallel = parallel
        self._listeners: list[PipelineEvent] = []

        # Ordered step instances
        self._steps: list[AlphaStackStep] = [
            FundamentalIntelligence(),   # 01
            MarketBiasStep(),            # 02
            SessionAnalysis(),           # 03
            MarketStructure(),           # 04
            SupportResistance(),         # 05  ─┐
            LiquidityDetection(),        # 06  ─┤ parallel group
            SmartMoneyConcepts(),        # 07  ─┤
            RSIConfirmation(),           # 08  ─┤
            CandlestickConfirmation(),   # 09  ─┘
            ConfluenceEngine(),          # 10
            PositionSizingStep(),        # 11
            StopLossStep(),              # 12
            TakeProfitStep(),            # 13
            TradeManagementStep(),       # 14
            ExitConditions(),            # 15
            TradeJournal(),              # 16
        ]

    # ------------------------------------------------------------------
    # Event system
    # ------------------------------------------------------------------

    def on_step(self, callback: PipelineEvent) -> None:
        """Register a listener called after every step completes."""
        self._listeners.append(callback)

    def _emit(self, step_number: int, step_name: str, ctx: AlphaStackContext) -> None:
        for cb in self._listeners:
            try:
                cb(step_number, step_name, ctx)
            except Exception:
                logger.warning("Event listener raised during step %02d", step_number, exc_info=True)

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    async def run(self, context: AlphaStackContext) -> AlphaStackContext:
        """Execute the full pipeline and return the final context."""
        logger.info("═══ AlphaStack pipeline started for %s ═══", context.symbol)
        ctx = context

        # Steps 1-4 (sequential)
        for step in self._steps[:4]:
            ctx = await step.run(ctx)
            self._emit(step.step_number, step.step_name, ctx)

        # Steps 5-9 (parallel or sequential)
        if self.parallel:
            ctx = await self._run_parallel_group(ctx, self._steps[4:9])
        else:
            for step in self._steps[4:9]:
                ctx = await step.run(ctx)
                self._emit(step.step_number, step.step_name, ctx)

        # Steps 10-16 (sequential)
        for step in self._steps[9:]:
            ctx = await step.run(ctx)
            self._emit(step.step_number, step.step_name, ctx)

        logger.info("═══ AlphaStack pipeline finished ═══")
        return ctx

    async def _run_parallel_group(
        self,
        context: AlphaStackContext,
        steps: list[AlphaStackStep],
    ) -> AlphaStackContext:
        """Run steps 5-9 concurrently; merge their outputs back."""
        logger.info("Running steps %s in parallel", [s.step_number for s in steps])

        results = await asyncio.gather(
            *(step.run(context) for step in steps),
            return_exceptions=True,
        )

        # Merge each step's output into the running context
        ctx = context
        for step, result in zip(steps, results):
            if isinstance(result, BaseException):
                logger.error("Parallel step %02d failed: %s", step.step_number, result)
                raise result
            # Each result context has exactly one new field set — merge it
            ctx = self._merge_context(ctx, result)
            self._emit(step.step_number, step.step_name, ctx)

        return ctx

    @staticmethod
    def _merge_context(base: AlphaStackContext, update: AlphaStackContext) -> AlphaStackContext:
        """Merge only the fields that *update* changed from *base*."""
        merged = {}
        for field_name in base.model_fields:
            base_val = getattr(base, field_name)
            update_val = getattr(update, field_name)
            if base_val != update_val:
                merged[field_name] = update_val
        return base.update(**merged)
