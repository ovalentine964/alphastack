"""Immutable strategy context that flows through the 16-step pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Bias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class Session(str, Enum):
    LONDON = "london"
    NEW_YORK = "new_york"
    ASIAN = "asian"
    OFF_HOURS = "off_hours"


class StructureType(str, Enum):
    HIGHER_HIGH = "higher_high"
    HIGHER_LOW = "higher_low"
    LOWER_HIGH = "lower_high"
    LOWER_LOW = "lower_low"
    CONSOLIDATION = "consolidation"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"


# ---------------------------------------------------------------------------
# Sub-models carried inside the context
# ---------------------------------------------------------------------------

class FundamentalData(BaseModel):
    bias: Bias = Bias.NEUTRAL
    news_sentiment: float = 0.0  # -1 … +1
    macro_regime: str = "neutral"
    high_impact_events: list[str] = Field(default_factory=list)


class MarketBias(BaseModel):
    bias: Bias = Bias.NEUTRAL
    trend_strength: float = 0.0  # 0 … 1
    htf_bias: Bias = Bias.NEUTRAL  # higher-timeframe


class SessionData(BaseModel):
    active: Session = Session.OFF_HOURS
    volatility: float = 0.0  # 0 … 1
    typical_range_pips: float = 0.0


class StructureData(BaseModel):
    structure_type: StructureType = StructureType.CONSOLIDATION
    direction: Direction = Direction.NONE
    swing_highs: list[float] = Field(default_factory=list)
    swing_lows: list[float] = Field(default_factory=list)


class Level(BaseModel):
    price: float
    strength: float = 0.0  # 0 … 1
    touches: int = 0
    label: str = ""


class SRLevels(BaseModel):
    support: list[Level] = Field(default_factory=list)
    resistance: list[Level] = Field(default_factory=list)


class LiquidityPool(BaseModel):
    price: float
    side: str  # "above" | "below"
    strength: float = 0.0
    label: str = ""


class OrderBlock(BaseModel):
    high: float
    low: float
    direction: Direction
    mitigated: bool = False


class FairValueGap(BaseModel):
    high: float
    low: float
    direction: Direction
    filled: bool = False


class SMCData(BaseModel):
    order_blocks: list[OrderBlock] = Field(default_factory=list)
    fvgs: list[FairValueGap] = Field(default_factory=list)
    breaker_blocks: list[OrderBlock] = Field(default_factory=list)


class RSIData(BaseModel):
    value: float = 50.0
    signal: str = "neutral"  # "overbought" | "oversold" | "neutral"
    divergence: str = "none"  # "bullish" | "bearish" | "none"


class CandlePattern(BaseModel):
    name: str
    direction: Direction
    strength: float = 0.0
    index: int = 0


class CandlestickData(BaseModel):
    patterns: list[CandlePattern] = Field(default_factory=list)
    pattern_score: float = 0.0  # 0 … 1


class ConfluenceResult(BaseModel):
    score: float = 0.0  # 0 … 100
    direction: Direction = Direction.NONE
    component_scores: dict[str, float] = Field(default_factory=dict)


class PositionSizing(BaseModel):
    position_size: float = 0.0
    risk_amount: float = 0.0
    risk_pct: float = 0.0


class StopLoss(BaseModel):
    price: float = 0.0
    stop_type: str = "atr"  # "atr" | "structure"
    atr_value: float = 0.0


class TakeProfit(BaseModel):
    levels: list[float] = Field(default_factory=list)
    rr_ratio: float = 0.0


class ManagementAction(BaseModel):
    action: str  # "trail" | "breakeven" | "partial_close"
    trigger_price: float = 0.0
    params: dict[str, Any] = Field(default_factory=dict)


class TradeManagement(BaseModel):
    actions: list[ManagementAction] = Field(default_factory=list)


class ExitSignal(BaseModel):
    should_exit: bool = False
    reason: str = ""


class JournalEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    symbol: str = ""
    direction: Direction = Direction.NONE
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: list[float] = Field(default_factory=list)
    position_size: float = 0.0
    confluence_score: float = 0.0
    notes: str = ""
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pipeline context (immutable per step — each step returns a new copy)
# ---------------------------------------------------------------------------

class AlphaStackContext(BaseModel, frozen=True):
    """Immutable context threaded through all 16 pipeline steps."""

    # --- identifiers ---
    symbol: str = ""
    timeframe: str = "1H"
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # --- raw market data (carried externally; steps read what they need) ---
    market_data: dict[str, Any] = Field(default_factory=dict)

    # --- step outputs ---
    fundamental: FundamentalData = Field(default_factory=FundamentalData)
    bias: MarketBias = Field(default_factory=MarketBias)
    session: SessionData = Field(default_factory=SessionData)
    structure: StructureData = Field(default_factory=StructureData)
    sr_levels: SRLevels = Field(default_factory=SRLevels)
    liquidity_pools: list[LiquidityPool] = Field(default_factory=list)
    smc: SMCData = Field(default_factory=SMCData)
    rsi: RSIData = Field(default_factory=RSIData)
    candlestick: CandlestickData = Field(default_factory=CandlestickData)
    confluence: ConfluenceResult = Field(default_factory=ConfluenceResult)
    sizing: PositionSizing = Field(default_factory=PositionSizing)
    stop_loss: StopLoss = Field(default_factory=StopLoss)
    take_profit: TakeProfit = Field(default_factory=TakeProfit)
    management: TradeManagement = Field(default_factory=TradeManagement)
    exit_signal: ExitSignal = Field(default_factory=ExitSignal)
    journal: JournalEntry = Field(default_factory=JournalEntry)

    # --- helpers ---
    def update(self, **kwargs: Any) -> "AlphaStackContext":
        """Return a new context with *kwargs* merged (frozen-model pattern)."""
        return self.model_copy(update=kwargs)
