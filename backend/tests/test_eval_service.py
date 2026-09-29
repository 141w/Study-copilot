"""阶段四：评测台 — 校验与指标口径。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, User
from app.exceptions import ValidationError
from app.services import eval_service


def _hit(doc_id: str, chunk_id: str = "c1", text: str = "相关段落") -> dict:
    return {
        "chunk": {
            "id": chunk_id,
            "document_id": doc_id,
            "text": text,
            "page": "1",
            "source": "a.pdf",
            "metadata": {},
        },
        "relevance": 0.9,
    }


class _FakeEngine:
    def __init__(self, hits: list[dict]):
        self._hits = hits
        self.calls: list[tuple] = []

    async def retrieve(self, doc_ids, query, top_k=5, retrieval_config=None):
        self.calls.append((tuple(doc_ids), query, top_k, retrieval_config))
        return list(self._hits)


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(id="ev-user", username="evuser", email="e@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.fixture
async def doc(db_session: AsyncSession, user: User) -> Document:
    d = Document(
        id="ev-doc",
        user_id=user.id,
        filename="a.pdf",
        file_path="/tmp/a.pdf",
        status="ready",
        chunk_count=1,
    )
    db_session.add(d)
    await db_session.commit()
    return d


@pytest.mark.asyncio
async def test_rejects_empty_questions(db_session, user, doc):
    with pytest.raises(ValidationError):
        await eval_service.run_retrieval_eval(db_session, user, [doc.id], [], expected=[])


@pytest.mark.asyncio
async def test_rejects_foreign_docs(db_session, user, doc):
    with pytest.raises(ValidationError):
        await eval_service.run_retrieval_eval(
            db_session, user, ["not-owned"], ["q？"], expected=[["x"]]
        )


@pytest.mark.asyncio
async def test_eval_metrics_and_top(db_session, user, doc):
    fake = _FakeEngine([_hit(doc.id, "c1")])
    with patch("app.core.rag_engine.rag_engine.retrieve", new=fake.retrieve):
        out = await eval_service.run_retrieval_eval(
            db_session, user, [doc.id], ["这题答案在哪？"], expected=[[doc.id]], top_k=5
        )

    assert out["meta"]["n_questions"] == 1
    assert out["meta"]["hit_rate@1"] == 1.0
    assert out["meta"]["hit_rate@5"] == 1.0
    assert out["results"][0]["hit@1"] is True
    assert out["results"][0]["top"][0]["document_id"] == doc.id
    assert out["results"][0]["top"][0]["chunk_id"] == "c1"


@pytest.mark.asyncio
async def test_eval_miss_when_empty_search(db_session, user, doc):
    fake = _FakeEngine([])
    with patch("app.core.rag_engine.rag_engine.retrieve", new=fake.retrieve):
        out = await eval_service.run_retrieval_eval(
            db_session, user, [doc.id], ["没命中？"], expected=[[doc.id]], top_k=5
        )
    assert out["meta"]["hit_rate@1"] == 0.0
    assert out["results"][0]["hit@1"] is False


# ---------------------------------------------------------------------------
# F3 · 指标恒真复现（fix(phase2-audit): F3）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_f3_returns_wrong_doc_scores_zero(db_session, user, doc):
    """检索返回了结果但不是期望文档时，hit@1 必须是 0。

    改前：ok1 = top[0].document_id in owned_ids，而检索已按 owned_ids 收窄
    → 只要返回结果就记命中（恒真）。本用例期望文档是另一个 id。
    """
    other_doc_id = "ev-other-doc"
    d2 = Document(
        id=other_doc_id,
        user_id=user.id,
        filename="b.pdf",
        file_path="/tmp/b.pdf",
        status="ready",
        chunk_count=1,
    )
    db_session.add(d2)
    await db_session.commit()

    fake = _FakeEngine([_hit(other_doc_id, "c-wrong", "无关段落")])
    with patch("app.core.rag_engine.rag_engine.retrieve", new=fake.retrieve):
        out = await eval_service.run_retrieval_eval(
            db_session,
            user,
            [doc.id, other_doc_id],
            ["这题答案在哪？"],
            expected=[[doc.id]],  # 期望命中 doc，实际返回 other
            top_k=5,
        )

    assert out["results"][0]["hit@1"] is False, "返回非期望文档不得计为命中"
    assert out["meta"]["hit_rate@1"] == 0.0
    assert out["meta"]["hit_rate@5"] == 0.0
    assert out["meta"]["recall@5"] == 0.0
    assert out["meta"]["mrr@5"] == 0.0


@pytest.mark.asyncio
async def test_f3_expected_required(db_session, user, doc):
    """缺少期望答案时不得静默出百分比。"""
    with pytest.raises(ValidationError):
        await eval_service.run_retrieval_eval(
            db_session, user, [doc.id], ["q？"], expected=None, top_k=5
        )
    with pytest.raises(ValidationError):
        await eval_service.run_retrieval_eval(
            db_session, user, [doc.id], ["q1", "q2"], expected=[["x"]], top_k=5  # 长度不匹配
        )
    with pytest.raises(ValidationError):
        await eval_service.run_retrieval_eval(
            db_session, user, [doc.id], ["q？"], expected=[[]], top_k=5  # 全空
        )


@pytest.mark.asyncio
async def test_f3_recall_not_inflated_by_duplicate_doc_keys(db_session, user, doc):
    """文档级 key 同文档多切片不得把 Recall 顶到 >1。"""
    hits = [_hit(doc.id, f"c{i}", f"chunk{i}") for i in range(5)]
    fake = _FakeEngine(hits)
    with patch("app.core.rag_engine.rag_engine.retrieve", new=fake.retrieve):
        out = await eval_service.run_retrieval_eval(
            db_session, user, [doc.id], ["q？"], expected=[[doc.id]], top_k=5
        )
    r = out["meta"]["recall@5"]
    assert 0.0 <= r <= 1.0, f"recall@5 越界: {r}"
    assert r == 1.0


@pytest.mark.asyncio
async def test_f3_metrics_match_harness(db_session, user, doc):
    """与 harness.py 指标对拍：返回结果是期望文档时 MRR/Recall 一致。"""
    from evaluation.harness import hit_rate_at_k, mrr_at_k, recall_at_k

    fake = _FakeEngine([_hit(doc.id, "c1")])
    with patch("app.core.rag_engine.rag_engine.retrieve", new=fake.retrieve):
        out = await eval_service.run_retrieval_eval(
            db_session, user, [doc.id], ["q？"], expected=[[doc.id]], top_k=5
        )

    # harness 对拍（文档级 qrels：retrieved=[doc.id], relevant={doc.id})
    assert out["meta"]["hit_rate@1"] == hit_rate_at_k([doc.id], {doc.id}, 1)
    assert out["meta"]["hit_rate@5"] == hit_rate_at_k([doc.id], {doc.id}, 5)
    assert out["meta"]["recall@5"] == recall_at_k([doc.id], {doc.id}, 5)
    assert out["meta"]["mrr@5"] == mrr_at_k([doc.id], {doc.id}, 5)


@pytest.mark.asyncio
async def test_f3_meta_contains_retrieval_fingerprint(db_session, user, doc):
    """报表 meta 必须含生效参数指纹（embedding/top_k/权重/FTS），否则跨次不可比。"""
    fake = _FakeEngine([_hit(doc.id, "c1", "x")])
    with patch("app.core.rag_engine.rag_engine.retrieve", new=fake.retrieve):
        out = await eval_service.run_retrieval_eval(
            db_session, user, [doc.id], ["q？"], expected=[[doc.id]], top_k=5
        )
    meta = out["meta"]
    assert "top_k" in meta
    assert "embedding_model" in meta
    assert "fts_config" in meta
    assert "retrieval_config" in meta


@pytest.mark.asyncio
async def test_f3_empty_expected_row_flags_warning(db_session, user, doc):
    """该题未录入期望时标 warning，不计入百分比分母。"""
    fake = _FakeEngine([_hit(doc.id)])
    with patch("app.core.rag_engine.rag_engine.retrieve", new=fake.retrieve):
        out = await eval_service.run_retrieval_eval(
            db_session, user, [doc.id], ["有期望", "无期望"], expected=[[doc.id], []], top_k=5
        )
    assert out["results"][1].get("warning")
    assert out["results"][1]["hit@1"] is False
    # 只有 1 题参与统计
    assert out["meta"]["hit_rate@1"] == 1.0

