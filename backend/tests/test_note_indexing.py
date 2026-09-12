"""笔记语义索引单元测试：建/改/删触发 pgvector embedding 重建。

Embedder 被 monkeypatch 为固定向量，避免加载本地 SBERT。
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.services import note_service


class FakeEmbedder:
    """返回固定维度向量的假 embedder。"""

    calls: list[str] = []

    async def embed_query(self, text: str):
        FakeEmbedder.calls.append(text)
        # 8-dim list is enough for unit tests (SQLITE stores as attribute)
        return [0.1] * 8

    async def embed_texts(self, texts):
        return [[0.1] * 8 for _ in texts]


@pytest.fixture()
def fake_embedder(monkeypatch):
    FakeEmbedder.calls.clear()
    import app.core.embedder as emb_mod

    monkeypatch.setattr(emb_mod, "embedder", FakeEmbedder())
    return FakeEmbedder


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
async def test_create_note_triggers_reindex_embedder(db_session, fake_embedder):
    user = await _make_user(db_session)

    await note_service.create_note(
        db_session, user, title="pgvector 简介", content="向量检索的近邻搜索方法。"
    )

    assert FakeEmbedder.calls, "reindex should embed notes"
    assert any("pgvector" in c or "向量检索" in c for c in FakeEmbedder.calls)
    # note row should have embedding attribute set after reindex
    from sqlalchemy import select

    from app.db import Note

    res = await db_session.execute(select(Note).where(Note.user_id == user.id))
    notes = list(res.scalars().all())
    assert notes
    assert notes[0].embedding is not None
    assert len(notes[0].embedding) == 8


@pytest.mark.asyncio
async def test_update_note_reindexes_new_content(db_session, fake_embedder):
    user = await _make_user(db_session)
    note = await note_service.create_note(db_session, user, title="旧标题", content="旧内容")

    FakeEmbedder.calls.clear()
    await note_service.update_note(db_session, user, note.id, content="全新的内容文本用于验证重建")

    assert any("全新的内容文本" in c for c in FakeEmbedder.calls)
    assert not any(c == "旧内容" for c in FakeEmbedder.calls)


@pytest.mark.asyncio
async def test_delete_note_reindexes_without_deleted(db_session, fake_embedder):
    user = await _make_user(db_session)
    n1 = await note_service.create_note(db_session, user, title="A", content="内容A")
    await note_service.create_note(db_session, user, title="B", content="内容B")

    FakeEmbedder.calls.clear()
    await note_service.delete_note(db_session, user, n1.id)

    # After delete, reindex only embeds remaining non-deleted notes
    assert FakeEmbedder.calls
    assert not any("内容A" in c for c in FakeEmbedder.calls)
    assert any("内容B" in c for c in FakeEmbedder.calls)


@pytest.mark.asyncio
async def test_empty_note_yields_no_embedding_but_does_not_crash(db_session, fake_embedder):
    user = await _make_user(db_session)
    FakeEmbedder.calls.clear()
    note = await note_service.create_note(db_session, user, title="", content="")
    # Empty body → no embed call for that note
    assert not any(c.strip() == "" for c in FakeEmbedder.calls)
    assert note is not None


@pytest.mark.asyncio
async def test_search_notes_fallback_like(db_session, fake_embedder):
    """SQLite / missing embeddings path: LIKE fallback still returns matches."""
    user = await _make_user(db_session)
    await note_service.create_note(db_session, user, title="注意力机制", content="Self-Attention")
    await note_service.create_note(db_session, user, title="其他", content="无关")

    results = await note_service.search_notes(db_session, user, query="注意力")
    assert results
    assert any("注意力" in (r.get("title") or "") for r in results)
