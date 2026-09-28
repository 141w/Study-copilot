"""P0 防护回归：注册开关、BYOK 不回落服务器 Key、reindex 不堆叠切片。"""

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLM
from app.db import Document, DocumentChunk, User
from app.services import document_service


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(
        id=str(uuid.uuid4()),
        username=f"guard_{uuid.uuid4().hex[:6]}",
        email=f"guard_{uuid.uuid4().hex[:6]}@t.com",
        password_hash="x" * 60,
    )
    db_session.add(u)
    await db_session.commit()
    return u


# ── 注册开关 ────────────────────────────────────────────────────────────────


async def test_register_open_by_default(client: AsyncClient):
    """默认保持「注册即用」。"""
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": f"u{uuid.uuid4().hex[:8]}",
            "email": f"u{uuid.uuid4().hex[:8]}@example.com",
            "password": "StudyPass9",
        },
    )
    assert resp.status_code in (200, 201)


async def test_register_closed_when_disabled(client: AsyncClient, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "allow_registration", False)
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": f"u{uuid.uuid4().hex[:8]}",
            "email": f"u{uuid.uuid4().hex[:8]}@example.com",
            "password": "StudyPass9",
        },
    )
    assert resp.status_code == 403
    assert "注册" in resp.json().get("detail", "")


async def test_register_rejects_short_password(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": f"u{uuid.uuid4().hex[:8]}",
            "email": f"u{uuid.uuid4().hex[:8]}@example.com",
            "password": "short",
        },
    )
    assert resp.status_code == 422


# ── BYOK：用户流量不回落服务器 Key ─────────────────────────────────────────


def test_llm_does_not_fallback_to_server_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "sk-server-should-not-be-used")
    llm = LLM()
    assert llm.configured is False


def test_llm_configured_with_explicit_user_key():
    llm = LLM(api_key="sk-user-key")
    assert llm.configured is True


# ── 切片替换语义：重复处理不得堆叠 ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_do_process_document_replaces_chunks(db_session: AsyncSession, user: User, tmp_path):
    """reindex / 重复处理必须先删旧切片，避免五倍重复事故重演。"""
    file_path = tmp_path / "doc.txt"
    file_path.write_text("content for replace semantics")

    doc = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        filename="doc.txt",
        file_path=str(file_path),
        status="ready",
        chunk_count=2,
        file_size=20,
    )
    db_session.add(doc)
    for i in range(2):
        db_session.add(
            DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc.id,
                content=f"stale-{i}",
                chunk_index=i,
                chunk_metadata={},
            )
        )
    await db_session.commit()

    with patch("app.services.document_service.document_parser.extract_pages") as mock_parse:
        mock_parse.return_value = [{"page": 1, "text": "Fresh page text for chunking."}]
        with patch("app.core.pgvector_store.embedder.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.0] * 768]
            count, _method = await document_service._do_process_document(db_session, user, doc.id)

    rows = (
        (await db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)))
        .scalars()
        .all()
    )
    assert all(not c.content.startswith("stale-") for c in rows)
    # 切片数应等于本次产出，而不是 旧数量 + 新数量
    assert len(rows) == count


async def test_classroom_health_shape(client: AsyncClient, user: User):
    """课堂健康检查返回链路就绪字段（引擎未起时 ready=false，不抛 500）。"""
    from app.services.auth_service import create_access_token

    token = create_access_token({"sub": user.id, "username": user.username})
    resp = await client.get(
        "/api/classroom/health", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) >= {
        "enabled",
        "engine_reachable",
        "webhook_configured",
        "ready",
    }
    # 默认 classroom_enabled=true 但引擎可能未跑：ready 可为 False，结构必须完整
    assert isinstance(data["ready"], bool)
    assert isinstance(data["engine_reachable"], bool)
