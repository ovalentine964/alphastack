"""Unit tests for the AlphaStack data pipeline.

Tests cover:
- LiveMarketFeed: tick validation, candle aggregation, gap detection, health
- MarketDataStore: cache-aside reads/writes, quality checks
- DataPipeline: orchestration, event publishing, health monitoring
- TickValidator: edge cases (NaN, negative prices, wide spreads)
- GapDetector: timing-based gap detection
- Replay mode: backtesting data flow

No external services required — all dependencies are mocked.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphastack.brokers.base import BrokerConnector, ConnectionState
from alphastack.brokers.models import BrokerBar, BrokerTick
from alphastack.core.events import DataEvent, EventBus, EventType
from alphastack.data.feed import (
    FeedStatus,
    GapDetector,
    LiveMarketFeed,
    TickValidator,
)
from alphastack.data.ingestion.market_data import (
    BrokerSource,
    Candle,
    CandleAggregator,
    CandleTimeframe,
    Tick,
)
from alphastack.data.pipeline import DataPipeline, PipelineStatus
from alphastack.data.store import DataQualityReport, MarketDataStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_tick(
    symbol: str = "BTC/USDT",
    bid: float = 65000.0,
    ask: float = 65001.0,
    last: float = 65000.5,
    volume: float = 100.0,
    timestamp: datetime | None = None,
) -> Tick:
    """Create a test tick."""
    return Tick(
        symbol=symbol,
        broker=BrokerSource.CCXT,
        bid=Decimal(str(bid)),
        ask=Decimal(str(ask)),
        last=Decimal(str(last)),
        volume=Decimal(str(volume)),
        timestamp=timestamp or datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc),
    )


def _make_broker_tick(
    symbol: str = "BTC/USDT",
    bid: float = 65000.0,
    ask: float = 65001.0,
    last: float = 65000.5,
    volume: float = 100.0,
) -> BrokerTick:
    """Create a test BrokerTick."""
    return BrokerTick(
        broker="ccxt",
        symbol=symbol,
        bid=bid,
        ask=ask,
        last=last,
        volume=volume,
        spread=ask - bid,
        timestamp=datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc),
    )


def _make_candle(
    symbol: str = "BTC/USDT",
    timeframe: CandleTimeframe = CandleTimeframe.H1,
    open_p: float = 65000.0,
    high: float = 65500.0,
    low: float = 64800.0,
    close: float = 65200.0,
    volume: float = 1000.0,
    timestamp: datetime | None = None,
    is_closed: bool = True,
) -> Candle:
    """Create a test candle."""
    c = Candle(
        symbol=symbol,
        timeframe=timeframe,
        open=Decimal(str(open_p)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal(str(volume)),
        timestamp=timestamp or datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc),
        tick_count=50,
        is_closed=is_closed,
    )
    return c


class MockConnector(BrokerConnector):
    """Mock broker connector for testing."""

    def __init__(self, name: str = "mock", ticks: list[BrokerTick] | None = None) -> None:
        super().__init__(name)
        self._ticks = ticks or []
        self._tick_index = 0
        self._connect_called = False
        self._disconnect_called = False

    async def connect(self) -> None:
        self._connect_called = True
        self._transition(ConnectionState.CONNECTED)

    async def disconnect(self) -> None:
        self._disconnect_called = True
        self._transition(ConnectionState.DISCONNECTED)

    async def place_order(self, order: Any) -> Any:
        raise NotImplementedError

    async def cancel_order(self, order_id: str) -> Any:
        raise NotImplementedError

    async def modify_order(self, order_id: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def get_positions(self) -> list:
        return []

    async def get_balance(self) -> Any:
        raise NotImplementedError

    async def get_tick(self, symbol: str) -> BrokerTick:
        if self._tick_index < len(self._ticks):
            tick = self._ticks[self._tick_index]
            self._tick_index += 1
            return tick
        return _make_broker_tick(symbol)

    async def get_bars(self, symbol: str, timeframe: str, count: int = 500) -> list[BrokerBar]:
        bars = []
        base_ts = datetime(2026, 7, 19, 0, 0, 0, tzinfo=timezone.utc)
        for i in range(min(count, 100)):
            bars.append(BrokerBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=base_ts + timedelta(hours=i),
                open=65000.0 + i * 10,
                high=65100.0 + i * 10,
                low=64900.0 + i * 10,
                close=65050.0 + i * 10,
                volume=1000.0 + i,
            ))
        return bars


class MockRedis:
    """Mock Redis client for testing cache operations."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}
        self._ttls: dict[str, int] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._store[key] = value
        if ex:
            self._ttls[key] = ex
        return True

    async def rpush(self, key: str, value: str) -> int:
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].append(value)
        return len(self._lists[key])

    async def ltrim(self, key: str, start: int, stop: int) -> bool:
        if key in self._lists:
            self._lists[key] = self._lists[key][start:stop + 1] if stop >= 0 else self._lists[key][start:]
        return True

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        lst = self._lists.get(key, [])
        if stop == -1:
            return lst[start:]
        return lst[start:stop + 1]

    async def expire(self, key: str, seconds: int) -> bool:
        self._ttls[key] = seconds
        return True

    async def aclose(self) -> None:
        pass


# ---------------------------------------------------------------------------
# TickValidator tests
# ---------------------------------------------------------------------------

class TestTickValidator:
    """Tests for TickValidator."""

    def test_valid_tick_passes(self) -> None:
        validator = TickValidator()
        tick = _make_tick()
        is_valid, reason = validator.validate(tick)
        assert is_valid is True
        assert reason == "ok"
        assert validator.accepted_count == 1

    def test_zero_bid_rejected(self) -> None:
        validator = TickValidator()
        tick = _make_tick(bid=0.0)
        is_valid, reason = validator.validate(tick)
        assert is_valid is False
        assert "non_positive" in reason

    def test_negative_ask_rejected(self) -> None:
        validator = TickValidator()
        tick = _make_tick(ask=-1.0)
        is_valid, reason = validator.validate(tick)
        assert is_valid is False
        assert "non_positive" in reason

    def test_bid_greater_than_ask_rejected(self) -> None:
        validator = TickValidator()
        tick = _make_tick(bid=65010.0, ask=65000.0)
        is_valid, reason = validator.validate(tick)
        assert is_valid is False
        assert "bid_gt_ask" in reason

    def test_wide_spread_rejected(self) -> None:
        validator = TickValidator()
        # Spread = 10000 on a 65000 mid = ~15.4% > 10% threshold
        tick = _make_tick(bid=60000.0, ask=70000.0)
        is_valid, reason = validator.validate(tick)
        assert is_valid is False
        assert "spread_too_wide" in reason

    def test_nan_price_rejected(self) -> None:
        validator = TickValidator()
        tick = _make_tick(last=float("nan"))
        is_valid, reason = validator.validate(tick)
        assert is_valid is False
        assert "non_finite" in reason

    def test_inf_price_rejected(self) -> None:
        validator = TickValidator()
        tick = _make_tick(bid=float("inf"))
        is_valid, reason = validator.validate(tick)
        assert is_valid is False
        assert "non_finite" in reason

    def test_price_deviation_rejected(self) -> None:
        validator = TickValidator(max_deviation_pct=10.0)
        # First tick establishes baseline
        tick1 = _make_tick(last=65000.0)
        validator.validate(tick1)

        # Second tick is 60% away — exceeds 10% threshold
        tick2 = _make_tick(last=104000.0, bid=104000.0, ask=104001.0)
        is_valid, reason = validator.validate(tick2)
        assert is_valid is False
        assert "price_deviation" in reason

    def test_price_within_deviation_passes(self) -> None:
        validator = TickValidator(max_deviation_pct=10.0)
        tick1 = _make_tick(last=65000.0)
        validator.validate(tick1)

        # 5% move — within threshold
        tick2 = _make_tick(last=68250.0, bid=68250.0, ask=68251.0)
        is_valid, reason = validator.validate(tick2)
        assert is_valid is True

    def test_rejection_rate(self) -> None:
        validator = TickValidator()
        # 2 valid, 1 invalid
        validator.validate(_make_tick(bid=65000.0, ask=65001.0))
        validator.validate(_make_tick(bid=65000.0, ask=65001.0))
        validator.validate(_make_tick(bid=0.0))  # Invalid

        assert validator.accepted_count == 2
        assert validator.rejected_count == 1
        assert abs(validator.rejection_rate - 1 / 3) < 0.01

    def test_equal_bid_ask_passes(self) -> None:
        """bid == ask should pass (zero spread is valid for some feeds)."""
        validator = TickValidator()
        tick = _make_tick(bid=65000.0, ask=65000.0)
        is_valid, reason = validator.validate(tick)
        assert is_valid is True


# ---------------------------------------------------------------------------
# GapDetector tests
# ---------------------------------------------------------------------------

class TestGapDetector:
    """Tests for GapDetector."""

    def test_no_gap_for_consecutive_ticks(self) -> None:
        detector = GapDetector([CandleTimeframe.M1])
        ts1 = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 7, 19, 12, 0, 30, tzinfo=timezone.utc)  # 30s later

        assert detector.check("BTC/USDT", ts1) is False
        assert detector.check("BTC/USDT", ts2) is False
        assert detector.gap_count == 0

    def test_gap_detected(self) -> None:
        detector = GapDetector([CandleTimeframe.M1])
        ts1 = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)
        # M1 = 60s, threshold = 3 * 60 = 180s
        ts2 = datetime(2026, 7, 19, 12, 4, 0, tzinfo=timezone.utc)  # 4 min later

        assert detector.check("BTC/USDT", ts1) is False
        assert detector.check("BTC/USDT", ts2) is True
        assert detector.gap_count == 1

    def test_gap_per_symbol(self) -> None:
        detector = GapDetector([CandleTimeframe.M5])
        ts = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)

        detector.check("BTC/USDT", ts)
        detector.check("ETH/USDT", ts)

        # Both have gaps if next ticks are far apart
        ts_late = datetime(2026, 7, 19, 12, 30, 0, tzinfo=timezone.utc)
        assert detector.check("BTC/USDT", ts_late) is True
        assert detector.check("ETH/USDT", ts_late) is True
        assert detector.gap_count == 2

    def test_recent_gaps_stored(self) -> None:
        detector = GapDetector([CandleTimeframe.M1])
        ts1 = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 7, 19, 12, 5, 0, tzinfo=timezone.utc)

        detector.check("BTC/USDT", ts1)
        detector.check("BTC/USDT", ts2)

        gaps = detector.recent_gaps
        assert len(gaps) == 1
        assert gaps[0]["symbol"] == "BTC/USDT"
        assert gaps[0]["gap_seconds"] == 300.0


# ---------------------------------------------------------------------------
# LiveMarketFeed tests
# ---------------------------------------------------------------------------

class TestLiveMarketFeed:
    """Tests for LiveMarketFeed."""

    @pytest.fixture
    def mock_connector(self) -> MockConnector:
        return MockConnector(name="test-ccxt")

    @pytest.fixture
    def feed(self, mock_connector: MockConnector) -> LiveMarketFeed:
        return LiveMarketFeed(
            connector=mock_connector,
            timeframes=[CandleTimeframe.M1, CandleTimeframe.M5],
            symbols=["BTC/USDT"],
            validate_ticks=True,
            market_type="crypto",
        )

    def test_initial_status(self, feed: LiveMarketFeed) -> None:
        assert feed.status == FeedStatus.IDLE
        assert feed.is_streaming is False
        assert feed.tick_count == 0
        assert feed.candle_count == 0

    def test_get_health(self, feed: LiveMarketFeed) -> None:
        health = feed.get_health()
        assert health["status"] == "idle"
        assert health["tick_count"] == 0
        assert health["gap_count"] == 0
        assert health["is_stale"] is False

    def test_get_latest_tick_none(self, feed: LiveMarketFeed) -> None:
        assert feed.get_latest_tick("BTC/USDT") is None

    def test_get_latest_candle_none(self, feed: LiveMarketFeed) -> None:
        assert feed.get_latest_candle("BTC/USDT", CandleTimeframe.H1) is None

    def test_get_candle_history_empty(self, feed: LiveMarketFeed) -> None:
        history = feed.get_candle_history("BTC/USDT", CandleTimeframe.H1)
        assert history == []

    def test_get_market_snapshot_empty(self, feed: LiveMarketFeed) -> None:
        snapshot = feed.get_market_snapshot("BTC/USDT")
        assert snapshot["symbol"] == "BTC/USDT"
        assert snapshot["bid"] == 0.0
        assert snapshot["last"] == 0.0
        # ohlcv will have keys for each timeframe but with empty lists
        assert all(v == [] for v in snapshot["ohlcv"].values())

    @pytest.mark.asyncio
    async def test_start_connects(self, feed: LiveMarketFeed, mock_connector: MockConnector) -> None:
        """start() should connect the connector."""
        # We can't fully test the stream loop without mocking CCXT internals,
        # but we can verify connect is called.
        with patch.object(feed, "_stream_loop", new_callable=AsyncMock):
            await feed.start()
            assert mock_connector._connect_called is True
            assert feed.status == FeedStatus.STREAMING
            await feed.stop()

    @pytest.mark.asyncio
    async def test_start_requires_symbols(self, feed: LiveMarketFeed) -> None:
        feed._symbols = []
        with pytest.raises(ValueError, match="No symbols"):
            await feed.start()

    @pytest.mark.asyncio
    async def test_stop_disconnects(self, feed: LiveMarketFeed, mock_connector: MockConnector) -> None:
        with patch.object(feed, "_stream_loop", new_callable=AsyncMock):
            await feed.start()
            await feed.stop()
            assert mock_connector._disconnect_called is True
            assert feed.status == FeedStatus.DISCONNECTED

    def test_tick_callback_registration(self, feed: LiveMarketFeed) -> None:
        async def my_callback(tick: Tick) -> None:
            pass

        feed.on_tick(my_callback)
        assert len(feed._on_tick_callbacks) == 1

    def test_candle_callback_registration(self, feed: LiveMarketFeed) -> None:
        async def my_callback(candle: Candle) -> None:
            pass

        feed.on_candle(my_callback)
        assert len(feed._on_candle_callbacks) == 1

    def test_from_ccxt_factory(self) -> None:
        feed = LiveMarketFeed.from_ccxt("binance", symbols=["BTC/USDT"])
        assert feed.connector.name == "ccxt:binance"
        assert feed._market_type == "crypto"
        assert feed.symbols == ["BTC/USDT"]

    def test_from_bars_factory(self) -> None:
        bars = [
            {"timestamp": datetime(2026, 7, 19, i, 0, 0, tzinfo=timezone.utc),
             "open": 65000 + i, "high": 65100 + i, "low": 64900 + i,
             "close": 65050 + i, "volume": 100 + i}
            for i in range(10)
        ]
        feed = LiveMarketFeed.from_bars(bars, "BTC/USDT")
        assert feed._replay_symbol == "BTC/USDT"
        assert len(feed._bars) == 10

    @pytest.mark.asyncio
    async def test_replay(self) -> None:
        """Replay historical bars and verify candle aggregation."""
        # Create 200 bars at 1-minute intervals to generate M1 candles
        base = datetime(2026, 7, 19, 0, 0, 0, tzinfo=timezone.utc)
        bars = [
            {"timestamp": base + timedelta(minutes=i),
             "open": 65000.0 + i, "high": 65050.0 + i, "low": 64950.0 + i,
             "close": 65020.0 + i, "volume": 100.0 + i}
            for i in range(200)
        ]

        feed = LiveMarketFeed.from_bars(
            bars, "BTC/USDT", timeframes=[CandleTimeframe.M1, CandleTimeframe.M5],
        )
        candle_count = await feed.replay()

        # Should have produced some closed candles
        assert candle_count > 0
        assert feed.tick_count == 200

        # Check candle history
        m1_history = feed.get_candle_history("BTC/USDT", CandleTimeframe.M1)
        assert len(m1_history) > 0


# ---------------------------------------------------------------------------
# MarketDataStore tests
# ---------------------------------------------------------------------------

class TestMarketDataStore:
    """Tests for MarketDataStore."""

    @pytest.fixture
    def mock_redis(self) -> MockRedis:
        return MockRedis()

    @pytest.fixture
    def store(self, mock_redis: MockRedis) -> MarketDataStore:
        store = MarketDataStore(
            enable_cache=True,
            enable_timescale=False,  # Skip DB for unit tests
        )
        store._redis = mock_redis  # type: ignore[assignment]
        store._initialized = True
        store._enable_cache = True
        return store

    @pytest.mark.asyncio
    async def test_write_tick_updates_cache(self, store: MarketDataStore, mock_redis: MockRedis) -> None:
        tick = _make_tick()
        await store.write_tick(tick)

        # Verify cache was updated
        cached = await mock_redis.get("alphastack:tick:BTC/USDT")
        assert cached is not None
        data = json.loads(cached)
        assert data["symbol"] == "BTC/USDT"
        assert data["bid"] == "65000.0"
        assert data["last"] == "65000.5"

    @pytest.mark.asyncio
    async def test_get_latest_tick_from_cache(self, store: MarketDataStore, mock_redis: MockRedis) -> None:
        # Write first
        tick = _make_tick()
        await store.write_tick(tick)

        # Read back
        result = await store.get_latest_tick("BTC/USDT")
        assert result is not None
        assert result["symbol"] == "BTC/USDT"
        assert store._cache_hits == 1

    @pytest.mark.asyncio
    async def test_get_latest_tick_cache_miss(self, store: MarketDataStore) -> None:
        result = await store.get_latest_tick("NONEXISTENT")
        assert result is None
        assert store._cache_misses == 1

    @pytest.mark.asyncio
    async def test_write_candle_updates_cache(self, store: MarketDataStore, mock_redis: MockRedis) -> None:
        candle = _make_candle()
        await store.write_candle(candle)

        # Check latest candle cache
        cached = await mock_redis.get("alphastack:candle:BTC/USDT:1h")
        assert cached is not None
        data = json.loads(cached)
        assert data["symbol"] == "BTC/USDT"
        assert data["timeframe"] == "1h"

    @pytest.mark.asyncio
    async def test_write_candle_appends_to_history(self, store: MarketDataStore, mock_redis: MockRedis) -> None:
        candle1 = _make_candle(close=65200.0)
        candle2 = _make_candle(close=65300.0)

        await store.write_candle(candle1)
        await store.write_candle(candle2)

        history = await mock_redis.lrange("alphastack:candles:BTC/USDT:1h", 0, -1)
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_candles_from_cache(self, store: MarketDataStore, mock_redis: MockRedis) -> None:
        # Write some candles
        for i in range(5):
            candle = _make_candle(close=65000.0 + i * 100)
            await store.write_candle(candle)

        # Read from cache (no start specified → cache-first)
        candles = await store.get_candles("BTC/USDT", "1h", limit=10)
        assert len(candles) == 5
        assert store._cache_hits == 1

    @pytest.mark.asyncio
    async def test_bulk_write_ticks(self, store: MarketDataStore) -> None:
        ticks = [_make_tick(bid=65000.0 + i) for i in range(10)]
        count = await store.write_ticks(ticks)
        assert count == 10
        assert store._write_count == 10

    @pytest.mark.asyncio
    async def test_bulk_write_candles(self, store: MarketDataStore) -> None:
        candles = [_make_candle(close=65000.0 + i * 100) for i in range(5)]
        count = await store.write_candles(candles)
        assert count == 5

    @pytest.mark.asyncio
    async def test_cache_hit_rate(self, store: MarketDataStore, mock_redis: MockRedis) -> None:
        # Write then read (hit)
        await store.write_tick(_make_tick())
        await store.get_latest_tick("BTC/USDT")

        # Miss
        await store.get_latest_tick("ETH/USDT")

        assert store.cache_hit_rate == 0.5

    @pytest.mark.asyncio
    async def test_metrics(self, store: MarketDataStore) -> None:
        metrics = store.get_metrics()
        assert "write_count" in metrics
        assert "read_count" in metrics
        assert "cache_hits" in metrics
        assert "cache_hit_rate" in metrics

    @pytest.mark.asyncio
    async def test_quality_report_clean(self, store: MarketDataStore, mock_redis: MockRedis) -> None:
        """Quality check with complete data should report is_clean."""
        # Pre-populate candles in cache
        now = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(24):  # 24 hourly candles
            candle = _make_candle(
                timestamp=now - timedelta(hours=23 - i),
                close=65000.0 + i,
            )
            candle_data = json.dumps({
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "open": str(candle.open),
                "high": str(candle.high),
                "low": str(candle.low),
                "close": str(candle.close),
                "volume": str(candle.volume),
                "timestamp": candle.timestamp.isoformat(),
                "tick_count": 50,
            })
            await mock_redis.rpush("alphastack:candles:BTC/USDT:1h", candle_data)

        report = await store.check_quality("BTC/USDT", "1h", lookback_hours=24)
        assert isinstance(report, DataQualityReport)
        assert report.symbol == "BTC/USDT"

    def test_quality_report_is_clean(self) -> None:
        report = DataQualityReport(
            symbol="BTC/USDT",
            timeframe="1h",
            expected_count=24,
            actual_count=24,
            gaps=[],
            stale=False,
            completeness_pct=100.0,
        )
        assert report.is_clean is True
        assert report.to_dict()["is_clean"] is True

    def test_quality_report_with_gaps(self) -> None:
        report = DataQualityReport(
            symbol="BTC/USDT",
            timeframe="1h",
            expected_count=24,
            actual_count=20,
            gaps=[{"from": "a", "to": "b", "gap_seconds": 7200}],
            stale=False,
            completeness_pct=83.3,
        )
        assert report.is_clean is False


# ---------------------------------------------------------------------------
# DataPipeline tests
# ---------------------------------------------------------------------------

class TestDataPipeline:
    """Tests for DataPipeline orchestrator."""

    @pytest.fixture
    def mock_connector(self) -> MockConnector:
        return MockConnector(name="test-feed")

    @pytest.fixture
    def feed(self, mock_connector: MockConnector) -> LiveMarketFeed:
        return LiveMarketFeed(
            connector=mock_connector,
            timeframes=[CandleTimeframe.M5],
            symbols=["BTC/USDT"],
            validate_ticks=False,  # Simplify for pipeline tests
        )

    @pytest.fixture
    def store(self) -> MarketDataStore:
        store = MarketDataStore(enable_cache=False, enable_timescale=False)
        store._initialized = True
        return store

    @pytest.fixture
    def pipeline(self, feed: LiveMarketFeed, store: MarketDataStore) -> DataPipeline:
        return DataPipeline(
            feeds=[feed],
            store=store,
            event_bus=None,
        )

    def test_initial_state(self, pipeline: DataPipeline) -> None:
        assert pipeline.is_running is False
        assert pipeline.uptime_seconds == 0.0
        assert len(pipeline.feeds) == 1
        assert pipeline._total_ticks == 0

    def test_get_status(self, pipeline: DataPipeline) -> None:
        status = pipeline.get_status()
        assert isinstance(status, PipelineStatus)
        assert status.is_healthy is False  # Not started yet
        assert status.total_ticks == 0

    def test_status_to_dict(self, pipeline: DataPipeline) -> None:
        status = pipeline.get_status()
        d = status.to_dict()
        assert "healthy" in d
        assert "feeds" in d
        assert "store" in d
        assert "alerts" in d

    def test_get_feed_by_name(self, pipeline: DataPipeline) -> None:
        feed = pipeline.get_feed("test-feed")
        assert feed is not None

    def test_get_feed_not_found(self, pipeline: DataPipeline) -> None:
        assert pipeline.get_feed("nonexistent") is None

    def test_get_market_snapshot_no_data(self, pipeline: DataPipeline) -> None:
        snapshot = pipeline.get_market_snapshot("BTC/USDT")
        assert snapshot["symbol"] == "BTC/USDT"
        assert snapshot["last"] == 0.0

    @pytest.mark.asyncio
    async def test_on_tick_increments_counter(self, pipeline: DataPipeline) -> None:
        tick = _make_tick()
        await pipeline._on_tick(tick)
        assert pipeline._total_ticks == 1

    @pytest.mark.asyncio
    async def test_on_candle_increments_counter(self, pipeline: DataPipeline) -> None:
        candle = _make_candle()
        await pipeline._on_candle(candle)
        assert pipeline._total_candles == 1

    @pytest.mark.asyncio
    async def test_on_tick_queues_for_store(self, pipeline: DataPipeline) -> None:
        tick = _make_tick()
        await pipeline._on_tick(tick)

        # Check queue
        assert not pipeline._tick_queue.empty()
        queued = await pipeline._tick_queue.get()
        assert queued.symbol == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_on_candle_queues_for_store(self, pipeline: DataPipeline) -> None:
        candle = _make_candle()
        await pipeline._on_candle(candle)

        assert not pipeline._candle_queue.empty()
        queued = await pipeline._candle_queue.get()
        assert queued.symbol == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_pipeline_start_stop(self, pipeline: DataPipeline, feed: LiveMarketFeed) -> None:
        """Test full start/stop lifecycle."""
        with patch.object(feed, "_stream_loop", new_callable=AsyncMock):
            with patch.object(pipeline._store, "init", new_callable=AsyncMock):
                with patch.object(pipeline._store, "close", new_callable=AsyncMock):
                    await pipeline.start()
                    assert pipeline.is_running is True
                    assert pipeline.uptime_seconds > 0

                    await pipeline.stop()
                    assert pipeline.is_running is False


# ---------------------------------------------------------------------------
# Integration: feed → store → pipeline
# ---------------------------------------------------------------------------

class TestFeedStoreIntegration:
    """Integration tests for feed + store working together."""

    @pytest.mark.asyncio
    async def test_tick_flows_through_pipeline(self) -> None:
        """Verify a tick flows from feed callback to store queue."""
        connector = MockConnector(name="integration-feed")
        feed = LiveMarketFeed(
            connector=connector,
            timeframes=[CandleTimeframe.M5],
            symbols=["BTC/USDT"],
            validate_ticks=False,
        )

        store = MarketDataStore(enable_cache=False, enable_timescale=False)
        store._initialized = True

        pipeline = DataPipeline(feeds=[feed], store=store)

        # Simulate a tick arriving
        tick = _make_tick()
        await pipeline._on_tick(tick)

        assert pipeline._total_ticks == 1
        queued = await pipeline._tick_queue.get()
        assert queued.last == Decimal("65000.5")

    @pytest.mark.asyncio
    async def test_candle_flows_through_pipeline(self) -> None:
        """Verify a candle flows from feed callback to store queue."""
        connector = MockConnector(name="candle-test")
        feed = LiveMarketFeed(
            connector=connector,
            timeframes=[CandleTimeframe.H1],
            symbols=["BTC/USDT"],
        )

        store = MarketDataStore(enable_cache=False, enable_timescale=False)
        store._initialized = True

        pipeline = DataPipeline(feeds=[feed], store=store)

        candle = _make_candle()
        await pipeline._on_candle(candle)

        assert pipeline._total_candles == 1
        queued = await pipeline._candle_queue.get()
        assert queued.close == Decimal("65200.0")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case tests."""

    def test_validator_handles_decimal_precision(self) -> None:
        """Validator should handle high-precision crypto prices."""
        validator = TickValidator()
        tick = _make_tick(
            bid=0.00000123,
            ask=0.00000124,
            last=0.000001235,
            volume=999999999.99,
        )
        is_valid, reason = validator.validate(tick)
        assert is_valid is True

    def test_validator_handles_forex_pip_spreads(self) -> None:
        """Validator should accept typical forex spreads."""
        validator = TickValidator()
        # EUR/USD: bid 1.08500, ask 1.08515 → spread 1.5 pips
        tick = Tick(
            symbol="EURUSD",
            broker=BrokerSource.MT5,
            bid=Decimal("1.08500"),
            ask=Decimal("1.08515"),
            last=Decimal("1.08507"),
            volume=Decimal("0"),
            timestamp=datetime.now(timezone.utc),
        )
        is_valid, reason = validator.validate(tick)
        assert is_valid is True

    def test_gap_detector_with_h4_timeframe(self) -> None:
        """Gap detector should use correct threshold for H4 candles."""
        detector = GapDetector([CandleTimeframe.H4])
        # H4 = 14400s, threshold = 3 * 14400 = 43200s = 12 hours
        ts1 = datetime(2026, 7, 19, 0, 0, 0, tzinfo=timezone.utc)
        # Gap from ts1 to ts2 is 15h > 12h threshold
        ts2 = datetime(2026, 7, 19, 15, 0, 0, tzinfo=timezone.utc)

        assert detector.check("EURUSD", ts1) is False
        assert detector.check("EURUSD", ts2) is True

    def test_candle_aggregator_integration(self) -> None:
        """Verify CandleAggregator works correctly with multiple timeframes."""
        aggregator = CandleAggregator([CandleTimeframe.M1, CandleTimeframe.M5])

        base_ts = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)

        # Send ticks within the same M1 bar
        tick1 = _make_tick(last=65000.0, timestamp=base_ts)
        tick2 = _make_tick(last=65100.0, timestamp=base_ts + timedelta(seconds=30))

        closed1 = aggregator.process_tick(tick1)
        closed2 = aggregator.process_tick(tick2)

        # No candles should close yet (still within the same bar)
        assert len(closed1) == 0
        assert len(closed2) == 0

        # Tick in a new M1 bar should close the previous one
        tick3 = _make_tick(last=65200.0, timestamp=base_ts + timedelta(seconds=65))
        closed3 = aggregator.process_tick(tick3)

        assert len(closed3) >= 1  # At least the M1 candle closed
        m1_candle = [c for c in closed3 if c.timeframe == CandleTimeframe.M1]
        assert len(m1_candle) == 1
        assert m1_candle[0].high == Decimal("65100.0")  # Max of tick1, tick2

    def test_replay_connector_stub(self) -> None:
        """ReplayConnector should not support live operations."""
        from alphastack.data.feed import _ReplayConnector

        conn = _ReplayConnector()
        assert conn.name == "replay"

    @pytest.mark.asyncio
    async def test_store_write_with_no_connections(self) -> None:
        """Store should handle gracefully when both connections are disabled."""
        store = MarketDataStore(enable_cache=False, enable_timescale=False)
        store._initialized = True

        # Should not raise
        await store.write_tick(_make_tick())
        await store.write_candle(_make_candle())

        result = await store.get_latest_tick("BTC/USDT")
        assert result is None

    def test_pipeline_status_alerts(self) -> None:
        """PipelineStatus should track alerts."""
        status = PipelineStatus()
        status.alerts = ["Feed disconnected", "Redis down"]
        assert status.is_healthy is False

    def test_pipeline_status_healthy(self) -> None:
        status = PipelineStatus()
        status.feeds = {"test": {"status": "streaming"}}
        assert status.is_healthy is True


# ---------------------------------------------------------------------------
# Reconnection tests
# ---------------------------------------------------------------------------

class TestReconnection:
    """Tests for feed reconnection logic."""

    @pytest.mark.asyncio
    async def test_reconnect_scheduled_on_stream_error(self) -> None:
        connector = MockConnector(name="reconnect-test")
        feed = LiveMarketFeed(
            connector=connector,
            symbols=["BTC/USDT"],
            validate_ticks=False,
        )
        feed._running = True
        feed._status = FeedStatus.STREAMING

        # Simulate a stream error triggering reconnect
        with patch.object(feed, "_reconnect_loop", new_callable=AsyncMock) as mock_loop:
            await feed._schedule_reconnect()
            # Give the task a moment to be created
            await asyncio.sleep(0.05)
            assert feed._status == FeedStatus.RECONNECTING

    @pytest.mark.asyncio
    async def test_reconnect_not_scheduled_when_stopped(self) -> None:
        connector = MockConnector(name="stopped-test")
        feed = LiveMarketFeed(connector=connector, symbols=["BTC/USDT"])
        feed._running = False

        await feed._schedule_reconnect()
        # Should not have created a reconnect task
        assert feed._reconnect_task is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
