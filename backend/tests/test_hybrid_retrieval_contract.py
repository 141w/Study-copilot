"""混合检索 RRF 融合 + 相关度归一化回归测试。

保障 PgVectorStore 的混合检索结果能通过 rag_engine 的相关性过滤，
以及 result_relevance 助手的回退语义。
"""

import asyncio
from unittest.mock import patch

from app.core.rag_engine import rag_engine
from app.core.vector_store import result_relevance


def _fake_pgvector_result(idx: int, fused: float) -> dict:
    """模拟 PgVectorStore.search() 的输出格式。"""
    best = 0.033
    return {
        "chunk": {"text": f"test content {idx}", "metadata": {}},
        "relevance": fused / best if best > 0 else 0.0,
        "fused_score": fused,
        "retrieval_type": "pgvector_hybrid",
    }


class FakePgVectorStore:
    """只实现 rag_engine.retrieve() 用到的 search() 接口。"""

    async def search(self, query: str, doc_ids: list[str], top_k: int):
        results = [_fake_pgvector_result(0, 0.0164), _fake_pgvector_result(1, 0.0082)]
        return results[:top_k]


def test_pgvector_results_survive_retrieve_filter():
    """PgVectorStore 批内归一结果必须通过 retrieve() 的相关性过滤。"""
    with patch.object(rag_engine, '_get_pg_vector_store') as mock_get:
        mock_get.return_value = FakePgVectorStore()
        got = asyncio.run(rag_engine.retrieve(["fake-doc"], "测试查询", top_k=5))
    # 两个结果的 relevance 经批内归一后均 > 1e-6，不应被误杀
    assert len(got) >= 1, "PgVectorStore 结果被相关性阈值误杀——回归了！"


def test_result_relevance_fallback_semantics():
    """result_relevance：新字段优先 > similarity 回退 > None。"""
    assert result_relevance({"relevance": 0.7}) == 0.7
    assert result_relevance({"similarity": 0.9}) == 0.9
    assert result_relevance({"similarity": 5.0}) == 1.0  # 越界截断
    assert result_relevance({"distance": 0.5}) is None
