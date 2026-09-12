"""
Note service — CRUD operations for notes, including tag management.
"""

import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import Note, Tag, User
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def _note_embed_text(note: Note) -> str:
    title = (note.title or "").strip()
    content = (note.content or "").strip()
    return f"{title}\n\n{content}".strip()


def _vec_str(embedding: list[float] | None) -> str | None:
    if embedding is None:
        return None
    return "[" + ",".join(str(float(v)) for v in embedding) + "]"


async def _embed_note(note: Note) -> list[float] | None:
    """Embed title+content for pgvector; returns None on failure (non-fatal)."""
    body = _note_embed_text(note)
    if not body:
        return None
    try:
        from app.core.embedder import embedder

        vec = await embedder.embed_query(body)
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)
    except Exception as exc:
        logger.warning("Note embedding failed (non-fatal): %s", exc)
        return None


async def reindex_user_notes(db: AsyncSession, user: User) -> int:
    """全量重建该用户的笔记语义索引（pgvector notes.embedding）。

    笔记量级小 + Embedder 自带文本哈希缓存，重建成本低；
    相比增量 upsert 更简单且天然覆盖删除场景。
    返回成功写入 embedding 的笔记数。
    """
    result = await db.execute(
        select(Note).where(Note.user_id == user.id, Note.deleted_at.is_(None))
    )
    notes = list(result.scalars().all())

    count = 0
    for note in notes:
        emb = await _embed_note(note)
        note.embedding = emb
        if emb is not None:
            count += 1
    try:
        bind = db.get_bind()
        if bind is not None and getattr(bind.dialect, "name", "") == "postgresql":
            from app.config import settings

            dim = int(getattr(settings, "embedding_dimension", 768) or 768)
            for note in notes:
                if note.embedding is None:
                    continue
                await db.execute(
                    text(
                        f"UPDATE notes SET embedding = CAST(:emb AS vector({dim})) WHERE id = :id"
                    ),
                    {"emb": _vec_str(note.embedding), "id": note.id},
                )
    except Exception as exc:
        logger.debug("Bulk note embedding SQL skipped: %s", exc)
    await db.commit()
    logger.info(
        "Notes index rebuilt: user=%s notes=%d embedded=%d", user.id, len(notes), count
    )
    return count


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
    logger.info("Created note %s for user %s", note.id, user.id)
    await _safe_reindex(db, user)
    return await get_note(db, user, note.id)


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
    query = (
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.user_id == user.id, Note.deleted_at.is_(None))
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
    """Semantic search across user notes via pgvector (fallback: title/content LIKE)."""
    from app.config import settings

    dim = int(getattr(settings, "embedding_dimension", 768) or 768)
    q_emb = None
    try:
        from app.core.embedder import embedder

        vec = await embedder.embed_query(query)
        q_emb = vec.tolist() if hasattr(vec, "tolist") else list(vec)
    except Exception as exc:
        logger.warning("Note search embed failed, falling back to LIKE: %s", exc)

    notes_map: dict[str, Note] = {}
    ordered_ids: list[str] = []

    bind = db.get_bind()
    is_pg = bind is not None and getattr(bind.dialect, "name", "") == "postgresql"

    if is_pg and q_emb is not None:
        q_str = _vec_str(q_emb)
        sql = text(
            f"""
            SELECT id, 1 - (embedding <=> CAST(:q AS vector({dim}))) AS score
            FROM notes
            WHERE user_id = :uid
              AND deleted_at IS NULL
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:q AS vector({dim}))
            LIMIT :k
            """
        )
        res = await db.execute(sql, {"q": q_str, "uid": user.id, "k": top_k})
        ordered_ids = [row[0] for row in res.all()]
        if ordered_ids:
            q = await db.execute(
                select(Note)
                .options(selectinload(Note.tags))
                .where(Note.id.in_(ordered_ids), Note.user_id == user.id)
            )
            notes_map = {n.id: n for n in q.scalars().all()}
            out = []
            for nid in ordered_ids:
                note = notes_map.get(nid)
                if not note:
                    continue
                out.append(
                    {
                        "id": note.id,
                        "title": note.title,
                        "content": note.content[:300],
                        "course_space_id": note.course_space_id,
                        "tags": [t.name for t in note.tags],
                        "score": 0.9,
                    }
                )
            if out:
                return out[:top_k]

    # Fallback: lexical LIKE (SQLite tests / missing embeddings)
    like = f"%{query.strip()}%"
    q = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(
            Note.user_id == user.id,
            Note.deleted_at.is_(None),
            (Note.title.ilike(like)) | (Note.content.ilike(like)),
        )
        .limit(top_k)
    )
    out = []
    for note in q.scalars().all():
        out.append(
            {
                "id": note.id,
                "title": note.title,
                "content": note.content[:300],
                "course_space_id": note.course_space_id,
                "tags": [t.name for t in note.tags],
                "score": 0.5,
            }
        )
    return out
