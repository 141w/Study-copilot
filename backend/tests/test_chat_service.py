import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatSession, Document, Message, User
from app.exceptions import NotFoundError
from app.services import chat_service


def _user(suffix: str = "") -> User:
    uid = uuid.uuid4().hex[:8]
    return User(
        id=f"cs-user-{uid}{suffix}",
        username=f"csuser_{uid}{suffix}",
        email=f"cs_{uid}{suffix}@test.local",
        password_hash="x" * 60,
    )


def _doc(user_id: str, deleted: bool = False) -> Document:
    from datetime import UTC, datetime

    return Document(
        id=str(uuid.uuid4()),
        user_id=user_id,
        filename="test_doc.pdf",
        file_path="/tmp/test_doc.pdf",
        status="ready",
        deleted_at=datetime.now(UTC).replace(tzinfo=None) if deleted else None,
    )


@pytest.mark.asyncio
async def test_ensure_session_creates_new(db_session: AsyncSession):
    u = _user()
    db_session.add(u)
    await db_session.commit()

    sess_id, is_new = await chat_service._ensure_session(db_session, u.id, None, "What is Python?")
    assert is_new is True
    assert sess_id is not None

    sess = await db_session.get(ChatSession, sess_id)
    assert sess is not None
    assert sess.user_id == u.id
    assert sess.title == "What is Python?"


@pytest.mark.asyncio
async def test_ensure_session_existing_and_idor_protection(db_session: AsyncSession):
    u1 = _user("1")
    u2 = _user("2")
    db_session.add_all([u1, u2])
    await db_session.commit()

    sess_id, _ = await chat_service._ensure_session(db_session, u1.id, None, "User 1 Question")

    # User 1 accesses their own session -> succeeds
    same_id, is_new = await chat_service._ensure_session(
        db_session, u1.id, sess_id, "User 1 Question"
    )
    assert same_id == sess_id
    assert is_new is False

    # User 2 tries to access User 1's session -> NotFoundError (IDOR blocked)
    with pytest.raises(NotFoundError, match="会话不存在"):
        await chat_service._ensure_session(db_session, u2.id, sess_id, "Hacked Question")

    # Non-existent session -> NotFoundError
    with pytest.raises(NotFoundError, match="会话不存在"):
        await chat_service._ensure_session(db_session, u1.id, "nonexistent-sess-id", "Question")


@pytest.mark.asyncio
async def test_validate_document_ids_user_isolation(db_session: AsyncSession):
    u1 = _user("1")
    u2 = _user("2")
    db_session.add_all([u1, u2])
    await db_session.commit()

    d1 = _doc(u1.id)
    d2 = _doc(u2.id)
    d1_del = _doc(u1.id, deleted=True)
    db_session.add_all([d1, d2, d1_del])
    await db_session.commit()

    valid_ids = await chat_service._validate_document_ids(
        db_session, u1.id, [d1.id, d2.id, d1_del.id, "fake-id"]
    )
    assert valid_ids == [d1.id]


@pytest.mark.asyncio
async def test_ask_question_non_streaming(db_session: AsyncSession):
    u = _user()
    db_session.add(u)
    await db_session.commit()

    d = _doc(u.id)
    db_session.add(d)
    await db_session.commit()

    mock_rag_result = {
        "answer": "Python is a high-level programming language.",
        "sources": [{"index": 1, "text": "Python source snippet"}],
        "used_source_indices": [1],
        "filtered_sources": [{"index": 1, "text": "Python source snippet"}],
        "context_used": True,
    }

    with (
        patch.object(chat_service, "get_llm_config_with_secret", return_value={}),
        patch.object(chat_service.rag_engine, "ask", new_callable=AsyncMock) as mock_ask,
        patch.object(chat_service, "_embed_text", return_value=None),
    ):
        mock_ask.return_value = mock_rag_result

        result = await chat_service.ask_question(db_session, u, "What is Python?", [d.id])

        assert result["answer"] == mock_rag_result["answer"]
        assert result["sources"] == mock_rag_result["sources"]
        assert "session_id" in result

        # Verify messages saved to database
        sess_id = result["session_id"]
        sess, msgs = await chat_service.get_session_history(db_session, u, sess_id)
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[0].content == "What is Python?"
        assert msgs[1].role == "assistant"
        assert msgs[1].content == mock_rag_result["answer"]
        assert "Python source snippet" in msgs[1].sources


@pytest.mark.asyncio
async def test_ask_question_stream_retains_sources(db_session: AsyncSession):
    u = _user()
    db_session.add(u)
    await db_session.commit()

    async def mock_stream(*args, **kwargs):
        yield {
            "type": "sources",
            "sources": [{"index": 1, "source": "doc.pdf", "text": "Sample source"}],
            "filtered_sources": [{"index": 1, "source": "doc.pdf", "text": "Sample source"}],
        }
        yield {"type": "token", "content": "Hello "}
        yield {"type": "token", "content": "world!"}

    with (
        patch.object(chat_service, "get_llm_config_with_secret", return_value={}),
        patch.object(chat_service.rag_engine, "ask_stream", side_effect=mock_stream),
        patch.object(chat_service, "_embed_text", return_value=None),
    ):
        chunks = []
        async for item in chat_service.ask_question_stream(db_session, u, "Say hello", []):
            chunks.append(item)

        assert any(c["type"] == "sources" for c in chunks)
        assert any(c["type"] == "token" and c["content"] == "Hello " for c in chunks)
        assert chunks[-1]["type"] == "done"

        # Check that the assistant message was stored with non-empty sources
        session_chunk = next(c for c in chunks if c["type"] == "session")
        sess_id = session_chunk["session_id"]
        _, msgs = await chat_service.get_session_history(db_session, u, sess_id)
        assert len(msgs) == 2
        assistant_msg = msgs[1]
        assert assistant_msg.content == "Hello world!"
        sources = json.loads(assistant_msg.sources)
        assert len(sources) == 1
        assert sources[0]["source"] == "doc.pdf"


@pytest.mark.asyncio
async def test_session_crud(db_session: AsyncSession):
    u1 = _user("1")
    u2 = _user("2")
    db_session.add_all([u1, u2])
    await db_session.commit()

    s1 = ChatSession(id=str(uuid.uuid4()), user_id=u1.id, title="Session 1")
    s2 = ChatSession(id=str(uuid.uuid4()), user_id=u1.id, title="Session 2")
    s_other = ChatSession(id=str(uuid.uuid4()), user_id=u2.id, title="Session Other")
    db_session.add_all([s1, s2, s_other])
    await db_session.commit()

    # list_sessions
    user_sessions = await chat_service.list_sessions(db_session, u1)
    assert len(user_sessions) == 2
    session_ids = {s.id for s in user_sessions}
    assert s1.id in session_ids and s2.id in session_ids
    assert s_other.id not in session_ids

    # update_session_title
    new_title = await chat_service.update_session_title(db_session, u1, s1.id, "Renamed Session")
    assert new_title == "Renamed Session"

    # update_session_title on other user's session -> NotFoundError
    with pytest.raises(NotFoundError):
        await chat_service.update_session_title(db_session, u2, s1.id, "Hacked Title")

    # delete_session
    await chat_service.delete_session(db_session, u1, s1.id)
    with pytest.raises(NotFoundError):
        await chat_service.get_session_history(db_session, u1, s1.id)

    # delete_session on other user's session -> NotFoundError
    with pytest.raises(NotFoundError):
        await chat_service.delete_session(db_session, u1, s_other.id)


@pytest.mark.asyncio
async def test_ask_question_merges_user_config_with_runtime_config(db_session: AsyncSession):
    u = _user("merge_test")
    db_session.add(u)
    await db_session.commit()

    fake_user_config = {
        "api_key": "sk-secret-key-123",
        "base_url": "https://api.custom.com/v1",
        "model_name": "custom-model",
        "context_window": 262144,
        "temperature": 0.7,
    }

    mock_rag_result = {
        "answer": "Test answer",
        "sources": [],
        "used_source_indices": [],
        "filtered_sources": [],
        "context_used": True,
    }

    with (
        patch.object(chat_service, "get_llm_config_with_secret", return_value=fake_user_config),
        patch.object(chat_service.rag_engine, "ask", new_callable=AsyncMock) as mock_ask,
        patch.object(chat_service, "_embed_text", return_value=None),
    ):
        mock_ask.return_value = mock_rag_result

        # Call ask_question with runtime config (e.g. ai_style)
        await chat_service.ask_question(
            db_session, u, "Question", [], config={"ai_style": "rigorous"}
        )

        # Assert rag_engine.ask received merged config containing both user's key/model and ai_style
        mock_ask.assert_called_once()
        passed_config = mock_ask.call_args[0][3]
        assert passed_config["api_key"] == "sk-secret-key-123"
        assert passed_config["base_url"] == "https://api.custom.com/v1"
        assert passed_config["model_name"] == "custom-model"
        assert passed_config["ai_style"] == "rigorous"

    async def mock_stream(*args, **kwargs):
        yield {"type": "token", "content": "chunk"}

    with (
        patch.object(chat_service, "get_llm_config_with_secret", return_value=fake_user_config),
        patch.object(
            chat_service.rag_engine, "ask_stream", side_effect=mock_stream
        ) as mock_stream_call,
        patch.object(chat_service, "_embed_text", return_value=None),
    ):
        chunks = []
        async for item in chat_service.ask_question_stream(
            db_session, u, "Question", [], config={"ai_style": "concise"}
        ):
            chunks.append(item)

        mock_stream_call.assert_called_once()
        passed_stream_config = mock_stream_call.call_args[0][3]
        assert passed_stream_config["api_key"] == "sk-secret-key-123"
        assert passed_stream_config["base_url"] == "https://api.custom.com/v1"
        assert passed_stream_config["model_name"] == "custom-model"
        assert passed_stream_config["ai_style"] == "concise"
