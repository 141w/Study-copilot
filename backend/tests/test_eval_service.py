"""阶段四：评测台 — 校验与指标口径。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, User
from app.exceptions import ValidationError
from app.services import eval_service


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
        await eval_service.run_retrieval_eval(db_session, user, [doc.id], [])


@pytest.mark.asyncio
async def test_rejects_foreign_docs(db_session, user, doc):
    with pytest.raises(ValidationError):
        await eval_service.run_retrieval_eval(db_session, user, ["not-owned"], ["q？"])


@pytest.mark.asyncio
async def test_eval_metrics_and_top(db_session, user, doc):
    fake_hit = {
        "chunk": {
            "id": "c1",
            "document_id": doc.id,
            "text": "相关段落",
            "page": "1",
            "source": "a.pdf",
            "metadata": {},
        },
        "relevance": 0.9,
    }

    class FakeStore:
        async def search(self, q, doc_ids, top_k=5, **kwargs):
            return [fake_hit]

    with patch("app.services.eval_service.PgVectorStore", return_value=FakeStore()):
        out = await eval_service.run_retrieval_eval(
            db_session, user, [doc.id], ["这题答案在哪？"], top_k=5
        )

    assert out["meta"]["n_questions"] == 1
    assert out["meta"]["hit_rate@1"] == 1.0
    assert out["meta"]["hit_rate@5"] == 1.0
    assert out["results"][0]["hit@1"] is True
    assert out["results"][0]["top"][0]["document_id"] == doc.id
    assert out["results"][0]["top"][0]["chunk_id"] == "c1"


@pytest.mark.asyncio
async def test_eval_miss_when_empty_search(db_session, user, doc):
    class EmptyStore:
        async def search(self, q, doc_ids, top_k=5, **kwargs):
            return []

    with patch("app.services.eval_service.PgVectorStore", return_value=EmptyStore()):
        out = await eval_service.run_retrieval_eval(
            db_session, user, [doc.id], ["没命中？"], top_k=5
        )
    assert out["meta"]["hit_rate@1"] == 0.0
    assert out["results"][0]["hit@1"] is False
