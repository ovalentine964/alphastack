# Alpha Stack — Web Application Research Report

**Date:** 2026-07-11  
**Purpose:** Research findings for building a browser-based companion app for an institutional-grade AI forex/crypto trading system

---

## 1. Frontend Frameworks

### Recommendation: **Next.js (React + TypeScript)**

| Framework | Bundle Size | Learning Curve | Ecosystem | Real-Time Fit | SSR/SSG | TypeScript |
|-----------|------------|----------------|-----------|---------------|---------|------------|
| **Next.js (React)** | Medium | Medium | ★★★★★ Largest | ★★★★★ | ★★★★★ Built-in | ★★★★★ Native |
| Vue.js / Nuxt | Small-Med | Low | ★★★★ | ★★★★ | ★★★★ | ★★★ Good |
| Svelte/SvelteKit | ★ Smallest | Low | ★★★ Growing | ★★★★★ | ★★★★ | ★★★★ |
| Angular | Largest | High | ★★★★ Enterprise | ★★★★ | ★★★★ | ★★★★★ Native |

**Why Next.js wins for Alpha Stack:**

1. **Largest talent pool** — Easiest to hire for. React developers are 10x more available than Svelte developers.
2. **API Routes** — Built-in backend-for-frontend (BFF) pattern. Perfect for proxying broker APIs, handling JWT refresh, and serving WebSocket upgrade endpoints without a separate server.
3. **App Router + React Server Components** — Server-side rendering for initial dashboard load, client components for real-time charts. Best of both worlds.
4. **TypeScript native** — Critical for financial calculations. Type safety prevents decimal/float errors in order sizing.
5. **Massive ecosystem** — Every charting library, auth library, and UI toolkit has first-class React support.
6. **Edge Runtime** — Deploy API routes to edge locations for low-latency broker API proxying globally.

**When to consider alternatives:**
- **Svelte/SvelteKit** — If bundle size is paramount and team is small (< 3 devs). Smallest bundles, best raw performance, but smaller ecosystem.
- **Vue/Nuxt** — If team has strong Vue experience. Gentler learning curve, excellent docs.

**Key libraries to pair with Next.js:**
- `@tanstack/react-query` — Server state management, caching, background refetch
- `zustand` — Lightweight client state (positions, settings, UI state)
- `tailwindcss` — Utility-first CSS, perfect for rapid dashboard prototyping
- `shadcn/ui` — Copy-paste accessible components, dark mode built-in
- `framer-motion` — Smooth transitions for dashboard panels

---

## 2. Real-Time Data in Browser

### Transport Layer Comparison

| Protocol | Direction | Latency | Complexity | Browser Support | Best For |
|----------|-----------|---------|------------|-----------------|----------|
| **WebSocket** | Bidirectional | Low (~1-5ms) | Medium | 99%+ | **Price streaming, order execution** |
| SSE | Server→Client | Low-Med | Low | 99%+ | News feeds, position updates |
| WebTransport | Bidirectional | Lowest (~0.5ms) | High | ~85% (no Safari yet) | Future: ultra-low latency tick data |
| Long Polling | Bidirectional | High | Low | 100% | Fallback only |

### Recommendation: **WebSocket (primary) + SSE (secondary)**

**WebSocket for trading-critical data:**
- Live price streaming (bid/ask ticks)
- Order execution status
- Position updates (P&L changes)
- Account balance updates

**SSE for supplementary feeds:**
- News/event streams
- AI signal notifications
- System status updates
- Less critical one-way data

**WebSocket architecture pattern:**
```
Browser ←→ WebSocket Server ←→ Price Feed (OANDA/Binance)
                         ←→ Order Engine
                         ←→ AI Signal Generator
```

**Reconnection strategy (critical for trading):**
- Exponential backoff: 1s → 2s → 4s → 8s → max 30s
- Heartbeat ping every 30s to detect dead connections
- On reconnect: request snapshot of missed data (last N ticks, current positions)
- Visual indicator showing connection status (green/yellow/red)

**Why not WebTransport yet:**
- Safari support still missing as of mid-2026 (critical for iOS traders)
- Can be added later as an upgrade path for latency-sensitive features

### Chart Rendering

| Library | Bundle Size | Candlestick | Real-Time Perf | Canvas/SVG | Best For |
|---------|------------|-------------|----------------|------------|----------|
| **TradingView Lightweight Charts** | ~12 KB gzipped | ★★★★★ Purpose-built | ★★★★★ Hundreds of ticks/sec | Canvas | **Primary: price charts** |
| Apache ECharts | 80-130 KB | ★★★★ Native | ★★★★ | Canvas/WebGL | Dashboard analytics, heatmaps |
| D3.js | ~80 KB | ★★ DIY | ★★★ | SVG/Canvas | Custom visualizations |
| Recharts | ~50 KB | ★ Workaround | ★★★ (jank at 1k+ points) | SVG | Simple dashboard charts |

### Recommendation: **TradingView Lightweight Charts (primary) + ECharts (secondary)**

**TradingView Lightweight Charts v5:**
- 12 KB gzipped — smallest of any chart library
- Purpose-built for financial time-series: candlesticks, lines, areas, volume histograms
- Canvas rendering — stays smooth with hundreds of data refreshes per second
- v5 (April 2026) is the latest major release
- Dark mode native (dark background is default)
- Perfect for: main price chart, order book visualization

**ECharts for supplementary charts:**
- P&L heatmaps
- Portfolio allocation treemaps
- Correlation matrices
- Custom analytics with drill-down support

**Canvas vs SVG for trading:**
- **Canvas wins** for real-time trading charts. SVG re-renders entire DOM tree on each update; Canvas only redraws changed pixels.
- Canvas handles 10,000+ data points smoothly; SVG chokes at ~1,000.
- Use SVG only for static/interactive UI elements (icons, logos, small diagrams).

---

## 3. Browser-Based Trading UI Design

### Dashboard Layout (Multi-Panel)

```
┌─────────────────────────────────────────────────────────────┐
│  HEADER: Account Summary | Balance | P&L Today | Connection │
├──────────────────────┬──────────────────────────────────────┤
│                      │                                      │
│   WATCHLIST          │        MAIN CHART                    │
│   (price table)      │   (TradingView Lightweight Charts)   │
│                      │   Multi-timeframe tabs               │
│                      │   Drawing tools overlay              │
├──────────────────────┼──────────────────────────────────────┤
│                      │                                      │
│   ORDER ENTRY        │     POSITIONS / ORDERS TABLE         │
│   • Market/Limit     │   (virtual scrolling)                │
│   • Size calculator   │   • Open positions with live P&L    │
│   • Stop/Target      │   • Pending orders                   │
│   • One-click trade  │   • Trade history                    │
│                      │                                      │
├──────────────────────┴──────────────────────────────────────┤
│  AI PANEL: Signals | Model Confidence | Risk Assessment     │
└─────────────────────────────────────────────────────────────┘
```

### Key UI Patterns for Trading

1. **Dark mode as default** — Traders stare at screens for hours. Dark backgrounds reduce eye strain. Every major trading platform (TradingView, Binance, Bloomberg) defaults to dark.

2. **Resizable panels** — Use `react-resizable-panels` or `allotment` for drag-to-resize layout sections. Traders customize their workspace obsessively.

3. **One-click trading** — Reduce order entry to minimum clicks. Pre-configured lot sizes. Keyboard shortcuts (B for buy, S for sell, Esc for cancel).

4. **Real-time P&L display** — Green/red coloring for profit/loss. Animate number changes. Show both absolute and percentage.

5. **Multi-chart layouts** — Support 1x1, 2x1, 2x2 grid layouts. Each chart can show different instrument or timeframe. Sync crosshair across charts.

6. **Order book visualization** — Horizontal or vertical depth chart. Color-coded bid/ask levels. Volume profile overlay.

7. **Alert system** — Visual + audio notifications for price alerts, order fills, stop hits. Toast notifications that don't block trading UI.

### Component Architecture

```
src/
├── app/                    # Next.js App Router
│   ├── layout.tsx          # Root layout with providers
│   ├── dashboard/          # Main trading dashboard
│   ├── analytics/          # P&L analytics, reports
│   └── settings/           # Account, strategy config
├── components/
│   ├── charts/             # Chart wrappers
│   │   ├── PriceChart.tsx  # TradingView LW Charts wrapper
│   │   ├── PnLHeatmap.tsx  # ECharts P&L heatmap
│   │   └── CorrelationMatrix.tsx
│   ├── trading/            # Trading-specific components
│   │   ├── OrderEntry.tsx
│   │   ├── PositionTable.tsx
│   │   └── WatchList.tsx
│   ├── ai/                 # AI signal components
│   │   ├── SignalPanel.tsx
│   │   └── ConfidenceGauge.tsx
│   └── ui/                 # Shared UI components
├── hooks/
│   ├── useWebSocket.ts     # WebSocket connection manager
│   ├── usePriceStream.ts   # Price data with buffering
│   └── usePositions.ts     # Position state management
├── lib/
│   ├── ws-client.ts        # WebSocket client with reconnection
│   ├── price-buffer.ts     # Tick data buffer/debounce
│   └── calculations.ts     # P&L, margin, pip calculations
└── workers/
    └── price-processor.worker.ts  # Heavy computation off main thread
```

---

## 4. PWA (Progressive Web App)

### Can PWA Replace Native for Trading?

**Short answer: Yes, for most use cases. No for push notifications on iOS.**

| Feature | PWA Support | Notes |
|---------|-------------|-------|
| Offline dashboard view | ✅ | Cache last known positions, charts |
| Install to home screen | ✅ | Works on Android, Chrome, Edge |
| Push notifications | ⚠️ | Android ✅, iOS Safari ❌ (still missing in 2026) |
| Background sync | ✅ | Queue orders when offline, execute when back |
| Biometric auth | ✅ | WebAuthn API, Face ID/Touch ID on iOS Safari |
| Full-screen mode | ✅ | `display: "standalone"` in manifest |
| File system access | ✅ | For exporting trade logs, reports |

### PWA Implementation Strategy

**Service Worker caching strategy:**
```
Cache-First:  Static assets (JS, CSS, fonts, icons)
Network-First: API calls, price data (fall back to cached)
Stale-While-Revalidate: Chart historical data, news
```

**Web App Manifest (`manifest.json`):**
```json
{
  "name": "Alpha Stack Trading",
  "short_name": "AlphaStack",
  "start_url": "/dashboard",
  "display": "standalone",
  "background_color": "#0a0a1a",
  "theme_color": "#1a1a2e",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

**Background Sync for offline trading:**
- Queue orders when connection drops
- Show "Queued" status to user
- Auto-execute when connection restores
- Alert user if market moved significantly during offline period

### Push Notifications Workaround (iOS)

Since iOS Safari still doesn't support PWA push notifications in 2026:
- **Primary:** Use in-app notifications (WebSocket-driven toast/snackbar)
- **Secondary:** Email alerts for critical events (margin calls, stop hits)
- **Optional:** Companion native app (React Native or Capacitor wrapper) purely for push notification relay

---

## 5. Performance Optimization

### Code Splitting & Lazy Loading

```typescript
// Next.js dynamic imports — load dashboard panels on demand
const PriceChart = dynamic(() => import('@/components/charts/PriceChart'), {
  loading: () => <ChartSkeleton />,
  ssr: false  // Charts are client-only
});

const PositionTable = dynamic(() => import('@/components/trading/PositionTable'));
const AnalyticsPanel = dynamic(() => import('@/components/analytics/AnalyticsPanel'));
```

**Splitting strategy:**
- **Initial load:** Dashboard shell, auth, WebSocket manager (~150 KB)
- **Lazy load:** Charts, order entry, analytics, settings (~200 KB each)
- **Route-based:** Separate bundles for dashboard, analytics, settings pages

### Web Workers for Heavy Computation

Offload from main thread to prevent UI jank during price updates:

```typescript
// workers/price-processor.worker.ts
self.onmessage = (e) => {
  const { ticks, indicators } = e.data;
  // Calculate RSI, MACD, Bollinger Bands, etc.
  const signals = calculateSignals(ticks, indicators);
  self.postMessage({ signals });
};
```

**What to offload to Web Workers:**
- Technical indicator calculations (RSI, MACD, Bollinger Bands)
- P&L aggregation across large position sets
- Historical data processing for backtesting results
- Statistical calculations (Sharpe ratio, drawdown, etc.)

### Virtual Scrolling for Large Data Tables

**Libraries:**
- `@tanstack/react-virtual` — Best for React, handles bidirectional scroll
- `react-window` / `react-virtualized` — More mature but heavier

**Use cases in trading:**
- Trade history (thousands of rows)
- Order book depth (hundreds of price levels)
- Watchlist (hundreds of instruments)
- Signal log (continuous append)

### Memoization Strategy

```typescript
// Prevent re-rendering chart on every tick
const PriceChart = React.memo(({ data }) => {
  // Only re-render when data actually changes
  return <TradingViewChart data={data} />;
}, (prev, next) => {
  // Custom comparison: only update if last candle changed
  return prev.data[prev.data.length - 1] === next.data[next.data.length - 1];
});

// Memoize expensive calculations
const pips = useMemo(() => calculatePipValue(pair, lotSize, accountCurrency), [pair, lotSize]);
```

### Performance Budget

| Metric | Target | Why |
|--------|--------|-----|
| First Contentful Paint | < 1.5s | Trader needs to see dashboard fast |
| Largest Contentful Paint | < 2.5s | Charts should render quickly |
| Total Blocking Time | < 200ms | UI must stay responsive during price updates |
| Cumulative Layout Shift | < 0.1 | No jumping — traders click where they expect |
| Time to Interactive | < 3s | Must be able to trade within 3 seconds |
| Bundle size (initial) | < 200 KB gzipped | Fast load on mobile networks |

---

## 6. Authentication & Security

### Authentication Flow

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│   Browser    │────▶│  Next.js API  │────▶│   Auth Server│
│              │◀────│  Route (BFF)  │◀────│   (JWT)      │
└──────────────┘     └───────────────┘     └──────────────┘
     │                      │
     │  httpOnly cookies    │  OAuth2 flow
     │  (not localStorage)  │  for broker
     │                      │  connections
     ▼                      ▼
  Auto-attach          Broker API
  on every request     (OANDA, IBKR, etc.)
```

### JWT Best Practices

1. **Store tokens in httpOnly cookies** — Never localStorage (XSS vulnerable)
2. **Short-lived access tokens** — 15 min expiry, refresh token in httpOnly cookie
3. **Rotate refresh tokens** — Each refresh issues a new refresh token (token rotation)
4. **Bind tokens to device** — Include device fingerprint in JWT claims
5. **Secure cookie flags:** `HttpOnly; Secure; SameSite=Strict; Path=/`

### OAuth2 for Broker Connections

- Use Authorization Code flow with PKCE (not implicit flow)
- Store broker tokens server-side (Next.js API routes), never expose to browser
- Implement token refresh scheduler on the server
- Support multiple broker connections simultaneously

### WebAuthn / Biometric Authentication

```typescript
// Register biometric credential
const credential = await navigator.credentials.create({
  publicKey: {
    challenge: new Uint8Array(32),
    rp: { name: "Alpha Stack", id: "alphastack.app" },
    user: { id: userId, name: email, displayName: name },
    pubKeyCredParams: [{ type: "public-key", alg: -7 }],
    authenticatorSelection: {
      authenticatorAttachment: "platform",  // Use device biometric
      userVerification: "required"
    }
  }
});
```

**WebAuthn support:**
- ✅ Touch ID / Face ID on macOS/iOS Safari
- ✅ Windows Hello on Edge/Chrome
- ✅ Android biometrics on Chrome
- ✅ Hardware keys (YubiKey) on all browsers

### Content Security Policy (CSP)

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'nonce-{random}';
  style-src 'self' 'unsafe-inline';  # Tailwind needs this
  connect-src 'self' wss://api.alphastack.app https://api.alphastack.app;
  img-src 'self' data: https://*.tradingview.com;
  font-src 'self' https://fonts.gstatic.com;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
```

### CORS Considerations

- Next.js API routes run same-origin — no CORS issues for BFF calls
- Broker API calls go through server-side API routes (no browser CORS)
- WebSocket connections to your own domain: same-origin, no CORS
- If direct broker WebSocket is needed: proxy through your server

### Additional Security Measures

- **Rate limiting** on API routes (prevent order spam)
- **Input validation** with Zod schemas on all order parameters
- **Audit logging** — Every trade action logged with timestamp, IP, device
- **Session management** — Limit concurrent sessions, alert on new device login
- **CSRF protection** — Double-submit cookie pattern for state-changing requests
- **Subresource Integrity (SRI)** — Verify integrity of CDN-loaded scripts

---

## 7. What Trading Web Apps Do Well

### TradingView (Web Architecture)

- **Canvas-based charts** — Custom WebGL/Canvas renderer for millions of data points
- **Modular widget system** — Each chart, watchlist, screener is an independent widget
- **Collaborative layouts** — Save/restore multi-chart layouts
- **Server-side indicator calculations** — Heavy indicators computed server-side
- **WebSocket for real-time** — Price data streamed via WebSocket, reconnection handled gracefully
- **Pine Script** — Client-side custom indicator scripting engine
- **Key takeaway:** Their chart library (Lightweight Charts) is open-source and purpose-built for finance. Use it.

### Binance (Web Trading Interface)

- **Depth chart** — Real-time order book visualization using Canvas
- **One-click trading** — Minimal friction for order execution
- **Dark theme** — Default dark mode, high contrast for price movement
- **WebSocket multiplexing** — Single connection handles multiple streams (trades, depth, klines)
- **Responsive** — Works on mobile browsers without native app
- **Key takeaway:** Their WebSocket stream multiplexing pattern (`/stream?streams=btcusdt@trade/btcusdt@depth`) is worth emulating.

### Bloomberg Terminal (Web Features)

- **Dense information display** — Maximum data density per pixel
- **Keyboard-driven** — Every action has a keyboard shortcut
- **Multi-pane layout** — Resizable, draggable panels
- **Context-sensitive** — Right-click menus, instrument linking between panels
- **Key takeaway:** Information density > visual aesthetics. Traders want data, not whitespace.

### Common Patterns That Work

1. **Persistent connection indicator** — Always visible green/yellow/red dot showing WebSocket status
2. **Sound alerts** — Configurable audio for order fills, stops, signals
3. **Keyboard shortcuts** — Power users demand them. Document and make customizable.
4. **Saved layouts** — Let traders save their preferred panel arrangement
5. **Instrument linking** — Clicking an instrument in watchlist updates all linked panels
6. **Quick trade** — One or two clicks max from signal to order
7. **Real-time everything** — Prices, P&L, margin — all update live, no manual refresh
8. **Dark mode default** — Every serious trading app uses dark mode

---

## 8. Recommended Tech Stack Summary

### Core Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Framework** | Next.js 15 (App Router) | SSR + API routes + largest ecosystem |
| **Language** | TypeScript | Type safety for financial calculations |
| **Styling** | Tailwind CSS + shadcn/ui | Rapid development, dark mode built-in |
| **State** | Zustand + React Query | Client state (UI) + server state (API) |
| **Charts** | TradingView Lightweight Charts | Purpose-built for financial charts, 12KB |
| **Analytics Charts** | ECharts | Heatmaps, treemaps, complex dashboards |
| **Real-time** | WebSocket (primary) + SSE | Bidirectional for trading, one-way for feeds |
| **Auth** | NextAuth.js + JWT (httpOnly cookies) | Secure, server-side token management |
| **Tables** | TanStack Table + TanStack Virtual | Virtual scrolling for large datasets |
| **Testing** | Vitest + Playwright | Unit + E2E testing |

### Infrastructure

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Hosting** | Vercel (or self-hosted) | Edge functions, global CDN |
| **WebSocket Server** | `ws` (Node.js) or dedicated service | Low-latency price streaming |
| **Database** | PostgreSQL + Redis | Persistent state + real-time cache |
| **Monitoring** | Sentry + custom metrics | Error tracking, performance monitoring |

### Development Timeline Estimate

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Phase 1: Foundation** | 2-3 weeks | Auth, layout shell, WebSocket infrastructure |
| **Phase 2: Charts** | 2-3 weeks | Price charts, candlestick, volume, multi-timeframe |
| **Phase 3: Trading** | 2-3 weeks | Order entry, position table, P&L tracking |
| **Phase 4: AI Integration** | 2 weeks | Signal display, confidence gauges, risk panel |
| **Phase 5: Polish** | 2 weeks | PWA, performance optimization, keyboard shortcuts |
| **Total** | 10-13 weeks | MVP trading companion app |

---

## 9. Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| WebSocket connection drops during trade | High — missed stop/limit | Server-side order management; browser is display-only for critical orders |
| Chart performance with 100k+ candles | Medium — UI lag | Canvas rendering, data decimation, viewport culling |
| XSS leading to trade manipulation | Critical — financial loss | CSP, httpOnly cookies, input sanitization, Content Security Policy |
| Mobile browser limitations (PWA push) | Low — missing alerts | In-app notifications + email fallback |
| Browser tab throttling (background tabs) | Medium — stale data | Web Worker for WebSocket handling, Page Visibility API to pause/resume |

---

## 10. Next Steps

1. **Set up Next.js project** with TypeScript, Tailwind, shadcn/ui
2. **Implement WebSocket infrastructure** with reconnection and message buffering
3. **Integrate TradingView Lightweight Charts** with real-time data feed
4. **Build order entry component** with validation and keyboard shortcuts
5. **Add PWA configuration** (manifest, service worker, offline support)
6. **Security hardening** — CSP headers, httpOnly cookies, input validation
7. **Performance profiling** — Lighthouse audit, bundle analysis, Web Vitals tracking
