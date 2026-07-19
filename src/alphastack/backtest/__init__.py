"""AlphaStack Backtesting Engine — production-grade backtesting with CCXT data.

Quick start::

    from alphastack.backtest import BacktestEngine, BacktestConfig, load_ccxt

    df = load_ccxt("BTC/USDT", "1h", days=30)
    engine = BacktestEngine(BacktestConfig(initial_balance=10000))
    result = engine.run(df, symbol="BTC/USDT", timeframe="1h")
    result.report.print_summary()
"""

from alphastack.backtest.data_loader import load_ccxt, load_csv, df_to_dict
from alphastack.backtest.engine import (
    BacktestConfig,
    BacktestEngine,
    BacktestMetrics,
    BacktestResult,
    FillReason,
    SlippageConfig,
    TradeRecord,
)
from alphastack.backtest.report import BacktestReport

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestMetrics",
    "BacktestReport",
    "BacktestResult",
    "FillReason",
    "SlippageConfig",
    "TradeRecord",
    "load_ccxt",
    "load_csv",
    "df_to_dict",
]
