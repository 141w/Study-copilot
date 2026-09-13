"""Task-completion notifications API (derived from async_tasks)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["通知"])


class NotificationItem(BaseModel):
    id: str
    task_id: str
    task_type: str
    status: str
    level: str
    icon: str
    title: str
    body: str
    link: str
    read: bool
    created_at: str | None = None
    completed_at: str | None = None


class NotificationListResponse(BaseModel):
    notifications: list[NotificationItem]
    unread: int


class MarkAllResponse(BaseModel):
    marked: int


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = 20,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = await notification_service.list_notifications(
        db, current_user.id, limit=limit, unread_only=unread_only
    )
    unread = await notification_service.unread_count(db, current_user.id)
    return NotificationListResponse(
        notifications=[NotificationItem(**n) for n in items],
        unread=unread,
    )


@router.post("/{task_id}/read")
async def mark_notification_read(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = await notification_service.mark_read(db, current_user.id, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知不存在或已读")
    unread = await notification_service.unread_count(db, current_user.id)
    return {"ok": True, "unread": unread}


@router.post("/read-all", response_model=MarkAllResponse)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    marked = await notification_service.mark_all_read(db, current_user.id)
    return MarkAllResponse(marked=marked)
