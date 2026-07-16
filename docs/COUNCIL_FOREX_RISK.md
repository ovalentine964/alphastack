# AlphaStack Council — FOREX Risk Integration Analysis

**Prepared by:** Risk Specialist  
**Date:** 2026-07-16  
**Status:** Risk Gap Analysis & Recommendations  
**Review Target:** `FOREX_MT5_INTEGRATION.md` + Current Risk Stack

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Risk Stack Assessment](#2-current-risk-stack-assessment)
3. [Risk Gap Analysis](#3-risk-gap-analysis)
4. [New Risk Types Required](#4-new-risk-types-required)
5. [Position Sizing: Lots vs Quantity](#5-position-sizing-lots-vs-quantity)
6. [Circuit Breaker Thresholds: Forex vs Crypto](#6-circuit-breaker-thresholds-forex-vs-crypto)
7. [Cross-Broker Risk](#7-cross-broker-risk)
8. [Regulatory Considerations](#8-regulatory-considerations)
9. [Recommended Risk Parameters for Forex](#9-recommended-risk-parameters-for-forex)
10. [MUST-Build Before Forex Go-Live](#10-must-build-before-forex-go-live)
11. [Implementation Priority](#11-implementation-priority)

---

## 1. Executive Summary

**Verdict: Current risk management is crypto-only. It does NOT support forex-specific risks.**

The existing risk stack (circuit breaker, drawdown, position sizer, exposure, governor, validators) was designed for crypto spot trading on Binance. It has a solid foundation — the 7-gate approval pipeline in `RiskGovernor` is well-architected — but it fundamentally lacks forex awareness:

| Category | Crypto Ready | Forex Ready | Gap Severity |
|----------|:---:|:---:|:---:|
| Position sizing | ✅ | ❌ | 🔴 Critical |
| Spread risk | ✅ (basic) | ❌ | 🔴 Critical |
| Swap/rollover | ❌ | ❌ | 🟡 High |
| Margin/leverage tracking | ❌ | ❌ | 🔴 Critical |
| Leverage caps | ❌ | ❌ | 🔴 Critical |
| Session awareness | ❌ | ❌ | 🟡 High |
| Cross-broker aggregation | ❌ | ❌ | 🔴 Critical |
| Regulatory compliance | ❌ | ❌ | 🔴 Critical |
| Gap risk (weekends) | ❌ | ❌ | 🟡 High |
| Correlation (cross-asset) | ⚠️ Partial | ❌ | 🟡 High |

**Bottom line:** 6 critical gaps, 4 high-priority gaps. Forex cannot go live without addressing all critical items.

---

## 2. Current Risk Stack Assessment

### 2.1 Circuit Breaker (`circuit_breaker.py`)

**Current implementation:**
- `DAILY_LOSS` — trips at `max_daily_loss_pct` (default 3%)
- `CONSECUTIVE_LOSS` — trips at `max_consecutive_losses` (default 5)
- `VOLATILITY` — z-score threshold (default 3.0)
- `BLACK_SWAN` — extreme z-score (default 5.0)
- Cooldown: 30 minutes

**Assessment for forex:**
- ✅ Daily loss breaker is asset-agnostic — works fine
- ⚠️ Volatility z-score uses raw P&L returns, not normalized. Forex P&L in pips differs from crypto in absolute terms. A 50-pip loss on EUR/USD (~$50/lot) is normal; a $50 loss on BTC/USDT is noise. **Z-scores will be misleading cross-asset.**
- ❌ No **session-aware** circuit breaker (forex sessions have different volatility profiles)
- ❌ No **spread-widening** breaker (forex spreads can 5x during news events)
- ❌ No **margin-level** breaker (forex can margin-call; crypto spot cannot)
- ❌ No **liquidity-gap** breaker (forex weekend gaps can blow through stops)

### 2.2 Drawdown Manager (`drawdown.py`)

**Current implementation:**
- Daily, weekly, total drawdown tracking
- Progressive de-escalation (risk multiplier 1.0 → 0.0 as drawdown increases)
- Hard breach at daily 3%, weekly 7%, total 15%

**Assessment for forex:**
- ✅ Core drawdown tracking is asset-agnostic — works fine
- ❌ Balance tracking uses a single account. With cross-broker positions (Binance + OANDA), drawdown must aggregate across brokers
- ❌ No **equity-based** drawdown (forex uses equity = balance + unrealized P&L; current code tracks realized balance only)
- ❌ Daily reset assumes UTC midnight. Forex daily close is 5 PM EST (22:00 UTC). **Reset timing is wrong for forex.**
- ⚠️ Progressive de-escalation thresholds (2%, 5%, 10%) are tuned for crypto volatility. Forex daily moves are typically 0.5-1.5%. These thresholds are too loose for forex.

### 2.3 Position Sizer (`position_sizer.py`)

**Current implementation:**
- Fixed-risk and Kelly criterion sizing
- Spread-cost aware (rejects if spread > 30% of risk)
- Progressive de-escalation with drawdown

**Assessment for forex:**
- ⚠️ Has `spread_pips` and `pip_value` fields in `SizingRequest` — some forex awareness exists
- ❌ **Critical:** Sizing computes `risk_amount / sl_distance` to get size. For crypto, size = quantity (e.g., 0.001 BTC). For forex, size = lots (e.g., 0.1 standard lots). The formula produces different units. **There is no lot-based sizing.**
- ❌ No contract size awareness (1 standard lot = 100,000 units for forex)
- ❌ No leverage-adjusted sizing (forex margin = notional / leverage; sizing must account for available margin)
- ❌ Spread cost calculation uses `spread_pips * pip_value` which is per-unit, but forex pips are per-lot. The math is wrong for forex.
- ❌ No swap cost consideration in the "effective risk" calculation
- ❌ Min size is `0.001` (crypto minimum) — forex minimum is typically `0.01` lots

### 2.4 Exposure Manager (`exposure.py`)

**Current implementation:**
- Per-pair, per-session, per-direction exposure tracking
- Leverage cap enforcement
- Max open positions

**Assessment for forex:**
- ❌ **Critical:** `size * entry_price` is used as notional value. For crypto, 0.001 BTC × $60,000 = $60. For forex, 0.1 lots × 1.0850 = $0.1085 — **completely wrong**. Forex notional = lots × contract_size × price (e.g., 0.1 × 100,000 × 1.0850 = $10,850).
- ❌ `max_leverage` default is `2.0` — forex routinely uses 1:30 to 1:100. The exposure manager would reject every forex trade.
- ❌ No cross-broker exposure aggregation (positions on Binance and OANDA are tracked independently)
- ❌ No currency-exposure tracking (holding EUR/USD long and GBP/USD short both expose you to USD weakness — correlated risk)
- ❌ `PositionExposure` model has no `broker` field — can't distinguish which broker a position is on

### 2.5 Risk Governor (`governor.py`)

**Current implementation:**
- 7-gate approval pipeline (halt → validation → circuit breaker → drawdown → exposure → correlation → sizing)
- Event-driven risk events for observability
- Composite risk score (0-1)

**Assessment for forex:**
- ✅ Gate architecture is excellent — adding forex-specific checks is straightforward
- ❌ Gate 4 (exposure) calls `exposure_manager.check_add_position()` which uses the broken `size * price` notional
- ❌ Gate 6 (sizing) calls `position_sizer.size_position()` without lot-awareness
- ❌ `TradeRequest` model has no `broker` field — governor can't route risk checks per-broker
- ❌ `TradeRequest` has no `leverage`, `margin_required`, or `swap_rate` fields
- ❌ Risk score computation doesn't account for leverage or swap costs

### 2.6 Trade Validators (`validators.py`)

**Current implementation:**
- Price sanity (NaN, zero, bounds)
- Size sanity (positive, min/max)
- Direction validation
- Stop loss / take profit logic
- Slippage and spread checks

**Assessment for forex:**
- ❌ `min_size` default is `0.001` — forex minimum is `0.01` lots
- ❌ `max_size` default is `1000.0` — meaningless without lot/contract context
- ❌ `max_spread_pct` is `0.5%` — forex spreads are measured in pips, not percentage. A 2-pip spread on EUR/USD at 1.0850 is 0.018%, well under 0.5%, but may be excessive for a scalping strategy. Need spread-in-pips validation.
- ❌ No validation of lot step alignment (forex brokers reject orders not aligned to lot_step, e.g., 0.01 increments)
- ❌ Stop loss distance checks use percentage — forex traders think in pips. A 50-pip SL on EUR/USD is 0.46% — seems tight by crypto standards but is normal for forex.

### 2.7 Trading Loop (`loop.py`)

**Current implementation:**
- Hardcoded for crypto: `symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]`
- Trade quantity hardcoded to `0.001`
- Drawdown normalized against `INITIAL_CAPITAL = 10000.0`

**Assessment for forex:**
- ❌ Symbol list is crypto-only
- ❌ Trade execution uses `quantity: 0.001` — meaningless for forex (needs lots)
- ❌ No session-time awareness (forex has defined sessions; crypto is 24/7)
- ❌ No weekend gap protection (forex markets close Friday ~22:00 UTC, reopen Sunday ~22:00 UTC)
- ⚠️ Circuit breaker drawdown threshold is 20% — too high for forex

### 2.8 Risk Agent (`agent.py`)

**Current implementation:**
- Evaluates signals against risk limits
- Checks drawdown, daily loss, positions, news
- Applies news risk adjustment multiplier

**Assessment for forex:**
- ❌ No forex-specific checks (margin level, swap impact, spread conditions)
- ❌ `quantity=1.0` as base — needs lot-based sizing
- ❌ News risk adjustment exists but doesn't distinguish between crypto news (exchange hacks, regulatory) and forex news (NFP, CPI, central bank decisions)
- ❌ No session-time awareness for trade approval

---

## 3. Risk Gap Analysis

### 3.1 Critical Gaps (Must Fix Before Go-Live)

| # | Gap | Current State | Required State |
|---|-----|---------------|----------------|
| C1 | **Lot-based position sizing** | `size = risk_amount / sl_distance` (crypto units) | `lots = risk_amount / (sl_distance × contract_size × pip_value)` |
| C2 | **Notional value calculation** | `size × price` | `lots × contract_size × price` |
| C3 | **Leverage enforcement** | `max_leverage=2.0` | Per-broker leverage caps (1:30 EU, 1:50 US, configurable) |
| C4 | **Margin tracking** | None | Track free margin, used margin, margin level % |
| C5 | **Cross-broker exposure** | Single-broker only | Aggregate notional across Binance + OANDA + MT5 |
| C6 | **Currency normalization** | Single currency (assumed USD) | Convert all P&L/exposure to base currency using live FX rates |

### 3.2 High-Priority Gaps (Should Fix Before Go-Live)

| # | Gap | Impact |
|---|-----|--------|
| H1 | **Swap/rollover tracking** | Holding costs accumulate silently; can turn winning trades into losers |
| H2 | **Session-aware circuit breakers** | Different volatility profiles per session; London open spikes can false-trip |
| H3 | **Spread-widening breaker** | News events can widen EUR/USD spread from 1.0 to 10+ pips instantly |
| H4 | **Weekend gap protection** | Positions held over weekend can gap 50-200+ pips through stops |
| H5 | **Forex-specific drawdown reset timing** | Reset at 22:00 UTC (5 PM EST forex day end), not midnight UTC |
| H6 | **Lot step validation** | Brokers reject non-aligned lot sizes (e.g., 0.123 lots rejected if step=0.01) |

### 3.3 Medium-Priority Gaps (Should Fix Soon)

| # | Gap | Impact |
|---|-----|--------|
| M1 | **Correlated pair detection** | EUR/USD long + GBP/USD long = double USD exposure |
| M2 | **Pip-based stop loss validation** | Forex traders think in pips, not percentages |
| M3 | **Exotic pair risk tiering** | Exotic pairs (USD/TRY) have wider spreads, higher gaps, lower liquidity |
| M4 | **Central bank event awareness** | FOMC, ECB, BOJ decisions cause extreme volatility; should auto-widen stops |
| M5 | **Hedging support** | MT5 supports hedging; OANDA is netting-only. Risk logic must handle both. |

---

## 4. New Risk Types Required

### 4.1 Spread Risk (Forex-Specific)

**What it is:** The bid-ask spread is the primary transaction cost in forex. Unlike crypto (which has explicit fees), forex costs are embedded in the spread.

**Why it matters:** During news events, spreads can widen 5-10x. A strategy profitable at 1.0 pip spread may be unprofitable at 5.0 pips.

**Required implementation:**
```python
class SpreadRiskMonitor:
    """Track and enforce spread limits per instrument."""
    
    def __init__(self):
        self._max_spread_pips: dict[str, float] = {}  # per-symbol limits
        self._spread_history: dict[str, list[float]] = {}  # rolling window
    
    def check_spread(self, symbol: str, current_spread_pips: float) -> tuple[bool, str]:
        """Reject trade if spread exceeds limit."""
        max_spread = self._max_spread_pips.get(symbol, 3.0)  # default 3 pips
        if current_spread_pips > max_spread:
            return False, f"Spread {current_spread_pips:.1f} pips > limit {max_spread:.1f} pips"
        
        # Check if spread is abnormally wide vs recent average
        history = self._spread_history.get(symbol, [])
        if len(history) >= 20:
            avg = sum(history[-20:]) / 20
            if current_spread_pips > avg * 3.0:
                return False, f"Spread {current_spread_pips:.1f} pips is 3x average {avg:.1f} pips"
        
        return True, ""
    
    def record_spread(self, symbol: str, spread_pips: float) -> None:
        """Record spread for rolling average."""
        if symbol not in self._spread_history:
            self._spread_history[symbol] = []
        self._spread_history[symbol].append(spread_pips)
        if len(self._spread_history[symbol]) > 100:
            self._spread_history[symbol] = self._spread_history[symbol][-100:]
```

### 4.2 Swap/Rollover Risk

**What it is:** Positions held past 5 PM EST incur swap fees based on interest rate differentials. Wednesday is triple-swap day.

**Why it matters:** Swap costs can be $3-10 per lot per day on major pairs. A position held for a month can lose 30-100 pips in swap alone.

**Required implementation:**
```python
class SwapRiskMonitor:
    """Track and project swap costs on open positions."""
    
    def __init__(self, max_daily_swap_pct: float = 0.5):
        self._max_daily_swap_pct = max_daily_swap_pct  # max swap as % of account
        self._swap_rates: dict[str, dict[str, float]] = {}  # symbol -> {long, short}
    
    def project_daily_swap_cost(
        self,
        symbol: str,
        direction: str,
        lots: float,
        contract_size: float = 100_000,
    ) -> float:
        """Project daily swap cost in account currency."""
        rates = self._swap_rates.get(symbol, {})
        swap_rate = rates.get(direction, 0.0)
        return swap_rate * lots * contract_size
    
    def check_swap_budget(
        self,
        total_daily_swap: float,
        account_balance: float,
    ) -> tuple[bool, str]:
        """Check if total daily swap costs exceed budget."""
        swap_pct = (total_daily_swap / account_balance * 100) if account_balance > 0 else 0
        if swap_pct > self._max_daily_swap_pct:
            return False, f"Daily swap cost {swap_pct:.2f}% > limit {self._max_daily_swap_pct}%"
        return True, ""
    
    def is_triple_swap_day(self) -> bool:
        """Check if today is Wednesday (triple swap)."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).weekday() == 2  # Wednesday
```

### 4.3 Margin Risk

**What it is:** Forex uses leverage. If your margin level drops below the broker's threshold (typically 50-100%), the broker forcibly closes your positions (stop-out).

**Why it matters:** Unlike crypto spot (where you can only lose what you put in), forex leverage means a 1% adverse move on 1:100 leverage = 100% account loss.

**Required implementation:**
```python
class MarginRiskMonitor:
    """Track margin usage and prevent margin calls."""
    
    def __init__(
        self,
        min_margin_level_pct: float = 200.0,  # our limit (broker's is ~50-100%)
        max_leverage: float = 30.0,  # conservative default
    ):
        self._min_margin_level_pct = min_margin_level_pct
        self._max_leverage = max_leverage
    
    def calculate_required_margin(
        self,
        lots: float,
        contract_size: float,
        price: float,
        leverage: float,
    ) -> float:
        """Calculate margin required for a position."""
        notional = lots * contract_size * price
        return notional / leverage
    
    def check_margin_level(
        self,
        equity: float,
        used_margin: float,
    ) -> tuple[bool, str]:
        """Check if margin level is safe."""
        if used_margin <= 0:
            return True, ""
        margin_level = (equity / used_margin) * 100
        if margin_level < self._min_margin_level_pct:
            return False, f"Margin level {margin_level:.1f}% < safe limit {self._min_margin_level_pct}%"
        return True, ""
    
    def check_leverage(
        self,
        total_notional: float,
        equity: float,
    ) -> tuple[bool, str]:
        """Check if effective leverage exceeds limit."""
        if equity <= 0:
            return False, "Zero equity"
        effective_leverage = total_notional / equity
        if effective_leverage > self._max_leverage:
            return False, f"Effective leverage {effective_leverage:.1f}x > limit {self._max_leverage}x"
        return True, ""
```

### 4.4 Gap Risk (Weekend/Holiday)

**What it is:** Forex markets close Friday ~22:00 UTC and reopen Sunday ~22:00 UTC. Price can gap significantly over the weekend, blowing through stop losses.

**Why it matters:** A stop loss at 1.0850 might fill at 1.0780 on Monday open — a 70-pip slippage that the system never anticipated.

**Required implementation:**
```python
class GapRiskMonitor:
    """Protect against weekend/holiday gap risk."""
    
    def __init__(self, max_gap_risk_pips: float = 50.0):
        self._max_gap_risk_pips = max_gap_risk_pips
    
    def should_close_before_weekend(
        self,
        symbol: str,
        direction: str,
        stop_loss_pips: float,
    ) -> tuple[bool, str]:
        """Determine if position should be closed before weekend."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        # Friday after 20:00 UTC — 2 hours before market close
        if now.weekday() == 4 and now.hour >= 20:
            if stop_loss_pips < self._max_gap_risk_pips:
                return True, (
                    f"Weekend gap risk: SL is {stop_loss_pips:.0f} pips, "
                    f"max acceptable gap is {self._max_gap_risk_pips:.0f} pips. "
                    f"Recommend closing before weekend."
                )
        
        return False, ""
    
    def is_market_closed(self) -> bool:
        """Check if forex market is currently closed."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        # Saturday
        if now.weekday() == 5:
            return True
        # Sunday before 22:00 UTC
        if now.weekday() == 6 and now.hour < 22:
            return True
        # Friday after 22:00 UTC
        if now.weekday() == 4 and now.hour >= 22:
            return True
        
        return False
```

### 4.5 Cross-Asset Correlation Risk

**What it is:** Forex pairs are inherently correlated. EUR/USD and GBP/USD share ~80% correlation. Holding both long doubles your USD-short exposure.

**Why it matters:** The current `CorrelationMonitor` tracks crypto correlations. Forex correlations are structural (driven by shared currency components), not statistical.

**Required implementation:**
```python
# Structural forex correlation matrix
FOREX_CORRELATION = {
    # High correlation groups (shared base/quote currency)
    "EUR/USD": {"GBP/USD": 0.85, "AUD/USD": 0.70, "NZD/USD": 0.65},
    "GBP/USD": {"EUR/USD": 0.85, "AUD/USD": 0.60},
    "USD/JPY": {"USD/CHF": 0.80, "USD/CAD": 0.60},
    # Inverse correlations
    "EUR/USD": {"USD/CHF": -0.90, "USD/JPY": -0.30},
}

class ForexCorrelationChecker:
    """Check structural correlations between forex positions."""
    
    def check_correlated_exposure(
        self,
        new_symbol: str,
        new_direction: str,
        existing_positions: list[dict],
        max_correlated_exposure_pct: float = 30.0,
        balance: float = 1000.0,
    ) -> tuple[bool, str]:
        """Check if new position creates excessive correlated exposure."""
        # Implementation would check structural correlations
        # and aggregate exposure across correlated pairs
        pass
```

---

## 5. Position Sizing: Lots vs Quantity

### 5.1 The Fundamental Difference

| Aspect | Crypto (Current) | Forex (Required) |
|--------|------------------|------------------|
| **Size unit** | Quantity (e.g., 0.001 BTC) | Lots (e.g., 0.1 standard lots) |
| **Notional** | quantity × price | lots × contract_size × price |
| **P&L per unit** | quantity × price_change | lots × contract_size × pip_size × pip_value |
| **Min size** | Exchange-specific (0.00001 BTC) | Broker-specific (0.01 lots) |
| **Size step** | Exchange-specific | Broker-specific (0.01 lots typical) |
| **Margin** | Not applicable (spot) | notional / leverage |

### 5.2 Required Changes to PositionSizer

```python
class AssetType(str, Enum):
    CRYPTO = "crypto"
    FOREX = "forex"

class SizingRequest(BaseModel):
    # ... existing fields ...
    asset_type: AssetType = AssetType.CRYPTO
    # Forex-specific
    contract_size: float = 100_000.0  # units per standard lot
    lot_step: float = 0.01
    leverage: float = 30.0
    swap_rate_daily: float = 0.0  # daily swap cost per lot

def _forex_risk_size(
    self,
    request: SizingRequest,
    balance: float,
    risk_pct: float,
) -> float:
    """Forex-specific position sizing in lots."""
    risk_amount = balance * (risk_pct / 100)
    
    # SL distance in pips
    sl_distance_pips = abs(request.entry_price - request.stop_loss) / request.pip_value
    
    # Pip value per lot
    pip_value_per_lot = request.pip_value * request.contract_size
    
    # Size in lots
    lots = risk_amount / (sl_distance_pips * pip_value_per_lot)
    
    # Align to lot step
    lots = round(lots / request.lot_step) * request.lot_step
    
    # Margin check
    margin_required = (lots * request.contract_size * request.entry_price) / request.leverage
    if margin_required > balance * 0.8:  # Never use more than 80% margin
        lots = (balance * 0.8 * request.leverage) / (request.contract_size * request.entry_price)
        lots = round(lots / request.lot_step) * request.lot_step
    
    return max(lots, request.min_size)
```

### 5.3 Lot Size Reference

| Account Size | Max Risk/Trade (1%) | EUR/USD SL 50 pips | Lots |
|-------------|---------------------|--------------------|----|
| $500 | $5.00 | 50 × $10 = $500/lot | 0.01 (micro) |
| $1,000 | $10.00 | 50 × $10 = $500/lot | 0.02 |
| $5,000 | $50.00 | 50 × $10 = $500/lot | 0.10 (mini) |
| $10,000 | $100.00 | 50 × $10 = $500/lot | 0.20 |
| $50,000 | $500.00 | 50 × $10 = $500/lot | 1.00 (standard) |

---

## 6. Circuit Breaker Thresholds: Forex vs Crypto

### 6.1 Why Thresholds Must Differ

| Metric | Crypto Typical | Forex Typical | Implication |
|--------|---------------|---------------|-------------|
| Daily volatility | 3-10% | 0.5-1.5% | Forex breakers need tighter % thresholds |
| Spread volatility | Low (exchange fees fixed) | High (variable, news-sensitive) | Forex needs spread breaker |
| Gap risk | None (24/7 market) | High (weekends, holidays) | Forex needs gap breaker |
| Leverage | 1-5x (spot) or 20-125x (futures) | 30-500x | Forex needs margin breaker |
| Max drawdown tolerance | 15-20% | 5-10% | Forex drawdown limits should be tighter |

### 6.2 Recommended Circuit Breaker Configuration

```python
FOREX_CIRCUIT_BREAKER_CONFIG = {
    "max_daily_loss_pct": 2.0,          # vs crypto 3.0%
    "max_consecutive_losses": 4,         # vs crypto 5
    "volatility_zscore_threshold": 2.5,  # vs crypto 3.0
    "black_swan_zscore_threshold": 4.0,  # vs crypto 5.0
    "cooldown_minutes": 60,              # vs crypto 30
    # New forex-specific breakers
    "max_spread_multiplier": 3.0,        # trip if spread > 3x average
    "min_margin_level_pct": 200.0,       # trip if margin level < 200%
    "max_daily_swap_pct": 0.5,           # trip if swap > 0.5% of account/day
    "weekend_close_minutes_before": 120, # auto-close 2h before weekend
}

CRYPTO_CIRCUIT_BREAKER_CONFIG = {
    "max_daily_loss_pct": 3.0,
    "max_consecutive_losses": 5,
    "volatility_zscore_threshold": 3.0,
    "black_swan_zscore_threshold": 5.0,
    "cooldown_minutes": 30,
}
```

### 6.3 Per-Session Breaker Adjustments

| Session | Characteristics | Adjustments |
|---------|----------------|-------------|
| **Asian** (00:00-09:00 UTC) | Lower volatility, thinner liquidity | Tighten spread breaker (2x avg), lower max position |
| **London** (07:00-16:00 UTC) | Highest liquidity, normal spreads | Standard thresholds |
| **London+NY Overlap** (12:00-16:00 UTC) | Peak volatility, tightest spreads | Widen volatility breaker (3.5 z-score) |
| **New York** (12:00-21:00 UTC) | High liquidity, news-heavy | Standard thresholds, news-aware |
| **Late NY** (20:00-22:00 UTC) | Thinning liquidity, wider spreads | Tighten position limits, warn on new positions |

---

## 7. Cross-Broker Risk

### 7.1 The Problem

When AlphaStack trades on both Binance (crypto) and OANDA/MT5 (forex) simultaneously:

1. **Double exposure:** A USD-short position via BTC/USDT long on Binance AND EUR/USD long on OANDA both benefit from USD weakness — correlated risk that neither broker sees alone.
2. **Capital allocation:** $5,000 split across two brokers means each broker sees only part of your capital. Risk limits calibrated per-broker are meaningless.
3. **Margin isolation:** Margin on OANDA is calculated only from OANDA positions. If Binance has a drawdown, your effective risk tolerance drops, but OANDA doesn't know.
4. **P&L currency mismatch:** Binance P&L is in USDT; OANDA P&L might be in USD. Need live conversion.

### 7.2 Required: Cross-Broker Risk Aggregator

```python
class CrossBrokerRiskAggregator:
    """Unified risk view across all brokers."""
    
    def __init__(self, registry: BrokerRegistry):
        self._registry = registry
    
    async def get_aggregate_state(self) -> AggregateRiskState:
        """Get unified risk state across all brokers."""
        total_equity = 0.0
        total_used_margin = 0.0
        total_notional = 0.0
        all_positions = []
        
        for name in self._registry.names:
            connector = self._registry.get(name)
            if not connector or not connector.is_connected:
                continue
            
            balance = await connector.get_balance()
            positions = await connector.get_positions()
            
            # Convert to base currency (USD)
            equity_usd = await self._convert_to_usd(balance.equity, balance.currency)
            total_equity += equity_usd
            total_used_margin += balance.used_margin  # TODO: currency conversion
            
            for pos in positions:
                all_positions.append({
                    "broker": name,
                    "symbol": pos.symbol,
                    "direction": pos.side.value,
                    "notional": pos.quantity * pos.avg_entry_price,  # needs forex fix
                    "unrealized_pnl": pos.unrealized_pnl,
                })
        
        return AggregateRiskState(
            total_equity_usd=total_equity,
            total_used_margin=total_used_margin,
            total_notional=total_notional,
            effective_leverage=total_notional / total_equity if total_equity > 0 else 0,
            positions=all_positions,
            margin_level_pct=(total_equity / total_used_margin * 100) if total_used_margin > 0 else float('inf'),
        )
    
    async def _convert_to_usd(self, amount: float, currency: str) -> float:
        """Convert amount to USD using live rates."""
        if currency == "USD" or currency == "USDT":
            return amount
        # Fetch live FX rate and convert
        # Implementation depends on having a rate source
        raise NotImplementedError(f"Currency conversion from {currency} to USD not implemented")
```

### 7.3 Cross-Broker Position Model Changes

```python
class PositionExposure(BaseModel):
    """Tracked position for exposure calculations."""
    symbol: str
    direction: str
    size: float  # lots (forex) or quantity (crypto)
    entry_price: float
    broker: str = ""           # NEW: which broker
    asset_type: str = ""       # NEW: "crypto" or "forex"
    notional_usd: float = 0.0  # NEW: normalized notional in USD
    margin_used: float = 0.0   # NEW: margin consumed
    session: str = ""
    strategy_id: str = ""
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

---

## 8. Regulatory Considerations

### 8.1 Jurisdiction-Specific Rules

| Jurisdiction | Max Leverage (Majors) | Key Rules | Impact on AlphaStack |
|-------------|----------------------|-----------|---------------------|
| **US (NFA/CFTC)** | 1:50 | FIFO only, no hedging, limited pairs | Must enforce FIFO; can't hedge same pair |
| **EU/UK (ESMA/FCA)** | 1:30 | Negative balance protection, margin close-out at 50% | Lower leverage cap; auto-close logic needed |
| **Australia (ASIC)** | 1:30 | Similar to ESMA | Same as EU |
| **Offshore** | 1:500-1:3000 | Minimal regulation | Higher leverage available but higher risk |
| **Japan (FSA)** | 1:25 | Strict reporting | Lowest leverage; may not be viable |

### 8.2 FIFO Compliance (US Accounts)

OANDA US accounts enforce FIFO (First In, First Out):

```python
class FIFOValidator:
    """Enforce FIFO rules for US forex accounts."""
    
    def validate_close(
        self,
        symbol: str,
        close_ticket: str,
        open_positions: list[dict],
    ) -> tuple[bool, str]:
        """Ensure the oldest position is closed first."""
        # Sort by open time
        same_symbol = [p for p in open_positions if p["symbol"] == symbol]
        if not same_symbol:
            return True, ""
        
        same_symbol.sort(key=lambda p: p["opened_at"])
        oldest_ticket = same_symbol[0]["ticket"]
        
        if close_ticket != oldest_ticket:
            return False, (
                f"FIFO violation: must close oldest position {oldest_ticket} "
                f"before {close_ticket}"
            )
        return True, ""
```

### 8.3 Hedging Restrictions

```python
class HedgingPolicy:
    """Enforce hedging rules per broker."""
    
    HEDGING_ALLOWED = {"mt5": True, "oanda_us": False, "oanda_intl": False, "binance": True}
    
    def can_open_opposite(
        self,
        broker: str,
        symbol: str,
        existing_direction: str,
    ) -> tuple[bool, str]:
        """Check if opening opposite direction is allowed."""
        if not self.HEDGING_ALLOWED.get(broker, False):
            # Netting account — opening opposite will reduce/close existing
            return True, f"Netting account: opposite order will reduce {existing_direction} position"
        return True, ""  # Hedging allowed
```

### 8.4 Required Regulatory Configuration

```python
@dataclass
class BrokerRegulatoryConfig:
    """Regulatory configuration per broker."""
    broker: str
    jurisdiction: str
    max_leverage: float
    fifo_required: bool = False
    hedging_allowed: bool = True
    negative_balance_protection: bool = True
    margin_closeout_pct: float = 50.0  # broker's stop-out level
    max_positions: int = 100
    restricted_symbols: list[str] = field(default_factory=list)
    
# Example configs
REGULATORY_CONFIGS = {
    "oanda_us": BrokerRegulatoryConfig(
        broker="oanda",
        jurisdiction="US",
        max_leverage=50.0,
        fifo_required=True,
        hedging_allowed=False,
    ),
    "oanda_eu": BrokerRegulatoryConfig(
        broker="oanda",
        jurisdiction="EU",
        max_leverage=30.0,
        negative_balance_protection=True,
        margin_closeout_pct=50.0,
    ),
    "mt5_icmarkets": BrokerRegulatoryConfig(
        broker="mt5",
        jurisdiction="AU",
        max_leverage=30.0,
        hedging_allowed=True,
    ),
    "binance": BrokerRegulatoryConfig(
        broker="binance",
        jurisdiction="Offshore",
        max_leverage=125.0,
    ),
}
```

---

## 9. Recommended Risk Parameters for Forex

### 9.1 Drawdown Limits

| Parameter | Crypto (Current) | Forex (Recommended) | Rationale |
|-----------|-----------------|---------------------|-----------|
| Max daily loss | 3.0% | 2.0% | Forex is lower volatility; 3% daily is extreme |
| Max weekly loss | 7.0% | 5.0% | Tighter weekly discipline |
| Max total drawdown | 15.0% | 10.0% | Leverage amplifies recovery difficulty |
| Drawdown reset time | 00:00 UTC | 22:00 UTC | Forex day ends at 5 PM EST |

### 9.2 Position Limits

| Parameter | Crypto (Current) | Forex (Recommended) | Rationale |
|-----------|-----------------|---------------------|-----------|
| Max open positions | 10 | 6 | Forex pairs are correlated; fewer positions = less hidden correlation |
| Max per-pair exposure | 20% | 15% | Single pair concentration is riskier with leverage |
| Max per-session exposure | 40% | 25% | Sessions have different liquidity |
| Max leverage | 2.0x | 20.0x (our limit, not broker's) | Conservative vs broker's 1:30-1:50 |
| Max margin utilization | N/A | 60% | Never use more than 60% of available margin |

### 9.3 Trade-Level Limits

| Parameter | Crypto (Current) | Forex (Recommended) | Rationale |
|-----------|-----------------|---------------------|-----------|
| Max risk per trade | 2.0% | 1.0% | Lower per-trade risk with leverage |
| Min lot size | 0.001 | 0.01 | Broker minimum |
| Max lot size | 1000 | 10.0 | 10 standard lots = $1M notional; sufficient |
| Lot step | N/A | 0.01 | Broker alignment |
| Max spread (entry) | 0.5% | 3.0 pips (majors), 8.0 pips (exotics) | Pips, not percentage |
| Max slippage | 1.0% | 2.0 pips | Forex slippage measured in pips |

### 9.4 Circuit Breaker Thresholds

| Parameter | Crypto (Current) | Forex (Recommended) |
|-----------|-----------------|---------------------|
| Max daily loss | 3.0% | 2.0% |
| Max consecutive losses | 5 | 4 |
| Volatility z-score | 3.0 | 2.5 |
| Black swan z-score | 5.0 | 4.0 |
| Cooldown | 30 min | 60 min |
| **Spread breaker** | N/A | 3x average spread |
| **Margin level breaker** | N/A | < 200% |
| **Weekend close** | N/A | Auto-close 2h before market close if SL < 50 pips |

### 9.5 Swap Management

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max daily swap cost | 0.5% of account | Prevent swap bleed |
| Triple swap awareness | Auto-warn on Wednesday | Wednesday = 3x swap |
| Swap-positive priority | Prefer swap-positive directions | Earn, don't pay, swap |
| Max holding period (swap-negative) | 5 trading days | Limit swap accumulation |

---

## 10. MUST-Build Before Forex Go-Live

### 🔴 BLOCKER — Cannot trade forex without these

| # | Component | What to Build | Effort |
|---|-----------|---------------|--------|
| 1 | **ForexPositionSizer** | Lot-based sizing with contract_size, pip_value, margin awareness | 2 days |
| 2 | **ForexExposureManager** | Correct notional calculation (`lots × contract_size × price`), leverage caps | 1 day |
| 3 | **MarginRiskMonitor** | Track margin level, prevent margin calls, enforce our 200% limit | 1 day |
| 4 | **CrossBrokerAggregator** | Aggregate equity, exposure, P&L across all brokers with currency conversion | 2 days |
| 5 | **ForexCircuitBreaker** | Spread breaker, margin breaker, weekend gap breaker | 2 days |
| 6 | **SymbolMetadataStore** | Per-symbol specs (pip size, contract size, lot step, swap rates) | 1 day |
| 7 | **LotStepValidator** | Enforce lot alignment in TradeValidator | 0.5 day |
| 8 | **ForexDrawdownReset** | Reset at 22:00 UTC instead of midnight | 0.5 day |

**Total blocker effort: ~10 days**

### 🟡 HIGH PRIORITY — Should build before go-live

| # | Component | What to Build | Effort |
|---|-----------|---------------|--------|
| 9 | **SwapRiskMonitor** | Track swap costs, triple-swap warnings, swap budget enforcement | 1 day |
| 10 | **SessionAwareBreaker** | Different circuit breaker thresholds per trading session | 1 day |
| 11 | **ForexCorrelationChecker** | Structural correlation detection (EUR/USD + GBP/USD = double USD exposure) | 1 day |
| 12 | **GapRiskManager** | Weekend/holiday position management, auto-close recommendations | 1 day |
| 13 | **RegulatoryConfig** | Per-broker regulatory rules (FIFO, hedging, leverage caps) | 1 day |
| 14 | **CurrencyConverter** | Live FX rate fetching for cross-broker P&L normalization | 1 day |

**Total high-priority effort: ~6 days**

### 🟢 NICE TO HAVE — Build after initial forex deployment

| # | Component | What to Build | Effort |
|---|-----------|---------------|--------|
| 15 | **CentralBankCalendar** | Auto-widen stops around FOMC, ECB, BOJ decisions | 1 day |
| 16 | **ExoticPairRiskTier** | Higher spread/gap/liquidity risk for exotic pairs | 0.5 day |
| 17 | **HedgingPolicyEngine** | Enforce hedging rules per broker/account type | 1 day |
| 18 | **ForexNewsFilter** | Block trades during high-impact forex news (NFP, CPI) | 1 day |

---

## 11. Implementation Priority

```
Phase 1 — Risk Foundation (Week 1)
├── SymbolMetadataStore (pip size, contract size, lot specs)
├── ForexPositionSizer (lot-based sizing)
├── ForexExposureManager (correct notional, leverage caps)
├── LotStepValidator
└── ForexDrawdownReset timing

Phase 2 — Safety Systems (Week 2)
├── MarginRiskMonitor
├── ForexCircuitBreaker (spread + margin + weekend)
├── CrossBrokerAggregator
└── CurrencyConverter

Phase 3 — Advanced Risk (Week 3)
├── SwapRiskMonitor
├── SessionAwareBreaker
├── ForexCorrelationChecker
├── GapRiskManager
└── RegulatoryConfig

Phase 4 — Intelligence (Week 4+)
├── CentralBankCalendar
├── ExoticPairRiskTier
├── HedgingPolicyEngine
└── ForexNewsFilter
```

---

## 12. Summary

### What Works Today
- Circuit breaker architecture (add forex triggers)
- Drawdown tracking framework (fix reset timing, tighten limits)
- 7-gate approval pipeline in RiskGovernor (add forex gates)
- Event-driven risk observability
- Trade validator framework (add forex validators)

### What Must Change
- Position sizing: crypto quantity → forex lots
- Notional calculation: `size × price` → `lots × contract_size × price`
- Leverage: `2.0x` → configurable per-broker (up to 50x our limit)
- All risk limits: retighten for forex volatility profile
- Exposure tracking: add broker field, normalize to USD

### What Must Be Added
- Margin monitoring (prevent margin calls)
- Spread risk monitoring (reject trades during spread spikes)
- Swap cost tracking (don't let swap bleed kill profits)
- Weekend gap protection (auto-close before market close)
- Cross-broker aggregation (single risk view across all brokers)
- Regulatory compliance per broker (FIFO, hedging, leverage caps)

### Risk Assessment

**Going live with forex using the current risk stack = operating without a safety net.**

The system would:
- Calculate position sizes in wrong units (crypto quantities, not lots)
- Not track margin usage (silent margin calls)
- Not enforce correct leverage limits (2x limit rejects all forex trades)
- Not aggregate risk across brokers (blind to total exposure)
- Not protect against weekend gaps (positions could gap through stops)
- Not track swap costs (silent P&L drain)

**All 8 BLOCKER items must be completed before any live forex trading.**

---

*End of Risk Analysis — Council Document*
