"""Step 3: Session Analysis — London/NY/Asian detection and session-specific behaviour."""

from __future__ import annotations

from datetime import datetime, timezone

from alphastack.strategy.context import AlphaStackContext, Session, SessionData
from alphastack.strategy.steps.base import AlphaStackStep

# Session windows in UTC (approximate)
_SESSION_WINDOWS: list[tuple[str, int, int]] = [
    ("asian", 0, 8),       # 00:00–08:00 UTC
    ("london", 7, 16),     # 07:00–16:00 UTC
    ("new_york", 12, 21),  # 12:00–21:00 UTC
]

_SESSION_MAP = {
    "asian": Session.ASIAN,
    "london": Session.LONDON,
    "new_york": Session.NEW_YORK,
}

# Typical range multipliers per session (relative to Asian baseline)
_VOLATILITY_MAP = {
    Session.ASIAN: 0.6,
    Session.LONDON: 1.0,
    Session.NEW_YORK: 0.9,
    Session.OFF_HOURS: 0.3,
}


class SessionAnalysis(AlphaStackStep):
    step_number = 3
    step_name = "session_analysis"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        now_utc = context.timestamp.astimezone(timezone.utc)
        hour = now_utc.hour

        # Detect active session(s)
        active_name = "off_hours"
        for name, start, end in _SESSION_WINDOWS:
            # Handle wrap-around (e.g. if we ever had 22-06)
            if start <= end:
                if start <= hour < end:
                    active_name = name
                    break
            else:
                if hour >= start or hour < end:
                    active_name = name
                    break

        active_session = _SESSION_MAP.get(active_name, Session.OFF_HOURS)

        # Session volatility estimate
        volatility = _VOLATILITY_MAP.get(active_session, 0.3)

        # Typical range in pips (from market data or default)
        base_range: float = context.market_data.get("atr_pips", 50.0)
        typical_range = base_range * volatility

        session_data = SessionData(
            active=active_session,
            volatility=volatility,
            typical_range_pips=round(typical_range, 1),
        )

        return context.update(session=session_data)
