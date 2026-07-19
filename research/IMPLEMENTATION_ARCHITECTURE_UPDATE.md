# AlphaStack — Implementation Architecture Update
## Week of July 19, 2026

**Version:** 2.0  
**Date:** 2026-07-19  
**Author:** Architecture Agent  
**Inputs:** 9 research files (`ai_week_*.md`), 4 architecture docs  
**Status:** Architecture Update — Ready for Review  
**Supersedes:** Prior architecture assumptions where noted

---

## Table of Contents

1. [What Changed in AI This Week](#1-what-changed-in-ai-this-week)
2. [Architecture Decisions That Need Updating](#2-architecture-decisions-that-need-updating)
3. [New Components to Add](#3-new-components-to-add)
4. [Components to Remove or Deprioritize](#4-components-to-remove-or-deprioritize)
5. [Updated Tech Stack Recommendations](#5-updated-tech-stack-recommendations)
6. [Priority Implementation Roadmap](#6-priority-implementation-roadmap)
7. [Risk Register Updates](#7-risk-register-updates)

---

## 1. What Changed in AI This Week That Affects AlphaStack's Architecture

### 1.1 The Model Cost Revolution (CRITICAL)

The cost-performance frontier has shifted dramatically. AlphaStack's architecture assumed expensive LLM inference; the ground has moved.

| Model | Input (Cache Hit) | Output | Context | Implication |
|-------|-------------------|--------|---------|-------------|
| **DeepSeek V4-Flash** | **$0.0028/MTok** | $0.28 | 1M | Essentially free for 16 agents with caching |
| **Claude Sonnet 5** | $2.00 (intro) | $10.00 | — | Best agentic reliability at mid-tier cost |
| **GPT-5.6 Luna** | ~$0.25* | ~$0.75* | — | Outperforms Opus 4.8 at 1/4 cost |
| **Kimi K3** | $0.30 (cached) | — | 1M | Open weights (Jul 27), 50B active from 2.8T |
| **Qwen3 (self-hosted)** | $0 | $0 | — | Apache 2.0, 119 languages |

*Source: ai_week_voice_reasoning_llm.md*

**AlphaStack Impact:** The architecture doc estimated ~$1.47/day for 16 agents using "reasoning-tier" and "fast model" tiers. With DeepSeek V4-Flash at $0.0028/MTok (cache hit), the actual cost drops to **~$0.07/day** — a 95% reduction. This changes the economic model for the entire system.

### 1.2 Open-Source Models Caught Proprietary (HIGH)

Kimi K3 (2.8T params, open-source) approaches Claude Fable 5 and GPT-5.6 Sol performance. Qwen3 supports 119 languages including African languages (Swahili, Hausa, Yoruba, Amharic). Bonsai 27B runs a 27B-class model on a phone at 3.9GB with 90% quality retention.

*Sources: ai_week_agi_race.md, ai_week_emerging_systems.md, ai_week_voice_ondevice.md*

**AlphaStack Impact:** The proprietary model moat is eroding. AlphaStack can now run near-frontier models self-hosted (zero API dependency) or use ultra-cheap open-source API endpoints. The architecture's assumption of "DeepSeek/Qwen via API" for LLM integration needs expanding to include self-hosted options and a multi-model routing layer.

### 1.3 Harness > Model Is Now Consensus (HIGH)

LangChain + NVIDIA's NemoClaw blueprint proved that a tuned harness with an open model (Nemotron 3 Ultra) scored 0.86 at $4.48/run, matching Opus 4.8's 0.87 at $43.48/run — a 10x cost reduction. The industry consensus is: **loop orchestration quality matters more than raw model capability**.

*Source: ai_week_loops_self_improving.md*

**AlphaStack Impact:** This validates AlphaStack's 5-loop architecture as a competitive advantage. Investment should shift from "which model" to "how well are the loops tuned." The 5 cognitive loop types (ReAct, Deliberation, Plan-and-Execute, Reflection, Event-driven) are the harness — they need tuning, not the models.

### 1.4 Agent Improvement = Data Mining from Traces (HIGH)

LangChain published the paradigm: agent improvement is a data mining problem. Traces are the currency. The improvement loop is: mine traces → curate evals → run experiments → improve specific axes. Every continual learning company is also an observability company.

*Source: ai_week_loops_self_improving.md*

**AlphaStack Impact:** AlphaStack's Reflection loop already exists but lacks a systematic trace mining pipeline. The architecture needs a dedicated trace capture, storage, and mining subsystem — this is how the system gets better over time, not through model upgrades.

### 1.5 Agent Security Is a Real Problem (HIGH)

VentureBeat Pulse Research: 54% of enterprises have had a confirmed agent security incident or near-miss. Only 32% give every agent its own scoped identity. OWASP published its first Agentic AI Security Maturity Framework with 6 adoption levels (AT0–AT5) and identified memory poisoning, cascading failures, and goal hijacking as top risks. Microsoft open-sourced an Agent Governance Toolkit with sub-millisecond policy enforcement.

*Sources: ai_week_emerging_systems.md, ai_week_multi_agent.md*

**AlphaStack Impact:** AlphaStack with 16+ agents is an AT5 system (custom in-house multi-agent). It needs Level 2+ governance at minimum. The current architecture has risk enforcement at infrastructure level (good), but lacks memory integrity protection, agent identity scoping, and formal governance tooling.

### 1.6 MCP + A2A Protocol Convergence (MEDIUM)

MCP (Model Context Protocol) crossed 97M+ monthly SDK downloads. A2A (Agent-to-Agent) protocol crossed 150+ organizations under the Linux Foundation with v1.0 stable. Industry consensus: **MCP = how agents talk to tools; A2A = how agents talk to each other**. ACP (IBM) is dead — merged into A2A.

*Source: ai_week_multi_agent.md*

**AlphaStack Impact:** AlphaStack uses custom Redis Streams for inter-agent communication. MCP should be adopted for tool integrations. A2A should be evaluated as a potential replacement or augmentation for the Redis Streams event bus — it would enable dynamic agent discovery and cross-system federation.

### 1.7 On-Device Inference Is Now Viable (MEDIUM-HIGH)

PrismML Bonsai 27B: 3.9GB model fits on an iPhone 17 Pro, retains 90% of 27B quality, supports 262K context, tool calling, and agentic loops. Apple's AFM 3 Core Advanced: 20B sparse model on phones using Instruction-Following Pruning (IFP) — activates only 1-4B parameters per prompt. Google Chrome silently installing 4GB on-device AI models.

*Source: ai_week_voice_ondevice.md*

**AlphaStack Impact:** AlphaStack targets East Africa where devices are resource-constrained. On-device inference means trading signal generation could happen locally on mid-range Android phones (6-8GB RAM), eliminating cloud dependency and latency for basic analysis. The architecture should include an on-device inference tier.

### 1.8 Model Routing Is Harder Than Expected (MEDIUM)

IBM Research found that cost ≠ sticker price (GPT-4.1 was 2x more expensive than Claude Sonnet 4.6 in practice due to cache dynamics). Task difficulty estimation is unreliable. Routers must simultaneously optimize cost, quality, latency, compliance, reliability, data residency, and approved model lists.

*Source: ai_week_emerging_systems.md*

**AlphaStack Impact:** The architecture's simple "reasoning-tier" vs "fast model" split is insufficient. A proper model routing layer is needed that considers actual cost (including cache hit rates), task complexity, and agent-specific requirements.

### 1.9 EU AI Act High-Risk Obligations — August 2026 (MEDIUM)

EU AI Act high-risk obligations take effect August 2026. Financial AI systems likely fall under "high-risk" classification requiring risk management systems, data governance documentation, transparency and human oversight provisions, and conformity assessments.

*Sources: ai_week_emerging_systems.md, ai_week_general_landscape.md*

**AlphaStack Impact:** If AlphaStack operates in EU markets, compliance documentation must be in place within weeks. The multi-agent architecture actually helps — each agent's role and decision can be traced for audit purposes.

### 1.10 World Bank "Small AI" Validation (MEDIUM)

The World Bank published a landmark blog arguing "the world's most impactful AI startups will be built in emerging markets." The "Small AI" philosophy — purpose-built, efficient, offline-capable, local-language — matches AlphaStack's approach exactly. A Kenya example: AI embedded into M-Pesa turning transaction data into business insights. A global acceleration program for emerging market AI startups is being developed.

*Source: ai_week_general_landscape.md*

**AlphaStack Impact:** Direct validation of the $7 micro-account approach. The World Bank acceleration program is a potential funding/partnership channel. M-Pesa AI integration is an existing precedent.

---

## 2. Architecture Decisions That Need Updating

### 2.1 LLM Model Selection Strategy

**BEFORE (architecture_ai_models.md):**
- Reasoning-tier: DeepSeek-R1 / QwQ for fundamental analysis
- Fast model: Qwen-2.5-7B / DeepSeek-V3 for quick classification
- Estimated cost: ~$1.47/day for 16 agents

**AFTER:**
- **Primary backbone:** DeepSeek V4-Flash at $0.0028/MTok (cache hit) for all routine agent reasoning
- **Reasoning upgrade:** Claude Sonnet 5 at $2/MTok for complex fundamental analysis and high-stakes decisions
- **Cost-optimized fallback:** Qwen3 self-hosted (Apache 2.0) for zero-cost inference with 119-language support
- **On-device tier:** Bonsai 27B (3.9GB, 1-bit variant) for local inference on user devices
- **Estimated cost:** ~$0.07–$2/day depending on model mix (95% reduction from original estimate)

**Justification:** DeepSeek V4-Flash cache hit pricing at $0.0028/MTok is extraordinary. AlphaStack's repeated system prompts and market context across 16 agents would hit cache consistently. Sonnet 5's agentic reliability ("stays on plan, follows conventions") is best-in-class for critical decisions. Qwen3's 119 languages cover African market languages.

*Source: ai_week_voice_reasoning_llm.md*

### 2.2 Multi-Agent Orchestration Framework

**BEFORE (architecture_multi_agent.md):**
- Custom Python asyncio orchestrator
- Redis Streams for inter-agent communication
- Agent identity defined in JSON but not formally enforced
- No formal governance layer

**AFTER:**
- **Stay with LangGraph 1.0** — validated as #1 production framework (Klarna, Uber in production)
- **Adopt MCP** for all tool integrations (97M+ downloads, universal adoption)
- **Evaluate A2A protocol** for inter-agent communication (v1.0 stable, 150+ orgs)
- **Add per-node timeouts** from LangGraph's Q2 2026 update — prevents runaway agents
- **Add DeltaChannel** for state-diff streaming — reduces Redis Streams message size
- **Integrate Agent Governance Toolkit** (Microsoft, open-source, sub-ms policy enforcement)

**Justification:** LangGraph remains the industry consensus. Per-node timeouts are critical for the sequential pipeline (News → Strategy → Risk → Execution → Reflection). DeltaChannel reduces event bus overhead. MCP standardizes tool connections. A2A could replace custom Redis Streams for inter-agent communication with dynamic agent discovery.

*Source: ai_week_multi_agent.md*

### 2.3 Agent Communication Protocol

**BEFORE (architecture_multi_agent.md):**
- Custom AgentMessage protocol over Redis Streams
- Hardcoded pipeline: News → Strategy → Risk → Execution → Reflection
- Static agent topology

**AFTER:**
- **Phase 1 (immediate):** Keep Redis Streams, add MCP for tool connections
- **Phase 2 (1-3 months):** Evaluate A2A protocol for inter-agent communication
  - Each agent publishes an Agent Card at `/.well-known/agent-card.json`
  - Dynamic capability discovery at runtime
  - JSON-RPC 2.0 wire format (same as MCP)
  - Supports task delegation, status polling, result streaming
- **Phase 3 (3-6 months):** Hybrid A2A + Redis Streams
  - A2A for agent discovery and routing
  - Redis Streams for high-frequency market data distribution
  - Enables parallel agent execution (multiple Strategy agents)

**Justification:** A2A's Agent Card pattern enables adding/removing agents without pipeline code changes. The current hardcoded pipeline is a maintenance burden as the system scales.

*Source: ai_week_multi_agent.md*

### 2.4 Memory Architecture

**BEFORE (architecture_multi_agent.md):**
- 3-layer memory: Working (Redis), Short-term (files), Long-term (vector DB)
- No memory integrity protection
- No formal memory typing

**AFTER:**
- **4-layer memory aligned to CoALA framework:**
  - Working memory: Current market state, active positions (Redis, ephemeral)
  - Episodic memory: Trade history, past market regimes (TimescaleDB + vector DB)
  - Semantic memory: Market structure knowledge, correlation maps (governed semantic layer)
  - Procedural memory: Learned trading patterns, loop selection heuristics (signal weights JSON)
- **Add memory integrity protection:**
  - Append-only memory with audit trail for Reflection agent
  - Memory integrity hashing (detect tampering)
  - Separate read-write memory (recent observations) from read-only memory (validated learnings)
  - Memory decay — older learnings have diminishing influence
- **Add proactive "Market Brain":**
  - Auto-ingest earnings reports, SEC filings, news → structured knowledge wiki
  - Cross-agent knowledge sharing via shared semantic layer
  - Fresh context without manual injection

**Justification:** OWASP identified memory poisoning as a top-10 agentic AI risk. The Reflection agent's memory is the most vulnerable surface — it writes learnings that influence future Strategy and Risk decisions. CoALA framework provides formal memory typing. Proactive memory (OpenWiki Brains pattern) keeps agents current on market developments.

*Sources: ai_week_loops_self_improving.md, ai_week_multi_agent.md*

### 2.5 Agent Identity and Scoping

**BEFORE (architecture_multi_agent.md):**
- Agent identity defined in JSON with permissions
- Only Execution Agent has `execute_orders: true`
- No formal identity verification

**AFTER:**
- **Scoped agent identities with cryptographic verification:**
  - Each agent gets a unique identity with scoped permissions (already defined)
  - Add signed agent credentials (inspired by A2A's Signed Agent Cards)
  - Implement zero-exposure credential pattern (inspired by Anthropic/1Password integration)
  - Per-agent sandboxed execution (inspired by Microsoft Agent Governance Toolkit)
- **Formal intent logging:**
  - Every agent action logs *why* it was taken (which loop type, what reasoning chain)
  - Regulatory requirement for AI-driven trading systems
  - Enables post-hoc analysis and regulatory compliance

**Justification:** VentureBeat research shows only 32% of enterprises give every agent its own scoped identity. AlphaStack needs to be in that 32% from day one for a 16-agent financial system.

*Sources: ai_week_loops_self_improving.md, ai_week_multi_agent.md*

### 2.6 Trace Mining Pipeline (NEW DECISION)

**BEFORE:** Not in architecture. Reflection loop existed but no systematic trace capture.

**AFTER:**
- **Every decision trace captured** (not just outcomes): full reasoning chain, tool calls, model inputs/outputs
- **Trace storage:** Append-only log in TimescaleDB with vector embeddings for semantic search
- **Mining pipeline:** Weekly automated analysis of traces to identify improvement opportunities
- **Feedback loop:** Insights feed back into loop selection, parameter tuning, and signal weight updates

**Justification:** "Agent improvement is a data mining problem" — LangChain's paradigm-setting finding. AlphaStack should treat every trading decision trace as training data for self-improvement. This is how the system compounds its edge over time.

*Source: ai_week_loops_self_improving.md*

---

## 3. New Components to Add

### 3.1 Model Routing Layer

**What:** Intelligent routing of agent requests to the optimal model based on task complexity, cost, latency, and cache dynamics.

**Why:** IBM Research proved model routing is harder than it looks. Token pricing doesn't reflect actual cost (cache hit rates dominate). Financial task complexity is often invisible at routing time.

**Design:**
```
┌─────────────────────────────────────────────────────┐
│                MODEL ROUTING LAYER                    │
│                                                       │
│  Input: Agent request + task metadata                 │
│                                                       │
│  Routing Rules:                                       │
│  ├── Simple classification → DeepSeek V4-Flash        │
│  │   (cache hit: $0.0028/MTok)                        │
│  ├── Complex reasoning → Claude Sonnet 5              │
│  │   ($2/MTok intro)                                  │
│  ├── Critical decisions → GPT-5.6 Terra              │
│  │   (~$0.50/MTok)                                    │
│  ├── African language tasks → Qwen3 (self-hosted)    │
│  │   ($0 API cost)                                    │
│  └── On-device tasks → Bonsai 27B                    │
│      ($0, local inference)                            │
│                                                       │
│  Optimization:                                        │
│  ├── Aggressive context caching (shared system prompts)│
│  ├── Cache hit rate monitoring per agent              │
│  ├── Actual cost tracking (not just token pricing)    │
│  └── Latency-aware routing (time-critical → fast model)│
└─────────────────────────────────────────────────────┘
```

**Effort:** 2 weeks  
**Priority:** Phase 1

### 3.2 Trace Mining Pipeline

**What:** Capture, store, and mine decision traces from all 5 loop types for systematic improvement.

**Why:** The industry consensus is that agent improvement = data mining from traces. AlphaStack's Reflection loop exists but lacks systematic trace infrastructure.

**Components:**
- **Trace Logger:** Captures full decision traces (reasoning chain, tool calls, model I/O, timing)
- **Trace Store:** Append-only TimescaleDB table with vector embeddings
- **Trace Miner:** Weekly automated analysis identifying patterns in winning vs losing trades
- **Insight Feed:** Mines insights back into signal weights, loop parameters, and strategy thresholds

**Effort:** 3 weeks  
**Priority:** Phase 1

### 3.3 Agent Governance Layer

**What:** Policy enforcement layer between agents and execution, inspired by Microsoft's Agent Governance Toolkit.

**Why:** OWASP Agentic AI Security Framework identifies memory poisoning, cascading failures, and goal hijacking as top risks. 54% of enterprises have had agent security incidents. AlphaStack is an AT5 system (highest complexity).

**Components:**
- **Policy Engine:** Sub-millisecond interception of every agent action before execution
- **Memory Integrity Checker:** Validates Reflection agent memory against tampering
- **Circuit Breakers:** Already in architecture, but formalize with OWASP-aligned severity levels
- **Audit Trail:** Every agent action logged with intent, reasoning, and outcome

**Effort:** 2 weeks  
**Priority:** Phase 1

### 3.4 Context Budget Manager

**What:** Per-loop-type context window management to prevent context rot.

**Why:** n8n's context engineering research shows that context windows suffer from "context rot" — high-value instructions get buried under low-value execution data. Each loop type needs different context allocation.

**Design:**
| Loop Type | Context Strategy |
|-----------|-----------------|
| ReAct | Rolling window — keep last 3 action-observation pairs, compress older |
| Deliberation | Full options in window, compress evaluation history |
| Plan-and-Execute | Plan stays, execution details compressed after each step |
| Reflection | Full trade context + compressed historical lessons |
| Event-driven | Minimal — only current event + relevant state |

**Effort:** 1 week  
**Priority:** Phase 1

### 3.5 On-Device Inference Tier

**What:** Lightweight model deployment on user devices for basic signal generation without cloud dependency.

**Why:** Bonsai 27B (3.9GB, 1-bit) fits on mid-range Android phones common in Africa. Retains 90% of 27B quality. Supports tool calling and 262K context. East Africa has network variability — on-device inference eliminates cloud dependency.

**Components:**
- **Model selection:** Bonsai 27B 1-bit variant (Apache 2.0, 3.9GB)
- **Capabilities:** Basic signal generation, price pattern recognition, sentiment classification
- **Limitations:** No complex multi-agent orchestration on-device; use for pre-filtering and alerts
- **Integration:** On-device agents send high-confidence signals to cloud orchestration layer

**Effort:** 4 weeks  
**Priority:** Phase 2

### 3.6 Proactive Market Brain

**What:** Auto-ingesting financial data feeds into a structured knowledge wiki that all agents can reference.

**Why:** OpenWiki Brains pattern from LangChain — proactive memory that connects to external sources and automatically builds structured knowledge. AlphaStack's Event-driven loop already monitors external signals, but lacks a persistent, structured knowledge store.

**Components:**
- **Ingestors:** RSS feeds, economic calendars, earnings reports, SEC filings, central bank statements
- **Processor:** FinBERT sentiment + LLM structuring → knowledge entries
- **Store:** Vector DB with semantic search (replaces raw RSS cache)
- **Access:** All agents can query the Market Brain for context

**Effort:** 3 weeks  
**Priority:** Phase 2

### 3.7 Multi-Teacher Distillation Pipeline

**What:** Train separate RL experts per financial domain, then distill into a unified model.

**Why:** Distillation is the dominant post-training paradigm of 2026. DeepSeek-V4, MiMo-V2-Flash, and GPT-5.6 all use multi-teacher on-policy distillation. This solves the "catastrophic forgetting" problem in multi-task financial RL.

**Design:**
```
Domain Expert 1 (Equities)     ─┐
Domain Expert 2 (Forex)        ─┤
Domain Expert 3 (Macro)        ─┼──▶ On-Policy Distillation ──▶ Unified Model
Domain Expert 4 (Sentiment)    ─┤    (reverse KL loss)
Domain Expert 5 (Risk)         ─┘
```

**Effort:** 6 weeks  
**Priority:** Phase 3

---

## 4. Components to Remove or Deprioritize

### 4.1 DEPRIORITIZE: Custom Transformer Multi-Timeframe Model

**Architecture reference:** `architecture_ai_models.md` — Transformer for multi-timeframe cross-asset analysis (Phase 2+)

**Why deprioritize:**
- Kimi K3 and Qwen3 already handle multi-timeframe reasoning via their 1M context windows
- A general-purpose LLM with proper prompting outperforms a custom transformer for cross-asset reasoning
- The engineering effort (months) doesn't justify the marginal improvement over well-prompted LLMs
- IBM Research showed that model routing and context engineering matter more than custom architectures

**New approach:** Use LLMs with structured prompts for multi-timeframe analysis. Reserve custom transformers for specific, well-defined tasks where LLMs are overkill.

**Effort saved:** 6-8 weeks  
**Risk:** Low — LLMs are already sufficient for this task

### 4.2 DEPRIORITIZE: CNN Chart Pattern Recognition

**Architecture reference:** `architecture_ai_models.md` — CNN for visual candlestick pattern recognition (Phase 2+)

**Why deprioritize:**
- Bonsai 27B and Kimi K3 have native vision capabilities
- General-purpose vision models now match or exceed specialized CNNs for chart pattern recognition
- The labeling effort for 50K+ chart patterns is prohibitive for a small team
- Rule-based pattern detection (already implemented) plus LLM vision is sufficient

**New approach:** Use vision-capable LLMs (Kimi K3 native vision, GPT-5.6) for complex chart analysis. Keep rule-based detection for real-time pattern matching.

**Effort saved:** 4-6 weeks  
**Risk:** Low — vision LLMs are now production-ready for this

### 4.3 DEPRIORITIZE: GAN Synthetic Data Generation

**Architecture reference:** `architecture_ai_models.md` — GAN-generated synthetic market data (Phase 5)

**Why deprioritize:**
- Distillation from multi-teacher experts (Section 3.7) is a better approach to data augmentation
- GANs for financial time series are notoriously difficult to train and validate
- The risk of generating unrealistic market patterns that hurt model performance is high
- Real data + proper augmentation techniques are sufficient

**Effort saved:** 4 weeks  
**Risk:** Low

### 4.4 SIMPLIFY: Event Bus Architecture

**Architecture reference:** `architecture_system.md` — 8 Redis Streams + 4 Pub/Sub channels + 6 shared state hashes

**Why simplify:**
- The current event bus has 18 channels — this is over-engineered for 16 agents
- A2A protocol (if adopted) handles agent discovery and routing natively
- DeltaChannel (LangGraph) reduces the need for full-state streaming
- Consolidate to 4-6 primary streams + A2A for agent-to-agent communication

**New design:**
```
Redis Streams (high-frequency, ordered):
├── market.data          → Ticks + candles (consolidated)
├── pipeline.signals     → All agent signals (consolidated)
├── pipeline.orders      → Order lifecycle events
└── system.events        → Health, alerts, kill switch

A2A Protocol (agent discovery + routing):
├── Agent Cards at /.well-known/agent-card.json
├── Dynamic capability discovery
└── Task delegation + status polling
```

**Effort saved:** 2 weeks  
**Risk:** Medium — needs careful migration

### 4.5 REMOVE: Separate ClickHouse Analytics Database

**Architecture reference:** `architecture_system.md` — ClickHouse for analytics/audit alongside TimescaleDB

**Why remove:**
- TimescaleDB can handle analytics workloads with continuous aggregates
- Running two time-series databases doubles operational complexity for a $7 micro-account system
- ClickHouse is justified at $100K+ capital scale, not at launch
- The research on "Small AI" emphasizes simplicity and efficiency

**New approach:** Use TimescaleDB for everything (time-series + analytics via continuous aggregates). Add ClickHouse only when query performance demands it (>$50K capital).

**Effort saved:** 1 week (avoided setup) + ongoing operational savings  
**Risk:** Low — TimescaleDB is sufficient at current scale

### 4.6 REMOVE: FIX Protocol Connector (Phase 5)

**Architecture reference:** `architecture_system.md` — FIX 4.4/5.0 connector for institutional access

**Why remove from current roadmap:**
- FIX protocol is for institutional DMA with co-location — this is years away
- By the time AlphaStack needs FIX, the landscape may have changed (AI-native market microstructure)
- Focus execution effort on MT5 (forex) and CCXT (crypto) which cover the target market

**New approach:** Keep as documented future option but remove from implementation roadmap. Revisit when capital exceeds $500K.

**Effort saved:** 3 weeks  
**Risk:** None — not needed at current scale

---

## 5. Updated Tech Stack Recommendations

### 5.1 Model Choices (Updated)

| Role | Previous | Updated | Rationale |
|------|----------|---------|-----------|
| **Primary reasoning** | DeepSeek-R1 / QwQ | **DeepSeek V4-Flash** | $0.0028/MTok cached, 1M context, 2500 concurrency |
| **Complex analysis** | DeepSeek-R1 | **Claude Sonnet 5** | Best agentic reliability, $2/MTok intro |
| **Critical decisions** | — | **GPT-5.6 Terra** | Outperforms Claude Fable 5 at ~1/16 cost |
| **Fast classification** | Qwen-2.5-7B | **DeepSeek V4-Flash** (same model, cache-optimized) | Unified model simplifies routing |
| **Sentiment** | FinBERT | **FinBERT** (unchanged) | Still best for domain-specific sentiment |
| **African languages** | — | **Qwen3** (self-hosted) | 119 languages, Apache 2.0 |
| **On-device** | — | **Bonsai 27B** (1-bit) | 3.9GB, 90% quality, tool-calling |
| **Vision/chart analysis** | CNN (custom) | **Kimi K3** (native vision) | 1M context, open weights Jul 27 |
| **Embeddings** | BGE-small-en-v1.5 | **NVIDIA Nemotron 3 Embed** | #1 on RTEB benchmark |

### 5.2 Frameworks (Updated)

| Component | Previous | Updated | Rationale |
|-----------|----------|---------|-----------|
| **Orchestration** | LangGraph (custom) | **LangGraph 1.0** (latest) | Per-node timeouts, DeltaChannel, v2 streaming |
| **Tool protocol** | Custom Redis | **MCP** (Model Context Protocol) | 97M+ downloads, universal adoption |
| **Agent protocol** | Custom Redis Streams | **MCP + A2A** (evaluate) | A2A v1.0 stable, 150+ orgs |
| **Agent governance** | Custom risk engine | **Microsoft Agent Governance Toolkit** | OWASP-aligned, sub-ms enforcement |
| **RL training** | Stable-Baselines3 | **Stable-Baselines3** (unchanged) | Still industry standard |
| **ML inference** | ONNX Runtime | **ONNX Runtime** (unchanged) | 2-5x faster CPU inference |
| **Quantization** | — | **MXFP4** (for self-hosted models) | 4x inference cost reduction, QAT-trained |

### 5.3 Protocols (Updated)

| Protocol | Purpose | Status | AlphaStack Action |
|----------|---------|--------|-------------------|
| **MCP** | Agent ↔ Tool | 97M+ downloads, universal | Adopt immediately for all tool integrations |
| **A2A** | Agent ↔ Agent | v1.0 stable, 150+ orgs | Evaluate for Phase 2 agent communication |
| **ACP** (IBM) | Agent ↔ Agent | Dead (merged into A2A) | Ignore |
| **AG-UI** | Agent ↔ Frontend | Emerging | Monitor for dashboard integration |

### 5.4 Infrastructure (Updated)

| Component | Previous | Updated | Rationale |
|-----------|----------|---------|-----------|
| **Primary DB** | TimescaleDB + ClickHouse | **TimescaleDB only** (at launch) | Simplify; add ClickHouse at >$50K |
| **Cache** | Redis | **Redis** (unchanged) | Still best for hot data + streams |
| **Event bus** | Redis Streams (18 channels) | **Redis Streams (4 channels) + A2A** | Simplified, standards-based |
| **Model hosting** | Cloud API only | **Cloud API + self-hosted option** | Qwen3 self-hosted for zero-cost inference |
| **Inference quantization** | — | **MXFP4** | Native on Blackwell/MI400, 4x cost reduction |
| **Post-quantum crypto** | Planned | **Accelerate timeline** | AI-accelerated quantum error correction (347x) |

---

## 6. Priority Implementation Roadmap

### Phase 1: Foundation (Weeks 1–4) — CRITICAL PATH

**Goal:** Working pipeline with optimized model costs and basic governance.

| Task | Effort | Priority | Dependencies |
|------|--------|----------|-------------|
| Switch primary LLM to DeepSeek V4-Flash with aggressive context caching | 3 days | P0 | None |
| Upgrade LangGraph to latest (per-node timeouts, DeltaChannel) | 2 days | P0 | None |
| Implement MCP for all tool integrations (market data, execution APIs) | 1 week | P0 | LangGraph upgrade |
| Build trace mining pipeline (capture + store + basic analysis) | 2 weeks | P0 | TimescaleDB |
| Implement context budget manager (per-loop-type) | 1 week | P0 | None |
| Add Agent Governance Toolkit (policy engine between agents and execution) | 1 week | P0 | None |
| Implement memory integrity protection (append-only + hashing for Reflection agent) | 3 days | P1 | None |
| Evaluate Claude Sonnet 5 for complex reasoning tasks | 2 days | P1 | DeepSeek V4-Flash baseline |
| Set up Qwen3 self-hosted instance for African language support | 3 days | P1 | GPU server |
| Commission African accent voice evaluation (Hume AI VoiceEQ findings) | 1 day | P1 | None |

**Phase 1 Total Effort:** ~3.5 weeks  
**Phase 1 Outcome:** 95% cost reduction on LLM inference, formal governance, trace capture for improvement

### Phase 2: Intelligence (Weeks 5–10) — HIGH VALUE

**Goal:** System learns from experience, proactive market intelligence, on-device capability.

| Task | Effort | Priority | Dependencies |
|------|--------|----------|-------------|
| Build Proactive Market Brain (auto-ingest financial feeds → structured knowledge) | 3 weeks | P1 | MCP, vector DB |
| Implement trace mining feedback loop (insights → signal weight updates) | 2 weeks | P1 | Trace pipeline from Phase 1 |
| Evaluate A2A protocol for inter-agent communication | 2 weeks | P2 | MCP adoption |
| Prototype on-device inference with Bonsai 27B | 3 weeks | P2 | None |
| Build model routing layer (cost-aware, cache-aware) | 2 weeks | P1 | DeepSeek + Sonnet baseline data |
| Formalize loop selection meta-decision (given conditions, which loop?) | 1 week | P2 | Trace data |
| Implement intent logging for regulatory compliance | 1 week | P1 | Agent Governance Toolkit |
| Add gold micro-trading as product vertical | 1 week | P2 | CCXT connector |

**Phase 2 Total Effort:** ~6 weeks  
**Phase 2 Outcome:** System improves itself from trade data, proactive intelligence, mobile-ready

### Phase 3: Scale (Weeks 11–18) — COMPETITIVE MOAT

**Goal:** Multi-teacher distillation, self-hosted models, institutional-grade governance.

| Task | Effort | Priority | Dependencies |
|------|--------|----------|-------------|
| Multi-teacher distillation pipeline (domain experts → unified model) | 6 weeks | P2 | RL training infra, trace data |
| Self-hosted Qwen3.5 deployment (when available, native multimodal) | 2 weeks | P2 | Qwen3 baseline |
| Evaluate Kimi K3 open weights (Jul 27) for self-hosted inference | 2 weeks | P2 | GPU infrastructure |
| Implement OWASP governance maturity Level 2 (policy-defined, HITL) | 2 weeks | P1 | Agent Governance Toolkit |
| A2A protocol integration for dynamic agent discovery | 3 weeks | P2 | A2A evaluation from Phase 2 |
| Post-quantum cryptography acceleration (crypto-agile architecture) | 2 weeks | P3 | None |
| Apply for World Bank AI Acceleration Program | 1 day | P2 | None |
| EU AI Act compliance documentation | 1 week | P1 | If operating in EU markets |

**Phase 3 Total Effort:** ~8 weeks  
**Phase 3 Outcome:** Self-hosted models, institutional governance, regulatory readiness

---

## 7. Risk Register Updates

### 7.1 NEW RISKS

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| **R-NEW-1** | **AGI timeline compression** — AGI by 2028-2030 (Hassabis), commoditizes AI trading edges | Medium | Critical | Alpha edge must come from proprietary data + execution speed, not model access. Build trace mining pipeline for continuous improvement. |
| **R-NEW-2** | **Open-source commoditization** — Kimi K3, Qwen3 give competitors near-frontier capabilities at zero cost | High | High | Differentiation through proprietary trading data, unique training approaches, and harness quality — not model access. |
| **R-NEW-3** | **Memory poisoning** — Adversarial market data corrupts Reflection agent memory, causing persistent incorrect behavior | Medium | Critical | Implement memory integrity hashing, append-only memory, read-only validated learnings, memory decay. |
| **R-NEW-4** | **Agent security incident** — 54% of enterprises have had confirmed incidents (VentureBeat research) | Medium | High | Adopt OWASP agentic AI security framework. Implement Agent Governance Toolkit. Scoped agent identities. |
| **R-NEW-5** | **Model routing cost surprise** — Actual costs differ from token pricing due to cache dynamics (IBM Research) | High | Medium | Measure actual cost per agent including cache hit rates. Don't route based on sticker price alone. |
| **R-NEW-6** | **EU AI Act compliance** — High-risk obligations take effect August 2026 | Medium | High | Prepare compliance documentation. Multi-agent architecture provides audit trail advantage. |
| **R-NEW-7** | **Quantum threat acceleration** — AI-accelerated error correction (347x reduction) compresses Q-day timeline | Low | Critical | Accelerate post-quantum cryptography migration. Adopt crypto-agile architecture (pQCee pattern). |
| **R-NEW-8** | **Voice AI accuracy for African accents** — Real World VoiceEQ shows models struggle with non-Western accents | High | Medium | Commission market-specific evaluation before launch. No single model works best everywhere. |
| **R-NEW-9** | **Regulatory crackdown on AI trading** — Hassabis proposes global AI watchdog, NY data center moratorium | Medium | High | Build transparent, auditable multi-agent architecture. Early engagement with regulators. Position as "augmented intelligence" (AI proposes, humans dispose). |
| **R-NEW-10** | **DeepSeek V4-Flash quality insufficient** — Cheapest model may not handle complex financial reasoning | Medium | Medium | A/B test against Sonnet 5 on real trading decisions. Use tiered routing: simple→Flash, complex→Sonnet. |

### 7.2 UPDATED RISKS

| # | Risk | Previous Assessment | Updated Assessment | Change Reason |
|---|------|-------------------|-------------------|---------------|
| **R-1** | Implementation gap (8.4/10 design, 3.0/10 implementation) | Critical | Critical (unchanged) | Gap remains #1 risk. Cost reduction makes implementation cheaper. |
| **R-2** | LLM API dependency | High | **Medium (reduced)** | Self-hosted Qwen3 + DeepSeek V4-Flash caching reduces dependency. |
| **R-3** | LLM cost overrun | High | **Low (reduced)** | 95% cost reduction via DeepSeek V4-Flash caching. |
| **R-4** | Model hallucination in trading decisions | High | High (unchanged) | Infrastructure-level risk enforcement still critical. |
| **R-5** | Single broker dependency (FXPesa) | Medium | Medium (unchanged) | CCXT provides crypto fallback. |

### 7.3 RISK MATRIX

```
                    IMPACT
                    Low      Medium     High      Critical
LIKELIHOOD  ┌──────────┬──────────┬──────────┬──────────┐
High        │          │ R-NEW-5  │ R-NEW-2  │          │
            │          │ R-NEW-8  │          │          │
            ├──────────┼──────────┼──────────┼──────────┤
Medium      │          │          │ R-NEW-4  │ R-NEW-1  │
            │          │          │ R-NEW-6  │ R-NEW-3  │
            │          │          │ R-NEW-9  │ R-NEW-7  │
            ├──────────┼──────────┼──────────┼──────────┤
Low         │          │ R-NEW-10 │          │          │
            ├──────────┼──────────┼──────────┼──────────┤
Very Low    │          │          │          │          │
            └──────────┴──────────┴──────────┴──────────┘
```

---

## Appendix A: Research Source Index

| # | File | Key Findings Used |
|---|------|-------------------|
| 1 | `ai_week_agi_race.md` | AGI timeline compression, Kimi K3, inference cost shift, global AI watchdog |
| 2 | `ai_week_emerging_systems.md` | Kimi K3 architecture (KDA, AttnRes, MoE), Inkling, VKUE on CPU, distillation trends, IBM model routing, Intuit agent rebuild, VulnHunter, agent security gap |
| 3 | `ai_week_general_landscape.md` | Together AI $800M, fintech funding +23%, World Bank "Small AI", Bybit/NOBI, Equiti India hub, SBI YONO Ji |
| 4 | `ai_week_loops_self_improving.md` | NemoClaw harness tuning, trace mining as data problem, RLMs, context engineering, CoALA memory, OpenWiki Brains, agent identity gaps |
| 5 | `ai_week_multi_agent.md` | LangGraph 1.0 updates, MAF consolidation, A2A v1.0, MCP adoption, OWASP agentic security, Microsoft Agent Governance Toolkit |
| 6 | `ai_week_openclaw.md` | OpenClaw 2026.7.1 capabilities, community scale, integration potential |
| 7 | `ai_week_quantum.md` | NVIDIA AI decoder (347x error reduction), non-Abelian anyons, pQCee funding, quantum timeline acceleration |
| 8 | `ai_week_voice_ondevice.md` | Bonsai 27B on phone, Apple AFM 3 IFP, Gradium $100M, Whispp voice reconstruction, on-device inference viability |
| 9 | `ai_week_voice_reasoning_llm.md` | GPT-5.6 family, Claude Sonnet 5, DeepSeek V4 pricing, Qwen3, Gemini Interactions API, cost comparison matrix |

## Appendix B: Architecture Doc References

| Doc | Sections Referenced | Key Decisions Updated |
|-----|-------------------|----------------------|
| `architecture_system.md` | Tech stack, event bus, deployment, data pipeline | Event bus simplification, ClickHouse removal, protocol updates |
| `architecture_multi_agent.md` | Agent roles, communication, memory, loops | Memory architecture, agent identity, governance, trace mining |
| `architecture_ai_models.md` | Model selection, serving, training | LLM model strategy, deprioritize CNN/Transformer/Custom, model routing |
| `architecture_future_tech.md` | Quantum readiness, CBDC, tokenized RWA | Quantum timeline acceleration, crypto-agile architecture |

---

*Document generated: 2026-07-19*  
*Next review: 2026-07-26 (weekly architecture sync)*  
*Owner: Architecture Agent → Main Agent*
