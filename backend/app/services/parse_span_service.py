"""阶段三：解析阶段时间线 recorder（轻量，失败不阻断主流程）。

F2 事务边界：span 写入走**独立会话**、每条状态转移立即 commit。
理由：失败 span 必须在主事务 rollback 之后仍可读（SAVEPOINT 嵌在主事务里，
主事务一并回滚就没了）；且 _safe 不得再碰共享 session，否则一次 span
写入失败会把已 flush 的主流程数据一并冲掉。
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import DocumentParseSpan
from app.db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# 与 _do_process_document 各阶段一一对应（勿抄 WeKnora 的 5 阶段名）
STAGE_ORDER = ["parse", "profile", "chunk", "embed", "index", "finalize"]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ParseSpanRecorder:
    """按 attempt 记录一次文档处理的阶段 span。

    写入使用独立会话并立即 commit；出错时只记日志，不抛、不影响主事务。
    """

    def __init__(
        self,
        document_id: str,
        attempt: int = 1,
        *,
        session_factory: Callable[[], AsyncSession] | None = None,
    ):
        self.document_id = document_id
        self.attempt = attempt
        self._factory = session_factory or AsyncSessionLocal
        self._session: AsyncSession | None = None
        self.root_id = str(uuid.uuid4())
        self._open: dict[str, str] = {}  # stage name → span id
        self._failed = False
        self.current_stage: str | None = None
        # 已终结（done/failed/cancelled）的阶段名：防二次 fail_stage 重复级联、
        # 防对已 done 阶段补插 cancelled（OCR High）
        self._settled: set[str] = set()

    async def _sess(self) -> AsyncSession:
        if self._session is None:
            self._session = self._factory()
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:  # noqa: BLE001
                pass
            self._session = None

    async def start_root(self) -> None:
        await self._safe(self._insert(
            span_id=self.root_id,
            kind="root",
            name="process",
            status="running",
            started_at=_now(),
        ))

    async def start_stage(self, name: str, detail: str | None = None) -> None:
        if self._failed or name in self._settled:
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
        self._open[name] = sid

    async def end_stage(self, name: str, detail: str | None = None) -> None:
        span_id = self._open.pop(name, None)
        self._settled.add(name)
        self.current_stage = None
        if not span_id:
            return
        await self._safe(self._finish(span_id, "done", detail=detail))

    async def fail_stage(self, name: str, error: str) -> None:
        span_id = self._open.pop(name, None)
        self._settled.add(name)
        self.current_stage = None
        if span_id:
            await self._safe(self._finish(span_id, "failed", error=error))
        if self._failed:
            # 级联已写过（外层 except 再调一次），no-op
            return
        self._failed = True
        # 其后未开的阶段标 cancelled（语义：上游失败，未执行）
        started = False
        for st in STAGE_ORDER:
            if st == name:
                started = True
                continue
            if started and st not in self._settled and st not in self._open:
                await self._safe(self._insert(
                    span_id=str(uuid.uuid4()),
                    kind="stage",
                    name=st,
                    status="cancelled",
                    started_at=_now(),
                    parent=self.root_id,
                ))
                self._settled.add(st)

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
        sess = await self._sess()
        sess.add(
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
        await sess.commit()

    async def _finish(
        self, span_id: str, status: str, error: str | None = None, detail: str | None = None
    ) -> None:
        sess = await self._sess()
        row = (
            await sess.execute(
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
        await sess.commit()

    async def _safe(self, coro: Any) -> None:
        """span 写入失败只记日志。绝不 rollback 主流程 session。"""
        try:
            await coro
        except Exception as exc:  # noqa: BLE001 — 时间线是增强项
            logger.debug("span write skipped: %s", exc)
            # 独立会话若进入坏状态，丢弃重建，不影响主事务
            if self._session is not None:
                try:
                    await self._session.rollback()
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


async def recover_stale_spans(db: AsyncSession) -> int:
    """进程重启/崩溃后，把残留 running 的 span 归为 failed（进程中断）。

    挂在应用启动引导（lifespan）里。返回受影响行数。
    """
    from sqlalchemy import func

    # 先数后改，避开 Result.rowcount 在部分方言上的类型缺失
    n = (
        await db.execute(
            select(func.count())
            .select_from(DocumentParseSpan)
            .where(DocumentParseSpan.status == "running")
        )
    ).scalar_one()
    if n:
        await db.execute(
            update(DocumentParseSpan)
            .where(DocumentParseSpan.status == "running")
            .values(status="failed", ended_at=_now(), error="进程中断")
        )
        await db.commit()
    return int(n or 0)
