"""阶段二：文档标签 — 覆盖 / 增量 / 自动打标解析 / 批量。"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, Tag, User
from app.services import document_tag_service


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(id="dt-user", username="dtuser", email="d@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.fixture
async def doc(db_session: AsyncSession, user: User) -> Document:
    d = Document(
        id="dt-doc",
        user_id=user.id,
        filename="ml.pdf",
        file_path="/tmp/ml.pdf",
        status="ready",
        chunk_count=1,
    )
    db_session.add(d)
    await db_session.commit()
    return d


@pytest.mark.asyncio
async def test_set_document_tags_overwrites(db_session, user, doc):
    a = await document_tag_service.set_document_tags(db_session, user, doc.id, ["机器学习", "入门"])
    assert sorted(a) == ["入门", "机器学习"]
    b = await document_tag_service.set_document_tags(db_session, user, doc.id, ["深度学习"])
    assert b == ["深度学习"]
    names = await document_tag_service.list_document_tag_names(db_session, user, doc.id)
    assert names == ["深度学习"]


@pytest.mark.asyncio
async def test_add_document_tags_keeps_manual(db_session, user, doc):
    await document_tag_service.set_document_tags(db_session, user, doc.id, ["人工标签"])
    added = await document_tag_service.add_document_tags(db_session, user, doc.id, ["自动标签", "人工标签"])
    assert added == ["自动标签"]
    names = await document_tag_service.list_document_tag_names(db_session, user, doc.id)
    assert "人工标签" in names
    assert "自动标签" in names


def test_parse_auto_tag_response_filters_low_confidence():
    names = ["A", "B", "C"]
    raw = '{"tags":[{"idx":0,"confidence":0.9},{"idx":1,"confidence":0.3},{"idx":2,"confidence":0.8}],"reason":"x"}'
    out = document_tag_service._parse_auto_tag_response(raw, names)
    assert out == [("A", 0.9), ("C", 0.8)]


def test_parse_auto_tag_response_rejects_unknown_idx():
    names = ["A"]
    raw = '{"tags":[{"idx":9,"confidence":0.9}]}'
    assert document_tag_service._parse_auto_tag_response(raw, names) == []


def test_parse_auto_tag_response_handles_fenced():
    names = ["甲", "乙"]
    raw = '```json\n{"tags":[{"idx":1,"confidence":0.95}]}\n```'
    assert document_tag_service._parse_auto_tag_response(raw, names) == [("乙", 0.95)]


@pytest.mark.asyncio
async def test_auto_tag_empty_pool_returns_empty(db_session, user, doc):
    out = await document_tag_service.auto_tag_document(db_session, user, doc.id)
    assert out == []


@pytest.mark.asyncio
async def test_auto_tag_appends_from_llm(db_session, user, doc):
    # 先造标签池
    await document_tag_service.set_document_tags(db_session, user, doc.id, ["池A", "池B"])
    await document_tag_service.set_document_tags(db_session, user, doc.id, [])  # 清文档标签，池仍在

    from unittest.mock import AsyncMock, patch

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value='{"tags":[{"idx":0,"confidence":0.95}]}')

    with (
        patch("app.core.llm.LLM.from_config", return_value=mock_llm),
        patch(
            "app.services.config_service.get_llm_config_with_secret",
            new=AsyncMock(return_value={"model_name": "m"}),
        ),
    ):
        added = await document_tag_service.auto_tag_document(db_session, user, doc.id)

    names = await document_tag_service.list_document_tag_names(db_session, user, doc.id)
    assert added == ["池A"] or "池A" in names


@pytest.mark.asyncio
async def test_batch_add_tags(db_session, user, doc):
    d2 = Document(
        id="dt-doc2",
        user_id=user.id,
        filename="nlp.pdf",
        file_path="/tmp/nlp.pdf",
        status="ready",
        chunk_count=1,
    )
    db_session.add(d2)
    await db_session.commit()

    out = await document_tag_service.batch_add_tags(
        db_session, user, [doc.id, d2.id, "missing-doc"], ["批量"]
    )
    assert out[doc.id] == ["批量"]
    assert out[d2.id] == ["批量"]
    assert out["missing-doc"] == []
