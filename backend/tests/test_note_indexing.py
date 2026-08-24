"""笔记语义索引单元测试：建/改/删后触发全量重建，chunk 携带 document_id。

DocumentVectorStore 被 monkeypatch 为内存 fake，避免真实 embedding。
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.services import note_service


class FakeStore:
    """记录 add_chunks 调用的假向量库包装器。"""

    instances: list["FakeStore"] = []
    deleted: list[str] = []

    def __init__(self, doc_id: str, vectorstore_dir: str = "", retrieval_type: str = "faiss"):
        self.doc_id = doc_id
        self.chunks: list[dict] = []
        FakeStore.instances.append(self)

    def delete(self):
        FakeStore.deleted.append(self.doc_id)
        return True

    async def add_chunks(self, chunks):
        self.chunks.extend(chunks)
        return True


@pytest.fixture()
def fake_store(monkeypatch):
    FakeStore.instances.clear()
    FakeStore.deleted.clear()
    monkeypatch.setattr(note_service, "DocumentVectorStore", FakeStore)
    return FakeStore


async def _make_user(db_session: AsyncSession) -> User:
    import uuid

    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=f"user-note-idx-{suffix}",
        username=f"noteidx_{suffix}",
        email=f"ni_{suffix}@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_create_note_triggers_reindex_with_document_id(db_session, fake_store):
    user = await _make_user(db_session)

    await note_service.create_note(
        db_session, user, title="FAISS 简介", content="向量检索的近邻搜索方法。"
    )

    # 每次重建会实例化两个 store：一个用于 delete 旧文件，一个用于 fresh 写入
    assert fake_store.instances, "reindex should instantiate a store"
    store = fake_store.instances[-1]
    assert store.doc_id == f"notes_{user.id}"
    assert len(store.chunks) >= 1
    assert all(c["document_id"] for c in store.chunks)
    assert any("向量检索" in c["text"] for c in store.chunks)


@pytest.mark.asyncio
async def test_update_note_reindexes_new_content(db_session, fake_store):
    user = await _make_user(db_session)
    note = await note_service.create_note(db_session, user, title="旧标题", content="旧内容")

    await note_service.update_note(
        db_session, user, note.id, content="全新的内容文本用于验证重建"
    )

    last = fake_store.instances[-1]
    assert any("全新的内容文本" in c["text"] for c in last.chunks)
    assert not any("旧内容" == c["text"] for c in last.chunks)


@pytest.mark.asyncio
async def test_delete_note_removes_chunks_from_index(db_session, fake_store):
    user = await _make_user(db_session)
    n1 = await note_service.create_note(db_session, user, title="A", content="内容A")
    await note_service.create_note(db_session, user, title="B", content="内容B")
    before = fake_store.instances[-1]

    await note_service.delete_note(db_session, user, n1.id)
    after = fake_store.instances[-1]

    assert sum(1 for c in after.chunks if c["document_id"] == n1.id) == 0
    assert any(c["document_id"] != n1.id for c in after.chunks)
    assert len(after.chunks) < len(before.chunks) or len(before.chunks) > 0


@pytest.mark.asyncio
async def test_empty_note_yields_no_chunks_but_does_not_crash(db_session, fake_store):
    user = await _make_user(db_session)
    await note_service.create_note(db_session, user, title="", content="")
    # 空 chunk 列表时 add_chunks 不应被调用（fake 中表现为空）
    assert all(len(s.chunks) == 0 for s in fake_store.instances)
