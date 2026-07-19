"""Tests for reasoning models — CoT, causal inference, explainability."""

import pytest
from alphastack.reasoning.chain_of_thought import (
    ChainOfThought,
    ThoughtStep,
    ThoughtStepType,
    ThoughtChain,
)
from alphastack.reasoning.causal import (
    CausalInference,
    CausalLink,
    CausalStrength,
    EventImpact,
)
from alphastack.reasoning.explainability import (
    TradeExplainer,
    TradeExplanation,
    TradeDirection,
    FactorContribution,
)


class TestChainOfThought:
    """Tests for chain-of-thought reasoning."""

    def test_start_chain(self):
        cot = ChainOfThought()
        chain = cot.start("Market analysis")
        assert chain.context == "Market analysis"
        assert chain.chain_id

    def test_observe(self):
        cot = ChainOfThought()
        chain = cot.start("Test")
        cot.observe(chain, "Price at 100", 0.9)
        assert len(chain.steps) == 1
        assert chain.steps[0].step_type == ThoughtStepType.OBSERVE

    def test_collect_evidence(self):
        cot = ChainOfThought()
        chain = cot.start("Test")
        cot.collect_evidence(chain, "RSI oversold", 0.8, {"rsi": 25})
        assert len(chain.steps) == 1
        assert chain.steps[0].supporting_data == {"rsi": 25}

    def test_weigh_evidence(self):
        cot = ChainOfThought()
        chain = cot.start("Test")
        cot.weigh_evidence(chain, "2 bullish, 1 bearish", 0.7)
        assert chain.steps[0].step_type == ThoughtStepType.WEIGH_EVIDENCE

    def test_hypothesize(self):
        cot = ChainOfThought()
        chain = cot.start("Test")
        cot.hypothesize(chain, "Bullish breakout", 0.6)
        assert chain.steps[0].step_type == ThoughtStepType.HYPOTHESIZE

    def test_validate(self):
        cot = ChainOfThought()
        chain = cot.start("Test")
        cot.validate(chain, "Volume confirms", 0.7)
        assert chain.steps[0].step_type == ThoughtStepType.VALIDATE

    def test_conclude(self):
        cot = ChainOfThought()
        chain = cot.start("Test")
        cot.observe(chain, "Price up", 0.9)
        cot.collect_evidence(chain, "RSI low", 0.8)
        conf = cot.conclude(chain, "Go long")
        assert chain.conclusion == "Go long"
        assert 0 < conf <= 1

    def test_trace_log(self):
        cot = ChainOfThought()
        chain = cot.start("Test")
        cot.observe(chain, "Test obs", 0.9)
        assert len(chain.trace_log) == 1
        assert "observe" in chain.trace_log[0]

    def test_full_analysis(self):
        cot = ChainOfThought()
        chain = cot.full_analysis(
            symbol="AAPL",
            price=150.0,
            indicators={"rsi": 25.0, "macd": 0.5},
            volume_ratio=1.8,
            sentiment=0.3,
        )
        assert chain.conclusion
        assert chain.final_confidence > 0
        assert len(chain.steps) >= 3

    def test_full_analysis_bearish(self):
        cot = ChainOfThought()
        chain = cot.full_analysis(
            symbol="AAPL",
            price=150.0,
            indicators={"rsi": 80.0, "macd": -0.5},
            volume_ratio=2.0,
            sentiment=-0.5,
        )
        assert "bearish" in chain.conclusion.lower() or "short" in chain.conclusion.lower()

    def test_get_chain(self):
        cot = ChainOfThought()
        chain = cot.start("Test")
        assert cot.get_chain(chain.chain_id) is not None
        assert cot.get_chain("nonexistent") is None

    def test_list_chains(self):
        cot = ChainOfThought()
        cot.start("A")
        cot.start("B")
        assert len(cot.list_chains()) == 2

    def test_chain_to_dict(self):
        cot = ChainOfThought()
        chain = cot.start("Test")
        cot.observe(chain, "Obs", 0.9)
        d = chain.to_dict()
        assert "chain_id" in d
        assert len(d["steps"]) == 1

    def test_thought_step_to_dict(self):
        step = ThoughtStep(
            step_type=ThoughtStepType.OBSERVE,
            content="Test",
            confidence=0.9,
            supporting_data={"key": "val"},
        )
        d = step.to_dict()
        assert d["type"] == "observe"
        assert d["confidence"] == 0.9


class TestCausalInference:
    """Tests for causal inference engine."""

    def test_record_event(self):
        ci = CausalInference()
        event = EventImpact(
            event_type="earnings",
            description="Beat estimates",
            price_change_pct=5.0,
        )
        ci.record_event(event)
        assert len(ci.get_event_history()) == 1

    def test_infer_causality_causal(self):
        ci = CausalInference()
        link = ci.infer_causality(
            cause="Earnings beat",
            effect="Price increase",
            correlation=0.8,
            temporal_precedence=True,
            confound_present=False,
            repeated_observation=True,
        )
        assert link.is_causal is True
        assert link.strength in (CausalStrength.STRONG, CausalStrength.MODERATE)

    def test_infer_causality_not_causal(self):
        ci = CausalInference()
        link = ci.infer_causality(
            cause="Ice cream sales",
            effect="Stock price",
            correlation=0.3,
            temporal_precedence=False,
            confound_present=True,
            repeated_observation=False,
        )
        assert link.is_causal is False

    def test_counterfactual(self):
        ci = CausalInference()
        ci.infer_causality("Event A", "Price move", 0.7, True, False, True)
        statement = ci.counterfactual("Event A", "Price move", 5.0, 1.0)
        assert "without" in statement.lower()
        assert "4.00" in statement  # 5.0 - 1.0

    def test_news_impact_score(self):
        ci = CausalInference()
        impact = ci.news_impact_score(
            "Company beats earnings by 20%",
            sentiment=0.8,
            relevance=0.9,
        )
        assert impact.price_change_pct > 0
        assert impact.event_type == "news"

    def test_news_impact_negative(self):
        ci = CausalInference()
        impact = ci.news_impact_score(
            "Company recalls product",
            sentiment=-0.7,
            relevance=0.8,
        )
        assert impact.price_change_pct < 0

    def test_correlation_vs_causation_with_confound(self):
        ci = CausalInference()
        result = ci.correlation_vs_causation(
            "sunscreen_sales", "ice_cream_sales", 0.8,
            potential_confound="temperature",
        )
        assert result["assessment"] == "likely_spurious"

    def test_correlation_vs_causation_strong(self):
        ci = CausalInference()
        result = ci.correlation_vs_causation(
            "earnings_beat", "price_increase", 0.75,
        )
        assert result["assessment"] == "worth_investigating"

    def test_correlation_vs_causation_weak(self):
        ci = CausalInference()
        result = ci.correlation_vs_causation(
            "moon_phase", "stock_price", 0.1,
        )
        assert result["assessment"] == "unlikely_causal"

    def test_get_links(self):
        ci = CausalInference()
        ci.infer_causality("A", "B", 0.6, True, False, False)
        ci.infer_causality("C", "D", 0.3, False, True, False)
        assert len(ci.get_links()) == 2

    def test_to_dict(self):
        ci = CausalInference()
        ci.infer_causality("A", "B", 0.6, True, False, False)
        d = ci.to_dict()
        assert "links" in d
        assert d["event_count"] == 0

    def test_causal_link_to_dict(self):
        link = CausalLink(
            cause="A",
            effect="B",
            strength=CausalStrength.MODERATE,
            correlation=0.6,
            is_causal=True,
            confidence=0.7,
        )
        d = link.to_dict()
        assert d["cause"] == "A"
        assert d["strength"] == "moderate"

    def test_event_impact_to_dict(self):
        event = EventImpact(
            event_type="earnings",
            description="Beat",
            price_change_pct=5.0,
            confidence=0.8,
        )
        d = event.to_dict()
        assert d["event_type"] == "earnings"


class TestTradeExplainer:
    """Tests for trade explainability."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.explainer = TradeExplainer()

    def _make_explanation(self) -> TradeExplanation:
        return self.explainer.explain(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=150.0,
            stop_loss=145.0,
            take_profit=165.0,
            position_size=0.05,
            factors={
                "rsi_oversold": (0.8, 0.3),
                "macd_crossover": (0.6, 0.25),
                "volume_surge": (0.5, 0.2),
                "news_sentiment": (0.3, 0.15),
                "market_trend": (0.4, 0.1),
            },
            confidence=0.72,
        )

    def test_explain_creates_explanation(self):
        exp = self._make_explanation()
        assert exp.symbol == "AAPL"
        assert exp.direction == TradeDirection.LONG
        assert exp.confidence == 0.72

    def test_factors_sorted_by_contribution(self):
        exp = self._make_explanation()
        contributions = [abs(f.contribution) for f in exp.factors]
        assert contributions == sorted(contributions, reverse=True)

    def test_risk_benefit_ratio(self):
        exp = self._make_explanation()
        rb = exp.risk_benefit
        assert rb["risk_reward_ratio"] == 3.0  # (165-150)/(150-145) = 3
        assert rb["max_loss_pct"] > 0
        assert rb["max_gain_pct"] > 0

    def test_rationale_non_empty(self):
        exp = self._make_explanation()
        assert len(exp.rationale) > 0
        assert "AAPL" in exp.rationale

    def test_audit_trail(self):
        exp = self._make_explanation()
        assert len(exp.audit_trail) >= 3

    def test_summary(self):
        exp = self._make_explanation()
        summary = exp.summary()
        assert "LONG" in summary
        assert "AAPL" in summary

    def test_factor_contribution_direction(self):
        exp = self._make_explanation()
        positive = [f for f in exp.factors if f.contribution > 0.05]
        assert all(f.direction == "bullish" for f in positive)

    def test_audit_report(self):
        # Using self.explainer
        exp = self._make_explanation()
        report = self.explainer.audit_report(exp.explanation_id)
        assert "AUDIT REPORT" in report
        assert "AAPL" in report
        assert "Risk" in report

    def test_audit_report_not_found(self):
        # Using self.explainer
        assert "No explanation" in self.explainer.audit_report("nonexistent")

    def test_list_explanations(self):
        # Using self.explainer
        self._make_explanation()
        lst = self.explainer.list_explanations()
        assert len(lst) == 1
        assert lst[0]["symbol"] == "AAPL"

    def test_get_explanation(self):
        # Using self.explainer
        exp = self._make_explanation()
        retrieved = self.explainer.get_explanation(exp.explanation_id)
        assert retrieved is not None
        assert retrieved.symbol == "AAPL"

    def test_explanation_to_dict(self):
        exp = self._make_explanation()
        d = exp.to_dict()
        assert d["symbol"] == "AAPL"
        assert "factors" in d
        assert "risk_benefit" in d

    def test_factor_to_dict(self):
        f = FactorContribution(
            factor_name="rsi",
            value=0.8,
            weight=0.3,
            contribution=0.24,
            direction="bullish",
            explanation="RSI oversold",
        )
        d = f.to_dict()
        assert d["factor"] == "rsi"
        assert d["contribution"] == 0.24

    def test_short_direction(self):
        # Using self.explainer
        exp = self.explainer.explain(
            symbol="TSLA",
            direction=TradeDirection.SHORT,
            entry_price=200.0,
            stop_loss=210.0,
            take_profit=180.0,
            position_size=0.03,
            factors={"bearish_pattern": (-0.7, 0.5)},
            confidence=0.65,
        )
        assert exp.direction == TradeDirection.SHORT
        assert "short" in exp.summary().lower()
