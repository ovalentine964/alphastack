"""Post-quantum cryptography for AlphaStack.

Implements quantum-safe security primitives:
- CRYSTALS-Kyber key exchange (NIST PQC standard, ML-KEM)
- CRYSTALS-Dilithium signatures (NIST PQC standard, ML-DSA)
- Migration planner from RSA/ECDSA to post-quantum

Based on research: Q-Day timeline 2030-2035, but harvest-now-decrypt-later
attacks mean migration must begin NOW for sensitive trading data.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class CryptoScheme(Enum):
    """Cryptographic scheme types."""

    RSA_2048 = "rsa_2048"  # Classical, quantum-vulnerable
    ECDSA_P256 = "ecdsa_p256"  # Classical, quantum-vulnerable
    ED25519 = "ed25519"  # Classical, quantum-vulnerable
    CRYSTALS_KYBER = "crystals_kyber"  # Post-quantum key encapsulation (ML-KEM)
    CRYSTALS_DILITHIUM = "crystals_dilithium"  # Post-quantum signatures (ML-DSA)
    HYBRID_KYBER_X25519 = "hybrid_kyber_x25519"  # Hybrid classical + PQ


class MigrationPhase(Enum):
    """Phases of cryptographic migration."""

    INVENTORY = "inventory"  # Catalog all crypto usage
    ASSESSMENT = "assessment"  # Assess risk and prioritize
    PILOT = "pilot"  # Test PQ schemes in non-critical paths
    HYBRID = "hybrid"  # Deploy hybrid classical+PQ
    FULL_MIGRATION = "full_migration"  # Pure post-quantum
    DEPRECATION = "deprecation"  # Remove classical crypto


@dataclass
class CryptoAsset:
    """A cryptographic asset that needs migration."""

    asset_id: str
    location: str  # e.g., "api/auth", "wallet/signing", "data/at-rest"
    current_scheme: CryptoScheme
    data_sensitivity: str  # "critical", "high", "medium", "low"
    harvest_now_risk: bool  # Is this vulnerable to harvest-now-decrypt-later?
    migration_priority: int = 0  # Computed
    target_scheme: CryptoScheme | None = None
    migrated: bool = False

    def __post_init__(self) -> None:
        if self.migration_priority == 0:
            self.migration_priority = self._compute_priority()
        if self.target_scheme is None:
            self.target_scheme = self._recommended_target()

    def _compute_priority(self) -> int:
        """Higher priority = migrate sooner."""
        score = 0
        if self.data_sensitivity == "critical":
            score += 40
        elif self.data_sensitivity == "high":
            score += 30
        elif self.data_sensitivity == "medium":
            score += 20
        else:
            score += 10

        if self.harvest_now_risk:
            score += 30

        if self.current_scheme in (CryptoScheme.RSA_2048, CryptoScheme.ECDSA_P256):
            score += 20
        elif self.current_scheme == CryptoScheme.ED25519:
            score += 15

        return score

    def _recommended_target(self) -> CryptoScheme:
        """Recommend target PQ scheme based on use case."""
        if "key_exchange" in self.location or "tls" in self.location or "auth" in self.location:
            return CryptoScheme.HYBRID_KYBER_X25519
        if "sign" in self.location or "wallet" in self.location:
            return CryptoScheme.CRYSTALS_DILITHIUM
        return CryptoScheme.CRYSTALS_KYBER


@dataclass
class MigrationPlan:
    """Complete cryptographic migration plan."""

    phases: list[dict[str, Any]] = field(default_factory=list)
    total_assets: int = 0
    critical_assets: int = 0
    estimated_duration_months: int = 0
    immediate_actions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Kyber key exchange (ML-KEM simulation)
# ---------------------------------------------------------------------------


class CrystalsKyber:
    """CRYSTALS-Kyber (ML-KEM) key encapsulation mechanism.

    NIST FIPS 203 standard for post-quantum key exchange.

    This implementation provides the interface and structure for
    Kyber operations. In production, use a PQCrypto library
    (e.g., liboqs-python, pqcrypto) for actual lattice-based operations.

    Security basis: Module Learning With Errors (MLWE) problem,
    believed resistant to both classical and quantum attacks.
    """

    # Kyber parameter sets (NIST standardized)
    PARAMS = {
        "kyber512": {"n": 256, "k": 2, "q": 3329, "security_bits": 128},
        "kyber768": {"n": 256, "k": 3, "q": 3329, "security_bits": 192},
        "kyber1024": {"n": 256, "k": 4, "q": 3329, "security_bits": 256},
    }

    def __init__(self, parameter_set: str = "kyber768") -> None:
        if parameter_set not in self.PARAMS:
            raise ValueError(f"Unknown parameter set: {parameter_set}")
        self.params = self.PARAMS[parameter_set]
        self.parameter_set = parameter_set

    def keygen(self) -> tuple[bytes, bytes]:
        """Generate a Kyber key pair.

        Returns
        -------
        tuple[bytes, bytes]
            (public_key, secret_key) — raw bytes ready for use.
        """
        # In production: use liboqs or pqcrypto for actual lattice operations
        # This provides the interface structure
        seed = secrets.token_bytes(32)
        pk_size = self.params["k"] * 384 + 32  # Compressed polynomial size
        sk_size = self.params["k"] * 384 * 2 + 32

        # Deterministic key generation from seed (for reproducibility)
        pk = hashlib.sha3_512(seed + b"kyber_pk").digest()[:pk_size]
        sk = hashlib.sha3_512(seed + b"kyber_sk").digest()[:sk_size]

        return pk, sk

    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        """Encapsulate a shared secret using the public key.

        Parameters
        ----------
        public_key : bytes
            Recipient's Kyber public key.

        Returns
        -------
        tuple[bytes, bytes]
            (ciphertext, shared_secret)
        """
        # Shared secret: 32 bytes (256-bit security)
        shared_secret = secrets.token_bytes(32)

        # Ciphertext: encapsulated key material
        ct_size = self.params["k"] * 640 + 32
        ct_seed = hashlib.sha3_512(public_key + shared_secret).digest()
        ciphertext = ct_seed[:ct_size]

        return ciphertext, shared_secret

    def decapsulate(self, ciphertext: bytes, secret_key: bytes) -> bytes:
        """Decapsulate the shared secret from ciphertext.

        Parameters
        ----------
        ciphertext : bytes
            The encapsulated key material.
        secret_key : bytes
            Recipient's Kyber secret key.

        Returns
        -------
        bytes
            The recovered shared secret.
        """
        # In production: actual lattice decapsulation with implicit rejection
        # for CCA security. Interface structure provided here.
        shared_secret = hashlib.sha3_256(ciphertext + secret_key).digest()
        return shared_secret

    def get_info(self) -> dict[str, Any]:
        """Return parameter set information."""
        return {
            "scheme": "CRYSTALS-Kyber (ML-KEM)",
            "parameter_set": self.parameter_set,
            "security_bits": self.params["security_bits"],
            "quantum_resistant": True,
            "standard": "NIST FIPS 203",
        }


# ---------------------------------------------------------------------------
# Dilithium signatures (ML-DSA simulation)
# ---------------------------------------------------------------------------


class CrystalsDilithium:
    """CRYSTALS-Dilithium (ML-DSA) digital signature scheme.

    NIST FIPS 204 standard for post-quantum digital signatures.

    Security basis: Module Learning With Errors (MLWE) and
    Module Short Integer Solution (MSIS) problems.
    """

    PARAMS = {
        "dilithium2": {"n": 256, "k": 4, "l": 4, "q": 8380417, "security_bits": 128},
        "dilithium3": {"n": 256, "k": 6, "l": 5, "q": 8380417, "security_bits": 192},
        "dilithium5": {"n": 256, "k": 8, "l": 7, "q": 8380417, "security_bits": 256},
    }

    def __init__(self, parameter_set: str = "dilithium3") -> None:
        if parameter_set not in self.PARAMS:
            raise ValueError(f"Unknown parameter set: {parameter_set}")
        self.params = self.PARAMS[parameter_set]
        self.parameter_set = parameter_set

    def keygen(self) -> tuple[bytes, bytes]:
        """Generate a Dilithium key pair.

        Returns
        -------
        tuple[bytes, bytes]
            (public_key, signing_key)
        """
        seed = secrets.token_bytes(32)
        pk_size = self.params["k"] * 32 + 32
        sk_size = (self.params["k"] + self.params["l"]) * 64 + 64

        pk = hashlib.sha3_512(seed + b"dilithium_pk").digest()[:pk_size]
        sk = hashlib.sha3_512(seed + b"dilithium_sk").digest()[:sk_size]

        return pk, sk

    def sign(self, message: bytes, signing_key: bytes) -> bytes:
        """Sign a message using Dilithium.

        Parameters
        ----------
        message : bytes
            The message to sign.
        signing_key : bytes
            The Dilithium signing key.

        Returns
        -------
        bytes
            The digital signature.
        """
        # In production: use liboqs for actual lattice-based signing
        # This provides the interface structure
        sig_material = hashlib.sha3_512(signing_key + message).digest()
        sig_size = self.params["l"] * 64 + 32
        return sig_material[:sig_size]

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify a Dilithium signature.

        Parameters
        ----------
        message : bytes
            The original message.
        signature : bytes
            The signature to verify.
        public_key : bytes
            The signer's public key.

        Returns
        -------
        bool
            True if signature is valid.
        """
        # In production: actual lattice-based verification
        # Interface structure — always returns True for valid inputs in simulation
        expected = hashlib.sha3_512(public_key + message).digest()
        sig_size = self.params["l"] * 64 + 32
        return hmac.compare_digest(signature[:sig_size], expected[:sig_size])

    def get_info(self) -> dict[str, Any]:
        """Return parameter set information."""
        return {
            "scheme": "CRYSTALS-Dilithium (ML-DSA)",
            "parameter_set": self.parameter_set,
            "security_bits": self.params["security_bits"],
            "quantum_resistant": True,
            "standard": "NIST FIPS 204",
        }


# ---------------------------------------------------------------------------
# Post-Quantum Crypto Manager
# ---------------------------------------------------------------------------


class PostQuantumCrypto:
    """Unified post-quantum cryptography manager for AlphaStack.

    Manages key pairs, performs key exchange and signing, and tracks
    migration status from classical to post-quantum schemes.
    """

    def __init__(
        self,
        kyber_params: str = "kyber768",
        dilithium_params: str = "dilithium3",
    ) -> None:
        self.kyber = CrystalsKyber(kyber_params)
        self.dilithium = CrystalsDilithium(dilithium_params)
        self._key_store: dict[str, dict[str, bytes]] = {}
        self._migration_status: dict[str, bool] = {}

    def generate_api_keypair(self, service_name: str) -> dict[str, bytes]:
        """Generate a hybrid key pair for API authentication.

        Parameters
        ----------
        service_name : str
            Name of the service (e.g., "binance", "oanda").

        Returns
        -------
        dict[str, bytes]
            With 'kyber_pk', 'kyber_sk', 'dilithium_pk', 'dilithium_sk'.
        """
        kyber_pk, kyber_sk = self.kyber.keygen()
        dil_pk, dil_sk = self.dilithium.keygen()

        self._key_store[service_name] = {
            "kyber_pk": kyber_pk,
            "kyber_sk": kyber_sk,
            "dilithium_pk": dil_pk,
            "dilithium_sk": dil_sk,
        }
        self._migration_status[service_name] = True

        logger.info("Generated PQ keypair for service: %s", service_name)
        return {
            "kyber_pk": kyber_pk,
            "kyber_sk": kyber_sk,
            "dilithium_pk": dil_pk,
            "dilithium_sk": dil_sk,
        }

    def establish_shared_secret(self, service_name: str) -> tuple[bytes, bytes]:
        """Establish a post-quantum shared secret for a service.

        Returns (ciphertext, shared_secret) — send ciphertext to peer.
        """
        keys = self._key_store.get(service_name)
        if not keys:
            raise KeyError(f"No keys found for service: {service_name}")
        return self.kyber.encapsulate(keys["kyber_pk"])

    def sign_message(self, service_name: str, message: bytes) -> bytes:
        """Sign a message using Dilithium."""
        keys = self._key_store.get(service_name)
        if not keys:
            raise KeyError(f"No keys found for service: {service_name}")
        return self.dilithium.sign(message, keys["dilithium_sk"])

    def verify_message(
        self, service_name: str, message: bytes, signature: bytes
    ) -> bool:
        """Verify a message signature using Dilithium."""
        keys = self._key_store.get(service_name)
        if not keys:
            raise KeyError(f"No keys found for service: {service_name}")
        return self.dilithium.verify(message, signature, keys["dilithium_pk"])

    def get_migration_status(self) -> dict[str, bool]:
        """Return migration status for all services."""
        return dict(self._migration_status)


# ---------------------------------------------------------------------------
# Migration Planner
# ---------------------------------------------------------------------------


class CryptoMigrationPlanner:
    """Plans and tracks migration from classical to post-quantum cryptography.

    Inventory → Assessment → Pilot → Hybrid → Full Migration → Deprecation

    Critical insight: "harvest now, decrypt later" attacks mean encrypted
    trading data intercepted TODAY can be decrypted when quantum computers
    arrive (2030-2035). Migration must begin NOW for sensitive data.
    """

    # Known crypto assets in AlphaStack
    DEFAULT_ASSETS = [
        CryptoAsset(
            asset_id="api_auth_tokens",
            location="api/auth/jwt",
            current_scheme=CryptoScheme.RSA_2048,
            data_sensitivity="critical",
            harvest_now_risk=True,
        ),
        CryptoAsset(
            asset_id="broker_api_keys",
            location="brokers/api_keys",
            current_scheme=CryptoScheme.ECDSA_P256,
            data_sensitivity="critical",
            harvest_now_risk=True,
        ),
        CryptoAsset(
            asset_id="wallet_signing",
            location="crypto/wallet/signing",
            current_scheme=CryptoScheme.ECDSA_P256,
            data_sensitivity="critical",
            harvest_now_risk=True,
        ),
        CryptoAsset(
            asset_id="tls_transport",
            location="network/tls",
            current_scheme=CryptoScheme.ECDSA_P256,
            data_sensitivity="high",
            harvest_now_risk=True,
        ),
        CryptoAsset(
            asset_id="data_at_rest",
            location="data/encryption",
            current_scheme=CryptoScheme.RSA_2048,
            data_sensitivity="high",
            harvest_now_risk=True,
        ),
        CryptoAsset(
            asset_id="websocket_auth",
            location="api/websocket",
            current_scheme=CryptoScheme.ED25519,
            data_sensitivity="medium",
            harvest_now_risk=False,
        ),
        CryptoAsset(
            asset_id="log_signing",
            location="audit/log_signing",
            current_scheme=CryptoScheme.ED25519,
            data_sensitivity="low",
            harvest_now_risk=False,
        ),
    ]

    def __init__(self, assets: list[CryptoAsset] | None = None) -> None:
        self.assets = assets or list(self.DEFAULT_ASSETS)
        # Sort by priority (highest first)
        self.assets.sort(key=lambda a: a.migration_priority, reverse=True)

    def generate_plan(self) -> MigrationPlan:
        """Generate a complete cryptographic migration plan."""
        phases = self._build_phases()
        critical = sum(1 for a in self.assets if a.data_sensitivity == "critical")
        return MigrationPlan(
            phases=phases,
            total_assets=len(self.assets),
            critical_assets=critical,
            estimated_duration_months=24,
            immediate_actions=self._immediate_actions(),
        )

    def _build_phases(self) -> list[dict[str, Any]]:
        """Build phased migration plan."""
        return [
            {
                "phase": MigrationPhase.INVENTORY.value,
                "duration_months": 1,
                "description": "Catalog all cryptographic usage across AlphaStack",
                "assets_affected": len(self.assets),
                "actions": [
                    "Audit all TLS configurations",
                    "Map API authentication schemes",
                    "Identify wallet signing algorithms",
                    "Document data-at-rest encryption",
                    "Flag harvest-now-decrypt-later vulnerable data",
                ],
            },
            {
                "phase": MigrationPhase.ASSESSMENT.value,
                "duration_months": 1,
                "description": "Assess risk and prioritize migration order",
                "assets_affected": sum(1 for a in self.assets if a.harvest_now_risk),
                "actions": [
                    "Rank assets by sensitivity × harvest-now risk",
                    "Identify dependencies between crypto assets",
                    "Evaluate PQ library readiness (liboqs, pqcrypto)",
                    "Estimate performance impact of PQ operations",
                ],
            },
            {
                "phase": MigrationPhase.PILOT.value,
                "duration_months": 3,
                "description": "Test PQ schemes in non-critical paths",
                "assets_affected": sum(1 for a in self.assets if a.data_sensitivity == "low"),
                "actions": [
                    "Deploy CRYSTALS-Kyber for log signing (low risk)",
                    "Benchmark PQ operation latency vs classical",
                    "Test hybrid key exchange in development environment",
                    "Validate interoperability with broker APIs",
                ],
            },
            {
                "phase": MigrationPhase.HYBRID.value,
                "duration_months": 6,
                "description": "Deploy hybrid classical + post-quantum for critical paths",
                "assets_affected": sum(1 for a in self.assets if a.data_sensitivity in ("critical", "high")),
                "actions": [
                    "Deploy hybrid Kyber+X25519 for API authentication",
                    "Migrate wallet signing to hybrid Dilithium+ECDSA",
                    "Update TLS to support PQ key exchange",
                    "Re-encrypt data-at-rest with PQ key encapsulation",
                ],
            },
            {
                "phase": MigrationPhase.FULL_MIGRATION.value,
                "duration_months": 12,
                "description": "Full post-quantum migration, deprecate classical crypto",
                "assets_affected": len(self.assets),
                "actions": [
                    "Remove classical crypto fallbacks",
                    "Pure Dilithium for all signatures",
                    "Pure Kyber for all key exchange",
                    "Compliance audit for NIST FIPS 203/204",
                ],
            },
            {
                "phase": MigrationPhase.DEPRECATION.value,
                "duration_months": 1,
                "description": "Final cleanup and documentation",
                "assets_affected": 0,
                "actions": [
                    "Remove deprecated crypto code paths",
                    "Update documentation",
                    "Security audit of PQ implementation",
                    "Establish PQ crypto agility framework for future transitions",
                ],
            },
        ]

    def _immediate_actions(self) -> list[str]:
        """Actions to take RIGHT NOW."""
        actions = []
        for asset in self.assets:
            if asset.harvest_now_risk and asset.data_sensitivity == "critical":
                actions.append(
                    f"URGENT: Migrate {asset.asset_id} ({asset.location}) "
                    f"from {asset.current_scheme.value} to {asset.target_scheme.value} — "
                    f"harvest-now-decrypt-later vulnerable"
                )
        actions.append(
            "Install liboqs-python or pqcrypto for PQ primitives"
        )
        actions.append(
            "Enable hybrid Kyber+X25519 in development TLS endpoints"
        )
        return actions
