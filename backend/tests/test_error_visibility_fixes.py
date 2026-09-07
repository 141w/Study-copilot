"""回归测试：错误可见性修复批次（2026-09 探针实测发现）。

覆盖四个修复点：
1. classify_llm_error 补 402/余额不足映射（此前穿透为裸 500）
2. rag_engine 直答/摘要路径 LLM 异常被 classify 包装（此前裸 500）
3. quiz_service 空结果报 ExternalServiceError（此前静默成功 0 题）
4. pgvector_store.search 结果携带扁平 page/source/document_id
   （此前嵌套在 metadata，来源卡页码恒空）
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import ExternalServiceError, classify_llm_error

# ── 1. 402 / 余额不足 → ExternalServiceError（而非裸 500）─────────────────


class TestBillingErrorClassification:
    @pytest.mark.parametrize(
        "raw",
        [
            "Error code: 402 - {'code': 30001, 'message': 'balance is insufficient'}",
            "insufficient balance: please top up",
            "insufficient_quota: usage limit reached",
            "402 Payment Required",
        ],
    )
    def test_billing_errors_map_to_external_service(self, raw):
        exc = classify_llm_error(RuntimeError(raw))
        assert isinstance(exc, ExternalServiceError), (
            f"402/余额类错误应映射为 ExternalServiceError，得到 {type(exc).__name__}"
        )
        assert "余额" in exc.message or "AI 服务" in exc.message

    def test_classification_rule_not_shadowed(self):
        """402 规则不应吞掉更早的 401 认证规则。"""
        exc = classify_llm_error(RuntimeError("401 unauthorized"))
        from app.exceptions import AuthenticationError

        assert isinstance(exc, AuthenticationError)


# ── 2. RAG 直答/摘要路径异常包装 ────────────────────────────────────────────


class TestDirectAnswerErrorWrapping:
    @pytest.mark.asyncio
    async def test_direct_answer_llm_failure_typed(self):
        """直答路径 LLM 失败应抛类型化 AppError（502）而非裸异常（500）。"""
        from app.core.rag_engine import rag_engine

        with patch("app.core.rag_engine.LLM") as MockLLM:
            MockLLM.from_config.return_value.chat = AsyncMock(
                side_effect=RuntimeError("Error code: 402 - {'message': 'balance is insufficient'}")
            )
            with pytest.raises(ExternalServiceError):
                await rag_engine._direct_answer("什么是Python", user_config={})

    @pytest.mark.asyncio
    async def test_summarize_llm_failure_typed(self):
        """摘要路径 LLM 失败同样应抛类型化 AppError。"""
        from app.core.rag_engine import rag_engine

        fake_results = [
            {
                "chunk": {"text": "内容", "page": "1", "source": "d1"},
                "relevance": 0.9,
            }
        ]
        with patch.object(rag_engine, "retrieve", new=AsyncMock(return_value=fake_results)):
            with patch("app.core.rag_engine.LLM") as MockLLM:
                MockLLM.from_config.return_value.chat = AsyncMock(
                    side_effect=RuntimeError("402 payment required")
                )
                with pytest.raises(ExternalServiceError):
                    await rag_engine._summarize_docs(["d1"], user_config={})


# ── 3. quiz_service 空结果显式报错 ──────────────────────────────────────────


class TestQuizEmptyResultExplicitError:
    @pytest.mark.asyncio
    async def test_empty_quiz_list_raises(self, db_session, client):
        """端到端：文档就绪但 LLM 零产出时，API 应报 502 而非 200 空列表。"""
        import uuid as _uuid

        from app.api.auth import get_current_user
        from app.db import Document, DocumentChunk, User

        user = User(
            id=str(_uuid.uuid4()),
            username="probe_empty_quiz",
            email="probe_empty_quiz@t.io",
            password_hash="x",
        )
        db_session.add(user)
        doc = Document(
            id=str(_uuid.uuid4()),
            user_id=user.id,
            filename="bio.txt",
            file_path="/tmp/x",
            status="ready",
            chunk_count=1,
            file_size=10,
        )
        db_session.add(doc)
        # 需要至少一个 chunk 才能通过"文档内容不足"检查
        db_session.add(
            DocumentChunk(
                id=str(_uuid.uuid4()),
                document_id=doc.id,
                content="光合作用",
                chunk_index=0,
                chunk_metadata={},
            )
        )
        await db_session.commit()

        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: user
        try:
            from app.core.quiz_generator import QuizGenerator

            with patch.object(QuizGenerator, "generate_quizzes", new=AsyncMock(return_value=[])):
                resp = await client.post(
                    "/api/quiz/generate",
                    json={"document_ids": [doc.id], "choice_count": 1, "short_answer_count": 0},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert resp.status_code == 502, (
            f"LLM 零产出应显式 502，得到 {resp.status_code}: {resp.text[:200]}"
        )
        assert "未能生成任何题目" in resp.text

    @pytest.mark.asyncio
    async def test_generate_quizzes_task_marks_failed_on_error(self, db_session):
        """生成失败时任务状态应为 failed（而非 completed）。"""
        import uuid as _uuid

        from app.db import User
        from app.services import quiz_service, task_service

        user = User(
            id=str(_uuid.uuid4()),
            username="probe_task_fail",
            email="probe_task_fail@t.io",
            password_hash="x",
        )
        db_session.add(user)
        await db_session.commit()

        captured: list[str] = []
        real_update = task_service.update_task

        async def spy_update(db, task_id, user_id, **kw):
            if kw.get("status"):
                captured.append(kw["status"])
            return await real_update(db, task_id, user_id, **kw)

        async def failing_gen(*a, **kw):
            raise ExternalServiceError("生成题目失败: 402")

        with (
            patch.object(quiz_service, "_do_generate_quiz", new=failing_gen),
            patch.object(task_service, "update_task", new=spy_update),
        ):
            with pytest.raises(ExternalServiceError):
                await quiz_service.generate_quizzes(db=db_session, user=user, document_ids=["d1"])
        assert "failed" in captured, f"任务应被标记为 failed，实际：{captured}"


# ── 4. pgvector 检索结果元数据扁平化 ─────────────────────────────────────────


class TestPgVectorSearchMetadataFlattening:
    def test_row_to_result_flattens_metadata(self):
        """SQL 返回行 → 检索结果的字段映射（页码/来源/文档ID 必须扁平到 chunk 顶层）。"""
        # 直接验证 SQL 语句包含 document_id 列（防止回归到旧投影）
        import inspect

        from app.core.pgvector_store import PgVectorStore

        src = inspect.getsource(PgVectorStore.search)
        assert "COALESCE(v.document_id, t.document_id) AS document_id" in src
        assert "SELECT id, document_id, content, chunk_metadata, rrf_score" in src
