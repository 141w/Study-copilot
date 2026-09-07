from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db
from app.services import course_service

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
    return CourseResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        color=course.color,
        created_at=str(course.created_at),
        updated_at=str(course.updated_at),
    )


@router.get("", response_model=list[CourseResponse])
async def list_courses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    courses = await course_service.list_course_spaces(db, current_user)
    return [
        CourseResponse(
            id=c.id,
            name=c.name,
            description=c.description,
            color=c.color,
            created_at=str(c.created_at),
            updated_at=str(c.updated_at),
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
    return CourseResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        color=course.color,
        created_at=str(course.created_at),
        updated_at=str(course.updated_at),
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
    return CourseResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        color=course.color,
        created_at=str(course.created_at),
        updated_at=str(course.updated_at),
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
    await course_service.add_document_to_course(
        db, current_user, course_id, req.document_id
    )
    return {"message": "Document added"}


@router.delete("/{course_id}/documents/{doc_id}")
async def remove_document_from_course(
    course_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove document from course."""
    await course_service.remove_document_from_course(
        db, current_user, course_id, doc_id
    )
    return {"message": "Document removed"}


# ── Course Generation ────────────────────────────────────────────────────────


class CourseGenRequest(BaseModel):
    doc_ids: list[str] = Field(..., max_length=5, description="源文档 ID 列表")
    requirement: str = Field(default="", max_length=500, description="课程主题/要求")


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
    result = await _gen(db, current_user, req.doc_ids, req.requirement, llm_config)

    outline = result["outline"]
    course = await course_service.create_course_space(
        db, current_user,
        name=outline.get("title", "未命名课程"),
        description=outline.get("description", req.requirement),
        color="#409EFF",
    )

    # 将大纲和测验存入 description（轻量实现：JSON）
    import json as _json
    course.description = _json.dumps({
        "outline": outline,
        "quizzes": result["quizzes"][:50],
        "source_doc_ids": result["source_doc_ids"],
        "generated": True,
    }, ensure_ascii=False)
    await db.commit()

    return CourseGenResponse(
        course_id=course.id,
        title=course.name,
        description=(outline.get("description") or outline.get("title") or course.name)[:200],
        section_count=len(outline.get("sections", [])),
        quiz_count=len(result["quizzes"]),
    )
