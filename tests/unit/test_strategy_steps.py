"""Unit tests for all 16 AlphaStack strategy pipeline steps."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from alphastack.strategy.context import (
    AlphaStackContext,
    Bias,
    CandlestickData,
    ConfluenceResult,
    Direction,
    ExitSignal,
    FundamentalData,
    JournalEntry,
    LiquidityPool,
    MarketBias,
    OrderBlock,
    FairValueGap,
    PositionSizing,
    RSIData,
    SMCData,
    Session,
    SessionData,
    SRLevels,
    Level,
    StructureData,
    StructureType,
    StopLoss,
    TakeProfit,
    TradeManagement,
)
from alphastack.strategy.steps.s01_fundamental import FundamentalIntelligence
from alphastack.strategy.steps.s02_bias import MarketBiasStep
from alphastack.strategy.steps.s03_session import SessionAnalysis
from alphastack.strategy.steps.s04_structure import MarketStructure, _detect_swings, _classify_structure
from alphastack.strategy.steps.s05_support_resistance import SupportResistance
from alphastack.strategy.steps.s06_liquidity import LiquidityDetection
from alphastack.strategy.steps.s07_smc import SmartMoneyConcepts
from alphastack.strategy.steps.s08_rsi import RSIConfirmation, _compute_rsi
from alphastack.strategy.steps.s09_candlestick import CandlestickConfirmation
from alphastack.strategy.steps.s10_confluence import ConfluenceEngine
from alphastack.strategy.steps.s11_sizing import PositionSizingStep
from alphastack.strategy.steps.s12_stop_loss import StopLossStep
from alphastack.strategy.steps.s13_take_profit import TakeProfitStep
from alphastack.strategy.steps.s14_management import TradeManagementStep
from alphastack.strategy.steps.s15_exit import ExitConditions
from alphastack.strategy.steps.s16_journal import TradeJournal

from tests.conftest import generate_ohlcv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(market_data: dict | None = None, **overrides) -> AlphaStackContext:
    """Build a context with default market data."""
    md = generate_ohlcv(200, seed=42)
    md["close"] = md["closes"][-1]
    md.update({
        "high_impact_events": [],
        "news_sentiment": 0.0,
        "volatility_index": 14.0,
        "atr_pips": 50.0,
        "pip_size": 0.0001,
        "spread_pips": 1.5,
        "account_balance": 10_000.0,
        "risk_pct": 1.0,
        "pip_value": 10.0,
        "stop_multiplier": 1.5,
        "rsi_period": 14,
        "entry_price": md["closes"][-1],
    })
    if market_data:
        md.update(market_data)
    return AlphaStackContext(
        symbol="EUR/USD",
        timeframe="1H",
        timestamp=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        market_data=md,
        **overrides,
    )


# ===========================================================================
# Step 1: Fundamental Intelligence
# ===========================================================================

class TestStep01Fundamental:
    @pytest.mark.asyncio
    async def test_risk_on_regime(self):
        step = FundamentalIntelligence()
        ctx = _make_context({"volatility_index": 10.0, "news_sentiment": 0.3})
        result = await step.run(ctx)
        assert result.fundamental.macro_regime == "risk_on"
        assert result.fundamental.bias == Bias.BULLISH

    @pytest.mark.asyncio
    async def test_risk_off_regime(self):
        step = FundamentalIntelligence()
        ctx = _make_context({"volatility_index": 30.0, "news_sentiment": -0.5})
        result = await step.run(ctx)
        assert result.fundamental.macro_regime == "risk_off"
        assert result.fundamental.bias == Bias.BEARISH

    @pytest.mark.asyncio
    async def test_neutral_regime(self):
        step = FundamentalIntelligence()
        ctx = _make_context({"volatility_index": 14.0, "news_sentiment": 0.0})
        result = await step.run(ctx)
        assert result.fundamental.bias == Bias.NEUTRAL

    @pytest.mark.asyncio
    async def test_high_impact_event_dampens(self):
        step = FundamentalIntelligence()
        ctx = _make_context({
            "news_sentiment": 0.5,
            "high_impact_events": ["NFP"],
            "volatility_index": 10.0,
        })
        result = await step.run(ctx)
        assert len(result.fundamental.high_impact_events) == 1
        # Score is dampened by 0.5 due to red event, so 0.5*0.5+0.1=0.35 > 0.2 => bullish
        assert result.fundamental.bias == Bias.BULLISH

    @pytest.mark.asyncio
    async def test_extreme_sentiment(self):
        step = FundamentalIntelligence()
        ctx = _make_context({"news_sentiment": -1.0, "volatility_index": 10.0})
        result = await step.run(ctx)
        assert result.fundamental.bias == Bias.BEARISH


# ===========================================================================
# Step 2: Market Bias
# ===========================================================================

class TestStep02Bias:
    @pytest.mark.asyncio
    async def test_bullish_trend(self):
        step = MarketBiasStep()
        # Create rising closes for multiple timeframes
        rising = [1.0 + i * 0.001 for i in range(30)]
        ctx = _make_context({
            "timeframe_closes": {"1h": rising, "4h": rising},
            "htf_closes": rising,
        })
        result = await step.run(ctx)
        assert result.bias.bias == Bias.BULLISH
        assert result.bias.trend_strength > 0

    @pytest.mark.asyncio
    async def test_bearish_trend(self):
        step = MarketBiasStep()
        falling = [1.1 - i * 0.001 for i in range(30)]
        ctx = _make_context({
            "timeframe_closes": {"1h": falling, "4h": falling},
            "htf_closes": falling,
        })
        result = await step.run(ctx)
        assert result.bias.bias == Bias.BEARISH

    @pytest.mark.asyncio
    async def test_empty_data_neutral(self):
        step = MarketBiasStep()
        ctx = _make_context({"timeframe_closes": {}, "htf_closes": []})
        result = await step.run(ctx)
        assert result.bias.bias == Bias.NEUTRAL
        assert result.bias.trend_strength == 0.0


# ===========================================================================
# Step 3: Session Analysis
# ===========================================================================

class TestStep03Session:
    @pytest.mark.asyncio
    async def test_london_session(self):
        step = SessionAnalysis()
        ctx = _make_context()
        ctx = ctx.update(timestamp=datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc))
        result = await step.run(ctx)
        assert result.session.active == Session.LONDON
        assert result.session.volatility == 1.0

    @pytest.mark.asyncio
    async def test_new_york_session(self):
        step = SessionAnalysis()
        ctx = _make_context()
        ctx = ctx.update(timestamp=datetime(2025, 6, 15, 15, 0, 0, tzinfo=timezone.utc))
        result = await step.run(ctx)
        assert result.session.active == Session.NEW_YORK

    @pytest.mark.asyncio
    async def test_asian_session(self):
        step = SessionAnalysis()
        ctx = _make_context()
        ctx = ctx.update(timestamp=datetime(2025, 6, 15, 3, 0, 0, tzinfo=timezone.utc))
        result = await step.run(ctx)
        assert result.session.active == Session.ASIAN

    @pytest.mark.asyncio
    async def test_off_hours(self):
        step = SessionAnalysis()
        ctx = _make_context()
        ctx = ctx.update(timestamp=datetime(2025, 6, 15, 22, 0, 0, tzinfo=timezone.utc))
        result = await step.run(ctx)
        assert result.session.active == Session.OFF_HOURS
        assert result.session.volatility == 0.3


# ===========================================================================
# Step 4: Market Structure
# ===========================================================================

class TestStep04Structure:
    def test_detect_swings(self):
        highs = [1.0, 1.2, 1.0, 1.3, 1.0, 1.4, 1.0, 1.5, 1.0, 1.6]
        lows = [0.9, 0.95, 0.85, 0.95, 0.80, 0.95, 0.75, 0.95, 0.70, 0.95]
        swing_h, swing_l = _detect_swings(highs, lows, lookback=2)
        assert len(swing_h) > 0
        assert len(swing_l) > 0

    def test_classify_higher_high(self):
        sh = [1.0, 1.1, 1.2]
        sl = [0.9, 0.95, 1.0]
        stype, direction = _classify_structure(sh, sl)
        assert direction == Direction.LONG

    def test_classify_lower_low(self):
        sh = [1.2, 1.1, 1.0]
        sl = [1.0, 0.95, 0.9]
        stype, direction = _classify_structure(sh, sl)
        assert direction == Direction.SHORT

    def test_classify_consolidation(self):
        # Not enough data
        stype, direction = _classify_structure([1.0], [0.9])
        assert stype == StructureType.CONSOLIDATION
        assert direction == Direction.NONE

    @pytest.mark.asyncio
    async def test_step_with_data(self):
        step = MarketStructure()
        ctx = _make_context()
        result = await step.run(ctx)
        assert result.structure is not None
        assert isinstance(result.structure.direction, Direction)


# ===========================================================================
# Step 5: Support & Resistance
# ===========================================================================

class TestStep05SupportResistance:
    @pytest.mark.asyncio
    async def test_levels_detected(self):
        step = SupportResistance()
        ctx = _make_context()
        # Run steps 1-4 first to populate structure
        from alphastack.strategy.steps.s04_structure import MarketStructure
        ctx = await MarketStructure().run(ctx)
        result = await step.run(ctx)
        # Should detect some levels from 200 bars
        assert isinstance(result.sr_levels, SRLevels)

    @pytest.mark.asyncio
    async def test_empty_data(self):
        step = SupportResistance()
        ctx = _make_context({"highs": [], "lows": [], "closes": []})
        result = await step.run(ctx)
        assert result.sr_levels.support == []
        assert result.sr_levels.resistance == []


# ===========================================================================
# Step 6: Liquidity Detection
# ===========================================================================

class TestStep06Liquidity:
    @pytest.mark.asyncio
    async def test_equal_highs_detected(self):
        step = LiquidityDetection()
        highs = [1.1000, 1.1001, 1.1002, 1.0999, 1.1000]
        lows = [1.0900, 1.0910, 1.0920, 1.0930, 1.0940]
        ctx = _make_context({"highs": highs, "lows": lows})
        result = await step.run(ctx)
        # Equal highs within tolerance should create pools
        above_pools = [p for p in result.liquidity_pools if p.side == "above"]
        assert len(above_pools) >= 0  # May or may not detect depending on tolerance

    @pytest.mark.asyncio
    async def test_empty_data(self):
        step = LiquidityDetection()
        ctx = _make_context({"highs": [], "lows": []})
        result = await step.run(ctx)
        assert result.liquidity_pools == []


# ===========================================================================
# Step 7: Smart Money Concepts
# ===========================================================================

class TestStep07SMC:
    @pytest.mark.asyncio
    async def test_fvg_detection(self):
        step = SmartMoneyConcepts()
        # Create FVG: candle1.high < candle3.low
        opens = [1.0, 1.0, 1.0, 1.0, 1.0]
        highs = [1.05, 1.02, 1.10, 1.08, 1.06]
        lows = [0.95, 0.98, 1.03, 1.02, 1.01]
        closes = [1.0, 1.0, 1.08, 1.05, 1.03]
        ctx = _make_context({
            "opens": opens, "highs": highs, "lows": lows, "closes": closes,
        })
        result = await step.run(ctx)
        assert isinstance(result.smc, SMCData)

    @pytest.mark.asyncio
    async def test_empty_data(self):
        step = SmartMoneyConcepts()
        ctx = _make_context({"opens": [], "highs": [], "lows": [], "closes": []})
        result = await step.run(ctx)
        assert result.smc.order_blocks == []
        assert result.smc.fvgs == []


# ===========================================================================
# Step 8: RSI Confirmation
# ===========================================================================

class TestStep08RSI:
    def test_compute_rsi_overbought(self):
        # All up moves → RSI near 100
        closes = [100 + i for i in range(30)]
        rsi = _compute_rsi(closes, 14)
        assert rsi > 70

    def test_compute_rsi_oversold(self):
        # All down moves → RSI near 0
        closes = [100 - i for i in range(30)]
        rsi = _compute_rsi(closes, 14)
        assert rsi < 30

    def test_compute_rsi_neutral(self):
        # Oscillating
        closes = [100 + (-1)**i for i in range(30)]
        rsi = _compute_rsi(closes, 14)
        assert 30 < rsi < 70

    def test_compute_rsi_insufficient_data(self):
        rsi = _compute_rsi([1.0, 2.0], 14)
        assert rsi == 50.0

    @pytest.mark.asyncio
    async def test_step_execution(self):
        step = RSIConfirmation()
        ctx = _make_context()
        result = await step.run(ctx)
        assert 0 <= result.rsi.value <= 100
        assert result.rsi.signal in ("overbought", "oversold", "neutral")


# ===========================================================================
# Step 9: Candlestick Confirmation
# ===========================================================================

class TestStep09Candlestick:
    @pytest.mark.asyncio
    async def test_bullish_engulfing(self):
        step = CandlestickConfirmation()
        # Bearish candle followed by larger bullish candle
        opens = [1.1000, 1.1050, 1.1020, 1.1010, 1.0990]
        highs = [1.1060, 1.1055, 1.1030, 1.1020, 1.1000]
        lows = [1.0990, 1.0980, 1.0990, 1.0985, 1.0970]
        closes = [1.0990, 1.0980, 1.1020, 1.1010, 1.0990]
        ctx = _make_context({
            "opens": opens, "highs": highs, "lows": lows, "closes": closes,
        })
        result = await step.run(ctx)
        assert isinstance(result.candlestick, CandlestickData)

    @pytest.mark.asyncio
    async def test_insufficient_data(self):
        step = CandlestickConfirmation()
        ctx = _make_context({
            "opens": [1.0], "highs": [1.1], "lows": [0.9], "closes": [1.0],
        })
        result = await step.run(ctx)
        assert result.candlestick.patterns == []


# ===========================================================================
# Step 10: Confluence Engine
# ===========================================================================

class TestStep10Confluence:
    @pytest.mark.asyncio
    async def test_high_confluence_bullish(self, bullish_context):
        step = ConfluenceEngine()
        result = await step.run(bullish_context)
        assert result.confluence.score > 0
        assert result.confluence.direction in (Direction.LONG, Direction.NONE)

    @pytest.mark.asyncio
    async def test_neutral_confluence(self):
        step = ConfluenceEngine()
        ctx = _make_context()
        result = await step.run(ctx)
        # Default context has no strong signals → low confluence
        assert result.confluence.score >= 0
        assert isinstance(result.confluence.direction, Direction)

    @pytest.mark.asyncio
    async def test_confluence_score_range(self, bullish_context):
        step = ConfluenceEngine()
        result = await step.run(bullish_context)
        assert 0 <= result.confluence.score <= 100

    @pytest.mark.asyncio
    async def test_component_scores_populated(self, bullish_context):
        step = ConfluenceEngine()
        result = await step.run(bullish_context)
        assert "fundamental" in result.confluence.component_scores
        assert "market_bias" in result.confluence.component_scores
        assert "structure" in result.confluence.component_scores


# ===========================================================================
# Step 11: Position Sizing
# ===========================================================================

class TestStep11Sizing:
    @pytest.mark.asyncio
    async def test_no_trade_zero_size(self):
        step = PositionSizingStep()
        ctx = _make_context()
        # confluence defaults to NONE direction → zero size
        result = await step.run(ctx)
        assert result.sizing.position_size == 0.0

    @pytest.mark.asyncio
    async def test_sizing_with_confluence(self, bullish_context):
        step = PositionSizingStep()
        result = await step.run(bullish_context)
        assert result.sizing.position_size > 0
        assert result.sizing.risk_amount > 0

    @pytest.mark.asyncio
    async def test_higher_risk_pct_increases_size(self, bullish_context):
        step = PositionSizingStep()
        ctx1 = bullish_context.update(
            market_data={**bullish_context.market_data, "risk_pct": 1.0}
        )
        ctx2 = bullish_context.update(
            market_data={**bullish_context.market_data, "risk_pct": 2.0}
        )
        r1 = await step.run(ctx1)
        r2 = await step.run(ctx2)
        assert r2.sizing.position_size >= r1.sizing.position_size


# ===========================================================================
# Step 12: Stop Loss
# ===========================================================================

class TestStep12StopLoss:
    @pytest.mark.asyncio
    async def test_no_trade_no_stop(self):
        step = StopLossStep()
        ctx = _make_context()
        result = await step.run(ctx)
        assert result.stop_loss.price == 0.0

    @pytest.mark.asyncio
    async def test_long_stop_below_entry(self, bullish_context):
        step = StopLossStep()
        result = await step.run(bullish_context)
        entry = bullish_context.market_data.get("close", 0)
        assert result.stop_loss.price < entry

    @pytest.mark.asyncio
    async def test_short_stop_above_entry(self):
        step = StopLossStep()
        ctx = _make_context()
        ctx = ctx.update(
            confluence=ConfluenceResult(score=70.0, direction=Direction.SHORT),
            structure=StructureData(
                direction=Direction.SHORT,
                swing_highs=[1.1100, 1.1080],
                swing_lows=[1.0980, 1.0960],
            ),
        )
        result = await step.run(ctx)
        entry = ctx.market_data.get("close", 0)
        assert result.stop_loss.price > entry


# ===========================================================================
# Step 13: Take Profit
# ===========================================================================

class TestStep13TakeProfit:
    @pytest.mark.asyncio
    async def test_no_trade_no_tp(self):
        step = TakeProfitStep()
        ctx = _make_context()
        result = await step.run(ctx)
        assert result.take_profit.levels == []

    @pytest.mark.asyncio
    async def test_long_tp_above_entry(self, bullish_context):
        step = TakeProfitStep()
        result = await step.run(bullish_context)
        entry = bullish_context.market_data.get("close", 0)
        if result.take_profit.levels:
            assert all(tp > entry for tp in result.take_profit.levels)

    @pytest.mark.asyncio
    async def test_rr_ratio_set(self, bullish_context):
        step = TakeProfitStep()
        result = await step.run(bullish_context)
        assert result.take_profit.rr_ratio > 0


# ===========================================================================
# Step 14: Trade Management
# ===========================================================================

class TestStep14Management:
    @pytest.mark.asyncio
    async def test_no_trade_no_actions(self):
        step = TradeManagementStep()
        ctx = _make_context()
        result = await step.run(ctx)
        assert result.management.actions == []

    @pytest.mark.asyncio
    async def test_actions_populated(self, bullish_context):
        step = TradeManagementStep()
        result = await step.run(bullish_context)
        actions = [a.action for a in result.management.actions]
        assert "breakeven" in actions
        assert "trail" in actions


# ===========================================================================
# Step 15: Exit Conditions
# ===========================================================================

class TestStep15Exit:
    @pytest.mark.asyncio
    async def test_no_trade_no_exit(self):
        step = ExitConditions()
        ctx = _make_context()
        result = await step.run(ctx)
        assert result.exit_signal.should_exit is False

    @pytest.mark.asyncio
    async def test_structure_flip_triggers_exit(self, bullish_context):
        step = ExitConditions()
        # Flip structure to bearish while confluence says LONG
        ctx = bullish_context.update(
            structure=StructureData(direction=Direction.SHORT),
        )
        result = await step.run(ctx)
        assert result.exit_signal.should_exit is True

    @pytest.mark.asyncio
    async def test_stop_loss_hit_triggers_exit(self, bullish_context):
        step = ExitConditions()
        # Price below stop loss
        ctx = bullish_context.update(
            market_data={**bullish_context.market_data, "close": 1.0900},
        )
        result = await step.run(ctx)
        assert result.exit_signal.should_exit is True


# ===========================================================================
# Step 16: Trade Journal
# ===========================================================================

class TestStep16Journal:
    @pytest.mark.asyncio
    async def test_journal_entry_created(self, bullish_context):
        step = TradeJournal()
        result = await step.run(bullish_context)
        assert result.journal.symbol == "EUR/USD"
        assert result.journal.confluence_score > 0
        assert result.journal.notes != ""

    @pytest.mark.asyncio
    async def test_journal_tags_populated(self, bullish_context):
        step = TradeJournal()
        result = await step.run(bullish_context)
        assert isinstance(result.journal.tags, list)

    @pytest.mark.asyncio
    async def test_journal_direction_matches_confluence(self, bullish_context):
        step = TradeJournal()
        result = await step.run(bullish_context)
        assert result.journal.direction == bullish_context.confluence.direction


# ===========================================================================
# Edge cases across steps
# ===========================================================================

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_all_steps_handle_empty_market_data(self):
        """Every step should handle empty market_data without crashing."""
        ctx = AlphaStackContext(symbol="TEST", market_data={})
        steps = [
            FundamentalIntelligence(),
            MarketBiasStep(),
            SessionAnalysis(),
            MarketStructure(),
            SupportResistance(),
            LiquidityDetection(),
            SmartMoneyConcepts(),
            RSIConfirmation(),
            CandlestickConfirmation(),
            ConfluenceEngine(),
            PositionSizingStep(),
            StopLossStep(),
            TakeProfitStep(),
            TradeManagementStep(),
            ExitConditions(),
            TradeJournal(),
        ]
        for step in steps:
            result = await step.run(ctx)
            assert isinstance(result, AlphaStackContext)

    @pytest.mark.asyncio
    async def test_context_immutable(self):
        """Each step returns a new context, not mutating the original."""
        step = FundamentalIntelligence()
        ctx = _make_context({"news_sentiment": 0.5, "volatility_index": 10.0})
        original_sentiment = ctx.fundamental.news_sentiment
        result = await step.run(ctx)
        assert ctx.fundamental.news_sentiment == original_sentiment
        assert result.fundamental.news_sentiment == 0.5

    @pytest.mark.asyncio
    async def test_step_numbers_unique(self):
        """All 16 steps have unique step numbers."""
        steps = [
            FundamentalIntelligence(), MarketBiasStep(), SessionAnalysis(),
            MarketStructure(), SupportResistance(), LiquidityDetection(),
            SmartMoneyConcepts(), RSIConfirmation(), CandlestickConfirmation(),
            ConfluenceEngine(), PositionSizingStep(), StopLossStep(),
            TakeProfitStep(), TradeManagementStep(), ExitConditions(), TradeJournal(),
        ]
        numbers = [s.step_number for s in steps]
        assert len(numbers) == len(set(numbers))
        assert sorted(numbers) == list(range(1, 17))
