"""Long-Term Memory API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db
from app.services.memory_service import (
    KIND_FACT,
    KIND_INTEREST,
    KIND_PREFERENCE,
    KIND_PROFILE,
    KIND_TASK,
    ORIGIN_MANUAL,
    STATUS_ACTIVE,
    memory_service,
)

router = APIRouter(prefix="/memory", tags=["长期记忆"])


class MemoryItemCreate(BaseModel):
    kind: str = Field(..., description="profile | preference | fact | task | interest")
    content: str = Field(..., min_length=1)
    key: str = Field("", description="Optional deduplication key")


class MemoryItemUpdate(BaseModel):
    content: str | None = None
    kind: str | None = None
    key: str | None = None


class MemoryConfigUpdate(BaseModel):
    enabled: bool | None = None
    capacity: int | None = None


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 10


@router.get("")
async def get_memories(
    kind: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List user memories and subject settings."""
    items = await memory_service.list_items(
        user_id=current_user.id, kind=kind, status=status, db=db
    )
    subject = await memory_service.get_or_create_subject(current_user.id, db)

    return {
        "items": [
            {
                "id": it.id,
                "kind": it.kind,
                "origin": it.origin,
                "status": it.status,
                "key": it.key,
                "content": it.content,
                "created_at": it.created_at.isoformat() if it.created_at else None,
                "updated_at": it.updated_at.isoformat() if it.updated_at else None,
                "superseded_at": it.superseded_at.isoformat() if it.superseded_at else None,
            }
            for it in items
        ],
        "config": {
            "enabled": subject.enabled,
            "capacity": subject.capacity,
            "has_resident_block": bool(subject.block_text.strip()),
            "last_extracted_at": subject.last_extracted_at.isoformat()
            if subject.last_extracted_at
            else None,
        },
    }


@router.post("")
async def create_memory(
    payload: MemoryItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Manually add a memory item."""
    valid_kinds = {KIND_PROFILE, KIND_PREFERENCE, KIND_FACT, KIND_TASK, KIND_INTEREST}
    if payload.kind not in valid_kinds:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid kind: {payload.kind}. Must be one of {valid_kinds}",
        )

    item = await memory_service.add_item(
        user_id=current_user.id,
        kind=payload.kind,
        content=payload.content,
        key=payload.key,
        origin=ORIGIN_MANUAL,
        status=STATUS_ACTIVE,
        db=db,
    )
    return {
        "id": item.id,
        "kind": item.kind,
        "key": item.key,
        "content": item.content,
        "status": item.status,
    }


@router.post("/{item_id}/confirm")
async def confirm_memory(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Confirm a pending inferred memory item."""
    try:
        item = await memory_service.confirm_pending(current_user.id, item_id, db)
        return {"id": item.id, "status": item.status, "message": "Memory confirmed"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{item_id}/supersede")
async def supersede_memory(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Mark memory item as superseded."""
    try:
        item = await memory_service.supersede_item(current_user.id, item_id, db)
        return {"id": item.id, "status": item.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{item_id}")
async def delete_memory(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete a memory item."""
    success = await memory_service.delete_item(current_user.id, item_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Memory item not found")
    return {"message": "Memory item deleted"}


@router.put("/config")
async def update_config(
    payload: MemoryConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Toggle memory enabled or update capacity."""
    subject = await memory_service.get_or_create_subject(current_user.id, db)
    if payload.enabled is not None:
        subject.enabled = payload.enabled
    if payload.capacity is not None:
        subject.capacity = payload.capacity
    await db.commit()
    await db.refresh(subject)
    return {"enabled": subject.enabled, "capacity": subject.capacity}


@router.post("/search")
async def search_memories(
    payload: MemorySearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Lexical search across memories."""
    return await memory_service.search(
        user_id=current_user.id, query=payload.query, limit=payload.limit, db=db
    )
