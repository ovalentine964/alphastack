"""Broker Setup Wizard – one function to connect any broker.

Auto-detects broker type from credentials, tests the connection,
saves credentials encrypted, and returns a connected broker instance.

Usage::

    from alphastack.brokers.setup import BrokerSetup

    wizard = BrokerSetup()

    # FBS – just login + password
    broker = await wizard.add_broker("fbs", {
        "login": 12345678,
        "password": "your-password",
    })

    # Binance – API key + secret
    broker = await wizard.add_broker("binance", {
        "api_key": "your-key",
        "api_secret": "your-secret",
    })

    # OANDA – account ID + token
    broker = await wizard.add_broker("oanda", {
        "account_id": "xxx-xxx-xxxxxxx-xxx",
        "api_token": "your-token",
    })
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

from alphastack.brokers.base import BrokerConnector, ConnectionState
from alphastack.brokers.registry import BrokerRegistry

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Broker type detection
# ---------------------------------------------------------------------------

class BrokerType(str, Enum):
    """Detected broker category."""
    FBS = "fbs"
    FXPESA = "fxpesa"
    BINANCE = "binance"
    MEXC = "mexc"
    OANDA = "oanda"
    MT5_GENERIC = "mt5_generic"
    CCXT_GENERIC = "ccxt_generic"
    UNKNOWN = "unknown"


# Credential patterns for auto-detection
_BROKER_PATTERNS: dict[BrokerType, dict[str, Any]] = {
    BrokerType.FBS: {
        "required": ["login", "password"],
        "server_keywords": ["FBS", "fbs"],
        "description": "FBS (African forex broker via MT5)",
    },
    BrokerType.FXPESA: {
        "required": ["login", "password"],
        "server_keywords": ["FXPesa", "fxpesa"],
        "description": "FXPesa (Kenya forex broker via MT5 + M-Pesa)",
    },
    BrokerType.BINANCE: {
        "required": ["api_key", "api_secret"],
        "optional": ["passphrase"],
        "description": "Binance (global crypto exchange)",
    },
    BrokerType.MEXC: {
        "required": ["api_key", "api_secret"],
        "description": "MEXC (crypto exchange)",
    },
    BrokerType.OANDA: {
        "required": ["account_id", "api_token"],
        "description": "OANDA (global forex broker)",
    },
}


def detect_broker_type(
    broker_name: str,
    credentials: dict[str, Any],
) -> BrokerType:
    """Auto-detect broker type from name and credential shape.

    Detection priority:
    1. Explicit name match (e.g. "fbs", "binance", "oanda")
    2. Server keyword match (e.g. server contains "FBS")
    3. Credential shape (login+password → MT5, api_key+secret → crypto)

    Parameters
    ----------
    broker_name : str
        User-provided broker name or alias.
    credentials : dict
        Credential key-value pairs.

    Returns
    -------
    BrokerType
        Detected broker type.
    """
    name_lower = broker_name.lower().strip()

    # 1. Explicit name match
    _name_aliases: dict[str, BrokerType] = {
        "fbs": BrokerType.FBS,
        "fxpesa": BrokerType.FXPESA,
        "fx-pesa": BrokerType.FXPESA,
        "binance": BrokerType.BINANCE,
        "mexc": BrokerType.MEXC,
        "oanda": BrokerType.OANDA,
        "mt5": BrokerType.MT5_GENERIC,
    }
    if name_lower in _name_aliases:
        return _name_aliases[name_lower]

    # 2. Server keyword match
    server = str(credentials.get("server", "")).lower()
    for btype, pattern in _BROKER_PATTERNS.items():
        for keyword in pattern.get("server_keywords", []):
            if keyword.lower() in server:
                return btype

    # 3. Credential shape detection
    cred_keys = set(credentials.keys())

    # MT5-style: has login + password
    if "login" in cred_keys and "password" in cred_keys:
        return BrokerType.MT5_GENERIC

    # Crypto-style: has api_key + api_secret
    if "api_key" in cred_keys and "api_secret" in cred_keys:
        return BrokerType.CCXT_GENERIC

    # OANDA-style: has account_id + api_token
    if "account_id" in cred_keys and "api_token" in cred_keys:
        return BrokerType.OANDA

    return BrokerType.UNKNOWN


# ---------------------------------------------------------------------------
# Broker Setup Wizard
# ---------------------------------------------------------------------------

class BrokerSetup:
    """One-function broker connection wizard.

    Auto-detects broker type, creates the connector, tests the connection,
    saves credentials encrypted, and registers in the global registry.

    Usage::

        wizard = BrokerSetup()
        broker = await wizard.add_broker("fbs", {
            "login": 12345678,
            "password": "your-password",
        })
    """

    def __init__(
        self,
        registry: BrokerRegistry | None = None,
        credential_vault: Any | None = None,
    ) -> None:
        self._registry = registry
        self._vault = credential_vault
        self._connections: dict[str, BrokerConnector] = {}

    def _get_registry(self) -> BrokerRegistry:
        """Get or create the broker registry."""
        if self._registry is None:
            from alphastack.api.rest.deps import get_broker_registry
            self._registry = get_broker_registry()
        return self._registry

    def _get_vault(self) -> Any | None:
        """Get the credential vault if available."""
        if self._vault is None:
            try:
                from alphastack.security.encryption import EncryptionService
                from alphastack.security.credentials import CredentialVault
                encryption = EncryptionService()
                self._vault = CredentialVault(encryption)
            except Exception as exc:
                logger.warning("credential_vault_unavailable", error=str(exc))
        return self._vault

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def add_broker(
        self,
        name: str,
        credentials: dict[str, Any],
        *,
        test_connection: bool = True,
        save_credentials: bool = True,
    ) -> BrokerConnector:
        """Add and connect a broker with just a name and credentials.

        This is the main entry point. Users call this with a broker name
        and their credentials – everything else is auto-configured.

        Parameters
        ----------
        name : str
            Broker name or alias (e.g. "fbs", "binance", "oanda").
        credentials : dict
            Broker credentials. Keys vary by broker type:
            - FBS/FXPesa: login, password, [server], [use_demo]
            - Binance/MEXC: api_key, api_secret
            - OANDA: account_id, api_token
        test_connection : bool
            Test the connection before returning (default True).
        save_credentials : bool
            Save credentials encrypted (default True).

        Returns
        -------
        BrokerConnector
            Connected broker instance.

        Raises
        ------
        ValueError
            If broker type cannot be detected or credentials are invalid.
        ConnectionError
            If test_connection is True and the connection fails.
        """
        # 1. Detect broker type
        broker_type = detect_broker_type(name, credentials)
        if broker_type == BrokerType.UNKNOWN:
            raise ValueError(
                f"Cannot detect broker type for '{name}'. "
                f"Provide: login+password (MT5), api_key+secret (crypto), "
                f"or account_id+api_token (OANDA)."
            )

        logger.info(
            "broker_setup_start",
            name=name,
            detected_type=broker_type.value,
        )

        # 2. Create connector
        connector = self._create_connector(broker_type, credentials)

        # 3. Test connection
        if test_connection:
            await self._test_connection(connector)

        # 4. Save credentials
        if save_credentials:
            await self._save_credentials(name, broker_type, credentials)

        # 5. Register in global registry
        registry = self._get_registry()
        registry.register(name, connector)

        # Track locally
        self._connections[name] = connector

        logger.info(
            "broker_setup_complete",
            name=name,
            broker_type=broker_type.value,
            state=connector.state.value,
        )

        return connector

    async def remove_broker(self, name: str) -> None:
        """Disconnect and remove a broker.

        Parameters
        ----------
        name : str
            Broker name to remove.
        """
        registry = self._get_registry()
        connector = registry.get(name)

        if connector and connector.is_connected:
            await connector.disconnect()

        registry.unregister(name)
        self._connections.pop(name, None)

        # Remove saved credentials
        vault = self._get_vault()
        if vault:
            try:
                vault.delete(name, "login")
                vault.delete(name, "api_key")
                vault.delete(name, "account_id")
            except Exception:
                pass

        logger.info("broker_removed", name=name)

    async def test_broker(self, name: str) -> dict[str, Any]:
        """Test a broker connection and return status.

        Parameters
        ----------
        name : str
            Broker name to test.

        Returns
        -------
        dict
            Test results with status, latency, and error details.
        """
        registry = self._get_registry()
        connector = registry.get(name)
        if connector is None:
            return {"status": "not_found", "error": f"Broker '{name}' not registered"}

        import time
        start = time.monotonic()

        try:
            if not connector.is_connected:
                await connector.connect()

            # Try to get balance as a connectivity test
            balance = await connector.get_balance()
            latency_ms = (time.monotonic() - start) * 1000

            return {
                "status": "connected",
                "broker": name,
                "state": connector.state.value,
                "latency_ms": round(latency_ms, 1),
                "balance": {
                    "total": balance.total,
                    "currency": balance.currency,
                    "equity": balance.equity,
                },
            }
        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000
            return {
                "status": "error",
                "broker": name,
                "state": connector.state.value,
                "latency_ms": round(latency_ms, 1),
                "error": str(exc),
            }

    def list_brokers(self) -> list[dict[str, Any]]:
        """List all registered brokers with their status.

        Returns
        -------
        list[dict]
            List of broker info dicts.
        """
        registry = self._get_registry()
        result = []
        for name in registry.names:
            connector = registry.get(name)
            if connector:
                result.append({
                    "name": name,
                    "state": connector.state.value,
                    "is_connected": connector.is_connected,
                    "broker_type": self._infer_type(connector),
                })
        return result

    # ------------------------------------------------------------------
    # Connector factory
    # ------------------------------------------------------------------

    def _create_connector(
        self,
        broker_type: BrokerType,
        credentials: dict[str, Any],
    ) -> BrokerConnector:
        """Create the appropriate connector for the detected broker type."""
        if broker_type == BrokerType.FBS:
            from alphastack.brokers.fbs import FBSConnector
            return FBSConnector.from_credentials(credentials)

        elif broker_type == BrokerType.FXPESA:
            from alphastack.brokers.fxpesa import FXPesaConnector, FXPesaAccountType
            return FXPesaConnector(
                login=int(credentials.get("login", 0)),
                password=credentials.get("password", ""),
                server=credentials.get("server"),
                account_type=FXPesaAccountType(
                    credentials.get("account_type", "cent")
                ),
                use_demo=credentials.get("use_demo", True),
            )

        elif broker_type in (BrokerType.BINANCE, BrokerType.MEXC, BrokerType.CCXT_GENERIC):
            from alphastack.brokers.ccxt_connector import CCXTConnector
            exchange = "binance" if broker_type == BrokerType.BINANCE else "mexc"
            return CCXTConnector(
                exchange_id=exchange,
                api_key=credentials.get("api_key", ""),
                secret=credentials.get("api_secret", ""),
                sandbox=credentials.get("sandbox", False),
            )

        elif broker_type == BrokerType.OANDA:
            from alphastack.brokers.oanda_connector import OandaConnector
            return OandaConnector(
                account_id=credentials.get("account_id", ""),
                api_token=credentials.get("api_token", ""),
                environment=credentials.get("environment", "practice"),
            )

        elif broker_type == BrokerType.MT5_GENERIC:
            from alphastack.brokers.mt5_connector import MT5Connector
            return MT5Connector(
                login=int(credentials.get("login", 0)),
                password=credentials.get("password", ""),
                server=credentials.get("server"),
            )

        raise ValueError(f"Unsupported broker type: {broker_type}")

    # ------------------------------------------------------------------
    # Connection testing
    # ------------------------------------------------------------------

    async def _test_connection(self, connector: BrokerConnector) -> None:
        """Test the broker connection. Raises on failure."""
        try:
            await connector.connect()
            logger.info("broker_connection_test_passed", broker=connector.name)
        except Exception as exc:
            logger.error(
                "broker_connection_test_failed",
                broker=connector.name,
                error=str(exc),
            )
            raise ConnectionError(
                f"Failed to connect to {connector.name}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Credential storage
    # ------------------------------------------------------------------

    async def _save_credentials(
        self,
        name: str,
        broker_type: BrokerType,
        credentials: dict[str, Any],
    ) -> None:
        """Save credentials encrypted in the vault."""
        vault = self._get_vault()
        if vault is None:
            logger.warning("credential_vault_unavailable_skip_save")
            return

        try:
            from alphastack.security.credentials import CredentialType

            # Save each credential field
            _type_map = {
                "login": CredentialType.BROKER_LOGIN,
                "password": CredentialType.BROKER_PASSWORD,
                "api_key": CredentialType.API_KEY,
                "api_secret": CredentialType.API_SECRET,
                "api_token": CredentialType.API_KEY,
                "account_id": CredentialType.BROKER_LOGIN,
                "server": CredentialType.BROKER_SERVER,
            }

            for key, value in credentials.items():
                if key in _type_map and value:
                    vault.store(
                        user_id="system",  # TODO: wire to actual user
                        account_id=name,
                        cred_type=_type_map[key],
                        value=str(value),
                        label=f"{name}.{key}",
                    )

            logger.info("credentials_saved", broker=name)
        except Exception as exc:
            logger.warning("credential_save_failed", broker=name, error=str(exc))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_type(connector: BrokerConnector) -> str:
        """Infer broker type from connector class name."""
        cls_name = connector.__class__.__name__.lower()
        if "fbs" in cls_name:
            return "fbs"
        if "fxpesa" in cls_name:
            return "fxpesa"
        if "oanda" in cls_name:
            return "oanda"
        if "ccxt" in cls_name:
            return "crypto"
        if "mt5" in cls_name:
            return "mt5"
        return "unknown"


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_global_setup: BrokerSetup | None = None


def get_broker_setup() -> BrokerSetup:
    """Return the global BrokerSetup singleton."""
    global _global_setup
    if _global_setup is None:
        _global_setup = BrokerSetup()
    return _global_setup
