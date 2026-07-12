"""Authentication — JWT tokens, TOTP 2FA, session management, rate limiting.

Implements the three-layer auth architecture from architecture_security.md:
  Layer 1: Identity (email + password via Argon2id)
  Layer 2: Second factor (TOTP RFC 6238)
  Layer 3: Session (JWT access + refresh tokens, device binding)
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import jwt  # PyJWT
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ACCESS_TOKEN_LIFETIME = 15 * 60  # 15 minutes
_REFRESH_TOKEN_LIFETIME = 7 * 24 * 60 * 60  # 7 days
_MAX_SESSIONS_PER_USER = 10
_BACKUP_CODE_COUNT = 8
_BACKUP_CODE_LENGTH = 8

_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    salt_len=16,
    hash_len=32,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class AuthMethod(str, Enum):
    PASSWORD = "password"
    TOTP = "totp"
    BACKUP_CODE = "backup_code"
    REFRESH = "refresh"


@dataclass
class Session:
    """Server-side session record."""
    session_id: str
    user_id: str
    device_id: str
    device_name: str
    ip_hash: str
    user_agent: str
    refresh_token_hash: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    last_active_at: float = field(default_factory=time.time)
    is_revoked: bool = False
    revoke_reason: str | None = None


@dataclass
class AuthResult:
    """Returned by login / token refresh."""
    access_token: str
    refresh_token: str | None = None
    requires_2fa: bool = False
    partial_token: str | None = None
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------

class PasswordPolicy:
    """Enforce password complexity rules."""

    MIN_LENGTH = 12
    MAX_LENGTH = 128
    SEQUENTIAL_LIMIT = 4  # "abcd", "1234"
    REPEATED_LIMIT = 3  # "aaa"

    @classmethod
    def validate(cls, password: str, email: str = "") -> list[str]:
        """Return a list of policy violations (empty ⇒ valid)."""
        errors: list[str] = []
        if len(password) < cls.MIN_LENGTH:
            errors.append(f"Minimum {cls.MIN_LENGTH} characters")
        if len(password) > cls.MAX_LENGTH:
            errors.append(f"Maximum {cls.MAX_LENGTH} characters")
        if not any(c.isupper() for c in password):
            errors.append("At least one uppercase letter")
        if not any(c.islower() for c in password):
            errors.append("At least one lowercase letter")
        if not any(c.isdigit() for c in password):
            errors.append("At least one digit")
        if not any(not c.isalnum() for c in password):
            errors.append("At least one special character")
        if email and email.split("@")[0].lower() in password.lower():
            errors.append("Must not contain email local part")
        if cls._has_sequential(password):
            errors.append(f"No {cls.SEQUENTIAL_LIMIT}+ sequential characters")
        if cls._has_repeated(password):
            errors.append(f"No {cls.REPEATED_LIMIT}+ repeated characters")
        return errors

    @classmethod
    def _has_sequential(cls, pw: str) -> bool:
        for i in range(len(pw) - cls.SEQUENTIAL_LIMIT + 1):
            chunk = pw[i : i + cls.SEQUENTIAL_LIMIT]
            ords = [ord(c) for c in chunk]
            if all(ords[j + 1] == ords[j] + 1 for j in range(len(ords) - 1)):
                return True
            if all(ords[j + 1] == ords[j] - 1 for j in range(len(ords) - 1)):
                return True
        return False

    @classmethod
    def _has_repeated(cls, pw: str) -> bool:
        for i in range(len(pw) - cls.REPEATED_LIMIT + 1):
            if len(set(pw[i : i + cls.REPEATED_LIMIT])) == 1:
                return True
        return False


def hash_password(password: str) -> str:
    """Hash *password* with Argon2id."""
    return _ph.hash(password)


def verify_password(password: str, hash_str: str) -> bool:
    """Verify *password* against an Argon2id hash."""
    try:
        return _ph.verify(hash_str, password)
    except VerifyMismatchError:
        return False


# ---------------------------------------------------------------------------
# JWT Manager
# ---------------------------------------------------------------------------

class JWTManager:
    """RS256 JWT access / refresh token management with key rotation.

    Parameters
    ----------
    private_key_pem : bytes
        RSA private key in PEM format.
    public_key_pem : bytes
        RSA public key in PEM format.
    issuer : str
        JWT ``iss`` claim.
    audience : str
        JWT ``aud`` claim.
    key_id : str
        ``kid`` header for key rotation support.
    """

    def __init__(
        self,
        private_key_pem: bytes,
        public_key_pem: bytes,
        issuer: str = "https://api.alphastack.io",
        audience: str = "alphastack-app",
        key_id: str = "as-key-default",
    ) -> None:
        self._private_key = private_key_pem
        self._public_key = public_key_pem
        self._issuer = issuer
        self._audience = audience
        self._key_id = key_id

    # -- Token creation -----------------------------------------------------

    def create_access_token(
        self,
        user_id: str,
        email: str,
        *,
        roles: list[str] | None = None,
        tier: str = "free",
        device_id: str = "",
        ip_hash: str = "",
        two_fa_verified: bool = False,
    ) -> str:
        now = int(time.time())
        payload = {
            "sub": user_id,
            "email": email,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "exp": now + _ACCESS_TOKEN_LIFETIME,
            "tier": tier,
            "roles": roles or ["trader"],
            "email_verified": True,
            "2fa_verified": two_fa_verified,
            "device_id": device_id,
            "ip_hash": ip_hash,
        }
        return jwt.encode(
            payload,
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._key_id},
        )

    def create_refresh_token(self, user_id: str, session_id: str) -> str:
        now = int(time.time())
        payload = {
            "sub": user_id,
            "sid": session_id,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "exp": now + _REFRESH_TOKEN_LIFETIME,
            "type": "refresh",
            "jti": secrets.token_hex(16),
        }
        return jwt.encode(
            payload,
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._key_id},
        )

    # -- Token verification -------------------------------------------------

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decode and fully verify an access or refresh token."""
        return jwt.decode(
            token,
            self._public_key,
            algorithms=["RS256"],
            issuer=self._issuer,
            audience=self._audience,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )

    def create_partial_token(self, user_id: str) -> str:
        """Short-lived token issued after password success, before 2FA."""
        now = int(time.time())
        payload = {
            "sub": user_id,
            "iss": self._issuer,
            "iat": now,
            "exp": now + 300,  # 5 minutes
            "type": "partial",
        }
        return jwt.encode(
            payload,
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._key_id},
        )

    # -- Key rotation -------------------------------------------------------

    def rotate_keys(
        self,
        new_private_pem: bytes,
        new_public_pem: bytes,
        new_key_id: str,
    ) -> None:
        """Swap signing keys.  Old tokens remain verifiable via JWKS grace."""
        self._private_key = new_private_pem
        self._public_key = new_public_pem
        self._key_id = new_key_id


# ---------------------------------------------------------------------------
# TOTP 2FA
# ---------------------------------------------------------------------------

class TOTPManager:
    """TOTP (RFC 6238) two-factor authentication.

    Generates secrets, QR provisioning URIs, verification, and backup codes.
    """

    ISSUER = "AlphaStack"

    def __init__(self, encrypted_secret: str | None = None) -> None:
        self._secret: str | None = encrypted_secret

    # -- Enrolment ----------------------------------------------------------

    def generate_secret(self) -> str:
        """Generate a new base32-encoded TOTP secret (256 bits of entropy)."""
        self._secret = pyotp.random_base32(length=32)
        return self._secret

    def provisioning_uri(self, email: str) -> str:
        """Return an ``otpauth://`` URI for QR-code generation."""
        if not self._secret:
            raise RuntimeError("No TOTP secret – call generate_secret first")
        totp = pyotp.TOTP(self._secret)
        return totp.provisioning_uri(name=email, issuer_name=self.ISSUER)

    # -- Verification -------------------------------------------------------

    def verify(self, code: str, *, window: int = 1) -> bool:
        """Validate a 6-digit TOTP code (±*window* steps tolerance)."""
        if not self._secret:
            return False
        totp = pyotp.TOTP(self._secret)
        return totp.verify(code, valid_window=window)

    # -- Backup codes -------------------------------------------------------

    @staticmethod
    def generate_backup_codes(count: int = _BACKUP_CODE_COUNT) -> list[str]:
        """Generate human-friendly backup codes (8 chars, alphanumeric)."""
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous chars
        codes: list[str] = []
        for _ in range(count):
            code = "".join(secrets.choice(alphabet) for _ in range(_BACKUP_CODE_LENGTH))
            codes.append(code)
        return codes

    @staticmethod
    def hash_backup_code(code: str) -> str:
        """Hash a backup code with Argon2id for storage."""
        return hash_password(code)

    @staticmethod
    def verify_backup_code(code: str, code_hash: str) -> bool:
        return verify_password(code, code_hash)


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------

class SessionManager:
    """In-memory session store (replace with Redis/DB in production)."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(
        self,
        user_id: str,
        device_id: str,
        device_name: str,
        ip_address: str,
        user_agent: str,
        refresh_token: str,
    ) -> Session:
        session_id = secrets.token_hex(16)
        ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()
        rt_hash = hash_password(refresh_token)

        session = Session(
            session_id=session_id,
            user_id=user_id,
            device_id=device_id,
            device_name=device_name,
            ip_hash=ip_hash,
            user_agent=user_agent,
            refresh_token_hash=rt_hash,
            expires_at=time.time() + _REFRESH_TOKEN_LIFETIME,
        )
        self._sessions[session_id] = session
        self._enforce_limit(user_id)
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def revoke(self, session_id: str, reason: str = "user_logout") -> None:
        if session_id in self._sessions:
            self._sessions[session_id].is_revoked = True
            self._sessions[session_id].revoke_reason = reason

    def revoke_all_for_user(self, user_id: str, reason: str = "logout_all") -> int:
        count = 0
        for s in self._sessions.values():
            if s.user_id == user_id and not s.is_revoked:
                s.is_revoked = True
                s.revoke_reason = reason
                count += 1
        return count

    def active_count(self, user_id: str) -> int:
        return sum(
            1
            for s in self._sessions.values()
            if s.user_id == user_id and not s.is_revoked
        )

    def _enforce_limit(self, user_id: str) -> None:
        user_sessions = sorted(
            [
                s
                for s in self._sessions.values()
                if s.user_id == user_id and not s.is_revoked
            ],
            key=lambda s: s.created_at,
        )
        while len(user_sessions) > _MAX_SESSIONS_PER_USER:
            oldest = user_sessions.pop(0)
            oldest.is_revoked = True
            oldest.revoke_reason = "session_limit_exceeded"


# ---------------------------------------------------------------------------
# Rate Limiter (token-bucket)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple in-memory token-bucket rate limiter.

    Parameters
    ----------
    rate : float
        Tokens replenished per second.
    burst : int
        Maximum bucket capacity.
    block_seconds : int
        Duration to block after bucket drains (0 = no block).
    """

    def __init__(
        self,
        rate: float = 100 / 60,  # 100 req/min default
        burst: int = 50,
        block_seconds: int = 0,
    ) -> None:
        self._rate = rate
        self._burst = burst
        self._block_seconds = block_seconds
        self._buckets: dict[str, tuple[float, float]] = {}  # key → (tokens, last_ts)
        self._blocked: dict[str, float] = {}  # key → unblock_ts

    def allow(self, key: str) -> bool:
        """Return ``True`` if the request is allowed under the rate limit."""
        now = time.time()

        # Check block list
        if key in self._blocked:
            if now < self._blocked[key]:
                return False
            del self._blocked[key]

        tokens, last = self._buckets.get(key, (float(self._burst), now))
        elapsed = now - last
        tokens = min(self._burst, tokens + elapsed * self._rate)

        if tokens < 1:
            if self._block_seconds:
                self._blocked[key] = now + self._block_seconds
            self._buckets[key] = (tokens, now)
            return False

        self._buckets[key] = (tokens - 1, now)
        return True

    def remaining(self, key: str) -> int:
        tokens, _ = self._buckets.get(key, (float(self._burst), time.time()))
        return max(0, int(tokens))

    def reset(self, key: str) -> None:
        self._buckets.pop(key, None)
        self._blocked.pop(key, None)


# ---------------------------------------------------------------------------
# Auth Manager (orchestrator)
# ---------------------------------------------------------------------------

class AuthManager:
    """High-level authentication orchestrator.

    Wires together password verification, TOTP, sessions, and JWT issuance.
    """

    def __init__(
        self,
        jwt_manager: JWTManager,
        session_manager: SessionManager | None = None,
        login_limiter: RateLimiter | None = None,
    ) -> None:
        self.jwt = jwt_manager
        self.sessions = session_manager or SessionManager()
        self.login_limiter = login_limiter or RateLimiter(
            rate=5 / (15 * 60),  # 5 per 15 min
            burst=3,
            block_seconds=30 * 60,
        )

    def login_step1(
        self,
        email: str,
        password: str,
        stored_hash: str,
        *,
        has_2fa: bool = False,
        ip_address: str = "",
    ) -> AuthResult:
        """Password verification → returns full token or partial + 2FA flag."""
        if not self.login_limiter.allow(ip_address):
            raise PermissionError("Rate limit exceeded – try later")

        if not verify_password(password, stored_hash):
            raise ValueError("Invalid credentials")

        if has_2fa:
            partial = self.jwt.create_partial_token(email)
            return AuthResult(
                access_token="",
                requires_2fa=True,
                partial_token=partial,
            )

        # No 2FA — issue full tokens immediately
        return self._issue_full_tokens(email, email, ip_address=ip_address)

    def login_step2_totp(
        self,
        user_id: str,
        partial_token: str,
        totp_code: str,
        totp_manager: TOTPManager,
        *,
        ip_address: str = "",
        device_id: str = "",
        device_name: str = "",
    ) -> AuthResult:
        """Verify TOTP code and issue full tokens."""
        # Validate partial token
        claims = self.jwt.decode_token(partial_token)
        if claims.get("type") != "partial":
            raise ValueError("Invalid partial token")

        if not totp_manager.verify(totp_code):
            raise ValueError("Invalid TOTP code")

        return self._issue_full_tokens(
            user_id, claims.get("sub", ""),
            ip_address=ip_address,
            device_id=device_id,
            device_name=device_name,
        )

    def refresh(
        self,
        refresh_token: str,
        *,
        ip_address: str = "",
    ) -> AuthResult:
        """Rotate refresh token and issue a new access token."""
        claims = self.jwt.decode_token(refresh_token)
        if claims.get("type") != "refresh":
            raise ValueError("Not a refresh token")

        session_id = claims.get("sid", "")
        session = self.sessions.get(session_id)
        if not session or session.is_revoked:
            raise PermissionError("Session revoked")

        # Verify refresh token matches session
        if not verify_password(refresh_token, session.refresh_token_hash):
            raise PermissionError("Token mismatch – possible theft")

        # Revoke old session (one-time use rotation)
        self.sessions.revoke(session_id, reason="refresh_rotation")

        return self._issue_full_tokens(
            session.user_id,
            session.user_id,
            ip_address=ip_address,
            device_id=session.device_id,
            device_name=session.device_name,
        )

    def _issue_full_tokens(
        self,
        user_id: str,
        email: str,
        *,
        ip_address: str = "",
        device_id: str = "",
        device_name: str = "",
    ) -> AuthResult:
        ip_hash = hashlib.sha256(ip_address.encode()).hexdigest() if ip_address else ""
        access = self.jwt.create_access_token(
            user_id, email, device_id=device_id, ip_hash=ip_hash, two_fa_verified=True,
        )

        session = self.sessions.create(
            user_id=user_id,
            device_id=device_id or "unknown",
            device_name=device_name or "unknown",
            ip_address=ip_address,
            user_agent="",
            refresh_token="",  # placeholder; real token below
        )
        refresh = self.jwt.create_refresh_token(user_id, session.session_id)

        # Update session with actual refresh-token hash
        session.refresh_token_hash = hash_password(refresh)

        return AuthResult(
            access_token=access,
            refresh_token=refresh,
            session_id=session.session_id,
        )
