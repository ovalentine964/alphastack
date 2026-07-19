"""
Text-to-Speech Engine for AlphaStack Voice Interface

Voice readback for trading confirmations, P&L announcements, and alerts.
Optimized for African users:
  - Swahili TTS via edge-tts (free, no API key needed)
  - English TTS via edge-tts or OpenAI
  - Trade confirmation readback: "Ununua BTC kwa dola 45,000"
  - P&L announcements: "Faida yako ni dola 250"
  - Market alerts with urgency tones

Usage:
    tts = TextToSpeech()
    audio_bytes = await tts.speak("Trade confirmed: bought BTC at $45,000", lang="en")
    audio_bytes = await tts.speak_trade_confirmation(symbol="BTC", side="buy", price=45000)
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("alphastack.voice.tts")


class TTSBackend(str, Enum):
    EDGE_TTS = "edge_tts"     # Microsoft Edge TTS (free, good quality)
    OPENAI = "openai"          # OpenAI TTS (high quality, costs money)
    PYTTSX3 = "pyttsx3"        # Offline fallback (lower quality)
    AUTO = "auto"


# Voice presets for African languages
VOICE_PRESETS = {
    "en": {
        "female": "en-KE-ZuriNeural",      # Kenyan English female
        "male": "en-KE-ChilembaNeural",     # Kenyan English male
        "default": "en-KE-ZuriNeural",
    },
    "sw": {
        "female": "sw-KE-ZuriNeural",      # Swahili female
        "male": "sw-KE-ChilembaNeural",     # Swahili male
        "default": "sw-KE-ZuriNeural",
    },
    "en-us": {
        "female": "en-US-JennyNeural",
        "male": "en-US-GuyNeural",
        "default": "en-US-JennyNeural",
    },
}


@dataclass
class TTSConfig:
    """Configuration for text-to-speech engine."""
    backend: TTSBackend = TTSBackend.AUTO
    default_language: str = "en"
    default_voice_gender: str = "female"    # "male" or "female"

    # edge-tts settings
    edge_voice_map: dict[str, str] = field(default_factory=lambda: {
        "en": "en-KE-ZuriNeural",
        "sw": "sw-KE-ZuriNeural",
        "sheng": "sw-KE-ZuriNeural",  # Sheng uses Swahili voice
    })
    edge_rate: str = "+0%"                  # Speech rate adjustment
    edge_pitch: str = "+0Hz"               # Pitch adjustment

    # OpenAI TTS settings
    openai_api_key: str = ""
    openai_model: str = "tts-1"
    openai_voice: str = "nova"             # alloy, echo, fable, onyx, nova, shimmer

    # Output format
    output_format: str = "mp3"              # mp3, wav, ogg
    sample_rate: int = 24000

    # Trade-specific speech patterns
    slow_rate_for_numbers: str = "-15%"     # Slow down for prices/numbers
    emphasis_rate: str = "-10%"             # Slightly slower for confirmations

    def __post_init__(self):
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")


class TextToSpeech:
    """Multi-backend TTS engine with trade-specific speech patterns.

    Usage:
        tts = TextToSpeech()
        audio = await tts.speak("Balance: $1,250", lang="en")
    """

    def __init__(self, config: TTSConfig | None = None):
        self.config = config or TTSConfig()
        self._edge_voices_loaded = False

    async def initialize(self) -> None:
        """Pre-load TTS engine."""
        if self.config.backend in (TTSBackend.AUTO, TTSBackend.EDGE_TTS):
            try:
                import edge_tts
                self._edge_voices_loaded = True
                logger.info("tts.edge_tts_ready")
            except ImportError:
                logger.warning("tts.edge_tts_not_installed pip install edge-tts")

    async def speak(
        self,
        text: str,
        lang: str | None = None,
        voice_gender: str | None = None,
        rate: str | None = None,
    ) -> bytes:
        """Convert text to speech audio.

        Args:
            text: Text to speak
            lang: Language code (en, sw, sheng)
            voice_gender: "male" or "female"
            rate: Speech rate override

        Returns:
            Audio bytes in configured format (mp3/wav/ogg)
        """
        lang = lang or self.config.default_language
        gender = voice_gender or self.config.default_voice_gender
        rate = rate or self.config.edge_rate

        backend = self._select_backend(lang)

        try:
            if backend == TTSBackend.EDGE_TTS:
                return await self._speak_edge_tts(text, lang, gender, rate)
            elif backend == TTSBackend.OPENAI:
                return await self._speak_openai(text, lang)
            elif backend == TTSBackend.PYTTSX3:
                return await self._speak_pyttsx3(text, lang)
        except Exception as e:
            logger.error("tts.speak_failed backend=%s error=%s", backend, e)
            # Fallback chain
            if backend != TTSBackend.EDGE_TTS and self._edge_voices_loaded:
                return await self._speak_edge_tts(text, lang, gender, rate)

        raise RuntimeError(f"TTS failed — no backend available for lang={lang}")

    async def speak_trade_confirmation(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: float = 0,
        lang: str = "en",
    ) -> bytes:
        """Speak a trade confirmation with appropriate pacing.

        Numbers are spoken slower for clarity.
        """
        if lang == "sw":
            side_word = "Nunua" if side.lower() == "buy" else "Uza"
            if quantity > 0:
                text = f"{side_word} {symbol} bei dola {price:,.0f}, kiasi {quantity:.6f}"
            else:
                text = f"{side_word} {symbol} bei dola {price:,.0f}"
        elif lang == "sheng":
            side_word = "Nunua" if side.lower() == "buy" else "Uza"
            text = f"{side_word} {symbol} bei {price:,.0f} doo"
        else:
            side_word = "Buy" if side.lower() == "buy" else "Sell"
            if quantity > 0:
                text = f"Confirming {side_word} {symbol} at ${price:,.2f}, quantity {quantity:.6f}"
            else:
                text = f"Confirming {side_word} {symbol} at ${price:,.2f}"

        return await self.speak(text, lang=lang, rate=self.config.emphasis_rate)

    async def speak_pnl(
        self,
        pnl: float,
        pnl_pct: float = 0,
        symbol: str = "",
        lang: str = "en",
    ) -> bytes:
        """Speak P&L announcement with emotional tone.

        Positive P&L: confident/celebratory
        Negative P&L: serious/cautionary
        """
        if lang == "sw":
            if pnl >= 0:
                text = f"Faida yako ni dola {pnl:,.0f}"
                if symbol:
                    text += f" kwenye {symbol}"
            else:
                text = f"Hasara ni dola {abs(pnl):,.0f}"
                if symbol:
                    text += f" kwenye {symbol}"
        else:
            if pnl >= 0:
                text = f"Profit is ${pnl:,.2f}"
                if pnl_pct:
                    text += f", up {pnl_pct:.1f} percent"
                if symbol:
                    text += f" on {symbol}"
            else:
                text = f"Loss is ${abs(pnl):,.2f}"
                if pnl_pct:
                    text += f", down {abs(pnl_pct):.1f} percent"
                if symbol:
                    text += f" on {symbol}"

        # Slower for numbers, slightly different rate for profit vs loss
        rate = self.config.slow_rate_for_numbers
        return await self.speak(text, lang=lang, rate=rate)

    async def speak_balance(self, balance: float, currency: str = "USD", lang: str = "en") -> bytes:
        """Speak account balance."""
        if lang == "sw":
            text = f"Salio lako ni dola {balance:,.0f}"
        else:
            text = f"Your balance is ${balance:,.2f} {currency}"

        return await self.speak(text, lang=lang, rate=self.config.slow_rate_for_numbers)

    async def speak_alert(
        self,
        message: str,
        urgency: str = "normal",
        lang: str = "en",
    ) -> bytes:
        """Speak a market or risk alert.

        urgency: "normal", "high", "critical"
        """
        rate = self.config.edge_rate
        if urgency == "high":
            rate = "-5%"  # Slightly slower, more deliberate
        elif urgency == "critical":
            rate = "-10%"  # Even slower for critical alerts

        prefix = ""
        if lang == "sw":
            if urgency == "critical":
                prefix = "Onyo! "
            elif urgency == "high":
                prefix = "Angalia! "
        else:
            if urgency == "critical":
                prefix = "Critical alert! "
            elif urgency == "high":
                prefix = "Warning! "

        return await self.speak(prefix + message, lang=lang, rate=rate)

    def _select_backend(self, lang: str) -> TTSBackend:
        """Select best TTS backend for language."""
        if self.config.backend != TTSBackend.AUTO:
            return self.config.backend

        # edge-tts supports Swahili and English well
        if self._edge_voices_loaded:
            return TTSBackend.EDGE_TTS

        if self.config.openai_api_key:
            return TTSBackend.OPENAI

        return TTSBackend.PYTTSX3

    def _get_voice(self, lang: str, gender: str) -> str:
        """Get the best voice ID for language and gender."""
        # Check custom voice map first
        voice = self.config.edge_voice_map.get(lang)
        if voice:
            return voice

        # Check presets
        presets = VOICE_PRESETS.get(lang, VOICE_PRESETS["en"])
        return presets.get(gender, presets["default"])

    async def _speak_edge_tts(
        self, text: str, lang: str, gender: str, rate: str
    ) -> bytes:
        """Generate speech using edge-tts (free Microsoft TTS)."""
        import edge_tts

        voice = self._get_voice(lang, gender)

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=self.config.edge_pitch,
        )

        # Collect audio chunks
        audio_data = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.write(chunk["data"])

        audio_bytes = audio_data.getvalue()
        if not audio_bytes:
            raise RuntimeError(f"edge-tts returned empty audio for voice={voice}")

        logger.info(
            "tts.edge_tts_generated voice=%s lang=%s bytes=%d",
            voice, lang, len(audio_bytes),
        )
        return audio_bytes

    async def _speak_openai(self, text: str, lang: str) -> bytes:
        """Generate speech using OpenAI TTS API."""
        if not self.config.openai_api_key:
            raise RuntimeError("OpenAI API key not set")

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.config.openai_api_key)

        response = await client.audio.speech.create(
            model=self.config.openai_model,
            voice=self.config.openai_voice,
            input=text,
            response_format=self.config.output_format,
        )

        audio_bytes = response.content
        logger.info("tts.openai_generated bytes=%d", len(audio_bytes))
        return audio_bytes

    async def _speak_pyttsx3(self, text: str, lang: str) -> bytes:
        """Offline TTS using pyttsx3 (system voices)."""
        try:
            import pyttsx3
        except ImportError:
            raise RuntimeError("pyttsx3 not installed: pip install pyttsx3")

        engine = pyttsx3.init()
        engine.setProperty("rate", 150)

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            audio_bytes = Path(tmp_path).read_bytes()
            return audio_bytes
        finally:
            os.unlink(tmp_path)
