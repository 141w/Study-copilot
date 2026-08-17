"""
Task service — manage async background tasks (CRUD + status tracking).
"""

import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncTask, User
from app.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


async def create_task(
    db: AsyncSession,
    user_id: str,
    task_type: str,
    metadata: dict | None = None,
) -> AsyncTask:
    """
    Create a new async task.

    Args:
        db: Database session.
        user_id: The ID of the user who owns the task.
        task_type: Type of task (e.g., 'document_process', 'quiz_generate', 'tts_generate').
        metadata: Optional metadata to store with the task.

    Returns:
        The newly created AsyncTask.
    """
    task = AsyncTask(
        id=str(uuid.uuid4()),
        user_id=user_id,
        task_type=task_type,
        status="pending",
        progress=0.0,
        result=json.dumps(metadata, ensure_ascii=False) if metadata else None,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    logger.info("Task created: %s (type=%s, user=%s)", task.id, task_type, user_id)
    return task


async def update_task(
    db: AsyncSession,
    task_id: str,
    user_id: str,
    status: str | None = None,
    progress: float | None = None,
    result: dict | None = None,
    error: str | None = None,
) -> AsyncTask:
    """
    Update an existing task's status, progress, result, or error.

    Args:
        db: Database session.
        task_id: The ID of the task to update.
        user_id: The ID of the task owner (for authorization).
        status: New status ('running', 'completed', 'failed', 'cancelled').
        progress: Progress value (0.0 ~ 1.0).
        result: Result data as a dict (will be JSON-serialized).
        error: Error message if the task failed.

    Returns:
        The updated AsyncTask.

    Raises:
        NotFoundError: If the task doesn't exist or doesn't belong to the user.
    """
    task = await _get_task_or_raise(db, task_id, user_id)

    if status is not None:
        task.status = status
    if progress is not None:
        task.progress = min(max(progress, 0.0), 1.0)
    if result is not None:
        task.result = json.dumps(result, ensure_ascii=False)
    if error is not None:
        task.error = error

    # Set completed_at when task reaches a terminal state
    if status in ("completed", "failed", "cancelled"):
        task.completed_at = datetime.now(UTC).replace(tzinfo=None)
        if status == "completed":
            task.progress = 1.0

    await db.commit()
    await db.refresh(task)

    logger.info("Task updated: %s → status=%s, progress=%.2f", task_id, task.status, task.progress)
    return task


async def get_user_tasks(
    db: AsyncSession,
    user_id: str,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AsyncTask]:
    """
    Get all tasks for a user, optionally filtered by status.

    Args:
        db: Database session.
        user_id: The ID of the task owner.
        status: Optional status filter.
        limit: Maximum number of tasks to return.
        offset: Number of tasks to skip.

    Returns:
        List of AsyncTask objects, newest first.
    """
    query = select(AsyncTask).where(AsyncTask.user_id == user_id)

    if status:
        query = query.where(AsyncTask.status == status)

    query = query.order_by(AsyncTask.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_task(
    db: AsyncSession,
    task_id: str,
    user_id: str,
) -> AsyncTask:
    """
    Get a single task by ID.

    Raises:
        NotFoundError: If the task doesn't exist or doesn't belong to the user.
    """
    return await _get_task_or_raise(db, task_id, user_id)


async def cancel_task(
    db: AsyncSession,
    task_id: str,
    user_id: str,
) -> AsyncTask:
    """
    Cancel a pending or running task.

    Raises:
        NotFoundError: If the task doesn't exist or doesn't belong to the user.
        ValidationError: If the task is already in a terminal state.
    """
    task = await _get_task_or_raise(db, task_id, user_id)

    if task.status in ("completed", "failed", "cancelled"):
        raise ValidationError(f"任务已处于 '{task.status}' 状态，无法取消")

    task.status = "cancelled"
    task.completed_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(task)

    logger.info("Task cancelled: %s", task_id)
    return task


def format_task(task: AsyncTask) -> dict:
    """Format an AsyncTask into a response dict."""
    result_data = None
    if task.result:
        try:
            result_data = json.loads(task.result)
        except (json.JSONDecodeError, TypeError):
            result_data = task.result

    return {
        "id": task.id,
        "user_id": task.user_id,
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress,
        "result": result_data,
        "error": task.error,
        "created_at": str(task.created_at) if task.created_at else None,
        "completed_at": str(task.completed_at) if task.completed_at else None,
    }


# ── internal helpers ────────────────────────────────────────────────────────


async def _get_task_or_raise(
    db: AsyncSession,
    task_id: str,
    user_id: str,
) -> AsyncTask:
    """Fetch a task by ID and user_id, or raise NotFoundError."""
    result = await db.execute(
        select(AsyncTask).where(AsyncTask.id == task_id, AsyncTask.user_id == user_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("任务不存在")
    return task
