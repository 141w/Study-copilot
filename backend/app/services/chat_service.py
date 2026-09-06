"""
Chat service — ask questions (streaming & non-streaming), session CRUD, semantic search.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedder import embedder
from app.core.rag_engine import rag_engine
from app.db import ChatSession, Document, Message, User
from app.exceptions import NotFoundError
from app.services.config_service import get_llm_config_with_secret

logger = logging.getLogger(__name__)

_Msg_INSERT_PG = text("""
    INSERT INTO messages (id, session_id, role, content, sources, embedding, created_at)
    VALUES (
        :id, :session_id, :role, :content, :sources,
        CAST(:embedding AS vector(768)), :created_at
    )
""")


def _vec_str(embedding: list[float] | None) -> str | None:
    """Convert embedding list to pgvector string format '[0.1,0.2,...]'."""
    if embedding is None:
        return None
    return "[" + ",".join(str(v) for v in embedding) + "]"


async def _embed_text(text_str: str) -> list[float] | None:
    """Compute embedding for a single text. Returns None on failure (non-blocking)."""
    if not text_str or not text_str.strip():
        return None
    try:
        vec = await embedder.embed_query(text_str)
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)
    except Exception as exc:
        logger.warning("Message embedding failed: %s", exc)
        return None


async def _insert_message(
    db: AsyncSession,
    msg_id: str,
    session_id: str,
    role: str,
    content: str,
    sources_json: str | None,
    embedding: list[float] | None,
) -> None:
    """Insert message into DB.

    Uses explicit CAST(:embedding AS vector(768)) for PostgreSQL/pgvector,
    and ORM for SQLite. If vector insertion encounters any type or dialect
    mismatch, falls back to embedding=None so user conversation is never blocked.
    """
    bind = db.get_bind()
    is_pg = bind is not None and getattr(bind.dialect, "name", "") == "postgresql"

    try:
        if is_pg:
            await db.execute(
                _Msg_INSERT_PG,
                {
                    "id": msg_id,
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                    "sources": sources_json,
                    "embedding": _vec_str(embedding),
                    "created_at": datetime.now(UTC).replace(tzinfo=None),
                },
            )
        else:
            msg = Message(
                id=msg_id,
                session_id=session_id,
                role=role,
                content=content,
                sources=sources_json,
                embedding=embedding,
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            db.add(msg)
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to insert message with embedding: %s. Falling back to embedding=None.", exc)
        await db.rollback()
        if is_pg:
            await db.execute(
                _Msg_INSERT_PG,
                {
                    "id": msg_id,
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                    "sources": sources_json,
                    "embedding": None,
                    "created_at": datetime.now(UTC).replace(tzinfo=None),
                },
            )
        else:
            msg = Message(
                id=msg_id,
                session_id=session_id,
                role=role,
                content=content,
                sources=sources_json,
                embedding=None,
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            db.add(msg)
        await db.commit()


async def _validate_document_ids(
    db: AsyncSession, user_id: str, document_ids: list[str]
) -> list[str]:
    """Filter document_ids to ensure they belong to the user and are not soft-deleted."""
    if not document_ids:
        return []
    result = await db.execute(
        select(Document.id).where(
            Document.id.in_(document_ids),
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def ask_question(
    db: AsyncSession,
    user: User,
    question: str,
    document_ids: list[str],
    session_id: str | None = None,
    config: dict | None = None,
) -> dict:
    """Non-streaming RAG ask. Returns {answer, sources, used_source_indices, filtered_sources, session_id}."""
    user_config = await get_llm_config_with_secret(db, user)
    llm_config = dict(user_config)
    if config:
        llm_config.update({k: v for k, v in config.items() if v is not None})

    valid_doc_ids = await _validate_document_ids(db, user.id, document_ids)
    session_id, _ = await _ensure_session(db, user.id, session_id, question)
    history = await _get_history(db, session_id)

    result = await rag_engine.ask(valid_doc_ids, question, history, llm_config)

    # Persist messages with embeddings (non-blocking: embedding failure doesn't break the flow)
    sources_json = json.dumps(result.get("sources", []), ensure_ascii=False)
    q_emb = await _embed_text(question)
    a_emb = await _embed_text(result["answer"])
    await _insert_message(db, str(uuid.uuid4()), session_id, "user", question, None, q_emb)
    await _insert_message(db, str(uuid.uuid4()), session_id, "assistant", result["answer"], sources_json, a_emb)

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
    user_config = await get_llm_config_with_secret(db, user)
    llm_config = dict(user_config)
    if config:
        llm_config.update({k: v for k, v in config.items() if v is not None})

    valid_doc_ids = await _validate_document_ids(db, user.id, document_ids)
    session_id, _ = await _ensure_session(db, user.id, session_id, question)
    history = await _get_history(db, session_id)

    yield {"type": "session", "session_id": session_id}

    # Compute user message embedding (non-blocking)
    q_emb = await _embed_text(question)
    user_msg_id = str(uuid.uuid4())
    await _insert_message(db, user_msg_id, session_id, "user", question, None, q_emb)

    answer_parts: list[str] = []
    collected_sources: list[dict] = []
    done_yielded = False

    try:
        async for chunk in rag_engine.ask_stream(valid_doc_ids, question, history, llm_config):
            if chunk["type"] == "sources":
                collected_sources = chunk.get("sources", [])
                yield {
                    "type": "sources",
                    "sources": chunk["sources"],
                    "filtered_sources": chunk["filtered_sources"],
                    "session_id": session_id,
                }
            elif chunk["type"] == "thinking":
                yield {"type": "thinking", "step": chunk.get("step", ""), "detail": chunk.get("detail", "")}
            elif chunk["type"] == "token":
                answer_parts.append(chunk["content"])
                yield {"type": "token", "content": chunk["content"]}
            elif chunk["type"] == "answer":
                answer_parts.clear()
                answer_parts.append(chunk["content"])
                yield {"type": "answer", "content": chunk["content"]}
            elif chunk["type"] == "answer_refined":
                answer_parts.clear()
                answer_parts.append(chunk["content"])
                yield {"type": "answer_refined", "content": chunk["content"]}
    except GeneratorExit:
        full_answer = "".join(answer_parts)
        if full_answer:
            sources_json = json.dumps(collected_sources, ensure_ascii=False)
            a_emb = await _embed_text(full_answer)
            await _insert_message(
                db, str(uuid.uuid4()), session_id, "assistant", full_answer,
                sources_json, a_emb,
            )
        done_yielded = True
        return
    finally:
        if not done_yielded:
            full_answer = "".join(answer_parts)
            if full_answer:
                sources_json = json.dumps(collected_sources, ensure_ascii=False)
                a_emb = await _embed_text(full_answer)
                await _insert_message(
                    db, str(uuid.uuid4()), session_id, "assistant", full_answer,
                    sources_json, a_emb,
                )
            done_yielded = True
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


async def search_messages(
    db: AsyncSession,
    user: User,
    query: str,
    session_id: str | None = None,
    top_k: int = 10,
) -> list[dict]:
    """Semantic search across user's chat messages using pgvector cosine similarity.

    Returns list of {message_id, session_id, role, content, similarity, created_at}.
    Searches across all sessions (or a single session if session_id is given),
    filtered to the current user's sessions via JOIN.
    """
    if not query or not query.strip():
        return []

    q_emb = await _embed_text(query)
    if q_emb is None:
        return []

    try:
        bind = db.get_bind()
        if bind and bind.dialect.name != "postgresql":
            return []
    except Exception:
        pass

    q_emb_str = "[" + ",".join(str(v) for v in q_emb) + "]"
    top_k = max(1, min(top_k, 50))

    if session_id:
        sql = text("""
            SELECT m.id, m.session_id, m.role, m.content, m.created_at,
                   1 - (m.embedding <=> CAST(:q_emb AS vector)) AS similarity
            FROM messages m
            JOIN chat_sessions s ON s.id = m.session_id
            WHERE m.session_id = :session_id
              AND m.embedding IS NOT NULL
              AND s.user_id = :user_id
            ORDER BY m.embedding <=> CAST(:q_emb AS vector)
            LIMIT :top_k
        """)
        params = {
            "q_emb": q_emb_str,
            "session_id": session_id,
            "user_id": user.id,
            "top_k": top_k,
        }
    else:
        sql = text("""
            SELECT m.id, m.session_id, m.role, m.content, m.created_at,
                   1 - (m.embedding <=> CAST(:q_emb AS vector)) AS similarity
            FROM messages m
            JOIN chat_sessions s ON s.id = m.session_id
            WHERE m.embedding IS NOT NULL
              AND s.user_id = :user_id
            ORDER BY m.embedding <=> CAST(:q_emb AS vector)
            LIMIT :top_k
        """)
        params = {
            "q_emb": q_emb_str,
            "user_id": user.id,
            "top_k": top_k,
        }

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "message_id": row.id,
            "session_id": row.session_id,
            "role": row.role,
            "content": row.content,
            "similarity": round(float(row.similarity), 4),
            "created_at": str(row.created_at),
        }
        for row in rows
    ]


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
    """Return (session_id, is_new). Creates a new session if session_id is None, validates ownership if provided."""
    is_new = False
    if not session_id:
        session_id = str(uuid.uuid4())
        new_session = ChatSession(id=session_id, user_id=user_id, title=question[:50])
        db.add(new_session)
        await db.commit()
        is_new = True
    else:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundError("会话不存在")
    return session_id, is_new


async def _get_history(db: AsyncSession, session_id: str) -> list:
    """Fetch message history for a session as list of {role, content} dicts."""
    msg_result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    msgs = msg_result.scalars().all()
    return [{"role": m.role, "content": m.content} for m in msgs]
