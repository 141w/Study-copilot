"""Metrics endpoint — operational stats for Prometheus-style scrapes.

No external metrics library (zero-new-dep); returns JSON.
Per-status task counts give immediate operational visibility; extend
with request-count/latency histograms once a prometheus-client dep
is acceptable (pure gains, no API break).
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncTask, get_db

router = APIRouter()

_STARTED_AT = datetime.now(UTC)


@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Operational snapshot: app info + task breakdown by status."""
    now = datetime.now(UTC)
    uptime_sec = round((now - _STARTED_AT).total_seconds(), 1)

    rows = (
        await db.execute(
            select(AsyncTask.status, func.count(AsyncTask.id).label("cnt")).group_by(
                AsyncTask.status
            )
        )
    ).all()

    counts = {row.status: row.cnt for row in rows}
    total = sum(counts.values())

    return {
        "app": {
            "name": "Study Copilot",
            "uptime_seconds": uptime_sec,
            "started_at": _STARTED_AT.isoformat(),
        },
        "tasks": {
            "total": total,
            "by_status": counts,
            "pending": counts.get("pending", 0),
            "running": counts.get("running", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "cancelled": counts.get("cancelled", 0),
        },
    }
