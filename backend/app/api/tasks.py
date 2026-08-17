"""
Async Tasks API endpoints.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["异步任务"])


# ── Schemas ────────────────────────────────────────────────────────────────


class TaskResponse(BaseModel):
    id: str
    user_id: str
    task_type: str
    status: str
    progress: float
    result: dict | list | str | None = None
    error: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tasks for the current user, optionally filtered by status."""
    tasks = await task_service.get_user_tasks(
        db, current_user.id, status=status, limit=limit, offset=offset
    )
    return TaskListResponse(
        tasks=[TaskResponse(**task_service.format_task(t)) for t in tasks],
        total=len(tasks),
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the status and result of a specific task."""
    task = await task_service.get_task(db, task_id, current_user.id)
    return TaskResponse(**task_service.format_task(task))


@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a pending or running task."""
    task = await task_service.cancel_task(db, task_id, current_user.id)
    return {"message": "任务已取消", "task": TaskResponse(**task_service.format_task(task))}
