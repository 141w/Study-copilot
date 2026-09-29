"""阶段三：解析时间线 span 语义（failed vs cancelled）。

F2（fix(phase2-audit)）补充：事务边界复现测试。原有用例只在同一 session 上
读（能看到未 commit 的 flush），掩盖了「成功收尾落进无人提交的新事务」与
「失败记录被共享 session rollback 抹掉」。以下用例用**独立会话**只读已提交
数据来暴露该缺陷。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import Document, DocumentParseSpan, User
from app.services.parse_span_service import (
    ParseSpanRecorder,
    list_parse_spans,
    recover_stale_spans,
)


@pytest.fixture
def span_factory(test_engine):
    """独立会话工厂（与主 db_session 分离，模拟生产 AsyncSessionLocal）。"""
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(id="ps-user", username="psuser", email="p@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.fixture
async def doc(db_session: AsyncSession, user: User) -> Document:
    d = Document(
        id="ps-doc",
        user_id=user.id,
        filename="x.pdf",
        file_path="/tmp/x.pdf",
        status="processing",
        chunk_count=0,
    )
    db_session.add(d)
    await db_session.commit()
    return d


@pytest.mark.asyncio
async def test_happy_path_all_done(db_session, doc, span_factory):
    rec = ParseSpanRecorder(doc.id, session_factory=span_factory)
    await rec.start_root()
    for stage in ("parse", "profile", "chunk", "embed", "finalize"):
        await rec.start_stage(stage)
        await rec.end_stage(stage)
    await rec.end_root("done")
    await rec.close()

    spans = await list_parse_spans(db_session, doc.id)
    stages = [s for s in spans if s["kind"] == "stage"]
    assert all(s["status"] == "done" for s in stages)
    assert {s["name"] for s in stages} == {"parse", "profile", "chunk", "embed", "finalize"}


@pytest.mark.asyncio
async def test_fail_marks_later_cancelled(db_session, doc, span_factory):
    rec = ParseSpanRecorder(doc.id, session_factory=span_factory)
    await rec.start_root()
    await rec.start_stage("parse")
    await rec.fail_stage("parse", "文件损坏")
    await rec.close()

    spans = await list_parse_spans(db_session, doc.id)
    by_name = {s["name"]: s for s in spans if s["kind"] == "stage"}
    assert by_name["parse"]["status"] == "failed"
    assert by_name["parse"]["error"] == "文件损坏"
    # 上游失败 → 其后阶段 cancelled（未执行）
    assert by_name["chunk"]["status"] == "cancelled"
    assert by_name["embed"]["status"] == "cancelled"
    assert by_name["finalize"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_span_write_failure_does_not_raise(db_session, span_factory):
    rec = ParseSpanRecorder("nonexistent-doc-for-fk", session_factory=span_factory)
    # FK 失败也只 debug，不抛
    await rec.start_root()
    await rec.start_stage("parse")
    await rec.end_stage("parse")
    await rec.end_root("done")
    await rec.close()


@pytest.mark.asyncio
async def test_list_limits_attempts(db_session, doc, span_factory):
    for attempt in (1, 2, 3):
        rec = ParseSpanRecorder(doc.id, attempt=attempt, session_factory=span_factory)
        await rec.start_root()
        await rec.start_stage("parse")
        await rec.end_stage("parse")
        await rec.end_root("done")
        await rec.close()

    spans = await list_parse_spans(db_session, doc.id, limit_attempts=2)
    assert {s["attempt"] for s in spans} == {2, 3}


# ---------------------------------------------------------------------------
# F2 · 事务边界复现
# ---------------------------------------------------------------------------

async def _committed_spans(test_engine, document_id: str) -> list[DocumentParseSpan]:
    """用独立会话只读**已提交**行——与前端/跨请求看到的一致。"""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        rows = (
            await s.execute(
                select(DocumentParseSpan).where(DocumentParseSpan.document_id == document_id)
            )
        ).scalars().all()
        return list(rows)


@pytest.mark.asyncio
async def test_f2_success_tail_survives_commit(test_engine, db_session, doc, span_factory):
    """成功路径：commit 之后的 end_stage/end_root 必须自己提交。

    复现 document_service 的写法：阶段写入 → commit（模拟 status=ready 落库）
    → 再写 finalize/root。改前这两笔只 flush 不 commit，独立会话里
    finalize 停在 running、root 也停在 running。
    """
    doc_id = doc.id
    rec = ParseSpanRecorder(doc_id, session_factory=span_factory)
    await rec.start_root()
    for stage in ("parse", "profile", "chunk", "embed"):
        await rec.start_stage(stage)
        await rec.end_stage(stage)

    await rec.start_stage("finalize")
    # 模拟 document_service 成功路径：doc.status=ready 后 commit
    doc.status = "ready"
    doc.chunk_count = 3
    await db_session.commit()

    # 这两笔必须自己提交
    await rec.end_stage("finalize", "ready")
    await rec.end_root("done")
    await rec.close()

    rows = await _committed_spans(test_engine, doc_id)
    by_name = {(r.kind, r.name): r for r in rows}
    assert ("stage", "finalize") in by_name
    assert by_name[("stage", "finalize")].status == "done", (
        f"finalize 收尾未提交，库里仍是 {by_name[('stage', 'finalize')].status!r}"
    )
    assert ("root", "process") in by_name
    assert by_name[("root", "process")].status == "done", (
        f"root 收尾未提交，库里仍是 {by_name[('root', 'process')].status!r}"
    )


@pytest.mark.asyncio
async def test_f2_failure_span_survives_main_rollback(test_engine, db_session, doc, span_factory):
    """失败路径：失败 span 必须在主事务 rollback 之后仍然在库里。

    复现 document_service 异常路径：fail_stage + end_root('failed')（写入）
    → db.rollback()（清掉共享 session 的写）→ doc.status=error + commit。
    改前失败记录被自己的 rollback 抹掉，只剩「文档失败」没有「为什么失败」。
    """
    doc_id = doc.id
    rec = ParseSpanRecorder(doc_id, session_factory=span_factory)
    await rec.start_root()
    await rec.start_stage("parse")
    # 主流程抛错前把失败写进时间线
    await rec.fail_stage("parse", "文件损坏无法解析")
    await rec.end_root("failed")
    await rec.close()

    # 模拟 document_service except 路径
    await db_session.rollback()
    doc2 = await db_session.get(Document, doc_id)
    assert doc2 is not None
    doc2.status = "error"
    await db_session.commit()

    rows = await _committed_spans(test_engine, doc_id)
    by_name = {(r.kind, r.name): r for r in rows}
    root = by_name.get(("root", "process"))
    parse = by_name.get(("stage", "parse"))
    assert root is not None, "root 记录被 rollback 抹掉"
    assert root.status == "failed", f"root 状态为 {root.status!r}，期望 failed"
    assert parse is not None, "失败 stage 被 rollback 抹掉"
    assert parse.status == "failed"
    assert parse.error == "文件损坏无法解析"
    assert by_name.get(("stage", "chunk")) is not None
    assert by_name[("stage", "chunk")].status == "cancelled"


@pytest.mark.asyncio
async def test_f2_span_error_does_not_poison_main_session(test_engine, db_session, doc, span_factory):
    """span 写入失败不得把共享 session 打进 PendingRollback、殃及主流程数据。

    直接让一次 span 落库抛错，随后主流程仍能提交自己的 DocumentChunk。
    改前 _safe 会 rollback 共享 session，把已 flush 的主流程数据一并冲掉。
    """
    from app.db import DocumentChunk

    doc_id = doc.id
    rec = ParseSpanRecorder(doc_id, session_factory=span_factory)
    await rec.start_root()
    await rec.start_stage("parse")

    # 主流程先写入切片（flush）
    db_session.add(
        DocumentChunk(id="f2-chunk-1", document_id=doc_id, content="hello", chunk_index=0)
    )
    await db_session.flush()

    # 注入一次 span 写入失败（比 FK 更可靠：SQLite 不开外键）
    async def _boom(*_a, **_k):
        raise RuntimeError("injected span write failure")

    rec2 = ParseSpanRecorder(doc_id, session_factory=span_factory)
    rec2._insert = _boom  # type: ignore[method-assign]
    await rec2.start_root()  # _safe 吞掉，且不得动主 session
    await rec2.close()

    # 主流程必须还能继续提交
    doc = await db_session.get(Document, doc_id)
    doc.status = "ready"
    doc.chunk_count = 1
    await db_session.commit()

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        chunks = (
            await s.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))
        ).scalars().all()
    assert len(chunks) == 1, (
        f"span 写入失败把主流程已 flush 的切片冲掉了，实查 {len(chunks)} 行"
    )
    await rec.close()


@pytest.mark.asyncio
async def test_f2_ready_with_chunks_requires_committed_rows(test_engine, db_session, doc, span_factory):
    """极端用例：span 写入失败时，文档不得既 status=ready/chunk_count>0 又库里 0 行。

    注入 span 落库失败后，主流程继续提交。独立会话保证共享 session 不被
    冲掉，切片与 chunk_count 应一致。
    """
    from app.db import DocumentChunk

    doc_id = doc.id
    rec = ParseSpanRecorder(doc_id, session_factory=span_factory)
    await rec.start_root()
    await rec.start_stage("chunk")
    db_session.add(
        DocumentChunk(id="f2-chunk-x", document_id=doc_id, content="x", chunk_index=0)
    )
    await db_session.flush()

    # 注入 span 收尾写入失败（_safe 吞掉，且不得动主 session）
    async def _boom(*_a, **_k):
        raise RuntimeError("injected")

    rec._finish = _boom  # type: ignore[method-assign]
    await rec.end_stage("chunk")
    await rec.end_root("done")
    await rec.close()

    # document_service 继续走到提交
    doc2 = await db_session.get(Document, doc_id)
    doc2.status = "ready"
    doc2.chunk_count = 1
    await db_session.commit()

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        n = len(
            (
                await s.execute(
                    select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
                )
            ).scalars().all()
        )
        d = await s.get(Document, doc_id)
    assert not (d.status == "ready" and d.chunk_count > 0 and n == 0), (
        f"文档显示 ready/{d.chunk_count} 块，库里实查 {n} 行"
    )
    assert n == d.chunk_count, f"chunk_count={d.chunk_count} 与实查 {n} 行不一致"


@pytest.mark.asyncio
async def test_f2_recover_stale_running_spans(db_session, doc, span_factory):
    """进程重启后残留 running 应归为 failed（进程中断）。"""
    rec = ParseSpanRecorder(doc.id, session_factory=span_factory)
    await rec.start_root()
    await rec.start_stage("parse")
    # 模拟进程被杀：不 end_stage / end_root
    await rec.close()

    n = await recover_stale_spans(db_session)
    assert n >= 2
    spans = await list_parse_spans(db_session, doc.id)
    assert all(s["status"] == "failed" for s in spans if s["status"] != "cancelled")
    root = next(s for s in spans if s["kind"] == "root")
    assert root["error"] == "进程中断"


@pytest.mark.asyncio
async def test_fail_stage_twice_no_duplicate_cancelled(db_session, doc, span_factory):
    """OCR High：外层 except 再次 fail_stage 不得重复插 cancelled / 覆盖 done。"""
    rec = ParseSpanRecorder(doc.id, session_factory=span_factory)
    await rec.start_root()
    await rec.start_stage("parse")
    await rec.end_stage("parse")  # parse 已 done
    await rec.start_stage("chunk")
    await rec.fail_stage("chunk", "boom")
    # 模拟 document_service 外层 except 再调一次
    await rec.fail_stage("chunk", "boom again")

    spans = await list_parse_spans(db_session, doc.id)
    stages = [s for s in spans if s["kind"] == "stage"]
    names = [s["name"] for s in stages]
    # 每个阶段只应有一行
    assert len(names) == len(set(names)), names
    by = {s["name"]: s for s in stages}
    assert by["parse"]["status"] == "done"  # 不被 cancelled 覆盖
    assert by["chunk"]["status"] == "failed"
    assert by["embed"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_f13_attempt_increments_on_reprocess(db_session, doc, span_factory):
    """重解析 attempt 递增，不往同一 attempt 追加重复行。"""
    from app.services.parse_span_service import next_attempt

    a1 = await next_attempt(db_session, doc.id)
    assert a1 == 1
    rec = ParseSpanRecorder(doc.id, attempt=a1, session_factory=span_factory)
    await rec.start_root()
    await rec.start_stage("parse")
    await rec.end_stage("parse")
    await rec.end_root("done")
    await rec.close()

    a2 = await next_attempt(db_session, doc.id)
    assert a2 == 2
    rec2 = ParseSpanRecorder(doc.id, attempt=a2, session_factory=span_factory)
    await rec2.start_root()
    await rec2.start_stage("parse")
    await rec2.end_stage("parse")
    await rec2.end_root("done")
    await rec2.close()

    spans = await list_parse_spans(db_session, doc.id)
    parse_rows = [s for s in spans if s["name"] == "parse"]
    assert {s["attempt"] for s in parse_rows} == {1, 2}


# F20
@pytest.mark.asyncio
async def test_f20_fail_stage_no_duplicate_cancelled(db_session, doc, span_factory):
    """fail_stage 两次不得重复插 cancelled、不得覆盖已 done 阶段。"""
    rec = ParseSpanRecorder(doc.id, session_factory=span_factory)
    await rec.start_root()
    await rec.start_stage("parse")
    await rec.end_stage("parse")
    await rec.start_stage("chunk")
    await rec.fail_stage("chunk", "boom")
    await rec.fail_stage("chunk", "boom again")
    await rec.close()
    spans = await list_parse_spans(db_session, doc.id)
    stages = [s for s in spans if s["kind"] == "stage"]
    names = [s["name"] for s in stages]
    assert len(names) == len(set(names)), names
    by = {s["name"]: s for s in stages}
    assert by["parse"]["status"] == "done"
    assert by["chunk"]["status"] == "failed"
