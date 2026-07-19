"""
AlphaStack Monitoring Module.

Provides Prometheus metrics, health checks, and observability endpoints
for the multi-agent trading system.

Usage:
    from alphastack.monitoring import metrics, health

    # Record a trade signal
    metrics.SIGNALS_TOTAL.labels(pair="EURUSD", direction="BULLISH", timeframe="H1").inc()

    # Time an agent execution
    with metrics.AGENT_LATENCY.labels(agent_name="news", loop_type="react").time():
        result = await news_agent.process(event)

    # Register health checks
    health.register_dependency("redis", check_redis_connection)
"""

from alphastack.monitoring import health, metrics

__all__ = ["metrics", "health"]
