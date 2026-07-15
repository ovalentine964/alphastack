"""Bear Agent — argues AGAINST a trade signal.

Builds a ReasoningChain that finds contradicting evidence: overbought
conditions, resistance levels, negative sentiment, macro risks, and
poor risk/reward setups.
"""

from __future__ import annotations

from typing import Any

from alphastack.agi.reasoning import (
    ChainOfThoughtEngine,
    ReasoningChain,
    ReasoningStepType,
)
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


class BearAgent:
    """Constructs a bearish case against a trade signal using chain-of-thought reasoning.

    The agent examines the signal, market data, and indicators to build
    a maximum-5-step reasoning chain that opposes executing the trade.
    """

    def __init__(self, cog_engine: ChainOfThoughtEngine | None = None) -> None:
        self._cog = cog_engine or ChainOfThoughtEngine()
        self.name = "bear"

    def argue(
        self,
        signal: dict[str, Any],
        market_data: dict[str, Any],
        indicators: dict[str, float],
        news_sentiment: float | None = None,
        bull_argument: str | None = None,
    ) -> ReasoningChain:
        """Build a bearish reasoning chain against the given signal.

        Parameters
        ----------
        signal : dict
            The trade signal (symbol, side, strength, confluence_score, etc.).
        market_data : dict
            OHLCV and order-book data.
        indicators : dict
            Technical indicator values (RSI, MACD, EMA, etc.).
        news_sentiment : float | None
            Optional sentiment score from -1 (bearish) to 1 (bullish).
        bull_argument : str | None
            If round 3, the bull's argument to counter.

        Returns
        -------
        ReasoningChain
            Completed bearish reasoning chain.
        """
        symbol = signal.get("symbol", "UNKNOWN")
        side = signal.get("side", "long")
        strength = signal.get("strength", 0.0)
        confluence = signal.get("confluence_score", 0.0)

        topic = f"Bear case against {side.upper()} {symbol}"
        if bull_argument:
            topic += " (rebuttal)"

        chain = self._cog.start_chain(topic=topic)

        # Step 1: Risk observation — signal weakness
        chain.add_step(
            ReasoningStepType.OBSERVATION,
            f"Signal: {side} {symbol} with strength={strength:.2f}, "
            f"confluence={confluence:.2f}. "
            f"{'Weak signal — strength below 0.5 threshold.' if abs(strength) < 0.5 else 'Moderate-to-strong signal.'}",
            confidence=min(0.5 + (1.0 - abs(strength)) * 0.3, 0.9),
        )

        # Step 2: Overbought / resistance evidence
        bearish_count = 0
        total_indicators = 0
        evidence_parts: list[str] = []

        for name, value in indicators.items():
            total_indicators += 1
            nl = name.lower()
            if "rsi" in nl:
                if value > 70:
                    bearish_count += 1
                    evidence_parts.append(f"{name}={value:.1f} (overbought, reversal risk)")
                elif value > 60:
                    bearish_count += 0.5
                    evidence_parts.append(f"{name}={value:.1f} (approaching overbought)")
            elif "macd" in nl:
                if value < 0:
                    bearish_count += 1
                    evidence_parts.append(f"{name}={value:.4f} (negative momentum)")
                elif value < 0.001:
                    bearish_count += 0.3
                    evidence_parts.append(f"{name}={value:.4f} (weakening momentum)")
            elif "ema" in nl or "sma" in nl:
                close = market_data.get("close", 0)
                if close > 0 and value > 0 and close < value:
                    bearish_count += 1
                    evidence_parts.append(f"Price below {name}={value:.2f} (resistance)")
            elif "atr" in nl:
                # High ATR = high volatility = higher risk
                avg_atr = market_data.get("avg_atr", 0)
                if avg_atr > 0 and value > avg_atr * 1.5:
                    bearish_count += 0.5
                    evidence_parts.append(f"{name} elevated ({value:.2f}) — high volatility risk")
            elif "volume" in nl:
                avg_vol = market_data.get("avg_volume", 0)
                if avg_vol > 0 and value < avg_vol * 0.5:
                    bearish_count += 0.5
                    evidence_parts.append(f"{name} below average (weak conviction)")

        trend_confidence = min(0.4 + (bearish_count / max(total_indicators, 1)) * 0.5, 0.9)
        chain.add_step(
            ReasoningStepType.EVIDENCE,
            f"Resistance/risk signals: {'; '.join(evidence_parts) if evidence_parts else 'limited bearish data'}",
            confidence=trend_confidence,
            evidence_refs=list(indicators.keys()),
        )

        # Step 3: Macro / sentiment risk
        sentiment_confidence = 0.5
        if news_sentiment is not None:
            if news_sentiment < -0.1:
                sentiment_confidence = min(0.5 + abs(news_sentiment) * 0.4, 0.85)
                chain.add_step(
                    ReasoningStepType.EVIDENCE,
                    f"Negative news sentiment ({news_sentiment:.2f}) — "
                    f"macro headwinds increase downside risk",
                    confidence=sentiment_confidence,
                    evidence_refs=["news_sentiment"],
                )
            elif news_sentiment > 0.1:
                sentiment_confidence = max(0.3, 0.5 - news_sentiment * 0.1)
                chain.add_step(
                    ReasoningStepType.EVIDENCE,
                    f"Positive sentiment ({news_sentiment:.2f}) may already be priced in — "
                    f"limited upside catalyst",
                    confidence=sentiment_confidence,
                    evidence_refs=["news_sentiment"],
                )
            else:
                chain.add_step(
                    ReasoningStepType.EVIDENCE,
                    "Neutral sentiment — no positive catalyst to drive the trade",
                    confidence=0.55,
                    evidence_refs=["news_sentiment"],
                )
        else:
            chain.add_step(
                ReasoningStepType.EVIDENCE,
                "No sentiment data — blind entry without full information",
                confidence=0.6,
            )

        # Step 4 (if rebuttal): Counter the bull's argument
        if bull_argument:
            chain.add_step(
                ReasoningStepType.INFERENCE,
                f"Bull argues: '{bull_argument}'. However, confluence={confluence:.2f} "
                f"is {'below 0.6 threshold' if confluence < 0.6 else 'not sufficient to override risk signals'}. "
                f"Strength={strength:.2f} suggests weak conviction. "
                f"Better to wait for confirmation.",
                confidence=min(0.5 + (1.0 - confluence) * 0.3, 0.85),
            )

        # Final step: Conclusion
        bearish_score = (bearish_count / max(total_indicators, 1)) * 0.5 + (1.0 - confluence) * 0.3 + (1.0 - abs(strength)) * 0.2
        action_confidence = min(0.3 + bearish_score, 0.9)
        chain.finalize(
            conclusion=(
                f"REJECT {side.upper()} {symbol}: bearish indicators={bearish_count}/{total_indicators}, "
                f"confluence={confluence:.2f} (below threshold), "
                f"strength={strength:.2f}. Risk outweighs reward."
            ),
        )

        logger.debug(
            "debate.bear.argue",
            symbol=symbol,
            confidence=chain.overall_confidence,
            steps=len(chain.steps),
        )
        return chain
