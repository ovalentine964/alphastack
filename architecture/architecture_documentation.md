# Alpha Stack — Documentation Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Documentation Architect Agent
> **Scope:** Complete documentation system design — structure, content, tooling, versioning, CI/CD, and maintenance
> **Design Philosophy:** Documentation is a product, not an afterthought. Every doc has an owner, an audience, and an expiry review.

---

## Table of Contents

1. [Documentation Philosophy](#1-documentation-philosophy)
2. [Information Architecture](#2-information-architecture)
3. [User Documentation](#3-user-documentation)
4. [Developer Documentation](#4-developer-documentation)
5. [Strategy Documentation](#5-strategy-documentation)
6. [API Documentation](#6-api-documentation)
7. [Deployment Documentation](#7-deployment-documentation)
8. [Troubleshooting Guides](#8-troubleshooting-guides)
9. [Community Documentation](#9-community-documentation)
10. [Documentation Generation & Tooling](#10-documentation-generation--tooling)
11. [Documentation Versioning](#11-documentation-versioning)
12. [Documentation CI/CD](#12-documentation-cicd)
13. [Maintenance & Governance](#13-maintenance--governance)
14. [Metrics & Quality Gates](#14-metrics--quality-gates)
15. [Implementation Roadmap](#15-implementation-roadmap)

---

## 1. Documentation Philosophy

### 1.1 Core Principles

| Principle | Description | Rationale |
|-----------|-------------|-----------|
| **Docs-as-Code** | Documentation lives in the same repository as code, reviewed in the same PR workflow | If docs aren't in the PR, they don't get written |
| **Audience-First** | Every page declares its target audience at the top | A beginner and an API consumer need different language |
| **Progressive Disclosure** | Start simple, link to deep dives | Don't dump 500 lines of config on a first-time user |
| **Executable Examples** | Code samples are tested in CI, not hand-written fiction | Broken examples destroy trust faster than no examples |
| **Single Source of Truth** | Each fact lives in exactly one place; everything else links to it | Contradictory docs are worse than no docs |
| **Expiry Dates** | Every doc has a `last_reviewed` date; stale docs get flagged | Alpha Stack moves fast — 6-month-old docs are lies |

### 1.2 Documentation Taxonomy

```
docs/
├── user/                    # For traders & end users
│   ├── getting-started/     # Installation, first trade
│   ├── guides/              # Step-by-step workflows
│   ├── configuration/       # Every config option explained
│   └── reference/           # Keyboard shortcuts, signal types
│
├── developer/               # For contributors & integrators
│   ├── architecture/        # System design (generated from arch reports)
│   ├── api-reference/       # Auto-generated from OpenAPI/protobuf
│   ├── contributing/        # How to contribute
│   └── internals/           # Deep dives into subsystems
│
├── strategy/                # For traders who want to understand the AI
│   ├── overview/            # VMPM philosophy, what alpha means
│   ├── steps/               # Each of the 16 steps, detailed
│   ├── pairs/               # Pair-specific behavior
│   └── backtesting/         # How to validate strategies
│
├── api/                     # For API consumers
│   ├── rest/                # REST endpoints
│   ├── websocket/           # WebSocket protocol
│   ├── cli/                 # CLI reference
│   └── sdks/                # Client libraries
│
├── deployment/              # For operators & DevOps
│   ├── quickstart/          # Docker Compose in 5 minutes
│   ├── production/          # VPS, cloud, K8s hardening
│   ├── monitoring/          # Prometheus, Grafana, alerting
│   └── security/            # Hardening checklist
│
├── troubleshooting/         # For everyone
│   ├── common/              # Top 20 issues
│   ├── broker/              # Broker-specific problems
│   └── error-codes/         # Every error code explained
│
├── community/               # For the community
│   ├── faq/                 # Frequently asked questions
│   ├── best-practices/      # Community wisdom
│   └── glossary/            # Trading + technical terms
│
└── adr/                     # Architecture Decision Records
    └── template.md          # ADR template
```

### 1.3 Document Template Standard

Every document follows this frontmatter:

```yaml
---
title: "Document Title"
audience: [user | developer | operator | contributor]
difficulty: [beginner | intermediate | advanced]
last_reviewed: 2026-07-11
review_cycle: [monthly | quarterly | on-release]
owner: "@username"
related: ["path/to/related-doc.md"]
tags: [setup, trading, api, risk, ...]
---
```

---

## 2. Information Architecture

### 2.1 Navigation Structure

The documentation site uses a **four-axis navigation** model:

| Axis | Purpose | Example |
|------|---------|---------|
| **By Role** | What are you? | Trader → User Docs; Developer → Dev Docs |
| **By Task** | What do you want to do? | "Install Alpha Stack" → Quick Start |
| **By Component** | Which system? | Risk Engine → Risk Architecture |
| **By Search** | Free-form | Full-text search across all docs |

### 2.2 User Journey Maps

#### Journey 1: New Trader (Day 1 → Day 30)

```
Day 1:  Landing Page → What is Alpha Stack? → Quick Start (Docker)
        → First Signal Received → "What does this mean?" → Signal Explainer
Day 3:  Configuration Guide → Set Risk Tolerance → Connect Broker
        → First Live Trade → Trade Journal Entry
Day 7:  Strategy Overview → Understanding VMPM → Why Did I Get This Signal?
Day 14: Pair-Specific Guides → Adjust Parameters → Backtest My Config
Day 30: Advanced Config → Multi-Pair Setup → Performance Review
```

#### Journey 2: Developer (Contributing)

```
Hour 1:  Contributing Guide → Dev Setup → Architecture Overview
Hour 4:  Pick an Issue → Module Interface → Write a Test → Submit PR
Day 3:   Internals Deep Dive → Event Bus → Agent Orchestration
Week 2:  Strategy Step Development → Custom Indicator → Backtest Integration
```

#### Journey 3: API Consumer

```
Minute 5:  API Quick Start → Authentication → First API Call
Hour 1:    REST Reference → WebSocket Protocol → Stream Market Data
Day 1:     Build a Dashboard → Subscribe to Signals → Place Orders
Week 1:    SDK Usage → Error Handling → Rate Limit Management
```

### 2.3 Cross-Reference Matrix

| From → To | User Guide | Dev Guide | Strategy | API | Deployment | Troubleshooting |
|-----------|:----------:|:---------:|:--------:|:---:|:----------:|:---------------:|
| **User Guide** | — | → internals | → VMPM overview | → CLI ref | → quickstart | → common issues |
| **Dev Guide** | → config ref | — | → step interfaces | → OpenAPI | → dev env | → error codes |
| **Strategy** | → signal guide | → module API | — | → signal events | — | → backtest issues |
| **API** | → auth setup | → SDK source | → signal schema | — | → API deploy | → rate limits |
| **Deployment** | → first run | → build from src | — | → health API | — | → monitoring |
| **Troubleshooting** | → config fixes | → debug mode | → parameter tuning | → error codes | → log analysis | — |

---

## 3. User Documentation

### 3.1 Getting Started

#### `user/getting-started/index.md`

**Audience:** Complete beginners. No trading experience assumed.

**Content outline:**

```markdown
# Welcome to Alpha Stack

## What is Alpha Stack?
- One-paragraph plain-English explanation
- "It's an AI that watches the markets 24/7 and tells you when there's an opportunity"
- What it is NOT (not a guaranteed money printer, not a gambling bot)

## How It Works (30-Second Version)
- Markets → AI Analysis → Signal → You Decide → Trade
- Diagram: Simple 4-box flow

## Your First 15 Minutes
1. Install (pick your platform)
2. Open the dashboard
3. Watch your first signal arrive
4. Understand what you're looking at

## What You Need
- A computer (specs table by tier)
- An internet connection
- A broker account (or start with paper trading)
- $7 minimum (or $0 for paper trading)

## What You DON'T Need
- Programming knowledge
- Trading experience
- Expensive hardware
- A large account
```

#### `user/getting-started/installation.md`

**Content outline:**

```markdown
# Installation Guide

## Choose Your Path
| Method | Time | Difficulty | Best For |
|--------|------|------------|----------|
| Docker Compose | 5 min | Easy | Everyone (recommended) |
| Native Install | 20 min | Medium | Developers, custom setups |
| Cloud Deploy | 15 min | Medium | Always-on trading |

## Docker Compose (Recommended)
### Prerequisites
- Docker 24+ and Docker Compose v2
- 4 GB RAM minimum, 8 GB recommended

### Step 1: Clone the Repository
```bash
git clone https://github.com/alphastack/alphastack.git
cd alphastack
```

### Step 2: Configure
```bash
cp .env.example .env
# Edit .env with your broker credentials
```

### Step 3: Launch
```bash
docker compose up -d
```

### Step 4: Verify
- Open http://localhost:3000
- Check dashboard shows "Connected"
- Verify data feed is receiving prices

## Native Installation
### Python Environment
[Detailed steps for Python 3.11+, venv, pip install]

### Rust Components (Optional Performance)
[PyO3 bindings compilation]

### Frontend (Development Mode)
[pnpm install, dev server]

## Cloud Deployment (Quick)
[Links to deployment docs for Hetzner, AWS, GCP]

## Next Steps
→ [Configuration Guide](../configuration/index.md)
→ [Your First Trade](../guides/first-trade.md)
```

#### `user/getting-started/first-trade.md`

**Content outline:**

```markdown
# Your First Trade

## Before You Start
- Have Alpha Stack running (installation guide)
- Have a broker account OR enable paper trading

## Understanding the Dashboard
[Screenshot with annotations]
- Signal panel: what the AI is seeing
- P&L panel: your performance
- Trade panel: open and closed positions

## Watching a Signal Arrive
1. Open the dashboard
2. Watch the "Live Signals" panel
3. When a signal arrives, read the reasoning
4. Notice the confidence score and grade (A+, A, B, C)

## Taking Your First Trade
### Option A: Manual Mode (Recommended for Beginners)
1. Signal arrives → Review the reasoning
2. Click "Accept" to set up the trade
3. Review the suggested entry, SL, TP
4. Click "Execute" to place the order

### Option B: Semi-Auto Mode
1. Configure auto-accept for A+ signals only
2. System places the trade, notifies you
3. You can override or close at any time

## After Your First Trade
- Check the Trade Journal entry
- Understand why the system made this decision
- Review the risk parameters that were applied

## Common First-Trade Questions
- "Why was my position so small?" → Risk management is conservative by default
- "Why did it suggest EUR/USD and not BTC?" → The AI picks the best opportunity
- "Can I lose more than I deposited?" → No. Stop losses protect you.
```

### 3.2 Configuration Guide

#### `user/configuration/index.md`

```markdown
# Configuration Guide

## Configuration Hierarchy
Alpha Stack uses a layered configuration system:

1. **Defaults** → Built-in safe defaults
2. **Config File** → `config/alphastack.yaml`
3. **Environment Variables** → `.env` file
4. **Runtime Overrides** → CLI flags, dashboard settings
5. **Per-Pair Overrides** → Pair-specific YAML files

Later layers override earlier ones.

## Quick Configuration
The minimum you need to change:
```yaml
# config/alphastack.yaml
broker:
  type: "mt5"           # or "ccxt" for crypto
  server: "FXPesa-Demo"
  login: YOUR_LOGIN
  # password stored in OS keyring, not here

risk:
  max_risk_per_trade: 1.0  # percent of account
  max_daily_loss: 3.0       # percent of account

trading:
  pairs: ["EUR/USD", "GBP/USD"]
  mode: "paper"  # change to "live" when ready
```

## Full Configuration Reference
[Auto-generated from config schema — every field, every type, every default]

## Configuration by Persona
### The Cautious Beginner
[Conservative settings, paper trading, manual approval]

### The Active Trader
[Semi-auto mode, multiple pairs, moderate risk]

### The Systematic Fund
[Full automation, max pairs, institutional risk parameters]
```

### 3.3 Trading Guide

#### `user/guides/trading-guide.md`

```markdown
# The Alpha Stack Trading Guide

## How Trading Works in Alpha Stack

### The Signal Lifecycle
```
Market Data → AI Analysis (16 steps) → Signal Generated → Risk Check
→ Notification Sent → You Review → Trade Executed → Monitored → Closed
```

### Signal Anatomy
Every signal contains:
- **Pair:** Which instrument (EUR/USD, BTC/USD, etc.)
- **Direction:** BUY or SELL
- **Entry Price:** Suggested entry level
- **Stop Loss:** Maximum loss point (ALWAYS present)
- **Take Profit:** Target levels (1-3 targets)
- **Confidence:** 0-100% — how sure the AI is
- **Grade:** A+ (highest conviction) through C (speculative)
- **Reasoning:** Plain-English explanation of WHY

### Understanding Signal Grades
| Grade | Confidence | Risk Allowed | Recommendation |
|-------|-----------|-------------|----------------|
| A+ | 85-100% | Full position | Auto-accept if enabled |
| A | 70-84% | Full position | Strong opportunity |
| B | 55-69% | Half position | Decent setup, verify manually |
| C | 40-54% | Quarter position | Speculative, use caution |

### Position Sizing
The system calculates position size based on:
1. Your account balance
2. Your configured risk per trade (default: 1%)
3. The distance to stop loss
4. Current volatility (ATR)
5. Correlation with open positions

**Example:** $1,000 account, 1% risk, 50-pip stop = 0.20 lot EUR/USD

### Managing Open Trades
- **Modify:** Adjust SL/TP via dashboard or chat command
- **Close:** Close manually at any time
- **Partial Close:** Take partial profits at TP1
- **Override:** The AI suggests; you decide

### The Trade Journal
Every trade gets an automatic journal entry:
- Entry/exit prices and times
- Signal reasoning chain
- Risk parameters applied
- P&L calculation
- Screenshot of chart at entry
- Post-trade analysis (added after close)
```

### 3.4 User Reference

#### `user/reference/signal-types.md`
- Every signal type the system can generate
- What each signal means in plain English
- Visual examples with chart screenshots

#### `user/reference/keyboard-shortcuts.md`
- Full keyboard shortcut reference for desktop app
- Organized by function (navigation, trading, analysis)

#### `user/reference/chat-commands.md`
- All Telegram/Discord/WhatsApp commands
- Command syntax with examples
- Permission levels

#### `user/reference/error-messages.md`
- Every user-facing error message
- What it means
- What to do about it

---

## 4. Developer Documentation

### 4.1 Architecture Overview

#### `developer/architecture/index.md`

**Source:** Auto-extracted from `architecture_system.md` with diagrams rendered.

```markdown
# Alpha Stack Architecture

## System Overview
Alpha Stack is a hybrid event-driven, multi-agent, pipeline architecture.

[Rendered system diagram from architecture_system.md]

## The Seven Layers
| Layer | Name | Key Technologies |
|-------|------|------------------|
| L0 | Infrastructure | Docker, Prometheus, Grafana |
| L1 | Data Foundation | TimescaleDB, Redis, ClickHouse |
| L2 | Execution & Broker | MT5, CCXT, ZeroMQ |
| L3 | Strategy & Analysis | VMPM Pipeline, PyTorch, Rust |
| L4 | Orchestration | LangGraph, Redis Streams |
| L5 | API Gateway | FastAPI, WebSocket, gRPC |
| L6 | Presentation | Tauri, React, Flutter |

## Key Architectural Decisions
→ See [ADR-001: Event-Driven Architecture](../adr/001-event-driven.md)
→ See [ADR-002: Strategy as Data](../adr/002-strategy-as-data.md)
→ See [ADR-003: Multi-Agent Orchestration](../adr/003-multi-agent.md)

## Module Map
[Interactive module dependency graph]
```

#### `developer/architecture/event-system.md`

```markdown
# Event System

## Event Bus Architecture
All inter-module communication uses Redis Streams.

## Event Types
| Stream | Producer | Consumers | Schema |
|--------|----------|-----------|--------|
| market.tick | Data Pipeline | All strategy steps | MarketEvent |
| signal.* | Strategy Steps | Confluence Engine | SignalEvent |
| risk.* | Risk Governor | All modules | RiskEvent |
| order.* | Execution Engine | Journal, Monitor | TradeOrder |
| agent.* | All Agents | Orchestrator | AgentEvent |

## Event Schema Reference
[Auto-generated from Pydantic models]

## Adding a New Event Type
1. Define the schema in `core/events/schemas.py`
2. Register the stream in `core/events/registry.py`
3. Add consumers in relevant modules
4. Update this document
```

### 4.2 Contributing Guide

#### `developer/contributing/index.md`

```markdown
# Contributing to Alpha Stack

## Welcome!
Alpha Stack is open-source and contributions are welcome.

## Getting Started
### 1. Fork & Clone
```bash
git clone https://github.com/YOUR_USERNAME/alphastack.git
cd alphastack
git remote add upstream https://github.com/alphastack/alphastack.git
```

### 2. Set Up Development Environment
```bash
# Python environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Pre-commit hooks
pre-commit install

# Verify
make test
make lint
```

### 3. Pick an Issue
- Look for `good first issue` label
- Comment on the issue to claim it
- Ask questions — we're friendly

## Code Standards
### Python
- Python 3.11+, type hints everywhere
- Ruff for linting, Black for formatting
- 100% type coverage on public APIs
- Docstrings: Google style

### Rust
- `cargo fmt` + `cargo clippy` (zero warnings)
- Public functions documented

### TypeScript/React
- ESLint + Prettier
- Functional components only
- Zustand for state management

## Pull Request Process
1. Create a feature branch from `main`
2. Write code + tests
3. Ensure `make check` passes
4. Update relevant documentation
5. Submit PR with description
6. Address review comments
7. Squash-merge

## Architecture Decision Records
Significant design decisions require an ADR:
→ See [ADR Template](../adr/template.md)

## Code of Conduct
→ See [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md)
```

### 4.3 Module Internals

#### `developer/internals/vmpm-pipeline.md`

```markdown
# VMPM Pipeline Internals

## Pipeline Architecture
The 16-step pipeline is a directed acyclic graph (DAG) with conditional branching.

## Module Interface
```python
class StrategyModule(ABC):
    async def initialize(self, config: dict) -> None: ...
    async def process(self, event: MarketEvent | SignalEvent) -> list[SignalEvent]: ...
    async def get_state(self) -> dict: ...
    async def shutdown(self) -> None: ...
```

## Adding a New Strategy Step
1. Create `core/vmpm/steps/S17_your_module.py`
2. Implement `StrategyModule` interface
3. Register in `core/vmpm/pipeline.yaml`
4. Add unit tests in `tests/steps/test_s17.py`
5. Update strategy documentation

## Pipeline Configuration
[YAML schema for pipeline.yaml with all options]
```

#### `developer/internals/multi-agent.md`
- Agent orchestration architecture (LangGraph)
- Agent communication protocol
- Adding a new agent
- Agent state management

#### `developer/internals/risk-engine.md`
- Risk governor internals
- Position sizing algorithms
- Circuit breaker logic
- Adding custom risk rules

#### `developer/internals/broker-connector.md`
- BrokerConnector interface
- Implementing a new broker connector
- Order routing logic
- Fill tracking and reconciliation

---

## 5. Strategy Documentation

### 5.1 Strategy Overview

#### `strategy/overview/index.md`

```markdown
# The Alpha Strategy

## What is Alpha?
Alpha (α) is excess return — the return above what the market gives you for free.
Alpha Stack's job is to find, capture, and compound alpha.

## The VMPM Philosophy
VMPM = Volatility-Modified Propulsion Model
- **Volatility-Modified:** Position sizes and targets adapt to current volatility
- **Propulsion:** Price moves in bursts; we catch the bursts
- **Model:** Systematic, rules-based, AI-enhanced — not guessing

## Why 16 Steps?
Each step is a filter. The more filters a trade passes, the higher the probability.

| Phase | Steps | Purpose |
|-------|-------|---------|
| Perception | 1-3 | See the market clearly |
| Regime | 4-5 | Know what game we're playing |
| Signal | 6-8 | Find the opportunity |
| Verification | 9-10 | Is this real or noise? |
| Risk | 11-12 | How much can we risk? |
| Execution | 13-14 | Get in cleanly |
| Review | 15-16 | Learn and improve |

## The Edge
Most retail traders fail because they:
1. Trade on emotion → We don't have emotions
2. Use fixed parameters → We adapt to volatility
3. Don't backtest → We test everything
4. Over-leverage → We have hard risk limits
5. Strategy-hop → We have one system, refined over time
```

### 5.2 Individual Step Documentation

Each of the 16 steps gets its own page under `strategy/steps/`:

#### `strategy/steps/S01-fundamental-intelligence.md`

```markdown
# Step 1: Fundamental Intelligence

## Purpose
Determine the macro-level directional bias before looking at any chart.

## What It Does
1. Ingests economic calendar data (CPI, NFP, FOMC, etc.)
2. Analyzes news sentiment via FinBERT + LLM
3. Builds a macro context map
4. Answers: "Should I be looking for BUYs, SELLs, or sitting out?"

## Inputs
| Input | Source | Frequency |
|-------|--------|-----------|
| Economic Calendar | Investing.com API | Daily |
| News Headlines | RSS + NewsAPI | Real-time |
| Sentiment Scores | FinBERT on news | Real-time |
| Central Bank Statements | Custom scraper | On release |

## Outputs
| Output | Type | Consumers |
|--------|------|-----------|
| macro_bias | SignalEvent (BIAS) | S2, S9 |
| news_impact | SignalEvent (WARNING) | Risk Governor |
| calendar_risk | SignalEvent (WARNING) | All steps |

## Configuration
```yaml
S1_fundamental:
  enabled: true
  news_lookback_hours: 24
  sentiment_model: "finbert"  # or "llm" for cloud models
  calendar_impact_threshold: "medium"  # low, medium, high
  macro_bias_decay_hours: 6
```

## How to Tune for Your Pair
| Pair | Key Drivers | Weight |
|------|-------------|--------|
| EUR/USD | ECB, Fed, CPI differential | High |
| GBP/USD | BOE, Brexit sentiment | High |
| XAU/USD | Real yields, DXY, risk sentiment | Very High |
| BTC/USD | Risk-on/off, halving cycle, ETF flows | High |
| GBP/JPY | BOE + BOJ, carry trade | Moderate |

## Common Issues
- "Bias keeps flipping" → Increase `macro_bias_decay_hours`
- "Too many warnings" → Raise `calendar_impact_threshold` to "high"
```

#### Steps 2-16 follow the same template:
- S02: Market Bias Determination
- S03: Session Analysis
- S04: Market Structure
- S05: Support & Resistance Detection
- S06: Liquidity Analysis
- S07: Smart Money Concepts (SMC)
- S08: RSI & Momentum
- S09: Multi-Timeframe Confluence
- S10: Confluence Scoring
- S11: Position Sizing
- S12: Stop Loss Placement
- S13: Take Profit Optimization
- S14: Trade Management
- S15: Exit Strategy
- S16: Post-Trade Learning

### 5.3 Pair-Specific Strategy

#### `strategy/pairs/xauusd.md`

```markdown
# XAU/USD (Gold) Strategy

## Pair Personality
- **Asset Class:** Commodity / Safe Haven
- **Avg Daily Range:** $25-40 (2500-4000 pips)
- **Best Session:** London + New York overlap
- **Key Drivers:** Real yields, DXY, geopolitical risk, CPI

## Gold-Specific Adjustments
### Step 1 (Fundamental): Gold is a Macro Instrument
- Real yield correlation: -0.85 (when yields fall, gold rises)
- DXY correlation: -0.75 (when dollar weakens, gold rises)
- Geopolitical risk: 2x weight vs other pairs

### Step 5 (S/R): Psychological Levels Matter
- Round numbers ($2000, $2050, $2100) are strong S/R
- Historical highs act as magnets
- Central bank buying levels provide floors

### Step 12 (Stop Loss): Wider Stops Required
- Minimum SL: 1.5x ATR (vs 1.0x for EUR/USD)
- Gold can spike $15 in seconds on news
- Use structure-based SL, not fixed pip SL

## What NOT to Do with Gold
- Don't trade during illiquid hours (Asian session for gold)
- Don't hold through NFP without wide stops
- Don't fight the macro trend — gold trends persist for months
```

#### Similar pages for: `btcusd.md`, `eurusd.md`, `gbpusd.md`, `gbpjpy.md`

---

## 6. API Documentation

### 6.1 REST API

#### `api/rest/index.md`

**Auto-generated from OpenAPI spec + manual guides.**

```markdown
# REST API Reference

## Base URL
```
https://api.alphastack.local/v1    # Local
https://api.alphastack.io/v1       # Production
```

## Authentication
All endpoints require a JWT Bearer token:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" https://api.alphastack.local/v1/signals
```

## Endpoints

### Signals
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/signals` | List recent signals |
| GET | `/signals/{id}` | Get signal detail |
| GET | `/signals/stream` | SSE stream of live signals |

### Trades
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/trades` | List trades (open + closed) |
| GET | `/trades/{id}` | Trade detail with full journal |
| POST | `/trades` | Place a manual trade |
| PATCH | `/trades/{id}` | Modify SL/TP |
| DELETE | `/trades/{id}` | Close a trade |

### Portfolio
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/portfolio` | Current positions + P&L |
| GET | `/portfolio/history` | Historical performance |
| GET | `/portfolio/risk` | Current risk metrics |

### Configuration
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config` | Current configuration |
| PATCH | `/config` | Update configuration |
| POST | `/config/validate` | Validate config before applying |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/status` | System status |
| GET | `/metrics` | Prometheus metrics |

## Error Handling
[Standard error response format with error codes]

## Rate Limiting
[Rate limit headers and tiers]
```

### 6.2 WebSocket API

#### `api/websocket/index.md`

```markdown
# WebSocket API

## Connection
```
ws://localhost:8000/ws?token=YOUR_JWT
```

## Channels
| Channel | Description | Push Frequency |
|---------|-------------|----------------|
| `market.tick` | Raw price ticks | Real-time (~100ms) |
| `market.candle` | Completed candles | Per timeframe |
| `signal.new` | New signals | On generation |
| `signal.update` | Signal status changes | On change |
| `trade.update` | Trade status changes | On change |
| `risk.alert` | Risk alerts | On trigger |
| `system.status` | System heartbeat | Every 30s |

## Subscribe
```json
{"action": "subscribe", "channels": ["signal.new", "trade.update"]}
```

## Message Format
```json
{
  "channel": "signal.new",
  "timestamp": "2026-07-11T14:30:00Z",
  "data": {
    "pair": "EUR/USD",
    "direction": "BUY",
    "confidence": 87,
    "grade": "A",
    "entry": 1.0850,
    "stop_loss": 1.0820,
    "take_profit": [1.0880, 1.0910, 1.0940]
  }
}
```

## Reconnection
[Auto-reconnect with exponential backoff protocol]
```

### 6.3 CLI Reference

#### `api/cli/index.md`

```markdown
# CLI Reference

## Installation
```bash
pip install alphastack-cli
```

## Commands

### `alpha start`
Start the Alpha Stack engine.
```bash
alpha start --config config/alphastack.yaml --mode paper
alpha start --config config/alphastack.yaml --mode live --pairs EUR/USD,GBP/USD
```

### `alpha status`
Show system status.
```bash
alpha status           # Summary
alpha status --verbose # Full details
alpha status --json    # JSON output
```

### `alpha signals`
View recent signals.
```bash
alpha signals                    # Last 10 signals
alpha signals --pair EUR/USD     # Filter by pair
alpha signals --grade A+         # Filter by grade
alpha signals --since 2h         # Last 2 hours
```

### `alpha trades`
Manage trades.
```bash
alpha trades                     # Open trades
alpha trades --history           # Closed trades
alpha trades --close TRADE_ID    # Close a trade
alpha trades --modify TRADE_ID --sl 1.0820  # Modify SL
```

### `alpha config`
Configuration management.
```bash
alpha config show                # Current config
alpha config validate            # Validate config file
alpha config set risk.max_risk_per_trade 1.5
```

### `alpha backtest`
Run backtests.
```bash
alpha backtest --pair EUR/USD --from 2024-01-01 --to 2025-12-31
alpha backtest --config config/custom.yaml --pairs all
```

### `alpha journal`
View and export trade journal.
```bash
alpha journal                    # Recent entries
alpha journal --export csv       # Export to CSV
alpha journal --export pdf       # Export to PDF
```
```

---

## 7. Deployment Documentation

### 7.1 Quick Start

#### `deployment/quickstart/docker-compose.md`

```markdown
# Docker Compose Deployment (5 Minutes)

## Prerequisites
- Docker 24+ and Docker Compose v2
- 4 GB RAM, 2 CPU cores minimum
- A broker account (or use paper trading)

## Step 1: Get the Code
```bash
git clone https://github.com/alphastack/alphastack.git
cd alphastack
```

## Step 2: Configure
```bash
cp .env.example .env
nano .env
```

Minimum `.env` settings:
```env
# Broker (use demo for testing)
BROKER_TYPE=mt5
BROKER_SERVER=FXPesa-Demo
BROKER_LOGIN=your_login
BROKER_PASSWORD_KEY=broker_password  # Stored in OS keyring

# Risk
MAX_RISK_PER_TRADE=1.0
MAX_DAILY_LOSS=3.0

# Mode
TRADING_MODE=paper

# API
API_SECRET_KEY=generate-a-random-key-here
```

## Step 3: Launch
```bash
docker compose up -d
```

## Step 4: Verify
```bash
# Check all services are running
docker compose ps

# Check logs
docker compose logs -f alphastack

# Open dashboard
open http://localhost:3000
```

## Architecture
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  alphastack  │  │  timescaledb│  │    redis    │
│  (main app)  │  │  (database) │  │   (cache)   │
└──────┬───────┘  └─────────────┘  └─────────────┘
       │
┌──────┴───────┐  ┌─────────────┐
│   grafana    │  │  prometheus  │
│ (dashboards) │  │  (metrics)   │
└──────────────┘  └─────────────┘
```

## Common Issues
→ [Docker Troubleshooting](../../troubleshooting/common/docker.md)
```

### 7.2 Production Deployment

#### `deployment/production/vps.md`

```markdown
# VPS Production Deployment

## Recommended Providers
| Provider | Specs | Cost | Location |
|----------|-------|------|----------|
| Hetzner CX22 | 2 vCPU, 4 GB | €5/mo | EU |
| Hetzner CX32 | 4 vCPU, 8 GB | €15/mo | EU |
| Vultr | 2 vCPU, 4 GB | $12/mo | Global |
| DigitalOcean | 2 vCPU, 4 GB | $18/mo | Global |

## Hardening Checklist
- [ ] SSH key-only authentication
- [ ] Firewall (UFW) — only 22, 80, 443
- [ ] Fail2ban installed
- [ ] Automatic security updates
- [ ] Non-root user for Alpha Stack
- [ ] TLS via Let's Encrypt
- [ ] Database not exposed to internet
- [ ] Secrets in encrypted vault, not .env files
- [ ] Log rotation configured
- [ ] Backup schedule for database

## Step-by-Step Setup
[Full walkthrough with every command]

## Performance Tuning
[TimescaleDB tuning, Redis memory, Python worker count]

## Backup & Recovery
[Database backup, config backup, disaster recovery]
```

#### `deployment/production/kubernetes.md`
- Helm chart deployment
- Scaling strategy
- Service mesh configuration
- Secret management with Vault

### 7.3 Security Documentation

#### `deployment/security/index.md`

```markdown
# Security Hardening Guide

## Security Architecture
→ See [Security Architecture Document](../../developer/architecture/security.md)

## Checklist: Production Security
### Network
- [ ] TLS 1.3 everywhere
- [ ] WAF enabled
- [ ] DDoS protection
- [ ] Geo-blocking (optional)

### Authentication
- [ ] MFA enabled for all users
- [ ] JWT tokens rotated
- [ ] API keys scoped to minimum permissions

### Data
- [ ] Encryption at rest (AES-256-GCM)
- [ ] Field-level encryption for broker credentials
- [ ] Database connections over TLS

### Broker Credentials
- [ ] Stored in OS keyring or Vault, never in files
- [ ] Isolated process/container
- [ ] Memory zeroization after use

### Monitoring
- [ ] Failed login alerts
- [ ] Anomalous API usage alerts
- [ ] Broker connection failure alerts
```

---

## 8. Troubleshooting Guides

### 8.1 Common Issues

#### `troubleshooting/common/index.md`

```markdown
# Troubleshooting Guide

## Quick Diagnostics
```bash
# Is Alpha Stack running?
alpha status

# Check logs
alpha logs --tail 50

# Check database
alpha db ping

# Check broker connection
alpha broker test

# Check data feed
alpha data status
```

## Top 20 Issues

### 1. "No signals are being generated"
**Symptoms:** Dashboard shows no signals for hours.
**Causes:**
- Market is closed (weekend/holiday)
- Data feed disconnected
- All steps disabled in config
- Confluence threshold too high

**Fix:**
1. Check `alpha data status` — is data flowing?
2. Check `alpha config show | grep confluence` — threshold ≤ 6?
3. Check market hours for your pairs
4. Check logs for errors: `alpha logs --grep "S01\|S02\|S03"`

### 2. "Broker connection failed"
**Symptoms:** Orders not executing, "DISCONNECTED" in dashboard.
**Fix:**
1. Verify credentials: `alpha broker test`
2. Check broker server status (is MetaTrader running?)
3. Check network: `ping broker-server.example.com`
4. Restart connector: `alpha broker reconnect`

[... 18 more common issues ...]
```

#### `troubleshooting/common/docker.md`
- Container won't start
- Out of memory
- Volume permission issues
- Network connectivity between containers

#### `troubleshooting/common/performance.md`
- High CPU usage
- Memory leaks
- Slow signal generation
- Database query performance

### 8.2 Broker-Specific Issues

#### `troubleshooting/broker/mt5.md`

```markdown
# MetaTrader 5 Troubleshooting

## Common MT5 Issues

### "Trade context busy"
**Cause:** MT5 can only process one order at a time.
**Fix:** The system has built-in retry with backoff. If persistent, check for stuck orders in MT5.

### "Requote"
**Cause:** Price moved between signal and execution.
**Fix:** Increase `max_slippage` in config, or use limit orders.

### "Not enough money"
**Cause:** Account balance too low for the position size.
**Fix:** Reduce `max_risk_per_trade` or increase account balance.

### Connection Drops
**Cause:** MT5 idle timeout (default: 30 minutes).
**Fix:** Alpha Stack sends keepalive packets. Ensure your MT5 allows expert advisors.
```

#### Similar pages for: `ccxt.md`, `oanda.md`, `interactive-brokers.md`

### 8.3 Error Code Reference

#### `troubleshooting/error-codes/index.md`

```markdown
# Error Code Reference

## Error Code Format
`ALPHA-[CATEGORY]-[NUMBER]`

| Category | Range | Description |
|----------|-------|-------------|
| DATA | 1000-1999 | Data pipeline errors |
| STRAT | 2000-2999 | Strategy pipeline errors |
| RISK | 3000-3999 | Risk management errors |
| EXEC | 4000-4999 | Execution errors |
| BROKER | 5000-5999 | Broker connection errors |
| AUTH | 6000-6999 | Authentication errors |
| API | 7000-7999 | API errors |
| SYS | 9000-9999 | System errors |

## Common Error Codes

### ALPHA-DATA-1001: Market Data Feed Disconnected
**Severity:** CRITICAL
**Action:** System auto-reconnects. If persistent, check data provider status.

### ALPHA-RISK-3001: Daily Loss Limit Reached
**Severity:** WARNING
**Action:** All new trades blocked until next trading day. Review recent losses.

### ALPHA-EXEC-4001: Order Rejected by Broker
**Severity:** WARNING
**Action:** Check broker account status, margin, and market hours.

[... full error code catalog ...]
```

---

## 9. Community Documentation

### 9.1 FAQ

#### `community/faq/index.md`

```markdown
# Frequently Asked Questions

## General

### What is Alpha Stack?
Alpha Stack is an AI-powered trading system that analyzes forex and crypto markets using a 16-step process and generates trade signals with full reasoning.

### How much money do I need to start?
$7 minimum for a micro account. The system adapts its position sizing to any account size. Paper trading requires $0.

### Can I lose more than I deposit?
No. The system always uses stop losses. Your maximum loss per trade is pre-defined and enforced by code.

### Does it guarantee profits?
No. No trading system guarantees profits. Alpha Stack is a tool that improves your odds through systematic analysis and risk management. You will have losing trades.

### Is it legal?
Algorithmic trading is legal in most jurisdictions. Check your local regulations. Alpha Stack does not provide financial advice.

## Trading

### Why is the position size so small?
The system uses conservative risk management by default (1% per trade). This protects your capital. You can increase it in settings, but we recommend starting small.

### Why didn't it trade during [major event]?
The system may have detected high-impact news and paused trading. This is a safety feature. Check the news calendar in the dashboard.

### Can I trade manually alongside the AI?
Yes. Manual trades are separate from AI trades. The risk engine accounts for total exposure.

## Technical

### What are the system requirements?
- Minimum: 2 CPU, 4 GB RAM, 10 GB disk
- Recommended: 4 CPU, 8 GB RAM, 50 GB SSD
- Internet: Stable connection, <100ms to broker server

### Does it work on Windows/Mac/Linux?
Yes. Docker works everywhere. Native install supports all three platforms.

### Can I run it on my phone?
The mobile app (Flutter) provides monitoring and alerts. The engine runs on a server or desktop.
```

### 9.2 Best Practices

#### `community/best-practices/index.md`

```markdown
# Best Practices

## For New Traders
1. **Start with paper trading.** Run for at least 2 weeks before going live.
2. **Use default risk settings.** Don't increase risk until you understand the system.
3. **Read the signal reasoning.** Don't blindly follow signals — understand why.
4. **Keep a manual journal.** Note your emotions and observations alongside the AI's journal.
5. **Review weekly.** Check your performance every Sunday.

## For Risk Management
1. **Never risk more than 2% per trade.** 1% is better.
2. **Never exceed 5% total exposure.** Correlated pairs count as one.
3. **Respect the circuit breakers.** If the system says stop, stop.
4. **Don't override stop losses.** The AI placed them there for a reason.
5. **Withdraw profits regularly.** Don't let your account grow unchecked.

## For System Operations
1. **Monitor daily.** Check the dashboard at least once per day.
2. **Keep backups.** Database + config, automated daily.
3. **Update regularly.** Security patches are important.
4. **Test in staging first.** Never update a live trading system without testing.
5. **Read the changelog.** Know what changed before you update.
```

### 9.3 Glossary

#### `community/glossary/index.md`

```markdown
# Glossary

## Trading Terms

| Term | Definition |
|------|------------|
| **Alpha** | Excess return above a benchmark |
| **ATR** | Average True Range — measures volatility |
| **Bid/Ask** | The price to sell / price to buy |
| **Confluence** | Multiple signals pointing to the same trade |
| **Drawdown** | Decline from peak account value |
| **FVG** | Fair Value Gap — price imbalance in SMC |
| **Lot Size** | Position size (1 standard lot = 100,000 units) |
| **Order Block** | Institutional supply/demand zone in SMC |
| **Pip** | Smallest standard price move (0.0001 for EUR/USD) |
| **SL** | Stop Loss — automatic exit at a loss threshold |
| **SMC** | Smart Money Concepts — institutional trading methodology |
| **Spread** | Difference between bid and ask price |
| **TP** | Take Profit — automatic exit at a profit target |

## Technical Terms

| Term | Definition |
|------|------------|
| **API** | Application Programming Interface |
| **CCXT** | Crypto exchange trading library |
| **DAG** | Directed Acyclic Graph |
| **JWT** | JSON Web Token — authentication token |
| **MT5** | MetaTrader 5 — forex trading platform |
| **REST** | Representational State Transfer — API style |
| **WebSocket** | Persistent bidirectional connection |
| **VMPM** | Volatility-Modified Propulsion Model |
```

---

## 10. Documentation Generation & Tooling

### 10.1 Tool Selection: MkDocs Material

| Criterion | MkDocs Material | Docusaurus | GitBook |
|-----------|:---------------:|:----------:|:-------:|
| Markdown-native | ✅ | ✅ | ✅ |
| Python ecosystem alignment | ✅ | ❌ (React) | ❌ |
| API doc integration | ✅ (mkdocstrings) | ✅ | Limited |
| Search quality | ✅ (built-in) | ✅ (Algolia) | ✅ |
| Admonitions/callouts | ✅ | ✅ | ✅ |
| Versioning | ✅ (mike) | ✅ (built-in) | ✅ |
| Diagram support | ✅ (mermaid) | ✅ | ✅ |
| Auto-generated API docs | ✅ (mkdocstrings) | Plugin needed | ❌ |
| Free hosting (GitHub Pages) | ✅ | ✅ | ❌ |
| Learning curve | Low | Medium | Low |
| Community size | Large | Large | Medium |

**Decision: MkDocs Material**

Rationale:
1. Python-native — same ecosystem as Alpha Stack
2. `mkdocstrings` auto-generates docs from Python docstrings
3. `mike` handles versioning natively
4. Material theme is the most polished option
5. Fast builds, excellent search, beautiful output

### 10.2 Toolchain

```
Documentation Pipeline:
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Source Files │───▶│  Pre-process │───▶│  MkDocs Build│───▶│  Deploy      │
│  (Markdown)  │    │  (Scripts)   │    │  (Material)  │    │  (Pages/S3)  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  .md files in       Auto-generate:       Static HTML         GitHub Pages
  docs/ dir          - API reference      with search         or S3/CloudFront
                     - Config schema      and versioning
                     - Error codes
```

### 10.3 MkDocs Configuration

#### `mkdocs.yml`

```yaml
site_name: Alpha Stack Documentation
site_url: https://docs.alphastack.io
site_description: Institutional-grade AI trading platform documentation

repo_url: https://github.com/alphastack/alphastack
repo_name: alphastack/alphastack
edit_uri: edit/main/docs/

theme:
  name: material
  palette:
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: deep navy
      accent: electric blue
      toggle:
        icon: material/brightness-7
        name: Switch to light mode
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: deep navy
      accent: electric blue
      toggle:
        icon: material/brightness-4
        name: Switch to dark mode
  font:
    text: Inter
    code: JetBrains Mono
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy
    - content.tabs.link
    - toc.follow
  icon:
    repo: fontawesome/brands/github

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_source: true
            show_root_heading: true
            members_order: source
  - tags
  - minify:
      minify_html: true

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_mermaid
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - attr_list
  - md_in_html
  - tables
  - toc:
      permalink: true

nav:
  - Home: index.md
  - User Guide:
    - Getting Started:
      - user/getting-started/index.md
      - Installation: user/getting-started/installation.md
      - Your First Trade: user/getting-started/first-trade.md
    - Guides:
      - Trading Guide: user/guides/trading-guide.md
      - user/guides/risk-management.md
      - user/guides/multi-pair-setup.md
    - Configuration:
      - user/configuration/index.md
      - user/configuration/broker.md
      - user/configuration/risk.md
      - user/configuration/pairs.md
    - Reference:
      - user/reference/signal-types.md
      - user/reference/keyboard-shortcuts.md
      - user/reference/chat-commands.md
  - Strategy:
    - strategy/overview/index.md
    - Steps:
      - strategy/steps/S01-fundamental-intelligence.md
      # ... all 16 steps
    - Pairs:
      - strategy/pairs/xauusd.md
      # ... all pairs
  - Developer:
    - Architecture:
      - developer/architecture/index.md
      - developer/architecture/event-system.md
      - developer/architecture/multi-agent.md
    - Contributing:
      - developer/contributing/index.md
    - Internals:
      - developer/internals/vmpm-pipeline.md
      - developer/internals/risk-engine.md
  - API Reference:
    - REST: api/rest/index.md
    - WebSocket: api/websocket/index.md
    - CLI: api/cli/index.md
  - Deployment:
    - Quick Start: deployment/quickstart/docker-compose.md
    - Production:
      - deployment/production/vps.md
      - deployment/production/kubernetes.md
    - Security: deployment/security/index.md
  - Troubleshooting:
    - troubleshooting/common/index.md
    - troubleshooting/broker/mt5.md
    - troubleshooting/error-codes/index.md
  - Community:
    - FAQ: community/faq/index.md
    - Best Practices: community/best-practices/index.md
    - Glossary: community/glossary/index.md

extra:
  version:
    provider: mike
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/alphastack/alphastack
    - icon: fontawesome/brands/discord
      link: https://discord.gg/alphastack
    - icon: fontawesome/brands/telegram
      link: https://t.me/alphastack
```

### 10.4 Auto-Generation Scripts

#### `scripts/docs/generate_api_reference.py`

```python
"""
Generate API reference from OpenAPI spec.
Runs in CI to keep API docs in sync with code.
"""
import yaml
from pathlib import Path

def generate_rest_docs(openapi_path: str, output_dir: str):
    """Parse OpenAPI spec and generate markdown docs."""
    with open(openapi_path) as f:
        spec = yaml.safe_load(f)
    
    for path, methods in spec["paths"].items():
        for method, details in methods.items():
            # Generate markdown for each endpoint
            ...

def generate_websocket_docs(ws_schema_path: str, output_dir: str):
    """Generate WebSocket channel documentation from schema."""
    ...
```

#### `scripts/docs/generate_config_docs.py`

```python
"""
Generate configuration reference from Pydantic settings models.
Extracts field descriptions, types, defaults, and constraints.
"""
from alphastack.config import AlphaStackConfig

def generate_config_docs(output_path: str):
    schema = AlphaStackConfig.model_json_schema()
    # Convert JSON Schema to markdown table
    ...
```

#### `scripts/docs/generate_error_codes.py`

```python
"""
Extract error codes from source and generate reference.
Scans for ALPHA-XXXX-XXXX patterns in source code.
"""
import re
from pathlib import Path

ERROR_PATTERN = re.compile(r"ALPHA-\w+-\d{4}")

def scan_error_codes(src_dir: str) -> dict:
    """Find all defined error codes with their descriptions."""
    ...
```

---

## 11. Documentation Versioning

### 11.1 Versioning Strategy

```
Version Lifecycle:
┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐
│   NEXT    │───▶│  LATEST   │───▶│ STABLE    │───▶│  ARCHIVED │
│ (main)    │    │ (release) │    │ (LTS)     │    │ (old)     │
└───────────┘    └───────────┘    └───────────┘    └───────────┘
     │                │                │                │
  dev docs       current docs    maintained docs    frozen docs
  may break      always shown    security fixes     search only
```

### 11.2 Versioning with Mike

```bash
# Build and deploy a new version
mike deploy --push --update-aliases 1.0 latest

# Deploy a development version
mike deploy --push main

# List versions
mike list

# Set default version
mike set-default --push latest
```

### 11.3 Version Lifecycle Rules

| Version | Status | Updates | Lifetime |
|---------|--------|---------|----------|
| `main` | Development | All changes | Continuous |
| `X.Y` (latest) | Active | Features, fixes, docs | Until next minor |
| `X.Y` (stable/LTS) | Maintenance | Security + critical fixes only | 12 months |
| `X.Y` (archived) | Frozen | None | Search-only |

### 11.4 Per-Version Content

Each version includes:
- Full documentation for that release
- Version-specific screenshots
- Version-specific configuration defaults
- Link to changelog for that version

---

## 12. Documentation CI/CD

### 12.1 Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DOCUMENTATION CI/CD PIPELINE                   │
│                                                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │  Commit  │───▶│  Lint &  │───▶│  Build & │───▶│  Deploy  │   │
│  │  to main │    │  Validate│    │  Test    │    │          │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
│       │               │               │               │          │
│       ▼               ▼               ▼               ▼          │
│  docs/*.md      markdownlint     mkdocs build    GitHub Pages    │
│  changed?       link check       test examples   or S3 deploy    │
│                 spell check      broken links                    │
│                 frontmatter      accessibility                   │
│                 validation                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 12.2 GitHub Actions Workflow

#### `.github/workflows/docs.yml`

```yaml
name: Documentation

on:
  push:
    branches: [main]
    paths:
      - 'docs/**'
      - 'mkdocs.yml'
      - 'src/**/*.py'  # For auto-generated API docs
  pull_request:
    paths:
      - 'docs/**'
      - 'mkdocs.yml'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install mkdocs-material mkdocstrings[python] mike
          pip install markdownlint-cli linkchecker
      
      - name: Lint markdown
        run: markdownlint docs/**/*.md
      
      - name: Check links
        run: linkchecker site/ --check-extern
      
      - name: Validate frontmatter
        run: python scripts/docs/validate_frontmatter.py
      
      - name: Build documentation
        run: mkdocs build --strict
      
      - name: Test code examples
        run: python scripts/docs/test_examples.py

  deploy:
    needs: validate
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install mkdocs-material mkdocstrings[python] mike
      
      - name: Configure git
        run: |
          git config user.name "docs-bot"
          git config user.email "docs@alphastack.io"
      
      - name: Generate API docs
        run: python scripts/docs/generate_api_reference.py
      
      - name: Generate config docs
        run: python scripts/docs/generate_config_docs.py
      
      - name: Deploy docs
        run: mike deploy --push --update-aliases main latest
```

### 12.3 Auto-Update Triggers

| Trigger | Action | Frequency |
|---------|--------|-----------|
| Code commit (API change) | Regenerate API reference | Every push |
| Code commit (config change) | Regenerate config reference | Every push |
| New error code added | Regenerate error code reference | Every push |
| Architecture report updated | Regenerate architecture docs | Manual review |
| New release tagged | Deploy versioned docs | On tag |
| PR merged to main | Deploy `main` version | Every merge |

### 12.4 Documentation Testing

#### `scripts/docs/test_examples.py`

```python
"""
Test that all code examples in documentation actually work.
Extracts Python/bash code blocks and validates them.
"""
import re
from pathlib import Path

def extract_code_blocks(filepath: str) -> list[dict]:
    """Extract fenced code blocks with language tags."""
    ...

def test_python_example(code: str) -> bool:
    """Run Python example and check for errors."""
    ...

def test_bash_example(code: str) -> bool:
    """Validate bash example syntax."""
    ...

def main():
    docs_dir = Path("docs")
    for md_file in docs_dir.rglob("*.md"):
        blocks = extract_code_blocks(md_file)
        for block in blocks:
            if block["lang"] == "python":
                assert test_python_example(block["code"]), \
                    f"Failed: {md_file}:{block['line']}"
```

#### `scripts/docs/validate_frontmatter.py`

```python
"""
Validate that all docs have required frontmatter fields.
"""
REQUIRED_FIELDS = ["title", "audience", "last_reviewed"]

def validate(filepath: str) -> list[str]:
    """Return list of validation errors."""
    ...
```

#### `scripts/docs/check_staleness.py`

```python
"""
Flag documentation that hasn't been reviewed within its review cycle.
"""
from datetime import datetime, timedelta

REVIEW_CYCLES = {
    "monthly": 30,
    "quarterly": 90,
    "on-release": None,  # Manual
}

def check_staleness(docs_dir: str) -> list[dict]:
    """Return list of stale documents."""
    stale = []
    for md_file in Path(docs_dir).rglob("*.md"):
        frontmatter = parse_frontmatter(md_file)
        last_reviewed = datetime.fromisoformat(frontmatter["last_reviewed"])
        cycle_days = REVIEW_CYCLES[frontmatter["review_cycle"]]
        if cycle_days and datetime.now() - last_reviewed > timedelta(days=cycle_days):
            stale.append({
                "file": str(md_file),
                "last_reviewed": last_reviewed,
                "days_stale": (datetime.now() - last_reviewed).days,
            })
    return stale
```

---

## 13. Maintenance & Governance

### 13.1 Ownership Model

| Section | Owner | Review Cycle |
|---------|-------|-------------|
| User Docs | Product Team | Monthly |
| Developer Docs | Engineering Lead | On release |
| Strategy Docs | Trading Lead | Quarterly |
| API Docs | Auto-generated (CI) | Every commit |
| Deployment Docs | DevOps | On release |
| Troubleshooting | Support Lead | Monthly |
| Community Docs | Community Manager | Quarterly |

### 13.2 Review Process

```
Documentation Change Process:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Author  │───▶│  Self-   │───▶│  Peer    │───▶│  Owner   │
│  writes  │    │  review  │    │  review  │    │  approve │
│  change  │    │  (lint)  │    │  (PR)    │    │  (merge) │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

PR checklist for documentation changes:
- [ ] Frontmatter is complete and valid
- [ ] Audience is clearly stated
- [ ] Code examples tested
- [ ] Links are valid
- [ ] Screenshots are current (if applicable)
- [ ] Related docs are updated
- [ ] Changelog entry (if user-facing)

### 13.3 Staleness Policy

| Severity | Action |
|----------|--------|
| `last_reviewed` > review cycle | Automated issue created |
| `last_reviewed` > 2x review cycle | Issue escalated to owner |
| `last_reviewed` > 3x review cycle | Doc marked as "potentially outdated" banner |
| No `last_reviewed` field | CI fails |

### 13.4 Changelog Integration

Every release includes a documentation changelog:

```markdown
## Documentation Changes in v1.2.0

### New
- Added WebSocket API reference
- Added GBP/JPY pair strategy guide

### Updated
- Installation guide updated for Docker Compose v2.24
- Risk management guide updated with new circuit breaker levels

### Fixed
- Fixed broken link in MT5 broker setup guide
- Corrected position sizing formula in trading guide

### Deprecated
- v0.9 configuration format (migration guide available)
```

---

## 14. Metrics & Quality Gates

### 14.1 Documentation Metrics

| Metric | Target | How Measured |
|--------|--------|-------------|
| **Coverage** | 100% of public APIs documented | mkdocstrings coverage report |
| **Freshness** | 90% of docs reviewed within cycle | Staleness checker |
| **Link Health** | 0 broken links | linkchecker in CI |
| **Code Example Validity** | 100% of examples pass | test_examples.py |
| **Search Success Rate** | >80% of searches find relevant result | Search analytics |
| **User Task Completion** | >90% complete common tasks from docs | User testing |

### 14.2 Quality Gates in CI

```yaml
# CI must pass ALL gates before docs deploy
quality_gates:
  - name: "No broken internal links"
    check: linkchecker --check-extern
    threshold: 0 broken
    
  - name: "All frontmatter valid"
    check: validate_frontmatter.py
    threshold: 0 errors
    
  - name: "No stale docs > 2x cycle"
    check: check_staleness.py
    threshold: 0 stale
    
  - name: "Code examples pass"
    check: test_examples.py
    threshold: 100% pass
    
  - name: "Build succeeds"
    check: mkdocs build --strict
    threshold: exit code 0
```

### 14.3 Documentation Health Dashboard

A Grafana dashboard tracking:
- Total pages by section
- Pages reviewed / total pages (freshness %)
- Broken links count (trending)
- Search queries with no results
- Most visited pages
- Pages with highest bounce rate
- CI build times

---

## 15. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

| Task | Deliverable | Effort |
|------|-------------|--------|
| Set up MkDocs Material | `mkdocs.yml` + theme | 2 hours |
| Create directory structure | All folders + index pages | 2 hours |
| Write frontmatter template | `docs/template.md` | 1 hour |
| Set up CI pipeline | `.github/workflows/docs.yml` | 3 hours |
| Write Getting Started guide | `user/getting-started/` | 4 hours |
| Write Installation guide | All three methods | 3 hours |

**Milestone:** Docs site live at `docs.alphastack.io` with installation guide.

### Phase 2: Core Content (Week 3-4)

| Task | Deliverable | Effort |
|------|-------------|--------|
| Trading Guide | Complete user trading guide | 6 hours |
| Configuration Reference | Full config documentation | 4 hours |
| Strategy Overview | VMPM philosophy + flow | 4 hours |
| Steps 1-8 documentation | First 8 strategy steps | 8 hours |
| REST API Reference | Auto-generated + manual guides | 6 hours |
| FAQ + Glossary | Community docs | 3 hours |

**Milestone:** New users can install, configure, and understand the system from docs alone.

### Phase 3: Deep Content (Week 5-6)

| Task | Deliverable | Effort |
|------|-------------|--------|
| Steps 9-16 documentation | Remaining 8 strategy steps | 8 hours |
| Pair-specific guides | 5 pair guides | 6 hours |
| WebSocket API Reference | Full WebSocket docs | 4 hours |
| CLI Reference | Complete CLI docs | 3 hours |
| Deployment guides | Docker, VPS, K8s | 6 hours |
| Troubleshooting guides | Top 20 issues + error codes | 6 hours |

**Milestone:** Complete documentation for all major features.

### Phase 4: Automation & Polish (Week 7-8)

| Task | Deliverable | Effort |
|------|-------------|--------|
| Auto-generation scripts | API, config, error codes | 6 hours |
| Documentation testing | test_examples.py | 4 hours |
| Versioning setup | mike configuration | 2 hours |
| Staleness checker | check_staleness.py | 2 hours |
| Link checker integration | CI integration | 1 hour |
| Health dashboard | Grafana dashboard | 3 hours |
| Search optimization | Tags, metadata, cross-refs | 3 hours |

**Milestone:** Self-maintaining documentation system.

### Phase 5: Community & Iteration (Ongoing)

| Task | Frequency |
|------|-----------|
| Review user feedback | Weekly |
| Update stale docs | Monthly |
| Add new troubleshooting items | As issues arise |
| Update for new releases | On release |
| User testing sessions | Quarterly |

---

## Appendix A: Architecture Decision Record Template

```markdown
# ADR-[NUMBER]: [TITLE]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## Date
YYYY-MM-DD

## Context
What is the issue that we're seeing that motivates this decision?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or harder because of this change?

## Alternatives Considered
What other options were evaluated and why they were rejected?
```

## Appendix B: Documentation Anti-Patterns

| Anti-Pattern | Why It's Bad | Alpha Stack Solution |
|-------------|-------------|---------------------|
| Wiki-style "anyone can edit" | Inconsistent quality, contradictory info | PR-based with owner approval |
| Screenshots without alt text | Inaccessible, unsearchable | Alt text required in CI |
| "See the code" as documentation | Code is not documentation | Every public API has prose docs |
| Outdated examples | Breaks user trust | CI tests all examples |
| Giant monolithic pages | Hard to find anything | Progressive disclosure, small pages |
| Docs in a separate repo | Drift from code | Same repo, same PR |
| No versioning | Users on old versions can't find their docs | mike versioning |
| "TODO" in production docs | Looks unprofessional | CI flags TODOs |

---

*Document generated: 2026-07-11*
*Next review: 2026-10-11 (quarterly)*
*Owner: Documentation Architect*
