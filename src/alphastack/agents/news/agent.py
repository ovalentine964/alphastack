"""News Agent — monitors news feeds and detects high-impact events.

This agent scans incoming news for scheduled economic events (NFP, CPI,
FOMC, etc.) and breaking news that could affect open positions. When a
high-impact event is detected it signals the risk agent to tighten limits.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from alphastack.agents.base import AlphaStackAgent
from alphastack.core.events import EventBus
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

# High-impact economic events and their typical risk multipliers
HIGH_IMPACT_EVENTS: dict[str, dict[str, Any]] = {
    "NFP": {"impact": "critical", "multiplier": 0.7, "description": "Non-Farm Payrolls"},
    "CPI": {"impact": "critical", "multiplier": 0.6, "description": "Consumer Price Index"},
    "FOMC": {"impact": "critical", "multiplier": 0.8, "description": "Federal Open Market Committee"},
    "ECB": {"impact": "high", "multiplier": 0.5, "description": "European Central Bank Rate Decision"},
    "BOE": {"impact": "high", "multiplier": 0.4, "description": "Bank of England Rate Decision"},
    "GDP": {"impact": "high", "multiplier": 0.4, "description": "Gross Domestic Product"},
    "RETAIL_SALES": {"impact": "medium", "multiplier": 0.3, "description": "Retail Sales"},
    "PMI": {"impact": "medium", "multiplier": 0.2, "description": "Purchasing Managers Index"},
    "UNEMPLOYMENT": {"impact": "high", "multiplier": 0.5, "description": "Unemployment Rate"},
    "EARNINGS": {"impact": "high", "multiplier": 0.4, "description": "Corporate Earnings Report"},
}


class NewsAgent(AlphaStackAgent):
    """Monitors news feeds and detects high-impact market events.

    Responsibilities:
    - Scan incoming news for scheduled economic events
    - Detect breaking news affecting open positions
    - Compute a risk adjustment multiplier for the strategy agent
    - Alert other agents of critical events
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__(
            name="news",
            role="monitor",
            description="Monitors news feeds and detects high-impact events",
            event_bus=event_bus,
        )

    def system_prompt(self) -> str:
        return (
            "You are the AlphaStack News Agent. Your job is to:\n"
            "1. Monitor incoming news feeds for economic events\n"
            "2. Detect high-impact events: NFP, CPI, FOMC, ECB, BOE, GDP, earnings\n"
            "3. Classify impact as low/medium/high/critical\n"
            "4. Compute a risk adjustment multiplier (0.0-1.0) for position sizing\n"
            "5. Alert other agents when critical events are imminent\n"
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Scan news and return alerts + risk adjustment."""
        market_data = state.get("market_data", {})
        symbol = state.get("current_symbol", "")

        logger.info("news_agent.scanning", symbol=symbol)

        news_alerts = []
        risk_adjustment = 0.0

        # Check market data for embedded news/event metadata
        news_items = market_data.get("news", [])
        calendar_events = market_data.get("economic_calendar", [])

        # Process calendar events
        for event in calendar_events:
            alert = self._evaluate_calendar_event(event, symbol)
            if alert:
                news_alerts.append(alert)
                risk_adjustment = max(risk_adjustment, alert.get("risk_multiplier", 0.0))

        # Process news feed items
        for item in news_items:
            alert = self._evaluate_news_item(item, symbol)
            if alert:
                news_alerts.append(alert)
                risk_adjustment = max(risk_adjustment, alert.get("risk_multiplier", 0.0))

        # Scan for known high-impact patterns in any text data
        raw_text = market_data.get("news_text", "")
        if raw_text:
            for event_type, meta in HIGH_IMPACT_EVENTS.items():
                if event_type.lower() in raw_text.lower():
                    alert = {
                        "id": uuid.uuid4().hex[:12],
                        "headline": f"Detected {meta['description']} ({event_type}) in news feed",
                        "source": "news_scan",
                        "impact": meta["impact"],
                        "event_type": event_type,
                        "affected_symbols": [symbol] if symbol else [],
                        "timestamp": datetime.utcnow().isoformat(),
                        "recommendation": self._make_recommendation(event_type, meta),
                        "risk_multiplier": meta["multiplier"],
                    }
                    news_alerts.append(alert)
                    risk_adjustment = max(risk_adjustment, meta["multiplier"])

        logger.info(
            "news_agent.complete",
            alerts=len(news_alerts),
            risk_adjustment=risk_adjustment,
        )

        return {
            "news_alerts": news_alerts,
            "news_risk_adjustment": risk_adjustment,
            "_confidence": 0.9 if news_alerts else 0.5,
        }

    def _evaluate_calendar_event(self, event: dict[str, Any], symbol: str) -> dict[str, Any] | None:
        """Evaluate an economic calendar event."""
        event_type = event.get("type", "").upper()
        if event_type not in HIGH_IMPACT_EVENTS:
            return None

        meta = HIGH_IMPACT_EVENTS[event_type]
        affected = event.get("affected_symbols", [])
        if symbol and symbol not in affected and affected:
            return None  # Not relevant to current symbol

        return {
            "id": uuid.uuid4().hex[:12],
            "headline": event.get("title", meta["description"]),
            "source": event.get("source", "economic_calendar"),
            "impact": meta["impact"],
            "event_type": event_type,
            "affected_symbols": affected or [symbol],
            "timestamp": event.get("time", datetime.utcnow().isoformat()),
            "recommendation": self._make_recommendation(event_type, meta),
            "risk_multiplier": meta["multiplier"],
        }

    def _evaluate_news_item(self, item: dict[str, Any], symbol: str) -> dict[str, Any] | None:
        """Evaluate a news feed item for impact."""
        headline = item.get("headline", "")
        impact = item.get("impact", "low")

        # Only care about medium+ impact
        if impact not in ("medium", "high", "critical"):
            return None

        # Check if symbol-related
        affected_symbols = item.get("symbols", [])
        if symbol and affected_symbols and symbol not in affected_symbols:
            return None

        multiplier = {"medium": 0.2, "high": 0.5, "critical": 0.7}.get(impact, 0.0)

        return {
            "id": uuid.uuid4().hex[:12],
            "headline": headline,
            "source": item.get("source", "news_feed"),
            "impact": impact,
            "event_type": item.get("category", "general"),
            "affected_symbols": affected_symbols or [symbol],
            "timestamp": item.get("time", datetime.utcnow().isoformat()),
            "recommendation": f"Review positions in affected symbols. Impact: {impact}",
            "risk_multiplier": multiplier,
        }

    @staticmethod
    def _make_recommendation(event_type: str, meta: dict[str, Any]) -> str:
        """Generate a human-readable recommendation."""
        desc = meta["description"]
        mult = meta["multiplier"]
        return (
            f"{desc} detected. Reduce position sizing by {mult * 100:.0f}%. "
            f"Consider widening stops. Avoid new entries 30 min before/after event."
        )
