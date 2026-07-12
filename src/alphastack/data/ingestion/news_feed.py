"""News Feed – economic calendar, sentiment scoring, event detection."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

from alphastack.core.config import get_settings
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class Impact(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SentimentLabel(str, Enum):
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"


@dataclass(frozen=True, slots=True)
class EconomicEvent:
    """Calendar event (NFP, CPI, FOMC, etc.)."""

    event_id: str
    title: str
    country: str
    impact: Impact
    timestamp: datetime
    forecast: str | None = None
    previous: str | None = None
    actual: str | None = None
    currency: str | None = None


@dataclass(slots=True)
class NewsArticle:
    """Normalised news item."""

    article_id: str
    title: str
    body: str
    source: str
    url: str
    published_at: datetime
    symbols: list[str] = field(default_factory=list)
    sentiment: SentimentLabel = SentimentLabel.NEUTRAL
    sentiment_score: float = 0.0  # -1.0 … +1.0
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Known macro event patterns
# ---------------------------------------------------------------------------

MACRO_EVENT_PATTERNS: dict[str, list[str]] = {
    "nfp": ["non-farm payroll", "nonfarm payroll", "nfp"],
    "cpi": ["consumer price index", "cpi", "inflation rate"],
    "fomc": ["federal open market committee", "fomc", "fed rate decision"],
    "gdp": ["gross domestic product", "gdp"],
    "pmi": ["purchasing managers", "pmi"],
    "retail_sales": ["retail sales"],
    "unemployment": ["unemployment rate", "jobless claims"],
}


def detect_macro_event(title: str) -> str | None:
    """Return canonical event key if title matches a known macro pattern."""
    lower = title.lower()
    for key, patterns in MACRO_EVENT_PATTERNS.items():
        if any(p in lower for p in patterns):
            return key
    return None


# ---------------------------------------------------------------------------
# Sentiment scorer (FinBERT-ready)
# ---------------------------------------------------------------------------

class SentimentScorer:
    """Pluggable sentiment scorer. Ships with a simple keyword baseline;
    swap in FinBERT by overriding ``score``."""

    _BEARISH = {"crash", "recession", "sell-off", "bearish", "decline", "plunge", "drop", "loss"}
    _BULLISH = {"rally", "surge", "bullish", "gain", "record", "soar", "growth", "boom"}

    def score(self, text: str) -> tuple[SentimentLabel, float]:
        """Return (label, score) for *text*.

        Score range: -1.0 (very bearish) to +1.0 (very bullish).
        """
        words = set(text.lower().split())
        bear = len(words & self._BEARISH)
        bull = len(words & self._BULLISH)
        total = bear + bull or 1
        raw = (bull - bear) / total

        if raw >= 0.5:
            label = SentimentLabel.VERY_BULLISH
        elif raw >= 0.15:
            label = SentimentLabel.BULLISH
        elif raw <= -0.5:
            label = SentimentLabel.VERY_BEARISH
        elif raw <= -0.15:
            label = SentimentLabel.BEARISH
        else:
            label = SentimentLabel.NEUTRAL
        return label, round(raw, 4)


# ---------------------------------------------------------------------------
# News feed fetcher
# ---------------------------------------------------------------------------

class NewsFeed:
    """Periodic news fetcher with sentiment scoring and event detection."""

    def __init__(
        self,
        poll_interval: float = 60.0,
        scorer: SentimentScorer | None = None,
    ) -> None:
        self.poll_interval = poll_interval
        self.scorer = scorer or SentimentScorer()
        self._running = False
        self._articles: list[NewsArticle] = []
        self._seen_ids: set[str] = set()

    async def fetch_calendar(self) -> list[EconomicEvent]:
        """Fetch upcoming economic calendar events.

        Uses ForexFactory-style scraping or API when configured.
        Returns an empty list if no feed is configured.
        """
        settings = get_settings()
        # Placeholder – wire up to real calendar API (e.g., investing.com, forexfactory)
        logger.debug("fetch_calendar_stub")
        return []

    async def fetch_news(self, limit: int = 50) -> list[NewsArticle]:
        """Fetch latest news articles from configured sources.

        Supports multiple upstream providers; returns normalised articles.
        """
        settings = get_settings()
        articles: list[NewsArticle] = []

        # Polygon.io news
        api_key = settings.feeds.polygon_api_key
        if api_key:
            articles.extend(await self._fetch_polygon_news(api_key.get_secret_value(), limit))

        # Score and tag
        for art in articles:
            if art.article_id not in self._seen_ids:
                art.sentiment, art.sentiment_score = self.scorer.score(f"{art.title} {art.body}")
                macro = detect_macro_event(art.title)
                if macro:
                    art.tags.append(macro)
                self._seen_ids.add(art.article_id)

        self._articles.extend(articles)
        return articles

    async def _fetch_polygon_news(self, api_key: str, limit: int) -> list[NewsArticle]:
        """Fetch from Polygon.io /v2/reference/news."""
        url = "https://api.polygon.io/v2/reference/news"
        params = {"limit": limit, "apiKey": api_key}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.warning("polygon_news_fetch_failed")
            return []

        articles: list[NewsArticle] = []
        for item in data.get("results", []):
            articles.append(NewsArticle(
                article_id=item.get("id", ""),
                title=item.get("title", ""),
                body=item.get("description", ""),
                source=item.get("publisher", {}).get("name", "polygon"),
                url=item.get("article_url", ""),
                published_at=datetime.fromisoformat(item["published_utc"].replace("Z", "+00:00"))
                    if "published_utc" in item else datetime.now(timezone.utc),
                symbols=[t.get("ticker", "") for t in item.get("tickers", [])],
            ))
        return articles

    @property
    def recent_articles(self) -> list[NewsArticle]:
        """Return articles fetched so far (most recent first)."""
        return list(reversed(self._articles))
