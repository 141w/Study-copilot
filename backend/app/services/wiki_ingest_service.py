"""阶段五 5.2：从文档摄入 Wiki 概念页（单用户简化版）。

对齐 WeKnora wiki_ingest 的产物契约（概念页 JSON），去掉分布式锁/claim；
同 slug 采用「合并摘要 + 追加来源段落」的读-改-写。
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentChunk, Note, User, WikiPage
from app.exceptions import ValidationError
from app.services.wiki_service import normalize_slug

logger = logging.getLogger(__name__)

MAX_SOURCE_CHARS = 12000
MAX_PAGES_PER_RUN = 12

_INGEST_PROMPT = """你是知识整理助手。请从下面的学习资料中提炼概念页，写成可点的 Wiki。

资料标题：{title}
资料正文：
{content}

{existing_section}
要求：
1. 提炼 3~{max_pages} 个**核心概念**（不要流水账、不要整章照搬）
2. 每个概念给出 slug（小写英文或中文，可用 - 连接）、title、summary（1 句）、content（Markdown，80~400 字）
3. content 里若提到其他已提炼概念，用 [[slug]] 互相链接
4. **若资料涉及下方已有概念，优先复用其 slug，不要另造中英文两套**
5. 只输出 JSON 数组，不要解释：
[{{"slug":"...","title":"...","summary":"...","content":"..."}}]
"""


def _parse_pages(raw: str | None) -> list[dict[str, Any]]:
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
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        slug = normalize_slug(str(item.get("slug") or ""))
        title = str(item.get("title") or "").strip()
        if not slug or not title:
            continue
        out.append(
            {
                "slug": slug,
                "title": title[:200],
                "summary": str(item.get("summary") or "")[:500],
                "content": str(item.get("content") or "")[:20000],
            }
        )
        if len(out) >= MAX_PAGES_PER_RUN:
            break
    return out


async def _gather_document_text(db: AsyncSession, user: User, doc_id: str) -> tuple[str, str]:
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
        raise ValidationError(f"文档不存在: {doc_id}")
    rows = (
        await db.execute(
            select(DocumentChunk.content)
            .where(DocumentChunk.document_id == doc_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(30)
        )
    ).all()
    text = "\n".join(r[0] or "" for r in rows)[:MAX_SOURCE_CHARS]
    return doc.filename or doc_id, text


async def _gather_note_text(db: AsyncSession, user: User, note_id: str) -> tuple[str, str]:
    note = (
        await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    ).scalar_one_or_none()
    if not note:
        raise ValidationError(f"笔记不存在: {note_id}")
    return note.title or note_id, (note.content or "")[:MAX_SOURCE_CHARS]


async def _list_existing_slugs(db: AsyncSession, user: User) -> str:
    """已有 slug + title 清单，注入提示词，要求模型优先复用（F5）。"""
    rows = (
        await db.execute(
            select(WikiPage.slug, WikiPage.title)
            .where(WikiPage.user_id == user.id)
            .order_by(WikiPage.updated_at.desc())
            .limit(80)
        )
    ).all()
    if not rows:
        return "已有概念页：（无）\n"
    lines = "\n".join(f"- {s}  （{t}）" for s, t in rows)
    return f"已有概念页（优先复用 slug，避免同概念拆成中英文两页）：\n{lines}\n"


async def _merge_or_create(
    db: AsyncSession, user: User, page: dict[str, Any], source_title: str
) -> dict[str, Any]:
    """同 slug：合并 summary + 追加来源段落，并写版本快照；否则新建。"""
    from app.services.wiki_service import MAX_CONTENT

    existing = (
        await db.execute(
            select(WikiPage).where(WikiPage.user_id == user.id, WikiPage.slug == page["slug"])
        )
    ).scalar_one_or_none()
    snippet = (page["content"] or "")[:800]
    if existing:
        body = existing.content or ""
        if snippet and snippet not in body:
            new_body = f"{body.rstrip()}\n\n---\n\n## 来源摘录（{source_title}）\n\n{snippet}"
            if len(new_body) > MAX_CONTENT:
                raise ValidationError(
                    f"合并后内容过长（{len(new_body)} > {MAX_CONTENT}），已跳过"
                )
            # F5：先写被取代版本的快照，再改内容、抬 revision
            from app.db import WikiPageRevision

            db.add(
                WikiPageRevision(
                    id=str(uuid.uuid4()),
                    page_id=existing.id,
                    revision=existing.revision or 1,
                    title=existing.title,
                    content=body,
                    summary=existing.summary or "",
                )
            )
            existing.content = new_body
            existing.revision = (existing.revision or 1) + 1
        if page["summary"] and not existing.summary:
            existing.summary = page["summary"]
        await db.commit()
        await db.refresh(existing)
        return {
            "id": existing.id,
            "slug": existing.slug,
            "title": existing.title,
            "action": "merged",
        }

    p = WikiPage(
        id=str(uuid.uuid4()),
        user_id=user.id,
        slug=page["slug"],
        title=page["title"],
        page_type="concept",
        status="published",
        content=page["content"],
        summary=page["summary"],
        revision=1,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {"id": p.id, "slug": p.slug, "title": p.title, "action": "created"}


async def ingest_from_sources(
    db: AsyncSession,
    user: User,
    *,
    document_ids: list[str] | None = None,
    note_ids: list[str] | None = None,
    max_pages: int = 8,
) -> dict[str, Any]:
    """从文档/笔记摄入概念页。单次 LLM 调用 / 每个源。"""
    if not document_ids and not note_ids:
        raise ValidationError("请选择文档或笔记")
    max_pages = max(3, min(int(max_pages or 8), MAX_PAGES_PER_RUN))

    sources: list[tuple[str, str]] = []
    for did in document_ids or []:
        sources.append(await _gather_document_text(db, user, did))
    for nid in note_ids or []:
        sources.append(await _gather_note_text(db, user, nid))

    from app.core.llm import LLM
    from app.services.config_service import get_llm_config_with_secret

    user_config = await get_llm_config_with_secret(db, user)
    llm = LLM.from_config(user_config)
    existing_section = await _list_existing_slugs(db, user)

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for title, text in sources:
        if not text.strip():
            errors.append(f"{title}: 内容为空")
            continue
        prompt = _INGEST_PROMPT.format(
            title=title[:200],
            content=text,
            max_pages=max_pages,
            existing_section=existing_section,
        )
        try:
            raw = await llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.3, max_tokens=3000
            )
        except Exception as exc:
            logger.warning("wiki ingest LLM failed for %s: %s", title, exc)
            errors.append(f"{title}: {exc}")
            continue
        pages = _parse_pages(raw)
        for page in pages:
            try:
                results.append(await _merge_or_create(db, user, page, source_title=title))
            except Exception as exc:
                await db.rollback()
                logger.warning("wiki merge failed %s: %s", page.get("slug"), exc)
                errors.append(f"{page.get('slug')}: {exc}")

    return {
        "pages": results,
        "created": sum(1 for r in results if r["action"] == "created"),
        "merged": sum(1 for r in results if r["action"] == "merged"),
        "errors": errors,
    }
