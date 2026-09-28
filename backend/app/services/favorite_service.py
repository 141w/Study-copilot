"""P0-B favorites service: type allowlist + thin CRUD (WeKnora user_resource_favorite 精神)。"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, UserFavorite
from app.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"document", "note", "message"}


def _validate_type(resource_type: str) -> str:
    t = (resource_type or "").strip().lower()
    if t not in ALLOWED_TYPES:
        raise ValidationError(f"不支持的收藏类型: {resource_type}")
    return t


def _fav_to_dict(f: UserFavorite) -> dict[str, Any]:
    return {
        "id": f.id,
        "resource_type": f.resource_type,
        "resource_id": f.resource_id,
        "created_at": str(f.created_at) if f.created_at else None,
    }


async def list_favorites(
    db: AsyncSession,
    user: User,
    resource_type: str | None = None,
) -> list[dict[str, Any]]:
    q = select(UserFavorite).where(UserFavorite.user_id == user.id)
    if resource_type:
        q = q.where(UserFavorite.resource_type == _validate_type(resource_type))
    q = q.order_by(UserFavorite.created_at.desc())
    rows = (await db.execute(q)).scalars().all()
    return [_fav_to_dict(r) for r in rows]


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
    await db.commit()
    await db.refresh(fav)
    return _fav_to_dict(fav)


async def remove_favorite(
    db: AsyncSession,
    user: User,
    resource_type: str,
    resource_id: str,
) -> None:
    t = _validate_type(resource_type)
    rid = (resource_id or "").strip()
    result = await db.execute(
        delete(UserFavorite).where(
            UserFavorite.user_id == user.id,
            UserFavorite.resource_type == t,
            UserFavorite.resource_id == rid,
        )
    )
    await db.commit()
    deleted = getattr(result, "rowcount", 0) or 0
    if not deleted:
        raise NotFoundError("收藏不存在")
