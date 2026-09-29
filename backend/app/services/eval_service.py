"""阶段四：端到端评测台（检索命中指标，与 harness.py 同口径）。

F3：判定改为与期望集求交（禁止「检索返回了就算命中」的同义反复）；
指标直接复用 evaluation/harness.py；检索走生产入口 RAGEngine.retrieve。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, User
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 200
TOP_K = 5

# 复用 harness 指标实现，禁止再抄一份
from evaluation.harness import (  # noqa: E402
    hit_rate_at_k,
    mrr_at_k,
    recall_at_k,
)


async def _load_retrieval_fingerprint(retrieval_config: dict[str, Any] | None) -> dict[str, Any]:
    """生效参数指纹（跨次结果可比）。"""
    cfg = dict(retrieval_config or {})
    fts = "unknown"
    try:
        from app.config import settings

        fts = getattr(settings, "fts_config", None) or "simple"
    except Exception:  # noqa: BLE001
        pass
    embedding_model = None
    try:
        from app.config import settings

        embedding_model = getattr(settings, "embedding_model", None)
    except Exception:  # noqa: BLE001
        pass
    return {
        "embedding_model": embedding_model,
        "top_k": cfg.get("embedding_top_k"),
        "rrf_k": cfg.get("rrf_k"),
        "rrf_vector_weight": cfg.get("rrf_vector_weight"),
        "rrf_keyword_weight": cfg.get("rrf_keyword_weight"),
        "vector_threshold": cfg.get("vector_threshold"),
        "rerank_top_k": cfg.get("rerank_top_k"),
        "fts_config": fts,
        "retrieval_config": cfg,
    }


def _score_question(
    ranked_ids: list[str],
    expected_set: set[str],
    top_k: int,
) -> dict[str, Any]:
    """用 harness 指标对单题打分。ranked_ids 为按名次降序的命中键。"""
    return {
        "hit@1": hit_rate_at_k(ranked_ids, expected_set, 1) > 0,
        f"hit@{top_k}": hit_rate_at_k(ranked_ids, expected_set, top_k) > 0,
        "recall@top_k": recall_at_k(ranked_ids, expected_set, top_k),
        "mrr@top_k": mrr_at_k(ranked_ids, expected_set, top_k),
    }


async def run_retrieval_eval(
    db: AsyncSession,
    user: User,
    document_ids: list[str],
    questions: list[str],
    expected: list[list[str]] | None = None,
    top_k: int = TOP_K,
    retrieval_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """对给定问题跑生产检索，产出与期望集求交的 hit@k / Recall@k / MRR。

    Args:
        expected: 与 questions 等长；每题一组期望 document_id 或 chunk_id。
                  缺失时拒绝出百分比（调用方须显式提供）。
    """
    if not questions:
        raise ValidationError("请至少提供 1 个问题")
    if len(questions) > MAX_QUESTIONS:
        raise ValidationError(f"问题数最多 {MAX_QUESTIONS}")
    if not document_ids:
        raise ValidationError("请至少选择 1 篇文档")
    if expected is None:
        raise ValidationError("未录入期望答案，指标不可用于比较")
    if len(expected) != len(questions):
        raise ValidationError("期望答案条数必须与问题数一致")

    # 归属校验
    from sqlalchemy import select as sa_select

    rows = (
        await db.execute(
            sa_select(Document.id).where(
                Document.user_id == user.id,
                Document.id.in_(document_ids),
                Document.deleted_at.is_(None),
            )
        )
    ).all()
    owned_ids = [r[0] for r in rows]
    if not owned_ids:
        raise ValidationError("所选文档不存在或无权限")

    # 生产同一条检索入口（RRF/阈值/去重/rerank 都在 retrieve 里）
    from app.core.rag_engine import rag_engine as engine
    fingerprint = await _load_retrieval_fingerprint(retrieval_config)

    results: list[dict[str, Any]] = []
    hit1 = hitk = 0
    recall_sum = 0.0
    mrr_sum = 0.0
    scored = 0

    for q, exp in zip(questions, expected, strict=True):
        q = (q or "").strip()
        if not q:
            continue
        exp_set = {e.strip() for e in (exp or []) if e and e.strip()}
        if not exp_set:
            results.append(
                {
                    "question": q,
                    "expected": [],
                    "hit@1": False,
                    f"hit@{top_k}": False,
                    f"recall@{top_k}": 0.0,
                    f"mrr@{top_k}": 0.0,
                    "top": [],
                    "warning": "未录入期望答案，指标不可用于比较",
                }
            )
            continue

        hits = await engine.retrieve(
            owned_ids, q, top_k=top_k, retrieval_config=retrieval_config
        )
        top = []
        ranked_ids: list[str] = []
        for h in hits:
            chunk = h.get("chunk", {})
            did = chunk.get("document_id", "")
            cid = chunk.get("chunk_id") or chunk.get("id") or ""
            # 命中键：优先用期望集里出现的那个 id
            key = cid if cid in exp_set else did
            ranked_ids.append(key)
            top.append(
                {
                    "document_id": did,
                    "chunk_id": cid,
                    "score": round(float(h.get("relevance") or h.get("reranker_score") or 0), 4),
                    "preview": (chunk.get("text") or "")[:80].replace("\n", " "),
                }
            )

        row_scores = _score_question(ranked_ids, exp_set, top_k)
        ok1 = row_scores["hit@1"]
        okk = row_scores[f"hit@{top_k}"]
        hit1 += int(ok1)
        hitk += int(okk)
        recall_sum += row_scores["recall@top_k"]
        mrr_sum += row_scores["mrr@top_k"]
        scored += 1
        results.append(
            {
                "question": q,
                "expected": sorted(exp_set),
                "hit@1": ok1,
                f"hit@{top_k}": okk,
                f"recall@{top_k}": round(row_scores["recall@top_k"], 4),
                f"mrr@{top_k}": round(row_scores["mrr@top_k"], 4),
                "top": top,
            }
        )

    n = max(scored, 1)
    meta: dict[str, Any] = {
        "kind": "retrieval-eval",
        "generated_at": datetime.now(UTC).isoformat(),
        "n_questions": len(results),
        "top_k": top_k,
        "hit_rate@1": round(hit1 / n, 4),
        f"hit_rate@{top_k}": round(hitk / n, 4),
        f"recall@{top_k}": round(recall_sum / n, 4),
        f"mrr@{top_k}": round(mrr_sum / n, 4),
        "document_ids": list(owned_ids),
    }
    meta.update(fingerprint)
    return {"meta": meta, "results": results}
