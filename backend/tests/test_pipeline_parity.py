"""Parity tests verifying Onion Chat Pipeline matches legacy rag_engine behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.query_router import QueryAnalysis, QueryType
from app.pipeline import PipelineBuilder, execute_chat_pipeline
from app.pipeline.base import EventType, PipelineState, Plugin


@pytest.mark.asyncio
async def test_pipeline_builder():
    builder = PipelineBuilder()
    builder.add(EventType.LOAD_HISTORY)
    builder.add_if(False, EventType.MEMORY_RECALL)
    builder.add_if(True, EventType.QUERY_UNDERSTAND)
    stages = builder.build()
    assert stages == [EventType.LOAD_HISTORY, EventType.QUERY_UNDERSTAND]


@pytest.mark.asyncio
async def test_onion_ordering_execution():
    call_order = []

    class OuterPlugin(Plugin):
        def activation_events(self) -> list[EventType]:
            return [EventType.LOAD_HISTORY]

        async def on_event(self, event_type, state, next_fn):
            call_order.append("outer_enter")
            await next_fn()
            call_order.append("outer_exit")

    class InnerPlugin(Plugin):
        def activation_events(self) -> list[EventType]:
            return [EventType.LOAD_HISTORY]

        async def on_event(self, event_type, state, next_fn):
            call_order.append("inner_body")
            await next_fn()

    from app.pipeline.manager import EventManager

    mgr = EventManager()
    mgr.register(OuterPlugin())
    mgr.register(InnerPlugin())

    state = PipelineState(query="test")
    await mgr.trigger(EventType.LOAD_HISTORY, state)

    assert call_order == ["outer_enter", "inner_body", "outer_exit"]


@pytest.mark.asyncio
async def test_pipeline_out_of_scope_short_circuit():
    with patch("app.core.query_router.query_router.analyze", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            intent=QueryType.OUT_OF_SCOPE,
            standalone_query="明天天气如何？",
        )

        res = await execute_chat_pipeline(
            doc_ids=["doc-1"],
            query="明天天气如何？",
            user_config={"model": "gpt-4o"},
        )

        assert "知识范围" in res["answer"]
        assert res["context_used"] is False
        assert res["sources"] == []


@pytest.mark.asyncio
async def test_pipeline_direct_answer_short_circuit():
    with patch("app.core.query_router.query_router.analyze", new_callable=AsyncMock) as mock_analyze, \
         patch("app.core.rag_engine.rag_engine._direct_answer", new_callable=AsyncMock) as mock_direct:
        mock_analyze.return_value = QueryAnalysis(
            intent=QueryType.DIRECT_ANSWER,
            standalone_query="1+1等于几？",
        )
        mock_direct.return_value = "1+1等于2。"

        res = await execute_chat_pipeline(
            doc_ids=["doc-1"],
            query="1+1等于几？",
            user_config={"model": "gpt-4o"},
        )

        assert res["answer"] == "1+1等于2。"
        assert res["context_used"] is False


@pytest.mark.asyncio
async def test_pipeline_rag_flow_end_to_end():
    with patch("app.core.query_router.query_router.analyze", new_callable=AsyncMock) as mock_analyze, \
         patch("app.core.adaptive_retriever.adaptive_retriever.select_strategy", new_callable=AsyncMock) as mock_strategy, \
         patch("app.core.adaptive_retriever.adaptive_retriever.retrieve_adaptive", new_callable=AsyncMock) as mock_retrieve, \
         patch("app.core.retrieval_grader.retrieval_grader.grade", new_callable=AsyncMock) as mock_grade, \
         patch("app.core.rag_engine.rag_engine.generate_answer", new_callable=AsyncMock) as mock_gen, \
         patch("app.core.answer_reflector.answer_reflector.evaluate", new_callable=AsyncMock) as mock_eval:

        from app.core.adaptive_retriever import RetrievalStrategy
        from app.core.retrieval_grader import RetrievalQuality

        mock_analyze.return_value = QueryAnalysis(
            intent=QueryType.RAG_QA,
            standalone_query="什么是梯度下降？",
        )
        mock_strategy.return_value = RetrievalStrategy.STANDARD
        mock_retrieve.return_value = (
            [
                {
                    "chunk": {
                        "text": "梯度下降是一种优化算法，用于求解极值点。",
                        "document_id": "doc-1",
                        "page": "1",
                        "source": "AI基础.pdf",
                    },
                    "distance": 0.1,
                    "relevance": 0.9,
                }
            ],
            [{"type": "thinking", "step": "strategy_select", "detail": "向量检索"}],
        )
        mock_grade.return_value = RetrievalQuality(
            quality="good", reason="high_relevance", score=0.92, detail="切片高度匹配"
        )
        mock_gen.return_value = "根据[来源1]，梯度下降是一种极值优化算法。"
        mock_eval.return_value = {"pass": True, "score": 95, "reason": "事实一致"}

        res = await execute_chat_pipeline(
            doc_ids=["doc-1"],
            query="什么是梯度下降？",
            user_config={"model": "gpt-4o"},
        )

        assert "梯度下降" in res["answer"]
        assert len(res["sources"]) == 1
        assert res["used_source_indices"] == [1]
        assert len(res["filtered_sources"]) == 1
        assert res["context_used"] is True
