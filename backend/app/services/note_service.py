"""
Note service — CRUD operations for notes, including tag management.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import Note, Tag, User
from app.core.vector_store import DocumentVectorStore
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


# ── Tag helpers ─────────────────────────────────────────────────────────


async def _get_or_create_tag(
    db: AsyncSession,
    user_id: str,
    tag_name: str,
) -> Tag:
    """Return existing tag or create a new one for this user."""
    result = await db.execute(select(Tag).where(Tag.user_id == user_id, Tag.name == tag_name))
    tag = result.scalar_one_or_none()
    if tag is None:
        tag = Tag(id=str(uuid.uuid4()), user_id=user_id, name=tag_name)
        db.add(tag)
    return tag


async def list_tags(db: AsyncSession, user: User) -> list[Tag]:
    """Return all tags for a user."""
    result = await db.execute(select(Tag).where(Tag.user_id == user.id).order_by(Tag.name))
    return list(result.scalars().all())


async def delete_tag(db: AsyncSession, user: User, tag_id: str) -> None:
    """Delete a tag by ID."""
    result = await db.execute(select(Tag).where(Tag.id == tag_id, Tag.user_id == user.id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise NotFoundError("标签不存在")
    await db.delete(tag)
    await db.commit()
    logger.info("Deleted tag %s", tag_id)


# ── Note CRUD ───────────────────────────────────────────────────────────


async def create_note(
    db: AsyncSession,
    user: User,
    title: str,
    content: str = "",
    course_space_id: str | None = None,
    note_type: str = "markdown",
    tag_names: list[str] | None = None,
) -> Note:
    """Create a new note with optional tags and course space link."""
    note = Note(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=title,
        content=content,
        course_space_id=course_space_id,
        note_type=note_type,
    )

    if tag_names:
        tags = []
        for name in tag_names:
            tag = await _get_or_create_tag(db, user.id, name.strip())
            tags.append(tag)
        note.tags = tags

    db.add(note)
    await db.commit()
    await db.refresh(note)
    logger.info("Created note %s for user %s", note.id, user.id)
    return note


async def list_notes(
    db: AsyncSession,
    user: User,
    course_space_id: str | None = None,
    tag_name: str | None = None,
) -> list[Note]:
    """Return notes for user, optionally filtered by course space or tag."""
    query = select(Note).options(selectinload(Note.tags)).where(Note.user_id == user.id)
    if course_space_id:
        query = query.where(Note.course_space_id == course_space_id)
    if tag_name:
        query = query.join(Note.tags).where(Tag.name == tag_name)

    query = query.order_by(Note.is_pinned.desc(), Note.updated_at.desc())
    result = await db.execute(query)
    return list(result.scalars().unique().all())


async def get_note(
    db: AsyncSession,
    user: User,
    note_id: str,
) -> Note:
    """Get a single note with tags. Raises NotFoundError if missing."""
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.id == note_id, Note.user_id == user.id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise NotFoundError("笔记不存在")
    return note


async def update_note(
    db: AsyncSession,
    user: User,
    note_id: str,
    title: str | None = None,
    content: str | None = None,
    course_space_id: str | None = None,
    note_type: str | None = None,
    is_pinned: bool | None = None,
    tag_names: list[str] | None = None,
) -> Note:
    """Update an existing note. Raises NotFoundError if missing."""
    note = await get_note(db, user, note_id)

    if title is not None:
        note.title = title
    if content is not None:
        note.content = content
    if course_space_id is not None:
        note.course_space_id = course_space_id
    if note_type is not None:
        note.note_type = note_type
    if is_pinned is not None:
        note.is_pinned = is_pinned
    if tag_names is not None:
        tags = []
        for name in tag_names:
            tag = await _get_or_create_tag(db, user.id, name.strip())
            tags.append(tag)
        note.tags = tags

    await db.commit()
    await db.refresh(note)
    logger.info("Updated note %s", note_id)
    return note


async def delete_note(
    db: AsyncSession,
    user: User,
    note_id: str,
) -> None:
    """Delete a note. Raises NotFoundError if missing."""
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    note = result.scalar_one_or_none()
    if not note:
        raise NotFoundError("笔记不存在")
    await db.delete(note)
    await db.commit()
    logger.info("Deleted note %s", note_id)



async def search_notes(
    db: AsyncSession,
    user: User,
    query: str,
    top_k: int = 10,
) -> list[dict]:
    """Semantic search across user notes using FAISS vector index."""
    from app.core.vector_store import DocumentVectorStore
    from app.core.embedder import embedder

    store = DocumentVectorStore(f"notes_{user.id}", vectorstore_dir="./vectorstore/notes")
    await store.load()

    if not store._store or not store._store.chunks:
        return []

    results = await store.search(query, top_k * 2)

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    note_ids = [r.get("chunk", {}).get("document_id", "") for r in results]
    note_ids = [nid for nid in note_ids if nid][:top_k]

    if not note_ids:
        return []

    q = await db.execute(
        select(Note).options(selectinload(Note.tags)).where(
            Note.id.in_(note_ids), Note.user_id == user.id
        )
    )
    notes_map = {n.id: n for n in q.scalars().all()}

    out = []
    for r in results:
        nid = r.get("chunk", {}).get("document_id", "")
        note = notes_map.get(nid)
        if note:
            out.append({
                "id": note.id,
                "title": note.title,
                "content": note.content[:300],
                "course_space_id": note.course_space_id,
                "tags": [t.name for t in note.tags],
                "score": 1.0 - float(r.get("distance", 1)),
            })
        if len(out) >= top_k:
            break
    return out
