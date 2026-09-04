"""
OpenMAIC integration — REST endpoints for classroom generation bridge.

Routes:
  POST /api/integrations/openmaic/classroom  — 发起课堂生成
  GET  /api/integrations/openmaic/classrooms — 列出已生成课堂
  POST /api/integrations/openmaic/webhook    — OpenMAIC 回调端点
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.config import settings
from app.db import CourseSpace, User, get_db
from app.services import openmaic_service

router = APIRouter(prefix="/integrations/openmaic", tags=["OpenMAIC 联动"])
logger = logging.getLogger(__name__)


# ══ Schemas ═══════════════════════════════════════════════════════════════════


class ClassroomCreateRequest(BaseModel):
    doc_ids: list[str] = Field(..., max_length=5, description="文档 ID 列表（最多 5 篇）")
    requirement: str = Field(default="", max_length=500, description="课程主题/要求")
    enable_web_search: bool = Field(default=False)
    enable_tts: bool = Field(default=True)
    agent_mode: str = Field(default="default", pattern=r"^(default|generate)$")


class ClassroomResponse(BaseModel):
    class_id: str
    job_id: str
    status: str
    poll_url: str
    course_id: str | None = None
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


@router.post("/classroom", response_model=ClassroomResponse)
async def create_classroom(
    req: ClassroomCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """选择文档 + 主题 → 调用 OpenMAIC 生成课堂。

    返回 job_id，前端可通过它轮询进度或等待 webhook 回调。
    """
    if not settings.openmaic_enabled:
        raise HTTPException(status_code=403, detail="OpenMAIC 联动未启用")

    if not req.doc_ids:
        raise HTTPException(status_code=422, detail="至少选择一篇文档")

    try:
        payload = await openmaic_service.build_classroom_request(
            db, current_user,
            doc_ids=req.doc_ids,
            requirement=req.requirement,
            enable_web_search=req.enable_web_search,
            enable_tts=req.enable_tts,
            agent_mode=req.agent_mode,
        )
        result = await openmaic_service.submit_classroom_generation(payload)
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error("OpenMAIC classroom generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"OpenMAIC 请求失败: {e}")

    # 批次9修复：提交即落 pending 占位课（description 嵌 class_id）。
    # 原实现首个 classroom_completed 回调必然 ignored——没有任何课包含该
    # classroom_id，webhook 找不到归属用户（鸡生蛋）。占位课让回调可循迹，
    # completed 事件原地更新占位课而非重复建课
    class_id = result.get("id", "")
    if class_id:
        try:
            import json as _json

            from app.services.course_service import create_course_space
            placeholder = await create_course_space(
                db, current_user,
                name=req.requirement.strip()[:60] or "OpenMAIC 课堂（生成中）",
                description=_json.dumps({
                    "openmaic_pending": True,
                    "classroom_id": class_id,
                    "event": "classroom_submitted",
                }),
                color="#409EFF",
            )
            await db.commit()
            logger.info("OpenMAIC placeholder course: %s -> %s", class_id, placeholder.id)
        except Exception as e:  # noqa: BLE001
            logger.warning("placeholder course creation failed: %s", e)

    return ClassroomResponse(
        class_id=result.get("id", ""),
        job_id=result.get("jobId", ""),
        status=result.get("status", "queued"),
        poll_url=result.get("pollUrl", ""),
        message=result.get("message", "课堂生成已排队"),
    )


@router.get("/classrooms", response_model=ClassroomListResponse)
async def list_classrooms(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出当前用户通过 OpenMAIC 联动创建的课程。"""
    # 通过 description JSON 中 JSON 中包含 openmaic_url 来筛选
    result = await db.execute(
        select(CourseSpace)
        .where(CourseSpace.user_id == current_user.id)
        .order_by(CourseSpace.created_at.desc())
    )
    courses = result.scalars().all()

    classrooms = []
    for c in courses:
        if c.description and "openmaic_url" in str(c.description):
            try:
                meta = json.loads(c.description)
                classrooms.append({
                    "course_id": c.id,
                    "title": c.name,
                    "url": meta.get("openmaic_url", ""),
                    "created_at": str(c.created_at),
                })
            except Exception:  # noqa: BLE001
                pass

    return ClassroomListResponse(classrooms=classrooms, total=len(classrooms))


@router.post("/webhook")
async def openmaic_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """OpenMAIC 回调端点（无需 JWT，通过 HMAC 签名验证来源）。

    配置时 OpenMAIC 侧指向: https://your-domain/api/integrations/openmaic/webhook
    """
    body = await request.body()
    signature = request.headers.get("X-OpenMAIC-Signature", "")

    if not openmaic_service.verify_webhook_signature(body, signature):
        logger.warning("OpenMAIC webhook signature verification failed")
        raise HTTPException(status_code=403, detail="签名验证失败")

    try:
        payload = __import__("json").loads(body)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="Invalid JSON payload")

    # 找到对应 OpenMAIC 回调所涉及的 user（通过 classroom_id 查询最近创建的 course）
    # 批次9修复：classroom_id 必须是非空合法 ID 才参与 LIKE 匹配——
    # 原实现空串/超短串会退化成 LIKE '%%' 匹配任意课程，回调落在错误用户头上。
    # 顺带移除 or_(..., False) 死分支。LIKE 前转义 %/_ 通配符防注入匹配。
    classroom_id = (payload.get("classroom_id") or "").strip()
    if not classroom_id:
        raise HTTPException(status_code=422, detail="回调缺少 classroom_id")

    escaped = classroom_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    result = await db.execute(
        select(CourseSpace)
        .where(
            CourseSpace.user_id.isnot(None),
            CourseSpace.description.like(f'%{escaped}%'),
        )
        .order_by(CourseSpace.created_at.desc())
        .limit(1),
    )
    course = result.scalar_one_or_none()

    if not course:
        logger.warning("OpenMAIC webhook: no matching course for classroom_id=%s", classroom_id)
        return {"status": "ignored", "reason": "no_matching_course"}

    user = await db.get(User, course.user_id)
    if not user:
        return {"status": "ignored", "reason": "user_not_found"}

    # 批次9：把匹配到的占位课传下去，completed 事件原地更新而非重建
    action_result = await openmaic_service.handle_webhook_callback(
        db, user, payload, matched_course=course
    )
    return {"status": "ok", **action_result}


class QuizImportRequest(BaseModel):
    course_id: str | None = None
    quiz_results: list[dict] = Field(..., min_length=1, description="OpenMAIC 测验结果列表")


class QuizImportResponse(BaseModel):
    synced: int
    skipped: int


@router.post("/quiz/import", response_model=QuizImportResponse)
async def import_classroom_quizzes(
    req: QuizImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将 OpenMAIC 课堂测验结果导入 Study Copilot 的 Quiz 系统。

    支持两种来源：
    1. Webhook 自动推送（classroom_completed 事件）
    2. 前端手动导入（用户从课堂页面点击"导入测验结果"）
    """
    if not settings.openmaic_enabled:
        raise HTTPException(status_code=403, detail="OpenMAIC 联动未启用")

    result = await openmaic_service.sync_quiz_results(db, current_user, req.quiz_results)
    return QuizImportResponse(synced=result, skipped=len(req.quiz_results) - result)
