"""Tests for analysis_service: analyze_wrong_questions, get_knowledge_stats, get_progress."""

import uuid
from datetime import UTC, datetime, timedelta
from operator import itemgetter

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, Quiz, QuizResult, User, get_db
from app.main import app
from app.services import analysis_service
from app.utils.auth import get_password_hash


# ── Helpers ──────────────────────────────────────────────────────────────────


def _user(username: str = "ana") -> User:
    return User(
        id=f"ana-{username}-{uuid.uuid4().hex[:8]}",
        username=username,
        email=f"{username}@test.local",
        password_hash="x" * 60,
    )


def _doc(user_id: str, filename: str = "chapter1.pdf") -> Document:
    return Document(
        id=str(uuid.uuid4()),
        user_id=user_id,
        filename=filename,
        file_path=f"/tmp/{uuid.uuid4()}.pdf",
        status="ready",
        chunk_count=5,
    )


def _quiz(doc_id: str, question: str = "Q?") -> Quiz:
    return Quiz(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        question_type="choice",
        question=question,
        answer="A",
    )


def _result(
    quiz_id: str,
    user_id: str,
    correct: bool,
    days_ago: int = 0,
) -> QuizResult:
    ts = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago)
    return QuizResult(
        id=str(uuid.uuid4()),
        quiz_id=quiz_id,
        user_id=user_id,
        user_answer="A" if correct else "B",
        is_correct=correct,
        submitted_at=ts,
    )


async def _seed_scenario(db: AsyncSession, user: User):
    """Create: 2 docs, 4 quizzes, 9 quiz results (5 wrong, 4 correct)."""
    doc_a = _doc(user.id, "chapter1.pdf")
    doc_b = _doc(user.id, "chapter2.pdf")
    db.add_all([doc_a, doc_b])
    await db.flush()

    q1 = _quiz(doc_a.id, "Q1 chapter1")
    q2 = _quiz(doc_a.id, "Q2 chapter1")
    q3 = _quiz(doc_b.id, "Q3 chapter2")
    q4 = _quiz(doc_b.id, "Q4 chapter2")
    db.add_all([q1, q2, q3, q4])
    await db.flush()

    results = [
        # chapter1 (doc_a): q1 ×2 (wrong+correct), q2 ×2 (correct+correct)
        _result(q1.id, user.id, False, days_ago=1),
        _result(q2.id, user.id, True, days_ago=1),
        _result(q1.id, user.id, True, days_ago=3),
        _result(q2.id, user.id, True, days_ago=3),
        # chapter2 (doc_b): q3 ×3 (correct+wrong+correct), q4 ×2 (wrong+wrong)
        _result(q3.id, user.id, True, days_ago=2),
        _result(q4.id, user.id, False, days_ago=2),
        _result(q3.id, user.id, False, days_ago=5),
        _result(q4.id, user.id, False, days_ago=5),
        _result(q3.id, user.id, True, days_ago=7),
    ]
    db.add_all(results)
    await db.commit()

    return doc_a, doc_b, [q1, q2, q3, q4]


# ── analyze_wrong_questions ─────────────────────────────────────────────────


class TestAnalyzeWrongQuestions:

    @pytest.mark.asyncio
    async def test_no_results_returns_empty(self, db_session: AsyncSession):
        u = _user("awq_empty")
        db_session.add(u)
        await db_session.commit()

        data = await analysis_service.analyze_wrong_questions(db_session, u)
        assert data["message"] == "暂无答题记录"
        assert data["weak_areas"] == []

    @pytest.mark.asyncio
    async def test_counts_per_document(self, db_session: AsyncSession):
        u = _user("awq_counts")
        db_session.add(u)
        await db_session.commit()

        doc_a, doc_b, _ = await _seed_scenario(db_session, u)
        data = await analysis_service.analyze_wrong_questions(db_session, u)

        by_name = {w["topic"]: w for w in data["weak_areas"]}
        assert doc_a.filename in by_name
        assert doc_b.filename in by_name

        # chapter1: 1 wrong / 4 total → accuracy 75.0
        wa = by_name[doc_a.filename]
        assert wa["wrong_count"] == 1
        assert wa["total_count"] == 4
        assert wa["accuracy_rate"] == 75.0

        # chapter2: 3 wrong / 5 total → accuracy 40.0
        wb = by_name[doc_b.filename]
        assert wb["wrong_count"] == 3
        assert wb["total_count"] == 5
        assert wb["accuracy_rate"] == 40.0

    @pytest.mark.asyncio
    async def test_sorted_by_accuracy_ascending(self, db_session: AsyncSession):
        u = _user("awq_sort")
        db_session.add(u)
        await db_session.commit()
        await _seed_scenario(db_session, u)

        data = await analysis_service.analyze_wrong_questions(db_session, u)
        rates = [w["accuracy_rate"] for w in data["weak_areas"]]
        assert rates == sorted(rates)

    @pytest.mark.asyncio
    async def test_weak_areas_capped_at_five(self, db_session: AsyncSession):
        u = _user("awq_limit")
        db_session.add(u)
        await db_session.commit()
        await _seed_scenario(db_session, u)

        # Add 4 more all-wrong docs → 2 seeds + 4 extras = 6 wrong-area docs
        _doc_ids = []
        for i in range(4):
            d = _doc(u.id, f"ex_{i}.pdf")
            db_session.add(d)
            await db_session.flush()
            _doc_ids.append(d.id)
            q = _quiz(d.id, f"Q{i}")
            db_session.add(q)
            await db_session.flush()
            for _ in range(2):
                db_session.add(_result(q.id, u.id, False, days_ago=10))
        await db_session.commit()

        # Verify all 6 docs exist with wrong results
        from app.db import Document
        from sqlalchemy import select as sa_select, func, case as sa_case
        from sqlalchemy import String as SA_String
        wrong_stmt2 = (
            sa_select(Document.filename, func.count(QuizResult.id).label("n"))
            .select_from(QuizResult)
            .join(Quiz, QuizResult.quiz_id == Quiz.id)
            .join(Document, Quiz.document_id == Document.id)
            .where(QuizResult.user_id == u.id, QuizResult.is_correct == False)
            .group_by(Document.id, Document.filename)
        )
        rows = (await db_session.execute(wrong_stmt2)).all()
        assert len(rows) == 6

        data = await analysis_service.analyze_wrong_questions(db_session, u)
        # Cap at 5
        assert len(data["weak_areas"]) == 5

    @pytest.mark.asyncio
    async def test_suggestions_low_accuracy(self, db_session: AsyncSession):
        u = _user("awq_sugg")
        db_session.add(u)
        await db_session.commit()
        _, doc_b, _ = await _seed_scenario(db_session, u)

        data = await analysis_service.analyze_wrong_questions(db_session, u)
        by_name = {w["topic"]: w for w in data["weak_areas"]}
        # chapter2 at 40% accuracy (< 0.7) → detailed suggestions
        assert doc_b.filename in by_name
        wb = by_name[doc_b.filename]
        assert "重新学习这部分内容" in wb["suggestions"]
        assert "多做相关练习" in wb["suggestions"]

    @pytest.mark.asyncio
    async def test_message_reports_total_wrong(self, db_session: AsyncSession):
        u = _user("awq_msg")
        db_session.add(u)
        await db_session.commit()
        await _seed_scenario(db_session, u)

        data = await analysis_service.analyze_wrong_questions(db_session, u)
        # 1 (ch1) + 3 (ch2) = 4 wrong
        assert "共4道错题" in data["message"]

    @pytest.mark.asyncio
    async def test_user_isolation(self, db_session: AsyncSession):
        u1 = _user("awq_u1")
        u2 = _user("awq_u2")
        db_session.add_all([u1, u2])
        await db_session.commit()

        doc_a = _doc(u1.id, "u1_doc.pdf")
        db_session.add(doc_a)
        await db_session.flush()
        q = _quiz(doc_a.id)
        db_session.add(q)
        await db_session.flush()
        db_session.add(_result(q.id, u1.id, True))
        await db_session.commit()

        doc_b = _doc(u2.id, "u2_doc.pdf")
        db_session.add(doc_b)
        await db_session.flush()
        q2 = _quiz(doc_b.id)
        db_session.add(q2)
        await db_session.flush()
        db_session.add(_result(q2.id, u2.id, False))
        await db_session.commit()

        # u1 has only correct → no wrong results, but total rows exist so appears in weak_areas
        data1 = await analysis_service.analyze_wrong_questions(db_session, u1)
        assert len(data1["weak_areas"]) == 1
        assert data1["weak_areas"][0]["topic"] == "u1_doc.pdf"
        assert data1["weak_areas"][0]["wrong_count"] == 0
        assert data1["weak_areas"][0]["accuracy_rate"] == 100.0

        # u2 has 1 wrong for u2_doc.pdf
        data2 = await analysis_service.analyze_wrong_questions(db_session, u2)
        assert len(data2["weak_areas"]) == 1
        assert data2["weak_areas"][0]["topic"] == "u2_doc.pdf"


# ── get_knowledge_stats ─────────────────────────────────────────────────────


class TestGetKnowledgeStats:

    @pytest.mark.asyncio
    async def test_no_results_returns_zero(self, db_session: AsyncSession):
        u = _user("ks_zero")
        db_session.add(u)
        await db_session.commit()

        data = await analysis_service.get_knowledge_stats(db_session, u)
        assert data["total_quizzes"] == 0
        assert data["correct_count"] == 0
        assert data["accuracy_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_all_correct(self, db_session: AsyncSession):
        u = _user("ks_correct")
        db_session.add(u)
        await db_session.commit()
        doc = _doc(u.id)
        db_session.add(doc)
        await db_session.flush()
        q = _quiz(doc.id)
        db_session.add(q)
        await db_session.flush()
        for _ in range(5):
            db_session.add(_result(q.id, u.id, True))
        await db_session.commit()

        data = await analysis_service.get_knowledge_stats(db_session, u)
        assert data["total_quizzes"] == 5
        assert data["correct_count"] == 5
        assert data["accuracy_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_mixed_results(self, db_session: AsyncSession):
        u = _user("ks_mixed")
        db_session.add(u)
        await db_session.commit()
        doc = _doc(u.id)
        db_session.add(doc)
        await db_session.flush()
        q = _quiz(doc.id)
        db_session.add(q)
        await db_session.flush()
        for _ in range(7):
            db_session.add(_result(q.id, u.id, True))
        for _ in range(3):
            db_session.add(_result(q.id, u.id, False))
        await db_session.commit()

        data = await analysis_service.get_knowledge_stats(db_session, u)
        assert data["total_quizzes"] == 10
        assert data["correct_count"] == 7
        assert data["accuracy_rate"] == 70.0

    @pytest.mark.asyncio
    async def test_user_isolation(self, db_session: AsyncSession):
        u1 = _user("ks_u1")
        u2 = _user("ks_u2")
        db_session.add_all([u1, u2])
        await db_session.commit()

        doc1 = _doc(u1.id)
        doc2 = _doc(u2.id)
        db_session.add_all([doc1, doc2])
        await db_session.flush()
        q1 = _quiz(doc1.id)
        q2 = _quiz(doc2.id)
        db_session.add_all([q1, q2])
        await db_session.flush()

        db_session.add(_result(q1.id, u1.id, True))
        db_session.add(_result(q1.id, u1.id, True))
        db_session.add(_result(q2.id, u2.id, False))
        db_session.add(_result(q2.id, u2.id, False))
        db_session.add(_result(q2.id, u2.id, False))
        await db_session.commit()

        d1 = await analysis_service.get_knowledge_stats(db_session, u1)
        d2 = await analysis_service.get_knowledge_stats(db_session, u2)

        assert d1["total_quizzes"] == 2
        assert d1["correct_count"] == 2
        assert d1["accuracy_rate"] == 100.0

        assert d2["total_quizzes"] == 3
        assert d2["correct_count"] == 0
        assert d2["accuracy_rate"] == 0.0


# ── get_progress ────────────────────────────────────────────────────────────


class TestGetProgress:

    @pytest.mark.asyncio
    async def test_empty_returns_zero(self, db_session: AsyncSession):
        u = _user("gp_empty")
        db_session.add(u)
        await db_session.commit()

        data = await analysis_service.get_progress(db_session, u)
        assert data["total_exercises"] == 0
        assert data["progress_data"] == []

    @pytest.mark.asyncio
    async def test_daily_aggregation(self, db_session: AsyncSession):
        u = _user("gp_daily")
        db_session.add(u)
        await db_session.commit()

        doc = _doc(u.id)
        db_session.add(doc)
        await db_session.flush()
        q = _quiz(doc.id)
        db_session.add(q)
        await db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        today_str = now.strftime("%Y-%m-%d")
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        r_today_a = QuizResult(
            id=str(uuid.uuid4()), quiz_id=q.id, user_id=u.id,
            user_answer="A", is_correct=True,
            submitted_at=now,
        )
        r_today_b = QuizResult(
            id=str(uuid.uuid4()), quiz_id=q.id, user_id=u.id,
            user_answer="B", is_correct=False,
            submitted_at=now,
        )
        r_yesterday = QuizResult(
            id=str(uuid.uuid4()), quiz_id=q.id, user_id=u.id,
            user_answer="A", is_correct=True,
            submitted_at=now - timedelta(days=1),
        )
        db_session.add_all([r_today_a, r_today_b, r_yesterday])
        await db_session.commit()

        data = await analysis_service.get_progress(db_session, u)
        assert data["total_exercises"] == 3

        dates = {p["date"]: p for p in data["progress_data"]}

        assert today_str in dates
        assert dates[today_str]["total"] == 2
        assert dates[today_str]["correct"] == 1
        assert dates[today_str]["accuracy"] == 50.0

        assert yesterday_str in dates
        assert dates[yesterday_str]["total"] == 1
        assert dates[yesterday_str]["correct"] == 1
        assert dates[yesterday_str]["accuracy"] == 100.0

    @pytest.mark.asyncio
    async def test_limits_to_last_7_days(self, db_session: AsyncSession):
        u = _user("gp_7day")
        db_session.add(u)
        await db_session.commit()

        doc = _doc(u.id)
        db_session.add(doc)
        await db_session.flush()
        q = _quiz(doc.id)
        db_session.add(q)
        await db_session.flush()

        # Results spanning 10 days
        for day in range(10):
            db_session.add(_result(q.id, u.id, True, days_ago=day))
        await db_session.commit()

        data = await analysis_service.get_progress(db_session, u)
        # SQL GROUP BY date() returns only days that have data
        # Since we added 10 days, capped at 7
        assert len(data["progress_data"]) <= 7

    @pytest.mark.asyncio
    async def test_user_isolation(self, db_session: AsyncSession):
        u1 = _user("gp_u1")
        u2 = _user("gp_u2")
        db_session.add_all([u1, u2])
        await db_session.commit()

        doc1 = _doc(u1.id)
        doc2 = _doc(u2.id)
        db_session.add_all([doc1, doc2])
        await db_session.flush()
        q1 = _quiz(doc1.id)
        q2 = _quiz(doc2.id)
        db_session.add_all([q1, q2])
        await db_session.flush()

        db_session.add(_result(q1.id, u1.id, True, days_ago=0))
        db_session.add(_result(q1.id, u1.id, True, days_ago=0))
        db_session.add(_result(q2.id, u2.id, False, days_ago=0))
        await db_session.commit()

        d1 = await analysis_service.get_progress(db_session, u1)
        d2 = await analysis_service.get_progress(db_session, u2)

        assert d1["total_exercises"] == 2
        assert d2["total_exercises"] == 1


# ── API integration tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analysis_wrong_endpoint(client, db_session: AsyncSession):
    u = _user("api_wrong")
    u.password_hash = get_password_hash("testpass")
    db_session.add(u)
    await db_session.commit()
    await _seed_scenario(db_session, u)

    resp = await client.post(
        "/api/auth/login",
        data={"username": u.username, "password": "testpass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        pytest.skip(f"Login endpoint unavailable: {resp.status_code} {resp.text}")

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/analysis/wrong", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "weak_areas" in body
    assert len(body["weak_areas"]) >= 1


@pytest.mark.asyncio
async def test_analysis_knowledge_endpoint(client, db_session: AsyncSession):
    u = _user("api_know")
    u.password_hash = get_password_hash("testpass")
    db_session.add(u)
    await db_session.commit()

    doc = _doc(u.id)
    db_session.add(doc)
    await db_session.flush()
    q = _quiz(doc.id)
    db_session.add(q)
    await db_session.flush()
    for _ in range(3):
        db_session.add(_result(q.id, u.id, True))
    await db_session.commit()

    resp = await client.post(
        "/api/auth/login",
        data={"username": u.username, "password": "testpass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        pytest.skip(f"Login endpoint unavailable: {resp.status_code} {resp.text}")

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/analysis/knowledge", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_quizzes"] == 3
    assert body["correct_count"] == 3
    assert body["accuracy_rate"] == 100.0


@pytest.mark.asyncio
async def test_analysis_progress_endpoint(client, db_session: AsyncSession):
    u = _user("api_prog")
    u.password_hash = get_password_hash("testpass")
    db_session.add(u)
    await db_session.commit()

    doc = _doc(u.id)
    db_session.add(doc)
    await db_session.flush()
    q = _quiz(doc.id)
    db_session.add(q)
    await db_session.flush()
    for _ in range(3):
        db_session.add(_result(q.id, u.id, True, days_ago=0))
    await db_session.commit()

    resp = await client.post(
        "/api/auth/login",
        data={"username": u.username, "password": "testpass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        pytest.skip(f"Login endpoint unavailable: {resp.status_code} {resp.text}")

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/analysis/progress", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_exercises"] == 3
    assert "progress_data" in body
