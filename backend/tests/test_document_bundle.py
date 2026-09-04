"""document_bundle 单测 + discuss 端点 context_mode/归属校验测试（批次10）。

覆盖：
1. build_bundle：多文档打包、来源标注、CJK 预算截断、单文件超限
2. build_bundle_from_doc_ids：按 id 从库构建、缺失 id 安全返回
3. discuss：full_docs 模式走 bundle；rag_snippets 默认；越权 doc_ids 被过滤
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.document_bundle import build_bundle, build_bundle_from_doc_ids
from app.db import Document, DocumentChunk


# ── 纯函数：build_bundle ──────────────────────────────────────────────────────


async def test_build_bundle_multi_document_with_source_headers():
    result = await build_bundle([
        ("线性代数.pdf", "向量空间的内容"),
        ("概率论.pdf", "概率密度的内容"),
    ])

    assert result.source_names == ["线性代数.pdf", "概率论.pdf"]
    assert "【来源 1】线性代数.pdf" in result.text
    assert "【来源 2】概率论.pdf" in result.text
    assert "---" in result.text  # 分节符
    assert result.truncated is False
    # total_chars = 各节 头部+1换行+正文 的累计（分节符不计入预算）
    expected = sum(
        len(h) + 1 + len(b)
        for h, b in [
            ("【来源 1】线性代数.pdf", "向量空间的内容"),
            ("【来源 2】概率论.pdf", "概率密度的内容"),
        ]
    )
    assert result.total_chars == expected


async def test_build_bundle_respects_max_files():
    docs = [(f"文档{i}.txt", "内容") for i in range(8)]
    result = await build_bundle(docs)
    assert len(result.source_names) == 5  # MAX_FILES


async def test_build_bundle_truncation_at_cjk_boundary():
    # 单文档超 1M 预算 → 截断且 truncated=True
    from app.core.document_bundle import MAX_TEXT_CHARS
    long_text = "这是很长的内容。" * (MAX_TEXT_CHARS // 7 + 10)  # 约 1M+ 字符
    result = await build_bundle([("大文档.txt", long_text)])
    assert result.truncated is True
    assert result.total_chars <= MAX_TEXT_CHARS
    # 截断后文本显著短于原文
    assert len(result.text) < len(long_text)
    # 不在汉字/句读中间切断
    assert result.text[-1] in ("。", "！", "？", ".", "!", "?", "，", " ", "\n")


async def test_build_bundle_empty_input():
    result = await build_bundle([])
    assert result.text == ""
    assert result.source_names == []


# ── DB 路径：build_bundle_from_doc_ids ────────────────────────────────────────


@pytest.fixture
async def seeded_docs(db_session):
    from app.db import User
    from app.utils.auth import get_password_hash

    user = User(
        id="u-bundle",
        username="bundleuser",
        email="b@example.com",
        password_hash=get_password_hash("x12345"),
    )
    db_session.add(user)
    await db_session.flush()

    d1 = Document(id="bd1", user_id=user.id, filename="线代.pdf", file_path="/x", status="ready")
    d2 = Document(id="bd2", user_id=user.id, filename="概率.pdf", file_path="/y", status="ready")
    db_session.add_all([d1, d2])
    await db_session.flush()
    db_session.add_all([
        DocumentChunk(id="bc11", document_id="bd1", content="线度独立", chunk_index=0),
        DocumentChunk(id="bc12", document_id="bd1", content="基与坐标", chunk_index=1),
        DocumentChunk(id="bc21", document_id="bd2", content="贝叶斯公式", chunk_index=0),
    ])
    await db_session.commit()
    return user


async def test_bundle_from_doc_ids_groups_and_orders(db_session, seeded_docs):
    result = await build_bundle_from_doc_ids(db_session, ["bd1", "bd2"])
    assert set(result.source_names) == {"线代.pdf", "概率.pdf"}
    assert "线度独立" in result.text
    assert "基与坐标" in result.text
    assert "贝叶斯公式" in result.text
    # 线代.pdf 的两个 chunk 在同一节内按序拼接
    assert result.text.index("线度独立") < result.text.index("基与坐标")


async def test_bundle_from_doc_ids_missing_ids(db_session, seeded_docs):
    result = await build_bundle_from_doc_ids(db_session, ["nope", "bd1"])
    assert result.source_names == ["线代.pdf"]
    assert "贝叶斯公式" not in result.text


# ── discuss 端点：context_mode + 归属过滤 ────────────────────────────────────


async def test_discuss_drops_non_owned_doc_ids(client, seeded_docs, db_session, monkeypatch):
    """其他用户的文档 id 被过滤，不进入检索/打包。"""
    # 另一个用户的文档
    from app.db import User

    other = User(
        id="u-other2",
        username="otheruser",
        email="o2@example.com",
        password_hash="x",
    )
    db_session.add(other)
    await db_session.flush()
    from app.utils.auth import get_password_hash

    secret_doc = Document(
        id="secret-doc",
        user_id=other.id,
        filename="机密.pdf",
        file_path="/s",
        status="ready",
    )
    db_session.add(secret_doc)
    db_session.add(DocumentChunk(id="sc1", document_id="secret-doc", content="机密内容不得外泄", chunk_index=0))
    await db_session.commit()

    captured: dict = {}

    import app.api.chat as chat_api
    import app.core.persona_discussion as pd_mod
    import app.services.config_service as config_service
    from app.api.auth import get_current_user
    from app.main import app

    async def fake_discuss(topic, personas=None, context="", llm_config=None, max_turns=2):
        captured["context"] = context
        yield {"type": "done"}

    async def fake_user_config(db, user):
        return {"api_key": "k", "base_url": "http://x", "model": "m"}

    app.dependency_overrides[get_current_user] = lambda: seeded_docs
    try:
        with (
            patch.object(pd_mod, "discuss", fake_discuss),
            patch.object(config_service, "get_llm_config_with_secret", fake_user_config),
            patch.object(chat_api, "_chat_limiter") as lim,
        ):
            lim.check = lambda request: True
            resp = await client.post(
                "/api/chat/discuss",
                json={
                    "question": "讨论向量空间",
                    "document_ids": ["bd1", "secret-doc"],
                    "context_mode": "full_docs",
                    "max_turns": 1,
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    # 机密文档内容绝不进入讨论上下文
    assert "机密内容不得外泄" not in captured.get("context", "")
    # 归属文档正常打包
    assert "线度独立" in captured.get("context", "")


async def test_discuss_full_docs_mode_uses_bundle(client, seeded_docs, monkeypatch):
    """full_docs 模式：上下文是 bundle 全文（带来源头），而非 RAG 片段。"""
    captured: dict = {}

    async def fake_discuss(topic, personas=None, context="", llm_config=None, max_turns=2):
        captured["context"] = context
        yield {"type": "done"}

    import app.api.chat as chat_api
    import app.core.persona_discussion as pd_mod
    import app.services.config_service as config_service
    from app.api.auth import get_current_user
    from app.main import app

    async def fake_user_config(db, user):
        return {"api_key": "k", "base_url": "http://x", "model": "m"}

    app.dependency_overrides[get_current_user] = lambda: seeded_docs
    try:
        with (
            patch.object(pd_mod, "discuss", fake_discuss),
            patch.object(config_service, "get_llm_config_with_secret", fake_user_config),
            patch.object(chat_api, "_chat_limiter") as lim,
        ):
            lim.check = lambda request: True
            resp = await client.post(
                "/api/chat/discuss",
                json={
                    "question": "讨论",
                    "document_ids": ["bd1"],
                    "context_mode": "full_docs",
                    "max_turns": 1,
                },
            )
        assert resp.status_code == 200
        # bundle 特征：来源头标注
        assert "【来源 1】线代.pdf" in captured.get("context", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
