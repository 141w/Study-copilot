"""
Text-to-Speech module using Edge TTS (free, no API key needed).

Provides a TTS provider abstraction and an EdgeTTS implementation.
"""

import abc
import logging
import os
import uuid

import edge_tts

from app.config import settings

logger = logging.getLogger(__name__)

# TODO: Add periodic cleanup of generated mp3 files (older than 24h)
# TTS output directory
TTS_DIR = os.path.join(settings.upload_dir, "tts")

# Pre-defined voices for Chinese and English
VOICES = {
    "zh-CN": [
        {
            "id": "zh-CN-XiaoxiaoNeural",
            "name": "晓晓 (女)",
            "language": "zh-CN",
            "gender": "Female",
        },
        {"id": "zh-CN-YunxiNeural", "name": "云希 (男)", "language": "zh-CN", "gender": "Male"},
        {"id": "zh-CN-YunjianNeural", "name": "云健 (男)", "language": "zh-CN", "gender": "Male"},
        {"id": "zh-CN-XiaoyiNeural", "name": "晓伊 (女)", "language": "zh-CN", "gender": "Female"},
        {
            "id": "zh-CN-liaoning-XiaobeiNeural",
            "name": "晓北 (女·辽宁)",
            "language": "zh-CN",
            "gender": "Female",
        },
    ],
    "en-US": [
        {
            "id": "en-US-JennyNeural",
            "name": "Jenny (Female)",
            "language": "en-US",
            "gender": "Female",
        },
        {"id": "en-US-GuyNeural", "name": "Guy (Male)", "language": "en-US", "gender": "Male"},
        {
            "id": "en-US-AriaNeural",
            "name": "Aria (Female)",
            "language": "en-US",
            "gender": "Female",
        },
        {"id": "en-US-DavisNeural", "name": "Davis (Male)", "language": "en-US", "gender": "Male"},
    ],
}

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


class TTSProvider(abc.ABC):
    """Abstract TTS provider interface."""

    @abc.abstractmethod
    async def generate_speech(self, text: str, voice: str | None = None, speed: float = 1.0) -> str:
        """Generate speech audio from text. Returns the file path of the audio."""
        ...

    @abc.abstractmethod
    def get_voices(self) -> dict[str, list[dict]]:
        """Return available voices grouped by language."""
        ...


class EdgeTTSProvider(TTSProvider):
    """Edge TTS provider — free Microsoft Edge neural voices."""

    async def generate_speech(self, text: str, voice: str | None = None, speed: float = 1.0) -> str:
        """
        Generate speech audio from text.

        Args:
            text: The text to convert to speech.
            voice: Edge TTS voice ID (e.g., 'zh-CN-XiaoxiaoNeural').
            speed: Playback speed (0.5 ~ 2.0). 1.0 = normal.

        Returns:
            Path to the generated audio file (MP3).
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")

        voice = voice or DEFAULT_VOICE
        rate_percent = int((speed - 1.0) * 100)
        rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"

        # Ensure output directory exists
        os.makedirs(TTS_DIR, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(TTS_DIR, filename)

        communicate = edge_tts.Communicate(text.strip(), voice, rate=rate_str)
        await communicate.save(filepath)

        logger.info("TTS generated: %s (voice=%s, speed=%.1f)", filepath, voice, speed)
        return filepath

    def get_voices(self) -> dict[str, list[dict]]:
        """Return pre-defined voices grouped by language."""
        return VOICES


# Module-level singleton
tts_provider: TTSProvider = EdgeTTSProvider()


def get_tts_provider() -> TTSProvider:
    """Get the current TTS provider."""
    return tts_provider
