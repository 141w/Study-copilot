import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import course_generator
from app.db import Document, DocumentChunk, User


def _user(suffix: str = "") -> User:
    uid = uuid.uuid4().hex[:8]
    return User(
        id=f"cg-user-{uid}{suffix}",
        username=f"cguser_{uid}{suffix}",
        email=f"cg_{uid}{suffix}@test.local",
        password_hash="x" * 60,
    )


def _doc(user_id: str, deleted: bool = False) -> Document:
    from datetime import UTC, datetime
    return Document(
        id=str(uuid.uuid4()),
        user_id=user_id,
        filename="course_material.pdf",
        file_path="/tmp/fake.pdf",
        status="ready",
        deleted_at=datetime.now(UTC).replace(tzinfo=None) if deleted else None,
    )


def _chunk(doc_id: str, content: str, idx: int = 0) -> DocumentChunk:
    return DocumentChunk(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        content=content,
        chunk_index=idx,
    )


def test_build_context_from_chunks():
    chunks = [
        {"content": "First chunk."},
        {"content": "   "},  # empty
        {"content": "Second chunk."},
    ]
    ctx = course_generator._build_context_from_chunks(chunks, max_chars=100)
    assert "First chunk." in ctx
    assert "Second chunk." in ctx

    # Test truncation
    long_chunks = [{"content": "a" * 50}, {"content": "b" * 50}]
    ctx_truncated = course_generator._build_context_from_chunks(long_chunks, max_chars=60)
    assert len(ctx_truncated) <= 60


@pytest.mark.asyncio
async def test_load_document_context_user_isolation(db_session: AsyncSession):
    u1 = _user("1")
    u2 = _user("2")
    db_session.add_all([u1, u2])
    await db_session.commit()

    d1 = _doc(u1.id)
    d2 = _doc(u2.id)
    d1_deleted = _doc(u1.id, deleted=True)
    db_session.add_all([d1, d2, d1_deleted])
    await db_session.commit()

    c1 = _chunk(d1.id, "User 1 document content")
    c2 = _chunk(d2.id, "User 2 document content")
    c3 = _chunk(d1_deleted.id, "User 1 deleted content")
    db_session.add_all([c1, c2, c3])
    await db_session.commit()

    # User 1 tries to query d1, d2, and d1_deleted
    ctx = await course_generator._load_document_context(
        db_session, [d1.id, d2.id, d1_deleted.id], u1.id
    )

    assert "User 1 document content" in ctx
    # User 2's doc must NOT be leaked
    assert "User 2 document content" not in ctx
    # Deleted doc must NOT be included
    assert "User 1 deleted content" not in ctx


@pytest.mark.asyncio
async def test_generate_outline_with_curly_braces():
    # Content with code or JSON that caused format() crashes
    context_with_braces = "Here is some code: if (x == {a: 1}) { return true; } and more {data}"

    mock_outline = {
        "title": "Programming Course",
        "description": "Learn syntax",
        "difficulty": "入门",
        "sections": [
            {
                "id": "s1",
                "title": "Syntax Intro",
                "objective": "Understand braces",
                "difficulty": "入门",
                "key_points": ["Braces", "Variables"],
            }
        ],
    }

    with patch.object(course_generator.LLM, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = f"```json\n{json.dumps(mock_outline)}\n```"
        outline = await course_generator.generate_outline(context_with_braces)
        assert outline["title"] == "Programming Course"
        assert len(outline["sections"]) == 1


@pytest.mark.asyncio
async def test_generate_outline_fallback_on_error():
    with patch.object(course_generator.LLM, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = Exception("LLM call failed")
        outline = await course_generator.generate_outline("Some context")
        assert outline["title"] == "未命名课程"
        assert len(outline["sections"]) == 3


@pytest.mark.asyncio
async def test_generate_course_full_flow(db_session: AsyncSession):
    u = _user()
    db_session.add(u)
    await db_session.commit()

    d = _doc(u.id)
    db_session.add(d)
    await db_session.commit()

    c = _chunk(d.id, "Machine learning fundamentals and neural networks.")
    db_session.add(c)
    await db_session.commit()

    mock_outline = {
        "title": "ML 101",
        "description": "Intro to ML",
        "difficulty": "入门",
        "sections": [
            {
                "id": "sec-1",
                "title": "Neural Networks",
                "key_points": ["Backpropagation", "Weights"],
            }
        ],
    }

    mock_quiz = [
        {
            "type": "choice",
            "question": "What is backpropagation?",
            "options": ["A", "B", "C", "D"],
            "answer": "A",
            "explanation": "Gradient calculation",
        }
    ]

    with patch.object(course_generator, "generate_outline", new_callable=AsyncMock) as mock_outline_fn, \
         patch("app.core.quiz_generator.QuizGenerator.generate_quizzes", new_callable=AsyncMock) as mock_quiz_fn:
        mock_outline_fn.return_value = mock_outline
        mock_quiz_fn.return_value = mock_quiz

        course = await course_generator.generate_course(
            db_session, u, [d.id], requirement="Focus on basics"
        )

        assert course["outline"]["title"] == "ML 101"
        assert len(course["quizzes"]) == 1
        assert course["quizzes"][0]["section_id"] == "sec-1"
        assert course["quizzes"][0]["section_title"] == "Neural Networks"
