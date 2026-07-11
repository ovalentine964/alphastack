# Alpha Stack — Monitoring Architecture Review

> **Version:** 1.0 · **Date:** 2026-07-11 · **Reviewer:** Monitoring & Alerting Review Agent
> **Scope:** Completeness review of monitoring, alerting, dashboards, notifications, and log aggregation
> **Documents Reviewed:** `architecture_trade_monitoring.md`, `architecture_channels.md`, `architecture_risk.md`, `architecture_system.md`, `architecture_trading_engine.md`, `architecture_data_storage.md`, `architecture_security.md`

---

## Executive Summary

The monitoring architecture is **exceptionally thorough for trade-level monitoring** — position tracking, P&L, anomaly detection, reconciliation, and agent attribution are all well-designed with production-grade code. However, there are **significant gaps in infrastructure monitoring, log aggregation, and observability of the monitoring system itself**. The notification system via channels is well-specified but the monitoring of that notification system is circular and under-specified.

**Overall Rating: 7.5/10** — Strong on trade domain monitoring, weak on infrastructure and self-monitoring.

---

## 1. Critical Component Coverage

### 1.1 Components That ARE Monitored ✅

| Component | Monitoring Quality | Notes |
|-----------|-------------------|-------|
| **Open Positions** | ⭐⭐⭐⭐⭐ | Real-time P&L, MAE/MFE, duration, sub-states. Excellent. |
| **Trade Lifecycle** | ⭐⭐⭐⭐⭐ | Full provenance chain from signal → entry → management → exit. Best-in-class. |
| **P&L & Equity** | ⭐⭐⭐⭐⭐ | Tick-level equity curve, HWM tracking, drawdown stages. |
| **Risk Utilization** | ⭐⭐⭐⭐ | Margin, exposure, drawdown stages, circuit breakers all tracked. |
| **Agent Performance** | ⭐⭐⭐⭐⭐ | Signal quality scores, contribution maps, conflict detection. Outstanding. |
| **Anomaly Detection** | ⭐⭐⭐⭐ | Execution, pattern, and data anomalies with statistical baselines. |
| **Trade Reconciliation** | ⭐⭐⭐⭐⭐ | 5-min cycle, phantom detection, equity drift, auto-resolve. Critical safety net. |
| **Circuit Breakers** | ⭐⭐⭐⭐ | Four-layer system with clear trip conditions and auto-actions. |
| **Notification Delivery** | ⭐⭐⭐ | Rate limiting, severity routing, retry logic. Basic but functional. |

### 1.2 Components That Are NOT Monitored ❌

| Component | Gap Severity | Impact |
|-----------|-------------|--------|
| **Redis (Event Bus)** | 🔴 CRITICAL | No monitoring of Redis health, memory, connection count, stream lag, consumer group health. If Redis goes down, the entire monitoring system is blind. |
| **TimescaleDB/PostgreSQL** | 🔴 CRITICAL | No database health monitoring — connection pool exhaustion, query latency, disk space, replication lag, hypertable chunk health. |
| **Python Process Health** | 🔴 CRITICAL | No monitoring of the monitoring container itself — memory leaks, goroutine/task counts, event loop blocking, GC pressure. |
| **Network Connectivity** | 🟡 HIGH | Broker connection health is referenced in circuit breakers but no dedicated network monitoring (latency to broker, packet loss, DNS resolution). |
| **Data Feed Quality** | 🟡 HIGH | Price feed staleness is checked but no monitoring of feed completeness (missing candles), data source uptime, or cross-source validation. |
| **Disk Space** | 🟡 HIGH | TimescaleDB will grow. No disk space alerts, no monitoring of compression job success, no retention policy health checks. |
| **Container/Docker Health** | 🟡 HIGH | No container restart counting, OOM kill detection, resource limit proximity alerts. |
| **Prometheus Itself** | 🟠 MEDIUM | Who monitors the monitor? No self-health check for Prometheus scraping, alertmanager delivery, or Grafana availability. |
| **Backup Status** | 🟠 MEDIUM | `architecture_data_storage.md` defines backup strategy but no monitoring of backup success/failure/recency. |
| **SSL/TLS Certificates** | 🟠 MEDIUM | No certificate expiry monitoring for API endpoints, webhook URLs, or broker connections. |
| **Grafana Dashboard Health** | 🟠 MEDIUM | No monitoring of dashboard load times, query failures, or datasource connectivity from Grafana's perspective. |

---

## 2. Alerting Thresholds Assessment

### 2.1 Trade Monitoring Thresholds

| Threshold | Value | Assessment | Recommendation |
|-----------|-------|------------|----------------|
| Excessive slippage alert | > 2.0 pips | ⚠️ Too absolute | Should be pair-specific. 2 pips on EUR/USD is excessive; 2 pips on GBP/JPY is normal. Use multiplier of average spread per pair. |
| Spread blowout | 3x average | ✅ Good | Dynamic baseline approach is correct. |
| Execution latency spike | 10x average | ✅ Good | Appropriate for detecting broker issues. |
| Win rate degradation | < 45% over 20 trades | ⚠️ Slightly aggressive | 20 trades is a small sample. Consider requiring 30+ trades before alerting to reduce false positives. |
| Negative expectancy | < 0 over 20 trades | ✅ Good | Correct to alert early on this. CRITICAL severity is appropriate. |
| Win/loss streak | 3 consecutive losses | ⚠️ Could cause alert fatigue | 3 losses in a row is normal variance with 65% win rate. Consider threshold of 4-5 for WARNING. |
| Pair concentration | > 60% of trades | ✅ Good | Appropriate diversification check. |
| Revenge trading detection | < 5 min between trades | ✅ Good | Smart behavioral check. |
| Position count mismatch | Any difference | ✅ Good | CRITICAL is correct — any mismatch is a potential phantom position. |
| Equity divergence | > 1% | ✅ Good | Appropriate threshold for P&L calculation errors. |

### 2.2 Risk Management Thresholds

| Threshold | Value | Assessment | Recommendation |
|-----------|-------|------------|----------------|
| Daily loss limit | 4% | ✅ Good | Standard for prop firm-level risk. |
| Weekly loss limit | 8% | ✅ Good | 2x daily is reasonable. |
| Monthly loss limit | 12% | ✅ Good | 3x daily, allows recovery. |
| Max drawdown halt | 18% | ✅ Good | Hard stop is appropriate. |
| Margin utilization warning | 25% | ✅ Good | Early warning before 30% limit. |
| VIX caution | 30 | ✅ Good | Appropriate for forex-focused system. |
| Correlation spike | 0.80 | ✅ Good | High correlation detection is critical. |
| Connectivity timeout | 30 seconds | ⚠️ Aggressive | 30 seconds could be a brief network hiccup. Consider 60s with a retry before closing positions. |

### 2.3 Missing Thresholds

| Missing Threshold | Severity | Recommendation |
|-------------------|----------|----------------|
| **Database connection pool utilization** | 🔴 CRITICAL | Alert at 80% pool usage. Connection exhaustion = system paralysis. |
| **Redis memory usage** | 🔴 CRITICAL | Alert at 75% maxmemory. Eviction = data loss. |
| **Event bus consumer lag** | 🔴 CRITICAL | Alert if any consumer falls behind by > 1000 events or > 30 seconds. |
| **Disk space** | 🟡 HIGH | Alert at 80% and 90% for all volumes, especially TimescaleDB data directory. |
| **API response time (dashboard)** | 🟡 HIGH | Alert if p95 latency > 2 seconds. |
| **Telegram bot delivery failure rate** | 🟡 HIGH | Alert if > 10% of messages fail delivery in 1 hour. |
| **TimescaleDB chunk count** | 🟠 MEDIUM | Alert if uncompressed chunks exceed expected count (compression job failure). |
| **Container restart count** | 🟠 MEDIUM | Alert on any restart — indicates instability. |

---

## 3. Grafana Dashboard Design

### 3.1 Current Dashboard Specification

The `architecture_trade_monitoring.md` defines two dashboards:

1. **Real-Time Overview** — Equity curve, open positions, drawdown gauge, risk exposure
2. **Performance Analytics** — Rolling win rate, R-multiple distribution, breakdowns, MAE/MFE scatter, heatmap

### 3.2 Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Trade-level panels** | ⭐⭐⭐⭐⭐ | Comprehensive. Equity curve, position table, drawdown gauge, exposure. |
| **Performance analytics** | ⭐⭐⭐⭐⭐ | Excellent breakdowns by pair, session, grade, agent. MAE/MFE and heatmap are institutional-grade. |
| **Refresh rates** | ⭐⭐⭐⭐ | 1s for real-time, 60s for analytics. Appropriate. |
| **Risk dashboard** | ⭐⭐⭐ | Risk metrics are defined in code but not explicitly in Grafana panel spec. |

### 3.3 Missing Dashboards

| Missing Dashboard | Priority | Contents |
|-------------------|----------|----------|
| **Infrastructure Health** | 🔴 CRITICAL | Redis memory/connections, DB connections/query latency, disk space, CPU/memory per container, network latency to broker. |
| **System Observability** | 🔴 CRITICAL | Event bus throughput, consumer lag, message processing latency, error rates per component. |
| **Notification Audit** | 🟡 HIGH | Messages sent by channel, delivery success rate, acknowledgment rate, rate limit hits, quiet hours queue depth. |
| **Agent Health** | 🟡 HIGH | Per-agent signal generation rate, processing latency, error rate, last signal time (detect silent agents). |
| **Reconciliation History** | 🟠 MEDIUM | Timeline of reconciliation results, mismatch frequency, auto-resolve success rate. |
| **Data Quality** | 🟠 MEDIUM | Price feed freshness, missing candle detection, cross-source validation results. |

### 3.4 Dashboard Design Gaps

1. **No alerting rules in Grafana** — The spec defines panels but no Grafana alert rules. Grafana's native alerting should be configured for infrastructure metrics (Prometheus datasource).
2. **No dashboard variables/filters** — No mention of Grafana template variables for pair, session, time range, agent filtering. These are essential for drill-down.
3. **No annotation events** — Trade entries/exits should be annotated on the equity curve for visual correlation.
4. **No row-level organization** — Panels should be grouped into collapsible rows (Overview, Risk, Performance, Infrastructure).

---

## 4. Notification Channel Configuration

### 4.1 Channel Coverage ✅

| Channel | Configuration | Assessment |
|---------|--------------|------------|
| **Telegram** | Primary cockpit, inline keyboards, rich media | ✅ Well-specified. Bot API, chat ID whitelist, inline buttons. |
| **Discord** | Community channel, threads, embeds | ✅ Well-specified. Guild + role-based access. |
| **WhatsApp** | Mobile alerts, text-only | ✅ Well-specified. Twilio integration, simplified formatting. |
| **Signal** | Encrypted channel | ⚠️ Mentioned but no implementation details (Matrix bridge?). |
| **Email** | Formal reports, PDFs | ✅ Specified for reports. SMTP configuration. |
| **SMS** | Emergency fallback | ✅ Via Twilio for P0/EMERGENCY events. |

### 4.2 Notification Routing ✅

The priority-based routing (P0-P3) is well-designed:

- **P0 (CRITICAL):** ALL channels + repeat + SMS fallback — ✅ Correct for black swan/circuit breaker
- **P1 (HIGH):** Primary + WhatsApp — ✅ Correct for trade entries/exits
- **P2 (MEDIUM):** Primary only, batched — ✅ Correct for management updates
- **P3 (LOW):** Scheduled delivery — ✅ Correct for reports

### 4.3 Notification Gaps

| Gap | Severity | Detail |
|-----|----------|--------|
| **No notification delivery confirmation** | 🟡 HIGH | The system tracks `sent` but not `delivered` or `read`. Telegram API provides delivery status — should be tracked. |
| **No dead-letter queue** | 🟡 HIGH | Failed notifications after all retries should be stored for manual review, not silently dropped. |
| **Ack timeout escalation is incomplete** | 🟡 HIGH | P0 events escalate to SMS after 5 minutes, but what if SMS also fails? No further escalation path (phone call? second contact?). |
| **Quiet hours override granularity** | 🟠 MEDIUM | Can override per-pair but not per-event-type. E.g., "alert me on reconciliation mismatches at night but not trade entries." |
| **No notification testing/dry-run** | 🟠 MEDIUM | No way to test notification pipeline without triggering real events. Should have `/test-alert` command. |
| **Channel health monitoring** | 🟠 MEDIUM | No monitoring of whether each channel's bot/API is actually operational. Telegram bot could be banned; Twilio account could be suspended. |

### 4.4 Cross-Reference with `architecture_channels.md`

The channels document specifies a richer notification model than the trade monitoring document implements:

- **Channels doc:** 5 channels (Telegram, Discord, WhatsApp, Signal, Email) with distinct roles
- **Trade monitoring doc:** Only Telegram + SMS + Dashboard explicitly implemented in code
- **Gap:** Discord, WhatsApp, and Signal integrations are architected but not implemented in the monitoring notification manager. The `NotificationManager` class only has `_send_telegram` and `_send_sms` methods.

---

## 5. Log Aggregation Assessment

### 5.1 Current State

| Aspect | Status | Detail |
|--------|--------|--------|
| **Application logs** | ⚠️ Minimal | Python `logger` is used throughout but no structured logging specification. No JSON log format defined. |
| **Audit trail** | ✅ Good | Trade events, reconciliation records, anomaly logs all stored in database tables. |
| **Notification log** | ✅ Basic | Redis list `monitoring:notifications:log` stores recent notifications. |
| **Error tracking** | ⚠️ Mentioned | Sentry is listed in tech stack but no integration code or configuration specified. |
| **Centralized logging** | ❌ Missing | ELK/Loki is mentioned in `architecture_system.md` Layer 0 but no implementation in monitoring architecture. |

### 5.2 Log Aggregation Gaps

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| **No structured logging standard** | 🔴 CRITICAL | All components should use JSON-structured logs with correlation IDs (trade_id, event_id). Define a log schema. |
| **No log aggregation pipeline** | 🔴 CRITICAL | Loki or ELK should be configured to collect logs from all containers. No log shipping, parsing, or indexing is specified. |
| **No log retention policy** | 🟡 HIGH | How long are logs kept? Application logs, audit logs, and notification logs should have defined retention. |
| **No log-based alerting** | 🟡 HIGH | Errors in logs should trigger alerts. E.g., `ERROR` count > 10/min → WARNING. Unhandled exceptions → CRITICAL. |
| **No request tracing** | 🟡 HIGH | No distributed tracing (OpenTelemetry/Jaeger). When a trade fails, tracing the full request path across components is impossible. |
| **No log search capability** | 🟠 MEDIUM | Without Loki/ELK, searching logs requires `docker logs` + `grep`. Not scalable. |
| **Audit log separation** | 🟠 MEDIUM | Security audit logs (auth events, credential access) should be in a separate, append-only store per `architecture_security.md`. |

---

## 6. Monitoring Gaps Summary

### 6.1 Critical Gaps (Must Fix Before Production)

| # | Gap | Risk | Recommendation |
|---|-----|------|----------------|
| **G1** | No infrastructure monitoring (Redis, DB, containers) | Silent infrastructure failure → system blindness | Deploy Prometheus exporters for Redis, PostgreSQL, Docker. Create infrastructure Grafana dashboard. |
| **G2** | No self-monitoring of the monitoring system | Monitoring system failure goes undetected | Implement watchdog: external health check that alerts if monitoring container is down or event bus has no consumers. |
| **G3** | No log aggregation pipeline | Cannot diagnose issues across components | Deploy Loki + Promtail or ELK. Define structured JSON log format. Ship logs from all containers. |
| **G4** | No event bus health monitoring | Redis Streams consumer lag → stale data | Monitor Redis Streams consumer group lag, pending message count, and consumer throughput. |
| **G5** | No database health monitoring | Connection pool exhaustion, disk full, slow queries → total failure | Deploy `postgres_exporter` and `timescaledb` extension metrics. Alert on connection count, query duration, disk usage. |
| **G6** | Slippage threshold is absolute (2.0 pips) | False alerts on volatile pairs, missed alerts on calm pairs | Make threshold pair-specific: `pair_avg_spread * multiplier`. |

### 6.2 High-Priority Gaps (Should Fix Before Scale)

| # | Gap | Risk | Recommendation |
|---|-----|------|----------------|
| **G7** | No distributed tracing | Cannot trace a trade event through the full pipeline | Implement OpenTelemetry instrumentation across all components. |
| **G8** | Notification delivery not confirmed | Silent notification failure → trader unaware of critical events | Track Telegram `message_id` return, implement delivery status checks. |
| **G9** | No dead-letter queue for failed notifications | Failed alerts are lost after retries | Store failed notifications in database for manual review and replay. |
| **G10** | Discord/WhatsApp/Signal not implemented in monitoring code | Only Telegram works for real-time alerts | Extend `NotificationManager` with channel adapters per `architecture_channels.md`. |
| **G11** | No backup monitoring | Backup failure → unrecoverable data loss | Monitor backup job execution, last successful backup time, backup size trends. |
| **G12** | No certificate expiry monitoring | Expired TLS → API/broker connectivity failure | Add certificate expiry check to Prometheus or scheduled health check. |

### 6.3 Medium-Priority Gaps (Should Fix Before Institutional)

| # | Gap | Risk | Recommendation |
|---|-----|------|----------------|
| **G13** | No Grafana alert rules defined | Infrastructure alerts only via code, not native Grafana | Define Grafana alert rules for Prometheus datasource metrics. |
| **G14** | No notification pipeline testing | Cannot verify alerts work without real events | Add `/test-alert [severity]` command and scheduled canary notifications. |
| **G15** | No monitoring of monitoring dashboards | Grafana itself could be down | External uptime check on Grafana endpoint. |
| **G16** | No data quality monitoring beyond staleness | Missing candles, corrupted data, source disagreement | Implement cross-source validation and completeness checks. |
| **G17** | No capacity planning metrics | Cannot predict when resources will be exhausted | Track and trend: DB size growth, Redis memory growth, event throughput growth. |
| **G18** | Win rate alert threshold too sensitive (20-trade window) | False positives during normal variance | Increase to 30-trade minimum before alerting, or use Bayesian credible interval. |

---

## 7. Architecture Strengths (What's Done Well)

1. **Trade provenance chain** — Every trade carries full agent signal history. This is exceptional for debugging and optimization.
2. **Reconciliation engine** — 5-minute automated reconciliation with phantom detection is a critical safety feature that many retail systems lack.
3. **Anomaly detection with adaptive baselines** — Statistical baselines that auto-update from recent data prevent static thresholds from becoming stale.
4. **Agent contribution tracking** — Attribution of P&L to individual agents with quality scores is sophisticated and enables data-driven agent tuning.
5. **Event-driven architecture** — Redis Streams as the event bus is the right choice. Decoupled, replayable, auditable.
6. **Rate limiting on notifications** — Preventing alert fatigue is as important as alerting itself. The per-severity rate limits are well-calibrated.
7. **Quiet hours** — Respecting trader sleep while still escalating P0 events is the right balance.
8. **Progressive autonomy model** — The 4-level trust system with explicit progression criteria is a thoughtful approach to automation risk.

---

## 8. Recommended Action Plan

### Phase 1: Critical Infrastructure Monitoring (Week 1-2)

```
1. Deploy Prometheus + exporters:
   - redis_exporter (Redis health, memory, connections, stream lag)
   - postgres_exporter (connections, query latency, disk, replication)
   - node_exporter (CPU, memory, disk, network)
   - cadvisor (container metrics)

2. Create Infrastructure Grafana dashboard:
   - Row: Redis (memory, connections, stream consumer lag, key count)
   - Row: PostgreSQL/TimescaleDB (connections, query p95, disk, chunk health)
   - Row: Containers (CPU, memory, restarts, OOM kills)
   - Row: Network (broker latency, packet loss, DNS)

3. Define Grafana alert rules:
   - Redis memory > 75% → WARNING
   - DB connections > 80% pool → CRITICAL
   - Disk > 80% → WARNING, > 90% → CRITICAL
   - Container restart > 0 → WARNING
   - Event bus consumer lag > 1000 → CRITICAL
```

### Phase 2: Log Aggregation & Observability (Week 3-4)

```
1. Deploy Loki + Promtail (or ELK):
   - Ship logs from all containers
   - Define JSON structured log format with correlation IDs
   - Set retention policy (30 days hot, 90 days warm, 1 year cold)

2. Instrument OpenTelemetry:
   - Trace trade events through full pipeline
   - Export to Jaeger or Tempo

3. Configure Sentry properly:
   - DSN for each component
   - Alert rules for unhandled exceptions
   - Source map upload for stack traces

4. Define log-based alerting:
   - ERROR count > 10/min → WARNING
   - Unhandled exception → CRITICAL
   - Specific error patterns → custom alerts
```

### Phase 3: Notification Hardening (Week 5-6)

```
1. Implement delivery confirmation for Telegram
2. Create dead-letter queue for failed notifications
3. Extend NotificationManager with Discord/WhatsApp/Signal adapters
4. Add /test-alert command
5. Implement canary notifications (hourly health check message)
6. Add channel health monitoring (bot API reachability)
```

### Phase 4: Dashboard Completion (Week 7-8)

```
1. Create System Observability dashboard (event bus, consumer health)
2. Create Notification Audit dashboard (delivery rates, channel health)
3. Create Agent Health dashboard (signal rates, latency, errors)
4. Add Grafana template variables (pair, session, time range, agent)
5. Add trade annotations on equity curve
6. Create Data Quality dashboard (feed freshness, completeness)
```

---

## 9. Monitoring Architecture Maturity Assessment

| Dimension | Current Level | Target Level | Gap |
|-----------|--------------|--------------|-----|
| **Trade Monitoring** | Level 4 (Optimized) | Level 4 | ✅ At target |
| **Risk Monitoring** | Level 3 (Defined) | Level 4 | 🟡 Need automated risk limit tuning feedback |
| **Infrastructure Monitoring** | Level 1 (Initial) | Level 4 | 🔴 Major gap — need Prometheus + Grafana |
| **Log Aggregation** | Level 1 (Initial) | Level 3 | 🔴 Need Loki/ELK + structured logging |
| **Alerting** | Level 3 (Defined) | Level 4 | 🟡 Need Grafana alerts + dead-letter queue |
| **Notification System** | Level 3 (Defined) | Level 4 | 🟡 Need delivery confirmation + multi-channel |
| **Self-Monitoring** | Level 0 (None) | Level 3 | 🔴 Need watchdog + health checks |
| **Distributed Tracing** | Level 0 (None) | Level 3 | 🟡 Need OpenTelemetry |

**Maturity Model:** 0=None, 1=Initial, 2=Managed, 3=Defined, 4=Optimized

---

## 10. Conclusion

The Alpha Stack monitoring architecture is **best-in-class for trade domain monitoring**. The provenance chain, reconciliation engine, agent attribution, and anomaly detection are features that most retail trading systems — and many institutional ones — lack.

The primary blind spots are **infrastructure and self-monitoring**. The system monitors everything about trades but nothing about the systems that do the monitoring. This is a classic "who watches the watchmen" problem.

**Priority 1** must be deploying Prometheus + Grafana for infrastructure metrics and Loki for log aggregation. Without these, a Redis memory exhaustion or database disk full event would silently cripple the entire monitoring system while the trader believes everything is fine.

**Priority 2** must be notification hardening — delivery confirmation, dead-letter queue, and multi-channel implementation. The notification system is the trader's lifeline; it must be bulletproof.

With these gaps addressed, Alpha Stack's monitoring architecture would be genuinely institutional-grade.

---

*Review completed: 2026-07-11*
*Next review recommended: After Phase 1 and Phase 2 implementation*
*Reviewer: Monitoring & Alerting Review Agent*
