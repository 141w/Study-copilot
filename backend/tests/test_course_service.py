"""Tests for course service: CRUD + document associations."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import CourseSpace, Document, User
from app.exceptions import NotFoundError
from app.services import course_service


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(id="svc-course-user", username="svc_course", email="c@t.com", password_hash="x" * 60)
    db_session.add(u)
    await db_session.commit()
    return u


def _course(user_id: str, name: str = "Test Course"):
    return CourseSpace(
        id=str(uuid.uuid4()), user_id=user_id, name=name, description="desc",
    )


def _doc(user_id: str, filename: str = "doc.pdf"):
    return Document(
        id=str(uuid.uuid4()), user_id=user_id, filename=filename,
        file_path=f"/tmp/{uuid.uuid4()}.pdf", status="ready", chunk_count=5,
    )


# ── CRUD ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_course_space(db_session: AsyncSession, user: User):
    course = await course_service.create_course_space(db_session, user, name="Math", description="Algebra")
    assert course.id is not None
    assert course.name == "Math"
    assert course.user_id == user.id


@pytest.mark.asyncio
async def test_list_course_spaces(db_session: AsyncSession, user: User):
    c1 = _course(user.id, "Course A")
    c2 = _course(user.id, "Course B")
    db_session.add_all([c1, c2])
    await db_session.commit()

    result = await course_service.list_course_spaces(db_session, user)
    assert len(result) == 2
    names = [c.name for c in result]
    assert "Course A" in names


@pytest.mark.asyncio
async def test_get_course_space(db_session: AsyncSession, user: User):
    c = _course(user.id)
    db_session.add(c)
    await db_session.commit()

    result = await course_service.get_course_space(db_session, user, c.id)
    assert result.name == c.name


@pytest.mark.asyncio
async def test_get_course_space_raises_for_other_user(db_session: AsyncSession, user: User):
    other = User(id="other-cs", username="other", email="o@t.com", password_hash="x" * 60)
    db_session.add(other)
    c = _course(other.id)
    db_session.add(c)
    await db_session.commit()

    with pytest.raises(NotFoundError):
        await course_service.get_course_space(db_session, user, c.id)


@pytest.mark.asyncio
async def test_update_course_space(db_session: AsyncSession, user: User):
    c = _course(user.id)
    db_session.add(c)
    await db_session.commit()

    updated = await course_service.update_course_space(
        db_session, user, c.id, name="Updated Name", description="New desc",
    )
    assert updated.name == "Updated Name"
    assert updated.description == "New desc"


@pytest.mark.asyncio
async def test_delete_course_space(db_session: AsyncSession, user: User):
    c = _course(user.id)
    db_session.add(c)
    await db_session.commit()
    cid = c.id

    await course_service.delete_course_space(db_session, user, cid)

    result = await db_session.get(CourseSpace, cid)
    assert result is None


# ── Document Associations ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_document_to_course(db_session: AsyncSession, user: User):
    c = _course(user.id)
    d = _doc(user.id)
    db_session.add_all([c, d])
    await db_session.commit()

    await course_service.add_document_to_course(db_session, user, c.id, d.id)

    docs = await course_service.get_course_documents(db_session, user, c.id)
    assert [d.id for d in docs] == [d.id]


@pytest.mark.asyncio
async def test_add_document_to_course_raises_for_wrong_user(db_session: AsyncSession, user: User):
    other = User(id="other-doc", username="other2", email="o2@t.com", password_hash="x" * 60)
    db_session.add(other)
    c = _course(user.id)
    d = _doc(other.id)
    db_session.add_all([c, d])
    await db_session.commit()

    with pytest.raises(NotFoundError):
        await course_service.add_document_to_course(db_session, user, c.id, d.id)


@pytest.mark.asyncio
async def test_get_course_documents(db_session: AsyncSession, user: User):
    c = _course(user.id)
    d1 = _doc(user.id, "doc1.pdf")
    d2 = _doc(user.id, "doc2.pdf")
    db_session.add_all([c, d1, d2])
    await db_session.commit()

    await course_service.add_document_to_course(db_session, user, c.id, d1.id)
    await course_service.add_document_to_course(db_session, user, c.id, d2.id)

    docs = await course_service.get_course_documents(db_session, user, c.id)
    assert len(docs) == 2
    filenames = [d.filename for d in docs]
    assert "doc1.pdf" in filenames and "doc2.pdf" in filenames


@pytest.mark.asyncio
async def test_remove_document_from_course(db_session: AsyncSession, user: User):
    c = _course(user.id)
    d = _doc(user.id)
    db_session.add_all([c, d])
    await db_session.commit()

    await course_service.add_document_to_course(db_session, user, c.id, d.id)
    docs_before = await course_service.get_course_documents(db_session, user, c.id)
    assert len(docs_before) == 1

    await course_service.remove_document_from_course(db_session, user, c.id, d.id)
    docs_after = await course_service.get_course_documents(db_session, user, c.id)
    assert len(docs_after) == 0
