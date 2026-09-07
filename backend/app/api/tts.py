"""
TTS (Text-to-Speech) API endpoints.
"""

import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.tts import get_tts_provider
from app.db import User, get_db

router = APIRouter(prefix="/tts", tags=["语音合成"])


# ── Schemas ────────────────────────────────────────────────────────────────


class TTSRequest(BaseModel):
    text: str
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
    current_user: User = Depends(get_current_user),
):
    """Generate speech audio from text using user config or Edge TTS. Returns audio file."""
    tts_config = None
    try:
        from app.services.config_service import get_llm_config_with_secret

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
