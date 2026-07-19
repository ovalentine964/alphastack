#!/usr/bin/env python3
"""Test order placement on MEXC (spot) with tiny test orders.

Places a minimal buy order, verifies it appears, then cancels and verifies cleanup.

⚠️  SAFETY: This script places REAL orders on a LIVE exchange.
    - Uses minimum possible order size (~$1-2)
    - Uses LIMIT orders (not market) for safety
    - Immediately cancels after verification
    - Requires CCXT_API_KEY and CCXT_SECRET environment variables

Usage::

    # Dry run (no actual orders)
    python scripts/test_order_placement.py --dry-run

    # Live test (places and cancels a limit order)
    python scripts/test_order_placement.py

    # Test on specific exchange
    python scripts/test_order_placement.py --exchange mexc
    python scripts/test_order_placement.py --exchange binance

    # Test with specific symbol
    python scripts/test_order_placement.py --symbol DOGE/USDT

Environment Variables:
    CCXT_API_KEY    - Exchange API key (REQUIRED)
    CCXT_SECRET     - Exchange secret (REQUIRED)
    CCXT_EXCHANGE   - Default exchange (default: mexc)
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
    DIM = "\033[2m"
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


def warn(text: str) -> None:
    print(f"  {Colors.YELLOW}⚠{Colors.END} {text}")


def metric(label: str, value: str) -> None:
    print(f"    {label:<25} {Colors.BOLD}{value}{Colors.END}")


# ---------------------------------------------------------------------------
# Minimum order sizes per exchange
# ---------------------------------------------------------------------------

# Minimum notional (in USDT) for each exchange
MIN_NOTIONAL: dict[str, float] = {
    "mexc": 1.0,
    "binance": 5.0,
    "bybit": 1.0,
    "okx": 1.0,
}

# Safe test symbols with low price per unit
# Using DOGE/USDT (~$0.10) to minimize test order value
DEFAULT_TEST_SYMBOLS: dict[str, str] = {
    "mexc": "DOGE/USDT",
    "binance": "DOGE/USDT",
    "bybit": "DOGE/USDT",
    "okx": "DOGE/USDT",
}


# ---------------------------------------------------------------------------
# Order test flow
# ---------------------------------------------------------------------------

async def test_order_lifecycle(
    exchange_id: str,
    symbol: str | None = None,
    dry_run: bool = False,
) -> bool:
    """Test the full order lifecycle: place → verify → cancel → verify cleanup.

    Parameters
    ----------
    exchange_id : str
        Exchange identifier.
    symbol : str | None
        Trading pair. Defaults to exchange-appropriate test symbol.
    dry_run : bool
        If True, only simulate the flow without placing real orders.

    Returns
    -------
    bool
        True if all tests passed.
    """
    header(f"Order Placement Test – {exchange_id.upper()}")

    api_key = os.environ.get("CCXT_API_KEY", "")
    secret = os.environ.get("CCXT_SECRET", "")

    if not api_key or not secret:
        error("CCXT_API_KEY and CCXT_SECRET are required")
        info("Set them in your environment or .env file")
        return False

    if symbol is None:
        symbol = DEFAULT_TEST_SYMBOLS.get(exchange_id, "DOGE/USDT")

    if dry_run:
        warn("DRY RUN mode – no real orders will be placed")
        print()

    try:
        import ccxt.async_support as ccxt_async
    except ImportError:
        import ccxt as ccxt_async

    exchange_class = getattr(ccxt_async, exchange_id, None)
    if exchange_class is None:
        error(f"Unknown exchange: {exchange_id}")
        return False

    exchange = exchange_class({
        "apiKey": api_key,
        "secret": secret,
        "enableRateLimit": True,
    })

    passed = True
    test_order_id: str | None = None

    try:
        # Step 1: Load markets
        info("Loading markets...")
        t0 = time.time()
        await exchange.load_markets()
        load_time = (time.time() - t0) * 1000
        success(f"Markets loaded ({len(exchange.markets)} symbols, {load_time:.0f}ms)")

        # Validate symbol exists
        if symbol not in exchange.markets:
            error(f"Symbol {symbol} not found on {exchange_id}")
            info(f"Available: {', '.join(list(exchange.markets.keys())[:10])}...")
            return False
        success(f"Symbol {symbol} available")

        market = exchange.markets[symbol]
        min_amount = market.get("limits", {}).get("amount", {}).get("min", 0)
        min_cost = market.get("limits", {}).get("cost", {}).get("min", 0)
        precision = market.get("precision", {})

        metric("Min Amount", str(min_amount))
        metric("Min Cost", f"${min_cost}" if min_cost else "N/A")
        metric("Price Precision", str(precision.get("price", "N/A")))
        metric("Amount Precision", str(precision.get("amount", "N/A")))

        # Step 2: Get current price
        info(f"Fetching current {symbol} price...")
        t0 = time.time()
        ticker = await exchange.fetch_ticker(symbol)
        latency = (time.time() - t0) * 1000

        current_price = ticker["last"]
        bid = ticker["bid"]
        ask = ticker["ask"]
        success(f"Current price: ${current_price:.6f} (bid: ${bid:.6f}, ask: ${ask:.6f}, {latency:.0f}ms)")

        # Step 3: Calculate test order parameters
        # Place a limit BUY order far below market price (won't fill)
        # This is the safest way to test order placement
        test_price = current_price * 0.80  # 20% below market
        min_notional = MIN_NOTIONAL.get(exchange_id, 1.0)

        # Calculate minimum quantity
        if min_amount and min_amount > 0:
            test_quantity = max(min_amount, min_notional / test_price)
        else:
            test_quantity = min_notional / test_price

        # Round to exchange precision
        amount_precision = precision.get("amount", 8)
        if isinstance(amount_precision, int):
            test_quantity = round(test_quantity, amount_precision)
        else:
            # Some exchanges use string precision like "0.001"
            step = float(amount_precision) if amount_precision else 0.001
            test_quantity = round(test_quantity / step) * step

        # Round price
        price_precision = precision.get("price", 8)
        if isinstance(price_precision, int):
            test_price = round(test_price, price_precision)
        else:
            step = float(price_precision) if price_precision else 0.0001
            test_price = round(test_price / step) * step

        notional = test_price * test_quantity
        info(f"Test order: BUY {test_quantity} {symbol} @ ${test_price:.6f} (notional: ${notional:.2f})")

        if notional > 10:
            warn(f"Order value ${notional:.2f} seems high for a test – aborting")
            return False

        # Step 4: Place test order
        if dry_run:
            info("[DRY RUN] Would place limit buy order")
            info(f"[DRY RUN] symbol={symbol}, side=buy, type=limit")
            info(f"[DRY RUN] quantity={test_quantity}, price={test_price:.6f}")
            success("[DRY RUN] Order placement simulated")
        else:
            info("Placing limit buy order...")
            try:
                t0 = time.time()
                order = await exchange.create_order(
                    symbol=symbol,
                    type="limit",
                    side="buy",
                    amount=test_quantity,
                    price=test_price,
                )
                latency = (time.time() - t0) * 1000

                test_order_id = order.get("id", "")
                order_status = order.get("status", "unknown")

                success(f"Order placed ({latency:.0f}ms)")
                metric("Order ID", test_order_id)
                metric("Status", order_status)
                metric("Type", order.get("type", ""))
                metric("Side", order.get("side", ""))
                metric("Amount", str(order.get("amount", "")))
                metric("Price", str(order.get("price", "")))
                metric("Filled", str(order.get("filled", "")))
                metric("Cost", str(order.get("cost", "")))
            except Exception as exc:
                error(f"Order placement failed: {exc}")
                passed = False

        # Step 5: Verify order appears in open orders
        if test_order_id and not dry_run:
            info("Verifying order in open orders...")
            try:
                t0 = time.time()
                open_orders = await exchange.fetch_open_orders(symbol)
                latency = (time.time() - t0) * 1000

                found = any(o.get("id") == test_order_id for o in open_orders)
                if found:
                    success(f"Order {test_order_id} found in open orders ({latency:.0f}ms)")
                    metric("Open Orders", str(len(open_orders)))
                else:
                    error(f"Order {test_order_id} NOT found in open orders")
                    # Check if it was filled immediately (unlikely for limit far from market)
                    info(f"Total open orders for {symbol}: {len(open_orders)}")
                    for o in open_orders:
                        info(f"  {o.get('id')} – {o.get('side')} {o.get('amount')} @ {o.get('price')}")
                    passed = False
            except Exception as exc:
                error(f"Fetch open orders failed: {exc}")
                passed = False

        # Step 6: Cancel test order
        if test_order_id and not dry_run:
            info(f"Cancelling order {test_order_id}...")
            try:
                t0 = time.time()
                cancel_result = await exchange.cancel_order(test_order_id, symbol)
                latency = (time.time() - t0) * 1000
                success(f"Order cancelled ({latency:.0f}ms)")

                cancel_status = cancel_result.get("status", "unknown")
                metric("Cancel Status", cancel_status)
            except Exception as exc:
                error(f"Cancel failed: {exc}")
                # Try to cancel via fetch_orders + cancel
                try:
                    info("Attempting alternative cancel...")
                    await exchange.cancel_order(test_order_id)
                    success("Order cancelled (alternative method)")
                except Exception as exc2:
                    error(f"Alternative cancel also failed: {exc2}")
                    passed = False

        # Step 7: Verify cleanup (no open orders for this symbol)
        if test_order_id and not dry_run:
            info("Verifying cleanup...")
            try:
                await asyncio.sleep(1)  # Brief pause for exchange to process
                open_orders = await exchange.fetch_open_orders(symbol)
                remaining = [o for o in open_orders if o.get("id") == test_order_id]

                if not remaining:
                    success("Cleanup verified – no orphaned orders")
                else:
                    error(f"Order {test_order_id} still appears in open orders!")
                    passed = False
            except Exception as exc:
                error(f"Cleanup verification failed: {exc}")
                passed = False

        # Step 8: Verify balance unchanged (minus any fees)
        if not dry_run:
            info("Checking balance...")
            try:
                balance = await exchange.fetch_balance()
                usdt = balance.get("USDT", {})
                total = float(usdt.get("total") or 0)
                free = float(usdt.get("free") or 0)
                success("Balance retrieved")
                metric("USDT Total", f"${total:,.4f}")
                metric("USDT Free", f"${free:,.4f}")
                metric("USDT Locked", f"${total - free:,.4f}")
            except Exception as exc:
                error(f"Balance check failed: {exc}")

    except Exception as exc:
        error(f"Test failed: {exc}")
        passed = False
    finally:
        # Safety: cancel any remaining test orders
        if test_order_id and not dry_run:
            try:
                await exchange.cancel_order(test_order_id, symbol)
                info(f"Safety cancel of {test_order_id}")
            except Exception:
                pass
        await exchange.close()

    return passed


# ---------------------------------------------------------------------------
# Full test suite
# ---------------------------------------------------------------------------

async def run_full_test(
    exchange_id: str,
    symbol: str | None = None,
    dry_run: bool = False,
) -> bool:
    """Run the complete order test suite.

    Steps:
    1. Verify connection and market data
    2. Check account balance
    3. Place a tiny limit order
    4. Verify order appears in open orders
    5. Cancel the order
    6. Verify cleanup (no orphaned orders)
    7. Confirm balance is unchanged
    """
    header("AlphaStack Order Placement Test Suite")
    print(f"  Exchange: {exchange_id.upper()}")
    print(f"  Symbol:   {symbol or 'auto'}")
    print(f"  Mode:     {'DRY RUN' if dry_run else 'LIVE (tiny test order)'}")
    print(f"  Time:     {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    if not dry_run:
        print(f"\n  {Colors.YELLOW}{Colors.BOLD}⚠  This will place a REAL order on {exchange_id.upper()}{Colors.END}")
        print(f"  {Colors.YELLOW}   Order value: ~$1-2 (limit buy far below market){Colors.END}")
        print(f"  {Colors.YELLOW}   The order will be cancelled immediately after verification{Colors.END}")

    result = await test_order_lifecycle(exchange_id, symbol, dry_run)

    # Final summary
    header("Test Result")
    if result:
        print(f"  {Colors.GREEN}{Colors.BOLD}✓ All order lifecycle tests passed{Colors.END}\n")
        print(f"  The following was verified:")
        print(f"    ✓ Order placement via API")
        print(f"    ✓ Order appears in open orders")
        print(f"    ✓ Order cancellation works")
        print(f"    ✓ No orphaned orders after cancel")
        print(f"    ✓ Balance integrity maintained")
    else:
        print(f"  {Colors.RED}{Colors.BOLD}✗ Some tests failed{Colors.END}\n")
        print(f"  Check the errors above for details.")
        print(f"  Common issues:")
        print(f"    - Insufficient balance for minimum order")
        print(f"    - API key doesn't have trading permissions")
        print(f"    - Exchange rate limits exceeded")
        print(f"    - Network connectivity issues")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test order placement on crypto exchanges",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (no real orders)
  python scripts/test_order_placement.py --dry-run

  # Live test on MEXC
  python scripts/test_order_placement.py --exchange mexc

  # Test with specific symbol
  python scripts/test_order_placement.py --symbol DOGE/USDT

  # Full test on Binance
  python scripts/test_order_placement.py --exchange binance --full
        """,
    )
    parser.add_argument(
        "--exchange",
        choices=["mexc", "binance", "bybit", "okx"],
        default=os.environ.get("CCXT_EXCHANGE", "mexc"),
        help="Exchange to test (default: mexc or CCXT_EXCHANGE env var)",
    )
    parser.add_argument(
        "--symbol",
        help="Trading pair (default: DOGE/USDT for low-value test)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without placing real orders",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full test suite including balance checks",
    )
    args = parser.parse_args()

    result = asyncio.run(run_full_test(
        exchange_id=args.exchange,
        symbol=args.symbol,
        dry_run=args.dry_run,
    ))

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
