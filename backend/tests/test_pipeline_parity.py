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
    with patch(
        "app.core.query_router.query_router.analyze", new_callable=AsyncMock
    ) as mock_analyze:
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
    with (
        patch("app.core.query_router.query_router.analyze", new_callable=AsyncMock) as mock_analyze,
        patch(
            "app.core.rag_engine.rag_engine._direct_answer", new_callable=AsyncMock
        ) as mock_direct,
    ):
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
    with (
        patch("app.core.query_router.query_router.analyze", new_callable=AsyncMock) as mock_analyze,
        patch(
            "app.core.adaptive_retriever.adaptive_retriever.select_strategy", new_callable=AsyncMock
        ) as mock_strategy,
        patch(
            "app.core.adaptive_retriever.adaptive_retriever.retrieve_adaptive",
            new_callable=AsyncMock,
        ) as mock_retrieve,
        patch(
            "app.core.retrieval_grader.retrieval_grader.grade", new_callable=AsyncMock
        ) as mock_grade,
        patch("app.core.rag_engine.rag_engine.generate_answer", new_callable=AsyncMock) as mock_gen,
        patch(
            "app.core.answer_reflector.answer_reflector.evaluate", new_callable=AsyncMock
        ) as mock_eval,
    ):
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


# ---------------------------------------------------------------------------
# Streaming pipeline (PIPELINE_V2 on SSE main path)
# ---------------------------------------------------------------------------


async def _collect_stream(**kwargs):
    from app.pipeline import execute_chat_pipeline_stream

    events = []
    async for ev in execute_chat_pipeline_stream(**kwargs):
        events.append(ev)
    return events


@pytest.mark.asyncio
async def test_pipeline_stream_out_of_scope():
    with patch(
        "app.core.query_router.query_router.analyze", new_callable=AsyncMock
    ) as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            intent=QueryType.OUT_OF_SCOPE,
            standalone_query="明天天气如何？",
        )
        events = await _collect_stream(
            doc_ids=["doc-1"],
            query="明天天气如何？",
            user_config={"model": "gpt-4o"},
        )
        types = [e["type"] for e in events]
        assert "thinking" in types
        assert "answer" in types
        answer = next(e for e in events if e["type"] == "answer")
        assert "知识范围" in answer["content"]


@pytest.mark.asyncio
async def test_pipeline_stream_direct_answer_tokens():
    with (
        patch("app.core.query_router.query_router.analyze", new_callable=AsyncMock) as mock_analyze,
        patch("app.core.llm.LLM.chat_stream") as mock_stream,
    ):
        mock_analyze.return_value = QueryAnalysis(
            intent=QueryType.DIRECT_ANSWER,
            standalone_query="1+1等于几？",
        )

        async def fake_stream(messages, **kwargs):
            for t in ["1", "+1", "等于2"]:
                yield t

        mock_stream.side_effect = lambda *a, **k: fake_stream(*a, **k)

        events = await _collect_stream(
            doc_ids=["doc-1"],
            query="1+1等于几？",
            user_config={"model": "gpt-4o"},
        )
        tokens = [e["content"] for e in events if e["type"] == "token"]
        assert tokens == ["1", "+1", "等于2"]
        thinking = [e for e in events if e["type"] == "thinking"]
        assert any(e["step"] == "intent_analysis" for e in thinking)


@pytest.mark.asyncio
async def test_pipeline_stream_rag_full_flow():
    with (
        patch("app.core.query_router.query_router.analyze", new_callable=AsyncMock) as mock_analyze,
        patch(
            "app.core.adaptive_retriever.adaptive_retriever.select_strategy", new_callable=AsyncMock
        ) as mock_strategy,
        patch(
            "app.core.adaptive_retriever.adaptive_retriever.retrieve_adaptive",
            new_callable=AsyncMock,
        ) as mock_retrieve,
        patch(
            "app.core.retrieval_grader.retrieval_grader.grade", new_callable=AsyncMock
        ) as mock_grade,
        patch("app.core.rag_engine.rag_engine.generate_answer_stream") as mock_gen,
        patch(
            "app.core.answer_reflector.answer_reflector.evaluate", new_callable=AsyncMock
        ) as mock_eval,
    ):
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

        async def fake_gen(*args, **kwargs):
            yield {"type": "token", "content": "根据[来源1]，"}
            yield {"type": "token", "content": "梯度下降是极值优化算法。"}

        mock_gen.side_effect = lambda *a, **k: fake_gen(*a, **k)
        mock_eval.return_value = {"pass": True, "score": 95, "reason": "事实一致"}

        events = await _collect_stream(
            doc_ids=["doc-1"],
            query="什么是梯度下降？",
            user_config={"model": "gpt-4o"},
        )

        assert any(e["type"] == "sources" for e in events)
        tokens = [e["content"] for e in events if e["type"] == "token"]
        assert "梯度下降" in "".join(tokens)
        reflections = [e for e in events if e.get("step") in ("reflection_pass", "reflection_fail")]
        assert len(reflections) == 1
        assert reflections[0]["step"] == "reflection_pass"


@pytest.mark.asyncio
async def test_pipeline_stream_empty_search_short_circuit():
    with (
        patch("app.core.query_router.query_router.analyze", new_callable=AsyncMock) as mock_analyze,
        patch(
            "app.core.adaptive_retriever.adaptive_retriever.select_strategy", new_callable=AsyncMock
        ) as mock_strategy,
        patch(
            "app.core.adaptive_retriever.adaptive_retriever.retrieve_adaptive",
            new_callable=AsyncMock,
        ) as mock_retrieve,
    ):
        from app.core.adaptive_retriever import RetrievalStrategy

        mock_analyze.return_value = QueryAnalysis(
            intent=QueryType.RAG_QA,
            standalone_query="不存在的内容",
        )
        mock_strategy.return_value = RetrievalStrategy.STANDARD
        mock_retrieve.return_value = ([], [])

        events = await _collect_stream(
            doc_ids=["doc-1"],
            query="不存在的内容",
            user_config={"model": "gpt-4o"},
        )
        answer = next(e for e in events if e["type"] == "answer")
        assert "没有找到" in answer["content"]


@pytest.mark.asyncio
async def test_pipeline_stream_enabled_in_chat_service(monkeypatch):
    """chat_service.ask_question_stream should route to pipeline when PIPELINE_V2 is on."""
    from app.services import chat_service

    class FakeUser:
        id = "user-1"

    class FakeDB:
        pass

    with (
        patch.object(chat_service.settings, "pipeline_v2_enabled", True),
        patch.object(
            chat_service, "get_llm_config_with_secret", new_callable=AsyncMock
        ) as mock_cfg,
        patch.object(chat_service, "_validate_document_ids", new_callable=AsyncMock) as mock_valid,
        patch.object(chat_service, "_ensure_session", new_callable=AsyncMock) as mock_sess,
        patch.object(chat_service, "_get_history", new_callable=AsyncMock) as mock_hist,
        patch.object(chat_service, "_embed_text", new_callable=AsyncMock) as mock_emb,
        patch.object(chat_service, "_insert_message", new_callable=AsyncMock) as mock_ins,
        patch.object(chat_service, "execute_chat_pipeline_stream") as mock_pipe,
    ):
        mock_cfg.return_value = {"model": "gpt-4o"}
        mock_valid.return_value = ["doc-1"]
        mock_sess.return_value = ("sess-1", None)
        mock_hist.return_value = []
        mock_emb.return_value = None

        async def fake_pipe(**kwargs):
            yield {"type": "token", "content": "来自管线"}
            yield {"type": "done"}

        mock_pipe.side_effect = lambda **kwargs: fake_pipe(**kwargs)

        events = []
        async for ev in chat_service.ask_question_stream(FakeDB(), FakeUser(), "你好", ["doc-1"]):
            events.append(ev)

        assert mock_pipe.call_count == 1
        assert any(e["type"] == "session" for e in events)
        assert any(e["type"] == "token" and e["content"] == "来自管线" for e in events)
        assert events[-1]["type"] == "done"
        assert mock_ins.await_count >= 1  # user message persisted
