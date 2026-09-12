"""Unit tests for Agent tools execute paths and ContextCompactor."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.context import ContextCompactor, estimate_tokens
from app.agent.tools.base import ToolRegistry, ToolResult
from app.agent.tools.definitions import (
    GetDocumentInfoTool,
    GrepChunksTool,
    KnowledgeSearchTool,
    ListDocumentChunksTool,
    SearchConversationsTool,
    SearchMemoryTool,
)

# ---------------------------------------------------------------------------
# KnowledgeSearchTool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_knowledge_search_empty_query():
    tool = KnowledgeSearchTool()
    with patch(
        "app.agent.tools.definitions.rag_engine.retrieve", new_callable=AsyncMock
    ) as mock_ret:
        mock_ret.return_value = []
        res = await tool.execute(query="")
        assert res.success is True
        assert "未检索到" in res.output


@pytest.mark.asyncio
async def test_knowledge_search_with_results():
    tool = KnowledgeSearchTool()
    with patch(
        "app.agent.tools.definitions.rag_engine.retrieve", new_callable=AsyncMock
    ) as mock_ret:
        mock_ret.return_value = [
            {
                "chunk": {
                    "text": "梯度下降是优化算法",
                    "page": "2",
                    "source": "ml.pdf",
                    "document_id": "d1",
                },
                "relevance": 0.9,
            }
        ]
        res = await tool.execute(query="梯度下降", doc_ids=["d1"], top_k=3)
        assert res.success is True
        assert "ml.pdf" in res.output
        assert "梯度下降" in res.output


@pytest.mark.asyncio
async def test_knowledge_search_failure():
    tool = KnowledgeSearchTool()
    with patch(
        "app.agent.tools.definitions.rag_engine.retrieve", new_callable=AsyncMock
    ) as mock_ret:
        mock_ret.side_effect = RuntimeError("vector store down")
        res = await tool.execute(query="x")
        assert res.success is False
        assert "检索失败" in res.output


# ---------------------------------------------------------------------------
# GrepChunksTool / ListDocumentChunksTool / GetDocumentInfoTool
# ---------------------------------------------------------------------------


def _mock_db_session(chunks=None, doc=None, empty_doc=False):
    """Build a fake AsyncSessionLocal context manager returning rows."""
    db = MagicMock()
    execute = AsyncMock()

    class _Res:
        def scalars(self):
            return SimpleNamespace(all=lambda: chunks or [])

        def all(self):
            # Document.id/filename projection for _load_filename_map
            return []

        def scalar_one_or_none(self):
            return None if empty_doc else doc

    execute.return_value = _Res()
    db.execute = execute
    return db


@pytest.mark.asyncio
async def test_grep_chunks_empty_keyword():
    tool = GrepChunksTool()
    res = await tool.execute(keyword="")
    assert res.success is False
    assert res.error == "empty_keyword"


@pytest.mark.asyncio
async def test_grep_chunks_found():
    tool = GrepChunksTool()
    chunk = SimpleNamespace(
        id="c1",
        document_id="d1",
        content="这段话包含梯度下降关键词",
        chunk_metadata={"page": 3},
    )
    db = _mock_db_session(chunks=[chunk])
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.agent.tools.definitions.AsyncSessionLocal", return_value=cm):
        res = await tool.execute(keyword="梯度下降", doc_ids=["d1"], limit=5)
    assert res.success is True
    assert "梯度下降" in res.output
    # Structured shape for the engine source pool (not raw chunk ids)
    assert isinstance(res.data, list) and len(res.data) == 1
    assert res.data[0]["chunk"]["text"] == "这段话包含梯度下降关键词"
    assert res.data[0]["chunk"]["document_id"] == "d1"


@pytest.mark.asyncio
async def test_grep_chunks_none_found():
    tool = GrepChunksTool()
    db = _mock_db_session(chunks=[])
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.agent.tools.definitions.AsyncSessionLocal", return_value=cm):
        res = await tool.execute(keyword="不存在的词")
    assert res.success is True
    assert "未找到" in res.output


@pytest.mark.asyncio
async def test_list_document_chunks_requires_doc_id():
    tool = ListDocumentChunksTool()
    res = await tool.execute()
    assert res.success is False
    assert res.error == "missing_doc_id"


@pytest.mark.asyncio
async def test_list_document_chunks_ok():
    tool = ListDocumentChunksTool()
    chunks = [
        SimpleNamespace(
            id="c1",
            chunk_index=0,
            document_id="d1",
            content="第一块",
            chunk_metadata={"page": 1},
        ),
        SimpleNamespace(
            id="c2",
            chunk_index=1,
            document_id="d1",
            content="第二块",
            chunk_metadata={"page": 2},
        ),
    ]
    db = _mock_db_session(chunks=chunks)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.agent.tools.definitions.AsyncSessionLocal", return_value=cm):
        res = await tool.execute(document_id="d1", offset=0, limit=5)
    assert res.success is True
    assert "第一块" in res.output
    assert "第二块" in res.output
    assert isinstance(res.data, list) and len(res.data) == 2
    assert res.data[0]["chunk"]["text"] == "第一块"
    assert res.data[1]["chunk"]["page"] == "2"


@pytest.mark.asyncio
async def test_get_document_info_not_found():
    tool = GetDocumentInfoTool()
    db = _mock_db_session(empty_doc=True)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.agent.tools.definitions.AsyncSessionLocal", return_value=cm):
        res = await tool.execute(document_id="missing")
    assert res.success is False
    assert res.error == "not_found"


@pytest.mark.asyncio
async def test_get_document_info_ok():
    tool = GetDocumentInfoTool()
    doc = SimpleNamespace(
        id="d1",
        filename="ai.pdf",
        chunk_count=12,
        file_size=1024,
        status="ready",
        created_at="2026-01-01",
    )
    db = _mock_db_session(doc=doc)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.agent.tools.definitions.AsyncSessionLocal", return_value=cm):
        res = await tool.execute(document_id="d1")
    assert res.success is True
    assert "ai.pdf" in res.output
    assert res.data["chunk_count"] == 12


# ---------------------------------------------------------------------------
# SearchConversationsTool / SearchMemoryTool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_conversations_empty_query():
    tool = SearchConversationsTool()
    res = await tool.execute(query="")
    assert res.success is False
    assert res.error == "empty_query"


@pytest.mark.asyncio
async def test_search_conversations_requires_user_id():
    """No identity → refuse; must never fall back to a global scan."""
    tool = SearchConversationsTool()
    res = await tool.execute(query="线性代数")
    assert res.success is False
    assert res.error == "missing_user_id"


@pytest.mark.asyncio
async def test_search_conversations_hits():
    tool = SearchConversationsTool()
    msg = SimpleNamespace(id="m1", role="user", content="如何学习线性代数？")
    db = _mock_db_session(chunks=[msg])
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.agent.tools.definitions.AsyncSessionLocal", return_value=cm):
        res = await tool.execute(query="线性代数", user_id="u1")
    assert res.success is True
    assert "线性代数" in res.output


@pytest.mark.asyncio
async def test_search_memory_no_user():
    tool = SearchMemoryTool()
    res = await tool.execute(query="偏好")
    assert res.success is False
    assert "未绑定" in res.output


@pytest.mark.asyncio
async def test_search_memory_disabled():
    tool = SearchMemoryTool()
    db = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.agent.tools.definitions.AsyncSessionLocal", return_value=cm),
        patch(
            "app.agent.tools.definitions.memory_service.search", new_callable=AsyncMock
        ) as mock_search,
    ):
        mock_search.return_value = {"available": False, "items": []}
        res = await tool.execute(query="偏好", user_id="u1")
    assert res.success is True
    assert "关闭" in res.output


@pytest.mark.asyncio
async def test_search_memory_hits():
    tool = SearchMemoryTool()
    db = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    item = SimpleNamespace(kind="preference", content="喜欢简明回答", id="mem-1")
    with (
        patch("app.agent.tools.definitions.AsyncSessionLocal", return_value=cm),
        patch(
            "app.agent.tools.definitions.memory_service.search", new_callable=AsyncMock
        ) as mock_search,
    ):
        mock_search.return_value = {"available": True, "items": [item]}
        res = await tool.execute(query="偏好", user_id="u1")
    assert res.success is True
    assert "喜欢简明回答" in res.output
    assert res.data == ["mem-1"]


# ---------------------------------------------------------------------------
# Tool schema / registry
# ---------------------------------------------------------------------------


def test_all_default_tools_schemas_are_valid():
    from app.agent import AgentEngine

    engine = AgentEngine()
    schemas = engine.registry.to_openai_schemas()
    assert len(schemas) == 6
    for s in schemas:
        assert s["type"] == "function"
        assert s["function"]["name"]
        assert s["function"]["parameters"]["type"] == "object"


def test_registry_list_and_get():
    registry = ToolRegistry()
    registry.register(KnowledgeSearchTool())
    assert registry.get("knowledge_search") is not None
    assert registry.get("nope") is None
    assert len(registry.list_tools()) == 1


# ---------------------------------------------------------------------------
# ContextCompactor
# ---------------------------------------------------------------------------


def test_estimate_tokens_counts_content_and_tools():
    msgs = [
        {"role": "system", "content": "你是一个助手"},
        {
            "role": "assistant",
            "content": "先检索",
            "tool_calls": [
                {"function": {"name": "knowledge_search", "arguments": '{"query":"x"}'}}
            ],
        },
        {"role": "tool", "content": "结果片段"},
    ]
    tokens = estimate_tokens(msgs)
    assert tokens > 20


@pytest.mark.asyncio
async def test_compactor_skips_when_under_budget():
    compactor = ContextCompactor(max_context_tokens=100000, keep_recent_messages=2)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "好的"},
    ]
    llm = MagicMock()
    out = await compactor.maybe_compact(messages, llm)
    assert out == messages


@pytest.mark.asyncio
async def test_compactor_summarizes_when_over_budget():
    compactor = ContextCompactor(max_context_tokens=50, keep_recent_messages=2)
    long_text = "研究内容。" * 200
    messages = [
        {"role": "system", "content": "sys prompt"},
        {"role": "user", "content": long_text},
        {"role": "assistant", "content": "早期回答"},
        {"role": "user", "content": "继续深入"},
        {"role": "assistant", "content": "更多细节"},
        {"role": "user", "content": "最近问题"},
    ]
    llm = MagicMock()
    llm.chat = AsyncMock(return_value="这是浓缩摘要")

    out = await compactor.maybe_compact(messages, llm)
    assert out[0]["role"] == "system"
    assert out[0]["content"] == "sys prompt"
    assert "摘要" in out[1]["content"]
    assert out[-1]["content"] == "最近问题"
    llm.chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_compactor_falls_back_to_truncation_on_llm_error():
    compactor = ContextCompactor(max_context_tokens=50, keep_recent_messages=2)
    long_text = "内容" * 300
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": long_text},
        {"role": "assistant", "content": "a"},
        {"role": "user", "content": "b"},
        {"role": "assistant", "content": "c"},
        {"role": "user", "content": "d"},
    ]
    llm = MagicMock()
    llm.chat = AsyncMock(side_effect=RuntimeError("llm down"))

    out = await compactor.maybe_compact(messages, llm)
    assert out[0]["content"] == "sys"
    assert len(out) == 1 + 2  # system + keep_recent
    assert out[-1]["content"] == "d"
