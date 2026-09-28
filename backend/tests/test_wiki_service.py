"""阶段五 5.1：Wiki 概念页 — slug / [[链接]] / CRUD / 死链。"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.services import wiki_service


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(id="wk-user", username="wkuser", email="w@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u


def test_normalize_slug():
    assert wiki_service.normalize_slug("RAG-Basics") == "rag-basics"
    assert wiki_service.normalize_slug("  梯度下降  ") == "梯度下降"
    assert wiki_service.normalize_slug("a//b--c") == "a/b-c"


def test_extract_links():
    content = "参见 [[gradient-descent]] 与 [[过拟合|过拟合现象]]，重复 [[gradient-descent]]。"
    assert wiki_service.extract_links(content) == ["gradient-descent", "过拟合"]


def test_extract_links_ignores_plain_md():
    assert wiki_service.extract_links("[text](http://x)") == []


@pytest.mark.asyncio
async def test_create_and_get_page(db_session, user):
    p = await wiki_service.create_page(
        db_session,
        user,
        slug="Gradient-Descent",
        title="梯度下降",
        content="正文 [[missing-link]]",
        summary="优化算法",
    )
    assert p["slug"] == "gradient-descent"
    assert p["links"] == ["missing-link"]
    assert p["dead_links"] == ["missing-link"]

    got = await wiki_service.get_page(db_session, user, p["id"])
    assert got["title"] == "梯度下降"
    assert got["revision"] == 1


@pytest.mark.asyncio
async def test_duplicate_slug_conflict(db_session, user):
    await wiki_service.create_page(db_session, user, slug="dup", title="A")
    with pytest.raises(ConflictError):
        await wiki_service.create_page(db_session, user, slug="dup", title="B")


@pytest.mark.asyncio
async def test_update_bumps_revision(db_session, user):
    p = await wiki_service.create_page(db_session, user, slug="rev", title="R", content="v1")
    up = await wiki_service.update_page(db_session, user, p["id"], content="v2")
    assert up["revision"] == 2
    assert up["content"] == "v2"


@pytest.mark.asyncio
async def test_resolve_links_dead_vs_live(db_session, user):
    await wiki_service.create_page(db_session, user, slug="live", title="活页")
    out = await wiki_service.resolve_links(db_session, user, ["live", "dead"])
    assert out["live"]["title"] == "活页"
    assert out["dead"] is None


@pytest.mark.asyncio
async def test_delete_and_404(db_session, user):
    p = await wiki_service.create_page(db_session, user, slug="gone", title="G")
    await wiki_service.delete_page(db_session, user, p["id"])
    with pytest.raises(NotFoundError):
        await wiki_service.get_page(db_session, user, p["id"])


@pytest.mark.asyncio
async def test_invalid_slug_rejected(db_session, user):
    with pytest.raises(ValidationError):
        await wiki_service.create_page(db_session, user, slug="!!!", title="X")


@pytest.mark.asyncio
async def test_search_by_title(db_session, user):
    await wiki_service.create_page(db_session, user, slug="nn", title="神经网络", summary="深度学习")
    await wiki_service.create_page(db_session, user, slug="ll", title="线性代数", summary="数学")
    hits = await wiki_service.list_pages(db_session, user, q="神经")
    assert len(hits) == 1 and hits[0]["title"] == "神经网络"


@pytest.mark.asyncio
async def test_revision_snapshot_and_revert(db_session, user):
    p = await wiki_service.create_page(db_session, user, slug="hist", title="原题", content="v1 正文")
    await wiki_service.update_page(db_session, user, p["id"], title="新题", content="v2 正文")
    await wiki_service.update_page(db_session, user, p["id"], content="v3 正文")

    revs = await wiki_service.list_revisions(db_session, user, p["id"])
    # v1、v2 各留一份快照
    assert [r["revision"] for r in revs] == [2, 1]
    assert revs[1]["title"] == "原题"
    assert "v1" in revs[1]["content_preview"]

    # 回滚到 rev=1（原题 + v1）→ 本身成为一次新编辑
    back = await wiki_service.revert_page(db_session, user, p["id"], revision=1)
    assert back["title"] == "原题"
    assert "v1" in back["content"]
    assert back["revision"] == 4  # 1→2→3→4

    # 回滚可再回滚：再回退到刚被替换掉的 v3
    revs2 = await wiki_service.list_revisions(db_session, user, p["id"])
    assert revs2[0]["revision"] == 3
    again = await wiki_service.revert_page(db_session, user, p["id"], revision=3)
    assert "v3" in again["content"]


@pytest.mark.asyncio
async def test_revert_missing_404(db_session, user):
    p = await wiki_service.create_page(db_session, user, slug="miss", title="M")
    with pytest.raises(NotFoundError):
        await wiki_service.revert_page(db_session, user, p["id"], revision=99)
