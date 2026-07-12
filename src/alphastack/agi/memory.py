"""Episodic memory for trade experiences."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass
class TradeEpisode:
    """A recorded trade episode for learning."""
    episode_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    symbol: str = ""
    direction: str = ""  # "long" | "short"
    entry_price: float = 0.0
    exit_price: float = 0.0
    entry_time: float = field(default_factory=time.time)
    exit_time: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    reasoning_chain_id: str = ""
    indicators: dict[str, float] = field(default_factory=dict)
    market_context: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""  # "win" | "loss" | "breakeven"
    lessons: list[str] = field(default_factory=list)
    is_long_term: bool = False  # consolidated to long-term memory

    def finalize(self) -> None:
        """Set outcome based on P&L."""
        if self.pnl > 0:
            self.outcome = "win"
        elif self.pnl < 0:
            self.outcome = "loss"
        else:
            self.outcome = "breakeven"

    def similarity_score(self, other: TradeEpisode) -> float:
        """Compute similarity to another episode (0–1).

        Considers symbol match, direction, indicator proximity, and
        market context overlap.
        """
        score = 0.0
        weights_total = 0.0

        # Symbol match (weight: 0.2)
        if self.symbol == other.symbol:
            score += 0.2
        weights_total += 0.2

        # Direction match (weight: 0.15)
        if self.direction == other.direction:
            score += 0.15
        weights_total += 0.15

        # Indicator proximity (weight: 0.35)
        common_indicators = set(self.indicators.keys()) & set(other.indicators.keys())
        if common_indicators:
            diffs = []
            for k in common_indicators:
                v1, v2 = self.indicators[k], other.indicators[k]
                max_val = max(abs(v1), abs(v2), 1e-10)
                diffs.append(1.0 - min(abs(v1 - v2) / max_val, 1.0))
            score += 0.35 * (sum(diffs) / len(diffs))
        weights_total += 0.35

        # Market context overlap (weight: 0.3)
        common_ctx = set(self.market_context.keys()) & set(other.market_context.keys())
        if common_ctx:
            matches = sum(
                1 for k in common_ctx
                if self.market_context[k] == other.market_context[k]
            )
            score += 0.3 * (matches / len(common_ctx))
        weights_total += 0.3

        return round(score / weights_total if weights_total > 0 else 0.0, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "outcome": self.outcome,
            "lessons": self.lessons,
            "is_long_term": self.is_long_term,
        }


class EpisodicMemory:
    """Store, retrieve, and consolidate trade episodes.

    Provides similarity-based retrieval and automatic consolidation
    of short-term episodes into long-term memory.
    """

    def __init__(self, consolidation_threshold: int = 50) -> None:
        self._short_term: dict[str, TradeEpisode] = {}
        self._long_term: dict[str, TradeEpisode] = {}
        self._consolidation_threshold = consolidation_threshold

    def store(self, episode: TradeEpisode) -> str:
        """Store a trade episode in short-term memory."""
        self._short_term[episode.episode_id] = episode
        # Auto-consolidate if threshold exceeded
        if len(self._short_term) > self._consolidation_threshold:
            self.consolidate()
        return episode.episode_id

    def retrieve(self, episode_id: str) -> TradeEpisode | None:
        """Retrieve an episode by ID from either memory tier."""
        return self._short_term.get(episode_id) or self._long_term.get(episode_id)

    def find_similar(
        self,
        reference: TradeEpisode,
        top_k: int = 5,
        long_term_only: bool = False,
    ) -> list[tuple[TradeEpisode, float]]:
        """Find the most similar episodes to a reference.

        Args:
            reference: The episode to compare against.
            top_k: Number of results to return.
            long_term_only: If True, only search long-term memory.

        Returns:
            List of (episode, similarity_score) tuples, sorted descending.
        """
        pool = self._long_term if long_term_only else {
            **self._short_term, **self._long_term
        }
        scored = [
            (ep, reference.similarity_score(ep))
            for ep in pool.values()
            if ep.episode_id != reference.episode_id
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def get_lessons(self, symbol: str | None = None) -> list[str]:
        """Aggregate lessons from past episodes.

        Args:
            symbol: Optional filter by symbol.

        Returns:
            Deduplicated list of lessons.
        """
        all_episodes = list(self._short_term.values()) + list(self._long_term.values())
        lessons: list[str] = []
        for ep in all_episodes:
            if symbol and ep.symbol != symbol:
                continue
            lessons.extend(ep.lessons)
        # Deduplicate preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for lesson in lessons:
            if lesson not in seen:
                seen.add(lesson)
                unique.append(lesson)
        return unique

    def consolidate(self) -> int:
        """Move older short-term episodes to long-term memory.

        Keeps the most recent 20% in short-term; moves the rest.
        Returns the number of episodes consolidated.
        """
        if not self._short_term:
            return 0

        sorted_eps = sorted(
            self._short_term.values(),
            key=lambda e: e.entry_time,
        )
        keep_count = max(1, len(sorted_eps) // 5)
        to_consolidate = sorted_eps[:-keep_count] if keep_count < len(sorted_eps) else []

        for ep in to_consolidate:
            ep.is_long_term = True
            self._long_term[ep.episode_id] = ep
            del self._short_term[ep.episode_id]

        return len(to_consolidate)

    def stats(self) -> dict[str, Any]:
        """Return memory statistics."""
        all_eps = list(self._short_term.values()) + list(self._long_term.values())
        wins = sum(1 for e in all_eps if e.outcome == "win")
        losses = sum(1 for e in all_eps if e.outcome == "loss")
        return {
            "short_term_count": len(self._short_term),
            "long_term_count": len(self._long_term),
            "total_episodes": len(all_eps),
            "win_rate": round(wins / max(len(all_eps), 1), 4),
            "loss_rate": round(losses / max(len(all_eps), 1), 4),
        }
