"""混合检索 distance 语义回归测试（2026-08-27 真机冒烟发现的致命缺陷）。

缺陷：HybridVectorStore 的 distance = 1 - RRF融合分，而 RRF 分数上限 ≈0.033，
导致 distance 恒 ∈ [0.97, 1)；rag_engine 旧的绝对阈值 `distance <= 0.85`
把 Hybrid 结果全部误杀 → 任何文档的任何提问都返回"没有找到相关内容"。

本测试锁定修复后的契约：
1. 三种 store 的结果都携带统一 [0,1] 的 relevance 字段；
2. rag_engine.retrieve 对纯 Hybrid 形态的结果不再误杀；
3. result_relevance 助手的回退语义。
"""

from app.core.rag_engine import rag_engine
from app.core.vector_store import HybridVectorStore, result_relevance


def _chunk(idx: int, text: str) -> dict:
    return {"text": text, "source": f"d{idx}", "page": 1}


def _hybrid_result(idx: int, fused: float) -> dict:
    """模拟 HybridVectorStore 的原始输出形态（distance 恒高）。"""
    return {
        "chunk": _chunk(idx, f"FAISS 应用场景说明 {idx}"),
        "distance": 1 - fused,
        "fused_score": fused,
        "relevance": None,  # 下面手动设，模拟真实批内归一
        "index": idx,
        "retrieval_type": "hybrid",
    }


class FakeHybridStore:
    """只实现 rag_engine 用到的接口，返回典型 Hybrid 输出。"""

    async def search(self, query: str, top_k: int):
        # 现实场景：RRF 后 fused≈0.0164~0.033 → relevance 批内归一后 top=1.0
        results = [_hybrid_result(0, 0.0164), _hybrid_result(1, 0.0082)]
        best = max(r["fused_score"] for r in results)
        for r in results:
            r["relevance"] = r["fused_score"] / best if best > 0 else 0.0
        return results[:top_k]


def test_hybrid_results_survive_retrieve_filter():
    """纯 Hybrid 形态结果必须能通过 retrieve() 的相关性过滤（原致命缺陷）。"""
    import asyncio

    doc_id = "fake-hybrid-doc"
    rag_engine._vector_store_cache[doc_id] = FakeHybridStore()

    async def run():
        return await rag_engine.retrieve([doc_id], "FAISS 应用场景", top_k=5)

    try:
        got = asyncio.run(run())
    finally:
        rag_engine._vector_store_cache.pop(doc_id, None)

    # 契约核心：不再被误杀。最终顺序可能被可选的 CrossEncoder 重排改变，
    # 因此只断言存活与类型，不断言具体位次。
    assert len(got) >= 1, "Hybrid 结果被距离阈值误杀——回归了！"
    assert got[0]["retrieval_type"] == "hybrid"


def test_result_relevance_fallback_semantics():
    """result_relevance：新字段优先 > similarity 回退 > None。"""
    assert result_relevance({"relevance": 0.7}) == 0.7
    assert result_relevance({"similarity": 0.9}) == 0.9
    assert result_relevance({"similarity": 5.0}) == 1.0  # 越界截断
    assert result_relevance({"distance": 0.5}) is None


def test_hybrid_store_emits_normalized_relevance():
    """真实 HybridVectorStore：批内归一化后 top1 relevance == 1.0。"""
    import asyncio

    store = HybridVectorStore(dimension=8)
    chunks = [
        {"text": "苹果是一种水果", "source": "s"},
        {"text": "FAISS 用于向量检索场景", "source": "s"},
    ]
    # 直接注入子索引数据，绕过嵌入模型（单元级、离线）
    store.chunks = chunks
    store.document_ids = ["d", "d"]

    class FakeInner:
        def __init__(self, order):
            self.order = order

        async def search(self, q, k):
            return [
                {"chunk": chunks[i], "distance": float(j), "index": i}
                for j, i in enumerate(self.order)
            ]

    store._faiss = FakeInner(order=[1, 0])
    store._bm25 = FakeInner(order=[1, 0])  # 同一文档在双列表均居首 → 融合分必更高

    out = asyncio.run(store.search("任意查询", 2))
    rels = [r["relevance"] for r in out]
    assert out[0]["relevance"] == 1.0          # 融合第一名=满相关度
    assert all(0.0 <= r <= 1.0 for r in rels)
    assert rels[0] > rels[1]                    # 排序与融合分一致
