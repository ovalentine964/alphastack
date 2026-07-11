# Alpha Stack — Deployment & Installation Final Validation

> **Author:** Deployment & Installation Final Agent  
> **Date:** 2026-07-11  
> **Status:** Final Review — Pre-Implementation  
> **Sources:** `architecture_deployment.md`, `fix_platform_consolidation.md`, `fix_scalability_final.md`, `architecture_ui_desktop.md`

---

## Executive Summary

The Alpha Stack deployment architecture is **well-designed but incomplete**. Docker Compose configurations are thorough, CI/CD pipelines are production-grade, and the VPS provisioning script automates most setup. However, **no one-line install command exists for end users**, the unified server architecture from `fix_platform_consolidation.md` has not been integrated into the deployment docs, and several critical gaps remain between the deployment architecture and the scalability/platform fixes.

**Overall Deployment Readiness: 65%** — Architecture is sound; implementation artifacts (scripts, configs, installers) need to be created.

---

## 1. One-Line Install Command Validation

### Current State: ❌ NOT IMPLEMENTED

No one-line install command exists in any document. The closest artifact is the VPS provisioning script:

```bash
curl -fsSL https://raw.githubusercontent.com/alphastack/main/scripts/provision-vps.sh | bash
```

This is a **server provisioning** script, not a user-facing installer. It installs Docker and system dependencies — it does NOT install or configure Alpha Stack itself.

### What's Needed Per Platform

| Platform | Expected Command | Status | Gap |
|----------|-----------------|--------|-----|
| **Linux (deb/apt)** | `curl -fsSL https://get.alphastack.app \| sh` | ❌ Missing | No install script, no apt repo, no AppImage download wrapper |
| **Linux (AppImage)** | Download + `chmod +x` + run | ❌ Missing | AppImage built in CI but no download page or wrapper |
| **Windows** | Download `.msi` or `.exe` installer | ⚠️ Partial | CI builds `.msi` via Tauri but no download URL or silent install option |
| **macOS** | Download `.dmg` or `brew install alphastack` | ❌ Missing | CI builds `.dmg` but no Homebrew cask, no download page |

### Recommended One-Liner Design

**Linux:**
```bash
curl -fsSL https://get.alphastack.app/install.sh | sh
# Detects distro → downloads AppImage or .deb → installs → launches
```

**macOS:**
```bash
brew install --cask alphastack
# OR
curl -fsSL https://get.alphastack.app/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://get.alphastack.app/install.ps1 | iex
# Downloads .msi → silent install → launches
```

### Verdict: 🔴 CRITICAL — No user-facing install path exists. Must create install scripts + download page + Homebrew cask before any release.

---

## 2. Docker Deployment Validation

### Current State: ✅ COMPREHENSIVE (with gaps)

The Docker architecture is well-designed with:

- **13 containers** defined (core-api, trading-engine, market-data, ai-inference, web-companion, postgres, redis, nginx, prometheus, grafana, loki, promtail, mt5-bridge)
- **Development compose** (`docker-compose.yml`) with profiles for optional services
- **Production overlay** (`docker-compose.prod.yml`) with resource limits, health checks, monitoring enabled
- **Dockerfiles** with multi-stage builds, non-root users, health checks
- **Volume strategy** with clear backup classification
- **Networking** with proper isolation (DB/cache localhost-only, nginx as sole internet entry)

### Gap Analysis

| Issue | Severity | Detail |
|-------|----------|--------|
| **Unified server not integrated** | 🔴 HIGH | `fix_platform_consolidation.md` defines an "Alpha Stack Server" (Rust/Axum) as the single backend. The Docker Compose still uses the old multi-service architecture (core-api + trading-engine + market-data as separate Python services). These need to be reconciled. |
| **No docker-compose for unified server** | 🔴 HIGH | The platform consolidation fix introduces a Rust-based API gateway. No Dockerfile or compose service exists for it. |
| **MT5 Data Proxy missing from compose** | 🟠 MEDIUM | `fix_scalability_final.md` introduces `MT5DataProxy` as a standalone service. Not present in Docker Compose. |
| **Redis Sentinel not in compose** | 🟠 MEDIUM | `fix_scalability_final.md` moves Redis Sentinel to Phase 2. The compose file still uses single Redis. Phase 2 compose needs sentinel config (provided in fix doc). |
| **No `.env.example` file** | 🟠 MEDIUM | `.env.production` template exists in docs but no actual `.env.example` file in repo structure. |
| **Health check endpoints undefined** | 🟠 MEDIUM | Dockerfiles reference `/health` endpoints but no implementation code exists for them. |
| **MT5 bridge Dockerfile missing** | 🟡 LOW | `services/mt5-bridge/Dockerfile` referenced but not provided. Running MT5 via Wine in Docker is non-trivial. |
| **No `docker-compose.sentinel.yml`** | 🟡 LOW | Fix doc provides YAML but it's not integrated as an overlay file. |

### Docker Compose Completeness Matrix

| Service | Dev Compose | Prod Overlay | Dockerfile | Health Check | Resource Limits |
|---------|-------------|-------------|------------|-------------|----------------|
| core-api | ✅ | ✅ | ✅ | ✅ | ✅ |
| trading-engine | ✅ | ✅ | ✅ | ⚠️ referenced | ✅ |
| market-data | ✅ | ✅ | ✅ | ⚠️ referenced | ✅ |
| ai-inference | ✅ | ✅ | ✅ | ✅ | ✅ |
| web-companion | ✅ | ✅ | ✅ | ⚠️ referenced | ❌ |
| postgres | ✅ | ✅ | ❌ (image) | ✅ | ✅ |
| redis | ✅ | ✅ | ❌ (image) | ✅ | ✅ |
| nginx | ✅ | ✅ | ❌ (image) | ❌ | ❌ |
| prometheus | ✅ (profile) | ✅ | ❌ (image) | ❌ | ❌ |
| grafana | ✅ (profile) | ✅ | ❌ (image) | ❌ | ❌ |
| loki | ✅ (profile) | ✅ | ❌ (image) | ❌ | ❌ |
| promtail | ✅ (profile) | ✅ | ❌ (image) | ❌ | ❌ |
| mt5-bridge | ✅ (profile) | ⚠️ | ❌ missing | ❌ | ❌ |
| **Alpha Stack Server (Rust)** | ❌ | ❌ | ❌ | ❌ | ❌ |
| **MT5 Data Proxy** | ❌ | ❌ | ❌ | ❌ | ❌ |

### Verdict: 🟡 GOOD foundation, but needs integration with platform consolidation fixes. The Rust unified server is a new major component with zero deployment artifacts.

---

## 3. VPS Deployment Automation Validation

### Current State: ✅ AUTOMATED (with version conflict)

**Provisioning script** (`scripts/provision-vps.sh`) handles:
- ✅ System package updates
- ✅ Docker installation
- ✅ UFW firewall (22, 80, 443 only)
- ✅ Fail2Ban (SSH brute force protection)
- ✅ Application user creation (`alphastack`)
- ✅ Directory structure (`/opt/alphastack/`)
- ✅ Repository clone
- ✅ System tuning (sysctl, file descriptors)

**SSL setup** (`scripts/setup-ssl.sh`) handles:
- ✅ Let's Encrypt certificate via certbot
- ✅ Auto-renewal cron job
- ✅ Certificate copy to nginx config

**Missing from automation:**
- ❌ DNS configuration (manual step)
- ❌ `.env` file generation or prompting
- ❌ Initial database migration execution
- ❌ Monitoring stack setup
- ❌ Backup cron installation
- ❌ First-run smoke test

### VPS Version Conflict 🔴

| Document | VPS Spec | Cost |
|----------|----------|------|
| `architecture_deployment.md` | Hetzner CX22 (2 vCPU, 4GB) | €4.49/mo |
| `fix_scalability_final.md` | Hetzner CX41 (8 vCPU, 16GB) | ~$30/mo |

**Resolution:** The fix doc supersedes the deployment doc. The deployment doc must be updated to reflect CX41 as the Phase 2 baseline. The CX22 is insufficient for the full stack (PostgreSQL + TimescaleDB + Redis Sentinel + trading engine + FinBERT + MT5 proxy = ~6.5GB minimum).

### Recommended End-to-End Install Script

A single script that does everything from VPS to running system:

```bash
#!/bin/bash
# install.sh — One-command Alpha Stack deployment
# Usage: curl -fsSL https://get.alphastack.app/server | bash

set -euo pipefail

# 1. Provision VPS (if not already done)
# 2. Clone repository
# 3. Prompt for configuration (MT5 creds, domain, etc.)
# 4. Generate .env file
# 5. docker compose up -d
# 6. Run migrations
# 7. Set up SSL
# 8. Install backup cron
# 9. Run smoke test
# 10. Print access URL and credentials
```

**This script does not exist.** The provisioning script and deploy steps are separate, manual processes.

### Verdict: 🟡 Good individual pieces, but no unified end-to-end automation. A user must follow ~6 manual steps across multiple scripts.

---

## 4. Auto-Update Mechanism Validation

### Desktop (Tauri): ✅ WELL-DESIGNED

| Aspect | Status | Detail |
|--------|--------|--------|
| Update endpoint | ✅ | `https://releases.alphastack.app/{{target}}/{{arch}}/{{current_version}}` |
| Signature verification | ✅ | Tauri built-in with `TAURI_SIGNING_PRIVATE_KEY` |
| Update manifest | ✅ | `latest.json` with version, notes, per-platform URLs + signatures |
| Safety rules | ✅ | Never update with open positions; save state first; offer "Update Later" |
| Rollback | ✅ | Keep previous binary for 7 days |
| CI integration | ✅ | `release-desktop.yml` generates manifest and uploads to S3/CDN |
| Platform coverage | ✅ | Linux (AppImage, .deb), Windows (.msi), macOS (.dmg) |

**Gaps:**
- ❌ No CDN deployment script for `releases.alphastack.app` (S3 upload referenced but not implemented)
- ❌ No actual `generate-update-manifest.py` script exists
- ❌ macOS notarization not automated in CI (mentioned in docs but not in workflow)

### Web Companion: ✅ WELL-DESIGNED

| Aspect | Status | Detail |
|--------|--------|--------|
| Deployment method | ✅ | Push to main → CI builds → deploy to nginx/CDN |
| Cache invalidation | ✅ | Service worker with stale-while-revalidate |
| Zero user action | ✅ | Updates load on next page navigation |

**Gaps:**
- ❌ No actual CDN deployment step in CI (self-hosted nginx assumed)
- ❌ Service worker implementation not provided

### Backend Services: ✅ WELL-DESIGNED

| Aspect | Status | Detail |
|--------|--------|--------|
| Rolling update script | ✅ | `scripts/deploy.sh` with scale-up → health check → scale-down |
| Zero-downtime | ✅ | Docker Compose scale technique |
| Migration handling | ✅ | `alembic upgrade head` in deploy step |

**Gaps:**
- ❌ `scripts/deploy.sh` not actually created (only documented)
- ❌ No rollback procedure for failed backend deploys

### Mobile: ⚠️ MINIMAL

| Aspect | Status | Detail |
|--------|--------|--------|
| Android | ⚠️ | Google Play auto-update mentioned, no implementation |
| iOS | ⚠️ | App Store auto-update mentioned, no implementation |
| In-app update check | ⚠️ | Code snippet shown but not implemented |
| OTA updates | ❌ | No CodePush or similar mechanism defined |

### Verdict: 🟡 Desktop and web update flows are well-designed but lack implementation artifacts. Mobile is barely addressed.

---

## 5. CI/CD Pipeline Validation

### Current State: ✅ COMPREHENSIVE

The GitHub Actions pipeline covers the full lifecycle:

| Pipeline | Trigger | Steps | Status |
|----------|---------|-------|--------|
| `ci.yml` | Push/PR | Lint → Test → Build Images → Deploy Staging | ✅ Complete |
| `nightly.yml` | Cron (03:00 UTC) | Full integration tests | ✅ Complete |
| `release-desktop.yml` | Tag push | Build all platforms → Create GitHub Release → Deploy Prod | ✅ Complete |

### CI Matrix

| Check | Implementation | Status |
|-------|---------------|--------|
| Python linting | `ruff check` + `ruff format --check` | ✅ |
| Type checking | `mypy` | ✅ |
| Unit tests | `pytest` with coverage | ✅ |
| Integration tests | Nightly with live DB/Redis services | ✅ |
| Docker image builds | Matrix build for 6 services | ✅ |
| Desktop builds | Matrix: Linux x86/aarch, Windows x86, macOS aarch | ✅ |
| Staging deploy | SSH + docker compose pull + up | ✅ |
| Production deploy | Tag-triggered, SSH deploy | ✅ |
| Release artifacts | AppImage, .deb, .msi, .dmg | ✅ |
| Coverage reporting | Codecov | ✅ |
| Container registry | GitHub Container Registry (ghcr.io) | ✅ |

### CI Gaps

| Issue | Severity | Detail |
|-------|----------|--------|
| **No security scanning** | 🟠 MEDIUM | No `trivy`, `snyk`, or `dependabot` configuration for container/dependency vulnerability scanning |
| **No integration test for unified server** | 🟠 MEDIUM | CI tests the old multi-service architecture. The Rust unified server has no CI pipeline. |
| **No mobile CI** | 🟠 MEDIUM | Flutter/React Native build pipeline not defined |
| **No load testing** | 🟡 LOW | No k6, locust, or similar load test in pipeline |
| **No E2E tests** | 🟡 LOW | No Playwright/Cypress for desktop or web UI testing |
| **Codecov token required** | 🟡 LOW | `CODECOV_TOKEN` secret must be configured |
| **Staging environment undefined** | 🟡 LOW | `STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_KEY` secrets must be configured |

### Verdict: ✅ CI/CD is the strongest part of the deployment architecture. Well-structured, comprehensive, production-ready pattern. Needs security scanning and mobile CI additions.

---

## 6. Remaining Deployment Issues

### 🔴 CRITICAL Issues

| # | Issue | Impact | Effort |
|---|-------|--------|--------|
| 1 | **No one-line install for end users** | Users cannot install the app without manual steps | 1 day |
| 2 | **Unified server not in deployment** | `fix_platform_consolidation.md` introduces Rust Axum server that replaces current Python services. Zero deployment artifacts exist. | 3-5 days |
| 3 | **VPS spec conflict (CX22 vs CX41)** | Deployment doc says 4GB RAM; fix doc proves 16GB needed. Following the wrong spec = OOM crashes. | 5 min (doc update) |
| 4 | **No end-to-end deploy script** | VPS provisioning, app config, SSL, backups, monitoring are 6+ separate manual steps | 1 day |

### 🟠 HIGH Issues

| # | Issue | Impact | Effort |
|---|-------|--------|--------|
| 5 | **MT5 Data Proxy not in Docker Compose** | New service from scalability fix has no deployment config | 2 hours |
| 6 | **Redis Sentinel compose not integrated** | Phase 2 HA config exists in fix doc but not as deployable overlay | 2 hours |
| 7 | **Health check endpoints unimplemented** | Docker health checks reference `/health` but no code exists | 4 hours |
| 8 | **No `.env.example` or config generator** | Users must manually construct `.env` from doc template | 2 hours |
| 9 | **Backup script references non-existent tools** | `b2` CLI assumed but not installed by provisioning script | 1 hour |
| 10 | **Desktop CI doesn't build unified server sidecar** | Tauri sidecar build references old Python sidecar, not Rust server | 1 day |

### 🟡 MEDIUM Issues

| # | Issue | Impact | Effort |
|---|-------|--------|--------|
| 11 | **No security scanning in CI** | Vulnerable dependencies could ship | 4 hours |
| 12 | **Mobile deployment pipeline missing** | Flutter/React Native not in CI/CD at all | 2 days |
| 13 | **No download/landing page** | `get.alphastack.app` and `releases.alphastack.app` referenced but don't exist | 1 day |
| 14 | **macOS notarization not automated** | Required for distribution outside App Store | 4 hours |
| 15 | **Monitoring stack profiles awkward** | Using `profiles: []` to override is a Docker Compose v2 hack; may not work reliably | 1 hour |
| 16 | **No database migration CI step for staging** | `alembic upgrade head` runs in deploy but not validated in CI | 2 hours |
| 17 | **Backup GPG passphrase management** | Passed as env var; should use Docker secrets or Vault | 2 hours |

### 🟢 LOW Issues

| # | Issue | Impact | Effort |
|---|-------|--------|--------|
| 18 | **No Grafana dashboard provisioning** | Dashboard layout described but no JSON export | 4 hours |
| 19 | **Prometheus alertmanager not in compose** | Alert rules defined but no alertmanager service | 1 hour |
| 20 | **No log rotation for nginx inside container** | Docker json-file driver handles it, but nginx logs also written to container filesystem | 30 min |
| 21 | **Loki retention config may conflict** | Both `limits_config` and `table_manager` set retention | 30 min |

---

## 7. Integration Conflicts Between Documents

### Conflict Matrix

| Topic | `architecture_deployment.md` | `fix_scalability_final.md` | `fix_platform_consolidation.md` | Resolution |
|-------|---------------------------|--------------------------|-------------------------------|------------|
| **Backend architecture** | Multi-service Python (core-api, trading-engine, market-data) | Same as deployment doc | **Single Rust Axum server** | Fix doc wins — unified server replaces multi-service |
| **VPS size Phase 2** | CX22 (2 vCPU, 4GB, €4.49) | **CX41 (8 vCPU, 16GB, ~$30)** | Not specified | Fix doc wins — 4GB is insufficient |
| **Redis config Phase 2** | Single Redis | **Redis Sentinel (1+2)** | Not specified | Fix doc wins — Sentinel for HA |
| **MT5 data access** | Direct Python API + mt5-bridge container | **MT5 Data Proxy service** | Via unified server | Fix doc wins — eliminates serialization |
| **Desktop architecture** | Tauri with Python sidecar | Not specified | **Tauri as thin shell + embedded Rust server** | Platform fix wins — eliminates architecture split |
| **Auth system** | Not specified in deployment | Not specified | **JWT with device sessions** | Platform fix defines auth; deployment must implement |
| **API surface** | Multiple endpoints per service | Same | **Single versioned API `/api/v1/*`** | Platform fix wins |

### Required Document Updates

1. **`architecture_deployment.md`** must be updated to:
   - Replace multi-service Python backend with unified Rust server
   - Update Phase 2 VPS from CX22 to CX41
   - Add Redis Sentinel to Phase 2 compose
   - Add MT5 Data Proxy service
   - Add Alpha Stack Server (Rust) Dockerfile and compose service
   - Integrate JWT auth configuration
   - Update CI pipeline for Rust server builds

2. **New artifacts needed:**
   - `server/Dockerfile` — Rust Axum server
   - `docker-compose.sentinel.yml` — Redis Sentinel overlay
   - `docker-compose.unified.yml` — Unified server overlay
   - `scripts/install.sh` — User-facing one-line installer
   - `scripts/configure.sh` — Interactive config generator
   - `.env.example` — Complete env template with all variables

---

## 8. Deployment Readiness by Phase

| Phase | Readiness | Blockers |
|-------|-----------|----------|
| **Phase 1: Local Dev** | 80% | Need unified server compose, health endpoints, `.env.example` |
| **Phase 2: Single VPS** | 50% | Need CX41 update, Sentinel compose, MT5 proxy, end-to-end script |
| **Phase 3: Split VPS** | 40% | WireGuard config exists conceptually; no actual configs |
| **Phase 4: Professional** | 20% | K3s manifests are skeleton only |
| **Phase 5: Multi-Region** | 10% | Conceptual only |

---

## 9. Recommended Action Plan

### Immediate (Before Any Deployment)

1. **Create unified server Dockerfile** — The Rust Axum server from `fix_platform_consolidation.md` needs a Dockerfile
2. **Update VPS spec to CX41** — 5-minute doc fix that prevents OOM in production
3. **Create `.env.example`** — Complete template with all required/optional variables
4. **Implement health endpoints** — Every service needs `GET /health` returning 200

### Short-Term (Before Phase 2)

5. **Create end-to-end deploy script** — Single `install.sh` that provisions, configures, and starts everything
6. **Integrate Redis Sentinel compose** — Copy fix doc YAML into `docker-compose.sentinel.yml`
7. **Add MT5 Data Proxy to compose** — New service with Dockerfile
8. **Create user install scripts** — Linux shell, macOS Homebrew cask, Windows PowerShell
9. **Set up download page** — `get.alphastack.app` with platform detection

### Medium-Term (Before Phase 3)

10. **Add security scanning to CI** — Trivy for containers, Dependabot for dependencies
11. **Add mobile CI pipeline** — Flutter build matrix
12. **Automate macOS notarization** — In `release-desktop.yml`
13. **Create Grafana dashboard JSON** — Provision dashboards automatically
14. **Add Alertmanager to compose** — Complete the alerting pipeline

---

## 10. Summary Scorecard

| Category | Score | Notes |
|----------|-------|-------|
| **Docker Architecture** | 8/10 | Excellent design; needs unified server integration |
| **CI/CD Pipeline** | 9/10 | Production-grade; needs security scanning |
| **VPS Automation** | 6/10 | Good pieces; no unified end-to-end flow |
| **Auto-Update** | 7/10 | Desktop well-designed; web/mobile gaps |
| **Monitoring** | 7/10 | Comprehensive config; dashboard provisioning missing |
| **Backup/DR** | 8/10 | Thorough scripts; needs actual file creation |
| **Security** | 7/10 | Good hardening; missing CI scanning |
| **Documentation** | 8/10 | Excellent docs; inter-document conflicts need resolution |
| **One-Line Install** | 1/10 | Does not exist |
| **Cross-Document Consistency** | 4/10 | Major conflicts between deployment and fix documents |
| **OVERALL** | **6.5/10** | Strong foundation; critical gaps before production use |

---

*This review validates the deployment architecture against all related documents. The architecture is sound and well-thought-out, but implementation artifacts are largely missing. The highest priority is resolving the conflict between the multi-service Python backend (deployment doc) and the unified Rust server (platform consolidation fix), as this affects every other deployment decision.*

*Generated: 2026-07-11*
