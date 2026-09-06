"""列表分页（limit/offset）回归测试。

背景：documents / notes 列表原先无分页，全量返回。
本组用例锁定：缺省行为不变（返回全部）+ 分页切片与排序稳定。
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, Note, User
from app.services import document_service, note_service


def _ts(base: datetime, i: int) -> datetime:
    return (base + timedelta(minutes=i)).replace(tzinfo=None)


@pytest.fixture
async def page_user(db_session: AsyncSession):
    # 每个用例独立 ID，避免共享测试库时主键冲突
    uid = f"u-page-{uuid.uuid4().hex[:8]}"
    user = User(
        id=uid,
        username=f"pager_{uid[-6:]}",
        email=f"{uid}@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_document_list_pagination(db_session: AsyncSession, page_user):
    base = datetime.now(UTC)
    for i in range(5):
        db_session.add(Document(
            id=f"doc-pg-{i}",
            user_id=page_user.id,
            filename=f"f{i}.txt",
            file_path=f"/tmp/f{i}.txt",
            status="ready",
            chunk_count=i,
            file_size=10,
            created_at=_ts(base, i),  # 越大越新
        ))
    await db_session.commit()

    all_docs = await document_service.list_documents(db_session, page_user)
    assert len(all_docs) == 5
    # 排序稳定：created_at 倒序（新的在前）
    assert [d.id for d in all_docs] == [f"doc-pg-{i}" for i in range(4, -1, -1)]

    page1 = await document_service.list_documents(db_session, page_user, limit=2)
    assert [d.id for d in page1] == ["doc-pg-4", "doc-pg-3"]

    page2 = await document_service.list_documents(db_session, page_user, limit=2, offset=2)
    assert [d.id for d in page2] == ["doc-pg-2", "doc-pg-1"]

    # offset 超出总量 → 空列表而非报错
    tail = await document_service.list_documents(db_session, page_user, limit=2, offset=10)
    assert tail == []


@pytest.mark.asyncio
async def test_note_list_pagination_respects_pinned_order(db_session: AsyncSession, page_user):
    base = datetime.now(UTC)
    rows = [
        ("note-pg-0", False, _ts(base, 0)),
        ("note-pg-1", True, _ts(base, 10)),   # 置顶优先
        ("note-pg-2", False, _ts(base, 20)),
        ("note-pg-3", False, _ts(base, 30)),
    ]
    for nid, pinned, ts in rows:
        db_session.add(Note(
            id=nid,
            user_id=page_user.id,
            title=nid,
            content="x",
            is_pinned=pinned,
            created_at=ts,
            updated_at=ts,
        ))
    await db_session.commit()

    all_notes = await note_service.list_notes(db_session, page_user)
    assert [n.id for n in all_notes] == ["note-pg-1", "note-pg-3", "note-pg-2", "note-pg-0"]

    page = await note_service.list_notes(db_session, page_user, limit=2, offset=1)
    assert [n.id for n in page] == ["note-pg-3", "note-pg-2"]
