"""阶段二：文档标签（含自动打标）。

契约对齐 WeKnora `knowledge_auto_tag.go`（只读参照）：
- 只从用户已有标签池挑，**不新建、不覆盖人工标签**
- 候选按序号而非 UUID 传给 LLM（省 token）
- 置信度阈值过滤（默认 0.75）
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, Tag, User
from app.exceptions import NotFoundError, ValidationError
from app.services.note_service import _get_or_create_tag

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 200
MAX_CONTENT_RUNES = 8000
MIN_CONFIDENCE = 0.75

_AUTO_TAG_PROMPT = """你是文档标签匹配器。从下面的「已有标签」中为文档挑选最贴切的若干个标签。

规则：
1. **只能**从已有标签里选，禁止发明新标签
2. 输出 JSON 对象：{{"tags": [{{"idx": 0, "confidence": 0.9}}], "reason": "简述"}}
3. confidence 为 0~1；低于 {min_conf} 的不要输出
4. 最多选 {max_tags} 个；宁缺毋滥

已有标签（idx: 名称）：
{candidates}

文档标题：{title}
文档内容节选：
{content}
"""


def _doc_content_preview(db_rows: Any) -> str:
    parts = [str(r[0] or "") for r in db_rows]
    text = "\n".join(parts)
    return text[:MAX_CONTENT_RUNES]


async def _owned_document(db: AsyncSession, user: User, doc_id: str) -> Document:
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.user_id == user.id,
                Document.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档不存在")
    return doc


async def list_document_tag_names(db: AsyncSession, user: User, doc_id: str) -> list[str]:
    await _owned_document(db, user, doc_id)
    from app.db.database import Tag as TagModel
    from app.db.database import document_tags as dt

    result = await db.execute(
        select(TagModel.name)
        .select_from(TagModel)
        .join(dt, dt.c.tag_id == TagModel.id)
        .where(dt.c.document_id == doc_id, TagModel.user_id == user.id)
        .order_by(TagModel.name)
    )
    return [r[0] for r in result.all()]


async def set_document_tags(
    db: AsyncSession, user: User, doc_id: str, tag_names: list[str]
) -> list[str]:
    """整集覆盖文档标签（人工编辑入口）。自动打标请用 add_document_tags。"""
    doc = await _owned_document(db, user, doc_id)
    # 清空现有关联
    await db.execute(delete(document_tags_table()).where(document_tags_table().c.document_id == doc.id))
    names: list[str] = []
    seen: set[str] = set()
    for raw in tag_names or []:
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        tag = await _get_or_create_tag(db, user.id, name)
        await db.execute(
            document_tags_table().insert().values(document_id=doc.id, tag_id=tag.id)
        )
        names.append(tag.name)
    await db.commit()
    return sorted(set(names))


async def add_document_tags(
    db: AsyncSession, user: User, doc_id: str, tag_names: list[str]
) -> list[str]:
    """增量关联标签（自动打标用：不删人工标签）。"""
    doc = await _owned_document(db, user, doc_id)
    existing = set(await list_document_tag_names(db, user, doc_id))
    added: list[str] = []
    for raw in tag_names or []:
        name = (raw or "").strip()
        if not name or name in existing:
            continue
        tag = await _get_or_create_tag(db, user.id, name)
        await db.execute(
            document_tags_table().insert().values(document_id=doc.id, tag_id=tag.id)
        )
        existing.add(name)
        added.append(name)
    await db.commit()
    return added


def document_tags_table():
    from app.db.database import document_tags

    return document_tags


async def batch_add_tags(
    db: AsyncSession, user: User, doc_ids: list[str], tag_names: list[str]
) -> dict[str, list[str]]:
    """批量增量打标；单篇失败不影响其他。"""
    out: dict[str, list[str]] = {}
    for did in doc_ids:
        try:
            out[did] = await add_document_tags(db, user, did, tag_names)
        except (NotFoundError, ValidationError):
            out[did] = []
        except Exception as exc:
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass
            logger.warning("batch tag %s failed: %s", did, exc)
            out[did] = []
    return out


def _parse_auto_tag_response(raw: str | None, valid_names: list[str]) -> list[tuple[str, float]]:
    """解析 LLM 输出的 {"tags":[{"idx":N,"confidence":C}]}，映射回标签名。"""
    if not raw:
        return []
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except Exception:
        return []
    items = data.get("tags") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    out: list[tuple[str, float]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            raw_conf = it.get("confidence")
            conf = 1.0 if raw_conf is None else float(raw_conf)
        except (TypeError, ValueError):
            continue
        if conf > 1:  # 兼容 0-100 量纲
            conf = conf / 100.0
        raw_name = it.get("name") or it.get("tag")
        if isinstance(raw_name, str) and raw_name.strip() in valid_names:
            name = raw_name.strip()
        else:
            raw_idx = it.get("idx")
            if raw_idx is None:
                continue
            try:
                idx = int(raw_idx)
            except (TypeError, ValueError):
                continue
            if not (0 <= idx < len(valid_names)):
                logger.debug("auto_tag: idx out of range=%s", raw_idx)
                continue
            name = valid_names[idx]
        if conf >= MIN_CONFIDENCE and all(n != name for n, _ in out):
            out.append((name, conf))
    return out


async def auto_tag_document(
    db: AsyncSession,
    user: User,
    doc_id: str,
    max_tags: int = 5,
) -> list[str]:
    """从用户已有标签池为文档自动匹配标签（只增不覆盖）。标签池为空则返回 []。"""
    doc = await _owned_document(db, user, doc_id)
    tag_rows = (
        await db.execute(select(Tag).where(Tag.user_id == user.id).order_by(Tag.name))
    ).scalars().all()
    if not tag_rows:
        return []
    candidates = [(t.id, t.name) for t in tag_rows[:MAX_CANDIDATES]]
    valid_names = [n for _, n in candidates]
    candidate_text = "\n".join(f"{i}: {n}" for i, n in enumerate(valid_names))

    from app.db.database import DocumentChunk

    content_rows = (
        await db.execute(
            select(DocumentChunk.content)
            .where(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index)
            .limit(20)
        )
    ).all()
    content = _doc_content_preview(content_rows)

    from app.core.llm import LLM
    from app.services.config_service import get_llm_config_with_secret

    user_config = await get_llm_config_with_secret(db, user)
    llm = LLM.from_config(user_config)
    prompt = _AUTO_TAG_PROMPT.format(
        min_conf=MIN_CONFIDENCE,
        max_tags=max_tags,
        candidates=candidate_text,
        title=doc.filename or "",
        content=content or "（无正文）",
    )
    try:
        raw = await llm.chat(
            [{"role": "user", "content": prompt}], temperature=0.1, max_tokens=400
        )
    except Exception as exc:
        logger.warning("auto_tag LLM failed for %s: %s", doc_id, exc)
        return []

    picked = sorted(
        _parse_auto_tag_response(raw, valid_names), key=lambda x: x[1], reverse=True
    )[:max_tags]
    names = [n for n, _ in picked]
    return await add_document_tags(db, user, doc_id, names)


async def batch_auto_tag(
    db: AsyncSession, user: User, doc_ids: list[str], max_tags: int = 5
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for did in doc_ids:
        try:
            out[did] = await auto_tag_document(db, user, did, max_tags=max_tags)
        except (NotFoundError, ValidationError):
            out[did] = []
        except Exception as exc:
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass
            logger.warning("batch auto-tag %s failed: %s", did, exc)
            out[did] = []
    return out
