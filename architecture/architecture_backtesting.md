# Alpha Stack — Backtesting Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/strategy/strategy_enhancement_steps1to4.md`](../research/strategy/strategy_enhancement_steps1to4.md) through [`steps13to16.md`](../research/strategy/strategy_enhancement_steps13to16.md) — Strategy enhancement steps — same pipeline, different data source principle
> **Status:** Architecture Complete

---

**Author:** Backtesting Architect
**Date:** 2026-07-11
**Version:** 1.0
**Status:** Architecture Design — Ready for Implementation Review
**Dependencies:** `architecture_strategy_flow.md`, `architecture_data.md`, `architecture_ml_pipeline.md`, `architecture_broker.md`, `architecture_database.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Principles](#2-design-principles)
3. [Core Architecture: Same Code for Backtest and Live](#3-core-architecture-same-code-for-backtest-and-live)
4. [Historical Data Management](#4-historical-data-management)
5. [Backtesting Engine Architecture](#5-backtesting-engine-architecture)
6. [Walk-Forward Analysis Framework](#6-walk-forward-analysis-framework)
7. [Out-of-Sample Testing Methodology](#7-out-of-sample-testing-methodology)
8. [Performance Metrics Suite](#8-performance-metrics-suite)
9. [Overfitting Detection and Prevention](#9-overfitting-detection-and-prevention)
10. [Monte Carlo Simulation for Robustness](#10-monte-carlo-simulation-for-robustness)
11. [Regime-Specific Backtesting](#11-regime-specific-backtesting)
12. [Multi-Pair Portfolio Backtesting](#12-multi-pair-portfolio-backtesting)
13. [Backtesting Reporting and Visualization](#13-backtesting-reporting-and-visualization)
14. [Implementation Roadmap](#14-implementation-roadmap)

---

## 1. Executive Summary

The backtesting engine is the **quality gate** between strategy development and live capital deployment. It must answer one question with statistical rigor: *"Would this strategy have made money historically, and is that result trustworthy?"*

### Core Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    BACKTESTING ARCHITECTURE                              │
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ HISTORICAL│→ │  EVENT   │→ │ STRATEGY │→ │EXECUTION │→ │PERFORMANCE│  │
│  │   DATA    │  │ REPLAYER │  │  ENGINE  │  │SIMULATOR │  │ ANALYZER  │  │
│  │  MANAGER  │  │          │  │(SAME CODE│  │          │  │           │  │
│  │           │  │          │  │AS LIVE)  │  │          │  │           │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  VALIDATION FRAMEWORK                                             │   │
│  │  Walk-Forward → OOS Test → Monte Carlo → Regime Analysis → Report│   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  OVERFITTING DEFENSE                                              │   │
│  │  CPCV → Deflated Sharpe → Parameter Stability → Cross-Pair Test  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Numbers

| Metric | Target |
|--------|--------|
| Backtest speed | 1 year of H1 data in < 30 seconds |
| Same-code guarantee | 100% shared code between backtest and live |
| Historical data coverage | 5+ years forex, 3+ years crypto |
| Walk-forward folds | Minimum 8 folds per strategy |
| Monte Carlo simulations | 10,000 per strategy evaluation |
| Overfitting detection | Deflated Sharpe ratio, CPCV |
| Regime coverage | 3 regimes × all pairs × all timeframes |

---

## 2. Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Same code, different data source** | Backtest replays historical data through the exact same 16-step pipeline used in live trading. Zero code duplication. |
| **Event-driven replay** | Historical candles are emitted as events, identical to live tick/candle events. The strategy engine cannot distinguish backtest from live. |
| **Realistic execution simulation** | Spread, slippage, swap, commission, and partial fills are modeled. No idealized fills. |
| **Temporal purity** | No future data leakage. Every bar is processed with only data available at that timestamp. Purge gaps between train/test. |
| **Statistical rigor** | Walk-forward validation, out-of-sample holdout, Monte Carlo stress testing, deflated Sharpe ratio. No cherry-picking. |
| **Regime awareness** | Strategies are tested across trending, ranging, and volatile regimes. Performance is reported per-regime. |
| **Portfolio-level testing** | Multi-pair correlation, cross-pair risk, and portfolio drawdown are tested, not just individual-pair metrics. |
| **Reproducibility** | Every backtest is fully reproducible: same data snapshot, same parameters, same random seeds, same results. |
| **Phase-gated complexity** | Phase 1: basic backtest. Phase 2: walk-forward + Monte Carlo. Phase 3: full institutional-grade validation. |

---

## 3. Core Architecture: Same Code for Backtest and Live

### 3.1 The Event-Driven Abstraction

The fundamental insight: both backtest and live trading are just **event processors**. The only difference is the event source.

```
LIVE TRADING:
  Market → MT5/Binance WebSocket → Event Bus → Strategy Engine → Execution

BACKTESTING:
  Historical DB → Event Replayer → Event Bus → Strategy Engine → Execution Simulator
```

The strategy engine, risk gate, signal agents, and all 16 steps are **identical** in both modes.

### 3.2 Event Source Abstraction

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketEvent:
    """Canonical event that the strategy engine consumes."""
    event_type: str          # 'tick', 'candle_close', 'news', 'orderbook', 'signal'
    symbol: str              # 'EUR/USD', 'BTC/USDT'
    timestamp: datetime      # UTC
    payload: dict            # Event-specific data
    source: str              # 'live', 'backtest', 'replay'


class EventSource(ABC):
    """
    Abstract event source. Both live and backtest implement this.
    The strategy engine only sees EventSource — it never knows which mode it's in.
    """

    @abstractmethod
    async def events(self) -> AsyncIterator[MarketEvent]:
        """Yield market events in chronological order."""
        ...

    @abstractmethod
    async def submit_order(self, order: 'Order') -> 'OrderResult':
        """Submit an order. Live goes to broker; backtest goes to simulator."""
        ...

    @abstractmethod
    async def get_position(self, symbol: str) -> 'Position':
        """Get current position for a symbol."""
        ...

    @abstractmethod
    async def get_account(self) -> 'Account':
        """Get account state (balance, equity, margin)."""
        ...


class LiveEventSource(EventSource):
    """Production event source — reads from Redis/MT5/Binance."""

    async def events(self) -> AsyncIterator[MarketEvent]:
        # Subscribe to Redis Pub/Sub for ticks and candles
        # Yield events as they arrive in real-time
        ...

    async def submit_order(self, order: 'Order') -> 'OrderResult':
        # Route through Unified Order Manager → Broker Connector
        ...


class BacktestEventSource(EventSource):
    """Backtest event source — replays historical data from TimescaleDB."""

    def __init__(self, data_store: 'HistoricalDataStore', config: 'BacktestConfig'):
        self.data_store = data_store
        self.config = config
        self.current_time = config.start_date
        self.execution_sim = ExecutionSimulator(config.execution_config)

    async def events(self) -> AsyncIterator[MarketEvent]:
        """Replay historical candles as events, in chronological order."""
        for candle in self.data_store.stream_candles(
            symbols=self.config.symbols,
            timeframes=self.config.timeframes,
            start=self.config.start_date,
            end=self.config.end_date
        ):
            # Advance simulated clock
            self.current_time = candle.timestamp

            # Yield candle close event (triggers signal detection)
            yield MarketEvent(
                event_type='candle_close',
                symbol=candle.symbol,
                timestamp=candle.timestamp,
                payload={
                    'timeframe': candle.timeframe,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume,
                    'tick_count': candle.tick_count
                },
                source='backtest'
            )

            # If tick data available, yield synthetic ticks within the candle
            if self.config.use_tick_data:
                async for tick in self.data_store.get_ticks_in_candle(candle):
                    yield MarketEvent(
                        event_type='tick',
                        symbol=tick.symbol,
                        timestamp=tick.timestamp,
                        payload={
                            'bid': tick.bid,
                            'ask': tick.ask,
                            'last': tick.last,
                            'volume': tick.volume
                        },
                        source='backtest'
                    )

    async def submit_order(self, order: 'Order') -> 'OrderResult':
        """Simulate order execution with realistic fills."""
        return await self.execution_sim.execute(order, self.current_time)

    async def get_position(self, symbol: str) -> 'Position':
        return self.execution_sim.get_position(symbol)

    async def get_account(self) -> 'Account':
        return self.execution_sim.get_account()
```

### 3.3 Strategy Engine Integration

```python
class AlphaStrategyEngine:
    """
    The 16-step strategy pipeline. Identical for live and backtest.
    It only interacts with the EventSource abstraction.
    """

    def __init__(self, event_source: EventSource, config: StrategyConfig):
        self.source = event_source
        self.config = config
        # Initialize all 16 steps (same as live)
        self.fundamental = FundamentalAgent()
        self.structure = StructureAgent()
        self.session = SessionAnalyzer()
        self.market_structure = MarketStructureAgent()
        self.sr_detector = SRDetector()
        self.liquidity = LiquidityAgent()
        self.smc = SMCAgent()
        self.momentum = MomentumAgent()
        self.candlestick = CandlestickAgent()
        self.confluence = ConfluenceScorer()
        self.entry = EntryAgent()
        self.sizing = PositionSizer()
        self.risk_gate = RiskGate()
        self.tp_manager = TPManager()
        self.trade_manager = TradeManager()
        self.journal = JournalAgent()

    async def run(self):
        """Main loop — identical for live and backtest."""
        async for event in self.source.events():
            if event.event_type == 'candle_close':
                await self._process_candle(event)
            elif event.event_type == 'tick':
                await self._process_tick(event)
            elif event.event_type == 'news':
                await self._process_news(event)

    async def _process_candle(self, event: MarketEvent):
        """Process a candle close — same logic as live."""
        # Phase 1: Context Building
        fundamental_out = await self.fundamental.analyze(event)
        structure_out = await self.market_structure.analyze(event)
        bias = await self.structure.fuse(fundamental_out, structure_out)
        session = await self.session.analyze(bias, event.timestamp)

        # Phase 2: Signal Detection (parallel)
        signals = await asyncio.gather(
            self.sr_detector.detect(event, bias, session),
            self.liquidity.detect(event, bias, session),
            self.smc.detect(event, bias, session),
            self.momentum.detect(event, bias, session),
            self.candlestick.detect(event, bias, session)
        )

        # Confluence scoring
        proposal = self.confluence.score(signals, bias, session)

        if proposal and proposal.confluence_score >= 40:
            # Phase 3: Trade Decision
            entry_plan = self.entry.plan(proposal)
            sized = self.sizing.calculate(entry_plan)
            approved = self.risk_gate.validate(sized)

            if approved:
                # Phase 4: Execution (goes to live broker OR backtest simulator)
                result = await self.source.submit_order(approved)
                self.journal.log_entry(result)
```

### 3.4 The Critical Invariant

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SAME-CODE INVARIANT                                │
│                                                                       │
│  The following components are SHARED between live and backtest:      │
│                                                                       │
│  ✅ Steps 1-16 of the strategy pipeline                              │
│  ✅ Confluence scoring logic                                          │
│  ✅ Risk gate rules                                                   │
│  ✅ Position sizing formulas                                          │
│  ✅ TP/SL management logic                                            │
│  ✅ Session analysis                                                  │
│  ✅ Regime detection (HMM)                                            │
│  ✅ Signal agent algorithms                                           │
│  ✅ Agent weight calculations                                         │
│                                                                       │
│  The following components DIFFER between live and backtest:          │
│                                                                       │
│  🔄 Event source (live WebSocket vs historical DB replay)            │
│  🔄 Order execution (broker API vs execution simulator)              │
│  🔄 Clock (real-time vs simulated)                                   │
│  🔄 Data feed (live ticks vs historical ticks/candles)               │
│                                                                       │
│  GUARANTEE: If a strategy passes backtest, the same code runs live.  │
│  There is no "backtest version" of any strategy component.           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Historical Data Management

### 4.1 Data Sources and Coverage

| Asset Class | Source | Timeframes | History | Storage |
|-------------|--------|------------|---------|---------|
| Forex (majors) | MT5 (FXPesa) | Tick, M1, M5, M15, H1, H4, D1 | 5+ years | TimescaleDB |
| Forex (crosses) | MT5 | M15, H1, H4, D1 | 3+ years | TimescaleDB |
| Crypto (BTC, ETH) | Binance | Tick, M1, M5, M15, H1, H4, D1 | 5+ years | TimescaleDB |
| Crypto (altcoins) | Binance, Bybit | M15, H1, H4, D1 | 2+ years | TimescaleDB |
| Economic calendar | MQL5 | Event timestamps | 10+ years | PostgreSQL |
| News headlines | RSS + CryptoCompare | Timestamped articles | 2+ years | PostgreSQL |
| Sentiment | Reddit, LunarCrush | Daily scores | 1+ year | PostgreSQL |
| On-chain | DefiLlama, Coinglass | Daily/hourly metrics | 2+ years | PostgreSQL |

### 4.2 Data Storage Schema for Backtesting

The backtesting engine reads from the same TimescaleDB tables used by the data pipeline (`architecture_data.md`). No separate backtest database.

```sql
-- Primary backtest data source: market_data hypertable
-- (Already defined in architecture_data.md)
-- Backtesting queries use time-range scans with symbol/timeframe filters

-- Backtest-specific: materialized data snapshots for reproducibility
CREATE TABLE backtest_data_snapshots (
    snapshot_id     UUID PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    name            TEXT NOT NULL,           -- 'eurusd_h1_2020_2026'
    symbols         TEXT[] NOT NULL,
    timeframes      TEXT[] NOT NULL,
    start_date      TIMESTAMPTZ NOT NULL,
    end_date        TIMESTAMPTZ NOT NULL,
    row_count       BIGINT NOT NULL,
    checksum        TEXT NOT NULL,           -- SHA-256 of data hash
    description     TEXT,
    metadata        JSONB                    -- Source versions, gaps found, etc.
);

-- Track data gaps found during backtest data loading
CREATE TABLE backtest_data_gaps (
    gap_id          UUID PRIMARY KEY,
    snapshot_id     UUID REFERENCES backtest_data_snapshots(snapshot_id),
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    gap_start       TIMESTAMPTZ NOT NULL,
    gap_end         TIMESTAMPTZ NOT NULL,
    gap_bars        INTEGER NOT NULL,
    fill_method     TEXT,                    -- 'forward_fill', 'interpolate', 'none'
    filled          BOOLEAN DEFAULT FALSE
);
```

### 4.3 Data Gap Detection and Handling

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA GAP HANDLING PIPELINE                         │
│                                                                       │
│  STEP 1: DETECTION                                                   │
│  • Scan all candles for each symbol/timeframe                        │
│  • Expected interval: M15=15min, H1=1h, H4=4h, D1=24h              │
│  • Gap = missing candle where expected timestamp has no data         │
│  • Exclude: weekends (forex), exchange maintenance (crypto)          │
│                                                                       │
│  STEP 2: CLASSIFICATION                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Gap Size        │ Classification │ Action                   │    │
│  │  1-2 bars        │ MINOR          │ Forward-fill             │    │
│  │  3-5 bars        │ MODERATE       │ Interpolate + flag       │    │
│  │  6-20 bars       │ MAJOR          │ Interpolate + alert      │    │
│  │  20+ bars        │ CRITICAL       │ Exclude period from test │    │
│  │  Weekend/holiday │ EXPECTED       │ Skip (no fill needed)    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  STEP 3: FILL STRATEGIES                                             │
│  • Forward-fill: Use last known OHLC. Open=Close, Volume=0.         │
│  • Linear interpolation: Interpolate OHLC linearly.                 │
│  • Higher-TF fill: Use H4 candle to synthesize missing H1 candles.  │
│  • No fill: Mark as gap, exclude from metrics for that period.      │
│                                                                       │
│  STEP 4: VALIDATION                                                  │
│  • After filling, re-scan to confirm no unexpected gaps remain       │
│  • Log all gaps with fill method to backtest_data_gaps table         │
│  • Include gap statistics in backtest report                         │
│  • If > 5% of bars are gaps → warn user of data quality issue       │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.4 Data Quality Validation

```python
class DataQualityValidator:
    """Validates historical data before backtesting."""

    def validate(self, data: DataFrame, symbol: str, timeframe: str) -> QualityReport:
        report = QualityReport(symbol=symbol, timeframe=timeframe)

        # 1. OHLC integrity
        violations = data[data['high'] < data['low']]
        report.ohlc_violations = len(violations)

        # 2. Price sanity (no zeros, no >20% single-bar moves)
        zero_prices = data[(data['open'] <= 0) | (data['close'] <= 0)]
        report.zero_prices = len(zero_prices)

        returns = data['close'].pct_change().abs()
        extreme_moves = returns[returns > 0.20]
        report.extreme_moves = len(extreme_moves)

        # 3. Timestamp ordering
        timestamp_gaps = data['time'].diff()
        expected_interval = self._expected_interval(timeframe)
        gaps = timestamp_gaps[timestamp_gaps > expected_interval * 1.5]
        report.gaps_found = len(gaps)

        # 4. Volume sanity
        zero_volume = data[data['volume'] < 0]
        report.negative_volume = len(zero_volume)

        # 5. Duplicate timestamps
        duplicates = data[data.duplicated(subset=['time'], keep=False)]
        report.duplicate_timestamps = len(duplicates)

        # 6. Session alignment
        misaligned = self._check_session_alignment(data, timeframe)
        report.session_misalignment = misaligned

        # Overall quality score
        total_checks = len(data)
        total_issues = (report.ohlc_violations + report.zero_prices +
                       report.extreme_moves + report.duplicate_timestamps)
        report.quality_score = 1.0 - (total_issues / total_checks)

        return report
```

### 4.5 Backtest Data Snapshot System

For reproducibility, every backtest run references a **data snapshot** — a checksummed record of exactly which data was used.

```python
class DataSnapshotManager:
    """Creates and manages reproducible data snapshots."""

    async def create_snapshot(self, config: BacktestConfig) -> DataSnapshot:
        """Create a named snapshot of the data used for a backtest."""
        # Fetch all data for the backtest
        data = await self.data_store.get_range(
            symbols=config.symbols,
            timeframes=config.timeframes,
            start=config.start_date,
            end=config.end_date
        )

        # Compute checksum
        checksum = hashlib.sha256(
            pd.util.hash_pandas_object(data).values.tobytes()
        ).hexdigest()

        # Detect gaps
        gaps = self.gap_detector.detect(data)

        # Store snapshot metadata
        snapshot = DataSnapshot(
            id=uuid.uuid4(),
            name=config.snapshot_name,
            symbols=config.symbols,
            timeframes=config.timeframes,
            start_date=config.start_date,
            end_date=config.end_date,
            row_count=len(data),
            checksum=checksum,
            gaps=gaps,
            metadata={
                'source_versions': self._get_source_versions(),
                'created_by': 'backtest_engine',
                'config_hash': config.hash()
            }
        )

        await self.db.insert('backtest_data_snapshots', snapshot)
        return snapshot

    async def verify_snapshot(self, snapshot_id: str) -> bool:
        """Verify that the data for a snapshot hasn't changed."""
        snapshot = await self.db.get('backtest_data_snapshots', snapshot_id)
        current_data = await self.data_store.get_range(
            symbols=snapshot.symbols,
            timeframes=snapshot.timeframes,
            start=snapshot.start_date,
            end=snapshot.end_date
        )
        current_checksum = hashlib.sha256(
            pd.util.hash_pandas_object(current_data).values.tobytes()
        ).hexdigest()
        return current_checksum == snapshot.checksum
```

---

## 5. Backtesting Engine Architecture

### 5.1 Execution Simulator

The execution simulator models realistic trading conditions. It is the single most important component for backtest accuracy.

```python
@dataclass
class ExecutionConfig:
    """Realistic execution modeling parameters."""
    # Spread model
    spread_model: str = 'dynamic'          # 'fixed', 'dynamic', 'historical'
    fixed_spread_pips: float = 1.5         # Used if spread_model='fixed'
    spread_multiplier: float = 1.0         # Scale historical spreads

    # Slippage model
    slippage_model: str = 'volume_based'   # 'fixed', 'volume_based', 'volatility_based'
    fixed_slippage_pips: float = 0.5       # Used if slippage_model='fixed'
    slippage_per_lot: float = 0.1          # Additional slippage per lot

    # Commission
    commission_per_lot: float = 7.0        # USD per round-turn lot
    commission_type: str = 'per_lot'       # 'per_lot', 'per_trade', 'percentage'

    # Swap
    include_swap: bool = True
    swap_source: str = 'broker'            # 'broker', 'estimated', 'custom'

    # Partial fills
    allow_partial_fills: bool = False      # True for large orders
    partial_fill_threshold_lots: float = 1.0  # Orders above this may partially fill

    # Latency simulation
    execution_latency_ms: int = 200        # Simulated latency
    slippage_during_latency: bool = True   # Price can move during latency

    # Limit order modeling
    limit_order_touch: str = 'high_low'    # 'close', 'high_low', 'tick_data'
    limit_fill_probability: float = 0.85   # Probability limit fills when price touches


class ExecutionSimulator:
    """
    Simulates realistic order execution for backtesting.
    Models spread, slippage, commission, swap, and partial fills.
    """

    def __init__(self, config: ExecutionConfig):
        self.config = config
        self.positions: dict[str, Position] = {}
        self.account = Account(balance=10000.0, equity=10000.0)
        self.trade_log: list[SimulatedTrade] = []

    async def execute(self, order: Order, current_time: datetime) -> OrderResult:
        """Execute an order with realistic simulation."""

        # 1. Get current market state
        market = await self._get_market_state(order.symbol, current_time)

        # 2. Apply execution latency (price may move)
        if self.config.execution_latency_ms > 0:
            market = await self._apply_latency_drift(market, order.symbol, current_time)

        # 3. Calculate fill price with spread and slippage
        fill_price = self._calculate_fill_price(order, market)

        # 4. Calculate commission
        commission = self._calculate_commission(order)

        # 5. Check margin requirements
        margin_required = self._calculate_margin(order, fill_price)
        if margin_required > self.account.free_margin:
            return OrderResult(
                status='REJECTED',
                reason='INSUFFICIENT_MARGIN',
                order=order
            )

        # 6. Execute the fill
        if order.order_type == 'MARKET':
            result = self._fill_market_order(order, fill_price, commission, current_time)
        elif order.order_type == 'LIMIT':
            result = self._fill_limit_order(order, market, commission, current_time)
        elif order.order_type == 'STOP':
            result = self._fill_stop_order(order, market, commission, current_time)
        else:
            result = OrderResult(status='REJECTED', reason='UNKNOWN_ORDER_TYPE')

        # 7. Update positions and account
        if result.status == 'FILLED':
            self._update_position(order, result)
            self._update_account()

        return result

    def _calculate_fill_price(self, order: Order, market: MarketState) -> float:
        """Calculate realistic fill price including spread and slippage."""

        if order.action == 'BUY':
            base_price = market.ask  # Buy at ask
        else:
            base_price = market.bid  # Sell at bid

        # Apply slippage
        if self.config.slippage_model == 'fixed':
            slippage = self.config.fixed_slippage_pips * market.pip_value
        elif self.config.slippage_model == 'volume_based':
            # More slippage for larger orders
            slippage = (self.config.fixed_slippage_pips +
                       order.size * self.config.slippage_per_lot) * market.pip_value
        elif self.config.slippage_model == 'volatility_based':
            # More slippage in volatile markets
            slippage = market.atr_14 * 0.05 * (order.size / 0.01)

        if order.action == 'BUY':
            return base_price + slippage
        else:
            return base_price - slippage

    def _calculate_commission(self, order: Order) -> float:
        """Calculate trading commission."""
        if self.config.commission_type == 'per_lot':
            return self.config.commission_per_lot * order.size
        elif self.config.commission_type == 'per_trade':
            return self.config.commission_per_lot
        elif self.config.commission_type == 'percentage':
            return order.size * order.price * (self.config.commission_per_lot / 100)
        return 0.0

    def calculate_swap(self, symbol: str, direction: str,
                       size: float, days_held: int) -> float:
        """Calculate swap/rollover cost for holding positions overnight."""
        if not self.config.include_swap:
            return 0.0
        swap_rate = self._get_swap_rate(symbol, direction)
        return swap_rate * size * days_held
```

### 5.2 Backtest Runner

```python
class BacktestRunner:
    """
    Orchestrates a complete backtest run.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.data_store = HistoricalDataStore()
        self.snapshot_mgr = DataSnapshotManager()
        self.validator = DataQualityValidator()

    async def run(self) -> BacktestResult:
        """Execute a complete backtest."""

        # 1. Validate data quality
        quality = self.validator.validate_all(
            self.config.symbols, self.config.timeframes,
            self.config.start_date, self.config.end_date
        )
        if quality.quality_score < 0.95:
            raise DataQualityError(f"Data quality too low: {quality.quality_score:.2%}")

        # 2. Create data snapshot for reproducibility
        snapshot = await self.snapshot_mgr.create_snapshot(self.config)

        # 3. Initialize event source (backtest mode)
        event_source = BacktestEventSource(
            data_store=self.data_store,
            config=self.config
        )

        # 4. Initialize strategy engine (SAME code as live)
        strategy = AlphaStrategyEngine(
            event_source=event_source,
            config=self.config.strategy_config
        )

        # 5. Run the strategy
        start_time = time.time()
        await strategy.run()
        elapsed = time.time() - start_time

        # 6. Collect results
        trades = event_source.execution_sim.trade_log
        account = event_source.execution_sim.account

        # 7. Compute performance metrics
        metrics = PerformanceAnalyzer.compute_all(trades, account)

        # 8. Package results
        return BacktestResult(
            config=self.config,
            snapshot=snapshot,
            quality=quality,
            trades=trades,
            metrics=metrics,
            elapsed_seconds=elapsed,
            bars_processed=event_source.bars_processed,
            data_gaps=quality.gaps_found
        )
```

### 5.3 Multi-Timeframe Event Replay

The strategy engine uses multiple timeframes (M15, H1, H4, D1). The event replayer must emit events in the correct order.

```python
class MultiTimeframeReplayer:
    """
    Replays multi-timeframe data in correct chronological order.
    Ensures H4 candle close events fire before H1 events that depend on them.
    """

    def __init__(self, data_store: HistoricalDataStore):
        self.data_store = data_store

    async def replay(self, symbols: list[str], timeframes: list[str],
                     start: datetime, end: datetime) -> AsyncIterator[MarketEvent]:
        """
        Merge-sort events from multiple timeframes by timestamp.
        Higher timeframes fire first when timestamps match (H4 before H1).
        """
        # Priority: D1 > H4 > H1 > M15 > M5 > M1
        tf_priority = {'D1': 0, 'H4': 1, 'H1': 2, 'M15': 3, 'M5': 4, 'M1': 5}

        # Create iterators for each symbol/timeframe combination
        iterators = []
        for symbol in symbols:
            for tf in timeframes:
                it = self.data_store.stream_candles(symbol, tf, start, end)
                iterators.append((it, symbol, tf))

        # Merge-sort using a priority queue
        import heapq
        heap = []

        # Prime the heap
        for it, symbol, tf in iterators:
            try:
                candle = await it.__anext__()
                heapq.heappush(heap, (
                    candle.timestamp,
                    tf_priority.get(tf, 99),
                    symbol, tf, it, candle
                ))
            except StopIteration:
                pass

        # Yield events in order
        while heap:
            timestamp, priority, symbol, tf, it, candle = heapq.heappop(heap)

            yield MarketEvent(
                event_type='candle_close',
                symbol=symbol,
                timestamp=timestamp,
                payload={
                    'timeframe': tf,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume
                },
                source='backtest'
            )

            # Advance iterator
            try:
                next_candle = await it.__anext__()
                heapq.heappush(heap, (
                    next_candle.timestamp,
                    tf_priority.get(tf, 99),
                    symbol, tf, it, next_candle
                ))
            except StopIteration:
                pass
```

---

## 6. Walk-Forward Analysis Framework

### 6.1 Walk-Forward Design

Walk-forward analysis is the **primary validation method** for Alpha Stack strategies. It prevents overfitting by testing on data the model has never seen.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WALK-FORWARD ANALYSIS                             │
│                                                                       │
│  WINDOW CONFIGURATION:                                               │
│  • Training window: 252 trading days (1 year)                       │
│  • Test window: 63 trading days (1 quarter)                         │
│  • Step size: 21 trading days (1 month)                             │
│  • Purge gap: 5 bars between train end and test start               │
│                                                                       │
│  TIMELINE:                                                            │
│                                                                       │
│  Fold 1: [===TRAIN 252d===]---[===TEST 63d===]                      │
│  Fold 2:    [===TRAIN 252d===]---[===TEST 63d===]                   │
│  Fold 3:       [===TRAIN 252d===]---[===TEST 63d===]                │
│  Fold 4:          [===TRAIN 252d===]---[===TEST 63d===]             │
│  Fold 5:             [===TRAIN 252d===]---[===TEST 63d===]          │
│  Fold 6:                [===TRAIN 252d===]---[===TEST 63d===]       │
│  Fold 7:                   [===TRAIN 252d===]---[===TEST 63d===]    │
│  Fold 8:                      [===TRAIN 252d===]---[===TEST 63d===] │
│                                                                       │
│  With 3 years of data: 8 folds (each test window is unique)         │
│  With 5 years of data: 16 folds                                     │
│                                                                       │
│  OUTPUT PER FOLD:                                                    │
│  • Sharpe ratio, Sortino ratio, max drawdown                        │
│  • Win rate, profit factor, avg R-multiple                          │
│  • Trade count, exposure time                                       │
│  • Parameter values used (if adaptive)                              │
│                                                                       │
│  AGGREGATE OUTPUT:                                                   │
│  • Mean ± std of all metrics across folds                           │
│  • Worst-fold metrics (stress case)                                 │
│  • Consistency ratio (% of profitable folds)                        │
│  • Parameter stability (drift across folds)                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Walk-Forward Implementation

```python
class WalkForwardAnalyzer:
    """
    Implements walk-forward analysis for strategy validation.
    """

    def __init__(self, config: WalkForwardConfig):
        self.train_days = config.train_days        # 252
        self.test_days = config.test_days          # 63
        self.step_days = config.step_days          # 21
        self.purge_bars = config.purge_bars        # 5

    async def analyze(self, strategy_config: StrategyConfig,
                      symbols: list[str],
                      full_start: datetime,
                      full_end: datetime) -> WalkForwardResult:
        """Run full walk-forward analysis."""

        folds = []
        fold_id = 0

        # Generate fold windows
        windows = self._generate_windows(full_start, full_end)

        for train_start, train_end, test_start, test_end in windows:
            fold_id += 1
            logger.info(f"Walk-forward fold {fold_id}: "
                       f"Train {train_start.date()}→{train_end.date()}, "
                       f"Test {test_start.date()}→{test_end.date()}")

            # 1. Train: Run backtest on training window
            # (For rule-based strategies, this is parameter optimization)
            # (For ML strategies, this is model training)
            train_result = await self._run_fold(
                strategy_config, symbols, train_start, train_end,
                mode='train'
            )

            # 2. Extract optimized parameters from training
            optimized_params = train_result.optimal_parameters

            # 3. Test: Run backtest on test window with frozen parameters
            test_config = strategy_config.with_parameters(optimized_params)
            test_result = await self._run_fold(
                test_config, symbols, test_start, test_end,
                mode='test'
            )

            # 4. Record fold results
            folds.append(WalkForwardFold(
                fold_id=fold_id,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_metrics=train_result.metrics,
                test_metrics=test_result.metrics,
                parameters=optimized_params,
                trade_count=test_result.trade_count
            ))

        # 5. Aggregate results
        return WalkForwardResult(
            folds=folds,
            mean_metrics=self._mean_metrics(folds),
            std_metrics=self._std_metrics(folds),
            worst_fold=self._worst_fold(folds),
            consistency_ratio=self._consistency_ratio(folds),
            parameter_stability=self._parameter_stability(folds)
        )

    def _generate_windows(self, start: datetime, end: datetime) -> list[tuple]:
        """Generate train/test window pairs with purge gap."""
        windows = []
        current = start

        while True:
            train_start = current
            train_end = train_start + timedelta(days=self.train_days)
            test_start = train_end + timedelta(days=self.purge_bars)
            test_end = test_start + timedelta(days=self.test_days)

            if test_end > end:
                break

            windows.append((train_start, train_end, test_start, test_end))
            current += timedelta(days=self.step_days)

        return windows
```

### 6.3 Parameter Optimization Within Walk-Forward

For rule-based strategy parameters, optimization happens **within each training fold only**:

```python
class WalkForwardOptimizer:
    """
    Optimizes strategy parameters within each walk-forward training window.
    Parameters are frozen and applied to the test window.
    """

    async def optimize_fold(self, strategy_config: StrategyConfig,
                           train_start: datetime, train_end: datetime,
                           optimization_target: str = 'sharpe_ratio') -> dict:
        """
        Find optimal parameters for a training window.
        Uses Bayesian optimization (Optuna).
        """
        import optuna

        def objective(trial):
            # Suggest parameters
            params = {
                'confluence_threshold': trial.suggest_int('confluence_threshold', 40, 80),
                'rsi_oversold': trial.suggest_int('rsi_oversold', 20, 35),
                'rsi_overbought': trial.suggest_int('rsi_overbought', 65, 80),
                'atr_sl_multiplier': trial.suggest_float('atr_sl_multiplier', 0.5, 2.0),
                'atr_tp_multiplier': trial.suggest_float('atr_tp_multiplier', 1.0, 4.0),
                'max_risk_pct': trial.suggest_float('max_risk_pct', 0.5, 2.0),
                'sr_touch_weight': trial.suggest_float('sr_touch_weight', 0.1, 0.4),
                'liquidity_weight': trial.suggest_float('liquidity_weight', 0.1, 0.4),
                'smc_weight': trial.suggest_float('smc_weight', 0.1, 0.4),
                'momentum_weight': trial.suggest_float('momentum_weight', 0.05, 0.3),
                'candlestick_weight': trial.suggest_float('candlestick_weight', 0.05, 0.2),
            }

            # Run backtest with these parameters on training window
            config = strategy_config.with_parameters(params)
            result = await self.backtest_runner.run_single(
                config, train_start, train_end
            )

            # Return optimization target
            if optimization_target == 'sharpe_ratio':
                return result.metrics.sharpe_ratio
            elif optimization_target == 'sortino_ratio':
                return result.metrics.sortino_ratio
            elif optimization_target == 'calmar_ratio':
                return result.metrics.calmar_ratio
            elif optimization_target == 'profit_factor':
                return result.metrics.profit_factor

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=50, timeout=300)  # 50 trials or 5 min

        return study.best_params
```

### 6.4 Walk-Forward Acceptance Criteria

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WALK-FORWARD ACCEPTANCE CRITERIA                   │
│                                                                       │
│  ALL of the following must be true for a strategy to pass:           │
│                                                                       │
│  1. PERFORMANCE CONSISTENCY                                          │
│     □ Mean Sharpe (test folds) > 1.0                                │
│     □ At least 70% of test folds are profitable                     │
│     □ Worst-fold Sharpe > 0 (no catastrophic fold)                  │
│     □ Test Sharpe within 30% of Train Sharpe (no severe overfitting)│
│                                                                       │
│  2. RISK METRICS                                                     │
│     □ Mean max drawdown (test folds) < 20%                          │
│     □ Worst-fold max drawdown < 30%                                 │
│     □ Mean Sortino ratio > 1.5                                      │
│     □ Mean profit factor > 1.3                                      │
│                                                                       │
│  3. TRADE QUALITY                                                    │
│     □ Minimum 30 trades per test fold (statistical significance)    │
│     □ Mean win rate > 45%                                           │
│     □ Mean R-multiple > 0.3 (positive expectancy)                   │
│                                                                       │
│  4. PARAMETER STABILITY                                              │
│     □ No parameter drifts > 50% of its range across folds           │
│     □ Optimal parameters don't cluster at search space boundaries   │
│                                                                       │
│  5. EXECUTION REALISM                                                │
│     □ Results include spread, slippage, commission, swap            │
│     □ No single trade accounts for > 20% of total P&L              │
│     □ Max consecutive losses < 10                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Out-of-Sample Testing Methodology

### 7.1 Data Allocation Protocol

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA ALLOCATION (STRICT)                           │
│                                                                       │
│  For a 5-year dataset (2021-2026):                                   │
│                                                                       │
│  ├─── 60% (3 years) ───┤── 20% (1 year) ──┤── 20% (1 year) ──┤    │
│  │     TRAINING          │   VALIDATION      │  OOS TEST         │    │
│  │  (Walk-forward CV)    │  (Hyperparameter  │  (FINAL test.     │    │
│  │                       │   tuning, model    │   Used ONCE.)     │    │
│  │                       │   selection)       │                   │    │
│                                                                       │
│  RULES:                                                               │
│  1. Training data: Used for walk-forward cross-validation            │
│  2. Validation data: Used for hyperparameter tuning and model        │
│     selection. May be peeked at during development.                  │
│  3. OOS test data: SACRED. Used exactly once, at the very end.      │
│     If we peek at it, we must hold out a new OOS portion.           │
│  4. Purge gaps: 5 bars between each split to prevent leakage        │
│                                                                       │
│  FOR 3-YEAR DATASET:                                                 │
│  ├─── 60% (21.6 months) ───┤── 20% (7.2mo) ──┤── 20% (7.2mo) ──┤ │
│  Same ratios, shorter periods.                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Out-of-Sample Test Protocol

```python
class OutOfSampleTester:
    """
    Runs the final out-of-sample test on held-out data.
    This is the "real world" test before deployment.
    """

    async def run_oos_test(self, strategy_config: StrategyConfig,
                           symbols: list[str],
                           oos_start: datetime,
                           oos_end: datetime) -> OOSResult:
        """
        Run the final out-of-sample test.

        The strategy parameters are FROZEN from walk-forward optimization.
        The model is retrained on training+validation data.
        """

        # 1. Verify OOS data has never been used
        assert not self._data_was_used_in_training(oos_start, oos_end), \
            "OOS data contamination detected!"

        # 2. Run backtest on OOS period with frozen parameters
        runner = BacktestRunner(strategy_config)
        result = await runner.run(symbols, oos_start, oos_end)

        # 3. Compare to walk-forward metrics
        wf_metrics = self.walk_forward_result.mean_metrics
        oos_metrics = result.metrics

        comparison = self._compare_metrics(wf_metrics, oos_metrics)

        # 4. Generate SHAP explanations for OOS predictions
        # (for ML-based signal components)
        explanations = await self._generate_explanations(result)

        # 5. Identify edge cases
        edge_cases = self._identify_edge_cases(result.trades)

        return OOSResult(
            metrics=oos_metrics,
            walk_forward_comparison=comparison,
            explanations=explanations,
            edge_cases=edge_cases,
            passed=self._check_acceptance(oos_metrics, wf_metrics)
        )

    def _compare_metrics(self, wf: Metrics, oos: Metrics) -> MetricComparison:
        """Compare OOS metrics to walk-forward metrics."""
        return MetricComparison(
            sharpe_ratio={'wf': wf.sharpe_ratio, 'oos': oos.sharpe_ratio,
                         'pct_diff': (oos.sharpe_ratio - wf.sharpe_ratio) / wf.sharpe_ratio},
            max_drawdown={'wf': wf.max_drawdown, 'oos': oos.max_drawdown,
                         'pct_diff': (oos.max_drawdown - wf.max_drawdown) / wf.max_drawdown},
            win_rate={'wf': wf.win_rate, 'oos': oos.win_rate,
                     'pct_diff': (oos.win_rate - wf.win_rate) / wf.win_rate},
            profit_factor={'wf': wf.profit_factor, 'oos': oos.profit_factor,
                          'pct_diff': (oos.profit_factor - wf.profit_factor) / wf.profit_factor}
        )

    def _check_acceptance(self, oos: Metrics, wf: Metrics) -> bool:
        """Check if OOS results pass acceptance criteria."""
        # Sharpe must be within 30% of walk-forward mean
        sharpe_ok = oos.sharpe_ratio >= wf.sharpe_ratio * 0.70

        # Max drawdown must not be >50% worse than walk-forward
        dd_ok = oos.max_drawdown <= wf.max_drawdown * 1.50

        # Win rate must be within 10% of walk-forward
        wr_ok = abs(oos.win_rate - wf.win_rate) <= 0.10

        # Must have positive expectancy
        positive_ok = oos.profit_factor > 1.0

        return sharpe_ok and dd_ok and wr_ok and positive_ok
```

### 7.3 OOS Acceptance Criteria

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OOS ACCEPTANCE CRITERIA                            │
│                                                                       │
│  The OOS test is PASS/FAIL. All criteria must be met:               │
│                                                                       │
│  □ OOS Sharpe ≥ 0.7 × Walk-Forward Sharpe                          │
│    (Performance degradation < 30%)                                   │
│                                                                       │
│  □ OOS Max Drawdown ≤ 1.5 × Walk-Forward Max Drawdown              │
│    (Risk increase < 50%)                                             │
│                                                                       │
│  □ |OOS Win Rate - WF Win Rate| ≤ 10%                               │
│    (Win rate stability)                                              │
│                                                                       │
│  □ OOS Profit Factor > 1.0                                          │
│    (Positive expectancy)                                             │
│                                                                       │
│  □ OOS Sharpe > 0.5                                                  │
│    (Minimum absolute performance)                                    │
│                                                                       │
│  □ No single trade accounts for > 30% of OOS P&L                   │
│    (No outlier dependence)                                           │
│                                                                       │
│  □ Trade count ≥ 20                                                  │
│    (Statistical significance)                                        │
│                                                                       │
│  FAILURE RESPONSE:                                                   │
│  • If OOS fails, the strategy CANNOT go live                        │
│  • Options: simplify strategy, reduce parameters, get more data     │
│  • Do NOT look at OOS results to adjust parameters                  │
│  • If adjusting, must hold out NEW OOS data                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Performance Metrics Suite

### 8.1 Complete Metrics Calculator

```python
class PerformanceAnalyzer:
    """
    Computes comprehensive performance metrics for backtest results.
    """

    @staticmethod
    def compute_all(trades: list[SimulatedTrade], account: Account) -> PerformanceMetrics:
        """Compute all performance metrics."""

        returns = [t.pnl_pct for t in trades if t.status == 'CLOSED']
        equity_curve = PerformanceAnalyzer._build_equity_curve(trades, account.initial_balance)

        return PerformanceMetrics(
            # Return metrics
            total_return_pct=PerformanceAnalyzer._total_return(equity_curve),
            annualized_return_pct=PerformanceAnalyzer._annualized_return(equity_curve),
            monthly_returns=PerformanceAnalyzer._monthly_returns(equity_curve),

            # Risk-adjusted returns
            sharpe_ratio=PerformanceAnalyzer._sharpe_ratio(returns),
            sortino_ratio=PerformanceAnalyzer._sortino_ratio(returns),
            calmar_ratio=PerformanceAnalyzer._calmar_ratio(returns, equity_curve),
            omega_ratio=PerformanceAnalyzer._omega_ratio(returns),

            # Drawdown metrics
            max_drawdown_pct=PerformanceAnalyzer._max_drawdown(equity_curve),
            max_drawdown_duration_days=PerformanceAnalyzer._max_drawdown_duration(equity_curve),
            avg_drawdown_pct=PerformanceAnalyzer._avg_drawdown(equity_curve),
            drawdown_series=PerformanceAnalyzer._drawdown_series(equity_curve),

            # Trade statistics
            total_trades=len(trades),
            winning_trades=len([t for t in trades if t.pnl > 0]),
            losing_trades=len([t for t in trades if t.pnl < 0]),
            win_rate=PerformanceAnalyzer._win_rate(trades),
            avg_win=PerformanceAnalyzer._avg_win(trades),
            avg_loss=PerformanceAnalyzer._avg_loss(trades),
            largest_win=PerformanceAnalyzer._largest_win(trades),
            largest_loss=PerformanceAnalyzer._largest_loss(trades),

            # Expectancy
            profit_factor=PerformanceAnalyzer._profit_factor(trades),
            expectancy_per_trade=PerformanceAnalyzer._expectancy(trades),
            avg_r_multiple=PerformanceAnalyzer._avg_r_multiple(trades),
            expectancy_r=PerformanceAnalyzer._expectancy_r(trades),

            # Streak analysis
            max_consecutive_wins=PerformanceAnalyzer._max_streak(trades, 'win'),
            max_consecutive_losses=PerformanceAnalyzer._max_streak(trades, 'loss'),

            # Time analysis
            avg_trade_duration_hours=PerformanceAnalyzer._avg_duration(trades),
            exposure_time_pct=PerformanceAnalyzer._exposure_time(trades, equity_curve),

            # Execution quality
            total_commission=PerformanceAnalyzer._total_commission(trades),
            total_slippage=PerformanceAnalyzer._total_slippage(trades),
            total_swap=PerformanceAnalyzer._total_swap(trades),
            avg_slippage_per_trade=PerformanceAnalyzer._avg_slippage(trades),

            # Per-signal breakdown
            metrics_by_signal_source=PerformanceAnalyzer._by_signal_source(trades),
            metrics_by_regime=PerformanceAnalyzer._by_regime(trades),
            metrics_by_session=PerformanceAnalyzer._by_session(trades),
            metrics_by_pair=PerformanceAnalyzer._by_pair(trades)
        )
```

### 8.2 Metric Definitions and Formulas

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PERFORMANCE METRICS DEFINITIONS                    │
│                                                                       │
│  ═══ RETURN METRICS ═══                                              │
│                                                                       │
│  Total Return = (Final Equity - Initial Equity) / Initial Equity     │
│  Annualized Return = (1 + Total Return)^(252/Trading Days) - 1       │
│  Monthly Return = (Equity Month End - Equity Month Start) /          │
│                   Equity Month Start                                  │
│                                                                       │
│  ═══ RISK-ADJUSTED RETURNS ═══                                       │
│                                                                       │
│  Sharpe Ratio = (Mean Daily Return - Rf) / Std(Daily Returns)        │
│                × √252                                                 │
│    Where Rf = risk-free rate (use 0 for simplicity)                  │
│                                                                       │
│  Sortino Ratio = (Mean Daily Return - Rf) / Downside Std Dev         │
│                  × √252                                               │
│    Where Downside Std = std of negative returns only                 │
│                                                                       │
│  Calmar Ratio = Annualized Return / |Max Drawdown|                   │
│                                                                       │
│  Omega Ratio = Σ(max(R - threshold, 0)) / Σ(max(threshold - R, 0))  │
│    Where threshold = 0 (or risk-free rate)                           │
│                                                                       │
│  ═══ DRAWDOWN METRICS ═══                                            │
│                                                                       │
│  Drawdown at time t = (Peak Equity - Current Equity) / Peak Equity   │
│  Max Drawdown = max(Drawdown(t)) for all t                           │
│  Avg Drawdown = mean(all drawdowns > 0)                              │
│  Drawdown Duration = time from peak to recovery                      │
│  Max DD Duration = longest drawdown duration                         │
│                                                                       │
│  ═══ TRADE STATISTICS ═══                                            │
│                                                                       │
│  Win Rate = Winning Trades / Total Trades                            │
│  Profit Factor = Gross Profit / Gross Loss                           │
│  Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)         │
│                                                                       │
│  R-Multiple = Actual P&L / Initial Risk (stop loss distance)         │
│  Avg R-Multiple = mean(R-multiples for all trades)                   │
│  Expectancy in R = mean(R-multiples)                                 │
│                                                                       │
│  ═══ STREAK ANALYSIS ═══                                             │
│                                                                       │
│  Max Consecutive Wins = longest winning streak                       │
│  Max Consecutive Losses = longest losing streak                      │
│  (Used for psychological assessment and drawdown estimation)         │
│                                                                       │
│  ═══ EXECUTION QUALITY ═══                                           │
│                                                                       │
│  Total Commission = Σ(commission per trade)                          │
│  Total Slippage = Σ(|fill_price - intended_price| × size)            │
│  Total Swap = Σ(swap charges per trade)                              │
│  Execution Cost % = (Commission + Slippage + Swap) / Total P&L       │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.3 Metric Implementation

```python
    @staticmethod
    def _sharpe_ratio(returns: list[float], risk_free_rate: float = 0.0,
                     periods_per_year: int = 252) -> float:
        """Annualized Sharpe ratio."""
        if not returns or len(returns) < 2:
            return 0.0
        returns_arr = np.array(returns)
        excess_returns = returns_arr - risk_free_rate / periods_per_year
        mean_excess = np.mean(excess_returns)
        std_returns = np.std(excess_returns, ddof=1)
        if std_returns == 0:
            return 0.0
        return (mean_excess / std_returns) * np.sqrt(periods_per_year)

    @staticmethod
    def _sortino_ratio(returns: list[float], risk_free_rate: float = 0.0,
                      periods_per_year: int = 252) -> float:
        """Annualized Sortino ratio (penalizes only downside volatility)."""
        if not returns or len(returns) < 2:
            return 0.0
        returns_arr = np.array(returns)
        excess_returns = returns_arr - risk_free_rate / periods_per_year
        mean_excess = np.mean(excess_returns)
        downside_returns = returns_arr[returns_arr < 0]
        if len(downside_returns) == 0:
            return float('inf')  # No losing trades
        downside_std = np.std(downside_returns, ddof=1)
        if downside_std == 0:
            return 0.0
        return (mean_excess / downside_std) * np.sqrt(periods_per_year)

    @staticmethod
    def _max_drawdown(equity_curve: list[float]) -> float:
        """Maximum drawdown as a percentage."""
        peak = equity_curve[0]
        max_dd = 0.0
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @staticmethod
    def _win_rate(trades: list[SimulatedTrade]) -> float:
        """Win rate as a decimal."""
        closed = [t for t in trades if t.status == 'CLOSED']
        if not closed:
            return 0.0
        wins = len([t for t in closed if t.pnl > 0])
        return wins / len(closed)

    @staticmethod
    def _profit_factor(trades: list[SimulatedTrade]) -> float:
        """Gross profit / gross loss."""
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @staticmethod
    def _avg_r_multiple(trades: list[SimulatedTrade]) -> float:
        """Average R-multiple across all trades."""
        r_multiples = []
        for t in trades:
            if t.initial_risk > 0:
                r_multiples.append(t.pnl / t.initial_risk)
        return np.mean(r_multiples) if r_multiples else 0.0
```

---

## 9. Overfitting Detection and Prevention

### 9.1 Overfitting Defense Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OVERFITTING DEFENSE SYSTEM                         │
│                                                                       │
│  LAYER 1: WALK-FORWARD VALIDATION (Primary defense)                  │
│  • Train on past, test on future — always                            │
│  • Multiple folds reveal instability                                 │
│  • Test Sharpe must be within 30% of Train Sharpe                    │
│                                                                       │
│  LAYER 2: COMBINATORIAL PURGED CV (CPCV)                            │
│  • Marcos López de Prado's method                                    │
│  • Generates multiple backtest paths                                 │
│  • Reveals performance variance                                      │
│  • Deflated Sharpe ratio accounts for multiple testing               │
│                                                                       │
│  LAYER 3: DEFLATED SHARPE RATIO                                      │
│  • Adjusts Sharpe for number of trials                               │
│  • Accounts for non-normal returns (skew, kurtosis)                  │
│  • Threshold: Deflated Sharpe > 1.0 required                        │
│                                                                       │
│  LAYER 4: PARAMETER STABILITY ANALYSIS                               │
│  • No parameter should cluster at search space boundaries            │
│  • Performance should be robust to ±10% parameter changes            │
│  • Parameters should not drift >50% across walk-forward folds        │
│                                                                       │
│  LAYER 5: CROSS-PAIR GENERALIZATION                                  │
│  • Strategy trained on EUR/USD must work on GBP/USD, USD/JPY        │
│  • If it only works on one pair → likely overfit to that pair        │
│                                                                       │
│  LAYER 6: REGIME CONSISTENCY                                         │
│  • Strategy must perform in trending AND ranging markets             │
│  • If it only works in one regime → regime-specific overfitting      │
│                                                                       │
│  LAYER 7: SIMPLE PARSIMONY                                           │
│  • Fewer parameters = less overfitting surface                       │
│  • AIC/BIC penalty for model complexity                              │
│  • Prefer simple strategies over complex ones when performance is    │
│    similar                                                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 Combinatorial Purged Cross-Validation (CPCV)

```python
class CombinatorialPurgedCV:
    """
    López de Prado's CPCV method for strategy validation.
    Generates multiple backtest paths to reveal performance variance.
    """

    def __init__(self, n_groups: int = 10, n_test_groups: int = 2,
                 purge_bars: int = 5):
        self.n_groups = n_groups
        self.n_test_groups = n_test_groups
        self.purge_bars = purge_bars

    def generate_paths(self, data_length: int) -> list[CVPath]:
        """Generate all C(n_groups, n_test_groups) backtest paths."""
        from itertools import combinations

        group_size = data_length // self.n_groups
        groups = [
            (i * group_size, (i + 1) * group_size)
            for i in range(self.n_groups)
        ]

        paths = []
        for test_group_ids in combinations(range(self.n_groups), self.n_test_groups):
            test_ranges = [groups[i] for i in test_group_ids]
            train_ranges = [
                groups[i] for i in range(self.n_groups)
                if i not in test_group_ids
            ]

            # Apply purge around test boundaries
            train_ranges = self._apply_purge(train_ranges, test_ranges)

            paths.append(CVPath(
                train_ranges=train_ranges,
                test_ranges=test_ranges,
                path_id=f"path_{'_'.join(map(str, test_group_ids))}"
            ))

        return paths

    async def evaluate_strategy(self, strategy_config: StrategyConfig,
                                data: DataFrame) -> CPVCResult:
        """
        Run strategy on all CPCV paths and compute performance distribution.
        """
        paths = self.generate_paths(len(data))
        path_results = []

        for path in paths:
            # Train on train ranges
            train_data = self._extract_ranges(data, path.train_ranges)
            optimized_params = await self._optimize(train_data, strategy_config)

            # Test on test ranges
            test_data = self._extract_ranges(data, path.test_ranges)
            test_config = strategy_config.with_parameters(optimized_params)
            result = await self._backtest(test_data, test_config)

            path_results.append(PathResult(
                path_id=path.path_id,
                sharpe=result.metrics.sharpe_ratio,
                max_dd=result.metrics.max_drawdown,
                trades=result.metrics.total_trades,
                pnl=result.metrics.total_return_pct
            ))

        # Compute deflated Sharpe ratio
        sharpe_values = [r.sharpe for r in path_results]
        deflated_sharpe = self._deflated_sharpe(sharpe_values, len(paths))

        return CPVCResult(
            paths=path_results,
            mean_sharpe=np.mean(sharpe_values),
            std_sharpe=np.std(sharpe_values),
            min_sharpe=np.min(sharpe_values),
            max_sharpe=np.max(sharpe_values),
            deflated_sharpe=deflated_sharpe,
            paths_profitable=sum(1 for r in path_results if r.sharpe > 0),
            total_paths=len(path_results)
        )

    def _deflated_sharpe(self, sharpe_values: list[float],
                         n_trials: int) -> float:
        """
        Compute deflated Sharpe ratio (Bailey & López de Prado, 2014).
        Adjusts for multiple testing bias and non-normal returns.
        """
        observed_sharpe = np.max(sharpe_values)

        # Expected max Sharpe under null (no skill)
        # Using approx: E[max(S)] ≈ sqrt(2 * ln(n_trials)) * σ_S
        expected_max_sharpe = np.sqrt(2 * np.log(n_trials)) * np.std(sharpe_values)

        # Adjust for skewness and kurtosis
        skew = self._skewness(sharpe_values)
        kurtosis = self._excess_kurtosis(sharpe_values)

        # Deflated Sharpe = Observed - E[max(S)] adjusted for non-normality
        n = len(sharpe_values)
        adjustment = (skew / 6) * (observed_sharpe ** 2 - expected_max_sharpe ** 2) / n
        adjustment += (kurtosis / 24) * (observed_sharpe ** 3 - expected_max_sharpe ** 3) / n

        deflated = observed_sharpe - expected_max_sharpe + adjustment
        return deflated
```

### 9.3 Parameter Sensitivity Analysis

```python
class ParameterSensitivityAnalyzer:
    """
    Tests strategy robustness to parameter changes.
    A robust strategy should degrade gracefully, not cliff-edge.
    """

    async def analyze(self, strategy_config: StrategyConfig,
                      base_params: dict,
                      test_start: datetime,
                      test_end: datetime) -> SensitivityReport:
        """
        Vary each parameter ±10%, ±20%, ±30% and measure performance impact.
        """
        results = {}

        for param_name, param_value in base_params.items():
            param_results = []

            for delta_pct in [-30, -20, -10, 0, +10, +20, +30]:
                # Create modified params
                modified = base_params.copy()
                modified[param_name] = param_value * (1 + delta_pct / 100)

                # Run backtest
                config = strategy_config.with_parameters(modified)
                result = await self.backtest_runner.run_single(
                    config, test_start, test_end
                )

                param_results.append(ParameterResult(
                    delta_pct=delta_pct,
                    param_value=modified[param_name],
                    sharpe=result.metrics.sharpe_ratio,
                    max_dd=result.metrics.max_drawdown,
                    win_rate=result.metrics.win_rate,
                    trade_count=result.metrics.total_trades
                ))

            # Calculate sensitivity score
            sharpes = [r.sharpe for r in param_results if r.delta_pct != 0]
            base_sharpe = [r.sharpe for r in param_results if r.delta_pct == 0][0]

            if base_sharpe > 0:
                sensitivity = np.std(sharpes) / base_sharpe
            else:
                sensitivity = float('inf')

            results[param_name] = ParameterSensitivity(
                results=param_results,
                sensitivity_score=sensitivity,
                robust=sensitivity < 0.30  # <30% variation = robust
            )

        return SensitivityReport(
            parameters=results,
            overall_robust=all(p.robust for p in results.values()),
            most_sensitive=max(results.items(), key=lambda x: x[1].sensitivity_score),
            least_sensitive=min(results.items(), key=lambda x: x[1].sensitivity_score)
        )
```

### 9.4 Overfitting Scorecard

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OVERFITTING SCORECARD                              │
│                                                                       │
│  Each test produces a score. Strategy must score ≥ 70/100 to pass.  │
│                                                                       │
│  TEST                           │ WEIGHT │ SCORE (0-10) │ WEIGHTED  │
│  ─────────────────────────────────────────────────────────────────── │
│  Walk-forward consistency        │  25%   │    /10       │   /2.5   │
│  (70%+ folds profitable)         │        │              │          │
│  CPCV deflated Sharpe            │  20%   │    /10       │   /2.0   │
│  (Deflated Sharpe > 1.0)         │        │              │          │
│  Train/Test performance gap      │  15%   │    /10       │   /1.5   │
│  (Gap < 20% = 10, Gap > 50% = 0)│        │              │          │
│  Parameter stability              │  15%   │    /10       │   /1.5   │
│  (No drift > 50% of range)       │        │              │          │
│  Parameter sensitivity            │  10%   │    /10       │   /1.0   │
│  (Robust to ±20% changes)        │        │              │          │
│  Cross-pair generalization        │  10%   │    /10       │   /1.0   │
│  (Works on 3+ pairs)             │        │              │          │
│  Parsimony (parameter count)      │   5%   │    /10       │   /0.5   │
│  (< 10 params = 10, > 30 = 0)    │        │              │          │
│  ─────────────────────────────────────────────────────────────────── │
│  TOTAL                                          │          │   /10   │
│                                                                       │
│  THRESHOLDS:                                                         │
│  ≥ 7.0: PASS — Strategy may proceed to OOS test                     │
│  5.0-6.9: MARGINAL — Requires investigation, may proceed with       │
│           additional safeguards                                      │
│  < 5.0: FAIL — Strategy is likely overfit. Do not deploy.           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 10. Monte Carlo Simulation for Robustness

### 10.1 Monte Carlo Methods

Monte Carlo simulation stress-tests strategy results by randomly resampling and perturbing trade sequences to estimate the range of possible outcomes.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MONTE CARLO SIMULATION METHODS                     │
│                                                                       │
│  METHOD 1: TRADE RESAMPLING (Bootstrap)                              │
│  • Randomly sample trades with replacement from the trade list       │
│  • Reconstruct equity curves from resampled sequences                │
│  • 10,000 simulations → distribution of Sharpe, max DD, final equity│
│  • Reveals: "What if the order of trades was different?"             │
│                                                                       │
│  METHOD 2: RETURN SHUFFLING                                          │
│  • Shuffle the order of periodic returns                             │
│  • Preserves return distribution but destroys autocorrelation        │
│  • 10,000 simulations → distribution of outcomes                     │
│  • Reveals: "Is performance dependent on return sequence?"           │
│                                                                       │
│  METHOD 3: TRADE REMOVAL (Leave-One-Out)                             │
│  • Remove each trade one at a time                                   │
│  • Re-run equity curve without that trade                            │
│  • Reveals: "Is performance dependent on any single trade?"          │
│                                                                       │
│  METHOD 4: WORST-CASE INSERTION                                      │
│  • Insert worst historical losing streaks at random points           │
│  • Test: "What if a 10-trade losing streak happened now?"            │
│  • Reveals: "Can the strategy survive extended drawdowns?"           │
│                                                                       │
│  METHOD 5: PARAMETER PERTURBATION                                    │
│  • Add random noise (±10%) to all parameters                        │
│  • Run 1,000 backtests with perturbed parameters                    │
│  • Reveals: "Is performance sensitive to parameter choices?"         │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.2 Monte Carlo Implementation

```python
class MonteCarloSimulator:
    """
    Monte Carlo simulation for strategy robustness testing.
    """

    def __init__(self, n_simulations: int = 10000, seed: int = 42):
        self.n_simulations = n_simulations
        self.rng = np.random.RandomState(seed)

    def trade_resampling(self, trades: list[SimulatedTrade],
                         initial_balance: float) -> MonteCarloResult:
        """
        Bootstrap resampling of trades.
        Generates distribution of possible outcomes.
        """
        trade_returns = [t.pnl_pct for t in trades]
        trade_r_multiples = [t.r_multiple for t in trades]

        final_equities = []
        max_drawdowns = []
        sharpes = []
        worst_drawdown_durations = []

        for _ in range(self.n_simulations):
            # Resample trades with replacement
            sampled_returns = self.rng.choice(
                trade_returns, size=len(trade_returns), replace=True
            )

            # Build equity curve
            equity = [initial_balance]
            for ret in sampled_returns:
                equity.append(equity[-1] * (1 + ret))

            # Compute metrics
            final_equities.append(equity[-1])
            max_drawdowns.append(self._max_drawdown(equity))
            sharpes.append(self._sharpe_from_returns(sampled_returns))

        return MonteCarloResult(
            method='trade_resampling',
            n_simulations=self.n_simulations,
            final_equity=self._distribution_stats(final_equities),
            max_drawdown=self._distribution_stats(max_drawdowns),
            sharpe_ratio=self._distribution_stats(sharpes),
            probability_of_profit=np.mean([e > initial_balance for e in final_equities]),
            probability_of_ruin=np.mean([e < initial_balance * 0.5 for e in final_equities]),
            var_95=np.percentile(final_equities, 5),
            cvar_95=np.mean([e for e in final_equities if e <= np.percentile(final_equities, 5)])
        )

    def worst_case_stress(self, trades: list[SimulatedTrade],
                          initial_balance: float,
                          max_streak_length: int = 10) -> MonteCarloResult:
        """
        Insert worst-case losing streaks at random points.
        Tests strategy resilience to extended drawdowns.
        """
        trade_returns = [t.pnl_pct for t in trades]
        losing_returns = [r for r in trade_returns if r < 0]

        if not losing_returns:
            return MonteCarloResult(method='worst_case_stress', n_simulations=0)

        final_equities = []
        max_drawdowns = []

        for _ in range(self.n_simulations):
            # Create a synthetic worst-case streak
            worst_streak = sorted(losing_returns)[:max_streak_length]

            # Insert at random position
            insert_pos = self.rng.randint(0, len(trade_returns))
            stressed_returns = (
                trade_returns[:insert_pos] +
                worst_streak +
                trade_returns[insert_pos:]
            )

            # Build equity curve
            equity = [initial_balance]
            for ret in stressed_returns:
                equity.append(equity[-1] * (1 + ret))

            final_equities.append(equity[-1])
            max_drawdowns.append(self._max_drawdown(equity))

        return MonteCarloResult(
            method='worst_case_stress',
            n_simulations=self.n_simulations,
            final_equity=self._distribution_stats(final_equities),
            max_drawdown=self._distribution_stats(max_drawdowns),
            probability_of_ruin=np.mean([e < initial_balance * 0.5 for e in final_equities])
        )

    def _distribution_stats(self, values: list[float]) -> dict:
        """Compute distribution statistics."""
        arr = np.array(values)
        return {
            'mean': np.mean(arr),
            'std': np.std(arr),
            'median': np.median(arr),
            'min': np.min(arr),
            'max': np.max(arr),
            'p5': np.percentile(arr, 5),
            'p25': np.percentile(arr, 25),
            'p75': np.percentile(arr, 75),
            'p95': np.percentile(arr, 95),
            'skew': float(self._skewness(arr.tolist())),
            'kurtosis': float(self._excess_kurtosis(arr.tolist()))
        }
```

### 10.3 Monte Carlo Acceptance Criteria

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MONTE CARLO ACCEPTANCE CRITERIA                    │
│                                                                       │
│  FROM TRADE RESAMPLING (10,000 simulations):                        │
│  □ Probability of profit > 70%                                      │
│  □ Probability of ruin (50%+ loss) < 5%                             │
│  □ 5th percentile final equity > initial balance (95% CI positive)  │
│  □ Median max drawdown < 25%                                        │
│  □ 95th percentile max drawdown < 40%                               │
│                                                                       │
│  FROM WORST-CASE STRESS (10,000 simulations):                       │
│  □ Strategy survives 10-trade losing streak without ruin            │
│  □ 95th percentile max drawdown < 50%                               │
│  □ Probability of ruin < 10% even under stress                      │
│                                                                       │
│  FROM PARAMETER PERTURBATION (1,000 simulations):                   │
│  □ Mean Sharpe across perturbations > 0.5                           │
│  □ No perturbation produces Sharpe < 0                              │
│  □ Std of Sharpe across perturbations < 0.5                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 11. Regime-Specific Backtesting

### 11.1 Regime Classification for Backtesting

The HMM regime detector (from `architecture_ml_pipeline.md`) classifies market conditions into three regimes. Backtesting evaluates performance **per regime**.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    REGIME-SPECIFIC BACKTESTING                        │
│                                                                       │
│  REGIME DEFINITIONS (from HMM):                                      │
│                                                                       │
│  REGIME 1: TRENDING BULL                                             │
│  • Characteristics: Higher highs, higher lows, positive momentum    │
│  • ADX > 25, positive 20-period return, low volatility              │
│  • Preferred strategies: Trend following, breakout, momentum        │
│                                                                       │
│  REGIME 2: TRENDING BEAR                                             │
│  • Characteristics: Lower highs, lower lows, negative momentum      │
│  • ADX > 25, negative 20-period return, elevated volatility         │
│  • Preferred strategies: Short momentum, breakdown                   │
│                                                                       │
│  REGIME 3: RANGING / CONSOLIDATION                                   │
│  • Characteristics: No clear trend, mean-reverting, low ADX         │
│  • ADX < 20, compressed ATR, oscillating price                      │
│  • Preferred strategies: Mean reversion, S/R bounce                 │
│                                                                       │
│  REGIME 4: HIGH VOLATILITY / CRISIS                                  │
│  • Characteristics: VIX spike, extreme ATR, gap moves               │
│  • ATR > 2x normal, spread widening, correlation breakdown          │
│  • Preferred strategies: Reduced exposure, wider stops              │
│                                                                       │
│  REGIME LABELING:                                                    │
│  • Each historical bar is labeled with its regime                   │
│  • Using the same HMM model that will be used in live trading       │
│  • Regime labels stored alongside backtest data                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 11.2 Per-Regime Performance Analysis

```python
class RegimeAnalyzer:
    """
    Analyzes backtest performance broken down by market regime.
    """

    def analyze_by_regime(self, trades: list[SimulatedTrade],
                          regime_labels: dict[datetime, str]) -> RegimeBreakdown:
        """Compute performance metrics for each regime."""

        regime_trades = {
            'trending_bull': [],
            'trending_bear': [],
            'ranging': [],
            'high_volatility': []
        }

        # Assign each trade to a regime based on entry time
        for trade in trades:
            regime = regime_labels.get(trade.entry_time, 'unknown')
            if regime in regime_trades:
                regime_trades[regime].append(trade)

        breakdown = {}
        for regime, regime_trade_list in regime_trades.items():
            if not regime_trade_list:
                continue

            metrics = PerformanceAnalyzer.compute_regime_metrics(regime_trade_list)
            breakdown[regime] = RegimeMetrics(
                trade_count=len(regime_trade_list),
                win_rate=metrics.win_rate,
                profit_factor=metrics.profit_factor,
                avg_r_multiple=metrics.avg_r_multiple,
                sharpe_ratio=metrics.sharpe_ratio,
                max_drawdown=metrics.max_drawdown,
                avg_trade_duration=metrics.avg_duration,
                total_pnl=metrics.total_pnl,
                pct_of_total_trades=len(regime_trade_list) / len(trades)
            )

        return RegimeBreakdown(
            regimes=breakdown,
            consistency=self._check_consistency(breakdown),
            best_regime=max(breakdown.items(), key=lambda x: x[1].sharpe_ratio),
            worst_regime=min(breakdown.items(), key=lambda x: x[1].sharpe_ratio),
            regime_adaptation_score=self._adaptation_score(breakdown)
        )

    def _check_consistency(self, breakdown: dict) -> bool:
        """Check if strategy is profitable in all regimes."""
        return all(m.profit_factor > 1.0 for m in breakdown.values() if m.trade_count >= 10)

    def _adaptation_score(self, breakdown: dict) -> float:
        """
        Score how well the strategy adapts to different regimes.
        1.0 = equally good in all regimes
        0.0 = only works in one regime
        """
        sharpes = [m.sharpe_ratio for m in breakdown.values() if m.trade_count >= 10]
        if len(sharpes) < 2:
            return 0.0
        # Coefficient of variation of Sharpe across regimes
        cv = np.std(sharpes) / (np.mean(sharpes) + 1e-8)
        return max(0, 1 - cv)
```

### 11.3 Regime Transition Testing

```python
class RegimeTransitionAnalyzer:
    """
    Tests strategy behavior during regime transitions.
    Transitions are the most dangerous periods for trend-following strategies.
    """

    def analyze_transitions(self, trades: list[SimulatedTrade],
                           regime_labels: dict[datetime, str]) -> TransitionAnalysis:
        """Analyze performance around regime transitions."""

        # Identify regime transitions
        transitions = []
        sorted_times = sorted(regime_labels.keys())
        for i in range(1, len(sorted_times)):
            prev_regime = regime_labels[sorted_times[i-1]]
            curr_regime = regime_labels[sorted_times[i]]
            if prev_regime != curr_regime:
                transitions.append(RegimeTransition(
                    time=sorted_times[i],
                    from_regime=prev_regime,
                    to_regime=curr_regime
                ))

        # Analyze trades around each transition
        transition_performance = []
        for trans in transitions:
            # Trades in the 24 hours before transition
            before_trades = [
                t for t in trades
                if trans.time - timedelta(hours=24) <= t.exit_time <= trans.time
            ]
            # Trades in the 24 hours after transition
            after_trades = [
                t for t in trades
                if trans.time <= t.entry_time <= trans.time + timedelta(hours=24)
            ]

            transition_performance.append(TransitionPerformance(
                transition=trans,
                trades_before=len(before_trades),
                pnl_before=sum(t.pnl for t in before_trades),
                trades_after=len(after_trades),
                pnl_after=sum(t.pnl for t in after_trades)
            ))

        return TransitionAnalysis(
            transitions=transitions,
            performance=transition_performance,
            avg_pnl_impact=np.mean([t.pnl_after - t.pnl_before
                                     for t in transition_performance]),
            transition_cost_pct=self._transition_cost(transition_performance)
        )
```

### 11.4 Regime Acceptance Criteria

```
┌─────────────────────────────────────────────────────────────────────┐
│                    REGIME ACCEPTANCE CRITERIA                         │
│                                                                       │
│  □ Strategy is profitable in at least 2 of 3 major regimes          │
│    (trending bull, trending bear, ranging)                           │
│                                                                       │
│  □ No regime produces a max drawdown > 35%                          │
│                                                                       │
│  □ Regime adaptation score > 0.5                                    │
│    (Not completely regime-dependent)                                 │
│                                                                       │
│  □ Transition cost < 5% of total P&L                                │
│    (Regime changes don't destroy profits)                            │
│                                                                       │
│  □ At least 10 trades per regime for statistical significance       │
│    (If not, note as "insufficient data" — not a failure)            │
│                                                                       │
│  □ High-volatility regime max drawdown < 20%                        │
│    (Must survive crises)                                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 12. Multi-Pair Portfolio Backtesting

### 12.1 Portfolio Backtesting Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MULTI-PAIR PORTFOLIO BACKTEST                      │
│                                                                       │
│  Instead of testing pairs individually, we test the full portfolio   │
│  to capture:                                                         │
│  • Cross-pair correlations                                           │
│  • Portfolio-level drawdown                                          │
│  • Aggregate risk exposure                                           │
│  • Diversification benefit                                           │
│  • Position sizing interactions                                      │
│                                                                       │
│  APPROACH:                                                           │
│  1. Replay all pairs simultaneously through the event replayer      │
│  2. Strategy engine processes all pairs with shared risk gate        │
│  3. Risk gate enforces portfolio-level limits                        │
│  4. Performance is measured at the portfolio level                   │
│                                                                       │
│  PORTFOLIO-LEVEL CONSTRAINTS (enforced by risk gate):                │
│  • Max 3 simultaneous positions                                      │
│  • Max 3% correlated exposure                                        │
│  • Max 5% daily loss                                                 │
│  • Max 15% total drawdown halt                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 12.2 Correlation Analysis

```python
class PortfolioCorrelationAnalyzer:
    """
    Analyzes cross-pair correlations and their impact on portfolio performance.
    """

    def analyze_correlations(self, pair_results: dict[str, BacktestResult]) -> CorrelationReport:
        """Compute pairwise correlations and portfolio metrics."""

        # Extract equity curves for each pair
        equity_curves = {
            pair: result.equity_curve
            for pair, result in pair_results.items()
        }

        # Compute pairwise return correlations
        returns = {
            pair: pd.Series(curve).pct_change().dropna()
            for pair, curve in equity_curves.items()
        }
        returns_df = pd.DataFrame(returns)
        correlation_matrix = returns_df.corr()

        # Find highly correlated pairs
        high_corr_pairs = []
        for i, pair1 in enumerate(returns_df.columns):
            for j, pair2 in enumerate(returns_df.columns):
                if i < j:
                    corr = correlation_matrix.loc[pair1, pair2]
                    if abs(corr) > 0.7:
                        high_corr_pairs.append((pair1, pair2, corr))

        # Compute portfolio-level metrics
        portfolio_returns = returns_df.mean(axis=1)  # Equal-weight portfolio
        portfolio_sharpe = PerformanceAnalyzer._sharpe_ratio(portfolio_returns.tolist())
        portfolio_max_dd = PerformanceAnalyzer._max_drawdown(
            (1 + portfolio_returns).cumprod().tolist()
        )

        # Diversification benefit
        avg_pair_sharpe = np.mean([
            result.metrics.sharpe_ratio for result in pair_results.values()
        ])
        diversification_ratio = portfolio_sharpe / avg_pair_sharpe if avg_pair_sharpe > 0 else 0

        return CorrelationReport(
            correlation_matrix=correlation_matrix,
            high_correlation_pairs=high_corr_pairs,
            portfolio_sharpe=portfolio_sharpe,
            portfolio_max_drawdown=portfolio_max_dd,
            diversification_ratio=diversification_ratio,
            avg_pairwise_correlation=correlation_matrix.values[
                np.triu_indices_from(correlation_matrix.values, k=1)
            ].mean()
        )
```

### 12.3 Portfolio Rebalancing Backtest

```python
class PortfolioBacktestRunner:
    """
    Runs portfolio-level backtests with cross-pair risk management.
    """

    async def run_portfolio_backtest(self, config: PortfolioBacktestConfig) -> PortfolioResult:
        """Run a complete portfolio backtest."""

        # 1. Initialize multi-pair event replayer
        replayer = MultiTimeframeReplayer(self.data_store)

        # 2. Initialize shared risk gate (portfolio-level)
        risk_gate = PortfolioRiskGate(config.risk_config)

        # 3. Initialize per-pair strategy engines
        engines = {}
        for symbol in config.symbols:
            engines[symbol] = AlphaStrategyEngine(
                event_source=None,  # Will be set by shared replayer
                config=config.strategy_config
            )

        # 4. Replay events across all pairs
        portfolio_trades = []
        portfolio_equity = [config.initial_balance]
        correlation_snapshots = []

        async for event in replayer.replay(
            symbols=config.symbols,
            timeframes=config.timeframes,
            start=config.start_date,
            end=config.end_date
        ):
            # Process event through appropriate strategy engine
            engine = engines[event.symbol]
            proposal = await engine.process_event(event)

            if proposal:
                # Apply portfolio-level risk checks
                approved = risk_gate.validate_portfolio(
                    proposal,
                    current_positions=risk_gate.open_positions,
                    portfolio_equity=portfolio_equity[-1]
                )

                if approved:
                    # Execute through simulator
                    result = await self.execution_sim.execute(approved)
                    portfolio_trades.append(result)

            # Update portfolio equity
            portfolio_equity.append(
                self.execution_sim.account.equity
            )

            # Periodically snapshot correlations
            if event.timestamp.hour == 0 and event.timestamp.minute == 0:
                correlation_snapshots.append(
                    self._compute_current_correlations(engines)
                )

        # 5. Compute portfolio metrics
        metrics = PerformanceAnalyzer.compute_all(
            portfolio_trades, self.execution_sim.account
        )

        # 6. Compute per-pair breakdown
        per_pair = {}
        for symbol in config.symbols:
            pair_trades = [t for t in portfolio_trades if t.symbol == symbol]
            per_pair[symbol] = PerformanceAnalyzer.compute_all(
                pair_trades, self.execution_sim.account
            )

        return PortfolioResult(
            portfolio_metrics=metrics,
            per_pair_metrics=per_pair,
            correlation_analysis=self.correlation_analyzer.analyze_correlations(per_pair),
            equity_curve=portfolio_equity,
            trade_log=portfolio_trades,
            risk_gate_stats=risk_gate.get_statistics()
        )
```

### 12.4 Portfolio Acceptance Criteria

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PORTFOLIO ACCEPTANCE CRITERIA                      │
│                                                                       │
│  □ Portfolio Sharpe > max(Individual Pair Sharpes) × 0.8            │
│    (Diversification doesn't hurt much)                               │
│                                                                       │
│  □ Portfolio max drawdown < 25%                                      │
│                                                                       │
│  □ No single pair contributes > 50% of total P&L                    │
│    (Not dependent on one pair)                                       │
│                                                                       │
│  □ Risk gate rejection rate 5-15%                                    │
│    (Healthy filtering, not too restrictive)                          │
│                                                                       │
│  □ Average pairwise correlation < 0.5                                │
│    (Genuine diversification)                                         │
│                                                                       │
│  □ Portfolio Sortino > Individual Pair Sortino (avg)                 │
│    (Downside risk is diversified)                                    │
│                                                                       │
│  □ Max correlated exposure never exceeds 3%                          │
│    (Risk gate works correctly)                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 13. Backtesting Reporting and Visualization

### 13.1 Report Structure

Every backtest produces a comprehensive report in Markdown and HTML formats.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BACKTEST REPORT STRUCTURE                          │
│                                                                       │
│  1. EXECUTIVE SUMMARY                                                │
│     • Strategy name, version, test period                            │
│     • Pass/Fail verdict with overfitting scorecard                   │
│     • Key metrics: Sharpe, max DD, win rate, profit factor          │
│     • Monte Carlo confidence intervals                               │
│                                                                       │
│  2. EQUITY CURVE                                                     │
│     • Line chart of equity over time                                 │
│     • Drawdown overlay (inverted area chart)                         │
│     • Benchmark comparison (buy & hold, random)                      │
│     • Monthly returns heatmap                                        │
│                                                                       │
│  3. TRADE ANALYSIS                                                   │
│     • Trade distribution (histogram of R-multiples)                  │
│     • Win/loss streak analysis                                       │
│     • Trade duration distribution                                    │
│     • P&L by signal source                                           │
│     • P&L by session (Asian, London, NY, Overlap)                    │
│     • P&L by regime                                                 │
│                                                                       │
│  4. RISK ANALYSIS                                                    │
│     • Drawdown chart with recovery time                              │
│     • Monte Carlo distribution (final equity, max DD)                │
│     • Value at Risk (95%, 99%)                                      │
│     • Conditional VaR                                                │
│     • Worst-case stress test results                                 │
│                                                                       │
│  5. WALK-FORWARD RESULTS                                             │
│     • Per-fold metrics table                                         │
│     • Fold-by-fold Sharpe chart                                      │
│     • Parameter stability across folds                               │
│     • Train vs Test performance comparison                           │
│                                                                       │
│  6. OVERFITTING ANALYSIS                                             │
│     • CPCV deflated Sharpe                                           │
│     • Parameter sensitivity heatmap                                  │
│     • Cross-pair generalization results                              │
│     • Overfitting scorecard                                          │
│                                                                       │
│  7. REGIME ANALYSIS                                                  │
│     • Per-regime metrics table                                       │
│     • Regime timeline with equity overlay                            │
│     • Transition cost analysis                                       │
│                                                                       │
│  8. PORTFOLIO ANALYSIS (if multi-pair)                               │
│     • Per-pair contribution                                          │
│     • Correlation matrix heatmap                                     │
│     • Diversification benefit                                        │
│     • Risk gate statistics                                           │
│                                                                       │
│  9. EXECUTION QUALITY                                                │
│     • Total commission, slippage, swap costs                         │
│     • Cost as % of P&L                                              │
│     • Slippage distribution                                          │
│                                                                       │
│  10. DATA QUALITY                                                    │
│      • Data gaps found and filled                                    │
│      • Data quality score                                            │
│      • Snapshot checksum for reproducibility                         │
│                                                                       │
│  11. RECOMMENDATION                                                  │
│      • Deploy / Do Not Deploy / Investigate Further                  │
│      • Specific concerns and mitigations                             │
│      • Suggested parameter adjustments (if marginal)                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 13.2 Visualization Components

```python
class BacktestReporter:
    """
    Generates comprehensive backtest reports with visualizations.
    """

    def generate_report(self, result: BacktestResult) -> str:
        """Generate a complete Markdown backtest report."""

        report = []

        # 1. Executive Summary
        report.append(self._executive_summary(result))

        # 2. Equity Curve
        report.append(self._equity_curve_section(result))

        # 3. Trade Analysis
        report.append(self._trade_analysis_section(result))

        # 4. Risk Analysis
        report.append(self._risk_analysis_section(result))

        # 5. Walk-Forward Results
        if result.walk_forward:
            report.append(self._walk_forward_section(result))

        # 6. Overfitting Analysis
        report.append(self._overfitting_section(result))

        # 7. Regime Analysis
        report.append(self._regime_section(result))

        # 8. Portfolio Analysis
        if result.portfolio:
            report.append(self._portfolio_section(result))

        # 9. Execution Quality
        report.append(self._execution_quality_section(result))

        # 10. Data Quality
        report.append(self._data_quality_section(result))

        # 11. Recommendation
        report.append(self._recommendation_section(result))

        return '\n'.join(report)

    def _executive_summary(self, result: BacktestResult) -> str:
        m = result.metrics
        verdict = "✅ PASS" if result.passed else "❌ FAIL"

        return f"""
## 1. Executive Summary

| Field | Value |
|-------|-------|
| **Strategy** | {result.config.strategy_name} |
| **Version** | {result.config.version} |
| **Test Period** | {result.config.start_date.date()} → {result.config.end_date.date()} |
| **Symbols** | {', '.join(result.config.symbols)} |
| **Verdict** | {verdict} |
| **Overfitting Score** | {result.overfitting_score:.1f}/10 |

### Key Metrics

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Sharpe Ratio | {m.sharpe_ratio:.2f} | > 1.0 | {'✅' if m.sharpe_ratio > 1.0 else '❌'} |
| Sortino Ratio | {m.sortino_ratio:.2f} | > 1.5 | {'✅' if m.sortino_ratio > 1.5 else '❌'} |
| Max Drawdown | {m.max_drawdown_pct:.1%} | < 20% | {'✅' if m.max_drawdown_pct < 0.20 else '❌'} |
| Win Rate | {m.win_rate:.1%} | > 45% | {'✅' if m.win_rate > 0.45 else '❌'} |
| Profit Factor | {m.profit_factor:.2f} | > 1.3 | {'✅' if m.profit_factor > 1.3 else '❌'} |
| Total Return | {m.total_return_pct:.1%} | > 0 | {'✅' if m.total_return_pct > 0 else '❌'} |
| Total Trades | {m.total_trades} | > 30 | {'✅' if m.total_trades > 30 else '❌'} |
| Avg R-Multiple | {m.avg_r_multiple:.2f} | > 0.3 | {'✅' if m.avg_r_multiple > 0.3 else '❌'} |

### Monte Carlo Confidence (10,000 simulations)

| Metric | 5th Percentile | Median | 95th Percentile |
|--------|---------------|--------|-----------------|
| Final Equity | ${result.monte_carlo.final_equity['p5']:,.0f} | ${result.monte_carlo.final_equity['median']:,.0f} | ${result.monte_carlo.final_equity['p95']:,.0f} |
| Max Drawdown | {result.monte_carlo.max_drawdown['p5']:.1%} | {result.monte_carlo.max_drawdown['median']:.1%} | {result.monte_carlo.max_drawdown['p95']:.1%} |
| Probability of Profit | {result.monte_carlo.probability_of_profit:.1%} | | |
| Probability of Ruin | {result.monte_carlo.probability_of_ruin:.1%} | | |
"""
```

### 13.3 Equity Curve Visualization (ASCII)

For terminal-based reports, the equity curve is rendered as ASCII art:

```python
    def _ascii_equity_curve(self, equity_curve: list[float],
                            width: int = 80, height: int = 20) -> str:
        """Render equity curve as ASCII art for terminal reports."""
        min_eq = min(equity_curve)
        max_eq = max(equity_curve)
        eq_range = max_eq - min_eq

        # Downsample to fit width
        step = max(1, len(equity_curve) // width)
        sampled = equity_curve[::step][:width]

        lines = []
        for row in range(height, -1, -1):
            threshold = min_eq + (eq_range * row / height)
            line = ''
            for eq in sampled:
                if eq >= threshold:
                    line += '█'
                else:
                    line += ' '
            lines.append(f'{threshold:>10.0f} │{line}')

        lines.append(' ' * 11 + '└' + '─' * len(sampled))
        return '\n'.join(lines)
```

### 13.4 Monthly Returns Heatmap

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MONTHLY RETURNS HEATMAP                            │
│                                                                       │
│         Jan    Feb    Mar    Apr    May    Jun    Jul    Aug    ...  │
│  2021   +2.1%  -0.8%  +3.2%  +1.5%  -1.2%  +2.8%  +0.9%  +1.7%   │
│  2022   +1.8%  +2.5%  -0.3%  +1.9%  -2.1%  +3.4%  +1.2%  -0.5%   │
│  2023   +0.5%  +1.8%  +2.7%  -0.9%  +1.3%  +2.1%  +0.8%  +1.5%   │
│  2024   +2.3%  -1.5%  +1.9%  +3.1%  +0.7%  -0.4%  +2.2%  +1.8%   │
│  2025   +1.1%  +2.8%  -0.6%  +1.4%  +2.5%  +1.9%  +0.3%  +2.1%   │
│                                                                       │
│  Color coding:  🟢 > 2%   🟡 0-2%   🔴 < 0%                       │
│                                                                       │
│  Annual totals:                                                       │
│  2021: +10.2%  2022: +7.9%  2023: +9.8%  2024: +9.6%  2025: +11.5%│
└─────────────────────────────────────────────────────────────────────┘
```

### 13.5 R-Multiple Distribution

```
┌─────────────────────────────────────────────────────────────────────┐
│                    R-MULTIPLE DISTRIBUTION                            │
│                                                                       │
│  R-Multiple │ Count │ Bar                                            │
│  ───────────┼───────┼────────────────────────────────────────────── │
│     < -3R   │     2 │ ██                                             │
│    -3 to -2R│     5 │ █████                                          │
│    -2 to -1R│    18 │ ██████████████████                             │
│    -1 to  0R│    35 │ ███████████████████████████████████            │
│     0 to  1R│    42 │ ██████████████████████████████████████████     │
│     1 to  2R│    28 │ ████████████████████████████                   │
│     2 to  3R│    12 │ ████████████                                   │
│     3 to  5R│     8 │ ████████                                       │
│      > 5R   │     3 │ ███                                            │
│                                                                       │
│  Statistics:                                                          │
│  Mean R: +0.85  │  Median R: +0.62  │  Std R: 1.45                  │
│  Best R: +6.2   │  Worst R: -3.8    │  Skew: +0.35                  │
│                                                                       │
│  ✅ Positive expectancy: Mean R > 0                                  │
│  ✅ Right-skewed: More large winners than large losers               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 14. Implementation Roadmap

### Phase 1: Foundation ($7 capital, ~1 week)

| Component | Implementation | Effort |
|-----------|---------------|--------|
| EventSource abstraction | Abstract base class + live/backtest implementations | 1 day |
| BacktestEventSource | Historical candle replay from TimescaleDB | 1 day |
| ExecutionSimulator | Basic spread + slippage + commission model | 1 day |
| BacktestRunner | Orchestrate single backtest run | 1 day |
| PerformanceAnalyzer | All core metrics (Sharpe, Sortino, DD, win rate, PF) | 1 day |
| Basic report | Markdown report with key metrics | 1 day |
| **Total Phase 1** | | **~6 days** |

**Phase 1 delivers:** Run a backtest on historical data with realistic execution costs. Same code as live trading. Basic performance report.

### Phase 2: Validation (~$100 capital, ~2 weeks)

| Component | Implementation | Effort |
|-----------|---------------|--------|
| WalkForwardAnalyzer | Walk-forward framework with configurable windows | 2 days |
| WalkForwardOptimizer | Optuna-based parameter optimization per fold | 1 day |
| OutOfSampleTester | OOS holdout test with acceptance criteria | 1 day |
| MonteCarloSimulator | Bootstrap, stress test, parameter perturbation | 2 days |
| RegimeAnalyzer | Per-regime performance breakdown | 1 day |
| DataQualityValidator | Gap detection, OHLC validation, quality scoring | 1 day |
| Data snapshot system | Reproducible data snapshots with checksums | 1 day |
| Enhanced report | Walk-forward + Monte Carlo + regime sections | 2 days |
| **Total Phase 2** | | **~11 days** |

**Phase 2 delivers:** Walk-forward validation, Monte Carlo robustness testing, regime-specific analysis, OOS testing. Full overfitting defense.

### Phase 3: Institutional (~$1K capital, ~2 weeks)

| Component | Implementation | Effort |
|-----------|---------------|--------|
| CombinatorialPurgedCV | CPCV with deflated Sharpe ratio | 2 days |
| ParameterSensitivityAnalyzer | Parameter perturbation and sensitivity heatmaps | 1 day |
| PortfolioBacktestRunner | Multi-pair portfolio backtesting | 2 days |
| PortfolioCorrelationAnalyzer | Cross-pair correlation and diversification analysis | 1 day |
| RegimeTransitionAnalyzer | Regime transition cost analysis | 1 day |
| Overfitting scorecard | Automated overfitting scoring (7 tests, 100-point scale) | 1 day |
| HTML report | Interactive HTML report with charts (Plotly) | 2 days |
| Backtest CLI | Command-line interface for running backtests | 1 day |
| **Total Phase 3** | | **~11 days** |

**Phase 3 delivers:** CPCV, portfolio-level testing, interactive HTML reports, CLI tool. Full institutional-grade backtest validation.

### Phase 4: Advanced (~$10K+ capital, ~3 weeks)

| Component | Implementation | Effort |
|-----------|---------------|--------|
| Tick-level backtest | Replay actual tick data for sub-candle accuracy | 3 days |
| Custom slippage models | Order book depth-based slippage | 2 days |
| Multi-broker simulation | Test across different broker conditions | 2 days |
| Synthetic data generation | GAN-based synthetic market data for stress testing | 3 days |
| Backtest dashboard | Grafana dashboard for backtest monitoring | 2 days |
| Automated retraining pipeline | Walk-forward → retrain → backtest → deploy automation | 3 days |
| GPU-accelerated backtest | Parallel backtest across parameter combinations | 2 days |
| **Total Phase 4** | | **~17 days** |

---

## Summary

### Architecture at a Glance

```
HISTORICAL DATA (TimescaleDB)
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│  DATA VALIDATOR  │────→│  DATA SNAPSHOT   │
│  (gaps, quality) │     │  (reproducibility)│
└──────────────────┘     └──────────────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│  EVENT REPLAYER  │────→│  MULTI-TF MERGER │
│  (candle replay) │     │  (chronological)  │
└──────────────────┘     └──────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│         STRATEGY ENGINE (SAME CODE)       │
│  Steps 1-16 — identical to live trading   │
└──────────────────────┬───────────────────┘
                       │
                       ▼
┌──────────────────┐     ┌──────────────────┐
│  EXECUTION SIM   │────→│  PERFORMANCE     │
│  (spread, slip,  │     │  ANALYZER        │
│   commission)    │     │  (all metrics)   │
└──────────────────┘     └──────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│         VALIDATION FRAMEWORK              │
│                                           │
│  Walk-Forward → OOS Test → Monte Carlo   │
│  → Regime Analysis → CPCV → Report       │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│         OVERFITTING SCORECARD             │
│  7 tests, 100-point scale                │
│  ≥ 70: PASS → proceed to OOS            │
│  < 50: FAIL → do not deploy              │
└──────────────────────────────────────────┘
```

### Deployment Pipeline

```
Strategy Development
        │
        ▼
┌──────────────┐
│  BACKTEST    │ ← Historical data, realistic costs
│  (Phase 1)   │
└──────┬───────┘
       │ Pass basic metrics
       ▼
┌──────────────┐
│  WALK-FORWARD│ ← Temporal validation, no leakage
│  (Phase 2)   │
└──────┬───────┘
       │ 70%+ folds profitable
       ▼
┌──────────────┐
│  OOS TEST    │ ← Held-out data, one-shot
│  (Phase 2)   │
└──────┬───────┘
       │ All acceptance criteria met
       ▼
┌──────────────┐
│  MONTE CARLO │ ← 10,000 simulations
│  (Phase 2)   │
└──────┬───────┘
       │ 95% CI positive
       ▼
┌──────────────┐
│  CPCV +      │ ← Deflated Sharpe, sensitivity
│  OVERFITTING │
│  (Phase 3)   │
└──────┬───────┘
       │ Score ≥ 70/100
       ▼
┌──────────────┐
│  PORTFOLIO   │ ← Multi-pair, correlation
│  TEST        │
│  (Phase 3)   │
└──────┬───────┘
       │ Portfolio Sharpe > individual
       ▼
┌──────────────┐
│  SHADOW LIVE │ ← Paper trading, 2+ weeks
│  (Manual)    │
└──────┬───────┘
       │ Matches backtest expectations
       ▼
┌──────────────┐
│  LIVE        │ ← Real capital, gradual ramp
│  DEPLOYMENT  │    10% → 25% → 50% → 100%
└──────────────┘
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Same code for backtest and live | EventSource abstraction | Eliminates backtest/live divergence. Zero code duplication. |
| Walk-forward as primary validation | Temporal CV with purge gap | Only valid method for time-series. Random CV leaks future data. |
| CPCV for overfitting detection | Deflated Sharpe ratio | Accounts for multiple testing bias. Industry standard (López de Prado). |
| Monte Carlo over analytical | 10,000 bootstrap simulations | Handles non-normal distributions. Reveals tail risks. |
| Regime-specific analysis | Per-regime metrics | Strategy must work across market conditions, not just one regime. |
| Portfolio-level testing | Multi-pair backtest | Captures correlations, portfolio drawdown, diversification benefit. |
| Data snapshots for reproducibility | Checksummed data records | Every backtest is exactly reproducible. No "it worked on my data". |
| Overfitting scorecard | 7 tests, 100-point scale | Objective, quantitative go/no-go decision for deployment. |
| Phase-gated implementation | 4 phases over ~6 weeks | Start simple, add complexity as capital and data justify it. |

---

*Document generated by Alpha Stack Backtesting Architect*
*Version 1.0 — 2026-07-11*
*Status: Architecture Design Complete — Ready for Implementation Review*
