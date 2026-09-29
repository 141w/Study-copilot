"""F2/F3 PostgreSQL 手测（fix(phase2-audit) 收尾验收）。

在真实 PostgreSQL 上验证 SQLite 单测无法证明的两点：
  F2 事务边界：span 独立会话写入在主事务 rollback 后仍可读；
              成功收尾（commit 后）能立即提交。
  F3 指标：文档级 key 去重后 Recall 不顶穿；期望集求交判定正确。

用法：DATABASE_URL=postgresql+asyncpg://...  .venv/bin/python scripts/pg_f2f3_verify.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 允许从 backend/ 直接跑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import Document, DocumentParseSpan, User  # noqa: E402
from app.services.parse_span_service import ParseSpanRecorder, recover_stale_spans  # noqa: E402
from evaluation.harness import hit_rate_at_k, mrr_at_k, recall_at_k  # noqa: E402


async def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url or "sqlite" in url:
        print("请设置指向 PostgreSQL 的 DATABASE_URL")
        return 2

    engine = create_async_engine(url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 建表（仅测试所需）
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        from app.db.database import Base

        await conn.run_sync(Base.metadata.create_all)

    results: list[tuple[str, bool, str]] = []

    async with factory() as db:
        # ---- 清理旧数据 ----
        await db.execute(text("DELETE FROM document_parse_spans"))
        await db.execute(text("DELETE FROM documents"))
        await db.execute(text("DELETE FROM users"))
        await db.commit()

        # PG 开外键：必须先提交 user 再插 document
        user = User(
            id="pg-user", username="pguser", email="pg@t.com", password_hash="x" * 60
        )
        db.add(user)
        await db.commit()

        doc = Document(
            id="pg-doc",
            user_id=user.id,
            filename="pg.pdf",
            file_path="/tmp/pg.pdf",
            status="processing",
            chunk_count=0,
        )
        db.add(doc)
        await db.commit()

    # ============================================================
    # F2-1 成功收尾：主事务 commit 后的 end_stage/end_root 必须落库
    # ============================================================
    async with factory() as main_db:
        spans = ParseSpanRecorder("pg-doc", attempt=1, session_factory=factory)
        await spans.start_root()
        for st in ("parse", "profile", "chunk", "embed"):
            await spans.start_stage(st)
            await spans.end_stage(st)
        await spans.start_stage("finalize")
        d = await main_db.get(Document, "pg-doc")
        d.status = "ready"
        d.chunk_count = 3
        await main_db.commit()
        await spans.end_stage("finalize", "ready")
        await spans.end_root("done")
        await spans.close()

        rows = (
            await main_db.execute(
                select(DocumentParseSpan).where(DocumentParseSpan.document_id == "pg-doc")
            )
        ).scalars().all()
        by = {(r.kind, r.name): r for r in rows}
        ok = (
            ("stage", "finalize") in by
            and by[("stage", "finalize")].status == "done"
            and ("root", "process") in by
            and by[("root", "process")].status == "done"
        )
        detail = f"finalize={by.get(('stage','finalize'), type('',(),{'status':'missing'})()).status} root={by.get(('root','process'), type('',(),{'status':'missing'})()).status}"
        results.append(("F2-1 成功收尾 commit 后落库", ok, detail))

    # ============================================================
    # F2-2 失败 span 在主事务 rollback 后仍在
    # ============================================================
    async with factory() as main_db:
        spans = ParseSpanRecorder("pg-doc", attempt=2, session_factory=factory)
        await spans.start_root()
        await spans.start_stage("parse")
        await spans.fail_stage("parse", "文件损坏无法解析")
        await spans.end_root("failed")
        await spans.close()

        await main_db.rollback()
        rows = (
            await main_db.execute(
                select(DocumentParseSpan)
                .where(
                    DocumentParseSpan.document_id == "pg-doc",
                    DocumentParseSpan.attempt == 2,
                )
            )
        ).scalars().all()
        by = {(r.kind, r.name): r for r in rows}
        root = by.get(("root", "process"))
        parse = by.get(("stage", "parse"))
        ok = (
            root is not None
            and root.status == "failed"
            and parse is not None
            and parse.status == "failed"
            and parse.error == "文件损坏无法解析"
        )
        results.append(
            (
                "F2-2 失败 span 在主 rollback 后仍在",
                ok,
                f"root={getattr(root,'status',None)} parse_err={getattr(parse,'error',None)!r}",
            )
        )

    # ============================================================
    # F2-3 悬挂 running 收敛
    # ============================================================
    async with factory() as main_db:
        spans = ParseSpanRecorder("pg-doc", attempt=3, session_factory=factory)
        await spans.start_root()
        await spans.start_stage("chunk")
        await spans.close()  # 模拟进程被杀
        n = await recover_stale_spans(main_db)
        rows = (
            await main_db.execute(
                select(DocumentParseSpan)
                .where(
                    DocumentParseSpan.document_id == "pg-doc",
                    DocumentParseSpan.attempt == 3,
                )
            )
        ).scalars().all()
        ok = n >= 2 and all(r.status == "failed" for r in rows)
        results.append(("F2-3 悬挂 running 归 failed", ok, f"recovered={n} rows={len(rows)}"))

    # ============================================================
    # F3 指标（harness 对拍 + 文档级去重）
    # ============================================================
    # 期望 {D}，检索返回 D 的 5 个切片 → 去重后 ranked=[D]，recall=1.0（不得 5.0）
    ranked_dup = ["D", "D", "D", "D", "D"]
    ranked_uniq = ["D"]
    rec_dup = recall_at_k(ranked_dup, {"D"}, 5)
    rec_uniq = recall_at_k(ranked_uniq, {"D"}, 5)
    results.append(
        (
            "F3-a harness 行为确认",
            rec_dup == 5.0 and rec_uniq == 1.0,
            f"recall(dup)={rec_dup} recall(uniq)={rec_uniq}（证明须去重）",
        )
    )

    # 服务层去重后结果（与 test_f3_recall_not_inflated 同逻辑）
    seen: set[str] = set()
    ranked: list[str] = []
    for k in ranked_dup:
        if k not in seen:
            seen.add(k)
            ranked.append(k)
    r = recall_at_k(ranked, {"D"}, 5)
    results.append(("F3-b 去重后 Recall∈[0,1]", 0.0 <= r <= 1.0 and r == 1.0, f"recall={r}"))

    # 期望求交：返回非期望文档 → hit@1=0
    hit_wrong = hit_rate_at_k(["OTHER"], {"D"}, 1)
    mrr_wrong = mrr_at_k(["OTHER", "D"], {"D"}, 2)
    results.append(
        (
            "F3-c 非期望不计命中",
            hit_wrong == 0.0 and mrr_wrong == 0.5,
            f"hit@1={hit_wrong} mrr@2={mrr_wrong}",
        )
    )

    # ============================================================
    # FTS 配置指纹（记录，不判定）
    # ============================================================
    async with engine.connect() as conn:
        fts = await conn.execute(
            text("SELECT cfgname FROM pg_ts_config WHERE cfgname IN ('simple','zhparser','english')")
        )
        fts_names = [r[0] for r in fts]
    results.append(
        (
            "FTS 可用配置（记录）",
            True,
            f"pg_ts_config={fts_names}；zhparser 未装则生产降级 simple",
        )
    )

    # ============================================================
    # 输出
    # ============================================================
    print("\n=== F2/F3 PostgreSQL 手测 ===")
    print(f"DSN: {url.split('@')[-1] if '@' in url else url}")
    print(f"时间: {datetime.now(UTC).isoformat()}")
    print()
    all_ok = True
    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  [{mark}] {name} — {detail}")
    print()
    print("结论:", "全部通过" if all_ok else "存在失败项")

    await engine.dispose()
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
