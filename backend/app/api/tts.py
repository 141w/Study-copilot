"""
TTS (Text-to-Speech) API endpoints.
"""

import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.rate_limit import IPRateLimiter
from app.core.tts import get_tts_provider
from app.db import User, get_db
from app.exceptions import ExternalServiceError, RateLimitError, ValidationError

router = APIRouter(prefix="/tts", tags=["语音合成"])

_tts_limiter = IPRateLimiter(requests_per_minute=30)


# ── Schemas ────────────────────────────────────────────────────────────────


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None
    speed: float = 1.0


class OpenAISpeechRequest(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str | None = None
    speed: float = 1.0


class VoiceInfo(BaseModel):
    id: str
    name: str
    language: str
    gender: str


class VoiceListResponse(BaseModel):
    voices: dict[str, list[VoiceInfo]]


def _tts_config_for_user(secret_cfg: dict) -> dict:
    cls_cfg = secret_cfg.get("classroom_config") or {}
    return {
        "tts_provider": cls_cfg.get("tts_provider") or "edge-tts",
        "tts_api_key": cls_cfg.get("tts_api_key") or secret_cfg.get("api_key"),
        "tts_base_url": cls_cfg.get("tts_base_url"),
        "tts_model": cls_cfg.get("tts_model"),
        "voice_teacher": cls_cfg.get("voice_teacher"),
        "voice_curious": cls_cfg.get("voice_curious"),
        "voice_thinker": cls_cfg.get("voice_thinker"),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/generate")
async def generate_speech(
    req: TTSRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate speech audio from the current user's TTS config (or Edge TTS)."""
    if not _tts_limiter.check(request):
        raise RateLimitError("请求过于频繁，请稍后再试")

    from app.services.config_service import get_llm_config_with_secret

    secret_cfg = await get_llm_config_with_secret(db, current_user)
    tts_config = _tts_config_for_user(secret_cfg)

    from app.core.tts import generate_speech_with_fallback

    try:
        filepath = await generate_speech_with_fallback(
            text=req.text,
            voice=req.voice,
            speed=req.speed,
            config=tts_config,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    except Exception as e:
        raise ExternalServiceError(f"语音生成失败: {e}") from e

    filename = os.path.basename(filepath)
    return FileResponse(
        path=filepath,
        media_type="audio/mpeg",
        filename=filename,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/v1/audio/speech")
@router.post("/audio/speech")
async def openai_compatible_speech(
    req: OpenAISpeechRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """OpenAI 兼容语音合成（需登录）。仅使用当前用户自己的密钥/配置。"""
    if not _tts_limiter.check(request):
        raise RateLimitError("请求过于频繁，请稍后再试")

    from app.services.config_service import get_llm_config_with_secret

    secret_cfg = await get_llm_config_with_secret(db, current_user)
    tts_config = _tts_config_for_user(secret_cfg)

    from app.core.tts import generate_speech_with_fallback

    # 映射常见音色名到高质量中文音色或用户设置角色音色
    voice = req.voice
    teacher_v = tts_config.get("voice_teacher")
    curious_v = tts_config.get("voice_curious")
    thinker_v = tts_config.get("voice_thinker")

    if not voice or voice in ("alloy", "default"):
        voice = teacher_v or "zh-CN-YunxiNeural"
    elif voice in ("nova", "shimmer"):
        voice = curious_v or "zh-CN-XiaoxiaoNeural"
    elif voice in ("echo", "onyx"):
        voice = thinker_v or "zh-CN-YunjianNeural"
    elif voice == "fable":
        voice = "zh-CN-XiaoyiNeural"

    try:
        filepath = await generate_speech_with_fallback(
            text=req.input,
            voice=voice,
            speed=req.speed,
            config=tts_config,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    except Exception as e:
        raise ExternalServiceError(f"语音生成失败: {e}") from e

    filename = os.path.basename(filepath)
    return FileResponse(
        path=filepath,
        media_type="audio/mpeg",
        filename=filename,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/voices", response_model=VoiceListResponse)
async def list_voices(
    current_user: User = Depends(get_current_user),
):
    """List available TTS voices grouped by language."""
    provider = get_tts_provider()
    voices = provider.get_voices()

    result = {}
    for lang, voice_list in voices.items():
        result[lang] = [VoiceInfo(**v) for v in voice_list]

    return VoiceListResponse(voices=result)
