# Alpha Stack — Installation & Deployment Review

> **Reviewer:** Deployment Review Agent  
> **Date:** 2026-07-11  
> **Scope:** Installation, deployment, CI/CD, auto-update across all platforms  
> **Documents Reviewed:** `architecture_system.md`, `architecture_ui_desktop.md`, `architecture_ui_mobile.md`, `architecture_documentation.md`, `architecture_testing.md`  
> **Critical Gap:** `architecture_deployment.md` — **FILE DOES NOT EXIST** (referenced but never authored)

---

## Executive Summary

| Area | Status | Verdict |
|------|--------|---------|
| One-Line Install (Linux) | ❌ Missing | No single command defined |
| One-Line Install (Windows) | ❌ Missing | No installer/MSI workflow defined |
| One-Line Install (macOS) | ❌ Missing | No brew/cask or DMG workflow defined |
| Docker Deployment | 🟡 Partial | Documented in prose only; no actual compose file or Dockerfile in workspace |
| VPS Deployment Automation | ❌ Missing | Hardening checklist exists; no automation scripts (Terraform/Ansible/etc.) |
| Auto-Update Mechanism | ❌ Missing | Toggle exists in desktop settings UI; zero implementation detail for any platform |
| CI/CD Pipeline | ✅ Complete | Full 8-stage GitHub Actions pipeline specified |
| Mobile Deployment (App Stores) | ❌ Missing | No Play Store / App Store submission, signing, or review process defined |
| Web Deployment | ❌ Missing | Architecture references "Web App (React)" but no web-specific deployment spec |

**Overall Rating: INCOMPLETE — The deployment story is the weakest part of the architecture.**

---

## 1. One-Line Install Commands

### 1.1 Linux — ❌ NOT DEFINED

**Expected:** A single `curl | bash` or similar command that installs and configures Alpha Stack on a fresh Linux machine.

**What exists:** Multi-step manual process documented in `architecture_documentation.md`:

```bash
# Step 1: Clone
git clone https://github.com/alphastack/alphastack.git
cd alphastack

# Step 2: Configure
cp .env.example .env
# Manual editing required

# Step 3: Launch
docker compose up -d
```

**Gaps:**
- No `curl -sSL https://get.alphastack.io | bash` style installer
- No dependency auto-detection (Docker, Docker Compose versions)
- No `.env` interactive wizard or smart defaults
- No `systemd` service file for persistent operation
- No uninstall command

### 1.2 Windows — ❌ NOT DEFINED

**Expected:** An `.msi` installer, `winget install alphastack`, or PowerShell one-liner.

**What exists:** Desktop architecture specifies `.msi` (enterprise) and `.exe/NSIS` (consumer) as package formats, but:
- No build pipeline for Windows installers
- No `winget` or `chocolatey` package manifest
- No Windows-specific installation guide
- MT5 on Windows is native (no Wine needed) but auto-detection of MT5 install path is mentioned in UI settings without implementation spec
- Code signing for Windows SmartScreen is mentioned as required but no signing process is defined

### 1.3 macOS — ❌ NOT DEFINED

**Expected:** `brew install --cask alphastack` or a `.dmg` download page.

**What exists:** Desktop architecture specifies `.dmg` (universal binary: x86_64 + aarch64) as the package format, but:
- No Homebrew cask formula
- No DMG creation pipeline
- Notarization is mentioned as "required" but no notarization workflow is defined
- No Apple Developer account / signing certificate management

### Recommendation

Create an `install.sh` (Linux) and integrate with package managers:

```bash
# Target experience for Linux:
curl -sSL https://get.alphastack.io | bash
# → Detects OS, installs Docker if needed, pulls images, configures .env interactively, starts services

# Target experience for macOS:
brew install --cask alphastack

# Target experience for Windows:
winget install AlphaStack
```

---

## 2. Docker Deployment — 🟡 PARTIAL

### 2.1 What's Documented

`architecture_documentation.md` outlines a Docker Compose deployment with 5 services:
- `alphastack` (main app)
- `timescaledb` (database)
- `redis` (cache)
- `prometheus` (metrics)
- `grafana` (dashboards)

`architecture_system.md` shows Docker Compose stacks in deployment topology diagrams (Phase 1 and Phase 2).

`architecture_testing.md` includes a `docker-compose.test.yml` for testing.

### 2.2 What's Missing

| Artifact | Status | Notes |
|----------|--------|-------|
| `infra/compose/docker-compose.yml` (production) | ❌ Not authored | Referenced in docs but file doesn't exist |
| `infra/compose/docker-compose.dev.yml` | ❌ Not authored | No dev-specific compose |
| `infra/compose/docker-compose.ci.yml` | ❌ Not authored | Referenced in CI pipeline but not created |
| `infra/docker/Dockerfile` (main app) | ❌ Not authored | No Dockerfile for the Python trading engine |
| `infra/docker/Dockerfile.api` | ❌ Not authored | No Dockerfile for FastAPI gateway |
| `infra/docker/Dockerfile.test` | ❌ Not authored | Referenced in CI but not created |
| `.env.example` | ❌ Not authored | Referenced in docs but not created |
| Health check endpoints | 🟡 Mentioned | `/health` endpoint referenced in CI deploy stage; no spec |
| Volume mounts for persistence | ❌ Not specified | TimescaleDB data, Redis AOF, Grafana dashboards |
| Network configuration | ❌ Not specified | Internal networking, port mappings |
| Resource limits | ❌ Not specified | CPU/memory limits per container |
| Multi-stage build optimization | ❌ Not specified | Image size targets not defined |

### 2.3 Architecture Gaps in Docker Spec

- **MT5 in Docker:** The system architecture shows MT5 (Wine) running inside Docker for VPS deployment, but Wine-in-Docker is notoriously fragile. No Wine base image is specified, no Wine prefix management, no MT5 headless configuration.
- **GPU support for ML inference:** Phase 3+ mentions ML inference pods but no NVIDIA container toolkit configuration.
- **Redis persistence:** Event bus uses Redis Streams but no AOF/RDB persistence configuration is specified.

---

## 3. VPS Deployment Automation — ❌ NOT AUTOMATED

### 3.1 What's Documented

`architecture_documentation.md` provides a VPS hardening checklist:
- SSH key-only auth
- UFW firewall (22, 80, 443)
- Fail2ban
- Auto security updates
- Non-root user
- TLS via Let's Encrypt
- Database not exposed to internet
- Secrets in encrypted vault
- Log rotation
- Backup schedule

Recommended providers: Hetzner CX22/CX32, Vultr, DigitalOcean.

### 3.2 What's Missing

| Artifact | Status | Notes |
|----------|--------|-------|
| `scripts/deploy.sh` (staging/production) | ❌ Not authored | Referenced in CI/CD pipeline (`./scripts/deploy.sh staging`) but doesn't exist |
| `scripts/rollback.sh` | ❌ Not authored | Referenced in CI/CD pipeline but doesn't exist |
| Terraform/Pulumi IaC | ❌ Not authored | No infrastructure-as-code for VPS provisioning |
| Ansible playbooks | ❌ Not authored | No configuration management automation |
| Nginx/Traefik reverse proxy config | ❌ Not authored | Phase 2 VPS shows Nginx but no config |
| TLS automation (certbot/Traefik) | ❌ Not authored | Mentioned but not scripted |
| Database backup scripts | ❌ Not authored | Mentioned in checklist but not implemented |
| Monitoring alert rules | ❌ Not authored | Prometheus alerting rules not defined |
| Log rotation config | ❌ Not authored | Mentioned in checklist |
| `systemd` service files | ❌ Not authored | For non-Docker deployments or Docker restart policies |

### 3.3 The Deploy Gap in CI/CD

The CI/CD pipeline (Stage 8) references `./scripts/deploy.sh staging` and `./scripts/deploy.sh production`, but these scripts don't exist. The pipeline also specifies:
- Blue-green deployment for production
- Health check verification with `curl` + `jq`
- Automatic rollback on failure

None of this is implemented. The CI/CD pipeline is a **specification** only.

---

## 4. Auto-Update Mechanism — ❌ NOT DEFINED

### 4.1 Desktop (Tauri)

**What exists:**
- Settings UI: `Auto-update | Toggle | On | Check for updates automatically` (desktop architecture, Section 6.2)
- Implementation roadmap Phase 6: "Auto-update integration"

**What's missing:**
- No Tauri updater configuration (Tauri 2.x has built-in update support via `tauri-plugin-updater`)
- No update server endpoint (e.g., `https://releases.alphastack.io/`)
- No update manifest format (`latest.json` with version, URL, signature)
- No code signing for update packages
- No staged rollout strategy (canary → beta → stable)
- No rollback mechanism for failed updates
- No differential/patch updates (full download every time?)
- No forced update mechanism for critical security patches

### 4.2 Mobile (Flutter)

**What exists:** Nothing. Mobile architecture has zero mention of:
- App Store / Play Store submission process
- App signing (keystore, provisioning profiles)
- Version management strategy
- OTA update mechanism (if bypassing stores)
- Store review guidelines compliance
- In-app update prompts

### 4.3 Web

**What exists:** Nothing. No web deployment architecture exists at all. The system architecture references a "Web App (React) (Companion)" but no `architecture_ui_web.md` was authored.

### 4.4 Backend (Docker/VPS)

**What exists:** The CI/CD pipeline specifies blue-green deployment, but:
- No container image registry (Docker Hub, ECR, GCR, GHCR) is specified
- No image tagging strategy (semver, SHA, `latest`)
- No rolling update configuration for Docker Compose or K8s
- No database migration strategy (Alembic? Flyway?)
- No zero-downtime deployment verification

---

## 5. CI/CD Pipeline — ✅ COMPLETE (as specification)

### 5.1 Pipeline Overview

The 8-stage pipeline in `architecture_testing.md` is the most complete deployment-related artifact:

| Stage | Scope | Trigger | Time Budget |
|-------|-------|---------|-------------|
| 1. Lint & Type Check | Ruff, mypy, Clippy, ESLint, flutter analyze | Every push/PR | <30s |
| 2. Unit Tests | pytest, cargo test, vitest, flutter test | After lint | <60s |
| 3. Security Scans | Bandit, cargo-audit, TruffleHog, Trivy, npm audit | After lint | <5min |
| 4. Build | Docker images, Tauri (all platforms), Flutter, Web | After tests+security | <5min |
| 5. Integration Tests | Testcontainers, broker demo, API | PR only | <10min |
| 6. E2E Tests | Full lifecycle, Playwright, Flutter integration | Nightly + pre-release | <15min |
| 7. Performance Tests | Latency, load, memory, backtest | Weekly + pre-release | <30min |
| 8. Deploy | Staging → smoke → production (blue-green) → health check | main branch only | — |

### 5.2 What's Good

- Concurrency control (`cancel-in-progress: true`)
- Nightly E2E with scheduled cron
- Coverage upload to Codecov
- Log collection on E2E failure
- Blue-green production deployment with automatic rollback
- Performance regression detection with baseline comparison

### 5.3 What's Missing from CI/CD

| Gap | Impact |
|-----|--------|
| No Flutter lint/test job (only mentioned, no YAML) | Mobile CI is incomplete |
| No Tauri build matrix (Linux/Windows/macOS) | Desktop CI only builds Linux |
| No code signing steps | Windows/macOS builds will trigger security warnings |
| No Docker registry push step | Built images are lost after CI run |
| No dependency caching strategy | Slow CI runs |
| No changelog generation | No automated release notes |
| No version bumping automation | Manual version management |

---

## 6. Platform-Specific Deployment Gaps

### 6.1 Linux Desktop

| Item | Status |
|------|--------|
| `.deb` package | Specified but not implemented |
| AppImage | Specified but not implemented |
| Flatpak | Specified but not implemented |
| `.desktop` file | Mentioned but not authored |
| System tray (GNOME/KDE) | Addressed in UI architecture |
| Wine MT5 setup | Not scripted |

### 6.2 Windows Desktop

| Item | Status |
|------|--------|
| `.msi` installer | Specified but not implemented |
| `.exe` NSIS installer | Specified but not implemented |
| Code signing | Required but no process |
| Auto-start registry entry | UI spec only |
| Windows Defender exclusion | Not addressed |
| MSIX (Store) | Mentioned as future |

### 6.3 macOS Desktop

| Item | Status |
|------|--------|
| `.dmg` universal binary | Specified but not implemented |
| Notarization | Required but no process |
| Homebrew cask | Not created |
| Keychain integration | UI spec only |
| Gatekeeper compliance | Not addressed |

### 6.4 Mobile (Android + iOS)

| Item | Status |
|------|--------|
| Play Store listing | Not created |
| App Store listing | Not created |
| App signing (Android keystore) | Not defined |
| iOS provisioning profiles | Not defined |
| Store screenshots/metadata | Not defined |
| Review guidelines compliance | Not addressed |
| Crash reporting (Crashlytics/Sentry) | Not specified |
| Analytics (Firebase/Amplitude) | Not specified |

### 6.5 Web Companion

| Item | Status |
|------|--------|
| `architecture_ui_web.md` | **FILE DOES NOT EXIST** |
| Hosting spec (Vercel/Netlify/S3+CloudFront) | Not defined |
| Domain/SSL | Not defined |
| CDN configuration | Not defined |
| SPA routing config | Not defined |

---

## 7. Critical Missing Artifacts

### 7.1 Missing Architecture Document

**`architecture_deployment.md`** — This file was requested for review but **does not exist**. Given the scope of gaps identified above, this document needs to be authored as a priority. It should cover:

1. One-line install commands for all platforms
2. Complete Docker Compose files (dev, staging, production)
3. Dockerfiles for all services
4. VPS automation scripts (Terraform + Ansible)
5. Auto-update mechanism specification
6. Release management process
7. Database migration strategy
8. Rollback procedures
9. Monitoring & alerting setup
10. Backup & disaster recovery

### 7.2 Missing Implementation Files

| File | Referenced By | Status |
|------|--------------|--------|
| `infra/compose/docker-compose.yml` | Documentation, CI/CD | ❌ Missing |
| `infra/compose/docker-compose.dev.yml` | — | ❌ Missing |
| `infra/compose/docker-compose.ci.yml` | CI/CD pipeline | ❌ Missing |
| `infra/docker/Dockerfile` | CI/CD pipeline | ❌ Missing |
| `infra/docker/Dockerfile.api` | — | ❌ Missing |
| `infra/docker/Dockerfile.test` | CI/CD pipeline | ❌ Missing |
| `.env.example` | Documentation | ❌ Missing |
| `scripts/deploy.sh` | CI/CD pipeline | ❌ Missing |
| `scripts/rollback.sh` | CI/CD pipeline | ❌ Missing |
| `scripts/compare_benchmarks.py` | CI/CD pipeline | ❌ Missing |
| `scripts/alert_performance_regression.py` | CI/CD pipeline | ❌ Missing |
| `infra/terraform/` | — | ❌ Missing |
| `infra/ansible/` | — | ❌ Missing |
| `apps/desktop/tauri.conf.json` (updater config) | — | ❌ Missing |

---

## 8. Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Cannot deploy to production | 🔴 Critical | Certain (today) | Author deployment artifacts ASAP |
| CI/CD pipeline references non-existent scripts | 🔴 Critical | Certain | All Stage 8 deploy steps will fail |
| No auto-update = users stuck on old versions | 🟡 High | High | Implement Tauri updater before v1.0 |
| No code signing = security warnings on install | 🟡 High | High | Set up signing before first release |
| Wine MT5 in Docker is fragile | 🟡 High | Medium | Test extensively; consider native VPS fallback |
| No backup strategy = data loss risk | 🟡 High | Medium | Author backup scripts and cron jobs |
| No monitoring alerts = silent failures | 🟡 High | Medium | Define Prometheus alerting rules |

---

## 9. Prioritized Action Items

### P0 — Block Release (Do Before v1.0)

1. **Author `architecture_deployment.md`** — Complete deployment architecture document
2. **Create Docker Compose files** — `docker-compose.yml` (production), `docker-compose.dev.yml`
3. **Create Dockerfiles** — For Python engine, FastAPI gateway, test runner
4. **Create `.env.example`** — With all required variables and sane defaults
5. **Create `deploy.sh` and `rollback.sh`** — Referenced by CI/CD pipeline
6. **Implement Tauri auto-updater** — `tauri-plugin-updater` configuration
7. **Set up code signing** — Windows (EV certificate) + macOS (Developer ID)

### P1 — Important (Do Before Public Beta)

8. **Create one-line install script** — `curl | bash` for Linux
9. **Create Homebrew cask** — For macOS distribution
10. **Create Windows installer** — `.msi` via WiX or NSIS
11. **Complete CI/CD pipeline YAML** — Flutter jobs, Tauri build matrix, registry push
12. **Define database migration strategy** — Alembic or equivalent
13. **Author monitoring/alerting rules** — Prometheus alertmanager config

### P2 — Nice to Have (Do Before v1.1)

14. **Terraform modules** — VPS provisioning for Hetzner/AWS
15. **Ansible playbooks** — Server hardening and configuration
16. **App Store submission** — Play Store + App Store metadata, screenshots
17. **Web deployment** — Hosting, CDN, domain setup
18. **Differential updates** — Reduce download size for desktop updates

---

## 10. Summary

The Alpha Stack architecture has **excellent design depth** for the trading engine, multi-agent system, risk management, and UI layers. The CI/CD pipeline specification is thorough and well-designed.

However, the **deployment and installation layer is essentially unimplemented**. The gap between "architecture document" and "runnable system" is significant:

- **0 out of 3** platform installers exist
- **0 out of 6** Docker/Dockerfile artifacts exist
- **0 out of 2** deployment scripts referenced by CI/CD exist
- **0 out of 1** auto-update mechanisms are specified
- The `architecture_deployment.md` file itself was never authored

This is the **single biggest blocker** to shipping Alpha Stack. The trading engine can be perfect, but if users can't install and run it, nothing else matters.

**Recommendation:** Treat `architecture_deployment.md` and its associated implementation files as a P0 sprint deliverable, parallel to the trading engine development.
