"""2026-08-27 mypy 渐进落地时修复的三个真实缺陷的行为回归测试。

1. QueryRouter.analyze 在有历史但无 LLM 实例时不得崩溃（此前对 None 调 .chat
   抛 AttributeError），应按既有兜底语义返回 RAG_QA + 原查询；
2. /api/quiz/generate 的可选计数显式传 null 时，必须收窄为服务层默认值（3/2），
   而不是把 None 传进 int 形参；
3. 文档上传缺少文件名时返回 422，而非把 None 传入 str 形参。
"""

import io

import pytest
from fastapi import HTTPException, UploadFile

import app.api.document as document_api
import app.api.quiz as quiz_api
import app.services.quiz_service as quiz_service_module
from app.api.auth import get_current_user
from app.core.query_router import QueryAnalysis, QueryRouter, QueryType
from app.db import User
from app.main import app

_FAKE_USER = User(id="u-regress", username="regress", email="r@example.com", password_hash="x")


# ── 1. QueryRouter：无 LLM 时兜底 RAG_QA ──────────────────────────────────


async def test_router_without_llm_falls_back_to_rag_qa():
    router = QueryRouter()
    # 查询必须不命中闲聊/总结关键词（如"讲了什么"），否则在关键词层就短路，
    # 走不到需要 LLM 实例的多轮路径——这正是本次回归要守护的场景
    result = await router.analyze(
        "RAG框架的召回率如何评估？",
        doc_ids=["doc-1"],
        history=[{"role": "user", "content": "上一篇文档是什么？"}],
        llm=None,
    )
    assert isinstance(result, QueryAnalysis)
    assert result.intent == QueryType.RAG_QA
    assert result.standalone_query == "RAG框架的召回率如何评估？"


# ── 2. /api/quiz/generate：null 计数收窄为服务层默认值 ─────────────────────


async def test_quiz_generate_narrows_none_counts_to_defaults(client, monkeypatch):
    captured: dict[str, object] = {}

    async def fake_generate(db, user, document_ids, choice_count, short_answer_count, config=None):
        captured["choice_count"] = choice_count
        captured["short_answer_count"] = short_answer_count
        return []

    monkeypatch.setattr(quiz_service_module, "generate_quizzes", fake_generate)
    monkeypatch.setattr(quiz_api._quiz_limiter, "check", lambda request: True)
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    try:
        resp = await client.post(
            "/api/quiz/generate",
            json={
                "document_ids": ["doc-1"],
                "choice_count": None,
                "short_answer_count": None,
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured["choice_count"] == 3
    assert captured["short_answer_count"] == 2


# ── 3. /api/documents/upload：空文件名返回 422 ────────────────────────────


async def test_upload_without_filename_rejected_with_422(db_session, monkeypatch):
    monkeypatch.setattr(document_api._upload_limiter, "check", lambda request: True)

    upload_file = UploadFile(file=io.BytesIO(b"fake-pdf-bytes"), filename="")
    with pytest.raises(HTTPException) as exc_info:
        await document_api.upload(
            request=None,  # 未用到——限流器已被桩替换
            file=upload_file,
            db=db_session,
            current_user=_FAKE_USER,
        )
    assert exc_info.value.status_code == 422
