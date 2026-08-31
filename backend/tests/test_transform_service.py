"""Tests for transform_service: validation, LLM mocking, note/document transforms."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.transformations import list_transformations
from app.db import Document, Note, User
from app.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.services import transform_service


# ── helpers ─────────────────────────────────────────────────────────────────


def _user(suffix: str = "") -> User:
    uid = uuid.uuid4().hex[:8]
    return User(
        id=f"tx-user-{uid}{suffix}",
        username=f"txuser_{uid}{suffix}",
        email=f"tx_{uid}{suffix}@test.local",
        password_hash="x" * 60,
    )


def _doc(user_id: str) -> Document:
    return Document(
        id=str(uuid.uuid4()),
        user_id=user_id,
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        status="ready",
        chunk_count=5,
    )


def _note(user_id: str, course_id: str | None = None) -> Note:
    return Note(
        id=str(uuid.uuid4()),
        user_id=user_id,
        course_space_id=course_id,
        title="My Note",
        content="Some content here",
        note_type="markdown",
    )


# ── get_available_transformations ──────────────────────────────────────────


class TestGetAvailableTransformations:

    def test_returns_list(self):
        result = list_transformations()
        assert isinstance(result, list)
        assert len(result) == 8

    def test_each_has_required_keys(self):
        for t in list_transformations():
            assert "key" in t
            assert "name" in t
            assert "name_en" in t
            assert "description" in t

    def test_includes_all_expected_types(self):
        keys = {t["key"] for t in list_transformations()}
        expected = {"summary", "keypoints", "outline", "flashcards",
                     "mindmap", "qa_pairs", "translate_en", "translate_zh"}
        assert keys == expected


# ── transform_content ──────────────────────────────────────────────────────


class TestTransformContent:

    @pytest.mark.asyncio
    async def test_unknown_type_raises_validation_error(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        with pytest.raises(ValidationError, match="未知的转换类型"):
            await transform_service.transform_content(
                db_session, u, "some text", "nonexistent_type"
            )

    @pytest.mark.asyncio
    async def test_empty_text_raises_validation_error(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        with pytest.raises(ValidationError, match="源文本内容为空"):
            await transform_service.transform_content(
                db_session, u, "   ", "summary"
            )

    @pytest.mark.asyncio
    async def test_empty_string_raises_validation_error(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        with pytest.raises(ValidationError, match="源文本内容为空"):
            await transform_service.transform_content(
                db_session, u, "", "summary"
            )

    @pytest.mark.asyncio
    async def test_long_text_truncated(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        long_text = "x" * 15000
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="result")

        with patch.object(transform_service, "_build_llm", return_value=mock_llm):
            await transform_service.transform_content(
                db_session, u, long_text, "summary"
            )

        call_kwargs = mock_llm.generate.call_args
        prompt = call_kwargs.kwargs.get("prompt", call_kwargs[1].get("prompt", "")) if call_kwargs.kwargs else call_kwargs[1].get("prompt", "")
        assert "[内容已截断...]" in prompt

    @pytest.mark.asyncio
    async def test_successful_transform_returns_result(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="这里是摘要内容")

        with patch.object(transform_service, "_build_llm", return_value=mock_llm):
            result = await transform_service.transform_content(
                db_session, u, "Some text to summarize", "summary"
            )

        assert result["transform_type"] == "summary"
        assert result["result"] == "这里是摘要内容"
        assert result["source_title"] == ""
        assert "transform_name" in result

    @pytest.mark.asyncio
    async def test_result_empty_string_returns_empty(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=None)

        with patch.object(transform_service, "_build_llm", return_value=mock_llm):
            result = await transform_service.transform_content(
                db_session, u, "Some text", "summary"
            )

        assert result["result"] == ""

    @pytest.mark.asyncio
    async def test_llm_failure_raises_external_service_error(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("API timeout"))

        with patch.object(transform_service, "_build_llm", return_value=mock_llm):
            with pytest.raises(ExternalServiceError, match="AI 转换失败"):
                await transform_service.transform_content(
                    db_session, u, "Some text", "summary"
                )

    @pytest.mark.asyncio
    async def test_passes_correct_params_to_llm(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="result")

        with patch.object(transform_service, "_build_llm", return_value=mock_llm):
            await transform_service.transform_content(
                db_session, u, "text", "keypoints", source_title="My Doc"
            )

        mock_llm.generate.assert_called_once()
        kwargs = mock_llm.generate.call_args.kwargs
        assert kwargs["system_prompt"] is not None
        assert "text" in kwargs["prompt"]
        assert kwargs["max_tokens"] == 2048
        assert kwargs["temperature"] == 0.2


# ── transform_note ─────────────────────────────────────────────────────────


class TestTransformNote:

    @pytest.mark.asyncio
    async def test_note_not_found_raises(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        with pytest.raises(NotFoundError, match="笔记不存在"):
            await transform_service.transform_note(
                db_session, u, "nonexistent-id", "summary"
            )

    @pytest.mark.asyncio
    async def test_other_user_note_not_found(self, db_session: AsyncSession):
        u1 = _user()
        u2 = _user()
        db_session.add_all([u1, u2])
        await db_session.commit()

        note = _note(u2.id)
        db_session.add(note)
        await db_session.commit()

        with pytest.raises(NotFoundError, match="笔记不存在"):
            await transform_service.transform_note(
                db_session, u1, note.id, "summary"
            )

    @pytest.mark.asyncio
    async def test_successful_note_transform(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        note = _note(u.id)
        db_session.add(note)
        await db_session.commit()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="摘要结果")

        with patch.object(transform_service, "_build_llm", return_value=mock_llm):
            result = await transform_service.transform_note(
                db_session, u, note.id, "summary"
            )

        assert result["note_id"] == note.id
        assert result["transform_type"] == "summary"
        assert result["result"] == "摘要结果"
        assert result["source_title"] == "My Note"

    @pytest.mark.asyncio
    async def test_note_without_title(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        note = _note(u.id)
        note.title = ""
        db_session.add(note)
        await db_session.commit()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="摘要")

        with patch.object(transform_service, "_build_llm", return_value=mock_llm):
            result = await transform_service.transform_note(
                db_session, u, note.id, "keypoints"
            )

        assert result["source_title"] == ""
        # text should be just content without title prefix
        call_kwargs = mock_llm.generate.call_args.kwargs
        assert note.content in call_kwargs["prompt"]
        assert "My Note" not in call_kwargs["prompt"]


# ── transform_document_chunks ──────────────────────────────────────────────


class TestTransformDocumentChunks:

    @pytest.mark.asyncio
    async def test_document_not_found_raises(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        with pytest.raises(NotFoundError, match="文档不存在"):
            await transform_service.transform_document_chunks(
                db_session, u, "nonexistent-doc", "summary"
            )

    @pytest.mark.asyncio
    async def test_other_user_document_not_found(self, db_session: AsyncSession):
        u1 = _user()
        u2 = _user()
        db_session.add_all([u1, u2])
        await db_session.commit()

        doc = _doc(u2.id)
        db_session.add(doc)
        await db_session.commit()

        with pytest.raises(NotFoundError, match="文档不存在"):
            await transform_service.transform_document_chunks(
                db_session, u1, doc.id, "summary"
            )

    @pytest.mark.asyncio
    async def test_empty_document_raises(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        doc = _doc(u.id)
        db_session.add(doc)
        await db_session.commit()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="result")

        with patch.object(transform_service, "_build_llm", return_value=mock_llm):
            with patch("app.core.vector_store.DocumentVectorStore") as mock_vs:
                mock_store = MagicMock()
                mock_store._store.chunks = []
                mock_store.load = AsyncMock()
                mock_vs.return_value = mock_store

                with pytest.raises(ValidationError, match="文档内容为空"):
                    await transform_service.transform_document_chunks(
                        db_session, u, doc.id, "summary"
                    )

    @pytest.mark.asyncio
    async def test_successful_document_transform(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        doc = _doc(u.id)
        db_session.add(doc)
        await db_session.commit()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="文档摘要结果")

        with patch.object(transform_service, "_build_llm", return_value=mock_llm):
            with patch("app.core.vector_store.DocumentVectorStore") as mock_vs:
                mock_store = MagicMock()
                mock_store._store.chunks = [
                    {"text": "Chapter 1 content"},
                    {"text": "Chapter 2 content"},
                    {"text": ""},  # empty chunk filtered out
                ]
                mock_store.load = AsyncMock()
                mock_vs.return_value = mock_store

                result = await transform_service.transform_document_chunks(
                    db_session, u, doc.id, "summary"
                )

        assert result["document_id"] == doc.id
        assert result["transform_type"] == "summary"
        assert result["result"] == "文档摘要结果"
        assert result["source_title"] == "test.pdf"

    @pytest.mark.asyncio
    async def test_chunks_combined_with_limit(self, db_session: AsyncSession):
        u = _user()
        db_session.add(u)
        await db_session.commit()

        doc = _doc(u.id)
        db_session.add(doc)
        await db_session.commit()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="result")

        with patch.object(transform_service, "_build_llm", return_value=mock_llm):
            with patch("app.core.vector_store.DocumentVectorStore") as mock_vs:
                # Create 35 chunks (>30 limit)
                chunks = [{"text": f"chunk {i}"} for i in range(35)]
                mock_store = MagicMock()
                mock_store._store.chunks = chunks
                mock_store.load = AsyncMock()
                mock_vs.return_value = mock_store

                await transform_service.transform_document_chunks(
                    db_session, u, doc.id, "summary"
                )

        # Verify only first 30 chunks were combined
        call_kwargs = mock_llm.generate.call_args.kwargs
        prompt = call_kwargs["prompt"]
        # Should contain chunk 0 through chunk 29, but not chunk 34
        assert "chunk 0" in prompt
        assert "chunk 29" in prompt
        assert "chunk 34" not in prompt
