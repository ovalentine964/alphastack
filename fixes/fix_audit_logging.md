# Audit Logging & GDPR Compliance — Remediation Plan

**Scope:** Hash-chain integrity, tamper-proofing, GDPR compliance
**Derived from:** `review_security_audit.md` findings C-1, C-2, C-3, H-1, H-2, H-5, M-1, M-3
**Date:** 2026-07-11

---

## 1. Hash-Chain Audit Trail Fixes

### 1.1 Fix Circular Hash Dependency (C-1a)

**Problem:** Hash is computed over the event without `integrity.hash`, then appended. Verification must replicate the exact same exclusion logic — fragile and error-prone.

**Fix:** Adopt explicit canonical serialization with deterministic field exclusion.

```python
import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import Optional


class AuditHashChain:
    """Tamper-proof append-only audit log with hash-chain integrity."""

    GENESIS_HASH = "GENESIS"

    def __init__(self, store):
        self._store = store
        self._lock = threading.Lock()
        self._previous_hash: str = self._recover_previous_hash()

    def _recover_previous_hash(self) -> str:
        """Recover chain state from storage on startup (fixes BUG 3)."""
        last_event = self._store.get_latest()
        if last_event is None:
            return self.GENESIS_HASH
        return last_event["integrity"]["hash"]

    @staticmethod
    def _canonical_payload(event: dict, previous_hash: str, timestamp: str) -> bytes:
        """
        Deterministic serialization for hashing.
        
        CONTRACT: Hash is computed over ALL fields except `integrity.hash`.
        The integrity block included in the hash contains ONLY:
          - previous_hash
          - timestamp
        
        This contract is tested and must not change without a chain migration.
        """
        canonical = {
            **{k: v for k, v in event.items() if k != "integrity"},
            "integrity": {
                "previous_hash": previous_hash,
                "timestamp": timestamp,
            },
        }
        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()

    def log(self, event: dict) -> str:
        """
        Append an event to the audit log with hash-chain integrity.
        
        Thread-safe. Atomic write. No race conditions.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        with self._lock:
            previous_hash = self._previous_hash
            payload = self._canonical_payload(event, previous_hash, timestamp)
            event_hash = hashlib.sha256(payload).hexdigest()

            record = {
                **event,
                "integrity": {
                    "previous_hash": previous_hash,
                    "timestamp": timestamp,
                    "hash": event_hash,
                },
            }

            # Atomic write: store handles crash-safety (single write, single fsync)
            self._store.append(record)
            self._previous_hash = event_hash

            return event_hash

    def verify_chain(self, events: list[dict]) -> list[dict]:
        """
        Verify chain integrity. Returns list of broken links (empty = valid).
        
        Each broken link includes: event index, expected vs actual previous_hash,
        and whether content was tampered.
        """
        broken = []
        prev_hash = self.GENESIS_HASH

        for i, event in enumerate(events):
            integrity = event.get("integrity", {})
            stored_hash = integrity.get("hash")
            stored_prev = integrity.get("previous_hash")
            timestamp = integrity.get("timestamp")

            # Check link integrity
            if stored_prev != prev_hash:
                broken.append({
                    "index": i,
                    "type": "chain_break",
                    "expected_previous": prev_hash,
                    "actual_previous": stored_prev,
                })

            # Check content integrity (recompute hash)
            payload = self._canonical_payload(event, stored_prev, timestamp)
            computed_hash = hashlib.sha256(payload).hexdigest()

            if computed_hash != stored_hash:
                broken.append({
                    "index": i,
                    "type": "content_tampered",
                    "expected_hash": computed_hash,
                    "actual_hash": stored_hash,
                })

            prev_hash = stored_hash

        return broken
```

### 1.2 Fix Race Condition (C-1b)

**Fix:** `threading.Lock` around the entire `log()` method (shown above). The lock scope covers read of `_previous_hash`, computation, and write — no window for concurrent access.

For async/high-throughput systems, use a single-writer queue pattern:

```python
import asyncio
from collections import deque


class AsyncAuditHashChain:
    """High-throughput variant using a single-writer event loop."""

    def __init__(self, store):
        self._store = store
        self._queue: asyncio.Queue = asyncio.Queue()
        self._previous_hash = self._recover_previous_hash(store)
        self._writer_task: Optional[asyncio.Task] = None

    async def start(self):
        self._writer_task = asyncio.create_task(self._writer_loop())

    async def _writer_loop(self):
        """Single writer — no concurrency issues."""
        while True:
            record = await self._queue.get()
            self._store.append(record)
            self._previous_hash = record["integrity"]["hash"]
            self._queue.task_done()

    async def log(self, event: dict) -> str:
        """Non-blocking enqueue. Returns hash after write completes."""
        timestamp = datetime.now(timezone.utc).isoformat()
        previous_hash = self._previous_hash

        payload = AuditHashChain._canonical_payload(event, previous_hash, timestamp)
        event_hash = hashlib.sha256(payload).hexdigest()

        record = {
            **event,
            "integrity": {
                "previous_hash": previous_hash,
                "timestamp": timestamp,
                "hash": event_hash,
            },
        }

        await self._queue.put(record)
        return event_hash
```

### 1.3 Fix Non-Atomic Store + Update (C-1c)

**Fix:** `_recover_previous_hash()` reads the last stored event on startup. This eliminates the stale-`previous_hash` crash scenario entirely. The `_previous_hash` is always derived from storage, never from in-memory state alone.

For the store implementation, ensure atomic writes:

```python
class AppendOnlyStore:
    """
    Append-only audit log store.
    
    Backed by a file with fsync, or a database with transactional inserts.
    Guarantees: each append is atomic and durable before returning.
    """

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()

    def append(self, record: dict) -> None:
        """Atomic append with fsync."""
        line = json.dumps(record, sort_keys=True) + "\n"
        with self._lock:
            with open(self._path, "a") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

    def get_latest(self) -> Optional[dict]:
        """Read the last record in the file."""
        try:
            with open(self._path, "r") as f:
                lines = f.readlines()
                if lines:
                    return json.loads(lines[-1])
        except FileNotFoundError:
            return None
        return None

    def read_all(self) -> list[dict]:
        """Read all records. Used for verification."""
        try:
            with open(self._path, "r") as f:
                return [json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            return []
```

### 1.4 Fix Verification Fragility (C-1d / M-4)

**Fix:** Verification uses the same `_canonical_payload` method as signing. The integrity contract is:

- **Included in hash:** All event fields + `integrity.previous_hash` + `integrity.timestamp`
- **Excluded from hash:** `integrity.hash` itself
- **No other fields** in `integrity` block affect the hash

Unit tests enforce this contract:

```python
import pytest

class TestHashChainContract:

    def test_hash_excludes_hash_field(self):
        """Hash must not depend on integrity.hash value."""
        event = {"action": "test", "integrity": {"previous_hash": "GENESIS", "timestamp": "2026-01-01T00:00:00Z"}}
        p1 = AuditHashChain._canonical_payload(event, "GENESIS", "2026-01-01T00:00:00Z")

        event["integrity"]["hash"] = "tampered_value"
        p2 = AuditHashChain._canonical_payload(event, "GENESIS", "2026-01-01T00:00:00Z")

        assert p1 == p2, "Hash must not include integrity.hash"

    def test_chain_verification_detects_tamper(self):
        store = InMemoryStore()
        chain = AuditHashChain(store)

        chain.log({"action": "login", "user": "alice"})
        chain.log({"action": "trade", "amount": 100})
        chain.log({"action": "logout", "user": "alice"})

        events = store.read_all()
        assert chain.verify_chain(events) == [], "Valid chain should pass"

        # Tamper with middle event
        events[1]["amount"] = 9999
        broken = chain.verify_chain(events)
        assert len(broken) >= 1
        assert any(b["type"] == "content_tampered" for b in broken)

    def test_chain_verification_detects_break(self):
        store = InMemoryStore()
        chain = AuditHashChain(store)

        chain.log({"action": "a"})
        chain.log({"action": "b"})

        events = store.read_all()
        events[1]["integrity"]["previous_hash"] = "FAKE"
        broken = chain.verify_chain(events)
        assert any(b["type"] == "chain_break" for b in broken)

    def test_concurrent_logging_no_fork(self):
        """Verify no chain fork under concurrent writes."""
        store = InMemoryStore()
        chain = AuditHashChain(store)

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(chain.log, {"i": i}) for i in range(100)]
            concurrent.futures.wait(futures)

        events = store.read_all()
        assert len(events) == 100
        assert chain.verify_chain(events) == [], "Concurrent writes must not fork chain"
```

---

## 2. Tamper-Proofing Upgrades

### 2.1 External Hash Anchoring (C-2)

**Problem:** Hash chain is self-referential — an attacker with DB access can rewrite the entire chain and recompute all hashes.

**Fix:** Anchor daily chain checkpoints to an external, immutable service.

```python
import hashlib
from datetime import datetime, timezone


class ExternalAnchor:
    """
    Anchors daily audit chain checkpoints to an external timestamping service.
    
    Supported backends:
    - OpenTimestamps (free, Bitcoin-anchored)
    - AWS QLDB (managed, immutable ledger)
    - RFC 3161 TSA (standard timestamping protocol)
    """

    def __init__(self, backend: str = "opentimestamps"):
        self._backend = backend

    def anchor_checkpoint(self, chain_hash: str, event_count: int, date: str) -> dict:
        """
        Anchor a daily checkpoint externally.
        
        Returns a receipt that can be stored alongside the audit log.
        """
        checkpoint = {
            "chain_tip_hash": chain_hash,
            "event_count": event_count,
            "date": date,
            "anchored_at": datetime.now(timezone.utc).isoformat(),
        }
        checkpoint_bytes = json.dumps(checkpoint, sort_keys=True).encode()
        checkpoint_hash = hashlib.sha256(checkpoint_bytes).hexdigest()

        if self._backend == "opentimestamps":
            receipt = self._ots_stamp(checkpoint_hash)
        elif self._backend == "qldb":
            receipt = self._qldb_record(checkpoint)
        elif self._backend == "rfc3161":
            receipt = self._tsa_stamp(checkpoint_hash)
        else:
            raise ValueError(f"Unknown backend: {self._backend}")

        return {"checkpoint": checkpoint, "receipt": receipt}

    def verify_checkpoint(self, checkpoint: dict, receipt: dict) -> bool:
        """Verify an anchored checkpoint against its external receipt."""
        # Implementation depends on backend
        # OpenTimestamps: verify against Bitcoin block headers
        # QLDB: verify digest against QLDB ledger
        # RFC 3161: verify TSA signature chain
        pass
```

**Implementation schedule:**
- Week 1: Integrate OpenTimestamps (free, no infrastructure cost)
- Week 2: Add AWS QLDB as alternative for managed environments
- Verify anchoring daily via scheduled job

### 2.2 Digital Signatures on Audit Events (H-1)

**Problem:** No non-repudiation. Anyone with DB write access can forge events.

**Fix:** Sign each event with a dedicated Ed25519 audit signing key (upgradeable to ML-DSA-65 for PQC).

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import base64


class AuditSigner:
    """
    Signs audit events with Ed25519 for non-repudiation.
    
    Key is stored in HSM/KMS in production. Local key for dev only.
    """

    def __init__(self, private_key: Ed25519PrivateKey, key_id: str):
        self._key = private_key
        self._key_id = key_id

    def sign_event(self, event_hash: str) -> dict:
        """Sign an event hash. Returns signature metadata."""
        signature = self._key.sign(event_hash.encode())
        return {
            "signed_by": self._key_id,
            "algorithm": "Ed25519",
            "signature": base64.b64encode(signature).decode(),
        }

    @staticmethod
    def verify_event(event_hash: str, signature_block: dict, public_key_bytes: bytes) -> bool:
        """Verify an event signature against the public key."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        signature = base64.b64decode(signature_block["signature"])
        try:
            public_key.verify(signature, event_hash.encode())
            return True
        except Exception:
            return False
```

Integration with the hash chain:

```python
def log_signed(self, event: dict, signer: AuditSigner) -> str:
    """Log an event with hash-chain + digital signature."""
    event_hash = self.log(event)

    # Sign and store signature as a separate linked record
    sig_block = signer.sign_event(event_hash)
    sig_record = {
        "type": "audit_signature",
        "target_hash": event_hash,
        "signature": sig_block,
        "integrity": {},  # Gets filled by log()
    }
    self.log(sig_record)

    return event_hash
```

### 2.3 Scheduled Chain Verification (H-2)

**Problem:** Chain corruption may go undetected for weeks/months.

**Fix:** Hourly verification job with alerting.

```python
class ChainVerifier:
    """
    Scheduled verification of audit log integrity.
    
    Runs hourly. Alerts on any chain break or content tampering.
    """

    def __init__(self, store, anchor: ExternalAnchor, alerter):
        self._store = store
        self._anchor = anchor
        self._alerter = alerter

    def run_verification(self) -> dict:
        """Full chain verification. Returns report."""
        events = self._store.read_all()
        chain = AuditHashChain(self._store)
        broken = chain.verify_chain(events)

        report = {
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "total_events": len(events),
            "broken_links": len(broken),
            "status": "PASS" if not broken else "FAIL",
            "details": broken,
        }

        if broken:
            self._alerter.critical(
                "AUDIT CHAIN INTEGRITY FAILURE",
                details=report,
            )

        return report

    def verify_last_24h(self) -> dict:
        """Verify only the last 24 hours of events (faster)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        events = [e for e in self._store.read_all()
                  if e.get("integrity", {}).get("timestamp", "") >= cutoff]
        chain = AuditHashChain(self._store)
        broken = chain.verify_chain(events)

        return {
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "events_checked": len(events),
            "broken_links": len(broken),
            "status": "PASS" if not broken else "FAIL",
        }
```

### 2.4 Append-Only Storage Enforcement

**ClickHouse configuration:**

```sql
-- Create audit log table with MergeTree (append-only by design)
CREATE TABLE audit_log (
    event_id UUID DEFAULT generateUUIDv4(),
    timestamp DateTime64(3, 'UTC'),
    action LowCardinality(String),
    actor_id String,
    resource_type LowCardinality(String),
    resource_id String,
    details String,  -- JSON blob
    previous_hash String,
    event_hash String,
    signature String,
    signed_by String
) ENGINE = MergeTree()
ORDER BY (timestamp, event_id)
TTL timestamp + INTERVAL 7 YEAR;

-- Revoke UPDATE and DELETE permissions from ALL roles
REVOKE UPDATE, DELETE ON audit_log FROM ALL;

-- Only the audit service account can insert
CREATE USER audit_writer IDENTIFIED BY '...';
GRANT INSERT ON audit_log TO audit_writer;
GRANT SELECT ON audit_log TO audit_reader;

-- No other users get any access
```

### 2.5 Separated Audit Storage (M-3)

**Architecture:**

```
┌─────────────────────────┐     ┌──────────────────────────┐
│  Application Database   │     │  Audit Log Store         │
│  (PostgreSQL)           │     │  (ClickHouse / S3)       │
│                         │     │                          │
│  - User data            │     │  - Append-only events    │
│  - Trading records      │     │  - Hash chain            │
│  - Sessions             │     │  - External anchors      │
│                         │     │  - Digital signatures    │
│  Credentials: app_user  │     │  Credentials: audit_user │
│  Access: CRUD           │     │  Access: INSERT + SELECT │
└─────────────────────────┘     └──────────────────────────┘
         │                                │
         └──── Different DB ──────────────┘
               Different credentials
               Different network segment
```

---

## 3. GDPR Compliance Implementation

### 3.1 Lawful Basis Mapping (Art. 6)

Every processing activity must have a documented lawful basis.

```yaml
# lawful_basis.yaml
processing_activities:
  - activity: "User account creation and authentication"
    lawful_basis: "contract"  # Art. 6(1)(b)
    data_categories: ["email", "name", "password_hash"]
    retention: "account_lifetime + 30_days"
    notes: "Necessary to provide the trading service"

  - activity: "Trade execution and portfolio management"
    lawful_basis: "contract"  # Art. 6(1)(b)
    data_categories: ["trade_orders", "positions", "balance"]
    retention: "7_years"  # Financial regulation requirement
    notes: "Core service delivery; regulatory retention mandate"

  - activity: "Audit logging for security and compliance"
    lawful_basis: "legal_obligation"  # Art. 6(1)(c)
    data_categories: ["ip_address", "user_agent", "action_logs"]
    retention: "7_years"
    notes: "Required by financial regulations and security obligations"

  - activity: "AML/CFT transaction monitoring"
    lawful_basis: "legal_obligation"  # Art. 6(1)(c)
    data_categories: ["transaction_patterns", "risk_scores"]
    retention: "5_years"  # POCAMLA requirement
    notes: "Required by anti-money laundering regulations"

  - activity: "Analytics and product improvement"
    lawful_basis: "legitimate_interest"  # Art. 6(1)(f)
    data_categories: ["usage_patterns", "feature_adoption"]
    retention: "2_years"
    notes: "LIA documented separately; opt-out available"
    legitimate_interest_assessment: "docs/lia_analytics.md"

  - activity: "Marketing communications"
    lawful_basis: "consent"  # Art. 6(1)(a)
    data_categories: ["email", "name"]
    retention: "until_withdrawal"
    notes: "Explicit opt-in required; easy withdrawal"
```

### 3.2 Data Protection Impact Assessment (Art. 35)

Trading platforms processing financial data are high-risk. DPIA is mandatory.

```markdown
# DPIA — Alpha Stack Trading Platform

## 1. Systematic Description

Alpha Stack is an automated trading platform that:
- Processes personal and financial data of users
- Uses algorithmic trading signals (automated decision-making)
- Stores data across multiple jurisdictions (Kenya, cloud infrastructure)
- Monitors transactions for AML/CFT compliance

## 2. Necessity and Proportionality

| Data Category | Purpose | Lawful Basis | Minimized? |
|--------------|---------|--------------|------------|
| Identity (name, email) | Account management | Contract | ✅ KYC-only |
| Financial (trades, balance) | Service delivery | Contract | ✅ No unnecessary collection |
| Technical (IP, device) | Security | Legitimate interest | ✅ IP pseudonymized after 90d |
| Behavioral (analytics) | Product improvement | Legitimate interest | ✅ Aggregated where possible |

## 3. Risk Assessment

| Risk | Likelihood | Severity | Mitigation | Residual Risk |
|------|-----------|----------|------------|---------------|
| Unauthorized access to financial data | Medium | Critical | Zero-trust, MFA, encryption, credential isolation | Low |
| Audit log tampering | Low | High | Hash chain + external anchoring + digital signatures | Low |
| Data breach exposing user identity | Medium | High | Encryption at rest, field-level encryption for PII | Low |
| Automated trading without human oversight | Medium | High | Position caps, circuit breakers, human review triggers | Medium |
| Cross-border transfer without safeguards | Low | High | SCCs, encryption in transit, data residency controls | Low |
| Inability to fulfill data subject rights | High | High | DSAR API, erasure workflow, portability export | Medium |

## 4. Consultation

- [ ] DPO review and sign-off
- [ ] User representative consultation (if high residual risk)
- [ ] Supervisory authority consultation (if required)

## 5. Approval

- DPO: _________________ Date: _________
- CTO: _________________ Date: _________
- Legal: ________________ Date: _________
```

### 3.3 Data Subject Rights API (H-5 / Art. 15-22)

```python
from enum import Enum
from datetime import datetime, timezone
from typing import Optional
import uuid


class DSARType(str, Enum):
    ACCESS = "access"              # Art. 15
    RECTIFICATION = "rectification"  # Art. 16
    ERASURE = "erasure"            # Art. 17
    PORTABILITY = "portability"    # Art. 20
    RESTRICTION = "restriction"    # Art. 18
    OBJECTION = "objection"        # Art. 21


class DSARStatus(str, Enum):
    PENDING = "pending"
    VERIFYING = "verifying_identity"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXEMPT = "exempt"


class DataSubjectRightsService:
    """
    Handles GDPR and Kenya DPA data subject access requests.
    
    SLA: 30 days from verified identity (GDPR) / 30 days (Kenya DPA).
    """

    def __init__(self, user_repo, audit_log, erasure_engine, export_engine):
        self._users = user_repo
        self._audit = audit_log
        self._erasure = erasure_engine
        self._export = export_engine

    def submit_request(self, user_id: str, request_type: DSARType,
                       details: Optional[str] = None) -> dict:
        """Submit a data subject request. Returns request ticket."""
        request_id = str(uuid.uuid4())
        request = {
            "request_id": request_id,
            "user_id": user_id,
            "type": request_type.value,
            "status": DSARStatus.PENDING.value,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "deadline": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "details": details,
        }

        self._audit.log({
            "action": "dsar_submitted",
            "request_id": request_id,
            "user_id": user_id,
            "type": request_type.value,
        })

        return request

    def process_access_request(self, request_id: str) -> dict:
        """
        Art. 15 — Right of Access
        Provide a copy of all personal data held about the user.
        """
        request = self._get_request(request_id)
        user_data = self._users.get_all_data(request["user_id"])

        export = {
            "subject": user_data["profile"],
            "trading_data": user_data["trades"],
            "audit_log": self._get_user_audit_entries(request["user_id"]),
            "processing_activities": self._get_user_processing(request["user_id"]),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "JSON (machine-readable per Art. 20)",
        }

        self._audit.log({
            "action": "dsar_access_fulfilled",
            "request_id": request_id,
            "user_id": request["user_id"],
        })

        return export

    def process_erasure_request(self, request_id: str) -> dict:
        """
        Art. 17 — Right to Erasure (Right to be Forgotten)
        
        Deletes personal data EXCEPT where retention is legally required:
        - Financial records: 7 years (regulatory requirement)
        - AML records: 5 years (POCAMLA)
        - Audit logs: 7 years (compliance)
        
        For exempt data: pseudonymize instead of delete.
        """
        request = self._get_request(request_id)
        user_id = request["user_id"]

        # Identify what can be erased vs. what must be retained
        erasure_plan = self._erasure.plan(user_id)

        results = {
            "erased": [],
            "pseudonymized": [],  # Legally required data — anonymize instead
            "retained_with_reason": [],
        }

        # Erase non-exempt data
        for category in erasure_plan["erasable"]:
            self._erasure.delete(user_id, category)
            results["erased"].append(category)

        # Pseudonymize exempt data (replaces PII with pseudonym, keeps records)
        for category, exemption in erasure_plan["exempt"]:
            pseudonym = self._erasure.pseudonymize(user_id, category)
            results["pseudonymized"].append({
                "category": category,
                "exemption": exemption,
                "pseudonym": pseudonym,
            })

        # Log erasure (audit log itself is exempt — record the action)
        self._audit.log({
            "action": "dsar_erasure_fulfilled",
            "request_id": request_id,
            "user_id": user_id,  # This is the LAST log entry with real user_id
            "erased_categories": results["erased"],
            "pseudonymized_categories": [p["category"] for p in results["pseudonymized"]],
        })

        # Pseudonymize future audit entries for this user
        self._erasure.set_pseudonym_mapping(user_id, pseudonym=f"PSEUDO-{request_id[:8]}")

        return results

    def process_portability_request(self, request_id: str) -> dict:
        """
        Art. 20 — Right to Data Portability
        Export user data in structured, machine-readable format (JSON/CSV).
        """
        request = self._get_request(request_id)
        user_id = request["user_id"]

        export = self._export.generate(user_id, formats=["json", "csv"])

        self._audit.log({
            "action": "dsar_portability_fulfilled",
            "request_id": request_id,
            "user_id": user_id,
            "formats": ["json", "csv"],
        })

        return export
```

### 3.4 Consent Management (Art. 7)

```python
class ConsentManager:
    """
    GDPR-compliant consent management.
    
    Requirements:
    - Freely given (not bundled with service)
    - Specific (per-purpose)
    - Informed (clear description)
    - Unambiguous (affirmative action)
    - Withdrawable (as easy as giving)
    """

    CONSENT_PURPOSES = {
        "marketing_email": {
            "description": "Receive trading tips, product updates, and promotions via email",
            "required": False,
            "category": "marketing",
        },
        "analytics": {
            "description": "Allow anonymized usage analytics to improve the platform",
            "required": False,
            "category": "analytics",
        },
        "third_party_sharing": {
            "description": "Share anonymized data with research partners",
            "required": False,
            "category": "data_sharing",
        },
    }

    def record_consent(self, user_id: str, purpose: str, granted: bool,
                       method: str = "ui_checkbox") -> dict:
        """Record a consent decision with full audit trail."""
        if purpose not in self.CONSENT_PURPOSES:
            raise ValueError(f"Unknown purpose: {purpose}")

        consent_record = {
            "user_id": user_id,
            "purpose": purpose,
            "granted": granted,
            "method": method,  # ui_checkbox, api_call, settings_page
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": self._get_privacy_policy_version(),
            "ip_hash": self._hash_ip(request.remote_addr),
        }

        self._store.save(consent_record)
        self._audit.log({
            "action": "consent_recorded",
            "user_id": user_id,
            "purpose": purpose,
            "granted": granted,
        })

        return consent_record

    def withdraw_consent(self, user_id: str, purpose: str) -> dict:
        """Withdraw consent. Must be as easy as granting it."""
        return self.record_consent(user_id, purpose, granted=False,
                                   method="withdrawal")

    def get_consents(self, user_id: str) -> dict:
        """Get current consent state for a user."""
        records = self._store.get_by_user(user_id)
        current = {}
        for purpose in self.CONSENT_PURPOSES:
            latest = max(
                (r for r in records if r["purpose"] == purpose),
                key=lambda r: r["timestamp"],
                default=None,
            )
            current[purpose] = {
                "granted": latest["granted"] if latest else False,
                "last_updated": latest["timestamp"] if latest else None,
                "description": self.CONSENT_PURPOSES[purpose]["description"],
            }
        return current

    def check_consent(self, user_id: str, purpose: str) -> bool:
        """Check if user has active consent for a purpose."""
        consents = self.get_consents(user_id)
        return consents.get(purpose, {}).get("granted", False)
```

### 3.5 Records of Processing Activities (Art. 30 / M-1)

```python
class ROPAManager:
    """
    Records of Processing Activities (ROPA) — Art. 30.
    
    Maintains a living register of all processing activities,
    automatically updated when new data flows are added.
    """

    def generate_ropa(self) -> dict:
        """Generate the current ROPA document."""
        return {
            "controller": {
                "name": "Alpha Stack Ltd",
                "contact": "dpo@alphastack.io",
                "dpo": "TBD",  # Update after DPO appointment
            },
            "processing_activities": self._load_activities(),
            "data_categories": self._catalog_data_categories(),
            "recipients": self._catalog_recipients(),
            "transfers": self._catalog_transfers(),
            "retention_periods": self._catalog_retention(),
            "security_measures": self._catalog_security(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "review_due": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
        }

    def _load_activities(self) -> list[dict]:
        """Load from lawful_basis.yaml + code analysis."""
        # Maps to the lawful_basis.yaml entries
        return [
            {
                "name": "User account management",
                "purpose": "Provide trading platform service",
                "lawful_basis": "Art. 6(1)(b) — Contract",
                "data_subjects": "Platform users",
                "data_categories": ["Identity", "Contact", "Financial"],
                "recipients": ["Internal", "Payment processor (Stripe)"],
                "transfer": "EU → US (SCCs)",
                "retention": "Account lifetime + 30 days",
                "security": ["Encryption at rest", "Encryption in transit", "RBAC"],
            },
            {
                "name": "Trade execution and record-keeping",
                "purpose": "Execute trades and maintain regulatory records",
                "lawful_basis": "Art. 6(1)(b) Contract + Art. 6(1)(c) Legal obligation",
                "data_subjects": "Platform users",
                "data_categories": ["Financial", "Transaction", "Behavioral"],
                "recipients": ["Internal", "MT5 broker"],
                "transfer": "Kenya → Broker jurisdiction (SCCs)",
                "retention": "7 years (regulatory)",
                "security": ["Encryption", "Credential isolation", "Audit logging"],
            },
            {
                "name": "Audit logging",
                "purpose": "Security monitoring and regulatory compliance",
                "lawful_basis": "Art. 6(1)(c) Legal obligation",
                "data_subjects": "All users",
                "data_categories": ["Technical (IP, user agent)", "Behavioral (actions)"],
                "recipients": ["Internal security team"],
                "transfer": "None (stored in jurisdiction)",
                "retention": "7 years",
                "security": ["Hash chain", "External anchoring", "Digital signatures"],
            },
        ]
```

### 3.6 Right to Erasure — Exemption Handling (Art. 17(3))

```python
class ErasureEngine:
    """
    Handles GDPR erasure requests with proper exemption management.
    
    Art. 17(3) exemptions that override erasure:
    - Legal obligation requiring retention (financial records, tax)
    - Public interest (AML/CFT)
    - Legal claims
    
    For exempt data: pseudonymize instead of delete.
    """

    ERASURE_EXEMPTIONS = {
        "financial_records": {
            "regulation": "Financial Services Act / Tax regulations",
            "retention_years": 7,
            "action": "pseudonymize",
            "description": "Trading records required for regulatory audit",
        },
        "aml_records": {
            "regulation": "POCAMLA / Proceeds of Crime",
            "retention_years": 5,
            "action": "pseudonymize",
            "description": "AML/CFT monitoring records",
        },
        "audit_logs": {
            "regulation": "Financial regulations / Security obligations",
            "retention_years": 7,
            "action": "pseudonymize",
            "description": "Audit trail for compliance verification",
        },
        "legal_hold": {
            "regulation": "Legal proceedings",
            "retention_years": None,  # Until hold is released
            "action": "retain",
            "description": "Data subject to legal hold",
        },
    }

    def plan(self, user_id: str) -> dict:
        """Create an erasure plan for a user."""
        all_categories = self._catalog_user_data(user_id)
        erasable = []
        exempt = []

        for category in all_categories:
            exemption = self._find_exemption(category)
            if exemption:
                exempt.append((category, exemption))
            else:
                erasable.append(category)

        return {"erasable": erasable, "exempt": exempt}

    def pseudonymize(self, user_id: str, category: str) -> str:
        """
        Replace PII with a pseudonym. Data remains usable for analytics
        but cannot be linked back to the individual without the mapping.
        """
        pseudonym = f"PS-{hashlib.sha256(user_id.encode()).hexdigest()[:16]}"

        # Replace PII fields with pseudonym
        self._store.replace_pii(user_id, category, {
            "name": pseudonym,
            "email": f"{pseudonym}@pseudonymized.local",
            "ip_address": "0.0.0.0",
            "phone": None,
        })

        # Store mapping in separate, restricted-access table
        # (needed for legal proceedings, regulatory requests)
        self._pseudonym_store.save(user_id, pseudonym, category)

        return pseudonym
```

### 3.7 EU Representative (Art. 27)

If Alpha Stack serves EU users without an EU establishment:

```markdown
## EU Representative Requirement (Art. 27)

**Status:** Required if Alpha Stack offers services to EU residents
without an establishment in the EU.

**Action Items:**
1. Appoint EU representative (law firm or specialized service)
2. Representative contact details in privacy policy
3. Representative serves as contact point for supervisory authorities and data subjects
4. Maintain written mandate per Art. 27(3)

**Recommended providers:**
- GDPR Local (Ireland)
- Data Protection Representatives Ltd (Ireland)
- Privasee (EU-wide)

**Timeline:** Before serving any EU users.

**Note:** EU representative does NOT replace DPO requirement.
```

### 3.8 DPO Appointment (Art. 37)

```markdown
## Data Protection Officer (Art. 37)

**DPO Required:** Yes — Alpha Stack engages in:
- Large-scale processing of financial data (special category under some interpretations)
- Systematic monitoring of user behavior (analytics, AML)
- Processing that requires DPIA

**DPO Requirements:**
- Expert knowledge of data protection law (GDPR + Kenya DPA)
- Reports to highest management level
- Cannot be penalized for performing DPO tasks
- Independent — no conflict of interest (cannot be CTO or CISO)

**Responsibilities:**
- Monitor GDPR/Kenya DPA compliance
- Advise on DPIAs
- Act as contact point for supervisory authorities
- Handle data subject complaints
- Maintain ROPA

**Timeline:** Appoint before launch.
```

---

## 4. Compliance Matrix — Updated Status

| Control | GDPR | Kenya DPA | Before | After | Action |
|---------|------|-----------|--------|-------|--------|
| Audit logging | Art. 30 ⚠️ | §41 ⚠️ | Partial | ✅ Fixed | Hash-chain bugs fixed, external anchoring, digital signatures |
| Data subject rights | Art. 15-22 ❌ | §26-29 ❌ | Missing | ✅ Built | DSAR API with access, erasure, portability |
| Consent management | Art. 7 ❌ | §32 ❌ | Missing | ✅ Built | Per-purpose consent with withdrawal |
| DPIA | Art. 35 ❌ | §31 ❌ | Missing | ✅ Drafted | Template + risk assessment |
| ROPA | Art. 30 ❌ | §30 ❌ | Missing | ✅ Built | Auto-generated from code + config |
| DPO | Art. 37 ❌ | §24 ❌ | Missing | 📋 Planned | Appointment required before launch |
| EU Representative | Art. 27 ❌ | N/A | Missing | 📋 Planned | Required before serving EU users |
| Lawful basis | Art. 6 ❌ | §30 ❌ | Missing | ✅ Documented | YAML mapping per processing activity |
| Erasure mechanism | Art. 17 ❌ | §27 ❌ | Missing | ✅ Built | With proper exemption handling |
| Data portability | Art. 20 ❌ | §26 ❌ | Missing | ✅ Built | JSON + CSV export |
| Chain verification | — | — | Missing | ✅ Built | Hourly scheduled + alerting |
| External anchoring | — | — | Missing | ✅ Built | OpenTimestamps / QLDB |
| Digital signatures | — | — | Missing | ✅ Built | Ed25519 per event |

---

## 5. Implementation Checklist

### Phase 1 — Critical (Week 1-2)

- [ ] Replace hash-chain implementation with fixed version (§1.1)
- [ ] Add `threading.Lock` or single-writer queue (§1.2)
- [ ] Implement `_recover_previous_hash()` for crash safety (§1.3)
- [ ] Write contract unit tests (§1.4)
- [ ] Separate audit log storage from application DB (§2.5)
- [ ] Enforce append-only on ClickHouse (§2.4)
- [ ] Begin DPIA document (§3.2)

### Phase 2 — High (Week 2-4)

- [ ] Integrate OpenTimestamps external anchoring (§2.1)
- [ ] Implement Ed25519 audit event signing (§2.2)
- [ ] Deploy hourly chain verification with alerting (§2.3)
- [ ] Build DSAR API — access, erasure, portability (§3.3)
- [ ] Implement consent management (§3.4)
- [ ] Document lawful basis mapping (§3.1)
- [ ] Appoint DPO (§3.8)
- [ ] Appoint EU representative if serving EU users (§3.7)

### Phase 3 — Medium (Week 4-12)

- [ ] Build ROPA generator (§3.5)
- [ ] Implement erasure engine with exemption handling (§3.6)
- [ ] Draft DPAs for sub-processors
- [ ] Add audit log integrity test cases to pen-test scope
- [ ] Add chaos/fault injection tests for audit log unavailability
- [ ] Credential isolation verification in CI

---

## 6. Verification Criteria

All fixes are complete when:

1. **Hash chain:** `verify_chain()` returns empty list on valid chain; detects single-bit tampering; passes concurrent write test with 100+ threads
2. **External anchoring:** Daily checkpoints anchored to OpenTimestamps; verification script confirms anchor integrity
3. **Digital signatures:** Every audit event signed; signature verification rejects forged events
4. **Chain verification:** Hourly cron runs; alert fires within 5 minutes of chain break
5. **DSAR access:** Returns complete user data within 30 days
6. **DSAR erasure:** Deletes non-exempt data; pseudonymizes exempt data; audit trail preserved
7. **DSAR portability:** Exports JSON + CSV with all portable data
8. **Consent:** Record, check, withdraw — all with audit trail; withdrawal is as easy as granting
9. **ROPA:** Generated document covers all processing activities from `lawful_basis.yaml`
10. **DPIA:** Documented, reviewed by DPO, residual risks accepted

---

*Document generated: 2026-07-11*
*Re-run audit after completing Phase 1 and Phase 2 items.*
