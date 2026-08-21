"""
In-process background task worker.
Runs CPU-bound operations (parsing, chunking, embedding) in the event loop's
thread pool via the service layer.
"""

import asyncio
import logging

from app.db.database import AsyncSessionLocal
from app.services.task_service import update_task

logger = logging.getLogger(__name__)

_task_queue = None
_worker_task = None


class TaskJob:
    def __init__(self, task_id, user_id, task_type, payload):
        self.task_id = task_id
        self.user_id = user_id
        self.task_type = task_type
        self.payload = payload


async def start_worker():
    global _task_queue, _worker_task
    if _worker_task is not None:
        return
    _task_queue = asyncio.Queue()
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Background worker started")


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
    if _task_queue is None:
        raise RuntimeError("Worker not started")
    await _task_queue.put(TaskJob(task_id, user_id, task_type, payload))
    logger.info("Enqueued task %s: %s", task_id, task_type)


async def _worker_loop():
    while True:
        try:
            job = await _task_queue.get()
            try:
                await _execute_job(job)
            except Exception as e:
                logger.error("Task %s error: %s", job.task_id, e)
            finally:
                _task_queue.task_done()
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
                result = await _run_document_process(job, db)
            elif job.task_type == "quiz_generate":
                result = await _run_quiz_generate(job, db)
            else:
                raise ValueError(f"Unknown type: {job.task_type}")
            await update_task(
                db, job.task_id, job.user_id, status="completed", progress=1.0, result=result
            )
        except Exception as e:
            await update_task(
                db, job.task_id, job.user_id, status="failed", progress=0.0, error=str(e)
            )


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

    chunk_count, method = await _do_process_document(db, user, doc_id)
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
