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
    await favorite_service.add_favorite(db_session, user, "message", "m1")
    await favorite_service.remove_favorite(db_session, user, "message", "m1")
    assert await favorite_service.list_favorites(db_session, user) == []
    with pytest.raises(NotFoundError):
        await favorite_service.remove_favorite(db_session, user, "message", "m1")


@pytest.mark.asyncio
async def test_list_filter_by_type(db_session, user):
    await favorite_service.add_favorite(db_session, user, "document", "d1")
    await favorite_service.add_favorite(db_session, user, "note", "n1")
    docs = await favorite_service.list_favorites(db_session, user, "document")
    assert len(docs) == 1 and docs[0]["resource_type"] == "document"
