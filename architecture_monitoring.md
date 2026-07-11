# Alpha Stack — Monitoring Architecture

> **Author:** System Monitoring Architect
> **Date:** 2026-07-11
> **Status:** Architecture Design — Pre-Implementation
> **Dependencies:** `architecture_deployment.md`, `architecture_database.md`, `architecture_multi_agent.md`, `architecture_data.md`, `research_scalability.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Monitoring Philosophy & Design Principles](#2-monitoring-philosophy--design-principles)
3. [System Health Monitoring](#3-system-health-monitoring)
4. [Trading Engine Monitoring](#4-trading-engine-monitoring)
5. [Broker Connection Monitoring](#5-broker-connection-monitoring)
6. [Agent Monitoring](#6-agent-monitoring)
7. [Data Pipeline Monitoring](#7-data-pipeline-monitoring)
8. [Database Monitoring](#8-database-monitoring)
9. [Alerting Rules and Escalation](#9-alerting-rules-and-escalation)
10. [Dashboard Design (Grafana)](#10-dashboard-design-grafana)
11. [Log Aggregation](#11-log-aggregation)
12. [Performance Metrics and SLAs](#12-performance-metrics-and-slas)
13. [Monitoring Stack Deployment](#13-monitoring-stack-deployment)
14. [Implementation Roadmap](#14-implementation-roadmap)

---

## 1. Executive Summary

Alpha Stack's monitoring architecture provides **end-to-end observability** across infrastructure, application, trading, and data layers. The system is designed for a solo developer operating on a $5–50/month VPS, with a clear scaling path to multi-region institutional monitoring.

### Monitoring Stack

| Component | Technology | Purpose | Phase |
|-----------|-----------|---------|-------|
| **Metrics** | Prometheus + exporters | Time-series metrics collection | Phase 1+ |
| **Dashboards** | Grafana | Visualization, alerting UI | Phase 1+ |
| **Logs** | Loki + Promtail | Structured log aggregation | Phase 2+ |
| **Tracing** | OpenTelemetry (optional) | Request/decision tracing | Phase 4+ |
| **Alerting** | Prometheus Alertmanager + Telegram | Alert routing and notification | Phase 1+ |
| **Uptime** | Blackbox Exporter | External endpoint probing | Phase 2+ |
| **Profiling** | py-spy / pyinstrument | CPU profiling for hot paths | Phase 3+ |

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Metrics format | Prometheus exposition | Industry standard, free, extensive exporters |
| Log format | JSON structured logs | Machine-parseable, queryable in Loki |
| Alert routing | Telegram (primary), Email (critical) | Solo developer — mobile-first alerting |
| Dashboard platform | Grafana | Free, integrates Prometheus + Loki natively |
| Metric cardinality | Bounded labels, no per-tick metrics | Prevents Prometheus OOM on high-frequency data |
| Trading metrics | Custom application-level | No off-the-shelf trading metrics exist |

---

## 2. Monitoring Philosophy & Design Principles

### 2.1 The Four Golden Signals (Adapted for Trading)

| Signal | Trading System Interpretation | Why It Matters |
|--------|-------------------------------|----------------|
| **Latency** | Order-to-fill time, signal-to-decision time, API response time | Slippage = money lost |
| **Traffic** | Ticks/sec, orders/min, signals/min, API requests/sec | Capacity planning, anomaly detection |
| **Errors** | Order rejections, broker disconnections, agent failures, data gaps | Direct financial impact |
| **Saturation** | CPU, memory, disk, connection pools, Redis memory | Prevent cascading failures |

### 2.2 Monitoring Tiers

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MONITORING TIER ARCHITECTURE                       │
│                                                                      │
│  TIER 1: INFRASTRUCTURE (Prometheus + Node Exporter)                │
│  ├── CPU, Memory, Disk, Network                                      │
│  ├── Docker container health                                         │
│  └── OS-level metrics (file descriptors, swap, load average)         │
│                                                                      │
│  TIER 2: SERVICES (Application /metrics endpoints)                   │
│  ├── HTTP request rates, latency, errors                             │
│  ├── Database connection pool stats                                  │
│  ├── Redis hit/miss rates                                            │
│  └── Internal queue depths                                           │
│                                                                      │
│  TIER 3: TRADING (Custom Prometheus metrics)                         │
│  ├── Order lifecycle (placed → filled → rejected)                    │
│  ├── Broker connectivity and latency                                 │
│  ├── Agent health and signal throughput                              │
│  └── Data pipeline freshness and gaps                                │
│                                                                      │
│  TIER 4: BUSINESS (Grafana + PostgreSQL queries)                     │
│  ├── P&L curves, win rates, Sharpe ratios                            │
│  ├── Strategy attribution                                            │
│  ├── Risk utilization vs limits                                      │
│  └── Capital efficiency metrics                                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 Cardinality Rules

High-frequency trading data creates cardinality explosion risks. Strict rules:

| Rule | Implementation |
|------|---------------|
| **No per-tick metrics** | Aggregate over 15s scrape interval |
| **Bounded label values** | Symbol list is fixed (enum, not free-text) |
| **No dynamic agent IDs in labels** | Use agent_type (e.g., `smc_agent`), not instance IDs |
| **Histogram buckets optimized** | Custom buckets for trading latencies (1ms–10s) |
| **Metric lifecycle** | Deprecated metrics removed within 2 versions |

---

## 3. System Health Monitoring

### 3.1 Infrastructure Metrics (Node Exporter)

All hosts run `node_exporter` exposing OS-level metrics to Prometheus.

| Metric | Source | Alert Threshold | Description |
|--------|--------|----------------|-------------|
| `node_cpu_seconds_total` | Node Exporter | >85% sustained 10m | CPU utilization |
| `node_memory_MemAvailable_bytes` | Node Exporter | <15% available | Memory pressure |
| `node_filesystem_avail_bytes` | Node Exporter | <20% / <10% (critical) | Disk space |
| `node_filesystem_files_avail` | Node Exporter | <10% inodes | Inode exhaustion |
| `node_network_receive_bytes_total` | Node Exporter | — (baseline) | Network throughput |
| `node_network_transmit_errs_total` | Node Exporter | >0 sustained | Network errors |
| `node_load1` | Node Exporter | >2× CPU count | Load average |
| `node_vmstat_pswpin` | Node Exporter | >0 sustained | Swap activity (bad for latency) |
| `node_filefd_allocated` | Node Exporter | >80% max | File descriptor usage |

### 3.2 Docker Container Metrics (cAdvisor)

| Metric | Source | Alert Threshold | Description |
|--------|--------|----------------|-------------|
| `container_cpu_usage_seconds_total` | cAdvisor | Per-container limits | Container CPU |
| `container_memory_usage_bytes` | cAdvisor | >80% of limit | Container memory |
| `container_fs_usage_bytes` | cAdvisor | — | Container disk usage |
| `container_network_receive_bytes_total` | cAdvisor | — | Container network I/O |
| `container_restart_count` | cAdvisor | >0 in 1h | Unexpected restarts |
| `container_oom_events_total` | cAdvisor | >0 | OOM kills |

### 3.3 Health Check Endpoints

Every service exposes a `/health` endpoint:

```python
# Standard health check response format
{
    "status": "healthy",           # healthy | degraded | unhealthy
    "version": "1.2.3",
    "uptime_seconds": 3600,
    "checks": {
        "database": {"status": "ok", "latency_ms": 2},
        "redis": {"status": "ok", "latency_ms": 1},
        "broker": {"status": "ok", "latency_ms": 45},
        "model": {"status": "ok", "latency_ms": 120}
    },
    "timestamp": "2026-07-11T13:00:00Z"
}
```

Blackbox Exporter probes these endpoints externally:

```yaml
# config/prometheus/blackbox.yml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: [200]
      follow_redirects: true
      preferred_ip_protocol: "ip4"
      fail_if_body_not_matches_regexp:
        - '"status":\s*"healthy"'
  tcp_connect:
    prober: tcp
    timeout: 3s
```

### 3.4 System Health Prometheus Queries

```promql
# CPU utilization (per host)
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory utilization
(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100

# Disk utilization (root partition)
(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100

# Container restart rate (last 1h)
increase(container_restart_count[1h])

# Container OOM events
increase(container_oom_events_total[1h])
```

---

## 4. Trading Engine Monitoring

### 4.1 Order Lifecycle Metrics

The trading engine exposes the following custom Prometheus metrics:

```python
# services/trading-engine/src/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Summary

# ─── Order Lifecycle ──────────────────────────────────────────
orders_total = Counter(
    'as_orders_total',
    'Total orders processed',
    ['symbol', 'side', 'order_type', 'status']  # status: filled, rejected, cancelled, error
)

order_latency_seconds = Histogram(
    'as_order_latency_seconds',
    'Time from order submission to fill confirmation',
    ['symbol', 'broker_id', 'order_type'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

order_slippage_pips = Histogram(
    'as_order_slippage_pips',
    'Slippage in pips at fill',
    ['symbol', 'side', 'broker_id'],
    buckets=[0, 0.5, 1, 2, 3, 5, 10, 20, 50]
)

# ─── Position Metrics ─────────────────────────────────────────
open_positions = Gauge(
    'as_open_positions',
    'Number of currently open positions',
    ['symbol', 'side', 'strategy_id', 'broker_id']
)

position_pnl_usd = Gauge(
    'as_position_pnl_usd',
    'Unrealized P&L per position',
    ['symbol', 'side', 'strategy_id']
)

position_duration_seconds = Gauge(
    'as_position_duration_seconds',
    'How long position has been open',
    ['symbol', 'side']
)

# ─── Account Metrics ──────────────────────────────────────────
account_balance_usd = Gauge(
    'as_account_balance_usd',
    'Account balance',
    ['account_id', 'broker_id']
)

account_equity_usd = Gauge(
    'as_account_equity_usd',
    'Account equity (balance + unrealized P&L)',
    ['account_id', 'broker_id']
)

account_drawdown_pct = Gauge(
    'as_account_drawdown_pct',
    'Current drawdown from high-water mark',
    ['account_id']
)

account_daily_pnl_usd = Gauge(
    'as_account_daily_pnl_usd',
    'Today\'s realized + unrealized P&L',
    ['account_id']
)

account_margin_utilization_pct = Gauge(
    'as_account_margin_utilization_pct',
    'Margin used / margin available',
    ['account_id']
)

# ─── Risk Metrics ─────────────────────────────────────────────
risk_utilization = Gauge(
    'as_risk_utilization',
    'Risk limit utilization (0.0 to 1.0)',
    ['limit_type']  # per_trade, daily_loss, max_positions, drawdown
)

circuit_breaker_state = Gauge(
    'as_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['breaker_id']
)

# ─── Strategy Metrics ─────────────────────────────────────────
strategy_signals_total = Counter(
    'as_strategy_signals_total',
    'Total signals generated by strategy',
    ['strategy_id', 'symbol', 'direction']
)

strategy_confluence_score = Histogram(
    'as_strategy_confluence_score',
    'Confluence score distribution',
    ['strategy_id'],
    buckets=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
)

strategy_win_rate = Gauge(
    'as_strategy_win_rate',
    'Rolling win rate (last 50 trades)',
    ['strategy_id']
)

strategy_sharpe_ratio = Gauge(
    'as_strategy_sharpe_ratio',
    'Rolling Sharpe ratio (30-day)',
    ['strategy_id']
)
```

### 4.2 Signal-to-Execution Pipeline Latency

```
┌──────────────────────────────────────────────────────────────────┐
│  LATENCY WATERFALL — Signal to Fill                               │
│                                                                   │
│  Signal Agent    ▓▓▓░░░░░░░░░░░░░░░░░░░░░░░  ~300ms (LLM)      │
│  Aggregator      ▓░░░░░░░░░░░░░░░░░░░░░░░░░  ~50ms              │
│  Risk Gate       ▓░░░░░░░░░░░░░░░░░░░░░░░░░  ~10ms              │
│  Execution       ▓▓░░░░░░░░░░░░░░░░░░░░░░░░  ~100ms             │
│  Broker Fill     ▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░  ~500ms (network)   │
│                                                                   │
│  Total: ~960ms (target: <2s for market orders)                    │
│  p99 target: <5s                                                  │
└──────────────────────────────────────────────────────────────────┘
```

Each stage is instrumented with start/end timestamps:

```python
class PipelineLatencyTracker:
    """Track latency through each stage of the trading pipeline."""

    STAGES = [
        'signal_generation',
        'signal_aggregation',
        'risk_validation',
        'entry_calculation',
        'order_submission',
        'broker_fill',
    ]

    def __init__(self):
        self.stage_latency = Histogram(
            'as_pipeline_stage_seconds',
            'Latency per pipeline stage',
            ['stage', 'symbol'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
        )
        self.total_latency = Histogram(
            'as_pipeline_total_seconds',
            'Total signal-to-fill latency',
            ['symbol', 'order_type'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )

    def record_stage(self, stage: str, symbol: str, duration_s: float):
        self.stage_latency.labels(stage=stage, symbol=symbol).observe(duration_s)

    def record_total(self, symbol: str, order_type: str, duration_s: float):
        self.total_latency.labels(symbol=symbol, order_type=order_type).observe(duration_s)
```

### 4.3 Trading Engine Health Summary

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Order fill rate | >95% | 90–95% | <90% |
| Order rejection rate | <2% | 2–5% | >5% |
| Order latency (p95) | <1s | 1–3s | >3s |
| Slippage (avg) | <1 pip | 1–3 pips | >3 pips |
| Open positions | Within limits | At limit | Over limit |
| Drawdown | <5% | 5–10% | >10% |
| Circuit breaker | Closed | Half-open | Open |

---

## 5. Broker Connection Monitoring

### 5.1 Broker Health Metrics

```python
# services/trading-engine/src/broker_metrics.py

broker_connection_status = Gauge(
    'as_broker_connection_status',
    'Broker connection status (1=connected, 0=disconnected)',
    ['broker_id', 'broker_type']
)

broker_connection_uptime_seconds = Gauge(
    'as_broker_uptime_seconds',
    'Seconds since last broker connection/reconnection',
    ['broker_id']
)

broker_reconnection_total = Counter(
    'as_broker_reconnections_total',
    'Total broker reconnections',
    ['broker_id', 'reason']  # reason: timeout, error, heartbeat_fail, network
)

broker_latency_seconds = Histogram(
    'as_broker_latency_seconds',
    'Round-trip latency to broker API',
    ['broker_id', 'operation'],  # operation: tick, order, balance, position
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

broker_api_errors_total = Counter(
    'as_broker_api_errors_total',
    'Broker API errors',
    ['broker_id', 'error_code', 'operation']
)

broker_rate_limit_remaining = Gauge(
    'as_broker_rate_limit_remaining',
    'Remaining API rate limit',
    ['broker_id']
)

broker_last_tick_timestamp = Gauge(
    'as_broker_last_tick_timestamp',
    'Unix timestamp of last tick received from broker',
    ['broker_id', 'symbol']
)

broker_account_sync_lag_seconds = Gauge(
    'as_broker_account_sync_lag',
    'Seconds since last successful account sync',
    ['broker_id']
)
```

### 5.2 Connection State Machine

```
┌──────────┐    connect()    ┌───────────┐    heartbeat_fail    ┌──────────┐
│DISCONNECTED│──────────────▶│ CONNECTED │────────────────────▶│DEGRADED  │
└──────────┘                └───────────┘                     └──────────┘
     ▲                           │                                 │
     │                           │ reconnect()                     │ timeout
     │                           ▼                                 ▼
     │                      ┌───────────┐                    ┌──────────┐
     └──────────────────────│RECONNECTING│◀──────────────────│   DOWN   │
            success()       └───────────┘   attempt()        └──────────┘
                                                                │
                                                           after 5 failures
                                                                ▼
                                                          ┌──────────┐
                                                          │ FAILOVER │
                                                          └──────────┘
```

### 5.3 Broker-Specific Monitoring

| Broker | Health Check | Critical Metric | Failover |
|--------|-------------|-----------------|----------|
| **MT5 (FXPesa)** | `account_info()` call | `as_broker_connection_status{broker_id="fxpesa"}` | CCXT Binance (crypto only) |
| **Binance** | `fetch_balance()` call | `as_broker_rate_limit_remaining{broker_id="binance"}` | Bybit via CCXT |
| **Bybit** | `fetch_balance()` call | `as_broker_rate_limit_remaining{broker_id="bybit"}` | Binance |

### 5.4 Reconnection Strategy Monitoring

```python
class BrokerReconnectionMonitor:
    """Track reconnection behavior and alert on anomalies."""

    def __init__(self):
        self.reconnect_attempts = Counter(
            'as_broker_reconnect_attempts_total',
            'Reconnection attempts',
            ['broker_id', 'attempt_number']
        )
        self.reconnect_duration = Histogram(
            'as_broker_reconnect_duration_seconds',
            'Time to successfully reconnect',
            ['broker_id'],
            buckets=[0.5, 1, 2, 5, 10, 30, 60, 120]
        )
        self.consecutive_failures = Gauge(
            'as_broker_consecutive_failures',
            'Consecutive connection failures',
            ['broker_id']
        )
```

---

## 6. Agent Monitoring

### 6.1 Agent Health Metrics

```python
# Multi-agent system monitoring metrics

agent_status = Gauge(
    'as_agent_status',
    'Agent status (0=stopped, 1=running, 2=degraded, 3=failed)',
    ['agent_id', 'agent_type']
)

agent_uptime_seconds = Gauge(
    'as_agent_uptime_seconds',
    'Agent uptime in seconds',
    ['agent_id', 'agent_type']
)

agent_heartbeat_timestamp = Gauge(
    'as_agent_heartbeat_timestamp',
    'Unix timestamp of last agent heartbeat',
    ['agent_id', 'agent_type']
)

agent_signals_produced_total = Counter(
    'as_agent_signals_total',
    'Total signals produced by agent',
    ['agent_type', 'symbol', 'direction']
)

agent_inference_duration_seconds = Histogram(
    'as_agent_inference_seconds',
    'LLM inference time per agent call',
    ['agent_type', 'model'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

agent_errors_total = Counter(
    'as_agent_errors_total',
    'Agent errors',
    ['agent_type', 'error_type']  # error_type: timeout, model_error, data_error, crash
)

agent_memory_usage_bytes = Gauge(
    'as_agent_memory_bytes',
    'Agent process memory usage',
    ['agent_id', 'agent_type']
)

agent_message_throughput = Counter(
    'as_agent_messages_total',
    'Messages processed by agent',
    ['agent_type', 'channel', 'direction']  # direction: sent, received
)

agent_queue_depth = Gauge(
    'as_agent_queue_depth',
    'Pending messages in agent queue',
    ['agent_type', 'channel']
)

agent_loop_iterations = Counter(
    'as_agent_loop_iterations_total',
    'Agent loop iterations (ReAct, deliberation, etc.)',
    ['agent_type', 'loop_type']
)

agent_confluence_contributions = Counter(
    'as_agent_confluence_contributions_total',
    'Times agent voted in consensus',
    ['agent_type', 'vote_direction']  # direction: bullish, bearish, neutral
)
```

### 6.2 Agent Health Dashboard Grid

| Agent | Status | Uptime | Signals/hr | Avg Inference | Errors/hr | Memory |
|-------|--------|--------|------------|---------------|-----------|--------|
| Orchestrator | 🟢 | 4h 23m | — | — | 0 | 128MB |
| Fundamental | 🟢 | 4h 23m | 2 | 1.2s | 0 | 256MB |
| Structure | 🟢 | 4h 23m | 6 | 0.4s | 0 | 192MB |
| Liquidity | 🟢 | 4h 23m | 12 | 0.05s | 0 | 128MB |
| SMC | 🟢 | 4h 23m | 8 | 0.3s | 0 | 192MB |
| Momentum | 🟢 | 4h 23m | 8 | 0.02s | 0 | 96MB |
| Candlestick | 🟢 | 4h 23m | 6 | 0.01s | 0 | 96MB |
| Signal Aggregator | 🟢 | 4h 23m | 4 | 0.1s | 0 | 128MB |
| Entry | 🟡 | 4h 23m | 2 | 0.2s | 1 | 128MB |
| Risk Gate | 🟢 | 4h 23m | 2 | 0.01s | 0 | 64MB |
| Execution | 🟢 | 4h 23m | 2 | 0.05s | 0 | 96MB |
| Monitor | 🟢 | 4h 23m | — | — | 0 | 64MB |

### 6.3 Agent Failure Detection

```python
class AgentHealthChecker:
    """Detect agent failures and trigger recovery."""

    HEARTBEAT_TIMEOUT_WARN = 120    # 2 minutes without heartbeat → warn
    HEARTBEAT_TIMEOUT_FAIL = 300    # 5 minutes → restart
    MAX_RESTARTS_PER_10MIN = 3      # More than 3 restarts → escalate

    def check(self, agent_id: str, last_heartbeat: float) -> str:
        age = time.time() - last_heartbeat

        if age > self.HEARTBEAT_TIMEOUT_FAIL:
            return 'failed'
        elif age > self.HEARTBEAT_TIMEOUT_WARN:
            return 'degraded'
        else:
            return 'healthy'
```

---

## 7. Data Pipeline Monitoring

### 7.1 Data Freshness Metrics

```python
# Data pipeline monitoring metrics

data_last_update_timestamp = Gauge(
    'as_data_last_update_timestamp',
    'Unix timestamp of last data update',
    ['symbol', 'source', 'data_type']  # data_type: tick, candle, orderbook, news
)

data_staleness_seconds = Gauge(
    'as_data_staleness_seconds',
    'Seconds since last data update',
    ['symbol', 'source', 'data_type']
)

data_ingestion_rate = Counter(
    'as_data_ingestion_total',
    'Total data points ingested',
    ['symbol', 'source', 'data_type']
)

data_ingestion_latency_seconds = Histogram(
    'as_data_ingestion_latency_seconds',
    'Latency from source timestamp to DB write',
    ['symbol', 'source'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0]
)

data_validation_errors_total = Counter(
    'as_data_validation_errors_total',
    'Data validation failures',
    ['symbol', 'source', 'error_type']  # error_type: stale, gap, invalid_ohlc, outlier
)

data_gap_detected = Gauge(
    'as_data_gap_detected',
    'Data gap detected (1=gap, 0=no gap)',
    ['symbol', 'timeframe']
)

data_candle_completeness = Gauge(
    'as_data_candle_completeness',
    'Candle completeness ratio (0.0 to 1.0)',
    ['symbol', 'timeframe']
)

# Redis stream metrics
stream_length = Gauge(
    'as_stream_length',
    'Redis stream length',
    ['stream_name']
)

stream_consumer_lag = Gauge(
    'as_stream_consumer_lag',
    'Consumer group lag in messages',
    ['stream_name', 'consumer_group']
)

stream_last_message_timestamp = Gauge(
    'as_stream_last_message_timestamp',
    'Timestamp of last message in stream',
    ['stream_name']
)
```

### 7.2 Data Quality Checks

```python
class DataQualityMonitor:
    """Automated data quality checks run on every candle close."""

    def check_ohlc_validity(self, candle: dict) -> bool:
        """Validate OHLC relationships."""
        return (
            candle['low'] <= candle['high'] and
            candle['low'] <= candle['open'] and
            candle['low'] <= candle['close'] and
            candle['high'] >= candle['open'] and
            candle['high'] >= candle['close'] and
            candle['volume'] >= 0
        )

    def check_gap(self, symbol: str, timeframe: str, current_time: datetime) -> float:
        """Detect gaps in candle series."""
        expected_interval = self._tf_to_delta(timeframe)
        last_candle_time = self._get_last_candle_time(symbol, timeframe)
        gap = (current_time - last_candle_time) / expected_interval
        return gap  # >1.5 means gap detected

    def check_outlier(self, symbol: str, price: float, lookback: int = 100) -> bool:
        """Detect price outliers (>5σ from recent mean)."""
        recent = self._get_recent_closes(symbol, lookback)
        mean = np.mean(recent)
        std = np.std(recent)
        return abs(price - mean) > 5 * std
```

### 7.3 Data Pipeline Health Matrix

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Tick staleness | <5s | 5–30s | >30s |
| Candle completeness | >99% | 95–99% | <95% |
| Gap detection | No gaps | 1–2 gaps/hour | >2 gaps/hour |
| Validation error rate | <0.1% | 0.1–1% | >1% |
| Stream consumer lag | <100 | 100–1000 | >1000 |
| Ingestion latency (p95) | <50ms | 50–200ms | >200ms |

### 7.4 Source-Specific Monitoring

| Source | Health Check | Key Metric | Failover Trigger |
|--------|-------------|------------|------------------|
| **MT5 Ticks** | WebSocket ping | `as_data_staleness_seconds{source="mt5"}` | >10s stale |
| **Binance WS** | Ping/pong | `as_data_staleness_seconds{source="binance"}` | >5s stale |
| **Finnhub News** | HTTP 200 check | `as_data_last_update_timestamp{source="finnhub"}` | >30min stale |
| **Economic Calendar** | Daily refresh check | `as_data_last_update_timestamp{data_type="calendar"}` | >24h stale |
| **On-Chain** | API health | `as_data_ingestion_rate{source="defilama"}` | >1h stale |

---

## 8. Database Monitoring

### 8.1 PostgreSQL Metrics (postgres_exporter)

| Metric | Source | Alert Threshold | Description |
|--------|--------|----------------|-------------|
| `pg_up` | Exporter | =0 for 1m | PostgreSQL is running |
| `pg_stat_activity_count` | Exporter | >80 | Active connections |
| `pg_stat_database_tup_fetched` | Exporter | — | Rows fetched |
| `pg_stat_database_tup_inserted` | Exporter | — | Rows inserted |
| `pg_stat_database_conflicts` | Exporter | >0 | Replication conflicts |
| `pg_stat_replication_lag` | Exporter | >30s | Replica lag |
| `pg_database_size_bytes` | Exporter | >80% disk | Database size |
| `pg_stat_user_tables_n_dead_tup` | Exporter | >100K | Dead tuples (needs vacuum) |
| `pg_stat_user_tables_last_vacuum` | Exporter | >7 days | Vacuum freshness |

### 8.2 TimescaleDB-Specific Metrics

```sql
-- Custom queries for postgres_exporter

-- Hypertable chunk count
SELECT hypertable_name, count(*) as chunk_count
FROM timescaledb_information.chunks
GROUP BY hypertable_name;

-- Compression ratio
SELECT
    hypertable_name,
    pg_size_before_compression,
    pg_size_after_compression,
    (pg_size_before_compression::float / pg_size_after_compression) as compression_ratio
FROM timescaledb_information.compressed_chunk_stats;

-- Continuous aggregate refresh lag
SELECT
    view_name,
    last_run_duration,
    last_refresh,
    EXTRACT(EPOCH FROM (NOW() - last_refresh)) as lag_seconds
FROM timescaledb_information.continuous_aggregate_stats;

-- Retention policy execution
SELECT
    application_name,
    last_run_success,
    last_run_duration,
    total_runs,
    total_failures
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_retention';
```

### 8.3 Query Performance Monitoring

```sql
-- Enable pg_stat_statements (in postgresql.conf)
-- shared_preload_libraries = 'pg_stat_statements'

-- Slow query detection (exported as custom metric)
SELECT
    queryid,
    LEFT(query, 100) as query_preview,
    calls,
    round(mean_exec_time::numeric, 2) as avg_ms,
    round(max_exec_time::numeric, 2) as max_ms,
    rows
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY total_exec_time DESC
LIMIT 20;

-- Table bloat detection
SELECT
    schemaname,
    relname,
    n_dead_tup,
    n_live_tup,
    round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 2) as dead_pct,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC;

-- Index usage audit
SELECT
    indexrelname,
    idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;
```

### 8.4 Redis Metrics (redis_exporter)

| Metric | Source | Alert Threshold | Description |
|--------|--------|----------------|-------------|
| `redis_up` | Exporter | =0 for 1m | Redis is running |
| `redis_memory_used_bytes` | Exporter | >80% maxmemory | Memory usage |
| `redis_connected_clients` | Exporter | >100 | Connected clients |
| `redis_blocked_clients` | Exporter | >10 | Blocked clients (BLPOP etc.) |
| `redis_ops_per_sec` | Exporter | — | Operations per second |
| `redis_keyspace_hits` | Exporter | — | Cache hit rate |
| `redis_keyspace_misses` | Exporter | — | Cache miss rate |
| `redis_latest_fork_usec` | Exporter | >100ms | BGSAVE/BGREWRITEAOF time |
| `redis_rdb_last_save_time` | Exporter | >1h | Last RDB snapshot |
| `redis_connected_slaves` | Exporter | — | Replica count |

### 8.5 Database Health Summary

```promql
# PostgreSQL connection utilization
pg_stat_activity_count / pg_settings_max_connections * 100

# Cache hit ratio (should be >99%)
pg_stat_database_blks_hit{datname="alphastack"} /
(pg_stat_database_blks_hit{datname="alphastack"} + pg_stat_database_blks_read{datname="alphastack"}) * 100

# Redis memory utilization
redis_memory_used_bytes / redis_memory_max_bytes * 100

# Redis cache hit rate
rate(redis_keyspace_hits[5m]) / (rate(redis_keyspace_hits[5m]) + rate(redis_keyspace_misses[5m])) * 100
```

---

## 9. Alerting Rules and Escalation

### 9.1 Alert Severity Levels

| Severity | Response Time | Notification | Examples |
|----------|--------------|--------------|----------|
| **CRITICAL** | Immediate | Telegram + Email + SMS | Trading halted, broker down, data corruption, max drawdown |
| **WARNING** | <15 min | Telegram | High error rate, degraded performance, disk >80% |
| **INFO** | <1 hour | Grafana only | Service restart, configuration change, scheduled maintenance |

### 9.2 Alertmanager Configuration

```yaml
# config/prometheus/alertmanager.yml
global:
  resolve_timeout: 5m
  smtp_from: 'alerts@alphastack.app'
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_auth_username: '${SMTP_USER}'
  smtp_auth_password: '${SMTP_PASSWORD}'

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'telegram-default'

  routes:
    # Critical alerts → Telegram + Email
    - match:
        severity: critical
      receiver: 'telegram-critical'
      group_wait: 5s
      repeat_interval: 30m
      continue: true

    - match:
        severity: critical
      receiver: 'email-critical'
      group_wait: 5m
      repeat_interval: 2h

    # Trading alerts → dedicated Telegram channel
    - match:
        category: trading
      receiver: 'telegram-trading'
      group_wait: 5s
      repeat_interval: 15m

    # Warning → Telegram only
    - match:
        severity: warning
      receiver: 'telegram-default'
      repeat_interval: 4h

receivers:
  - name: 'telegram-default'
    telegram_configs:
      - bot_token: '${TELEGRAM_BOT_TOKEN}'
        chat_id: '${TELEGRAM_CHAT_ID}'
        parse_mode: 'HTML'
        message: |
          🔔 <b>{{ .GroupLabels.alertname }}</b>
          {{ range .Alerts }}
          Status: {{ .Status }}
          Summary: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          {{ end }}

  - name: 'telegram-critical'
    telegram_configs:
      - bot_token: '${TELEGRAM_BOT_TOKEN}'
        chat_id: '${TELEGRAM_CHAT_ID}'
        parse_mode: 'HTML'
        message: |
          🚨 <b>CRITICAL: {{ .GroupLabels.alertname }}</b>
          {{ range .Alerts }}
          Summary: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          {{ end }}

  - name: 'telegram-trading'
    telegram_configs:
      - bot_token: '${TELEGRAM_BOT_TOKEN}'
        chat_id: '${TELEGRAM_TRADING_CHAT_ID}'
        parse_mode: 'HTML'

  - name: 'email-critical'
    email_configs:
      - to: '${ALERT_EMAIL}'
        subject: '🚨 Alpha Stack CRITICAL: {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Labels: {{ .Labels }}
          {{ end }}

inhibit_rules:
  # If broker is down, suppress individual connection warnings
  - source_match:
      alertname: BrokerDisconnected
    target_match_re:
      alertname: (BrokerLatencyHigh|BrokerRateLimitLow)
    equal: ['broker_id']

  # If trading halted, suppress individual order failures
  - source_match:
      alertname: TradingHalted
    target_match_re:
      alertname: (OrderRejectionSpike|HighSlippage)
    equal: []
```

### 9.3 Complete Alert Rules

```yaml
# config/prometheus/alerts.yml

groups:
  # ═══════════════════════════════════════════════════════════
  #  INFRASTRUCTURE ALERTS
  # ═══════════════════════════════════════════════════════════
  - name: infrastructure
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
          category: infrastructure
        annotations:
          summary: "{{ $labels.job }} is down"
          description: "{{ $labels.job }} on {{ $labels.instance }} has been unreachable for >1 minute."

      - alert: HighCPU
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85
        for: 10m
        labels:
          severity: warning
          category: infrastructure
        annotations:
          summary: "High CPU on {{ $labels.instance }}"
          description: "CPU usage is {{ $value | printf \"%.1f\" }}% (threshold: 85%)."

      - alert: HighMemory
        expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 85
        for: 5m
        labels:
          severity: warning
          category: infrastructure
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | printf \"%.1f\" }}% (threshold: 85%)."

      - alert: DiskSpaceWarning
        expr: (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 > 80
        for: 5m
        labels:
          severity: warning
          category: infrastructure
        annotations:
          summary: "Disk space low"
          description: "Disk usage is {{ $value | printf \"%.1f\" }}%."

      - alert: DiskSpaceCritical
        expr: (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 > 90
        for: 5m
        labels:
          severity: critical
          category: infrastructure
        annotations:
          summary: "Disk space critically low"
          description: "Disk usage is {{ $value | printf \"%.1f\" }}%. Immediate action required."

      - alert: SwapActive
        expr: rate(node_vmstat_pswpin[5m]) > 0
        for: 5m
        labels:
          severity: warning
          category: infrastructure
        annotations:
          summary: "Swap activity detected"
          description: "System is swapping — this causes latency spikes in trading."

      - alert: ContainerRestarting
        expr: increase(container_restart_count[1h]) > 0
        for: 0m
        labels:
          severity: warning
          category: infrastructure
        annotations:
          summary: "{{ $labels.name }} restarted"
          description: "Container {{ $labels.name }} restarted {{ $value }} time(s) in the last hour."

      - alert: ContainerOOM
        expr: increase(container_oom_events_total[1h]) > 0
        for: 0m
        labels:
          severity: critical
          category: infrastructure
        annotations:
          summary: "{{ $labels.name }} OOM killed"
          description: "Container {{ $labels.name }} was killed due to out-of-memory."

  # ═══════════════════════════════════════════════════════════
  #  TRADING ENGINE ALERTS
  # ═══════════════════════════════════════════════════════════
  - name: trading_engine
    rules:
      - alert: BrokerDisconnected
        expr: as_broker_connection_status == 0
        for: 2m
        labels:
          severity: critical
          category: trading
        annotations:
          summary: "Broker {{ $labels.broker_id }} disconnected"
          description: "{{ $labels.broker_type }} broker {{ $labels.broker_id }} has been disconnected for >2 minutes."

      - alert: BrokerLatencyHigh
        expr: histogram_quantile(0.95, rate(as_broker_latency_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
          category: trading
        annotations:
          summary: "Broker latency high"
          description: "P95 latency to {{ $labels.broker_id }} is {{ $value | printf \"%.2f\" }}s (threshold: 2s)."

      - alert: HighOrderRejectionRate
        expr: |
          rate(as_orders_total{status="rejected"}[15m])
          / rate(as_orders_total[15m]) > 0.1
        for: 10m
        labels:
          severity: warning
          category: trading
        annotations:
          summary: "High order rejection rate"
          description: "{{ $value | humanizePercentage }} of orders rejected in last 15min."

      - alert: HighSlippage
        expr: histogram_quantile(0.95, rate(as_order_slippage_pips_bucket[30m])) > 5
        for: 30m
        labels:
          severity: warning
          category: trading
        annotations:
          summary: "High slippage detected"
          description: "P95 slippage is {{ $value | printf \"%.1f\" }} pips (threshold: 5)."

      - alert: TradingHalted
        expr: as_circuit_breaker_state{breaker_id="main"} == 1
        for: 1m
        labels:
          severity: critical
          category: trading
        annotations:
          summary: "Trading halted — circuit breaker open"
          description: "Main circuit breaker has been tripped. No new trades will execute."

      - alert: DrawdownWarning
        expr: as_account_drawdown_pct > 10
        for: 5m
        labels:
          severity: warning
          category: trading
        annotations:
          summary: "Account drawdown elevated"
          description: "Drawdown is {{ $value | printf \"%.1f\" }}% (warning threshold: 10%)."

      - alert: DrawdownCritical
        expr: as_account_drawdown_pct > 15
        for: 1m
        labels:
          severity: critical
          category: trading
        annotations:
          summary: "CRITICAL drawdown — consider halting"
          description: "Drawdown is {{ $value | printf \"%.1f\" }}%. Max safe threshold: 15%."

      - alert: MarginWarning
        expr: as_account_margin_utilization_pct > 70
        for: 5m
        labels:
          severity: warning
          category: trading
        annotations:
          summary: "Margin utilization high"
          description: "Margin usage is {{ $value | printf \"%.1f\" }}% (threshold: 70%)."

      - alert: PipelineLatencyHigh
        expr: histogram_quantile(0.95, rate(as_pipeline_total_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
          category: trading
        annotations:
          summary: "Trading pipeline latency high"
          description: "P95 signal-to-fill latency is {{ $value | printf \"%.1f\" }}s (target: <5s)."

      - alert: DailyLossLimit
        expr: abs(as_account_daily_pnl_usd) > as_account_balance_usd * 0.05
        for: 1m
        labels:
          severity: critical
          category: trading
        annotations:
          summary: "Daily loss limit approaching"
          description: "Daily P&L is {{ $value }} — approaching 5% daily loss limit."

  # ═══════════════════════════════════════════════════════════
  #  AGENT ALERTS
  # ═══════════════════════════════════════════════════════════
  - name: agents
    rules:
      - alert: AgentDown
        expr: as_agent_status == 3
        for: 2m
        labels:
          severity: critical
          category: agents
        annotations:
          summary: "{{ $labels.agent_type }} agent failed"
          description: "Agent {{ $labels.agent_id }} ({{ $labels.agent_type }}) has failed."

      - alert: AgentHeartbeatStale
        expr: time() - as_agent_heartbeat_timestamp > 120
        for: 2m
        labels:
          severity: warning
          category: agents
        annotations:
          summary: "{{ $labels.agent_type }} heartbeat stale"
          description: "No heartbeat from {{ $labels.agent_id }} for {{ $value | printf \"%.0f\" }}s."

      - alert: AgentInferenceSlow
        expr: histogram_quantile(0.95, rate(as_agent_inference_seconds_bucket[5m])) > 10
        for: 10m
        labels:
          severity: warning
          category: agents
        annotations:
          summary: "{{ $labels.agent_type }} inference slow"
          description: "P95 inference time is {{ $value | printf \"%.1f\" }}s (threshold: 10s)."

      - alert: AgentErrorRateHigh
        expr: rate(as_agent_errors_total[15m]) > 0.1
        for: 10m
        labels:
          severity: warning
          category: agents
        annotations:
          summary: "{{ $labels.agent_type }} error rate high"
          description: "{{ $labels.agent_type }} has {{ $value | printf \"%.2f\" }} errors/sec."

      - alert: AgentMemoryLeak
        expr: as_agent_memory_bytes > 1073741824  # 1GB
        for: 5m
        labels:
          severity: warning
          category: agents
        annotations:
          summary: "{{ $labels.agent_type }} high memory"
          description: "Agent using {{ $value | humanize1024 }} — possible memory leak."

      - alert: AgentQueueBacklog
        expr: as_agent_queue_depth > 100
        for: 5m
        labels:
          severity: warning
          category: agents
        annotations:
          summary: "{{ $labels.agent_type }} queue backlog"
          description: "{{ $value }} messages pending in {{ $labels.channel }} queue."

  # ═══════════════════════════════════════════════════════════
  #  DATA PIPELINE ALERTS
  # ═══════════════════════════════════════════════════════════
  - name: data_pipeline
    rules:
      - alert: DataIngestionStale
        expr: as_data_staleness_seconds > 30
        for: 2m
        labels:
          severity: warning
          category: data
        annotations:
          summary: "Data stale for {{ $labels.symbol }}"
          description: "{{ $labels.data_type }} from {{ $labels.source }} is {{ $value | printf \"%.0f\" }}s stale."

      - alert: DataGapDetected
        expr: as_data_gap_detected == 1
        for: 1m
        labels:
          severity: warning
          category: data
        annotations:
          summary: "Data gap on {{ $labels.symbol }} {{ $labels.timeframe }}"
          description: "Missing candles detected in {{ $labels.symbol }} {{ $labels.timeframe }} series."

      - alert: DataValidationErrors
        expr: rate(as_data_validation_errors_total[15m]) > 0.05
        for: 10m
        labels:
          severity: warning
          category: data
        annotations:
          summary: "Data validation errors on {{ $labels.symbol }}"
          description: "{{ $labels.error_type }} errors from {{ $labels.source }} at {{ $value }}/sec."

      - alert: StreamConsumerLag
        expr: as_stream_consumer_lag > 1000
        for: 5m
        labels:
          severity: warning
          category: data
        annotations:
          summary: "Stream consumer lagging"
          description: "{{ $labels.consumer_group }} is {{ $value }} messages behind on {{ $labels.stream_name }}."

      - alert: CandleCompletenessLow
        expr: as_data_candle_completeness < 0.95
        for: 15m
        labels:
          severity: warning
          category: data
        annotations:
          summary: "Candle completeness low for {{ $labels.symbol }}"
          description: "Only {{ $value | humanizePercentage }} of expected candles present."

  # ═══════════════════════════════════════════════════════════
  #  DATABASE ALERTS
  # ═══════════════════════════════════════════════════════════
  - name: database
    rules:
      - alert: PostgreSQLDown
        expr: pg_up == 0
        for: 1m
        labels:
          severity: critical
          category: database
        annotations:
          summary: "PostgreSQL is down"
          description: "PostgreSQL instance is unreachable."

      - alert: HighConnectionCount
        expr: pg_stat_activity_count > 80
        for: 5m
        labels:
          severity: warning
          category: database
        annotations:
          summary: "High PostgreSQL connections"
          description: "{{ $value }} active connections (threshold: 80)."

      - alert: SlowQueries
        expr: pg_stat_activity_max_tx_duration{datname="alphastack"} > 30
        for: 5m
        labels:
          severity: warning
          category: database
        annotations:
          summary: "Long-running query detected"
          description: "Longest transaction running for {{ $value | printf \"%.0f\" }}s."

      - alert: DeadTuplesHigh
        expr: pg_stat_user_tables_n_dead_tup > 100000
        for: 1h
        labels:
          severity: warning
          category: database
        annotations:
          summary: "High dead tuples on {{ $labels.relname }}"
          description: "{{ $value }} dead tuples — vacuum needed."

      - alert: DatabaseSizeGrowth
        expr: pg_database_size_bytes{datname="alphastack"} > 53687091200  # 50GB
        for: 1h
        labels:
          severity: warning
          category: database
        annotations:
          summary: "Database size exceeds 50GB"
          description: "Database is {{ $value | humanize1024 }}. Review retention policies."

      - alert: RedisDown
        expr: redis_up == 0
        for: 1m
        labels:
          severity: critical
          category: database
        annotations:
          summary: "Redis is down"
          description: "Redis instance is unreachable. Trading state will be lost."

      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.85
        for: 5m
        labels:
          severity: warning
          category: database
        annotations:
          summary: "Redis memory high"
          description: "Redis using {{ $value | humanizePercentage }} of maxmemory."

      - alert: RedisCacheHitRateLow
        expr: |
          rate(redis_keyspace_hits[5m]) /
          (rate(redis_keyspace_hits[5m]) + rate(redis_keyspace_misses[5m])) < 0.9
        for: 15m
        labels:
          severity: warning
          category: database
        annotations:
          summary: "Redis cache hit rate low"
          description: "Cache hit rate is {{ $value | humanizePercentage }} (target: >90%)."

  # ═══════════════════════════════════════════════════════════
  #  BACKUP ALERTS
  # ═══════════════════════════════════════════════════════════
  - name: backups
    rules:
      - alert: BackupFailed
        expr: time() - as_backup_last_success_timestamp > 172800  # 2 days
        for: 1h
        labels:
          severity: critical
          category: backup
        annotations:
          summary: "Backup has not run in 2+ days"
          description: "Last successful backup was {{ $value | humanizeDuration }} ago."

      - alert: BackupSizeAnomaly
        expr: |
          abs(as_backup_size_bytes - as_backup_size_bytes offset 1d)
          / as_backup_size_bytes offset 1d > 0.5
        for: 1h
        labels:
          severity: warning
          category: backup
        annotations:
          summary: "Backup size anomaly"
          description: "Backup size changed by >50% — possible data growth or corruption."
```

### 9.4 Alert Escalation Matrix

```
┌────────────────────────────────────────────────────────────────────────┐
│                    ALERT ESCALATION FLOW                                │
│                                                                        │
│  Alert Fires                                                           │
│      │                                                                 │
│      ▼                                                                 │
│  ┌──────────┐    Telegram notification                                 │
│  │ WARNING  │──────────────────────────────────┐                       │
│  └──────────┘                                  │                       │
│      │                                         ▼                       │
│      │                                  ┌──────────────┐               │
│      │                                  │ Acked in 15m?│               │
│      │                                  └──────┬───────┘               │
│      │                                    Yes  │  No                   │
│      │                                         │    │                  │
│      │                                         ▼    ▼                  │
│      │                                    Resend  Escalate             │
│      │                                    (15m)  to Email              │
│      │                                                                 │
│  ┌──────────┐    Telegram + Email immediately                          │
│  │ CRITICAL │──────────────────────────────────────────┐               │
│  └──────────┘                                          │               │
│      │                                                 ▼               │
│      │                                          ┌──────────────┐       │
│      │                                          │ Acked in 5m? │       │
│      │                                          └──────┬───────┘       │
│      │                                            Yes  │  No          │
│      │                                                 │    │         │
│      │                                                 ▼    ▼         │
│      │                                            Resend  Auto-action │
│      │                                            (5m)   (if defined) │
│      │                                                                 │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │  TRADING CRITICAL: Broker down, drawdown >15%, halt          │     │
│  │  → Immediate Telegram + Email + Auto-halt trading            │     │
│  │  → NO escalation timeout — auto-action is immediate          │     │
│  └──────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Dashboard Design (Grafana)

### 10.1 Dashboard Architecture

```
GRAFANA DASHBOARD HIERARCHY

├── 📊 Alpha Stack — Overview (home)
│   ├── Service health grid
│   ├── System resources (CPU, memory, disk)
│   ├── Alert summary
│   └── Quick links to detailed dashboards
│
├── 💹 Trading Performance
│   ├── Equity curve
│   ├── Daily P&L heatmap
│   ├── Win rate by strategy
│   ├── Open positions table
│   ├── Order fill statistics
│   └── Sharpe/drawdown gauges
│
├── 🔌 Broker & Execution
│   ├── Broker connection status
│   ├── Order latency waterfall
│   ├── Slippage distribution
│   ├── Fill rate over time
│   └── Rate limit utilization
│
├── 🤖 Agent Health
│   ├── Agent status grid
│   ├── Inference latency by agent
│   ├── Signal throughput
│   ├── Error rates
│   ├── Memory usage
│   └── Queue depths
│
├── 📡 Data Pipeline
│   ├── Data freshness heatmap
│   ├── Ingestion rates by source
│   ├── Gap detection timeline
│   ├── Validation error rates
│   └── Stream consumer lag
│
├── 🗄️ Database
│   ├── PostgreSQL overview
│   │   ├── Connections, query rate, cache hit ratio
│   │   ├── Table sizes, dead tuples
│   │   └── Slow query log
│   ├── TimescaleDB
│   │   ├── Hypertable sizes, chunk counts
│   │   ├── Compression ratios
│   │   └── Continuous aggregate lag
│   └── Redis
│       ├── Memory, clients, ops/sec
│       ├── Key distribution
│       └── Hit/miss rates
│
├── 🖥️ Infrastructure
│   ├── CPU, memory, disk per host
│   ├── Docker container stats
│   ├── Network I/O
│   └── System load
│
└── 📋 Logs (Grafana + Loki)
    ├── Application logs (filterable)
    ├── Error log timeline
    └── Structured log search
```

### 10.2 Overview Dashboard Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ALPHA STACK — SYSTEM OVERVIEW                    Last 6h | 24h | 7d   │
├─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬────────────┤
│  CPU    │ Memory  │  Disk   │ Uptime  │ Brokers │ Agents  │ Data Age   │
│  23%    │ 61%     │ 45%     │ 14d 3h  │ 2/2 🟢 │ 14/14🟢│ <1s        │
│ [gauge] │ [gauge] │ [gauge] │ [text]  │ [grid]  │ [grid]  │ [gauge]    │
├─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴────────────┤
│  SERVICE HEALTH                                                         │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │ core-api │ trading- │ market-  │ ai-      │ postgres │ redis    │   │
│  │ 🟢 UP   │ engine   │ data     │ inferen. │ 🟢 UP   │ 🟢 UP   │   │
│  │ 2ms     │ 🟢 UP   │ 🟢 UP   │ 🟢 UP   │ 3 conn  │ 45MB    │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│  TRADING SUMMARY                                                        │
│  ┌──────────────┬──────────────┬──────────────┬──────────────────────┐ │
│  │ Daily P&L    │ Open Pos     │ Win Rate     │ Drawdown             │ │
│  │ +$12.34      │ 2            │ 62.5%        │ 3.2%                 │ │
│  │ [sparkline]  │ [table]      │ [gauge]      │ [progress bar]       │ │
│  └──────────────┴──────────────┴──────────────┴──────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│  RECENT ALERTS                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 14:23  ⚠️  Broker latency spike (FXPesa) — resolved            │   │
│  │ 12:05  🔴  Data gap detected EUR/USD M15 — auto-filled         │   │
│  │ 09:00  ℹ️  Daily backup completed successfully                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Trading Performance Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ALPHA STACK — TRADING PERFORMANCE          EUR/USD | All | Strategy X  │
├─────────────────────────────────────────────────────────────────────────┤
│  EQUITY CURVE                                                           │
│  $520 ────────────────────────────────────────────────╮                │
│  $510 ───────────────────────────────────╮            │                │
│  $500 ──────────────────╮                │            │                │
│  $490 ──────────────────╯                ╯            ╯                │
│        Mon   Tue   Wed   Thu   Fri   Mon   Tue   Wed                   │
│  [line chart with drawdown shading]                                     │
├──────────────────┬──────────────────┬──────────────────┬───────────────┤
│  Total P&L       │  Sharpe Ratio    │  Profit Factor   │ Max Drawdown  │
│  +$23.45         │  1.82            │  2.1             │ -4.2%         │
│  [sparkline]     │  [gauge]         │  [gauge]         │ [gauge]       │
├──────────────────┴──────────────────┴──────────────────┴───────────────┤
│  DAILY P&L HEATMAP (last 30 days)                                      │
│  ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐  │
│  │ + │ + │ - │ + │ + │ + │ - │ + │ + │ - │ + │ + │ + │ + │ - │ + │  │
│  │ ██│ ██│ ░░│ ██│ ██│ ██│ ░░│ ██│ ██│ ░░│ ██│ ██│ ██│ ██│ ░░│ ██│  │
│  └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘  │
│  (color intensity = magnitude of P&L)                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  OPEN POSITIONS                                                         │
│  ┌──────────┬──────┬────────┬────────┬────────┬────────┬───────────┐  │
│  │ Symbol   │ Side │ Entry  │ Current│ P&L    │ Duration│ Strategy  │  │
│  ├──────────┼──────┼────────┼────────┼────────┼────────┼───────────┤  │
│  │ EUR/USD  │ Long │ 1.0842 │ 1.0867 │ +$3.75 │ 2h 15m │ Momentum  │  │
│  │ GBP/USD  │ Short│ 1.2710 │ 1.2698 │ +$1.80 │ 45m    │ SMC       │  │
│  └──────────┴──────┴────────┴────────┴────────┴────────┴───────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│  STRATEGY ATTRIBUTION                                                   │
│  ┌──────────────┬────────┬────────┬────────┬────────┬──────────────┐  │
│  │ Strategy     │ Trades │ Win%   │ Avg R  │ P&L    │ Sharpe       │  │
│  ├──────────────┼────────┼────────┼────────┼────────┼──────────────┤  │
│  │ SMC Primary  │ 45     │ 64%    │ 1.5R   │ +$18.20│ 2.1          │  │
│  │ Momentum     │ 23     │ 57%    │ 1.2R   │ +$5.25 │ 1.4          │  │
│  │ Breakout     │ 12     │ 50%    │ 1.8R   │ +$0.00 │ 0.8          │  │
│  └──────────────┴────────┴────────┴────────┴────────┴──────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.4 Grafana Dashboard JSON (Overview)

```json
{
  "dashboard": {
    "title": "Alpha Stack — System Overview",
    "tags": ["alphastack", "overview"],
    "timezone": "browser",
    "refresh": "30s",
    "time": { "from": "now-6h", "to": "now" },
    "panels": [
      {
        "title": "CPU Usage",
        "type": "gauge",
        "gridPos": { "h": 4, "w": 4, "x": 0, "y": 0 },
        "targets": [{
          "expr": "100 - (avg by(instance) (rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
          "legendFormat": "{{ instance }}"
        }],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                { "value": 0, "color": "green" },
                { "value": 70, "color": "yellow" },
                { "value": 85, "color": "red" }
              ]
            },
            "unit": "percent",
            "max": 100
          }
        }
      },
      {
        "title": "Memory Usage",
        "type": "gauge",
        "gridPos": { "h": 4, "w": 4, "x": 4, "y": 0 },
        "targets": [{
          "expr": "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100"
        }],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                { "value": 0, "color": "green" },
                { "value": 70, "color": "yellow" },
                { "value": 85, "color": "red" }
              ]
            },
            "unit": "percent",
            "max": 100
          }
        }
      },
      {
        "title": "Service Health",
        "type": "stat",
        "gridPos": { "h": 4, "w": 16, "x": 0, "y": 4 },
        "targets": [{
          "expr": "up",
          "legendFormat": "{{ job }}"
        }],
        "fieldConfig": {
          "defaults": {
            "mappings": [
              { "type": "value", "options": { "0": { "text": "DOWN", "color": "red" } } },
              { "type": "value", "options": { "1": { "text": "UP", "color": "green" } } }
            ]
          }
        }
      },
      {
        "title": "Daily P&L",
        "type": "timeseries",
        "gridPos": { "h": 6, "w": 12, "x": 0, "y": 8 },
        "targets": [{
          "expr": "as_account_daily_pnl_usd",
          "legendFormat": "{{ account_id }}"
        }]
      },
      {
        "title": "Order Latency (p95)",
        "type": "timeseries",
        "gridPos": { "h": 6, "w": 12, "x": 12, "y": 8 },
        "targets": [{
          "expr": "histogram_quantile(0.95, rate(as_order_latency_seconds_bucket[5m]))",
          "legendFormat": "{{ broker_id }}"
        }]
      },
      {
        "title": "Recent Alerts",
        "type": "alertlist",
        "gridPos": { "h": 6, "w": 24, "x": 0, "y": 14 },
        "options": {
          "showOptions": "current",
          "maxItems": 10,
          "sortOrder": 1
        }
      }
    ]
  }
}
```

### 10.5 Grafana Provisioning

```yaml
# config/grafana/datasources/datasources.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: false

  - name: PostgreSQL
    type: postgres
    url: postgres:5432
    database: alphastack
    user: grafana_readonly
    secureJsonData:
      password: ${GRAFANA_DB_PASSWORD}
    jsonData:
      sslmode: disable
      maxOpenConns: 5
      maxIdleConns: 2
    editable: false
```

```yaml
# config/grafana/dashboards/dashboards.yml
apiVersion: 1

providers:
  - name: 'Alpha Stack'
    orgId: 1
    folder: 'Alpha Stack'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
      foldersFromFilesStructure: true
```

---

## 11. Log Aggregation

### 11.1 Structured Logging Standard

Every service emits structured JSON logs to stdout:

```python
# Standard log format for all Alpha Stack services
import structlog

def setup_logging(service_name: str, level: str = "INFO"):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service_name)
```

### 11.2 Log Schema

```json
{
  "timestamp": "2026-07-11T13:45:23.123456Z",
  "level": "info",
  "service": "trading-engine",
  "event": "order_placed",
  "order_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "symbol": "EUR/USD",
  "side": "buy",
  "quantity": 0.02,
  "price": 1.0842,
  "broker_id": "fxpesa_mt5",
  "latency_ms": 45,
  "strategy_id": "momentum_v1",
  "confluence_score": 85,
  "request_id": "req-xyz123",
  "trace_id": "abc-def-123"
}
```

### 11.3 Log Levels & Categories

| Level | Usage | Retention | Examples |
|-------|-------|-----------|----------|
| `DEBUG` | Detailed diagnostic | 3 days | Tick processing, indicator values, raw WS messages |
| `INFO` | Normal operations | 14 days | Order placed, signal generated, broker connected, candle closed |
| `WARNING` | Recoverable issues | 30 days | Reconnection, rate limit hit, spread filter rejected, data gap |
| `ERROR` | Failures requiring attention | 90 days | Broker error, DB connection lost, model inference failed |
| `CRITICAL` | System-threatening | 1 year | Trading halted, data corruption, all brokers down, OOM |

### 11.4 Log Query Examples (Grafana + Loki)

```
# All errors in trading-engine last hour
{service="trading-engine"} |= "error" | level="error"

# Order rejections with broker details
{service="trading-engine"} |~ "order.*rejected" | json | broker_id="fxpesa_mt5"

# Agent failures across all services
{service=~".*"} |= "agent" |= "failed" | json

# Slow queries (latency > 1s)
{service="core-api"} | json | latency_ms > 1000

# Drawdown warnings
{service="trading-engine"} | json | event="drawdown_warning"
```

### 11.5 Log Retention Configuration

```yaml
# config/loki/loki-config.yml (retention section)
limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h  # 7 days max ingestion lag

compactor:
  retention_enabled: true
  retention_delete_delay: 2h
  retention_delete_worker_count: 150

table_manager:
  retention_deletes_enabled: true
  retention_period: 720h  # 30 days
```

| Log Source | Retention | Rotation |
|------------|-----------|----------|
| Docker container stdout | 3 × 10MB per container | Docker json-file driver |
| Nginx access/error | 30 days | logrotate daily |
| System (syslog) | 14 days | journald vacuum |
| Loki aggregated | 30 days | Loki compactor |
| Application audit | 1 year | TimescaleDB `system_events` table |

---

## 12. Performance Metrics and SLAs

### 12.1 Service Level Objectives (SLOs)

| Service | Metric | SLO | Measurement |
|---------|--------|-----|-------------|
| **Core API** | Availability | 99.5% | Uptime / total time |
| **Core API** | Latency (p95) | <200ms | HTTP request duration |
| **Core API** | Error rate | <1% | 5xx / total requests |
| **Trading Engine** | Order latency (p95) | <2s | Submission to fill |
| **Trading Engine** | Order fill rate | >95% | Filled / submitted |
| **Trading Engine** | Slippage (avg) | <2 pips | Expected vs actual price |
| **Market Data** | Tick freshness | <5s | Time since last tick |
| **Market Data** | Candle completeness | >99% | Expected vs actual candles |
| **AI Inference** | Latency (p95) | <5s | Model inference time |
| **AI Inference** | Availability | 99% | Uptime / total time |
| **PostgreSQL** | Query latency (p95) | <50ms | Query execution time |
| **PostgreSQL** | Connection availability | 99.9% | Successful / total connects |
| **Redis** | Operation latency (p99) | <1ms | Redis command duration |
| **Redis** | Cache hit rate | >90% | Hits / (hits + misses) |
| **End-to-End** | Signal-to-fill (p95) | <5s | Full pipeline latency |

### 12.2 SLO Budget Tracking

```promql
# 30-day rolling availability for Core API
# SLO: 99.5% → allowed downtime: 3.6 hours/month

# Availability calculation
sum(up{job="core-api"} == 1) / count(up{job="core-api"}) * 100

# Error budget remaining
# 0.5% error budget over 30 days = 21.6 minutes of downtime
1 - (
  sum(rate(http_requests_total{job="core-api", status=~"5.."}[30d]))
  / sum(rate(http_requests_total{job="core-api"}[30d]))
) / 0.005

# Latency SLO compliance
# Target: 95% of requests < 200ms
sum(rate(http_request_duration_seconds_bucket{job="core-api", le="0.2"}[30d]))
/ sum(rate(http_request_duration_seconds_count{job="core-api"}[30d]))
```

### 12.3 Performance Baselines

| Metric | Phase 1 (Local) | Phase 2 (VPS) | Phase 3 (Split) | Phase 4 (Pro) |
|--------|-----------------|---------------|-----------------|---------------|
| CPU utilization | <30% | <50% | <60% | <70% |
| Memory utilization | <50% | <60% | <70% | <70% |
| Disk I/O (write) | <10 MB/s | <20 MB/s | <50 MB/s | <100 MB/s |
| Network (outbound) | <1 Mbps | <5 Mbps | <10 Mbps | <50 Mbps |
| DB connections | <5 | <10 | <20 | <50 |
| Redis memory | <64MB | <128MB | <256MB | <512MB |
| Tick processing latency | <10ms | <5ms | <3ms | <1ms |
| Candle computation lag | <1s | <500ms | <200ms | <100ms |

### 12.4 Capacity Planning Metrics

```promql
# Predict disk full date (linear projection)
predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[7d], 30*24*3600)

# Predict Redis memory exhaustion
predict_linear(redis_memory_used_bytes[7d], 30*24*3600) / redis_memory_max_bytes

# Predict PostgreSQL growth rate
predict_linear(pg_database_size_bytes{datname="alphastack"}[30d], 90*24*3600)

# Tick ingestion rate trend
rate(as_data_ingestion_total{data_type="tick"}[1h])
```

---

## 13. Monitoring Stack Deployment

### 13.1 Docker Compose Additions

The monitoring stack is defined in `docker-compose.yml` (Phase 2+) with these additional containers:

| Container | Image | Ports | Resources | Purpose |
|-----------|-------|-------|-----------|---------|
| `prometheus` | `prom/prometheus:v2.53` | 9090 | 0.25 CPU, 256MB | Metrics collection |
| `grafana` | `grafana/grafana:11.1` | 3001 | 0.25 CPU, 128MB | Dashboards |
| `loki` | `grafana/loki:3.0` | 3100 | 0.25 CPU, 256MB | Log aggregation |
| `promtail` | `grafana/promtail:3.0` | — | 0.1 CPU, 64MB | Log collection |
| `alertmanager` | `prom/alertmanager:v0.27` | 9093 | 0.1 CPU, 64MB | Alert routing |
| `node-exporter` | `prom/node-exporter:v1.8` | 9100 | 0.1 CPU, 64MB | Host metrics |
| `postgres-exporter` | `prometheuscommunity/postgres-exporter:v0.15` | 9187 | 0.1 CPU, 64MB | PG metrics |
| `redis-exporter` | `oliver006/redis_exporter:v1.62` | 9121 | 0.05 CPU, 32MB | Redis metrics |
| `cadvisor` | `gcr.io/cadvisor/cadvisor:v0.49` | 8080 | 0.1 CPU, 64MB | Container metrics |
| `blackbox-exporter` | `prom/blackbox-exporter:v0.25` | 9115 | 0.05 CPU, 32MB | Endpoint probing |

### 13.2 Prometheus Scrape Configuration

```yaml
# config/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  scrape_timeout: 10s

rule_files:
  - "alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

scrape_configs:
  # ─── Application Services ─────────────────────────────────
  - job_name: core-api
    static_configs:
      - targets: ["core-api:8000"]
    metrics_path: /metrics
    scrape_interval: 10s

  - job_name: trading-engine
    static_configs:
      - targets: ["trading-engine:8002"]
    metrics_path: /metrics
    scrape_interval: 10s

  - job_name: market-data
    static_configs:
      - targets: ["market-data:8003"]
    metrics_path: /metrics

  - job_name: ai-inference
    static_configs:
      - targets: ["ai-inference:8001"]
    metrics_path: /metrics

  # ─── Infrastructure Exporters ──────────────────────────────
  - job_name: node
    static_configs:
      - targets: ["node-exporter:9100"]

  - job_name: postgres
    static_configs:
      - targets: ["postgres-exporter:9187"]

  - job_name: redis
    static_configs:
      - targets: ["redis-exporter:9121"]

  - job_name: cadvisor
    static_configs:
      - targets: ["cadvisor:8080"]

  # ─── Blackbox Probes ──────────────────────────────────────
  - job_name: blackbox-http
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - http://core-api:8000/health
          - http://ai-inference:8001/health
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
```

### 13.3 Resource Budget

Total monitoring stack overhead on Phase 2 VPS (4GB RAM):

| Component | CPU | Memory | Disk | % of Total |
|-----------|-----|--------|------|------------|
| Prometheus | 0.25 | 256MB | 5GB | 6.4% RAM |
| Grafana | 0.25 | 128MB | 100MB | 3.2% RAM |
| Loki | 0.25 | 256MB | 10GB | 6.4% RAM |
| Promtail | 0.1 | 64MB | — | 1.6% RAM |
| Alertmanager | 0.1 | 64MB | — | 1.6% RAM |
| Node Exporter | 0.1 | 64MB | — | 1.6% RAM |
| PG Exporter | 0.1 | 64MB | — | 1.6% RAM |
| Redis Exporter | 0.05 | 32MB | — | 0.8% RAM |
| cAdvisor | 0.1 | 64MB | — | 1.6% RAM |
| Blackbox | 0.05 | 32MB | — | 0.8% RAM |
| **TOTAL** | **1.35** | **1024MB** | **~15GB** | **~25% RAM** |

**Impact:** Monitoring stack consumes ~25% of a 4GB VPS. This is acceptable for Phase 2. In Phase 3+, monitoring moves to a dedicated VPS.

---

## 14. Implementation Roadmap

### Phase 1: Foundation (Week 1–2)

```
□ Add prometheus_client to all Python services
□ Implement /health and /metrics endpoints for core-api
□ Implement /health and /metrics endpoints for trading-engine
□ Add node_exporter to Docker Compose
□ Add postgres_exporter to Docker Compose
□ Add redis_exporter to Docker Compose
□ Deploy Prometheus with basic scrape config
□ Deploy Grafana with provisioned datasources
□ Create Overview dashboard (CPU, memory, disk, service health)
□ Configure basic alert rules (service down, high CPU, disk space)
□ Set up Telegram alert notifications
□ Test: Kill a service, verify alert fires
```

### Phase 2: Trading Metrics (Week 3–4)

```
□ Implement order lifecycle metrics (orders_total, order_latency, slippage)
□ Implement account metrics (balance, equity, drawdown, daily P&L)
□ Implement broker connection metrics (status, latency, reconnections)
□ Implement risk utilization metrics
□ Create Trading Performance dashboard (equity curve, P&L, win rate)
□ Create Broker & Execution dashboard (latency, fill rate, slippage)
□ Add trading-specific alert rules (drawdown, broker disconnect, rejection rate)
□ Deploy Loki + Promtail for log aggregation
□ Configure structured logging in trading-engine
□ Create Logs dashboard in Grafana
□ Test: Simulate broker disconnect, verify alert + log correlation
```

### Phase 3: Agent & Data Monitoring (Week 5–6)

```
□ Implement agent health metrics (status, heartbeat, inference time, errors)
□ Implement agent throughput metrics (signals produced, messages processed)
□ Implement data pipeline metrics (freshness, gaps, validation errors, stream lag)
□ Create Agent Health dashboard (status grid, latency, errors, memory)
□ Create Data Pipeline dashboard (freshness heatmap, gap timeline, ingestion rates)
□ Add agent-specific alert rules (agent down, heartbeat stale, inference slow)
□ Add data pipeline alert rules (staleness, gaps, validation errors, stream lag)
□ Implement data quality checks with metrics export
□ Create Database dashboard (PG, TimescaleDB, Redis metrics)
□ Test: Inject data gap, verify detection and alert
```

### Phase 4: SLA & Capacity (Week 7+)

```
□ Define and document SLOs for each service
□ Implement SLO tracking dashboards
□ Implement error budget tracking
□ Add capacity planning metrics (predict_linear projections)
□ Implement backup monitoring metrics
□ Create Infrastructure dashboard (per-host drill-down)
□ Set up log-based alerts (error patterns in Loki)
□ Implement performance regression detection
□ Load test monitoring stack (verify no metric drop under load)
□ Document monitoring runbook (common alerts → resolution steps)
□ Review and tune alert thresholds based on 30 days of data
```

---

## Appendix A: Prometheus Label Cardinality Budget

| Label | Max Values | Notes |
|-------|-----------|-------|
| `symbol` | 50 | Fixed instrument universe |
| `broker_id` | 5 | MT5, Binance, Bybit, IBKR, OANDA |
| `agent_type` | 16 | Fixed agent types |
| `strategy_id` | 10 | Active strategies |
| `status` | 8 | Order statuses |
| `side` | 2 | buy, sell |
| `timeframe` | 7 | 1m, 5m, 15m, 1h, 4h, 1d, 1w |
| `source` | 10 | Data sources |
| `error_type` | 15 | Error categories |

**Total worst-case cardinality:** 50 × 5 × 16 × 10 × 8 × 2 × 7 × 10 × 15 = **~67M series**

This exceeds Prometheus capacity. **Mitigation:** Not all label combinations exist simultaneously. Realistic cardinality: ~5,000–20,000 active series, well within Prometheus limits.

---

## Appendix B: Monitoring Checklist (Per-Deployment)

```markdown
## Pre-Deployment Monitoring Checklist

### Metrics
- [ ] All services expose /metrics endpoint
- [ ] Prometheus scraping all targets (check /targets)
- [ ] No "stale" or "down" targets in Prometheus
- [ ] Custom trading metrics populated
- [ ] No high-cardinality label explosion

### Dashboards
- [ ] Overview dashboard shows all services healthy
- [ ] Trading dashboard shows current positions and P&L
- [ ] Broker dashboard shows connection status
- [ ] Agent dashboard shows all agents running
- [ ] Data pipeline dashboard shows fresh data

### Alerts
- [ ] Telegram bot connected and sending test alerts
- [ ] Alert rules loaded (check /alerts in Prometheus)
- [ ] Critical alerts tested (service kill, broker disconnect)
- [ ] Alert routing verified (correct severity → correct channel)
- [ ] Alert inhibition rules working (no alert storms)

### Logs
- [ ] Loki receiving logs from all services
- [ ] Structured JSON format verified
- [ ] Log search working in Grafana
- [ ] Log retention policy configured

### Performance
- [ ] Monitoring stack memory usage < 1GB
- [ ] Prometheus query latency < 1s for dashboards
- [ ] No metric gaps in time series
- [ ] Backup of Grafana dashboards exported
```

---

## Appendix C: Quick Reference Commands

```bash
# ─── Prometheus ───────────────────────────────────────────────
curl -sf http://localhost:9090/-/healthy           # Health check
curl -sf http://localhost:9090/api/v1/targets      # Active targets
curl -sf http://localhost:9090/api/v1/rules        # Loaded rules

# ─── Grafana ──────────────────────────────────────────────────
curl -sf http://localhost:3001/api/health           # Health check

# ─── Loki ─────────────────────────────────────────────────────
curl -sf http://localhost:3100/ready                # Health check
curl -sf http://localhost:3100/loki/api/v1/labels   # Available labels

# ─── Alertmanager ─────────────────────────────────────────────
curl -sf http://localhost:9093/-/healthy             # Health check
curl -sf http://localhost:9093/api/v1/alerts         # Active alerts

# ─── Debug Queries ────────────────────────────────────────────
# Check what Prometheus sees for a metric
curl -sf 'http://localhost:9090/api/v1/query?query=up'

# Check trading engine metrics
curl -sf 'http://localhost:8002/metrics' | grep as_

# Test Loki log query
curl -sf 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={service="trading-engine"}' \
  --data-urlencode 'start=2026-07-11T00:00:00Z' \
  --data-urlencode 'end=2026-07-11T23:59:59Z'
```

---

*This monitoring architecture provides comprehensive observability for Alpha Stack from Day 1. Start with infrastructure metrics, add trading metrics as the engine develops, and scale monitoring with the platform. The goal: never be surprised by a system failure, never miss a trading anomaly, and always have the data to diagnose what went wrong.*

*Generated: 2026-07-11*
*Next review: After Phase 2 deployment — tune alert thresholds based on real data*
