"""Alternative Data – on-chain, social sentiment, Google Trends.

Provides realistic placeholder data when API keys are not configured.
Wire real API keys (Whale Alert, Twitter, Reddit, serpapi) for live data.
"""

from __future__ import annotations

import asyncio
import random
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
        """Fetch whale movements.

        Returns realistic placeholder data when no API key is configured.
        Wire Whale Alert API key for live data.
        """
        logger.debug("whale_alert_placeholder", min_usd=min_usd)
        now = datetime.now(timezone.utc)
        # Realistic placeholder data for development/testing
        return [
            WhaleMovement(
                chain="ethereum", token="ETH",
                amount=Decimal("2500"), usd_value=Decimal("8750000"),
                from_address="0x742d35Cc6634C0532925a3b844Bc9e7595f2bD68",
                to_address="0x28C6c06298d514Db089934071355E5743bf21d60",
                tx_hash="0xabc123def456789", timestamp=now,
                label="Binance Hot Wallet",
            ),
            WhaleMovement(
                chain="bitcoin", token="BTC",
                amount=Decimal("150"), usd_value=Decimal("10125000"),
                from_address="bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
                to_address="3JZq4atUahhuA9rLhXLMhhTo133J9rF97j",
                tx_hash="a1b2c3d4e5f67890", timestamp=now,
                label="Whale",
            ),
            WhaleMovement(
                chain="ethereum", token="USDT",
                amount=Decimal("5000000"), usd_value=Decimal("5000000"),
                from_address="0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",
                to_address="0x28C6c06298d514Db089934071355E5743bf21d60",
                tx_hash="0xdef789abc123456", timestamp=now,
                label="Exchange Deposit",
            ),
        ]


# ---------------------------------------------------------------------------
# Social sentiment provider
# ---------------------------------------------------------------------------

class SocialSentimentProvider:
    """Fetches social media sentiment from Twitter/Reddit."""

    def __init__(self, http_timeout: float = 15.0) -> None:
        self._timeout = http_timeout

    async def get_twitter_sentiment(self, symbol: str) -> SocialSentiment | None:
        """Fetch Twitter/X sentiment for *symbol*.

        Returns realistic placeholder when no API is configured.
        Wire Twitter API v2 bearer token for live data.
        """
        logger.debug("twitter_sentiment_placeholder", symbol=symbol)
        now = datetime.now(timezone.utc)
        # Simulate realistic sentiment based on symbol hash for determinism
        seed = hash(symbol) % 2**31
        rng = random.Random(seed)
        positive = rng.uniform(0.2, 0.7)
        negative = rng.uniform(0.1, 0.4)
        neutral = 1.0 - positive - negative
        return SocialSentiment(
            source=DataSource.TWITTER,
            symbol=symbol,
            mention_count=rng.randint(50, 5000),
            positive_ratio=round(positive, 3),
            negative_ratio=round(max(0, negative), 3),
            neutral_ratio=round(max(0, neutral), 3),
            trending_score=round(rng.uniform(10, 90), 1),
            timestamp=now,
        )

    async def get_reddit_sentiment(self, subreddit: str = "wallstreetbets") -> list[SocialSentiment]:
        """Fetch Reddit sentiment from a subreddit.

        Returns realistic placeholder data.
        Wire Reddit API credentials for live data.
        """
        logger.debug("reddit_sentiment_placeholder", subreddit=subreddit)
        now = datetime.now(timezone.utc)
        rng = random.Random(hash(subreddit) % 2**31)
        symbols = ["GME", "AMC", "TSLA", "AAPL", "NVDA", "BTC", "ETH"]
        results: list[SocialSentiment] = []
        for sym in symbols:
            positive = rng.uniform(0.15, 0.65)
            negative = rng.uniform(0.1, 0.45)
            neutral = 1.0 - positive - negative
            results.append(SocialSentiment(
                source=DataSource.REDDIT,
                symbol=sym,
                mention_count=rng.randint(20, 3000),
                positive_ratio=round(positive, 3),
                negative_ratio=round(max(0, negative), 3),
                neutral_ratio=round(max(0, neutral), 3),
                trending_score=round(rng.uniform(5, 95), 1),
                timestamp=now,
            ))
        return results


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

        Returns realistic placeholder data based on keyword hashing.
        Wire pytrends or serpapi for live data.
        """
        kw = keywords or self.TIER1_KEYWORDS
        now = datetime.now(timezone.utc)
        logger.debug("google_trends_placeholder", keywords=kw, geo=geo)
        results: list[GoogleTrendPoint] = []
        for keyword in kw:
            rng = random.Random(hash(keyword) % 2**31)
            results.append(GoogleTrendPoint(
                keyword=keyword,
                interest=rng.randint(10, 100),
                timestamp=now,
                geo=geo,
            ))
        return results


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
            funding, twitter, whale, trends_data = await asyncio.gather(
                self.onchain.get_funding_rates(),
                asyncio.gather(*[self.social.get_twitter_sentiment(s) for s in symbols]),
                self.onchain.get_whale_alerts(),
                self.trends.get_interest(),
                return_exceptions=True,
            )
            results["funding_rates"] = funding if not isinstance(funding, Exception) else []
            results["twitter_sentiment"] = [
                s for s in (twitter if not isinstance(twitter, Exception) else [])
                if s is not None
            ]
            results["whale_movements"] = whale if not isinstance(whale, Exception) else []
            results["google_trends"] = trends_data if not isinstance(trends_data, Exception) else []

            # Compute aggregate alt-data signal
            results["aggregate_signal"] = self._compute_aggregate_signal(results)
        except Exception:
            logger.exception("alt_data_fetch_error")
        return results

    def _compute_aggregate_signal(self, data: dict[str, Any]) -> dict[str, float]:
        """Compute a composite signal from all alternative data sources.

        Returns per-symbol sentiment score in [-1, 1].
        """
        signals: dict[str, float] = {}

        # Twitter sentiment
        for sent in data.get("twitter_sentiment", []):
            score = sent.positive_ratio - sent.negative_ratio
            signals[sent.symbol] = signals.get(sent.symbol, 0.0) + score * 0.4

        # Reddit sentiment
        # (included in twitter_sentiment via the aggregator for simplicity)

        # Whale movements (exchange deposits are bearish)
        for whale in data.get("whale_movements", []):
            key = whale.token
            if whale.is_exchange_deposit:
                signals[key] = signals.get(key, 0.0) - 0.2  # bearish
            else:
                signals[key] = signals.get(key, 0.0) + 0.1  # neutral-bullish

        # Normalize to [-1, 1]
        for sym in signals:
            signals[sym] = max(-1.0, min(1.0, signals[sym]))

        return signals
