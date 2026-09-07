"""Tests covering pipeline optimizations (P1, P5, P7, P9, P10, P11, P12, S1, S2)."""

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chunker import (
    HierarchicalChunker,
    deduplicate_chunks,
)
from app.core.pgvector_store import PgVectorStore, _get_fts_config
from app.core.rag_engine import rag_engine
from app.db import Document, DocumentChunk, User
from app.exceptions import NotFoundError
from app.services import document_service
from app.services.document_service import _choose_chunker_method
from app.utils.auth import create_access_token


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(
        id=str(uuid.uuid4()),
        username=f"opt_user_{uuid.uuid4().hex[:6]}",
        email=f"opt_{uuid.uuid4().hex[:6]}@t.com",
        password_hash="x" * 60,
    )
    db_session.add(u)
    await db_session.commit()
    return u


# ── 1. Hierarchical chunking & parent context expansion (P7) ──────────────────


@pytest.mark.asyncio
async def test_hierarchical_chunker_stores_parent_text():
    """HierarchicalChunker must store parent_text in child chunks."""
    chunker = HierarchicalChunker(parent_chunk_size=300, child_chunk_size=80)
    pages = [
        {"page": 1, "text": "第一部分引言。\n\n" + "这是测试详细段落内容。\n\n" * 15},
    ]
    chunks = await chunker.chunk_document(pages, source_name="hier_test")
    parents = [c for c in chunks if c.get("is_parent")]
    children = [c for c in chunks if not c.get("is_parent")]

    assert len(parents) >= 1
    assert len(children) >= 1
    for child in children:
        assert "parent_text" in child
        assert len(child["parent_text"]) >= len(child["text"])


def test_deduplicate_chunks_preserves_parent_child_separation():
    """Parent and child chunks should not be merged even if text overlaps."""
    parent = {
        "text": "Full parent text contains child snippet inside it.",
        "is_parent": True,
    }
    child = {
        "text": "Full parent text contains child snippet",
        "is_parent": False,
        "parent_text": parent["text"],
    }
    # Jaccard similarity is very high, but is_parent differs
    deduped = deduplicate_chunks([parent, child], similarity_threshold=0.5)
    assert len(deduped) == 2


def test_rag_build_context_expands_parent_text():
    """build_context must expand parent_text when available in metadata."""
    retrieved = [
        {
            "chunk": {
                "text": "child snippet text",
                "page": 2,
                "source": "paper.pdf",
                "metadata": {
                    "parent_text": "This is the full rich parent context containing child snippet text and more.",
                },
            }
        }
    ]
    ctx = rag_engine.build_context(retrieved)
    assert "This is the full rich parent context" in ctx
    assert "<source" in ctx
    assert 'page="2"' in ctx


# ── 2. Strategy selection auto-adaptation (P5) ──────────────────────────────


def test_choose_chunker_method_pptx():
    """PPTX slides should use fixed chunking to preserve slide boundaries."""
    assert _choose_chunker_method(50_000, 100, filename="presentation.pptx") == "fixed"
    assert _choose_chunker_method(50_000, 100, filename="slides.PPT") == "fixed"


def test_choose_chunker_method_long_document():
    """Long structured documents (>15k, >=15 sentences) should use hierarchical."""
    assert _choose_chunker_method(30_000, 50, filename="thesis.pdf") == "hierarchical"
    assert _choose_chunker_method(120_000, 300, filename="book.pdf") == "hierarchical"


def test_choose_chunker_method_medium_document():
    """Medium articles (3k-15k) should use semantic."""
    assert _choose_chunker_method(8_000, 20, filename="article.docx") == "semantic"


def test_choose_chunker_method_short_document():
    """Short text should fall back to fixed or hierarchical if enough sentences."""
    assert _choose_chunker_method(1_000, 4, filename="note.txt") == "fixed"


# ── 3. Orphan file cleanup on commit failure (P1) ────────────────────────────


@pytest.mark.asyncio
async def test_upload_document_cleans_file_on_db_error(
    db_session: AsyncSession, user: User, tmp_path
):
    """If db.commit fails during upload, newly written disk file must be deleted."""
    content = b"sample test content for orphan check"
    with patch("app.services.document_service.settings.upload_dir", str(tmp_path)):
        with patch.object(db_session, "commit", side_effect=RuntimeError("DB Commit Crash")):
            with pytest.raises(RuntimeError, match="DB Commit Crash"):
                await document_service.upload_document(db_session, user, "orphan.txt", content)

    # Verify no file remains in tmp_path
    remaining = list(tmp_path.rglob("*.txt"))
    assert len(remaining) == 0, f"Orphan files found: {remaining}"


# ── 4. Document reprocessing (S2) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_reprocess_document_success(db_session: AsyncSession, user: User, tmp_path):
    """reprocess_document should clean old chunks, reset status, and re-enqueue."""
    file_path = tmp_path / "test_doc.txt"
    file_path.write_text("Document content for reprocessing test.")

    doc = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        filename="test_doc.txt",
        file_path=str(file_path),
        status="error",
        chunk_count=2,
        file_size=len(file_path.read_bytes()),
    )
    db_session.add(doc)
    # Add dummy chunk
    chunk = DocumentChunk(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        content="stale chunk",
        chunk_index=0,
        chunk_metadata={},
    )
    db_session.add(chunk)
    await db_session.commit()

    # Reprocess (worker unavailable in unit test -> runs sync fallback)
    with patch("app.services.document_service.document_parser.extract_pages") as mock_parse:
        mock_parse.return_value = [{"page": 1, "text": "Fresh extracted page content."}]
        with patch("app.core.pgvector_store.embedder.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.0] * 768]
            res = await document_service.reprocess_document(db_session, user, doc.id)

    assert res["id"] == doc.id
    assert res["status"] in ("ready", "processing")

    # Verify stale chunk was cleared and replaced
    chunks_in_db = (
        (await db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)))
        .scalars()
        .all()
    )
    assert all(c.content != "stale chunk" for c in chunks_in_db)


@pytest.mark.asyncio
async def test_reprocess_document_missing_file_raises_error(db_session: AsyncSession, user: User):
    """reprocess_document on nonexistent file path should raise NotFoundError."""
    doc = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        filename="missing.pdf",
        file_path="/tmp/non_existent_file_path_12345.pdf",
        status="error",
    )
    db_session.add(doc)
    await db_session.commit()

    with pytest.raises(NotFoundError, match="原始文件不存在"):
        await document_service.reprocess_document(db_session, user, doc.id)


@pytest.mark.asyncio
async def test_reprocess_document_api_endpoint(
    client, db_session: AsyncSession, user: User, tmp_path
):
    """POST /api/documents/{doc_id}/reprocess endpoint should return 200."""
    file_path = tmp_path / "endpoint_doc.txt"
    file_path.write_text("API endpoint test content.")

    doc = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        filename="endpoint_doc.txt",
        file_path=str(file_path),
        status="error",
    )
    db_session.add(doc)
    await db_session.commit()

    token = create_access_token(data={"sub": user.id, "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.document_service.document_parser.extract_pages") as mock_parse:
        mock_parse.return_value = [{"page": 1, "text": "Extracted text."}]
        with patch("app.core.pgvector_store.embedder.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.0] * 768]
            resp = await client.post(f"/api/documents/{doc.id}/reprocess", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == doc.id
    assert data["status"] in ("ready", "processing")


# ── 5. Progress callback in _do_process_document (S1) ───────────────────────


@pytest.mark.asyncio
async def test_do_process_document_progress_callback(
    db_session: AsyncSession, user: User, tmp_path
):
    """_do_process_document should trigger progress_callback at each phase."""
    file_path = tmp_path / "proc_test.txt"
    file_path.write_text("Line of text for process testing.")

    doc = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        filename="proc_test.txt",
        file_path=str(file_path),
        status="processing",
    )
    db_session.add(doc)
    await db_session.commit()

    progress_reports = []

    async def mock_cb(p: float, msg: str):
        progress_reports.append((p, msg))

    with patch("app.services.document_service.document_parser.extract_pages") as mock_parse:
        mock_parse.return_value = [{"page": 1, "text": "Page text content."}]
        with patch("app.core.pgvector_store.embedder.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.1] * 768]
            count, method = await document_service._do_process_document(
                db_session, user, doc.id, progress_callback=mock_cb
            )

    assert count >= 1
    assert len(progress_reports) >= 4
    # Check that progress reaches 1.0
    final_p, _ = progress_reports[-1]
    assert final_p == 1.0


# ── 6. PgVectorStore FTS fallback probe & batching (P10, P11) ────────────────


@pytest.mark.asyncio
async def test_fts_probe_fallback(db_session: AsyncSession):
    """_get_fts_config should return 'simple' if 'zh' config does not exist."""
    fake_db = AsyncMock()
    # Simulate SELECT 1 FROM pg_ts_config returning None/exception
    fake_db.execute.side_effect = Exception("No such table pg_ts_config")
    import app.core.pgvector_store as pvs

    pvs._cached_fts_config = None  # reset cache

    cfg = await _get_fts_config(fake_db)
    assert cfg == "simple"


@pytest.mark.asyncio
async def test_add_chunks_batches_rows(db_session: AsyncSession):
    """add_chunks should batch execution when rows exceed BATCH_SIZE."""
    store = PgVectorStore(user_id="batch_user", dimension=768)
    # Create 150 chunks
    many_chunks = [{"text": f"text chunk number {i}"} for i in range(150)]
    fake_embeddings = [[0.0] * 768 for _ in range(150)]

    fake_db = AsyncMock()
    with patch("app.core.pgvector_store.embedder.embed_texts", new_callable=AsyncMock) as mock_emb:
        mock_emb.return_value = fake_embeddings
        ok = await store.add_chunks(many_chunks, "doc-batch-1", db=fake_db)

    assert ok is True
    # With batch_size = 100, 150 items should execute execute() at least 2 times
    assert fake_db.execute.await_count >= 2


# ── 7. Config dimension validation (P9) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_config_endpoint_rejects_dimension_mismatch(
    client, db_session: AsyncSession, user: User
):
    """PUT /api/config/llm should reject dimensions differing from settings.embedding_dimension (768)."""
    token = create_access_token(data={"sub": user.id, "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "provider": "openrouter",
        "model_name": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 2048,
        "embedding_model": "BAAI/bge-m3",
        "embedding_dimension": 1024,  # Mismatch!
    }
    resp = await client.put("/api/config/llm", json=payload, headers=headers)
    assert resp.status_code == 422
    assert "768" in resp.json()["detail"]
