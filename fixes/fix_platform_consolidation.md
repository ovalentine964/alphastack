# Alpha Stack — Platform Consolidation Fix

> **Author:** Platform Architecture Engineer  
> **Date:** 2026-07-11  
> **Version:** 1.0  
> **Status:** Architecture Fix — Pre-Implementation  
> **Scope:** Unified backend, shared API, authentication, design tokens, feature parity, offline/online hybrid

---

## Table of Contents

1. [Problem Summary](#1-problem-summary)
2. [Unified Backend Architecture](#2-unified-backend-architecture)
3. [Shared API Layer](#3-shared-api-layer)
4. [Unified Authentication Flow](#4-unified-authentication-flow)
5. [Shared Design Tokens](#5-shared-design-tokens)
6. [Feature Parity Matrix](#6-feature-parity-matrix)
7. [Desktop Hybrid: Offline + Online](#7-desktop-hybrid-offline--online)
8. [Implementation Migration Path](#8-implementation-migration-path)

---

## 1. Problem Summary

### Current State: Three Silos

| Platform | Architecture | Data Transport | Auth | State Mgmt |
|----------|-------------|----------------|------|------------|
| **Desktop** (Tauri/Rust) | Local-first, IPC to Rust core | Tauri events (IPC) | OS keychain only, no app lock | Zustand + Tauri events |
| **Web** (Next.js/React) | Client-server, BFF proxy | REST + WebSocket via BFF | NextAuth.js + JWT (httpOnly cookies) | Zustand + TanStack Query |
| **Mobile** (Flutter/Dart) | Client-server, direct backend | WebSocket + REST API | Biometric + JWT (secure storage) | Riverpod + Isar cache |

### Fragmentation Issues

1. **No unified backend** — Desktop assumes local Rust core; Web assumes a BFF proxy layer; Mobile assumes direct backend access. There is no single API surface.
2. **Authentication inconsistency** — Desktop has no app lock mechanism. Web uses httpOnly cookies. Mobile uses biometrics + secure token storage. No cross-device session management.
3. **Design token drift** — Desktop uses CSS custom properties (`:root` variables). Mobile uses Dart constants (`AlphaColors`, `AlphaTypography`). Web uses Tailwind config. Colors match today but will diverge.
4. **No feature parity contract** — Each platform implements features independently. Desktop has keyboard shortcuts; Mobile has voice commands and home widgets; Web has PWA. No defined "must-have" baseline.
5. **Desktop has no cloud path** — If the desktop app is the primary interface, there's no way to access the same trading system from a browser or phone when away from the desktop machine.

---

## 2. Unified Backend Architecture

### 2.1 The Fix: Introduce Alpha Stack Server as the Single Source of Truth

Instead of each platform connecting to the backend differently, we introduce a **unified Alpha Stack Server** that all platforms connect to through a single API surface. The desktop app can optionally run this server locally (embedded mode) or connect to a cloud-hosted instance.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PLATFORM CLIENTS                                  │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   Desktop    │  │     Web      │  │    Mobile    │                   │
│  │  (Tauri)     │  │  (Next.js)   │  │  (Flutter)   │                   │
│  │              │  │              │  │              │                   │
│  │  ┌────────┐  │  │  ┌────────┐  │  │  ┌────────┐  │                   │
│  │  │ UI     │  │  │  │ UI     │  │  │  │ UI     │  │                   │
│  │  │ React  │  │  │  │ React  │  │  │  │ Flutter│  │                   │
│  │  └───┬────┘  │  │  └───┬────┘  │  │  └───┬────┘  │                   │
│  │      │       │  │      │       │  │      │       │                   │
│  │  ┌───▼────┐  │  │  ┌───▼────┐  │  │  ┌───▼────┐  │                   │
│  │  │ Shared │  │  │  │ Shared │  │  │  │ Shared │  │                   │
│  │  │ API    │  │  │  │ API    │  │  │  │ API    │  │                   │
│  │  │ Client │  │  │  │ Client │  │  │  │ Client │  │                   │
│  │  │ (TS)   │  │  │  │ (TS)   │  │  │  │ (Dart) │  │                   │
│  │  └───┬────┘  │  │  └───┬────┘  │  │  └───┬────┘  │                   │
│  └──────┼───────┘  └──────┼───────┘  └──────┼───────┘                   │
│         │                 │                 │                            │
│         │ REST + WS       │ REST + WS       │ REST + WS                  │
│         ▼                 ▼                 ▼                            │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    ALPHA STACK SERVER                             │   │
│  │                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │                 API GATEWAY (Rust — Axum)                    │ │   │
│  │  │                                                              │ │   │
│  │  │  • Unified REST API (versioned: /api/v1/*)                  │ │   │
│  │  │  • WebSocket server (/ws — all real-time data)              │ │   │
│  │  │  • JWT authentication middleware                              │ │   │
│  │  │  • Rate limiting per device/session                          │ │   │
│  │  │  • Request validation (serde)                                │ │   │
│  │  │  • Device-aware response formatting                          │ │   │
│  │  └──────────────────────┬──────────────────────────────────────┘ │   │
│  │                         │                                        │   │
│  │  ┌──────────────────────▼──────────────────────────────────────┐ │   │
│  │  │                 CORE SERVICES                                │ │   │
│  │  │                                                              │ │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │ │   │
│  │  │  │ Market   │ │ Trading  │ │ Agent    │ │ Risk         │  │ │   │
│  │  │  │ Service  │ │ Service  │ │ Orchestr.│ │ Engine       │  │ │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │ │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │ │   │
│  │  │  │ Journal  │ │ Auth     │ │ Notif.   │ │ Settings     │  │ │   │
│  │  │  │ Service  │ │ Service  │ │ Engine   │ │ Service      │  │ │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │                         │                                        │   │
│  │  ┌──────────────────────▼──────────────────────────────────────┐ │   │
│  │  │                 DATA LAYER                                   │ │   │
│  │  │                                                              │ │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │ │   │
│  │  │  │ Redis    │ │TimescaleDB│ │ SQLite  │ │ Sled (Config)│  │ │   │
│  │  │  │ (Hot)    │ │ (History) │ │ (Journal│ │ (Settings)   │  │ │   │
│  │  │  │ Prices,  │ │ Candles, │ │  Trades)│ │              │  │ │   │
│  │  │  │ Signals  │ │ P&L      │ │         │ │              │  │ │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │                         │                                        │   │
│  │  ┌──────────────────────▼──────────────────────────────────────┐ │   │
│  │  │                 BROKER ADAPTERS                              │ │   │
│  │  │                                                              │ │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │ │   │
│  │  │  │ MT5      │ │ cTrader  │ │ OANDA    │                    │ │   │
│  │  │  │ Adapter  │ │ Adapter  │ │ Adapter  │                    │ │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘                    │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Two Deployment Modes

The server supports two deployment modes to satisfy both local-first (desktop) and cloud-first (web/mobile) requirements:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Embedded** | Server runs as a sidecar process alongside the desktop app (localhost only) | Single trader, desktop-primary, no cloud dependency |
| **Cloud** | Server runs on a VPS/cloud instance, accessible over the internet | Multi-device access, web/mobile primary, team use |

```
EMBEDDED MODE (Desktop-Primary):
┌─────────────────────────────────────────────┐
│  Desktop Machine                            │
│                                             │
│  ┌─────────┐  IPC   ┌───────────────────┐  │
│  │ Tauri   │◄──────►│ Alpha Stack Server│  │
│  │ Shell   │        │ (localhost:9222)   │  │
│  └─────────┘        │                   │  │
│                     │  REST + WS API    │  │
│  ┌─────────┐  WS    │  (same endpoints) │  │
│  │ Browser │◄──────►│                   │  │
│  │ (local) │        └───────────────────┘  │
│  └─────────┘                                │
│                                             │
│  Phone connects via LAN or Tailscale       │
└─────────────────────────────────────────────┘

CLOUD MODE (Multi-Device):
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Desktop   │  │    Web      │  │   Mobile    │
│  (Tauri)    │  │  (Browser)  │  │  (Flutter)  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        │ REST + WS (TLS)
                        ▼
              ┌───────────────────┐
              │   Cloud Server    │
              │ (VPS / Docker)    │
              │                   │
              │  Alpha Stack      │
              │  Server + DB      │
              └───────────────────┘
```

### 2.3 Desktop Tauri Integration Change

The desktop Tauri app changes from **running the trading engine directly** to **being a thin shell that embeds and communicates with the Alpha Stack Server**:

```rust
// src-tauri/src/main.rs — NEW: Shell launches server, connects via API

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // 1. Start embedded Alpha Stack Server as sidecar
            let server = Command::new_sidecar("alpha-stack-server")
                .expect("failed to create sidecar command")
                .args(["--config", &config_path()])
                .spawn()
                .expect("failed to spawn server");

            // 2. Wait for server to be ready (health check)
            wait_for_server("http://localhost:9222/health")?;

            // 3. Store server handle for lifecycle management
            app.manage(ServerHandle::new(server));

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // Commands now proxy to the server API
            // instead of calling Rust trading logic directly
            api_proxy::get_positions,
            api_proxy::place_order,
            api_proxy::get_signals,
            api_proxy::get_agent_status,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

**Key change:** The Tauri app no longer contains trading logic. It's a UI shell that talks to the same API as web and mobile. This eliminates the architecture split.

---

## 3. Shared API Layer

### 3.1 API Design Principles

1. **Single versioned API** — `/api/v1/*` for all platforms
2. **REST for CRUD, WebSocket for real-time** — No platform-specific endpoints
3. **Device-agnostic payloads** — Same JSON structure everywhere; clients adapt to their UI
4. **JWT authentication** — Bearer token in Authorization header (all platforms)
5. **Pagination via cursor** — `?cursor=xxx&limit=50` for all list endpoints

### 3.2 REST API Endpoints

```
BASE URL: https://api.alphastack.local:9222/api/v1

─── AUTHENTICATION ───
POST   /auth/login              # Email + password → JWT pair
POST   /auth/refresh            # Refresh token → new access token
POST   /auth/logout             # Invalidate refresh token
POST   /auth/register           # Create account (self-hosted only)
GET    /auth/sessions           # List active sessions (devices)
DELETE /auth/sessions/:id       # Revoke a specific session

─── MARKET DATA ───
GET    /market/symbols          # List tradeable symbols
GET    /market/quotes/:symbol   # Current quote (REST fallback)
GET    /market/candles/:symbol  # Historical OHLCV
        ?timeframe=H1&from=...&to=...
GET    /market/spread/:symbol   # Current spread

─── TRADING ───
GET    /trading/positions       # Open positions
POST   /trading/positions       # Place new order
         Body: { symbol, direction, type, lots, sl?, tp?, price? }
PUT    /trading/positions/:id   # Modify SL/TP
DELETE /trading/positions/:id   # Close position
GET    /trading/orders          # Pending orders
POST   /trading/orders          # Place pending order
DELETE /trading/orders/:id      # Cancel pending order
POST   /trading/close-all       # Emergency close all

─── SIGNALS ───
GET    /signals                 # Active signals
GET    /signals/:id             # Signal detail
POST   /signals/:id/approve    # Approve pending signal
POST   /signals/:id/reject     # Reject pending signal
GET    /signals/history         # Past signals (paginated)

─── AGENTS ───
GET    /agents                  # All agent statuses
GET    /agents/:id              # Single agent detail
GET    /agents/:id/log          # Agent communication log
GET    /agents/pipeline/:runId  # Pipeline run detail

─── JOURNAL ───
GET    /journal/trades          # Trade history (paginated)
GET    /journal/trades/:id      # Single trade detail with AI notes
POST   /journal/trades/:id/notes # Add manual note
GET    /journal/analytics       # Performance metrics
         ?period=7d|30d|all
GET    /journal/equity-curve    # Equity history for chart

─── SETTINGS ───
GET    /settings                # Get all settings
PATCH  /settings                # Partial update
GET    /settings/strategy       # Strategy config
PUT    /settings/strategy       # Update strategy
GET    /settings/risk           # Risk limits
PUT    /settings/risk           # Update risk limits

─── SYSTEM ───
GET    /system/health           # Server health check
GET    /system/status           # Trading status, connection, uptime
POST   /system/pause            # Pause trading
POST   /system/resume           # Resume trading
GET    /system/version          # Server version info
```

### 3.3 WebSocket Protocol

Single WebSocket connection per client. All real-time data flows through one channel.

```
WS URL: wss://api.alphastack.local:9222/ws?token=<jwt>

─── CLIENT → SERVER (Subscribe/Command) ───

{ "type": "subscribe",   "channels": ["prices", "signals", "trades", "agents"] }
{ "type": "unsubscribe", "channels": ["prices"] }
{ "type": "command",     "action": "close_position", "id": 12345 }
{ "type": "command",     "action": "approve_signal", "signal_id": "sig-abc" }
{ "type": "ping" }

─── SERVER → CLIENT (Events) ───

{ "type": "price",       "data": { "symbol": "EURUSD", "bid": 1.08450, "ask": 1.08470, "ts": 1720712400 } }
{ "type": "signal",      "data": { "id": "sig-abc", "symbol": "EURUSD", "direction": "BUY", "confidence": 0.82, ... } }
{ "type": "trade_opened","data": { "id": 12345, "symbol": "EURUSD", "direction": "BUY", ... } }
{ "type": "trade_closed","data": { "id": 12345, "pnl": 0.23, "reason": "tp_hit" } }
{ "type": "trade_updated","data": { "id": 12345, "sl": 1.08300, ... } }
{ "type": "agent_status","data": { "id": "smc-agent", "status": "analyzing", ... } }
{ "type": "risk_alert",  "data": { "level": "warning", "message": "Drawdown at 3.2%" } }
{ "type": "system_status","data": { "trading_active": true, "uptime": 51600 } }
{ "type": "pong" }
```

### 3.4 Shared TypeScript API Client

A single `@alphastack/api-client` package used by both Desktop (Tauri) and Web (Next.js):

```typescript
// packages/api-client/src/index.ts

export class AlphaStackClient {
  private baseUrl: string;
  private wsUrl: string;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private ws: WebSocket | null = null;
  private eventHandlers = new Map<string, Set<(data: any) => void>>();

  constructor(config: { baseUrl: string; wsUrl: string }) {
    this.baseUrl = config.baseUrl;
    this.wsUrl = config.wsUrl;
  }

  // ── Auth ──

  async login(email: string, password: string): Promise<AuthTokens> {
    const res = await this.post('/auth/login', { email, password });
    this.accessToken = res.accessToken;
    this.refreshToken = res.refreshToken;
    return res;
  }

  // ── Market ──

  async getCandles(symbol: string, timeframe: string, from?: number, to?: number) {
    return this.get(`/market/candles/${symbol}`, { timeframe, from, to });
  }

  // ── Trading ──

  async getPositions(): Promise<Position[]> {
    return this.get('/trading/positions');
  }

  async placeOrder(order: PlaceOrderRequest): Promise<OrderResult> {
    return this.post('/trading/positions', order);
  }

  async closePosition(id: number): Promise<void> {
    return this.delete(`/trading/positions/${id}`);
  }

  async closeAllPositions(): Promise<void> {
    return this.post('/trading/close-all', {});
  }

  // ── Signals ──

  async getActiveSignals(): Promise<Signal[]> {
    return this.get('/signals');
  }

  async approveSignal(id: string): Promise<void> {
    return this.post(`/signals/${id}/approve`, {});
  }

  // ── Agents ──

  async getAgentStatus(): Promise<AgentStatus[]> {
    return this.get('/agents');
  }

  // ── Settings ──

  async getSettings(): Promise<Settings> {
    return this.get('/settings');
  }

  async updateSettings(patch: Partial<Settings>): Promise<Settings> {
    return this.patch('/settings', patch);
  }

  // ── WebSocket ──

  connectWebSocket(token: string): void {
    this.ws = new WebSocket(`${this.wsUrl}?token=${token}`);
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      const handlers = this.eventHandlers.get(msg.type);
      handlers?.forEach(h => h(msg.data));
    };
    this.ws.onclose = () => this.scheduleReconnect();
  }

  subscribe(channels: string[]): void {
    this.ws?.send(JSON.stringify({ type: 'subscribe', channels }));
  }

  on(event: string, handler: (data: any) => void): () => void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set());
    }
    this.eventHandlers.get(event)!.add(handler);
    return () => this.eventHandlers.get(event)?.delete(handler);
  }

  // ── HTTP helpers ──

  private async get(path: string, params?: Record<string, any>) {
    const url = new URL(`${this.baseUrl}${path}`);
    if (params) Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) url.searchParams.set(k, String(v));
    });
    const res = await fetch(url.toString(), {
      headers: this.authHeaders(),
    });
    return this.handleResponse(res);
  }

  private async post(path: string, body: any) {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { ...this.authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return this.handleResponse(res);
  }

  private authHeaders(): Record<string, string> {
    return this.accessToken
      ? { Authorization: `Bearer ${this.accessToken}` }
      : {};
  }
}

// ── Shared Type Definitions ──

export interface PlaceOrderRequest {
  symbol: string;
  direction: 'BUY' | 'SELL';
  type: 'MARKET' | 'LIMIT' | 'STOP';
  lots: number;
  sl?: number;
  tp?: number;
  price?: number;  // For limit/stop orders
}

export interface Position {
  id: number;
  symbol: string;
  direction: 'BUY' | 'SELL';
  lots: number;
  entryPrice: number;
  currentPrice: number;
  stopLoss: number;
  takeProfit: number;
  unrealizedPnl: number;
  openTime: string;  // ISO 8601
}

export interface Signal {
  id: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  confidence: number;
  entry: number;
  stopLoss: number;
  takeProfit: number;
  riskPercent: number;
  confluenceScore: number;
  agents: Record<string, { verdict: 'agree' | 'disagree' | 'pending'; score?: number }>;
  status: 'pending' | 'confirmed' | 'executed' | 'expired';
  createdAt: string;
  expiresAt: string;
}

export interface AgentStatus {
  id: string;
  displayName: string;
  status: 'online' | 'analyzing' | 'warning' | 'error' | 'offline';
  lastAction?: string;
  latencyMs?: number;
  metric?: string;
  uptime: number;
}

export interface Settings {
  general: GeneralSettings;
  strategy: StrategySettings;
  risk: RiskSettings;
  notifications: NotificationSettings;
  broker: BrokerSettings;
}

export interface AuthTokens {
  accessToken: string;   // Short-lived: 15 min
  refreshToken: string;  // Long-lived: 7 days
  expiresIn: number;     // Seconds until access token expires
}
```

### 3.5 Dart API Client (Mobile)

Equivalent client for Flutter, same endpoints, same types:

```dart
// lib/data/api/alpha_stack_client.dart

class AlphaStackClient {
  final String baseUrl;
  final String wsUrl;
  String? _accessToken;
  String? _refreshToken;
  WebSocketChannel? _wsChannel;

  AlphaStackClient({required this.baseUrl, required this.wsUrl});

  // ── Auth ──

  Future<AuthTokens> login(String email, String password) async {
    final response = await _post('/auth/login', {
      'email': email,
      'password': password,
    });
    _accessToken = response['accessToken'];
    _refreshToken = response['refreshToken'];
    return AuthTokens.fromJson(response);
  }

  // ── Trading ──

  Future<List<Position>> getPositions() async {
    final data = await _get('/trading/positions');
    return (data as List).map((j) => Position.fromJson(j)).toList();
  }

  Future<OrderResult> placeOrder({
    required String symbol,
    required TradeDirection direction,
    required OrderType type,
    required double lots,
    double? stopLoss,
    double? takeProfit,
    double? price,
  }) async {
    final response = await _post('/trading/positions', {
      'symbol': symbol,
      'direction': direction.name.toUpperCase(),
      'type': type.name.toUpperCase(),
      'lots': lots,
      if (stopLoss != null) 'sl': stopLoss,
      if (takeProfit != null) 'tp': takeProfit,
      if (price != null) 'price': price,
    });
    return OrderResult.fromJson(response);
  }

  // ── WebSocket ──

  Stream<WsMessage> connectWebSocket() {
    _wsChannel = WebSocketChannel.connect(
      Uri.parse('$wsUrl?token=$_accessToken'),
    );
    return _wsChannel!.stream
        .map((data) => WsMessage.fromJson(jsonDecode(data as String)));
  }

  void subscribe(List<String> channels) {
    _wsChannel?.sink.add(jsonEncode({
      'type': 'subscribe',
      'channels': channels,
    }));
  }

  // ── HTTP ──

  Future<dynamic> _get(String path, [Map<String, dynamic>? params]) async {
    final uri = Uri.parse('$baseUrl$path').replace(
      queryParameters: params?.map((k, v) => MapEntry(k, v.toString())),
    );
    final response = await http.get(uri, headers: _authHeaders());
    return _handleResponse(response);
  }

  Future<dynamic> _post(String path, Map<String, dynamic> body) async {
    final response = await http.post(
      Uri.parse('$baseUrl$path'),
      headers: { ..._authHeaders(), 'Content-Type': 'application/json' },
      body: jsonEncode(body),
    );
    return _handleResponse(response);
  }

  Map<String, String> _authHeaders() => {
    if (_accessToken != null) 'Authorization': 'Bearer $_accessToken',
  };
}
```

### 3.6 OpenAPI Specification

All endpoints defined in a single `openapi.yaml` that generates types for both TypeScript and Dart:

```yaml
# openapi.yaml (abbreviated)
openapi: 3.1.0
info:
  title: Alpha Stack API
  version: 1.0.0
servers:
  - url: http://localhost:9222/api/v1
    description: Embedded (local)
  - url: https://api.alphastack.io/api/v1
    description: Cloud

paths:
  /trading/positions:
    get:
      summary: Get open positions
      operationId: getPositions
      security:
        - bearerAuth: []
      responses:
        '200':
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Position'
    post:
      summary: Place new order
      operationId: placeOrder
      security:
        - bearerAuth: []
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PlaceOrderRequest'
      responses:
        '201':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderResult'

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    Position:
      type: object
      required: [id, symbol, direction, lots, entryPrice, currentPrice, stopLoss, takeProfit, unrealizedPnl, openTime]
      properties:
        id:
          type: integer
        symbol:
          type: string
        direction:
          type: string
          enum: [BUY, SELL]
        lots:
          type: number
          format: double
        entryPrice:
          type: number
          format: double
        currentPrice:
          type: number
          format: double
        stopLoss:
          type: number
          format: double
        takeProfit:
          type: number
          format: double
        unrealizedPnl:
          type: number
          format: double
        openTime:
          type: string
          format: date-time
```

Generate clients:
```bash
# TypeScript (for Desktop + Web)
npx openapi-typescript openapi.yaml -o packages/api-client/src/types.ts

# Dart (for Mobile)
dart run openapi_generator generate -i openapi.yaml -o lib/data/api/generated/
```

---

## 4. Unified Authentication Flow

### 4.1 JWT-Based Auth with Device Sessions

```
┌─────────────────────────────────────────────────────────────────────┐
│                   UNIFIED AUTHENTICATION FLOW                        │
│                                                                      │
│  ┌──────────┐                                                        │
│  │  Device   │                                                        │
│  │  (Any)    │                                                        │
│  └────┬─────┘                                                        │
│       │                                                              │
│       ▼                                                              │
│  ┌──────────────────┐     ┌──────────────────────────────┐          │
│  │  1. Login         │────►│  Auth Service                │          │
│  │  email + password │     │                              │          │
│  │  + device_info    │     │  • Validate credentials      │          │
│  └──────────────────┘     │  • Create device session     │          │
│                            │  • Generate JWT pair         │          │
│                            │  • Store refresh token       │          │
│                            └──────────┬───────────────────┘          │
│                                       │                              │
│                                       ▼                              │
│                            ┌──────────────────────┐                  │
│                            │  2. JWT Pair Issued    │                  │
│                            │                       │                  │
│                            │  Access Token: 15min  │                  │
│                            │  Refresh Token: 7 days│                  │
│                            │  Device ID: uuid      │                  │
│                            │  Session ID: uuid     │                  │
│                            └──────────┬────────────┘                  │
│                                       │                              │
│           ┌───────────────────────────┼───────────────────────┐      │
│           │                           │                       │      │
│           ▼                           ▼                       ▼      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │ Desktop (Tauri) │    │ Web (Browser)   │    │ Mobile (Flutter)│  │
│  │                 │    │                 │    │                 │  │
│  │ Store in OS     │    │ Store in        │    │ Store in        │  │
│  │ Keychain via    │    │ httpOnly cookie │    │ flutter_secure_ │  │
│  │ Tauri plugin    │    │ (server-set)    │    │ storage         │  │
│  │                 │    │                 │    │ (Keychain/      │  │
│  │ Optional:       │    │ + Biometric     │    │  Keystore)      │  │
│  │ App Lock PIN    │    │ gate for trades │    │                 │  │
│  └─────────────────┘    └─────────────────┘    │ + Biometric     │  │
│                                                 │ gate for trades │  │
│                                                 └─────────────────┘  │
│                                                                      │
│  ── TOKEN REFRESH (all platforms, same flow) ──                      │
│                                                                      │
│  Client detects 401 → POST /auth/refresh { refreshToken }            │
│  → Server validates → issues new access + refresh token pair         │
│  → Client retries original request                                   │
│                                                                      │
│  ── BIOMETRIC GATE (optional per platform) ──                        │
│                                                                      │
│  For trade execution, a second factor is required:                   │
│  Desktop: App lock PIN (stored in OS keychain, hashed)               │
│  Web: Browser biometric (WebAuthn) or re-enter password              │
│  Mobile: Face ID / Touch ID / Fingerprint                            │
│                                                                      │
│  Biometric does NOT replace JWT — it's an additional local gate      │
│  before the API call is made. The API itself only cares about JWT.   │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 JWT Payload Structure

```json
{
  "sub": "user-uuid-1234",
  "email": "trader@example.com",
  "session_id": "session-uuid-5678",
  "device_id": "device-uuid-abcd",
  "device_type": "desktop",
  "iat": 1720712400,
  "exp": 1720713300,
  "iss": "alphastack"
}
```

### 4.3 Device Session Management

Every login creates a named device session. Users can view and revoke sessions from any device:

```
GET /auth/sessions →
[
  {
    "id": "session-uuid-5678",
    "device_name": "MacBook Pro — Chrome",
    "device_type": "desktop",
    "last_active": "2026-07-11T22:30:00Z",
    "ip_address": "192.168.1.100",
    "current": true
  },
  {
    "id": "session-uuid-9012",
    "device_name": "iPhone 15 Pro",
    "device_type": "mobile",
    "last_active": "2026-07-11T20:15:00Z",
    "ip_address": "10.0.0.50",
    "current": false
  }
]
```

### 4.4 Biometric Gate Implementation Per Platform

| Platform | Biometric Method | Implementation | Fallback |
|----------|-----------------|----------------|----------|
| **Desktop** | App Lock PIN | 4-6 digit PIN, hashed with argon2, stored in OS keychain | Password re-entry |
| **Web** | WebAuthn (if available) | `navigator.credentials.get()` with platform authenticator | Re-enter password |
| **Mobile** | Face ID / Touch ID | `local_auth` Flutter plugin | PIN entry (4-6 digit) |

All biometric gates are **client-side only**. The server doesn't know or care — it only validates JWT. Biometric is an extra UX safety layer to prevent accidental trades.

### 4.5 Cross-Device Settings Sync

Settings are stored server-side and synced to all devices:

```
PATCH /settings { "risk.maxDailyDrawdown": 5.0 }
→ Server updates settings
→ Server pushes settings_updated event via WebSocket to ALL connected sessions
→ Each device pulls fresh settings and updates local cache
```

---

## 5. Shared Design Tokens

### 5.1 Single Source of Truth: `design-tokens.json`

A single JSON file defines all visual tokens. Platform-specific files are generated from it.

```json
{
  "$schema": "https://design-tokens.github.io/community-group/format/",
  "color": {
    "background": {
      "base":     { "value": "#0A0E1A", "type": "color" },
      "surface":  { "value": "#111827", "type": "color" },
      "elevated": { "value": "#1F2937", "type": "color" },
      "hover":    { "value": "#283548", "type": "color" },
      "active":   { "value": "#374151", "type": "color" }
    },
    "text": {
      "primary":   { "value": "#F9FAFB", "type": "color" },
      "secondary": { "value": "#9CA3AF", "type": "color" },
      "muted":     { "value": "#6B7280", "type": "color" },
      "inverse":   { "value": "#111827", "type": "color" }
    },
    "border": {
      "default": { "value": "rgba(255, 255, 255, 0.06)", "type": "color" },
      "strong":  { "value": "rgba(255, 255, 255, 0.12)", "type": "color" },
      "focus":   { "value": "#3B82F6", "type": "color" }
    },
    "semantic": {
      "profit":      { "value": "#10B981", "type": "color" },
      "loss":        { "value": "#EF4444", "type": "color" },
      "profit-bg":   { "value": "rgba(16, 185, 129, 0.1)", "type": "color" },
      "loss-bg":     { "value": "rgba(239, 68, 68, 0.1)", "type": "color" },
      "warning":     { "value": "#F59E0B", "type": "color" },
      "info":        { "value": "#3B82F6", "type": "color" },
      "critical":    { "value": "#DC2626", "type": "color" }
    },
    "chart": {
      "up":        { "value": "#10B981", "type": "color" },
      "down":      { "value": "#EF4444", "type": "color" },
      "grid":      { "value": "rgba(255, 255, 255, 0.04)", "type": "color" },
      "crosshair": { "value": "#9CA3AF", "type": "color" },
      "sma20":     { "value": "#3B82F6", "type": "color" },
      "sma50":     { "value": "#F59E0B", "type": "color" },
      "sma200":    { "value": "#8B5CF6", "type": "color" },
      "rsi":       { "value": "#06B6D4", "type": "color" }
    },
    "agent": {
      "online":  { "value": "#10B981", "type": "color" },
      "warning": { "value": "#F59E0B", "type": "color" },
      "offline": { "value": "#6B7280", "type": "color" },
      "error":   { "value": "#EF4444", "type": "color" }
    }
  },
  "typography": {
    "fontFamily": {
      "ui":   { "value": "Inter", "type": "fontFamily" },
      "mono": { "value": "JetBrains Mono", "type": "fontFamily" }
    },
    "fontSize": {
      "xs":   { "value": "12px", "type": "dimension" },
      "sm":   { "value": "14px", "type": "dimension" },
      "base": { "value": "16px", "type": "dimension" },
      "lg":   { "value": "20px", "type": "dimension" },
      "xl":   { "value": "24px", "type": "dimension" },
      "2xl":  { "value": "32px", "type": "dimension" }
    },
    "fontWeight": {
      "normal":   { "value": "400", "type": "fontWeight" },
      "medium":   { "value": "500", "type": "fontWeight" },
      "semibold": { "value": "600", "type": "fontWeight" },
      "bold":     { "value": "700", "type": "fontWeight" }
    }
  },
  "spacing": {
    "xs":   { "value": "4px", "type": "dimension" },
    "sm":   { "value": "8px", "type": "dimension" },
    "md":   { "value": "12px", "type": "dimension" },
    "lg":   { "value": "16px", "type": "dimension" },
    "xl":   { "value": "24px", "type": "dimension" },
    "2xl":  { "value": "32px", "type": "dimension" },
    "3xl":  { "value": "48px", "type": "dimension" },
    "4xl":  { "value": "64px", "type": "dimension" }
  },
  "borderRadius": {
    "sm":   { "value": "4px", "type": "dimension" },
    "md":   { "value": "6px", "type": "dimension" },
    "lg":   { "value": "8px", "type": "dimension" },
    "xl":   { "value": "12px", "type": "dimension" },
    "2xl":  { "value": "16px", "type": "dimension" },
    "full": { "value": "9999px", "type": "dimension" }
  },
  "animation": {
    "duration": {
      "fast":   { "value": "150ms", "type": "duration" },
      "normal": { "value": "250ms", "type": "duration" },
      "slow":   { "value": "400ms", "type": "duration" }
    }
  }
}
```

### 5.2 Platform-Specific Generators

A build script generates platform-native token files from the single JSON source:

```javascript
// scripts/generate-tokens.js

import designTokens from './design-tokens.json' assert { type: 'json' };
import { writeFileSync } from 'fs';

// ── Generate CSS Custom Properties (Desktop Web + Web) ──

function generateCSS() {
  let css = ':root {\n';
  function walk(obj, prefix = '') {
    for (const [key, val] of Object.entries(obj)) {
      if (val.value !== undefined) {
        css += `  --${prefix}${key}: ${val.value};\n`;
      } else {
        walk(val, `${prefix}${key}-`);
      }
    }
  }
  walk(designTokens);
  css += '}\n';
  writeFileSync('packages/tokens/tokens.css', css);
}

// ── Generate Tailwind Config Extension (Web) ──

function generateTailwindConfig() {
  const config = {
    colors: {
      'bg-base': designTokens.color.background.base.value,
      'bg-surface': designTokens.color.background.surface.value,
      // ... flatten all tokens
    },
    fontFamily: {
      sans: [designTokens.typography.fontFamily.ui.value],
      mono: [designTokens.typography.fontFamily.mono.value],
    },
  };
  writeFileSync(
    'packages/tokens/tailwind.config.json',
    JSON.stringify(config, null, 2)
  );
}

// ── Generate Dart Constants (Mobile) ──

function generateDart() {
  let dart = '// AUTO-GENERATED from design-tokens.json\n';
  dart += '// Do not edit manually\n\n';
  dart += 'import \'dart:ui\';\n\n';
  dart += 'class AlphaTokens {\n';

  // Colors
  dart += '  // Backgrounds\n';
  dart += `  static const Color bgBase = Color(0xFF${designTokens.color.background.base.value.slice(1)});\n`;
  dart += `  static const Color bgSurface = Color(0xFF${designTokens.color.background.surface.value.slice(1)});\n`;
  // ... all colors

  // Spacing
  dart += '\n  // Spacing\n';
  dart += `  static const double spacingXs = 4;\n`;
  dart += `  static const double spacingSm = 8;\n`;
  // ... all spacing

  dart += '}\n';
  writeFileSync('mobile/lib/theme/alpha_tokens.dart', dart);
}

// ── Generate TypeScript Constants (Desktop + Web) ──

function generateTypeScript() {
  let ts = '// AUTO-GENERATED from design-tokens.json\n';
  ts += 'export const tokens = ';
  ts += JSON.stringify(designTokens, null, 2);
  ts += ' as const;\n';
  writeFileSync('packages/tokens/tokens.ts', ts);
}

generateCSS();
generateTailwindConfig();
generateDart();
generateTypeScript();

console.log('✅ Design tokens generated for all platforms');
```

### 5.3 Light Theme Tokens (Override)

```json
{
  "color": {
    "background": {
      "base":     { "value": "#F8FAFC" },
      "surface":  { "value": "#FFFFFF" },
      "elevated": { "value": "#F1F5F9" },
      "hover":    { "value": "#E2E8F0" },
      "active":   { "value": "#CBD5E1" }
    },
    "text": {
      "primary":   { "value": "#0F172A" },
      "secondary": { "value": "#64748B" },
      "muted":     { "value": "#94A3B8" },
      "inverse":   { "value": "#F9FAFB" }
    },
    "border": {
      "default": { "value": "rgba(0, 0, 0, 0.06)" },
      "strong":  { "value": "rgba(0, 0, 0, 0.12)" },
      "focus":   { "value": "#3B82F6" }
    }
  }
}
```

### 5.4 Token Governance Rule

> **Rule:** No platform may define colors, spacing, typography, or border-radius values outside of `design-tokens.json`. If a new token is needed, it is added to the JSON and regenerated. Pull requests that hardcode visual values outside the token system are rejected.

---

## 6. Feature Parity Matrix

### 6.1 Must-Have (All Platforms)

These features MUST exist on every platform. No exceptions.

| Feature | Desktop | Web | Mobile | Notes |
|---------|---------|-----|--------|-------|
| **Dashboard with live prices** | ✅ | ✅ | ✅ | Core feature |
| **Open positions view** | ✅ | ✅ | ✅ | Must show live P&L |
| **Place market order** | ✅ | ✅ | ✅ | BUY/SELL with SL/TP |
| **Close position** | ✅ | ✅ | ✅ | Individual + close all |
| **Modify SL/TP** | ✅ | ✅ | ✅ | Drag on chart or form |
| **Pending orders** | ✅ | ✅ | ✅ | Limit + Stop |
| **AI signal display** | ✅ | ✅ | ✅ | Confidence, entry, SL/TP |
| **Signal approve/reject** | ✅ | ✅ | ✅ | Interactive |
| **Agent status overview** | ✅ | ✅ | ✅ | Health indicators |
| **Trade history** | ✅ | ✅ | ✅ | Paginated, filterable |
| **Performance metrics** | ✅ | ✅ | ✅ | Win rate, P&L, drawdown |
| **Settings management** | ✅ | ✅ | ✅ | Broker, strategy, risk |
| **Dark mode (default)** | ✅ | ✅ | ✅ | From shared tokens |
| **Push/real-time notifications** | ✅ Native | ✅ Browser | ✅ FCM/APNs | Same event, different delivery |
| **Authentication** | ✅ JWT | ✅ JWT | ✅ JWT | Same flow, different storage |
| **Offline data view** | ✅ Full | ✅ PWA cache | ✅ Isar cache | Read-only when offline |
| **Emergency close all** | ✅ | ✅ | ✅ | Must be instant on all |

### 6.2 Platform-Specific (Nice-to-Have, Not Required on All)

| Feature | Platform | Why |
|---------|----------|-----|
| Keyboard shortcuts / Command palette | Desktop, Web | Power users; not useful on mobile |
| System tray integration | Desktop only | OS-specific; no equivalent on web/mobile |
| Voice commands | Mobile only | Hands-free on mobile; not useful on desktop |
| Home screen widgets | Mobile only | OS-specific; not applicable to others |
| PWA install prompt | Web only | Browser-specific |
| Chart drawing tools (fib, trendlines) | Desktop, Web | Screen size matters; mobile has simplified chart |
| Multi-chart layout (2×2 grid) | Desktop only | Requires large screen |
| Swipe-to-close positions | Mobile only | Touch gesture; not applicable to desktop/web |
| Biometric app lock | Mobile only | Web uses WebAuthn; Desktop uses PIN |
| Retina/HiDPI chart rendering | Desktop, Mobile | Browser handles this via Canvas DPI |
| Low data mode | Mobile only | Desktop/Web assumed to have stable connection |
| Chart replay mode | Desktop, Web | Requires screen space |
| Equity heatmap | Desktop, Web | Requires screen space |

### 6.3 Feature Flag System

Use feature flags to manage per-platform capabilities:

```typescript
// packages/shared/src/features.ts

export const FEATURES = {
  // Must-have (all platforms)
  DASHBOARD: { desktop: true, web: true, mobile: true },
  POSITIONS: { desktop: true, web: true, mobile: true },
  ORDER_ENTRY: { desktop: true, web: true, mobile: true },
  SIGNALS: { desktop: true, web: true, mobile: true },
  AGENTS: { desktop: true, web: true, mobile: true },
  JOURNAL: { desktop: true, web: true, mobile: true },
  SETTINGS: { desktop: true, web: true, mobile: true },

  // Platform-specific
  KEYBOARD_SHORTCUTS: { desktop: true, web: true, mobile: false },
  SYSTEM_TRAY: { desktop: true, web: false, mobile: false },
  VOICE_COMMANDS: { desktop: false, web: false, mobile: true },
  HOME_WIDGETS: { desktop: false, web: false, mobile: true },
  PWA_INSTALL: { desktop: false, web: true, mobile: false },
  DRAWING_TOOLS: { desktop: true, web: true, mobile: false },
  MULTI_CHART: { desktop: true, web: false, mobile: false },
  SWIPE_ACTIONS: { desktop: false, web: false, mobile: true },
  BIOMETRIC_LOCK: { desktop: false, web: false, mobile: true },
  LOW_DATA_MODE: { desktop: false, web: false, mobile: true },
  CHART_REPLAY: { desktop: true, web: true, mobile: false },
  EQUITY_HEATMAP: { desktop: true, web: true, mobile: false },
  COMMAND_PALETTE: { desktop: true, web: true, mobile: false },
} as const;
```

---

## 7. Desktop Hybrid: Offline + Online

### 7.1 The Problem

Desktop users expect the app to work without internet (local-first). But the unified architecture requires a server. How do we reconcile?

### 7.2 Solution: Embedded Server with Offline Graceful Degradation

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DESKTOP HYBRID ARCHITECTURE                       │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Tauri Shell (UI)                          │    │
│  │                                                              │    │
│  │  React + TypeScript + Shared API Client                      │    │
│  │  (same code as Web, just different transport target)         │    │
│  └──────────────────────┬──────────────────────────────────────┘    │
│                         │                                            │
│                         │ API calls                                  │
│                         ▼                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    API Client Router                          │    │
│  │                                                              │    │
│  │  if (embedded_server_healthy) → localhost:9222               │    │
│  │  elif (cloud_server_healthy)  → api.alphastack.io           │    │
│  │  else                         → offline_cache (read-only)    │    │
│  └──────┬──────────────────┬──────────────────┬────────────────┘    │
│         │                  │                  │                      │
│         ▼                  ▼                  ▼                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐      │
│  │   EMBEDDED   │  │    CLOUD     │  │     OFFLINE CACHE     │      │
│  │   SERVER     │  │   SERVER     │  │                       │      │
│  │              │  │              │  │  • Last known prices  │      │
│  │  localhost   │  │  Internet    │  │  • Open positions     │      │
│  │  :9222       │  │  connection  │  │  • Trade history      │      │
│  │              │  │              │  │  • Settings           │      │
│  │  Full API    │  │  Full API    │  │  • Signals (stale)    │      │
│  │  + Broker    │  │  + Broker    │  │                       │      │
│  │  connection  │  │  connection  │  │  NO trading           │      │
│  │              │  │              │  │  NO live prices       │      │
│  └──────────────┘  └──────────────┘  └──────────────────────┘      │
│                                                                      │
│  ── TRANSITION LOGIC ──                                              │
│                                                                      │
│  1. App starts → try embedded server (fast, <100ms)                  │
│  2. If embedded unavailable → try cloud server                       │
│  3. If both unavailable → enter offline mode                         │
│  4. While in offline mode, poll every 30s for server recovery        │
│  5. On recovery → sync delta, resume normal operation                │
│                                                                      │
│  ── EMBEDDED SERVER LIFECYCLE ──                                     │
│                                                                      │
│  • Installed as part of the desktop app package                      │
│  • Started automatically by Tauri on app launch                      │
│  • Runs as a child process (sidecar)                                 │
│  • Stopped when the app exits                                        │
│  • Data stored in ~/.alphastack/server/                              │
│  • SQLite for local data (no Redis/TimescaleDB needed for embedded)  │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.3 Offline Mode Behavior

| Capability | Online (Embedded/Cloud) | Offline |
|-----------|------------------------|---------|
| View dashboard | ✅ Live data | ✅ Last snapshot (stale indicator shown) |
| View positions | ✅ Live P&L | ✅ Last known state (no live P&L) |
| Place orders | ✅ Full | ❌ Disabled, "Offline" message |
| Close positions | ✅ Full | ❌ Disabled |
| View signals | ✅ Live | ✅ Last 24h cached |
| View agents | ✅ Live | ❌ "Agents unavailable offline" |
| View journal | ✅ Full | ✅ Full (local DB) |
| View analytics | ✅ Full | ✅ Full (local DB) |
| Change settings | ✅ Full | ✅ Queued, synced on reconnect |
| Keyboard shortcuts | ✅ Full | ✅ Full (navigation only) |

### 7.4 API Client with Fallback

```typescript
// packages/api-client/src/resilient-client.ts

export class ResilientApiClient {
  private primary: AlphaStackClient;   // Embedded localhost
  private secondary: AlphaStackClient; // Cloud
  private cache: OfflineCache;
  private mode: 'embedded' | 'cloud' | 'offline' = 'offline';

  async initialize(): Promise<void> {
    // Try embedded first
    try {
      await this.primary.healthCheck({ timeout: 2000 });
      this.mode = 'embedded';
      return;
    } catch {}

    // Try cloud
    try {
      await this.secondary.healthCheck({ timeout: 5000 });
      this.mode = 'cloud';
      return;
    } catch {}

    // Offline
    this.mode = 'offline';
  }

  async getPositions(): Promise<Position[]> {
    if (this.mode === 'offline') {
      return this.cache.getPositions();
    }

    try {
      const client = this.mode === 'embedded' ? this.primary : this.secondary;
      const positions = await client.getPositions();
      this.cache.savePositions(positions); // Update cache
      return positions;
    } catch {
      // Server died mid-session → fallback to cache
      this.mode = 'offline';
      return this.cache.getPositions();
    }
  }

  async placeOrder(order: PlaceOrderRequest): Promise<OrderResult> {
    if (this.mode === 'offline') {
      throw new Error('Cannot place orders while offline');
    }

    const client = this.mode === 'embedded' ? this.primary : this.secondary;
    return client.placeOrder(order);
  }

  // Background health check (runs every 30s when offline)
  startRecoveryPolling(): void {
    setInterval(async () => {
      if (this.mode !== 'offline') return;
      await this.initialize();
      if (this.mode !== 'offline') {
        this.emit('reconnected', { mode: this.mode });
      }
    }, 30_000);
  }
}
```

### 7.5 Sync on Reconnect

When transitioning from offline to online:

```typescript
async onReconnect(): Promise<void> {
  // 1. Pull latest server state
  const [serverPositions, serverSettings] = await Promise.all([
    this.client.getPositions(),
    this.client.getSettings(),
  ]);

  // 2. Reconcile positions (server is authoritative for financial data)
  this.cache.savePositions(serverPositions);

  // 3. Push any queued settings changes
  const pendingSettings = this.cache.getPendingSettingsChanges();
  if (pendingSettings.length > 0) {
    for (const change of pendingSettings) {
      await this.client.updateSettings(change);
    }
    this.cache.clearPendingChanges();
  }

  // 4. Refresh stale data
  await Promise.all([
    this.cache.refreshSignals(),
    this.cache.refreshTradeHistory(),
  ]);

  // 5. Reconnect WebSocket
  this.client.connectWebSocket(this.auth.getToken());
}
```

---

## 8. Implementation Migration Path

### Phase 0: Foundation (Weeks 1–2)

- [ ] Create `design-tokens.json` and build script to generate CSS, Tailwind, Dart, TypeScript
- [ ] Create `openapi.yaml` specification for the unified API
- [ ] Scaffold `@alphastack/api-client` TypeScript package
- [ ] Scaffold `alpha_stack_client` Dart package
- [ ] Set up monorepo structure (Turborepo or similar)

### Phase 1: Unified Server (Weeks 3–6)

- [ ] Build Alpha Stack Server (Rust/Axum) with all REST endpoints
- [ ] Implement WebSocket server with subscription model
- [ ] Implement JWT authentication service
- [ ] Implement device session management
- [ ] Implement broker adapter interface (MT5 first)
- [ ] SQLite storage layer for embedded mode
- [ ] Redis + TimescaleDB storage layer for cloud mode
- [ ] Health check and graceful degradation endpoints

### Phase 2: Desktop Migration (Weeks 7–10)

- [ ] Refactor Tauri app to use API client instead of direct IPC
- [ ] Implement embedded server sidecar launch
- [ ] Implement offline cache (SQLite)
- [ ] Implement fallback routing (embedded → cloud → offline)
- [ ] Add app lock PIN feature
- [ ] Verify all existing desktop features work through the new API

### Phase 3: Web Alignment (Weeks 11–13)

- [ ] Remove Next.js BFF layer — connect directly to Alpha Stack Server
- [ ] Replace NextAuth.js with JWT-based auth using shared API client
- [ ] Migrate Zustand stores to use shared API client
- [ ] Implement PWA service worker for offline caching
- [ ] Add WebAuthn biometric gate for trade execution

### Phase 4: Mobile Alignment (Weeks 14–16)

- [ ] Replace custom WebSocket client with shared Dart API client
- [ ] Replace custom REST endpoints with shared API client
- [ ] Migrate Riverpod providers to use shared client
- [ ] Update Isar cache to match server data model
- [ ] Verify biometric flow works with new auth

### Phase 5: Cross-Platform Testing (Weeks 17–18)

- [ ] End-to-end testing: same trade visible on all three platforms
- [ ] Device session management testing (login/revoke from each device)
- [ ] Offline/online transition testing (desktop)
- [ ] Settings sync testing (change on one device, verify on others)
- [ ] Load testing (multiple WebSocket clients, price burst scenarios)

### Phase 6: Design Token Enforcement (Week 19)

- [ ] Lint rule: reject hardcoded colors/spacing outside tokens
- [ ] Visual regression tests: compare platform screenshots against shared Figma
- [ ] Documentation: contribution guide for adding new tokens
- [ ] CI check: `generate-tokens.js` must produce no diff (tokens are committed)

---

## Appendix A: Migration Impact Summary

| Component | Before | After | Impact |
|-----------|--------|-------|--------|
| Desktop trading logic | Rust in Tauri process | Rust in Alpha Stack Server (sidecar) | Medium — refactor IPC to HTTP/WS |
| Desktop auth | OS keychain only | JWT + OS keychain + optional PIN | Low — additive |
| Web BFF layer | Next.js API routes proxying | Direct to Alpha Stack Server | Medium — remove BFF, add auth |
| Web auth | NextAuth.js | JWT via shared API client | Medium — replace auth library |
| Mobile WebSocket | Custom client | Shared Dart API client | Low — similar pattern |
| Mobile REST | Custom client | Shared Dart API client | Low — similar pattern |
| Design tokens | 3 separate definitions | 1 JSON + generators | Low — build script |
| Settings storage | Per-platform | Server-side, synced | Medium — migration needed |

## Appendix B: Dependency Graph (Monorepo)

```
alphastack/
├── packages/
│   ├── api-client/          # TypeScript API client (Desktop + Web)
│   │   └── src/
│   │       ├── index.ts
│   │       ├── types.ts     # Generated from OpenAPI
│   │       ├── client.ts
│   │       └── ws-client.ts
│   │
│   ├── tokens/              # Design tokens (all platforms)
│   │   ├── design-tokens.json
│   │   ├── tokens.css       # Generated
│   │   ├── tokens.ts        # Generated
│   │   └── tailwind.config.json  # Generated
│   │
│   └── shared/              # Shared constants, feature flags
│       └── src/
│           ├── features.ts
│           ├── constants.ts
│           └── types.ts
│
├── server/                  # Alpha Stack Server (Rust)
│   ├── src/
│   │   ├── main.rs
│   │   ├── api/             # REST handlers
│   │   ├── ws/              # WebSocket handlers
│   │   ├── auth/            # JWT + session management
│   │   ├── services/        # Core business logic
│   │   ├── broker/          # Broker adapters
│   │   └── storage/         # SQLite + Redis + TimescaleDB
│   └── Cargo.toml
│
├── desktop/                 # Tauri app (thin shell)
│   ├── src/                 # React frontend (uses api-client)
│   └── src-tauri/           # Rust shell (sidecar launcher)
│
├── web/                     # Next.js app
│   ├── app/                 # Pages (uses api-client)
│   └── components/
│
├── mobile/                  # Flutter app
│   ├── lib/
│   │   ├── data/api/        # Dart API client
│   │   └── theme/           # Generated from tokens
│   └── pubspec.yaml
│
├── scripts/
│   └── generate-tokens.js   # Token generator
│
└── openapi.yaml             # API specification
```

## Appendix C: Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Single server vs per-platform backends | Single server | Eliminates drift, single source of truth, one codebase to secure |
| Embedded server for desktop | Yes | Preserves offline-first UX, no cloud dependency required |
| JWT over session cookies | JWT | Works across all platforms (cookies are browser-specific) |
| Shared API client packages | Yes | Single source of types, no manual sync between platforms |
| OpenAPI code generation | Yes | Types always match the server; no hand-maintained DTOs |
| Design tokens from JSON | Yes | Single source prevents visual drift; CI enforces consistency |
| Feature flags for parity | Yes | Explicit contract for what each platform must implement |
| Server-authoritative for financial data | Yes | Client caches are read-only; no client-side trade state mutations |
| Biometric as client-side gate only | Yes | Server doesn't need to know about biometrics; simplifies API |

---

*This fix document consolidates Alpha Stack's three platform architectures into a unified system. The key insight: a single server with a single API, consumed by platform-specific shells that share types, tokens, and behavioral contracts. The desktop preserves its local-first feel through an embedded server, while web and mobile get the same data through the same endpoints.*
