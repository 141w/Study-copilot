"""
Text-to-Speech module using Edge TTS (free, no API key needed).

Provides a TTS provider abstraction and an EdgeTTS implementation.
"""

import logging
import os
import time
import uuid
from typing import Any

import edge_tts

from app.config import settings

logger = logging.getLogger(__name__)

# TTS output directory
TTS_DIR = os.path.join(settings.upload_dir, "tts")

# Generated mp3 files older than this are cleaned up
TTS_FILE_MAX_AGE_SECONDS = 24 * 3600

# Minimum interval between cleanup sweeps (avoids scanning on every request)
_CLEANUP_INTERVAL_SECONDS = 3600
_last_cleanup = 0.0


def cleanup_old_audio(max_age_seconds: float = TTS_FILE_MAX_AGE_SECONDS) -> int:
    """Delete generated mp3 files older than max_age_seconds.

    Returns the number of files removed.
    """
    if not os.path.isdir(TTS_DIR):
        return 0

    now = time.time()
    removed = 0
    for name in os.listdir(TTS_DIR):
        if not name.endswith(".mp3"):
            continue
        path = os.path.join(TTS_DIR, name)
        try:
            if now - os.path.getmtime(path) > max_age_seconds:
                os.remove(path)
                removed += 1
        except OSError as e:
            logger.warning("Failed to clean up TTS file %s: %s", path, e)

    if removed:
        logger.info("TTS cleanup removed %d stale audio file(s)", removed)
    return removed


def _maybe_cleanup() -> None:
    """Run cleanup at most once per cleanup interval."""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup >= _CLEANUP_INTERVAL_SECONDS:
        _last_cleanup = now
        try:
            cleanup_old_audio()
        except Exception as e:
            logger.warning("TTS cleanup failed: %s", e)


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


class EdgeTTSProvider:
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

        # Periodically remove stale audio files
        _maybe_cleanup()

        filename = f"{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(TTS_DIR, filename)

        communicate = edge_tts.Communicate(text.strip(), voice, rate=rate_str)
        await communicate.save(filepath)

        logger.info("EdgeTTS generated: %s (voice=%s, speed=%.1f)", filepath, voice, speed)
        return filepath

    def get_voices(self) -> dict[str, list[dict]]:
        """Return pre-defined voices grouped by language."""
        return VOICES


class OpenAITTSProvider:
    """OpenAI compatible TTS provider (POST /v1/audio/speech).

    Supports OpenAI (tts-1/tts-1-hd), SiliconFlow (CosyVoice/Fish Audio), and custom endpoints.
    """

    def __init__(self, base_url: str | None, api_key: str | None, model: str | None):
        clean_url = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
        if not clean_url.endswith("/v1") and not clean_url.endswith("/v1/audio"):
            clean_url = f"{clean_url}/v1"
        self.base_url = clean_url
        self.api_key = (api_key or "").strip()
        self.model = (model or "tts-1").strip()

    async def generate_speech(self, text: str, voice: str | None = None, speed: float = 1.0) -> str:
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        if not self.api_key:
            raise ValueError("缺少 TTS API Key")

        import httpx

        url = f"{self.base_url}/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": text.strip(),
            "voice": voice or "alloy",
            "speed": max(0.25, min(4.0, speed)),
        }

        os.makedirs(TTS_DIR, exist_ok=True)
        _maybe_cleanup()

        filename = f"{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(TTS_DIR, filename)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                err_msg = resp.text[:200]
                logger.error("OpenAI TTS failed (%s): %s", resp.status_code, err_msg)
                raise RuntimeError(f"语音合成接口响应失败 ({resp.status_code}): {err_msg}")
            with open(filepath, "wb") as f:
                f.write(resp.content)

        logger.info("OpenAITTS generated: %s (model=%s, voice=%s)", filepath, self.model, voice)
        return filepath


# Module-level singleton
edge_tts_provider = EdgeTTSProvider()


def get_tts_provider(config: dict[str, Any] | None = None) -> EdgeTTSProvider | OpenAITTSProvider:
    """根据配置获取对应的 TTS 语音提供器。"""
    if not config:
        return edge_tts_provider

    provider_type = config.get("tts_provider") or "edge-tts"
    if provider_type in ("openai", "siliconflow", "custom"):
        api_key = config.get("tts_api_key")
        if api_key:
            return OpenAITTSProvider(
                base_url=config.get("tts_base_url"),
                api_key=api_key,
                model=config.get("tts_model"),
            )
    return edge_tts_provider


async def generate_speech_with_fallback(
    text: str,
    voice: str | None = None,
    speed: float = 1.0,
    config: dict[str, Any] | None = None,
) -> str:
    """生成语音音频，若外部 TTS 失败自动降级到内置 Edge TTS。"""
    if config and (config.get("tts_provider") or "edge-tts") != "edge-tts":
        try:
            provider = get_tts_provider(config)
            return await provider.generate_speech(text, voice=voice, speed=speed)
        except Exception as e:
            logger.warning("Custom TTS failed (%s), falling back to Edge TTS: %s", e, text[:30])

    # 降级或默认使用 Edge TTS
    edge_voice = voice if (voice and voice.startswith("zh-CN")) else DEFAULT_VOICE
    return await edge_tts_provider.generate_speech(text, voice=edge_voice, speed=speed)


async def test_tts_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    """测试语音合成接口连通性并生成试听音频片段。"""
    provider_type = config.get("tts_provider") or "edge-tts"
    test_text = "您好，Study Copilot 互动课堂语音服务连通正常。"
    start_time = time.time()

    if provider_type == "edge-tts":
        try:
            voice = config.get("voice_teacher") or DEFAULT_VOICE
            filepath = await edge_tts_provider.generate_speech(test_text, voice=voice)
            latency_ms = max(1, int((time.time() - start_time) * 1000))
            import base64

            with open(filepath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return {
                "success": True,
                "message": f"内置 Edge TTS 服务正常！试听音色: {voice}",
                "latency_ms": latency_ms,
                "audio_base64": f"data:audio/mp3;base64,{b64}",
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Edge TTS 测试失败: {str(e)}",
                "latency_ms": 0,
                "audio_base64": None,
            }

    # 外部 OpenAI 兼容 TTS
    api_key = (config.get("tts_api_key") or "").strip()
    if not api_key:
        return {
            "success": False,
            "message": "未检测到语音服务 API Key，请输入有效密钥",
            "latency_ms": 0,
            "audio_base64": None,
        }

    try:
        provider = OpenAITTSProvider(
            base_url=config.get("tts_base_url"),
            api_key=api_key,
            model=config.get("tts_model"),
        )
        voice = config.get("voice_teacher") or "alloy"
        filepath = await provider.generate_speech(test_text, voice=voice, speed=1.0)
        latency_ms = max(1, int((time.time() - start_time) * 1000))
        import base64

        with open(filepath, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return {
            "success": True,
            "message": f"语音服务连通正常！已成功连接到 {provider_type}（模型: {provider.model}）",
            "latency_ms": latency_ms,
            "audio_base64": f"data:audio/mp3;base64,{b64}",
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"语音测试失败: {str(e)}",
            "latency_ms": max(1, int((time.time() - start_time) * 1000)),
            "audio_base64": None,
        }
