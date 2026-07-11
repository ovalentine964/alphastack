# Alpha Stack — Desktop Application Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Target:** Cross-Platform Desktop (Linux / Windows / macOS)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Framework Selection](#2-framework-selection)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Backend / Trading Engine](#5-backend--trading-engine)
6. [IPC & Real-Time Communication](#6-ipc--real-time-communication)
7. [MT5 Integration Strategy](#7-mt5-integration-strategy)
8. [Cross-Platform Build & Distribution](#8-cross-platform-build--distribution)
9. [Web Companion App](#9-web-companion-app)
10. [Mobile Companion App](#10-mobile-companion-app)
11. [Installation & Onboarding](#11-installation--onboarding)
12. [Security Architecture](#12-security-architecture)
13. [File & Directory Layout](#13-file--directory-layout)
14. [Technology Stack Summary](#14-technology-stack-summary)
15. [Development Roadmap](#15-development-roadmap)

---

## 1. Executive Summary

Alpha Stack is an institutional-grade AI forex/crypto trading system targeting a $7 starting capital on FXPesa via MetaTrader 5. The desktop application must:

- Run natively on **Linux (Pop!_OS 24.04)**, **Windows 10/11**, and **macOS 12+**
- Host the **trading engine, AI models, and data pipeline** locally (no cloud dependency for core trading)
- Provide a **real-time dashboard** with live charts, trade management, and system monitoring
- Operate **in the background** via system tray when minimized
- Be installable with a **single command** on any platform
- Accompany with a **web companion** (remote monitoring) and **mobile companion** (alerts)

---

## 2. Framework Selection

### 2.1 Candidate Evaluation

| Criterion | Electron | Tauri 2.x | Flutter Desktop | PyQt/PySide | Qt (C++) |
|---|---|---|---|---|---|
| **Bundle Size** | ~150–200 MB | ~5–15 MB | ~25–40 MB | ~50–80 MB | ~30–60 MB |
| **Memory (idle)** | ~200–400 MB | ~30–80 MB | ~80–150 MB | ~80–150 MB | ~40–100 MB |
| **Language** | JS/TS | Rust + JS/TS | Dart | Python + JS | C++ |
| **Security** | Moderate (Node in renderer) | High (Rust sandbox) | Good | Moderate | Good |
| **System Tray** | ✅ (electron-tray) | ✅ (native plugin) | ✅ (limited) | ✅ | ✅ |
| **Auto-Update** | ✅ (electron-updater) | ✅ (tauri-updater) | ✅ | Manual | Manual |
| **Web Tech Reuse** | ✅ Full | ✅ Full | ❌ (Dart) | ✅ (QWebEngine) | ✅ (QWebEngine) |
| **Cross-Platform** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Python Integration** | Via subprocess/IPC | Via subprocess/IPC | Via FFI/subprocess | Native | Via pybind11 |
| **Learning Curve** | Low (web devs) | Medium (Rust) | Medium | Medium (Python) | High (C++) |
| **Community/Ecosystem** | Massive | Growing fast | Large (mobile) | Large | Large |
| **Startup Time** | Slow (2–5s) | Fast (<1s) | Fast (<1s) | Moderate | Moderate |

### 2.2 Recommendation: **Tauri 2.x**

**Primary choice: Tauri 2.x** (Rust backend + Web frontend)

**Rationale for Alpha Stack specifically:**

1. **Trading apps are resource-sensitive.** Electron's 200+ MB RAM baseline is unacceptable when the app runs 24/7 alongside MT5 (which itself runs under Wine on Linux). Tauri uses 30–80 MB — a 3–5x improvement.

2. **Security matters for financial software.** Tauri's Rust-based backend with explicit capability-based permissions is far more secure than Electron's Node.js-in-renderer model. Broker credentials and API keys are handled in Rust, not exposed to the web layer.

3. **System tray is critical.** Alpha Stack must run in the background. Tauri 2.x has first-class system tray support with native APIs on all three platforms.

4. **Web frontend = maximum flexibility.** The dashboard uses the same React/Vue/Svelte skills as the web companion. Chart libraries (Lightweight Charts, TradingView, D3) work identically.

5. **Rust backend = performance for the trading engine.** The core trading loop, signal processing, and WebSocket handling can run in Rust at native speed, while AI model inference calls out to Python.

6. **Auto-update built in.** Tauri's updater supports all platforms with signature verification.

7. **~5 MB installer.** Critical for the "single command install" requirement.

### 2.3 Fallback Option

If Rust proves too difficult for rapid iteration: **Electron + Python backend** (the VS Code model). The frontend is identical; only the backend wrapper changes. Architecture below is designed to be framework-agnostic at the backend layer.

---

## 3. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Tauri Desktop Shell                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Frontend (WebView)                        │   │
│  │  React/TS + Lightweight Charts + TailwindCSS + shadcn/ui    │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │   │
│  │  │Dashboard │ │Trade Mgr │ │ Analytics│ │  Settings    │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │   │
│  └───────────────────────┬──────────────────────────────────────┘   │
│                          │ Tauri IPC (invoke / events)              │
│  ┌───────────────────────┴──────────────────────────────────────┐   │
│  │                    Rust Backend (Core)                       │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │   │
│  │  │Trade     │ │Data      │ │System    │ │IPC/Event     │   │   │
│  │  │Engine    │ │Pipeline  │ │Tray Mgr  │ │Bridge        │   │   │
│  │  └────┬─────┘ └────┬─────┘ └──────────┘ └──────────────┘   │   │
│  │       │             │                                        │   │
│  │  ┌────┴─────────────┴──────────────────────────────────┐     │   │
│  │  │         WebSocket Server (localhost:9222)            │     │   │
│  │  └────┬─────────────┬──────────────────────────────────┘     │   │
│  └───────┼─────────────┼────────────────────────────────────────┘   │
│          │             │                                            │
│  ┌───────┴──────┐ ┌───┴──────────────────────────────────────┐     │
│  │ Python Sidecar│ │         Optional Services                │     │
│  │ ┌───────────┐ │ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ │     │
│  │ │AI Models  │ │ │ │Web Server│ │MT5 Bridge│ │Alert Svc │ │     │
│  │ │(PyTorch)  │ │ │ │(FastAPI) │ │(WS/MQTT) │ │(Push/WS) │ │     │
│  │ └───────────┘ │ │ └──────────┘ └──────────┘ └──────────┘ │     │
│  │ ┌───────────┐ │ └──────────────────────────────────────────┘     │
│  │ │MT5 Python │ │                                                  │
│  │ │Connector  │ │                                                  │
│  │ └───────────┘ │                                                  │
│  └───────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────┘
          │                         │
          ▼                         ▼
┌──────────────────┐    ┌───────────────────────┐
│   MetaTrader 5   │    │   External Services   │
│ (Wine/Linux or   │    │ ┌────────┐ ┌────────┐ │
│  native Windows) │    │ │FXPesa  │ │DataFeed│ │
│  ┌────────────┐  │    │ │Broker  │ │APIs    │ │
│  │MQL5 EA     │  │    │ └────────┘ └────────┘ │
│  │(Bridge EA) │  │    └───────────────────────┘
│  └────────────┘  │
└──────────────────┘
```

### 3.1 Layer Responsibilities

| Layer | Technology | Responsibility |
|---|---|---|
| **Shell** | Tauri 2.x (Rust) | Window management, system tray, auto-update, native APIs, process lifecycle |
| **Frontend** | React 19 + TypeScript + Vite | Dashboard UI, charts, trade management, settings, real-time data display |
| **Core Engine** | Rust (compiled into Tauri) | Trading signal processing, risk calculations, order management logic, WebSocket server |
| **Python Sidecar** | Python 3.11+ (embedded/managed) | AI model inference, MT5 API calls, data preprocessing, strategy backtesting |
| **Web Server** | FastAPI (Python) | REST API + WebSocket for web/mobile companions, optional remote access |
| **MT5 Bridge** | MQL5 EA + Python `MetaTrader5` lib | Order execution, position management, tick data streaming |
| **Data Layer** | SQLite (local) + optional PostgreSQL | Trade history, settings, logs, AI training data |

---

## 4. Frontend Architecture

### 4.1 Technology Stack

```
React 19 + TypeScript 5.x
├── Vite 6.x (build tool)
├── TailwindCSS 4.x (styling)
├── shadcn/ui (component library)
├── Zustand (state management — lightweight, perfect for trading data)
├── Lightweight Charts (TradingView open-source charting)
├── D3.js (custom analytics visualizations)
├── TanStack Query (API data fetching for web companion)
└── Socket.IO Client (real-time data from backend)
```

### 4.2 Page Structure

```
src/
├── pages/
│   ├── Dashboard/          # Main trading view
│   │   ├── PriceChart      # Live candlestick chart (Lightweight Charts)
│   │   ├── SignalPanel      # Active signals & AI recommendations
│   │   ├── PositionSummary  # Open positions, P&L
│   │   └── MarketOverview   # Multi-pair watchlist
│   ├── Trades/             # Trade management
│   │   ├── ActiveTrades     # Open positions with live P&L
│   │   ├── TradeHistory     # Closed trades with analytics
│   │   ├── PendingOrders    # Limit/stop orders
│   │   └── TradeJournal     # AI-generated trade notes
│   ├── Analytics/          # Performance analytics
│   │   ├── EquityCurve      # Balance over time
│   │   ├── WinRate          # Strategy performance breakdown
│   │   ├── RiskMetrics      # Max drawdown, Sharpe, etc.
│   │   └── AIInsights       # Model confidence, feature importance
│   ├── Strategy/           # Strategy configuration
│   │   ├── StrategyBuilder  # Visual strategy parameter tuning
│   │   ├── Backtester       # Historical backtest results
│   │   └── ModelStatus      # AI model training status
│   ├── Settings/           # App configuration
│   │   ├── BrokerConfig     # MT5 connection settings
│   │   ├── RiskManagement   # Position sizing, max drawdown
│   │   ├── Notifications    # Alert preferences
│   │   └── General          # Theme, language, updates
│   └── Logs/               # System logs & debug
├── components/
│   ├── charts/             # Chart components
│   ├── trading/            # Trade-specific components
│   ├── layout/             # App shell, sidebar, header
│   └── shared/             # Reusable UI components
├── stores/                 # Zustand stores
│   ├── marketStore          # Live price data
│   ├── tradeStore           # Positions & orders
│   ├── signalStore          # AI signals
│   └── settingsStore        # App configuration
├── hooks/                  # Custom React hooks
│   ├── useWebSocket         # Real-time data subscription
│   ├── useTauriIPC          # Tauri command invocation
│   └── useTrading           # Trading operations
└── lib/                    # Utilities
    ├── tauri-bridge.ts      # Tauri IPC wrapper
    ├── ws-client.ts         # WebSocket client
    └── formatters.ts        # Price, date, P&L formatters
```

### 4.3 Real-Time Data Flow

```
Rust Core Engine
    │
    ├── Tauri Events (for UI updates)
    │   └── emit("price-update", { pair: "EURUSD", bid: 1.0845, ask: 1.0847 })
    │   └── emit("signal-new", { pair: "GBPUSD", direction: "BUY", confidence: 0.82 })
    │   └── emit("trade-opened", { ticket: 12345, pair: "EURUSD", ... })
    │   └── emit("trade-closed", { ticket: 12345, pnl: 0.23 })
    │
    └── WebSocket (for web/mobile companions)
        └── ws://localhost:9222/stream
            ├── Channel: prices
            ├── Channel: signals
            ├── Channel: trades
            └── Channel: system
```

### 4.4 System Tray Behavior

```rust
// Tauri system tray configuration
TrayIconBuilder::new()
    .icon(app.default_window_icon().cloned().unwrap())
    .menu(&tray_menu)  // Show, Pause Trading, Quit
    .on_tray_icon_event(|tray, event| {
        match event {
            TrayIconEvent::Click { .. } => {
                // Toggle main window visibility
            }
            _ => {}
        }
    })
    .tooltip("Alpha Stack — Trading Active")
```

**Tray menu items:**
- **Show Dashboard** — Restore main window
- **Trading: Active/Paused** — Toggle trading on/off
- **Quick Stats** — Hover tooltip shows balance, daily P&L, open positions
- **Check for Updates**
- **Quit**

**Background behavior:**
- Closing the window hides to tray (does NOT quit)
- Trading engine continues running in background
- System notifications for trade events (native OS notifications)

---

## 5. Backend / Trading Engine

### 5.1 Rust Core (compiled into Tauri)

```
src-tauri/src/
├── main.rs                 # Tauri app entry
├── lib.rs                  # Module declarations
├── commands/               # Tauri IPC command handlers
│   ├── trading.rs           # place_order, close_position, modify_sl
│   ├── market.rs            # get_prices, subscribe_pairs
│   ├── strategy.rs          # get_signals, update_params
│   ├── system.rs            # get_status, get_logs
│   └── settings.rs          # get/set configuration
├── engine/
│   ├── mod.rs
│   ├── signal_processor.rs  # Signal aggregation & confirmation
│   ├── risk_manager.rs      # Position sizing, max drawdown, correlation
│   ├── order_manager.rs     # Order lifecycle management
│   └── scheduler.rs         # Time-based task scheduling
├── data/
│   ├── market_data.rs       # Price data management
│   ├── candle_builder.rs    # Tick-to-candle aggregation
│   └── indicators.rs        # RSI, S/R levels, SMC structures
├── bridge/
│   ├── mt5_client.rs        # MT5 WebSocket/TCP client
│   ├── python_bridge.rs     # Python sidecar management
│   └── ws_server.rs         # WebSocket server for companions
├── tray/
│   └── system_tray.rs       # System tray management
├── updater/
│   └── auto_update.rs       # Tauri auto-update integration
└── config/
    └── settings.rs          # Configuration management (TOML)
```

### 5.2 Python Sidecar

Python runs as a **managed sidecar process** — Tauri spawns it, monitors health, restarts on crash.

```
alpha-stack-python/
├── main.py                 # Entry point — FastAPI + signal handlers
├── ai/
│   ├── models/
│   │   ├── macro_model.py   # Macro sentiment analysis
│   │   ├── smc_detector.py  # Smart Money Concepts pattern detection
│   │   ├── regime_model.py  # Market regime classification
│   │   └── ensemble.py      # Model ensemble / voting
│   ├── training/
│   │   ├── trainer.py       # Model training pipeline
│   │   └── data_loader.py   # Training data preparation
│   └── inference.py         # Real-time inference server
├── mt5/
│   ├── connector.py         # MetaTrader5 Python API wrapper
│   ├── data_feed.py         # Tick/bar data streaming
│   └── order_executor.py    # Order placement via MT5
├── data/
│   ├── preprocessor.py      # Feature engineering
│   └── indicators.py        # Technical indicators (ta-lib wrapper)
├── api/
│   ├── routes.py            # FastAPI REST endpoints
│   └── websocket.py         # WebSocket handlers for companions
└── config.py                # Python-side configuration
```

### 5.3 Python Sidecar Lifecycle

```
Tauri App Start
    │
    ├── 1. Check Python environment
    │   ├── Bundled Python? → Use it
    │   ├── System Python 3.11+? → Use it
    │   └── Neither? → Prompt install or download embedded
    │
    ├── 2. Install/verify dependencies
    │   └── pip install -r requirements.txt (first run only)
    │
    ├── 3. Spawn Python sidecar
    │   └── Command: python main.py --port 9223 --ipc-mode stdio
    │
    ├── 4. Health check loop (every 30s)
    │   ├── HTTP GET localhost:9223/health
    │   ├── Healthy? → Continue
    │   └── Unhealthy? → Restart (max 3 retries)
    │
    └── 5. IPC via JSON-RPC over stdio
        ├── Rust → Python: {"method": "ai.predict", "params": {...}}
        └── Python → Rust: {"result": {"signal": "BUY", "confidence": 0.85}}
```

---

## 6. IPC & Real-Time Communication

### 6.1 Communication Architecture

```
┌─────────────┐     Tauri IPC (invoke/events)     ┌─────────────┐
│   Frontend   │ ◄──────────────────────────────► │  Rust Core   │
│   (WebView)  │                                   │  (Tauri)     │
└─────────────┘                                   └──────┬──────┘
                                                         │
                                              JSON-RPC over stdio
                                                         │
                                                  ┌──────┴──────┐
                                                  │   Python     │
                                                  │   Sidecar    │
                                                  └──────┬──────┘
                                                         │
                                              WebSocket / TCP
                                                         │
                                                  ┌──────┴──────┐
                                                  │   MetaTrader │
                                                  │      5       │
                                                  └─────────────┘
```

### 6.2 Tauri Commands (Frontend → Rust)

```typescript
// Frontend invokes Rust commands
import { invoke } from '@tauri-apps/api/core';

// Get current prices
const prices = await invoke<PriceData>('get_prices', { pairs: ['EURUSD', 'GBPUSD'] });

// Place a trade
const result = await invoke<TradeResult>('place_order', {
  pair: 'EURUSD',
  direction: 'BUY',
  lotSize: 0.01,
  stopLoss: 1.0820,
  takeProfit: 1.0900,
});

// Get AI signals
const signals = await invoke<Signal[]>('get_active_signals');
```

### 6.3 Tauri Events (Rust → Frontend)

```typescript
// Frontend subscribes to events
import { listen } from '@tauri-apps/api/event';

const unlisten = await listen<PriceUpdate>('price-update', (event) => {
  marketStore.updatePrice(event.payload);
});

const unlistenSignals = await listen<Signal>('signal-new', (event) => {
  signalStore.addSignal(event.payload);
  // Show native notification for high-confidence signals
  if (event.payload.confidence > 0.8) {
    sendNotification('Alpha Stack Signal', `${event.payload.pair} ${event.payload.direction}`);
  }
});
```

### 6.4 WebSocket Server (for Web/Mobile Companions)

```rust
// Rust WebSocket server on port 9222
// Same data that goes to Tauri events, but over network

// Channels:
// /prices     — Live price ticks
// /signals    — AI trading signals  
// /trades     — Trade open/close/modify events
// /system     — System status, health, logs

// Auth: API key in handshake header (configurable)
```

---

## 7. MT5 Integration Strategy

### 7.1 The Linux Challenge

MetaTrader 5 is a Windows application. On Linux (Pop!_OS 24.04), there are three approaches:

#### Option A: Wine/Bottles (Recommended for $7 Account)

```
┌────────────────────────────────────┐
│         Pop!_OS 24.04              │
│  ┌──────────────────────────────┐  │
│  │     Bottles (Wine prefix)    │  │
│  │  ┌────────────────────────┐  │  │
│  │  │   MetaTrader 5         │  │  │
│  │  │   ┌─────────────────┐  │  │  │
│  │  │   │  FXPesa EA      │  │  │  │
│  │  │   │  (Bridge EA)    │  │  │  │
│  │  │   └────────┬────────┘  │  │  │
│  │  └────────────┼───────────┘  │  │
│  └───────────────┼──────────────┘  │
│                  │                  │
│           Named Pipe / TCP          │
│                  │                  │
│  ┌───────────────┴──────────────┐  │
│  │     Alpha Stack Backend      │  │
│  │     (Python MT5 connector)   │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
```

**Pros:** Free, works offline, full MT5 functionality  
**Cons:** Wine quirks, occasional stability issues, requires setup

**Implementation:**
1. Alpha Stack installer detects Linux → offers to install Bottles + MT5
2. Pre-configured Wine prefix with optimal MT5 settings
3. MQL5 Bridge EA installed automatically into MT5
4. Communication via local TCP socket (port 9224)

#### Option B: Cloud MT5 (VPS)

```
Alpha Stack Desktop ←──WebSocket──→ Cloud VPS (Windows)
                                        │
                                   MetaTrader 5
                                   FXPesa Account
```

**Pros:** Reliable, no Wine issues, works from anywhere  
**Cons:** VPS cost ($5–15/month), latency, cloud dependency

#### Option C: Windows/macOS Native

On Windows, MT5 runs natively. On macOS, use the official MT5 for Mac (now available) or Wine.

### 7.2 MQL5 Bridge Expert Advisor

The Bridge EA runs inside MT5 and communicates with Alpha Stack:

```mql5
// AlphaStack_Bridge.mq5
// Runs inside MetaTrader 5, bridges to Alpha Stack backend

#property copyright "Alpha Stack"
#property version   "1.00"

input string AlphaStackHost = "127.0.0.1";
input int    AlphaStackPort = 9224;
input int    UpdateIntervalMs = 100;  // 10 Hz tick rate

// TCP socket connection to Alpha Stack
int socket = INVALID_HANDLE;

// === Communication Protocol ===
// Messages are JSON over TCP, length-prefixed:
// [4 bytes: length][JSON payload]

struct TradeCommand {
   string action;    // "open", "close", "modify"
   string symbol;
   string direction; // "buy", "sell"
   double volume;
   double sl;
   double tp;
   ulong  ticket;    // For close/modify
};

struct MarketData {
   string symbol;
   double bid;
   double ask;
   double high;
   double low;
   long   volume;
   datetime time;
};

// === Main Loop ===
void OnTimer() {
   // 1. Send tick data to Alpha Stack
   SendMarketData();
   
   // 2. Check for commands from Alpha Stack
   ReceiveAndExecuteCommands();
   
   // 3. Send position updates
   SendPositionUpdates();
}

void SendMarketData() {
   string symbols[] = {"EURUSD", "GBPUSD", "USDJPY", "XAUUSD"};
   for (int i = 0; i < ArraySize(symbols); i++) {
      MqlTick tick;
      if (SymbolInfoTick(symbols[i], tick)) {
         string json = StringFormat(
            "{\"type\":\"tick\",\"symbol\":\"%s\",\"bid\":%.5f,\"ask\":%.5f,\"time\":%d}",
            symbols[i], tick.bid, tick.ask, tick.time
         );
         SendMessage(json);
      }
   }
}

void ReceiveAndExecuteCommands() {
   string msg = ReceiveMessage();
   if (msg != "") {
      // Parse JSON command
      TradeCommand cmd = ParseCommand(msg);
      ExecuteTradeCommand(cmd);
   }
}
```

### 7.3 Python MT5 Connector

```python
# alpha-stack-python/mt5/connector.py

import MetaTrader5 as mt5
import asyncio
import json
from typing import Optional, Callable
from dataclasses import dataclass

@dataclass
class MT5Config:
    login: int
    password: str
    server: str
    path: Optional[str] = None  # Path to MT5 terminal on Linux/Wine

class MT5Connector:
    """Manages connection to MetaTrader 5."""
    
    def __init__(self, config: MT5Config, on_tick: Callable = None):
        self.config = config
        self.on_tick = on_tick
        self._connected = False
    
    async def connect(self) -> bool:
        """Initialize MT5 connection."""
        kwargs = {
            "login": self.config.login,
            "password": self.config.password,
            "server": self.config.server,
        }
        if self.config.path:
            kwargs["path"] = self.config.path
        
        if not mt5.initialize(**kwargs):
            raise ConnectionError(f"MT5 init failed: {mt5.last_error()}")
        
        self._connected = True
        return True
    
    async def stream_ticks(self, symbols: list[str]):
        """Stream tick data to callback."""
        while self._connected:
            for symbol in symbols:
                tick = mt5.symbol_info_tick(symbol)
                if tick and self.on_tick:
                    await self.on_tick({
                        "symbol": symbol,
                        "bid": tick.bid,
                        "ask": tick.ask,
                        "time": tick.time,
                    })
            await asyncio.sleep(0.1)  # 10 Hz
    
    async def place_order(self, symbol: str, direction: str, 
                          volume: float, sl: float = 0, 
                          tp: float = 0) -> dict:
        """Place a market order."""
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "sl": sl,
            "tp": tp,
            "magic": 202607,  # Alpha Stack magic number
            "comment": "AlphaStack",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        return {
            "success": result.retcode == mt5.TRADE_RETCODE_DONE,
            "ticket": result.order,
            "price": result.price,
            "error": result.comment if result.retcode != mt5.TRADE_RETCODE_DONE else None,
        }
    
    async def get_positions(self) -> list[dict]:
        """Get all open positions."""
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "direction": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "open_price": p.price_open,
                "current_price": p.price_current,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "swap": p.swap,
                "time": p.time,
            }
            for p in positions
        ]
```

---

## 8. Cross-Platform Build & Distribution

### 8.1 Build Matrix

| Platform | Build Target | Output Format | Size (est.) |
|---|---|---|---|
| Linux x64 | `x86_64-unknown-linux-gnu` | `.AppImage`, `.deb`, `.rpm` | ~8–12 MB |
| Linux ARM64 | `aarch64-unknown-linux-gnu` | `.AppImage`, `.deb` | ~8–12 MB |
| Windows x64 | `x86_64-pc-windows-msvc` | `.msi`, `.exe` (NSIS) | ~8–15 MB |
| macOS x64 | `x86_64-apple-darwin` | `.dmg`, `.app` | ~10–15 MB |
| macOS ARM64 | `aarch64-apple-darwin` | `.dmg`, `.app` | ~10–15 MB |

### 8.2 CI/CD Pipeline

```yaml
# .github/workflows/release.yml
name: Build & Release

on:
  push:
    tags: ['v*']

jobs:
  build:
    strategy:
      matrix:
        include:
          - os: ubuntu-22.04
            target: x86_64-unknown-linux-gnu
            artifacts: '*.AppImage *.deb *.rpm'
          - os: windows-latest
            target: x86_64-pc-windows-msvc
            artifacts: '*.msi *.exe'
          - os: macos-latest
            target: aarch64-apple-darwin
            artifacts: '*.dmg *.app'
    
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      
      # Build Python sidecar bundle
      - name: Build Python sidecar
        run: |
          cd alpha-stack-python
          pip install pyinstaller
          pyinstaller --onefile --name alpha-stack-sidecar main.py
      
      # Build Tauri app (includes Python sidecar as resource)
      - name: Build Tauri
        uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_KEY }}
        with:
          tagName: ${{ github.ref_name }}
          releaseName: Alpha Stack ${{ github.ref_name }}
          releaseBody: 'See the assets below to download.'
          releaseDraft: false
          prerelease: false
          args: --target ${{ matrix.target }}
```

### 8.3 Auto-Update Mechanism

```json
// tauri.conf.json
{
  "updater": {
    "active": true,
    "endpoints": [
      "https://releases.alphastack.app/{{target}}/{{arch}}/{{current_version}}"
    ],
    "dialog": true,
    "pubkey": "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIGtleQp..."
  }
}
```

**Update flow:**
1. App checks for updates on startup (and periodically every 6 hours)
2. If update found → native OS notification "Update available: v1.2.3"
3. User clicks "Update & Restart" → downloads, verifies signature, replaces binary
4. Trading engine state is saved → app restarts → state restored

### 8.4 Python Bundling Strategy

The Python sidecar and its dependencies need to be bundled with the app:

**Approach: Embedded Python + pre-built wheels**

1. **Bundle a minimal Python runtime** (~15 MB compressed)
   - Use `python-build-standalone` (by Gregory Szorc) — pre-built, portable Python
   - Include only essential stdlib modules
   
2. **Pre-install packages as wheels** in `site-packages/`:
   ```
   resources/python/
   ├── bin/python3
   ├── lib/python3.11/
   │   └── site-packages/
   │       ├── MetaTrader5/
   │       ├── torch/          (CPU-only, ~150 MB)
   │       ├── numpy/
   │       ├── pandas/
   │       ├── scikit-learn/
   │       ├── fastapi/
   │       └── uvicorn/
   └── requirements.txt
   ```

3. **Alternative: PyInstaller bundle** (~80 MB)
   - Single executable, no Python installation needed
   - Easier but larger and harder to debug

**Recommendation:** Embedded Python for development flexibility, PyInstaller for production releases.

---

## 9. Web Companion App

### 9.1 Architecture

```
┌─────────────────────────────────────────┐
│          Alpha Stack Desktop            │
│  ┌───────────────────────────────────┐  │
│  │  Built-in Web Server (port 9222)  │  │
│  │  ├── REST API (FastAPI)           │  │
│  │  ├── WebSocket Server             │  │
│  │  └── Static Web App Files         │  │
│  └──────────────────┬────────────────┘  │
└─────────────────────┼───────────────────┘
                      │
         ┌────────────┴────────────┐
         │    LAN / Internet       │
         │  (optional: ngrok/cloudflare) │
         └────────────┬────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    ▼                 ▼                 ▼
┌────────┐     ┌──────────┐     ┌──────────┐
│ Browser│     │  Mobile  │     │  Another │
│ (PWA)  │     │  App     │     │  Desktop │
└────────┘     └──────────┘     └──────────┘
```

### 9.2 Web App Stack

```
web-companion/
├── Next.js 15 (or Astro)     # Static-first, fast loading
├── React 19 + TypeScript
├── TailwindCSS
├── Lightweight Charts         # Same charting as desktop
├── Socket.IO Client           # Real-time data
└── PWA Manifest               # Installable on mobile
```

### 9.3 API Design

```yaml
# REST Endpoints
GET  /api/v1/status              # System health & status
GET  /api/v1/account             # Account balance, equity, margin
GET  /api/v1/positions           # Open positions
GET  /api/v1/orders              # Pending orders
GET  /api/v1/history             # Trade history (paginated)
GET  /api/v1/signals             # Active AI signals
GET  /api/v1/analytics           # Performance metrics
POST /api/v1/trade/open          # Open trade (manual override)
POST /api/v1/trade/close/:id     # Close position
POST /api/v1/trading/pause       # Pause trading
POST /api/v1/trading/resume      # Resume trading

# WebSocket Channels
ws://localhost:9222/ws/prices    # Live price stream
ws://localhost:9222/ws/signals   # Signal notifications
ws://localhost:9222/ws/trades    # Trade events
ws://localhost:9222/ws/system    # System status updates
```

### 9.4 Remote Access

For monitoring when away from the desktop:

1. **Local network:** Direct access at `http://192.168.x.x:9222`
2. **Internet (simple):** Cloudflare Tunnel (free) — no port forwarding needed
3. **Internet (advanced):** Tailscale/WireGuard VPN — secure, no exposed ports

```rust
// Tauri command to enable remote access
#[tauri::command]
async fn enable_remote_access(method: String) -> Result<String, String> {
    match method.as_str() {
        "cloudflare" => {
            // Start cloudflare tunnel
            // Returns public URL
        }
        "tailscale" => {
            // Configure tailscale funnel
        }
        _ => Err("Unsupported method".into())
    }
}
```

---

## 10. Mobile Companion App

### 10.1 Technology Choice: **React Native + Expo**

**Rationale:**
- Same React/TypeScript skills as desktop and web
- Expo simplifies iOS/Android builds
- Excellent push notification support
- Can share component logic with web companion

### 10.2 Mobile App Features

```
mobile/
├── screens/
│   ├── Dashboard        # Account overview, daily P&L
│   ├── Positions        # Open positions with live P&L
│   ├── Signals          # AI signal feed
│   ├── Alerts           # Notification history
│   └── Settings         # Connection, notification prefs
├── components/
│   ├── MiniChart        # Sparkline price charts
│   ├── PositionCard     # Position summary card
│   └── SignalBadge      # Signal indicator
└── services/
    ├── push-notifications  # FCM/APNs integration
    ├── websocket           # Real-time connection
    └── api                 # REST API client
```

### 10.3 Push Notification Flow

```
Alpha Stack Desktop (Rust)
    │
    ├── Detects high-confidence signal
    │   or trade event
    │
    ├── Sends to notification service
    │   ├── Option A: Direct FCM/APNs (requires API keys)
    │   ├── Option B: Via web companion relay
    │   └── Option C: Telegram bot (simplest, recommended)
    │
    └── Mobile receives push notification
        └── "🟢 EURUSD BUY Signal — Confidence: 85% — Entry: 1.0845"
```

**Recommended:** Telegram bot integration for alerts (already common in trading, zero app install needed, works everywhere).

---

## 11. Installation & Onboarding

### 11.1 One-Line Install Commands

#### Linux (Pop!_OS / Ubuntu / Debian)

```bash
# One-line install
curl -fsSL https://install.alphastack.app/linux.sh | bash

# What this does:
# 1. Detects architecture (x64/ARM)
# 2. Downloads .deb or .AppImage
# 3. Installs to ~/.local/share/alphastack/
# 4. Sets up desktop entry & PATH
# 5. Installs embedded Python + dependencies
# 6. (Optional) Installs Bottles + MT5 for Wine-based trading
# 7. Launches first-run wizard
```

#### Windows

```powershell
# PowerShell one-liner
irm https://install.alphastack.app/windows.ps1 | iex

# Or: winget install AlphaStack
# Or: Download .exe installer from website

# What this does:
# 1. Downloads NSIS installer
# 2. Installs to %LOCALAPPDATA%\AlphaStack\
# 3. Adds to PATH, creates Start Menu shortcut
# 4. Installs embedded Python + dependencies
# 5. (Optional) Detects existing MT5 installation
# 6. Launches first-run wizard
```

#### macOS

```bash
# Homebrew
brew install --cask alphastack

# Or one-liner
curl -fsSL https://install.alphastack.app/mac.sh | bash

# What this does:
# 1. Downloads .dmg (universal binary: Intel + Apple Silicon)
# 2. Installs to /Applications/AlphaStack.app
# 3. Installs embedded Python + dependencies
# 4. Launches first-run wizard
```

### 11.2 First-Run Wizard

```
┌─────────────────────────────────────────────────────────┐
│                Alpha Stack Setup Wizard                   │
│                                                           │
│  Step 1/5: Welcome                                        │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Welcome to Alpha Stack!                             │ │
│  │                                                      │ │
│  │  This wizard will set up your trading system.        │ │
│  │  You'll need:                                        │ │
│  │  • FXPesa MT5 account credentials                   │ │
│  │  • ~5 minutes for initial setup                      │ │
│  │                                                      │ │
│  │  [Let's Begin →]                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  Step 2/5: MT5 Connection                                 │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  MetaTrader 5 Setup                                  │ │
│  │                                                      │ │
│  │  ○ I have MT5 installed (Windows/native)            │ │
│  │  ● I need MT5 installed (Linux — will use Wine)     │ │
│  │  ○ I'll use a cloud VPS for MT5                     │ │
│  │                                                      │ │
│  │  Login:    [______________]                          │ │
│  │  Password: [______________]                          │ │
│  │  Server:   [FXPesa-Live    ▾]                       │ │
│  │                                                      │ │
│  │  [Test Connection]  [Next →]                         │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  Step 3/5: Risk Management                                │
│  Step 4/5: Strategy Parameters                            │
│  Step 5/5: Notification Setup                             │
└─────────────────────────────────────────────────────────┘
```

### 11.3 Dependency Management

All dependencies are self-contained:

```
AlphaStack/
├── alphastack              # Main binary (Rust/Tauri)
├── resources/
│   ├── python/             # Embedded Python runtime
│   │   ├── bin/python3
│   │   └── lib/site-packages/  # All Python packages
│   ├── mt5/                # MT5 Bridge EA files
│   │   └── AlphaStack_Bridge.ex5
│   ├── models/             # Pre-trained AI models
│   └── web/                # Web companion static files
├── config/
│   └── default.toml        # Default configuration
└── data/
    ├── trades.db           # SQLite trade history
    └── logs/               # Application logs
```

**No external dependencies required.** Python, packages, models — all bundled.

---

## 12. Security Architecture

### 12.1 Credential Storage

```
┌─────────────────────────────────────────────────────┐
│                  Security Layers                     │
│                                                      │
│  Layer 1: OS Keychain Integration                    │
│  ├── Linux:   libsecret (GNOME Keyring / KWallet)   │
│  ├── macOS:   Keychain Services                     │
│  └── Windows: Windows Credential Manager            │
│                                                      │
│  Layer 2: Encrypted Config (fallback)                │
│  ├── AES-256-GCM encrypted config file              │
│  ├── Key derived from machine-specific entropy      │
│  └── Never stores plaintext credentials             │
│                                                      │
│  Layer 3: Runtime Isolation                          │
│  ├── Broker credentials only in Rust core           │
│  ├── Python sidecar receives tokens, not passwords  │
│  └── Frontend never sees raw credentials            │
│                                                      │
│  Layer 4: Tauri Security Model                       │
│  ├── Capability-based permissions                   │
│  ├── No Node.js in renderer (unlike Electron)       │
│  └── CSP headers enforced                           │
└─────────────────────────────────────────────────────┘
```

### 12.2 Tauri Permissions (capabilities)

```json
// src-tauri/capabilities/default.json
{
  "identifier": "default",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "core:window:allow-show",
    "core:window:allow-hide",
    "core:window:allow-minimize",
    "shell:sidecar",
    "notification:default",
    "updater:default",
    "tray:default"
  ]
}
```

### 12.3 Network Security

- **Local WebSocket server** binds to `127.0.0.1` by default (not `0.0.0.0`)
- **Remote access** requires explicit opt-in with API key authentication
- **TLS** for all external connections (MT5, data feeds)
- **No telemetry** — zero data leaves the machine unless user enables it

---

## 13. File & Directory Layout

### 13.1 User Data Directory

```
~/.alphastack/                    # Linux / macOS
%APPDATA%\AlphaStack\            # Windows

├── config.toml                   # User configuration
├── credentials.keychain          # Encrypted credentials (or use OS keychain)
├── data/
│   ├── trades.db                 # SQLite: trade history
│   ├── signals.db                # SQLite: signal log
│   ├── market/                   # Cached market data
│   │   ├── EURUSD_H1.parquet
│   │   └── GBPUSD_H1.parquet
│   └── models/                   # Trained AI model files
│       ├── macro_model_v2.pt
│       ├── smc_detector_v1.onnx
│       └── regime_model_v3.pkl
├── logs/
│   ├── alphastack.log            # Main application log
│   ├── trading.log               # Trade execution log
│   ├── python.log                # Python sidecar log
│   └── mt5.log                   # MT5 communication log
└── backups/
    ├── config_backup_20260711.toml
    └── trades_backup_20260711.db
```

### 13.2 Project Source Layout

```
alpha-stack/
├── src-tauri/                    # Rust / Tauri backend
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── capabilities/
│   ├── icons/
│   └── src/
│       ├── main.rs
│       ├── lib.rs
│       ├── commands/
│       ├── engine/
│       ├── data/
│       ├── bridge/
│       ├── tray/
│       └── config/
├── src/                          # React/TypeScript frontend
│   ├── App.tsx
│   ├── pages/
│   ├── components/
│   ├── stores/
│   ├── hooks/
│   └── lib/
├── alpha-stack-python/           # Python sidecar
│   ├── main.py
│   ├── requirements.txt
│   ├── ai/
│   ├── mt5/
│   ├── data/
│   └── api/
├── web-companion/                # Web companion app (Next.js)
├── mobile/                       # React Native mobile app
├── mql5/                         # MQL5 Expert Advisors
│   └── AlphaStack_Bridge.mq5
├── scripts/                      # Build & install scripts
│   ├── install-linux.sh
│   ├── install-windows.ps1
│   └── install-mac.sh
├── docs/                         # Documentation
├── tests/                        # Test suites
├── .github/                      # CI/CD workflows
├── package.json                  # Frontend dependencies
├── Cargo.toml                    # Workspace root
└── README.md
```

---

## 14. Technology Stack Summary

| Component | Technology | Version | Purpose |
|---|---|---|---|
| **Desktop Shell** | Tauri | 2.x | Window, tray, IPC, auto-update |
| **Core Engine** | Rust | 1.80+ | Trading logic, signal processing, WS server |
| **Frontend** | React + TypeScript | 19 / 5.x | Dashboard UI |
| **Build Tool** | Vite | 6.x | Frontend bundling |
| **Styling** | TailwindCSS + shadcn/ui | 4.x | UI components |
| **State** | Zustand | 5.x | Client state management |
| **Charts** | Lightweight Charts | 4.x | TradingView open-source charts |
| **AI Runtime** | PyTorch (CPU) | 2.x | Model inference |
| **ML Framework** | scikit-learn + PyTorch | — | Training & inference |
| **MT5 API** | MetaTrader5 Python | 5.0.45+ | Broker connectivity |
| **Data Processing** | pandas + NumPy | — | Market data manipulation |
| **Web Server** | FastAPI + Uvicorn | 0.115+ | REST API + WebSocket |
| **Database** | SQLite (via rusqlite) | — | Local trade/config storage |
| **Mobile** | React Native + Expo | 52+ | Mobile companion |
| **Web Companion** | Next.js | 15 | Web monitoring app |
| **CI/CD** | GitHub Actions | — | Build, test, release |
| **Packaging** | Tauri Bundler | — | AppImage, .deb, .msi, .dmg |

---

## 15. Development Roadmap

### Phase 1: Foundation (Weeks 1–3)

- [ ] Tauri 2.x project scaffolding
- [ ] Rust core: config management, logging, system tray
- [ ] Python sidecar: process management, health checks, IPC
- [ ] Basic dashboard skeleton (React + Vite + TailwindCSS)
- [ ] MT5 Python connector: connect, stream ticks, place orders
- [ ] SQLite schema for trades, signals, settings

### Phase 2: Trading Engine (Weeks 4–6)

- [ ] Signal processor: aggregate macro + SMC + S/R + RSI + candlestick
- [ ] Risk manager: position sizing ($7 capital aware), max drawdown
- [ ] Order manager: open, close, modify, trailing stop
- [ ] Real-time price chart (Lightweight Charts integration)
- [ ] Trade management UI (active positions, P&L)

### Phase 3: AI Integration (Weeks 7–9)

- [ ] AI model inference pipeline (PyTorch CPU)
- [ ] Macro sentiment model integration
- [ ] SMC detector (order blocks, FVG, liquidity sweeps)
- [ ] Market regime classifier
- [ ] Ensemble voting system
- [ ] Signal confidence display in UI

### Phase 4: Polish & Distribution (Weeks 10–12)

- [ ] System tray: notifications, quick stats, pause/resume
- [ ] Auto-update mechanism
- [ ] Cross-platform build pipeline (GitHub Actions)
- [ ] Installation scripts (Linux, Windows, macOS)
- [ ] First-run setup wizard
- [ ] Web companion app (basic monitoring)
- [ ] Telegram alert integration

### Phase 5: Mobile & Remote (Weeks 13–14)

- [ ] React Native mobile companion
- [ ] Remote access via Cloudflare Tunnel
- [ ] Push notifications
- [ ] Performance optimization & profiling
- [ ] Security audit

---

## Appendix A: Key Design Decisions Log

| Decision | Choice | Rationale |
|---|---|---|
| Desktop framework | Tauri 2.x | 10x lighter than Electron, Rust security, native tray |
| Frontend framework | React + TypeScript | Ecosystem, team familiarity, shared with web/mobile |
| State management | Zustand | Lightweight, no boilerplate, great for real-time data |
| Charting | Lightweight Charts | TradingView's open-source lib, performant, trading-focused |
| Python sidecar | Managed subprocess | AI/ML needs Python; Rust handles performance-critical path |
| MT5 on Linux | Wine/Bottles | Free, local, no VPS cost (appropriate for $7 capital) |
| Database | SQLite | Zero-config, embedded, sufficient for single-user desktop |
| Mobile framework | React Native + Expo | Same React skills, fast development, cross-platform |
| Alert delivery | Telegram bot | Free, instant, works everywhere, no mobile app required for alerts |
| Remote access | Cloudflare Tunnel | Free, secure, no port forwarding, easy setup |
| Packaging | Embedded Python + PyInstaller | Self-contained, zero external dependencies |

## Appendix B: Risk Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Wine/MT5 instability on Linux | High | Cloud MT5 fallback option; Bridge EA with reconnection logic |
| Python sidecar crash | Medium | Rust monitors health, auto-restarts; trade state persisted in SQLite |
| Tauri ecosystem immaturity | Medium | Architecture is backend-agnostic; can swap to Electron if needed |
| $7 capital too small for trades | High | Micro-lot support (0.01); risk manager enforces % risk, not $ amounts |
| AI model overfitting | Medium | Walk-forward validation; ensemble approach reduces single-model risk |
| Network interruption | Medium | Order queue with retry; position reconciliation on reconnect |
| Auto-update breaks trading | High | Update only when no open positions; manual update option always available |

---

*Architecture designed for Alpha Stack v1.0 — Institutional-grade AI trading on a shoestring budget.*
