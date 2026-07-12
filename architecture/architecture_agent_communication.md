# Alpha Stack — Agent Communication Protocol

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/research_03_loop_multiagent_systems.md`](../research/research_03_loop_multiagent_systems.md) — Multi-agent systems — agent communication protocol
> **Status:** Architecture Complete

---

**Date:** 2026-07-11
**Version:** 1.0
**Status:** Architecture Design — Ready for Implementation Review
**Author:** Agent Communication Architect

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Principles](#2-design-principles)
3. [Communication Infrastructure](#3-communication-infrastructure)
4. [Message Format (JSON Schema)](#4-message-format-json-schema)
5. [Communication Channels](#5-communication-channels)
6. [Priority Levels](#6-priority-levels)
7. [Agent-to-Agent Direct Messaging](#7-agent-to-agent-direct-messaging)
8. [Broadcast Messaging](#8-broadcast-messaging)
9. [Request-Response Patterns](#9-request-response-patterns)
10. [Event-Driven Patterns](#10-event-driven-patterns)
11. [Message Routing and Filtering](#11-message-routing-and-filtering)
12. [Dead Letter Handling](#12-dead-letter-handling)
13. [Message Ordering and Deduplication](#13-message-ordering-and-deduplication)
14. [Protocol State Machines](#14-protocol-state-machines)
15. [Security and Authentication](#15-security-and-authentication)
16. [Monitoring and Observability](#16-monitoring-and-observability)
17. [Implementation Reference](#17-implementation-reference)
18. [Testing Strategy](#18-testing-strategy)
19. [Appendices](#19-appendices)

---

## 1. Executive Summary

### Problem

Alpha Stack's multi-agent system consists of 16+ specialized agents (Orchestrator, Fundamental, Structure, Liquidity, SMC, Momentum, Candlestick, Signal Aggregator, Entry, Risk Gate, TP, Trade Management, Execution, Monitor, Reflection, Journal) that must coordinate in real-time to analyze markets, generate signals, execute trades, and learn from outcomes. Communication failures — lost messages, out-of-order delivery, duplicate processing, or deadlocks — can cause missed trades, phantom positions, or risk breaches.

### Solution

A **hybrid communication protocol** combining three transport mechanisms, each optimized for its use case:

| Transport | Use Case | Guarantee |
|-----------|----------|-----------|
| **Redis Streams** | Ordered, persistent signal flow (pipeline handoffs) | At-least-once, ordered, replayable |
| **Redis Pub/Sub** | Low-latency fire-and-forget events (market data, alerts) | At-most-once, unordered |
| **Redis Hashes** | Shared state (positions, portfolio, regime) | Read-your-writes consistency |

All messages follow a **standardized envelope** with priority routing, correlation tracking, TTL-based expiry, deduplication, and dead letter handling. The protocol supports point-to-point, broadcast, request-response, and publish-subscribe patterns.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Message transport | Redis Streams + Pub/Sub | Streams for ordered persistence, Pub/Sub for low-latency |
| State store | Redis Hashes with Lua scripts | Atomic read-modify-write for consistency-critical data |
| Serialization | JSON (with MessagePack option) | Human-readable debugging; MessagePack for hot paths |
| Priority enforcement | Consumer-side priority queues | Redis Streams don't natively support priority; enforced in consumer |
| Deduplication | Message ID + Bloom filter | O(1) dedup check with negligible memory |
| Dead letters | Dedicated stream with retry policy | Never silently drop messages; always surface failures |
| Ordering | Per-correlation-ID ordering via stream partitioning | Pipeline messages ordered by correlation, not global order |

---

## 2. Design Principles

### P1: No Silent Failures
Every message that cannot be delivered or processed must surface to the dead letter queue and alert the Monitor Agent. No message is ever silently dropped.

### P2: At-Least-Once for Trade-Critical, At-Most-Once for Informational
Trade signals, risk decisions, and execution results use at-least-once delivery with idempotent consumers. Market data ticks and status updates use at-most-once (latest state wins).

### P3: Correlation Over Causation
Messages are correlated by `correlation_id` (pipeline run), not by causal ordering. Each pipeline run for an instrument produces a correlation group that can be traced end-to-end.

### P4: Consumer-Driven Priority
Redis Streams deliver in insertion order. Priority enforcement happens in the consumer: each agent maintains a priority inbox with separate queues per P-level, draining P0 first.

### P5: Schema-First Evolution
Every message type has a JSON Schema definition. New fields are additive. Breaking changes require a schema version bump and consumer migration window.

### P6: Idempotent Consumers
Every consumer must handle duplicate delivery gracefully. Message processing is idempotent: processing the same message twice produces the same result as processing it once.

### P7: Backpressure-Aware
When a consumer is slow, the protocol applies backpressure: producers buffer locally, then shed load by dropping lowest-priority messages (P4 only). P0-P3 messages never shed.

---

## 3. Communication Infrastructure

### 3.1 Redis Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        REDIS SINGLE NODE                                │
│                   (or Redis Cluster for HA)                             │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     STREAMS (Ordered, Persistent)                  │ │
│  │                                                                    │ │
│  │  pipeline.fundamental     ← Fundamental Agent output              │ │
│  │  pipeline.structure       ← Structure Agent output                │ │
│  │  pipeline.liquidity       ← Liquidity Agent output                │ │
│  │  pipeline.smc             ← SMC Agent output                      │ │
│  │  pipeline.momentum        ← Momentum Agent output                 │ │
│  │  pipeline.candlestick     ← Candlestick Agent output              │ │
│  │  pipeline.confluence      ← Signal Aggregator output              │ │
│  │  pipeline.risk_gate       ← Risk Gate decisions                   │ │
│  │  pipeline.execution       ← Execution results                    │ │
│  │  pipeline.management      ← Trade management actions             │ │
│  │  pipeline.journal         ← Journal entries                      │ │
│  │  request.{agent_id}       ← Direct request inbox per agent       │ │
│  │  response.{correlation_id}← Response stream per request          │ │
│  │  dead_letter              ← Failed messages                      │ │
│  │  audit_log                ← All messages (append-only)           │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    PUB/SUB (Fire-and-Forget)                       │ │
│  │                                                                    │ │
│  │  events.market_data       → Tick/bar distribution                 │ │
│  │  events.alerts            → Human-facing alerts                   │ │
│  │  events.system_health     → Agent health heartbeats               │ │
│  │  events.kill_switch       → Emergency halt                        │ │
│  │  events.regime_change     → Market regime transitions             │ │
│  │  events.session_change    → Trading session transitions           │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    HASHES (Shared State)                           │ │
│  │                                                                    │ │
│  │  state:positions          → Current open positions                │ │
│  │  state:portfolio          → Portfolio-level metrics               │ │
│  │  state:regime             → Market regime per pair                │ │
│  │  state:session            → Session state machine                 │ │
│  │  state:risk_limits        → Risk limit utilization                │ │
│  │  state:system             → Agent health status                   │ │
│  │  state:signal_cache       → Latest signal per agent per pair      │ │
│  │  dedup:bloom              → Deduplication bloom filter             │ │
│  │  consumers:offsets        → Consumer group offsets                │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Consumer Groups

Each agent type forms a **Redis Streams consumer group**. This enables:
- Load balancing across multiple instances of the same agent type
- Independent offset tracking (each agent reads at its own pace)
- Automatic rebalancing on agent failure

```
Consumer Groups:
├── cg:orchestrator        → Reads from all pipeline.* streams
├── cg:fundamental         → Reads from pipeline.fundamental (self)
├── cg:structure           → Reads from pipeline.structure (self)
├── cg:liquidity           → Reads from pipeline.liquidity (self)
├── cg:smc                 → Reads from pipeline.smc (self)
├── cg:momentum            → Reads from pipeline.momentum (self)
├── cg:candlestick         → Reads from pipeline.candlestick (self)
├── cg:signal_aggregator   → Reads from pipeline.{fundamental,structure,liquidity,smc,momentum,candlestick}
├── cg:entry               → Reads from pipeline.confluence
├── cg:risk_gate           → Reads from pipeline.risk_gate
├── cg:execution           → Reads from pipeline.risk_gate (approved trades)
├── cg:monitor             → Reads from ALL streams + events.*
├── cg:reflection          → Reads from pipeline.execution, pipeline.journal
└── cg:journal             → Reads from ALL pipeline.* streams
```

### 3.3 Stream Configuration

```python
STREAM_CONFIG = {
    "pipeline.*": {
        "max_len": 100_000,          # Max entries per stream
        "approximate": True,          # Use ~ for efficient trimming
        "retention_hours": 72,        # Keep 3 days of pipeline data
    },
    "request.*": {
        "max_len": 10_000,
        "approximate": True,
        "retention_hours": 1,         # Requests expire quickly
    },
    "response.*": {
        "max_len": 10_000,
        "approximate": True,
        "retention_hours": 1,
    },
    "dead_letter": {
        "max_len": 50_000,
        "approximate": True,
        "retention_hours": 168,       # Keep 7 days for debugging
    },
    "audit_log": {
        "max_len": 1_000_000,
        "approximate": True,
        "retention_hours": 720,       # Keep 30 days for compliance
    },
}
```

---

## 4. Message Format (JSON Schema)

### 4.1 Envelope Schema

Every inter-agent message wraps in a standardized envelope. The envelope is the **protocol layer**; the `payload` is the **application layer**.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "alphastack/message-envelope-v1",
  "title": "AlphaStack Message Envelope",
  "type": "object",
  "required": [
    "message_id",
    "timestamp",
    "source_agent",
    "channel",
    "priority",
    "message_type",
    "payload"
  ],
  "properties": {
    "message_id": {
      "type": "string",
      "format": "uuid",
      "description": "Globally unique message identifier (UUIDv4). Used for deduplication."
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 UTC timestamp of message creation."
    },
    "source_agent": {
      "type": "string",
      "description": "Agent ID that produced this message (e.g., 'smc_agent_01')."
    },
    "target_agent": {
      "type": ["string", "null"],
      "description": "Agent ID for direct messages. Null for broadcast/pipeline messages."
    },
    "channel": {
      "type": "string",
      "description": "Destination stream/channel (e.g., 'pipeline.smc', 'events.alerts')."
    },
    "priority": {
      "type": "string",
      "enum": ["P0", "P1", "P2", "P3", "P4"],
      "description": "Message priority level. P0=Critical, P4=Background."
    },
    "message_type": {
      "type": "string",
      "enum": [
        "SIGNAL",
        "COMMAND",
        "QUERY",
        "RESPONSE",
        "EVENT",
        "ACK",
        "NACK",
        "HEARTBEAT",
        "ERROR",
        "TRADE_PROPOSAL",
        "RISK_DECISION",
        "EXECUTION_RESULT",
        "MANAGEMENT_ACTION",
        "JOURNAL_ENTRY"
      ],
      "description": "Semantic type of the message."
    },
    "ttl_seconds": {
      "type": "integer",
      "minimum": 1,
      "maximum": 86400,
      "default": 3600,
      "description": "Time-to-live. Message expires if not consumed within this window."
    },
    "correlation_id": {
      "type": ["string", "null"],
      "description": "Groups messages from the same pipeline run. Format: 'pipeline_{instrument}_{timestamp}'."
    },
    "reply_to": {
      "type": ["string", "null"],
      "description": "Stream name for request-response pattern. Sender expects response on this stream."
    },
    "idempotency_key": {
      "type": ["string", "null"],
      "description": "Optional key for deduplication beyond message_id. Used for retried operations."
    },
    "schema_version": {
      "type": "string",
      "default": "1.0",
      "description": "Message schema version for forward compatibility."
    },
    "payload": {
      "type": "object",
      "description": "Application-specific message content. Schema varies by message_type."
    },
    "metadata": {
      "type": "object",
      "properties": {
        "model_used": { "type": "string" },
        "inference_ms": { "type": "integer" },
        "loop_type": { "type": "string" },
        "loop_iterations": { "type": "integer" },
        "retry_count": { "type": "integer", "default": 0 },
        "original_message_id": { "type": ["string", "null"] },
        "trace_id": { "type": "string", "description": "Distributed tracing ID for end-to-end visibility." }
      },
      "additionalProperties": true
    }
  }
}
```

### 4.2 Concrete Message Examples

#### Signal Message (SMC Agent → Signal Aggregator)

```json
{
  "message_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-07-11T13:24:00.123Z",
  "source_agent": "smc_agent_01",
  "target_agent": null,
  "channel": "pipeline.smc",
  "priority": "P2",
  "message_type": "SIGNAL",
  "ttl_seconds": 3600,
  "correlation_id": "pipeline_EURUSD_20260711_132400",
  "reply_to": null,
  "idempotency_key": null,
  "schema_version": "1.0",
  "payload": {
    "instrument": "EURUSD",
    "signal_type": "ORDER_BLOCK_DETECTED",
    "direction": "bullish",
    "data": {
      "ob_high": 1.0850,
      "ob_low": 1.0835,
      "timeframe": "H4",
      "strength": 0.82,
      "mitigated": false
    },
    "confidence": 0.82,
    "reasoning": "H4 bullish OB formed after impulsive move from 1.0820. OB at 1.0835-1.0850 aligns with D1 support and H1 FVG. Volume on impulse candle was 1.8x average."
  },
  "metadata": {
    "model_used": "qwen-2.5-72b",
    "inference_ms": 340,
    "loop_type": "react",
    "loop_iterations": 3
  }
}
```

#### Trade Proposal (Signal Aggregator → Risk Gate)

```json
{
  "message_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "timestamp": "2026-07-11T13:25:30.456Z",
  "source_agent": "signal_aggregator",
  "target_agent": "risk_gate_agent",
  "channel": "pipeline.confluence",
  "priority": "P1",
  "message_type": "TRADE_PROPOSAL",
  "ttl_seconds": 300,
  "correlation_id": "pipeline_EURUSD_20260711_132400",
  "reply_to": "response.b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "idempotency_key": "trade_proposal_EURUSD_20260711_132530",
  "schema_version": "1.0",
  "payload": {
    "instrument": "EURUSD",
    "action": "BUY",
    "order_type": "LIMIT",
    "entry_price": 1.0842,
    "stop_loss": 1.0810,
    "take_profits": [
      { "price": 1.0887, "size_pct": 33, "label": "TP1" },
      { "price": 1.0932, "size_pct": 33, "label": "TP2" },
      { "method": "trailing", "atr_multiple": 2.5, "size_pct": 34, "label": "TP3" }
    ],
    "position_size_lots": 0.02,
    "risk_pct": 1.5,
    "confluence_score": 85,
    "signals": {
      "fundamental": { "bias": "NEUTRAL", "confidence": 0.70 },
      "structure": { "bias": "BULLISH", "confidence": 0.82 },
      "sr_level": { "price": 1.0840, "score": 78 },
      "liquidity": { "sweep_detected": false, "pool_below": true },
      "smc": { "ob_type": "bullish", "ob_strength": 0.82 },
      "momentum": { "rsi_m15": 28, "composite": 22, "confirmation": "STRONG" },
      "candlestick": { "pattern": "hammer", "score": 0.75 }
    }
  },
  "metadata": {
    "model_used": "qwen-2.5-72b",
    "inference_ms": 180,
    "loop_type": "evaluation",
    "loop_iterations": 1
  }
}
```

#### Risk Decision (Risk Gate → Execution)

```json
{
  "message_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "timestamp": "2026-07-11T13:25:32.789Z",
  "source_agent": "risk_gate_agent",
  "target_agent": "execution_agent",
  "channel": "pipeline.risk_gate",
  "priority": "P0",
  "message_type": "RISK_DECISION",
  "ttl_seconds": 60,
  "correlation_id": "pipeline_EURUSD_20260711_132400",
  "reply_to": null,
  "idempotency_key": null,
  "schema_version": "1.0",
  "payload": {
    "proposal_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "instrument": "EURUSD",
    "approved": true,
    "rejection_reason": null,
    "modified_params": {
      "position_size_lots": 0.015,
      "risk_pct": 1.2,
      "notes": "Reduced size due to existing GBPUSD exposure (correlation limit)"
    },
    "risk_checks_passed": [
      "max_risk_per_trade",
      "max_daily_loss",
      "max_open_positions",
      "max_drawdown",
      "event_proximity",
      "correlation_check"
    ],
    "risk_metrics": {
      "current_daily_loss_pct": 0.8,
      "current_drawdown_pct": 2.3,
      "open_positions": 2,
      "correlated_positions": 1
    }
  },
  "metadata": {
    "model_used": null,
    "inference_ms": 12,
    "loop_type": "evaluation",
    "loop_iterations": 1
  }
}
```

#### Execution Result (Execution → Monitor/Journal)

```json
{
  "message_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
  "timestamp": "2026-07-11T13:25:35.012Z",
  "source_agent": "execution_agent",
  "target_agent": null,
  "channel": "pipeline.execution",
  "priority": "P1",
  "message_type": "EXECUTION_RESULT",
  "ttl_seconds": 86400,
  "correlation_id": "pipeline_EURUSD_20260711_132400",
  "reply_to": null,
  "idempotency_key": "exec_EURUSD_20260711_132535",
  "schema_version": "1.0",
  "payload": {
    "proposal_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "instrument": "EURUSD",
    "action": "BUY",
    "order_type": "LIMIT",
    "requested_price": 1.0842,
    "fill_price": 1.0843,
    "slippage_pips": 1.0,
    "fill_quantity": 0.015,
    "broker_order_id": "FXP-20260711-48291",
    "broker_id": "fxpesa_mt5",
    "execution_time_ms": 234,
    "stop_loss": 1.0810,
    "take_profits": [
      { "price": 1.0887, "size_pct": 33 },
      { "price": 1.0932, "size_pct": 33 },
      { "method": "trailing", "atr_multiple": 2.5, "size_pct": 34 }
    ],
    "status": "FILLED"
  },
  "metadata": {
    "model_used": null,
    "inference_ms": null,
    "loop_type": "plan-and-execute",
    "loop_iterations": 5
  }
}
```

#### Kill Switch Event (Orchestrator → All)

```json
{
  "message_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
  "timestamp": "2026-07-11T14:00:00.000Z",
  "source_agent": "orchestrator",
  "target_agent": null,
  "channel": "events.kill_switch",
  "priority": "P0",
  "message_type": "COMMAND",
  "ttl_seconds": 86400,
  "correlation_id": null,
  "reply_to": null,
  "idempotency_key": "kill_switch_20260711_140000",
  "schema_version": "1.0",
  "payload": {
    "command": "HALT_ALL_TRADING",
    "reason": "Max drawdown 15% reached",
    "scope": "ALL",
    "action_required": "FLATTEN_ALL_POSITIONS",
    "resume_requires": "HUMAN_APPROVAL"
  },
  "metadata": {}
}
```

### 4.3 Payload Schemas by Message Type

| Message Type | Payload Schema | Description |
|-------------|---------------|-------------|
| `SIGNAL` | `{instrument, signal_type, direction, data, confidence, reasoning}` | Agent analysis output |
| `TRADE_PROPOSAL` | `{instrument, action, order_type, entry_price, stop_loss, take_profits, position_size_lots, risk_pct, confluence_score, signals}` | Complete trade setup |
| `RISK_DECISION` | `{proposal_id, approved, rejection_reason, modified_params, risk_checks_passed, risk_metrics}` | Gate decision |
| `EXECUTION_RESULT` | `{proposal_id, fill_price, slippage, broker_order_id, status}` | Order fill result |
| `MANAGEMENT_ACTION` | `{position_id, action, params}` | In-trade action (move SL, partial close) |
| `JOURNAL_ENTRY` | `{trade_id, entry, exit, pnl, lessons}` | Trade record |
| `COMMAND` | `{command, params, scope}` | Control commands (halt, resume, restart) |
| `QUERY` | `{query_type, params}` | Data request between agents |
| `RESPONSE` | `{request_id, status, data}` | Response to QUERY |
| `HEARTBEAT` | `{agent_id, status, uptime_seconds, signals_produced, errors_last_hour}` | Health check |
| `EVENT` | `{event_type, data}` | Generic event |
| `ACK` | `{message_id, status}` | Acknowledgment |
| `NACK` | `{message_id, reason}` | Negative acknowledgment |
| `ERROR` | `{error_code, message, recoverable, context}` | Error report |

---

## 5. Communication Channels

### 5.1 Channel Classification

```
CHANNEL TYPES:
│
├── PIPELINE STREAMS (Redis Streams)
│   Purpose: Ordered, persistent signal flow through the analysis pipeline
│   Guarantee: At-least-once delivery, insertion-order per stream
│   Consumers: Consumer groups (one per agent type)
│   Retention: 72 hours (configurable)
│
│   ├── pipeline.fundamental   → Fundamental Agent → Orchestrator
│   ├── pipeline.structure     → Structure Agent → Orchestrator
│   ├── pipeline.liquidity     → Liquidity Agent → Signal Aggregator
│   ├── pipeline.smc           → SMC Agent → Signal Aggregator
│   ├── pipeline.momentum      → Momentum Agent → Signal Aggregator
│   ├── pipeline.candlestick   → Candlestick Agent → Signal Aggregator
│   ├── pipeline.confluence    → Signal Aggregator → Entry/Risk Gate
│   ├── pipeline.risk_gate     → Risk Gate → Execution
│   ├── pipeline.execution     → Execution → Monitor/Journal/Reflection
│   ├── pipeline.management    → Trade Mgmt → Execution/Monitor
│   └── pipeline.journal       → Journal Agent (terminal)
│
├── REQUEST/RESPONSE STREAMS (Redis Streams)
│   Purpose: Point-to-point queries with guaranteed response
│   Guarantee: At-least-once with correlation matching
│   Pattern: Producer writes to request.{target}, consumer reads, responds to reply_to
│   Retention: 1 hour
│
│   ├── request.{agent_id}     → Per-agent inbox
│   └── response.{correlation_id} → Per-request response
│
├── EVENT CHANNELS (Redis Pub/Sub)
│   Purpose: Low-latency broadcast for time-critical events
│   Guarantee: At-most-once (fire-and-forget)
│   Consumers: All subscribers receive every message
│   Retention: None (ephemeral)
│
│   ├── events.market_data     → Price ticks, bar closes
│   ├── events.alerts          → Human-facing notifications
│   ├── events.system_health   → Agent heartbeats
│   ├── events.kill_switch     → Emergency halt
│   ├── events.regime_change   → Market regime transitions
│   └── events.session_change  → Trading session transitions
│
├── SHARED STATE (Redis Hashes)
│   Purpose: Consistency-critical state read by multiple agents
│   Guarantee: Atomic read-modify-write via Lua scripts
│   Access: Read by all, write by designated owner
│   Retention: Until explicitly updated
│
│   ├── state:positions        → Owner: Execution Agent
│   ├── state:portfolio        → Owner: Portfolio Aggregator
│   ├── state:regime           → Owner: Structure Agent
│   ├── state:session          → Owner: Orchestrator
│   ├── state:risk_limits      → Owner: Risk Gate Agent
│   ├── state:system           → Owner: Monitor Agent
│   └── state:signal_cache     → Owner: Each signal agent (own field)
│
└── DEAD LETTER + AUDIT (Redis Streams)
    Purpose: Failed message capture and compliance audit trail
    Guarantee: At-least-once, never trimmed during retention
    Retention: 7 days (dead letter), 30 days (audit)
```

### 5.2 Channel Ownership Matrix

| Channel | Writer(s) | Reader(s) | Pattern |
|---------|----------|-----------|---------|
| `pipeline.fundamental` | Fundamental Agent | Orchestrator, Signal Aggregator, Journal | 1:N |
| `pipeline.structure` | Structure Agent | Orchestrator, Signal Aggregator, Journal | 1:N |
| `pipeline.liquidity` | Liquidity Agent | Signal Aggregator, Journal | 1:N |
| `pipeline.smc` | SMC Agent | Signal Aggregator, Journal | 1:N |
| `pipeline.momentum` | Momentum Agent | Signal Aggregator, Journal | 1:N |
| `pipeline.candlestick` | Candlestick Agent | Signal Aggregator, Journal | 1:N |
| `pipeline.confluence` | Signal Aggregator | Entry Agent, Risk Gate, Journal | 1:N |
| `pipeline.risk_gate` | Risk Gate Agent | Execution Agent, Orchestrator, Journal | 1:N |
| `pipeline.execution` | Execution Agent | Monitor, Journal, Reflection, Orchestrator | 1:N |
| `pipeline.management` | Trade Mgmt Agent | Execution Agent, Monitor | 1:N |
| `pipeline.journal` | Journal Agent | (Terminal — no downstream) | 1:0 |
| `events.market_data` | Data Feed Service | All analysis agents | 1:N |
| `events.kill_switch` | Orchestrator, Risk Gate, Human | ALL agents | 1:N |
| `state:positions` | Execution Agent | All agents (read) | 1:N |
| `state:regime` | Structure Agent | All analysis agents (read) | 1:N |
| `request.{agent}` | Any agent | Target agent | 1:1 |
| `dead_letter` | Consumer framework | Monitor Agent | 1:1 |
| `audit_log` | Message broker layer | Compliance/review tools | 1:N |

---

## 6. Priority Levels

### 6.1 Priority Definitions

| Priority | Name | Latency Target | Consumer Behavior | Use Cases |
|----------|------|---------------|-------------------|-----------|
| **P0** | CRITICAL | < 1s | Preemptive: interrupts current processing | Kill switch, risk breach, liquidity sweep, margin call |
| **P1** | HIGH | < 5s | Next-in-queue: processed before all non-P0 | Trade signals, entry triggers, stop loss hit, execution results |
| **P2** | MEDIUM | < 30s | Normal queue: FIFO within priority band | S/R levels, SMC patterns, RSI extremes, candlestick patterns |
| **P3** | LOW | < 5m | Batched: can process in groups | Background scans, session transitions, regime updates |
| **P4** | BACKGROUND | < 30m | Opportunistic: only when idle | Performance review, journal consolidation, memory cleanup |

### 6.2 Priority Enforcement in Consumers

Redis Streams deliver in insertion order — there is no native priority queue. Each agent enforces priority with a **multi-queue inbox**:

```python
class PriorityInbox:
    """
    Per-agent priority inbox. Reads from Redis Stream, sorts into
    priority queues, drains P0 first.
    """

    def __init__(self, stream_key: str, consumer_group: str, consumer_name: str):
        self.stream_key = stream_key
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.queues = {
            "P0": asyncio.Queue(),  # Preemptive
            "P1": asyncio.Queue(),  # High priority
            "P2": asyncio.Queue(),  # Normal
            "P3": asyncio.Queue(),  # Low
            "P4": asyncio.Queue(),  # Background
        }
        self._running = False

    async def start(self):
        """Background task: read from stream, route to priority queues."""
        self._running = True
        while self._running:
            messages = await redis.xreadgroup(
                self.consumer_group,
                self.consumer_name,
                {self.stream_key: ">"},
                count=100,
                block=1000,  # 1 second block
            )
            for stream, entries in messages:
                for msg_id, fields in entries:
                    envelope = json.loads(fields[b"message"])
                    priority = envelope.get("priority", "P2")

                    # Check TTL
                    if self._is_expired(envelope):
                        await self._send_to_dead_letter(envelope, "TTL_EXPIRED")
                        await redis.xack(self.stream_key, self.consumer_group, msg_id)
                        continue

                    # Route to priority queue
                    self.queues[priority].put_nowait((msg_id, envelope))

    async def receive(self) -> tuple[str, dict]:
        """
        Get next message, draining highest priority first.
        P0 is preemptive: if P0 arrives during P1 processing,
        the caller should yield.
        """
        # P0: Always check first (preemptive)
        if not self.queues["P0"].empty():
            return await self.queues["P0"].get()

        # P1 → P2 → P3 → P4: Drain in order
        for priority in ["P1", "P2", "P3", "P4"]:
            if not self.queues[priority].empty():
                return await self.queues[priority].get()

        # All empty: wait for next message
        # Re-read from stream with blocking
        return await self._blocking_receive()

    async def ack(self, msg_id: str):
        """Acknowledge message processing."""
        await redis.xack(self.stream_key, self.consumer_group, msg_id)

    def _is_expired(self, envelope: dict) -> bool:
        """Check if message TTL has expired."""
        ttl = envelope.get("ttl_seconds", 3600)
        created = datetime.fromisoformat(envelope["timestamp"].replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - created).total_seconds() > ttl
```

### 6.3 Priority Escalation

Messages can be **escalated** when their urgency changes:

| Scenario | Original Priority | Escalated To | Trigger |
|----------|------------------|-------------|---------|
| Signal confidence > 0.9 | P2 | P1 | High-confidence signal gets expedited |
| Position approaching stop loss | P2 | P1 | Price within 5 pips of SL |
| Agent timeout approaching | P3 | P1 | Agent hasn't responded in 80% of timeout |
| Multiple signals converging | P2 | P1 | 3+ agents signal same direction within 5 min |
| News event detected | P3 | P0 | High-impact news breaks during analysis |

```python
async def maybe_escalate(envelope: dict, context: dict) -> str:
    """Return potentially escalated priority."""
    current = envelope["priority"]

    # P0 is never escalated further
    if current == "P0":
        return "P0"

    # High-confidence signal escalation
    if (envelope["message_type"] == "SIGNAL"
            and envelope["payload"].get("confidence", 0) > 0.9
            and current in ("P2", "P3")):
        return "P1"

    # Proximity to stop loss
    if context.get("pips_to_sl", 999) < 5 and current == "P2":
        return "P1"

    # News event override
    if context.get("high_impact_news", False):
        return "P0"

    return current
```

---

## 7. Agent-to-Agent Direct Messaging

### 7.1 Point-to-Point Pattern

Direct messaging is used when one agent needs a **specific response** from another agent (e.g., Orchestrator querying current regime from Structure Agent).

```
┌──────────────┐                    ┌──────────────┐
│   Sender     │                    │   Receiver   │
│              │  request.{target}  │              │
│  Agent A     │ ─────────────────► │  Agent B     │
│              │                    │              │
│              │  response.{corr_id}│              │
│              │ ◄───────────────── │              │
│              │                    │              │
└──────────────┘                    └──────────────┘
```

### 7.2 Implementation

```python
class DirectMessenger:
    """
    Agent-to-agent direct messaging with request-response pattern.
    Uses dedicated request/response streams per agent.
    """

    def __init__(self, agent_id: str, redis_client):
        self.agent_id = agent_id
        self.redis = redis_client
        self.inbox_stream = f"request.{agent_id}"
        self.pending_responses = {}  # correlation_id → Future

    async def send_request(
        self,
        target_agent: str,
        message_type: str,
        payload: dict,
        priority: str = "P2",
        timeout_seconds: int = 30,
    ) -> dict:
        """
        Send a direct request to another agent and wait for response.
        Returns the response payload.
        """
        correlation_id = str(uuid.uuid4())
        reply_to = f"response.{correlation_id}"

        envelope = create_envelope(
            source_agent=self.agent_id,
            target_agent=target_agent,
            channel=f"request.{target_agent}",
            priority=priority,
            message_type=message_type,
            payload=payload,
            correlation_id=correlation_id,
            reply_to=reply_to,
            ttl_seconds=timeout_seconds,
        )

        # Register response handler
        future = asyncio.get_event_loop().create_future()
        self.pending_responses[correlation_id] = future

        # Send request
        await self.redis.xadd(
            f"request.{target_agent}",
            {"message": json.dumps(envelope)},
            maxlen=10_000,
        )

        try:
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout_seconds)
            return response
        except asyncio.TimeoutError:
            raise CommunicationTimeoutError(
                f"No response from {target_agent} within {timeout_seconds}s "
                f"(correlation_id={correlation_id})"
            )
        finally:
            del self.pending_responses[correlation_id]

    async def handle_request(self, envelope: dict) -> dict:
        """
        Override in agent implementation.
        Process incoming request and return response payload.
        """
        raise NotImplementedError

    async def send_response(self, reply_to: str, correlation_id: str, payload: dict):
        """Send response to a request."""
        envelope = create_envelope(
            source_agent=self.agent_id,
            target_agent=None,
            channel=reply_to,
            priority="P1",
            message_type="RESPONSE",
            payload=payload,
            correlation_id=correlation_id,
        )

        await self.redis.xadd(
            reply_to,
            {"message": json.dumps(envelope)},
            maxlen=10_000,
        )

    async def listen_for_responses(self):
        """Background task: listen on response streams for pending requests."""
        while True:
            for correlation_id, future in list(self.pending_responses.items()):
                if future.done():
                    continue

                stream_key = f"response.{correlation_id}"
                messages = await self.redis.xread(
                    {stream_key: "0"}, count=1, block=100
                )

                for stream, entries in messages:
                    for msg_id, fields in entries:
                        envelope = json.loads(fields[b"message"])
                        future.set_result(envelope["payload"])

            await asyncio.sleep(0.1)  # 100ms polling
```

### 7.3 Direct Message Examples

```python
# Orchestrator querying Structure Agent for current regime
regime = await orchestrator.messenger.send_request(
    target_agent="structure_agent",
    message_type="QUERY",
    payload={
        "query_type": "GET_REGIME",
        "instrument": "EURUSD",
    },
    priority="P2",
    timeout_seconds=5,
)
# Response: {"regime": "TRENDING_BULL", "confidence": 0.82, "session": "LONDON"}

# Risk Gate querying portfolio state before approval
positions = await risk_gate.messenger.send_request(
    target_agent="portfolio_aggregator",
    message_type="QUERY",
    payload={
        "query_type": "GET_POSITIONS",
        "include_unrealized_pnl": True,
    },
    priority="P0",
    timeout_seconds=2,
)
```

---

## 8. Broadcast Messaging

### 8.1 Broadcast Patterns

Broadcast messages are sent to **all agents** or **a subset** via Pub/Sub channels. Unlike Streams, Pub/Sub is fire-and-forget with no persistence.

| Broadcast Type | Channel | Scope | Use Case |
|---------------|---------|-------|----------|
| Kill Switch | `events.kill_switch` | ALL agents | Emergency halt |
| Market Data | `events.market_data` | Analysis agents | Price tick distribution |
| Regime Change | `events.regime_change` | ALL agents | Market regime transition |
| Session Change | `events.session_change` | ALL agents | Trading session transition |
| System Alert | `events.alerts` | Human + Monitor | Human-facing notifications |
| Agent Health | `events.system_health` | Monitor Agent | Health heartbeats |

### 8.2 Broadcast Implementation

```python
class BroadcastPublisher:
    """
    Publish broadcast messages via Redis Pub/Sub.
    Fire-and-forget — no delivery guarantee.
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    async def publish_kill_switch(self, reason: str, scope: str = "ALL"):
        """Emergency halt — highest priority broadcast."""
        envelope = create_envelope(
            source_agent="orchestrator",
            target_agent=None,
            channel="events.kill_switch",
            priority="P0",
            message_type="COMMAND",
            payload={
                "command": "HALT_ALL_TRADING",
                "reason": reason,
                "scope": scope,
                "action_required": "FLATTEN_ALL_POSITIONS",
                "resume_requires": "HUMAN_APPROVAL",
            },
            ttl_seconds=86400,
        )
        await self.redis.publish("events.kill_switch", json.dumps(envelope))

    async def publish_market_data(self, tick: dict):
        """Distribute price tick to all subscribers."""
        await self.redis.publish("events.market_data", json.dumps(tick))

    async def publish_regime_change(self, instrument: str, old_regime: str, new_regime: str):
        """Notify all agents of regime transition."""
        envelope = create_envelope(
            source_agent="structure_agent",
            target_agent=None,
            channel="events.regime_change",
            priority="P1",
            message_type="EVENT",
            payload={
                "event_type": "REGIME_CHANGE",
                "instrument": instrument,
                "old_regime": old_regime,
                "new_regime": new_regime,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        await self.redis.publish("events.regime_change", json.dumps(envelope))

    async def publish_session_change(self, session: str, instruments: list[str]):
        """Notify all agents of trading session transition."""
        envelope = create_envelope(
            source_agent="orchestrator",
            target_agent=None,
            channel="events.session_change",
            priority="P2",
            message_type="EVENT",
            payload={
                "event_type": "SESSION_CHANGE",
                "session": session,  # "ASIAN", "LONDON", "NY", "OVERLAP", "OFF_HOURS"
                "instruments": instruments,
            },
        )
        await self.redis.publish("events.session_change", json.dumps(envelope))


class BroadcastSubscriber:
    """
    Subscribe to broadcast channels. Each agent subscribes to the
    channels relevant to its role.
    """

    def __init__(self, agent_id: str, redis_client):
        self.agent_id = agent_id
        self.redis = redis_client
        self.handlers = {}  # channel → async callable
        self._running = False

    def on(self, channel: str, handler):
        """Register handler for a broadcast channel."""
        self.handlers[channel] = handler

    async def start(self):
        """Start listening for broadcast messages."""
        self._running = True
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(*self.handlers.keys())

        while self._running:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if message and message["type"] == "message":
                channel = message["channel"].decode()
                data = json.loads(message["data"])

                handler = self.handlers.get(channel)
                if handler:
                    try:
                        await handler(data)
                    except Exception as e:
                        logger.error(
                            f"Broadcast handler error on {channel}: {e}",
                            extra={"agent_id": self.agent_id},
                        )

    async def stop(self):
        self._running = False
```

### 8.3 Agent Subscription Map

| Agent | Subscribes To |
|-------|--------------|
| Orchestrator | `events.kill_switch`, `events.market_data`, `events.system_health`, `events.regime_change`, `events.session_change` |
| Fundamental | `events.kill_switch`, `events.session_change` |
| Structure | `events.kill_switch`, `events.market_data`, `events.session_change` |
| Liquidity | `events.kill_switch`, `events.market_data` |
| SMC | `events.kill_switch`, `events.market_data`, `events.regime_change` |
| Momentum | `events.kill_switch`, `events.market_data` |
| Candlestick | `events.kill_switch`, `events.market_data` |
| Signal Aggregator | `events.kill_switch`, `events.regime_change` |
| Entry | `events.kill_switch` |
| Risk Gate | `events.kill_switch`, `events.market_data` |
| TP | `events.kill_switch`, `events.market_data` |
| Trade Mgmt | `events.kill_switch`, `events.market_data` |
| Execution | `events.kill_switch` |
| Monitor | ALL events |
| Reflection | `events.kill_switch` |
| Journal | `events.kill_switch` |

---

## 9. Request-Response Patterns

### 9.1 Synchronous Request-Response

For queries where the caller needs an immediate answer before proceeding.

```
┌──────────────┐         ┌──────────────┐
│   Requester  │         │   Responder  │
│              │  QUERY  │              │
│              │────────►│              │
│              │         │  (process)   │
│              │ RESPONSE│              │
│              │◄────────│              │
└──────────────┘         └──────────────┘

Timeout: Configurable per request (default 30s)
On timeout: CommunicationTimeoutError → escalate to Monitor
```

### 9.2 Asynchronous Request-Response

For queries where the caller can continue working and check the response later.

```
┌──────────────┐         ┌──────────────┐
│   Requester  │         │   Responder  │
│              │  QUERY  │              │
│              │────────►│              │
│   (continues │         │  (process)   │
│    working)  │         │              │
│              │ RESPONSE│              │
│   (checks)   │◄────────│              │
└──────────────┘         └──────────────┘

Pattern: Fire request, store correlation_id, poll response stream later
Use case: Reflection Agent querying historical data (non-blocking)
```

### 9.3 Scatter-Gather Pattern

For queries that fan out to multiple agents and aggregate results.

```
                    ┌──────────────┐
                    │  Requester   │
                    │  (Scatter)   │
                    └──────┬───────┘
                           │ QUERY
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Agent A  │ │ Agent B  │ │ Agent C  │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │ RESPONSE   │ RESPONSE   │ RESPONSE
             ▼            ▼            ▼
        ┌─────────────────────────────────────┐
        │         Requester (Gather)          │
        │   Aggregate responses → proceed     │
        └─────────────────────────────────────┘

Timeout: max(individual_timeouts) + buffer
On partial timeout: Use available responses, flag missing
Use case: Orchestrator gathering signals from all analysis agents
```

```python
class ScatterGather:
    """
    Fan out a query to multiple agents, collect responses
    within a timeout window.
    """

    def __init__(self, messenger: DirectMessenger):
        self.messenger = messenger

    async def scatter_gather(
        self,
        targets: list[str],
        message_type: str,
        payload: dict,
        priority: str = "P2",
        timeout_seconds: int = 30,
        min_responses: int = 1,
    ) -> dict[str, dict]:
        """
        Send request to multiple agents, gather responses.
        Returns {agent_id: response_payload} for all agents that responded.
        """
        tasks = {}
        for target in targets:
            tasks[target] = asyncio.create_task(
                self.messenger.send_request(
                    target_agent=target,
                    message_type=message_type,
                    payload=payload,
                    priority=priority,
                    timeout_seconds=timeout_seconds,
                )
            )

        results = {}
        done, pending = await asyncio.wait(
            tasks.values(),
            timeout=timeout_seconds,
            return_when=asyncio.ALL_COMPLETED,
        )

        for target, task in tasks.items():
            if task.done() and not task.cancelled():
                try:
                    results[target] = task.result()
                except Exception as e:
                    logger.warning(f"Scatter-gather: {target} failed: {e}")
            else:
                task.cancel()
                logger.warning(f"Scatter-gather: {target} timed out")

        if len(results) < min_responses:
            raise InsufficientResponsesError(
                f"Only {len(results)}/{len(targets)} agents responded "
                f"(minimum: {min_responses})"
            )

        return results
```

### 9.4 Pipeline Handoff Pattern

The primary communication pattern for the trading pipeline. Each agent completes its work, writes to its output stream, and the Orchestrator routes to the next agent.

```
Agent A                    Orchestrator                 Agent B
  │                            │                          │
  │  Write to pipeline.A       │                          │
  │ ─────────────────────────► │                          │
  │                            │  Read from pipeline.A    │
  │                            │  Validate message        │
  │                            │  Update shared state     │
  │                            │                          │
  │                            │  Write to request.B      │
  │                            │ ───────────────────────► │
  │                            │                          │  Process
  │                            │                          │  Write to pipeline.B
  │                            │  Read from pipeline.B    │ ◄─────────
  │                            │                          │
  │                            │  ACK pipeline.A          │
  │                            │ ───────────────────────► │
```

---

## 10. Event-Driven Patterns

### 10.1 Market Data Distribution

Market data flows from the data feed service to all analysis agents via Pub/Sub. This is the highest-volume channel.

```
┌──────────────┐     events.market_data      ┌─────────────────┐
│  Data Feed   │ ────────────────────────────►│ Fundamental     │
│  Service     │ ────────────────────────────►│ Structure       │
│              │ ────────────────────────────►│ Liquidity       │
│  (WebSocket  │ ────────────────────────────►│ SMC             │
│   to Redis)  │ ────────────────────────────►│ Momentum        │
│              │ ────────────────────────────►│ Candlestick     │
│              │ ────────────────────────────►│ Risk Gate       │
│              │ ────────────────────────────►│ Trade Mgmt      │
│              │ ────────────────────────────►│ Monitor         │
└──────────────┘                               └─────────────────┘

Message format (tick):
{
  "type": "TICK",
  "instrument": "EURUSD",
  "bid": 1.08420,
  "ask": 1.08435,
  "timestamp": "2026-07-11T13:24:00.123Z"
}

Message format (bar):
{
  "type": "BAR_CLOSE",
  "instrument": "EURUSD",
  "timeframe": "M15",
  "open": 1.08350,
  "high": 1.08450,
  "low": 1.08320,
  "close": 1.08420,
  "volume": 1250,
  "timestamp": "2026-07-11T13:15:00.000Z"
}
```

### 10.2 Event Cascade Pattern

When a market event triggers a cascade of agent activations:

```
BAR_CLOSE (H4, EURUSD)
  │
  ├─► Structure Agent: Update multi-TF structure
  │     └─► Write pipeline.structure (regime + bias)
  │
  ├─► Orchestrator: Read pipeline.structure
  │     ├─► Spawn SMC Agent (Phase 3 parallel)
  │     ├─► Spawn Momentum Agent (Phase 3 parallel)
  │     └─► Spawn Candlestick Agent (Phase 3 parallel)
  │
  ├─► SMC Agent: Detect OB/FVG/BOS
  │     └─► Write pipeline.smc
  │
  ├─► Momentum Agent: Calculate RSI/composite
  │     └─► Write pipeline.momentum
  │
  ├─► Candlestick Agent: Detect patterns
  │     └─► Write pipeline.candlestick
  │
  └─► Orchestrator: All Phase 3 complete
        └─► Spawn Signal Aggregator (Phase 4)
              └─► Write pipeline.confluence
                    ├─► Spawn Entry Agent (if score ≥ 60)
                    └─► Spawn Risk Gate Agent (if proposal generated)
```

### 10.3 Circuit Breaker Event Pattern

When the system detects a failure cascade, circuit breaker events halt specific operations:

```python
class CircuitBreakerEventPublisher:
    """Publish circuit breaker state changes as events."""

    async def publish_trip(self, broker_id: str, failure_count: int, window_seconds: int):
        """Circuit breaker tripped — broker marked unhealthy."""
        envelope = create_envelope(
            source_agent="monitor_agent",
            target_agent=None,
            channel="events.system_health",
            priority="P0",
            message_type="EVENT",
            payload={
                "event_type": "CIRCUIT_BREAKER_TRIP",
                "broker_id": broker_id,
                "failure_count": failure_count,
                "window_seconds": window_seconds,
                "action": "HALT_NEW_ORDERS",
                "recovery_timeout_seconds": 60,
            },
        )
        await self.redis.publish("events.system_health", json.dumps(envelope))

    async def publish_recovery(self, broker_id: str):
        """Circuit breaker recovered — broker healthy again."""
        envelope = create_envelope(
            source_agent="monitor_agent",
            target_agent=None,
            channel="events.system_health",
            priority="P1",
            message_type="EVENT",
            payload={
                "event_type": "CIRCUIT_BREAKER_RECOVERY",
                "broker_id": broker_id,
                "action": "RESUME_NORMAL_OPERATION",
            },
        )
        await self.redis.publish("events.system_health", json.dumps(envelope))
```

---

## 11. Message Routing and Filtering

### 11.1 Routing Architecture

The Orchestrator acts as the **central router** for pipeline messages. It reads from all pipeline streams and routes to the next agent based on the pipeline phase and message content.

```python
class MessageRouter:
    """
    Central message router. Routes messages based on:
    1. Pipeline phase (determines next agent)
    2. Message content (conditional routing)
    3. Priority (urgent messages bypass normal flow)
    4. Correlation ID (groups messages from same pipeline run)
    """

    # Pipeline phase → next agent mapping
    PHASE_ROUTES = {
        "fundamental_complete": "structure_agent",
        "structure_complete": "signal_phase_3",  # Triggers parallel SMC/Momentum/Candlestick
        "smc_complete": "signal_aggregator",
        "momentum_complete": "signal_aggregator",
        "candlestick_complete": "signal_aggregator",
        "confluence_complete": "entry_agent",     # If score ≥ 60
        "entry_complete": "risk_gate_agent",
        "risk_approved": "execution_agent",
        "risk_rejected": None,                     # Terminal
        "execution_complete": "monitor_agent",
    }

    # Conditional routing rules
    ROUTING_RULES = [
        {
            "name": "fundamental_veto",
            "condition": lambda msg: (
                msg["message_type"] == "SIGNAL"
                and msg["source_agent"] == "fundamental_agent"
                and msg["payload"].get("event_risk_score", 0) > 0.8
            ),
            "action": "SKIP_PHASES_3_TO_6",
            "reason": "High event risk — skip analysis pipeline",
        },
        {
            "name": "confluence_gate",
            "condition": lambda msg: (
                msg["message_type"] == "SIGNAL"
                and msg["source_agent"] == "signal_aggregator"
                and msg["payload"].get("confluence_score", 0) < 40
            ),
            "action": "SKIP_ENTRY",
            "reason": "Confluence score below threshold — no trade",
        },
        {
            "name": "position_exists",
            "condition": lambda msg: (
                msg["message_type"] == "SIGNAL"
                and has_open_position(msg["payload"].get("instrument"))
            ),
            "action": "ROUTE_TO_MANAGEMENT",
            "reason": "Position already open — route to trade management",
        },
    ]

    async def route(self, envelope: dict, pipeline_state: dict) -> Optional[str]:
        """
        Determine the next destination for a message.
        Returns stream name or None if message should be terminal.
        """
        # Check routing rules first (conditional overrides)
        for rule in self.ROUTING_RULES:
            if rule["condition"](envelope):
                if rule["action"] == "SKIP_PHASES_3_TO_6":
                    return None  # Terminal — log and stop
                elif rule["action"] == "SKIP_ENTRY":
                    return None
                elif rule["action"] == "ROUTE_TO_MANAGEMENT":
                    return "pipeline.management"

        # Standard phase routing
        source = envelope["source_agent"]
        phase_key = f"{source.replace('_agent', '')}_complete"
        return self.PHASE_ROUTES.get(phase_key)
```

### 11.2 Content-Based Filtering

Agents filter incoming messages by content before processing:

```python
class MessageFilter:
    """
    Filter messages based on content rules.
    Each agent applies its own filter configuration.
    """

    def __init__(self, agent_id: str, config: dict):
        self.agent_id = agent_id
        self.config = config

    def should_process(self, envelope: dict) -> bool:
        """Determine if this message should be processed by the agent."""

        # 1. Check message type
        allowed_types = self.config.get("allowed_message_types", [])
        if allowed_types and envelope["message_type"] not in allowed_types:
            return False

        # 2. Check instrument filter
        allowed_instruments = self.config.get("instruments", [])
        msg_instrument = envelope["payload"].get("instrument")
        if allowed_instruments and msg_instrument not in allowed_instruments:
            return False

        # 3. Check priority threshold
        min_priority = self.config.get("min_priority", "P4")
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
        if priority_order.get(envelope["priority"], 4) > priority_order.get(min_priority, 4):
            return False

        # 4. Check TTL (skip expired)
        ttl = envelope.get("ttl_seconds", 3600)
        created = datetime.fromisoformat(envelope["timestamp"].replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - created).total_seconds() > ttl:
            return False

        # 5. Check correlation filter (only process messages from current pipeline)
        if self.config.get("current_correlation_id"):
            if envelope.get("correlation_id") != self.config["current_correlation_id"]:
                return False

        return True


# Agent-specific filter configurations
AGENT_FILTERS = {
    "smc_agent": {
        "allowed_message_types": ["SIGNAL", "EVENT", "COMMAND"],
        "instruments": [],  # All instruments
        "min_priority": "P3",
    },
    "risk_gate_agent": {
        "allowed_message_types": ["TRADE_PROPOSAL", "COMMAND"],
        "instruments": [],
        "min_priority": "P0",  # Process all priorities
    },
    "monitor_agent": {
        "allowed_message_types": [],  # All types
        "instruments": [],
        "min_priority": "P4",  # Process everything
    },
}
```

### 11.3 Stream Partitioning for Ordering

To maintain per-instrument ordering without global ordering constraints, pipeline streams are **partitioned by correlation_id**:

```python
class PartitionedStreamReader:
    """
    Read from a pipeline stream, maintaining per-correlation ordering.
    Messages with the same correlation_id are processed in insertion order.
    Messages with different correlation_ids can be processed in parallel.
    """

    def __init__(self, stream_key: str, consumer_group: str, consumer_name: str):
        self.stream_key = stream_key
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.partition_buffers = {}  # correlation_id → deque of messages

    async def read_batch(self, count: int = 100) -> dict[str, list[dict]]:
        """
        Read a batch of messages, grouped by correlation_id.
        Returns {correlation_id: [messages_in_order]}.
        """
        raw = await redis.xreadgroup(
            self.consumer_group,
            self.consumer_name,
            {self.stream_key: ">"},
            count=count,
            block=1000,
        )

        grouped = defaultdict(list)
        for stream, entries in raw:
            for msg_id, fields in entries:
                envelope = json.loads(fields[b"message"])
                corr_id = envelope.get("correlation_id", "_none")
                grouped[corr_id].append((msg_id, envelope))

        # Sort each group by stream position (insertion order)
        for corr_id in grouped:
            grouped[corr_id].sort(key=lambda x: x[0])  # msg_id is lexicographically ordered

        return grouped
```

---

## 12. Dead Letter Handling

### 12.1 Dead Letter Queue (DLQ)

Every message that cannot be processed or delivered is routed to the dead letter queue. Messages are never silently dropped.

```python
class DeadLetterHandler:
    """
    Handles messages that fail processing.
    Routes to dead_letter stream with full context for debugging.
    """

    DEAD_LETTER_STREAM = "dead_letter"

    def __init__(self, redis_client, monitor_alert_callback):
        self.redis = redis_client
        self.alert = monitor_alert_callback

    async def send_to_dead_letter(
        self,
        envelope: dict,
        reason: str,
        error: Optional[Exception] = None,
        consumer_id: Optional[str] = None,
    ):
        """
        Route a failed message to the dead letter queue.
        Preserves original message + failure context.
        """
        dead_letter = {
            "original_message": json.dumps(envelope),
            "reason": reason,
            "error_type": type(error).__name__ if error else None,
            "error_message": str(error) if error else None,
            "consumer_id": consumer_id,
            "dead_lettered_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": envelope.get("metadata", {}).get("retry_count", 0),
            "original_message_id": envelope.get("message_id"),
            "original_channel": envelope.get("channel"),
            "original_source": envelope.get("source_agent"),
            "original_priority": envelope.get("priority"),
        }

        await self.redis.xadd(
            self.DEAD_LETTER_STREAM,
            dead_letter,
            maxlen=50_000,
        )

        # Alert Monitor Agent for P0/P1 dead letters
        if envelope.get("priority") in ("P0", "P1"):
            await self.alert(
                severity="CRITICAL",
                message=f"P{envelope['priority'][1]} message dead-lettered: {reason}",
                context={
                    "message_id": envelope.get("message_id"),
                    "source": envelope.get("source_agent"),
                    "channel": envelope.get("channel"),
                },
            )

        logger.error(
            f"Dead letter: {reason}",
            extra={
                "message_id": envelope.get("message_id"),
                "source": envelope.get("source_agent"),
                "channel": envelope.get("channel"),
                "priority": envelope.get("priority"),
            },
        )
```

### 12.2 Dead Letter Reasons

| Reason Code | Description | Auto-Retry? | Recovery |
|------------|-------------|-------------|----------|
| `TTL_EXPIRED` | Message exceeded TTL before consumption | No | Investigate slow consumer |
| `PROCESSING_ERROR` | Consumer threw unhandled exception | Yes (with backoff) | Fix bug, restart agent |
| `SCHEMA_VALIDATION` | Message failed schema validation | No | Fix producer schema |
| `TARGET_UNAVAILABLE` | Target agent not responding | Yes (3 retries) | Restart target agent |
| `MAX_RETRIES_EXCEEDED` | Retried N times, still failing | No | Escalate to human |
| `CIRCUIT_BREAKER_OPEN` | Target broker/agent circuit breaker tripped | Yes (after recovery) | Wait for recovery |
| `INSUFFICIENT_PERMISSIONS` | Agent lacks permission for operation | No | Fix permissions |
| `UNKNOWN_ERROR` | Unexpected failure | No | Investigate manually |

### 12.3 Retry Policy

```python
class RetryPolicy:
    """
    Configurable retry policy for failed message processing.
    Uses exponential backoff with jitter.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay_ms: int = 1000,
        max_delay_ms: int = 30000,
        backoff_factor: float = 2.0,
        jitter_ms: int = 500,
    ):
        self.max_retries = max_retries
        self.base_delay_ms = base_delay_ms
        self.max_delay_ms = max_delay_ms
        self.backoff_factor = backoff_factor
        self.jitter_ms = jitter_ms

    def get_delay(self, retry_count: int) -> float:
        """Calculate delay for this retry attempt."""
        delay = min(
            self.base_delay_ms * (self.backoff_factor ** retry_count),
            self.max_delay_ms,
        )
        jitter = random.uniform(0, self.jitter_ms)
        return (delay + jitter) / 1000.0  # Convert to seconds

    def should_retry(self, envelope: dict, error: Exception) -> bool:
        """Determine if message should be retried."""
        current_retries = envelope.get("metadata", {}).get("retry_count", 0)

        # Don't retry if max retries exceeded
        if current_retries >= self.max_retries:
            return False

        # Don't retry non-recoverable errors
        if isinstance(error, (SchemaValidationError, PermissionError)):
            return False

        # Retry recoverable errors
        if isinstance(error, (ConnectionError, TimeoutError, BrokerError)):
            return error.recoverable if hasattr(error, "recoverable") else True

        return True


async def process_with_retry(
    envelope: dict,
    handler: Callable,
    retry_policy: RetryPolicy,
    dead_letter: DeadLetterHandler,
):
    """Process a message with retry and dead letter handling."""
    retry_count = envelope.get("metadata", {}).get("retry_count", 0)

    try:
        await handler(envelope)
    except Exception as e:
        if retry_policy.should_retry(envelope, e):
            # Schedule retry with backoff
            delay = retry_policy.get_delay(retry_count)
            envelope["metadata"]["retry_count"] = retry_count + 1
            envelope["metadata"]["original_message_id"] = envelope["message_id"]

            await asyncio.sleep(delay)

            # Re-publish to the same stream for retry
            await redis.xadd(
                envelope["channel"],
                {"message": json.dumps(envelope)},
            )
        else:
            # Send to dead letter
            await dead_letter.send_to_dead_letter(
                envelope=envelope,
                reason="MAX_RETRIES_EXCEEDED" if retry_count >= retry_policy.max_retries else "PROCESSING_ERROR",
                error=e,
            )
```

### 12.4 Dead Letter Monitoring

The Monitor Agent watches the dead letter queue and takes action:

```python
class DeadLetterMonitor:
    """
    Monitors the dead letter queue for patterns and alerts.
    """

    ALERT_THRESHOLDS = {
        "dead_letters_per_minute": 10,    # >10/min = system degradation
        "dead_letters_per_hour": 100,     # >100/hour = serious issue
        "p0_dead_letters": 1,             # Any P0 dead letter = immediate alert
        "same_agent_dead_letters": 5,     # 5+ from same agent = agent failure
    }

    async def monitor(self):
        """Background monitoring of dead letter queue."""
        while True:
            stats = await self._get_stats()

            # P0 dead letter = immediate alert
            if stats["p0_count"] > 0:
                await self._alert("CRITICAL", f"{stats['p0_count']} P0 messages in dead letter queue")

            # Rate-based alerts
            if stats["per_minute"] > self.ALERT_THRESHOLDS["dead_letters_per_minute"]:
                await self._alert("WARNING", f"High dead letter rate: {stats['per_minute']}/min")

            # Agent-specific alerts
            for agent, count in stats["by_agent"].items():
                if count > self.ALERT_THRESHOLDS["same_agent_dead_letters"]:
                    await self._alert("WARNING", f"Agent {agent} has {count} dead letters — possible failure")

            await asyncio.sleep(60)  # Check every minute
```

---

## 13. Message Ordering and Deduplication

### 13.1 Ordering Guarantees

| Scope | Guarantee | Mechanism |
|-------|----------|-----------|
| **Global** | No guarantee | Redis Pub/Sub has no ordering across channels |
| **Per-stream** | Insertion order | Redis Streams guarantee per-stream ordering |
| **Per-correlation** | Ordered within pipeline | Partitioned reads group by correlation_id |
| **Per-agent** | FIFO within priority | Priority inbox drains P0→P1→P2→P3→P4 |

### 13.2 Ordering Enforcement

```python
class OrderedPipelineProcessor:
    """
    Ensures pipeline messages are processed in correct order.
    Within a correlation_id (pipeline run), messages must be processed
    in the order they were produced.
    """

    def __init__(self):
        self.sequence_numbers = {}  # correlation_id → next expected sequence

    async def process_ordered(
        self,
        stream_key: str,
        consumer_group: str,
        handler: Callable,
    ):
        """Read and process messages in order per correlation_id."""
        messages = await redis.xreadgroup(
            consumer_group,
            "ordered_consumer",
            {stream_key: ">"},
            count=50,
            block=1000,
        )

        # Group by correlation_id
        grouped = defaultdict(list)
        for stream, entries in messages:
            for msg_id, fields in entries:
                envelope = json.loads(fields[b"message"])
                corr_id = envelope.get("correlation_id", "_none")
                grouped[corr_id].append((msg_id, envelope))

        # Process each group in order
        for corr_id, msgs in grouped.items():
            # Sort by message_id (which encodes insertion order in Redis Streams)
            msgs.sort(key=lambda x: x[0])

            for msg_id, envelope in msgs:
                await handler(envelope)
                await redis.xack(stream_key, consumer_group, msg_id)
```

### 13.3 Deduplication Strategy

Two layers of deduplication prevent duplicate processing:

#### Layer 1: Message ID Deduplication (At-Producer)

```python
class DeduplicatingProducer:
    """
    Prevents duplicate messages at the producer side.
    Uses a Bloom filter for O(1) memory-efficient dedup.
    """

    def __init__(self, redis_client, bloom_key: str = "dedup:bloom"):
        self.redis = redis_client
        self.bloom_key = bloom_key
        self.local_cache = set()  # Hot path: in-memory set
        self.local_cache_max = 100_000

    async def publish_if_unique(
        self,
        stream_key: str,
        envelope: dict,
    ) -> bool:
        """
        Publish message only if not a duplicate.
        Returns True if published, False if duplicate.
        """
        dedup_key = envelope.get("idempotency_key") or envelope["message_id"]

        # Check local cache first (fastest)
        if dedup_key in self.local_cache:
            logger.info(f"Dedup: skipping duplicate {dedup_key}")
            return False

        # Check Redis Bloom filter
        is_duplicate = await self.redis.execute_command(
            "BF.EXISTS", self.bloom_key, dedup_key
        )
        if is_duplicate:
            logger.info(f"Dedup: Bloom filter hit for {dedup_key}")
            self.local_cache.add(dedup_key)
            return False

        # Not a duplicate — publish and record
        await self.redis.xadd(
            stream_key,
            {"message": json.dumps(envelope)},
        )

        # Add to Bloom filter
        await self.redis.execute_command("BF.ADD", self.bloom_key, dedup_key)

        # Add to local cache
        if len(self.local_cache) >= self.local_cache_max:
            # Evict oldest (simple FIFO)
            self.local_cache.pop()
        self.local_cache.add(dedup_key)

        return True
```

#### Layer 2: Idempotent Consumer (At-Consumer)

```python
class IdempotentConsumer:
    """
    Ensures messages are processed exactly once at the consumer side.
    Uses Redis SET with NX (set-if-not-exists) for atomic dedup.
    """

    def __init__(self, redis_client, agent_id: str):
        self.redis = redis_client
        self.agent_id = agent_id
        self.processed_prefix = f"processed:{agent_id}"

    async def process_once(
        self,
        envelope: dict,
        handler: Callable,
    ) -> bool:
        """
        Process message only if not already processed.
        Returns True if processed, False if already seen.
        """
        message_id = envelope["message_id"]
        idempotency_key = envelope.get("idempotency_key")
        dedup_key = idempotency_key or message_id

        # Atomic: SET if not exists, with TTL
        was_set = await self.redis.set(
            f"{self.processed_prefix}:{dedup_key}",
            "1",
            nx=True,  # Only set if not exists
            ex=3600,   # 1 hour TTL (cleanup old entries)
        )

        if not was_set:
            logger.info(f"Idempotent: already processed {dedup_key}")
            return False

        try:
            await handler(envelope)
            return True
        except Exception as e:
            # Processing failed — remove the dedup key so it can be retried
            await self.redis.delete(f"{self.processed_prefix}:{dedup_key}")
            raise
```

#### Layer 3: Audit Trail (At-Broker)

Every message that passes through the system is logged to the audit stream for compliance and debugging:

```python
class AuditLogger:
    """
    Append-only audit log of all messages.
    Used for compliance, debugging, and replay.
    """

    AUDIT_STREAM = "audit_log"

    async def log_message(self, envelope: dict, direction: str, agent_id: str):
        """
        Log a message to the audit trail.
        direction: "PRODUCED" | "CONSUMED" | "DEAD_LETTER"
        """
        audit_entry = {
            "message_id": envelope["message_id"],
            "source_agent": envelope.get("source_agent"),
            "target_agent": envelope.get("target_agent"),
            "channel": envelope.get("channel"),
            "priority": envelope.get("priority"),
            "message_type": envelope.get("message_type"),
            "correlation_id": envelope.get("correlation_id"),
            "direction": direction,
            "agent_id": agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload_hash": hashlib.sha256(
                json.dumps(envelope.get("payload", {}), sort_keys=True).encode()
            ).hexdigest()[:16],
        }

        await redis.xadd(
            self.AUDIT_STREAM,
            audit_entry,
            maxlen=1_000_000,
        )
```

---

## 14. Protocol State Machines

### 14.1 Pipeline State Machine

Each instrument pipeline run follows a strict state machine:

```
┌─────────────┐
│   IDLE      │ ◄── Pipeline complete or cancelled
└──────┬──────┘
       │ Trigger (H4 candle, session change, news)
       ▼
┌─────────────┐
│  PHASE_1    │  Context Gathering (parallel: Fundamental + Structure)
│  CONTEXT    │
└──────┬──────┘
       │ Both agents complete
       ▼
┌─────────────┐
│  PHASE_2    │  Bias Construction (Structure Agent combines)
│  BIAS       │
└──────┬──────┘
       │ Bias established
       ▼
┌─────────────┐
│  PHASE_3    │  Signal Detection (parallel: SMC, Momentum, Candlestick, Liquidity, S/R)
│  SIGNALS    │
└──────┬──────┘
       │ All signal agents complete
       ▼
┌─────────────┐
│  PHASE_4    │  Confluence Scoring (Signal Aggregator)
│  CONFLUENCE │
└──────┬──────┘
       │ Score ≥ 40: proceed | Score < 40: → IDLE
       ▼
┌─────────────┐
│  PHASE_5    │  Trade Preparation (Entry + Risk Gate)
│  PREPARATION│
└──────┬──────┘
       │ Approved: proceed | Rejected: → IDLE
       ▼
┌─────────────┐
│  PHASE_6    │  Execution + Management
│  EXECUTION  │
└──────┬──────┘
       │ Position closed
       ▼
┌─────────────┐
│  PHASE_7    │  Reflection + Journaling
│  REVIEW     │
└──────┬──────┘
       │ Complete
       ▼
┌─────────────┐
│   IDLE      │
└─────────────┘

FAILURE AT ANY PHASE:
  → Log error
  → Send to dead letter
  → Alert Monitor Agent
  → Pipeline state → FAILED
  → After recovery: Resume from failed phase
```

### 14.2 Agent Lifecycle State Machine

```
┌─────────┐    spawn    ┌─────────┐    start     ┌──────────┐
│  NONE   │───────────►│ CREATED │────────────►│  READY   │
└─────────┘             └─────────┘              └────┬─────┘
                                                      │ receive_work
                                                      ▼
                                                 ┌──────────┐
                                                 │ RUNNING  │
                                                 └────┬─────┘
                                            ┌─────────┼─────────┐
                                            │         │         │
                                     timeout│   error │   done  │
                                            ▼         ▼         ▼
                                       ┌─────────┐ ┌────────┐ ┌──────────┐
                                       │ PAUSED  │ │ FAILED │ │COMPLETE  │
                                       │ (HITL)  │ └───┬────┘ └────┬─────┘
                                       └────┬────┘     │           │
                                            │    retry │     archive│
                                            ▼          ▼           ▼
                                       ┌─────────┐ ┌────────┐ ┌─────────┐
                                       │ RUNNING │ │CREATED │ │ RETIRED │
                                       └─────────┘ └────────┘ └─────────┘
```

---

## 15. Security and Authentication

### 15.1 Agent Identity

Each agent has a cryptographic identity for message authentication:

```json
{
  "agent_id": "smc_agent_01",
  "agent_type": "smc",
  "depth": 1,
  "public_key": "base64-encoded-ed25519-public-key",
  "permissions": {
    "read_streams": ["pipeline.structure", "pipeline.liquidity", "state:regime", "state:session"],
    "write_streams": ["pipeline.smc"],
    "read_state": ["state:regime", "state:session", "state:signal_cache"],
    "write_state": ["state:signal_cache:smc"],
    "publish_events": [],
    "subscribe_events": ["events.kill_switch", "events.market_data", "events.regime_change"],
    "spawn_children": true,
    "max_children": 2,
    "execute_orders": false
  }
}
```

### 15.2 Message Signing

For production deployments, messages are signed to prevent tampering:

```python
class MessageSigner:
    """
    Sign and verify messages using Ed25519.
    Ensures message integrity and authenticity.
    """

    def __init__(self, agent_id: str, private_key: bytes):
        self.agent_id = agent_id
        self.private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)

    def sign(self, envelope: dict) -> str:
        """Sign envelope, return signature as base64."""
        # Canonical JSON: sorted keys, no whitespace
        canonical = json.dumps(
            {k: v for k, v in sorted(envelope.items()) if k != "signature"},
            sort_keys=True,
            separators=(",", ":"),
        )
        signature = self.private_key.sign(canonical.encode())
        return base64.b64encode(signature).decode()

    @staticmethod
    def verify(envelope: dict, public_key: bytes) -> bool:
        """Verify message signature."""
        signature = base64.b64decode(envelope.pop("signature", ""))
        canonical = json.dumps(
            {k: v for k, v in sorted(envelope.items())},
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            ed25519.Ed25519PublicKey.from_public_bytes(public_key).verify(
                signature, canonical.encode()
            )
            return True
        except InvalidSignature:
            return False
```

### 15.3 Permission Enforcement

The message broker layer enforces permissions at the Redis level:

```python
class PermissionGuard:
    """
    Enforces agent permissions before message operations.
    Runs as middleware in the message broker.
    """

    def __init__(self, agent_permissions: dict):
        self.permissions = agent_permissions

    async def check_write(self, agent_id: str, stream_key: str) -> bool:
        """Check if agent can write to this stream."""
        perms = self.permissions.get(agent_id, {})
        allowed = perms.get("write_streams", [])

        # Wildcard check
        if "*" in allowed:
            return True

        # Exact match or prefix match (e.g., "pipeline.*")
        for pattern in allowed:
            if pattern.endswith("*"):
                if stream_key.startswith(pattern[:-1]):
                    return True
            elif stream_key == pattern:
                return True

        logger.warning(
            f"Permission denied: {agent_id} cannot write to {stream_key}"
        )
        return False

    async def check_read(self, agent_id: str, stream_key: str) -> bool:
        """Check if agent can read from this stream."""
        perms = self.permissions.get(agent_id, {})
        allowed = perms.get("read_streams", [])

        if "*" in allowed:
            return True

        for pattern in allowed:
            if pattern.endswith("*"):
                if stream_key.startswith(pattern[:-1]):
                    return True
            elif stream_key == pattern:
                return True

        return False

    async def check_execute_orders(self, agent_id: str) -> bool:
        """Check if agent can execute orders."""
        perms = self.permissions.get(agent_id, {})
        return perms.get("execute_orders", False)
```

**Critical rule:** Only the Execution Agent has `execute_orders: true`. The permission is enforced at the broker layer, not just in the agent prompt.

---

## 16. Monitoring and Observability

### 16.1 Protocol Metrics

```python
PROTOCOL_METRICS = {
    # Throughput
    "messages_produced_total": Counter("messages_produced", "Total messages produced", ["agent", "channel", "priority"]),
    "messages_consumed_total": Counter("messages_consumed", "Total messages consumed", ["agent", "channel", "priority"]),
    "messages_dead_lettered_total": Counter("messages_dead_lettered", "Total dead lettered", ["agent", "reason"]),

    # Latency
    "message_latency_seconds": Histogram("message_latency", "End-to-end message latency", ["channel", "priority"]),
    "processing_time_seconds": Histogram("processing_time", "Message processing time", ["agent", "message_type"]),

    # Queue depth
    "stream_length": Gauge("stream_length", "Current stream length", ["stream"]),
    "consumer_lag": Gauge("consumer_lag", "Consumer lag in messages", ["consumer_group", "stream"]),

    # Errors
    "processing_errors_total": Counter("processing_errors", "Processing errors", ["agent", "error_type"]),
    "retry_total": Counter("retries", "Message retries", ["agent", "retry_count"]),

    # Health
    "agent_heartbeat": Gauge("agent_heartbeat", "Last heartbeat timestamp", ["agent"]),
    "circuit_breaker_state": Gauge("circuit_breaker_state", "Circuit breaker state (0=closed, 1=open)", ["broker"]),
}
```

### 16.2 End-to-End Tracing

Every pipeline run generates a **trace** that can be followed from trigger to completion:

```python
class PipelineTracer:
    """
    Distributed tracing for pipeline execution.
    Tracks message flow from trigger through all agents.
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    async def start_trace(
        self,
        correlation_id: str,
        trigger: str,
        instrument: str,
    ):
        """Start a new pipeline trace."""
        trace = {
            "correlation_id": correlation_id,
            "trigger": trigger,
            "instrument": instrument,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "phases": [],
            "status": "IN_PROGRESS",
        }
        await self.redis.hset(f"trace:{correlation_id}", mapping={
            "data": json.dumps(trace),
        })
        await self.redis.expire(f"trace:{correlation_id}", 86400)  # 24h TTL

    async def record_phase(
        self,
        correlation_id: str,
        phase: str,
        agent_id: str,
        status: str,
        duration_ms: int,
        message_id: str,
    ):
        """Record a pipeline phase completion."""
        key = f"trace:{correlation_id}"
        raw = await self.redis.hget(key, "data")
        if not raw:
            return

        trace = json.loads(raw)
        trace["phases"].append({
            "phase": phase,
            "agent": agent_id,
            "status": status,
            "duration_ms": duration_ms,
            "message_id": message_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

        await self.redis.hset(key, "data", json.dumps(trace))

    async def complete_trace(self, correlation_id: str, final_status: str):
        """Mark pipeline trace as complete."""
        key = f"trace:{correlation_id}"
        raw = await self.redis.hget(key, "data")
        if not raw:
            return

        trace = json.loads(raw)
        trace["status"] = final_status
        trace["completed_at"] = datetime.now(timezone.utc).isoformat()

        if trace["phases"]:
            start = datetime.fromisoformat(trace["started_at"])
            end = datetime.fromisoformat(trace["completed_at"])
            trace["total_duration_ms"] = int((end - start).total_seconds() * 1000)

        await self.redis.hset(key, "data", json.dumps(trace))
```

### 16.3 Grafana Dashboard Panels

| Panel | Metric | Alert Threshold |
|-------|--------|----------------|
| **Pipeline Latency** | `message_latency_seconds` by phase | > 30s per phase |
| **Consumer Lag** | `consumer_lag` per consumer group | > 1000 messages |
| **Dead Letter Rate** | `messages_dead_lettered_total` rate | > 10/min |
| **Error Rate** | `processing_errors_total` rate by agent | > 5/min per agent |
| **Stream Depth** | `stream_length` per stream | > 50,000 |
| **Agent Health** | `agent_heartbeat` staleness | > 2 min stale |
| **Circuit Breaker** | `circuit_breaker_state` | Any open = alert |
| **Message Throughput** | `messages_produced_total` rate | Deviation from baseline |

---

## 17. Implementation Reference

### 17.1 Core Python Module

```python
# alphastack/messaging/__init__.py
"""
Alpha Stack Agent Communication Protocol — Core Module
"""

from .envelope import create_envelope, validate_envelope
from .producer import MessageProducer
from .consumer import PriorityInbox, IdempotentConsumer
from .router import MessageRouter
from .dead_letter import DeadLetterHandler
from .dedup import DeduplicatingProducer
from .broadcast import BroadcastPublisher, BroadcastSubscriber
from .direct import DirectMessenger, ScatterGather
from .state import SharedStateManager
from .audit import AuditLogger
from .tracer import PipelineTracer
from .permissions import PermissionGuard
from .signing import MessageSigner
from .metrics import ProtocolMetrics
from .retry import RetryPolicy, process_with_retry
```

### 17.2 Agent Base Class

```python
class AlphaStackAgent:
    """
    Base class for all Alpha Stack agents.
    Provides communication primitives.
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        redis_client,
        config: dict,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.redis = redis_client
        self.config = config

        # Communication components
        self.producer = MessageProducer(agent_id, redis_client)
        self.consumer = PriorityInbox(
            stream_key=config["input_stream"],
            consumer_group=f"cg:{agent_type}",
            consumer_name=agent_id,
        )
        self.messenger = DirectMessenger(agent_id, redis_client)
        self.broadcast = BroadcastSubscriber(agent_id, redis_client)
        self.dedup = IdempotentConsumer(redis_client, agent_id)
        self.state = SharedStateManager(redis_client)
        self.audit = AuditLogger(redis_client)

        # Agent-specific filter
        self.filter = MessageFilter(agent_id, config.get("filter", {}))

    async def start(self):
        """Start agent: begin consuming messages and broadcasts."""
        await self.consumer.start()
        await self.broadcast.start()
        await self.messenger.listen_for_responses()
        asyncio.create_task(self._process_loop())

    async def _process_loop(self):
        """Main processing loop."""
        while True:
            msg_id, envelope = await self.consumer.receive()

            # Apply filter
            if not self.filter.should_process(envelope):
                await self.consumer.ack(msg_id)
                continue

            # Idempotent processing
            processed = await self.dedup.process_once(
                envelope,
                lambda e: self.handle_message(e),
            )

            if processed:
                await self.audit.log_message(envelope, "CONSUMED", self.agent_id)

            await self.consumer.ack(msg_id)

    async def handle_message(self, envelope: dict):
        """Override in subclass. Process a message."""
        raise NotImplementedError

    async def emit_signal(self, channel: str, payload: dict, priority: str = "P2"):
        """Emit a signal to a pipeline channel."""
        envelope = create_envelope(
            source_agent=self.agent_id,
            channel=channel,
            priority=priority,
            message_type="SIGNAL",
            payload=payload,
        )
        await self.producer.publish(channel, envelope)
        await self.audit.log_message(envelope, "PRODUCED", self.agent_id)
```

### 17.3 Redis Lua Scripts for Atomic Operations

```lua
-- state_update.lua
-- Atomic read-modify-write for shared state
-- KEYS[1] = state hash key
-- ARGV[1] = field name
-- ARGV[2] = new value (JSON)
-- ARGV[3] = expected version (for CAS)
-- Returns: 1 if updated, 0 if version mismatch

local current_version = redis.call('HGET', KEYS[1], 'version')
if current_version ~= ARGV[3] then
    return 0  -- Version mismatch, retry
end

redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
redis.call('HINCRBY', KEYS[1], 'version', 1)
return 1
```

```lua
-- dedup_check.lua
-- Atomic check-and-set for deduplication
-- KEYS[1] = dedup key
-- ARGV[1] = message id
-- ARGV[2] = TTL seconds
-- Returns: 1 if unique (set), 0 if duplicate

if redis.call('EXISTS', KEYS[1]) == 1 then
    return 0  -- Duplicate
end

redis.call('SETEX', KEYS[1], ARGV[2], ARGV[1])
return 1  -- Unique
```

---

## 18. Testing Strategy

### 18.1 Test Categories

| Category | Purpose | Tools |
|----------|---------|-------|
| **Unit** | Message serialization, filtering, dedup logic | pytest, fakeredis |
| **Integration** | Redis Streams, Pub/Sub, consumer groups | pytest + real Redis |
| **Contract** | Schema validation, message format compatibility | jsonschema, schemathesis |
| **Load** | Throughput, latency under load | locust, custom benchmarks |
| **Chaos** | Failure injection, network partitions | toxiproxy, custom chaos |
| **E2E** | Full pipeline with mock agents | docker-compose test stack |

### 18.2 Key Test Scenarios

| Scenario | Expected Behavior |
|----------|------------------|
| Normal pipeline flow | All 7 phases complete, trade executed |
| Agent timeout | Pipeline pauses, Monitor alerts, agent restarts |
| Duplicate message | Processed once (idempotent), logged |
| Out-of-order messages | Reordered per correlation_id |
| Dead letter overflow | Alert triggered, oldest entries evicted |
| Kill switch broadcast | All agents halt within 1 second |
| Circuit breaker trip | Orders halted, existing positions managed |
| Network partition | Agents buffer locally, reconnect with replay |
| Schema version mismatch | Old consumers skip unknown fields, log warning |
| Bloom filter false positive | Rare duplicate skipped (acceptable tradeoff) |

### 18.3 Chaos Testing Scenarios

```python
# Chaos test: Kill random agents during pipeline execution
async def test_chaos_agent_kill():
    """Kill SMC agent mid-processing, verify pipeline recovers."""
    pipeline = PipelineRunner("EURUSD")

    # Start pipeline
    await pipeline.start()

    # Wait until Phase 3 (signal detection)
    await pipeline.wait_for_phase("PHASE_3")

    # Kill SMC agent
    await kill_agent("smc_agent_01")

    # Verify: pipeline should pause and wait for agent restart
    assert pipeline.state == "PHASE_3_WAITING"

    # Agent restarts
    await restart_agent("smc_agent_01")

    # Verify: pipeline resumes from Phase 3
    await pipeline.wait_for_phase("PHASE_4", timeout=60)
    assert pipeline.state == "PHASE_4"

# Chaos test: Redis connection drop
async def test_chaos_redis_disconnect():
    """Simulate Redis connection drop, verify agents buffer and reconnect."""
    agent = SMCAgent("smc_agent_01")

    # Start producing messages
    await agent.emit_signal("pipeline.smc", {"test": "data"})

    # Drop Redis connection
    await drop_redis_connection()

    # Agent should buffer locally
    assert agent.local_buffer_size > 0

    # Restore Redis
    await restore_redis_connection()

    # Agent should flush buffer
    await asyncio.sleep(5)
    assert agent.local_buffer_size == 0

    # Verify messages delivered
    count = await count_stream_messages("pipeline.smc")
    assert count > 0
```

---

## 19. Appendices

### A. Message Type Registry

| Type | Direction | Channel | Priority | TTL | Description |
|------|----------|---------|----------|-----|-------------|
| `SIGNAL` | Analysis → Aggregator | `pipeline.*` | P2 | 1h | Analysis output |
| `TRADE_PROPOSAL` | Aggregator → Risk | `pipeline.confluence` | P1 | 5m | Trade setup |
| `RISK_DECISION` | Risk → Execution | `pipeline.risk_gate` | P0 | 1m | Gate decision |
| `EXECUTION_RESULT` | Execution → Monitor | `pipeline.execution` | P1 | 24h | Fill result |
| `MANAGEMENT_ACTION` | Trade Mgmt → Execution | `pipeline.management` | P1 | 5m | In-trade action |
| `JOURNAL_ENTRY` | Journal → Storage | `pipeline.journal` | P4 | 24h | Trade record |
| `COMMAND` | Orchestrator → Any | `events.*` or direct | P0 | 24h | Control command |
| `QUERY` | Any → Any | `request.{target}` | P2 | 30s | Data request |
| `RESPONSE` | Any → Any | `response.{corr_id}` | P2 | 30s | Query response |
| `HEARTBEAT` | Any → Monitor | `events.system_health` | P4 | 5m | Health check |
| `EVENT` | Any → Subscribers | `events.*` | P1-P3 | 1h | System event |
| `ACK` | Consumer → Producer | (internal) | P2 | 1m | Acknowledgment |
| `NACK` | Consumer → Producer | (internal) | P2 | 1m | Negative ack |
| `ERROR` | Any → Monitor | `events.system_health` | P1 | 1h | Error report |

### B. Stream Naming Convention

```
Pattern: {namespace}.{category}[.{subcategory}]

Namespaces:
  pipeline.*     → Analysis pipeline signal flow
  request.*      → Direct agent request inbox
  response.*     → Direct agent response
  events.*       → Broadcast events
  state:*        → Shared state (Redis Hash)
  dedup:*        → Deduplication keys
  trace:*        → Pipeline trace data
  processed:*    → Consumer dedup keys
  dead_letter    → Failed messages
  audit_log      → Compliance audit trail
```

### C. Configuration Template

```yaml
# config/messaging.yaml
messaging:
  redis:
    host: "localhost"
    port: 6379
    db: 0
    password: "${REDIS_PASSWORD}"
    max_connections: 50

  streams:
    pipeline:
      max_len: 100000
      retention_hours: 72
    request:
      max_len: 10000
      retention_hours: 1
    response:
      max_len: 10000
      retention_hours: 1
    dead_letter:
      max_len: 50000
      retention_hours: 168
    audit:
      max_len: 1000000
      retention_hours: 720

  priorities:
    P0:
      label: "CRITICAL"
      latency_target_ms: 1000
      preemptive: true
    P1:
      label: "HIGH"
      latency_target_ms: 5000
    P2:
      label: "MEDIUM"
      latency_target_ms: 30000
    P3:
      label: "LOW"
      latency_target_ms: 300000
    P4:
      label: "BACKGROUND"
      latency_target_ms: 1800000

  dedup:
    bloom_filter:
      expected_items: 1000000
      false_positive_rate: 0.001
    idempotency_ttl_seconds: 3600

  retry:
    max_retries: 3
    base_delay_ms: 1000
    max_delay_ms: 30000
    backoff_factor: 2.0
    jitter_ms: 500

  dead_letter:
    alert_on_p0: true
    alert_on_p1: true
    alert_threshold_per_minute: 10

  monitoring:
    metrics_port: 9090
    trace_retention_hours: 24
    health_check_interval_seconds: 30
```

### D. Technology Summary

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Message Broker | Redis | 7+ | Streams, Pub/Sub, Hashes |
| Serialization | JSON | RFC 8259 | Message format (human-readable) |
| Serialization (hot path) | MessagePack | 1.0+ | Binary format for tick data |
| Bloom Filter | RedisBloom | 2.6+ | Deduplication |
| Schema Validation | jsonschema | 4.0+ | Message format validation |
| Tracing | Custom (Redis-backed) | — | Pipeline execution traces |
| Metrics | Prometheus | 2.x+ | Protocol observability |
| Dashboards | Grafana | 10.x+ | Visual monitoring |
| Encryption | Ed25519 | — | Message signing |
| Testing | pytest + fakeredis | — | Unit and integration tests |

---

*Document generated: 2026-07-11*
*Author: Agent Communication Architect — Alpha Stack*
*Status: Architecture Design Complete — Ready for Implementation Review*
*Next: Review with team → Begin Phase 1 implementation (Week 2 of roadmap)*
