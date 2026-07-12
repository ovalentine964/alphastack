# Alpha Stack — Desktop Application UI Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/platform/research_12_desktop_app_architecture.md`](../research/platform/research_12_desktop_app_architecture.md) — Desktop app architecture (Tauri-based)
> **Status:** Architecture Complete

---

> **Author:** Desktop UI Architect  
> **Date:** 2026-07-11  
> **Version:** 1.0  
> **Status:** Architecture Design — Pre-Implementation  
> **Platform:** Tauri 2.x (Rust backend + React/TypeScript frontend)  
> **Targets:** Linux (Pop!_OS 24.04), Windows 10/11, macOS 12+

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Layout Architecture](#2-layout-architecture)
3. [Dashboard View](#3-dashboard-view)
4. [Chart Integration](#4-chart-integration)
5. [Trade Management UI](#5-trade-management-ui)
6. [Settings UI](#6-settings-ui)
7. [Agent Monitoring UI](#7-agent-monitoring-ui)
8. [Journal UI](#8-journal-ui)
9. [System Tray Integration](#9-system-tray-integration)
10. [Dark Mode & Theming](#10-dark-mode--theming)
11. [Responsive Design](#11-responsive-design)
12. [Platform-Specific Considerations](#12-platform-specific-considerations)
13. [Component Architecture](#13-component-architecture)
14. [State Management](#14-state-management)
15. [Real-Time Data Pipeline](#15-real-time-data-pipeline)
16. [Keyboard Shortcuts & Power User Features](#16-keyboard-shortcuts--power-user-features)
17. [Accessibility](#17-accessibility)
18. [Performance Budget](#18-performance-budget)
19. [Implementation Roadmap](#19-implementation-roadmap)

---

## 1. Design Philosophy

### 1.1 Core Principles

| Principle | Rationale |
|-----------|-----------|
| **Information density > visual aesthetics** | Traders want data, not whitespace. Bloomberg Terminal is the gold standard. |
| **Dark mode is not optional** | Every serious trading platform defaults to dark. Traders stare at screens for hours. |
| **Zero-friction execution** | Signal → order in ≤2 clicks. Keyboard shortcuts for every critical action. |
| **Real-time everything** | Prices, P&L, margin, signals — all update live. No manual refresh. |
| **Graceful degradation** | If any subsystem fails, the UI shows clear status and continues functioning. |
| **Persistent workspace** | Layout, panel sizes, watchlists — all saved and restored across sessions. |
| **Agent transparency** | Users must see what each AI agent is doing, why, and with what confidence. |

### 1.2 Design System Foundation

```
Design Tokens
├── Colors (dark-first palette)
│   ├── Background:    #0a0a1a (base), #111827 (surface), #1f2937 (elevated)
│   ├── Text:          #f9fafb (primary), #9ca3af (secondary), #6b7280 (muted)
│   ├── Accent:        #3b82f6 (blue — primary actions)
│   ├── Profit:        #22c55e (green — positive P&L, buy signals)
│   ├── Loss:          #ef4444 (red — negative P&L, sell signals)
│   ├── Warning:       #f59e0b (amber — caution states)
│   └── Neutral:       #6b7280 (gray — pending/inactive)
├── Typography
│   ├── Font Family:   Inter (UI), JetBrains Mono (prices, code, logs)
│   ├── Price Display:  Tabular nums, monospace, 14-24px
│   └── Scale:         12/14/16/20/24/32px
├── Spacing:           4px base unit (4/8/12/16/24/32/48/64)
├── Borders:           1px solid rgba(255,255,255,0.06) — subtle separation
├── Radius:            6px (cards), 4px (buttons), 8px (modals)
└── Shadows:           Minimal — dark UI relies on elevation via background shades
```

---

## 2. Layout Architecture

### 2.1 Root Layout Structure

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    TITLEBAR (custom, platform-adaptive)            │  │
│  │  [≡ Alpha Stack]    [Dashboard] [Trades] [Analytics] [Agents] [⚙] │  │
│  │                              [🔔 3] [⏸ Trading Active] [─][□][×]  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    STATUS RIBBON (always visible)                   │  │
│  │  Balance: $7.23 │ Equity: $7.18 │ P&L Today: +$0.23 (3.3%) │ 🟢  │  │
│  │  Positions: 2 │ Signals: 3 │ Agent: Orchestrator — Idle │ v1.2.0  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────┬─────────────────────────────────────────────────────────┐   │
│  │        │                                                          │   │
│  │  NAV   │                    MAIN CONTENT AREA                     │   │
│  │  RAIL  │              (page-specific, see below)                  │   │
│  │        │                                                          │   │
│  │  📊    │                                                          │   │
│  │  📈    │                                                          │   │
│  │  🔄    │                                                          │   │
│  │  🤖    │                                                          │   │
│  │  📔    │                                                          │   │
│  │  ⚙    │                                                          │   │
│  │        │                                                          │   │
│  └────────┴─────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    FOOTER BAR (optional, toggleable)                │  │
│  │  [Log: 14:32:21 EURUSD BUY signal — confidence 82%] [Clear] [▼]   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Navigation Architecture

**Primary Navigation:** Collapsible icon rail (left side, 48px expanded / 64px collapsed)

| Icon | Page | Description |
|------|------|-------------|
| 📊 | Dashboard | Main trading view — charts, positions, signals |
| 📈 | Trades | Position management, order entry, pending orders |
| 🔄 | Analytics | Performance metrics, equity curve, P&L analysis |
| 🤖 | Agents | Multi-agent system monitoring |
| 📔 | Journal | Trade history, AI-generated notes, backtesting |
| ⚙ | Settings | Broker config, strategy, risk, notifications, general |

**Secondary Navigation:** Tab bar within each page (top of content area)

**Breadcrumbs:** Disabled — trading apps use flat navigation, not deep hierarchies.

### 2.3 Panel System

The Dashboard and Trades pages use a **resizable multi-panel layout** powered by `react-resizable-panels`:

```
Panel Configuration (persisted per-user):
{
  "dashboard": {
    "direction": "horizontal",
    "panels": [
      { "id": "watchlist", "size": 20, "minSize": 15, "maxSize": 30 },
      { "id": "chart", "size": 50, "minSize": 30 },
      { "id": "sidebar", "size": 30, "minSize": 20, "maxSize": 40 }
    ]
  },
  "trades": {
    "direction": "vertical",
    "panels": [
      { "id": "positions", "size": 60, "minSize": 30 },
      { "id": "order-entry", "size": 40, "minSize": 20 }
    ]
  }
}
```

**Panel behaviors:**
- Drag handles between panels for resizing
- Double-click handle to collapse/expand
- Right-click panel header for "Pop out" (separate window) — future feature
- Layout state persisted to `~/.alphastack/layouts.json`

---

## 3. Dashboard View

### 3.1 Dashboard Layout

The dashboard is the primary screen — it must show everything a trader needs at a glance.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DASHBOARD LAYOUT                                │
├──────────┬──────────────────────────────────────┬───────────────────────┤
│          │                                      │                       │
│ WATCHLIST│         MAIN CHART                   │    SIGNAL PANEL       │
│          │    (TradingView Lightweight Charts)   │                       │
│ EURUSD   │    ┌─────────────────────────────┐   │  🟢 EURUSD BUY       │
│  1.0845  │    │  Candlestick + Volume       │   │  Confidence: 82%     │
│  ▲ +0.12%│    │  Multi-timeframe tabs       │   │  Entry: 1.0845       │
│          │    │  Drawing tools              │   │  SL: 1.0820          │
│ GBPUSD   │    │  Indicator overlays         │   │  TP: 1.0900          │
│  1.2712  │    └─────────────────────────────┘   │  Risk: 1.2%          │
│  ▼ -0.05%│                                      │                       │
│          │                                      │  🟡 GBPUSD SELL       │
│ USDJPY   │                                      │  Confidence: 67%      │
│  149.23  │                                      │  Waiting for confirm  │
│  ▲ +0.08%│                                      │                       │
│          ├──────────────────────────────────────┤  ─────────────────    │
│ XAUUSD   │                                      │                       │
│  2341.50 │     POSITIONS TABLE                  │  AI SUMMARY           │
│  ▲ +0.31%│     (compact, inline P&L)            │                       │
│          │                                      │  Market: Ranging      │
│ BTCUSD   │  EURUSD BUY  0.01  +$0.23  [Close]  │  Regime: Consolidation│
│  57,420  │  XAUUSD SELL 0.01  -$0.05  [Close]  │  Risk: Low            │
│  ▼ -1.2% │                                      │  Volatility: Normal   │
│          │                                      │  Session: London       │
│          │                                      │                       │
├──────────┴──────────────────────────────────────┴───────────────────────┤
│  QUICK TRADE BAR (bottom, always accessible)                            │
│  [EURUSD ▾] [BUY] [SELL] [0.01 lots] [SL: 20 pips] [TP: 50 pips] [→] │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Dashboard Components

#### Watchlist Panel (Left)

```typescript
interface WatchlistItem {
  symbol: string;          // "EURUSD"
  bid: number;             // 1.08450
  ask: number;             // 1.08470
  spread: number;          // 2.0 pips
  change: number;          // +0.00120
  changePercent: number;   // +0.11%
  dayHigh: number;
  dayLow: number;
  signal?: 'BUY' | 'SELL' | null;
  signalConfidence?: number;
}
```

**Features:**
- Real-time bid/ask with color flash on change (green tick up, red tick down)
- Click to load chart for that pair
- Right-click context menu: View Chart, Place Order, Set Alert, Remove
- Drag to reorder
- Group by category (Forex Majors, Forex Minors, Crypto, Metals)
- Search/filter bar at top
- Sparkline mini-chart (last 24h) on hover

#### Main Chart Panel (Center)

See [Section 4: Chart Integration](#4-chart-integration) for full specification.

#### Signal Panel (Right)

Displays active AI signals from the multi-agent system.

```typescript
interface SignalCard {
  id: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  confidence: number;          // 0.0 - 1.0
  entry: number;
  stopLoss: number;
  takeProfit: number;
  riskPercent: number;         // % of account
  agents: {
    fundamental: AgentVerdict;
    structure: AgentVerdict;
    smc: AgentVerdict;
    momentum: AgentVerdict;
    candlestick: AgentVerdict;
  };
  confluenceScore: number;     // 0-100
  timeGenerated: number;       // Unix timestamp
  status: 'pending' | 'confirmed' | 'executed' | 'expired';
}
```

**Signal Card UI:**
```
┌─────────────────────────────────┐
│ 🟢 EURUSD BUY         82% ████ │
│ Entry: 1.0845  SL: 1.0820      │
│ TP: 1.0900   Risk: 1.2%        │
│ Confluence: 78/100              │
│ ┌───────────────────────────┐  │
│ │ F:✓ S:✓ L:✓ SMC:✓ M:✓ C:✓│  │
│ └───────────────────────────┘  │
│ [Execute] [Modify] [Dismiss]   │
│ Generated: 14:32 · 2m ago      │
└─────────────────────────────────┘
```

- Agent verdict indicators: ✓ (agree), ✗ (disagree), ⏳ (pending), — (no data)
- Color-coded confidence bar
- One-click Execute button (with confirmation dialog for high-risk trades)
- Auto-expire after configurable duration (default: 30 min)

#### Positions Table (Bottom-Center)

Compact inline table showing open positions with live P&L.

| Column | Width | Description |
|--------|-------|-------------|
| Symbol | 80px | Pair name with direction icon (▲ BUY / ▼ SELL) |
| Lots | 60px | Position size |
| Entry | 80px | Open price |
| Current | 80px | Current market price (live updating) |
| P&L | 80px | Unrealized P&L in account currency (green/red) |
| P&L % | 60px | Percentage return |
| SL | 80px | Stop loss level |
| TP | 80px | Take profit level |
| Duration | 60px | Time since open |
| Actions | 80px | [Modify] [Close] buttons |

**Features:**
- Row highlights green/red as P&L changes
- Click row to load that pair's chart
- "Close All" button with confirmation
- Total P&L summary row at bottom
- Virtual scrolling for large position sets (unlikely with $7 account, but future-proof)

#### Quick Trade Bar (Bottom)

Always-visible bar for rapid order execution.

```
[Pair: EURUSD ▾] [BUY ●] [SELL ○] [Lots: 0.01 ▾] [SL: 20 pips] [TP: 50 pips] [▶ Execute]
```

- Keyboard-driven: Tab between fields, Enter to execute
- Pre-configured lot sizes from settings
- SL/TP in pips or price (toggle)
- Confirmation required for orders > configured threshold

#### AI Summary Widget (Right, below signals)

Compact text summary of current market state:

```
┌─────────────────────────┐
│ AI MARKET SUMMARY       │
│                         │
│ Regime:    Ranging      │
│ Bias:      Neutral      │
│ Volatility: Normal      │
│ Session:   London       │
│ Risk Level: Low         │
│ Next Event: NFP 14:30   │
└─────────────────────────┘
```

---

## 4. Chart Integration

### 4.1 TradingView Lightweight Charts v5

**Library:** `lightweight-charts@^5.0` (~12 KB gzipped)

**Why Lightweight Charts:**
- Purpose-built for financial time-series
- Canvas rendering — handles hundreds of ticks/second smoothly
- Native dark mode (dark background default)
- Open-source, no license fees
- Supports candlestick, line, area, histogram, baseline series

### 4.2 Chart Component Architecture

```typescript
// src/components/charts/PriceChart.tsx

interface PriceChartProps {
  symbol: string;
  timeframe: Timeframe;           // 'M1' | 'M5' | 'M15' | 'H1' | 'H4' | 'D1' | 'W1'
  data: OHLCV[];                  // Historical candles
  studies?: StudyOverlay[];       // RSI, MACD, Bollinger, etc.
  markers?: TradeMarker[];        // Entry/exit markers on chart
  drawings?: DrawingObject[];     // User-drawn lines, rectangles, fibs
  onCrosshairMove?: (params: CrosshairParams) => void;
  onTimeRangeChange?: (range: TimeRange) => void;
}
```

### 4.3 Chart Features

```
┌──────────────────────────────────────────────────────────────────────┐
│  CHART HEADER                                                         │
│  [EURUSD] [M1] [M5] [M15] [H1] [H4] [D1] [W1] │ [Indicators ▾]     │
│  [Drawing Tools] [Screenshot] [Fullscreen] [Pop Out] [Settings ⚙]   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   1.0850 ┤                           ╭─╮                             │
│          │                          ╭╯ │                             │
│   1.0845 ┤        ╭──╮    ╭──╮   ╭─╯  │    ← Candlestick Series    │
│          │       ╭╯  ╰╮  ╭╯  ╰╮╭╯    │                             │
│   1.0840 ┤    ╭──╯    ╰──╯    ╰╯     │    ← Volume Histogram       │
│          │   ╭╯                       │       (bottom, semi-transparent)
│   1.0835 ┤───╯                        │                             │
│          │                            │    ← SMA 20 (blue line)     │
│          ├────┬────┬────┬────┬────┬───┤    ← SMA 50 (orange line)  │
│          10:00 10:15 10:30 10:45 11:00│                             │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  RSI (14)   65.2 ───────────────────────────────────           │ │
│  │  ─────────────────────────────── 70 ───── Overbought           │ │
│  │                           ╭──╮                                  │ │
│  │  ───────────────── 30 ── ╯    ╰── ────── Oversold              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  CROSSHAIR INFO (follows cursor):                                    │
│  O: 1.0842  H: 1.0851  L: 1.0838  C: 1.0845  V: 1,234  +0.03%     │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.4 Supported Chart Types

| Type | Implementation | Use Case |
|------|---------------|----------|
| Candlestick | `addCandlestickSeries()` | Primary price chart |
| Line | `addLineSeries()` | Close price, moving averages |
| Area | `addAreaSeries()` | Fill under price line |
| Histogram | `addHistogramSeries()` | Volume bars |
| Baseline | `addBaselineSeries()` | Zero-line reference (P&L) |
| Bar | `addBarSeries()` | OHLC bars (alternative to candlestick) |

### 4.5 Technical Indicator Overlays

Indicators rendered as additional series on the chart:

| Indicator | Type | Default |
|-----------|------|---------|
| SMA (20, 50, 200) | Line overlay | SMA 20 enabled |
| EMA (12, 26) | Line overlay | Disabled |
| Bollinger Bands (20, 2) | Area + lines | Disabled |
| VWAP | Line overlay | Disabled |
| Support/Resistance zones | Horizontal areas | Auto-detected by SMC Agent |
| Order Blocks | Highlighted rectangles | From SMC Agent |
| FVG (Fair Value Gaps) | Highlighted rectangles | From SMC Agent |
| Liquidity Pools | Horizontal lines | From Liquidity Agent |

**Sub-chart indicators (separate pane below price):**

| Indicator | Pane | Default |
|-----------|------|---------|
| RSI (14) | Sub-chart | Enabled |
| MACD (12, 26, 9) | Sub-chart | Disabled |
| Stochastic RSI | Sub-chart | Disabled |
| ATR (14) | Sub-chart | Disabled |

### 4.6 Drawing Tools

User-drawn annotations persisted per symbol:

| Tool | Shortcut | Description |
|------|----------|-------------|
| Horizontal Line | `H` | Support/resistance level |
| Trend Line | `T` | Diagonal trend line |
| Rectangle | `R` | Highlight zone |
| Fibonacci Retracement | `F` | Auto-draw fib levels |
| Extended Line | `E` | Line extending to right edge |
| Text Annotation | `A` | Add text note |
| Arrow | `W` | Directional arrow |
| Delete | `Del` | Remove selected drawing |
| Delete All | `Shift+Del` | Clear all drawings on chart |

**Persistence:** Drawings saved to `~/.alphastack/drawings/{symbol}.json`

### 4.7 Multi-Chart Layouts

Support configurable grid layouts:

```
Layout options:
┌──────┐  ┌──────┬──────┐  ┌──────┬──────┐  ┌──────┬──────┐
│      │  │      │      │  │      │      │  │      │      │
│ 1×1  │  │ 2×1  │      │  │ 2×2  │      │  │ 3×2  │      │
│      │  │      │      │  │      │      │  │      │      │
└──────┘  └──────┴──────┘  ├──────┼──────┤  ├──────┼──────┤
                           │      │      │  │      │      │
                           │      │      │  │      │      │
                           └──────┴──────┘  ├──────┼──────┤
                                           │      │      │
                                           └──────┴──────┘
```

- Each pane can show different symbol/timeframe
- Crosshair sync across panes (optional)
- Link panes so clicking a symbol in watchlist updates all linked panes
- Layout presets saved and switchable

### 4.8 Real-Time Chart Updates

```typescript
// Efficient real-time candle updates
function updateChart(chart: IChartApi, tick: TickData) {
  const series = chart.serieses()[0]; // candlestick series
  const lastBar = series.data().slice(-1)[0];

  if (tick.time > lastBar.time + timeframeSeconds) {
    // New candle
    series.update({
      time: tick.time,
      open: tick.price,
      high: tick.price,
      low: tick.price,
      close: tick.price,
      volume: tick.volume,
    });
  } else {
    // Update current candle
    series.update({
      time: lastBar.time,
      open: lastBar.open,
      high: Math.max(lastBar.high, tick.price),
      low: Math.min(lastBar.low, tick.price),
      close: tick.price,
      volume: (lastBar.volume || 0) + tick.volume,
    });
  }
}
```

**Performance target:** Handle 100+ ticks/second without frame drops.

---

## 5. Trade Management UI

### 5.1 Order Entry Panel

```
┌──────────────────────────────────────────────────────────┐
│  ORDER ENTRY                                    [×]      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Symbol:     [EURUSD                              ▾]     │
│                                                          │
│  Direction:  (●) BUY    (○) SELL                        │
│                                                          │
│  Type:       (●) Market  (○) Limit  (○) Stop            │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Lots:       [0.01    ]  [−] [+]  (min: 0.01)      │ │
│  │                                                     │ │
│  │  Entry Price: [1.08450  ]  (disabled for market)    │ │
│  │                                                     │ │
│  │  Stop Loss:   [1.08200  ]  (25 pips / $0.25)       │ │
│  │  Take Profit: [1.09000  ]  (55 pips / $0.55)       │ │
│  │                                                     │ │
│  │  Risk: 1.2% of account ($0.09)                     │ │
│  │  R:R Ratio: 1:2.2                                  │ │
│  │  Spread: 1.8 pips                                  │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  QUICK SIZING                                      │ │
│  │  [0.5% risk] [1% risk] [2% risk] [Custom]          │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  [  ▶  EXECUTE BUY ORDER  ]    [Save as Template]       │
│                                                          │
│  ⚠️ This will risk $0.09 (1.2% of $7.23 account)       │
└──────────────────────────────────────────────────────────┘
```

**Features:**
- Auto-calculates lot size based on risk % and SL distance
- R:R ratio display (reward-to-risk)
- Spread cost display
- Quick sizing buttons: 0.5%, 1%, 2% risk presets
- Order templates: save/load common configurations
- Confirmation dialog with risk summary before execution
- Keyboard shortcut: `B` for quick buy, `S` for quick sell (using defaults)

### 5.2 Position Management

Active positions displayed in a feature-rich table:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ACTIVE POSITIONS (2)                              [Close All] [Export CSV] │
├────────┬─────┬─────────┬─────────┬──────────┬────────┬───────┬────────────┤
│ Symbol │ Dir │  Lots   │  Entry  │ Current  │  P&L   │  SL   │   Actions  │
├────────┼─────┼─────────┼─────────┼──────────┼────────┼───────┼────────────┤
│ EURUSD │ BUY │  0.01   │ 1.08420 │ 1.08450  │ +$0.23 │1.08200│ [Mod][Close]│
│        │     │         │         │          │  +28%  │       │ [Trail]     │
├────────┼─────┼─────────┼─────────┼──────────┼────────┼───────┼────────────┤
│ XAUUSD │SELL │  0.01   │ 2345.50 │ 2341.50  │ -$0.05 │2355.00│ [Mod][Close]│
│        │     │         │         │          │  -4%   │       │ [Trail]     │
├────────┴─────┴─────────┴─────────┴──────────┼────────┴───────┴────────────┤
│                                              │ TOTAL: +$0.18 (+2.5%)      │
└──────────────────────────────────────────────┴────────────────────────────┘
```

**Position Actions:**

| Action | Description |
|--------|-------------|
| **Modify** | Change SL/TP levels (drag on chart or type in dialog) |
| **Close** | Close position at market (with confirmation) |
| **Trail** | Enable trailing stop (configurable distance in pips) |
| **Partial Close** | Close a portion of the position |
| **Reverse** | Close and open opposite direction |

**Visual SL/TP on Chart:**
- SL displayed as red dashed horizontal line on chart
- TP displayed as green dashed horizontal line on chart
- Drag lines to modify levels directly on chart
- Entry price shown as blue solid line

### 5.3 Pending Orders

```
┌──────────────────────────────────────────────────────────────────────┐
│  PENDING ORDERS (1)                                     [New Order] │
├────────┬───────┬─────────┬──────────┬──────────┬─────────┬─────────┤
│ Symbol │ Type  │  Lots   │  Price   │    SL    │   TP    │ Actions │
├────────┼───────┼─────────┼──────────┼──────────┼─────────┼─────────┤
│ GBPUSD │ Limit │  0.01   │ 1.26800  │ 1.26500  │ 1.27400 │ [C][D]  │
│        │  BUY │         │          │          │         │         │
└────────┴───────┴─────────┴──────────┴──────────┴─────────┴─────────┘
```

### 5.4 Trade Execution Flow

```
User clicks "Execute"
    │
    ├── 1. Client-side validation
    │   ├── Symbol tradeable? → reject if not
    │   ├── Lot size within limits? → reject if not
    │   ├── SL/TP valid distance? → reject if not
    │   └── Sufficient margin? → reject if not
    │
    ├── 2. Show confirmation dialog
    │   └── "BUY 0.01 EURUSD @ Market · SL: 1.0820 · TP: 1.0900 · Risk: $0.09"
    │
    ├── 3. User confirms
    │   └── Invoke Tauri command: `place_order`
    │
    ├── 4. Rust backend
    │   ├── Risk gate check (max positions, max drawdown, correlation)
    │   ├── Forward to Python sidecar → MT5
    │   └── Return result
    │
    ├── 5. Success
    │   ├── Update positions table
    │   ├── Show toast notification: "BUY EURUSD filled @ 1.08452"
    │   ├── Play sound (configurable)
    │   ├── Add entry marker on chart
    │   └── Log to journal
    │
    └── 6. Failure
        ├── Show error toast: "Order rejected: Insufficient margin"
        └── Log error
```

---

## 6. Settings UI

### 6.1 Settings Navigation

```
┌──────────────────────────────────────────────────────────────────┐
│  SETTINGS                                                        │
├──────────┬───────────────────────────────────────────────────────┤
│          │                                                       │
│ General  │  ┌─────────────────────────────────────────────────┐ │
│ Broker   │  │  BROKER CONNECTION                              │ │
│ Strategy │  │                                                 │ │
│ Risk     │  │  Platform:     MetaTrader 5                     │ │
│ Notify   │  │  Connection:   ● Connected (FXPesa-Live)       │ │
│ Display  │  │  Account:      12345678                         │ │
│ Advanced │  │  Balance:      $7.23                            │ │
│          │  │  Server:       FXPesa-Live                      │ │
│          │  │                                                 │ │
│          │  │  [Test Connection]  [Reconnect]  [Disconnect]   │ │
│          │  │                                                 │ │
│          │  │  ─── MT5 Settings (Linux) ───                   │ │
│          │  │  MT5 Path:    ~/.wine/.../terminal64.exe        │ │
│          │  │  Wine Prefix: ~/.local/share/bottles/...        │ │
│          │  │  Bridge Port: 9224                              │ │
│          │  │                                                 │ │
│          │  │  [Auto-detect MT5]  [Browse...]                 │ │
│          │  └─────────────────────────────────────────────────┘ │
│          │                                                       │
└──────────┴───────────────────────────────────────────────────────┘
```

### 6.2 Settings Pages

#### General Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| App Language | Select | English | UI language |
| Theme | Select | Dark | Dark / Light / System |
| Startup Behavior | Select | Minimize to tray | Launch on boot, show window, minimize to tray |
| Auto-update | Toggle | On | Check for updates automatically |
| Log Level | Select | Info | Debug / Info / Warn / Error |
| Data Directory | Path | `~/.alphastack/` | Where to store data files |
| Clear Cache | Button | — | Clear cached market data |

#### Broker Connection Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Platform | Select | MT5 | MetaTrader 5 (future: cTrader, OANDA) |
| Login | Number | — | MT5 account number |
| Password | Password | — | Stored in OS keychain |
| Server | Text | FXPesa-Live | Broker server name |
| MT5 Path | Path | Auto-detect | Path to MT5 terminal (Linux/Wine) |
| Connection Mode | Select | Local | Local / Cloud VPS |
| VPS Address | Text | — | If using cloud MT5 |
| Bridge Port | Number | 9224 | Local TCP port for MT5 bridge |

#### Strategy Configuration

```
┌──────────────────────────────────────────────────────────────┐
│  STRATEGY CONFIGURATION                                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Active Strategy: [Alpha Strategy v1.0 ▾]                    │
│                                                              │
│  ─── Signal Generation ───                                   │
│                                                              │
│  Min Confluence Score:  [65]  (0-100, higher = fewer trades) │
│  Min Agent Agreement:   [4/6] (how many agents must agree)   │
│  Signal Expiry:         [30]  minutes                        │
│                                                              │
│  ─── Agent Weights ───                                       │
│                                                              │
│  Fundamental:   [0.15] ████████░░░░░░░░░░░░                  │
│  Structure:     [0.20] ██████████░░░░░░░░░░                  │
│  Liquidity:     [0.15] ████████░░░░░░░░░░░░                  │
│  SMC:           [0.20] ██████████░░░░░░░░░░                  │
│  Momentum:      [0.15] ████████░░░░░░░░░░░░                  │
│  Candlestick:   [0.15] ████████░░░░░░░░░░░░                  │
│  Total: 1.00 ✓                                               │
│                                                              │
│  ─── Session Filters ───                                     │
│                                                              │
│  [✓] Asian Session    (00:00-08:00 UTC)                      │
│  [✓] London Session   (08:00-16:00 UTC)                      │
│  [✓] New York Session (13:00-21:00 UTC)                      │
│  [✗] Off-hours        (reduced liquidity)                    │
│                                                              │
│  ─── Symbol Filters ───                                      │
│                                                              │
│  [✓] EURUSD  [✓] GBPUSD  [✓] USDJPY  [✓] XAUUSD            │
│  [✓] AUDUSD  [✓] USDCAD  [✓] NZDUSD  [✗] BTCUSD            │
│                                                              │
│  [Reset to Defaults]  [Export Config]  [Import Config]       │
└──────────────────────────────────────────────────────────────┘
```

#### Risk Management Settings

```
┌──────────────────────────────────────────────────────────────┐
│  RISK MANAGEMENT                                             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ─── Position Sizing ───                                     │
│                                                              │
│  Risk per Trade:        [1.0] % of account                   │
│  Max Open Positions:    [3]                                  │
│  Max Lot Size:          [0.05]                               │
│  Min Lot Size:          [0.01]                               │
│                                                              │
│  ─── Drawdown Limits ───                                     │
│                                                              │
│  Max Daily Drawdown:    [5.0] % → Pause trading              │
│  Max Total Drawdown:    [15.0] % → Emergency stop            │
│  Daily Loss Limit:      [$0.50]                              │
│                                                              │
│  ─── Correlation Control ───                                 │
│                                                              │
│  Max Correlated Pairs:  [2]  (e.g., EURUSD + GBPUSD)         │
│  Correlation Threshold: [0.7]                                │
│                                                              │
│  ─── Emergency Controls ───                                  │
│                                                              │
│  [🔴 CLOSE ALL POSITIONS]  [⏸ PAUSE ALL TRADING]            │
│                                                              │
│  These buttons bypass all confirmations. Use with caution.   │
└──────────────────────────────────────────────────────────────┘
```

#### Notification Settings

| Notification Type | Desktop | Sound | Telegram | Email |
|-------------------|---------|-------|----------|-------|
| New Signal | ✓ | ✓ | ✓ | ✗ |
| Trade Opened | ✓ | ✓ | ✓ | ✗ |
| Trade Closed | ✓ | ✓ | ✓ | ✗ |
| Stop Loss Hit | ✓ | ✓ | ✓ | ✓ |
| Daily P&L Summary | ✓ | ✗ | ✓ | ✓ |
| Drawdown Warning | ✓ | ✓ | ✓ | ✓ |
| System Error | ✓ | ✓ | ✓ | ✓ |
| Agent Failure | ✓ | ✓ | ✓ | ✗ |
| Connection Lost | ✓ | ✓ | ✓ | ✓ |

**Notification Sound Options:**
- Default sounds: signal_alert.wav, trade_open.wav, trade_close.wav, warning.wav, error.wav
- Custom sounds: user can upload .wav/.mp3 files
- Volume slider per notification type
- Mute all toggle

---

## 7. Agent Monitoring UI

### 7.1 Agent Dashboard

This page provides full transparency into the multi-agent system — what each agent is doing, its current state, and its reasoning.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  AGENT MONITOR                                          [Refresh] [Log]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌── ORCHESTRATOR ──────────────────────────────────────────────────┐  │
│  │  Status: ● Idle          Last Action: 14:32 — Routed EURUSD BUY │  │
│  │  Queue: 0 pending        Uptime: 4h 23m                         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐       │
│  │ FUNDAMENTAL      │ │ STRUCTURE        │ │ LIQUIDITY        │       │
│  │ ● Idle           │ │ ● Analyzing      │ │ ● Idle           │       │
│  │ Last: 14:30      │ │ EURUSD H1        │ │ Last: 14:28      │       │
│  │ Bias: Neutral    │ │ Regime: Range    │ │ Pools: 3 active  │       │
│  │ Confidence: 62%  │ │ Confidence: 71%  │ │ Confidence: —    │       │
│  │ [View Log]       │ │ [View Log]       │ │ [View Log]       │       │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘       │
│                                                                         │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐       │
│  │ SMC              │ │ MOMENTUM         │ │ CANDLESTICK      │       │
│  │ ● Analyzing      │ │ ● Idle           │ │ ● Idle           │       │
│  │ GBPUSD M15       │ │ Last: 14:31      │ │ Last: 14:31      │       │
│  │ OB: 2 found      │ │ RSI: 62.4        │ │ Pattern: Doji    │       │
│  │ FVG: 1 found     │ │ Divergence: None │ │ Confidence: 58%  │       │
│  │ Confidence: 74%  │ │ Confidence: 65%  │ │ [View Log]       │       │
│  │ [View Log]       │ │ [View Log]       │ │                  │       │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘       │
│                                                                         │
│  ┌── DECISION PIPELINE (EURUSD — Last Signal) ──────────────────────┐  │
│  │                                                                   │  │
│  │  Step 1: Fundamental ──→ ✓ Neutral (bias: 0.52)                  │  │
│  │  Step 2: Structure   ──→ ✓ Bullish (regime: range, TF aligned)  │  │
│  │  Step 3: Liquidity   ──→ ✓ Buy-side pool above                  │  │
│  │  Step 4: SMC         ──→ ✓ Bullish OB at 1.0840                 │  │
│  │  Step 5: Momentum    ──→ ✓ RSI 62, no divergence                │  │
│  │  Step 6: Candlestick ──→ ✓ Engulfing bullish                    │  │
│  │  Step 7: Aggregation ──→ Confluence: 78/100                     │  │
│  │  Step 8: Risk Gate   ──→ ✓ Risk: 1.2%, within limits            │  │
│  │  Step 9: Execution   ──→ ✓ Order placed: #12345                 │  │
│  │                                                                   │  │
│  │  Total Pipeline Time: 3.2 seconds                                │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌── SUPPORT AGENTS ────────────────────────────────────────────────┐  │
│  │                                                                   │  │
│  │  Monitor Agent    ● Active  │ Watching: 4 pairs │ Alerts: 0      │  │
│  │  Reflection Agent ● Idle    │ Last run: Today 08:00               │  │
│  │  Journal Agent    ● Idle    │ Pending entries: 0                  │  │
│  │                                                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Agent Detail View

Clicking any agent card expands to show detailed information:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  SMC AGENT — Detailed View                              [Collapse]       │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Status:     ● Analyzing GBPUSD M15                                      │
│  Model:      XGBoost (v2.1) + LLM reasoning                             │
│  Uptime:     4h 23m                                                      │
│  Analyses:   142 total | 12 in last hour                                 │
│  Avg Time:   180ms per analysis                                          │
│  Errors:     0 (last 24h)                                                │
│                                                                          │
│  ─── Current Analysis ───                                                │
│                                                                          │
│  Symbol:     GBPUSD                                                      │
│  Timeframe:  M15                                                         │
│  Order Blocks Found: 2                                                   │
│    • Bullish OB: 1.2700-1.2710 (strength: 0.82, age: 3 candles)        │
│    • Bearish OB: 1.2750-1.2760 (strength: 0.65, age: 12 candles)       │
│  FVG Found: 1                                                            │
│    • Bullish FVG: 1.2695-1.2708 (unfilled, 5 candles old)              │
│  Structure Break: Bullish BOS at 1.2720                                  │
│  Confluence Score: 74/100                                                │
│                                                                          │
│  ─── ReAct Trace (last 5 steps) ───                                     │
│                                                                          │
│  14:31:02 [Think] Scanning GBPUSD M15 for order blocks...               │
│  14:31:02 [Act]   fetch_candles(GBPUSD, M15, count=100)                 │
│  14:31:03 [Observe] Received 100 candles, latest: 1.2712                │
│  14:31:03 [Think] Detected impulse move 1.2695→1.2720, marking OB...    │
│  14:31:03 [Act]   classify_ob(bullish, zone=1.2700-1.2710)             │
│  14:31:04 [Observe] OB classified: strength 0.82, valid                 │
│                                                                          │
│  ─── Historical Performance ───                                          │
│                                                                          │
│  Pattern Accuracy (last 30 days):                                        │
│    Order Blocks:  68% success rate (17/25)                               │
│    FVG:           72% success rate (13/18)                               │
│    BOS/CHoCH:     61% success rate (22/36)                               │
│                                                                          │
│  [View Full Log]  [View Model Details]  [Retrain Model]                  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Agent Communication Log

Real-time feed of inter-agent messages:

```
┌──────────────────────────────────────────────────────────────────┐
│  AGENT COMMUNICATION LOG                           [Filter ▾]    │
├──────────────────────────────────────────────────────────────────┤
│  14:32:15 ORCH → ALL      │ Trigger analysis: EURUSD             │
│  14:32:15 FUND → ORCH     │ Bias: Neutral (0.52), no events      │
│  14:32:16 STR  → ORCH     │ Regime: Range, TF aligned bullish    │
│  14:32:16 LIQ  → ORCH     │ Buy-side liquidity pool at 1.0860    │
│  14:32:17 SMC  → ORCH     │ Bullish OB 1.0840-1.0845, score 82  │
│  14:32:17 MOM  → ORCH     │ RSI 62, no divergence, momentum OK  │
│  14:32:18 CNDL → ORCH     │ Engulfing bullish on M15, conf 58   │
│  14:32:18 ORCH → RISK     │ Check: BUY EURUSD 0.01, SL 1.0820   │
│  14:32:18 RISK → ORCH     │ ✓ Approved: risk 1.2%, within limits │
│  14:32:19 ORCH → EXEC     │ Execute: BUY EURUSD 0.01 @ market   │
│  14:32:19 EXEC → ORCH     │ ✓ Filled: #12345 @ 1.08452          │
│  14:32:19 ORCH → JOURNAL  │ Log trade: EURUSD BUY #12345        │
│  14:32:20 ORCH → MONITOR  │ Watch position: EURUSD #12345       │
│                                                                  │
│  ▼                                                              │
└──────────────────────────────────────────────────────────────────┘
```

### 7.4 Agent Health Indicators

Each agent card shows health status via color-coded indicators:

| Indicator | Meaning |
|-----------|---------|
| 🟢 Green | Healthy, actively processing or idle |
| 🟡 Yellow | Degraded — high latency, retrying, or low confidence |
| 🔴 Red | Error — agent failed, requires attention |
| ⚪ Gray | Disabled — user has turned off this agent |
| 🔵 Blue | Processing — currently analyzing data |

---

## 8. Journal UI

### 8.1 Journal Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TRADE JOURNAL                    [All] [Open] [Closed] [Filter] [Export]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌── SUMMARY CARDS ─────────────────────────────────────────────────┐  │
│  │                                                                   │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │  │
│  │  │ Total    │  │ Win Rate │  │ Profit   │  │ Max DD   │        │  │
│  │  │ Trades   │  │          │  │ Factor   │  │          │        │  │
│  │  │   47     │  │  62.3%   │  │   1.85   │  │  -8.2%   │        │  │
│  │  │          │  │  ██████  │  │          │  │          │        │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │  │
│  │                                                                   │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │  │
│  │  │ Avg Win  │  │ Avg Loss │  │ Best     │  │ Worst    │        │  │
│  │  │  +$0.18  │  │  -$0.12  │  │  +$0.52  │  │  -$0.31  │        │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌── TRADE HISTORY TABLE ───────────────────────────────────────────┐  │
│  │                                                                   │  │
│  │  #  │ Symbol │ Dir  │ Lots │  Entry  │  Exit  │  P&L  │  Date   │  │
│  │  ───┼────────┼──────┼──────┼─────────┼────────┼───────┼─────────│  │
│  │  47 │ EURUSD │ BUY  │ 0.01 │ 1.08420 │1.08650 │+$0.23 │ Jul 11  │  │
│  │  46 │ XAUUSD │ SELL │ 0.01 │ 2345.50 │2341.50 │+$0.40 │ Jul 11  │  │
│  │  45 │ GBPUSD │ BUY  │ 0.01 │ 1.27100 │1.26950 │-$0.15 │ Jul 10  │  │
│  │  44 │ USDJPY │ SELL │ 0.01 │ 149.50  │149.20  │+$0.30 │ Jul 10  │  │
│  │  ...│        │      │      │         │        │       │         │  │
│  │                                                                   │  │
│  │  [Load More]                                                     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌── TRADE DETAIL (click any row) ──────────────────────────────────┐  │
│  │                                                                   │  │
│  │  Trade #47 — EURUSD BUY                                          │  │
│  │                                                                   │  │
│  │  Opened:    2026-07-11 14:32:19                                   │  │
│  │  Closed:    2026-07-11 16:45:02                                   │  │
│  │  Duration:  2h 12m 43s                                            │  │
│  │  Entry:     1.08420 (market)                                      │  │
│  │  Exit:      1.08650 (TP hit)                                      │  │
│  │  SL:        1.08200 (22 pips)                                     │  │
│  │  TP:        1.08650 (23 pips)                                     │  │
│  │  R:R:       1:1.05                                                │  │
│  │  P&L:       +$0.23 (+3.2%)                                       │  │
│  │  Commission: $0.07                                                │  │
│  │  Swap:      $0.00                                                 │  │
│  │                                                                   │  │
│  │  ─── AI Analysis ───                                              │  │
│  │                                                                   │  │
│  │  Confluence Score: 78/100                                         │  │
│  │  Agents: F:✓ S:✓ L:✓ SMC:✓ M:✓ C:✓                              │  │
│  │  Market Regime: Ranging → Breakout                                │  │
│  │  Key Level: 1.0840 (bullish OB)                                  │  │
│  │                                                                   │  │
│  │  ─── AI Notes (auto-generated) ───                                │  │
│  │                                                                   │  │
│  │  "Clean setup. Bullish order block held perfectly, price          │  │
│  │   swept liquidity below before reversing. All agents agreed.      │  │
│  │   Entry was slightly late — missed 5 pips of the move.            │  │
│  │   Consider tightening signal-to-execution latency."               │  │
│  │                                                                   │  │
│  │  [View Chart Replay]  [Add Manual Note]  [Flag for Review]       │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Analytics Tab

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ANALYTICS                [Overview] [By Symbol] [By Strategy] [By Time]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌── EQUITY CURVE ─────────────────────────────────────────────────┐   │
│  │                                                                  │   │
│  │  $7.50 ┤                                    ╭──────             │   │
│  │        │                              ╭────╯                    │   │
│  │  $7.25 ┤                        ╭────╯                          │   │
│  │        │                  ╭────╯                                │   │
│  │  $7.00 ┤           ╭────╯        ← Drawdown                    │   │
│  │        │      ╭───╯                                             │   │
│  │  $6.75 ┤─────╯                                                  │   │
│  │        ├────┬────┬────┬────┬────┬────┬────┬────┬────┬────       │   │
│  │        Jun 25  27   29  Jul 1   3    5    7    9   11           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌── PERFORMANCE METRICS ──────────────────────────────────────────┐   │
│  │                                                                  │   │
│  │  Metric              Value        Benchmark                     │   │
│  │  ─────────────────  ────────────  ──────────                    │   │
│  │  Total Return        +$0.23       +3.3%                         │   │
│  │  Sharpe Ratio        1.82         > 1.0 good                    │   │
│  │  Sortino Ratio       2.41         > 2.0 good                    │   │
│  │  Max Drawdown        -8.2%        < 15% limit                   │   │
│  │  Win Rate            62.3%        > 50%                         │   │
│  │  Profit Factor       1.85         > 1.5 good                    │   │
│  │  Avg Trade Duration  1h 42m       —                             │   │
│  │  Expectancy          +$0.005/trade                              │   │
│  │  Recovery Factor     2.8          > 2.0 good                    │   │
│  │  Consecutive Wins    7            —                             │   │
│  │  Consecutive Losses  3            —                             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌── P&L BY PAIR ──────────────┐  ┌── P&L BY SESSION ────────────┐   │
│  │                              │  │                              │   │
│  │  EURUSD  ████████ +$0.45    │  │  Asian   ██ +$0.08           │   │
│  │  XAUUSD  ██████   +$0.32    │  │  London  ████████ +$0.42     │   │
│  │  GBPUSD  ████     -$0.18    │  │  NY      ██████ +$0.28       │   │
│  │  USDJPY  ███      +$0.12    │  │  Off-hrs █ -$0.05            │   │
│  │                              │  │                              │   │
│  └──────────────────────────────┘  └──────────────────────────────┘   │
│                                                                         │
│  ┌── P&L HEATMAP (by day of week × hour) ─────────────────────────┐   │
│  │                                                                  │   │
│  │        Mon   Tue   Wed   Thu   Fri   Sat   Sun                  │   │
│  │  00h   ░░    ░░    ░░    ░░    ░░    —     —                    │   │
│  │  04h   ░░    ██    ░░    ██    ░░    —     —                    │   │
│  │  08h   ████  ██    ████  ██    ██    —     —                    │   │
│  │  12h   ████  ████  ██    ████  ████  —     —                    │   │
│  │  16h   ██    ██    ████  ██    ░░    —     —                    │   │
│  │  20h   ░░    ░░    ░░    ░░    ░░    —     —                    │   │
│  │                                                                  │   │
│  │  Legend: ░░ loss  ██ small win  ████ big win  — market closed   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.3 Chart Replay

Clicking "View Chart Replay" on any trade opens a replay mode:

```
┌──────────────────────────────────────────────────────────────────┐
│  TRADE REPLAY: #47 EURUSD BUY              [◀◀] [◀] [▶] [▶▶]   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Chart showing the trade's lifetime with:                 │   │
│  │  • Entry marker (blue arrow up)                           │   │
│  │  • SL line (red dashed)                                   │   │
│  │  • TP line (green dashed)                                 │   │
│  │  • Exit marker (green arrow down)                         │   │
│  │  • Order block overlay (shaded rectangle)                 │   │
│  │  • FVG overlay (shaded rectangle)                         │   │
│  │  • Agent signal indicators at entry                       │   │
│  │                                                           │   │
│  │  Playback speed: [1x] [2x] [5x] [10x]                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Timeline: ──────────●──────────────────── (entry) ─────── (exit)│
└──────────────────────────────────────────────────────────────────┘
```

---

## 9. System Tray Integration

### 9.1 Tray Icon Behavior

**Platform-specific tray icons:**

| Platform | Icon Style | Location |
|----------|-----------|----------|
| Linux | Monochrome, adapts to dark/light panel | Top bar (GNOME), system tray (KDE) |
| Windows | Color icon, 16×16 | System tray (notification area) |
| macOS | Monochrome template image, 22×22 | Menu bar (right side) |

**Icon states:**

| State | Icon | Tooltip |
|-------|------|---------|
| Trading Active | Green chart icon | "Alpha Stack — Trading Active · +$0.23 today" |
| Trading Paused | Yellow chart icon | "Alpha Stack — Trading Paused" |
| Disconnected | Red chart icon | "Alpha Stack — Disconnected" |
| Analyzing | Blue pulsing icon | "Alpha Stack — Analyzing EURUSD..." |

### 9.2 Tray Context Menu

```
┌─────────────────────────────────┐
│  Alpha Stack v1.2.0             │
│  ─────────────────────────────  │
│  Show Dashboard                 │
│  ─────────────────────────────  │
│  Status: Trading Active         │
│  Balance: $7.23                 │
│  P&L Today: +$0.23 (+3.3%)     │
│  Open Positions: 2              │
│  Active Signals: 3              │
│  ─────────────────────────────  │
│  ▶ Resume Trading               │
│  ⏸ Pause Trading                │
│  ─────────────────────────────  │
│  🔴 Close All Positions         │
│  ─────────────────────────────  │
│  Check for Updates...           │
│  ─────────────────────────────  │
│  Quit                           │
└─────────────────────────────────┘
```

### 9.3 Window Close Behavior

```
User clicks [×] (close button)
    │
    ├── Default: Hide to tray (app continues running)
    │   └── Show notification: "Alpha Stack is still running in the background"
    │
    ├── Shift+Click [×]: Actually quit
    │   └── If open positions: "You have 2 open positions. Quit anyway?"
    │
    └── Configurable in Settings:
        ├── "Close to tray" (default)
        └── "Quit on close"
```

### 9.4 System Notifications

Native OS notifications for trading events:

```typescript
// Tauri notification plugin
import { sendNotification } from '@tauri-apps/plugin-notification';

function notifyTradeFilled(trade: Trade) {
  sendNotification({
    title: `${trade.direction} ${trade.symbol} Filled`,
    body: `Entry: ${trade.entry} · SL: ${trade.sl} · TP: ${trade.tp}`,
    icon: 'trading-active',  // platform-specific
  });
}

function notifySignal(signal: Signal) {
  if (signal.confidence > 0.8) {
    sendNotification({
      title: `🎯 ${signal.symbol} ${signal.direction} Signal`,
      body: `Confidence: ${(signal.confidence * 100).toFixed(0)}% · Entry: ${signal.entry}`,
    });
  }
}

function notifyDrawdownWarning(drawdownPercent: number) {
  sendNotification({
    title: '⚠️ Drawdown Warning',
    body: `Daily drawdown at ${drawdownPercent.toFixed(1)}%. Trading may be paused.`,
  });
}
```

**Platform notification behaviors:**

| Platform | Sound | Persistence | Action Buttons |
|----------|-------|-------------|----------------|
| Linux (GNOME) | System default | Auto-dismiss 5s | No |
| Linux (KDE) | Configurable | Until dismissed | Yes |
| Windows | System toast | Action center | Yes |
| macOS | Configurable | Notification center | Yes |

---

## 10. Dark Mode & Theming

### 10.1 Dark Mode as Default

Dark mode is the **only** sensible default for a trading application. Traders work in low-light environments, stare at screens for hours, and every major trading platform (TradingView, Binance, Bloomberg, MetaTrader) defaults to dark.

### 10.2 Color System

```css
/* Dark theme (default) */
:root {
  /* Backgrounds */
  --bg-base:       #0a0a1a;   /* Deepest background */
  --bg-surface:    #111827;   /* Card/panel background */
  --bg-elevated:   #1f2937;   /* Modal/dropdown background */
  --bg-hover:      #374151;   /* Hover state */
  --bg-active:     #4b5563;   /* Active/selected state */

  /* Text */
  --text-primary:   #f9fafb;  /* Main text */
  --text-secondary: #9ca3af;  /* Labels, descriptions */
  --text-muted:     #6b7280;  /* Disabled, timestamps */
  --text-inverse:   #111827;  /* Text on light backgrounds */

  /* Borders */
  --border-default: rgba(255, 255, 255, 0.06);
  --border-strong:  rgba(255, 255, 255, 0.12);
  --border-focus:   #3b82f6;

  /* Semantic — Trading */
  --color-profit:   #22c55e;  /* Green — positive P&L, buy */
  --color-loss:     #ef4444;  /* Red — negative P&L, sell */
  --color-profit-bg: rgba(34, 197, 94, 0.1);
  --color-loss-bg:   rgba(239, 68, 68, 0.1);
  --color-warning:  #f59e0b;  /* Amber — caution */
  --color-info:     #3b82f6;  /* Blue — neutral info */

  /* Chart colors */
  --chart-up:       #22c55e;  /* Bullish candles */
  --chart-down:     #ef4444;  /* Bearish candles */
  --chart-grid:     rgba(255, 255, 255, 0.04);
  --chart-crosshair:#9ca3af;
  --chart-watermark: rgba(255, 255, 255, 0.03);
}

/* Light theme (optional) */
[data-theme="light"] {
  --bg-base:       #f8fafc;
  --bg-surface:    #ffffff;
  --bg-elevated:   #f1f5f9;
  --text-primary:  #0f172a;
  --text-secondary: #64748b;
  /* ... etc */
}
```

### 10.3 Theme Switching

```
Settings → General → Theme:
  (●) Dark — default, recommended for trading
  (○) Light — for bright environments
  (○) System — follows OS preference
```

**Implementation:** CSS custom properties + `data-theme` attribute on `<html>`. All components reference tokens, never hardcoded colors.

### 10.4 Chart Theme Integration

Chart colors must match the selected theme:

```typescript
const chartTheme = {
  dark: {
    background: '#0a0a1a',
    textColor: '#9ca3af',
    gridColor: 'rgba(255, 255, 255, 0.04)',
    upColor: '#22c55e',
    downColor: '#ef4444',
    crosshairColor: '#9ca3af',
    watermarkColor: 'rgba(255, 255, 255, 0.03)',
  },
  light: {
    background: '#ffffff',
    textColor: '#374151',
    gridColor: 'rgba(0, 0, 0, 0.06)',
    upColor: '#16a34a',
    downColor: '#dc2626',
    crosshairColor: '#64748b',
    watermarkColor: 'rgba(0, 0, 0, 0.03)',
  },
};
```

---

## 11. Responsive Design

### 11.1 Breakpoints

| Breakpoint | Width | Layout | Use Case |
|------------|-------|--------|----------|
| Compact | 1024-1279px | Single-column, stacked panels | Small laptop, half-screen |
| Standard | 1280-1599px | Two-column, sidebar + main | Default desktop |
| Wide | 1600-1919px | Three-column, full dashboard | Large monitor |
| Ultra-wide | 1920px+ | Three-column + extra panels | Multi-monitor, ultra-wide |

### 11.2 Layout Adaptations

**Compact (1024-1279px):**
```
┌─────────────────────────────┐
│  Header (compact)           │
├─────────────────────────────┤
│  Chart (full width)         │
├──────────┬──────────────────┤
│ Watchlist │ Signals          │
│ (collapsible)│ (stacked)     │
├──────────┴──────────────────┤
│  Positions (full width)     │
├─────────────────────────────┤
│  Quick Trade Bar            │
└─────────────────────────────┘
```

- Nav rail collapses to icons only (no labels)
- Watchlist becomes a dropdown/modal
- Signal panel stacks below chart
- Positions table uses horizontal scroll

**Standard (1280-1599px):**
- Default three-panel layout (watchlist | chart | sidebar)
- All panels visible

**Wide (1600px+):**
- Extra panel for agent monitoring widget
- Larger chart area
- Side-by-side signals + AI summary

### 11.3 Panel Resizing

All panels support drag-to-resize with minimum/maximum constraints:

```
Panel constraints:
├── Watchlist: min 200px, max 400px
├── Chart: min 400px, no max
├── Sidebar: min 280px, max 500px
├── Positions: min 200px height, no max
└── Quick Trade: fixed 60px height
```

### 11.4 Window State Persistence

```typescript
// Save window state on resize/move
interface WindowState {
  width: number;
  height: number;
  x: number;
  y: number;
  maximized: boolean;
  panels: PanelLayout;
  activeTab: string;
}

// Restore on launch
const savedState = await invoke<WindowState>('get_window_state');
if (savedState) {
  window.setSize(new PhysicalSize(savedState.width, savedState.height));
  window.setPosition(new PhysicalPosition(savedState.x, savedState.y));
  if (savedState.maximized) window.maximize();
}
```

---

## 12. Platform-Specific Considerations

### 12.1 Linux (Pop!_OS 24.04 / Ubuntu)

| Aspect | Consideration |
|--------|--------------|
| **System Tray** | GNOME uses AppIndicator extension; KDE has native tray. Test both. |
| **Window Decorations** | Use custom titlebar for consistency; GTK themes vary wildly. |
| **MT5 via Wine** | Monitor Wine process health; show connection status prominently. |
| **Font Rendering** | Ensure fontconfig is configured; test with different DPI settings. |
| **Package Format** | .deb (primary), AppImage (universal), Flatpak (sandboxed) |
| **Desktop Entry** | Install .desktop file for app launcher integration. |
| **Notifications** | Use `libnotify` via Tauri plugin; test with GNOME and KDE. |
| **HiDPI** | Fractional scaling (125%, 150%) — test chart rendering at these scales. |

### 12.2 Windows 10/11

| Aspect | Consideration |
|--------|--------------|
| **System Tray** | Standard notification area; works reliably. |
| **Titlebar** | Custom titlebar with window controls (min/max/close). |
| **MT5 Native** | Direct connection, no Wine needed. Detect install path automatically. |
| **Package Format** | .msi (enterprise), .exe/NSIS (consumer) |
| **Notifications** | Windows toast notifications; action center integration. |
| **Auto-start** | Registry entry for "Launch on boot" option. |
| **Windows Defender** | Code signing required to avoid SmartScreen warnings. |
| **DPI Awareness** | Per-monitor DPI awareness; test 100%, 125%, 150%, 200%. |
| **MSIX Packaging** | Consider for Windows Store distribution (future). |

### 12.3 macOS 12+ (Intel + Apple Silicon)

| Aspect | Consideration |
|--------|--------------|
| **Menu Bar** | Native macOS menu bar with standard items (File, Edit, View, etc.). |
| **System Tray** | Right side of menu bar; use template images for dark/light mode. |
| **Window Controls** | Traffic light buttons (close/minimize/maximize) on left side. |
| **Titlebar** | Transparent titlebar with inline toolbar buttons. |
| **MT5** | Official MT5 for Mac (if available) or Wine/CrossOver. |
| **Package Format** | .dmg (universal binary: x86_64 + aarch64) |
| **Notarization** | Required for distribution outside App Store. |
| **Keychain** | Use macOS Keychain for credential storage. |
| **Touch Bar** | Optional: show quick trade buttons on Touch Bar (MacBook Pro). |
| **Gestures** | Support trackpad gestures for chart navigation (pinch to zoom, swipe to scroll). |
| **Retina** | All assets must be @2x; chart rendering at native resolution. |

### 12.4 Cross-Platform Abstraction

```typescript
// src/lib/platform.ts
import { platform } from '@tauri-apps/plugin-os';

export const platformConfig = {
  get titlebarStyle() {
    const os = platform();
    if (os === 'macos') return 'transparent';  // Inline with content
    if (os === 'windows') return 'overlay';     // Custom, overlaying content
    return 'visible';                           // Standard titlebar (Linux)
  },

  get trayIconStyle() {
    const os = platform();
    if (os === 'macos') return 'template';      // Monochrome template
    return 'default';                           // Color icon
  },

  get closeBehavior() {
    const os = platform();
    // macOS convention: close doesn't quit
    if (os === 'macos') return 'hide-to-tray';
    return 'configurable';                      // User choice on Win/Linux
  },

  get keyboardModifier() {
    const os = platform();
    return os === 'macos' ? 'Meta' : 'Ctrl';   // Cmd on Mac, Ctrl on Win/Linux
  },
};
```

### 12.5 Keyboard Shortcut Mapping

| Action | Linux/Windows | macOS |
|--------|--------------|-------|
| Quick Buy | `Ctrl+B` | `Cmd+B` |
| Quick Sell | `Ctrl+S` | `Cmd+S` |
| Close Position | `Ctrl+W` | `Cmd+W` |
| Close All | `Ctrl+Shift+W` | `Cmd+Shift+W` |
| Toggle Trading | `Ctrl+T` | `Cmd+T` |
| Focus Chart | `Ctrl+1` | `Cmd+1` |
| Focus Watchlist | `Ctrl+2` | `Cmd+2` |
| Focus Positions | `Ctrl+3` | `Cmd+3` |
| Settings | `Ctrl+,` | `Cmd+,` |
| Command Palette | `Ctrl+K` | `Cmd+K` |
| Screenshot | `Ctrl+Shift+S` | `Cmd+Shift+S` |
| Fullscreen Chart | `F11` | `Cmd+Ctrl+F` |
| Zoom In Chart | `Ctrl+=` | `Cmd+=` |
| Zoom Out Chart | `Ctrl+-` | `Cmd+-` |
| Quit | `Ctrl+Q` | `Cmd+Q` |

---

## 13. Component Architecture

### 13.1 Frontend Directory Structure

```
src/
├── App.tsx                       # Root component with providers
├── main.tsx                      # Entry point
│
├── pages/
│   ├── Dashboard/
│   │   ├── index.tsx             # Dashboard page layout
│   │   ├── WatchlistPanel.tsx    # Left panel — symbol list
│   │   ├── ChartPanel.tsx        # Center — TradingView chart
│   │   ├── SignalPanel.tsx       # Right — AI signals
│   │   ├── PositionTable.tsx     # Bottom — open positions
│   │   ├── QuickTradeBar.tsx     # Bottom — order entry
│   │   └── AISummary.tsx         # Right — market summary
│   │
│   ├── Trades/
│   │   ├── index.tsx             # Trade management page
│   │   ├── OrderEntry.tsx        # Full order entry form
│   │   ├── ActivePositions.tsx   # Position management table
│   │   ├── PendingOrders.tsx     # Pending order management
│   │   └── TradeDetail.tsx       # Single position detail view
│   │
│   ├── Analytics/
│   │   ├── index.tsx             # Analytics page
│   │   ├── EquityCurve.tsx       # Balance over time chart
│   │   ├── MetricsGrid.tsx       # Performance metrics cards
│   │   ├── PnLHeatmap.tsx        # P&L by time/day heatmap
│   │   ├── SymbolBreakdown.tsx   # P&L by symbol
│   │   └── SessionBreakdown.tsx  # P&L by session
│   │
│   ├── Agents/
│   │   ├── index.tsx             # Agent monitoring page
│   │   ├── AgentCard.tsx         # Individual agent status card
│   │   ├── PipelineView.tsx      # Decision pipeline visualization
│   │   ├── CommunicationLog.tsx  # Inter-agent message log
│   │   ├── AgentDetail.tsx       # Expanded agent detail view
│   │   └── HealthGrid.tsx        # Agent health indicators
│   │
│   ├── Journal/
│   │   ├── index.tsx             # Journal page
│   │   ├── TradeHistory.tsx      # Trade history table
│   │   ├── TradeDetail.tsx       # Single trade detail
│   │   ├── ChartReplay.tsx       # Trade replay on chart
│   │   ├── AINotes.tsx           # AI-generated trade notes
│   │   └── ManualNotes.tsx       # User manual notes
│   │
│   └── Settings/
│       ├── index.tsx             # Settings page
│       ├── GeneralSettings.tsx   # Theme, language, startup
│       ├── BrokerSettings.tsx    # MT5 connection config
│       ├── StrategySettings.tsx  # Agent weights, filters
│       ├── RiskSettings.tsx      # Risk management limits
│       ├── NotificationSettings.tsx # Alert preferences
│       └── AdvancedSettings.tsx  # Logs, data, debug
│
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx          # Root layout with nav + content
│   │   ├── Titlebar.tsx          # Custom titlebar (platform-adaptive)
│   │   ├── NavRail.tsx           # Left navigation rail
│   │   ├── StatusRibbon.tsx      # Top status bar
│   │   ├── FooterBar.tsx         # Bottom log/status bar
│   │   └── ResizablePanels.tsx   # Panel layout wrapper
│   │
│   ├── charts/
│   │   ├── PriceChart.tsx        # TradingView LW Charts wrapper
│   │   ├── MiniChart.tsx         # Sparkline for watchlist
│   │   ├── EquityChart.tsx       # Line chart for equity curve
│   │   ├── HeatmapChart.tsx      # ECharts heatmap wrapper
│   │   └── ChartToolbar.tsx      # Timeframe, indicator, drawing tools
│   │
│   ├── trading/
│   │   ├── OrderForm.tsx         # Order entry form
│   │   ├── PositionRow.tsx       # Single position table row
│   │   ├── PriceDisplay.tsx      # Animated price component
│   │   ├── PnLDisplay.tsx        # Animated P&L component
│   │   ├── SignalCard.tsx        # Signal display card
│   │   └── TradeConfirmDialog.tsx # Order confirmation modal
│   │
│   ├── agents/
│   │   ├── AgentStatusBadge.tsx  # Health indicator badge
│   │   ├── ConfidenceBar.tsx     # Confidence percentage bar
│   │   ├── VerdictIcon.tsx       # ✓/✗/⏳ agent verdict icon
│   │   └── ReActTrace.tsx        # ReAct reasoning display
│   │
│   └── ui/                       # shadcn/ui + custom components
│       ├── Button.tsx
│       ├── Input.tsx
│       ├── Select.tsx
│       ├── Dialog.tsx
│       ├── Toast.tsx
│       ├── Tooltip.tsx
│       ├── Badge.tsx
│       ├── Tabs.tsx
│       ├── Table.tsx
│       ├── Card.tsx
│       └── CommandPalette.tsx    # Ctrl+K command palette
│
├── stores/                       # Zustand stores
│   ├── marketStore.ts            # Live price data
│   ├── tradeStore.ts             # Positions, orders, P&L
│   ├── signalStore.ts            # AI signals
│   ├── agentStore.ts             # Agent states and logs
│   ├── settingsStore.ts          # App configuration
│   ├── journalStore.ts           # Trade history
│   └── uiStore.ts                # UI state (panels, layout, theme)
│
├── hooks/
│   ├── useTauriCommand.ts        # Tauri invoke wrapper with loading/error
│   ├── useTauriEvent.ts          # Tauri event listener hook
│   ├── usePriceStream.ts         # Real-time price subscription
│   ├── usePositions.ts           # Position data + actions
│   ├── useSignals.ts             # Signal data + actions
│   ├── useAgents.ts              # Agent monitoring data
│   ├── useChart.ts               # Chart instance management
│   ├── useKeyboard.ts            # Keyboard shortcut registration
│   └── usePlatform.ts            # Platform detection + config
│
├── lib/
│   ├── tauri-bridge.ts           # Tauri IPC abstraction
│   ├── formatters.ts             # Price, P&L, date, percentage formatters
│   ├── calculations.ts           # Pip value, margin, risk calculations
│   ├── constants.ts              # Trading constants (pair configs, etc.)
│   └── sounds.ts                 # Sound effect player
│
└── assets/
    ├── sounds/                   # Notification sounds (.wav)
    ├── icons/                    # App icons, tray icons
    └── fonts/                    # Inter, JetBrains Mono
```

### 13.2 Key Component Interfaces

```typescript
// Price display with animation
interface PriceDisplayProps {
  value: number;
  prevValue: number;
  pair: string;
  precision: number;      // decimal places (e.g., 5 for EURUSD)
  size?: 'sm' | 'md' | 'lg';
  flashDuration?: number; // ms for color flash on change
}

// Animated P&L
interface PnLDisplayProps {
  value: number;          // in account currency
  percent: number;        // percentage return
  size?: 'sm' | 'md' | 'lg';
  showCurrency?: boolean;
  animate?: boolean;      // number counting animation
}

// Signal card
interface SignalCardProps {
  signal: Signal;
  onExecute: (signal: Signal) => void;
  onModify: (signal: Signal) => void;
  onDismiss: (signalId: string) => void;
  compact?: boolean;      // for sidebar vs full-page display
}

// Agent status card
interface AgentCardProps {
  agent: AgentState;
  onExpand: (agentId: string) => void;
  onViewLog: (agentId: string) => void;
}
```

---

## 14. State Management

### 14.1 Zustand Store Architecture

Zustand is chosen for its simplicity, small bundle size, and excellent TypeScript support.

```typescript
// stores/marketStore.ts
import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

interface MarketState {
  prices: Map<string, PriceTick>;
  subscriptions: Set<string>;

  // Actions
  updatePrice: (tick: PriceTick) => void;
  subscribe: (symbol: string) => void;
  unsubscribe: (symbol: string) => void;
  getPrice: (symbol: string) => PriceTick | undefined;
  getSpread: (symbol: string) => number;
}

export const useMarketStore = create<MarketState>()(
  subscribeWithSelector((set, get) => ({
    prices: new Map(),
    subscriptions: new Set(),

    updatePrice: (tick) =>
      set((state) => {
        const prices = new Map(state.prices);
        prices.set(tick.symbol, tick);
        return { prices };
      }),

    subscribe: (symbol) =>
      set((state) => {
        const subscriptions = new Set(state.subscriptions);
        subscriptions.add(symbol);
        return { subscriptions };
      }),

    getPrice: (symbol) => get().prices.get(symbol),
    getSpread: (symbol) => {
      const tick = get().prices.get(symbol);
      return tick ? tick.ask - tick.bid : 0;
    },
  }))
);

// stores/tradeStore.ts
interface TradeState {
  positions: Position[];
  pendingOrders: PendingOrder[];
  dailyPnL: number;
  totalPnL: number;

  // Actions
  setPositions: (positions: Position[]) => void;
  updatePosition: (ticket: number, update: Partial<Position>) => void;
  addPosition: (position: Position) => void;
  removePosition: (ticket: number) => void;
  setPendingOrders: (orders: PendingOrder[]) => void;
  updateDailyPnL: (pnl: number) => void;
}

// stores/agentStore.ts
interface AgentState {
  agents: Map<string, AgentStatus>;
  pipelineRuns: PipelineRun[];
  communicationLog: AgentMessage[];

  // Actions
  updateAgentStatus: (agentId: string, status: AgentStatus) => void;
  addPipelineRun: (run: PipelineRun) => void;
  addMessage: (message: AgentMessage) => void;
  clearLog: () => void;
}
```

### 14.2 Tauri Event → Store Bridge

```typescript
// hooks/useTauriEvents.ts
import { useEffect } from 'react';
import { listen } from '@tauri-apps/api/event';
import { useMarketStore } from '@/stores/marketStore';
import { useTradeStore } from '@/stores/tradeStore';
import { useSignalStore } from '@/stores/signalStore';
import { useAgentStore } from '@/stores/agentStore';

export function useTauriEvents() {
  const updatePrice = useMarketStore((s) => s.updatePrice);
  const { addPosition, removePosition, updatePosition } = useTradeStore();
  const addSignal = useSignalStore((s) => s.addSignal);
  const updateAgentStatus = useAgentStore((s) => s.updateAgentStatus);

  useEffect(() => {
    const unlisteners: (() => void)[] = [];

    // Price updates (high frequency)
    listen<PriceTick>('price-update', (event) => {
      updatePrice(event.payload);
    }).then(unlisten => unlisteners.push(unlisten));

    // Trade events
    listen<Position>('trade-opened', (event) => {
      addPosition(event.payload);
    }).then(unlisten => unlisteners.push(unlisten));

    listen<{ ticket: number; pnl: number }>('trade-closed', (event) => {
      removePosition(event.payload.ticket);
    }).then(unlisten => unlisteners.push(unlisten));

    listen<Partial<Position>>('trade-modified', (event) => {
      updatePosition(event.payload.ticket!, event.payload);
    }).then(unlisten => unlisteners.push(unlisten));

    // Signal events
    listen<Signal>('signal-new', (event) => {
      addSignal(event.payload);
    }).then(unlisten => unlisteners.push(unlisten));

    // Agent events
    listen<AgentStatus>('agent-status', (event) => {
      updateAgentStatus(event.payload.id, event.payload);
    }).then(unlisten => unlisteners.push(unlisten));

    return () => unlisteners.forEach(unlisten => unlisten());
  }, []);
}
```

---

## 15. Real-Time Data Pipeline

### 15.1 Data Flow Architecture

```
Rust Core Engine
    │
    ├── Tauri Events (high-frequency, for desktop UI)
    │   ├── "price-update"     → ~10-100 Hz per symbol
    │   ├── "trade-opened"     → on execution
    │   ├── "trade-closed"     → on close
    │   ├── "trade-modified"   → on SL/TP change
    │   ├── "signal-new"       → on signal generation
    │   ├── "signal-expired"   → on signal timeout
    │   ├── "agent-status"     → every 5s per agent
    │   └── "system-status"    → every 30s
    │
    └── WebSocket Server (localhost:9222, for web/mobile companions)
        └── Same data, JSON over WebSocket
```

### 15.2 Price Update Optimization

Price updates are the highest-frequency data. Optimization strategy:

```typescript
// Batch price updates to prevent excessive re-renders
import { useMarketStore } from '@/stores/marketStore';

// Instead of re-rendering on every tick, use selective subscriptions
const PriceDisplay = React.memo(({ symbol }: { symbol: string }) => {
  const tick = useMarketStore(
    (state) => state.prices.get(symbol),
    (a, b) => a?.bid === b?.bid && a?.ask === b?.ask // only re-render if price changed
  );

  if (!tick) return null;
  return <span>{formatPrice(tick.bid, symbol)}</span>;
});
```

### 15.3 Reconnection Strategy

```typescript
// lib/tauri-bridge.ts
class TauriBridge {
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private baseDelay = 1000; // 1 second

  async reconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.showPermanentError();
      return;
    }

    const delay = Math.min(
      this.baseDelay * Math.pow(2, this.reconnectAttempts),
      30000 // max 30 seconds
    );

    await sleep(delay);
    this.reconnectAttempts++;

    try {
      await invoke('reconnect');
      this.reconnectAttempts = 0;
      this.showReconnected();
    } catch {
      this.reconnect();
    }
  }
}
```

---

## 16. Keyboard Shortcuts & Power User Features

### 16.1 Command Palette

Accessible via `Ctrl+K` / `Cmd+K` — a Spotlight-style command palette:

```
┌──────────────────────────────────────────────────┐
│  🔍 Type a command...                            │
├──────────────────────────────────────────────────┤
│  Quick Actions                                    │
│  ├── Buy EURUSD (default lot)                    │
│  ├── Sell EURUSD (default lot)                   │
│  ├── Close All Positions                         │
│  └── Pause Trading                               │
│                                                   │
│  Navigation                                       │
│  ├── Go to Dashboard                             │
│  ├── Go to Trades                                │
│  ├── Go to Analytics                             │
│  ├── Go to Agents                                │
│  └── Go to Settings                              │
│                                                   │
│  Charts                                           │
│  ├── Switch to EURUSD                            │
│  ├── Switch to H1 timeframe                      │
│  └── Toggle RSI indicator                        │
│                                                   │
│  System                                           │
│  ├── Check for Updates                           │
│  ├── Open Log File                               │
│  └── Restart Python Sidecar                      │
└──────────────────────────────────────────────────┘
```

### 16.2 Global Keyboard Shortcut Registration

```typescript
// hooks/useKeyboard.ts
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export function useGlobalKeyboard() {
  const navigate = useNavigate();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;

      // Command palette
      if (mod && e.key === 'k') {
        e.preventDefault();
        openCommandPalette();
      }

      // Quick trading
      if (mod && e.key === 'b') {
        e.preventDefault();
        quickBuy();
      }
      if (mod && e.key === 's' && !e.shiftKey) {
        e.preventDefault();
        quickSell();
      }

      // Navigation
      if (mod && e.key === '1') navigate('/dashboard');
      if (mod && e.key === '2') navigate('/trades');
      if (mod && e.key === '3') navigate('/analytics');

      // Trading toggle
      if (mod && e.key === 't') {
        e.preventDefault();
        toggleTrading();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
}
```

---

## 17. Accessibility

### 17.1 Accessibility Requirements

| Requirement | Implementation |
|-------------|---------------|
| **Keyboard Navigation** | All interactive elements focusable with Tab; custom focus indicators |
| **Screen Reader** | ARIA labels on all data displays; live regions for price updates |
| **Color Blindness** | Never rely on color alone; use icons (▲/▼) + color for P&L |
| **Reduced Motion** | `prefers-reduced-motion` — disable price flash animations, chart animations |
| **Font Scaling** | Support system font size preferences; don't break layout at 200% |
| **High Contrast** | Tested with Windows High Contrast mode; borders visible without color |

### 17.2 ARIA Patterns for Trading Data

```tsx
// Price with screen reader support
<div
  role="status"
  aria-live="polite"
  aria-label={`EURUSD price ${formatPrice(tick.bid)}, up ${formatPips(change)} pips`}
>
  <span aria-hidden="true">{formatPrice(tick.bid)}</span>
  <span aria-hidden="true" className={change > 0 ? 'text-profit' : 'text-loss'}>
    {change > 0 ? '▲' : '▼'} {formatPips(change)}
  </span>
</div>

// P&L display
<div
  role="status"
  aria-live="polite"
  aria-label={`Portfolio profit and loss: ${formatCurrency(pnl)}, ${formatPercent(pnlPercent)}`}
>
  ...
</div>

// Signal notification
<div role="alert" aria-live="assertive">
  New buy signal for EURUSD with 82% confidence
</div>
```

---

## 18. Performance Budget

### 18.1 Targets

| Metric | Target | Why |
|--------|--------|-----|
| **App startup** | < 2 seconds | Trader needs to see data fast |
| **First meaningful paint** | < 1 second | Dashboard visible quickly |
| **Price update latency** | < 50ms (tick → UI update) | Real-time feel |
| **Chart frame rate** | 60fps during price streaming | Smooth candlestick rendering |
| **Memory (idle)** | < 80 MB | 24/7 operation |
| **Memory (active)** | < 150 MB | With charts and agents running |
| **CPU (idle)** | < 2% | Background operation |
| **CPU (active)** | < 10% | During price streaming + chart rendering |
| **Bundle size** | < 15 MB (installer) | Fast download, small footprint |

### 18.2 Optimization Strategies

| Area | Strategy |
|------|----------|
| **Price updates** | Selective Zustand subscriptions; only re-render changed components |
| **Chart rendering** | Canvas-based (Lightweight Charts); data decimation for historical candles |
| **Position table** | Virtual scrolling for large datasets (future-proof) |
| **Agent logs** | Log buffer (last 1000 messages); older messages loaded on demand |
| **Images/icons** | SVG for all icons; no rasterized images |
| **Code splitting** | Lazy-load pages; chart library loaded on demand |
| **Web Workers** | Offload indicator calculations to worker thread (future) |
| **Memoization** | React.memo on all list items; useMemo for expensive calculations |

---

## 19. Implementation Roadmap

### Phase 1: Foundation (Weeks 1–2)

- [ ] Tauri 2.x project scaffolding with React + TypeScript + Vite
- [ ] TailwindCSS + shadcn/ui setup with dark theme tokens
- [ ] Custom titlebar (platform-adaptive)
- [ ] Nav rail + app shell layout
- [ ] Status ribbon (static data first)
- [ ] Zustand store scaffolding (market, trade, settings)
- [ ] Tauri event bridge (`useTauriEvents` hook)
- [ ] Basic system tray (show/quit)

### Phase 2: Charts & Dashboard (Weeks 3–4)

- [ ] TradingView Lightweight Charts integration
- [ ] Candlestick chart with real-time updates
- [ ] Timeframe selector (M1 → W1)
- [ ] Volume histogram overlay
- [ ] SMA/EMA line overlays
- [ ] RSI sub-chart
- [ ] Crosshair with OHLCV info display
- [ ] Watchlist panel with live prices
- [ ] Mini sparkline charts in watchlist

### Phase 3: Trading UI (Weeks 5–6)

- [ ] Order entry form (market/limit/stop)
- [ ] Position table with live P&L
- [ ] SL/TP visualization on chart (draggable lines)
- [ ] Quick trade bar
- [ ] Trade confirmation dialog
- [ ] Pending orders management
- [ ] Position modify/close actions
- [ ] Sound effects for trade events

### Phase 4: Signals & Agents (Weeks 7–8)

- [ ] Signal card component
- [ ] Signal panel on dashboard
- [ ] Agent status cards
- [ ] Pipeline visualization
- [ ] Agent communication log
- [ ] Agent detail view with ReAct traces
- [ ] Health indicators

### Phase 5: Analytics & Journal (Weeks 9–10)

- [ ] Equity curve chart
- [ ] Performance metrics grid
- [ ] P&L heatmap (ECharts)
- [ ] Trade history table with virtual scrolling
- [ ] Trade detail view
- [ ] AI-generated trade notes
- [ ] Chart replay mode
- [ ] Manual note editing

### Phase 6: Settings & Polish (Weeks 11–12)

- [ ] All settings pages (General, Broker, Strategy, Risk, Notifications)
- [ ] Keyboard shortcuts + command palette
- [ ] Window state persistence
- [ ] Panel layout persistence
- [ ] Responsive breakpoints (compact/standard/wide)
- [ ] Platform-specific adjustments (macOS menu bar, Linux tray)
- [ ] Accessibility audit
- [ ] Performance profiling and optimization
- [ ] Auto-update integration

---

## Appendix A: Technology Stack Summary

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Shell** | Tauri | 2.x | Window, tray, IPC, auto-update |
| **Frontend** | React | 19 | UI framework |
| **Language** | TypeScript | 5.x | Type safety |
| **Build** | Vite | 6.x | Dev server + bundler |
| **Styling** | TailwindCSS | 4.x | Utility-first CSS |
| **Components** | shadcn/ui | Latest | Accessible component primitives |
| **State** | Zustand | 5.x | Client state management |
| **Charts** | Lightweight Charts | 5.x | TradingView open-source charting |
| **Analytics Charts** | ECharts | 5.x | Heatmaps, complex visualizations |
| **Layout** | react-resizable-panels | Latest | Draggable panel layout |
| **Tables** | TanStack Table + Virtual | Latest | Performant data tables |
| **Icons** | Lucide React | Latest | Consistent icon system |
| **Fonts** | Inter + JetBrains Mono | Latest | UI + monospace (prices, code) |

## Appendix B: Design Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Dark mode default | Yes | Industry standard for trading; reduces eye strain |
| Custom titlebar | Yes | Consistent look across platforms; space for trading controls |
| Left nav rail | Yes | Quick access to all pages; collapses to icons for space |
| Resizable panels | Yes | Traders customize workspaces; persisted layouts |
| Zustand over Redux | Zustand | Less boilerplate, better TypeScript, smaller bundle |
| TradingView LW Charts | Yes | 12KB, purpose-built for finance, Canvas rendering |
| ECharts for analytics | Yes | Rich heatmap/treemap support for P&L analysis |
| Command palette | Yes | Power user feature; fast navigation and actions |
| System tray | Yes | 24/7 background operation; quick access to status |
| Agent transparency | Full | Users must trust the AI; visibility into reasoning is critical |

---

*Architecture designed for Alpha Stack Desktop v1.0 — Institutional-grade AI trading UI, built light and fast with Tauri 2.x.*
