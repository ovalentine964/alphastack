"""Encryption layer — AES-256-GCM at rest, TLS 1.3 in transit, key rotation, encrypted config.

Implements the encryption architecture from architecture_security.md:
- AES-256-GCM for data at rest (field-level encryption)
- TLS 1.3 enforcement for data in transit
- Key rotation support with versioned DEKs
- Encrypted configuration storage
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NONCE_SIZE = 12  # 96-bit nonce for AES-GCM
_KEY_SIZE = 32  # 256-bit key
_TAG_SIZE = 16  # 128-bit GCM tag
_KEY_ROTATION_DAYS = 90
_GRACE_PERIOD_DAYS = 30


class KeyVersionStatus(str, Enum):
    """Lifecycle state of a data-encryption key."""
    ACTIVE = "active"
    GRACE = "grace"  # still usable for decryption, not for new encryption
    RETIRED = "retired"


@dataclass
class KeyVersion:
    """A single versioned DEK."""
    version: str
    key_material: bytes  # 32 bytes, stored only in memory
    created_at: float = field(default_factory=time.time)
    status: KeyVersionStatus = KeyVersionStatus.ACTIVE

    def is_usable(self) -> bool:
        return self.status in (KeyVersionStatus.ACTIVE, KeyVersionStatus.GRACE)


# ---------------------------------------------------------------------------
# Encryption Service
# ---------------------------------------------------------------------------

class EncryptionService:
    """AES-256-GCM field-level encryption with key versioning and rotation.

    Key hierarchy (simplified for Python layer):
        Master Key (env / KMS)  →  DEK versions (in-memory)

    In production the master key lives in an HSM/KMS; the DEK is wrapped
    (encrypted) before persistence.  This implementation keeps DEKs in
    memory and accepts a *master_key_bytes* parameter for wrapping.
    """

    def __init__(
        self,
        master_key: bytes | None = None,
        key_store_path: Path | None = None,
    ) -> None:
        self._master_key = master_key or self._load_master_key_from_env()
        self._key_store_path = key_store_path
        self._keys: dict[str, KeyVersion] = {}
        self._current_version: str | None = None

        # Load existing keys or bootstrap
        if key_store_path and key_store_path.exists():
            self._load_key_store()
        else:
            self._bootstrap()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encrypt(self, plaintext: str | bytes, *, aad: bytes | None = None) -> str:
        """Encrypt *plaintext* and return a self-describing base64 string.

        Format (base64-encoded)::

            version(UTF-8) ``:`` nonce(12 B) ``:`` ciphertext ‖ tag(16 B)
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        kv = self._active_key()
        aesgcm = AESGCM(kv.key_material)
        nonce = os.urandom(_NONCE_SIZE)
        ct = aesgcm.encrypt(nonce, plaintext, aad)

        packed = f"{kv.version}:".encode() + nonce + ct
        return base64.b64encode(packed).decode("ascii")

    def decrypt(self, token: str, *, aad: bytes | None = None) -> bytes:
        """Decrypt a token produced by :meth:`encrypt`."""
        raw = base64.b64decode(token)
        version_bytes, rest = raw.split(b":", 1)
        version = version_bytes.decode("ascii")
        nonce, ct = rest[:_NONCE_SIZE], rest[_NONCE_SIZE:]

        kv = self._get_key(version)
        if not kv or not kv.is_usable():
            raise ValueError(f"Key version {version!r} is not available")
        aesgcm = AESGCM(kv.key_material)
        return aesgcm.decrypt(nonce, ct, aad)

    # -- Key rotation -------------------------------------------------------

    def rotate(self) -> str:
        """Generate a new DEK version, mark the old one as *grace*.

        Returns the new version string.
        """
        if self._current_version and self._current_version in self._keys:
            self._keys[self._current_version].status = KeyVersionStatus.GRACE

        new_version = f"v{int(time.time())}"
        self._keys[new_version] = KeyVersion(
            version=new_version,
            key_material=os.urandom(_KEY_SIZE),
        )
        self._current_version = new_version
        self._persist_key_store()
        return new_version

    def retire_grace_keys(self) -> list[str]:
        """Mark all *grace* keys as *retired*.  Returns retired version ids."""
        retired: list[str] = []
        for kv in self._keys.values():
            if kv.status == KeyVersionStatus.GRACE:
                kv.status = KeyVersionStatus.RETIRED
                retired.append(kv.version)
        if retired:
            self._persist_key_store()
        return retired

    # -- Encrypted config ---------------------------------------------------

    def encrypt_config(self, config: dict[str, Any], path: Path) -> None:
        """Write *config* as an encrypted JSON file at *path*."""
        blob = json.dumps(config, separators=(",", ":")).encode()
        token = self.encrypt(blob)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token, encoding="utf-8")

    def decrypt_config(self, path: Path) -> dict[str, Any]:
        """Read and decrypt a config file produced by :meth:`encrypt_config`."""
        token = path.read_text(encoding="utf-8")
        return json.loads(self.decrypt(token))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bootstrap(self) -> None:
        """Create the initial DEK."""
        version = f"v{int(time.time())}"
        self._keys[version] = KeyVersion(
            version=version,
            key_material=os.urandom(_KEY_SIZE),
        )
        self._current_version = version
        self._persist_key_store()

    def _active_key(self) -> KeyVersion:
        if not self._current_version:
            raise RuntimeError("No active encryption key")
        kv = self._keys[self._current_version]
        assert kv.status == KeyVersionStatus.ACTIVE
        return kv

    def _get_key(self, version: str) -> KeyVersion | None:
        return self._keys.get(version)

    # -- Persistence (encrypted key store) ----------------------------------

    def _wrap_key(self, dek: bytes) -> bytes:
        """Wrap a DEK with the master key using AES-GCM (nonce prepended)."""
        aesgcm = AESGCM(self._master_key)
        nonce = os.urandom(_NONCE_SIZE)
        return nonce + aesgcm.encrypt(nonce, dek, None)

    def _unwrap_key(self, wrapped: bytes) -> bytes:
        aesgcm = AESGCM(self._master_key)
        nonce, ct = wrapped[:_NONCE_SIZE], wrapped[_NONCE_SIZE:]
        return aesgcm.decrypt(nonce, ct, None)

    def _persist_key_store(self) -> None:
        if not self._key_store_path:
            return
        store: dict[str, Any] = {"current_version": self._current_version, "keys": {}}
        for ver, kv in self._keys.items():
            store["keys"][ver] = {
                "wrapped_key": base64.b64encode(self._wrap_key(kv.key_material)).decode(),
                "created_at": kv.created_at,
                "status": kv.status.value,
            }
        self._key_store_path.parent.mkdir(parents=True, exist_ok=True)
        self._key_store_path.write_text(
            json.dumps(store, indent=2), encoding="utf-8"
        )
        # Restrict permissions on Unix
        try:
            self._key_store_path.chmod(0o600)
        except OSError:
            pass

    def _load_key_store(self) -> None:
        store = json.loads(self._key_store_path.read_text(encoding="utf-8"))
        self._current_version = store.get("current_version")
        for ver, meta in store.get("keys", {}).items():
            self._keys[ver] = KeyVersion(
                version=ver,
                key_material=self._unwrap_key(base64.b64decode(meta["wrapped_key"])),
                created_at=meta.get("created_at", 0.0),
                status=KeyVersionStatus(meta.get("status", "active")),
            )

    @staticmethod
    def _load_master_key_from_env() -> bytes:
        """Load master key from ALPHASTACK_MASTER_KEY env var (base64-encoded)."""
        b64 = os.environ.get("ALPHASTACK_MASTER_KEY", "")
        if not b64:
            # Dev fallback – deterministic key (NEVER use in production)
            return hashlib.sha256(b"alphastack-dev-master-key").digest()
        return base64.b64decode(b64)


# ---------------------------------------------------------------------------
# TLS helpers
# ---------------------------------------------------------------------------

def require_tls_context():
    """Return a pre-configured ``ssl.SSLContext`` enforcing TLS 1.3.

    Raises :class:`RuntimeError` if TLS 1.3 is not available.
    """
    import ssl

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx
