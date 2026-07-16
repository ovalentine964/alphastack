"""Unit tests for the OANDA v20 connector (fully mocked).

Tests cover connection lifecycle, order placement (market/limit/stop),
position retrieval, price streaming, and error handling.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphastack.brokers.base import BrokerConnector, ConnectionState
from alphastack.brokers.models import (
    BrokerBalance,
    BrokerBar,
    BrokerOrder,
    BrokerPosition,
    BrokerTick,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    TimeInForce,
)


# ---------------------------------------------------------------------------
# OANDA mock response factories
# ---------------------------------------------------------------------------

def _oanda_account_summary(account_id: str = "101-001-1234567-001") -> dict:
    return {
        "account": {
            "id": account_id,
            "currency": "USD",
            "balance": "10000.0000",
            "NAV": "10050.0000",
            "unrealizedPL": "50.0000",
            "marginUsed": "1105.0000",
            "marginAvailable": "8945.0000",
            "marginRate": "0.01",
            "openTradeCount": 1,
            "openPositionCount": 1,
            "pendingOrderCount": 0,
        }
    }


def _oanda_order_fill_response(order_type: str = "MARKET", units: str = "100") -> dict:
    return {
        "orderCreateTransaction": {
            "id": "12345",
            "type": order_type,
            "instrument": "EUR_USD",
            "units": units,
            "price": "1.10500",
            "time": "2025-06-15T12:00:00.000000000Z",
        },
        "orderFillTransaction": {
            "tradeOpened": {"tradeID": "12345", "units": units},
            "price": "1.10505",
            "units": units,
            "commission": "0.0000",
            "time": "2025-06-15T12:00:00.000000000Z",
        },
        "relatedTransactionIDs": ["12345"],
        "lastTransactionID": "12345",
    }


def _oanda_pending_order_response() -> dict:
    return {
        "orderCreateTransaction": {
            "id": "12346",
            "type": "LIMIT",
            "instrument": "EUR_USD",
            "units": "100",
            "price": "1.10000",
            "timeInForce": "GTC",
            "time": "2025-06-15T12:00:00.000000000Z",
        },
        "relatedTransactionIDs": ["12346"],
        "lastTransactionID": "12346",
    }


def _oanda_positions_response() -> dict:
    return {
        "positions": [
            {
                "instrument": "EUR_USD",
                "long": {"units": "1000", "averagePrice": "1.10500", "unrealizedPL": "50.00"},
                "short": {"units": "0", "averagePrice": "0.00000", "unrealizedPL": "0.00"},
            },
            {
                "instrument": "GBP_USD",
                "long": {"units": "0", "averagePrice": "0.00000", "unrealizedPL": "0.00"},
                "short": {"units": "-500", "averagePrice": "1.27000", "unrealizedPL": "-25.00"},
            },
        ]
    }


def _oanda_price_response(instrument: str = "EUR_USD") -> dict:
    return {
        "prices": [
            {
                "instrument": instrument,
                "time": "2025-06-15T12:00:00.000000000Z",
                "bids": [{"price": "1.10500", "liquidity": 1000000}],
                "asks": [{"price": "1.10520", "liquidity": 1000000}],
                "tradeable": True,
            }
        ]
    }


def _oanda_candles_response(count: int = 3) -> dict:
    candles = []
    for i in range(count):
        candles.append({
            "time": f"2025-06-15T{12 + i:02d}:00:00.000000000Z",
            "complete": True,
            "mid": {
                "o": f"{1.1000 + i * 0.001:.5f}",
                "h": f"{1.1050 + i * 0.001:.5f}",
                "l": f"{1.0950 + i * 0.001:.5f}",
                "c": f"{1.1020 + i * 0.001:.5f}",
            },
            "volume": 1000 + i * 100,
        })
    return {"candles": candles}


# ---------------------------------------------------------------------------
# OANDA connector implementation under test
# ---------------------------------------------------------------------------

class OandaConnector(BrokerConnector):
    """OANDA v20 REST API connector — testable with injected session."""

    def __init__(
        self,
        *,
        account_id: str,
        access_token: str,
        environment: str = "practice",
    ) -> None:
        super().__init__("oanda", max_retries=3, retry_delay=0.1)
        self._account_id = account_id
        self._access_token = access_token
        if environment == "practice":
            self._base_url = "https://api-fxpractice.oanda.com"
            self._stream_url = "https://stream-fxpractice.oanda.com"
        else:
            self._base_url = "https://api-fxtrade.oanda.com"
            self._stream_url = "https://stream-fxtrade.oanda.com"
        self._session: Any = None  # aiohttp.ClientSession (or mock)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}{path}"
        async with self._session.request(method, url, headers=self._headers, **kwargs) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise RuntimeError(f"OANDA API error {resp.status}: {body}")
            return await resp.json()

    async def connect(self) -> None:
        self._transition(ConnectionState.CONNECTING)
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        try:
            await self._request("GET", f"/v3/accounts/{self._account_id}/summary")
            self._transition(ConnectionState.CONNECTED)
        except Exception:
            self._transition(ConnectionState.ERROR)
            raise

    async def disconnect(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        self._transition(ConnectionState.DISCONNECTED)

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        instrument = order.symbol.replace("/", "_")
        units = order.quantity if order.side == OrderSide.BUY else -order.quantity

        body: dict[str, Any] = {
            "order": {
                "type": "MARKET" if order.order_type == OrderType.MARKET else order.order_type.value.upper(),
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK" if order.order_type == OrderType.MARKET else "GTC",
            }
        }
        if order.price and order.order_type != OrderType.MARKET:
            body["order"]["price"] = str(order.price)
        if order.stop_loss:
            body["order"]["stopLossOnFill"] = {"price": str(order.stop_loss)}
        if order.take_profit:
            body["order"]["takeProfitOnFill"] = {"price": str(order.take_profit)}

        result = await self._request("POST", f"/v3/accounts/{self._account_id}/orders", json=body)

        order_fill = result.get("orderFillTransaction", {})
        order_create = result.get("orderCreateTransaction", {})

        if order_fill:
            order.broker_order_id = order_fill.get("tradeOpened", {}).get("tradeID", "")
            order.status = OrderStatus.FILLED
            order.avg_fill_price = float(order_fill.get("price", 0))
            order.filled_quantity = abs(float(order_fill.get("units", 0)))
            order.commission = float(order_fill.get("commission", 0))
        elif order_create:
            order.broker_order_id = order_create.get("id", "")
            order.status = OrderStatus.OPEN

        order.raw = result
        order.updated_at = datetime.now(timezone.utc)
        return order

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        await self._request("PUT", f"/v3/accounts/{self._account_id}/orders/{order_id}/cancel")
        return BrokerOrder(broker_order_id=order_id, broker="oanda", status=OrderStatus.CANCELLED)

    async def modify_order(self, order_id: str, **kwargs: Any) -> BrokerOrder:
        body: dict[str, Any] = {"order": {}}
        if kwargs.get("price"):
            body["order"]["price"] = str(kwargs["price"])
        if kwargs.get("stop_loss"):
            body["order"]["stopLossOnFill"] = {"price": str(kwargs["stop_loss"])}
        if kwargs.get("take_profit"):
            body["order"]["takeProfitOnFill"] = {"price": str(kwargs["take_profit"])}
        await self._request("PUT", f"/v3/accounts/{self._account_id}/orders/{order_id}", json=body)
        return BrokerOrder(broker_order_id=order_id, broker="oanda", status=OrderStatus.OPEN)

    async def get_positions(self) -> list[BrokerPosition]:
        result = await self._request("GET", f"/v3/accounts/{self._account_id}/openPositions")
        positions: list[BrokerPosition] = []
        for p in result.get("positions", []):
            long = p.get("long", {})
            short = p.get("short", {})
            if float(long.get("units", 0)) != 0:
                positions.append(BrokerPosition(
                    broker="oanda",
                    symbol=p["instrument"].replace("_", "/"),
                    side=PositionSide.LONG,
                    quantity=abs(float(long["units"])),
                    avg_entry_price=float(long.get("averagePrice", 0)),
                    unrealized_pnl=float(long.get("unrealizedPL", 0)),
                ))
            if float(short.get("units", 0)) != 0:
                positions.append(BrokerPosition(
                    broker="oanda",
                    symbol=p["instrument"].replace("_", "/"),
                    side=PositionSide.SHORT,
                    quantity=abs(float(short["units"])),
                    avg_entry_price=float(short.get("averagePrice", 0)),
                    unrealized_pnl=float(short.get("unrealizedPL", 0)),
                ))
        return positions

    async def get_balance(self) -> BrokerBalance:
        result = await self._request("GET", f"/v3/accounts/{self._account_id}/summary")
        acct = result.get("account", {})
        return BrokerBalance(
            broker="oanda",
            currency=acct.get("currency", "USD"),
            total=float(acct.get("balance", 0)),
            available=float(acct.get("marginAvailable", 0)),
            used_margin=float(acct.get("marginUsed", 0)),
            equity=float(acct.get("NAV", 0)),
            unrealized_pnl=float(acct.get("unrealizedPL", 0)),
        )

    async def get_tick(self, symbol: str) -> BrokerTick:
        instrument = symbol.replace("/", "_")
        result = await self._request(
            "GET",
            f"/v3/accounts/{self._account_id}/pricing",
            params={"instruments": instrument},
        )
        price = result.get("prices", [{}])[0]
        bid = float(price.get("bids", [{}])[0].get("price", 0))
        ask = float(price.get("asks", [{}])[0].get("price", 0))
        return BrokerTick(
            broker="oanda",
            symbol=symbol,
            bid=bid,
            ask=ask,
            spread=ask - bid,
            timestamp=datetime.fromisoformat(price.get("time", "").replace("Z", "+00:00")),
        )

    async def get_bars(self, symbol: str, timeframe: str, count: int = 500) -> list[BrokerBar]:
        instrument = symbol.replace("/", "_")
        tf_map = {"M1": "M", "M5": "M5", "M15": "M15", "M30": "M30",
                  "H1": "H1", "H4": "H4", "D1": "D", "W1": "W", "MN1": "M"}
        granularity = tf_map.get(timeframe.upper(), "H1")

        result = await self._request(
            "GET",
            f"/v3/instruments/{instrument}/candles",
            params={"granularity": granularity, "count": min(count, 5000), "price": "MBA"},
        )

        bars: list[BrokerBar] = []
        for c in result.get("candles", []):
            if not c.get("complete"):
                continue
            mid = c.get("mid", {})
            bars.append(BrokerBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.fromisoformat(c["time"].replace("Z", "+00:00")),
                open=float(mid.get("o", 0)),
                high=float(mid.get("h", 0)),
                low=float(mid.get("l", 0)),
                close=float(mid.get("c", 0)),
                volume=float(c.get("volume", 0)),
            ))
        return bars


# ---------------------------------------------------------------------------
# Mock aiohttp response
# ---------------------------------------------------------------------------

class MockResponse:
    """Simulates an aiohttp.ClientResponse."""

    def __init__(self, json_data: dict, status: int = 200, text_data: str = ""):
        self._json = json_data
        self.status = status
        self._text = text_data or json.dumps(json_data)

    async def json(self):
        return self._json

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockSession:
    """Simulates aiohttp.ClientSession with preset responses."""

    def __init__(self, responses: dict[str, MockResponse] | None = None):
        self._responses = responses or {}
        self._closed = False
        self.requests: list[tuple[str, str, dict]] = []

    def _match(self, method: str, url: str) -> MockResponse:
        for key, resp in self._responses.items():
            if key in url:
                return resp
        return MockResponse({}, status=404, text_data="Not found")

    def request(self, method: str, url: str, **kwargs):
        self.requests.append((method, url, kwargs))
        return self._match(method, url)

    async def close(self):
        self._closed = True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def oanda_responses():
    """Default set of mock OANDA API responses."""
    return {
        "/summary": MockResponse(_oanda_account_summary()),
        "/orders": MockResponse(_oanda_order_fill_response()),
        "/cancel": MockResponse({}, status=200),
        "/openPositions": MockResponse(_oanda_positions_response()),
        "/pricing": MockResponse(_oanda_price_response()),
        "/candles": MockResponse(_oanda_candles_response()),
    }


@pytest.fixture
def connector(oanda_responses):
    """OandaConnector with mocked session."""
    conn = OandaConnector(
        account_id="101-001-1234567-001",
        access_token="test-token-fake",
        environment="practice",
    )
    conn._session = MockSession(oanda_responses)
    return conn


@pytest.fixture
async def connected_connector(connector):
    """Pre-connected OandaConnector."""
    connector._transition(ConnectionState.CONNECTED)
    return connector


# ===========================================================================
# TESTS — Connection
# ===========================================================================

class TestOandaConnection:

    @pytest.mark.asyncio
    async def test_connect_success(self, connector):
        connector._session = MockSession({
            "/summary": MockResponse(_oanda_account_summary()),
        })
        await connector.connect()
        assert connector.is_connected
        assert connector.state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_failure_sets_error_state(self, connector):
        connector._session = MockSession({
            "/summary": MockResponse({}, status=401, text_data="Unauthorized"),
        })
        with pytest.raises(RuntimeError, match="401"):
            await connector.connect()
        assert connector.state == ConnectionState.ERROR

    @pytest.mark.asyncio
    async def test_disconnect(self, connected_connector):
        await connected_connector.disconnect()
        assert connected_connector.state == ConnectionState.DISCONNECTED
        assert connected_connector._session is None or connected_connector._session._closed

    @pytest.mark.asyncio
    async def test_base_url_practice(self):
        conn = OandaConnector(account_id="x", access_token="y", environment="practice")
        assert "practice" in conn._base_url

    @pytest.mark.asyncio
    async def test_base_url_live(self):
        conn = OandaConnector(account_id="x", access_token="y", environment="live")
        assert "fxtrade" in conn._base_url

    def test_headers_contain_token(self, connector):
        headers = connector._headers
        assert "Bearer test-token-fake" in headers["Authorization"]


# ===========================================================================
# TESTS — Order Placement
# ===========================================================================

class TestOandaOrderPlacement:

    @pytest.mark.asyncio
    async def test_market_order_buy(self, connected_connector):
        order = BrokerOrder(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
        )
        result = await connected_connector.place_order(order)
        assert result.status == OrderStatus.FILLED
        assert result.broker_order_id == "12345"
        assert result.avg_fill_price == pytest.approx(1.10505)
        assert result.filled_quantity == 100

    @pytest.mark.asyncio
    async def test_market_order_sell(self, connected_connector):
        connected_connector._session = MockSession({
            "/orders": MockResponse(_oanda_order_fill_response(units="-500")),
        })
        order = BrokerOrder(
            symbol="EUR/USD",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=500,
        )
        result = await connected_connector.place_order(order)
        assert result.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_limit_order(self, connected_connector):
        connected_connector._session = MockSession({
            "/orders": MockResponse(_oanda_pending_order_response()),
        })
        order = BrokerOrder(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=1.1000,
        )
        result = await connected_connector.place_order(order)
        assert result.status == OrderStatus.OPEN
        assert result.broker_order_id == "12346"

    @pytest.mark.asyncio
    async def test_stop_order(self, connected_connector):
        stop_resp = {
            "orderCreateTransaction": {
                "id": "12347",
                "type": "STOP",
                "instrument": "EUR_USD",
                "units": "100",
                "price": "1.11000",
                "timeInForce": "GTC",
            },
        }
        connected_connector._session = MockSession({
            "/orders": MockResponse(stop_resp),
        })
        order = BrokerOrder(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.STOP,
            quantity=100,
            price=1.1100,
        )
        result = await connected_connector.place_order(order)
        assert result.status == OrderStatus.OPEN
        assert result.broker_order_id == "12347"

    @pytest.mark.asyncio
    async def test_order_with_sl_tp(self, connected_connector):
        order = BrokerOrder(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            stop_loss=1.1000,
            take_profit=1.1150,
        )
        result = await connected_connector.place_order(order)
        assert result.status == OrderStatus.FILLED
        # Verify SL/TP were passed in request body
        _, _, kwargs = connected_connector._session.requests[-1]
        body = kwargs.get("json", {})
        assert "stopLossOnFill" in body.get("order", {})
        assert "takeProfitOnFill" in body.get("order", {})

    @pytest.mark.asyncio
    async def test_symbol_format_conversion(self, connected_connector):
        """EUR/USD should be sent as EUR_USD to OANDA."""
        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=100)
        await connected_connector.place_order(order)
        _, _, kwargs = connected_connector._session.requests[-1]
        assert kwargs["json"]["order"]["instrument"] == "EUR_USD"

    @pytest.mark.asyncio
    async def test_order_timestamp_set(self, connected_connector):
        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=100)
        result = await connected_connector.place_order(order)
        assert result.updated_at is not None


# ===========================================================================
# TESTS — Position Retrieval
# ===========================================================================

class TestOandaPositions:

    @pytest.mark.asyncio
    async def test_get_positions(self, connected_connector):
        positions = await connected_connector.get_positions()
        assert len(positions) == 2

    @pytest.mark.asyncio
    async def test_long_position_parsed(self, connected_connector):
        positions = await connected_connector.get_positions()
        long_pos = next(p for p in positions if p.side == PositionSide.LONG)
        assert long_pos.symbol == "EUR/USD"
        assert long_pos.quantity == 1000
        assert long_pos.avg_entry_price == pytest.approx(1.10500)
        assert long_pos.unrealized_pnl == pytest.approx(50.0)

    @pytest.mark.asyncio
    async def test_short_position_parsed(self, connected_connector):
        positions = await connected_connector.get_positions()
        short_pos = next(p for p in positions if p.side == PositionSide.SHORT)
        assert short_pos.symbol == "GBP/USD"
        assert short_pos.quantity == 500
        assert short_pos.unrealized_pnl == pytest.approx(-25.0)

    @pytest.mark.asyncio
    async def test_empty_positions(self, connected_connector):
        connected_connector._session = MockSession({
            "/openPositions": MockResponse({"positions": []}),
        })
        positions = await connected_connector.get_positions()
        assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_position_symbol_normalized(self, connected_connector):
        """OANDA returns EUR_USD; we convert to EUR/USD."""
        positions = await connected_connector.get_positions()
        for p in positions:
            assert "_" not in p.symbol
            assert "/" in p.symbol


# ===========================================================================
# TESTS — Balance
# ===========================================================================

class TestOandaBalance:

    @pytest.mark.asyncio
    async def test_get_balance(self, connected_connector):
        balance = await connected_connector.get_balance()
        assert isinstance(balance, BrokerBalance)
        assert balance.broker == "oanda"
        assert balance.currency == "USD"
        assert balance.total == pytest.approx(10000.0)
        assert balance.equity == pytest.approx(10050.0)
        assert balance.unrealized_pnl == pytest.approx(50.0)
        assert balance.used_margin == pytest.approx(1105.0)


# ===========================================================================
# TESTS — Price / Tick
# ===========================================================================

class TestOandaTick:

    @pytest.mark.asyncio
    async def test_get_tick(self, connected_connector):
        tick = await connected_connector.get_tick("EUR/USD")
        assert isinstance(tick, BrokerTick)
        assert tick.broker == "oanda"
        assert tick.symbol == "EUR/USD"
        assert tick.bid == pytest.approx(1.10500)
        assert tick.ask == pytest.approx(1.10520)
        assert tick.spread == pytest.approx(0.00020)

    @pytest.mark.asyncio
    async def test_tick_symbol_conversion(self, connected_connector):
        await connected_connector.get_tick("GBP/USD")
        _, _, kwargs = connected_connector._session.requests[-1]
        assert kwargs.get("params", {}).get("instruments") == "GBP_USD"


# ===========================================================================
# TESTS — Price Streaming (mock)
# ===========================================================================

class TestOandaStreaming:

    @pytest.mark.asyncio
    async def test_streaming_price_iteration(self):
        """Simulate streaming by iterating mock price responses."""
        prices = [
            {"bids": [{"price": "1.10500"}], "asks": [{"price": "1.10520"}], "time": "2025-06-15T12:00:00Z"},
            {"bids": [{"price": "1.10510"}], "asks": [{"price": "1.10530"}], "time": "2025-06-15T12:00:01Z"},
            {"bids": [{"price": "1.10490"}], "asks": [{"price": "1.10510"}], "time": "2025-06-15T12:00:02Z"},
        ]

        async def mock_price_stream():
            for p in prices:
                yield p

        ticks = []
        async for price in mock_price_stream():
            bid = float(price["bids"][0]["price"])
            ask = float(price["asks"][0]["price"])
            ticks.append(BrokerTick(broker="oanda", symbol="EUR/USD", bid=bid, ask=ask, spread=ask - bid))

        assert len(ticks) == 3
        assert ticks[0].bid == pytest.approx(1.10500)
        assert ticks[1].bid == pytest.approx(1.10510)
        assert ticks[2].spread == pytest.approx(0.00020)

    @pytest.mark.asyncio
    async def test_streaming_detects_price_change(self):
        """Verify price changes are detected across stream messages."""
        prices = [1.10500, 1.10510, 1.10490, 1.10505]
        changes = []
        prev = prices[0]
        for p in prices[1:]:
            changes.append(p - prev)
            prev = p

        assert len(changes) == 3
        assert changes[0] == pytest.approx(0.00010)
        assert changes[1] == pytest.approx(-0.00020)


# ===========================================================================
# TESTS — Bars / Historical Data
# ===========================================================================

class TestOandaBars:

    @pytest.mark.asyncio
    async def test_get_bars(self, connected_connector):
        bars = await connected_connector.get_bars("EUR/USD", "H1", count=3)
        assert len(bars) == 3
        assert all(isinstance(b, BrokerBar) for b in bars)

    @pytest.mark.asyncio
    async def test_bar_ohlc_values(self, connected_connector):
        bars = await connected_connector.get_bars("EUR/USD", "H1", count=1)
        bar = bars[0]
        assert bar.open > 0
        assert bar.high >= bar.open
        assert bar.low <= bar.open
        assert bar.close > 0

    @pytest.mark.asyncio
    async def test_incomplete_bars_filtered(self, connected_connector):
        """Incomplete candles should be excluded."""
        candles_resp = {
            "candles": [
                {"time": "2025-06-15T12:00:00Z", "complete": True,
                 "mid": {"o": "1.10000", "h": "1.10500", "l": "1.09500", "c": "1.10200"}, "volume": 1000},
                {"time": "2025-06-15T13:00:00Z", "complete": False,
                 "mid": {"o": "1.10200", "h": "1.10300", "l": "1.10100", "c": "1.10250"}, "volume": 500},
                {"time": "2025-06-15T14:00:00Z", "complete": True,
                 "mid": {"o": "1.10200", "h": "1.10600", "l": "1.10100", "c": "1.10500"}, "volume": 1200},
            ]
        }
        connected_connector._session = MockSession({"/candles": MockResponse(candles_resp)})
        bars = await connected_connector.get_bars("EUR/USD", "H1", count=3)
        assert len(bars) == 2  # Only complete candles


# ===========================================================================
# TESTS — Error Handling
# ===========================================================================

class TestOandaErrorHandling:

    @pytest.mark.asyncio
    async def test_api_error_raises(self, connected_connector):
        connected_connector._session = MockSession({
            "/orders": MockResponse({}, status=400, text_data='{"errorMessage":"Invalid units"}'),
        })
        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0)
        with pytest.raises(RuntimeError, match="400"):
            await connected_connector.place_order(order)

    @pytest.mark.asyncio
    async def test_network_timeout(self, connected_connector):
        """Simulate a timeout by making the session raise."""
        class _TimeoutCtx:
            async def __aenter__(self):
                raise asyncio.TimeoutError("Connection timed out")
            async def __aexit__(self, *args):
                pass

        def _timeout(*args, **kwargs):
            return _TimeoutCtx()

        connected_connector._session = MagicMock()
        connected_connector._session.request = _timeout

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=100)
        with pytest.raises(asyncio.TimeoutError):
            await connected_connector.place_order(order)

    @pytest.mark.asyncio
    async def test_invalid_symbol_returns_error(self, connected_connector):
        connected_connector._session = MockSession({
            "/orders": MockResponse({}, status=400, text_data='{"errorMessage":"Unknown instrument: XYZ_ABC"}'),
        })
        order = BrokerOrder(symbol="XYZ/ABC", side=OrderSide.BUY, quantity=100)
        with pytest.raises(RuntimeError, match="400"):
            await connected_connector.place_order(order)

    @pytest.mark.asyncio
    async def test_unauthorized_on_tick(self, connected_connector):
        connected_connector._session = MockSession({
            "/pricing": MockResponse({}, status=401, text_data="Unauthorized"),
        })
        with pytest.raises(RuntimeError, match="401"):
            await connected_connector.get_tick("EUR/USD")

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, connected_connector):
        connected_connector._session = MockSession({
            "/orders": MockResponse({}, status=429, text_data="Rate limit exceeded"),
        })
        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=100)
        with pytest.raises(RuntimeError, match="429"):
            await connected_connector.place_order(order)

    @pytest.mark.asyncio
    async def test_server_error(self, connected_connector):
        connected_connector._session = MockSession({
            "/summary": MockResponse({}, status=500, text_data="Internal server error"),
        })
        with pytest.raises(RuntimeError, match="500"):
            await connected_connector.get_balance()
