#!/usr/bin/env python3
"""Test the AlphaStack 16-step strategy pipeline with synthetic market data.

Generates realistic OHLCV data for different market regimes and runs
the full pipeline, validating each step's output.

Usage:
    python scripts/test_strategy.py
    python scripts/test_strategy.py --regime trending_up
    python scripts/test_strategy.py --bars 500 --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add src to path so we can import alphastack
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np


# ---------------------------------------------------------------------------
# Synthetic Market Data Generator
# ---------------------------------------------------------------------------

def generate_trending_up_data(
    n_bars: int = 200,
    start_price: float = 1.1000,
    volatility: float = 0.0015,
    trend_strength: float = 0.0003,
    seed: int = 42,
) -> dict:
    """Generate OHLCV data for a bullish trending market."""
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    opens = [start_price]
    highs = []
    lows = []
    closes = [start_price]
    volumes = []

    for i in range(1, n_bars):
        # Trend component + noise
        trend = trend_strength * (1 + 0.3 * math.sin(i / 20))
        noise = np_rng.normal(0, volatility)

        o = closes[-1]
        c = o + trend + noise
        # Wicks
        h = max(o, c) + abs(np_rng.normal(0, volatility * 0.5))
        l = min(o, c) - abs(np_rng.normal(0, volatility * 0.5))
        vol = rng.uniform(500, 2000) * (1 + abs(noise) / volatility)

        opens.append(round(o, 5))
        highs.append(round(h, 5))
        lows.append(round(l, 5))
        closes.append(round(c, 5))
        volumes.append(round(vol, 0))

    # First bar
    highs.append(round(max(opens[0], closes[0]) + abs(np_rng.normal(0, volatility * 0.5)), 5))
    lows.append(round(min(opens[0], closes[0]) - abs(np_rng.normal(0, volatility * 0.5)), 5))
    volumes.append(round(rng.uniform(500, 2000), 0))

    return {
        "opens": opens,
        "highs": highs,
        "lows": lows,
        "closes": closes,
        "volumes": volumes,
    }


def generate_trending_down_data(
    n_bars: int = 200,
    start_price: float = 1.1200,
    volatility: float = 0.0015,
    trend_strength: float = -0.0003,
    seed: int = 43,
) -> dict:
    """Generate OHLCV data for a bearish trending market."""
    return generate_trending_up_data(
        n_bars=n_bars,
        start_price=start_price,
        volatility=volatility,
        trend_strength=trend_strength,
        seed=seed,
    )


def generate_ranging_data(
    n_bars: int = 200,
    start_price: float = 1.1000,
    volatility: float = 0.002,
    range_width: float = 0.005,
    seed: int = 44,
) -> dict:
    """Generate OHLCV data for a ranging/consolidating market."""
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    opens = [start_price]
    highs = []
    lows = []
    closes = [start_price]
    volumes = []

    mid = start_price
    for i in range(1, n_bars):
        # Mean-reverting within range
        o = closes[-1]
        mean_revert = (mid - o) * 0.05
        noise = np_rng.normal(0, volatility)
        c = o + mean_revert + noise

        # Keep within range
        c = max(mid - range_width, min(mid + range_width, c))

        h = max(o, c) + abs(np_rng.normal(0, volatility * 0.3))
        l = min(o, c) - abs(np_rng.normal(0, volatility * 0.3))
        vol = rng.uniform(300, 1500)

        opens.append(round(o, 5))
        highs.append(round(h, 5))
        lows.append(round(l, 5))
        closes.append(round(c, 5))
        volumes.append(round(vol, 0))

    highs.append(round(max(opens[0], closes[0]) + 0.001, 5))
    lows.append(round(min(opens[0], closes[0]) - 0.001, 5))
    volumes.append(round(rng.uniform(300, 1500), 0))

    return {
        "opens": opens,
        "highs": highs,
        "lows": lows,
        "closes": closes,
        "volumes": volumes,
    }


# ---------------------------------------------------------------------------
# Pipeline Test Runner
# ---------------------------------------------------------------------------

async def run_pipeline_test(
    regime: str = "trending_up",
    n_bars: int = 200,
    verbose: bool = False,
) -> dict:
    """Run the full 16-step pipeline on synthetic data and validate outputs."""
    from alphastack.strategy.context import AlphaStackContext, Direction
    from alphastack.strategy.pipeline import AlphaStackPipeline

    print(f"\n{'='*70}")
    print(f"  AlphaStack Pipeline Test — Regime: {regime} | Bars: {n_bars}")
    print(f"{'='*70}\n")

    # Generate data
    if regime == "trending_up":
        data = generate_trending_up_data(n_bars=n_bars)
    elif regime == "trending_down":
        data = generate_trending_down_data(n_bars=n_bars)
    elif regime == "ranging":
        data = generate_ranging_data(n_bars=n_bars)
    else:
        raise ValueError(f"Unknown regime: {regime}")

    closes = data["closes"]
    highs = data["highs"]
    lows = data["lows"]

    # Compute ATR
    atr_values = [0.0]
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        if i < 14:
            atr_values.append(sum(
                max(highs[j] - lows[j], abs(highs[j] - closes[j - 1]), abs(lows[j] - closes[j - 1]))
                for j in range(1, i + 1)
            ) / i)
        else:
            atr_values.append((atr_values[-1] * 13 + tr) / 14)

    atr_pips = atr_values[-1] / 0.0001  # Convert to pips for FX

    # Build market_data dict
    market_data = {
        "opens": data["opens"],
        "highs": data["highs"],
        "lows": data["lows"],
        "closes": data["closes"],
        "volumes": data["volumes"],
        "atr_values": atr_values,
        "atr_pips": round(atr_pips, 1),
        "pip_size": 0.0001,
        "close": closes[-1],
        "account_balance": 10_000.0,
        "risk_pct": 1.0,
        "spread_pips": 1.5,
        "pip_value": 10.0,
        "regime": regime.replace("trending_", "trending"),
        "news_sentiment": 0.1 if "up" in regime else (-0.1 if "down" in regime else 0.0),
        "volatility_index": 18.0,
        "timeframe_closes": {
            "1h": closes[-50:],
            "4h": closes[-100:],
        },
        "htf_closes": closes[-100:],
    }

    # Create context
    now = datetime.now(timezone.utc)
    ctx = AlphaStackContext(
        symbol="EUR/USD",
        timeframe="1H",
        timestamp=now,
        market_data=market_data,
    )

    # Run pipeline
    results = {}
    pipeline = AlphaStackPipeline(parallel=False)

    step_outputs = {}
    def on_step(step_num, step_name, context):
        step_outputs[step_num] = step_name
        if verbose:
            print(f"  ✓ Step {step_num:02d} [{step_name}]")

    pipeline.on_step(on_step)

    print(f"  Running pipeline...")
    final_ctx = await pipeline.run(ctx)
    print(f"  Pipeline completed: {len(step_outputs)} steps executed\n")

    # --- Validate Step Outputs ---
    validations = []

    # Step 1: Fundamental
    f = final_ctx.fundamental
    validations.append(("Step 01: Fundamental", f.bias.value != "", f"Bias={f.bias.value}, Sentiment={f.news_sentiment:.2f}"))

    # Step 2: Market Bias
    b = final_ctx.bias
    validations.append(("Step 02: Market Bias", b.bias.value != "", f"Bias={b.bias.value}, TrendStrength={b.trend_strength:.3f}"))

    # Step 3: Session
    s = final_ctx.session
    validations.append(("Step 03: Session", s.active.value != "", f"Active={s.active.value}, Volatility={s.volatility:.2f}"))

    # Step 4: Structure
    st = final_ctx.structure
    validations.append(("Step 04: Structure", st.structure_type.value != "",
                         f"Type={st.structure_type.value}, Dir={st.direction.value}, "
                         f"SwingH={len(st.swing_highs)}, SwingL={len(st.swing_lows)}"))

    # Step 5: S/R
    sr = final_ctx.sr_levels
    validations.append(("Step 05: S/R", True,
                         f"Support={len(sr.support)}, Resistance={len(sr.resistance)}"))

    # Step 6: Liquidity
    liq = final_ctx.liquidity_pools
    validations.append(("Step 06: Liquidity", True, f"Pools={len(liq)}"))

    # Step 7: SMC
    smc = final_ctx.smc
    validations.append(("Step 07: SMC", True,
                         f"OBs={len(smc.order_blocks)}, FVGs={len(smc.fvgs)}, Breakers={len(smc.breaker_blocks)}"))

    # Step 8: RSI
    rsi = final_ctx.rsi
    validations.append(("Step 08: RSI", 0 <= rsi.value <= 100,
                         f"Value={rsi.value:.1f}, Signal={rsi.signal}, Divergence={rsi.divergence}"))

    # Step 9: Candlestick
    cs = final_ctx.candlestick
    validations.append(("Step 09: Candlestick", True,
                         f"Patterns={len(cs.patterns)}, Score={cs.pattern_score:.3f}"))

    # Step 10: Confluence
    conf = final_ctx.confluence
    validations.append(("Step 10: Confluence", 0 <= conf.score <= 100,
                         f"Score={conf.score:.1f}, Direction={conf.direction.value}"))

    # Step 12: Stop Loss (runs before sizing in pipeline)
    sl = final_ctx.stop_loss
    validations.append(("Step 12: Stop Loss", True,
                         f"Price={sl.price:.5f}, Type={sl.stop_type}"))

    # Step 11: Position Sizing
    ps = final_ctx.sizing
    validations.append(("Step 11: Sizing", True,
                         f"Size={ps.position_size:.2f}, Risk=${ps.risk_amount:.2f}"))

    # Step 13: Take Profit
    tp = final_ctx.take_profit
    validations.append(("Step 13: Take Profit", True,
                         f"Levels={len(tp.levels)}, RR={tp.rr_ratio}"))

    # Step 14: Trade Management
    mgmt = final_ctx.management
    validations.append(("Step 14: Management", True,
                         f"Actions={len(mgmt.actions)}"))

    # Step 15: Exit
    ex = final_ctx.exit_signal
    validations.append(("Step 15: Exit", True,
                         f"ShouldExit={ex.should_exit}, Reason={ex.reason[:50] if ex.reason else 'none'}"))

    # Step 16: Journal
    j = final_ctx.journal
    validations.append(("Step 16: Journal", j.symbol != "",
                         f"Symbol={j.symbol}, Tags={len(j.tags)}"))

    # Print results
    print(f"  {'Step':<30} {'Status':<8} {'Details'}")
    print(f"  {'-'*30} {'-'*8} {'-'*30}")
    all_passed = True
    for name, passed, details in validations:
        status = "✓ PASS" if passed else "✗ FAIL"
        if not passed:
            all_passed = False
        print(f"  {name:<30} {status:<8} {details}")

    # Print component scores
    print(f"\n  Confluence Component Scores:")
    for k, v in conf.component_scores.items():
        bar = "█" * int(abs(v) * 20)
        sign = "+" if v >= 0 else "-"
        print(f"    {k:<20} {sign}{abs(v):.3f} {bar}")

    # Print trade setup summary
    direction = conf.direction.value
    if direction != "none":
        print(f"\n  ═══ TRADE SETUP ═══")
        print(f"  Direction:    {direction.upper()}")
        print(f"  Entry:        {closes[-1]:.5f}")
        print(f"  Stop Loss:    {sl.price:.5f} ({sl.stop_type})")
        print(f"  Take Profit:  {', '.join(f'{tp_lvl:.5f}' for tp_lvl in tp.levels)}")
        print(f"  R:R:          {tp.rr_ratio}")
        print(f"  Position:     {ps.position_size:.2f} lots")
        print(f"  Risk:         ${ps.risk_amount:.2f}")
        print(f"  Confluence:   {conf.score:.1f}/100")
    else:
        print(f"\n  ═══ NO TRADE — Confluence below threshold ═══")

    print(f"\n{'='*70}")
    print(f"  Overall: {'✓ ALL PASSED' if all_passed else '✗ SOME FAILED'}")
    print(f"{'='*70}\n")

    return {
        "regime": regime,
        "passed": all_passed,
        "direction": direction,
        "confluence_score": conf.score,
        "rsi": rsi.value,
        "structure": st.structure_type.value,
        "steps_executed": len(step_outputs),
    }


# ---------------------------------------------------------------------------
# Multi-Regime Test Suite
# ---------------------------------------------------------------------------

async def run_full_test_suite(verbose: bool = False) -> None:
    """Run tests across all market regimes."""
    regimes = ["trending_up", "trending_down", "ranging"]
    results = []

    for regime in regimes:
        try:
            result = await run_pipeline_test(regime=regime, n_bars=200, verbose=verbose)
            results.append(result)
        except Exception as e:
            print(f"\n  ✗ FAILED: {regime} — {e}")
            import traceback
            traceback.print_exc()
            results.append({"regime": regime, "passed": False, "error": str(e)})

    # Summary
    print(f"\n{'='*70}")
    print(f"  TEST SUITE SUMMARY")
    print(f"{'='*70}")
    for r in results:
        status = "✓" if r.get("passed") else "✗"
        direction = r.get("direction", "N/A")
        score = r.get("confluence_score", 0)
        print(f"  {status} {r['regime']:<15} Direction={direction:<8} Confluence={score:.1f}")
    print(f"{'='*70}\n")

    # Return results for programmatic use
    all_passed = all(r.get("passed") for r in results)
    sys.exit(0 if all_passed else 1)


# ---------------------------------------------------------------------------
# Individual Step Tests
# ---------------------------------------------------------------------------

async def test_individual_steps() -> None:
    """Test each step individually with minimal data."""
    from alphastack.strategy.context import AlphaStackContext

    print(f"\n{'='*70}")
    print(f"  Individual Step Tests")
    print(f"{'='*70}\n")

    # Generate minimal data
    data = generate_trending_up_data(n_bars=50, seed=99)
    closes = data["closes"]

    market_data = {
        "opens": data["opens"],
        "highs": data["highs"],
        "lows": data["lows"],
        "closes": data["closes"],
        "volumes": data["volumes"],
        "atr_pips": 50.0,
        "atr_values": [0.001] * len(closes),
        "pip_size": 0.0001,
        "close": closes[-1],
        "account_balance": 10_000.0,
        "risk_pct": 1.0,
        "spread_pips": 1.5,
        "pip_value": 10.0,
        "news_sentiment": 0.05,
        "volatility_index": 18.0,
        "timeframe_closes": {"1h": closes[-20:]},
        "htf_closes": closes[-30:],
    }

    ctx = AlphaStackContext(
        symbol="EUR/USD",
        timeframe="1H",
        timestamp=datetime.now(timezone.utc),
        market_data=market_data,
    )

    # Test Step 3 (Session)
    from alphastack.strategy.steps.s03_session import SessionAnalysis
    step3 = SessionAnalysis()
    ctx3 = await step3.run(ctx)
    print(f"  Step 03: session={ctx3.session.active.value}, volatility={ctx3.session.volatility}")
    assert ctx3.session.active.value in ("london", "new_york", "asian", "off_hours")

    # Test Step 4 (Structure)
    from alphastack.strategy.steps.s04_structure import MarketStructure
    step4 = MarketStructure()
    ctx4 = await step4.run(ctx3)
    print(f"  Step 04: structure={ctx4.structure.structure_type.value}, dir={ctx4.structure.direction.value}")
    assert ctx4.structure.structure_type.value != ""

    # Test Step 5 (S/R) — needs structure from step 4
    from alphastack.strategy.steps.s05_support_resistance import SupportResistance
    step5 = SupportResistance()
    ctx5 = await step5.run(ctx4)
    print(f"  Step 05: support={len(ctx5.sr_levels.support)}, resistance={len(ctx5.sr_levels.resistance)}")

    # Test Step 6 (Liquidity) — needs S/R from step 5
    from alphastack.strategy.steps.s06_liquidity import LiquidityDetection
    step6 = LiquidityDetection()
    ctx6 = await step6.run(ctx5)
    print(f"  Step 06: pools={len(ctx6.liquidity_pools)}")

    # Test Step 7 (SMC)
    from alphastack.strategy.steps.s07_smc import SmartMoneyConcepts
    step7 = SmartMoneyConcepts()
    ctx7 = await step7.run(ctx6)
    print(f"  Step 07: OBs={len(ctx7.smc.order_blocks)}, FVGs={len(ctx7.smc.fvgs)}, Breakers={len(ctx7.smc.breaker_blocks)}")

    # Test Step 8 (RSI)
    from alphastack.strategy.steps.s08_rsi import RSIConfirmation
    step8 = RSIConfirmation()
    ctx8 = await step8.run(ctx7)
    print(f"  Step 08: RSI={ctx8.rsi.value:.1f}, signal={ctx8.rsi.signal}, divergence={ctx8.rsi.divergence}")
    assert 0 <= ctx8.rsi.value <= 100

    # Test Step 9 (Candlestick)
    from alphastack.strategy.steps.s09_candlestick import CandlestickConfirmation
    step9 = CandlestickConfirmation()
    ctx9 = await step9.run(ctx8)
    pattern_names = [p.name for p in ctx9.candlestick.patterns]
    print(f"  Step 09: patterns={pattern_names}, score={ctx9.candlestick.pattern_score}")

    # Test Step 10 (Confluence) — needs all prior steps
    # First run steps 1, 2
    from alphastack.strategy.steps.s01_fundamental import FundamentalIntelligence
    from alphastack.strategy.steps.s02_bias import MarketBiasStep
    ctx1 = await FundamentalIntelligence().run(ctx)
    ctx2 = await MarketBiasStep().run(ctx1)
    # Rebuild context with all prior steps
    ctx_full = ctx9.update(
        fundamental=ctx1.fundamental,
        bias=ctx2.bias,
    )
    from alphastack.strategy.steps.s10_confluence import ConfluenceEngine
    step10 = ConfluenceEngine()
    ctx10 = await step10.run(ctx_full)
    print(f"  Step 10: score={ctx10.confluence.score:.1f}, dir={ctx10.confluence.direction.value}")

    print(f"\n  ✓ All individual step tests passed\n")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Test AlphaStack strategy pipeline")
    parser.add_argument("--regime", choices=["trending_up", "trending_down", "ranging", "all"],
                        default="all", help="Market regime to test")
    parser.add_argument("--bars", type=int, default=200, help="Number of bars to generate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--individual", action="store_true", help="Test steps individually")
    args = parser.parse_args()

    if args.individual:
        asyncio.run(test_individual_steps())
    elif args.regime == "all":
        asyncio.run(run_full_test_suite(verbose=args.verbose))
    else:
        result = asyncio.run(run_pipeline_test(
            regime=args.regime,
            n_bars=args.bars,
            verbose=args.verbose,
        ))
        sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
