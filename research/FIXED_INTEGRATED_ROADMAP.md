# AlphaStack — FIXED Integrated Roadmap

> **Date:** July 19, 2026
> **Author:** Architecture Fix Agent
> **Purpose:** SINGLE reconciled plan replacing all 8 unreconciled implementation plans
> **Verdict Source:** Architecture Review (8.7/10 design, 3.5/10 feasibility)
> **Realistic Timeline:** First paper trade Week 14–18 | First real trade Week 20–26

---

## Table of Contents

1. [Conflict Resolution](#1-conflict-resolution)
2. [Integrated Timeline](#2-integrated-timeline)
3. [Phase Gates](#3-phase-gates)
4. [Resource Allocation](#4-resource-allocation)
5. [Risk Mitigation](#5-risk-mitigation)
6. [Success Metrics](#6-success-metrics)
7. [First Trade Checklist](#7-first-trade-checklist)

---

## 1. Conflict Resolution

### 1.1 Security Timeline vs Engineering Timeline

| Aspect | Security Plan Says | Engineering Plan Says | Resolution |
|--------|-------------------|----------------------|------------|
| **Security effort** | 4–5 dedicated weeks (Tier 0 alone) | 3 days in Week 4 ("Fix JWT + add bcrypt") | **Security wins.** Engineering's 3-day estimate is off by 10×. |
| **When to start** | Immediately | Week 4 (as a side-task) | **Week 1.** Security is baked into every sprint, not bolted on at the end. |
| **First real money** | After ALL of Tier 0 complete | Week 12 | **Week 20–26.** No real money until security Tier 0 + quality gates G1–G6 pass. |

**Before (Engineering Plan):**
```
Week 4, Day 3: "Fix JWT persistence + add bcrypt"  (1 hour estimated)
```

**After (Integrated):**
```
Weeks 1–4:  Argon2id + JWT RS256 + rate limiting (parallel with data pipeline)
Weeks 5–8:  Order validation pipeline + position limits + circuit breakers + kill switch
Weeks 9–12: Audit logging + agent isolation + tool-call validation
Weeks 13–16: Paper trading with security Tier 0 complete
Weeks 20–26: First real money with all quality gates passing
```

**Reasoning:** The security plan's OWASP mapping is world-class and its Tier 0 items are non-negotiable for a trading system handling real money. Engineering's estimate of 3 days for security is dangerously optimistic. However, security work runs *in parallel* with engineering — not sequentially. The first 4 weeks focus on security-aware design (use Argon2id from day one, design for RS256). Weeks 5–8 are a dedicated security sprint running alongside backtesting.

---

### 1.2 Agent Model Assignments

| Aspect | Tech Stack Plan Says | Engineering Plan Says | Resolution |
|--------|---------------------|----------------------|------------|
| **Strategy Agent** | Claude Sonnet 5 ($2–3/MTok) | DeepSeek V4-Pro ($0.003625/MTok cached) | **Engineering wins at launch; upgrade later.** |
| **Risk Agent** | DeepSeek V4-Flash ($0.0028 cached) | Claude Sonnet 5 ($2/MTok) | **Both are partially right — see below.** |

**Before (Conflicting):**
```
Tech Stack: Strategy → Claude Sonnet 5, Risk → DeepSeek V4-Flash
Engineering: Strategy → DeepSeek V4-Pro, Risk → Claude Sonnet 5
```

**After (Resolved — Phased Approach):**
```
PHASE 1 (Paper Trading — cost-optimized):
  News       → DeepSeek V4-Flash  ($0.0028 cached)
  Strategy   → DeepSeek V4-Pro    ($0.003625 cached)
  Debate     → DeepSeek V4-Flash  ($0.0028 cached)
  Risk       → DeepSeek V4-Flash  ($0.0028 cached) + deterministic rules
  Execution  → No LLM (deterministic)
  Reflection → DeepSeek V4-Pro    ($0.003625 cached)

PHASE 2 (Live Trading — reliability-optimized):
  News       → Claude Sonnet 5    ($2/MTok)
  Strategy   → Claude Sonnet 5    ($2/MTok)
  Debate     → Claude Sonnet 5    ($2/MTok)
  Risk       → Claude Sonnet 5    ($2/MTok) + deterministic rules
  Execution  → No LLM (deterministic)
  Reflection → GPT-5.6 Terra      (~$0.50/MTok)
```

**Reasoning:** At paper trading stage, cost optimization matters more — you're validating the pipeline, not making money. The deterministic risk governor is the real safety net, not the LLM model choice. When moving to live money, reliability wins — upgrade to Claude Sonnet 5 for all high-stakes agents. The Risk agent's core logic must ALWAYS be deterministic code (not LLM), regardless of which model provides supplementary reasoning.

---

### 1.3 Event Bus Channel Count

| Aspect | Architecture Update Says | Integration Plan Says | Resolution |
|--------|-------------------------|----------------------|------------|
| **Streams** | 4 primary streams | 15+ streams (8 Redis Streams + 4 Pub/Sub + 6 shared state) | **Start with 4, expand to 8.** |

**Before (Conflicting):**
```
Architecture Update: 4 streams (market.data, pipeline.signals, pipeline.orders, system.events)
Integration Plan: 15+ streams (full topology from original architecture)
```

**After (Resolved):**
```
Phase 1 (4 streams — simplified):
  market.data        → Ticks + candles (consolidated)
  pipeline.signals   → All agent signals (consolidated)
  pipeline.orders    → Order lifecycle events
  system.events      → Health, alerts, kill switch

Phase 2 (8 streams — expanded after stabilization):
  + pipeline.news       → News agent output (separate for debugging)
  + pipeline.risk       → Risk decisions (separate for audit trail)
  + state.portfolio     → Portfolio state changes
  + state.positions     → Position updates
```

**Reasoning:** 15+ streams is over-engineered for 5 core agents. Start minimal, add streams when debugging or audit requirements justify them. The 4-stream design covers the critical path. Additional streams are added when you need to independently replay or debug a specific agent's output.

---

### 1.4 Agent Count

| Aspect | Quality Plan Tests | Architecture Update Describes | Resolution |
|--------|-------------------|------------------------------|------------|
| **Agents** | 5 core (News, Strategy, Risk, Execution, Reflection) | 8+ (adds Journal, Auditor, Fundamental Analyst, On-device) | **Launch with 5. Add 3 in Phase 2.** |

**Before (Conflicting):**
```
Quality: Tests 5 core agents
Architecture Update: Describes 8+ agent roles including Journal, Auditor, Fundamental Analyst, On-device
```

**After (Resolved):**
```
Phase 1 (Launch — 5 agents):
  1. News Agent        → Market data + sentiment + fundamental intelligence
  2. Strategy Agent    → 16-step pipeline + signal generation
  3. Risk Agent        → Deterministic risk governor + LLM reasoning for edge cases
  4. Execution Agent   → Order placement + management
  5. Reflection Agent  → Post-trade analysis + learning

Phase 2 (Months 3–6 — 8 agents):
  6. Journal Agent     → Separated from Reflection for audit compliance
  7. Auditor Agent     → Continuous compliance checking (EU AI Act)
  8. Market Brain      → Proactive data ingestion (earnings, filings, economic calendar)
```

**Reasoning:** 5 agents cover the complete trading loop. The additional 3 agents are organizational improvements (separating journaling from reflection) and capability additions (proactive market intelligence). They don't change the core pipeline and can be added without architectural changes.

---

### 1.5 Security Scope

| Aspect | Security Plan Describes | Engineering Plan Describes | Resolution |
|--------|------------------------|---------------------------|------------|
| **Agent isolation** | Scoped JWT per agent, tool-call allowlists, inter-agent message validation | AgentPolicyEngine with basic signal/execution checks | **Security plan's scope is correct; engineering implements incrementally.** |

**Before (Conflicting):**
```
Security: Full agent isolation with scoped JWT, tool-call allowlists, inter-agent validation, prompt injection defense
Engineering: AgentPolicyEngine with basic signal strength + confluence checks
```

**After (Resolved — Incremental):**
```
Weeks 1–4:   AgentPolicyEngine (engineering's version) — basic gates
Weeks 5–8:   + Position limits, circuit breakers, kill switch (security Tier 0)
Weeks 9–12:  + Scoped agent JWT, tool-call allowlists (security Tier 1)
Weeks 13–16: + Inter-agent message validation, prompt injection defense (security Tier 1)
Weeks 17–20: + Memory integrity, audit logging with hash chain (security Tier 1–2)
```

**Reasoning:** The security plan's full scope is the target state, but it doesn't all need to be built before the first paper trade. The incremental approach builds the most critical items first (circuit breakers, kill switch) and adds sophistication as the system matures. Paper trading can begin with basic gates; real money requires the full stack.

---

### 1.6 Quality Gates vs Go-to-Market Timing

| Aspect | Quality Plan Says | Market Strategy Says | Resolution |
|--------|------------------|---------------------|------------|
| **Before production** | 10 quality gates, 7-day paper trading, shadow mode, zero divergences for 24h | 50 beta testers in Week 1, public beta in Week 3 | **Quality wins for real money. Market gets demo accounts immediately.** |

**Before (Conflicting):**
```
Quality: No production until ALL gates pass (G1–G10)
Market: 50 beta testers in Week 1, $7 live accounts in Week 3
```

**After (Resolved):**
```
Weeks 1–8:    Demo accounts only (no real money). Market gets users early.
Weeks 9–16:   Paper trading with real market data. Quality gates G1–G6 enforced.
Weeks 17–20:  Shadow mode. Quality gates G7–G8 enforced.
Weeks 20–26:  Real money ($7 accounts). ALL quality gates G1–G10 must pass.
```

**Reasoning:** You can recruit users and validate UX with demo accounts without risking real money. This satisfies market timing (get users early) without quality risk. Real money waits for the full quality stack.

---

### 1.7 EU AI Act Compliance Deadline

| Aspect | Security Plan Says | Master Report Says | Resolution |
|--------|-------------------|-------------------|------------|
| **Deadline** | August 2, 2026 (documentation must be in place) | Phase 3, Weeks 9–12 | **Start documentation now; complete by Week 12.** |

**Before (Conflicting):**
```
Security: Compliance documentation must be in place by August 2, 2026
Master Report: EU AI Act compliance scheduled for Phase 3, Weeks 9–12
```

**After (Resolved):**
```
Weeks 1–4:   Begin risk management system documentation (Art. 9)
Weeks 5–8:   Technical documentation expansion (Art. 11), data governance (Art. 10)
Weeks 9–12:  Human oversight controls (Art. 14), transparency (Art. 13), logging (Art. 12)
Week 12:     File initial compliance documentation
```

**Reasoning:** The August 2 deadline is real for EU market operations. If AlphaStack is NOT operating in EU markets at launch (Kenya-first), the deadline is less urgent but documentation should still start early. The compliance work runs in parallel with engineering and doesn't block the critical path.

---

### 1.8 Pipeline Step Implementation Order

| Aspect | Engineering Plan Says | Market Strategy Says | Resolution |
|--------|----------------------|---------------------|------------|
| **Priority** | Implement Steps 3–10 sequentially (Session → Structure → S/R → Liquidity → SMC → RSI → Candlestick → Confluence) | Steps 1 + 11 + 12 = survival at $7. Ship these first. | **Market strategy's prioritization wins for $7 accounts.** |

**Before (Conflicting):**
```
Engineering: Steps 3–4 first (Session + Market Structure)
Market: Steps 1 + 11 + 12 first (Fundamental + Position Sizing + Stop Loss)
```

**After (Resolved):**
```
Week 1–2:   Steps 1, 11, 12 (Fundamental, Position Sizing, Stop Loss) — SURVIVAL
Week 3–4:   Steps 2, 3, 4 (Bias, Session, Higher TF Alignment) — CONTEXT
Week 5–6:   Steps 7, 6, 9 (SMC, Liquidity, Candlestick) — EDGE
Week 7–8:   Steps 5, 8, 10 (S/R, RSI, Confluence) — REFINEMENT
Week 9–10:  Steps 13, 14, 15, 16 (TP, Management, Exit, Journal) — POLISH
```

**Reasoning:** At $7, one oversized trade without a stop loss = account death. Position sizing and stop loss are existential. Market structure and session analysis are important but secondary to not blowing up. The market strategy's insight that "Steps 1 + 11 + 12 = survival" is correct and should drive implementation order.

---

## 2. Integrated Timeline

### 2.1 Timeline Overview

```
WEEK  1───4   PHASE 0: FOUNDATION
WEEK  5───12  PHASE 1: CORE TRADING
WEEK 13───20  PHASE 2: INTELLIGENCE & VALIDATION
WEEK 20───26  PHASE 3: MARKET LAUNCH

FIRST PAPER TRADE:  Week 14–18
FIRST REAL TRADE:   Week 20–26
```

### 2.2 Phase 0: Foundation (Weeks 1–4)

**Goal:** Data flows, security-aware design, CI/CD, demo accounts live.

| Week | Engineering | Security | Quality | Market |
|------|------------|----------|---------|--------|
| **1** | LiveMarketFeed (CCXT→Aggregator→Orchestrator). Fix ExecutionAgent._submit_order to use BrokerOrder. Alembic migrations. Wire API routes to PostgreSQL. | Replace SHA-256 with Argon2id. Fix JWT secret persistence (load from env/file, not regenerate). Implement rate limiting (slowapi). | Set up pytest infrastructure. Write Risk Governor tests (100% coverage). Configure pre-commit hooks (Ruff, mypy). | Recruit 50 beta testers from Nairobi forex WhatsApp groups. Configure FXPesa demo accounts. |
| **2** | Implement Steps 1, 11, 12 (Fundamental Intelligence, Position Sizing, Stop Loss). Historical data loader for backtesting. | Implement RS256 JWT with persistent keypair. Begin risk management system documentation (EU AI Act Art. 9). | Write unit tests for each agent (basic coverage). Set up GitHub Actions (lint + unit test stages). | Swahili + English interface prototype. Voice command parser (DeepSeek V4-Flash). |
| **3** | Implement Steps 2, 3, 4 (Bias, Session Analysis, Higher TF Alignment). Wire EventBus → WebSocket broadcasts. | Implement TOTP 2FA. Implement basic audit logging (append-only). | Write integration tests (agent chain, event bus). Add agent eval stage to CI/CD. | Private beta launch (50 users, demo accounts only). Telegram bot via OpenClaw. |
| **4** | Implement ModelRouter with DeepSeek V4-Flash/Pro. Add LLM reasoning to Strategy, Debate agents. Per-node timeouts on orchestrator. Agent circuit breakers. | Implement order validation pipeline (7-layer). Position limits (hard-coded). Technical documentation expansion (EU AI Act Art. 11). | Write backtest validation framework skeleton. Deploy Prometheus + Grafana (basic). | Collect beta feedback. Iterate on voice interface. |

**Phase 0 Exit Criteria:**
- [x] Data flows: CCXT → Aggregator → Pipeline → Signal generation
- [x] Security: Argon2id, RS256 JWT, rate limiting, basic audit logging
- [x] Quality: Risk Governor 100% coverage, CI/CD operational, >50% unit test coverage
- [x] Market: 50 beta users on demo accounts, Telegram cockpit live
- [x] Pipeline: Steps 1, 2, 3, 4, 11, 12 implemented (survival + context)

---

### 2.3 Phase 1: Core Trading (Weeks 5–12)

**Goal:** Full strategy pipeline, backtesting, paper trading engine, security Tier 0 complete.

| Week | Engineering | Security | Quality | Market |
|------|------------|----------|---------|--------|
| **5** | Implement Steps 7, 6 (SMC, Liquidity Detection). Binance CCXT connector for crypto. | Implement circuit breakers (daily loss, consecutive losses, concentration, volatility). | Build fill simulator with realistic slippage. Write module equivalence tests. | Open public beta (500 users). Free tier: 2 pairs, delayed signals. |
| **6** | Implement Steps 9, 5 (Candlestick Confirmation, S/R). Add LLM reasoning to Risk Agent (borderline cases). | Implement kill switch (UI button + API endpoint + keyboard shortcut). | Walk-forward validation framework. Monte Carlo ruin probability. | Pro tier ($10/mo): all pairs, real-time, voice. Add Binance crypto pairs. |
| **7** | Implement Steps 8, 10 (RSI Confirmation, Confluence Engine). AgentPolicyEngine (deterministic gates). | Implement tool-call validation for all agents. Implement agent isolation (scoped JWT per agent). | Backtest: run pipeline on 3 months BTC/USDT + EUR/USD data. Validate OOS Sharpe ≥50% of IS. | "$7 to $70 Challenge" content production. TikTok/YouTube demo videos. |
| **8** | Implement Steps 13, 14, 15 (Take Profit, Trade Management, Exit Conditions). TraceMiner (pattern extraction from trade history). | Implement prompt injection defense. Implement inter-agent message validation. | Deploy paper trading engine. Start shadow mode (live vs paper comparison). | University partnerships (UoN, Strathmore). Referral program design. |
| **9** | Implement Step 16 (Journal). Full pipeline integration test (all 16 steps). Optimize model routing (measure actual cache hit rates). | Implement memory integrity for Reflection agent (append-only + hash). EU AI Act human oversight controls (Art. 14). | 7-day paper trading validation begins. Compare against backtest expectations. | Growth marketing: TikTok ads, WhatsApp group campaigns. |
| **10** | Backtesting engine production hardening. Historical data quality validation. Fill simulator calibration against FXPesa actual fills. | EU AI Act transparency/disclosure (Art. 13). Comprehensive agent action logging with hash chain. | Fix any paper trading divergences. Shadow mode: zero divergences for 24h target. | CMA sandbox application preparation. Engage CMA for pre-application consultation. |
| **11** | Production deployment (staging). Performance testing. End-to-end latency optimization. | EU AI Act data governance (Art. 10). External penetration test (planned). | Agent eval pass rates ≥85% per agent. Performance benchmarks within targets. | CMA sandbox application submitted. University trading competition pilot. |
| **12** | Production deployment (staging hardened). Monitoring dashboards complete. All Prometheus metrics instrumented. | EU AI Act compliance documentation filed. Risk register complete. | All quality gates G1–G8 passing. Paper trading: win rate within 10% of backtest, 7+ days. | 2,000+ users target. Referral program launch. |

**Phase 1 Exit Criteria:**
- [x] Pipeline: All 16 steps implemented and tested
- [x] Security: Tier 0 complete (circuit breakers, kill switch, order validation, position limits, audit logging)
- [x] Quality: G1–G8 passing, paper trading 7+ days, shadow mode 24h zero divergences
- [x] Market: 2,000+ users, CMA sandbox application submitted
- [x] Backtest: OOS Sharpe ≥50% of IS, Monte Carlo ruin <5%

---

### 2.4 Phase 2: Intelligence & Validation (Weeks 13–20)

**Goal:** First paper trade with real market data, shadow mode validation, agent evals production-grade.

| Week | Engineering | Security | Quality | Market |
|------|------------|----------|---------|--------|
| **13** | First paper trade on staging (real market data, simulated execution). Fix any pipeline issues discovered. | Memory integrity verification running in production. Agent action logging validated. | Paper trading performance comparison: paper vs backtest. Alert on >10% deviation. | Content: "First AI Paper Trade" blog/video. Community updates. |
| **14** | Paper trading stability. Model routing A/B test (DeepSeek vs Sonnet for Strategy agent). | Adaptive circuit breakers (market-aware thresholds). | Continue paper trading. Collect 14+ days of data. | Beta user feedback collection. Feature requests triage. |
| **15** | Trace mining feedback loop (insights → signal weight updates). Optimize pipeline latency. | Crypto-agility abstraction layer (PQC Phase 1). | Monte Carlo validation on paper trading results. Walk-forward on live data. | M-Pesa integration research (Daraja API). Partner outreach. |
| **16** | Paper trading: 28+ days continuous. Performance profiling. Bug fixes from paper trading. | Hybrid JWT signing evaluation (Ed25519 + ML-DSA-65 prototype). | Paper trading: win rate, Sharpe, max drawdown all within targets. | Community growth. User testimonials. Case studies. |
| **17** | Shadow mode: production-stable 7-day zero divergences. Final pipeline tuning. | External penetration test. Remediate findings. | Quality gate G9: Shadow mode — zero divergences for 7 consecutive days. | Prepare for real-money launch. User communication plan. |
| **18** | Pre-production hardening. Load testing. Failover testing. Kill switch end-to-end validation. | Kill switch end-to-end test (simulate emergency). Circuit breaker reset procedure documented. | Quality gate G10: Paper trading — win rate within 10% of backtest for 28+ days. | CMA sandbox status check. Regulatory green light confirmation. |
| **19** | Production deployment (small capital, $7 test account). Monitor 48h. | All security Tier 0 + Tier 1 items verified in production. | All quality gates G1–G10 passing. Manual approval for first real trade. | "First Real Trade" announcement prepared. |
| **20** | **FIRST REAL TRADE** ($7 account, FXPesa). Monitor closely for 7 days. | Real-time monitoring active. All alerts configured. | Post-trade analysis. Compare real execution vs paper trading. | Announce first real trade. "$7 to $70 Challenge" begins. |

**Phase 2 Exit Criteria:**
- [x] Paper trading: 28+ days, win rate within 10% of backtest
- [x] Shadow mode: 7 consecutive days zero divergences
- [x] Security: Tier 0 + Tier 1 complete, penetration test passed
- [x] Quality: ALL gates G1–G10 passing
- [x] First real trade executed and monitored

---

### 2.5 Phase 3: Market Launch (Weeks 20–26)

**Goal:** Real trading, user growth, iterate on performance, CMA sandbox approval.

| Week | Engineering | Security | Quality | Market |
|------|------------|----------|---------|--------|
| **20–21** | Real trading stability. Monitor all metrics. Fix any real-execution vs paper divergences. | Real-money circuit breakers verified. Position limits enforced at broker level. | Daily P&L monitoring. Weekly performance report. Alert on anomalies. | "$7 to $70 Challenge" live streaming. TikTok/YouTube content. |
| **22–23** | Multi-pair expansion (add GBP/USD, USD/JPY). Model routing optimization (measure actual costs). | Quarterly security review. Dependency CVE scan. | Performance benchmarks: Sharpe, win rate, max drawdown tracked weekly. | 5,000+ users target. Partnership with Kenyan trading influencers. |
| **24–25** | Binance crypto integration live. Cross-broker portfolio view. Performance optimization. | Agent Governance Toolkit evaluation (Microsoft). OWASP governance Level 2 preparation. | Agent eval regression testing from trace mining. Continuous improvement loop active. | University trading competition. M-Pesa integration prototype. |
| **26** | System stabilization. Documentation. Prepare for next phase (MCP adoption, Market Brain). | Quarterly security review complete. PQC migration planning. | System operating within all performance targets. Ready for scale. | 10,000+ users target. Revenue tracking. Prepare for South Africa expansion. |

**Phase 3 Exit Criteria:**
- [x] Real trading: 30+ days continuous, profitable or break-even
- [x] Users: 5,000+ registered, 500+ paying
- [x] Revenue: Cover infrastructure costs
- [x] Security: Quarterly review passed
- [x] Performance: All benchmarks within targets
- [x] Ready for Phase 4 (MCP adoption, A2A evaluation, on-device inference)

---

### 2.6 Dependency Map

```
CRITICAL PATH (blocks everything):
  Data Pipeline → Strategy Pipeline → Backtesting → Paper Trading → Real Trading

PARALLEL WORKSTREAMS:
  Security (Weeks 1–20) ─────────────────────────────────────────────────┐
  Quality (Weeks 1–20) ──────────────────────────────────────────────────┤
  Market (Weeks 1–26) ───────────────────────────────────────────────────┤
  EU AI Act Compliance (Weeks 1–12) ─────────────────────────────────────┘

DEPENDENCY CHAIN:
  Week 1:  Data Pipeline ──┐
  Week 2:  Steps 1,11,12 ──┤
  Week 3:  Steps 2,3,4 ────┼──→ Week 5: Steps 6,7 ──→ Week 7: Steps 8,10
  Week 4:  ModelRouter ────┘         │                      │
                                      ├──→ Week 9: Full Pipeline Test
                                      │
  Week 5:  Backtesting Engine ────────┤
  Week 6:  Fill Simulator ───────────┤
  Week 7:  Walk-Forward Validation ──┤
  Week 8:  Paper Trading Engine ─────┼──→ Week 13: First Paper Trade
                                      │
  Week 1:  Argon2id + JWT ───────────┤
  Week 5:  Circuit Breakers ─────────┤
  Week 6:  Kill Switch ──────────────┼──→ Week 17: Shadow Mode (7 days)
  Week 9:  Memory Integrity ─────────┤
                                      │
  Week 13: Paper Trading ────────────┼──→ Week 20: First Real Trade
  Week 17: Shadow Mode ──────────────┘
```

---

## 3. Phase Gates

### Phase 0: Foundation (Weeks 1–4)

| Gate | Criteria | Estimated Completion | Risk Level |
|------|----------|---------------------|------------|
| **G0.1** Data Pipeline | CCXT → Aggregator → Pipeline → Signal. 99% uptime over 3 days. | Week 1 | 🟡 Medium — CCXT edge cases |
| **G0.2** Survival Steps | Steps 1, 11, 12 producing valid output on real market data. | Week 2 | 🟢 Low — well-defined algorithms |
| **G0.3** Security Baseline | Argon2id, RS256 JWT, rate limiting all operational. | Week 2 | 🟡 Medium — JWT key management |
| **G0.4** CI/CD | GitHub Actions: lint + unit tests + security scans passing on every PR. | Week 3 | 🟢 Low — standard setup |
| **G0.5** Beta Users | 50 users on demo accounts, Telegram cockpit functional. | Week 3 | 🟡 Medium — user recruitment |
| **G0.6** Model Routing | DeepSeek V4-Flash operational with cache hit tracking. | Week 4 | 🟡 Medium — API integration |

**Phase 0 Risk:** Medium. Most items are well-understood engineering tasks. Main risk is CCXT connector edge cases and MT5 authentication issues.

---

### Phase 1: Core Trading (Weeks 5–12)

| Gate | Criteria | Estimated Completion | Risk Level |
|------|----------|---------------------|------------|
| **G1.1** Full Pipeline | All 16 steps implemented and producing valid output. | Week 8 | 🔴 High — S/R clustering, SMC detection complex |
| **G1.2** Security Tier 0 | Circuit breakers, kill switch, order validation, position limits, audit logging. | Week 8 | 🔴 High — security scope is large |
| **G1.3** Backtest Validation | OOS Sharpe ≥50% of IS. Monte Carlo ruin <5%. Walk-forward 5 splits. | Week 10 | 🔴 High — fill simulation accuracy |
| **G1.4** Paper Trading | 7+ days continuous. Win rate within 10% of backtest. | Week 12 | 🟡 Medium — depends on pipeline quality |
| **G1.5** Shadow Mode | Zero divergences for 24h between live and paper. | Week 12 | 🟡 Medium — depends on code parity |
| **G1.6** Quality Gates G1–G8 | Lint, unit tests, agent evals, security, integration, backtest, E2E, performance all passing. | Week 12 | 🟡 Medium — test writing effort |
| **G1.7** CMA Sandbox | Application submitted. Pre-application consultation complete. | Week 12 | 🟡 Medium — regulatory timeline uncertain |

**Phase 1 Risk:** HIGH. This is the hardest phase. The 16-step pipeline implementation and backtesting engine are the most complex engineering tasks. Security Tier 0 scope is large. Risk mitigation: cut scope if behind (ship 8 steps instead of 16, add remaining in Phase 2).

---

### Phase 2: Intelligence & Validation (Weeks 13–20)

| Gate | Criteria | Estimated Completion | Risk Level |
|------|----------|---------------------|------------|
| **G2.1** Paper Trading Extended | 28+ days continuous. All metrics within targets. | Week 16 | 🟡 Medium |
| **G2.2** Shadow Mode Extended | 7 consecutive days zero divergences. | Week 17 | 🟡 Medium |
| **G2.3** Penetration Test | External pen test complete. Zero critical findings unresolved. | Week 17 | 🟡 Medium — external dependency |
| **G2.4** Security Tier 1 | Agent isolation, tool-call validation, prompt injection defense. | Week 18 | 🟡 Medium |
| **G2.5** Quality Gates G1–G10 | ALL gates passing. Manual approval for first real trade. | Week 19 | 🟢 Low — cumulative validation |
| **G2.6** First Real Trade | $7 account, FXPesa, monitored for 7 days. | Week 20 | 🔴 High — real money at risk |

**Phase 2 Risk:** Medium-High. The extended paper trading and shadow mode periods are time-consuming but low-risk technically. The first real trade is the highest-risk moment — mitigated by strict quality gates and small capital.

---

### Phase 3: Market Launch (Weeks 20–26)

| Gate | Criteria | Estimated Completion | Risk Level |
|------|----------|---------------------|------------|
| **G3.1** Real Trading Stability | 30+ days continuous real trading. No critical bugs. | Week 24 | 🟡 Medium |
| **G3.2** User Growth | 5,000+ registered users. 500+ paying. | Week 24 | 🟡 Medium — marketing execution |
| **G3.3** Revenue | Infrastructure costs covered by revenue. | Week 26 | 🟡 Medium |
| **G3.4** Multi-Broker | Binance crypto integration live. Cross-broker portfolio view. | Week 24 | 🟡 Medium |
| **G3.5** Performance | All benchmarks within targets for 4+ weeks. | Week 26 | 🟢 Low |
| **G3.6** Regulatory | CMA sandbox approval (or clear timeline). | Week 26 | 🔴 High — external dependency |

**Phase 3 Risk:** Medium. The system is proven at this point. Main risks are user acquisition costs and CMA sandbox timeline.

---

## 4. Resource Allocation

### 4.1 Phase-by-Phase Focus

| Phase | Primary Focus | Secondary Focus | Deferred |
|-------|--------------|-----------------|----------|
| **Phase 0 (Wk 1–4)** | Data pipeline, survival steps (1,11,12), security baseline | CI/CD, beta recruitment | MCP, A2A, on-device, voice |
| **Phase 1 (Wk 5–12)** | Full pipeline, backtesting, security Tier 0, paper trading | Monitoring, EU AI Act docs | Market Brain, trace mining, distillation |
| **Phase 2 (Wk 13–20)** | Extended validation, shadow mode, security Tier 1 | Trace mining feedback, model optimization | A2A, on-device inference, Qwen3 self-hosted |
| **Phase 3 (Wk 20–26)** | Real trading, user growth, multi-broker | M-Pesa integration, voice improvements | MCP adoption, multi-teacher distillation |

### 4.2 Model/Agent Allocation per Phase

| Phase | Models Used | Agents Active | Estimated LLM Cost/Day |
|-------|------------|---------------|----------------------|
| **Phase 0** | DeepSeek V4-Flash only | 5 core (minimal LLM usage) | $0.05–0.10 |
| **Phase 1** | DeepSeek V4-Flash + V4-Pro | 5 core (full LLM reasoning) | $0.10–0.25 |
| **Phase 2** | DS V4-Flash + V4-Pro + Claude Sonnet 5 (selective) | 5 core + model routing | $0.25–1.00 |
| **Phase 3** | Full tiered model strategy | 5 core + expanded | $1.00–5.00 |

### 4.3 Budget Allocation per Phase

| Phase | Infrastructure | LLM API | Data Feeds | Monitoring | Security Tools | Total/Month |
|-------|---------------|---------|------------|------------|---------------|-------------|
| **Phase 0** | $0 (local) | $3–5 | $0–10 | $0 | $0 | **$3–15** |
| **Phase 1** | $15 (VPS) | $5–15 | $0–20 | $0 | $0 | **$20–50** |
| **Phase 2** | $15–30 | $10–30 | $10–30 | $10–20 | $0 | **$45–110** |
| **Phase 3** | $30–50 | $20–50 | $20–50 | $10–20 | $500 (pen test) | **$80–170 + $500 one-time** |

### 4.4 What to Build vs Buy vs Borrow

| Component | Decision | Reasoning |
|-----------|----------|-----------|
| **Agent orchestration** | BUILD (LangGraph) | Core differentiator, must own |
| **Notification layer** | BORROW (OpenClaw) | Saves 8–12 weeks, not core IP |
| **Broker connectors** | BUILD (CCXT + MT5) | Core IP, must control |
| **Monitoring** | BUILD (Prometheus + Grafana) | Free, standard, self-hosted |
| **CI/CD** | BUILD (GitHub Actions) | Free, standard |
| **Voice TTS/STT** | BUY (Qwen3 self-hosted + evaluate Gradium) | Open-source backbone, evaluate commercial for quality |
| **Market data** | BUY (Finnhub free tier + CCXT) | Free tiers sufficient at launch |
| **Alternative data** | BUILD (M-Pesa API + on-chain) | Unique edge, must own |
| **Backtesting** | BUILD | Core differentiator |
| **ML models** | BUILD (FinBERT fine-tune + XGBoost) | Core IP |

---

## 5. Risk Mitigation

### 5.1 Top 10 Risks

| # | Risk | Likelihood | Impact | Mitigation | Contingency | Early Warning |
|---|------|-----------|--------|------------|-------------|---------------|
| **1** | **Pipeline produces poor signals** — win rate below 45% on paper trading | High | Critical | Implement 8 core steps first, validate with backtesting before adding more. Tune parameters iteratively. | Cut to 4-step minimum viable strategy (Steps 1, 2, 11, 12). Ship simpler but working. | Paper trading win rate <40% after 7 days. |
| **2** | **Security Tier 0 takes longer than 8 weeks** | Medium | Critical | Security work starts Week 1 (not Week 4). Parallel workstreams. | Delay first real money. Paper trading continues with demo capital. | Week 6: circuit breakers + kill switch not operational. |
| **3** | **FXPesa MT5 Python API has undocumented limitations** | Medium | High | Prototype MT5 connection in Week 1. Document all API quirks. | Fall back to CCXT for all trading. Use FXPesa web interface for manual trades. | Week 1: MT5 connection fails or has critical missing features. |
| **4** | **DeepSeek V4-Flash quality insufficient for financial reasoning** | Medium | Medium | A/B test against Claude Sonnet 5 on real trading decisions. | Upgrade to Claude Sonnet 5 for Strategy agent. Budget increases $5–15/day. | Agent eval pass rate <80% on financial reasoning tasks. |
| **5** | **Backtesting overfitting** — OOS Sharpe << IS Sharpe | High | High | Walk-forward validation with 5 splits. Monte Carlo ruin probability. Parameter stability checks. | Reduce strategy complexity. Use simpler models with fewer parameters. | OOS/IS Sharpe ratio <0.3 (target: ≥0.5). |
| **6** | **Beta testers not found** | Medium | Low | Start recruiting from Nairobi forex WhatsApp groups NOW (not Week 1). University partnerships. | Launch with 10–20 users instead of 50. Focus on quality feedback over quantity. | Week 2: <10 beta users signed up. |
| **7** | **CMA sandbox application delayed/rejected** | Medium | High | Engage CMA for pre-application consultation. Prepare thorough documentation. | Operate as software sold to traders (grey area but lower regulatory risk). FXPesa integration provides cover. | Week 12: No response from CMA. |
| **8** | **LLM cost overrun** (actual costs >> expected due to cache miss rates) | High | Low | Track actual cost per agent including cache hit rates. Budget caps per agent. | Reduce LLM usage. Use deterministic code for more decisions. Self-host Qwen3. | Daily LLM cost >$5 (target: <$1). |
| **9** | **Single developer capacity** — can't execute all plans | Certain | High | Prioritize ruthlessly. Cut Phase 2–4 items from initial scope. Use OpenClaw for notification layer. | Hire/contract. Reduce scope to 4-step minimum viable strategy. | Week 4: >2 weeks behind schedule. |
| **10** | **Market data quality issues** — gaps, stale data, API outages | Medium | Medium | Multi-source redundancy (CCXT + CryptoCompare + Finnhub). Data quality checks on ingestion. | Fall back to delayed data. Pause trading during data outages. | Data gaps >1% of expected ticks. |

### 5.2 Contingency Triggers

| Trigger | Action |
|---------|--------|
| Week 4: <3 of 6 Phase 0 gates passed | **Reduce scope.** Ship 4-step minimum viable strategy. Defer Steps 5–10 to Phase 2. |
| Week 8: Pipeline win rate <40% on backtesting | **Pivot to simpler strategy.** Use Steps 1, 2, 11, 12 only. Add complexity only after profitability. |
| Week 12: Security Tier 0 incomplete | **Delay real money.** Continue paper trading. No real money until Tier 0 complete. |
| Week 16: Paper trading win rate deviates >20% from backtest | **Investigate root cause.** Likely fill simulation inaccuracy. Recalibrate before proceeding. |
| Week 20: First real trade loses >5% in first week | **Halt trading.** Review all quality gates. Fix issues before resuming. |

### 5.3 Scope Reduction Ladder

If the project falls behind, reduce scope in this order:

```
LEVEL 1 (Cut polish):
  Remove: Steps 13–16 (TP, Management, Exit, Journal)
  Impact: Simpler trade management, no learning loop
  Recovery: Add back in Phase 2

LEVEL 2 (Cut edge):
  Remove: Steps 5–10 (S/R, Liquidity, SMC, RSI, Candlestick, Confluence)
  Impact: Simpler signal generation, lower win rate
  Recovery: Add back in Phase 2–3

LEVEL 3 (Minimum viable):
  Keep ONLY: Steps 1, 2, 11, 12 (Fundamental, Bias, Position Sizing, Stop Loss)
  Impact: Basic trading with survival controls
  Recovery: Add complexity only after proving profitability

LEVEL 4 (Paper only):
  No real money. Paper trading indefinitely until quality is proven.
  Impact: No revenue, but no losses either
  Recovery: Resume real-money plan when ready
```

---

## 6. Success Metrics

### 6.1 Phase 0 KPIs (Weeks 1–4)

| KPI | Target | Measurement |
|-----|--------|-------------|
| Data pipeline uptime | >99% over 3 days | Prometheus |
| Signal generation | ≥1 signal/day on BTC/USDT | Pipeline output logs |
| End-to-end latency | <5s from data to signal | Timing middleware |
| Unit test coverage | >50% for core modules | pytest --cov |
| Beta users | 50 registered | Platform analytics |
| CI/CD operational | All stages green on main branch | GitHub Actions |

### 6.2 Phase 1 KPIs (Weeks 5–12)

| KPI | Target | Measurement |
|-----|--------|-------------|
| Pipeline steps | 16/16 implemented | Code review |
| Backtest win rate | >45% (BTC/USDT, EUR/USD) | Backtester output |
| OOS/IS Sharpe ratio | ≥0.5 | Walk-forward validation |
| Monte Carlo ruin probability | <5% | Monte Carlo simulator |
| Paper trading win rate | Within 10% of backtest | Paper trading engine |
| Security Tier 0 | 100% complete | Security checklist |
| Quality gates G1–G8 | All passing | CI/CD pipeline |
| Users | 2,000+ registered | Platform analytics |

### 6.3 Phase 2 KPIs (Weeks 13–20)

| KPI | Target | Measurement |
|-----|--------|-------------|
| Paper trading duration | 28+ days continuous | Paper trading engine |
| Shadow mode divergences | 0 for 7 consecutive days | Shadow mode comparator |
| Agent eval pass rate | ≥85% per agent | Agent eval framework |
| Penetration test | Zero critical findings unresolved | Pen test report |
| Quality gates G1–G10 | ALL passing | CI/CD pipeline |
| First real trade | Executed and monitored | Broker confirmation |

### 6.4 Phase 3 KPIs (Weeks 20–26)

| KPI | Target | Measurement |
|-----|--------|-------------|
| Real trading days | 30+ continuous | Broker logs |
| Real trading P&L | Break-even or better | Broker P&L |
| Max drawdown | <10% | Monitoring dashboard |
| Users | 5,000+ registered, 500+ paying | Platform analytics |
| Monthly revenue | Cover infrastructure costs | Billing system |
| System uptime | >99.5% | Prometheus |
| CMA sandbox | Application submitted (approved if possible) | CMA correspondence |

### 6.5 Minimum Viable Trading System Definition

**A system is "minimum viable" when ALL of the following are true:**

1. **Data flows:** Real market data → pipeline → signal generation (end-to-end)
2. **Risk controls:** Stop loss on every trade, position limits enforced, kill switch operational
3. **Execution:** Orders placed and filled through broker API (CCXT or MT5)
4. **Monitoring:** P&L, drawdown, and position data visible in real-time
5. **Paper trading:** 7+ days continuous, win rate >40%
6. **Security:** Argon2id passwords, JWT auth, rate limiting, audit logging

**This minimum viable system uses Steps 1, 2, 11, 12 only.** It generates basic signals with fundamental intelligence and market bias, enforces strict position sizing and stop losses. It is NOT optimized for maximum returns — it is optimized for survival.

---

## 7. First Trade Checklist

### 7.1 Pre-Paper Trade Checklist (Must pass before first paper trade)

| # | Item | Owner | Estimated Effort | Priority | Status |
|---|------|-------|-----------------|----------|--------|
| 1 | **Data pipeline: CCXT → Aggregator → Pipeline** | Engineering | 3 days | 🔴 P0 | ❌ |
| 2 | **ExecutionAgent wired to BrokerOrder** | Engineering | 1 day | 🔴 P0 | ❌ |
| 3 | **Steps 1, 11, 12 implemented** (Fundamental, Position Sizing, Stop Loss) | Engineering | 5 days | 🔴 P0 | ❌ |
| 4 | **Steps 2–4 implemented** (Bias, Session, Higher TF) | Engineering | 3 days | 🔴 P0 | ❌ |
| 5 | **Steps 5–10 implemented** (S/R, Liquidity, SMC, RSI, Candlestick, Confluence) | Engineering | 10 days | 🔴 P0 | ❌ |
| 6 | **Steps 13–16 implemented** (TP, Management, Exit, Journal) | Engineering | 5 days | 🟡 P1 | ❌ |
| 7 | **ModelRouter with DeepSeek V4-Flash** | Engineering | 2 days | 🔴 P0 | ❌ |
| 8 | **Risk Governor: 100% test coverage** | Quality | 3 days | 🔴 P0 | ❌ |
| 9 | **Argon2id password hashing** | Security | 1 day | 🔴 P0 | ❌ |
| 10 | **RS256 JWT with persistent keypair** | Security | 3 days | 🔴 P0 | ❌ |
| 11 | **Rate limiting on all endpoints** | Security | 1 day | 🔴 P0 | ❌ |
| 12 | **Order validation pipeline (7-layer)** | Security | 5 days | 🔴 P0 | ❌ |
| 13 | **Position limits (hard-coded)** | Security | 2 days | 🔴 P0 | ❌ |
| 14 | **Circuit breakers** | Security | 3 days | 🔴 P0 | ❌ |
| 15 | **Kill switch** | Security | 2 days | 🔴 P0 | ❌ |
| 16 | **Basic audit logging** | Security | 3 days | 🔴 P0 | ❌ |
| 17 | **Unit test coverage >50%** | Quality | 5 days | 🟡 P1 | ❌ |
| 18 | **CI/CD: lint + unit + security scans** | Quality | 2 days | 🔴 P0 | ❌ |
| 19 | **Backtesting engine functional** | Engineering | 5 days | 🔴 P0 | ❌ |
| 20 | **Fill simulator with realistic slippage** | Engineering | 3 days | 🟡 P1 | ❌ |
| 21 | **Walk-forward validation** | Quality | 3 days | 🟡 P1 | ❌ |
| 22 | **Monte Carlo ruin probability <5%** | Quality | 2 days | 🟡 P1 | ❌ |
| 23 | **Prometheus + Grafana deployed** | Quality | 2 days | 🟡 P1 | ❌ |
| 24 | **Historical data loaded** (3+ months BTC/USDT, EUR/USD) | Engineering | 1 day | 🔴 P0 | ❌ |

**Total estimated effort: ~75 person-days (15 weeks for 1 person, 8 weeks for 2 people)**

---

### 7.2 Pre-Real-Money Checklist (Must pass before first real $7 trade)

| # | Item | Owner | Estimated Effort | Priority | Status |
|---|------|-------|-----------------|----------|--------|
| 1 | **Paper trading: 28+ days continuous** | Quality | 28 days (passive) | 🔴 P0 | ❌ |
| 2 | **Paper trading win rate within 10% of backtest** | Quality | 1 day (analysis) | 🔴 P0 | ❌ |
| 3 | **Shadow mode: 7 consecutive days zero divergences** | Quality | 7 days (passive) | 🔴 P0 | ❌ |
| 4 | **Quality gate G1: Lint — zero errors** | Quality | Ongoing | 🔴 P0 | ❌ |
| 5 | **Quality gate G2: Unit tests — ≥90% coverage, 0 failures** | Quality | Ongoing | 🔴 P0 | ❌ |
| 6 | **Quality gate G3: Agent evals — ≥85% pass rate per agent** | Quality | 3 days | 🔴 P0 | ❌ |
| 7 | **Quality gate G4: Security — zero critical/high CVEs** | Security | Ongoing | 🔴 P0 | ❌ |
| 8 | **Quality gate G5: Integration — all critical paths pass** | Quality | 3 days | 🔴 P0 | ❌ |
| 9 | **Quality gate G6: Backtest — OOS Sharpe ≥50% of IS, MC ruin <5%** | Quality | Ongoing | 🔴 P0 | ❌ |
| 10 | **Quality gate G7: E2E — all scenarios pass** | Quality | 2 days | 🔴 P0 | ❌ |
| 11 | **Quality gate G8: Performance — P95 latency within targets** | Quality | 1 day | 🔴 P0 | ❌ |
| 12 | **Quality gate G9: Shadow mode — zero divergences for 24h** | Quality | 1 day | 🔴 P0 | ❌ |
| 13 | **Quality gate G10: Paper trading — 7+ days, win rate validated** | Quality | 7 days (passive) | 🔴 P0 | ❌ |
| 14 | **Agent isolation (scoped JWT per agent)** | Security | 5 days | 🟡 P1 | ❌ |
| 15 | **Tool-call validation for all agents** | Security | 3 days | 🟡 P1 | ❌ |
| 16 | **Prompt injection defense** | Security | 3 days | 🟡 P1 | ❌ |
| 17 | **Memory integrity for Reflection agent** | Security | 2 days | 🟡 P1 | ❌ |
| 18 | **Comprehensive audit logging (hash chain)** | Security | 5 days | 🟡 P1 | ❌ |
| 19 | **External penetration test** | Security | 5 days (external) | 🟡 P1 | ❌ |
| 20 | **Kill switch end-to-end test** | Security + Quality | 1 day | 🔴 P0 | ❌ |
| 21 | **Circuit breaker reset procedure documented** | Security | 1 day | 🔴 P0 | ❌ |
| 22 | **Monitoring dashboards: all panels green** | Quality | 1 day | 🔴 P0 | ❌ |
| 23 | **Alerting rules configured** (Telegram notifications) | Quality | 1 day | 🔴 P0 | ❌ |
| 24 | **EU AI Act compliance documentation filed** | Security | 5 days | 🟡 P1 | ❌ |
| 25 | **Manual approval by Valentine** for first real trade | Founder | 1 day | 🔴 P0 | ❌ |
| 26 | **FXPesa live account funded with $7** | Founder | 1 day | 🔴 P0 | ❌ |
| 27 | **All position limits verified at broker level** | Security | 1 day | 🔴 P0 | ❌ |
| 28 | **Daily loss circuit breaker tested** (simulate 5% loss) | Security + Quality | 1 day | 🔴 P0 | ❌ |
| 29 | **Rollback plan documented** (how to halt and revert) | Engineering | 1 day | 🔴 P0 | ❌ |
| 30 | **Post-trade analysis pipeline operational** | Engineering | 2 days | 🟡 P1 | ❌ |

**Total estimated effort: ~65 person-days + 28 days passive monitoring (paper trading) + 7 days passive monitoring (shadow mode)**

---

### 7.3 The Single Most Important Item

**Item #25: Manual approval by Valentine for first real trade.**

No amount of automated testing replaces human judgment for the first real-money trade. Before clicking "approve":

1. Review the last 7 days of paper trading results
2. Verify all quality gates are green in Grafana
3. Confirm kill switch works (activate, verify halt, deactivate)
4. Confirm position limits are set correctly at the broker
5. Start with the minimum: $7, 0.01 lot, EURUSD, London session
6. Monitor the trade in real-time for the first hour
7. Have the kill switch shortcut ready

**This is not a checkbox. This is a deliberate human decision.**

---

## Appendix A: Key Decisions Summary

| Decision | Choice | Confidence | Review Date |
|----------|--------|-----------|-------------|
| Primary LLM | DeepSeek V4-Flash (cached) | ⭐⭐⭐⭐⭐ | Month 3 |
| Reasoning LLM (launch) | DeepSeek V4-Pro | ⭐⭐⭐⭐ | Month 3 |
| Reasoning LLM (live) | Claude Sonnet 5 | ⭐⭐⭐⭐ | Month 6 |
| Orchestration | LangGraph 1.0 | ⭐⭐⭐⭐⭐ | Month 6 |
| Event bus | Redis Streams (4 streams) | ⭐⭐⭐⭐⭐ | Month 6 |
| Primary broker | FXPesa (CMA #107) | ⭐⭐⭐⭐⭐ | — |
| Primary crypto | Binance (CCXT) | ⭐⭐⭐⭐ | Month 3 |
| First market | Kenya (CMA sandbox) | ⭐⭐⭐⭐⭐ | — |
| Notification layer | OpenClaw (Telegram) | ⭐⭐⭐⭐ | Month 3 |
| Pricing | Free + $10–15 Pro + 15–20% performance | ⭐⭐⭐⭐ | Month 6 |
| Agent count (launch) | 5 core agents | ⭐⭐⭐⭐⭐ | Month 6 |
| Pipeline steps (launch) | 16 steps (priority-ordered) | ⭐⭐⭐⭐ | Month 3 |

---

## Appendix B: What Was Cut and Why

| Component | Original Plan | Cut Reason | When to Revisit |
|-----------|--------------|------------|-----------------|
| A2A protocol | Evaluate in Phase 1 | Adds complexity without benefit for fixed pipeline | Phase 3 (Month 6) |
| Kafka event bus | Replace Redis Streams | Over-engineered at current scale | When >50K msg/sec |
| On-device inference (Bonsai 27B) | Phase 2 | Not on critical path for first trade | Phase 3 (Month 4) |
| Self-hosted Qwen3 | Phase 1 | API-based DeepSeek is cheaper at launch scale | Phase 3 (Month 6) |
| Multi-teacher distillation | Phase 2 | Requires months of training data first | Phase 4 (Month 9) |
| MCP adoption | Phase 1 | Adds abstraction layer; direct imports work fine for 5 agents | Phase 3 (Month 4) |
| ClickHouse analytics | Phase 1 | TimescaleDB sufficient at launch | When capital >$50K |
| FIX Protocol connector | Phase 3 | Institutional DMA is years away | When capital >$500K |
| Custom Transformer model | Phase 2 | LLMs with prompting are sufficient | When LLM quality plateaus |
| CNN chart recognition | Phase 2 | Vision LLMs (Kimi K3) now sufficient | When LLM vision improves |
| GAN synthetic data | Phase 3 | Multi-teacher distillation is better approach | Likely never |
| Mobile app (Flutter) | Phase 1 | Web + Telegram covers launch needs | Phase 3 (Month 6) |
| Voice interface (full) | Phase 1 | Text-based Telegram covers launch; voice is differentiation | Phase 2 (Month 3) |

---

## Appendix C: Weekly Check-In Template

Every week, answer these 5 questions:

```
1. Are we on track for the phase gate? (Which gates passed/failed?)
2. What's the biggest blocker right now?
3. What did we learn this week that changes the plan?
4. Are we still on the critical path? (Or did we get distracted?)
5. Do we need to activate the scope reduction ladder?
```

**If the answer to #5 is "yes" for 2 consecutive weeks, activate Level 1 scope reduction. No exceptions.**

---

*This is THE plan. Not one of eight plans. THE plan.*

*Every line of code, every security control, every quality gate, every market activity is sequenced in this document.*

*Execute against this. Update it weekly. Nothing else matters until the first real trade.*

*Generated: 2026-07-19*
*Next review: 2026-07-26 (weekly)*
*Owner: Valentine (Founder)*
