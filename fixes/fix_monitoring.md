# Alpha Stack — Critical Monitoring Gaps Fix Plan

> **Version:** 1.0 · **Date:** 2026-07-11
> **Scope:** Implementation guide for the 6 critical monitoring gaps identified in `review_monitoring.md`
> **Prerequisites:** Docker Compose stack, Redis, TimescaleDB/PostgreSQL, Prometheus, Grafana

---

## Gap 1: No Infrastructure Monitoring — Redis, DB, Container

### Problem
The system monitors trades but has zero visibility into the infrastructure running it. A Redis OOM or DB disk-full event would silently kill the monitoring pipeline while the trader believes everything is fine.

### Solution: Prometheus Exporters + Infrastructure Dashboard

#### 1.1 Deploy Exporters (Docker Compose additions)

```yaml
# docker-compose.monitoring.yml

services:
  redis-exporter:
    image: oliver006/redis_exporter:v1.58.0
    environment:
      REDIS_ADDR: "redis://redis:6379"
      REDIS_EXPORTER_INCL_SYSTEM_METRICS: "true"
    ports:
      - "9121:9121"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:9121/health"]
      interval: 15s
      timeout: 5s

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:v0.15.0
    environment:
      DATA_SOURCE_NAME: "postgresql://${PG_USER}:${PG_PASSWORD}@timescaledb:5432/${PG_DB}?sslmode=disable"
      PG_EXPORTER_AUTO_DISCOVER_DATABASES: "true"
    ports:
      - "9187:9187"
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:v1.7.0
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--path.rootfs=/rootfs'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    ports:
      - "9100:9100"
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.47.2
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    ports:
      - "8080:8080"
    privileged: true
    restart: unless-stopped
```

#### 1.2 Prometheus Scrape Config

```yaml
# prometheus/scrape_configs.yml additions
scrape_configs:
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
    scrape_interval: 10s

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
    scrape_interval: 15s

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
    scrape_interval: 15s

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
    scrape_interval: 10s
```

#### 1.3 Infrastructure Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Alpha Stack — Infrastructure Health",
    "tags": ["infrastructure", "alpha-stack"],
    "refresh": "10s",
    "rows": [
      {
        "title": "Redis",
        "panels": [
          {
            "title": "Memory Usage",
            "type": "gauge",
            "targets": [
              {
                "expr": "redis_memory_used_bytes / redis_memory_max_bytes * 100",
                "legendFormat": "Used %"
              }
            ],
            "thresholds": [
              {"value": 0, "color": "green"},
              {"value": 75, "color": "yellow"},
              {"value": 90, "color": "red"}
            ]
          },
          {
            "title": "Connected Clients",
            "type": "stat",
            "targets": [{"expr": "redis_connected_clients"}]
          },
          {
            "title": "Commands/sec",
            "type": "graph",
            "targets": [{"expr": "rate(redis_commands_processed_total[1m])"}]
          },
          {
            "title": "Key Count",
            "type": "stat",
            "targets": [{"expr": "redis_db_keys{db=\"db0\"}"}]
          }
        ]
      },
      {
        "title": "PostgreSQL / TimescaleDB",
        "panels": [
          {
            "title": "Active Connections",
            "type": "gauge",
            "targets": [
              {
                "expr": "pg_stat_activity_count / pg_settings_max_connections * 100",
                "legendFormat": "Pool Usage %"
              }
            ],
            "thresholds": [
              {"value": 0, "color": "green"},
              {"value": 60, "color": "yellow"},
              {"value": 80, "color": "red"}
            ]
          },
          {
            "title": "Query Latency (p95)",
            "type": "graph",
            "targets": [
              {
                "expr": "histogram_quantile(0.95, rate(pg_stat_activity_query_duration_seconds_bucket[5m]))",
                "legendFormat": "p95"
              }
            ]
          },
          {
            "title": "Database Size",
            "type": "graph",
            "targets": [
              {
                "expr": "pg_database_size_bytes",
                "legendFormat": "{{datname}}"
              }
            ]
          },
          {
            "title": "Disk Usage",
            "type": "gauge",
            "targets": [
              {
                "expr": "(node_filesystem_size_bytes{mountpoint=\"/data\"} - node_filesystem_avail_bytes{mountpoint=\"/data\"}) / node_filesystem_size_bytes{mountpoint=\"/data\"} * 100",
                "legendFormat": "Disk Used %"
              }
            ],
            "thresholds": [
              {"value": 0, "color": "green"},
              {"value": 80, "color": "yellow"},
              {"value": 90, "color": "red"}
            ]
          }
        ]
      },
      {
        "title": "Containers",
        "panels": [
          {
            "title": "CPU per Container",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(container_cpu_usage_seconds_total{name=~\".+\"}[1m]) * 100",
                "legendFormat": "{{name}}"
              }
            ]
          },
          {
            "title": "Memory per Container",
            "type": "graph",
            "targets": [
              {
                "expr": "container_memory_usage_bytes{name=~\".+\"} / 1024 / 1024",
                "legendFormat": "{{name}} (MB)"
              }
            ]
          },
          {
            "title": "Container Restarts",
            "type": "stat",
            "targets": [
              {
                "expr": "container_restart_count{name=~\".+\"}",
                "legendFormat": "{{name}}"
              }
            ],
            "thresholds": [
              {"value": 0, "color": "green"},
              {"value": 1, "color": "red"}
            ]
          },
          {
            "title": "Network I/O",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(container_network_receive_bytes_total{name=~\".+\"}[1m])",
                "legendFormat": "{{name}} RX"
              },
              {
                "expr": "rate(container_network_transmit_bytes_total{name=~\".+\"}[1m])",
                "legendFormat": "{{name}} TX"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

#### 1.4 Grafana Alert Rules — Infrastructure

```yaml
# grafana/provisioning/alerting/infrastructure.yml

groups:
  - name: infrastructure_critical
    interval: 30s
    rules:
      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes * 100 > 75
        for: 2m
        labels:
          severity: warning
          component: redis
        annotations:
          summary: "Redis memory usage > 75%"
          description: "Redis is using {{ $value }}% of maxmemory. Evictions will begin at 100%."

      - alert: RedisMemoryCritical
        expr: redis_memory_used_bytes / redis_memory_max_bytes * 100 > 90
        for: 1m
        labels:
          severity: critical
          component: redis
        annotations:
          summary: "Redis memory usage > 90% — EVICTION IMMINENT"

      - alert: DBConnectionsHigh
        expr: pg_stat_activity_count / pg_settings_max_connections * 100 > 80
        for: 2m
        labels:
          severity: critical
          component: database
        annotations:
          summary: "Database connection pool > 80%"
          description: "{{ $value }}% of max connections used. System may stall."

      - alert: DBQueryLatencyHigh
        expr: histogram_quantile(0.95, rate(pg_stat_activity_query_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
          component: database
        annotations:
          summary: "DB query p95 latency > 2 seconds"

      - alert: DiskSpaceWarning
        expr: (node_filesystem_size_bytes - node_filesystem_avail_bytes) / node_filesystem_size_bytes * 100 > 80
        for: 5m
        labels:
          severity: warning
          component: disk
        annotations:
          summary: "Disk usage > 80% on {{ $labels.mountpoint }}"

      - alert: DiskSpaceCritical
        expr: (node_filesystem_size_bytes - node_filesystem_avail_bytes) / node_filesystem_size_bytes * 100 > 90
        for: 2m
        labels:
          severity: critical
          component: disk
        annotations:
          summary: "Disk usage > 90% — SYSTEM WILL FAIL SOON"

      - alert: ContainerRestarted
        expr: increase(container_restart_count{name=~".+"}[5m]) > 0
        labels:
          severity: warning
          component: container
        annotations:
          summary: "Container {{ $labels.name }} restarted"
          description: "Any restart indicates instability. Check container logs."

      - alert: ContainerOOMKilled
        expr: container_oom_events_total > 0
        labels:
          severity: critical
          component: container
        annotations:
          summary: "Container {{ $labels.name }} was OOM killed"
```

---

## Gap 2: No Self-Monitoring — The "Watchmen" Problem

### Problem
If the monitoring container crashes, Redis Stream consumers stop, or Prometheus stops scraping, nobody knows. The trader thinks everything is fine while the monitoring system is silently dead.

### Solution: External Watchdog + Canary Health Checks

#### 2.1 Watchdog Service

```python
# watchdog/monitor_watchdog.py
"""
External watchdog that monitors the monitoring system itself.
Runs as a SEPARATE container — independent of the main monitoring stack.
If the watchdog itself dies, the OS/systemd supervisor alerts (Docker restart policy + external uptime monitor).
"""

import asyncio
import aiohttp
import redis.asyncio as aioredis
import json
import time
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional

logging.basicConfig(level=logging.INFO, format='json')
logger = logging.getLogger("watchdog")

@dataclass
class HealthCheck:
    component: str
    status: str  # "healthy", "degraded", "dead"
    latency_ms: float
    detail: str
    checked_at: str

class MonitoringWatchdog:
    """
    Monitors the monitoring system. Alerts if:
    1. Main monitoring container is unreachable
    2. Redis Stream consumers have no active members
    3. Prometheus is not scraping
    4. Grafana is unreachable
    5. No monitoring events processed in N minutes
    6. Alert delivery pipeline is broken (canary not received)
    """

    def __init__(self):
        self.redis_url = "redis://redis:6379"
        self.monitoring_http_url = "http://monitoring:8000"
        self.prometheus_url = "http://prometheus:9090"
        self.grafana_url = "http://grafana:3000"
        self.check_interval_sec = 30
        self.stale_event_threshold_sec = 300  # 5 min with no events = problem
        self.alert_webhook = "http://monitoring:8000/api/v1/alerts"
        self.results: list[HealthCheck] = []

    async def run(self):
        logger.info("Watchdog started")
        while True:
            try:
                self.results = []
                await asyncio.gather(
                    self.check_monitoring_container(),
                    self.check_redis_health(),
                    self.check_event_bus_consumers(),
                    self.check_prometheus(),
                    self.check_grafana(),
                    self.check_event_flow(),
                    return_exceptions=True
                )
                await self.evaluate_and_alert()
            except Exception as e:
                logger.error(f"Watchdog cycle failed: {e}")
            await asyncio.sleep(self.check_interval_sec)

    async def check_monitoring_container(self):
        """Is the main monitoring process alive and responding?"""
        start = time.monotonic()
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.monitoring_http_url}/health",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    latency = (time.monotonic() - start) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        self.results.append(HealthCheck(
                            component="monitoring_container",
                            status="healthy",
                            latency_ms=latency,
                            detail=f"uptime={data.get('uptime_sec', '?')}s",
                            checked_at=datetime.now(timezone.utc).isoformat()
                        ))
                    else:
                        self.results.append(HealthCheck(
                            component="monitoring_container",
                            status="degraded",
                            latency_ms=latency,
                            detail=f"HTTP {resp.status}",
                            checked_at=datetime.now(timezone.utc).isoformat()
                        ))
            except Exception as e:
                self.results.append(HealthCheck(
                    component="monitoring_container",
                    status="dead",
                    latency_ms=(time.monotonic() - start) * 1000,
                    detail=str(e),
                    checked_at=datetime.now(timezone.utc).isoformat()
                ))

    async def check_redis_health(self):
        """Is Redis responsive and not in a degraded state?"""
        start = time.monotonic()
        try:
            r = aioredis.from_url(self.redis_url, socket_timeout=5)
            info = await r.info()
            latency = (time.monotonic() - start) * 1000

            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)
            mem_pct = (used_memory / max_memory * 100) if max_memory > 0 else 0

            status = "healthy"
            detail = f"mem={mem_pct:.1f}%, clients={info.get('connected_clients', '?')}"
            if mem_pct > 75:
                status = "degraded"
            if mem_pct > 90:
                status = "dead"

            self.results.append(HealthCheck(
                component="redis",
                status=status,
                latency_ms=latency,
                detail=detail,
                checked_at=datetime.now(timezone.utc).isoformat()
            ))
            await r.close()
        except Exception as e:
            self.results.append(HealthCheck(
                component="redis",
                status="dead",
                latency_ms=(time.monotonic() - start) * 1000,
                detail=str(e),
                checked_at=datetime.now(timezone.utc).isoformat()
            ))

    async def check_event_bus_consumers(self):
        """Are there active consumers on critical Redis Streams?"""
        critical_streams = [
            "stream:market_data",
            "stream:trade_events",
            "stream:monitoring_events",
            "stream:position_updates",
        ]
        try:
            r = aioredis.from_url(self.redis_url, socket_timeout=5)
            for stream_name in critical_streams:
                start = time.monotonic()
                try:
                    # Check consumer groups
                    groups = await r.xinfo_groups(stream_name)
                    latency = (time.monotonic() - start) * 1000

                    total_consumers = sum(g.get("consumers", 0) for g in groups)
                    max_lag = max(
                        (g.get("lag", 0) for g in groups if g.get("lag") is not None),
                        default=0
                    )

                    if total_consumers == 0:
                        status = "dead"
                        detail = "NO ACTIVE CONSUMERS"
                    elif max_lag > 1000:
                        status = "degraded"
                        detail = f"consumers={total_consumers}, max_lag={max_lag}"
                    else:
                        status = "healthy"
                        detail = f"consumers={total_consumers}, max_lag={max_lag}"

                    self.results.append(HealthCheck(
                        component=f"stream:{stream_name}",
                        status=status,
                        latency_ms=latency,
                        detail=detail,
                        checked_at=datetime.now(timezone.utc).isoformat()
                    ))
                except aioredis.exceptions.ResponseError:
                    # Stream doesn't exist yet — not necessarily an error
                    self.results.append(HealthCheck(
                        component=f"stream:{stream_name}",
                        status="healthy",
                        latency_ms=(time.monotonic() - start) * 1000,
                        detail="stream not yet created",
                        checked_at=datetime.now(timezone.utc).isoformat()
                    ))
            await r.close()
        except Exception as e:
            self.results.append(HealthCheck(
                component="event_bus_consumers",
                status="dead",
                latency_ms=0,
                detail=str(e),
                checked_at=datetime.now(timezone.utc).isoformat()
            ))

    async def check_prometheus(self):
        """Is Prometheus alive and scraping targets?"""
        start = time.monotonic()
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/targets",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    latency = (time.monotonic() - start) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        targets = data.get("data", {}).get("activeTargets", [])
                        down = [t for t in targets if t.get("health") != "up"]
                        if down:
                            status = "degraded"
                            detail = f"{len(down)} targets down: {[t['labels'].get('job') for t in down]}"
                        else:
                            status = "healthy"
                            detail = f"{len(targets)} targets all UP"
                    else:
                        status = "degraded"
                        detail = f"HTTP {resp.status}"

                    self.results.append(HealthCheck(
                        component="prometheus",
                        status=status,
                        latency_ms=latency,
                        detail=detail,
                        checked_at=datetime.now(timezone.utc).isoformat()
                    ))
            except Exception as e:
                self.results.append(HealthCheck(
                    component="prometheus",
                    status="dead",
                    latency_ms=(time.monotonic() - start) * 1000,
                    detail=str(e),
                    checked_at=datetime.now(timezone.utc).isoformat()
                ))

    async def check_grafana(self):
        """Is Grafana alive and datasource connected?"""
        start = time.monotonic()
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.grafana_url}/api/health",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    latency = (time.monotonic() - start) * 1000
                    status = "healthy" if resp.status == 200 else "degraded"
                    self.results.append(HealthCheck(
                        component="grafana",
                        status=status,
                        latency_ms=latency,
                        detail=f"HTTP {resp.status}",
                        checked_at=datetime.now(timezone.utc).isoformat()
                    ))
            except Exception as e:
                self.results.append(HealthCheck(
                    component="grafana",
                    status="dead",
                    latency_ms=(time.monotonic() - start) * 1000,
                    detail=str(e),
                    checked_at=datetime.now(timezone.utc).isoformat()
                ))

    async def check_event_flow(self):
        """Is the monitoring system actually processing events?"""
        try:
            r = aioredis.from_url(self.redis_url, socket_timeout=5)
            last_event_ts = await r.get("monitoring:last_event_timestamp")
            await r.close()

            if last_event_ts is None:
                self.results.append(HealthCheck(
                    component="event_flow",
                    status="degraded",
                    latency_ms=0,
                    detail="No events ever processed (cold start or broken)",
                    checked_at=datetime.now(timezone.utc).isoformat()
                ))
                return

            age = time.time() - float(last_event_ts)
            if age > self.stale_event_threshold_sec:
                status = "dead"
                detail = f"Last event {age:.0f}s ago (threshold: {self.stale_event_threshold_sec}s)"
            elif age > self.stale_event_threshold_sec / 2:
                status = "degraded"
                detail = f"Last event {age:.0f}s ago"
            else:
                status = "healthy"
                detail = f"Last event {age:.0f}s ago"

            self.results.append(HealthCheck(
                component="event_flow",
                status=status,
                latency_ms=0,
                detail=detail,
                checked_at=datetime.now(timezone.utc).isoformat()
            ))
        except Exception as e:
            self.results.append(HealthCheck(
                component="event_flow",
                status="dead",
                latency_ms=0,
                detail=str(e),
                checked_at=datetime.now(timezone.utc).isoformat()
            ))

    async def evaluate_and_alert(self):
        """Evaluate all checks and fire alerts for anything non-healthy."""
        dead = [r for r in self.results if r.status == "dead"]
        degraded = [r for r in self.results if r.status == "degraded"]

        if dead or degraded:
            severity = "CRITICAL" if dead else "WARNING"
            components = [r.component for r in dead + degraded]
            details = [f"  {r.component}: {r.detail}" for r in dead + degraded]

            message = (
                f"🐕 WATCHDOG {severity}\n"
                f"Components: {', '.join(components)}\n"
                + "\n".join(details)
            )
            logger.warning(message)

            # Alert via the monitoring system itself (if alive)
            # Also write to a failover file that an external cron can pick up
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(
                        self.alert_webhook,
                        json={"severity": severity, "source": "watchdog", "message": message},
                        timeout=aiohttp.ClientTimeout(total=5)
                    )
            except Exception:
                # Monitoring system is probably dead — write failover alert
                with open("/alerts/watchdog_failover.json", "a") as f:
                    json.dump({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "severity": severity,
                        "checks": [asdict(r) for r in dead + degraded]
                    }, f)
                    f.write("\n")

    async def get_health_summary(self) -> dict:
        """HTTP endpoint response for external health checks."""
        return {
            "status": "healthy" if all(r.status == "healthy" for r in self.results) else "degraded",
            "checks": [asdict(r) for r in self.results],
            "checked_at": datetime.now(timezone.utc).isoformat()
        }


async def health_endpoint(request):
    """HTTP health endpoint for external uptime monitors to ping."""
    summary = await watchdog.get_health_summary()
    status_code = 200 if summary["status"] == "healthy" else 503
    return web.json_response(summary, status=status_code)


if __name__ == "__main__":
    from aiohttp import web
    watchdog = MonitoringWatchdog()

    app = web.Application()
    app.router.add_get("/health", health_endpoint)

    async def start_watchdog(app):
        app["watchdog_task"] = asyncio.create_task(watchdog.run())

    async def stop_watchdog(app):
        app["watchdog_task"].cancel()

    app.on_startup.append(start_watchdog)
    app.on_cleanup.append(stop_watchdog)

    web.run_app(app, host="0.0.0.0", port=8888)
```

#### 2.2 Watchdog Docker Compose

```yaml
  watchdog:
    build: ./watchdog
    restart: always
    depends_on:
      - redis
      - monitoring
    volumes:
      - watchdog_alerts:/alerts
    ports:
      - "8888:8888"
    environment:
      REDIS_URL: "redis://redis:6379"
      MONITORING_URL: "http://monitoring:8000"
      PROMETHEUS_URL: "http://prometheus:9090"
      GRAFANA_URL: "http://grafana:3000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8888/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### 2.3 External Uptime Monitor (Docker)

```yaml
  # Runs OUTSIDE the main stack — monitors the watchdog itself
  uptime-kuma:
    image: louislam/uptime-kuma:1
    volumes:
      - uptime_kuma_data:/app/data
    ports:
      - "3001:3001"
    restart: always
    # Configure via UI:
    #   - Monitor watchdog at http://watchdog:8888/health (expect 200)
    #   - Monitor grafana at http://grafana:3000/api/health
    #   - Monitor prometheus at http://prometheus:9090/-/healthy
    #   - Alert via Telegram/email if any goes down
```

---

## Gap 3: No Log Aggregation — Structured Logging + Loki Pipeline

### Problem
Logs are written to stdout with Python's default `logger`. No structured format, no centralized collection, no search, no retention policy. Debugging requires `docker logs | grep`.

### Solution: Structured JSON Logging + Loki + Promtail

#### 3.1 Structured Logging Standard

```python
# alpha_stack/logging_config.py
"""
Standard structured logging configuration for all Alpha Stack components.
Every log line is JSON with correlation IDs for distributed tracing.
"""

import logging
import json
import sys
import traceback
from datetime import datetime, timezone
from contextvars import ContextVar
from typing import Optional

# Context vars for correlation across async calls
current_trade_id: ContextVar[Optional[str]] = ContextVar('current_trade_id', default=None)
current_event_id: ContextVar[Optional[str]] = ContextVar('current_event_id', default=None)
current_agent_id: ContextVar[Optional[str]] = ContextVar('current_agent_id', default=None)
current_session_id: ContextVar[Optional[str]] = ContextVar('current_session_id', default=None)


class StructuredJsonFormatter(logging.Formatter):
    """Outputs each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.thread,
        }

        # Add correlation IDs if set
        trade_id = current_trade_id.get()
        if trade_id:
            log_entry["trade_id"] = trade_id
        event_id = current_event_id.get()
        if event_id:
            log_entry["event_id"] = event_id
        agent_id = current_agent_id.get()
        if agent_id:
            log_entry["agent_id"] = agent_id
        session_id = current_session_id.get()
        if session_id:
            log_entry["session_id"] = session_id

        # Add extra fields from the caller
        if hasattr(record, 'extra_data') and isinstance(record.extra_data, dict):
            log_entry["extra"] = record.extra_data

        # Add exception info
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }

        # Add stack info if present
        if record.stack_info:
            log_entry["stack_info"] = record.stack_info

        return json.dumps(log_entry, default=str, ensure_ascii=False)


def setup_structured_logging(
    service_name: str,
    level: int = logging.INFO,
    json_output: bool = True
):
    """
    Configure structured logging for a service.

    Usage:
        setup_structured_logging("trade_monitor")
        logger = logging.getLogger(__name__)
        logger.info("Trade opened", extra={"extra_data": {"pair": "EURUSD", "lot": 0.1}})
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if json_output:
        handler.setFormatter(StructuredJsonFormatter())
    else:
        # Human-readable for local dev
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        ))

    root.addHandler(handler)

    # Suppress noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    logger = logging.getLogger(service_name)
    logger.info(f"Structured logging initialized for {service_name}")
    return logger


# Convenience context manager for trade-scoped logging
import contextlib

@contextlib.contextmanager
def trade_context(trade_id: str, agent_id: str = None, session_id: str = None):
    """Set correlation context for a trade operation."""
    t_token = current_trade_id.set(trade_id)
    a_token = current_agent_id.set(agent_id) if agent_id else None
    s_token = current_session_id.set(session_id) if session_id else None
    try:
        yield
    finally:
        current_trade_id.reset(t_token)
        if a_token:
            current_agent_id.reset(a_token)
        if s_token:
            current_session_id.reset(s_token)
```

#### 3.2 Log Schema Standard

Every log line MUST be a JSON object with these fields:

```json
{
  "timestamp": "2026-07-11T15:30:00.123456Z",
  "level": "INFO|WARNING|ERROR|CRITICAL|DEBUG",
  "logger": "alpha_stack.trade_monitor",
  "message": "Trade opened: EURUSD LONG 0.1 lot",
  "module": "trade_monitor",
  "function": "open_trade",
  "line": 142,
  "trade_id": "T-20260711-001",
  "event_id": "E-abc123",
  "agent_id": "agent_trend_v2",
  "session_id": "S-live-001",
  "extra": {
    "pair": "EURUSD",
    "direction": "LONG",
    "lot_size": 0.1,
    "entry_price": 1.08542
  }
}
```

#### 3.3 Loki + Promtail Configuration

```yaml
# docker-compose.logging.yml

services:
  loki:
    image: grafana/loki:2.9.4
    ports:
      - "3100:3100"
    volumes:
      - ./loki/loki-config.yml:/etc/loki/local-config.yaml
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    restart: unless-stopped

  promtail:
    image: grafana/promtail:2.9.4
    volumes:
      - ./promtail/promtail-config.yml:/etc/promtail/config.yml
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    command: -config.file=/etc/promtail/config.yml
    restart: unless-stopped
    depends_on:
      - loki
```

```yaml
# loki/loki-config.yml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: "2026-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 90d          # 90 days hot storage
  max_query_length: 721h         # 30 days max query range
  ingestion_rate_mb: 10
  per_stream_rate_limit: 5MB
  per_stream_rate_limit_burst: 15MB

compactor:
  working_directory: /loki/compactor
  compaction_interval: 10m
  retention_enabled: true
  retention_delete_delay: 2h
  delete_request_store: filesystem

# Retention by label — longer for audit/trade logs
overrides:
  "default":
    retention_period: 90d
```

```yaml
# promtail/promtail-config.yml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  # Docker container logs — auto-discover all Alpha Stack containers
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 15s
        filters:
          - name: label
            values: ["logging=enabled"]
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'
      - source_labels: ['__meta_docker_container_label_logging_service']
        target_label: 'service'
      - source_labels: ['__meta_docker_container_label_logging_component']
        target_label: 'component'
    pipeline_stages:
      # Parse JSON structured logs
      - json:
          expressions:
            level: level
            logger: logger
            trade_id: trade_id
            event_id: event_id
            agent_id: agent_id
            message: message
            service: service
      - labels:
          level:
          logger:
          trade_id:
          agent_id:
      # Drop DEBUG in production (saves storage)
      - match:
          selector: '{level="DEBUG"}'
          action: drop
      # Extract error patterns for alerting
      - match:
          selector: '{level=~"ERROR|CRITICAL"}'
          stages:
            - metrics:
                log_errors_total:
                  type: Counter
                  description: "Total error log lines"
                  source: level
                  config:
                    action: inc

  # Application-specific log files (if using file output)
  - job_name: alpha_stack_app
    static_configs:
      - targets: [localhost]
        labels:
          job: alpha_stack
          __path__: /var/log/alpha_stack/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            trade_id: trade_id
            message: message
      - labels:
          level:
          trade_id:
```

#### 3.4 Log-Based Alerting Rules

```yaml
# prometheus/alerting/log_alerts.yml
# These use Loki as a datasource in Grafana alerting

groups:
  - name: log_alerts
    interval: 1m
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate({job="alpha_stack"} |= "ERROR" [5m])) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Error log rate > 0.1/sec over 5 minutes"

      - alert: CriticalLogEvent
        expr: |
          count_over_time({job="alpha_stack"} |= "CRITICAL" [5m]) > 0
        labels:
          severity: critical
        annotations:
          summary: "CRITICAL log events detected"

      - alert: UnhandledException
        expr: |
          count_over_time({job="alpha_stack"} |~ "Traceback|UnhandledException|FATAL" [5m]) > 0
        labels:
          severity: critical
        annotations:
          summary: "Unhandled exception in application logs"

      - alert: TradeProcessingStalled
        expr: |
          absent_over_time({job="alpha_stack", component="trade_monitor"} |= "trade" [10m])
        labels:
          severity: warning
        annotations:
          summary: "No trade processing logs in 10 minutes — possible stall"
```

#### 3.5 Retention Policy

| Log Type | Hot (Loki) | Warm (S3/GCS) | Cold (Archive) |
|----------|-----------|---------------|----------------|
| Application logs | 30 days | 90 days | 1 year |
| Trade audit logs | 90 days | 1 year | 7 years (regulatory) |
| Security audit logs | 90 days | 2 years | Indefinite |
| Notification logs | 30 days | 90 days | 1 year |
| Debug logs | 7 days | — | — |

---

## Gap 4: No Event Bus Health Monitoring — Redis Streams

### Problem
Redis Streams is the backbone of the entire system. If consumers fall behind or stop processing, data staleness silently corrupts every monitoring metric. No one notices until a trade goes wrong.

### Solution: Stream Lag Monitor + Consumer Group Health + DLQ

#### 4.1 Redis Streams Health Monitor

```python
# alpha_stack/monitors/event_bus_monitor.py
"""
Monitors Redis Streams health:
- Consumer group lag per stream
- Pending message count (stalled messages)
- Consumer throughput (events/sec)
- Dead letter queue depth
- Stream length growth rate
"""

import asyncio
import redis.asyncio as aioredis
import time
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger("alpha_stack.event_bus_monitor")

@dataclass
class StreamHealth:
    stream: str
    length: int
    first_entry_ts: Optional[float]
    last_entry_ts: Optional[float]
    groups: list[dict]
    consumer_lag: dict[str, int]  # group_name -> lag
    pending_count: dict[str, int]  # group_name -> pending
    throughput_per_min: float
    health: str  # "healthy", "degraded", "critical"

@dataclass
class EventBusHealth:
    streams: list[StreamHealth]
    dlq_depth: int
    total_throughput: float
    overall_health: str
    checked_at: str


class EventBusHealthMonitor:
    CRITICAL_STREAMS = [
        "stream:market_data",
        "stream:trade_events",
        "stream:monitoring_events",
        "stream:position_updates",
        "stream:risk_events",
        "stream:notifications",
    ]

    # Thresholds
    LAG_WARNING = 500        # messages behind
    LAG_CRITICAL = 2000      # messages behind — system is stalling
    STALLED_CONSUMER_SEC = 60 # consumer idle for > 60s = stalled
    DLQ_WARNING = 10         # dead letter queue depth
    DLQ_CRITICAL = 100       # DLQ growing = systemic failure

    def __init__(self, redis_url: str = "redis://redis:6379"):
        self.redis_url = redis_url
        self._r: Optional[aioredis.Redis] = None
        self._prev_lengths: dict[str, tuple[float, int]] = {}  # stream -> (timestamp, length)

    async def get_health(self) -> EventBusHealth:
        if not self._r:
            self._r = aioredis.from_url(self.redis_url, decode_responses=True)

        streams = []
        total_throughput = 0.0

        for stream_name in self.CRITICAL_STREAMS:
            try:
                sh = await self._check_stream(stream_name)
                streams.append(sh)
                total_throughput += sh.throughput_per_min
            except Exception as e:
                logger.error(f"Failed to check stream {stream_name}: {e}")
                streams.append(StreamHealth(
                    stream=stream_name,
                    length=0,
                    first_entry_ts=None,
                    last_entry_ts=None,
                    groups=[],
                    consumer_lag={},
                    pending_count={},
                    throughput_per_min=0,
                    health="critical"
                ))

        # Check dead letter queue
        dlq_depth = 0
        try:
            dlq_depth = await self._r.xlen("stream:dead_letter")
        except Exception:
            pass  # DLQ stream doesn't exist yet — fine

        # Determine overall health
        overall = "healthy"
        critical_streams = [s for s in streams if s.health == "critical"]
        degraded_streams = [s for s in streams if s.health == "degraded"]

        if critical_streams or dlq_depth >= self.DLQ_CRITICAL:
            overall = "critical"
        elif degraded_streams or dlq_depth >= self.DLQ_WARNING:
            overall = "degraded"

        return EventBusHealth(
            streams=streams,
            dlq_depth=dlq_depth,
            total_throughput=total_throughput,
            overall_health=overall,
            checked_at=datetime.now(timezone.utc).isoformat()
        )

    async def _check_stream(self, stream_name: str) -> StreamHealth:
        now = time.time()
        length = await self._r.xlen(stream_name)

        # Calculate throughput
        throughput = 0.0
        if stream_name in self._prev_lengths:
            prev_ts, prev_len = self._prev_lengths[stream_name]
            dt = now - prev_ts
            if dt > 0:
                throughput = (length - prev_len) / dt * 60  # per minute
        self._prev_lengths[stream_name] = (now, length)

        # Get first/last entry timestamps
        first_entry_ts = None
        last_entry_ts = None
        if length > 0:
            first = await self._r.xrange(stream_name, count=1)
            last = await self._r.xrevrange(stream_name, count=1)
            if first:
                first_entry_ts = float(first[0][1].get("_ts", 0))
            if last:
                last_entry_ts = float(last[0][1].get("_ts", 0))

        # Check consumer groups
        groups_info = []
        consumer_lag = {}
        pending_count = {}
        health = "healthy"

        try:
            groups = await self._r.xinfo_groups(stream_name)
            for g in groups:
                group_name = g.get("name", "unknown")
                lag = g.get("lag", 0)
                pending = g.get("pending", 0)
                consumers = g.get("consumers", 0)
                last_delivered_ts = g.get("last-delivered-id", "0-0")

                consumer_lag[group_name] = lag
                pending_count[group_name] = pending

                groups_info.append({
                    "name": group_name,
                    "consumers": consumers,
                    "lag": lag,
                    "pending": pending,
                    "last_delivered_id": last_delivered_ts,
                })

                # Evaluate health per group
                if lag >= self.LAG_CRITICAL:
                    health = "critical"
                elif lag >= self.LAG_WARNING and health != "critical":
                    health = "degraded"

                if consumers == 0 and length > 0:
                    health = "critical"

        except aioredis.exceptions.ResponseError:
            pass  # No consumer groups — not an error for some streams

        return StreamHealth(
            stream=stream_name,
            length=length,
            first_entry_ts=first_entry_ts,
            last_entry_ts=last_entry_ts,
            groups=groups_info,
            consumer_lag=consumer_lag,
            pending_count=pending_count,
            throughput_per_min=throughput,
            health=health
        )

    async def export_prometheus_metrics(self) -> dict:
        """Export metrics in Prometheus format for scraping."""
        health = await self.get_health()
        metrics = {}

        for s in health.streams:
            prefix = f"event_bus_{s.stream.replace(':', '_').replace('stream_', '')}"
            metrics[f"{prefix}_length"] = s.length
            metrics[f"{prefix}_throughput_per_min"] = s.throughput_per_min

            for group_name, lag in s.consumer_lag.items():
                safe_group = group_name.replace(".", "_").replace("-", "_")
                metrics[f"{prefix}_lag_{safe_group}"] = lag

            for group_name, pending in s.pending_count.items():
                safe_group = group_name.replace(".", "_").replace("-", "_")
                metrics[f"{prefix}_pending_{safe_group}"] = pending

        metrics["event_bus_dlq_depth"] = health.dlq_depth
        metrics["event_bus_total_throughput_per_min"] = health.total_throughput

        return metrics
```

#### 4.2 Dead Letter Queue (DLQ) Implementation

```python
# alpha_stack/dlq.py
"""
Dead Letter Queue for failed event processing.
Events that fail after max retries are moved here for manual inspection.
"""

import redis.asyncio as aioredis
import json
import logging
import time
from typing import Optional

logger = logging.getLogger("alpha_stack.dlq")


class DeadLetterQueue:
    DLQ_STREAM = "stream:dead_letter"
    MAX_RETRIES = 3

    def __init__(self, redis: aioredis.Redis):
        self._r = redis

    async def publish(
        self,
        original_stream: str,
        original_event_id: str,
        event_data: dict,
        error: str,
        retry_count: int,
        consumer_group: str
    ):
        """Move a failed event to the DLQ."""
        dlq_entry = {
            "original_stream": original_stream,
            "original_event_id": original_event_id,
            "error": error,
            "retry_count": str(retry_count),
            "consumer_group": consumer_group,
            "failed_at": str(time.time()),
            "event_data": json.dumps(event_data),
        }

        msg_id = await self._r.xadd(self.DLQ_STREAM, dlq_entry)
        logger.warning(
            f"Event moved to DLQ: stream={original_stream}, "
            f"event_id={original_event_id}, error={error}, dlq_id={msg_id}"
        )

        # Increment Prometheus-style counter
        await self._r.incr("metrics:dlq:total_count")
        await self._r.incr(f"metrics:dlq:by_stream:{original_stream}")

        return msg_id

    async def get_depth(self) -> int:
        """Get current DLQ depth."""
        return await self._r.xlen(self.DLQ_STREAM)

    async def peek(self, count: int = 10) -> list[dict]:
        """Peek at recent DLQ entries without consuming."""
        entries = await self._r.xrevrange(self.DLQ_STREAM, count=count)
        results = []
        for entry_id, data in entries:
            results.append({
                "id": entry_id,
                "original_stream": data.get("original_stream"),
                "error": data.get("error"),
                "failed_at": data.get("failed_at"),
                "event_data": json.loads(data.get("event_data", "{}")),
            })
        return results

    async def replay(self, event_id: str, target_stream: str) -> bool:
        """Replay a DLQ event back to its original stream."""
        # Read from DLQ
        entries = await self._r.xrange(self.DLQ_STREAM, min=event_id, max=event_id, count=1)
        if not entries:
            return False

        _, data = entries[0]
        event_data = json.loads(data.get("event_data", "{}"))

        # Re-publish to target stream
        new_id = await self._r.xadd(target_stream, event_data)

        # Remove from DLQ
        await self._r.xdel(self.DLQ_STREAM, event_id)

        logger.info(f"Replayed DLQ event {event_id} to {target_stream} as {new_id}")
        return True

    async def cleanup(self, max_age_sec: int = 604800):
        """Remove DLQ entries older than max_age (default 7 days)."""
        cutoff = str(int(time.time()) - max_age_sec)
        # XTRIM by min ID
        trimmed = await self._r.xtrim(self.DLQ_STREAM, minid=f"{cutoff}-0")
        if trimmed > 0:
            logger.info(f"Cleaned up {trimmed} old DLQ entries")
```

#### 4.3 Event Bus Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Alpha Stack — Event Bus Health",
    "rows": [
      {
        "title": "Stream Lengths",
        "panels": [
          {
            "title": "Messages per Stream",
            "type": "graph",
            "targets": [
              {"expr": "event_bus_stream_market_data_length", "legendFormat": "market_data"},
              {"expr": "event_bus_stream_trade_events_length", "legendFormat": "trade_events"},
              {"expr": "event_bus_stream_monitoring_events_length", "legendFormat": "monitoring"},
              {"expr": "event_bus_stream_position_updates_length", "legendFormat": "positions"}
            ]
          },
          {
            "title": "Throughput (events/min)",
            "type": "graph",
            "targets": [
              {"expr": "event_bus_total_throughput_per_min", "legendFormat": "Total"}
            ]
          }
        ]
      },
      {
        "title": "Consumer Lag",
        "panels": [
          {
            "title": "Consumer Lag by Stream",
            "type": "graph",
            "targets": [
              {"expr": "event_bus_stream_*_lag_*", "legendFormat": "{{stream}} / {{group}}"}
            ],
            "thresholds": [
              {"value": 0, "color": "green"},
              {"value": 500, "color": "yellow"},
              {"value": 2000, "color": "red"}
            ]
          },
          {
            "title": "Pending Messages (Stalled)",
            "type": "graph",
            "targets": [
              {"expr": "event_bus_stream_*_pending_*", "legendFormat": "{{stream}} / {{group}}"}
            ]
          }
        ]
      },
      {
        "title": "Dead Letter Queue",
        "panels": [
          {
            "title": "DLQ Depth",
            "type": "stat",
            "targets": [{"expr": "event_bus_dlq_depth"}],
            "thresholds": [
              {"value": 0, "color": "green"},
              {"value": 10, "color": "yellow"},
              {"value": 100, "color": "red"}
            ]
          }
        ]
      }
    ]
  }
}
```

---

## Gap 5: No Database Health Monitoring

### Problem
TimescaleDB holds all trade history, P&L, reconciliation records. Connection pool exhaustion, slow queries, or disk-full events would silently paralyze the system.

### Solution: PostgreSQL Exporter + Custom Metrics + Grafana Alerts

#### 5.1 PostgreSQL Exporter Queries

```yaml
# postgres_exporter/custom_queries.yml
# Additional queries beyond what postgres_exporter provides natively

pg_replication:
  query: |
    SELECT
      CASE WHEN NOT pg_is_in_recovery() THEN 0
           ELSE GREATEST(0, EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())))
      END AS lag_seconds
  metrics:
    - lag_seconds:
        usage: "GAUGE"
        description: "Replication lag in seconds"

pg_long_running_queries:
  query: |
    SELECT count(*) AS count
    FROM pg_stat_activity
    WHERE state = 'active'
      AND query_start < now() - interval '30 seconds'
      AND query NOT LIKE '%pg_stat%'
  metrics:
    - count:
        usage: "GAUGE"
        description: "Queries running longer than 30 seconds"

pg_table_sizes:
  query: |
    SELECT
      schemaname,
      relname AS table_name,
      pg_total_relation_size(relid) AS total_bytes,
      pg_relation_size(relid) AS table_bytes,
      pg_indexes_size(relid) AS index_bytes
    FROM pg_stat_user_tables
    ORDER BY pg_total_relation_size(relid) DESC
    LIMIT 20
  metrics:
    - schemaname:
        usage: "LABEL"
    - table_name:
        usage: "LABEL"
    - total_bytes:
        usage: "GAUGE"
        description: "Total table size including indexes"
    - table_bytes:
        usage: "GAUGE"
    - index_bytes:
        usage: "GAUGE"

pg_hypertable_health:
  query: |
    SELECT
      hypertable_name,
      num_chunks,
      compression_enabled,
      CASE WHEN compression_enabled THEN
        (SELECT count(*) FROM timescaledb_information.compressed_chunk_stats
         WHERE hypertable_name = h.hypertable_name AND compression_status = 'Compressed')
      ELSE 0 END AS compressed_chunks
    FROM timescaledb_information.hypertables h
  metrics:
    - hypertable_name:
        usage: "LABEL"
    - num_chunks:
        usage: "GAUGE"
        description: "Number of hypertable chunks"
    - compression_enabled:
        usage: "GAUGE"
        description: "Whether compression is enabled (1=yes)"
    - compressed_chunks:
        usage: "GAUGE"
        description: "Number of compressed chunks"

pg_lock_monitor:
  query: |
    SELECT
      mode,
      count(*) AS count
    FROM pg_locks
    WHERE NOT granted
    GROUP BY mode
  metrics:
    - mode:
        usage: "LABEL"
    - count:
        usage: "GAUGE"
        description: "Locks waiting (not granted)"

pg_cache_hit_ratio:
  query: |
    SELECT
      sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) AS ratio
    FROM pg_statio_user_tables
    WHERE heap_blks_hit + heap_blks_read > 0
  metrics:
    - ratio:
        usage: "GAUGE"
        description: "Buffer cache hit ratio (should be > 0.99)"
```

#### 5.2 Database Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Alpha Stack — Database Health",
    "rows": [
      {
        "title": "Connection Pool",
        "panels": [
          {
            "title": "Active vs Max Connections",
            "type": "gauge",
            "targets": [
              {
                "expr": "pg_stat_activity_count",
                "legendFormat": "Active"
              },
              {
                "expr": "pg_settings_max_connections",
                "legendFormat": "Max"
              }
            ]
          },
          {
            "title": "Connection Pool Utilization %",
            "type": "gauge",
            "targets": [
              {
                "expr": "pg_stat_activity_count / pg_settings_max_connections * 100",
                "legendFormat": "Pool Usage"
              }
            ],
            "thresholds": [
              {"value": 0, "color": "green"},
              {"value": 60, "color": "yellow"},
              {"value": 80, "color": "red"}
            ]
          },
          {
            "title": "Connections by State",
            "type": "piechart",
            "targets": [
              {
                "expr": "pg_stat_activity_count",
                "legendFormat": "{{state}}"
              }
            ]
          }
        ]
      },
      {
        "title": "Query Performance",
        "panels": [
          {
            "title": "Query Latency Distribution",
            "type": "heatmap",
            "targets": [
              {
                "expr": "rate(pg_stat_activity_query_duration_seconds_bucket[5m])",
                "legendFormat": "{{le}}"
              }
            ]
          },
          {
            "title": "Slow Queries (> 30s)",
            "type": "stat",
            "targets": [
              {
                "expr": "pg_long_running_queries_count",
                "legendFormat": "Count"
              }
            ],
            "thresholds": [
              {"value": 0, "color": "green"},
              {"value": 3, "color": "yellow"},
              {"value": 10, "color": "red"}
            ]
          },
          {
            "title": "Cache Hit Ratio",
            "type": "gauge",
            "targets": [
              {
                "expr": "pg_cache_hit_ratio_ratio",
                "legendFormat": "Hit Ratio"
              }
            ],
            "thresholds": [
              {"value": 0.95, "color": "red"},
              {"value": 0.99, "color": "yellow"},
              {"value": 0.999, "color": "green"}
            ]
          },
          {
            "title": "Locks Waiting",
            "type": "stat",
            "targets": [
              {
                "expr": "pg_lock_monitor_count",
                "legendFormat": "{{mode}}"
              }
            ],
            "thresholds": [
              {"value": 0, "color": "green"},
              {"value": 5, "color": "red"}
            ]
          }
        ]
      },
      {
        "title": "TimescaleDB",
        "panels": [
          {
            "title": "Hypertable Chunk Count",
            "type": "graph",
            "targets": [
              {
                "expr": "pg_hypertable_health_num_chunks",
                "legendFormat": "{{hypertable_name}}"
              }
            ]
          },
          {
            "title": "Compression Status",
            "type": "table",
            "targets": [
              {
                "expr": "pg_hypertable_health_compressed_chunks / pg_hypertable_health_num_chunks * 100",
                "legendFormat": "{{hypertable_name}} % compressed"
              }
            ]
          },
          {
            "title": "Database Size Growth",
            "type": "graph",
            "targets": [
              {
                "expr": "pg_database_size_bytes / 1024 / 1024 / 1024",
                "legendFormat": "{{datname}} (GB)"
              }
            ]
          },
          {
            "title": "Replication Lag",
            "type": "graph",
            "targets": [
              {
                "expr": "pg_replication_lag_seconds",
                "legendFormat": "Lag (s)"
              }
            ],
            "thresholds": [
              {"value": 0, "color": "green"},
              {"value": 30, "color": "yellow"},
              {"value": 300, "color": "red"}
            ]
          }
        ]
      }
    ]
  }
}
```

#### 5.3 Database Alert Rules

```yaml
groups:
  - name: database_critical
    interval: 30s
    rules:
      - alert: DBConnectionPoolExhausted
        expr: pg_stat_activity_count / pg_settings_max_connections * 100 > 80
        for: 2m
        labels:
          severity: critical
          component: database
        annotations:
          summary: "DB connection pool > 80%"
          description: "{{ $value }}% of max connections used. New connections will be rejected."

      - alert: DBSlowQueries
        expr: pg_long_running_queries_count > 5
        for: 3m
        labels:
          severity: warning
          component: database
        annotations:
          summary: "{{ $value }} queries running > 30 seconds"

      - alert: DBCacheHitRatioLow
        expr: pg_cache_hit_ratio_ratio < 0.95
        for: 5m
        labels:
          severity: warning
          component: database
        annotations:
          summary: "DB cache hit ratio {{ $value }} (should be > 0.99)"
          description: "Low cache hit ratio indicates missing indexes or insufficient shared_buffers."

      - alert: DBLockContention
        expr: pg_lock_monitor_count > 10
        for: 2m
        labels:
          severity: critical
          component: database
        annotations:
          summary: "{{ $value }} locks waiting — possible deadlock"

      - alert: DBDiskFull
        expr: |
          (node_filesystem_size_bytes{mountpoint="/data"} - node_filesystem_avail_bytes{mountpoint="/data"})
          / node_filesystem_size_bytes{mountpoint="/data"} * 100 > 85
        for: 5m
        labels:
          severity: critical
          component: database
        annotations:
          summary: "DB disk usage > 85%"

      - alert: TimescaleDBChunkUncompressed
        expr: |
          pg_hypertable_health_num_chunks - pg_hypertable_health_compressed_chunks > 50
        for: 10m
        labels:
          severity: warning
          component: database
        annotations:
          summary: "More than 50 uncompressed chunks — compression job may have failed"

      - alert: DBReplicationLag
        expr: pg_replication_lag_seconds > 300
        for: 5m
        labels:
          severity: critical
          component: database
        annotations:
          summary: "Replication lag > 5 minutes"
```

---

## Gap 6: Slippage Threshold — Pair-Specific

### Problem
A hardcoded 2.0 pip slippage threshold generates false positives on volatile pairs (GBP/JPY, XAU/USD where 2 pips is noise) and misses real issues on calm pairs (EUR/USD where 2 pips is massive).

### Solution: Dynamic Pair-Specific Slippage Thresholds

#### 6.1 Architecture

```
               ┌─────────────────────────┐
               │  Pair Config Registry   │
               │  (Redis + DB fallback)  │
               └───────────┬─────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐     ┌──────▼──────┐   ┌─────▼─────┐
    │ Base    │     │  Dynamic    │   │  Session   │
    │ Spread  │     │  Multiplier │   │  Modifier  │
    │ per Pair│     │  (Vol Adj)  │   │            │
    └────┬────┘     └──────┬──────┘   └─────┬─────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Threshold  │
                    │  Calculator │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Slippage    │
                    │ Evaluator   │
                    └─────────────┘
```

#### 6.2 Pair Configuration Registry

```python
# alpha_stack/monitors/slippage_config.py
"""
Pair-specific slippage thresholds.

Core concept: slippage is measured as a MULTIPLE of the pair's average spread,
not as an absolute pip value.

- EUR/USD avg spread: 0.8 pips → 2.0 pips slippage = 2.5x spread = excessive
- XAU/USD avg spread: 25 pips → 2.0 pips slippage = 0.08x spread = completely normal
- GBP/JPY avg spread: 3.0 pips → 2.0 pips slippage = 0.67x spread = normal

Using spread multiples normalizes across all pairs.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import redis.asyncio as aioredis

logger = logging.getLogger("alpha_stack.slippage_config")


class SlippageSeverity(Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    EXCESSIVE = "excessive"
    CRITICAL = "critical"


@dataclass
class PairSlippageConfig:
    pair: str
    pip_value: float               # Value of 1 pip (0.0001 for EUR/USD, 0.01 for USD/JPY, 0.01 for XAU/USD)
    avg_spread_pips: float         # Rolling average spread in pips
    avg_spread_updated_at: float   # Timestamp of last spread update
    slippage_multiplier_warning: float = 2.0    # 2x spread = WARNING
    slippage_multiplier_excessive: float = 3.5   # 3.5x spread = EXCESSIVE
    slippage_multiplier_critical: float = 5.0    # 5x spread = CRITICAL (likely broker issue)
    session_multipliers: dict = field(default_factory=lambda: {
        "asian": 1.3,      # Asian session: wider spreads normal
        "london": 1.0,     # London: baseline
        "new_york": 1.0,   # NY: baseline
        "off_hours": 1.5,  # Off-hours: wider spreads
        "rollover": 2.0,   # Day rollover: widest spreads
    })

    @property
    def warning_threshold_pips(self) -> float:
        return self.avg_spread_pips * self.slippage_multiplier_warning

    @property
    def excessive_threshold_pips(self) -> float:
        return self.avg_spread_pips * self.slippage_multiplier_excessive

    @property
    def critical_threshold_pips(self) -> float:
        return self.avg_spread_pips * self.slippage_multiplier_critical

    def evaluate(self, slippage_pips: float, session: str = "london") -> SlippageSeverity:
        """Evaluate slippage severity for this pair."""
        session_mult = self.session_multipliers.get(session, 1.0)
        adj_warning = self.warning_threshold_pips * session_mult
        adj_excessive = self.excessive_threshold_pips * session_mult
        adj_critical = self.critical_threshold_pips * session_mult

        if slippage_pips >= adj_critical:
            return SlippageSeverity.CRITICAL
        elif slippage_pips >= adj_excessive:
            return SlippageSeverity.EXCESSIVE
        elif slippage_pips >= adj_warning:
            return SlippageSeverity.ELEVATED
        else:
            return SlippageSeverity.NORMAL


# Default configurations for common forex pairs
DEFAULT_PAIR_CONFIGS: dict[str, PairSlippageConfig] = {
    # Major pairs — tight spreads
    "EURUSD": PairSlippageConfig(
        pair="EURUSD", pip_value=0.0001, avg_spread_pips=0.8,
        avg_spread_updated_at=0, slippage_multiplier_warning=2.5,
        slippage_multiplier_excessive=4.0, slippage_multiplier_critical=6.0
    ),
    "GBPUSD": PairSlippageConfig(
        pair="GBPUSD", pip_value=0.0001, avg_spread_pips=1.2,
        avg_spread_updated_at=0
    ),
    "USDJPY": PairSlippageConfig(
        pair="USDJPY", pip_value=0.01, avg_spread_pips=0.9,
        avg_spread_updated_at=0
    ),
    "USDCHF": PairSlippageConfig(
        pair="USDCHF", pip_value=0.0001, avg_spread_pips=1.5,
        avg_spread_updated_at=0
    ),
    "AUDUSD": PairSlippageConfig(
        pair="AUDUSD", pip_value=0.0001, avg_spread_pips=1.3,
        avg_spread_updated_at=0
    ),
    "USDCAD": PairSlippageConfig(
        pair="USDCAD", pip_value=0.0001, avg_spread_pips=1.6,
        avg_spread_updated_at=0
    ),
    "NZDUSD": PairSlippageConfig(
        pair="NZDUSD", pip_value=0.0001, avg_spread_pips=1.8,
        avg_spread_updated_at=0
    ),

    # Cross pairs — moderate spreads
    "GBPJPY": PairSlippageConfig(
        pair="GBPJPY", pip_value=0.01, avg_spread_pips=3.0,
        avg_spread_updated_at=0, slippage_multiplier_warning=2.0,
        slippage_multiplier_excessive=3.0, slippage_multiplier_critical=5.0
    ),
    "EURJPY": PairSlippageConfig(
        pair="EURJPY", pip_value=0.01, avg_spread_pips=2.0,
        avg_spread_updated_at=0
    ),
    "EURAUD": PairSlippageConfig(
        pair="EURAUD", pip_value=0.0001, avg_spread_pips=2.5,
        avg_spread_updated_at=0
    ),
    "EURGBP": PairSlippageConfig(
        pair="EURGBP", pip_value=0.0001, avg_spread_pips=1.2,
        avg_spread_updated_at=0
    ),

    # Metals — wide spreads, high volatility
    "XAUUSD": PairSlippageConfig(
        pair="XAUUSD", pip_value=0.01, avg_spread_pips=25.0,
        avg_spread_updated_at=0, slippage_multiplier_warning=2.0,
        slippage_multiplier_excessive=3.0, slippage_multiplier_critical=4.0
    ),
    "XAGUSD": PairSlippageConfig(
        pair="XAGUSD", pip_value=0.01, avg_spread_pips=30.0,
        avg_spread_updated_at=0, slippage_multiplier_warning=2.0,
        slippage_multiplier_excessive=3.0, slippage_multiplier_critical=4.0
    ),

    # Crypto (if traded)
    "BTCUSD": PairSlippageConfig(
        pair="BTCUSD", pip_value=0.01, avg_spread_pips=50.0,
        avg_spread_updated_at=0, slippage_multiplier_warning=2.5,
        slippage_multiplier_excessive=4.0, slippage_multiplier_critical=6.0
    ),
}


class SlippageConfigRegistry:
    """
    Manages pair-specific slippage configurations.
    - Loads defaults on startup
    - Updates avg_spread from live tick data (rolling 1-hour window)
    - Persists to Redis with DB fallback
    - Exposes to Prometheus for alerting
    """

    REDIS_KEY_PREFIX = "config:slippage:"
    SPREAD_HISTORY_KEY = "data:spread_history:"
    SPREAD_WINDOW_SEC = 3600  # 1-hour rolling window

    def __init__(self, redis: aioredis.Redis):
        self._r = redis
        self._configs: dict[str, PairSlippageConfig] = {}
        self._loaded = False

    async def initialize(self):
        """Load configs from Redis or fall back to defaults."""
        for pair, default_config in DEFAULT_PAIR_CONFIGS.items():
            stored = await self._r.get(f"{self.REDIS_KEY_PREFIX}{pair}")
            if stored:
                data = json.loads(stored)
                self._configs[pair] = PairSlippageConfig(**data)
            else:
                self._configs[pair] = default_config
                await self._save(pair, default_config)
        self._loaded = True
        logger.info(f"Loaded {len(self._configs)} pair slippage configs")

    def get_config(self, pair: str) -> Optional[PairSlippageConfig]:
        return self._configs.get(pair.upper())

    def evaluate_slippage(
        self,
        pair: str,
        slippage_pips: float,
        session: str = "london"
    ) -> tuple[SlippageSeverity, PairSlippageConfig]:
        """
        Evaluate whether slippage is excessive for this pair.

        Returns:
            (severity, config) tuple
        """
        config = self.get_config(pair)
        if not config:
            # Unknown pair — use conservative defaults
            logger.warning(f"No slippage config for {pair}, using generic thresholds")
            config = PairSlippageConfig(
                pair=pair, pip_value=0.0001,
                avg_spread_pips=2.0, avg_spread_updated_at=0
            )

        severity = config.evaluate(slippage_pips, session)
        return severity, config

    async def record_spread(self, pair: str, spread_pips: float):
        """
        Record a spread observation and update rolling average.
        Called on every tick or at regular intervals.
        """
        key = f"{self.SPREAD_HISTORY_KEY}{pair}"
        now = time.time()

        # Add to sorted set (score = timestamp, value = spread)
        await self._r.zadd(key, {f"{spread_pips}:{now}": now})

        # Remove entries outside the window
        cutoff = now - self.SPREAD_WINDOW_SEC
        await self._r.zremrangebyscore(key, "-inf", cutoff)

        # Calculate new average
        entries = await self._r.zrangebyscore(key, cutoff, now)
        if len(entries) >= 10:  # Minimum observations before updating
            spreads = [float(e.decode().split(":")[0]) for e in entries]
            new_avg = sum(spreads) / len(spreads)

            config = self.get_config(pair)
            if config:
                config.avg_spread_pips = round(new_avg, 4)
                config.avg_spread_updated_at = now
                await self._save(pair, config)
                logger.debug(f"Updated {pair} avg spread: {new_avg:.4f} pips ({len(spreads)} obs)")

    async def _save(self, pair: str, config: PairSlippageConfig):
        """Persist config to Redis."""
        data = {
            "pair": config.pair,
            "pip_value": config.pip_value,
            "avg_spread_pips": config.avg_spread_pips,
            "avg_spread_updated_at": config.avg_spread_updated_at,
            "slippage_multiplier_warning": config.slippage_multiplier_warning,
            "slippage_multiplier_excessive": config.slippage_multiplier_excessive,
            "slippage_multiplier_critical": config.slippage_multiplier_critical,
            "session_multipliers": config.session_multipliers,
        }
        await self._r.set(
            f"{self.REDIS_KEY_PREFIX}{pair}",
            json.dumps(data),
            ex=86400 * 30  # 30-day TTL — refreshed on each update
        )

    def get_all_thresholds(self) -> dict:
        """Return all pair thresholds for dashboard display."""
        result = {}
        for pair, config in self._configs.items():
            result[pair] = {
                "avg_spread_pips": config.avg_spread_pips,
                "warning_pips": config.warning_threshold_pips,
                "excessive_pips": config.excessive_threshold_pips,
                "critical_pips": config.critical_threshold_pips,
                "updated_at": config.avg_spread_updated_at,
            }
        return result
```

#### 6.3 Integration with Trade Monitor

```python
# In the existing trade monitoring code, replace the hardcoded threshold:

# BEFORE (broken):
# if slippage_pips > 2.0:
#     alert("Excessive slippage", severity="WARNING")

# AFTER (pair-specific):
async def check_slippage(
    pair: str,
    slippage_pips: float,
    session: str,
    trade_id: str,
    slippage_registry: SlippageConfigRegistry,
    notification_manager
):
    severity, config = slippage_registry.evaluate_slippage(pair, slippage_pips, session)

    if severity == SlippageSeverity.NORMAL:
        return  # No alert needed

    severity_map = {
        SlippageSeverity.ELEVATED: "WARNING",
        SlippageSeverity.EXCESSIVE: "HIGH",
        SlippageSeverity.CRITICAL: "CRITICAL",
    }

    alert_severity = severity_map[severity]

    await notification_manager.send_alert(
        severity=alert_severity,
        title=f"Slippage {severity.value.upper()}: {pair}",
        message=(
            f"Trade {trade_id}: {slippage_pips:.1f} pip slippage on {pair}\n"
            f"Avg spread: {config.avg_spread_pips:.1f} pips\n"
            f"Threshold: {config.excessive_threshold_pips:.1f} pips "
            f"({config.slippage_multiplier_excessive}x spread)\n"
            f"Session: {session}"
        ),
        data={
            "pair": pair,
            "slippage_pips": slippage_pips,
            "avg_spread_pips": config.avg_spread_pips,
            "threshold_pips": config.excessive_threshold_pips,
            "session": session,
            "trade_id": trade_id,
        }
    )
```

#### 6.4 Grafana Panel for Slippage Thresholds

```json
{
  "title": "Slippage Thresholds by Pair",
  "type": "table",
  "targets": [
    {
      "expr": "slippage_config_avg_spread_pips",
      "legendFormat": "{{pair}}",
      "format": "table",
      "instant": true
    }
  ],
  "columns": [
    {"text": "Pair", "value": "pair"},
    {"text": "Avg Spread", "value": "avg_spread_pips"},
    {"text": "Warning (pips)", "value": "warning"},
    {"text": "Excessive (pips)", "value": "excessive"},
    {"text": "Critical (pips)", "value": "critical"}
  ],
  "fieldConfig": {
    "overrides": [
      {
        "matcher": {"id": "byName", "options": "Avg Spread"},
        "properties": [
          {"id": "custom.width", "value": 100},
          {"id": "unit", "value": "pips"}
        ]
      }
    ]
  }
}
```

#### 6.5 Example Thresholds (What Changes)

| Pair | Avg Spread | Old Threshold (2.0 pips) | New Warning | New Excessive | New Critical |
|------|-----------|-------------------------|-------------|---------------|--------------|
| EUR/USD | 0.8 pips | 2.0 pips (2.5x) | 2.0 pips (2.5x) | 3.2 pips (4.0x) | 4.8 pips (6.0x) |
| GBP/JPY | 3.0 pips | 2.0 pips (0.67x) ❌ | 6.0 pips (2.0x) | 9.0 pips (3.0x) | 15.0 pips (5.0x) |
| XAU/USD | 25.0 pips | 2.0 pips (0.08x) ❌ | 50.0 pips (2.0x) | 75.0 pips (3.0x) | 100.0 pips (4.0x) |
| GBP/USD | 1.2 pips | 2.0 pips (1.67x) | 2.4 pips (2.0x) | 4.2 pips (3.5x) | 6.0 pips (5.0x) |

The old system would fire an alert on every XAU/USD trade (2 pips < 25 pip spread is totally normal) and miss real EUR/USD slippage issues (2 pips on a 0.8 pip spread is 2.5x — clearly problematic).

---

## Implementation Priority

| Phase | Gap | Effort | Dependencies |
|-------|-----|--------|-------------|
| **Week 1** | Gap 1: Infrastructure monitoring (Prometheus exporters + dashboard) | 2-3 days | Docker access |
| **Week 1-2** | Gap 5: Database health monitoring (postgres_exporter + custom queries) | 1-2 days | Gap 1 (Prometheus) |
| **Week 2** | Gap 4: Event bus health (Redis Streams monitor + DLQ) | 2 days | Gap 1 (Prometheus) |
| **Week 2** | Gap 6: Slippage thresholds (pair-specific config) | 1-2 days | None (standalone) |
| **Week 3** | Gap 3: Log aggregation (Loki + Promtail + structured logging) | 2-3 days | Gap 1 (Grafana) |
| **Week 3-4** | Gap 2: Self-monitoring (Watchdog + canary) | 2-3 days | All other gaps |

---

## Verification Checklist

After implementation, verify each gap is closed:

- [ ] **Gap 1:** Redis/DB/container metrics visible in Grafana "Infrastructure Health" dashboard
- [ ] **Gap 1:** Alerts fire when Redis memory > 75%, DB connections > 80%, disk > 80%
- [ ] **Gap 2:** Watchdog container running and checking all components every 30s
- [ ] **Gap 2:** Watchdog `/health` endpoint returns 200 when all systems are up
- [ ] **Gap 2:** Watchdog writes failover alert when monitoring container is unreachable
- [ ] **Gap 3:** All containers shipping JSON-structured logs to Loki
- [ ] **Gap 3:** `trade_id` correlation works across log search in Grafana
- [ ] **Gap 3:** Error rate > 0.1/sec triggers Loki-based alert
- [ ] **Gap 4:** Consumer lag visible per stream in "Event Bus Health" dashboard
- [ ] **Gap 4:** Alert fires when any consumer lag > 500 messages
- [ ] **Gap 4:** DLQ depth visible and alerts at > 10 entries
- [ ] **Gap 5:** DB connection pool, query latency, cache hit ratio visible in "Database Health" dashboard
- [ ] **Gap 5:** Compression job health monitored (uncompressed chunk count)
- [ ] **Gap 5:** Lock contention alerts work
- [ ] **Gap 6:** EUR/USD with 2.0 pip slippage → ELEVATED alert (was the same threshold before)
- [ ] **Gap 6:** XAU/USD with 2.0 pip slippage → NO alert (was incorrectly alerting before)
- [ ] **Gap 6:** XAU/USD with 75 pip slippage → EXCESSIVE alert
- [ ] **Gap 6:** Spread averages update from live tick data
- [ ] **Gap 6:** Session-specific multipliers apply correctly (Asian session gets 1.3x wider thresholds)

---

*Generated: 2026-07-11*
*Based on: review_monitoring.md*
*Ready for implementation.*
