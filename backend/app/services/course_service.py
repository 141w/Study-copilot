"""
Course space service — CRUD operations for course spaces and document associations.
"""

import json
import logging
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import CourseSpace, Document, Note, User
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
    """Get documents in a course space (checks both Document.course_space_id and source_doc_ids in course description)."""
    # Verify course exists and belongs to user
    course = await get_course_space(db, user, course_id)

    # 提取课程大纲/剧本元数据中记录的 source_doc_ids
    extra_doc_ids: list[str] = []
    if course.description:
        try:
            desc_obj = json.loads(course.description)
            if isinstance(desc_obj, dict):
                ids = desc_obj.get("source_doc_ids") or desc_obj.get("doc_ids") or []
                if isinstance(ids, list):
                    extra_doc_ids = [str(i) for i in ids if i]
        except Exception:
            pass

    conditions = [Document.course_space_id == course_id]
    if extra_doc_ids:
        conditions.append(Document.id.in_(extra_doc_ids))

    result = await db.execute(
        select(Document)
        .where(
            Document.user_id == user.id,
            Document.deleted_at.is_(None),
            or_(*conditions),
        )
        .order_by(Document.created_at.desc())
    )
    # 按 ID 去重并保持顺序
    seen: set[str] = set()
    unique_docs: list[Document] = []
    for doc in result.scalars().all():
        if doc.id not in seen:
            seen.add(doc.id)
            unique_docs.append(doc)
    return unique_docs


async def get_courses_counts(
    db: AsyncSession,
    user: User,
    courses: list[CourseSpace],
) -> dict[str, dict[str, int]]:
    """Return {course_id: {'document_count': X, 'note_count': Y}} for given courses."""
    if not courses:
        return {}

    course_ids = [c.id for c in courses]
    counts: dict[str, dict[str, int]] = {
        cid: {"document_count": 0, "note_count": 0} for cid in course_ids
    }

    # 1. 统计 notes
    note_stmt = (
        select(Note.course_space_id, func.count(Note.id))
        .where(
            Note.user_id == user.id,
            Note.course_space_id.in_(course_ids),
        )
        .group_by(Note.course_space_id)
    )
    note_rows = (await db.execute(note_stmt)).all()
    for cid, n_count in note_rows:
        if cid in counts:
            counts[cid]["note_count"] = n_count

    # 2. 统计 documents (兼容直接归属与多文档引用)
    for c in courses:
        docs = await get_course_documents(db, user, c.id)
        counts[c.id]["document_count"] = len(docs)

    return counts


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
