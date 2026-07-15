"""Bull Agent — argues FOR a trade signal.

Builds a ReasoningChain that finds supporting evidence: trend alignment,
momentum indicators, positive sentiment, and structural support levels.
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


class BullAgent:
    """Constructs a bullish case for a trade signal using chain-of-thought reasoning.

    The agent examines the signal, market data, and indicators to build
    a maximum-5-step reasoning chain that supports executing the trade.
    """

    def __init__(self, cog_engine: ChainOfThoughtEngine | None = None) -> None:
        self._cog = cog_engine or ChainOfThoughtEngine()
        self.name = "bull"

    def argue(
        self,
        signal: dict[str, Any],
        market_data: dict[str, Any],
        indicators: dict[str, float],
        news_sentiment: float | None = None,
        bear_argument: str | None = None,
    ) -> ReasoningChain:
        """Build a bullish reasoning chain for the given signal.

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
        bear_argument : str | None
            If round 3, the bear's argument to counter.

        Returns
        -------
        ReasoningChain
            Completed bullish reasoning chain.
        """
        symbol = signal.get("symbol", "UNKNOWN")
        side = signal.get("side", "long")
        strength = signal.get("strength", 0.0)
        confluence = signal.get("confluence_score", 0.0)

        topic = f"Bull case for {side.upper()} {symbol}"
        if bear_argument:
            topic += " (rebuttal)"

        chain = self._cog.start_chain(topic=topic)

        # Step 1: Signal strength observation
        chain.add_step(
            ReasoningStepType.OBSERVATION,
            f"Signal: {side} {symbol} with strength={strength:.2f}, "
            f"confluence={confluence:.2f}",
            confidence=min(0.5 + abs(strength) * 0.3 + confluence * 0.2, 0.95),
        )

        # Step 2: Trend & momentum evidence
        bullish_count = 0
        total_indicators = 0
        evidence_parts: list[str] = []

        for name, value in indicators.items():
            total_indicators += 1
            nl = name.lower()
            if "rsi" in nl:
                if value < 40:
                    bullish_count += 1
                    evidence_parts.append(f"{name}={value:.1f} (oversold, reversal likely)")
                elif value < 60:
                    bullish_count += 0.5
                    evidence_parts.append(f"{name}={value:.1f} (neutral-bullish zone)")
            elif "macd" in nl:
                if value > 0:
                    bullish_count += 1
                    evidence_parts.append(f"{name}={value:.4f} (positive momentum)")
                else:
                    evidence_parts.append(f"{name}={value:.4f} (negative but watch for crossover)")
            elif "ema" in nl or "sma" in nl:
                # Price above MA is bullish
                close = market_data.get("close", 0)
                if close > 0 and value > 0 and close > value:
                    bullish_count += 1
                    evidence_parts.append(f"Price above {name}={value:.2f}")
            elif "volume" in nl:
                avg_vol = market_data.get("avg_volume", 0)
                if avg_vol > 0 and value > avg_vol * 1.2:
                    bullish_count += 0.5
                    evidence_parts.append(f"{name} above average (accumulation)")

        trend_confidence = min(0.4 + (bullish_count / max(total_indicators, 1)) * 0.5, 0.9)
        chain.add_step(
            ReasoningStepType.EVIDENCE,
            f"Trend/momentum: {'; '.join(evidence_parts) if evidence_parts else 'limited data'}",
            confidence=trend_confidence,
            evidence_refs=list(indicators.keys()),
        )

        # Step 3: Sentiment & structural support
        sentiment_confidence = 0.5
        if news_sentiment is not None:
            if news_sentiment > 0.1:
                sentiment_confidence = min(0.5 + news_sentiment * 0.4, 0.85)
                chain.add_step(
                    ReasoningStepType.EVIDENCE,
                    f"Positive news sentiment ({news_sentiment:.2f}) supports bullish thesis",
                    confidence=sentiment_confidence,
                    evidence_refs=["news_sentiment"],
                )
            elif news_sentiment < -0.1:
                sentiment_confidence = max(0.3, 0.5 + news_sentiment * 0.2)
                chain.add_step(
                    ReasoningStepType.EVIDENCE,
                    f"News sentiment slightly negative ({news_sentiment:.2f}) "
                    f"but contrarian opportunity possible",
                    confidence=sentiment_confidence,
                    evidence_refs=["news_sentiment"],
                )
            else:
                chain.add_step(
                    ReasoningStepType.EVIDENCE,
                    "Neutral news sentiment — no headwind for the trade",
                    confidence=0.5,
                    evidence_refs=["news_sentiment"],
                )
        else:
            chain.add_step(
                ReasoningStepType.EVIDENCE,
                "No news data available — relying on technicals",
                confidence=0.45,
            )

        # Step 4 (if rebuttal): Counter the bear's argument
        if bear_argument:
            chain.add_step(
                ReasoningStepType.INFERENCE,
                f"Bear argues: '{bear_argument}'. However, the risk/reward "
                f"remains favorable given confluence={confluence:.2f} and "
                f"signal strength={strength:.2f}. Bearish concerns are already "
                f"priced into stop-loss placement.",
                confidence=min(0.5 + confluence * 0.3, 0.85),
            )

        # Final step: Conclusion
        bullish_score = (bullish_count / max(total_indicators, 1)) * 0.5 + confluence * 0.3 + abs(strength) * 0.2
        action_confidence = min(0.3 + bullish_score, 0.9)
        chain.finalize(
            conclusion=(
                f"EXECUTE {side.upper()} {symbol}: technical confluence={confluence:.2f}, "
                f"bullish indicators={bullish_count}/{total_indicators}, "
                f"strength={strength:.2f}. Risk/reward favors entry."
            ),
        )

        logger.debug(
            "debate.bull.argue",
            symbol=symbol,
            confidence=chain.overall_confidence,
            steps=len(chain.steps),
        )
        return chain
