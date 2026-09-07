"""持久化任务队列回归测试。

背景：队列原为进程内存 asyncio.Queue，重启即丢失（recover 只能收尸）。
现改为 pending 行落库 + worker 轮询认领（FOR UPDATE SKIP LOCKED）。

用例设计说明：conftest 的 db_session 使用 StaticPool 单连接，无法与后台
任务并发共用（MissingGreenlet），因此——
  A. 核心机制用「直接调用 _claim_next_job/_execute_job」顺序验证；
  B. 端到端轮询循环用独立的文件级 SQLite 引擎（tmp_path）隔离验证。
"""

import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import task_worker
from app.db.database import Base
from app.services import task_service


def _make_sessionmaker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_pending_row_claimed_and_executed(tmp_path, monkeypatch):
    """A. 核心机制：pending 行被 _claim_next_job 认领并执行至终态。

    使用独立引擎（与 B 同款）避免复用会话级循环上的共享连接。
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/core.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = _make_sessionmaker(engine)
    # 关键：让 worker 的会话工厂指向测试引擎（否则认领会连到真实 PG）
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", _make_sessionmaker(engine))
    uid = "u-persist-" + uuid.uuid4().hex[:8]

    task_id = ""
    async with maker() as db:
        task = await task_service.create_task(
            db,
            uid,
            "unknown_type_for_test",  # 未知类型 → 执行路径必然置 failed
            {"hello": "world"},
        )
        task_id = task.id
        assert task.status == "pending"

    async with maker() as db:
        probe = (await db.execute(select(task_service.AsyncTask))).scalars().all()
        print(
            "PROBE rows:", [(r.id[:8], r.status) for r in probe], "| dialect:", engine.dialect.name
        )

    job = await task_worker._claim_next_job()
    assert job is not None and job.task_id == task_id

    # 认领即置 running（原子性由行锁保证；SQLite 方言忽略 FOR UPDATE 但语义一致）
    async with maker() as db:
        claimed = (
            await db.execute(
                select(task_service.AsyncTask).where(task_service.AsyncTask.id == task_id)
            )
        ).scalar_one()
        assert claimed.status == "running"

    await task_worker._execute_job(job)
    async with maker() as db:
        done = (
            await db.execute(
                select(task_service.AsyncTask).where(task_service.AsyncTask.id == task_id)
            )
        ).scalar_one()
        assert done.status == "failed"
        assert "Unknown type" in done.error

    await engine.dispose()


@pytest.mark.asyncio
async def test_worker_loop_polls_pending_rows_autonomously(tmp_path, monkeypatch):
    """B. 端到端：仅落库、不 enqueue，独立引擎上 worker 轮询自动执行。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/queue.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(task_worker, "AsyncSessionLocal", _make_sessionmaker(engine))

    uid = "u-loop-" + uuid.uuid4().hex[:8]
    maker = _make_sessionmaker(engine)
    async with maker() as db:
        await task_service.create_task(
            db,
            uid,
            "unknown_type_for_test",
            {"src": "restart-before-enqueue"},
        )

    await task_worker.start_worker()
    try:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + 10
        status = "pending"
        while loop.time() < deadline:
            async with maker() as db:
                row = (
                    await db.execute(
                        select(task_service.AsyncTask).where(task_service.AsyncTask.user_id == uid)
                    )
                ).scalar_one()
                status = row.status
                error = row.error
            if status in ("completed", "failed"):
                break
            await asyncio.sleep(0.2)
        assert status == "failed", f"轮询未接管 pending 行（最后状态 {status}）"
        assert error and "Unknown type" in error
    finally:
        await task_worker.stop_worker()
        await engine.dispose()


@pytest.mark.asyncio
async def test_recover_marks_only_running_orphans(db_session: AsyncSession):
    """C. recover 收窄：仅 running 孤儿标记失败，pending 保持待执行。"""
    from app.db import AsyncTask

    uid = "u-any-" + uuid.uuid4().hex[:8]
    db_session.add(
        AsyncTask(
            id="t-orphan-running-" + uuid.uuid4().hex[:6],
            user_id=uid,
            task_type="document_process",
            status="running",
            progress=0.5,
        )
    )
    db_session.add(
        AsyncTask(
            id="t-queued-pending-" + uuid.uuid4().hex[:6],
            user_id=uid,
            task_type="document_process",
            status="pending",
            progress=0.0,
        )
    )
    await db_session.commit()

    recovered = await task_service.recover_interrupted_tasks(db_session)
    assert recovered >= 1

    rows = (
        (await db_session.execute(select(AsyncTask).where(AsyncTask.user_id == uid)))
        .scalars()
        .all()
    )
    by_id = {r.id: r.status for r in rows}
    orphan = next(s for i, s in by_id.items() if i.startswith("t-orphan-running"))
    queued = next(s for i, s in by_id.items() if i.startswith("t-queued-pending"))
    assert orphan == "failed"
    assert queued == "pending"
