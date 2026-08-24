"""
Note service — CRUD operations for notes, including tag management.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.vector_store import DocumentVectorStore
from app.db import Note, Tag, User
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)

# 笔记语义索引目录与 store 前缀（每用户一个独立索引）
NOTES_VECTORSTORE_DIR = "./vectorstore/notes"


def _notes_store(user_id: str) -> "DocumentVectorStore":
    """返回该用户笔记向量索引的包装器（FAISS）。"""
    return DocumentVectorStore(f"notes_{user_id}", vectorstore_dir=NOTES_VECTORSTORE_DIR)


def _build_note_chunks(note: Note) -> list[dict]:
    """把单条笔记切成可入索引的 chunk（document_id=note.id 供搜索回表）。

    标题并入正文提升匹配；内容按固定窗口切片。空笔记跳过。
    """
    title = (note.title or "").strip()
    content = (note.content or "").strip()
    if not title and not content:
        return []

    body = f"{title}\n\n{content}".strip()
    size, step = 800, 650
    if len(body) <= size:
        pieces = [body]
    else:
        pieces = [body[i : i + size] for i in range(0, len(body), step)]

    chunks = []
    for i, piece in enumerate(pieces):
        piece = piece.strip()
        if not piece:
            continue
        chunks.append(
            {
                "text": piece,
                "document_id": note.id,
                "note_id": note.id,
                "title": note.title or "",
                "chunk_index": i,
            }
        )
    return chunks


async def reindex_user_notes(db: AsyncSession, user: User) -> int:
    """全量重建该用户的笔记语义索引。

    笔记量级小 + Embedder 自带文本哈希缓存，重建成本低；
    相比增量 upsert 更简单且天然覆盖删除场景。
    返回入索引的 chunk 数。
    """
    result = await db.execute(
        select(Note).where(Note.user_id == user.id, Note.deleted_at.is_(None))
    )
    notes = list(result.scalars().all())

    # 先清旧文件再新建实例，避免维度/陈旧数据残留
    try:
        _notes_store(user.id).delete()
    except Exception:  # noqa: BLE001 — 索引文件可能本就不存在
        pass

    fresh = _notes_store(user.id)
    all_chunks: list[dict] = []
    for note in notes:
        all_chunks.extend(_build_note_chunks(note))

    if all_chunks:
        await fresh.add_chunks(all_chunks)
        logger.info(
            "Notes index rebuilt: user=%s notes=%d chunks=%d",
            user.id,
            len(notes),
            len(all_chunks),
        )
    else:
        logger.info("Notes index cleared (no notes): user=%s", user.id)
    return len(all_chunks)


async def _safe_reindex(db: AsyncSession, user: User) -> None:
    """索引失败不阻断笔记 CRUD——仅记录告警，下次变更会再次尝试重建。"""
    try:
        await reindex_user_notes(db, user)
    except Exception as e:  # noqa: BLE001
        logger.warning("Note reindex failed (non-fatal): %s", e)


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
    await _safe_reindex(db, user)
    return note


async def list_notes(
    db: AsyncSession,
    user: User,
    course_space_id: str | None = None,
    tag_name: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Note]:
    """Return notes for user, optionally filtered by course space or tag.

    limit/offset 为可选分页参数：缺省返回全部（兼容既有前端）。
    """
    query = select(Note).options(selectinload(Note.tags)).where(
        Note.user_id == user.id, Note.deleted_at.is_(None)
    )
    if course_space_id:
        query = query.where(Note.course_space_id == course_space_id)
    if tag_name:
        query = query.join(Note.tags).where(Tag.name == tag_name)

    query = query.order_by(Note.is_pinned.desc(), Note.updated_at.desc())
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
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
        .where(
            Note.id == note_id,
            Note.user_id == user.id,
            Note.deleted_at.is_(None),
        )
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
    await _safe_reindex(db, user)
    return note


async def delete_note(
    db: AsyncSession,
    user: User,
    note_id: str,
) -> None:
    """软删除笔记（进回收站，可 restore）。Raises NotFoundError if missing."""
    from datetime import UTC, datetime

    result = await db.execute(
        select(Note).where(
            Note.id == note_id,
            Note.user_id == user.id,
            Note.deleted_at.is_(None),
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise NotFoundError("笔记不存在")
    note.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    logger.info("Soft-deleted note %s", note_id)
    await _safe_reindex(db, user)


async def restore_note(db: AsyncSession, user: User, note_id: str) -> Note:
    """从回收站恢复软删除的笔记。"""
    result = await db.execute(
        select(Note).where(
            Note.id == note_id,
            Note.user_id == user.id,
            Note.deleted_at.is_not(None),
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise NotFoundError("回收站中没有该笔记")
    note.deleted_at = None
    await db.commit()
    logger.info("Restored note %s", note_id)
    await _safe_reindex(db, user)
    return note



async def search_notes(
    db: AsyncSession,
    user: User,
    query: str,
    top_k: int = 10,
) -> list[dict]:
    """Semantic search across user notes using FAISS vector index."""
    store = _notes_store(user.id)
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
            Note.id.in_(note_ids),
            Note.user_id == user.id,
            Note.deleted_at.is_(None),  # 索引陈旧时的双保险
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
