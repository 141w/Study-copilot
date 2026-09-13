"""
Token usage tracking and dashboard service.
Records token and modality usage across Chat, Classroom, Agent, and other tasks.
Provides aggregation for the ProfileView Token Usage Dashboard.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import TokenUsage, User, _utcnow_naive

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "chat": "AI 问答与对话",
    "classroom": "AI 互动课堂生成",
    "agent": "ReAct 深度研究",
    "quiz": "测验与巩固生成",
    "transform": "内容转换与总结",
    "note": "笔记归纳生成",
}

KIND_LABELS = {
    "llm": "大语言模型 (Tokens)",
    "image": "课件插图生成 (张)",
    "tts": "语音合成 (字符)",
    "asr": "语音识别 (秒)",
}


async def record_usage(
    db: AsyncSession,
    user_id: str,
    source: str = "chat",
    kind: str = "llm",
    provider: str = "openai",
    model_name: str = "unknown",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int | None = None,
    quantity: int = 0,
    unit: str = "token",
    extra_meta: dict[str, Any] | None = None,
    created_at: datetime | None = None,
) -> TokenUsage | None:
    """非阻塞记录一条用量流水。"""
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens

    try:
        usage = TokenUsage(
            id=str(uuid.uuid4()),
            user_id=user_id,
            created_at=created_at or _utcnow_naive(),
            source=source,
            kind=kind,
            provider=provider,
            model_name=model_name or "unknown",
            prompt_tokens=max(0, prompt_tokens),
            completion_tokens=max(0, completion_tokens),
            total_tokens=max(0, total_tokens),
            quantity=max(0, quantity),
            unit=unit,
            extra_meta=extra_meta or {},
        )
        db.add(usage)
        await db.commit()
        await db.refresh(usage)
        return usage
    except Exception as e:
        logger.warning("[UsageService] Failed to record token usage: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        return None


def _find_openmaic_usage_files() -> list[str]:
    """定位 OpenMAIC 的 data/usage/*.jsonl 文件。"""
    candidates = [
        Path(__file__).parent.parent.parent.parent / "classroom" / "data" / "usage",
        Path("classroom/data/usage"),
        Path("../classroom/data/usage"),
    ]
    files: list[str] = []
    for c in candidates:
        if c.exists() and c.is_dir():
            matched = glob.glob(str(c / "*.jsonl"))
            files.extend(matched)
    return sorted(set(files))


async def sync_classroom_usage(db: AsyncSession, user_id: str) -> int:
    """从 OpenMAIC 的 classroom/data/usage/*.jsonl 同步课堂生成用量。

    依据 extra_meta->'openmaic_id' 幂等去重，返回新增同步行数。
    """
    files = _find_openmaic_usage_files()
    if not files:
        logger.debug("[UsageService] No OpenMAIC usage files found.")
        return 0

    # 1. 查询当前用户已导入的 openmaic_id 集合
    res = await db.execute(
        select(TokenUsage.extra_meta).where(
            TokenUsage.user_id == user_id,
            TokenUsage.source == "classroom",
        )
    )
    imported_ids: set[str] = set()
    for (meta,) in res.all():
        if isinstance(meta, dict) and "openmaic_id" in meta:
            imported_ids.add(str(meta["openmaic_id"]))

    new_items: list[TokenUsage] = []
    for fpath in files:
        try:
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    rec_id = str(record.get("id", ""))
                    if not rec_id or rec_id in imported_ids:
                        continue

                    # 提取基础字段
                    kind = record.get("kind", "llm")
                    provider = record.get("providerId", "openai")
                    model_id = record.get("modelId") or record.get("modelString") or "unknown"
                    in_tokens = int(record.get("inputTokens", 0))
                    out_tokens = int(record.get("outputTokens", 0))
                    tot_tokens = in_tokens + out_tokens
                    qty = int(record.get("quantity", 0))
                    unit = record.get("unit", "token" if kind == "llm" else "item")

                    created_ts = record.get("createdAt")
                    if created_ts and isinstance(created_ts, (int, float)):
                        created_dt = datetime.fromtimestamp(created_ts / 1000.0, UTC).replace(tzinfo=None)
                    else:
                        created_dt = _utcnow_naive()

                    item = TokenUsage(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        created_at=created_dt,
                        source="classroom",
                        kind=kind,
                        provider=provider,
                        model_name=model_id,
                        prompt_tokens=in_tokens,
                        completion_tokens=out_tokens,
                        total_tokens=tot_tokens,
                        quantity=qty,
                        unit=unit,
                        extra_meta={
                            "openmaic_id": rec_id,
                            "openmaic_source": record.get("source", "classroom"),
                        },
                    )
                    new_items.append(item)
                    imported_ids.add(rec_id)
        except Exception as e:
            logger.warning("[UsageService] Failed to read usage file %s: %s", fpath, e)

    if new_items:
        try:
            db.add_all(new_items)
            await db.commit()
            logger.info("[UsageService] Synced %d OpenMAIC usage records for user %s", len(new_items), user_id)
        except Exception as e:
            logger.error("[UsageService] Failed to commit synced records: %s", e)
            await db.rollback()
            return 0

    return len(new_items)


async def get_usage_dashboard(
    db: AsyncSession,
    user_id: str,
    days: int | None = 30,
    source: str | None = None,
    auto_sync: bool = True,
) -> dict[str, Any]:
    """获取个人中心 Token 消耗综合看板数据。"""
    if auto_sync:
        try:
            await sync_classroom_usage(db, user_id)
        except Exception as e:
            logger.debug("[UsageService] Auto-sync failed (non-blocking): %s", e)

    # 1. 基础条件（总览统计必须覆盖全量来源，确保全局累计、课堂与问答资产指标始终真实可信）
    base_conditions = [TokenUsage.user_id == user_id]
    if days and days > 0:
        cutoff = _utcnow_naive() - timedelta(days=days)
        base_conditions.append(TokenUsage.created_at >= cutoff)

    # 2. 查询明细记录（全量拉取，保障分项与汇总一致性）
    query = (
        select(TokenUsage)
        .where(*base_conditions)
        .order_by(desc(TokenUsage.created_at))
    )
    res = await db.execute(query)
    records = res.scalars().all()

    # 3. 统计汇总
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    chat_tokens = 0
    classroom_tokens = 0
    other_tokens = 0
    total_requests = len(records)

    by_source_map: dict[str, dict[str, Any]] = {}
    by_kind_map: dict[str, dict[str, Any]] = {}
    by_model_map: dict[str, dict[str, Any]] = {}
    by_day_map: dict[str, dict[str, Any]] = {}

    # 3.0 初始化连续时间序列槽位，确保时间轴完整展开（而非孤立单点）
    today = _utcnow_naive().date()
    if days and days > 0:
        start_date = today - timedelta(days=days - 1)
        end_date = today
    elif records:
        earliest_rec_date = min(r.created_at.date() for r in records)
        start_date = min(earliest_rec_date, today - timedelta(days=6))
        end_date = today
    else:
        start_date = today - timedelta(days=6)
        end_date = today

    cur_d = start_date
    while cur_d <= end_date:
        d_str = cur_d.strftime("%Y-%m-%d")
        by_day_map[d_str] = {
            "date": d_str,
            "total_tokens": 0,
            "chat_tokens": 0,
            "classroom_tokens": 0,
            "other_tokens": 0,
            "requests": 0,
            "chat_requests": 0,
            "classroom_requests": 0,
            "other_requests": 0,
        }
        cur_d += timedelta(days=1)

    for r in records:
        total_tokens += r.total_tokens
        prompt_tokens += r.prompt_tokens
        completion_tokens += r.completion_tokens

        # 按来源分类累计
        if r.source == "chat":
            chat_tokens += r.total_tokens
        elif r.source == "classroom":
            classroom_tokens += r.total_tokens
        else:
            other_tokens += r.total_tokens

        # By Source
        src_key = r.source or "other"
        if src_key not in by_source_map:
            by_source_map[src_key] = {
                "source": src_key,
                "label": SOURCE_LABELS.get(src_key, src_key),
                "tokens": 0,
                "requests": 0,
            }
        by_source_map[src_key]["tokens"] += r.total_tokens
        by_source_map[src_key]["requests"] += 1

        # By Kind
        kind_key = r.kind or "llm"
        if kind_key not in by_kind_map:
            by_kind_map[kind_key] = {
                "kind": kind_key,
                "label": KIND_LABELS.get(kind_key, kind_key),
                "tokens": 0,
                "quantity": 0,
                "unit": r.unit or "token",
                "requests": 0,
            }
        by_kind_map[kind_key]["tokens"] += r.total_tokens
        by_kind_map[kind_key]["quantity"] += r.quantity
        by_kind_map[kind_key]["requests"] += 1

        # By Model
        model_key = r.model_name or "unknown"
        if model_key not in by_model_map:
            by_model_map[model_key] = {
                "model_name": model_key,
                "provider": r.provider or "openai",
                "kind": r.kind or "llm",
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "quantity": 0,
                "unit": r.unit or "token",
            }
        by_model_map[model_key]["requests"] += 1
        by_model_map[model_key]["prompt_tokens"] += r.prompt_tokens
        by_model_map[model_key]["completion_tokens"] += r.completion_tokens
        by_model_map[model_key]["total_tokens"] += r.total_tokens
        by_model_map[model_key]["quantity"] += r.quantity

        # By Day
        day_str = r.created_at.strftime("%Y-%m-%d")
        if day_str not in by_day_map:
            by_day_map[day_str] = {
                "date": day_str,
                "total_tokens": 0,
                "chat_tokens": 0,
                "classroom_tokens": 0,
                "other_tokens": 0,
                "requests": 0,
                "chat_requests": 0,
                "classroom_requests": 0,
                "other_requests": 0,
            }
        by_day_map[day_str]["total_tokens"] += r.total_tokens
        by_day_map[day_str]["requests"] += 1
        if r.source == "chat":
            by_day_map[day_str]["chat_tokens"] += r.total_tokens
            by_day_map[day_str]["chat_requests"] += 1
        elif r.source == "classroom":
            by_day_map[day_str]["classroom_tokens"] += r.total_tokens
            by_day_map[day_str]["classroom_requests"] += 1
        else:
            by_day_map[day_str]["other_tokens"] += r.total_tokens
            by_day_map[day_str]["other_requests"] += 1

    # 4. 排序整理
    by_source_list = sorted(by_source_map.values(), key=lambda x: x["tokens"], reverse=True)
    by_kind_list = sorted(by_kind_map.values(), key=lambda x: x["tokens"], reverse=True)
    by_model_list = sorted(by_model_map.values(), key=lambda x: x["total_tokens"], reverse=True)
    by_day_list = sorted(by_day_map.values(), key=lambda x: x["date"])

    # 5. 最近 30 条流水（若传入特定来源过滤则展示该来源最近流水，否则展示全平台最近流水）
    filtered_for_recent = [r for r in records if r.source == source] if (source and source not in ("all", "全部")) else records
    recent_records = [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "source": r.source,
            "source_label": SOURCE_LABELS.get(r.source, r.source),
            "kind": r.kind,
            "provider": r.provider,
            "model_name": r.model_name,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "total_tokens": r.total_tokens,
            "quantity": r.quantity,
            "unit": r.unit,
        }
        for r in filtered_for_recent[:30]
    ]

    totals_dict = {
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "chat_tokens": chat_tokens,
        "classroom_tokens": classroom_tokens,
        "other_tokens": other_tokens,
        "requests": total_requests,
    }

    return {
        "totals": totals_dict,
        "summary": totals_dict,
        "by_source": by_source_list,
        "by_kind": by_kind_list,
        "by_model": by_model_list,
        "by_day": by_day_list,
        "daily": by_day_list,
        "recent_records": recent_records,
        "days": days,
        "source_filter": source,
    }
