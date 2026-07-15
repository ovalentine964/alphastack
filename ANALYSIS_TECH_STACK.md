# AlphaStack — Tech Stack & Languages Review

**Reviewer:** Tech Stack Analysis Agent  
**Date:** 2026-07-15  
**Scope:** All dependency files, source code, CI/CD, infrastructure, cross-language integration

---

## Executive Summary

AlphaStack is a **polyglot, multi-platform trading system** spanning Python (backend/engine), Rust (performance-critical compute), Flutter/Dart (mobile), TypeScript/React (web + desktop via Tauri), and MQL5 (MetaTrader 5 bridge). The architecture is ambitious and well-structured, but contains significant tech debt in the form of placeholder data, unconnected integrations, and version pinning gaps. The Rust core is **real and substantial** — not boilerplate.

**Overall Grade: B+** — Strong architecture, solid language choices, but missing production hardening.

---

## 1. PYTHON STACK

### Framework Choices

| Component | Choice | Assessment |
|-----------|--------|------------|
| Web framework | **FastAPI 0.115+** | ✅ Excellent — async-native, auto-docs, type-safe |
| ASGI server | **Uvicorn** | ✅ Standard choice |
| Agent framework | **LangGraph 0.2+ / LangChain 0.3+** | ✅ Good for multi-agent orchestration |
| ORM | **SQLAlchemy 2.0 (async)** | ✅ Industry standard, async support |
| DB driver | **asyncpg** (async) + **psycopg2** (sync fallback) | ✅ Correct dual-driver pattern |
| Migrations | **Alembic** | ✅ Standard |
| Validation | **Pydantic v2 + pydantic-settings** | ✅ Excellent — strict typing, env config |
| Redis | **redis[hiredis] 5.2+** | ✅ Async Redis with C acceleration |
| HTTP client | **httpx** | ✅ Async-native |

### Dependency Quality

**Strengths:**
- `requires-python = ">=3.12"` — modern Python target
- All major deps are well-maintained, actively developed libraries
- `structlog` for structured logging — production-grade choice
- `prometheus-client` for metrics — good observability foundation
- `ccxt >= 4.4` for crypto exchange access — comprehensive library

**Concerns:**
- `torch >= 2.5.0` — **Very heavy dependency** (~2GB). Not clear if actually used in the codebase (no training code references found). Should be optional or moved to `[ml]` extra.
- `MetaTrader5 >= 5.0.51` — **Windows-only** dependency. Will fail on Linux/macOS. Must be conditional.
- `ta-lib >= 0.6.0` — Requires C library compilation. The Dockerfile handles this, but local dev will be painful.
- `onnxruntime >= 1.20.0` — No ONNX model files found in repo. Premature dependency.
- No version upper bounds on any dependency — risky for breaking changes.

### Code Patterns

**Positive patterns observed:**
- ✅ **Async/await throughout** — FastAPI routes, database sessions, event bus, WebSocket
- ✅ **Pydantic models** for all data structures (events, config, state)
- ✅ **Proper typing** — `from __future__ import annotations`, `type hints` on all functions
- ✅ **Abstract base classes** — `AlphaStackAgent(abc.ABC)`, `BrokerConnector(ABC)`, `AlphaStackStep`
- ✅ **Dependency injection** — Event bus injected into agents
- ✅ **Structured logging** — `structlog` with named parameters (`logger.info("ccxt_connected", exchange=...)`)
- ✅ **Secret management** — `SecretStr` for all credentials in config
- ✅ **Graceful degradation** — Rust bridge has full Python fallback implementations
- ✅ **Rate limiting** — Both in-memory token bucket (API) and async limiter (CCXT)
- ✅ **Connection pooling** — SQLAlchemy pool_size=20, max_overflow=10
- ✅ **Lifespan pattern** — FastAPI `@asynccontextmanager` for startup/shutdown

**Issues:**
- ⚠️ `datetime.utcnow()` used in multiple places — deprecated in Python 3.12, should use `datetime.now(timezone.utc)`
- ⚠️ Mixed logging libraries — `structlog` in brokers, `logging.getLogger` in agents/utils
- ⚠️ In-memory rate limiter won't work across multiple workers/processes
- ⚠️ No authentication middleware on API routes — auth router exists but no JWT/session validation middleware
- ⚠️ `dashboard_screen.dart` uses hardcoded mock data instead of real API calls

### Performance Considerations

- ✅ Rust offloading for tick processing, indicators, risk calculations, backtesting
- ✅ Parallel pipeline execution for steps 5-9 (`asyncio.gather`)
- ✅ Redis Streams for event bus (scalable pub/sub)
- ✅ Connection pooling on both PostgreSQL and Redis
- ⚠️ No caching layer (Redis used for events, not HTTP caching)
- ⚠️ No pagination on list endpoints (trades, signals)

---

## 2. FLUTTER/DART STACK

### Framework & Dependencies

| Component | Choice | Assessment |
|-----------|--------|------------|
| State management | **Riverpod 2.4+** | ✅ Modern, compile-safe |
| HTTP | **http 1.2+** | ✅ Standard |
| WebSocket | **web_socket_channel 2.4+** | ✅ Standard |
| Charts | **fl_chart 0.66+** | ✅ Good charting library |
| Auth | **local_auth** (biometric) | ✅ Good for mobile security |
| Storage | **flutter_secure_storage** | ✅ Encrypted keychain/keystore |
| Push notifications | **firebase_messaging 14.7+** | ✅ Standard |
| JSON | **json_annotation + json_serializable** | ✅ Code generation for models |
| Fonts | **google_fonts** | ✅ |
| Images | **cached_network_image** | ✅ |
| Dart SDK | `>=3.2.0 <4.0.0` | ✅ Modern |

### Architecture Pattern

- ✅ **Clean separation** — `models/`, `services/`, `screens/`, `widgets/`
- ✅ **Service singletons** — `ApiService` and `WebSocketService` with factory constructors
- ✅ **Secure storage** for auth tokens and base URL
- ✅ **WebSocket reconnection** — exponential backoff with max 10 attempts
- ✅ **Stream-based architecture** — Multiple typed streams (positions, signals, trades, portfolio)
- ✅ **Proper error handling** — `ApiException` class, try/catch in services
- ✅ **Dark theme** with comprehensive `ThemeData` configuration
- ✅ **Generated code** — `.g.dart` files for JSON serialization

### Code Quality

**Issues:**
- ⚠️ **Dashboard uses mock data** — `FutureProvider` returns hardcoded data with `Future.delayed` instead of calling `ApiService`. This means the dashboard is non-functional.
- ⚠️ **No tests** — No `test/` directory found in mobile app
- ⚠️ **No dependency injection** — Riverpod providers defined inline, no centralized provider setup
- ⚠️ **WebSocket protocol mismatch** — Flutter subscribes with `{'type': 'subscribe', 'channel': '...'}` (singular) but server expects `{'type': 'subscribe', 'channels': [...]}` (plural array)
- ⚠️ **No offline support** — No local database (Hive, drift, etc.)
- ⚠️ **No iOS build config** — Only Android APK built in CI (`flutter build apk`)

---

## 3. TYPESCRIPT / NEXT.JS STACK

### Web App (`apps/web/`)

| Component | Choice | Assessment |
|-----------|--------|------------|
| Framework | **Next.js 15.1+** | ✅ Latest stable |
| React | **19.0+** | ✅ Latest |
| State management | **Zustand 5.0+** | ✅ Lightweight, excellent DX |
| Charts | **lightweight-charts 4.2+** | ✅ TradingView's charting lib — excellent for trading |
| Styling | **Tailwind CSS 3.4+** | ✅ |
| Icons | **lucide-react** | ✅ |
| TypeScript | **5.7+** | ✅ |

**Strengths:**
- ✅ `output: "standalone"` in next.config — Docker-optimized builds
- ✅ API proxy via rewrites — clean backend integration
- ✅ Proper Zustand stores with typed interfaces
- ✅ `"use client"` directives for client components
- ✅ WebSocket client with auto-reconnect

**Issues:**
- ⚠️ **No server components used** — Everything is `"use client"`. Misses Next.js 15's main advantage.
- ⚠️ **No error boundaries** — Missing `error.tsx` and `loading.tsx` files
- ⚠️ **No authentication** — No middleware, no session management
- ⚠️ **API client inconsistency** — `lib/api.ts` and `stores/tradeStore.ts` both make raw `fetch` calls independently
- ⚠️ **No testing** — No test files found
- ⚠️ **Next.js 15 + React 19** — Very new; potential ecosystem compatibility issues

### Desktop App (`apps/desktop/`)

| Component | Choice | Assessment |
|-----------|--------|------------|
| Framework | **Tauri 1.x** | ✅ Lightweight native wrapper |
| Frontend | **React 18 + Vite 5** | ✅ Fast dev/build |
| State | **Zustand 4.5** | ✅ (Note: v4 vs web's v5 — version mismatch) |
| Styling | **Tailwind CSS** | ✅ |
| Build | **Vite** | ✅ |

**Strengths:**
- ✅ System tray integration with native menu
- ✅ Native notifications via Tauri plugin
- ✅ Settings persistence via Tauri Store plugin
- ✅ Auto-updater plugin configured
- ✅ Clean Tauri bridge pattern (`tauri-bridge.ts`)

**Issues:**
- ⚠️ **Tauri v1** — Tauri v2 is now stable and recommended
- ⚠️ **React 18 vs Web's React 19** — Version inconsistency across apps
- ⚠️ **Zustand 4 vs 5** — Different versions in desktop vs web
- ⚠️ **No shared code** — Desktop and web have completely separate components despite similar functionality
- ⚠️ **Hardcoded localhost proxy** — `next.config.ts` proxies to `localhost:8000`

---

## 4. RUST STACK

### Purpose & Scope

The Rust code serves **two distinct purposes**:

#### A. Performance Core (`src/rust_core/`) — **REAL, SUBSTANTIAL CODE**

This is a PyO3 extension module providing high-performance compute for:

| Module | Purpose | Lines | Quality |
|--------|---------|-------|---------|
| `tick_processor.rs` | Tick ingestion, OHLCV aggregation, volume profiling | ~150 | ✅ Solid |
| `indicators.rs` | RSI, MACD, Bollinger Bands, ATR, ADX, VWAP | ~250 | ✅ Correct implementations |
| `signal_compute.rs` | Confluence scoring, structure detection (HH/HL/LH/LL), S/R levels | ~200 | ✅ Real algorithms |
| `order_book.rs` | Imbalance detection, liquidity pools, cumulative delta | ~180 | ✅ Useful microstructure |
| `risk_calculator.rs` | Kelly criterion, drawdown, correlation, CVaR/VaR, Sharpe/Sortino | ~200 | ✅ Standard quant metrics |
| `backtest_engine.rs` | Event-driven backtester with walk-forward optimization | ~250 | ✅ Functional |

**Assessment: This is NOT placeholder code.** The implementations are algorithmically correct, well-documented, and expose clean PyO3 interfaces. The release profile (`opt-level = 3, lto = true, codegen-units = 1, strip = true`) shows performance awareness.

**Cargo Dependencies:**
- `pyo3 0.22` with `abi3-py310` — ✅ Stable ABI for Python 3.10+
- `ndarray 0.16` + `numpy 0.22` — ✅ NumPy interop (though not heavily used yet)
- `serde` + `serde_json` — ✅ Serialization
- `tokio` — ⚠️ Imported but not actually used (no async runtime in the extension)
- `thiserror 2` — ✅ Error handling
- `rand 0.8` — ✅ For backtesting randomness

#### B. Desktop Shell (`apps/desktop/src-tauri/`) — **THIN WRAPPER**

- `commands.rs` — 4 simple Tauri commands (notify, toggle_window, version, system_info)
- `main.rs` — System tray setup and event handling
- Dependencies: Tauri 1.x, serde, tokio, chrono, uuid

### Python ↔ Rust Bridge Quality

The bridge (`src/alphastack/core/rust_bridge.py`) is **exceptionally well-designed**:

- ✅ **Graceful fallback** — Full pure-Python implementations of all Rust classes
- ✅ **Runtime detection** — `RUST_AVAILABLE` flag
- ✅ **Identical API surface** — Same class names and method signatures
- ✅ **Logging** — Warns when falling back to Python
- ✅ **Helper utility** — `check_rust()` returns status dict

**Gap:** The Python fallbacks are incomplete compared to Rust:
- `Indicators` fallback only implements RSI and VWAP (missing MACD, Bollinger, ATR, ADX)
- `SignalEngine` fallback only implements `confluence_score` (missing structure detection, levels, trend bias)
- `OrderBookAnalyzer` fallback is a stub (no actual analysis methods)
- `BacktestEngine` fallback has no `run_backtest` method

---

## 5. INFRASTRUCTURE STACK

### Docker

**Dockerfile Quality: A-**
- ✅ Multi-stage build (builder → runtime)
- ✅ TA-Lib C library compiled from source
- ✅ Non-root user (`alphastack`)
- ✅ Health check configured
- ✅ Minimal runtime image (`python:3.12-slim`)
- ⚠️ No `.dockerignore` file found
- ⚠️ No Rust build stage — the Rust extension won't be available in Docker
- ⚠️ No pinned image digests — `python:3.12-slim` and `timescale/timescaledb:latest-pg16` are mutable tags

**docker-compose.yml Quality: B+**
- ✅ TimescaleDB (PostgreSQL + timescale extension) — good for time-series
- ✅ Redis 7 Alpine
- ✅ Health checks on all services
- ✅ `depends_on` with `condition: service_healthy`
- ✅ Named volumes for persistence
- ✅ YAML anchors for shared env vars
- ⚠️ Hardcoded credentials in compose file (dev-only, but risky)
- ⚠️ `version: "3.9"` — deprecated in modern Docker Compose
- ⚠️ No ClickHouse service despite being mentioned in architecture docs
- ⚠️ No monitoring stack (Prometheus/Grafana) in compose
- ⚠️ Trading engine service uses `profiles: [engine]` — won't start by default

### CI/CD Pipeline

**Quality: B**

| Workflow | Purpose | Assessment |
|----------|---------|------------|
| `ci.yml` | Lint + type-check + test on push/PR | ✅ Good — ruff, mypy, pytest |
| `deploy.yml` | Build Docker, push to GHCR, deploy staging/prod | ⚠️ Deployment steps are stubs (`echo` only) |
| `pages.yml` | Deploy docs to GitHub Pages | ✅ Working |
| `release.yml` | Build desktop (Win/Mac/Linux), mobile (Android), web | ✅ Comprehensive multi-platform |

**Issues:**
- ⚠️ `deploy.yml` — Staging and production deploy steps are **placeholder echo statements**, not real kubectl/deployment commands
- ⚠️ No Flutter test step in CI (only build)
- ⚠️ No Rust compilation step in CI (no `maturin develop` or `cargo build`)
- ⚠️ `mypy` step has `|| true` — type errors won't fail the build
- ⚠️ TypeScript matrix checks `apps/mobile` as TypeScript — it's a Flutter/Dart project
- ⚠️ No security scanning (SAST, dependency audit, container scanning)

### Database Choices

| Database | Use Case | Assessment |
|----------|----------|------------|
| **TimescaleDB** (PostgreSQL 16) | Time-series market data, trade history | ✅ Excellent choice for financial time-series |
| **Redis 7** | Event bus (Streams), caching, pub/sub | ✅ Correct use of Streams for event-driven architecture |
| **ClickHouse** | Mentioned in architecture docs | ❌ Not implemented in infrastructure |

### Monitoring

- `prometheus-client` in Python deps — metrics library present
- `src/alphastack/utils/metrics.py` exists — likely Prometheus metrics
- **No Grafana, Prometheus server, or alerting** in docker-compose
- **No APM** (no Datadog, New Relic, or OpenTelemetry)

---

## 6. CROSS-LANGUAGE INTEGRATION

### Python ↔ Rust Bridge

**Quality: A-**

- Clean PyO3 bindings with `#[pymodule]` registration
- `abi3-py310` for stable ABI across Python versions
- Comprehensive fallback implementations
- `check_rust()` utility for runtime introspection
- Build tooling via `pyo3-build-config` in `build.rs`

**Missing:**
- No `maturin` configuration (pyproject.toml doesn't reference maturin for building the Rust extension)
- No CI step to compile and test the Rust extension
- The `numpy` crate is a dependency but not used in any Rust source file

### API Contract (Frontend ↔ Backend)

**Quality: B**

- REST API at `/api/v1/` with typed routes
- WebSocket at `/ws` with JSON protocol
- Next.js proxies `/api/*` → `http://localhost:8000`

**Issues:**
- ⚠️ No OpenAPI/TypeScript code generation — frontend types are manually maintained
- ⚠️ No API versioning strategy beyond the `/v1` prefix
- ⚠️ No request/response validation on frontend

### WebSocket Protocol Design

**Quality: B+**

Server protocol (well-defined):
```
Client → Server: {"type": "subscribe", "channels": ["prices", "trades"]}
Client → Server: {"type": "ping"}
Server → Client: {"channel": "prices", "data": {...}, "ts": 1234567890.0}
```

**Issues:**
- ⚠️ **Protocol mismatch** — Flutter sends `{'channel': '...'}` (singular), server expects `{'channels': [...]}` (array)
- ⚠️ No authentication on WebSocket connections
- ⚠️ No message compression for high-frequency data
- ⚠️ No binary protocol option for tick data (JSON is verbose)

---

## 7. RECOMMENDATIONS

### 🔴 Critical (Must Fix)

1. **Build the Rust extension in CI** — Add a `maturin develop --release` step. Currently the Rust core is never compiled or tested in CI.

2. **Fix dashboard mock data** — Both Flutter and potentially web dashboards use hardcoded data. Wire up real API calls.

3. **Fix WebSocket protocol mismatch** — Flutter's `subscribe` sends singular `channel`, server expects plural `channels` array.

4. **Make `MetaTrader5` dependency conditional** — It's Windows-only. Move to `[mt5]` optional extra:
   ```toml
   [project.optional-dependencies]
   mt5 = ["MetaTrader5>=5.0.51"]
   ```

5. **Remove or make `torch` optional** — It's a 2GB dependency with no visible usage. Move to `[ml]` extra.

### 🟡 Important (Should Fix)

6. **Add `.dockerignore`** — Prevent `.git/`, `node_modules/`, `target/` from bloating Docker builds.

7. **Pin Docker image digests** — Use `python:3.12-slim@sha256:...` for reproducible builds.

8. **Add monitoring to docker-compose** — Prometheus + Grafana services with pre-configured dashboards.

9. **Unify logging** — Choose either `structlog` or standard `logging` consistently. Recommend `structlog` everywhere.

10. **Fix `datetime.utcnow()`** — Replace with `datetime.now(timezone.utc)` throughout (deprecated in Python 3.12).

11. **Add API authentication middleware** — The auth routes exist but there's no JWT validation middleware protecting other routes.

12. **Upgrade Tauri to v2** — Tauri v1 is in maintenance mode.

13. **Align frontend dependency versions** — React 18 (desktop) vs 19 (web), Zustand 4 vs 5.

14. **Add `maturin` build config** to pyproject.toml:
    ```toml
    [tool.maturin]
    features = ["pyo3/extension-module"]
    ```

15. **Complete Python fallbacks** — The Rust bridge fallbacks are incomplete (missing MACD, Bollinger, ATR, ADX, structure detection, order book analysis, backtest engine).

### 🟢 Nice to Have

16. **Extract shared TypeScript types** — Create a `packages/shared/` workspace for API types used by both web and desktop.

17. **Add Next.js server components** — The web app uses `"use client"` everywhere, missing SSR benefits.

18. **Add OpenAPI code generation** — Generate TypeScript types from FastAPI's auto-generated OpenAPI spec.

19. **Add ClickHouse** — Referenced in architecture but not implemented. Good for analytics queries on large time-series.

20. **Add integration tests for Rust ↔ Python** — Test the bridge with actual Rust compilation.

21. **Add Flutter iOS build** — CI only builds Android APK. Add iOS build step.

22. **Add `numpy` usage in Rust** — The `numpy` crate is imported but unused. Either use it for zero-copy array passing or remove it.

23. **Implement real deployment** — `deploy.yml` has placeholder echo commands. Implement actual kubectl/Helm deployments.

### Tech Debt Assessment

| Category | Debt Level | Notes |
|----------|-----------|-------|
| Python backend | **Low** | Clean code, good patterns, well-typed |
| Rust core | **Low** | Well-implemented, correct algorithms |
| Flutter mobile | **Medium** | Mock data, no tests, protocol mismatch |
| Web frontend | **Medium** | No SSR, no tests, no auth |
| Desktop app | **Medium** | Outdated Tauri v1, no tests |
| Infrastructure | **High** | Placeholder deployments, no monitoring, no Rust in Docker |
| CI/CD | **Medium** | Good foundation but missing Rust build, security scanning |
| Cross-language | **Low** | Bridge is well-designed, just needs CI integration |

### Version Update Summary

| Dependency | Current | Latest | Action |
|------------|---------|--------|--------|
| Tauri | 1.x | 2.x | Upgrade |
| React (desktop) | 18.x | 19.x | Align with web |
| Zustand (desktop) | 4.x | 5.x | Align with web |
| Docker Compose | 3.9 | (no version key) | Remove version field |
| Python | 3.12 | 3.13 | Consider upgrading |
| Flutter | 3.24.0 (CI) | 3.32+ | Update |

---

## Architecture Diagram (Tech Stack)

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                           │
├──────────────┬──────────────────┬───────────────────────────────┤
│  Flutter App │   Next.js Web    │      Tauri Desktop            │
│  (Dart)      │   (TypeScript)   │      (Rust + TypeScript)      │
│  Riverpod    │   Zustand        │      Zustand                  │
│  fl_chart    │   lightweight-   │      React + Vite             │
│              │   charts         │                               │
└──────┬───────┴────────┬─────────┴──────────┬────────────────────┘
       │                │                    │
       │    REST + WebSocket (JSON)          │
       │                │                    │
┌──────┴────────────────┴────────────────────┴────────────────────┐
│                     BACKEND LAYER (Python)                       │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI + Uvicorn                                              │
│  ├── REST routes (/api/v1/*)                                    │
│  ├── WebSocket (/ws)                                            │
│  └── Health (/health)                                           │
├─────────────────────────────────────────────────────────────────┤
│  LangGraph Orchestrator                                         │
│  ├── News Agent → Strategy Agent → Risk Agent                   │
│  ├── Human-in-the-loop checkpoint                               │
│  ├── Execution Agent → Reflection Agent                         │
│  └── 16-step Strategy Pipeline (parallelizable)                 │
├─────────────────────────────────────────────────────────────────┤
│  Core Services                                                  │
│  ├── Broker Connectors (CCXT, MT5)                              │
│  ├── Event Bus (Redis Streams)                                  │
│  ├── Risk Governor / Circuit Breaker                            │
│  ├── Market Data Pipeline                                       │
│  └── Security / Auth / Audit                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │   Rust Core (PyO3)  │
              │   ├── Tick Processor│
              │   ├── Indicators    │
              │   ├── Signal Engine │
              │   ├── Order Book    │
              │   ├── Risk Calc     │
              │   └── Backtest Eng  │
              └──────────┬──────────┘
                         │
┌────────────────────────┴────────────────────────────────────────┐
│                     DATA LAYER                                  │
├─────────────────────────────────────────────────────────────────┤
│  TimescaleDB (PostgreSQL 16)    │  Redis 7                      │
│  ├── Market data (time-series)  │  ├── Event streams            │
│  ├── Trade history              │  ├── Cache                    │
│  ├── Portfolio state            │  └── Pub/Sub                  │
│  └── Alembic migrations         │                               │
└─────────────────────────────────────────────────────────────────┘
```

---

*End of Tech Stack Review*
