"""P0-B favorites service: type allowlist + thin CRUD (WeKnora user_resource_favorite 精神）。

F8：INSERT ON CONFLICT DO NOTHING、删除幂等、列表 join 标题、文档删除清收藏。
`message` 从白名单移除（死枚举：前端消息操作栏无星标入口）。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, UserFavorite
from app.exceptions import ValidationError
from app.utils.timefmt import isoformat_utc

logger = logging.getLogger(__name__)

# F8：message 为死枚举，移除
ALLOWED_TYPES = {"document", "note"}


def _validate_type(resource_type: str) -> str:
    t = (resource_type or "").strip().lower()
    if t not in ALLOWED_TYPES:
        raise ValidationError(f"不支持的收藏类型: {resource_type}")
    return t


def _fav_to_dict(f: UserFavorite, title: str | None = None) -> dict[str, Any]:
    return {
        "id": f.id,
        "resource_type": f.resource_type,
        "resource_id": f.resource_id,
        "title": title,
        "created_at": isoformat_utc(f.created_at) if f.created_at else None,
    }


async def _resolve_titles(
    db: AsyncSession, user: User, rows: list[UserFavorite]
) -> dict[str, str]:
    """resource_id → 标题（document/note）。"""
    doc_ids = [r.resource_id for r in rows if r.resource_type == "document"]
    note_ids = [r.resource_id for r in rows if r.resource_type == "note"]
    titles: dict[str, str] = {}
    if doc_ids:
        from app.db import Document

        res = await db.execute(
            select(Document.id, Document.filename).where(
                Document.id.in_(doc_ids), Document.user_id == user.id
            )
        )
        for i, name in res.all():
            titles[i] = name or ""
    if note_ids:
        from app.db import Note

        res = await db.execute(
            select(Note.id, Note.title).where(
                Note.id.in_(note_ids), Note.user_id == user.id
            )
        )
        for i, name in res.all():
            titles[i] = name or ""
    return titles


async def list_favorites(
    db: AsyncSession,
    user: User,
    resource_type: str | None = None,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    q = select(UserFavorite).where(UserFavorite.user_id == user.id)
    if resource_type:
        q = q.where(UserFavorite.resource_type == _validate_type(resource_type))
    q = q.order_by(UserFavorite.created_at.desc()).limit(max(1, min(limit, 200))).offset(
        max(0, offset)
    )
    rows = list((await db.execute(q)).scalars().all())
    titles = await _resolve_titles(db, user, rows)
    return [_fav_to_dict(r, titles.get(r.resource_id)) for r in rows]


async def add_favorite(
    db: AsyncSession,
    user: User,
    resource_type: str,
    resource_id: str,
) -> dict[str, Any]:
    t = _validate_type(resource_type)
    rid = (resource_id or "").strip()
    if not rid:
        raise ValidationError("resource_id 不能为空")

    # F8：先取既有行（幂等），没有再插；并发撞唯一约束则再取一次
    existing = (
        await db.execute(
            select(UserFavorite).where(
                UserFavorite.user_id == user.id,
                UserFavorite.resource_type == t,
                UserFavorite.resource_id == rid,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return _fav_to_dict(existing)

    fav = UserFavorite(
        id=str(uuid.uuid4()),
        user_id=user.id,
        resource_type=t,
        resource_id=rid,
    )
    db.add(fav)
    try:
        await db.commit()
    except Exception:
        # 并发双击撞唯一约束：回滚后取既有行，不 500
        await db.rollback()
        existing = (
            await db.execute(
                select(UserFavorite).where(
                    UserFavorite.user_id == user.id,
                    UserFavorite.resource_type == t,
                    UserFavorite.resource_id == rid,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return _fav_to_dict(existing)
        raise
    await db.refresh(fav)
    return _fav_to_dict(fav)


async def remove_favorite(
    db: AsyncSession,
    user: User,
    resource_type: str,
    resource_id: str,
) -> None:
    """幂等删除：不存在也返回成功（双击/重复请求不报错）。"""
    t = _validate_type(resource_type)
    rid = (resource_id or "").strip()
    await db.execute(
        delete(UserFavorite).where(
            UserFavorite.user_id == user.id,
            UserFavorite.resource_type == t,
            UserFavorite.resource_id == rid,
        )
    )
    await db.commit()


async def clear_favorites_for_resource(
    db: AsyncSession, user_id: str, resource_type: str, resource_id: str
) -> None:
    """资源被删除时清理收藏行（防孤儿）。"""
    await db.execute(
        delete(UserFavorite).where(
            UserFavorite.user_id == user_id,
            UserFavorite.resource_type == resource_type,
            UserFavorite.resource_id == resource_id,
        )
    )
    await db.commit()
