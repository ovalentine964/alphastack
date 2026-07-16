"""Episodic memory for trade experiences.

Includes bounded memory with forced prioritization — hard caps that
force quality over quantity, impact-based eviction, and prioritized
retrieval.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
import uuid
import math


# ── Hard caps for bounded memory ──────────────────────────────────────
MAX_PATTERNS: int = 50          # only keep the 50 most impactful patterns
MAX_TRADES: int = 500           # only keep last 500 trades
MAX_ENTRY_CHARS: int = 2000     # force concise entries
MAX_REASONING_CHAINS: int = 100 # cap stored reasoning chains
CLEANUP_INTERVAL: int = 20      # prune every N trades
MIN_IMPACT_THRESHOLD: float = 0.01  # floor for impact scores
DEFAULT_IMPACT_SCORE: float = 0.1   # backward-compat default
RECENCY_HALF_LIFE: float = 7 * 24 * 3600  # 7 days in seconds


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
    impact_score: float = DEFAULT_IMPACT_SCORE  # bounded memory impact
    summary: str = ""  # concise summary (MAX_ENTRY_CHARS max)

    def finalize(self, confidence: float = 0.5) -> None:
        """Set outcome based on P&L and compute impact score.

        Args:
            confidence: Reasoning confidence (0–1) from the chain that
                produced this trade.  Defaults to 0.5 when unknown.
        """
        if self.pnl > 0:
            self.outcome = "win"
        elif self.pnl < 0:
            self.outcome = "loss"
        else:
            self.outcome = "breakeven"
        # Compute impact if not already set (backward compat)
        if self.impact_score == DEFAULT_IMPACT_SCORE:
            self.impact_score = self.compute_impact(confidence)
        # Auto-generate summary if empty
        if not self.summary:
            self.summary = self._generate_summary()
            # Enforce char limit
            self.summary = self.summary[:MAX_ENTRY_CHARS]

    def compute_impact(self, confidence: float = 0.5) -> float:
        """Compute impact score = |pnl_pct| * confidence * recency_weight.

        Returns a value >= MIN_IMPACT_THRESHOLD.
        """
        recency = self._recency_weight()
        raw = abs(self.pnl_pct) * max(0.01, confidence) * recency
        return max(MIN_IMPACT_THRESHOLD, round(raw, 6))

    def _recency_weight(self) -> float:
        """Exponential decay based on age.  Half-life = RECENCY_HALF_LIFE."""
        age = time.time() - self.entry_time
        if age <= 0:
            return 1.0
        return math.exp(-0.693 * age / RECENCY_HALF_LIFE)

    def _generate_summary(self) -> str:
        """Create a concise one-line summary of this trade."""
        parts = [
            f"{self.symbol} {self.direction} "
            f"{self.entry_price:.2f}->{self.exit_price:.2f} "
            f"pnl={self.pnl:+.2f} ({self.pnl_pct:+.2%})",
        ]
        if self.lessons:
            parts.append(f"Lessons: {'; '.join(self.lessons[:3])}")
        return " | ".join(parts)

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
            "impact_score": self.impact_score,
            "summary": self.summary,
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
        self._max_episodes: int = 500

    def store(self, episode: TradeEpisode) -> str:
        """Store a trade episode in short-term memory."""
        self._short_term[episode.episode_id] = episode
        # Auto-consolidate if threshold exceeded
        if len(self._short_term) > self._consolidation_threshold:
            self.consolidate()
        # Enforce hard cap: remove lowest-impact episodes from long-term
        total = len(self._short_term) + len(self._long_term)
        if total > self._max_episodes and self._long_term:
            excess = total - self._max_episodes
            sorted_lt = sorted(self._long_term.values(), key=lambda e: e.impact_score)
            for ep in sorted_lt[:excess]:
                del self._long_term[ep.episode_id]
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


# ── Learned Pattern ──────────────────────────────────────────────────


@dataclass
class LearnedPattern:
    """A pattern distilled from multiple trade episodes."""
    pattern_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    symbol: str = ""  # empty = cross-symbol
    conditions: dict[str, Any] = field(default_factory=dict)
    expected_edge: float = 0.0  # expected pnl_pct edge
    sample_count: int = 0  # how many trades formed this pattern
    impact_score: float = DEFAULT_IMPACT_SCORE
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description[:MAX_ENTRY_CHARS],
            "symbol": self.symbol,
            "conditions": self.conditions,
            "expected_edge": self.expected_edge,
            "sample_count": self.sample_count,
            "impact_score": self.impact_score,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
        }


# ── Eviction Insight ─────────────────────────────────────────────────


@dataclass
class EvictionInsight:
    """A single-line insight summarizing an evicted entry."""
    original_id: str = ""
    insight: str = ""
    impact_score: float = 0.0
    evicted_at: float = field(default_factory=time.time)


# ── Bounded Memory ───────────────────────────────────────────────────


class BoundedMemory:
    """Wraps EpisodicMemory with hard capacity limits and impact-based eviction.

    Enforces:
      - MAX_TRADES  (500)  — oldest / lowest-impact trades evicted first
      - MAX_PATTERNS (50)  — lowest-impact patterns evicted first
      - MAX_ENTRY_CHARS (2000) — summaries truncated on store

    When a limit is reached the *lowest impact* entry is evicted (not
    the oldest).  Each eviction produces a one-line EvictionInsight.
    Every CLEANUP_INTERVAL stores, low-impact entries are pruned.
    """

    def __init__(self, max_trades: int = MAX_TRADES,
                 max_patterns: int = MAX_PATTERNS) -> None:
        self._episodes: dict[str, TradeEpisode] = {}
        self._patterns: dict[str, LearnedPattern] = {}
        self._eviction_log: list[EvictionInsight] = []
        self._insights: list[str] = []  # distilled from evictions
        self._max_trades = max_trades
        self._max_patterns = max_patterns
        self._store_count: int = 0

    # ── Episode CRUD ──────────────────────────────────────────────

    def store_episode(self, episode: TradeEpisode,
                      confidence: float = 0.5) -> str:
        """Store an episode, enforcing bounds.

        Enforces MAX_ENTRY_CHARS on summary.  Triggers periodic cleanup
        every CLEANUP_INTERVAL stores.
        """
        # Ensure finalized (impact computed)
        if episode.outcome == "":
            episode.finalize(confidence)
        # Enforce summary length
        episode.summary = episode.summary[:MAX_ENTRY_CHARS]

        self._episodes[episode.episode_id] = episode
        self._store_count += 1

        # Evict if over limit
        while len(self._episodes) > self._max_trades:
            self._evict_lowest_impact_episode()

        # Periodic cleanup
        if self._store_count % CLEANUP_INTERVAL == 0:
            self._periodic_cleanup()

        return episode.episode_id

    def get_episode(self, episode_id: str) -> TradeEpisode | None:
        return self._episodes.get(episode_id)

    def all_episodes(self) -> list[TradeEpisode]:
        return list(self._episodes.values())

    def episode_count(self) -> int:
        return len(self._episodes)

    # ── Pattern CRUD ──────────────────────────────────────────────

    def store_pattern(self, pattern: LearnedPattern) -> str:
        """Store a pattern, enforcing MAX_PATTERNS."""
        pattern.description = pattern.description[:MAX_ENTRY_CHARS]
        self._patterns[pattern.pattern_id] = pattern

        while len(self._patterns) > self._max_patterns:
            self._evict_lowest_impact_pattern()

        return pattern.pattern_id

    def get_pattern(self, pattern_id: str) -> LearnedPattern | None:
        return self._patterns.get(pattern_id)

    def all_patterns(self) -> list[LearnedPattern]:
        return list(self._patterns.values())

    def pattern_count(self) -> int:
        return len(self._patterns)

    # ── Prioritized Retrieval ─────────────────────────────────────

    def query_episodes(
        self,
        top_k: int = 10,
        symbol: str | None = None,
        min_impact: float = MIN_IMPACT_THRESHOLD,
    ) -> list[TradeEpisode]:
        """Return top-K episodes by impact score, optionally filtered.

        Sorted descending by impact_score.  Entries below min_impact
        are excluded.
        """
        candidates = [
            ep for ep in self._episodes.values()
            if ep.impact_score >= min_impact
            and (symbol is None or ep.symbol == symbol)
        ]
        candidates.sort(key=lambda e: e.impact_score, reverse=True)
        return candidates[:top_k]

    def query_patterns(
        self,
        top_k: int = 10,
        symbol: str | None = None,
        min_impact: float = MIN_IMPACT_THRESHOLD,
    ) -> list[LearnedPattern]:
        """Return top-K patterns by impact score."""
        candidates = [
            p for p in self._patterns.values()
            if p.impact_score >= min_impact
            and (symbol is None or p.symbol == symbol or p.symbol == "")
        ]
        candidates.sort(key=lambda p: p.impact_score, reverse=True)
        return candidates[:top_k]

    # ── Eviction Logic ────────────────────────────────────────────

    def _evict_lowest_impact_episode(self) -> None:
        """Remove the episode with the lowest impact score.

        Before removal, distill a one-line insight.
        """
        if not self._episodes:
            return
        victim = min(self._episodes.values(), key=lambda e: e.impact_score)
        insight = EvictionInsight(
            original_id=victim.episode_id,
            insight=self._distill_insight(victim),
            impact_score=victim.impact_score,
        )
        self._eviction_log.append(insight)
        self._insights.append(insight.insight)
        # Keep insights list bounded
        if len(self._insights) > self._max_trades:
            self._insights = self._insights[-self._max_trades:]
        del self._episodes[victim.episode_id]

    def _evict_lowest_impact_pattern(self) -> None:
        """Remove the pattern with the lowest impact score."""
        if not self._patterns:
            return
        victim = min(self._patterns.values(), key=lambda p: p.impact_score)
        insight = EvictionInsight(
            original_id=victim.pattern_id,
            insight=f"Pattern '{victim.name}' evicted (impact={victim.impact_score:.4f}, "
                    f"samples={victim.sample_count}, edge={victim.expected_edge:+.2%})",
            impact_score=victim.impact_score,
        )
        self._eviction_log.append(insight)
        self._insights.append(insight.insight)
        del self._patterns[victim.pattern_id]

    def _distill_insight(self, ep: TradeEpisode) -> str:
        """Create a single-line insight from an evicted episode."""
        return (
            f"{ep.symbol} {ep.direction} pnl={ep.pnl:+.2f} "
            f"({ep.pnl_pct:+.2%}) impact={ep.impact_score:.4f}: "
            f"{' | '.join(ep.lessons[:2]) if ep.lessons else 'no lessons'}"
        )

    def _periodic_cleanup(self) -> int:
        """Prune low-impact episodes to stay healthy.

        Removes episodes in the bottom 10th percentile of impact.
        Returns count of pruned episodes.
        """
        if len(self._episodes) < 10:
            return 0
        sorted_eps = sorted(self._episodes.values(), key=lambda e: e.impact_score)
        cutoff_idx = max(1, len(sorted_eps) // 10)
        cutoff_impact = sorted_eps[cutoff_idx - 1].impact_score
        # Only prune if cutoff is truly low
        if cutoff_impact >= MIN_IMPACT_THRESHOLD * 2:
            return 0
        pruned = 0
        for ep in sorted_eps[:cutoff_idx]:
            if ep.episode_id in self._episodes:
                insight = EvictionInsight(
                    original_id=ep.episode_id,
                    insight=self._distill_insight(ep),
                    impact_score=ep.impact_score,
                )
                self._eviction_log.append(insight)
                self._insights.append(insight.insight)
                del self._episodes[ep.episode_id]
                pruned += 1
        return pruned

    # ── Insights Access ───────────────────────────────────────────

    def get_insights(self, last_n: int = 20) -> list[str]:
        """Return the most recent distilled insights from evictions."""
        return self._insights[-last_n:]

    def get_eviction_log(self) -> list[EvictionInsight]:
        return list(self._eviction_log)

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        eps = list(self._episodes.values())
        wins = sum(1 for e in eps if e.outcome == "win")
        losses = sum(1 for e in eps if e.outcome == "loss")
        impacts = [e.impact_score for e in eps]
        return {
            "episode_count": len(eps),
            "episode_cap": self._max_trades,
            "pattern_count": len(self._patterns),
            "pattern_cap": self._max_patterns,
            "win_rate": round(wins / max(len(eps), 1), 4),
            "loss_rate": round(losses / max(len(eps), 1), 4),
            "avg_impact": round(sum(impacts) / max(len(impacts), 1), 6),
            "min_impact": round(min(impacts), 6) if impacts else 0.0,
            "max_impact": round(max(impacts), 6) if impacts else 0.0,
            "total_evictions": len(self._eviction_log),
            "total_insights": len(self._insights),
            "store_count": self._store_count,
        }


# ── Prioritized Retrieval ────────────────────────────────────────────


class PrioritizedRetrieval:
    """Query engine that returns entries ranked by relevance × impact.

    Wraps a BoundedMemory and provides:
      - Combined scoring: relevance (similarity) × impact_score
      - Minimum impact threshold filtering
      - Top-N results sorted by combined score
    """

    def __init__(self, memory: BoundedMemory) -> None:
        self._memory = memory

    def query(
        self,
        reference: TradeEpisode,
        top_k: int = 5,
        min_impact: float = MIN_IMPACT_THRESHOLD,
        relevance_weight: float = 0.5,
        impact_weight: float = 0.5,
    ) -> list[tuple[TradeEpisode, float]]:
        """Find most relevant episodes by similarity × impact.

        Args:
            reference: Episode to compare against.
            top_k: Number of results.
            min_impact: Minimum impact threshold.
            relevance_weight: Weight for similarity score.
            impact_weight: Weight for impact score.

        Returns:
            List of (episode, combined_score) sorted descending.
        """
        candidates = [
            ep for ep in self._memory.all_episodes()
            if ep.episode_id != reference.episode_id
            and ep.impact_score >= min_impact
        ]

        scored: list[tuple[TradeEpisode, float]] = []
        for ep in candidates:
            relevance = reference.similarity_score(ep)
            combined = (relevance_weight * relevance +
                        impact_weight * ep.impact_score)
            scored.append((ep, round(combined, 6)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def query_by_symbol(
        self,
        symbol: str,
        top_k: int = 10,
        min_impact: float = MIN_IMPACT_THRESHOLD,
    ) -> list[TradeEpisode]:
        """Return top episodes for a symbol, ranked by impact."""
        return self._memory.query_episodes(
            top_k=top_k, symbol=symbol, min_impact=min_impact,
        )

    def query_worst(
        self,
        top_k: int = 5,
        symbol: str | None = None,
    ) -> list[TradeEpisode]:
        """Return the worst trades (most negative pnl) for learning."""
        eps = self._memory.all_episodes()
        if symbol:
            eps = [e for e in eps if e.symbol == symbol]
        eps.sort(key=lambda e: e.pnl)
        return eps[:top_k]

    def query_best(
        self,
        top_k: int = 5,
        symbol: str | None = None,
    ) -> list[TradeEpisode]:
        """Return the best trades (highest pnl) for reinforcement."""
        eps = self._memory.all_episodes()
        if symbol:
            eps = [e for e in eps if e.symbol == symbol]
        eps.sort(key=lambda e: e.pnl, reverse=True)
        return eps[:top_k]
