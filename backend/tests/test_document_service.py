"""Tests for document service layer (CRUD + soft-delete + restore + purge)."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import Document, User
from app.exceptions import NotFoundError
from app.services import document_service

@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(id="svc-doc-user", username="svcdoc", email="s@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u

def _doc(user_id: str, filename="test.pdf", status="ready"):
    return Document(
        id=str(uuid.uuid4()), user_id=user_id, filename=filename,
        file_path=f"/tmp/{uuid.uuid4()}.pdf", status=status, chunk_count=10,
    )

@pytest.mark.asyncio
async def test_list_documents_returns_user_docs(db_session: AsyncSession, user: User):
    d1, d2 = _doc(user.id, "a.pdf"), _doc(user.id, "b.pdf")
    db_session.add_all([d1, d2])
    await db_session.commit()
    result = await document_service.list_documents(db_session, user)
    assert len(result) == 2

@pytest.mark.asyncio
async def test_list_documents_excludes_soft_deleted(db_session: AsyncSession, user: User):
    d1 = _doc(user.id)
    d2 = _doc(user.id)
    d2.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    db_session.add_all([d1, d2])
    await db_session.commit()
    result = await document_service.list_documents(db_session, user)
    assert len(result) == 1
    assert result[0].id == d1.id

@pytest.mark.asyncio
async def test_list_documents_excludes_other_users_docs(db_session: AsyncSession, user: User):
    other = User(id="other-user", username="other", email="o@t.com", password_hash="x" * 60)
    db_session.add(other)
    d_other, d_mine = _doc(other.id), _doc(user.id)
    db_session.add_all([d_other, d_mine])
    await db_session.commit()
    result = await document_service.list_documents(db_session, user)
    assert len(result) == 1
    assert result[0].id == d_mine.id

@pytest.mark.asyncio
async def test_get_document_returns_data(db_session: AsyncSession, user: User):
    d = _doc(user.id, "file.pdf")
    db_session.add(d)
    await db_session.commit()
    with patch('app.services.document_service.DocumentVectorStore') as MockVS:
        mock_store = MagicMock()
        mock_store._store.chunks = []
        MockVS.return_value = mock_store
        # get_document 对 store.load() 有 await，必须用 AsyncMock
        mock_store.load = AsyncMock()
        result = await document_service.get_document(db_session, user, d.id)
    assert result["filename"] == "file.pdf"

@pytest.mark.asyncio
async def test_get_document_raises_for_missing(db_session: AsyncSession, user: User):
    with pytest.raises(NotFoundError):
        await document_service.get_document(db_session, user, "nonexistent")

@pytest.mark.asyncio
async def test_delete_document_soft_deletes(db_session: AsyncSession, user: User):
    d = _doc(user.id)
    db_session.add(d)
    await db_session.commit()
    await document_service.delete_document(db_session, user, d.id)
    await db_session.refresh(d)
    assert d.deleted_at is not None

@pytest.mark.asyncio
async def test_delete_document_raises_for_missing(db_session: AsyncSession, user: User):
    with pytest.raises(NotFoundError):
        await document_service.delete_document(db_session, user, "nonexistent")

@pytest.mark.asyncio
async def test_restore_document_restores(db_session: AsyncSession, user: User):
    d = _doc(user.id)
    d.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    db_session.add(d)
    await db_session.commit()
    result = await document_service.restore_document(db_session, user, d.id)
    await db_session.refresh(result)
    assert result.deleted_at is None

@pytest.mark.asyncio
async def test_restore_document_raises_for_non_deleted(db_session: AsyncSession, user: User):
    d = _doc(user.id)
    db_session.add(d)
    await db_session.commit()
    with pytest.raises(NotFoundError, match="回收站"):
        await document_service.restore_document(db_session, user, d.id)

@pytest.mark.asyncio
async def test_purge_removes_old_deleted(db_session: AsyncSession, user: User):
    old_doc = _doc(user.id)
    old_doc.deleted_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=40)
    db_session.add(old_doc)
    await db_session.commit()
    with patch('os.path.exists', return_value=True), patch('os.remove'):
        with patch('app.services.document_service.DocumentVectorStore'):
            count = await document_service.purge_deleted_documents(db_session, user, older_than_days=30)
    assert count == 1
