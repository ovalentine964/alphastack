"""Settings Routes – runtime configuration GET/PUT.

Exposes user-facing settings (notifications, display, risk preferences)
that can be read and updated at runtime.  Non-sensitive config only;
secrets stay in environment variables.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/settings")


# ---------------------------------------------------------------------------
# In-memory settings store (replace with DB in production)
# ---------------------------------------------------------------------------

_DEFAULT_SETTINGS: dict[str, Any] = {
    "notifications": {
        "email_enabled": True,
        "push_enabled": True,
        "signal_alerts": True,
        "trade_alerts": True,
        "price_alerts": False,
    },
    "display": {
        "theme": "dark",
        "language": "en",
        "timezone": "UTC",
        "currency": "USD",
        "decimal_places": 2,
    },
    "risk": {
        "max_position_size_pct": 5.0,
        "max_daily_loss_pct": 2.0,
        "max_drawdown_pct": 10.0,
        "auto_stop_loss": True,
        "default_risk_reward": 2.0,
    },
    "trading": {
        "default_order_type": "limit",
        "confirmation_required": True,
        "auto_close_on_target": False,
        "paper_trading": True,
    },
}

_settings_store: dict[str, Any] = {}


def _get_settings() -> dict[str, Any]:
    if not _settings_store:
        _settings_store.update(_DEFAULT_SETTINGS)
    return _settings_store


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SettingsResponse(BaseModel):
    notifications: dict[str, Any]
    display: dict[str, Any]
    risk: dict[str, Any]
    trading: dict[str, Any]


class SettingsUpdateRequest(BaseModel):
    notifications: dict[str, Any] | None = None
    display: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    trading: dict[str, Any] | None = None


class SettingsUpdateResponse(BaseModel):
    message: str
    settings: SettingsResponse


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Get current runtime settings."""
    s = _get_settings()
    return SettingsResponse(**s)


@router.put("", response_model=SettingsUpdateResponse)
async def update_settings(body: SettingsUpdateRequest) -> SettingsUpdateResponse:
    """Update runtime settings (partial update — only provided sections change)."""
    current = _get_settings()

    for section in ("notifications", "display", "risk", "trading"):
        updates = getattr(body, section, None)
        if updates is not None:
            if section not in current:
                current[section] = {}
            current[section].update(updates)

    logger.info("settings_updated", keys=[k for k, v in body.model_dump().items() if v is not None])
    return SettingsUpdateResponse(
        message="Settings updated",
        settings=SettingsResponse(**current),
    )
