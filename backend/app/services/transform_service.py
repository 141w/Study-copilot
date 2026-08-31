"""
Transformation service — orchestrates LLM-based content transformations.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.llm import LLM
from app.core.transformations import (
    TRANSFORMATIONS,
    get_transformation,
    list_transformations,
)
from app.db import Document, Note, User, UserLLMConfig
from app.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.services.config_service import get_llm_config_with_secret

logger = logging.getLogger(__name__)


async def _build_llm(db: AsyncSession, user: User) -> LLM:
    """Build an LLM instance from the user's configuration."""
    cfg = await get_llm_config_with_secret(db, user)
    return LLM.from_config(cfg)


async def transform_content(
    db: AsyncSession,
    user: User,
    source_text: str,
    transform_type: str,
    source_title: str = "",
) -> dict:
    """
    Execute a content transformation using the LLM.

    Parameters
    ----------
    db : AsyncSession
    user : User
    source_text : str — text to transform
    transform_type : str — one of the registered transformation keys
    source_title : str — optional title for context

    Returns
    -------
    dict with keys: transform_type, result, source_title
    """
    t = get_transformation(transform_type)
    if not t:
        valid = ", ".join(TRANSFORMATIONS.keys())
        raise ValidationError(f"未知的转换类型: {transform_type}。可用类型: {valid}")

    if not source_text.strip():
        raise ValidationError("源文本内容为空")

    # Truncate very long inputs to avoid context overflow
    max_input = 12000
    if len(source_text) > max_input:
        source_text = source_text[:max_input] + "\n\n[内容已截断...]"

    # Build LLM from user config
    llm = await _build_llm(db, user)

    system_prompt = t.system_prompt
    user_prompt = t.user_prompt_template.format(text=source_text)

    try:
        logger.info(
            "Running transformation '%s' for user %s (text len=%d)",
            transform_type,
            user.id,
            len(source_text),
        )
        result = await llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=t.temperature,
            max_tokens=t.max_tokens,
        )
    except Exception as e:
        logger.error("Transformation failed: %s", e, exc_info=True)
        raise ExternalServiceError(f"AI 转换失败: {str(e)}")

    return {
        "transform_type": transform_type,
        "transform_name": t.name,
        "result": result or "",
        "source_title": str(source_title),
    }


async def transform_note(
    db: AsyncSession,
    user: User,
    note_id: str,
    transform_type: str,
) -> dict:
    """
    Transform an existing note by its ID.

    Returns dict with keys: transform_type, result, source_title, note_id
    """
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.id == note_id, Note.user_id == user.id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise NotFoundError("笔记不存在")

    title_str = str(note.title) if note.title else ""
    content_str = str(note.content) if note.content else ""
    source_text = f"# {title_str}\n\n{content_str}" if title_str else content_str

    out = await transform_content(
        db=db,
        user=user,
        source_text=source_text,
        transform_type=transform_type,
        source_title=title_str,
    )
    out["note_id"] = note_id
    return out


async def transform_document_chunks(
    db: AsyncSession,
    user: User,
    doc_id: str,
    transform_type: str,
) -> dict:
    """
    Transform a document's text chunks.

    Returns dict with keys: transform_type, result, source_title, document_id
    """
    from app.core.vector_store import DocumentVectorStore

    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档不存在")

    # Get chunks from vector store
    store = DocumentVectorStore(doc_id)
    await store.load()

    chunks = store._store.chunks if store._store.chunks else []
    if not chunks:
        raise ValidationError("文档内容为空")

    # Combine chunks (limit to avoid context overflow)
    combined = "\n\n".join(c.get("text", "") for c in chunks[:30] if c.get("text"))

    filename = str(doc.filename) if doc.filename else ""

    out = await transform_content(
        db=db,
        user=user,
        source_text=combined,
        transform_type=transform_type,
        source_title=filename,
    )
    out["document_id"] = doc_id
    return out
