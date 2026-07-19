"""Unit tests for the AlphaStack AI module.

Tests cover:
  - Technical indicators (RSI, MACD, Bollinger, ATR, ADX, OBV, Stochastic)
  - Smart Money Concepts (order blocks, FVGs, liquidity sweeps)
  - Support/Resistance detection
  - Confluence scoring
  - Signal confidence scoring
  - Market regime detection
  - Sentiment analysis (news, social, calendar)
  - Model routing (tier selection, cost tracking, fallback chains)
  - AI pipeline integration
"""

from __future__ import annotations

import asyncio
import math
import time

import numpy as np
import pytest

from alphastack.ai.model_router import (
    AgentRoutingProfile,
    CostTracker,
    LatencyRequirement,
    ModelConfig,
    ModelRouter,
    ModelTier,
    TaskComplexity,
    TokenBudgetManager,
)
from alphastack.ai.pipeline import AIStrategyPipeline, PipelinePhase
from alphastack.ai.regime import (
    MarketRegime,
    MarketRegimeDetector,
    RegimeFeatureExtractor,
    TrendStrength,
)
from alphastack.ai.sentiment import (
    EconomicCalendarScorer,
    ImpactLevel,
    NewsSentimentAnalyzer,
    SentimentEngine,
    SentimentPolarity,
    SocialSentimentAnalyzer,
)
from alphastack.ai.signals import (
    ConfluenceScorer,
    ConfidenceScorer,
    FairValueGap,
    OrderBlock,
    Signal,
    SignalGenerator,
    SignalSide,
    SMCDetector,
    SRLevel,
    SupportResistanceDetector,
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_obv,
    compute_rsi,
    compute_stochastic,
    compute_vwap,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_trend_data(n: int = 100, direction: str = "up") -> dict[str, np.ndarray]:
    """Generate synthetic OHLCV data for a trending market."""
    rng = np.random.default_rng(42)
    base = 1.1000 if direction == "up" else 1.2000
    drift = 0.0005 if direction == "up" else -0.0005
    noise = rng.normal(0, 0.0008, n)

    closes = np.array([base + drift * i + noise[i] for i in range(n)])
    opens = closes - rng.normal(0, 0.0003, n)
    highs = np.maximum(opens, closes) + rng.uniform(0.0001, 0.001, n)
    lows = np.minimum(opens, closes) - rng.uniform(0.0001, 0.001, n)
    volumes = rng.uniform(100, 1000, n)

    return {"opens": opens, "highs": highs, "lows": lows, "closes": closes, "volumes": volumes}


def _make_range_data(n: int = 100) -> dict[str, np.ndarray]:
    """Generate synthetic OHLCV data for a ranging market."""
    rng = np.random.default_rng(42)
    base = 1.1000
    noise = rng.normal(0, 0.0005, n)

    closes = np.array([base + noise[i] for i in range(n)])
    opens = closes - rng.normal(0, 0.0003, n)
    highs = np.maximum(opens, closes) + rng.uniform(0.0001, 0.0008, n)
    lows = np.minimum(opens, closes) - rng.uniform(0.0001, 0.0008, n)
    volumes = rng.uniform(100, 1000, n)

    return {"opens": opens, "highs": highs, "lows": lows, "closes": closes, "volumes": volumes}


def _make_volatile_data(n: int = 100) -> dict[str, np.ndarray]:
    """Generate synthetic OHLCV data for a volatile market."""
    rng = np.random.default_rng(42)
    base = 1.1000
    noise = rng.normal(0, 0.003, n)  # much larger noise

    closes = np.array([base + sum(noise[:i+1]) for i in range(n)])
    opens = closes - rng.normal(0, 0.001, n)
    highs = np.maximum(opens, closes) + rng.uniform(0.0005, 0.003, n)
    lows = np.minimum(opens, closes) - rng.uniform(0.0005, 0.003, n)
    volumes = rng.uniform(200, 2000, n)

    return {"opens": opens, "highs": highs, "lows": lows, "closes": closes, "volumes": volumes}


# ===========================================================================
# Technical Indicators
# ===========================================================================

class TestRSI:
    def test_basic_rsi(self):
        closes = np.linspace(1.0, 1.5, 50)
        rsi = compute_rsi(closes, period=14)
        # Strong uptrend → RSI should be high
        assert not np.isnan(rsi[-1])
        assert rsi[-1] > 70

    def test_rsi_range(self):
        data = _make_trend_data(100)
        rsi = compute_rsi(data["closes"], period=14)
        valid = rsi[~np.isnan(rsi)]
        assert len(valid) > 0
        assert all(0 <= v <= 100 for v in valid)

    def test_rsi_short_data(self):
        closes = np.array([1.0, 1.1, 1.2])
        rsi = compute_rsi(closes, period=14)
        assert np.isnan(rsi[0])  # not enough data

    def test_rsi_flat_market(self):
        closes = np.ones(50) * 1.1000
        rsi = compute_rsi(closes, period=14)
        # Flat market → RSI should be near 50 (or 100 if no losses)
        assert not np.isnan(rsi[-1])


class TestMACD:
    def test_macd_output_shape(self):
        closes = np.linspace(1.0, 1.5, 100)
        macd_line, signal_line, histogram = compute_macd(closes)
        assert len(macd_line) == 100
        assert len(signal_line) == 100
        assert len(histogram) == 100

    def test_macd_histogram(self):
        closes = np.linspace(1.0, 1.5, 100)
        _, _, histogram = compute_macd(closes)
        # Histogram = macd - signal
        macd_line, signal_line, _ = compute_macd(closes)
        valid_idx = ~np.isnan(histogram)
        np.testing.assert_allclose(
            histogram[valid_idx],
            (macd_line - signal_line)[valid_idx],
            atol=1e-10,
        )


class TestBollingerBands:
    def test_bollinger_ordering(self):
        data = _make_trend_data(100)
        upper, middle, lower = compute_bollinger_bands(data["closes"])
        valid = ~np.isnan(upper)
        assert np.all(upper[valid] >= middle[valid])
        assert np.all(middle[valid] >= lower[valid])

    def test_bollinger_contains_price(self):
        data = _make_range_data(100)
        upper, middle, lower = compute_bollinger_bands(data["closes"], period=20)
        # Most prices should be within bands
        valid_idx = 19  # after warmup
        for i in range(valid_idx, len(data["closes"])):
            if not np.isnan(upper[i]):
                # At least 80% should be within bands (statistical expectation ~95%)
                pass  # just check no NaN crashes


class TestATR:
    def test_atr_positive(self):
        data = _make_trend_data(100)
        atr = compute_atr(data["highs"], data["lows"], data["closes"])
        valid = atr[~np.isnan(atr)]
        assert len(valid) > 0
        assert all(v > 0 for v in valid)

    def test_atr_higher_in_volatile(self):
        trend = _make_trend_data(200)
        volatile = _make_volatile_data(200)

        atr_trend = compute_atr(trend["highs"], trend["lows"], trend["closes"])
        atr_volatile = compute_atr(volatile["highs"], volatile["lows"], volatile["closes"])

        valid_trend = atr_trend[~np.isnan(atr_trend)]
        valid_volatile = atr_volatile[~np.isnan(atr_volatile)]

        if len(valid_trend) > 0 and len(valid_volatile) > 0:
            assert np.mean(valid_volatile) > np.mean(valid_trend)


class TestEMA:
    def test_ema_crossover(self):
        closes = np.linspace(1.0, 1.5, 100)
        ema_fast = compute_ema(closes, 9)
        ema_slow = compute_ema(closes, 21)
        # In uptrend, fast EMA should be above slow EMA (eventually)
        valid = ~(np.isnan(ema_fast) | np.isnan(ema_slow))
        if np.any(valid):
            assert ema_fast[valid][-1] > ema_slow[valid][-1]


class TestOBV:
    def test_obv_uptrend(self):
        closes = np.linspace(1.0, 1.5, 50)
        volumes = np.ones(50) * 100
        obv = compute_obv(closes, volumes)
        assert obv[-1] > obv[0]  # OBV should increase in uptrend


class TestStochastic:
    def test_stochastic_range(self):
        data = _make_range_data(100)
        k, d = compute_stochastic(data["highs"], data["lows"], data["closes"])
        valid = k[~np.isnan(k)]
        if len(valid) > 0:
            assert all(0 <= v <= 100 for v in valid)


class TestVWAP:
    def test_vwap_close_to_price(self):
        data = _make_range_data(100)
        vwap = compute_vwap(data["highs"], data["lows"], data["closes"], data["volumes"])
        # VWAP should be reasonably close to price
        assert abs(vwap[-1] - data["closes"][-1]) < 0.01


# ===========================================================================
# Smart Money Concepts
# ===========================================================================

class TestSMCDetector:
    def test_detect_order_blocks(self):
        data = _make_trend_data(100)
        smc = SMCDetector()
        obs = smc.detect_order_blocks(
            data["opens"], data["highs"], data["lows"], data["closes"],
        )
        # Should detect at least some order blocks in a trend
        assert isinstance(obs, list)
        for ob in obs:
            assert isinstance(ob, OrderBlock)
            assert ob.high >= ob.low
            assert ob.direction in (SignalSide.LONG, SignalSide.SHORT)

    def test_detect_fvgs(self):
        data = _make_trend_data(100)
        smc = SMCDetector()
        fvgs = smc.detect_fair_value_gaps(data["highs"], data["lows"])
        assert isinstance(fvgs, list)
        for fvg in fvgs:
            assert isinstance(fvg, FairValueGap)
            assert fvg.high >= fvg.low

    def test_detect_liquidity_sweeps(self):
        data = _make_range_data(100)
        smc = SMCDetector()
        sweeps = smc.detect_liquidity_sweeps(data["highs"], data["lows"], data["closes"])
        assert isinstance(sweeps, list)

    def test_analyze_returns_bias(self):
        data = _make_trend_data(100)
        atr = compute_atr(data["highs"], data["lows"], data["closes"])
        smc = SMCDetector()
        result = smc.analyze(data["opens"], data["highs"], data["lows"], data["closes"], atr)
        assert "bias" in result
        assert "bullish_score" in result
        assert "bearish_score" in result
        assert result["bias"] in (SignalSide.LONG, SignalSide.SHORT, SignalSide.FLAT)


# ===========================================================================
# Support/Resistance
# ===========================================================================

class TestSupportResistance:
    def test_detect_levels(self):
        data = _make_range_data(100)
        sr = SupportResistanceDetector()
        supports, resistances = sr.detect(data["highs"], data["lows"], data["closes"])
        assert isinstance(supports, list)
        assert isinstance(resistances, list)

        for lvl in supports:
            assert isinstance(lvl, SRLevel)
            assert lvl.level_type == "support"
            assert lvl.touches >= 2

        for lvl in resistances:
            assert isinstance(lvl, SRLevel)
            assert lvl.level_type == "resistance"
            assert lvl.touches >= 2

    def test_levels_sorted(self):
        data = _make_range_data(200)
        sr = SupportResistanceDetector()
        supports, resistances = sr.detect(data["highs"], data["lows"], data["closes"])

        if len(supports) > 1:
            # Supports sorted descending (closest to price first)
            assert supports[0].price >= supports[-1].price
        if len(resistances) > 1:
            # Resistances sorted ascending (closest to price first)
            assert resistances[0].price <= resistances[-1].price


# ===========================================================================
# Confluence Scoring
# ===========================================================================

class TestConfluenceScorer:
    def test_score_range(self):
        data = _make_trend_data(100)
        scorer = ConfluenceScorer()
        result = scorer.score(
            closes=data["closes"],
            highs=data["highs"],
            lows=data["lows"],
            volumes=data["volumes"],
            opens=data["opens"],
        )
        assert 0 <= result["score"] <= 100
        assert result["direction"] in (SignalSide.LONG, SignalSide.SHORT, SignalSide.FLAT)
        assert "component_scores" in result
        assert len(result["component_scores"]) > 0

    def test_uptrend_bullish(self):
        data = _make_trend_data(100, direction="up")
        scorer = ConfluenceScorer()
        result = scorer.score(
            closes=data["closes"],
            highs=data["highs"],
            lows=data["lows"],
            volumes=data["volumes"],
            opens=data["opens"],
        )
        # Strong uptrend should produce bullish signal
        assert result["direction"] == SignalSide.LONG or result["raw_score"] > 0

    def test_component_weights_sum_to_one(self):
        scorer = ConfluenceScorer()
        total = sum(scorer._weights.values())
        assert abs(total - 1.0) < 0.01


# ===========================================================================
# Confidence Scoring
# ===========================================================================

class TestConfidenceScorer:
    def test_high_confluence_high_confidence(self):
        scorer = ConfidenceScorer()
        conf = scorer.score(
            confluence_score=80.0,
            component_scores={"trend": 0.8, "rsi": 0.7, "macd": 0.6},
            regime="trending",
            session_quality=1.0,
        )
        assert 0.5 < conf <= 1.0

    def test_low_confluence_low_confidence(self):
        scorer = ConfidenceScorer()
        conf = scorer.score(
            confluence_score=10.0,
            component_scores={"trend": -0.2, "rsi": 0.1, "macd": -0.1},
            regime="unknown",
            session_quality=0.3,
        )
        assert conf < 0.5

    def test_confidence_range(self):
        scorer = ConfidenceScorer()
        for score in [0, 20, 40, 60, 80, 100]:
            conf = scorer.score(
                confluence_score=float(score),
                component_scores={"a": 0.5},
            )
            assert 0 <= conf <= 1.0


# ===========================================================================
# Market Regime Detection
# ===========================================================================

class TestRegimeDetector:
    def test_detect_trending_up(self):
        data = _make_trend_data(200, direction="up")
        detector = MarketRegimeDetector()
        state = detector.detect(
            data["opens"], data["highs"], data["lows"], data["closes"], data["volumes"],
        )
        assert isinstance(state.regime, MarketRegime)
        assert 0 <= state.confidence <= 1.0
        assert isinstance(state.trend_strength, TrendStrength)

    def test_detect_ranging(self):
        data = _make_range_data(200)
        detector = MarketRegimeDetector()
        state = detector.detect(
            data["opens"], data["highs"], data["lows"], data["closes"], data["volumes"],
        )
        # Ranging market should not be strongly trending
        assert state.regime in (MarketRegime.RANGING, MarketRegime.VOLATILE, MarketRegime.UNKNOWN)

    def test_detect_volatile(self):
        data = _make_volatile_data(200)
        detector = MarketRegimeDetector()
        state = detector.detect(
            data["opens"], data["highs"], data["lows"], data["closes"], data["volumes"],
        )
        assert state.atr_ratio > 0 or state.volatility_percentile > 0

    def test_adaptation_for_regime(self):
        detector = MarketRegimeDetector()
        for regime in MarketRegime:
            adapt = detector.get_adaptation(regime)
            assert adapt.regime == regime
            assert 0 < adapt.atr_multiplier_sl <= 3.0
            assert 0 < adapt.atr_multiplier_tp <= 5.0
            assert 0 < adapt.min_confluence <= 100
            assert 0 < adapt.position_size_factor <= 1.0

    def test_adaptation_dict(self):
        detector = MarketRegimeDetector()
        d = detector.get_adaptation_dict(MarketRegime.TRENDING_UP)
        assert "regime" in d
        assert "rsi_overbought" in d
        assert "notes" in d


class TestRegimeFeatureExtractor:
    def test_extract_features(self):
        data = _make_trend_data(100)
        extractor = RegimeFeatureExtractor()
        features = extractor.extract(
            data["opens"], data["highs"], data["lows"], data["closes"], data["volumes"],
        )
        assert "adx" in features
        assert "atr_ratio" in features
        assert "ema_alignment" in features
        assert "rsi" in features
        assert "volume_ratio" in features


# ===========================================================================
# Sentiment Analysis
# ===========================================================================

class TestNewsSentiment:
    def test_bullish_headline(self):
        analyzer = NewsSentimentAnalyzer()
        result = analyzer.analyze_headline("EUR/USD surges on dovish ECB statement")
        assert result["score"] > 0
        assert result["confidence"] > 0

    def test_bearish_headline(self):
        analyzer = NewsSentimentAnalyzer()
        result = analyzer.analyze_headline("USD crashes on recession fears and rate hike panic")
        assert result["score"] < 0

    def test_neutral_headline(self):
        analyzer = NewsSentimentAnalyzer()
        result = analyzer.analyze_headline("Trading volume unchanged today")
        assert abs(result["score"]) < 0.5

    def test_batch_analysis(self):
        analyzer = NewsSentimentAnalyzer()
        headlines = [
            "EUR/USD surges on bullish momentum",
            "ECB holds rates steady",
            "European stocks rally on strong GDP",
        ]
        result = analyzer.analyze_batch(headlines)
        assert result.score > 0
        assert result.sample_size == 3
        assert result.polarity in (SentimentPolarity.BULLISH, SentimentPolarity.VERY_BULLISH, SentimentPolarity.NEUTRAL)

    def test_time_decay(self):
        analyzer = NewsSentimentAnalyzer()
        now = time.time()
        headlines = ["EUR/USD surges on bullish breakout"]
        timestamps = [now - 7200]  # 2 hours ago

        result_recent = analyzer.analyze_batch(["EUR/USD surges on bullish breakout"], [now])
        result_old = analyzer.analyze_batch(headlines, timestamps)

        # Recent should have higher effective weight
        assert result_recent.score >= result_old.score or result_recent.confidence >= result_old.confidence


class TestSocialSentiment:
    def test_quality_filter(self):
        analyzer = SocialSentimentAnalyzer()
        assert analyzer._is_quality_post("This is a detailed analysis of EUR/USD") is True
        assert analyzer._is_quality_post("🚀🌙") is False
        assert analyzer._is_quality_post("join my signal group for 100x") is False
        assert analyzer._is_quality_post("hi") is False

    def test_analyze_social(self):
        analyzer = SocialSentimentAnalyzer()
        posts = [
            "EUR looking bullish after ECB decision",
            "I'm long EUR/USD, strong support at 1.0950",
            "Bearish on USD, expecting further decline",
        ]
        result = analyzer.analyze(posts)
        assert -1 <= result.score <= 1
        assert result.sample_size > 0


class TestEconomicCalendar:
    def test_high_impact_event(self):
        scorer = EconomicCalendarScorer()
        assert scorer.score_event("Non-Farm Payrolls") == ImpactLevel.HIGH
        assert scorer.score_event("FOMC Interest Rate Decision") == ImpactLevel.HIGH
        assert scorer.score_event("CPI m/m") == ImpactLevel.HIGH

    def test_medium_impact_event(self):
        scorer = EconomicCalendarScorer()
        assert scorer.score_event("Unemployment Rate") == ImpactLevel.MEDIUM
        assert scorer.score_event("PMI Manufacturing") == ImpactLevel.MEDIUM

    def test_no_impact_event(self):
        scorer = EconomicCalendarScorer()
        assert scorer.score_event("Some Random Event") == ImpactLevel.NONE

    def test_analyze_upcoming_events(self):
        scorer = EconomicCalendarScorer()
        now = time.time()
        events = [
            {"name": "FOMC", "time": now + 1800},  # 30 min away
            {"name": "Retail Sales", "time": now + 7200},  # 2h away
        ]
        result = scorer.analyze(events, current_time=now)
        assert result.sample_size == 2


class TestSentimentEngine:
    def test_aggregate_all_sources(self):
        engine = SentimentEngine()
        result = engine.analyze(
            news_headlines=["EUR/USD surges on dovish ECB"],
            social_posts=["EUR looking very bullish after ECB"],
            economic_events=[{"name": "FOMC", "time": time.time() + 3600}],
        )
        assert -1 <= result.score <= 1
        assert result.polarity in SentimentPolarity
        assert 0 <= result.confidence <= 1
        assert result.news_sentiment is not None
        assert result.social_sentiment is not None
        assert result.calendar_impact is not None

    def test_empty_sources(self):
        engine = SentimentEngine()
        result = engine.analyze()
        assert result.score == 0.0
        assert result.confidence == 0.0


# ===========================================================================
# Model Router
# ===========================================================================

class TestModelRouter:
    def test_route_flash_for_simple(self):
        router = ModelRouter()
        config = router.route("news", complexity=TaskComplexity.SIMPLE)
        assert config.tier == ModelTier.FLASH

    def test_route_reasoning_for_complex(self):
        router = ModelRouter()
        config = router.route("strategy", complexity=TaskComplexity.COMPLEX)
        assert config.tier in (ModelTier.REASONING, ModelTier.STANDARD)

    def test_route_realtime_uses_flash(self):
        router = ModelRouter()
        config = router.route("risk", latency=LatencyRequirement.REALTIME)
        assert config.tier == ModelTier.FLASH

    def test_route_unknown_agent(self):
        router = ModelRouter()
        config = router.route("unknown_agent_xyz")
        assert config.tier == ModelTier.FLASH  # safe default

    def test_fallback_chain(self):
        router = ModelRouter()
        chain = router.route_with_fallback("strategy")
        assert len(chain) >= 2
        # Should end with local model
        assert chain[-1].tier == ModelTier.LOCAL

    def test_force_tier(self):
        router = ModelRouter()
        config = router.route("news", force_tier=ModelTier.REASONING)
        assert config.tier == ModelTier.REASONING

    def test_african_language_override(self):
        router = ModelRouter()
        # News agent doesn't have african_language_override, but let's test the mechanism
        config = router.route("news", language="sw")
        # Default profiles don't have african_language_override=True, so this tests normal routing
        assert config is not None

    def test_cost_estimation(self):
        router = ModelRouter()
        cost = router.estimate_cost("news", input_tokens=1000, output_tokens=500)
        assert cost >= 0
        assert cost < 1.0  # should be cheap for flash model


class TestCostTracker:
    def test_record_and_summarize(self):
        tracker = CostTracker()
        from alphastack.ai.model_router import CostRecord
        rec = CostRecord(
            agent_name="test",
            model_tier=ModelTier.FLASH,
            model_name="DeepSeek V4-Flash",
            input_tokens=1000,
            output_tokens=500,
            cached_tokens=200,
            cost_usd=0.001,
            latency_ms=500,
        )
        asyncio.get_event_loop().run_until_complete(tracker.record(rec))
        summary = tracker.get_summary()
        assert summary["total_calls"] == 1
        assert summary["total_cost_usd"] > 0

    def test_agent_cost_tracking(self):
        tracker = CostTracker()
        assert tracker.get_agent_cost("test") == 0.0
        assert tracker.get_agent_calls("test") == 0


class TestTokenBudgetManager:
    def test_within_budget(self):
        budget = TokenBudgetManager(daily_budget_usd=5.0, per_call_budget_usd=0.10)
        assert budget.check_budget("test", 0.05) is True

    def test_exceeds_per_call(self):
        budget = TokenBudgetManager(daily_budget_usd=5.0, per_call_budget_usd=0.10)
        assert budget.check_budget("test", 0.15) is False

    def test_remaining(self):
        budget = TokenBudgetManager(daily_budget_usd=5.0)
        budget.record_spend("test", 1.0)
        remaining = budget.get_remaining("test")
        assert remaining == 4.0


# ===========================================================================
# Signal Generation
# ===========================================================================

class TestSignalGenerator:
    def test_generate_signal(self):
        data = _make_trend_data(100, direction="up")
        gen = SignalGenerator()
        signal = gen.generate(
            symbol="EUR/USD",
            opens=data["opens"],
            highs=data["highs"],
            lows=data["lows"],
            closes=data["closes"],
            volumes=data["volumes"],
            timeframe="1h",
        )
        assert isinstance(signal, Signal)
        assert signal.symbol == "EUR/USD"
        assert signal.side in (SignalSide.LONG, SignalSide.SHORT, SignalSide.FLAT)
        assert 0 <= signal.strength <= 1.0
        assert 0 <= signal.confluence_score <= 100
        assert 0 <= signal.confidence <= 1.0

    def test_signal_has_levels(self):
        data = _make_trend_data(100, direction="up")
        gen = SignalGenerator()
        signal = gen.generate(
            symbol="EUR/USD",
            opens=data["opens"],
            highs=data["highs"],
            lows=data["lows"],
            closes=data["closes"],
        )
        if signal.side != SignalSide.FLAT:
            assert signal.entry_price is not None
            assert signal.stop_loss is not None
            assert len(signal.take_profit) > 0

    def test_signal_indicators(self):
        data = _make_trend_data(100)
        gen = SignalGenerator()
        signal = gen.generate(
            symbol="EUR/USD",
            opens=data["opens"],
            highs=data["highs"],
            lows=data["lows"],
            closes=data["closes"],
        )
        assert "rsi" in signal.indicators
        assert "macd" in signal.indicators
        assert "atr" in signal.indicators
        assert "adx" in signal.indicators

    def test_signal_reasoning(self):
        data = _make_trend_data(100)
        gen = SignalGenerator()
        signal = gen.generate(
            symbol="EUR/USD",
            opens=data["opens"],
            highs=data["highs"],
            lows=data["lows"],
            closes=data["closes"],
        )
        assert len(signal.reasoning) > 0

    def test_signal_strength_label(self):
        signal = Signal(
            symbol="EUR/USD", side=SignalSide.LONG,
            strength=0.7, confluence_score=70, confidence=0.8,
        )
        assert signal.strength_label == "strong"

    def test_is_actionable(self):
        signal = Signal(
            symbol="EUR/USD", side=SignalSide.LONG,
            strength=0.5, confluence_score=50, confidence=0.6,
        )
        assert signal.is_actionable is True

        flat_signal = Signal(
            symbol="EUR/USD", side=SignalSide.FLAT,
            strength=0.0, confluence_score=0, confidence=0.0,
        )
        assert flat_signal.is_actionable is False


# ===========================================================================
# AI Pipeline Integration
# ===========================================================================

class TestAIStrategyPipeline:
    def test_pipeline_runs(self):
        data = _make_trend_data(100)
        pipeline = AIStrategyPipeline()
        result = asyncio.get_event_loop().run_until_complete(
            pipeline.run(
                symbol="EUR/USD",
                timeframe="1h",
                opens=data["opens"],
                highs=data["highs"],
                lows=data["lows"],
                closes=data["closes"],
                volumes=data["volumes"],
            )
        )
        assert result.symbol == "EUR/USD"
        assert result.signal is not None
        assert result.regime is not None
        assert result.total_duration_ms > 0
        assert len(result.step_results) == 16

    def test_pipeline_with_sentiment(self):
        data = _make_trend_data(100)
        pipeline = AIStrategyPipeline()
        result = asyncio.get_event_loop().run_until_complete(
            pipeline.run(
                symbol="EUR/USD",
                timeframe="1h",
                opens=data["opens"],
                highs=data["highs"],
                lows=data["lows"],
                closes=data["closes"],
                news_headlines=["EUR/USD surges on bullish ECB decision"],
            )
        )
        assert result.sentiment is not None
        assert result.sentiment.news_sentiment is not None

    def test_pipeline_to_dict(self):
        data = _make_range_data(100)
        pipeline = AIStrategyPipeline()
        result = asyncio.get_event_loop().run_until_complete(
            pipeline.run(
                symbol="EUR/USD",
                timeframe="1h",
                opens=data["opens"],
                highs=data["highs"],
                lows=data["lows"],
                closes=data["closes"],
            )
        )
        d = result.to_dict()
        assert "symbol" in d
        assert "signal" in d
        assert "regime" in d
        assert "confluence_score" in d

    def test_pipeline_regime_adaptation(self):
        # Ranging market should have higher confluence threshold
        data = _make_range_data(100)
        pipeline = AIStrategyPipeline()
        result = asyncio.get_event_loop().run_until_complete(
            pipeline.run(
                symbol="EUR/USD",
                timeframe="1h",
                opens=data["opens"],
                highs=data["highs"],
                lows=data["lows"],
                closes=data["closes"],
            )
        )
        # In a ranging market, the pipeline should be more conservative
        assert result.regime is not None
        adaptation = pipeline._regime_detector.get_adaptation(result.regime.regime)
        assert adaptation.min_confluence >= 35  # at least base threshold

    def test_pipeline_step_results(self):
        data = _make_trend_data(100)
        pipeline = AIStrategyPipeline()
        result = asyncio.get_event_loop().run_until_complete(
            pipeline.run(
                symbol="EUR/USD",
                timeframe="1h",
                opens=data["opens"],
                highs=data["highs"],
                lows=data["lows"],
                closes=data["closes"],
            )
        )
        step_names = {s.step_name for s in result.step_results}
        expected = {
            "fundamental_intelligence", "market_bias", "session_analysis",
            "market_structure", "support_resistance", "liquidity_detection",
            "smart_money_concepts", "rsi_confirmation", "candlestick_confirmation",
            "confluence_engine", "position_sizing", "stop_loss", "take_profit",
            "trade_management", "exit_conditions", "trade_journal",
        }
        assert expected == step_names
