"""Tests for the Async Task service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.db.database import AsyncTask
from app.exceptions import NotFoundError, ValidationError
from app.services.task_service import (
    cancel_task,
    create_task,
    format_task,
    get_task,
    get_user_tasks,
    update_task,
)

# ── Helpers ────────────────────────────────────────────────────────────────


def make_mock_task(task_id="task-123", user_id="user-1", status="pending", progress=0.0):
    """Create a mock AsyncTask object."""
    task = MagicMock(spec=AsyncTask)
    task.id = task_id
    task.user_id = user_id
    task.task_type = "document_process"
    task.status = status
    task.progress = progress
    task.result = None
    task.error = None
    task.created_at = None
    task.completed_at = None
    return task


def make_mock_db(task_to_return=None, tasks_list=None):
    """Create a mock AsyncSession that returns specified task(s)."""
    db = AsyncMock()

    if task_to_return is not None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = task_to_return
        db.execute.return_value = mock_result
    elif tasks_list is not None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = tasks_list
        db.execute.return_value = mock_result
    else:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

    return db


# ── Tests ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_task():
    db = AsyncMock()
    task = await create_task(db, user_id="user-1", task_type="document_process")

    assert task.user_id == "user-1"
    assert task.task_type == "document_process"
    assert task.status == "pending"
    assert task.progress == 0.0
    db.add.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_task_with_metadata():
    db = AsyncMock()
    meta = {"file": "test.pdf", "pages": 10}
    task = await create_task(db, "user-1", "quiz_generate", metadata=meta)

    assert task.result is not None
    result_data = json.loads(task.result)
    assert result_data["file"] == "test.pdf"


@pytest.mark.asyncio
async def test_update_task_status():
    mock_task = make_mock_task(status="pending")
    db = make_mock_db(task_to_return=mock_task)

    updated = await update_task(db, "task-123", "user-1", status="running", progress=0.5)

    assert mock_task.status == "running"
    assert mock_task.progress == 0.5
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_task_completed_sets_progress_to_1():
    mock_task = make_mock_task(status="running", progress=0.7)
    db = make_mock_db(task_to_return=mock_task)

    await update_task(db, "task-123", "user-1", status="completed", progress=0.7)

    assert mock_task.progress == 1.0
    assert mock_task.completed_at is not None


@pytest.mark.asyncio
async def test_update_task_not_found():
    db = make_mock_db(task_to_return=None)

    with pytest.raises(NotFoundError):
        await update_task(db, "nonexistent", "user-1", status="running")


@pytest.mark.asyncio
async def test_get_user_tasks():
    tasks = [make_mock_task(f"t{i}") for i in range(3)]
    db = make_mock_db(tasks_list=tasks)

    result = await get_user_tasks(db, "user-1")

    assert len(result) == 3


@pytest.mark.asyncio
async def test_get_task_found():
    mock_task = make_mock_task()
    db = make_mock_db(task_to_return=mock_task)

    result = await get_task(db, "task-123", "user-1")
    assert result.id == "task-123"


@pytest.mark.asyncio
async def test_get_task_not_found():
    db = make_mock_db(task_to_return=None)

    with pytest.raises(NotFoundError):
        await get_task(db, "nonexistent", "user-1")


@pytest.mark.asyncio
async def test_cancel_task_success():
    mock_task = make_mock_task(status="running")
    db = make_mock_db(task_to_return=mock_task)

    result = await cancel_task(db, "task-123", "user-1")

    assert mock_task.status == "cancelled"
    assert mock_task.completed_at is not None
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_cancel_task_already_completed():
    mock_task = make_mock_task(status="completed")
    db = make_mock_db(task_to_return=mock_task)

    with pytest.raises(ValidationError, match="无法取消"):
        await cancel_task(db, "task-123", "user-1")


def test_format_task_basic():
    task = make_mock_task(status="completed", progress=1.0)
    task.created_at = None
    task.completed_at = None

    result = format_task(task)

    assert result["id"] == "task-123"
    assert result["user_id"] == "user-1"
    assert result["task_type"] == "document_process"
    assert result["status"] == "completed"
    assert result["progress"] == 1.0
    assert result["result"] is None
    assert result["error"] is None


def test_format_task_with_json_result():
    task = make_mock_task()
    task.result = json.dumps({"chunks": 42})

    result = format_task(task)

    assert result["result"] == {"chunks": 42}


def test_format_task_with_non_json_result():
    task = make_mock_task()
    task.result = "plain text result"

    result = format_task(task)
    # Non-JSON result should be returned as-is
    assert result["result"] == "plain text result"
