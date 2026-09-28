"""阶段三：解析阶段时间线 recorder（轻量，失败不阻断主流程）。"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import DocumentParseSpan

logger = logging.getLogger(__name__)

# 与 _do_process_document 各阶段一一对应（勿抄 WeKnora 的 5 阶段名）
STAGE_ORDER = ["parse", "profile", "chunk", "embed", "index", "finalize"]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ParseSpanRecorder:
    """按 attempt 记录一次文档处理的阶段 span。出错时只写库，不抛。"""

    def __init__(self, db: AsyncSession, document_id: str, attempt: int = 1):
        self.db = db
        self.document_id = document_id
        self.attempt = attempt
        self.root_id = str(uuid.uuid4())
        self._open: dict[str, DocumentParseSpan] = {}
        self._failed = False
        self.current_stage: str | None = None

    async def start_root(self) -> None:
        await self._safe(self._insert(
            span_id=self.root_id,
            kind="root",
            name="process",
            status="running",
            started_at=_now(),
        ))

    async def start_stage(self, name: str, detail: str | None = None) -> None:
        if self._failed:
            return
        self.current_stage = name
        sid = str(uuid.uuid4())
        await self._safe(self._insert(
            span_id=sid,
            kind="stage",
            name=name,
            status="running",
            started_at=_now(),
            detail=detail,
            parent=self.root_id,
        ))
        self._open[name] = DocumentParseSpan(id=sid)  # 轻量占位，仅用 id

    async def end_stage(self, name: str, detail: str | None = None) -> None:
        placeholder = self._open.pop(name, None)
        self.current_stage = None
        if not placeholder:
            return
        await self._safe(self._finish(placeholder.id, "done", detail=detail))

    async def fail_stage(self, name: str, error: str) -> None:
        placeholder = self._open.pop(name, None)
        self._failed = True
        if placeholder:
            await self._safe(self._finish(placeholder.id, "failed", error=error))
        # 其后未开的阶段标 cancelled（语义：上游失败，未执行）
        started = False
        for st in STAGE_ORDER:
            if st == name:
                started = True
                continue
            if started and st not in self._open:
                await self._safe(self._insert(
                    span_id=str(uuid.uuid4()),
                    kind="stage",
                    name=st,
                    status="cancelled",
                    parent=self.root_id,
                ))

    async def end_root(self, status: str = "done") -> None:
        await self._safe(self._finish(self.root_id, status))

    async def _insert(
        self,
        span_id: str,
        kind: str,
        name: str,
        status: str,
        started_at: datetime | None = None,
        detail: str | None = None,
        parent: str | None = None,
    ) -> None:
        self.db.add(
            DocumentParseSpan(
                id=span_id,
                document_id=self.document_id,
                attempt=self.attempt,
                parent_span_id=parent,
                kind=kind,
                name=name,
                status=status,
                started_at=started_at,
                ended_at=_now() if status not in ("running", "pending") else None,
                detail=detail,
            )
        )
        await self.db.flush()

    async def _finish(
        self, span_id: str, status: str, error: str | None = None, detail: str | None = None
    ) -> None:
        row = (
            await self.db.execute(
                select(DocumentParseSpan).where(DocumentParseSpan.id == span_id)
            )
        ).scalar_one_or_none()
        if not row:
            return
        row.status = status
        row.ended_at = _now()
        if error:
            row.error = error[:2000]
        if detail:
            row.detail = detail
        await self.db.flush()

    async def _safe(self, coro: Any) -> None:
        try:
            await coro
        except Exception as exc:  # noqa: BLE001 — 时间线是增强项
            logger.debug("span write skipped: %s", exc)
            try:
                await self.db.rollback()
            except Exception:  # noqa: BLE001
                pass


async def list_parse_spans(
    db: AsyncSession, document_id: str, limit_attempts: int = 3
) -> list[dict[str, Any]]:
    """最近若干次 attempt 的 span，按 attempt/started_at 排。"""
    rows = (
        await db.execute(
            select(DocumentParseSpan)
            .where(DocumentParseSpan.document_id == document_id)
            .order_by(DocumentParseSpan.attempt.desc(), DocumentParseSpan.started_at)
        )
    ).scalars().all()
    attempts = sorted({r.attempt for r in rows}, reverse=True)[:limit_attempts]
    keep = {a for a in attempts}
    out = []
    for r in rows:
        if r.attempt not in keep:
            continue
        out.append(
            {
                "id": r.id,
                "attempt": r.attempt,
                "parent_span_id": r.parent_span_id,
                "kind": r.kind,
                "name": r.name,
                "status": r.status,
                "started_at": str(r.started_at) if r.started_at else None,
                "ended_at": str(r.ended_at) if r.ended_at else None,
                "error": r.error,
                "detail": r.detail,
            }
        )
    return out
