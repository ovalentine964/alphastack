"""Auth Routes – JWT login, refresh, logout."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth")

# ---------------------------------------------------------------------------
# JWT helpers (minimal, no external dependency – use PyJWT in production)
# ---------------------------------------------------------------------------

import base64
import json


_SECRET = secrets.token_urlsafe(64)  # Rotate on restart; read from env in prod
_ALGORITHM = "HS256"
_ACCESS_TTL = timedelta(minutes=30)
_REFRESH_TTL = timedelta(days=7)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def create_token(sub: str, ttl: timedelta, token_type: str = "access") -> str:
    header = _b64url(json.dumps({"alg": _ALGORITHM, "typ": "JWT"}).encode())
    now = int(time.time())
    payload = _b64url(json.dumps({
        "sub": sub,
        "type": token_type,
        "iat": now,
        "exp": now + int(ttl.total_seconds()),
    }).encode())
    sig_input = f"{header}.{payload}".encode()
    signature = _b64url(hmac.new(_SECRET.encode(), sig_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")
    header, payload, sig = parts
    sig_input = f"{header}.{payload}".encode()
    expected = _b64url(hmac.new(_SECRET.encode(), sig_input, hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid signature")
    data = json.loads(_b64url_decode(payload))
    if data.get("exp", 0) < time.time():
        raise ValueError("Token expired")
    return data


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


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
# Simple user store (replace with DB-backed auth in production)
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
    """Authenticate and return JWT tokens."""
    if not _verify_credentials(body.username, body.password):
        logger.warning("login_failed", username=body.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access = create_token(body.username, _ACCESS_TTL, "access")
    refresh = create_token(body.username, _REFRESH_TTL, "refresh")
    logger.info("login_success", username=body.username)
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
async def logout() -> MessageResponse:
    """Logout (client discards tokens; server-side revocation via blocklist)."""
    # In production: add token jti to Redis blocklist
    return MessageResponse(message="Logged out")
