# Telegram Bot Integration — Implementation Report

**Date:** 2026-07-16
**Status:** ✅ Complete

## Overview

Built a two-way Telegram integration for AlphaStack: users can chat with Alpha via commands, and the system pushes trade/risk/market notifications automatically.

## Files Created / Modified

### Created
| File | Lines | Purpose |
|------|-------|---------|
| `src/alphastack/integrations/__init__.py` | 1 | Package init |
| `src/alphastack/integrations/telegram_bot.py` | ~280 | Full Telegram bot integration |

### Modified
| File | Change |
|------|--------|
| `live_server.py` | +70 lines: import Telegram module, init bot in lifespan, add `/api/v1/config/telegram` GET/POST endpoints |
| `requirements.txt` | Added `python-telegram-bot>=21.0`, `PyJWT>=2.8.0`, `prometheus-client>=0.19.0` |

## Architecture

```
User (Telegram) ──message──▶ AlphaTelegramBot ──command handler──▶ TradeStore / SignalStore / Exchange
                                      │
Live Server ──notify()──▶ NotificationQueue ──flush loop──▶ Telegram API
```

### Key Classes

- **`TelegramConfig`** — Reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from env. Has `is_configured` property.
- **`NotificationQueue`** — Bounded FIFO (500 messages max). Survives in-process restarts. `enqueue()` is non-blocking.
- **`AlphaTelegramBot`** — Core bot. Registers 8 command handlers + free-text fallback. Runs in polling mode via `python-telegram-bot` async API.

### Module-Level Notification Helpers

Convenience functions for other modules to fire notifications without importing the bot directly:

```python
from alphastack.integrations.telegram_bot import notify_trade_executed
notify_trade_executed("BTC/USDT", "buy", 65000.0, 78.0)
# → "✅ BUY BTC/USDT @ $65,000.00 — Confluence: 78%"
```

Available: `notify_trade_executed`, `notify_trade_closed`, `notify_risk_alert`, `notify_signal`, `notify_daily_summary`, `notify_market_alert`.

## Chat Commands

| Command | Description | Data Source |
|---------|-------------|-------------|
| `/start` | Welcome message | — |
| `/help` | List all commands | — |
| `/status` | BTC price, pipeline, agents, testnet | Binance exchange |
| `/portfolio` | Open positions & P&L summary | `TradeStore` |
| `/signals` | Active signals with confluence | Pipeline / `SignalStore` |
| `/trades` | Last 10 trades | `TradeStore` |
| `/explain` | Explain last closed trade | `TradeStore` |
| `/market` | Top 5 tickers | Binance exchange |
| *(any text)* | Alpha reasoning prompt | — |

## Notification Types

| Event | Format |
|-------|--------|
| Trade executed | `✅ BUY BTC @ $65,000 — Confluence: 78%` |
| Trade closed | `📊 BTC trade closed — P&L: +$150 (2.3%) 📈` |
| Risk alert | `⚠️ Risk Alert\n{message}` |
| Signal generated | `🔔 New signal: SOL LONG — Confidence: 72%` |
| Daily summary | `📈 Daily Summary\n5 trades, 3 wins, +$340` |
| Market alert | `🔴 Market Alert\n{message}` |

## API Endpoints Added

### `GET /api/v1/config/telegram`
Returns current Telegram config status.

### `POST /api/v1/config/telegram`
Set bot token and chat ID at runtime. Restarts the bot with new credentials.

```json
{"bot_token": "123:ABC...", "chat_id": "-100123456"}
```

## Configuration

Set via environment variables:
```bash
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="-100your_chat_id"
```

Or via API:
```bash
curl -X POST http://localhost:8000/api/v1/config/telegram \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"bot_token": "...", "chat_id": "..."}'
```

## Error Handling

- **Missing config:** Bot silently skips initialization. Server runs normally.
- **Telegram down:** `_send()` catches `TelegramError`, retries once without Markdown formatting.
- **Queue overflow:** Deque with `maxlen=500` drops oldest messages automatically.
- **Formatting errors:** Falls back to plain text if Markdown parse fails.

## Integration with live_server.py

The bot starts inside the FastAPI `lifespan` context manager:

1. On startup: reads env config → creates `AlphaTelegramBot` → spawns `start()` as background task
2. On shutdown: calls `bot.stop()` → cancels flush loop → closes Telegram app

No blocking. The bot runs its own polling loop and notification flush loop as `asyncio.Task` instances.

## Usage from Other Modules

To send a notification from anywhere in AlphaStack:

```python
from alphastack.integrations.telegram_bot import notify_trade_executed, notify_risk_alert

# After a trade executes
notify_trade_executed("BTC/USDT", "buy", 65000.0, 78.0)

# Risk agent detects drawdown
notify_risk_alert("Drawdown at 8% — reducing position size")
```

The functions are safe to call even if Telegram is not configured (they no-op).
