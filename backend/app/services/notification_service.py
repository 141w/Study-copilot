"""Task-derived notifications: terminal AsyncTask → user-visible notice with jump link."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncTask
from app.utils.timefmt import isoformat_utc

logger = logging.getLogger(__name__)

# 只把终态任务展示为通知
_TERMINAL = ("completed", "failed", "cancelled")


def _parse_result(task: AsyncTask) -> dict[str, Any]:
    if not task.result:
        return {}
    try:
        data = json.loads(task.result)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def build_notification(task: AsyncTask) -> dict[str, Any]:
    """Map AsyncTask → notification payload with human title and jump route."""
    result = _parse_result(task)
    ttype = task.task_type or ""
    status = task.status or ""
    filename = result.get("filename") or result.get("document_names")
    if isinstance(filename, list):
        filename = "、".join(str(x) for x in filename[:3])
    filename = str(filename) if filename else ""
    short_name = (filename[:24] + "…") if len(filename) > 24 else filename

    title = "任务完成"
    body = ""
    link = "/tasks"
    icon = "success"
    level = "success"

    if status == "failed":
        icon = "error"
        level = "error"
        title = "任务失败"
        body = (task.error or "处理过程中出现错误")[:160]
        if short_name:
            body = f"《{short_name}》{body}" if not body.startswith("《") else body
    elif status == "cancelled":
        icon = "info"
        level = "info"
        title = "任务已取消"
        body = short_name or ttype
    elif ttype == "document_process":
        title = "文档解析完成"
        body = f"《{short_name or '文档'}》已可检索"
        doc_id = result.get("doc_id") or ""
        link = f"/documents?document_id={doc_id}" if doc_id else "/documents"
        if result.get("chunk_count"):
            body += f"（{result['chunk_count']} 段）"
    elif ttype == "quiz_generate":
        title = "测验生成完成"
        body = "可前往做题巩固"
        link = "/quiz"
        if short_name:
            body = f"基于《{short_name}》{body}"
    elif ttype == "classroom_generate":
        title = "互动课堂生成完成"
        body = "可打开课堂播放"
        course_id = result.get("course_id") or (result.get("result") or {}).get("classroomId")
        link = f"/courses/{course_id}/classroom" if course_id else "/courses"
    elif ttype == "tts_generate":
        title = "语音合成完成"
        body = short_name or "TTS 音频已就绪"
        link = "/tasks"
    else:
        title = f"{ttype or '后台'}任务完成"
        body = short_name or "处理完成"

    return {
        "id": task.id,
        "task_id": task.id,
        "task_type": ttype,
        "status": status,
        "level": level,
        "icon": icon,
        "title": title,
        "body": body,
        "link": link,
        "read": task.read_at is not None,
        "created_at": isoformat_utc(task.created_at),
        "completed_at": isoformat_utc(task.completed_at),
    }


async def list_notifications(
    db: AsyncSession,
    user_id: str,
    *,
    limit: int = 20,
    unread_only: bool = False,
) -> list[dict[str, Any]]:
    """Recent terminal tasks as notifications (newest first)."""
    stmt = (
        select(AsyncTask)
        .where(AsyncTask.user_id == user_id, AsyncTask.status.in_(_TERMINAL))
        .order_by(AsyncTask.completed_at.desc().nullslast(), AsyncTask.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(AsyncTask.read_at.is_(None))
    res = await db.execute(stmt)
    return [build_notification(t) for t in res.scalars().all()]


async def unread_count(db: AsyncSession, user_id: str) -> int:
    from sqlalchemy import func

    res = await db.execute(
        select(func.count())
        .select_from(AsyncTask)
        .where(
            AsyncTask.user_id == user_id,
            AsyncTask.status.in_(_TERMINAL),
            AsyncTask.read_at.is_(None),
        )
    )
    return int(res.scalar() or 0)


async def mark_read(db: AsyncSession, user_id: str, task_id: str) -> bool:
    res = await db.execute(
        select(AsyncTask).where(AsyncTask.id == task_id, AsyncTask.user_id == user_id)
    )
    task = res.scalar_one_or_none()
    if not task or task.read_at is not None:
        return False
    task.read_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    return True


async def mark_all_read(db: AsyncSession, user_id: str) -> int:
    from sqlalchemy import update

    now = datetime.now(UTC).replace(tzinfo=None)
    res = await db.execute(
        update(AsyncTask)
        .where(
            AsyncTask.user_id == user_id,
            AsyncTask.status.in_(_TERMINAL),
            AsyncTask.read_at.is_(None),
        )
        .values(read_at=now)
    )
    rowcount = getattr(res, "rowcount", None) or 0
    await db.commit()
    return int(rowcount)
