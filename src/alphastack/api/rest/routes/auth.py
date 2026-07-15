"""Auth Routes – JWT login, refresh, logout.

Uses PyJWT for token handling.  In production, wire to the full
AuthManager from security/auth.py with Argon2id password hashing
and TOTP 2FA support.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt  # PyJWT
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth")

# ---------------------------------------------------------------------------
# JWT config
# ---------------------------------------------------------------------------

_SECRET = os.environ.get("ALPHASTACK_JWT_SECRET", secrets.token_urlsafe(64))
_ALGORITHM = "HS256"
_ACCESS_TTL = timedelta(minutes=30)
_REFRESH_TTL = timedelta(days=7)


def create_token(sub: str, ttl: timedelta, token_type: str = "access") -> str:
    """Create a JWT token using PyJWT."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "type": token_type,
        "iat": now,
        "exp": now + int(ttl.total_seconds()),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT token using PyJWT."""
    try:
        return jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Unified login schema — accepts {username, password} or {apiKey, apiSecret}.

    Mobile clients send {apiKey, apiSecret}; web clients send {username, password}.
    Both formats are normalised to (username, password) via resolved_credentials().
    """
    username: str | None = Field(None, min_length=1, max_length=64)
    password: str | None = Field(None, min_length=1, max_length=128)
    apiKey: str | None = Field(None, min_length=1, max_length=128)
    apiSecret: str | None = Field(None, min_length=1, max_length=128)

    model_config = {"populate_by_name": True}

    def resolved_credentials(self) -> tuple[str, str]:
        """Return (username, password) from whichever fields were provided."""
        uname = self.username or self.apiKey or ""
        pwd = self.password or self.apiSecret or ""
        return uname, pwd


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
    """In-memory token revocation blocklist.

    Stores revoked JTI claims so the auth middleware can reject them.
    In production, back this with Redis or a database table.
    """

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
        return decode_token(token)


class _AuthManagerWrapper:
    """Minimal auth manager for middleware compatibility."""

    jwt = _AuthJWTWrapper()


_auth_manager = _AuthManagerWrapper()


def get_auth_manager() -> _AuthManagerWrapper:
    """Return the auth manager singleton (used by auth middleware)."""
    return _auth_manager


# ---------------------------------------------------------------------------
# User store (replace with DB-backed auth in production)
# ---------------------------------------------------------------------------

_DEMO_USERS: dict[str, str] = {
    "admin": hashlib.sha256("alphastack".encode()).hexdigest(),
}


def _verify_credentials(username: str, password: str) -> bool:
    expected = _DEMO_USERS.get(username)
    if expected is None:
        return False
    return hmac.compare_digest(expected, hashlib.sha256(password.encode()).hexdigest())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    """Authenticate and return JWT tokens.

    Accepts both {username, password} and {apiKey, apiSecret} formats.
    """
    username, password = body.resolved_credentials()
    if not username or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing credentials")
    if not _verify_credentials(username, password):
        logger.warning("login_failed", username=username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access = create_token(username, _ACCESS_TTL, "access")
    refresh = create_token(username, _REFRESH_TTL, "refresh")
    logger.info("login_success", username=username)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=int(_ACCESS_TTL.total_seconds()),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest) -> TokenResponse:
    """Exchange a refresh token for a new access token."""
    try:
        payload = decode_token(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a refresh token")

    username = payload["sub"]
    access = create_token(username, _ACCESS_TTL, "access")
    new_refresh = create_token(username, _REFRESH_TTL, "refresh")
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=int(_ACCESS_TTL.total_seconds()),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request) -> MessageResponse:
    """Logout — revoke the current access token's JTI."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_token(token)
            jti = payload.get("jti", "")
            if jti:
                blocklist.revoke(jti)
        except Exception:
            pass  # Token already invalid — that's fine
    return MessageResponse(message="Logged out")
