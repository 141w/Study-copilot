"""Notifications API: list / mark read / mark all read."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import User
from app.main import app
from app.utils.auth import create_access_token


@pytest.fixture
async def local_user(db_session):
    uid = "user-notif-1"
    u = User(id=uid, username="notif_user", email="n@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.fixture
async def client(local_user, db_session, monkeypatch):
    from app.db import get_db

    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    token = create_access_token({"sub": local_user.id, "username": local_user.username})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c.headers["Authorization"] = f"Bearer {token}"
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_notifications_empty(client):
    resp = await client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert data["notifications"] == []
    assert data["unread"] == 0


@pytest.mark.asyncio
async def test_notifications_from_terminal_tasks(local_user, client, db_session):
    from app.db import AsyncTask

    now = datetime.now(UTC).replace(tzinfo=None)
    done = AsyncTask(
        id="t-done-1",
        user_id=local_user.id,
        task_type="document_process",
        status="completed",
        progress=1.0,
        result='{"doc_id":"doc-1","filename":"讲义.pdf","chunk_count":12}',
        created_at=now,
        completed_at=now,
    )
    running = AsyncTask(
        id="t-run-1",
        user_id=local_user.id,
        task_type="document_process",
        status="running",
        progress=0.5,
        created_at=now,
    )
    db_session.add_all([done, running])
    await db_session.commit()

    resp = await client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unread"] == 1
    assert len(data["notifications"]) == 1
    n = data["notifications"][0]
    assert n["id"] == "t-done-1"
    assert "解析完成" in n["title"]
    assert n["link"] == "/documents?document_id=doc-1"
    assert n["read"] is False


@pytest.mark.asyncio
async def test_mark_read_and_read_all(local_user, client, db_session):
    from app.db import AsyncTask

    now = datetime.now(UTC).replace(tzinfo=None)
    for i, ttype in enumerate(["document_process", "quiz_generate"], 1):
        db_session.add(
            AsyncTask(
                id=f"t-{i}",
                user_id=local_user.id,
                task_type=ttype,
                status="completed",
                progress=1.0,
                result='{"filename":"a.pdf"}',
                created_at=now,
                completed_at=now,
            )
        )
    await db_session.commit()

    resp = await client.post("/api/notifications/t-1/read")
    assert resp.status_code == 200
    assert resp.json()["unread"] == 1

    resp = await client.get("/api/notifications")
    n1 = next(x for x in resp.json()["notifications"] if x["id"] == "t-1")
    assert n1["read"] is True

    resp = await client.post("/api/notifications/read-all")
    assert resp.status_code == 200
    assert resp.json()["marked"] >= 1

    resp = await client.get("/api/notifications")
    assert resp.json()["unread"] == 0


@pytest.mark.asyncio
async def test_failed_task_notification_link(client, db_session, local_user):
    from app.db import AsyncTask

    now = datetime.now(UTC).replace(tzinfo=None)
    db_session.add(
        AsyncTask(
            id="t-fail",
            user_id=local_user.id,
            task_type="quiz_generate",
            status="failed",
            progress=0.2,
            error="LLM 超时",
            created_at=now,
            completed_at=now,
        )
    )
    await db_session.commit()

    resp = await client.get("/api/notifications")
    n = resp.json()["notifications"][0]
    assert "失败" in n["title"]
    assert "LLM" in n["body"]
    assert n["link"] == "/tasks"
    assert n["level"] == "error"


@pytest.mark.asyncio
async def test_notification_timestamps_are_utc_iso_z(local_user, client, db_session):
    """Naive UTC DB times must serialize with Z so JS Date treats them as UTC."""
    from datetime import UTC, datetime

    from app.db import AsyncTask

    now = datetime.now(UTC).replace(tzinfo=None)
    db_session.add(
        AsyncTask(
            id="t-tz",
            user_id=local_user.id,
            task_type="document_process",
            status="completed",
            progress=1.0,
            result='{"filename":"a.pdf","doc_id":"d1"}',
            created_at=now,
            completed_at=now,
        )
    )
    await db_session.commit()

    resp = await client.get("/api/notifications")
    n = next(x for x in resp.json()["notifications"] if x["id"] == "t-tz")
    assert n["completed_at"] and n["completed_at"].endswith("Z")
    assert n["created_at"] and n["created_at"].endswith("Z")
    # JS parse as UTC should be within ~2 minutes of now
    from datetime import datetime as dt

    parsed = dt.fromisoformat(n["completed_at"].replace("Z", "+00:00"))
    assert abs((parsed - datetime.now(UTC)).total_seconds()) < 120
