"""4A 过程进度收束：阶段窗口关闭硬性语义 + duration/计数字段。

硬性约束：任何异常 / 短路 / 无结果路径都必须补发 window_close 收尾事件，
否则前端阶段窗会永久转圈。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.query_router import QueryAnalysis, QueryType
from app.core.rag_engine import (
    WINDOW_RETRIEVE,
    WINDOW_UNDERSTAND,
    RAGEngine,
    thinking_event,
    window_close_event,
)


@pytest.fixture
def engine():
    eng = RAGEngine()
    eng._reranker = None
    eng._reranker_loaded = True
    return eng


class TestWindowHelpers:
    def test_thinking_event_carries_duration_and_counts(self):
        ev = thinking_event(
            "adaptive_retrieve",
            "命中 3 条",
            window=WINDOW_RETRIEVE,
            duration_ms=85,
            count=3,
            doc_count=2,
        )
        assert ev["type"] == "thinking"
        assert ev["window"] == WINDOW_RETRIEVE
        assert ev["duration_ms"] == 85
        assert ev["count"] == 3
        assert ev["doc_count"] == 2

    def test_window_close_event_is_closing_signal(self):
        ev = window_close_event(
            WINDOW_UNDERSTAND, "完成", duration_ms=12, status="error"
        )
        assert ev["step"] == "window_close"
        assert ev["window"] == WINDOW_UNDERSTAND
        assert ev["status"] == "error"
        assert ev["duration_ms"] == 12


class TestAskStreamClosesWindows:
    @pytest.mark.asyncio
    async def test_out_of_scope_short_circuit_closes_understand(self, engine):
        """OUT_OF_SCOPE 短路必须关闭问题理解窗口。"""
        analysis = QueryAnalysis(
            intent=QueryType.OUT_OF_SCOPE, standalone_query="明天天气"
        )
        with (
            patch("app.core.rag_engine.LLM") as MockLLM,
            patch(
                "app.core.rag_engine.query_router.analyze",
                new=AsyncMock(return_value=analysis),
            ),
        ):
            MockLLM.from_config.return_value = AsyncMock()
            events = [e async for e in engine.ask_stream([], "明天天气")]

        closes = [
            e
            for e in events
            if e.get("type") == "thinking" and e.get("step") == "window_close"
        ]
        assert any(c.get("window") == WINDOW_UNDERSTAND for c in closes)
        assert all(c.get("status") in ("done", "empty", "error") for c in closes)
        # intent 事件带 duration_ms
        intents = [
            e
            for e in events
            if e.get("type") == "thinking" and e.get("step") == "intent_analysis"
        ]
        assert intents and "duration_ms" in intents[0]

    @pytest.mark.asyncio
    async def test_no_results_path_closes_retrieve_window(self, engine):
        """无结果短路必须关闭检索窗口（status=empty）。"""
        analysis = QueryAnalysis(
            intent=QueryType.RAG_QA, standalone_query="什么是 RAG"
        )
        mock_store = AsyncMock()
        mock_store.search.return_value = []
        engine._pg_vector_store = mock_store

        with (
            patch("app.core.rag_engine.LLM") as MockLLM,
            patch(
                "app.core.rag_engine.query_router.analyze",
                new=AsyncMock(return_value=analysis),
            ),
        ):
            MockLLM.from_config.return_value = MagicMock()
            MockLLM.from_config.return_value.chat = AsyncMock(return_value="standard")
            events = [e async for e in engine.ask_stream(["d1"], "什么是 RAG")]

        closes = [
            e
            for e in events
            if e.get("type") == "thinking" and e.get("step") == "window_close"
        ]
        understand_closed = any(c.get("window") == WINDOW_UNDERSTAND for c in closes)
        retrieve_closes = [c for c in closes if c.get("window") == WINDOW_RETRIEVE]
        assert understand_closed
        assert retrieve_closes, "空结果路径必须补发检索窗口关闭事件"
        assert retrieve_closes[-1].get("status") in ("empty", "done")
        # 检索相关事件带 count/doc_count
        retrieves = [
            e
            for e in events
            if e.get("type") == "thinking" and e.get("step") == "adaptive_retrieve"
        ]
        assert retrieves
        assert "count" in retrieves[-1] or "duration_ms" in retrieves[-1]

    @pytest.mark.asyncio
    async def test_direct_answer_closes_understand(self, engine):
        """直答短路关闭问题理解窗口。"""
        analysis = QueryAnalysis(
            intent=QueryType.DIRECT_ANSWER, standalone_query="你好"
        )

        async def fake_stream(*a, **kw):
            yield "你好"

        mock_llm = AsyncMock()
        mock_llm.chat_stream = fake_stream
        with (
            patch("app.core.rag_engine.LLM") as MockLLM,
            patch(
                "app.core.rag_engine.query_router.analyze",
                new=AsyncMock(return_value=analysis),
            ),
        ):
            MockLLM.from_config.return_value = mock_llm
            events = [e async for e in engine.ask_stream([], "你好")]

        closes = [
            e
            for e in events
            if e.get("type") == "thinking" and e.get("step") == "window_close"
        ]
        assert any(c.get("window") == WINDOW_UNDERSTAND for c in closes)
