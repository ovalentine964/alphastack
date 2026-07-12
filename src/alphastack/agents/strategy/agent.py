"""Strategy Agent — runs the 16-step AlphaStack pipeline and generates signals.

This agent wraps the existing :class:`AlphaStackPipeline` and translates
its output into :class:`Signal` objects that the orchestrator can route
through the risk and execution agents.
"""

from __future__ import annotations

import uuid
from typing import Any

from alphastack.agents.base import AlphaStackAgent
from alphastack.core.events import EventBus
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


class StrategyAgent(AlphaStackAgent):
    """Analyses market conditions and generates trade signals.

    Responsibilities:
    - Run the 16-step AlphaStack strategy pipeline
    - Generate signals with confluence scores
    - Incorporate news risk adjustments into signal strength
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__(
            name="strategy",
            role="analyst",
            description="Runs the 16-step AlphaStack pipeline and generates trade signals",
            event_bus=event_bus,
        )

    def system_prompt(self) -> str:
        return (
            "You are the AlphaStack Strategy Agent. Your job is to:\n"
            "1. Run the 16-step trading pipeline on the provided market data\n"
            "2. Analyse market structure, bias, session, S/R, liquidity, SMC, RSI, candlesticks\n"
            "3. Compute confluence scores and generate actionable trade signals\n"
            "4. Factor in any news risk adjustments from the News Agent\n"
            "5. Output signals with clear reasoning, entry, SL, and TP levels\n"
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run the strategy pipeline and return generated signals."""
        symbol = state.get("current_symbol", "BTC/USDT")
        timeframe = state.get("current_timeframe", "1h")
        market_data = state.get("market_data", {})
        news_adjustment = state.get("news_risk_adjustment", 0.0)
        pipeline_context = state.get("pipeline_context", {})

        logger.info(
            "strategy_agent.analyse",
            symbol=symbol,
            timeframe=timeframe,
            has_market_data=bool(market_data),
            news_adjustment=news_adjustment,
        )

        signals = []

        # Attempt to run the full pipeline
        try:
            from alphastack.strategy.context import AlphaStackContext
            from alphastack.strategy.pipeline import AlphaStackPipeline

            # Build pipeline context from state
            ctx = AlphaStackContext(
                symbol=symbol,
                timeframe=timeframe,
                market_data=market_data,
            )

            pipeline = AlphaStackPipeline(parallel=True)
            ctx = await pipeline.run(ctx)

            # Extract pipeline output
            pipeline_output = ctx.model_dump() if hasattr(ctx, "model_dump") else {}

            # Generate signal from pipeline output
            confluence = pipeline_output.get("confluence_score", 0.0)
            bias = pipeline_output.get("bias", "flat")

            # Apply news risk adjustment (reduce signal strength on high-impact news)
            adjusted_strength = confluence
            if news_adjustment > 0:
                adjusted_strength = confluence * (1.0 - min(news_adjustment, 0.8))
                logger.info(
                    "strategy_agent.news_adjustment",
                    original=confluence,
                    adjusted=adjusted_strength,
                    factor=news_adjustment,
                )

            if adjusted_strength > 0.3:  # minimum threshold
                signal = {
                    "id": uuid.uuid4().hex[:12],
                    "symbol": symbol,
                    "side": bias if bias in ("long", "short") else "flat",
                    "strength": adjusted_strength,
                    "confluence_score": confluence,
                    "timeframe": timeframe,
                    "strategy": "alphastack",
                    "reasoning": pipeline_output.get("reasoning", "Pipeline confluence signal"),
                    "stop_loss": pipeline_output.get("stop_loss"),
                    "take_profit": pipeline_output.get("take_profit"),
                    "entry_price": pipeline_output.get("entry_price"),
                }
                signals.append(signal)

            pipeline_context = pipeline_output

        except ImportError:
            logger.warning("strategy_agent.pipeline_unavailable", exc_info=True)
            # Fallback: generate a placeholder based on market data
            if market_data:
                signals.append(self._generate_fallback_signal(symbol, timeframe, market_data))

        except Exception:
            logger.error("strategy_agent.pipeline_error", exc_info=True)
            signals.append(self._generate_fallback_signal(symbol, timeframe, market_data))

        return {
            "signals": signals,
            "pipeline_context": pipeline_context,
            "_confidence": max((s.get("confluence_score", 0) for s in signals), default=0.0),
        }

    @staticmethod
    def _generate_fallback_signal(
        symbol: str,
        timeframe: str,
        market_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a basic signal when the pipeline is unavailable."""
        return {
            "id": uuid.uuid4().hex[:12],
            "symbol": symbol,
            "side": "flat",
            "strength": 0.0,
            "confluence_score": 0.0,
            "timeframe": timeframe,
            "strategy": "alphastack_fallback",
            "reasoning": "Pipeline unavailable — no actionable signal generated",
            "stop_loss": None,
            "take_profit": None,
            "entry_price": None,
        }
