"""
TTS (Text-to-Speech) API endpoints.
"""

import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.core.tts import get_tts_provider
from app.db import User

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
    current_user: User = Depends(get_current_user),
):
    """Generate speech audio from text. Returns the audio file for playback."""
    provider = get_tts_provider()
    filepath = await provider.generate_speech(
        text=req.text,
        voice=req.voice,
        speed=req.speed,
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
