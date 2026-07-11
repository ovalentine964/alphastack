# Alpha Stack — API Security Fix Plan

> **Author:** API Security Fix Agent  
> **Date:** 2026-07-11  
> **Input:** `review_security_api.md` — 7 critical findings  
> **Status:** READY FOR IMPLEMENTATION

---

## Table of Contents

| # | Issue | Section |
|---|-------|---------|
| 1 | [No per-API-key rate limiting](#1-per-api-key-rate-limiting) | §1 |
| 2 | [No global rate limits](#2-global-rate-limits) | §2 |
| 3 | [gRPC internal auth missing](#3-grpc-internal-authentication) | §3 |
| 4 | [WebSocket auth gaps](#4-websocket-authentication-gaps) | §4 |
| 5 | [SSRF risk](#5-ssrf-prevention) | §5 |
| 6 | [IDOR risk](#6-idor-prevention) | §6 |
| 7 | [Missing WebSocket message validation](#7-websocket-message-validation) | §7 |

---

## 1. Per-API-Key Rate Limiting

**Finding:** No rate limit per API key — attacker with a stolen key can rotate IPs and bypass all per-IP limits.

### 1.1 Solution Design

Rate-limit by **API key identity** (not IP) for all programmatic access. The key source priority:

```
api_key_id > jwt_sub > client_ip
```

Every request is attributed to a specific API key or user, and that attribution becomes the rate-limit bucket.

### 1.2 Configuration

```yaml
# config/rate_limits.yaml

# Per-API-key limits (highest priority for signed requests)
per_key:
  default:
    rate: 100/1m
    burst: 50
    key_source: "api_key_id"          # HMAC-signed requests → rate by key

  trading:
    pattern: "/api/v1/orders/*"
    rate: 30/1m
    burst: 10
    key_source: "api_key_id"

  market_data:
    pattern: "/api/v1/market-data/*"
    rate: 300/1m
    burst: 100
    key_source: "api_key_id"

  export:
    pattern: "/api/v1/export/*"
    rate: 10/1m
    burst: 5
    key_source: "api_key_id"

# Per-user limits (for JWT-authenticated browser sessions)
per_user:
  default:
    rate: 100/1m
    burst: 50
    key_source: "jwt_sub"

# Auth endpoints — per-IP + per-account (existing, preserved)
per_ip:
  login:
    pattern: "/api/v1/auth/login"
    rate: 5/15m
    burst: 3
    block_duration: 30m
```

### 1.3 Implementation — Rust (API Gateway)

```rust
// src/middleware/rate_limit.rs

use governor::{Quota, RateLimiter, clock::DefaultClock};
use std::num::NonZeroU32;
use std::sync::Arc;
use dashmap::DashMap;
use std::time::Duration;

/// Rate limit key: identifies the requester
#[derive(Debug, Clone, Hash, PartialEq, Eq)]
enum RateLimitKey {
    ApiKey(String),      // API key ID from HMAC verification
    User(String),        // JWT `sub` claim
    Ip(String),          // Fallback: client IP
}

/// Per-key rate limiter with automatic cleanup
pub struct PerKeyRateLimiter {
    limiters: DashMap<RateLimitKey, Arc<RateLimiter<RateLimitKey, DefaultClock>>>,
    quota: Quota,
    cleanup_interval: Duration,
}

impl PerKeyRateLimiter {
    pub fn new(requests_per_minute: u32, burst: u32) -> Self {
        let quota = Quota::per_minute(
            NonZeroU32::new(requests_per_minute).unwrap()
        ).allow_burst(
            NonZeroU32::new(burst).unwrap()
        );

        Self {
            limiters: DashMap::new(),
            quota,
            cleanup_interval: Duration::from_secs(300),
        }
    }

    /// Check if request is allowed. Returns (allowed, remaining, reset_after).
    pub fn check(&self, key: RateLimitKey) -> (bool, u32, Duration) {
        let limiter = self.limiters
            .entry(key.clone())
            .or_insert_with(|| {
                Arc::new(RateLimiter::keyed(self.quota))
            })
            .clone();

        match limiter.check() {
            Ok(_) => {
                // Request allowed
                (true, 0, Duration::ZERO) // remaining calculated from quota
            }
            Err(negative) => {
                let wait = negative.wait_time_from(governor::clock::DefaultClock::default().now());
                (false, 0, wait)
            }
        }
    }
}

/// Extract rate-limit key from request (priority: API key > JWT > IP)
fn extract_rate_limit_key(req: &Request) -> RateLimitKey {
    // 1. If HMAC-signed request → use API key ID
    if let Some(api_key_id) = req.extensions().get::<ApiKeyId>() {
        return RateLimitKey::ApiKey(api_key_id.0.clone());
    }

    // 2. If JWT-authenticated → use subject claim
    if let Some(claims) = req.extensions().get::<JwtClaims>() {
        return RateLimitKey::User(claims.sub.clone());
    }

    // 3. Fallback: client IP
    RateLimitKey::Ip(
        req.headers()
            .get("x-forwarded-for")
            .and_then(|v| v.to_str().ok())
            .unwrap_or("unknown")
            .split(',')
            .next()
            .unwrap_or("unknown")
            .trim()
            .to_string()
    )
}

/// Middleware: per-key rate limiting
pub async fn rate_limit_middleware(
    State(state): State<AppState>,
    req: Request,
    next: Next,
) -> Response {
    let key = extract_rate_limit_key(&req);

    // Select limiter config based on endpoint
    let limiter = select_limiter(&state, req.uri().path());

    let (allowed, remaining, retry_after) = limiter.check(key);

    if !allowed {
        return Response::builder()
            .status(StatusCode::TOO_MANY_REQUESTS)
            .header("RateLimit-Limit", limiter.quota_limit())
            .header("RateLimit-Remaining", "0")
            .header("RateLimit-Reset", retry_after.as_secs().to_string())
            .header("Retry-After", retry_after.as_secs().to_string())
            .body(Body::from(json!({
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please retry after the reset period.",
                "retry_after_seconds": retry_after.as_secs()
            }).to_string()))
            .unwrap();
    }

    let mut response = next.run(req).await;

    // Add rate-limit headers to all responses
    let headers = response.headers_mut();
    headers.insert("RateLimit-Limit", limiter.quota_limit().parse().unwrap());
    headers.insert("RateLimit-Remaining", remaining.to_string().parse().unwrap());

    response
}
```

### 1.4 Implementation — Python (FastAPI Internal Services)

```python
# src/middleware/rate_limit.py

import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class PerKeyRateLimiter:
    """Token-bucket rate limiter keyed by API key or user ID."""

    def __init__(self, rate: int, per: float, burst: int):
        self.rate = rate          # tokens per interval
        self.per = per            # interval in seconds (e.g., 60 for per-minute)
        self.burst = burst        # max burst
        self.buckets: dict[str, dict] = defaultdict(
            lambda: {"tokens": burst, "last": time.monotonic()}
        )

    def allow(self, key: str) -> tuple[bool, int, float]:
        """Check if key is allowed. Returns (allowed, remaining, retry_after)."""
        now = time.monotonic()
        bucket = self.buckets[key]

        # Refill tokens
        elapsed = now - bucket["last"]
        refill = elapsed * (self.rate / self.per)
        bucket["tokens"] = min(self.burst, bucket["tokens"] + refill)
        bucket["last"] = now

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return (True, int(bucket["tokens"]), 0.0)
        else:
            retry_after = (1 - bucket["tokens"]) / (self.rate / self.per)
            return (False, 0, retry_after)


# Limiter instances per endpoint class
LIMITERS = {
    "default": PerKeyRateLimiter(rate=100, per=60, burst=50),
    "trading": PerKeyRateLimiter(rate=30, per=60, burst=10),
    "market_data": PerKeyRateLimiter(rate=300, per=60, burst=100),
    "export": PerKeyRateLimiter(rate=10, per=60, burst=5),
}


def classify_endpoint(path: str) -> str:
    """Map request path to rate-limit class."""
    if path.startswith("/api/v1/orders"):
        return "trading"
    if path.startswith("/api/v1/market-data"):
        return "market_data"
    if path.startswith("/api/v1/export"):
        return "export"
    return "default"


class PerKeyRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract identity: API key > JWT > IP
        key = None
        if api_key_id := request.state.get("api_key_id"):
            key = f"apikey:{api_key_id}"
        elif user_id := request.state.get("jwt_sub"):
            key = f"user:{user_id}"
        else:
            key = f"ip:{request.client.host}"

        # Select limiter
        limiter_class = classify_endpoint(request.url.path)
        limiter = LIMITERS[limiter_class]

        allowed, remaining, retry_after = limiter.allow(key)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "retry_after_seconds": round(retry_after, 1),
                },
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["RateLimit-Remaining"] = str(remaining)
        return response
```

### 1.5 API Key Enforcement in Request Signing

Ensure the API key ID is extracted during HMAC verification and attached to the request context:

```python
# src/auth/request_signing.py

async def verify_hmac_signature(request: Request) -> str:
    """Verify HMAC-SHA256 signature and return API key ID."""
    api_key_id = request.headers.get("X-Api-Key-Id")
    signature = request.headers.get("X-Signature")
    timestamp = request.headers.get("X-Timestamp")

    if not all([api_key_id, signature, timestamp]):
        raise HTTPException(401, "Missing signature headers")

    # Replay protection: ±5 minutes
    ts = int(timestamp)
    if abs(time.time() - ts) > 300:
        raise HTTPException(401, "Request expired")

    # Fetch key from DB (includes hashed secret for verification)
    key_record = await get_api_key(api_key_id)
    if not key_record or key_record.revoked:
        raise HTTPException(401, "Invalid API key")

    # Verify HMAC
    payload = f"{request.method}\n{request.url.path}\n{timestamp}\n{await request.body()}"
    expected = hmac.new(
        key_record.secret_hash,  # retrieved from vault
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Invalid signature")

    # Attach to request state for rate limiting
    request.state.api_key_id = api_key_id
    return api_key_id
```

### 1.6 Verification Checklist

- [ ] API key ID extracted during HMAC verification and stored in request context
- [ ] Rate limit middleware reads API key ID from request context
- [ ] Per-key limiter uses `DashMap` (Rust) or `defaultdict` (Python) with cleanup
- [ ] Rate limit headers (`RateLimit-Limit`, `RateLimit-Remaining`, `Retry-After`) returned on all responses
- [ ] 429 response includes JSON error body with `retry_after_seconds`
- [ ] Key cleanup runs periodically (every 5 min) to prevent memory leaks
- [ ] Unit tests: key A's limit doesn't affect key B; burst works correctly

---

## 2. Global Rate Limits

**Finding:** No global ceiling — distributed botnet can overwhelm infrastructure even with per-key limits.

### 2.1 Solution Design

Add a **global rate limiter** at the gateway level that applies across all keys/IPs:

```
Request → Global Limit → Per-Key Limit → Endpoint Limit → Handler
```

Global limits protect infrastructure. Per-key limits protect fairness. Endpoint limits protect specific resources.

### 2.2 Configuration

```yaml
# config/rate_limits_global.yaml

global_limits:
  # Absolute ceilings — these are across ALL requesters
  total_api_requests:
    rate: 10000/1m
    description: "Infrastructure protection ceiling"

  total_auth_requests:
    rate: 1000/1m
    description: "Auth endpoint global ceiling"

  total_websocket_connections:
    max: 1000
    description: "Max concurrent WS connections system-wide"

  total_websocket_messages:
    rate: 10000/1m
    description: "Max WS messages per minute across all connections"

  total_export_requests:
    rate: 100/1m
    description: "Global export ceiling"

  # Per-IP auth brute-force protection (defense-in-depth)
  auth_per_ip:
    rate: 10/1m
    burst: 5
    block_duration: 15m
```

### 2.3 Implementation — Rust (Gateway Layer)

```rust
// src/middleware/global_rate_limit.rs

use std::sync::Arc;
use tokio::sync::Semaphore;
use std::num::NonZeroU32;
use governor::{Quota, RateLimiter, state::keyed::DefaultKeyedStateStore};

/// Global rate limiter — applies to ALL requests regardless of identity
pub struct GlobalRateLimiter {
    api_limiter: RateLimiter<(), DefaultKeyedStateStore<()>, DefaultClock>,
    auth_limiter: RateLimiter<(), DefaultKeyedStateStore<()>, DefaultClock>,
    ws_semaphore: Arc<Semaphore>,
    ws_message_limiter: RateLimiter<(), DefaultKeyedStateStore<()>, DefaultClock>,
    export_limiter: RateLimiter<(), DefaultKeyedStateStore<()>, DefaultClock>,
}

impl GlobalRateLimiter {
    pub fn new(config: &GlobalLimitConfig) -> Self {
        Self {
            api_limiter: RateLimiter::direct(
                Quota::per_minute(NonZeroU32::new(config.total_api_requests).unwrap())
            ),
            auth_limiter: RateLimiter::direct(
                Quota::per_minute(NonZeroU32::new(config.total_auth_requests).unwrap())
            ),
            ws_semaphore: Arc::new(Semaphore::new(config.total_websocket_connections)),
            ws_message_limiter: RateLimiter::direct(
                Quota::per_minute(NonZeroU32::new(config.total_websocket_messages).unwrap())
            ),
            export_limiter: RateLimiter::direct(
                Quota::per_minute(NonZeroU32::new(config.total_export_requests).unwrap())
            ),
        }
    }

    pub fn check_api(&self) -> bool {
        self.api_limiter.check().is_ok()
    }

    pub fn check_auth(&self) -> bool {
        self.auth_limiter.check().is_ok()
    }

    pub fn acquire_ws_connection(&self) -> Option<tokio::sync::OwnedSemaphorePermit> {
        self.ws_semaphore.clone().try_acquire_owned().ok()
    }

    pub fn check_ws_message(&self) -> bool {
        self.ws_message_limiter.check().is_ok()
    }

    pub fn check_export(&self) -> bool {
        self.export_limiter.check().is_ok()
    }
}

/// Middleware: global rate limiting (runs BEFORE per-key limiting)
pub async fn global_rate_limit_middleware(
    State(state): State<AppState>,
    req: Request,
    next: Next,
) -> Response {
    let path = req.uri().path();
    let limiter = &state.global_limiter;

    // Select global limiter based on endpoint category
    let allowed = if path.starts_with("/api/v1/auth/") {
        limiter.check_auth()
    } else if path.starts_with("/api/v1/export/") {
        limiter.check_export()
    } else if path.starts_with("/api/v1/") {
        limiter.check_api()
    } else {
        true  // Health checks, etc. are not limited
    };

    if !allowed {
        // Increment metric
        metrics::counter!("global_rate_limit_rejected", "path" => path.to_string()).increment(1);

        return Response::builder()
            .status(StatusCode::SERVICE_UNAVAILABLE)
            .header("Retry-After", "5")
            .body(Body::from(json!({
                "error": "service_overloaded",
                "message": "Server is under high load. Please retry shortly.",
                "retry_after_seconds": 5
            }).to_string()))
            .unwrap();
    }

    next.run(req).await
}
```

### 2.4 Metrics & Alerting

```rust
// Prometheus metrics for monitoring global limits

use metrics::{counter, gauge, histogram};

// Track rejections
counter!("global_rate_limit_rejected_total", "endpoint" => "auth").increment(1);
counter!("global_rate_limit_rejected_total", "endpoint" => "api").increment(1);

// Track utilization (periodic)
gauge!("global_rate_limit_utilization", "endpoint" => "api")
    .set(current_api_rate / max_api_rate * 100.0);

// Alert when utilization > 80%
// Alert on any rejection (indicates attack or capacity issue)
```

### 2.5 Monitoring Dashboard Queries

```promql
# Global rate limit utilization
rate(global_rate_limit_rejected_total[5m])

# Per-key rate limit hits
rate(per_key_rate_limit_rejected_total[5m])

# Total request rate
rate(http_requests_total[5m])

# Alert: global limit hit > 3 times in 5 minutes
# ALERT: Global rate limit hit — possible DDoS or capacity issue
```

### 2.6 Verification Checklist

- [ ] Global limiter runs BEFORE per-key limiter in middleware chain
- [ ] Auth endpoints have separate global ceiling (1000/min)
- [ ] WebSocket connections capped globally (1000 concurrent)
- [ ] 503 response returned (not 429) for global limit hits — signals infrastructure overload
- [ ] Prometheus metrics track rejections and utilization
- [ ] Alerts configured for >80% utilization and any rejection
- [ ] Global limits are configurable without code change (config file)

---

## 3. gRPC Internal Authentication

**Finding:** gRPC/IPC internal services have no specified authentication — zero-trust model is incomplete.

### 3.1 Solution Design

Implement **mutual TLS (mTLS)** for all gRPC internal services. Every service presents a certificate; every service validates the peer's certificate against the internal CA.

```
Service A ──mTLS──► Service B
  cert-A              cert-B
  validates B's cert  validates A's cert
```

### 3.2 Certificate Architecture

```
internal-ca (root, offline)
├── gateway-service (leaf cert, 24h rotation)
├── trading-engine (leaf cert, 24h rotation)
├── risk-manager (leaf cert, 24h rotation)
├── notification-engine (leaf cert, 24h rotation)
├── market-data-service (leaf cert, 24h rotation)
└── audit-log-service (leaf cert, 24h rotation)
```

### 3.3 Configuration

```yaml
# config/grpc_auth.yaml

grpc_services:
  tls:
    enabled: true
    mode: "mutual"                          # mTLS: both sides present certs
    ca_cert: "/etc/ssl/internal/ca.crt"     # Internal CA certificate
    cert: "/etc/ssl/internal/${SERVICE_NAME}.crt"   # Service leaf cert
    key: "/etc/ssl/internal/${SERVICE_NAME}.key"    # Service private key
    cert_rotation_hours: 24
    auto_reload: true                       # Watch cert files, reload on change

    # Allowed services (CN or SAN must match)
    allowed_clients:
      gateway:
        cn: "gateway-service.internal.alphastack.io"
        allowed_methods:
          - "trading.TradingService/*"
          - "marketdata.MarketDataService/*"
          - "risk.RiskService/CheckOrder"
      trading_engine:
        cn: "trading-engine.internal.alphastack.io"
        allowed_methods:
          - "risk.RiskService/*"
          - "audit.AuditService/LogTrade"

  # Fallback: if mTLS not available (dev/staging only)
  development:
    tls_enabled: false
    allowed_hosts: ["127.0.0.1", "::1"]
    require_header: "X-Internal-Auth"
    internal_token: "${INTERNAL_SERVICE_TOKEN}"  # From vault
```

### 3.4 Implementation — Rust (Tonic gRPC Server)

```rust
// src/grpc/auth.rs

use tonic::transport::{Certificate, Identity, ServerTlsConfig};
use tonic::{Request, Status, service::Interceptor};
use std::sync::Arc;

/// Configure mTLS for gRPC server
pub fn configure_mtls(config: &GrpcTlsConfig) -> Result<ServerTlsConfig, Box<dyn std::error::Error>> {
    let ca_cert = std::fs::read_to_string(&config.ca_cert)?;
    let cert = std::fs::read_to_string(&config.cert)?;
    let key = std::fs::read_to_string(&config.key)?;

    let identity = Identity::from_pem(cert, key);
    let ca = Certificate::from_pem(ca_cert);

    Ok(ServerTlsConfig::new()
        .identity(identity)
        .client_ca_root(ca)
        .client_auth_optional(false))  // REQUIRE client cert
}

/// Interceptor: validate client certificate and enforce method-level access
pub struct GrpcAuthInterceptor {
    allowed_clients: Arc<HashMap<String, Vec<String>>>,
}

impl Interceptor for GrpcAuthInterceptor {
    fn call(&mut self, request: Request<()>) -> Result<Request<()>, Status> {
        // Extract client CN from TLS peer info
        let peer_certs = request
            .peer_certs()
            .ok_or_else(|| Status::unauthenticated("No client certificate provided"))?;

        let client_cn = extract_cn(&peer_certs[0])
            .ok_or_else(|| Status::unauthenticated("Cannot extract CN from certificate"))?;

        // Validate client is in allowed list
        let method = request.metadata()
            .get("grpc-method")
            .and_then(|v| v.to_str().ok())
            .unwrap_or("unknown");

        let allowed_methods = self.allowed_clients
            .get(&client_cn)
            .ok_or_else(|| Status::permission_denied(
                format!("Service '{}' not authorized", client_cn)
            ))?;

        // Check method-level access (supports wildcard: "service/*")
        let authorized = allowed_methods.iter().any(|pattern| {
            if pattern.ends_with("/*") {
                let prefix = &pattern[..pattern.len() - 1];
                method.starts_with(prefix)
            } else {
                pattern == method
            }
        });

        if !authorized {
            return Err(Status::permission_denied(
                format!("Service '{}' not authorized for method '{}'", client_cn, method)
            ));
        }

        // Attach identity to extensions for downstream use
        request.extensions_mut().insert(ServiceIdentity(client_cn));
        Ok(request)
    }
}

/// Start gRPC server with mTLS
pub async fn start_grpc_server(config: &GrpcConfig) -> Result<(), Box<dyn std::error::Error>> {
    let tls_config = configure_mtls(&config.tls)?;
    let interceptor = GrpcAuthInterceptor {
        allowed_clients: Arc::new(config.allowed_clients.clone()),
    };

    Server::builder()
        .tls_config(tls_config)?
        .layer(tonic::service::interceptor(interceptor))
        .add_service(TradingServiceServer::new(trading_impl))
        .add_service(MarketDataServiceServer::new(market_data_impl))
        .add_service(RiskServiceServer::new(risk_impl))
        .serve(config.listen_addr.parse()?)
        .await?;

    Ok(())
}
```

### 3.5 Certificate Rotation

```rust
// src/grpc/cert_rotation.rs

use notify::{RecommendedWatcher, RecursiveMode, Watcher};
use std::sync::Arc;
use tokio::sync::RwLock;

/// Auto-rotate certificates when files change on disk
pub async fn watch_cert_rotation(
    cert_path: &str,
    key_path: &str,
    tls_config: Arc<RwLock<ServerTlsConfig>>,
) -> notify::Result<()> {
    let (tx, rx) = std::sync::mpsc::channel();
    let mut watcher = RecommendedWatcher::new(tx, notify::Config::default())?;

    watcher.watch(cert_path.as_ref(), RecursiveMode::NonRecursive)?;
    watcher.watch(key_path.as_ref(), RecursiveMode::NonRecursive)?;

    // Vault agent writes new certs every 24h; this picks them up
    loop {
        if rx.recv().is_ok() {
            match reload_identity(cert_path, key_path) {
                Ok(identity) => {
                    let mut config = tls_config.write().await;
                    *config = ServerTlsConfig::new().identity(identity);
                    tracing::info!("TLS certificate reloaded");
                }
                Err(e) => {
                    tracing::error!("Failed to reload TLS cert: {}", e);
                    metrics::counter!("cert_reload_failures").increment(1);
                }
            }
        }
    }
}
```

### 3.6 Development/Staging Fallback

For environments without a full PKI, use a shared internal token:

```rust
/// Fallback: internal token authentication (dev/staging only)
pub struct InternalTokenInterceptor {
    expected_token: String,
}

impl Interceptor for InternalTokenInterceptor {
    fn call(&mut self, request: Request<()>) -> Result<Request<()>, Status> {
        let token = request
            .metadata()
            .get("X-Internal-Auth")
            .and_then(|v| v.to_str().ok())
            .unwrap_or("");

        if !hmac::verify(token, &self.expected_token) {
            return Err(Status::unauthenticated("Invalid internal token"));
        }

        Ok(request)
    }
}
```

### 3.7 Verification Checklist

- [ ] mTLS enabled for all gRPC services in production
- [ ] Client certificate required (not optional)
- [ ] CN extracted from peer cert and validated against allowed-clients list
- [ ] Method-level authorization enforced (not just service-level)
- [ ] Certificate rotation: Vault agent writes new certs every 24h, watcher picks them up
- [ ] Prometheus metric for cert reload failures
- [ ] Dev/staging fallback: internal token auth (no mTLS), only on localhost
- [ ] Integration test: reject connection without valid cert
- [ ] Integration test: reject connection with cert from wrong service

---

## 4. WebSocket Authentication Gaps

**Finding:** JWT passing mechanism, token refresh, heartbeat, and idle timeout not specified.

### 4.1 Solution Design

```
Client                          Server
  │                                │
  │──── WS Upgrade ──────────────►│  Origin + Sec-WebSocket-Protocol: jwt.<token>
  │◄─── 101 Switching Protocols ──│  (token validated during upgrade)
  │                                │
  │◄─── heartbeat: ping ─────────│  Every 30s
  │──── heartbeat: pong ─────────►│  Must respond within 10s
  │                                │
  │◄─── auth:refresh_required ───│  2 min before JWT expiry
  │──── auth:refresh ────────────►│  { "new_token": "<jwt>" }
  │◄─── auth:refresh_ok ─────────│  Connection continues
  │                                │
  │ (idle 300s)                    │
  │◄─── close: idle_timeout ─────│  Connection closed
```

### 4.2 Configuration

```yaml
# config/websocket.yaml

websocket:
  auth:
    method: "subprotocol"           # JWT via Sec-WebSocket-Protocol header
    token_refresh:
      enabled: true
      warn_before_expiry: 120s      # Tell client to refresh 2 min before expiry
      refresh_timeout: 30s          # Client has 30s to send new token
      strategy: "reconnect"         # "reconnect" | "in_place" — reconnect is simpler
    origin_validation: true         # Validate Origin header on upgrade
    allowed_origins:                # Same as CORS config
      - "https://app.alphastack.io"
      - "https://staging.alphastack.io"
      - "tauri://localhost"
      - "https://tauri.localhost"

  heartbeat:
    interval: 30s                   # Server sends ping every 30s
    timeout: 10s                    # Client must pong within 10s
    max_missed: 3                   # Close after 3 missed pongs

  idle_timeout: 300s                # Close connections with no activity for 5 min
  max_connections_per_user: 5       # Per-user concurrent connection limit
  max_connections_global: 1000      # System-wide connection limit
  message_rate: 60/1m               # Per-connection message rate limit
  message_size_max: 65536           # 64KB max message size
```

### 4.3 Implementation — Rust (WebSocket Server)

```rust
// src/websocket/auth.rs

use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::{ConnectInfo, State};
use axum::response::IntoResponse;
use jsonwebtoken::{decode, DecodingKey, Validation};
use std::net::SocketAddr;
use tokio::time::{interval, Duration};
use futures::{SinkExt, StreamExt};

/// JWT claims for WebSocket authentication
#[derive(Debug, serde::Deserialize)]
struct WsClaims {
    sub: String,          // user ID
    exp: usize,           // expiry timestamp
    aud: String,          // audience
    device_id: String,    // device binding
}

/// WebSocket upgrade handler with authentication
pub async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_ws(socket, state, addr))
}

/// Handle authenticated WebSocket connection
async fn handle_ws(mut socket: WebSocket, state: AppState, addr: SocketAddr) {
    // ── Step 1: Extract and validate JWT from first message ──
    let user_id = match authenticate_ws(&mut socket, &state).await {
        Ok(uid) => uid,
        Err(e) => {
            let _ = socket.send(Message::Close(Some(
                CloseFrame { code: 4001, reason: format!("Auth failed: {}", e).into() }
            ))).await;
            return;
        }
    };

    // ── Step 2: Check concurrent connection limit ──
    if state.ws_connections.user_count(&user_id) >= state.config.ws.max_connections_per_user {
        let _ = socket.send(Message::Close(Some(
            CloseFrame { code: 4003, reason: "Connection limit reached".into() }
        ))).await;
        return;
    }
    state.ws_connections.add(&user_id);
    let _guard = WsConnectionGuard(state.ws_connections.clone(), user_id.clone());

    // ── Step 3: Heartbeat + message processing loop ──
    let mut heartbeat = interval(Duration::from_secs(30));
    let mut missed_pongs: u8 = 0;
    let max_missed: u8 = 3;
    let mut last_activity = tokio::time::Instant::now();
    let idle_timeout = Duration::from_secs(300);

    loop {
        tokio::select! {
            // Server-initiated ping
            _ = heartbeat.tick() => {
                if missed_pongs >= max_missed {
                    tracing::warn!("User {} heartbeat timeout", user_id);
                    let _ = socket.send(Message::Close(Some(
                        CloseFrame { code: 4002, reason: "Heartbeat timeout".into() }
                    ))).await;
                    break;
                }
                if socket.send(Message::Ping(vec![])).await.is_err() {
                    break;
                }
                missed_pongs += 1;
            }

            // Client message
            msg = socket.next() => {
                match msg {
                    Some(Ok(Message::Pong(_))) => {
                        missed_pongs = 0;
                        last_activity = tokio::time::Instant::now();
                    }
                    Some(Ok(Message::Text(text))) => {
                        last_activity = tokio::time::Instant::now();

                        // Validate and process message (see §7)
                        match handle_ws_message(&text, &user_id, &state).await {
                            Ok(response) => {
                                if let Err(e) = socket.send(Message::Text(response)).await {
                                    tracing::error!("WS send error: {}", e);
                                    break;
                                }
                            }
                            Err(e) => {
                                let _ = socket.send(Message::Text(
                                    json!({"error": e.to_string()}).to_string()
                                )).await;
                            }
                        }
                    }
                    Some(Ok(Message::Close(_))) => break,
                    Some(Err(e)) => {
                        tracing::error!("WS error for user {}: {}", user_id, e);
                        break;
                    }
                    None => break,
                    _ => {} // Binary, Ping handled automatically
                }
            }
        }

        // Check idle timeout
        if last_activity.elapsed() > idle_timeout {
            tracing::info!("User {} idle timeout", user_id);
            let _ = socket.send(Message::Close(Some(
                CloseFrame { code: 4004, reason: "Idle timeout".into() }
            ))).await;
            break;
        }
    }
}

/// Authenticate WebSocket connection via first message
async fn authenticate_ws(
    socket: &mut WebSocket,
    state: &AppState,
) -> Result<String, WsAuthError> {
    // Wait for first message (must be auth message, timeout 10s)
    let first_msg = tokio::time::timeout(
        Duration::from_secs(10),
        socket.next()
    ).await
        .map_err(|_| WsAuthError::Timeout)?
        .ok_or(WsAuthError::ConnectionClosed)?
        .map_err(|e| WsAuthError::Protocol(e))?;

    match first_msg {
        Message::Text(text) => {
            let msg: serde_json::Value = serde_json::from_str(&text)
                .map_err(|_| WsAuthError::InvalidFormat)?;

            let msg_type = msg.get("type")
                .and_then(|v| v.as_str())
                .ok_or(WsAuthError::InvalidFormat)?;

            if msg_type != "auth" {
                return Err(WsAuthError::ExpectedAuth);
            }

            let token = msg.get("token")
                .and_then(|v| v.as_str())
                .ok_or(WsAuthError::MissingToken)?;

            // Validate JWT
            let claims = decode::<WsClaims>(
                token,
                &DecodingKey::from_rsa_pem(&state.jwt_public_key)?,
                &Validation::new(jsonwebtoken::Algorithm::RS256),
            ).map_err(|e| WsAuthError::InvalidToken(e.to_string()))?;

            // Validate audience
            if claims.claims.aud != "alphastack-app" {
                return Err(WsAuthError::InvalidAudience);
            }

            // Send auth success
            socket.send(Message::Text(
                json!({
                    "type": "auth_ok",
                    "user_id": claims.claims.sub,
                    "expires_at": claims.claims.exp
                }).to_string()
            )).await.map_err(|e| WsAuthError::SendFailed(e))?;

            Ok(claims.claims.sub)
        }
        _ => Err(WsAuthError::ExpectedTextMessage),
    }
}

#[derive(Debug)]
enum WsAuthError {
    Timeout,
    ConnectionClosed,
    Protocol(axum::Error),
    InvalidFormat,
    ExpectedAuth,
    MissingToken,
    InvalidToken(String),
    InvalidAudience,
    ExpectedTextMessage,
    SendFailed(axum::Error),
}
```

### 4.4 Token Refresh Flow

```rust
// src/websocket/token_refresh.rs

/// Notify client when JWT is about to expire
async fn check_token_expiry(
    socket: &mut WebSocket,
    user_id: &str,
    token_exp: usize,
    state: &AppState,
) -> Result<(), WsError> {
    let now = chrono::Utc::now().timestamp() as usize;
    let warn_at = token_exp - 120; // 2 minutes before expiry

    if now >= warn_at && now < token_exp {
        // Send refresh warning
        socket.send(Message::Text(json!({
            "type": "auth:refresh_required",
            "reason": "token_expiring",
            "expires_at": token_exp,
            "action": "reconnect_with_new_token"
        }).to_string())).await?;

        // Wait for client to send new token (30s timeout)
        let refresh_msg = tokio::time::timeout(
            Duration::from_secs(30),
            socket.next()
        ).await;

        match refresh_msg {
            Some(Ok(Ok(Message::Text(text)))) => {
                let msg: serde_json::Value = serde_json::from_str(&text)?;
                if msg.get("type").and_then(|v| v.as_str()) == Some("auth:refresh") {
                    if let Some(new_token) = msg.get("token").and_then(|v| v.as_str()) {
                        // Validate new token
                        let claims = decode::<WsClaims>(
                            new_token,
                            &DecodingKey::from_rsa_pem(&state.jwt_public_key)?,
                            &Validation::new(jsonwebtoken::Algorithm::RS256),
                        )?;

                        if claims.claims.sub == user_id {
                            socket.send(Message::Text(json!({
                                "type": "auth:refresh_ok",
                                "expires_at": claims.claims.exp
                            }).to_string())).await?;
                            return Ok(());
                        }
                    }
                }
                // Invalid refresh → close
                socket.send(Message::Close(Some(
                    CloseFrame { code: 4001, reason: "Invalid refresh".into() }
                ))).await?;
                return Err(WsError::AuthRefreshFailed);
            }
            _ => {
                // Timeout or error → close
                socket.send(Message::Close(Some(
                    CloseFrame { code: 4001, reason: "Refresh timeout".into() }
                ))).await?;
                return Err(WsError::AuthRefreshFailed);
            }
        }
    }

    if now >= token_exp {
        socket.send(Message::Close(Some(
            CloseFrame { code: 4001, reason: "Token expired".into() }
        ))).await?;
        return Err(WsError::TokenExpired);
    }

    Ok(())
}
```

### 4.5 Origin Validation

```rust
/// Validate Origin header during WebSocket upgrade
fn validate_ws_origin(headers: &HeaderMap, config: &WsConfig) -> bool {
    if !config.auth.origin_validation {
        return true; // Skip in dev
    }

    let origin = headers.get("origin")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");

    config.auth.allowed_origins.iter().any(|allowed| allowed == origin)
}

/// Middleware: reject WS upgrade with bad Origin
pub async fn ws_origin_guard(
    headers: HeaderMap,
    State(state): State<AppState>,
    request: Request,
    next: Next,
) -> Response {
    if !validate_ws_origin(&headers, &state.config.ws) {
        return Response::builder()
            .status(StatusCode::FORBIDDEN)
            .body(Body::from("Origin not allowed"))
            .unwrap();
    }
    next.run(request).await
}
```

### 4.6 Verification Checklist

- [ ] JWT passed via first message (not query param — query params end up in logs)
- [ ] JWT validated: signature, expiry, audience, device binding
- [ ] Auth timeout: close connection if no auth message within 10s
- [ ] Heartbeat: server pings every 30s, client must pong within 10s
- [ ] Max 3 missed pongs → connection closed
- [ ] Idle timeout: 300s of no activity → connection closed
- [ ] Token expiry warning sent 2 min before JWT expires
- [ ] Client must reconnect with new token (or send auth:refresh)
- [ ] Origin validated on upgrade
- [ ] Per-user connection limit (5) enforced
- [ ] Close codes: 4001 (auth), 4002 (heartbeat), 4003 (limit), 4004 (idle)
- [ ] Integration test: connect without auth → rejected
- [ ] Integration test: expired JWT → rejected
- [ ] Integration test: heartbeat timeout → connection closed

---

## 5. SSRF Prevention

**Finding:** External data fetching (webhooks, RSS, broker APIs) can hit private IPs — cloud metadata, internal services.

### 5.1 Solution Design

**Layer 1: URL validation at input** — reject private IPs before any request.  
**Layer 2: DNS resolution check** — resolve hostname, verify IP is not private.  
**Layer 3: Network-level controls** — egress firewall blocks private ranges.  
**Layer 4: Timeout + redirect limits** — prevent slow-loris and redirect-based bypass.

### 5.2 Blocked Ranges

```yaml
# config/ssrf_protection.yaml

ssrf_protection:
  blocked_ip_ranges:
    # RFC 1918 private
    - "10.0.0.0/8"
    - "172.16.0.0/12"
    - "192.168.0.0/16"
    # Loopback
    - "127.0.0.0/8"
    - "::1/128"
    # Link-local
    - "169.254.0.16"
    - "fe80::/10"
    # Cloud metadata
    - "169.254.169.254/32"    # AWS/GCP/Azure metadata
    # Reserved
    - "0.0.0.0/8"
    - "100.64.0.0/10"         # Carrier-grade NAT
    - "192.0.0.0/24"
    - "192.0.2.0/24"
    - "198.51.100.0/24"
    - "203.0.113.0/24"
    - "224.0.0.0/4"           # Multicast
    - "::/128"                 # Unspecified

  blocked_schemes:
    - "file"
    - "ftp"
    - "gopher"
    - "dict"
    - "netdoc"

  allowed_schemes:
    - "https"
    - "http"                  # Only for known third-party APIs that don't support HTTPS

  request_limits:
    timeout: 10s
    max_redirects: 0          # NO redirects — attacker can redirect to private IP
    max_response_size: 1048576  # 1MB
    allowed_content_types:
      - "application/json"
      - "text/html"
      - "text/xml"
      - "application/xml"
```

### 5.3 Implementation — Rust

```rust
// src/security/ssrf.rs

use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};
use cidr_utils::cidr::IpCidr;
use reqwest::Client;
use url::Url;
use trust_dns_resolver::TokioAsyncResolver;

/// SSRF-safe HTTP client
pub struct SafeHttpClient {
    client: Client,
    blocked_ranges: Vec<IpCidr>,
    allowed_schemes: Vec<String>,
    resolver: TokioAsyncResolver,
}

impl SafeHttpClient {
    pub fn new(config: &SsrfConfig) -> Result<Self, Box<dyn std::error::Error>> {
        let client = Client::builder()
            .timeout(Duration::from_secs(config.request_limits.timeout))
            .redirect(reqwest::redirect::Policy::none())  // NO redirects
            .build()?;

        let blocked_ranges = config.blocked_ip_ranges
            .iter()
            .map(|s| s.parse::<IpCidr>())
            .collect::<Result<Vec<_>, _>>()?;

        let resolver = TokioAsyncResolver::tokio_from_system_conf()?;

        Ok(Self {
            client,
            blocked_ranges,
            allowed_schemes: config.allowed_schemes.clone(),
            resolver,
        })
    }

    /// Fetch URL with SSRF protection
    pub async fn safe_get(&self, url_str: &str) -> Result<SafeResponse, SsrfError> {
        // ── Layer 1: Parse and validate URL ──
        let url = Url::parse(url_str).map_err(|_| SsrfError::InvalidUrl)?;

        // Validate scheme
        if !self.allowed_schemes.contains(&url.scheme().to_string()) {
            return Err(SsrfError::BlockedScheme(url.scheme().to_string()));
        }

        let host = url.host_str().ok_or(SsrfError::NoHost)?;

        // ── Layer 2: Check if host is a literal IP ──
        if let Ok(ip) = host.parse::<IpAddr>() {
            if self.is_blocked_ip(&ip) {
                return Err(SsrfError::BlockedIp(ip));
            }
        } else {
            // ── Layer 3: DNS resolution — check ALL resolved IPs ──
            let response = self.resolver.lookup_ip(host).await
                .map_err(|_| SsrfError::DnsResolutionFailed)?;

            for ip in response.iter() {
                if self.is_blocked_ip(&ip) {
                    return Err(SsrfError::BlockedIp(ip));
                }
            }
        }

        // ── Layer 4: Make request with limits ──
        let response = self.client
            .get(url_str)
            .header("User-Agent", "AlphaStack-Internal/1.0")
            .send()
            .await
            .map_err(SsrfError::RequestFailed)?;

        // Check content type
        let content_type = response.headers()
            .get("content-type")
            .and_then(|v| v.to_str().ok())
            .unwrap_or("");

        // Enforce content type
        // (checked against config.allowed_content_types)

        Ok(SafeResponse {
            status: response.status().as_u16(),
            headers: response.headers().clone(),
            body: response.bytes().await.map_err(SsrfError::RequestFailed)?,
        })
    }

    /// Check if IP is in any blocked range
    fn is_blocked_ip(&self, ip: &IpAddr) -> bool {
        // Always block these regardless of config
        match ip {
            IpAddr::V4(v4) => {
                if v4.is_loopback() || v4.is_link_local() || v4.is_broadcast() {
                    return true;
                }
                if v4.octets() == [169, 254, 169, 254] {
                    return true; // Cloud metadata
                }
            }
            IpAddr::V6(v6) => {
                if v6.is_loopback() {
                    return true;
                }
            }
        }

        // Check against configured ranges
        self.blocked_ranges.iter().any(|range| range.contains(ip))
    }
}

/// Double-check: DNS can be rebinding. Re-resolve and check after connect.
/// This prevents TOCTOU attacks where DNS resolves to a public IP first,
/// then a private IP on retry.
pub async fn safe_get_with_dns_pin(
    client: &SafeHttpClient,
    url_str: &str,
) -> Result<SafeResponse, SsrfError> {
    let url = Url::parse(url_str).map_err(|_| SsrfError::InvalidUrl)?;
    let host = url.host_str().ok_or(SsrfError::NoHost)?;

    // Resolve DNS once and pin the IP
    let ips = client.resolver.lookup_ip(host).await
        .map_err(|_| SsrfError::DnsResolutionFailed)?;

    let safe_ip = ips.iter()
        .find(|ip| !client.is_blocked_ip(ip))
        .ok_or(SsrfError::NoSafeIp)?;

    // Build URL with pinned IP, set Host header
    let pinned_url = format!("{}://{}:{}{}",
        url.scheme(),
        safe_ip,
        url.port().unwrap_or(443),
        url.path()
    );

    client.client
        .get(&pinned_url)
        .header("Host", host)  // Preserve original Host header for SNI/virtual hosts
        .header("User-Agent", "AlphaStack-Internal/1.0")
        .send()
        .await
        .map_err(SsrfError::RequestFailed)?
        .into_safe_response()
        .await
}
```

### 5.4 Network-Level Controls (Infrastructure)

```bash
# iptables rules — block SSRF at network level (defense-in-depth)
# Applied to service account / container that makes outbound requests

# Allow HTTPS to external
iptables -A OUTPUT -p tcp --dport 443 -d 0.0.0.0/0 -j ACCEPT

# Block metadata endpoint
iptables -A OUTPUT -d 169.254.169.254/32 -j DROP

# Block private ranges
iptables -A OUTPUT -d 10.0.0.0/8 -j DROP
iptables -A OUTPUT -d 172.16.0.0/12 -j DROP
iptables -A OUTPUT -d 192.168.0.0/16 -j DROP
iptables -A OUTPUT -d 127.0.0.0/8 -j DROP

# Log blocked attempts
iptables -A OUTPUT -d 169.254.169.254/32 -j LOG --log-prefix "SSRF_BLOCKED: "
```

### 5.5 Webhook URL Allowlist

```python
# For webhook registration, use an allowlist approach

class WebhookUrlValidator:
    """Validate webhook URLs against allowlist + SSRF checks."""

    # Known safe webhook domains
    ALLOWED_DOMAINS = {
        "hooks.slack.com",
        "discord.com",
        "api.telegram.org",
        "hooks.zapier.com",
        "webhook.site",  # For testing only, gated behind feature flag
    }

    def validate(self, url: str) -> str:
        parsed = urlparse(url)

        # Must be HTTPS
        if parsed.scheme != "https":
            raise ValueError("Webhook URL must use HTTPS")

        # Must be in allowlist
        hostname = parsed.hostname
        if not any(hostname == d or hostname.endswith(f".{d}")
                   for d in self.ALLOWED_DOMAINS):
            raise ValueError(f"Domain '{hostname}' not in webhook allowlist")

        # Additional SSRF check
        ip = socket.gethostbyname(hostname)
        if self._is_private_ip(ip):
            raise ValueError("Resolved IP is private")

        return url
```

### 5.6 Verification Checklist

- [ ] All blocked IP ranges configured (RFC 1918, link-local, cloud metadata, loopback)
- [ ] DNS resolution checked BEFORE making HTTP request
- [ ] DNS pinning implemented (resolve once, use pinned IP) to prevent rebinding
- [ ] No redirects allowed (`redirect::Policy::none()`)
- [ ] Timeout enforced (10s)
- [ ] Content-type validation on responses
- [ ] Webhook URLs validated against allowlist
- [ ] Network-level egress rules in place (iptables / security group)
- [ ] Unit test: `http://169.254.169.254/...` → blocked
- [ ] Unit test: `http://127.0.0.1/...` → blocked
- [ ] Unit test: `http://internal-service.local/` → blocked (if resolves to private IP)
- [ ] Unit test: DNS rebinding → blocked
- [ ] Unit test: `file:///etc/passwd` → blocked
- [ ] Unit test: redirect to private IP → blocked

---

## 6. IDOR Prevention

**Finding:** Resource access checks authentication but not ownership — accessing `/orders/<other_user_order>` works.

### 6.1 Solution Design

**Every resource access** must verify `resource.owner_id == jwt.sub`. This is enforced via:

1. **Database query scoping** — all queries include `WHERE owner_id = :user_id`
2. **Middleware-level check** — generic ownership verification after resource fetch
3. **UUID v4 identifiers** — prevent enumeration (already in place)

### 6.2 Implementation — Query Scoping (Primary Defense)

```python
# src/repositories/order_repository.py

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID


class OrderRepository:
    """Repository pattern: all queries scoped to owner."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, order_id: UUID, user_id: UUID) -> Order | None:
        """Fetch order ONLY if owned by user. This is the ONLY way to get an order."""
        result = await self.session.execute(
            select(Order).where(
                and_(
                    Order.id == order_id,
                    Order.user_id == user_id,  # ← Ownership check in query
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Order]:
        """List orders for a specific user. No way to list another user's orders."""
        query = select(Order).where(Order.user_id == user_id)
        if status:
            query = query.where(Order.status == status)
        query = query.order_by(Order.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, order_id: UUID, user_id: UUID, **kwargs) -> Order | None:
        """Update order ONLY if owned by user."""
        order = await self.get_by_id(order_id, user_id)
        if not order:
            return None

        for key, value in kwargs.items():
            setattr(order, key, value)

        await self.session.commit()
        return order
```

### 6.3 Implementation — Generic Ownership Middleware

```python
# src/middleware/authorization.py

from functools import wraps
from fastapi import HTTPException, Request
from uuid import UUID


def require_ownership(resource_type: str, id_param: str = "id"):
    """
    Decorator: verify the authenticated user owns the requested resource.

    Usage:
        @router.get("/orders/{id}")
        @require_ownership("order", "id")
        async def get_order(id: UUID, request: Request):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request, **kwargs):
            user_id = request.state.jwt_sub
            resource_id = kwargs.get(id_param)

            if not resource_id:
                raise HTTPException(400, "Missing resource ID")

            # Look up resource with ownership check
            resource = await get_resource_with_owner_check(
                resource_type, resource_id, user_id
            )

            if not resource:
                # Return 404 (not 403) to prevent IDOR enumeration
                raise HTTPException(404, f"{resource_type} not found")

            # Attach resource to request for handler use
            request.state.resource = resource
            return await func(*args, request=request, **kwargs)

        return wrapper
    return decorator


async def get_resource_with_owner_check(
    resource_type: str,
    resource_id: UUID,
    user_id: UUID,
) -> dict | None:
    """Fetch resource and verify ownership in one query."""
    repositories = {
        "order": OrderRepository,
        "position": PositionRepository,
        "signal": SignalRepository,
        "account": AccountRepository,
        "webhook": WebhookRepository,
    }

    repo_class = repositories.get(resource_type)
    if not repo_class:
        raise ValueError(f"Unknown resource type: {resource_type}")

    async with get_db_session() as session:
        repo = repo_class(session)
        resource = await repo.get_by_id(resource_id, user_id)
        return resource
```

### 6.4 API Endpoint Pattern

```python
# src/api/orders.py

from fastapi import APIRouter, Depends, Request
from uuid import UUID

router = APIRouter(prefix="/api/v1/orders")


@router.get("/{order_id}")
@require_ownership("order", "order_id")
async def get_order(
    order_id: UUID,
    request: Request,
    # Ownership already verified by decorator
):
    """Get order details. Only returns orders owned by the authenticated user."""
    return OrderResponse.model_validate(request.state.resource)


@router.get("/")
async def list_orders(
    request: Request,
    status: str | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List orders for the authenticated user. No way to see other users' orders."""
    repo = OrderRepository(request.state.db_session)
    orders = await repo.list_by_user(
        user_id=request.state.jwt_sub,  # Always scoped to JWT subject
        status=status,
        limit=limit,
        offset=offset,
    )
    return [OrderResponse.model_validate(o) for o in orders]


@router.put("/{order_id}")
@require_ownership("order", "order_id")
async def update_order(
    order_id: UUID,
    body: UpdateOrderRequest,
    request: Request,
):
    """Update order. Only if owned by authenticated user."""
    repo = OrderRepository(request.state.db_session)
    updated = await repo.update(
        order_id=order_id,
        user_id=request.state.jwt_sub,
        **body.model_dump(exclude_unset=True),
    )
    if not updated:
        raise HTTPException(404, "Order not found")
    return OrderResponse.model_validate(updated)


@router.delete("/{order_id}")
@require_ownership("order", "order_id")
async def cancel_order(
    order_id: UUID,
    request: Request,
):
    """Cancel order. Only if owned by authenticated user."""
    repo = OrderRepository(request.state.db_session)
    cancelled = await repo.update(
        order_id=order_id,
        user_id=request.state.jwt_sub,
        status="cancelled",
    )
    if not cancelled:
        raise HTTPException(404, "Order not found")
    return {"status": "cancelled"}
```

### 6.5 Additional Protections

```python
# 1. Mass assignment prevention — separate input/output models

class CreateOrderRequest(BaseModel):
    """Input model: only user-settable fields."""
    model_config = ConfigDict(extra="forbid")  # Reject unknown fields

    symbol: str = Field(..., pattern=r'^[A-Z]{3,6}/[A-Z]{3,6}$')
    side: str = Field(..., pattern=r'^(buy|sell)$')
    order_type: str = Field(..., pattern=r'^(market|limit|stop)$')
    quantity: float = Field(..., gt=0, le=1_000_000)
    price: float | None = Field(None, gt=0)
    stop_loss: float | None = Field(None, gt=0)
    take_profit: float | None = Field(None, gt=0)
    # NO user_id, account_id, status, balance fields


class OrderResponse(BaseModel):
    """Output model: includes server-generated fields."""
    id: UUID
    user_id: UUID      # Read-only, set by server
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None
    status: str        # Read-only, set by server
    created_at: datetime
    updated_at: datetime


# 2. Rate limit per-resource to prevent enumeration
# (Even with UUIDs, rate-limit resource access)
@router.get("/{order_id}")
@require_ownership("order", "order_id")
@rate_limit(rate="60/1m", key_source="jwt_sub")
async def get_order(...):
    ...

# 3. Audit logging for ownership violations
async def log_idor_attempt(user_id: UUID, resource_type: str, resource_id: UUID):
    """Log attempted access to another user's resource."""
    await audit_log.warning(
        "IDOR attempt",
        user_id=str(user_id),
        resource_type=resource_type,
        resource_id=str(resource_id),
        action="access_denied",
        severity="high",
    )
```

### 6.6 Verification Checklist

- [ ] ALL database queries scoped to `user_id = :jwt_sub`
- [ ] Repository pattern: no unscoped queries exist
- [ ] `require_ownership` decorator on all resource endpoints
- [ ] 404 returned (not 403) for unauthorized resource access — prevents enumeration
- [ ] `extra="forbid"` on all input Pydantic models — blocks mass assignment
- [ ] Separate input models (CreateOrderRequest) and output models (OrderResponse)
- [ ] UUID v4 for all resource IDs — prevents enumeration
- [ ] Audit log for ownership violation attempts
- [ ] Unit test: user A cannot read user B's order → 404
- [ ] Unit test: user A cannot update user B's order → 404
- [ ] Unit test: user A cannot delete user B's order → 404
- [ ] Unit test: mass assignment with `{"user_id": "admin"}` → rejected by Pydantic
- [ ] Integration test: enumerate orders by sequential UUID → blocked (UUIDs are random)

---

## 7. WebSocket Message Validation

**Finding:** REST endpoints have Pydantic validation; WebSocket messages do not.

### 7.1 Solution Design

All WebSocket messages must be validated against strict schemas **before processing**. Invalid messages are rejected with an error response. This prevents injection, type confusion, and oversized payloads.

### 7.2 Message Schema Definitions

```python
# src/websocket/schemas.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal, Any
from uuid import UUID


# ── Base message type ──

class WSMessage(BaseModel):
    """Base WebSocket message — all messages extend this."""
    model_config = ConfigDict(extra="forbid")  # Reject unknown fields

    type: str = Field(..., min_length=1, max_length=50)
    id: Optional[str] = Field(None, max_length=36)  # Client message ID for correlation


# ── Auth messages ──

class WSAuthMessage(WSMessage):
    type: Literal["auth"]
    token: str = Field(..., min_length=10, max_length=4096)


class WSAuthRefreshMessage(WSMessage):
    type: Literal["auth:refresh"]
    token: str = Field(..., min_length=10, max_length=4096)


# ── Subscription messages ──

class WSSubscribeMessage(WSMessage):
    type: Literal["subscribe"]
    channel: str = Field(
        ...,
        pattern=r'^[a-z]+\.[a-z]+(\.[a-z]+)?$',
        description="Channel pattern: e.g., 'market.EUR/USD', 'orders.all', 'signals.active'"
    )


class WSUnsubscribeMessage(WSMessage):
    type: Literal["unsubscribe"]
    channel: str = Field(
        ...,
        pattern=r'^[a-z]+\.[a-z]+(\.[a-z]+)?$',
    )


# ── Command messages ──

class WSCommandMessage(WSMessage):
    type: Literal["command"]
    command: str = Field(
        ...,
        pattern=r'^(positions|balance|pnl|pause|resume|close|close_all)$',
    )
    args: Optional[dict[str, Any]] = None


class WSCloseCommand(WSCommandMessage):
    """Close specific position."""
    command: Literal["close"]
    args: dict = Field(...)

    @validator("args")
    def validate_args(cls, v):
        if "position_id" not in v:
            raise ValueError("position_id required")
        # Validate position_id is a UUID
        UUID(v["position_id"])
        return v


class WSCloseAllCommand(WSCommandMessage):
    """Close all positions — requires confirmation."""
    command: Literal["close_all"]
    args: dict = Field(...)

    @validator("args")
    def validate_args(cls, v):
        if v.get("confirm") is not True:
            raise ValueError("close_all requires confirm=true")
        return v


# ── Heartbeat ──

class WSPingMessage(WSMessage):
    type: Literal["ping"]


class WSPongMessage(WSMessage):
    type: Literal["pong"]


# ── Union of all valid message types ──

WS_VALID_MESSAGES = (
    WSAuthMessage
    | WSAuthRefreshMessage
    | WSSubscribeMessage
    | WSUnsubscribeMessage
    | WSCommandMessage
    | WSPingMessage
    | WSPongMessage
)


def parse_ws_message(raw: str) -> WSMessage:
    """Parse and validate a WebSocket message.

    Raises WsValidationError if message is invalid.
    """
    # Size check
    if len(raw) > 65536:  # 64KB
        raise WsValidationError("Message too large (max 64KB)")

    # JSON parse
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise WsValidationError(f"Invalid JSON: {e}")

    # Must be an object
    if not isinstance(data, dict):
        raise WsValidationError("Message must be a JSON object")

    # Type field required
    msg_type = data.get("type")
    if not msg_type:
        raise WsValidationError("Missing 'type' field")

    # Route to correct schema
    type_map = {
        "auth": WSAuthMessage,
        "auth:refresh": WSAuthRefreshMessage,
        "subscribe": WSSubscribeMessage,
        "unsubscribe": WSUnsubscribeMessage,
        "command": WSCommandMessage,
        "ping": WSPingMessage,
        "pong": WSPongMessage,
    }

    schema_class = type_map.get(msg_type)
    if not schema_class:
        raise WsValidationError(f"Unknown message type: {msg_type}")

    # Validate against schema
    try:
        return schema_class.model_validate(data)
    except ValidationError as e:
        raise WsValidationError(f"Invalid message: {e}")


class WsValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
```

### 7.3 Message Handler with Validation

```python
# src/websocket/handler.py

async def handle_ws_message(
    raw: str,
    user_id: str,
    state: AppState,
) -> str:
    """Process a validated WebSocket message."""

    # ── Validate ──
    try:
        message = parse_ws_message(raw)
    except WsValidationError as e:
        return json.dumps({
            "type": "error",
            "error": "validation_error",
            "message": e.message,
        })

    # ── Rate limit per-connection ──
    if not state.ws_message_limiter.allow(f"ws:{user_id}"):
        return json.dumps({
            "type": "error",
            "error": "rate_limit",
            "message": "Too many messages. Please slow down.",
        })

    # ── Route by type ──
    match message.type:
        case "subscribe":
            return await handle_subscribe(message, user_id, state)
        case "unsubscribe":
            return await handle_unsubscribe(message, user_id, state)
        case "command":
            return await handle_command(message, user_id, state)
        case "ping":
            return json.dumps({"type": "pong", "id": message.id})
        case _:
            return json.dumps({
                "type": "error",
                "error": "unsupported",
                "message": f"Message type '{message.type}' not supported in this state",
            })


async def handle_subscribe(
    message: WSSubscribeMessage,
    user_id: str,
    state: AppState,
) -> str:
    """Subscribe to a channel with authorization check."""

    # Parse channel parts
    parts = message.channel.split(".")
    channel_type = parts[0]

    # Authorization: check if user can subscribe to this channel
    allowed_channels = await get_user_channels(user_id, state)
    if message.channel not in allowed_channels and f"{channel_type}.*" not in allowed_channels:
        return json.dumps({
            "type": "error",
            "error": "unauthorized",
            "message": f"Not authorized for channel '{message.channel}'",
        })

    # Subscribe
    state.ws_subscriptions.add(user_id, message.channel)

    return json.dumps({
        "type": "subscribed",
        "channel": message.channel,
    })


async def handle_command(
    message: WSCommandMessage,
    user_id: str,
    state: AppState,
) -> str:
    """Execute a command with authorization."""

    # Commands require trade permission
    if not await user_has_permission(user_id, "trade", state):
        return json.dumps({
            "type": "error",
            "error": "unauthorized",
            "message": "Trading permission required",
        })

    # Destructive commands require explicit confirmation
    if message.command in ("close_all",):
        if not isinstance(message.args, dict) or message.args.get("confirm") is not True:
            return json.dumps({
                "type": "error",
                "error": "confirmation_required",
                "message": f"Command '{message.command}' requires args.confirm=true",
            })

    # Execute command
    result = await execute_trading_command(
        command=message.command,
        args=message.args or {},
        user_id=user_id,
        state=state,
    )

    return json.dumps({
        "type": "command_result",
        "command": message.command,
        "result": result,
    })
```

### 7.4 Per-Connection Message Rate Limiter

```python
# src/websocket/message_rate_limit.py

import time
from collections import defaultdict


class WsMessageRateLimiter:
    """Per-connection message rate limiter (token bucket)."""

    def __init__(self, rate: int = 60, per: float = 60.0):
        self.rate = rate
        self.per = per
        self.buckets: dict[str, dict] = defaultdict(
            lambda: {"tokens": rate, "last": time.monotonic()}
        )

    def allow(self, connection_id: str) -> bool:
        now = time.monotonic()
        bucket = self.buckets[connection_id]

        # Refill
        elapsed = now - bucket["last"]
        refill = elapsed * (self.rate / self.per)
        bucket["tokens"] = min(self.rate, bucket["tokens"] + refill)
        bucket["last"] = now

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False

    def remove(self, connection_id: str):
        """Clean up on disconnect."""
        self.buckets.pop(connection_id, None)
```

### 7.5 Verification Checklist

- [ ] All WebSocket messages validated against Pydantic schemas
- [ ] `extra="forbid"` on all message models — rejects unknown fields
- [ ] Message size limit: 64KB max
- [ ] Message rate limit: 60/minute per connection
- [ ] Channel name validated with regex pattern
- [ ] Channel authorization checked before subscription
- [ ] Destructive commands (close_all) require explicit confirmation
- [ ] Unknown message types rejected with error response
- [ ] JSON parse errors caught and returned as error
- [ ] Per-connection rate limiter cleaned up on disconnect
- [ ] Unit test: oversized message → rejected
- [ ] Unit test: unknown message type → rejected
- [ ] Unit test: missing required fields → rejected
- [ ] Unit test: extra fields → rejected (mass assignment prevention)
- [ ] Unit test: subscribe to unauthorized channel → rejected
- [ ] Unit test: command without trade permission → rejected
- [ ] Unit test: close_all without confirm → rejected
- [ ] Integration test: message flood → rate limited

---

## Implementation Priority

| Phase | Issues | Effort | Timeline |
|-------|--------|--------|----------|
| **Phase 1** | §5 SSRF, §6 IDOR | Medium | Week 1 |
| **Phase 2** | §1 Per-key rate limit, §2 Global rate limit | Medium | Week 1-2 |
| **Phase 3** | §4 WebSocket auth, §7 WS validation | High | Week 2-3 |
| **Phase 4** | §3 gRPC mTLS | High | Week 3-4 |

**Phase 1** blocks the most dangerous attacks (SSRF to cloud metadata, IDOR to other users' data).  
**Phase 2** protects infrastructure from abuse.  
**Phase 3** closes the WebSocket attack surface.  
**Phase 4** completes the zero-trust model for internal services.

---

## Testing Strategy

### Unit Tests (per-issue)

Each section above includes a verification checklist. Convert to unit tests:

```python
# tests/test_ssf.py
def test_block_metadata_endpoint():
    client = SafeHttpClient(test_config)
    with pytest.raises(SsrfError, match="BlockedIp"):
        await client.safe_get("http://169.254.169.254/latest/meta-data/")

def test_block_private_ip():
    with pytest.raises(SsrfError, match="BlockedIp"):
        await client.safe_get("http://192.168.1.1/admin")

def test_block_dns_rebinding():
    # Mock DNS that resolves to private IP
    with pytest.raises(SsrfError, match="BlockedIp"):
        await client.safe_get("http://attacker.com/ssrf")
```

### Integration Tests

```python
# tests/integration/test_idor.py
async def test_user_cannot_access_other_users_order(client, user_a, user_b):
    """User A creates order, User B tries to access it."""
    # User A creates order
    order = await client.post("/api/v1/orders", headers=auth_a, json={...})

    # User B tries to access
    response = await client.get(
        f"/api/v1/orders/{order['id']}",
        headers=auth_b,
    )
    assert response.status_code == 404  # Not 403!
```

### Penetration Test Scenarios

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | Connect WS without auth | Connection closed (4001) |
| 2 | WS with expired JWT | Connection closed (4001) |
| 3 | WS flood (1000 msgs/sec) | Rate limited after 60 |
| 4 | `GET /orders/{other_user_order}` | 404 |
| 5 | `POST /webhooks {"url": "http://169.254.169.254/..."}` | Blocked |
| 6 | Rotate IPs with same API key | Rate limited by key |
| 7 | Botnet hitting auth endpoint | Global limit hit, 503 |
| 8 | gRPC call without cert | Connection refused |
| 9 | WS message with extra fields | Rejected |
| 10 | WS subscribe to unauthorized channel | Rejected |

---

## Summary

| Issue | Root Cause | Fix | Defense Layers |
|-------|-----------|-----|----------------|
| No per-key rate limit | Rate limit by IP only | Rate limit by API key ID | Per-key → Per-endpoint |
| No global rate limit | No infrastructure ceiling | Global limiter before per-key | Global → Per-key → Per-endpoint |
| gRPC auth missing | "Internal" ≠ "trusted" | mTLS with method-level auth | mTLS + cert rotation + method ACL |
| WebSocket auth gaps | Auth on connect only | First-message JWT + heartbeat + refresh | Auth + heartbeat + idle timeout + origin |
| SSRF risk | User-controlled URLs | DNS check + IP blocklist + network rules | URL validation + DNS pinning + iptables |
| IDOR risk | Auth without ownership | Query scoping + ownership middleware | DB query filter + middleware + 404 masking |
| WS validation missing | REST-only validation | Pydantic schemas for all WS messages | Schema + size limit + rate limit + channel auth |

All fixes are defense-in-depth: no single layer is the only protection.
