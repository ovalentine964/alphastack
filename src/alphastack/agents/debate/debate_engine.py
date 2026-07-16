"""Debate Engine — orchestrates the bull/bear/risk-arbiter debate.

Runs a structured 3-round debate on each trade signal:
  Round 1: Bull presents case (why the trade is good)
  Round 2: Bear presents case (why the trade is bad)
  Round 3: Both respond to each other's arguments

The Risk Arbiter then scores both sides and makes the final call:
  EXECUTE — proceed with the original signal
  REJECT  — discard the signal entirely
  MODIFY  — proceed with adjusted parameters (smaller size, tighter stops)

Design constraints:
  - Each round = 1 ReasoningChain (max 5 steps)
  - Total debate time < 2 seconds (pure computation, no LLM calls)
  - Full transcript logged for audit
"""

from __future__ import annotations

import copy
import time
from typing import Any

from alphastack.agents.debate.bear_agent import BearAgent
from alphastack.agents.debate.bull_agent import BullAgent
from alphastack.agents.debate.risk_arbiter import DebateResult, DebateVerdict, RiskArbiter
from alphastack.agi.reasoning import ChainOfThoughtEngine
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

# Hard budget for the entire debate (seconds)
DEBATE_BUDGET_S = 2.0


class DebateEngine:
    """Orchestrates the multi-agent debate for trade signal validation.

    The engine is stateless between calls — each ``debate()`` invocation
    runs a fresh 3-round debate on a single signal.

    Parameters
    ----------
    bull : BullAgent | None
        Bull agent (created with shared CoT engine if omitted).
    bear : BearAgent | None
        Bear agent (created with shared CoT engine if omitted).
    arbiter : RiskArbiter | None
        Risk arbiter (created if omitted).
    """

    def __init__(
        self,
        bull: BullAgent | None = None,
        bear: BearAgent | None = None,
        arbiter: RiskArbiter | None = None,
    ) -> None:
        self._cog = ChainOfThoughtEngine()
        self.bull = bull or BullAgent(cog_engine=self._cog)
        self.bear = bear or BearAgent(cog_engine=self._cog)
        self.arbiter = arbiter or RiskArbiter()

    def debate(
        self,
        signal: dict[str, Any],
        market_data: dict[str, Any],
        indicators: dict[str, float],
        news_sentiment: float | None = None,
        risk_context: dict[str, Any] | None = None,
    ) -> DebateResult:
        """Run a full 3-round debate on a trade signal.

        Parameters
        ----------
        signal : dict
            Trade signal with keys: symbol, side, strength, confluence_score, etc.
        market_data : dict
            OHLCV / order-book data.
        indicators : dict
            Technical indicator values.
        news_sentiment : float | None
            Sentiment score (-1 to 1).
        risk_context : dict | None
            Portfolio risk snapshot (drawdown, positions, etc.).

        Returns
        -------
        DebateResult
            Verdict (EXECUTE / REJECT / MODIFY) with reasoning and transcript.
        """
        start = time.monotonic()
        symbol = signal.get("symbol", "UNKNOWN")
        side = signal.get("side", "long")

        logger.info(
            "debate.start",
            symbol=symbol,
            side=side,
            strength=signal.get("strength", 0),
            confluence=signal.get("confluence_score", 0),
        )

        # ---- Round 1: Bull presents case ----
        try:
            bull_chain = self.bull.argue(
                signal=signal,
                market_data=market_data,
                indicators=indicators,
                news_sentiment=news_sentiment,
            )
        except Exception:
            logger.warning("debate.bull_crash", exc_info=True)
            return DebateResult(
                verdict=DebateVerdict.REJECT,
                reasoning="debate_agent_error",
                bull_confidence=0.0,
                bear_confidence=1.0,
                transcript=[],
            )

        # ---- Round 2: Bear presents case ----
        try:
            bear_chain = self.bear.argue(
                signal=signal,
                market_data=market_data,
                indicators=indicators,
                news_sentiment=news_sentiment,
            )
        except Exception:
            logger.warning("debate.bear_crash", exc_info=True)
            return DebateResult(
                verdict=DebateVerdict.REJECT,
                reasoning="debate_agent_error",
                bull_confidence=0.0,
                bear_confidence=1.0,
                transcript=[],
            )

        # ---- Round 3: Cross-examination (rebuttals) ----
        # Bull rebuts bear's conclusion
        try:
            bull_rebuttal = self.bull.argue(
                signal=signal,
                market_data=market_data,
                indicators=indicators,
                news_sentiment=news_sentiment,
                bear_argument=bear_chain.conclusion,
            )
        except Exception:
            logger.warning("debate.bull_rebuttal_crash", exc_info=True)
            return DebateResult(
                verdict=DebateVerdict.REJECT,
                reasoning="debate_agent_error",
                bull_confidence=0.0,
                bear_confidence=1.0,
                transcript=[],
            )

        # Bear rebuts bull's conclusion
        try:
            bear_rebuttal = self.bear.argue(
                signal=signal,
                market_data=market_data,
                indicators=indicators,
                news_sentiment=news_sentiment,
                bull_argument=bull_chain.conclusion,
            )
        except Exception:
            logger.warning("debate.bear_rebuttal_crash", exc_info=True)
            return DebateResult(
                verdict=DebateVerdict.REJECT,
                reasoning="debate_agent_error",
                bull_confidence=0.0,
                bear_confidence=1.0,
                transcript=[],
            )

        # Use rebuttal confidences (they incorporate counter-arguments)
        # Blend original + rebuttal: 40% original, 60% rebuttal
        blended_bull_chain = copy.deepcopy(bull_chain)
        blended_bull_chain.overall_confidence = round(
            bull_chain.overall_confidence * 0.4 + bull_rebuttal.overall_confidence * 0.6,
            4,
        )

        blended_bear_chain = copy.deepcopy(bear_chain)
        blended_bear_chain.overall_confidence = round(
            bear_chain.overall_confidence * 0.4 + bear_rebuttal.overall_confidence * 0.6,
            4,
        )

        # ---- Arbiter decides ----
        result = self.arbiter.adjudicate(
            signal=signal,
            bull_chain=blended_bull_chain,
            bear_chain=blended_bear_chain,
            risk_context=risk_context,
        )

        # Inject rebuttal chains into transcript
        result.transcript.insert(2, {
            "round": "3a",
            "speaker": "bull_rebuttal",
            "chain": bull_rebuttal.to_dict(),
            "confidence": bull_rebuttal.overall_confidence,
        })
        result.transcript.insert(3, {
            "round": "3b",
            "speaker": "bear_rebuttal",
            "chain": bear_rebuttal.to_dict(),
            "confidence": bear_rebuttal.overall_confidence,
        })

        elapsed_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "debate.complete",
            symbol=symbol,
            verdict=result.verdict.value,
            bull_conf=result.bull_confidence,
            bear_conf=result.bear_confidence,
            elapsed_ms=elapsed_ms,
            budget_exceeded=elapsed_ms > DEBATE_BUDGET_S * 1000,
        )

        return result

    def debate_batch(
        self,
        signals: list[dict[str, Any]],
        market_data: dict[str, Any],
        indicators: dict[str, float],
        news_sentiment: float | None = None,
        risk_context: dict[str, Any] | None = None,
    ) -> list[DebateResult]:
        """Run debates on multiple signals sequentially.

        Returns a list of DebateResult in the same order as the input signals.
        """
        results: list[DebateResult] = []
        for sig in signals:
            result = self.debate(
                signal=sig,
                market_data=market_data,
                indicators=indicators,
                news_sentiment=news_sentiment,
                risk_context=risk_context,
            )
            results.append(result)
        return results
