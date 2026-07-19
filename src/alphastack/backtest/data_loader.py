"""Historical data loader — CCXT fetch_ohlcv and CSV support.

Loads OHLCV data into a normalized pandas DataFrame used by BacktestEngine.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger("alphastack.backtest.data_loader")


# ---------------------------------------------------------------------------
# DataFrame schema
# ---------------------------------------------------------------------------

OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame has the expected schema and types."""
    missing = set(OHLCV_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df = df[OHLCV_COLUMNS].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df.dropna(subset=["open", "high", "low", "close"], inplace=True)
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# ---------------------------------------------------------------------------
# CCXT loader
# ---------------------------------------------------------------------------

# Map human-readable timeframes to CCXT timeframe strings
_TIMEFRAME_MAP = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h", "12h": "12h",
    "1d": "1d", "3d": "3d", "1w": "1w", "1M": "1M",
}


def _tf_to_ms(timeframe: str) -> int:
    """Convert a timeframe string to milliseconds."""
    unit = timeframe[-1]
    val = int(timeframe[:-1])
    multipliers = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000, "M": 2_592_000_000}
    if unit not in multipliers:
        raise ValueError(f"Unknown timeframe unit: {unit}")
    return val * multipliers[unit]


def load_ccxt(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    days: int = 30,
    exchange_id: str = "binance",
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    max_candles: int = 5000,
) -> pd.DataFrame:
    """Fetch OHLCV data from a CCXT exchange.

    Parameters
    ----------
    symbol : str
        Trading pair, e.g. "BTC/USDT".
    timeframe : str
        Candle timeframe, e.g. "1h", "4h", "1d".
    days : int
        Number of days of history to fetch (ignored if *since* is set).
    exchange_id : str
        CCXT exchange id (default "binance").
    since : datetime, optional
        Start time (UTC). Defaults to *days* ago.
    until : datetime, optional
        End time (UTC). Defaults to now.
    max_candles : int
        Maximum candles to fetch per CCXT call.

    Returns
    -------
    pd.DataFrame
        Validated OHLCV DataFrame.
    """
    try:
        import ccxt
    except ImportError:
        raise ImportError("ccxt is required: pip install ccxt")

    exchange_class = getattr(ccxt, exchange_id, None)
    if exchange_class is None:
        raise ValueError(f"Unknown exchange: {exchange_id}")

    exchange: ccxt.Exchange = exchange_class({"enableRateLimit": True})

    tf = _TIMEFRAME_MAP.get(timeframe, timeframe)
    tf_ms = _tf_to_ms(tf)

    now = until or datetime.now(timezone.utc)
    start = since or (now - timedelta(days=days))
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)

    logger.info(
        "Fetching %s %s from %s (%s → %s)",
        symbol, tf, exchange_id, start.isoformat(), now.isoformat(),
    )

    all_candles: list[list] = []
    cursor = start_ms

    while cursor < end_ms and len(all_candles) < max_candles:
        candles = exchange.fetch_ohlcv(symbol, tf, since=cursor, limit=1000)
        if not candles:
            break
        all_candles.extend(candles)
        cursor = candles[-1][0] + tf_ms  # next candle after last received
        logger.debug("Fetched %d candles, cursor at %s", len(candles), datetime.fromtimestamp(cursor / 1000, tz=timezone.utc).isoformat())

    if not all_candles:
        raise ValueError(f"No data returned for {symbol} {tf}")

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = validate_ohlcv(df)

    # Trim to requested window
    df = df[(df["timestamp"] >= pd.Timestamp(start, tz="UTC")) & (df["timestamp"] <= pd.Timestamp(now, tz="UTC"))]
    df.reset_index(drop=True, inplace=True)

    logger.info("Loaded %d candles for %s %s", len(df), symbol, tf)
    return df


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def load_csv(
    path: str | Path,
    *,
    timestamp_col: str = "timestamp",
    date_format: str | None = None,
) -> pd.DataFrame:
    """Load OHLCV data from a CSV file.

    Expected columns: timestamp, open, high, low, close, volume.
    The timestamp column can be named 'timestamp', 'date', 'datetime', or 'time'.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CSV not found: {p}")

    df = pd.read_csv(p)
    logger.info("Read %d rows from %s", len(df), p)

    # Normalize timestamp column name
    col_lower = {c.lower().strip(): c for c in df.columns}
    for alias in [timestamp_col, "timestamp", "date", "datetime", "time", "Date", "Timestamp"]:
        if alias in col_lower:
            df.rename(columns={col_lower[alias]: "timestamp"}, inplace=True)
            break
    else:
        # Assume first column is timestamp
        df.rename(columns={df.columns[0]: "timestamp"}, inplace=True)

    # Normalize OHLCV column names
    rename_map = {}
    for target in ["open", "high", "low", "close", "volume"]:
        for col in df.columns:
            if col.lower().strip() == target:
                rename_map[col] = target
                break
    df.rename(columns=rename_map, inplace=True)

    if date_format:
        df["timestamp"] = pd.to_datetime(df["timestamp"], format=date_format, utc=True)
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, infer_datetime_format=True)

    return validate_ohlcv(df)


# ---------------------------------------------------------------------------
# Dict adapter (for legacy backtester compatibility)
# ---------------------------------------------------------------------------

def df_to_dict(df: pd.DataFrame) -> dict[str, list[float]]:
    """Convert an OHLCV DataFrame to the dict format used by tests/backtest/backtester.py."""
    return {
        "opens": df["open"].tolist(),
        "highs": df["high"].tolist(),
        "lows": df["low"].tolist(),
        "closes": df["close"].tolist(),
        "volumes": df["volume"].tolist(),
    }
