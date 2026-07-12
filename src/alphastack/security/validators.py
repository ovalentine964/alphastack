"""Input validation — SQL injection, XSS, order parameter, API sanitization.

Implements input validation from architecture_security.md §4.5:
- SQL injection prevention (parameterized queries)
- XSS prevention (output encoding)
- Order parameter validation (strict Pydantic-like checks)
- API input sanitization (general-purpose)
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Patterns that should NEVER appear in user input
_SQL_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bunion\b.*\bselect\b"),
    re.compile(r"(?i)\bselect\b.*\bfrom\b"),
    re.compile(r"(?i)\binsert\b.*\binto\b"),
    re.compile(r"(?i)\bdelete\b.*\bfrom\b"),
    re.compile(r"(?i)\bdrop\b.*\btable\b"),
    re.compile(r"(?i)\bupdate\b.*\bset\b"),
    re.compile(r"(?i);\s*--"),
    re.compile(r"(?i)'\s*or\s*'?\d*'?\s*=\s*'?\d*"),
    re.compile(r"(?i)'\s*or\s*'1'\s*=\s*'1"),
    re.compile(r"(?i)\bexec\b.*\bxp_"),
    re.compile(r"(?i)/\*.*\*/"),
]

_XSS_PATTERNS = [
    re.compile(r"<\s*script", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"<\s*iframe", re.IGNORECASE),
    re.compile(r"<\s*object", re.IGNORECASE),
    re.compile(r"<\s*embed", re.IGNORECASE),
    re.compile(r"<\s*link\s+", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
]

# Valid symbol pattern: EUR/USD, BTC/USDT, AAPL, etc.
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,10}(/[A-Z0-9]{1,10})?$")

# Valid order sides
_VALID_SIDES = {"buy", "sell"}

# Valid order types
_VALID_ORDER_TYPES = {"market", "limit", "stop", "stop_limit", "trailing_stop"}

# Valid time-in-force
_VALID_TIF = {"gtc", "ioc", "fok", "day"}


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of an input validation check."""
    is_valid: bool
    errors: list[str]
    sanitized: Any = None

    def __bool__(self) -> bool:
        return self.is_valid

    @classmethod
    def ok(cls, sanitized: Any = None) -> ValidationResult:
        return cls(is_valid=True, errors=[], sanitized=sanitized)

    @classmethod
    def fail(cls, *errors: str) -> ValidationResult:
        return cls(is_valid=False, errors=list(errors))


# ---------------------------------------------------------------------------
# Input Validator
# ---------------------------------------------------------------------------

class InputValidator:
    """General-purpose input validation and sanitization."""

    # -- SQL injection ------------------------------------------------------

    @staticmethod
    def check_sql_injection(value: str) -> ValidationResult:
        """Check if *value* contains SQL injection patterns.

        This is a **defense-in-depth** layer. The primary defence is
        parameterized queries (SQLAlchemy ORM). This adds a pre-check.
        """
        for pattern in _SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                return ValidationResult.fail(
                    f"Potential SQL injection detected: pattern '{pattern.pattern}'"
                )
        return ValidationResult.ok(value)

    @staticmethod
    def sanitize_sql_like(value: str) -> str:
        """Escape special characters for SQL LIKE patterns."""
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    # -- XSS ----------------------------------------------------------------

    @staticmethod
    def check_xss(value: str) -> ValidationResult:
        """Check if *value* contains XSS attack patterns."""
        for pattern in _XSS_PATTERNS:
            if pattern.search(value):
                return ValidationResult.fail(
                    f"Potential XSS detected: pattern '{pattern.pattern}'"
                )
        return ValidationResult.ok(value)

    @staticmethod
    def escape_html(value: str) -> str:
        """HTML-encode *value* for safe output."""
        return html.escape(value, quote=True)

    @staticmethod
    def strip_html_tags(value: str) -> str:
        """Remove all HTML tags from *value*."""
        return re.sub(r"<[^>]+>", "", value)

    # -- General sanitization -----------------------------------------------

    @staticmethod
    def sanitize_string(
        value: str,
        *,
        max_length: int = 1000,
        allow_html: bool = False,
        strip: bool = True,
    ) -> ValidationResult:
        """Sanitize a general string input."""
        errors: list[str] = []
        if strip:
            value = value.strip()

        if len(value) > max_length:
            errors.append(f"Exceeds maximum length of {max_length}")

        if not allow_html:
            xss_check = InputValidator.check_xss(value)
            if not xss_check:
                errors.extend(xss_check.errors)
            value = InputValidator.strip_html_tags(value)

        sql_check = InputValidator.check_sql_injection(value)
        if not sql_check:
            errors.extend(sql_check.errors)

        if errors:
            return ValidationResult.fail(*errors)
        return ValidationResult.ok(value)

    # -- Email validation ---------------------------------------------------

    _EMAIL_RE = re.compile(
        r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    )

    @classmethod
    def validate_email(cls, email: str) -> ValidationResult:
        email = email.strip().lower()
        if len(email) > 254:
            return ValidationResult.fail("Email exceeds 254 characters")
        if not cls._EMAIL_RE.match(email):
            return ValidationResult.fail("Invalid email format")
        return ValidationResult.ok(email)

    # -- Order parameter validation -----------------------------------------

    @classmethod
    def validate_order(
        cls,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        time_in_force: str = "gtc",
    ) -> ValidationResult:
        """Validate all order parameters.  Returns sanitized values on success."""
        errors: list[str] = []

        # Symbol
        symbol = symbol.upper().strip()
        if not _SYMBOL_RE.match(symbol):
            errors.append(f"Invalid symbol format: {symbol!r}")

        # Side
        side = side.lower().strip()
        if side not in _VALID_SIDES:
            errors.append(f"Invalid side: {side!r} (expected buy/sell)")

        # Order type
        order_type = order_type.lower().strip()
        if order_type not in _VALID_ORDER_TYPES:
            errors.append(f"Invalid order type: {order_type!r}")

        # Quantity
        if quantity <= 0:
            errors.append("Quantity must be positive")
        if quantity > 1_000_000:
            errors.append("Quantity exceeds maximum (1,000,000)")

        # Price (required for limit/stop)
        if order_type in ("limit", "stop", "stop_limit"):
            if price is None:
                errors.append(f"Price required for {order_type} orders")
            elif price <= 0:
                errors.append("Price must be positive")

        # Stop loss / take profit
        if stop_loss is not None and stop_loss <= 0:
            errors.append("Stop loss must be positive")
        if take_profit is not None and take_profit <= 0:
            errors.append("Take profit must be positive")

        # Time in force
        time_in_force = time_in_force.lower().strip()
        if time_in_force not in _VALID_TIF:
            errors.append(f"Invalid time-in-force: {time_in_force!r}")

        # Cross-field: SL/TP vs side
        if price and stop_loss:
            if side == "buy" and stop_loss >= price:
                errors.append("Buy stop loss must be below entry price")
            if side == "sell" and stop_loss <= price:
                errors.append("Sell stop loss must be above entry price")

        if errors:
            return ValidationResult.fail(*errors)

        return ValidationResult.ok({
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
            "price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "time_in_force": time_in_force,
        })

    # -- Numeric range validation -------------------------------------------

    @staticmethod
    def validate_range(
        value: float,
        *,
        min_val: float | None = None,
        max_val: float | None = None,
        name: str = "value",
    ) -> ValidationResult:
        errors: list[str] = []
        if min_val is not None and value < min_val:
            errors.append(f"{name} must be >= {min_val}")
        if max_val is not None and value > max_val:
            errors.append(f"{name} must be <= {max_val}")
        if errors:
            return ValidationResult.fail(*errors)
        return ValidationResult.ok(value)

    # -- Path traversal prevention ------------------------------------------

    _DANGEROUS_PATH_PATTERNS = [
        re.compile(r"\.\./"),
        re.compile(r"\.\.\\"),
        re.compile(r"^/etc/"),
        re.compile(r"^/proc/"),
        re.compile(r"^/sys/"),
    ]

    @classmethod
    def validate_file_path(
        cls,
        path: str,
        *,
        allowed_roots: list[str] | None = None,
    ) -> ValidationResult:
        """Check for path traversal attacks."""
        for pattern in cls._DANGEROUS_PATH_PATTERNS:
            if pattern.search(path):
                return ValidationResult.fail(f"Dangerous path pattern: {pattern.pattern}")

        if allowed_roots:
            import os
            resolved = os.path.realpath(path)
            if not any(resolved.startswith(root) for root in allowed_roots):
                return ValidationResult.fail(f"Path outside allowed roots")
        return ValidationResult.ok(path)
