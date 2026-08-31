"""Tests for app.core.rag_engine module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.rag_engine import RAGEngine, extract_source_indices

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_retrieved(n=3):
    """Build fake retrieval results compatible with PgVectorStore output."""
    results = []
    for i in range(n):
        results.append(
            {
                "chunk": {
                    "text": f"chunk text {i}" * 20,
                    "page": i + 1,
                    "source": "doc.pdf",
                    "document_id": "doc1",
                },
                "relevance": max(0.0, 1.0 - i * 0.1),  # batch-normalized relevance
                "retrieval_type": "pgvector_hybrid",
            }
        )
    return results


# ── extract_source_indices ───────────────────────────────────────────────────


class TestExtractSourceIndices:
    def test_single_index(self):
        assert extract_source_indices("根据[来源1]的内容") == [1]

    def test_multiple_indices(self):
        assert extract_source_indices("参考[来源2]和[来源1]以及[来源3]") == [1, 2, 3]

    def test_duplicate_indices(self):
        assert extract_source_indices("[来源1][来源1]") == [1]

    def test_no_indices(self):
        assert extract_source_indices("没有引用来源") == []

    def test_mixed_text(self):
        assert extract_source_indices("答案在[来源5]中，详见[来源2]") == [2, 5]

    def test_large_index_numbers(self):
        assert extract_source_indices("见[来源100]") == [100]

    def test_malformed_brackets(self):
        assert extract_source_indices("[来源]") == []

    def test_partial_match(self):
        """Only [来源N] pattern should match, not partial."""
        assert extract_source_indices("来源1 [来源2]") == [2]


# ── RAGEngine unit tests ─────────────────────────────────────────────────────


class TestRAGEngine:
    @pytest.fixture
    def engine(self):
        engine = RAGEngine()
        # Disable the real CrossEncoder reranker so tests never load the model
        engine._reranker = None
        engine._reranker_loaded = True
        return engine

    # deduplicate_results
    def test_deduplicate_empty(self, engine):
        assert engine.deduplicate_results([]) == []

    def test_deduplicate_no_dupes(self, engine):
        results = [
            {"chunk": {"text": "aaa"}, "distance": 0.1},
            {"chunk": {"text": "bbb"}, "distance": 0.2},
        ]
        assert len(engine.deduplicate_results(results)) == 2

    def test_deduplicate_keeps_lower_distance(self, engine):
        text = "x" * 150
        results = [
            {"chunk": {"text": text}, "distance": 0.5},
            {"chunk": {"text": text}, "distance": 0.1},
        ]
        deduped = engine.deduplicate_results(results)
        assert len(deduped) == 1
        assert deduped[0]["distance"] == 0.1

    def test_deduplicate_empty_text(self, engine):
        results = [{"chunk": {"text": ""}, "distance": 0.1}]
        assert len(engine.deduplicate_results(results)) == 1

    def test_deduplicate_three_dupes_keeps_best(self, engine):
        text = "y" * 120
        results = [
            {"chunk": {"text": text}, "distance": 0.5},
            {"chunk": {"text": text}, "distance": 0.1},
            {"chunk": {"text": text}, "distance": 0.3},
        ]
        deduped = engine.deduplicate_results(results)
        assert len(deduped) == 1
        assert deduped[0]["distance"] == 0.1

    def test_deduplicate_preserves_order(self, engine):
        results = [
            {"chunk": {"text": "unique_a"}, "distance": 0.1},
            {"chunk": {"text": "unique_b"}, "distance": 0.2},
            {"chunk": {"text": "unique_c"}, "distance": 0.3},
        ]
        deduped = engine.deduplicate_results(results)
        assert [r["chunk"]["text"] for r in deduped] == ["unique_a", "unique_b", "unique_c"]

    # build_context
    def test_build_context_basic(self, engine):
        chunks = _make_retrieved(2)
        ctx = engine.build_context(chunks)
        assert "chunk text 0" in ctx
        assert "chunk text 1" in ctx
        assert '<source index="1"' in ctx

    def test_build_context_with_page(self, engine):
        chunks = [{"chunk": {"text": "hello", "page": 3, "source": "a.pdf"}}]
        ctx = engine.build_context(chunks)
        assert 'page="3"' in ctx
        assert 'file="a.pdf"' in ctx

    def test_build_context_truncation(self, engine):
        # Create huge chunks that exceed token budget
        huge = [{"chunk": {"text": "x" * 20000, "page": 1}} for _ in range(10)]
        ctx = engine.build_context(huge, max_context_tokens=100)
        # Should have truncated some chunks
        assert len(ctx) < sum(len(c["chunk"]["text"]) for c in huge)

    def test_build_context_empty_chunks(self, engine):
        ctx = engine.build_context([])
        assert ctx == ""

    def test_build_context_no_page_no_source(self, engine):
        chunks = [{"chunk": {"text": "content"}}]
        ctx = engine.build_context(chunks)
        assert '<source index="1">' in ctx
        assert "page=" not in ctx
        assert "file=" not in ctx

    def test_build_context_all_attributes(self, engine):
        chunks = [{"chunk": {"text": "text", "page": 5, "source": "file.pdf"}}]
        ctx = engine.build_context(chunks)
        assert 'index="1"' in ctx
        assert 'page="5"' in ctx
        assert 'file="file.pdf"' in ctx

    def test_build_context_truncates_to_budget(self, engine):
        # Create chunks that just barely exceed budget
        big_text = "a" * 6000  # ~3000 tokens
        chunks = [
            {"chunk": {"text": big_text, "page": 1}},
            {"chunk": {"text": big_text, "page": 2}},
        ]
        ctx = engine.build_context(chunks, max_context_tokens=2500)
        # Should have dropped at least one chunk
        assert 'index="2"' not in ctx

    # build_sources_text
    def test_build_sources_text(self, engine):
        chunks = _make_retrieved(2)
        text = engine.build_sources_text(chunks)
        assert "来源1" in text
        assert "来源2" in text
        assert "doc.pdf" in text

    def test_build_sources_text_limits_to_10(self, engine):
        chunks = _make_retrieved(15)
        text = engine.build_sources_text(chunks)
        # Should only include first 10
        assert "来源10" in text
        assert "来源11" not in text

    def test_build_sources_text_preview_truncation(self, engine):
        long_text = "a" * 200
        chunks = [{"chunk": {"text": long_text, "page": 1}}]
        text = engine.build_sources_text(chunks)
        assert "..." in text
        assert len(text.split("...")[0].split(": ")[-1]) <= 80

    def test_build_sources_text_empty(self, engine):
        text = engine.build_sources_text([])
        assert text == ""

    def test_build_sources_text_with_page_and_source(self, engine):
        chunks = [{"chunk": {"text": "text", "page": 3, "source": "a.pdf"}}]
        text = engine.build_sources_text(chunks)
        assert "第3页" in text
        assert "a.pdf" in text


# ── RAGEngine async tests with mocks ─────────────────────────────────────────


class TestRAGEngineAsync:
    @pytest.fixture
    def engine(self):
        engine = RAGEngine()
        # Disable the real CrossEncoder reranker so tests never load the model
        engine._reranker = None
        engine._reranker_loaded = True
        return engine

    @pytest.mark.asyncio
    async def test_retrieve_calls_store_search(self, engine):
        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(3)
        engine._pg_vector_store = mock_store

        results = await engine.retrieve(["doc1"], "test query", top_k=3)
        mock_store.search.assert_called_once_with("test query", ["doc1"], 6)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_retrieve_filters_high_distance(self, engine):
        mock_store = AsyncMock()
        # All results above threshold (relevance <= 1e-6)
        mock_store.search.return_value = [
            {"chunk": {"text": f"t{i}"}, "relevance": 1e-7} for i in range(5)
        ]
        engine._pg_vector_store = mock_store
        results = await engine.retrieve(["doc1"], "q", top_k=5)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_retrieve_multiple_docs(self, engine):
        """Retrieve should merge results from multiple documents."""
        mock_store = AsyncMock()
        mock_store.search.return_value = [
            {"chunk": {"text": f"{doc_id}_chunk", "document_id": doc_id}, "relevance": 0.8}
            for doc_id in ["doc1", "doc2"]
        ]
        engine._pg_vector_store = mock_store

        results = await engine.retrieve(["doc1", "doc2"], "query", top_k=5)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_retrieve_sorts_by_relevance(self, engine):
        mock_store = AsyncMock()
        # Use distinct text for each chunk to avoid dedup false-positive
        mock_store.search.return_value = [
            {"chunk": {"text": "content that is definitely far from the query"}, "relevance": 0.2},
            {"chunk": {"text": "content that is near to the query"}, "relevance": 0.9},
        ]
        engine._pg_vector_store = mock_store
        # Disable reranker so sort order is purely by relevance
        engine._reranker = None
        engine._reranker_loaded = True
        results = await engine.retrieve(["doc1"], "q", top_k=5)
        assert results[0]["chunk"]["text"] == "content that is near to the query"

    @pytest.mark.asyncio
    async def test_retrieve_applies_reranker(self, engine):
        """If reranker is available, results should have reranker_score."""
        # Use distinct first-100 chars per chunk to survive dedup,
        # and batch-normalized relevance to survive post-filter.
        mock_store = AsyncMock()
        mock_store.search.return_value = [
            {"chunk": {"text": f"distinct content number {i}" * 5, "document_id": "d"},
             "relevance": 0.9, "retrieval_type": "pgvector_hybrid"}
            for i in range(3)
        ]
        engine._pg_vector_store = mock_store

        mock_reranker = MagicMock()
        mock_reranker.predict.return_value = [0.9, 0.5, 0.1]
        engine._reranker = mock_reranker
        engine._reranker_loaded = True

        results = await engine.retrieve(["doc1"], "query", top_k=3)
        assert all("reranker_score" in r for r in results)
        # Should be sorted by reranker_score descending
        assert results[0]["reranker_score"] >= results[-1]["reranker_score"]

    @pytest.mark.asyncio
    async def test_retrieve_reranker_failure_falls_back(self, engine):
        """If reranker raises, should fall back to original order."""
        # Use distinct chunks to survive dedup with batch-normalized relevance
        mock_store = AsyncMock()
        mock_store.search.return_value = [
            {"chunk": {"text": f"fallback content number {i}" * 5, "document_id": "d"},
             "relevance": 0.8, "retrieval_type": "pgvector_hybrid"}
            for i in range(3)
        ]
        engine._pg_vector_store = mock_store

        mock_reranker = MagicMock()
        mock_reranker.predict.side_effect = RuntimeError("reranker fail")
        engine._reranker = mock_reranker
        engine._reranker_loaded = True

        results = await engine.retrieve(["doc1"], "query", top_k=3)
        # Should still return results (original order after relevance sort)
        assert len(results) == 3

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_generate_answer(self, MockLLM, engine):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "这是答案[来源1]"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        answer = await engine.generate_answer("问题", "上下文", "来源列表")
        assert answer == "这是答案[来源1]"

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_generate_answer_with_config(self, MockLLM, engine):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "答案"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        config = {"api_key": "k", "base_url": "http://b", "model_name": "m", "temperature": 0.5}
        await engine.generate_answer("q", "ctx", llm_config=config)
        MockLLM.from_config.assert_called_with(config)

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_generate_answer_with_max_tokens(self, MockLLM, engine):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "答案"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        config = {"api_key": "k", "base_url": "http://b", "model_name": "m", "max_tokens": 512}
        await engine.generate_answer("q", "ctx", llm_config=config)
        mock_llm.chat.assert_called_once()
        call_kwargs = mock_llm.chat.call_args
        assert call_kwargs[1].get("max_tokens") == 512

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_rewrite_query(self, MockLLM, engine):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "独立的问题"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        history = [
            {"role": "user", "content": "什么是深度学习"},
            {"role": "assistant", "content": "深度学习是..."},
        ]
        result = await engine._rewrite_query("它有什么应用", history)
        assert result == "独立的问题"

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_rewrite_query_fallback(self, MockLLM, engine):
        """When LLM raises, original query is returned."""
        mock_llm = AsyncMock()
        mock_llm.chat.side_effect = RuntimeError("fail")
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        result = await engine._rewrite_query("原始问题", [])
        assert result == "原始问题"

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_rewrite_query_empty_response(self, MockLLM, engine):
        """When LLM returns empty string, original query is returned."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = ""
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        result = await engine._rewrite_query("原始问题", [{"role": "user", "content": "hi"}])
        assert result == "原始问题"

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_rewrite_query_with_config(self, MockLLM, engine):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "rewritten"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        config = {"api_key": "k", "base_url": "http://b", "model_name": "m"}
        await engine._rewrite_query("它是什么", [{"role": "user", "content": "hi"}], config)
        MockLLM.from_config.assert_called_with(config)

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_rewrite_query_truncates_history(self, MockLLM, engine):
        """History should be truncated to last 10 messages."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "rewritten"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        history = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        await engine._rewrite_query("它是什么", history)
        # The prompt should include only last 10 messages
        call_args = mock_llm.chat.call_args[0][0]
        prompt_content = call_args[0]["content"]
        assert "msg10" in prompt_content
        assert "msg0" not in prompt_content

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.embedder")
    @patch("app.core.rag_engine.LLM")
    async def test_ask_no_results(self, MockLLM, mock_embedder, engine):
        mock_store = AsyncMock()
        mock_store.search.return_value = []
        engine._pg_vector_store = mock_store

        result = await engine.ask(["doc1"], "question")
        assert result["context_used"] is False
        assert "没有找到" in result["answer"]

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_with_results(self, MockLLM, engine):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "答案内容[来源1]"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(3)
        engine._pg_vector_store = mock_store

        result = await engine.ask(["doc1"], "question")
        assert result["context_used"] is True
        assert len(result["sources"]) > 0
        assert 1 in result["used_source_indices"]

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_no_source_indices(self, MockLLM, engine):
        """When answer has no source indices, all sources should be in filtered_sources."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "答案没有引用来源"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(3)
        engine._pg_vector_store = mock_store

        result = await engine.ask(["doc1"], "question")
        assert result["used_source_indices"] == []
        assert len(result["filtered_sources"]) == len(result["sources"])

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_filtered_sources_match_indices(self, MockLLM, engine):
        """filtered_sources should only contain sources referenced in the answer."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "见[来源2]"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(3)
        engine._pg_vector_store = mock_store

        result = await engine.ask(["doc1"], "question")
        assert result["used_source_indices"] == [2]
        assert all(s["index"] == 2 for s in result["filtered_sources"])

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_with_llm_config(self, MockLLM, engine):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "答案"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(1)
        engine._pg_vector_store = mock_store

        config = {"api_key": "k", "base_url": "http://b", "model_name": "m"}
        result = await engine.ask(["doc1"], "question", user_config=config)
        assert result["context_used"] is True

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_truncates_long_history(self, MockLLM, engine):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "答案"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(1)
        engine._pg_vector_store = mock_store

        history = [{"role": "user", "content": f"q{i}"} for i in range(20)]
        result = await engine.ask(["doc1"], "question", history=history)
        assert result["context_used"] is True

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_generate_answer_stream(self, MockLLM, engine):
        async def fake_stream(*args, **kwargs):
            yield "你"
            yield "好"

        mock_llm = AsyncMock()
        mock_llm.chat_stream = fake_stream
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        tokens = []
        async for tok in engine.generate_answer_stream("q", "ctx"):
            tokens.append(tok)
        assert tokens == ["你", "好"]

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_generate_answer_stream_with_config(self, MockLLM, engine):
        async def fake_stream(*args, **kwargs):
            yield "token1"

        mock_llm = AsyncMock()
        mock_llm.chat_stream = fake_stream
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        config = {"api_key": "k", "base_url": "http://b", "model_name": "m", "temperature": 0.3}
        tokens = []
        async for tok in engine.generate_answer_stream("q", "ctx", llm_config=config):
            tokens.append(tok)
        assert tokens == ["token1"]
        MockLLM.from_config.assert_called_with(config)

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_stream_no_results(self, MockLLM, engine):
        mock_store = AsyncMock()
        mock_store.search.return_value = []
        engine._pg_vector_store = mock_store

        chunks = []
        async for event in engine.ask_stream(["doc1"], "question"):
            chunks.append(event)
        # Agentic RAG emits thinking events before the answer
        answer_events = [c for c in chunks if c["type"] == "answer"]
        assert len(answer_events) == 1
        assert "没有找到" in answer_events[0]["content"]

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_stream_with_results(self, MockLLM, engine):
        async def fake_stream(*args, **kwargs):
            yield "答"
            yield "案"

        mock_llm = AsyncMock()
        mock_llm.chat_stream = fake_stream
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(2)
        engine._pg_vector_store = mock_store

        events = []
        async for event in engine.ask_stream(["doc1"], "question"):
            events.append(event)

        # Agentic RAG emits thinking events first, then sources, then tokens
        sources_events = [e for e in events if e["type"] == "sources"]
        assert len(sources_events) == 1
        assert "sources" in sources_events[0]
        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) == 2
        assert "".join(e["content"] for e in token_events) == "答案"

    @pytest.mark.asyncio
    def test_pg_vector_store_init(self, engine):
        assert engine._pg_vector_store is None

    def test_ensure_reranker_failure(self, engine):
        """When CrossEncoder can't be imported, reranker should be None."""
        engine._reranker_loaded = False
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            reranker = engine._ensure_reranker()
            assert reranker is None
            assert engine._reranker_loaded is True

    def test_ensure_reranker_caching(self, engine):
        """_ensure_reranker should not re-import on second call."""
        engine._reranker = "mock_reranker"
        engine._reranker_loaded = True
        result = engine._ensure_reranker()
        assert result == "mock_reranker"

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.embedder")
    async def test_ask_switches_embedding_model(self, mock_embedder, engine):
        """When user_config has a different embedding model, reload should be called."""
        mock_embedder.model_name = "old_model"
        mock_embedder.reload_model = MagicMock()

        mock_store = AsyncMock()
        mock_store.search.return_value = []
        engine._pg_vector_store = mock_store

        with patch("app.core.rag_engine.LLM"):
            config = {"embedding_model": "new_model", "embedding_dimension": 512}
            await engine.ask(["doc1"], "q", user_config=config)

        mock_embedder.reload_model.assert_called_once_with("new_model", 512)

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.embedder")
    async def test_ask_no_model_switch_when_same(self, mock_embedder, engine):
        """When user_config embedding model matches current, no reload."""
        mock_embedder.model_name = "same_model"

        mock_store = AsyncMock()
        mock_store.search.return_value = []
        engine._pg_vector_store = mock_store

        with patch("app.core.rag_engine.LLM"):
            config = {"embedding_model": "same_model"}
            await engine.ask(["doc1"], "q", user_config=config)

        mock_embedder.reload_model.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_with_history_triggers_rewrite(self, MockLLM, engine):
        """Query with pronoun + history should be routed through query_router.analyze,
        which performs the context-aware rewrite."""
        from app.core.query_router import QueryAnalysis, QueryType

        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "rewritten query"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(1)
        engine._pg_vector_store = mock_store

        history = [{"role": "user", "content": "what is X"}]
        analysis = QueryAnalysis(QueryType.RAG_QA, "rewritten query")
        with patch(
            "app.core.rag_engine.query_router.analyze", return_value=analysis
        ) as mock_analyze:
            with patch.object(engine, "retrieve", return_value=_make_retrieved(1)):
                await engine.ask(["doc1"], "它是什么", history=history)
                mock_analyze.assert_called_once()
                # history must be forwarded so the router can rewrite
                assert mock_analyze.call_args[0][2] == history

    @pytest.mark.asyncio
    async def test_ask_no_rewrite_without_pronoun(self, engine):
        """Query without pronoun should NOT trigger rewrite."""
        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(1)
        engine._pg_vector_store = mock_store

        # Disable reranker to keep tests deterministic
        engine._reranker = None
        engine._reranker_loaded = True

        with patch.object(engine, "_rewrite_query") as mock_rewrite:
            with patch.object(engine, "retrieve", return_value=_make_retrieved(1)):
                with patch("app.core.rag_engine.LLM") as MockLLM:
                    mock_llm = AsyncMock()
                    mock_llm.chat.return_value = "answer"
                    MockLLM.return_value = mock_llm
                    MockLLM.from_config.return_value = mock_llm
                    await engine.ask(
                        ["doc1"], "什么是机器学习", history=[{"role": "user", "content": "hi"}]
                    )
                    mock_rewrite.assert_not_called()

    def test_engine_default_top_k(self, engine):
        """Default top_k should come from settings."""
        assert engine.top_k == 5

    def test_engine_vector_store_cache_init(self, engine):
        assert engine._pg_vector_store is None

    def test_engine_reranker_init(self):
        # Use a pristine engine (the fixture disables the reranker for other tests)
        fresh = RAGEngine()
        assert fresh._reranker is None
        assert fresh._reranker_loaded is False


# ── Extended RAGEngine tests ─────────────────────────────────────────────────


class TestRAGEngineExtended:
    """Additional comprehensive tests for RAGEngine."""

    @pytest.fixture
    def engine(self):
        engine = RAGEngine()
        # Disable the real CrossEncoder reranker so tests never load the model
        engine._reranker = None
        engine._reranker_loaded = True
        return engine

    # build_context edge cases
    def test_build_context_single_chunk(self, engine):
        chunks = [{"chunk": {"text": "only one chunk", "page": 1, "source": "a.pdf"}}]
        ctx = engine.build_context(chunks)
        assert "only one chunk" in ctx
        assert '<source index="1"' in ctx

    def test_build_context_preserves_order(self, engine):
        """Chunks should appear in the same order as input."""
        chunks = [
            {"chunk": {"text": "first", "page": 1}},
            {"chunk": {"text": "second", "page": 2}},
            {"chunk": {"text": "third", "page": 3}},
        ]
        ctx = engine.build_context(chunks)
        pos_first = ctx.index("first")
        pos_second = ctx.index("second")
        pos_third = ctx.index("third")
        assert pos_first < pos_second < pos_third

    def test_build_context_with_page_zero(self, engine):
        """Page 0 should still be included."""
        chunks = [{"chunk": {"text": "content", "page": 0}}]
        ctx = engine.build_context(chunks)
        assert 'page="0"' in ctx

    # build_sources_text edge cases
    def test_build_sources_text_no_page_no_source(self, engine):
        chunks = [{"chunk": {"text": "text only"}}]
        text = engine.build_sources_text(chunks)
        assert "来源1" in text
        assert "第" not in text

    def test_build_sources_text_long_preview(self, engine):
        """Preview should be capped at 80 chars."""
        chunks = [{"chunk": {"text": "a" * 200, "page": 1}}]
        text = engine.build_sources_text(chunks)
        # Find the preview part after ": "
        preview = text.split(": ", 1)[-1]
        assert len(preview) <= 84  # 80 chars + "..."

    # deduplicate edge cases
    def test_deduplicate_short_text_no_dedup(self, engine):
        """Text shorter than 100 chars uses full text as prefix, should still deduplicate."""
        text = "short"
        results = [
            {"chunk": {"text": text}, "distance": 0.5},
            {"chunk": {"text": text}, "distance": 0.1},
        ]
        deduped = engine.deduplicate_results(results)
        assert len(deduped) == 1
        assert deduped[0]["distance"] == 0.1

    def test_deduplicate_different_first_100_chars(self, engine):
        """Chunks with different first 100 chars should NOT be deduplicated."""
        text_a = "a" * 50 + "x" * 50
        text_b = "b" * 50 + "x" * 50
        results = [
            {"chunk": {"text": text_a}, "distance": 0.1},
            {"chunk": {"text": text_b}, "distance": 0.2},
        ]
        deduped = engine.deduplicate_results(results)
        assert len(deduped) == 2

    # retrieve edge cases
    @pytest.mark.asyncio
    async def test_retrieve_empty_doc_ids(self, engine):
        """Empty doc_ids should return empty results."""
        results = await engine.retrieve([], "query", top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_retrieve_top_k_limits_results(self, engine):
        """Results should be limited to top_k after reranking."""
        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(10)
        engine._pg_vector_store = mock_store

        results = await engine.retrieve(["doc1"], "query", top_k=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_retrieve_overfetches_for_reranker(self, engine):
        """Retrieve should request fetch_k = top_k * 2 from stores."""
        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(2)
        engine._pg_vector_store = mock_store

        await engine.retrieve(["doc1"], "query", top_k=5)
        # Should call search(query, doc_ids, top_k * 2=10)
        call_args = mock_store.search.call_args
        assert call_args[0][2] == 10  # fetch_k = 5 * 2 (3rd positional arg)

    # generate_answer edge cases
    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_generate_answer_no_config(self, MockLLM, engine):
        """Default config should use LLM() with no args."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "回答"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        answer = await engine.generate_answer("问题", "上下文")
        assert answer == "回答"
        MockLLM.from_config.assert_called_with(None)

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_generate_answer_with_history(self, MockLLM, engine):
        """History should be passed to LLM chat."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "answer"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        history = [{"role": "user", "content": "prev question"}]
        await engine.generate_answer("q", "ctx", history=history)
        call_args = mock_llm.chat.call_args[0][0]
        # Messages should include system + user
        assert call_args[0]["role"] == "system"
        assert call_args[1]["role"] == "user"

    # ask_stream edge cases
    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_stream_sources_event_format(self, MockLLM, engine):
        """Sources event should have proper structure."""

        async def fake_stream(*args, **kwargs):
            yield "ok"

        mock_llm = AsyncMock()
        mock_llm.chat_stream = fake_stream
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = _make_retrieved(2)
        engine._pg_vector_store = mock_store

        events = []
        async for event in engine.ask_stream(["doc1"], "q"):
            events.append(event)

        sources_events = [e for e in events if e["type"] == "sources"]
        assert len(sources_events) == 1
        sources_event = sources_events[0]
        assert "sources" in sources_event
        assert "filtered_sources" in sources_event
        for s in sources_event["sources"]:
            assert "index" in s
            assert "text" in s
            assert "relevance_score" in s

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_stream_page_to_string(self, MockLLM, engine):
        """Non-string page values should be converted to string in ask_stream."""

        async def fake_stream(*args, **kwargs):
            yield "ok"

        mock_llm = AsyncMock()
        mock_llm.chat_stream = fake_stream
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = [
            {
                "chunk": {"text": "t", "page": 5, "source": "a.pdf", "document_id": "d1"},
                "relevance": 0.8,
                "retrieval_type": "pgvector_hybrid",
            }
        ]
        engine._pg_vector_store = mock_store

        events = []
        async for event in engine.ask_stream(["doc1"], "q"):
            events.append(event)

        sources_events = [e for e in events if e["type"] == "sources"]
        sources = sources_events[0]["sources"]
        assert isinstance(sources[0]["page"], str)

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.embedder")
    async def test_ask_stream_embedding_model_switch(self, mock_embedder, engine):
        """ask_stream should reload embedding model if config differs."""
        mock_embedder.model_name = "old_model"
        mock_embedder.reload_model = MagicMock()

        mock_store = AsyncMock()
        mock_store.search.return_value = []
        engine._pg_vector_store = mock_store

        config = {"embedding_model": "new_model", "embedding_dimension": 512}
        with patch("app.core.rag_engine.LLM"):
            async for _ in engine.ask_stream(["doc1"], "q", user_config=config):
                pass

        mock_embedder.reload_model.assert_called_once_with("new_model", 512)

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_page_to_string(self, MockLLM, engine):
        """Non-string page values in ask() should be converted to string."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "answer"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = [
            {
                "chunk": {"text": "t", "page": 3, "source": "a.pdf", "document_id": "d1"},
                "relevance": 0.8,
                "retrieval_type": "pgvector_hybrid",
            }
        ]
        engine._pg_vector_store = mock_store

        result = await engine.ask(["doc1"], "q")
        assert isinstance(result["sources"][0]["page"], str)
        assert result["sources"][0]["page"] == "3"

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_page_none_not_crash(self, MockLLM, engine):
        """None page should be handled gracefully."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "answer"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = [
            {
                "chunk": {"text": "t", "page": None, "source": "a.pdf", "document_id": "d1"},
                "relevance": 0.8,
                "retrieval_type": "pgvector_hybrid",
            }
        ]
        engine._pg_vector_store = mock_store

        result = await engine.ask(["doc1"], "q")
        assert result["sources"][0]["page"] == ""

    @pytest.mark.asyncio
    @patch("app.core.rag_engine.LLM")
    async def test_ask_relevance_score_calculation(self, MockLLM, engine):
        """relevance_score should be the batch-normalized relevance from search."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "answer"
        MockLLM.return_value = mock_llm
        MockLLM.from_config.return_value = mock_llm

        mock_store = AsyncMock()
        mock_store.search.return_value = [
            {"chunk": {"text": "t", "page": 1, "source": "s", "document_id": "d"},
             "relevance": 0.667, "retrieval_type": "pgvector_hybrid"}
        ]
        engine._pg_vector_store = mock_store

        result = await engine.ask(["doc1"], "q")
        score = result["sources"][0]["relevance_score"]
        assert abs(score - 0.667) < 0.001
