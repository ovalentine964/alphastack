"""
Speech-to-Text Engine for AlphaStack Voice Interface

Designed for Africa's informal trading environments:
  - Whisper (OpenAI) for English — high accuracy, robust
  - Qwen3 ASR for Swahili — native African language support
  - Noise reduction for market/street environments
  - Offline fallback with Vosk when internet is unavailable
  - Language auto-detection (English vs Swahili vs Sheng)

Usage:
    stt = SpeechToText()
    text, lang = await stt.transcribe(audio_bytes)
    text, lang = await stt.transcribe_file("voice_note.ogg")
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import struct
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("alphastack.voice.stt")


class STTBackend(str, Enum):
    WHISPER = "whisper"         # OpenAI Whisper API or local model
    QWEN3_ASR = "qwen3_asr"   # Qwen3 ASR for Swahili
    VOSK = "vosk"              # Offline fallback
    AUTO = "auto"              # Auto-select based on language


@dataclass
class STTConfig:
    """Configuration for speech-to-text engine."""
    # Primary backend
    backend: STTBackend = STTBackend.AUTO

    # Whisper settings
    whisper_model: str = "whisper-1"           # API model name
    whisper_local_model: str = "base"          # Local model size: tiny/base/small/medium/large
    whisper_api_key: str = ""                  # If empty, uses OPENAI_API_KEY env var
    whisper_use_local: bool = False            # Use local Whisper model vs API

    # Qwen3 ASR settings
    qwen3_endpoint: str = ""                   # Qwen3 ASR API endpoint
    qwen3_api_key: str = ""                    # Qwen3 API key
    qwen3_model: str = "qwen3-asr"            # Model identifier

    # Vosk offline settings
    vosk_model_path: str = ""                  # Path to Vosk model directory
    vosk_model_en: str = "vosk-model-small-en-us-0.15"
    vosk_model_sw: str = "vosk-model-small-sw-0.3"

    # Audio preprocessing
    sample_rate: int = 16000
    noise_reduction: bool = True               # Apply noise gate/reduction
    noise_gate_threshold: float = 0.015        # Amplitude threshold for noise gate
    normalize_audio: bool = True               # Normalize volume levels
    max_duration_sec: float = 60.0             # Max audio duration to process

    # Language detection
    default_language: str = "en"               # Default if detection fails
    supported_languages: list[str] = field(default_factory=lambda: ["en", "sw"])

    def __post_init__(self):
        if not self.whisper_api_key:
            self.whisper_api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.qwen3_api_key:
            self.qwen3_api_key = os.environ.get("QWEN3_API_KEY", "")
        if not self.qwen3_endpoint:
            self.qwen3_endpoint = os.environ.get("QWEN3_ASR_ENDPOINT", "")


class AudioPreprocessor:
    """Clean audio for better STT accuracy in noisy environments."""

    @staticmethod
    def reduce_noise(audio: np.ndarray, threshold: float = 0.015) -> np.ndarray:
        """Simple noise gate — zero out low-amplitude segments.

        For market environments with background chatter, horns, music.
        """
        # Calculate RMS in small windows
        window_size = 512
        output = audio.copy()
        for i in range(0, len(audio), window_size):
            window = audio[i : i + window_size]
            rms = np.sqrt(np.mean(window ** 2))
            if rms < threshold:
                output[i : i + window_size] = 0.0
        return output

    @staticmethod
    def normalize(audio: np.ndarray, target_db: float = -20.0) -> np.ndarray:
        """Normalize audio to target dB level."""
        if len(audio) == 0:
            return audio
        rms = np.sqrt(np.mean(audio ** 2))
        if rms == 0:
            return audio
        target_rms = 10 ** (target_db / 20)
        gain = target_rms / rms
        # Clip to prevent distortion
        return np.clip(audio * gain, -1.0, 1.0)

    @staticmethod
    def trim_silence(audio: np.ndarray, threshold: float = 0.01) -> np.ndarray:
        """Remove leading and trailing silence."""
        if len(audio) == 0:
            return audio
        # Find first non-silent sample
        non_silent = np.where(np.abs(audio) > threshold)[0]
        if len(non_silent) == 0:
            return audio[:0]  # All silence
        start = max(0, non_silent[0] - 800)  # Keep 50ms before speech
        end = min(len(audio), non_silent[-1] + 800)  # Keep 50ms after
        return audio[start:end]

    @classmethod
    def process(cls, audio: np.ndarray, config: STTConfig) -> np.ndarray:
        """Full preprocessing pipeline."""
        audio = cls.trim_silence(audio)
        if config.noise_reduction:
            audio = cls.reduce_noise(audio, config.noise_gate_threshold)
        if config.normalize_audio:
            audio = cls.normalize(audio)
        return audio


class LanguageDetector:
    """Detect language from audio features or text content."""

    # Swahili phonetic markers
    SWAHILI_MARKERS = [
        "habari", "nzuri", "sawa", "namba", "hesabu", "pesa", "nunua",
        "uza", "faida", "hasara", "soko", "biashara", "fedha", "shilingi",
        "m-pesa", "mpesa", "tsh", "kes", "ugx",
    ]

    # Sheng (Kenyan slang) markers
    SHENG_MARKERS = [
        "niaje", "sasa", "poa", "mbogi", "ndege", "ngovo", "doe",
        "ka-ching", "kuja", "wazi", "fiti", "mazishi",
    ]

    @classmethod
    def detect_from_text(cls, text: str) -> str:
        """Detect language from transcribed text."""
        lower = text.lower().strip()

        # Check Sheng first (subset of Swahili ecosystem)
        sheng_score = sum(1 for m in cls.SHENG_MARKERS if m in lower)
        if sheng_score >= 1:
            return "sheng"

        # Check Swahili
        sw_score = sum(1 for m in cls.SWAHILI_MARKERS if m in lower)
        if sw_score >= 1:
            return "sw"

        return "en"


class SpeechToText:
    """Multi-backend speech-to-text engine optimized for African trading.

    Usage:
        stt = SpeechToText()
        text, lang = await stt.transcribe(audio_bytes)
    """

    def __init__(self, config: STTConfig | None = None):
        self.config = config or STTConfig()
        self._preprocessor = AudioPreprocessor()
        self._whisper_client = None
        self._vosk_model = None
        self._vosk_available = False

    async def initialize(self) -> None:
        """Pre-load models for faster inference."""
        # Try loading Vosk for offline fallback
        try:
            from vosk import Model as VoskModel

            model_path = self.config.vosk_model_path
            if model_path and Path(model_path).exists():
                self._vosk_model = VoskModel(model_path)
                self._vosk_available = True
                logger.info("stt.vosk_loaded path=%s", model_path)
            else:
                logger.info("stt.vosk_not_found path=%s offline_fallback=disabled", model_path)
        except ImportError:
            logger.info("stt.vosk_not_installed offline_fallback=disabled")

        # Initialize Whisper client
        if self.config.whisper_api_key and not self.config.whisper_use_local:
            try:
                from openai import AsyncOpenAI

                self._whisper_client = AsyncOpenAI(api_key=self.config.whisper_api_key)
                logger.info("stt.whisper_api_ready")
            except ImportError:
                logger.warning("stt.openai_not_installed pip install openai")

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
        content_type: str = "ogg",
    ) -> tuple[str, str]:
        """Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio data (ogg, wav, mp3, webm)
            language: Force language (None = auto-detect)
            content_type: Audio format hint

        Returns:
            (transcribed_text, detected_language)
        """
        # Decode and preprocess audio
        audio_array = await self._decode_audio(audio_bytes, content_type)
        if audio_array is None or len(audio_array) == 0:
            return "", self.config.default_language

        # Truncate to max duration
        max_samples = int(self.config.max_duration_sec * self.config.sample_rate)
        if len(audio_array) > max_samples:
            audio_array = audio_array[:max_samples]
            logger.warning("stt.audio_truncated to %.1fs", self.config.max_duration_sec)

        # Preprocess (noise reduction, normalization)
        audio_array = self._preprocessor.process(audio_array, self.config)

        # Select backend
        backend = self._select_backend(language)

        # Transcribe
        text = ""
        detected_lang = language or self.config.default_language

        try:
            if backend == STTBackend.QWEN3_ASR:
                text, detected_lang = await self._transcribe_qwen3(audio_bytes, language)
            elif backend == STTBackend.WHISPER:
                text, detected_lang = await self._transcribe_whisper(audio_bytes, language, content_type)
            elif backend == STTBackend.VOSK:
                text, detected_lang = await self._transcribe_vosk(audio_array, language)
        except Exception as e:
            logger.error("stt.transcribe_failed backend=%s error=%s", backend, e)
            # Fallback chain: try Vosk if primary fails
            if backend != STTBackend.VOSK and self._vosk_available:
                try:
                    text, detected_lang = await self._transcribe_vosk(audio_array, language)
                    logger.info("stt.fallback_vosk_success")
                except Exception:
                    pass

        # Post-detection language refinement
        if text and not language:
            detected_lang = LanguageDetector.detect_from_text(text)

        logger.info(
            "stt.transcribed backend=%s lang=%s len=%d",
            backend, detected_lang, len(text),
        )
        return text.strip(), detected_lang

    async def transcribe_file(self, file_path: str, language: str | None = None) -> tuple[str, str]:
        """Transcribe an audio file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        suffix = path.suffix.lstrip(".").lower()
        content_type = {
            "ogg": "ogg", "oga": "ogg", "opus": "ogg",
            "mp3": "mp3", "m4a": "m4a", "wav": "wav",
            "webm": "webm", "flac": "flac",
        }.get(suffix, "ogg")

        audio_bytes = path.read_bytes()
        return await self.transcribe(audio_bytes, language, content_type)

    def _select_backend(self, language: str | None) -> STTBackend:
        """Select the best STT backend based on language and availability."""
        if self.config.backend != STTBackend.AUTO:
            return self.config.backend

        # Swahili/Sheng → prefer Qwen3 ASR
        if language in ("sw", "sheng"):
            if self.config.qwen3_endpoint and self.config.qwen3_api_key:
                return STTBackend.QWEN3_ASR
            # Fallback to Whisper (multilingual)
            if self.config.whisper_api_key:
                return STTBackend.WHISPER
            if self._vosk_available:
                return STTBackend.VOSK

        # English → prefer Whisper
        if self.config.whisper_api_key:
            return STTBackend.WHISPER
        if self._vosk_available:
            return STTBackend.VOSK

        # Last resort
        if self.config.qwen3_endpoint:
            return STTBackend.QWEN3_ASR

        logger.warning("stt.no_backend_available")
        return STTBackend.WHISPER  # Will fail with clear error

    async def _transcribe_whisper(
        self, audio_bytes: bytes, language: str | None, content_type: str
    ) -> tuple[str, str]:
        """Transcribe using OpenAI Whisper API."""
        if self.config.whisper_use_local:
            return await self._transcribe_whisper_local(audio_bytes, language)

        if not self._whisper_client:
            raise RuntimeError("Whisper client not initialized — set OPENAI_API_KEY")

        # Map content types to file extensions
        ext_map = {
            "ogg": "audio.ogg", "mp3": "audio.mp3", "wav": "audio.wav",
            "webm": "audio.webm", "m4a": "audio.m4a", "flac": "audio.flac",
        }
        filename = ext_map.get(content_type, "audio.ogg")

        # Create file-like object
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        # Call Whisper API
        response = await self._whisper_client.audio.transcriptions.create(
            model=self.config.whisper_model,
            file=audio_file,
            language=language if language and language != "sheng" else None,
            response_format="verbose_json",
        )

        text = response.text
        detected = getattr(response, "language", language or self.config.default_language)
        return text, detected

    async def _transcribe_whisper_local(
        self, audio_bytes: bytes, language: str | None
    ) -> tuple[str, str]:
        """Transcribe using local Whisper model (whisper-python)."""
        try:
            import whisper

            model = whisper.load_model(self.config.whisper_local_model)
            # Write to temp file for whisper
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                result = model.transcribe(
                    tmp_path,
                    language=language if language and language != "sheng" else None,
                    task="transcribe",
                )
                return result["text"], result.get("language", language or "en")
            finally:
                os.unlink(tmp_path)

        except ImportError:
            raise RuntimeError("Local Whisper requires: pip install openai-whisper")

    async def _transcribe_qwen3(
        self, audio_bytes: bytes, language: str | None
    ) -> tuple[str, str]:
        """Transcribe using Qwen3 ASR — optimized for Swahili."""
        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {self.config.qwen3_api_key}",
                "Content-Type": "application/octet-stream",
            }
            params = {
                "model": self.config.qwen3_model,
                "language": language or "sw",
                "format": "ogg",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.config.qwen3_endpoint,
                    headers=headers,
                    params=params,
                    content=audio_bytes,
                )
                response.raise_for_status()
                data = response.json()

            text = data.get("text", "")
            detected = data.get("language", language or "sw")
            return text, detected

        except ImportError:
            raise RuntimeError("Qwen3 ASR requires: pip install httpx")
        except httpx.HTTPStatusError as e:
            logger.error("qwen3_asr.http_error status=%d", e.response.status_code)
            raise

    async def _transcribe_vosk(
        self, audio_array: np.ndarray, language: str | None
    ) -> tuple[str, str]:
        """Transcribe using Vosk offline model."""
        if not self._vosk_available:
            raise RuntimeError("Vosk model not loaded")

        from vosk import KaldiRecognizer, Model

        rec = KaldiRecognizer(self._vosk_model, self.config.sample_rate)
        rec.SetWords(True)

        # Feed audio in chunks
        chunk_size = 4000
        audio_bytes = (audio_array * 32767).astype(np.int16).tobytes()

        results = []
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i : i + chunk_size]
            if rec.AcceptWaveform(chunk):
                result = rec.Result()
                results.append(result)

        # Get final result
        final = rec.FinalResult()
        results.append(final)

        # Parse results
        import json

        texts = []
        for r in results:
            try:
                d = json.loads(r)
                if d.get("text"):
                    texts.append(d["text"])
            except json.JSONDecodeError:
                continue

        full_text = " ".join(texts).strip()
        detected = LanguageDetector.detect_from_text(full_text) if full_text else language or "en"
        return full_text, detected

    async def _decode_audio(self, audio_bytes: bytes, content_type: str) -> np.ndarray | None:
        """Decode audio bytes to float32 numpy array at target sample rate."""
        try:
            import io

            # Try pydub first (supports many formats)
            from pydub import AudioSegment

            audio_file = io.BytesIO(audio_bytes)

            format_map = {
                "ogg": "ogg", "mp3": "mp3", "wav": "wav",
                "webm": "webm", "m4a": "m4a", "flac": "flac",
            }
            fmt = format_map.get(content_type, "ogg")

            segment = AudioSegment.from_file(audio_file, format=fmt)

            # Convert to mono, target sample rate
            segment = segment.set_channels(1).set_frame_rate(self.config.sample_rate)

            # Convert to float32 numpy array
            samples = np.array(segment.get_array_of_samples(), dtype=np.float32)
            samples /= 32768.0  # Normalize to [-1, 1]
            return samples

        except ImportError:
            logger.warning("stt.pydub_not_installed pip install pydub")

        # Fallback: try raw PCM (assumes 16-bit signed, target sample rate)
        if content_type == "wav":
            try:
                import wave

                with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                    frames = wf.readframes(wf.getnframes())
                    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
                    samples /= 32768.0
                    # Resample if needed
                    if wf.getframerate() != self.config.sample_rate:
                        ratio = self.config.sample_rate / wf.getframerate()
                        new_len = int(len(samples) * ratio)
                        indices = np.linspace(0, len(samples) - 1, new_len)
                        samples = np.interp(indices, np.arange(len(samples)), samples)
                    return samples
            except Exception:
                pass

        logger.error("stt.decode_failed content_type=%s — install pydub", content_type)
        return None
