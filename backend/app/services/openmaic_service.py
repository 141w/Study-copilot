"""
OpenMAIC bridge service — 与 OpenMAIC 课堂平台的联动。

职责：
  1. 打包 Study Copilot 文档 → OpenMAIC classroom generation 请求
  2. 提交课堂生成任务 + 轮询状态
  3. 接收 OpenMAIC webhook 回调，创建 CourseSpace
  4. 同步课堂测验结果到 Quiz 系统

仅当 settings.openmaic_enabled 为 True 时可用。
"""

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import CourseSpace, DocumentChunk, User
from app.services import document_service
from app.services.course_service import create_course_space

logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────────────────────────────


def _check_enabled() -> None:
    """如果 OpenMAIC 联动未启用则直接返回，调用方应提前判断。"""
    if not settings.openmaic_enabled or not settings.openmaic_base_url:
        raise RuntimeError("OpenMAIC 联动未启用（OPENMAIC_ENABLED=false 或 BASE_URL 为空）")


# ── 文档内容提取 ─────────────────────────────────────────────────────────────


async def _read_document_text(db: AsyncSession, doc_id: str) -> str:
    """从 DocumentChunk 提取原文拼成连续文本。"""
    result = await db.execute(
        select(DocumentChunk.content)
        .where(DocumentChunk.document_id == doc_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = [row[0] for row in result.all()]
    return "\n\n".join(chunks)


# ── Classroom Generation ─────────────────────────────────────────────────────


async def build_classroom_request(
    db: AsyncSession,
    user: User,
    doc_ids: list[str],
    requirement: str,
    enable_web_search: bool = False,
    enable_tts: bool = True,
    agent_mode: str = "default",
) -> dict[str, Any]:
    """组装 OpenMAIC generate-classroom 请求体。

    最多带 5 篇文档的文本内容（OpenMAIC 限制）。
    """
    _check_enabled()

    docs = []
    for doc_id in doc_ids[:5]:
        doc = await document_service.get_document(db, user, doc_id)
        text = await _read_document_text(db, doc_id)
        docs.append({
            "text": text[:50_000],  # 单文档上限 50k 字符
            "filename": doc["filename"],
        })

    return {
        "requirement": requirement or "请根据提供的材料生成课程",
        "pdfContent": [{"text": d["text"]} for d in docs] if docs else None,
        "enableWebSearch": enable_web_search,
        "enableTTS": enable_tts,
        "agentMode": agent_mode,
    }


async def submit_classroom_generation(payload: dict[str, Any]) -> dict[str, Any]:
    """调用 OpenMAIC POST /api/generate-classroom，返回 job 信息。"""
    _check_enabled()

    url = f"{settings.openmaic_base_url.rstrip('/')}/api/generate-classroom"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    logger.info(
        "OpenMAIC classroom submitted: jobId=%s", data.get("jobId", "?")
    )
    return data


async def poll_generation_status(job_id: str) -> dict[str, Any]:
    """轮询 OpenMAIC 课堂生成进度。"""
    _check_enabled()

    url = f"{settings.openmaic_base_url.rstrip('/')}/api/generate-classroom/{job_id}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


# ── Webhook 处理 ─────────────────────────────────────────────────────────────


def verify_webhook_signature(body: bytes, signature: str | None) -> bool:
    """验证 OpenMAIC webhook HMAC 签名。

    批次9修复：webhook 是全站唯一免 JWT 的写端点，原实现
    在 OPENMAIC_WEBHOOK_SECRET 未配置时直接放行（return True），
    任何人可伪造 classroom_completed 回调创建课程并写入测验结果。
    改为 fail-closed：未配置密钥一律拒绝；仅显式 DEBUG=True 的
    本地开发环境允许无签名调用，生产（DEBUG=False）必配密钥。
    """
    if not settings.openmaic_webhook_secret:
        if settings.debug:
            logger.warning(
                "OPENMAIC_WEBHOOK_SECRET 未配置且 DEBUG=True：开发模式放行（生产必配）"
            )
            return True
        logger.error(
            "OPENMAIC webhook 被拒绝：未配置 OPENMAIC_WEBHOOK_SECRET（fail-closed）"
        )
        return False
    if not signature:
        return False
    expected = hmac.new(
        settings.openmaic_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle_webhook_callback(
    db: AsyncSession,
    user: User,
    payload: dict[str, Any],
    matched_course: CourseSpace | None = None,
) -> dict[str, Any]:
    """处理 OpenMAIC 回调，创建/更新 CourseSpace。

    批次9修复：提交时已创建 pending 占位课（description 嵌 classroom_id），
    completed 回调应原地更新占位课（matched_course），而非重复建新课。
    matched_course 为 None（历史数据/占位丢失）时回退为创建。

    回调 payload 预期格式：
    {
        "event": "classroom_completed",
        "classroom_id": "...",
        "title": "...",
        "description": "...",
        "url": "https://...",
        "quiz_results": [...],   // 可选
        "stage_summary": {...}   // 可选
    }
    """
    event = payload.get("event", "")
    logger.info("OpenMAIC webhook: event=%s", event)

    if event == "classroom_completed":
        if matched_course is not None:
            # 原地更新占位课：正名 + 落 URL/完成态
            course_row = matched_course
            title = payload.get("title") or course_row.name
            course_row.name = title
        else:
            course_row = await create_course_space(
                db, user,
                name=payload.get("title", "未命名课堂"),
                description=payload.get("description", ""),
                color="#409EFF",
            )
        import json as _json
        course_row.description = _json.dumps({
            "openmaic_url": payload.get("url", ""),
            "classroom_id": payload.get("classroom_id", ""),
            "event": event,
        })
        await db.commit()

        # 同步 quiz 结果
        quiz_results = payload.get("quiz_results", [])
        synced = await sync_quiz_results(db, user, quiz_results)

        logger.info(
            "OpenMAIC classroom synced: course_id=%s, quizzes=%d",
            course_row.id, synced,
        )
        return {"course_id": course_row.id, "quizzes_synced": synced}

    return {"status": "ignored", "event": event}


# ── Quiz 同步 ────────────────────────────────────────────────────────────────


async def sync_quiz_results(
    db: AsyncSession,
    user: User,
    quiz_results: list[dict[str, Any]],
) -> int:
    """将 OpenMAIC 课堂测验结果写入 Study Copilot 的 QuizResult 表。

    quiz_results 每项: { question, user_answer, correct_answer, is_correct, classroom_id }
    返回同步的 quiz 数量。
    """
    if not quiz_results:
        return 0

    from uuid import uuid4

    from app.db import Quiz, QuizResult

    count = 0
    for qr in quiz_results:
        try:
            # 批次9修复：原实现 Quiz 缺 id（PK NOT NULL 直接 IntegrityError），
            # 且 quiz_id=quiz.id 读到的是 None。显式生成 UUID 主键
            quiz = Quiz(
                id=str(uuid4()),
                document_id=None,  # 课堂来源，非文档
                question_type="multiple_choice",
                question=qr.get("question", ""),
                options=json.dumps(qr.get("options", []), ensure_ascii=False),
                answer=qr.get("correct_answer", ""),
                explanation=qr.get("explanation", ""),
            )
            db.add(quiz)
            await db.flush()

            # 批次9修复：QuizResult 同样缺 id 主键（NOT NULL PK 失败被 best-effort
            # except 吞掉 → 每条静默跳过、count 却不增 → webhook 报 synced=0 但 200 OK）
            result = QuizResult(
                id=str(uuid4()),
                quiz_id=quiz.id,
                user_id=user.id,
                user_answer=qr.get("user_answer", ""),
                is_correct=qr.get("is_correct", False),
            )
            db.add(result)
            count += 1
        except Exception:  # noqa: BLE001 — best-effort
            logger.warning("Failed to sync quiz result: %s", qr, exc_info=True)

    await db.commit()
    return count
