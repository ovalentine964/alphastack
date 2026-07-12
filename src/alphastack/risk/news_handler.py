"""News Event Handler for AlphaStack.

Three-phase protocol for high-impact news events:
- Pre-event: Reduce exposure, widen stops
- During: Halt new trading
- After: Gradual resume with tighter monitoring
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class NewsPhase(Enum):
    """Phase of news event handling."""
    NORMAL = "normal"           # No active news event
    PRE_EVENT = "pre_event"     # Approaching high-impact event
    ACTIVE = "active"           # Event is happening (halt trading)
    POST_EVENT = "post_event"   # Event passed, gradual resume


class ImpactLevel(Enum):
    """News event impact level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"  # NFP, CPI, FOMC, ECB rate decisions


@dataclass
class NewsEvent:
    """Represents a scheduled or detected news event."""
    event_id: str
    title: str
    currency: str
    impact: ImpactLevel
    scheduled_time: datetime
    actual_value: Optional[float] = None
    forecast_value: Optional[float] = None
    previous_value: Optional[float] = None
    is_active: bool = False

    @property
    def is_high_impact(self) -> bool:
        """Check if event is high impact."""
        return self.impact in (ImpactLevel.HIGH, ImpactLevel.CRITICAL)


@dataclass
class NewsHandlerConfig:
    """Configuration for news event handling."""
    # Pre-event timing
    pre_event_window_minutes: int = 30      # Start reducing exposure 30min before
    post_event_resume_minutes: int = 15     # Wait 15min after before resuming

    # Exposure reduction
    pre_event_exposure_reduction: float = 0.5  # Reduce exposure by 50% pre-event
    post_event_exposure_limit: float = 0.75    # Start at 75% exposure post-event

    # Volatility thresholds
    volatility_spike_threshold: float = 2.0    # 2x normal volatility = spike
    volatility_spike_cooldown_minutes: int = 10

    # Auto-reduce positions
    auto_reduce_before_critical: bool = True
    critical_event_reduce_pct: float = 0.5     # Reduce 50% before critical events


# Known high-impact recurring events
HIGH_IMPACT_EVENTS = {
    "NFP": {"title": "Non-Farm Payrolls", "currency": "USD", "impact": ImpactLevel.CRITICAL},
    "CPI": {"title": "Consumer Price Index", "currency": "USD", "impact": ImpactLevel.CRITICAL},
    "FOMC": {"title": "FOMC Rate Decision", "currency": "USD", "impact": ImpactLevel.CRITICAL},
    "ECB": {"title": "ECB Rate Decision", "currency": "EUR", "impact": ImpactLevel.CRITICAL},
    "BOE": {"title": "BOE Rate Decision", "currency": "GBP", "impact": ImpactLevel.HIGH},
    "BOJ": {"title": "BOJ Rate Decision", "currency": "JPY", "impact": ImpactLevel.HIGH},
    "GDP": {"title": "GDP Growth Rate", "currency": "USD", "impact": ImpactLevel.HIGH},
    "PMI": {"title": "PMI Manufacturing", "currency": "USD", "impact": ImpactLevel.MEDIUM},
    "RETAIL": {"title": "Retail Sales", "currency": "USD", "impact": ImpactLevel.HIGH},
    "UNEMPLOYMENT": {"title": "Unemployment Rate", "currency": "USD", "impact": ImpactLevel.HIGH},
}


class NewsEventHandler:
    """Handles news events with three-phase protocol.

    Usage:
        handler = NewsEventHandler(config)
        await handler.start()

        # In your trading loop:
        if handler.should_halt_trading():
            return  # Don't trade during news
        exposure_limit = handler.get_exposure_limit()
    """

    def __init__(self, config: Optional[NewsHandlerConfig] = None):
        self.config = config or NewsHandlerConfig()
        self._current_phase = NewsPhase.NORMAL
        self._active_events: list[NewsEvent] = []
        self._upcoming_events: list[NewsEvent] = []
        self._volatility_baseline: dict[str, float] = {}
        self._last_volatility_spike: Optional[datetime] = None
        self._phase_change_callbacks: list = []
        logger.info("NewsEventHandler initialized")

    @property
    def current_phase(self) -> NewsPhase:
        """Get current news handling phase."""
        return self._current_phase

    def register_phase_change_callback(self, callback) -> None:
        """Register callback for phase changes."""
        self._phase_change_callbacks.append(callback)

    async def update_events(self, events: list[NewsEvent]) -> None:
        """Update the list of upcoming news events."""
        self._upcoming_events = sorted(
            [e for e in events if e.scheduled_time > datetime.utcnow()],
            key=lambda e: e.scheduled_time
        )
        self._active_events = [e for e in events if e.is_active]
        await self._evaluate_phase()

    async def _evaluate_phase(self) -> None:
        """Evaluate and update current phase based on events."""
        now = datetime.utcnow()
        old_phase = self._current_phase

        # Check for active events
        active_high_impact = [
            e for e in self._active_events
            if e.is_high_impact and e.is_active
        ]
        if active_high_impact:
            self._current_phase = NewsPhase.ACTIVE
        else:
            # Check upcoming events within pre-event window
            pre_window = now + timedelta(minutes=self.config.pre_event_window_minutes)
            upcoming_high = [
                e for e in self._upcoming_events
                if e.is_high_impact and e.scheduled_time <= pre_window
            ]
            if upcoming_high:
                self._current_phase = NewsPhase.PRE_EVENT
            elif self._current_phase == NewsPhase.POST_EVENT:
                # Check if post-event resume time has passed
                pass  # Will be cleared by resume check
            else:
                self._current_phase = NewsPhase.NORMAL

        if self._current_phase != old_phase:
            logger.info(f"News phase changed: {old_phase.value} → {self._current_phase.value}")
            for cb in self._phase_change_callbacks:
                await cb(old_phase, self._current_phase)

    def should_halt_trading(self) -> bool:
        """Check if trading should be halted due to news events."""
        return self._current_phase in (NewsPhase.ACTIVE, NewsPhase.PRE_EVENT)

    def get_exposure_limit(self) -> float:
        """Get current exposure limit based on news phase."""
        if self._current_phase == NewsPhase.ACTIVE:
            return 0.0  # No exposure during active high-impact event
        elif self._current_phase == NewsPhase.PRE_EVENT:
            return self.config.pre_event_exposure_reduction
        elif self._current_phase == NewsPhase.POST_EVENT:
            return self.config.post_event_exposure_limit
        return 1.0  # Normal full exposure

    def detect_volatility_spike(self, pair: str, current_volatility: float) -> bool:
        """Detect if current volatility is abnormally high."""
        baseline = self._volatility_baseline.get(pair, current_volatility)
        if baseline > 0 and current_volatility / baseline > self.config.volatility_spike_threshold:
            self._last_volatility_spike = datetime.utcnow()
            logger.warning(f"Volatility spike detected on {pair}: "
                         f"{current_volatility:.2f} vs baseline {baseline:.2f}")
            return True
        return False

    def update_volatility_baseline(self, pair: str, volatility: float) -> None:
        """Update volatility baseline for a pair (running average)."""
        current = self._volatility_baseline.get(pair, volatility)
        # Exponential moving average
        self._volatility_baseline[pair] = current * 0.95 + volatility * 0.05

    def get_position_reduction(self) -> float:
        """Get recommended position reduction percentage before critical events."""
        if not self.config.auto_reduce_before_critical:
            return 0.0

        now = datetime.utcnow()
        for event in self._upcoming_events:
            if event.is_high_impact:
                time_until = (event.scheduled_time - now).total_seconds() / 60
                if 0 < time_until <= self.config.pre_event_window_minutes:
                    # Gradual reduction as event approaches
                    urgency = 1.0 - (time_until / self.config.pre_event_window_minutes)
                    return self.config.critical_event_reduce_pct * urgency
        return 0.0

    def get_status(self) -> dict:
        """Get current news handler status."""
        return {
            "phase": self._current_phase.value,
            "active_events": len(self._active_events),
            "upcoming_events": len(self._upcoming_events),
            "next_event": self._upcoming_events[0].title if self._upcoming_events else None,
            "next_event_time": self._upcoming_events[0].scheduled_time.isoformat() if self._upcoming_events else None,
            "exposure_limit": self.get_exposure_limit(),
            "should_halt": self.should_halt_trading(),
            "recommended_reduction": self.get_position_reduction(),
            "last_volatility_spike": self._last_volatility_spike.isoformat() if self._last_volatility_spike else None,
        }

    async def on_trade_closed_during_news(self, event: NewsEvent, pnl: float) -> None:
        """Log trade closed during news event for analysis."""
        logger.info(f"Trade closed during news event '{event.title}': PnL={pnl:.2f}")

    async def resume_trading(self) -> None:
        """Manually resume trading after news event."""
        self._current_phase = NewsPhase.NORMAL
        logger.info("Trading manually resumed after news event")
        for cb in self._phase_change_callbacks:
            await cb(NewsPhase.POST_EVENT, NewsPhase.NORMAL)
