"""
Classroom integration — AI 互动课堂 REST 接口。

Routes:
  POST /api/classroom/generate  — 发起课堂生成
  GET  /api/classroom/list      — 列出已生成课堂
  GET  /api/classroom/{job_id}/status — 查询生成任务状态
  POST /api/classroom/webhook   — 课堂引擎回调端点
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.config import settings
from app.db import CourseSpace, User, get_db
from app.services import classroom_service

router = APIRouter(tags=["AI 互动课堂"])
logger = logging.getLogger(__name__)


# ══ Schemas ═══════════════════════════════════════════════════════════════════


class ClassroomCreateRequest(BaseModel):
    doc_ids: list[str] = Field(..., max_length=5, description="文档 ID 列表（最多 5 篇）")
    requirement: str = Field(default="", max_length=500, description="课程主题/要求")
    enable_web_search: bool = Field(default=False)
    enable_tts: bool = Field(default=True)
    enable_image_generation: bool = Field(default=False)
    agent_mode: str = Field(default="default", pattern=r"^(default|generate)$")


class ClassroomResponse(BaseModel):
    class_id: str
    job_id: str
    status: str
    poll_url: str
    course_id: str | None = None
    url: str | None = None
    message: str


class ClassroomListResponse(BaseModel):
    classrooms: list[dict]
    total: int


class WebhookPayload(BaseModel):
    event: str
    classroom_id: str
    title: str = ""
    description: str = ""
    url: str = ""
    quiz_results: list[dict] = []


# ══ Endpoints ════════════════════════════════════════════════════════════════


@router.post("/classroom/generate", response_model=ClassroomResponse)
@router.post("/classroom", response_model=ClassroomResponse)
async def create_classroom(
    req: ClassroomCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """选择文档 + 主题 → 发起 AI 互动课堂生成。"""
    if not settings.classroom_enabled:
        raise HTTPException(status_code=403, detail="AI 互动课堂功能未启用")

    if not req.doc_ids:
        raise HTTPException(status_code=422, detail="至少选择一篇文档")

    try:
        payload = await classroom_service.build_classroom_request(
            db, current_user,
            doc_ids=req.doc_ids,
            requirement=req.requirement,
            enable_web_search=req.enable_web_search,
            enable_tts=req.enable_tts,
            enable_image_generation=req.enable_image_generation,
            agent_mode=req.agent_mode,
        )
        result = await classroom_service.submit_classroom_generation(
            payload,
            db=db,
            user=current_user,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error("Classroom generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"课堂生成请求失败: {e}")

    class_id = result.get("id", "") or result.get("jobId", "")
    job_id = result.get("jobId", class_id)
    course_id = result.get("course_id")
    url = result.get("url")

    # 如果非本地已建课，提交即落 pending 占位课（description 嵌 class_id）
    if class_id and not course_id:
        try:
            from app.services.course_service import create_course_space
            placeholder = await create_course_space(
                db, current_user,
                name=req.requirement.strip()[:60] or "AI 互动课堂（生成中）",
                description=json.dumps({
                    "classroom_pending": True,
                    "classroom_id": class_id,
                    "job_id": job_id,
                    "requirement": req.requirement.strip(),
                    "event": "classroom_submitted",
                }, ensure_ascii=False),
                color="#409EFF",
            )
            await db.commit()
            course_id = placeholder.id
            logger.info("Classroom placeholder course: %s -> %s", class_id, course_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("Placeholder course creation failed: %s", e)

    return ClassroomResponse(
        class_id=class_id,
        job_id=job_id,
        status=result.get("status", "queued"),
        poll_url=result.get("pollUrl", ""),
        course_id=course_id,
        url=url,
        message=result.get("message", "课堂生成已排队"),
    )


@router.get("/classroom/{job_id}/status")
async def get_classroom_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询 AI 互动课堂生成任务状态并实现双通道自愈。"""
    if not settings.classroom_enabled:
        raise HTTPException(status_code=403, detail="AI 互动课堂功能未启用")

    try:
        data = await classroom_service.poll_generation_status(job_id)
    except Exception as e:
        logger.warning("Failed to poll classroom job status for %s: %s", job_id, e)
        raise HTTPException(status_code=502, detail=f"查询课堂任务状态失败: {e}")

    # 尝试自动就地同步
    sync_result = None
    try:
        sync_result = await classroom_service.sync_completed_classroom_job(
            db, current_user, job_id, data
        )
    except Exception as sync_err:
        logger.warning("Auto sync completed classroom failed for job %s: %s", job_id, sync_err)

    status_str = data.get("status", "unknown")
    is_done = data.get("done") is True or status_str in ("succeeded", "completed")

    return {
        "job_id": job_id,
        "status": status_str,
        "step": data.get("step", ""),
        "progress": data.get("progress", 100 if is_done else 0),
        "message": data.get("message", ""),
        "scenes_generated": data.get("scenes_generated", 0),
        "total_scenes": data.get("total_scenes", 0),
        "done": is_done,
        "result": data.get("result"),
        "sync_result": sync_result,
    }


@router.get("/classroom/list", response_model=ClassroomListResponse)
@router.get("/classroom/classrooms", response_model=ClassroomListResponse)
async def list_classrooms(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出当前用户的所有 AI 互动课堂。"""
    if not settings.classroom_enabled:
        raise HTTPException(status_code=403, detail="AI 互动课堂功能未启用")

    # 兼容 classroom_url 与历史数据
    result = await db.execute(
        select(CourseSpace)
        .where(
            CourseSpace.user_id == current_user.id,
            CourseSpace.description.like("%classroom_id%"),
        )
        .order_by(CourseSpace.created_at.desc())
    )
    courses = result.scalars().all()

    classrooms = []
    for c in courses:
        url = ""
        try:
            desc = json.loads(c.description)
            url = desc.get("classroom_url", "")
        except (json.JSONDecodeError, TypeError):
            pass

        classrooms.append({
            "course_id": c.id,
            "title": c.name,
            "url": url,
            "created_at": c.created_at.isoformat() if c.created_at else "",
        })

    return ClassroomListResponse(
        classrooms=classrooms,
        total=len(classrooms),
    )


@router.post("/classroom/webhook")
async def classroom_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """课堂引擎回调端点。"""
    body = await request.body()
    signature = request.headers.get("x-classroom-signature")

    if not classroom_service.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="签名校验失败")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效 JSON")

    classroom_id = payload.get("classroom_id")
    if not classroom_id:
        raise HTTPException(status_code=422, detail="缺少 classroom_id")

    escaped = classroom_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    matched = await db.execute(
        select(CourseSpace)
        .where(CourseSpace.description.like(f"%{escaped}%"))
        .order_by(CourseSpace.created_at.desc())
        .limit(1)
    )
    course_row = matched.scalar_one_or_none()

    user: User | None = None
    if course_row:
        user_res = await db.execute(
            select(User).where(User.id == course_row.user_id)
        )
        user = user_res.scalar_one_or_none()

    if not user:
        first_user_res = await db.execute(select(User).limit(1))
        user = first_user_res.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=500, detail="无可用的用户上下文")

    result = await classroom_service.handle_webhook_callback(
        db, user, payload, matched_course=course_row
    )
    return {"status": "ok", "result": result}
