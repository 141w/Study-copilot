"""Token Usage API router for Study Copilot."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import TokenUsage, User, get_db
from app.services.usage_service import get_usage_dashboard, sync_classroom_usage

router = APIRouter(prefix="/usage", tags=["Token用量看板"])


@router.get("")
@router.get("/dashboard")
async def get_dashboard(
    days: int = Query(30, ge=0, le=365, description="统计天数，0为全部"),
    source: str = Query("all", description="来源过滤: all | chat | classroom | agent | quiz 等"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取用户 Token 消耗仪表盘数据，包含汇总指标、时间序列、多模态分布、模型用量及最近记录。"""
    return await get_usage_dashboard(
        db=db,
        user_id=current_user.id,
        days=days if days > 0 else None,
        source=source if source != "all" else None,
        auto_sync=True,
    )


@router.post("/sync")
async def trigger_sync(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """手动触发从 OpenMAIC classroom/data/usage 同步课堂生成消耗记录。"""
    synced = await sync_classroom_usage(db=db, user_id=current_user.id)
    return {
        "status": "success",
        "synced_count": synced,
        "message": f"成功同步 {synced} 条课堂用量记录",
    }


@router.get("/records")
async def get_records(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source: str | None = Query(None),
    kind: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """分页获取用量流水明细。"""
    conditions = [TokenUsage.user_id == current_user.id]
    if source and source != "all":
        conditions.append(TokenUsage.source == source)
    if kind and kind != "all":
        conditions.append(TokenUsage.kind == kind)

    stmt = (
        select(TokenUsage)
        .where(*conditions)
        .order_by(desc(TokenUsage.created_at))
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()

    return {
        "items": [r.to_dict() for r in records],
        "limit": limit,
        "offset": offset,
    }
