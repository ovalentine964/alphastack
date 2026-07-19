"""AlphaStack Security Module.

Provides encryption, authentication, credential management, audit logging,
compliance, input validation, order validation, circuit breakers, kill switch,
security middleware, and quantum-resistant cryptography.
"""

from __future__ import annotations

from alphastack.security.auth import (
    AuthManager,
    JWTManager,
    RateLimiter,
    SessionManager,
    TOTPManager,
    hash_password,
    verify_password,
)
from alphastack.security.audit import AuditLogger
from alphastack.security.compliance import ComplianceManager
from alphastack.security.credentials import CredentialVault
from alphastack.security.encryption import EncryptionService
from alphastack.security.middleware import (
    IPAllowlistMiddleware,
    RequestSigningMiddleware,
    SecurityAuditMiddleware,
)
from alphastack.security.quantum_ready import QuantumReadySecurity
from alphastack.security.validation import (
    CircuitBreaker,
    KillSwitch,
    OrderValidationPipeline,
    PositionLimits,
    ValidationResult,
)
from alphastack.security.validators import InputValidator

__all__ = [
    "AuthManager",
    "AuditLogger",
    "CircuitBreaker",
    "ComplianceManager",
    "CredentialVault",
    "EncryptionService",
    "InputValidator",
    "IPAllowlistMiddleware",
    "JWTManager",
    "KillSwitch",
    "OrderValidationPipeline",
    "PositionLimits",
    "QuantumReadySecurity",
    "RateLimiter",
    "RequestSigningMiddleware",
    "SecurityAuditMiddleware",
    "SessionManager",
    "TOTPManager",
    "ValidationResult",
    "hash_password",
    "verify_password",
]
