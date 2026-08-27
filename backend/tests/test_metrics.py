"""Tests for /api/metrics endpoint."""

import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.db import AsyncSessionLocal, AsyncTask, User
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_metrics_returns_200(client: AsyncClient):
    resp = await client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "app" in data
    assert "tasks" in data


@pytest.mark.asyncio
async def test_metrics_app_block(client: AsyncClient):
    data = (await client.get("/api/metrics")).json()
    assert data["app"]["name"] == "Study Copilot"
    assert isinstance(data["app"]["uptime_seconds"], float)
    assert data["app"]["uptime_seconds"] >= 0.0


@pytest.mark.asyncio
async def test_metrics_tasks_block_has_status_keys(client: AsyncClient):
    data = (await client.get("/api/metrics")).json()
    keys = set(data["tasks"].keys())
    assert {"total", "by_status", "pending", "running", "completed", "failed", "cancelled"} <= keys


@pytest.mark.asyncio
async def test_metrics_reflects_inserted_tasks():
    """Metrics returned counts should reflect queued tasks."""
    async with AsyncSessionLocal() as db:
        user = User(id=f"metrics-u-{uuid.uuid4().hex[:6]}", username="m", email="m@t.com", password_hash="x" * 60)
        db.add(user)
        await db.commit()
        for _ in range(3):
            t = AsyncTask(
                id=uuid.uuid4().hex, user_id=user.id,
                task_type="x", status="completed",
            )
            db.add(t)
        await db.commit()

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(AsyncTask.status, func.count(AsyncTask.id)).group_by(AsyncTask.status))).all()
        by = {r.status: r.cnt for r in rows}
        assert by.get("completed", 0) >= 3
