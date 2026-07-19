"""Broker Management Routes – add, list, test, disconnect.

Provides REST endpoints for broker lifecycle management:
- POST /brokers/add — add broker with credentials (auto-detect type)
- GET /brokers — list connected brokers
- GET /brokers/{id}/status — connection health
- DELETE /brokers/{id} — disconnect broker
- POST /brokers/{id}/test — test connection

UX goal: user enters broker name + credentials → system does the rest.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from alphastack.api.rest.deps import get_broker_registry
from alphastack.brokers.setup import BrokerSetup, detect_broker_type, BrokerType
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/brokers")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BrokerAddRequest(BaseModel):
    """Request to add a new broker connection."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Broker name or alias (e.g. 'fbs', 'binance', 'oanda')",
    )
    credentials: dict[str, Any] = Field(
        ...,
        description="Broker credentials. Keys vary by type: "
                    "login+password (MT5/FBS), api_key+secret (crypto), "
                    "account_id+api_token (OANDA).",
    )
    test_connection: bool = Field(
        default=True,
        description="Test the connection before registering (default true).",
    )
    save_credentials: bool = Field(
        default=True,
        description="Save credentials encrypted (default true).",
    )


class BrokerInfo(BaseModel):
    """Broker connection info."""
    name: str
    state: str
    is_connected: bool
    broker_type: str


class BrokerStatus(BaseModel):
    """Detailed broker connection status."""
    name: str
    state: str
    is_connected: bool
    broker_type: str
    balance: dict[str, Any] | None = None
    positions_count: int = 0
    last_check: str = ""


class BrokerTestResult(BaseModel):
    """Connection test result."""
    status: str  # "connected", "error", "not_found"
    broker: str
    state: str = ""
    latency_ms: float = 0.0
    balance: dict[str, Any] | None = None
    error: str | None = None


class BrokerAddResponse(BaseModel):
    """Response after adding a broker."""
    name: str
    broker_type: str
    state: str
    is_connected: bool
    message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/add", response_model=BrokerAddResponse, status_code=status.HTTP_201_CREATED)
async def add_broker(request: BrokerAddRequest) -> BrokerAddResponse:
    """Add and connect a broker with credentials.

    Auto-detects broker type from the name and credentials shape.
    Tests the connection immediately and saves credentials encrypted.

    Supported brokers:
    - **FBS**: login + password (auto-detects cent/standard)
    - **FXPesa**: login + password + optional account_type
    - **Binance**: api_key + api_secret
    - **MEXC**: api_key + api_secret
    - **OANDA**: account_id + api_token

    Minimal example:
    ```json
    {
        "name": "fbs",
        "credentials": {
            "login": 12345678,
            "password": "your-password"
        }
    }
    ```
    """
    # Validate credentials aren't empty
    if not request.credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credentials cannot be empty.",
        )

    # Detect broker type for early validation
    broker_type = detect_broker_type(request.name, request.credentials)
    if broker_type == BrokerType.UNKNOWN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot detect broker type for '{request.name}'. "
                "Provide: login+password (MT5/FBS), api_key+secret (crypto), "
                "or account_id+api_token (OANDA)."
            ),
        )

    # Check if broker already exists
    registry = get_broker_registry()
    if registry.get(request.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Broker '{request.name}' is already registered. "
                   f"DELETE /brokers/{request.name} first to re-add.",
        )

    # Add broker via setup wizard
    setup = BrokerSetup(registry=registry)
    try:
        connector = await setup.add_broker(
            name=request.name,
            credentials=request.credentials,
            test_connection=request.test_connection,
            save_credentials=request.save_credentials,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Connection failed: {exc}",
        )
    except Exception as exc:
        logger.error("broker_add_failed", name=request.name, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add broker: {exc}",
        )

    return BrokerAddResponse(
        name=request.name,
        broker_type=broker_type.value,
        state=connector.state.value,
        is_connected=connector.is_connected,
        message=f"Broker '{request.name}' ({broker_type.value}) connected successfully.",
    )


@router.get("", response_model=list[BrokerInfo])
async def list_brokers() -> list[BrokerInfo]:
    """List all registered brokers with connection status."""
    registry = get_broker_registry()
    brokers = []

    for name in registry.names:
        connector = registry.get(name)
        if connector:
            brokers.append(BrokerInfo(
                name=name,
                state=connector.state.value,
                is_connected=connector.is_connected,
                broker_type=_infer_type(connector),
            ))

    return brokers


@router.get("/{broker_id}/status", response_model=BrokerStatus)
async def get_broker_status(broker_id: str) -> BrokerStatus:
    """Get detailed connection status for a broker.

    Returns connection state, balance, and position count.
    """
    registry = get_broker_registry()
    connector = registry.get(broker_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Broker '{broker_id}' not found.",
        )

    balance_data = None
    positions_count = 0

    if connector.is_connected:
        try:
            balance = await connector.get_balance()
            balance_data = {
                "total": balance.total,
                "available": balance.available,
                "equity": balance.equity,
                "currency": balance.currency,
                "margin_level": balance.margin_level,
            }
        except Exception as exc:
            logger.warning("broker_status_balance_failed", broker=broker_id, error=str(exc))

        try:
            positions = await connector.get_positions()
            positions_count = len(positions)
        except Exception:
            pass

    return BrokerStatus(
        name=broker_id,
        state=connector.state.value,
        is_connected=connector.is_connected,
        broker_type=_infer_type(connector),
        balance=balance_data,
        positions_count=positions_count,
        last_check=datetime.now(timezone.utc).isoformat(),
    )


@router.delete("/{broker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_broker(broker_id: str) -> None:
    """Disconnect and remove a broker.

    Closes the connection and removes saved credentials.
    """
    registry = get_broker_registry()
    connector = registry.get(broker_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Broker '{broker_id}' not found.",
        )

    setup = BrokerSetup(registry=registry)
    try:
        await setup.remove_broker(broker_id)
    except Exception as exc:
        logger.error("broker_remove_failed", broker=broker_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove broker: {exc}",
        )


@router.post("/{broker_id}/test", response_model=BrokerTestResult)
async def test_broker(broker_id: str) -> BrokerTestResult:
    """Test a broker connection.

    Attempts to connect (if not already) and fetches balance
    to verify the connection is working.
    """
    registry = get_broker_registry()
    connector = registry.get(broker_id)
    if connector is None:
        return BrokerTestResult(
            status="not_found",
            broker=broker_id,
            error=f"Broker '{broker_id}' not registered.",
        )

    setup = BrokerSetup(registry=registry)
    result = await setup.test_broker(broker_id)

    return BrokerTestResult(
        status=result["status"],
        broker=result.get("broker", broker_id),
        state=result.get("state", ""),
        latency_ms=result.get("latency_ms", 0.0),
        balance=result.get("balance"),
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_type(connector: Any) -> str:
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
