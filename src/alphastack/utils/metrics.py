"""Prometheus metrics for AlphaStack."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------

SYSTEM_INFO = Info("alphastack", "AlphaStack trading system information")

# ---------------------------------------------------------------------------
# Trade metrics
# ---------------------------------------------------------------------------

TRADES_TOTAL = Counter(
    "alphastack_trades_total",
    "Total number of executed trades",
    ["symbol", "side", "strategy", "broker"],
)

TRADE_LATENCY = Histogram(
    "alphastack_trade_latency_seconds",
    "Latency from signal to execution",
    ["symbol", "broker"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

TRADE_VOLUME = Counter(
    "alphastack_trade_volume_total",
    "Total trade volume (in quote currency)",
    ["symbol", "strategy"],
)

TRADE_COMMISSION = Counter(
    "alphastack_trade_commission_total",
    "Total commissions paid",
    ["broker"],
)

# ---------------------------------------------------------------------------
# Position metrics
# ---------------------------------------------------------------------------

OPEN_POSITIONS = Gauge(
    "alphastack_open_positions",
    "Number of currently open positions",
    ["account", "symbol"],
)

POSITION_PNL = Gauge(
    "alphastack_position_pnl",
    "Unrealised P&L per position",
    ["account", "symbol", "side"],
)

TOTAL_EQUITY = Gauge(
    "alphastack_total_equity",
    "Account equity",
    ["account"],
)

TOTAL_DRAWDOWN = Gauge(
    "alphastack_drawdown_pct",
    "Current drawdown from peak as a percentage",
    ["account"],
)

# ---------------------------------------------------------------------------
# Signal / strategy metrics
# ---------------------------------------------------------------------------

SIGNALS_TOTAL = Counter(
    "alphastack_signals_total",
    "Total signals generated",
    ["symbol", "side", "strategy"],
)

SIGNAL_STRENGTH = Histogram(
    "alphastack_signal_strength",
    "Distribution of signal strengths",
    ["strategy"],
    buckets=(-1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
)

# ---------------------------------------------------------------------------
# Risk metrics
# ---------------------------------------------------------------------------

RISK_CHECKS_TOTAL = Counter(
    "alphastack_risk_checks_total",
    "Total risk checks performed",
    ["rule", "result"],  # result: passed | failed
)

RISK_BREACHES = Counter(
    "alphastack_risk_breaches_total",
    "Total risk limit breaches",
    ["level", "rule"],  # level: warning | critical
)

# ---------------------------------------------------------------------------
# Agent metrics
# ---------------------------------------------------------------------------

AGENT_DECISIONS = Counter(
    "alphastack_agent_decisions_total",
    "Total agent decisions",
    ["agent_id", "agent_type", "action"],
)

AGENT_LATENCY = Histogram(
    "alphastack_agent_latency_seconds",
    "Agent decision latency",
    ["agent_id", "agent_type"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

AGENT_CONFIDENCE = Histogram(
    "alphastack_agent_confidence",
    "Distribution of agent confidence scores",
    ["agent_type"],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

# ---------------------------------------------------------------------------
# Data feed metrics
# ---------------------------------------------------------------------------

DATA_EVENTS_TOTAL = Counter(
    "alphastack_data_events_total",
    "Total market data events received",
    ["symbol", "data_type", "source"],
)

DATA_STALE_SECONDS = Gauge(
    "alphastack_data_stale_seconds",
    "Seconds since last data update per symbol",
    ["symbol", "source"],
)

# ---------------------------------------------------------------------------
# API metrics
# ---------------------------------------------------------------------------

API_REQUESTS = Counter(
    "alphastack_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)

API_LATENCY = Histogram(
    "alphastack_api_latency_seconds",
    "API request latency",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
