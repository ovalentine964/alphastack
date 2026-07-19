# AlphaStack Implementation Tech Stack
## Week of July 19, 2026 — AI Research Synthesis

**Version:** 1.0  
**Date:** 2026-07-19  
**Author:** Tech Stack Agent  
**Status:** RESEARCH COMPLETE — PENDING REVIEW  
**Sources:** 9 weekly research files, 2 architecture documents

---

## Executive Summary

This document synthesizes all AI research from the week ending July 19, 2026, against AlphaStack's existing architecture to produce concrete technology recommendations. The research reveals a dramatically shifted landscape: **DeepSeek V4-Flash at $0.0028/MTok** (cache hit) makes multi-agent inference nearly free, **LangGraph 1.0** remains the production leader with new DeltaChannel and per-node timeouts, **Qwen3's 119-language support** solves African market voice needs, and **Bonsai 27B's 3.9GB on-device model** enables offline trading on mid-range African smartphones.

**Key recommendation:** AlphaStack's current stack (Python + Rust, PyTorch, LangGraph, Redis Streams, PostgreSQL/TimescaleDB, Tauri) is **validated and should remain**. Targeted upgrades — not rewrites — are the path forward.

---

## Section 1: LLM Model Matrix

### 1.1 Agent Role → Model Assignment

| Agent Role | Primary Model | Fallback Model | Cost/MTok (Input) | Latency | Why |
|---|---|---|---|---|---|
| **News Agent** (sentiment + classification) | DeepSeek V4-Flash | Claude Sonnet 5 | $0.0028 (cache) / $0.14 (miss) | 0.5–2s | 119 languages, cheapest with cache, fast classification |
| **Strategy Agent** (plan-and-execute) | Claude Sonnet 5 | GPT-5.6 Terra | $2–3 (intro) / $3 (std) | 1–3s | Best agentic reliability ("stays on plan, follows conventions") |
| **Risk Agent** (real-time guardrails) | DeepSeek V4-Flash | Qwen3 (self-hosted) | $0.0028 (cache) | 0.3–1s | Speed-critical, cache hits on repeated risk checks |
| **Execution Agent** (order routing) | DeepSeek V4-Flash | Rules-based fallback | $0.0028 (cache) | <500ms | Latency-critical, most decisions are deterministic |
| **Journal Agent** (trade logging) | DeepSeek V4-Flash | Qwen3-7B (local) | $0.0028 (cache) | 1–3s | Non-time-critical, cost-sensitive |
| **Auditor Agent** (reflection loop) | Claude Sonnet 5 | GPT-5.6 Terra | $2–3 | 5–15s | Complex reasoning over trade history |
| **Fundamental Analyst** (macro reasoning) | Claude Sonnet 5 | DeepSeek V4-Pro | $2–3 / $0.435 | 3–10s | High-stakes, needs deep reasoning |
| **On-device Agent** (offline mobile) | Bonsai 27B (1-bit) | Qwen3-7B (quantized) | $0 (local) | 1–3s | 3.9GB, 90% quality retention, Apache 2.0 |

### 1.2 Cost Comparison (July 2026)

| Provider / Model | Input (Std) | Input (Cache Hit) | Output | Context | Concurrency |
|---|---|---|---|---|---|
| **DeepSeek V4-Flash** | $0.14 | **$0.0028** | $0.28 | 1M | 2,500 |
| **DeepSeek V4-Pro** | $0.435 | $0.003625 | $0.87 | 1M | 500 |
| **Claude Sonnet 5** (intro, through Aug 31) | $2.00 | — | $10.00 | — | — |
| **Claude Sonnet 5** (standard) | $3.00 | — | $15.00 | — | — |
| **Claude Opus 4.8** | $5.00 | — | $25.00 | — | — |
| **Kimi K3** (open weights Jul 27) | — | $0.30 | — | 1M | — |
| **GPT-5.6 Terra** | ~$0.50* | — | ~$1.50* | — | — |
| **GPT-5.6 Luna** | ~$0.25* | — | ~$0.75* | — | — |
| **Gemini 3.5 Flash** | ~$0.075* | — | ~$0.30* | — | — |
| **Qwen3 (self-hosted)** | $0 | $0 | $0 | — | GPU-bound |

*\* Estimated from benchmark comparisons*

### 1.3 Model Routing Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                 MODEL ROUTING LAYER                          │
│                                                              │
│  Decision Factors:                                           │
│  1. Task complexity (simple classification vs deep reasoning)│
│  2. Latency requirement (<500ms vs <10s acceptable)         │
│  3. Cache hit probability (system prompts, repeated context) │
│  4. Stakes (execution vs journaling)                         │
│  5. Language requirements (African languages → Qwen3)        │
│                                                              │
│  Simple + Fast + Cache-heavy → DeepSeek V4-Flash             │
│  Complex + High-stakes       → Claude Sonnet 5              │
│  African languages + Voice   → Qwen3 (self-hosted)          │
│  On-device / Offline         → Bonsai 27B (1-bit)           │
│  Fallback chain              → DS V4-Flash → Sonnet 5       │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 Key Research Findings

- **DeepSeek V4-Flash at $0.0028/MTok** (cache hit) with 2,500 concurrency handles AlphaStack's 16+ agents for ~$2/month (IBM Research confirms cache dynamics dominate effective cost — don't route on sticker price alone)
- **Claude Sonnet 5** intro pricing ($2/MTok input) is the best cost-performance model for agentic work; "agents stay on plan, follow conventions, and ship clean multi-step changes" (LangChain)
- **GPT-5.6 Ultra mode** natively coordinates 4-16 parallel agents; programmatic tool calling reduces token waste
- **Qwen3** supports 119 languages (Swahili, Hausa, Yoruba, Amharic) with Apache 2.0 license; Qwen3.5 adds native multimodal
- **Kimi K3** (2.8T MoE, 50B active) open weights released July 27 — evaluate for 1M context window market analysis
- **Bonsai 27B** (1-bit, 3.9GB) runs on iPhone 17 Pro / mid-range Android; 90% quality retention; tool-calling + 262K context

---

## Section 2: Framework Evaluation

### 2.1 Decision Matrix: Multi-Agent Orchestration

| Criterion | LangGraph 1.0 | Microsoft Agent Framework | CrewAI 1.14 | Claude Agent SDK | Custom (current) |
|---|---|---|---|---|---|
| **Production readiness** | ✅ GA, Klarna, Uber | ✅ GA (Apr 2026) | ⚠️ Maturing | ✅ Anthropic internal | ⚠️ Custom maintenance |
| **Stateful workflows** | ✅ Built-in checkpoints | ✅ | ❌ Limited | ✅ Scoped memory | ⚠️ Manual |
| **Per-node timeouts** | ✅ Q2 2026 addition | ❌ | ❌ | ❌ | ❌ |
| **Delta streaming** | ✅ DeltaChannel (new) | ❌ | ❌ | ❌ | ❌ |
| **MCP support** | ✅ Native | ✅ Native | ✅ Native | ✅ Native | ❌ |
| **A2A protocol** | ⚠️ Via adapters | ✅ Native | ❌ | ❌ | ❌ |
| **HITL support** | ✅ Built-in | ✅ | ⚠️ Chat API | ✅ Biometric approval | ⚠️ Manual |
| **Python ecosystem** | ✅ Native | ✅ | ✅ | ✅ | ✅ |
| **LangChain integration** | ✅ Core product | ❌ | ❌ | ❌ | ❌ |
| **Community/momentum** | ✅ #1 production ranking | ⚠️ New | ⚠️ Prototyping focus | ⚠️ Anthropic-locked | ❌ |
| **Cost (license)** | Free (MIT) | Free (MIT) | Free (MIT) | Free (MIT) | Free |

### 2.2 Recommendation: **Stay with LangGraph 1.0**

**Decision:** LangGraph 1.0 remains the optimal choice. Upgrade from current version to latest.

**Rationale:**
1. **#1 production ranking** across 18+ deployments (Alice Labs, Jul 2026)
2. **Per-node timeouts** — critical for sequential pipeline (News → Strategy → Risk → Execution → Reflection); prevents runaway agents
3. **DeltaChannel** — transmits only changed state fields between nodes; reduces Redis Streams message size by 60-80%
4. **Head-to-head benchmarks:** LangGraph produced fewer tokens, lower latency, and lower cost per task than both CrewAI and AutoGen for the same pipeline
5. **AutoGen effectively dead** — Microsoft merged it into MAF; 56K-star repo abandoned for new features
6. **Native MCP support** — standardized tool integration for trading APIs

**Migration path:** Minimal. AlphaStack already uses LangGraph. Upgrade to latest version, enable per-node timeouts, adopt DeltaChannel for state streaming.

### 2.3 Protocol Strategy

| Protocol | Purpose | Status | AlphaStack Action |
|---|---|---|---|
| **MCP** (Model Context Protocol) | Agent ↔ Tool | 97M+ monthly SDK downloads, universal | **Adopt immediately** for all tool integrations |
| **A2A** (Agent-to-Agent) | Agent ↔ Agent | 150+ orgs, v1.0 stable, Linux Foundation | **Evaluate** for augmenting/replacing Redis Streams |
| **AG-UI** | Agent ↔ Frontend | Emerging | **Monitor** for future dashboard integration |

**MCP adoption:** All AlphaStack agents should use MCP for tool connections (market data feeds, execution APIs, news sources). This is complementary to existing architecture.

**A2A evaluation:** A2A could replace or augment Redis Streams for inter-agent communication. Each agent exposes an Agent Card at `/.well-known/agent-card.json`, enabling dynamic routing instead of hardcoded pipeline. Benefits: add/remove agents without code changes, parallel agent execution, cross-system federation. **Timeline: Evaluate in Phase 3 (Q4 2026).**

---

## Section 3: Data Stack

### 3.1 Current Stack Validation

| Component | Current | Research Verdict | Action |
|---|---|---|---|
| **Redis Streams** | Event bus + cache | ✅ Validated. Simple, fast, sufficient for scale, built-in cache. | **Keep.** Add DeltaChannel for state diffs. |
| **PostgreSQL** | OLTP (orders, config) | ✅ Validated. Industry standard. | **Keep.** |
| **TimescaleDB** | Time-series (OHLCV) | ✅ Validated. PostgreSQL-compatible, auto-partitioning. | **Keep.** |

### 3.2 Redis vs Kafka Evaluation

| Criterion | Redis Streams (current) | Apache Kafka | NATS JetStream |
|---|---|---|---|
| **Setup complexity** | ✅ Minimal (single binary) | ❌ ZooKeeper/KRaft, multiple brokers | ✅ Single binary |
| **Latency** | ✅ <1ms | ⚠️ 2-5ms | ✅ <1ms |
| **Throughput** | ✅ 100K+ msg/sec | ✅ 1M+ msg/sec | ✅ 500K+ msg/sec |
| **Persistence** | ✅ AOF + RDB | ✅ Disk-native | ✅ JetStream |
| **Consumer groups** | ✅ Built-in | ✅ Native | ✅ Built-in |
| **Caching** | ✅ Native (same process) | ❌ Separate (Redis needed) | ❌ Separate |
| **Operational cost** | ✅ $0 (already running) | ❌ 3+ brokers minimum | ✅ $0 |
| **When to switch** | — | >100K msg/sec sustained | Latency-critical + persistence |

**Decision:** **Keep Redis Streams.** It handles both event bus and caching in a single process. Kafka adds operational complexity with no benefit at AlphaStack's current scale. Revisit only if sustained throughput exceeds 100K msg/sec (institutional scale).

### 3.3 PostgreSQL vs ClickHouse Evaluation

| Criterion | PostgreSQL + TimescaleDB | ClickHouse | QuestDB |
|---|---|---|---|
| **Time-series queries** | ✅ TimescaleDB hypertables | ✅ Columnar, fastest reads | ✅ Purpose-built |
| **OLTP (orders, config)** | ✅ Native | ❌ Not designed for OLTP | ⚠️ Limited |
| **JOIN support** | ✅ Full SQL | ⚠️ Limited | ⚠️ Limited |
| **Operational complexity** | ✅ Single engine | ⚠️ Separate from OLTP | ⚠️ Separate |
| **Analytics speed** | ✅ Good (TimescaleDB) | ✅✅ Blazing fast | ✅ Good |
| **Compression** | ✅ TimescaleDB native | ✅✅ Best-in-class | ✅ Good |

**Decision:** **Keep PostgreSQL + TimescaleDB as primary. Add ClickHouse for analytics/backtesting at Phase 3 ($10K+).** ClickHouse's columnar architecture delivers 10-100× faster analytical queries for backtesting and audit, but it's not suitable as a primary OLTP store. Use the hybrid approach from the architecture doc.

### 3.4 Governance Layer (New Requirement)

Research from VentureBeat Pulse (Jul 2026) and OWASP identifies critical gaps:

- **54% of enterprises** have had a confirmed agent security incident
- **Only 32%** give every agent its own scoped identity
- **Governed semantic layer** emerging as fix for AI context gaps

**Action:** Implement a governed semantic layer for financial knowledge context. Don't rely solely on vector DB retrieval. Use structured financial knowledge (correlation maps, market structure rules, risk parameters) alongside RAG.

---

## Section 4: Voice Stack

### 4.1 TTS/STT for African Languages

| Solution | Languages | Quality | Latency | Cost | On-device | African Accent Quality |
|---|---|---|---|---|---|---|
| **Qwen3** (STT/TTS) | 119 languages (incl. Swahili, Hausa, Yoruba) | ✅ Good | 0.5–2s | $0 (self-hosted) | ✅ (quantized) | ⚠️ Needs testing |
| **Whisper v4** (STT) | 100+ languages | ✅ Good | 1–3s | $0.006/min (API) | ✅ (Whisper.cpp) | ⚠️ Degrades with non-Western accents |
| **Gemini Omni** (coming soon) | Multimodal native | ✅ Unknown | Unknown | Unknown | ❌ Cloud | ❓ Not yet available |
| **Gradium** (NVIDIA-backed) | TBD (expanding) | ✅ Unknown | Unknown | Unknown | ❌ Cloud | ❓ European focus, expanding |
| **Whispp** (voice reconstruction) | Any language | ✅ On-device | Real-time | TBD | ✅ | ✅ Designed for noisy environments |
| **Speechify** | Multiple | ✅ Production-ready | Real-time | Freemium | ✅ | ⚠️ Limited African coverage |
| **Hume AI (Kairos)** | Evaluation platform | N/A (benchmark) | N/A | N/A | N/A | ✅ Tests African accents specifically |

### 4.2 Real World VoiceEQ Benchmark Insights (Jul 2026)

Critical findings from Hume AI's 40+ model evaluation:

1. **No single voice model works best everywhere** — specialization matters
2. **ASR accuracy degrades significantly** with non-Western accents
3. **Emotional/expressive speech** poorly handled — trading alerts need clarity
4. **Background noise** is a major challenge — African market environments are noisy
5. **Existing benchmarks (WER, latency) are saturating** — need broader evaluation

### 4.3 Recommendation: Hybrid Voice Stack

```
┌─────────────────────────────────────────────────────────────┐
│                 VOICE STACK ARCHITECTURE                      │
│                                                              │
│  STT (Speech-to-Text):                                       │
│  ├── Primary: Qwen3 (self-hosted, 119 languages)             │
│  ├── Fallback: Whisper v4 (quantized, on-device)             │
│  └── Evaluation: Hume Kairos for African accent benchmarking │
│                                                              │
│  TTS (Text-to-Speech):                                       │
│  ├── Primary: Qwen3 native TTS (multimodal in 3.5)           │
│  ├── On-device: Bonsai 27B + custom TTS head                 │
│  └── Noisy environments: Whispp voice reconstruction         │
│                                                              │
│  Voice-first interface:                                      │
│  ├── Entry: "Buy EUR/USD, 2% risk, bullish" → parse → trade  │
│  ├── Readout: Portfolio summary, P&L, alerts                  │
│  ├── Confirmations: Trade execution voice confirm             │
│  └── Language: Auto-detect (Swahili, English, Hausa, etc.)    │
│                                                              │
│  Priority: Commission Hume Kairos evaluation for              │
│  Nigerian English, South African English, Swahili-accented    │
│  English BEFORE committing to any model.                     │
└─────────────────────────────────────────────────────────────┘
```

### 4.4 Cost: Voice Stack

| Component | Monthly Cost | Notes |
|---|---|---|
| Qwen3 self-hosted (STT/TTS) | $50–100 | GPU rental for inference |
| Whisper v4 (fallback) | $0 | On-device via whisper.cpp |
| Hume Kairos evaluation | $500–1000 (one-time) | Accent-specific benchmarking |
| Whispp integration | TBD | OEM partnerships pending |
| **Total ongoing** | **$50–100/mo** | At scale |

---

## Section 5: ML/AI Stack

### 5.1 Training Pipeline

| Component | Current | Recommended | Version | Notes |
|---|---|---|---|---|
| **Training framework** | PyTorch | PyTorch (keep) | 2.4+ | ONNX export for inference |
| **Gradient boosting** | scikit-learn | XGBoost 2.1 + LightGBM 4.x | Latest | 2-5× faster than sklearn for tabular |
| **RL framework** | Ray RLlib | Ray RLlib (keep) | 2.10+ | PPO for position sizing, DQN for TP |
| **Distillation** | None | Custom multi-teacher pipeline | N/A | Train domain-specific RL experts, distill to unified model |
| **Feature engineering** | Custom | Polars 1.x + Custom Rust | Latest | 10-100× faster than Pandas |

### 5.2 Inference Optimization

| Technique | Speedup | Quality Impact | Effort | Priority |
|---|---|---|---|---|
| **ONNX Runtime** (CPU) | 2-5× | None | Low | ✅ Already planned |
| **MXFP4 quantization** (GPU) | ~4× | <1% degradation (QAT) | Medium | 🟡 Phase 3 |
| **Speculative decoding** | 2-3× | None | Medium | 🟡 Phase 3 |
| **Context caching** (DeepSeek) | 50-100× cost reduction | None | Low | ✅ Immediate |
| **KV-cache compression** (Gated MLA) | 2-4× memory reduction | <2% degradation | High | 🔵 Research |
| **MoE architecture** (sparse) | 5-10× compute reduction | <5% degradation | High | 🔵 Research |

### 5.3 On-Device vs Cloud Split

```
┌─────────────────────────────────────────────────────────────┐
│            INFERENCE LOCATION DECISION TREE                  │
│                                                              │
│  Is latency critical (<100ms)?                               │
│  ├── YES → On-device (Bonsai 27B 1-bit or quantized model)  │
│  │         ├── Signal generation                             │
│  │         ├── Risk checks                                   │
│  │         └── Basic classification                          │
│  └── NO → Cloud API                                          │
│            ├── DeepSeek V4-Flash (cheap, fast)               │
│            ├── Claude Sonnet 5 (complex reasoning)            │
│            └── GPT-5.6 Terra (balanced)                      │
│                                                              │
│  Is connectivity guaranteed?                                 │
│  ├── YES → Cloud API (cheaper, more capable)                 │
│  └── NO → On-device (Bonsai 27B)                             │
│            ├── Offline trading signals                        │
│            ├── Voice interface (local STT/TTS)                │
│            └── Portfolio readout                              │
│                                                              │
│  Is the task African-language specific?                      │
│  ├── YES → Qwen3 (self-hosted, 119 languages)               │
│  └── NO → Best model for task (see Section 1)                │
└─────────────────────────────────────────────────────────────┘
```

### 5.4 Distillation Pipeline (New)

Based on HuggingFace research (Jul 2026), frontier labs converged on **multi-teacher on-policy distillation**:

```
Domain-Specific RL Experts (same-size, not larger):
├── Equities Expert     (SFT → GRPO on equity data)
├── Forex Expert        (SFT → GRPO on forex data)
├── Crypto Expert       (SFT → GRPO on crypto data)
├── Macro Expert        (SFT → GRPO on macro data)
└── Sentiment Expert    (SFT → GRPO on sentiment data)
           │
           ▼
    On-Policy Distillation (reverse KL loss)
           │
           ▼
    Unified AlphaStack Model
    (retains 95%+ of specialist quality)
```

**Action:** Implement multi-teacher distillation using Ray RLlib in Phase 4. Train separate RL experts for each financial domain, then distill into a unified model. This solves catastrophic forgetting in multi-task financial RL.

### 5.5 Model Performance Targets

| Model | Metric | Target | Minimum |
|---|---|---|---|
| **FinBERT** | Accuracy (forex test set) | > 85% | > 80% |
| **XGBoost (confluence)** | AUC-ROC | > 0.78 | > 0.72 |
| **LSTM (price)** | Direction accuracy | > 58% | > 55% |
| **HMM (regime)** | State accuracy | > 75% | > 70% |
| **PPO (sizing)** | Sharpe ratio vs rules | +15% | +5% |
| **DQN (TP)** | R-multiple improvement | +0.3R/trade | +0.1R |
| **LLM (fundamental)** | Human agreement | > 80% | > 70% |

---

## Section 6: Frontend Stack

### 6.1 Tauri vs Alternatives

| Criterion | Tauri 2.x (current) | Electron | PWA | Flutter Desktop |
|---|---|---|---|---|
| **Bundle size** | ✅ ~5MB | ❌ ~200MB | ✅ 0 (browser) | ⚠️ ~30MB |
| **Memory usage** | ✅ ~50MB | ❌ ~300MB | ✅ Browser-managed | ✅ ~80MB |
| **Rust backend** | ✅ Native | ❌ Node.js | ❌ N/A | ❌ Dart |
| **Security** | ✅ Rust sandbox | ⚠️ Node.js surface | ⚠️ Browser sandbox | ⚠️ Dart VM |
| **Cross-platform** | ✅ Win/Mac/Linux | ✅ Win/Mac/Linux | ✅ Any browser | ✅ Win/Mac/Linux |
| **Native APIs** | ✅ Full access | ✅ Full access | ❌ Limited | ✅ Full access |
| **Update mechanism** | ✅ Built-in | ✅ electron-updater | ✅ Auto (PWA) | ⚠️ Manual |
| **Trading charts** | ✅ Lightweight Charts | ✅ Lightweight Charts | ✅ Lightweight Charts | ⚠️ fl_chart |

**Decision:** **Keep Tauri 2.x.** The 40× smaller bundle, Rust security, and native performance are critical differentiators for a trading application. No alternative offers a compelling enough advantage to justify migration.

### 6.2 Mobile Strategy

| Approach | Current | Recommended | Notes |
|---|---|---|---|
| **Framework** | React Native | **Flutter 3.x** | Architecture doc already specifies Flutter; single codebase for iOS/Android |
| **Voice interface** | None | **Qwen3 + Whisper** | Voice-first for East Africa market |
| **On-device inference** | None | **Bonsai 27B (1-bit)** | 3.9GB, fits mid-range Android (6-8GB RAM) |
| **Offline capability** | None | **Full offline mode** | On-device model + local cache for network-variable environments |
| **PWA** | None | **Companion PWA** | For web access without app install |

### 6.3 Frontend Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 FRONTEND STACK                                │
│                                                              │
│  Desktop (Primary):                                          │
│  ├── Tauri 2.x shell (Rust backend)                          │
│  ├── React 19 + TypeScript frontend                          │
│  ├── Lightweight Charts (TradingView) for charting           │
│  └── WebSocket for real-time data                            │
│                                                              │
│  Web (Companion):                                            │
│  ├── Next.js 15 (React 19)                                   │
│  ├── Same charting library as desktop                        │
│  └── PWA for mobile web access                               │
│                                                              │
│  Mobile (Voice-first):                                       │
│  ├── Flutter 3.x                                             │
│  ├── Voice interface (Qwen3 STT/TTS)                         │
│  ├── On-device inference (Bonsai 27B)                         │
│  ├── Portfolio dashboard                                     │
│  └── Push notifications for trade alerts                     │
│                                                              │
│  Shared:                                                     │
│  ├── API client library (TypeScript/Dart)                    │
│  ├── WebSocket connection manager                            │
│  └── State management (Zustand / Riverpod)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Section 7: Infrastructure

### 7.1 Deployment Stack

| Component | Phase 1 ($7) | Phase 2 ($100) | Phase 3 ($10K) | Phase 4 ($100K+) |
|---|---|---|---|---|
| **Compute** | Local machine | Hetzner CX31 ($15/mo) | AWS/Hetzner K8s ($80-150/mo) | Multi-region K8s ($500-2000/mo) |
| **Orchestration** | Docker Compose | Docker Compose | Kubernetes | Multi-cluster K8s |
| **Database** | SQLite | PostgreSQL + Redis | TimescaleDB + Redis + ClickHouse | Distributed + Kafka |
| **Monitoring** | Console logs | Grafana + Prometheus | + Loki + PagerDuty | + 24/7 ops |
| **CI/CD** | Manual | GitHub Actions | GitHub Actions + ArgoCD | + Canary deployments |
| **Secrets** | .env file | Docker secrets | SOPS + age | Vault / AWS Secrets Manager |
| **CDN/DDoS** | None | Nginx | Cloudflare | Cloudflare Enterprise |

### 7.2 Monitoring Stack

| Layer | Tool | Purpose |
|---|---|---|
| **Metrics** | Prometheus | System metrics, model latency, trade counts |
| **Dashboards** | Grafana | Trading P&L, model performance, system health |
| **Logging** | Loki + Promtail | Centralized structured logging |
| **Alerting** | Grafana Alerting → Telegram/Discord | Drawdown alerts, model degradation, system failures |
| **Tracing** | OpenTelemetry | End-to-end signal → execution latency tracking |
| **Model monitoring** | Custom (ModelMonitor) | Per-model accuracy, latency P99, error rates |

### 7.3 Security Stack (Updated)

| Layer | Component | Notes |
|---|---|---|
| **Network** | TLS 1.3, VPN, DDoS protection | Architecture doc L1 |
| **Auth** | JWT + API keys + RBAC | Architecture doc L2 |
| **App** | Input validation, rate limiting, XSS prevention | Architecture doc L3 |
| **Data** | AES-256 at rest, TLS in transit, SOPS for secrets | Architecture doc L4 |
| **Agent governance** | **Microsoft Agent Governance Toolkit** (NEW) | Sub-ms policy engine; addresses all 10 OWASP agentic AI risks |
| **Memory integrity** | **Append-only + hash verification** (NEW) | Protects Reflection agent from memory poisoning |
| **Post-quantum** | **Crypto-agile design** (NEW) | PQCee's approach: swap cryptographic algorithms without redesign |

**OWASP Agentic AI Risks (must address):**
- Goal hijacking → Per-agent scoped objectives
- Tool misuse → MCP permission scoping
- Identity abuse → Scoped agent credentials (only 32% of enterprises do this — AlphaStack should be in that 32%)
- Memory poisoning → Append-only memory with integrity hashing
- Cascading failures → Circuit breakers between agents
- Rogue agents → Per-node timeouts + kill switches

### 7.4 Governance Requirements (New)

**EU AI Act high-risk obligations take effect August 2026.** AlphaStack likely qualifies as high-risk AI (automated financial trading). Required:

- Risk management systems
- Data governance documentation
- Transparency and human oversight provisions
- Conformity assessments

**Action:** Implement governance layer before August 2026. Microsoft Agent Governance Toolkit (open-source, Python/TypeScript/Rust, MIT license, sub-ms policy enforcement) is the leading solution. It addresses all 10 OWASP agentic AI risks and works with LangGraph.

---

## Section 8: Cost Model

### 8.1 Monthly Cost Estimates by Scale Tier

#### Tier 1: $7 Micro-Account (Paper/Live Trading)

| Component | Monthly Cost | Notes |
|---|---|---|
| **Compute** (local machine) | $0 | Existing hardware |
| **LLM API** (DeepSeek V4-Flash) | $2–5 | 16 agents × ~1M tokens/day, heavy caching |
| **LLM API** (Claude Sonnet 5, selective) | $5–15 | High-stakes decisions only |
| **Data feeds** | $0–10 | Free tiers (MT5 demo, CCXT) |
| **Database** | $0 | Local PostgreSQL + Redis |
| **Monitoring** | $0 | Local Grafana |
| **Voice (STT/TTS)** | $0 | Local Qwen3 (CPU inference, limited) |
| **Total** | **$7–30/mo** | |

#### Tier 2: $100 Capital (Live Trading VPS)

| Component | Monthly Cost | Notes |
|---|---|---|
| **VPS** (Hetzner CX31) | $15 | 4 CPU, 8GB RAM, Frankfurt |
| **LLM API** (DeepSeek V4-Flash) | $3–8 | With context caching |
| **LLM API** (Claude Sonnet 5) | $10–30 | Selective use |
| **Data feeds** | $0–20 | Forex: MT5 live; Crypto: CCXT free |
| **Domain + SSL** | $2 | Let's Encrypt (free) + domain |
| **Total** | **$30–75/mo** | |

#### Tier 3: $1,000 Capital (Multi-Pair)

| Component | Monthly Cost | Notes |
|---|---|---|
| **VPS** (Hetzner CX41) | $30 | 8 CPU, 16GB RAM |
| **LLM API** (DeepSeek V4-Flash) | $5–15 | Multi-pair, more agents |
| **LLM API** (Claude Sonnet 5) | $20–50 | Complex analysis |
| **Data feeds** | $20–50 | Multiple news sources |
| **GPU spot instance** (monthly retrain) | $5–10 | H100 spot for model training |
| **Total** | **$80–155/mo** | |

#### Tier 4: $10K Capital (Multi-Broker)

| Component | Monthly Cost | Notes |
|---|---|---|
| **Cloud compute** (K8s) | $50–100 | 2-3 nodes |
| **LLM API** (mixed) | $20–50 | Model routing layer |
| **ClickHouse** (analytics) | $20–40 | Managed or self-hosted |
| **Data feeds** | $50–100 | Reuters/BN alternatives |
| **Voice (self-hosted Qwen3 GPU)** | $50–100 | GPU rental for STT/TTS |
| **Monitoring** | $10–20 | Managed Grafana Cloud |
| **Total** | **$200–410/mo** | |

#### Tier 5: $100K+ Capital (Institutional)

| Component | Monthly Cost | Notes |
|---|---|---|
| **Multi-region K8s** | $200–500 | Primary + DR |
| **GPU nodes** (inference) | $200–400 | On-prem or dedicated |
| **LLM API** (mixed) | $50–150 | Heavily cached, model routing |
| **Managed databases** | $100–200 | TimescaleDB Cloud + Redis Cloud |
| **Data feeds** | $200–500 | Institutional-grade |
| **Monitoring + alerting** | $50–100 | PagerDuty + Grafana Cloud |
| **Security** | $50–100 | Vault, WAF, DDoS |
| **Voice stack** | $100–200 | Dedicated GPU for STT/TTS |
| **Total** | **$950–2,150/mo** | |

#### Tier 6: $1M+ Capital (Prime)

| Component | Monthly Cost | Notes |
|---|---|---|
| **Co-location** | $500–2000 | Equinix LD4/FR2 |
| **GPU cluster** | $1000–3000 | Dedicated inference + training |
| **LLM API** | $100–300 | Selective frontier models |
| **Managed everything** | $500–1000 | Databases, monitoring, security |
| **Institutional data** | $1000–5000 | Bloomberg/Reuters terminal |
| **Compliance** | $200–500 | Audit, reporting |
| **Total** | **$3,300–11,800/mo** | |

### 8.2 Cost Optimization Strategies

| Strategy | Savings | Effort | Priority |
|---|---|---|---|
| **DeepSeek context caching** | 50-100× on repeated prompts | Low | ✅ Immediate |
| **Model routing** (simple→cheap, complex→frontier) | 3-5× overall | Medium | ✅ Phase 2 |
| **Self-hosted Qwen3** (eliminate API costs for language tasks) | $100-300/mo at scale | Medium | 🟡 Phase 3 |
| **On-device inference** (Bonsai 27B, zero cloud cost) | $50-200/mo per user | Medium | 🟡 Phase 3 |
| **ONNX Runtime** (2-5× faster CPU inference) | Compute cost reduction | Low | ✅ Phase 1 |
| **MXFP4 quantization** (4× inference cost reduction) | GPU cost reduction | Medium | 🔵 Phase 4 |
| **Multi-teacher distillation** (unified model vs multiple APIs) | 2-3× API cost reduction | High | 🔵 Phase 5 |

### 8.3 Break-Even Analysis

| Capital Tier | Monthly Cost | Required Monthly Return | Required Annual Return |
|---|---|---|---|
| $7 | $7–30 | 100-430% | Impractical (learning phase) |
| $100 | $30–75 | 30-75% | 360-900% |
| $1,000 | $80–155 | 8-15.5% | 96-186% |
| $10,000 | $200–410 | 2-4.1% | 24-49% |
| $100,000 | $950–2,150 | 0.95-2.15% | 11-26% |
| $1,000,000 | $3,300–11,800 | 0.33-1.18% | 4-14% |

**Key insight:** The $7 tier is a learning investment, not a profit center. Break-even becomes realistic at $10K+ capital. This aligns with the architecture doc's scaling roadmap.

---

## Appendix A: Recommended Stack Changes Summary

### Keep (Validated by Research)

| Component | Version | Reason |
|---|---|---|
| Python | 3.12+ | ML ecosystem, rapid iteration |
| Rust (PyO3) | Latest | Performance-critical paths |
| PyTorch | 2.4+ | ONNX export, research-friendly |
| scikit-learn | 1.5+ | XGBoost/LightGBM for tabular |
| Ray RLlib | 2.10+ | RL training |
| LangGraph | **1.0+** (upgrade) | #1 production ranking, new features |
| Redis Streams | 7.x | Event bus + cache, simple, fast |
| PostgreSQL | 16+ | OLTP |
| TimescaleDB | 2.x | Time-series |
| Tauri | 2.x | Desktop (5MB bundle, Rust security) |
| Next.js | 15+ | Web companion |
| React | 19 | Web frontend |

### Add (New Recommendations)

| Component | Purpose | Priority |
|---|---|---|
| **DeepSeek V4-Flash** | Primary LLM for cost-sensitive agents | ✅ Immediate |
| **Claude Sonnet 5** | Primary LLM for complex reasoning | ✅ Immediate |
| **Qwen3** | African language STT/TTS, self-hosted | 🟡 Phase 2 |
| **Bonsai 27B (1-bit)** | On-device inference for mobile | 🟡 Phase 3 |
| **MCP** (Model Context Protocol) | Standardized tool integration | ✅ Phase 1 |
| **Microsoft Agent Governance Toolkit** | OWASP agentic AI security | ✅ Before Aug 2026 |
| **ClickHouse** | Analytics, backtesting | 🟡 Phase 3 |
| **Polars** | Fast dataframe operations | ✅ Phase 1 |
| **XGBoost 2.1** | Gradient boosting (replace sklearn) | ✅ Phase 1 |
| **LightGBM 4.x** | Fast gradient boosting | ✅ Phase 1 |
| **OpenTelemetry** | Distributed tracing | 🟡 Phase 2 |
| **Whispp** | Voice reconstruction (noisy environments) | 🔵 Phase 4 |

### Remove/Deprioritize

| Component | Reason |
|---|---|
| **AutoGen** | Dead. Microsoft merged into MAF; community fork AG2 is niche |
| **Kafka** | Unnecessary complexity at current scale; Redis Streams sufficient |
| **Electron** | Not in stack; Tauri is strictly better for AlphaStack's use case |

---

## Appendix B: Version Matrix

| Component | Current | Recommended | Latest Stable | Action |
|---|---|---|---|---|
| Python | 3.12 | 3.12+ | 3.13 | Keep 3.12, upgrade when 3.13 stabilizes |
| Rust | — | Latest | 1.80+ | Add PyO3 bindings for hot paths |
| PyTorch | — | 2.4+ | 2.7 | Standardize on 2.4+ |
| LangGraph | — | 1.0+ | 1.0 (GA Oct 2025) | Upgrade, enable per-node timeouts + DeltaChannel |
| Redis | 7.x | 7.4+ | 7.4 | Keep, enable Streams features |
| PostgreSQL | 16+ | 16+ | 17 | Keep 16, upgrade to 17 when stable |
| TimescaleDB | 2.x | 2.15+ | 2.15 | Keep |
| Tauri | 2.x | 2.x | 2.0 | Keep |
| Next.js | 15+ | 15+ | 15 | Keep |
| React | 19 | 19 | 19 | Keep |
| Flutter | 3.x | 3.24+ | 3.24 | Standardize |
| XGBoost | — | 2.1+ | 2.1 | Add (replace sklearn for signals) |
| LightGBM | — | 4.x | 4.5 | Add |
| Polars | — | 1.x | 1.3 | Add (replace Pandas) |
| ONNX Runtime | — | 1.18+ | 1.18 | Add for inference optimization |
| DeepSeek API | V3 | V4-Flash | V4-Flash | Switch immediately |
| Claude API | — | Sonnet 5 | Sonnet 5 | Add for complex reasoning |
| Qwen | — | 3 | 3.5 (coming) | Add for African languages |

---

## Appendix C: Research Source Index

| # | File | Key Findings for Tech Stack |
|---|---|---|
| 1 | `ai_week_general_landscape.md` | Together AI $800M (open-source infra costs dropping), World Bank "Small AI" validation |
| 2 | `ai_week_multi_agent.md` | LangGraph 1.0 #1, A2A protocol v1.0, OWASP agentic security, per-node timeouts |
| 3 | `ai_week_voice_reasoning_llm.md` | DeepSeek V4-Flash pricing, Claude Sonnet 5, Qwen3 119 languages, Kimi K3 |
| 4 | `ai_week_voice_ondevice.md` | Bonsai 27B (3.9GB on-phone), Gradium $100M, Whispp voice reconstruction |
| 5 | `ai_week_loops_self_improving.md` | Harness > model, trace mining, RLMs, context engineering |
| 6 | `ai_week_agi_race.md` | AGI timeline compressing, Kimi K3 frontier-class, inference cost shifting |
| 7 | `ai_week_emerging_systems.md` | Kimi K3 KDA/AttnRes, Inkling 1T, VKUE 34.7B on CPU, distillation trends |
| 8 | `ai_week_quantum.md` | NVIDIA AI-QEC 347× error reduction, post-quantum crypto urgency |
| 9 | `ai_week_openclaw.md` | OpenClaw as potential agent orchestration layer (evaluate) |
| 10 | `architecture_ai_models.md` | 8 model families, FinBERT, LSTM, HMM, RL agents, model serving |
| 11 | `architecture_system.md` | 6-layer architecture, Redis Streams, scaling roadmap, security layers |

---

*Document generated: July 19, 2026*  
*Next review: July 26, 2026*  
*Status: PENDING ARCHITECTURE TEAM REVIEW*
