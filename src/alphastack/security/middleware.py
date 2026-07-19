"""Security middleware — request signing, IP allowlisting, audit logging.

Implements middleware from IMPLEMENTATION_SECURITY.md:
- HMAC-SHA256 request signing validation
- IP allowlisting with CIDR support
- Comprehensive audit logging for all API requests
- Security headers enforcement
- Request ID propagation
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import time
import uuid
from typing import Any, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from alphastack.security.audit import AuditCategory, AuditLogger
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# IP Allowlist Middleware
# ---------------------------------------------------------------------------

class IPAllowlistMiddleware(BaseHTTPMiddleware):
    """Restrict API access to whitelisted IP addresses/CIDR ranges.

    When enabled, only requests from allowed IPs reach the application.
    All others receive 403 Forbidden.

    Configuration via environment:
        ALPHASTACK_IP_ALLOWLIST=10.0.0.0/8,192.168.1.0/24,203.0.113.5

    If the env var is empty or unset, all IPs are allowed (no restriction).
    """

    def __init__(
        self,
        app: ASGIApp,
        allowed_cidrs: list[str] | None = None,
        exempt_paths: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._exempt_paths = exempt_paths or {"/health", "/docs", "/redoc", "/openapi.json"}
        self._networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []

        cidrs = allowed_cidrs or self._load_from_env()
        for cidr in cidrs:
            try:
                self._networks.append(ipaddress.ip_network(cidr.strip(), strict=False))
            except ValueError:
                logger.warning("ip_allowlist_invalid_cidr", cidr=cidr)

    @staticmethod
    def _load_from_env() -> list[str]:
        raw = os.environ.get("ALPHASTACK_IP_ALLOWLIST", "")
        if not raw:
            return []
        return [c.strip() for c in raw.split(",") if c.strip()]

    def _is_allowed(self, ip_str: str) -> bool:
        if not self._networks:
            return True  # No allowlist configured — allow all
        try:
            addr = ipaddress.ip_address(ip_str)
            return any(addr in net for net in self._networks)
        except ValueError:
            return False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Exempt paths
        if path in self._exempt_paths:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        if not self._is_allowed(client_ip):
            logger.warning("ip_blocked", ip=client_ip, path=path)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access denied: IP not in allowlist"},
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Request Signing Middleware
# ---------------------------------------------------------------------------

class RequestSigningMiddleware(BaseHTTPMiddleware):
    """Validate HMAC-SHA256 request signatures for API integrity.

    Clients sign requests with:
        signature = HMAC-SHA256(secret, method + path + timestamp + body)

    Headers required:
        X-Request-ID: Unique request identifier
        X-Timestamp: Unix timestamp (must be within tolerance)
        X-Signature: Hex-encoded HMAC-SHA256 signature

    If ALPHASTACK_REQUEST_SIGNING_KEY is not set, signing is not enforced
    (development mode).
    """

    # Paths that don't require signing
    _EXEMPT_PATHS = frozenset({
        "/health", "/docs", "/redoc", "/openapi.json",
        "/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh",
    })

    # Timestamp tolerance in seconds
    _TIMESTAMP_TOLERANCE = 300  # 5 minutes

    def __init__(
        self,
        app: ASGIApp,
        signing_key: str | None = None,
        enforce: bool = False,
    ) -> None:
        super().__init__(app)
        self._signing_key = signing_key or os.environ.get("ALPHASTACK_REQUEST_SIGNING_KEY", "")
        self._enforce = enforce or bool(os.environ.get("ALPHASTACK_ENFORCE_REQUEST_SIGNING", ""))

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Skip if not enforcing or path is exempt
        if not self._enforce or not self._signing_key or path in self._EXEMPT_PATHS:
            # Still propagate request ID
            request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
            request.state.request_id = request_id
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

        # Extract signing headers
        request_id = request.headers.get("X-Request-ID", "")
        timestamp_str = request.headers.get("X-Timestamp", "")
        signature = request.headers.get("X-Signature", "")

        if not all([request_id, timestamp_str, signature]):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing required signing headers (X-Request-ID, X-Timestamp, X-Signature)"},
            )

        # Validate timestamp freshness
        try:
            timestamp = int(timestamp_str)
            now = int(time.time())
            if abs(now - timestamp) > self._TIMESTAMP_TOLERANCE:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Request timestamp outside tolerance window"},
                    headers={"X-Request-ID": request_id},
                )
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid X-Timestamp header"},
            )

        # Read body for signing
        body = await request.body()

        # Compute expected signature
        message = f"{request.method}{request.url.path}{timestamp_str}".encode() + body
        expected_sig = hmac.new(
            self._signing_key.encode(), message, hashlib.sha256
        ).hexdigest()

        # Constant-time comparison
        if not hmac.compare_digest(signature, expected_sig):
            logger.warning(
                "request_signature_invalid",
                request_id=request_id,
                path=path,
                ip=request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid request signature"},
                headers={"X-Request-ID": request_id},
            )

        # Signature valid — propagate request ID
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Security Audit Middleware
# ---------------------------------------------------------------------------

class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """Comprehensive audit logging for all API requests and responses.

    Logs:
    - All authentication events (login, logout, token refresh)
    - All trading operations (order placement, modification, cancellation)
    - All data access (portfolio, signals, analytics)
    - All security events (rate limit hits, blocked IPs, invalid tokens)
    - Request/response metadata (status codes, latency, user agent)

    Implements EU AI Act Art. 12 compliant logging with hash-chain integrity.
    """

    def __init__(
        self,
        app: ASGIApp,
        audit_logger: AuditLogger | None = None,
        log_body: bool = False,
        sensitive_headers: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._audit = audit_logger or AuditLogger()
        self._log_body = log_body
        self._sensitive_headers = sensitive_headers or {
            "authorization", "cookie", "x-api-key", "x-api-secret",
        }

    def _sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Redact sensitive header values."""
        return {
            k: ("[REDACTED]" if k.lower() in self._sensitive_headers else v)
            for k, v in headers.items()
        }

    def _categorize_request(self, method: str, path: str) -> AuditCategory:
        """Determine audit category from request path."""
        if "/auth/" in path:
            return AuditCategory.AUTH
        if "/trades/" in path or "/orders/" in path:
            return AuditCategory.TRADING
        if "/portfolio/" in path or "/signals/" in path:
            return AuditCategory.DATA_ACCESS
        if "/credentials/" in path:
            return AuditCategory.CREDENTIAL
        return AuditCategory.SYSTEM

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()

        # Extract user info from auth middleware
        user_claims = getattr(request.state, "user", None)
        actor_type = "user" if user_claims else "anonymous"
        actor_id = user_claims.get("sub", "") if user_claims else ""

        # Process request
        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        path = request.url.path
        method = request.method

        # Skip logging for health checks and metrics
        if path in ("/health", "/metrics", "/docs", "/redoc", "/openapi.json"):
            return response

        # Determine if this is a security-relevant event
        is_security_event = (
            response.status_code in (401, 403, 429)
            or "/auth/" in path
        )

        # Log to audit trail
        try:
            category = self._categorize_request(method, path)
            details: dict[str, Any] = {
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "latency_ms": round(elapsed_ms, 2),
                "ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", ""),
                "request_id": getattr(request.state, "request_id", ""),
            }

            if is_security_event:
                category = AuditCategory.SECURITY
                details["security_event"] = True
                if response.status_code == 429:
                    details["event_type"] = "rate_limit_exceeded"
                elif response.status_code == 401:
                    details["event_type"] = "authentication_failure"
                elif response.status_code == 403:
                    details["event_type"] = "authorization_failure"

            self._audit.log(
                category=category,
                action=f"{method} {path}",
                actor_type=actor_type,
                actor_id=actor_id,
                resource_type="api_endpoint",
                resource_id=path,
                details=details,
                outcome={
                    "status_code": response.status_code,
                    "success": 200 <= response.status_code < 400,
                },
            )
        except Exception as exc:
            # Audit logging must NEVER fail the request
            logger.error("audit_log_failed", error=str(exc))

        return response


# ---------------------------------------------------------------------------
# Request signing helper (for client-side use)
# ---------------------------------------------------------------------------

def compute_request_signature(
    signing_key: str,
    method: str,
    path: str,
    timestamp: int,
    body: bytes = b"",
) -> str:
    """Compute HMAC-SHA256 request signature.

    Use this on the client side to sign requests.

    Parameters
    ----------
    signing_key : str
        Shared secret key.
    method : str
        HTTP method (GET, POST, etc.).
    path : str
        Request path (e.g., /api/v1/trades).
    timestamp : int
        Unix timestamp.
    body : bytes
        Request body bytes.

    Returns
    -------
    str
        Hex-encoded HMAC-SHA256 signature.
    """
    message = f"{method}{path}{timestamp}".encode() + body
    return hmac.new(signing_key.encode(), message, hashlib.sha256).hexdigest()


def verify_request_signature(
    signing_key: str,
    method: str,
    path: str,
    timestamp: int,
    body: bytes,
    provided_signature: str,
) -> bool:
    """Verify an HMAC-SHA256 request signature.

    Parameters
    ----------
    signing_key : str
        Shared secret key.
    method : str
        HTTP method.
    path : str
        Request path.
    timestamp : int
        Unix timestamp from the request.
    body : bytes
        Request body bytes.
    provided_signature : str
        Hex-encoded signature from X-Signature header.

    Returns
    -------
    bool
        True if signature is valid.
    """
    expected = compute_request_signature(signing_key, method, path, timestamp, body)
    return hmac.compare_digest(expected, provided_signature)
