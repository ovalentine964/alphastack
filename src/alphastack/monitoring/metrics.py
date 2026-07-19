"""
Prometheus metrics for AlphaStack.

Defines 25+ metrics covering:
- Trading signals, orders, PnL, drawdown, win rate
- Agent execution latency, token usage, errors, eval pass rate
- Pipeline processing, step latency, halts
- Infrastructure: event bus, Redis, database
- Cost tracking: LLM API, data feeds, broker fees

Usage:
    from alphastack.monitoring.metrics import (
        SIGNALS_TOTAL, AGENT_LATENCY, PIPELINE_LATENCY,
        record_trade, record_agent_execution, record_pipeline_run,
    )

    # Manual counter increment
    SIGNALS_TOTAL.labels(pair="EURUSD", direction="BULLISH", timeframe="H1").inc()

    # Context manager for timing
    with AGENT_LATENCY.labels(agent_name="news", loop_type="react").time():
        result = await agent.process(event)

    # High-level helpers
    record_trade(pair="EURUSD", direction="BULLISH", broker="oanda", status="filled")
    record_agent_execution("strategy", "deliberation", latency_s=0.45, tokens=1200)
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

from prometheus_client import Counter, Gauge, Histogram, Info

# ─── System Info ──────────────────────────────────────────────────

SYSTEM_INFO = Info("alphastack", "AlphaStack trading system information")

# ═══════════════════════════════════════════════════════════════════
# TRADING METRICS (9 metrics)
# ═══════════════════════════════════════════════════════════════════

# 1. Total trading signals generated
SIGNALS_TOTAL = Counter(
    "alphastack_signals_total",
    "Total trading signals generated",
    ["pair", "direction", "timeframe"],
)

# 2. Confluence score distribution
CONFLUENCE_SCORE = Histogram(
    "alphastack_confluence_score",
    "Distribution of confluence scores",
    ["pair"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0],
)

# 3. Total orders placed
ORDERS_TOTAL = Counter(
    "alphastack_orders_total",
    "Total orders placed",
    ["pair", "direction", "broker", "status"],
)

# 4. Orders rejected by risk governor
ORDERS_REJECTED = Counter(
    "alphastack_orders_rejected_total",
    "Total orders rejected by risk governor",
    ["pair", "reason"],
)

# 5. Daily P&L
PNL_DAILY = Gauge(
    "alphastack_pnl_daily",
    "Daily P&L in account currency",
    ["account"],
)

# 6. Current drawdown percentage
DRAWDOWN_CURRENT = Gauge(
    "alphastack_drawdown_current",
    "Current drawdown percentage",
    ["account"],
)

# 7. Open position count
OPEN_POSITIONS = Gauge(
    "alphastack_open_positions",
    "Number of open positions",
    ["account"],
)

# 8. Total risk exposure
RISK_EXPOSURE = Gauge(
    "alphastack_risk_exposure",
    "Current total risk exposure as percentage of balance",
    ["account"],
)

# 9. Win rate (rolling)
WIN_RATE = Gauge(
    "alphastack_win_rate",
    "Rolling win rate percentage",
    ["account", "period"],
)

# ═══════════════════════════════════════════════════════════════════
# AGENT METRICS (5 metrics)
# ═══════════════════════════════════════════════════════════════════

# 10. Agent processing latency
AGENT_LATENCY = Histogram(
    "alphastack_agent_latency_seconds",
    "Agent processing latency",
    ["agent_name", "loop_type"],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# 11. Agent token consumption
AGENT_TOKENS = Counter(
    "alphastack_agent_tokens_consumed",
    "Total tokens consumed by agent",
    ["agent_name", "model"],
)

# 12. Agent errors
AGENT_ERRORS = Counter(
    "alphastack_agent_errors_total",
    "Total agent errors",
    ["agent_name", "error_type"],
)

# 13. Agent timeouts
AGENT_TIMEOUTS = Counter(
    "alphastack_agent_timeout_total",
    "Total agent timeouts",
    ["agent_name"],
)

# 14. Agent eval pass rate
AGENT_EVAL_PASS_RATE = Gauge(
    "alphastack_agent_eval_pass_rate",
    "Agent eval pass rate (rolling 24h)",
    ["agent_name"],
)

# ═══════════════════════════════════════════════════════════════════
# PIPELINE METRICS (3 metrics)
# ═══════════════════════════════════════════════════════════════════

# 15. Pipeline end-to-end latency
PIPELINE_LATENCY = Histogram(
    "alphastack_pipeline_processing_seconds",
    "End-to-end pipeline processing time",
    ["pair", "timeframe"],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
)

# 16. Individual step latency
PIPELINE_STEP_LATENCY = Histogram(
    "alphastack_pipeline_step_seconds",
    "Individual step processing time",
    ["step_name"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# 17. Pipeline halts
PIPELINE_HALTS = Counter(
    "alphastack_pipeline_halts_total",
    "Pipeline halts (AVOID_ALL, choppy market, etc.)",
    ["halt_reason", "step"],
)

# ═══════════════════════════════════════════════════════════════════
# EVENT BUS METRICS (3 metrics)
# ═══════════════════════════════════════════════════════════════════

# 18. Messages published
EVENT_BUS_PUBLISHED = Counter(
    "alphastack_event_bus_messages_published",
    "Messages published to event bus",
    ["stream"],
)

# 19. Messages consumed
EVENT_BUS_CONSUMED = Counter(
    "alphastack_event_bus_messages_consumed",
    "Messages consumed from event bus",
    ["stream", "consumer_group"],
)

# 20. Consumer lag
EVENT_BUS_LAG = Gauge(
    "alphastack_event_bus_consumer_lag",
    "Consumer group lag (messages behind)",
    ["stream", "consumer_group"],
)

# ═══════════════════════════════════════════════════════════════════
# INFRASTRUCTURE METRICS (2 metrics)
# ═══════════════════════════════════════════════════════════════════

# 21. Redis memory usage
REDIS_MEMORY_BYTES = Gauge(
    "alphastack_redis_memory_bytes",
    "Redis memory usage in bytes",
)

# 22. Database query latency
DB_QUERY_LATENCY = Histogram(
    "alphastack_database_query_seconds",
    "Database query latency",
    ["query_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# ═══════════════════════════════════════════════════════════════════
# COST METRICS (3 metrics)
# ═══════════════════════════════════════════════════════════════════

# 23. LLM API cost
LLM_COST = Counter(
    "alphastack_llm_cost_usd",
    "LLM API cost in USD",
    ["model", "agent_name"],
)

# 24. LLM cache hit rate
LLM_CACHE_HIT_RATE = Gauge(
    "alphastack_llm_cache_hit_rate",
    "LLM context cache hit rate",
    ["model"],
)

# 25. Data feed cost
DATA_FEED_COST = Counter(
    "alphastack_data_feed_cost_usd",
    "Data feed cost in USD",
    ["provider"],
)

# 26. Broker cost
BROKER_COST = Counter(
    "alphastack_broker_cost_usd",
    "Broker fees in USD",
    ["broker", "fee_type"],
)

# ═══════════════════════════════════════════════════════════════════
# ADDITIONAL TRADING METRICS (3 more)
# ═══════════════════════════════════════════════════════════════════

# 27. Trade execution latency (signal → fill)
TRADE_EXECUTION_LATENCY = Histogram(
    "alphastack_trade_execution_seconds",
    "Latency from signal generation to order fill",
    ["pair", "broker"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# 28. Trade volume
TRADE_VOLUME = Counter(
    "alphastack_trade_volume_total",
    "Total trade volume in quote currency",
    ["pair", "broker"],
)

# 29. Risk checks performed
RISK_CHECKS = Counter(
    "alphastack_risk_checks_total",
    "Total risk checks performed",
    ["result"],  # passed | rejected
)

# ═══════════════════════════════════════════════════════════════════
# HIGH-LEVEL HELPERS
# ═══════════════════════════════════════════════════════════════════


def record_trade(
    pair: str,
    direction: str,
    broker: str,
    status: str,
    volume: float = 0.0,
    execution_latency_s: float = 0.0,
) -> None:
    """Record a trade event across all relevant metrics."""
    ORDERS_TOTAL.labels(pair=pair, direction=direction, broker=broker, status=status).inc()
    if volume > 0:
        TRADE_VOLUME.labels(pair=pair, broker=broker).inc(volume)
    if execution_latency_s > 0:
        TRADE_EXECUTION_LATENCY.labels(pair=pair, broker=broker).observe(execution_latency_s)


def record_agent_execution(
    agent_name: str,
    loop_type: str,
    latency_s: float,
    tokens: int = 0,
    model: str = "unknown",
    error: bool = False,
    error_type: str = "",
    timed_out: bool = False,
) -> None:
    """Record an agent execution event."""
    AGENT_LATENCY.labels(agent_name=agent_name, loop_type=loop_type).observe(latency_s)
    if tokens > 0:
        AGENT_TOKENS.labels(agent_name=agent_name, model=model).inc(tokens)
    if error:
        AGENT_ERRORS.labels(agent_name=agent_name, error_type=error_type or "unknown").inc()
    if timed_out:
        AGENT_TIMEOUTS.labels(agent_name=agent_name).inc()


def record_pipeline_run(
    pair: str,
    timeframe: str,
    latency_s: float,
    halted: bool = False,
    halt_reason: str = "",
    halt_step: str = "",
) -> None:
    """Record a pipeline run."""
    PIPELINE_LATENCY.labels(pair=pair, timeframe=timeframe).observe(latency_s)
    if halted:
        PIPELINE_HALTS.labels(halt_reason=halt_reason, step=halt_step).inc()


def record_signal(
    pair: str,
    direction: str,
    timeframe: str,
    confluence_score: float,
) -> None:
    """Record a generated trading signal."""
    SIGNALS_TOTAL.labels(pair=pair, direction=direction, timeframe=timeframe).inc()
    CONFLUENCE_SCORE.labels(pair=pair).observe(confluence_score)


def record_risk_check(approved: bool, pair: str = "", reason: str = "") -> None:
    """Record a risk check result."""
    result = "passed" if approved else "rejected"
    RISK_CHECKS.labels(result=result).inc()
    if not approved and reason:
        ORDERS_REJECTED.labels(pair=pair, reason=reason).inc()


def update_account_state(
    account: str,
    daily_pnl: float = 0.0,
    drawdown_pct: float = 0.0,
    open_position_count: int = 0,
    risk_exposure_pct: float = 0.0,
    win_rate_pct: float = 0.0,
) -> None:
    """Update account-level gauge metrics."""
    if daily_pnl != 0.0:
        PNL_DAILY.labels(account=account).set(daily_pnl)
    DRAWDOWN_CURRENT.labels(account=account).set(drawdown_pct)
    OPEN_POSITIONS.labels(account=account).set(open_position_count)
    RISK_EXPOSURE.labels(account=account).set(risk_exposure_pct)
    if win_rate_pct > 0:
        WIN_RATE.labels(account=account, period="rolling").set(win_rate_pct)


def record_llm_cost(model: str, agent_name: str, cost_usd: float) -> None:
    """Record LLM API cost."""
    LLM_COST.labels(model=model, agent_name=agent_name).inc(cost_usd)


@contextmanager
def time_agent(agent_name: str, loop_type: str) -> Generator[None, None, None]:
    """Context manager to time agent execution and record latency."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        AGENT_LATENCY.labels(agent_name=agent_name, loop_type=loop_type).observe(elapsed)


@contextmanager
def time_pipeline_step(step_name: str) -> Generator[None, None, None]:
    """Context manager to time a pipeline step."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        PIPELINE_STEP_LATENCY.labels(step_name=step_name).observe(elapsed)


@contextmanager
def time_db_query(query_type: str) -> Generator[None, None, None]:
    """Context manager to time a database query."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        DB_QUERY_LATENCY.labels(query_type=query_type).observe(elapsed)
