import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_health_chunk_count_mismatch_degrades(client, db_session):
    """§13.3-6：ready 文档行数 != chunk_count 时 /health 必须 degraded。"""
    from app.db import Document, DocumentChunk, User

    user = User(id="health-user", username="healthu", email="h@t.com", password_hash="x" * 60)
    doc = Document(
        id="health-doc-mismatch",
        user_id=user.id,
        filename="mismatch.pdf",
        file_path="/tmp/mismatch.pdf",
        status="ready",
        chunk_count=5,  # 声称 5 段
    )
    db_session.add_all(
        [
            user,
            doc,
            DocumentChunk(
                id="health-chunk-1",
                document_id=doc.id,
                content="only one",
                chunk_index=0,
                chunk_metadata={},
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["chunk_count_sync"].startswith("mismatch")


@pytest.mark.asyncio
async def test_health_chunk_count_match_stays_healthy(client, db_session):
    from app.db import Document, DocumentChunk, User

    user = User(id="health-user-ok", username="healthok", email="ho@t.com", password_hash="x" * 60)
    doc = Document(
        id="health-doc-ok",
        user_id=user.id,
        filename="ok.pdf",
        file_path="/tmp/ok.pdf",
        status="ready",
        chunk_count=1,
    )
    db_session.add_all(
        [
            user,
            doc,
            DocumentChunk(
                id="health-chunk-ok",
                document_id=doc.id,
                content="one",
                chunk_index=0,
                chunk_metadata={},
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert data["checks"]["chunk_count_sync"] == "ok"
