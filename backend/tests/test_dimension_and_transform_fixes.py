"""回归测试：H-1 维度预检 + H-2 transform 读 DB（2026-09 深度审计批次）。

H-1：embedding 实际维度与配置不符时，add_chunks 必须在 INSERT 前给出
     明确中文报错（而非 PG 层晦涩的 22023）。
H-2：transform_document_chunks 必须从 document_chunks 表读文本（pgvector
     时代 legacy FAISS 索引不再生成，旧路径对一切新文档恒报"文档内容为空"）。
"""

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from app.exceptions import ValidationError

# ── H-1: add_chunks 维度预检 ─────────────────────────────────────────────────


class TestAddChunksDimensionPreflight:
    @pytest.mark.asyncio
    async def test_dimension_mismatch_raises_friendly_error(self):
        """模型输出 1024 维但配置 768 → 必须报中文 ValidationError。"""
        from app.core.pgvector_store import PgVectorStore

        store = PgVectorStore(user_id="u1", dimension=768)
        fake_embeddings = [np.zeros(1024, dtype=np.float32).tolist()]

        with patch.object(
            store, attribute=None, side_effect=None
        ) if False else patch(
            "app.core.pgvector_store.embedder"
        ) as mock_embedder:
            mock_embedder.embed_texts = AsyncMock(return_value=fake_embeddings)
            with pytest.raises(ValidationError, match="维度不匹配"):
                await store.add_chunks(
                    [{"text": "内容"}], "doc-1", db=AsyncMock()
                )

    @pytest.mark.asyncio
    async def test_dimension_match_passes_preflight(self, db_session):
        """维度一致时预检放行（后续由 DB/mock 决定成败，不应在预检处抛错）。"""
        from app.core.pgvector_store import PgVectorStore

        store = PgVectorStore(user_id="u1", dimension=768)
        fake_embeddings = [np.zeros(768, dtype=np.float32).tolist()]

        fake_db = AsyncMock()
        with patch("app.core.pgvector_store.embedder") as mock_embedder:
            mock_embedder.embed_texts = AsyncMock(return_value=fake_embeddings)
            ok = await store.add_chunks([{"text": "内容"}], "doc-1", db=fake_db)
        assert ok is True
        fake_db.execute.assert_awaited()

    def test_sql_uses_instance_dimension_not_hardcoded(self):
        """INSERT 的 CAST 必须用实例维度而非硬编码 768。"""
        import inspect

        from app.core.pgvector_store import PgVectorStore

        src = inspect.getsource(PgVectorStore.add_chunks)
        assert "vector(768)" not in src, "不允许再出现硬编码 768 维"
        assert "vector({self.dimension})" in src


# ── H-2: transform_document_chunks 读 DB ───────────────────────────────────


class TestTransformDocumentChunksReadsDB:
    @pytest.mark.asyncio
    async def test_reads_chunks_from_db_not_faiss(self, db_session):
        """文档 ready 且 DB 有 chunk 时，必须取到文本并推进到 LLM 调用层。"""
        import uuid as _uuid

        from app.api.auth import get_current_user
        from app.db import Document, DocumentChunk, User
        from app.main import app
        from app.services import transform_service

        user = User(
            id=str(_uuid.uuid4()), username="t_h2_probe",
            email="t_h2@t.io", password_hash="x",
        )
        db_session.add(user)
        doc = Document(
            id=str(_uuid.uuid4()), user_id=user.id, filename="bio.txt",
            file_path="/tmp/x", status="ready", chunk_count=1, file_size=10,
        )
        db_session.add(doc)
        db_session.add(
            DocumentChunk(
                id=str(_uuid.uuid4()), document_id=doc.id,
                content="热力学第一定律：能量守恒", chunk_index=0, chunk_metadata={},
            )
        )
        await db_session.commit()

        # 直接调 service（绕开 API 层），mock LLM.generate 返回结果；
        # 同时监视 legacy DocumentVectorStore —— DB 有 chunk 时绝不应触发它
        with patch(
            "app.core.vector_store.DocumentVectorStore"
        ) as MockLegacy:
            MockLegacy.side_effect = AssertionError(
                "DB 有 chunk 时不应触发 legacy FAISS 路径"
            )
            with patch.object(
                transform_service, "_build_llm"
            ) as mock_build:
                mock_llm = AsyncMock()
                mock_llm.generate = AsyncMock(return_value="转换结果文本")
                mock_build.return_value = mock_llm
                out = await transform_service.transform_document_chunks(
                    db_session, user, doc.id, "summary"
                )

        assert "转换结果文本" in out["result"]
        assert out["document_id"] == doc.id
        assert MockLegacy.call_count == 0

    @pytest.mark.asyncio
    async def test_no_chunks_raises_content_error(self, db_session):
        """DB 与兜底都无内容时报"文档内容为空"。"""
        import uuid as _uuid

        from app.db import Document, User
        from app.services import transform_service

        user = User(
            id=str(_uuid.uuid4()), username="t_h2_empty",
            email="t_h2e@t.io", password_hash="x",
        )
        db_session.add(user)
        doc = Document(
            id=str(_uuid.uuid4()), user_id=user.id, filename="e.txt",
            file_path="/tmp/e", status="ready", chunk_count=0, file_size=5,
        )
        db_session.add(doc)
        await db_session.commit()

        from app.exceptions import AppError

        with pytest.raises(AppError) as ei:
            await transform_service.transform_document_chunks(
                db_session, user, doc.id, "summary"
            )
        assert "文档内容为空" in str(ei.value.message)
