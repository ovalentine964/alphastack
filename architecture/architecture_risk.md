# Alpha Stack — Risk Management Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/research_financial_crises.md`](../research/research_financial_crises.md), [`research/research_market_microstructure.md`](../research/research_market_microstructure.md) — Financial crises analysis and market microstructure
> **Status:** Architecture Complete

---

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Risk Management Architect
> **Scope:** Institutional-grade risk management system for the Alpha Stack trading engine
> **Design Philosophy:** Survive first, profit second. Every risk limit is a hard wall, not a suggestion.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Position Sizing Engine](#2-position-sizing-engine)
3. [Drawdown Limit System](#3-drawdown-limit-system)
4. [Circuit Breaker System](#4-circuit-breaker-system)
5. [Correlation Monitoring](#5-correlation-monitoring)
6. [Tail Risk Management](#6-tail-risk-management)
7. [News Event Handling](#7-news-event-handling)
8. [Black Swan Detection & Response](#8-black-swan-detection--response)
9. [Integration with Trading Engine](#9-integration-with-trading-engine)
10. [Integration with Multi-Agent System](#10-integration-with-multi-agent-system)
11. [Configuration & Parameters](#11-configuration--parameters)
12. [Monitoring & Alerting](#12-monitoring--alerting)
13. [Testing & Validation](#13-testing--validation)

---

## 1. Architecture Overview

### 1.1 Design Philosophy

The risk management system is the **immune system** of Alpha Stack. It operates on five core principles:

| Principle | Description | Rationale |
|-----------|-------------|-----------|
| **Asymmetric Protection** | Missing a bull trend costs gains; missing a crisis costs capital. Crisis signals always overweight. | From 1997 Asian crisis to 2020 COVID — speed of decline kills. |
| **Hard Limits, Not Guidelines** | Every limit is enforced in code. No ML model, no agent, no human (except explicit kill switch) can bypass. | LTCM had "low" VaR before collapse. Models lie; limits don't. |
| **Layered Defense** | Four independent layers (position → portfolio → regime → system). Any single layer failure doesn't cascade. | Swiss franc 2015: single-layer systems were wiped out. |
| **Survive the Unprecedented** | Every "impossible" event has eventually happened. Model for 30% EUR/CHF moves, 50% BTC crashes, -34% S&P in 23 days. | Black swans are not rare — they're just undermodeled. |
| **Cost-Aware at Every Scale** | At $7, a 2% spread cost per trade is existential. At $1M, slippage on 10-lot orders is the constraint. Risk adapts. | TCA research: $7 account has ~46 trades before costs drain capital. |

### 1.2 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        RISK MANAGEMENT SYSTEM (RMS)                          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        RISK EVENT BUS (Redis Streams)                    │ │
│  │  risk.drawdown · risk.exposure · risk.correlation · risk.regime         │ │
│  │  risk.circuit_breaker · risk.black_swan · risk.news · risk.alert       │ │
│  └──────────────────────────────┬──────────────────────────────────────────┘ │
│                                 │                                            │
│  ┌──────────────────────────────▼──────────────────────────────────────────┐ │
│  │                     RISK GOVERNOR (Central Controller)                    │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │ │
│  │  │  POSITION    │ │  DRAWDOWN    │ │  CIRCUIT     │ │  CORRELATION │   │ │
│  │  │  SIZING      │ │  LIMIT       │ │  BREAKER     │ │  MONITOR     │   │ │
│  │  │  ENGINE      │ │  MANAGER     │ │  SYSTEM      │ │              │   │ │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘   │ │
│  │         └────────────────┼────────────────┼────────────────┘            │ │
│  │                          ▼                                              │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │ │
│  │  │  TAIL RISK   │ │  NEWS EVENT  │ │  BLACK SWAN  │ │  REGIME      │   │ │
│  │  │  MANAGER     │ │  HANDLER     │ │  DETECTOR    │ │  RISK        │   │ │
│  │  │              │ │              │ │              │ │  ADAPTER     │   │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │ │
│  └──────────────────────────────┬──────────────────────────────────────────┘ │
│                                 │                                            │
│  ┌──────────────────────────────▼──────────────────────────────────────────┐ │
│  │                     DECISION GATE (Pre-Trade / In-Trade)                 │ │
│  │  All trade proposals and management actions pass through this gate.      │ │
│  │  APPROVED / REJECTED / ADJUSTED — no exceptions.                         │ │
│  └──────────────────────────────┬──────────────────────────────────────────┘ │
│                                 │                                            │
│  ┌──────────────────────────────▼──────────────────────────────────────────┐ │
│  │                     INTEGRATION LAYER                                    │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │ │
│  │  │ Trading      │ │ Multi-Agent  │ │ Broker       │ │ Monitoring   │   │ │
│  │  │ Engine       │ │ System       │ │ Layer        │ │ & Alerting   │   │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Risk Event Types

All risk components communicate via the `risk.*` event streams:

```python
@dataclass
class RiskEvent:
    event_id: str                    # UUID
    timestamp: datetime
    event_type: RiskEventType        # See below
    severity: RiskSeverity           # INFO, WARNING, CRITICAL, EMERGENCY
    component: str                   # Which risk module generated this
    data: dict                       # Event-specific payload
    action_required: str             # NONE, REDUCE, HALT, CLOSE_ALL, HUMAN_OVERRIDE
    auto_response_taken: bool        # Did the system auto-respond?
    reasoning: str                   # Human-readable explanation

class RiskEventType(Enum):
    # Position level
    POSITION_SIZE_ADJUSTED = "position.size_adjusted"
    POSITION_LIMIT_BREACH = "position.limit_breach"
    STOP_LOSS_TRIGGERED = "position.stop_triggered"
    
    # Drawdown
    DRAWDOWN_STAGE_CHANGE = "drawdown.stage_change"
    DRAWDOWN_LIMIT_BREACH = "drawdown.limit_breach"
    
    # Circuit breaker
    CIRCUIT_BREAKER_TRIPPED = "circuit_breaker.tripped"
    CIRCUIT_BREAKER_RESET = "circuit_breaker.reset"
    
    # Correlation
    CORRELATION_SPIKE = "correlation.spike"
    CORRELATION_REGIME_SHIFT = "correlation.regime_shift"
    
    # Regime
    REGIME_CHANGE = "regime.change"
    REGIME_RISK_ADJUSTMENT = "regime.risk_adjustment"
    
    # Tail risk
    VAR_BREACH = "tail.var_breach"
    CVAR_BREACH = "tail.cvar_breach"
    STRESS_TEST_FAIL = "tail.stress_test_fail"
    
    # News
    NEWS_HIGH_IMPACT = "news.high_impact"
    NEWS_BLACKOUT_START = "news.blackout_start"
    NEWS_BLACKOUT_END = "news.blackout_end"
    
    # Black swan
    BLACK_SWAN_DETECTED = "black_swan.detected"
    BLACK_SWAN_PROTOCOL_ACTIVATED = "black_swan.protocol_activated"
    BLACK_SWAN_ALL_CLOSED = "black_swan.all_closed"
    
    # System
    SYSTEM_HEALTH_DEGRADED = "system.health_degraded"
    BROKER_DISCONNECT = "system.broker_disconnect"
    DATA_FEED_ANOMALY = "system.data_feed_anomaly"
```

---

## 2. Position Sizing Engine

### 2.1 Quarter-Kelly Criterion with Dynamic 4-Factor Adjustment

The position sizing engine uses **quarter-Kelly** as the mathematical foundation, modulated by four dynamic factors that adapt to real-time conditions.

#### 2.1.1 Kelly Foundation

```
Full Kelly:     f* = (bp - q) / b
Quarter Kelly:  f = f* / 4

Where:
  b = Average Win / Average Loss (reward-to-risk ratio)
  p = Win probability
  q = 1 - p (loss probability)

Example (Alpha Stack baseline):
  Win rate (p) = 0.68
  Avg R:R (b)  = 1.8
  Full Kelly    = (1.8 × 0.68 - 0.32) / 1.8 = 0.502 (50.2%)
  Quarter Kelly = 0.502 / 4 = 0.126 (12.6%)

RECOMMENDED: Cap at 2% per trade regardless of Kelly output.
Quarter Kelly provides the mathematical optimum; the 2% cap provides survival.
```

#### 2.1.2 Dynamic 4-Factor Model

```
FINAL_RISK = Base_Risk × F1(Confluence) × F2(Regime) × F3(Performance) × F4(Volatility)

Where:
  Base_Risk = Account_Balance × Quarter_Kelly_Fraction (capped at 2%)
```

**Factor 1: Confluence Score Multiplier (F1)**

| Setup Grade | Confluence Score | F1 Multiplier | Rationale |
|-------------|-----------------|---------------|-----------|
| A+ | 0.80 – 1.00 | 1.50× | Highest conviction — maximum edge |
| A | 0.65 – 0.79 | 1.00× | Standard — full allocation |
| B | 0.50 – 0.64 | 0.50× | Reduced — partial edge |
| C | 0.35 – 0.49 | 0.25× | Minimum — paper trade or skip |
| D | < 0.35 | 0.00× | No trade |

**Factor 2: Market Regime Multiplier (F2)**

| Regime | ADX | Volatility | F2 Multiplier | Rationale |
|--------|-----|-----------|---------------|-----------|
| Strong Trend | > 30 | Normal | 1.20× | Trend persistence favors sizing up |
| Normal Trend | 20–30 | Normal | 1.00× | Baseline |
| Range-Bound | < 20 | Low | 0.60× | Mean reversion — smaller edges |
| High Volatility | Any | > 35% ann. | 0.40× | Uncertainty premium — size down hard |
| Crisis | Any | > 50% ann. | 0.20× | Capital preservation mode |
| Uncertain | — | — | 0.50× | No consensus — conservative |

*Regime detection from HMM (S2) + volatility clustering + rules-based ensemble.*

**Factor 3: Recent Performance Multiplier (F3)**

| Condition | F3 Multiplier | Rationale |
|-----------|---------------|-----------|
| Last 5 trades: 4+ wins | 1.10× | Positive momentum — slight increase |
| Last 5 trades: 3 wins | 1.00× | Neutral |
| Last 5 trades: ≤ 2 wins | 0.70× | Cool-down — reduce exposure |
| 3 consecutive losses | 0.50× | Circuit breaker — half size |
| 5 consecutive losses | 0.00× | Full stop — no new trades |

*F3 implements anti-martingale: increase when winning, decrease when losing.*

**Factor 4: Volatility-Adjusted Sizing (F4)**

```
F4 = Target_Volatility / Current_Realized_Volatility

Target_Volatility = 15% annualized (configurable)
Current_Realized_Volatility = 20-day annualized standard deviation

Example:
  Current vol = 25% → F4 = 15/25 = 0.60 (size down)
  Current vol = 10% → F4 = 15/10 = 1.50 (size up, capped at 1.5)
  Current vol = 40% → F4 = 15/40 = 0.38 (aggressive reduction)

F4 is capped: min(F4, 1.5) — never more than 1.5× from volatility alone.
```

#### 2.1.3 Hard Caps (Absolute Limits)

No combination of factors can exceed these caps:

| Limit | Value | Override |
|-------|-------|---------|
| Max risk per trade | 2.0% of account | Never |
| Max total open exposure | 6.0% of account | Never |
| Max correlated exposure | 3.0% across correlated pairs | Never |
| Max daily loss | 4.0% of account | Never |
| Max concurrent positions | 5 (forex), 3 (crypto) | Configurable |
| Max margin utilization | 30% | Never |
| Max single exchange exposure | 5% of capital (crypto) | Never |

#### 2.1.4 Correlation-Adjusted Sizing

```
When correlation > 0.7 between two open positions:
  Combined_Risk = Σ(Individual_Risks) × (1 + max_correlation × 0.5)

If Combined_Risk > 2.5%:
  Reduce each position proportionally until Combined_Risk ≤ 2.5%

Example:
  EUR/USD long: 1.0% risk
  GBP/USD long: 1.0% risk
  Correlation: 0.85
  Combined: 2.0% × (1 + 0.85 × 0.5) = 2.85% → EXCEEDS 2.5%
  Solution: Reduce each to 0.88% → Combined: 1.76% × 1.425 = 2.51% ≈ OK
```

#### 2.1.5 Account Growth Scaling

| Account Size | Max Risk/Trade | Max Open Exposure | Max Correlated | Kelly Fraction |
|-------------|---------------|-------------------|----------------|---------------|
| $1K – $5K | 1.0% | 3.0% | 1.5% | 0.20 (1/5 Kelly) |
| $5K – $25K | 1.5% | 4.5% | 2.5% | 0.25 (Quarter Kelly) |
| $25K – $100K | 1.5% | 5.0% | 3.0% | 0.25 (Quarter Kelly) |
| $100K – $500K | 1.0% | 4.0% | 2.5% | 0.20 (1/5 Kelly) |
| $500K+ | 0.75% | 3.0% | 2.0% | 0.15 (Conservative) |

*As capital grows, percentage risk decreases because absolute dollar risk increases and recovery from drawdowns becomes harder.*

#### 2.1.6 Risk Parity Implementation

Instead of equal percentage risk per trade, equalize **dollar risk contribution** across pairs:

```
Position_Size_i = (Total_Risk_Budget / N_pairs) / (ATR_i × Pip_Value_i)

This means:
  EUR/USD (ATR 80 pips):  Standard size
  GBP/JPY (ATR 150 pips): Smaller size (higher volatility pair)
  USD/CHF (ATR 60 pips):  Larger size (lower volatility pair)

Each pair contributes EQUAL dollar risk to the portfolio,
regardless of individual pair volatility.
```

#### 2.1.7 TCA-Aware Sizing (Micro-Account Adjustment)

For accounts under $100, transaction costs dominate. The sizing engine applies a **cost-adjustment factor**:

```
Cost_Per_Trade = Spread_Cost + Commission + Estimated_Slippage
Cost_As_Pct = Cost_Per_Trade / Account_Balance

If Cost_As_Pct > 1.5%:
  Warning: "Trading costs exceed 1.5% per trade — account may not be viable"
  Adjustment: Reduce position count, increase minimum R:R requirement

If Cost_As_Pct > 3.0%:
  CRITICAL: "Trading costs exceed 3% — account will drain from costs alone"
  Action: Block new trades, recommend capital increase

Minimum R:R enforcement:
  If Cost_Per_Trade > 0.15% of account → Min R:R = 2:1 (costs require wider targets)
  If Cost_Per_Trade > 0.50% of account → Min R:R = 3:1
  If Cost_Per_Trade > 1.00% of account → Min R:R = 5:1 or skip trade
```

### 2.2 Position Sizing Engine Implementation

```python
class PositionSizingEngine:
    """
    Quarter-Kelly position sizing with dynamic 4-factor adjustment.
    Hard limits are enforced at the code level — no override possible.
    """
    
    # === HARD LIMITS (IMMUTABLE) ===
    MAX_RISK_PER_TRADE = 0.02       # 2% absolute max
    MAX_TOTAL_EXPOSURE = 0.06       # 6% total open risk
    MAX_CORRELATED_EXPOSURE = 0.03  # 3% across correlated pairs
    MAX_DAILY_LOSS = 0.04           # 4% daily circuit breaker
    MAX_CONCURRENT_POSITIONS = 5
    MAX_MARGIN_UTILIZATION = 0.30   # 30%
    MAX_SINGLE_EXCHANGE = 0.05      # 5% per exchange (crypto)
    
    def __init__(self, config: dict):
        self.kelly_fraction = config.get('kelly_fraction', 0.25)
        self.target_volatility = config.get('target_volatility', 0.15)
        self.account_tiers = config.get('account_tiers', self._default_tiers())
    
    async def calculate(
        self,
        setup: TradeSetup,
        account: AccountState,
        market_state: MarketState,
        open_positions: list[Position],
        recent_trades: list[TradeResult]
    ) -> PositionSizeResult:
        """Calculate final position size with full audit trail."""
        
        # Step 1: Get account tier limits
        tier = self._get_account_tier(account.balance)
        
        # Step 2: Calculate Kelly base risk
        kelly_f = self._calculate_kelly(recent_trades, tier.kelly_fraction)
        base_risk = account.balance * kelly_f
        
        # Step 3: Apply 4-factor adjustment
        f1 = self._confluence_factor(setup.confluence_score)
        f2 = self._regime_factor(market_state.regime, market_state.adx)
        f3 = self._performance_factor(recent_trades)
        f4 = self._volatility_factor(market_state.realized_volatility)
        
        adjusted_risk = base_risk * f1 * f2 * f3 * f4
        
        # Step 4: Apply correlation adjustment
        corr_factor = self._correlation_adjustment(
            setup.pair, setup.direction, open_positions
        )
        adjusted_risk *= corr_factor
        
        # Step 5: Apply TCA-aware adjustment (micro accounts)
        tca_factor = self._tca_adjustment(setup, account)
        adjusted_risk *= tca_factor
        
        # Step 6: Enforce hard caps (NEVER bypassed)
        final_risk = min(
            adjusted_risk,
            account.balance * tier.max_risk_per_trade,        # Per-trade cap
            account.balance * tier.max_total_exposure - self._current_exposure(open_positions),  # Total cap
            account.balance * self.MAX_DAILY_LOSS - abs(account.daily_pnl),  # Daily loss cap
        )
        
        # Step 7: Convert to lot size
        sl_pips = setup.stop_loss_distance_pips
        pip_value = get_pip_value(setup.pair, account.currency)
        lot_size = final_risk / (sl_pips * pip_value) if sl_pips > 0 else 0
        
        # Step 8: Minimum viable check
        if lot_size < setup.min_lot_size:
            return PositionSizeResult(
                approved=False,
                reason="Calculated size below minimum lot — insufficient edge after costs",
                risk_amount=0,
                lot_size=0
            )
        
        # Step 9: Final approval
        approved = final_risk > 0 and lot_size >= setup.min_lot_size
        
        return PositionSizeResult(
            approved=approved,
            risk_amount=final_risk,
            risk_pct=final_risk / account.balance * 100,
            lot_size=round(lot_size, 2),
            breakdown={
                'kelly_f': kelly_f,
                'base_risk': base_risk,
                'f1_confluence': f1,
                'f2_regime': f2,
                'f3_performance': f3,
                'f4_volatility': f4,
                'correlation_factor': corr_factor,
                'tca_factor': tca_factor,
                'tier_limit': tier.max_risk_per_trade,
                'hard_cap_applied': final_risk < adjusted_risk
            },
            reason="Approved" if approved else "Rejected"
        )
    
    def _calculate_kelly(self, recent_trades: list, fraction: float) -> float:
        """Quarter-Kelly with minimum 100-trade sample requirement."""
        if len(recent_trades) < 30:
            # Insufficient data — use conservative default
            return 0.01  # 1% default
        
        wins = [t for t in recent_trades if t.r_multiple > 0]
        losses = [t for t in recent_trades if t.r_multiple <= 0]
        
        p = len(wins) / len(recent_trades)  # Win rate
        q = 1 - p
        
        avg_win = sum(t.r_multiple for t in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(t.r_multiple for t in losses) / len(losses)) if losses else 1
        
        b = avg_win / avg_loss if avg_loss > 0 else 1  # R:R ratio
        
        # Full Kelly
        full_kelly = (b * p - q) / b if b > 0 else 0
        
        # Apply fraction (quarter-Kelly)
        kelly = max(full_kelly * fraction, 0.005)  # Minimum 0.5%
        
        # Cap at 2% regardless
        return min(kelly, 0.02)
    
    def _confluence_factor(self, score: float) -> float:
        """F1: Higher confluence → larger position."""
        if score >= 0.80: return 1.50
        if score >= 0.65: return 1.00
        if score >= 0.50: return 0.50
        if score >= 0.35: return 0.25
        return 0.00
    
    def _regime_factor(self, regime: str, adx: float) -> float:
        """F2: Regime-aware sizing."""
        regime_map = {
            'strong_trend': 1.20,
            'trending': 1.00,
            'range_bound': 0.60,
            'high_volatility': 0.40,
            'crisis': 0.20,
            'uncertain': 0.50
        }
        return regime_map.get(regime, 0.50)
    
    def _performance_factor(self, recent_trades: list) -> float:
        """F3: Anti-martingale — reduce after losses."""
        if len(recent_trades) < 3:
            return 1.00
        
        last_5 = recent_trades[-5:]
        wins = sum(1 for t in last_5 if t.r_multiple > 0)
        
        # Check consecutive losses
        consec_losses = 0
        for t in reversed(recent_trades):
            if t.r_multiple <= 0:
                consec_losses += 1
            else:
                break
        
        if consec_losses >= 5: return 0.00  # Full stop
        if consec_losses >= 3: return 0.50  # Circuit breaker
        
        if wins >= 4: return 1.10
        if wins >= 3: return 1.00
        return 0.70
    
    def _volatility_factor(self, realized_vol: float) -> float:
        """F4: Inverse volatility sizing for constant risk contribution."""
        if realized_vol <= 0:
            return 1.00
        factor = self.target_volatility / realized_vol
        return min(max(factor, 0.25), 1.50)  # Bounded [0.25, 1.50]
    
    def _correlation_adjustment(
        self, pair: str, direction: Direction, open_positions: list
    ) -> float:
        """Reduce sizing when correlated positions are open."""
        if not open_positions:
            return 1.00
        
        max_corr = 0.0
        for pos in open_positions:
            corr = get_correlation(pair, pos.pair, window=20)
            if direction == pos.direction:
                max_corr = max(max_corr, abs(corr))
        
        if max_corr > 0.7:
            return 1.0 / (1.0 + max_corr * 0.5)
        return 1.00
    
    def _tca_adjustment(self, setup: TradeSetup, account: AccountState) -> float:
        """Adjust for transaction costs on small accounts."""
        cost_per_trade = setup.estimated_spread_cost + setup.estimated_commission
        cost_pct = cost_per_trade / account.balance * 100
        
        if cost_pct > 3.0:
            return 0.00  # Block — costs too high
        if cost_pct > 1.5:
            return 0.50  # Halve size
        if cost_pct > 0.5:
            return 0.80  # Slight reduction
        return 1.00
    
    def _current_exposure(self, positions: list) -> float:
        """Sum of all open position risks as dollar amount."""
        return sum(p.risk_amount for p in positions)
```

---

## 3. Drawdown Limit System

### 3.1 Five-Stage Drawdown Framework

The drawdown system uses five stages with escalating responses. Each stage triggers automatically — no human intervention required.

```
EQUITY CURVE:

100% ───────────────────────────────────────────────────────────
      │ ████████████████████████████████
 97%  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ← GREEN (0-3%): Normal ops
      │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
 93%  │ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒ ← YELLOW (3-7%): Reduce size
      │ ████████████████████████████
 88%  │ ████████████████████████████    ← ORANGE (7-12%): Defensive
      │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
 82%  │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓        ← RED (12-18%): Crisis mode
      │ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
 80%  │ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒             ← BLACK (>18%): Full halt
```

### 3.2 Stage Definitions

| Stage | Drawdown Range | Color | State | Automatic Actions |
|-------|---------------|-------|-------|-------------------|
| **GREEN** | 0% – 3% | 🟢 | Normal Operations | No restrictions. Full position sizing. |
| **YELLOW** | 3% – 7% | 🟡 | Caution | Reduce new position sizes by 50%. Tighten all stops by 0.2 ATR. Max 3 concurrent positions. Alert human. |
| **ORANGE** | 7% – 12% | 🟠 | Defensive | Close all positions with >5% unrealized loss. Hedge remaining with inverse positions. Reduce to 25% normal size. No new counter-trend trades. |
| **RED** | 12% – 18% | 🔴 | Crisis Mode | Close 75% of all positions. Move remaining to cash equivalent. Only allow A+ setups at 10% normal size. Human review required for any new trade. |
| **BLACK** | > 18% | ⚫ | System Halt | Close ALL positions immediately. Halt ALL trading. Alert human with full diagnostic. System requires manual restart with explicit confirmation. |

### 3.3 Stage Transition Logic

```python
class DrawdownLimitManager:
    """
    Five-stage drawdown management with automatic escalation and de-escalation.
    """
    
    STAGES = {
        'GREEN':  {'min': 0.00, 'max': 0.03, 'severity': 'INFO'},
        'YELLOW': {'min': 0.03, 'max': 0.07, 'severity': 'WARNING'},
        'ORANGE': {'min': 0.07, 'max': 0.12, 'severity': 'CRITICAL'},
        'RED':    {'min': 0.12, 'max': 0.18, 'severity': 'EMERGENCY'},
        'BLACK':  {'min': 0.18, 'max': 1.00, 'severity': 'EMERGENCY'},
    }
    
    def __init__(self, config: dict):
        self.current_stage = 'GREEN'
        self.high_water_mark = 0.0
        self.stage_entry_time = {}
        self.daily_pnl = 0.0
        self.event_bus = None  # Injected
    
    async def update(self, account: AccountState) -> DrawdownState:
        """Called on every tick/candle. Returns current drawdown state."""
        
        # Update high water mark
        if account.equity > self.high_water_mark:
            self.high_water_mark = account.equity
        
        # Calculate drawdown from HWM
        if self.high_water_mark > 0:
            drawdown_pct = (self.high_water_mark - account.equity) / self.high_water_mark
        else:
            drawdown_pct = 0.0
        
        # Determine stage
        new_stage = self._determine_stage(drawdown_pct)
        
        # Handle stage transition
        if new_stage != self.current_stage:
            await self._handle_stage_transition(self.current_stage, new_stage, drawdown_pct, account)
            self.current_stage = new_stage
            self.stage_entry_time[new_stage] = datetime.utcnow()
        
        # Update daily P&L
        self.daily_pnl = account.equity - account.day_start_equity
        
        return DrawdownState(
            current_stage=self.current_stage,
            drawdown_pct=drawdown_pct,
            drawdown_amount=self.high_water_mark - account.equity,
            high_water_mark=self.high_water_mark,
            daily_pnl=self.daily_pnl,
            daily_pnl_pct=self.daily_pnl / account.day_start_equity * 100 if account.day_start_equity > 0 else 0,
            time_in_stage=datetime.utcnow() - self.stage_entry_time.get(self.current_stage, datetime.utcnow())
        )
    
    def _determine_stage(self, drawdown_pct: float) -> str:
        """Map drawdown percentage to stage."""
        if drawdown_pct >= 0.18: return 'BLACK'
        if drawdown_pct >= 0.12: return 'RED'
        if drawdown_pct >= 0.07: return 'ORANGE'
        if drawdown_pct >= 0.03: return 'YELLOW'
        return 'GREEN'
    
    async def _handle_stage_transition(
        self, old_stage: str, new_stage: str, drawdown_pct: float, account: AccountState
    ):
        """Execute automatic actions on stage transition."""
        
        severity = self.STAGES[new_stage]['severity']
        
        # Publish event
        await self.event_bus.publish('risk.drawdown', RiskEvent(
            event_type=RiskEventType.DRAWDOWN_STAGE_CHANGE,
            severity=severity,
            component='drawdown_manager',
            data={
                'old_stage': old_stage,
                'new_stage': new_stage,
                'drawdown_pct': drawdown_pct,
                'drawdown_amount': self.high_water_mark - account.equity,
                'account_balance': account.balance
            },
            reasoning=f"Drawdown transitioned from {old_stage} to {new_stage} at {drawdown_pct:.1%}"
        ))
        
        # === ESCALATION ACTIONS ===
        if self._is_escalation(old_stage, new_stage):
            
            if new_stage == 'YELLOW':
                # Reduce new position sizes by 50%, tighten stops
                await self.event_bus.publish('risk.drawdown', RiskEvent(
                    event_type=RiskEventType.DRAWDOWN_LIMIT_BREACH,
                    severity='WARNING',
                    component='drawdown_manager',
                    action_required='REDUCE',
                    data={'size_reduction': 0.50, 'stop_tighten_atr': 0.2}
                ))
            
            elif new_stage == 'ORANGE':
                # Close losing positions, activate hedging
                await self.event_bus.publish('risk.drawdown', RiskEvent(
                    event_type=RiskEventType.DRAWDOWN_LIMIT_BREACH,
                    severity='CRITICAL',
                    component='drawdown_manager',
                    action_required='REDUCE',
                    data={
                        'close_losing_threshold': 0.05,
                        'activate_hedging': True,
                        'size_reduction': 0.75,
                        'no_counter_trend': True
                    }
                ))
            
            elif new_stage == 'RED':
                # Close 75% of positions, cash mode
                await self.event_bus.publish('risk.drawdown', RiskEvent(
                    event_type=RiskEventType.DRAWDOWN_LIMIT_BREACH,
                    severity='EMERGENCY',
                    component='drawdown_manager',
                    action_required='HALT',
                    data={
                        'close_pct': 0.75,
                        'only_a_plus_setups': True,
                        'size_reduction': 0.90,
                        'require_human_review': True
                    }
                ))
            
            elif new_stage == 'BLACK':
                # Close everything, halt system
                await self.event_bus.publish('risk.drawdown', RiskEvent(
                    event_type=RiskEventType.DRAWDOWN_LIMIT_BREACH,
                    severity='EMERGENCY',
                    component='drawdown_manager',
                    action_required='CLOSE_ALL',
                    data={
                        'close_all_positions': True,
                        'halt_trading': True,
                        'require_manual_restart': True
                    }
                ))
    
    def _is_escalation(self, old: str, new: str) -> bool:
        """Check if transition is an escalation (worsening)."""
        order = ['GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK']
        return order.index(new) > order.index(old)
    
    def get_position_size_multiplier(self) -> float:
        """Return the current position size multiplier based on drawdown stage."""
        multipliers = {
            'GREEN': 1.00,
            'YELLOW': 0.50,
            'ORANGE': 0.25,
            'RED': 0.10,
            'BLACK': 0.00
        }
        return multipliers[self.current_stage]
    
    def get_max_concurrent_positions(self) -> int:
        """Return max concurrent positions based on drawdown stage."""
        limits = {
            'GREEN': 5,
            'YELLOW': 3,
            'ORANGE': 2,
            'RED': 1,
            'BLACK': 0
        }
        return limits[self.current_stage]
    
    def is_trading_allowed(self) -> bool:
        """Check if new trades are allowed in current stage."""
        return self.current_stage not in ('BLACK',)
    
    def requires_human_review(self) -> bool:
        """Check if human review is required for new trades."""
        return self.current_stage in ('RED', 'BLACK')
```

### 3.4 Recovery Protocol (De-escalation)

De-escalation requires **sustained recovery**, not just a single profitable trade:

| Transition | Recovery Condition | Minimum Wait |
|-----------|-------------------|-------------|
| BLACK → RED | Manual restart + human confirmation + 24h paper trading | 24 hours |
| RED → ORANGE | Drawdown < 12% for 48 consecutive hours | 48 hours |
| ORANGE → YELLOW | Drawdown < 7% for 24 consecutive hours | 24 hours |
| YELLOW → GREEN | Drawdown < 3% for 12 consecutive hours | 12 hours |

*De-escalation is always slower than escalation. Markets can crash in minutes; recovery takes days.*

---

## 4. Circuit Breaker System

### 4.1 Four-Layer Circuit Breaker Architecture

Circuit breakers are **independent, cascading safety mechanisms**. Each layer operates autonomously and can halt trading without consulting other layers.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CIRCUIT BREAKER SYSTEM                            │
│                                                                      │
│  LAYER 1: POSITION LEVEL (Fastest — millisecond response)           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Per-trade stop-loss: -2% of portfolio (hard stop, no override)│  │
│  │ Trailing stop: -3% from peak position value                   │  │
│  │ Time-based exit: Close positions >48h during crisis regime    │  │
│  │ Slippage breaker: If execution slippage >0.5%, pause entries  │  │
│  │ Spread breaker: If spread >3x normal, block new orders        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  LAYER 2: PORTFOLIO LEVEL (Second — second-level response)          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Daily loss limit: -4% → pause all new entries for 24h         │  │
│  │ Weekly loss limit: -8% → reduce all positions by 50%          │  │
│  │ Monthly loss limit: -12% → full de-risk to cash equivalent    │  │
│  │ Max drawdown: -18% → system halt, human intervention          │  │
│  │ Exposure limit: >6% total risk → block new trades             │  │
│  │ Margin limit: >30% utilization → block new trades             │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  LAYER 3: REGIME LEVEL (Third — market-condition response)          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ VIX > 30: Reduce position sizes by 50%                        │  │
│  │ VIX > 50: Reduce to 25% normal size, widen stops 2x           │  │
│  │ VIX > 70: Cash-only mode, no new positions                    │  │
│  │ Correlation spike (>0.8 cross-asset): Activate hedging mode    │  │
│  │ Regime uncertain >5 days: Enter defensive mode                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  LAYER 4: SYSTEM LEVEL (Fourth — infrastructure response)           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Exchange connectivity loss >30s: Close positions on that exch  │  │
│  │ Data feed anomaly: Cross-validate, halt if inconsistent       │  │
│  │ Order rejection rate >10%: Pause all trading                  │  │
│  │ Latency spike >10x normal: Cancel all open orders             │  │
│  │ Event bus failure: Enter safe mode, close all positions       │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Circuit Breaker Implementation

```python
class CircuitBreakerSystem:
    """
    Four-layer circuit breaker system. Each layer is independent.
    Any single breaker can halt trading without consulting others.
    """
    
    # === LAYER 1: POSITION LEVEL ===
    POSITION_STOP_PCT = 0.02           # 2% per-trade hard stop
    TRAILING_STOP_PCT = 0.03           # 3% trailing from peak
    SLIPPAGE_BREAKER_PCT = 0.005       # 0.5% slippage pause
    SPREAD_BREAKER_MULTIPLIER = 3.0    # 3x normal spread
    CRISIS_TIME_LIMIT_HOURS = 48       # Close after 48h in crisis
    
    # === LAYER 2: PORTFOLIO LEVEL ===
    DAILY_LOSS_LIMIT = 0.04            # 4% daily
    WEEKLY_LOSS_LIMIT = 0.08           # 8% weekly
    MONTHLY_LOSS_LIMIT = 0.12          # 12% monthly
    MAX_DRAWDOWN_HALT = 0.18           # 18% system halt
    
    # === LAYER 3: REGIME LEVEL ===
    VIX_CAUTION = 30                   # Reduce 50%
    VIX_HIGH = 50                      # Reduce 75%
    VIX_EXTREME = 70                   # Cash only
    CORRELATION_SPIKE = 0.80           # Cross-asset correlation
    REGIME_UNCERTAIN_DAYS = 5          # Defensive after 5 days
    
    # === LAYER 4: SYSTEM LEVEL ===
    CONNECTIVITY_TIMEOUT_SEC = 30      # Close positions if disconnected
    ORDER_REJECTION_THRESHOLD = 0.10   # 10% rejection rate
    LATENCY_SPIKE_MULTIPLIER = 10      # 10x normal latency
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.breaker_states = {}       # Track which breakers are tripped
        self.trip_times = {}           # When each breaker tripped
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.monthly_pnl = 0.0
    
    # === LAYER 1 CHECKS ===
    
    async def check_position_stop(self, position: Position, current_price: float) -> bool:
        """Layer 1: Check if position stop-loss is triggered."""
        if position.direction == Direction.LONG:
            pnl_pct = (current_price - position.entry_price) / position.entry_price
        else:
            pnl_pct = (position.entry_price - current_price) / position.entry_price
        
        # Hard stop
        if pnl_pct <= -self.POSITION_STOP_PCT:
            await self._trip_breaker('position_stop', {
                'position_id': position.ticket,
                'pnl_pct': pnl_pct,
                'action': 'close_position'
            })
            return True
        
        # Trailing stop
        if position.peak_pnl > 0:
            drawdown_from_peak = position.peak_pnl - pnl_pct
            if drawdown_from_peak >= self.TRAILING_STOP_PCT:
                await self._trip_breaker('trailing_stop', {
                    'position_id': position.ticket,
                    'peak_pnl': position.peak_pnl,
                    'current_pnl': pnl_pct,
                    'drawdown_from_peak': drawdown_from_peak,
                    'action': 'close_position'
                })
                return True
        
        return False
    
    async def check_slippage(self, expected_price: float, fill_price: float, pair: str) -> bool:
        """Layer 1: Check if execution slippage exceeds breaker."""
        slippage = abs(fill_price - expected_price) / expected_price
        
        if slippage > self.SLIPPAGE_BREAKER_PCT:
            await self._trip_breaker('slippage', {
                'pair': pair,
                'expected': expected_price,
                'fill': fill_price,
                'slippage_pct': slippage,
                'action': 'pause_new_entries'
            })
            return True
        return False
    
    async def check_spread(self, current_spread: float, avg_spread: float, pair: str) -> bool:
        """Layer 1: Check if spread exceeds breaker."""
        if avg_spread > 0 and current_spread / avg_spread > self.SPREAD_BREAKER_MULTIPLIER:
            await self._trip_breaker('spread', {
                'pair': pair,
                'current_spread': current_spread,
                'avg_spread': avg_spread,
                'multiplier': current_spread / avg_spread,
                'action': 'block_new_orders'
            })
            return True
        return False
    
    # === LAYER 2 CHECKS ===
    
    async def check_portfolio_loss(self, account: AccountState) -> bool:
        """Layer 2: Check daily/weekly/monthly loss limits."""
        
        # Daily
        daily_loss = abs(min(account.daily_pnl, 0))
        if daily_loss / account.day_start_equity >= self.DAILY_LOSS_LIMIT:
            await self._trip_breaker('daily_loss', {
                'daily_pnl': account.daily_pnl,
                'loss_pct': daily_loss / account.day_start_equity,
                'action': 'pause_24h'
            })
            return True
        
        # Weekly
        weekly_loss = abs(min(account.weekly_pnl, 0))
        if weekly_loss / account.week_start_equity >= self.WEEKLY_LOSS_LIMIT:
            await self._trip_breaker('weekly_loss', {
                'weekly_pnl': account.weekly_pnl,
                'loss_pct': weekly_loss / account.week_start_equity,
                'action': 'reduce_50pct'
            })
            return True
        
        # Monthly
        monthly_loss = abs(min(account.monthly_pnl, 0))
        if monthly_loss / account.month_start_equity >= self.MONTHLY_LOSS_LIMIT:
            await self._trip_breaker('monthly_loss', {
                'monthly_pnl': account.monthly_pnl,
                'loss_pct': monthly_loss / account.month_start_equity,
                'action': 'full_derisk'
            })
            return True
        
        return False
    
    # === LAYER 3 CHECKS ===
    
    async def check_regime_breakers(self, market_state: MarketState) -> bool:
        """Layer 3: Check market regime conditions."""
        tripped = False
        
        # VIX-based breakers
        if market_state.vix >= self.VIX_EXTREME:
            await self._trip_breaker('vix_extreme', {
                'vix': market_state.vix,
                'action': 'cash_only'
            })
            tripped = True
        elif market_state.vix >= self.VIX_HIGH:
            await self._trip_breaker('vix_high', {
                'vix': market_state.vix,
                'action': 'reduce_75pct'
            })
            tripped = True
        elif market_state.vix >= self.VIX_CAUTION:
            await self._trip_breaker('vix_caution', {
                'vix': market_state.vix,
                'action': 'reduce_50pct'
            })
            tripped = True
        
        # Correlation spike
        if market_state.cross_asset_correlation >= self.CORRELATION_SPIKE:
            await self._trip_breaker('correlation_spike', {
                'correlation': market_state.cross_asset_correlation,
                'action': 'hedging_mode'
            })
            tripped = True
        
        return tripped
    
    # === LAYER 4 CHECKS ===
    
    async def check_system_health(self, system_state: SystemState) -> bool:
        """Layer 4: Check infrastructure health."""
        tripped = False
        
        # Connectivity
        for broker, status in system_state.broker_status.items():
            if status.disconnected_duration_sec > self.CONNECTIVITY_TIMEOUT_SEC:
                await self._trip_breaker('connectivity', {
                    'broker': broker,
                    'disconnected_sec': status.disconnected_duration_sec,
                    'action': 'close_broker_positions'
                })
                tripped = True
        
        # Order rejections
        if system_state.order_rejection_rate > self.ORDER_REJECTION_THRESHOLD:
            await self._trip_breaker('order_rejection', {
                'rejection_rate': system_state.order_rejection_rate,
                'action': 'pause_trading'
            })
            tripped = True
        
        # Latency
        if system_state.latency_multiplier > self.LATENCY_SPIKE_MULTIPLIER:
            await self._trip_breaker('latency', {
                'latency_multiplier': system_state.latency_multiplier,
                'action': 'cancel_open_orders'
            })
            tripped = True
        
        return tripped
    
    # === BREAKER MANAGEMENT ===
    
    async def _trip_breaker(self, breaker_name: str, data: dict):
        """Trip a circuit breaker and publish event."""
        self.breaker_states[breaker_name] = 'TRIPPED'
        self.trip_times[breaker_name] = datetime.utcnow()
        
        await self.event_bus.publish('risk.circuit_breaker', RiskEvent(
            event_type=RiskEventType.CIRCUIT_BREAKER_TRIPPED,
            severity='CRITICAL',
            component=f'circuit_breaker.{breaker_name}',
            data=data,
            action_required=data.get('action', 'HALT'),
            reasoning=f"Circuit breaker '{breaker_name}' tripped: {data}"
        ))
    
    async def reset_breaker(self, breaker_name: str, reason: str):
        """Reset a tripped breaker (requires human confirmation for critical breakers)."""
        if breaker_name in self.breaker_states:
            self.breaker_states[breaker_name] = 'NORMAL'
            
            await self.event_bus.publish('risk.circuit_breaker', RiskEvent(
                event_type=RiskEventType.CIRCUIT_BREAKER_RESET,
                severity='INFO',
                component=f'circuit_breaker.{breaker_name}',
                data={'reason': reason},
                reasoning=f"Circuit breaker '{breaker_name}' reset: {reason}"
            ))
    
    def is_breaker_tripped(self, breaker_name: str = None) -> bool:
        """Check if any (or specific) breaker is tripped."""
        if breaker_name:
            return self.breaker_states.get(breaker_name) == 'TRIPPED'
        return any(v == 'TRIPPED' for v in self.breaker_states.values())
    
    def get_tripped_breakers(self) -> list[str]:
        """Return list of all currently tripped breakers."""
        return [k for k, v in self.breaker_states.items() if v == 'TRIPPED']
```

### 4.3 Circuit Breaker Reset Protocol

| Breaker Layer | Auto-Reset? | Reset Condition | Human Required? |
|--------------|------------|-----------------|----------------|
| Position stop | Yes | Next candle close | No |
| Slippage | Yes | After 5 minutes | No |
| Spread | Yes | Spread normalizes (<1.5x) | No |
| Daily loss | Yes | Next trading day (00:00 UTC) | No |
| Weekly loss | No | Manual review + 24h paper trading | Yes |
| Monthly loss | No | Manual review + strategy reassessment | Yes |
| VIX-based | Yes | VIX drops below threshold for 4h | No |
| Correlation | Yes | Correlation drops below 0.6 for 24h | No |
| Connectivity | Yes | Broker reconnects + 60s stability | No |
| Order rejection | No | Manual review of rejection cause | Yes |
| Latency | Yes | Latency returns to normal for 5min | No |

---

## 5. Correlation Monitoring

### 5.1 Real-Time Cross-Pair Correlation Engine

```python
class CorrelationMonitor:
    """
    Real-time correlation monitoring across all traded pairs.
    Detects correlation convergence (crisis signal) and divergence (rotation signal).
    """
    
    def __init__(self, config: dict):
        self.window_short = config.get('window_short', 20)    # 20-period rolling
        self.window_long = config.get('window_long', 100)      # 100-period baseline
        self.spike_threshold = config.get('spike_threshold', 0.70)
        self.crisis_threshold = config.get('crisis_threshold', 0.85)
        self.event_bus = None
        
        # Correlation matrices
        self.current_correlations = {}     # Short-window rolling
        self.baseline_correlations = {}    # Long-window baseline
        self.correlation_history = []      # For regime detection
    
    async def update(self, returns_matrix: dict[str, list[float]]):
        """
        Called on every candle close.
        returns_matrix: {pair: [recent_returns]} for all active pairs.
        """
        
        # Calculate short-window correlation matrix
        self.current_correlations = self._calculate_correlation_matrix(
            returns_matrix, self.window_short
        )
        
        # Calculate long-window baseline
        self.baseline_correlations = self._calculate_correlation_matrix(
            returns_matrix, self.window_long
        )
        
        # Detect spikes
        correlation_spike = self._detect_spike()
        
        # Check for crisis-level convergence
        mean_current = self._mean_off_diagonal(self.current_correlations)
        mean_baseline = self._mean_off_diagonal(self.baseline_correlations)
        spike_magnitude = mean_current - mean_baseline
        
        # === CRISIS DETECTION ===
        if mean_current >= self.crisis_threshold:
            await self.event_bus.publish('risk.correlation', RiskEvent(
                event_type=RiskEventType.CORRELATION_REGIME_SHIFT,
                severity='EMERGENCY',
                component='correlation_monitor',
                data={
                    'mean_correlation': mean_current,
                    'baseline_correlation': mean_baseline,
                    'spike_magnitude': spike_magnitude,
                    'regime': 'CRISIS_CONVERGENCE'
                },
                action_required='REDUCE',
                reasoning=f"Cross-asset correlation at {mean_current:.2f} — crisis convergence detected"
            ))
        
        # === SPIKE DETECTION ===
        elif spike_magnitude >= self.spike_threshold:
            await self.event_bus.publish('risk.correlation', RiskEvent(
                event_type=RiskEventType.CORRELATION_SPIKE,
                severity='WARNING',
                component='correlation_monitor',
                data={
                    'mean_correlation': mean_current,
                    'baseline_correlation': mean_baseline,
                    'spike_magnitude': spike_magnitude,
                    'spiked_pairs': correlation_spike
                },
                action_required='REDUCE',
                reasoning=f"Correlation spike of {spike_magnitude:.2f} detected — diversification failing"
            ))
        
        # Record for history
        self.correlation_history.append({
            'timestamp': datetime.utcnow(),
            'mean_correlation': mean_current,
            'max_pair_correlation': self._max_off_diagonal(self.current_correlations),
            'regime': self._classify_correlation_regime(mean_current)
        })
    
    def get_effective_risk(self, pair: str, direction: Direction, open_positions: list) -> float:
        """
        Calculate effective risk considering correlations.
        Returns multiplier to apply to position sizing.
        """
        if not open_positions:
            return 1.0
        
        max_corr = 0.0
        for pos in open_positions:
            corr = self.current_correlations.get(
                (min(pair, pos.pair), max(pair, pos.pair)), 0.0
            )
            if direction == pos.direction:
                max_corr = max(max_corr, abs(corr))
        
        if max_corr > 0.7:
            return 1.0 / (1.0 + max_corr * 0.5)
        return 1.0
    
    def _calculate_correlation_matrix(self, returns: dict, window: int) -> dict:
        """Calculate pairwise correlation for all pairs."""
        pairs = sorted(returns.keys())
        matrix = {}
        
        for i, p1 in enumerate(pairs):
            for j, p2 in enumerate(pairs):
                if i >= j:
                    continue
                key = (p1, p2)
                r1 = returns[p1][-window:]
                r2 = returns[p2][-window:]
                
                if len(r1) >= window * 0.8 and len(r2) >= window * 0.8:
                    matrix[key] = self._pearson_correlation(r1, r2)
                else:
                    matrix[key] = 0.0
        
        return matrix
    
    def _detect_spike(self) -> list[str]:
        """Identify specific pairs with correlation spikes."""
        spiked = []
        for pair, corr in self.current_correlations.items():
            baseline = self.baseline_correlations.get(pair, 0.0)
            if corr - baseline > 0.3:  # 0.3 spike threshold per pair
                spiked.append(f"{pair[0]}/{pair[1]}: {baseline:.2f} → {corr:.2f}")
        return spiked
    
    def _mean_off_diagonal(self, matrix: dict) -> float:
        """Mean of all pairwise correlations."""
        if not matrix:
            return 0.0
        return sum(abs(v) for v in matrix.values()) / len(matrix)
    
    def _max_off_diagonal(self, matrix: dict) -> float:
        """Maximum pairwise correlation."""
        if not matrix:
            return 0.0
        return max(abs(v) for v in matrix.values())
    
    def _classify_correlation_regime(self, mean_corr: float) -> str:
        """Classify current correlation environment."""
        if mean_corr >= 0.85: return 'CRISIS'
        if mean_corr >= 0.70: return 'ELEVATED'
        if mean_corr >= 0.50: return 'NORMAL'
        if mean_corr >= 0.30: return 'LOW'
        return 'DIVERSIFIED'
    
    @staticmethod
    def _pearson_correlation(x: list, y: list) -> float:
        """Calculate Pearson correlation coefficient."""
        n = min(len(x), len(y))
        if n < 2:
            return 0.0
        
        x, y = x[:n], y[:n]
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        
        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y)) / n
        std_x = (sum((xi - mean_x) ** 2 for xi in x) / n) ** 0.5
        std_y = (sum((yi - mean_y) ** 2 for yi in y) / n) ** 0.5
        
        if std_x == 0 or std_y == 0:
            return 0.0
        
        return cov / (std_x * std_y)
```

### 5.2 Correlation Regime Classification

| Regime | Mean Correlation | Max Pair Correlation | Action |
|--------|-----------------|---------------------|--------|
| **Diversified** | < 0.30 | < 0.50 | Full sizing, all strategies active |
| **Low** | 0.30 – 0.50 | 0.50 – 0.65 | Normal operations, monitor |
| **Normal** | 0.50 – 0.70 | 0.65 – 0.80 | Standard operations, correlation-aware sizing |
| **Elevated** | 0.70 – 0.85 | 0.80 – 0.90 | Reduce positions 50%, activate hedging mode |
| **Crisis** | > 0.85 | > 0.90 | Emergency: reduce to 25%, cash-heavy, tail hedges |

### 5.3 Cross-Asset Correlation Matrix

Beyond forex pairs, monitor cross-asset correlations:

```
FOREX ←→ CRYPTO:    BTC/USD ↔ AUD/USD (~0.6), BTC/USD ↔ Gold (~0.3)
FOREX ←→ EQUITY:    EUR/USD ↔ S&P 500 (~0.4), USD/JPY ↔ Nikkei (~0.5)
FOREX ←→ BONDS:     EUR/USD ↔ US 10Y (~-0.3), USD/CHF ↔ German Bunds (~-0.4)
CRYPTO ←→ EQUITY:   BTC ↔ NASDAQ (~0.6), BTC ↔ S&P (~0.5)
VIX ←→ ALL:         VIX ↔ Equities (~-0.8), VIX ↔ Crypto (~-0.5)

Crisis convergence: ALL correlations → ±1.0. Diversification vanishes.
```

---

## 6. Tail Risk Management

### 6.1 CVaR (Conditional Value at Risk) Framework

VaR is insufficient for Alpha Stack. CVaR measures the **average loss in the worst X% of cases**, capturing tail severity.

```
VaR (95%):   "We won't lose more than $X 95% of the time"
CVaR (95%):  "In the worst 5% of cases, our average loss is $Y"

CVaR = E[Loss | Loss > VaR]

Why CVaR > VaR:
1. CVaR is a coherent risk measure (satisfies subadditivity) — VaR is not
2. CVaR captures SEVERITY of tail events, not just probability
3. CVaR encourages proper diversification (VaR can be gamed)
4. Basel III/IV direction is toward CVaR
```

### 6.2 CVaR Implementation

```python
class TailRiskManager:
    """
    CVaR-based tail risk management with stress testing and scenario analysis.
    """
    
    def __init__(self, config: dict):
        self.confidence_level = config.get('confidence_level', 0.95)
        self.cvar_limit = config.get('cvar_limit', 0.05)  # 5% of portfolio
        self.stress_test_frequency = config.get('stress_test_frequency', 'weekly')
        self.event_bus = None
        
        # Historical scenarios for stress testing
        self.historical_scenarios = self._load_historical_scenarios()
        self.hypothetical_scenarios = self._load_hypothetical_scenarios()
    
    async def calculate_cvar(
        self, portfolio: Portfolio, returns_history: list[float], horizon_days: int = 1
    ) -> CVaRResult:
        """
        Calculate CVaR for current portfolio.
        Uses historical simulation + Cornish-Fisher expansion for fat tails.
        """
        
        # Method 1: Historical CVaR
        sorted_returns = sorted(returns_history)
        cutoff_index = int(len(sorted_returns) * (1 - self.confidence_level))
        tail_returns = sorted_returns[:cutoff_index]
        
        historical_cvar = -sum(tail_returns) / len(tail_returns) if tail_returns else 0
        
        # Method 2: Parametric CVaR (Cornish-Fisher for fat tails)
        mean_ret = sum(returns_history) / len(returns_history)
        std_ret = (sum((r - mean_ret) ** 2 for r in returns_history) / len(returns_history)) ** 0.5
        
        # Skewness and kurtosis adjustment
        skew = self._skewness(returns_history)
        kurt = self._kurtosis(returns_history)
        
        z = self._norm_ppf(1 - self.confidence_level)
        z_cf = z + (z**2 - 1) * skew / 6 + (z**3 - 3*z) * kurt / 24 - (2*z**3 - 5*z) * skew**2 / 36
        
        parametric_cvar = -(mean_ret + z_cf * std_ret)
        
        # Use the more conservative (higher) estimate
        cvar = max(historical_cvar, parametric_cvar)
        
        # Scale to portfolio
        cvar_dollar = cvar * portfolio.equity * (horizon_days ** 0.5)
        cvar_pct = cvar_dollar / portfolio.equity * 100
        
        # Check against limit
        breach = cvar_pct > self.cvar_limit * 100
        
        if breach:
            await self.event_bus.publish('risk.tail', RiskEvent(
                event_type=RiskEventType.CVAR_BREACH,
                severity='CRITICAL',
                component='tail_risk_manager',
                data={
                    'cvar_pct': cvar_pct,
                    'cvar_dollar': cvar_dollar,
                    'limit_pct': self.cvar_limit * 100,
                    'historical_cvar': historical_cvar,
                    'parametric_cvar': parametric_cvar,
                    'horizon_days': horizon_days
                },
                action_required='REDUCE',
                reasoning=f"CVaR ({cvar_pct:.1f}%) exceeds limit ({self.cvar_limit*100:.1f}%)"
            ))
        
        return CVaRResult(
            cvar_pct=cvar_pct,
            cvar_dollar=cvar_dollar,
            var_95=self._calculate_var(returns_history, 0.95),
            historical_cvar=historical_cvar,
            parametric_cvar=parametric_cvar,
            breach=breach,
            tail_shape={
                'skewness': skew,
                'kurtosis': kurt,
                'tail_index': self._hill_estimator(tail_returns)
            }
        )
    
    # === STRESS TESTING ===
    
    async def run_stress_tests(self, portfolio: Portfolio) -> StressTestResult:
        """Run all stress scenarios against current portfolio."""
        results = {}
        
        # Historical scenarios
        for name, scenario in self.historical_scenarios.items():
            impact = self._apply_scenario(portfolio, scenario)
            results[name] = impact
        
        # Hypothetical scenarios
        for name, scenario in self.hypothetical_scenarios.items():
            impact = self._apply_scenario(portfolio, scenario)
            results[name] = impact
        
        # Reverse stress test: what would kill us?
        kill_scenario = self._reverse_stress_test(portfolio)
        results['reverse_kill'] = kill_scenario
        
        # Check if any scenario exceeds tolerance
        worst_case = max(results.values(), key=lambda r: r['portfolio_loss_pct'])
        
        if worst_case['portfolio_loss_pct'] > 0.15:  # 15% loss tolerance
            await self.event_bus.publish('risk.tail', RiskEvent(
                event_type=RiskEventType.STRESS_TEST_FAIL,
                severity='CRITICAL',
                component='tail_risk_manager',
                data={
                    'worst_scenario': worst_case['scenario_name'],
                    'worst_loss_pct': worst_case['portfolio_loss_pct'],
                    'all_scenarios': results
                },
                action_required='REDUCE',
                reasoning=f"Stress test '{worst_case['scenario_name']}' shows {worst_case['portfolio_loss_pct']:.1%} loss"
            ))
        
        return StressTestResult(
            scenarios=results,
            worst_case=worst_case,
            passed=worst_case['portfolio_loss_pct'] <= 0.15
        )
    
    def _load_historical_scenarios(self) -> dict:
        """Historical crisis scenarios with market impacts."""
        return {
            'chf_unpeg_2015': {
                'name': 'Swiss Franc Unpegging (2015)',
                'description': 'EUR/CHF -30% in 15 minutes, zero liquidity',
                'forex_impacts': {
                    'EUR/CHF': -0.30, 'USD/CHF': -0.25, 'EUR/USD': -0.03,
                    'GBP/CHF': -0.28, 'AUD/CHF': -0.22
                },
                'volatility_impact': 3.0,  # 3x normal volatility
                'liquidity_impact': 0.1,    # 10% of normal liquidity
                'spread_impact': 10.0,      # 10x normal spread
                'duration_hours': 2
            },
            'covid_crash_2020': {
                'name': 'COVID-19 Crash (2020)',
                'description': 'S&P -34% in 23 days, VIX 82, everything correlated',
                'forex_impacts': {
                    'EUR/USD': -0.05, 'GBP/USD': -0.08, 'AUD/USD': -0.12,
                    'NZD/USD': -0.10, 'USD/JPY': +0.05, 'USD/CHF': +0.03
                },
                'crypto_impacts': {
                    'BTC/USD': -0.50, 'ETH/USD': -0.55
                },
                'volatility_impact': 4.0,
                'correlation_impact': 0.95,  # Everything → 1.0
                'duration_days': 23
            },
            'asian_crisis_1997': {
                'name': 'Asian Financial Crisis (1997)',
                'description': 'EM currencies -50-85%, contagion across region',
                'forex_impacts': {
                    'USD/THB': +0.50, 'USD/IDR': +0.85, 'USD/KRW': +0.40,
                    'USD/MYR': +0.45, 'AUD/USD': -0.15
                },
                'volatility_impact': 3.5,
                'contagion': True,
                'duration_months': 18
            },
            'luna_collapse_2022': {
                'name': 'LUNA/UST Collapse (2022)',
                'description': 'LUNA -99.99%, UST depeg, $60B destroyed',
                'crypto_impacts': {
                    'LUNA/USD': -0.9999, 'UST/USD': -0.90,
                    'BTC/USD': -0.25, 'ETH/USD': -0.30
                },
                'contagion_spread': ['3AC', 'Celsius', 'Voyager', 'BlockFi'],
                'duration_days': 5
            },
            'flash_crash_2010': {
                'name': 'Flash Crash (2010)',
                'description': 'Dow -9.2% in 5 minutes, then recovery',
                'equity_impact': -0.092,
                'liquidity_impact': 0.01,  # Near-zero liquidity
                'duration_minutes': 36,
                'recovered': True
            }
        }
    
    def _load_hypothetical_scenarios(self) -> dict:
        """Hypothetical but plausible stress scenarios."""
        return {
            'us_china_conflict': {
                'name': 'US-China Military Escalation',
                'description': 'Sanctions, supply chain disruption, safe haven flows',
                'forex_impacts': {
                    'USD/CNY': +0.10, 'AUD/USD': -0.15, 'NZD/USD': -0.12,
                    'USD/JPY': -0.08, 'EUR/USD': -0.03, 'USD/CHF': -0.05
                },
                'commodity_impacts': {'oil': +0.50, 'gold': +0.20}
            },
            'us_debt_default': {
                'name': 'US Technical Debt Default',
                'description': 'Risk-free rate explodes, all correlations break',
                'forex_impacts': {
                    'EUR/USD': +0.10, 'GBP/USD': +0.08, 'USD/JPY': -0.15,
                    'USD/CHF': -0.12
                },
                'bond_impact': -0.30,
                'equity_impact': -0.25
            },
            'crypto_exchange_hack': {
                'name': 'Major Exchange Hack (>$1B)',
                'description': 'Top-3 exchange compromised, bank run',
                'crypto_impacts': {
                    'BTC/USD': -0.30, 'ETH/USD': -0.35
                },
                'stablecoin_depeg': True
            },
            'quantum_crypto_break': {
                'name': 'Quantum Computing Cryptographic Break',
                'description': 'ECDSA compromised, crypto infrastructure collapses',
                'crypto_impacts': {
                    'BTC/USD': -0.90, 'ETH/USD': -0.95
                },
                'permanent': True
            }
        }
    
    def _apply_scenario(self, portfolio: Portfolio, scenario: dict) -> dict:
        """Apply a stress scenario to current portfolio."""
        total_loss = 0.0
        
        for position in portfolio.positions:
            # Check forex impacts
            pair_key = position.pair.replace('/', '')
            impact = scenario.get('forex_impacts', {}).get(position.pair, 0)
            
            # Apply directional logic
            if position.direction == Direction.LONG:
                position_loss = position.notional * impact
            else:
                position_loss = position.notional * (-impact)
            
            total_loss += min(position_loss, 0)  # Only count losses
        
        # Apply liquidity/spread impacts
        if 'liquidity_impact' in scenario:
            # Assume we can only exit at worse prices during liquidity crisis
            liquidity_cost = abs(total_loss) * (1 - scenario['liquidity_impact']) * 0.5
            total_loss -= liquidity_cost
        
        return {
            'scenario_name': scenario['name'],
            'portfolio_loss': total_loss,
            'portfolio_loss_pct': abs(total_loss) / portfolio.equity if portfolio.equity > 0 else 0,
            'positions_affected': len(portfolio.positions),
            'can_exit': scenario.get('liquidity_impact', 1.0) > 0.1
        }
    
    def _reverse_stress_test(self, portfolio: Portfolio) -> dict:
        """Find what market move would cause maximum acceptable loss."""
        target_loss = portfolio.equity * 0.20  # What would cause 20% loss?
        
        # Work backwards from portfolio composition
        total_notional = sum(p.notional for p in portfolio.positions)
        if total_notional == 0:
            return {'scenario_name': 'No positions', 'portfolio_loss_pct': 0}
        
        required_move = target_loss / total_notional
        
        return {
            'scenario_name': f'Reverse: {required_move:.1%} adverse move needed for 20% loss',
            'portfolio_loss_pct': 0.20,
            'required_adverse_move': required_move,
            'total_notional': total_notional,
            'margin_of_safety': 1.0 / required_move if required_move > 0 else float('inf')
        }
    
    # === STATISTICAL HELPERS ===
    
    def _skewness(self, data: list[float]) -> float:
        n = len(data)
        mean = sum(data) / n
        std = (sum((x - mean) ** 2 for x in data) / n) ** 0.5
        if std == 0:
            return 0.0
        return sum((x - mean) ** 3 for x in data) / (n * std ** 3)
    
    def _kurtosis(self, data: list[float]) -> float:
        n = len(data)
        mean = sum(data) / n
        std = (sum((x - mean) ** 2 for x in data) / n) ** 0.5
        if std == 0:
            return 0.0
        return sum((x - mean) ** 4 for x in data) / (n * std ** 4) - 3  # Excess kurtosis
    
    def _hill_estimator(self, tail_data: list[float]) -> float:
        """Hill estimator for tail index (heavier tails = lower index)."""
        if not tail_data or all(x == 0 for x in tail_data):
            return 0.0
        abs_data = sorted([abs(x) for x in tail_data if x != 0], reverse=True)
        if len(abs_data) < 2:
            return 0.0
        k = len(abs_data)
        log_sum = sum(math.log(abs_data[i] / abs_data[k-1]) for i in range(k))
        return k / log_sum if log_sum > 0 else 0.0
    
    def _norm_ppf(self, p: float) -> float:
        """Approximate inverse normal CDF (percent-point function)."""
        # Rational approximation for 0 < p < 1
        if p <= 0 or p >= 1:
            return 0.0
        if p < 0.5:
            return -self._norm_ppf(1 - p)
        
        t = (-2 * math.log(1 - p)) ** 0.5
        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308
        return t - (c0 + c1*t + c2*t**2) / (1 + d1*t + d2*t**2 + d3*t**3)
    
    def _calculate_var(self, returns: list[float], confidence: float) -> float:
        """Calculate Value at Risk."""
        sorted_ret = sorted(returns)
        index = int(len(sorted_ret) * (1 - confidence))
        return -sorted_ret[index] if 0 <= index < len(sorted_ret) else 0.0
```

### 6.3 Stress Testing Schedule

| Test Type | Frequency | Trigger | Scope |
|-----------|-----------|---------|-------|
| Historical replay | Weekly | Sunday midnight | All 5 historical scenarios |
| Hypothetical scenario | Weekly | Sunday midnight | All hypothetical scenarios |
| Reverse stress test | Weekly | Sunday midnight | Find portfolio kill threshold |
| On-demand | Real-time | Position change >20% | Updated portfolio impact |
| Event-triggered | On event | Regime change, correlation spike | Targeted scenario |

---

## 7. News Event Handling

### 7.1 Three-Phase News Protocol

```
PRE-EVENT (T-60min to T-0):
┌─────────────────────────────────────────────────────────────────┐
│  T-60min: Flag positions with news exposure                      │
│  T-30min: If profit >1R → tighten SL. At BE → move to -0.5R    │
│  T-15min: Close 50% of exposed positions with profit <1R         │
│  T-5min:  Block ALL new entries. Cancel pending limit orders     │
│  T-0:     BLACKOUT — no orders accepted                          │
└─────────────────────────────────────────────────────────────────┘

DURING EVENT (T-0 to T+5min):
┌─────────────────────────────────────────────────────────────────┐
│  All automated trading PAUSED                                    │
│  Existing stops remain active at broker                          │
│  No new orders submitted                                         │
│  Monitoring only — log all price action                          │
└─────────────────────────────────────────────────────────────────┘

POST-EVENT (T+5min to T+30min):
┌─────────────────────────────────────────────────────────────────┐
│  T+5min:  Assess post-news price action                          │
│  T+10min: If spreads normalized → resume with 50% size           │
│  T+15min: If volatility normalized → resume with 75% size         │
│  T+30min: Full resume if conditions normal                        │
│  If conditions persist → extend blackout                          │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 News Event Classification

| Impact Level | Examples | Pre-Event Action | Blackout Duration |
|-------------|---------|-----------------|-------------------|
| **CRITICAL** | NFP, CPI, FOMC rate decision, ECB rate decision | Close 50%, tighten remaining, block entries | 15 minutes |
| **HIGH** | GDP, Employment data, Central bank speeches | Tighten stops, reduce new entry size 50% | 10 minutes |
| **MEDIUM** | PMI, Retail sales, Consumer confidence | Monitor, no automatic action | 5 minutes |
| **LOW** | Housing data, Industrial production | Log only | None |

### 7.3 News Event Handler Implementation

```python
class NewsEventHandler:
    """
    Pre/during/post news event management.
    Integrates with economic calendar and news sentiment pipeline.
    """
    
    def __init__(self, config: dict):
        self.pre_event_minutes = config.get('pre_event_minutes', 60)
        self.blackout_minutes = config.get('blackout_minutes', 15)
        self.post_resume_minutes = config.get('post_resume_minutes', 30)
        self.event_bus = None
        self.active_blackouts = {}  # event_id → BlackoutState
    
    async def check_upcoming_events(
        self, calendar: EconomicCalendar, positions: list[Position]
    ) -> list[NewsAction]:
        """Check for upcoming events and generate pre-event actions."""
        actions = []
        
        upcoming = calendar.get_events_within(minutes=self.pre_event_minutes)
        
        for event in upcoming:
            if event.impact in ('CRITICAL', 'HIGH'):
                # Identify affected positions
                affected = [p for p in positions if self._is_affected(p, event)]
                
                if affected:
                    for pos in affected:
                        action = self._determine_pre_event_action(pos, event)
                        if action:
                            actions.append(action)
                    
                    # Schedule blackout
                    self.active_blackouts[event.event_id] = BlackoutState(
                        event=event,
                        start_time=event.time - timedelta(minutes=5),
                        end_time=event.time + timedelta(minutes=self.blackout_minutes),
                        affected_pairs=[p.pair for p in affected]
                    )
        
        return actions
    
    async def handle_event_start(self, event_id: str):
        """Called when a scheduled event begins."""
        blackout = self.active_blackouts.get(event_id)
        if not blackout:
            return
        
        await self.event_bus.publish('risk.news', RiskEvent(
            event_type=RiskEventType.NEWS_BLACKOUT_START,
            severity='WARNING',
            component='news_handler',
            data={
                'event_id': event_id,
                'event_name': blackout.event.name,
                'impact': blackout.event.impact,
                'affected_pairs': blackout.affected_pairs,
                'blackout_until': blackout.end_time.isoformat()
            },
            action_required='HALT',
            reasoning=f"News blackout started for {blackout.event.name}"
        ))
    
    async def handle_event_end(self, event_id: str):
        """Called when blackout period ends. Assess conditions for resume."""
        blackout = self.active_blackouts.get(event_id)
        if not blackout:
            return
        
        # Check post-event conditions
        conditions = await self._assess_post_event_conditions(blackout.affected_pairs)
        
        if conditions['spreads_normalized'] and conditions['volatility_acceptable']:
            # Resume trading
            await self.event_bus.publish('risk.news', RiskEvent(
                event_type=RiskEventType.NEWS_BLACKOUT_END,
                severity='INFO',
                component='news_handler',
                data={'event_id': event_id, 'conditions': conditions},
                action_required='NONE',
                reasoning=f"News blackout ended for {blackout.event.name} — conditions normalized"
            ))
            del self.active_blackouts[event_id]
        else:
            # Extend blackout
            blackout.end_time += timedelta(minutes=15)
            await self.event_bus.publish('risk.news', RiskEvent(
                event_type=RiskEventType.NEWS_BLACKOUT_START,
                severity='WARNING',
                component='news_handler',
                data={
                    'event_id': event_id,
                    'reason': 'Conditions not normalized',
                    'extended_until': blackout.end_time.isoformat()
                },
                reasoning=f"News blackout extended — spreads/volatility still elevated"
            ))
    
    def is_blackout_active(self, pair: str) -> bool:
        """Check if any blackout is currently active for a pair."""
        now = datetime.utcnow()
        for blackout in self.active_blackouts.values():
            if blackout.start_time <= now <= blackout.end_time:
                if pair in blackout.affected_pairs:
                    return True
        return False
    
    def _determine_pre_event_action(self, position: Position, event: EconomicEvent) -> NewsAction:
        """Determine what action to take on a position before news."""
        time_to_event = (event.time - datetime.utcnow()).total_seconds() / 60
        
        if time_to_event <= 5:
            # T-5min: Close or widen stop
            if position.unrealized_pnl_r < 1.0:
                return NewsAction(
                    position_id=position.ticket,
                    action='CLOSE_PARTIAL',
                    params={'close_pct': 0.50},
                    reason=f"T-5min {event.name}: close 50% (profit < 1R)"
                )
            else:
                return NewsAction(
                    position_id=position.ticket,
                    action='WIDEN_STOP',
                    params={'new_sl_mult': 2.0},  # 2x ATR
                    reason=f"T-5min {event.name}: widen stop (profit > 1R)"
                )
        
        elif time_to_event <= 15:
            # T-15min: Tighten stop
            if position.unrealized_pnl_r >= 1.0:
                return NewsAction(
                    position_id=position.ticket,
                    action='TIGHTEN_STOP',
                    params={'move_to': 'current_price'},
                    reason=f"T-15min {event.name}: move SL to breakeven"
                )
            elif position.unrealized_pnl_r >= 0:
                return NewsAction(
                    position_id=position.ticket,
                    action='TIGHTEN_STOP',
                    params={'move_to': '-0.5R'},
                    reason=f"T-15min {event.name}: tighten SL to -0.5R"
                )
        
        elif time_to_event <= 30:
            # T-30min: Tighten stops on profitable positions
            if position.unrealized_pnl_r >= 1.0:
                return NewsAction(
                    position_id=position.ticket,
                    action='TIGHTEN_STOP',
                    params={'move_to': 'breakeven'},
                    reason=f"T-30min {event.name}: secure profit at breakeven"
                )
        
        return None
    
    def _is_affected(self, position: Pair, event: EconomicEvent) -> bool:
        """Check if a position is affected by an economic event."""
        # Direct: event currency matches position pair
        event_currencies = event.affected_currencies
        pair_currencies = position.pair.split('/')
        
        return any(c in pair_currencies for c in event_currencies)
```

---

## 8. Black Swan Detection & Response

### 8.1 Detection Criteria

A black swan event requires **2 or more simultaneous triggers**:

| Trigger | Threshold | Detection Method |
|---------|-----------|-----------------|
| **VIX spike** | >40% increase in 1 hour | VIX feed monitoring |
| **ATR explosion** | Current ATR >5× 14-period ATR | Per-pair ATR calculation |
| **Spread blowout** | Current spread >10× normal spread | Per-pair spread monitoring |
| **Correlation convergence** | Cross-asset correlation >0.95 | Correlation monitor |
| **Liquidity evaporation** | Order book depth <10% of normal | Order book analysis |
| **Flash crash** | Price move >3% in <5 minutes on major pair | Price velocity monitor |
| **Stablecoin depeg** | Any major stablecoin moves >2% from peg | Stablecoin price monitor |
| **Exchange failure** | Major exchange halts withdrawals | Exchange status API |

### 8.2 Black Swan Protocol

```python
class BlackSwanDetector:
    """
    Always-on black swan detection and emergency response.
    Runs on a 1-second tick loop independent of all other systems.
    """
    
    # Detection thresholds
    VIX_SPIKE_THRESHOLD = 0.40       # 40% increase in 1 hour
    ATR_SPIKE_MULTIPLIER = 5.0       # 5x normal ATR
    SPREAD_SPIKE_MULTIPLIER = 10.0   # 10x normal spread
    CORRELATION_THRESHOLD = 0.95     # Near-perfect correlation
    LIQUIDITY_THRESHOLD = 0.10       # 10% of normal depth
    FLASH_CRASH_THRESHOLD = 0.03     # 3% in 5 minutes
    MIN_TRIGGERS = 2                 # Minimum triggers to activate
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.is_active = False
        self.activation_time = None
        self.cooldown_hours = 4  # Minimum time before resuming after black swan
        self.trigger_history = []  # For pattern detection
    
    async def monitor(self, market_state: MarketState, system_state: SystemState):
        """
        Main monitoring loop — called every second.
        Independent of all other risk systems.
        """
        triggers = []
        
        # Check each trigger
        if market_state.vix_1h_change > self.VIX_SPIKE_THRESHOLD:
            triggers.append(('vix_spike', market_state.vix_1h_change))
        
        for pair, atr_data in market_state.atr_data.items():
            if atr_data['current'] > atr_data['baseline'] * self.ATR_SPIKE_MULTIPLIER:
                triggers.append(('atr_spike', pair, atr_data['ratio']))
        
        for pair, spread_data in market_state.spread_data.items():
            if spread_data['current'] > spread_data['average'] * self.SPREAD_SPIKE_MULTIPLIER:
                triggers.append(('spread_blowout', pair, spread_data['ratio']))
        
        if market_state.cross_asset_correlation > self.CORRELATION_THRESHOLD:
            triggers.append(('correlation_convergence', market_state.cross_asset_correlation))
        
        for pair, depth_data in market_state.order_book_depth.items():
            if depth_data['current'] < depth_data['average'] * self.LIQUIDITY_THRESHOLD:
                triggers.append(('liquidity_evaporation', pair))
        
        for pair, velocity in market_state.price_velocity.items():
            if abs(velocity) > self.FLASH_CRASH_THRESHOLD:
                triggers.append(('flash_crash', pair, velocity))
        
        # Check stablecoin depegs
        for stable, price in market_state.stablecoin_prices.items():
            if abs(price - 1.0) > 0.02:
                triggers.append(('stablecoin_depeg', stable, price))
        
        # === ACTIVATION LOGIC ===
        if len(triggers) >= self.MIN_TRIGGERS and not self.is_active:
            await self._activate(triggers, market_state)
        
        # Log triggers for pattern analysis
        if triggers:
            self.trigger_history.append({
                'timestamp': datetime.utcnow(),
                'triggers': triggers,
                'count': len(triggers)
            })
    
    async def _activate(self, triggers: list, market_state: MarketState):
        """Activate black swan protocol — close everything."""
        self.is_active = True
        self.activation_time = datetime.utcnow()
        
        # Log critical event
        logger.critical(f"BLACK SWAN DETECTED — {len(triggers)} triggers: {triggers}")
        
        # Publish event
        await self.event_bus.publish('risk.black_swan', RiskEvent(
            event_type=RiskEventType.BLACK_SWAN_DETECTED,
            severity='EMERGENCY',
            component='black_swan_detector',
            data={
                'triggers': triggers,
                'trigger_count': len(triggers),
                'market_state_snapshot': {
                    'vix': market_state.vix,
                    'correlation': market_state.cross_asset_correlation,
                    'spreads': market_state.spread_data
                }
            },
            action_required='CLOSE_ALL',
            reasoning=f"Black swan detected: {len(triggers)} simultaneous triggers activated"
        ))
        
        # Execute emergency close
        await self.event_bus.publish('risk.black_swan', RiskEvent(
            event_type=RiskEventType.BLACK_SWAN_PROTOCOL_ACTIVATED,
            severity='EMERGENCY',
            component='black_swan_detector',
            data={
                'action': 'CLOSE_ALL_POSITIONS',
                'order_type': 'MARKET',
                'priority': 'IMMEDIATE'
            },
            action_required='CLOSE_ALL',
            auto_response_taken=True,
            reasoning="Black swan protocol: closing all positions at market"
        ))
        
        # Alert human
        await self._alert_human(
            f"🚨 BLACK SWAN DETECTED\n"
            f"Triggers: {len(triggers)}\n"
            f"Details: {[t[0] for t in triggers]}\n"
            f"ACTION: All positions being closed at market\n"
            f"Trading halted for {self.cooldown_hours}h minimum"
        )
    
    async def check_cooldown(self) -> bool:
        """Check if cooldown period has passed and conditions allow resumption."""
        if not self.is_active:
            return True
        
        elapsed = (datetime.utcnow() - self.activation_time).total_seconds() / 3600
        
        if elapsed < self.cooldown_hours:
            return False
        
        # Additional checks before resuming
        # (would check VIX, spreads, correlation in real implementation)
        return True
    
    async def manual_reset(self, operator_id: str, reason: str):
        """Manual reset by authorized operator."""
        if not self.is_active:
            return
        
        logger.warning(f"Black swan protocol manually reset by {operator_id}: {reason}")
        
        self.is_active = False
        self.activation_time = None
        
        await self.event_bus.publish('risk.black_swan', RiskEvent(
            event_type=RiskEventType.BLACK_SWAN_ALL_CLOSED,
            severity='WARNING',
            component='black_swan_detector',
            data={
                'reset_by': operator_id,
                'reason': reason,
                'was_active_since': self.activation_time.isoformat() if self.activation_time else None
            },
            reasoning=f"Black swan protocol manually reset: {reason}"
        ))
    
    async def _alert_human(self, message: str):
        """Send critical alert to human operator."""
        await self.event_bus.publish('system.alert', {
            'severity': 'EMERGENCY',
            'channel': 'telegram',
            'message': message,
            'sound': 'alarm',
            'repeat': True,
            'repeat_interval': 60  # Every 60 seconds until acknowledged
        })
```

### 8.3 Post-Black-Swan Recovery

```
RECOVERY PROTOCOL:

1. WAIT (4h minimum)
   - No trading for 4 hours after black swan detection
   - Monitor market conditions continuously

2. ASSESS (Hour 4-6)
   - Check: VIX < 30? Spreads normal? Correlation < 0.7?
   - Run full stress test on surviving portfolio state
   - Analyze what happened — update scenarios

3. PAPER TRADE (Hour 6-24)
   - Run paper trading for 18 hours
   - Verify system is functioning correctly
   - Check all risk systems are operational

4. SMALL RESUME (Day 2)
   - Resume with 25% of normal position size
   - Only A+ setups allowed
   - All positions require human approval

5. GRADUAL NORMALIZATION (Day 3-7)
   - Increase size by 25% per day if conditions remain stable
   - Monitor for "echo" events (second leg down)
   - Full normalization after 7 days of stable conditions
```

---

## 9. Integration with Trading Engine

### 9.1 Risk Governor — Pre-Trade Gate

The Risk Governor sits between the Confluence Engine (S10) and the Execution Layer (S11-S13). **Every trade proposal must pass through it.**

```
                    ┌──────────────┐
                    │  Confluence  │
                    │  Engine      │
                    │  (S10)       │
                    └──────┬───────┘
                           │ TradeProposal
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                      RISK GOVERNOR                            │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Drawdown    │  │ Exposure    │  │ Correlation │          │
│  │ Check       │  │ Check       │  │ Check       │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         └────────────────┼────────────────┘                   │
│                          ▼                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Regime      │  │ News        │  │ Circuit     │          │
│  │ Check       │  │ Blackout    │  │ Breaker     │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         └────────────────┼────────────────┘                   │
│                          ▼                                    │
│                    ┌──────────┐                                │
│                    │ APPROVED │ / REJECTED / ADJUSTED          │
│                    └──────────┘                                │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
                    ┌──────────────┐
                    │  Position    │
                    │  Sizing (S11)│
                    └──────────────┘
```

### 9.2 Risk Governor Implementation

```python
class RiskGovernor:
    """
    Central risk gate. Every trade proposal passes through here.
    No module can bypass this gate.
    """
    
    def __init__(
        self,
        drawdown_manager: DrawdownLimitManager,
        circuit_breaker: CircuitBreakerSystem,
        correlation_monitor: CorrelationMonitor,
        tail_risk_manager: TailRiskManager,
        news_handler: NewsEventHandler,
        black_swan_detector: BlackSwanDetector,
        position_sizing_engine: PositionSizingEngine,
        event_bus
    ):
        self.drawdown = drawdown_manager
        self.circuit_breaker = circuit_breaker
        self.correlation = correlation_monitor
        self.tail_risk = tail_risk_manager
        self.news = news_handler
        self.black_swan = black_swan_detector
        self.sizing = position_sizing_engine
        self.event_bus = event_bus
    
    async def pre_trade_check(
        self,
        proposal: TradeProposal,
        account: AccountState,
        market_state: MarketState,
        open_positions: list[Position],
        recent_trades: list[TradeResult]
    ) -> RiskCheckResult:
        """
        Full pre-trade risk evaluation.
        Returns APPROVED, REJECTED, or ADJUSTED with reasons.
        """
        checks = []
        
        # === CHECK 1: Black Swan ===
        if self.black_swan.is_active:
            return RiskCheckResult(
                approved=False,
                reason="BLACK_SWAN_ACTIVE",
                detail="Black swan protocol active — all trading halted",
                checks=checks
            )
        
        # === CHECK 2: Drawdown Stage ===
        dd_state = await self.drawdown.update(account)
        if not self.drawdown.is_trading_allowed():
            return RiskCheckResult(
                approved=False,
                reason="DRAWDOWN_BLACK",
                detail=f"Drawdown at {dd_state.drawdown_pct:.1%} — BLACK stage, trading halted",
                checks=checks
            )
        
        # === CHECK 3: Circuit Breakers ===
        if self.circuit_breaker.is_breaker_tripped():
            tripped = self.circuit_breaker.get_tripped_breakers()
            return RiskCheckResult(
                approved=False,
                reason="CIRCUIT_BREAKER",
                detail=f"Circuit breakers tripped: {tripped}",
                checks=checks
            )
        
        # === CHECK 4: News Blackout ===
        if self.news.is_blackout_active(proposal.pair):
            return RiskCheckResult(
                approved=False,
                reason="NEWS_BLACKOUT",
                detail=f"News blackout active for {proposal.pair}",
                checks=checks
            )
        
        # === CHECK 5: Portfolio Exposure ===
        current_exposure = sum(p.risk_amount for p in open_positions)
        max_exposure = account.balance * 0.06  # 6% cap
        if current_exposure >= max_exposure:
            return RiskCheckResult(
                approved=False,
                reason="EXPOSURE_LIMIT",
                detail=f"Current exposure {current_exposure/account.balance:.1%} >= 6% limit",
                checks=checks
            )
        
        # === CHECK 6: Correlation ===
        corr_factor = self.correlation.get_effective_risk(
            proposal.pair, proposal.direction, open_positions
        )
        if corr_factor < 0.5:
            checks.append(('correlation', 'WARNING', f'High correlation: factor={corr_factor:.2f}'))
        
        # === CHECK 7: Tail Risk ===
        # (Periodic check, not every trade — expensive)
        
        # === CHECK 8: Drawdown-adjusted sizing ===
        dd_multiplier = self.drawdown.get_position_size_multiplier()
        
        # === FINAL: Calculate adjusted size ===
        adjusted_proposal = await self.sizing.calculate(
            setup=proposal,
            account=account,
            market_state=market_state,
            open_positions=open_positions,
            recent_trades=recent_trades
        )
        
        if not adjusted_proposal.approved:
            return RiskCheckResult(
                approved=False,
                reason="SIZING_REJECTED",
                detail=adjusted_proposal.reason,
                checks=checks
            )
        
        # Apply drawdown multiplier
        final_risk = adjusted_proposal.risk_amount * dd_multiplier
        
        return RiskCheckResult(
            approved=True,
            reason="ALL_CHECKS_PASSED",
            adjusted_risk=final_risk,
            adjusted_lot_size=adjusted_proposal.lot_size * dd_multiplier,
            drawdown_stage=dd_state.current_stage,
            drawdown_multiplier=dd_multiplier,
            correlation_factor=corr_factor,
            checks=checks
        )
    
    async def in_trade_check(self, position: Position, market_state: MarketState) -> list[TradeAction]:
        """
        Continuous risk monitoring for open positions.
        Returns list of management actions to execute.
        """
        actions = []
        
        # Circuit breaker: position stop
        if await self.circuit_breaker.check_position_stop(position, market_state.current_price):
            actions.append(TradeAction(
                position_id=position.ticket,
                action='CLOSE',
                reason='Circuit breaker: position stop triggered'
            ))
        
        # Drawdown stage adjustments
        dd_state = await self.drawdown.update(market_state.account)
        if dd_state.current_stage in ('ORANGE', 'RED'):
            if position.unrealized_pnl < 0 and abs(position.unrealized_pnl) / position.entry_value > 0.05:
                actions.append(TradeAction(
                    position_id=position.ticket,
                    action='CLOSE',
                    reason=f'Drawdown {dd_state.current_stage}: closing losing position >5%'
                ))
        
        # News proximity
        if self.news.is_blackout_active(position.pair):
            if position.unrealized_pnl_r >= 1.0:
                actions.append(TradeAction(
                    position_id=position.ticket,
                    action='TIGHTEN_STOP',
                    params={'move_to': 'breakeven'},
                    reason='News blackout: securing profit'
                ))
        
        return actions
```

### 9.3 Integration with Execution Pipeline

```
Trade Proposal (S10)
        │
        ▼
Risk Governor ──── REJECTED ──── Log + Alert
        │
     APPROVED
        │
        ▼
Position Sizing (S11) ◄── Risk Governor parameters
        │
        ▼
Stop Loss (S12) ◄── Drawdown-adjusted stops
        │
        ▼
Take Profit (S13) ◄── Regime-adjusted targets
        │
        ▼
Broker Layer ──── Circuit Breaker checks slippage/spread
        │
        ▼
Fill Confirmation ──── Update risk state
        │
        ▼
Trade Management (S14) ◄── Continuous risk monitoring
        │
        ▼
Exit (S15) ◄── Risk-triggered exits
```

---

## 10. Integration with Multi-Agent System

### 10.1 Risk Agent Architecture

The Risk Agent is a dedicated agent in the multi-agent system that wraps all risk management components:

```
┌─────────────────────────────────────────────────────────────┐
│                      RISK AGENT                              │
│                                                              │
│  Role: Central risk management authority                     │
│  Loop Pattern: ReAct (Reason + Act continuously)             │
│  Priority: P0 (highest — overrides all other agents)         │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                 INTERNAL COMPONENTS                   │    │
│  │                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐                 │    │
│  │  │ Position     │  │ Drawdown     │                 │    │
│  │  │ Sizing       │  │ Manager      │                 │    │
│  │  │ Engine       │  │              │                 │    │
│  │  └──────────────┘  └──────────────┘                 │    │
│  │  ┌──────────────┐  ┌──────────────┐                 │    │
│  │  │ Circuit      │  │ Correlation  │                 │    │
│  │  │ Breaker      │  │ Monitor      │                 │    │
│  │  │ System       │  │              │                 │    │
│  │  └──────────────┘  └──────────────┘                 │    │
│  │  ┌──────────────┐  ┌──────────────┐                 │    │
│  │  │ Tail Risk    │  │ News Event   │                 │    │
│  │  │ Manager      │  │ Handler      │                 │    │
│  │  └──────────────┘  └──────────────┘                 │    │
│  │  ┌──────────────┐  ┌──────────────┐                 │    │
│  │  │ Black Swan   │  │ Risk         │                 │    │
│  │  │ Detector     │  │ Governor     │                 │    │
│  │  │              │  │ (Gate)       │                 │    │
│  │  └──────────────┘  └──────────────┘                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  INTERFACES:                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Receives:    │  │ Publishes:   │  │ Blocks:      │      │
│  │ Trade props  │  │ Risk events  │  │ Any trade    │      │
│  │ Market state │  │ Alerts       │  │ that fails   │      │
│  │ Account data │  │ Adjustments  │  │ risk checks  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 Agent Communication Protocol

```python
class RiskAgent:
    """
    Risk management agent in the multi-agent system.
    Has P0 priority — can override any other agent's decision.
    """
    
    AGENT_ID = "risk-agent"
    PRIORITY = Priority.P0  # Highest priority
    
    def __init__(self, risk_governor: RiskGovernor, event_bus):
        self.governor = risk_governor
        self.event_bus = event_bus
    
    async def on_trade_proposal(self, message: AgentMessage):
        """Handle incoming trade proposals from Strategy Agent."""
        proposal = TradeProposal.from_dict(message.payload)
        
        # Get current state
        account = await self._get_account_state()
        market_state = await self._get_market_state()
        positions = await self._get_open_positions()
        recent_trades = await self._get_recent_trades()
        
        # Run risk evaluation
        result = await self.governor.pre_trade_check(
            proposal, account, market_state, positions, recent_trades
        )
        
        # Send response
        if result.approved:
            await self.event_bus.publish_agent(AgentMessage(
                source_agent=self.AGENT_ID,
                target_agent="execution-agent",
                message_type=MessageType.COMMAND,
                priority=self.PRIORITY,
                payload={
                    'action': 'EXECUTE_TRADE',
                    'proposal': proposal.to_dict(),
                    'risk_params': {
                        'adjusted_lot_size': result.adjusted_lot_size,
                        'adjusted_risk': result.adjusted_risk,
                        'drawdown_stage': result.drawdown_stage,
                        'correlation_factor': result.correlation_factor
                    }
                }
            ))
        else:
            await self.event_bus.publish_agent(AgentMessage(
                source_agent=self.AGENT_ID,
                target_agent=message.source_agent,
                message_type=MessageType.RESPONSE,
                priority=self.PRIORITY,
                payload={
                    'approved': False,
                    'reason': result.reason,
                    'detail': result.detail
                }
            ))
            
            # Log rejection
            logger.info(f"Trade rejected: {proposal.pair} {proposal.direction} — {result.reason}")
    
    async def on_market_update(self, message: AgentMessage):
        """Handle market data updates — continuous risk monitoring."""
        market_state = MarketState.from_dict(message.payload)
        account = await self._get_account_state()
        positions = await self._get_open_positions()
        
        # Update all risk components
        dd_state = await self.governor.drawdown.update(account)
        await self.governor.correlation.update(market_state.returns_matrix)
        await self.governor.black_swan.monitor(market_state, SystemState())
        
        # Check circuit breakers
        await self.governor.circuit_breaker.check_portfolio_loss(account)
        await self.governor.circuit_breaker.check_regime_breakers(market_state)
        
        # In-trade risk checks
        for position in positions:
            actions = await self.governor.in_trade_check(position, market_state)
            for action in actions:
                await self.event_bus.publish_agent(AgentMessage(
                    source_agent=self.AGENT_ID,
                    target_agent="execution-agent",
                    message_type=MessageType.COMMAND,
                    priority=Priority.P1,
                    payload=action.to_dict()
                ))
    
    async def on_regime_change(self, message: AgentMessage):
        """Handle regime change events from Market Bias Agent."""
        regime = message.payload['new_regime']
        confidence = message.payload['confidence']
        
        # Adjust risk parameters based on regime
        adjustments = self._get_regime_adjustments(regime, confidence)
        
        await self.event_bus.publish('risk.regime', RiskEvent(
            event_type=RiskEventType.REGIME_RISK_ADJUSTMENT,
            severity='WARNING' if regime == 'crisis' else 'INFO',
            component='risk_agent',
            data=adjustments,
            reasoning=f"Regime change to {regime} (confidence {confidence:.0%}) — adjusting risk parameters"
        ))
    
    def _get_regime_adjustments(self, regime: str, confidence: float) -> dict:
        """Get risk parameter adjustments for a regime."""
        base = {
            'trending': {'size_mult': 1.0, 'stop_mult': 1.0, 'max_positions': 5},
            'range_bound': {'size_mult': 0.6, 'stop_mult': 0.8, 'max_positions': 3},
            'high_volatility': {'size_mult': 0.4, 'stop_mult': 1.5, 'max_positions': 2},
            'crisis': {'size_mult': 0.2, 'stop_mult': 2.0, 'max_positions': 1},
            'uncertain': {'size_mult': 0.5, 'stop_mult': 1.2, 'max_positions': 3}
        }
        
        adjustments = base.get(regime, base['uncertain'])
        
        # Scale by confidence
        if confidence < 0.5:
            # Low confidence — be more conservative
            adjustments['size_mult'] *= 0.7
        
        return adjustments
```

### 10.3 Agent Priority Hierarchy

| Priority | Agent | Override Power | Rationale |
|----------|-------|---------------|-----------|
| **P0** | Risk Agent | Can override ALL agents | Safety is non-negotiable |
| **P1** | Black Swan Sentinel | Can halt all execution | Existential threat response |
| **P1** | Execution Agent | Direct broker control | Needs autonomy for speed |
| **P2** | Strategy Agent | Signal generation | Important but subordinate to risk |
| **P2** | News Agent | Sentiment/awareness | Context provider |
| **P3** | Journal Agent | Recording | Non-blocking, async |
| **P3** | Auditor Agent | Analysis | Background, non-blocking |

### 10.4 Inter-Agent Risk Events

```
RISK AGENT PUBLISHES:

→ Strategy Agent:
  - risk.regime_adjustment: "Reduce sizing due to regime change"
  - risk.drawdown_stage: "Entered ORANGE stage — reduce signal threshold"
  - risk.black_swan: "All trading halted"

→ Execution Agent:
  - risk.approved_trade: "Trade approved with adjusted parameters"
  - risk.rejected_trade: "Trade rejected — [reason]"
  - risk.close_position: "Close position [id] — [reason]"
  - risk.modify_stop: "Tighten/widen stop on [id]"

→ News Agent:
  - risk.news_blackout: "Blackout active for [pairs]"
  - risk.news_resume: "Blackout ended, conditions normalized"

→ Journal Agent:
  - risk.event_log: All risk events for audit trail

→ Coordinator Agent:
  - risk.system_status: "Risk systems operational" / "ALERT: [issue]"
  - risk.drawdown_report: Daily/weekly drawdown summary
```

---

## 11. Configuration & Parameters

### 11.1 Risk Configuration Schema

```yaml
# risk_config.yaml

position_sizing:
  kelly_fraction: 0.25              # Quarter-Kelly
  base_risk_pct: 1.0                # 1% base risk per trade
  max_risk_pct: 2.0                 # 2% absolute max per trade
  target_volatility: 0.15           # 15% annualized target
  min_r_multiple: 2.0               # Minimum R:R for entry
  min_trades_for_kelly: 30          # Minimum trades before Kelly activates
  
  account_tiers:
    - range: [1000, 5000]
      max_risk: 0.01
      max_exposure: 0.03
      kelly: 0.20
    - range: [5000, 25000]
      max_risk: 0.015
      max_exposure: 0.045
      kelly: 0.25
    - range: [25000, 100000]
      max_risk: 0.015
      max_exposure: 0.05
      kelly: 0.25
    - range: [100000, 500000]
      max_risk: 0.01
      max_exposure: 0.04
      kelly: 0.20
    - range: [500000, null]
      max_risk: 0.0075
      max_exposure: 0.03
      kelly: 0.15

drawdown:
  stages:
    green:  { max: 0.03, size_mult: 1.00, max_positions: 5 }
    yellow: { max: 0.07, size_mult: 0.50, max_positions: 3 }
    orange: { max: 0.12, size_mult: 0.25, max_positions: 2 }
    red:    { max: 0.18, size_mult: 0.10, max_positions: 1 }
    black:  { max: 1.00, size_mult: 0.00, max_positions: 0 }
  
  recovery:
    black_to_red: { wait_hours: 24, requires: "manual_restart + paper_trading" }
    red_to_orange: { wait_hours: 48, requires: "dd < 12% for 48h" }
    orange_to_yellow: { wait_hours: 24, requires: "dd < 7% for 24h" }
    yellow_to_green: { wait_hours: 12, requires: "dd < 3% for 12h" }

circuit_breakers:
  layer_1_position:
    hard_stop_pct: 0.02
    trailing_stop_pct: 0.03
    slippage_breaker_pct: 0.005
    spread_breaker_mult: 3.0
    crisis_time_limit_hours: 48
  
  layer_2_portfolio:
    daily_loss_limit: 0.04
    weekly_loss_limit: 0.08
    monthly_loss_limit: 0.12
    max_drawdown_halt: 0.18
    max_exposure: 0.06
    max_margin: 0.30
  
  layer_3_regime:
    vix_caution: 30
    vix_high: 50
    vix_extreme: 70
    correlation_spike: 0.80
    regime_uncertain_days: 5
  
  layer_4_system:
    connectivity_timeout_sec: 30
    order_rejection_threshold: 0.10
    latency_spike_mult: 10

correlation:
  window_short: 20
  window_long: 100
  spike_threshold: 0.70
  crisis_threshold: 0.85
  effective_risk_threshold: 0.70

tail_risk:
  confidence_level: 0.95
  cvar_limit: 0.05
  stress_test_frequency: "weekly"
  max_scenario_loss: 0.15

news:
  pre_event_minutes: 60
  blackout_minutes: 15
  post_resume_minutes: 30
  critical_events: ["NFP", "CPI", "FOMC", "ECB_Rate", "BOJ_Rate"]
  high_events: ["GDP", "Employment", "Retail_Sales"]

black_swan:
  vix_spike_threshold: 0.40
  atr_spike_multiplier: 5.0
  spread_spike_multiplier: 10.0
  correlation_threshold: 0.95
  liquidity_threshold: 0.10
  flash_crash_threshold: 0.03
  min_triggers: 2
  cooldown_hours: 4

monitoring:
  alert_channels: ["telegram"]
  drawdown_alert_stage: "yellow"
  circuit_breaker_alert: true
  correlation_alert_threshold: 0.70
  stress_test_alert: true
```

---

## 12. Monitoring & Alerting

### 12.1 Risk Dashboard Metrics

| Metric | Update Frequency | Alert Threshold |
|--------|-----------------|----------------|
| Current drawdown % | Real-time | > 3% (YELLOW) |
| Daily P&L | Real-time | < -4% (circuit breaker) |
| Total open exposure % | Real-time | > 6% |
| Max pairwise correlation | Per candle | > 0.70 |
| Cross-asset correlation | Per candle | > 0.85 |
| CVaR (95%) | Hourly | > 5% of portfolio |
| Active circuit breakers | Real-time | Any breaker tripped |
| News blackout status | Real-time | Any active blackout |
| Black swan triggers | Every second | ≥ 2 triggers |
| Regime state | Per candle | Crisis detected |
| Position risk distribution | Real-time | Any position > 2% |

### 12.2 Alert Escalation Matrix

| Severity | Channel | Response Time | Acknowledgment Required |
|----------|---------|--------------|------------------------|
| **INFO** | Grafana dashboard | Passive | No |
| **WARNING** | Telegram notification | Within 1 hour | No |
| **CRITICAL** | Telegram + sound alert | Within 15 minutes | Yes |
| **EMERGENCY** | Telegram + repeat alerts | Immediate | Yes + action |

---

## 13. Testing & Validation

### 13.1 Risk System Test Suite

| Test Category | What's Tested | Frequency |
|--------------|--------------|-----------|
| **Unit tests** | Each risk component in isolation | Every commit |
| **Integration tests** | Risk Governor gate with mock proposals | Every commit |
| **Stress tests** | Historical scenario replay through full system | Weekly |
| **Chaos tests** | Inject failures (broker disconnect, data gaps, etc.) | Monthly |
| **Paper trading** | Full system with real market data, no real money | Continuous |
| **Backtesting** | Risk system behavior over 5+ years of history | Monthly |

### 13.2 Key Test Scenarios

```
1. SWISS FRANC TEST
   - Inject: EUR/CHF -30% in 15 minutes
   - Verify: All positions closed, system enters BLACK stage
   - Verify: Human alert sent within 30 seconds

2. COVID SPEED TEST
   - Inject: S&P -34% over 23 days with daily accelerations
   - Verify: Drawdown stages trigger progressively
   - Verify: Position sizes reduce at each stage

3. CORRELATION CONVERGENCE TEST
   - Inject: All pairs → 0.95 correlation
   - Verify: Position sizes reduced to minimum
   - Verify: Hedging mode activated

4. CIRCUIT BREAKER CASCADE TEST
   - Inject: Daily loss hits 4% while VIX > 50
   - Verify: Both breakers trip, trading halts
   - Verify: Recovery requires both conditions to clear

5. MICRO ACCOUNT COST TEST
   - Setup: $7 account, EURUSD 0.01 lot
   - Verify: TCA-aware sizing blocks trades with insufficient R:R
   - Verify: Warning logged about cost viability

6. NEWS EVENT TEST
   - Inject: NFP release in 30 minutes with open positions
   - Verify: Pre-event protocol executes (tighten stops, partial close)
   - Verify: Blackout starts and ends correctly
```

---

## Appendix A: Risk Event Flow Diagram

```
                    MARKET DATA
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
  ┌──────────┐   ┌──────────┐   ┌──────────┐
  │ Correl.  │   │ Black    │   │ News     │
  │ Monitor  │   │ Swan     │   │ Handler  │
  └────┬─────┘   │ Detector │   └────┬─────┘
       │         └────┬─────┘        │
       │              │              │
       └──────────────┼──────────────┘
                      ▼
              ┌──────────────┐
              │   RISK       │
              │   GOVERNOR   │◄──── Trade Proposal
              └──────┬───────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │ Drawdown │ │ Circuit  │ │ Position │
  │ Manager  │ │ Breaker  │ │ Sizing   │
  └────┬─────┘ └────┬─────┘ └────┬─────┘
       └─────────────┼───────────┘
                     ▼
              ┌──────────────┐
              │  APPROVED /  │
              │  REJECTED /  │
              │  ADJUSTED    │
              └──────┬───────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │ Execute  │ │ Alert    │ │ Journal  │
  │ Trade    │ │ Human    │ │ Log      │
  └──────────┘ └──────────┘ └──────────┘
```

---

## Appendix B: Risk Limits Summary Card

```
╔══════════════════════════════════════════════════════════════╗
║              ALPHA STACK — RISK LIMITS SUMMARY              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  POSITION LIMITS                                             ║
║  ├── Max risk per trade:           2.0%                      ║
║  ├── Max total open exposure:      6.0%                      ║
║  ├── Max correlated exposure:      3.0%                      ║
║  ├── Max concurrent positions:     5 (forex) / 3 (crypto)   ║
║  └── Max margin utilization:       30%                       ║
║                                                              ║
║  DRAWDOWN STAGES                                             ║
║  ├── GREEN  (0-3%):   Normal operations                     ║
║  ├── YELLOW (3-7%):   50% size reduction                    ║
║  ├── ORANGE (7-12%):  Close losers, hedge, 25% size         ║
║  ├── RED    (12-18%): Close 75%, cash mode                  ║
║  └── BLACK  (>18%):   CLOSE ALL, HALT SYSTEM                ║
║                                                              ║
║  CIRCUIT BREAKERS                                            ║
║  ├── Daily loss:       -4% → pause 24h                      ║
║  ├── Weekly loss:      -8% → reduce 50%                     ║
║  ├── Monthly loss:     -12% → full de-risk                  ║
║  ├── Max drawdown:     -18% → system halt                   ║
║  └── Black swan:       2+ triggers → close all              ║
║                                                              ║
║  CORRELATION                                                 ║
║  ├── Spike threshold:  0.70 → reduce sizing                 ║
║  ├── Crisis threshold: 0.85 → emergency mode                ║
║  └── Effective risk:   Combined < 2.5%                      ║
║                                                              ║
║  TAIL RISK                                                   ║
║  ├── CVaR (95%):       < 5% of portfolio                    ║
║  ├── Stress test:      Weekly, 5+ scenarios                 ║
║  └── Scenario loss:    < 15% in any scenario                ║
║                                                              ║
║  NEWS EVENTS                                                 ║
║  ├── Pre-event:        T-60min flag, T-5min block           ║
║  ├── Blackout:         15min (critical events)              ║
║  └── Resume:           After conditions normalize           ║
║                                                              ║
║  "The market can stay irrational longer than you can         ║
║   stay solvent." — Keynes                                    ║
║                                                              ║
║  "In a crisis, all correlations go to one."                  ║
║   — Every risk manager ever                                  ║
╚══════════════════════════════════════════════════════════════╝
```

---

*Document maintained by: Risk Management Architect — Alpha Stack*
*Review cadence: Monthly, or after any drawdown event > 5%*
*Next review: 2026-08-11*
