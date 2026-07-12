"""Step 16: Trade Journal — log all decisions, performance tracking, learning loop input."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from alphastack.strategy.context import AlphaStackContext, JournalEntry
from alphastack.strategy.steps.base import AlphaStackStep

logger = logging.getLogger("alphastack.step.16_journal")


class TradeJournal(AlphaStackStep):
    step_number = 16
    step_name = "trade_journal"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        direction = context.confluence.direction

        # Build tags from active signals
        tags: list[str] = []
        if context.fundamental.bias.value != "neutral":
            tags.append(f"fundamental_{context.fundamental.bias.value}")
        if context.bias.bias.value != "neutral":
            tags.append(f"bias_{context.bias.bias.value}")
        if context.structure.direction.value != "none":
            tags.append(f"structure_{context.structure.direction.value}")
        if context.rsi.divergence != "none":
            tags.append(f"rsi_div_{context.rsi.divergence}")
        for p in context.candlestick.patterns:
            tags.append(f"candle_{p.name}")
        if context.exit_signal.should_exit:
            tags.append("exit_signal")

        # Build notes summary
        notes_parts: list[str] = []
        notes_parts.append(f"Confluence: {context.confluence.score:.0f}/100 ({direction.value})")
        notes_parts.append(f"Session: {context.session.active.value}, volatility={context.session.volatility:.2f}")
        notes_parts.append(f"Structure: {context.structure.structure_type.value}")
        notes_parts.append(f"RSI: {context.rsi.value} ({context.rsi.signal})")
        if context.stop_loss.price:
            notes_parts.append(f"SL: {context.stop_loss.price} ({context.stop_loss.stop_type})")
        if context.take_profit.levels:
            notes_parts.append(f"TP: {context.take_profit.levels} R:R={context.take_profit.rr_ratio}")
        if context.exit_signal.should_exit:
            notes_parts.append(f"EXIT: {context.exit_signal.reason}")

        # Component scores
        if context.confluence.component_scores:
            score_str = ", ".join(
                f"{k}={v:.2f}" for k, v in context.confluence.component_scores.items()
            )
            notes_parts.append(f"Scores: {score_str}")

        journal = JournalEntry(
            timestamp=context.timestamp,
            symbol=context.symbol,
            direction=direction,
            entry_price=context.market_data.get("close", 0.0),
            stop_loss=context.stop_loss.price,
            take_profit=context.take_profit.levels,
            position_size=context.sizing.position_size,
            confluence_score=context.confluence.score,
            notes="\n".join(notes_parts),
            tags=tags,
        )

        # Structured log for downstream consumers
        logger.info(
            "JOURNAL | %s | %s | conf=%.0f | SL=%.5f | TP=%s | size=%.2f | tags=%s",
            context.symbol,
            direction.value,
            context.confluence.score,
            context.stop_loss.price,
            context.take_profit.levels,
            context.sizing.position_size,
            tags,
        )

        # Also emit machine-readable JSON line for log aggregation
        try:
            entry_dict = journal.model_dump(mode="json")
            logger.info("JOURNAL_JSON %s", json.dumps(entry_dict, default=str))
        except Exception:
            pass

        return context.update(journal=journal)
