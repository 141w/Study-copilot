"""阶段一：检索参数在线调节（默认=旧行为）。"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import User
from app.services import config_service


def test_normalize_defaults_match_legacy():
    cfg = config_service.normalize_retrieval_config(None)
    assert cfg == config_service.DEFAULT_RETRIEVAL_CONFIG
    assert cfg["rrf_k"] == 60
    assert cfg["rrf_vector_weight"] == 1.0  # 等权求和 = 旧 SQL
    assert cfg["embedding_top_k"] == 5


def test_normalize_clamps_out_of_range():
    cfg = config_service.normalize_retrieval_config(
        {
            "embedding_top_k": 999,
            "rerank_top_k": 0,
            "rrf_k": 0,
            "vector_threshold": 5,
            "rrf_vector_weight": -1,
            "rrf_keyword_weight": 2,
        }
    )
    assert cfg["embedding_top_k"] == 50
    assert cfg["rerank_top_k"] == 1
    assert cfg["rrf_k"] == 1
    assert cfg["vector_threshold"] == 1.0
    assert cfg["rrf_vector_weight"] == 0.1  # 下限，避免双零权重导致检索恒空
    assert cfg["rrf_keyword_weight"] == 1.0


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(id="ret-user", username="retuser", email="r@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.mark.asyncio
async def test_update_and_get_retrieval_config(db_session, user):
    got = await config_service.get_retrieval_config(db_session, user)
    assert got["embedding_top_k"] == 5

    updated = await config_service.update_retrieval_config(
        db_session, user, {"embedding_top_k": 12, "rrf_k": 80}
    )
    assert updated["embedding_top_k"] == 12
    assert updated["rrf_k"] == 80

    again = await config_service.get_retrieval_config(db_session, user)
    assert again["embedding_top_k"] == 12
    assert again["rrf_k"] == 80


@pytest.mark.asyncio
async def test_search_accepts_retrieval_kwargs():
    """search() 签名接受 rrf_k / 权重（回归：默认调用不炸）。"""
    import inspect

    from app.core.pgvector_store import PgVectorStore

    sig = inspect.signature(PgVectorStore.search)
    assert "rrf_k" in sig.parameters
    assert "vector_weight" in sig.parameters
    assert "keyword_weight" in sig.parameters


def test_settings_has_no_hard_dependency_on_new_env():
    # 阶段一不新增环境变量；检索参数走用户配置
    assert not hasattr(settings, "retrieval_top_k") or settings.retrieval_top_k is not None


@pytest.mark.asyncio
async def test_main_path_forwards_retrieval_config_to_store():
    """High 修复回归：主问答路径（adaptive STANDARD）必须把用户检索参数传到 store.search。"""
    from unittest.mock import AsyncMock, patch

    from app.core.adaptive_retriever import RetrievalStrategy, adaptive_retriever
    from app.core.rag_engine import RAGEngine

    engine = RAGEngine()
    engine._reranker = None
    engine._reranker_loaded = True

    mock_store = AsyncMock()
    mock_store.search.return_value = [
        {
            "chunk": {
                "id": "c1",
                "text": "t",
                "page": "",
                "source": "s",
                "document_id": "d1",
                "metadata": {},
            },
            "relevance": 0.9,
            "retrieval_type": "pgvector_hybrid",
        }
    ]
    engine._pg_vector_store = mock_store

    user_config = {
        "retrieval": {
            "embedding_top_k": 20,
            "rrf_k": 90,
            "rrf_vector_weight": 0.8,
            "rrf_keyword_weight": 0.2,
            "rerank_top_k": 20,
            "vector_threshold": 0.0,
        }
    }
    await adaptive_retriever.retrieve_adaptive(
        ["doc1"], "q", RetrievalStrategy.STANDARD, engine, user_config
    )

    mock_store.search.assert_called_once()
    args, kwargs = mock_store.search.call_args
    # embedding_top_k=20 → 候选池 40
    assert args[2] == 40
    assert kwargs.get("rrf_k") == 90
    assert kwargs.get("vector_weight") == 0.8
    assert kwargs.get("keyword_weight") == 0.2


@pytest.mark.asyncio
async def test_bulk_top_k_not_shrunk_by_user_config():
    """总结类 top_k=100 不得被 embedding_top_k=5 截断。"""
    from unittest.mock import AsyncMock

    from app.core.rag_engine import RAGEngine

    engine = RAGEngine()
    engine._reranker = None
    engine._reranker_loaded = True
    mock_store = AsyncMock()
    mock_store.search.return_value = []
    engine._pg_vector_store = mock_store

    await engine.retrieve(
        ["d"], "总结", top_k=100, retrieval_config={"embedding_top_k": 5}
    )
    args, _ = mock_store.search.call_args
    assert args[2] == 200  # 100 * 2，未被 5 覆盖
