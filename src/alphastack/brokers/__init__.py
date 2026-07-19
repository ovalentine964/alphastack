"""Broker connectors – unified abstraction over MT5, CCXT, OANDA, and future venues.

Exports
-------
Core ABC & models:
    BrokerConnector, BrokerOrder, BrokerPosition, BrokerBalance, BrokerTick,
    BrokerBar, OrderSide, OrderType, OrderStatus, TimeInForce, PositionSide

Connectors:
    CCXTConnector  – crypto exchanges (Binance, MEXC, Bybit, …)
    MT5Connector   – MetaTrader 5 (FXPesa, Scope Markets, …)

Routing & management:
    BrokerRegistry    – discover, connect, and manage multiple brokers
    SmartOrderRouter  – best-execution routing with slippage/fee estimation
    SmartRouter       – lower-level smart routing (legacy)
    OrderManager      – unified order lifecycle tracking

Utilities:
    FeeCalculator        – spread, commission, and swap cost calculation
    SlippageEstimator    – historical slippage calibration
    RoutingStrategy      – routing strategy enum
"""

from alphastack.brokers.base import BrokerConnector, ConnectionState
from alphastack.brokers.ccxt_connector import CCXTConnector
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
from alphastack.brokers.mt5_connector import MT5Connector
from alphastack.brokers.order_manager import OrderManager
from alphastack.brokers.registry import BrokerRegistry
from alphastack.brokers.router import (
    ExecutionQuality,
    FeeCalculator,
    RouterConfig,
    RoutingStrategy,
    SlippageEstimator,
    SmartOrderRouter,
)
from alphastack.brokers.smart_router import SmartRouter

__all__ = [
    # ABC & connection
    "BrokerConnector",
    "ConnectionState",
    # Models
    "BrokerBalance",
    "BrokerBar",
    "BrokerOrder",
    "BrokerPosition",
    "BrokerTick",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PositionSide",
    "TimeInForce",
    # Connectors
    "CCXTConnector",
    "MT5Connector",
    # Routing
    "BrokerRegistry",
    "SmartOrderRouter",
    "SmartRouter",
    "OrderManager",
    # Router internals
    "ExecutionQuality",
    "FeeCalculator",
    "RouterConfig",
    "RoutingStrategy",
    "SlippageEstimator",
]
