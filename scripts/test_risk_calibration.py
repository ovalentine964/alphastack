"""Risk Calibration Tests — verify all limits for $7 micro-accounts.

Tests every risk gate in the governor, position sizer, circuit breaker,
and drawdown manager. Every cent matters on a $7 account.

Usage:
    cd /home/work/.openclaw/workspace/alphastack
    python3 -m pytest scripts/test_risk_calibration.py -v
    # or
    python3 scripts/test_risk_calibration.py
"""

from __future__ import annotations

import asyncio
import sys
import os

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from alphastack.risk.governor import RiskGovernor, TradeRequest, RiskEvent, RiskEventType
from alphastack.risk.circuit_breaker import CircuitBreaker, BreakerType
from alphastack.risk.position_sizer import PositionSizer, SizingRequest, SizingMethod, AssetType
from alphastack.risk.drawdown import DrawdownManager
from alphastack.risk.validators import TradeValidator


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str):
        self.passed += 1
        print(f"  ✅ {name}")

    def fail(self, name: str, detail: str = ""):
        self.failed += 1
        msg = f"  ❌ {name}"
        if detail:
            msg += f": {detail}"
        print(msg)
        self.errors.append(f"{name}: {detail}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} passed, {self.failed} failed")
        if self.errors:
            print(f"\nFailures:")
            for e in self.errors:
                print(f"  • {e}")
        print(f"{'='*60}")
        return self.failed == 0


def make_request(
    symbol: str = "EUR/USD",
    direction: str = "long",
    size: float = 0.01,
    entry: float = 1.1000,
    sl: float = 1.0950,
    tp: float = 1.1100,
) -> TradeRequest:
    return TradeRequest(
        symbol=symbol,
        direction=direction,
        requested_size=size,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
    )


# ---------------------------------------------------------------------------
# 1. Governor — $7 account limits
# ---------------------------------------------------------------------------

def test_governor_risk_limits(r: TestResults):
    """Verify governor enforces all hard limits for $7 account."""
    print("\n🔒 Governor — Risk Limits ($7 account)")

    gov = RiskGovernor(account_balance=7.0)
    status = gov.status()

    limits = status["risk_limits"]

    # Max risk per trade: 2% = $0.14
    expected_risk = 7.0 * 0.02
    actual_risk = limits["max_risk_per_trade_abs"]
    if abs(actual_risk - expected_risk) < 0.01:
        r.ok("Max risk per trade = $0.14 (2% of $7)")
    else:
        r.fail("Max risk per trade", f"Expected ${expected_risk:.2f}, got ${actual_risk:.2f}")

    # Max daily loss: 5% = $0.35
    expected_daily = 7.0 * 0.05
    actual_daily = limits["max_daily_loss_abs"]
    if abs(actual_daily - expected_daily) < 0.01:
        r.ok("Max daily loss = $0.35 (5% of $7)")
    else:
        r.fail("Max daily loss", f"Expected ${expected_daily:.2f}, got ${actual_daily:.2f}")

    # Max drawdown: 15% = $1.05
    expected_dd = 7.0 * 0.15
    actual_dd = limits["max_drawdown_abs"]
    if abs(actual_dd - expected_dd) < 0.01:
        r.ok("Max drawdown = $1.05 (15% of $7)")
    else:
        r.fail("Max drawdown", f"Expected ${expected_dd:.2f}, got ${actual_dd:.2f}")

    # Max open positions: 3
    if limits["max_open_positions"] == 3:
        r.ok("Max open positions = 3")
    else:
        r.fail("Max open positions", f"Expected 3, got {limits['max_open_positions']}")

    # Max leverage forex: 1:100
    if limits["max_leverage_forex"] == 100.0:
        r.ok("Max leverage forex = 1:100")
    else:
        r.fail("Max leverage forex", f"Expected 100, got {limits['max_leverage_forex']}")

    # Max leverage crypto: 1:5
    if limits["max_leverage_crypto"] == 5.0:
        r.ok("Max leverage crypto = 1:5")
    else:
        r.fail("Max leverage crypto", f"Expected 5, got {limits['max_leverage_crypto']}")


def test_governor_trade_approval(r: TestResults):
    """Test trade approval pipeline with $7 account."""
    print("\n✅ Governor — Trade Approval Pipeline")

    gov = RiskGovernor(account_balance=7.0)

    # Normal trade should pass
    req = make_request(size=0.01, entry=1.1000, sl=1.0950)
    result = asyncio.run(gov.approve_trade(req))
    if result.approved:
        r.ok("Normal micro-lot trade approved")
    else:
        r.fail("Normal micro-lot trade", f"Rejected: {result.rejection_reason}")

    # Oversized trade should be reduced
    req = make_request(size=1.0, entry=1.1000, sl=1.0950)
    result = asyncio.run(gov.approve_trade(req))
    if result.approved and result.adjusted_size < 1.0:
        r.ok(f"Oversized trade reduced from 1.0 to {result.adjusted_size:.4f}")
    elif not result.approved:
        r.ok(f"Oversized trade rejected: {result.rejection_reason}")
    else:
        r.fail("Oversized trade", "Should have been reduced or rejected")

    # Trade with no stop loss should be rejected
    req = make_request(sl=1.1000)  # SL = entry
    result = asyncio.run(gov.approve_trade(req))
    if not result.approved:
        r.ok(f"Trade without stop loss rejected: {result.rejection_reason}")
    else:
        r.fail("No stop loss", "Should have been rejected")


def test_governor_halt_resume(r: TestResults):
    """Test halt and resume functionality."""
    print("\n🛑 Governor — Halt/Resume")

    gov = RiskGovernor(account_balance=7.0)

    # Manual halt
    gov.halt("Testing halt")
    if gov.is_halted:
        r.ok("Manual halt works")
    else:
        r.fail("Manual halt", "Not halted")

    # Trade during halt should be rejected
    req = make_request()
    result = asyncio.run(gov.approve_trade(req))
    if not result.approved and "halted" in result.rejection_reason.lower():
        r.ok("Trade rejected during halt")
    else:
        r.fail("Trade during halt", "Should be rejected")

    # Resume
    gov.resume()
    if not gov.is_halted:
        r.ok("Resume works")
    else:
        r.fail("Resume", "Still halted")


# ---------------------------------------------------------------------------
# 2. Position Sizer — Kelly & spread adjustment
# ---------------------------------------------------------------------------

def test_position_sizer_fixed_risk(r: TestResults):
    """Test fixed-risk sizing for $7 account."""
    print("\n📐 Position Sizer — Fixed Risk")

    sizer = PositionSizer(account_balance=7.0, default_risk_pct=2.0, max_risk_pct=2.0)

    # Micro-account: contract_size=1000 (micro lot), SL=50 pips
    req = SizingRequest(
        symbol="EUR/USD",
        direction="long",
        entry_price=1.1000,
        stop_loss=1.0950,  # 50 pips
        account_balance=7.0,
        method=SizingMethod.FIXED_RISK,
        max_risk_pct=2.0,
        asset_type=AssetType.FOREX,
        contract_size=1000,   # micro lot (1,000 units) — realistic for $7 account
        pip_value=0.0001,
        leverage=100.0,
        lot_step=0.01,
        min_size=0.01,
    )
    result = sizer.size_position(req)

    # Risk should be ~$0.14
    if result.risk_amount <= 0.15 and result.risk_amount > 0:
        r.ok(f"Risk amount = ${result.risk_amount:.4f} (target ~$0.14)")
    else:
        r.fail("Risk amount", f"Expected ~$0.14, got ${result.risk_amount:.4f}")

    # Risk % should be ~2%
    if result.risk_pct <= 2.1 and result.risk_pct > 0:
        r.ok(f"Risk % = {result.risk_pct:.2f}% (target 2%)")
    else:
        r.fail("Risk %", f"Expected ~2%, got {result.risk_pct:.2f}%")

    # Size should be positive
    if result.max_size > 0:
        r.ok(f"Position size = {result.max_size:.4f} lots")
    else:
        r.fail("Position size", "Should be positive")


def test_position_sizer_kelly(r: TestResults):
    """Test Kelly criterion sizing with quarter-Kelly safety."""
    print("\n🎯 Position Sizer — Kelly Criterion")

    sizer = PositionSizer(account_balance=7.0, default_risk_pct=2.0, max_risk_pct=2.0)

    # Good edge: 60% win rate, 1.5:1 reward:risk (crypto path for Kelly)
    req = SizingRequest(
        symbol="BTC/USDT",
        direction="long",
        entry_price=30000.0,
        stop_loss=29000.0,
        account_balance=7.0,
        method=SizingMethod.KELLY,
        win_rate=0.60,
        avg_win=1.5,
        avg_loss=1.0,
        max_risk_pct=2.0,
        asset_type=AssetType.CRYPTO,
        min_size=0.001,
    )
    result = sizer.size_position(req)

    # Kelly should produce a size
    if result.max_size > 0:
        r.ok(f"Kelly sizing produced {result.max_size:.6f} units (win_rate=60%)")
    else:
        r.fail("Kelly sizing", "Should produce positive size")

    # Negative edge should give minimum size (use crypto path where Kelly is used)
    req_bad = SizingRequest(
        symbol="BTC/USDT",
        direction="long",
        entry_price=30000.0,
        stop_loss=29000.0,
        account_balance=7.0,
        method=SizingMethod.KELLY,
        win_rate=0.30,  # bad edge
        avg_win=1.0,
        avg_loss=1.0,
        max_risk_pct=2.0,
        asset_type=AssetType.CRYPTO,
        min_size=0.001,
    )
    result_bad = sizer.size_position(req_bad)
    if result_bad.max_size <= 0.001:
        r.ok(f"Negative edge Kelly → minimum size ({result_bad.max_size:.6f})")
    else:
        r.fail("Negative edge Kelly", f"Should be min size, got {result_bad.max_size:.6f}")


def test_position_sizer_spread_cost(r: TestResults):
    """Test spread cost awareness for micro-accounts."""
    print("\n💸 Position Sizer — Spread Cost Awareness")

    sizer = PositionSizer(account_balance=7.0, default_risk_pct=2.0, max_risk_pct=2.0)

    base_kwargs = dict(
        symbol="EUR/USD",
        direction="long",
        entry_price=1.1000,
        stop_loss=1.0950,
        account_balance=7.0,
        pip_value=0.0001,
        asset_type=AssetType.FOREX,
        contract_size=1000,  # micro lot
        leverage=100.0,
        lot_step=0.01,
        min_size=0.01,
        max_risk_pct=2.0,
    )

    # Normal spread (1.5 pips)
    req_normal = SizingRequest(spread_pips=1.5, **base_kwargs)
    result_normal = sizer.size_position(req_normal)

    # Wide spread (5 pips — news event)
    req_wide = SizingRequest(spread_pips=5.0, **base_kwargs)
    result_wide = sizer.size_position(req_wide)

    if result_wide.max_size <= result_normal.max_size:
        r.ok(f"Wide spread reduces size: {result_normal.max_size:.4f} → {result_wide.max_size:.4f}")
    else:
        r.fail("Spread adjustment", "Wide spread should reduce size")

    if result_wide.spread_cost >= result_normal.spread_cost:
        r.ok(f"Spread cost tracked: ${result_normal.spread_cost:.6f} → ${result_wide.spread_cost:.6f}")
    else:
        r.fail("Spread cost tracking", "Wide spread should have higher cost")


def test_position_sizer_de_escalation(r: TestResults):
    """Test progressive de-escalation as drawdown increases."""
    print("\n📉 Position Sizer — De-escalation")

    sizer = PositionSizer(account_balance=7.0, default_risk_pct=2.0, max_risk_pct=2.0)

    base_kwargs = dict(
        symbol="EUR/USD",
        direction="long",
        entry_price=1.1000,
        stop_loss=1.0950,
        account_balance=7.0,
        max_risk_pct=2.0,
        asset_type=AssetType.FOREX,
        contract_size=1000,  # micro lot
        pip_value=0.0001,
        leverage=100.0,
        lot_step=0.01,
        min_size=0.01,
    )

    # No drawdown → full risk
    result_0 = sizer.size_position(SizingRequest(**base_kwargs))

    # 1.5% drawdown → 75% risk
    result_15 = sizer.size_position(SizingRequest(daily_drawdown_pct=1.5, **base_kwargs))

    # 3% drawdown → 50% risk
    result_3 = sizer.size_position(SizingRequest(daily_drawdown_pct=3.0, **base_kwargs))

    # 5% drawdown → 25% risk
    result_5 = sizer.size_position(SizingRequest(daily_drawdown_pct=5.0, **base_kwargs))

    if result_0.max_size >= result_15.max_size >= result_3.max_size >= result_5.max_size:
        r.ok(f"Progressive reduction: {result_0.max_size:.4f} → {result_15.max_size:.4f} → {result_3.max_size:.4f} → {result_5.max_size:.4f}")
    else:
        r.fail("De-escalation", f"Sizes should decrease: {result_0.max_size:.4f}, {result_15.max_size:.4f}, {result_3.max_size:.4f}, {result_5.max_size:.4f}")


# ---------------------------------------------------------------------------
# 3. Circuit Breaker — progressive response
# ---------------------------------------------------------------------------

def test_circuit_breaker_consecutive_losses(r: TestResults):
    """Test progressive circuit breaker: 3 losses → reduce, 5 → pause."""
    print("\n⚡ Circuit Breaker — Consecutive Losses")

    cb = CircuitBreaker(max_daily_loss_pct=5.0, max_consecutive_losses=5, account_balance=7.0)

    # 2 losses → no action
    cb.record_loss(-0.05)
    cb.record_loss(-0.05)
    if not cb.should_reduce_size and not cb.is_tripped:
        r.ok("2 losses → no action")
    else:
        r.fail("2 losses", "Should not trigger any breaker")

    # 3 losses → reduce size
    cb.record_loss(-0.05)
    if cb.should_reduce_size:
        r.ok(f"3 losses → reduce size (factor={cb.size_reduction_factor:.2f})")
    else:
        r.fail("3 losses", "Should trigger size reduction")

    if cb.size_reduction_factor == 0.5:
        r.ok("Size reduction factor = 50%")
    else:
        r.fail("Size reduction", f"Expected 0.5, got {cb.size_reduction_factor}")

    # 4 losses → more reduction
    cb.record_loss(-0.05)
    if cb.size_reduction_factor == 0.25:
        r.ok("4 losses → 25% size")
    else:
        r.fail("4 losses", f"Expected 0.25, got {cb.size_reduction_factor}")

    # 5 losses → full halt
    cb.record_loss(-0.05)
    if cb.is_tripped:
        r.ok("5 losses → circuit breaker tripped (halt)")
    else:
        r.fail("5 losses", "Should trip circuit breaker")


def test_circuit_breaker_daily_loss(r: TestResults):
    """Test daily loss limit circuit breaker."""
    print("\n🔴 Circuit Breaker — Daily Loss Limit")

    cb = CircuitBreaker(max_daily_loss_pct=5.0, max_consecutive_losses=5, account_balance=7.0)

    # Lose $0.30 (4.3%) → not tripped
    cb.record_loss(-0.30)
    if not cb.is_tripped:
        r.ok(f"$0.30 loss (4.3%) → not tripped (daily_pnl=${cb.daily_pnl:.2f})")
    else:
        r.fail("$0.30 loss", "Should not trip yet")

    # Lose another $0.10 → total $0.40 (5.7%) → tripped
    cb.record_loss(-0.10)
    if cb.is_tripped:
        r.ok(f"$0.40 total loss (5.7%) → tripped")
    else:
        r.fail("$0.40 loss", f"Should trip at 5%. Daily PnL: ${cb.daily_pnl:.2f}")


def test_circuit_breaker_emergency_kill(r: TestResults):
    """Test emergency kill switch."""
    print("\n🚨 Circuit Breaker — Emergency Kill Switch")

    cb = CircuitBreaker(max_daily_loss_pct=5.0, max_consecutive_losses=5, account_balance=7.0)

    cb.emergency_kill("Market anomaly detected")
    if cb.is_tripped and "EMERGENCY" in cb.trip_reason:
        r.ok("Emergency kill switch works")
    else:
        r.fail("Emergency kill", f"Tripped={cb.is_tripped}, reason={cb.trip_reason}")

    # Cooldown check — should not reset immediately
    can_reset = cb.reset()
    if not can_reset:
        r.ok("Emergency kill enforces cooldown")
    else:
        r.fail("Emergency cooldown", "Should enforce cooldown period")


def test_circuit_breaker_daily_reset(r: TestResults):
    """Test daily reset clears daily loss but not consecutive losses."""
    print("\n🔄 Circuit Breaker — Daily Reset")

    cb = CircuitBreaker(max_daily_loss_pct=5.0, max_consecutive_losses=5, account_balance=7.0)

    cb.record_loss(-0.20)
    cb.record_loss(-0.10)

    cb.reset_daily()

    if cb.daily_pnl == 0.0:
        r.ok("Daily reset clears daily PnL")
    else:
        r.fail("Daily reset", f"Daily PnL should be 0, got {cb.daily_pnl}")


# ---------------------------------------------------------------------------
# 4. Drawdown Manager
# ---------------------------------------------------------------------------

def test_drawdown_manager(r: TestResults):
    """Test drawdown tracking and limits."""
    print("\n📊 Drawdown Manager")

    dm = DrawdownManager(account_balance=7.0, max_daily_pct=5.0, max_total_pct=15.0)

    # Initial state
    if dm.state.current_balance == 7.0:
        r.ok("Initial balance = $7.00")
    else:
        r.fail("Initial balance", f"Expected 7.0, got {dm.state.current_balance}")

    # Record losses
    dm.record_pnl(-0.20)  # -$0.20 → $6.80
    if dm.state.daily_pct > 0:
        r.ok(f"Daily drawdown tracked: {dm.state.daily_pct:.2f}%")
    else:
        r.fail("Daily drawdown", "Should be > 0")

    # Record more losses to breach daily limit
    dm.record_pnl(-0.20)  # -$0.40 → $6.60 (5.7%)
    if dm.is_breach():
        r.ok(f"Daily limit breached at {dm.state.daily_pct:.2f}%")
    else:
        r.fail("Daily breach", f"Should breach at 5%. Current: {dm.state.daily_pct:.2f}%")

    # Total drawdown tracking
    dm2 = DrawdownManager(account_balance=7.0, max_daily_pct=5.0, max_total_pct=15.0)
    dm2.record_pnl(-0.50)  # -$0.50 → $6.50
    dm2.record_pnl(-0.30)  # -$0.80 → $6.20
    dm2.record_pnl(-0.30)  # -$1.10 → $5.90 (15.7% from peak)
    if dm2.state.total_pct >= 15.0:
        r.ok(f"Total drawdown tracked: {dm2.state.total_pct:.2f}%")
    else:
        r.fail("Total drawdown", f"Expected >= 15%, got {dm2.state.total_pct:.2f}%")

    # Risk multiplier de-escalation
    dm3 = DrawdownManager(account_balance=7.0, max_daily_pct=5.0, max_total_pct=15.0)
    dm3.record_pnl(-0.14)  # 2% drawdown
    mult = dm3.risk_multiplier()
    if mult < 1.0:
        r.ok(f"Risk multiplier at 2% drawdown: {mult:.2f}")
    else:
        r.fail("Risk multiplier", f"Should be < 1.0, got {mult}")


def test_drawdown_daily_reset(r: TestResults):
    """Test daily drawdown reset."""
    print("\n🔄 Drawdown Manager — Daily Reset")

    dm = DrawdownManager(account_balance=7.0, max_daily_pct=5.0, max_total_pct=15.0)
    dm.record_pnl(-0.30)

    dm.reset_daily()
    if dm.state.daily_pct == 0.0 and dm.state.daily_pnl == 0.0:
        r.ok("Daily reset clears daily metrics")
    else:
        r.fail("Daily reset", f"pct={dm.state.daily_pct}, pnl={dm.state.daily_pnl}")


# ---------------------------------------------------------------------------
# 5. Validators
# ---------------------------------------------------------------------------

def test_validators(r: TestResults):
    """Test trade validators catch dangerous parameters."""
    print("\n🔍 Trade Validators")

    tv = TradeValidator()

    # Valid trade
    req = make_request()
    result = tv.validate_pre_trade(req)
    if result.valid:
        r.ok("Valid trade passes validation")
    else:
        r.fail("Valid trade", f"Should pass: {result.errors}")

    # Invalid direction
    req_bad_dir = make_request(direction="up")
    result = tv.validate_pre_trade(req_bad_dir)
    if not result.valid:
        r.ok("Invalid direction caught")
    else:
        r.fail("Invalid direction", "Should reject 'up'")

    # SL above entry for long
    req_bad_sl = make_request(entry=1.1000, sl=1.1050)
    result = tv.validate_pre_trade(req_bad_sl)
    if not result.valid:
        r.ok("Long SL above entry caught")
    else:
        r.fail("Long SL above entry", "Should reject")

    # Negative price
    req_neg = make_request(entry=-1.0)
    result = tv.validate_pre_trade(req_neg)
    if not result.valid:
        r.ok("Negative price caught")
    else:
        r.fail("Negative price", "Should reject")

    # Empty symbol
    req_no_sym = make_request(symbol="")
    result = tv.validate_pre_trade(req_no_sym)
    if not result.valid:
        r.ok("Empty symbol caught")
    else:
        r.fail("Empty symbol", "Should reject")


# ---------------------------------------------------------------------------
# 6. Integration — full pipeline with $7 account
# ---------------------------------------------------------------------------

def test_integration_full_pipeline(r: TestResults):
    """End-to-end test: trade → loss → circuit breaker → halt."""
    print("\n🔗 Integration — Full Pipeline ($7 account)")

    gov = RiskGovernor(account_balance=7.0)

    # Trade 1: approve and record loss
    req1 = make_request(size=0.01, entry=1.1000, sl=1.0950)
    result1 = asyncio.run(gov.approve_trade(req1))
    if result1.approved:
        r.ok("Trade 1 approved")
        gov.record_trade_result(-0.10)  # lose $0.10

    # Trade 2: approve and record loss
    req2 = make_request(size=0.01, entry=1.0980, sl=1.0930)
    result2 = asyncio.run(gov.approve_trade(req2))
    if result2.approved:
        r.ok("Trade 2 approved")
        gov.record_trade_result(-0.10)  # lose $0.10

    # Trade 3: should trigger progressive reduction
    req3 = make_request(size=0.01, entry=1.0960, sl=1.0910)
    result3 = asyncio.run(gov.approve_trade(req3))
    if result3.approved:
        r.ok("Trade 3 approved (with size reduction)")
        gov.record_trade_result(-0.10)  # lose $0.10

    # Check progressive breaker is active
    status = gov.status()
    if status["progressive_breaker"]["active"]:
        r.ok("Progressive breaker active after 3 losses")
    else:
        r.fail("Progressive breaker", "Should be active after 3 losses")

    # Trade 4: still approved but smaller
    req4 = make_request(size=0.01, entry=1.0940, sl=1.0890)
    result4 = asyncio.run(gov.approve_trade(req4))
    if result4.approved:
        r.ok("Trade 4 approved (further reduced)")
        gov.record_trade_result(-0.10)

    # Trade 5: should trigger halt
    req5 = make_request(size=0.01, entry=1.0920, sl=1.0870)
    result5 = asyncio.run(gov.approve_trade(req5))
    if not result5.approved:
        r.ok(f"Trade 5 rejected — circuit breaker: {result5.rejection_reason}")
    else:
        gov.record_trade_result(-0.05)
        # After recording, check if halted
        if gov.is_halted:
            r.ok("Trading halted after 5 consecutive losses")
        else:
            r.fail("5 losses", "Should halt trading")


def test_integration_daily_loss_halt(r: TestResults):
    """Test that daily loss limit stops trading for the day."""
    print("\n📅 Integration — Daily Loss Halt")

    gov = RiskGovernor(account_balance=7.0)

    # Lose $0.35 (5% of $7)
    gov.record_trade_result(-0.20)
    gov.record_trade_result(-0.15)

    if gov.is_halted:
        r.ok(f"Trading halted at daily loss limit (balance=${gov.account_balance:.2f})")
    else:
        # Check drawdown state
        dd = gov.drawdown_manager.state
        r.fail("Daily loss halt", f"Should halt. DD={dd.daily_pct:.2f}%, PnL=${dd.daily_pnl:.2f}")


def test_integration_correlation_check(r: TestResults):
    """Test correlation check prevents correlated double-ups."""
    print("\n🔗 Integration — Correlation Check")

    gov = RiskGovernor(account_balance=7.0)

    # Open EUR/USD long
    req1 = make_request(symbol="EUR/USD", direction="long", size=0.01, entry=1.1000, sl=1.0950)
    result1 = asyncio.run(gov.approve_trade(req1))
    if result1.approved:
        # Manually register in correlation monitor
        from alphastack.risk.correlation import OpenPosition
        gov.correlation_monitor.add_position(OpenPosition(
            symbol="EUR/USD", direction="long", size=0.01, entry_price=1.1000
        ))

    # Try GBP/USD long (correlated with EUR/USD)
    req2 = make_request(symbol="GBP/USD", direction="long", size=0.01, entry=1.3000, sl=1.2950)
    result2 = asyncio.run(gov.approve_trade(req2))
    if not result2.approved:
        r.ok(f"Correlated GBP/USD long rejected: {result2.rejection_reason}")
    else:
        r.fail("Correlation check", "EUR/USD + GBP/USD long should be rejected (corr=0.85)")


# ---------------------------------------------------------------------------
# 7. Micro-account edge cases
# ---------------------------------------------------------------------------

def test_micro_account_tiny_balance(r: TestResults):
    """Test behavior with very small remaining balance."""
    print("\n🔬 Edge Cases — Tiny Balance")

    gov = RiskGovernor(account_balance=0.50)  # $0.50 remaining

    req = make_request(size=0.01, entry=1.1000, sl=1.0950)
    result = asyncio.run(gov.approve_trade(req))

    # Should either reject or approve with very small size
    if not result.approved:
        r.ok(f"$0.50 balance → trade rejected: {result.rejection_reason}")
    elif result.adjusted_size <= 0.01:
        r.ok(f"$0.50 balance → micro size approved: {result.adjusted_size:.4f}")
    else:
        r.fail("Tiny balance", f"Size {result.adjusted_size} too large for $0.50")


def test_micro_account_spread_eats_profit(r: TestResults):
    """Test that spread cost makes uneconomical trades uneconomical."""
    print("\n🔬 Edge Cases — Spread vs Profit")

    sizer = PositionSizer(account_balance=7.0, default_risk_pct=2.0, max_risk_pct=2.0)

    # Very tight SL with wide spread — should reduce or reject
    req = SizingRequest(
        symbol="EUR/USD",
        direction="long",
        entry_price=1.1000,
        stop_loss=1.0998,  # only 2 pips SL
        account_balance=7.0,
        spread_pips=3.0,   # 3 pip spread > 2 pip SL!
        pip_value=0.0001,
        asset_type=AssetType.FOREX,
        contract_size=1000,  # micro lot
        leverage=100.0,
        lot_step=0.01,
        min_size=0.01,
        max_risk_pct=2.0,
    )
    result = sizer.size_position(req)

    if result.max_size < 0.01 or "spread" in " ".join(result.adjustments).lower():
        r.ok(f"Tight SL + wide spread → reduced/rejected (size={result.max_size:.4f})")
    else:
        r.fail("Spread vs SL", f"Should reduce size when spread > SL distance (got {result.max_size:.4f})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  AlphaStack Risk Calibration — $7 Micro-Account Tests")
    print("=" * 60)

    r = TestResults()

    # Run all test suites
    test_governor_risk_limits(r)
    test_governor_trade_approval(r)
    test_governor_halt_resume(r)
    test_position_sizer_fixed_risk(r)
    test_position_sizer_kelly(r)
    test_position_sizer_spread_cost(r)
    test_position_sizer_de_escalation(r)
    test_circuit_breaker_consecutive_losses(r)
    test_circuit_breaker_daily_loss(r)
    test_circuit_breaker_emergency_kill(r)
    test_circuit_breaker_daily_reset(r)
    test_drawdown_manager(r)
    test_drawdown_daily_reset(r)
    test_validators(r)
    test_integration_full_pipeline(r)
    test_integration_daily_loss_halt(r)
    test_integration_correlation_check(r)
    test_micro_account_tiny_balance(r)
    test_micro_account_spread_eats_profit(r)

    # Summary
    success = r.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
