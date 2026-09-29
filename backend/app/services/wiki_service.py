"""阶段五 5.1：知识 Wiki 概念页服务。

核心约定（对齐 WeKnora wiki 机制，实现自研）：
- slug 用户内唯一、URL 友好；[[slug]] 双向链接
- 内容是 Markdown；链接解析在读取时做，不把 HTML 焊进 content
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, WikiPage, WikiPageRevision
from app.exceptions import ConflictError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

MAX_TITLE = 200
MAX_CONTENT = 200_000
SLUG_RE = re.compile(r"^[a-z0-9一-鿿][a-z0-9_\-/一-鿿]{0,127}$")
LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def normalize_slug(raw: str) -> str:
    s = (raw or "").strip().lower().replace(" ", "-")
    # 保留中英文、数字与 -_/；其余剔除
    s = re.sub(r"[^a-z0-9_\-/一-鿿]", "", s)
    s = re.sub(r"-{2,}", "-", s)
    s = re.sub(r"/{2,}", "/", s)
    return s.strip("-/")[:128]


def extract_links(content: str) -> list[str]:
    """从 Markdown 中抽取 [[slug]] 链接（去重保序）。"""
    out: list[str] = []
    for m in LINK_RE.finditer(content or ""):
        slug = normalize_slug(m.group(1))
        if slug and slug not in out:
            out.append(slug)
    return out


def _page_to_dict(p: WikiPage, *, dead_links: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": p.id,
        "slug": p.slug,
        "title": p.title,
        "page_type": p.page_type,
        "status": p.status,
        "content": p.content,
        "summary": p.summary,
        "revision": p.revision,
        "created_at": str(p.created_at) if p.created_at else None,
        "updated_at": str(p.updated_at) if p.updated_at else None,
        "links": extract_links(p.content or ""),
        "dead_links": dead_links or [],
    }


async def _get_owned(db: AsyncSession, user: User, page_id: str) -> WikiPage:
    p = (
        await db.execute(
            select(WikiPage).where(WikiPage.id == page_id, WikiPage.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not p:
        raise NotFoundError("Wiki 页面不存在")
    return p


async def _slug_exists(db: AsyncSession, user: User, slug: str, exclude_id: str | None = None) -> bool:
    q = select(WikiPage.id).where(WikiPage.user_id == user.id, WikiPage.slug == slug)
    if exclude_id:
        q = q.where(WikiPage.id != exclude_id)
    return (await db.execute(q)).first() is not None


async def list_pages(
    db: AsyncSession,
    user: User,
    q: str | None = None,
    page_type: str | None = None,
) -> list[dict[str, Any]]:
    stmt = select(WikiPage).where(WikiPage.user_id == user.id)
    if page_type:
        stmt = stmt.where(WikiPage.page_type == page_type)
    if q:
        like = f"%{(q or '').strip()}%"
        stmt = stmt.where(or_(WikiPage.title.ilike(like), WikiPage.summary.ilike(like)))
    stmt = stmt.order_by(WikiPage.title)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": p.id,
            "slug": p.slug,
            "title": p.title,
            "page_type": p.page_type,
            "status": p.status,
            "summary": p.summary,
            "updated_at": str(p.updated_at) if p.updated_at else None,
        }
        for p in rows
    ]


async def get_page(db: AsyncSession, user: User, page_id: str) -> dict[str, Any]:
    p = await _get_owned(db, user, page_id)
    links = extract_links(p.content or "")
    dead = await _find_dead_links(db, user, links)
    return _page_to_dict(p, dead_links=dead)


async def get_page_by_slug(db: AsyncSession, user: User, slug: str) -> dict[str, Any]:
    s = normalize_slug(slug)
    p = (
        await db.execute(select(WikiPage).where(WikiPage.user_id == user.id, WikiPage.slug == s))
    ).scalar_one_or_none()
    if not p:
        raise NotFoundError("Wiki 页面不存在")
    return await get_page(db, user, p.id)


async def _find_dead_links(db: AsyncSession, user: User, slugs: list[str]) -> list[str]:
    if not slugs:
        return []
    rows = (
        await db.execute(
            select(WikiPage.slug).where(WikiPage.user_id == user.id, WikiPage.slug.in_(slugs))
        )
    ).all()
    have = {r[0] for r in rows}
    return [s for s in slugs if s not in have]


async def create_page(
    db: AsyncSession,
    user: User,
    *,
    slug: str,
    title: str,
    content: str = "",
    summary: str = "",
    page_type: str = "concept",
    status: str = "published",
) -> dict[str, Any]:
    s = normalize_slug(slug)
    if not s or not SLUG_RE.match(s):
        raise ValidationError("slug 仅允许小写字母、数字、- _ / ，且以字母数字开头")
    title = (title or "").strip()
    if not title:
        raise ValidationError("标题不能为空")
    if len(title) > MAX_TITLE:
        raise ValidationError(f"标题最长 {MAX_TITLE} 字")
    if len(content or "") > MAX_CONTENT:
        raise ValidationError("内容过长")
    if await _slug_exists(db, user, s):
        raise ConflictError(f"slug 已存在: {s}")

    p = WikiPage(
        id=str(uuid.uuid4()),
        user_id=user.id,
        slug=s,
        title=title,
        page_type=page_type if page_type in ("concept", "entity", "summary", "index") else "concept",
        status=status if status in ("draft", "published", "archived") else "published",
        content=content or "",
        summary=(summary or "")[:500],
        revision=1,
    )
    db.add(p)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(f"slug 已存在: {s}") from exc
    await db.refresh(p)
    return await get_page(db, user, p.id)


async def update_page(
    db: AsyncSession,
    user: User,
    page_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
    summary: str | None = None,
    page_type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    p = await _get_owned(db, user, page_id)
    old_title, old_content, old_summary = p.title, p.content, p.summary
    changed = False
    if title is not None:
        title = title.strip()
        if not title:
            raise ValidationError("标题不能为空")
        if len(title) > MAX_TITLE:
            raise ValidationError(f"标题最长 {MAX_TITLE} 字")
        if title != p.title:
            p.title = title
            changed = True
    if content is not None:
        if len(content) > MAX_CONTENT:
            raise ValidationError("内容过长")
        if content != p.content:
            p.content = content
            changed = True
    if summary is not None and summary[:500] != (p.summary or ""):
        p.summary = summary[:500]
        changed = True
    if page_type in ("concept", "entity", "summary", "index"):
        p.page_type = page_type
    if status in ("draft", "published", "archived"):
        p.status = status
    if changed:
        # 先快照被取代的版本（回滚用），再抬 revision
        db.add(
            WikiPageRevision(
                id=str(uuid.uuid4()),
                page_id=p.id,
                revision=p.revision or 1,
                title=old_title,
                content=old_content or "",
                summary=old_summary or "",
            )
        )
        p.revision = (p.revision or 1) + 1
    await db.commit()
    await db.refresh(p)
    return await get_page(db, user, p.id)


async def list_revisions(db: AsyncSession, user: User, page_id: str) -> list[dict[str, Any]]:
    await _get_owned(db, user, page_id)
    rows = (
        await db.execute(
            select(WikiPageRevision)
            .where(WikiPageRevision.page_id == page_id)
            .order_by(WikiPageRevision.revision.desc())
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "revision": r.revision,
            "title": r.title,
            "summary": r.summary,
            "created_at": str(r.created_at) if r.created_at else None,
            "content_preview": (r.content or "")[:120],
        }
        for r in rows
    ]


async def revert_page(
    db: AsyncSession, user: User, page_id: str, revision: int
) -> dict[str, Any]:
    """回滚到历史版本 —— 实现为又一次编辑（可再回滚）。"""
    await _get_owned(db, user, page_id)
    hist = (
        await db.execute(
            select(WikiPageRevision).where(
                WikiPageRevision.page_id == page_id,
                WikiPageRevision.revision == revision,
            )
        )
    ).scalar_one_or_none()
    if not hist:
        raise NotFoundError("版本不存在")
    return await update_page(
        db,
        user,
        page_id,
        title=hist.title,
        content=hist.content,
        summary=hist.summary,
    )


async def delete_page(db: AsyncSession, user: User, page_id: str) -> None:
    p = await _get_owned(db, user, page_id)
    await db.delete(p)
    await db.commit()


async def resolve_links(
    db: AsyncSession, user: User, slugs: list[str]
) -> dict[str, dict[str, Any] | None]:
    """批量解析 slug → 摘要（死链为 None）。"""
    out: dict[str, dict[str, Any] | None] = {s: None for s in slugs}
    if not slugs:
        return out
    rows = (
        await db.execute(
            select(WikiPage).where(WikiPage.user_id == user.id, WikiPage.slug.in_(slugs))
        )
    ).scalars().all()
    for p in rows:
        out[p.slug] = {"id": p.id, "slug": p.slug, "title": p.title, "summary": p.summary}
    return out


async def audit_dead_links(db: AsyncSession, user: User) -> dict[str, Any]:
    """5.3 全局死链巡检：扫全部页面的 [[slug]]，汇总死链与孤页。

    返回：
      pages: [{id, slug, title, dead_links:[slug...]}]  — 仅含有死链的页
      orphan_pages: 没有任何入链的页面 slug
      stats: {pages, links, dead_links, orphan_pages}
    """
    rows = (
        await db.execute(
            select(WikiPage).where(WikiPage.user_id == user.id).order_by(WikiPage.title)
        )
    ).scalars().all()
    all_slugs = {p.slug for p in rows}

    # 收集入链（出链仅用于统计 total_links，无需单独建表）
    in_links: dict[str, set[str]] = {s: set() for s in all_slugs}
    total_links = 0
    dead_by_page: list[dict[str, Any]] = []

    for p in rows:
        links = extract_links(p.content or "")
        total_links += len(links)
        dead = [s for s in links if s not in all_slugs]
        for s in links:
            if s in in_links:
                in_links[s].add(p.slug)
        if dead:
            dead_by_page.append(
                {
                    "id": p.id,
                    "slug": p.slug,
                    "title": p.title,
                    "dead_links": dead,
                }
            )

    # 孤页 = 没有入链（排除自链）
    orphan_pages = []
    for p in rows:
        sources = in_links.get(p.slug, set()) - {p.slug}
        if not sources:
            orphan_pages.append({"id": p.id, "slug": p.slug, "title": p.title})

    dead_total = sum(len(d["dead_links"]) for d in dead_by_page)
    return {
        "pages": dead_by_page,
        "orphan_pages": orphan_pages,
        "stats": {
            "pages": len(rows),
            "links": total_links,
            "dead_links": dead_total,
            "orphan_pages": len(orphan_pages),
        },
    }


async def wiki_index(db: AsyncSession, user: User) -> dict[str, Any]:
    """5.3 索引页数据：按 page_type 分组 + 最近更新，供前端目录展示。"""
    rows = (
        await db.execute(
            select(WikiPage).where(WikiPage.user_id == user.id).order_by(WikiPage.updated_at.desc())
        )
    ).scalars().all()
    by_type: dict[str, list[dict[str, Any]]] = {}
    for p in rows:
        by_type.setdefault(p.page_type or "concept", []).append(
            {
                "id": p.id,
                "slug": p.slug,
                "title": p.title,
                "summary": p.summary,
                "updated_at": str(p.updated_at) if p.updated_at else None,
            }
        )
    return {
        "total": len(rows),
        "by_type": by_type,
        "recent": [
            {
                "id": p.id,
                "slug": p.slug,
                "title": p.title,
                "updated_at": str(p.updated_at) if p.updated_at else None,
            }
            for p in rows[:10]
        ],
    }
