"""P0-B favorites: type allowlist + CRUD + idempotent add."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.exceptions import NotFoundError, ValidationError
from app.services import favorite_service


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(id="fav-user", username="favuser", email="f@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.mark.asyncio
async def test_add_and_list_favorite(db_session, user):
    got = await favorite_service.add_favorite(db_session, user, "document", "doc-1")
    assert got["resource_type"] == "document"
    assert got["resource_id"] == "doc-1"

    items = await favorite_service.list_favorites(db_session, user)
    assert len(items) == 1
    assert items[0]["id"] == got["id"]


@pytest.mark.asyncio
async def test_add_is_idempotent(db_session, user):
    a = await favorite_service.add_favorite(db_session, user, "note", "n1")
    b = await favorite_service.add_favorite(db_session, user, "note", "n1")
    assert a["id"] == b["id"]
    items = await favorite_service.list_favorites(db_session, user, "note")
    assert len(items) == 1


@pytest.mark.asyncio
async def test_invalid_type_rejected(db_session, user):
    with pytest.raises(ValidationError):
        await favorite_service.add_favorite(db_session, user, "hack", "x")
    with pytest.raises(ValidationError):
        await favorite_service.add_favorite(db_session, user, "document", "  ")


@pytest.mark.asyncio
async def test_remove_favorite(db_session, user):
    # F8：message 已移出白名单；删除幂等（重复删不再抛 NotFoundError）
    await favorite_service.add_favorite(db_session, user, "note", "m1")
    await favorite_service.remove_favorite(db_session, user, "note", "m1")
    assert await favorite_service.list_favorites(db_session, user) == []
    # 幂等：再删一次不抛
    await favorite_service.remove_favorite(db_session, user, "note", "m1")


@pytest.mark.asyncio
async def test_list_filter_by_type(db_session, user):
    await favorite_service.add_favorite(db_session, user, "document", "d1")
    await favorite_service.add_favorite(db_session, user, "note", "n1")
    docs = await favorite_service.list_favorites(db_session, user, "document")
    assert len(docs) == 1 and docs[0]["resource_type"] == "document"


# ---------------------------------------------------------------------------
# F8 · 收藏并发/幂等/可读性（fix(phase2-audit): F8）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_f8_add_is_idempotent_and_delete_is_idempotent(db_session, user):
    """重复添加不重复入库；重复删除返回成功而非报错。"""
    a = await favorite_service.add_favorite(db_session, user, "note", "n1")
    b = await favorite_service.add_favorite(db_session, user, "note", "n1")
    assert a["id"] == b["id"]

    await favorite_service.remove_favorite(db_session, user, "note", "n1")
    # 幂等：再删一次不抛
    await favorite_service.remove_favorite(db_session, user, "note", "n1")


@pytest.mark.asyncio
async def test_f8_list_returns_title(db_session, user):
    """列表须 join 回标题，否则只有 (type,id) 无法辨认。"""
    from app.db import Note

    db_session.add(
        Note(
            id="fav-note",
            user_id=user.id,
            title="收藏的笔记",
            content="x",
            note_type="manual",
        )
    )
    await db_session.commit()
    await favorite_service.add_favorite(db_session, user, "note", "fav-note")
    items = await favorite_service.list_favorites(db_session, user)
    assert items
    assert items[0].get("title") == "收藏的笔记"


@pytest.mark.asyncio
async def test_f8_message_type_removed_from_allowlist(db_session, user):
    """message 是死枚举（无星标入口）——从白名单去掉，避免假能力。"""
    assert "message" not in favorite_service.ALLOWED_TYPES
    with pytest.raises(ValidationError):
        await favorite_service.add_favorite(db_session, user, "message", "m1")


@pytest.mark.asyncio
async def test_f8_document_delete_clears_favorites(db_session, user):
    """删文档后收藏列表不得再出现孤儿。"""
    from app.db import Document
    from app.services import document_service
    from app.services import favorite_service as fs

    d = Document(
        id="fav-doc",
        user_id=user.id,
        filename="a.pdf",
        file_path="/tmp/a.pdf",
        status="ready",
        chunk_count=0,
    )
    db_session.add(d)
    await db_session.commit()
    await fs.add_favorite(db_session, user, "document", "fav-doc")
    await document_service.delete_document(db_session, user, "fav-doc")
    items = await fs.list_favorites(db_session, user, "document")
    assert items == [] or all(i["resource_id"] != "fav-doc" for i in items)
