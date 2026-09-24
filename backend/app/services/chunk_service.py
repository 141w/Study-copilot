"""Chunk online edit + version history + rollback + parent rebuild.

Phase-3 (WeKnora chunk.go 设计参考，Python 落地)：
- 乐观并发：``expected_revision`` 不匹配返回 409
- 旧内容快照进 ``chunk_revisions``，``content_revision += 1``
- ``index_status``：processing → ready / failed（重嵌失败可重试）
- 父块重建：把已编辑子块区间按 char_start 倒序覆盖回 source_content
- 回滚 = 又一次编辑（可再回滚）

坐标约定：``char_start`` / ``char_end`` / ``source_content`` 是解析器坐标，
编辑时不改坐标；``content == source_content[char_start:char_end]`` 仅在
新旧等长时保持成立（"when possible"）。父块重建用原始坐标做倒序 splice，
因此长度变化不会使前面的坐标失效。
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pgvector_store import PgVectorStore
from app.db import ChunkRevision, Document, DocumentChunk, User
from app.exceptions import ConflictError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

MAX_EDIT_CHARS = 50_000


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _chunk_to_dict(c: DocumentChunk) -> dict[str, Any]:
    return {
        "id": c.id,
        "document_id": c.document_id,
        "content": c.content,
        "content_revision": c.content_revision,
        "index_status": c.index_status,
        "last_editor_id": c.last_editor_id,
        "char_start": c.char_start,
        "char_end": c.char_end,
        "source_content": c.source_content,
        "is_parent": bool(c.is_parent),
        "chunk_metadata": c.chunk_metadata or {},
        "chunk_index": c.chunk_index,
        "created_at": str(c.created_at) if c.created_at else None,
    }


def _revision_to_dict(r: ChunkRevision) -> dict[str, Any]:
    return {
        "id": r.id,
        "chunk_id": r.chunk_id,
        "revision": r.revision,
        "content": r.content,
        "editor_id": r.editor_id,
        "edited_at": str(r.edited_at) if r.edited_at else None,
        "is_enabled": bool(r.is_enabled),
    }


async def _get_owned_chunk(
    db: AsyncSession, user: User, doc_id: str, chunk_id: str
) -> DocumentChunk:
    doc_result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == user.id,
            Document.deleted_at.is_(None),
        )
    )
    if doc_result.scalar_one_or_none() is None:
        raise NotFoundError("文档不存在")
    chunk_result = await db.execute(
        select(DocumentChunk).where(
            DocumentChunk.id == chunk_id,
            DocumentChunk.document_id == doc_id,
        )
    )
    chunk = chunk_result.scalar_one_or_none()
    if chunk is None:
        raise NotFoundError("切片不存在")
    return chunk


async def list_chunk_briefs(
    db: AsyncSession, user: User, doc_id: str
) -> list[dict[str, Any]]:
    """Return ordered chunk briefs (id + edit state) for a document."""
    doc_result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == user.id,
            Document.deleted_at.is_(None),
        )
    )
    if doc_result.scalar_one_or_none() is None:
        raise NotFoundError("文档不存在")
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return [
        {
            "id": c.id,
            "content": c.content,
            "content_revision": c.content_revision,
            "index_status": c.index_status,
            "char_start": c.char_start,
            "char_end": c.char_end,
            "is_parent": bool(c.is_parent),
            "chunk_metadata": c.chunk_metadata or {},
        }
        for c in result.scalars().all()
    ]


async def get_chunk(
    db: AsyncSession, user: User, doc_id: str, chunk_id: str
) -> dict[str, Any]:
    chunk = await _get_owned_chunk(db, user, doc_id, chunk_id)
    return _chunk_to_dict(chunk)


async def list_revisions(
    db: AsyncSession, user: User, doc_id: str, chunk_id: str
) -> list[dict[str, Any]]:
    await _get_owned_chunk(db, user, doc_id, chunk_id)
    result = await db.execute(
        select(ChunkRevision)
        .where(ChunkRevision.chunk_id == chunk_id)
        .order_by(ChunkRevision.revision.desc())
    )
    return [_revision_to_dict(r) for r in result.scalars().all()]


async def _find_parent(db: AsyncSession, child: DocumentChunk) -> DocumentChunk | None:
    """Locate the hierarchical parent whose parser range covers this child."""
    if child.is_parent or child.char_start is None or child.char_end is None:
        return None
    result = await db.execute(
        select(DocumentChunk).where(
            DocumentChunk.document_id == child.document_id,
            DocumentChunk.is_parent.is_(True),
            DocumentChunk.char_start.is_not(None),
            DocumentChunk.char_end.is_not(None),
            DocumentChunk.char_start <= child.char_start,
            DocumentChunk.char_end >= child.char_end,
            DocumentChunk.id != child.id,
        )
    )
    parents = list(result.scalars().all())
    if not parents:
        return None
    parents.sort(key=lambda p: (p.char_end or 0) - (p.char_start or 0))
    return parents[0]


async def _list_children(db: AsyncSession, parent: DocumentChunk) -> list[DocumentChunk]:
    result = await db.execute(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == parent.document_id,
            DocumentChunk.is_parent.is_(False),
            DocumentChunk.char_start.is_not(None),
            DocumentChunk.char_end.is_not(None),
            DocumentChunk.char_start >= parent.char_start,
            DocumentChunk.char_end <= parent.char_end,
        )
        .order_by(DocumentChunk.char_start)
    )
    return list(result.scalars().all())


def apply_child_slices_reverse(
    base: str, replacements: list[tuple[int, int, str]]
) -> str:
    """Splice edited child bodies onto ``base`` in reverse ``char_start`` order.

    Reverse order keeps earlier (lower-start) parser coordinates valid even
    when an edit changes text length. Overlaps keep the later-starting edit
    (applied first) and then the earlier one overwrites if ranges allow.
    """
    ordered = sorted(replacements, key=lambda r: r[0], reverse=True)
    result = base
    for start, end, text_content in ordered:
        if start < 0 or end < start or end > len(result):
            continue
        result = result[:start] + text_content + result[end:]
    return result


async def rebuild_parent_content(db: AsyncSession, edited: DocumentChunk) -> DocumentChunk | None:
    """Overlay edited child ranges on the immutable parent source.

    Parent body = apply child slices (content_revision > 0) onto
    ``source_content`` in reverse char_start order.
    """
    parent = await _find_parent(db, edited)
    if parent is None:
        return None
    children = await _list_children(db, parent)
    base = parent.source_content or parent.content
    replacements: list[tuple[int, int, str]] = []
    for c in children:
        if c.content_revision <= 0:
            continue
        if c.char_start is None or c.char_end is None:
            continue
        if c.char_start < 0 or c.char_end < c.char_start or c.char_end > len(base):
            continue
        replacements.append((c.char_start, c.char_end, c.content))
    parent.content = apply_child_slices_reverse(base, replacements)
    return parent


def _preserve_invariant_if_possible(chunk: DocumentChunk, new_content: str) -> None:
    """Keep content == source_content[char_start:char_end] when length is unchanged."""
    if (
        chunk.char_start is None
        or chunk.char_end is None
        or chunk.source_content is None
        or len(new_content) != chunk.char_end - chunk.char_start
    ):
        return
    s, e = chunk.char_start, chunk.char_end
    chunk.source_content = chunk.source_content[:s] + new_content + chunk.source_content[e:]


async def _reindex_chunk(db: AsyncSession, user: User, chunk: DocumentChunk) -> dict[str, Any]:
    """Delete-by-chunk_id + re-embed; flip index_status ready/failed."""
    chunk.index_status = "processing"
    await db.commit()
    store = PgVectorStore(user_id=user.id)
    try:
        await store.delete_by_chunk_id(chunk.id, db=db)
        await store.reindex_chunk(chunk.id, chunk.content, db=db)
        chunk.index_status = "ready"
        await db.commit()
    except Exception as exc:
        logger.error("Reindex failed for chunk %s: %s", chunk.id, exc)
        chunk.index_status = "failed"
        await db.commit()
        result = _chunk_to_dict(chunk)
        result["error"] = str(exc)
        return result
    return _chunk_to_dict(chunk)


async def update_chunk(
    db: AsyncSession,
    user: User,
    doc_id: str,
    chunk_id: str,
    content: str,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    """Optimistic, versioned edit with snapshot + reindex.

    Raises ConflictError (409) when ``expected_revision`` mismatches.
    Same content + index_status=failed → retry reindex without a new revision.
    """
    chunk = await _get_owned_chunk(db, user, doc_id, chunk_id)
    if expected_revision is not None and expected_revision != chunk.content_revision:
        raise ConflictError(
            f"版本冲突：期望 revision={expected_revision}，当前为 {chunk.content_revision}"
        )

    new_content = content if content is not None else ""
    if not new_content.strip():
        raise ValidationError("切片内容不能为空")
    if len(new_content) > MAX_EDIT_CHARS:
        raise ValidationError(f"切片内容超过上限 {MAX_EDIT_CHARS} 字符")

    current = chunk.content or ""
    if new_content == current:
        # No body change: only retry a failed reindex (WeKnora semantics).
        if chunk.index_status == "failed":
            return await _reindex_chunk(db, user, chunk)
        return _chunk_to_dict(chunk)

    # Snapshot the version being replaced
    db.add(
        ChunkRevision(
            id=str(uuid.uuid4()),
            chunk_id=chunk.id,
            revision=chunk.content_revision,
            content=current,
            editor_id=chunk.last_editor_id,
            edited_at=_utcnow(),
            is_enabled=True,
        )
    )
    chunk.content = new_content
    chunk.content_revision += 1
    chunk.last_editor_id = user.id
    chunk.index_status = "processing"
    _preserve_invariant_if_possible(chunk, new_content)
    await db.commit()

    # Parent rebuild is best-effort; failure must not block reindex of the child.
    try:
        parent = await rebuild_parent_content(db, chunk)
        if parent is not None:
            await db.commit()
    except Exception as exc:
        logger.warning("Parent rebuild failed for chunk %s: %s", chunk.id, exc)
        await db.rollback()
        # re-load chunk after rollback
        chunk = await _get_owned_chunk(db, user, doc_id, chunk_id)

    return await _reindex_chunk(db, user, chunk)


async def revert_chunk(
    db: AsyncSession,
    user: User,
    doc_id: str,
    chunk_id: str,
    revision: int,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    """Revert to a historical revision — implemented as another edit (revertible)."""
    chunk = await _get_owned_chunk(db, user, doc_id, chunk_id)
    result = await db.execute(
        select(ChunkRevision).where(
            ChunkRevision.chunk_id == chunk_id,
            ChunkRevision.revision == revision,
        )
    )
    hist = result.scalar_one_or_none()
    if hist is None:
        raise NotFoundError(f"历史版本 revision={revision} 不存在")
    return await update_chunk(
        db,
        user,
        doc_id,
        chunk_id,
        hist.content,
        expected_revision=expected_revision if expected_revision is not None else chunk.content_revision,
    )
