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

    # Forex pair metadata for pip-based scoring
    _FOREX_PIP_SIZES: dict[str, float] = {
        "EUR/USD": 0.0001, "GBP/USD": 0.0001, "AUD/USD": 0.0001,
        "NZD/USD": 0.0001, "USD/CHF": 0.0001, "USD/CAD": 0.0001,
        "EUR/GBP": 0.0001, "USD/JPY": 0.01, "EUR/JPY": 0.01,
        "GBP/JPY": 0.01,
    }

    # High-liquidity session windows (UTC hours)
    _LIQUID_SESSIONS: dict[str, tuple[int, int]] = {
        "london": (7, 16),
        "new_york": (12, 21),
        "overlap": (12, 16),  # London-NY overlap — best liquidity
    }

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

    def _is_forex_symbol(self, symbol: str) -> bool:
        """Check if the symbol is a forex pair."""
        return symbol in self._FOREX_PIP_SIZES or "/" in symbol and len(symbol) == 7 and symbol[3] == "/"

    def _get_pip_size(self, symbol: str) -> float:
        """Get pip size for a symbol. Returns 1.0 for crypto."""
        return self._FOREX_PIP_SIZES.get(symbol, 1.0)

    def _get_session_quality(self) -> tuple[str, float]:
        """Get current session name and a quality multiplier (0.0–1.0).

        Overlap sessions get highest quality, offline gets zero.
        """
        from datetime import datetime, timezone
        hour = datetime.now(timezone.utc).hour

        # London-NY overlap — best liquidity
        if 12 <= hour < 16:
            return "overlap", 1.0
        # London session
        if 7 <= hour < 12:
            return "london", 0.9
        # NY session
        if 16 <= hour < 21:
            return "new_york", 0.8
        # Asian session
        if 0 <= hour < 7 or hour >= 22:
            return "asian", 0.5
        return "off_hours", 0.3

    def _pip_based_confluence_adjustment(
        self,
        confluence: float,
        symbol: str,
        market_data: dict[str, Any],
    ) -> float:
        """Adjust confluence score based on forex-specific factors.

        - Session quality: liquid sessions boost score
        - Spread quality: tight spreads boost score
        - ATR in pips: reasonable volatility boosts score
        """
        if not self._is_forex_symbol(symbol):
            return confluence

        pip_size = self._get_pip_size(symbol)
        session_name, session_quality = self._get_session_quality()

        # Session adjustment: boost during liquid sessions
        session_mult = 0.7 + (0.3 * session_quality)

        # Spread adjustment: penalize wide spreads
        spread_pips = market_data.get("spread_pips", 0)
        if spread_pips > 0:
            # Good: < 2 pips, OK: 2-5 pips, bad: > 5 pips
            if spread_pips < 2.0:
                spread_mult = 1.0
            elif spread_pips < 5.0:
                spread_mult = 0.9
            else:
                spread_mult = 0.7
        else:
            spread_mult = 1.0

        # ATR sanity check: reasonable volatility for the pair
        atr_pips = market_data.get("atr_pips", 0)
        if atr_pips > 0:
            # Reasonable range: 10-100 pips for most pairs
            if 10 <= atr_pips <= 100:
                atr_mult = 1.0
            elif atr_pips < 10:
                atr_mult = 0.8  # Too quiet
            else:
                atr_mult = 0.85  # Too volatile
        else:
            atr_mult = 1.0

        adjusted = confluence * session_mult * spread_mult * atr_mult

        logger.info(
            "strategy_agent.forex_adjustment",
            symbol=symbol,
            session=session_name,
            original=round(confluence, 2),
            adjusted=round(adjusted, 2),
            session_mult=round(session_mult, 2),
            spread_mult=round(spread_mult, 2),
            atr_mult=round(atr_mult, 2),
        )
        return adjusted

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run the strategy pipeline and return generated signals."""
        symbol = state.get("current_symbol", "BTC/USDT")
        timeframe = state.get("current_timeframe", "1h")
        market_data = state.get("market_data", {})
        news_adjustment = state.get("news_risk_adjustment", 0.0)
        pipeline_context = state.get("pipeline_context", {})
        is_forex = self._is_forex_symbol(symbol)

        logger.info(
            "strategy_agent.analyse",
            symbol=symbol,
            timeframe=timeframe,
            has_market_data=bool(market_data),
            news_adjustment=news_adjustment,
            asset_type="forex" if is_forex else "crypto",
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
            confluence = pipeline_output.get("confluence", {}).get("score", 0.0)
            bias = pipeline_output.get("bias", {}).get("bias", "flat")

            # Apply forex-specific confluence adjustments
            if is_forex:
                confluence = self._pip_based_confluence_adjustment(
                    confluence, symbol, market_data,
                )

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

            # Forex requires higher threshold for signal generation
            min_threshold = 0.4 if is_forex else 0.3
            if adjusted_strength > min_threshold:
                # Compute forex-specific stop/take-profit in pips
                entry_price = pipeline_output.get("entry_price")
                stop_loss = pipeline_output.get("stop_loss")
                take_profit = pipeline_output.get("take_profit")
                sl_pips = None
                tp_pips = None
                if is_forex and entry_price and stop_loss:
                    pip_size = self._get_pip_size(symbol)
                    if pip_size > 0:
                        sl_pips = round(abs(entry_price - stop_loss) / pip_size, 1)
                        if take_profit:
                            tp_levels = take_profit if isinstance(take_profit, list) else [take_profit]
                            tp_pips = [round(abs(entry_price - tp) / pip_size, 1) for tp in tp_levels]

                signal = {
                    "id": uuid.uuid4().hex[:12],
                    "symbol": symbol,
                    "side": bias if bias in ("long", "short") else "flat",
                    "strength": adjusted_strength,
                    "confluence_score": confluence,
                    "timeframe": timeframe,
                    "strategy": "alphastack",
                    "asset_type": "forex" if is_forex else "crypto",
                    "reasoning": pipeline_output.get("reasoning", "Pipeline confluence signal"),
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "entry_price": entry_price,
                }
                # Add forex-specific fields
                if is_forex:
                    signal["pip_size"] = self._get_pip_size(symbol)
                    signal["sl_pips"] = sl_pips
                    signal["tp_pips"] = tp_pips
                    session_name, _ = self._get_session_quality()
                    signal["session"] = session_name

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
