#!/usr/bin/env python3
"""Test real broker connections – CCXT (Binance/MEXC) and MT5 (FXPesa).

This script tests connectivity to live broker APIs using public data
(no credentials needed for market data endpoints).

Usage::

    # Test all connections
    python scripts/test_broker_connection.py

    # Test specific broker
    python scripts/test_broker_connection.py --broker mexc
    python scripts/test_broker_connection.py --broker binance
    python scripts/test_broker_connection.py --broker fxpesa

    # With credentials (for balance/position checks)
    CCXT_API_KEY=xxx CCXT_SECRET=yyy python scripts/test_broker_connection.py --full

Environment Variables:
    CCXT_API_KEY    - Exchange API key (optional, for authenticated endpoints)
    CCXT_SECRET     - Exchange secret (optional)
    MT5_LOGIN       - MT5 account number (for FXPesa)
    MT5_PASSWORD    - MT5 password (for FXPesa)
    MT5_SERVER      - MT5 server name (e.g., FXPesa-Demo)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def header(text: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 60}{Colors.END}\n")


def success(text: str) -> None:
    print(f"  {Colors.GREEN}✓{Colors.END} {text}")


def error(text: str) -> None:
    print(f"  {Colors.RED}✗{Colors.END} {text}")


def info(text: str) -> None:
    print(f"  {Colors.YELLOW}▸{Colors.END} {text}")


def metric(label: str, value: str) -> None:
    print(f"    {label:<25} {Colors.BOLD}{value}{Colors.END}")


# ---------------------------------------------------------------------------
# CCXT connection tests
# ---------------------------------------------------------------------------

async def test_ccxt_public(
    exchange_id: str,
    symbols: list[str] | None = None,
) -> bool:
    """Test CCXT public API (no auth required).

    Parameters
    ----------
    exchange_id : str
        Exchange identifier (binance, mexc, etc.)
    symbols : list[str] | None
        Symbols to test. Defaults to exchange-appropriate pairs.

    Returns
    -------
    bool
        True if all tests passed.
    """
    header(f"CCXT Public API Test – {exchange_id.upper()}")

    try:
        import ccxt.async_support as ccxt_async
    except ImportError:
        try:
            import ccxt as ccxt_async
        except ImportError:
            error("ccxt not installed – run: pip install ccxt")
            return False

    exchange_class = getattr(ccxt_async, exchange_id, None)
    if exchange_class is None:
        error(f"Unknown exchange: {exchange_id}")
        return False

    # Default symbols per exchange
    if symbols is None:
        default_symbols = {
            "binance": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
            "mexc": ["BTC/USDT", "ETH/USDT", "DOGE/USDT"],
            "bybit": ["BTC/USDT", "ETH/USDT", "XRP/USDT"],
            "okx": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        }
        symbols = default_symbols.get(exchange_id, ["BTC/USDT", "ETH/USDT"])

    passed = True
    exchange = exchange_class({"enableRateLimit": True})

    try:
        # Test 1: Load markets
        t0 = time.time()
        await exchange.load_markets()
        load_time = (time.time() - t0) * 1000
        success(f"Markets loaded ({len(exchange.markets)} symbols, {load_time:.0f}ms)")
        metric("Total markets", str(len(exchange.markets)))

        # Count spot markets
        spot_markets = [m for m in exchange.markets.values() if m.get("spot")]
        metric("Spot markets", str(len(spot_markets)))

        # Test 2: Fetch tickers
        for symbol in symbols:
            try:
                t0 = time.time()
                ticker = await exchange.fetch_ticker(symbol)
                latency = (time.time() - t0) * 1000

                bid = ticker.get("bid", 0)
                ask = ticker.get("ask", 0)
                last = ticker.get("last", 0)
                spread = ask - bid if bid and ask else 0
                spread_pct = (spread / last * 100) if last else 0
                volume = ticker.get("quoteVolume", 0)

                success(f"{symbol}")
                metric("Last", f"${last:,.2f}" if last > 1 else f"${last:.6f}")
                metric("Bid/Ask", f"${bid:,.2f} / ${ask:,.2f}" if bid > 1 else f"${bid:.6f} / ${ask:.6f}")
                metric("Spread", f"{spread_pct:.4f}%")
                metric("24h Volume", f"${volume:,.0f}")
                metric("Latency", f"{latency:.0f}ms")
            except Exception as exc:
                error(f"{symbol} – {exc}")
                passed = False

        # Test 3: Fetch OHLCV
        try:
            symbol = symbols[0]
            t0 = time.time()
            ohlcv = await exchange.fetch_ohlcv(symbol, "1h", limit=10)
            latency = (time.time() - t0) * 1000
            success(f"OHLCV ({symbol}, 1h × {len(ohlcv)} bars, {latency:.0f}ms)")
        except Exception as exc:
            error(f"OHLCV – {exc}")
            passed = False

        # Test 4: Order book depth
        try:
            symbol = symbols[0]
            t0 = time.time()
            ob = await exchange.fetch_order_book(symbol, limit=5)
            latency = (time.time() - t0) * 1000
            bids = len(ob.get("bids", []))
            asks = len(ob.get("asks", []))
            success(f"Order Book ({symbol}, {bids} bids / {asks} asks, {latency:.0f}ms)")
        except Exception as exc:
            error(f"Order Book – {exc}")
            passed = False

    except Exception as exc:
        error(f"Connection failed: {exc}")
        passed = False
    finally:
        await exchange.close()

    return passed


async def test_ccxt_authenticated(exchange_id: str) -> bool:
    """Test CCXT authenticated endpoints (requires API key).

    Returns
    -------
    bool
        True if all tests passed.
    """
    header(f"CCXT Authenticated Test – {exchange_id.upper()}")

    api_key = os.environ.get("CCXT_API_KEY", "")
    secret = os.environ.get("CCXT_SECRET", "")

    if not api_key or not secret:
        info("Skipping – set CCXT_API_KEY and CCXT_SECRET to test authenticated endpoints")
        return True

    try:
        import ccxt.async_support as ccxt_async
    except ImportError:
        import ccxt as ccxt_async

    exchange_class = getattr(ccxt_async, exchange_id, None)
    exchange = exchange_class({
        "apiKey": api_key,
        "secret": secret,
        "enableRateLimit": True,
    })

    passed = True

    try:
        await exchange.load_markets()

        # Test: Fetch balance
        try:
            t0 = time.time()
            balance = await exchange.fetch_balance()
            latency = (time.time() - t0) * 1000

            usdt = balance.get("USDT", {})
            total = float(usdt.get("total") or 0)
            free = float(usdt.get("free") or 0)
            used = float(usdt.get("used") or 0)

            success(f"Balance fetched ({latency:.0f}ms)")
            metric("USDT Total", f"${total:,.4f}")
            metric("USDT Free", f"${free:,.4f}")
            metric("USDT Used", f"${used:,.4f}")

            # Show non-zero balances
            for currency, data in balance.items():
                if isinstance(data, dict):
                    t = float(data.get("total") or 0)
                    if t > 0 and currency not in ("USDT", "info", "free", "used", "total"):
                        metric(currency, f"{t:,.8f}")
        except Exception as exc:
            error(f"Balance – {exc}")
            passed = False

        # Test: Fetch open orders
        try:
            orders = await exchange.fetch_open_orders()
            success(f"Open orders: {len(orders)}")
        except Exception as exc:
            error(f"Open orders – {exc}")
            passed = False

        # Test: Fetch positions (if futures)
        try:
            positions = await exchange.fetch_positions()
            open_pos = [p for p in positions if float(p.get("contracts") or 0) > 0]
            success(f"Positions: {len(open_pos)} open / {len(positions)} total")
        except Exception:
            info("Positions not available (spot-only exchange)")

    except Exception as exc:
        error(f"Auth test failed: {exc}")
        passed = False
    finally:
        await exchange.close()

    return passed


# ---------------------------------------------------------------------------
# MT5 / FXPesa connection tests
# ---------------------------------------------------------------------------

async def test_mt5_connection(
    login: int | None = None,
    password: str | None = None,
    server: str | None = None,
) -> bool:
    """Test MetaTrader 5 connection (FXPesa demo).

    Parameters
    ----------
    login : int | None
        MT5 account number.
    password : str | None
        MT5 password.
    server : str | None
        MT5 server name.

    Returns
    -------
    bool
        True if all tests passed.
    """
    header("MetaTrader 5 / FXPesa Connection Test")

    # Check credentials
    login = login or int(os.environ.get("MT5_LOGIN", "0"))
    password = password or os.environ.get("MT5_PASSWORD", "")
    server = server or os.environ.get("MT5_SERVER", "FXPesa-Demo")

    if not login:
        info("Skipping – set MT5_LOGIN, MT5_PASSWORD, MT5_SERVER to test")
        info("FXPesa demo accounts: register at https://www.fxpesa.com")
        return True

    try:
        import MetaTrader5 as mt5
    except ImportError:
        error("MetaTrader5 not installed – run: pip install MetaTrader5")
        info("Note: MT5 Python package only works on Windows")
        info("For Linux: use Wine or a remote Windows VPS")
        return False

    passed = True

    # Initialize
    t0 = time.time()
    if not mt5.initialize():
        err = mt5.last_error()
        error(f"MT5 initialize failed: {err}")
        return False
    init_time = (time.time() - t0) * 1000
    success(f"MT5 initialized ({init_time:.0f}ms)")

    try:
        # Login
        t0 = time.time()
        authorized = mt5.login(login, password=password, server=server)
        login_time = (time.time() - t0) * 1000

        if not authorized:
            err = mt5.last_error()
            error(f"MT5 login({login}) failed: {err}")
            passed = False
        else:
            success(f"Logged in to {server} ({login_time:.0f}ms)")

        # Account info
        try:
            info = mt5.account_info()
            if info:
                d = info._asdict() if hasattr(info, "_asdict") else {}
                success("Account info retrieved")
                metric("Login", str(d.get("login", "")))
                metric("Server", d.get("server", ""))
                metric("Currency", d.get("currency", ""))
                metric("Balance", f"${d.get('balance', 0):,.2f}")
                metric("Equity", f"${d.get('equity', 0):,.2f}")
                metric("Margin", f"${d.get('margin', 0):,.2f}")
                metric("Free Margin", f"${d.get('margin_free', 0):,.2f}")
                metric("Leverage", f"1:{d.get('leverage', 0)}")
                metric("Margin Level", f"{d.get('margin_level', 0):.1f}%")
        except Exception as exc:
            error(f"Account info – {exc}")
            passed = False

        # Terminal info
        try:
            terminal = mt5.terminal_info()
            if terminal:
                td = terminal._asdict() if hasattr(terminal, "_asdict") else {}
                success("Terminal info retrieved")
                metric("Company", td.get("company", ""))
                metric("Build", str(td.get("build", "")))
                metric("Connected", str(td.get("connected", "")))
                metric("Trade Allowed", str(td.get("trade_allowed", "")))
        except Exception as exc:
            error(f"Terminal info – {exc}")

        # Symbol info (FXPesa pairs)
        test_symbols = ["EURUSD", "GBPUSD", "XAUUSD"]
        for sym in test_symbols:
            try:
                si = mt5.symbol_info(sym)
                if si is None:
                    # Try with cent suffix
                    si = mt5.symbol_info(sym + "c")
                    if si:
                        sym = sym + "c"

                if si:
                    sd = si._asdict() if hasattr(si, "_asdict") else {}
                    point = sd.get("point", 0)
                    digits = sd.get("digits", 0)
                    spread = sd.get("spread", 0)
                    vol_min = sd.get("volume_min", 0)
                    contract = sd.get("trade_contract_size", 0)

                    success(f"Symbol {sym}")
                    metric("Point", str(point))
                    metric("Digits", str(digits))
                    metric("Spread", f"{spread} points")
                    metric("Min Lot", str(vol_min))
                    metric("Contract Size", str(contract))
                else:
                    info(f"Symbol {sym} not available on this server")
            except Exception as exc:
                error(f"Symbol {sym} – {exc}")

        # Tick data
        try:
            tick = mt5.symbol_info_tick("EURUSD")
            if tick:
                td = tick._asdict() if hasattr(tick, "_asdict") else {}
                success("EURUSD tick data")
                metric("Bid", f"{td.get('bid', 0):.5f}")
                metric("Ask", f"{td.get('ask', 0):.5f}")
                metric("Spread", f"{td.get('spread', 0)} points")
                metric("Time", str(datetime.fromtimestamp(td.get("time", 0), tz=timezone.utc)))
        except Exception as exc:
            error(f"Tick data – {exc}")

        # Open positions
        try:
            positions = mt5.positions_get()
            if positions:
                success(f"Open positions: {len(positions)}")
                for p in positions[:5]:  # Show first 5
                    pd = p._asdict() if hasattr(p, "_asdict") else {}
                    info(
                        f"  {pd.get('symbol', '')} "
                        f"{'BUY' if pd.get('type') == 0 else 'SELL'} "
                        f"{pd.get('volume', 0)} lots "
                        f"@ {pd.get('price_open', 0):.5f} "
                        f"P&L: ${pd.get('profit', 0):+.2f}"
                    )
            else:
                success("No open positions")
        except Exception as exc:
            error(f"Positions – {exc}")

    except Exception as exc:
        error(f"MT5 test failed: {exc}")
        passed = False
    finally:
        mt5.shutdown()

    return passed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(description="Test AlphaStack broker connections")
    parser.add_argument(
        "--broker",
        choices=["mexc", "binance", "bybit", "okx", "fxpesa", "all"],
        default="all",
        help="Which broker to test",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Test authenticated endpoints (requires credentials)",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Symbols to test (e.g., BTC/USDT ETH/USDT)",
    )
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}AlphaStack Broker Connection Test{Colors.END}")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Python: {sys.version.split()[0]}")

    results: dict[str, bool] = {}

    if args.broker in ("mexc", "all"):
        results["mexc_public"] = await test_ccxt_public("mexc", args.symbols)
        if args.full:
            results["mexc_auth"] = await test_ccxt_authenticated("mexc")

    if args.broker in ("binance", "all"):
        results["binance_public"] = await test_ccxt_public("binance", args.symbols)
        if args.full:
            results["binance_auth"] = await test_ccxt_authenticated("binance")

    if args.broker in ("bybit", "all"):
        results["bybit_public"] = await test_ccxt_public("bybit", args.symbols)

    if args.broker in ("okx", "all"):
        results["okx_public"] = await test_ccxt_public("okx", args.symbols)

    if args.broker in ("fxpesa", "all"):
        results["fxpesa"] = await test_mt5_connection()

    # Summary
    header("Test Summary")
    all_passed = True
    for name, passed in results.items():
        if passed:
            success(f"{name}")
        else:
            error(f"{name}")
            all_passed = False

    if all_passed:
        print(f"\n  {Colors.GREEN}{Colors.BOLD}All tests passed ✓{Colors.END}\n")
    else:
        print(f"\n  {Colors.RED}{Colors.BOLD}Some tests failed ✗{Colors.END}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
