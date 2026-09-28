"""P0-B favorites (bookmarks) API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db
from app.services import favorite_service

router = APIRouter(prefix="/favorites", tags=["收藏"])
logger = logging.getLogger(__name__)


class FavoriteCreate(BaseModel):
    resource_type: str = Field(..., min_length=1, max_length=20)
    resource_id: str = Field(..., min_length=1, max_length=64)


class FavoriteOut(BaseModel):
    id: str
    resource_type: str
    resource_id: str
    created_at: str | None = None


@router.get("", response_model=list[FavoriteOut])
async def list_favorites(
    resource_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await favorite_service.list_favorites(db, current_user, resource_type)


@router.post("", response_model=FavoriteOut)
async def add_favorite(
    body: FavoriteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await favorite_service.add_favorite(
        db, current_user, body.resource_type, body.resource_id
    )


@router.delete("", response_model=dict)
async def remove_favorite(
    resource_type: str = Query(...),
    resource_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await favorite_service.remove_favorite(db, current_user, resource_type, resource_id)
    return {"success": True}
