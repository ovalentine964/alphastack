#!/usr/bin/env python3
"""Test script for LiveMarketFeed — connects to Binance (public, no API keys).

Streams live BTC/USDT and ETH/USDT prices for 30 seconds, demonstrating:
- Real-time WebSocket tick data from Binance
- Tick → candle aggregation (M1/M5/M15)
- Health monitoring
- Graceful shutdown

Usage::

    cd /home/work/.openclaw/workspace/alphastack
    python scripts/test_live_feed.py

No API keys required — uses Binance public market data endpoints.
"""

from __future__ import annotations

import asyncio
import signal
import sys
import time
from datetime import datetime, timezone

# Ensure the project src is on the path
sys.path.insert(0, "/home/work/.openclaw/workspace/alphastack/src")

from alphastack.data.live_feed import LiveFeedStatus, LiveMarketFeed
from alphastack.data.ingestion.market_data import Candle, CandleTimeframe, Tick


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EXCHANGE = "binance"
SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAMES = [CandleTimeframe.M1, CandleTimeframe.M5, CandleTimeframe.M15]
DURATION_S = 30  # How long to stream


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_DIM = "\033[2m"
_RED = "\033[91m"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _price_color(prev: float, current: float) -> str:
    if current > prev:
        return _GREEN
    elif current < prev:
        return _RED
    return _DIM


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

async def main() -> None:
    print(f"\n{_BOLD}{'=' * 60}{_RESET}")
    print(f"{_BOLD}  AlphaStack Live Data Feed — Binance Test{ _RESET}")
    print(f"{_BOLD}{'=' * 60}{_RESET}")
    print(f"  Exchange:  {_CYAN}{EXCHANGE}{_RESET}")
    print(f"  Symbols:   {_CYAN}{', '.join(SYMBOLS)}{_RESET}")
    print(f"  Timeframes:{_CYAN}{', '.join(tf.value for tf in TIMEFRAMES)}{_RESET}")
    print(f"  Duration:  {_CYAN}{DURATION_S}s{_RESET}")
    print(f"  API Keys:  {_GREEN}NOT REQUIRED (public data){_RESET}")
    print(f"{'=' * 60}\n")

    # State tracking for price change coloring
    prev_prices: dict[str, float] = {}
    tick_counts: dict[str, int] = {s: 0 for s in SYMBOLS}
    candle_counts: dict[str, dict[str, int]] = {
        s: {tf.value: 0 for tf in TIMEFRAMES} for s in SYMBOLS
    }

    # -- Tick callback ------------------------------------------------------
    async def on_tick(tick: Tick) -> None:
        symbol = tick.symbol
        tick_counts[symbol] = tick_counts.get(symbol, 0) + 1
        last_price = float(tick.last)
        prev = prev_prices.get(symbol, last_price)
        color = _price_color(prev, last_price)
        prev_prices[symbol] = last_price

        bid = float(tick.bid)
        ask = float(tick.ask)
        spread = ask - bid
        vol = float(tick.volume)

        # Print tick (throttled: every 5th tick per symbol to avoid spam)
        if tick_counts[symbol] % 5 == 0 or tick_counts[symbol] <= 3:
            print(
                f"  {_DIM}{_ts()}{_RESET} "
                f"{_BOLD}{symbol:<10}{_RESET} "
                f"Bid {color}{bid:>12,.2f}{_RESET}  "
                f"Ask {color}{ask:>12,.2f}{_RESET}  "
                f"Last {color}{last_price:>12,.2f}{_RESET}  "
                f"Spread {spread:>8,.2f}  "
                f"Vol {vol:>14,.1f}  "
                f"{_DIM}[tick #{tick_counts[symbol]}]{_RESET}"
            )

    # -- Candle callback ----------------------------------------------------
    def on_candle(candle: Candle) -> None:
        symbol = candle.symbol
        tf = candle.timeframe.value
        candle_counts[symbol][tf] = candle_counts.get(symbol, {}).get(tf, 0) + 1

        print(
            f"  {_YELLOW}🕯  CANDLE CLOSED{ _RESET}  "
            f"{_BOLD}{symbol:<10}{_RESET} "
            f"{_CYAN}{tf:<4}{_RESET}  "
            f"O {float(candle.open):>12,.2f}  "
            f"H {float(candle.high):>12,.2f}  "
            f"L {float(candle.low):>12,.2f}  "
            f"C {float(candle.close):>12,.2f}  "
            f"V {float(candle.volume):>14,.1f}  "
            f"ticks={candle.tick_count}"
        )

    # -- Create and start the feed ------------------------------------------
    feed = LiveMarketFeed(
        exchange_id=EXCHANGE,
        symbols=SYMBOLS,
        timeframes=TIMEFRAMES,
        validate_ticks=True,
    )

    feed.on_tick(on_tick)
    feed.on_candle(on_candle)

    print(f"{_CYAN}⏳ Connecting to {EXCHANGE}...{ _RESET}\n")

    try:
        await feed.start()
    except Exception as exc:
        print(f"\n{_RED}✗ Failed to connect: {exc}{_RESET}")
        print(f"  Make sure you have ccxt.pro installed:")
        print(f"  {_CYAN}pip install 'ccxt[pro]'{_RESET}\n")
        return

    print(f"{_GREEN}✓ Connected! Streaming live data...{ _RESET}\n")
    print(f"{_DIM}  (Showing every 5th tick per symbol to reduce noise){ _RESET}")
    print(f"{_DIM}  (Candle close events shown in full){ _RESET}\n")

    # -- Stream for DURATION_S seconds --------------------------------------
    start_time = time.monotonic()
    last_health_print = start_time

    try:
        while feed.is_streaming:
            elapsed = time.monotonic() - start_time
            remaining = DURATION_S - elapsed

            if remaining <= 0:
                print(f"\n{_YELLOW}⏱  {DURATION_S}s elapsed — stopping...{ _RESET}")
                break

            # Print health snapshot every 10 seconds
            now = time.monotonic()
            if now - last_health_print >= 10.0:
                health = feed.get_health()
                print(
                    f"\n  {_DIM}── Health ──{ _RESET}\n"
                    f"  {_DIM}Status: {health['status']}  "
                    f"Ticks: {health['tick_count']}  "
                    f"Candles: {health['candle_count']}  "
                    f"Errors: {health['error_count']}  "
                    f"Uptime: {health['uptime_seconds']}s  "
                    f"Stale: {health['is_stale']}{ _RESET}\n"
                )
                last_health_print = now

            await asyncio.sleep(0.5)

    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        print(f"\n{_YELLOW}⚡ Interrupted by user{ _RESET}")

    # -- Shutdown -----------------------------------------------------------
    await feed.stop()

    # -- Summary ------------------------------------------------------------
    print(f"\n{_BOLD}{'=' * 60}{_RESET}")
    print(f"{_BOLD}  Session Summary{ _RESET}")
    print(f"{'=' * 60}")
    print(f"  Duration:     {feed.uptime_seconds:.1f}s")
    print(f"  Total Ticks:  {feed.tick_count}")
    print(f"  Total Candles:{feed.candle_count}")
    print(f"  Errors:       {feed.error_count}")
    print()
    for symbol in SYMBOLS:
        tc = tick_counts.get(symbol, 0)
        print(f"  {symbol:<12} ticks={tc}", end="")
        for tf in TIMEFRAMES:
            cc = candle_counts.get(symbol, {}).get(tf.value, 0)
            print(f"  {tf.value}={cc}", end="")
        last = feed.get_latest_tick(symbol)
        if last:
            print(f"  last={float(last.last):,.2f}", end="")
        print()

    # Show latest candles
    print(f"\n{_BOLD}  Latest Closed Candles:{_RESET}")
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            candle = feed.get_latest_candle(symbol, tf)
            if candle:
                print(
                    f"  {symbol} {tf.value}: "
                    f"O={float(candle.open):,.2f} H={float(candle.high):,.2f} "
                    f"L={float(candle.low):,.2f} C={float(candle.close):,.2f} "
                    f"V={float(candle.volume):,.1f} ticks={candle.tick_count}"
                )

    print(f"\n{_GREEN}✓ Test complete!{ _RESET}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    loop = asyncio.new_event_loop()

    def _handle_signal(sig: int, frame: object) -> None:
        print(f"\n{_YELLOW}⚡ Signal {sig} received — shutting down...{ _RESET}")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print(f"\n{_YELLOW}⚡ Keyboard interrupt{ _RESET}")
    finally:
        loop.close()
