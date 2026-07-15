# FIX RESULTS — latin-1 Encoding Bug in AlphaStack Live Server

**File:** `alphastack/live_server.py`
**Date:** 2026-07-16
**Status:** ✅ Fixed

---

## Root Cause

When ccxt signs authenticated API requests (HMAC-SHA256), it encodes the API key, secret, and request parameters using **latin-1**. If any of these strings contain non-ASCII characters (e.g. `…` U+2026 ellipsis), the encoding fails with:

```
UnicodeEncodeError: 'latin-1' codec can't encode character '\u2026'
```

This occurs because:
1. API keys/secrets may be copy-pasted with invisible Unicode characters
2. Symbol strings or other parameters could contain non-ASCII chars
3. ccxt's `requests`-based HTTP client uses latin-1 for header/body encoding

---

## Fixes Applied

### 1. Added `_sanitize_str()` helper (line ~105)

```python
def _sanitize_str(val: str) -> str:
    """Remove non-ASCII characters (e.g. U+2026 ellipsis) that cause
    ccxt/requests HMAC signing to fail with latin-1 codec error."""
    return val.encode('ascii', 'ignore').decode('ascii')
```

### 2. Sanitized API credentials at initialization (line ~110)

```python
BINANCE_API_KEY = _sanitize_str(os.environ.get("BINANCE_API_KEY", ""))
BINANCE_API_SECRET = _sanitize_str(os.environ.get("BINANCE_API_SECRET", ""))
```

### 3. Sanitized symbol in trade execution path (line ~632)

```python
safe_symbol = _sanitize_str(body.symbol)
order = exchange_testnet.create_order(
    symbol=safe_symbol, type='market', side=body.side, amount=body.quantity,
)
```

### 4. Sanitized symbol in market data fetching (line ~181)

```python
def _fetch_ohlcv(symbol, timeframe="1h", limit=200):
    return exchange_public.fetch_ohlcv(_sanitize_str(symbol), timeframe, limit=limit)
```

---

## `quantity` vs `amount` Field Mapping

**No bug found.** The `TradeCreate` Pydantic model correctly uses `quantity` (matching the API contract), and it's correctly mapped to ccxt's `amount` parameter:

```python
# TradeCreate model
quantity: float

# ccxt call — maps quantity → amount
exchange_testnet.create_order(... amount=body.quantity)
```

The `InputValidator.validate_order()` also accepts `quantity` — consistent throughout.

---

## Verification

| Check | Result |
|-------|--------|
| Python syntax | ✅ Pass |
| `_sanitize_str("api_key…")` → `"api_key"` | ✅ Pass |
| Sanitized strings encodable as latin-1 | ✅ Pass |
| `/health` endpoint responds | ✅ Status: ok |
| Binance connected | ✅ BTC price: $64,981.98 |
| Testnet configured | ✅ True |
| Pipeline available | ✅ True |

---

## Risk Assessment

- **Low risk:** `_sanitize_str` is a defensive filter; legitimate API keys are always ASCII
- **No breaking changes:** The function only strips characters that would cause encoding errors
- **Applied consistently:** All authenticated exchange calls now use sanitized inputs
