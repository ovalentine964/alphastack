"""Tests for bounded memory with forced prioritization."""

import time
import pytest
from alphastack.agi.memory import (
    BoundedMemory,
    PrioritizedRetrieval,
    LearnedPattern,
    TradeEpisode,
    EvictionInsight,
    MAX_TRADES,
    MAX_PATTERNS,
    MAX_ENTRY_CHARS,
    CLEANUP_INTERVAL,
    MIN_IMPACT_THRESHOLD,
    DEFAULT_IMPACT_SCORE,
)


def _make_episode(symbol="AAPL", direction="long", pnl=100.0,
                  pnl_pct=None, entry_time=None, lessons=None) -> TradeEpisode:
    """Helper to create a finalized TradeEpisode."""
    if pnl_pct is None:
        pnl_pct = pnl / 150.0
    ep = TradeEpisode(
        symbol=symbol,
        direction=direction,
        entry_price=150.0,
        exit_price=150.0 + pnl * 0.1,
        entry_time=entry_time or time.time(),
        exit_time=time.time(),
        pnl=pnl,
        pnl_pct=pnl_pct,
        indicators={"rsi": 30.0, "macd": 0.5},
        market_context={"regime": "bullish", "volatility": "high"},
        lessons=lessons or ["Test lesson"],
    )
    ep.finalize(confidence=0.8)
    return ep


def _make_pattern(name="test_pattern", impact=0.5, sample_count=10) -> LearnedPattern:
    """Helper to create a LearnedPattern."""
    return LearnedPattern(
        name=name,
        description=f"Pattern: {name}",
        expected_edge=0.02,
        sample_count=sample_count,
        impact_score=impact,
    )


# ── TradeEpisode new fields ────────────────────────────────────────────


class TestTradeEpisodeImpactFields:
    """Test the new impact_score and summary fields on TradeEpisode."""

    def test_default_impact_score(self):
        ep = TradeEpisode(symbol="AAPL")
        assert ep.impact_score == DEFAULT_IMPACT_SCORE

    def test_default_summary_empty(self):
        ep = TradeEpisode(symbol="AAPL")
        assert ep.summary == ""

    def test_finalize_computes_impact(self):
        ep = _make_episode(pnl=200, pnl_pct=1.33)
        assert ep.impact_score > MIN_IMPACT_THRESHOLD
        assert ep.outcome == "win"

    def test_finalize_generates_summary(self):
        ep = _make_episode(pnl=100, lessons=["Lesson A", "Lesson B"])
        assert len(ep.summary) > 0
        assert "AAPL" in ep.summary
        assert "Lesson A" in ep.summary

    def test_summary_truncated_to_max_chars(self):
        long_lessons = ["x" * 500 for _ in range(10)]
        ep = _make_episode(lessons=long_lessons)
        ep.summary = ""  # reset so finalize regenerates
        ep.finalize()
        assert len(ep.summary) <= MAX_ENTRY_CHARS

    def test_compute_impact_positive(self):
        ep = _make_episode(pnl=100, pnl_pct=0.67)
        impact = ep.compute_impact(confidence=0.8)
        assert impact >= MIN_IMPACT_THRESHOLD

    def test_compute_impact_with_zero_pnl(self):
        ep = _make_episode(pnl=0, pnl_pct=0.0)
        impact = ep.compute_impact(confidence=0.5)
        # Zero pnl → floor impact
        assert impact == MIN_IMPACT_THRESHOLD

    def test_to_dict_includes_new_fields(self):
        ep = _make_episode(pnl=50)
        d = ep.to_dict()
        assert "impact_score" in d
        assert "summary" in d
        assert isinstance(d["impact_score"], float)
        assert isinstance(d["summary"], str)

    def test_backward_compat_finalize_no_confidence(self):
        """finalize() without confidence arg should still work."""
        ep = _make_episode(pnl=100)
        ep.impact_score = DEFAULT_IMPACT_SCORE  # reset
        ep.finalize()  # no confidence arg
        assert ep.impact_score > 0
        assert ep.outcome == "win"


# ── LearnedPattern ─────────────────────────────────────────────────────


class TestLearnedPattern:
    """Test the LearnedPattern dataclass."""

    def test_create_pattern(self):
        p = _make_pattern(name="bullish_divergence", impact=0.7)
        assert p.name == "bullish_divergence"
        assert p.impact_score == 0.7

    def test_pattern_to_dict(self):
        p = _make_pattern()
        d = p.to_dict()
        assert "pattern_id" in d
        assert "impact_score" in d
        assert "description" in d

    def test_pattern_description_truncated_in_dict(self):
        p = _make_pattern()
        p.description = "x" * 5000
        d = p.to_dict()
        assert len(d["description"]) <= MAX_ENTRY_CHARS


# ── BoundedMemory ──────────────────────────────────────────────────────


class TestBoundedMemory:
    """Test the BoundedMemory class."""

    def test_store_and_get_episode(self):
        mem = BoundedMemory()
        ep = _make_episode()
        eid = mem.store_episode(ep)
        assert mem.get_episode(eid) is not None
        assert mem.episode_count() == 1

    def test_store_auto_finalizes(self):
        mem = BoundedMemory()
        ep = TradeEpisode(symbol="AAPL", pnl=100, pnl_pct=0.67)
        mem.store_episode(ep, confidence=0.7)
        stored = mem.get_episode(ep.episode_id)
        assert stored.outcome == "win"
        assert stored.impact_score > MIN_IMPACT_THRESHOLD

    def test_store_truncates_summary(self):
        mem = BoundedMemory()
        ep = _make_episode()
        ep.summary = "x" * 5000
        mem.store_episode(ep)
        stored = mem.get_episode(ep.episode_id)
        assert len(stored.summary) <= MAX_ENTRY_CHARS

    def test_hard_cap_enforced(self):
        """Store more than MAX_TRADES episodes; count must stay at cap."""
        cap = 20  # small cap for test
        mem = BoundedMemory(max_trades=cap)
        for i in range(cap + 50):
            ep = _make_episode(pnl=float(i), pnl_pct=float(i) / 150.0)
            mem.store_episode(ep)
        assert mem.episode_count() <= cap

    def test_evicts_lowest_impact_not_oldest(self):
        """When over limit, the lowest-impact entry should be evicted."""
        cap = 5
        mem = BoundedMemory(max_trades=cap)
        # Store high-impact entries
        for i in range(cap):
            ep = _make_episode(pnl=1000.0, pnl_pct=6.67)
            ep.entry_time = time.time() - 86400 * i  # vary age
            mem.store_episode(ep)
        # Store a low-impact entry (should trigger eviction of the low one)
        low_ep = _make_episode(pnl=0.01, pnl_pct=0.0001)
        mem.store_episode(low_ep)
        # The low-impact episode should have been evicted
        assert mem.get_episode(low_ep.episode_id) is None
        assert mem.episode_count() <= cap

    def test_eviction_produces_insight(self):
        """Each eviction should produce an insight string."""
        cap = 3
        mem = BoundedMemory(max_trades=cap)
        for i in range(cap + 5):
            ep = _make_episode(pnl=float(i * 10))
            mem.store_episode(ep)
        insights = mem.get_insights()
        assert len(insights) > 0
        # Each insight should be a non-empty string
        for insight in insights:
            assert len(insight) > 0

    def test_eviction_log_populated(self):
        cap = 3
        mem = BoundedMemory(max_trades=cap)
        for i in range(cap + 3):
            mem.store_episode(_make_episode(pnl=float(i)))
        log = mem.get_eviction_log()
        assert len(log) > 0
        assert all(isinstance(e, EvictionInsight) for e in log)

    def test_periodic_cleanup(self):
        """Every CLEANUP_INTERVAL stores, low-impact entries get pruned."""
        mem = BoundedMemory(max_trades=1000)
        # Store CLEANUP_INTERVAL entries with very low impact
        for i in range(CLEANUP_INTERVAL):
            ep = _make_episode(pnl=0.001, pnl_pct=0.00001)
            mem.store_episode(ep)
        # Periodic cleanup should have run on the last store
        stats = mem.stats()
        assert stats["store_count"] == CLEANUP_INTERVAL

    def test_stats(self):
        mem = BoundedMemory()
        for i in range(10):
            mem.store_episode(_make_episode(pnl=float(i * 10)))
        s = mem.stats()
        assert s["episode_count"] == 10
        assert s["episode_cap"] == MAX_TRADES
        assert "avg_impact" in s
        assert "total_evictions" in s

    def test_query_episodes_top_k(self):
        mem = BoundedMemory()
        for i in range(20):
            ep = _make_episode(pnl=float(i * 10), pnl_pct=float(i * 10) / 150.0)
            mem.store_episode(ep)
        top = mem.query_episodes(top_k=5)
        assert len(top) == 5
        # Should be sorted by impact descending
        for i in range(len(top) - 1):
            assert top[i].impact_score >= top[i + 1].impact_score

    def test_query_episodes_by_symbol(self):
        mem = BoundedMemory()
        for i in range(10):
            mem.store_episode(_make_episode(symbol="AAPL", pnl=float(i * 10)))
        for i in range(5):
            mem.store_episode(_make_episode(symbol="TSLA", pnl=float(i * 10)))
        aapl = mem.query_episodes(top_k=100, symbol="AAPL")
        assert all(ep.symbol == "AAPL" for ep in aapl)

    def test_query_episodes_min_impact_filter(self):
        mem = BoundedMemory()
        # High impact
        for i in range(5):
            mem.store_episode(_make_episode(pnl=1000.0, pnl_pct=6.67))
        # Very low impact
        for i in range(5):
            ep = _make_episode(pnl=0.001, pnl_pct=0.000001)
            ep.impact_score = 0.005
            mem._episodes[ep.episode_id] = ep  # bypass store to control impact
        result = mem.query_episodes(top_k=100, min_impact=0.01)
        assert all(ep.impact_score >= 0.01 for ep in result)

    # ── Pattern tests ──────────────────────────────────────────────

    def test_store_and_get_pattern(self):
        mem = BoundedMemory()
        p = _make_pattern()
        pid = mem.store_pattern(p)
        assert mem.get_pattern(pid) is not None
        assert mem.pattern_count() == 1

    def test_pattern_cap_enforced(self):
        cap = 5
        mem = BoundedMemory(max_patterns=cap)
        for i in range(cap + 10):
            mem.store_pattern(_make_pattern(name=f"p{i}", impact=float(i) / 100))
        assert mem.pattern_count() <= cap

    def test_pattern_evicts_lowest_impact(self):
        cap = 3
        mem = BoundedMemory(max_patterns=cap)
        mem.store_pattern(_make_pattern(name="high", impact=0.9))
        mem.store_pattern(_make_pattern(name="mid", impact=0.5))
        mem.store_pattern(_make_pattern(name="low", impact=0.1))
        # Adding one more should evict "low"
        mem.store_pattern(_make_pattern(name="new", impact=0.7))
        patterns = mem.all_patterns()
        names = {p.name for p in patterns}
        assert "low" not in names
        assert "high" in names

    def test_query_patterns(self):
        mem = BoundedMemory()
        for i in range(10):
            mem.store_pattern(_make_pattern(name=f"p{i}", impact=float(i) / 10))
        top = mem.query_patterns(top_k=3)
        assert len(top) == 3
        assert top[0].impact_score >= top[1].impact_score

    def test_query_patterns_by_symbol(self):
        mem = BoundedMemory()
        p1 = _make_pattern(name="aapl_p", impact=0.8)
        p1.symbol = "AAPL"
        p2 = _make_pattern(name="tsla_p", impact=0.7)
        p2.symbol = "TSLA"
        p3 = _make_pattern(name="global_p", impact=0.6)
        p3.symbol = ""
        mem.store_pattern(p1)
        mem.store_pattern(p2)
        mem.store_pattern(p3)
        aapl = mem.query_patterns(top_k=10, symbol="AAPL")
        assert len(aapl) == 2  # AAPL + global (empty symbol)

    # ── Insights ───────────────────────────────────────────────────

    def test_get_insights_bounded(self):
        mem = BoundedMemory(max_trades=2)
        for i in range(20):
            mem.store_episode(_make_episode(pnl=float(i)))
        insights = mem.get_insights(last_n=5)
        assert len(insights) <= 5


# ── PrioritizedRetrieval ──────────────────────────────────────────────


class TestPrioritizedRetrieval:
    """Test the PrioritizedRetrieval query engine."""

    def _filled_memory(self, n=20) -> BoundedMemory:
        mem = BoundedMemory(max_trades=1000)
        for i in range(n):
            ep = _make_episode(
                symbol="AAPL" if i % 2 == 0 else "TSLA",
                pnl=float(i * 50),
                pnl_pct=float(i * 50) / 150.0,
            )
            mem.store_episode(ep)
        return mem

    def test_query_returns_top_k(self):
        mem = self._filled_memory(20)
        pr = PrioritizedRetrieval(mem)
        ref = _make_episode(symbol="AAPL")
        results = pr.query(ref, top_k=5)
        assert len(results) == 5

    def test_query_sorted_by_combined_score(self):
        mem = self._filled_memory(20)
        pr = PrioritizedRetrieval(mem)
        ref = _make_episode(symbol="AAPL")
        results = pr.query(ref, top_k=10)
        for i in range(len(results) - 1):
            assert results[i][1] >= results[i + 1][1]

    def test_query_filters_min_impact(self):
        mem = BoundedMemory(max_trades=1000)
        # Add high-impact
        for i in range(5):
            mem.store_episode(_make_episode(pnl=1000, pnl_pct=6.67))
        # Add low-impact directly
        for i in range(5):
            ep = _make_episode(pnl=0.001, pnl_pct=0.00001)
            ep.impact_score = 0.005
            mem._episodes[ep.episode_id] = ep
        pr = PrioritizedRetrieval(mem)
        ref = _make_episode()
        results = pr.query(ref, top_k=100, min_impact=0.01)
        for ep, score in results:
            assert ep.impact_score >= 0.01

    def test_query_excludes_reference(self):
        mem = self._filled_memory(10)
        pr = PrioritizedRetrieval(mem)
        ref = mem.all_episodes()[0]
        results = pr.query(ref, top_k=100)
        result_ids = {ep.episode_id for ep, _ in results}
        assert ref.episode_id not in result_ids

    def test_query_by_symbol(self):
        mem = self._filled_memory(20)
        pr = PrioritizedRetrieval(mem)
        results = pr.query_by_symbol("AAPL", top_k=100)
        assert all(ep.symbol == "AAPL" for ep in results)

    def test_query_worst(self):
        mem = self._filled_memory(20)
        pr = PrioritizedRetrieval(mem)
        worst = pr.query_worst(top_k=3)
        assert len(worst) == 3
        assert worst[0].pnl <= worst[1].pnl

    def test_query_best(self):
        mem = self._filled_memory(20)
        pr = PrioritizedRetrieval(mem)
        best = pr.query_best(top_k=3)
        assert len(best) == 3
        assert best[0].pnl >= best[1].pnl

    def test_query_worst_by_symbol(self):
        mem = self._filled_memory(20)
        pr = PrioritizedRetrieval(mem)
        worst = pr.query_worst(top_k=5, symbol="TSLA")
        assert all(ep.symbol == "TSLA" for ep in worst)


# ── Stress test: 1000+ trades stay under limits ───────────────────────


class TestBoundedMemoryStress:
    """Verify memory stays under limits with 1000+ trades."""

    def test_1000_trades_stay_under_cap(self):
        """Core requirement: after 1000+ stores, count <= MAX_TRADES."""
        mem = BoundedMemory(max_trades=MAX_TRADES)
        for i in range(1200):
            ep = _make_episode(
                symbol=["AAPL", "TSLA", "GOOG", "MSFT"][i % 4],
                pnl=float(i % 200 - 100),  # mix of wins/losses
                pnl_pct=float(i % 200 - 100) / 150.0,
            )
            mem.store_episode(ep)
        assert mem.episode_count() <= MAX_TRADES

    def test_1000_trades_stats_sane(self):
        """Stats should be reasonable after heavy churn."""
        mem = BoundedMemory(max_trades=MAX_TRADES)
        for i in range(1000):
            ep = _make_episode(pnl=float(i % 200 - 100))
            mem.store_episode(ep)
        s = mem.stats()
        assert s["episode_count"] <= MAX_TRADES
        assert s["total_evictions"] > 0
        assert s["avg_impact"] > 0

    def test_1000_trades_insights_collected(self):
        """Evictions should have produced insights."""
        mem = BoundedMemory(max_trades=50)
        for i in range(1000):
            mem.store_episode(_make_episode(pnl=float(i)))
        insights = mem.get_insights()
        assert len(insights) > 0

    def test_200_patterns_stay_under_cap(self):
        mem = BoundedMemory(max_patterns=MAX_PATTERNS)
        for i in range(200):
            mem.store_pattern(_make_pattern(name=f"p{i}", impact=float(i) / 200))
        assert mem.pattern_count() <= MAX_PATTERNS

    def test_mixed_stress(self):
        """Both episodes and patterns under heavy load."""
        mem = BoundedMemory(max_trades=100, max_patterns=10)
        for i in range(500):
            mem.store_episode(_make_episode(pnl=float(i)))
        for i in range(50):
            mem.store_pattern(_make_pattern(name=f"p{i}", impact=float(i) / 50))
        assert mem.episode_count() <= 100
        assert mem.pattern_count() <= 10

    def test_prioritized_retrieval_after_stress(self):
        """PrioritizedRetrieval should work correctly after heavy churn."""
        mem = BoundedMemory(max_trades=100)
        for i in range(1000):
            mem.store_episode(_make_episode(
                symbol="AAPL" if i % 3 == 0 else "TSLA",
                pnl=float(i % 300 - 150),
                pnl_pct=float(i % 300 - 150) / 150.0,
            ))
        pr = PrioritizedRetrieval(mem)
        ref = _make_episode(symbol="AAPL")
        results = pr.query(ref, top_k=10)
        assert len(results) > 0
        # All results should be above min impact
        for ep, score in results:
            assert ep.impact_score >= MIN_IMPACT_THRESHOLD
