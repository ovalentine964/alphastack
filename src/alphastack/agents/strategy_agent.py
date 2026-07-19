"""Strategy Agent — real implementation with pipeline integration.

Regime-aware strategy selection using the existing AlphaStackPipeline.
Handles multiple asset classes (forex, crypto) with session-aware
confluence scoring and news risk integration.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from alphastack.agents.base import AlphaStackAgent
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Market Regime
# ---------------------------------------------------------------------------

class MarketRegime(str, Enum):
    """Detected market regime — drives strategy selection."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    LOW_VOLATILITY = "low_volatility"
    UNKNOWN = "unknown"


# Regime → strategy weight map
REGIME_STRATEGY_WEIGHTS: dict[MarketRegime, dict[str, float]] = {
    MarketRegime.TRENDING_UP: {
        "trend_following": 1.2,
        "breakout": 1.1,
        "mean_reversion": 0.6,
        "smc": 1.0,
    },
    MarketRegime.TRENDING_DOWN: {
        "trend_following": 1.2,
        "breakout": 1.1,
        "mean_reversion": 0.6,
        "smc": 1.0,
    },
    MarketRegime.RANGING: {
        "trend_following": 0.5,
        "breakout": 0.7,
        "mean_reversion": 1.3,
        "smc": 0.9,
    },
    MarketRegime.VOLATILE: {
        "trend_following": 0.7,
        "breakout": 1.2,
        "mean_reversion": 0.8,
        "smc": 1.1,
    },
    MarketRegime.LOW_VOLATILITY: {
        "trend_following": 0.8,
        "breakout": 0.5,
        "mean_reversion": 1.1,
        "smc": 0.7,
    },
    MarketRegime.UNKNOWN: {
        "trend_following": 1.0,
        "breakout": 1.0,
        "mean_reversion": 1.0,
        "smc": 1.0,
    },
}


# ---------------------------------------------------------------------------
# Session metadata
# ---------------------------------------------------------------------------

_FOREX_PIP_SIZES: dict[str, float] = {
    "EUR/USD": 0.0001, "GBP/USD": 0.0001, "AUD/USD": 0.0001,
    "NZD/USD": 0.0001, "USD/CHF": 0.0001, "USD/CAD": 0.0001,
    "EUR/GBP": 0.0001, "USD/JPY": 0.01, "EUR/JPY": 0.01,
    "GBP/JPY": 0.01,
}


# ---------------------------------------------------------------------------
# Strategy Agent
# ---------------------------------------------------------------------------

class StrategyAgent(AlphaStackAgent):
    """Analyses market conditions and generates trade signals.

    Upgraded v2.0 features:
    - Regime-aware strategy selection (weights adjusted by detected regime)
    - Uses ai/pipeline.py for signal generation (real implementation)
    - Session-aware confluence scoring
    - News risk integration from upstream NewsAgent
    - Multi-timeframe awareness
    """

    def __init__(self, event_bus: Any | None = None) -> None:
        super().__init__(
            name="strategy",
            role="analyst",
            description="Runs the AlphaStack pipeline with regime-aware strategy selection",
            event_bus=event_bus,
            timeout=45.0,  # pipeline can be slow
            max_retries=2,
            cb_failure_threshold=3,
        )
        self._pipeline_cache: dict[str, Any] = {}

    def system_prompt(self) -> str:
        return (
            "You are the AlphaStack Strategy Agent. Your job is to:\n"
            "1. Detect the current market regime (trending, ranging, volatile, low-vol)\n"
            "2. Run the AlphaStack strategy pipeline with regime-adjusted weights\n"
            "3. Generate signals with confluence scores adjusted for session and regime\n"
            "4. Factor in news risk adjustments from the News Agent\n"
            "5. Output signals with clear reasoning, entry, SL, and TP levels\n"
        )

    # ------------------------------------------------------------------
    # Regime detection
    # ------------------------------------------------------------------

    def _detect_regime(self, market_data: dict[str, Any]) -> MarketRegime:
        """Detect market regime from available indicators.

        Uses ATR, ADX, and Bollinger Band width as regime proxies.
        Falls back to UNKNOWN if data is insufficient.
        """
        atr = market_data.get("atr", 0.0)
        atr_pct = market_data.get("atr_pct", 0.0)
        adx = market_data.get("adx", 0.0)
        bb_width = market_data.get("bb_width", 0.0)
        closes = market_data.get("closes", [])
        sma_20 = market_data.get("sma_20", [])
        sma_50 = market_data.get("sma_50", [])

        # ADX-based trend detection (if available)
        if adx > 0:
            if adx > 25:
                # Trending — check direction
                if len(closes) >= 2 and len(sma_20) >= 1:
                    last_close = closes[-1] if isinstance(closes, list) else closes
                    sma_val = sma_20[-1] if isinstance(sma_20, list) else sma_20
                    if last_close > sma_val:
                        return MarketRegime.TRENDING_UP
                    else:
                        return MarketRegime.TRENDING_DOWN
                return MarketRegime.TRENDING_UP  # default for strong ADX
            elif adx < 15:
                # Low ADX → ranging or low vol
                if bb_width and bb_width < 0.02:
                    return MarketRegime.LOW_VOLATILITY
                return MarketRegime.RANGING

        # ATR-based volatility detection
        if atr_pct > 0:
            if atr_pct > 2.0:
                return MarketRegime.VOLATILE
            elif atr_pct < 0.5:
                return MarketRegime.LOW_VOLATILITY

        # SMA crossover detection
        if len(sma_20) >= 2 and len(sma_50) >= 2:
            sma20_now = sma_20[-1] if isinstance(sma_20, list) else sma_20
            sma50_now = sma_50[-1] if isinstance(sma_50, list) else sma_50
            sma20_prev = sma_20[-2] if isinstance(sma_20, list) and len(sma_20) > 1 else sma20_now
            sma50_prev = sma_50[-2] if isinstance(sma_50, list) and len(sma_50) > 1 else sma50_now

            if sma20_now > sma50_now and sma20_prev <= sma50_prev:
                return MarketRegime.TRENDING_UP
            elif sma20_now < sma50_now and sma20_prev >= sma50_prev:
                return MarketRegime.TRENDING_DOWN
            elif sma20_now > sma50_now:
                return MarketRegime.TRENDING_UP
            elif sma20_now < sma50_now:
                return MarketRegime.TRENDING_DOWN

        # BB width for ranging detection
        if bb_width:
            if bb_width < 0.02:
                return MarketRegime.LOW_VOLATILITY
            elif bb_width > 0.06:
                return MarketRegime.VOLATILE
            else:
                return MarketRegime.RANGING

        return MarketRegime.UNKNOWN

    def _get_regime_weights(self, regime: MarketRegime) -> dict[str, float]:
        """Return strategy weights for the detected regime."""
        return REGIME_STRATEGY_WEIGHTS.get(regime, REGIME_STRATEGY_WEIGHTS[MarketRegime.UNKNOWN])

    # ------------------------------------------------------------------
    # Session quality
    # ------------------------------------------------------------------

    @staticmethod
    def _get_session_quality() -> tuple[str, float]:
        """Get current session and quality multiplier (0.0–1.0)."""
        hour = datetime.now(timezone.utc).hour
        if 12 <= hour < 16:
            return "overlap", 1.0
        if 7 <= hour < 12:
            return "london", 0.9
        if 16 <= hour < 21:
            return "new_york", 0.8
        if 0 <= hour < 7 or hour >= 22:
            return "asian", 0.5
        return "off_hours", 0.3

    @staticmethod
    def _is_forex_symbol(symbol: str) -> bool:
        return symbol in _FOREX_PIP_SIZES or (
            "/" in symbol and len(symbol) == 7 and symbol[3] == "/"
        )

    @staticmethod
    def _get_pip_size(symbol: str) -> float:
        return _FOREX_PIP_SIZES.get(symbol, 1.0)

    # ------------------------------------------------------------------
    # Confluence adjustment
    # ------------------------------------------------------------------

    def _adjust_confluence(
        self,
        base_confluence: float,
        symbol: str,
        market_data: dict[str, Any],
        regime: MarketRegime,
        news_adjustment: float,
    ) -> float:
        """Apply regime, session, and news adjustments to confluence score."""
        adjusted = base_confluence
        is_forex = self._is_forex_symbol(symbol)

        # Regime weight (apply as multiplier centered on 1.0)
        regime_weights = self._get_regime_weights(regime)
        # Use a neutral default strategy weight (no specific strategy hint in pipeline output)
        avg_regime_weight = sum(regime_weights.values()) / len(regime_weights)
        regime_mult = 0.7 + (0.3 * avg_regime_weight)  # scale to 0.7–1.3 range
        adjusted *= regime_mult

        # Session adjustment (forex only)
        if is_forex:
            session_name, session_quality = self._get_session_quality()
            session_mult = 0.7 + (0.3 * session_quality)
            adjusted *= session_mult

            # Spread penalty
            spread_pips = market_data.get("spread_pips", 0)
            if spread_pips > 0:
                if spread_pips < 2.0:
                    pass  # no penalty
                elif spread_pips < 5.0:
                    adjusted *= 0.9
                else:
                    adjusted *= 0.7

            # ATR sanity
            atr_pips = market_data.get("atr_pips", 0)
            if atr_pips > 0:
                if atr_pips < 10:
                    adjusted *= 0.8  # too quiet
                elif atr_pips > 100:
                    adjusted *= 0.85  # too volatile

        # News risk adjustment (reduce strength on high-impact news)
        if news_adjustment > 0:
            adjusted *= (1.0 - min(news_adjustment, 0.8))

        return adjusted

    # ------------------------------------------------------------------
    # Pipeline integration
    # ------------------------------------------------------------------

    async def _run_pipeline(
        self,
        symbol: str,
        timeframe: str,
        market_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Run the AlphaStack strategy pipeline and extract results."""
        try:
            from alphastack.strategy.context import AlphaStackContext
            from alphastack.strategy.pipeline import AlphaStackPipeline

            ctx = AlphaStackContext(
                symbol=symbol,
                timeframe=timeframe,
                market_data=market_data,
            )

            pipeline = AlphaStackPipeline(parallel=True)
            ctx = await pipeline.run(ctx)

            output = ctx.model_dump() if hasattr(ctx, "model_dump") else {}
            return output

        except ImportError:
            logger.warning("strategy_agent.pipeline_import_failed", exc_info=True)
            return {}
        except Exception as exc:
            logger.error("strategy_agent.pipeline_error", error=str(exc), exc_info=True)
            return {}

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run the strategy pipeline with regime-aware signal generation."""
        symbol = state.get("current_symbol", "BTC/USDT")
        timeframe = state.get("current_timeframe", "1h")
        market_data = state.get("market_data", {})
        news_adjustment = state.get("news_risk_adjustment", 0.0)
        is_forex = self._is_forex_symbol(symbol)

        # 1. Detect market regime
        regime = self._detect_regime(market_data)
        regime_weights = self._get_regime_weights(regime)

        logger.info(
            "strategy_agent.analyse",
            symbol=symbol,
            timeframe=timeframe,
            regime=regime.value,
            news_adjustment=news_adjustment,
            asset_type="forex" if is_forex else "crypto",
        )

        # 2. Run pipeline
        pipeline_output = await self._run_pipeline(symbol, timeframe, market_data)

        # 3. Extract confluence and bias
        confluence_data = pipeline_output.get("confluence", {})
        base_confluence = confluence_data.get("score", 0.0) if isinstance(confluence_data, dict) else 0.0
        bias_data = pipeline_output.get("bias", {})
        bias = bias_data.get("bias", "flat") if isinstance(bias_data, dict) else "flat"

        # 4. Adjust confluence for regime, session, news
        adjusted_confluence = self._adjust_confluence(
            base_confluence, symbol, market_data, regime, news_adjustment,
        )

        # 5. Generate signals
        signals: list[dict[str, Any]] = []
        min_threshold = 0.4 if is_forex else 0.3

        if adjusted_confluence > min_threshold and bias in ("long", "short"):
            entry_price = pipeline_output.get("entry_price")
            stop_loss = pipeline_output.get("stop_loss")
            take_profit = pipeline_output.get("take_profit")

            # Forex pip calculations
            sl_pips = None
            tp_pips = None
            if is_forex and entry_price and stop_loss:
                pip_size = self._get_pip_size(symbol)
                if pip_size > 0:
                    sl_pips = round(abs(entry_price - stop_loss) / pip_size, 1)
                    if take_profit:
                        tp_levels = take_profit if isinstance(take_profit, list) else [take_profit]
                        tp_pips = [round(abs(entry_price - tp) / pip_size, 1) for tp in tp_levels]

            signal: dict[str, Any] = {
                "id": uuid.uuid4().hex[:12],
                "symbol": symbol,
                "side": bias,
                "strength": adjusted_confluence,
                "confluence_score": base_confluence,
                "adjusted_confluence": adjusted_confluence,
                "timeframe": timeframe,
                "strategy": "alphastack",
                "asset_type": "forex" if is_forex else "crypto",
                "regime": regime.value,
                "regime_weights": regime_weights,
                "reasoning": pipeline_output.get("reasoning", f"Pipeline signal in {regime.value} regime"),
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "entry_price": entry_price,
            }
            if is_forex:
                signal["pip_size"] = self._get_pip_size(symbol)
                signal["sl_pips"] = sl_pips
                signal["tp_pips"] = tp_pips
                session_name, _ = self._get_session_quality()
                signal["session"] = session_name

            signals.append(signal)

        elif not pipeline_output:
            # Pipeline unavailable — generate fallback
            signals.append(self._fallback_signal(symbol, timeframe, regime))

        # 6. Build result
        pipeline_context = {
            **pipeline_output,
            "regime": regime.value,
            "regime_weights": regime_weights,
        }

        max_confidence = max((s.get("adjusted_confluence", 0) for s in signals), default=0.0)

        logger.info(
            "strategy_agent.complete",
            symbol=symbol,
            regime=regime.value,
            signals=len(signals),
            base_confluence=round(base_confluence, 3),
            adjusted_confluence=round(adjusted_confluence, 3),
        )

        return {
            "signals": signals,
            "pipeline_context": pipeline_context,
            "_confidence": max_confidence,
        }

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_signal(
        symbol: str,
        timeframe: str,
        regime: MarketRegime,
    ) -> dict[str, Any]:
        """Generate a safe fallback signal when pipeline is unavailable."""
        return {
            "id": uuid.uuid4().hex[:12],
            "symbol": symbol,
            "side": "flat",
            "strength": 0.0,
            "confluence_score": 0.0,
            "adjusted_confluence": 0.0,
            "timeframe": timeframe,
            "strategy": "alphastack_fallback",
            "regime": regime.value,
            "reasoning": f"Pipeline unavailable — no actionable signal (regime: {regime.value})",
            "stop_loss": None,
            "take_profit": None,
            "entry_price": None,
        }
