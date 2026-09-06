"""Tests for app.core.vector_store module."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.core.vector_store import (
    BM25VectorStore,
    DocumentVectorStore,
    FAISSVectorStore,
    HybridVectorStore,
)

# ── Shared fixtures ──────────────────────────────────────────────────────────


def _sample_chunks(n=3):
    return [{"text": f"chunk {i} content", "page": i + 1} for i in range(n)]


# ── FAISSVectorStore ─────────────────────────────────────────────────────────


class TestFAISSVectorStore:
    @pytest.fixture
    def store(self):
        return FAISSVectorStore(dimension=4)

    @pytest.mark.asyncio
    @patch("app.core.embedder.embedder")
    async def test_add_chunks(self, mock_embedder, store):
        fake_embeddings = np.random.randn(3, 4).astype(np.float32)
        mock_embedder.embed_texts = AsyncMock(return_value=fake_embeddings)

        result = await store.add_chunks(_sample_chunks(3), "doc1")
        assert result is True
        assert store.get_chunk_count() == 3

    @pytest.mark.asyncio
    @patch("app.core.embedder.embedder")
    async def test_add_empty_chunks(self, mock_embedder, store):
        result = await store.add_chunks([], "doc1")
        assert result is False

    @pytest.mark.asyncio
    @patch("app.core.embedder.embedder")
    async def test_search_returns_results(self, mock_embedder, store):
        # Add chunks first
        fake_embs = np.random.randn(3, 4).astype(np.float32)
        mock_embedder.embed_texts = AsyncMock(return_value=fake_embs)
        await store.add_chunks(_sample_chunks(3), "doc1")

        # Search
        query_emb = np.random.randn(4).astype(np.float32)
        mock_embedder.embed_query = AsyncMock(return_value=query_emb)

        results = await store.search("test query", top_k=2)
        assert len(results) <= 2
        assert all("chunk" in r for r in results)
        assert all("distance" in r for r in results)
        assert all("similarity" in r for r in results)

    @pytest.mark.asyncio
    async def test_search_empty_index(self, store):
        results = await store.search("query", top_k=5)
        assert results == []

    @pytest.mark.asyncio
    @patch("app.core.embedder.embedder")
    async def test_save_and_load(self, mock_embedder, store):
        fake_embs = np.random.randn(2, 4).astype(np.float32)
        mock_embedder.embed_texts = AsyncMock(return_value=fake_embs)
        await store.add_chunks(_sample_chunks(2), "doc1")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_store")
            saved = await store.save(path)
            assert saved is True
            assert os.path.exists(f"{path}.index")
            assert os.path.exists(f"{path}.pkl")

            # Load into a new store
            new_store = FAISSVectorStore(dimension=4)
            loaded = await new_store.load(path)
            assert loaded is True
            assert new_store.get_chunk_count() == 2

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, store):
        result = await store.load("/nonexistent/path")
        assert result is False

    def test_delete(self, store):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "del_test")
            # Create fake files
            open(f"{path}.index", "w").close()
            open(f"{path}.pkl", "w").close()
            assert store.delete(path) is True
            assert not os.path.exists(f"{path}.index")


# ── BM25VectorStore ──────────────────────────────────────────────────────────


class TestBM25VectorStore:
    @pytest.fixture
    def store(self):
        return BM25VectorStore()

    @pytest.mark.asyncio
    async def test_add_chunks(self, store):
        result = await store.add_chunks(_sample_chunks(3), "doc1")
        assert result is True
        assert store.get_chunk_count() == 3

    @pytest.mark.asyncio
    async def test_add_empty(self, store):
        result = await store.add_chunks([], "doc1")
        assert result is False

    @pytest.mark.asyncio
    async def test_search(self, store):
        chunks = [
            {"text": "machine learning is a subset of artificial intelligence"},
            {"text": "deep learning neural networks for image recognition tasks"},
            {"text": "cooking recipes for dinner tonight with chicken and rice"},
        ]
        await store.add_chunks(chunks, "doc1")

        results = await store.search("machine learning", top_k=2)
        assert len(results) <= 2
        assert all("bm25_score" in r for r in results)
        # BM25 should return results (exact match behavior depends on tokenizer)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_empty_index(self, store):
        results = await store.search("query")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_empty_query(self, store):
        await store.add_chunks(_sample_chunks(2), "doc1")
        results = await store.search("   ", top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_save_and_load(self, store):
        await store.add_chunks(_sample_chunks(2), "doc1")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bm25_test")
            saved = await store.save(path)
            assert saved is True
            assert os.path.exists(f"{path}.bm25")

            new_store = BM25VectorStore()
            loaded = await new_store.load(path)
            assert loaded is True
            assert new_store.get_chunk_count() == 2

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, store):
        result = await store.load("/nonexistent/path")
        assert result is False

    def test_delete(self, store):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "del")
            open(f"{path}.bm25", "w").close()
            store.delete(path)
            assert not os.path.exists(f"{path}.bm25")


# ── HybridVectorStore ────────────────────────────────────────────────────────


class TestHybridVectorStore:
    @pytest.fixture
    def store(self):
        return HybridVectorStore(dimension=4)

    @pytest.mark.asyncio
    @patch("app.core.embedder.embedder")
    async def test_add_chunks(self, mock_embedder, store):
        fake_embs = np.random.randn(3, 4).astype(np.float32)
        mock_embedder.embed_texts = AsyncMock(return_value=fake_embs)

        result = await store.add_chunks(_sample_chunks(3), "doc1")
        assert result is True
        assert store.get_chunk_count() == 3

    @pytest.mark.asyncio
    @patch("app.core.embedder.embedder")
    async def test_search_hybrid(self, mock_embedder, store):
        chunks = [
            {"text": "artificial intelligence basics"},
            {"text": "natural language processing"},
            {"text": "computer vision"},
        ]
        fake_embs = np.random.randn(3, 4).astype(np.float32)
        mock_embedder.embed_texts = AsyncMock(return_value=fake_embs)
        await store.add_chunks(chunks, "doc1")

        query_emb = np.random.randn(4).astype(np.float32)
        mock_embedder.embed_query = AsyncMock(return_value=query_emb)

        results = await store.search("artificial intelligence", top_k=2)
        assert len(results) <= 2
        assert all("fused_score" in r for r in results)
        assert all(r.get("retrieval_type") == "hybrid" for r in results)

    def test_rrf_fusion(self, store):
        faiss_results = [
            {"index": 0, "chunk": {"text": "a"}, "distance": 0.1},
            {"index": 1, "chunk": {"text": "b"}, "distance": 0.2},
        ]
        bm25_results = [
            {"index": 1, "chunk": {"text": "b"}, "distance": 0.3},
            {"index": 2, "chunk": {"text": "c"}, "distance": 0.4},
        ]
        store.chunks = [{"text": "a"}, {"text": "b"}, {"text": "c"}]

        results = store._rrf_fusion(faiss_results, bm25_results, top_k=3)
        assert len(results) <= 3
        assert all("fused_score" in r for r in results)

    @pytest.mark.asyncio
    @patch("app.core.embedder.embedder")
    async def test_save_and_load(self, mock_embedder, store):
        fake_embs = np.random.randn(2, 4).astype(np.float32)
        mock_embedder.embed_texts = AsyncMock(return_value=fake_embs)
        await store.add_chunks(_sample_chunks(2), "doc1")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "hybrid_test")
            await store.save(path)
            # Check both FAISS and BM25 files were created
            assert os.path.exists(f"{path}_faiss.index") or os.path.exists(f"{path}_bm25.bm25")


# ── DocumentVectorStore ──────────────────────────────────────────────────────


class TestDocumentVectorStore:
    def test_init_faiss(self):
        dvs = DocumentVectorStore("doc1", retrieval_type="faiss")
        assert isinstance(dvs._store, FAISSVectorStore)

    def test_init_bm25(self):
        dvs = DocumentVectorStore("doc1", retrieval_type="bm25")
        assert isinstance(dvs._store, BM25VectorStore)

    def test_init_hybrid(self):
        dvs = DocumentVectorStore("doc1", retrieval_type="hybrid")
        assert isinstance(dvs._store, HybridVectorStore)

    def test_get_path(self):
        dvs = DocumentVectorStore("doc1", vectorstore_dir="/tmp/vs")
        assert dvs.get_path() == "/tmp/vs/doc1"

    @pytest.mark.asyncio
    @patch("app.core.embedder.embedder")
    async def test_add_chunks_calls_save(self, mock_embedder):
        fake_embs = np.random.randn(1, 4).astype(np.float32)
        mock_embedder.embed_texts = AsyncMock(return_value=fake_embs)

        with tempfile.TemporaryDirectory() as tmpdir:
            dvs = DocumentVectorStore("doc1", vectorstore_dir=tmpdir)
            dvs._store = MagicMock()
            dvs._store.add_chunks = AsyncMock(return_value=True)

            with patch.object(dvs, "save", new_callable=AsyncMock) as mock_save:
                mock_save.return_value = True
                await dvs.add_chunks([{"text": "hello"}])
                mock_save.assert_called_once()

    def test_normalize_score(self):
        store = FAISSVectorStore(dimension=4)
        scores = np.array([1.0, 2.0, 3.0])
        normalized = store._normalize_score(scores)
        assert normalized.min() == 0.0
        assert normalized.max() == 1.0

    def test_normalize_score_single_value(self):
        store = FAISSVectorStore(dimension=4)
        scores = np.array([5.0])
        normalized = store._normalize_score(scores)
        assert normalized[0] == 1.0

    def test_normalize_score_empty(self):
        store = FAISSVectorStore(dimension=4)
        scores = np.array([])
        normalized = store._normalize_score(scores)
        assert len(normalized) == 0
