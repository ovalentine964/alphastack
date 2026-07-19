"""
AlphaStack Voice Interface — Voice-First Trading for Africa

Provides speech-to-text, text-to-speech, voice command parsing,
and a unified voice trade handler optimized for:
  - African informal economy users (low literacy, voice-first)
  - Market environments (background noise handling)
  - Multilingual support (English, Swahili, Sheng slang)
  - Offline resilience (cached models, fallback prompts)

Architecture:
  STT (stt.py)  →  Command Parser (commands.py)  →  Trade Handler (handler.py)  →  TTS (tts.py)
     ↑                                                   ↓
  Audio Input                                    Audio Response
"""

from alphastack.voice.stt import SpeechToText, STTConfig
from alphastack.voice.tts import TextToSpeech, TTSConfig
from alphastack.voice.commands import VoiceCommandParser, VoiceCommand, CommandIntent
from alphastack.voice.handler import VoiceTradeHandler, VoiceHandlerConfig

__all__ = [
    "SpeechToText",
    "STTConfig",
    "TextToSpeech",
    "TTSConfig",
    "VoiceCommandParser",
    "VoiceCommand",
    "CommandIntent",
    "VoiceTradeHandler",
    "VoiceHandlerConfig",
]
