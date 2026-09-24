"""Preview-chunking API: read-only, no DB writes, no embedder."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chunking_pipeline import run_chunking_chain
from app.db import DocumentChunk, User
from app.utils.auth import get_password_hash

SAMPLE_MD = (
    "# 标题一\n\n## 小节 A\n"
    + ("内容甲。" * 40)
    + "\n\n# 标题二\n\n## 小节 B\n"
    + ("内容乙。" * 40)
    + "\n"
)


async def _login_headers(client, db_session: AsyncSession, username: str = "previewer") -> dict:
    u = User(
        id=f"prev-{username}",
        username=username,
        email=f"{username}@test.local",
        password_hash=get_password_hash("testpass"),
    )
    db_session.add(u)
    await db_session.commit()
    resp = await client.post(
        "/api/auth/login",
        data={"username": username, "password": "testpass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        pytest.skip(f"login unavailable: {resp.status_code} {resp.text}")
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_preview_returns_chain_and_profile(client, db_session):
    headers = await _login_headers(client, db_session)
    r = await client.post(
        "/api/documents/preview-chunking",
        json={"text": SAMPLE_MD, "strategy": "auto"},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["selected_strategy"] in {"fixed", "hierarchical", "semantic"}
    assert isinstance(body["chain"], list) and body["chain"]
    assert "total_chars" in body["profile"]
    assert body["chunks"] and body["chunks"][0]["seq"] == 1
    assert body["stats"]["count"] == len(body["chunks"])
    for item in body["rejected"]:
        assert set(item.keys()) == {"strategy", "reason"}


@pytest.mark.asyncio
async def test_preview_rejects_oversize_text(client, db_session):
    headers = await _login_headers(client, db_session, "prev_big")
    r = await client.post(
        "/api/documents/preview-chunking",
        json={"text": "x" * 64_001},
        headers=headers,
    )
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_preview_never_calls_embedder():
    with patch(
        "app.core.embedder.embedder.embed_texts", new_callable=AsyncMock
    ) as emb, patch(
        "app.core.embedder.embedder.embed_query", new_callable=AsyncMock
    ) as emb_q:
        run = await run_chunking_chain(
            [{"text": SAMPLE_MD, "page": 1}],
            "preview",
            allow_embed=False,
        )
        assert run.chunks
        emb.assert_not_called()
        emb_q.assert_not_called()
    # 若 semantic 被尝试，原因必须是 preview 跳过 embedder
    for item in run.rejected:
        if item["strategy"] == "semantic":
            assert "embed" in item["reason"]
    assert run.selected_strategy != "semantic"


@pytest.mark.asyncio
async def test_preview_does_not_write_document_chunks(db_session: AsyncSession):
    await run_chunking_chain(
        [{"text": SAMPLE_MD, "page": 1}],
        "preview",
        allow_embed=False,
    )
    n = (
        await db_session.execute(select(func.count(DocumentChunk.id)))
    ).scalar() or 0
    assert n == 0


@pytest.mark.asyncio
async def test_preview_forced_fixed_strategy(client, db_session):
    headers = await _login_headers(client, db_session, "prev_fix")
    r = await client.post(
        "/api/documents/preview-chunking",
        json={"text": SAMPLE_MD, "strategy": "fixed", "chunk_size": 200},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["selected_strategy"] == "fixed"
    assert body["chain"] == ["fixed"]


@pytest.mark.asyncio
async def test_preview_records_rejected_tiers():
    run = await run_chunking_chain(
        [{"text": "短" * 2000, "page": 1}],
        "preview",
        strategy="auto",
        allow_embed=False,
    )
    assert run.chain
    for item in run.rejected:
        assert set(item.keys()) == {"strategy", "reason"}


@pytest.mark.asyncio
async def test_preview_requires_auth(client):
    r = await client.post(
        "/api/documents/preview-chunking",
        json={"text": SAMPLE_MD},
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_preview_truncates_over_500_chunks():
    from app.core.chunking_pipeline import (
        PREVIEW_MAX_CHUNKS,
        chunk_stats,
        serialize_chunks,
    )

    many = [{"text": f"块{i}内容" * 5, "page": 1} for i in range(520)]
    stats = chunk_stats(many, PREVIEW_MAX_CHUNKS)
    assert stats["count"] == PREVIEW_MAX_CHUNKS
    assert stats["truncated_to"] == PREVIEW_MAX_CHUNKS
    serialized = serialize_chunks(many, PREVIEW_MAX_CHUNKS)
    assert len(serialized) == PREVIEW_MAX_CHUNKS


@pytest.mark.asyncio
async def test_preview_timeout_504(client, db_session):
    headers = await _login_headers(client, db_session, "prev_slow")

    async def _slow(*_a, **_k):
        await asyncio.sleep(8)
        return []

    with patch("app.core.chunking_pipeline.create_chunker") as mk:
        chunker = AsyncMock()
        chunker.chunk_document = _slow
        chunker.chunk_size = 500
        mk.return_value = chunker
        r = await client.post(
            "/api/documents/preview-chunking",
            json={"text": "hello world " * 50},
            headers=headers,
        )
    assert r.status_code == 504
