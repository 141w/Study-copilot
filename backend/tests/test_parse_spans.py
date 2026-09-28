"""阶段三：解析时间线 span 语义（failed vs cancelled）。"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentParseSpan, User
from app.services.parse_span_service import ParseSpanRecorder, list_parse_spans


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
async def test_happy_path_all_done(db_session, doc):
    rec = ParseSpanRecorder(db_session, doc.id)
    await rec.start_root()
    for stage in ("parse", "profile", "chunk", "embed", "finalize"):
        await rec.start_stage(stage)
        await rec.end_stage(stage)
    await rec.end_root("done")

    spans = await list_parse_spans(db_session, doc.id)
    stages = [s for s in spans if s["kind"] == "stage"]
    assert all(s["status"] == "done" for s in stages)
    assert {s["name"] for s in stages} == {"parse", "profile", "chunk", "embed", "finalize"}


@pytest.mark.asyncio
async def test_fail_marks_later_cancelled(db_session, doc):
    rec = ParseSpanRecorder(db_session, doc.id)
    await rec.start_root()
    await rec.start_stage("parse")
    await rec.fail_stage("parse", "文件损坏")

    spans = await list_parse_spans(db_session, doc.id)
    by_name = {s["name"]: s for s in spans if s["kind"] == "stage"}
    assert by_name["parse"]["status"] == "failed"
    assert by_name["parse"]["error"] == "文件损坏"
    # 上游失败 → 其后阶段 cancelled（未执行）
    assert by_name["chunk"]["status"] == "cancelled"
    assert by_name["embed"]["status"] == "cancelled"
    assert by_name["finalize"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_span_write_failure_does_not_raise(db_session, doc):
    rec = ParseSpanRecorder(db_session, "nonexistent-doc-for-fk")
    # FK 失败也只 debug，不抛
    await rec.start_root()
    await rec.start_stage("parse")
    await rec.end_stage("parse")
    await rec.end_root("done")


@pytest.mark.asyncio
async def test_list_limits_attempts(db_session, doc):
    for attempt in (1, 2, 3):
        rec = ParseSpanRecorder(db_session, doc.id, attempt=attempt)
        await rec.start_root()
        await rec.start_stage("parse")
        await rec.end_stage("parse")
        await rec.end_root("done")

    spans = await list_parse_spans(db_session, doc.id, limit_attempts=2)
    assert {s["attempt"] for s in spans} == {2, 3}
