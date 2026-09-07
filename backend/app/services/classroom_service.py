"""
Classroom service — AI 互动课堂核心服务。

职责：
  1. 打包 Study Copilot 文档 → 提交 AI 互动课堂生成请求
  2. 提交课堂生成任务 + 轮询生成进度
  3. 接收课堂 Webhook 回调，自动创建/更新 CourseSpace 课程空间
  4. 同步课堂测验与答题记录到 Quiz 系统
  5. 容灾保障：当外部渲染服务不可达时，自动降级为本地课程大纲与测验生成
"""

import hashlib
import hmac
import json
import logging
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import CourseSpace, DocumentChunk, Quiz, QuizResult, User
from app.services import document_service
from app.services.course_service import add_document_to_course, create_course_space

logger = logging.getLogger(__name__)


def _check_enabled() -> None:
    """如果互动课堂未启用则报错。"""
    if not settings.classroom_enabled:
        raise RuntimeError("AI 互动课堂功能未启用（CLASSROOM_ENABLED=false）")


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
    enable_image_generation: bool = False,
    agent_mode: str = "default",
) -> dict[str, Any]:
    """组装课堂生成请求体。最多带 5 篇文档文本内容。"""
    _check_enabled()

    docs = []
    for doc_id in doc_ids[:5]:
        doc = await document_service.get_document(db, user, doc_id)
        text = await _read_document_text(db, doc_id)
        docs.append(
            {
                "text": text[:50_000],  # 单文档上限 50k 字符
                "filename": doc["filename"],
            }
        )

    return {
        "requirement": requirement or "请根据提供的材料生成课程",
        "pdfContent": [{"text": d["text"]} for d in docs] if docs else None,
        "enableWebSearch": enable_web_search,
        "enableTTS": enable_tts,
        "enableImageGeneration": enable_image_generation,
        "agentMode": agent_mode,
        "doc_ids": doc_ids,
    }


async def submit_classroom_generation(
    payload: dict[str, Any],
    db: AsyncSession | None = None,
    user: User | None = None,
) -> dict[str, Any]:
    """调用课堂引擎 POST /api/generate-classroom，返回 job 信息。

    若引擎不可达且提供了 db 和 user，自动降级为本地大纲与测验生成保底。
    """
    _check_enabled()

    base_url = (settings.classroom_base_url or "").rstrip("/")
    if base_url:
        url = f"{base_url}/api/generate-classroom"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            logger.info("Classroom generation submitted: jobId=%s", data.get("jobId", "?"))
            return data
        except Exception as e:
            logger.warning(
                "Classroom engine request failed (%s), attempting local fallback: %s", url, e
            )

    # 本地保底生成
    if db is not None and user is not None:
        try:
            from app.core.course_generator import generate_course, save_classroom_dsl_to_disk
            from app.services.course_service import add_document_to_course, create_course_space

            doc_ids = payload.get("doc_ids", [])
            req_text = payload.get("requirement", "AI 互动课程")
            course_data = await generate_course(
                db=db,
                user=user,
                doc_ids=doc_ids,
                requirement=req_text[:50],
                enable_image_generation=payload.get("enableImageGeneration", False),
            )
            job_id = f"local-{uuid4().hex[:10]}"
            course_space = await create_course_space(
                db=db,
                user=user,
                name=course_data.get("outline", {}).get("title") or req_text[:50] or "AI 互动课程",
                description="",
                color="#409EFF",
            )
            # 关联参考文档至课程空间
            for d_id in doc_ids:
                try:
                    await add_document_to_course(db, user, course_space.id, d_id)
                except Exception as add_err:
                    logger.warning("Failed to link doc %s to course %s: %s", d_id, course_space.id, add_err)

            classroom_url = f"/courses/{course_space.id}/classroom"
            classroom_data = course_data.get("classroom_data")
            if classroom_data:
                classroom_data["id"] = course_space.id
                classroom_data["url"] = classroom_url
                try:
                    save_classroom_dsl_to_disk(classroom_data)
                except Exception as disk_err:
                    logger.warning("Failed to write classroom DSL to disk: %s", disk_err)

            course_space.description = json.dumps(
                {
                    "classroom_url": classroom_url,
                    "classroom_id": course_space.id,
                    "job_id": job_id,
                    "event": "classroom_completed",
                    "outline": course_data.get("outline"),
                    "classroom_data": classroom_data,
                    "source_doc_ids": doc_ids,
                },
                ensure_ascii=False,
            )
            await db.commit()
            return {
                "jobId": job_id,
                "status": "succeeded",
                "done": True,
                "message": "已通过内置 AI 课程引擎完成大纲与课件生成",
                "pollUrl": "",
                "course_id": course_space.id,
                "url": classroom_url,
                "source_doc_ids": doc_ids,
                "result": {
                    "classroomId": course_space.id,
                    "url": classroom_url,
                    "title": course_space.name,
                },
            }
        except Exception as fallback_err:
            logger.error("Local fallback course generation failed: %s", fallback_err, exc_info=True)

    raise RuntimeError("AI 互动课堂服务暂时无法连接，请确认服务已启动。")


async def poll_generation_status(job_id: str) -> dict[str, Any]:
    """轮询课堂生成进度。"""
    _check_enabled()

    if job_id.startswith("local-"):
        return {
            "job_id": job_id,
            "status": "succeeded",
            "step": "completed",
            "progress": 100,
            "message": "本地课程已生成完毕",
            "done": True,
        }

    base_url = (settings.classroom_base_url or "").rstrip("/")
    url = f"{base_url}/api/generate-classroom/{job_id}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def sync_completed_classroom_job(
    db: AsyncSession,
    user: User,
    job_id: str,
    job_info: dict[str, Any],
) -> dict[str, Any] | None:
    """当轮询发现课堂任务完成时，就地更新占位课程并同步测验（双通道自愈）。"""
    raw_data = job_info.get("data") if isinstance(job_info, dict) else None
    payload: dict[str, Any] = (
        raw_data if isinstance(raw_data, dict) else (job_info if isinstance(job_info, dict) else {})
    )
    status = payload.get("status", "")
    is_done = payload.get("done") is True or status in ("succeeded", "completed")
    if not is_done:
        return None

    result = payload.get("result") or {}
    classroom_id = result.get("classroomId") or payload.get("classroomId") or job_id
    url = result.get("url") or payload.get("url") or ""
    title = result.get("title") or payload.get("title") or ""

    escaped = job_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    matched = await db.execute(
        select(CourseSpace)
        .where(
            CourseSpace.user_id == user.id,
            CourseSpace.description.like(f"%{escaped}%"),
        )
        .order_by(CourseSpace.created_at.desc())
        .limit(1)
    )
    course_row = matched.scalar_one_or_none()

    if not course_row and classroom_id:
        escaped_cid = classroom_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        matched_cid = await db.execute(
            select(CourseSpace)
            .where(
                CourseSpace.user_id == user.id,
                CourseSpace.description.like(f"%{escaped_cid}%"),
            )
            .order_by(CourseSpace.created_at.desc())
            .limit(1)
        )
        course_row = matched_cid.scalar_one_or_none()

    callback_payload = {
        "event": "classroom_completed",
        "classroom_id": classroom_id,
        "title": title
        or (course_row.name.replace("（生成中）", "") if course_row else "AI 互动课堂"),
        "url": url,
        "quiz_results": payload.get("quiz_results") or result.get("quiz_results") or [],
    }
    return await handle_webhook_callback(db, user, callback_payload, matched_course=course_row)


# ── Webhook 处理 ─────────────────────────────────────────────────────────────


def verify_webhook_signature(body: bytes, signature: str | None) -> bool:
    """验证课堂 webhook HMAC 签名。"""
    if not settings.classroom_webhook_secret:
        if settings.debug:
            logger.warning("CLASSROOM_WEBHOOK_SECRET 未配置且 DEBUG=True：开发模式放行（生产必配）")
            return True
        logger.error("CLASSROOM webhook 被拒绝：未配置 CLASSROOM_WEBHOOK_SECRET（fail-closed）")
        return False
    if not signature:
        return False
    expected = hmac.new(
        settings.classroom_webhook_secret.encode(),
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
    """处理课堂引擎回调，创建/更新 CourseSpace。"""
    event = payload.get("event", "")
    logger.info("Classroom webhook: event=%s", event)

    if event == "classroom_completed":
        existing_doc_ids = []
        if matched_course is not None:
            course_row = matched_course
            title = payload.get("title") or course_row.name
            course_row.name = title
            if course_row.description:
                try:
                    desc_obj = json.loads(course_row.description)
                    if isinstance(desc_obj, dict):
                        existing_doc_ids = desc_obj.get("source_doc_ids", [])
                except Exception:
                    pass
        else:
            course_row = await create_course_space(
                db,
                user,
                name=payload.get("title", "未命名课堂"),
                description=payload.get("description", ""),
                color="#409EFF",
            )

        doc_ids = payload.get("doc_ids") or payload.get("source_doc_ids") or existing_doc_ids
        for d_id in doc_ids:
            try:
                await add_document_to_course(db, user, course_row.id, d_id)
            except Exception as link_err:
                logger.warning("Failed to link doc %s to course %s in webhook: %s", d_id, course_row.id, link_err)

        course_row.description = json.dumps(
            {
                "classroom_url": payload.get("url", ""),
                "classroom_id": payload.get("classroom_id", ""),
                "description": payload.get("description", ""),
                "event": event,
                "source_doc_ids": doc_ids,
            },
            ensure_ascii=False,
        )
        await db.commit()

        # 同步 quiz 结果
        quiz_results = payload.get("quiz_results", [])
        synced = await sync_quiz_results(db, user, quiz_results)

        logger.info(
            "Classroom synced: course_id=%s, quizzes=%d",
            course_row.id,
            synced,
        )
        return {"course_id": course_row.id, "quizzes_synced": synced}

    return {"status": "ignored", "event": event}


# ── Quiz 同步 ────────────────────────────────────────────────────────────────


async def sync_quiz_results(
    db: AsyncSession,
    user: User,
    quiz_results: list[dict[str, Any]],
) -> int:
    """将课堂测验结果写入 Study Copilot 的 QuizResult 表。"""
    if not quiz_results:
        return 0

    count = 0
    for qr in quiz_results:
        try:
            quiz = Quiz(
                id=str(uuid4()),
                document_id=None,
                question_type="multiple_choice",
                question=qr.get("question", ""),
                options=json.dumps(qr.get("options", []), ensure_ascii=False),
                answer=qr.get("correct_answer", ""),
                explanation=qr.get("explanation", ""),
            )
            db.add(quiz)
            await db.flush()

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
