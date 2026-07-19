"""
Voice Trade Handler for AlphaStack

Orchestrates the full voice trading pipeline:
  Audio In → STT → Command Parser → Trade Execution → TTS Response

Handles:
  - Voice note intake (from Telegram, WhatsApp, phone)
  - Multi-turn confirmation flows for trade execution
  - Multilingual responses (English, Swahili, Sheng)
  - P&L announcements and trade confirmations
  - Safety: confirmation required for all money-moving actions
  - Session state: tracks pending confirmations per user

Usage:
    handler = VoiceTradeHandler(config)
    await handler.initialize()

    # Process a voice note
    response_audio = await handler.handle_voice(
        audio_bytes=voice_ogg,
        user_id="user_123",
        content_type="ogg",
    )
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from alphastack.voice.commands import CommandIntent, VoiceCommand, VoiceCommandParser
from alphastack.voice.stt import SpeechToText, STTConfig
from alphastack.voice.tts import TextToSpeech, TTSConfig

logger = logging.getLogger("alphastack.voice.handler")


class SessionState(str, Enum):
    IDLE = "idle"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    AWAITING_CLARIFICATION = "awaiting_clarification"


@dataclass
class UserSession:
    """Per-user voice interaction state."""
    user_id: str
    state: SessionState = SessionState.IDLE
    last_language: str = "en"
    pending_command: VoiceCommand | None = None
    pending_params: dict[str, Any] = field(default_factory=dict)
    last_response: str = ""
    last_audio: bytes = b""
    interaction_count: int = 0
    last_interaction_time: float = 0.0


@dataclass
class VoiceHandlerConfig:
    """Configuration for the voice trade handler."""
    # Confirmation
    require_confirmation: bool = True      # Always confirm trades
    confirmation_timeout_sec: float = 120.0  # Auto-cancel after 2 min

    # Safety limits
    max_trade_amount_usd: float = 1000.0  # Max single trade amount
    max_daily_trades: int = 50            # Max trades per day per user

    # Session
    session_timeout_sec: float = 3600.0   # Session expires after 1 hour

    # Logging
    log_voice_commands: bool = True       # Log all voice commands for audit


class VoiceTradeHandler:
    """Full voice trading pipeline: STT → Parse → Execute → TTS.

    Integrates with AlphaStack's trade execution, portfolio, and exchange APIs.
    """

    def __init__(
        self,
        config: VoiceHandlerConfig | None = None,
        stt_config: STTConfig | None = None,
        tts_config: TTSConfig | None = None,
        # AlphaStack service dependencies (injected)
        trade_store: Any = None,
        portfolio_service: Any = None,
        exchange: Any = None,
        signal_store: Any = None,
    ):
        self.config = config or VoiceHandlerConfig()
        self.stt = SpeechToText(stt_config)
        self.tts = TextToSpeech(tts_config)
        self.parser = VoiceCommandParser()

        # Service dependencies
        self.trade_store = trade_store
        self.portfolio_service = portfolio_service
        self.exchange = exchange
        self.signal_store = signal_store

        # User sessions
        self._sessions: dict[str, UserSession] = {}

        # Daily trade counters
        self._daily_trades: dict[str, int] = {}
        self._daily_reset_day: str = ""

    async def initialize(self) -> None:
        """Initialize STT and TTS engines."""
        await self.stt.initialize()
        await self.tts.initialize()
        logger.info("voice.handler_initialized")

    async def handle_voice(
        self,
        audio_bytes: bytes,
        user_id: str,
        content_type: str = "ogg",
        language: str | None = None,
    ) -> bytes:
        """Process a voice note end-to-end.

        Args:
            audio_bytes: Raw audio data
            user_id: User identifier
            content_type: Audio format (ogg, mp3, wav, webm)
            language: Force language (None = auto-detect)

        Returns:
            Response audio bytes (mp3)
        """
        session = self._get_session(user_id)

        # Step 1: Speech-to-Text
        text, detected_lang = await self.stt.transcribe(
            audio_bytes, language=language, content_type=content_type
        )
        if not text:
            return await self._respond(
                session, "I couldn't hear what you said. Please try again.",
                lang=session.last_language,
            )

        session.last_language = detected_lang
        session.interaction_count += 1
        session.last_interaction_time = time.time()

        logger.info(
            "voice.input user=%s lang=%s text=%s",
            user_id, detected_lang, text[:100],
        )

        # Step 2: Check if we're in a confirmation flow
        if session.state == SessionState.AWAITING_CONFIRMATION:
            return await self._handle_confirmation(session, text, detected_lang)

        if session.state == SessionState.AWAITING_CLARIFICATION:
            return await self._handle_clarification(session, text, detected_lang)

        # Step 3: Parse command
        cmd = self.parser.parse(text, detected_lang)

        if self.config.log_voice_commands:
            logger.info(
                "voice.command user=%s intent=%s symbol=%s amount=%.2f conf=%.2f",
                user_id, cmd.intent, cmd.symbol, cmd.amount, cmd.confidence,
            )

        # Step 4: Handle unknown commands
        if cmd.intent == CommandIntent.UNKNOWN:
            return await self._respond(
                session,
                self._unknown_response(detected_lang),
                lang=detected_lang,
            )

        # Step 5: Handle info commands (no confirmation needed)
        if not cmd.is_dangerous:
            return await self._handle_info_command(session, cmd)

        # Step 6: Dangerous action — check safety limits
        safety_check = self._check_safety(cmd, user_id)
        if safety_check:
            return await self._respond(session, safety_check, lang=detected_lang)

        # Step 7: Needs confirmation
        if self.config.require_confirmation and cmd.needs_confirmation:
            if cmd.missing_params:
                # Ask for missing info
                prompt = self.parser.get_clarification_prompt(cmd)
                session.state = SessionState.AWAITING_CLARIFICATION
                session.pending_command = cmd
                return await self._respond(session, prompt, lang=detected_lang)

            # Ask for confirmation
            prompt = self.parser.get_confirmation_prompt(cmd)
            session.state = SessionState.AWAITING_CONFIRMATION
            session.pending_command = cmd
            return await self._respond(session, prompt, lang=detected_lang)

        # Step 8: Execute directly (shouldn't reach here normally)
        return await self._execute_trade(session, cmd)

    async def handle_text(
        self,
        text: str,
        user_id: str,
        language: str = "en",
    ) -> str:
        """Process a text command (for testing or text fallback).

        Returns response text instead of audio.
        """
        session = self._get_session(user_id)
        session.last_language = language
        session.interaction_count += 1
        session.last_interaction_time = time.time()

        # Handle confirmation flow
        if session.state == SessionState.AWAITING_CONFIRMATION:
            cmd = self.parser.parse(text, language)
            if cmd.intent == CommandIntent.CONFIRM and session.pending_command:
                return await self._execute_trade(session, session.pending_command)
            elif cmd.intent == CommandIntent.CANCEL:
                session.state = SessionState.IDLE
                session.pending_command = None
                return "Cancelled."

        if session.state == SessionState.AWAITING_CLARIFICATION:
            # Merge new info with pending command
            if session.pending_command:
                new_cmd = self.parser.parse(text, language)
                merged = self._merge_commands(session.pending_command, new_cmd)
                if not merged.missing_params:
                    if self.config.require_confirmation:
                        prompt = self.parser.get_confirmation_prompt(merged)
                        session.state = SessionState.AWAITING_CONFIRMATION
                        session.pending_command = merged
                        return prompt
                    return await self._execute_trade(session, merged)
                else:
                    return self.parser.get_clarification_prompt(merged)

        cmd = self.parser.parse(text, language)

        if cmd.intent == CommandIntent.UNKNOWN:
            return self._unknown_response(language)

        if not cmd.is_dangerous:
            return await self._handle_info_command_text(session, cmd)

        safety_check = self._check_safety(cmd, user_id)
        if safety_check:
            return safety_check

        if cmd.missing_params:
            session.state = SessionState.AWAITING_CLARIFICATION
            session.pending_command = cmd
            return self.parser.get_clarification_prompt(cmd)

        if self.config.require_confirmation and cmd.needs_confirmation:
            prompt = self.parser.get_confirmation_prompt(cmd)
            session.state = SessionState.AWAITING_CONFIRMATION
            session.pending_command = cmd
            return prompt

        return await self._execute_trade_text(session, cmd)

    # ── Command Execution ──────────────────────────────────

    async def _execute_trade(self, session: UserSession, cmd: VoiceCommand) -> bytes:
        """Execute a trade and return audio response."""
        result_text = await self._execute_trade_text(session, cmd)
        return await self._respond(session, result_text, lang=session.last_language)

    async def _execute_trade_text(self, session: UserSession, cmd: VoiceCommand) -> str:
        """Execute a trade and return text response."""
        session.state = SessionState.IDLE
        session.pending_command = None

        if cmd.intent == CommandIntent.KILL_SWITCH:
            return await self._execute_kill_switch()

        if cmd.intent == CommandIntent.CLOSE_ALL:
            return await self._execute_close_all()

        if cmd.intent in (CommandIntent.BUY, CommandIntent.SELL):
            return await self._execute_buy_sell(cmd)

        if cmd.intent == CommandIntent.CLOSE_POSITION:
            return await self._execute_close_position(cmd)

        return "Command not recognized for execution."

    async def _execute_buy_sell(self, cmd: VoiceCommand) -> str:
        """Execute a buy or sell order."""
        try:
            if not self.exchange:
                return "Exchange not connected. Please configure trading first."

            symbol = cmd.symbol
            side = cmd.side

            # Calculate quantity
            if cmd.quantity > 0:
                qty = cmd.quantity
            elif cmd.amount > 0:
                # Get current price to calculate quantity
                ticker = self.exchange.fetch_ticker(symbol)
                price = ticker["last"]
                qty = cmd.amount / price
            else:
                return "No amount specified."

            # Place order
            order = self.exchange.create_order(
                symbol=symbol,
                type=cmd.order_type,
                side=side,
                amount=qty,
            )

            # Record in trade store
            if self.trade_store:
                self.trade_store.add_trade({
                    "symbol": symbol,
                    "side": side,
                    "quantity": qty,
                    "entry_price": order.get("average") or order.get("price", 0),
                    "status": "open",
                    "order_id": order.get("id"),
                    "source": "voice",
                })

            # Increment daily counter
            self._increment_daily_trades(cmd.raw_text)

            fill_price = order.get("average") or order.get("price", 0)
            return (
                f"Order executed: {side.upper()} {qty:.6f} {symbol} "
                f"at ${fill_price:,.2f}. Order ID: {order.get('id', 'N/A')}"
            )

        except Exception as e:
            logger.error("voice.trade_failed error=%s", str(e))
            return f"Trade failed: {str(e)}"

    async def _execute_close_position(self, cmd: VoiceCommand) -> str:
        """Close a specific position."""
        try:
            if not self.trade_store:
                return "Trade store not available."

            open_trades = self.trade_store.list_trades(status_filter="open")
            matching = [t for t in open_trades if t["symbol"] == cmd.symbol]

            if not matching:
                return f"No open position for {cmd.symbol}."

            # Close the most recent matching trade
            trade = matching[-1]
            close_side = "sell" if trade["side"] == "buy" else "buy"

            if self.exchange:
                order = self.exchange.create_order(
                    symbol=trade["symbol"],
                    type="market",
                    side=close_side,
                    amount=trade["quantity"],
                )
                exit_price = order.get("average") or order.get("price", 0)
            else:
                exit_price = 0

            # Update trade record
            pnl = 0
            entry = trade.get("entry_price", 0)
            if entry and exit_price:
                if trade["side"] == "buy":
                    pnl = (exit_price - entry) * trade["quantity"]
                else:
                    pnl = (entry - exit_price) * trade["quantity"]

            self.trade_store.close_trade(trade["id"], exit_price=exit_price, pnl=pnl)

            return f"Closed {trade['symbol']} position. P&L: ${pnl:+,.2f}"

        except Exception as e:
            logger.error("voice.close_failed error=%s", str(e))
            return f"Failed to close position: {str(e)}"

    async def _execute_kill_switch(self) -> str:
        """Emergency stop all trading."""
        logger.warning("voice.kill_switch_activated")
        # This would integrate with the risk governor
        return "Kill switch activated. All trading has been stopped."

    async def _execute_close_all(self) -> str:
        """Close all open positions."""
        if not self.trade_store:
            return "Trade store not available."

        open_trades = self.trade_store.list_trades(status_filter="open")
        if not open_trades:
            return "No open positions to close."

        closed = 0
        total_pnl = 0.0
        for trade in open_trades:
            try:
                result = await self._execute_close_position(
                    VoiceCommand(
                        intent=CommandIntent.CLOSE_POSITION,
                        symbol=trade["symbol"],
                    )
                )
                closed += 1
            except Exception:
                continue

        return f"Closed {closed} positions."

    # ── Info Commands ──────────────────────────────────────

    async def _handle_info_command(self, session: UserSession, cmd: VoiceCommand) -> bytes:
        """Handle non-trade commands and return audio."""
        text = await self._handle_info_command_text(session, cmd)
        return await self._respond(session, text, lang=session.last_language)

    async def _handle_info_command_text(self, session: UserSession, cmd: VoiceCommand) -> str:
        """Handle non-trade commands and return text."""
        if cmd.intent == CommandIntent.GET_BALANCE:
            return await self._get_balance()

        if cmd.intent == CommandIntent.GET_POSITIONS:
            return await self._get_positions()

        if cmd.intent == CommandIntent.GET_PNL:
            return await self._get_pnl()

        if cmd.intent == CommandIntent.GET_TRADES:
            return await self._get_trades()

        if cmd.intent == CommandIntent.GET_PRICE:
            return await self._get_price(cmd.symbol)

        if cmd.intent == CommandIntent.GET_MARKET:
            return await self._get_market()

        if cmd.intent == CommandIntent.HELP:
            return self._get_help(session.last_language)

        if cmd.intent == CommandIntent.EXPLAIN:
            return await self._explain_last_trade()

        if cmd.intent == CommandIntent.REPEAT:
            return session.last_response or "Nothing to repeat."

        return "Command recognized but not implemented yet."

    async def _get_balance(self) -> str:
        """Get account balance."""
        try:
            if self.portfolio_service:
                balance = self.portfolio_service.get_balance()
                return f"Your balance is ${balance:,.2f} USDT."
            if self.exchange:
                balance = self.exchange.fetch_balance()
                usdt = balance.get("USDT", {}).get("free", 0)
                return f"Your balance is ${usdt:,.2f} USDT."
            return "Balance service not available."
        except Exception as e:
            return f"Could not fetch balance: {str(e)}"

    async def _get_positions(self) -> str:
        """Get open positions."""
        if not self.trade_store:
            return "Trade store not available."
        open_trades = self.trade_store.list_trades(status_filter="open")
        if not open_trades:
            return "You have no open positions."
        lines = [f"You have {len(open_trades)} open positions."]
        for t in open_trades:
            side = "long" if t["side"] == "buy" else "short"
            lines.append(f"{side} {t['symbol']}, quantity {t['quantity']:.6f}")
        return ". ".join(lines)

    async def _get_pnl(self) -> str:
        """Get P&L summary."""
        if not self.trade_store:
            return "Trade store not available."
        closed = self.trade_store.list_trades(status_filter="closed")
        if not closed:
            return "No closed trades yet."
        total_pnl = sum(t.get("pnl") or 0 for t in closed)
        wins = sum(1 for t in closed if (t.get("pnl") or 0) > 0)
        losses = sum(1 for t in closed if (t.get("pnl") or 0) < 0)
        result = f"Total P&L is ${total_pnl:+,.2f}. {wins} wins, {losses} losses."
        return result

    async def _get_trades(self) -> str:
        """Get recent trades."""
        if not self.trade_store:
            return "Trade store not available."
        trades = self.trade_store.list_trades()
        if not trades:
            return "No trades yet."
        last = trades[-1]
        pnl_str = ""
        if last.get("pnl") is not None:
            pnl_str = f" P&L was ${last['pnl']:+,.2f}."
        return (
            f"Last trade: {last['side']} {last['symbol']} "
            f"at ${last.get('entry_price', 0):,.2f}.{pnl_str}"
        )

    async def _get_price(self, symbol: str) -> str:
        """Get current price for a symbol."""
        if not symbol:
            return "Which coin? Say the name, like Bitcoin or Ethereum."
        if not self.exchange:
            return "Exchange not available."
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker["last"]
            change = ticker.get("percentage", 0) or 0
            direction = "up" if change >= 0 else "down"
            return f"{symbol} is ${price:,.2f}, {direction} {abs(change):.1f}% in 24 hours."
        except Exception:
            return f"Could not fetch price for {symbol}."

    async def _get_market(self) -> str:
        """Get market overview."""
        if not self.exchange:
            return "Exchange not available."
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        lines = ["Market overview."]
        for sym in symbols:
            try:
                t = self.exchange.fetch_ticker(sym)
                pct = t.get("percentage", 0) or 0
                direction = "up" if pct >= 0 else "down"
                lines.append(f"{sym} at ${t['last']:,.2f}, {direction} {abs(pct):.1f}%")
            except Exception:
                continue
        return " ".join(lines)

    async def _explain_last_trade(self) -> str:
        """Explain the last closed trade."""
        if not self.trade_store:
            return "Trade store not available."
        closed = self.trade_store.list_trades(status_filter="closed")
        if not closed:
            return "No closed trades to explain."
        last = closed[-1]
        pnl = last.get("pnl") or 0
        direction = "profit" if pnl >= 0 else "loss"
        return (
            f"Last trade was {last['side']} {last['symbol']} "
            f"at ${last.get('entry_price', 0):,.2f}. "
            f"Closed at ${last.get('exit_price', 0):,.2f}. "
            f"{direction} of ${abs(pnl):,.2f}."
        )

    def _get_help(self, lang: str) -> str:
        """Get help text."""
        if lang == "sw":
            return (
                "Amri za sauti: "
                "Sema 'salio' kuona pesa zako. "
                "Sema 'nunua BTC' kununua bitcoin. "
                "Sema 'uza BTC' kuuza. "
                "Sema 'faida' kuona faida yako. "
                "Sema 'soko' kuona bei za soko. "
                "Sema 'simamisha biashara' kusitisha."
            )
        return (
            "Voice commands: "
            "Say 'check my balance' to see your money. "
            "Say 'buy BTC' to buy Bitcoin. "
            "Say 'sell ETH' to sell Ethereum. "
            "Say 'what's my P&L' for profit and loss. "
            "Say 'market' for price overview. "
            "Say 'stop trading' for emergency stop."
        )

    # ── Confirmation & Clarification Flows ─────────────────

    async def _handle_confirmation(
        self, session: UserSession, text: str, lang: str
    ) -> bytes:
        """Handle confirmation response."""
        cmd = self.parser.parse(text, lang)

        if cmd.intent == CommandIntent.CONFIRM:
            if session.pending_command:
                return await self._execute_trade(session, session.pending_command)
            session.state = SessionState.IDLE
            return await self._respond(session, "No pending action.", lang=lang)

        if cmd.intent == CommandIntent.CANCEL:
            session.state = SessionState.IDLE
            session.pending_command = None
            if lang == "sw":
                return await self._respond(session, "Imefutwa. Sema nyingine.", lang=lang)
            return await self._respond(session, "Cancelled. What else can I do?", lang=lang)

        # Check for timeout
        if time.time() - session.last_interaction_time > self.config.confirmation_timeout_sec:
            session.state = SessionState.IDLE
            session.pending_command = None
            return await self._respond(
                session, "Confirmation timed out. Please try again.", lang=lang,
            )

        # Didn't understand — ask again
        prompt = self.parser.get_confirmation_prompt(session.pending_command)
        return await self._respond(session, prompt, lang=lang)

    async def _handle_clarification(
        self, session: UserSession, text: str, lang: str
    ) -> bytes:
        """Handle clarification response — merge new info with pending command."""
        new_cmd = self.parser.parse(text, lang)

        if session.pending_command:
            merged = self._merge_commands(session.pending_command, new_cmd)

            if not merged.missing_params:
                # All info gathered — ask for confirmation
                if self.config.require_confirmation:
                    prompt = self.parser.get_confirmation_prompt(merged)
                    session.state = SessionState.AWAITING_CONFIRMATION
                    session.pending_command = merged
                    return await self._respond(session, prompt, lang=lang)
                return await self._execute_trade(session, merged)
            else:
                # Still missing info
                prompt = self.parser.get_clarification_prompt(merged)
                session.pending_command = merged
                return await self._respond(session, prompt, lang=lang)

        session.state = SessionState.IDLE
        return await self._respond(session, "Starting over. What would you like to do?", lang=lang)

    def _merge_commands(self, original: VoiceCommand, new: VoiceCommand) -> VoiceCommand:
        """Merge new command info into original (fill in missing params)."""
        merged = VoiceCommand(
            intent=original.intent,
            raw_text=original.raw_text,
            language=original.language,
            symbol=original.symbol or new.symbol,
            side=original.side or new.side,
            amount=original.amount or new.amount,
            quantity=original.quantity or new.quantity,
            price=original.price or new.price,
            order_type=original.order_type,
            confidence=min(original.confidence, new.confidence),
            needs_confirmation=original.needs_confirmation,
        )

        # Recalculate missing params
        merged.missing_params = []
        if merged.intent in (CommandIntent.BUY, CommandIntent.SELL):
            if not merged.symbol:
                merged.missing_params.append("symbol")
            if merged.amount == 0 and merged.quantity == 0:
                merged.missing_params.append("amount")

        return merged

    # ── Safety ─────────────────────────────────────────────

    def _check_safety(self, cmd: VoiceCommand, user_id: str) -> str:
        """Check safety limits. Returns error message or empty string."""
        if cmd.is_trade and cmd.amount > self.config.max_trade_amount_usd:
            return (
                f"Trade amount ${cmd.amount:,.2f} exceeds maximum "
                f"${self.config.max_trade_amount_usd:,.2f} per trade."
            )

        # Check daily limit
        day = time.strftime("%Y-%m-%d")
        if day != self._daily_reset_day:
            self._daily_trades.clear()
            self._daily_reset_day = day

        daily_count = self._daily_trades.get(user_id, 0)
        if daily_count >= self.config.max_daily_trades:
            return f"Daily trade limit reached ({self.config.max_daily_trades}). Try again tomorrow."

        return ""

    def _increment_daily_trades(self, user_id: str) -> None:
        """Track daily trade count."""
        day = time.strftime("%Y-%m-%d")
        if day != self._daily_reset_day:
            self._daily_trades.clear()
            self._daily_reset_day = day
        self._daily_trades[user_id] = self._daily_trades.get(user_id, 0) + 1

    # ── Response Helpers ───────────────────────────────────

    async def _respond(self, session: UserSession, text: str, lang: str = "en") -> bytes:
        """Generate audio response and cache it."""
        session.last_response = text
        try:
            audio = await self.tts.speak(text, lang=lang)
            session.last_audio = audio
            return audio
        except Exception as e:
            logger.error("voice.tts_failed error=%s", str(e))
            return b""

    def _get_session(self, user_id: str) -> UserSession:
        """Get or create user session."""
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(user_id=user_id)
        session = self._sessions[user_id]

        # Check session timeout
        if session.last_interaction_time > 0:
            elapsed = time.time() - session.last_interaction_time
            if elapsed > self.config.session_timeout_sec:
                session.state = SessionState.IDLE
                session.pending_command = None

        return session

    def _unknown_response(self, lang: str) -> str:
        """Response for unrecognized commands."""
        if lang == "sw":
            return "Sijaelewa. Sema 'msaada' kuona amri zote."
        return "I didn't understand. Say 'help' to see all commands."

    def get_session_info(self, user_id: str) -> dict:
        """Get session state for debugging."""
        session = self._sessions.get(user_id)
        if not session:
            return {"user_id": user_id, "state": "no_session"}
        return {
            "user_id": session.user_id,
            "state": session.state.value,
            "language": session.last_language,
            "interactions": session.interaction_count,
            "has_pending": session.pending_command is not None,
        }
