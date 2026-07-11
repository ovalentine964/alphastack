# Alpha Stack — Channel & Notification Architecture

> **"Institutional-grade visibility, from your pocket."**
> Every signal, trade, decision, and risk event — delivered to wherever the trader is.

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Channel Integration Architecture](#2-channel-integration-architecture)
3. [Message Taxonomy — What Gets Sent](#3-message-taxonomy--what-gets-sent)
4. [Trader Commands — What Traders Can Do](#4-trader-commands--what-traders-can-do)
5. [Progressive Autonomy Model](#5-progressive-autonomy-model)
6. [Notification Priority System](#6-notification-priority-system)
7. [Channel-Specific Formatting](#7-channel-specific-formatting)
8. [OpenClaw Integration Layer](#8-openclaw-integration-layer)
9. [Notification Engine — Internal Design](#9-notification-engine--internal-design)
10. [Security & Access Control](#10-security--access-control)
11. [Implementation Roadmap](#11-implementation-roadmap)

---

## 1. Design Philosophy

### Core Principles

| Principle | Meaning |
|-----------|---------|
| **Radical Transparency** | Every decision the system makes is visible to the trader. No black boxes. |
| **Trader Sovereignty** | The trader always has the final word. Override, pause, close — instantly. |
| **Context Over Noise** | Send *why*, not just *what*. A signal without reasoning is noise. |
| **Progressive Trust** | Start with alerts, earn autonomy over time. Prove, don't assume. |
| **Channel Agnostic** | Same intelligence, adapted to each platform's strengths. |

### The Institutional Analogy

A hedge fund PM sees every trade their desk executes, every risk metric, every model output. Alpha Stack gives the retail trader the same operational visibility — just delivered to their phone instead of a Bloomberg terminal.

---

## 2. Channel Integration Architecture

### 2.1 System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        ALPHA STACK CORE                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ Strategy │ │   Risk   │ │ Execution│ │  Agent Orchestr. │   │
│  │  Agents  │ │  Engine  │ │  Engine  │ │  (Observer etc.) │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘   │
│       │            │            │                 │              │
│       └────────────┴────────────┴─────────────────┘              │
│                          │                                       │
│                   ┌──────▼──────┐                                │
│                   │  NOTIFICATION│                                │
│                   │    ENGINE    │                                │
│                   │  (Priority,  │                                │
│                   │   Routing,   │                                │
│                   │   Batching)  │                                │
│                   └──────┬──────┘                                │
└──────────────────────────┼──────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐ ┌────▼─────┐
        │  OpenClaw  │ │  Cron  │ │  Direct  │
        │  Gateway   │ │  Jobs  │ │   API    │
        └─────┬─────┘ └───┬────┘ └────┬─────┘
              │            │           │
    ┌─────────┼────────────┼───────────┼──────────┐
    │         │            │           │          │
┌───▼───┐ ┌──▼───┐ ┌──────▼──┐ ┌─────▼──┐ ┌────▼────┐
│Telegram│ │Discord│ │ WhatsApp│ │ Signal │ │  Email  │
│  Bot   │ │  Bot  │ │  (API)  │ │(Matrix)│ │ (SMTP)  │
│(primary)│ │(comm) │ │(twilio) │ │(encrypt)│ │(reports)│
└────────┘ └───────┘ └─────────┘ └────────┘ └─────────┘
```

### 2.2 Channel Roles

Each channel has a **primary purpose**, not just a copy-paste of the same feed:

| Channel | Role | Why This Channel |
|---------|------|-----------------|
| **Telegram** | **Primary cockpit** — real-time signals, trade alerts, interactive commands, chart images | Best bot API, rich media, inline keyboards, instant delivery. The trader's main screen. |
| **Discord** | **Community & education** — signal sharing, discussion threads, trade reviews, strategy explanations | Thread support, rich embeds, community interaction. Where traders learn together. |
| **WhatsApp** | **Mobile alerts** — critical notifications, daily summaries, quick status checks | Ubiquitous on mobile, high open rate. For the trader who's away from their desk. |
| **Signal** | **Encrypted channel** — sensitive data, account balance, position details | End-to-end encryption. For traders who prioritize privacy. |
| **Email** | **Formal reports** — daily/weekly P&L, trade journal, performance analytics | Persistent, searchable, printable. The institutional audit trail. |

### 2.3 Channel Priority & Fallback

```
Notification Priority → Channel Routing:

P0 (CRITICAL)  → ALL channels simultaneously + push notification
P1 (HIGH)      → Primary channel (Telegram) + WhatsApp
P2 (MEDIUM)    → Primary channel only
P3 (LOW)       → Primary channel, batched / scheduled
```

---

## 3. Message Taxonomy — What Gets Sent

### 3.1 Signal Events

#### New Signal Detected

```
🔔 NEW SIGNAL — EUR/USD LONG

📊 Signal: EMA crossover + RSI divergence
🎯 Direction: LONG
📈 Entry Zone: 1.0845–1.0855
🛑 Stop Loss: 1.0810 (35 pips)
✅ Take Profit: 1.0920 (70 pips)
⚖️ R:R Ratio: 1:2.0
🤖 Confidence: 78% (3/4 agents agree)
📋 Reasoning: Observer notes bullish structure,
   Regime Detector confirms trending regime,
   News Sentiment is neutral-positive.

⏰ Valid for: 2 hours
💡 Autonomy Level: Awaiting your approval
```

#### Signal Expired (No Action Taken)

```
⏰ SIGNAL EXPIRED — EUR/USD LONG

The signal from 2h ago is no longer valid.
Entry zone was missed. No trade taken.
Agents will continue monitoring.
```

### 3.2 Trade Lifecycle Events

#### Trade Entered

```
✅ TRADE OPENED — GBP/JPY SHORT

📍 Entry: 189.450
🛑 Stop Loss: 189.850 (40 pips)
🎯 TP1: 189.050 (40 pips) — 50% close
🎯 TP2: 188.650 (80 pips) — remaining
📊 Lot Size: 0.15 (1.5% risk)
🤖 Agents: Observer + Risk Manager active
📋 Strategy: Mean reversion at resistance zone

I'll manage this trade and keep you updated.
```

#### Trade Management Update

```
🔄 TRADE UPDATE — GBP/JPY SHORT

✅ SL moved to Breakeven (189.450)
📊 Price reached 189.150 (+30 pips / 75% to TP1)
💡 Reason: Price showed rejection at 189.150,
   securing the position at zero risk.

Current P/L: +$45.00 (+30 pips)
```

#### Partial Close

```
🎯 TP1 HIT — GBP/JPY SHORT

✅ Closed 50% at 189.050 (+40 pips)
💰 Realized: +$60.00
📊 Remaining: 0.07 lots
🛑 New SL: 189.250 (trailing)
🎯 TP2: 188.650 still active

Risk-free trade from here. Letting the rest run.
```

#### Trade Exited

```
🏁 TRADE CLOSED — GBP/JPY SHORT

📍 Entry: 189.450 → Exit: 188.720
📊 Result: +73 pips | +$109.50
⏱️ Duration: 4h 22m
📋 Exit Reason: TP2 hit

📝 LESSON LEARNED:
Resistance-level mean reversion worked well.
The trailing SL after TP1 captured extra movement.
Consider scaling in at partial resistance levels next time.

📈 Today's P/L: +$187.50 (3 trades, 2W/1L)
```

#### Trade Stopped Out

```
❌ TRADE STOPPED — EUR/USD LONG

📍 Entry: 1.0850 → Exit: 1.0810
📊 Result: -40 pips | -$60.00
⏱️ Duration: 1h 15m
📋 Exit Reason: Stop Loss hit

📝 POST-MORTEM:
Price reversed after unexpected ECB hawkish comment.
Entry was technically sound but macro overrode setup.
Risk was correctly sized — loss is within tolerance.

📊 Today's P/L: +$127.50 (3 trades, 2W/1L)
```

### 3.3 Risk & System Events

#### Drawdown Warning

```
⚠️ RISK ALERT — Drawdown Warning

Current drawdown: -3.2%
Daily loss limit: -5.0%
Remaining buffer: -1.8%

If drawdown reaches -5%, all trading will pause automatically.

Recommended action: Review open positions.
```

#### Circuit Breaker Triggered

```
🚨 CIRCUIT BREAKER TRIGGERED 🚨

Reason: Daily loss limit reached (-5.0%)
Action Taken: ALL POSITIONS CLOSED
Total Realized Loss: -$150.00

Trading is PAUSED. Manual restart required.

This is a safety mechanism to protect your capital.
Review your trades before restarting.
```

#### Black Swan Event

```
🚨🚨 BLACK SWAN ALERT 🚨🚨

Extreme volatility detected across all pairs.
VIX spike: +45% in 15 minutes.

Action Taken: ALL POSITIONS CLOSED
Unrealized P/L realized: -$89.00

System is in SAFE MODE.
All automated trading suspended.
Manual intervention required to resume.

Your capital is protected. Positions will not
be reopened until you explicitly authorize it.
```

### 3.4 Agent Status Updates

#### Agent Heartbeat (Batched, Periodic)

```
🤖 AGENT STATUS — 14:30 UTC

👁️ Observer: Monitoring 6 pairs, 2 setups forming
📊 Regime Detector: Trending (risk-on), confidence 82%
📰 News Scanner: No high-impact events in next 4h
⚠️ Risk Manager: 3.2% drawdown, 2 open positions
🧠 Strategy: Scanning for mean reversion setups

All systems nominal. ✅
```

#### Agent Decision Explained

```
🧠 AGENT DECISION — Why No Trade on USD/JPY

Observer detected a potential setup at 148.50.
But Regime Detector flagged consolidation regime.
Conflicting signals → No trade taken.

This is the system working correctly.
We'd rather miss a trade than take a bad one.
```

### 3.5 Scheduled Reports

#### Daily Summary (End of Trading Day)

```
📊 DAILY REPORT — 2024-01-15

━━━ PERFORMANCE ━━━
Trades: 5 (3W / 1L / 1BE)
Win Rate: 60%
Net P/L: +$234.50 (+2.3%)
Best Trade: GBP/JPY SHORT +$109.50
Worst Trade: EUR/USD LONG -$60.00
Avg Winner: +$91.33
Avg Loser: -$60.00
Profit Factor: 2.28

━━━ RISK METRICS ━━━
Max Drawdown: -1.2%
Max Consecutive Losses: 1
Risk Per Trade: 1.5% avg
Total Exposure: 0 open positions

━━━ AGENT ACTIVITY ━━━
Signals Generated: 8
Signals Taken: 5
Signals Filtered: 3 (regime mismatch, news conflict, correlation risk)

━━━ KEY DECISIONS ━━━
• Filtered EUR/USD signal at 10:15 — RSI overbought on H4
• Moved GBP/JPY SL to BE after +30 pips
• Early exit on AUD/USD before FOMC minutes

━━━ TOMORROW ━━━
High-impact: US Retail Sales (13:30 UTC)
Regime: Trending continues, watch for reversal signals
Pairs in focus: EUR/GBP, USD/CAD

Full journal: /trades/2024-01-15.md
```

---

## 4. Trader Commands — What Traders Can Do

### 4.1 Command Interface

Traders interact via natural language or structured commands. The system parses intent regardless of phrasing.

#### Information Queries

| Command | What It Does | Example Phrases |
|---------|-------------|-----------------|
| `/positions` | Show all open positions | "What's open?", "Show positions", "/pos" |
| `/balance` | Account balance, equity, margin | "How much money do I have?", "/bal" |
| `/pnl` | Today's P&L breakdown | "How am I doing today?", "/pnl" |
| `/history` | Recent trade history | "Show my last 10 trades", "/hist" |
| `/status` | System & agent status | "What are the agents doing?", "/status" |
| `/why [trade]` | Explain a specific trade decision | "Why did you take the EUR/USD trade?" |
| `/signals` | Current active signals | "Any signals right now?", "/sig" |
| `/risk` | Current risk exposure & metrics | "What's my risk?", "/risk" |

#### Control Commands

| Command | What It Does | Example Phrases |
|---------|-------------|-----------------|
| `/pause` | Pause all automated trading | "Stop trading", "/pause" |
| `/resume` | Resume automated trading | "Start trading again", "/resume" |
| `/close [pair]` | Close specific position | "Close EUR/USD", "/close eurusd" |
| `/closeall` | Close all positions | "Close everything", "/closeall" |
| `/risk [level]` | Adjust risk level | "Set risk to 1%", "/risk 1%" |
| `/approve [signal]` | Approve a pending signal | "Take the GBP/JPY signal", "yes" |
| `/reject [signal]` | Reject a pending signal | "Skip that signal", "no" |
| `/level [1-4]` | Change autonomy level | "Go to level 3", "/level 3" |

#### Advanced Queries

| Command | What It Does |
|---------|-------------|
| `/journal [date]` | Trade journal for a specific date |
| `/performance [period]` | Performance stats (week/month/all) |
| `/agents` | Detailed agent breakdown |
| `/explain [indicator]` | Educational: explain an indicator or concept |
| `/backtest [pair] [strategy]` | Quick backtest results |

### 4.2 Natural Language Examples

The system handles conversational input, not just slash commands:

```
Trader: "What happened to my GBP/JPY trade?"
System:  [Shows full trade lifecycle with entry, management, exit]

Trader: "I'm nervous about the market, should I pause?"
System:  Current regime: Trending. Your exposure: 1.5%.
         No elevated risk signals detected.
         Would you like me to pause? [Yes / No / Reduce Risk]

Trader: "Why haven't you taken any trades today?"
System:  3 signals were generated but filtered:
         1. EUR/USD — regime mismatch (consolidation)
         2. AUD/USD — high-impact news in 30min
         3. USD/CAD — correlation with open GBP position
         The system is protecting your capital, not being lazy. 💪

Trader: "Show me the chart for EUR/USD"
System:  [Sends chart image with key levels, current price, signal zones]
```

### 4.3 Confirmation & Safety

Destructive actions require confirmation:

```
Trader: Close everything

System: ⚠️ CONFIRM CLOSE ALL

Currently open:
• EUR/USD LONG — +$45.00
• GBP/JPY SHORT — +$109.50
• USD/CAD LONG — -$23.00

Total unrealized: +$131.50

Type "CONFIRM" to close all positions.
Type "CANCEL" to abort.
```

---

## 5. Progressive Autonomy Model

### 5.1 The Four Levels

```
Level 1: ALERT ONLY
├── System detects signals
├── Sends alert with entry/SL/TP suggestion
├── Trader manually executes on their broker
├── System monitors if trader reports the trade
└── Use case: New traders, testing the system

Level 2: SIGNAL + APPROVAL
├── System detects signals
├── Sends signal with full reasoning
├── Trader approves or rejects via channel command
├── System executes approved trades automatically
├── System manages approved trades (SL moves, partials)
└── Use case: Traders building trust in the system

Level 3: AUTO-EXECUTE + OVERRIDE
├── System detects, evaluates, and executes automatically
├── Trader receives notification of every trade
├── Trader can override at any time (close, modify, pause)
├── System manages full trade lifecycle
└── Use case: Experienced traders who trust the system

Level 4: FULL AUTOMATION
├── System operates autonomously
├── Trader receives daily/weekly reports
├── Real-time alerts only for P0/P1 events
├── Trader can intervene at any time
└── Use case: Verified track record, high trust
```

### 5.2 Level Selection via Channel

```
Trader: /level

System: 🎛️ AUTONOMY LEVEL

Current: Level 2 (Signal + Approval)

[1] 🔔 Alert Only — You execute everything
[2] ✋ Signal + Approval — You approve, I execute
[3] ⚡ Auto-Execute + Override — I execute, you can stop me
[4] 🤖 Full Automation — I handle everything, you review

Each level earns trust over time.
You can change anytime. No judgment.

Which level? [1/2/3/4]
```

### 5.3 Trust Progression

```
Level 1 → Level 2: After 20+ manually tracked trades with >55% win rate
Level 2 → Level 3: After 50+ approved trades with positive expectancy
Level 3 → Level 4: After 100+ auto trades with consistent profitability

The system suggests upgrades but NEVER auto-upgrades.
The trader always decides.
```

---

## 6. Notification Priority System

### 6.1 Priority Levels

| Priority | Event Type | Latency Target | Channels | Behavior |
|----------|-----------|----------------|----------|----------|
| **P0 — CRITICAL** | Black swan, circuit breaker, system halt, margin call warning | < 10 seconds | ALL channels | Immediate, persistent retry until acknowledged |
| **P1 — HIGH** | Trade entry/exit, stop loss hit, risk limit approaching | < 30 seconds | Primary + WhatsApp | Immediate delivery |
| **P2 — MEDIUM** | SL moved to BE, partial close, agent status change | < 5 minutes | Primary only | May be batched (max 3 per batch) |
| **P3 — LOW** | Daily summary, educational tips, performance reports | Scheduled | Primary only | Delivered at configured time |

### 6.2 Priority Routing Logic

```python
class NotificationPriority(Enum):
    CRITICAL = 0  # Black swan, circuit breaker, system halt
    HIGH = 1      # Trade entry/exit, risk alerts
    MEDIUM = 2    # Trade management, agent updates
    LOW = 3       # Reports, education, tips

def route_notification(event):
    priority = classify_priority(event)

    if priority == P0:
        # Fan out to ALL channels simultaneously
        for channel in user.active_channels:
            send_immediate(channel, event)
        # Also trigger push notification if available
        trigger_push(event)
        # Retry until acknowledged
        set_ack_timeout(event, timeout=300)

    elif priority == P1:
        send_immediate(user.primary_channel, event)
        send_immediate(user.whatsapp_channel, event)

    elif priority == P2:
        # Batch with other P2 events, max wait 5 min
        batch_queue.add(user.primary_channel, event)

    elif priority == P3:
        # Schedule for next delivery window
        schedule_queue.add(user.primary_channel, event)
```

### 6.3 Batching Strategy (P2 Events)

```
Batch Window: 5 minutes
Max Batch Size: 5 events
Batch Format:

📋 TRADE UPDATES — 14:25–14:30 UTC

1. EUR/USD: SL moved to Breakeven
2. GBP/JPY: Partial close at TP1 (+$60)
3. AUD/USD: Price approaching entry zone (monitoring)

---
Instead of 3 separate messages, trader gets 1 clean digest.
```

### 6.4 Quiet Hours

```
Quiet Hours: 23:00–07:00 (trader's local time)

During quiet hours:
- P0: Still delivered (all channels)
- P1: Queued, delivered at 07:00 as digest
- P2: Queued, delivered at 07:00 as digest
- P3: Delivered at scheduled time as usual

Exception: Trader can override quiet hours per-pair
(e.g., "Alert me on JPY pairs even at night")
```

---

## 7. Channel-Specific Formatting

### 7.1 Telegram (Primary Channel)

Rich formatting with inline keyboards for interactive commands:

```markdown
✅ TRADE OPENED — GBP/JPY SHORT

📍 Entry: 189.450
🛑 Stop Loss: 189.850
🎯 TP1: 189.050 | TP2: 188.650
📊 Lot Size: 0.15 (1.5% risk)
🤖 Confidence: 78%

[📊 Chart] [📋 Details] [❌ Close Trade]
```

**Inline Keyboard Actions:**
- `📊 Chart` → Sends candlestick chart with levels
- `📋 Details` → Full signal reasoning
- `❌ Close Trade` → Confirmation dialog
- `⏸️ Pause System` → Emergency pause

**Media Support:**
- Chart images (PNG from charting engine)
- Trade journal PDFs
- Performance screenshots

### 7.2 Discord (Community Channel)

Rich embeds with thread creation for discussion:

```
┌─────────────────────────────────────┐
│  🟢 NEW TRADE — GBP/JPY SHORT      │
│  ─────────────────────────────────  │
│  Entry: 189.450                     │
│  Stop Loss: 189.850                 │
│  Take Profit: 189.050 / 188.650    │
│  Risk: 1.5% | Confidence: 78%      │
│  ─────────────────────────────────  │
│  Strategy: Mean Reversion           │
│  Agents: Observer + Risk Manager    │
│  ─────────────────────────────────  │
│  💬 Thread created for discussion   │
└─────────────────────────────────────┘
```

**Thread Features:**
- Auto-created per trade for community discussion
- Trade updates posted in the same thread
- Educational explanations shared in threads
- Post-mortem analysis after trade closes

### 7.3 WhatsApp (Mobile Alerts)

Clean, text-only format (no markdown tables, no complex formatting):

```
✅ TRADE OPENED — GBP/JPY SHORT

Entry: 189.450
Stop Loss: 189.850 (40 pips)
TP1: 189.050 | TP2: 188.650
Lot Size: 0.15 (1.5% risk)
Confidence: 78%

I'll manage this and keep you updated.
Reply "status" anytime for updates.
```

**WhatsApp Rules:**
- No markdown tables (rendering issues)
- No inline keyboards (use numbered reply options)
- Keep messages under 300 words
- Use simple emoji for visual structure
- Support quick-reply patterns: "1" = yes, "2" = no

### 7.4 Signal (Encrypted Channel)

Minimal formatting, maximum privacy:

```
TRADE: GBP/JPY SHORT
Entry: 189.450
SL: 189.850
TP: 189.050/188.650
Risk: 1.5%
Status: OPEN

Reply: Y/N to approve next signal
```

### 7.5 Email (Reports)

Full HTML reports with charts, tables, and attachments:

```
Subject: Alpha Stack Daily Report — Jan 15, 2024 (+$234.50)

[HTML Email Body]
- Performance summary table
- Equity curve chart (embedded image)
- Individual trade breakdown
- Agent activity log
- Tomorrow's outlook
- Attached: Trade journal CSV, Performance PDF
```

---

## 8. OpenClaw Integration Layer

### 8.1 Architecture with OpenClaw

Alpha Stack leverages OpenClaw as the **channel abstraction layer**. The trading system doesn't need to know about Telegram APIs or Discord bots — it just emits events, and OpenClaw routes them.

```
Alpha Stack Core
       │
       ▼
┌──────────────────────┐
│  Notification Engine  │
│  (Event → Message)    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   OpenClaw Gateway    │
│  ┌────────────────┐  │
│  │  Session Router  │  │
│  │  (per-channel)   │  │
│  └────────┬─────────┘  │
│           │            │
│  ┌────────▼─────────┐  │
│  │ Channel Adapters  │  │
│  │ • Telegram Bot    │  │
│  │ • Discord Bot     │  │
│  │ • WhatsApp API    │  │
│  │ • Signal (Matrix) │  │
│  │ • Email (SMTP)    │  │
│  └──────────────────┘  │
└──────────────────────┘
```

### 8.2 OpenClaw Channel Configuration

#### Telegram (Primary)

```yaml
# In openclaw.json — channels.telegram
channels:
  telegram:
    token: "${TELEGRAM_BOT_TOKEN}"
    allowedFrom:
      - "telegram:user:${TRADER_CHAT_ID}"
    dmPolicy: "pairing"  # or "open" for pre-approved traders
    features:
      inlineButtons: true
      media: true
```

#### Discord (Community)

```yaml
channels:
  discord:
    token: "${DISCORD_BOT_TOKEN}"
    allowedFrom:
      - "discord:guild:${GUILD_ID}"
    features:
      threads: true
      embeds: true
      reactions: true
```

#### WhatsApp (Mobile)

```yaml
channels:
  whatsapp:
    provider: "twilio"  # or "meta" for WhatsApp Business API
    accountSid: "${TWILIO_ACCOUNT_SID}"
    authToken: "${TWILIO_AUTH_TOKEN}"
    from: "${WHATSAPP_FROM_NUMBER}"
    allowedFrom:
      - "whatsapp:${TRADER_PHONE}"
```

### 8.3 Message Delivery Patterns

#### Direct Notification (Agent → Trader)

```python
# Alpha Stack emits an event
notification_engine.emit(
    event=TradeEntered(
        pair="GBP/JPY",
        direction="SHORT",
        entry=189.450,
        sl=189.850,
        tp=[189.050, 188.650],
        lot_size=0.15,
        confidence=0.78,
        reasoning="Mean reversion at daily resistance..."
    ),
    priority=NotificationPriority.HIGH
)
```

#### Interactive Command (Trader → Agent)

```python
# Trader sends "/positions" via Telegram
# OpenClaw routes to Alpha Stack agent session
# Agent queries position manager and responds

# OpenClaw cron for scheduled reports
cron.add(
    schedule="0 22 * * 1-5",  # 10 PM UTC, weekdays
    sessionTarget="isolated",
    payload={
        "kind": "agentTurn",
        "message": "Generate and deliver the daily trading report"
    },
    delivery={
        "mode": "announce",
        "channel": "telegram",
        "to": f"telegram:user:{TRADER_CHAT_ID}"
    }
)
```

### 8.4 Multi-Agent Session Routing

OpenClaw supports routing different channels/accounts to different agent sessions:

```yaml
agents:
  routing:
    # Main trading agent — handles all trader commands
    - match:
        channel: "telegram"
        from: "telegram:user:${TRADER_CHAT_ID}"
      agent: "alpha-stack-main"

    # Community agent — handles Discord interactions
    - match:
        channel: "discord"
        from: "discord:guild:${GUILD_ID}"
      agent: "alpha-stack-community"

    # Alert-only agent — WhatsApp, read-only
    - match:
        channel: "whatsapp"
      agent: "alpha-stack-alerts"
```

### 8.5 Chart & Media Delivery

```python
# Generate chart
chart_path = chart_engine.render(
    pair="GBP/JPY",
    timeframe="H1",
    indicators=["EMA20", "EMA50", "RSI"],
    levels={"entry": 189.450, "sl": 189.850, "tp1": 189.050},
    output_path="/home/work/.openclaw/workspace/charts/gbpjpy_h1.png"
)

# OpenClaw handles media delivery per channel:
# - Telegram: sends as photo with caption
# - Discord: sends as embed image
# - WhatsApp: sends as image message
# - Signal: sends as attachment
```

---

## 9. Notification Engine — Internal Design

### 9.1 Event Bus Architecture

```
┌─────────────────────────────────────────────────┐
│                  EVENT BUS                       │
│                                                  │
│  Events In:                                      │
│  • strategy.signal_detected                      │
│  • execution.trade_opened                        │
│  • execution.trade_closed                        │
│  • execution.trade_updated                       │
│  • risk.drawdown_warning                         │
│  • risk.circuit_breaker                          │
│  • risk.black_swan                               │
│  • agent.status_update                           │
│  • agent.decision_explained                      │
│  • regime.changed                                │
│  • news.high_impact                              │
│  • report.daily                                  │
│  • report.weekly                                 │
│                                                  │
│  Processing Pipeline:                            │
│  1. Classify priority (P0-P3)                    │
│  2. Format message per channel                   │
│  3. Apply quiet hours filter                     │
│  4. Apply batching rules (P2/P3)                 │
│  5. Route to OpenClaw Gateway                    │
│  6. Track delivery & acknowledgment              │
│                                                  │
│  Events Out:                                     │
│  • channel.delivered                             │
│  • channel.acknowledged                          │
│  • channel.failed (retry logic)                  │
└─────────────────────────────────────────────────┘
```

### 9.2 Message Template System

```python
# Templates are channel-aware
templates = {
    "trade_opened": {
        "telegram": "templates/trade_opened_telegram.md",
        "discord": "templates/trade_opened_discord.md",
        "whatsapp": "templates/trade_opened_whatsapp.txt",
        "signal": "templates/trade_opened_signal.txt",
        "email": "templates/trade_opened_email.html",
    },
    "daily_report": {
        "telegram": "templates/daily_telegram.md",
        "email": "templates/daily_email.html",
    }
}

def format_message(event_type, channel, data):
    template = load_template(templates[event_type][channel])
    return template.render(**data)
```

### 9.3 Delivery Tracking & Retry

```python
class DeliveryTracker:
    def track(self, notification_id, channel, status):
        # Store in SQLite for audit trail
        db.insert("deliveries", {
            "id": notification_id,
            "channel": channel,
            "status": status,  # sent, delivered, failed, acked
            "timestamp": datetime.utcnow(),
            "retry_count": 0
        })

    def retry_failed(self):
        # Retry P0/P1 failures up to 5 times with exponential backoff
        failed = db.query("deliveries", status="failed", priority__in=[0, 1])
        for delivery in failed:
            if delivery.retry_count < 5:
                backoff = 2 ** delivery.retry_count  # 1s, 2s, 4s, 8s, 16s
                schedule_retry(delivery, delay=backoff)
```

### 9.4 Acknowledgment System (P0 Events)

```
For P0 events, the system requires acknowledgment:

1. Send notification to ALL channels
2. Start 5-minute ack timer
3. If no ack received:
   a. Re-send to all channels
   b. Escalate: send SMS via Twilio (if configured)
   c. Log: "UNACKNOWLEDGED CRITICAL EVENT" in system journal
4. Trader acks by replying "OK" or tapping [Acknowledge] button
5. Log acknowledgment with timestamp
```

---

## 10. Security & Access Control

### 10.1 Channel Authentication

```
Each channel has its own authentication layer:

Telegram:  Chat ID whitelist + pairing verification
Discord:   Guild + role-based access
WhatsApp:  Phone number whitelist
Signal:    Phone number + safety number verification
Email:     Encrypted reports (PGP optional)
```

### 10.2 Command Authorization

```
Read Commands (positions, balance, pnl):
  → Any authenticated user on any channel

Control Commands (pause, resume, close):
  → Primary user only (Telegram chat ID)
  → Requires confirmation for destructive actions

Admin Commands (risk settings, autonomy level):
  → Primary user only
  → Changes logged with timestamp and reason
```

### 10.3 Data Sensitivity by Channel

| Data Type | Telegram | Discord | WhatsApp | Signal | Email |
|-----------|----------|---------|----------|--------|-------|
| Signals | ✅ | ✅ (community) | ✅ | ✅ | ❌ |
| Trade entries | ✅ | ✅ (public) | ✅ | ✅ | ✅ |
| P&L amounts | ✅ | ❌ (private) | ✅ | ✅ | ✅ |
| Account balance | ✅ | ❌ | ✅ | ✅ | ✅ |
| API keys | ❌ | ❌ | ❌ | ❌ | ❌ |
| Risk settings | ✅ | ❌ | ❌ | ✅ | ✅ |

**Rule: Financial details (balance, P&L, positions) are NEVER sent to public/community channels.**

---

## 11. Implementation Roadmap

### Phase 1: Foundation (Weeks 1–2)

- [ ] Build notification engine event bus
- [ ] Implement message template system
- [ ] Set up Telegram bot as primary channel via OpenClaw
- [ ] Basic commands: /positions, /balance, /pnl, /pause, /resume
- [ ] P0/P1 priority routing

### Phase 2: Trade Lifecycle (Weeks 3–4)

- [ ] Full trade event notifications (open, manage, close)
- [ ] Chart generation and delivery
- [ ] Interactive inline keyboards (Telegram)
- [ ] Signal approval/rejection flow
- [ ] Delivery tracking and retry logic

### Phase 3: Multi-Channel (Weeks 5–6)

- [ ] WhatsApp integration via Twilio
- [ ] Discord bot with community features
- [ ] Channel-specific formatting engine
- [ ] Quiet hours and batching system
- [ ] Daily/weekly report generation

### Phase 4: Progressive Autonomy (Weeks 7–8)

- [ ] Autonomy level system (1–4)
- [ ] Trust progression tracking
- [ ] Natural language command parsing
- [ ] Trade journal and post-mortem automation
- [ ] Educational content delivery

### Phase 5: Advanced Features (Weeks 9–10)

- [ ] Signal channel (encrypted)
- [ ] Email reports with charts and attachments
- [ ] Cross-channel state sync
- [ ] Acknowledgment escalation (SMS fallback)
- [ ] Performance analytics dashboard link

### Phase 6: Polish & Scale (Weeks 11–12)

- [ ] End-to-end testing across all channels
- [ ] Load testing (notification burst scenarios)
- [ ] Documentation for traders
- [ ] Onboarding flow per channel
- [ ] Monitoring and alerting for the notification system itself

---

## Appendix A: OpenClaw Cron Jobs for Scheduled Reports

```python
# Daily report at 22:00 UTC (after US market close)
cron.add(
    name="daily-report",
    schedule={"kind": "cron", "expr": "0 22 * * 1-5", "tz": "UTC"},
    sessionTarget="isolated",
    payload={
        "kind": "agentTurn",
        "message": "Generate the daily trading report. Include: "
                   "trades taken, P&L, win rate, agent decisions, "
                   "key lessons, and tomorrow's outlook. "
                   "Format for Telegram with markdown."
    },
    delivery={
        "mode": "announce",
        "channel": "telegram",
        "to": f"telegram:user:{TRADER_CHAT_ID}"
    }
)

# Weekly report on Sunday
cron.add(
    name="weekly-report",
    schedule={"kind": "cron", "expr": "0 18 * * 0", "tz": "UTC"},
    sessionTarget="isolated",
    payload={
        "kind": "agentTurn",
        "message": "Generate the weekly trading report. Include: "
                   "weekly P&L, trade statistics, strategy performance, "
                   "risk metrics, agent efficiency, and next week outlook."
    },
    delivery={
        "mode": "announce",
        "channel": "email",
        "to": f"email:{TRADER_EMAIL}"
    }
)
```

## Appendix B: Emergency Contact Flow

```
Circuit Breaker Triggered:
  1. Close all positions immediately
  2. P0 notification → ALL channels
  3. Start 5-min ack timer
  4. If no ack → SMS via Twilio
  5. If no ack after 15 min → Log "UNACKNOWLEDGED EMERGENCY"
  6. System remains in SAFE MODE until manual restart

Black Swan Event:
  1. Close all positions immediately
  2. P0 notification → ALL channels
  3. Pause all automated trading
  4. Freeze all pending signals
  5. Require explicit "/resume" to restart
  6. Generate emergency report with all actions taken
```

---

*This architecture ensures that Alpha Stack traders have institutional-grade visibility and control — from anywhere, on any device, through any channel they prefer. The system is transparent by default, secure by design, and always puts the trader in control.*
