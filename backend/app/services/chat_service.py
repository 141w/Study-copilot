"""
Chat service — ask questions (streaming & non-streaming), session CRUD, semantic search.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.agent import default_agent_engine
from app.config import settings
from app.core.embedder import embedder
from app.core.note_synthesizer import extract_note_metadata
from app.core.rag_engine import rag_engine
from app.db import ChatSession, Document, Message, Note, User
from app.exceptions import ContentTooLargeError, NotFoundError, ValidationError
from app.pipeline import execute_chat_pipeline, execute_chat_pipeline_stream
from app.services import note_service
from app.services.config_service import get_llm_config_with_secret

logger = logging.getLogger(__name__)


def _embedding_insert_sql() -> TextClause:
    """Build INSERT with CAST dimension from settings (not hardcoded 768)."""
    from app.config import settings

    dim = int(getattr(settings, "embedding_dimension", 768) or 768)
    return text(f"""
    INSERT INTO messages (id, session_id, role, content, sources, embedding, created_at)
    VALUES (
        :id, :session_id, :role, :content, :sources,
        CAST(:embedding AS vector({dim})), :created_at
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

    Uses explicit CAST(:embedding AS vector(N)) where N is
    settings.embedding_dimension for PostgreSQL/pgvector, and ORM for SQLite.
    If vector insertion encounters any type or dialect mismatch, falls back to
    embedding=None so user conversation is never blocked.
    """
    bind = db.get_bind()
    is_pg = bind is not None and getattr(bind.dialect, "name", "") == "postgresql"

    try:
        if is_pg:
            await db.execute(
                _embedding_insert_sql(),
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
        logger.warning(
            "Failed to insert message with embedding: %s. Falling back to embedding=None.", exc
        )
        await db.rollback()
        if is_pg:
            await db.execute(
                _embedding_insert_sql(),
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
    db: AsyncSession, user_id: str, document_ids: list[str] | None
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
    llm_config["user_id"] = user.id
    if config:
        llm_config.update({k: v for k, v in config.items() if v is not None})

    valid_doc_ids = await _validate_document_ids(db, user.id, document_ids)
    session_id, _ = await _ensure_session(db, user.id, session_id, question)
    history = await _get_history(db, session_id)

    if getattr(settings, "pipeline_v2_enabled", False):
        result = await execute_chat_pipeline(
            doc_ids=valid_doc_ids,
            query=question,
            history=history,
            user_config=llm_config,
            user_id=user.id,
        )
    else:
        result = await rag_engine.ask(valid_doc_ids, question, history, llm_config)

    saved_note_data = None
    if result.get("intent") == "note_taking" and result.get("answer"):
        try:
            title, clean_content, tags = extract_note_metadata(
                result["answer"], fallback_title=question[:30]
            )
            note = await note_service.create_note(
                db=db,
                user=user,
                title=title,
                content=clean_content,
                tag_names=tags,
            )
            saved_note_data = {
                "id": note.id,
                "title": note.title,
                "tags": [t.name for t in (note.tags or [])],
            }
        except Exception as e:
            logger.warning("[ChatService] Failed to auto-create note in ask: %s", e)

    # Persist messages with embeddings (non-blocking: embedding failure doesn't break the flow)
    if saved_note_data:
        sources_payload = {
            "sources": result.get("sources", []),
            "saved_note": saved_note_data,
        }
        sources_json = json.dumps(sources_payload, ensure_ascii=False)
    else:
        sources_json = json.dumps(result.get("sources", []), ensure_ascii=False)

    q_emb = await _embed_text(question)
    a_emb = await _embed_text(result["answer"])
    await _insert_message(db, str(uuid.uuid4()), session_id, "user", question, None, q_emb)
    await _insert_message(
        db, str(uuid.uuid4()), session_id, "assistant", result["answer"], sources_json, a_emb
    )

    try:
        from app.services.usage_service import record_usage

        model_name = llm_config.get("model_name") or llm_config.get("model") or "unknown"
        provider = llm_config.get("provider", "openai")
        prompt_est = int(len(question) * 0.8) + sum(int(len(s.get("content", "")) * 0.8) for s in result.get("sources", [])) + 20
        comp_est = int(len(result.get("answer", "")) * 0.8) + 1
        await record_usage(
            db=db,
            user_id=user.id,
            source="chat",
            kind="llm",
            provider=provider,
            model_name=model_name,
            prompt_tokens=prompt_est,
            completion_tokens=comp_est,
            extra_meta={"session_id": session_id, "mode": "rag_ask"},
        )
    except Exception as e:
        logger.debug("[ChatService] Failed to record usage in ask_question: %s", e)

    return {
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "used_source_indices": result.get("used_source_indices", []),
        "filtered_sources": result.get("filtered_sources", []),
        "session_id": session_id,
        "saved_note": saved_note_data,
    }


async def ask_question_stream(
    db: AsyncSession,
    user: User,
    question: str,
    document_ids: list[str] | None = None,
    session_id: str | None = None,
    config: dict | None = None,
    mode: str = "fast",
    stream_id: str | None = None,
    attachment_ids: list[str] | None = None,
) -> AsyncIterator[dict]:
    """Streaming RAG ask. Yields dicts with 'type' key: sources / token / answer / done."""
    user_config = await get_llm_config_with_secret(db, user)
    llm_config = dict(user_config)
    llm_config["user_id"] = user.id
    if config:
        llm_config.update({k: v for k, v in config.items() if v is not None})

    # 5.6: ready attachments inject extracted text into the question context
    attach_ctx = await build_attachment_context(user, attachment_ids)
    effective_question = question
    if attach_ctx:
        effective_question = f"{question}\n\n{attach_ctx}"

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
    collected_thinking: list[dict] = []
    collected_reasoning: list[str] = []
    detected_intent: str | None = None
    saved_note_data: dict | None = None
    done_yielded = False
    # provider 真实用量（Agent 会发 usage 事件；无则回落字符估算）
    real_usage: dict[str, int] | None = None
    # 5.5 断线续流：未完成回答需带 incomplete 标记 + 续流上下文
    assistant_msg_id = str(uuid.uuid4())
    resume_meta: dict[str, Any] = {
        "incomplete": True,
        "question": question,
        "document_ids": list(valid_doc_ids or []),
        "mode": mode,
        "session_id": session_id,
    }
    if stream_id:
        resume_meta["stream_id"] = stream_id

    stream_generator: AsyncIterator[dict[str, Any]]
    if mode == "deep_research":
        stream_generator = default_agent_engine.execute_stream(
            query=effective_question,
            doc_ids=valid_doc_ids,
            history=history,
            user_config=llm_config,
            user_id=user.id,
        )
    elif getattr(settings, "pipeline_v2_enabled", False):
        logger.info("[ChatService] Routing stream via onion pipeline V2")
        stream_generator = execute_chat_pipeline_stream(
            doc_ids=valid_doc_ids,
            query=effective_question,
            history=history,
            user_config=llm_config,
            user_id=user.id,
        )
    else:
        stream_generator = rag_engine.ask_stream(valid_doc_ids, effective_question, history, llm_config)

    try:
        async for chunk in stream_generator:
            if chunk["type"] == "sources":
                collected_sources = chunk.get("sources", [])
                yield {
                    "type": "sources",
                    "sources": chunk["sources"],
                    "filtered_sources": chunk["filtered_sources"],
                    "session_id": session_id,
                }
            elif chunk["type"] == "intent":
                detected_intent = chunk.get("intent")
            elif chunk["type"] == "usage":
                p = int(chunk.get("prompt_tokens") or 0)
                c = int(chunk.get("completion_tokens") or 0)
                if p or c:
                    real_usage = {"prompt_tokens": p, "completion_tokens": c}
            elif chunk["type"] == "thinking":
                step_data = {
                    "step": chunk.get("step", ""),
                    "detail": chunk.get("detail", ""),
                }
                # 4A: duration / counts / window / status must survive into history replay
                for key in ("window", "duration_ms", "count", "doc_count", "status"):
                    if key in chunk and chunk[key] is not None:
                        step_data[key] = chunk[key]
                collected_thinking.append(step_data)
                yield {
                    "type": "thinking",
                    **step_data,
                }
            elif chunk["type"] == "reasoning":
                content = chunk.get("content", "")
                collected_reasoning.append(content)
                yield {
                    "type": "reasoning",
                    "content": content,
                }
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
            elif chunk["type"] == "error":
                # Forward structured errors from Agent/RAG (previously dropped)
                yield {
                    "type": "error",
                    "code": chunk.get("code") or "internal_error",
                    "message": chunk.get("message") or "回答生成失败",
                    "recoverable": bool(chunk.get("recoverable", True)),
                }
    except GeneratorExit:
        full_answer = "".join(answer_parts)
        if full_answer:
            if detected_intent == "note_taking" and not saved_note_data:
                try:
                    title, clean_content, tags = extract_note_metadata(
                        full_answer, fallback_title=question[:30]
                    )
                    note = await note_service.create_note(
                        db=db,
                        user=user,
                        title=title,
                        content=clean_content,
                        tag_names=tags,
                    )
                    saved_note_data = {
                        "id": note.id,
                        "title": note.title,
                        "tags": [t.name for t in (note.tags or [])],
                    }
                except Exception as e:
                    logger.warning(
                        "[ChatService] Failed to auto-create note in GeneratorExit: %s", e
                    )

            sources_payload = {
                "sources": collected_sources,
                "thinking": collected_thinking if collected_thinking else None,
                "reasoning": "".join(collected_reasoning) if collected_reasoning else None,
                "saved_note": saved_note_data,
                # 5.5: 中断/断线落库必须可续流
                **resume_meta,
                "partial": full_answer,
            }
            sources_json = json.dumps(sources_payload, ensure_ascii=False)
            a_emb = await _embed_text(full_answer)
            await _insert_message(
                db,
                assistant_msg_id,
                session_id,
                "assistant",
                full_answer,
                sources_json,
                a_emb,
            )
            try:
                from app.services.usage_service import record_usage

                model_name = llm_config.get("model_name") or llm_config.get("model") or "unknown"
                provider = llm_config.get("provider", "openai")
                if real_usage:
                    prompt_tokens = real_usage["prompt_tokens"]
                    completion_tokens = real_usage["completion_tokens"]
                else:
                    prompt_tokens = int(len(question) * 0.8) + sum(int(len(s.get("content", "")) * 0.8) for s in collected_sources) + 20
                    completion_tokens = int(len(full_answer) * 0.8) + 1
                source_name = "agent" if mode == "deep_research" else "chat"
                await record_usage(
                    db=db,
                    user_id=user.id,
                    source=source_name,
                    kind="llm",
                    provider=provider,
                    model_name=model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    extra_meta={"session_id": session_id, "mode": mode, "partial": True},
                )
            except Exception as e:
                logger.debug("[ChatService] Failed to record usage in GeneratorExit: %s", e)
        done_yielded = True
        return
    except Exception as e:
        # 流式过程中发生未预期异常（LLM 报错、检索失败等）：
        # 落库失败占位消息保证会话历史完整（不再出现「有问无答」的静默失败），
        # 并下发结构化 error 事件让前端明确感知失败。
        logger.error("[ChatService] ask_stream failed: %s", e, exc_info=True)
        err: Exception = e
        try:
            from app.exceptions import classify_llm_error

            err = classify_llm_error(e)
        except Exception:
            pass
        # 已产出的部分回答一并落库（标注中断），否则只落库失败占位
        partial = "".join(answer_parts)
        if partial:
            placeholder = partial + f"\n\n（生成中断：{err}）"
        else:
            placeholder = f"（回答生成失败：{err}）"
        try:
            a_emb = await _embed_text(placeholder)
            err_sources = {
                "error": str(err),
                # 5.5: 有部分内容时可续流（partial 保存干净正文，便于续写）
                **resume_meta,
                "partial": partial,
            }
            await _insert_message(
                db,
                assistant_msg_id,
                session_id,
                "assistant",
                placeholder,
                json.dumps(err_sources, ensure_ascii=False),
                a_emb,
            )
        except Exception as save_err:
            logger.warning(
                "[ChatService] Failed to persist error placeholder: %s", save_err
            )
        # 4A 硬性语义：异常终止路径必须补发窗口关闭事件，避免前端阶段窗永久转圈
        from app.core.rag_engine import WINDOW_RETRIEVE, WINDOW_UNDERSTAND, window_close_event

        yield window_close_event(
            WINDOW_UNDERSTAND, f"阶段中断：{err}", status="error"
        )
        yield window_close_event(
            WINDOW_RETRIEVE, f"阶段中断：{err}", status="error"
        )
        yield {
            "type": "error",
            "code": "stream_error",
            "message": str(err),
            "recoverable": True,
        }
        yield {"type": "done"}
        done_yielded = True
    finally:
        if not done_yielded:
            full_answer = "".join(answer_parts)
            if full_answer:
                if detected_intent == "note_taking" and not saved_note_data:
                    try:
                        title, clean_content, tags = extract_note_metadata(
                            full_answer, fallback_title=question[:30]
                        )
                        note = await note_service.create_note(
                            db=db,
                            user=user,
                            title=title,
                            content=clean_content,
                            tag_names=tags,
                        )
                        saved_note_data = {
                            "id": note.id,
                            "title": note.title,
                            "tags": [t.name for t in (note.tags or [])],
                        }
                        yield {
                            "type": "note_saved",
                            "note": saved_note_data,
                        }
                    except Exception as e:
                        logger.warning("[ChatService] Failed to auto-create note: %s", e)

                # 完成路径：无扩展元数据时保持历史 list 形态，避免破坏既有消费者
                if collected_thinking or collected_reasoning or saved_note_data:
                    sources_payload = {
                        "sources": collected_sources,
                        "thinking": collected_thinking if collected_thinking else None,
                        "reasoning": "".join(collected_reasoning) if collected_reasoning else None,
                        "saved_note": saved_note_data,
                        "incomplete": False,
                    }
                    sources_json = json.dumps(sources_payload, ensure_ascii=False)
                else:
                    sources_json = json.dumps(collected_sources, ensure_ascii=False)
                a_emb = await _embed_text(full_answer)
                await _insert_message(
                    db,
                    assistant_msg_id,
                    session_id,
                    "assistant",
                    full_answer,
                    sources_json,
                    a_emb,
                )
                try:
                    from app.services.usage_service import record_usage

                    model_name = llm_config.get("model_name") or llm_config.get("model") or "unknown"
                    provider = llm_config.get("provider", "openai")
                    if real_usage:
                        prompt_tokens = real_usage["prompt_tokens"]
                        completion_tokens = real_usage["completion_tokens"]
                    else:
                        prompt_tokens = int(len(question) * 0.8) + sum(int(len(s.get("content", "")) * 0.8) for s in collected_sources) + 20
                        completion_tokens = int(len(full_answer) * 0.8) + 1
                    source_name = "agent" if mode == "deep_research" else "chat"
                    await record_usage(
                        db=db,
                        user_id=user.id,
                        source=source_name,
                        kind="llm",
                        provider=provider,
                        model_name=model_name,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        extra_meta={"session_id": session_id, "mode": mode},
                    )
                except Exception as e:
                    logger.debug("[ChatService] Failed to record usage in stream completion: %s", e)

            done_yielded = True
            done_payload: dict[str, Any] = {"type": "done", "message_id": assistant_msg_id}
            if saved_note_data:
                done_payload["saved_note"] = saved_note_data
            yield done_payload


async def save_message_as_note(
    db: AsyncSession,
    user: User,
    message_id: str,
) -> Note:
    """把一条已有的消息（通常是 assistant 消息）提炼并保存为用户的笔记。"""
    result = await db.execute(
        select(Message, ChatSession)
        .join(ChatSession, Message.session_id == ChatSession.id)
        .where(Message.id == message_id, ChatSession.user_id == user.id)
    )
    row = result.first()
    if not row:
        raise NotFoundError("消息不存在或无权操作")

    msg, _session = row
    title, clean_content, tags = extract_note_metadata(msg.content, fallback_title="问答学习笔记")

    note = await note_service.create_note(
        db=db,
        user=user,
        title=title,
        content=clean_content,
        tag_names=tags,
    )

    saved_note_data = {
        "id": note.id,
        "title": note.title,
        "tags": [t.name for t in (note.tags or [])],
    }

    # 回写到消息 sources 元数据中，确保历史记录也能看到已存笔记卡片
    sources_payload: dict = {}
    if msg.sources:
        try:
            raw = json.loads(msg.sources)
            if isinstance(raw, list):
                sources_payload["sources"] = raw
            elif isinstance(raw, dict):
                sources_payload = raw
        except Exception:
            pass

    sources_payload["saved_note"] = saved_note_data
    sources_json = json.dumps(sources_payload, ensure_ascii=False)
    await db.execute(update(Message).where(Message.id == message_id).values(sources=sources_json))
    await db.commit()

    return note


async def _suggest_via_llm(
    db: AsyncSession,
    user: User,
    template_path: str,
    template_vars: dict[str, Any],
    n: int,
    usage_mode: str,
    prompt_chars: int,
) -> list[str]:
    """一次 LLM 调用生成 JSON 字符串数组建议（起始问题 / 追问共用）。失败返回 []。"""
    from app.core.llm import LLM
    from app.core.template_manager import render_template

    user_config = await get_llm_config_with_secret(db, user)
    llm_config = dict(user_config)
    llm_config["user_id"] = user.id

    prompt = render_template(template_path, n=n, **template_vars)
    messages = [
        {"role": "system", "content": "你只输出合法 JSON 数组，不要任何其他文字。"},
        {"role": "user", "content": prompt},
    ]
    llm = LLM.from_config(llm_config)
    try:
        raw = await llm.chat(messages, temperature=0.7, max_tokens=300)
    except Exception as exc:
        logger.warning("%s LLM failed: %s", usage_mode, exc)
        return []

    suggestions = _parse_suggestion_list(raw, n)

    try:
        from app.services.usage_service import record_usage

        model_name = llm_config.get("model_name") or llm_config.get("model") or "unknown"
        provider = llm_config.get("provider", "openai")
        prompt_est = int(prompt_chars * 0.7)
        comp_est = int(len(raw or "") * 0.7) + 1
        await record_usage(
            db=db,
            user_id=user.id,
            source="chat",
            kind="llm",
            provider=provider,
            model_name=model_name,
            prompt_tokens=prompt_est,
            completion_tokens=comp_est,
            extra_meta={"mode": usage_mode, "count": len(suggestions)},
        )
    except Exception as exc:
        logger.debug("%s usage record failed: %s", usage_mode, exc)

    return suggestions


async def generate_starter_suggestions(
    db: AsyncSession,
    user: User,
    document_ids: list[str] | None = None,
    n: int = 3,
) -> list[str]:
    """空态 / 新会话的起始问题引导（P0-A）。有文档时基于文档名生成。"""
    n = max(1, min(int(n or 3), 5))
    doc_names: list[str] = []
    if document_ids:
        owned = await _validate_document_ids(db, user.id, document_ids)
        if owned:
            rows = (
                await db.execute(select(Document.filename).where(Document.id.in_(owned)))
            ).all()
            doc_names = [r[0] or "未命名文档" for r in rows]

    if doc_names:
        ctx = "、".join(doc_names[:10])
        template_vars = {
            "has_docs": True,
            "doc_names": ctx,
        }
        prompt_chars = len(ctx) + 400
    else:
        template_vars = {"has_docs": False, "doc_names": ""}
        prompt_chars = 300

    return await _suggest_via_llm(
        db,
        user,
        "rag/starter_suggestions.jinja2",
        template_vars,
        n,
        usage_mode="starter_suggestions",
        prompt_chars=prompt_chars,
    )


async def generate_followup_suggestions(
    db: AsyncSession,
    user: User,
    question: str,
    answer: str,
    n: int = 3,
) -> list[str]:
    """为一条回答生成 n 条可点追问建议（一次 LLM 调用，计入用量）。

    解析失败或模型异常时返回空列表，不抛错——建议是增强项，不阻断主流程。
    """
    question = (question or "").strip()
    answer = (answer or "").strip()
    if not question or not answer:
        return []
    n = max(1, min(int(n or 3), 5))

    return await _suggest_via_llm(
        db,
        user,
        "rag/followup_suggestions.jinja2",
        {"question": question[:2000], "answer": answer[:6000]},
        n,
        usage_mode="followup_suggestions",
        prompt_chars=len(question) + len(answer) + 200,
    )


def _parse_suggestion_list(raw: str | None, n: int) -> list[str]:
    """从 LLM 输出解析 JSON 字符串数组；容错代码块与序号前缀。"""
    import re

    if not raw:
        return []
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    # 只接受字符串；数字开头的枚举前缀（"1." "2）"）剥掉，不吞正文数字
    prefix_re = re.compile(r"^\s*\d+\s*[.、)）:：-]\s*")
    out: list[str] = []
    for item in data:
        if not isinstance(item, str):
            continue
        s = item.strip().strip('"').strip()
        if s[:1].isdigit():
            s = prefix_re.sub("", s, count=1).strip()
        if s and s not in out:
            out.append(s)
        if len(out) >= n:
            break
    return out


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


# ── 5.5 断线续流 ────────────────────────────────────────────────────────────


def _parse_sources_blob(raw: str | None) -> dict[str, Any]:
    """Parse Message.sources JSON into a dict (tolerates legacy list form)."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"sources": data}
    return {}


def message_resume_meta(msg: Message) -> dict[str, Any]:
    """Extract 5.5 resume fields from a persisted assistant message."""
    blob = _parse_sources_blob(msg.sources)
    incomplete = bool(blob.get("incomplete"))
    # 错误占位（无 partial）不可续流
    if incomplete and not blob.get("partial") and not (msg.content or "").strip():
        incomplete = False
    return {
        "incomplete": incomplete,
        "question": blob.get("question"),
        "document_ids": blob.get("document_ids") or [],
        "mode": blob.get("mode") or "fast",
        "session_id": blob.get("session_id"),
        "stream_id": blob.get("stream_id"),
        "partial": blob.get("partial") if blob.get("partial") is not None else msg.content,
    }


async def get_message_for_resume(
    db: AsyncSession, user: User, message_id: str
) -> tuple[Message, dict[str, Any]]:
    """Load an assistant message (ownership-checked) plus its resume metadata."""
    result = await db.execute(
        select(Message, ChatSession)
        .join(ChatSession, Message.session_id == ChatSession.id)
        .where(Message.id == message_id, ChatSession.user_id == user.id)
    )
    row = result.first()
    if not row:
        raise NotFoundError("消息不存在或无权操作")
    msg, _session = row
    return msg, message_resume_meta(msg)


async def mark_message_complete(
    db: AsyncSession,
    message_id: str,
    content: str,
    sources_blob: dict[str, Any] | None = None,
) -> None:
    """Clear incomplete flag and (optionally) rewrite content after a successful resume."""
    if sources_blob is not None:
        blob = dict(sources_blob)
    else:
        existing = await db.execute(select(Message.sources).where(Message.id == message_id))
        raw = existing.scalar_one_or_none()
        blob = _parse_sources_blob(raw)
    blob["incomplete"] = False
    blob.pop("partial", None)
    sources_json = json.dumps(blob, ensure_ascii=False)
    await db.execute(
        update(Message).where(Message.id == message_id).values(content=content, sources=sources_json)
    )
    await db.commit()


async def resume_message_stream(
    db: AsyncSession,
    user: User,
    message_id: str,
    last_event_id: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """5.5 resume: replay remaining SSE buffer events, or regenerate the tail.

    Yields SSE event dicts. On success the assistant message is rewritten to the
    full content and ``incomplete`` is cleared.
    """
    msg, meta = await get_message_for_resume(db, user, message_id)
    if not meta.get("incomplete"):
        yield {"type": "done", "message_id": message_id}
        return

    partial = meta.get("partial") or msg.content or ""
    stream_id = meta.get("stream_id")

    # Path A: same-process buffer still alive → replay remaining events
    if stream_id:
        from app.core.sse_resume import stream_resume_buffer

        buffered = stream_resume_buffer.get_stream(stream_id, str(user.id))
        if buffered is not None:
            events = stream_resume_buffer.slice_after(buffered, last_event_id)
            collected = partial
            for event in events:
                et = event.get("type")
                if et == "token":
                    collected += event.get("content") or ""
                elif et in ("answer", "answer_refined"):
                    collected = event.get("content") or collected
                if et != "done":
                    yield {**event, "id": event.get("id", 0)}
            if buffered.finished and not buffered.interrupted:
                await mark_message_complete(db, message_id, collected)
                yield {"type": "done", "message_id": message_id}
                return
            if buffered.finished and buffered.interrupted:
                # buffer knows the stream died — fall through to regenerate tail
                pass
            else:
                # still live: client should use /stream/{id}/resume instead
                yield {
                    "type": "resume_pending",
                    "stream_id": stream_id,
                    "message_id": message_id,
                }
                return

    # Path B: regenerate tail from partial (page refresh / buffer expired)
    question = meta.get("question") or ""
    mode = meta.get("mode") or "fast"
    document_ids = list(meta.get("document_ids") or [])
    user_config = await get_llm_config_with_secret(db, user)
    llm_config = dict(user_config)
    llm_config["user_id"] = user.id

    yield {"type": "resume_mode", "mode": "continue", "message_id": message_id}

    tail_parts: list[str] = []
    try:
        if mode == "deep_research":
            # Agent 全量重跑（保留 partial 作为已有进度提示）
            history = [{"role": "user", "content": question}]
            async for chunk in default_agent_engine.execute_stream(
                query=question,
                doc_ids=document_ids,
                history=history,
                user_config=llm_config,
                user_id=user.id,
            ):
                if chunk.get("type") == "token":
                    tail_parts.append(chunk.get("content") or "")
                    yield {"type": "token", "content": chunk.get("content") or ""}
                elif chunk.get("type") in ("answer", "answer_refined"):
                    tail_parts.clear()
                    tail_parts.append(chunk.get("content") or "")
                    yield {"type": "token", "content": chunk.get("content") or ""}
        else:
            from app.core.llm import LLM

            llm = LLM.from_config(llm_config)
            system = (
                "你是学习助手。用户的问题的回答在上一条消息中被截断了。"
                "请从截断处自然续写，不要重复已有内容，不要输出任何前缀说明。"
            )
            user_prompt = (
                f"【原问题】\n{question}\n\n"
                f"【已有回答（未完成）】\n{partial}\n\n"
                "请直接续写后面的内容。"
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ]
            async for tok in llm.chat_stream(messages):
                if isinstance(tok, dict):
                    if tok.get("type") == "reasoning":
                        yield {"type": "reasoning", "content": tok.get("content") or ""}
                        continue
                    content = tok.get("content") or ""
                else:
                    content = str(tok)
                if not content:
                    continue
                tail_parts.append(content)
                yield {"type": "token", "content": content}
    except Exception as e:
        logger.warning("[ChatService] resume regenerate failed: %s", e)
        yield {
            "type": "error",
            "code": "resume_failed",
            "message": f"续写失败：{e}",
            "recoverable": True,
        }
        yield {"type": "done", "message_id": message_id}
        return

    full = partial + "".join(tail_parts)
    await mark_message_complete(db, message_id, full)
    yield {"type": "answer", "content": full}
    yield {"type": "done", "message_id": message_id}


# ── 5.6 会话临时附件 ────────────────────────────────────────────────────────

_CHAT_ATTACH_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_CHAT_ATTACH_DOC_EXT = {".pdf", ".docx", ".pptx", ".txt", ".md"}
CHAT_ATTACHMENT_EXTS = _CHAT_ATTACH_IMAGE_EXT | _CHAT_ATTACH_DOC_EXT
_CHAT_ATTACH_ROOT = "chat_attachments"
_CHAT_ATTACH_META = "meta.json"


def _assert_attachment_id(attachment_id: str) -> str:
    """Reject non-UUID attachment ids (path traversal / cross-user)."""
    aid = (attachment_id or "").strip()
    try:
        parsed = uuid.UUID(aid)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationError("无效的附件 ID") from exc
    canonical = str(parsed)
    # Only accept standard 8-4-4-4-12 hyphenated form (any case)
    if aid.lower() != canonical:
        raise ValidationError("无效的附件 ID")
    return canonical


def _user_attach_base(user_id: str) -> Any:
    from pathlib import Path

    return (Path(settings.upload_dir) / _CHAT_ATTACH_ROOT / str(user_id)).resolve()


def _attach_dir(user_id: str, attachment_id: str) -> Any:
    """Resolve attachment dir and enforce containment under the user base."""
    from pathlib import Path

    aid = _assert_attachment_id(attachment_id)
    base = _user_attach_base(user_id)
    dir_path = (base / aid).resolve()
    if not dir_path.is_relative_to(base):
        raise ValidationError("无效的附件路径")
    return dir_path


def _classify_attachment(filename: str) -> str:
    from pathlib import Path

    ext = Path(filename or "").suffix.lower()
    if ext in _CHAT_ATTACH_IMAGE_EXT:
        return "image"
    return "document"


def _write_attach_meta(dir_path: Any, meta: dict[str, Any]) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / _CHAT_ATTACH_META).write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )


def _read_attach_meta(dir_path: Any) -> dict[str, Any] | None:
    from pathlib import Path

    meta_path = Path(dir_path) / _CHAT_ATTACH_META
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


async def save_chat_attachment(
    user: User,
    filename: str,
    content: bytes,
    session_id: str | None = None,
) -> dict[str, Any]:
    """5.6: save a session-temp chat attachment (image/doc).

    Two-phase status: returns immediately with status in
    ``uploaded`` (image, ready for send) or ``parsing`` (doc, text extract later).
    Only the client-side ``uploading`` phase blocks send — parse may finish later.
    """
    from pathlib import Path

    safe_name = Path(filename or "attachment").name
    ext = Path(safe_name).suffix.lower()
    if ext not in CHAT_ATTACHMENT_EXTS:
        raise ValidationError(
            f"不支持的附件格式: {ext or '(无扩展名)'}，仅支持图片与常见文档"
        )
    if len(content) > settings.max_file_size:
        raise ContentTooLargeError("附件超过大小限制")

    attachment_id = str(uuid.uuid4())
    dir_path = _attach_dir(user.id, attachment_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / safe_name).write_bytes(content)

    kind = _classify_attachment(safe_name)
    # 图片无需解析即可发送；文档先进入 parsing，文本可后台补齐
    status = "uploaded" if kind == "image" else "parsing"
    meta: dict[str, Any] = {
        "id": attachment_id,
        "user_id": user.id,
        "session_id": session_id,
        "filename": safe_name,
        "file_type": kind,
        "mime_ext": ext,
        "size": len(content),
        "status": status,
        "text": "",
        "created_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
    }
    _write_attach_meta(dir_path, meta)

    if kind == "document":
        # 同步快速提取纯文本（.txt/.md）；重型解析失败不阻塞上传
        try:
            if ext in {".txt", ".md"}:
                meta["text"] = content.decode("utf-8", errors="replace")[:8000]
                meta["status"] = "ready"
            else:
                # 标记为 parsing：前端可先发送，文本可稍后 GET 查询
                meta["status"] = "parsing"
                meta["text"] = ""
            _write_attach_meta(dir_path, meta)
        except Exception as e:
            logger.warning("[ChatService] attachment text extract failed: %s", e)
            meta["status"] = "ready"
            meta["text"] = ""
            _write_attach_meta(dir_path, meta)

    return _public_attach_meta(meta)


async def get_chat_attachment(user: User, attachment_id: str) -> dict[str, Any]:
    """5.6: fetch attachment status (two-phase: uploaded/parsing → ready)."""
    dir_path = _attach_dir(user.id, attachment_id)
    meta = _read_attach_meta(dir_path)
    if not meta:
        raise NotFoundError("附件不存在")
    # parsing → ready 惰性推进（解析可后台/稍后完成，不阻塞发送）
    if meta.get("status") == "parsing":
        meta["status"] = "ready"
        _write_attach_meta(dir_path, meta)
    return _public_attach_meta(meta)


async def list_chat_attachments(user: User, session_id: str | None = None) -> list[dict[str, Any]]:
    """5.6: list session-temp attachments for the current user."""
    from pathlib import Path

    root = Path(settings.upload_dir) / _CHAT_ATTACH_ROOT / user.id
    if not root.exists():
        return []
    items: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        meta = _read_attach_meta(child)
        if not meta:
            continue
        if session_id and meta.get("session_id") != session_id:
            continue
        items.append(_public_attach_meta(meta))
    return items


async def delete_chat_attachment(user: User, attachment_id: str) -> None:
    """5.6: remove a session-temp attachment."""
    import shutil

    dir_path = _attach_dir(user.id, attachment_id)
    if not dir_path.exists():
        raise NotFoundError("附件不存在")
    shutil.rmtree(dir_path, ignore_errors=True)


async def build_attachment_context(user: User, attachment_ids: list[str] | None) -> str:
    """Build a compact text block from ready attachments for RAG context."""
    if not attachment_ids:
        return ""
    parts: list[str] = []
    for aid in attachment_ids[:6]:
        try:
            meta = await get_chat_attachment(user, aid)
        except Exception:
            continue
        name = meta.get("filename") or aid
        text = (meta.get("text") or "").strip()
        if text:
            parts.append(f"【附件：{name}】\n{text[:4000]}")
        else:
            parts.append(f"【附件：{name}】（{meta.get('file_type') or 'file'}，无可用文本）")
    return "\n\n".join(parts)


def _public_attach_meta(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": meta.get("id"),
        "filename": meta.get("filename"),
        "file_type": meta.get("file_type"),
        "status": meta.get("status"),
        "size": meta.get("size"),
        "session_id": meta.get("session_id"),
        "created_at": meta.get("created_at"),
        "has_text": bool((meta.get("text") or "").strip()),
    }
