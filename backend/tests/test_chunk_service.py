"""Phase-3 chunk online edit: 409 / snapshot / revert-twice / reindex retry / parent rebuild."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChunkRevision, Document, DocumentChunk, User
from app.exceptions import ConflictError, NotFoundError
from app.services import chunk_service


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(id="chunk-user", username="chunkuser", email="c@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.fixture
async def doc(db_session: AsyncSession, user: User) -> Document:
    d = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        filename="chunk.pdf",
        file_path=f"/tmp/{uuid.uuid4()}.pdf",
        status="ready",
        chunk_count=3,
    )
    db_session.add(d)
    await db_session.commit()
    return d


def _chunk(
    doc_id: str,
    content: str,
    *,
    index: int = 0,
    is_parent: bool = False,
    char_start: int | None = None,
    char_end: int | None = None,
    source: str | None = None,
) -> DocumentChunk:
    return DocumentChunk(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        content=content,
        chunk_index=index,
        chunk_metadata={},
        source_content=source,
        char_start=char_start,
        char_end=char_end,
        is_parent=is_parent,
        content_revision=0,
        index_status="ready",
    )


def _reindex_ok():
    return patch(
        "app.services.chunk_service.PgVectorStore",
        return_value=AsyncMock(delete_by_chunk_id=AsyncMock(return_value=True), reindex_chunk=AsyncMock(return_value=True)),
    )


def _reindex_fail():
    store = AsyncMock()
    store.delete_by_chunk_id = AsyncMock(return_value=True)
    store.reindex_chunk = AsyncMock(side_effect=RuntimeError("embed boom"))
    return patch("app.services.chunk_service.PgVectorStore", return_value=store)


@pytest.mark.asyncio
async def test_update_revision_mismatch_409(db_session: AsyncSession, user: User, doc: Document):
    c = _chunk(doc.id, "原文内容")
    db_session.add(c)
    await db_session.commit()

    with pytest.raises(ConflictError):
        await chunk_service.update_chunk(
            db_session, user, doc.id, c.id, "新内容", expected_revision=99
        )
    await db_session.refresh(c)
    assert c.content == "原文内容"
    assert c.content_revision == 0


@pytest.mark.asyncio
async def test_update_snapshots_old_content(db_session: AsyncSession, user: User, doc: Document):
    c = _chunk(doc.id, "旧内容V0")
    db_session.add(c)
    await db_session.commit()

    with _reindex_ok():
        result = await chunk_service.update_chunk(
            db_session, user, doc.id, c.id, "新内容V1", expected_revision=0
        )

    assert result["content"] == "新内容V1"
    assert result["content_revision"] == 1
    assert result["index_status"] == "ready"

    revs = await chunk_service.list_revisions(db_session, user, doc.id, c.id)
    assert len(revs) == 1
    assert revs[0]["revision"] == 0
    assert revs[0]["content"] == "旧内容V0"


@pytest.mark.asyncio
async def test_revert_twice_is_revertible(db_session: AsyncSession, user: User, doc: Document):
    c = _chunk(doc.id, "V0")
    db_session.add(c)
    await db_session.commit()

    with _reindex_ok():
        await chunk_service.update_chunk(db_session, user, doc.id, c.id, "V1", expected_revision=0)
        # revert to rev 0 (body "V0")
        r1 = await chunk_service.revert_chunk(db_session, user, doc.id, c.id, revision=0)
        assert r1["content"] == "V0"
        assert r1["content_revision"] == 2

        # revert the revert → back to "V1" (rev 1 snapshot)
        r2 = await chunk_service.revert_chunk(db_session, user, doc.id, c.id, revision=1)
        assert r2["content"] == "V1"
        assert r2["content_revision"] == 3

    revs = await chunk_service.list_revisions(db_session, user, doc.id, c.id)
    # three snapshots: V0@0, V1@1, V0@2
    assert sorted(r["revision"] for r in revs) == [0, 1, 2]


@pytest.mark.asyncio
async def test_revert_missing_revision_404(db_session: AsyncSession, user: User, doc: Document):
    c = _chunk(doc.id, "V0")
    db_session.add(c)
    await db_session.commit()
    with pytest.raises(NotFoundError):
        await chunk_service.revert_chunk(db_session, user, doc.id, c.id, revision=42)


@pytest.mark.asyncio
async def test_reindex_fail_then_retry_ready(db_session: AsyncSession, user: User, doc: Document):
    c = _chunk(doc.id, "原文A")
    db_session.add(c)
    await db_session.commit()

    with _reindex_fail():
        result = await chunk_service.update_chunk(
            db_session, user, doc.id, c.id, "编辑后B", expected_revision=0
        )
    assert result["index_status"] == "failed"
    assert "embed boom" in (result.get("error") or "")
    await db_session.refresh(c)
    assert c.index_status == "failed"
    assert c.content == "编辑后B"

    # Retry with the same body → reindex only, no new revision
    with _reindex_ok():
        retry = await chunk_service.update_chunk(
            db_session, user, doc.id, c.id, "编辑后B", expected_revision=1
        )
    assert retry["index_status"] == "ready"
    assert retry["content_revision"] == 1
    revs = await chunk_service.list_revisions(db_session, user, doc.id, c.id)
    assert len(revs) == 1  # only the first edit snapshotted


@pytest.mark.asyncio
async def test_parent_rebuild_reverse_char_start(db_session: AsyncSession, user: User, doc: Document):
    src = "AAAA BBBB CCCC"
    parent = _chunk(
        doc.id,
        src,
        index=0,
        is_parent=True,
        char_start=0,
        char_end=len(src),
        source=src,
    )
    c1 = _chunk(doc.id, "AAAA", index=1, char_start=0, char_end=4, source=src)
    c2 = _chunk(doc.id, "BBBB", index=2, char_start=5, char_end=9, source=src)
    c3 = _chunk(doc.id, "CCCC", index=3, char_start=10, char_end=14, source=src)
    db_session.add_all([parent, c1, c2, c3])
    await db_session.commit()

    with _reindex_ok():
        # Edit middle child with a longer body; then earlier child with a shorter body.
        await chunk_service.update_chunk(db_session, user, doc.id, c2.id, "XXXXX")
        await chunk_service.update_chunk(db_session, user, doc.id, c1.id, "AA")

    await db_session.refresh(parent)
    # Reverse-order splice: c2 at [5:9] then c1 at [0:4]
    # base[:5]+"XXXXX"+base[9:] = "AAAA XXXXX CCCC"
    # then [:0]+"AA"+that[4:] = "AA XXXXX CCCC"
    assert parent.content == "AA XXXXX CCCC"

    # Invariant "when possible": equal-length edit keeps content == source[s:e]
    with _reindex_ok():
        await chunk_service.update_chunk(db_session, user, doc.id, c3.id, "CCCC")  # same len, same body → no-op
        await chunk_service.update_chunk(db_session, user, doc.id, c3.id, "DDDD")
    await db_session.refresh(c3)
    assert c3.source_content is not None
    assert c3.char_start is not None and c3.char_end is not None
    assert c3.content == c3.source_content[c3.char_start : c3.char_end]


@pytest.mark.asyncio
async def test_apply_child_slices_reverse_helper():
    base = "0123456789"
    out = chunk_service.apply_child_slices_reverse(
        base,
        [(0, 2, "AA"), (5, 7, "BBBBB")],
    )
    # reverse: (5,7)->"BBBBB" first, then (0,2)->"AA"
    assert out == "AA234BBBBB789"


@pytest.mark.asyncio
async def test_get_chunk_and_briefs(db_session: AsyncSession, user: User, doc: Document):
    c = _chunk(doc.id, "hello")
    db_session.add(c)
    await db_session.commit()

    got = await chunk_service.get_chunk(db_session, user, doc.id, c.id)
    assert got["content"] == "hello"
    assert got["index_status"] == "ready"

    briefs = await chunk_service.list_chunk_briefs(db_session, user, doc.id)
    assert len(briefs) == 1
    assert briefs[0]["id"] == c.id
    assert briefs[0]["content_revision"] == 0
