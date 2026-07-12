# Alpha Stack — Error Handling & Recovery Architecture Review

> **Version:** 1.0 · **Date:** 2026-07-11 · **Reviewer:** Error Handling Review Agent  
> **Scope:** Comprehensive review of error handling, circuit breakers, disaster recovery, failure modes, and self-healing across the entire Alpha Stack system  
> **Documents Reviewed:** `architecture_system.md`, `architecture_risk.md`, `fix_broker_disconnect.md`, `architecture_deployment.md` (missing)

---

## Executive Summary

The Alpha Stack has an **exceptionally strong** error handling architecture for a trading system. The layered defense model (position → portfolio → regime → system), the four-layer circuit breaker cascade, and the broker disconnection fixes are all well-designed and largely complete. However, there are **12 material gaps** that should be addressed before live capital deployment, ranging from missing error propagation in the AlphaStack pipeline to incomplete disaster recovery documentation.

**Overall Grade: B+ (Strong, with specific gaps)**

| Category | Grade | Notes |
|----------|-------|-------|
| Error catching at every layer | B | Strong at L0-L2, gaps in L3 (AlphaStack pipeline) and L4 (agent orchestration) |
| Circuit breaker cascading | A- | Four-layer design is correct; minor reset race conditions |
| Disaster recovery completeness | B- | Good broker failover; missing infrastructure DR, data recovery, and partial state recovery |
| Failure mode documentation | A- | Extensive; missing ~4 scenarios in agent/orchestration layer |
| Self-healing capability | B | Broker reconnection is self-healing; drawdown recovery, agent crash recovery, and data pipeline recovery are not |
| Error handling gaps | 12 material gaps identified | See Section 7 for full gap list |

---

## 1. Error Catching at Every Layer

### 1.1 Layer-by-Layer Assessment

| Layer | Name | Error Handling | Grade | Notes |
|-------|------|---------------|-------|-------|
| **L0** | Infrastructure | ✅ Strong | A | Docker health checks, Prometheus alerts, log aggregation (Loki) |
| **L1** | Data Foundation | ✅ Strong | A- | Gap detector, outlier filter, cross-source validation, quality gates |
| **L2** | Execution & Broker | ✅ Strong | A | Full Broker Health Manager with 6 fixes (adaptive timeout, failover, zombie detection, reconciliation, degraded state, partial disconnect) |
| **L3** | Strategy & Analysis | ⚠️ Gaps | C+ | AlphaStack pipeline has no per-step error handling, no timeout enforcement, no fallback for LLM failures |
| **L4** | Orchestration | ⚠️ Gaps | B- | Agent crash recovery undefined; event bus failure recovery is "close all" (too aggressive); no agent health monitoring |
| **L5** | API Gateway | ✅ Moderate | B | JWT auth, rate limiting, CORS — but no circuit breaker for external API calls |
| **L6** | Presentation | ⚠️ Minimal | C | No offline mode, no degraded UI state, no reconnection UX |

### 1.2 Critical Finding: AlphaStack Pipeline Error Handling

The AlphaStack 16-step pipeline defines a `AlphaStackStep` abstract base class but has **no error handling contract**:

```python
class AlphaStackStep(ABC):
    @abstractmethod
    async def analyze(self, context: StrategyContext) -> StepResult:
        pass
    
    # MISSING:
    # - timeout per step (what if an LLM call hangs?)
    # - error handling contract (what does a step return on failure?)
    # - fallback behavior (skip step? use cached result? abort pipeline?)
    # - partial failure (step 5 fails — does step 6 still run?)
```

**Risk:** If Step 7 (Smart Money Concepts) calls an LLM that hangs for 60 seconds, the entire pipeline stalls. If Step 5 (S/R Detection) throws an exception, Steps 6-16 all fail — but there's no mechanism to detect or recover from this.

**Recommendation:** Add a `StepErrorHandler` interface:
- Each step must define a `timeout_seconds` (default: 30s for LLM steps, 5s for indicator steps)
- Each step must define a `on_failure` strategy: `SKIP`, `USE_CACHED`, `ABORT_PIPELINE`, `USE_DEFAULT`
- Pipeline orchestrator must catch per-step exceptions and apply the failure strategy
- All partial failures must be logged to the reasoning chain for audit

### 1.3 Critical Finding: LLM Call Error Handling

The system uses DeepSeek/Qwen for multiple agents (Strategy, News, Journal, Auditor). There is **no documented error handling for LLM API failures**:

| Failure Mode | Current Handling | Risk |
|-------------|-----------------|------|
| LLM API timeout | Undefined | Pipeline stalls indefinitely |
| LLM API rate limit (429) | Undefined | Repeated failures during high load |
| LLM returns malformed JSON | Undefined | Downstream parsing crashes |
| LLM returns empty/irrelevant response | Undefined | Garbage signals fed to risk engine |
| LLM API key expired | Undefined | Silent failure across all agents |
| LLM provider outage | Undefined | All LLM-dependent agents fail simultaneously |

**Recommendation:** Add an `LLMCallWrapper` that implements:
- Exponential backoff with jitter (3 retries max)
- Response validation (JSON schema check, relevance scoring)
- Fallback model configuration (DeepSeek → Qwen → local model)
- Circuit breaker per provider (open after 5 consecutive failures, half-open after 60s)
- Timeout enforcement (30s default, configurable per agent)

### 1.4 Finding: Event Bus Error Handling

The architecture states: "Event Bus down → CRITICAL — All communication stops → System enters safe mode: close all positions, halt trading."

This is **too aggressive**. A brief Redis blip (1-2 seconds) should not trigger a full position close. The current design has no:
- Event bus reconnection logic
- Event queuing during brief outages
- Graceful degradation (which modules can operate without the bus?)
- Partial bus failure (some streams accessible, others not)

**Recommendation:**
- Add Redis Sentinel or Redis Cluster for HA
- Implement local event buffer (in-memory queue) for brief outages (<30s)
- Define "degraded mode" where only essential events (risk, execution) are processed
- Only trigger "close all" after 60+ seconds of bus unavailability

---

## 2. Circuit Breaker Cascade Validation

### 2.1 Cascade Architecture Review

The four-layer circuit breaker system is well-designed:

```
Layer 1 (Position) → Layer 2 (Portfolio) → Layer 3 (Regime) → Layer 4 (System)
     fastest              ↓                     ↓                    slowest
   (ms-level)        (seconds)             (minutes)              (seconds-minutes)
```

**✅ Correct cascade properties:**
- Each layer is independent (can halt trading without consulting others)
- Layers are ordered by speed (fastest protection first)
- No single point of failure across layers
- Escalation is automatic; de-escalation requires sustained recovery

### 2.2 Cascade Issues Found

**Issue 1: Reset Race Condition**

When multiple breakers trip simultaneously (e.g., daily loss + VIX spike), the reset protocol doesn't define ordering. If the daily loss breaker auto-resets at 00:00 UTC but VIX is still elevated, the system could resume trading prematurely.

**Recommendation:** Add a `can_resume()` check that verifies ALL tripped breakers are clear before resuming. Implement a priority ordering for reset:
1. System-level breakers must clear first
2. Regime-level breakers must clear second
3. Portfolio-level breakers must clear third
4. Position-level breakers clear independently

**Issue 2: Breaker State Persistence**

The `CircuitBreakerSystem` stores breaker states in memory (`self.breaker_states = {}`). If the system restarts, all breaker states are lost. A system that crashed during a drawdown event could restart in GREEN stage with no memory of the crisis.

**Recommendation:** Persist breaker states to Redis with a TTL. On startup, load all active breaker states. Add a `recovery_mode` flag that loads persisted state and validates against current market conditions before clearing.

**Issue 3: Missing Circuit Breaker for Strategy Pipeline**

There is no circuit breaker for the AlphaStack pipeline itself. If the pipeline starts producing consistently bad signals (all rejected by risk agent), there's no automatic throttle. The system will keep running expensive LLM calls that produce rejected signals.

**Recommendation:** Add a "signal quality" circuit breaker:
- If >80% of signals are rejected by risk agent in the last 50 signals → pause pipeline for 1 hour
- If confidence scores are trending down for 24h → alert human
- If pipeline step failures exceed 20% → enter degraded mode (skip LLM steps, use indicator-only signals)

### 2.4 Correctness Verdict

| Layer | Cascade Correct? | Independent? | Reset Correct? | Notes |
|-------|-----------------|-------------|----------------|-------|
| Layer 1 (Position) | ✅ | ✅ | ✅ | Auto-reset on next candle |
| Layer 2 (Portfolio) | ✅ | ✅ | ⚠️ | Daily resets correctly; weekly/monthly need human |
| Layer 3 (Regime) | ✅ | ✅ | ⚠️ | VIX auto-reset is correct; correlation needs 24h |
| Layer 4 (System) | ✅ | ✅ | ⚠️ | Broker reconnect needs reconciliation first |
| Cross-layer | ⚠️ | ✅ | ❌ | No coordinated reset ordering |

---

## 3. Disaster Recovery Completeness

### 3.1 DR Coverage Matrix

| Scenario | Recovery Plan | Automated? | Grade | Notes |
|----------|--------------|------------|-------|-------|
| **Broker disconnect** | Failover to backup broker + hedge | ✅ Yes | A | Comprehensive (Fix 1-6) |
| **Broker zombie connection** | Zombie detection + failover | ✅ Yes | A | Heartbeat-based, 15s detection |
| **Position reconciliation** | Full diff + corrective actions | ✅ Yes | A | Broker = truth principle |
| **Black swan event** | Close all + cooldown + paper trade | ✅ Yes | A | 2+ trigger activation |
| **Drawdown escalation** | 5-stage progressive response | ✅ Yes | A | Automatic escalation, slow de-escalation |
| **News event** | 3-phase protocol | ✅ Yes | A- | Pre/during/post handling |
| **Data pipeline failure** | ❌ Incomplete | ❌ No | D | "Fail to last known state" is undefined |
| **Redis failure** | ❌ Missing | ❌ No | F | "Close all" is too aggressive; no HA plan |
| **TimescaleDB failure** | ❌ Missing | ❌ No | F | No documented backup/restore procedure |
| **Strategy agent crash** | ❌ Incomplete | ❌ No | D | "Existing positions continue" is correct, but restart/recovery undefined |
| **Risk agent crash** | ⚠️ Partial | ❌ No | C | "HALT ALL NEW TRADES" is correct, but restart/recovery undefined |
| **Full system restart** | ❌ Missing | ❌ No | F | No documented cold-start procedure |
| **Network partition** | ❌ Missing | ❌ No | F | Split-brain between components not addressed |
| **Cloud region failure** | ❌ Missing | ❌ No | F | DR region exists in Phase 4 diagram but no failover procedure |
| **Credential compromise** | ⚠️ Partial | ❌ No | C | Rotation mentioned but no incident response procedure |
| **Database corruption** | ❌ Missing | ❌ No | F | No backup schedule, no point-in-time recovery |

### 3.2 Critical DR Gaps

**Gap 1: Data Pipeline Failure Recovery**

The architecture says "fail to last known state" for data pipeline failure, but doesn't define:
- What "last known state" means (last candle? last tick? last hour's average?)
- How long the system can operate on stale data
- When to halt vs. continue with degraded data
- How to catch up after recovery (replay missed candles?)

**Gap 2: Infrastructure DR (Redis/DB)**

For a system that stores everything in Redis Streams and TimescaleDB:
- No Redis Sentinel/Cluster configuration for HA
- No TimescaleDB replication or backup schedule
- No documented restore procedure
- No point-in-time recovery capability
- No data integrity verification after restore

**Gap 3: Full System Restart**

No documented procedure for:
- Cold start sequence (which services start first?)
- State recovery from persistent storage
- Validation that all systems are operational before trading resumes
- Paper trading period after restart

**Gap 4: Network Partition / Split-Brain**

If the event bus (Redis) is reachable by some agents but not others:
- Risk agent might approve a trade that execution agent can't execute
- Strategy agent might generate signals that risk agent never sees
- No fencing mechanism to prevent split-brain decisions

### 3.3 Recommended DR Additions

```
PRIORITY 1 (Before live capital):
├── Redis Sentinel for event bus HA
├── TimescaleDB daily backups + WAL archiving
├── Full system restart procedure document
└── Data pipeline failure → degraded mode definition

PRIORITY 2 (Before $10K capital):
├── Database point-in-time recovery
├── Network partition handling (fencing)
├── Credential compromise incident response
└── Automated backup verification

PRIORITY 3 (Before $100K capital):
├── Cross-region failover
├── Chaos engineering test suite
├── DR drill schedule (quarterly)
└── RTO/RPO definitions per component
```

---

## 4. Failure Mode Documentation

### 4.1 Documented Failure Modes

The architecture documents cover the following failure modes extensively:

| Category | Documented Modes | Count |
|----------|-----------------|-------|
| Broker failures | Disconnect, zombie, partial, degraded, spread blowout, leverage change, maintenance | 7 |
| Market events | Black swan, flash crash, correlation convergence, VIX spike, stablecoin depeg | 5 |
| Risk events | Drawdown stages (5), circuit breakers (4 layers × multiple triggers), tail risk breach | 15+ |
| News events | Critical/high/medium/low impact, blackout protocol | 4 |
| Data quality | Gaps, outliers, cross-source inconsistency | 3 |

### 4.2 Undocumented Failure Modes

| Failure Mode | Impact | Risk Level |
|-------------|--------|-----------|
| **Agent infinite loop** | Agent consumes 100% CPU, blocks other agents | HIGH |
| **Memory leak in long-running agent** | OOM crash after days of operation | HIGH |
| **Clock skew between components** | Stale data treated as fresh; incorrect time-based decisions | MEDIUM |
| **LLM hallucination in strategy reasoning** | Bad trade with "good" reasoning chain | HIGH |
| **Event bus message ordering violation** | Risk agent processes trade proposal before position update | MEDIUM |
| **Database connection pool exhaustion** | All DB-dependent operations fail simultaneously | HIGH |
| **Docker container restart storm** | Repeated crashes consuming resources | MEDIUM |
| **Certificate expiry** | TLS connections fail; broker API calls rejected | MEDIUM |
| **Disk space exhaustion** | Logs fill disk; database writes fail | HIGH |
| **Timezone handling errors** | Economic calendar off by hours; session detection wrong | MEDIUM |
| **Integer overflow in position sizing** | Extreme values produce incorrect lot sizes | LOW |
| **Concurrent position modification** | Two agents modify the same position simultaneously | HIGH |

### 4.3 Recommended: Failure Mode Registry

Create a `failure_modes.yaml` that catalogs every known failure mode with:
- Detection method
- Impact assessment
- Automatic response
- Manual fallback
- Recovery procedure
- Test scenario

---

## 5. Self-Healing Capability Assessment

### 5.1 Self-Healing Matrix

| Component | Self-Healing? | Mechanism | Grade |
|-----------|--------------|-----------|-------|
| **Broker connection** | ✅ Yes | Reconnect + reconciliation + hedge resolution | A |
| **Zombie detection** | ✅ Yes | Ping/pong loop with auto-recovery detection | A |
| **Circuit breakers (L1-L3)** | ✅ Yes | Auto-reset after conditions normalize | A |
| **Circuit breakers (L4)** | ⚠️ Partial | Broker reconnect triggers reconciliation; other L4 breakers need manual | B |
| **Drawdown recovery** | ⚠️ Partial | De-escalation requires sustained recovery (correct), but no auto-monitoring | B |
| **Agent crash recovery** | ❌ No | No documented restart/recovery for crashed agents | F |
| **Data pipeline recovery** | ❌ No | No automatic catch-up after data gaps | F |
| **Event bus recovery** | ❌ No | No automatic reconnection or event replay | F |
| **Database recovery** | ❌ No | No automatic failover or recovery | F |
| **Configuration drift** | ❌ No | No detection of configuration changes at runtime | F |

### 5.2 Recommended Self-Healing Additions

**Agent Crash Recovery:**
```python
class AgentSupervisor:
    """Supervisor that monitors agent health and restarts crashed agents."""
    
    async def monitor_agent(self, agent_id: str):
        while True:
            health = await self.check_agent_health(agent_id)
            if health.status == 'DEAD':
                await self.restart_agent(agent_id)
                await self.replay_missed_events(agent_id)
            elif health.status == 'UNRESPONSIVE':
                await self.force_kill_and_restart(agent_id)
            await asyncio.sleep(5)
```

**Data Pipeline Catch-Up:**
```python
class DataPipelineRecovery:
    """Automatic data gap filling after pipeline recovery."""
    
    async def catch_up(self, pair: str, gap_start: datetime, gap_end: datetime):
        # 1. Detect gap boundaries
        # 2. Fetch missing data from broker API
        # 3. Validate and fill gaps
        # 4. Recalculate affected indicators
        # 5. Re-run AlphaStack pipeline for missed signals
```

---

## 6. Error Propagation Analysis

### 6.1 Error Propagation Paths

```
AlphaStack Step Failure
    │
    ├─→ [UNDEFINED] Pipeline continues with missing data?
    ├─→ [UNDEFINED] Pipeline aborts?
    └─→ [UNDEFINED] Step uses cached/default value?

Risk Agent Rejection
    │
    ├─→ ✅ Logged to journal
    ├─→ ✅ Sent back to strategy agent
    └─→ ⚠️ No mechanism to learn from rejections (feedback loop)

Broker Order Rejection
    │
    ├─→ ✅ Logged
    ├─→ ✅ Retry logic (assumed)
    └─→ ⚠️ No escalation after N retries

LLM API Failure
    │
    ├─→ [UNDEFINED] No documented handling
    └─→ Cascades to all dependent agents

Event Bus Failure
    │
    ├─→ [TOO AGGRESSIVE] Close all positions
    └─→ ⚠️ No degraded mode
```

### 6.2 Error Propagation Gaps

| Origin | Destination | Gap | Risk |
|--------|------------|-----|------|
| AlphaStack Step → Pipeline | No error propagation contract | Silent failures produce bad signals |
| LLM → Agent | No error handling wrapper | Agent crashes on API failure |
| Agent → Agent | No message delivery guarantee | Lost events during brief outages |
| Risk Rejection → Strategy | No feedback loop | Strategy doesn't learn from rejections |
| Data Quality → Pipeline | Quality gates defined but error response unclear | Bad data can still reach strategy |

---

## 7. Complete Gap Summary

### 7.1 Critical Gaps (Must Fix Before Live Capital)

| # | Gap | Impact | Recommendation |
|---|-----|--------|---------------|
| **C1** | AlphaStack pipeline has no per-step error handling | Silent failures, pipeline stalls | Add `StepErrorHandler` with timeout, fallback, and partial failure handling |
| **C2** | LLM API failures have no handling | Agent crashes, silent failures | Add `LLMCallWrapper` with retries, validation, fallback model, circuit breaker |
| **C3** | Event bus failure triggers "close all" (too aggressive) | Unnecessary position closures on brief Redis blips | Add local buffer, degraded mode, 60s threshold before close-all |
| **C4** | Breaker states not persisted across restarts | System forgets crisis state on crash | Persist to Redis; load on startup |
| **C5** | No data pipeline failure recovery | Undefined behavior when data stops | Define degraded mode, stale data policy, catch-up procedure |
| **C6** | No infrastructure DR (Redis/DB HA) | Single point of failure for all data | Add Redis Sentinel, DB replication, backup schedule |

### 7.2 High Gaps (Must Fix Before $10K Capital)

| # | Gap | Impact | Recommendation |
|---|-----|--------|---------------|
| **H1** | No agent crash recovery | Agents stay down until manual restart | Add agent supervisor with auto-restart and event replay |
| **H2** | No full system restart procedure | Undefined cold-start sequence | Document and automate startup sequence |
| **H3** | Undocumented failure modes (12 identified) | Unknown responses to common failures | Create failure mode registry |
| **H4** | No circuit breaker for strategy pipeline quality | Bad signals keep generating indefinitely | Add signal quality circuit breaker |
| **H5** | No breaker reset ordering | Premature resume after multi-breaker trip | Add coordinated reset with priority ordering |
| **H6** | No configuration drift detection | Runtime config changes go unnoticed | Add config hash verification on heartbeat |

### 7.3 Medium Gaps (Must Fix Before $100K Capital)

| # | Gap | Impact | Recommendation |
|---|-----|--------|---------------|
| **M1** | No network partition handling | Split-brain decisions | Add fencing mechanism |
| **M2** | No cross-region failover procedure | Region failure = total loss | Document and test DR region failover |
| **M3** | No disk space monitoring | Log/DB fill causes cascading failures | Add disk space alerts and log rotation |
| **M4** | No certificate expiry monitoring | TLS failures on expiry | Add cert expiry alerts (30/7/1 day) |
| **M5** | No clock synchronization verification | Time-based decisions may be wrong | Add NTP monitoring, clock skew alerts |
| **M6** | No concurrent position modification protection | Race conditions between agents | Add optimistic locking on position state |

---

## 8. Recommendations Summary

### 8.1 Priority Action Items

```
IMMEDIATE (Before any live trading):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Add AlphaStack pipeline error handling (StepErrorHandler)
2. Add LLM API call wrapper with circuit breaker
3. Soften event bus failure response (buffer → degrade → close-all)
4. Persist circuit breaker states to Redis
5. Define data pipeline degraded mode

SHORT-TERM (Before $10K capital):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. Add Redis Sentinel for event bus HA
7. Implement TimescaleDB backup schedule
8. Document full system restart procedure
9. Add agent supervisor with auto-restart
10. Create failure mode registry
11. Add signal quality circuit breaker

MEDIUM-TERM (Before $100K capital):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
12. Implement cross-region failover
13. Add network partition fencing
14. Add chaos engineering test suite
15. Implement configuration drift detection
16. Add comprehensive disk/cert/NTP monitoring
```

### 8.2 Architecture Strengths to Preserve

The following design decisions are excellent and should not be changed:

1. **"Fail-Safe by Default" principle** — Every module assumes the module below it will fail
2. **Four-layer circuit breaker independence** — Any single layer can halt trading
3. **Broker = truth reconciliation** — Never trust local state after disconnect
4. **Five-stage drawdown with slow de-escalation** — Markets crash fast, recovery takes days
5. **Black swan detection with 2+ trigger requirement** — Avoids false positives
6. **Adaptive disconnect timeout** — Losing positions get faster protection
7. **Progressive autonomy model** — HITL → semi-auto → full-auto based on proven performance
8. **Risk Agent P0 priority** — Safety overrides all other agents

### 8.3 Risk Assessment

If the 6 critical gaps (C1-C6) are not fixed before live deployment:

| Scenario | Probability | Impact | Risk |
|----------|------------|--------|------|
| LLM timeout stalls AlphaStack pipeline during NFP | Medium | High — missed exit on losing position | **HIGH** |
| Redis blip closes all positions unnecessarily | Medium | Medium — realized losses on winning positions | **MEDIUM** |
| System restarts during drawdown, forgets crisis state | Low | Critical — resumes full-size trading during active drawdown | **CRITICAL** |
| Data pipeline fails, system trades on stale data | Medium | High — entries at wrong prices | **HIGH** |
| Agent crashes, stays down for hours | Medium | Medium — no new trades, existing positions unmanaged | **MEDIUM** |
| LLM returns hallucinated signal | Medium | Medium — bad trade with good-sounding reasoning | **MEDIUM** |

---

## 9. Conclusion

The Alpha Stack error handling architecture is **institutional-grade in design** but has implementation gaps primarily in the strategy/orchestration layers (L3/L4) and infrastructure resilience (L0). The broker execution layer (L2) and risk management system are exceptionally well-designed.

The system is **not self-healing** at the infrastructure level — it relies on manual intervention for database failures, agent crashes, and full restarts. For a $7 account this is acceptable; for $100K+ it needs automated recovery.

**Bottom line:** Fix the 6 critical gaps, and this system has error handling that rivals institutional trading desks. Leave them unfixed, and a single LLM timeout during a news event could cascade into significant losses.

---

*"The goal of error handling isn't to prevent all errors — it's to ensure that when errors happen, the system fails in the safest possible way."*

---

> **Document maintained by:** Error Handling Review Agent  
> **Review cadence:** After any incident, or quarterly  
> **Next review:** Before live capital deployment
