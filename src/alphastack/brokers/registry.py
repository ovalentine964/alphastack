"""Broker Registry – discover, connect, and route to multiple brokers."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from alphastack.brokers.base import BrokerConnector, ConnectionState
from alphastack.brokers.models import BrokerOrder

logger = structlog.get_logger(__name__)


class BrokerRegistry:
    """Central registry that manages multiple broker connectors.

    Typical usage::

        registry = BrokerRegistry()
        registry.register("mt5", mt5_connector)
        registry.register("binance", ccxt_connector)
        await registry.connect_all()

        # Route an order to a specific broker
        order = await registry.route_order(order)

        # Or let the registry pick the best one
        order = await registry.route_order_best(order)
    """

    def __init__(self) -> None:
        self._brokers: dict[str, BrokerConnector] = {}
        self._default_broker: str | None = None

    # -- registration -------------------------------------------------------

    def register(self, name: str, connector: BrokerConnector, *, default: bool = False) -> None:
        """Register a broker connector under *name*."""
        self._brokers[name] = connector
        if default or self._default_broker is None:
            self._default_broker = name
        logger.info("broker_registered", name=name, default=default)

    def unregister(self, name: str) -> None:
        """Remove a broker from the registry."""
        self._brokers.pop(name, None)
        if self._default_broker == name:
            self._default_broker = next(iter(self._brokers), None)

    def get(self, name: str) -> BrokerConnector | None:
        return self._brokers.get(name)

    @property
    def default(self) -> BrokerConnector | None:
        if self._default_broker:
            return self._brokers.get(self._default_broker)
        return None

    @property
    def names(self) -> list[str]:
        return list(self._brokers.keys())

    # -- lifecycle ----------------------------------------------------------

    async def connect_all(self) -> dict[str, bool]:
        """Connect every registered broker concurrently. Returns success map."""
        results: dict[str, bool] = {}

        async def _connect(name: str, connector: BrokerConnector) -> None:
            try:
                await connector.connect()
                results[name] = True
            except Exception as exc:
                logger.error("broker_connect_failed", name=name, error=str(exc))
                results[name] = False

        await asyncio.gather(
            *[_connect(n, c) for n, c in self._brokers.items()]
        )
        return results

    async def disconnect_all(self) -> None:
        """Disconnect every registered broker."""
        await asyncio.gather(
            *[c.disconnect() for c in self._brokers.values()],
            return_exceptions=True,
        )

    async def reconnect(self, name: str) -> None:
        """Reconnect a single broker by name."""
        connector = self._brokers.get(name)
        if connector is None:
            raise KeyError(f"Unknown broker: {name}")
        await connector.reconnect()

    # -- order routing ------------------------------------------------------

    def _get_connector(self, broker_name: str | None) -> BrokerConnector:
        """Resolve broker name to connector, falling back to default."""
        name = broker_name or self._default_broker
        if name is None:
            raise RuntimeError("No brokers registered")
        connector = self._brokers.get(name)
        if connector is None:
            raise KeyError(f"Unknown broker: {name}")
        return connector

    async def route_order(self, order: BrokerOrder) -> BrokerOrder:
        """Route an order to the broker specified in ``order.broker``.

        If *order.broker* is empty the default broker is used.
        """
        connector = self._get_connector(order.broker or None)
        order.broker = connector.name
        return await connector.place_order(order)

    async def route_order_with_failover(self, order: BrokerOrder) -> BrokerOrder:
        """Try the target broker first, then fall back to others on failure."""
        primary_name = order.broker or self._default_broker
        tried: set[str] = set()

        # Try primary first
        if primary_name and primary_name in self._brokers:
            tried.add(primary_name)
            connector = self._brokers[primary_name]
            if connector.is_connected:
                try:
                    order.broker = connector.name
                    return await connector.place_order(order)
                except Exception as exc:
                    logger.warning(
                        "primary_broker_failed",
                        broker=primary_name,
                        error=str(exc),
                    )

        # Fail over to remaining connected brokers
        for name, connector in self._brokers.items():
            if name in tried or not connector.is_connected:
                continue
            try:
                logger.info("failing_over", broker=name)
                order.broker = connector.name
                return await connector.place_order(order)
            except Exception as exc:
                logger.warning("failover_broker_failed", broker=name, error=str(exc))
                tried.add(name)

        raise RuntimeError("All brokers exhausted – order could not be placed")

    # -- auto-detection / factory ------------------------------------------

    @classmethod
    def from_env(cls) -> BrokerRegistry:
        """Create a registry and auto-register brokers from environment variables.

        Detection logic:
        1. If ``CCXT_API_KEY`` is set → register the CCXT connector.
        2. If ``OANDA_ACCOUNT_ID`` + ``OANDA_API_KEY`` are set → register OANDA.
        3. If ``MT5_LOGIN`` is set → register MT5.
        4. The first-registered broker becomes the default.
        """
        from alphastack.core.config import get_settings

        registry = cls()
        cfg = get_settings()

        # --- CCXT (crypto) ---
        ccxt_key = cfg.ccxt.api_key.get_secret_value()
        if ccxt_key:
            try:
                from alphastack.brokers.ccxt_connector import CCXTConnector
                connector = CCXTConnector()
                registry.register("ccxt", connector, default=True)
                logger.info("auto_registered_ccxt", exchange=cfg.ccxt.exchange)
            except Exception as exc:
                logger.warning("auto_register_ccxt_failed", error=str(exc))

        # --- OANDA (forex) ---
        oanda_id = cfg.oanda.account_id
        oanda_key = cfg.oanda.api_key.get_secret_value()
        if oanda_id and oanda_key:
            try:
                from alphastack.brokers.oanda_connector import OandaConnector
                connector = OandaConnector()
                default = not bool(ccxt_key)  # Default if no crypto broker
                registry.register("oanda", connector, default=default)
                logger.info(
                    "auto_registered_oanda",
                    account=oanda_id,
                    environment=cfg.oanda.environment,
                )
            except Exception as exc:
                logger.warning("auto_register_oanda_failed", error=str(exc))

        # --- MT5 (forex / CFD) ---
        mt5_login = cfg.mt5.login
        if mt5_login:
            try:
                from alphastack.brokers.mt5_connector import MT5Connector
                connector = MT5Connector()
                default = not bool(ccxt_key or oanda_key)
                registry.register("mt5", connector, default=default)
                logger.info("auto_registered_mt5", login=mt5_login)
            except Exception as exc:
                logger.warning("auto_register_mt5_failed", error=str(exc))

        if not registry.names:
            logger.warning(
                "no_brokers_configured",
                msg="Set CCXT_API_KEY, OANDA_ACCOUNT_ID+OANDA_API_KEY, or MT5_LOGIN to enable a broker.",
            )

        return registry

    # -- status -------------------------------------------------------------

    def status(self) -> dict[str, str]:
        """Return connection state of every registered broker."""
        return {name: c.state.value for name, c in self._brokers.items()}

    def connected_brokers(self) -> list[str]:
        return [n for n, c in self._brokers.items() if c.is_connected]
