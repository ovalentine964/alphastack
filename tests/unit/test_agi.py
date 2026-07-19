"""Tests for AGI readiness and reasoning modules."""

import pytest
from alphastack.agi.readiness import AGIReadiness, ReadinessLevel
from alphastack.agi.reasoning import ChainOfThoughtEngine, ReasoningStepType
from alphastack.agi.planning import TradePlanner, ScenarioType
from alphastack.agi.memory import EpisodicMemory, TradeEpisode


class TestAGIReadiness:
    """Tests for AGI readiness assessment."""

    def test_initial_level_is_l1(self):
        readiness = AGIReadiness()
        assert readiness.compute_readiness_level() == ReadinessLevel.L1

    def test_update_score_valid(self):
        readiness = AGIReadiness()
        readiness.update_score("pattern_recognition", 0.8)
        assert readiness.get_score("pattern_recognition").current == 0.8

    def test_update_score_invalid_name(self):
        readiness = AGIReadiness()
        with pytest.raises(KeyError):
            readiness.update_score("nonexistent", 0.5)

    def test_update_score_out_of_range(self):
        readiness = AGIReadiness()
        with pytest.raises(ValueError):
            readiness.update_score("pattern_recognition", 1.5)

    def test_overall_score_zero_by_default(self):
        readiness = AGIReadiness()
        assert readiness.compute_overall_score() == 0.0

    def test_overall_score_with_updates(self):
        readiness = AGIReadiness()
        readiness.update_score("market_data_ingestion", 0.9)
        readiness.update_score("pattern_recognition", 0.8)
        score = readiness.compute_overall_score()
        assert score > 0.0

    def test_gap_analysis_identifies_missing(self):
        readiness = AGIReadiness()
        gap = readiness.gap_analysis()
        assert len(gap.missing_capabilities) > 0

    def test_gap_analysis_with_strengths(self):
        readiness = AGIReadiness()
        readiness.update_score("market_data_ingestion", 0.95)
        gap = readiness.gap_analysis()
        assert "market_data_ingestion" in gap.strengths

    def test_readiness_level_advances(self):
        readiness = AGIReadiness()
        # Set all L1 capabilities to target
        readiness.update_score("market_data_ingestion", 0.9)
        readiness.update_score("pattern_recognition", 0.9)
        readiness.update_score("risk_management", 0.9)
        readiness.update_score("strategy_generation", 0.9)
        readiness.update_score("causal_reasoning", 0.9)
        readiness.update_score("multi_timeframe_analysis", 0.9)
        readiness.update_score("natural_language_understanding", 0.9)
        readiness.update_score("adversarial_robustness", 0.9)
        readiness.update_score("meta_learning", 0.9)
        readiness.update_score("self_improvement", 0.9)
        level = readiness.compute_readiness_level()
        assert level >= ReadinessLevel.L2

    def test_roadmap_generation(self):
        readiness = AGIReadiness()
        roadmap = readiness.generate_roadmap()
        assert len(roadmap.phases) >= 2
        assert roadmap.estimated_timeline_weeks > 0

    def test_to_dict(self):
        readiness = AGIReadiness()
        d = readiness.to_dict()
        assert "level" in d
        assert "overall_score" in d
        assert "capabilities" in d

    def test_score_achieved(self):
        readiness = AGIReadiness()
        readiness.update_score("market_data_ingestion", 0.3)
        score = readiness.get_score("market_data_ingestion")
        # target is L1/5 = 0.2, so 0.3 should be achieved
        assert score.achieved is True

    def test_gap_value(self):
        readiness = AGIReadiness()
        readiness.update_score("market_data_ingestion", 0.1)
        score = readiness.get_score("market_data_ingestion")
        assert score.gap > 0


class TestChainOfThoughtEngine:
    """Tests for chain-of-thought reasoning engine."""

    def test_start_chain(self):
        engine = ChainOfThoughtEngine()
        chain = engine.start_chain("Test topic")
        assert chain.topic == "Test topic"
        assert chain.chain_id

    def test_add_step(self):
        engine = ChainOfThoughtEngine()
        chain = engine.start_chain("Test")
        step = chain.add_step(ReasoningStepType.OBSERVATION, "Price is 100", 0.9)
        assert step.content == "Price is 100"
        assert len(chain.steps) == 1

    def test_finalize_computes_confidence(self):
        engine = ChainOfThoughtEngine()
        chain = engine.start_chain("Test")
        chain.add_step(ReasoningStepType.OBSERVATION, "Obs A", 0.9)
        chain.add_step(ReasoningStepType.HYPOTHESIS, "Hyp B", 0.7)
        conf = chain.finalize("Conclusion")
        assert 0 < conf <= 1
        assert chain.conclusion == "Conclusion"

    def test_analyze_market_signal(self):
        engine = ChainOfThoughtEngine()
        chain = engine.analyze_market_signal(
            symbol="AAPL",
            price_data={"close": 150.0},
            indicators={"rsi": 25.0, "macd": 0.5},
        )
        assert "AAPL" in chain.topic
        assert chain.conclusion
        assert chain.overall_confidence > 0

    def test_list_chains(self):
        engine = ChainOfThoughtEngine()
        engine.start_chain("A")
        engine.start_chain("B")
        chains = engine.list_chains()
        assert len(chains) == 2

    def test_get_chain(self):
        engine = ChainOfThoughtEngine()
        chain = engine.start_chain("Test")
        retrieved = engine.get_chain(chain.chain_id)
        assert retrieved is not None
        assert retrieved.topic == "Test"

    def test_to_dict(self):
        engine = ChainOfThoughtEngine()
        engine.start_chain("Test")
        d = engine.to_dict()
        assert len(d) == 1


class TestTradePlanner:
    """Tests for trade planning module."""

    def test_create_plan(self):
        planner = TradePlanner()
        plan = planner.create_plan("AAPL", 150.0, 0.25)
        assert plan.symbol == "AAPL"
        assert len(plan.scenarios) == 3

    def test_scenario_types(self):
        planner = TradePlanner()
        plan = planner.create_plan("AAPL", 150.0, 0.25)
        types = {s.scenario for s in plan.scenarios}
        assert ScenarioType.BULL in types
        assert ScenarioType.BEAR in types
        assert ScenarioType.SIDEWAYS in types

    def test_probabilities_sum_to_one(self):
        planner = TradePlanner()
        plan = planner.create_plan("AAPL", 150.0, 0.25)
        total = sum(s.probability for s in plan.scenarios)
        assert abs(total - 1.0) < 0.01

    def test_risk_adjusted_score(self):
        planner = TradePlanner()
        plan = planner.create_plan("AAPL", 150.0, 0.25)
        score = plan.risk_adjusted_score()
        assert isinstance(score, float)

    def test_best_scenario(self):
        planner = TradePlanner()
        plan = planner.create_plan("AAPL", 150.0, 0.25)
        best = plan.best_scenario()
        assert best is not None

    def test_adapt_plan(self):
        planner = TradePlanner()
        plan = planner.create_plan("AAPL", 150.0, 0.25)
        adapted = planner.adapt_plan(plan.plan_id, ScenarioType.BULL, 0.6)
        bull = next(s for s in adapted.scenarios if s.scenario == ScenarioType.BULL)
        assert bull.probability == 0.6

    def test_adapt_plan_not_found(self):
        planner = TradePlanner()
        with pytest.raises(KeyError):
            planner.adapt_plan("nonexistent", ScenarioType.BULL, 0.6)

    def test_list_plans(self):
        planner = TradePlanner()
        planner.create_plan("AAPL", 150.0, 0.25)
        plans = planner.list_plans()
        assert len(plans) == 1

    def test_to_dict(self):
        planner = TradePlanner()
        plan = planner.create_plan("AAPL", 150.0, 0.25)
        d = plan.to_dict()
        assert d["symbol"] == "AAPL"
        assert "scenarios" in d


class TestEpisodicMemory:
    """Tests for episodic memory."""

    def _make_episode(self, symbol="AAPL", direction="long", pnl=100.0) -> TradeEpisode:
        ep = TradeEpisode(
            symbol=symbol,
            direction=direction,
            entry_price=150.0,
            exit_price=160.0,
            pnl=pnl,
            pnl_pct=pnl / 150.0,
            indicators={"rsi": 30.0, "macd": 0.5},
            market_context={"regime": "bullish", "volatility": "high"},
            lessons=["Bought the dip successfully"],
        )
        ep.finalize()
        return ep

    def test_store_and_retrieve(self):
        mem = EpisodicMemory()
        ep = self._make_episode()
        ep_id = mem.store(ep)
        retrieved = mem.retrieve(ep_id)
        assert retrieved is not None
        assert retrieved.symbol == "AAPL"

    def test_retrieve_nonexistent(self):
        mem = EpisodicMemory()
        assert mem.retrieve("nonexistent") is None

    def test_outcome_assignment(self):
        win_ep = self._make_episode(pnl=100)
        assert win_ep.outcome == "win"
        loss_ep = self._make_episode(pnl=-50)
        assert loss_ep.outcome == "loss"
        bep_ep = self._make_episode(pnl=0)
        assert bep_ep.outcome == "breakeven"

    def test_similarity_score_identical(self):
        ep1 = self._make_episode()
        ep2 = self._make_episode()
        score = ep1.similarity_score(ep2)
        assert score > 0.8

    def test_similarity_score_different(self):
        ep1 = self._make_episode(symbol="AAPL", direction="long")
        ep2 = self._make_episode(symbol="TSLA", direction="short")
        score = ep1.similarity_score(ep2)
        assert score < 0.8

    def test_find_similar(self):
        mem = EpisodicMemory()
        ep1 = self._make_episode(symbol="AAPL")
        ep2 = self._make_episode(symbol="AAPL")
        ep3 = self._make_episode(symbol="TSLA")
        mem.store(ep1)
        mem.store(ep2)
        mem.store(ep3)
        similar = mem.find_similar(ep1, top_k=2)
        assert len(similar) <= 2

    def test_get_lessons(self):
        mem = EpisodicMemory()
        ep = self._make_episode()
        mem.store(ep)
        lessons = mem.get_lessons("AAPL")
        assert len(lessons) > 0

    def test_get_lessons_filtered(self):
        mem = EpisodicMemory()
        ep = self._make_episode()
        mem.store(ep)
        lessons = mem.get_lessons("TSLA")
        assert len(lessons) == 0

    def test_consolidate(self):
        mem = EpisodicMemory(consolidation_threshold=3)
        for i in range(5):
            ep = self._make_episode(pnl=float(i * 10))
            ep.entry_time = i  # type: ignore[assignment]
            mem.store(ep)
        # Should have triggered consolidation
        stats = mem.stats()
        assert stats["long_term_count"] > 0

    def test_stats(self):
        mem = EpisodicMemory()
        mem.store(self._make_episode(pnl=100))
        mem.store(self._make_episode(pnl=-50))
        stats = mem.stats()
        assert stats["total_episodes"] == 2
        assert stats["win_rate"] == 0.5

    def test_episode_to_dict(self):
        ep = self._make_episode()
        d = ep.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["outcome"] == "win"
