"""Tests for /api/metrics endpoint.

2026-08-27 重构为密闭测试：原文件自带 session 级 client 且绕过 get_db 覆盖，
直连模块级 AsyncSessionLocal（即 .env 指向的真实 PostgreSQL）——既依赖外部
数据库存活，又会向开发库写入固定邮箱数据（二次运行撞 UNIQUE 约束）。
现统一走 conftest 的 sqlite 引擎 + get_db 覆盖链路，与其他测试一致。

2026-09-27：/api/metrics 收紧为需登录（与其它业务 API 一致），用例同步带 token。
"""

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncTask, User
from app.services.auth_service import create_access_token


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


async def _seed_user(db_session: AsyncSession, prefix: str) -> User:
    user = User(
        id=f"metrics-{prefix}-{uuid.uuid4().hex[:6]}",
        username=f"{prefix}-{uuid.uuid4().hex[:6]}",
        email=f"{prefix}-{uuid.uuid4().hex[:8]}@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def test_metrics_requires_auth(client: AsyncClient):
    resp = await client.get("/api/metrics")
    assert resp.status_code == 401


async def test_metrics_returns_200(client: AsyncClient, db_session: AsyncSession):
    user = await _seed_user(db_session, "a")
    resp = await client.get("/api/metrics", headers=_auth_headers(user))
    assert resp.status_code == 200
    data = resp.json()
    assert "app" in data
    assert "tasks" in data


async def test_metrics_app_block(client: AsyncClient, db_session: AsyncSession):
    user = await _seed_user(db_session, "b")
    data = (await client.get("/api/metrics", headers=_auth_headers(user))).json()
    assert data["app"]["name"] == "Study Copilot"
    assert isinstance(data["app"]["uptime_seconds"], float)
    assert data["app"]["uptime_seconds"] >= 0.0


async def test_metrics_tasks_block_has_status_keys(client: AsyncClient, db_session: AsyncSession):
    user = await _seed_user(db_session, "c")
    data = (await client.get("/api/metrics", headers=_auth_headers(user))).json()
    keys = set(data["tasks"].keys())
    assert {"total", "by_status", "pending", "running", "completed", "failed", "cancelled"} <= keys


async def test_metrics_reflects_inserted_tasks(client: AsyncClient, db_session: AsyncSession):
    """Metrics returned counts should reflect queued tasks."""
    user = await _seed_user(db_session, "u")
    tasks = [
        AsyncTask(id=uuid.uuid4().hex, user_id=user.id, task_type="x", status="completed")
        for _ in range(3)
    ]
    db_session.add_all(tasks)
    await db_session.commit()

    resp = await client.get("/api/metrics", headers=_auth_headers(user))
    assert resp.status_code == 200
    by = resp.json()["tasks"]["by_status"]
    assert by.get("completed", 0) >= len(tasks)


async def test_metrics_counts_are_global_across_users(
    client: AsyncClient, db_session: AsyncSession
):
    """统计是全库维度：任意用户入库的任务都应计入 total。"""
    user = await _seed_user(db_session, "v")
    statuses = ["pending", "running", "completed", "failed", "cancelled"]
    for i, status in enumerate(statuses):
        db_session.add(
            AsyncTask(id=uuid.uuid4().hex, user_id=user.id, task_type="x", status=status)
        )
    await db_session.commit()

    rows = ((await db_session.execute(select(func.count(AsyncTask.id)))).scalar_one(),)
    assert rows[0] >= len(statuses)

    resp = await client.get("/api/metrics", headers=_auth_headers(user))
    assert resp.json()["tasks"]["total"] >= len(statuses)
