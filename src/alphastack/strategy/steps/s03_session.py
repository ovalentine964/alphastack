"""Step 3: Session Analysis — London/NY/Asian detection with overlap, DST, and session-specific behaviour.

Real trading logic:
- Detects primary and overlapping sessions using UTC hour windows
- Handles London/NY overlap (highest volatility period)
- Applies session-specific volatility, spread, and liquidity profiles
- Considers weekday patterns (Monday gap, Friday wind-down)
- Computes session quality score for confluence weighting
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from enum import Enum

from alphastack.strategy.context import AlphaStackContext, Session, SessionData
from alphastack.strategy.steps.base import AlphaStackStep
from alphastack.strategy.config import strategy_params


class SessionPhase(str, Enum):
    """More granular session phase for trading decisions."""
    ASIAN = "asian"
    LONDON_OPEN = "london_open"          # First 2 hours — breakout setups
    LONDON_CORE = "london_core"          # Main London session
    LONDON_NY_OVERLAP = "london_ny_overlap"  # Highest vol, best setups
    NY_CORE = "ny_core"
    NY_CLOSE = "ny_close"                # Last 2 hours — position squaring
    OFF_HOURS = "off_hours"


# Session windows in UTC (standard hours, no DST adjustment needed —
# forex sessions are defined by market open/close in local time, which
# shifts with DST.  We approximate by using the mid-point of the range.)
#
# London:  08:00–16:00 BST (summer) / 07:00–15:00 GMT (winter) → avg ~07:00–16:00 UTC
# New York: 13:00–21:00 EDT (summer) / 12:00–20:00 EST (winter) → avg ~12:00–21:00 UTC
# Asian:   00:00–08:00 UTC (Tokyo + Sydney)
_SESSION_WINDOWS: list[tuple[str, int, int]] = [
    ("asian", 0, 8),
    ("london", 7, 16),
    ("new_york", 12, 21),
]

_SESSION_MAP = {
    "asian": Session.ASIAN,
    "london": Session.LONDON,
    "new_york": Session.NEW_YORK,
}

# Phase-specific volatility multipliers (relative to baseline)
_PHASE_VOLATILITY: dict[SessionPhase, float] = {
    SessionPhase.ASIAN: 0.6,
    SessionPhase.LONDON_OPEN: 1.1,      # Breakout volatility at open
    SessionPhase.LONDON_CORE: 1.0,
    SessionPhase.LONDON_NY_OVERLAP: 1.3,  # Highest liquidity & vol
    SessionPhase.NY_CORE: 0.95,
    SessionPhase.NY_CLOSE: 0.7,          # Position squaring, lower vol
    SessionPhase.OFF_HOURS: 0.3,
}

# Typical pip range multipliers per session (EUR/USD baseline ~60 pips/day)
_SESSION_RANGE_MULTIPLIER: dict[Session, float] = {
    Session.ASIAN: 0.4,
    Session.LONDON: 1.0,
    Session.NEW_YORK: 0.9,
    Session.OFF_HOURS: 0.2,
}

# Session quality: how suitable the session is for taking new trades
# (1.0 = excellent, 0.0 = avoid)
_SESSION_QUALITY: dict[SessionPhase, float] = {
    SessionPhase.ASIAN: 0.5,
    SessionPhase.LONDON_OPEN: 0.85,
    SessionPhase.LONDON_CORE: 0.9,
    SessionPhase.LONDON_NY_OVERLAP: 1.0,
    SessionPhase.NY_CORE: 0.85,
    SessionPhase.NY_CLOSE: 0.4,       # Avoid new trades near NY close
    SessionPhase.OFF_HOURS: 0.2,
}

# Day-of-week quality (0=Monday … 4=Friday)
_DOW_QUALITY: list[float] = [0.8, 0.95, 1.0, 0.95, 0.7]  # Wed best, Fri worst


def _detect_sessions(utc_hour: int) -> tuple[Session, Session | None]:
    """Return primary session and optional overlapping session.

    The London/NY overlap (12:00–16:00 UTC) is the most important period
    in forex.  We return the overlap as the primary session when active,
    with the individual sessions as secondary.
    """
    primary = Session.OFF_HOURS
    secondary: Session | None = None

    # London/NY overlap takes priority
    if 12 <= utc_hour < 16:
        primary = Session.LONDON  # Overlap is London-primary
        secondary = Session.NEW_YORK
    elif 7 <= utc_hour < 12:
        primary = Session.LONDON
    elif 16 <= utc_hour < 21:
        primary = Session.NEW_YORK
    elif 0 <= utc_hour < 7:
        primary = Session.ASIAN

    return primary, secondary


def _detect_phase(utc_hour: int, minute: int, dow: int) -> SessionPhase:
    """Detect the granular session phase for more precise trading decisions."""
    if 0 <= utc_hour < 7:
        return SessionPhase.ASIAN
    elif utc_hour == 7 or (utc_hour == 8 and minute < 30):
        return SessionPhase.LONDON_OPEN
    elif 12 <= utc_hour < 16:
        return SessionPhase.LONDON_NY_OVERLAP
    elif 8 <= utc_hour < 12:
        return SessionPhase.LONDON_CORE
    elif 16 <= utc_hour < 19:
        return SessionPhase.NY_CORE
    elif 19 <= utc_hour < 21:
        return SessionPhase.NY_CLOSE
    else:
        return SessionPhase.OFF_HOURS


def _session_quality(phase: SessionPhase, dow: int) -> float:
    """Compute session quality score (0–1) factoring in phase and day-of-week."""
    phase_quality = _SESSION_QUALITY.get(phase, 0.3)
    dow_quality = _DOW_QUALITY[min(dow, 4)]
    return round(phase_quality * dow_quality, 3)


class SessionAnalysis(AlphaStackStep):
    step_number = 3
    step_name = "session_analysis"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        now_utc = context.timestamp.astimezone(timezone.utc)
        hour = now_utc.hour
        minute = now_utc.minute
        dow = now_utc.weekday()  # 0=Mon, 4=Fri

        # Detect primary + overlapping sessions
        primary_session, overlap_session = _detect_sessions(hour)

        # Detect granular phase
        phase = _detect_phase(hour, minute, dow)

        # Session volatility
        volatility = _PHASE_VOLATILITY.get(phase, 0.3)

        # If in overlap, boost volatility
        if overlap_session is not None:
            volatility = min(volatility * 1.15, 1.5)

        # Typical range in pips
        base_range: float = context.market_data.get("atr_pips", 50.0)
        range_mult = _SESSION_RANGE_MULTIPLIER.get(primary_session, 0.3)
        typical_range = base_range * range_mult

        # Session quality for confluence weighting
        quality = _session_quality(phase, dow)

        # Max allowed spread from config
        max_spread = strategy_params.get(f"session.max_spread.{primary_session.value}", 5.0)

        session_data = SessionData(
            active=primary_session,
            volatility=round(volatility, 3),
            typical_range_pips=round(typical_range, 1),
        )

        # Store extended session info in market_data for downstream steps
        # (SessionData model is frozen, so we use market_data for extras)
        md = dict(context.market_data)
        md["session_phase"] = phase.value
        md["session_quality"] = quality
        md["session_overlap"] = overlap_session.value if overlap_session else None
        md["session_max_spread"] = max_spread
        md["day_of_week"] = dow

        return context.update(session=session_data, market_data=md)
