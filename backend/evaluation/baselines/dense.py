"""纯向量基线：app embedder（text2vec-base-chinese）+ numpy cosine。

与自研 hybrid 方案共享同一 embedding 模型，用于量化「纯语义通道」
与「混合通道」的差距。语料 embedding 批量计算（64 条一批）。
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from evaluation.datasets.base import EvalDataset

_BATCH = 64


BGE_ZH_SMALL = "BAAI/bge-small-zh-v1.5"
BGE_ZH_BASE = "BAAI/bge-base-zh-v1.5"
BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

BGE_M3 = "BAAI/bge-m3"  # 无 instruction；dense/sparse/colbert 多粒度模型，此处只评 dense 通道
QWEN3_EMBEDDING = "Qwen/Qwen3-Embedding-0.6B"
# Qwen3 检索协议：query 侧加指令前缀，语料侧不加
QWEN3_INSTRUCTION_TMPL = "Instruct: 给定任务，检索满足该任务需求的段落\nQuery: {query}"


async def retrieve_dense_model(
    ds: EvalDataset,
    queries: Mapping[str, str],
    top_k: int,
    model_name: str,
    query_instruction: str | None = None,
    query_format: str | None = None,
) -> dict[str, list[str]]:
    """指定任意 sentence-transformers 模型的纯向量基线（embedding 横评专用）。

    与 app embedder 解耦，用于同数据集同口径对比不同 embedding 模型。
    BGE 系模型按检索协议给 query 加指令前缀、语料不加。

    Args:
        model_name: HF 模型 ID（如 BAAI/bge-small-zh-v1.5）。
        query_instruction: query 前缀（None 表示不加）。
        query_format: 完整指令模板（含 {query} 占位符），优先于
            query_instruction——用于 Qwen3 这类 "Instruct: ...\\nQuery: ..."
            协议模型（模板整体替换 query，而非简单拼接前缀）。
    """
    import os

    import numpy as np
    from sentence_transformers import SentenceTransformer

    # 沙箱/无头环境下 macOS MPS 编译服务可能断连（MPSLibrary broken pipe），
    # 评测侧允许显式钉设备：EVAL_TORCH_DEVICE=cpu（不设则 sentence-transformers 自动选）
    device = os.environ.get("EVAL_TORCH_DEVICE") or None
    model = SentenceTransformer(model_name, device=device)
    ids = list(ds.corpus)
    texts = [ds.corpus[cid] for cid in ids]

    embs = []
    for start in range(0, len(texts), _BATCH):
        batch = model.encode(
            texts[start : start + _BATCH], normalize_embeddings=True, show_progress_bar=False
        )
        embs.append(np.asarray(batch, dtype=np.float32))
    mat = np.vstack(embs) if embs else np.zeros((0, 1), dtype=np.float32)

    run: dict[str, list[str]] = {}
    for qid, q in queries.items():
        if query_format:
            qq = query_format.format(query=q)
        else:
            qq = (query_instruction or "") + q
        q_vec = np.asarray(model.encode(qq, normalize_embeddings=True), dtype=np.float32)
        sims = mat @ q_vec
        order = np.argsort(-sims)[:top_k]
        run[qid] = [ids[i] for i in order]
    return run


async def retrieve_dense(
    ds: EvalDataset,
    queries: Mapping[str, str],
    top_k: int,
) -> dict[str, list[str]]:
    """对每个 query 返回 top_k 排名的 chunk id 列表（cosine 相似度降序）。"""
    from app.core.embedder import embedder

    ids = list(ds.corpus)
    texts = [ds.corpus[cid] for cid in ids]

    # 语料 embedding（批量化）
    embs = []
    for start in range(0, len(texts), _BATCH):
        batch = await embedder.embed_texts(texts[start : start + _BATCH])
        embs.append(np.asarray(batch, dtype=np.float32))
    mat = np.vstack(embs) if embs else np.zeros((0, 768), dtype=np.float32)

    # 归一化后点积即 cosine
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat_n = mat / norms

    run: dict[str, list[str]] = {}
    for qid, q in queries.items():
        q_vec = np.asarray(await embedder.embed_query(q), dtype=np.float32)
        q_norm = float(np.linalg.norm(q_vec)) or 1.0
        sims = mat_n @ (q_vec / q_norm)
        order = np.argsort(-sims)[:top_k]
        run[qid] = [ids[i] for i in order]
    return run
