"""
In-process background task worker.
Runs CPU-bound operations (parsing, chunking, embedding) in the event loop's
thread pool via the service layer.
"""

import asyncio
import logging
import os

from app.db.database import AsyncSessionLocal
from app.services.task_service import update_task

logger = logging.getLogger(__name__)

# 看门狗：单任务最长执行时间。超时转为 failed，避免环境故障（如模型
# 下载被代理挂起）让任务永远停留在 running、前端显示假进度。
TASK_TIMEOUT_SEC = int(os.environ.get("TASK_TIMEOUT_SEC", "600"))

# 持久化队列：任务以 pending 行落库，worker 轮询认领。
# 重启后未认领的 pending 行会被新进程继续执行，不再丢失。
POLL_INTERVAL_SEC = float(os.environ.get("TASK_POLL_INTERVAL_SEC", "1.0"))

_worker_task = None


class TaskJob:
    def __init__(self, task_id, user_id, task_type, payload):
        self.task_id = task_id
        self.user_id = user_id
        self.task_type = task_type
        self.payload = payload


async def start_worker():
    global _worker_task
    if _worker_task is not None:
        return
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Background worker started (poll interval %.1fs)", POLL_INTERVAL_SEC)


async def stop_worker():
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None
    logger.info("Background worker stopped")


async def enqueue(task_id, user_id, task_type, payload):
    """兼容入口：pending 任务行已提交入库，轮询型 worker 会自动认领。

    保留 RuntimeError 语义——worker 未启动时调用方（如 upload）据此走同步回退。
    """
    if _worker_task is None:
        raise RuntimeError("Worker not started")
    logger.debug("Task %s persisted as pending (poll-based queue)", task_id)


async def _claim_next_job():
    """认领最早已提交的 pending 任务（FOR UPDATE SKIP LOCKED，多 worker 安全）。"""
    import json

    from sqlalchemy import select

    from app.db import AsyncTask

    async with AsyncSessionLocal() as db:
        query = (
            select(AsyncTask)
            .where(AsyncTask.status == "pending")
            .order_by(AsyncTask.created_at.asc())
            .limit(1)
        )
        # 行锁仅 PG 有意义；SQLite 加该子句会静默返回空集，故按方言条件启用
        if db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        result = await db.execute(query)
        task = result.scalar_one_or_none()
        if task is None:
            return None
        task.status = "running"
        await db.commit()

        payload = {}
        if task.result:
            try:
                payload = json.loads(task.result)
            except json.JSONDecodeError:
                payload = {}
        return TaskJob(task.id, task.user_id, task.task_type, payload)


async def _worker_loop():
    while True:
        try:
            job = await _claim_next_job()
            if job is None:
                await asyncio.sleep(POLL_INTERVAL_SEC)
                continue
            try:
                await _execute_job(job)
            except Exception as e:
                logger.error("Task %s error: %s", job.task_id, e)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Worker loop: %s", e)


async def _execute_job(job):
    logger.info("Executing %s (%s)", job.task_id, job.task_type)
    async with AsyncSessionLocal() as db:
        await update_task(db, job.task_id, job.user_id, status="running")
        try:
            if job.task_type == "document_process":
                result = await asyncio.wait_for(
                    _run_document_process(job, db), timeout=TASK_TIMEOUT_SEC
                )
            elif job.task_type == "quiz_generate":
                result = await asyncio.wait_for(
                    _run_quiz_generate(job, db), timeout=TASK_TIMEOUT_SEC
                )
            else:
                raise ValueError(f"Unknown type: {job.task_type}")
            await update_task(
                db, job.task_id, job.user_id, status="completed", progress=1.0, result=result
            )
        except TimeoutError:
            # 看门狗：任务卡死（典型如模型下载被代理挂起）时转为可见失败，
            # 而非永远停留在 running 让前端显示假进度。
            await db.rollback()  # 被取消的协程可能留下失效事务
            logger.error("Task %s timed out after %ss", job.task_id, TASK_TIMEOUT_SEC)
            await update_task(
                db,
                job.task_id,
                job.user_id,
                status="failed",
                progress=0.0,
                error=(
                    f"任务超时（超过 {TASK_TIMEOUT_SEC}s 未完成），已中止。"
                    "常见原因：Embedding 模型下载受网络/代理限制。"
                ),
            )
            if job.task_type == "document_process":
                doc_id = job.payload.get("doc_id")
                if doc_id:
                    from app.db import Document
                    doc = await db.get(Document, doc_id)
                    if doc and doc.status in ("pending", "processing"):
                        doc.status = "error"
                        await db.commit()
        except Exception as e:
            await db.rollback()
            await update_task(
                db, job.task_id, job.user_id, status="failed", progress=0.0, error=str(e)
            )
            if job.task_type == "document_process":
                doc_id = job.payload.get("doc_id")
                if doc_id:
                    from app.db import Document
                    doc = await db.get(Document, doc_id)
                    if doc and doc.status in ("pending", "processing"):
                        doc.status = "error"
                        await db.commit()


async def _run_document_process(job, db):
    """Parse -> chunk -> index a document in background."""
    from sqlalchemy import select

    from app.db import User
    from app.services.document_service import _do_process_document

    doc_id = job.payload.get("doc_id")
    result = await db.execute(select(User).where(User.id == job.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    async def progress_cb(p: float, msg: str) -> None:
        try:
            await update_task(db, job.task_id, job.user_id, progress=p)
            logger.debug("Task %s progress %.2f: %s", job.task_id, p, msg)
        except Exception as exc:
            logger.warning("Failed to update task progress for %s: %s", job.task_id, exc)

    chunk_count, method = await _do_process_document(
        db, user, doc_id, progress_callback=progress_cb
    )
    return {"doc_id": doc_id, "chunk_count": chunk_count, "method": method}


async def _run_quiz_generate(job, db):
    """Generate quizzes in background."""
    from sqlalchemy import select

    from app.db import User
    from app.services.quiz_service import _do_generate_quiz

    doc_ids = job.payload.get("document_ids", [])
    choice_cnt = job.payload.get("choice_count", 3)
    short_cnt = job.payload.get("short_answer_count", 2)
    result = await db.execute(select(User).where(User.id == job.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    quizzes = await _do_generate_quiz(db, user, doc_ids, choice_cnt, short_cnt)
    return {"quiz_count": len(quizzes)}
