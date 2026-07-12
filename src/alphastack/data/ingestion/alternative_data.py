"""Alternative Data – on-chain, social sentiment, Google Trends."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

import httpx

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class DataSource(str, Enum):
    ONCHAIN = "onchain"
    TWITTER = "twitter"
    REDDIT = "reddit"
    GOOGLE_TRENDS = "google_trends"


@dataclass(frozen=True, slots=True)
class WhaleMovement:
    """Large on-chain transfer detected."""

    chain: str  # ethereum, bitcoin, solana …
    token: str
    amount: Decimal
    usd_value: Decimal
    from_address: str
    to_address: str
    tx_hash: str
    timestamp: datetime
    label: str = ""  # exchange, whale, contract …

    @property
    def is_exchange_deposit(self) -> bool:
        return "exchange" in self.label.lower()


@dataclass(frozen=True, slots=True)
class FundingRate:
    """Perpetual futures funding rate."""

    exchange: str
    symbol: str
    rate: Decimal  # e.g. 0.0001 = 0.01%
    next_funding_time: datetime
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class SocialSentiment:
    """Aggregated social sentiment for a symbol."""

    source: DataSource
    symbol: str
    mention_count: int
    positive_ratio: float  # 0.0 – 1.0
    negative_ratio: float
    neutral_ratio: float
    trending_score: float  # normalised 0-100
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class GoogleTrendPoint:
    """A single Google Trends data point."""

    keyword: str
    interest: int  # 0-100 relative interest
    timestamp: datetime
    geo: str = "worldwide"


# ---------------------------------------------------------------------------
# On-chain data provider
# ---------------------------------------------------------------------------

class OnChainProvider:
    """Fetches whale movements and funding rates from public APIs."""

    def __init__(self, http_timeout: float = 15.0) -> None:
        self._timeout = http_timeout

    async def get_funding_rates(self, exchange: str = "binance") -> list[FundingRate]:
        """Fetch current funding rates from a CCXT-compatible exchange."""
        url_map = {
            "binance": "https://fapi.binance.com/fapi/v1/premiumIndex",
            "bybit": "https://api.bybit.com/v5/market/tickers?category=linear",
        }
        url = url_map.get(exchange)
        if not url:
            logger.warning("unsupported_exchange_funding", exchange=exchange)
            return []

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.warning("funding_rate_fetch_failed", exchange=exchange)
            return []

        rates: list[FundingRate] = []
        now = datetime.now(timezone.utc)

        if exchange == "binance":
            for item in data:
                rates.append(FundingRate(
                    exchange=exchange,
                    symbol=item.get("symbol", ""),
                    rate=Decimal(str(item.get("lastFundingRate", 0))),
                    next_funding_time=datetime.fromtimestamp(
                        item.get("nextFundingTime", 0) / 1000, tz=timezone.utc
                    ),
                    timestamp=now,
                ))
        elif exchange == "bybit":
            for item in data.get("result", {}).get("list", []):
                rates.append(FundingRate(
                    exchange=exchange,
                    symbol=item.get("symbol", ""),
                    rate=Decimal(str(item.get("fundingRate", 0))),
                    next_funding_time=now,  # simplified
                    timestamp=now,
                ))
        return rates

    async def get_whale_alerts(self, min_usd: float = 1_000_000) -> list[WhaleMovement]:
        """Fetch whale movements (placeholder – wire Whale Alert API)."""
        # Placeholder: integrate whale-alert.io or on-chain indexer
        logger.debug("whale_alert_stub", min_usd=min_usd)
        return []


# ---------------------------------------------------------------------------
# Social sentiment provider
# ---------------------------------------------------------------------------

class SocialSentimentProvider:
    """Fetches social media sentiment from Twitter/Reddit."""

    def __init__(self, http_timeout: float = 15.0) -> None:
        self._timeout = http_timeout

    async def get_twitter_sentiment(self, symbol: str) -> SocialSentiment | None:
        """Fetch Twitter/X sentiment for *symbol*.

        Placeholder – integrate Twitter API v2 or sentiment aggregator.
        """
        logger.debug("twitter_sentiment_stub", symbol=symbol)
        return None

    async def get_reddit_sentiment(self, subreddit: str = "wallstreetbets") -> list[SocialSentiment]:
        """Fetch Reddit sentiment from a subreddit.

        Placeholder – integrate Reddit API.
        """
        logger.debug("reddit_sentiment_stub", subreddit=subreddit)
        return []


# ---------------------------------------------------------------------------
# Google Trends provider
# ---------------------------------------------------------------------------

class GoogleTrendsProvider:
    """Fetches Google Trends data for financial keywords."""

    TIER1_KEYWORDS = [
        "bitcoin", "ethereum", "crypto", "forex",
        "stock market", "S&P 500", "gold price",
    ]

    def __init__(self, http_timeout: float = 15.0) -> None:
        self._timeout = http_timeout

    async def get_interest(
        self,
        keywords: list[str] | None = None,
        geo: str = "worldwide",
    ) -> list[GoogleTrendPoint]:
        """Fetch relative interest for keywords.

        Uses pytrends-compatible API or scraper.
        """
        kw = keywords or self.TIER1_KEYWORDS
        # Placeholder – integrate pytrends or serpapi
        logger.debug("google_trends_stub", keywords=kw, geo=geo)
        return []


# ---------------------------------------------------------------------------
# Alternative data aggregator
# ---------------------------------------------------------------------------

class AlternativeDataPipeline:
    """Orchestrates all alternative data sources."""

    def __init__(
        self,
        onchain: OnChainProvider | None = None,
        social: SocialSentimentProvider | None = None,
        trends: GoogleTrendsProvider | None = None,
        poll_interval: float = 300.0,
    ) -> None:
        self.onchain = onchain or OnChainProvider()
        self.social = social or SocialSentimentProvider()
        self.trends = trends or GoogleTrendsProvider()
        self.poll_interval = poll_interval

    async def fetch_all(self, symbols: list[str]) -> dict[str, Any]:
        """Fetch all alternative data sources in parallel."""
        results: dict[str, Any] = {}
        try:
            funding, twitter, trends_data = await asyncio.gather(
                self.onchain.get_funding_rates(),
                asyncio.gather(*[self.social.get_twitter_sentiment(s) for s in symbols]),
                self.trends.get_interest(),
                return_exceptions=True,
            )
            results["funding_rates"] = funding if not isinstance(funding, Exception) else []
            results["twitter_sentiment"] = [
                s for s in (twitter if not isinstance(twitter, Exception) else [])
                if s is not None
            ]
            results["google_trends"] = trends_data if not isinstance(trends_data, Exception) else []
        except Exception:
            logger.exception("alt_data_fetch_error")
        return results
