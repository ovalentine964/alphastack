# Alpha Stack — Encryption Security Fixes

> **Type:** Implementation Fix Guide for 3 Must-Fix Security Issues
> **Source:** `review_security_encryption.md` — V1, V2, V3
> **Date:** 2026-07-11
> **Status:** READY FOR IMPLEMENTATION

---

## Fix Summary

| # | Issue | Severity | CVSS | Fix Strategy |
|---|-------|----------|------|--------------|
| V1 | X25519 key derivation bug — Argon2id output fed as X25519 private key | HIGH (7.5) | Replace with `age` passphrase mode or direct symmetric cipher |
| V2 | Backup encryption commented out in Phase 1 | HIGH (7.1) | Uncomment GPG encryption, make it mandatory |
| V3 | Missing AAD in AES-256-GCM | MEDIUM (5.9) | Bind `{user_id}:{field_name}:{key_version}` as AAD |

---

## Fix 1: X25519 Key Derivation Bug (V1)

### Problem

In the Rust file-based credential fallback, the `derive_key()` function produces a 32-byte Argon2id hash. This hash is then passed directly to `age::x25519::Identity::from_bytes(key)`. This is a **type confusion**:

- Argon2id output is a **symmetric derived key** (arbitrary 32 bytes).
- X25519 `Identity::from_bytes()` expects a **private scalar** on the Curve25519 curve.
- While the bytes are technically interpreted as a scalar, the result violates the `age` specification and may produce weak or biased keys depending on the Argon2id output distribution.

### Chosen Fix: Use `age` Passphrase Mode (Option A)

This is the recommended approach because `age` internally applies **scrypt** KDF when given a passphrase — a proper, specification-compliant key derivation for password-based encryption. This eliminates the X25519 type confusion entirely.

### Before (Vulnerable Code)

```rust
use age::secrecy::ExposeSecret;

/// Derives a 32-byte key from password using Argon2id
fn derive_key(password: &str, salt: &[u8]) -> [u8; 32] {
    let mut output = [0u8; 32];
    argon2::Argon2::default()
        .hash_password_into(password.as_bytes(), salt, &mut output)
        .expect("Argon2id derivation failed");
    output
}

fn encrypt_credentials_file(
    path: &Path,
    password: &str,
    data: &str,
) -> Result<(), SecurityError> {
    let salt = age::secrecy::SecretVec::new(vec![/* ... */]);
    let key = derive_key(password, &salt);

    // BUG: Argon2id symmetric output used as X25519 private scalar
    let identity = age::x25519::Identity::from_bytes(key)
        .map_err(|_| SecurityError::KeyDerivationFailed)?;
    let recipient = identity.to_public();

    let encryptor = age::encryptor::Encryptor::with_recipients(
        vec![Box::new(recipient)]
    ).unwrap();

    let mut encrypted = vec![];
    let mut writer = encryptor.wrap_output(&mut encrypted)?;
    std::io::Write::write_all(&mut writer, data.as_bytes())?;
    writer.finish()?;

    std::fs::write(path, &encrypted)?;
    // ... set 0o600 permissions
    Ok(())
}

fn decrypt_credentials_file(
    path: &Path,
    password: &str,
) -> Result<String, SecurityError> {
    let salt = /* ... */;
    let key = derive_key(password, &salt);

    // BUG: Same type confusion on decryption side
    let identity = age::x25519::Identity::from_bytes(key)
        .map_err(|_| SecurityError::KeyDerivationFailed)?;

    let encrypted_data = std::fs::read(path)?;
    let decryptor = age::decryptor::Decryptor::new(&encrypted_data[..])?;
    let mut decrypted = vec![];
    let mut reader = decryptor.decrypt(
        std::iter::once(&identity as &dyn age::Identity)
    )?;
    std::io::Read::read_to_end(&mut reader, &mut decrypted)?;

    Ok(String::from_utf8(decrypted)?)
}
```

### After (Fixed Code — Passphrase Mode)

```rust
use age::secrecy::{ExposeSecret, Secret};
use std::io::{Read, Write};

fn encrypt_credentials_file(
    path: &Path,
    password: &str,
    data: &str,
) -> Result<(), SecurityError> {
    // age::Encryptor::with_user_passphrase uses scrypt internally.
    // No manual key derivation needed — no X25519 type confusion.
    let encryptor = age::Encryptor::with_user_passphrase(
        Secret::new(password.to_string())
    );

    let mut encrypted = vec![];
    let mut writer = encryptor.wrap_output(&mut encrypted)?;
    writer.write_all(data.as_bytes())?;
    writer.finish()?;

    std::fs::write(path, &encrypted)?;

    // Set file permissions to 0o600
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))?;
    }

    Ok(())
}

fn decrypt_credentials_file(
    path: &Path,
    password: &str,
) -> Result<String, SecurityError> {
    let encrypted_data = std::fs::read(path)?;

    let decryptor = age::decryptor::Decryptor::new(&encrypted_data[..])
        .map_err(|_| SecurityError::DecryptionFailed)?;

    // Decrypt with passphrase — scrypt KDF is applied internally
    let mut decrypted = vec![];
    let mut reader = decryptor.decrypt(
        std::iter::once(password as &str)
    ).map_err(|_| SecurityError::DecryptionFailed)?;
    reader.read_to_end(&mut decrypted)?;

    // Zeroize the password bytes after use
    // (Secret<String> handles this automatically for the age API)

    String::from_utf8(decrypted)
        .map_err(|_| SecurityError::InvalidUtf8)
}
```

### Alternative: Direct Symmetric Cipher (Option B)

If you prefer to keep Argon2id for key derivation (e.g., to reuse the same KDF used elsewhere), use the derived key directly with a symmetric AEAD cipher, bypassing X25519 entirely:

```rust
use chacha20poly1305::{
    aead::{Aead, KeyInit, OsRng},
    XChaCha20Poly1305, XNonce,
};

fn derive_key(password: &str, salt: &[u8]) -> [u8; 32] {
    let mut output = [0u8; 32];
    argon2::Argon2::default()
        .hash_password_into(password.as_bytes(), salt, &mut output)
        .expect("Argon2id derivation failed");
    output
}

fn encrypt_credentials_file(
    path: &Path,
    password: &str,
    data: &str,
) -> Result<(), SecurityError> {
    let salt = generate_salt(); // 16-byte CSPRNG salt
    let derived_key = derive_key(password, &salt);

    let cipher = XChaCha20Poly1305::new((&derived_key).into());

    // 24-byte nonce for XChaCha — larger nonce space eliminates collision risk
    let nonce = XChaCha20Poly1305::generate_nonce(&mut OsRng);

    let ciphertext = cipher.encrypt(&nonce, data.as_bytes())
        .map_err(|_| SecurityError::EncryptionFailed)?;

    // File format: [16-byte salt][24-byte nonce][ciphertext+tag]
    let mut output = Vec::with_capacity(16 + 24 + ciphertext.len());
    output.extend_from_slice(&salt);
    output.extend_from_slice(&nonce);
    output.extend_from_slice(&ciphertext);

    std::fs::write(path, &output)?;

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))?;
    }

    // Zeroize derived key
    zeroize::Zeroize::zeroize(&mut derived_key.clone());

    Ok(())
}

fn decrypt_credentials_file(
    path: &Path,
    password: &str,
) -> Result<String, SecurityError> {
    let file_data = std::fs::read(path)?;

    if file_data.len() < 40 {
        return Err(SecurityError::InvalidFileFormat);
    }

    let salt = &file_data[..16];
    let nonce = XNonce::from_slice(&file_data[16..40]);
    let ciphertext = &file_data[40..];

    let mut derived_key = derive_key(password, salt);
    let cipher = XChaCha20Poly1305::new((&derived_key).into());

    let plaintext = cipher.decrypt(nonce, ciphertext)
        .map_err(|_| SecurityError::DecryptionFailed)?;

    // Zeroize key material
    zeroize::Zeroize::zeroize(&mut derived_key);

    String::from_utf8(plaintext)
        .map_err(|_| SecurityError::InvalidUtf8)
}
```

### Recommended Choice

**Use Option A (passphrase mode)** for these reasons:

1. **Specification-compliant** — `age` passphrase mode is a well-specified, audited protocol
2. **Simpler code** — no manual Argon2id call, no salt management, no file format design
3. **Future-proof** — `age` handles algorithm upgrades internally
4. **Minimum changes** — smallest diff from current code

Option B is acceptable if you have a strong reason to keep Argon2id (e.g., tuning memory cost independently), but adds complexity.

### Also Fix: Directory Permissions

While fixing V1, also fix the directory permissions issue (Issue #4 from review):

```rust
// After fs::create_dir_all(&credentials_dir):
#[cfg(unix)]
{
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(
        &credentials_dir,
        std::fs::Permissions::from_mode(0o700),
    )?;
}
```

### Verification

```bash
# Run existing test suite
cargo test --package alphastack-credentials

# Add specific test for passphrase round-trip
#[test]
fn test_passphrase_encrypt_decrypt_roundtrip() {
    let dir = tempdir().unwrap();
    let path = dir.path().join("test_creds.enc");
    let password = "test-passphrase-with-entropy-2026!";
    let data = r#"{"account_id": "test-001", "api_key": "sk-live-abc123"}"#;

    encrypt_credentials_file(&path, password, data).unwrap();
    let decrypted = decrypt_credentials_file(&path, password).unwrap();

    assert_eq!(decrypted, data);
}

#[test]
fn test_wrong_passphrase_fails() {
    let dir = tempdir().unwrap();
    let path = dir.path().join("test_creds.enc");

    encrypt_credentials_file(&path, "correct-passphrase", "secret").unwrap();
    let result = decrypt_credentials_file(&path, "wrong-passphrase");

    assert!(result.is_err());
}
```

---

## Fix 2: Make Backup Encryption Mandatory (V2)

### Problem

In `architecture_data_storage.md` §7.2, the Phase 1 backup script has GPG encryption **commented out**. Unencrypted backups of a trading database expose trade history, account balances, and encrypted credential blobs to anyone with local disk access.

### Chosen Fix: Uncomment and Enforce GPG Encryption

### Before (Vulnerable Script)

```bash
#!/bin/bash
# backup.sh — Phase 1 Database Backup
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/alphastack"
DB_NAME="alphastack"

mkdir -p "$BACKUP_DIR"

# Dump database
pg_dump -Fc "$DB_NAME" > "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"

# TODO Phase 2: Add GPG encryption (optional for Phase 1)
# gpg --batch --yes --symmetric --cipher-algo AES256 \
#     --output "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump.gpg" \
#     "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"
# rm "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"

# Retain last 30 days
find "$BACKUP_DIR" -name "*.dump" -mtime +30 -delete
```

### After (Fixed Script — Encryption Mandatory)

```bash
#!/bin/bash
# backup.sh — Phase 1 Database Backup (Encryption MANDATORY)
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/alphastack"
DB_NAME="alphastack"

# --- Validate prerequisites ---
if [ -z "${BACKUP_GPG_PASSPHRASE:-}" ]; then
    echo "ERROR: BACKUP_GPG_PASSPHRASE environment variable is not set."
    echo "Backup encryption is MANDATORY. Aborting."
    exit 1
fi

# Check gpg is available
if ! command -v gpg &> /dev/null; then
    echo "ERROR: gpg is not installed. Cannot encrypt backup. Aborting."
    exit 1
fi

mkdir -p "$BACKUP_DIR"

# --- Dump database ---
echo "[$(date)] Dumping database '$DB_NAME'..."
pg_dump -Fc "$DB_NAME" > "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"

if [ ! -s "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump" ]; then
    echo "ERROR: Database dump is empty. Aborting."
    rm -f "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"
    exit 1
fi

# --- Encrypt backup (MANDATORY) ---
echo "[$(date)] Encrypting backup with AES-256..."
echo "$BACKUP_GPG_PASSPHRASE" | gpg \
    --batch \
    --yes \
    --passphrase-fd 0 \
    --symmetric \
    --cipher-algo AES256 \
    --compress-algo none \
    --output "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump.gpg" \
    "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"

# Verify encrypted file exists and is non-empty
if [ ! -s "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump.gpg" ]; then
    echo "ERROR: Encrypted backup file is missing or empty."
    rm -f "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"
    exit 1
fi

# --- Remove unencrypted dump IMMEDIATELY ---
rm -f "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"
echo "[$(date)] Unencrypted dump removed."

# --- Generate integrity hash ---
sha256sum "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump.gpg" \
    > "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump.gpg.sha256"

# --- Retain last 30 days of encrypted backups ---
find "$BACKUP_DIR" -name "*.dump.gpg" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.dump.gpg.sha256" -mtime +30 -delete

echo "[$(date)] Backup complete: alphastack_${TIMESTAMP}.dump.gpg"
```

### Key Changes

| Change | Why |
|--------|-----|
| **Fail if `BACKUP_GPG_PASSPHRASE` not set** | Prevents silent unencrypted backups if env var is misconfigured |
| **Fail if `gpg` not installed** | No silent fallback to plaintext |
| **Fail if dump is empty** | Catches pg_dump errors before encrypting garbage |
| **Verify encrypted file exists** | Catches GPG failures |
| **Remove unencrypted dump immediately** | Minimizes window of plaintext exposure |
| **SHA-256 integrity hash** | Enables tamper detection on backup files |
| **No `-o` on gpg** | Passphrase from env via `--passphrase-fd 0` avoids shell history exposure |

### Restoring a Backup

```bash
#!/bin/bash
# restore.sh — Decrypt and restore a backup
set -euo pipefail

BACKUP_FILE="$1"

if [ -z "${BACKUP_GPG_PASSPHRASE:-}" ]; then
    echo "ERROR: BACKUP_GPG_PASSPHRASE not set."
    exit 1
fi

# Verify integrity first
sha256sum -c "${BACKUP_FILE}.sha256"

# Decrypt
echo "$BACKUP_GPG_PASSPHRASE" | gpg \
    --batch \
    --yes \
    --passphrase-fd 0 \
    --decrypt \
    --output "/tmp/restore_$(basename "$BACKUP_FILE" .gpg)" \
    "$BACKUP_FILE"

# Restore
pg_restore -d alphastack --clean "/tmp/restore_$(basename "$BACKUP_FILE" .gpg)"

# Clean up decrypted file
rm -f "/tmp/restore_$(basename "$BACKUP_FILE" .gpg)"

echo "Restore complete."
```

### Secret Management for `BACKUP_GPG_PASSPHRASE`

The passphrase must be stored securely. Options by environment:

| Environment | Storage Method |
|-------------|---------------|
| **Production (server)** | HashiCorp Vault, AWS Secrets Manager, or systemd `EnvironmentFile` with 0o600 permissions |
| **Docker** | Docker secrets (`/run/secrets/backup_gpg_passphrase`) |
| **Development** | `.env` file (gitignored), 0o600 permissions |
| **CI/CD** | Encrypted CI secrets (GitHub Actions secrets, GitLab CI variables) |

**Never commit the passphrase to version control.**

### Verification

```bash
# 1. Run backup
BACKUP_GPG_PASSPHRASE="test-passphrase" ./backup.sh

# 2. Verify encrypted file exists, unencrypted does not
ls /var/backups/alphastack/*.dump.gpg     # Should exist
ls /var/backups/alphastack/*.dump          # Should NOT exist

# 3. Verify integrity hash
sha256sum -c /var/backups/alphastack/*.dump.gpg.sha256

# 4. Test restore
BACKUP_GPG_PASSPHRASE="test-passphrase" ./restore.sh /var/backups/alphastack/alphastack_*.dump.gpg

# 5. Verify backup cron is scheduled
crontab -l | grep backup
```

---

## Fix 3: Add AAD to AES-256-GCM (V3)

### Problem

In `FieldEncryptor.encrypt()` and `encrypt_credentials()`, the AES-256-GCM call passes `None` as AAD (Associated Authenticated Data):

```python
ciphertext = aesgcm.encrypt(nonce, plaintext, None)  # ← No AAD
```

Without AAD, AES-256-GCM only authenticates the ciphertext. An attacker with database write access could **swap encrypted fields** between rows (e.g., swap User A's TOTP secret with User B's) and the decryption would succeed without error — the ciphertext is valid, it just belongs to the wrong context.

### Chosen Fix: Bind Context as AAD

Encode `user_id`, `field_name`, and `key_version` into the AAD. On decryption, the same AAD must be provided; any tampering causes authentication failure.

### Before (Vulnerable Code)

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

class FieldEncryptor:
    def __init__(self, kms_client):
        self.kms = kms_client
        self._key_cache = {}

    def encrypt(
        self,
        plaintext: bytes,
        key_version: str,
        field_name: str = "",
    ) -> bytes:
        dek = self._get_dek(key_version)
        aesgcm = AESGCM(dek)
        nonce = os.urandom(12)

        # VULNERABLE: No AAD — ciphertext can be swapped between contexts
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        return nonce + ciphertext

    def decrypt(
        self,
        data: bytes,
        key_version: str,
        field_name: str = "",
    ) -> bytes:
        dek = self._get_dek(key_version)
        aesgcm = AESGCM(dek)
        nonce = data[:12]
        ciphertext = data[12:]

        # VULNERABLE: No AAD — accepts swapped ciphertext
        return aesgcm.decrypt(nonce, ciphertext, None)

    def _get_dek(self, version: str) -> bytes:
        if version not in self._key_cache:
            self._key_cache[version] = self.kms.generate_data_key(version)
        return self._key_cache[version]
```

### After (Fixed Code — With AAD)

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
from typing import Optional

class FieldEncryptor:
    def __init__(self, kms_client, cache_ttl_seconds: int = 3600):
        self.kms = kms_client
        self._key_cache = {}  # version -> (key, timestamp)
        self._cache_ttl = cache_ttl_seconds

    def encrypt(
        self,
        plaintext: bytes,
        key_version: str,
        field_name: str,
        user_id: str,
    ) -> bytes:
        dek = self._get_dek(key_version)
        aesgcm = AESGCM(dek)
        nonce = os.urandom(12)

        # AAD binds ciphertext to its context — prevents swapping attacks
        aad = self._build_aad(user_id, field_name, key_version)
        ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

        # Format: [12-byte nonce][ciphertext + 16-byte GCM tag]
        return nonce + ciphertext

    def decrypt(
        self,
        data: bytes,
        key_version: str,
        field_name: str,
        user_id: str,
    ) -> bytes:
        dek = self._get_dek(key_version)
        aesgcm = AESGCM(dek)
        nonce = data[:12]
        ciphertext = data[12:]

        # Same AAD required — any mismatch → authentication failure
        aad = self._build_aad(user_id, field_name, key_version)
        return aesgcm.decrypt(nonce, ciphertext, aad)

    @staticmethod
    def _build_aad(
        user_id: str,
        field_name: str,
        key_version: str,
    ) -> bytes:
        """
        Build Associated Authenticated Data from context fields.

        Uses a fixed format so encrypt and decrypt produce identical AAD.
        The colon-separated format is simple and unambiguous given that
        user_id, field_name, and key_version don't contain colons.
        """
        return f"{user_id}:{field_name}:{key_version}".encode("utf-8")

    def _get_dek(self, version: str) -> bytes:
        import time
        now = time.time()
        if version in self._key_cache:
            key, cached_at = self._key_cache[version]
            if now - cached_at < self._cache_ttl:
                return key
        key = self.kms.generate_data_key(version)
        self._key_cache[version] = (key, now)
        return key
```

### Also Fix: Server-Side `encrypt_credentials()`

The same fix applies to the higher-level credentials encryption function:

```python
# BEFORE:
def encrypt_credentials(self, user_id: str, credentials: dict) -> dict:
    encrypted = {}
    for field_name, value in credentials.items():
        plaintext = json.dumps(value).encode()
        encrypted[field_name] = self.encryptor.encrypt(
            plaintext, self.current_key_version, field_name
        )
    return encrypted

# AFTER:
def encrypt_credentials(self, user_id: str, credentials: dict) -> dict:
    encrypted = {}
    for field_name, value in credentials.items():
        plaintext = json.dumps(value).encode()
        encrypted[field_name] = self.encryptor.encrypt(
            plaintext,
            self.current_key_version,
            field_name=field_name,
            user_id=user_id,
        )
    return encrypted

def decrypt_credentials(self, user_id: str, encrypted: dict) -> dict:
    decrypted = {}
    for field_name, ciphertext in encrypted.items():
        plaintext = self.encryptor.decrypt(
            ciphertext,
            self.current_key_version,
            field_name=field_name,
            user_id=user_id,
        )
        decrypted[field_name] = json.loads(plaintext)
    return decrypted
```

### Migration for Existing Data

If there's existing data encrypted with `None` as AAD, migrate it:

```python
def migrate_field_encryption(
    self,
    user_id: str,
    field_name: str,
    old_data: bytes,
    old_key_version: str,
    new_key_version: str,
) -> bytes:
    """
    Decrypt with old AAD (None), re-encrypt with new AAD (context-bound).
    """
    # Decrypt using old method (no AAD)
    dek_old = self._get_dek(old_key_version)
    aesgcm_old = AESGCM(dek_old)
    nonce = old_data[:12]
    ciphertext = old_data[12:]
    plaintext = aesgcm_old.decrypt(nonce, ciphertext, None)  # old way

    # Re-encrypt with AAD
    return self.encrypt(plaintext, new_key_version, field_name, user_id)
```

Run the migration as a background job:

```python
async def migrate_all_fields(self):
    """One-time migration: re-encrypt all fields with AAD."""
    users = await self.db.get_all_users()
    for user in users:
        credentials = await self.db.get_encrypted_credentials(user.id)
        for field_name, old_ciphertext in credentials.items():
            new_ciphertext = self.migrate_field_encryption(
                user_id=user.id,
                field_name=field_name,
                old_data=old_ciphertext,
                old_key_version=self.previous_key_version,
                new_key_version=self.current_key_version,
            )
            await self.db.update_encrypted_credential(
                user.id, field_name, new_ciphertext
            )
    await self.db.retire_key_version(self.previous_key_version)
```

### AAD Format Rules

| Rule | Rationale |
|------|-----------|
| Use `":"` as separator | Unambiguous — user_id, field_name, key_version don't contain colons |
| Include `user_id` | Prevents swapping ciphertext between users |
| Include `field_name` | Prevents swapping between fields (e.g., api_key ↔ totp_secret) |
| Include `key_version` | Prevents swapping between DEK versions during rotation |
| Encode as UTF-8 | Consistent across Python versions and platforms |

### What AAD Prevents

| Attack | Without AAD | With AAD |
|--------|-------------|----------|
| Swap User A's TOTP ↔ User B's TOTP | ✅ Decryption succeeds — wrong secret used | ❌ Auth failure — `user_id` mismatch |
| Swap api_key ↔ totp_secret for same user | ✅ Decryption succeeds — wrong field exposed | ❌ Auth failure — `field_name` mismatch |
| Swap ciphertext from old DEK ↔ new DEK | ✅ Decryption succeeds with old key | ❌ Auth failure — `key_version` mismatch |
| Modify ciphertext bytes | ✅ Undetected (GCM tag is over ciphertext only) | ❌ Auth failure — tag includes AAD |

### Verification

```python
import pytest

def test_aad_prevents_user_swap():
    """Ciphertext from user A cannot be decrypted as user B."""
    encryptor = FieldEncryptor(mock_kms)

    # Encrypt for user A
    ct = encryptor.encrypt(b"secret_a", "v1", "api_key", user_id="user_A")

    # Try to decrypt as user B — must fail
    with pytest.raises(Exception):  # InvalidTag
        encryptor.decrypt(ct, "v1", "api_key", user_id="user_B")

def test_aad_prevents_field_swap():
    """Ciphertext for api_key cannot be decrypted as totp_secret."""
    encryptor = FieldEncryptor(mock_kms)

    ct = encryptor.encrypt(b"secret", "v1", "api_key", user_id="user_A")

    with pytest.raises(Exception):  # InvalidTag
        encryptor.decrypt(ct, "v1", "totp_secret", user_id="user_A")

def test_roundtrip_with_aad():
    """Normal encrypt/decrypt round-trip works with AAD."""
    encryptor = FieldEncryptor(mock_kms)
    plaintext = b"my-secret-api-key"

    ct = encryptor.encrypt(plaintext, "v1", "api_key", user_id="user_A")
    result = encryptor.decrypt(ct, "v1", "api_key", user_id="user_A")

    assert result == plaintext
```

---

## Implementation Checklist

### Fix 1 — X25519 Key Derivation
- [ ] Replace `derive_key()` + `Identity::from_bytes()` with `age::Encryptor::with_user_passphrase()`
- [ ] Update `encrypt_credentials_file()` function
- [ ] Update `decrypt_credentials_file()` function
- [ ] Remove unused `derive_key()` function
- [ ] Fix parent directory permissions to 0o700
- [ ] Add round-trip and wrong-passphrase tests
- [ ] Run `cargo clippy` — no new warnings
- [ ] Run `cargo test` — all pass

### Fix 2 — Backup Encryption Mandatory
- [ ] Uncomment GPG encryption in `backup.sh`
- [ ] Add pre-flight checks (env var, gpg available)
- [ ] Add post-backup verification (file exists, non-empty)
- [ ] Remove unencrypted dump immediately after encryption
- [ ] Add SHA-256 integrity hash generation
- [ ] Create `restore.sh` with integrity verification
- [ ] Document `BACKUP_GPG_PASSPHRASE` storage for each environment
- [ ] Update cron/systemd timer to use the fixed script
- [ ] Test: run backup → verify encrypted file → restore → verify data

### Fix 3 — AAD in AES-256-GCM
- [ ] Update `FieldEncryptor.encrypt()` — add `user_id` parameter, build AAD
- [ ] Update `FieldEncryptor.decrypt()` — add `user_id` parameter, build AAD
- [ ] Update `encrypt_credentials()` — pass `user_id` through
- [ ] Update `decrypt_credentials()` — pass `user_id` through
- [ ] Write data migration function for existing ciphertext
- [ ] Run migration as background job
- [ ] Add unit tests: user swap, field swap, round-trip
- [ ] Verify: no `None` as AAD anywhere in codebase (`grep -r "aad.*None\|None.*aad"`)

---

## Risk Assessment After Fixes

| Metric | Before Fixes | After Fixes |
|--------|-------------|-------------|
| **Encryption Architecture Rating** | 7.5/10 | 8.5/10 |
| **High-severity issues** | 3 | 0 |
| **Ciphertext swapping risk** | Possible | Eliminated (AAD) |
| **Key type confusion** | Present | Eliminated (passphrase mode) |
| **Backup exposure risk** | Unencrypted on disk | AES-256 encrypted |

---

*These fixes address all three must-find items from the security review. Apply them before Phase 1 implementation begins.*
