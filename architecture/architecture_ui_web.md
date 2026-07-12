# Alpha Stack — Web Application UI Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/platform/research_web_app.md`](../research/platform/research_web_app.md) — Web application architecture research
> **Status:** Architecture Complete

---

> **Author:** Web UI Architect
> **Date:** 2026-07-11
> **Version:** 1.0
> **Status:** Architecture Design — Ready for Implementation
> **Scope:** Browser-based trading companion built with Next.js (React + TypeScript)
> **Dependencies:** Web App Research, Desktop App Architecture, Multi-Platform Research, Data Pipeline Architecture, Multi-Agent Architecture, Broker Abstraction Layer

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack & Rationale](#2-technology-stack--rationale)
3. [Application Architecture Overview](#3-application-architecture-overview)
4. [Authentication Flow (JWT-Based)](#4-authentication-flow-jwt-based)
5. [Dashboard Layout & Components](#5-dashboard-layout--components)
6. [Chart Integration (TradingView Lightweight Charts)](#6-chart-integration-tradingview-lightweight-charts)
7. [Trade Management UI](#7-trade-management-ui)
8. [Settings UI](#8-settings-ui)
9. [Agent Monitoring UI](#9-agent-monitoring-ui)
10. [Journal UI](#10-journal-ui)
11. [WebSocket Real-Time Updates](#11-websocket-real-time-updates)
12. [PWA Capabilities](#12-pwa-capabilities)
13. [Dark Mode & Theming](#13-dark-mode--theming)
14. [Responsive Design](#14-responsive-design)
15. [State Management Architecture](#15-state-management-architecture)
16. [Performance Optimization](#16-performance-optimization)
17. [Security Architecture](#17-security-architecture)
18. [Project Structure](#18-project-structure)
19. [API Integration Layer](#19-api-integration-layer)
20. [Testing Strategy](#20-testing-strategy)
21. [Deployment Architecture](#21-deployment-architecture)
22. [Development Roadmap](#22-development-roadmap)

---

## 1. Executive Summary

### Purpose

The Alpha Stack Web Application is a **browser-based trading companion** that provides real-time monitoring, trade management, analytics, and AI agent oversight for the Alpha Stack trading system. It connects to the desktop-hosted backend (Rust core + Python sidecar) via REST API and WebSocket, enabling remote monitoring from any browser on any device.

### Design Goals

| Goal | Target | Rationale |
|------|--------|-----------|
| **First Contentful Paint** | < 1.5s | Traders need the dashboard instantly |
| **Time to Interactive** | < 3s | Must be able to trade within 3 seconds |
| **Real-time latency** | < 100ms (WS push → UI update) | Price updates must feel instantaneous |
| **Bundle size (initial)** | < 200 KB gzipped | Fast load on mobile networks |
| **Offline capability** | Dashboard + cached data viewable | PWA with service worker caching |
| **Browser support** | Chrome 90+, Firefox 90+, Safari 15+, Edge 90+ | Cover 95%+ of trader browsers |
| **Accessibility** | WCAG 2.1 AA | Keyboard navigation, screen reader support |

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | Next.js 15 (App Router) | SSR for fast initial load, API routes as BFF, largest React ecosystem |
| Language | TypeScript 5.x | Type safety for financial calculations (decimal precision, order types) |
| Styling | Tailwind CSS 4.x + shadcn/ui | Rapid development, dark mode built-in, copy-paste accessible components |
| State Management | Zustand (client) + TanStack Query (server) | Lightweight client state for real-time data; server state caching + background refetch |
| Charts | TradingView Lightweight Charts (primary) + ECharts (analytics) | 12KB purpose-built financial charts; ECharts for heatmaps/treemaps |
| Real-time | WebSocket (primary) + SSE (secondary) | Bidirectional for trading; one-way for news/alerts |
| Auth | NextAuth.js + JWT (httpOnly cookies) | Secure server-side token management, never expose tokens to JS |
| Tables | TanStack Table + TanStack Virtual | Virtual scrolling for thousands of trade history rows |

---

## 2. Technology Stack & Rationale

### Core Stack

```
Next.js 15 (App Router + React Server Components)
├── React 19                         # UI library
├── TypeScript 5.x                   # Type safety for financial math
├── Tailwind CSS 4.x                 # Utility-first styling
├── shadcn/ui                        # Accessible component primitives
├── Zustand 5.x                      # Client-side state (positions, prices, UI)
├── TanStack Query v5                # Server state (API data, caching, refetch)
├── TanStack Table v8                # Data tables with virtual scrolling
├── TradingView Lightweight Charts   # Price charts (12KB, Canvas-based)
├── ECharts                          # Analytics charts (heatmaps, treemaps)
├── framer-motion                    # Smooth transitions, number animations
├── next-themes                      # Dark/light mode switching
├── next-pwa                         # PWA support (service worker, manifest)
├── zod                              # Runtime validation for order parameters
├── date-fns                         # Date formatting (lightweight)
└── recharts                         # Simple dashboard sparklines
```

### Why Next.js Over Alternatives

| Criterion | Next.js | SvelteKit | Nuxt (Vue) | Angular |
|-----------|---------|-----------|------------|---------|
| **Ecosystem** | ★★★★★ Largest | ★★★ Growing | ★★★★ | ★★★★ Enterprise |
| **Talent pool** | 10x more React devs | Small | Medium | Medium |
| **SSR/SSG** | ★★★★★ RSC + streaming | ★★★★ | ★★★★ | ★★★★ |
| **API Routes** | ★★★★★ Built-in BFF | ★★★★ | ★★★★ | ★★★★ |
| **TypeScript** | ★★★★★ Native | ★★★★ | ★★★ | ★★★★★ Native |
| **TradingView LW Charts** | ★★★★★ First-class React | ★★★ Wrapper | ★★★ Wrapper | ★★★ Wrapper |
| **Edge Runtime** | ★★★★★ Vercel Edge | ★★★★ | ★★★ | ★★★ |

**Bottom line:** React's ecosystem is unmatched for trading UIs. Every charting library, auth library, and data table has first-class React support. Next.js adds SSR (fast dashboard load), API routes (BFF for broker proxying), and Edge Runtime (low-latency global access).

---

## 3. Application Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           BROWSER (Client)                               │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    Next.js App (React 19)                          │  │
│  │                                                                    │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │  │
│  │  │Dashboard │  │  Trades  │  │Analytics │  │    Settings      │  │  │
│  │  │  Page    │  │  Page    │  │  Page    │  │     Page         │  │  │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │  │
│  │       │              │              │                  │           │  │
│  │  ┌────┴──────────────┴──────────────┴──────────────────┴────────┐  │  │
│  │  │                   Zustand Store Layer                         │  │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │  │  │
│  │  │  │ market   │ │ trade    │ │ signal   │ │  settings    │   │  │  │
│  │  │  │ Store    │ │ Store    │ │ Store    │ │  Store       │   │  │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │  │  │
│  │  └──────────────────────────┬───────────────────────────────────┘  │  │
│  │                             │                                      │  │
│  │  ┌──────────────────────────┴───────────────────────────────────┐  │  │
│  │  │                   Data Layer                                  │  │  │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │  │  │
│  │  │  │  WebSocket   │  │ TanStack     │  │  Service Worker  │  │  │  │
│  │  │  │  Client      │  │ Query        │  │  (PWA Cache)     │  │  │  │
│  │  │  │  (real-time) │  │ (REST cache) │  │                  │  │  │  │
│  │  │  └──────┬───────┘  └──────┬───────┘  └──────────────────┘  │  │  │
│  │  └─────────┼─────────────────┼──────────────────────────────────┘  │  │
│  └────────────┼─────────────────┼─────────────────────────────────────┘  │
│               │                 │                                        │
└───────────────┼─────────────────┼────────────────────────────────────────┘
                │ WebSocket       │ HTTPS
                ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    NEXT.JS API ROUTES (BFF Layer)                        │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ /api/auth/*  │  │ /api/market/*│  │ /api/trade/* │  │ /api/agent │  │
│  │ (JWT issue/  │  │ (price proxy,│  │ (order mgmt, │  │ /signal/*  │  │
│  │  refresh)    │  │  candle API) │  │  position)   │  │ (AI data)  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │
│         │                 │                  │                │         │
│  ┌──────┴─────────────────┴──────────────────┴────────────────┴──────┐  │
│  │              Backend For Frontend (BFF) Proxy Layer                │  │
│  │  • JWT validation on every request                                │  │
│  │  • Broker credential proxying (credentials never reach browser)   │  │
│  │  • Response transformation (backend → frontend DTOs)              │  │
│  │  • Rate limiting per user session                                 │  │
│  └───────────────────────────┬───────────────────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │ HTTP/WS (localhost or LAN)
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ALPHA STACK BACKEND                                    │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Rust Core   │  │  Python      │  │  Redis       │  │ TimescaleDB│  │
│  │  (Tauri)     │  │  Sidecar     │  │  (Hot Store) │  │ (Cold Store│  │
│  │  Port: 9222  │  │  Port: 9223  │  │  Port: 6379  │  │  Port:5432 │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Technology | Responsibility |
|-------|-----------|----------------|
| **Presentation** | React 19 + shadcn/ui + Tailwind | UI rendering, user interaction, layout management |
| **State** | Zustand + TanStack Query | Client state (real-time data), server state (API cache) |
| **Data** | WebSocket Client + REST (TanStack Query) | Real-time price/signal/trade streams, REST for historical data |
| **BFF** | Next.js API Routes | JWT auth, broker proxying, response transformation, rate limiting |
| **PWA** | Service Worker + Web App Manifest | Offline caching, installability, background sync |

### Page Routing (Next.js App Router)

```
app/
├── layout.tsx                  # Root layout (providers, theme, global nav)
├── page.tsx                    # Redirect → /dashboard
├── (auth)/
│   ├── login/page.tsx          # Login page
│   └── register/page.tsx       # Registration (if self-hosted)
├── (dashboard)/
│   ├── layout.tsx              # Dashboard shell (sidebar + header + content)
│   ├── dashboard/page.tsx      # Main trading dashboard (default)
│   ├── trades/page.tsx         # Trade management
│   ├── analytics/page.tsx      # Performance analytics
│   ├── agents/page.tsx         # Agent monitoring
│   ├── journal/page.tsx        # Trade journal
│   └── settings/page.tsx       # System settings
├── api/
│   ├── auth/[...nextauth]/route.ts   # NextAuth.js handlers
│   ├── market/route.ts               # Market data proxy
│   ├── trade/route.ts                # Trade operations proxy
│   ├── agent/route.ts                # Agent status proxy
│   └── ws/route.ts                   # WebSocket upgrade endpoint
└── manifest.ts                 # PWA manifest
```

---

## 4. Authentication Flow (JWT-Based)

### 4.1 Auth Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        AUTHENTICATION FLOW                            │
│                                                                       │
│  ┌──────────┐     ┌───────────────┐     ┌──────────────────────────┐│
│  │  Browser  │────▶│ Next.js BFF   │────▶│  Alpha Stack Backend     ││
│  │           │◀────│ (API Route)   │◀────│  (Auth Service)          ││
│  └──────────┘     └───────────────┘     └──────────────────────────┘│
│       │                  │                                           │
│       │ httpOnly cookie  │ JWT validation                            │
│       │ (Secure,         │ on every request                          │
│       │  SameSite=Strict)│                                           │
│       ▼                  ▼                                           │
│  Auto-attach      Validate + proxy                                   │
│  on every req     to backend                                         │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 Token Strategy

| Token | Storage | Lifetime | Purpose |
|-------|---------|----------|---------|
| **Access Token** | httpOnly cookie | 15 minutes | Authenticate API requests |
| **Refresh Token** | httpOnly cookie | 7 days | Renew access token silently |
| **Session ID** | httpOnly cookie | 7 days | Track active sessions |

**Critical security rules:**
- Tokens are **never** stored in `localStorage` or `sessionStorage` (XSS vulnerable)
- All auth cookies use `HttpOnly; Secure; SameSite=Strict; Path=/`
- Refresh tokens are **rotated** on each use (old refresh token invalidated)
- Device fingerprint included in JWT claims for token binding

### 4.3 Login Flow

```
1. User submits credentials (email + password)
2. POST /api/auth/login
3. BFF validates credentials against backend
4. Backend returns access token + refresh token
5. BFF sets httpOnly cookies:
   - access_token (15 min, HttpOnly, Secure, SameSite=Strict)
   - refresh_token (7 days, HttpOnly, Secure, SameSite=Strict)
6. Redirect to /dashboard
```

### 4.4 Token Refresh Flow

```
1. API request returns 401 (access token expired)
2. TanStack Query interceptor catches 401
3. POST /api/auth/refresh (with refresh_token cookie)
4. BFF validates refresh token, issues new pair
5. BFF sets new cookies (both rotated)
6. Original request is retried automatically
7. If refresh fails → redirect to /login
```

### 4.5 WebAuthn / Biometric Authentication (Optional)

```typescript
// Register biometric credential for passwordless login
const credential = await navigator.credentials.create({
  publicKey: {
    challenge: new Uint8Array(32),
    rp: { name: "Alpha Stack", id: "alphastack.app" },
    user: { id: userId, name: email, displayName: name },
    pubKeyCredParams: [{ type: "public-key", alg: -7 }],
    authenticatorSelection: {
      authenticatorAttachment: "platform",
      userVerification: "required"
    }
  }
});
```

**WebAuthn support matrix:**
- ✅ Touch ID / Face ID on macOS/iOS Safari
- ✅ Windows Hello on Edge/Chrome
- ✅ Android biometrics on Chrome
- ✅ Hardware keys (YubiKey) on all browsers

### 4.6 Multi-Session Management

```
GET /api/auth/sessions → Returns all active sessions

Sessions:
┌────────────────────────────────────────────────────────────┐
│  Active Sessions                                           │
├──────────────┬──────────┬──────────┬────────┬──────────────┤
│  Device      │ Browser  │ IP       │ Last   │ Action       │
├──────────────┼──────────┼──────────┼────────┼──────────────┤
│ 🖥 Desktop   │ Chrome   │ 192.168… │ Now    │ Current      │
│ 📱 iPhone    │ Safari   │ 10.0.0…  │ 2h ago │ [Revoke]     │
│ 💻 Laptop    │ Firefox  │ 172.16…  │ 1d ago │ [Revoke]     │
└──────────────┴──────────┴──────────┴────────┴──────────────┘

• New device login triggers email/push notification
• Configurable max concurrent sessions (default: 5)
• "Revoke all other sessions" button
```

---

## 5. Dashboard Layout & Components

### 5.1 Master Layout — Dashboard Shell

The dashboard uses a **resizable multi-panel layout** inspired by Bloomberg Terminal and TradingView. Panels are draggable and resizable, with layouts saved per user.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HEADER BAR                                                             │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  🟢 Alpha Stack   [EURUSD ▾]   Balance: $523.40   P&L: +$12.30  │  │
│  │  Connection: ● Online    │  ⚙ Settings  │  🔔 Alerts (3)  │ 👤  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
├──────────────┬──────────────────────────────────────────────────────────┤
│              │                                                          │
│  SIDEBAR     │                 MAIN CHART PANEL                         │
│  (collapsible│   ┌──────────────────────────────────────────────────┐   │
│   240px)     │   │  EURUSD · 1H · [1m] [5m] [15m] [1H] [4H] [D1]  │   │
│              │   │  ┌────────────────────────────────────────────┐  │   │
│  📊 Dashboard│   │  │                                            │  │   │
│  📈 Trades   │   │  │     TradingView Lightweight Charts         │  │   │
│  📉 Analytics│   │  │     (Candlestick + Volume + Indicators)    │  │   │
│  🤖 Agents   │   │  │                                            │  │   │
│  📓 Journal  │   │  │     ┌──────┐                               │  │   │
│  ⚙ Settings  │   │  │     │Cross-│                               │  │   │
│              │   │  │     │hair  │                               │  │   │
│  ──────────  │   │  │     │Info  │                               │  │   │
│  WATCHLIST   │   │  └─────┴──────┴───────────────────────────────┘  │   │
│              │   │  [Indicators▾] [Draw▾] [Screenshot] [Fullscreen] │   │
│  EURUSD 1.08 ▼│   └──────────────────────────────────────────────────┘   │
│  GBPUSD 1.27 ▲│                                                          │
│  USDJPY 159.2▼│   ┌──────────────────────────────────────────────────┐   │
│  BTCUSDT 68k ▲│   │         POSITIONS / ORDERS TABLE                  │   │
│  ETHUSDT 3.5k▼│   ├────────┬──────┬──────┬────────┬────────┬────────┤   │
│              │   │ Symbol │ Side │ Size │ Entry  │ P&L    │ Action │   │
│  ──────────  │   ├────────┼──────┼──────┼────────┼────────┼────────┤   │
│  SIGNALS     │   │ EURUSD │ BUY  │ 0.02 │ 1.0842 │ +$5.20 │ [Close]│   │
│              │   │ BTCUSDT│ SELL │ 0.01 │ 68450  │ -$2.10 │ [Close]│   │
│  🟢 EURUSD   │   └────────┴──────┴──────┴────────┴────────┴────────┘   │
│    BUY 85%   │                                                          │
│  🟡 GBPUSD   │   ┌──────────────────────────────────────────────────┐   │
│    WAIT 45%  │   │  AI PANEL: Signals │ Confidence │ Risk           │   │
│              │   │  ┌──────┐ ┌────────┐ ┌──────────────────────┐   │   │
│  🟢 BTCUSDT  │   │  │Confid│ │  Risk  │ │   Latest Signal      │   │   │
│    BUY 72%   │   │  │ 85%  │ │  LOW   │ │ EURUSD BUY @ 1.0842  │   │   │
│              │   │  │ ████▓│ │  🟢    │ │ Confluence: 85/100   │   │   │
│              │   │  └──────┘ └────────┘ └──────────────────────┘   │   │
│              │   └──────────────────────────────────────────────────┘   │
│              │                                                          │
├──────────────┴──────────────────────────────────────────────────────────┤
│  FOOTER: Connection: ws://192.168.1.100:9222 ● │ Latency: 3ms │ v1.0  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Header Bar Component

```typescript
// components/layout/HeaderBar.tsx
interface HeaderBarProps {
  account: AccountSummary;
  connection: ConnectionStatus;
  notifications: Notification[];
}

// Displays:
// - App logo + name
// - Active instrument selector (dropdown with search)
// - Account balance (real-time)
// - Today's P&L (absolute + percentage, color-coded)
// - Connection status indicator (green/yellow/red dot)
// - Notification bell (with unread count badge)
// - Settings gear
// - User avatar (profile menu)
```

**Header data updates:**
- Balance: via WebSocket `account` channel (every 1s)
- P&L: computed from open positions, updated every tick
- Connection: WebSocket client state (connected/reconnecting/disconnected)
- Notifications: WebSocket `alerts` channel

### 5.3 Sidebar Component

```typescript
// components/layout/Sidebar.tsx
// - Collapsible (icon-only mode for more chart space)
// - Navigation links with active state
// - Watchlist with live prices (sorted by change %)
// - Active signals panel (compact cards)
// - Quick trade button
```

**Watchlist item:**
```
┌──────────────────────────────┐
│  EURUSD            1.08532   │
│  ▲ +0.23%          +25.2 pips│
└──────────────────────────────┘
```

Each watchlist item is a clickable instrument selector — clicking updates the main chart, positions table, and AI panel to show data for that instrument.

### 5.4 Main Chart Panel

See [Section 6: Chart Integration](#6-chart-integration-tradingview-lightweight-charts) for full detail.

### 5.5 Positions / Orders Table

See [Section 7: Trade Management UI](#7-trade-management-ui) for full detail.

### 5.6 AI Panel

```typescript
// components/ai/AIPanel.tsx
// Displays:
// - Confidence gauge (circular progress, 0-100%)
// - Risk level indicator (LOW/MEDIUM/HIGH with color)
// - Latest signal card (direction, entry, confluence breakdown)
// - Mini confluence breakdown (S/R, SMC, Momentum, etc. — horizontal bars)
// - Active agent status dots (green/yellow/red per agent)
```

### 5.7 Resizable Panel System

```typescript
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';

<PanelGroup direction="horizontal" autoSaveId="dashboard-layout">
  <Panel defaultSize={20} minSize={15} maxSize={30}>
    <Sidebar />
  </Panel>
  <PanelResizeHandle className="w-1 bg-border hover:bg-primary transition-colors" />
  <Panel defaultSize={80}>
    <PanelGroup direction="vertical" autoSaveId="main-panels">
      <Panel defaultSize={65} minSize={40}>
        <ChartPanel />
      </Panel>
      <PanelResizeHandle className="h-1 bg-border" />
      <Panel defaultSize={35} minSize={20}>
        <TabPanel tabs={['Positions', 'Orders', 'History', 'AI Signals']} />
      </Panel>
    </PanelGroup>
  </Panel>
</PanelGroup>
```

**Layout persistence:** Panel sizes and arrangement are saved to `localStorage` and restored on page load. Users can reset to default layout.

---

## 6. Chart Integration (TradingView Lightweight Charts)

### 6.1 Why TradingView Lightweight Charts

| Criterion | TradingView LW | Apache ECharts | D3.js | Recharts |
|-----------|---------------|----------------|-------|----------|
| **Bundle size** | ~12 KB gzipped | 80-130 KB | ~80 KB | ~50 KB |
| **Candlestick** | ★★★★★ Purpose-built | ★★★★ Native | ★★ DIY | ★ Workaround |
| **Real-time perf** | ★★★★★ 100s of ticks/sec | ★★★★ | ★★★ | ★★★ (jank at 1k+) |
| **Rendering** | Canvas | Canvas/WebGL | SVG/Canvas | SVG |
| **Dark mode** | ★★★★★ Default dark | ★★★★ | ★★★ | ★★★ |
| **Financial focus** | ★★★★★ Built for trading | ★★★★ | ★★ | ★ |

**Decision:** TradingView Lightweight Charts for all price charts. ECharts for analytics visualizations (P&L heatmaps, treemaps, correlation matrices).

### 6.2 Chart Component Architecture

```typescript
// components/charts/PriceChart.tsx
'use client';

import { createChart, IChartApi, ISeriesApi, CandlestickData, HistogramData } from 'lightweight-charts';
import { useEffect, useRef, useCallback, memo } from 'react';
import { useMarketStore } from '@/stores/marketStore';

interface PriceChartProps {
  symbol: string;
  timeframe: Timeframe;
  indicators?: IndicatorConfig[];
  onCrosshairMove?: (data: CrosshairData) => void;
}

const PriceChart = memo(function PriceChart({ symbol, timeframe, indicators, onCrosshairMove }: PriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#0a0a1a' },
        textColor: '#d1d5db',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      crosshair: {
        mode: 0, // Normal crosshair
        vertLine: { labelBackgroundColor: '#374151' },
        horzLine: { labelBackgroundColor: '#374151' },
      },
      rightPriceScale: {
        borderColor: '#374151',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: '#374151',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { vertTouchDrag: false }, // Allow vertical scroll on mobile
    });

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',       // Green for bullish
      downColor: '#ef4444',     // Red for bearish
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    // Volume histogram
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // Crosshair handler
    chart.subscribeCrosshairMove((param) => {
      if (onCrosshairMove && param.time) {
        onCrosshairMove({
          time: param.time,
          open: param.seriesData.get(candleSeries)?.open,
          high: param.seriesData.get(candleSeries)?.high,
          low: param.seriesData.get(candleSeries)?.low,
          close: param.seriesData.get(candleSeries)?.close,
        });
      }
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    return () => chart.remove();
  }, []);

  // Load historical data when symbol/timeframe changes
  useEffect(() => {
    const loadData = async () => {
      const candles = await fetchCandles(symbol, timeframe, 500);
      candleSeriesRef.current?.setData(candles);
      const volumes = candles.map(c => ({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)',
      }));
      volumeSeriesRef.current?.setData(volumes);
    };
    loadData();
  }, [symbol, timeframe]);

  // Real-time tick updates from Zustand store
  const lastTick = useMarketStore(state => state.getLastTick(symbol));
  
  useEffect(() => {
    if (!lastTick || !candleSeriesRef.current) return;
    
    // Update current candle with new tick
    candleSeriesRef.current.update({
      time: lastTick.candleTime,
      open: lastTick.open,
      high: lastTick.high,
      low: lastTick.low,
      close: lastTick.close,
    });
    
    volumeSeriesRef.current?.update({
      time: lastTick.candleTime,
      value: lastTick.volume,
      color: lastTick.close >= lastTick.open ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)',
    });
  }, [lastTick]);

  return <div ref={chartContainerRef} className="w-full h-full" />;
});
```

### 6.3 Multi-Timeframe Support

```typescript
// hooks/useTimeframe.ts
type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1d' | '1w';

// Timeframe tabs rendered above the chart
const TIMEFRAMES: { label: string; value: Timeframe }[] = [
  { label: '1m', value: '1m' },
  { label: '5m', value: '5m' },
  { label: '15m', value: '15m' },
  { label: '1H', value: '1h' },
  { label: '4H', value: '4h' },
  { label: 'D1', value: '1d' },
  { label: 'W1', value: '1w' },
];
```

### 6.4 Indicator Overlays

```typescript
// components/charts/indicators/
// Indicators are computed in a Web Worker to avoid main thread jank

// Supported indicators:
// - Moving Averages (SMA, EMA) — overlay on price chart
// - Bollinger Bands — overlay
// - RSI — separate sub-chart below
// - MACD — separate sub-chart below
// - Volume Profile — overlay (horizontal histogram)
// - Support/Resistance levels — horizontal lines
// - Order Blocks — highlighted rectangles
// - FVG (Fair Value Gap) — highlighted rectangles

// Indicator rendering uses addLineSeries() for overlays
// and separate chart instances for sub-charts (RSI, MACD)
```

### 6.5 Drawing Tools

```typescript
// components/charts/DrawingToolbar.tsx
// Drawing tools for user annotations:
// - Trendline
// - Horizontal line (S/R)
// - Rectangle (zone marking)
// - Fibonacci retracement
// - Text annotation
// - Arrow (trade entry/exit markers)

// Implementation: Custom drawing layer on top of Lightweight Charts
// using HTML5 Canvas overlay or the lightweight-charts-drawings plugin
```

### 6.6 Multi-Chart Layouts

```typescript
// components/charts/MultiChartLayout.tsx
// Supports grid layouts:
// - 1×1 (single chart, default)
// - 2×1 (side-by-side)
// - 2×2 (quad chart)
// - 1+2 (one large + two small)

// Each chart cell is independently configurable:
// - Different symbol
// - Different timeframe
// - Different indicators
// - Crosshair sync across charts (optional)
```

---

## 7. Trade Management UI

### 7.1 Positions Table

```typescript
// components/trading/PositionTable.tsx
// Virtual-scrolled table for open positions

interface Position {
  ticket: number;
  symbol: string;
  direction: 'BUY' | 'SELL';
  size: number;
  openPrice: number;
  currentPrice: number;
  stopLoss: number;
  takeProfit: number;
  pnl: number;          // Real-time, updated every tick
  pnlPercent: number;
  swap: number;
  openTime: string;
  strategy: string;      // Which AI agent opened this
  confluenceScore: number;
}

// Table columns:
// Symbol | Direction | Size | Entry | Current | SL | TP | P&L | P&L % | Strategy | Actions
// 
// P&L column: color-coded (green/red), animated number transitions
// Actions: [Modify] [Close] [Partial Close]
```

### 7.2 Order Entry Component

```typescript
// components/trading/OrderEntry.tsx

interface OrderEntryProps {
  symbol: string;
  currentBid: number;
  currentAsk: number;
  accountBalance: number;
}

// Features:
// - Buy/Sell buttons (large, color-coded, one-click)
// - Order type selector: Market | Limit | Stop
// - Price input (pre-filled for limit/stop)
// - Size input with lot calculator
//   - Direct lot size input
//   - Risk % input → auto-calculate lots
//   - Risk $ input → auto-calculate lots
// - Stop Loss input (pips or price)
// - Take Profit input (pips or price, multiple TPs)
// - Risk/Reward ratio display (auto-calculated)
// - Spread display (current, in pips)
// - Margin required display
// - Confirm button with order summary

// Keyboard shortcuts:
// - B: Buy market
// - S: Sell market
// - Esc: Cancel/close order panel
// - Tab: Cycle through inputs
```

### 7.3 Pending Orders Table

```typescript
// components/trading/PendingOrdersTable.tsx

interface PendingOrder {
  ticket: number;
  symbol: string;
  type: 'LIMIT' | 'STOP' | 'STOP_LIMIT';
  direction: 'BUY' | 'SELL';
  price: number;
  size: number;
  stopLoss: number;
  takeProfit: number;
  createdTime: string;
  expiryTime?: string;
  strategy: string;
}

// Actions: [Modify] [Cancel]
```

### 7.4 Trade History Table

```typescript
// components/trading/TradeHistoryTable.tsx
// Virtual-scrolled, paginated, filterable

// Filters:
// - Date range picker
// - Symbol multi-select
// - Direction (Buy/Sell/All)
// - Strategy (Agent name/All)
// - Outcome (Win/Loss/Breakeven/All)
// - Sort by: Date, P&L, Duration, Symbol

// Columns:
// Close Time | Symbol | Direction | Size | Entry | Exit | P&L | Duration | Strategy | R-Multiple

// Export: CSV, JSON
```

### 7.5 One-Click Trading

```typescript
// components/trading/QuickTrade.tsx
// Floating panel for rapid execution

// Features:
// - Persistent buy/sell buttons visible on chart
// - Pre-configured lot sizes (0.01, 0.02, 0.05, 0.10)
// - One-click close all positions
// - One-click breakeven all positions
// - Keyboard shortcuts (configurable)
```

### 7.6 Trade Modification Modal

```typescript
// components/trading/ModifyOrderModal.tsx
// Modal for modifying SL/TP on existing positions

// Features:
// - Visual SL/TP levels on chart (draggable lines)
// - Input fields for precise values
// - Pips calculator (enter distance in pips)
// - Risk/Reward ratio preview
// - Partial close slider (close 25%, 50%, 75%, custom %)
```

---

## 8. Settings UI

### 8.1 Settings Page Structure

```
settings/
├── /settings                  # Overview / quick settings
├── /settings/broker           # Broker connections
├── /settings/strategy         # Strategy parameters
├── /settings/risk             # Risk management rules
├── /settings/notifications    # Alert preferences
├── /settings/ai               # AI agent configuration
├── /settings/appearance       # Theme, layout, chart defaults
├── /settings/security         # Password, 2FA, sessions
├── /settings/api              # API keys, webhooks
└── /settings/advanced         # Developer options, logging
```

### 8.2 Broker Connections

```typescript
// app/(dashboard)/settings/broker/page.tsx

// Broker connection cards:
┌────────────────────────────────────────────────────────────┐
│  Broker Connections                                        │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  🟢 FXPesa (MetaTrader 5)              Connected     │  │
│  │  Account: 12345678  │  Server: FXPesa-Live           │  │
│  │  Balance: $523.40   │  Leverage: 1:400               │  │
│  │  Last sync: 2s ago  │  [Disconnect] [Reconfigure]    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  🟢 Binance (CCXT)                     Connected     │  │
│  │  Account: Spot + Futures  │  Mode: Live              │  │
│  │  Balance: $1,234.56       │  [Disconnect] [Reconfig]  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  [+ Add Broker Connection]                                 │
│                                                            │
│  Supported:                                                │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │
│  │FXPesa  │ │Binance │ │Bybit   │ │OANDA   │ │IBKR    │  │
│  │(MT5)   │ │(CCXT)  │ │(CCXT)  │ │(REST)  │ │(API)   │  │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘  │
└────────────────────────────────────────────────────────────┘
```

**Connection flow:**
1. User selects broker type
2. Enters credentials (API key, secret, server, login)
3. BFF validates connection (test balance query)
4. Credentials encrypted server-side, stored in OS keychain
5. Browser only sees connection status, never raw credentials

### 8.3 Strategy Configuration

```typescript
// app/(dashboard)/settings/strategy/page.tsx

// Strategy parameter cards:
┌────────────────────────────────────────────────────────────┐
│  Strategy Parameters                                       │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Signal Weights                                       │  │
│  │                                                       │  │
│  │  S/R Levels     ████████████████░░░░  0.20           │  │
│  │  SMC Patterns   ██████████████████░░  0.25           │  │
│  │  Momentum (RSI) ████████████░░░░░░░░  0.15           │  │
│  │  Liquidity      ██████████░░░░░░░░░░  0.10           │  │
│  │  Candlestick    ████████░░░░░░░░░░░░  0.10           │  │
│  │  Fundamental    ██████████████░░░░░░  0.15           │  │
│  │  Structure      ██████████░░░░░░░░░░  0.05           │  │
│  │                                                       │  │
│  │  [Reset to Defaults]  [Apply Changes]                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Entry Rules                                          │  │
│  │                                                       │  │
│  │  Min Confluence Score:  [60] (0-100)                 │  │
│  │  Min RSI Confirmation:  [30] (0-100)                 │  │
│  │  Allowed Sessions:      ☑ Asian ☑ London ☑ NY        │  │
│  │  Max Spread (pips):     [3.0]                        │  │
│  │  News Filter:           ☑ Skip 30min before H/I news │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### 8.4 Risk Management Settings

```typescript
// app/(dashboard)/settings/risk/page.tsx

┌────────────────────────────────────────────────────────────┐
│  Risk Management Rules                                     │
│                                                            │
│  ⚠️ These rules are enforced at INFRASTRUCTURE level.      │
│     They CANNOT be overridden by AI agents.                │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Position Sizing                                      │  │
│  │                                                       │  │
│  │  Max Risk Per Trade:     [1.5]% of equity             │  │
│  │  Default Risk Per Trade: [1.0]% of equity             │  │
│  │  Max Open Positions:     [3]                          │  │
│  │  Max Correlated Pairs:   [2] (same base/quote)       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Loss Limits                                          │  │
│  │                                                       │  │
│  │  Max Daily Loss:         [5]% of equity               │  │
│  │  Max Weekly Loss:        [10]% of equity              │  │
│  │  Max Drawdown Halt:      [15]% — flatten ALL          │  │
│  │  Loss Streak Pause:      [3] consecutive losses       │  │
│  │  Pause Duration:         [30] minutes                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Emergency Controls                                   │  │
│  │                                                       │  │
│  │  [🔴 KILL SWITCH — Close All Positions Immediately]  │  │
│  │  [⏸ Pause Trading — No New Entries]                  │  │
│  │  [▶ Resume Trading]                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### 8.5 Notification Settings

```typescript
// app/(dashboard)/settings/notifications/page.tsx

┌────────────────────────────────────────────────────────────┐
│  Notification Preferences                                  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  In-App Notifications                                 │  │
│  │                                                       │  │
│  │  Trade Opened:          ☑ Visual + Sound             │  │
│  │  Trade Closed:          ☑ Visual + Sound             │  │
│  │  Stop Loss Hit:         ☑ Visual + Sound + Vibrate   │  │
│  │  High-Confluence Signal: ☑ Visual + Sound            │  │
│  │  Risk Alert:            ☑ Visual + Sound + Vibrate   │  │
│  │  Agent Error:           ☑ Visual                     │  │
│  │  Daily Summary:         ☑ Visual                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  External Notifications                               │  │
│  │                                                       │  │
│  │  Telegram Bot:          ☑ Enabled  Token: ****       │  │
│  │  Email Alerts:          ☐ Enabled  Address: ****     │  │
│  │  Push (PWA):            ☑ Enabled  (Android only)    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Sound Files                                          │  │
│  │                                                       │  │
│  │  Trade Fill:    [Default ▾]  [▶ Test]                │  │
│  │  Alert:         [Default ▾]  [▶ Test]                │  │
│  │  Error:         [Default ▾]  [▶ Test]                │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### 8.6 AI Agent Configuration

```typescript
// app/(dashboard)/settings/ai/page.tsx

┌────────────────────────────────────────────────────────────┐
│  AI Agent Configuration                                    │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Agent Weights (Adaptive — adjusts based on accuracy) │  │
│  │                                                       │  │
│  │  Fundamental Agent:  ██████████████░░░░  0.15  [0.70]│  │
│  │  Structure Agent:    ████████████████████  0.25  [0.82│  │
│  │  SMC Agent:          ██████████████████░░  0.20  [0.78│  │
│  │  Momentum Agent:     ████████████░░░░░░░░  0.12  [0.65│  │
│  │  Liquidity Agent:    ██████████░░░░░░░░░░  0.10  [0.60│  │
│  │  Candlestick Agent:  ████████░░░░░░░░░░░░  0.08  [0.55│  │
│  │  S/R Module:         ██████████░░░░░░░░░░  0.10  [0.62│  │
│  │                                                       │  │
│  │  [ ] Lock weights (disable auto-adjustment)           │  │
│  │  [Reset to Defaults]                                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  LLM Configuration                                    │  │
│  │                                                       │  │
│  │  Reasoning Model:    [qwen-2.5-72b ▾]               │  │
│  │  Fast Model:         [qwen-2.5-7b ▾]                │  │
│  │  Sentiment Model:    [FinBERT ▾]                     │  │
│  │  Max Tokens/Day:     [200,000]                       │  │
│  │  Max Cost/Day:       [$2.00]                         │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### 8.7 Appearance Settings

```typescript
// app/(dashboard)/settings/appearance/page.tsx

// Theme:
// - Dark (default) / Light / System
// - Accent color picker (for P&L colors, buttons)
// - Font size (compact/normal/large)
//
// Chart defaults:
// - Default timeframe
// - Candle colors (green/red, blue/orange, custom)
// - Grid visibility
// - Crosshair style
//
// Layout:
// - Sidebar position (left/right)
// - Default panel arrangement
// - Compact mode (more data density)
```

---

## 9. Agent Monitoring UI

### 9.1 Agent Dashboard

```typescript
// app/(dashboard)/agents/page.tsx

┌─────────────────────────────────────────────────────────────────────────┐
│  Agent Monitoring                                                       │
│                                                                         │
│  System Status: 🟢 All Agents Healthy  │  Uptime: 4h 23m  │  v1.0.0   │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Agent Grid                                                         │ │
│  │                                                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │ │
│  │  │ 🟢 Orchestrator│ │ 🟢 Fundamental│ │ 🟢 Structure  │             │ │
│  │  │ Status: Active │ │ Status: Active│ │ Status: Active│             │ │
│  │  │ Signals: 142   │ │ Signals: 28  │ │ Signals: 56  │             │ │
│  │  │ Avg: 120ms     │ │ Avg: 2.3s    │ │ Avg: 890ms   │             │ │
│  │  │ Errors: 0      │ │ Errors: 0    │ │ Errors: 0    │             │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │ │
│  │                                                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │ │
│  │  │ 🟢 SMC Agent  │ │ 🟢 Momentum  │ │ 🟢 Liquidity  │             │ │
│  │  │ Status: Active│ │ Status: Active│ │ Status: Active│             │ │
│  │  │ Patterns: 34  │ │ RSI: 45.2    │ │ Pools: 12    │             │ │
│  │  │ OBs: 8       │ │ Composite: 52│ │ Sweeps: 3    │             │ │
│  │  │ FVGs: 5      │ │ Divergences: 0│ │ Delta: +120  │             │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │ │
│  │                                                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │ │
│  │  │ 🟢 Risk Gate  │ │ 🟢 Execution  │ │ 🟢 Monitor   │             │ │
│  │  │ Status: Active│ │ Status: Active│ │ Status: Active│             │ │
│  │  │ Approved: 12  │ │ Fills: 12    │ │ Alerts: 3    │             │ │
│  │  │ Rejected: 3   │ │ Slippage: 0.8│ │ Health: OK   │             │ │
│  │  │ Drawdown: 2.1%│ │ Avg: 45ms    │ │ Latency: 3ms │             │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Pipeline Visualization                                             │ │
│  │                                                                     │ │
│  │  EURUSD Pipeline (Last Run: 2 min ago)                             │ │
│  │                                                                     │ │
│  │  [Fundamental] ──→ [Structure] ──→ [SMC] ──→ [Aggregator]         │ │
│  │       ✅            ✅           ✅          ✅                      │ │
│  │  [Momentum] ──→ [Candlestick] ──→ [Risk Gate] ──→ [Execution]     │ │
│  │      ✅             ✅              ✅ (APPROVED)     ✅             │ │
│  │                                                                     │ │
│  │  Confluence Score: 85/100  │  Direction: BUY  │  Confidence: 0.82  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Agent Performance (Last 24h)                                       │ │
│  │                                                                     │ │
│  │  ┌─────────────┬──────────┬──────────┬──────────┬───────────────┐ │ │
│  │  │ Agent       │ Signals  │ Accuracy │ Avg Time │ Token Usage   │ │ │
│  │  ├─────────────┼──────────┼──────────┼──────────┼───────────────┤ │ │
│  │  │ Fundamental │ 28       │ 72%      │ 2.3s     │ 12,450        │ │ │
│  │  │ Structure   │ 56       │ 81%      │ 890ms    │ 8,200         │ │ │
│  │  │ SMC         │ 34       │ 78%      │ 650ms    │ 5,100         │ │ │
│  │  │ Momentum    │ 56       │ 65%      │ 120ms    │ 1,200         │ │ │
│  │  │ Liquidity   │ 45       │ 70%      │ 200ms    │ 800           │ │ │
│  │  │ Candlestick │ 56       │ 62%      │ 80ms     │ 500           │ │ │
│  │  └─────────────┴──────────┴──────────┴──────────┴───────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Agent Detail View

```typescript
// app/(dashboard)/agents/[agentId]/page.tsx

// Per-agent detail page showing:
// - Agent configuration (model, parameters, permissions)
// - Signal history (last 100 signals with outcomes)
// - Performance metrics (accuracy, win rate by pattern type)
// - Recent reasoning traces (ReAct loop output)
// - Resource usage (tokens, cost, latency)
// - Error log (last 50 errors with context)
// - Restart/reconfigure controls
```

### 9.3 Pipeline Visualization

```typescript
// components/agents/PipelineVisualization.tsx
// Interactive flowchart showing the 16-step pipeline
// - Each step is a node with status indicator
// - Arrows show data flow
// - Clicking a node shows its latest output
// - Real-time updates as pipeline runs
// - Color-coded: green (success), yellow (running), red (failed), gray (pending)
```

---

## 10. Journal UI

### 10.1 Journal Page

```typescript
// app/(dashboard)/journal/page.tsx

┌─────────────────────────────────────────────────────────────────────────┐
│  Trade Journal                                                          │
│                                                                         │
│  [Filter▾] [Date Range▾] [Symbol▾] [Strategy▾] [Outcome▾] [Search🔍] │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Journal Entries (sorted by date, newest first)                     │ │
│  │                                                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │  📗 EURUSD BUY — +1.5R (+$6.75)              2026-07-11    │  │ │
│  │  │                                                              │  │ │
│  │  │  Entry: 1.0842 │ SL: 1.0810 │ TP1: 1.0887 │ Duration: 2h   │  │ │
│  │  │  Confluence: 85/100 │ Strategy: H4 OB + RSI Oversold        │  │ │
│  │  │                                                              │  │ │
│  │  │  AI Analysis:                                                │  │ │
│  │  │  "H4 bullish order block at D1 support zone. RSI oversold   │  │ │
│  │  │   on H1 (28.3). London session with high volume. Multi-TF   │  │ │
│  │  │   alignment score: 0.77. Regime: Trending Bull (0.82)."     │  │ │
│  │  │                                                              │  │ │
│  │  │  Outcome: TP1 hit. Price continued to TP2 level but          │  │ │
│  │  │  trailing stop was triggered prematurely.                    │  │ │
│  │  │                                                              │  │ │
│  │  │  Lesson: "In trending markets with regime confidence > 0.8,  │  │ │
│  │  │  use wider trailing stops (ATR × 3.0 instead of × 2.5)."    │  │ │
│  │  │                                                              │  │ │
│  │  │  [View Chart] [View Signals] [View Full Analysis]            │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │  📕 BTCUSDT SELL — -1.0R (-$3.50)           2026-07-11    │  │ │
│  │  │  ...                                                          │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Weekly Summary                                                     │ │
│  │                                                                     │ │
│  │  Week of July 7-11, 2026                                           │ │
│  │  ┌──────────────┬──────────┬──────────┬──────────┬──────────────┐ │ │
│  │  │ Metric       │ Value    │ vs Last  │ Trend    │ Target       │ │ │
│  │  ├──────────────┼──────────┼──────────┼──────────┼──────────────┤ │ │
│  │  │ Total Trades │ 12       │ +3       │ 📈       │ 10-15        │ │ │
│  │  │ Win Rate     │ 67%      │ +5%      │ 📈       │ > 60%        │ │ │
│  │  │ Profit Factor│ 1.8      │ +0.2     │ 📈       │ > 1.5        │ │ │
│  │  │ Net P&L      │ +$18.50  │ +$8.20   │ 📈       │ Positive     │ │ │
│  │  │ Max Drawdown │ 3.2%     │ -0.5%    │ 📉       │ < 5%         │ │ │
│  │  │ Avg R-Multi  │ +0.8R    │ +0.1R    │ 📈       │ > 0.5R       │ │ │
│  │  └──────────────┴──────────┴──────────┴──────────┴──────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Trade Detail Modal

```typescript
// components/journal/TradeDetailModal.tsx

// Full trade analysis view:
// - Mini chart with entry/exit markers
// - Complete signal breakdown (each agent's contribution)
// - Confluence score visualization (radar chart)
// - Execution details (fill price, slippage, latency)
// - Risk parameters used
// - AI reasoning trace (full ReAct loop output)
// - Post-trade reflection (from Reflection Agent)
// - Similar past trades (semantic search results)
// - User notes (editable)
```

### 10.3 Analytics Page

```typescript
// app/(dashboard)/analytics/page.tsx

┌─────────────────────────────────────────────────────────────────────────┐
│  Performance Analytics                                                  │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Equity Curve                                                       │ │
│  │  [TradingView Lightweight Charts — Line chart of balance over time] │ │
│  │  [1W] [1M] [3M] [6M] [1Y] [ALL]                                   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────┐ │
│  │  Key Metrics          │  │  Win Rate by Strategy │  │  P&L Heatmap │ │
│  │                       │  │                       │  │  (ECharts)   │ │
│  │  Net P&L:    +$142.30 │  │  H4 OB:     80% 🟢   │  │              │ │
│  │  Win Rate:   67%      │  │  FVG:       72% 🟢   │  │  ┌────────┐ │ │
│  │  Profit Fac: 1.8      │  │  Sweep:     65% 🟡   │  │  │Heatmap │ │ │
│  │  Sharpe:     1.4      │  │  Divergence: 55% 🟡  │  │  │by day  │ │ │
│  │  Max DD:     4.2%     │  │  Candle:    60% 🟡   │  │  │& pair  │ │ │
│  │  Avg Win:    +$8.50   │  │  RSI:       58% 🟡   │  │  └────────┘ │ │
│  │  Avg Loss:   -$4.70   │  │                       │  │              │ │
│  │  Expectancy: +$1.85   │  │                       │  │              │ │
│  └──────────────────────┘  └──────────────────────┘  └──────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  P&L by Session                                                     │ │
│  │  [Bar chart: Asian / London / New York / Overlap]                   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Drawdown Chart                                                     │ │
│  │  [Area chart showing drawdown from peak over time]                  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Risk Metrics                                                       │ │
│  │  • Sortino Ratio: 1.6  • Calmar Ratio: 2.1  • Max Consec Losses: 3│ │
│  │  • Avg Trade Duration: 3.2h  • Best Trade: +$18.50  • Worst: -$8.20│ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 11. WebSocket Real-Time Updates

### 11.1 WebSocket Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     WebSocket Connection Manager                      │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  WS Client (lib/ws-client.ts)                                  │  │
│  │                                                                 │  │
│  │  • Single WebSocket connection to backend                      │  │
│  │  • Channel-based subscription model                            │  │
│  │  • Automatic reconnection with exponential backoff             │  │
│  │  • Heartbeat ping every 30s                                    │  │
│  │  • Message buffering during reconnection                       │  │
│  │  • Connection state: CONNECTING → CONNECTED → RECONNECTING     │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  Channels:                                                            │
│  ┌────────────────┬───────────────────────────────────────────────┐  │
│  │ Channel        │ Data                                           │  │
│  ├────────────────┼───────────────────────────────────────────────┤  │
│  │ prices         │ Bid/Ask ticks, candle updates                 │  │
│  │ positions      │ Position open/close/modify, P&L updates       │  │
│  │ orders         │ Order fill, cancel, modify events             │  │
│  │ signals        │ AI signal generation, confluence scores       │  │
│  │ account        │ Balance, equity, margin updates               │  │
│  │ agents         │ Agent health, status changes                  │  │
│  │ alerts         │ Risk alerts, system notifications             │  │
│  │ system         │ Connection status, pipeline state             │  │
│  └────────────────┴───────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 11.2 WebSocket Client Implementation

```typescript
// lib/ws-client.ts

type ConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

interface WSMessage {
  channel: string;
  type: string;
  data: any;
  timestamp: number;
  seq: number;
}

class WebSocketClient {
  private ws: WebSocket | null = null;
  private state: ConnectionState = 'disconnected';
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 50;
  private baseDelay = 1000;
  private maxDelay = 30000;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private subscriptions = new Set<string>();
  private messageBuffer: WSMessage[] = [];
  private handlers = new Map<string, Set<(data: any) => void>>();
  private lastSeq = 0;

  connect(url: string, token: string) {
    this.state = 'connecting';
    this.ws = new WebSocket(`${url}?token=${token}`);

    this.ws.onopen = () => {
      this.state = 'connected';
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      this.resubscribe();
      this.flushBuffer();
    };

    this.ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data);
      
      // Detect missed messages
      if (msg.seq > this.lastSeq + 1) {
        console.warn(`Missed ${msg.seq - this.lastSeq - 1} messages, requesting sync`);
        this.requestSync(msg.channel);
      }
      this.lastSeq = msg.seq;

      // Route to handlers
      const channelHandlers = this.handlers.get(msg.channel);
      if (channelHandlers) {
        channelHandlers.forEach(handler => handler(msg.data));
      }
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  subscribe(channel: string, handler: (data: any) => void) {
    if (!this.handlers.has(channel)) {
      this.handlers.set(channel, new Set());
    }
    this.handlers.get(channel)!.add(handler);
    this.subscriptions.add(channel);

    if (this.state === 'connected') {
      this.ws?.send(JSON.stringify({ type: 'subscribe', channel }));
    }
  }

  unsubscribe(channel: string) {
    this.subscriptions.delete(channel);
    this.handlers.delete(channel);
    if (this.state === 'connected') {
      this.ws?.send(JSON.stringify({ type: 'unsubscribe', channel }));
    }
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.state = 'disconnected';
      return;
    }

    this.state = 'reconnecting';
    const delay = Math.min(
      this.baseDelay * Math.pow(2, this.reconnectAttempts),
      this.maxDelay
    );
    this.reconnectAttempts++;

    setTimeout(() => this.connect(this.url!, this.token!), delay);
  }

  private startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }

  private flushBuffer() {
    this.messageBuffer.forEach(msg => {
      const handlers = this.handlers.get(msg.channel);
      handlers?.forEach(handler => handler(msg.data));
    });
    this.messageBuffer = [];
  }

  getState(): ConnectionState { return this.state; }
}

export const wsClient = new WebSocketClient();
```

### 11.3 Zustand Store Integration

```typescript
// stores/marketStore.ts

import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

interface Tick {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  time: number;
}

interface CandleUpdate {
  symbol: string;
  timeframe: string;
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface MarketState {
  ticks: Map<string, Tick>;
  candles: Map<string, CandleUpdate[]>;  // key: `${symbol}:${timeframe}`
  
  updateTick: (tick: Tick) => void;
  updateCandle: (update: CandleUpdate) => void;
  getLastTick: (symbol: string) => Tick | undefined;
}

export const useMarketStore = create<MarketState>()(
  subscribeWithSelector((set, get) => ({
    ticks: new Map(),
    candles: new Map(),

    updateTick: (tick) => set((state) => {
      const newTicks = new Map(state.ticks);
      newTicks.set(tick.symbol, tick);
      return { ticks: newTicks };
    }),

    updateCandle: (update) => set((state) => {
      const key = `${update.symbol}:${update.timeframe}`;
      const existing = state.candles.get(key) || [];
      const lastCandle = existing[existing.length - 1];
      
      let newCandles;
      if (lastCandle && lastCandle.time === update.time) {
        // Update existing candle
        newCandles = [...existing.slice(0, -1), update];
      } else {
        // New candle
        newCandles = [...existing, update].slice(-1000); // Keep last 1000
      }
      
      const newMap = new Map(state.candles);
      newMap.set(key, newCandles);
      return { candles: newMap };
    }),

    getLastTick: (symbol) => get().ticks.get(symbol),
  }))
);
```

### 11.4 Price Update Throttling

```typescript
// hooks/useThrottledPrice.ts
// Throttle price updates to 60fps to prevent UI jank

import { useMarketStore } from '@/stores/marketStore';
import { useRef, useCallback, useEffect } from 'react';

export function useThrottledPrice(symbol: string) {
  const tick = useMarketStore(state => state.ticks.get(symbol));
  const rafRef = useRef<number>(0);
  const lastUpdateRef = useRef<number>(0);

  // Throttle to ~60fps (16ms)
  useEffect(() => {
    if (!tick) return;
    
    const now = performance.now();
    if (now - lastUpdateRef.current < 16) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        // Update DOM with new price
        lastUpdateRef.current = performance.now();
      });
    } else {
      lastUpdateRef.current = now;
    }
  }, [tick]);

  return tick;
}
```

### 11.5 Connection Status Indicator

```typescript
// components/ui/ConnectionStatus.tsx

import { useWSState } from '@/hooks/useWSState';

export function ConnectionStatus() {
  const state = useWSState();
  
  const indicators = {
    connected: { color: 'bg-green-500', label: 'Online', pulse: false },
    connecting: { color: 'bg-yellow-500', label: 'Connecting...', pulse: true },
    reconnecting: { color: 'bg-yellow-500', label: 'Reconnecting...', pulse: true },
    disconnected: { color: 'bg-red-500', label: 'Offline', pulse: false },
  };

  const { color, label, pulse } = indicators[state];

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`h-2 w-2 rounded-full ${color} ${pulse ? 'animate-pulse' : ''}`} />
      <span className="text-muted-foreground">{label}</span>
    </div>
  );
}
```

---

## 12. PWA Capabilities

### 12.1 PWA Configuration

```typescript
// next.config.ts (with next-pwa)
import withPWA from 'next-pwa';

export default withPWA({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
  runtimeCaching: [
    // Static assets — Cache First
    {
      urlPattern: /^https:\/\/.*\.(js|css|woff2?|png|svg|ico)$/,
      handler: 'CacheFirst',
      options: {
        cacheName: 'static-assets',
        expiration: { maxEntries: 100, maxAgeSeconds: 30 * 24 * 60 * 60 },
      },
    },
    // API calls — Network First (fall back to cache)
    {
      urlPattern: /^https:\/\/.*\/api\//,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'api-cache',
        networkTimeoutSeconds: 5,
        expiration: { maxEntries: 50, maxAgeSeconds: 5 * 60 },
      },
    },
    // Chart historical data — Stale While Revalidate
    {
      urlPattern: /^https:\/\/.*\/api\/market\/candles/,
      handler: 'StaleWhileRevalidate',
      options: {
        cacheName: 'chart-data',
        expiration: { maxEntries: 20, maxAgeSeconds: 24 * 60 * 60 },
      },
    },
  ],
});
```

### 12.2 Web App Manifest

```json
// public/manifest.json
{
  "name": "Alpha Stack Trading",
  "short_name": "AlphaStack",
  "description": "Institutional-grade AI trading companion",
  "start_url": "/dashboard",
  "display": "standalone",
  "orientation": "any",
  "background_color": "#0a0a1a",
  "theme_color": "#1a1a2e",
  "categories": ["finance", "business"],
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/icons/icon-maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable" },
    { "src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ],
  "screenshots": [
    { "src": "/screenshots/dashboard.png", "sizes": "1280x720", "type": "image/png", "form_factor": "wide" },
    { "src": "/screenshots/mobile.png", "sizes": "390x844", "type": "image/png", "form_factor": "narrow" }
  ],
  "shortcuts": [
    { "name": "Dashboard", "url": "/dashboard", "icons": [{ "src": "/icons/dashboard.png", "sizes": "96x96" }] },
    { "name": "Trades", "url": "/trades", "icons": [{ "src": "/icons/trades.png", "sizes": "96x96" }] }
  ]
}
```

### 12.3 Offline Behavior

| Feature | Offline Behavior | Sync on Reconnect |
|---------|-----------------|-------------------|
| Dashboard | Shows last known positions, balance | Full state sync via WS snapshot |
| Charts | Shows cached historical data | Fetches missing candles |
| Trade History | Fully browsable (cached) | Fetches new entries |
| Analytics | Fully browsable (cached) | Recalculates with new data |
| Settings | Fully editable (cached) | Syncs changes to backend |
| **New Orders** | **BLOCKED** — requires connection | N/A |
| Position Close | **BLOCKED** — requires connection | N/A |

**Offline indicator:** Persistent banner at top of screen: "📴 You're offline. Trading is paused. Showing cached data."

### 12.4 Background Sync (When Supported)

```typescript
// When connection drops during an order attempt:
// 1. Order is queued in IndexedDB
// 2. Service worker registers for background sync
// 3. When connection restores, queued orders are submitted
// 4. User is notified of any price changes since queue time
// 5. If price moved > threshold, user must re-confirm

// NOTE: Critical trading operations should NOT be queued offline.
// This is for non-critical actions like:
// - Saving chart annotations
// - Updating settings
// - Bookmarking signals
```

### 12.5 Push Notifications (Cross-Platform)

```typescript
// Push notification strategy:

// Android (Chrome):
// ✅ Full Web Push API support
// - Trade alerts, risk warnings, signal notifications
// - Background delivery when app is closed

// iOS (Safari):
// ❌ PWA push notifications NOT supported (as of 2026)
// Workarounds:
// 1. In-app notifications via WebSocket (when tab is open)
// 2. Telegram bot alerts (recommended — works everywhere)
// 3. Email alerts for critical events
// 4. Optional native app wrapper (Capacitor) purely for push

// Desktop (Chrome, Edge, Firefox):
// ✅ Full Web Push API support
// - System notifications with action buttons
// - "Close Position" action directly from notification

// Registration:
async function registerPushNotifications() {
  const permission = await Notification.requestPermission();
  if (permission === 'granted') {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: process.env.NEXT_PUBLIC_VAPID_KEY,
    });
    // Send subscription to backend
    await fetch('/api/notifications/subscribe', {
      method: 'POST',
      body: JSON.stringify(subscription),
    });
  }
}
```

---

## 13. Dark Mode & Theming

### 13.1 Dark Mode as Default

Dark mode is the **default and primary theme** for Alpha Stack. This is non-negotiable — every serious trading platform (TradingView, Binance, Bloomberg, MetaTrader) defaults to dark. Traders stare at screens for hours; dark backgrounds reduce eye strain and make price colors (green/red) more vivid.

### 13.2 Theme Implementation

```typescript
// app/layout.tsx
import { ThemeProvider } from 'next-themes';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
```

### 13.3 Color System (CSS Variables)

```css
/* globals.css — Dark theme (default) */
:root {
  /* Background layers */
  --background: #0a0a1a;          /* Deepest background */
  --background-secondary: #111827; /* Card/panel backgrounds */
  --background-tertiary: #1f2937;  /* Elevated surfaces */
  
  /* Foreground */
  --foreground: #f9fafb;
  --foreground-secondary: #9ca3af;
  --foreground-muted: #6b7280;
  
  /* Borders */
  --border: #374151;
  --border-subtle: #1f2937;
  
  /* Trading colors */
  --color-bull: #22c55e;          /* Green for profit/buy */
  --color-bear: #ef4444;          /* Red for loss/sell */
  --color-bull-muted: rgba(34, 197, 94, 0.15);
  --color-bear-muted: rgba(239, 68, 68, 0.15);
  
  /* Status colors */
  --color-success: #22c55e;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --color-info: #3b82f6;
  
  /* Primary (accent) */
  --primary: #6366f1;
  --primary-foreground: #ffffff;
  
  /* Sidebar */
  --sidebar-background: #0f172a;
  --sidebar-foreground: #94a3b8;
  --sidebar-active: #6366f1;
}

/* Light theme (optional, for daytime use) */
.light {
  --background: #ffffff;
  --background-secondary: #f9fafb;
  --background-tertiary: #f3f4f6;
  --foreground: #111827;
  --foreground-secondary: #6b7280;
  --border: #e5e7eb;
  --color-bull: #16a34a;
  --color-bear: #dc2626;
}
```

### 13.4 Price Color Accessibility

```typescript
// components/ui/PriceChange.tsx
// Accessible price coloring that works in both themes

interface PriceChangeProps {
  value: number;
  previousValue?: number;
  showAnimation?: boolean;
}

export function PriceChange({ value, previousValue, showAnimation = true }: PriceChangeProps) {
  const direction = value > 0 ? 'bull' : value < 0 ? 'bear' : 'neutral';
  const isFlashing = showAnimation && previousValue !== undefined && value !== previousValue;

  return (
    <span
      className={cn(
        'font-mono tabular-nums transition-colors',
        direction === 'bull' && 'text-bull',
        direction === 'bear' && 'text-bear',
        direction === 'neutral' && 'text-foreground-secondary',
        isFlashing && direction === 'bull' && 'animate-flash-green',
        isFlashing && direction === 'bear' && 'animate-flash-red',
      )}
      aria-label={`${value > 0 ? 'Up' : value < 0 ? 'Down' : 'Unchanged'} ${Math.abs(value).toFixed(2)}`}
    >
      {value > 0 ? '+' : ''}{value.toFixed(5)}
    </span>
  );
}
```

---

## 14. Responsive Design

### 14.1 Breakpoint Strategy

| Breakpoint | Width | Target | Layout |
|------------|-------|--------|--------|
| `xs` | < 640px | Mobile portrait | Single column, stacked panels |
| `sm` | 640-767px | Mobile landscape | Single column, compact |
| `md` | 768-1023px | Tablet | Two-column (sidebar collapses) |
| `lg` | 1024-1279px | Small laptop | Full dashboard, compact sidebar |
| `xl` | 1280-1535px | Desktop | Full dashboard, expanded sidebar |
| `2xl` | ≥ 1536px | Large monitor | Multi-chart layouts, maximum density |

### 14.2 Mobile Layout (< 768px)

```
┌──────────────────────┐
│  Header (compact)     │
│  [☰] AlphaStack  [🔔]│
├──────────────────────┤
│                       │
│   PRICE CHART         │
│   (full width)        │
│   (touch gestures)    │
│                       │
├──────────────────────┤
│  [Positions] [Orders] │
│  [Signals]  [Journal] │
│                       │
│  Position #1          │
│  EURUSD BUY 0.02      │
│  P&L: +$5.20  [Close] │
│                       │
│  Position #2          │
│  BTCUSDT SELL 0.01    │
│  P&L: -$2.10  [Close] │
│                       │
├──────────────────────┤
│  Quick Trade          │
│  [BUY]  [SELL]        │
│  Size: [0.01▾]        │
│                       │
├──────────────────────┤
│  [📊] [📈] [📓] [⚙]  │
│  Nav    Trades Jrnl  Set│
└──────────────────────┘
```

### 14.3 Tablet Layout (768-1023px)

```
┌──────────────────────────────────┐
│  Header Bar                       │
├──────┬───────────────────────────┤
│ [☰]  │  Chart (full width)       │
│      │                           │
│ Side │                           │
│ bar  ├───────────────────────────┤
│ (coll│  Tabs: [Pos] [Ord] [Hist] │
│ apsed│  Table (scrollable)       │
│ )    │                           │
├──────┴───────────────────────────┤
│  Bottom bar: [Dashboard] [Trades]│
│  [Analytics] [Settings]          │
└──────────────────────────────────┘
```

### 14.4 Touch Interactions

```typescript
// Touch gesture support for mobile chart interaction:
// - Pinch to zoom (time axis)
// - Pan left/right (scroll through candles)
// - Double-tap to reset zoom
// - Long-press for crosshair
// - Swipe down to refresh data

// Implementation via Lightweight Charts built-in touch support
// + custom gesture handler for app-level interactions
```

### 14.5 Responsive Component Patterns

```typescript
// Pattern: Desktop shows full table, mobile shows card list

function PositionList({ positions }: { positions: Position[] }) {
  const isMobile = useMediaQuery('(max-width: 767px)');

  if (isMobile) {
    return (
      <div className="space-y-2">
        {positions.map(pos => (
          <PositionCard key={pos.ticket} position={pos} />
        ))}
      </div>
    );
  }

  return (
    <DataTable
      columns={positionColumns}
      data={positions}
      virtualScroll={positions.length > 100}
    />
  );
}
```

---

## 15. State Management Architecture

### 15.1 State Layer Design

```
┌──────────────────────────────────────────────────────────────┐
│                     STATE ARCHITECTURE                        │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  LAYER 1: Server State (TanStack Query)                 │  │
│  │  • Trade history, analytics, settings, agent configs    │  │
│  │  • Fetched via REST, cached with stale-while-revalidate│  │
│  │  • Background refetch on window focus                  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  LAYER 2: Real-Time State (Zustand)                     │  │
│  │  • Live prices, positions, P&L, signals, agent status  │  │
│  │  • Updated via WebSocket messages                      │  │
│  │  • Subscribed by components via selectors              │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  LAYER 3: UI State (Zustand / React state)              │  │
│  │  • Panel sizes, sidebar open/closed, active tab        │  │
│  │  • Modal visibility, form inputs, search queries       │  │
│  │  • Persisted to localStorage where appropriate         │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  LAYER 4: URL State (Next.js searchParams)              │  │
│  │  • Active instrument, timeframe, date range            │  │
│  │  • Shareable, bookmarkable, back-button compatible     │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 15.2 Store Definitions

```typescript
// stores/marketStore.ts — Real-time market data
// stores/tradeStore.ts — Positions, orders, P&L
// stores/signalStore.ts — AI signals, confluence scores
// stores/agentStore.ts — Agent health, status
// stores/settingsStore.ts — User preferences (persisted)
// stores/uiStore.ts — Panel state, modals, sidebar
```

### 15.3 TanStack Query Configuration

```typescript
// lib/query-client.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,         // 30 seconds
      gcTime: 5 * 60_000,        // 5 minutes
      refetchOnWindowFocus: true, // Refetch on tab focus
      retry: 2,
    },
  },
});

// Query keys (centralized for type safety)
export const queryKeys = {
  account: ['account'] as const,
  positions: ['positions'] as const,
  orders: ['orders'] as const,
  tradeHistory: (filters: TradeFilters) => ['trades', filters] as const,
  analytics: (period: string) => ['analytics', period] as const,
  signals: ['signals'] as const,
  agents: ['agents'] as const,
  settings: ['settings'] as const,
  journal: (filters: JournalFilters) => ['journal', filters] as const,
};
```

---

## 16. Performance Optimization

### 16.1 Code Splitting Strategy

```typescript
// Route-based splitting (automatic with Next.js App Router)
// Each page is a separate chunk loaded on navigation

// Component-based splitting for heavy components:
import dynamic from 'next/dynamic';

const PriceChart = dynamic(() => import('@/components/charts/PriceChart'), {
  loading: () => <ChartSkeleton />,
  ssr: false, // Charts are client-only
});

const EChartsHeatmap = dynamic(() => import('@/components/charts/EChartsHeatmap'), {
  loading: () => <ChartSkeleton />,
  ssr: false,
});

const TradeHistoryTable = dynamic(() => import('@/components/trading/TradeHistoryTable'));
```

### 16.2 Bundle Size Budget

| Chunk | Target (gzipped) | Contents |
|-------|------------------|----------|
| Framework | ~45 KB | React, React DOM |
| Next.js | ~30 KB | Router, hydration |
| Shared UI | ~40 KB | shadcn/ui, Tailwind runtime |
| Dashboard page | ~30 KB | Dashboard components |
| Charts | ~15 KB | TradingView LW Charts wrapper |
| **Total initial** | **~160 KB** | First paint payload |

### 16.3 Web Workers for Heavy Computation

```typescript
// workers/price-processor.worker.ts
// Offload indicator calculations from main thread

self.onmessage = (e) => {
  const { type, data } = e.data;
  
  switch (type) {
    case 'calculate-indicators': {
      const { candles, indicators } = data;
      const results = {};
      
      if (indicators.includes('rsi')) {
        results.rsi = calculateRSI(candles, 14);
      }
      if (indicators.includes('macd')) {
        results.macd = calculateMACD(candles, 12, 26, 9);
      }
      if (indicators.includes('bb')) {
        results.bollingerBands = calculateBB(candles, 20, 2);
      }
      
      self.postMessage({ type: 'indicators', data: results });
      break;
    }
    
    case 'calculate-pnl': {
      const { positions, prices } = data;
      const pnl = positions.map(pos => ({
        ticket: pos.ticket,
        pnl: calculatePnL(pos, prices[pos.symbol]),
        pnlPercent: calculatePnLPercent(pos, prices[pos.symbol]),
      }));
      self.postMessage({ type: 'pnl', data: pnl });
      break;
    }
  }
};
```

### 16.4 Memoization Patterns

```typescript
// Prevent re-rendering chart on every tick
const PriceChart = memo(({ data, timeframe }) => {
  // ...
}, (prev, next) => {
  // Only re-render if last candle changed
  return prev.data[prev.data.length - 1]?.time === 
         next.data[next.data.length - 1]?.time;
});

// Memoize expensive calculations
const pipValue = useMemo(
  () => calculatePipValue(symbol, lotSize, accountCurrency),
  [symbol, lotSize, accountCurrency]
);

// Memoize callbacks passed to child components
const handleClosePosition = useCallback(
  (ticket: number) => closePosition(ticket),
  [closePosition]
);
```

### 16.5 Virtual Scrolling

```typescript
// For tables with 1000+ rows (trade history, order book)

import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualTradeTable({ trades }: { trades: Trade[] }) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: trades.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48, // Row height in px
    overscan: 10,
  });

  return (
    <div ref={parentRef} className="h-[400px] overflow-auto">
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
        {virtualizer.getVirtualItems().map(virtualRow => (
          <div
            key={virtualRow.key}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualRow.size}px`,
              transform: `translateY(${virtualRow.start}px)`,
            }}
          >
            <TradeRow trade={trades[virtualRow.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 16.6 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| First Contentful Paint | < 1.5s | Lighthouse |
| Largest Contentful Paint | < 2.5s | Lighthouse |
| Total Blocking Time | < 200ms | Lighthouse |
| Cumulative Layout Shift | < 0.1 | Lighthouse |
| Time to Interactive | < 3s | Lighthouse |
| WebSocket reconnect | < 5s | Custom metric |
| Price tick → UI update | < 50ms | Custom metric |
| Chart initial render | < 1s | Custom metric |

---

## 17. Security Architecture

### 17.1 Security Layers

```
┌──────────────────────────────────────────────────────────────┐
│                    SECURITY ARCHITECTURE                       │
│                                                               │
│  Layer 1: Transport Security                                  │
│  ├── HTTPS enforced (HSTS header)                            │
│  ├── WSS for WebSocket (TLS encrypted)                       │
│  └── Certificate pinning (optional, for self-hosted)         │
│                                                               │
│  Layer 2: Authentication                                      │
│  ├── JWT in httpOnly cookies (never localStorage)            │
│  ├── Short-lived access tokens (15 min)                      │
│  ├── Refresh token rotation                                  │
│  ├── Device fingerprint binding                              │
│  └── Optional WebAuthn / biometric                           │
│                                                               │
│  Layer 3: Authorization                                       │
│  ├── Role-based access (admin, trader, viewer)               │
│  ├── Per-action permissions (view, trade, configure)         │
│  └── Session-scoped permissions                              │
│                                                               │
│  Layer 4: Input Validation                                    │
│  ├── Zod schemas on all order parameters                     │
│  ├── Price/size bounds checking                              │
│  └── SQL injection prevention (parameterized queries)        │
│                                                               │
│  Layer 5: Content Security Policy                             │
│  ├── Strict CSP headers                                      │
│  ├── Nonce-based script loading                              │
│  └── No inline scripts                                       │
│                                                               │
│  Layer 6: Rate Limiting                                       │
│  ├── API route rate limiting (per-user, per-IP)              │
│  ├── Order submission throttling                             │
│  └── Login attempt limiting                                  │
│                                                               │
│  Layer 7: Audit Logging                                       │
│  ├── Every trade action logged with timestamp, IP, device    │
│  ├── Settings changes logged                                 │
│  └── Login/logout events logged                              │
└──────────────────────────────────────────────────────────────┘
```

### 17.2 Content Security Policy

```typescript
// middleware.ts
export function middleware(request: NextRequest) {
  const nonce = crypto.randomUUID();
  
  const cspHeader = `
    default-src 'self';
    script-src 'self' 'nonce-${nonce}' 'strict-dynamic';
    style-src 'self' 'unsafe-inline';
    connect-src 'self' wss://${request.headers.get('host')} https://api.alphastack.app;
    img-src 'self' data: blob:;
    font-src 'self' https://fonts.gstatic.com;
    frame-ancestors 'none';
    base-uri 'self';
    form-action 'self';
  `.replace(/\s{2,}/g, ' ').trim();

  const response = NextResponse.next();
  response.headers.set('Content-Security-Policy', cspHeader);
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  
  return response;
}
```

### 17.3 BFF Proxy Pattern (Credentials Never Reach Browser)

```typescript
// api/trade/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { verifyJWT } from '@/lib/auth';
import { z } from 'zod';

const OrderSchema = z.object({
  symbol: z.string().regex(/^[A-Z]{3}\/[A-Z]{3,4}$/),
  direction: z.enum(['BUY', 'SELL']),
  orderType: z.enum(['MARKET', 'LIMIT', 'STOP']),
  size: z.number().positive().max(10),
  price: z.number().positive().optional(),
  stopLoss: z.number().positive(),
  takeProfit: z.number().positive(),
});

export async function POST(request: NextRequest) {
  // 1. Authenticate
  const token = request.cookies.get('access_token')?.value;
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  
  const user = await verifyJWT(token);
  if (!user) return NextResponse.json({ error: 'Invalid token' }, { status: 401 });

  // 2. Validate input
  const body = await request.json();
  const order = OrderSchema.safeParse(body);
  if (!order.success) {
    return NextResponse.json({ error: order.error.flatten() }, { status: 400 });
  }

  // 3. Proxy to backend (credentials are server-side only)
  const backendResponse = await fetch(`${process.env.BACKEND_URL}/api/v1/trade`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.BACKEND_API_KEY}`,
    },
    body: JSON.stringify(order.data),
  });

  // 4. Return result
  const result = await backendResponse.json();
  return NextResponse.json(result, { status: backendResponse.status });
}
```

---

## 18. Project Structure

### 18.1 Complete Directory Layout

```
alphastack-web/
├── public/
│   ├── icons/                    # PWA icons
│   ├── screenshots/              # PWA screenshots
│   ├── sounds/                   # Alert sound files
│   ├── manifest.json             # PWA manifest
│   └── sw.js                     # Service worker (generated)
│
├── src/
│   ├── app/                      # Next.js App Router
│   │   ├── layout.tsx            # Root layout (providers, theme, fonts)
│   │   ├── page.tsx              # Redirect to /dashboard
│   │   ├── globals.css           # Tailwind + CSS variables
│   │   │
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   │
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx        # Dashboard shell (sidebar + header)
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── trades/page.tsx
│   │   │   ├── analytics/page.tsx
│   │   │   ├── agents/page.tsx
│   │   │   ├── journal/page.tsx
│   │   │   └── settings/
│   │   │       ├── page.tsx
│   │   │       ├── broker/page.tsx
│   │   │       ├── strategy/page.tsx
│   │   │       ├── risk/page.tsx
│   │   │       ├── notifications/page.tsx
│   │   │       ├── ai/page.tsx
│   │   │       ├── appearance/page.tsx
│   │   │       └── security/page.tsx
│   │   │
│   │   └── api/
│   │       ├── auth/
│   │       │   ├── [...nextauth]/route.ts
│   │       │   ├── login/route.ts
│   │       │   ├── refresh/route.ts
│   │       │   └── sessions/route.ts
│   │       ├── market/
│   │       │   ├── candles/route.ts
│   │       │   └── prices/route.ts
│   │       ├── trade/
│   │       │   ├── route.ts
│   │       │   ├── close/route.ts
│   │       │   └── modify/route.ts
│   │       ├── agent/
│   │       │   ├── status/route.ts
│   │       │   └── signals/route.ts
│   │       └── notifications/
│   │           └── subscribe/route.ts
│   │
│   ├── components/
│   │   ├── ui/                   # shadcn/ui primitives
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── table.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── toast.tsx
│   │   │   └── ...
│   │   │
│   │   ├── layout/               # Layout components
│   │   │   ├── HeaderBar.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── DashboardShell.tsx
│   │   │   └── MobileNav.tsx
│   │   │
│   │   ├── charts/               # Chart components
│   │   │   ├── PriceChart.tsx
│   │   │   ├── EquityCurve.tsx
│   │   │   ├── PnLHeatmap.tsx
│   │   │   ├── CorrelationMatrix.tsx
│   │   │   ├── DrawdownChart.tsx
│   │   │   ├── ConfidenceGauge.tsx
│   │   │   ├── ConfluenceRadar.tsx
│   │   │   └── MiniSparkline.tsx
│   │   │
│   │   ├── trading/              # Trading components
│   │   │   ├── OrderEntry.tsx
│   │   │   ├── PositionTable.tsx
│   │   │   ├── PositionCard.tsx
│   │   │   ├── PendingOrdersTable.tsx
│   │   │   ├── TradeHistoryTable.tsx
│   │   │   ├── ModifyOrderModal.tsx
│   │   │   ├── QuickTrade.tsx
│   │   │   └── WatchList.tsx
│   │   │
│   │   ├── ai/                   # AI/Agent components
│   │   │   ├── AIPanel.tsx
│   │   │   ├── SignalCard.tsx
│   │   │   ├── SignalFeed.tsx
│   │   │   ├── AgentGrid.tsx
│   │   │   ├── AgentCard.tsx
│   │   │   ├── PipelineView.tsx
│   │   │   └── AgentPerformanceTable.tsx
│   │   │
│   │   ├── journal/              # Journal components
│   │   │   ├── JournalEntry.tsx
│   │   │   ├── JournalList.tsx
│   │   │   ├── TradeDetailModal.tsx
│   │   │   ├── WeeklySummary.tsx
│   │   │   └── JournalFilters.tsx
│   │   │
│   │   ├── analytics/            # Analytics components
│   │   │   ├── KeyMetrics.tsx
│   │   │   ├── WinRateByStrategy.tsx
│   │   │   ├── PnLBySession.tsx
│   │   │   ├── RiskMetrics.tsx
│   │   │   └── ExportButton.tsx
│   │   │
│   │   └── settings/             # Settings components
│   │       ├── BrokerCard.tsx
│   │       ├── StrategyWeights.tsx
│   │       ├── RiskRulesForm.tsx
│   │       ├── NotificationPrefs.tsx
│   │       ├── KillSwitch.tsx
│   │       └── ConnectionTest.tsx
│   │
│   ├── hooks/                    # Custom React hooks
│   │   ├── useWebSocket.ts       # WebSocket connection manager
│   │   ├── useWSState.ts         # Connection state
│   │   ├── useThrottledPrice.ts  # Throttled price updates
│   │   ├── usePositions.ts       # Position state
│   │   ├── useSignals.ts         # Signal state
│   │   ├── useMediaQuery.ts      # Responsive breakpoints
│   │   └── useKeyboardShortcuts.ts
│   │
│   ├── stores/                   # Zustand stores
│   │   ├── marketStore.ts
│   │   ├── tradeStore.ts
│   │   ├── signalStore.ts
│   │   ├── agentStore.ts
│   │   ├── settingsStore.ts
│   │   └── uiStore.ts
│   │
│   ├── lib/                      # Utilities
│   │   ├── ws-client.ts          # WebSocket client
│   │   ├── api-client.ts         # REST API client
│   │   ├── auth.ts               # JWT utilities
│   │   ├── query-client.ts       # TanStack Query config
│   │   ├── calculations.ts       # P&L, margin, pip calculations
│   │   ├── formatters.ts         # Price, date, percentage formatters
│   │   ├── constants.ts          # App constants
│   │   └── validations.ts        # Zod schemas
│   │
│   ├── workers/                  # Web Workers
│   │   └── price-processor.worker.ts
│   │
│   └── types/                    # TypeScript types
│       ├── market.ts
│       ├── trade.ts
│       ├── signal.ts
│       ├── agent.ts
│       ├── settings.ts
│       └── api.ts
│
├── middleware.ts                  # Next.js middleware (CSP, auth)
├── next.config.ts                 # Next.js configuration
├── tailwind.config.ts             # Tailwind configuration
├── tsconfig.json                  # TypeScript configuration
├── package.json
└── .env.local                     # Environment variables
```

---

## 19. API Integration Layer

### 19.1 REST API Endpoints (BFF → Backend)

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| `POST` | `/api/auth/login` | Login, issue JWT | No |
| `POST` | `/api/auth/refresh` | Refresh access token | Cookie |
| `POST` | `/api/auth/logout` | Revoke session | Cookie |
| `GET` | `/api/auth/sessions` | List active sessions | JWT |
| `DELETE` | `/api/auth/sessions/:id` | Revoke session | JWT |
| `GET` | `/api/market/prices` | Current prices for subscribed symbols | JWT |
| `GET` | `/api/market/candles` | Historical OHLCV data | JWT |
| `GET` | `/api/trade` | Open positions + pending orders | JWT |
| `POST` | `/api/trade` | Place new order | JWT |
| `POST` | `/api/trade/close` | Close position | JWT |
| `POST` | `/api/trade/modify` | Modify SL/TP | JWT |
| `GET` | `/api/trade/history` | Trade history (paginated, filterable) | JWT |
| `GET` | `/api/agent/status` | All agent health/status | JWT |
| `GET` | `/api/agent/signals` | Active signals | JWT |
| `GET` | `/api/analytics` | Performance metrics | JWT |
| `GET` | `/api/settings` | User settings | JWT |
| `PUT` | `/api/settings` | Update settings | JWT |
| `POST` | `/api/trading/pause` | Pause all trading | JWT |
| `POST` | `/api/trading/resume` | Resume trading | JWT |
| `POST` | `/api/trading/kill-switch` | Emergency flatten all | JWT |

### 19.2 WebSocket Channels (Client → Server)

```json
// Subscribe
{ "type": "subscribe", "channels": ["prices", "positions", "signals"] }

// Unsubscribe
{ "type": "unsubscribe", "channels": ["prices"] }

// Request sync (after reconnection)
{ "type": "sync", "channels": ["positions", "account"] }

// Heartbeat
{ "type": "ping" }
```

### 19.3 WebSocket Messages (Server → Client)

```json
// Price tick
{ "channel": "prices", "type": "tick", "data": { "symbol": "EURUSD", "bid": 1.08532, "ask": 1.08545, "time": 1689012345678 }, "seq": 42 }

// Position update
{ "channel": "positions", "type": "update", "data": { "ticket": 12345, "pnl": 5.20, "currentPrice": 1.08580 }, "seq": 43 }

// New signal
{ "channel": "signals", "type": "new", "data": { "symbol": "GBPUSD", "direction": "BUY", "confidence": 0.82, "confluence": 85 }, "seq": 44 }

// Account update
{ "channel": "account", "type": "update", "data": { "balance": 523.40, "equity": 535.70, "margin": 20.50 }, "seq": 45 }

// Agent health
{ "channel": "agents", "type": "health", "data": { "agentId": "smc_agent_01", "status": "healthy", "latencyMs": 340 }, "seq": 46 }

// Alert
{ "channel": "alerts", "type": "risk", "data": { "level": "warning", "message": "Daily loss approaching 5% limit", "action": "reduce_positions" }, "seq": 47 }
```

---

## 20. Testing Strategy

### 20.1 Testing Pyramid

| Layer | Tool | Coverage Target | What to Test |
|-------|------|----------------|--------------|
| **Unit** | Vitest | > 80% | Calculations, formatters, validators, store logic |
| **Component** | Vitest + Testing Library | > 70% | Component rendering, user interactions, state updates |
| **Integration** | Vitest + MSW | > 60% | API routes, WebSocket handling, auth flow |
| **E2E** | Playwright | Critical paths | Login → Dashboard → Place order → Close position |
| **Visual** | Playwright screenshots | Key pages | Dashboard, charts, mobile layouts |

### 20.2 Critical Test Scenarios

```typescript
// tests/e2e/trading.spec.ts
test.describe('Trading Flow', () => {
  test('login and view dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.fill('[name=email]', 'trader@alphastack.app');
    await page.fill('[name=password]', 'secure-password');
    await page.click('button[type=submit]');
    await expect(page).toHaveURL('/dashboard');
    await expect(page.locator('[data-testid=balance]')).toBeVisible();
  });

  test('place market order', async ({ page }) => {
    // ... navigate to order entry, fill form, submit
    await expect(page.locator('[data-testid=position-table]')).toContainText('EURUSD');
  });

  test('WebSocket reconnection', async ({ page }) => {
    // Simulate connection drop
    // Verify reconnection indicator appears
    // Verify data resumes after reconnect
  });
});
```

### 20.3 Financial Calculation Tests

```typescript
// tests/unit/calculations.test.ts
describe('P&L Calculations', () => {
  test('EURUSD BUY profit calculation', () => {
    const position = { symbol: 'EURUSD', direction: 'BUY', size: 0.01, openPrice: 1.0800 };
    const currentPrice = 1.0850;
    const pnl = calculatePnL(position, currentPrice);
    expect(pnl).toBeCloseTo(5.0, 2); // 50 pips × 0.01 lots × $1/pip
  });

  test('position sizing with risk percentage', () => {
    const size = calculatePositionSize({
      accountBalance: 500,
      riskPercent: 1.5,
      stopLossPips: 32,
      symbol: 'EURUSD',
    });
    expect(size).toBeCloseTo(0.02, 2);
  });
});
```

---

## 21. Deployment Architecture

### 21.1 Deployment Options

| Option | Cost | Complexity | Best For |
|--------|------|-----------|----------|
| **Vercel** | Free tier available | ★☆☆ Lowest | Quick start, global CDN, edge functions |
| **Self-hosted (Docker)** | $0 (same machine) | ★★☆ Medium | Full control, LAN access, no external dependency |
| **Cloudflare Pages** | Free tier | ★☆☆ Lowest | Static-heavy, edge-first |
| **VPS (Hetzner/DO)** | $5/mo | ★★☆ Medium | Full control, custom domain |

### 21.2 Recommended: Self-Hosted + Cloudflare Tunnel

For Alpha Stack, the web app runs **on the same machine as the desktop app**:

```
┌─────────────────────────────────────────────────────────────┐
│  User's Machine (Linux/Windows/Mac)                          │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Alpha Stack  │  │  Alpha Stack │  │  Next.js Web App │  │
│  │  Desktop      │  │  Backend     │  │  (port 3000)     │  │
│  │  (Tauri)      │  │  (port 9222) │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Cloudflare Tunnel (optional, for remote access)      │   │
│  │  *.trycloudflare.com → localhost:3000                 │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 21.3 Docker Configuration

```dockerfile
# Dockerfile
FROM node:22-alpine AS base

FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
```

### 21.4 Environment Variables

```bash
# .env.local
# Backend connection
BACKEND_URL=http://localhost:9222
BACKEND_WS_URL=ws://localhost:9222/ws
BACKEND_API_KEY=your-backend-api-key

# Auth
JWT_SECRET=your-jwt-secret-min-32-chars
JWT_ACCESS_EXPIRY=15m
JWT_REFRESH_EXPIRY=7d

# PWA
NEXT_PUBLIC_VAPID_KEY=your-vapid-public-key
VAPID_PRIVATE_KEY=your-vapid-private-key

# App
NEXT_PUBLIC_APP_URL=https://alphastack.local
```

---

## 22. Development Roadmap

### Phase 1: Foundation (Weeks 1–3)

- [ ] Next.js 15 project scaffolding with TypeScript, Tailwind, shadcn/ui
- [ ] Root layout with dark theme, sidebar navigation, header bar
- [ ] JWT authentication flow (login, refresh, logout, session management)
- [ ] WebSocket client with reconnection, channel subscriptions, heartbeat
- [ ] Zustand stores (market, trade, signal, settings)
- [ ] TanStack Query configuration with REST API client
- [ ] PWA manifest and service worker setup
- [ ] Responsive breakpoint system

### Phase 2: Dashboard & Charts (Weeks 4–6)

- [ ] Dashboard layout with resizable panels (`react-resizable-panels`)
- [ ] TradingView Lightweight Charts integration (candlestick, volume)
- [ ] Multi-timeframe support (1m, 5m, 15m, 1h, 4h, 1d)
- [ ] Real-time price updates via WebSocket → Zustand → Chart
- [ ] Watchlist with live prices
- [ ] Indicator overlays (SMA, EMA, Bollinger Bands)
- [ ] RSI and MACD sub-charts
- [ ] Crosshair with OHLCV data display
- [ ] Chart skeleton loading states

### Phase 3: Trading UI (Weeks 7–9)

- [ ] Order entry component (market, limit, stop)
- [ ] Position table with virtual scrolling, live P&L
- [ ] Position modification modal (SL/TP adjustment)
- [ ] One-click close and partial close
- [ ] Quick trade panel
- [ ] Pending orders table
- [ ] Trade history table with filters and export
- [ ] Kill switch and pause trading controls
- [ ] Keyboard shortcuts (B/S for buy/sell, Esc to cancel)

### Phase 4: AI & Analytics (Weeks 10–12)

- [ ] AI panel with confidence gauge and signal feed
- [ ] Agent monitoring grid with health indicators
- [ ] Pipeline visualization (step-by-step flow)
- [ ] Agent performance table
- [ ] Equity curve chart (ECharts)
- [ ] P&L heatmap by day/pair
- [ ] Win rate by strategy breakdown
- [ ] Risk metrics dashboard (Sharpe, Sortino, max DD)
- [ ] Journal page with entry list, filters, weekly summary
- [ ] Trade detail modal with full AI analysis

### Phase 5: Settings & Polish (Weeks 13–14)

- [ ] Broker connection management UI
- [ ] Strategy parameter configuration
- [ ] Risk management rules form
- [ ] Notification preferences
- [ ] AI agent configuration
- [ ] Appearance settings
- [ ] Push notification registration
- [ ] Performance optimization (Lighthouse audit, bundle analysis)
- [ ] E2E tests for critical paths
- [ ] Accessibility audit (keyboard navigation, screen reader)

### Phase 6: PWA & Distribution (Weeks 15–16)

- [ ] Offline support with service worker caching
- [ ] Install prompt for mobile/desktop
- [ ] Background sync for non-critical operations
- [ ] Push notifications (Android, Desktop)
- [ ] Telegram bot integration for iOS alerts
- [ ] Cloudflare Tunnel setup for remote access
- [ ] Docker configuration for self-hosted deployment
- [ ] Documentation (user guide, API reference)

---

## Appendix A: Design Decisions Log

| Decision | Choice | Rationale | Trade-off |
|----------|--------|-----------|-----------|
| Framework | Next.js 15 | Largest ecosystem, SSR, API routes as BFF | Heavier than Svelte/Astro |
| State management | Zustand + TanStack Query | Lightweight, no boilerplate, excellent for real-time | Less structured than Redux |
| Charting | TradingView LW Charts | 12KB, purpose-built, Canvas-based, dark mode native | Fewer chart types than ECharts |
| WebSocket | Custom client | Full control over reconnection, buffering, channel routing | More code than Socket.IO |
| Auth storage | httpOnly cookies | XSS-immune, server-controlled | Can't read tokens in JS (by design) |
| Panel layout | react-resizable-panels | Lightweight, accessible, keyboard-navigable | Less flexible than custom solution |
| Tables | TanStack Table + Virtual | Virtual scrolling, type-safe, headless | More setup than simple HTML tables |
| PWA | next-pwa | Automatic service worker generation | iOS push notifications unsupported |
| Deployment | Self-hosted + Cloudflare Tunnel | Zero cost, no external dependency, LAN + internet access | Requires user to manage server |

## Appendix B: Accessibility Checklist

- [ ] All interactive elements keyboard-accessible
- [ ] Color is not the only indicator of state (use icons + text + color)
- [ ] ARIA labels on all chart components
- [ ] Screen reader announcements for price changes (aria-live region)
- [ ] Focus management in modals and dialogs
- [ ] High contrast mode support
- [ ] Reduced motion option (disable animations)
- [ ] Minimum touch target size 44×44px on mobile

## Appendix C: Browser Compatibility Matrix

| Feature | Chrome 90+ | Firefox 90+ | Safari 15+ | Edge 90+ |
|---------|------------|-------------|------------|----------|
| WebSocket | ✅ | ✅ | ✅ | ✅ |
| Service Worker | ✅ | ✅ | ✅ | ✅ |
| Web Push | ✅ | ✅ | ❌ iOS | ✅ |
| WebAuthn | ✅ | ✅ | ✅ | ✅ |
| Web Workers | ✅ | ✅ | ✅ | ✅ |
| CSS Grid | ✅ | ✅ | ✅ | ✅ |
| CSS Container Queries | ✅ | ✅ | ✅ 16+ | ✅ |
| Canvas 2D | ✅ | ✅ | ✅ | ✅ |
| IndexedDB | ✅ | ✅ | ✅ | ✅ |
| Web Share API | ✅ | ✅ | ✅ | ✅ |

---

*Architecture designed for Alpha Stack v1.0 — Web companion for institutional-grade AI trading.*
*Next: Begin Phase 1 implementation — Next.js scaffolding + auth + WebSocket infrastructure.*
