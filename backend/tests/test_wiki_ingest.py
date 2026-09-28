"""阶段五 5.2：Wiki 摄入 — JSON 解析 / 合并语义 / LLM 失败降级。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentChunk, User, WikiPage
from app.exceptions import ValidationError
from app.services import wiki_ingest_service


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(id="wi-user", username="wiuser", email="wi@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.fixture
async def doc(db_session: AsyncSession, user: User) -> Document:
    d = Document(
        id="wi-doc",
        user_id=user.id,
        filename="ml.md",
        file_path="/tmp/ml.md",
        status="ready",
        chunk_count=1,
    )
    db_session.add(d)
    db_session.add(
        DocumentChunk(
            id="wi-c1",
            document_id=d.id,
            content="梯度下降是优化算法。过拟合需要正则化。",
            chunk_index=0,
            chunk_metadata={},
        )
    )
    await db_session.commit()
    return d


def test_parse_pages_from_fenced_json():
    raw = '```json\n[{"slug":"gd","title":"梯度下降","summary":"优化","content":"正文"}]\n```'
    pages = wiki_ingest_service._parse_pages(raw)
    assert pages[0]["slug"] == "gd"
    assert pages[0]["title"] == "梯度下降"


def test_parse_pages_skips_invalid():
    raw = '[{"slug":"","title":""},{"slug":"ok","title":"好"}]'
    pages = wiki_ingest_service._parse_pages(raw)
    assert len(pages) == 1


def test_parse_pages_garbage():
    assert wiki_ingest_service._parse_pages("not json") == []
    assert wiki_ingest_service._parse_pages(None) == []


@pytest.mark.asyncio
async def test_ingest_creates_pages(db_session, user, doc):
    async def fake_chat(*args, **kwargs):
        return '[{"slug":"gradient","title":"梯度下降","summary":"优化","content":"[[regularization]] 相关"}]'

    mock_llm = AsyncMock()
    mock_llm.chat = fake_chat
    with (
        patch("app.core.llm.LLM.from_config", return_value=mock_llm),
        patch(
            "app.services.config_service.get_llm_config_with_secret",
            new=AsyncMock(return_value={"model_name": "m"}),
        ),
    ):
        out = await wiki_ingest_service.ingest_from_sources(
            db_session, user, document_ids=[doc.id], max_pages=5
        )

    assert out["created"] == 1
    p = (
        await db_session.execute(
            __import__("sqlalchemy").select(WikiPage).where(WikiPage.slug == "gradient")
        )
    ).scalar_one()
    assert p.title == "梯度下降"


@pytest.mark.asyncio
async def test_ingest_merges_same_slug(db_session, user, doc):
    async def fake_chat(*args, **kwargs):
        return '[{"slug":"same","title":"同概念","summary":"","content":"第一次内容块"}]'

    mock_llm = AsyncMock()
    mock_llm.chat = fake_chat
    patchers = (
        patch("app.core.llm.LLM.from_config", return_value=mock_llm),
        patch(
            "app.services.config_service.get_llm_config_with_secret",
            new=AsyncMock(return_value={"model_name": "m"}),
        ),
    )
    for p in patchers:
        p.start()
    try:
        await wiki_ingest_service.ingest_from_sources(
            db_session, user, document_ids=[doc.id], max_pages=5
        )
        await wiki_ingest_service.ingest_from_sources(
            db_session, user, document_ids=[doc.id], max_pages=5
        )
    finally:
        for p in patchers:
            p.stop()

    from sqlalchemy import select

    rows = (
        await db_session.execute(select(WikiPage).where(WikiPage.slug == "same"))
    ).scalars().all()
    assert len(rows) == 1
    assert "第一次内容块" in (rows[0].content or "")


@pytest.mark.asyncio
async def test_ingest_requires_sources(db_session, user):
    with pytest.raises(ValidationError):
        await wiki_ingest_service.ingest_from_sources(db_session, user)


@pytest.mark.asyncio
async def test_llm_failure_reports_error(db_session, user, doc):
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(side_effect=RuntimeError("boom"))
    with (
        patch("app.core.llm.LLM.from_config", return_value=mock_llm),
        patch(
            "app.services.config_service.get_llm_config_with_secret",
            new=AsyncMock(return_value={"model_name": "m"}),
        ),
    ):
        out = await wiki_ingest_service.ingest_from_sources(
            db_session, user, document_ids=[doc.id]
        )
    assert out["pages"] == []
    assert out["errors"]
