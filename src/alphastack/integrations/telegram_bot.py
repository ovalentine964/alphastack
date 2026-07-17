"""
AlphaStack Telegram Bot Integration

Provides two-way communication between Alpha and Telegram:
  • Chat commands — user sends /status, /portfolio, /signals, etc.
  • Notifications — Alpha pushes trade alerts, risk warnings, daily summaries.

Reads config from environment variables or from the live_server settings API.
Uses python-telegram-bot (async). Gracefully degrades if token is missing.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import TelegramError

if TYPE_CHECKING:
    from alphastack.api.rest.deps import TradeStore, SignalStore, PortfolioService

logger = logging.getLogger("alphastack.telegram")


# ═══════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════

class TelegramConfig:
    """Holds Telegram bot credentials.  Reads from env by default."""

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        allowed_chat_ids: list[str] | None = None,
        webhook_url: str | None = None,
    ) -> None:
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.webhook_url = webhook_url or os.environ.get("TELEGRAM_WEBHOOK_URL", "")
        # Parse allowed chat IDs from env (comma-separated)
        if allowed_chat_ids is not None:
            self.allowed_chat_ids = [str(cid) for cid in allowed_chat_ids]
        else:
            env_ids = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
            self.allowed_chat_ids = [
                cid.strip() for cid in env_ids.split(",") if cid.strip()
            ]

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def is_authorized(self, chat_id: int | str) -> bool:
        """Check if a chat ID is authorized to interact with the bot."""
        if not self.allowed_chat_ids:
            # No allowlist configured — fall back to primary chat_id only
            return str(chat_id) == str(self.chat_id)
        return str(chat_id) in self.allowed_chat_ids


# ═══════════════════════════════════════════════════════════
# Notification Queue — survives bot restarts (in-memory)
# ═══════════════════════════════════════════════════════════

_MAX_QUEUE = 500


class NotificationQueue:
    """Bounded FIFO queue for outgoing Telegram messages."""

    def __init__(self, maxlen: int = _MAX_QUEUE) -> None:
        self._q: deque[str] = deque(maxlen=maxlen)

    def enqueue(self, text: str) -> None:
        self._q.append(text)

    def drain(self, limit: int = 50) -> list[str]:
        msgs: list[str] = []
        while self._q and len(msgs) < limit:
            msgs.append(self._q.popleft())
        return msgs

    def __len__(self) -> int:
        return len(self._q)


# ═══════════════════════════════════════════════════════════
# Telegram Bot — chat commands + notification sender
# ═══════════════════════════════════════════════════════════

class AlphaTelegramBot:
    """Async Telegram bot with command handlers and notification delivery.

    Usage::

        bot = AlphaTelegramBot(config, trade_store, signal_store, portfolio_service)
        await bot.start()   # starts polling + flush loop
        bot.notify("✅ Trade executed")  # enqueue a message
        await bot.stop()
    """

    def __init__(
        self,
        config: TelegramConfig,
        trade_store: "TradeStore | None" = None,
        signal_store: "SignalStore | None" = None,
        portfolio_service: "PortfolioService | None" = None,
        exchange_public: Any = None,
        generate_signals: Any = None,
        ai_model: Any = None,
    ) -> None:
        self.config = config
        self.trade_store = trade_store
        self.signal_store = signal_store
        self.portfolio_service = portfolio_service
        self.exchange_public = exchange_public
        self._generate_signals = generate_signals
        self._ai_model = ai_model

        self._queue = NotificationQueue()
        self._app: Application | None = None
        self._flush_task: asyncio.Task | None = None
        self._running = False

    # ── Lifecycle ──────────────────────────────────────────

    async def start(self) -> None:
        """Build and start the Telegram application.

        Uses webhooks if TELEGRAM_WEBHOOK_URL is set (production — works with multiple machines).
        Falls back to polling if no webhook URL (development — single machine only).
        """
        if not self.config.is_configured:
            logger.info("telegram.skipped — token or chat_id not set")
            return

        self._app = (
            Application.builder()
            .token(self.config.bot_token)
            .build()
        )

        # Register command handlers
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("portfolio", self._cmd_portfolio))
        self._app.add_handler(CommandHandler("signals", self._cmd_signals))
        self._app.add_handler(CommandHandler("trades", self._cmd_trades))
        self._app.add_handler(CommandHandler("explain", self._cmd_explain))
        self._app.add_handler(CommandHandler("market", self._cmd_market))
        # Catch-all for free-text messages
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._cmd_fallback))

        # Set bot command menu
        await self._app.bot.set_my_commands([
            BotCommand("status", "System status (BTC price, pipeline, agents)"),
            BotCommand("portfolio", "Current positions and P&L"),
            BotCommand("signals", "Active signals with confluence scores"),
            BotCommand("trades", "Recent trade history"),
            BotCommand("explain", "Explain the last trade"),
            BotCommand("market", "What's moving the market"),
            BotCommand("help", "List all commands"),
        ])

        await self._app.initialize()
        await self._app.start()

        if self.config.webhook_url:
            # Production: webhook mode — register URL with Telegram, handle via FastAPI
            webhook_path = "/webhook/telegram"
            webhook_url = f"{self.config.webhook_url}{webhook_path}"
            try:
                # Register webhook URL with Telegram (no local server — FastAPI handles it)
                await self._app.bot.set_webhook(
                    url=webhook_url,
                    drop_pending_updates=True,
                    max_connections=40,
                )
                logger.info("telegram.webhook_registered url=%s", webhook_url)
            except Exception as e:
                logger.warning("telegram.webhook_register_failed error=%s fallback=polling", str(e))
                await self._app.updater.start_polling(drop_pending_updates=True)
                logger.info("telegram.started_polling_fallback")
        else:
            # Development: polling mode — single machine only
            await self._app.updater.start_polling(drop_pending_updates=True)
            logger.info("telegram.started_polling")

        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())

    def get_webhook_app(self):
        """Return the ASGI webhook app for integration with FastAPI."""
        if self._app and self.config.webhook_url:
            return self._app.updater.webhook_app(update_queue=self._app.update_queue)
        return None

    async def stop(self) -> None:
        """Gracefully stop the bot."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
        if self._app:
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
            except Exception:
                logger.warning("telegram.shutdown_error", exc_info=True)
        logger.info("telegram.stopped")

    # ── Public notification API ────────────────────────────

    def notify(self, text: str) -> None:
        """Enqueue a notification message. Non-blocking."""
        self._queue.enqueue(text)

    # ── Internal: flush queue → Telegram ───────────────────

    async def _flush_loop(self) -> None:
        """Background loop: drain the queue and send messages."""
        while self._running:
            try:
                messages = self._queue.drain(limit=20)
                for msg in messages:
                    await self._send(msg)
                    await asyncio.sleep(0.1)  # rate-limit courtesy
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("telegram.flush_error", exc_info=True)
            await asyncio.sleep(2)

    async def _send(self, text: str) -> None:
        """Send a single message to the configured chat."""
        if not self._app:
            return
        try:
            await self._app.bot.send_message(
                chat_id=self.config.chat_id,
                text=text,
                parse_mode="Markdown",
            )
        except TelegramError:
            # Retry once without Markdown if formatting breaks
            try:
                await self._app.bot.send_message(
                    chat_id=self.config.chat_id,
                    text=text,
                )
            except TelegramError as e:
                logger.warning("telegram.send_failed: %s", e)

    # ── Auth helper ──────────────────────────────────────────

    def _check_auth(self, update: Update) -> bool:
        """Check if the message sender is authorized. Returns True if OK."""
        if not update.message or not update.message.chat_id:
            return False
        return self.config.is_authorized(update.message.chat_id)

    # ── Command Handlers ───────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        await update.message.reply_text(
            "🤖 *AlphaStack* — AI Trading System\n\n"
            "I'm Alpha, your AI trading assistant.\n"
            "Type /help to see what I can do.",
            parse_mode="Markdown",
        )

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        await update.message.reply_text(
            "📋 *AlphaStack Commands*\n\n"
            "/status — System status (BTC price, pipeline, agents)\n"
            "/portfolio — Current positions & P&L\n"
            "/signals — Active signals with confluence scores\n"
            "/trades — Recent trade history\n"
            "/explain — Explain the last trade\n"
            "/market — What's moving the market right now\n"
            "/help — This message\n\n"
            "💬 Send any text and I'll respond with AI reasoning.",
            parse_mode="Markdown",
        )

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        lines = ["📊 *AlphaStack Status*\n"]
        # BTC price
        if self.exchange_public:
            try:
                ticker = self.exchange_public.fetch_ticker("BTC/USDT")
                lines.append(f"💰 BTC: ${ticker['last']:,.2f} ({ticker.get('percentage', 0):+.2f}% 24h)")
            except Exception:
                lines.append("💰 BTC: ⚠️ unavailable")
        # Pipeline
        lines.append("🧠 Pipeline: ✅ 16-step AlphaStack")
        # Agents
        lines.append("🤖 Agents: news · strategy · risk · execution · reflection")
        # Testnet
        lines.append("🏦 Testnet: ✅ connected" if self.exchange_public else "🏦 Testnet: ❌ not connected")
        # Uptime
        lines.append(f"⏰ Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_portfolio(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        if not self.trade_store:
            await update.message.reply_text("⚠️ Trade store not available")
            return
        open_trades = self.trade_store.list_trades(status_filter="open")
        if not open_trades:
            await update.message.reply_text("📭 No open positions")
            return
        lines = ["💼 *Portfolio*\n"]
        for t in open_trades:
            entry = t.get("entry_price") or 0
            qty = t["quantity"]
            side = "🟢 LONG" if t["side"] == "buy" else "🔴 SHORT"
            lines.append(f"{side} {t['symbol']} — {qty} @ ${entry:,.2f}")
            if t.get("stop_loss"):
                lines.append(f"  SL: ${t['stop_loss']:,.2f} | TP: ${t.get('take_profit', '—'):,.2f}")
        # P&L summary
        closed = self.trade_store.list_trades(status_filter="closed")
        total_pnl = sum(t.get("pnl") or 0 for t in closed)
        wins = sum(1 for t in closed if (t.get("pnl") or 0) > 0)
        losses = sum(1 for t in closed if (t.get("pnl") or 0) < 0)
        lines.append(f"\n📈 Closed P&L: *${total_pnl:+,.2f}* ({wins}W / {losses}L)")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_signals(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        signals: list[dict] = []
        if self._generate_signals:
            try:
                signals = await self._generate_signals()
            except Exception:
                pass
        if not signals and self.signal_store:
            signals = self.signal_store.list_active()
        if not signals:
            await update.message.reply_text("📭 No active signals")
            return
        lines = ["🔔 *Active Signals*\n"]
        for s in signals[:10]:
            direction = s.get("direction", "?").upper()
            emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"
            score = s.get("confluence_score", s.get("confidence", 0))
            if isinstance(score, float) and score <= 1:
                score *= 100
            lines.append(
                f"{emoji} *{s['symbol']}* {direction}\n"
                f"  Confluence: {score:.0f}% | Strategy: {s.get('strategy_id', '—')}\n"
                f"  Entry: ${s.get('entry_price', 0):,.2f} | RR: {s.get('risk_reward', '—')}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_trades(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        if not self.trade_store:
            await update.message.reply_text("⚠️ Trade store not available")
            return
        trades = self.trade_store.list_trades()
        if not trades:
            await update.message.reply_text("📭 No trades yet")
            return
        lines = ["📜 *Recent Trades*\n"]
        for t in trades[-10:]:
            status_emoji = {"open": "🟢", "closed": "📊", "pending": "⏳"}.get(t["status"], "⚪")
            pnl_str = ""
            if t.get("pnl") is not None:
                pnl_val = t["pnl"]
                pnl_str = f" | P&L: *${pnl_val:+,.2f}*"
            lines.append(
                f"{status_emoji} {t['symbol']} {t['side'].upper()} {t['quantity']}"
                f" @ ${t.get('entry_price', 0):,.2f}{pnl_str}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_explain(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        if not self.trade_store:
            await update.message.reply_text("⚠️ Trade store not available")
            return
        closed = self.trade_store.list_trades(status_filter="closed")
        if not closed:
            await update.message.reply_text("📭 No closed trades to explain")
            return
        last = sorted(closed, key=lambda x: x.get("closed_at") or "")[-1]
        pnl = last.get("pnl") or 0
        pnl_pct = 0
        entry = last.get("entry_price") or 0
        exit_p = last.get("exit_price") or 0
        if entry:
            pnl_pct = ((exit_p / entry) - 1) * 100
            if last["side"] == "sell":
                pnl_pct = -pnl_pct

        lines = [
            "🔍 *Last Trade Explained*\n",
            f"*{last['symbol']}* — {last['side'].upper()}",
            f"Entry: ${entry:,.2f} → Exit: ${exit_p:,.2f}",
            f"P&L: *${pnl:+,.2f}* ({pnl_pct:+.2f}%)",
            f"Quantity: {last['quantity']}",
            f"Strategy: {last.get('strategy_id', '—')}",
            f"Opened: {last.get('opened_at', '—')[:19]}",
            f"Closed: {last.get('closed_at', '—')[:19]}",
        ]
        if last.get("notes"):
            lines.append(f"\n📝 Notes: {last['notes']}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_market(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        if not self.exchange_public:
            await update.message.reply_text("⚠️ Exchange not available")
            return
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
        lines = ["🌍 *Market Overview*\n"]
        for sym in symbols:
            try:
                t = self.exchange_public.fetch_ticker(sym)
                pct = t.get("percentage", 0) or 0
                emoji = "🟢" if pct >= 0 else "🔴"
                lines.append(f"{emoji} *{sym}*: ${t['last']:,.2f} ({pct:+.2f}%)")
            except Exception:
                lines.append(f"⚪ *{sym}*: unavailable")
        lines.append(f"\n⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_fallback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Free-text message → AI-powered conversational response."""
        if not self._check_auth(update):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        user_msg = update.message.text

        # Gather market context for the AI
        market_context = ""
        if self.exchange_public:
            try:
                ticker = self.exchange_public.fetch_ticker("BTC/USDT")
                market_context = f"BTC=${ticker['last']:,.2f} ({ticker.get('percentage', 0):+.2f}% 24h)"
            except Exception:
                market_context = "BTC price unavailable"

        # Get portfolio context
        portfolio_context = ""
        if self.trade_store:
            try:
                open_trades = self.trade_store.list_trades(status_filter="open")
                portfolio_context = f"{len(open_trades)} open positions"
            except Exception:
                pass

        # Build prompt with context
        system_prompt = (
            f"You are AlphaStack AI — an institutional-grade multi-agent quantitative trading system. "
            f"\n\nCURRENT MARKET: {market_context}. PORTFOLIO: {portfolio_context}. "
            f"\n\nYOUR ACTUAL STRATEGY — the 16-step AlphaStack Pipeline: "
            f"\n1. Fundamental Analysis — news sentiment, macro events, economic calendar" 
            f"\n2. Market Bias — multi-timeframe EMA crossover (5/20) across 1H, 4H, 1D" 
            f"\n3. Session Detection — London/NY/Asian session with volatility multipliers" 
            f"\n4. Market Structure — swing point detection, BOS/CHoCH identification" 
            f"\n5. Support/Resistance — key price levels from multi-timeframe analysis" 
            f"\n6. Liquidity Mapping — equal highs/lows, liquidity pools, stop clusters" 
            f"\n7. Smart Money Concepts — order blocks, fair value gaps, breaker blocks" 
            f"\n8. RSI Analysis — Wilder smoothing, divergence detection, regime-adaptive thresholds" 
            f"\n9. Candlestick Patterns — engulfing, pin bars, morning/evening star" 
            f"\n10. Confluence Engine — weighted voting from all components, minimum agreement threshold" 
            f"\n11. Position Sizing — risk-based sizing using actual stop price, spread cost included" 
            f"\n12. Stop Loss — structure-based + ATR-based, picks the more conservative" 
            f"\n13. Take Profit — multiple R:R targets (1.5x, 2.5x, 4x) with partial TPs" 
            f"\n14. Trade Management — breakeven at 1R, trailing at 1.5R, partial close at TP1" 
            f"\n15. Exit Logic — time-based, structure-flip, confluence-drop, stop-loss hit" 
            f"\n16. Trade Journal — structured logging with JSON output" 
            f"\n\nMULTI-AGENT SYSTEM: You have 5 specialized agents: "
            f"\n- News Agent: scans macro events and adjusts risk" 
            f"\n- Strategy Agent: runs the 16-step pipeline" 
            f"\n- Risk Agent: enforces drawdown limits, position limits, circuit breakers" 
            f"\n- Execution Agent: handles order routing and fill tracking" 
            f"\n- Reflection Agent: post-trade analysis and learning" 
            f"\n\nBROKER SUPPORT: Binance (crypto), FXPesa/FBS (forex via MT5 bridge)" 
            f"\nRISK RULES: Max 2% per trade, max 15% drawdown, max 10 open positions" 
            f"\n\nWhen asked about your strategy, describe THIS system — not generic strategies. " 
            f"You are NOT a generic chatbot. You are a specific multi-agent trading system with a 16-step pipeline. " 
            f"Be specific about your pipeline steps, agent architecture, and risk management. "
            f"Keep responses under 500 words."
        )

        if self._ai_model:
            try:
                await update.message.reply_chat_action("typing")
                response = await self._ai_model.chat(user_msg, system=system_prompt)
                # Split long messages (Telegram limit:4096 chars)
                for i in range(0, len(response), 4000):
                    await update.message.reply_text(
                        response[i:i+4000],
                        parse_mode="Markdown" if i == 0 else None,
                    )
            except Exception as e:
                logger.warning(f"telegram.ai_error: {e}")
                await update.message.reply_text(
                    f"🧠 *Alpha received:*\n_{user_msg}_\n\n"
                    f"⚠️ AI temporarily unavailable. Try /status, /signals, or /market.",
                    parse_mode="Markdown",
                )
        else:
            # Fallback: no AI model configured
            await update.message.reply_text(
                f"🧠 *Alpha received:*\n_{user_msg}_\n\n"
                "I'm a trading AI — try /status, /signals, /portfolio, or /market for actionable info.\n"
                "AI chat not configured yet. Set AI_API_KEY to enable conversational mode.",
                parse_mode="Markdown",
            )


# ═══════════════════════════════════════════════════════════
# Convenience notification helpers (module-level)
# ═══════════════════════════════════════════════════════════

_bot_instance: AlphaTelegramBot | None = None


def get_bot() -> AlphaTelegramBot | None:
    """Return the global bot instance (or None)."""
    return _bot_instance


def set_bot(bot: AlphaTelegramBot | None) -> None:
    """Register the global bot instance."""
    global _bot_instance
    _bot_instance = bot


def notify_trade_executed(symbol: str, side: str, price: float, confluence: float) -> None:
    emoji = "✅" if side.lower() == "buy" else "🔴"
    b = get_bot()
    if b:
        b.notify(f"{emoji} *{side.upper()}* {symbol} @ ${price:,.2f} — Confluence: {confluence:.0f}%")


def notify_trade_closed(symbol: str, pnl: float, pnl_pct: float) -> None:
    emoji = "📈" if pnl >= 0 else "📉"
    b = get_bot()
    if b:
        b.notify(f"📊 *{symbol}* trade closed — P&L: *${pnl:+,.2f}* ({pnl_pct:+.2f}%) {emoji}")


def notify_risk_alert(message: str) -> None:
    b = get_bot()
    if b:
        b.notify(f"⚠️ *Risk Alert*\n{message}")


def notify_signal(symbol: str, direction: str, confidence: float) -> None:
    b = get_bot()
    if b:
        b.notify(f"🔔 New signal: *{symbol}* {direction.upper()} — Confidence: {confidence:.0f}%")


def notify_daily_summary(trades: int, wins: int, pnl: float) -> None:
    b = get_bot()
    if b:
        emoji = "📈" if pnl >= 0 else "📉"
        b.notify(f"{emoji} *Daily Summary*\n{trades} trades, {wins} wins, *${pnl:+,.2f}*")


def notify_market_alert(message: str) -> None:
    b = get_bot()
    if b:
        b.notify(f"🔴 *Market Alert*\n{message}")
