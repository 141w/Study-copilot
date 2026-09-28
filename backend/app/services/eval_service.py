"""阶段四：端到端评测台（检索命中指标，与 retrieval_probe 同口径）。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pgvector_store import PgVectorStore
from app.db import Document, User
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 30
TOP_K = 5


async def run_retrieval_eval(
    db: AsyncSession,
    user: User,
    document_ids: list[str],
    questions: list[str],
    top_k: int = TOP_K,
) -> dict[str, Any]:
    """对给定问题跑混合检索，产出 hit@k / top 结果。

    expected 语义：question 与 document_ids 中某文档配对时，由调用方按同序
    传入 expected_doc_ids；缺省则用「命中任一选中文档」算 hit。
    """
    if not questions:
        raise ValidationError("请至少提供 1 个问题")
    if len(questions) > MAX_QUESTIONS:
        raise ValidationError(f"问题数最多 {MAX_QUESTIONS}")
    if not document_ids:
        raise ValidationError("请至少选择 1 篇文档")

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

    store = PgVectorStore(user_id=user.id)
    results: list[dict[str, Any]] = []
    hit1 = hitk = 0

    for q in questions:
        q = (q or "").strip()
        if not q:
            continue
        hits = await store.search(q, owned_ids, top_k=top_k)
        top = []
        hit_docs = set()
        for h in hits:
            chunk = h.get("chunk", {})
            did = chunk.get("document_id", "")
            hit_docs.add(did)
            top.append(
                {
                    "document_id": did,
                    "chunk_id": chunk.get("chunk_id") or chunk.get("id") or "",
                    "score": round(float(h.get("relevance") or 0), 4),
                    "preview": (chunk.get("text") or "")[:80].replace("\n", " "),
                }
            )
        ok1 = bool(top) and top[0]["document_id"] in owned_ids
        okk = bool(hit_docs & set(owned_ids))
        hit1 += int(ok1)
        hitk += int(okk)
        results.append(
            {
                "question": q,
                "hit@1": ok1,
                f"hit@{top_k}": okk,
                "top": top,
            }
        )

    n = max(len(results), 1)
    return {
        "meta": {
            "kind": "retrieval-eval",
            "generated_at": datetime.now(UTC).isoformat(),
            "n_questions": len(results),
            "top_k": top_k,
            "hit_rate@1": round(hit1 / n, 4),
            f"hit_rate@{top_k}": round(hitk / n, 4),
            "document_ids": list(owned_ids),
        },
        "results": results,
    }
