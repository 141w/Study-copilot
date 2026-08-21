"""
Chat service — ask questions (streaming & non-streaming), session CRUD.
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rag_engine import rag_engine
from app.services.config_service import get_llm_config_with_secret
from app.db import ChatSession, Message, User
from app.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


async def ask_question(
    db: AsyncSession,
    user: User,
    question: str,
    document_ids: list[str],
    session_id: str | None = None,
    config: dict | None = None,
) -> dict:
    """Non-streaming RAG ask. Returns {answer, sources, used_source_indices, filtered_sources, session_id}."""
    if not document_ids:
        raise ValidationError("请选择文档")

    user_config = await get_llm_config_with_secret(db, user)
    llm_config = config if config else user_config

    session_id, _ = await _ensure_session(db, user.id, session_id, question)
    history = await _get_history(db, session_id)

    result = await rag_engine.ask(document_ids, question, history, llm_config)

    # Persist messages
    sources_json = json.dumps(result.get("sources", []), ensure_ascii=False)
    await _save_messages(db, session_id, question, result["answer"], sources_json)

    return {
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "used_source_indices": result.get("used_source_indices", []),
        "filtered_sources": result.get("filtered_sources", []),
        "session_id": session_id,
    }


async def ask_question_stream(
    db: AsyncSession,
    user: User,
    question: str,
    document_ids: list[str],
    session_id: str | None = None,
    config: dict | None = None,
) -> AsyncIterator[dict]:
    """Streaming RAG ask. Yields dicts with 'type' key: sources / token / answer / done."""
    if not document_ids:
        raise ValidationError("请选择文档")

    user_config = await get_llm_config_with_secret(db, user)
    llm_config = config if config else user_config

    session_id, _ = await _ensure_session(db, user.id, session_id, question)
    history = await _get_history(db, session_id)

    # 第一时间下发 session_id，保证前端在所有路径（含无 sources 的快速路径）
    # 都能拿到会话 ID，从而支持多轮追问
    yield {"type": "session", "session_id": session_id}

    answer_parts: list[str] = []

    async for chunk in rag_engine.ask_stream(document_ids, question, history, llm_config):
        if chunk["type"] == "sources":
            yield {
                "type": "sources",
                "sources": chunk["sources"],
                "filtered_sources": chunk["filtered_sources"],
                "session_id": session_id,
            }
        elif chunk["type"] == "thinking":
            # 转发思考过程事件（Agentic RAG）
            yield {"type": "thinking", "step": chunk.get("step", ""), "detail": chunk.get("detail", "")}
        elif chunk["type"] == "token":
            answer_parts.append(chunk["content"])
            yield {"type": "token", "content": chunk["content"]}
        elif chunk["type"] == "answer":
            answer_parts.clear()
            answer_parts.append(chunk["content"])
            yield {"type": "answer", "content": chunk["content"]}
        elif chunk["type"] == "answer_refined":
            # 答案反思后修正：替换已流式传输的内容
            answer_parts.clear()
            answer_parts.append(chunk["content"])
            yield {"type": "answer_refined", "content": chunk["content"]}

    # Persist after stream completes
    full_answer = "".join(answer_parts)
    await _save_messages(db, session_id, question, full_answer, json.dumps([], ensure_ascii=False))
    yield {"type": "done"}


async def list_sessions(
    db: AsyncSession,
    user: User,
) -> list[ChatSession]:
    """Return all chat sessions for the user, newest first."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.created_at.desc())
    )
    return list(result.scalars().all())


async def get_session_history(
    db: AsyncSession,
    user: User,
    session_id: str,
) -> tuple:
    """Return (session, messages) for the given session. Raises NotFoundError if missing."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("会话不存在")

    msg_result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    msgs = list(msg_result.scalars().all())
    return session, msgs


async def delete_session(
    db: AsyncSession,
    user: User,
    session_id: str,
) -> None:
    """Delete a chat session. Raises NotFoundError if missing."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("会话不存在")

    await db.delete(session)
    await db.commit()


async def update_session_title(
    db: AsyncSession,
    user: User,
    session_id: str,
    title: str,
) -> str:
    """Update session title. Returns the new title. Raises NotFoundError if missing."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("会话不存在")

    session.title = title
    await db.commit()
    return title


# ── internal helpers ────────────────────────────────────────────────────────


async def _ensure_session(
    db: AsyncSession,
    user_id: str,
    session_id: str | None,
    question: str,
) -> tuple[str, bool]:
    """Return (session_id, is_new). Creates a new session if session_id is None."""
    is_new = False
    if not session_id:
        session_id = str(uuid.uuid4())
        new_session = ChatSession(id=session_id, user_id=user_id, title=question[:50])
        db.add(new_session)
        await db.commit()
        is_new = True
    return session_id, is_new


async def _get_history(db: AsyncSession, session_id: str) -> list:
    """Fetch message history for a session as list of {role, content} dicts."""
    msg_result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    msgs = msg_result.scalars().all()
    return [{"role": m.role, "content": m.content} for m in msgs]


async def _save_messages(
    db: AsyncSession,
    session_id: str,
    question: str,
    answer: str,
    sources_json: str,
) -> None:
    """Persist user + assistant messages."""
    user_msg = Message(id=str(uuid.uuid4()), session_id=session_id, role="user", content=question)
    ai_msg = Message(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="assistant",
        content=answer,
        sources=sources_json,
    )
    db.add(user_msg)
    db.add(ai_msg)
    await db.commit()
