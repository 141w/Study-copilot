"""
TTS (Text-to-Speech) API endpoints.
"""

import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, get_optional_user
from app.core.tts import get_tts_provider
from app.db import User, get_db

router = APIRouter(prefix="/tts", tags=["语音合成"])


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


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/generate")
async def generate_speech(
    req: TTSRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """Generate speech audio from text using user config or Edge TTS. Returns audio file."""
    tts_config = None
    try:
        from app.services.config_service import get_llm_config_with_secret

        if not current_user:
            raise RuntimeError("auth required for user TTS config")
        secret_cfg = await get_llm_config_with_secret(db, current_user)
        cls_cfg = secret_cfg.get("classroom_config") or {}
        tts_config = {
            "tts_provider": cls_cfg.get("tts_provider") or "edge-tts",
            "tts_api_key": cls_cfg.get("tts_api_key") or secret_cfg.get("api_key"),
            "tts_base_url": cls_cfg.get("tts_base_url"),
            "tts_model": cls_cfg.get("tts_model"),
        }
    except Exception:
        pass

    from app.core.tts import generate_speech_with_fallback

    filepath = await generate_speech_with_fallback(
        text=req.text,
        voice=req.voice,
        speed=req.speed,
        config=tts_config,
    )

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
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """OpenAI 兼容的语音合成接口 (POST /api/tts/v1/audio/speech)。
    供外部微前端引擎 (OpenMAIC) 及第三方客户端直接调用，支持免密 Edge-TTS 与自定义模型。
    """
    tts_config = None
    if not current_user:
        try:
            from sqlalchemy import select

            from app.db.database import UserLLMConfig

            res = await db.execute(
                select(User)
                .join(UserLLMConfig, User.id == UserLLMConfig.user_id)
                .order_by(UserLLMConfig.updated_at.desc())
            )
            current_user = res.scalars().first()
            if not current_user:
                res = await db.execute(select(User))
                current_user = res.scalars().first()
        except Exception:
            pass

    if current_user:
        try:
            from app.services.config_service import get_llm_config_with_secret

            secret_cfg = await get_llm_config_with_secret(db, current_user)
            cls_cfg = secret_cfg.get("classroom_config") or {}
            tts_config = {
                "tts_provider": cls_cfg.get("tts_provider") or "edge-tts",
                "tts_api_key": cls_cfg.get("tts_api_key") or secret_cfg.get("api_key"),
                "tts_base_url": cls_cfg.get("tts_base_url"),
                "tts_model": cls_cfg.get("tts_model"),
                "voice_teacher": cls_cfg.get("voice_teacher"),
                "voice_curious": cls_cfg.get("voice_curious"),
                "voice_thinker": cls_cfg.get("voice_thinker"),
            }
        except Exception:
            pass

    from app.core.tts import generate_speech_with_fallback

    # 映射常见音色名到高质量中文音色或用户设置角色音色
    voice = req.voice
    teacher_v = (tts_config or {}).get("voice_teacher")
    curious_v = (tts_config or {}).get("voice_curious")
    thinker_v = (tts_config or {}).get("voice_thinker")

    if not voice or voice in ("alloy", "default"):
        voice = teacher_v or "zh-CN-YunxiNeural"
    elif voice in ("nova", "shimmer"):
        voice = curious_v or "zh-CN-XiaoxiaoNeural"
    elif voice in ("echo", "onyx"):
        voice = thinker_v or "zh-CN-YunjianNeural"
    elif voice == "fable":
        voice = "zh-CN-XiaoyiNeural"

    filepath = await generate_speech_with_fallback(
        text=req.input,
        voice=voice,
        speed=req.speed,
        config=tts_config,
    )

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
