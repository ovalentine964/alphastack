"""
Voice Command Parser for AlphaStack Voice Interface

Parses natural language voice commands into structured trading intents.
Supports English, Swahili, and Sheng (Kenyan slang).

Designed for Africa's informal economy:
  - Handles imprecise speech ("buy some bitcoin")
  - Understands colloquial amounts ("niaje ka-100" = buy 100 USDT worth)
  - Maps fuzzy commands to precise actions
  - Safety confirmations for high-risk actions

Command Categories:
  - Portfolio: balance, positions, P&L
  - Trading: buy, sell, close
  - Market: prices, trends
  - Control: stop, pause, resume
  - Info: help, explain

Usage:
    parser = VoiceCommandParser()
    cmd = parser.parse("buy BTC worth 100 dollars")
    # → VoiceCommand(intent=BUY, symbol="BTC/USDT", amount=100)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CommandIntent(str, Enum):
    """What the user wants to do."""
    # Portfolio
    GET_BALANCE = "get_balance"
    GET_POSITIONS = "get_positions"
    GET_PNL = "get_pnl"
    GET_TRADES = "get_trades"

    # Trading
    BUY = "buy"
    SELL = "sell"
    CLOSE_POSITION = "close_position"
    CLOSE_ALL = "close_all"

    # Market
    GET_PRICE = "get_price"
    GET_MARKET = "get_market"

    # Control
    KILL_SWITCH = "kill_switch"
    PAUSE_TRADING = "pause_trading"
    RESUME_TRADING = "resume_trading"

    # Info
    HELP = "help"
    EXPLAIN = "explain"
    REPEAT = "repeat"

    # Confirmation responses
    CONFIRM = "confirm"
    CANCEL = "cancel"

    # Unrecognized
    UNKNOWN = "unknown"


# Symbol aliases — how users actually talk about crypto
SYMBOL_ALIASES = {
    # Bitcoin
    "btc": "BTC/USDT",
    "bitcoin": "BTC/USDT",
    "btc/usdt": "BTC/USDT",
    "btc dollar": "BTC/USDT",
    "mchele": "BTC/USDT",       # Swahili slang: "rice" (looks like rice grains on chart)
    "bitcoinu": "BTC/USDT",     # Sheng pronunciation

    # Ethereum
    "eth": "ETH/USDT",
    "ethereum": "ETH/USDT",
    "ether": "ETH/USDT",
    "eth/usdt": "ETH/USDT",

    # Solana
    "sol": "SOL/USDT",
    "solana": "SOL/USDT",
    "sol/usdt": "SOL/USDT",

    # BNB
    "bnb": "BNB/USDT",
    "binance": "BNB/USDT",
    "bnb/usdt": "BNB/USDT",

    # XRP
    "xrp": "XRP/USDT",
    "ripple": "XRP/USDT",
    "xrp/usdt": "XRP/USDT",

    # Dogecoin
    "doge": "DOGE/USDT",
    "dogecoin": "DOGE/USDT",
    "doge/usdt": "DOGE/USDT",

    # Cardano
    "ada": "ADA/USDT",
    "cardano": "ADA/USDT",
    "ada/usdt": "ADA/USDT",

    # M-Pesa related (forex)
    "dollar": "USD/KES",
    "dollars": "USD/KES",
    "peso": "USD/KES",
}


@dataclass
class VoiceCommand:
    """Parsed voice command ready for execution."""
    intent: CommandIntent
    raw_text: str = ""
    language: str = "en"

    # Trading parameters
    symbol: str = ""           # e.g., "BTC/USDT"
    side: str = ""             # "buy" or "sell"
    amount: float = 0.0        # Amount in quote currency (USDT)
    quantity: float = 0.0      # Amount in base currency (BTC)
    price: float = 0.0         # Specific price (limit order)
    order_type: str = "market" # "market" or "limit"

    # Metadata
    confidence: float = 0.0    # 0-1, how confident we are in the parse
    needs_confirmation: bool = False  # High-risk actions need voice confirmation
    missing_params: list[str] = field(default_factory=list)

    @property
    def is_trade(self) -> bool:
        return self.intent in (CommandIntent.BUY, CommandIntent.SELL)

    @property
    def is_dangerous(self) -> bool:
        """Actions that can lose money or halt trading."""
        return self.intent in (
            CommandIntent.BUY, CommandIntent.SELL,
            CommandIntent.CLOSE_ALL, CommandIntent.KILL_SWITCH,
        )


class VoiceCommandParser:
    """Parse natural language voice commands into structured intents.

    Handles:
      - English: "Buy BTC for $100"
      - Swahili: "Nunua BTC kwa dola 100"
      - Sheng: "Nunua bitcoinu ka-100"
      - Imprecise: "get me some bitcoin"
      - Colloquial: "what's my money looking like"
    """

    # Intent patterns — ordered by specificity (most specific first)
    INTENT_PATTERNS: list[tuple[str, CommandIntent, float]] = [
        # === KILL SWITCH / EMERGENCY (must precede cancel — both have "stop") ===
        (r"\b(stop\s*(all\s*)?trading|kill\s*switch|emergency\s*stop|simamisha\s*biashara|funga\s*biashara\s*zote)\b",
         CommandIntent.KILL_SWITCH, 0.95),
        (r"\b(pause\s*trading|pause|simamisha)\b", CommandIntent.PAUSE_TRADING, 0.85),
        (r"\b(resume|continue|endelea|anza\s*tena)\b", CommandIntent.RESUME_TRADING, 0.85),

        # === CONFIRMATION / CANCEL ===
        (r"\b(yes|confirm|do it|sawa|ndiyo|nenda)\b(?!\s*(long|short))", CommandIntent.CONFIRM, 0.95),
        (r"\b(no|cancel|hapana|sitisha|usifanye)\b", CommandIntent.CANCEL, 0.95),



        # === PORTFOLIO ===
        (r"\b(balance|how\s*much|account|salio|hesabu\s*yangu|pesa\s*zangu|doo\s*yangu)\b",
         CommandIntent.GET_BALANCE, 0.9),
        # close_all must precede get_positions (both match "positions")
        (r"\b(close\s*all|close\s*everything|funga\s*zote|close\s*positions?)\b",
         CommandIntent.CLOSE_ALL, 0.9),
        (r"\b(positions?|open\s*(trades?|positions?)|mafunguo|nini\s*imefunguliwa)\b",
         CommandIntent.GET_POSITIONS, 0.9),
        (r"\b(p\s*&?\s*l|profit|loss|pnl|faida|hasara|faida\s*yangu|ninapata\s*nn)\b",
         CommandIntent.GET_PNL, 0.9),
        (r"\b(trades?|history|trade\s*history|historia)\b", CommandIntent.GET_TRADES, 0.85),

        # === TRADING — BUY ===
        (r"\b(buy|purchase|nunua|acquire)\b", CommandIntent.BUY, 0.9),
        (r"\b(get\s*me)\b", CommandIntent.BUY, 0.85),
        (r"\b(go\s*long|long|ingia\s*kwa\s*buy)\b", CommandIntent.BUY, 0.9),

        # === TRADING — SELL ===
        (r"\b(sell|dispose|uza|cash\s*out|liquidate)\b", CommandIntent.SELL, 0.9),
        (r"\b(short|go\s*short|ingia\s*kwa\s*sell)\b", CommandIntent.SELL, 0.85),

        # === CLOSE (close_all already above) ===
        (r"\b(close|exit|funga|toka)\b", CommandIntent.CLOSE_POSITION, 0.8),

        # === MARKET (market must precede price — "soko gani" should be market, not price) ===
        (r"\b(market|soko|trend|soko\s*gani)\b", CommandIntent.GET_MARKET, 0.85),
        (r"\b(price|bei|gani|how\s*much\s*is|bei\s*ya)\b", CommandIntent.GET_PRICE, 0.85),

        # === INFO ===
        (r"\b(help|msaada|nifanye\s*nini|commands?)\b", CommandIntent.HELP, 0.9),
        (r"\b(explain|eleza|why|kwa\s*nini)\b", CommandIntent.EXPLAIN, 0.85),
        (r"\b(repeat|rudia|say\s*again|sikia\s*tena)\b", CommandIntent.REPEAT, 0.9),
    ]

    # Amount patterns — extract numbers from speech
    AMOUNT_PATTERNS = [
        # "100 dollars", "$100", "dola 100"
        r"(?:dollar[s]?|dola[s]?|\$|USD|USDT|pesa)\s*(\d[\d,]*\.?\d*)",
        r"(\d[\d,]*\.?\d*)\s*(?:dollar[s]?|dola[s]?|\$|USD|USDT)",
        # "ka-100" (Sheng for "about 100")
        r"ka-?(\d[\d,]*\.?\d*)",
        # Plain numbers near buy/sell context
        r"(?:for|worth|kwa|bei\s*ya)\s*(\d[\d,]*\.?\d*)",
        r"(\d[\d,]*\.?\d*)\s*(?:worth|only)",
    ]

    # Quantity patterns — "0.5 BTC", "bitcoin 0.5"
    QUANTITY_PATTERNS = [
        r"(\d[\d,]*\.?\d*)\s*(?:btc|eth|sol|bnb|xrp|doge|ada)",
        r"(?:btc|eth|sol|bnb|xrp|doge|ada)\s*(\d[\d,]*\.?\d*)",
    ]

    def parse(self, text: str, language: str = "en") -> VoiceCommand:
        """Parse voice text into a structured command.

        Args:
            text: Transcribed voice text
            language: Detected language (en, sw, sheng)

        Returns:
            VoiceCommand with intent and parameters extracted
        """
        cleaned = self._clean_text(text)
        if not cleaned:
            return VoiceCommand(
                intent=CommandIntent.UNKNOWN,
                raw_text=text,
                language=language,
                confidence=0.0,
            )

        # Detect intent
        intent, confidence = self._detect_intent(cleaned)

        # Extract symbol
        symbol = self._extract_symbol(cleaned)

        # Extract amounts
        amount = self._extract_amount(cleaned)
        quantity = self._extract_quantity(cleaned)

        # Determine side for close_position
        side = ""
        if intent in (CommandIntent.BUY, CommandIntent.SELL):
            side = "buy" if intent == CommandIntent.BUY else "sell"

        # Build command
        cmd = VoiceCommand(
            intent=intent,
            raw_text=text,
            language=language,
            symbol=symbol,
            side=side,
            amount=amount,
            quantity=quantity,
            confidence=confidence,
        )

        # Set confirmation requirements
        if cmd.is_dangerous:
            cmd.needs_confirmation = True

        # Check for missing params
        if intent in (CommandIntent.BUY, CommandIntent.SELL):
            if not symbol:
                cmd.missing_params.append("symbol")
            if amount == 0 and quantity == 0:
                cmd.missing_params.append("amount")

        if intent == CommandIntent.GET_PRICE and not symbol:
            cmd.missing_params.append("symbol")

        if intent == CommandIntent.CLOSE_POSITION and not symbol:
            cmd.missing_params.append("symbol")

        return cmd

    def _clean_text(self, text: str) -> str:
        """Normalize text for parsing."""
        text = text.lower().strip()
        # Remove filler words
        fillers = ["um", "uh", "like", "you know", "basically", "so", "na", "ya", "ee"]
        for filler in fillers:
            text = re.sub(rf"\b{filler}\b", " ", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _detect_intent(self, text: str) -> tuple[CommandIntent, float]:
        """Match text against intent patterns."""
        best_intent = CommandIntent.UNKNOWN
        best_confidence = 0.0

        for pattern, intent, confidence in self.INTENT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                if confidence > best_confidence:
                    best_intent = intent
                    best_confidence = confidence

        # Contextual boost: if we see buy/sell with a symbol, boost confidence
        if best_intent in (CommandIntent.BUY, CommandIntent.SELL):
            symbol = self._extract_symbol(text)
            if symbol:
                best_confidence = min(1.0, best_confidence + 0.05)

        return best_intent, best_confidence

    def _extract_symbol(self, text: str) -> str:
        """Extract trading symbol from text."""
        text_lower = text.lower()

        # Try each alias (longest match first to avoid partial matches)
        sorted_aliases = sorted(SYMBOL_ALIASES.keys(), key=len, reverse=True)
        for alias in sorted_aliases:
            # Word boundary match
            if re.search(rf"\b{re.escape(alias)}\b", text_lower):
                return SYMBOL_ALIASES[alias]

        # Try direct symbol patterns like "BTC/USDT"
        match = re.search(r"\b([A-Z]{2,5})/([A-Z]{2,5})\b", text.upper())
        if match:
            return f"{match.group(1)}/{match.group(2)}"

        return ""

    def _extract_amount(self, text: str) -> float:
        """Extract monetary amount from text."""
        for pattern in self.AMOUNT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        return 0.0

    def _extract_quantity(self, text: str) -> float:
        """Extract base asset quantity from text."""
        for pattern in self.QUANTITY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                qty_str = match.group(1).replace(",", "")
                try:
                    return float(qty_str)
                except ValueError:
                    continue
        return 0.0

    def get_confirmation_prompt(self, cmd: VoiceCommand) -> str:
        """Generate a confirmation prompt for dangerous actions.

        Returns text that should be spoken back to the user for confirmation.
        """
        if cmd.intent == CommandIntent.KILL_SWITCH:
            return (
                "Warning: This will stop all trading immediately. "
                "Say 'confirm' to proceed or 'cancel' to abort."
            )

        if cmd.intent == CommandIntent.CLOSE_ALL:
            return (
                "Warning: This will close ALL open positions. "
                "Say 'confirm' to proceed or 'cancel' to abort."
            )

        if cmd.is_trade:
            side_word = "Buy" if cmd.side == "buy" else "Sell"
            symbol = cmd.symbol or "unknown"
            if cmd.amount > 0:
                return (
                    f"Confirming {side_word} {symbol} for ${cmd.amount:,.2f}. "
                    f"Say 'confirm' to execute or 'cancel' to abort."
                )
            elif cmd.quantity > 0:
                return (
                    f"Confirming {side_word} {cmd.quantity} {symbol}. "
                    f"Say 'confirm' to execute or 'cancel' to abort."
                )

        return "Please confirm this action. Say 'confirm' or 'cancel'."

    def get_clarification_prompt(self, cmd: VoiceCommand) -> str:
        """Generate a clarification prompt when params are missing."""
        prompts = []

        if "symbol" in cmd.missing_params:
            if cmd.language == "sw":
                prompts.append("Unataka kununua au kuuza coin gani?")
            else:
                prompts.append("Which coin do you want to trade?")

        if "amount" in cmd.missing_params:
            if cmd.language == "sw":
                prompts.append("Kiasi gani? Ni pesa ngapi?")
            else:
                prompts.append("How much? What amount in dollars?")

        return " ".join(prompts) if prompts else ""
