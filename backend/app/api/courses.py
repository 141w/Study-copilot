from fastapi import APIRouter, Depends
from pydantic import BaseModel
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
