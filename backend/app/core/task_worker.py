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

# AI 互动课堂涉及多幕大纲编排、剧本生成、多角色TTS语音合成与AI生图，通常耗时较长（10-30分钟）。
# 设置独立的整体超时上限（默认 3600s）与停滞看门狗上限（默认 600s 无任何进展则判定挂起）。
CLASSROOM_TASK_TIMEOUT_SEC = int(os.environ.get("CLASSROOM_TASK_TIMEOUT_SEC", "3600"))
CLASSROOM_STALL_TIMEOUT_SEC = int(os.environ.get("CLASSROOM_STALL_TIMEOUT_SEC", "600"))

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
        timeout = TASK_TIMEOUT_SEC
        try:
            if job.task_type == "document_process":
                timeout = TASK_TIMEOUT_SEC
                result = await asyncio.wait_for(
                    _run_document_process(job, db), timeout=timeout
                )
            elif job.task_type == "quiz_generate":
                timeout = TASK_TIMEOUT_SEC
                result = await asyncio.wait_for(
                    _run_quiz_generate(job, db), timeout=timeout
                )
            elif job.task_type == "classroom_generate":
                timeout = CLASSROOM_TASK_TIMEOUT_SEC
                result = await asyncio.wait_for(
                    _run_classroom_generate(job, db), timeout=timeout
                )
            else:
                raise ValueError(f"Unknown type: {job.task_type}")
            await update_task(
                db, job.task_id, job.user_id, status="completed", progress=1.0, result=result
            )
        except TimeoutError as te:
            # 看门狗：任务卡死（如模型下载被代理挂起或外部服务停滞）时转为可见失败，
            # 而非永远停留在 running 让前端显示假进度。
            await db.rollback()  # 被取消的协程可能留下失效事务
            logger.error("Task %s timed out after %ss", job.task_id, timeout)
            custom_msg = str(te).strip()
            if custom_msg and not custom_msg.isdigit():
                err_msg = custom_msg
            elif job.task_type == "document_process":
                err_msg = (
                    f"文档处理超时（超过 {timeout}s 未完成），已中止。"
                    "常见原因：文档体积过大或 Embedding 模型下载受网络/代理限制。"
                )
            elif job.task_type == "quiz_generate":
                err_msg = (
                    f"智能测验生成超时（超过 {timeout}s 未完成），已中止。"
                    "常见原因：大模型响应过慢或连接受阻，请稍后重试。"
                )
            elif job.task_type == "classroom_generate":
                err_msg = (
                    f"AI 互动课堂生成超时（超过 {timeout}s 未完成），已中止。"
                    "常见原因：多幕音视频与 AI 生图耗时较长，或外部生图/语音模型响应超时。"
                )
            else:
                err_msg = f"任务超时（超过 {timeout}s 未完成），已中止。"

            await update_task(
                db,
                job.task_id,
                job.user_id,
                status="failed",
                progress=0.0,
                error=err_msg,
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

    from app.db import Document, User
    from app.services.document_service import _do_process_document

    doc_id = job.payload.get("doc_id")
    result = await db.execute(select(User).where(User.id == job.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    doc = await db.get(Document, doc_id)
    filename = doc.filename if doc else job.payload.get("filename", "")

    async def progress_cb(p: float, msg: str) -> None:
        try:
            await update_task(db, job.task_id, job.user_id, progress=p)
            logger.debug("Task %s progress %.2f: %s", job.task_id, p, msg)
        except Exception as exc:
            logger.warning("Failed to update task progress for %s: %s", job.task_id, exc)

    chunk_count, method = await _do_process_document(
        db, user, doc_id, progress_callback=progress_cb
    )
    return {"doc_id": doc_id, "filename": filename, "chunk_count": chunk_count, "method": method}


async def _run_quiz_generate(job, db):
    """Generate quizzes in background."""
    from sqlalchemy import select

    from app.db import Document, User
    from app.services.quiz_service import _do_generate_quiz

    doc_ids = job.payload.get("document_ids", [])
    choice_cnt = job.payload.get("choice_count", 3)
    short_cnt = job.payload.get("short_answer_count", 2)
    result = await db.execute(select(User).where(User.id == job.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    doc_titles = []
    for d_id in doc_ids:
        doc_obj = await db.get(Document, d_id)
        if doc_obj and doc_obj.filename:
            doc_titles.append(doc_obj.filename)

    quizzes = await _do_generate_quiz(db, user, doc_ids, choice_cnt, short_cnt)
    return {
        "quiz_count": len(quizzes),
        "document_ids": doc_ids,
        "document_names": doc_titles,
        "choice_count": choice_cnt,
        "short_answer_count": short_cnt,
    }


async def _run_classroom_generate(job, db):
    """Background runner for classroom generation: poll OpenMAIC and track progress."""
    from sqlalchemy import select

    from app.db import User
    from app.services import classroom_service

    result = await db.execute(select(User).where(User.id == job.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError(f"User {job.user_id} not found")

    job_id = job.payload.get("job_id")
    if not job_id:
        raise ValueError("Missing job_id for classroom generation")

    course_id = job.payload.get("course_id")
    title = job.payload.get("title", "AI 互动课堂")
    poll_interval = 2.0

    import time
    last_active_time = time.time()
    last_state = None

    while True:
        try:
            status_info = await classroom_service.poll_generation_status(job_id)
        except Exception as poll_err:
            logger.warning("Failed to poll classroom job %s: %s", job_id, poll_err)
            if time.time() - last_active_time > CLASSROOM_STALL_TIMEOUT_SEC:
                raise TimeoutError(
                    f"AI 互动课堂生成服务连续 {CLASSROOM_STALL_TIMEOUT_SEC}s 无法连接，可能服务已中断。"
                )
            await asyncio.sleep(poll_interval)
            continue

        raw_progress = status_info.get("progress", 0)
        # OpenMAIC 返回 0-100，AsyncTask.progress 采用 0.0-1.0 浮点数
        progress_val = min(0.99, max(0.05, float(raw_progress) / 100.0))

        step_msg = status_info.get("message") or status_info.get("step") or "正在生成课堂场景..."
        scenes_generated = status_info.get("scenes_generated", 0)
        total_scenes = status_info.get("total_scenes", 0)

        # 动态停滞（Stall）看门狗：只要阶段更新、分幕数推进或进度增加，即刷新活跃时钟
        current_state = (raw_progress, step_msg, scenes_generated)
        if current_state != last_state:
            last_active_time = time.time()
            last_state = current_state
        elif time.time() - last_active_time > CLASSROOM_STALL_TIMEOUT_SEC:
            raise TimeoutError(
                f"AI 互动课堂生成在步骤「{step_msg}」停滞超过 {CLASSROOM_STALL_TIMEOUT_SEC}s 无响应，已中止。"
            )

        await update_task(
            db,
            job.task_id,
            job.user_id,
            status="running",
            progress=progress_val,
            result={
                **job.payload,
                "title": title,
                "course_id": course_id,
                "message": step_msg,
                "step": status_info.get("step"),
                "scenes_generated": scenes_generated,
                "total_scenes": total_scenes,
            },
        )

        if status_info.get("done"):
            if status_info.get("status") == "failed":
                err = status_info.get("error") or "AI 互动课堂引擎生成失败"
                raise RuntimeError(err)

            # 同步完成状态及测验结果至 CourseSpace
            try:
                await classroom_service.sync_completed_classroom_job(
                    db, user, job_id, status_info
                )
            except Exception as sync_err:
                logger.warning("Failed to sync completed classroom in worker: %s", sync_err)

            res_data = status_info.get("result") or {}
            cid = (
                res_data.get("classroomId")
                or res_data.get("id")
                or job.payload.get("classroom_id")
                or job_id
            )
            return {
                **job.payload,
                "title": title,
                "course_id": course_id,
                "classroom_id": cid,
                "url": f"/courses/{course_id}/classroom" if course_id else f"/classroom-engine/classroom/{cid}",
                "message": "互动课堂已生成完成，可打开播放",
                "scenes_generated": status_info.get("scenes_generated", 0),
                "total_scenes": status_info.get("total_scenes", 0),
            }

        await asyncio.sleep(poll_interval)
