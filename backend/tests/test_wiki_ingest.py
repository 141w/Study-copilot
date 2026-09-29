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


# ---------------------------------------------------------------------------
# F5 · 摄入合并必须写版本快照（fix(phase2-audit): F5）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_f5_merge_writes_revision_snapshot(db_session, user, doc):
    """同 slug 重跑两次（第二次带新摘录）：wiki_page_revisions 必须出现第 1 版快照。

    改前：合并只抬 revision 不写 WikiPageRevision，用户手写正文被覆盖后
    永久不可恢复、回滚列表错位。
    """
    from sqlalchemy import select

    from app.db import WikiPageRevision

    calls = {"n": 0}

    async def fake_chat(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return '[{"slug":"gd2","title":"梯度下降","summary":"s","content":"正文A"}]'
        return '[{"slug":"gd2","title":"梯度下降","summary":"s","content":"正文B-新增摘录"}]'

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

    page = (
        await db_session.execute(select(WikiPage).where(WikiPage.slug == "gd2"))
    ).scalar_one()
    revs = (
        await db_session.execute(
            select(WikiPageRevision).where(WikiPageRevision.page_id == page.id)
        )
    ).scalars().all()
    assert len(revs) >= 1, "合并路径必须写快照，否则手写正文被覆盖后无法回滚"
    assert revs[0].revision == 1
    assert "正文A" in (revs[0].content or ""), "快照应是被覆盖前的正文"
    assert page.revision >= 2


@pytest.mark.asyncio
async def test_f5_prompt_includes_existing_slugs(db_session, user, doc):
    """提示词必须注入已有 slug/title 清单，否则模型无从复用 → 中英拆两页。"""
    from app.db import WikiPage

    db_session.add(
        WikiPage(
            id="exist-1",
            user_id=user.id,
            slug="gradient-descent",
            title="梯度下降",
            content="x",
            summary="",
            revision=1,
        )
    )
    await db_session.commit()

    captured: dict = {}

    async def fake_chat(messages=None, **kwargs):
        # chat(messages, temperature=..., max_tokens=...) — messages 可能是位置参数
        captured["messages"] = messages if messages is not None else kwargs.get("messages")
        if not captured["messages"] and "args" not in captured:
            pass
        return "[]"

    # 也兼容位置参数调用
    async def fake_chat2(*args, **kwargs):
        captured["messages"] = args[0] if args else kwargs.get("messages")
        return "[]"

    mock_llm = AsyncMock()
    mock_llm.chat = fake_chat2
    with (
        patch("app.core.llm.LLM.from_config", return_value=mock_llm),
        patch(
            "app.services.config_service.get_llm_config_with_secret",
            new=AsyncMock(return_value={"model_name": "m"}),
        ),
    ):
        await wiki_ingest_service.ingest_from_sources(
            db_session, user, document_ids=[doc.id], max_pages=5
        )

    blob = str(captured.get("messages"))
    assert "gradient-descent" in blob, "提示词未注入已有 slug"
    assert "梯度下降" in blob, "提示词未注入已有 title"


@pytest.mark.asyncio
async def test_f5_merge_respects_max_content(db_session, user, doc):
    """合并超 MAX_CONTENT 必须记 error，不得静默截断。"""
    from app.db import WikiPage

    big = "x" * 199_990  # 追加「来源摘录」段后必超 MAX_CONTENT=200000
    db_session.add(
        WikiPage(
            id="big-1",
            user_id=user.id,
            slug="big",
            title="大页",
            content=big,
            summary="",
            revision=1,
        )
    )
    await db_session.commit()

    async def fake_chat(*args, **kwargs):
        return '[{"slug":"big","title":"大页","summary":"","content":"新增摘录"}]'

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

    assert any("过长" in e or "内容" in e for e in out.get("errors", [])), (
        f"超限应记 error，got errors={out.get('errors')}"
    )


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
