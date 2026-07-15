# AlphaStack — Comprehensive Setup & Running Guide

> **Generated:** 2026-07-15 | **Repo Version:** 0.1.0 | **Status:** Implementation Phase

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Prerequisites & System Requirements](#2-prerequisites--system-requirements)
3. [Environment Variables & Configuration](#3-environment-variables--configuration)
4. [Infrastructure Services](#4-infrastructure-services)
5. [Python Backend Setup](#5-python-backend-setup)
6. [Docker Setup (Recommended)](#6-docker-setup-recommended)
7. [Flutter Mobile App Setup](#7-flutter-mobile-app-setup)
8. [Desktop App Setup (Tauri)](#8-desktop-app-setup-tauri)
9. [Web App Setup (Next.js)](#9-web-app-setup-nextjs)
10. [API Keys & Broker Credentials](#10-api-keys--broker-credentials)
11. [Xiaomi AI Model Configuration](#11-xiaomi-ai-model-configuration)
12. [CI/CD Pipelines](#12-cicd-pipelines)
13. [Minimum Viable Setup (MVS)](#13-minimum-viable-setup-mvs)
14. [API Reference](#14-api-reference)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. System Overview

AlphaStack is a multi-agent AI trading system with these major components:

| Component | Tech | Port | Purpose |
|-----------|------|------|---------|
| **Trading Engine** | Python 3.12 | — | Background worker: strategy execution, ML inference |
| **API Server** | FastAPI + Uvicorn | 8000 | REST API, WebSocket, health checks |
| **TimescaleDB** | PostgreSQL 16 + TimescaleDB | 5432 | Time-series storage, trade history |
| **Redis** | Redis 7 | 6379 | Caching, pub/sub, streams, rate limiting |
| **Web Dashboard** | Next.js 15 | 3000 | Browser-based monitoring |
| **Desktop App** | Tauri (Rust + React) | — | Native cross-platform desktop |
| **Mobile App** | Flutter | — | iOS/Android monitoring |
| **Orchestrator** | LangGraph + LangChain | — | Multi-agent pipeline (news→strategy→risk→execution→reflection) |

### Architecture Flow

```
Market Data → News Agent → Strategy Agent (16-step pipeline) → Risk Agent
    → [Human-in-the-loop checkpoint] → Execution Agent → Reflection Agent
```

---

## 2. Prerequisites & System Requirements

### Python Backend
- **Python 3.12+** (required — `requires-python = ">=3.12"`)
- **pip** or **hatch** (build system: hatchling)
- **TA-Lib C library** (for technical analysis — must be compiled from source)

### Infrastructure
- **Docker & Docker Compose** (for TimescaleDB + Redis, or full stack)
- **PostgreSQL 16** with TimescaleDB extension (if not using Docker)
- **Redis 7** (if not using Docker)

### Frontend (optional)
- **Node.js 20+** (for web and desktop apps)
- **Flutter 3.24+** (for mobile app)
- **Rust toolchain** (for Tauri desktop app)

### Hardware
- **Minimum:** 4 GB RAM, 2 CPU cores
- **Recommended:** 8 GB RAM, 4 CPU cores (ML inference is memory-hungry)
- **Disk:** ~2 GB for Docker images + data

---

## 3. Environment Variables & Configuration

### 3.1 Configuration File

Copy the default config and customize:

```bash
cp config/alphastack.yaml config/alphastack.local.yaml
```

The system loads `config/alphastack.yaml` first, then overlays `config/alphastack.local.yaml`.

### 3.2 Environment Variable Override

All config values can be overridden via environment variables. The naming convention is:

```
ALPHASTACK_<SECTION>_<KEY>    (for top-level settings)
DB_<KEY>                       (for database settings)
REDIS_<KEY>                    (for Redis settings)
MT5_<KEY>                      (for MT5 broker settings)
CCXT_<KEY>                     (for crypto exchange settings)
LLM_<KEY>                      (for AI model settings)
FEED_<KEY>                     (for market data feed settings)
RISK_<KEY>                     (for risk management settings)
API_<KEY>                      (for API server settings)
```

### 3.3 Complete Environment Variable Reference

#### Core Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `ALPHASTACK_ENV` | `dev` | Runtime environment: `dev`, `staging`, `prod` |

#### Database (PostgreSQL/TimescaleDB)
| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `5432` | Database port |
| `DB_NAME` | `alphastack` | Database name |
| `DB_USER` | `alphastack` | Database user |
| `DB_PASSWORD` | `alphastack` | Database password (**change in production**) |
| `DB_POOL_SIZE` | `20` | Connection pool size |
| `DB_MAX_OVERFLOW` | `10` | Extra connections beyond pool |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for connection |
| `DB_ECHO` | `false` | Log all SQL (dev only) |

#### Redis
| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database number |
| `REDIS_PASSWORD` | `null` | Redis password (optional) |
| `REDIS_SSL` | `false` | Use TLS |
| `REDIS_POOL_SIZE` | `20` | Connection pool size |

#### MT5 Broker (Forex/CFDs)
| Variable | Default | Description |
|----------|---------|-------------|
| `MT5_LOGIN` | `0` | MT5 account login number |
| `MT5_PASSWORD` | `""` | MT5 password |
| `MT5_SERVER` | `""` | MT5 server (e.g. `FXPesa-Demo`) |
| `MT5_PATH` | `""` | Path to terminal64.exe (auto-detect if empty) |
| `MT5_TIMEOUT` | `60000` | Connection timeout (ms) |

#### CCXT Broker (Crypto)
| Variable | Default | Description |
|----------|---------|-------------|
| `CCXT_EXCHANGE` | `binance` | Exchange name |
| `CCXT_API_KEY` | `""` | Exchange API key |
| `CCXT_SECRET` | `""` | Exchange API secret |
| `CCXT_PASSPHRASE` | `null` | Some exchanges require this |
| `CCXT_SANDBOX` | `false` | Use exchange testnet |

#### LLM / AI
| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_OPENAI_API_KEY` | `null` | OpenAI API key |
| `LLM_ANTHROPIC_API_KEY` | `null` | Anthropic API key |
| `LLM_DEFAULT_MODEL` | `gpt-4o` | Default LLM model |
| `LLM_TEMPERATURE` | `0.1` | Model temperature |
| `LLM_MAX_TOKENS` | `4096` | Max output tokens |

#### Market Data Feeds
| Variable | Default | Description |
|----------|---------|-------------|
| `FEED_POLYGON_API_KEY` | `null` | Polygon.io API key |
| `FEED_ALPHA_VANTAGE_API_KEY` | `null` | Alpha Vantage API key |
| `FEED_FINNHUB_API_KEY` | `null` | Finnhub API key |

#### Risk Management
| Variable | Default | Description |
|----------|---------|-------------|
| `RISK_MAX_DRAWDOWN_PCT` | `15.0` | Max allowed drawdown (%) |
| `RISK_MAX_POSITION_SIZE_PCT` | `5.0` | Max single position as % of equity |
| `RISK_MAX_DAILY_LOSS_PCT` | `3.0` | Max daily loss before halt (%) |
| `RISK_MAX_OPEN_POSITIONS` | `10` | Concurrent open position limit |
| `RISK_MAX_CORRELATION` | `0.7` | Max cross-position correlation |
| `RISK_MAX_LEVERAGE` | `2.0` | Max allowed leverage |
| `RISK_STOP_LOSS_ATR_MULTIPLIER` | `2.0` | Default SL = ATR × multiplier |
| `RISK_RISK_FREE_RATE` | `0.05` | For Sharpe/Sortino calculations |

#### API Server
| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8000` | Listen port |
| `API_WORKERS` | `4` | Uvicorn worker count |
| `API_CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `API_API_PREFIX` | `/api/v1` | URL prefix for all routes |
| `API_DEBUG` | `false` | Enable debug mode |

#### Logging
| Variable | Default | Description |
|----------|---------|-------------|
| `LOGGING_LEVEL` | `INFO` | Log level |
| `LOGGING_JSON_OUTPUT` | `true` | JSON lines output |
| `LOGGING_LOG_DIR` | `logs` | Log file directory |

### 3.4 .env File

The system also reads from a `.env` file in the project root (via `python-dotenv`):

```bash
# .env example
ALPHASTACK_ENV=dev
DB_HOST=localhost
DB_PASSWORD=your_secure_password
REDIS_HOST=localhost
CCXT_API_KEY=your_binance_api_key
CCXT_SECRET=your_binance_secret
LLM_OPENAI_API_KEY=sk-...
FEED_POLYGON_API_KEY=...
```

---

## 4. Infrastructure Services

### 4.1 TimescaleDB (PostgreSQL + TimescaleDB Extension)

TimescaleDB is required for time-series data storage (OHLCV data, trade history, performance metrics).

**Option A: Docker (recommended)**
```bash
docker run -d \
  --name alphastack-timescaledb \
  -p 5432:5432 \
  -e POSTGRES_DB=alphastack \
  -e POSTGRES_USER=alphastack \
  -e POSTGRES_PASSWORD=alphastack \
  -v timescaledb_data:/var/lib/postgresql/data \
  timescale/timescaledb:latest-pg16
```

**Option B: Native install**
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-16
# Add TimescaleDB repo: https://docs.timescale.com/install/latest/
sudo apt-get install timescaledb-2-postgresql-16
sudo systemctl enable postgresql
```

**Database initialization** (handled automatically by the app on first startup):
```python
# In dev mode, tables are created via SQLAlchemy:
from alphastack.core.database import init_db
await init_db()

# In production, use Alembic migrations:
alembic upgrade head
```

### 4.2 Redis

Redis is used for caching, pub/sub messaging, rate limiting, and stream-based data pipelines.

**Option A: Docker**
```bash
docker run -d \
  --name alphastack-redis \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:7-alpine
```

**Option B: Native install**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl enable redis-server
```

**Verify:**
```bash
redis-cli ping
# Expected: PONG
```

### 4.3 Services NOT Currently Required (but referenced in architecture)

| Service | Status | Notes |
|---------|--------|-------|
| **Apache Kafka** | Not in docker-compose | Referenced in architecture docs but not in current code. Redis Streams used instead. |
| **ClickHouse** | Not in docker-compose | Referenced for analytics. TimescaleDB handles current needs. |
| **InfluxDB** | Not in docker-compose | Alternative time-series DB. Not currently integrated. |
| **Prometheus/Grafana** | Not in docker-compose | `prometheus-client` is a dependency. Metrics endpoint available. |

---

## 5. Python Backend Setup

### 5.1 Clone & Install

```bash
git clone https://github.com/ovalentine964/alphastack.git
cd alphastack

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install TA-Lib C library (REQUIRED — Python package needs it)
# Linux:
wget https://github.com/TA-Lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz
tar -xzf ta-lib-0.6.4-src.tar.gz
cd ta-lib-0.6.4
./configure --prefix=/usr/local
make -j$(nproc) && sudo make install
cd .. && rm -rf ta-lib-0.6.4 ta-lib-0.6.4-src.tar.gz
sudo ldconfig

# macOS:
brew install ta-lib

# Install Python dependencies
pip install -e ".[dev]"
```

### 5.2 Key Python Dependencies

From `pyproject.toml`:

| Package | Purpose |
|---------|---------|
| `fastapi` + `uvicorn` | REST API server |
| `sqlalchemy[asyncio]` + `asyncpg` + `psycopg2-binary` | Database ORM |
| `alembic` | Database migrations |
| `redis[hiredis]` | Redis client |
| `ccxt` | Crypto exchange connectivity |
| `MetaTrader5` | MT5 broker connectivity (Windows only) |
| `torch` | PyTorch for ML models |
| `scikit-learn` | ML algorithms |
| `onnxruntime` | Model inference |
| `pandas` + `numpy` | Data manipulation |
| `ta-lib` | Technical analysis indicators |
| `langgraph` + `langchain` | Multi-agent orchestration |
| `prometheus-client` | Metrics |
| `structlog` | Structured logging |
| `pydantic` + `pydantic-settings` | Configuration & validation |

### 5.3 Start the API Server

```bash
# Method 1: Direct uvicorn
uvicorn alphastack.api.rest.app:app --host 0.0.0.0 --port 8000 --reload

# Method 2: Python module (if __main__.py exists)
python -m alphastack.main
```

### 5.4 Start the Trading Engine

```bash
# The trading engine is a background worker
python -m alphastack.engine
```

**Note:** The trading engine runs the multi-agent orchestrator:
1. **News Agent** — Detects high-impact events
2. **Strategy Agent** — Runs the 16-step signal pipeline
3. **Risk Agent** — Evaluates and approves/rejects signals
4. **Execution Agent** — Routes orders to brokers
5. **Reflection Agent** — Post-trade analysis and learning

### 5.5 Run Backtests

```bash
# Synthetic data (500 bars, seed=42)
python scripts/run_backtest.py --bars 500 --seed 42

# Custom data
python scripts/run_backtest.py --data data/EURUSD_1h.csv --balance 50000 --risk 1.5

# Options
python scripts/run_backtest.py --help
```

### 5.6 Run Tests

```bash
# All tests
pytest tests/ -v

# Specific test suite
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/backtest/ -v
pytest tests/security/ -v
pytest tests/performance/ -v

# With coverage
pytest tests/ -v --cov=alphastack --cov-report=term-missing
```

### 5.7 Linting & Type Checking

```bash
# Lint
ruff check src/ tests/
ruff format --check src/ tests/

# Type check
mypy src/alphastack/ --ignore-missing-imports
```

---

## 6. Docker Setup (Recommended)

### 6.1 Full Stack with Docker Compose

```bash
cd alphastack

# Start all services (TimescaleDB + Redis + API)
docker-compose -f infra/docker/docker-compose.yml up -d

# Check status
docker-compose -f infra/docker/docker-compose.yml ps

# View logs
docker-compose -f infra/docker/docker-compose.yml logs -f api
docker-compose -f infra/docker/docker-compose.yml logs -f timescaledb
docker-compose -f infra/docker/docker-compose.yml logs -f redis
```

### 6.2 Docker Compose Services

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| `timescaledb` | `timescale/timescaledb:latest-pg16` | 5432 | Database |
| `redis` | `redis:7-alpine` | 6379 | Cache/streams |
| `api` | Built from `infra/docker/Dockerfile` | 8000 | API server |
| `trading-engine` | Built from `infra/docker/Dockerfile` | — | Background worker |

**Note:** The `trading-engine` service uses a Docker Compose profile:
```bash
# Start with trading engine
docker-compose -f infra/docker/docker-compose.yml --profile engine up -d

# Start without trading engine (API + DB + Redis only)
docker-compose -f infra/docker/docker-compose.yml up -d
```

### 6.3 Docker Build Details

The `Dockerfile` uses a multi-stage build:

1. **Builder stage:** Installs TA-Lib C library, compiles Python dependencies
2. **Runtime stage:** Slim image with only runtime libraries

```bash
# Build image manually
docker build -f infra/docker/Dockerfile -t alphastack:latest .

# Run API server
docker run -p 8000:8000 \
  -e DB_HOST=your-db-host \
  -e REDIS_HOST=your-redis-host \
  alphastack:latest
```

### 6.4 Environment Variables for Docker

Override via docker-compose or `.env` file:

```yaml
# In docker-compose.yml
environment:
  ALPHASTACK_ENV: dev
  DB_HOST: timescaledb
  DB_PORT: 5432
  DB_NAME: alphastack
  DB_USER: alphastack
  DB_PASSWORD: alphastack
  REDIS_HOST: redis
  REDIS_PORT: 6379
  API_HOST: "0.0.0.0"
  API_PORT: 8000
  API_DEBUG: "true"
```

---

## 7. Flutter Mobile App Setup

### 7.1 Prerequisites

- **Flutter SDK 3.24+**
- **Dart SDK** (included with Flutter)
- **Android Studio** or **Xcode** (for building)

### 7.2 Install Flutter

```bash
# macOS
brew install flutter

# Linux (snap)
sudo snap install flutter

# Or manual
git clone https://github.com/flutter/flutter.git -b stable
export PATH="$PATH:$(pwd)/flutter/bin"
```

### 7.3 Build Mobile App

```bash
cd apps/mobile

# Install dependencies
flutter pub get

# Build Android APK
flutter build apk --release
# Output: build/app/outputs/flutter-apk/app-release.apk

# Build iOS (requires Mac + Xcode)
flutter build ios --release
# Open ios/Runner.xcarchive in Xcode
```

### 7.4 Mobile App Dependencies

| Package | Purpose |
|---------|---------|
| `flutter_riverpod` | State management |
| `http` | HTTP client |
| `web_socket_channel` | WebSocket for real-time data |
| `fl_chart` | Charts |
| `local_auth` | Biometric authentication |
| `flutter_secure_storage` | Secure credential storage |
| `firebase_messaging` | Push notifications |
| `google_fonts` | Typography |

### 7.5 Configure API Endpoint

The mobile app connects to the backend API. Configure the endpoint in the app settings or environment:

```
API_BASE_URL=http://your-server:8000/api/v1
```

---

## 8. Desktop App Setup (Tauri)

### 8.1 Prerequisites

- **Node.js 20+**
- **Rust toolchain** (install via `rustup`)
- **Platform-specific dependencies:**

```bash
# Linux
sudo apt-get install libgtk-3-dev libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf

# macOS
brew install openssl

# Windows: Visual Studio Build Tools
```

### 8.2 Build Desktop App

```bash
cd apps/desktop
npm install
npm run tauri build
# Output: src-tauri/target/release/bundle/
#   - Windows: .exe, .msi
#   - macOS: .dmg
#   - Linux: .AppImage, .deb
```

### 8.3 Development Mode

```bash
cd apps/desktop
npm run tauri:dev
```

---

## 9. Web App Setup (Next.js)

### 9.1 Build Web App

```bash
cd apps/web
npm install
npm run build
# Output: .next/ directory

# Development mode
npm run dev
# Available at http://localhost:3000
```

### 9.2 Deploy

The web app can be deployed to:
- **Vercel** (recommended for Next.js)
- **Netlify**
- **Any static host** (after `next build`)
- **Self-hosted** with `next start`

---

## 10. API Keys & Broker Credentials

### 10.1 Crypto Exchange (CCXT)

**Binance (default):**
1. Create account at https://www.binance.com
2. Go to API Management → Create API
3. Enable spot trading permissions
4. Set IP restrictions for security

```bash
CCXT_EXCHANGE=binance
CCXT_API_KEY=your_api_key
CCXT_SECRET=your_secret
CCXT_SANDBOX=false  # true for testnet
```

**Supported exchanges** (via CCXT): Binance, MEXC, Bybit, OKX, Kraken, Coinbase, and 100+ others.

### 10.2 MetaTrader 5 (Forex/CFDs)

**Requirements:**
- MT5 terminal installed (Windows only, or use Wine/VPS)
- Broker account (e.g., FXPesa, IC Markets, Pepperstone)

```bash
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=FXPesa-Demo  # or FXPesa-Live
MT5_PATH=""  # Auto-detect if empty
```

**Note:** MT5 integration requires Windows. For Linux/macOS, use a Windows VPS or Wine.

### 10.3 Market Data Feeds

| Provider | Key | Free Tier | Use Case |
|----------|-----|-----------|----------|
| **Polygon.io** | `FEED_POLYGON_API_KEY` | 5 API calls/min | US stocks, crypto, forex |
| **Alpha Vantage** | `FEED_ALPHA_VANTAGE_API_KEY` | 25 calls/day | Stocks, forex, crypto |
| **Finnhub** | `FEED_FINNHUB_API_KEY` | 60 calls/min | Stocks, news, earnings |

### 10.4 LLM API Keys

| Provider | Key | Use Case |
|----------|-----|----------|
| **OpenAI** | `LLM_OPENAI_API_KEY` | Default LLM for agent reasoning |
| **Anthropic** | `LLM_ANTHROPIC_API_KEY` | Alternative LLM |

---

## 11. Xiaomi AI Model Configuration

### 11.1 Current Setup

The system's agent infrastructure is configured to use **Xiaomi MiMo V2.5 Pro** as the primary AI model. This is configured in the OpenClaw agent config (not in AlphaStack's code directly).

**Model specifications:**
- **Provider:** xiaomi
- **Model ID:** `mimo-v2.5-pro`
- **Context Window:** 1,048,576 tokens (1M)
- **Max Output:** 65,536 tokens
- **Reasoning:** Enabled (medium thinking level)
- **Cost:** Free

### 11.2 How the AI Model Integrates

The AlphaStack codebase uses LLMs through two paths:

**Path 1: Direct LLM calls** (configured in `config/alphastack.yaml`):
```yaml
llm:
  openai_api_key: null      # Set via LLM_OPENAI_API_KEY
  anthropic_api_key: null   # Set via LLM_ANTHROPIC_API_KEY
  default_model: gpt-4o     # Change to your preferred model
  temperature: 0.1
  max_tokens: 4096
```

**Path 2: Multi-agent orchestration** (via LangGraph/LangChain):
The orchestrator in `src/alphastack/agents/orchestrator/graph.py` uses LangChain, which can be configured to use any OpenAI-compatible API endpoint.

### 11.3 Using Xiaomi MiMo as the Backend LLM

To use Xiaomi MiMo V2.5 Pro as the LLM backend for AlphaStack's agents:

1. **Set up the MiMo API endpoint** (via OpenClaw or direct API)
2. **Configure the LLM settings** to point to MiMo:

```bash
# Environment variables
LLM_OPENAI_API_KEY=your_mimo_api_key
LLM_DEFAULT_MODEL=mimo-v2.5-pro
```

Or in `config/alphastack.local.yaml`:
```yaml
llm:
  openai_api_key: "your_mimo_api_key"
  default_model: "mimo-v2.5-pro"
  temperature: 0.1
  max_tokens: 4096
```

3. **For LangChain integration**, configure the OpenAI-compatible base URL:
```python
# In your agent configuration
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="mimo-v2.5-pro",
    base_url="https://your-mimo-api-endpoint/v1",
    api_key="your_key",
    temperature=0.1,
)
```

### 11.4 OpenClaw Agent Config

The OpenClaw agent that manages AlphaStack is configured in `~/.openclaw/openclaw.json`. Key settings:

```json
{
  "models": {
    "providers": {
      "xiaomi": {
        "baseUrl": "https://api.xiaomi.com/v1",
        "apiKey": "your-key",
        "models": [{
          "id": "mimo-v2.5-pro",
          "reasoning": true,
          "contextWindow": 1048576,
          "maxTokens": 65536
        }]
      }
    }
  }
}
```

---

## 12. CI/CD Pipelines

### 12.1 CI Pipeline (`.github/workflows/ci.yml`)

Triggers on push to `main`/`develop` and PRs to `main`:

1. **Python job:** Lint (ruff) → Type check (mypy) → Test (pytest) → Coverage upload
2. **TypeScript job:** Build web/mobile/desktop apps
3. **Docker job:** Build Docker image (no push)

### 12.2 Deploy Pipeline (`.github/workflows/deploy.yml`)

Triggers on version tags (`v*`) or manual dispatch:

1. Build & test
2. Push Docker image to GitHub Container Registry (`ghcr.io`)
3. Deploy to staging (on tag push)
4. Deploy to production (manual dispatch)

**Deploy targets** (currently placeholder):
```bash
# Staging
https://staging.alphastack.dev

# Production
https://alphastack.dev
```

### 12.3 Release Pipeline (`.github/workflows/release.yml`)

Triggers on version tags:

1. Build desktop app (Windows, macOS, Linux)
2. Build mobile app (Android APK)
3. Build web app
4. Create GitHub Release with all artifacts

### 12.4 GitHub Pages (`.github/workflows/pages.yml`)

Deploys `docs/` directory to GitHub Pages on push to `main`.

---

## 13. Minimum Viable Setup (MVS)

### What You Need to Get Running RIGHT NOW

**Goal:** API server responding at `http://localhost:8000/health`

#### Step 1: Infrastructure (2 minutes)

```bash
# Start TimescaleDB + Redis with Docker
docker run -d --name ast-db -p 5432:5432 \
  -e POSTGRES_DB=alphastack -e POSTGRES_USER=alphastack -e POSTGRES_PASSWORD=alphastack \
  timescale/timescaledb:latest-pg16

docker run -d --name ast-redis -p 6379:6379 redis:7-alpine
```

#### Step 2: Python Backend (3 minutes)

```bash
cd alphastack
python3 -m venv venv
source venv/bin/activate

# Install TA-Lib (skip if already installed)
# pip install ta-lib  # or compile from source

# Install dependencies
pip install -e ".[dev]"

# Copy config
cp config/alphastack.yaml config/alphastack.local.yaml
```

#### Step 3: Start API (1 command)

```bash
uvicorn alphastack.api.rest.app:app --host 0.0.0.0 --port 8000 --reload
```

#### Step 4: Verify

```bash
# Health check
curl http://localhost:8000/health
# {"status":"healthy","version":"0.1.0","uptime_seconds":...,"timestamp":"..."}

# API docs
open http://localhost:8000/docs

# System status
curl http://localhost:8000/status

# Config (non-sensitive)
curl http://localhost:8000/config
```

### What Works Without API Keys

| Feature | Works? | Notes |
|---------|--------|-------|
| API server | ✅ | Fully functional |
| Health/status endpoints | ✅ | |
| Trade management (CRUD) | ✅ | In-memory store (demo data) |
| Portfolio/PnL | ✅ | Based on in-memory trades |
| Signal listing | ✅ | Pre-seeded demo signals |
| Auth (login/refresh) | ✅ | Demo user: `admin`/`alphastack` |
| Backtesting | ✅ | Synthetic data |
| Strategy pipeline | ⚠️ | Needs market data |
| Live trading | ❌ | Needs broker API keys |
| AI agent reasoning | ❌ | Needs LLM API key |
| News detection | ❌ | Needs news feed API key |

### What Needs API Keys

To unlock full functionality, configure these (in order of priority):

1. **CCXT (crypto trading):** `CCXT_API_KEY` + `CCXT_SECRET`
2. **LLM (AI reasoning):** `LLM_OPENAI_API_KEY` or Xiaomi MiMo
3. **MT5 (forex trading):** `MT5_LOGIN` + `MT5_PASSWORD` + `MT5_SERVER`
4. **Market data:** `FEED_POLYGON_API_KEY` or `FEED_ALPHA_VANTAGE_API_KEY`
5. **News:** `FEED_FINNHUB_API_KEY` (for news sentiment)

---

## 14. API Reference

### Base URL
```
http://localhost:8000/api/v1
```

### Endpoints

#### System (no prefix)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/status` | System status |
| GET | `/config` | Non-sensitive config |

#### Auth (`/api/v1/auth`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Login (returns JWT) |
| POST | `/auth/refresh` | Refresh token |
| POST | `/auth/logout` | Logout |

**Demo credentials:** `admin` / `alphastack`

#### Trades (`/api/v1/trades`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/trades` | List trades (paginated) |
| POST | `/trades` | Create trade |
| GET | `/trades/{id}` | Get trade detail |
| PUT | `/trades/{id}/close` | Close trade |

#### Portfolio (`/api/v1/portfolio`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/portfolio` | Open positions |
| GET | `/portfolio/pnl` | P&L summary |
| GET | `/portfolio/performance` | Performance metrics |

#### Signals (`/api/v1/signals`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/signals` | Active signals |
| GET | `/signals/history` | Signal history |

### Rate Limiting
- **120 requests per minute** per IP
- Returns `429 Too Many Requests` when exceeded

### Authentication
- JWT-based (HS256)
- Access token: 30 minutes
- Refresh token: 7 days
- **Note:** Current implementation uses in-memory JWT secret (regenerated on restart). Production should use persistent secret.

---

## 15. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'alphastack'` | Run `pip install -e .` from project root |
| `TA-Lib not found` | Install TA-Lib C library first, then `pip install ta-lib` |
| `Connection refused: localhost:5432` | Start TimescaleDB: `docker start ast-db` |
| `Connection refused: localhost:6379` | Start Redis: `docker start ast-redis` |
| `MetaTrader5 import error` | MT5 only works on Windows. Use Docker or skip for crypto-only. |
| `Port 8000 already in use` | Change port: `uvicorn ... --port 8001` or `API_PORT=8001` |
| `torch not found` | PyTorch is large. Install: `pip install torch` (CPU) or `pip install torch --index-url https://download.pytorch.org/whl/cu121` (CUDA) |
| `Docker build fails on TA-Lib` | Ensure internet access during build. The Dockerfile downloads TA-Lib source. |
| `flutter: command not found` | Install Flutter: https://docs.flutter.dev/get-started/install |
| `npm: command not found` | Install Node.js 20+: https://nodejs.org |

### Logs

```bash
# Application logs
tail -f logs/trades.jsonl

# Docker logs
docker-compose -f infra/docker/docker-compose.yml logs -f api

# Structured logging (JSON lines)
# Default: stdout + logs/trades.jsonl
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database (from Docker)
docker exec alphastack-timescaledb pg_isready -U alphastack

# Redis
redis-cli ping
```

---

## Appendix: Project Status

Based on the repository analysis:

| Phase | Status | Details |
|-------|--------|---------|
| Research | ✅ Complete | 55+ research reports |
| Architecture | ✅ Complete | 22+ architecture documents |
| Review Pipeline | ✅ Complete | 47+ review reports |
| Fix Generation | ✅ Complete | 32+ fix reports |
| **Implementation** | 🔄 In Progress | Core code exists, some modules are stubs |

### What's Actually Implemented (Code Exists)

- ✅ FastAPI REST API with all routes
- ✅ Pydantic configuration system
- ✅ Database connection layer (SQLAlchemy async)
- ✅ Redis client with cache/pub/sub/stream helpers
- ✅ Structured logging (structlog)
- ✅ Multi-agent orchestrator (LangGraph)
- ✅ Strategy pipeline (16 steps)
- ✅ Risk management modules
- ✅ Broker connectors (MT5, CCXT)
- ✅ Chain-of-thought reasoning engine
- ✅ Backtest runner
- ✅ Docker build pipeline
- ✅ CI/CD workflows
- ✅ Demo data (trades, signals)

### What Needs Work

- ⚠️ Some agent implementations may be stubs
- ⚠️ In-memory trade store (needs DB persistence)
- ⚠️ JWT secret is ephemeral (regenerated on restart)
- ⚠️ Portfolio current prices are placeholder (`entry * 1.005`)
- ⚠️ Deployment targets are placeholder URLs
- ⚠️ No Alembic migration files found (schema management)
- ⚠️ WebSocket server exists but route registration unclear

---

*This guide was generated by analyzing the full AlphaStack repository. For updates, check the [GitHub repo](https://github.com/ovalentine964/alphastack).*
