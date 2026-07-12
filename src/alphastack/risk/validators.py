"""Trade Validators — pre-trade and post-trade sanity checks.

Catches impossible, dangerous, or obviously wrong trade parameters
before they reach the broker.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

class ValidationSeverity(str, Enum):
    ERROR = "error"      # Hard rejection
    WARNING = "warning"  # Proceed with caution
    INFO = "info"        # Informational


class ValidationIssue(BaseModel):
    """A single validation finding."""
    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR


class ValidationResult(BaseModel):
    """Result of a trade validation check."""
    valid: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Trade Validator
# ---------------------------------------------------------------------------

class TradeValidator:
    """Validates trade parameters before execution.

    Pre-trade checks:
    - Price sanity (not NaN, not zero, not absurd)
    - Size sanity (positive, within broker limits)
    - Direction validity
    - Stop loss / take profit logic
    - Spread check

    Post-trade checks:
    - Fill price vs expected
    - Size reconciliation
    - Slippage analysis
    """

    def __init__(
        self,
        min_price: float = 1e-10,
        max_price: float = 1e10,
        min_size: float = 0.001,
        max_size: float = 1000.0,
        max_slippage_pct: float = 1.0,
        max_spread_pct: float = 0.5,
    ) -> None:
        self._min_price = min_price
        self._max_price = max_price
        self._min_size = min_size
        self._max_size = max_size
        self._max_slippage_pct = max_slippage_pct
        self._max_spread_pct = max_spread_pct

    # -- Pre-trade validation -----------------------------------------------

    def validate_pre_trade(self, request: Any) -> ValidationResult:
        """Run all pre-trade validation checks.

        Accepts any object with the expected attributes (TradeRequest or similar).
        """
        issues: list[ValidationIssue] = []

        # Price checks
        issues.extend(self._validate_price(request.entry_price, "entry_price"))
        issues.extend(self._validate_price(request.stop_loss, "stop_loss"))

        if hasattr(request, "take_profit") and request.take_profit > 0:
            issues.extend(self._validate_price(request.take_profit, "take_profit"))

        # Size checks
        issues.extend(self._validate_size(request.requested_size))

        # Direction checks
        issues.extend(self._validate_direction(request.direction))

        # Stop loss logic
        issues.extend(self._validate_stop_loss(
            request.entry_price,
            request.stop_loss,
            request.direction,
        ))

        # Take profit logic
        if hasattr(request, "take_profit") and request.take_profit > 0:
            issues.extend(self._validate_take_profit(
                request.entry_price,
                request.take_profit,
                request.direction,
            ))

        # Symbol check
        if not request.symbol or not request.symbol.strip():
            issues.append(ValidationIssue(
                code="EMPTY_SYMBOL",
                message="Symbol cannot be empty",
                severity=ValidationSeverity.ERROR,
            ))

        # Build result
        errors = [i.message for i in issues if i.severity == ValidationSeverity.ERROR]
        warnings = [i.message for i in issues if i.severity == ValidationSeverity.WARNING]

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            issues=issues,
        )

    # -- Post-trade validation ----------------------------------------------

    def validate_post_trade(
        self,
        expected_price: float,
        fill_price: float,
        expected_size: float,
        fill_size: float,
        direction: str,
    ) -> ValidationResult:
        """Validate a filled trade against expected parameters."""
        issues: list[ValidationIssue] = []

        # Slippage check
        if expected_price > 0:
            slippage = abs(fill_price - expected_price) / expected_price * 100
            if slippage > self._max_slippage_pct:
                issues.append(ValidationIssue(
                    code="EXCESSIVE_SLIPPAGE",
                    message=(
                        f"Slippage {slippage:.3f}% > {self._max_slippage_pct}% "
                        f"(expected {expected_price}, filled {fill_price})"
                    ),
                    severity=ValidationSeverity.WARNING,
                ))

        # Size reconciliation
        if expected_size > 0:
            size_diff = abs(fill_size - expected_size) / expected_size * 100
            if size_diff > 1.0:  # More than 1% difference
                issues.append(ValidationIssue(
                    code="SIZE_MISMATCH",
                    message=(
                        f"Fill size {fill_size} differs {size_diff:.2f}% "
                        f"from expected {expected_size}"
                    ),
                    severity=ValidationSeverity.WARNING,
                ))

        # Direction sanity (filled price should make sense)
        if direction == "long" and fill_price > expected_price * 1.05:
            issues.append(ValidationIssue(
                code="UNFAVORABLE_LONG_FILL",
                message=f"Long fill at {fill_price} is >5% above expected {expected_price}",
                severity=ValidationSeverity.WARNING,
            ))
        elif direction == "short" and fill_price < expected_price * 0.95:
            issues.append(ValidationIssue(
                code="UNFAVORABLE_SHORT_FILL",
                message=f"Short fill at {fill_price} is >5% below expected {expected_price}",
                severity=ValidationSeverity.WARNING,
            ))

        errors = [i.message for i in issues if i.severity == ValidationSeverity.ERROR]
        warnings = [i.message for i in issues if i.severity == ValidationSeverity.WARNING]

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            issues=issues,
        )

    # -- Order sanity checks ------------------------------------------------

    def validate_order_modify(
        self,
        current_sl: float,
        new_sl: float,
        current_tp: float,
        new_tp: float,
        entry_price: float,
        direction: str,
    ) -> ValidationResult:
        """Validate stop loss / take profit modification."""
        issues: list[ValidationIssue] = []

        # Stop loss can only be moved in the favorable direction
        if direction == "long" and new_sl < current_sl:
            issues.append(ValidationIssue(
                code="SL_MOVED_AGAINST",
                message=f"Long SL moved down from {current_sl} to {new_sl} (widening risk)",
                severity=ValidationSeverity.WARNING,
            ))
        elif direction == "short" and new_sl > current_sl:
            issues.append(ValidationIssue(
                code="SL_MOVED_AGAINST",
                message=f"Short SL moved up from {current_sl} to {new_sl} (widening risk)",
                severity=ValidationSeverity.WARNING,
            ))

        # Stop loss must be on the correct side of entry
        if direction == "long" and new_sl >= entry_price:
            issues.append(ValidationIssue(
                code="SL_ABOVE_ENTRY",
                message=f"Long SL {new_sl} >= entry {entry_price}",
                severity=ValidationSeverity.ERROR,
            ))
        elif direction == "short" and new_sl <= entry_price:
            issues.append(ValidationIssue(
                code="SL_BELOW_ENTRY",
                message=f"Short SL {new_sl} <= entry {entry_price}",
                severity=ValidationSeverity.ERROR,
            ))

        errors = [i.message for i in issues if i.severity == ValidationSeverity.ERROR]
        warnings = [i.message for i in issues if i.severity == ValidationSeverity.WARNING]

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            issues=issues,
        )

    # -- Internal validators ------------------------------------------------

    def _validate_price(self, price: float, field_name: str) -> list[ValidationIssue]:
        """Validate a price value."""
        issues: list[ValidationIssue] = []

        if price != price:  # NaN check
            issues.append(ValidationIssue(
                code="NAN_PRICE",
                message=f"{field_name} is NaN",
            ))
        elif price < 0:
            issues.append(ValidationIssue(
                code="NEGATIVE_PRICE",
                message=f"{field_name} is negative: {price}",
            ))
        elif price == 0 and field_name != "take_profit":
            issues.append(ValidationIssue(
                code="ZERO_PRICE",
                message=f"{field_name} is zero",
            ))
        elif price > 0 and price < self._min_price:
            issues.append(ValidationIssue(
                code="PRICE_TOO_LOW",
                message=f"{field_name} {price} below minimum {self._min_price}",
            ))
        elif price > self._max_price:
            issues.append(ValidationIssue(
                code="PRICE_TOO_HIGH",
                message=f"{field_name} {price} above maximum {self._max_price}",
            ))

        return issues

    def _validate_size(self, size: float) -> list[ValidationIssue]:
        """Validate position size."""
        issues: list[ValidationIssue] = []

        if size != size:  # NaN
            issues.append(ValidationIssue(
                code="NAN_SIZE",
                message="Position size is NaN",
            ))
        elif size <= 0:
            issues.append(ValidationIssue(
                code="NON_POSITIVE_SIZE",
                message=f"Position size must be positive: {size}",
            ))
        elif size < self._min_size:
            issues.append(ValidationIssue(
                code="SIZE_TOO_SMALL",
                message=f"Size {size} below minimum {self._min_size}",
                severity=ValidationSeverity.WARNING,
            ))
        elif size > self._max_size:
            issues.append(ValidationIssue(
                code="SIZE_TOO_LARGE",
                message=f"Size {size} exceeds maximum {self._max_size}",
            ))

        return issues

    def _validate_direction(self, direction: str) -> list[ValidationIssue]:
        """Validate trade direction."""
        issues: list[ValidationIssue] = []
        if direction not in ("long", "short"):
            issues.append(ValidationIssue(
                code="INVALID_DIRECTION",
                message=f"Direction must be 'long' or 'short': '{direction}'",
            ))
        return issues

    def _validate_stop_loss(
        self,
        entry: float,
        stop_loss: float,
        direction: str,
    ) -> list[ValidationIssue]:
        """Validate stop loss placement."""
        issues: list[ValidationIssue] = []

        if entry <= 0 or stop_loss <= 0:
            return issues

        if direction == "long" and stop_loss >= entry:
            issues.append(ValidationIssue(
                code="SL_ABOVE_ENTRY_LONG",
                message=f"Long stop loss {stop_loss} >= entry {entry}",
            ))
        elif direction == "short" and stop_loss <= entry:
            issues.append(ValidationIssue(
                code="SL_BELOW_ENTRY_SHORT",
                message=f"Short stop loss {stop_loss} <= entry {entry}",
            ))

        # Check if SL is too tight (< 0.1% of entry)
        sl_distance_pct = abs(entry - stop_loss) / entry * 100
        if sl_distance_pct < 0.1:
            issues.append(ValidationIssue(
                code="SL_TOO_TIGHT",
                message=f"Stop loss only {sl_distance_pct:.3f}% from entry (likely to be hit by noise)",
                severity=ValidationSeverity.WARNING,
            ))

        # Check if SL is too wide (> 10% of entry)
        if sl_distance_pct > 10.0:
            issues.append(ValidationIssue(
                code="SL_TOO_WIDE",
                message=f"Stop loss {sl_distance_pct:.1f}% from entry (very wide)",
                severity=ValidationSeverity.WARNING,
            ))

        return issues

    def _validate_take_profit(
        self,
        entry: float,
        take_profit: float,
        direction: str,
    ) -> list[ValidationIssue]:
        """Validate take profit placement."""
        issues: list[ValidationIssue] = []

        if entry <= 0 or take_profit <= 0:
            return issues

        if direction == "long" and take_profit <= entry:
            issues.append(ValidationIssue(
                code="TP_BELOW_ENTRY_LONG",
                message=f"Long take profit {take_profit} <= entry {entry}",
                severity=ValidationSeverity.WARNING,
            ))
        elif direction == "short" and take_profit >= entry:
            issues.append(ValidationIssue(
                code="TP_ABOVE_ENTRY_SHORT",
                message=f"Short take profit {take_profit} >= entry {entry}",
                severity=ValidationSeverity.WARNING,
            ))

        return issues
