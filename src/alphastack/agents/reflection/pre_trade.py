"""Pre-Trade Signal Reflection — quality gate before risk assessment.

Runs chain-of-thought reasoning on each strategy signal to answer:
"Is this signal actually good enough to send to the risk agent?"

Decisions:
- APPROVE  → signal passes through unchanged
- REJECT   → signal is dropped; skips to END
- MODIFY   → signal parameters adjusted (size, SL, TP)
"""

from __future__ import annotations

from typing import Any, Literal

from alphastack.agents.base import AlphaStackAgent
from alphastack.agi.reasoning import ChainOfThoughtEngine, ReasoningChain, ReasoningStepType
from alphastack.core.events import EventBus
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

# Thresholds (could be loaded from config)
MIN_CONFIDENCE = 0.45
MIN_CONFLUENCE = 0.30
MAX_RECENT_CONFLICTS = 2


class PreTradeReflection(AlphaStackAgent):
    """Pre-trade signal quality gate using chain-of-thought reasoning.

    Sits between the Strategy and Risk agents.  Each signal is scored
    through a reasoning chain; only signals that pass move forward.
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__(
            name="pre_trade_reflection",
            role="gatekeeper",
            description="Pre-trade signal quality reflection",
            event_bus=event_bus,
        )
        self._engine = ChainOfThoughtEngine()

    def system_prompt(self) -> str:
        return (
            "You are the Pre-Trade Reflection Agent. Before any signal "
            "reaches the risk engine, you evaluate whether it's worth "
            "taking. Check regime fit, confidence, and conflict with "
            "recent trades. Approve, reject, or modify."
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Reflect on every signal and return a verdict per signal."""
        signals = state.get("signals", [])
        pipeline_ctx = state.get("pipeline_context", {})
        recent_decisions = state.get("trade_decisions", [])
        market_data = state.get("market_data", {})

        if not signals:
            logger.info("pre_trade_reflection.no_signals")
            return {
                "pre_trade_reflection": {
                    "verdict": "APPROVE",
                    "reasoning": "No signals to evaluate",
                    "confidence": 1.0,
                    "signal_verdicts": [],
                },
                "_confidence": 1.0,
            }

        verdicts: list[dict[str, Any]] = []
        overall_verdict: Literal["APPROVE", "REJECT", "MODIFY"] = "APPROVE"
        overall_reasoning_parts: list[str] = []

        for i, signal in enumerate(signals):
            chain = self._engine.start_chain(
                topic=f"Pre-trade reflection: {signal.symbol} {signal.side}"
            )
            verdict = self._evaluate_signal(
                chain, signal, pipeline_ctx, recent_decisions, market_data,
            )
            verdicts.append(verdict)

            # Aggregate: any REJECT → overall REJECT; any MODIFY (without reject) → MODIFY
            if verdict["verdict"] == "REJECT":
                overall_verdict = "REJECT"
                overall_reasoning_parts.append(
                    f"Signal {i} ({signal.symbol}): REJECTED — {verdict['reasoning']}"
                )
            elif verdict["verdict"] == "MODIFY" and overall_verdict != "REJECT":
                overall_verdict = "MODIFY"
                overall_reasoning_parts.append(
                    f"Signal {i} ({signal.symbol}): MODIFIED — {verdict['reasoning']}"
                )
            else:
                overall_reasoning_parts.append(
                    f"Signal {i} ({signal.symbol}): APPROVED — {verdict['reasoning']}"
                )

        # Apply modifications to signals in-place if needed
        if overall_verdict == "MODIFY":
            self._apply_modifications(signals, verdicts)

        reflection_result = {
            "verdict": overall_verdict,
            "reasoning": " | ".join(overall_reasoning_parts),
            "confidence": self._aggregate_confidence(verdicts),
            "signal_verdicts": verdicts,
        }

        logger.info(
            "pre_trade_reflection.complete",
            verdict=overall_verdict,
            signal_count=len(signals),
        )

        return {
            "pre_trade_reflection": reflection_result,
            "signals": signals,
            "_confidence": reflection_result["confidence"],
        }

    def _evaluate_signal(
        self,
        chain: ReasoningChain,
        signal: Any,
        pipeline_ctx: dict[str, Any],
        recent_decisions: list[Any],
        market_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Run reasoning chain on a single signal. Returns verdict dict."""
        side = getattr(signal, "side", "flat")
        strength = abs(getattr(signal, "strength", 0))
        confluence = getattr(signal, "confluence_score", 0)
        symbol = getattr(signal, "symbol", "?")

        # Step 1: Observe signal properties
        chain.add_step(
            ReasoningStepType.OBSERVATION,
            f"Signal: {side} {symbol}, strength={strength:.2f}, confluence={confluence:.2f}",
            confidence=0.95,
        )

        # Step 2: Check confidence threshold
        if strength < MIN_CONFIDENCE:
            chain.add_step(
                ReasoningStepType.EVIDENCE,
                f"Strength {strength:.2f} below minimum {MIN_CONFIDENCE}",
                confidence=0.2,
            )
            chain.finalize("REJECT — signal strength too low")
            return {
                "verdict": "REJECT",
                "reasoning": f"Strength {strength:.2f} < {MIN_CONFIDENCE}",
                "confidence": chain.overall_confidence,
                "chain": chain.to_dict(),
            }

        # Step 3: Check confluence
        if confluence < MIN_CONFLUENCE:
            chain.add_step(
                ReasoningStepType.EVIDENCE,
                f"Confluence {confluence:.2f} below minimum {MIN_CONFLUENCE}",
                confidence=0.25,
            )
            chain.finalize("REJECT — insufficient confluence")
            return {
                "verdict": "REJECT",
                "reasoning": f"Confluence {confluence:.2f} < {MIN_CONFLUENCE}",
                "confidence": chain.overall_confidence,
                "chain": chain.to_dict(),
            }

        chain.add_step(
            ReasoningStepType.EVIDENCE,
            "Strength and confluence above thresholds",
            confidence=0.8,
        )

        # Step 4: Check market regime alignment
        regime = pipeline_ctx.get("market_regime", "unknown")
        regime_confidence = self._check_regime_fit(side, regime)
        chain.add_step(
            ReasoningStepType.HYPOTHESIS,
            f"Market regime '{regime}' — fit score {regime_confidence:.2f}",
            confidence=regime_confidence,
        )

        # Step 5: Check for conflicts with recent trades
        conflicts = self._count_conflicts(symbol, side, recent_decisions)
        if conflicts > MAX_RECENT_CONFLICTS:
            chain.add_step(
                ReasoningStepType.EVIDENCE,
                f"{conflicts} conflicting recent trades (max {MAX_RECENT_CONFLICTS})",
                confidence=0.3,
            )
            chain.finalize("REJECT — too many conflicting recent trades")
            return {
                "verdict": "REJECT",
                "reasoning": f"{conflicts} recent conflicts > {MAX_RECENT_CONFLICTS}",
                "confidence": chain.overall_confidence,
                "chain": chain.to_dict(),
            }

        chain.add_step(
            ReasoningStepType.EVIDENCE,
            f"{conflicts} recent conflicts — within tolerance",
            confidence=0.75,
        )

        # Step 6: Decide — adjust parameters if regime fit is mediocre
        if regime_confidence < 0.5:
            # MODIFY: reduce size, tighten stops
            size_factor = max(0.5, regime_confidence)
            chain.add_step(
                ReasoningStepType.INFERENCE,
                f"Regime fit mediocre — reducing position to {size_factor:.0%}",
                confidence=0.6,
            )
            chain.finalize(f"MODIFY — reduce size to {size_factor:.0%}")
            return {
                "verdict": "MODIFY",
                "reasoning": f"Regime fit {regime_confidence:.2f} — size reduced to {size_factor:.0%}",
                "confidence": chain.overall_confidence,
                "chain": chain.to_dict(),
                "modifications": {
                    "size_factor": round(size_factor, 2),
                    "sl_factor": 0.8,  # tighten stop loss by 20%
                },
            }

        # Full approval
        chain.add_step(
            ReasoningStepType.INFERENCE,
            "Signal passes all quality gates",
            confidence=0.85,
        )
        chain.finalize("APPROVE")
        return {
            "verdict": "APPROVE",
            "reasoning": "Signal passes all quality checks",
            "confidence": chain.overall_confidence,
            "chain": chain.to_dict(),
        }

    @staticmethod
    def _check_regime_fit(side: str, regime: str) -> float:
        """Return 0-1 score for how well the signal side fits the regime."""
        if regime == "unknown":
            return 0.5
        bullish = regime in ("trending_up", "bull", "uptrend")
        bearish = regime in ("trending_down", "bear", "downtrend")
        if side == "long" and bullish:
            return 0.9
        if side == "short" and bearish:
            return 0.9
        if side == "flat":
            return 0.5
        if (side == "long" and bearish) or (side == "short" and bullish):
            return 0.3
        return 0.6  # neutral / ranging regime

    @staticmethod
    def _count_conflicts(symbol: str, side: str, recent_decisions: list[Any]) -> int:
        """Count recent decisions that conflict with this signal."""
        conflicts = 0
        for d in recent_decisions[-10:]:  # last 10 decisions
            d_symbol = getattr(d, "symbol", d.get("symbol", "") if isinstance(d, dict) else "")
            d_action = getattr(d, "action", d.get("action", "") if isinstance(d, dict) else "")
            d_status = getattr(d, "status", d.get("status", "") if isinstance(d, dict) else "")
            if d_symbol != symbol or d_status != "approved":
                continue
            if (side == "long" and d_action == "sell") or (side == "short" and d_action == "buy"):
                conflicts += 1
        return conflicts

    @staticmethod
    def _apply_modifications(signals: list[Any], verdicts: list[dict[str, Any]]) -> None:
        """Apply MODIFY verdicts to adjust signal parameters."""
        for signal, verdict in zip(signals, verdicts):
            if verdict.get("verdict") != "MODIFY":
                continue
            mods = verdict.get("modifications", {})
            size_factor = mods.get("size_factor", 1.0)
            sl_factor = mods.get("sl_factor", 1.0)

            # Adjust stop loss (tighten)
            sl = getattr(signal, "stop_loss", None)
            if sl is not None:
                new_sl = sl * sl_factor
                object.__setattr__(signal, "stop_loss", round(new_sl, 6))

            # Store size factor for risk agent to pick up
            verdict["applied_modifications"] = {
                "size_factor": size_factor,
                "sl_adjusted": sl is not None,
            }

    @staticmethod
    def _aggregate_confidence(verdicts: list[dict[str, Any]]) -> float:
        """Weighted average confidence across all signal verdicts."""
        if not verdicts:
            return 1.0
        total = sum(v.get("confidence", 0) for v in verdicts)
        return round(total / len(verdicts), 4)
