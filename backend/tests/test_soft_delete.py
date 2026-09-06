"""软删除（回收站）回归测试：documents / notes。

语义：DELETE → deleted_at 打标（文件与索引保留），列表/详情不可见；
restore 恢复；purge 物理清除超期项。
"""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, Note, User
from app.exceptions import NotFoundError
from app.services import document_service, note_service


async def _make_user(db_session: AsyncSession) -> User:
    user = User(
        id=f"u-sd-{uuid.uuid4().hex[:8]}",
        username="sd_" + uuid.uuid4().hex[:6],
        email=f"sd_{uuid.uuid4().hex[:6]}@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_document_soft_delete_and_restore(db_session: AsyncSession):
    user = await _make_user(db_session)
    db_session.add(Document(
        id="doc-sd-1",
        user_id=user.id,
        filename="讲义.pdf",
        file_path="/tmp/nonexistent-doc-sd-1.pdf",  # 软删除不触达文件
        status="ready",
        chunk_count=3,
        file_size=100,
    ))
    await db_session.commit()

    await document_service.delete_document(db_session, user, "doc-sd-1")
    assert all(
        d.id != "doc-sd-1" for d in await document_service.list_documents(db_session, user)
    )
    with pytest.raises(NotFoundError):
        await document_service.get_document(db_session, user, "doc-sd-1")

    restored = await document_service.restore_document(db_session, user, "doc-sd-1")
    assert restored.deleted_at is None
    assert restored.chunk_count == 3
    ids = [d.id for d in await document_service.list_documents(db_session, user)]
    assert ids == ["doc-sd-1"]


@pytest.mark.asyncio
async def test_note_soft_delete_restore_and_reindex_filter(
    db_session: AsyncSession, monkeypatch,
):
    """删除笔记后 reindex 不应再为已删笔记产出 chunk。"""
    captured = {}

    class FakeStore:
        def __init__(self, doc_id: str, vectorstore_dir: str = "", retrieval_type: str = "faiss"):
            pass

        def delete(self):
            return True

        async def add_chunks(self, chunks):
            captured["chunks"] = list(chunks)
            return True

    monkeypatch.setattr(note_service, "DocumentVectorStore", FakeStore)

    user = await _make_user(db_session)
    keep = await note_service.create_note(db_session, user, title="保留", content="保留内容")
    drop = await note_service.create_note(db_session, user, title="待删", content="待删内容")

    await note_service.delete_note(db_session, user, drop.id)
    with pytest.raises(NotFoundError):
        await note_service.get_note(db_session, user, drop.id)

    titles = [n.title for n in await note_service.list_notes(db_session, user)]
    assert titles == ["保留"]

    # 重建索引：chunk 只应来自未删除笔记
    await note_service.reindex_user_notes(db_session, user)
    src_ids = {c["document_id"] for c in captured["chunks"]}
    assert drop.id not in src_ids and keep.id in src_ids

    # 恢复后重新可见
    await note_service.restore_note(db_session, user, drop.id)
    assert any(n.id == drop.id for n in await note_service.list_notes(db_session, user))


@pytest.mark.asyncio
async def test_purge_removes_only_old_deleted_docs(db_session: AsyncSession):
    from datetime import UTC, datetime, timedelta

    user = await _make_user(db_session)
    now = datetime.now(UTC).replace(tzinfo=None)
    old_del = now - timedelta(days=40)
    recent_del = now - timedelta(days=1)

    db_session.add(Document(
        id="doc-purge-old-" + uuid.uuid4().hex[:6],
        user_id=user.id, filename="old.pdf",
        file_path="/tmp/definitely-missing-old.pdf", status="ready", deleted_at=old_del,
    ))
    db_session.add(Document(
        id="doc-purge-recent-" + uuid.uuid4().hex[:6],
        user_id=user.id, filename="new.pdf",
        file_path="/tmp/definitely-missing-new.pdf", status="ready", deleted_at=recent_del,
    ))
    db_session.add(Document(
        id="doc-alive-" + uuid.uuid4().hex[:6],
        user_id=user.id, filename="alive.pdf",
        file_path="/tmp/definitely-missing-alive.pdf", status="ready",
    ))
    await db_session.commit()

    purged = await document_service.purge_deleted_documents(
        db_session, user, older_than_days=30
    )
    assert purged == 1

    remaining = {
        d.id: d for d in await document_service.list_documents(db_session, user)
    }
    assert len(remaining) == 1  # recent-deleted 在回收站不可见但未被物理清除
    alive_id = list(remaining)[0]
    assert alive_id.startswith("doc-alive-")
