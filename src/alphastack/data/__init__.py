"""Data pipeline – live feeds, storage, and orchestration.

This module provides the core data infrastructure for AlphaStack:

- :class:`LiveMarketFeed` – real-time tick streaming with candle aggregation
- :class:`MarketDataStore` – TimescaleDB + Redis hot-cache storage
- :class:`DataPipeline` – orchestrator coordinating feeds, storage, and event bus

Usage::

    from alphastack.data import LiveMarketFeed, MarketDataStore, DataPipeline

    feed = LiveMarketFeed.from_ccxt("binance", symbols=["BTC/USDT"])
    store = MarketDataStore()
    pipeline = DataPipeline(feed=feed, store=store)
    await pipeline.start()
"""

from __future__ import annotations

from alphastack.data.feed import LiveMarketFeed
from alphastack.data.store import MarketDataStore
from alphastack.data.pipeline import DataPipeline

__all__ = [
    "LiveMarketFeed",
    "MarketDataStore",
    "DataPipeline",
]
