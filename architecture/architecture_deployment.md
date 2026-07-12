# Alpha Stack — Deployment Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/research_scalability.md`](../research/research_scalability.md) — Scalability research and 5-phase scaling roadmap
> **Status:** Architecture Complete

---

> **Author:** Deployment Architect
> **Date:** 2026-07-11
> **Status:** Architecture Design — Pre-Implementation
> **Dependencies:** `architecture_broker.md`, `architecture_data.md`, `architecture_database.md`, `architecture_ui_desktop.md`, `architecture_ui_web.md`, `research_scalability.md`, `research_multi_platform.md`, `research_desktop_app_architecture.md`, `research_web_app.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Docker Architecture](#2-docker-architecture)
3. [CI/CD Pipeline (GitHub Actions)](#3-cicd-pipeline-github-actions)
4. [VPS Deployment](#4-vps-deployment)
5. [Auto-Update Mechanism](#5-auto-update-mechanism)
6. [Monitoring Stack](#6-monitoring-stack)
7. [Logging Architecture](#7-logging-architecture)
8. [Backup Automation](#8-backup-automation)
9. [Disaster Recovery Procedures](#9-disaster-recovery-procedures)
10. [Scaling: Single VPS to Multi-Region](#10-scaling-single-vps-to-multi-region)
11. [Security Hardening](#11-security-hardening)
12. [Cost Analysis by Phase](#12-cost-analysis-by-phase)
13. [Implementation Roadmap](#13-implementation-roadmap)

---

## 1. Executive Summary

Alpha Stack's deployment architecture is designed to start at **$0/month** on a local machine and scale incrementally to a **multi-region, multi-VPS** setup as capital and user base grow. The core principle: **infrastructure scales with capital, not ahead of it.**

### Deployment Phases at a Glance

| Phase | Capital | Infrastructure | Monthly Cost | Deployment |
|-------|---------|---------------|-------------|------------|
| **1: Local** | $7–$50 | Developer laptop/desktop | $0 | Docker Compose locally |
| **2: Single VPS** | $50–$1K | 1 VPS (Hetzner CX21) | $5–10 | Docker Compose on VPS |
| **3: Split VPS** | $1K–$10K | 2 VPS (app + DB) | $20–40 | Docker Compose + managed DB |
| **4: Professional** | $10K–$100K | 3+ VPS + managed services | $100–300 | Docker Swarm or K3s |
| **5: Multi-Region** | $100K+ | Multi-region cluster | $500+ | Kubernetes + CDN |

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Container runtime | Docker + Docker Compose (Phase 1–3), K3s/K8s (Phase 4+) | Simple → scalable progression |
| CI/CD | GitHub Actions | Free for public repos, excellent matrix builds, native Tauri support |
| VPS providers | Hetzner (primary), DigitalOcean (fallback) | Hetzner: best price/performance in EU; DO: better US presence |
| Monitoring | Prometheus + Grafana | Industry standard, free, extensive exporters |
| Logging | Loki + Promtail (→ Grafana) | Lightweight, integrates with Grafana stack, no Elasticsearch overhead |
| Backup | pg_dump + WAL archiving → pgBackRest | Simple → professional progression |
| Auto-update | Tauri updater (desktop), CDN deploy (web), OTA (mobile) | Platform-native mechanisms |
| Secrets | Docker secrets (Phase 1–3), Vault (Phase 4+) | Progressive complexity |

---

## 2. Docker Architecture

### 2.1 Container Inventory

Alpha Stack is composed of the following containers:

| Container | Image Base | Purpose | Ports | Resources (min) |
|-----------|-----------|---------|-------|-----------------|
| `core-api` | `python:3.11-slim` | REST API, WebSocket server, auth | 8000 | 0.5 CPU, 256MB |
| `trading-engine` | `python:3.11-slim` | Signal processing, order management, broker connectors | — | 1 CPU, 512MB |
| `market-data` | `python:3.11-slim` | Data ingestion, normalization, Redis/DB writes | — | 0.5 CPU, 256MB |
| `ai-inference` | `python:3.11-slim` + PyTorch CPU | AI model inference (SMC, regime, macro) | 8001 | 2 CPU, 1GB |
| `web-companion` | `node:20-alpine` | Next.js web dashboard (static + SSR) | 3000 | 0.25 CPU, 128MB |
| `postgres` | `postgres:16` | Primary database (OLTP + TimescaleDB) | 5432 | 0.5 CPU, 512MB |
| `redis` | `redis:7-alpine` | Hot cache, pub/sub, streams | 6379 | 0.25 CPU, 128MB |
| `prometheus` | `prom/prometheus:v2.53` | Metrics collection | 9090 | 0.25 CPU, 128MB |
| `grafana` | `grafana/grafana:11.1` | Monitoring dashboards | 3001 | 0.25 CPU, 128MB |
| `loki` | `grafana/loki:3.0` | Log aggregation | 3100 | 0.25 CPU, 256MB |
| `promtail` | `grafana/promtail:3.0` | Log collection agent | — | 0.1 CPU, 64MB |
| `nginx` | `nginx:1.27-alpine` | Reverse proxy, TLS termination, static files | 80, 443 | 0.1 CPU, 64MB |
| `mt5-bridge` | `python:3.11-slim` | MT5 WebSocket bridge (Linux/Wine or Windows) | 9224 | 0.5 CPU, 256MB |

### 2.2 Docker Compose — Phase 1 (Local Development)

```yaml
# docker-compose.yml — Local development
version: "3.9"

x-common: &common
  restart: unless-stopped
  logging:
    driver: json-file
    options:
      max-size: "10m"
      max-file: "3"

services:
  # ─── Database Layer ──────────────────────────────────────────
  postgres:
    <<: *common
    image: timescale/timescaledb:latest-pg16
    container_name: as-postgres
    environment:
      POSTGRES_DB: alphastack
      POSTGRES_USER: alphastack
      POSTGRES_PASSWORD: ${DB_PASSWORD:-alphastack_dev}
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts/db/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U alphastack"]
      interval: 10s
      timeout: 5s
      retries: 5
    shm_size: 256mb

  redis:
    <<: *common
    image: redis:7-alpine
    container_name: as-redis
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --save 900 1
      --save 300 10
      --save 60 10000
      --appendonly yes
      --appendfsync everysec
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # ─── Application Layer ──────────────────────────────────────
  core-api:
    <<: *common
    build:
      context: ./services/core-api
      dockerfile: Dockerfile
    container_name: as-core-api
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      DATABASE_URL: postgresql://alphastack:${DB_PASSWORD:-alphastack_dev}@postgres:5432/alphastack
      REDIS_URL: redis://redis:6379/0
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      ENVIRONMENT: development
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./services/core-api/src:/app/src
      - ./config:/app/config:ro

  trading-engine:
    <<: *common
    build:
      context: ./services/trading-engine
      dockerfile: Dockerfile
    container_name: as-trading-engine
    environment:
      DATABASE_URL: postgresql://alphastack:${DB_PASSWORD:-alphastack_dev}@postgres:5432/alphastack
      REDIS_URL: redis://redis:6379/0
      MT5_BRIDGE_URL: ws://mt5-bridge:9224
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./config:/app/config:ro

  market-data:
    <<: *common
    build:
      context: ./services/market-data
      dockerfile: Dockerfile
    container_name: as-market-data
    environment:
      DATABASE_URL: postgresql://alphastack:${DB_PASSWORD:-alphastack_dev}@postgres:5432/alphastack
      REDIS_URL: redis://redis:6379/0
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  ai-inference:
    <<: *common
    build:
      context: ./services/ai-inference
      dockerfile: Dockerfile
    container_name: as-ai-inference
    ports:
      - "127.0.0.1:8001:8001"
    environment:
      REDIS_URL: redis://redis:6379/0
      MODEL_DIR: /app/models
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./models:/app/models:ro
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G

  # ─── Web Companion ──────────────────────────────────────────
  web-companion:
    <<: *common
    build:
      context: ./apps/web-companion
      dockerfile: Dockerfile
    container_name: as-web-companion
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
      NEXT_PUBLIC_WS_URL: ws://localhost:8000/ws
    depends_on:
      core-api:
        condition: service_started

  # ─── MT5 Bridge ─────────────────────────────────────────────
  mt5-bridge:
    <<: *common
    build:
      context: ./services/mt5-bridge
      dockerfile: Dockerfile
    container_name: as-mt5-bridge
    ports:
      - "127.0.0.1:9224:9224"
    environment:
      MT5_LOGIN: ${MT5_LOGIN}
      MT5_PASSWORD: ${MT5_PASSWORD}
      MT5_SERVER: ${MT5_SERVER:-FXPesa-Live}
      MT5_PATH: ${MT5_PATH:-/opt/mt5/terminal64.exe}
    volumes:
      - mt5-data:/opt/mt5
    profiles:
      - mt5  # Only start with --profile mt5

  # ─── Monitoring Stack ───────────────────────────────────────
  prometheus:
    <<: *common
    image: prom/prometheus:v2.53.0
    container_name: as-prometheus
    ports:
      - "127.0.0.1:9090:9090"
    volumes:
      - ./config/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./config/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro
      - prometheus-data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=30d"
      - "--storage.tsdb.retention.size=5GB"
    profiles:
      - monitoring

  grafana:
    <<: *common
    image: grafana/grafana:11.1.0
    container_name: as-grafana
    ports:
      - "127.0.0.1:3001:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./config/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./config/grafana/datasources:/etc/grafana/provisioning/datasources:ro
    depends_on:
      - prometheus
    profiles:
      - monitoring

  loki:
    <<: *common
    image: grafana/loki:3.0.0
    container_name: as-loki
    ports:
      - "127.0.0.1:3100:3100"
    volumes:
      - ./config/loki/loki-config.yml:/etc/loki/local-config.yaml:ro
      - loki-data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    profiles:
      - monitoring

  promtail:
    <<: *common
    image: grafana/promtail:3.0.0
    container_name: as-promtail
    volumes:
      - ./config/promtail/promtail-config.yml:/etc/promtail/config.yml:ro
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    command: -config.file=/etc/promtail/config.yml
    depends_on:
      - loki
    profiles:
      - monitoring

  # ─── Reverse Proxy ──────────────────────────────────────────
  nginx:
    <<: *common
    image: nginx:1.27-alpine
    container_name: as-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./config/nginx/ssl:/etc/nginx/ssl:ro
      - web-static:/usr/share/nginx/html:ro
    depends_on:
      - core-api
      - web-companion
    profiles:
      - production

volumes:
  pgdata:
  redis-data:
  mt5-data:
  prometheus-data:
  grafana-data:
  loki-data:
  web-static:

networks:
  default:
    name: alphastack
    driver: bridge
```

### 2.3 Docker Compose — Phase 2 (Production VPS)

The production overlay adds:
- Resource limits per container
- Health checks on all services
- Nginx reverse proxy with TLS
- Monitoring stack enabled
- Log aggregation enabled

```yaml
# docker-compose.prod.yml — Production overlay
# Usage: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
version: "3.9"

services:
  core-api:
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
        reservations:
          cpus: "0.25"
          memory: 128M
    restart: always

  trading-engine:
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G
        reservations:
          cpus: "0.5"
          memory: 256M
    restart: always

  market-data:
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
    restart: always

  postgres:
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "0.5"
          memory: 512M
    shm_size: 512mb

  redis:
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M

  # Enable monitoring in production
  prometheus:
    profiles: []  # Remove profile restriction
  grafana:
    profiles: []
  loki:
    profiles: []
  promtail:
    profiles: []
  nginx:
    profiles: []  # Enable reverse proxy
```

### 2.4 Docker Networking

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Network: alphastack                     │
│                    Bridge driver, 172.20.0.0/16                   │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ nginx    │───▶│ core-api │───▶│ postgres │    │ redis    │  │
│  │ :80/443  │    │ :8000    │    │ :5432    │    │ :6379    │  │
│  └──────────┘    └────┬─────┘    └──────────┘    └──────────┘  │
│       │               │              ▲                ▲         │
│       │               ▼              │                │         │
│       │         ┌──────────┐         │                │         │
│       │         │ trading- │─────────┘────────────────┘         │
│       │         │ engine   │                                    │
│       │         └──────────┘                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                   │
│  │ web-     │    │ market-  │    │ ai-      │                   │
│  │ companion│    │ data     │    │ inference│                   │
│  │ :3000    │    │          │    │ :8001    │                   │
│  └──────────┘    └──────────┘    └──────────┘                   │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │prometheus│    │ grafana  │    │ loki     │    │promtail  │  │
│  │ :9090    │    │ :3001    │    │ :3100    │    │          │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                                  │
│  ┌──────────┐                                                   │
│  │ mt5-     │  (optional, --profile mt5)                        │
│  │ bridge   │                                                   │
│  │ :9224    │                                                   │
│  └──────────┘                                                   │
└─────────────────────────────────────────────────────────────────┘

External access:
  Internet → nginx:443 (TLS) → core-api:8000 / web-companion:3000
  Localhost only: postgres:5432, redis:6379, prometheus:9090, grafana:3001
```

**Network security rules:**
- All database/cache ports bind to `127.0.0.1` on the host (never exposed to internet)
- Only `nginx` exposes ports 80/443 to the internet
- Internal services communicate over the Docker bridge network
- No inter-container communication except through defined dependencies

### 2.5 Dockerfile Templates

```dockerfile
# services/core-api/Dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Python deps (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY src/ ./src/
COPY config/ ./config/

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Non-root user
RUN useradd -m -s /bin/bash alphastack
USER alphastack

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

```dockerfile
# services/ai-inference/Dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# PyTorch CPU-only (much smaller than GPU version)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

COPY src/ ./src/
COPY models/ ./models/

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

RUN useradd -m -s /bin/bash alphastack
USER alphastack

EXPOSE 8001

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### 2.6 Volume Strategy

| Volume | Purpose | Backup? | Size Estimate |
|--------|---------|---------|---------------|
| `pgdata` | PostgreSQL data files | ✅ Critical | 6GB (Phase 1) → 220GB (Phase 3) |
| `redis-data` | Redis AOF + RDB snapshots | ⚠️ Reconstructable | 256MB max |
| `mt5-data` | MT5 terminal files | ❌ Reinstallable | 500MB |
| `prometheus-data` | Metrics time-series | ❌ 30-day retention | 5GB |
| `grafana-data` | Dashboard configs | ✅ Easy to recreate | 100MB |
| `loki-data` | Log chunks | ❌ 30-day retention | 10GB |
| `web-static` | Built web companion files | ❌ Rebuild from source | 50MB |

---

## 3. CI/CD Pipeline (GitHub Actions)

### 3.1 Pipeline Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CI/CD PIPELINE                                 │
│                                                                       │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐             │
│  │  Lint   │──▶│  Test   │──▶│  Build  │──▶│ Deploy  │             │
│  │ & Check │   │         │   │         │   │         │             │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘             │
│                                                                       │
│  Triggers:                                                            │
│  • Push to main → full pipeline → deploy to staging                  │
│  • Push tag v*  → full pipeline → build release → deploy to prod     │
│  • PR           → lint + test only (no deploy)                       │
│  • Schedule     → nightly integration tests                          │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 Main CI Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_PREFIX: ${{ github.repository }}

jobs:
  # ─── Lint & Type Check ─────────────────────────────────────
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: |
          pip install ruff mypy
          pip install -r requirements-dev.txt

      - name: Ruff lint
        run: ruff check .

      - name: Ruff format check
        run: ruff format --check .

      - name: Type check
        run: mypy services/ --ignore-missing-imports

  # ─── Unit & Integration Tests ──────────────────────────────
  test:
    runs-on: ubuntu-latest
    needs: lint
    services:
      postgres:
        image: timescale/timescaledb:latest-pg16
        env:
          POSTGRES_DB: alphastack_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd="pg_isready -U test"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd="redis-cli ping"
          --health-interval=10s
          --health-timeout=3s
          --health-retries=5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Run migrations
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/alphastack_test
        run: alembic upgrade head

      - name: Run tests
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/alphastack_test
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest services/ -v --tb=short --cov=services --cov-report=xml \
            --junitxml=test-results.xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
          token: ${{ secrets.CODECOV_TOKEN }}

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-results
          path: test-results.xml

  # ─── Build Docker Images ───────────────────────────────────
  build-images:
    runs-on: ubuntu-latest
    needs: test
    if: github.event_name == 'push'
    strategy:
      matrix:
        service:
          - core-api
          - trading-engine
          - market-data
          - ai-inference
          - web-companion
          - mt5-bridge

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.service }}
          tags: |
            type=ref,event=branch
            type=sha,prefix=
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: ./services/${{ matrix.service }}
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ─── Build Desktop App (Tauri) ─────────────────────────────
  build-desktop:
    runs-on: ${{ matrix.os }}
    needs: test
    if: startsWith(github.ref, 'refs/tags/v')
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: ubuntu-22.04
            target: x86_64-unknown-linux-gnu
            artifact_name: alphastack-linux-x86_64
          - os: ubuntu-22.04
            target: aarch64-unknown-linux-gnu
            artifact_name: alphastack-linux-aarch64
          - os: windows-latest
            target: x86_64-pc-windows-msvc
            artifact_name: alphastack-windows-x86_64
          - os: macos-latest
            target: aarch64-apple-darwin
            artifact_name: alphastack-macos-aarch64

    steps:
      - uses: actions/checkout@v4

      - name: Install Rust
        uses: dtolnay/rust-toolchain@stable
        with:
          targets: ${{ matrix.target }}

      - name: Rust cache
        uses: Swatinem/rust-cache@v2
        with:
          workspaces: apps/desktop/src-tauri -> target

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: apps/desktop/package-lock.json

      - name: Install frontend dependencies
        working-directory: apps/desktop
        run: npm ci

      - name: Build Python sidecar
        working-directory: services/sidecar
        run: |
          pip install pyinstaller
          pyinstaller --onefile --name alpha-stack-sidecar \
            --add-data "config:config" main.py

      - name: Build Tauri app
        uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}
          TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY_PASSWORD }}
        with:
          projectPath: apps/desktop
          args: --target ${{ matrix.target }} --bundles appimage deb msi dmg

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact_name }}
          path: apps/desktop/src-tauri/target/${{ matrix.target }}/release/bundle/*

  # ─── Deploy to Staging ─────────────────────────────────────
  deploy-staging:
    runs-on: ubuntu-latest
    needs: [build-images]
    if: github.ref == 'refs/heads/main'
    environment: staging
    concurrency:
      group: deploy-staging
      cancel-in-progress: true

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to staging VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.STAGING_HOST }}
          username: ${{ secrets.STAGING_USER }}
          key: ${{ secrets.STAGING_SSH_KEY }}
          script: |
            cd /opt/alphastack
            export IMAGE_TAG=${{ github.sha }}
            docker compose pull
            docker compose up -d --remove-orphans
            docker compose exec -T core-api alembic upgrade head
            docker compose exec -T core-api python -m src.health_check

      - name: Smoke test
        run: |
          sleep 30
          curl -sf https://staging.alphastack.app/health || exit 1

  # ─── Deploy to Production ──────────────────────────────────
  deploy-production:
    runs-on: ubuntu-latest
    needs: [build-desktop]
    if: startsWith(github.ref, 'refs/tags/v')
    environment: production
    concurrency:
      group: deploy-production
      cancel-in-progress: false

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to production VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.PRODUCTION_HOST }}
          username: ${{ secrets.PRODUCTION_USER }}
          key: ${{ secrets.PRODUCTION_SSH_KEY }}
          script: |
            cd /opt/alphastack
            export IMAGE_TAG=${GITHUB_REF_NAME}
            docker compose pull
            docker compose up -d --remove-orphans
            docker compose exec -T core-api alembic upgrade head

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
          files: |
            apps/desktop/src-tauri/target/*/release/bundle/**/*.AppImage
            apps/desktop/src-tauri/target/*/release/bundle/**/*.deb
            apps/desktop/src-tauri/target/*/release/bundle/**/*.msi
            apps/desktop/src-tauri/target/*/release/bundle/**/*.dmg
```

### 3.3 Nightly Integration Tests

```yaml
# .github/workflows/nightly.yml
name: Nightly Integration Tests

on:
  schedule:
    - cron: "0 3 * * *"  # 03:00 UTC daily

jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: timescale/timescaledb:latest-pg16
        env:
          POSTGRES_DB: alphastack_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Run full integration suite
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/alphastack_test
          REDIS_URL: redis://localhost:6379/0
          BINANCE_TESTNET: ${{ secrets.BINANCE_TESTNET_KEY }}
        run: |
          pytest tests/integration/ -v --tb=long \
            -m "not requires_live_broker"

      - name: Notify on failure
        if: failure()
        uses: rtCamp/action-slack-notify@v2
        env:
          SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}
          SLACK_TITLE: "Nightly Integration Tests Failed"
          SLACK_COLOR: danger
```

### 3.4 Release Pipeline

```yaml
# .github/workflows/release-desktop.yml
name: Desktop Release

on:
  release:
    types: [published]

jobs:
  update-manifest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate update manifest
        run: |
          # Generate latest.json for Tauri updater
          python scripts/generate-update-manifest.py \
            --version ${{ github.event.release.tag_name }} \
            --assets "${{ github.event.release.assets }}" \
            --output latest.json

      - name: Upload manifest to CDN
        run: |
          # Deploy to releases.alphastack.app
          aws s3 cp latest.json s3://alphastack-releases/latest.json \
            --cache-control "no-cache"
```

---

## 4. VPS Deployment

### 4.1 VPS Provider Comparison

| Provider | Plan | vCPU | RAM | Disk | Bandwidth | Price/mo | Location |
|----------|------|------|-----|------|-----------|----------|----------|
| **Hetzner CX22** | Cloud | 2 | 4GB | 40GB SSD | 20TB | **€4.49** | EU (Falkenstein, Helsinki) |
| **Hetzner CX32** | Cloud | 4 | 8GB | 80GB SSD | 20TB | **€8.49** | EU |
| **DigitalOcean** | Basic | 2 | 4GB | 80GB SSD | 4TB | **$24** | US, EU, SG |
| **DigitalOcean** | Basic | 4 | 8GB | 160GB SSD | 5TB | **$48** | US, EU, SG |
| **Vultr** | Cloud | 2 | 4GB | 80GB SSD | 4TB | **$24** | Global |
| **AWS Lightsail** | — | 2 | 4GB | 80GB SSD | 4TB | **$20** | Global |

**Recommendation:**
- **Phase 2 (single VPS):** Hetzner CX22 — €4.49/mo, best value in the industry
- **Phase 3 (split):** Hetzner CX32 (app) + CX22 (DB) — ~€13/mo
- **Phase 4 (professional):** Hetzner CPX31 (4 ARM vCPU, 8GB, €15.59) for compute-heavy services
- **US latency required:** DigitalOcean or Vultr

### 4.2 VPS Provisioning Script

```bash
#!/bin/bash
# scripts/provision-vps.sh
# Usage: curl -fsSL https://raw.githubusercontent.com/alphastack/main/scripts/provision-vps.sh | bash
set -euo pipefail

echo "=== Alpha Stack VPS Provisioning ==="
echo "Target: Ubuntu 22.04 LTS / 24.04 LTS"
echo ""

# ─── System Updates ────────────────────────────────────────────
echo "[1/8] Updating system packages..."
apt-get update && apt-get upgrade -y
apt-get install -y \
    curl wget git unzip \
    ufw fail2ban \
    ca-certificates gnupg lsb-release \
    htop iotop ncdu \
    jq

# ─── Docker Installation ──────────────────────────────────────
echo "[2/8] Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker "$SUDO_USER" 2>/dev/null || true
fi

# Docker Compose plugin (v2)
docker compose version

# ─── Firewall ─────────────────────────────────────────────────
echo "[3/8] Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment "SSH"
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"
ufw --force enable

# ─── Fail2Ban ─────────────────────────────────────────────────
echo "[4/8] Configuring Fail2Ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF
systemctl enable fail2ban
systemctl restart fail2ban

# ─── Create Application User ─────────────────────────────────
echo "[5/8] Creating alphastack user..."
if ! id "alphastack" &>/dev/null; then
    useradd -m -s /bin/bash -G docker alphastack
    mkdir -p /home/alphastack/.ssh
    cp /root/.ssh/authorized_keys /home/alphastack/.ssh/ 2>/dev/null || true
    chown -R alphastack:alphastack /home/alphastack/.ssh
    chmod 700 /home/alphastack/.ssh
fi

# ─── Application Directory ────────────────────────────────────
echo "[6/8] Setting up application directory..."
mkdir -p /opt/alphastack/{config,backups,logs,models}
chown -R alphastack:alphastack /opt/alphastack

# ─── Clone Repository ─────────────────────────────────────────
echo "[7/8] Cloning Alpha Stack repository..."
if [ ! -d /opt/alphastack/.git ]; then
    git clone https://github.com/alphastack/alphastack.git /opt/alphastack
    chown -R alphastack:alphastack /opt/alphastack
fi

# ─── System Tuning ────────────────────────────────────────────
echo "[8/8] Applying system tuning..."
cat >> /etc/sysctl.conf << 'EOF'

# Alpha Stack tuning
vm.swappiness = 10
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
fs.file-max = 2097152
EOF
sysctl -p

# Increase file descriptor limits
cat >> /etc/security/limits.conf << 'EOF'
alphastack soft nofile 65536
alphastack hard nofile 65536
EOF

echo ""
echo "=== Provisioning Complete ==="
echo "Next steps:"
echo "  1. Copy .env file: scp .env alphastack@$(hostname -I | awk '{print $1}'):/opt/alphastack/"
echo "  2. Start services: ssh alphastack@$(hostname -I | awk '{print $1}') 'cd /opt/alphastack && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d'"
echo "  3. Run migrations: docker compose exec core-api alembic upgrade head"
echo "  4. Configure DNS: Point your domain to $(hostname -I | awk '{print $1}')"
```

### 4.3 SSL/TLS with Let's Encrypt

```bash
# scripts/setup-ssl.sh
#!/bin/bash
set -euo pipefail

DOMAIN="${1:-alphastack.app}"
EMAIL="${2:-admin@alphastack.app}"

# Install certbot
apt-get install -y certbot

# Obtain certificate (standalone mode, nginx must be stopped)
systemctl stop nginx 2>/dev/null || docker compose stop nginx || true
certbot certonly --standalone \
    -d "$DOMAIN" \
    -d "www.$DOMAIN" \
    -d "api.$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive

# Copy certs to nginx config directory
mkdir -p /opt/alphastack/config/nginx/ssl
cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem /opt/alphastack/config/nginx/ssl/
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem /opt/alphastack/config/nginx/ssl/

# Auto-renewal cron
echo "0 3 * * 1 certbot renew --quiet && docker compose restart nginx" | crontab -

# Restart nginx
docker compose start nginx

echo "SSL configured for $DOMAIN"
```

### 4.4 Nginx Configuration

```nginx
# config/nginx/nginx.conf
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format json_combined escape=json
        '{'
            '"time":"$time_iso8601",'
            '"remote_addr":"$remote_addr",'
            '"request":"$request",'
            '"status":$status,'
            '"body_bytes_sent":$body_bytes_sent,'
            '"request_time":$request_time,'
            '"http_referrer":"$http_referer",'
            '"http_user_agent":"$http_user_agent"'
        '}';

    access_log /var/log/nginx/access.log json_combined;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 10M;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 1000;
    gzip_types text/plain text/css application/json application/javascript text/xml;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'nonce-{random}'; style-src 'self' 'unsafe-inline'; connect-src 'self' wss://api.alphastack.app https://api.alphastack.app; img-src 'self' data:; font-src 'self' https://fonts.gstatic.com;" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;

    # Upstream
    upstream core_api {
        server core-api:8000;
        keepalive 32;
    }

    upstream web_companion {
        server web-companion:3000;
        keepalive 16;
    }

    # HTTP → HTTPS redirect
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    # Main HTTPS server
    server {
        listen 443 ssl http2;
        server_name alphastack.app www.alphastack.app;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        # HSTS
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # Web companion (Next.js)
        location / {
            proxy_pass http://web_companion;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # API
        location /api/ {
            limit_req zone=api burst=50 nodelay;
            proxy_pass http://core_api;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # WebSocket
        location /ws/ {
            proxy_pass http://core_api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 86400;
        }

        # Auth endpoints (stricter rate limiting)
        location /api/v1/auth/ {
            limit_req zone=auth burst=3 nodelay;
            proxy_pass http://core_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # Health check
        location /health {
            proxy_pass http://core_api;
            access_log off;
        }
    }

    # API subdomain
    server {
        listen 443 ssl http2;
        server_name api.alphastack.app;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        location / {
            limit_req zone=api burst=100 nodelay;
            proxy_pass http://core_api;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /ws/ {
            proxy_pass http://core_api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_read_timeout 86400;
        }
    }
}
```

### 4.5 Environment Configuration

```bash
# .env.production — Template (never commit actual values)
# ─── Database ─────────────────────────────────────────────────
DB_PASSWORD=<generate-with-openssl-rand-base64-32>
DATABASE_URL=postgresql://alphastack:${DB_PASSWORD}@postgres:5432/alphastack

# ─── Redis ────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ─── Application ──────────────────────────────────────────────
ENVIRONMENT=production
LOG_LEVEL=INFO
SECRET_KEY=<generate-with-openssl-rand-base64-64>
JWT_SECRET=<generate-with-openssl-rand-base64-32>

# ─── MT5 (optional) ──────────────────────────────────────────
MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=FXPesa-Live

# ─── Monitoring ───────────────────────────────────────────────
GRAFANA_PASSWORD=<strong-password>
SENTRY_DSN=

# ─── Notifications ────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ─── Backup ───────────────────────────────────────────────────
BACKUP_S3_BUCKET=alphastack-backups
BACKUP_S3_REGION=eu-central-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

---

## 5. Auto-Update Mechanism

### 5.1 Desktop App Updates (Tauri)

The desktop app uses Tauri's built-in updater with signature verification.

```
┌──────────────────────────────────────────────────────────────┐
│                DESKTOP AUTO-UPDATE FLOW                        │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐ │
│  │  App     │───▶│  Check   │───▶│ Download │───▶│ Verify │ │
│  │  Start   │    │  Update  │    │  Update  │    │Signature│ │
│  └──────────┘    └──────────┘    └──────────┘    └────┬───┘ │
│       │              │                                  │     │
│       │         Every 6h                           ┌────▼───┐ │
│       │         or on launch                       │Install │ │
│       │                                            │& Restart│ │
│       │                                            └────────┘ │
│       │                                                       │
│       ▼                                                       │
│  ┌──────────┐                                                 │
│  │ Save     │  ← Save trading state before update             │
│  │ State    │                                                 │
│  └──────────┘                                                 │
└──────────────────────────────────────────────────────────────┘
```

**Update manifest endpoint:**
```
GET https://releases.alphastack.app/{{target}}/{{arch}}/{{current_version}}
```

**Response:**
```json
{
  "version": "1.2.3",
  "notes": "Bug fixes and performance improvements",
  "pub_date": "2026-07-11T12:00:00Z",
  "platforms": {
    "linux-x86_64": {
      "signature": "dW50cnVzdGVkIGNvbW1lbnQ6...",
      "url": "https://releases.alphastack.app/alphastack_1.2.3_amd64.AppImage.tar.gz"
    },
    "windows-x86_64": {
      "signature": "...",
      "url": "https://releases.alphastack.app/alphastack_1.2.3_x64-setup.nsis.zip"
    },
    "darwin-aarch64": {
      "signature": "...",
      "url": "https://releases.alphastack.app/alphastack_1.2.3_aarch64.app.tar.gz"
    }
  }
}
```

**Tauri updater configuration:**
```json
// apps/desktop/src-tauri/tauri.conf.json
{
  "updater": {
    "active": true,
    "endpoints": [
      "https://releases.alphastack.app/{{target}}/{{arch}}/{{current_version}}"
    ],
    "dialog": true,
    "pubkey": "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIGtleQp...",
    "windows": {
      "installMode": "passive"
    }
  }
}
```

**Update safety rules:**
1. Never update while open positions exist (check before downloading)
2. Save all trading state to SQLite before applying update
3. Verify binary signature before installation
4. Offer "Update Later" option — never force-update
5. Rollback capability: keep previous version binary for 7 days

### 5.2 Web Companion Updates

The web companion deploys independently via CDN. No user action required.

```
┌──────────────────────────────────────────────────────────────┐
│                WEB UPDATE FLOW                                │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐ │
│  │  Push    │───▶│  CI/CD   │───▶│  Build   │───▶│ Deploy │ │
│  │  to main │    │ Pipeline │    │  Static  │    │ to CDN │ │
│  └──────────┘    └──────────┘    └──────────┘    └────┬───┘ │
│                                                       │     │
│  ┌──────────┐    ┌──────────┐                         │     │
│  │  User   │◀───│  Service │◀────────────────────────┘     │
│  │  Browser│    │  Worker  │  (cache invalidation)          │
│  └──────────┘    └──────────┘                               │
│       │                                                     │
│       ▼                                                     │
│  New version loaded on next page navigation                 │
│  (stale-while-revalidate strategy)                          │
└──────────────────────────────────────────────────────────────┘
```

**Deployment options (self-hosted):**

| Method | Setup | CDN | Cost |
|--------|-------|-----|------|
| **Nginx static** | Build Next.js → `out/` → copy to nginx | Self-hosted | $0 (included in VPS) |
| **Cloudflare Pages** | Git push → auto-build | Global CDN | Free tier |
| **Vercel** | Git push → auto-build | Global CDN | Free for hobby |
| **Docker** | Build image → deploy container | Self-hosted via nginx | $0 |

**Recommendation for Phase 2:** Self-hosted nginx (zero extra cost, full control).
**Recommendation for Phase 4+:** Cloudflare Pages (global CDN, DDoS protection, free).

### 5.3 Mobile App Updates

| Platform | Mechanism | User Action | Rollback |
|----------|-----------|-------------|----------|
| **Android** | Google Play auto-update | Automatic (if enabled) | Uninstall & sideload old APK |
| **iOS** | App Store auto-update | Automatic (if enabled) | TestFlight for beta |
| **Direct APK** | In-app update check | Download & install prompt | Keep previous APK |

**In-app update flow (React Native):**
```typescript
// Check for updates on app launch
const checkForUpdate = async () => {
  const currentVersion = DeviceInfo.getVersion();
  const response = await fetch('https://api.alphastack.app/v1/app/version');
  const { latestVersion, minVersion, downloadUrl } = await response.json();

  if (semver.lt(currentVersion, minVersion)) {
    // Force update — critical security fix
    showForceUpdateModal(downloadUrl);
  } else if (semver.lt(currentVersion, latestVersion)) {
    // Optional update
    showOptionalUpdateModal(downloadUrl);
  }
};
```

### 5.4 Backend Service Updates (Zero-Downtime)

For the server-side services, we use rolling updates:

```bash
# scripts/deploy.sh — Zero-downtime deployment
#!/bin/bash
set -euo pipefail

SERVICE="${1:?Usage: deploy.sh <service> <tag>}"
TAG="${2:-latest}"
IMAGE="ghcr.io/alphastack/alphastack/${SERVICE}:${TAG}"

echo "Deploying ${SERVICE}:${TAG}..."

# Pull new image
docker compose pull "$SERVICE"

# Rolling update (one container at a time)
docker compose up -d --no-deps --scale "${SERVICE}=2" "$SERVICE"

# Wait for new container to be healthy
echo "Waiting for health check..."
for i in $(seq 1 30); do
    if docker compose exec -T "$SERVICE" curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "New instance healthy"
        break
    fi
    sleep 2
done

# Scale back to 1 (removes old container)
docker compose up -d --no-deps --scale "${SERVICE}=1" "$SERVICE"

echo "Deployed ${SERVICE}:${TAG} successfully"
```

---

## 6. Monitoring Stack

### 6.1 Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    MONITORING ARCHITECTURE                             │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    METRICS (Prometheus)                        │    │
│  │                                                               │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │    │
│  │  │ core-api │  │ trading- │  │ market-  │  │ ai-      │    │    │
│  │  │ /metrics │  │ engine   │  │ data     │  │ inference│    │    │
│  │  │          │  │ /metrics │  │ /metrics │  │ /metrics │    │    │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │    │
│  │       │              │              │              │          │    │
│  │       └──────────────┴──────────────┴──────────────┘          │    │
│  │                          │                                    │    │
│  │                   ┌──────▼──────┐                             │    │
│  │                   │ Prometheus  │                             │    │
│  │                   │  :9090      │                             │    │
│  │                   └──────┬──────┘                             │    │
│  └──────────────────────────┼───────────────────────────────────┘    │
│                             │                                         │
│  ┌──────────────────────────┼───────────────────────────────────┐    │
│  │                    LOGS (Loki)                                │    │
│  │                          │                                    │    │
│  │  ┌──────────┐  ┌────────▼────────┐  ┌──────────┐            │    │
│  │  │Promtail  │──▶│     Loki        │  │  Grafana │            │    │
│  │  │(collect) │  │   :3100         │  │  :3001   │            │    │
│  │  └──────────┘  └─────────────────┘  └────┬─────┘            │    │
│  └───────────────────────────────────────────┼──────────────────┘    │
│                                               │                       │
│  ┌────────────────────────────────────────────▼──────────────────┐   │
│  │                    ALERTING                                    │   │
│  │                                                               │   │
│  │  Prometheus Alertmanager → Telegram / Slack / Email / PagerDuty│  │
│  └───────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 Prometheus Configuration

```yaml
# config/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

scrape_configs:
  # ─── Application Services ────────────────────────────────────
  - job_name: core-api
    static_configs:
      - targets: ["core-api:8000"]
    metrics_path: /metrics
    scrape_interval: 10s

  - job_name: trading-engine
    static_configs:
      - targets: ["trading-engine:8002"]
    metrics_path: /metrics

  - job_name: market-data
    static_configs:
      - targets: ["market-data:8003"]
    metrics_path: /metrics

  - job_name: ai-inference
    static_configs:
      - targets: ["ai-inference:8001"]
    metrics_path: /metrics

  # ─── Infrastructure ──────────────────────────────────────────
  - job_name: postgres
    static_configs:
      - targets: ["postgres-exporter:9187"]

  - job_name: redis
    static_configs:
      - targets: ["redis-exporter:9121"]

  - job_name: node
    static_configs:
      - targets: ["node-exporter:9100"]

  - job_name: nginx
    static_configs:
      - targets: ["nginx-exporter:9113"]

  # ─── Blackbox Monitoring ────────────────────────────────────
  - job_name: blackbox-http
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - https://alphastack.app/health
          - https://api.alphastack.app/health
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
```

### 6.3 Alert Rules

```yaml
# config/prometheus/alerts.yml
groups:
  # ─── Application Alerts ─────────────────────────────────────
  - name: application
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.job }} is down"
          description: "{{ $labels.job }} has been down for more than 1 minute."

      - alert: HighErrorRate
        expr: |
          rate(http_requests_total{status=~"5.."}[5m])
          / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on {{ $labels.job }}"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 5%)"

      - alert: HighLatency
        expr: |
          histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency on {{ $labels.job }}"
          description: "P95 latency is {{ $value }}s (threshold: 2s)"

  # ─── Trading Alerts ─────────────────────────────────────────
  - name: trading
    rules:
      - alert: BrokerDisconnected
        expr: broker_connection_status != 1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Broker {{ $labels.broker_id }} disconnected"
          description: "Broker connection has been down for more than 2 minutes."

      - alert: TradingHalted
        expr: trading_engine_state == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Trading engine halted"
          description: "The trading engine is not running."

      - alert: HighDrawdown
        expr: account_drawdown_pct > 10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High drawdown detected"
          description: "Account drawdown is {{ $value }}% (threshold: 10%)"

      - alert: MarginWarning
        expr: account_margin_utilization_pct > 70
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Margin utilization high"
          description: "Margin utilization is {{ $value }}% (threshold: 70%)"

      - alert: OrderRejectionSpike
        expr: rate(orders_rejected_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Spike in order rejections"
          description: "Order rejection rate is {{ $value }}/s"

  # ─── Infrastructure Alerts ──────────────────────────────────
  - name: infrastructure
    rules:
      - alert: HighCPU
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage on {{ $labels.instance }}"
          description: "CPU usage is {{ $value }}%"

      - alert: HighMemory
        expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }}%"

      - alert: DiskSpaceLow
        expr: (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Disk space low"
          description: "Disk usage is {{ $value }}%"

      - alert: DiskSpaceCritical
        expr: (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 > 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Disk space critically low"
          description: "Disk usage is {{ $value }}%"

      - alert: PostgreSQLDown
        expr: pg_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL is down"

      - alert: RedisDown
        expr: redis_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis is down"

      - alert: HighPostgresConnections
        expr: pg_stat_activity_count > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High PostgreSQL connection count"
          description: "{{ $value }} active connections"

  # ─── Data Pipeline Alerts ───────────────────────────────────
  - name: data_pipeline
    rules:
      - alert: DataIngestionStale
        expr: time() - market_data_last_update_timestamp > 30
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Market data ingestion stale"
          description: "No data received for {{ $labels.symbol }} for {{ $value }}s"

      - alert: StreamConsumerLag
        expr: redis_stream_consumer_lag > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Stream consumer lag high"
          description: "{{ $labels.consumer }} lagging by {{ $value }} messages"
```

### 6.4 Grafana Dashboard Layout

```
┌──────────────────────────────────────────────────────────────┐
│  ALPHA STACK — SYSTEM OVERVIEW                                │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│  CPU         │  Memory      │  Disk        │  Network        │
│  [gauge]     │  [gauge]     │  [gauge]     │  [graph]        │
├──────────────┴──────────────┴──────────────┴─────────────────┤
│  Service Health                                               │
│  core-api: 🟢  trading-engine: 🟢  market-data: 🟢          │
│  ai-inference: 🟢  postgres: 🟢  redis: 🟢                  │
├──────────────────────────────────────────────────────────────┤
│  Trading Metrics                                              │
│  ┌──────────────┬──────────────┬──────────────┬────────────┐ │
│  │ Orders/min   │ Fill Rate    │ Broker       │ Drawdown   │ │
│  │ [graph]      │ [gauge]      │ Latency      │ [gauge]    │ │
│  │              │              │ [graph]      │            │ │
│  └──────────────┴──────────────┴──────────────┴────────────┘ │
├──────────────────────────────────────────────────────────────┤
│  Data Pipeline                                                │
│  ┌──────────────┬──────────────┬──────────────┬────────────┐ │
│  │ Ticks/sec    │ Ingestion    │ Stream       │ DB Write   │ │
│  │ [graph]      │ Latency      │ Lag          │ Rate       │ │
│  │              │ [graph]      │ [graph]      │ [graph]    │ │
│  └──────────────┴──────────────┴──────────────┴────────────┘ │
├──────────────────────────────────────────────────────────────┤
│  Recent Alerts                                                │
│  [table: time, alert, severity, status]                       │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  ALPHA STACK — TRADING PERFORMANCE                            │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│  Equity      │  Daily P&L   │  Win Rate    │  Sharpe Ratio  │
│  Curve       │  Heatmap     │  by Strategy │  [gauge]       │
│  [graph]     │  [heatmap]   │  [bar]       │                │
├──────────────┴──────────────┴──────────────┴─────────────────┤
│  Open Positions                                               │
│  [table: symbol, side, size, entry, current, P&L, duration]  │
├──────────────────────────────────────────────────────────────┤
│  Signal Agent Performance                                     │
│  [table: agent, accuracy, signals, avg_confidence, P&L]       │
└──────────────────────────────────────────────────────────────┘
```

### 6.5 Application Metrics (Custom)

Each Python service exports Prometheus metrics:

```python
# services/core-api/src/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info

# HTTP metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'path'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Trading metrics
orders_total = Counter(
    'orders_total',
    'Total orders placed',
    ['symbol', 'side', 'status', 'broker_id']
)

orders_rejected_total = Counter(
    'orders_rejected_total',
    'Total rejected orders',
    ['symbol', 'reason']
)

broker_connection_status = Gauge(
    'broker_connection_status',
    'Broker connection status (1=connected, 0=disconnected)',
    ['broker_id']
)

account_balance = Gauge(
    'account_balance',
    'Account balance in USD',
    ['account_id']
)

account_drawdown_pct = Gauge(
    'account_drawdown_pct',
    'Current drawdown percentage',
    ['account_id']
)

account_margin_utilization_pct = Gauge(
    'account_margin_utilization_pct',
    'Margin utilization percentage',
    ['account_id']
)

# Data pipeline metrics
market_data_last_update_timestamp = Gauge(
    'market_data_last_update_timestamp',
    'Timestamp of last market data update',
    ['symbol', 'source']
)

redis_stream_consumer_lag = Gauge(
    'redis_stream_consumer_lag',
    'Redis stream consumer lag in messages',
    ['stream', 'consumer']
)

# AI inference metrics
ai_inference_duration_seconds = Histogram(
    'ai_inference_duration_seconds',
    'AI model inference duration',
    ['model_name'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

ai_signals_generated_total = Counter(
    'ai_signals_generated_total',
    'Total AI signals generated',
    ['model_name', 'symbol', 'direction']
)
```

---

## 7. Logging Architecture

### 7.1 Structured Logging Format

All services emit structured JSON logs to stdout (Docker captures these).

```python
# services/core-api/src/logging_config.py
import structlog
import logging
import sys

def setup_logging(level: str = "INFO"):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
```

**Log output example:**
```json
{
  "event": "order_placed",
  "level": "info",
  "timestamp": "2026-07-11T13:45:23.123456Z",
  "logger": "trading.engine",
  "order_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "symbol": "EUR/USD",
  "side": "buy",
  "quantity": 0.1,
  "price": 1.085,
  "broker_id": "fxpesa_mt5",
  "latency_ms": 45,
  "strategy_id": "momentum_v1",
  "request_id": "req-xyz123"
}
```

### 7.2 Log Levels & Categories

| Level | Usage | Examples |
|-------|-------|---------|
| `DEBUG` | Detailed diagnostic | Tick processing, indicator values, WS messages |
| `INFO` | Normal operations | Order placed, signal generated, broker connected |
| `WARNING` | Recoverable issues | Reconnection, rate limit hit, spread filter rejected |
| `ERROR` | Failures requiring attention | Broker error, DB connection lost, model inference failed |
| `CRITICAL` | System-threatening | Trading halted, data corruption, all brokers down |

### 7.3 Loki Configuration

```yaml
# config/loki/loki-config.yml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: "2024-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h  # 7 days
  max_query_length: 721h  # 30 days
  ingestion_rate_mb: 10
  ingestion_burst_size_mb: 20

compactor:
  working_directory: /loki/compactor
  compaction_interval: 10m
  retention_enabled: true
  retention_delete_delay: 2h
  retention_delete_worker_count: 150

table_manager:
  retention_deletes_enabled: true
  retention_period: 720h  # 30 days
```

### 7.4 Promtail Configuration

```yaml
# config/promtail/promtail-config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  # Docker container logs
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
        filters:
          - name: label
            values: ["logging=promtail"]
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'
      - source_labels: ['__meta_docker_container_label_logging_group']
        target_label: 'group'
    pipeline_stages:
      - json:
          expressions:
            level: level
            event: event
            service: logger
      - labels:
          level:
          event:
          service:

  # Nginx access logs
  - job_name: nginx
    static_configs:
      - targets:
          - localhost
        labels:
          job: nginx
          __path__: /var/log/nginx/access.log
    pipeline_stages:
      - json:
          expressions:
            status: status
            request_time: request_time
            request: request
      - labels:
          status:

  # System logs
  - job_name: system
    static_configs:
      - targets:
          - localhost
        labels:
          job: syslog
          __path__: /var/log/syslog
```

### 7.5 Log Retention & Rotation

| Log Source | Retention | Rotation |
|------------|-----------|----------|
| Docker container logs | 7 days (3 × 10MB files per container) | Docker json-file driver |
| Nginx access logs | 30 days | logrotate, daily |
| Nginx error logs | 30 days | logrotate, daily |
| System logs | 14 days | journald vacuum |
| Loki stored logs | 30 days | Loki compactor retention |
| Application audit logs | 1 year (in PostgreSQL) | TimescaleDB retention policy |

---

## 8. Backup Automation

### 8.1 Backup Strategy Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    BACKUP ARCHITECTURE                         │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐ │
│  │PostgreSQL│───▶│ pg_dump  │───▶│ Encrypt  │───▶│Upload  │ │
│  │ (daily)  │    │ + WAL    │    │ (GPG)    │    │(S3/B2) │ │
│  └──────────┘    └──────────┘    └──────────┘    └────────┘ │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐ │
│  │ Redis    │───▶│  RDB     │───▶│ Copy     │───▶│Upload  │ │
│  │ (daily)  │    │  Snapshot│    │          │    │(S3/B2) │ │
│  └──────────┘    └──────────┘    └──────────┘    └────────┘ │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐ │
│  │ Config   │───▶│  Git     │───▶│ Encrypt  │───▶│Upload  │ │
│  │ Files    │    │  Bundle  │    │          │    │(S3/B2) │ │
│  └──────────┘    └──────────┘    └──────────┘    └────────┘ │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐ │
│  │ AI       │───▶│  Copy    │───▶│ Encrypt  │───▶│Upload  │ │
│  │ Models   │    │          │    │          │    │(S3/B2) │ │
│  └──────────┘    └──────────┘    └──────────┘    └────────┘ │
│                                                               │
│  Schedule:  Daily at 03:00 UTC                                │
│  Retention: 7 daily, 4 weekly, 3 monthly                      │
│  Storage:   Local + Backblaze B2 (cheaper than S3)            │
│  Encryption: AES-256 (GPG symmetric)                          │
└──────────────────────────────────────────────────────────────┘
```

### 8.2 Backup Script

```bash
#!/bin/bash
# scripts/backup.sh
# Cron: 0 3 * * * /opt/alphastack/scripts/backup.sh >> /var/log/alphastack-backup.log 2>&1
set -euo pipefail

BACKUP_ROOT="/opt/alphastack/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAILY=7
RETENTION_WEEKLY=4
RETENTION_MONTHLY=3
GPG_PASSPHRASE="${BACKUP_GPG_PASSPHRASE}"
S3_BUCKET="${BACKUP_S3_BUCKET:-alphastack-backups}"

log() { echo "[$(date -Iseconds)] $*"; }

# ─── PostgreSQL Backup ────────────────────────────────────────
log "Starting PostgreSQL backup..."

PG_BACKUP_DIR="${BACKUP_ROOT}/postgres"
mkdir -p "$PG_BACKUP_DIR"

# Full dump (compressed, custom format)
docker compose exec -T postgres pg_dump \
    -U alphastack \
    -Fc \
    -Z9 \
    --verbose \
    alphastack > "${PG_BACKUP_DIR}/alphastack_${DATE}.dump" 2>/dev/null

# Verify dump integrity
if ! docker compose exec -T postgres pg_restore --list \
    "${PG_BACKUP_DIR}/alphastack_${DATE}.dump" > /dev/null 2>&1; then
    log "ERROR: PostgreSQL backup verification failed!"
    exit 1
fi

PG_SIZE=$(du -h "${PG_BACKUP_DIR}/alphastack_${DATE}.dump" | cut -f1)
log "PostgreSQL backup: ${PG_SIZE}"

# ─── Redis Backup ─────────────────────────────────────────────
log "Starting Redis backup..."

REDIS_BACKUP_DIR="${BACKUP_ROOT}/redis"
mkdir -p "$REDIS_BACKUP_DIR"

# Trigger BGSAVE and copy RDB
docker compose exec -T redis redis-cli BGSAVE
sleep 5  # Wait for background save
docker compose cp as-redis:/data/dump.rdb \
    "${REDIS_BACKUP_DIR}/redis_${DATE}.rdb"

log "Redis backup completed"

# ─── Configuration Backup ─────────────────────────────────────
log "Starting configuration backup..."

CONFIG_BACKUP_DIR="${BACKUP_ROOT}/config"
mkdir -p "$CONFIG_BACKUP_DIR"

tar -czf "${CONFIG_BACKUP_DIR}/config_${DATE}.tar.gz" \
    -C /opt/alphastack \
    config/ \
    docker-compose.yml \
    docker-compose.prod.yml \
    .env.production \
    scripts/ \
    2>/dev/null || true

log "Configuration backup completed"

# ─── AI Models Backup ─────────────────────────────────────────
log "Starting AI models backup..."

MODELS_BACKUP_DIR="${BACKUP_ROOT}/models"
mkdir -p "$MODELS_BACKUP_DIR"

if [ -d /opt/alphastack/models ] && [ "$(ls -A /opt/alphastack/models)" ]; then
    tar -czf "${MODELS_BACKUP_DIR}/models_${DATE}.tar.gz" \
        -C /opt/alphastack models/
    log "AI models backup completed"
else
    log "No AI models to backup"
fi

# ─── Encrypt All Backups ──────────────────────────────────────
log "Encrypting backups..."

ENCRYPTED_DIR="${BACKUP_ROOT}/encrypted"
mkdir -p "$ENCRYPTED_DIR"

for file in "${PG_BACKUP_DIR}/alphastack_${DATE}.dump" \
            "${REDIS_BACKUP_DIR}/redis_${DATE}.rdb" \
            "${CONFIG_BACKUP_DIR}/config_${DATE}.tar.gz" \
            "${MODELS_BACKUP_DIR}/models_${DATE}.tar.gz"; do
    if [ -f "$file" ]; then
        gpg --batch --yes --passphrase "$GPG_PASSPHRASE" \
            --symmetric --cipher-algo AES256 \
            --output "${ENCRYPTED_DIR}/$(basename "$file").gpg" \
            "$file"
        log "Encrypted: $(basename "$file")"
    fi
done

# ─── Upload to Remote Storage ─────────────────────────────────
log "Uploading to remote storage..."

# Backblaze B2 (cheaper than S3 for storage)
if command -v b2 &>/dev/null; then
    b2 sync --noProgress "${ENCRYPTED_DIR}" \
        "b2://${S3_BUCKET}/backups/${DATE}/"
    log "Uploaded to Backblaze B2"
elif command -v aws &>/dev/null; then
    aws s3 sync "${ENCRYPTED_DIR}" \
        "s3://${S3_BUCKET}/backups/${DATE}/" \
        --storage-class STANDARD_IA
    log "Uploaded to S3"
else
    log "WARNING: No remote upload tool configured"
fi

# ─── Cleanup Old Backups ──────────────────────────────────────
log "Cleaning up old backups..."

# Keep daily backups for 7 days
find "${BACKUP_ROOT}" -name "*.dump" -mtime +${RETENTION_DAILY} -delete
find "${BACKUP_ROOT}" -name "*.rdb" -mtime +${RETENTION_DAILY} -delete
find "${BACKUP_ROOT}" -name "*.tar.gz" -mtime +${RETENTION_DAILY} -delete
find "${BACKUP_ROOT}/encrypted" -name "*.gpg" -mtime +${RETENTION_DAILY} -delete

# Weekly backup (keep Sunday's backup for 4 weeks)
if [ "$(date +%u)" = "7" ]; then
    WEEKLY_DIR="${BACKUP_ROOT}/weekly"
    mkdir -p "$WEEKLY_DIR"
    cp "${ENCRYPTED_DIR}/alphastack_${DATE}.dump.gpg" \
        "${WEEKLY_DIR}/alphastack_weekly_$(date +%Y%W).dump.gpg"
    find "$WEEKLY_DIR" -mtime +$((RETENTION_WEEKLY * 7)) -delete
fi

# Monthly backup (keep 1st of month for 3 months)
if [ "$(date +%d)" = "01" ]; then
    MONTHLY_DIR="${BACKUP_ROOT}/monthly"
    mkdir -p "$MONTHLY_DIR"
    cp "${ENCRYPTED_DIR}/alphastack_${DATE}.dump.gpg" \
        "${MONTHLY_DIR}/alphastack_monthly_$(date +%Y%m).dump.gpg"
    find "$MONTHLY_DIR" -mtime +$((RETENTION_MONTHLY * 30)) -delete
fi

# ─── Summary ──────────────────────────────────────────────────
TOTAL_SIZE=$(du -sh "${BACKUP_ROOT}" | cut -f1)
log "=== Backup Complete ==="
log "Total backup size: ${TOTAL_SIZE}"
log "Files:"
ls -lh "${ENCRYPTED_DIR}/"*_${DATE}* 2>/dev/null || true

# ─── Verify Remote ────────────────────────────────────────────
if command -v b2 &>/dev/null; then
    REMOTE_COUNT=$(b2 ls --recursive "${S3_BUCKET}" "backups/${DATE}/" | wc -l)
    log "Remote files: ${REMOTE_COUNT}"
fi
```

### 8.3 Backup Verification (Monthly)

```bash
#!/bin/bash
# scripts/verify-backup.sh
# Cron: 0 4 1 * * /opt/alphastack/scripts/verify-backup.sh
set -euo pipefail

log() { echo "[$(date -Iseconds)] $*"; }

# Find latest backup
LATEST=$(ls -t /opt/alphastack/backups/postgres/*.dump 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
    log "ERROR: No backup found!"
    exit 1
fi

log "Verifying backup: ${LATEST}"

# Test restore to temporary database
docker compose exec -T postgres createdb -U alphastack alphastack_verify 2>/dev/null || true
docker compose exec -T postgres pg_restore \
    -U alphastack \
    -d alphastack_verify \
    --no-owner \
    --no-privileges \
    "$LATEST"

# Run integrity checks
TABLE_COUNT=$(docker compose exec -T postgres psql -U alphastack -d alphastack_verify \
    -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")

log "Restored tables: ${TABLE_COUNT}"

if [ "$TABLE_COUNT" -lt 5 ]; then
    log "ERROR: Too few tables restored! Backup may be corrupt."
    exit 1
fi

# Check TimescaleDB hypertables
HYPERTABLE_COUNT=$(docker compose exec -T postgres psql -U alphastack -d alphastack_verify \
    -t -c "SELECT count(*) FROM timescaledb_information.hypertables;" 2>/dev/null || echo "0")
log "Hypertables: ${HYPERTABLE_COUNT}"

# Cleanup
docker compose exec -T postgres dropdb -U alphastack alphastack_verify

log "=== Backup verification PASSED ==="
```

### 8.4 Backup Monitoring

```yaml
# Add to prometheus alerts
- alert: BackupFailed
  expr: time() - backup_last_success_timestamp > 86400 * 2
  for: 1h
  labels:
    severity: critical
  annotations:
    summary: "Backup has not run in 2+ days"
    description: "Last successful backup was {{ $value }} seconds ago"

- alert: BackupSizeAnomaly
  expr: |
    abs(backup_size_bytes - backup_size_bytes offset 1d)
    / backup_size_bytes offset 1d > 0.5
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Backup size changed by >50%"
    description: "Backup size anomaly detected — possible data growth or corruption"
```

---

## 9. Disaster Recovery Procedures

### 9.1 Risk Matrix

| Scenario | Probability | Impact | RTO | RPO | Prevention |
|----------|-------------|--------|-----|-----|------------|
| Accidental DELETE/UPDATE | Medium | High | < 1h | < 24h | Daily backups, WAL archiving |
| Database corruption | Low | Critical | < 2h | < 1h | WAL archiving, checksum verification |
| VPS disk failure | Low | Critical | < 4h | < 24h | External backups, VPS snapshots |
| VPS provider outage | Low | High | < 8h | < 24h | Multi-provider strategy (Phase 4+) |
| Ransomware/security breach | Low | Critical | < 8h | < 24h | Encrypted backups, immutable backups |
| Redis data loss | Medium | Low | < 5min | 0 | Rebuild from PostgreSQL + broker APIs |
| Trading engine crash | Medium | Medium | < 2min | 0 | Auto-restart, state in PostgreSQL |
| All brokers disconnected | Low | High | < 5min | 0 | Circuit breaker, halt trading |

### 9.2 Recovery Procedures

#### 9.2.1 Database Recovery (Accidental Data Loss)

```bash
# RTO: < 1 hour | RPO: < 24 hours (last daily backup)

# Step 1: Stop all services that write to PostgreSQL
docker compose stop trading-engine core-api market-data

# Step 2: Restore from latest backup
LATEST_BACKUP="/opt/alphastack/backups/postgres/alphastack_YYYYMMDD_HHMMSS.dump"

# Drop and recreate database
docker compose exec -T postgres dropdb -U alphastack alphastack
docker compose exec -T postgres createdb -U alphastack alphastack

# Restore
docker compose exec -T postgres pg_restore \
    -U alphastack \
    -d alphastack \
    --no-owner \
    --no-privileges \
    --verbose \
    "$LATEST_BACKUP"

# Step 3: If WAL archiving is enabled, replay WALs for point-in-time recovery
# docker compose exec -T postgres pg_wal_replay

# Step 4: Rebuild Redis state from PostgreSQL
docker compose exec -T core-api python -m src.scripts.rebuild_redis_state

# Step 5: Reconcile positions with broker
docker compose exec -T trading-engine python -m src.scripts.reconcile_positions

# Step 6: Restart services
docker compose start trading-engine core-api market-data

# Step 7: Verify
docker compose exec -T core-api curl -sf http://localhost:8000/health
```

#### 9.2.2 Full Server Recovery

```bash
# RTO: < 8 hours | RPO: < 24 hours
# On a new VPS:

# Step 1: Provision new VPS
curl -fsSL https://raw.githubusercontent.com/alphastack/main/scripts/provision-vps.sh | bash

# Step 2: Clone repository
cd /opt/alphastack
git clone https://github.com/alphastack/alphastack.git .

# Step 3: Restore configuration
# Download encrypted config backup from remote storage
b2 download-file-by-name alphastack-backups "backups/YYYYMMDD_HHMMSS/config_YYYYMMDD_HHMMSS.tar.gz.gpg" /tmp/config.tar.gz.gpg
gpg --decrypt --passphrase "$GPG_PASSPHRASE" /tmp/config.tar.gz.gpg > /tmp/config.tar.gz
tar -xzf /tmp/config.tar.gz -C /opt/alphastack/

# Step 4: Start database and restore
docker compose up -d postgres redis
sleep 10

# Download and restore PostgreSQL backup
b2 download-file-by-name alphastack-backups "backups/YYYYMMDD_HHMMSS/alphastack_YYYYMMDD_HHMMSS.dump.gpg" /tmp/db.dump.gpg
gpg --decrypt --passphrase "$GPG_PASSPHRASE" /tmp/db.dump.gpg > /tmp/db.dump
docker compose exec -T postgres pg_restore -U alphastack -d alphastack /tmp/db.dump

# Step 5: Start all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Step 6: Run migrations (in case of version mismatch)
docker compose exec -T core-api alembic upgrade head

# Step 7: Verify
docker compose exec -T core-api curl -sf http://localhost:8000/health

# Step 8: Update DNS to point to new server IP
# (depends on DNS provider)

# Step 9: Reconcile with brokers
docker compose exec -T trading-engine python -m src.scripts.reconcile_positions
```

#### 9.2.3 Redis Recovery

```bash
# RTO: < 5 minutes | RPO: 0 (ephemeral data)
# Redis data is reconstructable from PostgreSQL and broker APIs

# Step 1: If RDB file exists, try restoring
docker compose stop redis
docker compose cp /opt/alphastack/backups/redis/latest.rdb as-redis:/data/dump.rdb
docker compose start redis

# Step 2: If RDB is corrupt or missing, rebuild from PostgreSQL
docker compose exec -T core-api python -m src.scripts.rebuild_redis_state
# This script:
# 1. Loads all open positions from PostgreSQL
# 2. Fetches current prices from broker APIs
# 3. Rebuilds all Redis keys (tick:*, position:*, account:*, etc.)
# 4. Re-publishes current state to Pub/Sub channels
```

#### 9.2.4 Trading Engine Recovery

```bash
# RTO: < 2 minutes | RPO: 0

# The trading engine is stateless — all state is in PostgreSQL + Redis
# If it crashes, Docker auto-restarts it (restart: always)

# Manual restart if needed:
docker compose restart trading-engine

# After restart, the engine:
# 1. Reconnects to all brokers
# 2. Loads open positions from PostgreSQL
# 3. Reconciles with broker positions
# 4. Resumes signal processing
```

### 9.3 Disaster Recovery Runbook

```markdown
# DR-001: Complete System Recovery

## Prerequisites
- Access to backup storage (Backblaze B2 / S3)
- GPG passphrase for encrypted backups
- SSH access to new VPS
- Domain DNS management access

## Steps

### 1. Provision New Infrastructure [15 min]
- [ ] Create new VPS (Hetzner/DigitalOcean)
- [ ] Run provisioning script
- [ ] Configure firewall
- [ ] Set up SSH keys

### 2. Restore Application [30 min]
- [ ] Clone repository
- [ ] Download encrypted backups
- [ ] Decrypt and restore configuration
- [ ] Start database and Redis
- [ ] Restore PostgreSQL backup
- [ ] Run migrations

### 3. Start Services [15 min]
- [ ] Start all Docker containers
- [ ] Verify health endpoints
- [ ] Check broker connections
- [ ] Reconcile positions

### 4. Update DNS [5-60 min]
- [ ] Update A record to new IP
- [ ] Wait for DNS propagation
- [ ] Verify SSL certificate (renew if needed)
- [ ] Test external access

### 5. Verify Trading [15 min]
- [ ] Check open positions match broker
- [ ] Verify market data is flowing
- [ ] Test order placement (small test order)
- [ ] Monitor for 30 minutes

### 6. Post-Recovery [30 min]
- [ ] Document incident
- [ ] Review what caused the failure
- [ ] Update runbook if needed
- [ ] Notify stakeholders

## Total Estimated RTO: 2-3 hours
```

---

## 10. Scaling: Single VPS to Multi-Region

### 10.1 Scaling Phases

```
Phase 2: Single VPS                    Phase 3: Split VPS
┌────────────────────────┐             ┌──────────┐  ┌──────────┐
│  All services on one   │             │ App VPS  │  │  DB VPS  │
│  VPS (Hetzner CX22)   │             │ (CX32)   │  │  (CX22)  │
│                        │             │          │  │          │
│  core-api              │             │ core-api │  │ postgres │
│  trading-engine        │             │ trading- │  │ timescale│
│  market-data           │             │ engine   │  │ redis    │
│  ai-inference          │             │ market-  │  │          │
│  web-companion         │             │ data     │  │          │
│  postgres              │             │ ai-      │  │          │
│  redis                 │             │ inference│  │          │
│  nginx                 │             │ web-     │  │          │
│  prometheus            │             │ companion│  │          │
│  grafana               │             │ nginx    │  │          │
│  loki                  │             │ prometh. │  │          │
│  promtail              │             │ grafana  │  │          │
│                        │             │ loki     │  │          │
│  Cost: ~€5/mo          │             │ promtail │  │          │
└────────────────────────┘             │          │  │          │
                                       │ Cost:€13 │  │ Cost:€5  │
                                       └──────────┘  └──────────┘

Phase 4: Professional                  Phase 5: Multi-Region
┌──────────┐  ┌──────────┐            ┌────────────────────────────┐
│ App VPS  │  │  DB VPS  │            │  Region: EU (Frankfurt)    │
│ (CPX31)  │  │  (CX32)  │            │  ┌──────┐ ┌──────┐ ┌────┐│
│          │  │          │            │  │App-1 │ │App-2 │ │DB  ││
│ core-api │  │ postgres │            │  └──────┘ └──────┘ └────┘│
│ (x2)     │  │ timescale│            │                           │
│ trading- │  │ redis    │            │  Region: US (New York)    │
│ engine   │  │ pgbouncer│            │  ┌──────┐ ┌──────┐ ┌────┐│
│ market-  │  │          │            │  │App-1 │ │App-2 │ │DB  ││
│ data     │  └──────────┘            │  └──────┘ └──────┘ └────┘│
│ ai-      │                          │                           │
│ inference│  ┌──────────┐            │  Region: Asia (Singapore) │
│ web-     │  │Monitoring│            │  ┌──────┐ ┌──────┐       │
│ companion│  │ VPS      │            │  │App-1 │ │App-2 │       │
│ nginx    │  │          │            │  └──────┘ └──────┘       │
│          │  │ prometh. │            │                           │
│ Cost: €30│  │ grafana  │            │  Global: Cloudflare CDN   │
└──────────┘  │ loki     │            │  Load Balancer: Hetzner   │
              │ alertmgr │            │  Cost: ~€200/mo           │
              │ Cost: €8 │            └────────────────────────────┘
              └──────────┘
```

### 10.2 Phase 3: Split Application and Database

**Why split:** The database needs different scaling characteristics (more RAM, faster disk) than the application (more CPU for AI inference).

```yaml
# docker-compose.app.yml — Application VPS
version: "3.9"

services:
  core-api:
    build: ./services/core-api
    environment:
      DATABASE_URL: postgresql://alphastack:${DB_PASSWORD}@db.internal:5432/alphastack
      REDIS_URL: redis://db.internal:6379/0
    # ... rest of config

  trading-engine:
    build: ./services/trading-engine
    environment:
      DATABASE_URL: postgresql://alphastack:${DB_PASSWORD}@db.internal:5432/alphastack
      REDIS_URL: redis://db.internal:6379/0

  # ... other app services

  # WireGuard tunnel to DB VPS
  wireguard:
    image: linuxserver/wireguard
    cap_add:
      - NET_ADMIN
    volumes:
      - ./config/wireguard:/config
    sysctls:
      - net.ipv4.conf.all.src_valid_mark=1
```

**Inter-VPS communication:** WireGuard VPN tunnel (encrypted, low latency, free).

### 10.3 Phase 4: Kubernetes (K3s)

When the system needs horizontal scaling, we move to K3s (lightweight Kubernetes).

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-engine
  namespace: alphastack
spec:
  replicas: 1  # Single replica — trading engine is stateful
  selector:
    matchLabels:
      app: trading-engine
  template:
    metadata:
      labels:
        app: trading-engine
    spec:
      containers:
        - name: trading-engine
          image: ghcr.io/alphastack/alphastack/trading-engine:latest
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2000m"
              memory: "1Gi"
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: alphastack-secrets
                  key: database-url
          livenessProbe:
            httpGet:
              path: /health
              port: 8002
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8002
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: core-api
  namespace: alphastack
spec:
  replicas: 2  # Horizontally scalable
  selector:
    matchLabels:
      app: core-api
  template:
    spec:
      containers:
        - name: core-api
          image: ghcr.io/alphastack/alphastack/core-api:latest
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "1000m"
              memory: "512Mi"
```

### 10.4 Phase 5: Multi-Region Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    MULTI-REGION ARCHITECTURE                       │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    Cloudflare (Global)                     │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │    │
│  │  │   CDN    │  │   WAF    │  │   DDoS   │               │    │
│  │  │ (static) │  │ (rules)  │  │ (protect)│               │    │
│  │  └──────────┘  └──────────┘  └──────────┘               │    │
│  └──────────────────────────┬───────────────────────────────┘    │
│                              │                                    │
│              ┌───────────────┼───────────────┐                    │
│              ▼               ▼               ▼                    │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐          │
│  │  EU Region    │ │  US Region    │ │  Asia Region  │          │
│  │  (Frankfurt)  │ │  (New York)   │ │  (Singapore)  │          │
│  │               │ │               │ │               │          │
│  │  ┌─────────┐  │ │  ┌─────────┐  │ │  ┌─────────┐  │          │
│  │  │ K3s     │  │ │  │ K3s     │  │ │  │ K3s     │  │          │
│  │  │ Cluster │  │ │  │ Cluster │  │ │  │ Cluster │  │          │
│  │  │         │  │ │  │         │  │ │  │         │  │          │
│  │  │ App (2) │  │ │  │ App (2) │  │ │  │ App (2) │  │          │
│  │  │ DB      │  │ │  │ DB      │  │ │  │ DB      │  │          │
│  │  │ Redis   │  │ │  │ Redis   │  │ │  │ Redis   │  │          │
│  │  └─────────┘  │ │  └─────────┘  │ │  └─────────┘  │          │
│  └───────────────┘ └───────────────┘ └───────────────┘          │
│                                                                   │
│  Database replication:                                            │
│  EU (primary) ──streaming──▶ US (replica) ──streaming──▶ Asia    │
│                                                                   │
│  Redis: Independent per region (hot data is region-local)         │
│  PostgreSQL: Primary in EU, async replicas in US/Asia             │
│  Trading engine: Runs in ONE region (lowest latency to broker)    │
└──────────────────────────────────────────────────────────────────┘
```

**Multi-region considerations:**
- **Trading engine runs in ONE region** — closest to the broker's servers (EU for FXPesa, US for Interactive Brokers)
- **Web companion replicated** — static files on CDN, API routes proxied to nearest region
- **PostgreSQL** — primary in trading region, async replicas for read-heavy dashboards
- **Redis** — independent per region (hot data is ephemeral, rebuilds on startup)
- **Monitoring** — centralized Grafana in EU, Prometheus scrapes across regions via WireGuard

### 10.5 Scaling Decision Matrix

| Metric | Threshold | Action |
|--------|-----------|--------|
| Single VPS CPU > 70% sustained | Phase 2→3 | Split app and DB onto separate VPS |
| PostgreSQL RAM > 80% | Phase 2→3 | Upgrade DB VPS or split |
| Disk > 80% | Any phase | Add storage, enable compression, archive old data |
| API response time > 500ms | Phase 3→4 | Add API replicas, optimize queries |
| Need zero-downtime deploys | Phase 3→4 | Move to K3s |
| Users in multiple continents | Phase 4→5 | Multi-region deployment |
| Need DDoS protection | Phase 4→5 | Cloudflare in front |
| Need managed database | Phase 4→5 | Hetzner Managed DB or Supabase |

---

## 11. Security Hardening

### 11.1 VPS Security Checklist

```bash
# scripts/security-hardening.sh
#!/bin/bash
set -euo pipefail

echo "=== Alpha Stack Security Hardening ==="

# 1. SSH hardening
cat >> /etc/ssh/sshd_config << 'EOF'
# Alpha Stack SSH hardening
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers alphastack
Protocol 2
X11Forwarding no
EOF
systemctl restart sshd

# 2. Kernel hardening
cat >> /etc/sysctl.conf << 'EOF'
# Security hardening
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.tcp_syncookies = 1
kernel.randomize_va_space = 2
EOF
sysctl -p

# 3. Automatic security updates
apt-get install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

# 4. File permissions
chmod 700 /opt/alphastack/backups
chmod 600 /opt/alphastack/.env.production
chmod 700 /opt/alphastack/config/nginx/ssl

# 5. Docker security
# Run containers as non-root (already in Dockerfiles)
# Limit container capabilities
# No privileged containers

echo "Security hardening complete"
```

### 11.2 Network Security

| Layer | Protection | Implementation |
|-------|-----------|----------------|
| **Edge** | DDoS protection | Cloudflare (Phase 4+) or VPS provider's built-in |
| **Firewall** | Port restriction | UFW: only 22, 80, 443 |
| **Application** | Rate limiting | Nginx `limit_req` on API and auth endpoints |
| **Application** | Input validation | Zod schemas on all inputs |
| **Application** | CORS | Strict same-origin policy |
| **Database** | Network isolation | Bind to localhost, Docker internal network |
| **Secrets** | Encryption at rest | AES-256-GCM for credentials, GPG for backups |
| **Secrets** | Encryption in transit | TLS 1.2+ for all external, WireGuard for inter-VPS |
| **Audit** | Access logging | All API calls logged with IP, user, action |

### 11.3 Secret Management

```yaml
# Docker secrets (Phase 1-3)
# .env.production is the single source of truth
# Never committed to git (in .gitignore)

# Phase 4+: HashiCorp Vault or Infisical
# - Dynamic database credentials
# - Automatic secret rotation
# - Audit logging of secret access
```

---

## 12. Cost Analysis by Phase

### 12.1 Phase 1: Local Development ($0/month)

| Component | Cost | Notes |
|-----------|------|-------|
| VPS | $0 | Running on developer machine |
| Database | $0 | Docker PostgreSQL |
| Redis | $0 | Docker Redis |
| Monitoring | $0 | Optional: local Grafana |
| Domain | $0 | localhost |
| **Total** | **$0** | |

### 12.2 Phase 2: Single VPS (~€5/month)

| Component | Cost | Provider | Notes |
|-----------|------|----------|-------|
| VPS (CX22) | €4.49/mo | Hetzner | 2 vCPU, 4GB RAM, 40GB SSD |
| Domain | ~€10/year | Cloudflare Registrar | ~€0.83/mo |
| SSL | $0 | Let's Encrypt | Free |
| Backblaze B2 | ~$0.50/mo | Backblaze | ~5GB encrypted backups |
| **Total** | **~€5.80/mo** | | |

### 12.3 Phase 3: Split VPS (~€18/month)

| Component | Cost | Provider | Notes |
|-----------|------|----------|-------|
| App VPS (CX32) | €8.49/mo | Hetzner | 4 vCPU, 8GB RAM |
| DB VPS (CX22) | €4.49/mo | Hetzner | 2 vCPU, 4GB RAM, dedicated to DB |
| Domain | ~€0.83/mo | Cloudflare | |
| Backblaze B2 | ~$1/mo | Backblaze | ~20GB backups |
| WireGuard | $0 | — | Free, self-hosted |
| **Total** | **~€15/mo** | | |

### 12.4 Phase 4: Professional (~€60/month)

| Component | Cost | Provider | Notes |
|-----------|------|----------|-------|
| App VPS (CPX31) | €15.59/mo | Hetzner | 4 ARM vCPU, 8GB RAM |
| DB VPS (CX32) | €8.49/mo | Hetzner | 4 vCPU, 8GB RAM |
| Monitoring VPS (CX22) | €4.49/mo | Hetzner | Dedicated monitoring |
| Managed PostgreSQL | €18/mo | Hetzner Cloud | OR self-hosted on VPS |
| Domain | ~€0.83/mo | Cloudflare | |
| Cloudflare (Free) | $0 | Cloudflare | CDN, DDoS basic |
| Backblaze B2 | ~$2/mo | Backblaze | ~50GB backups |
| **Total** | **~€50/mo** | | |

### 12.5 Phase 5: Multi-Region (~€200/month)

| Component | Cost | Provider | Notes |
|-----------|------|----------|-------|
| EU cluster (3 nodes) | €60/mo | Hetzner | CPX31 × 3 |
| US cluster (2 nodes) | $48/mo | DigitalOcean | 4vCPU/8GB × 2 |
| Managed DB (EU) | €30/mo | Hetzner | Primary |
| Cloudflare Pro | $20/mo | Cloudflare | WAF, advanced CDN |
| Backblaze B2 | ~$5/mo | Backblaze | ~100GB backups |
| Domain | ~€0.83/mo | Cloudflare | |
| **Total** | **~€170/mo** | | |

---

## 13. Implementation Roadmap

### Phase 1: Foundation (Week 1)

```
□ Create Docker Compose configuration (development)
□ Write Dockerfiles for all services
□ Set up PostgreSQL + TimescaleDB init script
□ Configure Redis with persistence
□ Create .env template
□ Write provisioning script for VPS
□ Set up GitHub Actions CI (lint + test)
□ Write basic health check endpoints
□ Test: Full stack starts locally with docker compose up
```

### Phase 2: Production VPS (Week 2–3)

```
□ Provision Hetzner CX22 VPS
□ Run provisioning script
□ Set up Let's Encrypt SSL
□ Configure Nginx reverse proxy
□ Create docker-compose.prod.yml overlay
□ Set up daily backup cron job
□ Configure backup encryption and remote upload
□ Set up basic Prometheus + Grafana monitoring
□ Configure alert rules (service down, high CPU, disk)
□ Set up Loki + Promtail for log aggregation
□ Test: Deploy to VPS, verify all services healthy
□ Test: Backup and restore procedure
□ Document: Runbook for common operations
```

### Phase 3: Professional (Week 4–6)

```
□ Split app and DB onto separate VPS
□ Set up WireGuard tunnel between VPS
□ Configure PgBouncer connection pooling
□ Set up WAL archiving for point-in-time recovery
□ Add custom application metrics (trading, data pipeline)
□ Build Grafana dashboards (system overview, trading performance)
□ Set up Telegram/Slack alert notifications
□ Configure structured logging in all services
□ Write backup verification script
□ Set up nightly integration tests
□ Test: Simulate failure scenarios, verify recovery
□ Document: Disaster recovery runbook
```

### Phase 4: Scaling (Week 7+)

```
□ Evaluate K3s for container orchestration
□ Set up Cloudflare for CDN and DDoS protection
□ Implement zero-downtime deployment script
□ Set up desktop auto-update infrastructure (Tauri updater endpoint)
□ Configure web companion deployment pipeline
□ Set up multi-stage Docker builds for smaller images
□ Implement connection pooling optimization
□ Add Prometheus alertmanager for multi-channel alerting
□ Load test: Simulate 50+ concurrent users
□ Security audit: Penetration test, dependency scan
□ Document: Scaling playbook
```

---

## Appendix A: Quick Reference Commands

```bash
# ─── Development ──────────────────────────────────────────────
docker compose up -d                          # Start all services
docker compose up -d --profile mt5           # Start with MT5 bridge
docker compose up -d --profile monitoring    # Start with monitoring
docker compose logs -f trading-engine        # Follow logs
docker compose exec postgres psql -U alphastack  # Database shell
docker compose exec redis redis-cli          # Redis shell

# ─── Production ───────────────────────────────────────────────
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose pull && docker compose up -d  # Update images
docker compose exec core-api alembic upgrade head  # Run migrations

# ─── Backups ──────────────────────────────────────────────────
/opt/alphastack/scripts/backup.sh            # Manual backup
/opt/alphastack/scripts/verify-backup.sh     # Verify latest backup

# ─── Monitoring ───────────────────────────────────────────────
curl -sf http://localhost:9090/-/healthy     # Prometheus health
curl -sf http://localhost:3001/api/health    # Grafana health
curl -sf http://localhost:3100/ready         # Loki health

# ─── Debugging ────────────────────────────────────────────────
docker stats                                 # Container resource usage
docker compose top                           # Process list per container
docker system df                             # Disk usage
ncdu /var/lib/docker                         # Docker disk breakdown
```

---

## Appendix B: Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_PASSWORD` | ✅ | — | PostgreSQL password |
| `DATABASE_URL` | ✅ | — | Full PostgreSQL connection string |
| `REDIS_URL` | ✅ | — | Redis connection string |
| `SECRET_KEY` | ✅ | — | Application secret key (JWT, sessions) |
| `ENVIRONMENT` | ❌ | `development` | `development`, `staging`, `production` |
| `LOG_LEVEL` | ❌ | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `MT5_LOGIN` | ❌ | — | MetaTrader 5 account login |
| `MT5_PASSWORD` | ❌ | — | MetaTrader 5 account password |
| `MT5_SERVER` | ❌ | `FXPesa-Live` | MetaTrader 5 server name |
| `GRAFANA_PASSWORD` | ❌ | `admin` | Grafana admin password |
| `BACKUP_GPG_PASSPHRASE` | ✅ | — | Encryption passphrase for backups |
| `BACKUP_S3_BUCKET` | ❌ | `alphastack-backups` | Remote backup bucket name |
| `SENTRY_DSN` | ❌ | — | Sentry error tracking DSN |
| `TELEGRAM_BOT_TOKEN` | ❌ | — | Telegram bot for alerts |
| `TELEGRAM_CHAT_ID` | ❌ | — | Telegram chat for alerts |

---

*This deployment architecture is designed to grow with Alpha Stack. Start with `docker compose up` on your laptop, deploy to a €5 VPS when you have $50 in capital, and scale to multi-region when the system proves its edge. Infrastructure follows strategy — never the other way around.*

*Generated: 2026-07-11*
*Next review: After Phase 2 deployment*
