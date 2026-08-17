"""
Transform API — endpoints for content transformation.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db
from app.services import transform_service

router = APIRouter(prefix="/transform", tags=["内容转换"])


# ── Schemas ─────────────────────────────────────────────────────────────


class TransformRequest(BaseModel):
    """Request to transform content."""

    transform_type: str
    # One of: source text directly, or reference to a note/document
    source_text: str | None = None
    source_title: str = ""
    note_id: str | None = None
    document_id: str | None = None


class TransformResponse(BaseModel):
    """Response from a transformation."""

    transform_type: str
    transform_name: str
    result: str
    source_title: str


class TransformationInfo(BaseModel):
    """Metadata about an available transformation."""

    key: str
    name: str
    name_en: str
    description: str


# ── Endpoints ───────────────────────────────────────────────────────────


@router.get("/transformations", response_model=list[TransformationInfo])
async def list_transformations():
    """List all available transformation types."""
    return transform_service.get_available_transformations()


@router.post("", response_model=TransformResponse)
async def execute_transform(
    data: TransformRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute a content transformation."""
    if data.note_id:
        result = await transform_service.transform_note(
            db, current_user, data.note_id, data.transform_type
        )
    elif data.document_id:
        result = await transform_service.transform_document_chunks(
            db, current_user, data.document_id, data.transform_type
        )
    elif data.source_text:
        result = await transform_service.transform_content(
            db,
            current_user,
            data.source_text,
            data.transform_type,
            source_title=data.source_title,
        )
    else:
        from app.exceptions import ValidationError

        raise ValidationError("请提供 source_text、note_id 或 document_id 之一")

    return TransformResponse(**result)
