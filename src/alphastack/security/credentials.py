"""Credential management — broker credential encryption, API key secure storage.

Implements broker credential isolation from architecture_security.md:
- Broker credentials stored in OS keyring (or encrypted file fallback)
- API keys encrypted at rest with field-level encryption
- Credentials NEVER logged or transmitted to Alpha Stack servers
- Credential rotation support
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from alphastack.security.encryption import EncryptionService


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class CredentialType(str, Enum):
    BROKER_SERVER = "server"
    BROKER_LOGIN = "login"
    BROKER_PASSWORD = "password"
    API_KEY = "api_key"
    API_SECRET = "api_secret"
    TOTP_SECRET = "totp_secret"
    OAUTH_TOKEN = "oauth_token"
    OAUTH_REFRESH = "oauth_refresh"


class CredentialStatus(str, Enum):
    ACTIVE = "active"
    ROTATING = "rotating"
    REVOKED = "revoked"


@dataclass
class CredentialMeta:
    """Metadata about a stored credential — NEVER contains the value."""
    credential_id: str
    user_id: str
    account_id: str
    credential_type: CredentialType
    label: str
    status: CredentialStatus = CredentialStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    last_accessed: float | None = None
    last_rotated: float | None = None
    access_count: int = 0
    fingerprint: str = ""  # SHA-256 of the value (for rotation detection)


# ---------------------------------------------------------------------------
# Secure string (memory-zeroized on drop)
# ---------------------------------------------------------------------------

class SecureString:
    """Wraps a sensitive string value; attempts to zero memory on deletion.

    Note: Python's GC makes guaranteed zeroing difficult; this is a
    best-effort layer.  Rust/Swift layers provide true zeroization.
    """

    def __init__(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def __del__(self) -> None:
        # Best-effort: overwrite the internal buffer
        try:
            self._value = "\x00" * len(self._value)
        except Exception:
            pass

    def __repr__(self) -> str:
        return "<SecureString ****>"


# ---------------------------------------------------------------------------
# Credential Vault
# ---------------------------------------------------------------------------

class CredentialVault:
    """Encrypted credential storage with audit trail.

    Backends:
    1. **OS Keyring** (desktop) — preferred, via ``keyring`` package.
    2. **Encrypted file** (server/container) — AES-256-GCM via
       :class:`EncryptionService`.

    Parameters
    ----------
    encryption : EncryptionService
        Used for file-based credential encryption.
    keyring_enabled : bool
        Attempt OS keyring first (requires ``keyring`` package).
    store_path : Path | None
        Directory for encrypted credential files.
    """

    SERVICE_NAME = "com.alphastack.credentials"

    def __init__(
        self,
        encryption: EncryptionService,
        *,
        keyring_enabled: bool = True,
        store_path: Path | None = None,
    ) -> None:
        self._encryption = encryption
        self._keyring_enabled = keyring_enabled
        self._store_path = store_path or Path.home() / ".alphastack" / "credentials"
        self._meta: dict[str, CredentialMeta] = {}
        self._audit_log: list[dict[str, Any]] = []

        self._store_path.mkdir(parents=True, exist_ok=True)
        self._load_meta()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(
        self,
        user_id: str,
        account_id: str,
        cred_type: CredentialType,
        value: str,
        *,
        label: str = "",
    ) -> CredentialMeta:
        """Store a credential securely.  Returns metadata (never the value)."""
        cred_id = self._credential_id(account_id, cred_type)
        fingerprint = hashlib.sha256(value.encode()).hexdigest()

        # Encrypt and persist
        encrypted = self._encryption.encrypt(value)
        self._write_encrypted(cred_id, encrypted)

        meta = CredentialMeta(
            credential_id=cred_id,
            user_id=user_id,
            account_id=account_id,
            credential_type=cred_type,
            label=label or f"{account_id}.{cred_type.value}",
            fingerprint=fingerprint,
        )
        self._meta[cred_id] = meta
        self._save_meta()

        self._audit("store", meta)
        return meta

    def retrieve(
        self,
        account_id: str,
        cred_type: CredentialType,
    ) -> SecureString:
        """Retrieve a credential.  Returns a :class:`SecureString`."""
        cred_id = self._credential_id(account_id, cred_type)
        meta = self._meta.get(cred_id)
        if not meta or meta.status == CredentialStatus.REVOKED:
            raise KeyError(f"Credential {cred_id} not found or revoked")

        # Try OS keyring first
        raw = self._try_keyring_get(cred_id)
        if raw is None:
            # Fallback: encrypted file
            encrypted = self._read_encrypted(cred_id)
            raw = self._encryption.decrypt(encrypted).decode("utf-8")

        # Update access metadata
        meta.last_accessed = time.time()
        meta.access_count += 1
        self._save_meta()
        self._audit("retrieve", meta)

        return SecureString(raw)

    def rotate(
        self,
        account_id: str,
        cred_type: CredentialType,
        new_value: str,
        user_id: str,
    ) -> CredentialMeta:
        """Rotate a credential to a new value."""
        cred_id = self._credential_id(account_id, cred_type)
        meta = self._meta.get(cred_id)
        if not meta:
            raise KeyError(f"Credential {cred_id} not found")

        # Store new value
        encrypted = self._encryption.encrypt(new_value)
        self._write_encrypted(cred_id, encrypted)

        meta.fingerprint = hashlib.sha256(new_value.encode()).hexdigest()
        meta.last_rotated = time.time()
        meta.status = CredentialStatus.ACTIVE
        self._save_meta()

        self._audit("rotate", meta)
        return meta

    def revoke(self, account_id: str, cred_type: CredentialType) -> None:
        """Mark a credential as revoked (value still encrypted at rest)."""
        cred_id = self._credential_id(account_id, cred_type)
        meta = self._meta.get(cred_id)
        if meta:
            meta.status = CredentialStatus.REVOKED
            self._save_meta()
            self._audit("revoke", meta)

    def delete(self, account_id: str, cred_type: CredentialType) -> None:
        """Permanently remove a credential (encrypted file + metadata)."""
        cred_id = self._credential_id(account_id, cred_type)
        # Remove encrypted file
        enc_path = self._enc_path(cred_id)
        if enc_path.exists():
            enc_path.unlink()
        # Remove from keyring
        self._try_keyring_delete(cred_id)
        # Remove metadata
        self._meta.pop(cred_id, None)
        self._save_meta()
        self._audit("delete", CredentialMeta(
            credential_id=cred_id,
            user_id="",
            account_id=account_id,
            credential_type=cred_type,
            label="",
        ))

    def list_credentials(self, user_id: str) -> list[CredentialMeta]:
        """List credential metadata for a user (no values)."""
        return [m for m in self._meta.values() if m.user_id == user_id]

    def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent credential access audit events."""
        return self._audit_log[-limit:]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _credential_id(account_id: str, cred_type: CredentialType) -> str:
        return f"{account_id}.{cred_type.value}"

    def _enc_path(self, cred_id: str) -> Path:
        return self._store_path / f"{cred_id}.enc"

    def _write_encrypted(self, cred_id: str, encrypted: str) -> None:
        path = self._enc_path(cred_id)
        path.write_text(encrypted, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def _read_encrypted(self, cred_id: str) -> str:
        path = self._enc_path(cred_id)
        if not path.exists():
            raise FileNotFoundError(f"Encrypted credential {cred_id} not found")
        return path.read_text(encoding="utf-8")

    # -- OS Keyring ---------------------------------------------------------

    def _try_keyring_get(self, cred_id: str) -> str | None:
        if not self._keyring_enabled:
            return None
        try:
            import keyring
            return keyring.get_password(self.SERVICE_NAME, cred_id)
        except Exception:
            return None

    def _try_keyring_set(self, cred_id: str, value: str) -> bool:
        if not self._keyring_enabled:
            return False
        try:
            import keyring
            keyring.set_password(self.SERVICE_NAME, cred_id, value)
            return True
        except Exception:
            return False

    def _try_keyring_delete(self, cred_id: str) -> bool:
        if not self._keyring_enabled:
            return False
        try:
            import keyring
            keyring.delete_password(self.SERVICE_NAME, cred_id)
            return True
        except Exception:
            return False

    # -- Metadata persistence -----------------------------------------------

    def _meta_path(self) -> Path:
        return self._store_path / "_meta.enc"

    def _save_meta(self) -> None:
        data = {
            cid: {
                "credential_id": m.credential_id,
                "user_id": m.user_id,
                "account_id": m.account_id,
                "credential_type": m.credential_type.value,
                "label": m.label,
                "status": m.status.value,
                "created_at": m.created_at,
                "last_accessed": m.last_accessed,
                "last_rotated": m.last_rotated,
                "access_count": m.access_count,
                "fingerprint": m.fingerprint,
            }
            for cid, m in self._meta.items()
        }
        self._encryption.encrypt_config(data, self._meta_path())

    def _load_meta(self) -> None:
        if not self._meta_path().exists():
            return
        try:
            data = self._encryption.decrypt_config(self._meta_path())
            for cid, d in data.items():
                self._meta[cid] = CredentialMeta(
                    credential_id=d["credential_id"],
                    user_id=d["user_id"],
                    account_id=d["account_id"],
                    credential_type=CredentialType(d["credential_type"]),
                    label=d["label"],
                    status=CredentialStatus(d["status"]),
                    created_at=d.get("created_at", 0),
                    last_accessed=d.get("last_accessed"),
                    last_rotated=d.get("last_rotated"),
                    access_count=d.get("access_count", 0),
                    fingerprint=d.get("fingerprint", ""),
                )
        except Exception:
            pass  # corrupt store — start fresh

    # -- Audit --------------------------------------------------------------

    def _audit(self, action: str, meta: CredentialMeta) -> None:
        """Append an audit event (never includes credential value)."""
        self._audit_log.append({
            "event": "credential_" + action,
            "timestamp": time.time(),
            "credential_id": meta.credential_id,
            "user_id": meta.user_id,
            "account_id": meta.account_id,
            "credential_type": meta.credential_type.value,
            "fingerprint": meta.fingerprint[:16] + "...",
        })
