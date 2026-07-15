# AlphaStack – Integration & Deployment Review

**Date:** 2026-07-15  
**Scope:** API contracts, WebSocket protocol, frontend-backend integration, Docker/deployment, CI/CD, and gaps

---

## 1. API CONTRACT

### 1.1 REST API Design Quality

**Strengths:**
- Clean resource-oriented URL design under `/api/v1` prefix: `/trades`, `/portfolio`, `/signals`, `/auth`
- Proper HTTP methods: `GET` for reads, `POST` for creates, `PUT` for state changes (close trade)
- Pydantic models enforce request/response validation with clear field types and constraints
- Pagination support on list endpoints (`page`, `page_size` query params)
- Filtering support on trades (`status`, `symbol`) and signals (`symbol`, `strategy_id`)
- FastAPI auto-generates OpenAPI docs at `/docs` and `/redoc`

**Weaknesses:**
- **No versioning beyond the prefix** — `/api/v1` is set but there's no negotiation or deprecation strategy documented
- **In-memory data stores** — `_TRADES` and `_SIGNALS` are Python dicts; all data is lost on restart. This is explicitly demo-only but blocks any real deployment
- **No authentication middleware** — JWT tokens are issued by `/auth/login` but no `Depends()` guard enforces them on protected routes. Any endpoint is accessible without a token
- **No request ID / correlation** — No `X-Request-ID` header propagation for tracing

### 1.2 Endpoint Completeness

| Endpoint | Method | Status | Notes |
|---|---|---|---|
| `/auth/login` | POST | ✅ Working | Demo credentials only |
| `/auth/refresh` | POST | ✅ Working | Refresh token rotation |
| `/auth/logout` | POST | ⚠️ Stub | No server-side revocation |
| `/trades` | GET | ✅ Working | Pagination + filters |
| `/trades` | POST | ✅ Working | Creates in-memory trade |
| `/trades/{id}` | GET | ✅ Working | |
| `/trades/{id}/close` | PUT | ✅ Working | |
| `/portfolio` | GET | ⚠️ Placeholder | Current prices hardcoded as `entry * 1.005` |
| `/portfolio/pnl` | GET | ⚠️ Placeholder | Unrealized PnL uses same placeholder |
| `/portfolio/performance` | GET | ⚠️ Placeholder | Metrics are simplified approximations |
| `/signals` | GET | ✅ Working | Seeded demo data |
| `/signals/history` | GET | ✅ Working | |
| `/health` | GET | ✅ Working | |
| `/status` | GET | ⚠️ Partial | DB/Redis/engine status hardcoded to "unknown" |
| `/config` | GET | ✅ Working | Non-sensitive config exposed |
| `/analytics/*` | — | ❌ Missing | Frontend expects these |
| `/settings` | — | ❌ Missing | Frontend expects GET/PUT |
| `/positions` | — | ❌ Missing | Web frontend expects this as separate from portfolio |

### 1.3 Request/Response Formats

**Consistent patterns:**
- All responses are JSON
- List endpoints return `{ items: [...], total: N, page: N, page_size: N }` (trades) or `{ signals: [...], total: N }` (signals)
- Error responses follow FastAPI default: `{"detail": "..."}`

**Issues:**
- **Inconsistent list response shapes** — trades use `trades` key, signals use `signals` key. No standard envelope
- **Mobile client expects different field names** — Dart `Trade.fromJson` expects `entryPrice` (camelCase) but API returns `entry_price` (snake_case). This will cause deserialization failures unless a JSON key mapping is applied (the `.g.dart` generated files likely handle this, but it's fragile)
- **No standard error envelope** — Different error shapes across endpoints

### 1.4 Error Handling

**Server-side:**
- Proper HTTP status codes: 401 for auth failures, 404 for not found, 400 for bad state, 429 for rate limits
- `HTTPException` used consistently

**Client-side gaps:**
- **Mobile** (`api_service.dart`): Parses error body for `message` or `error` keys — but server returns `detail`. Will always fall back to raw body text
- **Web** (`api.ts`): Only reads `res.text()` on error, no structured error parsing
- **Desktop**: No API client at all (only Tauri bridge for native features)

### 1.5 Versioning Strategy

- Current: URL prefix `/api/v1`
- No header-based versioning
- No deprecation warnings
- No changelog or migration docs
- **Recommendation:** The v1 prefix is sufficient for now but should be complemented with a `Deprecation` header strategy when v2 arrives

---

## 2. WEBSOCKET PROTOCOL

### 2.1 Message Format

**Server → Client:**
```json
{"channel": "prices", "data": {"symbol": "BTC/USDT", "price": 67200, "bid": 67199, "ask": 67201}, "ts": 1234567890.0}
{"type": "subscribed", "channels": ["prices"]}
{"type": "pong", "ts": 1234567890.0}
{"type": "error", "detail": "..."}
```

**Client → Server:**
```json
{"type": "subscribe", "channels": ["prices", "trades", "signals"]}
{"type": "unsubscribe", "channels": ["prices"]}
{"type": "ping"}
```

**Issues:**
- **Two different message shapes** — broadcast messages use `{channel, data, ts}` while control messages use `{type, ...}`. This is workable but the mobile client parses everything through `type` field, which won't exist on broadcast messages. The mobile client's `_onMessage` handler will hit the `default` branch for all price/trade/signal broadcasts
- **No message ID** — Can't correlate request/response pairs
- **No sequence numbers** — Can't detect missed messages or reorder

### 2.2 Authentication

- **Server**: No authentication on the WebSocket endpoint. The `/ws` endpoint accepts any connection
- **Mobile client**: Appends `?token=<jwt>` to the WS URL, but the server never reads or validates it
- **Web client**: No auth token sent at all
- **Gap:** WebSocket is completely unauthenticated. Any client can connect and subscribe to all channels

### 2.3 Reconnection Logic

| Client | Strategy | Max Attempts | Backoff |
|---|---|---|---|
| Mobile (Dart) | Exponential | 10 | 2s × 2^attempt (2s, 4s, 8s... up to ~17 min) |
| Web (TS) | Fixed | ∞ | 3s constant |
| Desktop | None | — | No WebSocket client at all |

**Issues:**
- **Web client has no max reconnect limit** — will retry forever at 3s intervals if the server is down
- **No reconnection state recovery** — After reconnect, clients don't re-subscribe to channels. The mobile client has `subscribe()` methods but never calls them after reconnect
- **No jitter** — All clients of the same type will reconnect at exactly the same time (thundering herd)

### 2.4 Channel Subscriptions

**Defined channels:** `prices`, `trades`, `signals`, `system`

**Issues:**
- **Mobile client sends `channel` (singular)** but server expects `channels` (plural array). The subscribe messages will be silently ignored
- **No subscription confirmation tracking** — Client doesn't verify which channels it's actually subscribed to
- **No channel-level auth** — All authenticated users can subscribe to all channels (if auth existed)

---

## 3. FRONTEND-BACKEND INTEGRATION

### 3.1 Mobile (Flutter/Dart) → Backend

**Connection method:** HTTP REST via `http` package + WebSocket via `web_socket_channel`

**Critical mismatches:**

| Issue | Detail | Severity |
|---|---|---|
| Auth body format | Mobile sends `{apiKey, apiSecret}` but server expects `{username, password}` | 🔴 Breaking |
| Trade list parsing | Mobile expects `List<Trade>` directly, server returns `{trades: [...], total, page, page_size}` | 🔴 Breaking |
| Signal endpoints | Mobile calls `/signals/active` — server has `/signals` (no `/active` sub-path) | 🔴 Breaking |
| Analytics endpoints | Mobile calls `/analytics/*` — server has no analytics routes | 🔴 Breaking |
| Portfolio endpoints | Mobile calls `/portfolio/summary` and `/portfolio/positions` — server has `/portfolio` and `/portfolio/pnl` | 🟡 Mismatch |
| WS subscribe format | Mobile sends `{type: "subscribe", channel: "x"}` — server expects `{type: "subscribe", channels: ["x"]}` | 🔴 Breaking |
| Error parsing | Mobile looks for `message`/`error` keys, server returns `detail` | 🟡 Degraded |
| WS message routing | Mobile routes by `type` field, but broadcast messages have `channel` field, no `type` | 🔴 Breaking |

### 3.2 Web (Next.js/React) → Backend

**Connection method:** HTTP fetch via relative `/api` prefix + WebSocket via `ws://host/ws`

**Critical mismatches:**

| Issue | Detail | Severity |
|---|---|---|
| API prefix | Web uses `/api` prefix, server uses `/api/v1` — all calls will 404 | 🔴 Breaking |
| Portfolio endpoint | Web calls `/api/portfolio`, server has `/api/v1/portfolio` | 🔴 Breaking |
| Positions endpoint | Web calls `/api/positions` — no such route exists | 🔴 Missing |
| Analytics endpoints | Web calls `/analytics/performance`, `/analytics/equity-curve`, `/analytics/win-rate` — none exist | 🔴 Missing |
| Settings endpoints | Web calls `/settings` GET/PUT — no such route exists | 🔴 Missing |
| Signal detail | Web calls `/signals/{id}` — server has no single-signal endpoint | 🟡 Missing |
| Trade limit param | Web uses `limit` param, server uses `page_size` | 🟡 Mismatch |
| No auth | Web client has no authentication at all | 🔴 Missing |
| WS reconnect | Infinite retry with no backoff or limit | 🟡 Risk |

### 3.3 Desktop (Tauri/Svelte) → Backend

**Connection method:** Tauri bridge only (native OS features)

**Critical gaps:**
- **No API client** — The desktop app has `tauri-bridge.ts` for native features (notifications, window management, settings persistence) but **zero HTTP API calls to the backend**
- **No WebSocket client** — No real-time data streaming
- **No trade/signal/portfolio data fetching** — The desktop app cannot display any trading data
- The `store.ts` (Zustand) only manages UI state (sidebar, app version, system info)
- **The desktop app is essentially an empty shell** with native OS integration but no trading functionality

### 3.4 Shared Contracts/Types

**There are none.** Each platform defines its own types independently:

- **Backend (Python):** Pydantic models with snake_case fields (`entry_price`, `stop_loss`)
- **Mobile (Dart):** Dart classes with `@JsonSerializable()` — likely maps snake_case to camelCase via `json_annotation`
- **Web (TypeScript):** No type definitions at all — uses raw `unknown` types and ad-hoc `Record<string, string>`
- **Desktop (TypeScript):** Only UI state types, no API types

**Risk:** Any backend schema change requires manual updates in 3 separate codebases with no automated contract validation.

---

## 4. DOCKER & DEPLOYMENT

### 4.1 Docker Compose Services

| Service | Image | Health Check | Dependencies | Profile |
|---|---|---|---|---|
| `timescaledb` | `timescale/timescaledb:latest-pg16` | `pg_isready` ✅ | None | default |
| `redis` | `redis:7-alpine` | `redis-cli ping` ✅ | None | default |
| `api` | Custom build | `curl /health` (in Dockerfile) | timescaledb, redis | default |
| `trading-engine` | Custom build | None | timescaledb, redis | `engine` |

**Strengths:**
- Multi-stage Dockerfile reduces final image size
- Non-root user (`alphastack`) in container
- Health checks on infrastructure services
- `depends_on` with `condition: service_healthy` ensures proper startup order
- Volume mounts for development hot-reload

**Issues:**
- **Hardcoded dev credentials** — `DB_PASSWORD: alphastack` in plain text in compose file. Acceptable for dev but must not reach staging/production
- **No `.env` file support** — All env vars are inline in compose. Should use `env_file: .env`
- **No resource limits** — No `mem_limit`, `cpus`, or `deploy.resources` on any service
- **Ports exposed to host** — TimescaleDB (5432) and Redis (6379) are exposed, which is a security risk in non-dev environments
- **Trading engine has no health check** — Can't verify it's actually running correctly
- **`--reload` flag in API command** — Uvicorn's `--reload` is for development only; the compose file uses it in the API service command
- **No network isolation** — All services on the default network; no separation between frontend-facing and backend services
- **Volume mount inconsistency** — `../../src:/app/src` mounts host source into container, overriding the built image. This is dev-mode only but makes the compose file unsuitable for production

### 4.2 Environment Configuration

**Config hierarchy:**
1. `config/alphastack.yaml` — Base config
2. Environment variables — Override via `ALPHASTACK_<SECTION>_<KEY>` pattern
3. Docker Compose `environment` — Sets specific overrides

**Issues:**
- **No `.env.example`** — No template for required environment variables
- **Secrets in config file** — `config/alphastack.yaml` contains placeholder passwords (`password: alphastack`). Should use env-only for secrets
- **No config validation at startup** — No schema validation for the YAML file; malformed config will cause runtime errors
- **LLM/Feed API keys** — Config references `openai_api_key`, `polygon_api_key`, etc. but no guidance on which are required vs optional

### 4.3 Secret Management

**Current state:** All secrets are either hardcoded or expected as environment variables.

| Secret | Storage | Risk |
|---|---|---|
| DB password | Compose env / YAML | 🔴 Plaintext |
| MT5 password | YAML placeholder | 🟡 Not set |
| CCXT API key/secret | YAML placeholder | 🟡 Not set |
| LLM API keys | YAML placeholder | 🟡 Not set |
| Feed API keys | YAML placeholder | 🟡 Not set |
| JWT signing secret | Generated at runtime (`secrets.token_urlsafe`) | 🔴 Lost on restart |

**Critical:** The JWT `_SECRET` in `auth.py` is generated fresh on each process start. In a multi-worker deployment, each worker gets a different secret, making tokens invalid across workers.

### 4.4 Health Checks

- **Dockerfile:** `HEALTHCHECK curl -f http://localhost:8000/health` ✅
- **TimescaleDB:** `pg_isready` ✅
- **Redis:** `redis-cli ping` ✅
- **Trading engine:** ❌ None
- **`/status` endpoint:** Reports component health but hardcoded to "unknown" for DB/Redis/engine

### 4.5 Scaling Considerations

- **Single-process API** — Uvicorn runs with `--workers` not set (default 1). Config says `workers: 4` but the compose command doesn't use it
- **No load balancer** — Single API container exposed directly
- **In-memory rate limiter** — Won't work across multiple instances (need Redis-backed)
- **In-memory trade/signal store** — Can't scale horizontally at all
- **No message queue** — Trading engine → API communication is not defined; no event bus between services

---

## 5. CI/CD PIPELINE

### 5.1 Build Process

**CI (`ci.yml`):**
- Triggers on push to `main`/`develop` and PRs to `main`
- Python: lint (ruff) → type-check (mypy, allowed to fail) → test (pytest with coverage)
- TypeScript: matrix build for web/mobile/desktop — lint + build
- Docker: build-only test (no push)
- **Issue:** mypy is run with `|| true`, meaning type errors are never blocking

**Deploy (`deploy.yml`):**
- Triggers on version tags (`v*`) or manual dispatch
- Builds and pushes Docker image to GHCR
- Semver + SHA + latest tagging strategy ✅
- Staging deployment (triggered by tags or manual)
- Production deployment (manual only, requires staging first)

**Release (`release.yml`):**
- Builds all three desktop platforms (Windows/macOS/Linux)
- Builds mobile APK (Android only)
- Builds web app
- Creates GitHub Release with all artifacts

### 5.2 Test Automation

**Coverage:**
- Python: pytest with coverage XML ✅
- TypeScript: **No tests** — CI only does `lint` and `build`, no `npm test`
- Integration tests: **None**
- E2E tests: **None**
- Contract tests: **None**

### 5.3 Deployment Strategy

**Current state:** The deploy workflow has **placeholder commands**:
```yaml
# kubectl set image deployment/alphastack ...
echo "✅ Staging deployment complete"
```

**What's missing:**
- No actual Kubernetes manifests, Helm charts, or Terraform configs
- No staging/production environment definitions
- No database migration step
- No rollback strategy
- Smoke tests are also placeholders (`# curl -f ...`)
- No infrastructure-as-code

### 5.4 Release Process

- Tag-based release (`v*`) triggers full build pipeline ✅
- All platform artifacts collected into a single GitHub Release ✅
- **No iOS build** — Only Android APK is built
- **No code signing** — Desktop builds aren't signed
- **No notarization** — macOS builds won't pass Gatekeeper
- **Release notes auto-generated** — Good for MVP but needs manual curation for production

---

## 6. GAPS & RECOMMENDATIONS

### 6.1 Critical (Blocking Real Usage)

| # | Gap | Impact | Recommendation |
|---|---|---|---|
| C1 | **No database persistence** | All data lost on restart | Implement SQLAlchemy models for trades, signals, positions. Use Alembic for migrations |
| C2 | **No auth middleware** | All endpoints unprotected | Add `Depends(get_current_user)` to all protected routes |
| C3 | **JWT secret rotates on restart** | All tokens invalidated on deploy | Read JWT secret from env var; persist in secrets manager |
| C4 | **Frontend-backend contract mismatch** | Mobile and web apps can't communicate with backend | Align endpoint paths, request/response formats. Ideally generate OpenAPI client SDKs |
| C5 | **Desktop app has no backend integration** | Desktop shows no trading data | Implement HTTP API client + WebSocket in desktop app |
| C6 | **WebSocket has no auth** | Anyone can subscribe to all data | Validate JWT on WS connect; extract from query param or first message |
| C7 | **Mobile WS message format mismatch** | Mobile won't receive broadcast messages | Standardize on `{type, channel, data, ts}` envelope for all WS messages |

### 6.2 High Priority

| # | Gap | Recommendation |
|---|---|---|
| H1 | Missing analytics endpoints | Implement `/analytics/performance`, `/analytics/equity-curve`, `/analytics/win-rate`, `/analytics/pnl-history`, `/analytics/risk` |
| H2 | Missing settings endpoints | Implement `/settings` GET/PUT for runtime configuration |
| H3 | No shared type contracts | Generate TypeScript/Dart clients from OpenAPI spec |
| H4 | WS reconnection doesn't re-subscribe | After reconnect, automatically re-subscribe to previous channels |
| H5 | No database migrations | Set up Alembic with initial migration |
| H6 | Config/env secrets in plaintext | Use `.env` files for dev, secrets manager for prod |
| H7 | API worker count not applied | Use `uvicorn --workers 4` or gunicorn with uvicorn workers |

### 6.3 Medium Priority

| # | Gap | Recommendation |
|---|---|---|
| M1 | No rate limiting on WebSocket | Add per-client message rate limiting |
| M2 | No message compression | Consider `permessage-deflate` for WS |
| M3 | Web client has no auth | Implement login flow in web app |
| M4 | No iOS build | Add Flutter iOS build to release workflow |
| M5 | Desktop builds not signed | Add code signing for Windows/macOS |
| M6 | No integration tests | Add API integration tests with test database |
| M7 | No contract tests | Use Schemathesis or similar for API contract testing |
| M8 | mypy errors non-blocking | Fix type errors and remove `|| true` |
| M9 | No OpenAPI client generation | Add `openapi-generator` step to CI for TS and Dart clients |
| M10 | No E2E tests | Add Playwright (web) and integration tests |

### 6.4 Low Priority

| # | Gap | Recommendation |
|---|---|---|
| L1 | No request tracing | Add `X-Request-ID` middleware |
| L2 | No API versioning deprecation strategy | Document versioning policy |
| L3 | No Kubernetes manifests | Create Helm chart or k8s manifests |
| L4 | No database backup strategy | Add pg_dump cron or managed DB backups |
| L5 | No monitoring/observability | Add Prometheus metrics, structured logging to central store |
| L6 | No WebSocket message ordering | Add sequence numbers for gap detection |
| L7 | Thundering herd on reconnect | Add jitter to reconnection delays |

### 6.5 What Needs Building

**Immediate (unblock frontend integration):**
1. Fix API endpoint paths to match frontend expectations (or fix frontends)
2. Implement missing endpoints: analytics, settings, positions, signal detail
3. Add auth middleware to protect endpoints
4. Persist JWT secret in environment variable
5. Fix mobile WebSocket subscribe message format

**Short-term (functional system):**
1. Replace in-memory stores with database models
2. Implement proper portfolio price fetching (not placeholder `1.005x`)
3. Add WebSocket authentication
4. Build desktop app's API + WebSocket client
5. Generate shared type contracts from OpenAPI

**Medium-term (production readiness):**
1. Secrets management (Vault, AWS Secrets Manager, etc.)
2. Kubernetes deployment with proper resource limits
3. Database migrations (Alembic)
4. Integration + E2E test suites
5. Code signing for desktop/mobile releases
6. Monitoring and alerting stack

---

## Summary

The AlphaStack codebase has a **solid architectural foundation** — clean FastAPI structure, well-organized multi-platform frontend apps, proper Docker multi-stage builds, and a reasonable CI/CD skeleton. However, it's currently in a **pre-integration state** where the frontend apps and backend were developed with different assumptions about API contracts.

**The single biggest risk:** Every frontend client (mobile, web, desktop) has endpoint paths, request formats, or response parsing that **will fail at runtime** against the current backend. The system needs a contract alignment pass before it can function as an integrated whole.

**Top 3 actions:**
1. **Align API contracts** — Pick one source of truth (the backend), fix all frontend clients to match, or generate clients from OpenAPI
2. **Add auth middleware** — The JWT system exists but isn't enforced anywhere
3. **Persist data** — Replace in-memory dicts with database models for any non-demo usage
