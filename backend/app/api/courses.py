import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db
from app.services import course_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/courses", tags=["课程空间"])


# ── Schemas ─────────────────────────────────────────────────────────────


class CourseCreate(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None


class CourseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class CourseResponse(BaseModel):
    id: str
    name: str
    description: str | None
    color: str | None
    created_at: str
    updated_at: str
    document_count: int = 0
    note_count: int = 0


class AddDocRequest(BaseModel):
    document_id: str


class CourseDocResponse(BaseModel):
    id: str
    filename: str
    status: str
    chunk_count: int
    file_size: int | None = None
    created_at: str


# ── Endpoints ───────────────────────────────────────────────────────────


@router.post("", response_model=CourseResponse)
async def create_course(
    data: CourseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = await course_service.create_course_space(
        db, current_user, data.name, data.description, data.color
    )
    counts = await course_service.get_courses_counts(db, current_user, [course])
    return CourseResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        color=course.color,
        created_at=str(course.created_at),
        updated_at=str(course.updated_at),
        document_count=counts.get(course.id, {}).get("document_count", 0),
        note_count=counts.get(course.id, {}).get("note_count", 0),
    )


@router.get("", response_model=list[CourseResponse])
async def list_courses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    courses = await course_service.list_course_spaces(db, current_user)
    counts = await course_service.get_courses_counts(db, current_user, courses)
    return [
        CourseResponse(
            id=c.id,
            name=c.name,
            description=c.description,
            color=c.color,
            created_at=str(c.created_at),
            updated_at=str(c.updated_at),
            document_count=counts.get(c.id, {}).get("document_count", 0),
            note_count=counts.get(c.id, {}).get("note_count", 0),
        )
        for c in courses
    ]


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = await course_service.get_course_space(db, current_user, course_id)
    counts = await course_service.get_courses_counts(db, current_user, [course])
    return CourseResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        color=course.color,
        created_at=str(course.created_at),
        updated_at=str(course.updated_at),
        document_count=counts.get(course.id, {}).get("document_count", 0),
        note_count=counts.get(course.id, {}).get("note_count", 0),
    )


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    data: CourseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = await course_service.update_course_space(
        db, current_user, course_id, data.name, data.description, data.color
    )
    counts = await course_service.get_courses_counts(db, current_user, [course])
    return CourseResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        color=course.color,
        created_at=str(course.created_at),
        updated_at=str(course.updated_at),
        document_count=counts.get(course.id, {}).get("document_count", 0),
        note_count=counts.get(course.id, {}).get("note_count", 0),
    )


@router.delete("/{course_id}")
async def delete_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await course_service.delete_course_space(db, current_user, course_id)
    return {"message": "删除成功"}


# ── Course-Document association endpoints ───────────────────────────────


@router.get("/{course_id}/documents", response_model=list[CourseDocResponse])
async def get_course_documents(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents in course."""
    docs = await course_service.get_course_documents(db, current_user, course_id)
    return [
        CourseDocResponse(
            id=d.id,
            filename=d.filename,
            status=d.status,
            chunk_count=d.chunk_count,
            file_size=d.file_size,
            created_at=str(d.created_at),
        )
        for d in docs
    ]


@router.post("/{course_id}/documents")
async def add_document_to_course(
    course_id: str,
    req: AddDocRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add document to course."""
    await course_service.add_document_to_course(db, current_user, course_id, req.document_id)
    return {"message": "Document added"}


@router.delete("/{course_id}/documents/{doc_id}")
async def remove_document_from_course(
    course_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove document from course."""
    await course_service.remove_document_from_course(db, current_user, course_id, doc_id)
    return {"message": "Document removed"}


# ── Course Generation ────────────────────────────────────────────────────────


class CourseGenRequest(BaseModel):
    doc_ids: list[str] = Field(..., max_length=5, description="源文档 ID 列表")
    requirement: str = Field(default="", max_length=500, description="课程主题/要求")
    enable_image_generation: bool | None = Field(default=None, description="是否启用 AI 配图插画")


class CourseGenResponse(BaseModel):
    course_id: str
    title: str
    description: str
    section_count: int
    quiz_count: int


@router.post("/generate", response_model=CourseGenResponse)
async def generate_course(
    req: CourseGenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """基于文档自动生成课程大纲 + 测验，创建 CourseSpace。"""
    from app.core.course_generator import generate_course as _gen
    from app.services.config_service import get_llm_config_with_secret

    llm_config = await get_llm_config_with_secret(db, current_user)
    cls_cfg = (llm_config or {}).get("classroom_config") or {}
    should_gen_image = req.enable_image_generation
    if should_gen_image is None:
        should_gen_image = cls_cfg.get("image_enabled", True)

    result = await _gen(
        db,
        current_user,
        req.doc_ids,
        req.requirement,
        llm_config,
        enable_image_generation=should_gen_image,
    )

    outline = result["outline"]
    course = await course_service.create_course_space(
        db,
        current_user,
        name=outline.get("title", "未命名课程"),
        description=outline.get("description", req.requirement),
        color="#409EFF",
    )

    # 关联参考文档到该课程空间
    for doc_id in req.doc_ids:
        try:
            await course_service.add_document_to_course(db, current_user, course.id, doc_id)
        except Exception as add_err:
            logger.warning("Failed to link doc %s to course %s: %s", doc_id, course.id, add_err)

    # 将大纲、测验与课件 DSL 存入 description 并落盘同步
    import json as _json

    classroom_data = result.get("classroom_data")
    if classroom_data:
        classroom_data["id"] = course.id
        classroom_data["url"] = f"/courses/{course.id}/classroom"
        from app.core.course_generator import save_classroom_dsl_to_disk

        try:
            save_classroom_dsl_to_disk(classroom_data)
        except Exception as disk_err:
            logger.warning("Failed to save classroom DSL to disk: %s", disk_err)

    course.description = _json.dumps(
        {
            "classroom_url": f"/courses/{course.id}/classroom",
            "classroom_id": course.id,
            "outline": outline,
            "quizzes": result["quizzes"][:50],
            "source_doc_ids": result["source_doc_ids"],
            "classroom_data": classroom_data,
            "generated": True,
        },
        ensure_ascii=False,
    )
    await db.commit()

    return CourseGenResponse(
        course_id=course.id,
        title=course.name,
        description=(outline.get("description") or outline.get("title") or course.name)[:200],
        section_count=len(outline.get("sections", [])),
        quiz_count=len(result["quizzes"]),
    )
