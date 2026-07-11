# Alpha Stack — Model Selection & Access Architecture

> **Version:** 1.0 · **Date:** 2026-07-11  
> **Purpose:** Define how traders of every budget access AI models — from $0 to enterprise — optimized for forex/crypto trading workflows.

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Model Access Tiers](#2-model-access-tiers)
3. [Trading-Smart Model Catalog](#3-trading-smart-model-catalog)
4. [Strategy Step → Model Mapping](#4-strategy-step--model-mapping)
5. [User Configuration Flow](#5-user-configuration-flow)
6. [Model Fallback System](#6-model-fallback-system)
7. [Hybrid Local/Cloud Architecture](#7-hybrid-localcloud-architecture)
8. [Technical Implementation](#8-technical-implementation)
9. [API Key Management & Security](#9-api-key-management--security)
10. [Cost Estimation Engine](#10-cost-estimation-engine)

---

## 1. Design Philosophy

### Core Principles

1. **No trader left behind.** A user with $0 gets real value. A user with $200/mo gets proportionally more. Nobody is blocked.
2. **Trading-smart filtering.** We don't show every model on earth. We show only models that have been validated for financial/trading tasks.
3. **Graceful degradation.** If a paid API key expires or a local model is too slow, the system falls back — it never crashes or shows an error wall.
4. **Hybrid by default.** Small, fast tasks (sentiment, classification) run locally. Heavy reasoning tasks (fundamental analysis, multi-factor synthesis) run in the cloud. The user can override.
5. **Transparency.** Every model card shows: cost, latency estimate, quality tier, and what it's good at. No hidden tradeoffs.

### Who Is This For?

| Persona | Budget | Hardware | Goal |
|---------|--------|----------|------|
| **Broke Beginner** | $0 | 8 GB laptop | Learn, get signal ideas |
| **Side Hustler** | $5-20/mo | 16 GB desktop | Consistent daily analysis |
| **Serious Trader** | $20-100/mo | 32 GB + GPU | Edge with deep analysis |
| **Pro / Fund** | $100+/mo | 64 GB + multi-GPU | Full-stack reasoning |

---

## 2. Model Access Tiers

### Tier Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL ACCESS TIERS                           │
├──────────┬──────────────┬──────────────┬────────────┬──────────┤
│  FREE    │   BUDGET     │     PRO      │  PREMIUM   │  LOCAL   │
│  $0/mo   │  $5-20/mo    │  $20-100/mo  │  $100+/mo  │  RAM req │
├──────────┼──────────────┼──────────────┼────────────┼──────────┤
│ NIM Free │ GPT-4o-mini  │ GPT-4o       │ GPT-5      │ DS-R1    │
│ Gemini   │ Claude Haiku │ Claude Sonn. │ Claude Opus│ Qwen-2.5 │
│ HF Inf.  │ DeepSeek API │ Gemini Pro   │ o1 / o3    │ Llama 3  │
│ Ollama   │ Groq Free    │ Perplexity   │ Gemini Ult.│ Mistral  │
└──────────┴──────────────┴──────────────┴────────────┴──────────┘
```

### 2.1 Free Tier — $0/month

Zero cost. No credit card. No API key required (or free-tier key only).

| Provider | Model | Best For | Limits | Latency |
|----------|-------|----------|--------|---------|
| **NVIDIA NIM** | Various (Llama 3.1 70B, Mixtral) | General analysis, reasoning | 1K req/day free | 1-3s |
| **Google Gemini** | Gemini 2.0 Flash | Multi-modal (chart screenshots) | 15 req/min, 1M tok/day | 0.5-2s |
| **Hugging Face Inference** | Community models | Sentiment, classification | Rate-limited | 2-5s |
| **Ollama (local)** | DeepSeek-R1:8B, Llama 3.1:8B | Anything, runs offline | Hardware-bound | 1-10s |
| **Groq Free** | Llama 3.1 8B, Mixtral 8x7B | Fast inference, chat | 30 req/min | <1s |

**Free tier gives you:** Basic signal ideas, sentiment checks, simple chart interpretation. Not production-grade, but real and useful.

### 2.2 Budget Tier — $5-20/month

Small monthly spend. Serious quality jump over free.

| Provider | Model | $/1M tokens (in/out) | Best For |
|----------|-------|---------------------|----------|
| **OpenAI** | GPT-4o-mini | $0.15 / $0.60 | Daily analysis, fast reasoning |
| **Anthropic** | Claude 3.5 Haiku | $0.80 / $4.00 | Structured reports, careful analysis |
| **DeepSeek** | DeepSeek-V3 | $0.27 / $1.10 | Reasoning, math, multi-step logic |
| **Groq Paid** | Llama 3.1 70B | ~$0.59 / $0.79 | Ultra-fast batch processing |

**Budget tier gives you:** Daily multi-step analysis, reliable structured outputs, enough headroom for a full Alpha Stack run (~20-50 API calls/day).

### 2.3 Pro Tier — $20-100/month

Dedicated trading infrastructure. Best price/performance.

| Provider | Model | $/1M tokens (in/out) | Best For |
|----------|-------|---------------------|----------|
| **OpenAI** | GPT-4o | $2.50 / $10.00 | Complex multi-factor analysis |
| **Anthropic** | Claude Sonnet 4 | $3.00 / $15.00 | Deep reasoning, long context |
| **Google** | Gemini 2.5 Pro | $1.25 / $10.00 | 1M context window, chart analysis |
| **DeepSeek** | DeepSeek-R1 | $0.55 / $2.19 | Chain-of-thought reasoning |
| **Perplexity** | Sonar Pro | $3.00 / $15.00 | Real-time web + financial data |

**Pro tier gives you:** Full Alpha Stack pipeline, deep fundamental + technical synthesis, multi-model orchestration, chart image analysis.

### 2.4 Premium Tier — $100+/month

Maximum capability. Institutional-grade reasoning.

| Provider | Model | $/1M tokens (in/out) | Best For |
|----------|-------|---------------------|----------|
| **OpenAI** | GPT-5 / o3 | $10-30 (est.) | Frontier reasoning, complex strategy |
| **Anthropic** | Claude Opus 4 | $15.00 / $75.00 | Deep multi-step analysis |
| **Google** | Gemini 2.5 Ultra | TBD | Largest context, multi-modal |
| **OpenAI** | o1 / o3 | $15-60 | Mathematical reasoning, risk models |

**Premium tier gives you:** Best-in-class reasoning for position sizing, risk modeling, multi-timeframe synthesis, and complex scenario analysis.

### 2.5 Local Tier — RAM-Dependent

No API costs. Runs on user hardware. Latency depends on specs.

| Model | Min RAM | Recommended | VRAM (GPU) | Best For |
|-------|---------|-------------|------------|----------|
| **DeepSeek-R1:8B** | 8 GB | 16 GB | 6 GB | Reasoning, analysis |
| **DeepSeek-R1:70B** | 48 GB | 64 GB | 40 GB+ | Deep reasoning (Pro quality) |
| **Qwen-2.5:72B** | 48 GB | 64 GB | 40 GB+ | Multi-lingual, math |
| **Llama 3.1:8B** | 8 GB | 16 GB | 6 GB | General purpose |
| **Llama 3.1:70B** | 48 GB | 64 GB | 40 GB+ | High-quality reasoning |
| **Mistral 7B** | 8 GB | 16 GB | 6 GB | Fast, efficient |
| **FinBERT** | 2 GB | 4 GB | 2 GB | Financial sentiment |
| **FinGPT** | 4 GB | 8 GB | 4 GB | Financial analysis |

---

## 3. Trading-Smart Model Catalog

### Why Filter?

Showing "GPT-4o-mini" or "Llama 3.1 70B" without context is useless to a trader. We need to answer: **"Is this model good for MY trading task?"**

### Trading-Smart Tags

Every model in Alpha Stack gets tagged with trading capabilities:

```
┌─────────────────────────────────────────────────┐
│              TRADING CAPABILITY TAGS             │
├─────────────────────────────────────────────────┤
│ 📊 TECHNICAL   — Reads indicators, patterns     │
│ 📰 SENTIMENT   — News/social sentiment scoring  │
│ 🧮 QUANT       — Math, stats, risk formulas     │
│ 📖 FUNDAMENTAL — Economic data, macro reasoning │
│ 🖼️ CHART-VISION — Reads chart screenshots       │
│ ⚡ FAST         — Sub-second, batch-friendly     │
│ 🧠 REASONING   — Multi-step chain-of-thought    │
└─────────────────────────────────────────────────┘
```

### Model × Capability Matrix

| Model | TECH | SENT | QUANT | FUND | CHART | FAST | REASON | Tier |
|-------|------|------|-------|------|-------|------|--------|------|
| GPT-4o | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | Pro |
| GPT-4o-mini | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ⚠️ | Budget |
| Claude Sonnet 4 | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | Pro |
| Claude Haiku | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ⚠️ | Budget |
| DeepSeek-R1 | ✅ | ⚠️ | ✅ | ✅ | ❌ | ❌ | ✅ | Pro/Local |
| DeepSeek-V3 | ✅ | ✅ | ✅ | ✅ | ❌ | ⚠️ | ✅ | Budget |
| Gemini 2.0 Flash | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ⚠️ | Free |
| Gemini 2.5 Pro | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | Pro |
| Llama 3.1 8B | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | Free/Local |
| Llama 3.1 70B | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | ⚠️ | ✅ | Local |
| FinBERT | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | Local |
| Mistral 7B | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | Local |

**Legend:** ✅ Strong · ⚠️ Capable with caveats · ❌ Not recommended

---

## 4. Strategy Step → Model Mapping

### The Alpha Stack has 15 strategy steps. Each step has different model requirements.

### Step-to-Model Recommendation Engine

| Step | Task | Requirement | Free Pick | Budget Pick | Pro Pick | Local Pick |
|------|------|-------------|-----------|-------------|----------|------------|
| **1** Fundamental Analysis | Deep reasoning, macro data | 🧠 REASONING | DeepSeek-R1:8B | DeepSeek-V3 | Claude Sonnet 4 | DS-R1:70B |
| **2** Market Structure | Pattern recognition | 📊 TECHNICAL | Gemini Flash | GPT-4o-mini | GPT-4o | Llama 3.1:8B |
| **3** Supply/Demand Zones | Price action analysis | 📊 TECHNICAL | Gemini Flash | GPT-4o-mini | GPT-4o | Llama 3.1:8B |
| **4** Liquidity Mapping | Order flow reasoning | 🧠 REASONING | NIM (Llama 70B) | DeepSeek-V3 | Claude Sonnet 4 | DS-R1:70B |
| **5** Multi-TF Alignment | Cross-timeframe synthesis | 🧠 REASONING | NIM (Llama 70B) | DeepSeek-V3 | GPT-4o | DS-R1:70B |
| **6** Indicator Confluence | Technical scoring | 📊 TECHNICAL | Gemini Flash | GPT-4o-mini | GPT-4o | Llama 3.1:8B |
| **7** SMC Analysis | Smart Money Concepts | 📊 + 🧠 | NIM (Llama 70B) | DeepSeek-V3 | Claude Sonnet 4 | DS-R1:70B |
| **8** News/Sentiment | Real-time sentiment | 📰 SENTIMENT | FinBERT (local) | GPT-4o-mini | Perplexity | FinBERT |
| **9** Correlation | Multi-asset analysis | 🧮 QUANT | NIM (Llama 70B) | DeepSeek-V3 | GPT-4o | DS-R1:70B |
| **10** Session Timing | Time-based logic | 📊 TECHNICAL | Gemini Flash | GPT-4o-mini | GPT-4o | Llama 3.1:8B |
| **11** Position Sizing | Risk math, RL | 🧮 QUANT | Local RL model | Local RL model | Local RL model | Local RL |
| **12** Entry Triggers | Precise entry logic | 📊 + ⚡ | Gemini Flash | GPT-4o-mini | GPT-4o | Llama 3.1:8B |
| **13** Risk Management | Stop/TP calculation | 🧮 QUANT | Gemini Flash | DeepSeek-V3 | GPT-4o | DS-R1:8B |
| **14** Trade Journaling | Structured logging | 📊 TECHNICAL | Gemini Flash | Claude Haiku | Claude Sonnet | Llama 3.1:8B |
| **15** Review & Adapt | Performance analysis | 🧠 REASONING | NIM (Llama 70B) | DeepSeek-V3 | Claude Sonnet 4 | DS-R1:70B |

### Filtering Rules

When user opens model picker for a given step:

1. **Show only models tagged with the step's required capabilities**
2. **Sort by:** (a) user's tier, (b) quality score for that task, (c) latency
3. **Default selection:** Best model the user can afford
4. **Show "Why this model?"** tooltip explaining the recommendation

```typescript
interface ModelRecommendation {
  modelId: string;
  displayName: string;
  tier: 'free' | 'budget' | 'pro' | 'premium' | 'local';
  capabilities: TradingCapability[];
  qualityScore: number;       // 0-100, task-specific
  avgLatencyMs: number;
  costPerCall: number;        // $0 for free/local
  provider: string;
  reason: string;             // "Best reasoning model in your budget"
}

function getModelsForStep(
  step: AlphaStep,
  userTier: UserTier,
  userHardware: HardwareProfile
): ModelRecommendation[] {
  const required = STEP_CAPABILITY_MAP[step];
  const allModels = CATALOG.filter(m =>
    required.every(cap => m.capabilities.includes(cap))
  );
  return rankByValue(allModels, userTier, userHardware);
}
```

---

## 5. User Configuration Flow

### 5.1 First-Time Setup

```
┌─────────────────────────────────────────────────────────────┐
│                    SETTINGS → AI MODELS                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🔍 HARDWARE DETECTION                               │   │
│  │                                                      │   │
│  │  CPU: Apple M3 Pro (12 cores)                        │   │
│  │  RAM: 36 GB (28 GB available)                        │   │
│  │  GPU: Apple M3 Pro (18-core GPU, 18 GB unified)      │   │
│  │  Storage: 200 GB free                                │   │
│  │                                                      │   │
│  │  ✅ Detected: Can run models up to ~20B locally      │   │
│  │  📊 Recommended tier: BUDGET ($5-20/mo) + Local      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🎯 SELECT YOUR TIER                                 │   │
│  │                                                      │   │
│  │  ○ Free Only          — $0/mo, free endpoints        │   │
│  │  ● Budget + Local     — $5-20/mo + local models      │   │
│  │  ○ Pro + Local        — $20-100/mo + local models    │   │
│  │  ○ Premium            — $100+/mo, best everything    │   │
│  │  ○ Custom             — Pick individual models       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🔑 API KEYS                                         │   │
│  │                                                      │   │
│  │  OpenAI API Key:    [sk-••••••••] ✅ Valid           │   │
│  │  Anthropic API Key: [sk-ant-••••] ❌ Not set         │   │
│  │  DeepSeek API Key:  [•••••••••••] ✅ Valid           │   │
│  │  Google AI Key:     [AIza••••••]  ✅ Valid           │   │
│  │                                                      │   │
│  │  [+ Add API Key]  [🧪 Test All Keys]                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🏠 LOCAL MODELS (Ollama)                            │   │
│  │                                                      │   │
│  │  Installed:                                          │   │
│  │  ✅ deepseek-r1:8b      (5.2 GB)  — Ready           │   │
│  │  ✅ llama3.1:8b         (4.9 GB)  — Ready           │   │
│  │  ⏳ finbert             (0.4 GB)  — Downloading 67%  │   │
│  │                                                      │   │
│  │  Recommended for your hardware:                      │   │
│  │  📥 deepseek-r1:14b     (9.0 GB)  — Good fit        │   │
│  │  📥 qwen2.5:14b         (9.0 GB)  — Good fit        │   │
│  │                                                      │   │
│  │  [Browse Models]  [Install Recommended]              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ⚡ LATENCY TEST RESULTS                             │   │
│  │                                                      │   │
│  │  GPT-4o-mini .............. 320ms ✅ Fast             │   │
│  │  DeepSeek-V3 .............. 890ms ✅ OK               │   │
│  │  Gemini 2.0 Flash ......... 210ms ✅ Fast             │   │
│  │  deepseek-r1:8b (local) ... 2.1s  ⚠️ Slow            │   │
│  │  llama3.1:8b (local) ...... 680ms ✅ OK               │   │
│  │                                                      │   │
│  │  [Re-test]                                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│              [ Save Configuration ]                          │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Model Picker (Per Strategy Step)

When a user clicks the model selector for any Alpha Stack step:

```
┌─────────────────────────────────────────────────────────┐
│  Select Model for: Step 1 — Fundamental Analysis        │
│  Required: 🧠 REASONING · 📖 FUNDAMENTAL                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ⭐ RECOMMENDED                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │ DeepSeek-V3          Budget · $0.003/call         │  │
│  │ Quality: 88/100 · Latency: ~900ms                 │  │
│  │ "Best reasoning per dollar. Excellent at macro."  │  │
│  │                                          [SELECT] │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  OTHER OPTIONS                                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │ GPT-4o               Pro · $0.025/call            │  │
│  │ Quality: 94/100 · Latency: ~400ms                 │  │
│  │ "Highest quality. Multi-modal chart reading."     │  │
│  │                                          [SELECT] │  │
│  ├───────────────────────────────────────────────────┤  │
│  │ Claude Sonnet 4      Pro · $0.018/call            │  │
│  │ Quality: 92/100 · Latency: ~500ms                 │  │
│  │ "Excellent structured analysis. Careful reasoning."│  │
│  │                                          [SELECT] │  │
│  ├───────────────────────────────────────────────────┤  │
│  │ deepseek-r1:8b       Local · $0.00/call           │  │
│  │ Quality: 62/100 · Latency: ~2.1s                  │  │
│  │ "Free, offline. Reasonable for basic analysis."   │  │
│  │                                          [SELECT] │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  🔒 UPGRADE OPTIONS                                      │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Claude Opus 4        Premium · $0.09/call         │  │
│  │ Quality: 98/100 · Latency: ~800ms                 │  │
│  │ "Frontier reasoning. Requires Pro+ tier."         │  │
│  │                                    [UPGRADE TIER] │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  [x] Remember this choice for all Fundamental steps     │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Model Fallback System

### 6.1 Fallback Chain

Every model has a defined fallback chain. When the primary fails, the system silently degrades — never crashes.

```
Primary Model Fails
        │
        ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ Retry (1x, 2s)   │────▶│ Fallback Model    │────▶│ Free Endpoint     │
│ with backoff      │     │ (same tier, diff  │     │ (NIM/Gemini/      │
│                   │     │  provider)        │     │  Ollama local)    │
└──────────────────┘     └──────────────────┘     └──────────────────┘
        │                        │                        │
        ▼                        ▼                        ▼
    Success?                 Success?                 Success?
    → Continue               → Continue               → Continue
        │                        │                        │
        ▼                        ▼                        ▼
    Log warning              Log warning              Log: "Using degraded
    about latency            about fallback            model. Results may
                                                     be lower quality."
```

### 6.2 Fallback Rules by Tier

| User Tier | Primary | Fallback 1 | Fallback 2 | Fallback 3 |
|-----------|---------|------------|------------|------------|
| Free | Gemini Flash | NIM Free | Ollama local | Cached result |
| Budget | GPT-4o-mini | DeepSeek-V3 | Gemini Flash | Ollama local |
| Pro | GPT-4o | Claude Sonnet | Gemini Pro | DeepSeek-V3 |
| Premium | GPT-5 / o3 | Claude Opus | GPT-4o | Claude Sonnet |
| Local | Ollama primary | Ollama secondary | Gemini Flash | Cached result |

### 6.3 Degradation Signals (User-Facing)

```typescript
interface DegradationNotice {
  type: 'warning' | 'info';
  message: string;
  action?: string;  // "Upgrade API key" or "Install larger model"
}

// Examples:
{
  type: 'warning',
  message: 'GPT-4o API key expired. Using GPT-4o-mini (lower quality).',
  action: 'Update API key in Settings → AI Models'
}
{
  type: 'info',
  message: 'Local model running slow (4.2s). Consider cloud alternative.',
  action: 'Switch to DeepSeek-V3 ($0.003/call)'
}
```

### 6.4 Health Monitoring

```typescript
interface ModelHealth {
  modelId: string;
  status: 'healthy' | 'degraded' | 'down';
  lastSuccess: timestamp;
  lastFailure: timestamp;
  failureCount: number;
  avgLatencyMs: number;
  consecutiveFailures: number;
}

// Auto-disable after 5 consecutive failures
// Auto-re-enable after 10 minutes
// Alert user if all models in a tier fail
```

---

## 7. Hybrid Local/Cloud Architecture

### 7.1 Design: Right Model for Right Task

```
┌─────────────────────────────────────────────────────────────┐
│                    HYBRID ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  LOCAL (User's Machine)          CLOUD (API)                │
│  ┌─────────────────────┐        ┌─────────────────────┐    │
│  │                     │        │                     │    │
│  │  📰 FinBERT         │        │  🧠 GPT-4o           │    │
│  │  Sentiment scoring  │        │  Fundamental analysis│    │
│  │  (fast, free)       │        │  (deep reasoning)    │    │
│  │                     │        │                     │    │
│  │  📊 Llama 3.1:8B   │        │  📊 Claude Sonnet    │    │
│  │  Pattern recognition│        │  Multi-TF synthesis  │    │
│  │  (fast, free)       │        │  (context window)    │    │
│  │                     │        │                     │    │
│  │  🧮 RL Position     │        │  🖼️ GPT-4o Vision    │    │
│  │  Sizing model       │        │  Chart screenshot    │    │
│  │  (lightweight)      │        │  analysis            │    │
│  │                     │        │                     │    │
│  │  ⚡ Fast inference   │        │  🧮 DeepSeek-R1      │    │
│  │  for real-time      │        │  Complex math/risk   │    │
│  │  entry triggers     │        │  modeling            │    │
│  │                     │        │                     │    │
│  └─────────────────────┘        └─────────────────────┘    │
│           │                              │                  │
│           └──────────┬───────────────────┘                  │
│                      ▼                                      │
│            ┌─────────────────┐                              │
│            │  ORCHESTRATOR    │                              │
│            │  (Alpha Stack)   │                              │
│            │                  │                              │
│            │  Routes each     │                              │
│            │  step to the     │                              │
│            │  optimal model   │                              │
│            └─────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Default Routing Rules

| Task Type | Default Location | Reason |
|-----------|-----------------|--------|
| Sentiment analysis | **Local** (FinBERT) | Fast, free, specialized |
| Position sizing (RL) | **Local** | Lightweight, no API cost |
| Pattern recognition | **Local** if 8B+ available, else **Cloud** | Fast enough locally |
| Fundamental analysis | **Cloud** | Needs deep reasoning + large context |
| Chart image analysis | **Cloud** (vision models) | Multi-modal required |
| Multi-TF synthesis | **Cloud** | Large context window needed |
| Risk calculations | **Local** if model available, else **Cloud** | Math-heavy |
| Real-time entry triggers | **Local** | Speed-critical (<500ms) |

### 7.3 User Override

Users can always override the default routing:

```
Settings → AI Models → Routing

Step 8 (News/Sentiment):
  [●] Auto (FinBERT local → GPT-4o-mini cloud)
  [ ] Always local
  [ ] Always cloud: [GPT-4o-mini ▼]

Step 1 (Fundamental):
  [●] Auto (best available)
  [ ] Always local: [deepseek-r1:14b ▼]
  [ ] Always cloud: [Claude Sonnet 4 ▼]
```

---

## 8. Technical Implementation

### 8.1 Unified Model Interface

```typescript
// All models — cloud or local — expose the same interface
interface AlphaModel {
  id: string;
  displayName: string;
  tier: ModelTier;
  provider: 'openai' | 'anthropic' | 'google' | 'deepseek' | 'ollama' | 'nvidia' | 'huggingface';
  capabilities: TradingCapability[];
  tradingQualityScores: Record<AlphaStep, number>;  // 0-100
  pricing: {
    inputPer1M: number;   // $0 for local/free
    outputPer1M: number;
    avgCostPerCall: number;
  };
  limits: {
    maxContextTokens: number;
    maxOutputTokens: number;
    rateLimit: number;  // requests per minute
  };
  latency: {
    p50Ms: number;
    p95Ms: number;
  };
  requiresApiKey: boolean;
  requiresLocalInstall: boolean;
  minRamGb: number;
  minVramGb: number;
  fallbackChain: string[];  // model IDs
}
```

### 8.2 Model Router

```typescript
class ModelRouter {
  async executeForStep(
    step: AlphaStep,
    prompt: string,
    context: TradeContext
  ): Promise<ModelResponse> {
    const userConfig = await this.getUserConfig();
    const recommended = this.getRecommendedModels(step, userConfig);
    
    for (const model of recommended) {
      try {
        const result = await this.callWithTimeout(model, prompt, context);
        this.healthMonitor.recordSuccess(model.id);
        return result;
      } catch (error) {
        this.healthMonitor.recordFailure(model.id, error);
        this.notifyDegradation(model, recommended);
        continue;  // try next fallback
      }
    }
    
    // Last resort: cached result or error
    return this.getLastResort(step, context);
  }

  private getRecommendedModels(
    step: AlphaStep,
    config: UserConfig
  ): AlphaModel[] {
    const required = STEP_CAPABILITY_MAP[step];
    return CATALOG
      .filter(m => this.isAvailable(m, config))
      .filter(m => required.every(cap => m.capabilities.includes(cap)))
      .sort((a, b) => this.scoreForStep(b, step) - this.scoreForStep(a, step));
  }
}
```

### 8.3 Hardware Detection

```typescript
async function detectHardware(): Promise<HardwareProfile> {
  const cpu = await getCPUInfo();          // cores, arch, speed
  const ram = await getMemoryInfo();       // total, available GB
  const gpu = await getGPUInfo();          // VRAM, CUDA/Metal support
  const storage = await getDiskSpace();    // free GB
  const ollamaInstalled = await checkOllama();
  const installedModels = ollamaInstalled
    ? await listOllamaModels()
    : [];

  return {
    cpu, ram, gpu, storage,
    ollamaInstalled,
    installedModels,
    maxLocalModelSize: calculateMaxModelSize(ram, gpu),
    recommendedTier: calculateRecommendedTier(ram, gpu),
  };
}
```

---

## 9. API Key Management & Security

### 9.1 Storage

- API keys stored in OS keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service)
- **Never** in plaintext config files
- Keys encrypted at rest with machine-specific key

### 9.2 Validation Flow

```
User enters API key
       │
       ▼
┌──────────────────┐
│ Format check      │  sk-*, sk-ant-*, AIza*, etc.
│ (regex)           │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Ping test         │  Send minimal request to /models
│ (1 request)       │  or /v1/models endpoint
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Quota check       │  Check remaining credits/quota
│ (if available)    │  via provider API
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Latency test      │  Send small prompt, measure ms
│ (benchmark)       │  Store p50/p95 for routing
└────────┬─────────┘
         ▼
    ✅ Key valid
    Store securely
    Show in UI
```

### 9.3 Key Rotation

- Prompt user to re-validate keys every 90 days
- Auto-detect expired keys via failed requests
- Never expose key in UI — show only last 4 chars

---

## 10. Cost Estimation Engine

### 10.1 Per-Run Cost Calculator

```typescript
function estimateRunCost(
  steps: AlphaStep[],
  models: Map<AlphaStep, AlphaModel>
): CostEstimate {
  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  let totalCost = 0;

  for (const step of steps) {
    const model = models.get(step)!;
    const est = STEP_TOKEN_ESTIMATES[step];  // avg tokens per step
    
    totalInputTokens += est.inputTokens;
    totalOutputTokens += est.outputTokens;
    
    if (model.tier !== 'free' && model.tier !== 'local') {
      totalCost += (est.inputTokens / 1_000_000) * model.pricing.inputPer1M;
      totalCost += (est.outputTokens / 1_000_000) * model.pricing.outputPer1M;
    }
  }

  return {
    totalInputTokens,
    totalOutputTokens,
    estimatedCost: totalCost,
    estimatedLatencyMs: steps.reduce((sum, s) =>
      sum + (models.get(s)?.latency.p50Ms ?? 0), 0),
  };
}
```

### 10.2 Monthly Budget Tracker

```
┌─────────────────────────────────────────────┐
│  💰 JULY 2026 — AI MODEL COSTS              │
├─────────────────────────────────────────────┤
│                                             │
│  Budget: $20.00/mo                          │
│  Spent:  $7.43 (37%)                        │
│  Remaining: $12.57                          │
│  ████████████░░░░░░░░░░░░░  37%            │
│                                             │
│  Breakdown by model:                        │
│  GPT-4o-mini .... $4.21  (58 calls)        │
│  DeepSeek-V3 .... $2.08  (31 calls)        │
│  Gemini Flash ... $0.00  (free, 42 calls)  │
│  FinBERT local .. $0.00  (free, 89 calls)  │
│  Llama 3.1:8B ... $0.00  (free, 23 calls)  │
│  Claude Haiku ... $1.14  (8 calls)         │
│                                             │
│  ⚠️ At current rate: ~$18.50 by month end   │
│  ✅ Within budget                           │
│                                             │
│  [View Details] [Set Budget Alert]          │
└─────────────────────────────────────────────┘
```

### 10.3 Cost Optimization Hints

The system proactively suggests savings:

- **"You're using GPT-4o for Step 10 (Session Timing). GPT-4o-mini gives 95% of the quality at 6% of the cost. Switch?"**
- **"You ran sentiment analysis 89 times this month on GPT-4o. FinBERT local gives equivalent results for $0. Install?"**
- **"Your DeepSeek-R1:8B is being used for Steps 2, 3, 6 — pattern tasks. A 70B model would improve quality by ~20%. Worth the 48GB RAM?"**

---

## Appendix A: Supported Providers Quick Reference

| Provider | Free Tier | Paid Tier | Auth Method | Base URL |
|----------|-----------|-----------|-------------|----------|
| OpenAI | ❌ | GPT-4o-mini, GPT-4o, o1, o3, GPT-5 | API Key | `api.openai.com` |
| Anthropic | ❌ | Haiku, Sonnet, Opus | API Key | `api.anthropic.com` |
| Google | ✅ 15 rpm | Gemini Pro, Ultra | API Key | `generativelanguage.googleapis.com` |
| DeepSeek | ✅ $0.50 credit | V3, R1 | API Key | `api.deepseek.com` |
| NVIDIA NIM | ✅ 1K/day | Higher limits | API Key | `integrate.api.nvidia.com` |
| Groq | ✅ 30 rpm | Higher limits | API Key | `api.groq.com` |
| Ollama | ✅ Unlimited | N/A | Local | `localhost:11434` |
| HuggingFace | ✅ Rate-limited | Inference Endpoints | Token | `api-inference.huggingface.co` |

## Appendix B: Token Budget per Alpha Step

| Step | Avg Input Tokens | Avg Output Tokens | Total/Run |
|------|-----------------|-------------------|-----------|
| 1 Fundamental | 3,000 | 1,500 | 4,500 |
| 2 Market Structure | 2,000 | 800 | 2,800 |
| 3 Supply/Demand | 2,000 | 800 | 2,800 |
| 4 Liquidity | 2,500 | 1,000 | 3,500 |
| 5 Multi-TF | 4,000 | 1,500 | 5,500 |
| 6 Indicators | 1,500 | 600 | 2,100 |
| 7 SMC | 3,000 | 1,200 | 4,200 |
| 8 Sentiment | 1,000 | 400 | 1,400 |
| 9 Correlation | 2,000 | 800 | 2,800 |
| 10 Timing | 1,000 | 400 | 1,400 |
| 11 Sizing | 1,500 | 600 | 2,100 |
| 12 Entry | 1,500 | 500 | 2,000 |
| 13 Risk | 2,000 | 800 | 2,800 |
| 14 Journal | 1,000 | 500 | 1,500 |
| 15 Review | 3,000 | 1,500 | 4,500 |
| **Total** | **31,000** | **12,900** | **43,900** |

**Estimated cost per full Alpha Stack run:**

| Tier | Model Mix | Cost/Run | Runs/Day for $20/mo |
|------|-----------|----------|---------------------|
| Free | All free | $0.00 | ∞ |
| Budget | GPT-4o-mini + DeepSeek | ~$0.007 | ~95 |
| Pro | GPT-4o + Claude Sonnet | ~$0.12 | ~5.5 |
| Premium | GPT-5 + Opus | ~$0.50 | ~1.3 |

---

*Architecture designed for Alpha Stack v1.0. Review quarterly as model pricing and capabilities evolve.*
