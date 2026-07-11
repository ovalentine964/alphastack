# Alpha Stack — Trade Monitoring Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Trade Monitoring Architect
> **Scope:** Real-time tracking of all trading activity, P&L, positions, performance, and anomaly detection
> **Design Philosophy:** If it isn't measured, it isn't managed. Every tick, every trade, every decision — recorded, analyzed, surfaced.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Real-Time Position Tracking](#2-real-time-position-tracking)
3. [Trade Lifecycle Monitoring](#3-trade-lifecycle-monitoring)
4. [Performance Dashboard](#4-performance-dashboard)
5. [Risk Utilization Monitoring](#5-risk-utilization-monitoring)
6. [Agent Contribution Tracking](#6-agent-contribution-tracking)
7. [Anomaly Detection](#7-anomaly-detection)
8. [Trade Reconciliation](#8-trade-reconciliation)
9. [Historical Trade Analytics](#9-historical-trade-analytics)
10. [Notification Channels](#10-notification-channels)
11. [Export & Reporting](#11-export--reporting)
12. [Technology Stack & Deployment](#12-technology-stack--deployment)

---

## 1. Architecture Overview

### 1.1 Design Philosophy

The trade monitoring system is the **nervous system** of Alpha Stack — it sees everything, remembers everything, and alerts on anything that deviates from expectation.

| Principle | Description | Rationale |
|-----------|-------------|-----------|
| **Complete Observability** | Every signal, decision, order, fill, modification, and exit is captured with full context. | You can't improve what you can't see. Blind spots hide edge decay. |
| **Real-Time First** | Position state, P&L, and risk metrics update on every tick. Dashboards refresh sub-second. | Stale data = stale decisions. A 5-second delay on a 30-pip stop hunt is the difference between saved and stopped out. |
| **Layered Aggregation** | Raw tick → per-trade → per-session → per-day → per-week → per-month → per-quarter → lifetime. | Different decisions need different zoom levels. Intra-day management needs tick-level; quarterly review needs monthly aggregates. |
| **Agent-Aware** | Every trade carries a full provenance chain — which agents contributed signals, what scores they assigned, what confidence they expressed. | Multi-agent systems need attribution. If performance degrades, you need to know which agent to recalibrate. |
| **Reconcile or Die** | Internal records must match broker records. Discrepancies are flagged within seconds, not days. | Silent position drift, missed fills, or phantom trades can destroy an account before anyone notices. |
| **Alert Fatigue Prevention** | Smart escalation: INFO → WARNING → CRITICAL → EMERGENCY. Only actionable alerts reach the human. | A system that cries wolf gets ignored. A system that stays silent during crises gets blown up. |

### 1.2 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         TRADE MONITORING SYSTEM (TMS)                             │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                        MONITORING EVENT BUS (Redis Streams)                  │ │
│  │  trade.opened · trade.modified · trade.closed · position.update              │ │
│  │  pnl.update · risk.utilization · agent.signal · anomaly.detected            │ │
│  │  reconciliation.mismatch · performance.alert · notification.send             │ │
│  └──────────────────────────────┬──────────────────────────────────────────────┘ │
│                                 │                                                 │
│  ┌──────────────────────────────▼──────────────────────────────────────────────┐ │
│  │                     MONITORING ORCHESTRATOR (Central Controller)              │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │ │
│  │  │  POSITION    │ │  TRADE       │ │  PERFORMANCE │ │  RISK        │       │ │
│  │  │  TRACKER     │ │  LIFECYCLE   │ │  ENGINE      │ │  UTILIZATION │       │ │
│  │  │              │ │  MONITOR     │ │              │ │  MONITOR     │       │ │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘       │ │
│  │         └────────────────┼────────────────┼────────────────┘                │ │
│  │                          ▼                                                  │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │ │
│  │  │  AGENT       │ │  ANOMALY     │ │  RECONCILIA- │ │  HISTORICAL  │       │ │
│  │  │  CONTRIBUTION│ │  DETECTOR    │ │  TION ENGINE │ │  ANALYTICS   │       │ │
│  │  │  TRACKER     │ │              │ │              │ │              │       │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │ │
│  └──────────────────────────────┬──────────────────────────────────────────────┘ │
│                                 │                                                 │
│  ┌──────────────────────────────▼──────────────────────────────────────────────┐ │
│  │                     NOTIFICATION & REPORTING LAYER                           │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │ │
│  │  │  TELEGRAM    │ │  DASHBOARD   │ │  EXPORT      │ │  TAX         │       │ │
│  │  │  ALERTS      │ │  (Grafana)   │ │  ENGINE      │ │  REPORTING   │       │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                     STORAGE LAYER                                            │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │ │
│  │  │  TimescaleDB │ │  Redis       │ │  S3/MinIO    │ │  PostgreSQL  │       │ │
│  │  │  (time-series│ │  (real-time  │ │  (screenshots│ │  (metadata,  │       │ │
│  │  │   P&L, ticks)│ │   state)     │ │   exports)   │ │   config)    │       │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Monitoring Event Schema

All monitoring components communicate through standardized events:

```python
@dataclass
class MonitoringEvent:
    event_id: str                    # UUID v7 (time-ordered)
    timestamp: datetime              # UTC, microsecond precision
    event_type: MonitoringEventType  # Enum (see below)
    severity: Severity               # INFO, WARNING, CRITICAL, EMERGENCY
    source: str                      # Component that generated the event
    trade_id: str | None             # Associated trade (if applicable)
    pair: str | None                 # Currency pair (if applicable)
    data: dict                       # Event-specific payload
    agent_chain: list[str]           # Which agents contributed (provenance)
    checksum: str                    # SHA-256 of data for integrity

class MonitoringEventType(Enum):
    # Position events
    POSITION_OPENED = "position.opened"
    POSITION_MODIFIED = "position.modified"
    POSITION_CLOSED = "position.closed"
    POSITION_PARTIAL_CLOSE = "position.partial_close"
    POSITION_SL_MOVED = "position.sl_moved"
    POSITION_TP_HIT = "position.tp_hit"
    
    # P&L events
    PNL_UPDATE = "pnl.update"
    PNL_MILESTONE = "pnl.milestone"              # New HWM, drawdown threshold
    DAILY_PNL_SUMMARY = "pnl.daily_summary"
    
    # Trade lifecycle
    SIGNAL_GENERATED = "trade.signal_generated"
    SIGNAL_EXPIRED = "trade.signal_expired"
    CONFLUENCE_SCORED = "trade.confluence_scored"
    RISK_CHECK_PASSED = "trade.risk_check_passed"
    RISK_CHECK_FAILED = "trade.risk_check_failed"
    ORDER_SUBMITTED = "trade.order_submitted"
    ORDER_FILLED = "trade.order_filled"
    ORDER_REJECTED = "trade.order_rejected"
    ORDER_CANCELLED = "trade.order_cancelled"
    
    # Performance
    PERFORMANCE_SNAPSHOT = "performance.snapshot"
    WIN_RATE_UPDATE = "performance.win_rate_update"
    STREAK_DETECTED = "performance.streak_detected"      # Win/loss streak
    DRAWDOWN_ALERT = "performance.drawdown_alert"
    EQUITY_CURVE_UPDATE = "performance.equity_curve"
    
    # Risk utilization
    MARGIN_UPDATE = "risk.margin_update"
    EXPOSURE_UPDATE = "risk.exposure_update"
    CORRELATION_ALERT = "risk.correlation_alert"
    RISK_BUDGET_CONSUMED = "risk.budget_consumed"
    
    # Agent tracking
    AGENT_SIGNAL = "agent.signal"
    AGENT_CONFLICT = "agent.conflict"             # Agents disagree
    AGENT_PERFORMANCE = "agent.performance"
    
    # Anomaly
    ANOMALY_DETECTED = "anomaly.detected"
    EXECUTION_ANOMALY = "anomaly.execution"
    PATTERN_ANOMALY = "anomaly.pattern"
    DATA_ANOMALY = "anomaly.data"
    
    # Reconciliation
    RECONCILIATION_MATCH = "reconciliation.match"
    RECONCILIATION_MISMATCH = "reconciliation.mismatch"
    RECONCILIATION_DRIFT = "reconciliation.drift"
    
    # Notification
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_ACKNOWLEDGED = "notification.acknowledged"
```

### 1.4 Core Data Model

```sql
-- Core trade record — single source of truth
CREATE TABLE trades (
    trade_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id      TEXT,                    -- Broker order ID
    pair             TEXT NOT NULL,
    direction        TEXT NOT NULL,            -- LONG / SHORT
    timeframe        TEXT NOT NULL,            -- Entry timeframe (M15, H1, H4, D1)
    trade_type       TEXT NOT NULL,            -- trend_continuation, reversal, breakout, range_play
    
    -- Entry
    entry_price      NUMERIC(18,8),
    entry_time       TIMESTAMPTZ,
    entry_slippage   NUMERIC(18,8),
    entry_spread     NUMERIC(18,8),
    entry_session    TEXT,                     -- asian, london, new_york, overlap
    
    -- Position
    lot_size         NUMERIC(18,4),
    notional_value   NUMERIC(18,2),
    stop_loss        NUMERIC(18,8),
    stop_loss_pips   NUMERIC(18,2),
    
    -- Take profit levels (JSON array)
    take_profits     JSONB,                   -- [{price, r_multiple, close_pct, status}]
    
    -- Exit
    exit_price       NUMERIC(18,8),
    exit_time        TIMESTAMPTZ,
    exit_condition   TEXT,                     -- tp_hit, sl_hit, trailing_stop, manual, time_stop, etc.
    exit_slippage    NUMERIC(18,8),
    
    -- P&L
    gross_pnl        NUMERIC(18,2),
    net_pnl          NUMERIC(18,2),           -- After spread + commission
    commission       NUMERIC(18,2),
    swap             NUMERIC(18,2),
    r_multiple       NUMERIC(18,4),
    
    -- Context at entry
    confluence_score NUMERIC(5,4),            -- 0.0000 - 1.0000
    setup_grade      TEXT,                     -- A+, A, B, C, D
    regime           TEXT,                     -- trending, range_bound, high_vol, crisis
    adx_at_entry     NUMERIC(8,4),
    atr_at_entry     NUMERIC(18,8),
    
    -- Agent provenance
    agent_signals    JSONB,                   -- Full signal chain from all agents
    signal_summary   TEXT,                     -- Human-readable signal summary
    
    -- Risk context
    risk_amount      NUMERIC(18,2),           -- Dollar amount risked
    risk_pct         NUMERIC(8,4),            -- % of account risked
    drawdown_stage   TEXT,                     -- GREEN, YELLOW, ORANGE, RED at entry
    
    -- Management
    management_log   JSONB,                   -- All SL moves, partial closes, decisions
    
    -- Psychological (optional, human-filled)
    pre_confidence   SMALLINT,                -- 1-10
    emotion_during   TEXT,
    rule_adherence   SMALLINT,                -- 1-10
    post_grade       TEXT,                     -- A, B, C, D, F
    
    -- Metadata
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    closed_at        TIMESTAMPTZ,
    status           TEXT DEFAULT 'open',      -- open, partially_closed, closed
    tags             TEXT[],                   -- Custom tags for filtering
    
    -- Indexes
    CONSTRAINT valid_direction CHECK (direction IN ('LONG', 'SHORT')),
    CONSTRAINT valid_status CHECK (status IN ('open', 'partially_closed', 'closed'))
);

CREATE INDEX idx_trades_pair ON trades(pair);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_entry_time ON trades(entry_time);
CREATE INDEX idx_trades_exit_time ON trades(exit_time);
CREATE INDEX idx_trades_setup_grade ON trades(setup_grade);
CREATE INDEX idx_trades_agent_signals ON trades USING GIN(agent_signals);

-- Position snapshots — real-time state of open positions
CREATE TABLE position_snapshots (
    snapshot_id      BIGSERIAL,
    trade_id         UUID REFERENCES trades(trade_id),
    timestamp        TIMESTAMPTZ NOT NULL,
    current_price    NUMERIC(18,8),
    unrealized_pnl   NUMERIC(18,2),
    unrealized_pnl_r NUMERIC(18,4),          -- In R-multiples
    mae_pips         NUMERIC(18,2),           -- Max Adverse Excursion
    mfe_pips         NUMERIC(18,2),           -- Max Favorable Excursion
    duration_minutes INTEGER,
    sl_current       NUMERIC(18,8),           -- Current SL (may have been moved)
    tp_status        JSONB,                   -- Which TPs have been hit
    partial_closes   JSONB                    -- Log of partial closes
);

CREATE INDEX idx_snapshots_trade ON position_snapshots(trade_id, timestamp DESC);
CREATE INDEX idx_snapshots_time ON position_snapshots(timestamp DESC);

-- Convert to hypertable for TimescaleDB
SELECT create_hypertable('position_snapshots', 'timestamp');

-- Agent signal log — every signal from every agent
CREATE TABLE agent_signals (
    signal_id        BIGSERIAL,
    timestamp        TIMESTAMPTZ NOT NULL,
    agent_id         TEXT NOT NULL,            -- e.g., "S1_FIA", "S7_SMC", "S8_RSI"
    signal_type      TEXT NOT NULL,            -- BIAS, LEVEL, PATTERN, CONFIRMATION, WARNING
    pair             TEXT NOT NULL,
    direction        TEXT,
    strength         NUMERIC(5,4),            -- 0.0 - 1.0
    confidence       NUMERIC(5,4),            -- 0.0 - 1.0
    data             JSONB,                   -- Full signal payload
    trade_id         UUID,                    -- Linked trade (filled when trade opens)
    ttl_seconds      INTEGER,                 -- Signal expiry
    expired          BOOLEAN DEFAULT FALSE,
    contributed      BOOLEAN DEFAULT FALSE     -- Did this signal contribute to a trade?
);

CREATE INDEX idx_signals_agent ON agent_signals(agent_id, timestamp DESC);
CREATE INDEX idx_signals_trade ON agent_signals(trade_id);
CREATE INDEX idx_signals_pair ON agent_signals(pair, timestamp DESC);

SELECT create_hypertable('agent_signals', 'timestamp');

-- P&L time series — equity curve at every tick/candle
CREATE TABLE equity_curve (
    timestamp        TIMESTAMPTZ NOT NULL PRIMARY KEY,
    equity           NUMERIC(18,2) NOT NULL,
    balance           NUMERIC(18,2) NOT NULL,
    unrealized_pnl   NUMERIC(18,2),
    realized_pnl_day NUMERIC(18,2),
    drawdown_pct     NUMERIC(8,4),
    drawdown_from_hwm NUMERIC(8,4),
    open_positions   INTEGER,
    total_exposure   NUMERIC(18,2)
);

SELECT create_hypertable('equity_curve', 'timestamp');

-- Anomaly log
CREATE TABLE anomalies (
    anomaly_id       BIGSERIAL PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    anomaly_type     TEXT NOT NULL,            -- execution, pattern, data, risk
    severity         TEXT NOT NULL,
    description      TEXT NOT NULL,
    context          JSONB,                    -- Full context data
    trade_id         UUID,
    acknowledged     BOOLEAN DEFAULT FALSE,
    acknowledged_by  TEXT,
    acknowledged_at  TIMESTAMPTZ,
    resolution       TEXT
);

CREATE INDEX idx_anomalies_type ON anomalies(anomaly_type, timestamp DESC);
CREATE INDEX idx_anomalies_unacked ON anomalies(acknowledged) WHERE NOT acknowledged;

-- Reconciliation records
CREATE TABLE reconciliation_log (
    recon_id         BIGSERIAL PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    broker           TEXT NOT NULL,
    internal_count   INTEGER,
    broker_count     INTEGER,
    matched          INTEGER,
    mismatched       INTEGER,
    status           TEXT NOT NULL,            -- matched, mismatched, drift
    details          JSONB,                    -- Specific mismatches
    resolved         BOOLEAN DEFAULT FALSE,
    resolved_at      TIMESTAMPTZ
);

-- Performance snapshots — periodic aggregation
CREATE TABLE performance_snapshots (
    snapshot_id      BIGSERIAL PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    period           TEXT NOT NULL,            -- daily, weekly, monthly, quarterly
    
    -- Trade counts
    total_trades     INTEGER,
    winning_trades   INTEGER,
    losing_trades    INTEGER,
    breakeven_trades INTEGER,
    
    -- Returns
    gross_profit     NUMERIC(18,2),
    gross_loss       NUMERIC(18,2),
    net_profit       NUMERIC(18,2),
    total_r_gained   NUMERIC(18,4),
    
    -- Ratios
    win_rate         NUMERIC(8,4),
    profit_factor    NUMERIC(8,4),
    expectancy       NUMERIC(18,4),            -- Per-trade expected R
    sharpe_ratio     NUMERIC(8,4),
    sortino_ratio    NUMERIC(8,4),
    calmar_ratio     NUMERIC(8,4),
    
    -- Risk
    max_drawdown     NUMERIC(8,4),
    max_drawdown_dur INTEGER,                   -- Hours
    max_consec_losses INTEGER,
    max_consec_wins  INTEGER,
    avg_risk_per_trade NUMERIC(8,4),
    
    -- R-multiples
    avg_winner_r     NUMERIC(18,4),
    avg_loser_r      NUMERIC(18,4),
    largest_winner_r NUMERIC(18,4),
    largest_loser_r  NUMERIC(18,4),
    
    -- Time metrics
    avg_trade_duration NUMERIC(18,2),           -- Hours
    avg_time_to_tp   NUMERIC(18,2),
    avg_time_to_sl   NUMERIC(18,2),
    
    -- Breakdown by dimension
    by_pair          JSONB,                     -- Per-pair breakdown
    by_session       JSONB,                     -- Per-session breakdown
    by_setup_grade   JSONB,                     -- Per-grade breakdown
    by_agent         JSONB,                     -- Per-agent contribution
    by_regime        JSONB,                     -- Per-regime breakdown
    
    -- Comparison
    vs_previous      JSONB,                     -- Change vs previous period
    vs_target        JSONB                      -- Comparison to targets/benchmarks
);

CREATE INDEX idx_perf_period ON performance_snapshots(period, timestamp DESC);
```

### 1.5 Integration with Existing Systems

The TMS integrates with the existing Alpha Stack architecture at these points:

```
┌──────────────────────────────────────────────────────────────────┐
│                    INTEGRATION TOUCHPOINTS                        │
│                                                                   │
│  Trading Engine (architecture_trading_engine.md)                  │
│  ├── S1-S8 Signal Generation → TMS captures all signals          │
│  ├── S9-S10 Confluence Engine → TMS records confluence scores     │
│  ├── S11-S15 Execution Layer → TMS tracks order lifecycle         │
│  └── S16 Journal/Learning → TMS feeds data to journal system      │
│                                                                   │
│  Risk Management (architecture_risk.md)                          │
│  ├── Risk Governor → TMS monitors approval/rejection rates        │
│  ├── Drawdown Manager → TMS tracks drawdown stage transitions     │
│  ├── Circuit Breaker → TMS logs all breaker trips                 │
│  ├── Correlation Monitor → TMS surfaces correlation state         │
│  └── Black Swan Detector → TMS triggers emergency notifications   │
│                                                                   │
│  Strategy Enhancement (Steps 1-16)                               │
│  ├── Agent signals → TMS captures full provenance chain          │
│  ├── Entry/Exit decisions → TMS records decision context         │
│  └── Performance by step → TMS attributes outcomes to steps      │
│                                                                   │
│  Market Microstructure                                            │
│  ├── Spread data → TMS tracks spread cost per trade              │
│  ├── Order flow → TMS correlates flow with outcomes              │
│  └── Slippage → TMS monitors execution quality                   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Real-Time Position Tracking

### 2.1 Position State Machine

Every position follows a deterministic state machine. The TMS tracks state transitions and emits events at each change.

```
┌─────────┐    order_filled     ┌──────────┐    partial_close    ┌──────────────┐
│  NONE   │ ──────────────────→ │   OPEN   │ ─────────────────→ │ PARTIALLY    │
│         │                     │          │                     │ CLOSED       │
└─────────┘                     └────┬─────┘                     └──────┬───────┘
                                     │                                  │
                                     │ final_close                      │ final_close
                                     ▼                                  ▼
                              ┌──────────────┐                  ┌──────────────┐
                              │   CLOSED     │                  │   CLOSED     │
                              └──────────────┘                  └──────────────┘

Sub-states within OPEN:
  ├── MONITORING      → Normal position, SL/TP active
  ├── SL_MOVED_BE     → SL moved to breakeven
  ├── TRAILING_ACTIVE → Trailing stop engaged
  ├── NEWS_MANAGEMENT → Pre-news position adjustment
  ├── RISK_ALERT      → Position flagged by risk system
  └── EXIT_PENDING    → Exit signal generated, awaiting execution
```

### 2.2 Real-Time Position Tracker

```python
class RealTimePositionTracker:
    """
    Maintains real-time state of all open positions.
    Updates on every tick. Sub-second latency to dashboard.
    """
    
    def __init__(self, redis_client, timescaledb, event_bus):
        self.redis = redis_client          # Real-time state
        self.db = timescaledb              # Persistent storage
        self.event_bus = event_bus         # Event publishing
        self.positions: dict[str, PositionState] = {}
        self.high_water_mark: Decimal = Decimal('0')
        self.equity_at_day_start: Decimal = Decimal('0')
    
    async def on_tick(self, tick: TickEvent):
        """Called on every price tick for all tracked pairs."""
        
        for trade_id, pos in self.positions.items():
            if pos.pair != tick.pair:
                continue
            
            # Update current price
            pos.current_price = tick.bid if pos.direction == 'LONG' else tick.ask
            
            # Calculate unrealized P&L
            if pos.direction == 'LONG':
                price_change = pos.current_price - pos.entry_price
            else:
                price_change = pos.entry_price - pos.current_price
            
            pos.unrealized_pnl = price_change * pos.lot_size * pos.pip_value_per_lot
            pos.unrealized_pnl_r = price_change / pos.stop_distance if pos.stop_distance > 0 else 0
            
            # Update MFE/MAE
            pos.mfe_pips = max(pos.mfe_pips, price_change / pos.pip_size)
            pos.mae_pips = max(pos.mae_pips, -price_change / pos.pip_size)
            
            # Duration
            pos.duration_seconds = (datetime.utcnow() - pos.entry_time).total_seconds()
            
            # Store snapshot (throttled — every 5 seconds for tick data)
            if (datetime.utcnow() - pos.last_snapshot_time).total_seconds() >= 5:
                await self._store_snapshot(pos)
                pos.last_snapshot_time = datetime.utcnow()
            
            # Update Redis for real-time dashboard
            await self._update_redis(pos)
        
        # Update aggregate metrics
        await self._update_aggregates()
    
    async def on_position_opened(self, event: MonitoringEvent):
        """Register a new position."""
        data = event.data
        
        pos = PositionState(
            trade_id=event.trade_id,
            external_id=data['external_id'],
            pair=data['pair'],
            direction=data['direction'],
            entry_price=Decimal(str(data['entry_price'])),
            entry_time=event.timestamp,
            lot_size=Decimal(str(data['lot_size'])),
            stop_loss=Decimal(str(data['stop_loss'])),
            stop_distance=abs(Decimal(str(data['entry_price'])) - Decimal(str(data['stop_loss']))),
            take_profits=data['take_profits'],
            confluence_score=data['confluence_score'],
            setup_grade=data['setup_grade'],
            agent_signals=data['agent_signals'],
            risk_amount=Decimal(str(data['risk_amount'])),
            risk_pct=Decimal(str(data['risk_pct'])),
            entry_session=data.get('entry_session'),
            regime=data.get('regime'),
            management_log=[],
            mfe_pips=Decimal('0'),
            mae_pips=Decimal('0'),
            last_snapshot_time=event.timestamp
        )
        
        self.positions[event.trade_id] = pos
        
        # Publish event
        await self.event_bus.publish('trade.opened', event)
        
        # Store in database
        await self._store_trade_record(pos)
        
        # Update real-time state
        await self._update_redis(pos)
        await self._update_aggregates()
    
    async def on_position_closed(self, event: MonitoringEvent):
        """Handle position close — full or partial."""
        data = event.data
        trade_id = event.trade_id
        
        pos = self.positions.get(trade_id)
        if not pos:
            logger.warning(f"Close event for unknown position: {trade_id}")
            return
        
        # Update exit data
        pos.exit_price = Decimal(str(data['exit_price']))
        pos.exit_time = event.timestamp
        pos.exit_condition = data['exit_condition']
        pos.exit_slippage = Decimal(str(data.get('exit_slippage', 0)))
        
        # Final P&L
        if pos.direction == 'LONG':
            price_change = pos.exit_price - pos.entry_price
        else:
            price_change = pos.entry_price - pos.exit_price
        
        pos.gross_pnl = price_change * pos.lot_size * pos.pip_value_per_lot
        pos.commission = Decimal(str(data.get('commission', 0)))
        pos.swap = Decimal(str(data.get('swap', 0)))
        pos.net_pnl = pos.gross_pnl - pos.commission - pos.swap
        pos.r_multiple = price_change / pos.stop_distance if pos.stop_distance > 0 else Decimal('0')
        
        # Update trade record
        await self._finalize_trade_record(pos)
        
        # Remove from active positions
        del self.positions[trade_id]
        
        # Publish event
        await self.event_bus.publish('trade.closed', event)
        
        # Update aggregates
        await self._update_aggregates()
        
        # Trigger performance recalculation
        await self._trigger_performance_update()
    
    async def on_sl_moved(self, trade_id: str, new_sl: Decimal, reason: str):
        """Track stop-loss modifications."""
        pos = self.positions.get(trade_id)
        if not pos:
            return
        
        old_sl = pos.stop_loss
        pos.stop_loss = new_sl
        pos.stop_distance = abs(pos.entry_price - new_sl)
        
        # Log management action
        pos.management_log.append({
            'time': datetime.utcnow().isoformat(),
            'action': 'sl_moved',
            'old_value': str(old_sl),
            'new_value': str(new_sl),
            'reason': reason
        })
        
        # Update state
        if reason == 'breakeven':
            pos.sub_state = 'SL_MOVED_BE'
        elif reason == 'trailing':
            pos.sub_state = 'TRAILING_ACTIVE'
        
        await self.event_bus.publish('position.sl_moved', MonitoringEvent(
            event_type=MonitoringEventType.POSITION_SL_MOVED,
            trade_id=trade_id,
            data={'old_sl': str(old_sl), 'new_sl': str(new_sl), 'reason': reason}
        ))
        
        await self._update_redis(pos)
    
    async def on_partial_close(self, trade_id: str, close_pct: Decimal, 
                                fill_price: Decimal, reason: str):
        """Track partial position closes."""
        pos = self.positions.get(trade_id)
        if not pos:
            return
        
        closed_lot = pos.lot_size * close_pct / 100
        
        # Calculate partial P&L
        if pos.direction == 'LONG':
            partial_pnl = (fill_price - pos.entry_price) * closed_lot * pos.pip_value_per_lot
        else:
            partial_pnl = (pos.entry_price - fill_price) * closed_lot * pos.pip_value_per_lot
        
        pos.partial_closes.append({
            'time': datetime.utcnow().isoformat(),
            'close_pct': str(close_pct),
            'closed_lot': str(closed_lot),
            'fill_price': str(fill_price),
            'partial_pnl': str(partial_pnl),
            'reason': reason,
            'r_multiple': str((fill_price - pos.entry_price) / pos.stop_distance) if pos.direction == 'LONG'
                          else str((pos.entry_price - fill_price) / pos.stop_distance)
        })
        
        # Reduce remaining lot size
        pos.lot_size -= closed_lot
        pos.status = 'partially_closed' if pos.lot_size > 0 else 'closed'
        
        await self.event_bus.publish('position.partial_close', MonitoringEvent(
            event_type=MonitoringEventType.POSITION_PARTIAL_CLOSE,
            trade_id=trade_id,
            data={
                'close_pct': str(close_pct),
                'remaining_lot': str(pos.lot_size),
                'partial_pnl': str(partial_pnl),
                'reason': reason
            }
        ))
    
    async def _update_aggregates(self):
        """Update aggregate position metrics in Redis."""
        total_exposure = sum(p.risk_amount for p in self.positions.values())
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        open_count = len(self.positions)
        
        # Update high water mark
        current_equity = self.equity_at_day_start + total_unrealized
        if current_equity > self.high_water_mark:
            self.high_water_mark = current_equity
        
        drawdown_pct = ((self.high_water_mark - current_equity) / self.high_water_mark * 100 
                       if self.high_water_mark > 0 else 0)
        
        await self.redis.hset('monitoring:realtime', mapping={
            'open_positions': open_count,
            'total_exposure': str(total_exposure),
            'total_unrealized_pnl': str(total_unrealized),
            'high_water_mark': str(self.high_water_mark),
            'drawdown_pct': str(drawdown_pct),
            'last_update': datetime.utcnow().isoformat()
        })
        
        # Publish aggregate update
        await self.event_bus.publish('pnl.update', MonitoringEvent(
            event_type=MonitoringEventType.PNL_UPDATE,
            data={
                'unrealized_pnl': str(total_unrealized),
                'exposure': str(total_exposure),
                'drawdown_pct': str(drawdown_pct),
                'open_count': open_count
            }
        ))
    
    async def _store_snapshot(self, pos: PositionState):
        """Store position snapshot in TimescaleDB."""
        await self.db.execute("""
            INSERT INTO position_snapshots 
            (trade_id, timestamp, current_price, unrealized_pnl, unrealized_pnl_r,
             mae_pips, mfe_pips, duration_minutes, sl_current, tp_status, partial_closes)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """, pos.trade_id, datetime.utcnow(), pos.current_price, pos.unrealized_pnl,
             pos.unrealized_pnl_r, pos.mae_pips, pos.mfe_pips,
             int(pos.duration_seconds / 60), pos.stop_loss,
             json.dumps(pos.tp_status), json.dumps(pos.partial_closes))
    
    async def get_all_positions(self) -> list[dict]:
        """Get current state of all open positions for dashboard."""
        return [
            {
                'trade_id': p.trade_id,
                'pair': p.pair,
                'direction': p.direction,
                'entry_price': str(p.entry_price),
                'current_price': str(p.current_price),
                'lot_size': str(p.lot_size),
                'unrealized_pnl': str(p.unrealized_pnl),
                'unrealized_pnl_r': str(p.unrealized_pnl_r),
                'mfe_pips': str(p.mfe_pips),
                'mae_pips': str(p.mae_pips),
                'duration': str(timedelta(seconds=int(p.duration_seconds))),
                'setup_grade': p.setup_grade,
                'confluence_score': str(p.confluence_score),
                'sl_current': str(p.stop_loss),
                'sub_state': p.sub_state
            }
            for p in self.positions.values()
        ]
```

### 2.3 Position State in Redis

For sub-second dashboard updates, position state is maintained in Redis:

```
monitoring:realtime                    → Hash of aggregate metrics
monitoring:position:{trade_id}         → Hash of individual position state
monitoring:positions:open              → Sorted set (by unrealized P&L)
monitoring:equity:current              → Current equity value
monitoring:equity:hwm                  → High water mark
monitoring:drawdown:current            → Current drawdown %
monitoring:exposure:total              → Total open risk exposure
monitoring:exposure:by_pair            → Hash of exposure per pair
```

---

## 3. Trade Lifecycle Monitoring

### 3.1 Complete Trade Lifecycle

Every trade passes through a defined lifecycle. The TMS captures context at each stage.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         TRADE LIFECYCLE                                          │
│                                                                                   │
│  STAGE 1: SIGNAL GENERATION (S1-S8)                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  S1 Fundamental → S2 Bias → S3 Session → S4 Structure → S5 S/R →        │    │
│  │  S6 Liquidity → S7 SMC → S8 RSI                                          │    │
│  │                                                                           │    │
│  │  TMS captures: Each agent's signal, strength, confidence, timestamp      │    │
│  │  TMS stores: agent_signals table (full provenance chain)                 │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                           │
│                                      ▼                                           │
│  STAGE 2: CONFLUENCE SCORING (S9-S10)                                            │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  Candlestick Confirmation (S9) → Entry Decision (S10)                    │    │
│  │                                                                           │    │
│  │  TMS captures: Final confluence score, setup grade, all contributing     │    │
│  │  signals with weights, entry method decision (limit/market/skip)        │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                           │
│                                      ▼                                           │
│  STAGE 3: RISK CHECK                                                             │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  Risk Governor pre-trade gate                                            │    │
│  │                                                                           │    │
│  │  TMS captures: Approval/rejection, all check results, adjusted params   │    │
│  │  If rejected: Log reason, link to signal chain for analysis              │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                           │
│                                      ▼                                           │
│  STAGE 4: POSITION SIZING (S11) + STOP LOSS (S12)                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  Position Sizing Engine calculates lot size, SL placed                   │    │
│  │                                                                           │    │
│  │  TMS captures: Final lot size, risk amount, risk %, SL level,           │    │
│  │  sizing breakdown (F1-F4 factors), stop placement reasoning             │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                           │
│                                      ▼                                           │
│  STAGE 5: ORDER EXECUTION                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  Broker layer submits order, receives fill                               │    │
│  │                                                                           │    │
│  │  TMS captures: Order type, expected vs actual fill price, slippage,     │    │
│  │  spread at fill, latency (order submit → fill confirmation)             │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                           │
│                                      ▼                                           │
│  STAGE 6: TRADE MANAGEMENT (S13-S14)                                             │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  TP hits, SL moves, partial closes, trailing stops, news management     │    │
│  │                                                                           │    │
│  │  TMS captures: Every management action with timestamp, price, reason    │    │
│  │  Real-time: MFE/MAE tracking, duration, current R-multiple              │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                           │
│                                      ▼                                           │
│  STAGE 7: EXIT (S15)                                                             │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  TP hit, SL hit, trailing stop, time stop, manual close,                │    │
│  │  structure invalidation, news exit, black swan exit                      │    │
│  │                                                                           │    │
│  │  TMS captures: Exit condition, exit price, slippage, final P&L,        │    │
│  │  R-multiple, total duration, MFE/MAE, all management actions            │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                           │
│                                      ▼                                           │
│  STAGE 8: POST-TRADE ANALYSIS (S16)                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  Journal entry, performance update, pattern recognition, ML feedback    │    │
│  │                                                                           │    │
│  │  TMS provides: Complete trade record with full context for journal      │    │
│  │  TMS triggers: Performance snapshot update, agent performance scoring   │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Trade Lifecycle Event Logger

```python
class TradeLifecycleMonitor:
    """
    Tracks every trade from signal generation to post-trade analysis.
    Maintains the complete provenance chain for each trade.
    """
    
    def __init__(self, db, event_bus, redis):
        self.db = db
        self.event_bus = event_bus
        self.redis = redis
        self.pending_signals: dict[str, list[SignalEvent]] = {}  # pair → signals
        self.active_trades: dict[str, TradeLifecycle] = {}       # trade_id → lifecycle
    
    async def on_signal(self, event: MonitoringEvent):
        """Capture agent signals before they become trades."""
        pair = event.pair
        agent_id = event.data['agent_id']
        
        # Store signal in agent_signals table
        await self.db.execute("""
            INSERT INTO agent_signals 
            (timestamp, agent_id, signal_type, pair, direction, strength, confidence, data, ttl_seconds)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, event.timestamp, agent_id, event.data['signal_type'], pair,
             event.data.get('direction'), event.data.get('strength'),
             event.data.get('confidence'), json.dumps(event.data),
             event.data.get('ttl_seconds', 3600))
        
        # Accumulate signals for confluence tracking
        if pair not in self.pending_signals:
            self.pending_signals[pair] = []
        self.pending_signals[pair].append(event)
        
        # Track signal-to-trade conversion
        await self.redis.hincrby('monitoring:signals:count', agent_id, 1)
        await self.redis.hset('monitoring:signals:latest', agent_id, event.timestamp.isoformat())
    
    async def on_confluence_scored(self, event: MonitoringEvent):
        """Record confluence scoring for a potential trade."""
        data = event.data
        
        await self.db.execute("""
            INSERT INTO trade_lifecycle_events 
            (timestamp, event_type, pair, data)
            VALUES ($1, 'CONFLUENCE_SCORED', $2, $3)
        """, event.timestamp, event.pair, json.dumps({
            'confluence_score': data['confluence_score'],
            'setup_grade': data['setup_grade'],
            'contributing_signals': data['contributing_signals'],
            'signal_weights': data['signal_weights'],
            'entry_method': data.get('entry_method'),
            'decision': data.get('decision')  # trade, skip, wait
        }))
    
    async def on_order_submitted(self, event: MonitoringEvent):
        """Track order submission to broker."""
        trade_id = event.trade_id
        data = event.data
        
        lifecycle = TradeLifecycle(
            trade_id=trade_id,
            pair=data['pair'],
            direction=data['direction'],
            order_type=data['order_type'],
            expected_price=Decimal(str(data['expected_price'])),
            lot_size=Decimal(str(data['lot_size'])),
            submitted_at=event.timestamp,
            agent_signals=self.pending_signals.get(data['pair'], []),
            confluence_score=data.get('confluence_score'),
            setup_grade=data.get('setup_grade')
        )
        
        self.active_trades[trade_id] = lifecycle
        
        # Record order latency start
        await self.redis.hset(f'monitoring:order:{trade_id}', mapping={
            'submitted_at': event.timestamp.isoformat(),
            'expected_price': str(data['expected_price']),
            'status': 'submitted'
        })
    
    async def on_order_filled(self, event: MonitoringEvent):
        """Track order fill — compute slippage, latency."""
        trade_id = event.trade_id
        data = event.data
        lifecycle = self.active_trades.get(trade_id)
        
        if not lifecycle:
            logger.warning(f"Fill for unknown lifecycle: {trade_id}")
            return
        
        fill_price = Decimal(str(data['fill_price']))
        
        # Calculate slippage
        if lifecycle.direction == 'LONG':
            slippage = fill_price - lifecycle.expected_price
        else:
            slippage = lifecycle.expected_price - fill_price
        
        slippage_pips = slippage / lifecycle.pip_size
        
        # Calculate execution latency
        latency_ms = (event.timestamp - lifecycle.submitted_at).total_seconds() * 1000
        
        # Update lifecycle
        lifecycle.fill_price = fill_price
        lifecycle.fill_time = event.timestamp
        lifecycle.slippage_pips = slippage_pips
        lifecycle.execution_latency_ms = latency_ms
        lifecycle.spread_at_fill = Decimal(str(data.get('spread', 0)))
        
        # Update agent signal linkage — mark contributing signals
        for signal in lifecycle.agent_signals:
            await self.db.execute("""
                UPDATE agent_signals SET contributed = TRUE, trade_id = $1
                WHERE signal_id = $2
            """, trade_id, signal.data.get('signal_id'))
        
        # Store complete lifecycle event
        await self.db.execute("""
            INSERT INTO trade_lifecycle_events
            (timestamp, event_type, trade_id, pair, data)
            VALUES ($1, 'ORDER_FILLED', $2, $3, $4)
        """, event.timestamp, trade_id, lifecycle.pair, json.dumps({
            'expected_price': str(lifecycle.expected_price),
            'fill_price': str(fill_price),
            'slippage_pips': str(slippage_pips),
            'spread': str(lifecycle.spread_at_fill),
            'latency_ms': latency_ms,
            'lot_size': str(lifecycle.lot_size)
        }))
        
        # Alert if slippage is excessive
        if abs(slippage_pips) > 2.0:
            await self.event_bus.publish('anomaly.execution', MonitoringEvent(
                event_type=MonitoringEventType.EXECUTION_ANOMALY,
                severity='WARNING',
                trade_id=trade_id,
                data={
                    'type': 'excessive_slippage',
                    'slippage_pips': str(slippage_pips),
                    'threshold': 2.0,
                    'pair': lifecycle.pair
                }
            ))
        
        # Clean up
        await self.redis.delete(f'monitoring:order:{trade_id}')
    
    async def on_management_action(self, event: MonitoringEvent):
        """Track any management action (SL move, partial close, etc.)."""
        trade_id = event.trade_id
        
        await self.db.execute("""
            INSERT INTO trade_lifecycle_events
            (timestamp, event_type, trade_id, pair, data)
            VALUES ($1, $2, $3, $4, $5)
        """, event.timestamp, event.event_type.value, trade_id, event.pair,
             json.dumps(event.data))
        
        # Update Redis for real-time dashboard
        await self.redis.rpush(f'monitoring:management:{trade_id}', json.dumps({
            'time': event.timestamp.isoformat(),
            'action': event.event_type.value,
            'data': event.data
        }))
    
    async def get_trade_lifecycle(self, trade_id: str) -> dict:
        """Get complete lifecycle for a trade — all events from signal to exit."""
        events = await self.db.fetch("""
            SELECT timestamp, event_type, data 
            FROM trade_lifecycle_events
            WHERE trade_id = $1
            ORDER BY timestamp ASC
        """, trade_id)
        
        signals = await self.db.fetch("""
            SELECT agent_id, signal_type, direction, strength, confidence, data
            FROM agent_signals
            WHERE trade_id = $1
            ORDER BY timestamp ASC
        """, trade_id)
        
        return {
            'trade_id': trade_id,
            'events': [dict(e) for e in events],
            'agent_signals': [dict(s) for s in signals],
            'total_events': len(events),
            'contributing_agents': list(set(s['agent_id'] for s in signals if s.get('contributed')))
        }
    
    async def get_signal_conversion_rate(self, period_days: int = 30) -> dict:
        """Analyze signal-to-trade conversion rates by agent."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        results = await self.db.fetch("""
            SELECT 
                agent_id,
                COUNT(*) as total_signals,
                COUNT(*) FILTER (WHERE contributed = TRUE) as contributed_signals,
                COUNT(*) FILTER (WHERE expired = TRUE) as expired_signals,
                AVG(strength) as avg_strength,
                AVG(confidence) as avg_confidence
            FROM agent_signals
            WHERE timestamp > $1
            GROUP BY agent_id
            ORDER BY contributed_signals DESC
        """, cutoff)
        
        return {
            row['agent_id']: {
                'total_signals': row['total_signals'],
                'contributed': row['contributed_signals'],
                'expired': row['expired_signals'],
                'conversion_rate': row['contributed_signals'] / row['total_signals'] if row['total_signals'] > 0 else 0,
                'avg_strength': float(row['avg_strength'] or 0),
                'avg_confidence': float(row['avg_confidence'] or 0)
            }
            for row in results
        }
```

---

## 4. Performance Dashboard

### 4.1 Dashboard Architecture

The performance dashboard provides real-time and historical views across all performance dimensions.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PERFORMANCE DASHBOARD                                    │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  REAL-TIME PANEL (sub-second refresh)                                    │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │    │
│  │  │ Equity   │ │ Open P&L │ │ Drawdown │ │ Open     │ │ Exposure │     │    │
│  │  │ Curve    │ │ $ / R    │ │ % / Stage│ │ Positions│ │ %        │     │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  TODAY'S PANEL                                                           │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │    │
│  │  │ Trades   │ │ Win Rate │ │ Net P&L  │ │ Avg R    │ │ Best /   │     │    │
│  │  │ Today    │ │ Today    │ │ Today    │ │ Today    │ │ Worst    │     │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  ROLLING METRICS (configurable window: 20/50/100 trades)               │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │    │
│  │  │ Expect-  │ │ Profit   │ │ Sharpe   │ │ Max DD   │ │ Consec   │     │    │
│  │  │ ancy (R) │ │ Factor   │ │ Ratio    │ │ (R)      │ │ Losses   │     │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  BREAKDOWN PANELS (filterable by period, pair, session, grade, agent)  │    │
│  │  ┌──────────────────────┐ ┌──────────────────────┐                      │    │
│  │  │ By Pair              │ │ By Session           │                      │    │
│  │  │ EURUSD: 72% / 1.8R   │ │ London: 68% / 1.6R   │                      │    │
│  │  │ GBPUSD: 65% / 1.5R   │ │ NY: 71% / 2.1R       │                      │    │
│  │  │ USDJPY: 58% / 1.2R   │ │ Asian: 55% / 1.0R    │                      │    │
│  │  └──────────────────────┘ └──────────────────────┘                      │    │
│  │  ┌──────────────────────┐ ┌──────────────────────┐                      │    │
│  │  │ By Setup Grade       │ │ By Agent             │                      │    │
│  │  │ A+: 78% / 2.3R       │ │ S7_SMC: +12.5R       │                      │    │
│  │  │ A:  68% / 1.8R       │ │ S4_Struct: +8.2R     │                      │    │
│  │  │ B:  52% / 1.1R       │ │ S6_Liq: +6.8R        │                      │    │
│  │  │ C:  38% / 0.5R       │ │ S1_FIA: -2.1R        │                      │    │
│  │  └──────────────────────┘ └──────────────────────┘                      │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  CHARTS                                                                   │    │
│  │  ┌────────────────────────────────────────────────────────────────┐     │    │
│  │  │ Equity Curve (cumulative R, cumulative $, drawdown overlay)    │     │    │
│  │  ├────────────────────────────────────────────────────────────────┤     │    │
│  │  │ R-Multiple Distribution (histogram of all trade outcomes)      │     │    │
│  │  ├────────────────────────────────────────────────────────────────┤     │    │
│  │  │ Win Rate Rolling Window (20-trade rolling)                     │     │    │
│  │  ├────────────────────────────────────────────────────────────────┤     │    │
│  │  │ MAE/MFE Scatter Plot (per trade, colored by outcome)           │     │    │
│  │  ├────────────────────────────────────────────────────────────────┤     │    │
│  │  │ Heatmap: Performance by Hour × Day of Week                     │     │    │
│  │  └────────────────────────────────────────────────────────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Performance Engine

```python
class PerformanceEngine:
    """
    Calculates all performance metrics in real-time and on-demand.
    Maintains rolling windows for adaptive metrics.
    """
    
    def __init__(self, db, redis, event_bus):
        self.db = db
        self.redis = redis
        self.event_bus = event_bus
        
        # Rolling windows
        self.rolling_window_sizes = [20, 50, 100, 200]
        self.trade_cache: list[TradeResult] = []
        self.equity_series: list[tuple[datetime, Decimal]] = []
    
    async def on_trade_closed(self, trade: TradeResult):
        """Update all metrics when a trade closes."""
        self.trade_cache.append(trade)
        
        # Update real-time metrics
        metrics = self._calculate_rolling_metrics()
        await self._store_realtime_metrics(metrics)
        
        # Check for streaks
        await self._check_streaks()
        
        # Check for performance alerts
        await self._check_performance_alerts(metrics)
        
        # Publish performance update
        await self.event_bus.publish('performance.snapshot', MonitoringEvent(
            event_type=MonitoringEventType.PERFORMANCE_SNAPSHOT,
            data=metrics
        ))
    
    def _calculate_rolling_metrics(self) -> dict:
        """Calculate all metrics across multiple rolling windows."""
        results = {}
        
        for window in self.rolling_window_sizes:
            trades = self.trade_cache[-window:]
            if not trades:
                continue
            
            wins = [t for t in trades if t.r_multiple > 0]
            losses = [t for t in trades if t.r_multiple <= 0]
            breakeven = [t for t in trades if t.r_multiple == 0]
            
            # Basic counts
            total = len(trades)
            win_count = len(wins)
            loss_count = len(losses)
            
            # Win rate
            win_rate = win_count / total if total > 0 else 0
            
            # R-multiples
            total_r = sum(t.r_multiple for t in trades)
            avg_r = total_r / total if total > 0 else 0
            avg_winner_r = sum(t.r_multiple for t in wins) / win_count if win_count > 0 else 0
            avg_loser_r = sum(t.r_multiple for t in losses) / loss_count if loss_count > 0 else 0
            
            # Profit factor
            gross_profit = sum(t.r_multiple for t in wins)
            gross_loss = abs(sum(t.r_multiple for t in losses))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # Expectancy
            expectancy = (win_rate * avg_winner_r) - ((1 - win_rate) * abs(avg_loser_r))
            
            # Sharpe (using R-multiples as returns)
            if total > 1:
                returns = [t.r_multiple for t in trades]
                mean_r = sum(returns) / len(returns)
                variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
                std_r = variance ** 0.5
                sharpe = (mean_r / std_r) * (252 ** 0.5) if std_r > 0 else 0  # Annualized
            else:
                sharpe = 0
            
            # Sortino (downside deviation only)
            downside_returns = [r for r in [t.r_multiple for t in trades] if r < 0]
            if downside_returns and total > 1:
                downside_dev = (sum(r ** 2 for r in downside_returns) / len(downside_returns)) ** 0.5
                sortino = (avg_r / downside_dev) * (252 ** 0.5) if downside_dev > 0 else 0
            else:
                sortino = 0
            
            # Max drawdown (in R)
            cumulative_r = 0
            peak_r = 0
            max_dd_r = 0
            for t in trades:
                cumulative_r += t.r_multiple
                peak_r = max(peak_r, cumulative_r)
                dd = peak_r - cumulative_r
                max_dd_r = max(max_dd_r, dd)
            
            # Max consecutive
            max_consec_wins = self._max_consecutive(trades, 'win')
            max_consec_losses = self._max_consecutive(trades, 'loss')
            
            # Streaks
            current_streak = self._current_streak(trades)
            
            results[f'w{window}'] = {
                'window': window,
                'total_trades': total,
                'winning_trades': win_count,
                'losing_trades': loss_count,
                'breakeven_trades': len(breakeven),
                'win_rate': round(win_rate, 4),
                'total_r': round(total_r, 4),
                'avg_r': round(avg_r, 4),
                'avg_winner_r': round(avg_winner_r, 4),
                'avg_loser_r': round(avg_loser_r, 4),
                'profit_factor': round(profit_factor, 4),
                'expectancy': round(expectancy, 4),
                'sharpe_ratio': round(sharpe, 4),
                'sortino_ratio': round(sortino, 4),
                'max_drawdown_r': round(max_dd_r, 4),
                'max_consec_wins': max_consec_wins,
                'max_consec_losses': max_consec_losses,
                'current_streak': current_streak,
                'largest_winner_r': max((t.r_multiple for t in trades), default=0),
                'largest_loser_r': min((t.r_multiple for t in trades), default=0)
            }
        
        return results
    
    async def get_breakdown(self, dimension: str, period_days: int = 30) -> dict:
        """Get performance breakdown by dimension (pair, session, grade, agent, regime)."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        if dimension == 'pair':
            group_col = 'pair'
        elif dimension == 'session':
            group_col = 'entry_session'
        elif dimension == 'grade':
            group_col = 'setup_grade'
        elif dimension == 'regime':
            group_col = 'regime'
        else:
            raise ValueError(f"Unknown dimension: {dimension}")
        
        rows = await self.db.fetch(f"""
            SELECT 
                {group_col} as dimension_value,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE r_multiple > 0) as wins,
                COUNT(*) FILTER (WHERE r_multiple <= 0) as losses,
                AVG(r_multiple) as avg_r,
                SUM(r_multiple) as total_r,
                AVG(r_multiple) FILTER (WHERE r_multiple > 0) as avg_winner_r,
                AVG(r_multiple) FILTER (WHERE r_multiple <= 0) as avg_loser_r,
                MAX(r_multiple) as best_r,
                MIN(r_multiple) as worst_r,
                AVG(confluence_score) as avg_confluence,
                AVG(duration_minutes) as avg_duration_min
            FROM trades
            WHERE closed_at > $1 AND status = 'closed'
            GROUP BY {group_col}
            ORDER BY total_r DESC
        """, cutoff)
        
        return {
            row['dimension_value']: {
                'total_trades': row['total'],
                'wins': row['wins'],
                'losses': row['losses'],
                'win_rate': round(row['wins'] / row['total'], 4) if row['total'] > 0 else 0,
                'avg_r': round(float(row['avg_r'] or 0), 4),
                'total_r': round(float(row['total_r'] or 0), 4),
                'avg_winner_r': round(float(row['avg_winner_r'] or 0), 4),
                'avg_loser_r': round(float(row['avg_loser_r'] or 0), 4),
                'best_r': round(float(row['best_r'] or 0), 4),
                'worst_r': round(float(row['worst_r'] or 0), 4),
                'avg_confluence': round(float(row['avg_confluence'] or 0), 4),
                'avg_duration_min': round(float(row['avg_duration_min'] or 0), 1)
            }
            for row in rows
        }
    
    async def get_equity_curve(self, period_days: int = 90) -> list[dict]:
        """Get equity curve data for charting."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        rows = await self.db.fetch("""
            SELECT timestamp, equity, balance, unrealized_pnl, 
                   drawdown_pct, open_positions
            FROM equity_curve
            WHERE timestamp > $1
            ORDER BY timestamp ASC
        """, cutoff)
        
        return [dict(r) for r in rows]
    
    async def get_r_distribution(self, period_days: int = 90) -> dict:
        """Get R-multiple distribution for histogram."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        rows = await self.db.fetch("""
            SELECT r_multiple FROM trades
            WHERE closed_at > $1 AND status = 'closed'
            ORDER BY r_multiple
        """, cutoff)
        
        r_values = [float(r['r_multiple']) for r in rows]
        
        # Create histogram bins
        bins = {}
        for r in r_values:
            bin_label = f"{round(r * 2) / 2:.1f}"  # 0.5R bins
            bins[bin_label] = bins.get(bin_label, 0) + 1
        
        return {
            'r_values': r_values,
            'histogram': bins,
            'count': len(r_values),
            'mean': sum(r_values) / len(r_values) if r_values else 0,
            'median': sorted(r_values)[len(r_values) // 2] if r_values else 0
        }
    
    async def get_mae_mfe_data(self, period_days: int = 90) -> list[dict]:
        """Get MAE/MFE scatter plot data."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        rows = await self.db.fetch("""
            SELECT trade_id, pair, direction, r_multiple, 
                   mae_pips, mfe_pips, setup_grade
            FROM trades
            WHERE closed_at > $1 AND status = 'closed'
        """, cutoff)
        
        return [dict(r) for r in rows]
    
    async def get_heatmap_data(self, period_days: int = 90) -> dict:
        """Get performance heatmap by hour × day of week."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        rows = await self.db.fetch("""
            SELECT 
                EXTRACT(DOW FROM entry_time) as day_of_week,
                EXTRACT(HOUR FROM entry_time) as hour,
                COUNT(*) as trades,
                AVG(r_multiple) as avg_r,
                COUNT(*) FILTER (WHERE r_multiple > 0)::float / NULLIF(COUNT(*), 0) as win_rate
            FROM trades
            WHERE entry_time > $1 AND status = 'closed'
            GROUP BY day_of_week, hour
            ORDER BY day_of_week, hour
        """, cutoff)
        
        heatmap = {}
        for row in rows:
            dow = int(row['day_of_week'])
            hour = int(row['hour'])
            heatmap[(dow, hour)] = {
                'trades': row['trades'],
                'avg_r': round(float(row['avg_r'] or 0), 4),
                'win_rate': round(float(row['win_rate'] or 0), 4)
            }
        
        return heatmap
    
    async def _check_streaks(self):
        """Detect and alert on win/loss streaks."""
        recent = self.trade_cache[-10:]
        if len(recent) < 3:
            return
        
        current_streak = self._current_streak(recent)
        
        if current_streak['type'] == 'loss' and current_streak['count'] >= 3:
            await self.event_bus.publish('performance.streak', MonitoringEvent(
                event_type=MonitoringEventType.STREAK_DETECTED,
                severity='WARNING',
                data={
                    'streak_type': 'loss',
                    'count': current_streak['count'],
                    'total_r': current_streak['total_r'],
                    'recommendation': 'Reduce position size by 50%' if current_streak['count'] >= 3 
                                     else 'STOP TRADING — circuit breaker'
                }
            ))
        
        if current_streak['type'] == 'win' and current_streak['count'] >= 5:
            await self.event_bus.publish('performance.streak', MonitoringEvent(
                event_type=MonitoringEventType.STREAK_DETECTED,
                severity='INFO',
                data={
                    'streak_type': 'win',
                    'count': current_streak['count'],
                    'total_r': current_streak['total_r'],
                    'recommendation': 'Positive momentum — maintain discipline, do not oversize'
                }
            ))
    
    async def _check_performance_alerts(self, metrics: dict):
        """Check for performance degradation alerts."""
        w20 = metrics.get('w20', {})
        
        # Win rate below 45% over 20 trades
        if w20.get('win_rate', 1) < 0.45 and w20.get('total_trades', 0) >= 20:
            await self.event_bus.publish('performance.alert', MonitoringEvent(
                event_type=MonitoringEventType.DRAWDOWN_ALERT,
                severity='WARNING',
                data={
                    'alert': 'win_rate_degradation',
                    'win_rate': w20['win_rate'],
                    'window': 20,
                    'recommendation': 'Review recent setups. Consider pausing until edge is confirmed.'
                }
            ))
        
        # Expectancy negative
        if w20.get('expectancy', 0) < 0 and w20.get('total_trades', 0) >= 20:
            await self.event_bus.publish('performance.alert', MonitoringEvent(
                event_type=MonitoringEventType.DRAWDOWN_ALERT,
                severity='CRITICAL',
                data={
                    'alert': 'negative_expectancy',
                    'expectancy': w20['expectancy'],
                    'window': 20,
                    'recommendation': 'NEGATIVE EXPECTANCY — Stop live trading. Review strategy.'
                }
            ))
    
    @staticmethod
    def _max_consecutive(trades: list, kind: str) -> int:
        """Calculate max consecutive wins or losses."""
        max_streak = 0
        current = 0
        for t in trades:
            if (kind == 'win' and t.r_multiple > 0) or (kind == 'loss' and t.r_multiple <= 0):
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak
    
    @staticmethod
    def _current_streak(trades: list) -> dict:
        """Get current win/loss streak."""
        if not trades:
            return {'type': 'none', 'count': 0, 'total_r': 0}
        
        last = trades[-1]
        streak_type = 'win' if last.r_multiple > 0 else 'loss'
        count = 0
        total_r = 0
        
        for t in reversed(trades):
            if (streak_type == 'win' and t.r_multiple > 0) or \
               (streak_type == 'loss' and t.r_multiple <= 0):
                count += 1
                total_r += t.r_multiple
            else:
                break
        
        return {'type': streak_type, 'count': count, 'total_r': round(total_r, 4)}
```

### 4.3 Grafana Dashboard Configuration

```yaml
# Grafana dashboard panels for Alpha Stack Trade Monitoring

dashboards:
  realtime_overview:
    refresh: 1s
    panels:
      - title: "Equity Curve"
        type: timeseries
        query: "SELECT timestamp, equity FROM equity_curve ORDER BY timestamp"
        overrides:
          - drawdown_overlay: true
          - hwm_line: true
      
      - title: "Open Positions"
        type: table
        query: "SELECT * FROM monitoring:positions:open"
        columns: [pair, direction, entry, current, pnl, pnl_r, duration, grade]
        color: conditional (green=profit, red=loss)
      
      - title: "Drawdown Gauge"
        type: gauge
        query: "SELECT drawdown_pct FROM monitoring:realtime"
        thresholds: [3, 7, 12, 18]
        colors: [green, yellow, orange, red]
      
      - title: "Risk Exposure"
        type: stat
        query: "SELECT total_exposure FROM monitoring:realtime"
        unit: percentage
        thresholds: [3, 6]
  
  performance_analytics:
    refresh: 60s
    panels:
      - title: "Rolling Win Rate (20-trade)"
        type: timeseries
        query: calculated from performance engine
      
      - title: "R-Multiple Distribution"
        type: histogram
        query: "SELECT r_multiple FROM trades WHERE status='closed'"
      
      - title: "Performance by Pair"
        type: bargauge
        query: breakdown by pair
      
      - title: "Performance by Session"
        type: bargauge
        query: breakdown by session
      
      - title: "Performance by Grade"
        type: bargauge
        query: breakdown by setup_grade
      
      - title: "MAE/MFE Scatter"
        type: scatter
        x: mae_pips, y: mfe_pips, color: r_multiple
      
      - title: "Hour × Day Heatmap"
        type: heatmap
        query: performance heatmap data
```

---

## 5. Risk Utilization Monitoring

### 5.1 Risk Metrics Dashboard

```python
class RiskUtilizationMonitor:
    """
    Monitors real-time risk utilization across all dimensions.
    Integrates with the Risk Management System (architecture_risk.md).
    """
    
    def __init__(self, db, redis, event_bus):
        self.db = db
        self.redis = redis
        self.event_bus = event_bus
    
    async def get_risk_state(self) -> dict:
        """Get current risk utilization state."""
        
        # Pull from Redis (real-time) and supplement from DB
        realtime = await self.redis.hgetall('monitoring:realtime')
        
        # Margin utilization
        margin_used = Decimal(realtime.get('margin_used', '0'))
        margin_available = Decimal(realtime.get('margin_available', '0'))
        margin_pct = (margin_used / (margin_used + margin_available) * 100 
                     if (margin_used + margin_available) > 0 else 0)
        
        # Exposure by pair
        exposure_by_pair = await self.redis.hgetall('monitoring:exposure:by_pair')
        
        # Correlation state
        correlation_data = await self.redis.hgetall('monitoring:correlation')
        
        # Drawdown state
        drawdown_pct = Decimal(realtime.get('drawdown_pct', '0'))
        drawdown_stage = self._classify_drawdown_stage(drawdown_pct)
        
        # Daily P&L
        daily_pnl = Decimal(realtime.get('daily_pnl', '0'))
        daily_loss_pct = abs(daily_pnl) / Decimal(realtime.get('equity', '1')) * 100 if daily_pnl < 0 else Decimal('0')
        
        # Circuit breaker states
        breakers = await self.redis.hgetall('monitoring:circuit_breakers')
        
        return {
            'margin': {
                'used': str(margin_used),
                'available': str(margin_available),
                'utilization_pct': str(round(margin_pct, 2)),
                'limit_pct': 30,
                'status': 'OK' if margin_pct < 25 else 'WARNING' if margin_pct < 30 else 'BREACH'
            },
            'exposure': {
                'total_risk': realtime.get('total_exposure', '0'),
                'open_positions': realtime.get('open_positions', '0'),
                'limit_pct': 6,
                'by_pair': dict(exposure_by_pair),
                'status': 'OK' if Decimal(realtime.get('total_exposure', '0')) < Decimal(realtime.get('equity', '1')) * Decimal('0.05') else 'WARNING'
            },
            'drawdown': {
                'current_pct': str(round(drawdown_pct, 2)),
                'stage': drawdown_stage,
                'high_water_mark': realtime.get('high_water_mark', '0'),
                'daily_pnl': str(daily_pnl),
                'daily_loss_pct': str(round(daily_loss_pct, 2))
            },
            'correlation': {
                'mean_correlation': correlation_data.get('mean', '0'),
                'max_pair': correlation_data.get('max_pair', ''),
                'max_value': correlation_data.get('max_value', '0'),
                'regime': correlation_data.get('regime', 'NORMAL')
            },
            'circuit_breakers': {
                name: state for name, state in breakers.items()
            },
            'news_blackout': {
                'active': realtime.get('news_blackout_active', 'false') == 'true',
                'event': realtime.get('news_blackout_event', ''),
                'until': realtime.get('news_blackout_until', '')
            }
        }
    
    async def get_exposure_timeline(self, period_hours: int = 24) -> list[dict]:
        """Get exposure over time for charting."""
        cutoff = datetime.utcnow() - timedelta(hours=period_hours)
        
        rows = await self.db.fetch("""
            SELECT timestamp, total_exposure, open_positions, 
                   drawdown_pct, margin_utilization
            FROM equity_curve
            WHERE timestamp > $1
            ORDER BY timestamp ASC
        """, cutoff)
        
        return [dict(r) for r in rows]
    
    async def get_risk_budget_consumption(self) -> dict:
        """Track how much of each risk budget has been consumed."""
        
        # Get current state
        equity = Decimal(await self.redis.hget('monitoring:realtime', 'equity') or '0')
        daily_pnl = Decimal(await self.redis.hget('monitoring:realtime', 'daily_pnl') or '0')
        weekly_pnl = Decimal(await self.redis.hget('monitoring:realtime', 'weekly_pnl') or '0')
        monthly_pnl = Decimal(await self.redis.hget('monitoring:realtime', 'monthly_pnl') or '0')
        total_exposure = Decimal(await self.redis.hget('monitoring:realtime', 'total_exposure') or '0')
        drawdown_pct = Decimal(await self.redis.hget('monitoring:realtime', 'drawdown_pct') or '0')
        
        return {
            'daily_loss': {
                'consumed': str(abs(min(daily_pnl, Decimal('0')))),
                'limit': str(equity * Decimal('0.04')),
                'pct_of_limit': str(abs(min(daily_pnl, Decimal('0'))) / (equity * Decimal('0.04')) * 100 
                                   if equity > 0 else 0)
            },
            'weekly_loss': {
                'consumed': str(abs(min(weekly_pnl, Decimal('0')))),
                'limit': str(equity * Decimal('0.08')),
                'pct_of_limit': str(abs(min(weekly_pnl, Decimal('0'))) / (equity * Decimal('0.08')) * 100 
                                   if equity > 0 else 0)
            },
            'monthly_loss': {
                'consumed': str(abs(min(monthly_pnl, Decimal('0')))),
                'limit': str(equity * Decimal('0.12')),
                'pct_of_limit': str(abs(min(monthly_pnl, Decimal('0'))) / (equity * Decimal('0.12')) * 100 
                                   if equity > 0 else 0)
            },
            'total_exposure': {
                'consumed': str(total_exposure),
                'limit': str(equity * Decimal('0.06')),
                'pct_of_limit': str(total_exposure / (equity * Decimal('0.06')) * 100 
                                   if equity > 0 else 0)
            },
            'max_drawdown': {
                'current': str(drawdown_pct),
                'limit': 18,
                'pct_of_limit': str(drawdown_pct / 18 * 100)
            }
        }
    
    @staticmethod
    def _classify_drawdown_stage(pct: Decimal) -> str:
        if pct >= 18: return 'BLACK'
        if pct >= 12: return 'RED'
        if pct >= 7: return 'ORANGE'
        if pct >= 3: return 'YELLOW'
        return 'GREEN'
```

---

## 6. Agent Contribution Tracking

### 6.1 Agent Performance Attribution

The multi-agent system (Steps 1-16) generates signals from multiple agents. The TMS tracks which agents contributed to each trade and their individual performance.

```python
class AgentContributionTracker:
    """
    Tracks agent signal generation, contribution to trades, and individual performance.
    Enables identification of which agents add value and which add noise.
    """
    
    AGENTS = {
        'S1_FIA': 'Fundamental Intelligence Agent',
        'S2_MBA': 'Market Bias Agent',
        'S3_SAA': 'Session Analysis Agent',
        'S4_MSA': 'Market Structure Agent',
        'S5_SR': 'Support/Resistance Agent',
        'S6_LIQ': 'Liquidity Agent',
        'S7_SMC': 'Smart Money Concepts Agent',
        'S8_RSI': 'RSI Confirmation Agent',
        'S9_CDL': 'Candlestick Agent',
        'S10_ENTRY': 'Entry Decision Agent',
        'S11_SIZE': 'Position Sizing Agent',
        'S12_SL': 'Stop Loss Agent',
        'S13_TP': 'Take Profit Agent',
        'S14_MGMT': 'Trade Management Agent',
        'S15_EXIT': 'Exit Agent',
        'S16_JOURNAL': 'Journal/Learning Agent'
    }
    
    def __init__(self, db, redis, event_bus):
        self.db = db
        self.redis = redis
        self.event_bus = event_bus
    
    async def get_agent_performance(self, period_days: int = 30) -> dict:
        """Get performance metrics for each agent."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        # Get all signals with trade outcomes
        rows = await self.db.fetch("""
            SELECT 
                s.agent_id,
                s.signal_type,
                s.direction,
                s.strength,
                s.confidence,
                s.contributed,
                t.r_multiple,
                t.setup_grade,
                t.pair,
                t.entry_session
            FROM agent_signals s
            LEFT JOIN trades t ON s.trade_id = t.trade_id
            WHERE s.timestamp > $1
            ORDER BY s.agent_id, s.timestamp
        """, cutoff)
        
        # Aggregate by agent
        agent_data = {}
        for row in rows:
            agent_id = row['agent_id']
            if agent_id not in agent_data:
                agent_data[agent_id] = {
                    'total_signals': 0,
                    'contributed_signals': 0,
                    'expired_signals': 0,
                    'avg_strength': [],
                    'avg_confidence': [],
                    'trade_outcomes': [],
                    'by_pair': {},
                    'by_direction': {'LONG': [], 'SHORT': []}
                }
            
            ad = agent_data[agent_id]
            ad['total_signals'] += 1
            
            if row['contributed']:
                ad['contributed_signals'] += 1
            
            if row['strength']:
                ad['avg_strength'].append(float(row['strength']))
            if row['confidence']:
                ad['avg_confidence'].append(float(row['confidence']))
            
            if row['r_multiple'] is not None:
                ad['trade_outcomes'].append(float(row['r_multiple']))
                
                pair = row['pair']
                if pair not in ad['by_pair']:
                    ad['by_pair'][pair] = []
                ad['by_pair'][pair].append(float(row['r_multiple']))
                
                direction = row['direction']
                if direction in ad['by_direction']:
                    ad['by_direction'][direction].append(float(row['r_multiple']))
        
        # Calculate final metrics per agent
        results = {}
        for agent_id, ad in agent_data.items():
            outcomes = ad['trade_outcomes']
            total_r = sum(outcomes)
            wins = [o for o in outcomes if o > 0]
            losses = [o for o in outcomes if o <= 0]
            
            results[agent_id] = {
                'name': self.AGENTS.get(agent_id, agent_id),
                'total_signals': ad['total_signals'],
                'contributed_signals': ad['contributed_signals'],
                'conversion_rate': ad['contributed_signals'] / ad['total_signals'] if ad['total_signals'] > 0 else 0,
                'avg_strength': sum(ad['avg_strength']) / len(ad['avg_strength']) if ad['avg_strength'] else 0,
                'avg_confidence': sum(ad['avg_confidence']) / len(ad['avg_confidence']) if ad['avg_confidence'] else 0,
                'total_trades': len(outcomes),
                'total_r': round(total_r, 4),
                'win_rate': len(wins) / len(outcomes) if outcomes else 0,
                'avg_r': total_r / len(outcomes) if outcomes else 0,
                'avg_winner_r': sum(wins) / len(wins) if wins else 0,
                'avg_loser_r': sum(losses) / len(losses) if losses else 0,
                'best_pair': max(ad['by_pair'].items(), key=lambda x: sum(x[1]))[0] if ad['by_pair'] else None,
                'worst_pair': min(ad['by_pair'].items(), key=lambda x: sum(x[1]))[0] if ad['by_pair'] else None,
                'by_pair': {
                    pair: {
                        'trades': len(rs),
                        'total_r': round(sum(rs), 4),
                        'win_rate': len([r for r in rs if r > 0]) / len(rs) if rs else 0
                    }
                    for pair, rs in ad['by_pair'].items()
                }
            }
        
        return results
    
    async def get_agent_contribution_map(self, trade_id: str) -> list[dict]:
        """Get full agent contribution chain for a specific trade."""
        signals = await self.db.fetch("""
            SELECT agent_id, signal_type, direction, strength, confidence, 
                   data, timestamp, contributed
            FROM agent_signals
            WHERE trade_id = $1
            ORDER BY timestamp ASC
        """, trade_id)
        
        return [
            {
                'agent': s['agent_id'],
                'agent_name': self.AGENTS.get(s['agent_id'], s['agent_id']),
                'signal_type': s['signal_type'],
                'direction': s['direction'],
                'strength': float(s['strength'] or 0),
                'confidence': float(s['confidence'] or 0),
                'contributed': s['contributed'],
                'timestamp': s['timestamp'].isoformat(),
                'data': s['data']
            }
            for s in signals
        ]
    
    async def get_agent_correlation_matrix(self, period_days: int = 30) -> dict:
        """Analyze how agents agree/disagree with each other."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        # Get all signals grouped by trade
        rows = await self.db.fetch("""
            SELECT trade_id, agent_id, direction, strength
            FROM agent_signals
            WHERE trade_id IS NOT NULL AND timestamp > $1
            ORDER BY trade_id, agent_id
        """, cutoff)
        
        # Build agreement matrix
        trades_by_id = {}
        for row in rows:
            tid = row['trade_id']
            if tid not in trades_by_id:
                trades_by_id[tid] = {}
            trades_by_id[tid][row['agent_id']] = {
                'direction': row['direction'],
                'strength': float(row['strength'] or 0)
            }
        
        # Calculate pairwise agreement rates
        agent_ids = list(self.AGENTS.keys())
        agreement_matrix = {}
        
        for a1 in agent_ids:
            for a2 in agent_ids:
                if a1 >= a2:
                    continue
                
                agree_count = 0
                total_count = 0
                
                for tid, signals in trades_by_id.items():
                    if a1 in signals and a2 in signals:
                        total_count += 1
                        if signals[a1]['direction'] == signals[a2]['direction']:
                            agree_count += 1
                
                if total_count > 0:
                    agreement_matrix[f"{a1}↔{a2}"] = {
                        'agreement_rate': agree_count / total_count,
                        'sample_size': total_count
                    }
        
        return agreement_matrix
    
    async def get_signal_quality_scores(self, period_days: int = 30) -> dict:
        """
        Score each agent's signal quality based on:
        1. Directional accuracy (did the trade go in the signaled direction?)
        2. Strength calibration (did high-strength signals outperform low-strength?)
        3. Timing accuracy (did signals arrive at the right time?)
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        rows = await self.db.fetch("""
            SELECT s.agent_id, s.strength, s.confidence, s.direction,
                   t.r_multiple, t.pair, t.entry_time, t.exit_time
            FROM agent_signals s
            JOIN trades t ON s.trade_id = t.trade_id
            WHERE s.timestamp > $1 AND s.contributed = TRUE AND t.status = 'closed'
        """, cutoff)
        
        agent_scores = {}
        for row in rows:
            agent_id = row['agent_id']
            if agent_id not in agent_scores:
                agent_scores[agent_id] = {
                    'directional_hits': 0,
                    'directional_total': 0,
                    'high_strength_outcomes': [],
                    'low_strength_outcomes': [],
                    'confidence_calibration': []
                }
            
            score = agent_scores[agent_id]
            r = float(row['r_multiple'] or 0)
            strength = float(row['strength'] or 0)
            confidence = float(row['confidence'] or 0)
            
            # Directional accuracy
            score['directional_total'] += 1
            if (row['direction'] == 'LONG' and r > 0) or (row['direction'] == 'SHORT' and r > 0):
                score['directional_hits'] += 1
            
            # Strength calibration
            if strength >= 0.7:
                score['high_strength_outcomes'].append(r)
            else:
                score['low_strength_outcomes'].append(r)
            
            # Confidence calibration
            score['confidence_calibration'].append({
                'confidence': confidence,
                'outcome': r
            })
        
        results = {}
        for agent_id, score in agent_scores.items():
            high_avg = sum(score['high_strength_outcomes']) / len(score['high_strength_outcomes']) if score['high_strength_outcomes'] else 0
            low_avg = sum(score['low_strength_outcomes']) / len(score['low_strength_outcomes']) if score['low_strength_outcomes'] else 0
            
            results[agent_id] = {
                'directional_accuracy': score['directional_hits'] / score['directional_total'] if score['directional_total'] > 0 else 0,
                'high_strength_avg_r': round(high_avg, 4),
                'low_strength_avg_r': round(low_avg, 4),
                'strength_differentiation': round(high_avg - low_avg, 4),  # Positive = strength adds value
                'total_contributed': score['directional_total'],
                'quality_score': round(
                    (score['directional_hits'] / score['directional_total'] * 0.4 +
                     max(0, high_avg) * 0.3 +
                     max(0, (high_avg - low_avg)) * 0.3) * 100, 2
                ) if score['directional_total'] > 0 else 0
            }
        
        return results
```

### 6.2 Agent Conflict Detection

```python
class AgentConflictDetector:
    """
    Detects when agents disagree — useful for identifying
    uncertainty periods and potential signal degradation.
    """
    
    async def detect_conflicts(self, pair: str) -> dict:
        """Check for conflicts among active signals for a pair."""
        
        # Get recent signals for this pair
        signals = await self.redis.zrevrangebyscore(
            f'monitoring:signals:{pair}',
            max='+inf',
            min=f'-inf',
            start=0,
            num=20,
            withscores=True
        )
        
        bullish_agents = []
        bearish_agents = []
        neutral_agents = []
        
        for signal_json, timestamp in signals:
            signal = json.loads(signal_json)
            agent = signal['agent_id']
            direction = signal.get('direction', 'NEUTRAL')
            
            if direction == 'BULLISH':
                bullish_agents.append(agent)
            elif direction == 'BEARISH':
                bearish_agents.append(agent)
            else:
                neutral_agents.append(agent)
        
        total_active = len(bullish_agents) + len(bearish_agents)
        
        if total_active == 0:
            return {'conflict': False, 'consensus': 'NO_SIGNALS'}
        
        bullish_pct = len(bullish_agents) / total_active
        bearish_pct = len(bearish_agents) / total_active
        
        # Conflict detection
        conflict = abs(bullish_pct - bearish_pct) < 0.3  # Nearly split
        
        # Consensus detection
        if bullish_pct >= 0.7:
            consensus = 'STRONG_BULLISH'
        elif bearish_pct >= 0.7:
            consensus = 'STRONG_BEARISH'
        elif bullish_pct >= 0.6:
            consensus = 'MODERATE_BULLISH'
        elif bearish_pct >= 0.6:
            consensus = 'MODERATE_BEARISH'
        else:
            consensus = 'CONFLICTED'
        
        result = {
            'pair': pair,
            'conflict': conflict,
            'consensus': consensus,
            'bullish_agents': bullish_agents,
            'bearish_agents': bearish_agents,
            'neutral_agents': neutral_agents,
            'bullish_pct': round(bullish_pct, 2),
            'bearish_pct': round(bearish_pct, 2),
            'confidence_penalty': 0.3 if conflict else 0  # Reduce confidence when conflicted
        }
        
        if conflict:
            await self.event_bus.publish('agent.conflict', MonitoringEvent(
                event_type=MonitoringEventType.AGENT_CONFLICT,
                severity='INFO',
                pair=pair,
                data=result
            ))
        
        return result
```

---

## 7. Anomaly Detection

### 7.1 Multi-Layer Anomaly Detection

```python
class AnomalyDetector:
    """
    Detects unusual trading patterns, execution anomalies, and data issues.
    Three layers: execution, pattern, and systemic.
    """
    
    def __init__(self, db, redis, event_bus):
        self.db = db
        self.redis = redis
        self.event_bus = event_bus
        
        # Statistical baselines (updated daily)
        self.baselines = {
            'avg_slippage_pips': 0.3,
            'avg_spread_pips': 1.2,
            'avg_execution_latency_ms': 150,
            'avg_trade_duration_hours': 8,
            'avg_daily_trades': 3,
            'avg_daily_volume_lots': 0.15,
            'typical_win_rate': 0.65,
            'typical_r_distribution': {}  # R-multiple histogram
        }
    
    async def check_execution_anomaly(self, trade_id: str, fill_data: dict) -> list[dict]:
        """Check for execution anomalies on trade fill."""
        anomalies = []
        
        # 1. Excessive slippage
        slippage = abs(fill_data.get('slippage_pips', 0))
        if slippage > self.baselines['avg_slippage_pips'] * 3:
            anomalies.append({
                'type': 'excessive_slippage',
                'severity': 'WARNING',
                'description': f"Slippage {slippage:.1f} pips is {slippage/self.baselines['avg_slippage_pips']:.1f}x average",
                'threshold': self.baselines['avg_slippage_pips'] * 3,
                'actual': slippage
            })
        
        # 2. Spread blowout
        spread = fill_data.get('spread', 0)
        if spread > self.baselines['avg_spread_pips'] * 3:
            anomalies.append({
                'type': 'spread_blowout',
                'severity': 'WARNING',
                'description': f"Spread {spread:.1f} pips is {spread/self.baselines['avg_spread_pips']:.1f}x average",
                'threshold': self.baselines['avg_spread_pips'] * 3,
                'actual': spread
            })
        
        # 3. Execution latency spike
        latency = fill_data.get('latency_ms', 0)
        if latency > self.baselines['avg_execution_latency_ms'] * 10:
            anomalies.append({
                'type': 'latency_spike',
                'severity': 'WARNING',
                'description': f"Execution latency {latency:.0f}ms is {latency/self.baselines['avg_execution_latency_ms']:.0f}x average",
                'threshold': self.baselines['avg_execution_latency_ms'] * 10,
                'actual': latency
            })
        
        # 4. Off-quote fill (price moved significantly between order and fill)
        if fill_data.get('off_quote', False):
            anomalies.append({
                'type': 'off_quote',
                'severity': 'CRITICAL',
                'description': 'Broker reported off-quote — fill price differs significantly from request',
                'action': 'Review broker execution quality'
            })
        
        for anomaly in anomalies:
            await self._emit_anomaly('execution', anomaly, trade_id)
        
        return anomalies
    
    async def check_pattern_anomaly(self, period_days: int = 7) -> list[dict]:
        """Detect unusual trading patterns."""
        anomalies = []
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        # 1. Trade frequency anomaly
        recent_trades = await self.db.fetch("""
            SELECT COUNT(*) as count, 
                   SUM(lot_size) as volume,
                   AVG(r_multiple) as avg_r
            FROM trades
            WHERE entry_time > $1
        """, cutoff)
        
        if recent_trades[0]['count']:
            daily_rate = recent_trades[0]['count'] / period_days
            if daily_rate > self.baselines['avg_daily_trades'] * 2:
                anomalies.append({
                    'type': 'overtrading',
                    'severity': 'WARNING',
                    'description': f"Trading {daily_rate:.1f} trades/day vs normal {self.baselines['avg_daily_trades']:.1f}",
                    'recommendation': 'Review if setups are A-grade quality or revenge trading'
                })
        
        # 2. Win rate deviation
        if recent_trades[0]['avg_r'] is not None:
            wins = await self.db.fetch("""
                SELECT COUNT(*) as count FROM trades
                WHERE entry_time > $1 AND r_multiple > 0
            """, cutoff)
            
            total = recent_trades[0]['count']
            if total >= 10:
                win_rate = wins[0]['count'] / total
                deviation = abs(win_rate - self.baselines['typical_win_rate'])
                
                if deviation > 0.15:
                    direction = 'above' if win_rate > self.baselines['typical_win_rate'] else 'below'
                    anomalies.append({
                        'type': 'win_rate_deviation',
                        'severity': 'WARNING' if direction == 'below' else 'INFO',
                        'description': f"Win rate {win_rate:.0%} is {deviation:.0%} {direction} normal {self.baselines['typical_win_rate']:.0%}",
                        'recommendation': 'Edge may be changing. Review recent setups.' if direction == 'below' 
                                        else 'Good run — maintain discipline, do not oversize'
                    })
        
        # 3. Single-pair concentration
        pair_counts = await self.db.fetch("""
            SELECT pair, COUNT(*) as count FROM trades
            WHERE entry_time > $1
            GROUP BY pair
        """, cutoff)
        
        total = sum(r['count'] for r in pair_counts)
        for r in pair_counts:
            concentration = r['count'] / total if total > 0 else 0
            if concentration > 0.6:
                anomalies.append({
                    'type': 'pair_concentration',
                    'severity': 'WARNING',
                    'description': f"{r['pair']} accounts for {concentration:.0%} of trades — low diversification",
                    'recommendation': 'Diversify across pairs to reduce concentration risk'
                })
        
        # 4. Session concentration
        session_counts = await self.db.fetch("""
            SELECT entry_session, COUNT(*) as count FROM trades
            WHERE entry_time > $1
            GROUP BY entry_session
        """, cutoff)
        
        for r in session_counts:
            concentration = r['count'] / total if total > 0 else 0
            if concentration > 0.7:
                anomalies.append({
                    'type': 'session_concentration',
                    'severity': 'INFO',
                    'description': f"{r['entry_session']} session accounts for {concentration:.0%} of trades",
                    'recommendation': 'Consider if other sessions offer opportunities'
                })
        
        # 5. Time-between-trades analysis (revenge trading detection)
        trade_times = await self.db.fetch("""
            SELECT entry_time FROM trades
            WHERE entry_time > $1
            ORDER BY entry_time ASC
        """, cutoff)
        
        for i in range(1, len(trade_times)):
            gap = (trade_times[i]['entry_time'] - trade_times[i-1]['entry_time']).total_seconds() / 60
            if gap < 5:  # Less than 5 minutes between trades
                anomalies.append({
                    'type': 'rapid_fire_trading',
                    'severity': 'WARNING',
                    'description': f"Trade entered {gap:.0f} minutes after previous — possible revenge trading",
                    'recommendation': 'Minimum 15-minute cooldown between trades recommended'
                })
        
        for anomaly in anomalies:
            await self._emit_anomaly('pattern', anomaly)
        
        return anomalies
    
    async def check_data_anomaly(self) -> list[dict]:
        """Detect data feed and system anomalies."""
        anomalies = []
        
        # 1. Price feed staleness
        last_prices = await self.redis.hgetall('monitoring:price:last_update')
        now = datetime.utcnow()
        
        for pair, last_update_str in last_prices.items():
            last_update = datetime.fromisoformat(last_update_str)
            staleness = (now - last_update).total_seconds()
            
            if staleness > 30:  # No price update for 30 seconds
                anomalies.append({
                    'type': 'price_feed_stale',
                    'severity': 'CRITICAL' if staleness > 60 else 'WARNING',
                    'description': f"{pair}: No price update for {staleness:.0f}s",
                    'pair': pair,
                    'last_update': last_update_str,
                    'action': 'Check broker connection' if staleness > 60 else 'Monitor'
                })
        
        # 2. Position count mismatch
        internal_count = await self.redis.hget('monitoring:realtime', 'open_positions')
        broker_count = await self._get_broker_position_count()
        
        if internal_count and broker_count and int(internal_count) != broker_count:
            anomalies.append({
                'type': 'position_count_mismatch',
                'severity': 'CRITICAL',
                'description': f"Internal: {internal_count} positions vs Broker: {broker_count} positions",
                'action': 'Run immediate reconciliation',
                'internal': int(internal_count),
                'broker': broker_count
            })
        
        # 3. Equity divergence
        internal_equity = await self.redis.hget('monitoring:realtime', 'equity')
        broker_equity = await self._get_broker_equity()
        
        if internal_equity and broker_equity:
            diff_pct = abs(float(internal_equity) - broker_equity) / broker_equity * 100
            if diff_pct > 1.0:  # > 1% divergence
                anomalies.append({
                    'type': 'equity_divergence',
                    'severity': 'CRITICAL',
                    'description': f"Equity divergence: Internal ${internal_equity} vs Broker ${broker_equity:.2f} ({diff_pct:.2f}%)",
                    'action': 'Investigate P&L calculation or missing trades'
                })
        
        for anomaly in anomalies:
            await self._emit_anomaly('data', anomaly)
        
        return anomalies
    
    async def _emit_anomaly(self, category: str, anomaly: dict, trade_id: str = None):
        """Store and publish anomaly."""
        await self.db.execute("""
            INSERT INTO anomalies (timestamp, anomaly_type, severity, description, context, trade_id)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, datetime.utcnow(), f"{category}:{anomaly['type']}", anomaly['severity'],
             anomaly['description'], json.dumps(anomaly), trade_id)
        
        await self.event_bus.publish('anomaly.detected', MonitoringEvent(
            event_type=MonitoringEventType.ANOMALY_DETECTED,
            severity=anomaly['severity'],
            trade_id=trade_id,
            data=anomaly
        ))
    
    async def update_baselines(self):
        """Recalculate statistical baselines from recent data."""
        cutoff = datetime.utcnow() - timedelta(days=30)
        
        stats = await self.db.fetch("""
            SELECT 
                AVG(entry_slippage) as avg_slippage,
                AVG(entry_spread) as avg_spread,
                AVG(EXTRACT(EPOCH FROM (exit_time - entry_time))/3600) as avg_duration,
                COUNT(*) / 30.0 as avg_daily_trades,
                AVG(lot_size) * 30 as avg_daily_volume,
                COUNT(*) FILTER (WHERE r_multiple > 0)::float / NULLIF(COUNT(*), 0) as win_rate
            FROM trades
            WHERE entry_time > $1 AND status = 'closed'
        """, cutoff)
        
        if stats[0]:
            s = stats[0]
            self.baselines.update({
                'avg_slippage_pips': float(s['avg_slippage'] or 0.3),
                'avg_spread_pips': float(s['avg_spread'] or 1.2),
                'avg_trade_duration_hours': float(s['avg_duration'] or 8),
                'avg_daily_trades': float(s['avg_daily_trades'] or 3),
                'avg_daily_volume_lots': float(s['avg_daily_volume'] or 0.15),
                'typical_win_rate': float(s['win_rate'] or 0.65)
            })
```

---

## 8. Trade Reconciliation

### 8.1 Broker vs Internal Reconciliation

```python
class TradeReconciliationEngine:
    """
    Continuously reconciles internal trade records with broker records.
    Detects phantom trades, missed fills, and position drift.
    """
    
    def __init__(self, db, redis, broker_client, event_bus):
        self.db = db
        self.redis = redis
        self.broker = broker_client
        self.event_bus = event_bus
        self.last_recon_time = None
        self.recon_interval = timedelta(minutes=5)  # Reconcile every 5 minutes
    
    async def reconcile(self) -> dict:
        """Run full reconciliation between internal and broker records."""
        
        # 1. Get internal state
        internal_positions = await self._get_internal_positions()
        internal_orders = await self._get_internal_orders()
        
        # 2. Get broker state
        broker_positions = await self.broker.get_positions()
        broker_orders = await self.broker.get_orders()
        broker_history = await self.broker.get_trade_history(hours=24)
        
        # 3. Compare positions
        position_match = self._compare_positions(internal_positions, broker_positions)
        
        # 4. Compare orders
        order_match = self._compare_orders(internal_orders, broker_orders)
        
        # 5. Check for missed fills
        missed_fills = self._detect_missed_fills(internal_orders, broker_history)
        
        # 6. Check for phantom trades (in internal but not in broker)
        phantoms = self._detect_phantoms(internal_positions, broker_positions)
        
        # 7. Calculate equity drift
        equity_drift = await self._check_equity_drift()
        
        # Compile result
        result = {
            'timestamp': datetime.utcnow().isoformat(),
            'position_match': position_match,
            'order_match': order_match,
            'missed_fills': missed_fills,
            'phantoms': phantoms,
            'equity_drift': equity_drift,
            'status': 'matched' if all([
                position_match['status'] == 'matched',
                order_match['status'] == 'matched',
                not missed_fills,
                not phantoms,
                equity_drift['status'] == 'matched'
            ]) else 'mismatched'
        }
        
        # Store reconciliation record
        await self.db.execute("""
            INSERT INTO reconciliation_log 
            (timestamp, broker, internal_count, broker_count, matched, mismatched, status, details)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, datetime.utcnow(), 'primary',
             len(internal_positions), len(broker_positions),
             position_match['matched'], position_match['mismatched'],
             result['status'], json.dumps(result))
        
        # Alert on mismatch
        if result['status'] == 'mismatched':
            await self.event_bus.publish('reconciliation.mismatch', MonitoringEvent(
                event_type=MonitoringEventType.RECONCILIATION_MISMATCH,
                severity='CRITICAL',
                data=result
            ))
        else:
            await self.event_bus.publish('reconciliation.match', MonitoringEvent(
                event_type=MonitoringEventType.RECONCILIATION_MATCH,
                severity='INFO',
                data={'timestamp': result['timestamp']}
            ))
        
        self.last_recon_time = datetime.utcnow()
        return result
    
    def _compare_positions(self, internal: list, broker: list) -> dict:
        """Compare internal and broker position lists."""
        internal_map = {p['pair'] + p['direction']: p for p in internal}
        broker_map = {p['symbol'] + p['type']: p for p in broker}
        
        matched = 0
        mismatched = 0
        details = []
        
        # Check each internal position exists in broker
        for key, int_pos in internal_map.items():
            if key in broker_map:
                brk_pos = broker_map[key]
                # Compare lot sizes
                lot_diff = abs(float(int_pos['lot_size']) - float(brk_pos['volume']))
                if lot_diff > 0.001:  # Allow for floating point
                    mismatched += 1
                    details.append({
                        'type': 'lot_size_mismatch',
                        'pair': int_pos['pair'],
                        'internal': str(int_pos['lot_size']),
                        'broker': str(brk_pos['volume'])
                    })
                else:
                    matched += 1
            else:
                mismatched += 1
                details.append({
                    'type': 'phantom_position',
                    'pair': int_pos['pair'],
                    'direction': int_pos['direction'],
                    'lot_size': str(int_pos['lot_size'])
                })
        
        # Check for broker positions not in internal
        for key, brk_pos in broker_map.items():
            if key not in internal_map:
                mismatched += 1
                details.append({
                    'type': 'untracked_position',
                    'pair': brk_pos['symbol'],
                    'direction': brk_pos['type'],
                    'lot_size': str(brk_pos['volume'])
                })
        
        return {
            'matched': matched,
            'mismatched': mismatched,
            'details': details,
            'status': 'matched' if mismatched == 0 else 'mismatched'
        }
    
    def _detect_missed_fills(self, internal_orders: list, broker_history: list) -> list[dict]:
        """Detect fills that happened at broker but weren't captured internally."""
        internal_ids = {o.get('external_id') for o in internal_orders if o.get('external_id')}
        
        missed = []
        for fill in broker_history:
            if fill.get('ticket') not in internal_ids:
                missed.append({
                    'broker_ticket': fill.get('ticket'),
                    'pair': fill.get('symbol'),
                    'direction': fill.get('type'),
                    'lot_size': fill.get('volume'),
                    'price': fill.get('price'),
                    'time': fill.get('time').isoformat() if fill.get('time') else None
                })
        
        return missed
    
    def _detect_phantoms(self, internal: list, broker: list) -> list[dict]:
        """Detect positions in internal records that don't exist at broker."""
        broker_keys = {p['symbol'] + p['type'] for p in broker}
        
        phantoms = []
        for pos in internal:
            key = pos['pair'] + pos['direction']
            if key not in broker_keys:
                phantoms.append({
                    'pair': pos['pair'],
                    'direction': pos['direction'],
                    'lot_size': str(pos['lot_size']),
                    'trade_id': pos.get('trade_id'),
                    'action': 'Close phantom position or update broker state'
                })
        
        return phantoms
    
    async def _check_equity_drift(self) -> dict:
        """Check if internal equity calculation matches broker."""
        internal_equity = Decimal(await self.redis.hget('monitoring:realtime', 'equity') or '0')
        broker_equity = Decimal(str(await self.broker.get_equity()))
        
        if broker_equity > 0:
            drift_pct = abs(internal_equity - broker_equity) / broker_equity * 100
        else:
            drift_pct = Decimal('0')
        
        return {
            'internal_equity': str(internal_equity),
            'broker_equity': str(broker_equity),
            'drift_pct': str(round(drift_pct, 4)),
            'status': 'matched' if drift_pct < 0.5 else 'drift' if drift_pct < 2.0 else 'mismatched'
        }
    
    async def auto_reconcile_loop(self):
        """Background loop for automatic reconciliation."""
        while True:
            try:
                result = await self.reconcile()
                
                if result['status'] == 'mismatched':
                    logger.warning(f"Reconciliation mismatch: {result}")
                    # Auto-resolve minor issues
                    await self._auto_resolve(result)
                
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")
                await self.event_bus.publish('anomaly.detected', MonitoringEvent(
                    event_type=MonitoringEventType.ANOMALY_DETECTED,
                    severity='CRITICAL',
                    data={'type': 'reconciliation_failure', 'error': str(e)}
                ))
            
            await asyncio.sleep(self.recon_interval.total_seconds())
    
    async def _auto_resolve(self, result: dict):
        """Attempt to auto-resolve minor reconciliation issues."""
        for phantom in result.get('phantoms', []):
            # If phantom is a small position, flag for closure
            if float(phantom['lot_size']) < 0.01:
                logger.warning(f"Auto-flagging phantom position for closure: {phantom}")
                await self.event_bus.publish('reconciliation.drift', MonitoringEvent(
                    event_type=MonitoringEventType.RECONCILIATION_DRIFT,
                    severity='WARNING',
                    data={'action': 'auto_close_phantom', 'details': phantom}
                ))
        
        for missed in result.get('missed_fills', []):
            # Attempt to reconstruct missed fill from broker data
            logger.warning(f"Attempting to reconstruct missed fill: {missed}")
            await self.event_bus.publish('reconciliation.drift', MonitoringEvent(
                event_type=MonitoringEventType.RECONCILIATION_DRIFT,
                severity='WARNING',
                data={'action': 'reconstruct_fill', 'details': missed}
            ))
```

---

## 9. Historical Trade Analytics

### 9.1 Advanced Analytics Engine

```python
class HistoricalAnalyticsEngine:
    """
    Deep historical analysis for strategy optimization.
    Runs periodic batch analyses and on-demand queries.
    """
    
    def __init__(self, db, event_bus):
        self.db = db
        self.event_bus = event_bus
    
    async def run_weekly_analysis(self) -> dict:
        """Comprehensive weekly analysis — runs every Sunday."""
        
        analysis = {
            'period': f"Week ending {datetime.utcnow().strftime('%Y-%m-%d')}",
            'generated_at': datetime.utcnow().isoformat()
        }
        
        # 1. Edge analysis — is the strategy still profitable?
        analysis['edge_analysis'] = await self._analyze_edge()
        
        # 2. Setup quality analysis — which setups are working?
        analysis['setup_analysis'] = await self._analyze_setups()
        
        # 3. Timing analysis — when are we most profitable?
        analysis['timing_analysis'] = await self._analyze_timing()
        
        # 4. Agent analysis — which agents are adding value?
        analysis['agent_analysis'] = await self._analyze_agents()
        
        # 5. Risk analysis — are risk limits appropriate?
        analysis['risk_analysis'] = await self._analyze_risk()
        
        # 6. Behavioral analysis — are we following the plan?
        analysis['behavioral_analysis'] = await self._analyze_behavior()
        
        # 7. Optimization suggestions
        analysis['suggestions'] = await self._generate_suggestions(analysis)
        
        return analysis
    
    async def _analyze_edge(self) -> dict:
        """Is the trading edge still present?"""
        
        # Rolling 100-trade expectancy
        recent_100 = await self.db.fetch("""
            SELECT r_multiple FROM trades
            WHERE status = 'closed'
            ORDER BY closed_at DESC
            LIMIT 100
        """)
        
        if len(recent_100) < 30:
            return {'status': 'insufficient_data', 'trades': len(recent_100)}
        
        r_values = [float(r['r_multiple']) for r in recent_100]
        
        # T-test: is expectancy significantly > 0?
        n = len(r_values)
        mean_r = sum(r_values) / n
        std_r = (sum((r - mean_r) ** 2 for r in r_values) / (n - 1)) ** 0.5
        t_stat = mean_r / (std_r / n ** 0.5) if std_r > 0 else 0
        
        # Approximate p-value (one-tailed, t-distribution)
        # Using normal approximation for large n
        p_value = 0.5 * (1 - math.erf(t_stat / 2**0.5)) if t_stat > 0 else 0.5
        
        edge_present = t_stat > 1.645  # 95% confidence one-tailed
        
        return {
            'edge_present': edge_present,
            'expectancy_r': round(mean_r, 4),
            'std_dev': round(std_r, 4),
            't_statistic': round(t_stat, 4),
            'p_value': round(p_value, 4),
            'confidence': 'HIGH' if t_stat > 2.326 else 'MODERATE' if t_stat > 1.645 else 'LOW',
            'sample_size': n,
            'recommendation': 'Continue trading' if edge_present else 'EDGE MAY BE GONE — review strategy'
        }
    
    async def _analyze_setups(self) -> dict:
        """Which setups are working and which aren't?"""
        
        # By setup grade
        grades = await self.db.fetch("""
            SELECT setup_grade,
                   COUNT(*) as trades,
                   COUNT(*) FILTER (WHERE r_multiple > 0) as wins,
                   AVG(r_multiple) as avg_r,
                   SUM(r_multiple) as total_r,
                   STDDEV(r_multiple) as std_r
            FROM trades
            WHERE status = 'closed' AND closed_at > NOW() - INTERVAL '90 days'
            GROUP BY setup_grade
            ORDER BY total_r DESC
        """)
        
        grade_analysis = {}
        for g in grades:
            grade = g['setup_grade']
            n = g['trades']
            win_rate = g['wins'] / n if n > 0 else 0
            avg_r = float(g['avg_r'] or 0)
            std_r = float(g['std_r'] or 1)
            sharpe = avg_r / std_r if std_r > 0 else 0
            
            grade_analysis[grade] = {
                'trades': n,
                'win_rate': round(win_rate, 4),
                'avg_r': round(avg_r, 4),
                'total_r': round(float(g['total_r'] or 0), 4),
                'sharpe': round(sharpe, 4),
                'recommendation': (
                    'KEEP — profitable' if avg_r > 0.2 else
                    'REVIEW — marginal' if avg_r > 0 else
                    'STOP — negative expectancy'
                )
            }
        
        # By trade type
        types = await self.db.fetch("""
            SELECT trade_type,
                   COUNT(*) as trades,
                   AVG(r_multiple) as avg_r,
                   SUM(r_multiple) as total_r
            FROM trades
            WHERE status = 'closed' AND closed_at > NOW() - INTERVAL '90 days'
            GROUP BY trade_type
            ORDER BY total_r DESC
        """)
        
        type_analysis = {
            t['trade_type']: {
                'trades': t['trades'],
                'avg_r': round(float(t['avg_r'] or 0), 4),
                'total_r': round(float(t['total_r'] or 0), 4)
            }
            for t in types
        }
        
        return {'by_grade': grade_analysis, 'by_type': type_analysis}
    
    async def _analyze_timing(self) -> dict:
        """When are we most profitable?"""
        
        # By hour of day
        hourly = await self.db.fetch("""
            SELECT EXTRACT(HOUR FROM entry_time) as hour,
                   COUNT(*) as trades,
                   AVG(r_multiple) as avg_r,
                   COUNT(*) FILTER (WHERE r_multiple > 0)::float / NULLIF(COUNT(*), 0) as win_rate
            FROM trades
            WHERE status = 'closed' AND closed_at > NOW() - INTERVAL '90 days'
            GROUP BY hour
            ORDER BY hour
        """)
        
        # By day of week
        daily = await self.db.fetch("""
            SELECT EXTRACT(DOW FROM entry_time) as dow,
                   COUNT(*) as trades,
                   AVG(r_multiple) as avg_r,
                   COUNT(*) FILTER (WHERE r_multiple > 0)::float / NULLIF(COUNT(*), 0) as win_rate
            FROM trades
            WHERE status = 'closed' AND closed_at > NOW() - INTERVAL '90 days'
            GROUP BY dow
            ORDER BY dow
        """)
        
        # By holding duration
        duration = await self.db.fetch("""
            SELECT 
                CASE 
                    WHEN EXTRACT(EPOCH FROM (exit_time - entry_time))/3600 < 1 THEN '< 1h'
                    WHEN EXTRACT(EPOCH FROM (exit_time - entry_time))/3600 < 4 THEN '1-4h'
                    WHEN EXTRACT(EPOCH FROM (exit_time - entry_time))/3600 < 24 THEN '4-24h'
                    WHEN EXTRACT(EPOCH FROM (exit_time - entry_time))/3600 < 120 THEN '1-5d'
                    ELSE '> 5d'
                END as duration_bucket,
                COUNT(*) as trades,
                AVG(r_multiple) as avg_r,
                COUNT(*) FILTER (WHERE r_multiple > 0)::float / NULLIF(COUNT(*), 0) as win_rate
            FROM trades
            WHERE status = 'closed' AND closed_at > NOW() - INTERVAL '90 days'
            GROUP BY duration_bucket
            ORDER BY MIN(EXTRACT(EPOCH FROM (exit_time - entry_time))/3600)
        """)
        
        return {
            'by_hour': {int(r['hour']): {'trades': r['trades'], 'avg_r': round(float(r['avg_r'] or 0), 4), 'win_rate': round(float(r['win_rate'] or 0), 4)} for r in hourly},
            'by_day': {int(r['dow']): {'trades': r['trades'], 'avg_r': round(float(r['avg_r'] or 0), 4), 'win_rate': round(float(r['win_rate'] or 0), 4)} for r in daily},
            'by_duration': {r['duration_bucket']: {'trades': r['trades'], 'avg_r': round(float(r['avg_r'] or 0), 4), 'win_rate': round(float(r['win_rate'] or 0), 4)} for r in duration}
        }
    
    async def _analyze_agents(self) -> dict:
        """Which agents are adding the most value?"""
        # Delegated to AgentContributionTracker
        from agent_tracker import AgentContributionTracker
        tracker = AgentContributionTracker(self.db, None, self.event_bus)
        return await tracker.get_signal_quality_scores(period_days=90)
    
    async def _analyze_risk(self) -> dict:
        """Are risk limits appropriate for current performance?"""
        
        # Actual risk distribution
        risk_stats = await self.db.fetch("""
            SELECT 
                AVG(risk_pct) as avg_risk,
                MAX(risk_pct) as max_risk,
                STDDEV(risk_pct) as std_risk,
                AVG(r_multiple) as avg_r,
                COUNT(*) FILTER (WHERE r_multiple < -1.5) as deep_losses,
                COUNT(*) as total
            FROM trades
            WHERE status = 'closed' AND closed_at > NOW() - INTERVAL '90 days'
        """)
        
        s = risk_stats[0]
        deep_loss_rate = (s['deep_losses'] / s['total']) if s['total'] > 0 else 0
        
        # Check if Kelly fraction is appropriate
        kelly_analysis = await self._check_kelly_calibration()
        
        return {
            'avg_risk_pct': round(float(s['avg_risk'] or 0), 4),
            'max_risk_pct': round(float(s['max_risk'] or 0), 4),
            'deep_loss_rate': round(deep_loss_rate, 4),
            'kelly_calibration': kelly_analysis,
            'recommendation': (
                'Risk parameters appropriate' if deep_loss_rate < 0.05 else
                'Consider reducing position sizes — deep loss rate elevated'
            )
        }
    
    async def _analyze_behavior(self) -> dict:
        """Are we following the trading plan?"""
        
        # Rule adherence
        adherence = await self.db.fetch("""
            SELECT AVG(rule_adherence) as avg_adherence,
                   COUNT(*) FILTER (WHERE rule_adherence < 5) as low_adherence_count,
                   COUNT(*) as total
            FROM trades
            WHERE status = 'closed' AND rule_adherence IS NOT NULL
            AND closed_at > NOW() - INTERVAL '90 days'
        """)
        
        # Plan deviations
        deviations = await self.db.fetch("""
            SELECT COUNT(*) as count
            FROM trades
            WHERE status = 'closed' AND post_grade IN ('D', 'F')
            AND closed_at > NOW() - INTERVAL '90 days'
        """)
        
        a = adherence[0]
        return {
            'avg_rule_adherence': round(float(a['avg_adherence'] or 0), 2),
            'low_adherence_count': a['low_adherence_count'],
            'graded_trades': a['total'],
            'poor_execution_count': deviations[0]['count'],
            'recommendation': (
                'Good discipline — maintain' if (a['avg_adherence'] or 0) >= 7 else
                'Discipline slipping — review trading rules before next session'
            )
        }
    
    async def _generate_suggestions(self, analysis: dict) -> list[str]:
        """Generate actionable suggestions from analysis."""
        suggestions = []
        
        # Edge analysis
        edge = analysis.get('edge_analysis', {})
        if not edge.get('edge_present'):
            suggestions.append("🔴 CRITICAL: Statistical edge may be gone. Consider pausing live trading and reviewing strategy.")
        
        # Setup analysis
        for grade, data in analysis.get('setup_analysis', {}).get('by_grade', {}).items():
            if data['avg_r'] < 0 and data['trades'] >= 10:
                suggestions.append(f"⚠️ {grade}-grade setups have negative expectancy ({data['avg_r']:.2f}R avg). Consider skipping or reducing size.")
        
        # Timing
        timing = analysis.get('timing_analysis', {})
        for hour, data in timing.get('by_hour', {}).items():
            if data['avg_r'] < -0.3 and data['trades'] >= 5:
                suggestions.append(f"⚠️ Hour {hour}:00 has negative expectancy ({data['avg_r']:.2f}R). Consider avoiding trades in this window.")
        
        # Behavioral
        behavior = analysis.get('behavioral_analysis', {})
        if (behavior.get('avg_rule_adherence') or 10) < 6:
            suggestions.append("⚠️ Rule adherence below 6/10. Review trading rules and consider mandatory checklists.")
        
        if not suggestions:
            suggestions.append("✅ All systems operating within normal parameters. No critical issues detected.")
        
        return suggestions
```

---

## 10. Notification Channels

### 10.1 Notification Architecture

```python
class NotificationManager:
    """
    Smart notification system with escalation and fatigue prevention.
    Integrates with Telegram, WhatsApp, and dashboard.
    """
    
    # Severity → channel mapping
    CHANNEL_MAP = {
        'INFO': ['dashboard'],
        'WARNING': ['telegram'],
        'CRITICAL': ['telegram', 'dashboard_popup'],
        'EMERGENCY': ['telegram_repeat', 'dashboard_popup', 'sms']  # SMS for black swan
    }
    
    # Rate limiting (prevent spam)
    RATE_LIMITS = {
        'INFO': {'max_per_hour': 20, 'cooldown_seconds': 60},
        'WARNING': {'max_per_hour': 10, 'cooldown_seconds': 120},
        'CRITICAL': {'max_per_hour': 5, 'cooldown_seconds': 300},
        'EMERGENCY': {'max_per_hour': 0, 'cooldown_seconds': 0}  # No limit — always send
    }
    
    def __init__(self, redis, telegram_bot, event_bus):
        self.redis = redis
        self.telegram = telegram_bot
        self.event_bus = event_bus
        self.message_templates = self._load_templates()
    
    async def send(self, event: MonitoringEvent):
        """Route notification to appropriate channels based on severity."""
        severity = event.severity
        
        # Check rate limit
        if not await self._check_rate_limit(severity, event.event_type.value):
            return
        
        # Format message
        message = self._format_message(event)
        
        # Route to channels
        channels = self.CHANNEL_MAP.get(severity, ['dashboard'])
        
        for channel in channels:
            if channel == 'telegram':
                await self._send_telegram(message, event)
            elif channel == 'telegram_repeat':
                await self._send_telegram_repeat(message, event)
            elif channel == 'dashboard':
                await self._send_dashboard(message, event)
            elif channel == 'dashboard_popup':
                await self._send_dashboard_popup(message, event)
            elif channel == 'sms':
                await self._send_sms(message, event)
        
        # Log notification
        await self.redis.lpush('monitoring:notifications:log', json.dumps({
            'timestamp': datetime.utcnow().isoformat(),
            'severity': severity,
            'event_type': event.event_type.value,
            'channels': channels,
            'message': message[:200]
        }))
    
    def _format_message(self, event: MonitoringEvent) -> str:
        """Format event into human-readable notification."""
        templates = {
            MonitoringEventType.POSITION_OPENED: "🟢 {pair} {direction} opened @ {price} | Grade: {grade} | Risk: {risk_pct}%",
            MonitoringEventType.POSITION_CLOSED: "{emoji} {pair} {direction} closed @ {price} | P&L: {pnl} ({r_multiple}R) | Duration: {duration}",
            MonitoringEventType.DRAWDOWN_ALERT: "⚠️ DRAWDOWN ALERT: {stage} stage | DD: {drawdown_pct}% | Action: {action}",
            MonitoringEventType.STREAK_DETECTED: "{emoji} {streak_type} streak: {count} trades | Total: {total_r}R | {recommendation}",
            MonitoringEventType.ANOMALY_DETECTED: "🚨 ANOMALY [{severity}]: {description}",
            MonitoringEventType.RECONCILIATION_MISMATCH: "🔴 RECONCILIATION MISMATCH: Internal {internal} vs Broker {broker}",
            MonitoringEventType.BLACK_SWAN_DETECTED: "🚨🚨 BLACK SWAN DETECTED 🚨🚨\nTriggers: {triggers}\nACTION: All positions closing at market\nTrading HALTED",
            MonitoringEventType.CIRCUIT_BREAKER_TRIPPED: "⚡ CIRCUIT BREAKER: {breaker_name} | Action: {action}",
            MonitoringEventType.NEWS_BLACKOUT_START: "📰 News blackout: {event_name} | Until: {until}",
            MonitoringEventType.AGENT_CONFLICT: "🤔 Agent conflict on {pair}: {consensus}",
            MonitoringEventType.PERFORMANCE_SNAPSHOT: "📊 Period: {period} | Trades: {trades} | WR: {win_rate}% | PF: {pf} | Sharpe: {sharpe}"
        }
        
        template = templates.get(event.event_type, str(event.data))
        
        # Fill template with event data
        try:
            return template.format(**event.data)
        except (KeyError, AttributeError):
            return f"[{event.severity}] {event.event_type.value}: {json.dumps(event.data)[:200]}"
    
    async def _send_telegram(self, message: str, event: MonitoringEvent):
        """Send to Telegram with appropriate formatting."""
        # Add emoji prefix based on severity
        prefix = {'INFO': 'ℹ️', 'WARNING': '⚠️', 'CRITICAL': '🔴', 'EMERGENCY': '🚨'}
        formatted = f"{prefix.get(event.severity, '')} **Alpha Stack**\n\n{message}"
        
        await self.telegram.send_message(
            chat_id=self.telegram.chat_id,
            text=formatted,
            parse_mode='Markdown'
        )
    
    async def _send_telegram_repeat(self, message: str, event: MonitoringEvent):
        """Send repeated Telegram alerts for emergencies."""
        await self._send_telegram(message, event)
        
        # Schedule repeat
        await self.redis.setex(
            f'monitoring:alert_repeat:{event.event_id}',
            300,  # Repeat every 5 minutes for 30 minutes
            json.dumps({
                'message': message,
                'event': event.event_type.value,
                'repeat_until': (datetime.utcnow() + timedelta(minutes=30)).isoformat()
            })
        )
    
    async def _check_rate_limit(self, severity: str, event_type: str) -> bool:
        """Check if notification should be sent based on rate limits."""
        limits = self.RATE_LIMITS.get(severity, {})
        max_per_hour = limits.get('max_per_hour', 10)
        cooldown = limits.get('cooldown_seconds', 60)
        
        # No limit for emergencies
        if max_per_hour == 0:
            return True
        
        # Check cooldown
        last_sent = await self.redis.get(f'monitoring:rate:{event_type}')
        if last_sent:
            elapsed = (datetime.utcnow() - datetime.fromisoformat(last_sent.decode())).total_seconds()
            if elapsed < cooldown:
                return False
        
        # Check hourly limit
        hour_key = f'monitoring:rate:{event_type}:{datetime.utcnow().strftime("%Y%m%d%H")}'
        count = await self.redis.incr(hour_key)
        if count == 1:
            await self.redis.expire(hour_key, 3600)
        
        if count > max_per_hour:
            return False
        
        # Update last sent time
        await self.redis.set(f'monitoring:rate:{event_type}', datetime.utcnow().isoformat())
        return True
    
    def _load_templates(self) -> dict:
        """Load message templates."""
        return {}
```

### 10.2 Notification Types and Routing

| Event | Severity | Telegram | Dashboard | SMS | Repeat |
|-------|----------|----------|-----------|-----|--------|
| Trade opened | INFO | ✅ | ✅ | - | - |
| Trade closed (profit) | INFO | ✅ | ✅ | - | - |
| Trade closed (loss) | INFO | ✅ | ✅ | - | - |
| Drawdown YELLOW | WARNING | ✅ | ✅ | - | - |
| Drawdown ORANGE/RED | CRITICAL | ✅ | ✅ popup | - | Every 15min |
| Drawdown BLACK | EMERGENCY | ✅ repeat | ✅ popup | ✅ | Every 5min |
| Circuit breaker | CRITICAL | ✅ | ✅ popup | - | Every 10min |
| Black swan | EMERGENCY | ✅ repeat | ✅ popup | ✅ | Every 5min |
| Reconciliation mismatch | CRITICAL | ✅ | ✅ popup | - | Once |
| Execution anomaly | WARNING | ✅ | ✅ | - | - |
| Agent conflict | INFO | - | ✅ | - | - |
| Win/loss streak | INFO/WARNING | ✅ | ✅ | - | - |
| Performance alert | WARNING | ✅ | ✅ | - | - |
| News blackout | INFO | ✅ | ✅ | - | - |
| Daily summary | INFO | ✅ | ✅ | - | - |

---

## 11. Export & Reporting

### 11.1 Export Engine

```python
class ExportEngine:
    """
    Generates exports in multiple formats for analysis, tax, and compliance.
    """
    
    def __init__(self, db):
        self.db = db
    
    async def export_trades_csv(self, start_date: datetime, end_date: datetime, 
                                 filters: dict = None) -> str:
        """Export trades to CSV for external analysis."""
        
        query = """
            SELECT 
                trade_id, external_id, pair, direction, timeframe, trade_type,
                entry_price, entry_time, entry_slippage, entry_spread, entry_session,
                lot_size, notional_value, stop_loss, stop_loss_pips,
                take_profits, exit_price, exit_time, exit_condition, exit_slippage,
                gross_pnl, net_pnl, commission, swap, r_multiple,
                confluence_score, setup_grade, regime, adx_at_entry, atr_at_entry,
                agent_signals, signal_summary, risk_amount, risk_pct,
                drawdown_stage, management_log, duration_minutes,
                mae_pips, mfe_pips, pre_confidence, emotion_during,
                rule_adherence, post_grade, tags
            FROM trades
            WHERE entry_time BETWEEN $1 AND $2
        """
        params = [start_date, end_date]
        
        # Apply filters
        if filters:
            if 'pair' in filters:
                query += f" AND pair = ${len(params) + 1}"
                params.append(filters['pair'])
            if 'session' in filters:
                query += f" AND entry_session = ${len(params) + 1}"
                params.append(filters['session'])
            if 'grade' in filters:
                query += f" AND setup_grade = ${len(params) + 1}"
                params.append(filters['grade'])
            if 'direction' in filters:
                query += f" AND direction = ${len(params) + 1}"
                params.append(filters['direction'])
        
        query += " ORDER BY entry_time ASC"
        
        rows = await self.db.fetch(query, *params)
        
        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys() if rows else [])
        writer.writeheader()
        for row in rows:
            # Serialize JSON fields
            row_data = dict(row)
            for key in ['take_profits', 'agent_signals', 'management_log', 'tags']:
                if row_data.get(key):
                    row_data[key] = json.dumps(row_data[key])
            writer.writerow(row_data)
        
        return output.getvalue()
    
    async def generate_tax_report(self, tax_year: int) -> dict:
        """Generate tax-ready report for a given year."""
        
        start = datetime(tax_year, 1, 1)
        end = datetime(tax_year, 12, 31, 23, 59, 59)
        
        # Get all closed trades for the year
        trades = await self.db.fetch("""
            SELECT 
                pair, direction, entry_price, entry_time, exit_price, exit_time,
                lot_size, gross_pnl, net_pnl, commission, swap, r_multiple,
                notional_value
            FROM trades
            WHERE status = 'closed' AND closed_at BETWEEN $1 AND $2
            ORDER BY closed_at ASC
        """, start, end)
        
        # Aggregate by pair
        by_pair = {}
        total_gross = Decimal('0')
        total_net = Decimal('0')
        total_commission = Decimal('0')
        total_swap = Decimal('0')
        
        for t in trades:
            pair = t['pair']
            if pair not in by_pair:
                by_pair[pair] = {
                    'trades': 0, 'wins': 0, 'losses': 0,
                    'gross_pnl': Decimal('0'), 'net_pnl': Decimal('0'),
                    'commission': Decimal('0'), 'swap': Decimal('0'),
                    'notional_volume': Decimal('0')
                }
            
            p = by_pair[pair]
            p['trades'] += 1
            pnl = Decimal(str(t['net_pnl'] or 0))
            if pnl > 0:
                p['wins'] += 1
            elif pnl < 0:
                p['losses'] += 1
            p['gross_pnl'] += Decimal(str(t['gross_pnl'] or 0))
            p['net_pnl'] += pnl
            p['commission'] += Decimal(str(t['commission'] or 0))
            p['swap'] += Decimal(str(t['swap'] or 0))
            p['notional_volume'] += Decimal(str(t['notional_value'] or 0))
            
            total_gross += Decimal(str(t['gross_pnl'] or 0))
            total_net += pnl
            total_commission += Decimal(str(t['commission'] or 0))
            total_swap += Decimal(str(t['swap'] or 0))
        
        # Monthly breakdown
        monthly = await self.db.fetch("""
            SELECT 
                DATE_TRUNC('month', closed_at) as month,
                COUNT(*) as trades,
                SUM(gross_pnl) as gross_pnl,
                SUM(net_pnl) as net_pnl,
                SUM(commission) as commission,
                SUM(swap) as swap,
                COUNT(*) FILTER (WHERE r_multiple > 0) as wins
            FROM trades
            WHERE status = 'closed' AND closed_at BETWEEN $1 AND $2
            GROUP BY month
            ORDER BY month
        """, start, end)
        
        return {
            'tax_year': tax_year,
            'generated_at': datetime.utcnow().isoformat(),
            'summary': {
                'total_trades': len(trades),
                'winning_trades': sum(1 for t in trades if Decimal(str(t['net_pnl'] or 0)) > 0),
                'losing_trades': sum(1 for t in trades if Decimal(str(t['net_pnl'] or 0)) < 0),
                'gross_profit_loss': str(total_gross),
                'total_commissions': str(total_commission),
                'total_swaps': str(total_swap),
                'net_profit_loss': str(total_net)
            },
            'by_pair': {
                pair: {
                    'trades': data['trades'],
                    'wins': data['wins'],
                    'losses': data['losses'],
                    'gross_pnl': str(data['gross_pnl']),
                    'net_pnl': str(data['net_pnl']),
                    'commission': str(data['commission']),
                    'swap': str(data['swap']),
                    'volume': str(data['notional_volume'])
                }
                for pair, data in by_pair.items()
            },
            'monthly': [
                {
                    'month': row['month'].strftime('%Y-%m'),
                    'trades': row['trades'],
                    'wins': row['wins'],
                    'gross_pnl': str(row['gross_pnl']),
                    'net_pnl': str(row['net_pnl']),
                    'commission': str(row['commission']),
                    'swap': str(row['swap'])
                }
                for row in monthly
            ]
        }
    
    async def generate_performance_report_pdf(self, period: str = 'monthly') -> bytes:
        """Generate a PDF performance report with charts."""
        # Uses reportlab or weasyprint to generate PDF
        
        # 1. Collect data
        if period == 'monthly':
            start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        elif period == 'quarterly':
            quarter = (datetime.utcnow().month - 1) // 3
            start = datetime(datetime.utcnow().year, quarter * 3 + 1, 1)
        else:
            start = datetime.utcnow() - timedelta(days=30)
        
        end = datetime.utcnow()
        
        trades = await self.db.fetch("""
            SELECT * FROM trades
            WHERE closed_at BETWEEN $1 AND $2 AND status = 'closed'
            ORDER BY closed_at
        """, start, end)
        
        # 2. Generate charts (matplotlib)
        equity_chart = await self._generate_equity_chart(trades)
        r_dist_chart = await self._generate_r_distribution_chart(trades)
        heatmap_chart = await self._generate_heatmap_chart(trades)
        
        # 3. Build PDF
        pdf_buffer = io.BytesIO()
        # ... (reportlab PDF generation code)
        
        return pdf_buffer.getvalue()
```

### 11.2 Scheduled Reports

| Report | Frequency | Content | Delivery |
|--------|-----------|---------|----------|
| **Daily Summary** | Every day at 22:00 UTC | Today's trades, P&L, open positions, alerts | Telegram |
| **Weekly Analytics** | Every Sunday 20:00 UTC | Full weekly analysis, agent performance, edge check | Telegram + PDF |
| **Monthly Report** | 1st of month | Complete monthly review, all breakdowns, suggestions | PDF email |
| **Quarterly Review** | Q1/Q2/Q3/Q4 start | Deep strategy review, parameter optimization | PDF + meeting |
| **Tax Report** | Jan 31 (for prev year) | Full year P&L, by pair, by month, commissions | PDF + CSV |
| **Reconciliation** | Every 5 minutes | Position and equity match status | Dashboard (alert on mismatch) |

---

## 12. Technology Stack & Deployment

### 12.1 Technology Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    TECHNOLOGY STACK                               │
│                                                                   │
│  RUNTIME                                                         │
│  ├── Python 3.12+ (async/await throughout)                      │
│  ├── asyncio + uvloop (high-performance event loop)             │
│  └── FastAPI (dashboard API, webhook endpoints)                 │
│                                                                   │
│  DATA LAYER                                                      │
│  ├── TimescaleDB (time-series: equity, snapshots, signals)      │
│  ├── PostgreSQL 16 (metadata: trades, config, reconciliation)   │
│  ├── Redis 7 (real-time state, pub/sub, rate limiting)          │
│  └── MinIO/S3 (screenshots, PDF exports, backups)               │
│                                                                   │
│  MESSAGING                                                       │
│  ├── Redis Streams (monitoring event bus)                       │
│  └── asyncio.Queue (in-process event routing)                   │
│                                                                   │
│  DASHBOARD                                                       │
│  ├── Grafana (real-time dashboards, alerting)                   │
│  ├── Plotly Dash (custom interactive charts)                    │
│  └── FastAPI + WebSocket (live updates)                         │
│                                                                   │
│  NOTIFICATION                                                    │
│  ├── python-telegram-bot (Telegram alerts)                      │
│  ├── Twilio (SMS for emergencies)                               │
│  └── SMTP (email reports)                                       │
│                                                                   │
│  EXPORT                                                          │
│  ├── pandas + openpyxl (Excel/CSV)                              │
│  ├── reportlab (PDF generation)                                 │
│  └── matplotlib + plotly (charts)                               │
│                                                                   │
│  MONITORING                                                      │
│  ├── Prometheus (system metrics)                                │
│  ├── Grafana (visualization)                                    │
│  └── Sentry (error tracking)                                    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 12.2 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT                                     │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  MONITORING CONTAINER (Docker)                            │    │
│  │  ├── Position Tracker (async worker)                      │    │
│  │  ├── Performance Engine (async worker)                    │    │
│  │  ├── Anomaly Detector (async worker)                      │    │
│  │  ├── Reconciliation Engine (5-min loop)                   │    │
│  │  ├── Notification Manager (event listener)                │    │
│  │  ├── Analytics Engine (weekly batch + on-demand)          │    │
│  │  └── FastAPI Server (dashboard API + webhooks)            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  GRAFANA CONTAINER                                        │    │
│  │  ├── Real-time dashboards                                 │    │
│  │  ├── Alert rules                                          │    │
│  │  └── Datasource: TimescaleDB + Redis + Prometheus         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  DATABASE CONTAINER                                       │    │
│  │  ├── TimescaleDB (extension of PostgreSQL)                │    │
│  │  └── Redis                                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Shared with Trading Engine container via:                       │
│  ├── Redis Streams (event bus)                                  │
│  └── TimescaleDB (shared database)                              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 12.3 Performance Requirements

| Metric | Target | Method |
|--------|--------|--------|
| Position update latency | < 100ms (tick to dashboard) | Redis in-memory + WebSocket push |
| Dashboard refresh | < 1s | Grafana auto-refresh + Redis polling |
| Trade recording | < 50ms | Async DB write, non-blocking |
| Reconciliation cycle | < 30s (full) | Optimized queries, batch comparison |
| Alert delivery | < 5s (CRITICAL/EMERGENCY) | Direct Telegram API, no queue |
| Historical query | < 2s (90-day range) | TimescaleDB hypertables + indexes |
| Export generation | < 30s (monthly CSV) | Streaming query + async I/O |
| Storage per trade | ~2KB | Compressed JSONB, partitioned tables |
| Storage per year (1000 trades) | ~2MB trades + ~500MB snapshots | TimescaleDB compression after 30 days |

---

## Appendix A: Monitoring Event Flow

```
                        TRADING ENGINE
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MONITORING EVENT BUS (Redis Streams)           │
│                                                                   │
│  trade.opened ──→ Position Tracker ──→ Store ──→ Dashboard       │
│  trade.closed ──→ Position Tracker ──→ Performance Engine         │
│                    └──→ Notification Manager ──→ Telegram         │
│                                                                   │
│  signal.generated ──→ Lifecycle Monitor ──→ Agent Tracker         │
│                                                                   │
│  pnl.update ──→ Dashboard (real-time)                            │
│             └──→ Anomaly Detector (check thresholds)             │
│                                                                   │
│  risk.utilization ──→ Risk Dashboard                             │
│                    └──→ Notification (if breach)                  │
│                                                                   │
│  anomaly.detected ──→ Notification Manager ──→ Telegram          │
│                    └──→ Anomaly Log ──→ DB                       │
│                                                                   │
│  reconciliation.mismatch ──→ CRITICAL alert                      │
│  reconciliation.match ──→ INFO log                               │
│                                                                   │
│  (every 5 min) ──→ Reconciliation Engine                         │
│  (every Sunday) ──→ Analytics Engine ──→ Weekly Report           │
│  (daily 22:00) ──→ Daily Summary ──→ Telegram                   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Appendix B: Quick Reference — Key Metrics

```
╔══════════════════════════════════════════════════════════════════╗
║            ALPHA STACK — TRADE MONITORING QUICK REFERENCE        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  REAL-TIME (sub-second)                                          ║
║  ├── Open positions (count, P&L, R-multiple)                    ║
║  ├── Total unrealized P&L                                       ║
║  ├── Equity curve (current vs HWM)                              ║
║  ├── Drawdown % and stage (GREEN/YELLOW/ORANGE/RED/BLACK)       ║
║  ├── Total exposure %                                           ║
║  └── Margin utilization %                                       ║
║                                                                  ║
║  PER-TRADE                                                       ║
║  ├── Entry: price, time, slippage, spread, session              ║
║  ├── Context: confluence score, grade, regime, agents            ║
║  ├── Management: SL moves, partial closes, trailing              ║
║  ├── Exit: price, time, condition, slippage                      ║
║  ├── P&L: gross, net, commission, swap, R-multiple              ║
║  └── Quality: MAE, MFE, duration, rule adherence                ║
║                                                                  ║
║  PERFORMANCE (rolling 20/50/100/200)                             ║
║  ├── Win rate, Profit factor, Expectancy (R)                    ║
║  ├── Sharpe ratio, Sortino ratio                                ║
║  ├── Max drawdown (R and %)                                     ║
║  ├── Max consecutive wins/losses                                ║
║  ├── Average winner R, Average loser R                          ║
║  └── Breakdowns: pair, session, grade, agent, regime            ║
║                                                                  ║
║  RISK UTILIZATION                                                ║
║  ├── Margin used vs limit (30%)                                 ║
║  ├── Exposure vs limit (6%)                                     ║
║  ├── Correlation state (mean, max, regime)                      ║
║  ├── Circuit breaker status (4 layers)                          ║
║  ├── Daily/weekly/monthly loss vs limits                        ║
║  └── News blackout status                                       ║
║                                                                  ║
║  ALERTS                                                          ║
║  ├── Trade opened/closed → Telegram INFO                        ║
║  ├── Drawdown stage change → Telegram WARNING+                  ║
║  ├── Circuit breaker trip → Telegram CRITICAL                   ║
║  ├── Black swan → Telegram EMERGENCY + SMS + repeat             ║
║  ├── Reconciliation mismatch → Telegram CRITICAL                ║
║  ├── Win/loss streak → Telegram WARNING                         ║
║  └── Anomaly detected → Telegram WARNING+                       ║
║                                                                  ║
║  "What gets measured gets managed." — Drucker                    ║
║  "In God we trust. All others must bring data." — Deming         ║
╚══════════════════════════════════════════════════════════════════╝
```

---

*Document maintained by: Trade Monitoring Architect — Alpha Stack*
*Review cadence: Monthly, or after any monitoring system failure*
*Next review: 2026-08-11*
