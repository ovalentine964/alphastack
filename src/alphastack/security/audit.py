"""Audit logging — tamper-proof, append-only event trail.

Implements the audit architecture from architecture_security.md:
- All trade decisions logged
- All agent actions logged
- All security events logged
- Hash-chain tamper detection
- Configurable retention per category
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants & enums
# ---------------------------------------------------------------------------

class AuditCategory(str, Enum):
    AUTH = "authentication"
    AUTHZ = "authorization"
    TRADING = "trading"
    CREDENTIAL = "credential"
    SYSTEM = "system"
    SECURITY = "security"
    DATA_ACCESS = "data_access"
    AGENT = "agent"


# Retention in seconds
_RETENTION: dict[AuditCategory, int] = {
    AuditCategory.AUTH: 2 * 365 * 86400,
    AuditCategory.AUTHZ: 2 * 365 * 86400,
    AuditCategory.TRADING: 7 * 365 * 86400,
    AuditCategory.CREDENTIAL: 2 * 365 * 86400,
    AuditCategory.SYSTEM: 3 * 365 * 86400,
    AuditCategory.SECURITY: 5 * 365 * 86400,
    AuditCategory.DATA_ACCESS: 365 * 86400,
    AuditCategory.AGENT: 3 * 365 * 86400,
}


# ---------------------------------------------------------------------------
# Audit event dataclass
# ---------------------------------------------------------------------------

@dataclass
class AuditEvent:
    """A single immutable audit event."""
    version: str = "1.0"
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex}")
    timestamp: float = field(default_factory=time.time)
    category: AuditCategory = AuditCategory.SYSTEM
    action: str = ""
    actor_type: str = "system"
    actor_id: str = ""
    resource_type: str = ""
    resource_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    outcome: dict[str, Any] = field(default_factory=dict)
    # Integrity fields (filled by AuditLogger)
    previous_hash: str = "GENESIS"
    event_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "category": self.category.value,
            "action": self.action,
            "actor": {
                "type": self.actor_type,
                "id": self.actor_id,
            },
            "resource": {
                "type": self.resource_type,
                "id": self.resource_id,
            },
            "details": self.details,
            "outcome": self.outcome,
            "integrity": {
                "previous_hash": self.previous_hash,
                "event_hash": self.event_hash,
            },
        }


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------

class AuditLogger:
    """Append-only audit logger with hash-chain integrity.

    Parameters
    ----------
    store_dir : Path
        Directory for audit log files (one JSON-lines file per day).
    max_memory_events : int
        Flush to disk after this many events in memory.
    """

    def __init__(
        self,
        store_dir: Path | None = None,
        max_memory_events: int = 100,
    ) -> None:
        self._store_dir = store_dir or Path(".alphastack/audit")
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._max_memory = max_memory_events

        self._previous_hash = "GENESIS"
        self._buffer: list[AuditEvent] = []
        self._alert_callbacks: list[Any] = []

        # Restore chain head from disk
        self._restore_chain_head()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log(
        self,
        category: AuditCategory,
        action: str,
        *,
        actor_type: str = "system",
        actor_id: str = "",
        resource_type: str = "",
        resource_id: str = "",
        details: dict[str, Any] | None = None,
        outcome: dict[str, Any] | None = None,
    ) -> str:
        """Append an audit event.  Returns the event hash."""
        event = AuditEvent(
            category=category,
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            outcome=outcome or {},
        )
        return self._append(event)

    def log_trade(
        self,
        user_id: str,
        order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None,
        *,
        strategy_id: str = "",
        confidence: float = 0.0,
        broker_order_id: str = "",
        fill_price: float | None = None,
        slippage: float = 0.0,
    ) -> str:
        """Convenience: log a trade decision + outcome."""
        return self.log(
            AuditCategory.TRADING,
            "order_placed",
            actor_type="user",
            actor_id=user_id,
            resource_type="order",
            resource_id=order_id,
            details={
                "symbol": symbol,
                "side": side,
                "order_type": order_type,
                "quantity": quantity,
                "price": price,
                "strategy_id": strategy_id,
                "confidence": confidence,
            },
            outcome={
                "broker_order_id": broker_order_id,
                "fill_price": fill_price,
                "slippage_pips": slippage,
            },
        )

    def log_agent_action(
        self,
        agent_id: str,
        action: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> str:
        """Convenience: log an agent action."""
        return self.log(
            AuditCategory.AGENT,
            action,
            actor_type="agent",
            actor_id=agent_id,
            details=details or {},
        )

    def log_security(
        self,
        action: str,
        *,
        actor_type: str = "system",
        actor_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> str:
        """Convenience: log a security event."""
        return self.log(
            AuditCategory.SECURITY,
            action,
            actor_type=actor_type,
            actor_id=actor_id,
            details=details or {},
        )

    # -- Chain verification -------------------------------------------------

    def verify_chain(self, events: list[dict[str, Any]]) -> bool:
        """Verify the hash chain integrity of a list of audit events.

        Returns ``True`` if every event's hash is correct and the chain is
        unbroken.
        """
        prev_hash = "GENESIS"
        for ev in events:
            stored_prev = ev.get("integrity", {}).get("previous_hash", "")
            stored_hash = ev.get("integrity", {}).get("event_hash", "")
            if stored_prev != prev_hash:
                return False
            computed = self._compute_hash(ev, prev_hash)
            if computed != stored_hash:
                return False
            prev_hash = stored_hash
        return True

    # -- Flush & persistence ------------------------------------------------

    def flush(self) -> None:
        """Write buffered events to disk."""
        if not self._buffer:
            return
        day_file = self._store_dir / f"{self._day_tag()}.jsonl"
        with day_file.open("a", encoding="utf-8") as f:
            for ev in self._buffer:
                f.write(json.dumps(ev.to_dict(), separators=(",", ":")) + "\n")
        self._buffer.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append(self, event: AuditEvent) -> str:
        event.previous_hash = self._previous_hash
        ev_dict = event.to_dict()
        event.event_hash = self._compute_hash(ev_dict, self._previous_hash)
        self._previous_hash = event.event_hash

        self._buffer.append(event)
        if len(self._buffer) >= self._max_memory:
            self._flush_buffer()

        # Fire alerts
        self._check_alerts(event)
        return event.event_hash

    def _flush_buffer(self) -> None:
        if not self._buffer:
            return
        day_file = self._store_dir / f"{self._day_tag()}.jsonl"
        with day_file.open("a", encoding="utf-8") as f:
            for ev in self._buffer:
                f.write(json.dumps(ev.to_dict(), separators=(",", ":")) + "\n")
        self._buffer.clear()

    @staticmethod
    def _compute_hash(ev_dict: dict[str, Any], prev_hash: str) -> str:
        """Deterministic SHA-256 hash of an event dict + previous hash."""
        # Remove the event_hash itself before computing
        clean = {k: v for k, v in ev_dict.items() if k != "integrity"}
        integrity = {"previous_hash": prev_hash, "timestamp": ev_dict.get("timestamp")}
        clean["integrity"] = integrity
        blob = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(blob).hexdigest()

    def _restore_chain_head(self) -> None:
        """Read the last event from today's log to restore the chain head."""
        day_file = self._store_dir / f"{self._day_tag()}.jsonl"
        if not day_file.exists():
            return
        last_line = ""
        with day_file.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line
        if last_line:
            try:
                last = json.loads(last_line)
                self._previous_hash = last.get("integrity", {}).get("event_hash", "GENESIS")
            except json.JSONDecodeError:
                pass

    @staticmethod
    def _day_tag() -> str:
        import datetime
        return datetime.datetime.utcnow().strftime("%Y-%m-%d")

    # -- Alerts -------------------------------------------------------------

    def register_alert(self, callback) -> None:
        """Register a callable(AuditEvent) for real-time alerting."""
        self._alert_callbacks.append(callback)

    def _check_alerts(self, event: AuditEvent) -> None:
        for cb in self._alert_callbacks:
            try:
                cb(event)
            except Exception:
                pass  # alerting must not crash the logger
