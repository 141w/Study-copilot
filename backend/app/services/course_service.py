"""
Course space service — CRUD operations for course spaces and document associations.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import CourseSpace, Document, User
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def create_course_space(
    db: AsyncSession,
    user: User,
    name: str,
    description: str | None = None,
    color: str | None = None,
) -> CourseSpace:
    """Create a new course space."""
    course = CourseSpace(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name=name,
        description=description,
        color=color or "#6366f1",
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    logger.info("Created course space %s for user %s", course.id, user.id)
    return course


async def list_course_spaces(
    db: AsyncSession,
    user: User,
) -> list[CourseSpace]:
    """Return all course spaces owned by user, newest first."""
    result = await db.execute(
        select(CourseSpace)
        .where(CourseSpace.user_id == user.id)
        .order_by(CourseSpace.created_at.desc())
    )
    return list(result.scalars().all())


async def get_course_space(
    db: AsyncSession,
    user: User,
    course_id: str,
) -> CourseSpace:
    """Get a single course space. Raises NotFoundError if missing."""
    result = await db.execute(
        select(CourseSpace).where(
            CourseSpace.id == course_id,
            CourseSpace.user_id == user.id,
        )
    )
    course = result.scalar_one_or_none()
    if not course:
        raise NotFoundError("课程空间不存在")
    return course


async def update_course_space(
    db: AsyncSession,
    user: User,
    course_id: str,
    name: str | None = None,
    description: str | None = None,
    color: str | None = None,
) -> CourseSpace:
    """Update a course space. Raises NotFoundError if missing."""
    course = await get_course_space(db, user, course_id)
    if name is not None:
        course.name = name
    if description is not None:
        course.description = description
    if color is not None:
        course.color = color
    await db.commit()
    await db.refresh(course)
    logger.info("Updated course space %s", course_id)
    return course


async def delete_course_space(
    db: AsyncSession,
    user: User,
    course_id: str,
) -> None:
    """Delete a course space and its linked notes. Raises NotFoundError if missing."""
    course = await get_course_space(db, user, course_id)

    # Unlink documents associated with this course
    result = await db.execute(
        select(Document).where(
            Document.course_space_id == course_id,
            Document.user_id == user.id,
        )
    )
    for doc in result.scalars().all():
        doc.course_space_id = None

    await db.delete(course)
    await db.commit()
    logger.info("Deleted course space %s", course_id)


# ── Course-Document associations ────────────────────────────────────────


async def get_course_documents(
    db: AsyncSession,
    user: User,
    course_id: str,
) -> list[Document]:
    """Get documents in a course space."""
    # Verify course exists and belongs to user
    await get_course_space(db, user, course_id)

    result = await db.execute(
        select(Document).where(
            Document.course_space_id == course_id,
            Document.user_id == user.id,
        )
    )
    return list(result.scalars().all())


async def add_document_to_course(
    db: AsyncSession,
    user: User,
    course_id: str,
    document_id: str,
) -> None:
    """Add a document to a course space."""
    # Verify course exists and belongs to user
    await get_course_space(db, user, course_id)

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档不存在")

    doc.course_space_id = course_id
    await db.commit()
    logger.info("Added document %s to course %s", document_id, course_id)


async def remove_document_from_course(
    db: AsyncSession,
    user: User,
    course_id: str,
    document_id: str,
) -> None:
    """Remove document from course space."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.course_space_id == course_id,
            Document.user_id == user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档不存在")

    doc.course_space_id = None
    await db.commit()
    logger.info("Removed document %s from course %s", document_id, course_id)
