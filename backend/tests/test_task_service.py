"""Tests for task service: CRUD + cancel + recover + format."""

import uuid
from datetime import UTC, datetime
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import AsyncTask, User
from app.exceptions import NotFoundError, ValidationError
from app.services import task_service


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(id="svc-task-user", username="svc_task", email="t@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u


async def _create_task(db_session: AsyncSession, user_id: str, task_type: str = "document_process") -> AsyncTask:
    return await task_service.create_task(db_session, user_id, task_type, {"key": "value"})


# ── create_task ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_task(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id)
    assert task.id is not None
    assert task.task_type == "document_process"
    assert task.status == "pending"
    assert task.progress == 0.0


@pytest.mark.asyncio
async def test_create_task_stores_metadata(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id, "quiz_generate")
    assert task.task_type == "quiz_generate"
    formatted = task_service.format_task(task)
    assert formatted["result"] == {"key": "value"}


# ── update_task ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_task_status(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id)
    updated = await task_service.update_task(db_session, task.id, user.id, status="running")
    assert updated.status == "running"


@pytest.mark.asyncio
async def test_update_task_progress(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id)
    updated = await task_service.update_task(db_session, task.id, user.id, progress=0.5)
    assert updated.progress == 0.5


@pytest.mark.asyncio
async def test_update_task_completes_and_sets_timestamp(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id)
    updated = await task_service.update_task(db_session, task.id, user.id, status="completed", progress=1.0)
    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert updated.progress == 1.0


@pytest.mark.asyncio
async def test_update_task_failed_sets_error(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id)
    updated = await task_service.update_task(db_session, task.id, user.id, status="failed", error="boom")
    assert updated.status == "failed"
    assert updated.error == "boom"
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_update_task_raises_for_wrong_user(db_session: AsyncSession, user: User):
    other = User(id="other-task", username="ot", email="ot@t.com", password_hash="x" * 60)
    db_session.add(other)
    await db_session.commit()
    task = await _create_task(db_session, user.id)
    with pytest.raises(NotFoundError):
        await task_service.update_task(db_session, task.id, other.id, status="completed")


# ── cancel_task ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_pending_task(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id)
    cancelled = await task_service.cancel_task(db_session, task.id, user.id)
    assert cancelled.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_running_task(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id)
    await task_service.update_task(db_session, task.id, user.id, status="running")
    cancelled = await task_service.cancel_task(db_session, task.id, user.id)
    assert cancelled.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_completed_task_raises(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id)
    await task_service.update_task(db_session, task.id, user.id, status="completed")
    with pytest.raises(ValidationError, match="无法取消"):
        await task_service.cancel_task(db_session, task.id, user.id)


@pytest.mark.asyncio
async def test_cancel_already_cancelled_raises(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id)
    await task_service.cancel_task(db_session, task.id, user.id)
    with pytest.raises(ValidationError):
        await task_service.cancel_task(db_session, task.id, user.id)


# ── get_task / get_user_tasks ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_task_returns_task(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id)
    result = await task_service.get_task(db_session, task.id, user.id)
    assert result.id == task.id


@pytest.mark.asyncio
async def test_get_task_raises_for_missing(db_session: AsyncSession, user: User):
    with pytest.raises(NotFoundError, match="任务不存在"):
        await task_service.get_task(db_session, "nonexistent", user.id)


@pytest.mark.asyncio
async def test_get_user_tasks_filters_by_status(db_session: AsyncSession, user: User):
    t1 = await _create_task(db_session, user.id, "doc")
    await task_service.update_task(db_session, t1.id, user.id, status="completed")
    t2 = await _create_task(db_session, user.id, "quiz")
    await task_service.update_task(db_session, t2.id, user.id, status="failed")

    completed = await task_service.get_user_tasks(db_session, user.id, status="completed")
    assert len(completed) == 1
    assert completed[0].id == t1.id


@pytest.mark.asyncio
async def test_get_user_tasks_default_no_filter(db_session: AsyncSession, user: User):
    t1 = await _create_task(db_session, user.id, "doc")
    await task_service.update_task(db_session, t1.id, user.id, status="completed")
    t2 = await _create_task(db_session, user.id, "quiz")
    t3 = await _create_task(db_session, user.id, "tts")

    all_tasks = await task_service.get_user_tasks(db_session, user.id)
    assert len(all_tasks) == 3


# ── recover_interrupted_tasks ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recover_interrupted_tasks_marks_running_as_failed(db_session: AsyncSession, user: User):
    t1 = await _create_task(db_session, user.id)
    await task_service.update_task(db_session, t1.id, user.id, status="running")
    t2 = await _create_task(db_session, user.id)
    await task_service.update_task(db_session, t2.id, user.id, status="running")

    count = await task_service.recover_interrupted_tasks(db_session)
    assert count == 2

    recovered = await task_service.get_user_tasks(db_session, user.id)
    for t in recovered:
        assert t.status == "failed"


@pytest.mark.asyncio
async def test_recover_does_not_affect_completed(db_session: AsyncSession, user: User):
    t1 = await _create_task(db_session, user.id)
    await task_service.update_task(db_session, t1.id, user.id, status="completed")

    count = await task_service.recover_interrupted_tasks(db_session)
    assert count == 0


# ── format_task ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_format_task_with_metadata(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id, "quiz_generate")
    formatted = task_service.format_task(task)
    assert formatted["id"] == task.id
    assert formatted["task_type"] == "quiz_generate"
    assert formatted["result"] == {"key": "value"}


@pytest.mark.asyncio
async def test_format_task_serializes_result(db_session: AsyncSession, user: User):
    task = await _create_task(db_session, user.id)
    task.result = '{"doc_id": "abc", "chunk_count": 42}'
    formatted = task_service.format_task(task)
    assert isinstance(formatted["result"], dict)
    assert formatted["result"]["doc_id"] == "abc"
