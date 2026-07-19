"""Auth Routes – JWT login, refresh, logout, registration.

Uses AuthManager from security/auth.py with:
- Argon2id password hashing (replaces SHA-256)
- RS256 JWT with persistent keypair (replaces ephemeral HS256)
- TOTP 2FA support
- Rate limiting on auth endpoints
- Token revocation (logout)
"""

from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from alphastack.security.auth import (
    AuthManager,
    AuthResult,
    JWTManager,
    PasswordPolicy,
    RateLimiter,
    SessionManager,
    TOTPManager,
    hash_password,
    verify_password,
)
from alphastack.security.audit import AuditCategory, AuditLogger
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth")


# ---------------------------------------------------------------------------
# RSA key management (persistent, NOT regenerated on restart)
# ---------------------------------------------------------------------------

_KEY_DIR = Path(os.environ.get("ALPHASTACK_KEY_DIR", ".alphastack/keys"))
_KEY_DIR.mkdir(parents=True, exist_ok=True)


def _load_or_generate_keypair() -> tuple[bytes, bytes]:
    """Load RSA-4096 keypair from disk, or generate and persist."""
    priv_path = _KEY_DIR / "jwt_private.pem"
    pub_path = _KEY_DIR / "jwt_public.pem"

    if priv_path.exists() and pub_path.exists():
        return priv_path.read_bytes(), pub_path.read_bytes()

    # Generate fresh RSA-4096 keypair
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Persist to disk (restrict permissions)
    priv_path.write_bytes(private_pem)
    pub_path.write_bytes(public_pem)
    try:
        priv_path.chmod(0o600)
        pub_path.chmod(0o644)
    except OSError:
        pass

    logger.info("jwt_keypair_generated", key_dir=str(_KEY_DIR))
    return private_pem, public_pem


# ---------------------------------------------------------------------------
# Singletons — initialised once at import time
# ---------------------------------------------------------------------------

_PRIVATE_PEM, _PUBLIC_PEM = _load_or_generate_keypair()

jwt_manager = JWTManager(
    private_key_pem=_PRIVATE_PEM,
    public_key_pem=_PUBLIC_PEM,
    key_id=os.environ.get("ALPHASTACK_JWT_KID", "as-key-default"),
)

session_manager = SessionManager()

login_limiter = RateLimiter(
    rate=5 / (15 * 60),   # 5 attempts per 15 minutes
    burst=3,
    block_seconds=30 * 60,  # 30-minute block after exhaustion
)

refresh_limiter = RateLimiter(
    rate=20 / (15 * 60),
    burst=10,
    block_seconds=5 * 60,
)

auth_manager = AuthManager(
    jwt_manager=jwt_manager,
    session_manager=session_manager,
    login_limiter=login_limiter,
)

audit = AuditLogger()

# In-memory user store (replace with DB in production)
# Values are Argon2id hashes
_users: dict[str, dict[str, Any]] = {}

# TOTP secrets (encrypted in production)
_totp_managers: dict[str, TOTPManager] = {}


def _ensure_demo_user() -> None:
    """Create default admin user with Argon2id hash if no users exist."""
    if not _users:
        _users["admin"] = {
            "user_id": "usr_admin_001",
            "email": "admin@alphastack.io",
            "password_hash": hash_password(os.environ.get("ALPHASTACK_ADMIN_PASSWORD", "Ch@ngeMe!2026x")),
            "roles": ["admin", "trader"],
            "tier": "premium",
            "has_2fa": False,
            "is_active": True,
        }


_ensure_demo_user()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Unified login schema — accepts {username, password} or {apiKey, apiSecret}."""
    username: str | None = Field(None, min_length=1, max_length=64)
    password: str | None = Field(None, min_length=1, max_length=128)
    apiKey: str | None = Field(None, min_length=1, max_length=128)
    apiSecret: str | None = Field(None, min_length=1, max_length=128)

    model_config = {"populate_by_name": True}

    def resolved_credentials(self) -> tuple[str, str]:
        uname = self.username or self.apiKey or ""
        pwd = self.password or self.apiSecret or ""
        return uname, pwd


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=12, max_length=128)


class TOTPSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    backup_codes: list[str]


class TOTPVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)
    partial_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Token blocklist (in-memory; replace with Redis in production)
# ---------------------------------------------------------------------------

class TokenBlocklist:
    """In-memory token revocation blocklist."""

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    def revoke(self, jti: str) -> None:
        self._revoked.add(jti)

    def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked

    def clear(self) -> None:
        self._revoked.clear()


blocklist = TokenBlocklist()


# ---------------------------------------------------------------------------
# Auth manager wrapper (for middleware compatibility)
# ---------------------------------------------------------------------------

class _AuthJWTWrapper:
    """Thin wrapper exposing decode_token as the middleware expects."""

    @staticmethod
    def decode_token(token: str) -> dict[str, Any]:
        return jwt_manager.decode_token(token)


class _AuthManagerWrapper:
    """Minimal auth manager for middleware compatibility."""

    jwt = _AuthJWTWrapper()


_auth_manager_wrapper = _AuthManagerWrapper()


def get_auth_manager() -> _AuthManagerWrapper:
    """Return the auth manager singleton (used by auth middleware)."""
    return _auth_manager_wrapper


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=MessageResponse)
async def register(body: RegisterRequest) -> MessageResponse:
    """Register a new user with password policy enforcement."""
    errors = PasswordPolicy.validate(body.password, body.email)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password policy violation: {'; '.join(errors)}",
        )

    email = body.email.strip().lower()
    if email in _users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    import uuid
    _users[email] = {
        "user_id": f"usr_{uuid.uuid4().hex[:12]}",
        "email": email,
        "password_hash": hash_password(body.password),
        "roles": ["trader"],
        "tier": "free",
        "has_2fa": False,
        "is_active": True,
    }

    audit.log(
        AuditCategory.AUTH,
        "user_registered",
        actor_type="user",
        actor_id=email,
        resource_type="user",
        resource_id=email,
    )
    logger.info("user_registered", email=email)

    return MessageResponse(message="Registration successful")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request) -> TokenResponse:
    """Authenticate with Argon2id password verification and RS256 JWT issuance.

    Accepts both {username, password} and {apiKey, apiSecret} formats.
    """
    username, password = body.resolved_credentials()
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing credentials",
        )

    ip = request.client.host if request.client else "unknown"

    # Rate limit check
    if not login_limiter.allow(ip):
        audit.log(
            AuditCategory.SECURITY,
            "login_rate_limited",
            actor_type="ip",
            actor_id=ip,
            details={"username": username},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": "900"},
        )

    # Look up user
    user = _users.get(username)
    if not user or not user.get("is_active"):
        # Constant-time dummy hash to prevent timing attacks
        hash_password("timing-attack-mitigation-dummy")
        audit.log(
            AuditCategory.AUTH,
            "login_failed",
            actor_type="user",
            actor_id=username,
            details={"reason": "user_not_found", "ip": ip},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Verify password (Argon2id)
    if not verify_password(password, user["password_hash"]):
        audit.log(
            AuditCategory.AUTH,
            "login_failed",
            actor_type="user",
            actor_id=username,
            details={"reason": "invalid_password", "ip": ip},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # 2FA check
    if user.get("has_2fa"):
        partial = jwt_manager.create_partial_token(user["user_id"])
        return TokenResponse(
            access_token="",
            refresh_token="",
            token_type="bearer",
            expires_in=300,
        )

    # Issue full tokens
    result = _issue_tokens(user, ip)

    audit.log(
        AuditCategory.AUTH,
        "login_success",
        actor_type="user",
        actor_id=username,
        details={"ip": ip, "2fa": False},
    )
    logger.info("login_success", username=username)

    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token or "",
        expires_in=900,
    )


@router.post("/login/2fa", response_model=TokenResponse)
async def login_2fa(body: TOTPVerifyRequest, request: Request) -> TokenResponse:
    """Complete 2FA login with TOTP code."""
    ip = request.client.host if request.client else "unknown"

    if not login_limiter.allow(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
        )

    try:
        claims = jwt_manager.decode_token(body.partial_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid partial token: {exc}",
        )

    if claims.get("type") != "partial":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not a partial authentication token",
        )

    user_id = claims["sub"]
    user = next((u for u in _users.values() if u["user_id"] == user_id), None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    totp_mgr = _totp_managers.get(user_id)
    if not totp_mgr or not totp_mgr.verify(body.code):
        audit.log(
            AuditCategory.AUTH,
            "2fa_failed",
            actor_type="user",
            actor_id=user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code",
        )

    result = _issue_tokens(user, ip)

    audit.log(
        AuditCategory.AUTH,
        "login_success",
        actor_type="user",
        actor_id=user_id,
        details={"ip": ip, "2fa": True},
    )

    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token or "",
        expires_in=900,
    )


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def totp_setup(request: Request) -> TOTPSetupResponse:
    """Enable TOTP 2FA for the current user."""
    claims = getattr(request.state, "user", {})
    user_id = claims.get("sub", "")
    email = claims.get("email", "")

    user = next((u for u in _users.values() if u["user_id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    totp_mgr = TOTPManager()
    secret = totp_mgr.generate_secret()
    uri = totp_mgr.provisioning_uri(email)
    backup_codes = TOTPManager.generate_backup_codes()

    _totp_managers[user_id] = totp_mgr
    user["has_2fa"] = True

    audit.log(
        AuditCategory.AUTH,
        "2fa_enabled",
        actor_type="user",
        actor_id=user_id,
    )

    return TOTPSetupResponse(
        secret=secret,
        provisioning_uri=uri,
        backup_codes=backup_codes,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, request: Request) -> TokenResponse:
    """Exchange a refresh token for a new access+refresh token pair (rotation)."""
    ip = request.client.host if request.client else "unknown"

    if not refresh_limiter.allow(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many refresh attempts.",
            headers={"Retry-After": "300"},
        )

    try:
        result = auth_manager.refresh(body.refresh_token, ip_address=ip)
    except PermissionError as exc:
        audit.log(
            AuditCategory.SECURITY,
            "refresh_token_theft_detected",
            actor_type="ip",
            actor_id=ip,
            details={"reason": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {exc}",
        )

    audit.log(
        AuditCategory.AUTH,
        "token_refreshed",
        actor_type="user",
        actor_id=result.session_id or "",
        details={"ip": ip},
    )

    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token or "",
        expires_in=900,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request) -> MessageResponse:
    """Logout — revoke the current access token and session."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt_manager.decode_token(token)
            jti = payload.get("jti", "")
            if jti:
                blocklist.revoke(jti)
            user_id = payload.get("sub", "")

            # Revoke all sessions for this user
            session_manager.revoke_all_for_user(user_id, reason="user_logout")

            audit.log(
                AuditCategory.AUTH,
                "logout",
                actor_type="user",
                actor_id=user_id,
            )
        except Exception:
            pass

    return MessageResponse(message="Logged out")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(request: Request) -> MessageResponse:
    """Revoke ALL sessions and tokens for the current user."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = jwt_manager.decode_token(auth_header[7:])
        user_id = payload.get("sub", "")
        count = session_manager.revoke_all_for_user(user_id, reason="logout_all")

        audit.log(
            AuditCategory.AUTH,
            "logout_all",
            actor_type="user",
            actor_id=user_id,
            details={"sessions_revoked": count},
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    return MessageResponse(message=f"Logged out from {count} sessions")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _issue_tokens(user: dict[str, Any], ip: str) -> AuthResult:
    """Issue access + refresh tokens for a user whose password is already verified."""
    # Use the AuthManager's internal token issuance (bypasses re-verification)
    return auth_manager._issue_full_tokens(
        user_id=user["user_id"],
        email=user["email"],
        ip_address=ip,
        device_id="web",
        device_name="web-client",
    )
