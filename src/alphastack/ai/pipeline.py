"""AI-enhanced strategy pipeline — 16-step pipeline with ML signal generation.

Integrates the AI layer (signals, regime, sentiment) into the AlphaStack
16-step pipeline. Provides:
  - Phase 1 steps (3-5, 10): price action, basic indicators
  - Signal aggregation and ranking across multiple timeframes
  - Regime-adaptive parameter selection
  - Sentiment-adjusted confluence scoring

This module complements (does not replace) the existing strategy/pipeline.py.
It adds AI/ML intelligence on top of the existing step-based architecture.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from alphastack.ai.regime import MarketRegime, MarketRegimeDetector, RegimeState
from alphastack.ai.sentiment import AggregateSentiment, SentimentEngine
from alphastack.ai.signals import (
    ConfluenceScorer,
    ConfidenceScorer,
    SMCDetector,
    Signal,
    SignalGenerator,
    SignalSide,
    SupportResistanceDetector,
    compute_adx,
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_obv,
    compute_rsi,
    compute_stochastic,
    compute_vwap,
)
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pipeline phase definitions
# ---------------------------------------------------------------------------

class PipelinePhase(str, Enum):
    """Pipeline execution phases aligned with the 16-step architecture."""
    PRICE_ACTION = "price_action"        # Steps 3-5: structure, S/R, liquidity
    INDICATORS = "indicators"            # Steps 6-9: SMC, RSI, candlestick
    CONFLUENCE = "confluence"            # Step 10: confluence scoring
    SIZING_RISK = "sizing_risk"          # Steps 11-13: sizing, SL, TP
    MANAGEMENT = "management"            # Steps 14-16: management, exit, journal


# ---------------------------------------------------------------------------
# Pipeline step result
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Result from a single pipeline step."""
    step_number: int
    step_name: str
    phase: PipelinePhase
    duration_ms: float
    output: dict[str, Any]
    confidence: float = 0.0
    error: str | None = None


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""
    symbol: str
    timeframe: str
    signal: Signal | None
    regime: RegimeState | None
    sentiment: AggregateSentiment | None
    step_results: list[StepResult]
    total_duration_ms: float
    confluence_score: float = 0.0
    risk_adjustment: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for event bus / storage."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "signal": {
                "side": self.signal.side.value if self.signal else "flat",
                "strength": self.signal.strength if self.signal else 0.0,
                "confluence_score": self.signal.confluence_score if self.signal else 0.0,
                "confidence": self.signal.confidence if self.signal else 0.0,
                "entry_price": self.signal.entry_price if self.signal else None,
                "stop_loss": self.signal.stop_loss if self.signal else None,
                "take_profit": self.signal.take_profit if self.signal else [],
                "reasoning": self.signal.reasoning if self.signal else "",
            },
            "regime": {
                "regime": self.regime.regime.value if self.regime else "unknown",
                "confidence": self.regime.confidence if self.regime else 0.0,
                "trend_strength": self.regime.trend_strength.value if self.regime else "none",
            },
            "sentiment": {
                "score": self.sentiment.score if self.sentiment else 0.0,
                "polarity": self.sentiment.polarity.value if self.sentiment else "neutral",
                "risk_adjustment": self.sentiment.risk_adjustment if self.sentiment else 0.0,
            },
            "confluence_score": self.confluence_score,
            "risk_adjustment": self.risk_adjustment,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "steps_completed": len([s for s in self.step_results if s.error is None]),
            "steps_failed": len([s for s in self.step_results if s.error is not None]),
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# AI Pipeline — 16-step strategy pipeline with ML integration
# ---------------------------------------------------------------------------

class AIStrategyPipeline:
    """AI-enhanced 16-step strategy pipeline.

    Integrates technical analysis, regime detection, and sentiment scoring
    into a unified signal generation pipeline.

    Pipeline steps:
    ┌──────┬──────────────────────────┬────────────────────────────────┐
    │ Step │ Name                     │ AI Enhancement                 │
    ├──────┼──────────────────────────┼────────────────────────────────┤
    │  1   │ Fundamental Intelligence │ SentimentEngine (news+social)  │
    │  2   │ Market Bias              │ EMA alignment + trend score    │
    │  3   │ Session Analysis         │ Session quality multiplier     │
    │  4   │ Market Structure         │ Swing H/L detection + regime   │
    │  5   │ Support/Resistance       │ S/R detector with clustering   │
    │  6   │ Liquidity Detection      │ Liquidity sweep detection      │
    │  7   │ Smart Money Concepts     │ OB + FVG + breaker detection   │
    │  8   │ RSI Confirmation         │ RSI + divergence detection     │
    │  9   │ Candlestick Confirmation │ Pattern scoring                │
    │ 10   │ Confluence Engine        │ Weighted multi-factor scoring  │
    │ 11   │ Position Sizing          │ Regime-adaptive sizing         │
    │ 12   │ Stop Loss                │ ATR-based SL with regime mult  │
    │ 13   │ Take Profit              │ Multi-level TP with R:R        │
    │ 14   │ Trade Management         │ Trailing/breakeven rules       │
    │ 15   │ Exit Conditions          │ Regime-based exit triggers     │
    │ 16   │ Trade Journal            │ Full trace logging             │
    └──────┴──────────────────────────┴────────────────────────────────┘

    Usage::

        pipeline = AIStrategyPipeline()
        result = await pipeline.run(
            symbol="EUR/USD",
            timeframe="1h",
            opens=opens, highs=highs, lows=lows, closes=closes,
            volumes=volumes,
        )
    """

    def __init__(
        self,
        confluence_weights: dict[str, float] | None = None,
        risk_per_trade_pct: float = 2.0,
        account_balance: float = 10000.0,
    ) -> None:
        self._signal_gen = SignalGenerator(confluence_weights)
        self._regime_detector = MarketRegimeDetector()
        self._sentiment_engine = SentimentEngine()
        self._smc = SMCDetector()
        self._sr = SupportResistanceDetector()
        self._confluence = ConfluenceScorer(confluence_weights)
        self._confidence = ConfidenceScorer()

        self._risk_per_trade_pct = risk_per_trade_pct
        self._account_balance = account_balance

    async def run(
        self,
        symbol: str,
        timeframe: str,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray | None = None,
        news_headlines: list[str] | None = None,
        news_timestamps: list[float] | None = None,
        social_posts: list[str] | None = None,
        economic_events: list[dict[str, Any]] | None = None,
    ) -> PipelineResult:
        """Run the full 16-step AI pipeline.

        Returns PipelineResult with signal, regime, sentiment, and all step outputs.
        """
        t0 = time.perf_counter()
        step_results: list[StepResult] = []
        notes: list[str] = []

        if volumes is None:
            volumes = np.ones(len(closes))

        # ── Phase 1: Price Action (Steps 1-5) ──────────────────────────

        # Step 1: Fundamental Intelligence (sentiment)
        sentiment = await self._step_sentiment(
            news_headlines, news_timestamps, social_posts, economic_events,
        )
        step_results.append(StepResult(
            step_number=1, step_name="fundamental_intelligence",
            phase=PipelinePhase.PRICE_ACTION,
            duration_ms=0, output={"sentiment_score": sentiment.score if sentiment else 0.0},
        ))

        # Step 2: Market Bias (trend direction)
        bias_result = self._step_bias(opens, highs, lows, closes)
        step_results.append(bias_result)

        # Step 3: Session Analysis
        session_result = self._step_session()
        step_results.append(session_result)
        session_quality = session_result.output.get("quality", 0.5)

        # Step 4: Market Structure (regime detection)
        regime = self._regime_detector.detect(opens, highs, lows, closes, volumes)
        step_results.append(StepResult(
            step_number=4, step_name="market_structure",
            phase=PipelinePhase.PRICE_ACTION,
            duration_ms=0,
            output={
                "regime": regime.regime.value,
                "confidence": regime.confidence,
                "adx": regime.adx_value,
                "trend_strength": regime.trend_strength.value,
            },
            confidence=regime.confidence,
        ))

        # Step 5: Support/Resistance
        sr_result = self._step_support_resistance(highs, lows, closes)
        step_results.append(sr_result)

        # ── Phase 2: Indicators (Steps 6-9) ────────────────────────────

        # Step 6: Liquidity Detection
        liquidity_result = self._step_liquidity(highs, lows, closes)
        step_results.append(liquidity_result)

        # Step 7: Smart Money Concepts
        smc_result = self._step_smc(opens, highs, lows, closes)
        step_results.append(smc_result)

        # Step 8: RSI Confirmation
        rsi_result = self._step_rsi(closes, regime)
        step_results.append(rsi_result)

        # Step 9: Candlestick Confirmation
        candle_result = self._step_candlestick(opens, highs, lows, closes)
        step_results.append(candle_result)

        # ── Phase 3: Confluence (Step 10) ───────────────────────────────

        # Step 10: Confluence Engine
        confluence = self._confluence.score(
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            opens=opens,
            regime=regime.regime.value,
            session_quality=session_quality,
        )
        step_results.append(StepResult(
            step_number=10, step_name="confluence_engine",
            phase=PipelinePhase.CONFLUENCE,
            duration_ms=0,
            output=confluence,
            confidence=confluence["score"] / 100.0,
        ))

        # ── Phase 4: Sizing & Risk (Steps 11-13) ───────────────────────

        # Get regime adaptation
        adaptation = self._regime_detector.get_adaptation(regime.regime)

        # Apply sentiment risk adjustment
        risk_adj = sentiment.risk_adjustment if sentiment else 0.0
        adjusted_confluence = confluence["score"] * (1.0 - min(risk_adj, 0.8))

        # Check minimum confluence threshold
        if adjusted_confluence < adaptation.min_confluence:
            notes.append(
                f"Confluence {adjusted_confluence:.1f} below regime threshold "
                f"{adaptation.min_confluence:.1f} ({regime.regime.value})"
            )

        # Compute ATR for SL/TP
        atr = compute_atr(highs, lows, closes)
        atr_val = float(atr[-1]) if not np.isnan(atr[-1]) else float(closes[-1]) * 0.01
        current_price = float(closes[-1])

        # Step 12: Stop Loss (runs before sizing)
        sl_result = self._step_stop_loss(
            current_price, atr_val, confluence["direction"], adaptation,
        )
        step_results.append(sl_result)
        stop_loss = sl_result.output.get("stop_loss", current_price)

        # Step 11: Position Sizing
        sizing_result = self._step_sizing(
            current_price, stop_loss, adaptation,
        )
        step_results.append(sizing_result)

        # Step 13: Take Profit
        tp_result = self._step_take_profit(
            current_price, stop_loss, atr_val, confluence["direction"], adaptation,
        )
        step_results.append(tp_result)

        # ── Phase 5: Management (Steps 14-16) ───────────────────────────

        # Step 14: Trade Management
        mgmt_result = self._step_management(
            current_price, stop_loss, tp_result.output.get("levels", []), atr_val,
        )
        step_results.append(mgmt_result)

        # Step 15: Exit Conditions
        exit_result = self._step_exit(regime, confluence)
        step_results.append(exit_result)

        # Step 16: Journal
        journal_result = self._step_journal(
            symbol, timeframe, confluence, regime, sentiment,
        )
        step_results.append(journal_result)

        # ── Final signal generation ─────────────────────────────────────

        # Compute confidence
        component_scores = confluence.get("component_scores", {})
        confidence = self._confidence.score(
            confluence_score=adjusted_confluence,
            component_scores=component_scores,
            regime=regime.regime.value,
            session_quality=session_quality,
        )

        # Build final signal
        side = confluence["direction"]
        strength = min(1.0, adjusted_confluence / 80.0) * confidence

        if side == SignalSide.FLAT or adjusted_confluence < adaptation.min_confluence:
            signal = Signal(
                symbol=symbol,
                side=SignalSide.FLAT,
                strength=0.0,
                confluence_score=adjusted_confluence,
                confidence=confidence,
                reasoning=f"Below threshold ({adjusted_confluence:.1f} < {adaptation.min_confluence})",
                timeframe=timeframe,
                regime=regime.regime.value,
            )
        else:
            # Build indicator dict for signal
            rsi_vals = compute_rsi(closes)
            macd_line, _, histogram = compute_macd(closes)
            bb_upper, _, bb_lower = compute_bollinger_bands(closes)
            adx = compute_adx(highs, lows, closes)

            indicators = {
                "rsi": round(float(rsi_vals[-1]), 2) if not np.isnan(rsi_vals[-1]) else 50.0,
                "macd": round(float(histogram[-1]), 6) if not np.isnan(histogram[-1]) else 0.0,
                "atr": round(atr_val, 6),
                "adx": round(float(adx[-1]), 2) if not np.isnan(adx[-1]) else 0.0,
                "confluence": round(adjusted_confluence, 1),
            }

            signal = Signal(
                symbol=symbol,
                side=side,
                strength=round(strength, 4),
                confluence_score=round(adjusted_confluence, 1),
                confidence=confidence,
                entry_price=round(current_price, 6),
                stop_loss=round(stop_loss, 6),
                take_profit=tp_result.output.get("levels", []),
                reasoning=self._build_signal_reasoning(
                    side, adjusted_confluence, indicators, regime, sentiment,
                ),
                timeframe=timeframe,
                indicators=indicators,
                regime=regime.regime.value,
            )

        total_ms = (time.perf_counter() - t0) * 1000

        logger.info(
            "pipeline.complete",
            symbol=symbol,
            side=signal.side.value,
            strength=signal.strength,
            confluence=signal.confluence_score,
            confidence=signal.confidence,
            regime=regime.regime.value,
            duration_ms=round(total_ms, 1),
        )

        return PipelineResult(
            symbol=symbol,
            timeframe=timeframe,
            signal=signal,
            regime=regime,
            sentiment=sentiment,
            step_results=step_results,
            total_duration_ms=total_ms,
            confluence_score=adjusted_confluence,
            risk_adjustment=risk_adj,
            notes=notes,
        )

    # ── Individual step implementations ─────────────────────────────────

    async def _step_sentiment(
        self,
        news_headlines: list[str] | None,
        news_timestamps: list[float] | None,
        social_posts: list[str] | None,
        economic_events: list[dict[str, Any]] | None,
    ) -> AggregateSentiment | None:
        """Step 1: Run sentiment analysis."""
        if not any([news_headlines, social_posts, economic_events]):
            return None
        return self._sentiment_engine.analyze(
            news_headlines=news_headlines,
            news_timestamps=news_timestamps,
            social_posts=social_posts,
            economic_events=economic_events,
        )

    def _step_bias(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
    ) -> StepResult:
        """Step 2: Market bias from EMA alignment and trend."""
        t0 = time.perf_counter()

        ema_9 = compute_ema(closes, 9)
        ema_21 = compute_ema(closes, 21)
        ema_50 = compute_ema(closes, 50)

        if any(np.isnan([ema_9[-1], ema_21[-1], ema_50[-1]])):
            return StepResult(
                step_number=2, step_name="market_bias",
                phase=PipelinePhase.PRICE_ACTION,
                duration_ms=(time.perf_counter() - t0) * 1000,
                output={"bias": "neutral", "trend_strength": 0.0},
            )

        # Alignment score
        alignment = 0.0
        if ema_9[-1] > ema_21[-1]:
            alignment += 1
        if ema_21[-1] > ema_50[-1]:
            alignment += 1
        if closes[-1] > ema_9[-1]:
            alignment += 1

        if alignment >= 2:
            bias = "bullish"
        elif alignment <= -2:
            bias = "bearish"
        else:
            bias = "neutral"

        # Trend strength from EMA separation
        sep = abs(ema_9[-1] - ema_50[-1]) / max(ema_50[-1], 1e-10)
        trend_strength = min(sep * 100, 1.0)

        return StepResult(
            step_number=2, step_name="market_bias",
            phase=PipelinePhase.PRICE_ACTION,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={"bias": bias, "trend_strength": round(trend_strength, 3), "alignment": alignment},
        )

    def _step_session(self) -> StepResult:
        """Step 3: Session analysis (time-of-day quality)."""
        from datetime import datetime, timezone
        t0 = time.perf_counter()
        hour = datetime.now(timezone.utc).hour

        if 12 <= hour < 16:
            session, quality = "overlap", 1.0
        elif 7 <= hour < 12:
            session, quality = "london", 0.9
        elif 16 <= hour < 21:
            session, quality = "new_york", 0.8
        elif 0 <= hour < 7 or hour >= 22:
            session, quality = "asian", 0.5
        else:
            session, quality = "off_hours", 0.3

        return StepResult(
            step_number=3, step_name="session_analysis",
            phase=PipelinePhase.PRICE_ACTION,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={"session": session, "quality": quality},
        )

    def _step_support_resistance(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
    ) -> StepResult:
        """Step 5: Support/Resistance detection."""
        t0 = time.perf_counter()
        supports, resistances = self._sr.detect(highs, lows, closes)

        return StepResult(
            step_number=5, step_name="support_resistance",
            phase=PipelinePhase.PRICE_ACTION,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={
                "supports": [{"price": s.price, "strength": s.strength, "touches": s.touches} for s in supports[:5]],
                "resistances": [{"price": r.price, "strength": r.strength, "touches": r.touches} for r in resistances[:5]],
            },
        )

    def _step_liquidity(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
    ) -> StepResult:
        """Step 6: Liquidity detection."""
        t0 = time.perf_counter()
        sweeps = self._smc.detect_liquidity_sweeps(highs, lows, closes)

        return StepResult(
            step_number=6, step_name="liquidity_detection",
            phase=PipelinePhase.INDICATORS,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={
                "sweeps": [{"level": s.level, "direction": s.direction.value, "strength": s.strength} for s in sweeps],
                "sweep_count": len(sweeps),
            },
        )

    def _step_smc(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
    ) -> StepResult:
        """Step 7: Smart Money Concepts analysis."""
        t0 = time.perf_counter()
        atr = compute_atr(highs, lows, closes)
        result = self._smc.analyze(opens, highs, lows, closes, atr)

        return StepResult(
            step_number=7, step_name="smart_money_concepts",
            phase=PipelinePhase.INDICATORS,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={
                "bias": result["bias"].value,
                "bullish_score": result["bullish_score"],
                "bearish_score": result["bearish_score"],
                "active_obs": len([ob for ob in result["order_blocks"] if not ob.mitigated]),
                "active_fvgs": len([fvg for fvg in result["fair_value_gaps"] if not fvg.filled]),
            },
        )

    def _step_rsi(
        self,
        closes: np.ndarray,
        regime: RegimeState,
    ) -> StepResult:
        """Step 8: RSI confirmation with regime-adaptive thresholds."""
        t0 = time.perf_counter()
        rsi = compute_rsi(closes)
        rsi_val = float(rsi[-1]) if not np.isnan(rsi[-1]) else 50.0

        adaptation = self._regime_detector.get_adaptation(regime.regime)

        if rsi_val >= adaptation.rsi_overbought:
            signal = "overbought"
        elif rsi_val <= adaptation.rsi_oversold:
            signal = "oversold"
        else:
            signal = "neutral"

        return StepResult(
            step_number=8, step_name="rsi_confirmation",
            phase=PipelinePhase.INDICATORS,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={
                "rsi": round(rsi_val, 2),
                "signal": signal,
                "overbought_level": adaptation.rsi_overbought,
                "oversold_level": adaptation.rsi_oversold,
            },
        )

    def _step_candlestick(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
    ) -> StepResult:
        """Step 9: Candlestick pattern confirmation."""
        t0 = time.perf_counter()

        patterns: list[dict[str, Any]] = []
        if len(closes) >= 3:
            # Engulfing
            body_curr = closes[-1] - opens[-1]
            body_prev = closes[-2] - opens[-2]

            if body_curr > 0 and body_prev < 0 and abs(body_curr) > abs(body_prev):
                patterns.append({"name": "bullish_engulfing", "direction": "long", "strength": 0.7})
            elif body_curr < 0 and body_prev > 0 and abs(body_curr) > abs(body_prev):
                patterns.append({"name": "bearish_engulfing", "direction": "short", "strength": 0.7})

            # Hammer / Shooting Star
            wick_range = highs[-1] - lows[-1]
            if wick_range > 0:
                body_ratio = abs(body_curr) / wick_range
                upper_wick = highs[-1] - max(opens[-1], closes[-1])
                lower_wick = min(opens[-1], closes[-1]) - lows[-1]

                if body_ratio < 0.3 and lower_wick > upper_wick * 2:
                    patterns.append({"name": "hammer", "direction": "long", "strength": 0.6})
                elif body_ratio < 0.3 and upper_wick > lower_wick * 2:
                    patterns.append({"name": "shooting_star", "direction": "short", "strength": 0.6})

            # Doji
            if wick_range > 0 and abs(body_curr) / wick_range < 0.1:
                patterns.append({"name": "doji", "direction": "flat", "strength": 0.3})

        return StepResult(
            step_number=9, step_name="candlestick_confirmation",
            phase=PipelinePhase.INDICATORS,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={"patterns": patterns, "pattern_count": len(patterns)},
        )

    def _step_stop_loss(
        self,
        entry: float,
        atr_val: float,
        direction: SignalSide,
        adaptation: Any,
    ) -> StepResult:
        """Step 12: Compute stop loss level."""
        t0 = time.perf_counter()
        sl_distance = atr_val * adaptation.atr_multiplier_sl

        if direction == SignalSide.LONG:
            stop_loss = entry - sl_distance
        elif direction == SignalSide.SHORT:
            stop_loss = entry + sl_distance
        else:
            stop_loss = entry

        return StepResult(
            step_number=12, step_name="stop_loss",
            phase=PipelinePhase.SIZING_RISK,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={
                "stop_loss": round(stop_loss, 6),
                "sl_distance": round(sl_distance, 6),
                "atr_multiplier": adaptation.atr_multiplier_sl,
            },
        )

    def _step_sizing(
        self,
        entry: float,
        stop_loss: float,
        adaptation: Any,
    ) -> StepResult:
        """Step 11: Position sizing based on risk."""
        t0 = time.perf_counter()

        risk_amount = self._account_balance * (self._risk_per_trade_pct / 100.0)
        sl_distance = abs(entry - stop_loss)

        if sl_distance > 0:
            position_size = risk_amount / sl_distance
        else:
            position_size = 0.0

        # Apply regime scaling
        position_size *= adaptation.position_size_factor

        return StepResult(
            step_number=11, step_name="position_sizing",
            phase=PipelinePhase.SIZING_RISK,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={
                "position_size": round(position_size, 4),
                "risk_amount": round(risk_amount, 2),
                "risk_pct": self._risk_per_trade_pct,
                "size_factor": adaptation.position_size_factor,
            },
        )

    def _step_take_profit(
        self,
        entry: float,
        stop_loss: float,
        atr_val: float,
        direction: SignalSide,
        adaptation: Any,
    ) -> StepResult:
        """Step 13: Multi-level take profit."""
        t0 = time.perf_counter()

        sl_distance = abs(entry - stop_loss)
        tp_mult = adaptation.atr_multiplier_tp

        if direction == SignalSide.LONG:
            levels = [
                round(entry + sl_distance * 1.5, 6),
                round(entry + sl_distance * 2.5, 6),
                round(entry + sl_distance * tp_mult, 6),
            ]
            rr_ratio = 1.5
        elif direction == SignalSide.SHORT:
            levels = [
                round(entry - sl_distance * 1.5, 6),
                round(entry - sl_distance * 2.5, 6),
                round(entry - sl_distance * tp_mult, 6),
            ]
            rr_ratio = 1.5
        else:
            levels = []
            rr_ratio = 0.0

        return StepResult(
            step_number=13, step_name="take_profit",
            phase=PipelinePhase.SIZING_RISK,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={"levels": levels, "rr_ratio": rr_ratio},
        )

    def _step_management(
        self,
        entry: float,
        stop_loss: float,
        tp_levels: list[float],
        atr_val: float,
    ) -> StepResult:
        """Step 14: Trade management rules."""
        t0 = time.perf_counter()

        actions = []
        sl_distance = abs(entry - stop_loss)

        if sl_distance > 0:
            # Move to breakeven at 1R
            be_trigger = entry + sl_distance if entry > stop_loss else entry - sl_distance
            actions.append({
                "action": "breakeven",
                "trigger_price": round(be_trigger, 6),
                "trigger_rr": 1.0,
            })

            # Trail stop at 2R
            trail_trigger = entry + sl_distance * 2 if entry > stop_loss else entry - sl_distance * 2
            actions.append({
                "action": "trail",
                "trigger_price": round(trail_trigger, 6),
                "trigger_rr": 2.0,
                "trail_distance": round(atr_val * 1.0, 6),
            })

            # Partial close at TP1
            if tp_levels:
                actions.append({
                    "action": "partial_close",
                    "trigger_price": tp_levels[0],
                    "close_pct": 0.5,
                })

        return StepResult(
            step_number=14, step_name="trade_management",
            phase=PipelinePhase.MANAGEMENT,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={"actions": actions},
        )

    def _step_exit(
        self,
        regime: RegimeState,
        confluence: dict[str, Any],
    ) -> StepResult:
        """Step 15: Exit condition evaluation."""
        t0 = time.perf_counter()

        should_exit = False
        reasons = []

        # Exit if regime changed against position
        if regime.regime in (MarketRegime.VOLATILE, MarketRegime.UNKNOWN):
            if regime.confidence > 0.7:
                should_exit = True
                reasons.append(f"Regime shift to {regime.regime.value}")

        # Exit if confluence collapsed
        if confluence["score"] < 20:
            should_exit = True
            reasons.append(f"Confluence collapsed to {confluence['score']:.1f}")

        return StepResult(
            step_number=15, step_name="exit_conditions",
            phase=PipelinePhase.MANAGEMENT,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output={"should_exit": should_exit, "reasons": reasons},
        )

    def _step_journal(
        self,
        symbol: str,
        timeframe: str,
        confluence: dict[str, Any],
        regime: RegimeState,
        sentiment: AggregateSentiment | None,
    ) -> StepResult:
        """Step 16: Trade journal entry."""
        t0 = time.perf_counter()

        entry = {
            "symbol": symbol,
            "timeframe": timeframe,
            "confluence_score": confluence["score"],
            "direction": confluence["direction"].value,
            "regime": regime.regime.value,
            "regime_confidence": regime.confidence,
            "sentiment_score": sentiment.score if sentiment else 0.0,
            "timestamp": time.time(),
        }

        return StepResult(
            step_number=16, step_name="trade_journal",
            phase=PipelinePhase.MANAGEMENT,
            duration_ms=(time.perf_counter() - t0) * 1000,
            output=entry,
        )

    @staticmethod
    def _build_signal_reasoning(
        side: SignalSide,
        confluence: float,
        indicators: dict[str, float],
        regime: RegimeState,
        sentiment: AggregateSentiment | None,
    ) -> str:
        """Build human-readable signal reasoning."""
        parts = [f"{'Bullish' if side == SignalSide.LONG else 'Bearish'} signal"]
        parts.append(f"confluence={confluence:.1f}")
        parts.append(f"RSI={indicators.get('rsi', 50):.1f}")
        parts.append(f"ADX={indicators.get('adx', 0):.1f}")
        parts.append(f"regime={regime.regime.value}")

        if sentiment and abs(sentiment.score) > 0.1:
            parts.append(f"sentiment={sentiment.score:+.2f}")
        if sentiment and sentiment.risk_adjustment > 0.05:
            parts.append(f"risk_adj={sentiment.risk_adjustment:.0%}")

        return " | ".join(parts)
